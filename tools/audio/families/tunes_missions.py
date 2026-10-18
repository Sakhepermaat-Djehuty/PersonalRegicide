"""Info pop-up clips of the missions group (docs/INFO_POPUPS.md, "Melody plan", ZONE MOTIF):
the zone growing in missions 3, 5, 10 and 12, mission 5's carried damage, mission 7's
pilgrims, mission 8's filled zone, mission 9's captured piles, mission 10's corrupted
Cleric and Bard, and mission 11's beast.

THE ZONE MOTIF is three cards laid down on a hammered dulcimer: D (a quarter), E (an
eighth), A (a dotted quarter), one bar of the Whistle jig's 6/8. Each mission colours it:

  m3  Zone grows      dulcimer and celesta in D lydian over a crackle of flame (the academy)
  m5  Zone grows      dulcimer, the motif twice (D E A, then F G B-flat), a bassoon swelling
                      a step higher under every card (D E F G A), heavier each time, home to D
  m7  Pilgrim         a recorder walking tune over soft frame-drum footsteps (D mixolydian)
  m7  Pilgrim match   the recorder's call answered by a harp on the same A, a light rise; open
  m8  Zone filled!    a pan-flute ladder to a high D with gusts of wind and a bell; open
  m9  Captured piles  tubular bells toll the motif at half time over low voices (the lament
                      bass D C B-flat A); open
  m10 Zone grows      a darkened dulcimer, low, over a slow war drum in D minor
  m10 Cleric enemy    the Cleric's rising harp arpeggio mirrored, falling in D minor into
                      the motif on a low dulcimer
  m10 Bard enemy      the Bard's lute run backwards in D minor, a sly detuned strum, its
                      turn reversed; open
  m11 Beast           a low horn growl with a bassoon under it over a frame drum, answered
                      by the beast's class instrument in D minor (``BEASTS``: four renders,
                      the Bard beast's lute first; the Cleric's harp also waits on A, the
                      Warrior's fiddle and the Paladin's horn have no box and settle on D)
  m12 Zone grows      wooden flute and harp in D minor (D minor, B-flat, A) brightening to
                      D major on the last note
  m5  Carry damage    the Damage strike (bodhran under a strummed D-minor lute stab, D D A),
                      echoing twice into the distance a fifth higher, landing on D major

A card shown just before a decision box ends open on A over the open A-E fifth (Pilgrim
match, Zone filled!, Captured piles, Bard enemy, Beast); the others end on D. Every clip is
built by ``_info_common.clip``: the harp pickup, the two-bar motif, the held cadence over
the soft harp chord, the shared harp tail, the tavern room and the master chain.

Foley no bank records (a fire's crackle, a gust of wind) is modelled from filtered noise,
kept low and darkened so it never hisses over the music.

TUNING: a few of the banks' samples are off; the notes that are held or exposed are bent
back to pitch where they are written (celesta D6 +10 cents, bassoon A3 -13, recorder D5 +9,
flute D5 +7), and the voices come from the MuseScore bank (the Fluid choir is 15 to 30
cents flat). Harp strings ring on past note-off, so a harp part that must not ring into a
cadence is damped there (``_part``).
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np

from _info_common import (BAR, DQ, EIGHTH, MOTIF, QUARTER, SIXTEENTH, A, INote, at, cadence_notes, choke, clip, fit,
                          info, n, perc, phrase, render, roll)

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


def _mix(*parts: np.ndarray) -> np.ndarray:
    """Sum audio parts that all start at 0 (their lengths may differ)."""
    x = np.zeros(max(len(y) for y in parts))
    for y in parts:
        x[:len(y)] += y
    return x


def _part(notes: Sequence[INote], damp_at: float = 0.0, fall: float = 0.3, lp: float = 0.0) -> np.ndarray:
    """Notes (times from the downbeat) rendered on their own at the bank's level: damped
    from ``damp_at`` (a hand on the strings, so a dulcimer's or harp's open ring does not
    blur the cadence) and gently low-passed at ``lp`` (a struck string's top softened)."""
    x = render(notes)
    if damp_at:
        x = choke(x, damp_at, fall)
    if lp:
        x = A.lowpass(x, lp, 2)
    return x


def _hits(name_: str, times_vels: Sequence[Tuple[float, int]], lp: float = 0.0) -> np.ndarray:
    """A tavern percussion part: ``perc`` strokes at (time, velocity), one layer."""
    x = np.zeros(A.n_of(0.1))
    for t, v in times_vels:
        x = A.mix_at(x, perc(name_, v), t)
    if lp:
        x = A.lowpass(x, lp, 2)
    return _tail(x)


def _far(x: np.ndarray, lp: float, wet: float, gain_db: float) -> np.ndarray:
    """A sound heard from farther away: darker, wetter, softer."""
    y = A.lowpass(x, lp, 2)
    y = A.reverb(y, 0.7, wet, 0.6, 1.0, 0.8)
    return _tail(y * 10 ** (gain_db / 20.0))


def _bell(pitch: str = "D6", vel: int = 46, lp: float = 4200.0, seconds: float = 1.6) -> np.ndarray:
    """A small bright bell: the bank's tinkle bell (a clear fundamental; the tubular bell
    at D6 keeps half its energy above 4 kHz), its top taken down so it rings, not pings."""
    return _tail(A.lowpass(render([n("cap_bells", pitch, 0.0, 0.6, vel=vel)], seconds + 0.4), lp, 4))


def _crackle(seconds: float, seed: int, rate: float = 22.0) -> np.ndarray:
    """A fire's crackle: little pops (short noise bursts ringing in a band, a few loud,
    most faint) over the flames' soft breathy roar, swelling in and dying away."""
    rng = np.random.default_rng(seed)
    x = np.zeros(A.n_of(seconds))
    t = float(rng.exponential(1.0 / rate))
    while t < seconds - 0.05:
        k = A.n_of(float(rng.uniform(0.003, 0.009)))
        burst = rng.standard_normal(k) * np.hanning(k)
        f = float(rng.uniform(700, 2600))
        pop = A.bandpass(fit(burst, 0.03), f * 0.6, f * 1.5, 2)
        x = A.mix_at(x, float(rng.uniform(0.2, 1.0)) ** 2.5 * pop / (np.max(np.abs(pop)) or 1.0), t)
        t += float(rng.exponential(1.0 / rate))
    roar = A.bandpass(A.noise(seconds, "pink", seed + 1), 180, 900, 2)
    roar *= 1 + 0.5 * np.sin(2 * np.pi * 3.1 * np.arange(len(roar)) / A.SR + 0.7)
    roar = 0.18 * roar / (np.max(np.abs(roar)) or 1.0)
    env = np.interp(np.arange(len(x)) / A.SR, [0, 0.12, seconds * 0.55, seconds], [0.0, 1.0, 0.8, 0.0])
    return _tail(A.lowpass((x + roar) * env, 3200, 2))


def _gust(seconds: float, seed: int, f0: float, f1: float, peak: float = 0.45) -> np.ndarray:
    """A gust of wind: pink noise through a band that moves from ``f0`` up to ``f1`` and
    back as the gust swells (at ``peak`` of its length) and dies away."""
    y = A.highpass(A.noise(seconds, "pink", seed), 220, 2)
    t = np.arange(len(y)) / A.SR
    out = np.zeros_like(y)
    edges = np.linspace(0, len(y), 25).astype(int)
    for i in range(24):
        u = (edges[i] + edges[i + 1]) / 2.0 / len(y)
        f = f0 + (f1 - f0) * np.sin(np.pi * min(1.0, u / (2 * peak))) if u < 2 * peak else f0
        seg = A.bandpass(y, f * 0.6, f * 1.5, 2)
        out[edges[i]:edges[i + 1]] = seg[edges[i]:edges[i + 1]]
    env = np.interp(t, [0, peak * seconds, seconds], [0.0, 1.0, 0.0]) ** 1.5
    return _tail(A.lowpass(out * env, 3500, 2))


# ============================================================================= mission 3: Lessons in Flames (D)
def _m3_zone() -> np.ndarray:
    # the dulcimer lays the three cards over a low D; the celesta answers in D lydian (its G
    # sharp: the academy's magic), the fire crackling under both
    dulc = _zone("hammered_dulcimer", 0.0, vel=98, seed=301)
    dulc += [n("hammered_dulcimer", "D4", 0.0, 0.6, vel=66), n("hammered_dulcimer", "D4", BAR, 0.6, vel=60)]
    celesta = phrase("celesta", "A5:2 B5 G#5:2 E5", at=BAR, vel=82, seed=302)
    # the bank's celesta D6 is 10 cents sharp: bent back so it sits on the dulcimer's D
    held = [n("hammered_dulcimer", "D5", MOTIF, 0.6, vel=94), n("hammered_dulcimer", "D4", MOTIF + 0.006, 0.6, vel=62),
            n("celesta", "D6", MOTIF + 0.004, 0.5, vel=52, bend=(-0.1, -0.1))]
    band = _mix(_part(dulc + celesta, MOTIF + 0.01, 0.3, 5200), _part(held, lp=5200))
    return clip((), end="D5", mood="magic", layers=[(band, 0.0, 0.0), (_crackle(1.85, 303), -0.1, -19.5)])


# ============================================================================= mission 5: High and Mighty (D)
def _m5_zone() -> np.ndarray:
    # the zone motif, then again a third higher and darker; a bassoon swells under every
    # card a step higher (D E F G A), heavier each time, and falls home to D
    dulc = phrase("hammered_dulcimer", "D5:2 E5 A5:3 F5:2 G5 Bb5:2 A5", vel=96, seed=501)
    held = [n("hammered_dulcimer", "D5", MOTIF, 0.6, vel=104), n("hammered_dulcimer", "D4", MOTIF + 0.006, 0.6, vel=70)]
    steps = (("D3", 0.0, DQ, 66, (44, 92)), ("E3", DQ, DQ, 72, (50, 100)), ("F3", BAR, DQ, 80, (58, 108)),
             ("G3", BAR + DQ, QUARTER, 86, (66, 116)), ("A3", BAR + DQ + QUARTER, EIGHTH, 90, (104, 120)))
    # the bank's bassoon A3 is 13 cents flat: bent back up
    bassoon = [n("bassoon", p, t, d + 0.02, vel=v, swell=s, bend=(0.13, 0.13) if p == "A3" else None)
               for p, t, d, v, s in steps]
    bassoon += [n("bassoon", "D3", MOTIF, 0.42, vel=86, swell=(112, 30))]
    band = _mix(_part(dulc, MOTIF + 0.01, 0.25, 5200), _part(held, lp=5200), render(bassoon))
    return clip((), end="D5", mood="enemy", layers=[(band, 0.0, 0.0)])


def _stab(pitches: Sequence[str], t: float, vel: int, dur: float = 0.45) -> List[INote]:
    """A chord strummed down hard on the lute (the Damage card's stab)."""
    return roll("lute", list(pitches), t, dur, vel=vel, spread=0.011)


def _m5_carry() -> np.ndarray:
    # the Damage strike: a D-minor stab, again, then A (D D A) over the bodhran ...
    strike = _stab(["D3", "A3", "D4", "F4"], 0.0, 112) + _stab(["D3", "A3", "D4"], DQ, 98, 0.2)
    strike += _stab(["A2", "E3", "A3"], DQ + 2 * EIGHTH, 92, 0.12)
    drum = _hits("bodhran", [(0.0, 124), (DQ, 96), (DQ + 2 * EIGHTH, 82)])
    # ... echoing twice a fifth higher (A A, then A), farther each time ...
    echo1 = render(_stab(["A3", "E4", "A4", "C5"], 0.0, 100, 0.3) + _stab(["A3", "E4", "A4"], 2 * EIGHTH, 88, 0.2))
    echo1 = A.mix_at(echo1, perc("bodhran", 96), 0.0)
    echo2 = A.mix_at(render(_stab(["A3", "E4", "A4", "C5"], 0.0, 94, 0.3)), perc("bodhran", 84), 0.0)
    # ... and the blow lands on the next enemy: a soft D-major strum
    land = [n("lute", p, MOTIF + 0.016 * i, 0.6, vel=v) for i, (p, v) in
            enumerate((("D3", 84), ("F#3", 64), ("A3", 70), ("D4", 92)))]
    return clip(strike + land, end="D", mood="folk", instrument=None,
                layers=[(drum, 0.0, 0.0), (_far(echo1, 2800, 0.3, 0.0), BAR, -4.0),
                        (_far(echo2, 2000, 0.42, 0.0), BAR + DQ, -9.0)])


# ============================================================================= mission 7: Tales of Rebirth
def _m7_pilgrim() -> np.ndarray:
    # the zone motif as a traveller's song: a recorder walks D E A G, F# D E C and home to
    # D (mixolydian), a lute bass stepping with it, soft frame-drum footsteps on each beat
    tune = phrase("recorder", "D5:2 E5 A5:2 G5 F#5:2 D5 E5:2 C5", vel=84, legato=0.92, seed=701)
    bass = [n("lute", p, t, 0.3, vel=v) for p, t, v in
            (("D3", 0.0, 62), ("A2", DQ, 54), ("D3", BAR, 58), ("C3", BAR + DQ, 56))]
    steps = _hits("frame_drum", [(0.0, 70), (DQ, 56), (BAR, 66), (BAR + DQ, 56), (MOTIF, 62)], lp=1600)
    # the held D (the bank's recorder D5 is 9 cents sharp: bent back onto the harp's D)
    held = [n("recorder", "D5", MOTIF, 0.44, vel=86, swell=(118, 46), bend=(-0.09, -0.09))]
    return clip(tune + bass + held, end="D5", mood="folk", instrument=None,
                layers=[(steps, 0.0, -11.0)])


def _m7_match() -> np.ndarray:
    # the pilgrim's call on the recorder (D E A); a harp answers on the very same A (a
    # match), then the recorder rises lightly E F# G and waits on A
    call = phrase("recorder", "D5:2 E5 A5:3", vel=84, legato=0.9, seed=711)
    harp = [n("harp", "A5", BAR, 0.8, vel=88), n("harp", "A4", BAR + 0.008, 0.8, vel=70),
            n("harp", "D3", 0.0, 0.7, vel=56), n("harp", "A2", BAR, 0.7, vel=54)]
    rise = phrase("recorder", "E5 F#5 G5", at=BAR + DQ, vel=76, legato=0.9, accent=0, seed=712)
    return clip(call + harp + rise, end="A5", mood="party", instrument="recorder", held_vel=84)


# ============================================================================= mission 8: Winds of Chaos (open)
def _m8_filled() -> np.ndarray:
    # a pan flute climbs the ladder D E F# G A B C# to the top, high D, as a bell rings
    # and the wind gusts; then it drops to A and waits (the banish box)
    ladder = phrase("pan_flute", "D5 E5 F#5 G5 A5 B5:0.5 C#6:0.5 D6:3", vel=80, legato=1.0, accent=4, seed=801)
    ladder += [n("pan_flute", "A5", at(1, 3), 0.7, vel=100, swell=(122, 50))]
    bass = [n("harp", "D3", 0.0, 0.6, vel=58), n("harp", "G2", DQ, 0.6, vel=54), n("harp", "D3", BAR, 0.6, vel=58),
            n("harp", "A3", BAR, 0.6, vel=50)]
    bell = choke(_bell("D6", 50, 4200, 1.4), 0.3, 0.4)
    wind = A.mix_at(_gust(0.9, 803, 500, 1300, 0.7), _gust(0.8, 804, 650, 1600, 0.35), 0.62)
    return clip(ladder, end="A", mood="party", instrument=None, cadence_at=at(1, 3), hold=0.7,
                layers=[(_part(bass, at(1, 3), 0.25), 0.0), (bell, BAR + 0.004, -10.0), (wind, -0.08, -12.5)])


# ============================================================================= mission 9: Hope From Ashes (open)
def _m9_piles() -> np.ndarray:
    # the zone motif tolled slowly on tubular bells (D, E, A: one toll a beat at half time)
    # over low voices pleading down the lament bass (D minor, C, B flat), opening onto A
    bells = render([n("temple_bell", "D4", 0.0, 0.9, vel=80), n("temple_bell", "E4", BAR, 0.9, vel=76),
                    n("temple_bell", "A4", MOTIF, 1.0, vel=80)])
    bells = _tail(A.lowpass(A.peak_eq(bells, 2600, -4.0, 1.0), 3400, 2))
    # the voices come from the MuseScore bank: the Fluid choir is 15 to 30 cents flat. Each
    # chord lets go just before the next (the sample's release carries it over), and the
    # lament's chords are damped as the open fifth comes in, so the B flat does not smear
    # the question
    moving: List[INote] = []
    for chord, t, d, v in ((("D3", "F3", "A3"), 0.0, BAR, 70), (("C3", "E3", "G3"), BAR, DQ, 72),
                           (("Bb2", "D3", "F3"), BAR + DQ, DQ, 74)):
        moving += [n("voices", p, t + 0.01 * i, d - 0.04, vel=v - 4 * i, bank="musescore")
                   for i, p in enumerate(chord)]
    final = [n("voices", p, MOTIF + 0.01 * i, 0.62, vel=74 - 4 * i, swell=(110, 40), bank="musescore")
             for i, p in enumerate(("A2", "E3", "A3"))]
    choir = _mix(_part(moving, MOTIF + 0.03, 0.35, 3400), _part(final, lp=3400))
    return clip((), end="A", mood="enemy", slow=True, bed_db=-15.0, layers=[(choir, 0.0, 0.0), (bells, 0.0, 1.0)])


# ============================================================================= mission 10: Pride to Fall
def _m10_zone() -> np.ndarray:
    # the zone motif low and dark on the dulcimer (its top taken away), then B flat, A,
    # F, E down to D; a slow war drum under it in D minor
    dulc = phrase("hammered_dulcimer", "D4:2 E4 A4:3 Bb4:2 A4 F4:2 E4", vel=100, seed=1001)
    dulc += [n("hammered_dulcimer", "D3", 0.0, 0.6, vel=74), n("hammered_dulcimer", "Bb2", BAR, 0.6, vel=70),
             n("hammered_dulcimer", "A2", BAR + DQ, 0.6, vel=66)]
    held = [n("hammered_dulcimer", "D4", MOTIF, 0.6, vel=98), n("hammered_dulcimer", "D3", MOTIF + 0.006, 0.6, vel=76)]
    dark = _tail(A.lowpass(_mix(_part(dulc, MOTIF + 0.01, 0.3), render(held)), 2400, 2))
    drum = _hits("war_drum", [(0.0, 100), (BAR, 92), (MOTIF, 96)], lp=2500)
    ghosts = _hits("frame_drum", [(DQ, 60), (BAR + DQ, 60)], lp=2000)
    return clip((), end="D", mood="enemy", instrument=None,
                layers=[(dark, 0.0, 0.0), (drum, 0.0, -5.0), (ghosts, 0.0, -14.0)])


def _m10_cleric() -> np.ndarray:
    # the Cleric's rising harp arpeggio mirrored: it falls A F D, A F D in D minor, into
    # the zone motif on a low dulcimer, which closes down onto D
    harp = phrase("harp", "A5 F5 D5 A4 F4 D4", vel=82, legato=1.6, accent=6, seed=1011)
    harp += [n("harp", "D3", 0.0, 1.0, vel=60), n("harp", "A2", BAR + DQ, 0.6, vel=56)]
    dulc = _zone("hammered_dulcimer", BAR, ("D4", "E4", "A4"), vel=98, seed=1012)
    held = [n("hammered_dulcimer", "D4", MOTIF, 0.6, vel=96), n("hammered_dulcimer", "D3", MOTIF + 0.006, 0.6, vel=64)]
    band = _mix(_part(harp + dulc, MOTIF + 0.01, 0.3), _part(held, lp=5200))
    return clip((), end="D4", mood="enemy", layers=[(band, 0.0, 0.0)])


def _m10_bard() -> np.ndarray:
    # the Bard's run backwards: the lute runs down B flat to D in D minor, a sly detuned
    # strum, the Bard's turn reversed (C# E D E F), and it waits on A for your card
    run = phrase("lute", "Bb4 A4 G4 F4 E4 D4", vel=84, seed=1021)
    for x in run:                                    # a run of sixteenths
        x.start = x.start / 2
        x.dur = SIXTEENTH * 1.2
    sour = (-0.32, 0.26, -0.22, 0.3, -0.28)          # each string a little out (semitones)
    strum = [n("lute", p, DQ + 0.024 * i, 0.5 - 0.024 * i, vel=94 - 3 * i, bend=(b - 0.25, b))
             for i, (p, b) in enumerate(zip(("D3", "A3", "D4", "F4", "A4"), sour))]
    turn = phrase("lute", "C#5 E5 D5 E5 F5:2", at=BAR, vel=84, seed=1022)
    return clip(run + strum + turn, end="A4", mood="enemy", instrument="lute", held_vel=86)


# ============================================================================= mission 11: Descent Into Darkness
# The beast's class: (its instrument, the octave its answer is played in, how it ends: the
# Cleric and Bard beasts pause on a box, open on A; the Warrior and Paladin beasts do not).
# The instruments are the classes' own (tunes_classes: the Warrior's fiddle is the violin).
BEASTS: Dict[str, Tuple[str, int, str]] = {
    "cleric": ("harp", 0, "A4"), "bard": ("lute", 0, "A4"), "warrior": ("violin", 0, "D5"),
    "paladin": ("horn", -1, "D4"),
}
RINGS = {"harp"}                    # answers whose strings ring on past note-off: damped at the cadence
ANSWER_DB = -3.0                    # the answer's loudest moments re the growl's


def _beast(cls: str) -> np.ndarray:
    # the beast motif: a low horn growls up into D, rubs against E flat and sinks back,
    # a bassoon growling under it, a frame drum pacing; the beast's class answers in D
    # minor (A D, F E C#) and stops on A (or resolves to D)
    inst, octv, end = BEASTS[cls]
    growl = [n("horn", "D3", 0.0, DQ - 0.02, vel=106, bend=(-2.0, 0.0), swell=(70, 122)),
             n("horn", "Eb3", DQ, EIGHTH, vel=100),
             n("horn", "D3", DQ + EIGHTH, QUARTER + 0.02, vel=96, swell=(116, 56))]
    growl += [n("horn", "A2", 0.0, DQ - 0.02, vel=96, bend=(-2.0, 0.0), swell=(70, 118)),
              n("horn", "A2", DQ + EIGHTH, QUARTER + 0.02, vel=88, swell=(110, 50)),
              n("bassoon", "D2", 0.0, DQ - 0.02, vel=92, bend=(-2.0, 0.0)),
              n("bassoon", "D2", DQ + EIGHTH, QUARTER, vel=84)]
    shift = 12 * octv
    answer = phrase(inst, [(62 + 7 + shift, 1), (74 + shift, 2), (77 + shift, 1), (76 + shift, 1), (73 + shift, 1)],
                    at=BAR, vel=80, legato=0.95, seed=1101)
    held = cadence_notes(end, inst, MOTIF, 0.44, 82, answer[-1].key())
    # the answer (with its held note) is one layer set a little under the growl, so every
    # class answers alike (the banks' own levels differ: the violin's sits 9 dB under the
    # growl); a harp is damped at the cadence, so F E C# do not ring on under the held A
    ans = _part(answer, MOTIF + 0.01, 0.25) if inst in RINGS else render(answer)
    ans = _mix(ans, render(held))
    drum = _hits("frame_drum", [(0.0, 112), (2 * EIGHTH, 68), (DQ, 100), (BAR, 84), (BAR + DQ, 66)], lp=2200)
    return clip(growl, end=end, mood="enemy", instrument=None, layers=[(ans, 0.0, ANSWER_DB), (drum, 0.0, -7.0)])


def _beast_bard() -> np.ndarray:
    return _beast("bard")


def _beast_cleric() -> np.ndarray:
    return _beast("cleric")


def _beast_warrior() -> np.ndarray:
    return _beast("warrior")


def _beast_paladin() -> np.ndarray:
    return _beast("paladin")


# ============================================================================= mission 12: Decay to Growth (D)
def _m12_zone() -> np.ndarray:
    # the zone motif on a wooden flute over a flowing harp in D minor (D minor, B flat, A),
    # the flute stepping E to D as the harp brightens to D major under it
    flute = phrase("wooden_flute", "D5:2 E5 A5:3 F5:2 G5 E5:3", vel=78, legato=1.0, accent=6, seed=1201)
    # the flowing harp is damped as the D-major chord comes in (its strings ring on past
    # note-off: undamped, the minor's F and the A chord's C# rang under the brightening F#)
    harp = phrase("harp", "D3 A3 F4 D3 A3 F4 Bb2 F3 D4 A2 E3 C#4", vel=58, legato=2.2, accent=6, seed=1202)
    bright = roll("harp", ["D3", "A3", "D4", "F#4"], MOTIF, 0.9, vel=66, spread=0.02)
    # the held D (the bank's flute D5 is 7 cents sharp: bent back onto the harp's D)
    held = [n("wooden_flute", "D5", MOTIF, 0.44, vel=82, swell=(118, 46), bend=(-0.07, -0.07))]
    return clip(flute + bright + held, end="D5", mood="party", chord="major", instrument=None,
                layers=[(_part(harp, MOTIF + 0.01, 0.3), 0.0)])


# ============================================================================= the candidates
CANDIDATES = [
    info("m3_zone", "flame_lesson", "Flame lesson",
         "A hammered dulcimer lays down D, E, A; a celesta answers with a magic sharp note over a crackling fire.",
         _m3_zone, ["zone", "magic"]),
    info("m5_zone", "heavier_steps", "Heavier steps",
         "The dulcimer lays its three cards twice, higher the second time, as a bassoon swells a step higher under "
         "each, then sinks to D.",
         _m5_zone, ["zone", "dark"]),
    info("m5_carry", "strike_echo", "Strike echo",
         "The Damage strike (lute and bodhran) echoes twice a fifth higher into the distance, then lands on D.",
         _m5_carry, ["strike", "lute"]),
    info("m7_pilgrim", "travellers_song", "Traveller's song",
         "A recorder walking tune over soft frame-drum footsteps, gentle and hopeful.", _m7_pilgrim,
         ["zone", "recorder"]),
    info("m7_match", "harp_match", "Harp match",
         "The pilgrim's recorder call answered by a harp on the same note, then a light rise that waits on A.",
         _m7_match, ["recorder", "harp", "question"]),
    info("m8_filled", "wind_ladder", "Wind ladder",
         "A pan flute climbs a ladder to a high D with a bell and gusts of wind, then waits on A.", _m8_filled,
         ["zone", "flute", "question"]),
    info("m9_piles", "captive_bells", "Captive bells",
         "Slow temple bells toll D, E, A over low pleading voices, ending open.", _m9_piles,
         ["zone", "bells", "slow", "question"]),
    info("m10_zone", "rubble_drum", "Rubble drum",
         "The dulcimer's three cards, low and dark, over a slow war drum in D minor.", _m10_zone,
         ["zone", "dark", "drum"]),
    info("m10_cleric", "falling_harp", "Falling harp",
         "The Cleric's harp arpeggio turned upside down, falling in D minor into the dulcimer's three cards.",
         _m10_cleric, ["zone", "dark", "harp"]),
    info("m10_bard", "sly_strum", "Sly strum",
         "The Bard's lute run backwards in D minor, a sour detuned strum and a sly turn that waits on A.", _m10_bard,
         ["dark", "lute", "question"]),
    info("m11_beast", "growl_lute", "Growl and lute",
         "A low horn growls over a pacing frame drum and a lute answers in D minor, waiting on A (the Bard beast).",
         _beast_bard, ["dark", "horn", "question"]),
    # the other three beasts' renders (the plan's four renders, one row); the card plays the
    # revealed beast's own clip, info_m11_beast_<class>, falling back on info_m11_beast
    info("m11_beast", "growl_harp", "Growl and harp",
         "A low horn growls over a pacing frame drum and a harp answers in D minor, waiting on A (the Cleric "
         "beast).",
         _beast_cleric, ["dark", "horn", "question", "cleric"]),
    info("m11_beast", "growl_fiddle", "Growl and fiddle",
         "A low horn growls over a pacing frame drum and a fiddle answers in D minor, settling on D (the Warrior "
         "beast: no box).",
         _beast_warrior, ["dark", "horn", "warrior"]),
    info("m11_beast", "growl_horn", "Growl and horn",
         "A low horn growls over a pacing frame drum and answers itself low in D minor, settling on D (the Paladin "
         "beast: no box).",
         _beast_paladin, ["dark", "horn", "paladin"]),
    # one per class: the clip the card plays for that beast
    info("m11_beast_H", "growl_harp", "Growl and harp", "The Cleric beast: a harp answers the growl, waiting on A.",
         _beast_cleric, ["dark", "horn", "question", "cleric"]),
    info("m11_beast_D", "growl_lute", "Growl and lute", "The Bard beast: a lute answers the growl, waiting on A.",
         _beast_bard, ["dark", "horn", "question"]),
    info("m11_beast_C", "growl_fiddle", "Growl and fiddle", "The Warrior beast: a fiddle answers the growl, settling on D.",
         _beast_warrior, ["dark", "horn", "warrior"]),
    info("m11_beast_S", "growl_horn", "Growl and horn", "The Paladin beast: the horn answers itself low, settling on D.",
         _beast_paladin, ["dark", "horn", "paladin"]),
    info("m12_zone", "minor_to_major", "Minor to major",
         "The three cards on a wooden flute over a flowing harp in D minor, brightening to D major at the end.",
         _m12_zone, ["zone", "flute", "warm"]),
]
