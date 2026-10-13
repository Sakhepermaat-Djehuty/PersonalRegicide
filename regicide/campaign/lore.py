"""Lore entries revealed as a campaign progresses.

The texts here are short in-world summaries written for this app, not the story
cards. To use the real card text privately, create ``lore_private.json`` next to your
saves (see app/store.py ``lore_overlay_path``) with ``{"<entry id>": {"text": "...",
"title": "..."}}``; it overrides these entries and is never committed.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from .missions import MISSIONS

_LORE: List[Dict[str, str]] = [
    {"id": "campaign_start", "mission": 0, "title": "The Golden Blade Syndicate",
     "text": "A corruption spreads over Deccaria and the royalty has succumbed to its maddening "
             "haze. The High Crown Council calls on the Golden Blade Syndicate, forty professional "
             "adventurers, to find out where the blight comes from and stop it."},
]
for _m in MISSIONS:
    _LORE.append({"id": "m%d_intro" % _m["number"], "mission": _m["number"],
                  "title": "Mission %d: %s" % (_m["number"], _m["title"]),
                  "text": "%s. %s" % (_m["location"].capitalize() if _m["location"] != "unknown" else "Location unknown",
                                      _m["summary"])})
    _LORE.append({"id": "m%d_outcome" % _m["number"], "mission": _m["number"],
                  "title": "After mission %d" % _m["number"],
                  "text": _m["rewards_text"]})
_LORE.append({"id": "pack_m", "mission": 0, "title": "Pack M: the mercenary camp",
              "text": "Losing a mission is expected. Each failure brings coins, and mercenaries with "
                      "fat stats and some flexibility can be hired for the next attempt. They never stay."})
_LORE.append({"id": "campaign_end", "mission": 13, "title": "Eternal mode",
              "text": "The campaign is complete. The party you built can keep adventuring in "
                      "generated missions."})


def entries(overlay_path: Optional[str] = None) -> List[Dict[str, str]]:
    """All lore entries in order, with the private overlay applied when present."""
    out = [dict(e) for e in _LORE]
    if overlay_path and os.path.exists(overlay_path):
        try:
            with open(overlay_path) as f:
                overlay = json.load(f)
        except (OSError, ValueError):
            overlay = {}
        by_id = {e["id"]: e for e in out}
        for eid, data in overlay.items():
            if not isinstance(data, dict):
                continue
            if eid in by_id:
                by_id[eid].update({k: str(v) for k, v in data.items() if k in ("title", "text")})
            else:
                out.append({"id": eid, "mission": int(data.get("mission", 0)),
                            "title": str(data.get("title", eid)), "text": str(data.get("text", ""))})
    return out


def entry(entry_id: str, overlay_path: Optional[str] = None) -> Optional[Dict[str, str]]:
    for e in entries(overlay_path):
        if e["id"] == entry_id:
            return e
    return None
