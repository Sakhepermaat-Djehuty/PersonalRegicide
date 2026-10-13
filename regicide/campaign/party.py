"""The persistent party deck (card dicts) and the sticker-like edits applied to it."""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence

from ..cards import BASIC_SUITS, NUMBER_RANKS, RANK_VALUE, Card

CardDict = Dict[str, object]


def starting_party() -> List[CardDict]:
    """The Golden Blade Syndicate: A–10 of the four basic classes (40 cards)."""
    out: List[CardDict] = []
    for s in BASIC_SUITS:
        for r in NUMBER_RANKS:
            out.append({"id": r + s, "rank": r, "suits": [s], "value": RANK_VALUE[r], "flags": []})
    return out


def to_card(d: CardDict) -> Card:
    return Card.from_dict(dict(d))


def find(party: Sequence[CardDict], card_id: str) -> Optional[CardDict]:
    for c in party:
        if c["id"] == card_id:
            return c
    return None


def add_flag(party: List[CardDict], card_id: str, flag: str) -> None:
    c = find(party, card_id)
    if c is None:
        raise KeyError(card_id)
    flags = list(c.get("flags", []))
    if flag not in flags:
        flags.append(flag)
    c["flags"] = flags


def remove_flag(party: List[CardDict], card_id: str, flag: str) -> None:
    c = find(party, card_id)
    if c is not None:
        c["flags"] = [f for f in c.get("flags", []) if f != flag]


def add_suit(party: List[CardDict], card_id: str, suit: str) -> None:
    c = find(party, card_id)
    if c is None:
        raise KeyError(card_id)
    suits = list(c.get("suits", []))
    if suit not in suits:
        suits.append(suit)
    c["suits"] = suits


def add_card(party: List[CardDict], card: CardDict) -> None:
    if find(party, str(card["id"])) is not None:
        raise ValueError("duplicate card id %s" % card["id"])
    party.append(dict(card))


def remove_card(party: List[CardDict], card_id: str) -> Optional[CardDict]:
    c = find(party, card_id)
    if c is not None:
        party.remove(c)
    return c


def corrupted_ids(party: Sequence[CardDict]) -> List[str]:
    return [str(c["id"]) for c in party if "corrupted" in c.get("flags", [])]


def pick_corruption_target(party: Sequence[CardDict], rng: random.Random) -> Optional[str]:
    """A random basic card of value 2–9 to corrupt.

    Constraints follow the fan transcription: never repeat a rank, never the same
    class more than twice. (The physical game names the character on a story card;
    this stands in until the owner enters the real one.)
    """
    used_ranks = set()
    suit_count: Dict[str, int] = {}
    for c in party:
        if "corrupted" in c.get("flags", []):
            used_ranks.add(c["rank"])
            for s in c.get("suits", []):
                suit_count[s] = suit_count.get(s, 0) + 1
    candidates = []
    for c in party:
        if c.get("name") or "corrupted" in c.get("flags", []):
            continue
        if c["rank"] not in ("2", "3", "4", "5", "6", "7", "8", "9"):
            continue
        suits = c.get("suits", [])
        if len(suits) != 1 or suits[0] not in BASIC_SUITS:
            continue
        if c["rank"] in used_ranks or suit_count.get(suits[0], 0) >= 2:
            continue
        candidates.append(str(c["id"]))
    if not candidates:
        return None
    return rng.choice(sorted(candidates))
