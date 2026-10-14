"""The relics' names and card texts (confirmed from the owner's photos; both sides).

Each relic card has a side for two or more players and a solo side; the restored Evergreen
Mother reads the same on both. The engine implements them in ``legacy_rules.py``; this
module only names and explains them for the app (deck list, rules card, reward lines).
"""
from __future__ import annotations

from typing import Dict, List

RELICS: Dict[str, Dict[str, object]] = {
    "flute": {
        "symbol": "♪", "color": "#c9a227", "name": "Kinfolk Flute", "mission": 1,
        "team": "After you form an attack (before proceeding to Step 2), other players may add cards from "
                "their hand to the attack, as long as the added cards form a valid Kinfolk Attack. Animal "
                "Companions may not be added this way as they cannot be a part of Kinfolk Attacks.",
        "solo": "Once per turn at any time you may put a 2, 3, 4 or 5 from hand here as long as there are no "
                "other cards of a different strength already here. While forming a Kinfolk Attack you may "
                "play cards from here as though they were from your hand.",
    },
    "whistle": {
        "symbol": "♬", "color": "#c0392b", "name": "Scarlet Whistle", "mission": 4,
        "team": "After you form an attack with a solitary Animal Companion or Beast, one other player may add "
                "any card from their hand to the attack (except a Jester). This must be done before "
                "proceeding to Step 2.",
        "solo": "When you form an attack with a solitary animal companion or beast you may take the top card "
                "of the discard pile and add it to the attack.",
    },
    "emblem": {
        "symbol": "◈", "color": "#2f6fc0", "name": "Azure Emblem", "mission": 6,
        "team": "When you form an attack with a mage, before peeking at any cards, each other player may place "
                "one card from their hand on the top of the reserve deck. This power only happens once per "
                "attack: if you use a mage to add an additional mage to an attack, this relic power does not "
                "happen another time.",
        "solo": "When resolving a mage class ability, after selecting a card to be added to the attack, you may "
                "put one of the other cards you looked at on top of the reserve deck before discarding the rest.",
    },
    "mother": {
        "symbol": "❦", "color": "#9440c8", "name": "Evergreen Mother (corrupt)", "mission": 9,
        "team": "Whenever a corrupted card enters play, instead of banishing a card from the top of the reserve "
                "deck, another player must banish a card from their hand. If all other players' hands are "
                "empty, do not banish any card.",
        "solo": "Whenever a corrupted card enters play, if the discard pile is not empty, you may choose to "
                "banish a card from the top of the discard pile instead of the reserve deck.",
    },
    "mother_restored": {
        "symbol": "❦", "color": "#21b05f", "name": "Evergreen Mother (restored)", "mission": 12,
        "team": "Restored cards can never enter the banished pile. If they would, instead put them on the "
                "bottom of the reserve deck.",
        "solo": "Restored cards can never enter the banished pile. If they would, instead put them on the "
                "bottom of the reserve deck.",
    },
}


def relic_name(relic_id: str) -> str:
    return str(RELICS.get(relic_id, {}).get("name", relic_id))


def relic_text(relic_id: str, players: int) -> str:
    """The side of the relic card that applies: solo for one player, else the team side."""
    r = RELICS.get(relic_id)
    if r is None:
        return ""
    return str(r["solo" if int(players) == 1 else "team"])


def relic_lines(relic_ids: List[str], players: int) -> List[str]:
    """"Name: text" for each relic held, in the order they were gained."""
    return ["%s: %s" % (relic_name(r), relic_text(r, players)) for r in relic_ids if r in RELICS]
