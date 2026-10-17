"""Real instrument recordings for the suite: General MIDI notes rendered by FluidSynth from
the MIT-licensed sample banks Ubuntu ships (``apt-get install fluidsynth fluid-soundfont-gm
musescore-general-soundfont-small``; ``pip install mido``):

- ``"fluid"``: FluidR3_GM.sf2, Frank Wen's Fluid bank (MIT), the fuller one;
- ``"musescore"``: MuseScore_General_Lite.sf3 (MIT, built on Fluid), often cleaner.

    from sf import GM, DRUMS, Note, render
    x = render([Note(GM["nylon_guitar"], "D4", 0.00, 0.6, vel=90),
                Note(GM["harp"], "A4", 0.10, 1.2, vel=70, pan=0.3),
                Note(DRUM, DRUMS["tambourine"], 0.25, 0.2, vel=60)], seconds=2.0)

``render`` returns float64 at ``synth.SR``: mono by default (the mean of the bank's stereo),
stereo with ``stereo=True``, at the bank's own level (master it afterwards like any other
sound). It is deterministic. A note's pitch is a name ("D4"), a MIDI number or, for the
drums (``program=DRUM``), a key from ``DRUMS``. Per note: velocity, pan (-1..1), reverb and
chorus sends (0..127; FluidSynth's own room, off by default so the families can use
``synth.reverb``), a pitch bend (``bend``: semitones at the start and the end, glided over
the note: slides, falls) and an expression curve (``swell``: (start, end) 0..127, for bowed
and blown swells). Notes that need their own bend or swell get a channel of their own.
Drum kits: ``kit`` on a drum note picks a General MIDI kit from ``KITS`` (the orchestral kit
has concert bass drums and timpani).

Instrument names below are what the instruments are in the bank; a medieval lute is best
approached by the nylon guitar (or the harp, dulcimer or mandolin-like banjo played softly),
a viol by the cello or viola, a shawm by the oboe, a tabor by the drum keys.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import warnings
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy.io import wavfile

import synth as A

BANKS = {
    "fluid": "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "musescore": "/usr/share/sounds/sf3/MuseScore_General_Lite.sf3",
}

DRUM = -1       # a Note's program for the percussion channel

# General MIDI programs (0-based) worth having for an acoustic, courtly sound.
GM: Dict[str, int] = {
    "piano": 0, "harpsichord": 6, "celesta": 8, "glockenspiel": 9, "music_box": 10, "vibraphone": 11,
    "marimba": 12, "xylophone": 13, "tubular_bells": 14, "dulcimer": 15, "church_organ": 19,
    "reed_organ": 20, "accordion": 21, "nylon_guitar": 24, "steel_guitar": 25, "acoustic_bass": 32,
    "violin": 40, "viola": 41, "cello": 42, "contrabass": 43, "tremolo_strings": 44, "pizzicato": 45,
    "harp": 46, "timpani": 47, "strings": 48, "slow_strings": 49, "choir": 52, "voice_oohs": 53,
    "trumpet": 56, "trombone": 57, "tuba": 58, "french_horn": 60, "brass": 61, "oboe": 68,
    "english_horn": 69, "bassoon": 70, "clarinet": 71, "piccolo": 72, "flute": 73, "recorder": 74,
    "pan_flute": 75, "bottle": 76, "shakuhachi": 77, "whistle": 78, "ocarina": 79, "sitar": 104,
    "banjo": 105, "shamisen": 106, "koto": 107, "kalimba": 108, "bagpipe": 109, "fiddle": 110,
    "shanai": 111, "tinkle_bell": 112, "agogo": 113, "woodblock": 115, "taiko": 116,
    "melodic_tom": 117, "fret_noise": 120, "breath": 121, "seashore": 122, "applause": 126,
}

# General MIDI percussion keys (channel 10).
DRUMS: Dict[str, int] = {
    "bass_drum": 35, "kick": 36, "side_stick": 37, "snare": 38, "hand_clap": 39, "low_floor_tom": 41,
    "closed_hat": 42, "high_floor_tom": 43, "low_tom": 45, "open_hat": 46, "low_mid_tom": 47,
    "hi_mid_tom": 48, "crash": 49, "high_tom": 50, "ride": 51, "chinese_cymbal": 52, "ride_bell": 53,
    "tambourine": 54, "splash": 55, "cowbell": 56, "crash2": 57, "vibraslap": 58, "hi_bongo": 60,
    "low_bongo": 61, "mute_conga": 62, "open_conga": 63, "low_conga": 64, "high_timbale": 65,
    "low_timbale": 66, "high_agogo": 67, "low_agogo": 68, "cabasa": 69, "maracas": 70,
    "short_whistle": 71, "long_whistle": 72, "short_guiro": 73, "long_guiro": 74, "claves": 75,
    "hi_woodblock": 76, "low_woodblock": 77, "mute_cuica": 78, "open_cuica": 79,
    "mute_triangle": 80, "open_triangle": 81,
}

# Drum kits (bank 128 programs). "orchestra": concert bass drum and snare, timpani on keys
# 41-53 (F2..F3), concert cymbals; "brush": soft brushed snare; "room": a smaller live kit.
KITS: Dict[str, int] = {"standard": 0, "room": 8, "power": 16, "brush": 40, "orchestra": 48}

Pitch = Union[str, int]
TICKS = 960                 # per beat; at 120 bpm, 1920 per second
_TPS = TICKS * 2


@dataclass
class Note:
    program: int            # a GM program, or DRUM
    pitch: Pitch            # "D4", a MIDI number, or a DRUMS key / number for DRUM
    start: float            # seconds
    dur: float              # seconds the key is held (the bank's release rings on)
    vel: int = 90           # 1..127
    pan: float = 0.0        # -1 (left) .. 1 (right)
    reverb: int = 0         # FluidSynth reverb send 0..127
    chorus: int = 0         # FluidSynth chorus send 0..127
    bend: Optional[Tuple[float, float]] = None     # semitones at start and end (glided), +-12
    swell: Optional[Tuple[int, int]] = None        # expression at start and end (0..127)
    kit: str = "standard"   # DRUM notes only: a KITS name

    def key(self) -> int:
        if self.program == DRUM:
            return DRUMS[self.pitch] if isinstance(self.pitch, str) else int(self.pitch)
        return A.midi(self.pitch) if isinstance(self.pitch, str) else int(self.pitch)


def _ticks(t: float) -> int:
    return max(0, int(round(t * _TPS)))


def _channels(notes: Sequence[Note]) -> List[Tuple[int, dict, List[Note]]]:
    """Group notes into MIDI channels: one per (program, pan, sends) for plain notes, one
    per note that bends or swells, the drums (per kit) on channel 10."""
    groups: Dict[tuple, List[Note]] = {}
    for i, n in enumerate(notes):
        if n.program == DRUM:
            k = ("drum", n.kit, round(n.pan, 2), n.reverb, n.chorus)
        elif n.bend is not None or n.swell is not None:
            k = ("solo", i)
        else:
            k = ("plain", n.program, round(n.pan, 2), n.reverb, n.chorus)
        groups.setdefault(k, []).append(n)
    drum_groups = [g for k, g in groups.items() if k[0] == "drum"]
    if len(drum_groups) > 1:
        raise ValueError("one drum kit, pan and send per render (render the others separately)")
    melodic = [g for k, g in groups.items() if k[0] != "drum"]
    free = [c for c in range(16) if c != 9]
    out = []
    for g in drum_groups:
        out.append((9, {"program": KITS[g[0].kit], "bank": 128}, g))
    # notes sharing a channel are fine; solo notes that overlap in time may reuse a channel
    # only once the previous one has ended
    plain = [g for g in melodic if g[0].bend is None and g[0].swell is None]
    solos = [g for g in melodic if g[0].bend is not None or g[0].swell is not None]
    if len(plain) > len(free):
        raise ValueError("too many instrument/pan/send combinations in one render")
    for g in plain:
        out.append((free.pop(0), {"program": g[0].program, "bank": 0}, g))
    # solo channels: reuse a channel when its last note (plus a release margin) is over and
    # the program matches; otherwise take a new one
    busy: List[Tuple[int, tuple, float]] = []        # (channel, (program, pan, sends), free_at)
    for g in sorted(solos, key=lambda g: g[0].start):
        n = g[0]
        voice = (n.program, round(n.pan, 2), n.reverb, n.chorus)
        slot = next((b for b in busy if b[1] == voice and b[2] <= n.start), None)
        if slot is not None:
            busy.remove(slot)
            ch = slot[0]
        else:
            if not free:
                raise ValueError("too many overlapping bent or swelling notes in one render")
            ch = free.pop(0)
        busy.append((ch, voice, n.start + n.dur + 1.5))
        out.append((ch, {"program": n.program, "bank": 0}, g))
    return out


def _midi(notes: Sequence[Note], seconds: float, path: str) -> None:
    import mido
    mid = mido.MidiFile(ticks_per_beat=TICKS)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    events: List[Tuple[int, int, object]] = []        # (tick, order, message)
    configured = set()
    channels = _channels(notes)
    solo_channels = set(ch for ch, setup, group in channels
                        if any(n.bend is not None or n.swell is not None for n in group))
    # A key struck again on its channel while still held: the earlier note ends there (a
    # MIDI note-off would otherwise cut the new one short).
    restruck: Dict[int, Dict[tuple, int]] = {}
    held: Dict[tuple, Note] = {}
    for ch, setup, group in channels:
        for n in sorted(group, key=lambda n: n.start):
            k = (ch, n.key())
            prev = held.get(k)
            if prev is not None and _ticks(prev.start + prev.dur) > _ticks(n.start):
                restruck.setdefault(id(prev), {})[k] = max(_ticks(prev.start) + 1, _ticks(n.start) - 1)
            held[k] = n
    for ch, setup, group in channels:
        if ch not in configured:
            configured.add(ch)
            first = group[0]
            events += [(0, 0, mido.Message("control_change", channel=ch, control=0, value=1 if setup["bank"] == 128 else 0)),
                       (0, 0, mido.Message("program_change", channel=ch, program=setup["program"])),
                       (0, 0, mido.Message("control_change", channel=ch, control=10,
                                           value=int(round(64 + 63 * max(-1.0, min(1.0, first.pan)))))),
                       (0, 0, mido.Message("control_change", channel=ch, control=91, value=int(first.reverb))),
                       (0, 0, mido.Message("control_change", channel=ch, control=93, value=int(first.chorus))),
                       # pitch-bend range: 12 semitones
                       (0, 0, mido.Message("control_change", channel=ch, control=101, value=0)),
                       (0, 0, mido.Message("control_change", channel=ch, control=100, value=0)),
                       (0, 0, mido.Message("control_change", channel=ch, control=6, value=12)),
                       (0, 0, mido.Message("control_change", channel=ch, control=38, value=0))]
        for n in group:
            on, off = _ticks(n.start), _ticks(n.start + n.dur)
            if (ch, n.key()) in restruck.get(id(n), {}):
                off = min(off, restruck[id(n)][(ch, n.key())])
            if ch in solo_channels:
                # a reused channel: this note's own start bend and swell, whatever came before
                b0 = n.bend[0] if n.bend is not None else 0.0
                events.append((on, 1, mido.Message("pitchwheel", channel=ch,
                                                   pitch=int(round(max(-8192, min(8191, b0 / 12.0 * 8192)))))))
                events.append((on, 1, mido.Message("control_change", channel=ch, control=11,
                                                   value=int(n.swell[0]) if n.swell is not None else 127)))
            if n.bend is not None:
                b0, b1 = n.bend
                steps = max(1, min(64, (off - on) // 24))
                for s in range(steps + 1):
                    semis = b0 + (b1 - b0) * s / steps
                    val = int(round(max(-8192, min(8191, semis / 12.0 * 8192))))
                    events.append((on + (off - on) * s // steps, 1, mido.Message("pitchwheel", channel=ch, pitch=val)))
            if n.swell is not None:
                e0, e1 = n.swell
                steps = max(1, min(64, (off - on) // 24))
                for s in range(steps + 1):
                    events.append((on + (off - on) * s // steps, 1,
                                   mido.Message("control_change", channel=ch, control=11,
                                                value=int(round(e0 + (e1 - e0) * s / steps)))))
            events.append((on, 2, mido.Message("note_on", channel=ch, note=n.key(), velocity=int(max(1, min(127, n.vel))))))
            events.append((max(off, on + 1), 0, mido.Message("note_off", channel=ch, note=n.key(), velocity=0)))
    end = _ticks(seconds)
    events.append((end, 3, mido.Message("control_change", channel=0, control=110, value=0)))   # the file's length
    events.sort(key=lambda e: (e[0], e[1]))
    now = 0
    for tick, _, msg in events:
        track.append(msg.copy(time=tick - now))
        now = tick
    mid.save(path)


def render(notes: Sequence[Note], seconds: float, bank: str = "fluid", stereo: bool = False,
           gain: float = 0.5, room: float = 0.5, damping: float = 0.4, level: float = 0.9) -> np.ndarray:
    """Render ``notes`` for exactly ``seconds`` (what rings past the end is cut: render a
    little longer and trim, or fold it with ``synth.render_loop`` for music). ``room``,
    ``damping`` and ``level`` set FluidSynth's reverb, heard only through notes' sends."""
    path = BANKS[bank]
    if not os.path.exists(path):
        raise FileNotFoundError("%s: apt-get install fluid-soundfont-gm musescore-general-soundfont-small" % path)
    with tempfile.TemporaryDirectory() as d:
        mid, wav = os.path.join(d, "n.mid"), os.path.join(d, "o.wav")
        _midi(notes, seconds, mid)
        subprocess.run(["fluidsynth", "-ni", "-q", "-g", "%.3f" % gain, "-r", str(A.SR),
                        "-o", "audio.file.format=float", "-o", "synth.chorus.active=1",
                        "-o", "synth.reverb.active=1", "-o", "synth.reverb.room-size=%.3f" % room,
                        "-o", "synth.reverb.damp=%.3f" % damping, "-o", "synth.reverb.level=%.3f" % level,
                        "-o", "synth.cpu-cores=1", "-F", wav, path, mid],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", wavfile.WavFileWarning)   # FluidSynth's float WAV has a fact chunk
            sr, x = wavfile.read(wav)
    x = x.astype(np.float64)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    n = A.n_of(seconds)
    if len(x) < n:
        x = np.concatenate([x, np.zeros((n - len(x), 2))])
    x = x[:n]
    return x if stereo else x.mean(axis=1)


def one(program: int, pitch: Pitch, dur: float = 0.5, vel: int = 90, seconds: Optional[float] = None,
        bank: str = "fluid", **kw) -> np.ndarray:
    """A single note (or drum hit), mono, ``seconds`` long (default: the hold plus 1.5 s)."""
    total = seconds if seconds is not None else dur + 1.5
    return render([Note(program, pitch, 0.0, dur, vel=vel, **kw)], total, bank=bank)


def onset(x: np.ndarray, floor_db: float = -50.0) -> int:
    """The first sample above ``floor_db`` of the peak: the bank's notes start a few ms
    late; cut there so an effect sounds at once on a tap."""
    mono = x if x.ndim == 1 else np.abs(x).max(axis=1)
    peak = float(np.max(np.abs(mono))) or 1.0
    idx = np.nonzero(np.abs(mono) >= peak * 10 ** (floor_db / 20.0))[0]
    return int(idx[0]) if len(idx) else 0
