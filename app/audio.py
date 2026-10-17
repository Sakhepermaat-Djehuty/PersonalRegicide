"""Sound effects and music, through Pythonista's ``sound`` module.

The files live in app/sounds/: ``effects/<event>.wav`` for each sound effect and jingle
(the events of tools/audio/catalog.py) and ``music/<slot>.m4a`` for the music of the menus,
the table and the last enemies ("menu", "table", "boss"). A missing file is silence, so the
game runs the same with none of them.

Settings (App.settings): "sound_effects" and "music" switch each on or off (both on by
default); "sound_in_silent_mode" (on by default) plays even when the phone's ring/silent
switch is on silent, which Pythonista otherwise honours.

What one game action does can make several sounds (a play, its power, the damage, the next
enemy...): ``game_events`` spaces them out in the order they happen.
"""
from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Sequence

SOUNDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
MUSIC_SLOTS = ("menu", "table", "boss")

# The order of a turn's sounds and the gap before each (seconds after the action).
STEPS = [("play", 0.0), ("power", 0.18), ("strike", 0.42), ("jester", 0.0), ("yield", 0.0),
         ("discard", 0.0), ("draw", 0.55), ("new_enemy", 0.95), ("suffer", 1.15), ("end", 0.6)]


def sounds_for(events: Sequence[dict]) -> List[tuple]:
    """(delay, sound event) for what an action did, from the engine's last_events: one
    sound per step at most, in the order the table plays them."""
    steps: Dict[str, str] = {}
    defeated = False
    for ev in events:
        t = ev.get("t")
        if t == "play" or t == "add_to_play":
            steps.setdefault("play", "play")
        elif t == "power":
            if ev.get("immune"):
                steps.setdefault("power", "power_blocked")
            elif ev.get("healed"):
                steps.setdefault("power", "power_heal")
            elif ev.get("doubled"):
                steps.setdefault("power", "power_double")
            elif ev.get("shield"):
                steps.setdefault("power", "power_shield")
            elif ev.get("drawn"):
                steps.setdefault("draw", "draw")
        elif t == "damage":
            steps.setdefault("strike", "hit")
        elif t == "defeat":
            defeated = True
            steps["strike"] = "exact_kill" if ev.get("exact") else "defeat_enemy"
        elif t == "reveal":
            steps.setdefault("new_enemy", "new_enemy")
        elif t == "suffer_due":
            steps.setdefault("suffer", "suffer")
        elif t == "suffer":
            steps.setdefault("discard", "discard")
        elif t in ("jester", "solo_jester"):
            steps.setdefault("jester", "jester")
        elif t == "yield":
            steps.setdefault("yield", "yield")
        elif t == "draw":
            steps.setdefault("draw", "draw")
        elif t == "won":
            steps["end"] = "victory"
        elif t == "lost":
            steps["end"] = "loss"
    if "end" in steps:
        # the game is over: the last blow, then the jingle; nothing about a next turn
        steps.pop("new_enemy", None)
        steps.pop("suffer", None)
    out = []
    for name, delay in STEPS:
        if name in steps:
            if name == "new_enemy" and not defeated:
                delay = 0.0        # the first enemy of a game, or one revealed on its own
            out.append((delay, steps[name]))
    return out


class Audio:
    def __init__(self, settings: dict, delay: Optional[Callable[[Callable[[], None], float], None]] = None) -> None:
        self.settings = settings
        self.delay = delay
        self.player = None
        self.slot: Optional[str] = None
        try:
            import sound  # Pythonista (or the tests' stand-in)
            self.sound = sound
        except ImportError:
            self.sound = None
        self.apply_settings()

    # ------------------------------------------------------------------ settings
    def on(self, key: str) -> bool:
        return bool(self.settings.get(key, True))

    def apply_settings(self) -> None:
        if self.sound is None:
            return
        try:
            self.sound.set_honors_silent_switch(not self.on("sound_in_silent_mode"))
        except Exception:
            pass
        if not self.on("music"):
            self.stop_music()

    # ------------------------------------------------------------------ effects
    @staticmethod
    def effect_path(event: str) -> str:
        return os.path.join(SOUNDS, "effects", event + ".wav")

    def effect(self, event: str, delay: float = 0.0) -> None:
        """Play a sound effect (or a jingle) now, or after ``delay`` seconds."""
        if self.sound is None or not self.on("sound_effects"):
            return
        path = self.effect_path(event)
        if not os.path.exists(path):
            return
        if delay > 0 and self.delay is not None:
            self.delay(lambda: self._play(path), delay)
        else:
            self._play(path)

    def _play(self, path: str) -> None:
        try:
            self.sound.play_effect(path, 0.8)
        except Exception:
            pass

    def game_events(self, events: Sequence[dict]) -> None:
        for delay, name in sounds_for(events):
            self.effect(name, delay)

    # ------------------------------------------------------------------ music
    @staticmethod
    def music_path(slot: str) -> str:
        return os.path.join(SOUNDS, "music", slot + ".m4a")

    def music(self, slot: Optional[str]) -> None:
        """Play the music for ``slot`` ("menu", "table", "boss"; None: none), looping. The
        same slot keeps playing; another changes the track."""
        if self.sound is None or not self.on("music") or slot is None:
            self.stop_music()
            return
        if slot == self.slot and self.player is not None:
            return
        path = self.music_path(slot)
        self.stop_music()
        if not os.path.exists(path):
            return
        try:
            p = self.sound.Player(path)
            p.number_of_loops = -1
            p.play()
        except Exception:
            return
        self.player, self.slot = p, slot

    def stop_music(self) -> None:
        if self.player is not None:
            try:
                self.player.stop()
            except Exception:
                pass
        self.player, self.slot = None, None
