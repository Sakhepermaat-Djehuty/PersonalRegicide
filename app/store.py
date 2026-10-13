"""Save files and settings.

On Pythonista everything lives in ``~/Documents/PersonalRegicide-saves`` so that
re-installing the code never touches your games. Elsewhere (tests, desktop) the
``REGICIDE_SAVE_DIR`` environment variable or ``./saves`` is used.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

from regicide.engine import Game


def _is_pythonista() -> bool:
    return sys.platform == "ios" or "Pythonista" in sys.executable


def save_dir() -> str:
    env = os.environ.get("REGICIDE_SAVE_DIR")
    if env:
        d = env
    elif _is_pythonista():
        d = os.path.join(os.path.expanduser("~/Documents"), "PersonalRegicide-saves")
    else:
        d = os.path.join(os.getcwd(), "saves")
    os.makedirs(d, exist_ok=True)
    return d


def _path(name: str) -> str:
    return os.path.join(save_dir(), name)


AUTOSAVE = "current_game.json"
SETTINGS = "settings.json"
HISTORY = "history.jsonl"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "open_hands": False,
    "jester_may_choose_self": True,
    "show_hints": True,
    "names": ["Player 1", "Player 2", "Player 3", "Player 4"],
    "last_players": 1,
}


def load_settings() -> Dict[str, Any]:
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(_path(SETTINGS)) as f:
            s.update(json.load(f))
    except (OSError, ValueError):
        pass
    return s


def save_settings(s: Dict[str, Any]) -> None:
    _atomic_write(_path(SETTINGS), json.dumps(s, indent=1))


def save_game(game: Game, name: str = AUTOSAVE) -> None:
    _atomic_write(_path(name), json.dumps(game.to_dict()))


def load_game(name: str = AUTOSAVE) -> Optional[Game]:
    try:
        with open(_path(name)) as f:
            return Game.from_dict(json.load(f))
    except (OSError, ValueError, KeyError):
        return None


def has_game(name: str = AUTOSAVE) -> bool:
    return os.path.exists(_path(name))


def delete_game(name: str = AUTOSAVE) -> None:
    try:
        os.remove(_path(name))
    except OSError:
        pass


def record_result(game: Game) -> None:
    rec = {
        "when": time.strftime("%Y-%m-%d %H:%M"),
        "players": game.n_players,
        "result": game.result,
        "defeated": game.enemies_defeated,
        "turns": game.turn,
        "jesters_used": game.solo_jesters_used,
        "seed": getattr(game, "seed", None),
    }
    with open(_path(HISTORY), "a") as f:
        f.write(json.dumps(rec) + "\n")


def load_history() -> List[dict]:
    out: List[dict] = []
    try:
        with open(_path(HISTORY)) as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except (OSError, ValueError):
        pass
    return out


def _atomic_write(path: str, text: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)
