"""The info pop-ups' stinger toolkit: short, simple clips that carry one feeling over the
mission music. Not a family (the leading "_"): the composers' families import it.

    from _stingers import *

    def _turn_harp():                      # neutral: one soft harp A, left to ring
        return stinger(strike("harp", "A4", vel=56), room="near")

    def _attack_drum():                    # threat: a war drum and a low trombone stab on D
        return stinger(hit("war_drum", vel=112),
                       swell("trombone", "D3", dur=1.1, peak=0.06, start_db=-3, vel=100).db(-4))

    CANDIDATES = [
        option("turn", "harp_a", "Single harp A", "One soft harp A, left to ring in a small room.",
               _turn_harp, "neutral", "instrumental"),
        option("enemy_attack", "drum_trombone", "War drum, low trombone", "...", _attack_drum, "threat", "hybrid"),
    ]

THE OWNER'S RULES (``stinger`` enforces 1-4 and the length; the critics judge 5-7)
  1. SIMPLE: one or two sound sources per clip (a ``Layer`` is one source: one instrument,
     one percussion or one texture). ``stinger`` raises on three or more layers.
  2. NO MELODY: at most three pitched notes in the clip (``MAX_NOTES``); better one or two.
     A single note, an interval, one chord struck or swelled once, a slide, a roll.
  3. NO SHARED OPENING: start on different sources and pitches; never a common pickup.
     ``python3 _stingers.py over <family>`` lists each clip's opening and the shared ones.
  4. OVER DARK MUSIC (assume D minor or modal D): pitches are D or A in any octave; any
     other note must be marked as colour on purpose with a "*" ("F3*", "Eb4*"), one colour
     pitch class per clip at most. Layers lose their low-mid below ``CLEAR_HZ`` (the
     music's 80-250 Hz) unless weight is the point (``.heavy()``; hits, timpani, rolls on
     drums and rumble are heavy by default). A clear onset when the card appears (the
     first 0.12 s within ``ONSET_DB`` of the loudest moment, ``onset=`` moves the check
     for a breath into a hit), then a natural decay: 2.0-2.4 s (Jester rows 2.6:
     ``max_s=JESTER_S``), mostly the gesture's own tail, already ``TAIL_DB`` down when
     the clip has to end.
  5. EMOTION FIRST: pick the row's colour from ``PALETTE`` (``ROW_COLOUR``, ``SHARED``).
  6. THREE OPTIONS per pop-up, three approaches (``APPROACHES``): instrumental (a bowed,
     blown or sung gesture), textural (percussion or a modelled texture), hybrid (one of
     each, minimal). Name each by what it feels or sounds like.
  7. ACOUSTIC: real instrument samples (the FluidSynth banks, through _info_common's
     renderer and this module's tuning table) and modelled natural textures; no synth tones.

GESTURES: each returns a ``Layer`` (one source), cut to start at its own onset.
  swell(inst, pitches, dur, peak, start_db, ...)   a bowed, blown or sung note, fifth or
        chord that rises to ``peak`` seconds and falls away (``peak`` near 0: a stab)
  strike(inst, pitches, vel, spread, ...)          a struck or plucked note or chord with
        its natural decay (harp, lute, dulcimer, bells, celesta, timpani...); ``spread``
        rolls it; ``damp`` puts a hand on it
  slide(inst, frm, to, dur, glide, ...)            one bowed, blown or sung note gliding
        from ``frm`` to ``to`` (both D/A or colour; within an octave)
  roll(inst, pitch, dur, shape, vel, ...)          a timpani, marimba, snare, frame drum,
        bass drum or suspended cymbal roll ("fade", "swell", "steady", "cresc")
  hit(source, vel, felt) / hits(source, pattern) / heartbeat()   a drum or wood impact,
        or a few strokes of one (``HITS``)
  TEXTURES (modelled, unpitched): air, breath, wind, rustle (cards, leaves, cloth),
        water (lap, stream), drips, rumble, embers, chains, sparkle, creak
  Layer methods: .at(seconds) .db(dB re the lead layer's level; default -6) .heavy()
        .far(amount) (darker, wetter: heard from farther away)
  Pitches: "D3", "D3+A3", ["D3", "A3"], MIDI numbers; helpers fifth(3) "D3+A3",
        octave(3) "D3+D4", minor(3) "D3+F3*+A3", rub(4) "D4+Eb4*", colour("F3") "F3*".

THE CLIP: stinger(*layers, length=None, onset=0.0, room="hall", max_s=MAX_S, ...) mixes
  one or two layers (the first is the reference level), places them (``.at``), puts them
  in a room (``ROOMS``: near, tavern, hall, crypt, chapel, cave, open, dry), filters
  (subsonic high-pass, ``lp`` low-pass), finds the natural end, fades only what is left,
  glues the peaks and trims as build.py trims. It returns raw mono audio for a
  Candidate's render; the build masters it. ``LAST`` describes the clip just made.

OVER THE MUSIC: dark_bed(seconds) is a test bed in the spirit of the planned mission
  music (low bowed strings on D with a minor colour, a slow quiet timpani pulse); and
  over_bed(clip, bed=None, at=1.0, duck_db=-8.0, event=...) masters the clip as the build
  does, ducks the bed as the game does (to about 40%) and measures how the clip reads:
  ``reads_db`` (clip over bed in the clip's main octave band), ``onset_db`` (the same for
  the best 60 ms of its first 0.15 s, in that moment's main band), ``phone_db`` (above
  ~350 Hz, what a phone speaker plays), ``masked`` (the share of the clip's energy in
  bands the bed covers) and a verdict: clear (reads >= 8 dB), faint (>= 3), buried (less,
  or a phone_db under 0). A heavy low D (D2) merges with the music's drone: it reads buried.

    python3 tools/audio/families/_stingers.py                 # writes out/_bed/dark_bed.wav/.mp3
    python3 tools/audio/families/_stingers.py over <family>.. # each clip over the bed: out/_bed/<event>/<id>.*
    python3 tools/audio/families/_stingers.py palette         # the emotion palette
    python3 tools/audio/families/_stingers.py sketches        # renders every palette sketch, with its reading

Everything is deterministic (seeded noise, cached renders): a rebuild is identical.
"""
from __future__ import annotations

import dataclasses
import functools
import math
import os
import re
import subprocess
import sys
import tempfile
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))           # tools/audio/families
AUDIO = os.path.dirname(HERE)                                # tools/audio
for _p in (AUDIO, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _info_common as IC  # noqa: E402
import sf  # noqa: E402
import synth as A  # noqa: E402
from catalog import EVENT_BY_ID, Candidate  # noqa: E402

__all__ = [
    # limits and rooms
    "SR", "MIN_S", "MAX_S", "JESTER_S", "JESTER_ROWS", "MAX_LAYERS", "MAX_NOTES", "CLEAR_HZ", "ONSET_DB",
    "TAIL_DB", "ROOMS", "Room", "max_for", "A",
    # pitches
    "fifth", "octave", "minor", "rub", "colour", "DETUNE", "tune", "INSTRUMENTS",
    # gestures and textures
    "Layer", "swell", "strike", "slide", "roll", "hit", "hits", "heartbeat", "HITS",
    "air", "breath", "wind", "rustle", "water", "drips", "rumble", "embers", "chains", "sparkle", "creak",
    # the clip
    "stinger", "LAST", "option", "APPROACHES",
    # the palette
    "Colour", "PALETTE", "ROW_COLOUR", "SHARED", "palette_text",
    # over the music
    "dark_bed", "over_bed", "master_like_build", "write_over_bed",
]

SR = A.SR
OUT = os.path.join(AUDIO, "out")
BED_DIR = os.path.join(OUT, "_bed")

# ============================================================================= the rules' numbers
MIN_S, MAX_S, JESTER_S = 2.0, 2.4, 2.6     # every clip; the four Jester rows may run to 2.6 s
JESTER_ROWS = frozenset({"jester", "jester_claim", "solo_jester_refresh", "solo_jester_attack"})
MAX_LAYERS = 2              # sources per clip
MAX_NOTES = 3               # distinct pitched notes per clip
SAFE_PCS = (2, 9)           # D and A: the music's root and fifth
CLEAR_HZ = 160.0            # a layer that is not weight leaves the music's low-mid (2nd-order high-pass)
SUBSONIC_HZ = 35.0          # every clip
LP_HZ = 9000.0              # the clip's default low-pass (nothing hisses over the music)
ONSET_DB = 12.0             # the first ONSET_WINDOW s must come within this of the loudest moment
ONSET_WINDOW = 0.12
MAX_ONSET = 0.3             # ``onset=``: a breath may lead into the accent, no longer than this
TAIL_DB = 20.0              # where the clip must end, the gesture has already fallen this far
APPROACHES = ("instrumental", "textural", "hybrid")


def max_for(row: str) -> float:
    """A row's longest clip: 2.6 s for the Jester rows, else 2.4 s."""
    return JESTER_S if row.replace("info_", "") in JESTER_ROWS else MAX_S


# ============================================================================= rooms
@dataclass(frozen=True)
class Room:
    name: str
    size: float         # Freeverb room size 0..1
    wet: float          # wet level
    damping: float      # high-frequency damping 0..1
    note: str


ROOMS: Dict[str, Room] = {r.name: r for r in [
    Room("dry", 0.0, 0.0, 0.5, "no room: a layer already placed (.far) or a sound that should sit close"),
    Room("near", 0.25, 0.08, 0.5, "close and nearly dry: a quiet 'your move'"),
    Room("tavern", 0.35, 0.16, 0.5, "the Whistle jig's tavern: warm wood"),
    Room("hall", 0.72, 0.20, 0.50, "a stone hall (the default): a big drum alone rings to 2 s"),
    Room("crypt", 0.80, 0.24, 0.75, "low and long, the highs swallowed: dread"),
    Room("chapel", 0.88, 0.26, 0.40, "tall and bright, a long bloom: sacred"),
    Room("cave", 0.84, 0.30, 0.25, "hard wet walls, bright reflections: drips, echoes"),
    Room("open", 0.12, 0.05, 0.60, "outdoors: hills, forest"),
]}


def _room(room: Union[str, Room, Tuple[float, float, float], None]) -> Room:
    if room is None:
        return ROOMS["dry"]
    if isinstance(room, Room):
        return room
    if isinstance(room, str):
        try:
            return ROOMS[room]
        except KeyError:
            raise KeyError("unknown room %r: %s" % (room, ", ".join(ROOMS)))
    size, wet, damping = room
    return Room("custom", float(size), float(wet), float(damping), "")


# ============================================================================= pitches
def fifth(oct_: int = 3) -> str:
    """The open fifth on D: "D3+A3"."""
    return "D%d+A%d" % (oct_, oct_)


def octave(oct_: int = 3) -> str:
    """D and the D above: "D3+D4"."""
    return "D%d+D%d" % (oct_, oct_ + 1)


def minor(oct_: int = 3) -> str:
    """The D minor triad, its third marked as colour: "D3+F3*+A3" (three notes: the limit)."""
    return "D%d+F%d*+A%d" % (oct_, oct_, oct_)


def rub(oct_: int = 4, against: str = "Eb") -> str:
    """D rubbing against a note a semitone above (the bane's dread): "D4+Eb4*"."""
    return "D%d+%s%d*" % (oct_, against, oct_)


def colour(note: str) -> str:
    """Mark a note that is neither D nor A as colour on purpose: colour("F3") -> "F3*"."""
    return note if note.endswith("*") else note + "*"


_NAMES12 = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]


def _pname(m: int) -> str:
    return "%s%d" % (_NAMES12[m % 12], m // 12 - 1)


PitchSpec = Union[str, int, Sequence[Union[str, int]]]


def _parse(spec: PitchSpec) -> List[Tuple[int, bool]]:
    """Pitches as (MIDI, colour on purpose). D and A pass; any other note must carry "*"."""
    if isinstance(spec, (int, np.integer)):
        items: List[Union[str, int]] = [int(spec)]
    elif isinstance(spec, str):
        items = [s for s in re.split(r"[+\s,]+", spec.strip()) if s]
    else:
        items = list(spec)
    if not items:
        raise ValueError("no pitch given")
    out = []
    for it in items:
        col = False
        if isinstance(it, str):
            s = it.strip()
            if s.endswith("*"):
                col, s = True, s[:-1]
            m = A.midi(s)
        else:
            m = int(it)
        if m % 12 not in SAFE_PCS and not col:
            raise ValueError("%s is neither D nor A: over the mission music keep to D and A, or mark a colour note "
                             "on purpose with '*' (%s*)" % (_pname(m), _pname(m)))
        out.append((m, col))
    return out


# ============================================================================= instruments and tuning
# _info_common's band names (lute, viol, horn, tin_whistle, hand_bell, humming...) and a few more.
INSTRUMENTS: Dict[str, int] = dict(IC.INSTR)
INSTRUMENTS.update({
    "bell": sf.GM["tubular_bells"], "small_bell": sf.GM["tinkle_bell"], "hum": sf.GM["voice_oohs"],
    "organ": sf.GM["church_organ"], "bass": sf.GM["contrabass"],
})


def _prog(inst: Union[str, int]) -> int:
    if isinstance(inst, (int, np.integer)):
        return int(inst)
    try:
        return INSTRUMENTS[inst]
    except KeyError:
        raise KeyError("unknown instrument %r (see INSTRUMENTS)" % inst)


def _src(inst: Union[str, int]) -> str:
    if isinstance(inst, str):
        return inst
    for k, v in sf.GM.items():
        if v == int(inst):
            return k
    return "program %d" % int(inst)


def _bank_of(nt: sf.Note) -> str:
    return getattr(nt, "bank", None) or IC.BANK_FOR.get(nt.program, "fluid")


# Cents off, measured on D and A (the pitch the first five harmonics agree on, at velocity
# 90, mid-note for held instruments and the first 0.35 s for struck ones); 7 cents or more
# are listed and bent back to pitch for the note's whole length. Left out on purpose: the
# pizzicato strings (their pitch drifts by 20-30 cents over a note: avoid exposing them),
# timpani (it glides; within ~10 cents), and bells (inharmonic). The Fluid choir is 20-30
# cents flat: BANK_FOR sends the choir to MuseScore; its rows here only correct a forced Fluid.
_DETUNE_SRC: Dict[str, Dict[str, Dict[str, int]]] = {
    "cello": {"fluid": {"A3": -10}, "musescore": {"A2": -7, "D4": 10}},
    "viola": {"fluid": {"D5": -9}, "musescore": {"D5": -7}},
    "violin": {"fluid": {"D5": 7, "A5": -16}, "musescore": {"A5": -8}},
    "strings": {"fluid": {"D2": -12, "D5": 8}, "musescore": {"D2": -9, "A4": 7, "D5": 8}},
    "slow_strings": {"fluid": {"D2": -11, "D5": 8}, "musescore": {"D2": -9, "A4": 7, "D5": 8}},
    "tremolo_strings": {"fluid": {"D2": -12, "D5": 8}, "musescore": {"D2": -10, "A4": 7, "D5": 8}},
    "choir": {"fluid": {"D3": -22, "A3": -22, "D4": -30, "D5": -19},
              "musescore": {"D3": 12, "A3": 11, "D4": -7, "D5": 8}},
    "voice_oohs": {"fluid": {"D3": -10}, "musescore": {"D3": -9}},
    "bassoon": {"fluid": {"A2": -18}, "musescore": {"A2": -18}},
    "oboe": {"fluid": {"A5": -7}},
    "english_horn": {"fluid": {"D4": -12, "A4": -7, "D5": -10}, "musescore": {"D4": -12, "A4": -8, "D5": -8}},
    "flute": {"fluid": {"D4": 7}, "musescore": {"D4": 7}},
    "recorder": {"fluid": {"D5": 12, "D6": 7}},
    "piccolo": {"fluid": {"A5": 7}},
    "celesta": {"fluid": {"D6": 10}, "musescore": {"D6": 10}},
    "church_organ": {b: {"D2": 14, "A2": 8, "D3": 10, "A3": 8, "D4": 9, "A4": 9} for b in ("fluid", "musescore")},
    "accordion": {b: {"D3": 7, "A3": 8, "D4": 7} for b in ("fluid", "musescore")},
    # the blown bottle is ~22 cents sharp on every note (one sample set in both banks)
    "bottle": {b: {"D4": 20, "A4": 20, "D5": 21, "A5": 22, "D6": 22, "A6": 22} for b in ("fluid", "musescore")},
}
DETUNE: Dict[Tuple[int, str], Dict[int, int]] = {
    (sf.GM[inst], bank): {A.midi(p): c for p, c in table.items()}
    for inst, banks in _DETUNE_SRC.items() for bank, table in banks.items()
}


def tune(notes: Sequence[sf.Note]) -> List[sf.Note]:
    """``notes`` with the out-of-tune samples (``DETUNE``) bent back to pitch."""
    out: List[sf.Note] = []
    for x in notes:
        if x.program != sf.DRUM:
            c = DETUNE.get((x.program, _bank_of(x)), {}).get(x.key())
            if c:
                b0, b1 = x.bend if x.bend is not None else (0.0, 0.0)
                x = dataclasses.replace(x, bend=(b0 - c / 100.0, b1 - c / 100.0))
        out.append(x)
    return out


def _render(notes: Sequence[sf.Note], seconds: Optional[float] = None) -> np.ndarray:
    """_info_common's renderer (banks, the lute's body, caching) with the samples in tune."""
    return IC.render(tune(list(notes)), seconds)


def _from_onset(x: np.ndarray, floor_db: float = -50.0, pre: float = 0.0004) -> np.ndarray:
    """Cut the bank's few ms of latency: start just before the first sound."""
    if not len(x) or not np.any(x):
        return x
    i = max(0, sf.onset(x, floor_db) - A.n_of(pre))
    y = x[i:].copy()
    k = max(1, A.n_of(pre))
    y[:k] *= np.linspace(0.0, 1.0, k)
    return y


def _even_attack(x: np.ndarray, max_boost_db: float = 9.0) -> np.ndarray:
    """Lift a sustained sample's slow attack to its steady level (by up to ``max_boost_db``),
    so the bow or breath starts firmly and a swell's curve is the sound's curve (some
    samples take 0.2-0.6 s to speak: the cello's A3, the slow strings, the cor anglais)."""
    from scipy.ndimage import uniform_filter1d
    blk = A.n_of(0.005)
    k = len(x) // blk
    if k < 100:
        return x
    e = np.sqrt(np.mean(x[:k * blk].reshape(k, blk) ** 2, axis=1))
    e = uniform_filter1d(e, 5)
    steady = float(np.median(e[70:min(k, 180)]))
    reach = np.nonzero(e >= 0.89 * steady)[0]
    ia = int(reach[0]) if len(reach) else k
    if ia == 0 or steady <= 0:
        return x
    gain = np.ones(k)
    gain[:ia] = np.clip(steady / np.maximum(e[:ia], 1e-12), 1.0, 10 ** (max_boost_db / 20.0))
    gain = uniform_filter1d(gain, 4)
    return x * np.interp(np.arange(len(x)), (np.arange(k) + 0.5) * blk, gain)


def _drop_tail(x: np.ndarray, floor_db: float = -75.0) -> np.ndarray:
    """Cut what stays under ``floor_db`` (re the peak) at the end (keeps layers short)."""
    if not len(x) or not np.any(x):
        return x
    peak = float(np.max(np.abs(x)))
    idx = np.nonzero(np.abs(x) > peak * 10 ** (floor_db / 20.0))[0]
    y = x[:min(len(x), int(idx[-1]) + A.n_of(0.01))].copy()
    k = min(len(y), A.n_of(0.01))
    y[-k:] *= np.linspace(1.0, 0.0, k)
    return y


# per-program treatment of struck sounds after the bank renders them
_TREAT = {
    sf.GM["tubular_bells"]: lambda x: A.lowpass(x, 4500, 4),     # the tubular bell's clang taken down
    sf.GM["tinkle_bell"]: lambda x: A.lowpass(x, 4200, 4),       # rings rather than pings
}


# ============================================================================= envelopes and noise helpers
def _swell_env(n: int, peak: float, dur: float, start_db: float, fall_db: float = 48.0,
               hold: float = 0.0) -> np.ndarray:
    """An amplitude curve: from ``start_db`` up to 0 dB at ``peak`` s (a raised cosine in dB),
    held ``hold`` s, then a natural fall (linear in dB: exponential) reaching ``-fall_db`` at
    ``dur`` s and going on falling."""
    t = np.arange(n) / SR
    peak = max(1e-3, float(peak))
    db = np.zeros(n)
    a = t < peak
    db[a] = start_db * (0.5 + 0.5 * np.cos(np.pi * t[a] / peak))
    r = t >= peak + hold
    span = max(0.05, dur - peak - hold)
    db[r] = -fall_db * (t[r] - peak - hold) / span
    env = 10 ** (np.maximum(db, -120.0) / 20.0)
    k = min(n, A.n_of(0.003))
    env[:k] *= np.linspace(0.0, 1.0, k)
    return env


def _smooth(n: int, hz: float, seed: int) -> np.ndarray:
    """A slow random curve in -1..1 (cosine-interpolated points ``hz`` times a second)."""
    rng = np.random.default_rng(seed)
    k = max(3, int(math.ceil(n / SR * hz)) + 2)
    pts = rng.uniform(-1.0, 1.0, k)
    dx = (n - 1) / (k - 1) if n > 1 else 1.0
    p = np.arange(n) / dx
    j = np.minimum(p.astype(int), k - 2)
    u = p - j
    w = 0.5 - 0.5 * np.cos(np.pi * u)
    return pts[j] * (1 - w) + pts[j + 1] * w


def _vbandpass(x: np.ndarray, freqs: np.ndarray, q: float = 1.5, block: int = 256) -> np.ndarray:
    """A band-pass whose centre follows ``freqs`` (per sample), block by block."""
    out = np.empty_like(x)
    zi = np.zeros((1, 2))
    nyq = SR / 2.0
    for i in range(0, len(x), block):
        f = float(np.mean(freqs[i:i + block]))
        lo = max(20.0, f * (1 - 0.5 / q))
        hi = min(nyq * 0.95, f * (1 + 0.5 / q))
        sos = signal.butter(1, [lo / nyq, hi / nyq], btype="bandpass", output="sos")
        out[i:i + block], zi = signal.sosfilt(sos, x[i:i + block], zi=zi)
    return out


def _bubble(f0: float, xi: float = 0.08, amp: float = 1.0) -> np.ndarray:
    """A water bubble or drop (van den Doel's model): a sine that rises as it dies away."""
    d = 0.043 * f0 + 0.0014 * f0 ** 1.5
    dur = min(0.35, 7.0 / d)
    t = A.seconds(dur)
    f = f0 * (1 + xi * d * t)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-d * t) * amp
    k = A.n_of(0.0006)
    y[:k] *= np.linspace(0.0, 1.0, k)
    return y


def _modal(f0: float, ratios: Sequence[float], gains: Sequence[float], t60s: Sequence[float],
           rng: np.random.Generator, dur: float, click: float = 0.15) -> np.ndarray:
    """A small struck object (a chain link, a glass): a few inharmonic modes and a click."""
    t = A.seconds(dur)
    y = np.zeros(len(t))
    for r, g, tt in zip(ratios, gains, t60s):
        f = f0 * r
        if f > 15000:
            continue
        y += g * np.sin(2 * np.pi * f * t + rng.uniform(0, 2 * np.pi)) * np.exp(-6.9078 * t / tt)
    nk = A.n_of(0.002)
    y[:nk] += click * rng.standard_normal(nk) * np.exp(-np.linspace(0, 6, nk))
    k = A.n_of(0.0004)
    y[:k] *= np.linspace(0.0, 1.0, k)
    return y


def _place(buf: np.ndarray, x: np.ndarray, t: float, gain: float = 1.0) -> np.ndarray:
    i = A.n_of(t)
    if i >= len(buf):
        return buf
    k = min(len(x), len(buf) - i)
    buf[i:i + k] += gain * x[:k]
    return buf


# ============================================================================= the layer
@dataclass(frozen=True, eq=False)
class Layer:
    """One sound source of a clip: audio from its own onset, what it is, and where it goes.
    The first layer of a stinger is the reference; a second layer's ``gain_db`` is its
    level relative to the first (default -6 dB; the build masters the whole clip)."""
    audio: np.ndarray = field(repr=False)
    source: str
    gesture: str
    pitches: Tuple[int, ...] = ()
    colour: Tuple[int, ...] = ()
    start: float = 0.0
    gain_db: Optional[float] = None
    weight: bool = False
    first: Optional[int] = None         # the pitch heard first (a slide's start, a roll's first note)

    def at(self, seconds: float) -> "Layer":
        """Start this layer ``seconds`` into the clip."""
        return dataclasses.replace(self, start=float(seconds))

    def db(self, gain_db: float) -> "Layer":
        """This layer's level relative to the lead layer's (ignored on the lead)."""
        return dataclasses.replace(self, gain_db=float(gain_db))

    def heavy(self, on: bool = True) -> "Layer":
        """Keep this layer's low end (weight is the point: an impact, a rumble, a drone)."""
        return dataclasses.replace(self, weight=bool(on))

    def far(self, amount: float = 0.5) -> "Layer":
        """Heard from farther away: darker, more diffuse, the room's reflections ahead of
        the sound itself (``amount`` 0..1). Combine with ``.db`` to make it quieter."""
        return dataclasses.replace(self, audio=_distance(self.audio, amount))

    @property
    def seconds(self) -> float:
        return len(self.audio) / SR

    def describe(self) -> str:
        p = "+".join(_pname(m) + ("*" if m in self.colour else "") for m in self.pitches)
        return "%s %s%s%s%s" % (self.source, self.gesture, (" " + p) if p else "",
                                (" at %.2f" % self.start) if self.start else "",
                                (" %+.0f dB" % self.gain_db) if self.gain_db is not None else "")


def _layer(audio: np.ndarray, source: str, gesture: str, ps: Sequence[Tuple[int, bool]] = (),
           weight: bool = False, first: Optional[int] = None) -> Layer:
    return Layer(_drop_tail(audio), source, gesture, tuple(sorted(set(m for m, _ in ps))),
                 tuple(sorted(set(m for m, c in ps if c))), weight=weight, first=first)


def _wet(x: np.ndarray, size: float, damping: float, tail: float) -> np.ndarray:
    from pedalboard import Reverb
    pad = np.concatenate([x, np.zeros(A.n_of(tail))])
    return A._pb(pad, [Reverb(room_size=size, wet_level=1.0, dry_level=0.0, damping=damping, width=1.0)])


def _distance(x: np.ndarray, amount: float) -> np.ndarray:
    a = float(np.clip(amount, 0.0, 1.0))
    y = A.lowpass(x, 9000.0 * (1 - a) + 1600.0 * a, 2)
    wet = _wet(y, 0.8, 0.6, 1.2)
    pre = A.n_of(0.012 + 0.03 * a)
    out = np.zeros(len(wet) + pre)
    out[:len(y)] += (1.0 - 0.55 * a) * y
    out[pre:pre + len(wet)] += (0.12 + 0.45 * a) * wet
    return _drop_tail(out)


# ============================================================================= instrumental gestures
def swell(inst: Union[str, int], pitches: PitchSpec, dur: float = 1.8, peak: float = 0.45, start_db: float = -8.0,
          hold: float = 0.0, vel: int = 84, fall_db: float = 48.0, bank: Optional[str] = None,
          weight: bool = False) -> Layer:
    """A bowed, blown or sung note (or an open fifth, one chord) that rises to ``peak`` s
    and falls away to -``fall_db`` at ``dur`` s (then the room). It starts ``start_db`` under
    its peak (the sample's own slow attack is evened out, so this is what is heard): -8 is
    a clear but soft start; with ``peak`` near 0 and ``start_db`` -2 to -4 it is a stab
    (sfz) that dies away. ``vel`` sets the bow or breath's attack and colour."""
    ps = _parse(pitches)
    hold_s = dur + 0.25
    notes = [IC.n(_prog(inst), m, 0.0, hold_s, vel=vel, bank=bank) for m, _ in ps]
    x = _even_attack(_from_onset(_render(notes, hold_s + 1.0)))
    x = x * _swell_env(len(x), peak, dur, start_db, fall_db, hold)
    return _layer(x, _src(inst), "swell", ps, weight)


def strike(inst: Union[str, int], pitches: PitchSpec, vel: int = 80, spread: float = 0.0, down: bool = False,
           hold: float = 1.2, damp: Optional[float] = None, fall: float = 0.45, lp: Optional[float] = None,
           bank: Optional[str] = None, weight: Optional[bool] = None) -> Layer:
    """A struck or plucked note or chord, left to ring (harp, lute, dulcimer, celesta,
    hand_bell / bell, small_bell, music_box, marimba, timpani...). ``spread`` s between the
    notes rolls the chord (from the bottom; ``down`` from the top); ``damp`` s puts a hand on
    it (60 dB down in ``fall`` s); ``lp`` softens the top. Timpani are heavy by default."""
    ps = _parse(pitches)
    order = sorted(ps, key=lambda p: p[0], reverse=down)
    p = _prog(inst)
    notes = [IC.n(p, m, i * spread, max(0.05, hold - i * spread), vel=max(1, vel - 4 * i), bank=bank)
             for i, (m, _) in enumerate(order)]
    x = _from_onset(_render(notes, hold + len(order) * spread + 2.2))
    if p in _TREAT:
        x = _TREAT[p](x)
    if damp is not None:
        x = IC.choke(x, damp, fall)
    if lp:
        x = A.lowpass(x, lp, 2)
    if weight is None:
        weight = p == sf.GM["timpani"]
    return _layer(x, _src(inst), "strike", ps, weight, first=order[0][0])


def _fluidsynth(mid_path: str, wav_path: str, bank: str) -> np.ndarray:
    from scipy.io import wavfile
    subprocess.run(["fluidsynth", "-ni", "-q", "-g", "0.500", "-r", str(SR), "-o", "audio.file.format=float",
                    "-o", "synth.chorus.active=1", "-o", "synth.reverb.active=1", "-o", "synth.cpu-cores=1",
                    "-F", wav_path, sf.BANKS[bank], mid_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", wavfile.WavFileWarning)
        _, x = wavfile.read(wav_path)
    x = x.astype(np.float64)
    return x.mean(axis=1) if x.ndim == 2 else x


@functools.lru_cache(maxsize=64)
def _glide_cached(program: int, key: int, dur: float, vel: int, b0: float, b1: float, t0: float, t1: float,
                  bank: str, seconds: float) -> np.ndarray:
    """One note whose pitch bend glides from ``b0`` to ``b1`` semitones between ``t0`` and
    ``t1`` s (a smoothstep), held ``dur`` s (sf.Note bends only over a whole note)."""
    import mido
    mid = mido.MidiFile(ticks_per_beat=sf.TICKS)
    tr = mido.MidiTrack()
    mid.tracks.append(tr)

    def tk(t: float) -> int:
        return max(0, int(round(t * sf.TICKS * 2)))

    def wheel(semis: float) -> int:
        return int(round(max(-8192, min(8191, semis / 12.0 * 8192))))

    ev = [(0, 0, mido.Message("control_change", channel=0, control=0, value=0)),
          (0, 0, mido.Message("program_change", channel=0, program=program)),
          (0, 0, mido.Message("control_change", channel=0, control=10, value=64)),
          (0, 0, mido.Message("control_change", channel=0, control=101, value=0)),
          (0, 0, mido.Message("control_change", channel=0, control=100, value=0)),
          (0, 0, mido.Message("control_change", channel=0, control=6, value=12)),
          (0, 0, mido.Message("control_change", channel=0, control=38, value=0)),
          (0, 0, mido.Message("control_change", channel=0, control=11, value=127)),
          (0, 1, mido.Message("pitchwheel", channel=0, pitch=wheel(b0)))]
    steps = max(2, int((t1 - t0) / 0.008))
    for s in range(steps + 1):
        u = s / steps
        sm = u * u * (3 - 2 * u)
        ev.append((tk(t0 + (t1 - t0) * u), 1, mido.Message("pitchwheel", channel=0, pitch=wheel(b0 + (b1 - b0) * sm))))
    ev.append((0, 2, mido.Message("note_on", channel=0, note=key, velocity=int(max(1, min(127, vel))))))
    ev.append((tk(dur), 0, mido.Message("note_off", channel=0, note=key, velocity=0)))
    ev.append((tk(seconds), 3, mido.Message("control_change", channel=0, control=110, value=0)))
    ev.sort(key=lambda e: (e[0], e[1]))
    now = 0
    for t, _, msg in ev:
        tr.append(msg.copy(time=t - now))
        now = t
    with tempfile.TemporaryDirectory() as d:
        mp, wp = os.path.join(d, "g.mid"), os.path.join(d, "g.wav")
        mid.save(mp)
        x = _fluidsynth(mp, wp, bank)
    return IC.fit(x, seconds)


def slide(inst: Union[str, int], frm: Union[str, int], to: Union[str, int], dur: float = 1.6,
          glide: Tuple[float, float] = (0.2, 0.7), vel: int = 84, peak: float = 0.3, start_db: float = -6.0,
          fall_db: float = 48.0, bank: Optional[str] = None, weight: bool = False) -> Layer:
    """One bowed, blown or sung note gliding from ``frm`` to ``to`` (within an octave):
    held, then the glide between the fractions ``glide`` of ``dur``, shaped like a swell
    (a rise to ``peak`` s, a fall to -``fall_db`` at ``dur``). A falling slide is a sigh,
    a rising one a lift or a call; a fall-off may end on a colour note ("C#3*")."""
    (m0, c0), = _parse([frm])
    (m1, c1), = _parse([to])
    if abs(m1 - m0) > 12:
        raise ValueError("a slide stays within an octave (%s to %s)" % (_pname(m0), _pname(m1)))
    p = _prog(inst)
    bank_ = bank or IC.BANK_FOR.get(p, "fluid")
    base = int(round((m0 + m1) / 2.0))           # the sample nearest both ends: least colour change
    cents = DETUNE.get((p, bank_), {}).get(base, 0) / 100.0
    t0, t1 = glide[0] * dur, glide[1] * dur
    x = _glide_cached(p, base, round(dur + 0.25, 4), int(vel), round(m0 - base - cents, 4),
                      round(m1 - base - cents, 4), round(t0, 4), round(t1, 4), bank_, round(dur + 1.4, 4)).copy()
    if p in IC.FX_FOR:
        x = IC.FX_FOR[p](x)
    x = _even_attack(_from_onset(x))
    x = x * _swell_env(len(x), peak, dur, start_db, fall_db)
    return _layer(x, _src(inst), "slide", [(m0, c0), (m1, c1)], weight, first=m0)


# ============================================================================= percussion
# name -> parts [(sf.DRUMS key, kit, bank, gain, choke at, choke fall)], low-pass, heavy, what it is
HITS: Dict[str, Tuple[List[tuple], Optional[float], bool, str]] = {
    "bass_drum": ([("bass_drum", "orchestra", "fluid", 1.0, None, None)], None, True,
                  "a concert bass drum, let ring"),
    "felt_drum": ([("bass_drum", "orchestra", "fluid", 1.0, 0.6, 0.9)], 900.0, True,
                  "a felt-mallet bass drum: a deep, soft thud"),
    "war_drum": ([("bass_drum", "orchestra", "fluid", 1.0, 0.25, 1.2),
                  ("low_conga", "standard", "fluid", 0.6, 0.05, 0.25)],
                 None, True, "a big skin drum struck hard"),
    "frame_drum": ([("low_floor_tom", "brush", "fluid", 1.0, 0.08, 0.3),
                    ("mute_conga", "standard", "fluid", 0.5, 0.04, 0.15)],
                   None, True, "a hand drum (tar)"),
    "bodhran": ([("low_floor_tom", "brush", "fluid", 1.0, 0.1, 0.35),
                 ("low_conga", "standard", "fluid", 0.8, 0.06, 0.25)],
                None, True, "a bodhran stroke"),
    "tabor": ([("snare", "orchestra", "musescore", 1.0, 0.04, 0.2)], None, False, "a small rope drum, dry"),
    "snare": ([("snare", "orchestra", "fluid", 1.0, None, None)], None, False, "a concert snare (for rolls)"),
    "tom": ([("low_tom", "orchestra", "fluid", 1.0, None, None)], None, True, "a low concert tom"),
    "woodblock": ([("low_woodblock", "standard", "fluid", 1.0, 0.03, 0.12)], None, False, "a low woodblock"),
    "knock": ([("low_woodblock", "standard", "fluid", 1.0, 0.02, 0.08)], 1800.0, False,
              "a knuckle on old wood"),
    "rim": ([("side_stick", "standard", "fluid", 1.0, 0.03, 0.1)], 5000.0, False, "a stick on a drum's rim"),
    "claves": ([("claves", "standard", "fluid", 1.0, None, None)], 6000.0, False, "two hardwood sticks"),
    "cymbal": ([("crash", "orchestra", "fluid", 1.0, None, None)], 7000.0, False, "a suspended cymbal, soft mallet"),
    "tambourine": ([("tambourine", "standard", "fluid", 1.0, 0.25, 0.3)], 6500.0, False, "a tambourine shake"),
    "shaker": ([("maracas", "standard", "fluid", 1.0, 0.08, 0.1)], None, False, "a seed shaker"),
    "triangle": ([("open_triangle", "standard", "fluid", 1.0, None, None)], 6000.0, False, "a triangle, let ring"),
}

# rolls: sources that are drums (one stroke from the kit) and their default stroke rates
_ROLL_DRUMS = {"snare": ("snare", "orchestra", "fluid"), "bass_drum": ("bass_drum", "orchestra", "fluid"),
               "frame_drum": ("low_floor_tom", "brush", "fluid"), "cymbal": ("crash", "orchestra", "fluid"),
               "tom": ("low_tom", "orchestra", "fluid")}
_ROLL_RATE = {"timpani": 13.0, "marimba": 12.0, "snare": 22.0, "bass_drum": 12.0, "frame_drum": 14.0,
              "cymbal": 16.0, "tom": 13.0}


@functools.lru_cache(maxsize=128)
def _hit_cached(source: str, vel: int) -> np.ndarray:
    parts, lp, _, _ = HITS[source]
    out = np.zeros(A.n_of(3.0))
    for key_, kit, bank, gain, c_at, c_fall in parts:
        y = IC.hit(key_, vel, kit, bank, 3.0)
        if c_at is not None:
            y = IC.choke(y, c_at, c_fall)
        out[:min(len(out), len(y))] += gain * y[:len(out)]
    if lp:
        out = A.lowpass(out, lp, 2)
    return _drop_tail(out)


def hit(source: str, vel: int = 100, felt: bool = False, lp: Optional[float] = None,
        weight: Optional[bool] = None) -> Layer:
    """One drum or wood impact (``HITS``: bass_drum, felt_drum, war_drum, frame_drum, bodhran,
    tabor, snare, tom, woodblock, knock, rim, claves, cymbal, tambourine, shaker, triangle).
    ``felt``: a soft mallet (the attack rounded, the top taken off). For a pitched timpani
    stroke use strike("timpani", "D2")."""
    if source not in HITS:
        raise KeyError("unknown hit %r: %s" % (source, ", ".join(sorted(HITS))))
    x = _hit_cached(source, int(vel)).copy()
    if felt:
        x = A.lowpass(x, 1200, 2)
        k = A.n_of(0.004)
        x[:k] *= np.linspace(0.0, 1.0, k) ** 2
    if lp:
        x = A.lowpass(x, lp, 2)
    return _layer(x, source, "hit", (), HITS[source][2] if weight is None else weight)


def hits(source: str, pattern: Sequence[Tuple[float, int]], felt: bool = False, lp: Optional[float] = None,
         weight: Optional[bool] = None) -> Layer:
    """A few strokes of one drum or wood: ``pattern`` [(seconds, velocity), ...] from 0
    (a knock-knock, a heartbeat). Keep it to a few: a pulse, not a rhythm section."""
    if not pattern:
        raise ValueError("no strokes")
    t_end = max(t for t, _ in pattern) + 3.0
    out = np.zeros(A.n_of(t_end))
    for t, v in pattern:
        out = _place(out, hit(source, v, felt, lp).audio, t)
    return _layer(out, source, "hits", (), HITS[source][2] if weight is None else weight)


def heartbeat(beats: int = 2, bpm: float = 62.0, vel: int = 96, source: str = "felt_drum") -> Layer:
    """A heartbeat on a felt drum: lub-dub ``beats`` times."""
    step = 60.0 / bpm
    pat = []
    for i in range(beats):
        pat += [(i * step, int(vel * (0.92 ** i))), (i * step + 0.26, int(vel * 0.7 * (0.92 ** i)))]
    return hits(source, pat)


@functools.lru_cache(maxsize=256)
def _stroke(inst: str, pitch: Optional[int], vel: int, bank: Optional[str]) -> np.ndarray:
    if inst in _ROLL_DRUMS:
        key_, kit, b = _ROLL_DRUMS[inst]
        x = IC.hit(key_, vel, kit, b, 2.5)
        if inst == "cymbal":
            x = A.lowpass(x, 6500, 2)
        return x
    return _from_onset(_render([IC.n(_prog(inst), pitch, 0.0, 0.25, vel=vel, bank=bank)], 2.5))


def _roll_vels(shape: str, k: int, lo: float, hi: float) -> np.ndarray:
    u = np.linspace(0.0, 1.0, k)
    if shape == "fade":                       # an accent, then dying away: a clear onset
        return hi * (lo / hi) ** u
    if shape == "swell":                      # from a firm start up to ``hi``, then down to ``lo``
        mid = 0.5 * (lo + hi)
        v = np.where(u < 0.4, mid + (hi - mid) * np.sin(0.5 * np.pi * u / 0.4),
                     hi * (lo / hi) ** ((u - 0.4) / 0.6))
        v[0] = max(v[0], mid + 0.25 * (hi - mid))
        return v
    if shape == "steady":
        v = np.full(k, hi * 0.85)
        tail = u > 0.75
        v[tail] = hi * 0.85 * (lo / (hi * 0.85)) ** ((u[tail] - 0.75) / 0.25)
        v[0] = hi
        return v
    if shape == "cresc":                      # soft to loud: needs another layer for the onset
        v = lo * (hi / lo) ** u
        v[-1] = hi
        return v
    raise ValueError("roll shape: fade, swell, steady or cresc")


def roll(inst: str, pitch: Optional[Union[str, int]] = None, dur: float = 1.4, shape: str = "fade",
         vel: Tuple[int, int] = (36, 100), rate: Optional[float] = None, seed: int = 0, lp: Optional[float] = None,
         bank: Optional[str] = None, weight: Optional[bool] = None) -> Layer:
    """A roll for ``dur`` s: timpani (pitch default D2), marimba (D4) or a drum (snare,
    bass_drum, frame_drum, tom, cymbal: a suspended cymbal with soft mallets). ``vel`` is
    (soft, loud); ``shape`` "fade" (an accent dying away), "swell", "steady" or "cresc"
    (soft to loud: pair it with a layer that gives the onset). Strokes alternate hands."""
    pitched = inst not in _ROLL_DRUMS
    ps: List[Tuple[int, bool]] = []
    if pitched:
        ps = _parse([pitch if pitch is not None else ("D2" if inst == "timpani" else "D4")])
    rng = np.random.default_rng(seed)
    r = rate or _ROLL_RATE.get(inst, 13.0)
    k = max(2, int(dur * r))
    lo, hi = float(min(vel)), float(max(vel))
    vs = _roll_vels(shape, k, lo, hi)
    out = np.zeros(A.n_of(dur + 2.6))
    for i in range(k):
        t = i / r + (rng.uniform(-0.12, 0.12) / r if i else 0.0)
        v = vs[i] * (0.93 if i % 2 else 1.0) * rng.uniform(0.97, 1.03)
        q = int(min(127, max(8, round(v / 8.0) * 8)))
        s = _stroke(inst, ps[0][0] if ps else None, q, bank)
        out = _place(out, s, t, v / q)
    if lp:
        out = A.lowpass(out, lp, 2)
    if weight is None:
        weight = inst in ("timpani", "bass_drum", "tom", "frame_drum")
    return _layer(out, inst, "roll", ps, weight)


# ============================================================================= modelled textures
def air(dur: float = 2.0, bright: float = 0.5, peak: float = 0.4, start_db: float = -8.0, seed: int = 0) -> Layer:
    """Moving air: a soft band of breathy noise that swells and fades (``bright`` 0..1)."""
    n = A.n_of(dur + 0.3)
    x = A.noise(dur + 0.3, "pink", seed)
    x = A.bandpass(x, 220 + 380 * bright, 1800 + 5200 * bright, 2)
    x = x * (1 + 0.18 * _smooth(n, 3.0, seed + 1))
    return _layer(x * _swell_env(n, peak, dur, start_db), "air", "texture")


_BREATH_FORMANTS = ((650.0, 1.0, 4.0), (1250.0, 0.7, 5.0), (2600.0, 0.45, 6.0), (4200.0, 0.2, 5.0))


def breath(dur: float = 0.9, kind: str = "out", seed: int = 0) -> Layer:
    """A human breath: "out" (an exhale: quick rise, long fall), "sigh" (slower, falling as
    the chest drops) or "in" (an intake that rises and stops: pair it with an onset)."""
    n = A.n_of(dur + 0.2)
    src = A.noise(dur + 0.2, "white", seed)

    def voiced(scale: float) -> np.ndarray:
        y = np.zeros(n)
        for f, g, q in _BREATH_FORMANTS:
            f *= scale
            y += g * A.bandpass(src, f * (1 - 0.5 / q), f * (1 + 0.5 / q), 2)
        return y + 0.12 * A.highpass(src, 5000, 2)

    if kind == "sigh":
        w = np.clip(np.arange(n) / max(1, A.n_of(dur)), 0, 1)
        y = voiced(1.0) * (1 - w) + voiced(0.84) * w
        env = _swell_env(n, 0.18, dur, -10.0, 50.0)
    elif kind == "in":
        y = voiced(1.08)
        t = np.arange(n) / SR
        env = np.where(t < 0.8 * dur, 10 ** ((-22 + 22 * (t / (0.8 * dur)) ** 0.7) / 20.0),
                       10 ** (-60 * (t - 0.8 * dur) / max(0.05, 0.2 * dur) / 20.0))
    elif kind == "out":
        y = voiced(1.0)
        env = _swell_env(n, 0.07, dur, -14.0, 50.0)
    else:
        raise ValueError("breath kind: out, sigh or in")
    y = y * (1 + 0.12 * _smooth(n, 9.0, seed + 3))
    return _layer(y * env, "breath", "texture")


def wind(dur: float = 2.1, strength: float = 0.5, whistle: float = 0.0, peak: float = 0.5, seed: int = 0) -> Layer:
    """Wind: noise through a band that wanders with the gusts (``strength`` 0..1 moves it
    higher and further); ``whistle`` 0..1 adds a faint hollow whistle riding on top."""
    n = A.n_of(dur + 0.3)
    base = 0.6 * A.noise(dur + 0.3, "pink", seed) + 0.4 * A.noise(dur + 0.3, "brown", seed + 1)
    gust = 0.5 + 0.5 * _smooth(n, 1.3, seed + 2)
    centre = 280.0 * 2 ** (0.3 + 1.7 * gust * strength)
    body = _vbandpass(base, centre, 2.5)
    howl = _vbandpass(base, centre * 1.9, 6.0)
    y = body / (np.std(body) or 1.0) + 0.45 * howl / (np.std(howl) or 1.0)
    if whistle > 0:
        w = _vbandpass(A.noise(dur + 0.3, "white", seed + 4), centre * 2.6, 20.0)
        y += whistle * 0.5 * w / (np.std(w) or 1.0)
    y = A.lowpass(y, 3500, 2) * (0.45 + 0.55 * gust)
    return _layer(y * _swell_env(n, peak, dur, -7.0, 45.0), "wind", "texture")


_RUSTLE = {
    "cards": dict(lo=1600.0, hi=8000.0, glen=(0.006, 0.022), rate=70.0, grain=0.7),
    "leaves": dict(lo=900.0, hi=6500.0, glen=(0.012, 0.05), rate=45.0, grain=0.85),
    "cloth": dict(lo=300.0, hi=3000.0, glen=(0.04, 0.12), rate=22.0, grain=0.4),
}


def rustle(dur: float = 0.8, kind: str = "cards", density: float = 1.0, seed: int = 0) -> Layer:
    """Many small frictions: "cards" (a deck's edges, crisp), "leaves" (dry, crackly) or
    "cloth" (a cloak, soft); dense at the start, thinning out."""
    if kind not in _RUSTLE:
        raise ValueError("rustle kind: %s" % ", ".join(_RUSTLE))
    p = _RUSTLE[kind]
    rng = np.random.default_rng(seed)
    out = np.zeros(A.n_of(dur + 0.2))
    t, k = 0.0, 0
    while t < dur:
        g = rng.uniform(*p["glen"])
        a = (1.4 if k == 0 else rng.lognormal(0.0, 0.5)) * (1 - 0.65 * t / dur)
        gr = A.paper(g, p["lo"], p["hi"], seed=seed * 1000 + k, grain=p["grain"]) * A.decay(g, g * 0.9, 0.0008)
        out = _place(out, gr, t, a)
        rate = p["rate"] * density * (0.3 + 0.7 * math.exp(-t / (0.35 * dur)))
        t += rng.exponential(1.0 / rate)
        k += 1
    return _layer(out, kind, "texture")


def water(dur: float = 2.2, kind: str = "lap", seed: int = 0) -> Layer:
    """Water: "lap" (small waves against stone or a boat, each with a splash and bubbles)
    or "stream" (a brook's babble of small bubbles)."""
    rng = np.random.default_rng(seed)
    n = A.n_of(dur + 0.3)
    t = np.arange(n) / SR
    if kind == "lap":
        crests, c = [], 0.06
        while c < dur - 0.35:
            crests.append(c)
            c += rng.uniform(0.7, 0.95)
        body = A.bandpass(A.noise(dur + 0.3, "pink", seed), 150, 1100, 2)
        spl = A.bandpass(A.noise(dur + 0.3, "white", seed + 1), 900, 4500, 2)
        amp, sp = np.zeros(n), np.zeros(n)
        out = np.zeros(n)
        for i, cr in enumerate(crests):
            a = 0.8 ** i
            amp += a * np.exp(-0.5 * ((t - cr) / 0.22) ** 2)
            sp += a * np.exp(-0.5 * ((t - cr - 0.05) / 0.07) ** 2)
            for _ in range(18):              # the slosh: bubbles and glugs as the wave breaks
                at_ = max(0.0, cr + rng.gamma(2.0, 0.05) - 0.03)
                f0 = float(np.clip(rng.lognormal(math.log(650), 0.4), 250, 1600))
                out = _place(out, _bubble(f0, 0.09, 0.7 * a * rng.uniform(0.3, 1.0)), at_)
        out += body / (np.std(body) or 1) * 0.1 * (0.1 + amp) + spl / (np.std(spl) or 1) * 0.05 * sp
    elif kind == "stream":
        body = A.bandpass(A.noise(dur + 0.3, "pink", seed), 300, 2500, 2)
        out = body / (np.std(body) or 1) * 0.05
        tt = 0.0
        while tt < dur:
            f0 = float(np.clip(rng.lognormal(math.log(900), 0.35), 350, 2600))
            out = _place(out, _bubble(f0, 0.06, rng.uniform(0.05, 0.2)), tt)
            tt += rng.exponential(1 / 55.0)
    else:
        raise ValueError("water kind: lap or stream")
    return _layer(out * _swell_env(n, 0.05, dur, -3.0, 40.0), "water", "texture")


@functools.lru_cache(maxsize=64)
def _drop_start(target_hz: float, xi: float = 0.07) -> float:
    """Where a drop must start for its chirp to be heard at ``target_hz``: a bubble's pitch
    rises as it dies (``_bubble``), so its spectrum peaks ~90 cents above its start (the
    whole drop's spectrum, unwindowed: it has died away by its end; a window would hide
    its loud start)."""
    f0 = float(target_hz)
    n = 1 << 18
    fr = np.fft.rfftfreq(n, 1.0 / SR)
    for _ in range(3):
        f0 *= target_hz / float(fr[np.argmax(np.abs(np.fft.rfft(_bubble(f0, xi), n=n)))])
    return f0


def drips(count: int = 3, spacing: float = 0.5, pitches: Sequence[str] = ("A5", "D6", "A6"), seed: int = 0) -> Layer:
    """Drops falling into a pool, one by one (``count``, about ``spacing`` s apart), tuned
    to D and A so they never clash (each drop's rising chirp peaks on its pitch); put them
    in the "cave" room."""
    rng = np.random.default_rng(seed)
    out = np.zeros(A.n_of(count * spacing * 1.3 + 0.6))
    t = 0.0
    for i in range(count):
        f0 = _drop_start(A.note_hz(pitches[i % len(pitches)])) * rng.uniform(0.997, 1.003)
        a = (1.0 if i == 0 else rng.uniform(0.55, 0.9))
        d = _bubble(f0, 0.07, a)
        nk = A.n_of(0.003)
        d[:nk] += 0.15 * a * A.highpass(rng.standard_normal(nk), 3000, 2) * np.linspace(1, 0, nk)
        out = _place(out, d, t)
        t += spacing * rng.uniform(0.75, 1.3)
    return _layer(out, "drips", "texture")


def rumble(dur: float = 2.1, depth: float = 0.6, grit: float = 0.0, peak: float = 0.3, start_db: float = -6.0,
           seed: int = 0) -> Layer:
    """Deep earth or stone: low noise that swells and settles (``depth`` 0..1 lowers it);
    ``grit`` 0..1 adds stones shifting. Heavy: its weight is the point. A phone speaker
    hardly plays it (over_bed's phone_db): pair it with a layer that does (a hit, grit,
    chains, a bell)."""
    rng = np.random.default_rng(seed)
    n = A.n_of(dur + 0.3)
    y = A.lowpass(A.noise(dur + 0.3, "brown", seed), 170 - 60 * depth, 4)
    y = A.highpass(y, 28, 2)
    y = y / (np.std(y) or 1.0) * (1 + 0.3 * _smooth(n, 2.0, seed + 1))
    if grit > 0:
        tt = 0.0
        while tt < dur:
            ln = rng.uniform(0.008, 0.03)
            st = A.lowpass(rng.standard_normal(A.n_of(ln)), 1200, 2) * A.decay(ln, ln, 0.001)
            y = _place(y, st, tt, grit * rng.uniform(0.3, 1.2))
            tt += rng.exponential(1 / 8.0)
    return _layer(y * _swell_env(n, peak, dur, start_db, 45.0), "rumble", "texture", weight=True)


def _crackle(rng: np.random.Generator, big: bool) -> np.ndarray:
    L = A.n_of(0.014)
    y = np.zeros(L)
    for _ in range(int(rng.integers(1, 4))):
        off = int(rng.integers(0, A.n_of(0.006)))
        ln = max(4, A.n_of(rng.uniform(0.0004, 0.004 if big else 0.0016)))
        b = rng.standard_normal(ln) * np.exp(-np.linspace(0, 5, ln)) * rng.uniform(0.4, 1.0)
        k = min(ln, L - off)
        y[off:off + k] += b[:k]
    if big:
        return 2.5 * A.bandpass(y, 400, 1800, 2)
    fc = rng.uniform(1800, 5500)
    return A.bandpass(y, fc / 1.6, min(fc * 1.6, 15000), 2)


def embers(dur: float = 2.0, crackle: float = 1.0, flare: bool = True, seed: int = 0) -> Layer:
    """A fire: a low breathing roar under crackles and the odd pop, flaring at the start
    (``crackle`` sets how busy it is)."""
    rng = np.random.default_rng(seed)
    n = A.n_of(dur + 0.3)
    lo = A.lowpass(A.noise(dur + 0.3, "brown", seed), 350, 2)
    mid = A.bandpass(A.noise(dur + 0.3, "pink", seed + 1), 400, 1600, 2)
    roar = 0.75 * lo / (np.std(lo) or 1) + 0.25 * mid / (np.std(mid) or 1)
    roar = roar * (1 + 0.3 * _smooth(n, 6.0, seed + 2)) * _swell_env(n, 0.3, dur, -6.0, 40.0)
    out = 0.012 * roar
    t, k = 0.0, 0
    while t < dur:
        big = k == 0 or rng.random() < 0.1
        a = (1.0 if k == 0 else min(3.0, 0.25 * (rng.pareto(2.5) + 1))) * (1 - 0.6 * t / dur)
        out = _place(out, _crackle(rng, big), t, a)
        rate = 16.0 * crackle * (1.8 if (flare and t < 0.3) else 1.0) * (1 - 0.7 * t / dur)
        t += rng.exponential(1 / max(1.0, rate))
        k += 1
    return _layer(out, "fire", "texture")


def chains(dur: float = 1.2, shake: float = 1.0, seed: int = 0) -> Layer:
    """Iron chains shaken or dragged: a jangle of small links, then a few settling."""
    rng = np.random.default_rng(seed)
    out = np.zeros(A.n_of(dur + 0.5))
    t, k = 0.0, 0
    while t < dur:
        f0 = rng.uniform(1100, 2600)
        t60s = np.array([0.22, 0.12, 0.07, 0.04]) * rng.uniform(0.7, 1.3)
        cl = _modal(f0, (1.0, 2.76, 5.40, 8.93), (1.0, 0.55, 0.3, 0.15), t60s, rng, 0.3, 0.3)
        a = (1.0 if k == 0 else rng.uniform(0.3, 0.9)) * (1 - 0.6 * t / dur)
        out = _place(out, cl, t, a)
        rate = (90.0 if t < 0.12 else 25.0 * math.exp(-(t - 0.12) / (0.5 * dur))) * shake
        t += rng.exponential(1 / max(2.0, rate))
        k += 1
    scrape = A.paper(dur, 2000, 7000, seed=seed + 5, grain=0.9) * _swell_env(A.n_of(dur), 0.05, dur, -3.0, 40.0)
    out = _place(out, scrape, 0.0, 0.05)
    return _layer(out, "chains", "texture")


def sparkle(dur: float = 1.8, count: int = 10, pitches: Sequence[str] = ("D7", "A7", "D8"), seed: int = 0) -> Layer:
    """Tiny glassy glints scattered and thinning out, their fundamentals on D and A (a
    gleam, magic, luck); keep it well under the lead."""
    rng = np.random.default_rng(seed)
    out = np.zeros(A.n_of(dur + 1.0))
    t = 0.0
    for i in range(count):
        f0 = A.note_hz(pitches[int(rng.integers(0, len(pitches)))]) * rng.uniform(0.998, 1.002)
        t60s = np.array([0.7, 0.4, 0.2, 0.1]) * rng.uniform(0.6, 1.3)
        g = _modal(f0, (1.0, 2.32, 4.25, 6.63), (1.0, 0.4, 0.2, 0.08), t60s, rng, 0.9, 0.05)
        out = _place(out, g, t, (1.0 if i == 0 else rng.uniform(0.35, 0.85)) * (1 - 0.6 * t / dur))
        t += rng.exponential(dur / (count * 1.3)) * (0.6 + 0.8 * i / count)
        if t > dur:
            break
    return _layer(out, "sparkle", "texture")


def creak(dur: float = 0.9, tension: float = 0.5, seed: int = 0) -> Layer:
    """Old wood under strain (a door, a beam, a ship's timber): a stick-slip that speeds
    up and slows down, sounding through the wood's body."""
    rng = np.random.default_rng(seed)
    n = A.n_of(dur + 0.2)
    t = np.arange(n) / SR
    u = np.clip(t / dur, 0, 1)
    rate = (40 + 60 * tension) * (1 + 0.7 * np.sin(np.pi * u)) * (1 + 0.15 * _smooth(n, 6.0, seed + 1))
    ph = np.cumsum(rate) / SR
    idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0] + 1
    imp = np.zeros(n)
    imp[idx] = rng.uniform(0.5, 1.0, len(idx))
    body = np.zeros(n)
    for f, g in ((380.0, 0.7), (760.0, 1.0), (1250.0, 0.8), (2100.0, 0.45), (3300.0, 0.2)):
        body += g * A.bandpass(imp, f / 1.06, f * 1.06, 2)
    body /= (np.std(body) or 1.0)
    body += 0.15 * A.bandpass(A.noise(dur + 0.2, "white", seed), 800, 3000, 2)
    body = A.lowpass(body, 4500, 2) * (t < dur + 0.15)
    return _layer(body * _swell_env(n, 0.12 * dur, dur, -6.0, 40.0), "wood", "texture")


# ============================================================================= the clip
LAST: Dict[str, object] = {}       # the last clip stinger() made: opening, layers, pitches, room, checks


def _sample_of(source: str) -> str:
    """The sample a source name plays, for the opening check: several names share one
    (felt_drum, war_drum and bass_drum are one bass drum; bodhran and frame_drum one
    floor tom; hand_bell and bell one tubular bell; wooden_flute and flute one flute)."""
    if source in HITS:
        key_, _, bank, _, _, _ = HITS[source][0][0]
        return key_ if bank == "fluid" else "%s (%s)" % (key_, bank)
    if source in INSTRUMENTS:
        return _src(INSTRUMENTS[source])
    return source


def _blocks_db(x: np.ndarray, blk_s: float = 0.02) -> np.ndarray:
    blk = A.n_of(blk_s)
    k = max(1, len(x) // blk)
    y = IC.fit(x, k * blk / SR)
    p = np.mean(y.reshape(k, blk) ** 2, axis=1)
    return 10 * np.log10(p + 1e-20)


def stinger(*layers: Layer, length: Optional[float] = None, onset: float = 0.0,
            room: Union[str, Room, Tuple[float, float, float], None] = "hall", max_s: float = MAX_S,
            lp: float = LP_HZ, fade: float = 0.3, crest_db: float = 16.0, tail_db: float = TAIL_DB,
            check: bool = True) -> np.ndarray:
    """One info clip from one or two layers (one sound source each): raw mono audio of
    2.0 to ``max_s`` s (2.4; ``JESTER_S`` 2.6 for the Jester rows) for a Candidate.

    layers   one or two ``Layer``s; the first is the reference level, the second sits at its
             ``.db`` (default -6 dB) and starts at its ``.at``. Three or more raise.
    length   the clip's length before the build's trim; default: where the sound has died
             away (-45 dB) plus 0.1 s, within 2.06 s and ``max_s`` - 0.03 s
    onset    when the accent falls (s): 0 for most clips; up to 0.3 for a breath, a swell or
             a cymbal leading into it. The first ``onset`` + 0.12 s must reach within
             ``ONSET_DB`` (12 dB) of the clip's loudest moment.
    room     a ``ROOMS`` name (near, tavern, hall, crypt, chapel, cave, open, dry), a Room
             or (size, wet, damping)
    lp       the low-pass on the whole clip (Hz); fade: the final half-cosine fade (s)
    crest_db peaks held this far above the loudness (glue), so the build's limiter barely acts
    tail_db  the gesture must be this far under its loudest moment where the fade begins
    check    False skips the onset and tail checks (never the layer, note and length limits)

    Raises ValueError when a rule is broken, naming the rule and a fix."""
    if not layers:
        raise ValueError("a stinger needs a layer")
    if len(layers) > MAX_LAYERS:
        raise ValueError("one or two sound sources per clip (the owner's rule): got %d layers: %s"
                         % (len(layers), "; ".join(L.describe() for L in layers)))
    for L in layers:
        if not isinstance(L, Layer):
            raise TypeError("stinger takes Layers (from swell, strike, slide, roll, hit, hits or a texture)")
    pitches = sorted(set(p for L in layers for p in L.pitches))
    if len(pitches) > MAX_NOTES:
        raise ValueError("at most %d pitched notes (no melody): %s" % (MAX_NOTES, " ".join(_pname(p) for p in pitches)))
    colours = sorted(set(p for L in layers for p in L.colour))
    for L in layers:
        for p in L.pitches:
            if p % 12 not in SAFE_PCS and p not in L.colour:
                raise ValueError("%s is neither D nor A and not marked as colour" % _pname(p))
    if len(set(p % 12 for p in colours if p % 12 not in SAFE_PCS)) > 1:
        raise ValueError("one colour note at most (a minor third or a rub): %s" % " ".join(_pname(p) for p in colours))
    if not 0.0 <= onset <= MAX_ONSET:
        raise ValueError("onset %.2f s: the accent must fall within %.1f s of the card appearing" % (onset, MAX_ONSET))
    if length is not None and length > max_s:
        raise ValueError("length %.2f s is over %.1f s" % (length, max_s))

    # the layers: low-mid cleared unless heavy, levels against the lead, placed
    t0 = min(L.start for L in layers)
    parts = []
    ref = None
    for i, L in enumerate(layers):
        y = L.audio if L.weight else A.highpass(L.audio, CLEAR_HZ, 2)
        if i == 0:
            ref = IC.level(y)
        else:
            y = IC.to_level(y, ref + (L.gain_db if L.gain_db is not None else -6.0))
        parts.append((y, L.start - t0))
    total = max(A.n_of(s) + len(y) for y, s in parts)
    x = np.zeros(total)
    for y, s in parts:
        x = _place(x, y, s)

    # the room, the clip's filters
    rm = _room(room)
    y = A.reverb(x, rm.size, rm.wet, rm.damping, 1.0, 1.6) if rm.size > 0 and rm.wet > 0 else \
        np.concatenate([x, np.zeros(A.n_of(1.6))])
    y = A.highpass(y, SUBSONIC_HZ, 2)
    y = A.lowpass(y, lp, 4)
    y = y - np.mean(y)

    # its length: where it has died away (-45 dB), inside the limits; and where the build's
    # trim (-70 dB under the peak) would end it: that must not come before 2.0 s
    env = _blocks_db(y, 0.01)
    top = float(env.max())
    alive = np.nonzero(env > top - 45.0)[0]
    natural = (int(alive[-1]) + 1) * 0.01 if len(alive) else 0.0
    audible = np.nonzero(env > top - 64.0)[0]
    heard = (int(audible[-1]) + 1) * 0.01 if len(audible) else 0.0
    hi = max_s - 0.02
    lo = MIN_S + 0.06
    L_s = float(length) if length is not None else min(hi, max(lo, natural + 0.1))

    lead = layers[0]
    first = lead.first if lead.first is not None else (lead.pitches[0] if lead.pitches else None)
    LAST.clear()
    LAST.update({
        "opening": (_sample_of(lead.source), "hit" if lead.gesture == "hits" else lead.gesture,
                    _pname(first) if first is not None else None),
        "layers": [L.describe() for L in layers], "pitches": [_pname(p) for p in pitches],
        "room": rm.name, "natural_end": round(natural, 2), "heard_until": round(heard, 2),
    })
    if heard < MIN_S:
        raise ValueError("the sound has died away by %.2f s (the build trims what is 70 dB under the peak) and a clip "
                         "lasts %.1f to %.1f s: let it ring longer (dur=, hold=, a drum left to ring), use a longer "
                         "room (crypt, chapel, cave) or add a texture" % (heard, MIN_S, max_s))

    def finish(L_s: float) -> Tuple[np.ndarray, float]:
        z = IC.fit(y, L_s)
        b50 = _blocks_db(z, 0.05)
        a, b = A.n_of(max(0.0, L_s - fade - 0.2)), A.n_of(max(0.05, L_s - fade))
        seg = z[a:b]
        end_db = (10 * math.log10(float(np.mean(seg ** 2)) + 1e-20) - float(b50.max())) if len(seg) else -120.0
        # the fade over what is left, a click-free start, the peaks glued, trimmed as the build trims
        k = min(len(z), A.n_of(fade))
        z[-k:] *= 0.5 + 0.5 * np.cos(np.linspace(0, math.pi, k))
        j = min(len(z), 24)
        z[:j] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(j) / j)
        z = IC.glue(z, crest_db)
        return A.trim(z, -70.0, 0.01), end_db

    out, end_db = finish(L_s)
    while len(out) / SR < MIN_S + 0.005 and L_s < hi and length is None:
        L_s = min(hi, L_s + 0.05)           # the fade took the quiet tail under the trim: end later
        out, end_db = finish(L_s)
    y = out
    secs = len(y) / SR

    # the onset: the first moment against the loudest
    b20 = _blocks_db(y, 0.02)
    first = float(b20[:max(1, int(math.ceil((onset + ONSET_WINDOW) / 0.02)))].max())
    onset_db = first - float(b20.max())
    LAST.update({"seconds": round(secs, 3), "onset_db": round(onset_db, 1), "end_db": round(end_db, 1)})
    if not (MIN_S <= secs <= max_s):
        raise ValueError("the clip is %.2f s (it must be %.1f to %.1f s): %s" % (
            secs, MIN_S, max_s, "let it ring longer or use a longer room" if secs < MIN_S else "shorten it"))
    if check and onset_db < -ONSET_DB:
        raise ValueError("no clear onset: the first %.2f s peak %.1f dB under the loudest moment (limit -%.0f): start "
                         "the swell higher (start_db), put the accent sooner, or let a strike or hit give the onset"
                         % (onset + ONSET_WINDOW, -onset_db, ONSET_DB))
    if check and end_db > -tail_db:
        raise ValueError("the clip must end at %.2f s but the gesture is still only %.1f dB down there (it must have "
                         "decayed %.0f dB): shorten it (dur=, damp=) or use a drier room" % (L_s, -end_db, tail_db))
    return y


def option(row: str, cid: str, title: str, note: str, render, colour_: str, approach: Optional[str] = None,
           tags: Sequence[str] = ()) -> Candidate:
    """A candidate for row ``row``'s clip (event "info_<row>"), tagged with its ``PALETTE``
    colour and its approach ("instrumental", "textural" or "hybrid"). Name it by what it
    feels or sounds like ("Low cello swell", "Felt drum and air", "Single bell, far off")."""
    if colour_ not in PALETTE:
        raise KeyError("unknown colour %r: %s" % (colour_, ", ".join(PALETTE)))
    if approach is not None and approach not in APPROACHES:
        raise KeyError("approach: %s" % ", ".join(APPROACHES))
    t = [colour_] + ([approach] if approach else []) + [x for x in tags if x not in (colour_, approach)]
    return IC.info(row, cid, title, note, render, t)


# ============================================================================= the emotion palette
@dataclass(frozen=True)
class Colour:
    name: str
    feeling: str
    sources: Tuple[str, ...]
    register: str
    dynamics: str
    intervals: str
    room: str
    avoid: str
    sketches: Tuple[str, str, str]      # instrumental, textural, hybrid (each a stinger(...) call)


PALETTE: Dict[str, Colour] = {c.name: c for c in [
    Colour("neutral", "your move: a quiet marker that something is ready, no judgement",
           ("harp", "lute", "knock (felt)", "cards rustle", "breath", "small bell far off"),
           "middle: D4-A5, above the music's drones",
           "one soft onset, then a natural ring; the quietest colour",
           "a single D or A; the octave at most", "near or tavern",
           "swells that ask for attention, low notes, any minor colour",
           ('stinger(strike("harp", "A4", vel=56), room="near")',
            'stinger(rustle(0.6, "cards"), air(2.0, bright=0.4, start_db=-10).db(-10), room="hall")',
            'stinger(strike("lute", "D4", vel=60, hold=1.8), breath(0.8).at(0.04).db(-14), room="hall")')),
    Colour("weariness", "a sigh, a weight set down: a turn given up, a hand thinned",
           ("cello or viola falling slide", "breath (sigh)", "felt drum", "low harp"),
           "low-middle: A3 falling to D3, D4",
           "falling: a firm start that sinks away; no accent after the start",
           "a falling fifth A to D or fourth D to A; a slide down", "hall",
           "rising gestures, bright bells, anything quick",
           ('stinger(slide("cello", "A3", "D3", dur=1.4, glide=(0.25, 0.8)), room="hall")',
            'stinger(hit("felt_drum", vel=64), breath(1.1, "sigh").at(0.03).db(-3), room="hall")',
            'stinger(strike("harp", "A3", vel=62), slide("viola", "D4", "A3", dur=1.2).at(0.12).db(-5), room="hall")')),
    Colour("relief", "the blow does not land: breath let out, shoulders drop",
           ("strings or choir open fifth", "breath (out)", "harp", "air"),
           "middle: D4-A4, lifted above the music",
           "a small quick bloom, then a long exhale",
           "the open fifth D-A, the octave", "hall",
           "hits, low weight, minor colour",
           ('stinger(swell("strings", fifth(4), dur=1.6, peak=0.25, start_db=-6, vel=70), room="hall")',
            'stinger(breath(1.2, "out"), air(1.6, bright=0.3).at(0.06).db(-8), room="hall")',
            'stinger(strike("harp", "D4+A4", spread=0.05, vel=66), breath(1.0, "out").at(0.05).db(-6), room="hall")')),
    Colour("warmth", "care from the party: a hand on the shoulder, a hearth",
           ("harp", "lute", "cello (middle)", "horn (soft)", "humming", "embers"),
           "warm middle: D3-A4 (heard through the harmonics, not as a drone)",
           "a gentle bloom: a soft onset that opens, a long ring",
           "the open fifth; a major third (F#*) only as the one colour note", "tavern or hall",
           "brightness, high bells, hits",
           ('stinger(swell("horn", "D4", dur=1.5, peak=0.4, start_db=-7, vel=72), room="hall")',
            'stinger(embers(2.2, crackle=0.7), rustle(0.9, "cloth").at(0.1).db(-8), room="tavern")',
            'stinger(strike("harp", "D4", vel=64), '
            'swell("cello", "A3", dur=1.6, peak=0.5, vel=76).db(-3), room="hall")')),
    Colour("sacred", "stillness, a blessing: a shrine, a chant, a holy shield",
           ("choir (MuseScore)", "church organ (soft)", "hand bell far off", "celesta", "air"),
           "open middle: D4-A5; a bell at D5 or A5",
           "a slow bloom and a long, even ring",
           "the open fifth and the octave only (no third)", "chapel",
           "drums, rubs, anything quick",
           ('stinger(swell("choir", fifth(4), dur=1.7, peak=0.6, start_db=-8, vel=76), room="chapel")',
            'stinger(strike("hand_bell", "D5", vel=62).far(0.4), air(1.8, bright=0.2).db(-12), room="chapel")',
            'stinger(strike("hand_bell", "A4", vel=58), '
            'swell("choir", "D4", dur=1.6, peak=0.6, vel=72).db(-4), room="chapel")')),
    Colour("mystery", "something hidden shows itself: a peek, a deal, a lake, a cave",
           ("celesta", "shakuhachi or flute breathy note", "drips", "sparkle", "air", "a far bell"),
           "high (D5-A6) or far away and dark",
           "soft and suspended: sounds appear and hang",
           "fifth or octave, no third (ambiguous)", "cave or chapel",
           "drums, warm thirds, a clear resolution",
           ('stinger(swell("shakuhachi", "A4", dur=1.5, peak=0.35, start_db=-6, vel=70), room="cave")',
            'stinger(drips(3, spacing=0.45), air(1.8, bright=0.6).db(-12), room="cave")',
            'stinger(strike("celesta", "D6", vel=56), sparkle(1.4, count=8).at(0.08).db(-6), room="chapel")')),
    Colour("mischief", "a trick, a wink: the Jester, a stolen card, a two-faced bard",
           ("tin whistle slide (the Whistle jig's whistle)", "woodblock", "small bell", "tambourine"),
           "high: D5-A6",
           "quick and light: a flick or a bounce; dry",
           "a slide up onto D or A; a rub for a sly grin", "tavern",
           "heavy drums, long swells, dark rooms",
           ('stinger(slide("tin_whistle", "A5", "D6", dur=1.9, glide=(0.03, 0.2), peak=0.22, vel=80), room="tavern")',
            'stinger(hits("tambourine", [(0.0, 84), (0.22, 60)]), '
            'hit("triangle", vel=50).at(0.22).db(-8), room="tavern")',
            'stinger(hit("woodblock", vel=84), '
            'slide("tin_whistle", "D6", "A5", dur=1.8, glide=(0.15, 0.6), peak=0.25).at(0.12).db(-2), room="tavern")')),
    Colour("unease", "the ground shifts: something changed and it is not clear how",
           ("tremolo strings (thin)", "creak", "a rub", "a slide that does not settle", "chains"),
           "thin and high (D5-A5) or a low creak",
           "unstable: tremble, flicker, no clean resolution",
           "the semitone rub D+Eb*; a slide that ends on A", "crypt or near",
           "warm thirds, full resolutions, big hits",
           ('stinger(swell("tremolo_strings", rub(5), dur=1.5, peak=0.4, start_db=-6, vel=70), room="crypt")',
            'stinger(creak(0.9), air(1.6, bright=0.4).at(0.1).db(-10), room="crypt")',
            'stinger(strike("harp", "A4", vel=60), creak(0.8).at(0.12).db(-4), room="crypt")')),
    Colour("dread", "a bane: dark, slow, inevitable",
           ("cello or contrabass low swell", "humming (low)", "felt drum", "rumble", "chains", "a far bell"),
           "low: D3-A3, carried by the cello's or a voice's harmonics (a heavy D2 merges with the music's drone: "
           "over_bed reads it buried); a far bell",
           "a slow swell from under the music; no accent beyond the start",
           "unison or octave; the bane's mark is one colour note: the rub Eb* or the minor third F*", "crypt",
           "brightness, quick notes, major thirds",
           ('stinger(swell("cello", "D3+Eb3*", dur=1.7, peak=0.6, start_db=-7, vel=80), room="crypt")',
            'stinger(hit("felt_drum", vel=96), rumble(1.9, depth=0.6).db(-4), room="crypt")',
            'stinger(strike("hand_bell", "D4", vel=64, damp=1.5, fall=0.8).far(0.6), '
            'swell("cello", "D3", dur=1.6, peak=0.5, start_db=-10).db(-3), room="crypt")')),
    Colour("threat", "the enemy acts: danger aimed at you",
           ("trombone", "tuba", "horn (low, hard)", "timpani", "war drum", "bass drum"),
           "low: D2-D3, weight on purpose, with a brass edge",
           "a sharp onset (a stab) and a heavy fall",
           "unison or octave D; a bare fifth", "hall",
           "thirds, sweetness, high bells",
           ('stinger(swell("trombone", octave(2), dur=1.6, peak=0.06, start_db=-3, vel=104).heavy(), room="hall")',
            'stinger(hit("war_drum", vel=112), '
            'roll("timpani", "D2", dur=1.0, vel=(30, 70)).at(0.12).db(-6), room="hall")',
            'stinger(strike("timpani", "D2", vel=112), '
            'swell("horn", "D3", dur=1.2, peak=0.08, start_db=-4, vel=100).db(-3), room="hall")')),
    Colour("impact", "a blow lands: damage, a strike, a collapse",
           ("bass drum", "war drum", "timpani", "taiko-like skins", "cymbal (soft)", "strings stab"),
           "low with an attack (weight is the point)",
           "one hit, a natural decay, nothing after",
           "none, or a timpani D2 / A2", "hall",
           "sustained notes after the hit, tunes",
           ('stinger(swell("strings", "D3+A3", dur=0.8, peak=0.03, start_db=-2, vel=112), '
            'strike("timpani", "D2", vel=110).db(-2), room="hall")',
            'stinger(hit("bass_drum", vel=118), room="hall")',
            'stinger(hit("war_drum", vel=120), rustle(0.6, "cards").at(0.03).db(-10), room="hall")')),
    Colour("triumph", "the enemy falls: a clean kill, a filled zone",
           ("horn", "timpani", "hand bell", "cymbal swell", "harp"),
           "middle to high: D4-A5, bright",
           "a strong onset and a long, bright ring",
           "the open fifth; a rising fourth A to D", "hall",
           "minor colour, low rumble",
           ('stinger(swell("horn", fifth(4), dur=1.5, peak=0.12, start_db=-3, vel=100), room="hall")',
            'stinger(strike("timpani", "D2", vel=112), '
            'roll("cymbal", dur=1.2, shape="swell", vel=(30, 70)).db(-8), room="hall")',
            'stinger(strike("hand_bell", "D5", vel=80), '
            'swell("horn", "A4", dur=1.4, peak=0.2, vel=96).db(-2), room="hall")')),
    Colour("fortune", "luck turns your way: an Evergreen boon (the boons' shared colour)",
           ("harp roll (bright)", "small bell", "celesta", "sparkle", "recorder"),
           "high: D5-A6, bright",
           "a quick upward roll or shimmer; a clear onset, a light ring",
           "rising D-A, the octave", "hall",
           "low weight, minor colour, drums",
           ('stinger(strike("harp", "D5+A5+D6", spread=0.05, vel=70), room="hall")',
            'stinger(sparkle(1.8, count=10), air(2.0, bright=0.7).db(-12), room="hall")',
            'stinger(strike("small_bell", "A5", vel=66), '
            'swell("recorder", "D5", dur=1.6, peak=0.3, vel=74).db(-4), room="hall")')),
]}

# Each row's suggested colour (docs/info_popups.json: the moment each card shows). A row of
# a shared kind keeps its kind's colour (SHARED) and stays recognisable by its own source.
ROW_COLOUR: Dict[str, str] = {
    "turn": "neutral", "yield": "weariness",
    "corrupted": "dread", "restored": "warmth", "declared": "neutral",
    "kinfolk_flute": "warmth", "scarlet_whistle": "mischief", "azure_emblem": "mystery",
    "mother_corrupt": "dread", "mother_restored": "warmth",
    "jester": "mischief", "jester_claim": "mischief", "solo_jester_refresh": "mischief",
    "solo_jester_attack": "mischief",
    "immunity": "threat", "mage": "mystery", "druid": "mystery", "cleric": "warmth", "bard": "warmth",
    "chanter": "sacred", "reaver": "unease", "warrior": "impact", "paladin": "sacred", "guardian": "relief",
    "damage": "impact", "defeated": "triumph", "exact_kill": "triumph", "cleanup": "neutral", "team_damage": "threat",
    "new_enemy": "threat", "enemy_shift": "unease", "enemy_attack": "threat", "shielded": "relief",
    "feign_death": "relief", "damage_paid": "weariness",
    "hydra_regrows": "threat", "m3_zone": "threat", "m5_zone": "threat", "m5_carry": "impact",
    "m7_pilgrim": "sacred", "m7_match": "mystery", "m8_filled": "triumph", "m9_piles": "warmth",
    "m10_zone": "threat", "m10_cleric": "dread", "m10_bard": "dread",
    "m11_beast": "threat", "m11_beast_H": "threat", "m11_beast_D": "threat", "m11_beast_C": "threat",
    "m11_beast_S": "threat", "m12_zone": "threat",
    "shrine": "sacred", "cave": "mystery", "cave_collapse": "impact", "forest": "mystery", "hills": "mystery",
    "lake": "mystery",
    "bane10": "dread", "bane12": "dread", "bane14": "dread", "bane15": "dread", "bane16": "dread", "bane21": "dread",
    "bane22": "dread", "bane23": "dread",
    "boon30": "fortune", "boon31": "fortune", "boon32": "fortune", "boon33": "fortune", "boon35": "fortune",
}

# The kinds that share one colour, so the owner learns them; each row keeps its own source.
SHARED: Dict[str, Tuple[str, Tuple[str, ...], str]] = {
    "banes": ("dread", ("bane10", "bane12", "bane14", "bane15", "bane16", "bane21", "bane22", "bane23",
                        "m10_cleric", "m10_bard"),
              "dark and low, the crypt room; the bane's mark is its one colour note (the Eb* rub or the F* "
              "minor third) somewhere in the clip, never as a shared opening; each bane its own source "
              "(fire for the Crucible, chains, a creak, a bell, a low voice...)"),
    "boons": ("fortune", ("boon30", "boon31", "boon32", "boon33", "boon35"),
              "bright and high, the hall; a rising D-A or a shimmer; each boon its own source (harp, bells, "
              "recorder, sparkle, air...)"),
    "enemy": ("threat", ("new_enemy", "enemy_attack", "immunity", "team_damage", "hydra_regrows", "m3_zone",
                         "m5_zone", "m10_zone", "m11_beast", "m11_beast_H", "m11_beast_D", "m11_beast_C",
                         "m11_beast_S", "m12_zone"),
              "low brass and skins on D, a stab and a heavy fall; each enemy card its own source (trombone, "
              "tuba, horn, timpani, war drum, bass drum); the beasts by class (Cleric low choir, Bard a "
              "bent horn, Warrior war drum, Paladin trombone and bell)"),
}


def palette_text() -> str:
    """The palette as plain text (``python3 _stingers.py palette``)."""
    lines = []
    for c in PALETTE.values():
        rows = [r for r, k in ROW_COLOUR.items() if k == c.name]
        lines += ["%s: %s" % (c.name.upper(), c.feeling),
                  "  sources    %s" % ", ".join(c.sources),
                  "  register   %s" % c.register,
                  "  dynamics   %s" % c.dynamics,
                  "  intervals  %s" % c.intervals,
                  "  room       %s; avoid: %s" % (c.room, c.avoid),
                  "  rows       %s" % ", ".join(rows)]
        lines += ["  %-12s %s" % (ap, sk) for ap, sk in zip(APPROACHES, c.sketches)]
        lines.append("")
    for kind, (col, rows, how) in SHARED.items():
        lines.append("SHARED %s -> %s: %s" % (kind, col, how))
    return "\n".join(lines)


# ============================================================================= over the music
MUSIC_DB = EVENT_BY_ID["music"].loudness_db       # the music's loudness (the build masters loops to it)


@functools.lru_cache(maxsize=4)
def _bed_cached(seconds: float, seed: int) -> np.ndarray:
    T = seconds + 1.2
    t = np.arange(A.n_of(T)) / SR
    rng = np.random.default_rng(seed)
    # the drone: a low string section on D and A, breathing slowly; a contrabass under it
    drone = _render([IC.n("slow_strings", "D2", 0.0, T, vel=74), IC.n("slow_strings", "A2", 0.0, T, vel=62)], T)
    drone = drone * (1 + 0.22 * np.sin(2 * np.pi * t / 5.3 + 0.4))
    bass = _render([IC.n("contrabass", "D2", 0.0, T, vel=70)], T)
    # a cello sul tasto on D3 and a viola that brings in the minor third: moody D minor
    cello = _render([IC.n("cello", "D3", 0.0, T, vel=58)], T)
    cello = A.lowpass(cello, 1800, 2) * (0.75 + 0.25 * np.sin(2 * np.pi * t / 7.1 + 2.0))
    viola = _render([IC.n("viola", "F3", 2.8, min(3.8, T - 3.0), vel=56)], T)
    viola = viola * np.clip((t - 2.8) / 1.2, 0, 1)
    # the pulse: a soft timpani D every two seconds, felt mallets
    pulse = np.zeros(A.n_of(T))
    k = 0
    while 0.6 + 2.0 * k < T - 0.5:
        s = _from_onset(_render([IC.n("timpani", "D2", 0.0, 0.3, vel=int(52 + rng.integers(-4, 5)))], 2.5))
        pulse = _place(pulse, A.lowpass(s, 900, 2), 0.6 + 2.0 * k)
        k += 1
    mix = (A.pan(IC.to_level(drone, -24), -0.15) + A.pan(IC.to_level(bass, -27), 0.0)
           + A.pan(IC.to_level(cello, -30), -0.4) + A.pan(IC.to_level(viola, -33), 0.4)
           + A.pan(IC.to_level(pulse, -27), 0.1))
    mix = A.reverb(mix, 0.7, 0.22, 0.6, 1.0, 0.0)
    mix = A.highpass(mix, 30, 2)
    mix = mix[:A.n_of(seconds)]
    mix = A.master(mix, MUSIC_DB, -1.0, fade_out=0.0)
    return A.fade(mix, 0.4, 0.5)


def dark_bed(seconds: float = 8.0, seed: int = 0) -> np.ndarray:
    """A test bed in the spirit of the owner's planned mission music: a low string drone
    on D and A breathing slowly over a contrabass, a cello sul tasto on D3, a viola bringing
    in the minor third (F3) at ~3 s, and a soft felt timpani D every 2 s; a stone hall.
    Stereo, ``seconds`` long, at the music's loudness (catalog "music", -21 dB)."""
    return _bed_cached(round(float(seconds), 3), int(seed)).copy()


def master_like_build(raw: np.ndarray, event: Optional[str] = None) -> np.ndarray:
    """``raw`` mastered as build.py masters a candidate of ``event`` (an info pop-up's
    loudness and phone-speaker weighting; default -20 dB like most pop-ups)."""
    import build as B
    ev = EVENT_BY_ID.get(event) if event else None
    loud = ev.loudness_db if ev is not None else -20.0
    x = A.master(A.trim(raw, -70.0, 0.01), loud, -1.0, fade_out=0.008)
    if ev is None or ev.group == "Info pop-ups":
        shift = B.PHONE_K * (B.PHONE_REF - B.phone_offset(x))
        x = A.master(A.trim(raw, -70.0, 0.01), loud + shift, -1.0, fade_out=0.008)
    return x


OCTAVES = (63.0, 125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0)
READS_CLEAR, READS_OK = 8.0, 3.0      # dB of clip over the ducked bed in the clip's main band


def _band_energy(x: np.ndarray) -> np.ndarray:
    if len(x) < 64:
        return np.full(len(OCTAVES), 1e-20)
    w = np.hanning(len(x))
    p = np.abs(np.fft.rfft(x * w)) ** 2
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    return np.array([p[(f >= fc / math.sqrt(2)) & (f < fc * math.sqrt(2))].sum() + 1e-20 for fc in OCTAVES])


def _readability(c: np.ndarray, b: np.ndarray) -> Dict[str, object]:
    """How a clip ``c`` reads over the ducked bed ``b`` (both mono, from the clip's start)."""
    blk = A.n_of(0.05)
    k = max(1, len(c) // blk)
    pc = np.mean(IC.fit(c, k * blk / SR).reshape(k, blk) ** 2, axis=1)
    active = np.nonzero(pc >= pc.max() * 10 ** (-20 / 10.0))[0]
    end = max(A.n_of(0.3), (int(active[-1]) + 1) * blk)
    Ec, Eb = _band_energy(c[:end]), _band_energy(b[:end])
    main = int(np.argmax(Ec))
    # the onset: the best 60 ms in the first 0.15 s, in that moment's own main band (a 30 ms
    # hit averaged over a long window would read weaker than it is heard)
    onset_db = -120.0
    w = A.n_of(0.06)
    for off in (0.0, 0.03, 0.06, 0.09):
        i = A.n_of(off)
        Eco, Ebo = _band_energy(c[i:i + w]), _band_energy(b[i:i + w])
        m = int(np.argmax(Eco))
        onset_db = max(onset_db, 10 * math.log10(Eco[m] / Ebo[m]))
    hi = np.array(OCTAVES) >= 500
    reads = 10 * math.log10(Ec[main] / Eb[main])
    phone = 10 * math.log10(Ec[hi].sum() / Eb[hi].sum())
    verdict = "buried" if reads < READS_OK or phone < 0 else ("faint" if reads < READS_CLEAR else "clear")
    return {
        "band": "%d Hz" % OCTAVES[main],
        "reads_db": round(reads, 1),
        "onset_db": round(onset_db, 1),
        "phone_db": round(phone, 1),
        "broad_db": round(10 * math.log10((np.sum(c[:end] ** 2) + 1e-20) / (np.sum(b[:end] ** 2) + 1e-20)), 1),
        "masked": round(float(Ec[Eb >= Ec].sum() / Ec.sum()), 2),
        "window_s": round(end / SR, 2),
        "verdict": verdict,
    }


def over_bed(clip: np.ndarray, bed: Optional[np.ndarray] = None, at: float = 1.0, duck_db: float = -8.0,
             event: Optional[str] = None, mastered: bool = False, ramp: float = 0.05,
             release: float = 0.4) -> Dict[str, object]:
    """``clip`` over the music as the game plays it: mastered as the build masters it for
    ``event`` (unless ``mastered``: a built .wav), starting ``at`` s into ``bed`` (default
    ``dark_bed``), the bed ducked by ``duck_db`` (about 40%) over ``ramp`` s while the clip
    plays and brought back over ``release`` s. Returns {"mix": stereo, "clip": the mastered
    clip, and the readings: band (the clip's main octave band), reads_db (clip over bed in
    it), onset_db (the same for the best 60 ms of the first 0.15 s, in that moment's main
    band), phone_db (above ~350 Hz), broad_db, masked (share of the clip's energy in bands
    the bed covers), verdict (clear >= 8 dB, faint >= 3, else buried; also buried when
    phone_db < 0)}."""
    x = np.asarray(clip, dtype=np.float64)
    if not mastered:
        x = master_like_build(x, event)
    n_clip = len(x)
    if bed is None:
        bed = dark_bed(max(8.0, at + n_clip / SR + 1.5))
    bed = A.stereo(np.asarray(bed, dtype=np.float64)).copy()
    i0 = A.n_of(at)
    total = max(len(bed), i0 + n_clip)
    if len(bed) < total:
        bed = np.concatenate([bed, np.zeros((total - len(bed), 2))])
    g = np.ones(total)
    duck = 10 ** (duck_db / 20.0)
    r = A.n_of(ramp)
    rel = A.n_of(release)
    i1 = i0 + n_clip
    g[i0:i0 + r] = np.linspace(1.0, duck, len(g[i0:i0 + r]))
    g[i0 + r:i1] = duck
    seg = g[i1:i1 + rel]
    g[i1:i1 + rel] = duck + (1 - duck) * (0.5 - 0.5 * np.cos(np.linspace(0, math.pi, len(seg))))
    bed_d = bed * g[:, None]
    mix = bed_d.copy()
    mix[i0:i1] += A.pan(x, 0.0)
    res = _readability(x * math.cos(math.pi / 4), bed_d[i0:i1].mean(axis=1))
    res.update({"mix": mix, "clip": x, "at": at})
    return res


def write_over_bed(base: str, res: Dict[str, object]) -> str:
    """Write ``over_bed``'s mix to ``base``.wav, .mp3 and a spectrogram .png (peaks held
    under -0.5 dB)."""
    mix = A.limit(res["mix"], -0.5)
    A.write_wav(base + ".wav", mix)
    A.write_mp3(base + ".mp3", mix, 128)
    A.spectrogram_png(base + ".png", mix)
    return base + ".wav"


def write_bed(seconds: float = 8.0) -> str:
    """out/_bed/dark_bed.wav and .mp3."""
    os.makedirs(BED_DIR, exist_ok=True)
    x = dark_bed(seconds)
    base = os.path.join(BED_DIR, "dark_bed")
    A.write_wav(base + ".wav", x)
    A.write_mp3(base + ".mp3", x, 128)
    A.spectrogram_png(base + ".png", x)
    return base + ".wav"


def _fmt(res: Dict[str, object]) -> str:
    return "%-7s band %-7s reads %+5.1f  onset %+5.1f  phone %+5.1f  broad %+5.1f  masked %.2f" % (
        res["verdict"], res["band"], res["reads_db"], res["onset_db"], res["phone_db"], res["broad_db"], res["masked"])


def _main(argv: Sequence[str]) -> int:
    if not argv:
        print("wrote", write_bed())
        return 0
    cmd, rest = argv[0], list(argv[1:])
    if cmd == "palette":
        print(palette_text())
        return 0
    if cmd == "sketches":
        ns = {k: globals()[k] for k in __all__}
        bad = 0
        for c in PALETTE.values():
            for ap, sk in zip(APPROACHES, c.sketches):
                try:
                    y = eval(sk, ns)  # the palette's own code strings
                    res = over_bed(y)
                    print("  %-9s %-12s %.2fs onset %5.1f end %5.1f | %s | %s" % (
                        c.name, ap, len(y) / SR, LAST["onset_db"], LAST["end_db"], _fmt(res), sk))
                except Exception as e:  # report and go on: this is a survey
                    bad += 1
                    print("!! %-9s %-12s %s | %s" % (c.name, ap, e, sk))
        print("%d sketches failed" % bad)
        return 1 if bad else 0
    if cmd == "over":
        import build as B
        import _stingers as imported     # the families' instance (run as a script, this module is __main__)
        last = imported.LAST
        openings: Dict[tuple, List[str]] = {}
        for name_, mod in B.family_modules(rest):
            for c in getattr(mod, "CANDIDATES", []):
                last.clear()
                raw = c.render()
                res = over_bed(raw, event=c.event)
                d = os.path.join(BED_DIR, c.event)
                os.makedirs(d, exist_ok=True)
                write_over_bed(os.path.join(d, c.id), res)
                op = last.get("opening")
                if op:
                    openings.setdefault(op, []).append(c.key())
                print("%-40s %s | %s" % (c.key(), _fmt(res), " + ".join(last.get("layers", [])) or "?"))
        shared = {k: v for k, v in openings.items() if len(v) > 1}
        if shared:
            print("\nshared openings (source, gesture, first pitch):")
            for k, v in sorted(shared.items(), key=lambda kv: -len(kv[1])):
                print("  %-40s %d: %s" % (" ".join(str(x) for x in k if x), len(v), ", ".join(v)))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
