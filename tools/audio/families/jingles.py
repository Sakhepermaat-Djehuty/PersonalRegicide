"""Jingles: victory, loss and mission start (five candidates each), all played by real,
recorded instruments.

Every note here is a real instrument recording from the General MIDI banks (``sf.py``:
FluidR3 and MuseScore General, both MIT), played from a score, then mixed by loudness,
put in a stone hall's reverb and shaped to fade naturally. There is no oscillator, no
pulse wave, nothing modelled: the old 8-bit candidates are gone (the owner's pick
"Ready, go!" is now a herald's trumpet and a field drum).

The five candidates of each event come from five matching sets, so the owner can pick
one set for all three events (or mix freely):

  royal       the castle's brass: trumpets, French horns, trombones, a tuba, kettle drums
              and a field drum
  tavern      a lute (a nylon-strung guitar, its paired courses made by doubling every
              note a few cents apart), a recorder, a fiddle, a hand drum and a tambourine
  enchanted   a harp, glockenspiel, celesta and a tubular bell
  orchestral  a string section with solo violin, cello and double bass, and timpani
  chapel /    church bells (tubular bells) and a choir; the mission start's fifth is the
  herald      herald: a trumpet call and a field drum ("Ready, go!")

All in D: victory and mission start in D major (cadences IV-V-I, 2-7-1 and V-I), the
losses in D dorian (D E F G A B C: a dorian amen G-Dm, the folk C-Dm close, the cello's
sigh F-E onto the fifth). Every loss is slow and soft, never a "wah-wah" joke.

How it is made:
  - each part is rendered from the bank whose recording suits it (the banks share most
    samples; where they differ, the cello, double bass, strings, choir, tubular bells and
    timpani, the better one is used), with small seeded timing and velocity variations,
    as real players have;
  - a section or a lute's paired course is the same recording doubled a few cents and a
    few milliseconds apart (``_double``), so it sounds like several players, not one;
  - the banks' notes start a few milliseconds late: the finished jingle is cut to its first
    sound (``sf.onset``), so it starts at once;
  - parts are balanced by loudness (gated RMS, as the build measures it), sent through one
    hall reverb, kept below ~7.5 kHz (no hiss, no sizzle), and faded naturally to silence
    well inside the event's length limit.
Everything is seeded, so each rebuild is identical.
"""
from __future__ import annotations

import dataclasses
import functools
import math
from typing import List, Sequence, Tuple, Union

import numpy as np

import sf
import synth as A
from catalog import EVENT_BY_ID, Candidate
from sf import DRUM, GM, Note

SR = A.SR
Pitch = Union[str, int]
Seq = Sequence[Tuple[float, float, Pitch, float]]     # (beat, length in beats, pitch, velocity 0..1)


# ----------------------------------------------------------------------------- basics
def _n(s: float) -> int:
    return int(round(s * SR))


def _peak(x: np.ndarray) -> float:
    return float(np.max(np.abs(x))) if len(x) else 0.0


def _endfade(x: np.ndarray, sec: float) -> np.ndarray:
    """A raised-cosine fade over the last ``sec`` seconds, so a buffer always ends at 0."""
    k = min(len(x), _n(sec))
    if k < 2:
        return x
    y = x.copy()
    y[-k:] *= 0.5 + 0.5 * np.cos(np.pi * np.linspace(0.0, 1.0, k))
    return y


def _mix(*parts: Tuple[np.ndarray, float]) -> np.ndarray:
    n = max(len(x) for x, _ in parts)
    out = np.zeros(n)
    for x, g in parts:
        out[:len(x)] += g * x
    return out


def _delay(x: np.ndarray, sec: float) -> np.ndarray:
    return np.concatenate([np.zeros(_n(sec)), x]) if sec > 0 else x


def _loud(x: np.ndarray) -> float:
    """The build's loudness measure (gated RMS of 50 ms blocks)."""
    return A._rms_db(x)


def _at(x: np.ndarray, db: float) -> np.ndarray:
    """Scale a part to a loudness, so parts are balanced by how loud they sound."""
    return x * 10 ** ((db - _loud(x)) / 20.0)


def _verb(x: np.ndarray, room: float, wet: float, damping: float = 0.5, tail: float = 2.0) -> np.ndarray:
    return A.reverb(x, room=room, wet=wet, damping=damping, width=1.0, tail=tail)


def _glue(x: np.ndarray, crest_db: float = 14.0, release: float = 0.05) -> np.ndarray:
    """Hold the peaks to ``crest_db`` above the loudness with a smooth, look-ahead gain
    (only the tallest transients move), so the master's limiter barely has to act."""
    thr = 10 ** ((_loud(x) + crest_db) / 20.0)
    if _peak(x) <= thr:
        return x
    return A.limit(x / thr, 0.0, lookahead=0.004, release=release) * thr


def _finish(x: np.ndarray, event: str, max_s: float, fade: float = 0.6, hp: float = 70.0,
            lp: float = 7500.0, crest_db: float = 14.0) -> np.ndarray:
    """Start at the first sound (the banks' latency cut), remove sub-bass, keep the top
    below ``lp``, cut at ``max_s`` (well inside the event's limit) with a long fade so the
    tail dies away naturally, and glue the peaks."""
    ev = EVENT_BY_ID[event]
    max_s = min(max_s, ev.max_seconds - 0.05)
    y = x[sf.onset(x, -50.0):]
    y = A.highpass(y, hp, 2)
    if lp:
        y = A.lowpass(y, lp, 4)
    n = _n(max_s)
    if len(y) > n:
        y = y[:n]
    y = _endfade(y, min(fade, len(y) / SR * 0.5))
    # the very first samples rise from zero in under a millisecond (no click)
    k = min(len(y), 24)
    y[:k] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(k) / k)
    return _glue(y, crest_db)


# ----------------------------------------------------------------------------- the banks
@functools.lru_cache(maxsize=None)
def _bank_cached(key: tuple, seconds: float, bank: str) -> np.ndarray:
    return sf.render([Note(*k) for k in key], seconds, bank=bank)


def _r(notes: Sequence[Note], seconds: float, bank: str = "fluid") -> np.ndarray:
    """Render notes from a bank (cached). The bank's latency is kept here, the same for
    every part, so parts stay in time; ``_finish`` cuts it once from the whole jingle."""
    key = tuple(dataclasses.astuple(n) for n in notes)
    return _bank_cached(key, round(float(seconds), 4), bank).copy()


def _play(program: int, seq: Seq, beat: float, at: float = 0.0, seed: int = 0, jitter: float = 0.005,
          vel: float = 1.0, legato: float = 1.0, **kw) -> List[Note]:
    """A part as bank notes: ``seq`` in beats (velocity 0..1), started at ``at`` seconds.
    Every note but a downbeat at 0 is nudged by up to ``jitter`` seconds and its velocity
    by a few percent (seeded), as a player would."""
    rng = np.random.default_rng(seed)
    out = []
    for i, (b, L, p, v) in enumerate(seq):
        dt = 0.0 if (b == 0 and at == 0) else rng.uniform(-jitter, jitter)
        v127 = int(np.clip(round(127 * v * vel * rng.uniform(0.95, 1.03)), 1, 127))
        out.append(Note(program, p, max(0.0, at + b * beat + dt), max(0.03, L * beat * legato), vel=v127, **kw))
    return out


def _chord(pitches: Sequence[Pitch], b: float, L: float, v: float, spread: float = 0.0) -> List[tuple]:
    """A chord as seq entries; ``spread`` (beats) rolls it from the lowest note up."""
    return [(b + i * spread, L, p, v) for i, p in enumerate(pitches)]


def _double(x: np.ndarray, cents: float = 6.0, delay: float = 0.012, gain: float = 0.7) -> np.ndarray:
    """A second player: the same recording a few cents apart (resampled) and a few
    milliseconds late. A lute's paired course, a section of two."""
    r = 2 ** (cents / 1200.0)
    m = int(len(x) / r)
    y = np.interp(np.arange(m) * r, np.arange(len(x)), x)
    return _mix((x, 1.0), (_delay(y, delay), gain)) / math.sqrt(1.0 + gain * gain)


def _lute_body(x: np.ndarray) -> np.ndarray:
    """The guitar played as a lute: a little less boom, a wooden bowl near 280 Hz and a
    gentle nasal presence; the top softened like gut strings under a fingertip."""
    y = A.highpass(x, 90, 2)
    y = A.peak_eq(y, 280, 3.0, 1.2)
    y = A.peak_eq(y, 1100, 1.5, 1.4)
    return A.lowpass(y, 5500, 2)


def _glock(notes: Sequence[Tuple[float, Pitch, float]], seconds: float) -> np.ndarray:
    """A glockenspiel (time, pitch, velocity 0..1) played with soft mallets: in these
    recordings most of a bar's energy is one piercing partial between 6 and 7.5 kHz, so
    the top is taken off above 4.5 kHz (the fundamental and the warm 2.76x partial ring
    on) and a celesta doubles each note for a rounder, sweeter ring."""
    gl = _r([Note(GM["glockenspiel"], p, tt, 0.8, vel=int(127 * v)) for tt, p, v in notes], seconds, "fluid")
    gl = A.lowpass(gl, 4500, 4)
    cel = _r([Note(GM["celesta"], p, tt, 0.6, vel=int(100 * v)) for tt, p, v in notes], seconds, "fluid")
    return _mix((_at(gl, -21), 1.0), (_at(cel, -23), 1.0))


# ============================================================================= VICTORY
def _victory_royal() -> np.ndarray:
    """Trumpets call (a triplet pickup, the tonic, then IV and V rising into a long D
    major chord); horns and trombones fill the chords; timpani roll in, mark the
    harmony, roll under the last chord and close it with one stroke."""
    b = 0.42
    T = 1.0 / 3.0
    s = 0.85                                   # short notes are detached
    rhythm = [(0, T * s), (T, T * s), (2 * T, T * s), (1, 0.9), (2, 0.45), (2.5, 0.45),
              (3, T * 0.9), (3 + T, T * 0.9), (3 + 2 * T, T * 0.9), (4, 2.5)]
    top = ["A4", "A4", "A4", "D5", "B4", "D5", "E5", "F#5", "G5", "A5"]
    sec = ["F#4", "F#4", "F#4", "A4", "G4", "B4", "C#5", "D5", "E5", "F#5"]
    vel = [0.72, 0.66, 0.78, 0.9, 0.78, 0.84, 0.78, 0.84, 0.88, 0.92]
    tp1 = _r(_play(GM["trumpet"], [(bb, L, p, v) for (bb, L), p, v in zip(rhythm, top, vel)], b, seed=1,
                   jitter=0.004), 4.4)
    tp2 = _r(_play(GM["trumpet"], [(bb, L, p, v * 0.9) for (bb, L), p, v in zip(rhythm, sec, vel)], b, seed=2,
                   jitter=0.006), 4.4, "musescore")
    trumpets = _mix((_double(tp1, 7.0, 0.011, 0.55), 1.0), (_double(tp2, -6.0, 0.014, 0.5), 0.8))
    hn = (_chord(["A3", "D4"], 0, 0.95, 0.62) + _chord(["D4", "F#4"], 1, 0.95, 0.76)
          + _chord(["B3", "D4"], 2, 0.95, 0.76) + _chord(["C#4", "E4"], 3, 0.95, 0.8)
          + _chord(["D4", "A4"], 4, 2.6, 0.9))
    horns = _double(_r(_play(GM["french_horn"], hn, b, seed=3), 4.4, "musescore"), -5.0, 0.016, 0.6)
    tb = (_chord(["D3"], 0, 0.95, 0.6) + _chord(["D3", "A3"], 1, 0.95, 0.74) + _chord(["G2", "G3"], 2, 0.95, 0.74)
          + _chord(["A2", "A3"], 3, 0.95, 0.78) + _chord(["D3", "A3"], 4, 2.6, 0.86))
    tuba = [(1, 0.95, "D2", 0.6), (2, 0.95, "G2", 0.6), (3, 0.95, "A2", 0.64), (4, 2.6, "D2", 0.7)]
    low = _r(_play(GM["trombone"], tb, b, seed=4) + _play(GM["tuba"], tuba, b, seed=5), 4.4)
    # timpani: a roll on A swelling into the downbeat, the harmony's roots, a roll under the
    # last chord and one closing stroke
    tim = [((i / 16.0) / b, 0.05, "A2", 0.3 + 0.35 * i / 13.0) for i in range(14)]
    tim += [(1, 0.3, "D3", 0.92), (3, 0.3, "A2", 0.72), (4, 0.3, "D3", 0.95)]
    tim += [(4.3 + (i / 15.0) / b, 0.05, "D3", 0.42 + 0.12 * math.sin(math.pi * i / 30.0)) for i in range(30)]
    tim += [(6.55, 0.6, "D3", 0.88)]
    timp = A.lowpass(_r(_play(GM["timpani"], tim, b, seed=6, jitter=0.004), 4.6, "fluid"), 3000, 2)
    x = _mix((_at(trumpets, -18), 1.0), (_at(horns, -22), 1.0), (_at(low, -23), 1.0), (_at(timp, -22.5), 1.0))
    x = _verb(x, room=0.8, wet=0.2, damping=0.45, tail=2.5)
    return _finish(x, "victory", 4.9, fade=1.0)


def _hand_drum(seq: Seq, beat: float, seed: int, at: float = 0.0) -> np.ndarray:
    """A hand drum played like a bodhran or a tabor: the deep stroke in the middle of the
    skin (a low tom with brushes for the boom, a low conga for the skin's ring) and the
    light tap near the rim (a muted conga). ``seq`` pitches are "doum" or "tek"."""
    notes: List[Note] = []
    for i, (b, L, p, v) in enumerate(seq):
        if p == "doum":
            notes += _play(DRUM, [(b, 0.1, "low_floor_tom", v * 0.85)], beat, at, seed + i, kit="brush")
            notes += _play(DRUM, [(b, 0.1, "low_conga", v * 0.8)], beat, at, seed + 50 + i, jitter=0.0015,
                           kit="brush")
        else:
            notes += _play(DRUM, [(b, 0.1, "mute_conga", v * 0.75)], beat, at, seed + i, kit="brush")
    end = max(n.start for n in notes) + 0.8
    y = _r(notes, end, "fluid")
    y = A.peak_eq(y, 120, -3.0, 1.0)            # less boom: a frame drum, not a kick drum
    return A.lowpass(y, 5000, 2)


def _tambourine(seq: Seq, beat: float, seed: int, at: float = 0.0) -> np.ndarray:
    """A tambourine (its jingles taken down above 7 kHz: bright but not sizzling)."""
    y = _r(_play(DRUM, seq, beat, at, seed, jitter=0.004), max(n[0] for n in seq) * beat + at + 1.0, "fluid")
    return A.lowpass(A.highpass(y, 300, 2), 7000, 4)


def _victory_tavern() -> np.ndarray:
    """A jig in 6/8: the recorder climbs the D chord and comes home through G and A, a
    fiddle joins it an octave down; the lute plays bass and chord ('oom-pa'); a hand
    drum keeps the lilt and a tambourine shakes on the off-beat; a rolled D chord ends it."""
    e = 0.15
    tune = [(0, 1, "D5", 0.8), (1, 1, "F#5", 0.8), (2, 1, "A5", 0.85), (3, 2, "D6", 0.88), (5, 1, "A5", 0.76),
            (6, 2, "B5", 0.86), (8, 1, "G5", 0.76), (9, 1, "E5", 0.78), (10, 1, "F#5", 0.78), (11, 1, "G5", 0.8),
            (12, 1, "A5", 0.84), (13, 1, "G5", 0.76), (14, 1, "E5", 0.78), (15, 2, "C#5", 0.82), (17, 1, "E5", 0.78)]
    rec = _r(_play(GM["recorder"], [(bb, L * 0.85, p, v) for bb, L, p, v in tune] + [(18, 5.0, "D5", 0.86)], e,
                   seed=21, jitter=0.004), 4.6)
    fid_seq = [(bb, L * 0.8, A.midi(p) - 12, v * 0.9) for bb, L, p, v in tune] + [(18, 4.5, "D4", 0.8)]
    fiddle = _r(_play(GM["fiddle"], fid_seq, e, seed=22, jitter=0.006), 4.6)
    lute = []
    for bar, (bass, ch) in enumerate([("D3", ["F#3", "A3", "D4"]), ("G2", ["G3", "B3", "D4"]),
                                       ("A2", ["G3", "C#4", "E4"])]):
        lute.append((bar * 6, 2.6, bass, 0.8))
        lute += _chord(ch, bar * 6 + 3, 2.4, 0.56, spread=0.07)
    lute += [(18 + j * 0.16, 9, p, 0.82 - 0.03 * j) for j, p in enumerate(["D2", "D3", "A3", "D4", "F#4", "A4"])]
    lute_x = _lute_body(_double(_r(_play(GM["nylon_guitar"], lute, e, seed=23), 5.2), 4.0, 0.006, 0.6))
    drum = _hand_drum([(k, 1, "doum" if k % 3 == 0 else "tek",
                        (0.9 if k % 6 == 0 else 0.62) if k % 3 == 0 else (0.38 if k % 3 == 2 else 0.0))
                       for k in range(18) if k % 3 != 1] + [(18, 1, "doum", 1.0)], e, 30)
    tamb = _tambourine([(k, 1, "tambourine", 0.55) for k in (3, 9, 15)] + [(18, 1, "tambourine", 0.7)], e, 31)
    x = _mix((_at(rec, -18.5), 1.0), (_at(fiddle, -24), 1.0), (_at(lute_x, -21), 1.0), (_at(drum, -24), 1.0),
             (_at(tamb, -30), 1.0))
    x = _verb(x, room=0.42, wet=0.14, damping=0.55, tail=1.5)
    return _finish(x, "victory", 4.9, fade=1.1)


def _victory_bells() -> np.ndarray:
    """A harp sweeps up the pentatonic scale; the glockenspiel answers with the D chord
    and a 2-7-1 turn (E, C#, D) over A then D chords on the harp; a tubular bell and two
    celesta twinkles ring out."""
    harp = []
    for i, p in enumerate(["D3", "E3", "F#3", "A3", "B3", "D4", "E4", "F#4", "A4", "B4", "D5", "E5", "F#5"]):
        harp.append(Note(GM["harp"], p, i * 0.034, 1.2, vel=int(62 + 3 * i)))
    for i, p in enumerate(["A2", "E3", "A3", "C#4", "E4"]):
        harp.append(Note(GM["harp"], p, 1.05 + i * 0.025, 0.6, vel=78))
    for i, p in enumerate(["D2", "A2", "D3", "F#3", "A3", "D4", "F#4", "A4"]):
        harp.append(Note(GM["harp"], p, 1.5 + i * 0.03, 2.5, vel=int(100 - 3 * i)))
    harp_x = _r(harp, 5.0, "musescore")
    glock = _glock([(0.47, "F#5", 0.7), (0.62, "A5", 0.74), (0.77, "D6", 0.84), (1.07, "E6", 0.78),
                    (1.25, "C#6", 0.72), (1.50, "D6", 0.95), (1.50, "A5", 0.5)], 5.0)
    cel = _r([Note(GM["celesta"], "A6", 1.78, 0.6, vel=60), Note(GM["celesta"], "D7", 1.95, 0.6, vel=52)],
             5.0, "fluid")
    bell = _r([Note(GM["tubular_bells"], "D5", 1.5, 2.0, vel=70)], 5.0, "fluid")
    x = _mix((_at(harp_x, -21), 1.0), (_at(glock, -20), 1.0), (_at(cel, -29), 1.0), (_at(bell, -27), 1.0))
    x = _verb(x, room=0.8, wet=0.25, damping=0.5, tail=2.5)
    return _finish(x, "victory", 4.6, fade=1.2)


def _victory_strings() -> np.ndarray:
    """The violins rush up a scale into three bowed chords, IV, V and a long I that
    swells and is let go, with the cellos and basses underneath and the timpani on each
    chord."""
    run = [(0.0, "D5"), (0.07, "E5"), (0.14, "F#5"), (0.21, "G5"), (0.28, "A5")]
    vln = []
    for i, (tt, p) in enumerate(run):
        v = int(78 + 7 * i)
        vln.append(Note(GM["violin"], p, tt, 0.08, vel=v))
        vln.append(Note(GM["violin"], A.midi(p) - 12, tt + 0.004, 0.08, vel=v - 10))
    run_x = _double(_r(vln, 1.2, "musescore"), 8.0, 0.009, 0.7)
    chords = [(0.35, 0.3, ["G2", "G3", "D4", "B4", "G5", "B5"], 0.82),
              (0.75, 0.3, ["A2", "A3", "E4", "C#5", "A5", "C#6"], 0.86),
              (1.15, 2.0, ["D2", "D3", "A3", "F#4", "D5", "A5", "D6"], 0.92)]
    sect, solo = [], []
    for tt, L, ps, v in chords:
        for p in ps:
            sect.append(Note(GM["strings"], p, tt, L, vel=int(127 * v)))
        # the solo violin and cello on top of each chord give it a quick, biting attack
        solo.append(Note(GM["violin"], ps[-1], tt, L * 0.9, vel=int(120 * v)))
        solo.append(Note(GM["cello"], ps[1], tt, L * 0.9, vel=int(120 * v)))
    body = _mix((_double(_r(sect, 4.4, "fluid"), 7.0, 0.013, 0.6), 1.0), (_r(sect, 4.4, "musescore"), 0.6))
    solo_x = _r(solo, 4.4, "musescore")
    timp = A.lowpass(_r([Note(GM["timpani"], "G2", 0.35, 0.3, vel=88), Note(GM["timpani"], "A2", 0.75, 0.3, vel=94),
                         Note(GM["timpani"], "D3", 1.15, 0.3, vel=108)]
                        + [Note(GM["timpani"], "D3", 1.45 + i / 15.0, 0.05, vel=int(48 + 10 * math.sin(math.pi * i / 22)))
                           for i in range(22)], 4.4, "fluid"), 3000, 2)
    x = _mix((_at(run_x, -20), 1.0), (_at(body, -18.5), 1.0), (_at(solo_x, -22), 1.0), (_at(timp, -23), 1.0))
    x = _verb(x, room=0.75, wet=0.22, damping=0.5, tail=2.0)
    return _finish(x, "victory", 4.4, fade=0.9)


def _victory_bell_tower() -> np.ndarray:
    """Church bells ring rounds down the D pentatonic scale, then a change (the pairs
    swapped, as bell-ringers do), and all ring together on a D chord while a choir
    swells in on a bright 'Ah' and a concert bass drum gives the moment its weight."""
    rounds = ["D6", "B5", "A5", "F#5", "E5", "D5"]
    change = ["B5", "D6", "F#5", "A5", "D5", "E5"]
    gap = 0.17
    bells = []
    for i, p in enumerate(rounds):
        bells.append(Note(GM["tubular_bells"], p, i * gap, 0.6, vel=int(92 - 2 * i)))
    for i, p in enumerate(change):
        bells.append(Note(GM["tubular_bells"], p, 6 * gap + 0.08 + i * gap, 0.6, vel=int(86 - 2 * i)))
    fin = 12 * gap + 0.2
    for i, p in enumerate(["D5", "A5", "D6"]):
        bells.append(Note(GM["tubular_bells"], p, fin + i * 0.012, 1.2, vel=104 - 6 * i))
    bell_x = _r(bells, 6.0, "musescore")
    choir = [Note(GM["choir"], p, 0.55, fin + 1.6 - 0.55, vel=88, swell=(45, 120))
             for p in ["D3", "A3", "D4", "F#4", "A4", "D5"]]
    choir_x = _r(choir, 6.0, "fluid")
    drum = _r([Note(DRUM, "kick", fin, 0.4, vel=95, kit="orchestra")], 6.0, "fluid")
    drum = A.lowpass(drum, 2500, 2)
    x = _mix((_at(bell_x, -19), 1.0), (_at(choir_x, -22.5), 1.0), (_at(drum, -27), 1.0))
    x = _verb(x, room=0.88, wet=0.28, damping=0.45, tail=2.5)
    return _finish(x, "victory", 5.2, fade=1.6)


# ============================================================================= LOSS
def _loss_royal() -> np.ndarray:
    """A soft horn chorale: D minor, C, G (the dorian major IV), back to D minor, the top
    horn holding its G over the G chord and sighing down to F; the trombones and a tuba
    underneath, and a muffled kettle drum rolling quietly at the end."""
    b = 0.58
    sop = [(0, 1.5, "A4", 0.6), (1.5, 2.5, "G4", 0.6)]
    alt = [(0, 1.5, "F4", 0.54), (1.5, 1.0, "E4", 0.54), (2.5, 1.0, "D4", 0.54)]
    ten = [(0, 1.5, "D4", 0.54), (1.5, 1.0, "C4", 0.54), (2.5, 1.0, "B3", 0.54)]
    bas = [(0, 1.5, "D3", 0.56), (1.5, 1.0, "C3", 0.56), (2.5, 1.0, "G2", 0.56)]
    fade = (112, 22)
    horns = (_play(GM["french_horn"], sop + alt + ten, b, seed=201, jitter=0.012)
             + [Note(GM["french_horn"], p, 4.0 * b if p == "F4" else 3.5 * b, (2.4 if p == "F4" else 2.9) * b,
                     vel=v, swell=fade) for p, v in (("F4", 74), ("D4", 68), ("A3", 68))])
    horns_x = _double(_r(horns, 5.6, "musescore"), -6.0, 0.018, 0.65)
    low = (_play(GM["trombone"], bas, b, seed=202, jitter=0.012)
           + [Note(GM["trombone"], "D3", 3.5 * b, 2.9 * b, vel=68, swell=fade),
              Note(GM["tuba"], "D2", 3.5 * b, 2.9 * b, vel=58, swell=fade)])
    low_x = _r(low, 5.6, "fluid")
    roll = [(3.5 + (i / 13.0) / b, 0.05, "D3", 0.36 - 0.24 * i / 26.0) for i in range(27)]
    timp = _r(_play(GM["timpani"], [(3.5, 0.3, "D3", 0.5)] + roll, b, seed=203, jitter=0.005), 5.6, "fluid")
    timp = A.lowpass(timp, 1200, 2)             # muffled, far away
    x = _mix((_at(horns_x, -19), 1.0), (_at(low_x, -23), 1.0), (_at(timp, -28), 1.0))
    x = _verb(x, room=0.85, wet=0.25, damping=0.55, tail=2.5)
    return _finish(x, "loss", 4.9, fade=1.1)


def _loss_tavern() -> np.ndarray:
    """A lone lute picks a D minor chord, then C, and the recorder sings A, D, F, sighs
    down through E and C and comes to rest on D over a slow rolled D minor chord."""
    e = 0.28
    lute = [(0, 4, "D3", 0.7), (1, 3, "A3", 0.56), (2, 2, "D4", 0.56), (3, 1.2, "F4", 0.52),
            (4, 4, "C3", 0.68), (5, 3, "G3", 0.54), (6, 2, "C4", 0.54), (7, 1.2, "E4", 0.5)]
    lute += [(8 + j * 0.16, 6, p, 0.7 - 0.04 * j) for j, p in enumerate(["D2", "A2", "D3", "A3", "D4", "F4"])]
    lute_x = _lute_body(_double(_r(_play(GM["nylon_guitar"], lute, e, seed=221, jitter=0.008), 5.6, "musescore"),
                                4.0, 0.006, 0.6))
    rec = [(0, 0.9, "A4", 0.58), (1, 0.9, "D5", 0.64), (2, 1.9, "F5", 0.7), (4, 1.4, "E5", 0.64),
           (5.5, 0.45, "D5", 0.58), (6, 1.9, "C5", 0.6)]
    recorder = _r(_play(GM["recorder"], rec, e, seed=222, jitter=0.01)
                  + [Note(GM["recorder"], "D5", 8 * e, 5.2 * e, vel=82, swell=(110, 12))], 5.6, "fluid")
    x = _mix((_at(recorder, -19), 1.0), (_at(lute_x, -21), 1.0))
    x = _verb(x, room=0.55, wet=0.18, damping=0.55, tail=2.0)
    return _finish(x, "loss", 5.2, fade=1.2)


def _loss_harp() -> np.ndarray:
    """A harp lets slow arpeggios fall, D minor, C, then G (the dorian IV), and comes to
    rest on a low rolled D minor chord; a celesta echoes the top notes softly, like a
    candle guttering out."""
    e = 0.24
    harp = []
    for k, ch in enumerate([["D5", "A4", "F4", "D4"], ["C5", "G4", "E4", "C4"], ["B4", "G4", "D4", "B3"]]):
        for j, p in enumerate(ch):
            harp.append((k * 4 + j, 3.5, p, 0.66 - 0.04 * j))
    harp += [(12 + j * 0.22, 6, p, 0.74 - 0.04 * j) for j, p in enumerate(["D2", "A2", "D3", "F3", "A3", "D4"])]
    harp_x = _r(_play(GM["harp"], harp, e, seed=231, jitter=0.012), 6.0, "musescore")
    cel = [(0.5, 1, "D6", 0.42), (4.5, 1, "C6", 0.4), (8.5, 1, "B5", 0.38), (13.5, 2, "A5", 0.34)]
    cel_x = _r(_play(GM["celesta"], cel, e, seed=232, jitter=0.01), 6.0, "fluid")
    x = _mix((_at(harp_x, -19), 1.0), (_at(cel_x, -27), 1.0))
    x = _verb(x, room=0.82, wet=0.26, damping=0.5, tail=2.5)
    return _finish(x, "loss", 5.3, fade=1.4)


def _loss_cello() -> np.ndarray:
    """A lone cello sings a slow lament in D dorian, A, B-A, G, F-E (the sixth sighing
    onto the fifth), and settles on a low D, over hushed strings (D minor, G, C, A minor,
    D minor) and a double bass."""
    b = 0.62
    mel = [(0, 1.0, "A3", 0.62), (1, 0.5, "B3", 0.68), (1.5, 0.5, "A3", 0.58), (2, 1.0, "G3", 0.62),
           (3, 0.5, "F3", 0.66), (3.5, 0.5, "E3", 0.56)]
    cello = _r(_play(GM["cello"], [(bb, L * 1.02, p, v) for bb, L, p, v in mel], b, seed=241, jitter=0.01)
               + [Note(GM["cello"], "D3", 4 * b, 2.3 * b, vel=80, swell=(118, 25))], 5.8, "musescore")
    ch = [(0, ["D4", "F4", "A4"], "D3"), (1, ["D4", "G4", "B4"], "G2"), (2, ["C4", "E4", "G4"], "C3"),
          (3, ["C4", "E4", "A4"], "A2")]
    pad = []
    for bb, ps, bass in ch:
        pad += [(bb, 1.0, p, 0.44) for p in ps + [bass]]
    pad_n = _play(GM["slow_strings"], pad, b, seed=242, jitter=0.0)
    pad_n += [Note(GM["slow_strings"], p, 4 * b, 2.3 * b, vel=56, swell=(110, 20)) for p in ["D3", "A3", "D4", "F4"]]
    strings = _r(pad_n, 5.8, "fluid")
    bass = _r(_play(GM["contrabass"], [(0, 1, "D2", 0.5), (1, 1, "G1", 0.5), (2, 1, "C2", 0.5), (3, 1, "A1", 0.5)],
                    b, seed=243, jitter=0.0) + [Note(GM["contrabass"], "D2", 4 * b, 2.3 * b, vel=62, swell=(110, 20))],
              5.8, "musescore")
    x = _mix((_at(cello, -19), 1.0), (_at(strings, -24), 1.0), (_at(bass, -27), 1.0))
    x = _verb(x, room=0.84, wet=0.26, damping=0.55, tail=2.5)
    return _finish(x, "loss", 5.2, fade=1.2)


def _loss_bell() -> np.ndarray:
    """A low church bell tolls three times, each softer, while a choir hums a slow dorian
    'amen' underneath: D minor, G major, D minor."""
    tolls = [Note(GM["tubular_bells"], "D4", t, 1.2, vel=v) for t, v in ((0.0, 96), (1.6, 80), (3.2, 66))]
    bell = _r(tolls, 6.0, "musescore")
    bell = A.peak_eq(bell, 300, 2.0, 1.0)       # a bigger, rounder bell
    # (the first chord's channels are free again for the last: 10 channels, not 15)
    ch = [(0.15, 1.45, ["D3", "A3", "D4", "F4", "A4"], (40, 92)), (1.6, 1.6, ["G3", "B3", "D4", "G4", "B4"], (92, 92)),
          (3.25, 1.9, ["D3", "A3", "D4", "F4", "A4"], (92, 18))]
    choir = []
    for tt, L, ps, sw in ch:
        choir += [Note(GM["voice_oohs"], p, tt, L, vel=76, swell=sw) for p in ps]
    choir_x = _r(choir, 6.0, "fluid")
    x = _mix((_at(bell, -20), 1.0), (_at(choir_x, -22), 1.0))
    x = _verb(x, room=0.9, wet=0.3, damping=0.5, tail=2.5)
    return _finish(x, "loss", 5.3, fade=1.4)


# ============================================================================= MISSION START
def _snare(seq: Seq, beat: float, seed: int, at: float = 0.0, seconds: float = 4.0) -> np.ndarray:
    """A field drum (the orchestral kit's snare), kept below 7 kHz: warm, not hissy."""
    y = _r(_play(DRUM, seq, beat, at, seed, jitter=0.003, kit="orchestra"), seconds, "fluid")
    return A.lowpass(y, 6500, 4)


def _mission_royal() -> np.ndarray:
    """A horn call over a kettle drum and a field drum: 'D, A-A, F# A, D!' climbing the
    D chord, the trombones holding D underneath, a drum roll driving into the last note
    and the trumpets joining it."""
    b = 0.36
    call = [(0, 0.7, "D4", 0.82), (0.75, 0.22, "A4", 0.8), (1, 0.92, "A4", 0.9), (2, 0.45, "F#4", 0.82),
            (2.5, 0.45, "A4", 0.86), (3, 2.0, "D5", 0.96)]
    second = [(0, 0.7, "D4", 0.72), (0.75, 0.22, "F#4", 0.7), (1, 0.92, "F#4", 0.8), (2, 0.45, "D4", 0.72),
              (2.5, 0.45, "F#4", 0.76), (3, 2.0, "A4", 0.88)]
    # tongued: each note a little short of the next, so the call is clearly articulated
    horns = _r(_play(GM["french_horn"], call[:-1], b, seed=401, jitter=0.003, legato=0.84)
               + _play(GM["french_horn"], call[-1:], b, at=0.002, seed=411)
               + _play(GM["french_horn"], second[:-1], b, seed=402, jitter=0.008, legato=0.84)
               + _play(GM["french_horn"], second[-1:], b, at=0.006, seed=412), 3.8, "musescore")
    horns = _double(horns, 6.0, 0.012, 0.6)
    tp = _double(_r(_play(GM["trumpet"], [(3, 2.0, "F#5", 0.72), (3, 2.0, "D5", 0.7)], b, seed=403), 3.8),
                 -5.0, 0.01, 0.5)
    bones = _r(_play(GM["trombone"], [(0, 2.95, "D3", 0.6), (3, 2.0, "D3", 0.78), (3, 2.0, "A3", 0.74)], b,
                     seed=404), 3.8)
    timp = A.lowpass(_r(_play(GM["timpani"], [(0, 0.3, "D3", 0.94), (1, 0.3, "A2", 0.66), (2, 0.3, "A2", 0.56),
                                             (3, 0.3, "D3", 1.0)], b, seed=405, jitter=0.0), 3.8), 3000, 2)
    roll = [(2 + i / 24.0 / b, 0.03, "snare", 0.28 + 0.4 * i / 20.0) for i in range(21)]
    sn = _snare([(0, 0.1, "snare", 0.8), (0.75, 0.1, "snare", 0.5), (1, 0.1, "snare", 0.64)] + roll
                + [(3, 0.1, "snare", 0.86)], b, 406, seconds=3.8)
    x = _mix((_at(horns, -18.5), 1.0), (_at(tp, -24), 1.0), (_at(bones, -24), 1.0), (_at(timp, -22), 1.0),
             (_at(sn, -27.5), 1.0))
    x = _verb(x, room=0.75, wet=0.2, damping=0.5, tail=2.0)
    return _finish(x, "mission_start", 3.6, fade=0.9)


def _mission_tavern() -> np.ndarray:
    """A marching tune to set off on: the hand drum and the lute strum on every beat, the
    recorder skips up the D chord, through G and A, and lands home on D."""
    b = 0.28
    rec = [(0, 0.45, "D5", 0.78), (0.5, 0.45, "F#5", 0.78), (1, 0.45, "A5", 0.84), (1.5, 0.45, "F#5", 0.76),
           (2, 0.45, "G5", 0.8), (2.5, 0.45, "B5", 0.84), (3, 0.45, "A5", 0.82), (3.5, 0.22, "F#5", 0.76),
           (3.75, 0.22, "E5", 0.74)]
    recorder = _r(_play(GM["recorder"], rec, b, seed=451, jitter=0.005)
                  + [Note(GM["recorder"], "D5", 4 * b + 0.003, 3.0 * b, vel=104, swell=(120, 55))], 3.6)
    chords = [["D3", "A3", "D4", "F#4"], ["D3", "A3", "D4", "F#4"], ["G2", "D3", "G3", "B3"], ["A2", "E3", "A3", "C#4"]]
    lute = []
    for i, ch in enumerate(chords):
        lute += [(i + j * 0.045, 1.0, p, 0.7 - 0.05 * j) for j, p in enumerate(ch)]
        lute += [(i + 0.5 + j * 0.035, 0.5, p, 0.36) for j, p in enumerate(reversed(ch[1:]))]   # a light up-strum
    lute += [(4 + j * 0.06, 4, p, 0.78 - 0.03 * j) for j, p in enumerate(["D3", "A3", "D4", "F#4", "A4"])]
    lute_x = _lute_body(_double(_r(_play(GM["nylon_guitar"], lute, b, seed=453, jitter=0.004), 4.0), 4.0, 0.006, 0.6))
    drum = _hand_drum([(0, 1, "doum", 0.95), (0.5, 1, "tek", 0.42), (0.75, 1, "tek", 0.36), (1, 1, "doum", 0.8),
                       (1.5, 1, "tek", 0.42), (2, 1, "doum", 0.86), (2.5, 1, "tek", 0.42), (2.75, 1, "tek", 0.36),
                       (3, 1, "doum", 0.8), (3.5, 1, "tek", 0.46), (3.75, 1, "tek", 0.5), (4, 1, "doum", 1.0)], b, 460)
    tamb = _tambourine([(1, 1, "tambourine", 0.5), (3, 1, "tambourine", 0.5), (4, 1, "tambourine", 0.62)], b, 461)
    x = _mix((_at(recorder, -18.5), 1.0), (_at(lute_x, -21), 1.0), (_at(drum, -23.5), 1.0), (_at(tamb, -31), 1.0))
    x = _verb(x, room=0.4, wet=0.14, damping=0.55, tail=1.5)
    return _finish(x, "mission_start", 3.4, fade=1.0)


def _mission_bells() -> np.ndarray:
    """The glockenspiel asks a question (A, D, E, rising), a harp sweeps up to meet it and
    opens into a ringing D-A-E chord (open, like a road ahead), with a tubular bell
    underneath and a trail of celesta sparkles."""
    glock = _glock([(0.0, "A5", 0.8), (0.16, "D6", 0.84), (0.32, "E6", 0.92), (0.72, "D6", 0.5)], 4.0)
    harp = [Note(GM["harp"], p, 0.36 + i * 0.03, 1.0, vel=int(58 + 4 * i))
            for i, p in enumerate(["D4", "E4", "F#4", "A4", "B4", "D5", "E5", "F#5", "A5"])]
    harp += [Note(GM["harp"], p, 0.72 + i * 0.03, 2.4, vel=int(98 - 4 * i))
             for i, p in enumerate(["D2", "A2", "D3", "A3", "E4", "A4", "D5"])]
    harp_x = _r(harp, 4.0, "musescore")
    cel = _r([Note(GM["celesta"], p, tt, 0.5, vel=v) for tt, p, v in ((1.0, "A6", 62), (1.16, "E6", 56),
                                                                     (1.34, "A5", 52))], 4.0)
    bell = _r([Note(GM["tubular_bells"], "D5", 0.72, 1.5, vel=64)], 4.0, "musescore")
    x = _mix((_at(glock, -19.5), 1.0), (_at(harp_x, -21), 1.0), (_at(cel, -27), 1.0), (_at(bell, -27), 1.0))
    x = _verb(x, room=0.8, wet=0.25, damping=0.5, tail=2.5)
    return _finish(x, "mission_start", 3.6, fade=1.1)


def _mission_strings() -> np.ndarray:
    """Low strings shiver on D and swell over a timpani roll; the violins call out in
    octaves, D up to A, a quick B-A-F# and a leap to the high D on a full D major chord
    with a timpani stroke."""
    trem = [Note(GM["tremolo_strings"], p, 0.0, 1.72, vel=100, swell=(64, 124)) for p in ["D2", "D3", "A3", "D4"]]
    trem_x = _r(trem, 4.0, "fluid")
    call = [(0.62, 0.16, "D5", 0.84), (0.78, 0.4, "A5", 0.9), (1.18, 0.13, "B5", 0.82), (1.31, 0.13, "A5", 0.8),
            (1.44, 0.26, "F#5", 0.84)]
    vl = []
    for tt, L, p, v in call:
        vl.append(Note(GM["violin"], p, tt, L, vel=int(127 * v)))
        vl.append(Note(GM["violin"], A.midi(p) - 12, tt + 0.004, L, vel=int(115 * v)))
    vln = _double(_r(vl, 4.0, "musescore"), 8.0, 0.01, 0.7)
    fin = [Note(GM["strings"], p, 1.70, 1.05, vel=110) for p in ["D2", "D3", "A3", "D4", "F#4", "A4", "D5", "F#5"]]
    fin += [Note(GM["violin"], "D6", 1.70, 1.0, vel=112), Note(GM["cello"], "D3", 1.70, 1.0, vel=108)]
    fin_x = _mix((_double(_r(fin, 4.0, "fluid"), 7.0, 0.012, 0.6), 1.0),
                 (_r([n for n in fin if n.program == GM["strings"]], 4.0, "musescore"), 0.5))
    tim = [(i / 16.0, 0.05, "D3", 0.3 + 0.32 * (i / 9.0) ** 1.5) for i in range(10)]
    tim[0] = (0.0, 0.05, "D3", 0.55)          # a firm first stroke: the jingle starts at once
    tim += [(0.62, 0.3, "D3", 0.82), (1.70, 0.3, "D3", 0.98)]
    timp = A.lowpass(_r(_play(GM["timpani"], tim, 1.0, seed=601, jitter=0.003), 4.0), 3000, 2)
    x = _mix((_at(trem_x, -22.5), 1.0), (_at(vln, -19), 1.0), (_at(fin_x, -18), 1.0), (_at(timp, -23), 1.0))
    x = _verb(x, room=0.72, wet=0.22, damping=0.5, tail=2.0)
    return _finish(x, "mission_start", 3.7, fade=0.9)


def _mission_ready() -> np.ndarray:
    """A herald's 'Ready, go!': two short trumpet A's, each with a crisp rap of the field
    drum ('ready... ready...'), then the trumpet runs up D, F#, A to a bright held high
    D, a second trumpet and the trombones under it, a kettle drum and a soft cymbal."""
    tp = [Note(GM["trumpet"], "A4", 0.0, 0.13, vel=96), Note(GM["trumpet"], "A4", 0.4, 0.13, vel=96),
          Note(GM["trumpet"], "D5", 0.80, 0.06, vel=94), Note(GM["trumpet"], "F#5", 0.86, 0.06, vel=98),
          Note(GM["trumpet"], "A5", 0.92, 0.06, vel=102), Note(GM["trumpet"], "D6", 0.98, 0.75, vel=108)]
    tp_x = _double(_r(tp, 2.8), 6.0, 0.008, 0.45)
    tp2 = [Note(GM["trumpet"], "A4", 0.0, 0.13, vel=80), Note(GM["trumpet"], "A4", 0.4, 0.13, vel=80),
           Note(GM["trumpet"], "A5", 0.985, 0.72, vel=96), Note(GM["trumpet"], "F#5", 0.99, 0.72, vel=92)]
    tp2_x = _r(tp2, 2.8, "musescore")
    low = _r([Note(GM["trombone"], "D3", 0.98, 0.72, vel=92), Note(GM["trombone"], "A3", 0.985, 0.72, vel=88),
              Note(GM["tuba"], "D2", 0.98, 0.72, vel=80)], 2.8)
    sn = _snare([(0, 0.1, "snare", 0.82), (0.4, 0.1, "snare", 0.82), (0.80, 0.03, "snare", 0.42),
                 (0.86, 0.03, "snare", 0.5), (0.92, 0.03, "snare", 0.6)], 1.0, 701, seconds=2.8)
    timp = A.lowpass(_r([Note(GM["timpani"], "D3", 0.98, 0.3, vel=110)], 2.8), 3000, 2)
    cym = _r([Note(DRUM, "crash", 0.98, 0.3, vel=58, kit="orchestra")], 2.8)
    cym = A.lowpass(A.highpass(cym, 400, 2), 6000, 4)
    x = _mix((_at(tp_x, -18), 1.0), (_at(tp2_x, -23), 1.0), (_at(low, -24), 1.0), (_at(sn, -25), 1.0),
             (_at(timp, -24), 1.0), (_at(cym, -31), 1.0))
    x = _verb(x, room=0.7, wet=0.18, damping=0.5, tail=1.8)
    return _finish(x, "mission_start", 2.9, fade=0.9)


# ============================================================================= the list
_SETS = {"royal": ["brass", "royal"], "tavern": ["tavern", "lute"], "enchanted": ["bells", "harp", "magic"],
         "orchestral": ["strings", "orchestral"], "chapel": ["bells", "choir", "chapel"],
         "herald": ["brass", "herald"]}

CANDIDATES = [
    Candidate("victory", "royal_fanfare", "Royal fanfare",
              "Trumpets, horns and kettle drums ring out a proud fanfare that ends on a long, rolling chord.",
              _victory_royal, _SETS["royal"]),
    Candidate("victory", "tavern_jig", "Tavern jig",
              "A recorder and a fiddle dance a quick jig over a strummed lute, a hand drum and a tambourine, "
              "like the whole inn cheering.",
              _victory_tavern, _SETS["tavern"]),
    Candidate("victory", "golden_bells", "Golden bells",
              "A harp sweeps up and a glockenspiel chimes a little winning tune, with a bell and a celesta "
              "sparkling as it fades.",
              _victory_bells, _SETS["enchanted"]),
    Candidate("victory", "string_triumph", "String triumph",
              "Violins rush upwards into three big bowed chords with timpani, the last one swelling and rolling "
              "like a film's happy end.",
              _victory_strings, _SETS["orchestral"]),
    Candidate("victory", "bell_tower", "Bell tower",
              "Church bells peal down the scale from the castle tower and ring together while a choir swells "
              "in beneath them.",
              _victory_bell_tower, _SETS["chapel"]),

    Candidate("loss", "fallen_banner", "Fallen banner",
              "Soft French horns and trombones play a slow, solemn hymn over a far-off drum roll: dignified, "
              "not mocking.",
              _loss_royal, _SETS["royal"]),
    Candidate("loss", "lonely_lute", "Lonely lute",
              "A lute picks a quiet minor chord while a recorder sings a short, wistful phrase and fades to rest.",
              _loss_tavern, _SETS["tavern"]),
    Candidate("loss", "last_candle", "Last candle",
              "A harp lets slow minor chords fall away while a celesta echoes softly, fading like a candle "
              "going out.",
              _loss_harp, _SETS["enchanted"]),
    Candidate("loss", "cello_lament", "Cello lament",
              "A lone cello sings a slow, sighing phrase over hushed strings and settles on a low note.",
              _loss_cello, _SETS["orchestral"]),
    Candidate("loss", "tolling_bell", "Tolling bell",
              "A church bell tolls three times, softer each time, while a quiet choir hums a mournful 'amen'.",
              _loss_bell, _SETS["chapel"]),

    Candidate("mission_start", "horn_call", "Horn call",
              "Horns sound a rising call over kettle drums and a snare roll, and trumpets join the last note: "
              "time to ride out.",
              _mission_royal, _SETS["royal"]),
    Candidate("mission_start", "road_song", "Road song",
              "A hand drum, a strummed lute and a skipping recorder strike up a marching tune for the road.",
              _mission_tavern, _SETS["tavern"]),
    Candidate("mission_start", "starlit_path", "Starlit path",
              "A glockenspiel asks a rising question and a harp sweeps up into a shimmering, open chord with a "
              "soft bell.",
              _mission_bells, _SETS["enchanted"]),
    Candidate("mission_start", "rising_quest", "Rising quest",
              "Low strings shiver and swell over a timpani roll, then the violins call out a bold motif onto a "
              "big chord.",
              _mission_strings, _SETS["orchestral"]),
    Candidate("mission_start", "ready_go", "Ready, go!",
              "A herald's trumpet and field drum: two short calls, then a quick run up to a bright, held note "
              "with a kettle drum.",
              _mission_ready, _SETS["herald"]),
]


# ============================================================================= the editor's pass
# A phone's small speaker plays almost nothing below 300 Hz: a jingle that would lose more
# than PHONE_MAX_LOSS dB of its loudness there (less for a victory, the biggest moment)
# gets a gentle low shelf (at most -8 dB below about 250 Hz), so after mastering its body
# is that much more present on the phone.
PHONE_MAX_LOSS = {"victory": 1.5}          # any other event: 3 dB


def _low_shelf(x: np.ndarray, f0: float, gain_db: float, q: float = 0.707) -> np.ndarray:
    """A low shelf (RBJ biquad): ``gain_db`` below ``f0``, half of it at ``f0``."""
    from scipy import signal
    a_ = 10 ** (gain_db / 40.0)
    w0 = 2 * math.pi * f0 / A.SR
    al = math.sin(w0) / (2 * q)
    c = math.cos(w0)
    s2 = 2 * math.sqrt(a_) * al
    b = [a_ * ((a_ + 1) - (a_ - 1) * c + s2), 2 * a_ * ((a_ - 1) - (a_ + 1) * c), a_ * ((a_ + 1) - (a_ - 1) * c - s2)]
    a = [(a_ + 1) + (a_ - 1) * c + s2, -2 * ((a_ - 1) + (a_ + 1) * c), (a_ + 1) + (a_ - 1) * c - s2]
    return signal.lfilter(b, a, x)


def _phone_loss(x: np.ndarray) -> float:
    return A._rms_db(x) - A._rms_db(A.highpass(x, 300, 4))


def _phone(x: np.ndarray, most: float) -> np.ndarray:
    if _phone_loss(x) <= most:
        return x
    for g in range(1, 9):
        y = _low_shelf(x, 250.0, -float(g))
        if _phone_loss(y) <= most:
            break
    return y


def _edited(c: Candidate) -> Candidate:
    render = c.render
    return dataclasses.replace(c, render=lambda: _phone(render(), PHONE_MAX_LOSS.get(c.event, 3.0)))


CANDIDATES = [_edited(c) for c in CANDIDATES]
