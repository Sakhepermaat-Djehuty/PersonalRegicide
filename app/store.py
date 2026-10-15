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


# ---------------------------------------------------------------------------- campaigns
# Each campaign ("game") lives in its own slot folder: campaigns/<slot>/campaign.json plus
# attempt.json for an attempt in progress. Lore unlocked anywhere is also remembered in
# lore_seen.json at the save root so it survives deleting a game.
import re
import glob
import shutil

LEGACY_CAMPAIGN = "campaign.json"
LEGACY_CAMPAIGN_GAME = "campaign_attempt.json"
GLOBAL_LORE = "lore_seen.json"
LORE_OVERLAY = "lore_private.json"


def campaigns_dir() -> str:
    d = os.path.join(save_dir(), "campaigns")
    os.makedirs(d, exist_ok=True)
    _migrate_single_campaign(d)
    return d


def _migrate_single_campaign(d: str) -> None:
    old = _path(LEGACY_CAMPAIGN)
    if not os.path.exists(old):
        return
    try:
        with open(old) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    slot = data.get("slot") or new_slot_id(data.get("name") or "Campaign")
    data["slot"] = slot
    sd = os.path.join(d, slot)
    os.makedirs(sd, exist_ok=True)
    _atomic_write(os.path.join(sd, "campaign.json"), json.dumps(data, indent=1))
    os.remove(old)
    old_game = _path(LEGACY_CAMPAIGN_GAME)
    if os.path.exists(old_game):
        os.replace(old_game, os.path.join(sd, "attempt.json"))


def new_slot_id(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "campaign"
    d = os.path.join(save_dir(), "campaigns")
    os.makedirs(d, exist_ok=True)
    slot = base
    n = 2
    while os.path.exists(os.path.join(d, slot)):
        slot = "%s-%d" % (base, n)
        n += 1
    return slot


def slot_dir(slot: str) -> str:
    d = os.path.join(campaigns_dir(), slot)
    os.makedirs(d, exist_ok=True)
    return d


def attempt_path(slot: str) -> str:
    return os.path.join(slot_dir(slot), "attempt.json")


def list_campaigns() -> List[dict]:
    out: List[dict] = []
    for cp in glob.glob(os.path.join(campaigns_dir(), "*", "campaign.json")):
        try:
            with open(cp) as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        slot = os.path.basename(os.path.dirname(cp))
        out.append({
            "slot": slot, "name": d.get("name", slot), "players": d.get("players", 1),
            "mission": d.get("mission", 1), "finished": bool(d.get("finished")),
            "last_played": d.get("last_played", d.get("created", "")),
            "has_attempt": os.path.exists(attempt_path(slot)),
        })
    out.sort(key=lambda r: r["last_played"], reverse=True)
    return out


def save_campaign(camp) -> None:
    if not camp.slot:
        camp.slot = new_slot_id(camp.name)
    _atomic_write(os.path.join(slot_dir(camp.slot), "campaign.json"), json.dumps(camp.to_dict(), indent=1))
    add_global_lore(camp.lore_seen)


def load_campaign(slot: Optional[str] = None):
    from regicide.campaign import CampaignState
    if slot is None:
        rows = list_campaigns()
        if not rows:
            return None
        slot = rows[0]["slot"]
    try:
        with open(os.path.join(campaigns_dir(), slot, "campaign.json")) as f:
            c = CampaignState.from_dict(json.load(f))
            c.slot = slot
            return c
    except (OSError, ValueError, KeyError):
        return None


def has_campaign(slot: Optional[str] = None) -> bool:
    if slot is None:
        return bool(list_campaigns())
    return os.path.exists(os.path.join(campaigns_dir(), slot, "campaign.json"))


def delete_campaign(slot: str) -> None:
    import shutil
    d = os.path.join(campaigns_dir(), slot)
    if os.path.isdir(d):
        shutil.rmtree(d)


def save_attempt(game: Game, slot: str) -> None:
    _atomic_write(attempt_path(slot), json.dumps(game.to_dict()))


def load_attempt(slot: str) -> Optional[Game]:
    try:
        with open(attempt_path(slot)) as f:
            game = Game.from_dict(json.load(f))
        # attempts saved before the themeless cards carried names on beasts, class decks,
        # mages, pilgrims and mercenaries; the cards are plain now
        from regicide.campaign import missions as _missions
        _missions.strip_game_names(game)
        # mission 7 attempts saved while the pilgrim ace was wrongly in pack P's deck
        _missions.drop_stray_puppy(game)
        return game
    except (OSError, ValueError, KeyError):
        return None


def has_attempt(slot: str) -> bool:
    return os.path.exists(attempt_path(slot))


def delete_attempt(slot: str) -> None:
    try:
        os.remove(attempt_path(slot))
    except OSError:
        pass


def global_lore_seen() -> List[str]:
    try:
        with open(_path(GLOBAL_LORE)) as f:
            return list(json.load(f))
    except (OSError, ValueError):
        return []


def add_global_lore(ids) -> None:
    seen = global_lore_seen()
    changed = False
    for i in ids:
        if i not in seen:
            seen.append(i)
            changed = True
    if changed:
        _atomic_write(_path(GLOBAL_LORE), json.dumps(seen))


def _lore_candidates() -> List[str]:
    """Folders where a ``lore_private.json`` may have been put by hand: Pythonista's
    Documents root (where an imported file lands, the saves folder's parent), its Inbox
    (files opened "in Pythonista" from another app) and the game folder itself."""
    docs = os.path.dirname(save_dir())
    game = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = []
    for d in (docs, os.path.join(docs, "Inbox"), game):
        if d not in out:
            out.append(d)
    return out


def lore_overlay_path() -> str:
    """The private story text. It lives in the saves folder; a copy found in one of the
    places above is copied there first (so updating the game never loses it)."""
    home = _path(LORE_OVERLAY)
    if os.path.isfile(home):
        return home
    for d in _lore_candidates():
        found = os.path.join(d, LORE_OVERLAY)
        if os.path.isfile(found):
            try:
                with open(found) as f:
                    json.load(f)           # only a readable JSON file is taken
                shutil.copyfile(found, home)
                return home
            except (OSError, ValueError):
                continue
    return home
