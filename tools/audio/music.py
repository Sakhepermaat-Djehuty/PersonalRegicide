"""Helpers for composing the music loops: scales and chords, and a sequencer that places
notes (in beats) for an instrument function.

    from music import Song, scale, chord
    s = Song(bpm=96, beats=64)                       # 16 bars of 4/4: the loop's length
    lute = lambda hz, dur, vel, i: A.pluck(hz, dur + 1.2, 0.45, 1.3, seed=i) * vel
    s.part("lute", lute, [(0, 1, "D4", 0.8), (1, 1, "F4", 0.7), ...], pan=-0.2, gain=0.7)
    s.part("drone", ..., reverb=(0.6, 0.3))
    x = s.render()                                    # stereo, exactly s.seconds long, loops seamlessly

A note is (beat, length in beats, pitch, velocity): pitch a name ("D4"), a MIDI number or a
frequency in Hz (a float above 20 with a fractional part is read as Hz). ``swing`` delays
every off-beat eighth; ``humanize`` nudges onsets and velocities (seeded).
"""
from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple, Union

import numpy as np

import synth as A

MODES = {
    "ionian": [0, 2, 4, 5, 7, 9, 11], "major": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10], "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "aeolian": [0, 2, 3, 5, 7, 8, 10], "minor": [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11], "pentatonic": [0, 2, 4, 7, 9],
    "minor_pentatonic": [0, 3, 5, 7, 10],
}

Pitch = Union[str, int, float]


def hz(p: Pitch) -> float:
    if isinstance(p, str):
        return A.note_hz(p)
    if isinstance(p, float) and p > 20 and p != int(p):
        return p
    return A.note_hz(int(p))


def scale(root: str, mode: str = "dorian", octaves: int = 2) -> List[int]:
    """MIDI numbers of a mode from ``root`` upwards."""
    r = A.midi(root)
    steps = MODES[mode]
    return [r + 12 * o + s for o in range(octaves) for s in steps] + [r + 12 * octaves]


def chord(root: str, kind: str = "minor", inversion: int = 0) -> List[int]:
    shapes = {"major": [0, 4, 7], "minor": [0, 3, 7], "sus2": [0, 2, 7], "sus4": [0, 5, 7],
              "fifth": [0, 7], "dim": [0, 3, 6], "maj7": [0, 4, 7, 11], "min7": [0, 3, 7, 10],
              "dom7": [0, 4, 7, 10], "add9": [0, 4, 7, 14]}
    notes = [A.midi(root) + s for s in shapes[kind]]
    for _ in range(inversion):
        notes = notes[1:] + [notes[0] + 12]
    return notes


class Song:
    def __init__(self, bpm: float, beats: float, tail: float = 4.0, swing: float = 0.0,
                 humanize: float = 0.0, seed: int = 0):
        self.bpm = float(bpm)
        self.beats = float(beats)
        self.tail = tail                 # seconds rendered past the loop, folded back onto its start
        self.swing = swing               # 0..0.33 of a beat's half
        self.humanize = humanize         # seconds of onset jitter
        self.seed = seed
        self.parts: List[Tuple] = []

    @property
    def beat(self) -> float:
        return 60.0 / self.bpm

    @property
    def seconds(self) -> float:
        return self.beats * self.beat

    def at(self, beat: float) -> float:
        b = float(beat)
        frac = b - int(b)
        if self.swing and abs(frac - 0.5) < 1e-6:
            b += self.swing * 0.5
        return b * self.beat

    def part(self, name: str, inst: Callable[[float, float, float, int], np.ndarray],
             notes: Sequence[Tuple[float, float, Pitch, float]], pan: float = 0.0, gain: float = 1.0,
             reverb: Optional[Tuple[float, float]] = None, lowpass: Optional[float] = None) -> "Song":
        """``inst(hz, seconds, velocity, index)`` returns a mono note (it may ring past
        ``seconds``)."""
        self.parts.append((name, inst, list(notes), pan, gain, reverb, lowpass))
        return self

    def render(self) -> np.ndarray:
        total = self.seconds
        rng = np.random.default_rng(self.seed)

        def full() -> np.ndarray:
            mix = A.silence(total + self.tail, 2)
            for name, inst, notes, pan_, gain, rev, lp in self.parts:
                track = A.silence(total + self.tail)
                for i, (b, length, p, vel) in enumerate(notes):
                    t0 = self.at(b) + (rng.uniform(-1, 1) * self.humanize if self.humanize else 0.0)
                    t0 = max(0.0, t0)
                    v = vel * (1 + (rng.uniform(-0.08, 0.08) if self.humanize else 0.0))
                    snd = inst(hz(p), length * self.beat, v, i)
                    track = A.mix_at(track, snd, t0)
                if lp:
                    track = A.lowpass(track, lp)
                st = A.pan(track, pan_)
                if rev:
                    st = A.reverb(st, rev[0], rev[1], tail=0.0)
                n = min(len(mix), len(st))
                mix[:n] += gain * st[:n]
            return mix

        return A.render_loop(full, total)
