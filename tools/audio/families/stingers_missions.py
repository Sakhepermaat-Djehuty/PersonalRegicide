"""Info pop-up stingers, the missions group: the zone cards, Carry damage, the pilgrims,
Zone filled!, Captured piles, the corrupted Cleric and Bard of mission 10, the beasts
of mission 11 and the zone of mission 12.

Each card gets three options (the four class beasts two), each a different approach
(instrumental, textural, hybrid), built with the stinger toolkit (_stingers.py): one or two
sound sources, one to three pitched notes on D and A (one colour note at most, marked "*"),
a clear onset when the card appears, then the gesture's own decay, 2.0-2.4 s. They sit on
top of dark mission music: a feeling, not a tune. Cards of one kind share a colour so the
owner learns them, and each row keeps its own sources:

    Zone grows (3, 5, 10,  threat, encroaching: something low swells toward you over half a
      12)                  second and sinks back (a swell, a roll building, footfalls
                           closing in); each mission tints it: 3 fire, 5 weight, 10 crumbling,
                           12 growth (a dark reed, the ground heaving under leaves, low
                           voices and groaning roots)
    Carry damage (5)       impact: one blow, and its force travelling on (an echo, a rush
                           of air past you to a far blow, a trombone blow and its wind)
    Pilgrim arrives (7)    sacred, gentle: a wanderer on the road (a low pan pipe, soft steps
                           in the wind, a staff bell and a hum); it follows Turn, so it opens
                           on neither of Turn's pitches (A4, D5)
    Pilgrim match (7)      mystery: two things meet on one note (A)
    Zone filled! (8)       triumph, a release: an organ chord opening out, the wind dropping and a
                           breath let out, a dulcimer ringing as the air clears; it follows
                           Defeated or Exact kill!, so none of their horns, bells, cymbals,
                           trumpets or triangles
    Captured piles (9)     sorrow: a falling minor third, chains and a sigh, mourning voices
    Cleric enemy (10)      dread (the banes' colour): healing turned sour, Eb against D
    Bard enemy (10)        dread: a sly, sour pluck or bend, Eb against D; dice thrown and a
                           card palmed
    Beast (11)             threat: the beast's voice is a low horn growl on a D octave (a
                           stab and a heavy fall); the class beasts lead with their class's
                           own sound (Cleric voices or harp, Bard lute or cards, Warrior
                           a clash of iron or a snare, Paladin organ or bell) with the beast
                           under it (the Warrior's no longer opens on Damage's bass drum)

    python3 tools/audio/build.py stingers_missions
    python3 tools/audio/families/_stingers.py over stingers_missions
"""
from __future__ import annotations

import dataclasses
import os
import sys

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _stingers import (  # noqa: E402
    SR, A, Layer, air, breath, chains, creak, drips, embers, hit, hits, option, roll, rumble, rustle, slide, stinger,
    strike, swell, water, wind,
)
from _stingers import _layer, _modal, _place  # noqa: E402

# fires that flare at the start and then die down (seeds measured: each later half second
# quieter than the one before), so no late pop sounds like an accent: (crackle, seed)
_FIRE_BRIGHT = (1.0, 3)
_FIRE_LOW = (0.8, 13)


def _dying(layer: Layer, after: float = 0.4, db_per_s: float = 12.0) -> Layer:
    """A texture dying down: steadily quieter (dB-linear) after its first ``after`` s, so a
    fire's later pops sink into its tail instead of sounding like accents."""
    t = np.arange(len(layer.audio)) / float(SR)
    fall = 10 ** (-np.maximum(0.0, t - after) * db_per_s / 20.0)
    return dataclasses.replace(layer, audio=layer.audio * fall)


def _deeper(layer: Layer, factor: float = 1.5) -> Layer:
    """A modelled breath played slower: a bigger chest (lower formants, a longer exhale).
    Also retunes a drum whose ring is off the key (1.05: the frame drum's E flat to D)."""
    return dataclasses.replace(layer, audio=signal.resample_poly(layer.audio, int(round(factor * 20)), 20))


def _dice(count: int = 2, seed: int = 0) -> Layer:
    """Dice thrown on a wooden table (one source): each die bounces, its knocks quicker and
    softer, a small hard click over the table's short wooden knock; darkened above 5 kHz."""
    rng = np.random.default_rng(seed)
    out = np.zeros(A.n_of(1.2))
    for d in range(count):
        t = d * rng.uniform(0.008, 0.025)
        gap, a = rng.uniform(0.09, 0.12), (1.0 if d == 0 else 0.75)
        while gap > 0.012 and a > 0.04:
            click = _modal(rng.uniform(1500, 2400), (1.0, 1.52, 2.31), (1.0, 0.5, 0.25),
                           np.array([0.025, 0.016, 0.011]) * rng.uniform(0.8, 1.25), rng, 0.08, 0.25)
            knock = _modal(rng.uniform(380, 480), (1.0, 2.13), (1.0, 0.3), np.array([0.035, 0.02]), rng, 0.08, 0.0)
            out = _place(out, click + 0.8 * knock, t, a)
            t += gap
            gap *= rng.uniform(0.6, 0.72)
            a *= rng.uniform(0.6, 0.72)
    return _layer(A.lowpass(out, 5000, 2), "dice", "texture")


# ============================================================================= 3 · Zone grows (fire)
def _m3_brass():
    """A trombone D swelling up toward you like a flame catching, then sinking back."""
    return stinger(swell("trombone", "D3", dur=1.9, peak=0.5, start_db=-8, vel=100), room="hall")


def _m3_fire():
    """A fire catching and its flames roaring up toward you, then dying down."""
    return stinger(_dying(embers(2.1, crackle=_FIRE_BRIGHT[0], seed=_FIRE_BRIGHT[1]), 0.4, 14),
                   air(2.0, bright=0.35, peak=0.5, start_db=-9, seed=4).db(-2), room="hall")


def _m3_cello_fire():
    """A low cello A swelling through a crackle of fire that dies down."""
    return stinger(swell("cello", "A3", dur=2.0, peak=0.5, start_db=-8, vel=96),
                   _dying(embers(2.1, crackle=_FIRE_LOW[0], seed=_FIRE_LOW[1]), 0.4, 12).db(-8), room="hall")


# ============================================================================= 5 · Zone grows (weight)
def _m5_basses():
    """Double basses on A and D growing heavier as they come, then sinking."""
    return stinger(swell("bass", "A2+D3", dur=1.9, peak=0.5, start_db=-8, vel=100).heavy(), room="hall")


def _m5_footfalls():
    """Two heavy felt footfalls, the second nearer and harder, chains dragging after them
    (the chains, not a sub-bass rumble, so a phone hears it and headphones are not boomed)."""
    return stinger(hits("felt_drum", [(0.0, 96), (0.6, 124)]),
                   chains(1.0, shake=0.4, seed=6).at(0.62).db(-6), room="hall")


def _m5_tuba():
    """A tuba D swelling up as the floor's boards groan under it."""
    return stinger(swell("tuba", "D3", dur=1.9, peak=0.5, start_db=-8, vel=100),
                   creak(1.2, tension=0.2, seed=2).at(0.25).db(-8), room="hall")


# ============================================================================= 10 · Zone grows (crumbling)
def _m10_tremolo():
    """Low strings trembling on an open fifth, swelling and sinking, in a crypt."""
    return stinger(swell("tremolo_strings", "D3+A3", dur=1.9, peak=0.5, start_db=-8, vel=90), room="crypt")


def _m10_rubble():
    """A timpani roll on A building as grit and stones shift and trickle down (a timpani,
    not the tom: the tom's roll rings a quarter-tone-sharp E flat over the music's D)."""
    return stinger(roll("timpani", "A2", dur=0.9, shape="swell", vel=(40, 84)),
                   rumble(2.1, depth=0.2, grit=1.4, peak=0.5, start_db=-8, seed=3).db(-8), room="crypt")


def _m10_bassoon():
    """A bassoon A swelling up while grit trickles down the walls."""
    return stinger(swell("bassoon", "A2", dur=1.9, peak=0.5, start_db=-8, vel=96),
                   rumble(2.1, depth=0.3, grit=1.0, peak=0.4, start_db=-6).db(-3), room="crypt")


# ============================================================================= 5 · Carry damage (impact)
def _carry_strings():
    """A string-section blow on A, and the same blow echoing on, far away."""
    blow = dict(dur=0.8, peak=0.02, start_db=-2, vel=112)
    return stinger(swell("strings", "A2+A3", **blow),
                   swell("strings", "A2+A3", **blow).far(0.9).at(0.42).db(-10), room="hall")


def _carry_rush():
    """A rush of air going on past you, and the blow landing far off (Carry damage always
    follows Damage, so it does not open on a drum like Damage's)."""
    return stinger(wind(2.0, strength=1.0, peak=0.06, seed=9),
                   hit("felt_drum", vel=118).far(0.6).at(0.3).db(0), room="hall")


def _carry_trombone():
    """A trombone blow on A, and the rush of its force going on past."""
    return stinger(swell("trombone", "A2", dur=1.0, peak=0.03, start_db=-2, vel=112),
                   air(1.6, bright=0.5, peak=0.15, start_db=-6, seed=7).at(0.04).db(-8), room="hall")


# ============================================================================= 7 · Pilgrim arrives (sacred, gentle)
def _pilgrim_pipe():
    """One soft, low pan-pipe D, breathy, outdoors (not Turn's A4, which comes just before)."""
    return stinger(swell("pan_flute", "D4", dur=1.9, peak=0.35, start_db=-7, vel=76), room="open")


def _pilgrim_steps():
    """Three light footsteps on a road, a soft wind around them. The frame drum rings on E
    flat (the banes' dread note): played 5% slower, it rings on D."""
    return stinger(_deeper(hits("frame_drum", [(0.0, 64), (0.55, 54), (1.1, 46)], felt=True).heavy(False), 1.05),
                   wind(2.2, strength=0.25, peak=0.6).db(-4), room="open")


def _pilgrim_bell():
    """A small bell on a staff, and a traveller humming a low D (the bell on D6: Pilgrim
    match's harp is on A5)."""
    return stinger(strike("small_bell", "D6", vel=60),
                   swell("hum", "D4", dur=1.8, peak=0.5, start_db=-8, vel=66).at(0.1).db(-3), room="chapel")


# ============================================================================= 7 · Pilgrim match (mystery)
def _match_unison():
    """A high harp A, and a wooden flute finding the same A an octave below."""
    return stinger(strike("harp", "A5", vel=70),
                   swell("wooden_flute", "A4", dur=1.7, peak=0.4, start_db=-8, vel=66).at(0.12).db(-3), room="cave")


def _match_drops():
    """Two drops falling into still water, both on the same A, the second softer."""
    return stinger(drips(2, spacing=0.5, pitches=("A5", "A5"), seed=3),
                   air(2.1, bright=0.4, peak=0.5, start_db=-9).db(-12), room="cave")


def _match_knock_bell():
    """A knock on old wood, and a hand bell answering far off on A."""
    return stinger(hit("knock", vel=96),
                   strike("hand_bell", "A5", vel=60).far(0.4).at(0.12).db(-2), room="chapel")


# ============================================================================= 8 · Zone filled! (triumph, release)
def _filled_organ():
    """An organ chord opening out on a bright fifth and ringing away (an organ: No damage's
    strings already swell on D4+A4, and Exact kill!'s trumpets just before hold D5+A5)."""
    return stinger(swell("organ", "D4+A4", dur=1.8, peak=0.1, start_db=-3, vel=96), room="hall")


def _filled_wind():
    """A gust of wind that drops, and a long, deep breath let out: the tension goes."""
    return stinger(wind(1.6, strength=0.8, peak=0.08, seed=11),
                   _deeper(breath(1.3, "out", seed=4), 1.3).at(0.25).db(-2), room="hall")


def _filled_dulcimer():
    """A hammered dulcimer rings out on a bright fifth as the air clears."""
    return stinger(strike("hammered_dulcimer", "D5+A5", vel=92, hold=1.9),
                   air(2.0, bright=0.5, peak=0.3, start_db=-8, seed=8).at(0.05).db(-8), room="hall")


# ============================================================================= 9 · Captured piles (sorrow)
def _piles_viola():
    """A lone viola sinking from A to F: a falling minor third, a plea."""
    return stinger(slide("viola", "A4", "F4*", dur=2.0, glide=(0.14, 0.42), peak=0.22, start_db=-6, vel=70),
                   room="hall")


def _piles_chains():
    """Chains shifting in the dark, and a tired sigh."""
    return stinger(chains(1.0, shake=0.5), breath(1.4, "sigh").at(0.15).db(-2), room="crypt")


def _piles_voices():
    """Mourning voices on F and D, a bell tolling far off behind them."""
    return stinger(swell("hum", "F4*+D5", dur=1.9, peak=0.45, start_db=-6, vel=70),
                   strike("bell", "D4", vel=72, damp=1.0, fall=0.9).far(0.6).at(0.3).db(-5), room="crypt")


# ============================================================================= 10 · Cleric enemy (dread)
def _cleric_cello():
    """A cello rising as if to heal, but by a sour tritone, A up to E flat."""
    return stinger(slide("cello", "A3", "Eb4*", dur=1.9, glide=(0.15, 0.45), peak=0.35, start_db=-7, vel=78),
                   room="crypt")


def _cleric_water():
    """Dark water lapping in a crypt over a dull felt thud."""
    return stinger(water(2.1, "lap", seed=2), hit("felt_drum", vel=100).db(-2), room="crypt")


def _cleric_harp():
    """A harp falling from D down onto a sour E flat, a cold draught behind it."""
    return stinger(strike("harp", "Eb4*+A4+D5", spread=0.09, down=True, vel=74),
                   air(2.1, bright=0.15, peak=0.6, start_db=-10).db(-10), room="crypt")


# ============================================================================= 10 · Bard enemy (dread)
def _bard_strum():
    """One lute strum down, its top string sour (E flat over D and A), a hand settling on it."""
    return stinger(strike("lute", "D3+A3+Eb4*", spread=0.03, down=True, vel=88, hold=2.2, damp=0.7, fall=1.4),
                   room="crypt")


def _bard_dice():
    """Dice thrown on a table, and a card palmed away."""
    return stinger(_dice(2, seed=3), rustle(0.5, "cards", density=0.6, seed=6).at(0.55).db(-3), room="crypt")


def _bard_reed():
    """A dry tap on a small drum, and a cor anglais scooping slyly up from D to E flat (the
    bend lands as the note swells, so the sour E flat is heard)."""
    return stinger(hit("tabor", vel=90),
                   slide("english_horn", "D4", "Eb4*", dur=1.8, glide=(0.06, 0.16), peak=0.32, start_db=-6,
                         vel=74).at(0.05).db(-1), room="crypt")


# ============================================================================= 11 · Beast (threat)
_GROWL = "D2+D3"     # the beasts' voice: a low horn on a D octave


def _growl(at: float = 0.0, db: float = -4.0, vel: int = 112) -> Layer:
    """The beasts' shared voice under another sound: the low horn octave, hard, falling away."""
    return swell("horn", _GROWL, dur=1.4, peak=0.06, start_db=-3, vel=vel).at(at).db(db)


def _beast_horn():
    """A low horn growl on a D octave, a stab that falls away heavily."""
    return stinger(swell("horn", _GROWL, dur=1.6, peak=0.05, start_db=-3, vel=118).heavy(), room="hall")


def _beast_tread():
    """A heavy war-drum footfall and a big beast's breath let out."""
    return stinger(hit("war_drum", vel=124), _deeper(breath(1.0, "out", seed=2), 1.5).at(0.04).db(-4),
                   room="hall")


def _beast_timpani():
    """A timpani blow on A and the beast's low horn growl."""
    return stinger(strike("timpani", "A2", vel=118), _growl(0.02, -3), room="hall")


# the class beasts: their class's own sound, with the beast under it
def _beast_h_voices():
    """Cleric beast: dark voices cry out on D and A, the beast's horn under them."""
    return stinger(swell("choir", "D3+A3", dur=1.5, peak=0.08, start_db=-3, vel=118), _growl(0.0, -6, 110),
                   room="hall")


def _beast_h_harp():
    """Cleric beast: a harp struck hard and low, a heavy footfall under it."""
    return stinger(strike("harp", "A2+D3", vel=116), hit("bass_drum", vel=110).db(-3), room="hall")


def _beast_d_lute():
    """Bard beast: a low lute slashed hard, the beast's horn growling under it."""
    return stinger(strike("lute", "D2+A2+D3", vel=118, spread=0.012, down=True, hold=2.2, damp=0.45, fall=1.5),
                   _growl(0.03, -4, 110), room="hall")


def _beast_d_cards():
    """Bard beast: cards torn away in a flurry, a heavy footfall under them."""
    return stinger(rustle(0.7, "cards", density=1.6, seed=4), hit("bass_drum", vel=110).db(-9), room="hall")


def _beast_c_clash():
    """Warrior beast: a clash of iron (a cymbal struck hard) and the beast's growl under it
    (no bass drum: Damage's deep drum plays in the same turn)."""
    return stinger(hit("cymbal", vel=100), _growl(0.0, 0, 116), room="hall")


def _beast_c_snare():
    """Warrior beast: a martial snare roll dying away, chains rattling: a war beast straining."""
    return stinger(roll("snare", dur=1.0, shape="fade", vel=(30, 116)),
                   chains(1.2, shake=0.7, seed=3).at(0.03).db(-6), room="hall")


def _beast_s_organ():
    """Paladin beast: a dark organ fifth blasted once, the beast's growl under it."""
    return stinger(swell("organ", "D3+A3", dur=1.8, peak=0.05, start_db=-3, vel=120), _growl(0.0, -6, 110),
                   room="hall")


def _beast_s_bell():
    """Paladin beast: an iron bell struck on A and a low trombone on D."""
    return stinger(strike("bell", "A3", vel=118),
                   swell("trombone", "D3", dur=1.4, peak=0.06, start_db=-3, vel=116).db(-2), room="hall")


# ============================================================================= 12 · Zone grows (growth)
def _m12_reed():
    """A dark cor anglais A swelling up toward you like something growing, then sinking."""
    return stinger(swell("english_horn", "A3", dur=1.9, peak=0.5, start_db=-6, vel=96), room="hall")


def _m12_ground():
    """The ground heaving up and settling, dry leaves stirring over it."""
    return stinger(rumble(2.0, depth=0.4, grit=0.3, peak=0.4, start_db=-4, seed=8),
                   rustle(1.2, "leaves", density=0.7, seed=12).at(0.1).db(0), room="hall")


def _m12_voices():
    """Low voices rising on A, and roots groaning as they push through."""
    return stinger(swell("choir", "A3", dur=1.9, peak=0.5, start_db=-8, vel=90),
                   creak(1.1, tension=0.2, seed=9).at(0.2).db(-8), room="hall")


# ============================================================================= the options
def _zone(row, cid, name, note, fn, approach, tint):
    return option(row, cid, name, note, fn, "threat", approach, ("encroaching", "zone", tint))


CANDIDATES = [
    # 3 · Zone grows: the academy learns your class (fire)
    _zone("m3_zone", "brass_flare", "Low brass flares up",
          "A trombone D swells toward you like a flame catching, then sinks back. Encroaching.",
          _m3_brass, "instrumental", "fire"),
    _zone("m3_zone", "fire_roars", "Fire roars up",
          "A fire catches and its flames roar up toward you, then die down to a crackle. Encroaching.",
          _m3_fire, "textural", "fire"),
    _zone("m3_zone", "cello_embers", "Cello through the crackle",
          "A low cello A swells up through a crackle of fire and fades. Encroaching.",
          _m3_cello_fire, "hybrid", "fire"),
    # 5 · Zone grows: the enemy gets stronger (weight)
    _zone("m5_zone", "basses_swell", "Basses swell, heavier",
          "Double basses on A and D grow heavier as they come toward you, then sink. Weight.",
          _m5_basses, "instrumental", "weight"),
    _zone("m5_zone", "footfalls", "Two heavy footfalls",
          "Two deep felt footfalls, the second nearer and harder, chains dragging after them. Something big "
          "comes closer.",
          _m5_footfalls, "textural", "weight"),
    _zone("m5_zone", "tuba_groan", "Tuba swells, floor groans",
          "A tuba D swells up toward you as the floor's boards groan under it. Weight gathering.",
          _m5_tuba, "hybrid", "weight"),
    # 10 · Zone grows: strength drawn from the rubble (crumbling)
    _zone("m10_zone", "trembling_strings", "Trembling low strings",
          "Low strings tremble on an open fifth, swell and sink in a crypt. Stone giving way.",
          _m10_tremolo, "instrumental", "crumbling"),
    _zone("m10_zone", "shifting_rubble", "Timpani roll, shifting rubble",
          "A low timpani roll builds as grit and stones shift and trickle down. Crumbling.",
          _m10_rubble, "textural", "crumbling"),
    _zone("m10_zone", "bassoon_grit", "Bassoon and falling grit",
          "A bassoon A swells up while grit trickles down the walls. Crumbling, encroaching.",
          _m10_bassoon, "hybrid", "crumbling"),
    # 5 · Carry damage: the blow carries on to the next enemy (impact)
    option("m5_carry", "string_echo", "String blow, echoing on",
           "A string-section blow on A, and the same blow echoing away into the distance.",
           _carry_strings, "impact", "instrumental", ("echo", "strings")),
    option("m5_carry", "rush_far_blow", "Rush of air, a far blow",
           "A rush of air going on past you, and the blow landing far off: the force travels on.",
           _carry_rush, "impact", "textural", ("wind", "drum", "echo")),
    option("m5_carry", "trombone_rush", "Trombone blow, rush of air",
           "A trombone blow on A, and the rush of its force going on past.",
           _carry_trombone, "impact", "hybrid", ("brass", "air")),
    # 7 · Pilgrim arrives (sacred: a gentle wanderer)
    option("m7_pilgrim", "pan_pipe", "Low pan pipe on the road",
           "One soft, breathy, low pan-pipe D in the open air. Gentle, hopeful.",
           _pilgrim_pipe, "sacred", "instrumental", ("gentle", "wanderer", "blown")),
    option("m7_pilgrim", "soft_steps", "Soft steps in the wind",
           "Three light footsteps on a road with a soft wind around them. Someone arrives.",
           _pilgrim_steps, "sacred", "textural", ("gentle", "wanderer", "steps", "wind")),
    option("m7_pilgrim", "bell_hum", "Staff bell and a hum",
           "A small high bell on a pilgrim's staff and a traveller humming a low D.",
           _pilgrim_bell, "sacred", "hybrid", ("gentle", "wanderer", "bell", "voice")),
    # 7 · Pilgrim match (mystery: two things meet)
    option("m7_match", "harp_flute", "Harp meets the flute",
           "A high harp A, and a wooden flute finding the same A an octave below. A match.",
           _match_unison, "mystery", "instrumental", ("match", "unison")),
    option("m7_match", "two_drops", "Two drops, one note",
           "Two drops fall into still water in a cave, both ringing the same A.",
           _match_drops, "mystery", "textural", ("match", "water")),
    option("m7_match", "knock_far_bell", "A knock, a far bell answers",
           "A knock on old wood, and a hand bell answering far off on A: a call and its answer.",
           _match_knock_bell, "mystery", "hybrid", ("match", "wood", "bell")),
    # 8 · Zone filled! (triumph: a release)
    option("m8_filled", "organ_opens", "Organ opens out",
           "An organ chord opens out on a bright D-A fifth and rings away. Release.",
           _filled_organ, "triumph", "instrumental", ("release", "organ")),
    option("m8_filled", "wind_breath", "The wind drops, a breath out",
           "A gust of wind drops away and a long, deep breath is let out. The tension goes.",
           _filled_wind, "triumph", "textural", ("release", "wind", "breath")),
    option("m8_filled", "dulcimer_air", "Dulcimer rings, the air clears",
           "A hammered dulcimer rings out on a bright D-A fifth as the air clears. Release.",
           _filled_dulcimer, "triumph", "hybrid", ("release", "dulcimer", "air")),
    # 9 · Captured piles (sorrow)
    option("m9_piles", "viola_plea", "Viola sinks, a plea",
           "A lone viola sinks from A to F, a falling minor third. Sorrow.",
           _piles_viola, "weariness", "instrumental", ("sorrow", "plea", "strings")),
    option("m9_piles", "chains_sigh", "Chains and a sigh",
           "Chains shift in the dark and someone sighs. Captives.",
           _piles_chains, "weariness", "textural", ("sorrow", "captive", "chains", "breath")),
    option("m9_piles", "voices_far_bell", "Mourning voices, far bell",
           "Voices hum F and D, a bell tolling far off behind them. Sorrow, a plea.",
           _piles_voices, "weariness", "hybrid", ("sorrow", "voice", "bell")),
    # 10 · Cleric enemy (dread, the banes' colour: healing turned against you)
    option("m10_cleric", "cello_sours", "Cello rises and sours",
           "A cello note rises as if to heal, but by a sour tritone, A up to E flat. Dread.",
           _cleric_cello, "dread", "instrumental", ("corrupted", "rub", "strings")),
    option("m10_cleric", "dark_water", "Dark water, dull thud",
           "Dark water lapping in a crypt over one dull felt thud. Dread.",
           _cleric_water, "dread", "textural", ("corrupted", "water", "drum")),
    option("m10_cleric", "harp_falls_sour", "Harp falls onto a sour note",
           "A harp falls from D onto a sour E flat (healing upside down), a cold draught behind it.",
           _cleric_harp, "dread", "hybrid", ("corrupted", "rub", "harp", "air")),
    # 10 · Bard enemy (dread: sly)
    option("m10_bard", "sour_strum", "Sour lute strum",
           "One lute strum down, its top string sour (E flat over D and A). Sly, corrupted.",
           _bard_strum, "dread", "instrumental", ("corrupted", "sly", "rub", "lute")),
    option("m10_bard", "dice_card", "Dice thrown, a card palmed",
           "Dice clatter on a table and a card is quietly palmed away. Sly.",
           _bard_dice, "dread", "textural", ("corrupted", "sly", "dice", "cards")),
    option("m10_bard", "bent_reed", "Drum tap, a reed bends",
           "A dry tap on a small drum, and a cor anglais scooping slyly up from D to E flat.",
           _bard_reed, "dread", "hybrid", ("corrupted", "sly", "rub", "reed")),
    # 11 · Beast (threat): the fallback for any beast
    option("m11_beast", "horn_growl", "Low horn growl",
           "A low horn growl on a D octave: a stab that falls away heavily. The beast's voice.",
           _beast_horn, "threat", "instrumental", ("beast", "brass")),
    option("m11_beast", "heavy_tread", "Heavy tread, a beast's breath",
           "A heavy war-drum footfall and a big beast's breath let out after it.",
           _beast_tread, "threat", "textural", ("beast", "drum", "breath")),
    option("m11_beast", "timpani_growl", "Timpani and horn growl",
           "A timpani blow on A with the beast's low horn growl.",
           _beast_timpani, "threat", "hybrid", ("beast", "drum", "brass")),
    # 11 · the class beasts: the class's own sound, the beast under it
    option("m11_beast_H", "dark_voices", "Dark voices, horn growl",
           "Cleric beast: dark voices cry out on D and A over the beast's low horn.",
           _beast_h_voices, "threat", "instrumental", ("beast", "cleric", "voice")),
    option("m11_beast_H", "low_harp_tread", "Low harp, heavy tread",
           "Cleric beast: a harp struck hard and low on A and D, with a heavy footfall.",
           _beast_h_harp, "threat", "hybrid", ("beast", "cleric", "harp", "drum")),
    option("m11_beast_D", "lute_slash", "Lute slash, horn growl",
           "Bard beast: a low lute slashed hard on D and A, the beast's horn growling under it.",
           _beast_d_lute, "threat", "instrumental", ("beast", "bard", "lute")),
    option("m11_beast_D", "torn_cards", "Cards torn away, heavy tread",
           "Bard beast: cards torn away in a flurry over a heavy footfall.",
           _beast_d_cards, "threat", "textural", ("beast", "bard", "cards", "drum")),
    option("m11_beast_C", "iron_clash", "Clash of iron, a growl",
           "Warrior beast: a clash of iron and the beast's low horn growl under it.",
           _beast_c_clash, "threat", "hybrid", ("beast", "warrior", "cymbal", "brass")),
    option("m11_beast_C", "snare_chains", "Snare roll, rattling chains",
           "Warrior beast: a martial snare roll dying away and chains rattling, a war beast straining.",
           _beast_c_snare, "threat", "textural", ("beast", "warrior", "drum", "chains")),
    option("m11_beast_S", "organ_growl", "Dark organ, horn growl",
           "Paladin beast: a dark organ fifth blasted once, the beast's horn under it.",
           _beast_s_organ, "threat", "instrumental", ("beast", "paladin", "organ")),
    option("m11_beast_S", "iron_bell", "Iron bell, low trombone",
           "Paladin beast: an iron bell struck on A and a low trombone on D.",
           _beast_s_bell, "threat", "hybrid", ("beast", "paladin", "bell", "brass")),
    # 12 · Zone grows: decay to growth, the enemy stronger and immune (growth)
    _zone("m12_zone", "dark_reed", "Dark reed grows",
          "A dark cor anglais A swells up toward you like something growing, then sinks. Encroaching.",
          _m12_reed, "instrumental", "growth"),
    _zone("m12_zone", "ground_heaves", "The ground heaves, leaves stir",
          "The ground heaves up and settles as dry leaves stir over it. Something grows beneath.",
          _m12_ground, "textural", "growth"),
    _zone("m12_zone", "voices_roots", "Low voices, groaning roots",
          "Low voices rise on A as roots groan, pushing through. Encroaching.",
          _m12_voices, "hybrid", "growth"),
]
