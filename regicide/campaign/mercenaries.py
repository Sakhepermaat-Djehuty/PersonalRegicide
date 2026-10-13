"""Pack M: mercenaries hired with coins after losses.

Card list is from the physical-contents guide. Costs are NOT known: the values below
are placeholders (tag: unverified) chosen so that one loss buys one modest card and a
run of losses buys the big ones. Edit freely once the real costs are known.
"""
from __future__ import annotations

from typing import Dict, List

MERCENARIES: List[Dict[str, object]] = []


def _add(mid: str, name: str, cost: int, card: Dict[str, object]) -> None:
    MERCENARIES.append({"id": mid, "name": name, "cost": cost, "card": card})


for _s, _n in (("H", "Cleric"), ("D", "Bard"), ("C", "Warrior"), ("S", "Paladin")):
    _add("merc_12%s" % _s, "Mercenary 12 (%s)" % _n, 3,
         {"id": "M12%s" % _s, "rank": "12", "suits": [_s], "value": 12, "name": "Mercenary", "flags": ["mercenary"]})
for _s, _n in (("H", "Cleric"), ("D", "Bard"), ("C", "Warrior"), ("S", "Paladin")):
    _add("merc_25%s" % _s, "Mercenary 2/5 (%s)" % _n, 1,
         {"id": "M25%s" % _s, "rank": "2", "suits": [_s], "value": 2, "name": "2/5", "flags": ["mercenary", "twofive"]})
for _i in (1, 2):
    _add("merc_19_%d" % _i, "Mercenary 19 (no class)", 4,
         {"id": "M19_%d" % _i, "rank": "19", "suits": [], "value": 19, "name": "Mercenary 19", "flags": ["mercenary"]})
for _i in (1, 2):
    _add("merc_ace_%d" % _i, "Mercenary Animal Companion (choose class)", 1,
         {"id": "MA_%d" % _i, "rank": "A", "suits": [], "value": 1, "name": "Companion", "flags": ["mercenary", "choosable"]})
for _i in (1, 2):
    _add("merc_jester_%d" % _i, "Extra Jester", 2,
         {"id": "MX_%d" % _i, "rank": "X", "suits": [], "value": 0, "name": "Jester", "flags": ["mercenary"]})


def by_id(mid: str) -> Dict[str, object]:
    for m in MERCENARIES:
        if m["id"] == mid:
            return m
    raise KeyError(mid)
