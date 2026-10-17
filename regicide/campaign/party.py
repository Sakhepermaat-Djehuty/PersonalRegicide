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


def restored_ids(party: Sequence[CardDict]) -> List[str]:
    return [str(c["id"]) for c in party if "restored" in c.get("flags", [])]


TEMPORARY_IDS = ("3R", "7R", "9R", "5G", "7G", "9G", "3U", "5U", "9U", "3T", "5T", "7T")

# Named special characters that pack C never corrupts (owner's decision): Gøran (both
# cards), Myla, the High Arcana, Esme and Ash. Gøran carries no flag before his renewal
# and gains class stickers from mission 5 on, so the id list keeps him out as well.
SPECIAL_IDS = ("GOR8", "GOR8E", "MYLA7", "ARC25", "ESME6E", "B_ASH")

# The original reserve deck: the Golden Blade Syndicate's 40 cards (starting_party), the
# only cards the campaign corrupts. Mission 10 has rules for these as enemies and none
# for corrupted mages or class-deck members (owner's patch; balance to be looked at).
ORIGINAL_IDS = frozenset(r + s for s in BASIC_SUITS for r in NUMBER_RANKS)


def corruption_candidates(party: Sequence[CardDict]) -> List[str]:
    """Party cards that may be corrupted now.

    Pack C (confirmed): a race card is drawn (races go by strength: gnomes 2, halflings
    3, dwarves 4, avions 5, humans 6, elves 7, feltrix 8, drakonids 9) and discarded, then
    a feature card picks one character of that race. The owner plays a themeless deck, so
    the app simply corrupts a random card: one strength among 2 to 9 that has not been
    corrupted yet, then a random card of that strength. Only the original reserve deck
    (the 40 starting cards of the four basic classes, class stickers and all) is eligible,
    never the mages, the class decks or the special characters, and a card already
    corrupted or restored is not corrupted again.
    """
    used_ranks = set(c["rank"] for c in party if "corrupted" in c.get("flags", []))
    candidates = []
    for c in party:
        flags = c.get("flags", [])
        if c["rank"] not in ("2", "3", "4", "5", "6", "7", "8", "9") or c["rank"] in used_ranks:
            continue
        if str(c["id"]) not in ORIGINAL_IDS:
            continue
        if not c.get("suits") or str(c["id"]) in TEMPORARY_IDS or str(c["id"]) in SPECIAL_IDS:
            continue
        if any(f in flags for f in ("corrupted", "restored", "evergreen", "beast", "pilgrim", "mercenary")):
            continue
        candidates.append(str(c["id"]))
    return sorted(candidates)


def pick_corruption_target(party: Sequence[CardDict], rng: random.Random) -> Optional[str]:
    """A random corruption: first a strength (the race card), then a card of that strength
    (the feature card). None when nothing qualifies."""
    candidates = corruption_candidates(party)
    if not candidates:
        return None
    by_rank: Dict[str, List[str]] = {}
    for cid in candidates:
        by_rank.setdefault(find(party, cid)["rank"], []).append(cid)
    rank = rng.choice(sorted(by_rank))
    return rng.choice(sorted(by_rank[rank]))
