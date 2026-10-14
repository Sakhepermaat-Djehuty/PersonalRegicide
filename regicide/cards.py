"""Cards, suits and deck construction.

Cards are immutable values identified by a short id such as ``"7H"`` (seven of hearts),
``"AS"`` (ace of spades), ``"KC"``, ``"X1"`` (first Jester). Legacy adds cards with
several suits, no suit, special names and flags; the same ``Card`` type carries them,
which is why ``suits`` is a tuple and ``flags`` exists already in the base game.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Basic suits. Letters are used in ids and in saves; symbols only for display.
HEARTS, DIAMONDS, CLUBS, SPADES = "H", "D", "C", "S"
BASIC_SUITS: Tuple[str, ...] = (HEARTS, DIAMONDS, CLUBS, SPADES)
MAGE = "M"   # Legacy class the engine itself knows: an attack with a mage is banished

SUIT_SYMBOL: Dict[str, str] = {
    HEARTS: "♥",   # ♥
    DIAMONDS: "♦", # ♦
    CLUBS: "♣",    # ♣
    SPADES: "♠",   # ♠
    # Legacy suits (used from Stage 3 on). Symbols are deliberately plain.
    "M": "★",      # ★ mages
    "R": "⚔",      # ⚔ reavers
    "G": "⛨",      # ⛨ guardians
    "U": "✿",      # ✿ druids
    "T": "♫",      # ♫ drums
}
SUIT_NAME: Dict[str, str] = {
    HEARTS: "Hearts", DIAMONDS: "Diamonds", CLUBS: "Clubs", SPADES: "Spades",
    "M": "Mages", "R": "Reavers", "G": "Guardians", "U": "Druids", "T": "Chanters",
}
# Legacy class names (the rulebook's names for the suits).
CLASS_NAME: Dict[str, str] = {
    HEARTS: "Cleric", DIAMONDS: "Bard", CLUBS: "Warrior", SPADES: "Paladin",
    "M": "Mage", "R": "Reaver", "G": "Guardian", "U": "Druid", "T": "Chanter",
}

NUMBER_RANKS: Tuple[str, ...] = ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10")
ROYAL_RANKS: Tuple[str, ...] = ("J", "Q", "K")
JESTER = "X"

RANK_VALUE: Dict[str, int] = {
    "A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10,
    "J": 10, "Q": 15, "K": 20, JESTER: 0,
}
ROYAL_HEALTH: Dict[str, int] = {"J": 20, "Q": 30, "K": 40}
ROYAL_ATTACK: Dict[str, int] = {"J": 10, "Q": 15, "K": 20}


@dataclass(frozen=True)
class Card:
    id: str
    rank: str
    suits: Tuple[str, ...] = ()
    value: int = 0
    name: str = ""
    flags: Tuple[str, ...] = ()
    attack: int = 0     # enemy cards only (0 = use the royal table)
    health: int = 0     # enemy cards only

    # -- classification -------------------------------------------------
    @property
    def is_jester(self) -> bool:
        return self.rank == JESTER

    @property
    def is_ace(self) -> bool:
        return self.rank == "A"

    @property
    def is_royal(self) -> bool:
        return self.rank in ROYAL_RANKS

    @property
    def is_number(self) -> bool:
        return self.rank in NUMBER_RANKS

    def has(self, flag: str) -> bool:
        return flag in self.flags

    @property
    def defence_value(self) -> int:
        """Value when discarded to suffer damage (Legacy's 2/5 counts as 5)."""
        if self.has("twofive"):
            return 5
        return self.value

    # -- display ----------------------------------------------------------
    @property
    def suit(self) -> Optional[str]:
        """The single suit of a base-game card, or None for suitless / multi-suit."""
        return self.suits[0] if len(self.suits) == 1 else None

    def label(self) -> str:
        if self.is_jester:
            return "Jester"
        if self.name and not self.suits:
            return "%s (%s)" % (self.name, self.value)
        if not self.suits:
            # Legacy's classless cards are plain (themeless) cards: a pilgrim reads
            # "Pilgrim 4", a Wild Animal "Wild Animal", a 19 simply "19".
            if self.has("pilgrim") or self.has("evergreen_puppy"):
                return "Pilgrim %s" % self.rank
            if self.has("choosable"):
                return "Wild Animal"
        return self.rank + "".join(SUIT_SYMBOL.get(s, s) for s in self.suits)

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.label()

    # -- (de)serialisation ------------------------------------------------
    def to_dict(self) -> dict:
        d = {"id": self.id, "rank": self.rank, "suits": list(self.suits), "value": self.value}
        if self.name:
            d["name"] = self.name
        if self.flags:
            d["flags"] = list(self.flags)
        if self.attack or self.health:
            d["attack"] = self.attack
            d["health"] = self.health
        return d

    @staticmethod
    def from_dict(d: dict) -> "Card":
        return Card(
            id=d["id"], rank=d["rank"], suits=tuple(d.get("suits", ())),
            value=int(d.get("value", 0)), name=d.get("name", ""),
            flags=tuple(d.get("flags", ())), attack=int(d.get("attack", 0)),
            health=int(d.get("health", 0)),
        )

    def with_changes(self, **changes) -> "Card":
        """Copy with fields replaced (cards are immutable)."""
        d = {"id": self.id, "rank": self.rank, "suits": self.suits, "value": self.value,
             "name": self.name, "flags": self.flags, "attack": self.attack, "health": self.health}
        d.update(changes)
        d["suits"] = tuple(d["suits"])
        d["flags"] = tuple(d["flags"])
        return Card(**d)


def make_card(rank: str, suit: Optional[str] = None, *, id: Optional[str] = None,
              name: str = "", flags: Iterable[str] = (), value: Optional[int] = None,
              suits: Optional[Sequence[str]] = None, attack: int = 0, health: int = 0) -> Card:
    """Build a card. ``make_card("7", "H")`` -> 7♥ with id "7H"."""
    if suits is None:
        suits = (suit,) if suit else ()
    suits = tuple(suits)
    if id is None:
        id = rank + "".join(suits)
    if value is None:
        value = RANK_VALUE.get(rank, 0)
    return Card(id=id, rank=rank, suits=suits, value=value, name=name, flags=tuple(flags),
                attack=attack, health=health)


def jester_card(n: int) -> Card:
    return Card(id="X%d" % n, rank=JESTER, suits=(), value=0, name="Jester")


def number_cards() -> List[Card]:
    """The 40 number cards A–10 in the four basic suits (the starting party)."""
    return [make_card(r, s) for s in BASIC_SUITS for r in NUMBER_RANKS]


def royal_cards() -> List[Card]:
    return [make_card(r, s) for r in ROYAL_RANKS for s in BASIC_SUITS]


def build_tavern(jesters: int) -> List[Card]:
    cards = number_cards()
    for i in range(jesters):
        cards.append(jester_card(i + 1))
    return cards


def build_castle(rng) -> List[Card]:
    """Jacks (shuffled) on top of Queens (shuffled) on top of Kings (shuffled).

    Index 0 is the top of the deck, i.e. the first enemy.
    """
    tiers: List[List[Card]] = []
    for rank in ROYAL_RANKS:
        tier = [make_card(rank, s) for s in BASIC_SUITS]
        rng.shuffle(tier)
        tiers.append(tier)
    return tiers[0] + tiers[1] + tiers[2]


def card_table(cards: Iterable[Card]) -> Dict[str, Card]:
    table: Dict[str, Card] = {}
    for c in cards:
        if c.id in table:
            raise ValueError("duplicate card id %s" % c.id)
        table[c.id] = c
    return table
