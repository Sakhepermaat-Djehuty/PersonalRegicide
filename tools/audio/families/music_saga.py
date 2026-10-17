"""Music suite "Castle Saga": four looping tracks, one per stage of the castle, played by a
small cinematic orchestra in a stone hall, every note a real instrument recording
(``sf.py``: the Fluid R3 and MuseScore General banks, both MIT). No synthesized instrument
anywhere.

The orchestra (each track draws on it, so the four belong together):
  harp            the menu's voice, the Queens' hypnotic ostinato, glissandi into a climax
  strings         the string ensemble: soft chords, the violins' tune; for the Queens and
                  the Kings the MuseScore bank's real tremolo (the Fluid bank's "tremolo"
                  preset is its plain ensemble sample)
  solo cello      the MuseScore bank's cello (darker and steadier than Fluid's): the menu's
                  middle section, the Jacks' middle section, the Queens' voice-like line
  french horns    the Jacks' travelling call and the Kings' theme
  trombones, tuba the Kings' low brass
  choir           low and wordless for the Queens (and "ooh" voices singing the theme),
                  full for the Kings; a soft "ooh" choir under the Jacks' last verse
  contrabass      the bass line
  dulcimer        the Jacks' travelling ostinato
  percussion      a frame drum (a melodic tom's body with a conga's skin, a muted conga's
                  rim tap), taiko, orchestral timpani; a church organ only as a colour under
                  the Kings' choir

One theme runs through the suite, "the saga call": a rising fifth from D up to A, then a
falling line G-F-E down to a medieval cadence through C (E-C-D). It is a harp ballad for the
menus, a horn call for the Jacks, a cello lament for the Queens and a march for the Kings;
tension rises stage by stage, and every key is centred on D (A major as the dominant
colour), so the effects never clash.

  menu   "Misty Keep"        4/4, 70 bpm, D dorian. A: the harp sings the call over its own
                             broken chords and soft strings; B: the solo cello, rolled harp
                             chords; A': the violins take the call, the cello below them.
                             The players breathe at the end of every four bars.
  jack   "The Long Road"     4/4, 96 bpm, D mixolydian. A: the horn's call over a dulcimer
                             ostinato, pizzicato bass and a light frame drum; A': the violins
                             take the tune, the horn a counter-line; B: the cello sings in B
                             minor over harp and bowed bass, the drums thin out; a harp
                             glissando into A'': horn and violins together, a soft "ooh" choir.
  queen  "Veiled Queen"      3/4, 72 bpm, D minor (harmonic: A major, an E-flat chord). A
                             harp ostinato leaning on the semitone above each fifth; A: the
                             cello sings the call over a low choir; A': "ooh" voices take it,
                             a heartbeat drum enters; B: voice and cello rise over swelling
                             tremolo strings and timpani rolls to an E-flat chord and A major;
                             A'': the cello low and dark, ending open on A so it loops.
  king   "Siege of Kings"    4/4, 104 bpm, D minor. Cellos and basses drive in 3+3+2 quavers
                             under tremolo strings; A: trombones state the theme; A': horns
                             take it, choir and trombone chords; B: the choir sings the call
                             broadened over an organ colour, drums at half time, a horn
                             fanfare and a harp glissando; A'': horns, trombones and choir
                             together, timpani and taiko, rolling back into the start.

How a track is made: the score is written bar by bar (``_tune``: "D4:1 A4:3 | ..."), the
harmony too (``_harm``); chords for the strings, choir and brass are voiced so each voice
moves as little as possible (``_voicings``), and the accompaniments are derived from the
harmony so they never clash with it. Every note is nudged a few milliseconds and its
velocity a few percent (seeded), as players do; bowed and blown instruments are played a
little early so they speak on the beat (``EARLY``, measured on the banks), long bowed and
sung notes swell (expression), and the driving low strings get a firmer bow stroke
(``_bow_attack``). Each part is rendered on its own (stereo), placed on a stage (``PAN``,
per track; ``_place`` corrects the banks' own stereo leanings), shaped (``_tone_*``) and balanced by loudness; the orchestra shares one hall (``_hall``:
a reverb fed only from above 140 Hz, so the low end stays clear), is rendered 5 s past the
loop's end and folded back onto its start (the loop is seamless), and is rotated to a quiet
start for the AAC encoder. The beat is nudged (``music.aac_unit``) so each loop is a whole
number of AAC frames.
"""
from __future__ import annotations

import dataclasses
import functools
import itertools
import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

import music
import sf
import synth as A
from catalog import Candidate
from sf import DRUM, GM, Note

SR = A.SR
TAIL = 5.0                                   # seconds rendered past the loop, folded back
Ev = Tuple[float, float, object, float]      # (beat, beats, MIDI pitch or drum stroke, velocity 0..1)

HARP, STRINGS, TREMOLO, CHOIR, OOHS = GM["harp"], GM["strings"], GM["tremolo_strings"], GM["choir"], GM["voice_oohs"]
CELLO, BASS = GM["cello"], GM["contrabass"]
HORN, TROMBONE, TUBA = GM["french_horn"], GM["trombone"], GM["tuba"]
TIMPANI, TAIKO, TOM = GM["timpani"], GM["taiko"], GM["melodic_tom"]
DULCIMER, ORGAN, PIZZ = GM["dulcimer"], GM["church_organ"], GM["pizzicato"]

# how much earlier each instrument is played so it speaks on the beat (measured on the
# banks: the time each takes to reach -12 dB of its first moments, a little more for the
# slow ones)
EARLY = {STRINGS: 0.05, TREMOLO: 0.04, CHOIR: 0.07, OOHS: 0.035, CELLO: 0.045, BASS: 0.02, HORN: 0.03,
         TROMBONE: 0.03, TUBA: 0.012, ORGAN: 0.035, PIZZ: 0.008}

# the orchestra's places on the stage (-1 left .. 1 right)
PAN = {"harp": 0.32, "violins": -0.18, "strings": 0.0, "tremolo": -0.08, "cello": 0.16, "bass": 0.22,
       "horn": -0.3, "trombone": 0.3, "tuba": 0.36, "choir": 0.0, "voice": -0.06, "dulcimer": -0.36,
       "pizz": 0.2, "drum": 0.0, "taiko": -0.05, "timpani": -0.2, "organ": 0.0}


def _m(p) -> int:
    return A.midi(p) if isinstance(p, str) else int(p)


# ============================================================================= the score
def _tune(text: str, bar: float, vel: float = 0.7, offset: float = 0.0, shift: int = 0,
          accent: float = 0.07) -> List[Ev]:
    """A melody written bar by bar: "D4:1 A4:3 | G4:1.5 F4:0.5 E4:1 C4:1", lengths in
    beats, "r" a rest; every bar must add up to ``bar``. Downbeats lean a little, higher
    notes sing out slightly, ``shift`` transposes (semitones)."""
    out: List[Ev] = []
    for i, b in enumerate(text.split("|")):
        pos = 0.0
        for tok in b.split():
            p, d = tok.split(":")
            d = float(d)
            if p != "r":
                m = _m(p) + shift
                v = vel + (accent if pos == 0 else 0.0) + 0.004 * (m - 67)
                out.append((offset + i * bar + pos, d, m, float(np.clip(v, 0.12, 1.0))))
            pos += d
        if abs(pos - bar) > 1e-6:
            raise ValueError("bar %d adds up to %s, not %s: %r" % (i + 1, pos, bar, b))
    return out


def _harm(text: str, bar: float, offset: float = 0.0) -> List[Tuple[float, float, str]]:
    """Chords bar by bar: "Dm | C | Bb:2 C:2" (a bar's chords share it equally unless
    given lengths)."""
    out = []
    for i, b in enumerate(text.split("|")):
        toks = b.split()
        if all(":" in t for t in toks):
            names = [t.split(":")[0] for t in toks]
            lens = [float(t.split(":")[1]) for t in toks]
        else:
            names, lens = toks, [bar / len(toks)] * len(toks)
        if abs(sum(lens) - bar) > 1e-6:
            raise ValueError("harmony bar %d: %r" % (i + 1, b))
        pos = 0.0
        for name, L in zip(names, lens):
            out.append((offset + i * bar + pos, L, name))
            pos += L
    return out


_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SHAPES = {"": [0, 4, 7], "m": [0, 3, 7], "sus4": [0, 5, 7], "sus2": [0, 2, 7], "7": [0, 4, 7, 10],
           "m7": [0, 3, 7, 10], "5": [0, 7]}


def _pc(name: str) -> Tuple[int, str]:
    k = _PC[name[0]]
    i = 1
    while i < len(name) and name[i] in "#b":
        k += 1 if name[i] == "#" else -1
        i += 1
    return k % 12, name[i:]


@functools.lru_cache(maxsize=None)
def _chord(name: str) -> Tuple[int, Tuple[int, ...], int]:
    """(root pitch class, chord tones from the root as offsets, bass pitch class)."""
    bass = None
    if "/" in name:
        name, b = name.split("/")
        bass = _pc(b)[0]
    root, q = _pc(name)
    return root, tuple(_SHAPES[q]), root if bass is None else bass


def _in_range(pc: int, lo: str, hi: str) -> int:
    """The pitch of pitch class ``pc`` within [lo, hi] (the lowest if there are two)."""
    for m in range(_m(lo), _m(hi) + 1):
        if m % 12 == pc:
            return m
    raise ValueError("no %d in %s..%s" % (pc, lo, hi))


def _bass(name: str, lo: str = "C2", hi: str = "B2") -> int:
    return _in_range(_chord(name)[2], lo, hi)


def _deg(name: str, which: int, base_lo: str = "G2", base_hi: str = "F#3") -> int:
    """A chord tone above the root placed in [base_lo, base_hi]: ``which`` indexes the
    chord's tones (0 root, 1 third, 2 fifth), +3 for each octave up."""
    r, sh, _ = _chord(name)
    root = _in_range(r, base_lo, base_hi)
    octave, k = divmod(which, 3)
    k = min(k, len(sh) - 1)
    return root + sh[k] + 12 * octave


def _voicings(harm, k: int, lo: str, hi: str, center: Optional[str] = None,
              ceiling: Optional[Callable[[float, float], int]] = None) -> List[Tuple[float, float, List[int]]]:
    """Each chord voiced in ``k`` voices between ``lo`` and ``hi`` so every voice moves as
    little as possible from the chord before (the first sits near ``center``); every
    chord tone is present (the root doubled first), no two voices further apart than a
    sixth (a tenth at the bottom). ``ceiling(start, length)`` keeps voices below a
    melody sung by the same section."""
    out = []
    prev: Optional[List[int]] = None
    c = _m(center) if center else (_m(lo) + _m(hi)) / 2.0
    for s, L, name in harm:
        r, sh, _ = _chord(name)
        pcs = [(r + x) % 12 for x in sh]
        top = _m(hi) if ceiling is None else min(_m(hi), ceiling(s, L))
        cands = [m for m in range(_m(lo), top + 1) if m % 12 in pcs]
        best, best_cost = None, None
        for combo in itertools.combinations(cands, k):
            have = {m % 12 for m in combo}
            need = set(pcs) if k >= len(pcs) else {pcs[0], pcs[1]}
            if not need <= have:
                continue
            gaps = np.diff(combo)
            if len(gaps) and (gaps[0] > 16 or (len(gaps) > 1 and max(gaps[1:]) > 9)):
                continue
            cost = 0.0
            if prev is not None:
                cost += sum(abs(a - b) for a, b in zip(combo, prev))
            cost += 0.25 * abs(np.mean(combo) - c)
            doubled = [m % 12 for m in combo]
            if k > len(set(pcs)) and doubled.count(pcs[0]) < 2:
                cost += 1.5
            if best_cost is None or cost < best_cost:
                best, best_cost = list(combo), cost
        if best is None:
            raise ValueError("cannot voice %s in %s..%s" % (name, lo, hi))
        out.append((s, L, best))
        prev = best
    return out


def _pad(voiced, vel: float, hold: float = 1.0) -> List[Ev]:
    return [(s, L * hold, m, vel) for s, L, ms in voiced for m in ms]


def _within(evs, a: float, b: float):
    """The events (or chords) that start in [a, b)."""
    return [e for e in evs if a - 1e-6 <= e[0] < b - 1e-6]


def _arp(harm, unit: float, order: Sequence[int], vel: float, ring: float = 1.0, accent: float = 1.15,
         base: Tuple[str, str] = ("G2", "F#3")) -> List[Ev]:
    """A broken chord, one note per ``unit`` through ``order`` (chord-tone indexes for
    ``_deg``) restarting at each chord; every string rings on until the chord changes."""
    out = []
    for s, L, ch in harm:
        t, k = s, 0
        while t < s + L - 1e-6:
            m = _deg(ch, order[k % len(order)], *base)
            v = vel * (accent if k == 0 else 1.0)
            out.append((t, max(unit, (s + L - t) * ring), m, min(1.0, v)))
            t += unit
            k += 1
    return out


def _roll(t: float, pitches: Sequence[int], L: float, v: float, spread: float) -> List[Ev]:
    """A rolled chord, from the lowest string up."""
    return [(t + i * spread, L - i * spread, p, v * (1.0 - 0.04 * i)) for i, p in enumerate(sorted(pitches))]


def _gliss(t: float, length: float, lo: str, hi: str, pcs: Sequence[int], v0: float, v1: float,
           ring: float = 1.5) -> List[Ev]:
    """A harp glissando up through the strings tuned to ``pcs`` over ``length`` beats."""
    keys = [m for m in range(_m(lo), _m(hi) + 1) if m % 12 in pcs]
    n = len(keys)
    return [(t + length * i / n, ring, m, v0 + (v1 - v0) * i / max(1, n - 1)) for i, m in enumerate(keys)]


def _drum_bars(pattern: Sequence[Tuple[float, str, float]], bars: Sequence[int], bar: float) -> List[Ev]:
    """A drum pattern [(beat in the bar, stroke, velocity)] in the given (0-based) bars."""
    return [(b * bar + pos, 0.25, stroke, v) for b in bars for pos, stroke, v in pattern]


def _roll_drum(t: float, length: float, pitch, v0: float, v1: float, rate: float = 7.0) -> List[Ev]:
    """A timpani roll: single strokes ``rate`` per beat, swelling from ``v0`` to ``v1``."""
    n = max(2, int(round(length * rate)))
    return [(t + length * i / n, 0.3, pitch, v0 + (v1 - v0) * i / (n - 1)) for i in range(n)]


# ============================================================================= rendering
# the frame drum: the deep stroke ("doum": a melodic tom's body under a conga's skin) and
# the rim tap ("tek": a muted conga); a stroke is a list of (program, pitch, gain)
FRAME = {"doum": [(TOM, "A2", 0.8), (DRUM, "low_conga", 0.55)],
         "tek": [(DRUM, "mute_conga", 0.8)]}


def _no_retrigger(evs: Sequence[Ev], gap: float = 0.05) -> List[Ev]:
    """End each note ``gap`` beats before the same pitch is struck again. Notes of one
    instrument share a MIDI channel, and a note-off silences every sounding note of its
    pitch there: a long-ringing dulcimer fifth would otherwise choke the same fifth struck
    again under it, and an organ chord's note-off would drop the common tone of the next
    chord if that one was played a few milliseconds early."""
    order = sorted(range(len(evs)), key=lambda i: evs[i][0])
    out = list(evs)
    nxt: Dict[int, float] = {}
    for i in reversed(order):
        s, L, m, v = evs[i]
        if m in nxt and nxt[m] > s + 1e-6:
            L = max(0.05, min(L, nxt[m] - s - gap))
        out[i] = (s, L, m, v)
        nxt[m] = s
    return out


def _notes(program: int, evs: Sequence[Ev], unit: float, loop_s: float, seed: int, jitter: float = 0.008,
           legato: float = 0.95, swell_from: Optional[float] = None, swell=(92, 120), pan: float = 0.0,
           vel: float = 1.0, warp: Optional[Callable[[float], float]] = None,
           strokes: Optional[Dict[str, list]] = None) -> List[Note]:
    """Events (in beats) to bank notes: seconds, a human nudge in time and velocity
    (seeded), ``legato`` of each length held, a swell on notes at least ``swell_from``
    beats long, played ``EARLY`` so they speak on the beat. ``warp`` (beats -> seconds)
    bends the time of every part alike (a breath at the end of a phrase). A note nudged
    before the loop's start wraps round to its end. For ``strokes`` (drums) the pitch
    slot names a stroke."""
    rng = np.random.default_rng(seed)
    out: List[Note] = []
    early = EARLY.get(program, 0.0)
    if strokes is None:
        evs = _no_retrigger(evs)
    for s, L, m, v in evs:
        t = s * unit - early + rng.uniform(-jitter, jitter)
        dur = max(0.05, L * unit * legato)
        if warp is not None:
            t += warp(s)
            dur = max(0.05, dur + warp(s + L) - warp(s))
        if t < 0:
            t += loop_s
        v127 = 127 * v * vel * rng.uniform(0.95, 1.04)
        if strokes is not None:
            for prog, key, g in strokes[m]:
                out.append(Note(prog, key, t + rng.uniform(0, 0.003), 0.3, vel=int(np.clip(v127 * g, 1, 127)),
                                pan=pan))
            continue
        sw = None
        if swell_from is not None and L >= swell_from - 1e-6:
            sw = tuple(int(np.clip(e + rng.integers(-4, 5), 0, 127)) for e in swell)
        out.append(Note(program, int(m), t, dur, vel=int(np.clip(round(v127), 1, 127)), pan=pan, swell=sw))
    return out


@functools.lru_cache(maxsize=None)
def _bank_cached(key: tuple, seconds: float, bank: str) -> np.ndarray:
    return sf.render([Note(*k) for k in key], seconds, bank=bank, stereo=True)


def _render(notes: Sequence[Note], seconds: float, bank: str) -> np.ndarray:
    key = tuple(dataclasses.astuple(n) for n in notes)
    return _bank_cached(key, round(float(seconds), 4), bank).copy()


def _render_split(notes: Sequence[Note], seconds: float, bank: str) -> np.ndarray:
    """Render a part in as few bank renders as its channels allow: the plain notes
    together, the drum kit's own, and the swelling notes (a channel each while they
    sound) in groups of at most ten at a time."""
    plain = [n for n in notes if n.program != DRUM and n.swell is None and n.bend is None]
    drums = [n for n in notes if n.program == DRUM]
    solo = sorted([n for n in notes if n.program != DRUM and not (n.swell is None and n.bend is None)],
                  key=lambda n: n.start)
    groups: List[List[Note]] = []
    lanes: List[Tuple[List[Note], List[float]]] = []         # (notes, end times)
    for n in solo:
        for g, ends in lanes:
            live = [e for e in ends if e > n.start]
            if len(live) < 10:
                g.append(n)
                ends[:] = live + [n.start + n.dur + 1.6]
                break
        else:
            lanes.append(([n], [n.start + n.dur + 1.6]))
    groups = [g for g, _ in lanes]
    if groups:
        groups[0] = plain + drums + groups[0]
    else:
        groups = [plain + drums]
    out = None
    for g in groups:
        if g:
            x = _render(g, seconds, bank)
            out = x if out is None else out + x
    return out if out is not None else np.zeros((A.n_of(seconds), 2))


def _fit(x: np.ndarray, n: int) -> np.ndarray:
    return x[:n] if len(x) >= n else np.concatenate([x, np.zeros((n - len(x),) + x.shape[1:])])


def _at(x: np.ndarray, db: float) -> np.ndarray:
    """``x`` at a gated loudness of ``db`` while it plays."""
    return x * 10 ** ((db - A._rms_db(x)) / 20.0)


def _place(x: np.ndarray, pan: float) -> np.ndarray:
    """Put a rendered part where it belongs on the stage. The banks' stereo samples carry
    their own placement (the horn sits right of centre whatever its pan), so the part's
    left and right are rebalanced to the energy an equal-power pan to ``pan`` would give,
    its stereo image otherwise untouched and its total energy kept."""
    el, er = float(np.sum(x[:, 0] ** 2)), float(np.sum(x[:, 1] ** 2))
    if el <= 0 or er <= 0:
        return x
    a = (max(-0.95, min(0.95, pan)) + 1) * math.pi / 4
    want = (math.cos(a) / math.sin(a)) ** 2                 # left/right energy
    g = (want / (el / er)) ** 0.25
    y = x * np.array([g, 1.0 / g])
    return y * math.sqrt((el + er) / float(np.sum(y ** 2)))


def _bow_attack(x: np.ndarray, onsets: Sequence[float], boost_db: float, tau: float) -> np.ndarray:
    """A firmer bow stroke for quick notes: the banks' bowed samples speak slowly, which
    blurs a driving rhythm, so the first moments of each note (we know when each starts)
    are lifted by up to ``boost_db``, the lift dying away over ``tau`` seconds."""
    n = len(x)
    a = 10 ** (boost_db / 20.0) - 1.0
    g = np.zeros(n)
    k = A.n_of(tau * 5)
    shape = a * np.exp(-np.arange(k) / (tau * SR))
    ramp = A.n_of(0.006)
    shape[:ramp] *= np.linspace(0.0, 1.0, ramp)
    for t in onsets:
        i = A.n_of(t + 0.004)
        if i >= n:
            continue
        j = min(n, i + k)
        g[i:j] = np.maximum(g[i:j], shape[:j - i])
    return x * (1.0 + g)[:, None]


# ----------------------------------------------------------------------------- tone
def _tone_harp(x):
    """The harp: no thump below its lowest strings, its top softened a touch."""
    return A.lowpass(A.highpass(x, 70, 2), 9000, 2)


def _tone_harp_even(x):
    """The ballad's harp, where it carries both the call and its own broken chords: as
    ``_tone_harp``, and a gentle compressor (3:1 from 4 dB above its loudness, the pluck
    itself let through) so the call's long, firmly plucked notes do not jump out of a
    calm menu by 8 or 9 dB."""
    y = _tone_harp(x)
    return A.compress(y, threshold_db=A._rms_db(y) + 4.0, ratio=3.0, attack_ms=4.0, release_ms=160.0)


def _tone_strings(x):
    """The section: no rumble, the bow's rasp near 3 kHz eased for long listening."""
    y = A.highpass(x, 110, 2)
    y = A.peak_eq(y, 300, -1.5, 0.9)
    y = A.peak_eq(y, 3000, -2.0, 1.0)
    return A.lowpass(y, 8000, 2)


def _tone_violins(x):
    y = A.highpass(x, 180, 2)
    y = A.peak_eq(y, 3200, -2.5, 1.0)
    return A.lowpass(y, 8500, 2)


def _tone_cello(x):
    """The solo cello: its body kept, the boom under 80 Hz and the hiss above 7 kHz cut,
    a little less of the woolly 250 Hz."""
    y = A.highpass(x, 75, 2)
    y = A.peak_eq(y, 250, -2.0, 1.0)
    return A.lowpass(y, 7000, 2)


def _tone_drive(x):
    """The driving cellos: their bite kept, the low body (an octave above the basses
    already) thinned so the drive never thickens into a rumble."""
    y = A.highpass(x, 95, 2)
    y = A.peak_eq(y, 220, -2.5, 1.0)
    return A.lowpass(y, 7000, 2)


def _tone_bass(x):
    """The contrabass: nothing below 45 Hz, no bow hiss, its 120 Hz bloom trimmed."""
    y = A.highpass(x, 45, 2)
    y = A.peak_eq(y, 120, -2.0, 0.9)
    return A.lowpass(y, 4000, 2)


def _tone_choir(x):
    y = A.highpass(x, 120, 2)
    y = A.peak_eq(y, 2800, -1.5, 1.0)
    return A.lowpass(y, 7500, 2)


def _tone_horn(x):
    y = A.highpass(x, 90, 2)
    return A.lowpass(y, 6500, 2)


def _tone_low_brass(x):
    y = A.highpass(x, 50, 2)
    y = A.peak_eq(y, 1800, -1.5, 1.0)
    return A.lowpass(y, 5500, 2)


def _tone_tuba(x):
    y = A.highpass(x, 45, 2)
    return A.lowpass(y, 2500, 2)


def _tone_dulcimer(x):
    """The dulcimer's ring kept, its metallic edge near 3 kHz and above 8 kHz softened."""
    y = A.highpass(x, 160, 2)
    y = A.peak_eq(y, 3000, -2.5, 1.0)
    return A.lowpass(y, 8000, 2)


def _tone_frame(x):
    """A frame drum, not a kit: less boom, no click above 5 kHz."""
    y = A.highpass(x, 60, 2)
    y = A.peak_eq(y, 95, -3.0, 0.9)
    return A.lowpass(y, 5000, 2)


def _tone_taiko(x):
    """The taiko (played high in the bank, near 86 Hz): what is left of its sub-bass
    rumble cut, the skin's knock kept."""
    y = A.highpass(x, 62, 2)
    return A.lowpass(y, 4500, 2)


def _tone_timpani(x):
    y = A.highpass(x, 55, 2)
    return A.lowpass(y, 6000, 2)


def _tone_organ(x):
    y = A.highpass(x, 120, 2)
    return A.lowpass(y, 5000, 2)


def _tone_pizz(x):
    y = A.highpass(x, 70, 2)
    return A.lowpass(y, 6000, 2)


# ----------------------------------------------------------------------------- the mix
@dataclasses.dataclass
class Part:
    name: str
    notes: List[Note]
    level: float                              # loudness (dB) while it plays, before mastering
    bank: str = "fluid"
    tone: Optional[Callable[[np.ndarray], np.ndarray]] = None
    attack: Optional[Tuple[float, float]] = None   # a firmer bow (_bow_attack): (boost dB, seconds)
    send: float = 1.0                          # how much of it goes to the hall
    pan: Optional[float] = None                # where it sits (default: its notes' pan)


def _hall(x: np.ndarray, room: float, damping: float, width: float = 1.0, predelay: float = 0.025,
          low_cut: float = 140.0, high_cut: float = 6500.0) -> np.ndarray:
    """The stone hall's reverberation alone (no dry sound), fed only from above
    ``low_cut``: the low notes stay clear and the room never booms; centred. Three seconds
    longer than ``x`` so it can ring out."""
    from pedalboard import Pedalboard, Reverb
    pad = np.zeros((A.n_of(3.0 + predelay), 2))
    s = A.lowpass(A.highpass(x, low_cut, 2), high_cut, 2)
    s = np.concatenate([np.zeros((A.n_of(predelay), 2)), s, pad])[:len(x) + len(pad)]
    board = Pedalboard([Reverb(room_size=room, damping=damping, wet_level=1.0, dry_level=0.0, width=width)])
    y = board(s.T.astype(np.float32), SR).T.astype(np.float64)
    return _place(y, 0.0)          # Freeverb's large rooms lean right by a decibel or so


def _mixdown(parts: Sequence[Part], loop_s: float, room: float, wet: float, damping: float = 0.5) -> np.ndarray:
    """Render each part past the loop's end, shape and balance it, put the orchestra in
    one hall, fold everything that rings past the end back onto the start, and start the
    file at a quiet point just before the downbeat."""
    seconds = loop_s + TAIL
    n = A.n_of(seconds)
    dry = np.zeros((n, 2))
    send = np.zeros((n, 2))
    for p in parts:
        x = _fit(_render_split(p.notes, seconds, p.bank), n)
        if p.attack:
            x = _bow_attack(x, sorted({round(nt.start, 4) for nt in p.notes}), *p.attack)
        if p.tone:
            x = p.tone(x)
        pan = p.pan if p.pan is not None else (p.notes[0].pan if p.notes else 0.0)
        x = _at(_place(x, pan), p.level)
        dry += x
        send += x * p.send
    rev = _hall(send, room, damping)
    full = np.concatenate([dry, np.zeros((len(rev) - n, 2))]) + wet * rev
    full = A.highpass(full, 32, 2)
    loop = A.loop_seamless(full[:A.n_of(loop_s)], full[A.n_of(loop_s):])
    return music.aac_friendly_start(loop)


def _breath(phrase: float, total: float, before: float, after: float, amount: float) -> Callable[[float], float]:
    """A time warp for a ballad: approaching the end of each ``phrase`` (beats) the
    players hold back, up to ``amount`` seconds late at the boundary, and settle back into
    time over ``after`` beats; it wraps round the loop, so the loop's length is unchanged."""
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


# ============================================================================= the saga call
# The theme in its four modes, two four-bar phrases: the call (D up to A) and its answer.
CALL_DORIAN = ("D5:1 A5:3 | G5:1.5 F5:0.5 E5:1 C5:1 | F5:1.5 G5:0.5 A5:1 F5:1 | E5:4 | "
               "D5:1 A5:3 | C6:1.5 B5:0.5 A5:1 G5:1 | F5:1 D5:1 E5:1 C5:1 | D5:4")
CALL_MIXO = ("D4:0.5 D4:0.5 A4:3 | G4:1.5 F#4:0.5 E4:1 C4:1 | B4:1.5 A4:0.5 G4:1 B4:1 | A4:3 r:1 | "
             "D4:0.5 D4:0.5 A4:3 | C5:1.5 B4:0.5 A4:1 G4:1 | G4:1 D4:1 E4:1 C4:1 | D4:3 r:1")
CALL_LAMENT = ("D4:1 A4:2 | Bb4:2 A4:1 | G4:2 F4:1 | E4:3 | "
               "D4:1 A4:2 | D5:1.5 C5:0.5 Bb4:1 | Bb4:1 G4:1 E4:1 | D4:3")
CALL_LAMENT_OPEN = ("D4:1 A4:2 | Bb4:2 A4:1 | G4:2 F4:1 | E4:3 | "
                    "D4:1 A4:2 | D5:1.5 C5:0.5 Bb4:1 | Bb4:1 G4:1 F4:1 | E4:3")
CALL_MARCH = ("D4:1 A4:3 | G4:1.5 F4:0.5 E4:1 C4:1 | F4:1.5 G4:0.5 A4:1 F4:1 | E4:4 | "
              "D4:1 A4:3 | C5:1.5 Bb4:0.5 A4:1 G4:1 | F4:1 D4:1 E4:1 C4:1 | D4:4")
CALL_MARCH_TURN = ("D4:1 A4:3 | G4:1.5 F4:0.5 E4:1 C4:1 | F4:1.5 G4:0.5 A4:1 F4:1 | E4:4 | "
                   "D4:1 A4:3 | C5:1.5 Bb4:0.5 A4:1 G4:1 | F4:1 D4:1 E4:1 C4:1 | D4:2 C#4:2")


def _unit(bpm: float, beats: int) -> Tuple[float, float]:
    u = music.aac_unit(60.0 / bpm, beats)
    return u, u * beats


# ============================================================================= menu: Misty Keep
MENU_BPM, MENU_BEATS = 70.0, 24 * 4
MENU_H_A = "Dm | C | F | Am | Dm | C:2 G:2 | Dm:2 C:2 | Dm"
MENU_H_B = "F | C | G | Dm | F | C | G | Asus4:2 A:2"
MENU_H_A2 = "Dm | C | F | Am | Dm | C:2 G:2 | Dm:2 C:2 | Dm:2 C:2"
MENU_CELLO_B = ("C4:1 F4:3 | E4:1.5 D4:0.5 C4:1 G3:1 | B3:1.5 C4:0.5 D4:1 B3:1 | A3:4 | "
                "C4:1 F4:2 A4:1 | G4:1.5 F4:0.5 E4:1 C4:1 | D4:1.5 E4:0.5 D4:1 B3:1 | D4:2 C#4:2")
MENU_CELLO_A2 = "F3:2 A3:2 | G3:2 E3:2 | A3:2 C4:2 | E3:2 C3:2 | D3:2 F3:2 | E3:2 D3:2 | A3:2 G3:2 | F3:2 E3:2"
MENU_HARP_ECHO = "r:4 | r:4 | r:4 | r:2 D5:0.5 E5:0.5 F5:1 | r:4 | r:4 | r:4 | r:2 E5:0.5 C#5:0.5 A4:1"


def _misty_keep() -> np.ndarray:
    pan = dict(PAN, harp=0.05, violins=-0.16, cello=-0.12, bass=0.14)
    bar = 4.0
    u, L = _unit(MENU_BPM, MENU_BEATS)
    harm = _harm(MENU_H_A, bar) + _harm(MENU_H_B, bar, 32) + _harm(MENU_H_A2, bar, 64)
    # the harp: the call (bars 1-8), its own broken chords in A and A', rolled chords and
    # two little echoes of the cello in B, a pickup back into the call at the very end
    harp = _tune(CALL_DORIAN, bar, 0.6)
    harp += _arp(_within(harm, 0, 32), 0.5, (0, 2, 3, 4, 5, 4, 3, 2), 0.36)
    harp += _arp(_within(harm, 64, 96), 0.5, (0, 2, 3, 4, 5, 4, 3, 2), 0.26)
    for s, Lc, ch in _within(harm, 32, 64):
        for k in range(int(round(Lc / 2))):
            harp += _roll(s + 2 * k, [_deg(ch, 0), _deg(ch, 2), _deg(ch, 3), _deg(ch, 4)], 2.2, 0.31, 0.07)
    harp += _tune(MENU_HARP_ECHO, bar, 0.36, offset=32)
    harp += _tune("E5:0.5 D5:0.5 C5:1", 2, 0.44, offset=94)
    # the strings: soft chords throughout (above the cello in B), the violins sing the
    # call in A'
    pad = _pad(_voicings(_within(harm, 0, 32), 3, "A3", "A4", "D4"), 0.36)
    pad += _pad(_voicings(_within(harm, 32, 64), 3, "E4", "E5", "A4"), 0.3)
    pad += _pad(_voicings(_within(harm, 64, 96), 3, "A3", "A4", "D4"), 0.33)
    violins = _tune(CALL_DORIAN.replace("| D5:4", "| D5:2 r:2"), bar, 0.5, offset=64)
    cello = _tune(MENU_CELLO_B, bar, 0.62, offset=32) + _tune(MENU_CELLO_A2, bar, 0.4, offset=64)
    bass = [(s, Lc, _bass(ch, "C2", "B2"), 0.42) for s, Lc, ch in harm]
    breath = _breath(16.0, MENU_BEATS, 3.0, 1.5, 0.07)
    parts = [
        Part("harp", _notes(HARP, harp, u, L, 101, jitter=0.006, legato=1.0, warp=breath, pan=pan["harp"]),
             -21.5, "fluid", _tone_harp_even),
        Part("strings", _notes(STRINGS, pad, u, L, 102, legato=1.0, swell_from=1.5, swell=(78, 104), warp=breath,
                               pan=pan["strings"]), -27.5, "fluid", _tone_strings),
        Part("violins", _notes(STRINGS, violins, u, L, 103, legato=0.98, swell_from=1.5, swell=(92, 118),
                               warp=breath, pan=pan["violins"]), -19.5, "fluid", _tone_violins),
        Part("cello", _notes(CELLO, cello, u, L, 104, legato=0.97, swell_from=1.0, swell=(90, 118), warp=breath,
                             pan=pan["cello"]), -21.5, "musescore", _tone_cello),
        Part("bass", _notes(BASS, bass, u, L, 105, legato=1.0, swell_from=1.5, swell=(80, 100), warp=breath,
                            pan=pan["bass"]), -29.0, "fluid", _tone_bass, send=0.5),
    ]
    return _mixdown(parts, L, room=0.82, wet=0.3, damping=0.45)


# ============================================================================= jack: The Long Road
JACK_BPM, JACK_BEATS = 96.0, 32 * 4
JACK_H_A = "D | G:2 C:2 | G | A | D | C:2 Am:2 | G:2 C:2 | D"
JACK_H_B = "Bm | G | D | A | Bm | G | C | Asus4:2 A:2"
JACK_HORN_COUNTER = "F#4:4 | G4:2 E4:2 | D4:4 | C#4:2 E4:2 | F#4:4 | E4:2 C4:2 | D4:2 E4:2 | F#4:3 r:1"
JACK_CELLO_B = ("B3:1 F#4:3 | G4:1.5 F#4:0.5 D4:1 B3:1 | A3:1.5 B3:0.5 D4:1 F#4:1 | E4:4 | "
                "B3:1 F#4:3 | B4:1.5 A4:0.5 G4:1 D4:1 | E4:1.5 D4:0.5 C4:1 E4:1 | D4:2 C#4:2")
JACK_DRUM_A = [(0, "doum", 0.72), (1, "tek", 0.42), (1.5, "tek", 0.3), (2, "doum", 0.6), (3, "tek", 0.45),
               (3.5, "tek", 0.32)]
JACK_DRUM_B = [(0, "doum", 0.6), (2, "tek", 0.36), (3, "tek", 0.28)]


def _long_road() -> np.ndarray:
    pan = dict(PAN, horn=-0.25, violins=-0.2, cello=0.2, dulcimer=0.3, harp=0.3, pizz=0.1, bass=0.16, timpani=-0.1)
    bar = 4.0
    u, L = _unit(JACK_BPM, JACK_BEATS)
    harm = (_harm(JACK_H_A, bar) + _harm(JACK_H_A, bar, 32) + _harm(JACK_H_B, bar, 64)
            + _harm(JACK_H_A, bar, 96))
    a_sections = _within(harm, 0, 64) + _within(harm, 96, 128)
    # the tune: the horn calls (A), the violins take it an octave up with the horn's
    # counter-line below (A'), the cello in B, horn and violins together (A'')
    horn = (_tune(CALL_MIXO, bar, 0.66) + _tune(JACK_HORN_COUNTER, bar, 0.46, offset=32)
            + _tune(CALL_MIXO, bar, 0.68, offset=96))
    violins = _tune(CALL_MIXO, bar, 0.56, offset=32, shift=12) + _tune(CALL_MIXO, bar, 0.52, offset=96, shift=12)
    cello = _tune(JACK_CELLO_B, bar, 0.64, offset=64)
    # the travelling ostinato: dulcimer quavers through each chord (not in B)
    dulc = _arp(a_sections, 0.5, (0, 2, 3, 2, 4, 2, 3, 2), 0.34, ring=0.6, accent=1.25, base=("G3", "F#4"))
    # the harp: broken chords in B, a glissando up into A''
    harp = _arp(_within(harm, 64, 96), 0.5, (0, 2, 3, 4, 5, 4, 3, 2), 0.36)
    harp += _gliss(95.0, 1.0, "A3", "A5", [9, 1, 4, 7], 0.25, 0.55)
    # the strings: soft chords throughout, a little fuller in B
    pad = _pad(_voicings(_within(harm, 0, 64), 3, "A3", "A4", "D4"), 0.32)
    pad += _pad(_voicings(_within(harm, 64, 96), 3, "D4", "D5", "F#4"), 0.36)
    pad += _pad(_voicings(_within(harm, 96, 128), 3, "A3", "A4", "D4"), 0.34)
    # the bass: pizzicato root and fifth in the A sections, bowed roots in B
    pizz = []
    for s, Lc, ch in a_sections:
        root = _bass(ch, "D2", "C#3")
        pizz.append((s, 1.0, root, 0.62))
        if Lc >= 4:
            fifth = root + 7 if root < _m("G2") else root - 5
            pizz.append((s + 2, 1.0, fifth, 0.5))
    bass = [(s, Lc, _bass(ch, "D2", "C#3"), 0.46) for s, Lc, ch in _within(harm, 64, 128)]
    # a soft "ooh" choir under the last A
    oohs = _pad(_voicings(_within(harm, 96, 128), 3, "D4", "D5", "F#4"), 0.34)
    # percussion
    frame = (_drum_bars(JACK_DRUM_A, range(0, 16), bar) + _drum_bars(JACK_DRUM_B, range(16, 24), bar)
             + _drum_bars(JACK_DRUM_A, range(24, 32), bar))
    taiko = [(b * bar, 1.0, _m("D4"), 0.55) for b in (16, 20)] + [(b * bar, 1.0, _m("D4"), 0.62) for b in (24, 28)]
    timp = [(0.0, 1.0, _m("D2"), 0.5), (32.0, 1.0, _m("D2"), 0.55), (12.0, 1.0, _m("A2"), 0.42),
            (44.0, 1.0, _m("A2"), 0.42), (112.0, 1.0, _m("A2"), 0.45), (96.0, 1.0, _m("D2"), 0.6)]
    timp += _roll_drum(93.0, 3.0, _m("A2"), 0.18, 0.5) + _roll_drum(126.0, 2.0, _m("A2"), 0.15, 0.36)
    parts = [
        Part("horn", _notes(HORN, horn, u, L, 201, legato=0.93, swell_from=2.0, swell=(96, 122), pan=pan["horn"]),
             -20.5, "fluid", _tone_horn),
        Part("violins", _notes(STRINGS, violins, u, L, 202, legato=0.95, swell_from=2.0, swell=(94, 120),
                               pan=pan["violins"]), -21.5, "fluid", _tone_violins),
        Part("cello", _notes(CELLO, cello, u, L, 203, legato=0.96, swell_from=1.0, swell=(92, 120),
                             pan=pan["cello"]), -20.5, "musescore", _tone_cello),
        Part("dulcimer", _notes(DULCIMER, dulc, u, L, 204, jitter=0.006, legato=1.0, pan=pan["dulcimer"]),
             -27.0, "fluid", _tone_dulcimer),
        Part("harp", _notes(HARP, harp, u, L, 205, jitter=0.006, legato=1.0, pan=pan["harp"]),
             -25.0, "fluid", _tone_harp),
        Part("strings", _notes(STRINGS, pad, u, L, 206, legato=1.0, swell_from=1.5, swell=(80, 106),
                               pan=pan["strings"]), -28.0, "fluid", _tone_strings),
        Part("pizz", _notes(PIZZ, pizz, u, L, 207, jitter=0.006, legato=1.0, pan=pan["pizz"]),
             -28.5, "fluid", _tone_pizz, send=0.6),
        Part("bass", _notes(BASS, bass, u, L, 208, legato=1.0, swell_from=1.5, swell=(84, 104), pan=pan["bass"]),
             -29.5, "fluid", _tone_bass, send=0.5),
        Part("oohs", _notes(OOHS, oohs, u, L, 209, legato=1.0, swell_from=1.5, swell=(84, 108), pan=pan["choir"]),
             -29.0, "fluid", _tone_choir),
        Part("frame", _notes(DRUM, frame, u, L, 210, jitter=0.005, strokes=FRAME, pan=pan["drum"]),
             -27.0, "fluid", _tone_frame, send=0.6),
        Part("taiko", _notes(TAIKO, taiko, u, L, 211, jitter=0.004, legato=1.0, pan=pan["taiko"]),
             -29.0, "fluid", _tone_taiko, send=0.7),
        Part("timpani", _notes(TIMPANI, timp, u, L, 212, jitter=0.004, legato=1.0, pan=pan["timpani"]),
             -28.0, "fluid", _tone_timpani, send=0.8),
    ]
    return _mixdown(parts, L, room=0.75, wet=0.24, damping=0.5)


# ============================================================================= queen: Veiled Queen
QUEEN_BPM, QUEEN_BEATS = 72.0, 32 * 3
QUEEN_H_A = "Dm | Bb | Gm | A | Dm | Bb | Gm:2 A:1 | Dm"
QUEEN_H_B = "Bb | Bb | Gm | Gm | Eb | Eb | A | A"
QUEEN_H_A3 = "Dm | Bb | Gm | A | Dm | Bb | Gm | A"
QUEEN_CELLO_COUNTER = "A3:3 | F3:3 | Bb2:2 D3:1 | C#3:3 | A3:3 | F3:3 | Bb2:2 A2:1 | F3:3"
QUEEN_B = ("F4:1 Bb4:2 | D5:1.5 C5:0.5 Bb4:1 | Bb4:1 G4:2 | D4:1.5 F4:0.5 G4:1 | "
           "G4:1 Bb4:2 | Eb5:2 D5:1 | C#5:1.5 Bb4:0.5 A4:1 | A4:2 E4:1")
QUEEN_VOICE_A3 = "F4:3 | F4:3 | D4:3 | C#4:3 | F4:3 | F4:3 | D4:3 | C#4:3"
# the harp's ostinato leans on the note above each chord's fifth: a semitone for the minor
# chords and A major, the phrygian E-flat under G minor
QUEEN_NEIGHBOUR = {"Dm": "Bb", "Bb": "G", "Gm": "Eb", "A": "F", "Eb": "C"}
QUEEN_HEART = [(0, "doum", 0.55), (0.5, "doum", 0.32)]


def _queen_ostinato(harm, vel: float) -> List[Ev]:
    """Quavers through each chord: root, fifth, the note above the fifth, fifth, the root
    an octave up, fifth. The fifth before the neighbour and the neighbour itself are
    played lightly: a harp string rings on (the banks' harp ignores a damped note-off), and
    by the time the neighbour sounds the fifth has fallen about 10 dB, so the semitone
    only shimmers instead of clashing."""
    out = []
    for s, Lc, ch in harm:
        r = _deg(ch, 0)
        fifth = _deg(ch, 2)
        pc = _pc(QUEEN_NEIGHBOUR[ch])[0]
        nb = next(m for m in range(fifth + 1, fifth + 4) if m % 12 == pc)
        fig = [r, fifth, nb, fifth, r + 12, fifth]
        lean = [1.2, 0.8, 0.86, 0.9, 1.0, 0.86]
        for k in range(int(round(Lc * 2))):
            out.append((s + 0.5 * k, 1.2, fig[k % 6], vel * lean[k % 6]))
    return out


def _veiled_queen() -> np.ndarray:
    pan = dict(PAN, cello=0.16, voice=-0.1, harp=-0.24, tremolo=-0.05, bass=0.14, timpani=-0.1)
    bar = 3.0
    u, L = _unit(QUEEN_BPM, QUEEN_BEATS)
    harm = (_harm(QUEEN_H_A, bar) + _harm(QUEEN_H_A, bar, 24) + _harm(QUEEN_H_B, bar, 48)
            + _harm(QUEEN_H_A3, bar, 72))
    # the solo line: the cello (A), the voice with the cello's counter-line below (A'),
    # voice and cello an octave apart (B), the cello low and dark under a held voice (A'')
    cello = (_tune(CALL_LAMENT, bar, 0.62) + _tune(QUEEN_CELLO_COUNTER, bar, 0.42, offset=24)
             + _tune(QUEEN_B, bar, 0.56, offset=48, shift=-12) + _tune(CALL_LAMENT_OPEN, bar, 0.65, offset=72, shift=-12))
    voice = (_tune(CALL_LAMENT, bar, 0.62, offset=24) + _tune(QUEEN_B, bar, 0.62, offset=48)
             + _tune(QUEEN_VOICE_A3, bar, 0.47, offset=72))
    harp = (_queen_ostinato(_within(harm, 0, 48), 0.36) + _queen_ostinato(_within(harm, 48, 72), 0.4)
            + _queen_ostinato(_within(harm, 72, 96), 0.34))
    # the low choir: men's voices, rising an octave and swelling in B
    choir = (_pad(_voicings(_within(harm, 0, 48), 3, "D3", "D4", "A3"), 0.36)
             + _pad(_voicings(_within(harm, 48, 72), 3, "G3", "G4", "D4"), 0.4)
             + _pad(_voicings(_within(harm, 72, 96), 3, "D3", "D4", "A3"), 0.34))
    # tremolo strings: a low murmur in A, chords in A', swelling in B, soft in A''
    trem = (_pad(_voicings(_within(harm, 0, 24), 2, "D3", "D4", "F3"), 0.3)
            + _pad(_voicings(_within(harm, 24, 48), 3, "D3", "D4", "A3"), 0.34)
            + _pad(_voicings(_within(harm, 48, 72), 4, "D3", "F4", "A3"), 0.46)
            + _pad(_voicings(_within(harm, 72, 96), 3, "D3", "D4", "A3"), 0.32))
    bass = [(s, Lc, _bass(ch, "C2", "B2"), 0.44) for s, Lc, ch in _within(harm, 24, 96)]
    heart = (_drum_bars(QUEEN_HEART, range(8, 24), bar)
             + _drum_bars([(0, "doum", 0.4)], range(24, 32), bar))
    timp = [(24.0, 1.0, _m("D2"), 0.42), (48.0, 1.0, _m("D2"), 0.4), (72.0, 1.0, _m("D2"), 0.5)]
    timp += _roll_drum(54.0, 6.0, _m("D2"), 0.12, 0.32, rate=6.0)
    timp += _roll_drum(66.0, 6.0, _m("A2"), 0.14, 0.48, rate=6.0)
    parts = [
        Part("cello", _notes(CELLO, cello, u, L, 301, legato=0.97, swell_from=1.0, swell=(88, 118), pan=pan["cello"]),
             -21.0, "musescore", _tone_cello),
        Part("voice", _notes(OOHS, voice, u, L, 302, legato=0.97, swell_from=1.0, swell=(86, 116), pan=pan["voice"]),
             -20.5, "fluid", _tone_choir),
        Part("harp", _notes(HARP, harp, u, L, 303, jitter=0.006, legato=1.0, pan=pan["harp"]),
             -24.0, "fluid", _tone_harp),
        Part("choir", _notes(CHOIR, choir, u, L, 304, legato=1.0, swell_from=1.5, swell=(76, 104),
                             pan=pan["choir"]), -27.5, "fluid", _tone_choir),
        Part("tremolo", _notes(TREMOLO, trem, u, L, 305, legato=1.0, swell_from=1.5, swell=(70, 108),
                               pan=pan["tremolo"]), -27.0, "musescore", _tone_strings),
        Part("bass", _notes(BASS, bass, u, L, 306, legato=1.0, swell_from=1.5, swell=(80, 102), pan=pan["bass"]),
             -29.5, "fluid", _tone_bass, send=0.5),
        Part("heart", _notes(DRUM, heart, u, L, 307, jitter=0.004, strokes=FRAME, pan=pan["drum"]),
             -29.0, "fluid", _tone_frame, send=0.6),
        Part("timpani", _notes(TIMPANI, timp, u, L, 308, jitter=0.004, legato=1.0, pan=pan["timpani"]),
             -29.0, "fluid", _tone_timpani, send=0.8),
    ]
    return _mixdown(parts, L, room=0.8, wet=0.3, damping=0.5)


# ============================================================================= king: Siege of Kings
KING_BPM, KING_BEATS = 104.0, 32 * 4
KING_H_A = "Dm | C | F | A | Dm | F | Bb:2 C:2 | Dm"
KING_H_B = "Bb | F | C | Dm | Bb | F | Gm | A"
KING_H_A3 = "Dm | C | F | A | Dm | F | Bb:2 C:2 | Dm:2 A:2"
KING_CHOIR_B = "D4:4 | A4:4 | G4:2 E4:2 | F4:2 D4:2 | F4:4 | C5:4 | Bb4:2 D5:2 | C#5:4"
KING_FANFARE = "A3:1 C#4:1 E4:1 A4:1"
ACCENTS = (0.0, 1.5, 3.0)                      # 3+3+2 quavers


def _drive(harm, vel: float, accents_only: bool = False) -> Tuple[List[Ev], List[Ev]]:
    """The low strings' drive: the cellos in quavers on each chord's root, leaning on
    3+3+2, the basses on the leaning notes only."""
    cel, bas = [], []
    for s, Lc, ch in harm:
        root = _bass(ch, "C3", "B3")
        t = s
        while t < s + Lc - 1e-6:
            pos = (t % 4.0)
            acc = any(abs(pos - a) < 1e-6 for a in ACCENTS)
            if acc or not accents_only:
                cel.append((t, 0.5 if not accents_only else 1.0, root, vel * (1.0 if acc else 0.62)))
            if acc:
                bas.append((t, 1.0 if pos < 3 else 0.9, root - 12, vel * 0.95))
            t += 0.5
    return cel, bas


def _timp_pitch(ch: str) -> int:
    r = _chord(ch)[0]
    return {2: _m("D2"), 9: _m("A2"), 5: _m("F2"), 0: _m("C3"), 10: _m("Bb2"), 7: _m("G2")}.get(r, _m("D2"))


def _siege_of_kings() -> np.ndarray:
    pan = dict(PAN, trombone=0.25, horn=-0.25, tuba=0.3, tremolo=-0.1, cello=0.16, bass=0.2, harp=0.3, timpani=-0.1)
    bar = 4.0
    u, L = _unit(KING_BPM, KING_BEATS)
    harm = (_harm(KING_H_A, bar) + _harm(KING_H_A, bar, 32) + _harm(KING_H_B, bar, 64)
            + _harm(KING_H_A3, bar, 96))
    # the theme: trombones (A), horns (A'), the choir broadened (B), all together (A'')
    trombone = _tune(CALL_MARCH, bar, 0.72, shift=-12) + _tune(CALL_MARCH_TURN, bar, 0.66, offset=96, shift=-12)
    trombone += _pad(_voicings(_within(harm, 32, 64), 3, "F2", "F3", "A2"), 0.46)
    horn = _tune(CALL_MARCH, bar, 0.64, offset=32) + _tune(CALL_MARCH_TURN, bar, 0.66, offset=96)
    horn += _tune(KING_FANFARE, 4, 0.56, offset=92)
    tuba = [(s, Lc, _bass(ch, "C2", "B2"), 0.5) for s, Lc, ch in _within(harm, 96, 128)]
    # the choir: chords in A', the broadened call over its own chords in B, the theme on
    # top of its chords in A''
    choir_mel = _tune(KING_CHOIR_B, bar, 0.56, offset=64) + _tune(CALL_MARCH_TURN, bar, 0.5, offset=96)

    def under(evs):
        def ceil(s, Lc):
            inside = [m for t, d, m, v in evs if t < s + Lc - 1e-6 and t + d > s + 1e-6]
            return (min(inside) - 3) if inside else 200
        return ceil

    choir = _pad(_voicings(_within(harm, 32, 64), 3, "F3", "F4", "A3"), 0.42)
    choir += _pad(_voicings(_within(harm, 64, 96), 3, "C3", "A4", "F3", ceiling=under(choir_mel)), 0.42)
    choir += _pad(_voicings(_within(harm, 96, 128), 3, "C3", "A4", "F3", ceiling=under(choir_mel)), 0.4)
    choir += choir_mel
    # the strings: tremolo chords all through, swelling in B
    trem = (_pad(_voicings(_within(harm, 0, 64), 3, "D4", "D5", "A4"), 0.34)
            + _pad(_voicings(_within(harm, 64, 96), 3, "F4", "F5", "A4"), 0.4)
            + _pad(_voicings(_within(harm, 96, 128), 3, "D4", "D5", "A4"), 0.36))
    cel_a, bas_a = _drive(_within(harm, 0, 64), 0.6)
    cel_b, bas_b = _drive(_within(harm, 64, 96), 0.5, accents_only=True)
    cel_c, bas_c = _drive(_within(harm, 96, 128), 0.64)
    organ = _pad(_voicings(_within(harm, 64, 96), 3, "A3", "A4", "D4"), 0.4)
    harp = _gliss(7 * 4 + 2.0, 2.0, "D3", "D6", [2, 5, 9], 0.25, 0.5)
    harp += _gliss(23 * 4 + 2.0, 2.0, "A2", "A5", [9, 1, 4], 0.25, 0.55)
    # percussion
    taiko = []
    for b in range(32):
        if b < 8:
            hits = [(0, 0.55)] if b % 2 == 0 else []
        elif b < 16 or b >= 24:
            hits = [(0, 0.6), (2, 0.48)]
        else:
            hits = [(0, 0.5)] if b % 2 == 0 else []
        taiko += [(b * bar + p, 1.0, _m("D4"), v) for p, v in hits]
    taiko += [(27 * bar + 3.5, 0.5, _m("D4"), 0.42), (31 * bar + 3.5, 0.5, _m("D4"), 0.45)]
    frame_a = [(0, "doum", 0.62), (0.5, "tek", 0.3), (1, "tek", 0.34), (1.5, "doum", 0.5), (2, "tek", 0.3),
               (2.5, "tek", 0.3), (3, "doum", 0.55), (3.5, "tek", 0.36)]
    frame = (_drum_bars([(0, "doum", 0.55), (1.5, "doum", 0.4), (3, "doum", 0.45)], range(0, 8), bar)
             + _drum_bars(frame_a, range(8, 16), bar)
             + _drum_bars([(0, "doum", 0.5), (2, "tek", 0.32)], range(16, 24), bar)
             + _drum_bars(frame_a, range(24, 32), bar))
    # timpani: downbeats in A, the 3+3+2 leaning notes in A' and A'', each chord's first
    # beat in B; rolls on A into A', into A'' and back round to the start
    rolls = [(30.0, 2.0, 0.18, 0.45), (92.0, 4.0, 0.15, 0.55), (126.0, 2.0, 0.18, 0.46)]
    timp = []
    for s, Lc, ch in harm:
        b, p = int(s // 4), _timp_pitch(ch)
        if b < 8:
            if abs(s % 4) < 1e-6:
                timp.append((s, 1.0, p, 0.48))
        elif 16 <= b < 24:
            timp.append((s, 1.0, p, 0.38))
        else:
            for a in ACCENTS:
                t = s - s % 4 + a
                if s - 1e-6 <= t < s + Lc - 1e-6:
                    timp.append((t, 1.0, p, 0.5 if a == 0 else 0.36))
    timp = [e for e in timp if not any(r0 - 1e-6 <= e[0] < r0 + rl - 1e-6 for r0, rl, _, _ in rolls)]
    for r0, rl, v0, v1 in rolls:
        timp += _roll_drum(r0, rl, _m("A2"), v0, v1)
    parts = [
        Part("trombone", _notes(TROMBONE, trombone, u, L, 401, legato=0.92, swell_from=2.0, swell=(92, 118),
                                pan=pan["trombone"]), -22.5, "fluid", _tone_low_brass),
        Part("horn", _notes(HORN, horn, u, L, 402, legato=0.93, swell_from=2.0, swell=(94, 122), pan=pan["horn"]),
             -21.0, "fluid", _tone_horn),
        Part("tuba", _notes(TUBA, tuba, u, L, 403, legato=0.95, swell_from=2.0, swell=(80, 100), pan=pan["tuba"]),
             -32.5, "fluid", _tone_tuba, send=0.5),
        Part("choir", _notes(CHOIR, choir, u, L, 404, legato=1.0, swell_from=1.5, swell=(84, 112), pan=pan["choir"]),
             -24.0, "fluid", _tone_choir),
        Part("tremolo", _notes(TREMOLO, trem, u, L, 405, legato=1.0, swell_from=1.5, swell=(80, 106),
                               pan=pan["tremolo"]), -27.5, "musescore", _tone_strings),
        Part("cellos", _notes(CELLO, cel_a + cel_b + cel_c, u, L, 406, jitter=0.006, legato=0.8, pan=pan["cello"]),
             -25.5, "musescore", _tone_drive, attack=(4.0, 0.05)),
        Part("basses", _notes(BASS, bas_a + bas_b + bas_c, u, L, 407, jitter=0.006, legato=0.85, pan=pan["bass"]),
             -30.0, "fluid", _tone_bass, attack=(3.0, 0.06), send=0.5),
        Part("organ", _notes(ORGAN, organ, u, L, 408, legato=1.0, pan=pan["organ"]),
             -31.0, "fluid", _tone_organ),
        Part("harp", _notes(HARP, harp, u, L, 409, jitter=0.003, legato=1.0, pan=pan["harp"]),
             -25.0, "fluid", _tone_harp),
        Part("taiko", _notes(TAIKO, taiko, u, L, 410, jitter=0.004, legato=1.0, pan=pan["taiko"]),
             -29.0, "fluid", _tone_taiko, send=0.7),
        Part("frame", _notes(DRUM, frame, u, L, 411, jitter=0.005, strokes=FRAME, pan=pan["drum"]),
             -28.5, "fluid", _tone_frame, send=0.6),
        Part("timpani", _notes(TIMPANI, timp, u, L, 412, jitter=0.004, legato=1.0, pan=pan["timpani"]),
             -28.5, "fluid", _tone_timpani, send=0.8),
    ]
    return _mixdown(parts, L, room=0.78, wet=0.24, damping=0.5)


# ============================================================================= the suite
CANDIDATES = [
    Candidate("music", "saga_menu", "Misty Keep",
              "For the menus: a calm, misty ballad in which a harp sings the suite's theme over soft strings, "
              "a solo cello answers, and the violins take the tune home.",
              _misty_keep, tags=["menu"], loop_seconds=_unit(MENU_BPM, MENU_BEATS)[1], bpm=MENU_BPM),
    Candidate("music", "saga_jack", "The Long Road",
              "For the Jacks: an adventurous travelling theme, a French horn calling over a hammered dulcimer, "
              "plucked strings and a light frame drum, with a cello verse and a harp sweep back into the tune.",
              _long_road, tags=["jack"], loop_seconds=_unit(JACK_BPM, JACK_BEATS)[1], bpm=JACK_BPM),
    Candidate("music", "saga_queen", "Veiled Queen",
              "For the Queens: mysterious and tense, a slow circling harp figure and a low wordless choir, the "
              "theme sung by a cello and soft \"ooh\" voices, trembling strings and timpani rolls rising, then "
              "falling away.",
              _veiled_queen, tags=["queen"], loop_seconds=_unit(QUEEN_BPM, QUEEN_BEATS)[1], bpm=QUEEN_BPM),
    Candidate("music", "saga_king", "Siege of Kings",
              "For the Kings, the climax: an epic, driving battle theme of trombones and horns over galloping "
              "cellos and basses, a full choir, timpani and taiko drums, kept warm rather than harsh.",
              _siege_of_kings, tags=["king"], loop_seconds=_unit(KING_BPM, KING_BEATS)[1], bpm=KING_BPM),
]
