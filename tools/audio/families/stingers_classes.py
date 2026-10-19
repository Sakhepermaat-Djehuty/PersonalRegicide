"""Info pop-up stingers, the classes group: IMMUNITY, the nine class cards and Damage.

Each card gets three options, each a different approach (instrumental, textural, hybrid),
built with the stinger toolkit (_stingers.py): one or two sound sources, one to three
pitched notes on D and A (one colour note at most, marked "*"), a clear onset when the
card appears, then the gesture's own decay, 2.0-2.4 s, meant to sit on top of dark mission
music rather than to be a tune. Each class keeps one signature across its options so the
owner learns it:

    IMMUNITY  threat   the stamp: a thud or a note choked off (denial)
    Mage      mystery  glass: blown glass, glints, a celesta
    Druid     mystery  wood and the outdoors: a wooden flute, a creaking bough, a marimba
    Cleric    warmth   warm and rising: a viola lifting, a spring under rising air, a harp rising
    Bard      warmth   a strum or quick pluck: lute, cards dealt round, a dulcimer
    Chanter   sacred   a sung or breathed tone: voices, a breath, a hum
    Reaver    unease   a dig or scrape: a cello biting on a rub, gravel, iron
    Warrior   impact   a doubled blow: two hits (strings, taiko, toms), the second harder
    Paladin   sacred   a shield's steady ring: horn, a struck shield, an organ and cymbal
    Guardian  relief   a wall of low strings, then the breath let out
    Damage    impact   one plain blow

    python3 tools/audio/build.py stingers_classes
    python3 tools/audio/families/_stingers.py over stingers_classes
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _stingers import (  # noqa: E402
    air, breath, chains, creak, hit, hits, option, roll, rumble, rustle, slide, sparkle, stinger,
    strike, swell, water, wind,
)


# a stone hall a little larger than "hall", so a short stab or blow still rings to 2 s
BIG_HALL = (0.80, 0.22, 0.5)


# ============================================================================= IMMUNITY (threat: denial)
def _immunity_trombone():
    """A low trombone blast on A, cut dead: the power slammed shut; only the hall answers."""
    return stinger(swell("trombone", "A2+A3", dur=0.8, peak=0.02, start_db=-2, vel=112, fall_db=60),
                   room=BIG_HALL)


def _immunity_stamp():
    """Two quick raps and a thump on the bodhran, a felt-mallet tom under the last: the stamp lands."""
    return stinger(hits("bodhran", [(0.0, 96), (0.13, 76), (0.26, 124)]),
                   hit("tom", vel=110, felt=True).at(0.26).db(-2), room="tavern")


def _immunity_bassoon():
    """A bassoon blurt that sags from A down to D over a felt thud: the power falls flat."""
    return stinger(slide("bassoon", "A2", "D2", dur=1.5, glide=(0.1, 0.6), peak=0.04, start_db=-3, vel=96),
                   hit("felt_drum", vel=110).db(-4), room="hall")


# ============================================================================= Mage (mystery: glass)
def _mage_glass():
    """Breath across the mouth of a glass bottle, a single A, hanging in a cave."""
    return stinger(swell("bottle", "A5", dur=1.8, peak=0.3, start_db=-6, vel=70), room="cave")


def _mage_glints():
    """Glassy glints on D and A, thinning out in a cold draught."""
    return stinger(sparkle(1.9, count=9), air(2.1, bright=0.6, start_db=-6).db(-10), room="chapel")


def _mage_celesta():
    """One celesta D, a few faint glints scattering after it: a secret look."""
    return stinger(strike("celesta", "D6", vel=58),
                   sparkle(1.4, count=6, pitches=("A6", "D7", "A7")).at(0.1).db(-10), room="chapel")


# ============================================================================= Druid (mystery: wood)
def _druid_flute():
    """A breathy wooden flute (shakuhachi) on D, outdoors."""
    return stinger(swell("shakuhachi", "D5", dur=1.9, peak=0.35, start_db=-6, vel=72), room="open")


def _druid_bough():
    """An old bough creaks as the wind moves through the trees."""
    return stinger(creak(1.0, tension=0.45), wind(2.1, strength=0.35).db(-6), room="hall")


def _druid_marimba():
    """A soft wooden marimba roll on A under a faint stir of leaves."""
    return stinger(roll("marimba", "A4", dur=1.3, shape="fade", vel=(30, 80)),
                   rustle(1.2, "leaves", density=0.5).db(-13), room="open")


# ============================================================================= Cleric (warmth: rising)
def _cleric_cello():
    """A warm viola note lifting from A up to D."""
    return stinger(slide("viola", "A3", "D4", dur=1.8, glide=(0.2, 0.55), peak=0.5, start_db=-6, vel=76),
                   room="hall")


def _cleric_spring():
    """A spring running clear under rising warm air: healing (not a fire: the Kinfolk Flute's
    hearth, which can come just before the Cleric card, is one)."""
    return stinger(water(2.2, "stream", seed=3), air(2.0, bright=0.2, peak=0.8, start_db=-12).db(-12), room="hall")


def _cleric_harp():
    """A harp lifting from D to A on a rising warm air."""
    return stinger(strike("harp", "D4+A4", spread=0.12, vel=66, hold=1.8),
                   air(2.0, bright=0.2, peak=0.6, start_db=-12).db(-14), room="hall")


# ============================================================================= Bard (warmth: strum)
def _bard_lute():
    """One open lute strum (D, A, D), left to ring in the tavern."""
    return stinger(strike("lute", "D3+A3+D4", spread=0.025, vel=86, hold=1.8), room="tavern")


def _bard_cards():
    """A hand drum tapped once and cards dealt round the table, thinning out."""
    return stinger(rustle(1.5, "cards", density=0.6), hit("frame_drum", vel=80).db(-4), room="hall")


def _bard_dulcimer():
    """A quick dulcimer pluck (A, D) as the cards are dealt."""
    return stinger(strike("hammered_dulcimer", "A4+D5", spread=0.04, vel=78, hold=2.4),
                   rustle(0.6, "cards").at(0.02).db(-8), room="tavern")


# ============================================================================= Chanter (sacred: voice)
def _chanter_choir():
    """Voices on an open fifth, swelling once in a chapel."""
    return stinger(swell("choir", "D4+A4", dur=1.8, peak=0.5, start_db=-7, vel=74), room="chapel")


def _chanter_breath():
    """A long breath out, a temple bell answering far off."""
    return stinger(breath(1.2, "out"), strike("bell", "A4", vel=60).far(0.6).db(-4), room="chapel")


def _chanter_hum():
    """A breath drawn in, then a low humming voice on D: about to call."""
    return stinger(swell("hum", "D4", dur=1.8, peak=0.45, start_db=-6, vel=70).at(0.22),
                   breath(0.3, "in").db(-4), onset=0.22, room="chapel")


# ============================================================================= Reaver (unease: dig)
def _reaver_cello():
    """A cello bites in hard on a rub (D against E flat) and dig away."""
    return stinger(swell("cello", "D3+Eb3*", dur=1.6, peak=0.03, start_db=-3, vel=118), room="crypt")


def _reaver_gravel():
    """Digging in stony ground: a low shifting of earth and a crunch of gravel."""
    return stinger(rumble(2.0, depth=0.2, grit=1.0, peak=0.05, start_db=-3),
                   rustle(0.6, "leaves", density=2.0).db(-2), room="crypt")


def _reaver_tremolo():
    """A thin, uneasy string tremolo (A against B flat) over a scrape of iron."""
    return stinger(swell("tremolo_strings", "A4+Bb4*", dur=1.6, peak=0.3, start_db=-5, vel=70),
                   chains(1.0, shake=0.4).db(-8), room="crypt")


# ============================================================================= Warrior (impact: doubled)
def _warrior_strings():
    """A string stab on D, then a harder one an octave up: the damage doubled."""
    return stinger(swell("strings", "D3", dur=0.5, peak=0.02, start_db=-2, vel=110),
                   swell("strings", "D3+D4", dur=1.5, peak=0.02, start_db=-2, vel=124).at(0.24).db(2), room="hall")


def _warrior_drums():
    """Two taiko blows on D, the second harder (not the war drum: Enemy attacks, which can
    follow the Warrior card, opens on that same bass-drum sample)."""
    return stinger(strike("taiko", "D2", vel=100), strike("taiko", "D2", vel=124).at(0.24).db(3), room="hall")


def _warrior_hybrid():
    """Two low tom blows, a string stab on the second."""
    return stinger(hits("tom", [(0.0, 100), (0.24, 124)]),
                   swell("strings", "D3+D4", dur=1.4, peak=0.02, start_db=-2, vel=118).at(0.24).db(-2), room="hall")


# ============================================================================= Paladin (sacred: shield)
def _paladin_horn():
    """A calm horn fifth (D and A), held steady."""
    return stinger(swell("horn", "D3+A3", dur=1.8, peak=0.4, start_db=-6, vel=76), room="hall")


def _paladin_shield():
    """A blow taken on a shield: the metal rings on D (a bell, a hand laid on it) over a soft thud."""
    return stinger(strike("bell", "D4", vel=84, damp=1.0, fall=1.2), hit("felt_drum", vel=96).db(-2), room="chapel")


def _paladin_organ():
    """A soft organ fifth with a shield ringing under it."""
    return stinger(swell("organ", "D4+A4", dur=1.8, peak=0.5, start_db=-8, vel=64), hit("cymbal", vel=60).db(-6),
                   room="chapel")


# ============================================================================= Guardian (relief: a wall)
def _guardian_strings():
    """A wall of low strings rises (D, A, D) and holds, then lets go."""
    return stinger(swell("slow_strings", "D3+A3+D4", dur=1.9, peak=0.35, start_db=-6, vel=80), room="hall")


def _guardian_roll():
    """A soft hand-drum roll builds like a wall, then a breath let out."""
    return stinger(roll("frame_drum", dur=1.2, shape="swell", vel=(40, 96), lp=1800),
                   breath(1.3, "out").at(0.6).db(-4), room="hall")


def _guardian_bass():
    """Low basses on one D, a timpani roll swelling an octave under them."""
    return stinger(swell("bass", "D3", dur=1.9, peak=0.4, start_db=-6, vel=88),
                   roll("timpani", "D2", dur=1.2, shape="swell", vel=(30, 70)).db(-9), room="hall")


# ============================================================================= Damage (impact: plain)
def _damage_timpani():
    """One timpani blow on A, left to ring."""
    return stinger(strike("timpani", "A2", vel=118), room="hall")


def _damage_drum():
    """One low tom blow, left to ring (not the bass drum: Enemy attacks, which can follow the
    Damage card, opens on that same sample in its war drum; the tom also carries on a phone)."""
    return stinger(hit("tom", vel=120), room="hall")


def _damage_taiko():
    """A big drum and a short lute stab on A and D."""
    return stinger(strike("taiko", "A2", vel=118),
                   strike("lute", "A2+D3", vel=100, damp=0.15, fall=0.4).db(-4), room=BIG_HALL)


CANDIDATES = [
    # IMMUNITY: the stamped, blocked card
    option("immunity", "trombone_cut", "Trombone blast, cut dead",
           "A low trombone blast on A that stops dead; only the hall answers. Denied.",
           _immunity_trombone, "threat", "instrumental", ("denial", "brass")),
    option("immunity", "dry_stamp", "Dry stamp",
           "Two quick raps on a bodhran and a felt thump: the stamp coming down. A rhythm, not a tune.",
           _immunity_stamp, "threat", "textural", ("denial", "drum", "stamp")),
    option("immunity", "sagging_bassoon", "Sagging bassoon, felt thud",
           "A bassoon blurt on A that sags down to D over a felt thud: the power falls flat.",
           _immunity_bassoon, "threat", "hybrid", ("denial", "drum", "reed")),
    # Mage
    option("mage", "blown_glass", "Breath across glass",
           "A single breathy A blown across a glass bottle, hanging in a cave. Something hidden.",
           _mage_glass, "mystery", "instrumental", ("glass", "blown")),
    option("mage", "glints", "Glints in a draught",
           "Tiny glassy glints on D and A thinning out in cold air.",
           _mage_glints, "mystery", "textural", ("glass", "shimmer")),
    option("mage", "celesta_glints", "Celesta and faint glints",
           "One celesta D with a few faint glints scattering after it: a secret look.",
           _mage_celesta, "mystery", "hybrid", ("glass", "celesta")),
    # Druid
    option("druid", "wooden_flute", "Wooden flute, outdoors",
           "One breathy wooden-flute D in the open air.",
           _druid_flute, "mystery", "instrumental", ("wood", "nature", "blown")),
    option("druid", "creaking_bough", "Creaking bough in the wind",
           "An old bough creaks as the wind moves through the trees.",
           _druid_bough, "mystery", "textural", ("wood", "nature", "wind")),
    option("druid", "marimba_leaves", "Wooden roll and leaves",
           "A soft marimba roll on A under a faint stir of leaves.",
           _druid_marimba, "mystery", "hybrid", ("wood", "nature", "leaves")),
    # Cleric
    option("cleric", "viola_lift", "Viola lifts a fourth",
           "A warm viola note rising from A to D and opening out.",
           _cleric_cello, "warmth", "instrumental", ("rising", "strings")),
    option("cleric", "clear_spring", "A spring runs clear",
           "A spring running clear under rising warm air: healing.",
           _cleric_spring, "warmth", "textural", ("rising", "water", "air")),
    option("cleric", "harp_rise", "Harp rising on warm air",
           "A harp lifting from D to A on a rising swell of warm air.",
           _cleric_harp, "warmth", "hybrid", ("rising", "harp")),
    # Bard
    option("bard", "lute_strum", "One lute strum",
           "A single open lute strum on D and A, left to ring in the tavern.",
           _bard_lute, "warmth", "instrumental", ("strum", "lute")),
    option("bard", "dealt_cards", "Cards dealt round, drum tap",
           "One tap of a hand drum and cards dealt round the table, thinning out.",
           _bard_cards, "warmth", "textural", ("strum", "cards", "drum")),
    option("bard", "dulcimer_pluck", "Dulcimer pluck and cards",
           "A quick dulcimer pluck on A and D as the cards go round.",
           _bard_dulcimer, "warmth", "hybrid", ("pluck", "dulcimer", "cards")),
    # Chanter
    option("chanter", "choir_fifth", "Voices on a fifth",
           "Voices on an open fifth, swelling once and fading in a chapel.",
           _chanter_choir, "sacred", "instrumental", ("voice", "choir")),
    option("chanter", "breath_bell", "Breath and far bell",
           "A long breath out, a temple bell answering far off.",
           _chanter_breath, "sacred", "textural", ("voice", "breath", "bell")),
    option("chanter", "breath_hum", "Breath, then a hum",
           "A breath drawn in, then a low humming voice on D: about to call out.",
           _chanter_hum, "sacred", "hybrid", ("voice", "breath", "hum")),
    # Reaver
    option("reaver", "cello_dig", "Cello digs in on a rub",
           "A cello bites in hard on a rub (D against E flat) and digs away.",
           _reaver_cello, "unease", "instrumental", ("dig", "strings", "rub")),
    option("reaver", "stony_ground", "Digging in stony ground",
           "A low shifting of earth and a crunch of gravel: something dug up.",
           _reaver_gravel, "unease", "textural", ("dig", "earth")),
    option("reaver", "tremolo_scrape", "Thin tremolo, iron scrape",
           "A thin, uneasy string tremolo (A against B flat) over a scrape of iron.",
           _reaver_tremolo, "unease", "hybrid", ("scrape", "strings", "iron")),
    # Warrior
    option("warrior", "double_stab", "Stab, then doubled",
           "A string stab on D, then a harder one with the octave above: the damage doubled.",
           _warrior_strings, "impact", "instrumental", ("doubled", "strings")),
    option("warrior", "two_taiko_blows", "Two taiko blows",
           "Two big taiko blows on D, the second harder.",
           _warrior_drums, "impact", "textural", ("doubled", "drum")),
    option("warrior", "toms_stab", "Two blows and a stab",
           "Two low tom blows with a string stab on the second.",
           _warrior_hybrid, "impact", "hybrid", ("doubled", "drum", "strings")),
    # Paladin
    option("paladin", "horn_fifth", "Steady horn fifth",
           "A calm horn fifth on D and A, held steady and fading.",
           _paladin_horn, "sacred", "instrumental", ("shield", "brass", "noble")),
    option("paladin", "struck_shield", "Struck shield",
           "A blow taken on a shield: a soft thud and the metal ringing on D, then stilled.",
           _paladin_shield, "sacred", "textural", ("shield", "metal")),
    option("paladin", "organ_shield", "Organ fifth, shield ring",
           "A soft organ fifth with a shield ringing under it.",
           _paladin_organ, "sacred", "hybrid", ("shield", "organ", "metal")),
    # Guardian
    option("guardian", "string_wall", "Wall of low strings",
           "A wall of low strings rises on D and A, holds, then lets go.",
           _guardian_strings, "relief", "instrumental", ("wall", "strings")),
    option("guardian", "roll_breath", "Drum roll, breath out",
           "A soft hand-drum roll builds like a wall, then a breath let out.",
           _guardian_roll, "relief", "textural", ("wall", "drum", "breath")),
    option("guardian", "bass_timpani", "Low basses, timpani swell",
           "Low basses on one D with a timpani roll swelling an octave under them.",
           _guardian_bass, "relief", "hybrid", ("wall", "strings", "timpani")),
    # Damage
    option("damage", "timpani_blow", "One timpani blow",
           "One timpani blow on A, left to ring. Plain.",
           _damage_timpani, "impact", "instrumental", ("blow", "timpani")),
    option("damage", "low_drum_blow", "One low drum blow",
           "One low tom blow and its ring. Plain.",
           _damage_drum, "impact", "textural", ("blow", "drum")),
    option("damage", "drum_lute_stab", "Big drum, lute stab",
           "A big drum with a short lute stab on A and D.",
           _damage_taiko, "impact", "hybrid", ("blow", "drum", "lute")),
]
