"""Mission definitions: enemies, setup, and reward steps.

Only missions 1 and 2 are playable in this build; the others carry their public
description so the campaign screen can show what is coming once revealed, and raise
``NotImplementedError`` when started.
"""
from __future__ import annotations

import itertools
import random
from typing import Any, Dict, List, Optional

from ..cards import BASIC_SUITS, CLASS_NAME, RANK_VALUE, SUIT_NAME
from . import party as P

Step = Dict[str, Any]


TIER_NAME = {"J": "Justicar", "Q": "Queen", "K": "King"}


def _royal_castle(rng: random.Random, corrupted: bool = False) -> List[dict]:
    """Mission 1's enemy stat card: Justicars 10/20, Queens 15/30, Kings 20/40, one of each
    basic class per tier (each immune to its own class)."""
    tiers = []
    for rank, atk, hp in (("J", 10, 20), ("Q", 15, 30), ("K", 20, 40)):
        tier = [{"id": rank + s, "rank": rank, "suits": [s], "value": RANK_VALUE[rank],
                 "name": "%s %s" % (CLASS_NAME[s], TIER_NAME[rank]),
                 "attack": atk, "health": hp, "flags": ["corrupted"] if corrupted else []} for s in BASIC_SUITS]
        rng.shuffle(tier)
        tiers.append(tier)
    return tiers[0] + tiers[1] + tiers[2]


def _academy_castle(rng: random.Random) -> List[dict]:
    """Mission 3's enemy stat card: four Instructors 10/30, two Professors 15/45 and the
    Dean 20/60, all of the Mage class."""
    tiers = []
    for rank, name, n, atk, hp in (("J", "Instructor", 4, 10, 30), ("Q", "Professor", 2, 15, 45), ("K", "Dean", 1, 20, 60)):
        tier = [{"id": "AC%s%d" % (rank, i + 1), "rank": rank, "suits": ["M"], "value": RANK_VALUE[rank],
                 "name": name, "attack": atk, "health": hp, "flags": []} for i in range(n)]
        rng.shuffle(tier)
        tiers.append(tier)
    return tiers[0] + tiers[1] + tiers[2]


def _lab_castle(rng: random.Random) -> List[dict]:
    """Mission 4's enemy stat card: Phase I 10/20, Phase II 15/30, Phase III 20/40, one
    experiment of each class per phase. Enemies are always in corrupted sleeves, so a
    defeated experiment drawn into a hand plays as a corrupted card."""
    tiers = []
    for rank, phase, atk, hp in (("J", "I", 10, 20), ("Q", "II", 15, 30), ("K", "III", 20, 40)):
        tier = [{"id": "LAB%s%s" % (rank, s), "rank": rank, "suits": [s], "value": RANK_VALUE[rank],
                 "name": "Phase %s Experiment" % phase, "attack": atk, "health": hp, "flags": ["corrupted"]}
                for s in BASIC_SUITS]
        rng.shuffle(tier)
        tiers.append(tier)
    return tiers[0] + tiers[1] + tiers[2]


def _hydra_castle(rng: random.Random) -> List[dict]:
    hydras = []
    for i, (a, b) in enumerate(itertools.combinations(BASIC_SUITS, 2)):
        hydras.append({"id": "HY%d" % (i + 1), "rank": "J", "suits": [a, b], "value": 10,
                       "name": "Hydra Head", "attack": 10, "health": 20, "flags": []})
    rng.shuffle(hydras)
    return hydras


MISSIONS: List[Dict[str, Any]] = [
    {
        "number": 1, "title": "Call to Arms", "fan_title": "The Beginning", "location": "Ostrana",
        "rules_id": "legacy_m1", "playable": True, "verified": True,
        "summary": "Four Justicars (10/20), four Queens (15/30) and four Kings (20/40), one of each "
                   "class, each immune to its own class. Enemy defeated: into the discard pile, or on "
                   "top of the reserve deck if dealt exact damage.",
        "rewards_text": "Open pack C and corrupt a character in your party. Add the High Arcana (25) to "
                        "your party. Acquire the Kinfolk Flute.",
    },
    {
        "number": 2, "title": "Shadow and Mist", "fan_title": "The Hydra Assault", "location": "Umbra Cavern",
        "rules_id": "legacy_m2", "playable": True, "verified": True,
        "summary": "Six Hydra Heads (10/20), each with two classes and immune to both. Exact damage banishes "
                   "a head; otherwise it goes face down to the bottom of the enemy deck and must be fought "
                   "again. The High Arcana (25) fights with you; a corrupted card banishes the top reserve "
                   "card as soon as it is played.",
        "rewards_text": "Open pack C and corrupt another character in your party. The first 3, 5, 7 and 9 "
                        "revealed from the shuffled party each get one class sticker, one of each class, "
                        "never a class the card already has.",
    },
    {"number": 3, "title": "Lessons in Flames", "fan_title": "The Mage Tower", "location": "Magic Academy",
     "rules_id": "legacy_m3", "playable": True, "verified": True,
     "summary": "The High Arcana is gone. Four Instructors (10/30), two Professors (15/45) and the Dean "
                "(20/60), all Mages. End of turn: the top reserve card goes face up into the mission zone. "
                "Enemies are immune to the classes of every card in the zone. A defeated enemy is banished "
                "with the whole zone; on exact damage one zone card is rescued to the discard pile first.",
     "rewards_text": "Open pack C and corrupt another character in your party. Open pack F (contents still "
                     "to be read: the app assumes the Mage class deck joins the party)."},
    {"number": 4, "title": "Fusion of Darkness", "fan_title": "The Gauntlet", "location": "Biology Laboratory",
     "rules_id": "legacy_m4", "playable": False, "verified": True,
     "summary": "Twelve corrupted experiments: Phase I (10/20), Phase II (15/30), Phase III (20/40), one of "
                "each class. Each enemy has additional strength equal to the strength of the top card of the "
                "discard pile, so what you leave on top matters. Enemy defeated: discard pile, or the top of "
                "the reserve deck on exact damage; experiments drawn into a hand play as corrupted cards.",
     "rewards_text": "Gøran (8, no class) joins. Gøran's four beasts wait beside the party: each attempt you may "
                     "include one in the reserve. Open pack C and corrupt another character. Acquire the "
                     "Scarlet Whistle."},
    {"number": 5, "title": "High and Mighty", "fan_title": "The Siege", "location": "unknown",
     "rules_id": "legacy_m5", "playable": False, "verified": False,
     "summary": "Eight enemies (10/40 and 15/60). The banished pile feeds the mission zone, which adds to "
                "enemy strength. Reavers and Myla help for this mission.", "rewards_text": "Myla and a Reaver stay."},
    {"number": 6, "title": "Shards of Memory", "fan_title": "The Evergreen Siege", "location": "Garden of Remembrance",
     "rules_id": "legacy_m6", "playable": False, "verified": False,
     "summary": "Guardians (15/30) and Evergreens (20/40). Every kill feeds the mission zone, which then "
                "strikes you. (Rules changed in the second printing.)", "rewards_text": "The Azure Emblem."},
    {"number": 7, "title": "Tales of Rebirth", "fan_title": "The Pilgrimage", "location": "Well of Tears",
     "rules_id": "legacy_m7", "playable": False, "verified": False,
     "summary": "Royals again, with a deck of pilgrims wandering into the mission zone; match their values "
                "to banish them. Druids help.", "rewards_text": "A Druid stays."},
    {"number": 8, "title": "Winds of Chaos", "fan_title": "The Troll Bridge", "location": "Heaven's Edge",
     "rules_id": "legacy_m8", "playable": False, "verified": False,
     "summary": "Six Trolls (10/20) then six Wyverns (25/50), all two-class. Build the mission zone in "
                "ascending order; a 10 clears it. Chanters help.", "rewards_text": "A Chanter stays."},
    {"number": 9, "title": "Hope From Ashes", "fan_title": "The Rescue", "location": "Twinseed Temple",
     "rules_id": "legacy_m9", "playable": False, "verified": False,
     "summary": "Thirty party cards are captured in three piles. Eight enemies, then Myla (20/80).",
     "rewards_text": "A Mage Beast; Goran ignores immunity; Evergreen Mother."},
    {"number": 10, "title": "Pride to Fall", "fan_title": "The Corruption", "location": "Twinseed Temple Ruins",
     "rules_id": "legacy_m10", "playable": False, "verified": False,
     "summary": "Your corrupted party members are the enemies.", "rewards_text": "They return; Goran is lost."},
    {"number": 11, "title": "Descent Into Darkness", "fan_title": "The Beast Hunt", "location": "Caverns of Decay",
     "rules_id": "legacy_m11", "playable": False, "verified": False,
     "summary": "Four classless enemies (10/30), then Evil Goran (20/90). Beasts shape the battlefield.",
     "rewards_text": "Esme returns with every class."},
    {"number": 12, "title": "Decay to Growth", "fan_title": "The Final Stand", "location": "Throne of Corruption",
     "rules_id": "legacy_m12", "playable": False, "verified": False,
     "summary": "Four Queens, four Kings and the High Arcana (25/120). Corrupted cards are restored.",
     "rewards_text": "The campaign ends; Eternal mode unlocks."},
]


def mission(number: int) -> Dict[str, Any]:
    return MISSIONS[number - 1]


# --------------------------------------------------------------------------- setup
def build_setup(camp, number: int, rng: random.Random) -> Dict[str, Any]:
    """Return the GameConfig.extra for an attempt at ``number``: party, castle, flags."""
    party = [dict(c) for c in camp.party]
    if number == 1:
        castle = _royal_castle(rng)
    elif number == 2:
        castle = _hydra_castle(rng)
    elif number == 3:
        castle = _academy_castle(rng)
    elif number == 4:
        castle = _lab_castle(rng)
    else:
        raise NotImplementedError("Mission %d is not implemented yet (see PLAN.md stage ladder)." % number)
    # Gøran's beast chosen for this attempt (reward of mission 4)
    if camp.beast and camp.flags.get("beasts"):
        beast = beast_by_id(camp.beast)
        if beast is not None and P.find(party, str(beast["id"])) is None:
            party.append(dict(beast))
    # mercenaries hired for this mission
    extra_jesters = 0
    for mid in camp.mercenaries:
        from .mercenaries import by_id
        m = by_id(mid)
        card = dict(m["card"])
        if card["rank"] == "X":
            extra_jesters += 1
            continue
        if P.find(party, str(card["id"])) is None:
            party.append(card)
    return {
        "party": party, "castle": castle, "relics": list(camp.relics),
        "extra_jesters": extra_jesters, "discard_low_to_high": bool(camp.flags.get("discard_low_to_high")),
        "mission": number,
    }


# --------------------------------------------------------------------------- mission start
def start_steps(camp, number: int) -> List[Step]:
    """Permanent changes a mission's setup cards make before its first attempt."""
    steps: List[Step] = []
    if number == 3 and P.find(camp.party, HIGH_ARCANA["id"]) is not None:
        # Card (confirmed): "Remove the High Arcana from your party. Store the card in mission box 3."
        steps.append({"kind": "remove_card", "card_id": HIGH_ARCANA["id"],
                      "label": "The High Arcana is nowhere to be seen: he leaves the party"})
    return steps


# --------------------------------------------------------------------------- rewards
def reward_steps(camp, number: int, rng: random.Random) -> List[Step]:
    """Reward steps for completing ``number``; 'auto' steps apply at once, 'choice'
    steps wait for the player. Each step is JSON-serialisable."""
    steps: List[Step] = []
    if number == 1:
        # Reward cards (confirmed): "Open pack C and corrupt a character in your party",
        # "Add the High Arcana to your party", "Acquire the new relic" (Kinfolk Flute).
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt a character in your party"))
        steps.append({"kind": "add_card", "card": HIGH_ARCANA, "label": "The High Arcana (25, Elf Mage) joins the party"})
        steps.append({"kind": "relic", "relic": "flute", "label": "Relic: Kinfolk Flute"})
    elif number == 2:
        # Reward cards (confirmed): "Open pack C and corrupt another character in your party";
        # class stickers for the first 3, 5, 7 and 9 revealed from the shuffled party. No
        # mission 2 card removes the High Arcana; mission 3's cards will say when he leaves.
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt another character in your party"))
        steps.append(_class_sticker_choice(camp, rng))
    elif number == 3:
        # Reward cards (confirmed): "Open pack C and corrupt another character in your party";
        # "Open pack F". Pack F's contents are not read yet: the fan transcription says the
        # Mage class deck (A to 10) joins the party permanently, so that is assumed.
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt another character in your party"))
        steps.append({"kind": "add_cards", "cards": MAGE_DECK,
                      "label": "Open pack F: the Mage class deck joins the party (unverified)"})
    elif number == 4:
        # Reward cards (confirmed, in order): "Add Gøran to your party"; "Keep Gøran's four
        # beasts in the box beside your party. Each mission attempt you may include one of
        # these four beasts in your reserve deck"; "Open pack C and corrupt another
        # character in your party"; "Acquire the new relic" (Scarlet Whistle).
        steps.append({"kind": "add_card", "card": GORAN, "label": "Gøran (8, Feltrix Evergreen) joins the party"})
        steps.append({"kind": "set_flag", "flag": "beasts", "value": True,
                      "label": "Gøran's four beasts wait beside the party: one may join each attempt"})
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt another character in your party"))
        steps.append({"kind": "relic", "relic": "whistle", "label": "Relic: Scarlet Whistle"})
    return steps


GORAN: Dict[str, Any] = {"id": "GOR8", "rank": "8", "suits": [], "value": 8, "name": "Gøran",
                         "subtitle": "Feltrix Evergreen", "flags": []}

# Gøran's beasts (mission 4 reward): rank B, one per basic class, strength 0 on their own
# and equal to the paired card's strength while attacking. Only Bonty's name was read.
BEASTS: List[Dict[str, Any]] = [
    {"id": "B_H", "rank": "B", "suits": ["H"], "value": 0, "name": "Bonty", "flags": ["beast"]},
    {"id": "B_D", "rank": "B", "suits": ["D"], "value": 0, "name": "Bard beast", "flags": ["beast"]},
    {"id": "B_C", "rank": "B", "suits": ["C"], "value": 0, "name": "Warrior beast", "flags": ["beast"]},
    {"id": "B_S", "rank": "B", "suits": ["S"], "value": 0, "name": "Paladin beast", "flags": ["beast"]},
]


def beast_by_id(bid: str) -> Optional[Dict[str, Any]]:
    for b in BEASTS:
        if b["id"] == bid:
            return b
    return None


MAGE_DECK: List[Dict[str, Any]] = [
    {"id": "%sM" % r, "rank": r, "suits": ["M"], "value": RANK_VALUE[r], "flags": []}
    for r in ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10")
]


HIGH_ARCANA: Dict[str, Any] = {"id": "ARC25", "rank": "25", "suits": [], "value": 25, "name": "High Arcana",
                               "subtitle": "Elf Mage", "flags": []}


def _class_sticker_choice(camp, rng: random.Random) -> Step:
    """Mission 2 reward card: shuffle the party, reveal from the top and set aside the first
    3, 5, 7 and 9 found; give each one class sticker so that each class is used once and
    no card gets a class it already has. The player assigns the stickers."""
    cards: List[str] = []
    for _ in range(50):
        cards = []
        for rank in ("3", "5", "7", "9"):
            pool = sorted(str(c["id"]) for c in camp.party if c["rank"] == rank)
            if pool:
                cards.append(rng.choice(pool))
        # Four stickers, one per class, cannot all be placed when every revealed card
        # already has the same single class (the card forbids a card's own class). The
        # physical game would have to reshuffle; so does the app.
        own = {tuple(P.find(camp.party, cid).get("suits", [])) for cid in cards}
        if len(cards) < 4 or len(own) > 1 or len(next(iter(own))) != 1:
            break
    return {"kind": "choice_classes", "label": "Class stickers: the first 3, 5, 7 and 9 revealed each gain a class",
            "cards": cards, "classes": list(BASIC_SUITS)}


def _corrupt_choice(camp, label: str) -> Step:
    """A player choice among the party cards that may be corrupted now."""
    return {"kind": "choice_corrupt", "label": label, "options": P.corruption_candidates(camp.party)}


def apply_step(camp, step: Step, rng: random.Random, option: Optional[str] = None) -> str:
    """Apply one reward step; returns a log line. Raises ValueError if a choice is needed."""
    kind = step["kind"]
    if kind in ("choice_corrupt", "corrupt_random"):
        if kind == "choice_corrupt":
            options = list(step.get("options") or P.corruption_candidates(camp.party))
            if not options:
                return "No card left to corrupt."
            if option is None:
                raise ValueError("choose a character to corrupt")
            if option not in options:
                raise ValueError("%s cannot be corrupted now" % option)
            target = option
        else:
            target = P.pick_corruption_target(camp.party, rng)
            if target is None:
                return "No card left to corrupt."
        P.add_flag(camp.party, target, "corrupted")
        camp.corrupted.append(target)
        return "%s is corrupted." % P.to_card(P.find(camp.party, target)).label()
    if kind == "relic":
        if step["relic"] not in camp.relics:
            camp.relics.append(step["relic"])
        return "Gained relic: %s." % step["relic"]
    if kind == "add_card":
        if P.find(camp.party, str(step["card"]["id"])) is None:
            P.add_card(camp.party, step["card"])
        return "%s joins the party." % (step["card"].get("name") or step["card"]["id"])
    if kind == "remove_card":
        c = P.remove_card(camp.party, step["card_id"])
        return "%s leaves the party." % ((c or {}).get("name") or step["card_id"])
    if kind == "set_flag":
        camp.flags[str(step["flag"])] = step.get("value", True)
        return str(step.get("label", "Flag %s set." % step["flag"]))
    if kind == "add_cards":
        added = []
        for card in step["cards"]:
            if P.find(camp.party, str(card["id"])) is None:
                P.add_card(camp.party, dict(card))
                added.append(P.to_card(card).label())
        return "%s join the party: %s." % (step.get("label", "New cards"), ", ".join(added)) if added else "Nothing new joins."
    if kind == "choice_classes":
        cards = [str(x) for x in step.get("cards", [])]
        classes = [str(x) for x in step.get("classes", [])]
        if not cards:
            return "No card qualifies for the class stickers."
        if not isinstance(option, dict):
            raise ValueError("assign one class to each card")
        assign = {str(k): str(v) for k, v in option.items()}
        if sorted(assign) != sorted(cards):
            raise ValueError("every revealed card needs exactly one sticker")
        if len(set(assign.values())) != len(assign) or any(v not in classes for v in assign.values()):
            raise ValueError("each class sticker may be used once")
        for cid, s in assign.items():
            card = P.find(camp.party, cid)
            if card is None:
                raise ValueError("%s is not in the party" % cid)
            if s in card.get("suits", []):
                raise ValueError("%s already has the %s class" % (cid, CLASS_NAME[s]))
        lines = []
        for cid in cards:
            P.add_suit(camp.party, cid, assign[cid])
            lines.append("%s gains %s" % (P.to_card(P.find(camp.party, cid)).label(), CLASS_NAME[assign[cid]]))
        return "Class stickers: " + ", ".join(lines) + "."
    raise ValueError("unknown reward step %r" % kind)
