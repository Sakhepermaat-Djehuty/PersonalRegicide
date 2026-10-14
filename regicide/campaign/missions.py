"""Mission definitions: enemies, setup, and reward steps.

All twelve missions are playable; Evergreen mode (pack E) builds its generated missions
from the same card data (see ``evergreen.py``).
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


def _grove_castle(rng: random.Random) -> List[dict]:
    """Mission 5's enemy stat card: four Sporelings 10/40 and four Gloomspores 15/60, one
    of each class per tier."""
    tiers = []
    for rank, name, atk, hp in (("J", "Sporeling", 10, 40), ("Q", "Gloomspore", 15, 60)):
        tier = [{"id": "GR%s%s" % (rank, s), "rank": rank, "suits": [s], "value": RANK_VALUE[rank],
                 "name": name, "attack": atk, "health": hp, "flags": []} for s in BASIC_SUITS]
        rng.shuffle(tier)
        tiers.append(tier)
    return tiers[0] + tiers[1]


def _garden_castle(rng: random.Random) -> List[dict]:
    """Mission 6's enemy stat card: four Guardian statues 15/30 and four Evergreen statues
    20/40, one of each class per tier."""
    tiers = []
    for rank, name, atk, hp in (("Q", "Guardian Statue", 15, 30), ("K", "Evergreen Statue", 20, 40)):
        tier = [{"id": "GD%s%s" % (rank, s), "rank": rank, "suits": [s], "value": RANK_VALUE[rank],
                 "name": name, "attack": atk, "health": hp, "flags": []} for s in BASIC_SUITS]
        rng.shuffle(tier)
        tiers.append(tier)
    return tiers[0] + tiers[1]


def _well_castle(rng: random.Random) -> List[dict]:
    """Mission 7's enemy stat card: Shoal 10/20, Deep 15/30, Abyssal 20/40 pondkin, one of
    each class per tier (twelve enemies)."""
    tiers = []
    for rank, name, atk, hp in (("J", "Shoal Pondkin", 10, 20), ("Q", "Deep Pondkin", 15, 30), ("K", "Abyssal Pondkin", 20, 40)):
        tier = [{"id": "WL%s%s" % (rank, s), "rank": rank, "suits": [s], "value": RANK_VALUE[rank],
                 "name": name, "attack": atk, "health": hp, "flags": []} for s in BASIC_SUITS]
        rng.shuffle(tier)
        tiers.append(tier)
    return tiers[0] + tiers[1] + tiers[2]


def _edge_castle(rng: random.Random) -> List[dict]:
    """Mission 8's enemy stat card: six Trolls 10/20 and six Wyverns 25/50, each with a
    distinct pair of the four classes (immune to both)."""
    tiers = []
    for rank, name, atk, hp in (("J", "Troll", 10, 20), ("K", "Wyvern", 25, 50)):
        tier = []
        for i, (a, b) in enumerate(itertools.combinations(BASIC_SUITS, 2)):
            tier.append({"id": "HE%s%d" % (rank, i + 1), "rank": rank, "suits": [a, b], "value": RANK_VALUE[rank],
                         "name": name, "attack": atk, "health": hp, "flags": []})
        rng.shuffle(tier)
        tiers.append(tier)
    return tiers[0] + tiers[1]


def _temple_castle(rng: random.Random) -> List[dict]:
    """Mission 9's enemy stat card: four Loreguards 15/30 and four Lorekeepers 20/40, one
    of each class per tier, then Myla 20/80 (bard and paladin; her immunity can never be
    ignored)."""
    tiers = []
    for rank, name, atk, hp in (("Q", "Loreguard", 15, 30), ("K", "Lorekeeper", 20, 40)):
        tier = [{"id": "TT%s%s" % (rank, s), "rank": rank, "suits": [s], "value": RANK_VALUE[rank],
                 "name": name, "attack": atk, "health": hp, "flags": []} for s in BASIC_SUITS]
        rng.shuffle(tier)
        tiers.append(tier)
    return tiers[0] + tiers[1] + [dict(MYLA_BOSS)]


# Mission 9's boss (also Evergreen bane 5): Myla, the High Arcana's apprentice, 20/80, bard
# and paladin; her immunity can never be ignored.
MYLA_BOSS: Dict[str, Any] = {"id": "MYLA_BOSS", "rank": "K", "suits": ["D", "S"], "value": 20, "name": "Myla",
                             "attack": 20, "health": 80, "flags": ["fixed_immunity"]}

# Mission 12's boss (also Evergreen bane 8): the High Arcana, 25/120, dark gem icon (no
# class), in a corrupted sleeve. Bane 8 adds the ``immune_basic`` flag: immune to the
# four base classes without carrying them as suits (a defeated enemy drawn into a hand
# must not play as a four-class card).
HIGH_ARCANA_BOSS: Dict[str, Any] = {"id": "TH_ARCANA", "rank": "K", "suits": [], "value": 25, "name": "High Arcana",
                                    "attack": 25, "health": 120, "flags": ["corrupted"]}


def _ruins_castle(camp) -> List[dict]:
    """Mission 10's enemy deck: the corrupted party members themselves (moved out of the
    party by the setup card into ``camp.away``), face up, ordered from 9 on the bottom to
    2 on the top; health five times the base strength, strength equal to it. They keep
    their classes (stickers included) and their corruption, so a defeated one drawn from
    the discard pile plays as the corrupted party card it is."""
    enemies = []
    for c in sorted(camp.away, key=lambda d: (int(d.get("value", 0)), str(d["id"]))):
        e = dict(c)
        e["attack"] = int(c.get("value", 0))
        e["health"] = 5 * int(c.get("value", 0))
        flags = list(c.get("flags", []))
        if "corrupted" not in flags:
            flags.append("corrupted")
        e["flags"] = flags
        enemies.append(e)
    return enemies


def _caverns_castle(rng: random.Random) -> List[dict]:
    """Mission 11's enemy stat card: four Justicars 10/30, then the Corrupted Evergreen
    20/90. Both carry a dark gem icon rather than a class; the app reads it as no innate
    class, so their immunities come only from the tops of the discard and banished piles
    as the mission rules say."""
    tier = [{"id": "CV_J%d" % (i + 1), "rank": "J", "suits": [], "value": 10, "name": "Justicar",
             "attack": 10, "health": 30, "flags": []} for i in range(4)]
    rng.shuffle(tier)
    boss = {"id": "CV_EVERGREEN", "rank": "K", "suits": [], "value": 20, "name": "Corrupted Evergreen",
            "attack": 20, "health": 90, "flags": []}
    return tier + [boss]


def _throne_castle(rng: random.Random) -> List[dict]:
    """Mission 12's enemy stat card: four Queens 15/30 and four Kings 20/40, one of each
    class per tier, then the High Arcana 25/120 (dark gem icon: no class). The royals are
    corrupted (the summary's corrupted-card rule applies to them): a corrupted card can
    never enter the reserve deck and goes to the bottom of the banished pile instead."""
    tiers = []
    for rank, name, atk, hp in (("Q", "Queen", 15, 30), ("K", "King", 20, 40)):
        tier = [{"id": "TH%s%s" % (rank, s), "rank": rank, "suits": [s], "value": RANK_VALUE[rank],
                 "name": "%s %s" % (CLASS_NAME[s], name), "attack": atk, "health": hp, "flags": ["corrupted"]}
                for s in BASIC_SUITS]
        rng.shuffle(tier)
        tiers.append(tier)
    return tiers[0] + tiers[1] + [dict(HIGH_ARCANA_BOSS)]


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
     "rewards_text": "Open pack C and corrupt another character in your party. Open pack F: the ten mages "
                     "join the party."},
    {"number": 4, "title": "Fusion of Darkness", "fan_title": "The Gauntlet", "location": "Biology Laboratory",
     "rules_id": "legacy_m4", "playable": True, "verified": True,
     "summary": "Twelve corrupted experiments: Phase I (10/20), Phase II (15/30), Phase III (20/40), one of "
                "each class. Each enemy has additional strength equal to the strength of the top card of the "
                "discard pile, so what you leave on top matters. Enemy defeated: discard pile, or the top of "
                "the reserve deck on exact damage; experiments drawn into a hand play as corrupted cards.",
     "rewards_text": "Gøran (8, no class) joins. Gøran's four beasts wait beside the party: each attempt you may "
                     "include one in the reserve. Open pack C and corrupt another character. Acquire the "
                     "Scarlet Whistle."},
    {"number": 5, "title": "High and Mighty", "fan_title": "The Siege", "location": "Crimson Grove",
     "rules_id": "legacy_m5", "playable": True, "verified": True,
     "summary": "Four Reavers join the party for this mission and Myla (7) starts in the banished pile. Four "
                "Sporelings (10/40) and four Gloomspores (15/60), one of each class. End of turn: the top "
                "card of the banished pile goes face up into the mission zone, and each enemy has additional "
                "strength equal to the combined strength of the zone. Enemy defeated: the enemy and the zone "
                "are shuffled into the banished pile; on exact damage the next enemy takes damage equal to "
                "the defeated enemy's strength.",
     "rewards_text": "Gøran gains the Warrior class. Myla joins the party; the 5 Reaver stays and the "
                     "other three Reavers leave. Open pack C and corrupt another character. Choose the 6 "
                     "Cleric, 6 Bard or 6 Paladin to gain the Reaver class."},
    {"number": 6, "title": "Shards of Memory", "fan_title": "The Evergreen Siege", "location": "Garden of Remembrance",
     "rules_id": "legacy_m6", "playable": True, "verified": True,
     "summary": "Myla leaves the party and starts face up in the mission zone; four Guardians join. Four "
                "Guardian statues (15/30) and four Evergreen statues (20/40), one of each class. Enemy "
                "defeated: banish it, move one card in play into the mission zone (one zone card except Myla "
                "goes to the discard pile instead on exact damage), then Myla deals team damage equal to the "
                "zone's combined strength, discarded one card at a time by any players. A Guardian in the "
                "killing attack prevents the team damage.",
     "rewards_text": "Gøran gains the Paladin class. Open pack C and corrupt another character. Acquire the "
                     "Azure Emblem. Choose the 8 Cleric, 8 Bard or 8 Warrior to gain the Guardian class. The "
                     "3 Guardian stays; the other three Guardians leave."},
    {"number": 7, "title": "Tales of Rebirth", "fan_title": "The Pilgrimage", "location": "Well of Tears",
     "rules_id": "legacy_m7", "playable": True, "verified": True,
     "summary": "Four Druids join for the mission. Shoal (10/20), Deep (15/30) and Abyssal (20/40) pondkin, "
                "one of each class. Pack P's pilgrims form a face-down deck in the mission zone; at the start "
                "of every turn one is turned face up. A card entering play may banish one pilgrim of the "
                "same strength. Pilgrims never leave players' hands. Enemy defeated: discard reserve cards "
                "equal to the zone's total strength, discard the zone, banish the enemy; on exact damage one "
                "zone card may be banished first.",
     "rewards_text": "Gøran gains the Cleric class. Open pack C and corrupt another character. The 7 Druid "
                     "stays and the other three Druids leave. Choose the 4 Bard, 4 Warrior or 4 Paladin to "
                     "gain the Druid class."},
    {"number": 8, "title": "Winds of Chaos", "fan_title": "The Troll Bridge", "location": "Heaven's Edge",
     "rules_id": "legacy_m8", "playable": True, "verified": True,
     "summary": "Four Chanters join for the mission. The pilgrim ace starts in the mission zone and the "
                "other pilgrims are shuffled into the reserve. Six Trolls (10/20) then six Wyverns (25/50), "
                "each immune to two classes. Non-pilgrim cards in the zone add their strength to the "
                "enemy. Enemy defeated: banish it, then cards in play may be moved into the zone one at a "
                "time, each exactly one strength higher than the zone's highest (the pilgrim ace is 1); a 10 "
                "clears the zone into the discard pile, lets you banish any discards and heals the rest "
                "under the reserve. Exact damage: any discard pile card goes on top of the reserve.",
     "rewards_text": "Gøran gains the Bard class. Open pack C and corrupt another character. The 9 Chanter "
                     "stays and the other three Chanters leave. Choose the 2 Cleric, 2 Warrior or 2 Paladin "
                     "to gain the Chanter class. The pilgrim ace goes back in the box."},
    {"number": 9, "title": "Hope From Ashes", "fan_title": "The Rescue", "location": "Twinseed Temple",
     "rules_id": "legacy_m9", "playable": True, "verified": True,
     "summary": "Gøran, your beast, Jesters and mercenaries are set aside; thirty of the remaining party "
                "cards are dealt into three captured piles in the mission zone, top cards face up; the "
                "pilgrims and the set-aside cards are shuffled into the rest of the reserve. Four "
                "Loreguards (15/30), four Lorekeepers (20/40), then Myla (20/80), immune to bards and "
                "paladins in a way nothing can ignore. End of turn: banish a card from hand to rescue the "
                "top card of one pile to the discard pile, or rotate every pile. Enemy defeated: banish it; "
                "on exact damage a pile's top card may go on top of the reserve deck.",
     "rewards_text": "Acquire the Evergreen Mother (corrupt relic). Gøran is renewed: the old card leaves "
                     "and the Evergreen Gøran (8, all four classes, ignores immunity) joins. Choose the 4s "
                     "or the 8s: the first unstickered one revealed from the shuffled party gains the Mage "
                     "class. Myla's beast, a B of the Mage class, joins the party."},
    {"number": 10, "title": "Pride to Fall", "fan_title": "The Corruption", "location": "Twinseed Temple Ruins",
     "rules_id": "legacy_m10", "playable": True, "verified": True,
     "summary": "The corrupted members leave the party and form the enemy deck, face up, 2 on top down to 9. "
                "Each has health five times its strength and gains strength from every card in the mission "
                "zone. Start of turn: the top reserve card goes into the zone. Warriors double their total "
                "strength; paladins shrug off damage equal to their base strength; clerics pull the top "
                "discard into the zone at the end of each turn; bards make the current player put a hand "
                "card into the zone. Enemy defeated: banish the zone and discard the enemy; on exact damage "
                "the zone is discarded instead.",
     "rewards_text": "Gøran is lost. The corrupted characters return to the party."},
    {"number": 11, "title": "Descent Into Darkness", "fan_title": "The Beast Hunt", "location": "Caverns of Decay",
     "rules_id": "legacy_m11", "playable": True, "verified": True,
     "summary": "One corrupted member of the Eternal Vine dies at the machine and is torn up for good. "
                "Gøran's four beasts form a face-down beast deck in the mission zone (none may join the "
                "reserve; Myla's B of the Mage class may). Start of turn: reveal a beast and apply its class: warrior banishes the "
                "top discard, paladin discards the top reserve card, cleric makes you discard a hand card, "
                "bard makes you banish one; revealed beasts pile up face up and reform the deck when all "
                "four are out. Four Justicars (10/30), then the Corrupted Evergreen (20/90); each enemy is "
                "immune to the classes of, and gains the strength of, the top cards of the discard and "
                "banished piles. Enemy defeated: banish it; on exact damage no beast is revealed next turn.",
     "rewards_text": "The reborn Evergreen joins the party: Esme (6, Evergreen: all four classes, ignores "
                     "immunity). Gøran's beasts return to the box beside the party."},
    {"number": 12, "title": "Decay to Growth", "fan_title": "The Final Stand", "location": "Throne of Corruption",
     "rules_id": "legacy_m12", "playable": True, "verified": True,
     "summary": "Esme's light restores every corrupted party member (and Esme herself): restored cards "
                "ignore immunity and return the top banished card under the reserve when played, and the "
                "restored Evergreen Mother keeps them out of the banished pile. Four Queens (15/30), four "
                "Kings (20/40), then the High Arcana (25/120). Start of turn: the top banished card goes "
                "into the mission zone; the zone adds its strength to the enemy and grants immunity to its "
                "classes. Enemy defeated: banish the zone, the enemy and the whole discard pile; on exact "
                "damage the next start of turn is skipped. Corrupted cards never enter the reserve.",
     "rewards_text": "The High Arcana is dead. Open pack E: the campaign is complete and Eternal mode begins."},
]

# One line of flavour for the game menu (written for this app; the mission's rules are on
# the rules card the app shows when a mission first loads, and from the in-game menu).
_FLAVOUR: Dict[int, str] = {
    1: "Ostrana's royals have succumbed to a maddening corruption. The party is called to arms.",
    2: "Something with many heads waits in the dark of Umbra Cavern.",
    3: "The Magic Academy's teachers have lost their minds. Class is in session.",
    4: "Something stirs in the vats of the Biology Laboratory.",
    5: "Spores drift over the Crimson Grove, and the trail leads to Myla.",
    6: "In the Garden of Remembrance, the statues are waking.",
    7: "Pilgrims gather at the Well of Tears, and the pondkin rise to meet them.",
    8: "Trolls hold the way to Heaven's Edge, and wyverns circle above.",
    9: "Twinseed Temple holds the captured. Get them out.",
    10: "In the temple's ruins, your corrupted friends stand against you.",
    11: "Deep in the Caverns of Decay, the hunt begins.",
    12: "The Throne of Corruption. End it.",
}
for _m in MISSIONS:
    _m["flavour"] = _FLAVOUR.get(int(_m["number"]), "")


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
    elif number == 5:
        castle = _grove_castle(rng)
    elif number == 6:
        castle = _garden_castle(rng)
    elif number == 7:
        castle = _well_castle(rng)
    elif number == 8:
        castle = _edge_castle(rng)
    elif number == 9:
        castle = _temple_castle(rng)
    elif number == 10:
        castle = _ruins_castle(camp)
    elif number == 11:
        castle = _caverns_castle(rng)
    elif number == 12:
        castle = _throne_castle(rng)
    else:
        raise NotImplementedError("Mission %d is not implemented yet (see PLAN.md stage ladder)." % number)
    banished_start: List[dict] = []
    zone_start: List[dict] = []
    if number == 5:
        # Setup card (confirmed): "Put Myla (7) in a standard sleeve then place her in the
        # banished pile." She is not in the party yet; she joins after the mission.
        banished_start.append(dict(MYLA))
    if number == 6:
        # Mission rules (confirmed): "Place Myla (7) face up into the mission zone."
        zone_start.append(dict(MYLA))
    pilgrims: List[dict] = []
    pilgrims_in_reserve: List[dict] = []
    if number == 7:
        # Mission rules (confirmed): "Open pack P. Shuffle the pilgrims and place them in a
        # facedown pilgrim deck in the mission zone."
        pilgrims = [dict(c) for c in PILGRIMS]
        rng.shuffle(pilgrims)
    if number == 8:
        # Mission rules (confirmed): "Place the pilgrim puppy into the mission zone. Open
        # pack P and shuffle the pilgrims into the reserve deck."
        zone_start.append(dict(PUPPY))
        pilgrims_in_reserve = [dict(c) for c in PILGRIMS if c["id"] != PUPPY["id"]]
    capture: Dict[str, Any] = {}
    if number == 9:
        # Mission rules (confirmed): set Gøran, the chosen beast and any Jesters or
        # mercenaries aside; shuffle the rest of the reserve and deal 30 cards face down
        # into three captured piles of 10 in the mission zone, top cards face up; shuffle
        # the pilgrims and the set-aside cards into the remaining reserve deck. (The puppy
        # went back into the mission 8 box.)
        pilgrims_in_reserve = [dict(c) for c in PILGRIMS if c["id"] != PUPPY["id"]]
        capture = {"piles": 3, "size": 10, "exempt": []}  # exempt ids filled in below
    beast_deck: List[dict] = []
    if number == 11:
        # Mission rules (confirmed): all four of Gøran's beasts, shuffled, form a face-down
        # beast deck in the mission zone; none may be in the reserve deck (Ash may, he is in
        # the party). After the mission they go back to the box beside the party.
        beast_deck = [dict(b) for b in BEASTS]
        rng.shuffle(beast_deck)
    # Gøran's beast chosen for this attempt (reward of mission 4)
    if camp.beast and camp.flags.get("beasts") and number != 11:
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
    if capture:
        # Gøran, the chosen beast, mercenaries (and Jesters, which the rules add) are never
        # captured; Ash, a party beast, is set aside too ("your chosen beast" and beasts alike).
        capture["exempt"] = [str(c["id"]) for c in party
                             if c.get("name") == "Gøran" or "beast" in c.get("flags", []) or "mercenary" in c.get("flags", [])]
    return {
        "party": party, "castle": castle, "relics": list(camp.relics),
        "extra_jesters": extra_jesters, "discard_low_to_high": bool(camp.flags.get("discard_low_to_high")),
        "mission": number, "banished_start": banished_start, "zone_start": zone_start,
        "pilgrims": pilgrims, "pilgrims_in_reserve": pilgrims_in_reserve, "capture": capture,
        "beast_deck": beast_deck,
    }


# --------------------------------------------------------------------------- mission start
def start_steps(camp, number: int) -> List[Step]:
    """Permanent changes a mission's setup cards make before its first attempt."""
    steps: List[Step] = []
    if number == 3 and P.find(camp.party, HIGH_ARCANA["id"]) is not None:
        # Card (confirmed): "Remove the High Arcana from your party. Store the card in mission box 3."
        steps.append({"kind": "remove_card", "card_id": HIGH_ARCANA["id"],
                      "label": "The High Arcana is nowhere to be seen: he leaves the party"})
    if number == 5 and any(P.find(camp.party, str(r["id"])) is None for r in REAVERS):
        # Card (confirmed): "Add the four Reavers to your party."
        steps.append({"kind": "add_cards", "cards": REAVERS, "label": "The four Reavers charge into battle"})
    if number == 6:
        # Cards (confirmed): "Remove Myla from your party. She will be in the mission zone for
        # this mission." and "Add the four Guardians to your party."
        if P.find(camp.party, MYLA["id"]) is not None:
            steps.append({"kind": "remove_card", "card_id": MYLA["id"],
                          "label": "Myla turns on the party: she animates the statues of the veil"})
        if any(P.find(camp.party, str(g["id"])) is None for g in GUARDIANS):
            steps.append({"kind": "add_cards", "cards": GUARDIANS, "label": "The four Guardians raise their shields"})
    if number == 7 and any(P.find(camp.party, str(d["id"])) is None for d in DRUIDS):
        # Card (confirmed): "Add the four Druids to your party."
        steps.append({"kind": "add_cards", "cards": DRUIDS, "label": "The druids draw out scythes, swords and shields"})
    if number == 8 and any(P.find(camp.party, str(d["id"])) is None for d in CHANTERS):
        # Card (confirmed): "Add the four Chanters to your party."
        steps.append({"kind": "add_cards", "cards": CHANTERS, "label": "Thrum. Thrum. Thrum. The chanters beat their drums"})
    if number == 10 and P.corrupted_ids(camp.party):
        # Card (confirmed): "Remove the corrupted characters from your party. For this
        # mission they will form the enemy deck."
        steps.append({"kind": "corrupted_leave", "label": "Friends turned foe: the corrupted characters leave the party"})
    if number == 11 and not camp.flags.get("vine_ripped"):
        # Card (confirmed): "From your corrupted party members, choose one of them that has
        # a cloak of the Eternal Vine. Rip up the chosen card." The reborn Evergreen is Esme
        # (6), the 6 of warriors in the physical game.
        # Corruption is random in the app, so the corrupted 6 (whatever its class) dies and
        # the reborn Evergreen, a 6, takes its place.
        corrupted = P.corrupted_ids(camp.party)
        sixes = [cid for cid in corrupted if P.find(camp.party, cid)["rank"] == "6"]
        steps.append({"kind": "rip_up", "card_id": sixes[0] if sixes else None,
                      "label": "A member of the Eternal Vine dies at the machine"})
    if number == 12:
        # Setup cards (confirmed): "Take all the corrupted party members, remove their
        # corrupted sleeve and replace them with restored sleeves. These cards are no longer
        # corrupted. Sleeve Esme (6, Evergreen) with a restored sleeve." and "Put the corrupted
        # Evergreen Mother relic in the mission 12 box. Acquire the new restored Evergreen
        # Mother relic."
        if P.corrupted_ids(camp.party) or (P.find(camp.party, ESME_REBORN["id"]) is not None
                                           and "restored" not in P.find(camp.party, ESME_REBORN["id"]).get("flags", [])):
            steps.append({"kind": "restore_all", "label": "Esme's light burns the corruption away: the party is restored"})
        if "mother" in camp.relics or "mother_restored" not in camp.relics:
            steps.append({"kind": "relic_swap", "old": "mother", "new": "mother_restored",
                          "label": "The Evergreen Mother blooms once more: the restored relic replaces the corrupt one"})
    return steps


# The app plays a themeless deck (owner's choice): the cards the party holds are plain
# playing cards, rank and class only, with no names or races. Only the story characters
# the mission cards name (Gøran, Myla, Esme, the High Arcana) keep their names.

# Mission 8's Chanters: a 3, 5, 7 and 9. Only the 9 stays after the mission.
CHANTERS: List[Dict[str, Any]] = [
    {"id": "%sT" % r, "rank": r, "suits": ["T"], "value": int(r), "flags": []} for r in ("3", "5", "7", "9")
]


# Mission 7's Druids: a 3, 5, 7 and 9. Only the 7 stays after the mission.
DRUIDS: List[Dict[str, Any]] = [
    {"id": "%sU" % r, "rank": r, "suits": ["U"], "value": int(r), "flags": []} for r in ("3", "5", "7", "9")
]

# Pack P, the pilgrim deck (missions 7 and 8), confirmed by the owner: four classless
# cards of every strength 2 to 7 (24 cards) plus the pilgrim ace (the puppy on the
# physical card), which mission 8 places in the mission zone. They show as "Pilgrim 4".
PUPPY: Dict[str, Any] = {"id": "PILA", "rank": "A", "suits": [], "value": 1, "flags": ["pilgrim"]}
PILGRIMS: List[Dict[str, Any]] = [dict(PUPPY)] + [
    {"id": "PIL%s_%d" % (r, i + 1), "rank": r, "suits": [], "value": int(r), "flags": ["pilgrim"]}
    for r in ("2", "3", "4", "5", "6", "7") for i in range(4)
]


# Mission 6's Guardians: a 3, 5, 7 and 9. Only the 3 stays after the mission.
GUARDIANS: List[Dict[str, Any]] = [
    {"id": "%sG" % r, "rank": r, "suits": ["G"], "value": int(r), "flags": []} for r in ("3", "5", "7", "9")
]


# Mission 5's Reavers: a 3, 5, 7 and 9. Only the 5 stays after the mission.
REAVERS: List[Dict[str, Any]] = [
    {"id": "%sR" % r, "rank": r, "suits": ["R"], "value": int(r), "flags": []} for r in ("3", "5", "7", "9")
]

MYLA: Dict[str, Any] = {"id": "MYLA7", "rank": "7", "suits": [], "value": 7, "name": "Myla", "flags": []}


# --------------------------------------------------------------------------- rewards
# The class-sticker choices of missions 5 to 8 and mission 9's mage student, named the
# plain way (the cards name reserve characters and races; the app shows none).
CHOICE_SUIT_LABELS: Dict[str, str] = {
    "R": "The 5 Reaver teaches a 6: the Cleric, Bard or Paladin 6 gains the Reaver class",
    "G": "The 3 Guardian teaches an 8: the Cleric, Bard or Warrior 8 gains the Guardian class",
    "U": "The 7 Druid teaches a 4: the Bard, Warrior or Paladin 4 gains the Druid class",
    "T": "The 9 Chanter teaches a 2: the Cleric, Warrior or Paladin 2 gains the Chanter class",
}
MAGE_STUDENT_LABEL = "A new student: choose the 4s or the 8s; the first unstickered one revealed gains the Mage class"


def reward_steps(camp, number: int, rng: random.Random) -> List[Step]:
    """Reward steps for completing ``number``; 'auto' steps apply at once, 'choice'
    steps wait for the player. Each step is JSON-serialisable."""
    steps: List[Step] = []
    if number == 1:
        # Reward cards (confirmed): "Open pack C and corrupt a character in your party",
        # "Add the High Arcana to your party", "Acquire the new relic" (Kinfolk Flute).
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt a character in your party"))
        steps.append({"kind": "add_card", "card": HIGH_ARCANA, "label": "The High Arcana (25, no class) joins the party"})
        steps.append({"kind": "relic", "relic": "flute", "label": "Relic: Kinfolk Flute"})
    elif number == 2:
        # Reward cards (confirmed): "Open pack C and corrupt another character in your party";
        # class stickers for the first 3, 5, 7 and 9 revealed from the shuffled party. No
        # mission 2 card removes the High Arcana; mission 3's cards will say when he leaves.
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt another character in your party"))
        steps.append(_class_sticker_choice(camp, rng))
    elif number == 3:
        # Reward cards (confirmed): "Open pack C and corrupt another character in your party";
        # "Open pack F": "Add the 10 mages to your party" (A to 10 of the Mage class; Quill
        # the owl is the animal mage).
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt another character in your party"))
        steps.append({"kind": "add_cards", "cards": MAGE_DECK,
                      "label": "Open pack F: the ten mages join the party"})
    elif number == 4:
        # Reward cards (confirmed, in order): "Add Gøran to your party"; "Keep Gøran's four
        # beasts in the box beside your party. Each mission attempt you may include one of
        # these four beasts in your reserve deck"; "Open pack C and corrupt another
        # character in your party"; "Acquire the new relic" (Scarlet Whistle).
        steps.append({"kind": "add_card", "card": GORAN, "label": "Gøran (8, no class) joins the party"})
        steps.append({"kind": "set_flag", "flag": "beasts", "value": True,
                      "label": "Gøran's four beasts (B♥ B♦ B♣ B♠) wait beside the party: one may join each attempt"})
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt another character in your party"))
        steps.append({"kind": "relic", "relic": "whistle", "label": "Relic: Scarlet Whistle"})
    elif number == 5:
        # Reward cards (confirmed, in order): "Add a Warrior sticker to Gøran"; "Add Myla to
        # your party. Harore (5 Reaver) remains in your party. Remove the other three Reavers
        # from your party and return them to mission box 5"; "Open pack C and corrupt another
        # character in your party"; "Choose either James (6 Cleric), Jakhim (6 Bard) or Lee
        # (6 Paladin), then put a Reaver sticker on them."
        steps.append({"kind": "add_suit", "card_id": GORAN["id"], "suit": "C", "label": "Gøran gains the Warrior class"})
        steps.append({"kind": "add_card", "card": MYLA, "label": "Myla (7, no class) joins the party"})
        for r in REAVERS:
            if r["id"] != "5R":
                steps.append({"kind": "remove_card", "card_id": r["id"], "label": "The %s stays to defend the veil" % plain_name(r)})
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt another character in your party"))
        steps.append({"kind": "choice_suit", "suit": "R", "options": [c for c in ("6H", "6D", "6S") if P.find(camp.party, c)],
                      "label": CHOICE_SUIT_LABELS["R"]})
    elif number == 6:
        # Reward cards (confirmed, in order): "Add a Paladin sticker to Gøran"; "Open pack C
        # and corrupt another character in your party"; "Acquire the new relic" (Azure
        # Emblem); "Choose either Bronze (8 cleric), Snow (8 bard) or Shadow (8 warrior), then
        # put a Guardian sticker on them"; "Runo (3 Guardian) remains in your party. Remove
        # the other three Guardians from your party and return them to the mission 6 box."
        steps.append({"kind": "add_suit", "card_id": GORAN["id"], "suit": "S", "label": "Gøran gains the Paladin class"})
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt another character in your party"))
        steps.append({"kind": "relic", "relic": "emblem", "label": "Relic: Azure Emblem"})
        steps.append({"kind": "choice_suit", "suit": "G", "options": [c for c in ("8H", "8D", "8C") if P.find(camp.party, c)],
                      "label": CHOICE_SUIT_LABELS["G"]})
        for g in GUARDIANS:
            if g["id"] != "3G":
                steps.append({"kind": "remove_card", "card_id": g["id"], "label": "The %s stays to rebuild the garden" % plain_name(g)})
    elif number == 7:
        # Reward cards (confirmed, in order): "Add a Cleric sticker to Gøran"; "Open pack C
        # and corrupt another character in your party"; "Alantha (7 Druid) remains in your
        # party. Remove the other three Druids from your party and return them to the
        # mission 7 box"; "Choose either Glamelyn (4 bard), Herbod (4 warrior) or Dhonatir
        # (4 paladin), then put a Druid sticker on them."
        steps.append({"kind": "add_suit", "card_id": GORAN["id"], "suit": "H", "label": "Gøran gains the Cleric class"})
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt another character in your party"))
        for d in DRUIDS:
            if d["id"] != "7U":
                steps.append({"kind": "remove_card", "card_id": d["id"], "label": "The %s stays at the Well" % plain_name(d)})
        steps.append({"kind": "choice_suit", "suit": "U", "options": [c for c in ("4D", "4C", "4S") if P.find(camp.party, c)],
                      "label": CHOICE_SUIT_LABELS["U"]})
    elif number == 8:
        # Reward cards (confirmed, in order): "Add a Bard sticker to Gøran"; "Open pack C and
        # corrupt another character in your party"; "Druldox (9 Chanter) remains in your
        # party. Remove the other three Chanters..."; "Choose either Sprinkle (2 cleric), Dinky
        # (2 warrior) or Wicket (2 paladin), then put a Chanter sticker on them"; "Put the
        # puppy back in the mission 8 box."
        steps.append({"kind": "add_suit", "card_id": GORAN["id"], "suit": "D", "label": "Gøran gains the Bard class"})
        steps.append(_corrupt_choice(camp, "Open pack C: corrupt another character in your party"))
        for d in CHANTERS:
            if d["id"] != "9T":
                steps.append({"kind": "remove_card", "card_id": d["id"], "label": "The %s stays with the order" % plain_name(d)})
        steps.append({"kind": "choice_suit", "suit": "T", "options": [c for c in ("2H", "2C", "2S") if P.find(camp.party, c)],
                      "label": CHOICE_SUIT_LABELS["T"]})
        steps.append({"kind": "set_flag", "flag": "puppy_boxed", "value": True,
                      "label": "The pilgrim ace stays at Heaven's Edge (back in the mission 8 box)"})
    elif number == 9:
        # Reward cards (confirmed, in order): "Acquire the new relic" (Evergreen Mother,
        # corrupt relic); "Remove Gøran from your party. Add the new, renewed Gøran (8,
        # evergreen) to your party"; "Choose either dwarves (4) or feltrix (8). Flip cards
        # from your reserve until you reveal one of the chosen race (except Gøran or a mage)
        # that has no stickers on them. Put a Mage sticker on them"; "Add Ash (B, Mage) to
        # your party."
        steps.append({"kind": "relic", "relic": "mother", "label": "Relic: Evergreen Mother (corrupt)"})
        steps.append({"kind": "remove_card", "card_id": GORAN["id"], "label": "Gøran reaches into the Mother's soul"})
        steps.append({"kind": "add_card", "card": GORAN_RENEWED,
                      "label": "The renewed Gøran (8, Evergreen: all four classes, ignores immunity) joins the party"})
        steps.append({"kind": "choice_mage_student", "options": ["4", "8"],
                      "label": MAGE_STUDENT_LABEL})
        steps.append({"kind": "add_card", "card": ASH, "label": "Myla's beast, a B of the Mage class (B★), joins the party"})
    elif number == 10:
        # Reward cards (confirmed, in order): "Remove Gøran (8, Evergreen) from your party";
        # "Return the corrupted characters (the enemies from the previous mission) to your
        # party."
        steps.append({"kind": "remove_card", "card_id": GORAN_RENEWED["id"],
                      "label": "The floor decays to dust: Gøran and the Arcana fall into the darkness"})
        steps.append({"kind": "away_return", "label": "The infected members return to themselves, corruption halted but not cured"})
    elif number == 11:
        # Reward card (confirmed): "Add the reborn Evergreen to your party." Esme, 6, Human
        # Evergreen (holographic): the Evergreen icon, so all four basic classes, ignoring
        # immunity. The mission rules add: Gøran's beasts return to the box by the party.
        steps.append({"kind": "add_card", "card": ESME_REBORN,
                      "label": "The reborn Evergreen touches down: Esme (6, Evergreen) joins the party"})
    elif number == 12:
        # Outcome cards (confirmed): the High Arcana is dead; "Open pack E" (Eternal mode).
        steps.append({"kind": "set_flag", "flag": "pack_e_opened", "value": True,
                      "label": "A new dawn is here. Open pack E: Eternal mode"})
    return steps


# The reborn Evergreen (mission 11 reward).
ESME_REBORN: Dict[str, Any] = {"id": "ESME6E", "rank": "6", "suits": ["H", "D", "C", "S"], "value": 6, "name": "Esme",
                               "flags": ["evergreen", "ignores_immunity"]}


# The renewed Gøran (mission 9 reward): the Evergreen icon stands for cleric, bard,
# warrior and paladin at once, ignoring immunity to those four (rulebook p.15).
GORAN_RENEWED: Dict[str, Any] = {"id": "GOR8E", "rank": "8", "suits": ["H", "D", "C", "S"], "value": 8, "name": "Gøran",
                                 "flags": ["evergreen", "ignores_immunity"]}

# Myla's beast (mission 9 reward, "Ash" on the physical card): a plain B of the Mage
# class, a permanent party member. Beasts pair with one other card and copy its
# strength; alone they are worth 0.
ASH: Dict[str, Any] = {"id": "B_ASH", "rank": "B", "suits": ["M"], "value": 0, "flags": ["beast"]}


GORAN: Dict[str, Any] = {"id": "GOR8", "rank": "8", "suits": [], "value": 8, "name": "Gøran", "flags": []}

# Gøran's beasts (mission 4 reward): plain B cards, one per basic class (B♥ B♦ B♣ B♠),
# strength 0 on their own and equal to the paired card's strength while attacking.
BEASTS: List[Dict[str, Any]] = [
    {"id": "B_%s" % s, "rank": "B", "suits": [s], "value": 0, "flags": ["beast"]} for s in ("H", "D", "C", "S")
]


def plain_name(card: Dict[str, Any]) -> str:
    """A card dict named the themeless way: rank and class, e.g. "3 Reaver" or "B Cleric"."""
    suits = [CLASS_NAME.get(str(s), str(s)) for s in card.get("suits", [])]
    return ("%s %s" % (card["rank"], "/".join(suits))) if suits else str(card["rank"])


def plain_card_ids() -> set:
    """Ids of the cards the app shows as plain playing cards (no names): the beasts, the
    class decks, the mages, the pilgrims and the mercenaries."""
    from .mercenaries import MERCENARIES
    ids = {str(c["id"]) for c in BEASTS + [ASH] + MAGE_DECK + CHANTERS + DRUIDS + GUARDIANS + REAVERS + PILGRIMS}
    ids.update(str(m["card"]["id"]) for m in MERCENARIES)   # type: ignore[index]
    return ids


def strip_flavour_names(cards: List[Any]) -> int:
    """Saves from before the themeless cards gave those cards names and races: drop them
    (and every card's unused race subtitle). Returns how many cards changed."""
    ids = plain_card_ids()
    changed = 0
    for c in cards:
        if not isinstance(c, dict):
            continue
        before = len(c)
        c.pop("subtitle", None)
        if str(c.get("id")) in ids:
            c.pop("name", None)
        changed += before != len(c)
    return changed


def printed_suits(card_id: str, suits: List[str], flags: List[str]) -> Optional[List[str]]:
    """Restored cards keep their own classes (owner): only the Evergreen cards, Gøran and
    Esme, are all four basic classes. One short-lived build gave restored cards all four;
    for such a card this returns its printed classes (the basic class in its id, e.g. the
    H of "3H", plus any sticker class), else None when nothing needs undoing."""
    if "restored" not in flags or "evergreen" in flags:
        return None
    if not all(s in suits for s in BASIC_SUITS) or card_id[-1:] not in BASIC_SUITS:
        return None
    return [card_id[-1]] + [str(s) for s in suits if s not in BASIC_SUITS]


def undo_all_classes(card: Dict[str, Any]) -> bool:
    """Put a restored party card dict back to its printed classes (see ``printed_suits``)."""
    base = card.pop("base_suits", None)
    fixed = printed_suits(str(card.get("id", "")), [str(s) for s in card.get("suits", [])],
                          list(card.get("flags", [])))
    if fixed is None:
        return base is not None
    card["suits"] = [str(s) for s in base] if base else fixed
    return True


def strip_game_names(game) -> int:
    """The same for an attempt saved before the change: its plain cards lose their names
    (the current enemy too, when it is one of them: mission 10 fights the corrupted party
    members), and a restored card keeps only its own classes."""
    ids = plain_card_ids()
    changed = 0
    for cid, card in list(game.cards.items()):
        if cid in ids and card.name:
            card = card.with_changes(name="")
            game.cards[cid] = card
            changed += 1
        fixed = printed_suits(cid, list(card.suits), list(card.flags))
        if fixed is not None:
            game.cards[cid] = card.with_changes(suits=tuple(fixed))
            changed += 1
    enemy = getattr(game, "enemy", None)
    if enemy is not None and enemy.card_id in ids:
        card = game.cards[enemy.card_id]
        enemy.name = card.name or ("%s of %s" % ({"J": "Jack", "Q": "Queen", "K": "King"}.get(card.rank, card.rank),
                                                SUIT_NAME.get(card.suit or "", "no suit")))
    return changed


def beast_by_id(bid: str) -> Optional[Dict[str, Any]]:
    for b in BEASTS:
        if b["id"] == bid:
            return b
    return None


# Pack F (confirmed): the ten mages, A to 10 (the ace is the animal mage).
MAGE_DECK: List[Dict[str, Any]] = [
    {"id": "%sM" % r, "rank": r, "suits": ["M"], "value": RANK_VALUE[r], "flags": []}
    for r in ("A", "2", "3", "4", "5", "6", "7", "8", "9", "10")
]


HIGH_ARCANA: Dict[str, Any] = {"id": "ARC25", "rank": "25", "suits": [], "value": 25, "name": "High Arcana",
                               "flags": []}


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
    """Pack C's corruption: a random strength 2 to 9 not yet corrupted, then a random card
    of that strength (the owner plays a themeless deck, so no race or feature cards)."""
    return {"kind": "corrupt_random", "label": label}


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
        return "%s: %s is corrupted." % (step.get("label", "Corruption"), P.to_card(P.find(camp.party, target)).label())
    if kind == "relic":
        if step["relic"] not in camp.relics:
            camp.relics.append(step["relic"])
        from .relics import relic_name, relic_text
        return "Gained relic: %s. %s" % (relic_name(step["relic"]), relic_text(step["relic"], camp.players))
    if kind == "add_card":
        if P.find(camp.party, str(step["card"]["id"])) is None:
            P.add_card(camp.party, step["card"])
        return "%s joins the party." % P.to_card(step["card"]).label()
    if kind == "remove_card":
        c = P.remove_card(camp.party, step["card_id"])
        return "%s leaves the party." % (P.to_card(c).label() if c else step["card_id"])
    if kind == "add_suit":
        card = P.find(camp.party, str(step["card_id"]))
        if card is None:
            return "%s is not in the party; no sticker added." % step["card_id"]
        P.add_suit(camp.party, str(step["card_id"]), str(step["suit"]))
        return str(step.get("label", "%s gains %s" % (P.to_card(card).label(), CLASS_NAME[str(step["suit"])])))
    if kind == "choice_suit":
        options = [str(x) for x in step.get("options", [])]
        if not options:
            return "No character qualifies for the sticker."
        if option is None:
            raise ValueError("choose a character for the sticker")
        if option not in options:
            raise ValueError("%s is not one of the choices" % option)
        P.add_suit(camp.party, str(option), str(step["suit"]))
        return "%s gains the %s class." % (P.to_card(P.find(camp.party, str(option))).label(), CLASS_NAME[str(step["suit"])])
    if kind == "choice_mage_student":
        options = [str(x) for x in step.get("options", ["4", "8"])]
        if option is None:
            raise ValueError("choose the 4s or the 8s")
        if str(option) not in options:
            raise ValueError("%s is not one of the choices" % option)
        # "Flip cards from your reserve until you reveal one of the chosen race (except
        # Gøran or a mage) that has no stickers on them": a random card of that strength
        # with its single original class and no class sticker (pack C: corruption is a
        # sleeve, not a sticker, so a corrupted card may be picked).
        pool = sorted(str(c["id"]) for c in camp.party
                      if c["rank"] == str(option) and not c.get("name") and len(c.get("suits", [])) == 1
                      and c["suits"][0] in BASIC_SUITS)
        if not pool:
            return "No unstickered %s left in the party: the mages find no student." % option
        target = rng.choice(pool)
        P.add_suit(camp.party, target, "M")
        return "%s takes up the mages' studies: gains the Mage class." % P.to_card(P.find(camp.party, target)).label()
    if kind == "restore_all":
        changed = []
        for c in camp.party:
            flags = list(c.get("flags", []))
            if "corrupted" in flags:
                flags.remove("corrupted")
                if "restored" not in flags:
                    flags.append("restored")
                c["flags"] = flags
                changed.append(P.to_card(c).label())
            elif c["id"] == ESME_REBORN["id"] and "restored" not in flags:
                flags.append("restored")
                c["flags"] = flags
                changed.append(P.to_card(c).label())
        camp.corrupted = []
        return "Restored: %s." % ", ".join(changed) if changed else "Nobody needed restoring."
    if kind == "relic_swap":
        if step["old"] in camp.relics:
            camp.relics.remove(step["old"])
        if step["new"] not in camp.relics:
            camp.relics.append(step["new"])
        return str(step.get("label", "Relic %s replaces %s." % (step["new"], step["old"])))
    if kind == "rip_up":
        camp.flags["vine_ripped"] = True
        cid = step.get("card_id")
        if not cid:
            return "No corrupted 6 wears the cloak of the Eternal Vine; nobody is ripped up."
        c = P.remove_card(camp.party, str(cid))
        if str(cid) in camp.corrupted:
            camp.corrupted.remove(str(cid))
        return "%s dies at the machine: the card is ripped up." % (P.to_card(c).label() if c else cid)
    if kind == "choice_rip":
        options = [str(x) for x in step.get("options", [])]
        if not options:
            camp.flags["vine_ripped"] = True
            return "No corrupted character wears a cloak of the Eternal Vine; nothing is ripped up."
        if option is None:
            raise ValueError("choose the character to rip up")
        if option not in options:
            raise ValueError("%s is not one of the choices" % option)
        c = P.remove_card(camp.party, str(option))
        if str(option) in camp.corrupted:
            camp.corrupted.remove(str(option))
        camp.flags["vine_ripped"] = True
        return "%s dies at the machine: the card is ripped up." % (P.to_card(c).label() if c else option)
    if kind == "corrupted_leave":
        moved = []
        for cid in P.corrupted_ids(camp.party):
            c = P.remove_card(camp.party, cid)
            if c is not None:
                camp.away.append(dict(c))
                moved.append(P.to_card(c).label())
        return "The corrupted characters leave the party: %s." % ", ".join(moved) if moved else "No corrupted character to remove."
    if kind == "away_return":
        back = []
        for c in list(camp.away):
            if P.find(camp.party, str(c["id"])) is None:
                P.add_card(camp.party, dict(c))
            back.append(P.to_card(c).label())
        camp.away = []
        return "Back in the party: %s." % ", ".join(back) if back else "Nobody was away."
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
