"""Info pop-ups, the turn group, second set: short stingers that carry one feeling over the
mission music (docs/INFO_POPUPS.md; the owner's feedback on the first set: fewer instruments,
no melody, no shared opening, an emotion that sits on top of dark music). Built with
``_stingers`` (one or two sound sources, at most three pitched notes, D and A plus one
marked colour note, a clear onset and a natural decay, 2.0-2.4 s; the Jester rows 2.6 s).

Rows and the feeling each carries (``_stingers.PALETTE``; three options per row, one per
approach: instrumental, textural, hybrid):
  turn             neutral: "your move", the quietest clip (mastered 3 dB softer)
  yield            weariness: a sigh, the turn given up (3 dB softer)
  corrupted        dread: a card turns bad and another is banished (its colour: B flat
                   rubbing on A)
  restored         warmth: the light comes back (its colour: the major third F sharp)
  declared         neutral but decisive: "this card counts as..."
  kinfolk_flute    warmth: family voices together, just before the flute's box
  scarlet_whistle  mischief: "over here!", just before the whistle's box
  azure_emblem     mystery: the blue emblem glints, a hidden card is placed or kept
  mother_corrupt   dread: the Evergreen Mother's lullaby gone dark (a minor colour, F)
  mother_restored  warmth: the same voice healed, high and open
  the four Jester rows   mischief: the owner's Whistle jig (tunes_turn's render, imported,
                   started straight on the whistle) and two simple tricks each

Each option opens on its own source and pitch (``python3 _stingers.py over stingers_turn``
lists any shared opening); the pairs that answer each other keep one source (the Mother's
hum, her music box) on different notes.
"""
from __future__ import annotations

from typing import Sequence, Tuple

import numpy as np

import _info_common as IC
from _stingers import (JESTER_S, A, Layer, air, breath, chains, creak, embers, heartbeat, hit, hits, option, roll,
                       rumble, rustle, slide, stinger, strike, swell, tune, water, wind)
from _stingers import _drop_tail, _from_onset, _prog
from catalog import Candidate
from tunes_turn import _whistle_jig


# ============================================================================= helpers
def _shake(times: Sequence[Tuple[float, float]], pitches: Sequence[str] = ("D6", "A6", "D7"), per: int = 3,
           vel: int = 84, seed: int = 0, spread: float = 0.025, lp: float = 5200.0, inst: str = "small_bell",
           ring: float = 0.8) -> Layer:
    """A shake of small bells (one source): at each (time, strength) ``per`` bells of
    ``pitches`` ring a few ms apart, as a jester's cap or a crier's hand bell does."""
    rng = np.random.default_rng(seed)
    ms = [A.midi(p) for p in pitches]
    notes = []
    for t0, s in times:
        for b in range(per):
            t = t0 + (float(rng.uniform(0, spread)) if b else 0.0)
            notes.append(IC.n(_prog(inst), ms[int(rng.integers(0, len(ms)))], round(t, 4), ring,
                              vel=int(np.clip(s * vel * rng.uniform(0.8, 1.15), 20, 127))))
    x = _from_onset(IC.render(tune(notes), max(t for t, _ in times) + 2.0))
    return Layer(_drop_tail(A.lowpass(x, lp, 4)), inst, "shake", tuple(sorted(set(ms))))


def _bounce(inst: str = "marimba", pitch: str = "D5", n: int = 8, first: float = 0.34, ratio: float = 0.74,
            vel: int = 96, decay: float = 0.82, ring: float = 0.6) -> Layer:
    """One note struck like a ball dropped on a table: each bounce sooner and softer."""
    m = A.midi(pitch)
    notes, t, gap, v = [], 0.0, first, float(vel)
    for _ in range(n):
        notes.append(IC.n(_prog(inst), m, round(t, 4), ring, vel=int(max(12, v))))
        t += gap
        gap *= ratio
        v *= decay
    x = _from_onset(IC.render(tune(notes), t + 2.0))
    return Layer(_drop_tail(x), inst, "bounce", (m,))


def _jester(*layers: Layer, room: str = "tavern") -> np.ndarray:
    """A Jester row's clip (they may run to 2.6 s)."""
    return stinger(*layers, room=room, max_s=JESTER_S)


# ============================================================================= Turn (neutral, the quietest)
def _turn_lute() -> np.ndarray:
    # one soft lute A, let ring in the tavern: your move (A4: above the music's low-mid, heard on a phone)
    return stinger(strike("lute", "A4", vel=58, hold=1.6), room="tavern")


def _turn_knock() -> np.ndarray:
    # two knuckle knocks on the table (a player's "your go"), a breath of room air after
    return stinger(hits("knock", [(0.0, 72), (0.17, 58)]),
                   air(2.3, bright=0.3, start_db=-12, peak=0.3).db(-14), room="tavern")


def _turn_celesta_card() -> np.ndarray:
    # one soft celesta D, a card's edge brushing the felt just after it (not a second plucked
    # A4 beside the lute option; a harp D4 is lost on a phone and a harp D5 was the first set's
    # opening on every clip)
    return stinger(strike("celesta", "D5", vel=52, hold=1.8),
                   rustle(0.3, "cards", density=0.7, seed=3).at(0.06).db(-8), room="near")


# ============================================================================= Yield (weariness)
def _yield_cello() -> np.ndarray:
    # a cello sighs down a fifth, A to D, and fades: the turn given up (the Fluid cello: the
    # glide plays its F sharp sample, in tune at both ends; MuseScore's lands 12 cents flat)
    return stinger(slide("cello", "A4", "D4", dur=1.7, glide=(0.15, 0.55), peak=0.12, start_db=-3, vel=78,
                         fall_db=44, bank="fluid"), room="hall")


def _yield_sigh() -> np.ndarray:
    # a long tired breath out as a cloak settles
    return stinger(breath(1.6, "sigh"), rustle(0.7, "cloth", density=0.6).at(0.05).db(-8), room="hall")


def _yield_clarinet() -> np.ndarray:
    # one low clarinet D set down softly, a cloak settling with it
    return stinger(swell("clarinet", "D4", dur=1.8, peak=0.06, start_db=-3, vel=70),
                   rustle(0.9, "cloth", density=0.7, seed=1).at(0.06).db(-9), room="hall")


# ============================================================================= Corrupted (dread)
def _corrupted_viola() -> np.ndarray:
    # a viola holds a sour B flat and sags onto A, swelling as it lands: the card goes bad
    return stinger(slide("viola", "Bb4*", "A4", dur=1.9, glide=(0.12, 0.42), peak=0.75, start_db=-5, vel=80),
                   room="crypt")


def _corrupted_chains() -> np.ndarray:
    # chains shaken and let fall into a low stone rumble: a card banished below
    return stinger(chains(1.1, shake=0.8), rumble(2.1, depth=0.5, peak=0.2, start_db=-4).db(-9), room="crypt")


def _corrupted_reeds() -> np.ndarray:
    # a felt-drum thud, then two cor anglais a half step apart (A and B flat) souring together
    return stinger(hit("felt_drum", vel=96),
                   swell("english_horn", "A4+Bb4*", dur=1.6, peak=0.45, start_db=-9, vel=70).db(-4), room="crypt")


# ============================================================================= Restored (warmth)
def _restored_horns() -> np.ndarray:
    # two soft horns bloom on A and D and fade: the light coming back
    return stinger(swell("horn", "A3+D4", dur=1.6, peak=0.35, start_db=-7, vel=72), room="hall")


def _restored_vibes() -> np.ndarray:
    # a soft-mallet vibraphone roll on A swells and fades, a warm glow (not the marimba: the
    # Druid card, which follows a restored Druid, rolls a marimba; and a marimba D4 all but
    # vanishes on a phone speaker)
    return stinger(roll("vibraphone", "A4", dur=1.4, shape="swell", vel=(26, 70)), room="hall")


def _restored_harp() -> np.ndarray:
    # a harp rolls up A, D and the warm F sharp (the major third: light after the dark), a breath out
    return stinger(strike("harp", "A3+D4+F#4*", spread=0.08, vel=66, hold=1.8),
                   breath(1.1, "out").at(0.24).db(-9), room="hall")


# ============================================================================= Declared (neutral, decisive)
def _declared_harpsichord() -> np.ndarray:
    # one firm harpsichord stroke on an open fifth, D and A, its top softened: so it is
    # decreed (not a lute strum: the Bard card, which follows a declared Bard, strums the lute)
    return stinger(strike("harpsichord", "D4+A4", spread=0.015, vel=96, hold=2.2, lp=4500), room="hall")


def _declared_bell() -> np.ndarray:
    # a crier's hand bell rung twice: hear ye (a tubular D5: its loudest partials are D and A)
    return stinger(_shake([(0.0, 1.0), (0.22, 0.8)], pitches=("D5",), per=1, inst="hand_bell", ring=1.0, lp=4500),
                   room="hall")


def _declared_rim() -> np.ndarray:
    # a stick taps a drum's rim and a glockenspiel D rings with it (not the dulcimer A4 the
    # Bard card opens on)
    return stinger(hit("rim", vel=90), strike("glockenspiel", "D6", vel=74, hold=2.0).db(-2), room="hall")


# ============================================================================= Kinfolk Flute (warmth, before its box)
def _kinfolk_flutes() -> np.ndarray:
    # two wooden flutes breathe A and D together and fade: family voices
    return stinger(swell("wooden_flute", "A4+D5", dur=1.6, peak=0.35, start_db=-6, vel=74), room="hall")


def _kinfolk_hearth() -> np.ndarray:
    # a hearth fire crackles as cloaks gather round it (the crackles' peaks held closer to the
    # body, crest 10 dB, or the master leaves the clip ~4 dB under its siblings)
    return stinger(embers(2.3, crackle=1.3, seed=1), rustle(0.9, "cloth", density=0.8).at(0.1).db(-10), room="tavern",
                   crest_db=10)


def _kinfolk_flute_harp() -> np.ndarray:
    # one wooden flute D over a plucked harp A
    return stinger(swell("wooden_flute", "D5", dur=1.6, peak=0.3, start_db=-5, vel=72),
                   strike("harp", "A3", vel=62, hold=1.6).db(-3), room="hall")


# =========================================================================== Scarlet Whistle (mischief, before its box)
def _scarlet_call() -> np.ndarray:
    # a tin whistle flicks up from A to a held high D: over here!
    return stinger(slide("tin_whistle", "A5", "D6", dur=2.0, glide=(0.03, 0.15), peak=0.2, start_db=-4, vel=84),
                   room="tavern")


def _scarlet_claves() -> np.ndarray:
    # two quick clave clicks ("psst"), a triangle ringing on the second
    return stinger(hits("claves", [(0.0, 90), (0.14, 76)]), hit("triangle", vel=60).at(0.14).db(-4), room="tavern")


def _scarlet_chirp() -> np.ndarray:
    # a short whistle chirp up from D to A, a tambourine slapped with it
    return stinger(slide("tin_whistle", "D6", "A6", dur=1.9, glide=(0.02, 0.1), peak=0.12, start_db=-4),
                   hit("tambourine", vel=80).db(-3), room="tavern")


# ============================================================================= Azure Emblem (mystery, before its box)
def _azure_strings() -> np.ndarray:
    # one cold, thin string D high up, hanging in a tall room (the Azure card comes right
    # after the Mage card, whose options are a blown A5 and glassy glints: so no flute A5 and
    # no glints here)
    return stinger(swell("slow_strings", "D6", dur=1.7, peak=0.4, start_db=-6, vel=62), room="chapel")


def _azure_bell() -> np.ndarray:
    # one tiny bell far off in a cave, cold air moving under it: something kept hidden
    return stinger(strike("small_bell", "A5", vel=70).far(0.5), air(2.1, bright=0.6, start_db=-6).db(-12), room="cave")


def _azure_vibes() -> np.ndarray:
    # a vibraphone fifth, D and A, shimmering in a cave, cool air behind it
    return stinger(strike("vibraphone", "D5+A5", vel=70, hold=1.8), air(2.0, bright=0.6).at(0.05).db(-12), room="cave")


# ============================================================================= Evergreen Mother, corrupt (dread)
def _mother_corrupt_hum() -> np.ndarray:
    # a low hummed A with the dark F above it: her lullaby gone wrong
    return stinger(swell("hum", "A3+F4*", dur=1.8, peak=0.5, start_db=-8, vel=74), room="crypt")


def _mother_corrupt_cradle() -> np.ndarray:
    # an empty cradle rocks once, creak... creak (not a creak in the wind: that is the Druid's
    # creaking bough)
    return stinger(creak(0.7, tension=0.3, seed=1), creak(0.7, tension=0.25, seed=2).at(0.9).db(-4), room="crypt")


def _mother_corrupt_box() -> np.ndarray:
    # a music box plinks D and the minor F over a slow heartbeat
    return stinger(strike("music_box", "D5+F5*", spread=0.42, vel=70, hold=1.6),
                   heartbeat(2, bpm=58, vel=90).db(-4), room="crypt")


# ============================================================================= Evergreen Mother, restored (warmth)
def _mother_restored_hum() -> np.ndarray:
    # the same voice healed: a warm hum on A and D, high and open
    return stinger(swell("hum", "A4+D5", dur=1.8, peak=0.45, start_db=-8, vel=70), room="hall")


def _mother_restored_leaves() -> np.ndarray:
    # a soft breeze through forest leaves
    return stinger(wind(2.3, strength=0.25, peak=0.5, seed=4), rustle(1.0, "leaves", density=0.7, seed=4).db(-2),
                   room="open")


def _mother_restored_box() -> np.ndarray:
    # her music box again, healed: A and D, beside a running brook
    return stinger(strike("music_box", "A5+D6", spread=0.4, vel=66, hold=1.6), water(2.2, "stream").db(-10),
                   room="hall")


# ============================================================================= the Jester (mischief)
def _jig() -> np.ndarray:
    # the owner's Whistle jig (tunes_turn's render, one bar longer) started straight on the
    # whistle as combat.py's original is: no harp pickup before it and no harp note after it
    return _whistle_jig(pickup_kind=None, tail=False)


def _jester_bells() -> np.ndarray:
    # the jester's cap bells shaken, a last jingle as he settles
    return _jester(_shake([(0.0, 1.0), (0.12, 0.7), (0.24, 0.85), (0.62, 0.55), (1.1, 0.5)], seed=4))


def _jester_fiddle() -> np.ndarray:
    # a fiddle flicks up from A to D and holds it, cheeky (from D up to A it lands 15 cents flat)
    return _jester(slide("fiddle", "A4", "D5", dur=2.1, glide=(0.02, 0.12), peak=0.1, start_db=-3, vel=92))


def _claim_bounce() -> np.ndarray:
    # a marimba D bounces like a ball dropped on the table: up for grabs
    return _jester(_bounce("marimba", "D5", n=8, first=0.34, ratio=0.74))


def _claim_flam() -> np.ndarray:
    # a snare flam and a soft cymbal shimmer: ta-da, who takes it?
    return _jester(hits("snare", [(0.0, 64), (0.028, 104)]),
                   roll("cymbal", dur=0.9, shape="fade", vel=(20, 60)).at(0.03).db(-8), room="hall")


def _refresh_riffle() -> np.ndarray:
    # the hand riffled away, a glockenspiel ting as the new one lands
    return _jester(rustle(0.8, "cards", density=1.8, seed=2), strike("glockenspiel", "A6", vel=70).at(0.42).db(-4))


def _refresh_tumble() -> np.ndarray:
    # a hammered dulcimer tumbles down D, A, D like cards falling
    return _jester(strike("hammered_dulcimer", "D5+A5+D6", spread=0.09, down=True, vel=92, hold=2.0))


def _attack_dive() -> np.ndarray:
    # a woodblock tock and the jig's recorder diving from D down to A: he pounces
    return _jester(hit("woodblock", vel=96),
                   slide("recorder", "D6", "A5", dur=1.9, glide=(0.04, 0.2), peak=0.05, start_db=-2, vel=100)
                   .at(0.05).db(-1))


def _attack_tambourine() -> np.ndarray:
    # three tambourine slaps, a triangle ringing on the last
    return _jester(hits("tambourine", [(0.0, 100), (0.11, 70), (0.22, 90)]),
                   hit("triangle", vel=66).at(0.22).db(-7))


# ============================================================================= the candidates
_JIG_NOTE = ("The Whistle jig you picked, one bar longer: a wooden whistle's quick jig over a little drum and a "
             "tambourine, ending on a held high D with the cap bells. It starts straight on the whistle.")


def _jig_option(row: str) -> Candidate:
    return option(row, "jig", "Whistle jig", _JIG_NOTE, _jig, "mischief", None, ["owner_pick", "tune"])


CANDIDATES = [
    # Turn
    option("turn", "lute_a", "Lute, one soft A",
           "One soft lute A, plucked and left to ring in a small wooden room: your move.",
           _turn_lute, "neutral", "instrumental", ["quiet", "lute"]),
    option("turn", "table_knock", "Two knocks on the table",
           "Two knuckle knocks on the table, the way a player says 'your go', and a breath of room air.",
           _turn_knock, "neutral", "textural", ["quiet", "wood"]),
    option("turn", "celesta_and_card", "Celesta D, a card's edge",
           "One soft celesta D with a card brushing the felt just after it.",
           _turn_celesta_card, "neutral", "hybrid", ["quiet", "celesta", "cards"]),
    # Yield
    option("yield", "cello_sigh", "Cello sighs down",
           "A cello slides down from A to D and fades, like a tired sigh.",
           _yield_cello, "weariness", "instrumental", ["quiet", "strings"]),
    option("yield", "long_sigh", "A long sigh",
           "A long tired breath out as a cloak settles.",
           _yield_sigh, "weariness", "textural", ["quiet", "breath"]),
    option("yield", "low_clarinet", "Low clarinet, set down",
           "One low clarinet D set down softly and fading, a cloak settling with it.",
           _yield_clarinet, "weariness", "hybrid", ["quiet", "clarinet"]),
    # Corrupted
    option("corrupted", "viola_sags", "Viola sags, B flat to A",
           "A viola holds a sour B flat and sags down onto A, swelling as it lands, in a dark crypt: the card goes "
           "bad.",
           _corrupted_viola, "dread", "instrumental", ["dark", "strings"]),
    option("corrupted", "chains_below", "Chains into the deep",
           "Chains shaken and let fall into a low stone rumble: a card banished below.",
           _corrupted_chains, "dread", "textural", ["dark", "chains"]),
    option("corrupted", "sour_reeds", "Thud and sour reeds",
           "A soft felt-drum thud, then two cor anglais half a step apart souring together.",
           _corrupted_reeds, "dread", "hybrid", ["dark", "reeds", "drum"]),
    # Restored
    option("restored", "soft_horns", "Soft horns bloom",
           "Two soft horns bloom on A and D and fade in a stone hall: the light coming back.",
           _restored_horns, "warmth", "instrumental", ["warm", "horn"]),
    option("restored", "vibraphone_glow", "Vibraphone glow",
           "A soft-mallet vibraphone roll on A swells and fades: a warm glow coming back.",
           _restored_vibes, "warmth", "textural", ["warm", "vibraphone"]),
    option("restored", "harp_light", "Harp rolls into the light",
           "A harp rolls up A, D and a warm F sharp (the bright third after the dark), with a breath let out.",
           _restored_harp, "warmth", "hybrid", ["warm", "harp", "breath"]),
    # Declared
    option("declared", "harpsichord_stroke", "One harpsichord stroke",
           "A single firm harpsichord stroke on an open fifth, D and A: so it is decreed.",
           _declared_harpsichord, "neutral", "instrumental", ["decisive", "harpsichord"]),
    option("declared", "criers_bell", "Crier's bell, twice",
           "A crier's hand bell rung twice: hear ye.",
           _declared_bell, "neutral", "textural", ["decisive", "bell"]),
    option("declared", "rim_glockenspiel", "Rim tap and a bright ting",
           "A stick taps a drum's rim as a glockenspiel D rings out.",
           _declared_rim, "neutral", "hybrid", ["decisive", "glockenspiel", "drum"]),
    # Kinfolk Flute
    option("kinfolk_flute", "two_flutes", "Two wooden flutes",
           "Two wooden flutes breathe A and D together and fade: family voices.",
           _kinfolk_flutes, "warmth", "instrumental", ["warm", "flute"]),
    option("kinfolk_flute", "hearth", "Round the hearth",
           "A hearth fire crackling as cloaks gather round it.",
           _kinfolk_hearth, "warmth", "textural", ["warm", "fire"]),
    option("kinfolk_flute", "flute_and_harp", "Flute over a harp",
           "One wooden flute D breathing over a plucked harp A.",
           _kinfolk_flute_harp, "warmth", "hybrid", ["warm", "flute", "harp"]),
    # Scarlet Whistle
    option("scarlet_whistle", "whistle_up", "Whistle flicks up",
           "A tin whistle flicks up from A to a held high D: over here!",
           _scarlet_call, "mischief", "instrumental", ["whistle"]),
    option("scarlet_whistle", "claves_psst", "Claves, psst",
           "Two quick clave clicks, a triangle ringing on the second.",
           _scarlet_claves, "mischief", "textural", ["wood", "triangle"]),
    option("scarlet_whistle", "chirp_tambourine", "Whistle chirp, tambourine",
           "A short whistle chirp up from D to A with a tambourine slapped on it.",
           _scarlet_chirp, "mischief", "hybrid", ["whistle", "tambourine"]),
    # Azure Emblem
    option("azure_emblem", "cold_strings", "Cold strings, high D",
           "One cold, thin string D high up, hanging in a tall stone room.",
           _azure_strings, "mystery", "instrumental", ["strings", "cool"]),
    option("azure_emblem", "far_small_bell", "A tiny bell, far off",
           "One tiny bell far off in a cave, cold air moving under it: something kept hidden.",
           _azure_bell, "mystery", "textural", ["bell", "cool"]),
    option("azure_emblem", "vibraphone_cave", "Vibraphone in a cave",
           "A vibraphone fifth, D and A, shimmering in a cave with cool air behind it.",
           _azure_vibes, "mystery", "hybrid", ["vibraphone", "cool"]),
    # Evergreen Mother, corrupt
    option("mother_corrupt", "dark_hum", "Her hum, darkened",
           "A low hummed A with a dark F above it: a mother's lullaby gone wrong.",
           _mother_corrupt_hum, "dread", "instrumental", ["dark", "voice"]),
    option("mother_corrupt", "empty_cradle", "Empty cradle",
           "An empty cradle rocking once in a cold crypt: creak... creak.",
           _mother_corrupt_cradle, "dread", "textural", ["dark", "wood"]),
    option("mother_corrupt", "music_box_heartbeat", "Music box, heartbeat",
           "A music box plinks D and a minor F over a slow heartbeat.",
           _mother_corrupt_box, "dread", "hybrid", ["dark", "music_box", "heartbeat"]),
    # Evergreen Mother, restored
    option("mother_restored", "warm_hum", "Her hum, healed",
           "The same voice healed: a warm hum on A and D, high and open.",
           _mother_restored_hum, "warmth", "instrumental", ["warm", "voice"]),
    option("mother_restored", "forest_breeze", "Forest breeze",
           "A soft breeze moving through forest leaves.",
           _mother_restored_leaves, "warmth", "textural", ["warm", "wind", "leaves"]),
    option("mother_restored", "music_box_brook", "Music box by a brook",
           "Her music box again, healed: A and D, beside a running brook.",
           _mother_restored_box, "warmth", "hybrid", ["warm", "music_box", "water"]),
    # Jester (base)
    _jig_option("jester"),
    option("jester", "cap_bells", "Cap bells shaken",
           "The little bells on a jester's cap shaken, with a last jingle as he settles.",
           _jester_bells, "mischief", "textural", ["bells"]),
    option("jester", "fiddle_flick", "Fiddle flicks up",
           "A fiddle flicks up from A to D and holds it, cheeky.",
           _jester_fiddle, "mischief", "instrumental", ["fiddle"]),
    # Jester claim
    _jig_option("jester_claim"),
    option("jester_claim", "marimba_bounce", "Bouncing marimba",
           "A marimba D bouncing like a ball dropped on the table: up for grabs.",
           _claim_bounce, "mischief", "instrumental", ["wood"]),
    option("jester_claim", "snare_flam", "Snare flam, cymbal",
           "A snare flam and a soft cymbal shimmer: ta-da, who takes it?",
           _claim_flam, "mischief", "textural", ["drum", "cymbal"]),
    # Solo Jester: new hand
    _jig_option("solo_jester_refresh"),
    option("solo_jester_refresh", "riffle_ting", "Riffle and a ting",
           "The hand riffled away, a glockenspiel ting as the new one lands.",
           _refresh_riffle, "mischief", "hybrid", ["cards", "bell"]),
    option("solo_jester_refresh", "dulcimer_tumble", "Dulcimer tumbles",
           "A hammered dulcimer tumbles down D, A, D like cards falling.",
           _refresh_tumble, "mischief", "instrumental", ["dulcimer"]),
    # Solo Jester: attack
    _jig_option("solo_jester_attack"),
    option("solo_jester_attack", "recorder_dive", "Woodblock, recorder dives",
           "A woodblock tock and the jig's recorder diving from D down to A: he pounces.",
           _attack_dive, "mischief", "hybrid", ["wood", "recorder"]),
    option("solo_jester_attack", "tambourine_slaps", "Tambourine slaps",
           "Three tambourine slaps, a triangle ringing on the last.",
           _attack_tambourine, "mischief", "textural", ["tambourine", "triangle"]),
]
