"""Info pop-up clips of the Evergreen group (docs/INFO_POPUPS.md, "Melody plan", ZONE MOTIF
and EVERGREEN): the five locations, the Cave's collapse, eight banes and five boons.

THE LOCATIONS colour the zone motif, three cards laid down: D (a quarter), E (an eighth),
A (a dotted quarter), one bar of the Whistle jig's 6/8 (as in the missions' clips):

  Shrine          hand bells ring the motif, a celesta chime answers, soft voices hum a
                  D drone under them: serene as a temple (D major)
  Cave            a low marimba lays the motif and the cave sends it back twice, darker;
                  woodblock and marimba drips; it settles on a marimba roll (D minor)
  Cave collapses  the cave motif starts and falls apart: marimba notes tumble down two
                  octaves over a drum roll, stones settle and a low D is left (D minor)
  Forest          a pan flute plays the motif among whistled birdsong and a shaker's
                  rustle, homing to D through C natural (D mixolydian)
  Hills           a horn calls the motif across the hills, the call echoes back from
                  far away over a distant drum, and the horn ends low on D (D minor)
  Lake            a recorder sings the motif over rippling harp sixteenths (D major)

THE BANES open with the bane sting (a low pizzicato D rubbing against E flat, a bassoon
on the D under it), then the card's own phrase, in D minor or dorian:

  10 Poisonous Clerics   the Cleric's harp arpeggio falls in D minor into the zone motif
  12 Duplicitous Bards   a sly lute strum and turn, doubled by a second lute about a
                         sixth of a semitone out of tune with it; open on A (its box)
  14 Absorbtion          the dulcimer's zone motif is swallowed by a bassoon sliding down
  15 Tread Carefully     light pizzicato tiptoes up high, trips and falls into a spill of cards
  16 Lingering Dread     half time: a slow tolling bell over a viol drone
  21 Eye-Level Sticks    sharp woodblock and claves knocks, a startled fiddle yelp; open on A
  22 The Fiery Crucible  a fire's crackle (shaker), a fiddle figure flaring up and falling
  23 Choose Your Poison  an oboe asks D, E flat again and again; open on A (its box)

THE BOONS open with the boon lift (a recorder's A rising to D over a rolled harp chord),
then the card's own phrase, in D major; every boon stands before its box and ends open
on A over the open A-E fifth:

  30 Squad of Siblings   two recorders in unison stepping along together
  31 Selfless Rescue     a horn call answered by a harp
  32 Precision Strike    a harp arpeggio aims up, one bright pluck and a bell ring on high
                         D (on target), then the recorder waits on A
  33 Restored Arrows     arrows whoosh past (breath), then a harp run up to A
  35 A Close Call        a nervous fiddle tremolo over a pounding heart, hanging on B flat
                         until the very last moment, when it lets go onto A

Every clip is built by ``_info_common.clip`` (the harp pickup, the cadence, the shared
tail, the tavern room and the master chain). Foley no bank records (a fire's crackle, an
arrow's whoosh) is modelled from filtered noise, kept low and dark so it never hisses.
"""
from __future__ import annotations

import dataclasses
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from _info_common import (BAR, DQ, DRUM, EIGHTH, MOTIF, QUARTER, SIXTEENTH, A, INote, Note, at, card_sound, choke, clip,
                          double, fit, hit, info, n, name, perc, phrase, prog, render, roll, trill)

# ============================================================================= tuning
# Some of the banks' samples are out of tune: the pizzicato strings by up to a fifth of a
# semitone, differently in each register (the MuseScore bank's alike), and the timpani's D.
# Cents off, measured on the notes this family plays (the pitch its first five harmonics
# agree on, which is what a phone's small speaker lets one hear); a note listed here is
# bent back to pitch for its whole length (a note that already slides keeps its slide).
# The Fluid bank (BANK_FOR leaves both there); offsets under 7 cents are left alone.
DETUNE: Dict[str, Dict[str, int]] = {
    "pizzicato": {"D2": -12, "A2": 18, "D3": 14, "Eb3": 10, "A3": 11, "C4": 7, "D4": 7, "G4": -10, "A4": -8},
    "timpani": {"D3": 10},
    # the boon lift's goal note, the Lake's held D, the Shrine's chime and bane 22's held D
    "recorder": {"D5": 9}, "celesta": {"D6": 10}, "violin": {"D5": 9},
}
_DETUNE_BY_PROG = {prog(k): v for k, v in DETUNE.items()}


def _tuned(notes: Sequence[Note]) -> List[Note]:
    """``notes`` with the out-of-tune samples (``DETUNE``) bent back to pitch."""
    out: List[Note] = []
    for x in notes:
        table = _DETUNE_BY_PROG.get(x.program) if x.program != DRUM else None
        c = table.get(name(x.key())) if table else None
        if c:
            b0, b1 = x.bend if x.bend is not None else (0.0, 0.0)
            x = dataclasses.replace(x, bend=(b0 - c / 100.0, b1 - c / 100.0))
        out.append(x)
    return out


def _render(notes: Sequence[Note], seconds: Optional[float] = None) -> np.ndarray:
    """``render`` with the samples in tune."""
    return render(_tuned(list(notes)), seconds)


def _clip(motif: Sequence[Note] = (), **kw) -> np.ndarray:
    """``clip`` with the motif's samples in tune."""
    return clip(_tuned(list(motif)), **kw)


# ============================================================================= helpers
ZONE = ("D5", "E5", "A5")                   # the zone motif's three cards


def _zone(inst: str, start: float = 0.0, pitches: Sequence[str] = ZONE, vel: int = 96, slow: bool = False,
          seed: int = 0, **kw) -> List[INote]:
    """The zone motif, three cards laid down: D (a quarter), E (an eighth), A (a dotted
    quarter), from ``start`` (motif time)."""
    d, e, a = pitches
    return phrase(inst, "%s:2 %s:1 %s:3" % (d, e, a), at=start, vel=vel, slow=slow, seed=seed, **kw)


def _tail(x: np.ndarray, floor_db: float = -60.0) -> np.ndarray:
    """Cut what stays under ``floor_db`` (re the peak) at the end, so a layer is measured by
    its sound rather than the silence after it (the start is kept: timing holds)."""
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak <= 0:
        return x
    idx = np.nonzero(np.abs(x) > peak * 10 ** (floor_db / 20.0))[0]
    y = x[:min(len(x), int(idx[-1]) + A.n_of(0.02))].copy()
    k = min(len(y), A.n_of(0.02))
    y[-k:] *= np.linspace(1.0, 0.0, k)
    return y


def _hits(name_: str, times_vels: Sequence[Tuple[float, int]], lp: float = 0.0) -> np.ndarray:
    """A tavern percussion part: ``perc`` strokes at (time, velocity), as one layer."""
    x = np.zeros(A.n_of(0.1))
    for t, v in times_vels:
        x = A.mix_at(x, perc(name_, v), t)
    if lp:
        x = A.lowpass(x, lp, 2)
    return _tail(x)


def _gm_hits(key_: str, times_vels: Sequence[Tuple[float, int]], kit: str = "standard", lp: float = 0.0) -> np.ndarray:
    """General MIDI percussion hits (``hit``) at (time, velocity), as one layer."""
    x = np.zeros(A.n_of(0.1))
    for t, v in times_vels:
        x = A.mix_at(x, hit(key_, v, kit), t)
    if lp:
        x = A.lowpass(x, lp, 2)
    return _tail(x)


def _bell(pitch: str = "D6", vel: int = 50, lp: float = 3800.0, seconds: float = 1.6, order: int = 2) -> np.ndarray:
    """A hand bell touched softly: the bank's tubular bell with its sharp top taken away
    (``order`` 4: a steeper cut, a rounder, warmer bell)."""
    return _tail(A.lowpass(_render([n("hand_bell", pitch, 0.0, 0.6, vel=vel)], seconds + 0.4), lp, order))


def _far(x: np.ndarray, lp: float, wet: float, gain_db: float, room: float = 0.75) -> np.ndarray:
    """A sound heard from farther away: darker, wetter, softer."""
    y = A.lowpass(x, lp, 2)
    y = A.reverb(y, room, wet, 0.6, 1.0, 0.9)
    return _tail(y * 10 ** (gain_db / 20.0))


def _crossfade_dark(x: np.ndarray, t0: float, t1: float, lp: float = 520.0, keep: float = 0.6) -> np.ndarray:
    """From ``t0`` to ``t1`` s the sound turns from bright to dark and dim (swallowed)."""
    dark = A.lowpass(x, lp, 2) * keep
    t = np.arange(len(x)) / A.SR
    w = np.clip((t - t0) / max(1e-3, t1 - t0), 0.0, 1.0)
    w = 0.5 - 0.5 * np.cos(np.pi * w)
    return x * (1.0 - w) + dark * w


def _whoosh(d: float = 0.24, seed: int = 0, f0: float = 2400.0, f1: float = 650.0) -> np.ndarray:
    """An arrow whooshing past: breathy noise through a band that drops from ``f0`` to
    ``f1`` as it passes (a Doppler fall), swelling in fast and dying away."""
    y = A.highpass(A.noise(d, "pink", seed), 250, 2)
    out = np.zeros_like(y)
    edges = np.linspace(0, len(y), 17).astype(int)
    for i in range(16):
        u = (edges[i] + edges[i + 1]) / 2.0 / len(y)
        f = f0 * (f1 / f0) ** u
        seg = A.bandpass(y, f * 0.6, f * 1.6, 2)
        out[edges[i]:edges[i + 1]] = seg[edges[i]:edges[i + 1]]
    t = np.arange(len(y)) / len(y)
    env = np.where(t < 0.42, (t / 0.42) ** 2, np.exp(-(t - 0.42) * 7.0))
    return _tail(A.lowpass(out * env, 3800, 2))


def _crackle(seconds: float, seed: int, rate: float = 20.0) -> np.ndarray:
    """A fire's crackle: little pops (short noise bursts ringing in a band, a few loud, most
    faint) over the flames' soft roar, swelling in and dying away."""
    rng = np.random.default_rng(seed)
    x = np.zeros(A.n_of(seconds))
    t = float(rng.exponential(1.0 / rate))
    while t < seconds - 0.05:
        k = A.n_of(float(rng.uniform(0.0015, 0.005)))
        burst = rng.standard_normal(k) * np.exp(-np.arange(k) / (k / 3.0))
        f = float(rng.uniform(900, 3200))
        pop = A.bandpass(fit(burst, 0.03), f * 0.55, f * 1.6, 2)
        x = A.mix_at(x, float(rng.uniform(0.15, 1.0)) ** 2.2 * pop / (np.max(np.abs(pop)) or 1.0), t)
        t += float(rng.exponential(1.0 / rate))
    roar = A.bandpass(A.noise(seconds, "pink", seed + 1), 180, 900, 2)
    roar *= 1 + 0.5 * np.sin(2 * np.pi * 2.7 * np.arange(len(roar)) / A.SR + 0.4)
    roar = 0.12 * roar / (np.max(np.abs(roar)) or 1.0)
    env = np.interp(np.arange(len(x)) / A.SR, [0, 0.1, seconds * 0.5, seconds], [0.0, 1.0, 0.85, 0.0])
    return _tail(A.lowpass((x + roar) * env, 4000, 2))


def _sixteenths(notes: List[INote], start: float, dur: float = SIXTEENTH * 1.2) -> List[INote]:
    """Squeeze a phrase written in eighths into sixteenths from ``start`` (motif time)."""
    t0 = min(x.start for x in notes)
    for x in notes:
        x.start = start + (x.start - t0) / 2
        x.dur = dur
    return notes


# ============================================================================= the signatures
def _sting(vel: int = 98) -> np.ndarray:
    """The bane sting (a dotted quarter long), as a layer at the bank's level: a low
    pizzicato D struck with the E flat a semitone above it, rubbing, and a bassoon on the
    D under them that fades; the player then damps the strings, so the rub does not ring
    on under the card's phrase."""
    notes = [n("pizzicato", "D3", 0.0, 0.26, vel=vel),
             n("pizzicato", "D2", 0.0, 0.26, vel=vel - 18),
             n("pizzicato", "Eb3", 0.014, 0.26, vel=vel - 8),
             n("bassoon", "D3", 0.004, 0.30, vel=vel - 14, swell=(124, 58))]
    return _tail(choke(_render(notes, 1.4), 0.34, 0.4))


# the sting's loudest moment sits level with the loudest moments of the card's phrase: a
# signature heard first, not the main event
STING_DB = 0.0


def _lift(vel: int = 88, seed: int = 0) -> List[INote]:
    """The boon lift (a dotted quarter long): the recorder's A rising to D over a soft
    rolled harp chord."""
    return (roll("harp", ["D3", "A3", "F#4"], 0.0, 0.8, vel=60, spread=0.022)
            + phrase("recorder", "A4 D5:2", vel=vel, legato=0.98, accent=0, seed=seed))


# ============================================================================= locations
def _shrine() -> np.ndarray:
    # hand bells ring the three cards; a celesta chime answers an octave up; the bells
    # step down to D as humming voices hold a soft D drone, a temple at rest
    bells = np.zeros(A.n_of(0.1))
    for p, t, v in (("D5", 0.0, 54), ("E5", QUARTER, 48), ("A5", DQ, 54), ("G5", BAR, 46), ("F#5", at(1, 2), 46),
                    ("E5", at(1, 3), 44), ("D5", MOTIF, 52)):
        b = _bell(p, v, 2300, 1.4, order=4)
        if t == MOTIF:                               # the last bell: its twelfth (A6) down, its D rings clear
            b = A.peak_eq(b, 1760, -9.0, 3.0)
        bells = A.mix_at(bells, b, t)
    bells = A.peak_eq(bells, 3000, -4.0, 0.8)
    chime = phrase("celesta", "r:4 A5 D6:2", at=BAR, vel=52, accent=0, seed=601)
    chime += [n("celesta", "D6", MOTIF + 0.006, 0.6, vel=40), n("celesta", "A5", at(0, 4), 0.3, vel=36)]
    hum = [n("humming", "D3", 0.0, MOTIF + 0.5, vel=64, swell=(60, 96)),
           n("humming", "A3", 0.02, MOTIF - 0.04, vel=54, swell=(54, 80))]       # it leaves D alone at the end
    harp = [n("harp", "D3", 0.0, 0.9, vel=52), n("harp", "A2", BAR, 0.9, vel=48)]
    return _clip(chime + hum + harp, end="D", mood="party", instrument=None, bed_db=-14.0,
                 layers=[(_tail(bells), 0.0, 1.0)])


def _cave() -> np.ndarray:
    # a low marimba lays the three cards and the cave sends them back twice, darker each
    # time; drips (a high woodblock, a soft marimba plink); a slow D-minor descent F, E
    # settles on a fading marimba roll on D
    lay = _zone("marimba", 0.0, ("D3", "E3", "A3"), vel=104, seed=611)
    lay += _zone("marimba", 0.0, ("D4", "E4", "A4"), vel=74, seed=612)
    dry = _render(lay)
    echo = A.mix_at(_far(dry, 1500, 0.35, -7.0, 0.85), _far(dry, 900, 0.5, -14.0, 0.9), DQ)
    descent = phrase("marimba", "F3:3 E3:3", at=BAR, vel=96, accent=0, seed=613)
    descent += phrase("marimba", "F4:3 E4:3", at=BAR, vel=64, accent=0, seed=614)
    roll_ = [n("marimba", p, MOTIF + i * 0.058 + (0.012 if p == "D4" else 0.0), 0.05,
               vel=max(24, int(92 - 9 * i))) for i in range(9) for p in ("D3", "D4") if (i % 2 == 0) == (p == "D3")]
    roll_ += [n("marimba", "D3", MOTIF, 0.1, vel=100)]
    plinks = [n("marimba", "D6", 0.43, 0.08, vel=44), n("marimba", "A5", 1.07, 0.08, vel=40)]
    drips = _gm_hits("hi_woodblock", [(0.21, 46), (0.77, 38), (0.95, 44), (1.52, 34)], lp=4200)
    return _clip(lay + descent + roll_ + plinks, end="D", mood="enemy", instrument=None, bed_db=-13.0,
                 layers=[(echo, DQ, -6.0), (drips, 0.0, -12.0)])


def _cave_collapse() -> np.ndarray:
    # the cave's three cards start (D E A, quick) and the roof gives: marimba notes tumble
    # down two octaves of D minor over a drum roll and a heavy thud; stones settle in a
    # few dull knocks and a low D is left on marimba and timpani
    start = phrase("marimba", "D4 E4 A4", vel=100, seed=621)
    fall = ["A5", "G5", "F5", "E5", "D5", "C5", "A4", "Bb4", "G4", "F4", "E4", "C#4", "D4", "A3", "F3", "E3"]
    rng = np.random.default_rng(622)
    tumble: List[INote] = []
    t = DQ
    for i, p in enumerate(fall):
        tumble.append(n("marimba", p, t, 0.08, vel=int(np.clip(100 - 3 * i + rng.integers(-8, 9), 50, 112))))
        t += 0.047 + 0.012 * np.sin(i * 1.7) + 0.0016 * i          # an uneven, slowing fall
    land = [n("marimba", "D3", MOTIF, 0.3, vel=106), n("marimba", "D4", MOTIF + 0.01, 0.3, vel=70),
            n("timpani", "D3", MOTIF, 0.6, vel=92)]
    roll_t = [(DQ + 0.05 * k + 0.004 * (k % 3), int(54 + 40 * np.sin(np.pi * k / 16))) for k in range(16)]
    drum = _hits("frame_drum", roll_t, lp=2400)
    thuds = _hits("war_drum", [(BAR + 0.02, 104), (MOTIF, 82)], lp=1800)
    stones = _hits("woodblock", [(1.08, 70), (1.17, 52), (1.235, 40), (1.28, 30)], lp=2600)
    return _clip(start + tumble + land, end="D", mood="enemy", instrument=None, bed_db=-14.0,
                 layers=[(drum, 0.0, -7.0), (thuds, 0.0, -3.0), (stones, 0.0, -12.0)])


def _bird(t0: float, seed: int) -> List[INote]:
    """A little bird: two or three quick whistled chirps, each sliding up into its note."""
    rng = np.random.default_rng(seed)
    out: List[INote] = []
    t = t0
    for k in range(int(rng.integers(2, 4))):
        p = ["A6", "B6", "F#6", "E6"][int(rng.integers(0, 4))]
        out.append(n("whistle", p, t, 0.045, vel=int(rng.integers(46, 60)), bend=(-2.5, 0.3)))
        t += float(rng.uniform(0.055, 0.075))
    return out


def _forest() -> np.ndarray:
    # a pan flute plays the three cards and wanders home through C natural (mixolydian);
    # whistled birds chirp in its rests, a shaker rustles like leaves, a harp keeps the bass
    flute = _zone("pan_flute", 0.0, vel=90, seed=631, legato=0.98)
    flute += phrase("pan_flute", "G5:2 F#5 E5:2 C5", at=BAR, vel=86, legato=0.98, seed=632)
    birds = _render(_bird(0.47, 633) + _bird(1.02, 634) + _bird(MOTIF + 0.36, 635))
    birds = _tail(A.lowpass(birds, 5200, 2))
    trill_ = _render(trill("whistle", "A6", "B6", 0.86, 0.12, vel=44, rate=0.03))
    birds = A.mix_at(birds, 0.6 * _tail(A.lowpass(trill_, 5200, 2)), 0.0)
    leaves = _hits("shaker", [(0.0, 56), (DQ, 44), (BAR, 52), (at(1, 3), 42), (MOTIF, 48)], lp=4800)
    harp = [n("harp", "D3", 0.0, 0.8, vel=58), n("harp", "A2", DQ, 0.6, vel=50), n("harp", "G2", BAR, 0.6, vel=52),
            n("harp", "C3", at(1, 3), 0.6, vel=54)]
    harp_ = _tail(choke(_render(harp), MOTIF + 0.03, 0.4))     # damped as D comes home: the C does not ring on
    return _clip(flute, end="D5", mood="folk", instrument="pan_flute", held_vel=88,
                 layers=[(harp_, 0.0), (birds, 0.0, -10.0), (leaves, 0.0, -15.0)])


def _hills() -> np.ndarray:
    # a horn calls the three cards across the hills; the call comes back from far away,
    # twice, as a distant drum beats; the horn answers F, E and settles low on D: a warning
    call = _zone("horn", 0.0, ("D4", "E4", "A4"), vel=100, seed=641, legato=0.97)
    echo_src = _render(_zone("horn", 0.0, ("D4", "E4", "A4"), vel=96, seed=642, legato=0.97))
    echo = A.mix_at(_far(echo_src, 1700, 0.4, 0.0, 0.85), _far(echo_src, 1100, 0.55, -8.0, 0.9), DQ)
    answer = phrase("horn", "F4:2 E4", at=at(1, 3), vel=92, seed=643)
    drum = _far(_hits("war_drum", [(0.0, 90), (BAR, 84), (MOTIF, 88)], lp=900), 700, 0.45, 0.0, 0.8)
    harp = [n("harp", "D3", 0.0, 0.9, vel=54), n("harp", "A2", BAR, 0.8, vel=48)]
    return _clip(call + answer + harp, end="D4", mood="enemy", instrument="horn", held_vel=92,
                 layers=[(echo, BAR, -9.0), (drum, 0.0, -10.0)])


def _ripples(chords: Sequence[Tuple[Sequence[str], float, int, float]], vel: int = 56,
             seed: int = 0) -> List[INote]:
    """Harp ripples: each chord's notes up and down in sixteenths, ringing over each other
    (each chord: pitches, start, how many sixteenths, how long each string is let ring)."""
    rng = np.random.default_rng(seed)
    out: List[INote] = []
    for pitches, t0, count, ring in chords:
        ps = list(pitches) + list(pitches[-2:0:-1])
        for k in range(count):
            v = vel + int(8 * np.sin(np.pi * k / max(1, count - 1))) + int(rng.integers(-4, 5))
            out.append(n("harp", ps[k % len(ps)], t0 + k * SIXTEENTH + float(rng.uniform(-0.003, 0.003)),
                         ring, vel=v))
    return out


def _lake() -> np.ndarray:
    # a recorder sings the three cards and comes home B, A, F#, E to D, over harp ripples
    # like water (D major, G, A)
    tune = _zone("recorder", 0.0, vel=86, seed=651, legato=0.98)
    tune += phrase("recorder", "B5:2 A5 F#5:2 E5", at=BAR, vel=84, legato=0.98, seed=652)
    water = _ripples([(("D4", "A4", "D5", "F#5"), 0.0, 12, 0.4), (("G3", "D4", "G4", "B4"), BAR, 6, 0.3),
                      (("A3", "E4", "A4", "C#5"), at(1, 3), 6, 0.2)], vel=54, seed=653)
    water += [n("harp", "D3", 0.0, 0.9, vel=56), n("harp", "G2", BAR, 0.6, vel=50), n("harp", "A2", at(1, 3), 0.6,
                                                                                       vel=50)]
    water = _tail(choke(_render(water), MOTIF + 0.05, 0.6))         # the ripples settle as the recorder lands
    tune += [n("recorder", "D5", MOTIF, 0.44, vel=84, swell=(118, 46))]     # the held D (in tune: DETUNE)
    return _clip(tune, end="D5", mood="party", instrument=None, bed_db=-14.0,
                 layers=[(water, 0.0)])


# ============================================================================= banes
def _bane10() -> np.ndarray:
    # the sting; the Cleric's harp arpeggio falls in D minor (A F D A F D, quick), and the
    # zone's three cards follow low on the dulcimer, closing on D
    harp = _sixteenths(phrase("harp", "A5 F5 D5 A4 F4 D4", vel=84, accent=0, seed=661), DQ, 0.5)
    harp += [n("harp", "D3", BAR, 0.8, vel=56)]
    dulc = _zone("hammered_dulcimer", BAR, ("D4", "E4", "A4"), vel=98, seed=662)
    dulc += [n("hammered_dulcimer", "D3", BAR, 0.5, vel=62)]
    return _clip(harp + dulc, end="D4", mood="enemy", instrument="hammered_dulcimer", held_vel=94,
                 layers=[(_sting(), 0.0, STING_DB)])


def _bane12() -> np.ndarray:
    # the sting; a sly lute: a D-minor strum, a slithering turn (D F E C# E) and a waiting
    # A, played by two lutes, the second about a sixth of a semitone out of tune
    lute = roll("lute", ["D3", "A3", "D4", "F4"], DQ, 0.3, vel=92, spread=0.02)
    lute += phrase("lute", "D4 F4 E4 C#4:2 E4", at=BAR, vel=84, seed=671)
    lute += [n("lute", "A3", MOTIF, 0.5, vel=86), n("lute", "A4", MOTIF + 0.012, 0.5, vel=80)]
    # "slightly out of tune": a sixth of a semitone beats clearly on the held A without souring it
    two = _tail(double(_render(lute), cents=16.0, delay=0.024, gain=0.85))
    return _clip((), end="A", mood="bane", instrument=None, bed="lute", bed_db=-12.0,
                 layers=[(_sting(), 0.0, STING_DB), (two, 0.0, 1.0)])


def _bane14() -> np.ndarray:
    # the sting; the dulcimer lays the zone's three cards, and a bassoon slides down from
    # A to D under the last one, swallowing it (the dulcimer darkens as it goes down)
    dulc = _render(_zone("hammered_dulcimer", 0.0, vel=98, seed=681)
                  + [n("hammered_dulcimer", "D4", 0.0, 0.5, vel=64)])
    gulp = at(1, 1)                                  # the slide starts (motif time)
    dulc = _tail(_crossfade_dark(dulc, gulp - DQ, MOTIF - DQ, lp=480, keep=0.5))
    bsn = [n("bassoon", "A3", gulp, MOTIF - gulp, vel=100, bend=(0.0, -7.0), swell=(96, 120)),
           n("bassoon", "D3", MOTIF, 0.46, vel=98, swell=(112, 44)),
           n("pizzicato", "D3", MOTIF, 0.3, vel=84), n("pizzicato", "D4", MOTIF + 0.01, 0.3, vel=70)]
    return _clip(bsn, end="D", mood="enemy", instrument=None, bed_db=-13.0,
                 layers=[(_sting(), 0.0, STING_DB), (dulc, DQ, 0.0)])


def _bane15() -> np.ndarray:
    # the sting; pizzicato tiptoes on light feet (A, C, D, E, up high), trips and falls
    # A G F E as the whole discard pile spills; the pizzicato picks itself up on D
    toes = phrase("pizzicato", "A4 r C5 D5 r E5", at=DQ, vel=70, accent=6, legato=0.6, seed=691)
    trip = _sixteenths(phrase("pizzicato", "A4 G4 F4 E4", vel=86, accent=0, seed=692), at(1, 3) - 0.01, 0.1)
    land = [n("pizzicato", "D3", MOTIF, 0.3, vel=96), n("pizzicato", "D4", MOTIF + 0.01, 0.3, vel=80),
            n("bassoon", "D3", MOTIF, 0.44, vel=82, swell=(104, 40))]
    spill = card_sound("discard")
    spill = A.mix_at(spill, 0.7 * card_sound("discard"), 0.09)
    spill = _tail(A.lowpass(spill, 6000, 2))
    return _clip(toes + trip + land, end="D", mood="bane", instrument=None,
                 layers=[(_sting(), 0.0, STING_DB), (spill, at(1, 4), -4.0)])


def _bane16() -> np.ndarray:
    # the sting; then in half time a viol drone on D and A, a bell tolling low (A, then
    # D), and a viol line sinking F, E onto D
    viol = [n("bass_viol", "D3", 0.2, MOTIF + 0.5, vel=78, swell=(66, 100)),
            n("viol", "A3", 0.3, MOTIF - 0.3, vel=64, swell=(60, 80))]
    line = phrase("viol", "F4:2 E4", at=at(0, 3, slow=True), vel=82, slow=True, accent=0, seed=701)
    gap = MOTIF - at(0, 3, slow=True)                # from the first toll to the second
    first = choke(_bell("A4", 66, 2600, 1.4), gap, 0.3)   # the damper falls on the A as the D tolls
    tolls = A.mix_at(first, _bell("D4", 70, 2400, 1.6), gap)
    return _clip(viol + line, end="D4", mood="enemy", instrument="viol", slow=True, held_vel=82,
                 layers=[(_sting(), 0.0, STING_DB), (_tail(tolls), at(0, 3, slow=True), -2.0)])


def _bane21() -> np.ndarray:
    # the sting; sticks knock at eye level (woodblock and claves, sharp, three then one);
    # a fiddle yelps up to a startled B flat and falls back, waiting on A
    knocks = A.mix_at(_hits("woodblock_hi", [(DQ, 108), (DQ + EIGHTH, 96), (DQ + QUARTER, 114), (BAR, 120)], lp=5500),
                      _gm_hits("claves", [(DQ, 70), (DQ + EIGHTH, 62), (DQ + QUARTER, 74), (BAR, 82)], lp=5000), 0.0)
    yelp = [n("violin", "Bb5", BAR + 0.03, 0.16, vel=104, bend=(-6.0, 0.0)),
            n("violin", "G5", at(1, 3), EIGHTH, vel=82), n("violin", "E5", at(1, 4), EIGHTH, vel=80),
            n("violin", "C#5", at(1, 5), EIGHTH, vel=80)]
    pizz = [n("pizzicato", "A2", BAR, 0.2, vel=80)]
    return _clip(yelp + pizz, end="A4", mood="bane", instrument="violin", held_vel=82,
                 layers=[(_sting(), 0.0, STING_DB), (knocks, 0.0, -1.0)])


def _bane22() -> np.ndarray:
    # the sting; the fire crackles (a shaker over little pops); a fiddle flares up D F A
    # D F A and falls back G F E C# onto D
    flare = _sixteenths(phrase("violin", "D4 F4 A4 D5 F5 A5", vel=80, accent=0, seed=711), DQ, 0.07)
    fall = phrase("violin", "A5:2 G5 F5 E5 C#5", at=BAR, vel=82, legato=0.9, seed=712)
    fire = A.mix_at(_crackle(1.6, 713), 0.9 * _hits("shaker", [(t, v) for t, v in
                    ((0.05, 50), (0.24, 38), (0.4, 62), (0.52, 44), (0.7, 58), (0.81, 40), (0.98, 52), (1.2, 36))],
                    lp=3600), 0.0)
    fire = _tail(A.lowpass(fire, 3200, 2))                # a warm hearth, never a hiss
    held = [n("violin", "D5", MOTIF, 0.44, vel=84, swell=(118, 46))]
    fiddle = _render(flare + fall + held)
    fiddle = _tail(A.peak_eq(A.lowpass(fiddle, 5000, 2), 3200, -3.0, 1.0))    # this clip comes every turn: warmer
    return _clip((), end="D5", mood="enemy", instrument=None,
                 layers=[(fiddle, 0.0, 0.0), (_sting(), 0.0, STING_DB), (fire, 0.1, -14.0)])


def _bane23() -> np.ndarray:
    # the sting; an oboe asks the same two notes, D and E flat, again and again (faster
    # the third time), then waits on A
    oboe = phrase("oboe", "D5 Eb5:2 D5 Eb5:2 D5 Eb5 D5", at=DQ, vel=84, legato=0.9, seed=721)
    pizz = [n("pizzicato", "D3", BAR, 0.2, vel=70), n("pizzicato", "Eb3", BAR + 0.012, 0.2, vel=56)]
    return _clip(oboe + pizz, end="A4", mood="bane", instrument="oboe", held_vel=80,
                 layers=[(_sting(), 0.0, STING_DB)])


# ============================================================================= boons
def _boon30() -> np.ndarray:
    # the lift; two recorders in unison (a sibling a few cents apart) step along D E F#,
    # G F# G A B, and wait on A together
    walk = phrase("recorder", "D5 E5 F#5 G5:2 F#5 G5 A5 B5", at=DQ, vel=82, legato=0.9, seed=731)
    walk += [n("recorder", "A5", MOTIF, 0.44, vel=80, swell=(118, 46))]
    pair = _tail(double(_render(walk), cents=9.0, delay=0.016, gain=0.9))
    harp = [n("harp", "G2", BAR, 0.6, vel=56), n("harp", "A2", at(1, 3), 0.6, vel=52)]      # IV, V: onto the A
    return _clip(_lift(seed=730) + harp, end="A", mood="party", instrument=None,
                 layers=[(pair, 0.0, 0.0)])


def _boon31() -> np.ndarray:
    # the lift; a horn calls A D F# up to A; a harp answers it, F# E C#, and waits on A
    horn = phrase("horn", "A3 D4 F#4 A4:3", at=DQ, vel=96, legato=0.96, seed=741)
    harp = phrase("harp", "F#5:2 E5 C#5", at=at(1, 3) - EIGHTH, vel=86, legato=1.6, seed=742)
    harp += [n("harp", "D3", BAR, 0.6, vel=56), n("harp", "A2", at(1, 3), 0.6, vel=52)]
    return _clip(_lift(seed=740) + horn + harp, end="A4", mood="party", instrument="harp", held_vel=86)


def _boon32() -> np.ndarray:
    # the lift; a harp aims up F# A C#, and one bright pluck lands on high D with a bell
    # ringing on it (on target); the recorder then waits on A under the bell
    aim = phrase("harp", "F#5 A5 C#6", at=DQ, vel=70, legato=1.2, accent=0, seed=751)
    pluck = [n("harp", "D6", BAR, 0.6, vel=98), n("harp", "D5", BAR + 0.004, 0.6, vel=92),
             n("lute", "D5", BAR, 0.4, vel=90), n("harp", "D4", BAR, 0.6, vel=70)]
    pluck_ = _tail(choke(_render(pluck), MOTIF + 0.04, 0.45))     # the strings are stopped; the bell rings on
    ring = A.peak_eq(_bell("D6", 58, 2800, 1.5, order=4), 3200, -4.0, 0.8)
    wait = phrase("recorder", "B5", at=at(1, 5), vel=70, seed=752)
    return _clip(_lift(seed=750) + aim + wait, end="A5", mood="party", instrument="recorder", held_vel=72,
                 layers=[(pluck_, 0.0), (ring, BAR + 0.006, -4.0)])


def _boon33() -> np.ndarray:
    # the lift; arrows whoosh past, three of them; then a harp runs up the D-major scale
    # from D to A and waits there
    whooshes = A.mix_at(A.mix_at(_whoosh(0.24, 761), 0.7 * _whoosh(0.22, 762, 2800, 800), 0.13),
                        0.8 * _whoosh(0.26, 763, 2200, 600), 0.27)
    run = _sixteenths(phrase("harp", "D4 E4 F#4 G4 A4 B4 C#5 D5 E5 F#5 G5", vel=82, accent=0, seed=764), BAR, 0.5)
    run += [n("harp", "D3", BAR, 0.4, vel=58), n("harp", "A2", at(1, 3), 0.6, vel=56)]
    run_ = _tail(choke(_render(run), MOTIF + 0.03, 0.35))          # the harpist stops the run's strings on the A
    return _clip(_lift(seed=760), end="A5", mood="party", instrument="harp", held_vel=90,
                 layers=[(run_, 0.0), (_tail(whooshes), DQ - 0.04, -6.0)])


def _boon35() -> np.ndarray:
    # the lift; a fiddle trembles nervously (F, E, then B flat) over a pounding heart, and
    # only at the very last moment lets go onto A
    trem: List[INote] = []
    for p, t0, t1 in (("F5", DQ, BAR), ("E5", BAR, at(1, 2)), ("Bb4", at(1, 2), MOTIF - 0.02)):
        k = 0
        t = t0
        while t < t1 - 0.02:
            trem.append(n("violin", p, t, 0.036, vel=74 + (8 if k % 2 == 0 else 0) + int(10 * (t - DQ))))
            t += 0.038
            k += 1
    heart = _hits("frame_drum", [(DQ, 74), (DQ + 0.13, 56), (at(1, 0) + 0.12, 80), (at(1, 0) + 0.25, 60),
                                 (at(1, 3) + 0.06, 86), (at(1, 3) + 0.18, 64)], lp=1600)
    harp = [n("harp", "D3", DQ, 0.6, vel=54), n("harp", "Bb2", at(1, 2), 0.6, vel=54)]
    harp_ = _tail(choke(_render(harp), MOTIF + 0.02, 0.3))      # the B flat is let go with the fiddle's
    return _clip(_lift(seed=770) + trem, end="A4", mood="party", instrument="violin", held_vel=86,
                 layers=[(harp_, 0.0), (heart, 0.0, -9.0)])


# ============================================================================= the candidates
CANDIDATES = [
    # locations
    info("shrine", "temple_bells", "Temple bells",
         "Soft hand bells ring D, E, A and step home to D, a celesta chiming above and voices humming a drone.",
         _shrine, ["zone", "bells", "calm"]),
    info("cave", "marimba_echo", "Marimba echo",
         "A low marimba plays D, E, A and the cave echoes it back twice, with drips, settling on a soft roll.",
         _cave, ["zone", "dark", "marimba"]),
    info("cave_collapse", "rockfall", "Rockfall",
         "The cave's marimba notes tumble down over a drum roll and a heavy thud; stones settle on a low D.",
         _cave_collapse, ["zone", "dark", "drum"]),
    info("forest", "birdsong_flute", "Birdsong flute",
         "A pan flute plays D, E, A among whistled bird chirps and a rustling shaker, coming home to D.",
         _forest, ["zone", "flute", "birds"]),
    info("hills", "horn_echo", "Horn echo",
         "A horn calls D, E, A; the call echoes back from far away over a distant drum, and the horn sinks to D.",
         _hills, ["zone", "horn", "warning"]),
    info("lake", "harp_ripples", "Harp ripples",
         "A recorder sings D, E, A over rippling harp notes like water, gently home to D.",
         _lake, ["zone", "harp", "calm"]),
    # banes
    info("bane10", "falling_cleric", "Falling Cleric",
         "The bane sting (a low pluck rubbing D against E flat), then a harp falls in D minor into a dulcimer's "
         "D, E, A.",
         _bane10, ["bane", "harp", "dark"]),
    info("bane12", "two_faced_lute", "Two-faced lute",
         "The bane sting, then a sly lute strum and turn played by two lutes slightly out of tune; waits on A.",
         _bane12, ["bane", "lute", "question"]),
    info("bane14", "swallowed", "Swallowed",
         "The bane sting, then a dulcimer's D, E, A swallowed by a bassoon sliding down to a low D.",
         _bane14, ["bane", "bassoon", "dark"]),
    info("bane15", "tiptoe_spill", "Tiptoe and spill",
         "The bane sting, then plucked strings tiptoe, trip, and a pile of cards spills; a low D picks itself up.",
         _bane15, ["bane", "pizzicato", "cards"]),
    info("bane16", "tolling_dread", "Tolling dread",
         "The bane sting, then slowly: a bell tolls over a low viol drone as a viol line sinks to D.",
         _bane16, ["bane", "bells", "slow"]),
    info("bane21", "sticks_and_yelp", "Sticks and yelp",
         "The bane sting, sharp woodblock knocks, a startled fiddle yelp, and a nervous wait on A.",
         _bane21, ["bane", "fiddle", "question"]),
    info("bane22", "fiddle_flare", "Fiddle flare",
         "The bane sting, a crackling fire, and a fiddle that flares up quickly and falls back down to D.",
         _bane22, ["bane", "fiddle", "fire"]),
    info("bane23", "oboe_question", "Oboe question",
         "The bane sting, then an oboe asks D, E flat again and again, and waits on A.",
         _bane23, ["bane", "oboe", "question"]),
    # boons
    info("boon30", "recorder_pair", "Recorder pair",
         "The boon lift (a recorder rising A to D over harp), then two recorders step along together and wait on A.",
         _boon30, ["boon", "recorder", "question"]),
    info("boon31", "horn_and_harp", "Horn and harp",
         "The boon lift, then a horn calls up to A and a harp answers, waiting on A.",
         _boon31, ["boon", "horn", "question"]),
    info("boon32", "bullseye_bell", "Bullseye bell",
         "The boon lift, a harp aims up, one bright pluck and a bell ring on high D, then the recorder waits on A.",
         _boon32, ["boon", "bells", "question"]),
    info("boon33", "arrows_and_harp", "Arrows and harp",
         "The boon lift, three arrows whoosh past, then a harp runs up the scale to A.",
         _boon33, ["boon", "harp", "question"]),
    info("boon35", "nervous_fiddle", "Nervous fiddle",
         "The boon lift, then a fiddle trembles over a pounding heart and only at the last moment lets go onto A.",
         _boon35, ["boon", "fiddle", "question"]),
]
