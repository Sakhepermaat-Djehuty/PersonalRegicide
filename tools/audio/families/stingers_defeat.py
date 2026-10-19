"""Info pop-ups, the defeat group, second set: short stingers that carry one feeling over the
mission music (docs/INFO_POPUPS.md; the owner's feedback on the first set: fewer instruments,
no melody, no shared opening, an emotion that sits on top of dark music). Built with
``_stingers`` (one or two sound sources, at most three pitched notes, D and A plus one
marked colour note, a clear onset and a natural decay, 2.0-2.4 s).

Rows and the feeling each carries (``_stingers.PALETTE``; three options per row, one per
approach: instrumental, textural, hybrid):
  defeated       triumph, as a release: the enemy falls and the tension lets go (a fall,
                 a settling); darker and lower than Exact kill
  exact_kill     triumph, gleaming: the same release turned bright and high (mastered
                 1.5 dB louder)
  hydra_regrows  threat: not exact, so the head slips back under the castle; something
                 creeps back up (in Defeated's place)
  cleanup        neutral: the played cards swept away, a quiet reset
  team_damage    threat: everyone braces (team damage, no feign death)
  new_enemy      threat: the next enemy steps out of the castle, something looms
  enemy_shift    threat (one of the enemy's cards), bent out of shape: a pile top changed
                 mid-attack and the enemy changes; its mark is a bend from D up to a sour
                 E flat (the palette's suggestion for this row is unease: kept as a tag)
  enemy_attack   threat, the strongest of the enemy's cards: the blow comes (mastered 1.5 dB
                 louder)
  shielded       relief: the blow is blocked, nothing to pay
  feign_death    relief: a player plays dead and gets away with it
  damage_paid    weariness: the blow is paid with discards and accepted

The enemy's cards share the threat colour (low brass and skins, heavy on purpose, a hit and
a heavy fall) and each keeps its own source: Enemy attacks the trombones, a war drum and
the timpani; New enemy a looming low brass call (the tuba, a far horn) and the castle gate;
Enemy changes low basses bent a half step out of shape; Team damage the brass section; Hydra
regrows the bassoon, marsh water and a creeping tremolo. Every option opens on its own
source and pitch (``python3 _stingers.py over stingers_defeat`` lists any shared opening).
"""
from __future__ import annotations

import numpy as np

from _stingers import (air, breath, chains, creak, hit, hits, option, roll, rumble, rustle, slide, stinger, strike,
                       swell, water)


# ============================================================================= Defeated (triumph: a release, a fall)
def _defeated_horn() -> np.ndarray:
    # one horn calls on A and falls a fifth to D, then fades: the enemy topples, the tension lets go
    return stinger(slide("horn", "A4", "D4", dur=2.0, glide=(0.12, 0.4), peak=0.06, start_db=-3, vel=100,
                         fall_db=40), room="hall")


def _defeated_cymbal() -> np.ndarray:
    # a soft-mallet cymbal struck hard, ringing away like settling dust over stones falling
    # still (no bass-drum thud: the Damage card just before it may open on that same drum)
    return stinger(hit("cymbal", vel=112), rumble(1.8, depth=0.3, grit=0.8, peak=0.04, start_db=-2).db(-8),
                   room="hall")


def _defeated_harp() -> np.ndarray:
    # a harp tumbles down from A (A, D, D) as the hall breathes out: it topples (from A4, not
    # the Cleric's harp D4; air, not a bass-drum roll)
    return stinger(strike("harp", "A4+D4+D3", spread=0.08, down=True, vel=82, hold=2.0, damp=1.3, fall=1.0),
                   air(2.0, bright=0.3, peak=0.3, start_db=-8).at(0.05).db(-10), room="hall")


# ============================================================================= Exact kill! (triumph: gleaming)
def _exact_trumpets() -> np.ndarray:
    # two trumpets strike a high open fifth and let it ring out
    return stinger(swell("trumpet", "D5+A5", dur=2.0, peak=0.05, start_db=-3, vel=104, fall_db=40), room="hall")


def _exact_triangle() -> np.ndarray:
    # a triangle struck bright over a softly struck cymbal, both left to ring: a glint
    return stinger(hit("triangle", vel=110), hit("cymbal", vel=64).db(-6), room="hall")


def _exact_bell() -> np.ndarray:
    # a high bell A rings out over two bright horns on D and A
    return stinger(strike("hand_bell", "A5", vel=92),
                   swell("horn", "D4+A4", dur=1.6, peak=0.12, start_db=-4, vel=100).db(-2), room="hall")


# ============================================================================= Hydra regrows (threat: it comes back)
def _hydra_bassoon() -> np.ndarray:
    # a bassoon slithers up from D to A and hangs there: the head grows back
    return stinger(slide("bassoon", "D3", "A3", dur=1.9, glide=(0.12, 0.75), peak=0.12, start_db=-4, vel=100,
                         fall_db=40).heavy(), room="hall")


def _hydra_water() -> np.ndarray:
    # dark water laps and churns as a deep drum roll swells and sinks: something rising from the marsh
    return stinger(water(2.2, "lap", seed=2), roll("bass_drum", dur=1.4, shape="swell", vel=(40, 100)).db(-4),
                   room="hall")


def _hydra_roll() -> np.ndarray:
    # a timpani roll on A swells while tremolo strings creep up from D to A: not over yet
    return stinger(roll("timpani", "A2", dur=1.3, shape="swell", vel=(40, 104)),
                   slide("tremolo_strings", "D3", "A3", dur=1.8, glide=(0.1, 0.8), peak=0.3, start_db=-6).db(-3),
                   room="hall")


# ============================================================================= Clean-up (neutral: cards swept)
def _cleanup_flute() -> np.ndarray:
    # one soft, breathy low wooden-flute D that fades: a quiet reset
    return stinger(swell("wooden_flute", "D4", dur=1.8, peak=0.25, start_db=-6, vel=66), room="hall")


def _cleanup_cards() -> np.ndarray:
    # the played cards swept across the felt, then two soft taps as the deck is squared
    return stinger(rustle(0.9, "cards", density=1.2, seed=5), hits("knock", [(0.6, 62), (0.75, 54)]).db(-5),
                   room="hall")


def _cleanup_marimba() -> np.ndarray:
    # one soft marimba D, the played cards gathered up beside it (the chapel's longer room
    # carries the marimba's short ring past 2 s)
    return stinger(strike("marimba", "D4", vel=70, hold=1.6),
                   rustle(0.7, "cards", density=0.7, seed=6).at(0.04).db(-6), room="chapel")


# ============================================================================= Team damage (threat: everyone braces)
def _team_brass() -> np.ndarray:
    # a low brass section swells on a bare fifth and falls away: everyone holds the line
    return stinger(swell("brass", "D3+A3", dur=1.8, peak=0.25, start_db=-5, vel=100).heavy(), room="hall")


def _team_drums_gather() -> np.ndarray:
    # a deep drum roll gathers for a moment and breaks into one war-drum blow
    return stinger(roll("bass_drum", dur=0.32, shape="cresc", vel=(50, 112)), hit("war_drum", vel=127).at(0.3).db(4),
                   onset=0.3, room="hall")


def _team_drums() -> np.ndarray:
    # three strokes of a dry rope drum, as if from all sides, over the low brass section on D
    # (not the frame drum: IMMUNITY's stamp is three strokes on that same sample)
    return stinger(hits("tabor", [(0.0, 104), (0.16, 84), (0.32, 112)]),
                   swell("brass", "D3", dur=1.6, peak=0.3, start_db=-6, vel=96).heavy().db(0), room="hall")


# ============================================================================= New enemy (threat: something looms)
def _new_tuba() -> np.ndarray:
    # a low tuba fifth swells up and sinks back: something big steps out
    return stinger(swell("tuba", "D2+A2", dur=1.9, peak=0.3, start_db=-6, vel=100).heavy(), room="hall")


def _new_gate() -> np.ndarray:
    # a deep drum booms as old timber groans: the castle gate opens
    return stinger(hit("tom", vel=104), creak(1.3, tension=0.25, seed=2).at(0.04).db(2), room="hall")


def _new_horn() -> np.ndarray:
    # a low horn A sounds far off over one deep drum beat
    return stinger(swell("horn", "A2", dur=1.8, peak=0.35, start_db=-7, vel=96).far(0.3),
                   hit("bass_drum", vel=100).db(-2), room="hall")


# ============================================================================= Enemy changes (threat, bent)
def _shift_basses() -> np.ndarray:
    # low basses bow a D and bend it up to a sour E flat: the enemy changes shape (not the
    # tuba: it is New enemy's source, and its bend all but vanished on a phone speaker)
    return stinger(slide("bass", "D3", "Eb3*", dur=1.9, glide=(0.2, 0.55), peak=0.06, start_db=-3, vel=110,
                         fall_db=40).heavy(), room="hall")


def _shift_cymbal() -> np.ndarray:
    # a suspended cymbal shivers up softly over a deep drum
    return stinger(roll("cymbal", dur=1.3, shape="swell", vel=(28, 76)), hit("bass_drum", vel=104).db(0), room="hall")


def _shift_violin() -> np.ndarray:
    # a thin violin D bends up to a sour E flat over a muffled snare roll: something shifts
    # (no felt-drum thud: the row's cymbal option already opens on the bass drum)
    return stinger(slide("violin", "D5", "Eb5*", dur=1.8, glide=(0.2, 0.6), peak=0.2, start_db=-5, vel=80),
                   roll("snare", dur=1.0, shape="swell", vel=(20, 56), lp=3000).db(-10), room="hall")


# ============================================================================= Enemy attacks (threat: the strongest)
def _attack_trombones() -> np.ndarray:
    # trombones hit a hard low D in octaves and let it fall away
    return stinger(swell("trombone", "D2+D3", dur=1.9, peak=0.04, start_db=-3, vel=118, fall_db=44).heavy(),
                   room="hall")


def _attack_war_drum() -> np.ndarray:
    # one huge war-drum blow with a rattle of iron
    return stinger(hit("war_drum", vel=127), chains(1.0, shake=1.0).db(1), room="hall")


def _attack_timpani() -> np.ndarray:
    # a timpani D struck hard with a short, snarling horn stab an octave and more above it
    # (horn D4 over the timpani: the strongest card must carry on a phone, which hardly
    # plays a timpani; and the Paladin card just before it opens on a horn D3)
    return stinger(strike("timpani", "D2", vel=127),
                   swell("horn", "D4", dur=1.3, peak=0.04, start_db=-3, vel=127).db(3), room="hall")


# ============================================================================= No damage (relief: blocked)
def _shielded_strings() -> np.ndarray:
    # strings bloom softly on an open fifth and settle
    return stinger(swell("strings", "D4+A4", dur=1.8, peak=0.22, start_db=-6, vel=72), room="hall")


def _shielded_cymbal() -> np.ndarray:
    # a soft cymbal shimmer that fades as the air settles: the blow glances off (no felt thud and
    # breath: Damage paid's weight set down is one, and the Paladin card just before opens on a
    # struck shield; no breath either: Yield, which can come just before, is a long sigh)
    return stinger(roll("cymbal", dur=1.2, shape="fade", vel=(20, 64)),
                   air(2.0, bright=0.3, peak=0.4, start_db=-8).db(-6), room="hall")


def _shielded_harp() -> np.ndarray:
    # a high harp fourth, A up to D, on a soft breath of air (not from a harp D5: the first
    # set opened every clip on one)
    return stinger(strike("harp", "A5+D6", spread=0.05, vel=66, hold=2.0),
                   air(2.0, bright=0.35, start_db=-8).at(0.03).db(-10), room="hall")


# ============================================================================= Feign death (relief: playing dead)
def _feign_fiddle() -> np.ndarray:
    # a fiddle slides down an octave from D and lies still
    return stinger(slide("fiddle", "D5", "D4", dur=1.9, glide=(0.08, 0.55), peak=0.06, start_db=-3, vel=90),
                   room="hall")


def _feign_cloak() -> np.ndarray:
    # a cloak rustles and a body drops with a soft thud, then stillness
    return stinger(rustle(0.7, "cloth", density=1.0, seed=4), hit("felt_drum", vel=90).at(0.18).db(2), room="hall")


def _feign_lute() -> np.ndarray:
    # one quiet high lute D, then a long breath let out
    return stinger(strike("lute", "D5", vel=70, hold=1.8), breath(1.3, "out").at(0.3).db(-3), room="hall")


# ============================================================================= Damage paid (weariness)
def _paid_cello() -> np.ndarray:
    # a cello D bowed once and left to sag away
    return stinger(swell("cello", "D4", dur=2.0, peak=0.12, start_db=-4, vel=74, fall_db=40), room="hall")


def _paid_sigh() -> np.ndarray:
    # a soft frame-drum thud like a weight set down, and a long sigh
    return stinger(hit("frame_drum", vel=84, felt=True), breath(1.3, "sigh").at(0.03).db(-3), room="hall")


def _paid_cor_anglais() -> np.ndarray:
    # a low cor anglais D sighs as the discarded cards are laid on the pile
    return stinger(swell("english_horn", "D4", dur=1.8, peak=0.1, start_db=-4, vel=74),
                   rustle(0.6, "cards", density=0.6, seed=8).db(-6), room="hall")


# ============================================================================= the candidates
CANDIDATES = [
    # Defeated
    option("defeated", "horn_falls_home", "Horn call falls home",
           "One horn calls on A and falls to D, then fades in a stone hall: the enemy topples and the tension "
           "lets go.",
           _defeated_horn, "triumph", "instrumental", ["release", "fall", "horn"]),
    option("defeated", "cymbal_settles", "Cymbal settles, stones still",
           "A soft-mallet cymbal struck hard and ringing away like settling dust, the stones under it falling "
           "still: the body falls.",
           _defeated_cymbal, "triumph", "textural", ["release", "fall", "cymbal", "earth"]),
    option("defeated", "harp_tumbles", "Harp tumbles, the hall breathes out",
           "A harp rolled downwards (A, D, D) as the hall breathes out: it topples.",
           _defeated_harp, "triumph", "hybrid", ["release", "fall", "harp", "air"]),
    # Exact kill!
    option("exact_kill", "bright_trumpets", "Bright trumpets, one chord",
           "Two trumpets strike a high open fifth (D and A) and let it ring out in the hall: a clean, gleaming "
           "kill.",
           _exact_trumpets, "triumph", "instrumental", ["gleaming", "bright", "trumpet"]),
    option("exact_kill", "triangle_gleam", "Triangle gleam, cymbal wash",
           "A triangle struck bright over a softly struck cymbal, both left to ring: a glint of light.",
           _exact_triangle, "triumph", "textural", ["gleaming", "bright", "metal"]),
    option("exact_kill", "bell_and_horns", "Bell over bright horns",
           "A high bell A rings out over two horns on D and A: a golden release.",
           _exact_bell, "triumph", "hybrid", ["gleaming", "bright", "bell", "horn"]),
    # Hydra regrows
    option("hydra_regrows", "bassoon_creeps_up", "Bassoon creeps back up",
           "A bassoon slithers up from D to A and hangs there: the head grows back.",
           _hydra_bassoon, "threat", "instrumental", ["creeping", "return", "bassoon"]),
    option("hydra_regrows", "marsh_stirs", "The marsh stirs",
           "Water laps and churns as a deep drum roll swells and sinks: something rising from the marsh.",
           _hydra_water, "threat", "textural", ["creeping", "return", "water", "drum"]),
    option("hydra_regrows", "roll_and_tremolo", "Drum roll, creeping strings",
           "A timpani roll swells while tremolo strings creep up from D to A: it is not over.",
           _hydra_roll, "threat", "hybrid", ["creeping", "return", "timpani", "strings"]),
    # Clean-up
    option("cleanup", "low_flute", "One low flute breath",
           "A soft, breathy low wooden-flute D that fades: the table is cleared, a quiet reset.",
           _cleanup_flute, "neutral", "instrumental", ["quiet", "reset", "flute"]),
    option("cleanup", "cards_swept", "Cards swept and squared",
           "The played cards swept across the felt, then two soft taps as the deck is squared.",
           _cleanup_cards, "neutral", "textural", ["quiet", "cards", "wood"]),
    option("cleanup", "marimba_and_cards", "Soft wood note, cards gathered",
           "One soft marimba D, the played cards gathered up beside it.",
           _cleanup_marimba, "neutral", "hybrid", ["quiet", "cards", "marimba"]),
    # Team damage
    option("team_damage", "brass_braced", "Low brass, braced",
           "A low brass section swells on a bare fifth (D and A) and falls away: everyone holds the line.",
           _team_brass, "threat", "instrumental", ["brace", "everyone", "brass"]),
    option("team_damage", "drums_gather", "Drums gather, one blow",
           "A deep drum roll gathers for a moment and breaks into one war-drum blow: everyone braces.",
           _team_drums_gather, "threat", "textural", ["brace", "everyone", "drum"]),
    option("team_damage", "rope_drum_brass", "Rope drum and low brass",
           "Three strokes of a dry rope drum, as if from all sides, over the low brass on D: the whole party is hit.",
           _team_drums, "threat", "hybrid", ["brace", "everyone", "drum", "brass"]),
    # New enemy
    option("new_enemy", "tuba_looms", "Tuba looms from below",
           "A low tuba fifth (D and A) swells up and sinks back: something big steps out.",
           _new_tuba, "threat", "instrumental", ["looming", "arrival", "tuba"]),
    option("new_enemy", "castle_gate", "The castle gate groans",
           "A deep drum booms as old timber groans: the castle gate opens on the next enemy.",
           _new_gate, "threat", "textural", ["looming", "arrival", "wood", "drum"]),
    option("new_enemy", "far_horn_drum", "Far horn over a deep drum",
           "A low horn sounds far off over one deep drum beat: the next foe steps out.",
           _new_horn, "threat", "hybrid", ["looming", "arrival", "horn", "drum"]),
    # Enemy changes
    option("enemy_shift", "basses_bend", "Low basses bend out of shape",
           "Low basses bow a D and bend it up to a sour E flat: the enemy changes shape.",
           _shift_basses, "threat", "instrumental", ["shift", "unease", "strings"]),
    option("enemy_shift", "drum_and_shiver", "Deep drum, shivering cymbal",
           "A deep drum under a suspended cymbal that shivers up softly and fades: something has shifted.",
           _shift_cymbal, "threat", "textural", ["shift", "unease", "drum", "cymbal"]),
    option("enemy_shift", "violin_slips", "Violin slips, muffled drum",
           "A thin violin D bends up to a sour E flat over a muffled snare roll: something shifts.",
           _shift_violin, "threat", "hybrid", ["shift", "unease", "violin", "drum"]),
    # Enemy attacks
    option("enemy_attack", "trombones_strike", "Low trombones strike",
           "Trombones hit a hard low D in octaves and let it fall away: the enemy strikes.",
           _attack_trombones, "threat", "instrumental", ["strongest", "blow", "trombone"]),
    option("enemy_attack", "war_drum_iron", "War drum, rattling iron",
           "One huge war-drum blow with a rattle of iron: the blow is coming.",
           _attack_war_drum, "threat", "textural", ["strongest", "blow", "drum", "chains"]),
    option("enemy_attack", "timpani_horn_stab", "Timpani and horn stab",
           "A timpani D struck hard with a short, snarling horn stab above it.",
           _attack_timpani, "threat", "hybrid", ["strongest", "blow", "timpani", "horn"]),
    # No damage
    option("shielded", "strings_exhale", "Strings breathe out",
           "Strings bloom softly on an open fifth (D and A) and settle: the blow does not land.",
           _shielded_strings, "relief", "instrumental", ["blocked", "strings"]),
    option("shielded", "cymbal_shimmer", "Cymbal shimmer, air settles",
           "A soft cymbal shimmer fading as the air settles: the blow glances off.",
           _shielded_cymbal, "relief", "textural", ["blocked", "cymbal", "air"]),
    option("shielded", "harp_on_air", "High harp on soft air",
           "A high harp A and D on a soft breath of air: safe.",
           _shielded_harp, "relief", "hybrid", ["blocked", "harp", "air"]),
    # Feign death
    option("feign_death", "fiddle_drops", "Fiddle drops dead",
           "A fiddle slides down an octave from D and lies still: playing dead.",
           _feign_fiddle, "relief", "instrumental", ["playing_dead", "fiddle"]),
    option("feign_death", "cloak_falls", "A cloak falls, a soft thud",
           "A cloak rustles and a body drops with a soft thud, then stillness.",
           _feign_cloak, "relief", "textural", ["playing_dead", "cloth", "drum"]),
    option("feign_death", "lute_then_breath", "Lute note, breath let go",
           "One quiet high lute D, then a long breath let out: they bought it.",
           _feign_lute, "relief", "hybrid", ["playing_dead", "lute", "breath"]),
    # Damage paid
    option("damage_paid", "cello_tired_bow", "Cello, one tired bow",
           "A cello D bowed once and left to sag away: the price is paid.",
           _paid_cello, "weariness", "instrumental", ["accepted", "cello"]),
    option("damage_paid", "weight_set_down", "Weight set down, a sigh",
           "A soft frame-drum thud like a weight set down, and a long sigh.",
           _paid_sigh, "weariness", "textural", ["accepted", "drum", "breath"]),
    option("damage_paid", "cor_anglais_cards", "Cor anglais and cards",
           "A low cor anglais D sighs as the discarded cards are laid on the pile.",
           _paid_cor_anglais, "weariness", "hybrid", ["accepted", "cor_anglais", "cards"]),
]
