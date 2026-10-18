"""The info pop-ups' shared grammar (docs/INFO_POPUPS.md, "Melody plan"): one family of
short acoustic clips in D, every one built the same way, so a change here (the room, the
pickup, the cadence) re-renders the whole set alike.

Not a family (the leading "_"): the composers' families import it.

    from _info_common import *

    def _turn():
        motif = phrase("lute", "A4:3 D5:3", vel=78) + [n("hand_bell", "D6", DQ, 0.5, vel=46)]
        return clip(motif, end="D", mood="major", cadence_at=BAR)

    CANDIDATES = [info("turn", "lute_bell", "Lute and bell", "Lute A then D, a soft bell.", _turn, ["quiet"])]

THE SHAPE of every clip (``clip``), on one timeline:
  1. the pickup (``pickup``): a soft card flick and one plucked harp D5, the info-card
     signature; the motif's downbeat falls one eighth later (``PICKUP`` = 0.12 s). A card
     that stands for a card action bakes in the game's own card sound instead
     (``pickup="shuffle" | "draw" | "discard"``: the owner's pick, ``card_sound``), and the
     downbeat falls after the sound's main gesture (0.11 to 0.33 s).
  2. the motif: the composer's notes (sf.Note, or ``n`` / ``phrase`` / ``roll`` / ``trill``),
     times in seconds FROM THE MOTIF'S DOWNBEAT, normally two 6/8 bars (``MOTIF`` = 1.32 s;
     slow cards: one bar at half time, the same 1.32 s).
  3. the cadence at ``cadence_at`` (default ``MOTIF`` after the downbeat): the signature
     ``instrument`` holds the final note (D, or A for a card shown just before a decision
     box: a question), a soft rolled harp chord under it (major, minor or the open A-E
     fifth), then the shared tail: the harp plucks the pickup's note again (D5, or A4 for
     an open ending), the tavern room rings and the clip fades.
  Then the room and the master chain (``finish``): the Whistle jig's tavern reverb (room
  0.35, wet 0.16), high-pass 100 Hz, low-pass 7.5 kHz, mono, a natural fade; peaks glued
  so the build's limiter barely acts; trimmed exactly as build.py trims, and checked to be
  2.0 to 2.4 s (``clip`` raises otherwise, naming the length).

KEYS (all on D): ``MAJOR`` (party news), ``MIXO`` (folk colour), ``MINOR`` and ``DORIAN``
(enemies, banes), ``LYDIAN`` (magic); ``key(mood)`` for a mood name ("party", "folk",
"enemy", "bane", "magic" or a mode name). ``K(degree, octave)`` gives a MIDI number:
degree 1 is D in that octave (D4 = 62), 8 the D above, 0 the seventh below, "b3" / "#4"
with accidentals. ``midi("F#4")`` and ``name(66)`` convert names and numbers.

GRID: the Whistle jig's 6/8: ``EIGHTH`` 0.11 s, ``QUARTER`` 0.22, ``DQ`` (dotted quarter)
0.33, ``BAR`` 0.66; ``at(bar, eighth, slow)`` is a time from the downbeat (slow: half time).

LEVELS: the motif's notes keep the bank's own balance (velocity); the pickup, the bed,
the tail and any foreign layer with a dB are set relative to the motif's ``level`` (its
loudest moments: the 95th percentile of 50 ms blocks, so a sparse motif is not judged
quieter than it sounds), and the family balances alike whatever the signature
instrument. The build masters the finished clip to its event's loudness.

RENDER TIME: a clip takes about 2 to 3 s (a MuseScore-bank render costs ~1.2 s to load
the bank; renders are cached per process, so the shared pickup, bed and tail are made
once per build). Prefer Fluid for parts where the banks sound alike.

Everything is deterministic (seeded jitter, cached renders), so a rebuild is identical.
"""
from __future__ import annotations

import dataclasses
import functools
import importlib
import json
import math
import os
import re
import sys
import warnings
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))           # tools/audio/families
AUDIO = os.path.dirname(HERE)                                # tools/audio
REPO = os.path.dirname(os.path.dirname(AUDIO))
for _p in (AUDIO, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sf  # noqa: E402
import synth as A  # noqa: E402
from catalog import EVENT_BY_ID, Candidate  # noqa: E402
from sf import DRUM, DRUMS, GM, KITS, Note  # noqa: E402

__all__ = [
    # constants
    "SR", "EIGHTH", "SIXTEENTH", "QUARTER", "DQ", "BAR", "MOTIF", "PICKUP", "ROOM", "WET", "DAMPING", "HP", "LP",
    "MIN_S", "MAX_S", "BEFORE_BOX", "GM", "DRUM", "DRUMS", "KITS", "Note", "A", "sf",
    # keys and the grid
    "MODES", "MOODS", "Key", "key", "MAJOR", "MIXO", "MINOR", "DORIAN", "LYDIAN", "midi", "name", "at", "beats",
    # instruments and notes
    "INSTR", "prog", "BANK_FOR", "INote", "n", "drum", "phrase", "roll", "trill",
    # audio pieces
    "render", "perc", "hit", "choke", "lute_body", "double", "loudness", "to_db", "level", "to_level", "fit", "glue",
    "card_sound", "card_source", "pickup", "cadence_notes", "bed_notes", "room", "finish", "clip", "info",
    "default_end",
]

SR = A.SR

# ============================================================================= the grid
EIGHTH = 0.11                 # the Whistle jig's eighth note
SIXTEENTH = EIGHTH / 2
QUARTER = 2 * EIGHTH
DQ = 3 * EIGHTH               # a dotted quarter: one beat of 6/8
BAR = 6 * EIGHTH              # 0.66 s
MOTIF = 2 * BAR               # the two-bar motif, 1.32 s (slow cards: one bar at half time)
PICKUP = 0.12                 # the harp pickup: the motif's downbeat falls here

# ============================================================================= room and master
ROOM, WET, DAMPING = 0.35, 0.16, 0.5      # the Whistle jig's tavern
HP, LP = 100.0, 7500.0
MIN_S, MAX_S = 2.0, 2.4                   # every clip (the Jester rows' cap is 2.6)
_SAFE = (2.10, 2.36)                      # what clip aims for, inside the limits


def at(bar: float, eighth: float = 0.0, slow: bool = False) -> float:
    """Seconds from the motif's downbeat to ``bar`` (0-based) and ``eighth`` (0..5) of it;
    ``slow``: half time (an eighth lasts 0.22 s)."""
    return (bar * 6 + eighth) * EIGHTH * (2 if slow else 1)


def beats(eighths: float, slow: bool = False) -> float:
    """The length of ``eighths`` eighth notes in seconds (``slow``: half time)."""
    return eighths * EIGHTH * (2 if slow else 1)


# ============================================================================= keys
MODES: Dict[str, Tuple[int, ...]] = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
}
MOODS: Dict[str, str] = {"party": "major", "folk": "mixolydian", "enemy": "minor", "bane": "dorian",
                         "magic": "lydian"}
_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]


def midi(p: Union[str, int]) -> int:
    """A pitch as a MIDI number: "F#4" -> 66, "Bb3" -> 58; a number is returned as is."""
    if isinstance(p, (int, np.integer)):
        return int(p)
    return A.midi(p)


def name(m: Union[str, int]) -> str:
    """A MIDI number as a note name (62 -> "D4"); a name is returned as is."""
    if isinstance(m, str):
        return m
    return "%s%d" % (_NAMES[int(m) % 12], int(m) // 12 - 1)


class Key(object):
    """A mode on D. ``K(degree, octave=4)`` -> MIDI: degree 1 is D in ``octave`` (D4 = 62),
    2..7 the steps above it, 8 the D an octave up, 0 the seventh below, -1 the sixth below;
    a string may carry accidentals ("b3", "#4", "b7"). ``K.notes("1 3 5 8", 4)`` a list,
    ``K.chord(1, 3)`` a triad on a degree, ``K.scale(4)`` the seven notes from D."""

    def __init__(self, mode: str = "major", tonic: str = "D") -> None:
        self.mode = MOODS.get(mode, mode)
        self.steps = MODES[self.mode]
        self.tonic = tonic

    def root(self, octave: int = 4) -> int:
        return midi("%s%d" % (self.tonic, octave))

    def __call__(self, degree: Union[int, str], octave: int = 4) -> int:
        acc = 0
        if isinstance(degree, str):
            s = degree.strip()
            while s and s[0] in "#b":
                acc += 1 if s[0] == "#" else -1
                s = s[1:]
            degree = int(s)
        octs, step = divmod(int(degree) - 1, 7)
        return self.root(octave) + 12 * octs + self.steps[step] + acc

    def notes(self, degrees: Union[str, Sequence], octave: int = 4) -> List[int]:
        items = degrees.split() if isinstance(degrees, str) else list(degrees)
        return [self(d, octave) for d in items]

    def chord(self, degree: int = 1, octave: int = 3, size: int = 3) -> List[int]:
        return [self(degree + 2 * k, octave) for k in range(size)]

    def scale(self, octave: int = 4) -> List[int]:
        return [self(d, octave) for d in range(1, 8)]

    @property
    def minor(self) -> bool:
        return self.steps[2] == 3

    def __repr__(self) -> str:
        return "Key(%s %s)" % (self.tonic, self.mode)


def key(mood: str = "major") -> Key:
    """The key of a mood: "party" (D major), "folk" (D mixolydian), "enemy" (D minor),
    "bane" (D dorian), "magic" (D lydian), or a mode name."""
    return Key(mood)


MAJOR, MIXO, MINOR, DORIAN, LYDIAN = (Key(m) for m in ("major", "mixolydian", "minor", "dorian", "lydian"))


# ============================================================================= instruments
# The plan's band by its own names (the General MIDI stand-ins), on top of sf.GM's names.
INSTR: Dict[str, int] = dict(GM)
INSTR.update({
    "lute": GM["nylon_guitar"],          # a nylon-strung guitar, given a lute's body (render)
    "viol": GM["viola"], "treble_viol": GM["viola"], "bass_viol": GM["cello"],
    # a tin whistle is the piccolo's soft bottom octave (a fife): General MIDI's "whistle"
    # is a human whistle whose samples warble (two detuned layers beating 10-40 Hz, ~20 dB
    # deep), a synthetic flutter on any held note (fine for a bird's short chirps)
    "tin_whistle": GM["piccolo"], "wooden_flute": GM["flute"], "pipe": GM["recorder"],
    "hammered_dulcimer": GM["dulcimer"], "hand_bell": GM["tubular_bells"],    # play it high (D6)
    "temple_bell": GM["tubular_bells"], "humming": GM["voice_oohs"], "voices": GM["choir"],
    "low_strings": GM["strings"], "horn": GM["french_horn"], "cap_bells": GM["tinkle_bell"],
})

# The bank each instrument sounds best from (the jingles' and the Whistle jig's choices);
# the rest come from Fluid (faster: the MuseScore bank takes ~1.2 s to load per render).
# The Fluid choir measures 15-30 cents flat (D3 -30, A3 -27, D4 -24); MuseScore's is in tune.
BANK_FOR: Dict[int, str] = {GM[k]: "musescore" for k in (
    "harp", "nylon_guitar", "recorder", "french_horn", "violin", "viola", "cello", "tinkle_bell", "choir")}

# Programs that hold a note (blown, bowed, sung): a held cadence note on one of them
# fades under the bow or breath (an expression swell) instead of just stopping.
SUSTAINED = {GM[k] for k in (
    "recorder", "flute", "whistle", "pan_flute", "ocarina", "piccolo", "oboe", "english_horn", "bassoon",
    "clarinet", "french_horn", "trumpet", "trombone", "tuba", "brass", "violin", "viola", "cello", "contrabass",
    "fiddle", "strings", "slow_strings", "tremolo_strings", "choir", "voice_oohs", "accordion", "reed_organ",
    "church_organ", "bagpipe", "shanai", "shakuhachi", "bottle")}


def prog(inst: Union[str, int]) -> int:
    """A General MIDI program from a name ("lute", "harp", "viol") or a number."""
    if isinstance(inst, (int, np.integer)):
        return int(inst)
    try:
        return INSTR[inst]
    except KeyError:
        raise KeyError("unknown instrument %r (see INSTR / sf.GM)" % inst)


@dataclasses.dataclass
class INote(Note):
    """An sf.Note that may name its bank ("fluid" / "musescore"; None: BANK_FOR)."""
    bank: Optional[str] = None


def n(inst: Union[str, int], pitch, start: float, dur: float, vel: int = 90, bank: Optional[str] = None,
      **kw) -> INote:
    """One note: ``n("harp", "D5", 0.0, 0.4, vel=80)``; ``kw``: pan, bend, swell (sf.Note)."""
    return INote(prog(inst), pitch, float(start), float(dur), vel=int(vel), bank=bank, **kw)


def drum(key_: Union[str, int], start: float, vel: int = 90, kit: str = "standard", dur: float = 0.15,
         bank: Optional[str] = None) -> INote:
    """A General MIDI percussion hit as a note (``key_``: a sf.DRUMS name); ``kit`` from sf.KITS.
    For a shaped tavern drum (tabor, bodhran, war drum) use ``perc`` as a layer instead."""
    return INote(DRUM, key_, float(start), dur, vel=int(vel), kit=kit, bank=bank)


_TOKEN = re.compile(r"^(?P<body>[^:@]+)(?::(?P<len>[0-9.]+))?(?:@(?P<vel>\d+))?$")
_NOTE_NAME = re.compile(r"^[A-G][#b]*-?\d+$")
_DEGREE = re.compile(r"^[#b]*-?\d+$")


def _pitch(tok: Union[str, int], k: Optional[Key], octave: int) -> int:
    if isinstance(tok, (int, np.integer)):
        return int(tok)
    t = tok.strip()
    if _NOTE_NAME.match(t):
        return midi(t)
    if _DEGREE.match(t):
        return (k or MAJOR)(t, octave)
    raise ValueError("not a pitch: %r (a name like F#4, or a degree like 5 / b3 with key=)" % tok)


def phrase(inst: Union[str, int], tune: Union[str, Sequence], at: float = 0.0, vel: int = 90, slow: bool = False,
           key: Optional[Key] = None, octave: int = 4, legato: float = 0.95, accent: int = 8,
           jitter: float = 0.004, seed: int = 0, bank: Optional[str] = None, grace: float = 0.025,
           **kw) -> List[INote]:
    """A line of notes on the 6/8 grid, one after the other, from ``at`` seconds (motif time).

    ``tune``: space-separated tokens ``pitch[:eighths][@velocity]``:
      "A5 B5 A5 F#5:3"   names; the length in eighths (default 1; "0.5" a sixteenth)
      "5 6 5 3:3"        scale degrees of ``key`` in ``octave`` (8 = the octave up, "b3")
      "r:2" or "-:2"     a rest
      "D4+F#4+A4:3"      a chord (all at once; ``roll`` spreads one)
      "E6/D6:3"          a grace note (a cut, ``grace`` seconds) into the main note
      "D5:3@110"         this note's own velocity
    or a list of (pitch, eighths) / (pitch, eighths, velocity), pitch None for a rest.
    Notes on the beats (eighths 0 and 3 of a bar) get ``accent`` more velocity; every note
    but the first is nudged by up to ``jitter`` s and its velocity by a few percent (seeded),
    as a player would. ``kw`` goes to every note (pan, swell, bend)."""
    rng = np.random.default_rng(seed)
    step = EIGHTH * (2 if slow else 1)
    items: List[Tuple[object, float, Optional[int]]] = []
    if isinstance(tune, str):
        for tok in tune.split():
            m = _TOKEN.match(tok)
            if not m:
                raise ValueError("bad token %r" % tok)
            items.append((m.group("body"), float(m.group("len") or 1), int(m.group("vel")) if m.group("vel") else None))
    else:
        for it in tune:
            items.append((it[0], float(it[1]), int(it[2]) if len(it) > 2 and it[2] is not None else None))
    out: List[INote] = []
    pos = 0.0
    p = prog(inst)
    for i, (body, length, own_vel) in enumerate(items):
        if body is None or body in ("r", "-"):
            pos += length
            continue
        t0 = at + pos * step + (0.0 if not out else float(rng.uniform(-jitter, jitter)))
        strong = abs((pos % 3)) < 1e-6
        v = own_vel if own_vel is not None else vel + (accent if strong else 0)
        v = int(np.clip(round(v * rng.uniform(0.97, 1.03)), 1, 127))
        dur = max(0.03, length * step * legato)
        if isinstance(body, str) and "/" in body:
            g, main = body.split("/", 1)
            out.append(INote(p, _pitch(g, key, octave), max(0.0, t0), grace, vel=max(1, v - 8), bank=bank, **kw))
            out.append(INote(p, _pitch(main, key, octave), max(0.0, t0 + grace), max(0.03, dur - grace), vel=v,
                             bank=bank, **kw))
        else:
            for part in (body.split("+") if isinstance(body, str) else [body]):
                out.append(INote(p, _pitch(part, key, octave), max(0.0, t0), dur, vel=v, bank=bank, **kw))
        pos += length
    return out


def roll(inst: Union[str, int], pitches: Sequence, start: float, dur: float, vel: int = 80, spread: float = 0.018,
         down: bool = False, bank: Optional[str] = None, key: Optional[Key] = None, octave: int = 4,
         **kw) -> List[INote]:
    """A rolled chord or a strum: ``pitches`` (names, MIDI or degrees of ``key``) from the
    lowest up (``down``: from the top), ``spread`` seconds apart, each a little softer."""
    ps = [_pitch(x, key, octave) for x in pitches]
    ps = sorted(ps, reverse=down)
    return [INote(prog(inst), q, start + i * spread, max(0.03, dur - i * spread), vel=max(1, int(vel - 3 * i)),
                  bank=bank, **kw) for i, q in enumerate(ps)]


def trill(inst: Union[str, int], main, upper, start: float, dur: float, vel: int = 80, rate: float = 0.05,
          bank: Optional[str] = None, end_on_main: bool = True, **kw) -> List[INote]:
    """A trill (main, upper, main, ...) every ``rate`` seconds for ``dur`` seconds."""
    a, b = midi(main), midi(upper)
    k = max(2, int(round(dur / rate)))
    if end_on_main and k % 2 == 0:
        k += 1
    return [INote(prog(inst), a if i % 2 == 0 else b, start + i * rate, rate * 0.95,
                  vel=max(1, int(vel - (6 if i % 2 else 0))), bank=bank, **kw) for i in range(k)]


# ============================================================================= rendering
RING = 1.6                     # seconds rendered past the last note-off (the bank's release)


def _fit(x: np.ndarray, d: float) -> np.ndarray:
    k = A.n_of(d)
    return x[:k].copy() if len(x) >= k else np.concatenate([x, np.zeros(k - len(x))])


fit = _fit


def _base(nt: Note) -> tuple:
    return (nt.program, nt.key(), round(nt.start, 5), round(nt.dur, 5), int(nt.vel), round(nt.pan, 3),
            nt.reverb, nt.chorus, nt.bend, nt.swell, nt.kit)


@functools.lru_cache(maxsize=512)
def _sf_cached(spec: tuple, seconds: float, bank: str) -> np.ndarray:
    return sf.render([Note(*s) for s in spec], seconds, bank=bank)


def _sf_safe(notes: List[Note], seconds: float, bank: str) -> np.ndarray:
    """One FluidSynth render; split in two (by time) when the notes need more channels than
    a render has (many bent or swelling notes, many instruments)."""
    spec = tuple(_base(x) for x in notes)
    try:
        return _sf_cached(spec, round(seconds, 4), bank).copy()
    except ValueError:
        if len(notes) < 2:
            raise
        ns = sorted(notes, key=lambda x: x.start)
        h = len(ns) // 2
        return _sf_safe(ns[:h], seconds, bank) + _sf_safe(ns[h:], seconds, bank)


def lute_body(x: np.ndarray) -> np.ndarray:
    """The guitar played as a lute (the jingles' lute): less boom, a wooden bowl near
    280 Hz, a gentle nasal presence, the top softened like gut strings."""
    y = A.highpass(x, 90, 2)
    y = A.peak_eq(y, 280, 3.0, 1.2)
    y = A.peak_eq(y, 1100, 1.5, 1.4)
    return A.lowpass(y, 5500, 2)


def double(x: np.ndarray, cents: float = 6.0, delay: float = 0.012, gain: float = 0.7) -> np.ndarray:
    """A second player: the same recording a few cents apart and a few ms late (a lute's
    paired course, a section of two). Keeps the level."""
    r = 2 ** (cents / 1200.0)
    m = int(len(x) / r)
    y = np.interp(np.arange(m) * r, np.arange(len(x)), x)
    out = x.copy()
    d = A.n_of(delay)
    k = min(len(out) - d, len(y))
    if k > 0:
        out[d:d + k] += gain * y[:k]
    return out / math.sqrt(1.0 + gain * gain)


def _glock_fx(x: np.ndarray) -> np.ndarray:
    # most of a glockenspiel's energy here is one piercing partial at 6-7.5 kHz
    return A.lowpass(x, 4500, 4)


# per-program treatment applied after the bank renders it
FX_FOR = {GM["nylon_guitar"]: lambda x: lute_body(double(x)), GM["glockenspiel"]: _glock_fx}


def _bank_of(nt: Note, default: Optional[str]) -> str:
    return getattr(nt, "bank", None) or default or BANK_FOR.get(nt.program, "fluid")


def render(notes: Iterable[Note], seconds: Optional[float] = None, bank: Optional[str] = None) -> np.ndarray:
    """Render notes (times from 0) to mono audio at the banks' own level: each note from its
    bank (INote.bank, else ``bank``, else BANK_FOR, else Fluid), the lute (nylon guitar)
    given a lute's body and paired course, the glockenspiel's top softened. Cached; drum
    kits and channel limits are handled. ``seconds``: default the last note-off + 1.6 s."""
    notes = list(notes)
    if not notes:
        return np.zeros(A.n_of(seconds or 0.01))
    if any(x.start < 0 for x in notes):
        raise ValueError("a note starts before 0: %r" % min(notes, key=lambda x: x.start))
    seconds = seconds or max(x.start + x.dur for x in notes) + RING
    # one render per bank for its plain notes plus its first drum kit (a render takes one
    # kit), then one per further kit, and one per instrument that gets its own treatment
    plain: Dict[str, List[Note]] = {}
    kits: Dict[str, Dict[tuple, List[Note]]] = {}
    fx: Dict[tuple, List[Note]] = {}
    for x in notes:
        b = _bank_of(x, bank)
        if x.program == DRUM:
            kits.setdefault(b, {}).setdefault((x.kit, round(x.pan, 2), x.reverb, x.chorus), []).append(x)
        elif x.program in FX_FOR:
            fx.setdefault((b, x.program), []).append(x)
        else:
            plain.setdefault(b, []).append(x)
    jobs: List[Tuple[str, List[Note], Optional[int]]] = []
    for b in sorted(set(plain) | set(kits)):
        drum_groups = list(kits.get(b, {}).values())
        jobs.append((b, plain.get(b, []) + (drum_groups[0] if drum_groups else []), None))
        jobs += [(b, g, None) for g in drum_groups[1:]]
    jobs += [(b, g, p) for (b, p), g in fx.items()]
    out = np.zeros(A.n_of(seconds))
    for b, g, p in jobs:
        if not g:
            continue
        y = _fit(_sf_safe(g, seconds, b), seconds)
        out += FX_FOR[p](y) if p is not None else y
    return out


# percussion of the tavern band, shaped as the families shape them: name -> [(key, kit,
# bank, gain, choke at, choke fall)]
_PERC = {
    "tabor": [("snare", "orchestra", "musescore", 1.0, 0.04, 0.2)],
    "bodhran": [("low_floor_tom", "brush", "fluid", 1.0, 0.1, 0.35),
                ("low_conga", "standard", "fluid", 0.8, 0.06, 0.25)],
    "frame_drum": [("low_floor_tom", "brush", "fluid", 1.0, 0.08, 0.3),
                   ("mute_conga", "standard", "fluid", 0.5, 0.04, 0.15)],
    "war_drum": [("bass_drum", "orchestra", "fluid", 1.0, 0.12, 0.45),
                 ("low_conga", "standard", "fluid", 0.6, 0.05, 0.2)],
    "bass_drum": [("bass_drum", "orchestra", "fluid", 1.0, 0.2, 0.6)],
    "woodblock": [("low_woodblock", "standard", "fluid", 1.0, 0.03, 0.12)],
    "woodblock_hi": [("hi_woodblock", "standard", "fluid", 1.0, 0.03, 0.1)],
    "shaker": [("maracas", "standard", "fluid", 1.0, 0.08, 0.1)],
    "cabasa": [("cabasa", "standard", "fluid", 1.0, 0.08, 0.1)],
    "tambourine": [("tambourine", "standard", "fluid", 1.0, 0.25, 0.3)],
    "brush": [("snare", "brush", "fluid", 1.0, 0.08, 0.2)],
    "cymbal": [("crash", "orchestra", "fluid", 1.0, 0.6, 0.8)],
}


def choke(x: np.ndarray, at_: float, fall: float) -> np.ndarray:
    """Damp a ringing sound after ``at_`` seconds, falling 60 dB in ``fall`` (a hand on it)."""
    t = np.arange(len(x)) / SR
    return x * np.where(t < at_, 1.0, np.exp(-6.9078 * np.clip(t - at_, 0, None) / fall))


def _cut(x: np.ndarray, floor_db: float = -50.0, pre: float = 0.0004) -> np.ndarray:
    i = max(0, sf.onset(x, floor_db) - A.n_of(pre))
    y = x[i:].copy()
    k = A.n_of(pre) or 1
    y[:k] *= np.linspace(0, 1, k)
    return y


def hit(key_: Union[str, int], vel: int = 100, kit: str = "standard", bank: str = "fluid",
        seconds: float = 1.5) -> np.ndarray:
    """One General MIDI percussion hit (a sf.DRUMS name), cut at its onset (it sounds at once)."""
    return _cut(_sf_safe([Note(DRUM, key_, 0.0, 0.2, vel=int(vel), kit=kit)], seconds, bank))


@functools.lru_cache(maxsize=128)
def _perc_cached(name_: str, vel: int) -> np.ndarray:
    parts = _PERC[name_]
    out = np.zeros(A.n_of(1.6))
    for key_, kit, bank, gain, c_at, c_fall in parts:
        y = choke(hit(key_, vel, kit, bank, 1.6), c_at, c_fall)
        out[:min(len(out), len(y))] += gain * y[:len(out)]
    if name_ == "tambourine":
        out = A.lowpass(out, 6500, 4)          # its sizzle above the jingles' ring taken down
    return A.trim(out, -60.0, 0.01)


def perc(name_: str, vel: int = 100) -> np.ndarray:
    """A tavern percussion stroke as audio, cut at its onset, at the bank's level (so it
    sits with the notes as rendered; use it as a layer: ``(perc("tabor", 80), t)``).
    Names: tabor, bodhran, frame_drum, war_drum, bass_drum, woodblock, woodblock_hi,
    shaker, cabasa, tambourine, brush, cymbal."""
    if name_ not in _PERC:
        raise KeyError("unknown percussion %r: %s" % (name_, ", ".join(sorted(_PERC))))
    return _perc_cached(name_, int(vel)).copy()


# ============================================================================= levels
def loudness(x: np.ndarray) -> float:
    """The build's loudness measure (gated RMS dB, 50 ms blocks, 100 Hz high-pass)."""
    if not len(x) or not np.any(x):
        return -120.0
    return A._rms_db(x)


def to_db(x: np.ndarray, db: float) -> np.ndarray:
    """Scale ``x`` to a loudness of ``db`` (the build's measure)."""
    cur = loudness(x)
    return x if cur <= -119 else x * 10 ** ((db - cur) / 20.0)


def level(x: np.ndarray) -> float:
    """How loud a part's loudest moments are (dB): the 95th percentile of its 50 ms blocks'
    power after a 100 Hz high-pass. Unlike ``loudness`` it does not fall when a motif is
    sparse, so parts set relative to it balance alike in every clip."""
    if not len(x) or not np.any(x):
        return -120.0
    y = A.highpass(x, 100, 1)
    blk = A.n_of(0.05)
    k = max(1, len(y) // blk)
    y = _fit(y, k * blk / SR)
    p = np.mean(y.reshape(k, blk) ** 2, axis=1)
    return 10 * math.log10(float(np.percentile(p, 95)) + 1e-20)


def to_level(x: np.ndarray, db: float) -> np.ndarray:
    """Scale ``x`` so its ``level`` is ``db``."""
    cur = level(x)
    return x if cur <= -119 else x * 10 ** ((db - cur) / 20.0)


def glue(x: np.ndarray, crest_db: float = 14.0, release: float = 0.05) -> np.ndarray:
    """Hold the peaks to ``crest_db`` above the loudness with a smooth look-ahead gain
    (only the tallest transients move), so the build's limiter barely acts."""
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    thr = 10 ** ((loudness(x) + crest_db) / 20.0)
    if peak <= thr:
        return x
    return A.limit(x / thr, 0.0, lookahead=0.004, release=release) * thr


# ============================================================================= the game's card sounds
PICKS = os.path.join(REPO, "app", "sounds", "PICKS.json")
INSTALLED = os.path.join(REPO, "app", "sounds", "effects")
CARD_EVENTS = {"shuffle": "shuffle", "draw": "draw", "discard": "discard", "select": "card_select",
               "deselect": "card_deselect", "play": "play", "flick": "card_select"}


def _picks() -> Dict[str, str]:
    try:
        with open(PICKS) as f:
            return dict(json.load(f).get("effects") or {})
    except (OSError, ValueError):
        return {}


def _find_candidate(event: str, cid: str) -> Optional[Candidate]:
    """The family candidate ``event/cid``: only modules whose source names the id are imported."""
    pat = re.compile(r"""["']%s["']""" % re.escape(cid))
    for f in sorted(os.listdir(HERE)):
        if not f.endswith(".py") or f.startswith("_"):
            continue
        try:
            with open(os.path.join(HERE, f)) as fh:
                if not pat.search(fh.read()):
                    continue
            mod = importlib.import_module(f[:-3])
        except Exception:
            continue
        for c in getattr(mod, "CANDIDATES", []):
            if c.event == event and c.id == cid:
                return c
    return None


def _read_wav(path: str) -> np.ndarray:
    from scipy.io import wavfile
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", wavfile.WavFileWarning)
        sr, raw = wavfile.read(path)
    x = raw.astype(np.float64)
    if raw.dtype == np.int16:
        x = x / 32768.0
    elif raw.dtype == np.int32:
        x = x / 2147483648.0
    if x.ndim == 2:
        x = x.mean(axis=1)
    if sr != SR:
        x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x)
    return x


def _stand_in(event: str) -> np.ndarray:
    """A modelled card sound when neither the pick nor its file can be had."""
    if event == "shuffle":                           # a riffle: ever faster little paper ticks
        x = np.zeros(A.n_of(0.6))
        t = 0.0
        k = 0
        while t < 0.5:
            x = A.mix_at(x, 0.5 * A.paper(0.03, 1500, 7000, seed=900 + k), t)
            t += 0.024 - 0.012 * t
            k += 1
        return A.master(x, EVENT_BY_ID[event].loudness_db, -1.0, 0.02)
    if event == "draw":                              # a slide off the deck and a snap
        x = A.paper(0.16, 1200, 6000, seed=910) * A.adsr(0.16, 0.03, 0.05, 0.6, 0.06)
        x = A.mix_at(x, 0.6 * A.tick(2400, 0.04, seed=911), 0.17)
        return A.master(x, EVENT_BY_ID[event].loudness_db, -1.0, 0.02)
    if event == "discard":                           # three cards set down on a stack
        x = np.zeros(A.n_of(0.4))
        for i, tt in enumerate((0.0, 0.05, 0.1)):
            slap = A.paper(0.06, 400, 4000, seed=920 + i) * A.decay(0.06, 0.05)
            x = A.mix_at(x, slap, tt)
        return A.master(x, EVENT_BY_ID[event].loudness_db, -1.0, 0.02)
    x = A.tick(2600, 0.04, seed=930)                 # a flick
    return A.master(x, EVENT_BY_ID.get(event, EVENT_BY_ID["card_select"]).loudness_db, -1.0, 0.005)


@functools.lru_cache(maxsize=None)
def _card_cached(event: str) -> Tuple[np.ndarray, str]:
    ev = EVENT_BY_ID[event]
    cid = _picks().get(event)
    if cid:
        c = _find_candidate(event, cid)
        if c is not None:
            try:
                raw = c.render()
                return A.master(A.trim(raw, -70.0, 0.01), ev.loudness_db, -1.0, fade_out=0.008), "pick:" + cid
            except Exception:
                pass
        built = os.path.join(AUDIO, "out", event, cid + ".wav")
        if os.path.exists(built):
            return _read_wav(built), "built:" + cid
    path = os.path.join(INSTALLED, event + ".wav")
    if os.path.exists(path):
        return _read_wav(path), "installed"
    return _stand_in(event), "stand-in"


def card_sound(kind: str, keep: Optional[float] = None, fade: float = 0.06) -> np.ndarray:
    """The game's own card sound, as the game plays it (mastered to its event's loudness):
    "shuffle", "draw", "discard" (also "select" / "flick", "deselect", "play", or an event
    id). It is the owner's pick from app/sounds/PICKS.json rendered from its family's
    Candidate; failing that, the built file, then the installed app/sounds/effects file,
    then a modelled stand-in. ``keep``: cut after that many seconds with a ``fade``."""
    event = CARD_EVENTS.get(kind, kind)
    x = _card_cached(event)[0].copy()
    if keep is not None and len(x) > A.n_of(keep):
        x = x[:A.n_of(keep)]
        k = min(len(x), A.n_of(fade))
        x[-k:] *= 0.5 + 0.5 * np.cos(np.linspace(0, math.pi, k))
    return x


def card_source(kind: str) -> str:
    """Where ``card_sound(kind)`` came from ("pick:<id>", "built:<id>", "installed", "stand-in")."""
    return _card_cached(CARD_EVENTS.get(kind, kind))[1]


# ============================================================================= the pickup
PICKUP_NOTE = "D5"            # the info-card signature: one plucked harp D


def _env10(x: np.ndarray) -> np.ndarray:
    blk = A.n_of(0.01)
    k = len(x) // blk
    return np.sqrt(np.mean(x[:k * blk].reshape(k, blk) ** 2, axis=1)) if k else np.zeros(1)


def _gesture(x: np.ndarray) -> Tuple[float, float]:
    """A card sound's main gesture: (where the music may start, where to cut the sound).
    The music starts once 80% of the sound's energy is out, on the eighth grid, between
    one eighth and a dotted quarter; the sound is kept one eighth past that (a long
    sound, a riffle, stops at its first pause), so it hands over to the motif."""
    env = _env10(x)
    peak = float(env.max()) or 1.0
    # the first pause (50 ms under -30 dB) after 0.25 s ends a long gesture
    quiet = env < peak * 10 ** (-30 / 20.0)
    end = len(env)
    run = 0
    for i in range(25, len(env)):
        run = run + 1 if quiet[i] else 0
        if run >= 5:
            end = i - 4
            break
    e = np.cumsum(env[:end] ** 2)
    t80 = (int(np.searchsorted(e, 0.8 * e[-1])) + 1) * 0.01 if len(e) else EIGHTH
    lead = min(DQ, max(EIGHTH, math.ceil(t80 / EIGHTH - 1e-6) * EIGHTH))
    return lead, min(end * 0.01, lead + EIGHTH)


@functools.lru_cache(maxsize=None)
def _harp_pickup() -> np.ndarray:
    flick = A.lowpass(card_sound("flick"), 4500, 2)
    harp = render([n("harp", PICKUP_NOTE, 0.0, 0.5, vel=76)], 1.6)
    x = np.zeros(A.n_of(1.6))
    x = A.mix_at(x, to_level(flick, level(harp) - 8.0), 0.0)
    x = A.mix_at(x, _cut(harp), 0.012)
    # the render stops at 1.6 s while the harp still rings (about -35 dB): damp it over
    # the last 0.3 s, or the cut is a tick 1.61 s into every clip (its quietest blocks
    # only, so ``level`` and the pickup's balance are unchanged)
    k = A.n_of(0.3)
    x[-k:] *= 0.5 + 0.5 * np.cos(np.linspace(0, math.pi, k))
    return x


def pickup(kind: Union[str, None, Tuple[np.ndarray, float]] = "harp") -> Tuple[np.ndarray, float]:
    """The clip's first sound and where the motif's downbeat falls after it (seconds):
      "harp"     a soft card flick (the owner's card-select flick, softened) and one plucked
                 harp D5; the downbeat at PICKUP (0.12 s)
      "flick"    the flick alone; the downbeat at 0.06 s
      "shuffle" / "draw" / "discard"   the game's own card sound (``card_sound``), kept to
                 its main gesture; the downbeat after it (0.11 to 0.33 s)
      None       no pickup; the downbeat at 0
      (audio, lead)   your own"""
    if kind is None or kind == "none":
        return np.zeros(1), 0.0
    if isinstance(kind, tuple):
        return kind[0], float(kind[1])
    if kind == "harp":
        return _harp_pickup().copy(), PICKUP
    if kind == "flick":
        return A.lowpass(card_sound("flick"), 4500, 2), 0.06
    x = card_sound(kind)
    lead, keep = _gesture(x)
    return card_sound(kind, keep=keep, fade=min(0.08, keep / 3)), lead


_pickup = pickup


# ============================================================================= cadence and tail
_CHORDS = {
    "major": ("D3", "A3", "F#4"),
    "minor": ("D3", "A3", "F4"),
    "fifth": ("D3", "A3", "D4"),           # D with no third: bare, modal
    "open": ("A2", "E3", "A3"),            # the open A-E fifth under an A ending: a question
}


def _is_a(end: Union[str, int]) -> bool:
    """Whether an ending is the open A ("A", "A4", 69...)."""
    if isinstance(end, str) and not end[-1].isdigit():
        return end.upper().startswith("A")
    return midi(end) % 12 == 9


def _end_pitch(end: Union[str, int], ref: Optional[int]) -> int:
    """``end`` "D" / "A" -> the D or A nearest the motif's last note (a tie goes down);
    a full pitch ("D4", 62) is used as is."""
    if isinstance(end, (int, np.integer)) or (isinstance(end, str) and end[-1].isdigit()):
        return midi(end)
    pc = 2 if end.upper().startswith("D") else 9
    ref = ref if ref is not None else (74 if pc == 2 else 69)
    cands = [m for m in range(ref - 12, ref + 13) if m % 12 == pc]
    return min(cands, key=lambda m: (abs(m - ref), m > ref))


def bed_notes(chord: Union[str, Sequence] = "major", inst: Union[str, int] = "harp", vel: int = 60,
              spread: float = 0.022) -> List[INote]:
    """The soft rolled chord under the cadence (times from 0): ``chord`` "major" (D F# A),
    "minor" (D F A), "fifth" (D A), "open" (A E: under an A ending), or your own pitches."""
    ps = _CHORDS[chord] if isinstance(chord, str) else chord
    return roll(inst, ps, 0.0, 0.9, vel=vel, spread=spread)


def cadence_notes(end: Union[str, int], instrument: Union[str, int], start: float, hold: float, vel: int = 84,
                  ref: Optional[int] = None, bank: Optional[str] = None) -> List[INote]:
    """The held final note on the signature instrument at ``start`` for ``hold`` seconds
    (blown, bowed and sung instruments fade under the breath or bow)."""
    p = prog(instrument)
    pitch = _end_pitch(end, ref)
    swell = (118, 46) if p in SUSTAINED else None
    return [INote(p, pitch, start, hold, vel=int(vel), swell=swell, bank=bank)]


def default_end(row: str) -> str:
    """"A" for a card shown just before a decision box (it ends open, a question), else "D".
    Advisory: the row's own brief in docs/info_popups.json may say otherwise."""
    return "A" if row in BEFORE_BOX else "D"


# Rows whose card stands right before a decision box (docs/info_popups.json "order"). The
# Jester rows (the Whistle jig, on D) and Declared (after its box) are not among them.
BEFORE_BOX = frozenset({
    "kinfolk_flute", "scarlet_whistle", "azure_emblem", "mother_corrupt", "mage", "druid", "chanter", "reaver",
    "enemy_attack", "m7_match", "m8_filled", "m9_piles", "m10_bard", "m11_beast", "bane12", "bane21", "bane23",
    "boon30", "boon31", "boon32", "boon33", "boon35",
})


# ============================================================================= room and master
def room(x: np.ndarray, room_: float = ROOM, wet: float = WET, tail: float = 1.0) -> np.ndarray:
    """The tavern: the Whistle jig's reverb (room 0.35, wet 0.16), with ``tail`` s to ring."""
    return A.reverb(x, room_, wet, DAMPING, 1.0, tail)


def finish(x: np.ndarray, length: float, fade: float = 0.36, crest_db: float = 14.0, wet: float = WET) -> np.ndarray:
    """The master chain: tavern room, high-pass 100 Hz, low-pass 7.5 kHz, cut to ``length``
    with a half-cosine fade over the last ``fade`` s, a sub-millisecond fade-in, the peaks
    glued, then trimmed exactly as build.py trims (so its length is what the build sees)."""
    y = room(x, wet=wet)
    y = A.highpass(y, HP, 2)
    y = A.lowpass(y, LP, 4)
    y = _fit(y, length)
    k = min(len(y), A.n_of(fade))
    y[-k:] *= 0.5 + 0.5 * np.cos(np.linspace(0, math.pi, k))
    j = min(len(y), 24)
    y[:j] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(j) / j)
    y = glue(y - np.mean(y), crest_db)
    return A.trim(y, -70.0, 0.01)


# ============================================================================= the clip
Layer = Union[Tuple[np.ndarray, float], Tuple[np.ndarray, float, Optional[float]]]


def clip(motif: Sequence[Note] = (), *, end: Union[str, int] = "D", mood: str = "major",
         instrument: Union[str, int, None] = None, pickup: Union[str, None, tuple] = "harp", slow: bool = False,
         cadence_at: Optional[float] = None, hold: Optional[float] = None, held_vel: Optional[int] = None,
         chord: Union[str, Sequence, None] = None, bed: Union[str, int, None] = "harp", tail: Union[bool, str] = True,
         layers: Sequence[Layer] = (), bank: Optional[str] = None, pickup_db: Optional[float] = None,
         bed_db: float = -12.0, tail_db: float = -15.0, length: Optional[float] = None, fade: float = 0.36,
         crest_db: float = 14.0, wet: float = WET, max_s: float = MAX_S) -> np.ndarray:
    """One info clip: pickup + motif + held cadence and tail, through the room and master
    chain; returns raw mono audio of 2.0 to 2.4 s (raises ValueError otherwise).

    motif       notes, times from the motif's downbeat (a note may start up to the
                pickup's length before it, negative); normally two bars (MOTIF, 1.32 s)
    end         "D" (resolved) or "A" (open: before a decision box), or a pitch ("D3")
    mood        the cadence chord's third: "party"/"major"/"folk"/"mixolydian"/"magic"/
                "lydian" major, "enemy"/"minor"/"bane"/"dorian" minor (``chord`` overrides)
    instrument  the signature instrument: holds the final note at ``cadence_at`` (the D or
                A nearest its last motif note); None: no held note (your motif holds it)
    pickup      "harp" (flick + harp D), "flick", "shuffle", "draw", "discard", None, or
                (audio, lead); see ``pickup``
    slow        half time: a longer held note
    cadence_at  seconds from the downbeat to the cadence (default MOTIF, 1.32 s)
    hold        how long the held note lasts (default 0.44 s, slow 0.66 s)
    held_vel    its velocity (default the instrument's last motif velocity, else 84)
    chord       "major", "minor", "fifth", "open" or pitches (default: from end and mood)
    bed         the instrument of the soft rolled chord ("harp", "lute", ...), None: none
    tail        True: the harp plucks the pickup's note again (D5, A4 for an A ending)
                a little after the cadence; a pitch: that note; False: no tail note
    layers      extra audio, (audio, seconds from the downbeat[, dB]): dB relative to the
                motif's ``level``, or None / absent to keep the audio's own level (bank
                renders like ``perc`` or ``render`` sit with the notes as they are); foley,
                card sounds, shaped drums, parts with their own effects
    bank        the bank for notes that do not name one (default: BANK_FOR, else Fluid)
    pickup_db   the pickup's level relative to the motif's (default -6 harp, -9 flick,
                -4 a card sound)
    bed_db, tail_db   the bed's and the tail note's level relative to the motif's
    length      the clip's length before the trim (default: to the held note's end plus
                0.34 s, kept within 2.10..2.36 s; the trim then takes ~0.01-0.03 s)
    fade        the final fade's length; crest_db: the glue; wet: the room's wet level
    max_s       the upper limit checked (2.4; the Jester rows may pass 2.6)"""
    pk, lead = _pickup(pickup)
    motif = list(motif)
    early = min([x.start for x in motif] + [0.0])
    if early < -lead - 1e-9:
        raise ValueError("a motif note starts %.3f s before the downbeat; the pickup is only %.3f s" % (-early, lead))
    cad = MOTIF if cadence_at is None else float(cadence_at)
    hold = (0.66 if slow else 0.44) if hold is None else float(hold)
    is_a = _is_a(end)
    if chord is None:
        chord = "open" if is_a else ("minor" if Key(mood).minor else "major")
    notes = [dataclasses.replace(x, start=x.start + lead) for x in motif]
    if instrument is not None:
        p = prog(instrument)
        mine = [x for x in motif if x.program == p]
        last = max(mine, key=lambda x: x.start) if mine else None
        ref = last.key() if last is not None else None
        v = held_vel if held_vel is not None else (last.vel if last is not None else 84)
        notes += cadence_notes(end, p, lead + cad, hold, v, ref, bank)
    total = A.n_of(lead + cad + 2.5)
    x = np.zeros(total)
    m = render(notes, bank=bank) if notes else np.zeros(1)
    x = A.mix_at(x, m, 0.0)
    ref_db = level(m) if notes else None
    for lay in layers:
        audio, t = lay[0], float(lay[1])
        db = lay[2] if len(lay) > 2 else None
        if ref_db is None and db is not None:
            ref_db = level(audio) - db
        y = to_level(audio, ref_db + db) if db is not None else audio
        x = A.mix_at(x, y, lead + t)
    if ref_db is None:
        ref_db = level(x) if np.any(x) else -30.0
    # the pickup
    if len(pk) > 1:
        if pickup_db is None:
            pickup_db = -6.0 if pickup == "harp" else (-9.0 if pickup == "flick" else -4.0)
        x = A.mix_at(x, to_level(pk, ref_db + pickup_db), 0.0)
    # the bed and the tail
    if bed:
        x = A.mix_at(x, to_level(render(bed_notes(chord, bed)), ref_db + bed_db), lead + cad)
    if tail:
        tp = tail if isinstance(tail, str) else ("A4" if is_a else PICKUP_NOTE)
        tn = render([n("harp", tp, 0.0, 0.6, vel=64)])
        x = A.mix_at(x, to_level(tn, ref_db + tail_db), lead + cad + QUARTER)
    if length is None:
        length = min(_SAFE[1], max(_SAFE[0], lead + cad + hold + 0.34))
    y = finish(x, length, fade, crest_db, wet)
    secs = len(y) / SR
    if not (MIN_S <= secs <= max_s):
        raise ValueError("the clip is %.3f s (it must be %.1f to %.1f s): adjust length= or the motif"
                         % (secs, MIN_S, max_s))
    return y


def info(row: str, cid: str, title: str, note: str, render_, tags: Sequence[str] = ()) -> Candidate:
    """A candidate for row ``row``'s clip (event "info_<row>")."""
    ev = "info_" + row
    if ev not in EVENT_BY_ID:
        raise KeyError("no event %r in catalog.py" % ev)
    return Candidate(ev, cid, title, note, render_, list(tags))
