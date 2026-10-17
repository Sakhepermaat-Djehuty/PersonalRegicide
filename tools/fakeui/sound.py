"""Fake ``sound`` module (Pythonista's), for tests: nothing is heard; every call is recorded
in ``history`` as a tuple, e.g. ("effect", path, volume), ("play", path), ("stop", path)."""
from __future__ import annotations

from typing import List, Optional

history: List[tuple] = []
honors_silent_switch = [True]
volume = [0.5]


class Effect:
    def __init__(self, name: str) -> None:
        self.name = name
        self.looping = False


def play_effect(name: str, volume: float = 0.5, pitch: float = 1.0, pan: float = 0.0,
                looping: bool = False) -> Optional[Effect]:
    history.append(("effect", name, round(float(volume), 3)))
    return Effect(name)


def stop_effect(effect: Effect) -> None:
    history.append(("stop_effect", getattr(effect, "name", None)))


def stop_all_effects() -> None:
    history.append(("stop_all_effects",))


def set_volume(v: float) -> None:
    volume[0] = float(v)
    history.append(("set_volume", round(float(v), 3)))


def set_honors_silent_switch(flag: bool) -> None:
    honors_silent_switch[0] = bool(flag)
    history.append(("honors_silent_switch", bool(flag)))


class Player:
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.number_of_loops = 0
        self.current_time = 0.0
        self.duration = 0.0
        self.volume = 1.0
        self.playing = False
        history.append(("player", file_path))

    def play(self) -> None:
        self.playing = True
        history.append(("play", self.file_path, self.number_of_loops))

    def pause(self) -> None:
        self.playing = False
        history.append(("pause", self.file_path))

    def stop(self) -> None:
        self.playing = False
        history.append(("stop", self.file_path))
