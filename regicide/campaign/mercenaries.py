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


# Names read from the cards: Hella (12, paladin), Zimis & Ora (2/5, clerics), Bristle and
# Thistle (Wild Animals), Raki and Taitonga (19s), Nelle and Xam (Jesters). The other 12s
# and 2/5s were fanned behind and keep a generic name.
_TWELVE_NAMES = {"H": "Gi…", "D": "Bard 12", "C": "Warrior 12", "S": "Hella"}
_TWOFIVE_NAMES = {"H": "Zimis & Ora", "D": "Bard pair", "C": "Warrior pair", "S": "Paladin pair"}
for _s, _n in (("H", "Cleric"), ("D", "Bard"), ("C", "Warrior"), ("S", "Paladin")):
    _add("merc_12%s" % _s, "%s (12, %s)" % (_TWELVE_NAMES[_s], _n), 1,
         {"id": "M12%s" % _s, "rank": "12", "suits": [_s], "value": 12, "name": _TWELVE_NAMES[_s],
          "subtitle": "%s Mercenary" % _n, "flags": ["mercenary"]})
for _s, _n in (("H", "Cleric"), ("D", "Bard"), ("C", "Warrior"), ("S", "Paladin")):
    _add("merc_25%s" % _s, "%s (2/5, %ss)" % (_TWOFIVE_NAMES[_s], _n), 1,
         {"id": "M25%s" % _s, "rank": "2", "suits": [_s], "value": 2, "name": _TWOFIVE_NAMES[_s],
          "subtitle": "%s Mercenaries" % _n, "flags": ["mercenary", "twofive"]})
for _i, _n, _sub in ((1, "Raki", "Mountain Warden"), (2, "Taitonga", "Forest Warden")):
    _add("merc_19_%d" % _i, "%s (19, no class)" % _n, 3,
         {"id": "M19_%d" % _i, "rank": "19", "suits": [], "value": 19, "name": _n,
          "subtitle": "%s Mercenary" % _sub, "flags": ["mercenary"]})
for _i, _n in ((1, "Bristle"), (2, "Thistle")):
    _add("merc_ace_%d" % _i, "%s (Wild Animal, choose class)" % _n, 3,
         {"id": "MA_%d" % _i, "rank": "A", "suits": [], "value": 1, "name": _n,
          "subtitle": "Wild Animal Mercenary", "flags": ["mercenary", "choosable"]})
for _i, _n in ((1, "Nelle"), (2, "Xam")):
    _add("merc_jester_%d" % _i, "%s (Jester)" % _n, 5,
         {"id": "MX_%d" % _i, "rank": "X", "suits": [], "value": 0, "name": _n,
          "subtitle": "Jester Mercenary", "flags": ["mercenary"]})


def by_id(mid: str) -> Dict[str, object]:
    for m in MERCENARIES:
        if m["id"] == mid:
            return m
    raise KeyError(mid)
