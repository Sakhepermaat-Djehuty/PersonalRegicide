"""Pack M: mercenaries hired with coins after losses (confirmed from the owner's cards).

Mercenary rules card: "When you fail a mission, you gain coins equal to the number of
losses you've had for this mission. You can use those coins to hire mercenaries to join
you on your next attempt. You may also swap any mercenaries currently in your deck with
other mercenaries of the same cost. When you successfully complete a mission, all the
mercenaries you've hired will return to the mercenary box. As you have just tasted
defeat, you may spend 1 coin now!"

Costs are printed as coins in the top-right corner: 12s and 2/5s cost 1, 19s and Wild
Animals cost 3, Jesters cost 5. Wild Animals show all four class icons and declare one
class when they enter a playmat (rulebook p.25); 2/5s declare 2 or 5 the same way.
"""
from __future__ import annotations

from typing import Dict, List

MERCENARIES: List[Dict[str, object]] = []


def _add(mid: str, name: str, cost: int, card: Dict[str, object]) -> None:
    MERCENARIES.append({"id": mid, "name": name, "cost": cost, "card": card})


# The app plays a themeless deck (owner's choice), so mercenaries are plain cards named by
# what they are. (The physical cards are named: Hella the paladin 12, Zimis & Ora the
# cleric 2/5s, Raki and Taitonga the 19s, Bristle and Thistle the Wild Animals, Nelle
# and Xam the Jesters.)
for _s, _n in (("H", "Cleric"), ("D", "Bard"), ("C", "Warrior"), ("S", "Paladin")):
    _add("merc_12%s" % _s, "12 %s" % _n, 1,
         {"id": "M12%s" % _s, "rank": "12", "suits": [_s], "value": 12, "flags": ["mercenary"]})
for _s, _n in (("H", "Cleric"), ("D", "Bard"), ("C", "Warrior"), ("S", "Paladin")):
    _add("merc_25%s" % _s, "2/5 %s" % _n, 1,
         {"id": "M25%s" % _s, "rank": "2", "suits": [_s], "value": 2, "flags": ["mercenary", "twofive"]})
for _i in (1, 2):
    _add("merc_19_%d" % _i, "19 (no class)", 3,
         {"id": "M19_%d" % _i, "rank": "19", "suits": [], "value": 19, "flags": ["mercenary"]})
for _i in (1, 2):
    _add("merc_ace_%d" % _i, "Wild Animal (choose a class)", 3,
         {"id": "MA_%d" % _i, "rank": "A", "suits": [], "value": 1, "flags": ["mercenary", "choosable"]})
for _i in (1, 2):
    _add("merc_jester_%d" % _i, "Jester", 5,
         {"id": "MX_%d" % _i, "rank": "X", "suits": [], "value": 0, "flags": ["mercenary"]})


def by_id(mid: str) -> Dict[str, object]:
    for m in MERCENARIES:
        if m["id"] == mid:
            return m
    raise KeyError(mid)
