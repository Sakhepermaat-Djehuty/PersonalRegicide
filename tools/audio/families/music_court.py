"""Music suite "Royal Court": four looping tracks, one per stage of the castle, played by a
renaissance consort in a stone hall, every note a real instrument recording (``sf.py``: the
Fluid R3 and MuseScore General banks, both MIT).

The consort (in every track): a harp, recorder and flute, a treble and a bass viol (a viola
and a cello) and, for the Jacks' dance, a harpsichord (taking turns with the harp), a soft
tabor and a tambourine. Brass and timpani are kept for the Kings: horns, sackbuts
(trombones), timpani, a double bass and a choir, with the harp and the viols still there.

One theme runs through the suite: a rise of a fifth, D up to A, then a fall down four steps
back home (A G F# E D; A G F E D in the minor). Renaissance musicians turned one tune into
a pair of dances, a slow pavane and a quick galliard; the suite does that, and then lets
the four falling steps grow darker:

  menu   "Candlelit Pavane"      4/4, 72 bpm, D major: the theme as a stately pavane, recorder
                                 then flute over a harp and the viols; no drums
  jack   "The Jack's Galliard"   3/4, 168 bpm, D major: the same tune as a leaping galliard with
                                 hemiola cadences (two bars of three felt as three of two), a
                                 B strain in D mixolydian (C natural); harpsichord, harp,
                                 recorder, flute, viols and a soft tabor; the second time round
                                 the winds play divisions (running ornaments) on the tune
  queen  "The Queen's Sarabande" 3/4, 78 bpm, D minor: the four falling steps become a ground
                                 bass (D C Bb A, the old lament), a slow sarabande leaning on its
                                 second beat; the theme on the viola, then the flute; a sighing
                                 Bb-A, Phrygian cadences, a muffled drum in the second half
  king   "The King's Procession" 4/4, 72 bpm, D minor: the theme on horns over a tread of low
                                 strings and timpani on D and A; a middle section where the choir
                                 sings over a chromatic lament (D C# C B Bb A) and the horns call
                                 the motif; then everything together, ending on A to go round

How a track is made: each line is written bar by bar ("D5:2 A5:2 | ..."; "|" checks the bar
line), the harmony likewise ("D:2 Em:1 Bm:1 | ..."). The bass follows the harmony, inner
voices are led from chord to chord (``_voicings``: each voice moves as little as it can,
the third is present, no parallel fifths or octaves against any other part, below the
tune), and harp arpeggios, rolled chords and the harpsichord's chords are made from those
voicings. The melodies were checked by hand for parallel fifths and octaves against the
bass, and a script checked every pair of parts for held semitone or tritone clashes
(the cadences' suspended fourths have their own sus4 chords so the accompaniment does not
sound the C# under the tune's D). Every note is nudged a few milliseconds and its velocity
a few percent (seeded); bowed and blown notes of a beat or more swell (or fade at a phrase
end). The banks' solo strings, winds and brass have samples up to a quarter-tone out of
tune (a viola G4 +22 cents, a flute C#5 +16), some sharp at first and settling, some with a
vibrato: each sample's pitch is measured over two seconds (``_tuning``) and each note gets a
fixed pitch bend for the average over the part of the sample it plays (measured on the
phrases: the viola's worst note +22 -> +4 cents, the cello within 2). The bank's horn is
a section whose held notes throb, so it goes through a gentle compressor (``_steady``).
Every part is rendered on its own (stereo, panned across a small stage), balanced by
loudness, sent in its own amount to one stone hall (``synth.reverb``, wet only, a short
pre-delay, no bass), rendered past the loop's end and folded back onto its start (a
seamless loop), its two channels evened out, and rotated to a quiet start for the AAC
encoder. Each beat is nudged (``music.aac_unit``) so the loop is a whole number of AAC
frames.
"""
from __future__ import annotations

import dataclasses
import functools
import itertools
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

import music
import sf
import synth as A
from catalog import Candidate
from sf import DRUM, GM, Note

SR = A.SR
TAIL = 5.0                    # seconds rendered past the loop, folded back onto its start
Ev = Tuple[float, float, object, float, str]       # (beat, beats, MIDI pitch or drum key, velocity 0..1, swell)

HARP, HARPSICHORD, RECORDER, FLUTE = GM["harp"], GM["harpsichord"], GM["recorder"], GM["flute"]
VIOLA, CELLO, BASS = GM["viola"], GM["cello"], GM["contrabass"]
HORN, SACKBUT, TIMPANI, CHOIR = GM["french_horn"], GM["trombone"], GM["timpani"], GM["choir"]

# the consort's places on a small stage (-1 left .. 1 right)
PAN = {"harp": -0.22, "harpsichord": 0.28, "recorder": -0.36, "flute": 0.38, "viola": -0.12, "cello": 0.22,
       "bass": 0.1, "horn": -0.28, "sackbut": 0.3, "timpani": -0.05, "choir": 0.0, "tabor": 0.12, "tambourine": 0.4}

# the keys the tunes are built on (pitch classes)
D_MAJOR = (2, 4, 6, 7, 9, 11, 1)
D_MIXOLYDIAN = (2, 4, 6, 7, 9, 11, 0)
D_MINOR = (2, 4, 5, 7, 9, 10, 0)


def _m(p) -> int:
    return A.midi(p) if isinstance(p, str) else int(p)


# ============================================================================= the score
def _bar_check(pos: float, bar: float, what: str) -> None:
    if abs(pos / bar - round(pos / bar)) > 1e-6:
        raise ValueError("bar line at beat %s is not on a bar (%s): %r" % (pos, bar, what[:60]))


def _line(text: str, bar: float, vel: float = 0.64, offset: float = 0.0, strong: Sequence[float] = (),
          bars: Optional[int] = None) -> List[Ev]:
    """A line written note by note: "D5:2 A5:2 | G5:1.5 F#5:0.5 E5:2 |", lengths in beats,
    "r" a rest, "|" a bar line (checked), a trailing "<" or ">" a swell or a fade. Downbeats
    are leaned on, the ``strong`` beats of the bar a little, high notes sing out slightly."""
    out: List[Ev] = []
    pos = 0.0
    for tok in text.split():
        if tok == "|":
            _bar_check(pos, bar, text)
            continue
        sh = ""
        if tok[-1] in "<>":
            sh, tok = tok[-1], tok[:-1]
        p, d = tok.split(":")
        d = float(d)
        if p != "r":
            m = _m(p)
            inbar = round(pos % bar, 6)
            v = vel + (0.06 if inbar < 1e-6 else (0.03 if any(abs(inbar - s) < 1e-6 for s in strong) else 0.0))
            v += 0.003 * (m - 74)
            out.append((offset + pos, d, m, float(np.clip(v, 0.1, 1.0)), sh))
        pos += d
    if bars is not None and abs(pos - bars * bar) > 1e-6:
        raise ValueError("line is %s beats, not %s bars of %s: %r" % (pos, bars, bar, text[:60]))
    return out


_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_QUAL = {"": (0, 4, 7), "m": (0, 3, 7), "dim": (0, 3, 6), "sus4": (0, 5, 7), "7": (0, 4, 7, 10),
         "m7": (0, 3, 7, 10), "m6": (0, 3, 7, 9)}


def _pc(name: str) -> int:
    k = _PC[name[0]]
    for ch in name[1:]:
        k += 1 if ch == "#" else -1
    return k % 12


@functools.lru_cache(maxsize=None)
def _chord(name: str) -> Tuple[int, Tuple[int, ...], int]:
    """"D", "Em", "A/C#", "Gm/Bb" -> (root, chord tones with the root first, bass), as
    pitch classes."""
    body, _, bass = name.partition("/")
    i = 2 if len(body) > 1 and body[1] in "#b" else 1
    root = _pc(body[:i])
    pcs = tuple((root + s) % 12 for s in _QUAL[body[i:]])
    return root, pcs, (_pc(bass) if bass else root)


def _harm(text: str, bar: float, offset: float = 0.0, bars: Optional[int] = None) -> List[Tuple[float, float, str]]:
    """Chords with their lengths: "D:2 Em:1 Bm:1 | A:4 |"."""
    out = []
    pos = 0.0
    for tok in text.split():
        if tok == "|":
            _bar_check(pos, bar, text)
            continue
        name, d = tok.rsplit(":", 1)
        _chord(name)
        out.append((offset + pos, float(d), name))
        pos += float(d)
    if bars is not None and abs(pos - bars * bar) > 1e-6:
        raise ValueError("harmony is %s beats, not %s bars: %r" % (pos, bars, text[:60]))
    return out


def _chord_at(harm, t: float) -> str:
    for s, L, name in harm:
        if s - 1e-6 <= t < s + L - 1e-6:
            return name
    return harm[-1][2]


def _idx(harm, a: float, b: float) -> List[int]:
    """The chords that start in [a, b) beats."""
    return [j for j, (s, L, nm) in enumerate(harm) if a - 1e-6 <= s < b - 1e-6]


def _pick(seq, idx: Sequence[int]) -> list:
    return [seq[j] for j in idx]


def _shift(evs: List[Ev], semis: int = 0, vel: float = 1.0, offset: float = 0.0) -> List[Ev]:
    return [(s + offset, L, m + semis, v * vel, sh) for s, L, m, v, sh in evs]


def _diatonic(m: int, steps: int, scale: Sequence[int]) -> int:
    """Move a pitch by scale steps (a pitch outside the scale moves from the scale tone
    just below it)."""
    ladder = [k for k in range(24, 108) if k % 12 in scale]
    i = max(j for j, k in enumerate(ladder) if k <= m)
    return ladder[i + steps]


def _parallel(p0: int, b0: int, p1: int, b1: int) -> bool:
    """Two parts moving the same way into the same fifth or octave."""
    return (p1 != p0 and b1 != b0 and (p1 - p0) * (b1 - b0) > 0 and (p0 - b0) % 12 == (p1 - b1) % 12
            and (p1 - b1) % 12 in (0, 7))


def _second(mel: List[Ev], harm, scale: Sequence[int], beat: float = 1.0, vel: float = 0.8,
            bass: Optional[List[int]] = None) -> List[Ev]:
    """A second voice a third below the tune; on the beats and under long notes, where the
    third is not in the chord, the nearest chord tone a fourth to a sixth below instead,
    and never in parallel fifths or octaves with the bass."""
    out = []
    prev = None
    for s, L, m, v, sh in mel:
        cands = [_diatonic(m, -2, scale)]
        if abs(s / beat - round(s / beat)) < 1e-6 or L >= beat - 1e-6:
            pcs = _chord(_chord_at(harm, s))[1]
            alts = [c for c in (_diatonic(m, -k, scale) for k in (3, 4, 5)) if c % 12 in pcs]
            cands = (cands + alts) if cands[0] % 12 in pcs else (alts + cands)
        h = cands[0]
        b = None
        if bass is not None:
            j = next(j for j in range(len(harm) - 1, -1, -1) if harm[j][0] <= s + 1e-6)
            b = bass[j]
            if prev is not None:
                h = next((c for c in cands if not _parallel(prev[0], prev[1], c, b)), h)
        out.append((s, L, h, v * vel, sh))
        prev = (h, b) if b is not None else None
    return out


def _bass_line(harm, lo: str, hi: str, first: Optional[str] = None) -> List[int]:
    """The chord's bass note for each chord, in [lo, hi], each the nearest to the last."""
    a, b = _m(lo), _m(hi)
    prev = _m(first) if first else None
    out = []
    for s, L, name in harm:
        pc = _chord(name)[2]
        cands = [k for k in range(a, b + 1) if k % 12 == pc]
        k = cands[0] if prev is None else min(cands, key=lambda c: (abs(c - prev), c))
        out.append(k)
        prev = k
    return out


def _bass_text(text: str, harm) -> List[int]:
    """A bass line written out, one note per chord ("D3 G2 A2 ..."), checked against the
    chords' bass notes."""
    notes = [_m(t) for t in text.split() if t != "|"]
    if len(notes) != len(harm):
        raise ValueError("%d bass notes for %d chords" % (len(notes), len(harm)))
    for k, (s, L, name) in zip(notes, harm):
        if k % 12 != _chord(name)[2]:
            raise ValueError("bass %s under %s at beat %s" % (k, name, s))
    return notes


def _voicings(harm, n: int, lo: str, hi: str, bass: Optional[List[int]] = None, top: Optional[List[Ev]] = None,
              above: bool = False) -> List[Tuple[int, ...]]:
    """``n`` upper voices for each chord, chord tones in [lo, hi] from low to high, led
    smoothly: each voice moves as little as it can, the third is there, the third is not
    doubled, no parallel fifths or octaves between any two parts (the bass and the tune
    included), no voice at or above the tune (unless ``above``: then the voices keep a
    third away from it)."""
    a, b = _m(lo), _m(hi)
    out: List[Tuple[int, ...]] = []
    prev: Optional[Tuple[int, ...]] = None
    prev_b = prev_t = None
    mid = (a + b) / 2.0
    for i, (s, L, name) in enumerate(harm):
        root, pcs, bpc = _chord(name)
        third = pcs[1] if len(pcs) > 1 and name.split("/")[0][1:2] not in ("s",) else None
        bp = bass[i] if bass else None
        tp = None
        if top:
            cur = [e for e in top if e[0] <= s + 1e-6 and e[0] + e[1] > s + 1e-6]
            tp = cur[-1][2] if cur else None
        lo_ = a
        pool = [k for k in range(lo_, b + 1) if k % 12 in pcs]
        while len(pool) < n + 1:                           # too narrow for this chord: reach lower
            lo_ -= 5
            pool = [k for k in range(lo_, b + 1) if k % 12 in pcs]
        best, best_cost = None, None
        for combo in itertools.combinations(pool, n):
            cost = 0.0
            if prev is not None:
                cost += sum(abs(c - p) for c, p in zip(combo, prev))
            else:
                cost += 0.3 * sum(abs(c - mid) for c in combo)
            have = [c % 12 for c in combo] + ([bp % 12] if bp is not None else [])
            if tp is not None and tp % 12 in pcs:
                have.append(tp % 12)
            if third is not None and third not in have:
                cost += 14
            if root not in have:
                cost += 8
            if len(pcs) > 3 and pcs[3] not in have:
                cost += 4
            if third is not None and have.count(third) > 1:
                cost += 5
            for x, y in zip(combo, combo[1:]):
                if y - x > 12:
                    cost += 4
                elif y - x < 3:
                    cost += 2
            if tp is not None:
                for c in combo:
                    if not above and c >= tp:
                        cost += 30
                    elif abs(tp - c) <= 2:
                        cost += 6
            if prev is not None:
                cur_parts = list(combo) + [bp, tp]
                prev_parts = list(prev) + [prev_b, prev_t]
                for (i1, c1), (i2, c2) in itertools.combinations(enumerate(cur_parts), 2):
                    p1, p2 = prev_parts[i1], prev_parts[i2]
                    if None in (c1, c2, p1, p2) or (i1 >= n and i2 >= n):
                        continue
                    iv0, iv1 = (p1 - p2) % 12, (c1 - c2) % 12
                    if iv0 == iv1 and iv1 in (0, 7) and c1 != p1 and np.sign(c1 - p1) == np.sign(c2 - p2):
                        cost += 20
            if best_cost is None or cost < best_cost:
                best, best_cost = combo, cost
        out.append(best)
        prev, prev_b, prev_t = best, bp, tp
    return out


def _held(harm, pitches: Sequence[int], vel: float, sh: str = "") -> List[Ev]:
    """One sustained note per chord, a repeated pitch held on as one note."""
    out: List[Ev] = []
    for (s, L, name), p in zip(harm, pitches):
        if out and out[-1][2] == p and abs(out[-1][0] + out[-1][1] - s) < 1e-6:
            q = out[-1]
            out[-1] = (q[0], q[1] + L, p, q[3], q[4])
        else:
            out.append((s, L, p, vel, sh))
    return out


def _arp(harm, bass: List[int], voic, unit: float, pattern: Sequence[int], vel: float, ring: float = 1.0,
         accent: float = 1.12) -> List[Ev]:
    """A broken chord, one note per ``unit``: the pattern picks from [bass, voice 1, voice
    2, ...] (-1 the bass), every string ringing until the chord changes."""
    out: List[Ev] = []
    for (s, L, name), b, v in zip(harm, bass, voic):
        tones = [b] + list(v)
        k = 0
        t = s
        while t < s + L - 1e-6:
            idx = pattern[k % len(pattern)]
            p = tones[idx + 1]
            out.append((t, (s + L - t) * ring + 0.1 * unit, p, min(1.0, vel * (accent if k == 0 else 1.0)), ""))
            k += 1
            t += unit
    return out


def _roll(t: float, pitches: Sequence[int], L: float, v: float, spread: float) -> List[Ev]:
    """A chord spread from the bottom up, as a harpist or a lutenist plays it."""
    return [(t + i * spread, L - i * spread, p, v * (1.0 - 0.04 * i), "") for i, p in enumerate(pitches)]


def _drums(pattern: Sequence[Tuple[float, str, float]], bars: Sequence[int], bar: float) -> List[Ev]:
    return [(b * bar + pos, 0.25, key, v, "") for b in bars for pos, key, v in pattern]


# ============================================================================= rendering
def _f0(seg: np.ndarray, guess: float) -> float:
    """The pitch of a held note near ``guess`` Hz: the strongest of its first three
    harmonics, located between the bins of a zero-padded spectrum (a parabola through
    the peak's log magnitudes), divided back down."""
    seg = seg - seg.mean()
    n = len(seg)
    spec = np.abs(np.fft.rfft(seg * np.hanning(n), 8 * n)) + 1e-12
    df = SR / (8.0 * n)
    best = (guess, 0.0)
    for h in (1, 2, 3):
        lo, hi = int(guess * h * 2 ** (-0.6 / 12) / df), int(guess * h * 2 ** (0.6 / 12) / df) + 1
        if hi + 1 >= len(spec) or hi <= lo:
            continue
        i = lo + int(np.argmax(spec[lo:hi]))
        a, b, c = np.log(spec[i - 1:i + 2])
        off = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) < 0 else 0.0
        if spec[i] > best[1]:
            best = ((i + off) * df / h, float(spec[i]))
    return best[0]


TRACK_WIN, TRACK_HOP, TRACK_N = 0.3, 0.15, 11          # 0.1 .. 1.9 s of each sample


@functools.lru_cache(maxsize=None)
def _tuning(program: int, bank: str, pitches: Tuple[int, ...], vel: int) -> Dict[int, np.ndarray]:
    """How far (cents) the bank's sample for each pitch is from true, over time: each
    pitch held for two seconds and measured in overlapping 0.3 s windows. (Some samples
    start sharp and settle, some have a vibrato: a note is corrected by the average over
    the part of the sample it plays.)"""
    notes = [Note(program, p, i * 2.2, 2.0, vel=vel) for i, p in enumerate(pitches)]
    x = sf.render(notes, len(pitches) * 2.2 + 0.5, bank=bank)
    out = {}
    for i, p in enumerate(pitches):
        g = A.note_hz(int(p))
        row = []
        for k in range(TRACK_N):
            a = 2.2 * i + 0.1 + k * TRACK_HOP
            row.append(1200 * np.log2(_f0(x[A.n_of(a):A.n_of(a + TRACK_WIN)], g) / g))
        out[p] = np.clip(np.array(row), -45, 45)
    return out


def _cents_off(track: np.ndarray, dur: float) -> float:
    """A note's average error: the windows that fit in the time it is held (at least the
    first)."""
    k = int(np.clip((dur - 0.1 - TRACK_WIN) / TRACK_HOP + 1, 1, TRACK_N))
    return float(np.mean(track[:k]))


def _notes(program: int, evs: List[Ev], unit: float, loop_s: float, seed: int, jitter: float = 0.008,
           legato: float = 0.92, swell_min: Optional[float] = None, swell=(108, 124), pan: float = 0.0,
           vel: float = 1.0, bank: str = "musescore", tune: bool = False, kit: str = "standard") -> List[Note]:
    """Events (in beats) to bank notes: seconds, a small human nudge in time and velocity
    (seeded), ``legato`` of each length held, a swell on notes at least ``swell_min``
    beats long (a fade on those marked ">"), the sample's tuning corrected (``tune``). A
    note nudged before the loop's start wraps round to its end."""
    rng = np.random.default_rng(seed)
    dev: Dict[int, np.ndarray] = {}
    if tune and program != DRUM and evs:
        vmed = int(np.clip(round(127 * vel * float(np.median([e[3] for e in evs])) / 10) * 10, 40, 120))
        dev = _tuning(program, bank, tuple(sorted({int(e[2]) for e in evs})), vmed)
    out: List[Note] = []
    for s, L, m, v, sh in evs:
        t = s * unit + rng.uniform(-jitter, jitter)
        if t < 0:
            t += loop_s
        v127 = int(np.clip(round(127 * v * vel * rng.uniform(0.94, 1.04)), 1, 127))
        if program == DRUM:
            out.append(Note(DRUM, m, t + rng.uniform(0, 0.002), 0.1, vel=v127, pan=pan, kit=kit))
            continue
        dur = max(0.04, L * unit * legato)
        sw = None
        if sh or (swell_min is not None and L >= swell_min - 1e-6):
            lo_, hi_ = swell[0] + int(rng.integers(-3, 4)), swell[1] + int(rng.integers(-2, 3))
            sw = (int(np.clip(hi_, 0, 127)), int(np.clip(lo_ - 14, 0, 127))) if sh == ">" else \
                 (int(np.clip(lo_, 0, 127)), int(np.clip(hi_, 0, 127)))
        bend = None
        c = _cents_off(dev[int(m)], dur) if int(m) in dev else 0.0
        if abs(c) >= 4.0:
            bend = (-c / 100.0, -c / 100.0)
        out.append(Note(program, int(m), t, dur, vel=v127, pan=pan, swell=sw, bend=bend))
    return _declash(out)


def _declash(notes: List[Note]) -> List[Note]:
    """Notes sharing a channel (no bend, no swell) on the same key: let each go before the
    next is struck, or the next one's release would cut both."""
    plain = [n for n in notes if n.bend is None and n.swell is None and n.program != DRUM]
    by: Dict[tuple, List[Note]] = {}
    for n in plain:
        by.setdefault((n.program, round(n.pan, 2), n.key()), []).append(n)
    for group in by.values():
        group.sort(key=lambda n: n.start)
        for a_, b_ in zip(group, group[1:]):
            if a_.start + a_.dur > b_.start - 0.004:
                a_.dur = max(0.02, b_.start - a_.start - 0.006)
    return notes


def _groups(notes: Sequence[Note]) -> List[List[Note]]:
    """Split notes into renders FluidSynth can play: one channel per plain instrument, one
    per bending or swelling note (reused once it has rung out), 15 in all."""
    plain = [n for n in notes if n.bend is None and n.swell is None]
    solo = sorted([n for n in notes if not (n.bend is None and n.swell is None)], key=lambda n: n.start)
    nplain = len({(n.program, round(n.pan, 2), n.reverb, n.chorus) for n in plain if n.program != DRUM})
    groups = [[list(plain), [], 15 - nplain]]
    for n in solo:
        for g in groups:
            busy = g[1]
            slot = next((b for b in busy if b[0] == n.program and b[1] <= n.start), None)
            if slot is not None:
                busy.remove(slot)
            elif len(busy) >= g[2]:
                continue
            busy.append((n.program, n.start + n.dur + 1.5))
            g[0].append(n)
            break
        else:
            groups.append([[n], [(n.program, n.start + n.dur + 1.5)], 15])
    return [g[0] for g in groups if g[0]]


def _render(notes: Sequence[Note], seconds: float, bank: str) -> np.ndarray:
    out = np.zeros((A.n_of(seconds), 2))
    for g in _groups(notes):
        x = sf.render(g, seconds, bank=bank, stereo=True)
        out[:len(x)] += x[:len(out)]
    return out


# ----------------------------------------------------------------------------- tone
def _band(lo: float, hi: float, order: int = 2) -> Callable[[np.ndarray], np.ndarray]:
    return lambda x: A.lowpass(A.highpass(x, lo, 2), hi, order)


def _harp_tone(x: np.ndarray) -> np.ndarray:
    """The harp a little less boomy, its top left open."""
    y = A.highpass(x, 75, 2)
    y = A.peak_eq(y, 170, -2.5, 0.8)
    return A.lowpass(y, 9500, 2)


def _harpsichord_tone(x: np.ndarray) -> np.ndarray:
    """The harpsichord's jangle eased for long listening: a dip at its 3-4 kHz bite and
    nothing above 7 kHz."""
    y = A.highpass(x, 120, 2)
    y = A.peak_eq(y, 3600, -3.5, 0.9)
    return A.lowpass(y, 7000, 2)


def _viola_tone(x: np.ndarray) -> np.ndarray:
    y = A.highpass(x, 130, 2)
    y = A.peak_eq(y, 3000, -2.0, 1.0)
    return A.lowpass(y, 7500, 2)


def _cello_tone(x: np.ndarray) -> np.ndarray:
    """A bass viol: less boom at 100-250 Hz (mud), a soft top."""
    y = A.highpass(x, 60, 2)
    y = A.peak_eq(y, 180, -2.5, 0.9)
    return A.lowpass(y, 6000, 2)


def _steady(x: np.ndarray, below: float = 8.0, ratio: float = 3.0) -> np.ndarray:
    """A gentle compressor: the bank's horn is a section whose held notes throb by several
    dB; this halves that and leaves the attacks alone."""
    return A.compress(x, A._rms_db(x) - below, ratio, 20.0, 160.0)


def _tamb_tone(x: np.ndarray) -> np.ndarray:
    """A tambourine's jingles, bright but not sizzling."""
    return A.lowpass(A.highpass(x, 500, 2), 7000, 4)


@dataclasses.dataclass
class Part:
    name: str
    notes: List[Note]
    level: float                              # loudness (dB) while it plays, before mastering
    bank: str = "musescore"
    tone: Optional[Callable[[np.ndarray], np.ndarray]] = None
    send: float = 1.0                         # how much of it goes to the hall


def _fit(x: np.ndarray, n: int) -> np.ndarray:
    return x[:n] if len(x) >= n else np.concatenate([x, np.zeros((n - len(x),) + x.shape[1:])])


def _at(x: np.ndarray, db: float) -> np.ndarray:
    return x * 10 ** ((db - A._rms_db(x)) / 20.0)


def _hall(send: np.ndarray, size: float, damping: float, predelay: float = 0.024) -> np.ndarray:
    """The stone hall alone (no dry signal): Freeverb at full wet minus its dry path, a
    little later than the sound (the walls are some way off)."""
    y = A.reverb(send, room=size, wet=1.0, damping=damping, width=0.9, tail=3.0)
    w = y - _fit(send, len(y))           # JUCE's dry gain at dry_level 0.5 is exactly 1
    d = A.n_of(predelay)
    return np.concatenate([np.zeros((d, 2)), w[:-d]])


def _mixdown(parts: Sequence[Part], loop_s: float, size: float, wet: float, damping: float = 0.5) -> np.ndarray:
    seconds = loop_s + TAIL
    n = A.n_of(seconds)
    dry = np.zeros((n, 2))
    send = np.zeros((n, 2))
    for p in parts:
        x = _fit(_render(p.notes, seconds, p.bank), n)
        if p.tone:
            x = p.tone(x)
        x = _at(x, p.level)
        dry += x
        send += p.send * x
    send = A.lowpass(A.highpass(send, 220, 2), 7000, 2)     # no low end in the hall: no mud
    hall = _hall(send, size, damping)
    mix = _fit(dry, len(hall)) + wet * hall
    mix = A.highpass(mix, 35, 2)
    loop = A.loop_seamless(mix[:A.n_of(loop_s)], mix[A.n_of(loop_s):])
    # centre the stage: even out the two channels' loudness (a fraction of a dB)
    d = float(np.clip(20 * np.log10(np.sqrt(np.mean(loop[:, 0] ** 2)) / np.sqrt(np.mean(loop[:, 1] ** 2))), -1.5, 1.5))
    loop = loop * np.array([10 ** (-d / 40), 10 ** (d / 40)])
    return music.aac_friendly_start(loop)


# ============================================================================= menu: Candlelit Pavane
MENU_BPM = 72.0
MENU_BEATS = 24 * 4
MENU_UNIT = music.aac_unit(60.0 / MENU_BPM, MENU_BEATS)
MENU_LOOP = MENU_BEATS * MENU_UNIT

# the court theme in D major: a rise of a fifth, then the four steps down, twice
PAV_A = ("D5:2 A5:2 | G5:1.5 F#5:0.5 E5:2 | F#5:2 E5:1 D5:1 | E5:1 D5:1 C#5:2 | "
         "D5:2 A5:2 | B5:1.5 A5:0.5 G5:1 F#5:1 | E5:2 D5:1 C#5:1 | D5:4> |")
# the same, lightly ornamented (the flute's turn)
PAV_A2 = ("D5:2 A5:2 | G5:1 F#5:0.5 G5:0.5 E5:2 | F#5:1.5 G5:0.5 E5:1 D5:1 | E5:1 D5:0.5 E5:0.5 C#5:2 | "
          "D5:1 E5:0.5 F#5:0.5 A5:2 | B5:1 A5:0.5 B5:0.5 G5:1 F#5:1 | E5:1.5 F#5:0.5 D5:1 C#5:1 | D5:4> |")
PAV_HA = "D:4 | G:2 A:2 | D:2 Em:1 Bm:1 | Asus4:2 A:2 | D:2 D/F#:2 | G:2 Em:1 D:1 | Em:2 Asus4:1 A:1 | D:4 |"
# the B strain: the fifth turned upside down (falling), towards B minor, back to A
PAV_B = ("B5:2 F#5:2 | E5:1.5 F#5:0.5 G5:1 E5:1 | F#5:2 B4:2 | C#5:1.5 D5:0.5 E5:2 | "
         "F#5:2 B5:2 | A5:1.5 G5:0.5 F#5:1 E5:1 | G5:2 F#5:1 E5:1 | E5:2 A4:2 |")
PAV_HB = "G:2 Bm:2 | Em:3 A:1 | D:2 G:2 | A:2 A/C#:2 | Bm:2 G:2 | D:3 A:1 | Em:2 D:1 A:1 | A:2 A/C#:2 |"
PAV_BASS_A = "D3 | G2 A2 | D3 E3 B2 | A2 A2 | D3 F#3 | G3 E3 D3 | E3 A2 A2 | D3"
PAV_BASS_B = "G2 B2 | E3 A2 | D3 G2 | A2 C#3 | B2 G2 | D3 A2 | E3 D3 A2 | A2 C#3"


def _pavane() -> np.ndarray:
    bar = 4.0
    u, L = MENU_UNIT, MENU_LOOP
    a1 = _line(PAV_A, bar, 0.6, 0, (2.0,), bars=8)
    a2 = _line(PAV_A2, bar, 0.6, 32, (2.0,), bars=8)
    b = _line(PAV_B, bar, 0.62, 64, (2.0,), bars=8)
    harm = _harm(PAV_HA, bar, 0, 8) + _harm(PAV_HA, bar, 32, 8) + _harm(PAV_HB, bar, 64, 8)
    bass = _bass_text(" ".join([PAV_BASS_A, PAV_BASS_A, PAV_BASS_B]), harm)
    tune = a1 + a2 + b
    voic = _voicings(harm, 3, "F#3", "D5", bass, tune)
    # the harp: a broken chord in quavers (bass, then up and back through the chord) in the
    # A strains; rolled chords on the first and third beats in B
    ja, jb = _idx(harm, 0, 64), _idx(harm, 64, 96)
    harp = _arp(_pick(harm, ja), _pick(bass, ja), _pick(voic, ja), 0.5, (-1, 0, 1, 2, 1, 2, 1, 0), 0.4)
    for (s, Lc, name), bp, v in zip(_pick(harm, jb), _pick(bass, jb), _pick(voic, jb)):
        harp += _roll(s, [bp] + list(v), Lc + 0.3, 0.42, 0.045)
        if Lc >= 4:
            harp += _roll(s + 2, list(v)[1:], 2.3, 0.3, 0.04)
        elif Lc >= 3:
            harp += [(s + 2, Lc - 1.9, v[2], 0.3, "")]
    # the bass viol: the bass line, bowed, legato
    cello = _held(harm, bass, 0.48)
    # the treble viol: the middle voice of the chords, held, from the second A
    j2 = _idx(harm, 32, 96)
    viola = _held(_pick(harm, j2), [voic[j][1] for j in j2], 0.42)
    # who plays the tune: recorder (A), flute (A', ornamented), flute with the recorder a
    # third below (B)
    rec = a1 + _second(b, harm, D_MAJOR, 1.0, 0.86, bass)
    flute = a2 + b
    parts = [
        Part("recorder", _notes(RECORDER, rec, u, L, 11, legato=0.95, swell_min=2, pan=PAN["recorder"], tune=True),
             -21.0, "musescore", _band(260, 8000)),
        Part("flute", _notes(FLUTE, flute, u, L, 12, legato=0.95, swell_min=2, pan=PAN["flute"], tune=True),
             -21.0, "musescore", _band(240, 8500), 1.1),
        Part("harp", _notes(HARP, harp, u, L, 13, jitter=0.006, legato=1.0, pan=PAN["harp"]), -22.0, "musescore",
             _harp_tone, 1.2),
        Part("viola", _notes(VIOLA, viola, u, L, 14, legato=0.97, swell_min=2, swell=(100, 120), pan=PAN["viola"],
                             tune=True), -27.5, "musescore", _viola_tone),
        Part("cello", _notes(CELLO, cello, u, L, 15, legato=0.97, swell_min=2, swell=(100, 120), pan=PAN["cello"],
                             tune=True), -26.0, "musescore", _cello_tone, 0.6),
    ]
    return _mixdown(parts, L, size=0.62, wet=0.32)


# ============================================================================= jack: The Jack's Galliard
JACK_BPM = 168.0
JACK_BEATS = 64 * 3
JACK_UNIT = music.aac_unit(60.0 / JACK_BPM, JACK_BEATS)
JACK_LOOP = JACK_BEATS * JACK_UNIT

# the pavane's tune in three: long-short, and a hemiola to close (two bars as three minims)
GAL_A = ("D5:2 A5:1 | G5:1.5 F#5:0.5 E5:1 | F#5:2 D5:1 | E5:2 A4:1 | D5:2 A5:1 | B5:1.5 A5:0.5 G5:1 | "
         "F#5:2 E5:2 D5:2 |")
GAL_HA = "D:3 | Em:3 | Bm:3 | A:2 A/C#:1 | D:3 | G:3 | D:2 A:2 D:2 |"
GAL_B = ("A5:2 F#5:1 | G5:2 E5:1 | F#5:2 D5:1 | E5:2 C5:1 | D5:1 E5:1 F#5:1 | G5:1 A5:1 B5:1 | "
         "G5:1 F#5:1 E5:2 D5:2 |")
GAL_HB = "D:3 | C:3 | D:3 | Am:3 | Bm:3 | G:3 | Em:2 A:2 D:2 |"
# divisions: the same tunes broken into running quavers, as players ornamented a repeat
GAL_A_DIV = ("D5:1 E5:0.5 F#5:0.5 A5:1 | G5:0.5 A5:0.5 G5:0.5 F#5:0.5 E5:1 | F#5:1 E5:0.5 F#5:0.5 D5:1 | "
             "E5:1 D5:0.5 C#5:0.5 A4:1 | D5:1 E5:0.5 F#5:0.5 A5:1 | B5:1 A5:0.5 B5:0.5 G5:1 | "
             "F#5:1 G5:0.5 F#5:0.5 E5:1 D5:0.5 E5:0.5 D5:2 |")
GAL_B_DIV = ("A5:1 G5:0.5 F#5:0.5 E5:0.5 F#5:0.5 | G5:1 E5:0.5 D5:0.5 C5:0.5 E5:0.5 | F#5:1 E5:0.5 D5:0.5 A4:0.5 D5:0.5 | "
             "E5:1 D5:0.5 C5:0.5 B4:0.5 C5:0.5 | D5:0.5 C#5:0.5 D5:0.5 E5:0.5 F#5:1 | G5:0.5 F#5:0.5 G5:0.5 A5:0.5 B5:1 | "
             "G5:1 F#5:1 E5:1 F#5:0.5 E5:0.5 D5:2 |")


def _galliard() -> np.ndarray:
    bar = 3.0
    u, L = JACK_UNIT, JACK_LOOP
    plan = ["A", "A", "B", "B", "A", "Ad", "Bd", "B"]
    text = {"A": GAL_A, "Ad": GAL_A_DIV, "B": GAL_B, "Bd": GAL_B_DIV}
    tune: List[List[Ev]] = []
    plain: List[List[Ev]] = []
    harm = []
    for i, k in enumerate(plan):
        off = i * 24.0
        tune.append(_line(text[k], bar, 0.62, off, (2.0,), bars=8))
        plain.append(_line(GAL_A if k[0] == "A" else GAL_B, bar, 0.62, off, (2.0,), bars=8))
        harm += _harm(GAL_HA if k[0] == "A" else GAL_HB, bar, off, 8)
    scale = [D_MAJOR if k[0] == "A" else D_MIXOLYDIAN for k in plan]
    bass = _bass_line(harm, "D2", "E3", "D3")
    second = [_second(plain[i], harm, scale[i], 1.0, 0.84, bass) for i in range(8)]
    voic = _voicings(harm, 3, "A3", "E5", bass, [e for t in tune for e in t])
    alto = _voicings(harm, 1, "A3", "A4", bass, [e for t in tune for e in t])

    def strain(i):
        return [j for j, (s, Lc, nm) in enumerate(harm) if i * 24 - 1e-6 <= s < (i + 1) * 24 - 1e-6]

    rec: List[Ev] = []
    fl: List[Ev] = []
    vla: List[Ev] = []
    rec += tune[0]                                                   # 1: the recorder
    fl += tune[1]; rec += second[1]                                  # 2: flute, recorder a third below
    vla += _shift(tune[2], -12, 1.05)                                # 3: B on the treble viol, low
    fl += tune[3]; rec += second[3]                                  # 4: flute and recorder
    rec += tune[4]                                                   # 5: the recorder, harp only (a breather)
    fl += tune[5]; vla += _shift(plain[5], -12, 0.95)                # 6: flute divisions over the plain tune
    rec += tune[6]; vla += _shift(second[6], -12, 1.0)               # 7: recorder divisions, viol below
    fl += tune[7]; rec += second[7]                                  # 8: everyone
    vla += _held([harm[j] for j in strain(7)], [alto[j][0] for j in strain(7)], 0.5)
    # the harpsichord and the harp take turns at the chords (both only in the last strain):
    # the harpsichord, bass and chord on the downbeat, the chord again on the third beat
    hpsi: List[Ev] = []
    for i in (0, 1, 3, 6, 7):
        for j in strain(i):
            s, Lc, nm = harm[j]
            hpsi += _roll(s, [bass[j]] + list(voic[j]), min(Lc, 2.0) * 0.9, 0.5, 0.012)
            if Lc >= 3 - 1e-6:
                hpsi += _roll(s + 2, list(voic[j]), 0.85, 0.36, 0.01)
    # the harp: one string a beat through the chord; in the breather, bass and a rolled chord
    harp: List[Ev] = []
    for i in (2, 5, 7):
        js = strain(i)
        harp += _arp([harm[j] for j in js], [bass[j] for j in js], [voic[j] for j in js], 1.0, (-1, 1, 2), 0.42)
    for j in strain(4):
        s, Lc, nm = harm[j]
        harp += [(s, Lc + 0.2, bass[j], 0.5, "")] + _roll(s + 1, list(voic[j]), Lc - 0.8, 0.4, 0.04)
    # the bass viol: the root held through the bar, the fifth on the third beat when fuller
    cello: List[Ev] = []
    for i in range(8):
        for j in strain(i):
            s, Lc, nm = harm[j]
            if i in (3, 6, 7) and Lc >= 3 - 1e-6:
                fifth = bass[j] + 7 if bass[j] + 7 <= _m("E3") else bass[j] - 5
                cello += [(s, 2.0, bass[j], 0.52, ""), (s + 2, 1.0, fifth, 0.44, "")]
            else:
                cello.append((s, Lc, bass[j], 0.5 if i != 4 else 0.42, ""))
    # the tabor (a small snared drum played with one stick): a stroke on the downbeat and a
    # lighter one on the galliard's third beat; in the hemiola, a stroke on each minim
    def stroke(t: float, v: float) -> List[Ev]:
        return [(t, 0.25, "high_tom", v, ""), (t, 0.25, "snare", v * 0.62, "")]

    tabor: List[Ev] = []
    tamb: List[Ev] = []
    for i in range(8):
        if i in (2, 4):
            continue
        for b in range(i * 8, i * 8 + 8):
            if b % 8 == 6:
                for k in range(3):
                    tabor += stroke(b * bar + 2 * k, 0.52 if k == 0 else 0.44)
                    if i in (1, 3, 6, 7):
                        tamb.append((b * bar + 2 * k + 1, 0.25, "tambourine", 0.28, ""))
            elif b % 8 == 7:
                continue
            else:
                tabor += stroke(b * bar, 0.52)
                if i != 0:
                    tabor += stroke(b * bar + 2, 0.36)
                if i in (1, 3, 6, 7):
                    tamb.append((b * bar + 2, 0.25, "tambourine", 0.3, ""))
    parts = [
        Part("recorder", _notes(RECORDER, rec, u, L, 21, legato=0.9, swell_min=2, pan=PAN["recorder"], tune=True),
             -21.0, "musescore", _band(260, 8000)),
        Part("flute", _notes(FLUTE, fl, u, L, 22, legato=0.9, swell_min=2, pan=PAN["flute"], tune=True),
             -21.0, "musescore", _band(240, 8500), 1.1),
        Part("viola", _notes(VIOLA, vla, u, L, 23, legato=0.9, swell_min=2, swell=(104, 122), pan=PAN["viola"], tune=True),
             -23.0, "musescore", _viola_tone),
        Part("harpsichord", _notes(HARPSICHORD, hpsi, u, L, 24, jitter=0.005, legato=1.0, pan=PAN["harpsichord"]),
             -24.5, "fluid", _harpsichord_tone),
        Part("harp", _notes(HARP, harp, u, L, 25, jitter=0.005, legato=1.0, pan=PAN["harp"]), -24.0, "musescore",
             _harp_tone, 1.2),
        Part("cello", _notes(CELLO, cello, u, L, 26, legato=0.85, swell_min=3, swell=(104, 120), pan=PAN["cello"],
                             tune=True), -25.5, "musescore", _cello_tone, 0.6),
        Part("tabor", _notes(DRUM, tabor, u, L, 27, jitter=0.004, pan=PAN["tabor"], kit="brush"), -30.0, "fluid",
             _band(100, 5000), 0.7),
        Part("tambourine", _notes(DRUM, tamb, u, L, 28, jitter=0.004, pan=PAN["tambourine"]), -34.0, "fluid",
             _tamb_tone, 0.8),
    ]
    return _mixdown(parts, L, size=0.55, wet=0.26)


# ============================================================================= queen: The Queen's Sarabande
QUEEN_BPM = 78.0
QUEEN_BEATS = 32 * 3
QUEEN_UNIT = music.aac_unit(60.0 / QUEEN_BPM, QUEEN_BEATS)
QUEEN_LOOP = QUEEN_BEATS * QUEEN_UNIT

# over the falling ground D C Bb A (twice): the theme's fifth, leaning on the second beat
SAR_A = ("D5:1 A5:2 | E5:1 G5:1.5 F5:0.5 | D5:1 F5:2 | C#5:1 E5:2 | "
         "D5:1 A5:1.5 Bb5:0.5 | A5:2 E5:1 | F5:1.5 E5:0.5 D5:1 | C#5:2 E5:1> |")
SAR_A2 = ("D5:1 A5:1.5 G5:0.5 | E5:1 G5:1 F5:0.5 E5:0.5 | D5:1 F5:1.5 E5:0.5 | C#5:1 E5:1.5 D5:0.5 | "
          "D5:1 A5:1 Bb5:0.5 A5:0.5 | A5:1.5 G5:0.5 E5:1 | F5:0.5 G5:0.5 F5:1 E5:0.5 D5:0.5 | C#5:2 E5:1> |")
SAR_HA = "Dm:3 | C:3 | Bb:3 | A:3 | Dm:3 | Am/C:2 C:1 | Bb:3 | A:3 |"
# the B strain climbs to F major and comes back down the ground to the Phrygian close
SAR_B = ("A5:1 C6:2 | E5:1 G5:2 | F5:2 D5:1 | E5:2 C#5:1 | D5:1 F5:1 Bb5:1 | A5:1 F5:1 C5:1 | "
         "Bb4:1 D5:1.5 E5:0.5 | C#5:2 E5:1> |")
SAR_HB = "F:3 | C:3 | Dm:3 | A:3 | Bb:3 | F:3 | Gm:3 | A:3 |"


def _sarabande() -> np.ndarray:
    bar = 3.0
    u, L = QUEEN_UNIT, QUEEN_LOOP
    strong = (1.0,)                                   # a sarabande's weight on its second beat
    a1 = _line(SAR_A, bar, 0.62, 0, strong, bars=8)
    a2 = _line(SAR_A2, bar, 0.6, 24, strong, bars=8)
    b = _line(SAR_B, bar, 0.62, 48, strong, bars=8)
    a3 = _line(SAR_A, bar, 0.64, 72, strong, bars=8)
    harm = (_harm(SAR_HA, bar, 0, 8) + _harm(SAR_HA, bar, 24, 8) + _harm(SAR_HB, bar, 48, 8)
            + _harm(SAR_HA, bar, 72, 8))
    bass = _bass_line(harm, "F2", "D3", "D3")
    voic = _voicings(harm, 3, "F3", "C5", bass, _shift(a1, -12) + a2 + b + _shift(a3, -12))
    # the flute's descant over the last A: long notes above the viol's tune
    jb, j3 = _idx(harm, 48, 72), _idx(harm, 72, 96)
    desc = _voicings(_pick(harm, j3), 1, "D5", "A5", _pick(bass, j3), top=_shift(a3, -12), above=True)
    # who sings: the treble viol low (A), the flute (A', the viol a tenth below it), the flute
    # high (B), the viol again with the flute's descant (A'')
    vla = _shift(a1, -12, 1.05) + _shift(_second(a2, harm, D_MINOR, 1.0, 0.82, bass), -12) + _shift(a3, -12, 1.05)
    vla += _held(_pick(harm, jb), [voic[j][1] for j in jb], 0.44)
    fl = a2 + b + _held(_pick(harm, j3), [v[0] for v in desc], 0.42)
    # the harp: quavers rising and falling through the chord (A, A', A''); in B the chord
    # rolled on the first beat and a single string on the leaning second
    harp: List[Ev] = []
    for j, ((s, Lc, nm), bp, v) in enumerate(zip(harm, bass, voic)):
        if 48 - 1e-6 <= s < 72 - 1e-6:
            harp += _roll(s, [bp] + list(v), Lc + 0.2, 0.42, 0.05)
            harp.append((s + 1, Lc - 0.9, v[2] + 12 if v[2] + 12 <= _m("A5") else v[2], 0.4, ""))
        else:
            harp += _arp([(s, Lc, nm)], [bp], [v], 0.5, (-1, 0, 1, 2, 1, 0), 0.38)
    # the bass viol: the ground, held through each bar; in A' it steps down to the fifth on
    # the third beat (not under the A chord, whose fifth would double the tune)
    cello: List[Ev] = []
    for j, ((s, Lc, nm), bp) in enumerate(zip(harm, bass)):
        if 24 - 1e-6 <= s < 48 - 1e-6 and Lc >= 3 - 1e-6 and _chord(nm)[0] != 9:
            cello += [(s, 2.0, bp, 0.5, ""), (s + 2, 1.0, bp - 5 if bp - 5 >= _m("E2") else bp + 7, 0.42, "")]
        else:
            cello.append((s, Lc, bp, 0.5, ""))
    cello = [(s, Lc, p, v, sh) for s, Lc, p, v, sh in _merge_ties(cello)]
    # a muffled drum from the B strain on: the sarabande's two beats
    drum = _drums([(0.0, "low_floor_tom", 0.36), (1.0, "low_floor_tom", 0.46)], range(16, 32), bar)
    parts = [
        Part("viola", _notes(VIOLA, vla, u, L, 31, legato=0.95, swell_min=1.5, swell=(104, 124), pan=PAN["viola"],
                             tune=True), -21.0, "musescore", _viola_tone),
        Part("flute", _notes(FLUTE, fl, u, L, 32, legato=0.95, swell_min=1.5, pan=PAN["flute"], tune=True), -21.5,
             "musescore", _band(240, 8500), 1.1),
        Part("harp", _notes(HARP, harp, u, L, 33, jitter=0.006, legato=1.0, pan=PAN["harp"]), -22.5, "musescore",
             _harp_tone, 1.2),
        Part("cello", _notes(CELLO, cello, u, L, 34, legato=0.97, swell_min=1.5, swell=(100, 122), pan=PAN["cello"],
                             tune=True), -24.5, "musescore", _cello_tone, 0.6),
        Part("drum", _notes(DRUM, drum, u, L, 35, jitter=0.004, pan=PAN["tabor"], kit="brush"), -32.0, "fluid",
             _band(60, 3000), 0.6),
    ]
    return _mixdown(parts, L, size=0.68, wet=0.34)


def _merge_ties(evs: List[Ev]) -> List[Ev]:
    """Join a note to the one before when it is the same pitch straight after (a held bow)."""
    out: List[Ev] = []
    for e in sorted(evs, key=lambda e: e[0]):
        if out and out[-1][2] == e[2] and abs(out[-1][0] + out[-1][1] - e[0]) < 1e-6:
            q = out[-1]
            out[-1] = (q[0], q[1] + e[1], q[2], q[3], q[4])
        else:
            out.append(e)
    return out


# ============================================================================= king: The King's Procession
KING_BPM = 72.0
KING_BEATS = 24 * 4
KING_UNIT = music.aac_unit(60.0 / KING_BPM, KING_BEATS)
KING_LOOP = KING_BEATS * KING_UNIT

# the theme in D minor on the horns
KING_A = ("D4:2 A4:2 | G4:1.5 F4:0.5 E4:2 | F4:2 E4:1 D4:1 | E4:1 D4:1 C#4:2 | "
          "D4:2 A4:2 | Bb4:1.5 A4:0.5 G4:1 F4:1 | E4:2 D4:1 C#4:1 | D4:4> |")
KING_HA = "Dm:4 | Gm:2 A:2 | Dm:2 C:1 Bb:1 | Asus4:2 A:2 | Dm:2 Dm/F:2 | Gm:2 C:1 Dm:1 | C:2 Asus4:1 A:1 | Dm:4 |"
# the last time, the close turned to A so the procession goes round again
KING_A3 = ("D4:2 A4:2 | G4:1.5 F4:0.5 E4:2 | F4:2 E4:1 D4:1 | E4:1 D4:1 C#4:2 | "
           "D4:2 A4:2 | Bb4:1.5 A4:0.5 G4:1 F4:1 | E4:2 D4:1 C#4:1 | E4:4< |")
KING_HA3 = "Dm:4 | Gm:2 A:2 | Dm:2 C:1 Bb:1 | Asus4:2 A:2 | Dm:2 Dm/F:2 | Gm:2 C:1 Dm:1 | C:2 Asus4:1 A:1 | A:4 |"
# the middle: a chromatic lament in the bass, twice, the choir's top line over it; the horns
# call the theme's fifth the second time
KING_HB = ("Dm:2 A/C#:2 | C:2 G/B:2 | Gm/Bb:2 A:2 | Dm:2 A:2 | Dm:2 A/C#:2 | Am/C:2 G/B:2 | Gm/Bb:2 A:2 | A:4 |")
KING_B_TOP = "A4:4 | G4:4 | G4:2 A4:2 | F4:2 E4:2 | F4:2 E4:2 | E4:2 D4:2 | D4:2 E4:2 | E4:4 |"
KING_B_CALL = "r:4 | r:4 | r:4 | r:4 | D4:2 A4:2 | A4:2 G4:2 | G4:2 E4:2 | r:4 |"


def _timp_roll(start: float, beats: float, key: int, v0: float, v1: float, unit: float, seed: int) -> List[Ev]:
    """A timpani roll: single strokes about 14 a second, unevenly spaced and weighted as two
    sticks are, growing from ``v0`` to ``v1``."""
    rng = np.random.default_rng(seed)
    out: List[Ev] = []
    t = 0.0
    k = 0
    while t < beats * unit - 0.03:
        v = v0 + (v1 - v0) * t / (beats * unit)
        v *= (1.0 if k % 2 == 0 else 0.88) * rng.uniform(0.9, 1.08)
        out.append((start + t / unit, 0.08 / unit, key, float(np.clip(v, 0.05, 1.0)), ""))
        t += rng.uniform(0.062, 0.082)
        k += 1
    return out


def _procession() -> np.ndarray:
    bar = 4.0
    u, L = KING_UNIT, KING_LOOP
    a1 = _line(KING_A, bar, 0.62, 0, (2.0,), bars=8)
    a3 = _line(KING_A3, bar, 0.7, 64, (2.0,), bars=8)
    top = _line(KING_B_TOP, bar, 0.5, 32, bars=8)
    call = _line(KING_B_CALL, bar, 0.6, 32, bars=8)
    harm = _harm(KING_HA, bar, 0, 8) + _harm(KING_HB, bar, 32, 8) + _harm(KING_HA3, bar, 64, 8)
    nA = len(_harm(KING_HA, bar))
    nB = len(_harm(KING_HB, bar))
    bass = _bass_line(harm, "F2", "E3", "D3")
    for j, (s, Lc, nm) in enumerate(harm):                 # the lament's descent stays stepwise
        if 32 - 1e-6 <= s < 64 - 1e-6:
            bass[j] = {"Dm": _m("D3"), "A/C#": _m("C#3"), "C": _m("C3"), "Am/C": _m("C3"), "G/B": _m("B2"),
                       "Gm/Bb": _m("Bb2"), "A": _m("A2")}[nm]
    # the sackbuts: two inner voices, held, under the horns (A and the last A)
    sack_h = harm[:nA] + harm[nA + nB:]
    sack_b = bass[:nA] + bass[nA + nB:]
    sack_v = _voicings(sack_h, 2, "D3", "D4", sack_b, a1 + a3)
    sack = _held(sack_h, [v[0] for v in sack_v], 0.46) + _held(sack_h, [v[1] for v in sack_v], 0.46)
    # the choir: four voices over the lament (the top line given), then three held above
    # the horns in the last A
    hb, bb = harm[nA:nA + nB], bass[nA:nA + nB]
    ch_b = _voicings(hb, 2, "F3", "D4", bb, top)
    ch3 = _voicings(harm[nA + nB:], 3, "D4", "E5", bass[nA + nB:], a3, above=True)
    choir = top[:]
    for k in range(2):
        choir += _held(hb, [v[k] for v in ch_b], 0.44)
    for k in range(3):
        choir += _held(harm[nA + nB:], [v[k] for v in ch3], 0.42)
    # the treble viol doubles the choir's lower voice in the lament
    vla = _held(hb, [v[0] for v in ch_b], 0.46)
    # low strings: the bass viol treads in crotchets in the A sections and bows the lament
    # long; the double bass holds the bass an octave down, on the minims
    cello: List[Ev] = []
    dbass: List[Ev] = []
    for j, ((s, Lc, nm), bp) in enumerate(zip(harm, bass)):
        if 32 - 1e-6 <= s < 64 - 1e-6:
            cello.append((s, Lc, bp, 0.5, ""))
            dbass.append((s, Lc, bp - 12, 0.46, ""))
        else:
            t = s
            while t < s + Lc - 1e-6:
                beat = round(t % bar, 6)
                cello.append((t, 0.62, bp, 0.5 if beat == 0 else (0.44 if beat == 2 else 0.38), ""))
                t += 1.0
            dbass.append((s, Lc, bp - 12, 0.46, ""))
    cello_tread = [e for e in cello if e[1] < 1]
    cello_bow = _merge_ties([e for e in cello if e[1] >= 1])
    dbass = _merge_ties(dbass)
    # the harp: a rolled chord on each downbeat (and the third beat in the last A)
    harp: List[Ev] = []
    hv = _voicings(harm, 3, "A3", "A4", bass, None)
    for j, ((s, Lc, nm), bp, v) in enumerate(zip(harm, bass, hv)):
        if s % bar < 1e-6 or Lc >= 2:
            harp += _roll(s, [bp] + list(v), min(Lc, 2.0) + 0.4, 0.46 if s % bar < 1e-6 else 0.38, 0.05)
    # timpani on D and A: the procession's two strokes a bar, rolls into the lament and
    # into the return
    d2, a2 = _m("D2"), _m("A2")
    timp: List[Ev] = []
    def drum_for(t: float) -> Optional[int]:
        """D or A, whichever is in the chord (its root first); none under a chord with neither."""
        root, pcs, _ = _chord(_chord_at(harm, t))
        for pc in sorted({2, 9} & set(pcs), key=lambda k: k != root):
            return d2 if pc == 2 else a2
        return None

    for bnum in range(24):
        s = bnum * bar
        if bnum in (15, 23):
            timp += [(s, 0.5, a2, 0.5, "")] + _timp_roll(s + 1.0, 2.75, a2, 0.18, 0.5 if bnum == 15 else 0.6, u, 70 + bnum)
            continue
        hits = [(s, 0.36 if 8 <= bnum < 16 else (0.5 if bnum >= 16 else 0.44))]
        if not 8 <= bnum < 16:
            hits.append((s + 2, 0.3))
        for t, v in hits:
            k = drum_for(t)
            if k is not None:
                timp.append((t, 0.5, k, v, ""))
    horn = a1 + call + a3
    parts = [
        Part("horn", _notes(HORN, horn, u, L, 41, legato=0.94, swell_min=1.5, swell=(104, 122), pan=PAN["horn"],
                            tune=True), -20.5, "fluid", lambda x: _steady(_band(90, 8000)(x)), 1.0),
        Part("sackbut", _notes(SACKBUT, sack, u, L, 42, legato=0.96, swell_min=2, swell=(96, 116), pan=PAN["sackbut"],
                               tune=True), -26.0, "musescore", _band(80, 7000), 0.9),
        Part("choir", _notes(CHOIR, choir, u, L, 43, legato=0.98, swell_min=2, swell=(100, 122), pan=PAN["choir"]),
             -24.0, "musescore", _band(170, 10000), 1.2),
        Part("viola", _notes(VIOLA, vla, u, L, 44, legato=0.97, swell_min=2, swell=(100, 120), pan=PAN["viola"], tune=True),
             -28.0, "musescore", _viola_tone),
        Part("cello tread", _notes(CELLO, cello_tread, u, L, 45, jitter=0.006, pan=PAN["cello"], tune=True), -25.5,
             "musescore", _cello_tone, 0.5),
        Part("cello bow", _notes(CELLO, cello_bow, u, L, 46, legato=0.97, swell_min=2, swell=(100, 122), pan=PAN["cello"],
                                 tune=True), -25.5, "musescore", _cello_tone, 0.5),
        Part("double bass", _notes(BASS, dbass, u, L, 47, legato=0.97, swell_min=2, swell=(96, 116), pan=PAN["bass"],
                                   tune=True), -29.5, "musescore", _band(38, 2500), 0.3),
        Part("harp", _notes(HARP, harp, u, L, 48, jitter=0.006, legato=1.0, pan=PAN["harp"]), -25.0, "musescore",
             _harp_tone, 1.1),
        Part("timpani", _notes(TIMPANI, timp, u, L, 49, jitter=0.004, legato=1.0, pan=PAN["timpani"]), -27.0,
             "musescore", _band(45, 4000), 0.8),
    ]
    return _mixdown(parts, L, size=0.78, wet=0.36, damping=0.45)


# ============================================================================= the candidates
CANDIDATES = [
    Candidate("music", "court_menu", "Candlelit Pavane",
              "For the menus: a slow, stately court dance in a major key; a recorder and then a flute sing "
              "the suite's theme over a softly plucked harp and two bowed viols, with no drums.",
              _pavane, tags=["menu"], loop_seconds=MENU_LOOP, bpm=round(60.0 / MENU_UNIT, 3)),
    Candidate("music", "court_jack", "The Jack's Galliard",
              "For the Jacks: the same theme as a bright, leaping court dance in three, played by recorder, "
              "flute and viols over a harpsichord and harp, with a soft tabor and tambourine.",
              _galliard, tags=["jack"], loop_seconds=JACK_LOOP, bpm=round(60.0 / JACK_UNIT, 3)),
    Candidate("music", "court_queen", "The Queen's Sarabande",
              "For the Queens: a slow, elegant but uneasy minor-key dance over a falling bass line, the "
              "theme on a viola and then a flute over a rippling harp, a muffled drum joining halfway.",
              _sarabande, tags=["queen"], loop_seconds=QUEEN_LOOP, bpm=round(60.0 / QUEEN_UNIT, 3)),
    Candidate("music", "court_king", "The King's Procession",
              "For the Kings: a grand, tense procession in a minor key; horns and trombones carry the theme over "
              "marching low strings and timpani, a choir sings a darkening middle section, and everyone joins for the climax.",
              _procession, tags=["king"], loop_seconds=KING_LOOP, bpm=round(60.0 / KING_UNIT, 3)),
]
