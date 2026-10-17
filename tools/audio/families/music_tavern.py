"""Music suite "Tavern Band": four looping tracks, one per stage of the castle, played by a
small folk band in an inn, every note a real instrument recording (``sf.py``: the Fluid R3
and MuseScore General banks, both MIT). No synthesized instrument anywhere.

The band (the same in all four tracks, and the same instruments as the "tavern" jingles):
  recorder     the tune or a soft second voice
  fiddle       the tune, harmonies and, for the Kings, double stops (two strings at once)
  lute         a nylon-strung guitar played lightly as a lute: its pairs of strings are a
               second, slowly drifting copy a few milliseconds behind (``_courses``), its
               body tuned to a wooden bowl (``_lute_body``)
  bass viol    a cello: the bass line and, for the Kings, a bowed drone
  bodhran      a frame drum: the deep stroke ("doum": a brushed floor tom with a conga's
               skin) and the light rim tap ("tek": a muted conga)
  tambourine   a light shake on the off-beats (not for the menus or the Kings)
  and, sparingly: a hammered dulcimer (one pass of the Jacks' jig); for the Kings a viola
  doubling the drone, an accordion holding the chords of the middle section, a concert
  bass drum and a field drum.

One theme runs through the suite: a rising fourth from A up to D, then a turn D-E-F#-E-D
(F natural in the minor tracks). It is a slow air for the menus, a jig for the Jacks, a
bourree in D dorian for the Queens and a dark march in D minor for the Kings; tension
rises from stage to stage, and every key is centred on D (A major as the dominant colour),
so the effects never clash.

  menu   "Hearthside Air"   3/4, 72 bpm, D major. A (recorder), A (fiddle), B (fiddle, the
                            recorder below), A (recorder, the fiddle below); the lute picks
                            the chords, rolls them in B; the bass viol joins at B; no drums.
                            The band holds back a little at the end of every four bars.
  jack   "The Jack's Jig"   6/8, 100 dotted crotchets a minute, D mixolydian (C natural, an A
                            minor chord before the close). The tune (A A B B) twice round,
                            traded between recorder and fiddle, in unison, octaves or thirds;
                            the second time round opens with the fiddle alone, low.
  queen  "Queen's Bourree"  2/2, 120, D dorian (B natural: a G major chord). A A B B A: the
                            B section turns to F and C with dotted, pushing rhythms; the bass
                            viol walks in crotchets under it.
  king   "The King's March" 4/4, 96, D minor. A A B A: fiddle double stops over a bowed drone
                            (on D, shifting to A under the C and A chords), lute strums, the
                            drums marching; the B section turns to F, the drone stops, the
                            accordion holds the chords and the drums thin out.

How a track is made: the score is written bar by bar (``_tune``: "D5:2 E5:1 | ..."), the
harmony too (``_harm``); second voices, double stops and the accompaniments are derived from
the harmony so they never clash with it. Every note is nudged a few milliseconds and its
velocity a few percent (seeded), as players do; bowed and blown instruments are played a
little early so they speak on the beat (``EARLY``), long notes swell, the jig lilts, and in
the dances the fiddle's and bass viol's slow sampled bow is firmed up (``_bow_attack``).
Each instrument is rendered on its own (stereo, placed on a small stage, ``PAN``), shaped
and balanced by loudness; the band is put in one room (``synth.reverb``), rendered past the
loop's end and folded back onto its start (the loop is seamless), and rotated to a quiet
start for the AAC encoder. The beat is nudged (``music.aac_unit``) so each loop is a whole
number of AAC frames.
"""
from __future__ import annotations

import dataclasses
import functools
import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

import music
import sf
import synth as A
from catalog import Candidate
from sf import DRUM, GM, Note

SR = A.SR
Ev = Tuple[float, float, int, float]          # (start, length, MIDI pitch, velocity 0..1), in units

RECORDER, FIDDLE, LUTE = GM["recorder"], GM["fiddle"], GM["nylon_guitar"]
CELLO, VIOLA, ACCORDION, DULCIMER = GM["cello"], GM["viola"], GM["accordion"], GM["dulcimer"]

# the band's places on a small stage (-1 left .. 1 right)
PAN = {"recorder": -0.22, "fiddle": 0.38, "lute": -0.02, "bass viol": 0.12, "viola": -0.16, "accordion": -0.22,
       "dulcimer": 0.12, "bodhran": 0.0, "tambourine": 0.3, "bass drum": 0.0, "field drum": 0.18}

TAIL = 5.0                                     # seconds rendered past the loop, folded back


def _m(p) -> int:
    return A.midi(p) if isinstance(p, str) else int(p)


# ============================================================================= the score
def _tune(text: str, bar: float, vel: float = 0.7, strong: Sequence[float] = (0.0,),
          offset: float = 0.0) -> List[Ev]:
    """A melody written bar by bar: "D5:2 E5:1 | F#5:1.5 E5:0.5 D5:1", durations in the
    track's unit, "r" a rest. Every bar must add up to ``bar``. Downbeats are leaned on,
    the other ``strong`` positions a little, and higher notes sing out slightly."""
    out: List[Ev] = []
    for i, b in enumerate(text.split("|")):
        pos = 0.0
        for tok in b.split():
            p, d = tok.split(":")
            d = float(d)
            if p != "r":
                m = _m(p)
                v = vel + (0.08 if pos == 0 else (0.04 if any(abs(pos - s) < 1e-6 for s in strong) else 0.0))
                v += 0.004 * (m - 74)
                out.append((offset + i * bar + pos, d, m, float(np.clip(v, 0.15, 1.0))))
            pos += d
        if abs(pos - bar) > 1e-6:
            raise ValueError("bar %d adds up to %s, not %s: %r" % (i + 1, pos, bar, b))
    return out


def _harm(text: str, bar: float, offset: float = 0.0) -> List[Tuple[float, float, str]]:
    """Chords bar by bar: "D | Bm | Em:2 A:1 | C G" (a bar's chords share it equally
    unless given lengths)."""
    out = []
    for i, b in enumerate(text.split("|")):
        toks = b.split()
        if all(":" in t for t in toks):
            lens = [float(t.split(":")[1]) for t in toks]
            names = [t.split(":")[0] for t in toks]
        else:
            names = toks
            lens = [bar / len(toks)] * len(toks)
        if abs(sum(lens) - bar) > 1e-6:
            raise ValueError("harmony bar %d: %r" % (i + 1, b))
        pos = 0.0
        for name, L in zip(names, lens):
            out.append((offset + i * bar + pos, L, name))
            pos += L
    return out


# chord: (bass, upper voicing low to high); the voicings sit around D4 and share common
# tones, so chord changes move by step
CHORDS: Dict[str, Tuple[str, List[str]]] = {
    "D": ("D3", ["A3", "D4", "F#4"]), "D/F#": ("F#2", ["A3", "D4", "F#4"]), "Bm": ("B2", ["B3", "D4", "F#4"]),
    "G": ("G2", ["B3", "D4", "G4"]), "A": ("A2", ["A3", "C#4", "E4"]), "Em": ("E3", ["B3", "E4", "G4"]),
    "C": ("C3", ["G3", "C4", "E4"]), "Am": ("A2", ["A3", "C4", "E4"]), "Dm": ("D3", ["A3", "D4", "F4"]),
    "F": ("F2", ["A3", "C4", "F4"]), "Gm": ("G2", ["Bb3", "D4", "G4"]), "Bb": ("Bb2", ["Bb3", "D4", "F4"]),
}


def _bass(ch: str) -> int:
    return _m(CHORDS[ch][0])


def _upper(ch: str) -> List[int]:
    return [_m(p) for p in CHORDS[ch][1]]


def _tones(ch: str) -> set:
    return {p % 12 for p in _upper(ch) + [_bass(ch)]}


def _chord_at(harm, t: float) -> str:
    for s, L, name in harm:
        if s - 1e-6 <= t < s + L - 1e-6:
            return name
    return harm[-1][2]


def _alt_bass(ch: str) -> int:
    """The fifth for an alternating bass: below the root when the root is high enough."""
    b = _bass(ch)
    return b - 5 if b >= _m("C3") else b + 7


SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10],
          "dorian": [0, 2, 3, 5, 7, 9, 10], "aeolian": [0, 2, 3, 5, 7, 8, 10]}


def _diatonic(m: int, steps: int, mode: str) -> int:
    """Move a pitch by scale steps in D ``mode`` (a pitch outside the mode moves from its
    nearest scale tone below)."""
    pcs = [(2 + s) % 12 for s in SCALES[mode]]
    ladder = [k for k in range(24, 108) if k % 12 in pcs]
    i = max(j for j, k in enumerate(ladder) if k <= m)
    return ladder[i + steps]


def _second_voice(mel: List[Ev], harm, mode: str, beat: float, vel: float = 0.8, below: bool = True) -> List[Ev]:
    """A folk second voice a third below (or above) the tune; on the beats and under long
    notes, where the third is not in the chord, the nearest chord tone a fourth to a sixth
    away instead."""
    out = []
    sgn = -1 if below else 1
    for s, L, m, v in mel:
        h = _diatonic(m, 2 * sgn, mode)
        on_beat = abs(s / beat - round(s / beat)) < 1e-6
        if on_beat or L >= beat - 1e-6:
            tones = _tones(_chord_at(harm, s))
            if h % 12 not in tones:
                for steps in (3, 4, 5):
                    c = _diatonic(m, steps * sgn, mode)
                    if c % 12 in tones:
                        h = c
                        break
        out.append((s, L, h, v * vel))
    return out


def _double_stops(mel: List[Ev], harm, min_len: float, vel: float = 0.78) -> List[Ev]:
    """A fiddler's double stops: under each long note, the highest chord tone a third to a
    sixth below it (often an open string), played on the same bow."""
    out = []
    for s, L, m, v in mel:
        if L < min_len - 1e-6:
            continue
        tones = _tones(_chord_at(harm, s))
        for k in range(3, 10):
            if (m - k) % 12 in tones and m - k >= _m("G3"):          # G3: the fiddle's lowest string
                out.append((s, L, m - k, v * vel))
                break
    return out


def _shift(evs: List[Ev], semis: int = 0, vel: float = 1.0, offset: float = 0.0) -> List[Ev]:
    return [(s + offset, L, m + semis, v * vel) for s, L, m, v in evs]


def _within(evs: List[Ev], a: float, b: float) -> List[Ev]:
    """The events that start in [a, b)."""
    return [e for e in evs if a - 1e-6 <= e[0] < b - 1e-6]


# ----------------------------------------------------------------------------- accompaniments
def _arpeggio(harm, unit: float, order=(None, 0, 1, 2, 1, 0), vel: float = 0.5, ring: float = 1.0) -> List[Ev]:
    """A picked broken chord: one note per ``unit`` through each chord, ``None`` the bass;
    every string rings until the chord changes."""
    out = []
    for s, L, ch in harm:
        k = 0
        t = s
        while t < s + L - 1e-6:
            idx = order[k % len(order)]
            m = _bass(ch) if idx is None else _upper(ch)[idx]
            v = vel * (1.12 if idx is None else 1.0) * (1.08 if k == 0 else 1.0)
            out.append((t, (s + L - t) * ring + 0.08 * unit, m, min(1.0, v)))
            k += 1
            t += unit
    return out


def _roll(t: float, pitches: Sequence[int], L: float, v: float, spread: float) -> List[Ev]:
    return [(t + i * spread, L, p, v * (1.0 - 0.04 * i)) for i, p in enumerate(pitches)]


# ============================================================================= rendering
# how much earlier each instrument is played so it speaks on the beat: the bow and the
# breath take time to sound (measured on the banks' samples: the fiddle is at -12 dB of its
# full tone after 40 ms, the recorder at -6 dB, a plucked string after 10 ms)
EARLY = {RECORDER: 0.018, FIDDLE: 0.034, CELLO: 0.05, VIOLA: 0.045, ACCORDION: 0.03}


def _notes(program: int, evs: List[Ev], unit_s: float, loop_s: float, seed: int, jitter: float = 0.008,
           legato: float = 0.92, swell_from: Optional[float] = None, swell=(96, 124), pan: float = 0.0,
           vel: float = 1.0, kit: str = "standard", drum_map: Optional[Dict[str, List[Tuple[str, float]]]] = None,
           lilt: float = 0.0, warp: Optional[Callable[[float], float]] = None) -> List[Note]:
    """Events (in units) to bank notes: seconds, a human nudge in time and velocity
    (seeded), ``legato`` of each length held, a swell on notes at least ``swell_from``
    units long. ``lilt`` (units) delays the middle quaver of each three, a jig's lilt;
    ``warp`` (units -> seconds) bends the time of every part alike (a breath at the end of
    a phrase). A note nudged before the loop's start wraps round to its end."""
    rng = np.random.default_rng(seed)
    out: List[Note] = []
    early = EARLY.get(program, 0.0)
    for s, L, m, v in evs:
        if lilt and abs((s % 3.0) - 1.0) < 1e-6:
            s += lilt
        t = s * unit_s - early + rng.uniform(-jitter, jitter)
        dur = max(0.04, L * unit_s * legato)
        if warp is not None:
            t += warp(s)
            dur = max(0.04, dur + warp(s + L) - warp(s))
        if t < 0:
            t += loop_s
        v127 = int(np.clip(round(127 * v * vel * rng.uniform(0.94, 1.04)), 1, 127))
        if program == DRUM:
            for key, g in drum_map[m] if drum_map else [(m, 1.0)]:
                out.append(Note(DRUM, key, t + rng.uniform(0, 0.002), 0.1, vel=int(np.clip(v127 * g, 1, 127)),
                                pan=pan, kit=kit))
            continue
        sw = None
        if swell_from is not None and L >= swell_from - 1e-6:
            sw = tuple(int(np.clip(e + rng.integers(-4, 5), 0, 127)) for e in swell)
        out.append(Note(program, m, t, dur, vel=v127, pan=pan, swell=sw))
    return out


@functools.lru_cache(maxsize=None)
def _bank_cached(key: tuple, seconds: float, bank: str) -> np.ndarray:
    return sf.render([Note(*k) for k in key], seconds, bank=bank, stereo=True)


def _render(notes: Sequence[Note], seconds: float, bank: str) -> np.ndarray:
    key = tuple(dataclasses.astuple(n) for n in notes)
    return _bank_cached(key, round(float(seconds), 4), bank).copy()


def _render_split(notes: Sequence[Note], seconds: float, bank: str) -> np.ndarray:
    """Render in groups of notes with their own bends or swells (a render has 15 channels),
    split by time where needed, and sum."""
    plain = [n for n in notes if n.swell is None and n.bend is None]
    solo = sorted([n for n in notes if not (n.swell is None and n.bend is None)], key=lambda n: n.start)
    groups: List[List[Note]] = []
    cur: List[Note] = list(plain)
    busy: List[float] = []
    for n in solo:
        busy = [f for f in busy if f > n.start]
        if len(busy) >= 10:
            groups.append(cur)
            cur, busy = [], []
        cur.append(n)
        busy.append(n.start + n.dur + 1.6)
    groups.append(cur)
    out = None
    for g in groups:
        if not g:
            continue
        x = _render(g, seconds, bank)
        out = x if out is None else out + x
    return out if out is not None else np.zeros((A.n_of(seconds), 2))


def _fit(x: np.ndarray, n: int) -> np.ndarray:
    return x[:n] if len(x) >= n else np.concatenate([x, np.zeros((n - len(x),) + x.shape[1:])])


def _loud(x: np.ndarray) -> float:
    return A._rms_db(x)


def _at(x: np.ndarray, db: float) -> np.ndarray:
    return x * 10 ** ((db - _loud(x)) / 20.0)


def _courses(x: np.ndarray, delay_ms: float = 11.0, depth_ms: float = 1.4, rate: float = 0.27,
             gain: float = 0.6) -> np.ndarray:
    """A lute's paired strings: a second copy a few milliseconds behind whose delay drifts
    slowly, so it wanders a few cents around the first (and never drifts away in time),
    drifting differently in each ear, which widens the lute a little."""
    n = len(x)
    t = np.arange(n, dtype=float)
    out = x.copy()
    for c, ph in ((0, 0.0), (1, 1.9)):
        d = (delay_ms + depth_ms * np.sin(2 * np.pi * rate * t / SR + ph)) * SR / 1000.0
        y = np.interp(t - d, t, x[:, c], left=0.0)
        out[:, c] = x[:, c] + gain * y
    return out / math.sqrt(1 + gain * gain)


def _lute_body(x: np.ndarray) -> np.ndarray:
    """The guitar as a lute: less boom, a wooden bowl near 280 Hz, a little nasal presence,
    the top softened like gut strings under a fingertip."""
    y = A.highpass(x, 90, 2)
    y = A.peak_eq(y, 125, -4.0, 0.8)
    y = A.peak_eq(y, 280, 3.0, 1.2)
    y = A.peak_eq(y, 1100, 1.5, 1.4)
    return A.lowpass(y, 5500, 2)


def _fiddle_tone(x: np.ndarray) -> np.ndarray:
    """The fiddle's edge softened a touch for long listening (the bow's rasp near 3 kHz),
    nothing above 7.5 kHz."""
    y = A.highpass(x, 150, 2)
    y = A.peak_eq(y, 3200, -2.5, 1.0)
    return A.lowpass(y, 7500, 2)


def _recorder_tone(x: np.ndarray) -> np.ndarray:
    """Nothing below the recorder's range (the bank's low rumble), nothing above 8 kHz."""
    return A.lowpass(A.highpass(x, 200, 2), 8000, 2)


def _drum_tone(x: np.ndarray) -> np.ndarray:
    """A frame drum, not a kit: less boom, no click above 5 kHz."""
    y = A.highpass(x, 70, 2)
    y = A.peak_eq(y, 100, -4.0, 0.9)
    return A.lowpass(y, 5000, 2)


def _tamb_tone(x: np.ndarray) -> np.ndarray:
    """A tambourine's jingles, bright but not sizzling."""
    return A.lowpass(A.highpass(x, 400, 2), 7500, 4)


def _bass_tone(x: np.ndarray) -> np.ndarray:
    """Bowed bass: no sub-rumble below 55 Hz, no bow hiss above 6 kHz."""
    return A.lowpass(A.highpass(x, 55, 2), 6000, 2)


def _bow_attack(x: np.ndarray, onsets: Sequence[float], boost_db: float, tau: float) -> np.ndarray:
    """A firmer bow stroke: the banks' fiddle and cello swell in over 100-200 ms (a slow,
    slurred bow), which blurs quick dance notes. The first moments of each note (we know
    when each starts) are lifted by up to ``boost_db``, the lift dying away over ``tau``
    seconds, so each note speaks with a bite, as a fiddler's bow does in a dance."""
    n = len(x)
    a = 10 ** (boost_db / 20.0) - 1.0
    g = np.zeros(n)
    k = A.n_of(tau * 5)
    shape = a * np.exp(-np.arange(k) / (tau * SR))
    shape[:A.n_of(0.004)] *= np.linspace(0.0, 1.0, A.n_of(0.004))     # the lift itself fades in
    for t in onsets:
        i = A.n_of(t + 0.003)                                            # the bank's latency
        if i >= n:
            continue
        j = min(n, i + k)
        g[i:j] = np.maximum(g[i:j], shape[:j - i])
    return x * (1.0 + g)[:, None]


BODHRAN = {"doum": [("low_floor_tom", 0.85), ("low_conga", 0.8)], "tek": [("mute_conga", 0.75)]}


@dataclasses.dataclass
class Part:
    name: str
    notes: List[Note]
    level: float                              # loudness (dB) while it plays, before mastering
    bank: str = "fluid"
    tone: Optional[Callable[[np.ndarray], np.ndarray]] = None
    attack: Optional[Tuple[float, float]] = None   # a firmer bow (_bow_attack): (boost dB, seconds)


def _mixdown(parts: Sequence[Part], loop_s: float, room: float, wet: float, damping: float = 0.55) -> np.ndarray:
    """Render each part past the loop's end, shape and balance it, put the band in one
    room, fold everything that rings past the end back onto the start, and start the file
    at a quiet point just before the downbeat."""
    seconds = loop_s + TAIL
    mix = np.zeros((A.n_of(seconds), 2))
    for p in parts:
        x = _fit(_render_split(p.notes, seconds, p.bank), len(mix))
        if p.attack:
            x = _bow_attack(x, sorted({round(nt.start, 4) for nt in p.notes}), *p.attack)
        if p.tone:
            x = p.tone(x)
        mix += _at(x, p.level)
    mix = A.highpass(mix, 40, 2)
    wetmix = A.reverb(mix, room=room, wet=wet, damping=damping, width=0.9, tail=3.0)
    loop = A.loop_seamless(wetmix[:A.n_of(loop_s)], wetmix[A.n_of(loop_s):])
    return music.aac_friendly_start(loop)


def _breath(phrase: float, total: float, before: float, after: float, amount: float) -> Callable[[float], float]:
    """A time warp for a slow air: approaching the end of each ``phrase`` (units) the band
    holds back, up to ``amount`` seconds late at the boundary, and settles back into time
    over ``after`` units; it wraps round the loop, so the loop's length is unchanged."""
    def w(u: float) -> float:
        u = u % total
        k = round(u / phrase) * phrase
        d = u - k
        if -before <= d <= 0:
            x = 1.0 + d / before
            return amount * x * x
        if 0 < d <= after:
            x = d / after
            return amount * (1 - x) * (1 - x)
        return 0.0
    return w


def _drum_bars(pattern: Sequence[Tuple[float, str, float]], bars: Sequence[int], bar: float) -> List[Ev]:
    """A drum pattern [(position, stroke, velocity)] in the given (0-based) bars; the
    stroke rides in the pitch slot."""
    return [(b * bar + pos, 0.25, stroke, v) for b in bars for pos, stroke, v in pattern]


# ============================================================================= menu: Hearthside Air
MENU_BPM = 72.0
MENU_BEATS = 32 * 3
MENU_UNIT = music.aac_unit(60.0 / MENU_BPM, MENU_BEATS)          # a crotchet
MENU_LOOP = MENU_BEATS * MENU_UNIT

AIR_A = ("D5:2 E5:1 | F#5:1.5 E5:0.5 D5:1 | B4:2 G4:1 | A4:2 C#5:1 | "
         "D5:2 E5:1 | F#5:1 A5:1 G5:0.5 F#5:0.5 | E5:1.5 D5:0.5 C#5:1 | D5:2 A4:1")
AIR_A2 = ("D5:2 E5:1 | F#5:1.5 E5:0.5 D5:1 | B4:2 G4:1 | A4:2 C#5:1 | "
          "D5:2 E5:1 | F#5:1 A5:1 G5:0.5 F#5:0.5 | E5:1.5 D5:0.5 C#5:1 | D5:2 E5:0.5 F#5:0.5")
AIR_B = ("G5:1.5 A5:0.5 B5:1 | A5:2 F#5:1 | G5:1.5 F#5:0.5 E5:1 | E5:3 | "
         "B5:1.5 A5:0.5 G5:1 | F#5:1.5 E5:0.5 D5:1 | E5:1 G5:1 F#5:0.5 E5:0.5 | E5:2 A4:1")
AIR_A3 = ("D5:2 E5:1 | F#5:1.5 E5:0.5 D5:1 | B4:1 D5:1 G5:1 | F#5:1 E5:2 | "
          "D5:2 E5:1 | F#5:1 A5:1 G5:0.5 F#5:0.5 | E5:1.5 D5:0.5 C#5:1 | D5:2 A4:1")
AIR_H_A = "D | Bm | G | A | D | D/F# | Em:2 A:1 | D"
AIR_H_B = "G | D/F# | Em | A | G | D/F# | Em:2 A:1 | A"
# the recorder's second voice under the fiddle in B, the fiddle's under the recorder in A''
AIR_B_LOW = "B4:3 | A4:3 | B4:3 | C#5:3 | D5:3 | A4:3 | B4:2 C#5:1 | C#5:2 r:1"
AIR_A3_LOW = "A4:3 | B4:3 | G4:3 | C#5:3 | A4:3 | A4:3 | B4:2 A4:1 | F#4:3"


def _hearthside_air() -> np.ndarray:
    bar = 3.0
    u, L = MENU_UNIT, MENU_LOOP
    lead = (_tune(AIR_A, bar, 0.66) + _tune(AIR_A2, bar, 0.64, offset=8 * bar)
            + _tune(AIR_B, bar, 0.68, offset=16 * bar) + _tune(AIR_A3, bar, 0.66, offset=24 * bar))
    harm = (_harm(AIR_H_A, bar) + _harm(AIR_H_A, bar, 8 * bar) + _harm(AIR_H_B, bar, 16 * bar)
            + _harm(AIR_H_A, bar, 24 * bar))
    # who plays the tune: the recorder (bars 1-8 and 25-32, with the pick-ups into them),
    # the fiddle (9-24)
    rec_lead = _within(lead, 0, 23) + _within(lead, 71, 96)
    fid_lead = _within(lead, 23, 71)
    rec_low = _tune(AIR_B_LOW, bar, 0.5, offset=16 * bar)
    fid_low = _tune(AIR_A3_LOW, bar, 0.46, offset=24 * bar)
    # the lute: a picked broken chord in quavers, rolled chords for the B section
    lute = _arpeggio(_within(harm, 0, 48) + _within(harm, 72, 96), 0.5, vel=0.42)
    for s, Lc, ch in _within(harm, 48, 72):
        lute += _roll(s, [_bass(ch)] + _upper(ch), Lc + 0.2, 0.46, 0.06)
        if Lc >= 3:
            lute += [(s + 1, 2.1, _upper(ch)[1], 0.34), (s + 2, 1.1, _upper(ch)[2], 0.32)]
    # the bass viol, from the B section on: a long bowed root under each chord
    cello = [(s, Lc, _bass(ch), 0.5) for s, Lc, ch in _within(harm, 48, 96)]
    # the band breathes at the end of every four bars: a slight holding back, then on
    breath = _breath(12.0, MENU_BEATS, 2.5, 1.5, 0.05)
    parts = [
        Part("recorder", _notes(RECORDER, rec_lead + rec_low, u, L, 11, legato=0.95, swell_from=2,
                                swell=(100, 124), warp=breath, pan=PAN["recorder"]),
             -20.0, "fluid", _recorder_tone),
        Part("fiddle", _notes(FIDDLE, fid_lead + fid_low, u, L, 12, legato=0.97, swell_from=1.5,
                              swell=(92, 122), warp=breath, pan=PAN["fiddle"]),
             -20.5, "fluid", _fiddle_tone),
        Part("lute", _notes(LUTE, lute, u, L, 13, jitter=0.006, legato=1.0, warp=breath, pan=PAN["lute"]),
             -23.0, "musescore", lambda x: _lute_body(_courses(x))),
        Part("bass viol", _notes(CELLO, cello, u, L, 14, legato=0.98, swell_from=2, swell=(84, 112), warp=breath,
                                 pan=PAN["bass viol"]),
             -27.0, "musescore", _bass_tone),
    ]
    return _mixdown(parts, L, room=0.55, wet=0.2)


# ============================================================================= jack: The Jack's Jig
JIG_EIGHTH = music.aac_unit(0.2, 64 * 6)                         # a quaver; 100 dotted crotchets a minute
JIG_LOOP = 64 * 6 * JIG_EIGHTH

JIG_A = ("D5:2 E5:1 F#5:1 E5:1 D5:1 | C5:2 B4:1 C5:1 E5:1 G5:1 | D5:2 E5:1 F#5:1 A5:1 F#5:1 | "
         "G5:1 E5:1 C5:1 B4:1 A4:1 G4:1 | D5:2 E5:1 F#5:1 E5:1 D5:1 | C5:2 B4:1 C5:1 D5:1 E5:1 | "
         "G5:1 F#5:1 E5:1 D5:1 C5:1 A4:1 | D5:3 D5:2 {end}:1")
JIG_B = ("F#5:1 A5:1 A5:1 D6:2 A5:1 | G5:2 E5:1 G5:1 E5:1 C5:1 | F#5:1 A5:1 A5:1 D6:1 A5:1 F#5:1 | "
         "E5:2 C5:1 B4:1 A4:1 G4:1 | F#5:2 E5:1 F#5:1 G5:1 A5:1 | G5:2 E5:1 C5:2 E5:1 | "
         "G5:1 F#5:1 E5:1 D5:1 C5:1 A4:1 | D5:3 D5:2 {end}:1")
JIG_H_A = "D | C | D | C G | D | C | G Am | D"
JIG_H_B = "D | C | D | Am G | D | C | G Am | D"


def _jacks_jig() -> np.ndarray:
    bar = 6.0
    u, L = JIG_EIGHTH, JIG_LOOP
    strong = (3.0,)
    # the tune: A A B B, twice round (64 bars); the last quaver of each 8 bars leads on
    blocks = [(JIG_A, "A4"), (JIG_A, "E5"), (JIG_B, "E5"), (JIG_B, "A4")] * 2
    tune: List[List[Ev]] = []
    harm = []
    for i, (t, end) in enumerate(blocks):
        tune.append(_tune(t.format(end=end), bar, 0.66, strong, offset=i * 8 * bar))
        harm += _harm(JIG_H_A if t is JIG_A else JIG_H_B, bar, i * 8 * bar)
    third = [_second_voice(b, harm, "mixolydian", 3.0, 0.82) for b in tune]
    rec, fid, dul = [], [], []
    rec += tune[0]                                             # 1: the recorder alone
    rec += tune[1]; fid += _shift(tune[1], -12, 0.9)           # 2: the fiddle joins an octave below
    fid += tune[2]; rec += third[2]                            # 3: the fiddle leads the B part, recorder below
    fid += tune[3]; rec += _shift(tune[3], 0, 0.92)            # 4: both on the tune
    fid += _shift(tune[4], -12)                                # 5: the fiddle alone, low (a breather)
    rec += tune[5]; fid += _shift(third[5], 0, 0.95)           # 6: the recorder, the fiddle below
    fid += tune[6]; dul += _shift(tune[6], 0, 0.8)             # 7: fiddle and hammered dulcimer
    fid += tune[7]; rec += _shift(tune[7], 0, 0.92)            # 8: everyone
    # the lute: bass on the first dotted crotchet, a rolled chord on the second
    lute: List[Ev] = []
    for b in range(64):
        c1, c2 = _chord_at(harm, b * bar), _chord_at(harm, b * bar + 3)
        bass = _bass(c1) if (b % 2 == 0 or c1 != _chord_at(harm, b * bar - 3)) else _alt_bass(c1)
        lute.append((b * bar, 2.7, bass, 0.56))
        if c2 != c1:
            lute.append((b * bar + 3, 2.7, _bass(c2), 0.5))
        lute += _roll(b * bar + 3, _upper(c2), 2.5, 0.4, 0.05)
        if b // 8 in (2, 3, 6, 7):                              # a lighter chord on the last quaver, for lift
            lute += _roll(b * bar + 5, _upper(c2)[1:], 0.9, 0.26, 0.03)
    # the bodhran and tambourine
    light = [(0, "doum", 0.62), (3, "doum", 0.42)]
    full = [(0, "doum", 0.74), (2, "tek", 0.3), (3, "doum", 0.54), (5, "tek", 0.36)]
    fill = [(0, "doum", 0.74), (2, "tek", 0.3), (3, "tek", 0.36), (4, "tek", 0.44), (5, "tek", 0.52)]
    drum: List[Ev] = []
    tamb: List[Ev] = []
    for blk in range(8):
        bars = list(range(blk * 8, blk * 8 + 8))
        if blk in (0, 4):
            drum += _drum_bars(light, bars, bar)
        else:
            drum += _drum_bars(full, bars[:-1], bar)
            drum += _drum_bars(fill if blk in (3, 7) else full, bars[-1:], bar)
        if blk in (1, 5):
            tamb += _drum_bars([(3, "tambourine", 0.42)], bars, bar)
        elif blk not in (0, 4):
            tamb += _drum_bars([(0, "tambourine", 0.3), (3, "tambourine", 0.46)], bars, bar)
    lilt = 0.07
    parts = [
        Part("recorder", _notes(RECORDER, rec, u, L, 21, legato=0.88, swell_from=3, lilt=lilt, pan=PAN["recorder"]),
             -20.0, "fluid", _recorder_tone),
        Part("fiddle", _notes(FIDDLE, fid, u, L, 22, legato=0.9, swell_from=3, lilt=lilt, pan=PAN["fiddle"]),
             -20.5, "fluid", _fiddle_tone, attack=(4.0, 0.06)),
        Part("dulcimer", _notes(DULCIMER, dul, u, L, 23, jitter=0.005, legato=1.0, lilt=lilt, pan=PAN["dulcimer"]),
             -24.0, "fluid", lambda x: A.lowpass(A.highpass(x, 200, 2), 6000, 2)),
        Part("lute", _notes(LUTE, lute, u, L, 24, jitter=0.005, legato=1.0, pan=PAN["lute"]),
             -22.5, "musescore", lambda x: _lute_body(_courses(x))),
        Part("bodhran", _notes(DRUM, drum, u, L, 25, jitter=0.004, lilt=lilt, pan=PAN["bodhran"], kit="brush",
                               drum_map=BODHRAN),
             -25.5, "fluid", _drum_tone),
        Part("tambourine", _notes(DRUM, tamb, u, L, 26, jitter=0.004, lilt=lilt, pan=PAN["tambourine"]),
             -31.0, "fluid", _tamb_tone),
    ]
    return _mixdown(parts, L, room=0.45, wet=0.16)


# ============================================================================= queen: Queen's Bourree
QUEEN_BPM = 120.0
QUEEN_BEATS = 40 * 4
QUEEN_UNIT = music.aac_unit(60.0 / QUEEN_BPM, QUEEN_BEATS)
QUEEN_LOOP = QUEEN_BEATS * QUEEN_UNIT

BOUR_A = ("D5:1 D5:0.5 E5:0.5 F5:1 E5:0.5 D5:0.5 | E5:0.5 D5:0.5 C5:1 G4:1 C5:1 | D5:1 F5:1 A5:1 G5:0.5 F5:0.5 | "
          "E5:2 E5:1 A4:1 | D5:1 D5:0.5 E5:0.5 F5:1 G5:0.5 A5:0.5 | B5:1 A5:0.5 G5:0.5 D5:1 G5:1 | "
          "A5:0.5 G5:0.5 F5:0.5 E5:0.5 C#5:1 E5:1 | D5:2 D5:1 A4:1")
BOUR_B = ("A5:1.5 G5:0.5 F5:1 C5:1 | G5:1.5 F5:0.5 E5:1 C5:1 | F5:1 A5:1 D6:1 A5:1 | "
          "G5:0.5 F5:0.5 E5:0.5 D5:0.5 E5:2 | A5:1.5 G5:0.5 F5:1 C5:1 | B5:1.5 A5:0.5 G5:1 D5:1 | "
          "F5:0.5 E5:0.5 D5:0.5 F5:0.5 E5:1 C#5:1 | D5:2 D5:1 A4:1")
BOUR_H_A = "Dm | C | Dm | A | Dm | G | F A | Dm"
BOUR_H_B = "F | C | Dm | C A | F | G | Dm A | Dm"
# the recorder's long counter-line under the fiddle in the first B
BOUR_B_LOW = "C5:4 | C5:2 G4:2 | A4:4 | G4:2 A4:2 | C5:4 | B4:4 | A4:2 A4:2 | A4:3 r:1"


def _queens_bourree() -> np.ndarray:
    bar = 4.0
    u, L = QUEEN_UNIT, QUEEN_LOOP
    strong = (2.0,)
    order = [BOUR_A, BOUR_A, BOUR_B, BOUR_B, BOUR_A]
    tune = [_tune(t, bar, 0.66, strong, offset=i * 8 * bar) for i, t in enumerate(order)]
    harm = []
    for i, t in enumerate(order):
        harm += _harm(BOUR_H_A if t is BOUR_A else BOUR_H_B, bar, i * 8 * bar)
    third = [_second_voice(b, harm, "dorian", 1.0, 0.8) for b in tune]
    rec, fid = [], []
    fid += tune[0]                                             # 1: the fiddle leads
    rec += tune[1]; fid += third[1]                            # 2: the recorder, the fiddle a third below
    fid += tune[2]; rec += _tune(BOUR_B_LOW, bar, 0.5, offset=16 * bar)   # 3: fiddle, recorder's long notes
    rec += tune[3]; fid += _shift(tune[3], -12, 0.95)          # 4: recorder, the fiddle an octave below
    fid += tune[4]; rec += _shift(tune[4], 0, 0.9)             # 5: both on the tune
    # the lute: bass and a short chord, bass and chord (a bourree's two-in-a-bar)
    lute: List[Ev] = []
    for b in range(40):
        for half in (0, 2):
            t = b * bar + half
            ch = _chord_at(harm, t)
            bass = _bass(ch) if (half == 0 or ch != _chord_at(harm, t - 2)) else _alt_bass(ch)
            lute.append((t, 0.95, bass, 0.56 if half == 0 else 0.5))
            lute += _roll(t + 1, _upper(ch), 0.55, 0.38, 0.025)
    # the bass viol from the second A on: minims, then crotchets walking under the B section
    # (root, fifth, root, then a step into the next bar's root, from whichever side does
    # not rub against the tune)
    cello: List[Ev] = []
    sung = [e for blk in tune for e in blk]
    for b in range(8, 40):
        if 16 <= b < 24:
            for k in range(4):
                ch = _chord_at(harm, b * bar + k)
                nxt = _bass(_chord_at(harm, (b + 1) * bar))
                if k == 3:
                    t = b * bar + k
                    above = [m2 for s2, L2, m2, _ in sung if s2 <= t + 1e-6 < s2 + L2]
                    steps = [_diatonic(nxt, -1, "dorian"), _diatonic(nxt, 1, "dorian"), _alt_bass(ch)]
                    m = next((c for c in steps if all((a - c) % 12 not in (1, 2, 6, 10, 11) for a in above)),
                             _bass(ch))
                else:
                    m = _alt_bass(ch) if k == 1 else _bass(ch)
                cello.append((b * bar + k, 0.8, m, 0.5 if k == 0 else 0.42))
        else:
            for half in (0, 2):
                ch = _chord_at(harm, b * bar + half)
                cello.append((b * bar + half, 1.85, _bass(ch) if half == 0 else _alt_bass(ch), 0.5))
    light = [(0, "doum", 0.6), (2, "doum", 0.44), (3, "tek", 0.28)]
    full = [(0, "doum", 0.72), (1, "tek", 0.28), (1.5, "tek", 0.2), (2, "doum", 0.54), (3, "tek", 0.34),
            (3.5, "tek", 0.26)]
    fill = [(0, "doum", 0.72), (1, "tek", 0.28), (2, "doum", 0.5), (2.5, "tek", 0.3), (3, "tek", 0.4),
            (3.5, "tek", 0.5)]
    drum: List[Ev] = []
    tamb: List[Ev] = []
    for blk in range(5):
        bars = list(range(blk * 8, blk * 8 + 8))
        if blk == 0:
            drum += _drum_bars(light, bars, bar)
        else:
            drum += _drum_bars(full, bars[:-1], bar) + _drum_bars(fill, bars[-1:], bar)
            tamb += _drum_bars([(1, "tambourine", 0.4), (3, "tambourine", 0.44)], bars, bar)
    parts = [
        Part("fiddle", _notes(FIDDLE, fid, u, L, 31, legato=0.88, swell_from=2, swell=(98, 124), pan=PAN["fiddle"]),
             -20.0, "fluid", _fiddle_tone, attack=(4.0, 0.06)),
        Part("recorder", _notes(RECORDER, rec, u, L, 32, legato=0.9, swell_from=2, swell=(96, 122),
                                pan=PAN["recorder"]),
             -20.5, "fluid", _recorder_tone),
        Part("lute", _notes(LUTE, lute, u, L, 33, jitter=0.005, legato=1.0, pan=PAN["lute"]),
             -22.5, "musescore", lambda x: _lute_body(_courses(x))),
        Part("bass viol", _notes(CELLO, cello, u, L, 34, jitter=0.006, legato=0.9, pan=PAN["bass viol"]),
             -25.5, "musescore", _bass_tone, attack=(4.0, 0.08)),
        Part("bodhran", _notes(DRUM, drum, u, L, 35, jitter=0.004, pan=PAN["bodhran"], kit="brush",
                               drum_map=BODHRAN),
             -25.0, "fluid", _drum_tone),
        Part("tambourine", _notes(DRUM, tamb, u, L, 36, jitter=0.004, pan=PAN["tambourine"]),
             -31.0, "fluid", _tamb_tone),
    ]
    return _mixdown(parts, L, room=0.5, wet=0.16)


# ============================================================================= king: The King's March
KING_BPM = 96.0
KING_BEATS = 32 * 4
KING_UNIT = music.aac_unit(60.0 / KING_BPM, KING_BEATS)
KING_LOOP = KING_BEATS * KING_UNIT

MARCH_A = ("D5:1.5 E5:0.5 F5:1 E5:0.5 D5:0.5 | Bb4:1.5 C5:0.5 D5:1 Bb4:1 | C5:1.5 D5:0.5 E5:1 C5:1 | "
           "E5:1.5 D5:0.5 C#5:2 | D5:1.5 E5:0.5 F5:1 G5:0.5 A5:0.5 | Bb5:1.5 A5:0.5 G5:1 D5:1 | "
           "F5:1.5 E5:0.5 D5:1 C#5:1 | D5:2.5 r:1 A4:0.5")
MARCH_B = ("A5:2 G5:1 F5:1 | E5:1.5 F5:0.5 G5:1 C5:1 | F5:1.5 E5:0.5 D5:1 A4:1 | Bb4:1 C5:1 D5:1 E5:1 | "
           "F5:1.5 G5:0.5 A5:1 C6:1 | Bb5:2 A5:1 G5:1 | A5:1.5 G5:0.5 F5:0.5 E5:0.5 C#5:1 | E5:2 r:1.5 A4:0.5")
MARCH_H_A = "Dm | Bb | C | A | Dm | Gm | Bb A | Dm"
MARCH_H_B = "F | C | Dm | Bb C | F | Gm | A | A"


def _kings_march() -> np.ndarray:
    bar = 4.0
    u, L = KING_UNIT, KING_LOOP
    strong = (2.0,)
    order = [MARCH_A, MARCH_A, MARCH_B, MARCH_A]
    tune = [_tune(t, bar, 0.68, strong, offset=i * 8 * bar) for i, t in enumerate(order)]
    harm = []
    for i, t in enumerate(order):
        harm += _harm(MARCH_H_A if t is MARCH_A else MARCH_H_B, bar, i * 8 * bar)
    third = [_second_voice(b, harm, "aeolian", 1.0, 0.8) for b in tune]
    rec, fid = [], []
    fid += tune[0] + _double_stops(tune[0], harm, 1.0)                     # 1: fiddle double stops
    below = _shift(third[1], 0, 0.85)
    rec += tune[1]; fid += below + _double_stops(below, harm, 1.5)         # 2: recorder, fiddle below
    fid += tune[2] + _double_stops(tune[2], harm, 1.0)                     # 3: B, the fiddle high
    low = _shift(tune[3], -12, 0.85)
    rec += _shift(tune[3], 0, 0.92); fid += low + _double_stops(low, harm, 1.0, 0.85)   # 4: all, the fiddle low
    # the lute: a rolled chord on each strong beat, a light one on the last quaver (a march's lilt)
    lute: List[Ev] = []
    for b in range(32):
        for k in (0, 2):
            t = b * bar + k
            ch = _chord_at(harm, t)
            lute += _roll(t, [_bass(ch)] + _upper(ch), 1.7, 0.56 if k == 0 else 0.48, 0.035)
        ch = _chord_at(harm, b * bar + 3.5)
        lute += _roll(b * bar + 3.5, _upper(ch), 0.4, 0.3, 0.02)
    # the bass viol: a bowed drone under the A sections, a bow change every two bars, on D
    # but shifting to A under the C and A chords (bars 3-4 of a phrase); the bass line
    # under B; the viola doubles the drone an octave up in the last A
    cello: List[Ev] = []
    viola: List[Ev] = []
    for b in range(0, 32, 2):
        if 16 <= b < 24:
            for k in (0, 1):
                for half in (0, 2):
                    ch = _chord_at(harm, (b + k) * bar + half)
                    cello.append(((b + k) * bar + half, 1.9, _bass(ch) if half == 0 else _alt_bass(ch), 0.5))
        else:
            root = "A" if b % 8 == 2 else "D"
            cello.append((b * bar, 8.1, _m(root + "2"), 0.55))
            if b >= 24:
                viola.append((b * bar, 8.1, _m(root + "3"), 0.5))
    # the accordion only under the B section: soft held chords
    acc = [(s, Lc, m, 0.45) for s, Lc, ch in _within(harm, 64, 96) for m in _upper(ch)]
    # drums: bodhran on the strong beats, a concert bass drum on the downbeat, a field drum's
    # soft march taps and a roll into each section
    a_bars = [b for b in range(32) if not 16 <= b < 24]
    bod = _drum_bars([(0, "doum", 0.72), (2, "doum", 0.55), (3, "tek", 0.28)], a_bars, bar)
    bod += _drum_bars([(0, "doum", 0.62), (2.5, "tek", 0.24)], range(16, 24), bar)
    big = _drum_bars([(0, "bass_drum", 0.58)], [b for b in range(32) if b in a_bars or b % 2 == 0], bar)
    taps = [(1, "snare", 0.26), (1.75, "snare", 0.18), (3, "snare", 0.3), (3.5, "snare", 0.2)]
    field: List[Ev] = []
    for b in range(32):
        if b % 8 == 7:
            field += [(b * bar + 2 + i * 0.25, 0.25, "snare", 0.14 + 0.24 * i / 7) for i in range(8)]
        elif not 16 <= b < 24:
            field += _drum_bars(taps, [b], bar)
    parts = [
        Part("fiddle", _notes(FIDDLE, fid, u, L, 41, legato=0.9, swell_from=1.5, swell=(98, 124), pan=PAN["fiddle"]),
             -19.5, "fluid", _fiddle_tone, attack=(3.0, 0.08)),
        Part("recorder", _notes(RECORDER, rec, u, L, 42, legato=0.9, swell_from=1.5, swell=(96, 122),
                                pan=PAN["recorder"]),
             -20.5, "fluid", _recorder_tone),
        Part("lute", _notes(LUTE, lute, u, L, 43, jitter=0.005, legato=1.0, pan=PAN["lute"]),
             -22.5, "musescore", lambda x: _lute_body(_courses(x))),
        Part("bass viol", _notes(CELLO, cello, u, L, 44, jitter=0.006, legato=0.98, swell_from=1.5, swell=(84, 116),
                                 pan=PAN["bass viol"]),
             -24.5, "musescore", _bass_tone),
        Part("viola", _notes(VIOLA, viola, u, L, 45, legato=0.98, swell_from=4, swell=(80, 112), pan=PAN["viola"]),
             -30.0, "musescore", _bass_tone),
        Part("accordion", _notes(ACCORDION, acc, u, L, 46, legato=0.98, swell_from=2, swell=(82, 110),
                                 pan=PAN["accordion"]),
             -29.0, "fluid", lambda x: A.lowpass(A.highpass(x, 150, 2), 5000, 2)),
        Part("bodhran", _notes(DRUM, bod, u, L, 47, jitter=0.004, pan=PAN["bodhran"], kit="brush", drum_map=BODHRAN),
             -25.5, "fluid", _drum_tone),
        Part("bass drum", _notes(DRUM, big, u, L, 48, jitter=0.003, pan=PAN["bass drum"], kit="orchestra"),
             -29.5, "fluid", lambda x: A.lowpass(A.highpass(x, 45, 2), 2500, 2)),
        Part("field drum", _notes(DRUM, field, u, L, 49, jitter=0.004, pan=PAN["field drum"], kit="orchestra"),
             -30.5, "fluid", lambda x: A.lowpass(A.highpass(x, 180, 2), 6000, 2)),
    ]
    return _mixdown(parts, L, room=0.6, wet=0.18)


# ============================================================================= the candidates
CANDIDATES = [
    Candidate("music", "tavern_menu", "Hearthside Air",
              "For the menus: a gentle slow air by the fire, the band's tune sung by a recorder and then a fiddle "
              "over a softly picked lute, the two together at the end, a bass viol underneath; no drums.",
              _hearthside_air, tags=["menu"], loop_seconds=MENU_LOOP, bpm=round(60.0 / MENU_UNIT, 3)),
    Candidate("music", "tavern_jack", "The Jack's Jig",
              "For the Jacks: the same tune as a lively tavern jig, recorder and fiddle trading it over a lute, "
              "a frame drum and a tambourine, with a hammered dulcimer joining once.",
              _jacks_jig, tags=["jack"], loop_seconds=JIG_LOOP, bpm=round(60.0 / (3 * JIG_EIGHTH), 3)),
    Candidate("music", "tavern_queen", "Queen's Bourree",
              "For the Queens: the same tune as a minor-key court dance, quicker and more pressing, fiddle and "
              "recorder in harmony over lute, a walking bass viol, frame drum and tambourine.",
              _queens_bourree, tags=["queen"], loop_seconds=QUEEN_LOOP, bpm=round(60.0 / QUEEN_UNIT, 3)),
    Candidate("music", "tavern_king", "The King's March",
              "For the Kings: the same tune as a dark, driving march, the fiddle playing two strings at once over "
              "a low bowed drone, with lute, frame drum, bass drum and a soft field drum.",
              _kings_march, tags=["king"], loop_seconds=KING_LOOP, bpm=round(60.0 / KING_UNIT, 3)),
]
