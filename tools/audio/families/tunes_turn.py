"""Info pop-ups, the turn group (docs/INFO_POPUPS.md, "Melody plan"): Turn and Yield, the
cards of an attack entering play (Corrupted, Restored, Declared), the relics asked just
before their boxes (Kinfolk Flute, Scarlet Whistle, Azure Emblem), the Evergreen Mother's
two lullabies, and the four Jester rows (the Whistle jig, one bar longer).

Every clip is built by ``_info_common.clip``: the harp pickup (a soft card flick and one
plucked harp D), a two-bar motif in 6/8 on the card's own instruments, a held cadence over
the soft rolled harp chord, the shared harp tail, the tavern room. A card shown right
before a decision box ends open on A over the open A-E fifth (Kinfolk Flute, Scarlet
Whistle, Azure Emblem, Mother corrupt); the others end on D. Turn and Yield are the
quietest of the set (their events are mastered 3 dB softer), so they are sparse too.

Pairs that answer each other:
  Corrupted / Restored         B flat falling to A on a viol, then B flat lifting to B,
                               C sharp and D on a wooden flute
  Mother corrupt / restored    one lullaby (D C A B-flat / D C# A B C#): on viol and low
                               flute over a heartbeat in D minor, stopping on A; healed
                               on wooden flute over a rocking harp in D major, rising to D
The Jester rows share the Whistle jig (combat.py's whistle_jig, the owner's favourite):
the same recorder, tabor, tambourine and cap bells, one bar longer and resolved on a held
high D; the claim, new-hand and attack rows each add one variant of it.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np

from _info_common import *  # noqa: F401,F403

# ============================================================================= helpers
_BELLS = ["D6", "E6", "F#6", "A6", "B6", "D7", "E7"]          # the jester's cap: D major pentatonic


def _cap_bells(shakes: Sequence[Tuple[float, float]], seed: int, per: int = 4, spread: float = 0.03) -> np.ndarray:
    """The little bells on a jester's cap shaken at (time, strength), as combat.py's
    Whistle jig shakes them: each shake rings a handful of small bells a few ms apart."""
    rng = np.random.default_rng(seed)
    notes = []
    for t0, s in shakes:
        for b in range(per):
            t = t0 + (float(rng.uniform(0, spread)) if b else 0.0)
            notes.append(n("cap_bells", str(rng.choice(_BELLS)), round(t, 4), 0.12,
                           vel=int(np.clip(s * rng.uniform(70, 110), 20, 127))))
    return A.lowpass(render(notes), 6500, 2)


def _crest(x: np.ndarray) -> float:
    """How far a part's loudest 50 ms block stands above its ``level`` (dB). clip() sets a
    layer by ``level`` (the 95th percentile of its blocks), which reads a single bell
    stroke in a long buffer 10 to 18 dB too quiet and so boosts it by as much: subtract
    this from a bell's dB so the dB is where its strike really sits against the motif."""
    blk = A.n_of(0.05)
    y = A.highpass(x, 100, 1)
    k = max(1, len(y) // blk)
    y = fit(y, k * blk / SR)
    top = 10 * np.log10(float(np.max(np.mean(y.reshape(k, blk) ** 2, axis=1))) + 1e-20)
    return top - level(x)


def _bell_layer(x: np.ndarray, t: float, db: float) -> Tuple[np.ndarray, float, float]:
    """A bell (or a shake of bells) as a clip layer whose STRIKE sits ``db`` from the motif."""
    return (x, t, db - _crest(x))


def _hits(name_: str, times_vels: Sequence[Tuple[float, int]]) -> np.ndarray:
    """A tavern percussion part (``perc`` strokes at (time, velocity)) as one layer."""
    x = np.zeros(A.n_of(0.1))
    for t, v in times_vels:
        x = A.mix_at(x, perc(name_, v), t)
    return x


def _small_bell(pitch: str, vel: int = 40, lp: float = 4200.0) -> np.ndarray:
    """A soft hand bell: the small bell (tinkle bell, a clear fundamental) with its top
    taken down, so it glows instead of pinging."""
    return A.lowpass(render([n("cap_bells", pitch, 0.0, 0.9, vel=vel)], 2.0), lp, 4)


def _cracked_bell(pitch: str = "D5", vel: int = 58) -> np.ndarray:
    """A cracked bell: a tubular bell and its own double a little under half a step sharp,
    so the two beat roughly, darkened."""
    x = render([n("temple_bell", pitch, 0.0, 1.4, vel=vel),
                n("temple_bell", pitch, 0.0, 1.4, vel=max(1, vel - 8), bend=(0.42, 0.42))], 2.2)
    return A.lowpass(A.peak_eq(x, 2400, -4.0, 1.0), 3200, 4)


def _damped(notes: Sequence[INote], at_: float, fall: float = 0.35) -> np.ndarray:
    """A part rendered on its own and damped from ``at_`` (a hand on the harp strings at
    the cadence, so the last chord does not ring into the next)."""
    return choke(render(notes), at_, fall)


def _heartbeat(beats_at: Sequence[float], vel: int = 84) -> np.ndarray:
    """A slow heartbeat on a frame drum: lub (strong) and dub (soft) 0.17 s apart."""
    x = np.zeros(A.n_of(0.1))
    for t in beats_at:
        x = A.mix_at(x, perc("frame_drum", vel), t)
        x = A.mix_at(x, perc("frame_drum", int(vel * 0.7)), t + 0.17)
    return A.lowpass(x, 2500, 2)


# ============================================================================= Turn and Yield
def _turn_lute_bell() -> np.ndarray:
    # 'your move': the lute plucks A, then D one beat later as a soft hand bell glows on it
    motif = phrase("lute", "A4:3@80 D5:6@90", legato=1.0, seed=11)
    return clip(motif, end="D", mood="party", cadence_at=BAR + EIGHTH,
                layers=[_bell_layer(_small_bell("D6", 38), DQ, -9.0)])


def _turn_strums() -> np.ndarray:
    # the same A then D, slower and lower: two soft lute strums a bar apart, a hand bell on each
    motif = roll("lute", ["A2", "E3", "A3", "C#4"], 0.0, 0.62, vel=64, spread=0.028)
    motif += roll("lute", ["D3", "A3", "D4", "F#4"], BAR, 1.1, vel=68, spread=0.028)
    return clip(motif, end="D", mood="party", cadence_at=BAR + DQ,
                layers=[_bell_layer(_small_bell("A5", 34), 0.0, -12.0), _bell_layer(_small_bell("D6", 38), BAR, -10.0)])


def _yield_viol() -> np.ndarray:
    # a viol sighs A to F# over one soft lute D; the harp's D chord settles under the F#
    motif = [n("lute", "D3", 0.0, 1.4, vel=50),
             n("viol", "A4", 0.0, DQ + 0.03, vel=66, swell=(74, 100)),
             n("viol", "F#4", DQ, 1.0, vel=62, swell=(98, 26))]
    return clip(motif, end="D", mood="party", cadence_at=BAR + DQ, bed_db=-13.0)


# ============================================================================= the attack's cards
def _corrupted() -> np.ndarray:
    # a low viol drone on D and A; a cracked bell; the viol's B flat falls to A as a card
    # slides off to the banished pile, then sinks to a low D
    drone = [n("bass_viol", "D3", 0.0, MOTIF + 0.5, vel=60, swell=(46, 100)),
             n("bass_viol", "A3", 0.02, MOTIF + 0.48, vel=50, swell=(40, 88))]
    melody = [n("viol", "Bb4", DQ, DQ + 0.04, vel=78, swell=(80, 108)),
              n("viol", "A4", BAR, BAR, vel=74, swell=(104, 70))]
    slide = A.lowpass(card_sound("draw", keep=0.22), 3500, 2)
    return clip(drone + melody, end="D4", mood="enemy", instrument="viol", held_vel=70,
                layers=[(_cracked_bell("D5", 60), 0.0, -7.0), (slide, BAR - 0.06, -9.0)])


def _restored() -> np.ndarray:
    # the Corrupted figure turned upward: the flute's B flat lifts to B, C sharp and a held D,
    # the harp rising under it (G minor, G major, A, D: the light coming back)
    flute = phrase("wooden_flute", "Bb4:3 B4:3 C#5:3", vel=74, legato=1.02, accent=6, seed=21)
    harp = phrase("harp", "G2 D3 Bb3 G2 D3 B3 A2 E3 C#4", vel=66, legato=3.0, accent=6, seed=22)
    return clip(flute, end="D", mood="party", instrument="wooden_flute", held_vel=82,
                cadence_at=BAR + DQ, hold=0.62, layers=[(_damped(harp, BAR + DQ), 0.0, -6.0)])


def _declared() -> np.ndarray:
    # two quick lute plucks and a decisive strummed D chord, a card slapped down on the felt
    # with it, the tabor marking each
    motif = [n("lute", "A4", 0.0, 0.1, vel=86), n("lute", "C#5", EIGHTH, 0.1, vel=82)]
    motif += roll("lute", ["D3", "A3", "D4", "F#4", "A4", "D5"], DQ, 1.25, vel=108, spread=0.011)
    tabor = _hits("tabor", [(0.0, 62), (EIGHTH, 56), (DQ, 104), (BAR, 50)])
    return clip(motif, end="D", mood="party", cadence_at=BAR,
                layers=[(tabor, 0.0, -11.0), (card_sound("play"), DQ - 0.004, -7.0)])


# ============================================================================= relics (before their boxes: open on A)
def _kinfolk_flute() -> np.ndarray:
    # two wooden flutes in parallel thirds over a lute's bass, the family together; they
    # stop on A over F#, still a third apart: a question to the others
    upper = phrase("wooden_flute", "F#5:2 E5:1 D5:2 E5:1 F#5:2 G5:1 A5:2 B5:1", vel=74, seed=31)
    lower = phrase("wooden_flute", "D5:2 C#5:1 B4:2 C#5:1 D5:2 E5:1 F#5:2 G5:1", vel=62, seed=32)
    held = [n("wooden_flute", "A5", MOTIF, 0.5, vel=76, swell=(118, 46)),
            n("wooden_flute", "F#5", MOTIF + 0.008, 0.5, vel=64, swell=(112, 42))]
    bass = [n("lute", p, t, 0.31, vel=v) for p, t, v in
            (("D3", 0.0, 60), ("G2", DQ, 54), ("D3", BAR, 58), ("G2", BAR + DQ, 54))]
    return clip(upper + lower + held + bass, end="A", mood="party")


# The tin whistle: the bank's piccolo in its soft bottom octave, a fife (_info_common maps
# "tin_whistle" to it; General MIDI's "whistle" warbles, two detuned layers beating 10 to
# 40 Hz about 20 dB deep, a synthetic flutter on a held note).
_TIN = "tin_whistle"


def _scarlet_whistle() -> np.ndarray:
    # 'over here!': two quick tin-whistle calls flicking from A up to high D, answered by a
    # hammered dulcimer that runs down and stops on A
    calls: List[INote] = []
    for t0, held in ((0.0, 0.2), (DQ, 0.26)):
        calls += [n(_TIN, "A5", t0, 0.05, vel=62), n(_TIN, "D6", t0 + 0.05, held, vel=72)]
    answer = phrase("hammered_dulcimer", "F#5 A5 D6 B5 G5 E5", at=BAR, vel=104, seed=41)
    answer += [n("hammered_dulcimer", "A5", MOTIF, 0.6, vel=110),
               n("hammered_dulcimer", "A4", MOTIF + 0.006, 0.6, vel=88)]
    bass = [n("harp", "D3", 0.0, 0.6, vel=60), n("harp", "B2", BAR, 0.6, vel=56),
            n("harp", "E3", BAR + DQ, 0.6, vel=54)]
    return clip(calls, end="A", mood="party",
                layers=[(render(answer), 0.0, 0.0), (_damped(bass, MOTIF), 0.0, -9.0)])


def _azure_emblem() -> np.ndarray:
    # the blue emblem glints: harp and glockenspiel climb a D triad, then the lydian E major
    # one (its G sharp the cool colour), and settle on A, open
    harp = phrase("harp", "D5 F#5 A5:4 E5 G#5 B5:4", vel=72, legato=1.6, seed=51)
    harp += [n("harp", "D3", 0.0, 0.7, vel=54), n("harp", "E3", BAR, 0.7, vel=52)]
    glock = phrase("glockenspiel", "D6 F#6 A6:4 E6 G#6 B6:4", vel=70, legato=1.0, seed=52)
    glock += [n("glockenspiel", p, t, 0.2, vel=v) for p, t, v in
              (("A6", 2 * EIGHTH + 0.165, 40), ("B6", BAR + 2 * EIGHTH + 0.165, 40), ("A6", MOTIF, 66),
               ("A6", MOTIF + 0.165, 36))]
    return clip(harp, end="A", mood="magic", instrument="harp", held_vel=66,
                layers=[(render(glock), 0.0, -3.0)])


# ============================================================================= the Evergreen Mother's lullaby
_LULLABY_BEATS = (0.0, BAR, MOTIF)          # a slow 6/8: one dotted quarter every 0.66 s


def _mother_corrupt() -> np.ndarray:
    # the lullaby gone dark: viol over a low flute a third under, a slow heartbeat; it falls
    # B flat to A and stops there, waiting
    viol = phrase("viol", "D5:2 C5:1 A4:2 Bb4:1", vel=72, slow=True, legato=1.02, accent=6, seed=61,
                  swell=(84, 100))
    flute = phrase("wooden_flute", "Bb4:2 A4:1 F4:2 G4:1", vel=64, slow=True, legato=1.0, accent=4, seed=62)
    flute += [n("wooden_flute", "E4", MOTIF + 0.01, 0.6, vel=64, swell=(110, 40))]
    return clip(viol, end="A4", mood="enemy", instrument="viol", slow=True, held_vel=70,
                layers=[(render(flute), 0.0, -5.0), (_heartbeat(_LULLABY_BEATS, 86), 0.0, -10.0)])


def _mother_restored() -> np.ndarray:
    # the same lullaby healed: a wooden flute over a rocking harp in D major, rising
    # B, C sharp to a held D
    flute = phrase("wooden_flute", "D5:2 C#5:1 A4:2 B4:0.5 C#5:0.5", vel=72, slow=True, legato=1.02,
                   accent=6, seed=71)
    harp = phrase("harp", "D3 A3 F#4 G2 D3 B3", vel=64, slow=True, legato=2.5, accent=6, seed=72)
    return clip(flute, end="D", mood="party", instrument="wooden_flute", slow=True, held_vel=78,
                layers=[(_damped(harp, MOTIF, 0.45), 0.0, -7.0)])


# ============================================================================= the Jester: the Whistle jig
_JIG = "A5 B5 A5 B5/F#5 D5 F#5 A5 B5 D6 E6 D6 B5 A5 B5"     # combat.py's tune with one more bar
_JIG_LOW = "A4 B4 A4 F#4 D4 F#4 A4 B4 D5 E5 D5 B4 A4 B4"   # the same an octave down, no cut (the fiddle)
_JIG_END = 14 * EIGHTH                                        # the held note: bar 3, third eighth
_JIG_BEATS = [0.0, DQ, BAR, BAR + DQ, MOTIF]


def _jig_tune(tune: str = _JIG, inst: str = "recorder", vel: int = 92, at_: float = 0.0, step: float = EIGHTH,
              seed: int = 81, **kw) -> List[INote]:
    """The Whistle jig's line on ``inst`` as combat.py plays it: 12 more velocity on the
    beats, a cut (``B5/F#5``: a 20 ms flick of the B above) into the fourth note."""
    out: List[INote] = []
    rng = np.random.default_rng(seed)
    p = prog(inst)
    for i, tok in enumerate(tune.split()):
        t0 = at_ + i * step + (float(rng.uniform(-0.003, 0.003)) if i else 0.0)
        v = vel + (12 if i % 3 == 0 else 0)
        if "/" in tok:
            g, main = tok.split("/")
            out += [INote(p, g, max(0.0, t0), 0.02, vel=v - 8, **kw),
                    INote(p, main, t0 + 0.02, step - 0.02, vel=v, **kw)]
        else:
            out.append(INote(p, tok, max(0.0, t0), step * 0.98, vel=v, **kw))
    return out


def _jig_drums(beats: Sequence[float], end: float) -> List[Tuple[np.ndarray, float, float]]:
    """The jig's tabor on the beats and the held note, the tambourine on the beats, at the
    owner's Whistle jig's balance (combat.py: both about 10 dB under the recorder)."""
    tabor = _hits("tabor", [(t, 64) for t in beats] + [(end, 64)])
    tamb = _hits("tambourine", [(t, 70 if i % 2 == 0 else 55) for i, t in enumerate(beats)])
    return [(tabor, 0.0, -9.7), (tamb, 0.0, -10.0)]


def _whistle_jig(cad_note: str = "D6", cut: str = "E6", layers_extra=(), pickup_kind="harp", length: float = 2.36,
                 tail=True, chord=None) -> np.ndarray:
    tune = _jig_tune()
    tune += [n("recorder", cut, _JIG_END, 0.025, vel=100),
             n("recorder", cad_note, _JIG_END + 0.025, 0.52, vel=106, swell=(118, 70))]
    layers = _jig_drums(_JIG_BEATS, _JIG_END)
    # the cap bells' shake about 3 dB under the recorder, as in combat.py's jig
    layers.append(_bell_layer(_cap_bells([(0.0, 0.8)], 612, per=4), _JIG_END, -2.1))
    layers += list(layers_extra)
    return clip(tune, end=cad_note, mood="party", cadence_at=_JIG_END, layers=layers, pickup=pickup_kind,
                length=length, max_s=2.6, tail=tail, chord=chord)


def _jig() -> np.ndarray:
    # the default Jester clip, the same for all four rows
    return _whistle_jig()


def _jig_tease() -> np.ndarray:
    # the claim: the jig stops on a teasing high E instead of home, the cap bells shaking
    shakes = _cap_bells([(0.0, 0.9), (0.12, 0.7), (0.24, 0.85), (0.4, 0.6)], 655, per=4)
    return _whistle_jig(cad_note="E6", cut="F#6", chord=("A2", "E3", "B3"), tail=False,
                        layers_extra=[_bell_layer(shakes, _JIG_END + 0.11, -6.7)])


def _jig_riffle() -> np.ndarray:
    # the new hand: the jig over the game's own card riffle and its bridge
    riffle = card_sound("shuffle", keep=1.0, fade=0.08)
    return _whistle_jig(layers_extra=[(riffle, -0.09, -10.0)])


def _jig_double() -> np.ndarray:
    # the attack: a fiddle chops the beat for a bar, then the jig's recorder and the fiddle
    # race the jig at double speed to the held high D
    s = SIXTEENTH
    start = BAR                                      # the tune enters on the second bar
    end = start + 14 * s                             # its held D, where the jig holds it
    # the jig's own recorder (see _TIN)
    whistle = _jig_tune(inst="recorder", vel=84, at_=start, step=s, seed=91)
    whistle += [n("recorder", "E6", end, 0.02, vel=96),
                n("recorder", "D6", end + 0.02, 0.46, vel=104, swell=(118, 60))]
    fiddle: List[INote] = []
    for i, t in enumerate((0.0, 3 * s, 6 * s, 9 * s)):
        v = 100 if i % 2 == 0 else 86
        fiddle += [n("fiddle", "D4", t, 0.1, vel=v), n("fiddle", "A4", t + 0.004, 0.1, vel=v - 6)]
    fiddle += _jig_tune(_JIG_LOW, inst="fiddle", vel=92, at_=start, step=s, seed=92)
    fiddle += [n("fiddle", "D5", end, 0.5, vel=100, swell=(118, 56)),
               n("fiddle", "D4", end + 0.006, 0.5, vel=84, swell=(110, 50))]
    beats = [i * 3 * s for i in range(9)]
    tabor = _hits("tabor", [(t, 70 if i % 2 == 0 else 54) for i, t in enumerate(beats)] + [(end, 70)])
    tamb = _hits("tambourine", [(t, 62) for t in beats[::2]])
    return clip(whistle, end="D6", mood="party", cadence_at=end, length=2.36, max_s=2.6,
                layers=[(render(fiddle), 0.0, -3.0), (tabor, 0.0, -11.0), (tamb, 0.0, -13.0),
                        _bell_layer(_cap_bells([(0.0, 0.8)], 613, per=4), end, -3.0)])


# ============================================================================= the candidates
_JIG_NOTE = ("The Whistle jig one bar longer: a wooden whistle's quick jig over a little drum and a tambourine, "
             "ending on a held high D with the cap bells.")

CANDIDATES = [
    info("turn", "lute_bell", "Lute and bell",
         "A lute plucks A, then D, with a soft hand bell on the D: your move.", _turn_lute_bell, ["quiet", "lute"]),
    info("turn", "lute_strums", "Lute strums",
         "Two soft low lute strums a bar apart, A then D, a hand bell glowing on each.", _turn_strums,
         ["quiet", "lute"]),
    info("yield", "viol_sigh", "Viol sigh",
         "A viol sighs two quiet falling notes, A to F sharp, over one soft lute D.", _yield_viol,
         ["quiet", "strings"]),
    info("corrupted", "cracked_bell", "Cracked bell",
         "A low viol drone and a cracked bell; B flat falls to A as a card slides away, then sinks to D.",
         _corrupted, ["dark", "strings"]),
    info("restored", "light_returns", "Light returns",
         "A wooden flute lifts B flat to B, C sharp and a held D over a rising harp.", _restored, ["warm", "flute"]),
    info("declared", "strum_slap", "Strum and slap",
         "Two quick lute plucks, then a strummed D chord with a tabor beat and a card slapped down.", _declared,
         ["lute", "drum"]),
    info("kinfolk_flute", "flutes_thirds", "Flutes in thirds",
         "Two wooden flutes in thirds play a little family tune over a lute, stopping open on A.", _kinfolk_flute,
         ["flute", "question"]),
    info("scarlet_whistle", "whistle_call", "Whistle call",
         "Two quick tin-whistle calls, A up to high D, answered by a hammered dulcimer that stops on A.",
         _scarlet_whistle, ["whistle", "question"]),
    info("azure_emblem", "glinting_triad", "Glinting triad",
         "Harp and glockenspiel climb a bright triad, then a cool lydian one, and ring on A.", _azure_emblem,
         ["bells", "magic", "question"]),
    info("mother_corrupt", "dark_lullaby", "Dark lullaby",
         "A slow viol lullaby over a low flute and a heartbeat drum in D minor, stopping on A.", _mother_corrupt,
         ["dark", "slow", "question"]),
    info("mother_restored", "healed_lullaby", "Healed lullaby",
         "The same lullaby on a wooden flute over a rocking harp in D major, rising to a held D.", _mother_restored,
         ["warm", "slow"]),
    # the Jester: the extended Whistle jig is every row's default
    info("jester", "whistle_jig", "Whistle jig", _JIG_NOTE, _jig, ["tavern", "jig"]),
    info("jester_claim", "whistle_jig", "Whistle jig", _JIG_NOTE, _jig, ["tavern", "jig"]),
    info("jester_claim", "teasing_e", "Teasing E",
         "The Whistle jig stops short on a teasing high E while the cap bells shake.", _jig_tease,
         ["tavern", "jig", "funny"]),
    info("solo_jester_refresh", "whistle_jig", "Whistle jig", _JIG_NOTE, _jig, ["tavern", "jig"]),
    info("solo_jester_refresh", "jig_riffle", "Jig and riffle",
         "The Whistle jig played over the game's card riffle, as the new hand is dealt.", _jig_riffle,
         ["tavern", "jig", "card"]),
    info("solo_jester_attack", "whistle_jig", "Whistle jig", _JIG_NOTE, _jig, ["tavern", "jig"]),
    info("solo_jester_attack", "double_time", "Double time",
         "A fiddle chops the beat, then recorder and fiddle race the jig at double speed to a high D.",
         _jig_double, ["tavern", "jig", "fast"]),
]
