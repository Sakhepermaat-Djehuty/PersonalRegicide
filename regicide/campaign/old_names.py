"""Old-save cleanup for the themeless cards.

Before the owner chose plain cards, the app named the beasts, the class decks, the mages'
ace, the pilgrims and the mercenaries, and some reward texts named reserve characters and
races. Campaigns saved then keep those words in their log and in reward steps still
waiting for a choice. ``rewrite`` turns them into today's plain wording; it is used only
when an old save is loaded (``CampaignState._migrate_plain_cards``).
"""
from __future__ import annotations

import re
from typing import Iterable, List, Tuple

# Whole phrases first (reward labels and mercenary names as they were shown).
_PHRASES: List[Tuple[str, str]] = [
    ("Harore teaches a 6: James (Cleric), Jakhim (Bard) or Lee (Paladin) gains the Reaver class",
     "The 5 Reaver teaches a 6: the Cleric, Bard or Paladin 6 gains the Reaver class"),
    ("Runo teaches an 8: Bronze (Cleric), Snow (Bard) or Shadow (Warrior) gains the Guardian class",
     "The 3 Guardian teaches an 8: the Cleric, Bard or Warrior 8 gains the Guardian class"),
    ("Alantha teaches a 4: Glamelyn (Bard), Herbod (Warrior) or Dhonatir (Paladin) gains the Druid class",
     "The 7 Druid teaches a 4: the Bard, Warrior or Paladin 4 gains the Druid class"),
    ("A song or two: Sprinkle (Cleric), Dinky (Warrior) or Wicket (Paladin) gains the Chanter class",
     "The 9 Chanter teaches a 2: the Cleric, Warrior or Paladin 2 gains the Chanter class"),
    ("A new student: choose dwarves (4) or feltrix (8); the first unstickered one revealed gains the Mage class",
     "A new student: choose the 4s or the 8s; the first unstickered one revealed gains the Mage class"),
    ("The High Arcana (25, Elf Mage)", "The High Arcana (25, no class)"),
    ("Gøran (8, Feltrix Evergreen)", "Gøran (8, no class)"),
    ("Myla (7, Elf Pilgrim)", "Myla (7, no class)"),
    ("Ash, Myla's beast (Mage), joins the party", "Myla's beast, a B of the Mage class (B⚝), joins the party"),
    ("Gøran's four beasts wait beside the party", "Gøran's four beasts (B♥ B♦ B♣ B♠) wait beside the party"),
    ("The puppy stays at Heaven's Edge", "The pilgrim ace stays at Heaven's Edge"),
    ("Gi… (12, Cleric)", "12 Cleric"), ("Bard 12 (12, Bard)", "12 Bard"),
    ("Warrior 12 (12, Warrior)", "12 Warrior"), ("Hella (12, Paladin)", "12 Paladin"),
    ("Zimis & Ora (2/5, Clerics)", "2/5 Cleric"), ("Bard pair (2/5, Bards)", "2/5 Bard"),
    ("Warrior pair (2/5, Warriors)", "2/5 Warrior"), ("Paladin pair (2/5, Paladins)", "2/5 Paladin"),
    ("Raki (19, no class)", "19 (no class)"), ("Taitonga (19, no class)", "19 (no class)"),
    ("Bristle (Wild Animal, choose class)", "Wild Animal (choose a class)"),
    ("Thistle (Wild Animal, choose class)", "Wild Animal (choose a class)"),
    ("Nelle (Jester)", "Jester"), ("Xam (Jester)", "Jester"),
    # classless cards' old labels, "Name (strength)"
    ("Traveller (2)", "Pilgrim 2"), ("Seeker (2)", "Pilgrim 2"), ("Follower (3)", "Pilgrim 3"),
    ("Servant (4)", "Pilgrim 4"), ("Pilgrim (5)", "Pilgrim 5"), ("Acolyte (6)", "Pilgrim 6"),
    ("Pilgrim (7)", "Pilgrim 7"), ("Puppy (1)", "Pilgrim A"), ("Raki (19)", "19"), ("Taitonga (19)", "19"),
    ("Bristle (1)", "Wild Animal"), ("Thistle (1)", "Wild Animal"),
]
_PHRASES.sort(key=lambda p: -len(p[0]))

# Then single names (whole words), as they appeared in "X joins / leaves the party".
_NAMES: List[Tuple[str, str]] = [
    ("Avion Chanter", "5𝄞"), ("Elf Chanter", "7𝄞"), ("Avion Druid", "5☘︎"), ("Drakonid Druid", "9☘︎"),
    ("Elf Guardian", "7♜"), ("Drakonid Guardian", "9♜"), ("Elf Reaver", "7⛏︎"), ("Drakonid Reaver", "9⛏︎"),
    ("Roslyn", "3𝄞"), ("Druldox", "9𝄞"), ("Tolman", "3☘︎"), ("Alantha", "7☘︎"), ("Runo", "3♜"),
    ("Teko", "5♜"), ("Oaken", "3⛏︎"), ("Harore", "5⛏︎"), ("Bonty", "B♥"), ("Ash", "B⚝"), ("Quill", "A⚝"),
    ("Puppy", "Pilgrim A"),
]
_NAME_RE = re.compile(r"\b(%s)\b" % "|".join(re.escape(n) for n, _ in sorted(_NAMES, key=lambda p: -len(p[0]))))
_NAME_MAP = dict(_NAMES)


def rewrite(text: str, keep: Iterable[str] = ()) -> str:
    """``text`` with the old card names and races replaced by the plain wording. Words in
    ``keep`` (the players' own names) are never touched."""
    if not isinstance(text, str) or not text:
        return text
    for old, new in _PHRASES:
        if old in text:
            text = text.replace(old, new)
    kept = set(keep)
    return _NAME_RE.sub(lambda m: m.group(1) if m.group(1) in kept else _NAME_MAP[m.group(1)], text)
