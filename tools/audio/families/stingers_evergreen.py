"""Info pop-ups, the Evergreen group, second set: short stingers that carry one feeling over
the mission music (docs/INFO_POPUPS.md; the owner's feedback on the first set: fewer
instruments, no melody, no shared opening, an emotion that sits on top of dark music).
Built with ``_stingers`` (one or two sound sources, at most three pitched notes, D and A
plus one marked colour note, a clear onset and a natural decay, 2.0-2.4 s).

Rows and the feeling each carries (``_stingers.PALETTE``; three options per row, one per
approach: instrumental, textural, hybrid):

THE LOCATIONS are places, each heard as its own space and sound:
  shrine          sacred: stillness in a chapel (a high choir, a far hand bell, a soft organ)
  cave            mystery: a hollow, dripping dark (a blown bottle, drips, a low marimba octave)
  cave_collapse   impact: the cave comes down (low strings giving way, a modelled
                  rockfall, a timpani blow with stones after it)
  forest          mystery: deep woods (a high far pan pipe, leaves in the wind, an owl's hoots)
  hills           mystery and distance, a warning (team damage follows): a far horn
                  call, wind over open ground, a lookout's trumpet and a far drum
  lake            mystery: still water (a breathy shakuhachi on a high A, lapping water, a harp
                  rippling down)

THE BANES share the dread colour: low, slow, the crypt room; each bane has its own
source, and its mark is one colour note (F, B flat or E flat) in most options:
  bane10 Poisonous Clerics   a sour low choir (F), a censer on its chain, the healer's harp gone dark
  bane12 Duplicitous Bards   a two-faced lute (A rubbing on B flat), a palmed card and a door,
                             a sly fiddle
  bane14 Absorbtion          a bassoon sinking a tritone (E flat), a deep gulp, a low bass and a
                             breath drawn in
  bane15 Tread Carefully     a trembling rub (E flat), tiptoes and a spill of cards, a hushed clarinet
  bane16 Lingering Dread     a bare viol fifth that lingers, a bell tolling twice, a low far bell
                             over a dark cello (F)
  bane21 Eye-Level Sticks    strings flinch (E flat and A), sticks crack, a drum cracks and a fiddle
                             yelps
  bane22 The Fiery Crucible  a cello rising like a flame, a fire flaring, a horn in the heat (E flat)
  bane23 Choose Your Poison  an oboe asking D, E flat?, a slow heartbeat, an oboe left on A

THE BOONS share the fortune colour: high, bright, the hall, a glint of sparkle in most;
each boon its own source:
  boon30 Squad of Siblings   two recorders side by side, a pair of triangles, a celesta octave
  boon31 Selfless Rescue     two horns on a bright fourth, a rush of air and a glint, a violin lift
  boon32 Precision Strike    one high dulcimer D, an arrow's thock and a glint, a glockenspiel A tap
  boon33 Restored Arrows     a harp sweeping up, arrows whistling past, a flute in flight
  boon35 A Close Call        a tremolo that settles from E flat onto D, a breath let out, a celesta

Every option opens on its own source, gesture and pitch within this family (``python3
_stingers.py over stingers_evergreen`` lists any shared opening), and away from the
openings of the cards each row can follow in a queue (Turn's knock, lute A4 and celesta D5
before the Lake and Lingering Dread, the Scarlet Whistle's claves and Declared's rim before
Eye-Level Sticks, Damage's bass drum before Absorbtion, the Chanter's breath before it...).

Three small one-source helpers: ``_repeat`` (one note played again: a bell's toll, an
owl's hoots), ``_stones`` (a modelled rockfall: a crash, stony knocks, a settling roar)
and ``_whoosh`` (an arrow's air going past); ``_damp`` and ``_thin`` shape a source.
"""
from __future__ import annotations

import dataclasses
from typing import Sequence, Tuple

import numpy as np

import _info_common as IC
from _stingers import (SR, A, Layer, air, breath, chains, creak, drips, embers, heartbeat, hit, hits, option, rustle,
                       slide, sparkle, stinger, strike, swell, water, wind)
from _stingers import _from_onset, _layer, _modal, _parse, _place, _prog, _render, _swell_env, _vbandpass

__all__ = ["CANDIDATES"]


# ============================================================================= helpers (one source each)
def _repeat(inst: str, pitch: str, pattern: Sequence[Tuple[float, int]], hold: float = 0.3, gesture: str = "repeat",
            lp: float = 0.0, bank: str = None) -> Layer:
    """One note played again (``pattern`` [(seconds, velocity)...]): a bell's toll, an owl's
    hoot. One pitch, one source; each stroke rings into the next."""
    ps = _parse([pitch])
    (m, _), = ps
    notes = [IC.n(_prog(inst), m, round(t, 4), hold, vel=v, bank=bank) for t, v in pattern]
    x = _from_onset(_render(notes, max(t for t, _ in pattern) + hold + 2.6))
    if lp:
        x = A.lowpass(x, lp, 4)
    return _layer(x, inst, gesture, ps)


def _damp(layer: Layer, at_: float, fall: float) -> Layer:
    """A hand on a ringing source after ``at_`` s (60 dB down in ``fall`` s)."""
    return dataclasses.replace(layer, audio=IC.choke(layer.audio, at_, fall))


def _thin(layer: Layer, hz: float) -> Layer:
    """A source with its body taken off below ``hz`` (water's splash without its slosh)."""
    return dataclasses.replace(layer, audio=A.highpass(layer.audio, hz, 2))


def _stones(dur: float = 2.1, crash: float = 1.0, tumble: float = 1.0, seed: int = 0) -> Layer:
    """A rockfall (one source: stone): a low crash of rock on rock, stones knocking as they
    tumble after it (each a short knock of a few stony modes, dense at first and thinning
    out) and the ground settling in a low roar. Heavy: its weight is the point; the knocks
    are what a phone speaker plays."""
    rng = np.random.default_rng(seed)
    n = A.n_of(dur + 0.4)
    out = np.zeros(n)
    c = A.bandpass(A.noise(0.6, "pink", seed), 150, 1000, 2)
    c = c / (np.std(c) or 1.0) * np.exp(-np.arange(len(c)) / SR / 0.12)
    k = A.n_of(0.004)
    c[:k] *= np.linspace(0.0, 1.0, k)
    out = _place(out, c, 0.0, 0.6 * crash)
    knocks = np.zeros(n)
    t = 0.0
    while t < 0.85 * dur:
        f0 = float(np.exp(rng.uniform(np.log(260.0), np.log(1500.0))))
        t60s = np.array([0.07, 0.045, 0.03, 0.018]) * rng.uniform(0.6, 1.4)
        g = _modal(f0, (1.0, 1.73, 2.61, 3.9), (1.0, 0.55, 0.3, 0.15), t60s, rng, 0.12, 0.25)
        a = float(rng.lognormal(0.0, 0.5)) * np.exp(-t / 0.6) * tumble
        knocks = _place(knocks, g, t, a)
        t += float(rng.exponential(1.0 / (45.0 * np.exp(-t / 0.4) + 4.0)))
    knocks = A.lowpass(knocks, 3500, 2)
    out = out + 0.7 * knocks / (np.max(np.abs(knocks)) or 1.0) * (np.max(np.abs(out)) or 1.0)
    r = A.highpass(A.lowpass(A.noise(dur + 0.4, "brown", seed + 1), 150, 4), 30, 2)
    r = r / (np.std(r) or 1.0) * _swell_env(n, 0.12, dur, -4.0, 45.0)
    out = out + 0.12 * crash * r
    return _layer(out, "stones", "texture", weight=True)


def _whoosh(times: Sequence[float] = (0.0, 0.3), dur: float = 0.5, seed: int = 0, hi: float = 3600.0,
            lo: float = 900.0, fall: float = 0.75) -> Layer:
    """Something flying past (an arrow): moving air whose band falls as it goes by, once at
    each of ``times``, each pass ``fall`` times the last."""
    total = max(times) + dur + 0.3
    out = np.zeros(A.n_of(total))
    for i, t in enumerate(times):
        n = A.n_of(dur)
        x = A.noise(dur, "pink", seed + i)
        y = _vbandpass(x, np.geomspace(hi, lo, n), 1.8)
        tt = np.arange(n) / SR
        env = np.exp(-0.5 * ((tt - 0.3 * dur) / (0.15 * dur)) ** 2)
        y = y / (np.std(y) or 1.0) * env * (fall ** i)
        out = _place(out, y, t)
    return _layer(out, "air", "whoosh")


# ============================================================================= Shrine (sacred)
def _shrine_choir() -> np.ndarray:
    # a high choir breathes A and D (an open fourth), no third, in a tall stone chapel
    return stinger(swell("choir", "A4+D5", dur=1.9, peak=0.5, start_db=-7, vel=70), room="chapel")


def _shrine_far_bell() -> np.ndarray:
    # one hand bell on a high D, rung somewhere far off in the chapel, still air around it
    return stinger(strike("hand_bell", "D6", vel=62, hold=2.0).far(0.45),
                   air(2.3, bright=0.2, peak=0.6, start_db=-10, seed=11).db(-16), room="chapel")


def _shrine_organ() -> np.ndarray:
    # a soft church organ holds A and D, a small altar triangle touched as it starts
    return stinger(swell("organ", "A3+D4", dur=1.8, peak=0.35, start_db=-6, vel=60),
                   hit("triangle", vel=52).db(-9), room="chapel")


# ============================================================================= Cave (mystery)
def _cave_bottle() -> np.ndarray:
    # a hollow blown note, like breath across a jar's mouth, sent round the cave's walls
    return stinger(swell("bottle", "D5", dur=1.7, peak=0.3, start_db=-6, vel=70), room="cave")


def _cave_drips() -> np.ndarray:
    # three drops fall into a dark pool (tuned to D and A), the cave's cold air under them
    return stinger(drips(3, spacing=0.5, pitches=("D6", "A5", "D6"), seed=2),
                   air(2.3, bright=0.1, peak=0.5, start_db=-8, seed=12).db(-14), room="cave")


def _cave_marimba() -> np.ndarray:
    # a low marimba octave on A, struck softly and echoing; a single drop answers from the
    # dark (the octave above gives the phone something: A3 alone was all low-mid, mastered
    # 3 dB louder than the rest on full-range speakers)
    return stinger(strike("marimba", "A3+A4", vel=74, hold=1.5),
                   drips(1, pitches=("A5",), seed=6).at(0.62).db(-5), room="cave")


# ============================================================================= Cave collapses (impact)
def _collapse_strings() -> np.ndarray:
    # the low strings strike hard on D and fall away to A beneath it: the roof gives
    return stinger(slide("strings", "D3", "A2", dur=1.7, glide=(0.08, 0.55), peak=0.03, start_db=-2, vel=112,
                         weight=True), room="cave")


def _collapse_rockfall() -> np.ndarray:
    # rock crashes on rock, stones tumble after it and the ground settles in a low roar
    return stinger(_stones(2.1, seed=13), room="cave")


def _collapse_timpani_stones() -> np.ndarray:
    # one timpani D struck hard, stones and dust coming down after it
    return stinger(strike("timpani", "D3", vel=116),
                   _stones(2.0, crash=0.4, tumble=1.2, seed=19).at(0.05).db(-3), room="cave")


# ============================================================================= Forest (mystery)
def _forest_pipe() -> np.ndarray:
    # a pan pipe's high, breathy D, heard far off between the trees (D6: the Cave's bottle
    # holds D5, and Turn's celesta opens on D5)
    return stinger(swell("pan_flute", "D6", dur=1.8, peak=0.35, start_db=-6, vel=64).far(0.55),
                   room=(0.55, 0.12, 0.6))


def _forest_leaves() -> np.ndarray:
    # dry leaves stir as the wind moves through the branches
    return stinger(rustle(0.9, "leaves", density=0.9, seed=4),
                   wind(2.3, strength=0.3, peak=0.5, seed=14).db(-5), room=(0.55, 0.12, 0.6))


def _forest_owl() -> np.ndarray:
    # an owl's two low hoots (an ocarina on A), far off; leaves rustle near by
    return stinger(_repeat("ocarina", "A4", [(0.0, 76), (0.5, 66)], hold=0.34, gesture="hoots").far(0.55),
                   rustle(0.8, "leaves", density=0.6, seed=7).at(0.9).db(-7), room=(0.55, 0.12, 0.6))


# ============================================================================= Hills (mystery: distance, a warning)
def _hills_horn() -> np.ndarray:
    # a horn calls from A up to D across the hills, small with distance
    return stinger(slide("horn", "A3", "D4", dur=1.9, glide=(0.18, 0.45), peak=0.35, start_db=-5, vel=82).far(0.6),
                   room="open")


def _hills_wind() -> np.ndarray:
    # wind across open ground, a hollow whistle riding the gusts
    return stinger(wind(2.3, strength=0.65, whistle=0.35, peak=0.35, seed=15), room="open")


def _hills_trumpet_drum() -> np.ndarray:
    # a lookout's trumpet on A, far off, a drum beaten farther away with it: something is coming
    return stinger(swell("trumpet", "A4", dur=1.7, peak=0.3, start_db=-5, vel=74).far(0.75),
                   hit("bass_drum", vel=110, weight=False).far(0.85).db(-4), room="open")


# ============================================================================= Lake (mystery)
def _lake_shakuhachi() -> np.ndarray:
    # a breathy bamboo flute on a high A drifts over still water (the Lake follows Turn,
    # whose lute opens on A4; the shakuhachi's low D4 is too pure a tone for a phone)
    return stinger(swell("shakuhachi", "A5", dur=1.8, peak=0.35, start_db=-6, vel=66).far(0.3),
                   room=(0.65, 0.16, 0.4))


def _lake_water() -> np.ndarray:
    # small waves lap against the stones of the shore (the splash and bubbles, not the slosh)
    return stinger(_thin(water(2.3, "lap", seed=3), 350.0), room=(0.65, 0.16, 0.4))


def _lake_harp_ripple() -> np.ndarray:
    # a harp ripples down from D to A, slowly, as water moves under it (from the top: Pilgrim
    # match and No damage open their harps on A5)
    return stinger(strike("harp", "A5+D6", spread=0.16, down=True, vel=60, hold=1.8),
                   water(2.2, "stream", seed=8).db(-11), room=(0.65, 0.16, 0.4))


# ============================================================================= Bane 10 Poisonous Clerics (dread, F)
def _bane10_choir() -> np.ndarray:
    # a low choir sings D with a sour minor third: a hymn gone bad (the choir, not the hum:
    # the hum's near-pure D3 and F3 sat on the music's own cello D3 and viola F3, all in the
    # low-mid, and mastered 4.5 dB louder than the rest)
    return stinger(swell("choir", "D3+F3*", dur=1.9, peak=0.6, start_db=-8, vel=76), room="crypt")


def _bane10_censer() -> np.ndarray:
    # a censer swung on its chain, its smoke hanging in the cold crypt air
    return stinger(chains(1.0, shake=0.45, seed=4),
                   air(2.3, bright=0.1, peak=0.4, start_db=-6, seed=16).db(-9), room="crypt")


def _bane10_harp() -> np.ndarray:
    # the healer's harp plucks a dark F and D, a single poisoned drop falls after
    return stinger(strike("harp", "F3*+D4", vel=72, hold=1.8),
                   drips(1, pitches=("A5",), seed=3).at(0.55).db(-6), room="crypt")


# ========================================================================= Bane 12 Duplicitous Bards (dread, B flat)
def _bane12_lute() -> np.ndarray:
    # a lute plucks A against a sour B flat: two faces on one string
    return stinger(strike("lute", "A3+Bb3*", vel=86, hold=1.9), room="crypt")


def _bane12_door_card() -> np.ndarray:
    # a card slides out of your hand and a door creaks behind you (the card first: the
    # corrupt Mother's and the Druid's cards open on the same modelled creak)
    return stinger(rustle(0.45, "cards", density=0.5, seed=5),
                   creak(0.9, tension=0.4, seed=5).at(0.28).db(5), room="crypt")


def _bane12_fiddle() -> np.ndarray:
    # a fiddle creeps up from A onto a sly B flat as it swells; a card slips away under it
    return stinger(slide("fiddle", "A3", "Bb3*", dur=1.8, glide=(0.16, 0.32), peak=0.45, start_db=-5, vel=72),
                   rustle(0.4, "cards", density=0.7, seed=9).at(0.1).db(-10), room="crypt")


# ============================================================================= Bane 14 Absorbtion (dread, E flat)
def _bane14_bassoon() -> np.ndarray:
    # a bassoon sinks from a sour E flat down to A: the zone swallows the attack
    return stinger(slide("bassoon", "Eb3*", "A2", dur=1.8, glide=(0.2, 0.75), peak=0.15, start_db=-5, vel=84),
                   room="crypt")


def _bane14_gulp() -> np.ndarray:
    # dark water closing over a soft deep thud: a gulp (the water first: Absorbtion comes
    # right after Damage, whose deep drum is the same bass-drum sample)
    return stinger(_thin(water(2.0, "lap", seed=11), 240.0),
                   hit("felt_drum", vel=92, weight=False).at(0.16).db(-1), onset=0.16, room="crypt")


def _bane14_drawn_in() -> np.ndarray:
    # a low bass closes on D, then a breath is drawn in after it (the bass first: the
    # Chanter, earlier in the same attack, opens on a breath drawn in)
    return stinger(swell("bass", "D3", dur=1.6, peak=0.04, start_db=-3, vel=100),
                   breath(0.4, "in", seed=3).at(0.42).db(-6), room="crypt")


# ============================================================================= Bane 15 Tread Carefully (dread, E flat)
def _bane15_tremolo() -> np.ndarray:
    # thin strings tremble on D and E flat, hushed: tread carefully
    return stinger(swell("tremolo_strings", "D4+Eb4*", dur=1.8, peak=0.5, start_db=-8, vel=60), room="crypt")


def _bane15_tiptoe() -> np.ndarray:
    # two muffled careful steps, then the cards spill everywhere
    return stinger(hits("frame_drum", [(0.0, 70), (0.42, 58)], felt=True, weight=False),
                   rustle(0.8, "cards", density=1.4, seed=10).at(0.72).db(3), room="crypt")


def _bane15_clarinet_hush() -> np.ndarray:
    # a low clarinet holds its breath on A, hushed, and then the cards spill (no slide: the
    # oboe of Choose Your Poison already creeps from D up to E flat)
    return stinger(swell("clarinet", "A3", dur=1.8, peak=0.35, start_db=-6, vel=64),
                   rustle(0.7, "cards", density=1.3, seed=12).at(0.85).db(-2), room="crypt")


# ============================================================================= Bane 16 Lingering Dread (dread, F)
def _bane16_viol() -> np.ndarray:
    # a viol holds a bare D and A, slow and low, and lingers as it fades
    return stinger(swell("viol", "D3+A3", dur=1.95, peak=0.75, start_db=-9, vel=70), room="crypt")


def _bane16_toll() -> np.ndarray:
    # a deep bell tolls twice, far down in the crypt
    return stinger(_damp(_repeat("bell", "A3", [(0.0, 80), (0.8, 62)], hold=1.4, gesture="toll", lp=4500),
                         1.3, 1.6).far(0.4), room="crypt")


def _bane16_far_bell_cello() -> np.ndarray:
    # a low far bell on D, a hand on it, a cello's dark F and A swelling under it (D4:
    # Lingering Dread follows Turn, whose celesta rings D5)
    return stinger(_damp(strike("bell", "D4", vel=70, hold=1.8), 1.2, 1.0).far(0.6),
                   swell("cello", "A2+F3*", dur=1.7, peak=0.6, start_db=-10, vel=72).db(-2), room="crypt")


# ============================================================================= Bane 21 Eye-Level Sticks (dread, E flat)
def _bane21_strings() -> np.ndarray:
    # the strings flinch: a sharp E flat and A struck at once, then falling back
    return stinger(swell("strings", "Eb4*+A4", dur=1.4, peak=0.03, start_db=-2, vel=112), room="crypt")


def _bane21_sticks() -> np.ndarray:
    # two sticks crack sharply at eye level; cold air after
    return stinger(hits("woodblock", [(0.0, 116), (0.13, 100)]),
                   air(2.3, bright=0.2, peak=0.2, start_db=-6, seed=17).db(-12), room="crypt")


def _bane21_fiddle_snap() -> np.ndarray:
    # a dry drum cracks and a fiddle yelps up from A to E flat (the fiddle is the reference
    # level; a tabor, not a rim: Declared can come just before, on a rim)
    return stinger(slide("fiddle", "A4", "Eb5*", dur=1.3, glide=(0.02, 0.14), peak=0.05, start_db=-3, vel=100)
                   .at(0.03), hit("tabor", vel=104).db(0), room="crypt")


# ======================================================================= Bane 22 The Fiery Crucible (dread, E flat)
def _bane22_cello() -> np.ndarray:
    # a cello rises from D to A like a flame catching, then sinks back (D4-A4, above the
    # music's own cello on D3: an octave lower it sat in the music's low-mid and mastered
    # 3.6 dB louder than the rest on full-range speakers)
    return stinger(slide("cello", "D4", "A4", dur=1.8, glide=(0.05, 0.4), peak=0.5, start_db=-7, vel=84),
                   room="crypt")


def _bane22_fire() -> np.ndarray:
    # the crucible's fire flares and crackles; the heat roars like a bellows under it
    # (seed 4: it flares and dies down, each half second quieter, so no late pop sounds like
    # an accent; and its crackle is not mission 3's, which uses seed 3)
    return stinger(embers(2.2, crackle=1.2, flare=True, seed=4),
                   air(2.2, bright=0.15, peak=0.25, start_db=-6, seed=18).db(-6), room="crypt")


def _bane22_horn_fire() -> np.ndarray:
    # a horn swells on E flat and A, a tritone in the heat, the fire crackling with it
    # (seed 20: a fire that dies down, no late pop)
    return stinger(swell("horn", "Eb3*+A3", dur=1.7, peak=0.5, start_db=-8, vel=78),
                   embers(2.0, crackle=0.9, flare=False, seed=20).db(-5), room="crypt")


# ======================================================================= Bane 23 Choose Your Poison (dread, E flat)
def _bane23_oboe() -> np.ndarray:
    # an oboe holds D and rises to E flat as it swells, a question left hanging (the rise
    # lands at the swell's peak: later, the E flat came 18 dB down and was hardly heard)
    return stinger(slide("oboe", "D4", "Eb4*", dur=1.8, glide=(0.2, 0.36), peak=0.55, start_db=-6, vel=76),
                   room="crypt")


def _bane23_heartbeat() -> np.ndarray:
    # a slow heartbeat on a felt drum, twice: choose (its sub-bass left to the music)
    return stinger(heartbeat(2, bpm=56, vel=100).heavy(False), room="crypt")


def _bane23_oboe_heart() -> np.ndarray:
    # an oboe waits on A over a soft heartbeat: the choice is yours
    return stinger(swell("oboe", "A4", dur=1.8, peak=0.25, start_db=-6, vel=70),
                   heartbeat(2, bpm=60, vel=84).db(-9), room="crypt")


# ============================================================================= Boon 30 Squad of Siblings (fortune)
def _boon30_recorders() -> np.ndarray:
    # two recorders side by side on D and A, bright and together
    return stinger(swell("recorder", "D5+A5", dur=1.7, peak=0.25, start_db=-6, vel=72), room="hall")


def _boon30_triangles() -> np.ndarray:
    # two triangles struck a moment apart, a glint of luck after them
    return stinger(_damp(hits("triangle", [(0.0, 84), (0.1, 74)]), 0.9, 1.3),
                   sparkle(1.6, count=6, seed=5).at(0.08).db(-8), room="hall")


def _boon30_celesta() -> np.ndarray:
    # a celesta plays D and the D above together, big and little, a shimmer after
    return stinger(strike("celesta", "D5+D6", vel=72, hold=1.8),
                   sparkle(1.9, count=7, seed=4).at(0.12).db(-10), room="hall")


# ============================================================================= Boon 31 Selfless Rescue (fortune)
def _boon31_horns() -> np.ndarray:
    # two horns ring out on A and D, a bright fourth: help is here
    return stinger(swell("horn", "A4+D5", dur=1.6, peak=0.18, start_db=-4, vel=88), room="hall")


def _boon31_rush_glint() -> np.ndarray:
    # a rush of air as you are pulled clear, a glint of light after it
    return stinger(air(1.5, bright=0.6, peak=0.12, start_db=-5, seed=6),
                   sparkle(2.1, count=9, seed=7).at(0.1).db(-4), room="hall")


def _boon31_violin_cloak() -> np.ndarray:
    # a violin lifts from A to D as a cloak is grabbed: pulled to safety
    return stinger(slide("violin", "A4", "D5", dur=1.7, glide=(0.12, 0.35), peak=0.3, start_db=-6, vel=72),
                   rustle(0.5, "cloth", density=1.2, seed=8).db(-4), room="hall")


# ============================================================================= Boon 32 Precision Strike (fortune)
def _boon32_dulcimer() -> np.ndarray:
    # one bright hammered dulcimer D, high and clean: right on target
    return stinger(strike("hammered_dulcimer", "D6", vel=96, hold=1.9), room="hall")


def _boon32_thock() -> np.ndarray:
    # an arrow thocks into the straw target, a glint after it
    return stinger(hit("bodhran", vel=108, weight=False), sparkle(2.1, count=8, seed=8).at(0.03).db(-5), room="hall")


def _boon32_glock_tap() -> np.ndarray:
    # a glockenspiel rings on a high A with a stick's tap: a clean hit (A5: the dulcimer
    # option is the row's one bright D6)
    return stinger(strike("glockenspiel", "A5", vel=78, hold=1.8), hit("rim", vel=92).db(-5), room="hall")


# ============================================================================= Boon 33 Restored Arrows (fortune)
def _boon33_harp() -> np.ndarray:
    # a harp sweeps up D, A and D, bright: the quiver is full again
    return stinger(strike("harp", "D5+A5+D6", spread=0.07, vel=72, hold=1.8), room="hall")


def _boon33_arrows() -> np.ndarray:
    # two arrows whistle past, a glint as they land
    return stinger(_whoosh((0.0, 0.26), dur=0.5, seed=21), sparkle(1.5, count=6, seed=7).at(0.35).db(-6),
                   room="hall")


def _boon33_flute() -> np.ndarray:
    # a flute lifts from A to D as an arrow flies
    return stinger(slide("flute", "A5", "D6", dur=1.7, glide=(0.04, 0.3), peak=0.25, start_db=-6, vel=72),
                   _whoosh((0.0,), dur=0.45, seed=23).db(-6), room="hall")


# ============================================================================= Boon 35 A Close Call (fortune)
def _boon35_tremolo() -> np.ndarray:
    # strings tremble on a nervous E flat and settle onto D as they swell, then ring out on
    # D: relief (settling later, the D came 27 dB down and the clip was only the E flat)
    return stinger(slide("tremolo_strings", "Eb5*", "D5", dur=1.9, glide=(0.08, 0.24), peak=0.45, start_db=-4, vel=70),
                   room="hall")


def _boon35_breath() -> np.ndarray:
    # a glint of luck, then a long breath let out: that was close (the glint leads, so it
    # does not open like Yield's sigh a few cards earlier)
    return stinger(sparkle(2.1, count=9, seed=9), breath(1.3, "out", seed=5).at(0.08).db(3), room="hall")


def _boon35_celesta() -> np.ndarray:
    # a celesta A, a breath of relief let out with it
    return stinger(strike("celesta", "A5", vel=72, hold=1.8), breath(1.1, "out", seed=6).at(0.05).db(-4),
                   room="hall")


# ============================================================================= the candidates
CANDIDATES = [
    # Shrine
    option("shrine", "choir_fourth", "High choir, A and D", "A high choir breathes A and D, no third, in a tall "
           "chapel.",
           _shrine_choir, "sacred", "instrumental", ["stillness", "voices"]),
    option("shrine", "far_hand_bell", "Hand bell, far off", "One hand bell on a high D rung far off, still air "
           "around it.", _shrine_far_bell, "sacred", "textural", ["bell", "distance"]),
    option("shrine", "soft_organ", "Soft organ and altar triangle", "A soft church organ holds A and D; a small "
           "triangle touched as it starts.", _shrine_organ, "sacred", "hybrid", ["organ", "calm"]),
    # Cave
    option("cave", "hollow_bottle", "Hollow blown note", "A hollow blown D, like breath over a jar, sent round the "
           "cave's walls.", _cave_bottle, "mystery", "instrumental", ["hollow", "echo"]),
    option("cave", "dark_drips", "Drips in the dark", "Three drops fall into a dark pool, cold cave air under them.",
           _cave_drips, "mystery", "textural", ["water", "echo"]),
    option("cave", "low_marimba", "Low marimba, one drop", "A soft low marimba octave on A echoing; a single drop "
           "answers.",
           _cave_marimba, "mystery", "hybrid", ["wood", "echo"]),
    # Cave collapses
    option("cave_collapse", "strings_fall", "Low strings give way", "The low strings strike hard on D and fall away "
           "to A beneath it.", _collapse_strings, "impact", "instrumental", ["collapse", "heavy"]),
    option("cave_collapse", "rockfall", "Rockfall", "Rock crashes on rock, stones tumble after it and the ground "
           "settles in a low roar.", _collapse_rockfall, "impact", "textural", ["collapse", "stone"]),
    option("cave_collapse", "timpani_stones", "Timpani blow, stones fall", "One timpani D struck hard, stones and dust "
           "coming down after it.", _collapse_timpani_stones, "impact", "hybrid", ["collapse", "heavy", "stone"]),
    # Forest
    option("forest", "far_pipe", "Far pipe in the trees", "A pan pipe's high, breathy D heard far off between the "
           "trees.",
           _forest_pipe, "mystery", "instrumental", ["woods", "distance"]),
    option("forest", "leaves_wind", "Leaves in the wind", "Dry leaves stir as the wind moves through the branches.",
           _forest_leaves, "mystery", "textural", ["woods", "wind"]),
    option("forest", "owl_leaves", "Owl over the leaves", "An owl's two low hoots far off; leaves rustle near by.",
           _forest_owl, "mystery", "hybrid", ["woods", "night"]),
    # Hills
    option("hills", "far_horn_call", "Horn call across the hills", "A horn calls from A up to D, small with "
           "distance: a warning.", _hills_horn, "mystery", "instrumental", ["distance", "warning"]),
    option("hills", "hill_wind", "Wind over open ground", "Wind across the hills, a hollow whistle riding the gusts.",
           _hills_wind, "mystery", "textural", ["distance", "wind"]),
    option("hills", "trumpet_far_drum", "Lookout's trumpet, far drum", "A lookout's trumpet on A far off, a drum "
           "beaten farther away: something is coming.", _hills_trumpet_drum, "mystery", "hybrid",
           ["distance", "warning"]),
    # Lake
    option("lake", "shakuhachi", "Breathy flute over water", "A breathy bamboo flute on a high A drifts over still "
           "water.",
           _lake_shakuhachi, "mystery", "instrumental", ["water", "stillness"]),
    option("lake", "lapping_water", "Water lapping", "Small waves lap against the stones of the shore.",
           _lake_water, "mystery", "textural", ["water"]),
    option("lake", "harp_ripple", "Harp ripple on the water", "A harp ripples slowly down from D to A over moving "
           "water.", _lake_harp_ripple, "mystery", "hybrid", ["water", "harp"]),
    # Bane 10 Poisonous Clerics
    option("bane10", "sour_hum", "Sour low choir", "A low choir sings D with a sour minor third: a hymn gone bad.",
           _bane10_choir, "dread", "instrumental", ["bane", "voices", "poison"]),
    option("bane10", "swinging_censer", "Censer on its chain", "A censer swung on its chain, its smoke hanging in the "
           "cold crypt air.", _bane10_censer, "dread", "textural", ["bane", "chains", "poison"]),
    option("bane10", "dark_harp_drop", "Dark harp, one drop", "The healer's harp plucks a dark F and D; one poisoned "
           "drop falls.", _bane10_harp, "dread", "hybrid", ["bane", "harp", "poison"]),
    # Bane 12 Duplicitous Bards
    option("bane12", "two_faced_lute", "Two-faced lute", "A lute plucks A against a sour B flat: two faces on one "
           "string.", _bane12_lute, "dread", "instrumental", ["bane", "sly"]),
    option("bane12", "door_and_card", "Palmed card, creaking door", "A card slides out of your hand and a door creaks "
           "behind you.", _bane12_door_card, "dread", "textural", ["bane", "sly", "cards"]),
    option("bane12", "sly_fiddle", "Sly fiddle", "A fiddle creeps up from A onto a sly B flat; a card slips away.",
           _bane12_fiddle, "dread", "hybrid", ["bane", "sly"]),
    # Bane 14 Absorbtion
    option("bane14", "sinking_bassoon", "Bassoon sinks", "A bassoon sinks from a sour E flat down to A: swallowed.",
           _bane14_bassoon, "dread", "instrumental", ["bane", "swallow"]),
    option("bane14", "deep_gulp", "A deep gulp", "Dark water closing over a soft deep thud.",
           _bane14_gulp, "dread", "textural", ["bane", "swallow", "water"]),
    option("bane14", "drawn_in", "Low bass, a breath drawn in", "A low bass closes on D, then a breath is drawn in.",
           _bane14_drawn_in, "dread", "hybrid", ["bane", "swallow"]),
    # Bane 15 Tread Carefully
    option("bane15", "trembling_rub", "Strings tremble", "Thin strings tremble on D and E flat, hushed.",
           _bane15_tremolo, "dread", "instrumental", ["bane", "tension"]),
    option("bane15", "tiptoe_spill", "Tiptoes, then a spill", "Two muffled careful steps, then the cards spill "
           "everywhere.", _bane15_tiptoe, "dread", "textural", ["bane", "cards"]),
    option("bane15", "hushed_clarinet", "Hushed clarinet, cards spill", "A low clarinet holds its breath on A, "
           "hushed; then the cards spill.", _bane15_clarinet_hush, "dread", "hybrid",
           ["bane", "tension", "cards"]),
    # Bane 16 Lingering Dread
    option("bane16", "lingering_viol", "Lingering viol", "A viol holds a bare low D and A and lingers as it fades.",
           _bane16_viol, "dread", "instrumental", ["bane", "slow"]),
    option("bane16", "tolling_bell", "Bell tolls twice", "A deep bell tolls twice, far down in the crypt.",
           _bane16_toll, "dread", "textural", ["bane", "bell", "slow"]),
    option("bane16", "far_bell_cello", "Far bell, dark cello", "A low far bell on D, a cello's dark F and A swelling "
           "under it.", _bane16_far_bell_cello, "dread", "hybrid", ["bane", "bell"]),
    # Bane 21 Eye-Level Sticks
    option("bane21", "flinching_strings", "Strings flinch", "A sharp E flat and A struck at once on the strings, "
           "falling back.", _bane21_strings, "dread", "instrumental", ["bane", "startle"]),
    option("bane21", "cracking_sticks", "Sticks crack", "Two sticks crack sharply at eye level; cold air after.",
           _bane21_sticks, "dread", "textural", ["bane", "startle", "wood"]),
    option("bane21", "fiddle_yelp", "Crack and a fiddle yelp", "A dry drum cracks and a fiddle yelps up from A to "
           "E flat.", _bane21_fiddle_snap, "dread", "hybrid", ["bane", "startle"]),
    # Bane 22 The Fiery Crucible
    option("bane22", "rising_cello", "Cello rises like a flame", "A cello rises from D to A like a flame catching, "
           "then sinks back.", _bane22_cello, "dread", "instrumental", ["bane", "fire"]),
    option("bane22", "crucible_fire", "Crucible fire", "The fire flares and crackles, the heat roaring like a bellows.",
           _bane22_fire, "dread", "textural", ["bane", "fire"]),
    option("bane22", "horn_in_fire", "Horn in the heat", "A horn swells on E flat and A, a tritone, the fire "
           "crackling with it.", _bane22_horn_fire, "dread", "hybrid", ["bane", "fire"]),
    # Bane 23 Choose Your Poison
    option("bane23", "oboe_question", "Oboe asks", "An oboe holds D and rises to E flat: a question left hanging.",
           _bane23_oboe, "dread", "instrumental", ["bane", "question"]),
    option("bane23", "slow_heartbeat", "Slow heartbeat", "A slow heartbeat on a felt drum, twice: choose.",
           _bane23_heartbeat, "dread", "textural", ["bane", "question"]),
    option("bane23", "oboe_heartbeat", "Oboe over a heartbeat", "An oboe waits on A over a soft heartbeat.",
           _bane23_oboe_heart, "dread", "hybrid", ["bane", "question"]),
    # Boon 30 Squad of Siblings
    option("boon30", "two_recorders", "Two recorders together", "Two recorders side by side on D and A, bright.",
           _boon30_recorders, "fortune", "instrumental", ["boon", "together"]),
    option("boon30", "triangle_pair", "A pair of triangles", "Two triangles struck a moment apart, a glint after.",
           _boon30_triangles, "fortune", "textural", ["boon", "together"]),
    option("boon30", "celesta_octave", "Celesta octave, shimmer", "A celesta plays D and the D above together, a "
           "shimmer after.", _boon30_celesta, "fortune", "hybrid", ["boon", "together"]),
    # Boon 31 Selfless Rescue
    option("boon31", "bright_horns", "Two horns, a bright fourth", "Two horns ring out on A and D: help is here.",
           _boon31_horns, "fortune", "instrumental", ["boon", "rescue"]),
    option("boon31", "rush_glint", "A rush of air, a glint", "A rush of air as you are pulled clear, a glint of light "
           "after it.", _boon31_rush_glint, "fortune", "textural", ["boon", "rescue", "air"]),
    option("boon31", "violin_lift", "Violin lifts, cloak grabbed", "A violin lifts from A to D as a cloak is grabbed: "
           "pulled to safety.", _boon31_violin_cloak, "fortune", "hybrid", ["boon", "rescue", "rising"]),
    # Boon 32 Precision Strike
    option("boon32", "high_dulcimer", "One high dulcimer D", "One bright hammered dulcimer D, clean: right on "
           "target.", _boon32_dulcimer, "fortune", "instrumental", ["boon", "precise"]),
    option("boon32", "arrow_thock", "Thock and a glint", "An arrow thocks into the straw target, a glint after it.",
           _boon32_thock, "fortune", "textural", ["boon", "precise"]),
    option("boon32", "glock_tap", "Glockenspiel, clean tap", "A glockenspiel rings on a high A with a stick's tap.",
           _boon32_glock_tap, "fortune", "hybrid", ["boon", "precise", "bell"]),
    # Boon 33 Restored Arrows
    option("boon33", "harp_sweep", "Harp sweeps up", "A harp sweeps up D, A and D, bright: the quiver is full again.",
           _boon33_harp, "fortune", "instrumental", ["boon", "harp", "rising"]),
    option("boon33", "arrows_past", "Arrows whistle past", "Two arrows whistle past, a glint as they land.",
           _boon33_arrows, "fortune", "textural", ["boon", "air"]),
    option("boon33", "flute_flight", "Flute in flight", "A flute lifts from A to D as an arrow flies past.",
           _boon33_flute, "fortune", "hybrid", ["boon", "air", "rising"]),
    # Boon 35 A Close Call
    option("boon35", "tremolo_settles", "Tremolo settles on D", "Strings tremble on a nervous E flat and settle onto "
           "D at the last moment.", _boon35_tremolo, "fortune", "instrumental", ["boon", "relief"]),
    option("boon35", "glint_breath_out", "Glint, then a breath let out", "A glint of luck, then a long breath let "
           "out: that was close.",
           _boon35_breath, "fortune", "textural", ["boon", "relief"]),
    option("boon35", "celesta_relief", "Celesta, a sigh of relief", "A celesta A and a breath of relief let out with "
           "it.", _boon35_celesta, "fortune", "hybrid", ["boon", "relief"]),
]
