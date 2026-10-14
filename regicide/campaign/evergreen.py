"""Pack E: Evergreen mode (confirmed from the owner's cards; parts 1 and 2 of 3 so far).

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

The data below is a transcription; the engine rules for each card follow once all
three parts of the pack are read.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

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
     "text": "Set aside all five Deccari (10s). You can't use them this game."},
    {"n": 6, "name": "Full Moon", "tier": "grey", "when": "setup",
     "text": "Set aside Ash (B, mage) and Quill (A, mage). You cannot use them this game."},
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

BOONS: List[Dict[str, Any]] = []   # part 3 of the pack


def by_tier(cards: List[Dict[str, Any]], tier: str) -> List[Dict[str, Any]]:
    return [c for c in cards if c["tier"] == tier]


def draw_setup(rng: random.Random, extra_red: bool = False, extra_bane: bool = False) -> Dict[str, Any]:
    """A random Evergreen mission per the rules card: one location, two grey banes (or one
    grey and a second red with ``extra_red``), one yellow and one red bane, one grey and
    one yellow boon; ``extra_bane`` adds one more bane of any tier. Tiers that have no
    cards yet (parts 2 and 3 of the pack) are simply left out."""
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
