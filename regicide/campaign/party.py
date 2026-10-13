"""The persistent party deck (card dicts) and the sticker-like edits applied to it."""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence

from ..cards import BASIC_SUITS, CLUBS, NUMBER_RANKS, RANK_VALUE, Card

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


def corruption_candidates(party: Sequence[CardDict]) -> List[str]:
    """Party cards that may be corrupted now (the reward card says "corrupt a character
    in your party": the player chooses).

    The constraints follow the fan implementation until pack C's corruption rules card
    is read: basic cards of strength 2–9 only, never repeat a strength, never the same
    class more than twice, and the 6 is always Esme, the 6 of Warriors (clubs), with one
    clubs slot kept free for her until she is corrupted.
    """
    used_ranks = set()
    suit_count: Dict[str, int] = {}
    for c in party:
        if "corrupted" in c.get("flags", []):
            used_ranks.add(c["rank"])
            for s in c.get("suits", []):
                suit_count[s] = suit_count.get(s, 0) + 1
    six_done = "6" in used_ranks
    candidates = []
    for c in party:
        if c.get("name") or "corrupted" in c.get("flags", []):
            continue
        if c["rank"] not in ("2", "3", "4", "5", "6", "7", "8", "9"):
            continue
        suits = c.get("suits", [])
        if not suits or suits[0] not in BASIC_SUITS:
            continue
        if c["rank"] in used_ranks:
            continue
        if c["rank"] == "6" and suits[0] != CLUBS:
            continue
        limit = 1 if (suits[0] == CLUBS and not six_done and c["rank"] != "6") else 2
        if suit_count.get(suits[0], 0) >= limit:
            continue
        candidates.append(str(c["id"]))
    return sorted(candidates)


def pick_corruption_target(party: Sequence[CardDict], rng: random.Random) -> Optional[str]:
    """A random corruption candidate (used by tests and bots); None when nothing qualifies."""
    candidates = corruption_candidates(party)
    if not candidates:
        return None
    return rng.choice(candidates)
