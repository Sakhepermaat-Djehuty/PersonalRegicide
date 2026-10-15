"""Pack E: Evergreen mode (confirmed from the owner's cards, all three parts).

Evergreen rules card: "Evergreen mode allows you to play Regicide Legacy over and over
again using your party deck from the end of Mission 12. Use the Evergreen cards in this
pack to construct unique missions. Set the game up like a normal mission (rulebook
pg. 7) with the following changes: use the 4 Phase III Experiments and 4 Phase II
Experiments (from mission box 4) as your 8 enemies. From this box randomly select: one
location card; two grey banes, one yellow bane and one red bane; one grey boon and one
yellow boon. Greys are low complexity and mostly affect the setup. Yellows are medium
complexity and usually introduce a rule change. Reds are high complexity and often
introduce new rules along with changes to the game state as you play. Keep boons and
banes by the mat as you play as reminders of the rules. To increase complexity you can
swap one of the grey banes with a second red bane. For an extra challenge just add
another bane!"

The data below is the transcription; ``draw_setup`` draws a mission, ``build_setup``
turns a drawn setup (location id, bane and boon numbers) into a ``GameConfig.extra`` for
``EvergreenRules`` (``evergreen_rules.py``), which implements every card.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from . import party as P

# Each location is a mission rules card: an optional setup, a start/end of turn effect,
# special rules and an enemy-defeated step.
LOCATIONS: List[Dict[str, Any]] = [
    {"id": "A", "name": "Shrine",
     "end_of_turn": "Put the top card of the reserve deck into the mission zone.",
     "special": "Each enemy has immunity to the classes of cards in the mission zone.",
     "defeated": "Banish the enemy, or discard it if exact damage was dealt. Then banish cards in the mission zone."},
    {"id": "B", "name": "Cave",
     "end_of_turn": "Put the top card of the reserve deck into the mission zone. If the combined strength of "
                    "cards in the mission zone equal or exceed the base strength of the current enemy, banish "
                    "the mission zone and the entire discard pile.",
     "defeated": "Banish the enemy, or discard it if exact damage was dealt. Then discard cards in the mission zone."},
    {"id": "C", "name": "Forest",
     "setup": "Shuffle Phase I Experiment enemies (from mission box 4) into the banished pile.",
     "special": "Each enemy has additional strength equal to the combined strength of cards in the mission zone.",
     "end_of_turn": "Put the top card of the banished pile into the mission zone.",
     "defeated": "Put the enemy and cards in mission zone into the banished pile then shuffle the banished pile. "
                 "If exact damage was dealt, you may first discard one card from the mission zone."},
    {"id": "D", "name": "Hills",
     "end_of_turn": "Put the top card of the banished pile into the mission zone. Players suffer team damage "
                    "equal to the combined strength of cards in the mission zone (satisfy this damage using the "
                    "same rules as team damage in mission 6). If the damage can't be satisfied the game is lost.",
     "defeated": "Put the enemy and cards in mission zone into the banished pile then shuffle the banished pile. "
                 "If exact damage was dealt, you may first discard one card from the mission zone."},
    {"id": "E", "name": "Lake",
     "setup": "Shuffle pilgrims and place in pilgrim deck in mission zone.",
     "start_of_turn": "Put the top card of the pilgrim deck (or reserve deck if pilgrim deck is empty) into the "
                      "mission zone.",
     "defeated": "For each card in the mission zone, banish a card from reserve deck, then move the cards in the "
                 "mission zone to the discard pile in any order. Then banish the enemy, or discard it if exact "
                 "damage was dealt."},
]

# Banes are numbered 1 to 23 on the card; the chevron colour gives the tier: 1 to 8 grey
# (setup changes), 9 to 15 yellow (rule changes), 16 to 23 red (ongoing effects).
BANES: List[Dict[str, Any]] = [
    {"n": 23, "name": "Choose Your Poison", "tier": "red", "when": "end_of_turn",
     "text": "You may discard a card from hand. If you don't, put the top card of the reserve deck into the mission zone."},
    {"n": 22, "name": "The Fiery Crucible", "tier": "red", "when": "start_of_turn",
     "text": "Put the top card of the reserve deck into the discard pile."},
    {"n": 21, "name": "Eye-Level Sticks", "tier": "red", "when": "special",
     "text": "Immediately after you form an attack that contains a card with 8 or more strength discard a card "
             "from your hand (if you can)."},
    {"n": 20, "name": "Fused Bones", "tier": "red", "when": "special",
     "text": "Each enemy is immune to the classes of the card on top of the banished pile."},
    {"n": 19, "name": "Shapeshift", "tier": "red", "when": "special",
     "text": "Each enemy is immune to the classes of the card on top of the discard pile."},
    {"n": 18, "name": "Mutated Beasts", "tier": "red", "when": "special",
     "text": "Each enemy has additional strength equal to the strength of the top card of the banished pile."},
    {"n": 17, "name": "Beastly Vigor", "tier": "red", "when": "special",
     "text": "Each enemy has additional strength equal to the strength of the top card of the discard pile."},
    {"n": 16, "name": "Lingering Dread", "tier": "red", "when": "start_of_turn",
     "text": "Put the top card of the discard pile into the banished pile."},
    {"n": 15, "name": "Tread Carefully", "tier": "yellow", "when": "enemy_defeated",
     "text": "If you did not deal exact damage, move the entire discard pile to the banished pile before carrying "
             "out the Location \"Enemy Defeated\" rules."},
    {"n": 14, "name": "Absorbtion", "tier": "yellow", "when": "enemy_defeated",
     "text": "After carrying out the Location \"Enemy Defeated\" rules, place all cards in the attack that dealt "
             "the final damage into the mission zone."},
    {"n": 13, "name": "Explosive Spores", "tier": "yellow", "when": "enemy_defeated",
     "text": "Players suffer team damage equal to the base strength of the defeated enemy. To satisfy this damage, "
             "cards may be discarded one at a time by any player (in any order) until a total amount of strength "
             "has been discarded at least equal to the team damage suffered. If this team damage cannot be "
             "satisfied the mission is lost."},
    {"n": 12, "name": "Duplicitous Bards", "tier": "yellow", "when": "end_of_turn",
     "text": "If the current enemy has a bard icon, put a card from your hand into the mission zone."},
    {"n": 11, "name": "Immovable Paladins", "tier": "yellow", "when": "special",
     "text": "Enemies with a paladin icon reduce damage dealt to them by 10."},
    {"n": 10, "name": "Poisonous Clerics", "tier": "yellow", "when": "end_of_turn",
     "text": "If the current enemy has a cleric icon, place the top card of the discard pile into the mission zone."},
    {"n": 9, "name": "Lethal Warriors", "tier": "yellow", "when": "special",
     "text": "Enemies with a warrior icon have double strength (including from other strength bonuses)."},
    {"n": 8, "name": "Ghosts From The Past", "tier": "grey", "when": "setup",
     "text": "Add the High Arcana (from mission box 12) to the bottom of the enemy deck. The High Arcana is immune "
             "to the 4 base classes (cleric, bard, warrior and paladin)."},
    {"n": 7, "name": "Solstice", "tier": "grey", "when": "setup",
     "text": "Set aside all five 10s. You can't use them this game."},
    {"n": 6, "name": "Full Moon", "tier": "grey", "when": "setup",
     "text": "Set aside Myla's beast (B, mage) and the mage ace (A, mage). You cannot use them this game."},
    {"n": 5, "name": "Somehow, Myla Returned", "tier": "grey", "when": "setup",
     "text": "Add Myla, High Arcana's Apprentice (in mission box 9), to the bottom of the enemy deck."},
    {"n": 4, "name": "Seeds of Corruption", "tier": "grey", "when": "setup",
     "text": "Replace the Restored Evergreen Mother relic with the Corrupted Evergreen Mother relic (in mission box 12)."},
    {"n": 3, "name": "A Dozen Ways to Die", "tier": "grey", "when": "setup",
     "text": "Replace the Phase III Experiment enemies with the Wyvern enemies (in mission 8 box)."},
    {"n": 2, "name": "Mental Health Day", "tier": "grey", "when": "setup",
     "text": "Put 30 cards from top of reserve deck into the discard pile."},
    {"n": 1, "name": "Six is the New Four", "tier": "grey", "when": "setup",
     "text": "Replace the Phase II Experiment enemies with the Hydra enemies (in mission box 2). Enemy defeated: if "
             "a Hydra was not dealt exact damage, place it on the bottom of the enemy deck. This rule overrides any "
             "location cleanup rule for where the enemy normally goes when defeated."},
]

# Boons are numbered 24 to 35: 24 to 29 grey (setup), 30 to 35 yellow (rule changes).
BOONS: List[Dict[str, Any]] = [
    {"n": 24, "name": "This Is Noble, Sir", "tier": "grey", "when": "setup",
     "text": "Spend 5 coins on mercenaries (from pack M) and add them to your reserve deck."},
    {"n": 25, "name": "There Are Two of Them!", "tier": "grey", "when": "setup",
     "text": "Add Gøran the Evergreen to your reserve deck (from mission box 10)."},
    {"n": 26, "name": "Call for Help", "tier": "grey", "when": "setup",
     "text": "Add all four of Gøran's Beasts to your reserve deck (instead of just one as usual)."},
    {"n": 27, "name": "Too Easy!", "tier": "grey", "when": "special",
     "text": "The hand size limit is increased by 1."},
    {"n": 28, "name": "Best Friend", "tier": "grey", "when": "setup",
     "text": "Add the pilgrim ace (from mission box 8) to the reserve deck. When you play it, it has all four base "
             "classes for this attack (cleric, bard, warrior, paladin)."},
    {"n": 29, "name": "Second Breakfast", "tier": "grey", "when": "setup",
     "text": "Add the 3 reaver, the 3 druid and the 3 chanter to the reserve deck (from mission "
             "boxes 5, 7 and 8 respectively)."},
    {"n": 30, "name": "Squad of Siblings", "tier": "yellow", "when": "special",
     "text": "Immediately after you form an attack you may move one card from the mission zone to the discard "
             "pile if it has the same strength as a card in your attack."},
    {"n": 31, "name": "Selfless Rescue", "tier": "yellow", "when": "special",
     "text": "Immediately after discarding a card to satisfy damage, if it matches the strength of a card in the "
             "mission zone you may move that card from the mission zone to the discard pile."},
    {"n": 32, "name": "Precision Strike", "tier": "yellow", "when": "enemy_defeated",
     "text": "If exact damage was dealt, put any card from the mission zone into your hand or put the top card of "
             "the discard pile into your hand."},
    {"n": 33, "name": "Restored Arrows", "tier": "yellow", "when": "enemy_defeated",
     "text": "If exact damage was dealt, you may put any one card from the banished pile to the bottom of the "
             "reserve deck."},
    {"n": 34, "name": "An Alliance", "tier": "yellow", "when": "special",
     "text": "Increase the Kinfolk Attack strength limit from 10 to 12 (for example you may now form Kinfolk Attacks "
             "with two 6s or with three 4s)."},
    {"n": 35, "name": "A Close Call", "tier": "yellow", "when": "special",
     "text": "When you satisfy damage for the exact amount you suffered (not including team damage or when damage "
             "is 0), place the discarded cards on the bottom of the reserve deck instead of the discard pile, then "
             "search the discard pile and put a card from it on top of the reserve deck."},
]


def by_tier(cards: List[Dict[str, Any]], tier: str) -> List[Dict[str, Any]]:
    return [c for c in cards if c["tier"] == tier]


def draw_setup(rng: random.Random, extra_red: bool = False, extra_bane: bool = False) -> Dict[str, Any]:
    """A random Evergreen mission per the rules card: one location, two grey banes (or one
    grey and a second red with ``extra_red``), one yellow and one red bane, one grey and
    one yellow boon; ``extra_bane`` adds one more bane of any tier."""
    def pick(cards: List[Dict[str, Any]], n: int, used: List[int]) -> List[Dict[str, Any]]:
        pool = [c for c in cards if c["n"] not in used]
        out = rng.sample(pool, min(n, len(pool)))
        used.extend(c["n"] for c in out)
        return out
    used_b: List[int] = []
    banes = pick(by_tier(BANES, "grey"), 1 if extra_red else 2, used_b)
    banes += pick(by_tier(BANES, "yellow"), 1, used_b)
    banes += pick(by_tier(BANES, "red"), 2 if extra_red else 1, used_b)
    if extra_bane:
        banes += pick(BANES, 1, used_b)
    used_o: List[int] = []
    boons = pick(by_tier(BOONS, "grey"), 1, used_o) + pick(by_tier(BOONS, "yellow"), 1, used_o)
    return {"location": rng.choice(LOCATIONS), "banes": banes, "boons": boons}


# --------------------------------------------------------------------------- lookups
def location_by_id(loc_id: str) -> Dict[str, Any]:
    for loc in LOCATIONS:
        if loc["id"] == loc_id:
            return loc
    raise KeyError(loc_id)


def bane(n: int) -> Dict[str, Any]:
    for b in BANES:
        if b["n"] == int(n):
            return b
    raise KeyError(n)


def boon(n: int) -> Dict[str, Any]:
    for b in BOONS:
        if b["n"] == int(n):
            return b
    raise KeyError(n)


def setup_ids(setup: Dict[str, Any]) -> Dict[str, Any]:
    """The compact, saveable form of a drawn setup: the location letter and the card numbers."""
    return {"location": str(setup["location"]["id"]), "banes": sorted(int(b["n"]) for b in setup["banes"]),
            "boons": sorted(int(b["n"]) for b in setup["boons"])}


def expand_setup(ids: Dict[str, Any]) -> Dict[str, Any]:
    """The card dicts of a saved setup (``setup_ids`` inverse)."""
    return {"location": location_by_id(str(ids["location"])), "banes": [bane(n) for n in ids.get("banes", [])],
            "boons": [boon(n) for n in ids.get("boons", [])]}


# --------------------------------------------------------------------------- a mission's setup
def build_setup(camp, ids: Dict[str, Any], rng: random.Random, mercenaries: Optional[List[str]] = None) -> Dict[str, Any]:
    """``GameConfig.extra`` for an attempt at the drawn setup ``ids`` (see ``setup_ids``)
    with the finished campaign's party. The grey banes and boons change this setup; the
    location's setup line and everything else is read by ``EvergreenRules`` from the
    ``evergreen`` entry.

    * Enemies (rules card): the four Phase III and four Phase II experiments of mission 4,
      weaker group on top, in their corrupted sleeves. Bane 1 puts the six Hydras of
      mission 2 in place of the Phase II group, bane 3 the six Wyverns of mission 8 in
      place of the Phase III group, bane 5 Myla (20/80) at the bottom and bane 8 the High
      Arcana (25/120, immune to the four base classes) at the very bottom (5 before 8).
    * Reserve: the party, less Ash and Quill (bane 6) or the five 10s (bane 7); plus the
      chosen beast or all four (boon 26), the renewed Gøran (boon 25), the puppy with its
      four classes while played (boon 28), Oaken, Tolman and Roslyn (boon 29) and the
      mercenaries hired with the boon's five coins (boon 24).
    * Bane 4 plays with the corrupt Evergreen Mother instead of the restored one. The
      Forest shuffles the four Phase I experiments into the banished pile; the Lake deals
      the 24 pilgrims (the puppy is in mission box 8) into a face-down pilgrim deck.
    * ``hand_bonus`` is 1 with boon 27 (the hand limit rises by one).
    """
    from . import missions as M
    banes = [int(n) for n in ids.get("banes", [])]
    boons = [int(n) for n in ids.get("boons", [])]
    loc = str(ids["location"])
    lab = M._lab_castle(rng)
    phase2 = [e for e in lab if e["rank"] == "Q"]
    phase3 = [e for e in lab if e["rank"] == "K"]
    phase1 = [e for e in lab if e["rank"] == "J"]
    if 1 in banes:
        phase2 = M._hydra_castle(rng)
    if 3 in banes:
        phase3 = [e for e in M._edge_castle(rng) if e["rank"] == "K"]
    castle = phase2 + phase3
    if 5 in banes:
        castle.append(dict(M.MYLA_BOSS))
    if 8 in banes:
        arcana = dict(M.HIGH_ARCANA_BOSS)
        arcana["flags"] = list(arcana.get("flags", [])) + ["immune_basic"]
        castle.append(arcana)
    party = [dict(c) for c in camp.party]
    if 6 in banes:
        party = [c for c in party if str(c["id"]) not in (M.ASH["id"], "AM")]
    if 7 in banes:
        party = [c for c in party if str(c.get("rank")) != "10"]
    if 26 in boons:
        for b in M.BEASTS:
            if P.find(party, str(b["id"])) is None:
                party.append(dict(b))
    elif camp.beast and camp.flags.get("beasts"):
        b = M.beast_by_id(camp.beast)
        if b is not None and P.find(party, str(b["id"])) is None:
            party.append(dict(b))
    if 25 in boons and P.find(party, M.GORAN_RENEWED["id"]) is None:
        party.append(dict(M.GORAN_RENEWED))
    if 28 in boons and P.find(party, M.PUPPY["id"]) is None:
        puppy = dict(M.PUPPY)
        puppy["flags"] = ["evergreen_puppy"]
        party.append(puppy)
    if 29 in boons:
        for group, cid in ((M.REAVERS, "3R"), (M.DRUIDS, "3U"), (M.CHANTERS, "3T")):
            card = [c for c in group if c["id"] == cid][0]
            if P.find(party, cid) is None:
                party.append(dict(card))
    extra_jesters = 0
    if 24 in boons:
        from .mercenaries import by_id
        for mid in mercenaries or []:
            card = dict(by_id(mid)["card"])
            if card["rank"] == "X":
                extra_jesters += 1
            elif P.find(party, str(card["id"])) is None:
                party.append(card)
    relics = list(camp.relics)
    if 4 in banes and "mother_restored" in relics:
        relics = [r for r in relics if r != "mother_restored"]
        if "mother" not in relics:
            relics.append("mother")
    banished_start: List[dict] = []
    if loc == "C":
        rng.shuffle(phase1)
        banished_start = phase1
    pilgrims: List[dict] = []
    if loc == "E":
        pilgrims = [dict(c) for c in M.PILGRIMS]
        rng.shuffle(pilgrims)
    return {
        "party": party, "castle": castle, "relics": relics, "extra_jesters": extra_jesters,
        "discard_low_to_high": bool(camp.flags.get("discard_low_to_high")),
        "mission": 13, "evergreen": {"location": loc, "banes": sorted(banes), "boons": sorted(boons)},
        "banished_start": banished_start, "zone_start": [], "pilgrims": pilgrims,
        "pilgrims_in_reserve": [], "capture": {}, "beast_deck": [],
        "hand_bonus": 1 if 27 in boons else 0,
    }
