"""What the game makes a sound for, and how a candidate sound is described.

A family module in ``families/`` (cards.py, combat.py, ...) lists its candidates:

    from catalog import Candidate
    import synth as A

    def _soft_tick():
        return A.tick(2600, 0.04) * 0.8

    CANDIDATES = [
        Candidate("card_select", "soft_tick", "Soft tick", "A light fingertip tick.", _soft_tick),
    ]

``render`` returns the raw sound (mono for effects and jingles, stereo for music, any
level); ``build.py`` masters it to the event's loudness and checks its length.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np


@dataclass(frozen=True)
class Event:
    id: str
    group: str            # "Cards", "Combat", "Class powers", "Table and menus", "Jingles", "Music"
    title: str            # shown on the picker page
    when: str             # when the game plays it
    loudness_db: float    # gated RMS target after mastering
    max_seconds: float    # a candidate longer than this is rejected
    min_seconds: float = 0.02
    kind: str = "effect"  # "effect" (mono, played on demand), "jingle" (mono, once), "music" (stereo loop)


# Info pop-ups (app/info.py ROWS, docs/INFO_POPUPS.md "Melody plan"): every card of the
# queue shown after an action plays its own short clip, "info_<row id>", 2.0 to 2.4 s (the
# four Jester rows 2.6 s: the Whistle jig with one more bar). Battle start, Victory and
# Defeat play the mission_start, victory and loss jingles instead, so they have no event.
# Mastered as jingles at about -20 dB; Turn and Yield 3 dB softer, Enemy attacks, Exact
# kill! and IMMUNITY 1.5 dB louder.
def _info(row: str, title: str, when: str, loudness_db: float = -20.0, max_seconds: float = 2.4) -> Event:
    return Event("info_" + row, "Info pop-ups", title, when, loudness_db, max_seconds, 2.0, "jingle")


INFO_EVENTS: List[Event] = [
    # turn
    _info("turn", "Turn", "A new turn begins (2+ players: it names who plays next).", -23),
    _info("yield", "Yield", "A player yields the turn.", -23),
    # the attack's cards entering play
    _info("corrupted", "Corrupted", "A corrupted card enters play and a card is banished."),
    _info("restored", "Restored", "A restored card enters play."),
    _info("declared", "Declared", "A card's value or class is declared as it enters play."),
    _info("kinfolk_flute", "Kinfolk Flute", "The Kinfolk Flute can grow the attack, just before its box."),
    _info("scarlet_whistle", "Scarlet Whistle", "The Scarlet Whistle can add or take a card, just before its box."),
    _info("azure_emblem", "Azure Emblem", "The Azure Emblem places or keeps peeked cards, just before its box."),
    _info("mother_corrupt", "Mother (corrupt)", "The corrupt Evergreen Mother asks for a banish, just before her box."),
    _info("mother_restored", "Mother (restored)", "The restored Evergreen Mother saves banished cards."),
    # the Jester (the Whistle jig)
    _info("jester", "Jester (base)", "A Jester is played (base game, 2+ players).", max_seconds=2.6),
    _info("jester_claim", "Jester claim", "A Jester is played to claim the next turn (Legacy, 2+ players).",
          max_seconds=2.6),
    _info("solo_jester_refresh", "Solo Jester: new hand", "A solo Jester discards the hand and draws a new one.",
          max_seconds=2.6),
    _info("solo_jester_attack", "Solo Jester: attack", "A solo Jester is played as an attack (Legacy solo).",
          max_seconds=2.6),
    # the classes
    _info("immunity", "IMMUNITY", "Any class card stamped IMMUNITY: the enemy blocks that power.", -18.5),
    _info("mage", "Mage", "A Mage peeks at the reserve, just before the pick box."),
    _info("druid", "Druid", "A Druid deals cards, just before the sorting box."),
    _info("cleric", "Cleric", "A Cleric heals cards from the discard pile into the reserve."),
    _info("bard", "Bard", "A Bard draws cards for the party."),
    _info("chanter", "Chanter", "A Chanter calls a number, just before the number box."),
    _info("reaver", "Reaver", "A Reaver digs into the reserve, just before the count box."),
    _info("warrior", "Warrior", "A Warrior doubles the attack's damage."),
    _info("paladin", "Paladin", "A Paladin's shield lowers the enemy's attack."),
    _info("guardian", "Guardian", "A Guardian protects the party."),
    # damage and defeat
    _info("damage", "Damage", "The attack deals its damage (no Warrior doubling it)."),
    _info("defeated", "Defeated", "The enemy is defeated (not exactly)."),
    _info("exact_kill", "Exact kill!", "The enemy is defeated exactly and joins the party's cards.", -18.5),
    _info("cleanup", "Clean-up", "After a kill: the played cards are cleared away."),
    _info("team_damage", "Team damage", "Every player must pay team damage."),
    # the enemy
    _info("new_enemy", "New enemy", "The next enemy is revealed from the castle."),
    _info("enemy_shift", "Enemy changes", "A pile top changes mid-attack and so changes the enemy."),
    _info("enemy_attack", "Enemy attacks", "The enemy strikes back: damage to pay, just before the discard box.",
          -18.5),
    _info("shielded", "No damage", "The enemy's attack is shielded to nothing."),
    _info("feign_death", "Feign death", "A player feigns death to escape the enemy's attack."),
    _info("damage_paid", "Damage paid", "The enemy's attack is paid with discarded cards."),
    # missions
    _info("hydra_regrows", "2 · Hydra regrows", "Mission 2: a defeated Hydra head goes back under the castle."),
    _info("m3_zone", "3 · Zone grows", "Mission 3, end of turn: the zone gives the enemy a new immunity."),
    _info("m5_zone", "5 · Zone grows", "Mission 5, end of turn: the zone makes the enemy stronger."),
    _info("m5_carry", "5 · Carry damage", "Mission 5: extra damage carries on to the next enemy."),
    _info("m7_pilgrim", "7 · Pilgrim arrives", "Mission 7, start of turn: a pilgrim joins the zone."),
    _info("m7_match", "7 · Pilgrim match", "Mission 7: a played card matches a pilgrim, just before the box."),
    _info("m8_filled", "8 · Zone filled!", "Mission 8, at a kill: the zone is filled, just before the banish box."),
    _info("m9_piles", "9 · Captured piles", "Mission 9, end of turn: a captured pile can be rescued, before its box."),
    _info("m10_zone", "10 · Zone grows", "Mission 10, start of turn: the zone makes the enemy stronger."),
    _info("m10_cleric", "10 · Cleric enemy", "Mission 10, end of turn: the corrupted Cleric heals the zone."),
    _info("m10_bard", "10 · Bard enemy", "Mission 10, end of turn: the corrupted Bard wants a card, before its box."),
    _info("m11_beast", "11 · Beast", "Mission 11, start of turn: a beast is revealed and acts."),
    _info("m11_beast_H", "11 · Beast: Cleric", "Mission 11: a Cleric beast is revealed (its own clip)."),
    _info("m11_beast_D", "11 · Beast: Bard", "Mission 11: a Bard beast is revealed (its own clip)."),
    _info("m11_beast_C", "11 · Beast: Warrior", "Mission 11: a Warrior beast is revealed (its own clip)."),
    _info("m11_beast_S", "11 · Beast: Paladin", "Mission 11: a Paladin beast is revealed (its own clip)."),
    _info("m12_zone", "12 · Zone grows", "Mission 12, start of turn: the zone makes the enemy stronger and immune."),
    # Evergreen: locations
    _info("shrine", "Shrine", "Evergreen, end of turn at the Shrine: a reserve card joins the zone."),
    _info("cave", "Cave", "Evergreen, end of turn in the Cave: a reserve card joins the zone."),
    _info("cave_collapse", "Cave collapses", "Evergreen, end of turn: the Cave's zone collapses."),
    _info("forest", "Forest", "Evergreen, end of turn in the Forest: a banished card joins the zone."),
    _info("hills", "Hills", "Evergreen, end of turn in the Hills: a banished card joins the zone."),
    _info("lake", "Lake", "Evergreen, start of turn at the Lake: a card joins the zone."),
    # Evergreen: banes
    _info("bane10", "Poisonous Clerics", "Bane 10, end of turn: discarded cards feed the zone."),
    _info("bane12", "Duplicitous Bards", "Bane 12, end of turn: the zone demands a card, before its box."),
    _info("bane14", "Absorbtion", "Bane 14, at a kill: the zone absorbs cards."),
    _info("bane15", "Tread Carefully", "Bane 15, at a non-exact kill: discard cards are banished."),
    _info("bane16", "Lingering Dread", "Bane 16, start of turn: the dread lingers."),
    _info("bane21", "Eye-Level Sticks", "Bane 21, in an attack: a card must be discarded, before its box."),
    _info("bane22", "The Fiery Crucible", "Bane 22, start of turn: the crucible burns."),
    _info("bane23", "Choose Your Poison", "Bane 23, end of turn: choose a poison, before its box."),
    # Evergreen: boons
    _info("boon30", "Squad of Siblings", "Boon 30, in an attack: a sibling can join from the zone, before its box."),
    _info("boon31", "Selfless Rescue", "Boon 31, after paying damage: a zone card can be rescued, before its box."),
    _info("boon32", "Precision Strike", "Boon 32, at an exact kill: a precision strike, before its box."),
    _info("boon33", "Restored Arrows", "Boon 33, at an exact kill: arrows are restored, before its box."),
    _info("boon35", "A Close Call", "Boon 35, after paying damage: a close call, before its pick box."),
]


EVENTS: List[Event] = [
    # cards in the hand and on the table
    Event("card_select", "Cards", "Select a card", "You tap a card in your hand to add it to your play.", -24, 0.25),
    # deselect sits 4 dB under select: their weight is in the bass a phone speaker hardly
    # plays, so 2 dB on paper came out level on the phone
    Event("card_deselect", "Cards", "Deselect a card", "You tap a selected card again to take it back.", -28, 0.25),
    Event("play", "Cards", "Play an attack", "Your selected cards go onto the table against the enemy.", -19, 0.9),
    Event("draw", "Cards", "Draw cards", "Cards come into your hand (a Bard's draw, a refill).", -21, 1.0),
    # a riffle's thrum sits under 150 Hz: 2 dB more, to sound as loud as a draw on a phone
    Event("shuffle", "Cards", "Shuffle", "A pile is shuffled (a Cleric's heal, a new castle).", -19, 1.6),
    Event("discard", "Cards", "Discard to suffer", "You discard cards to pay the enemy's attack.", -21, 0.9),
    # the fight
    Event("hit", "Combat", "Damage the enemy", "Your attack deals damage and the enemy survives.", -18, 1.0),
    Event("defeat_enemy", "Combat", "Defeat an enemy", "An enemy's health reaches zero.", -17, 2.0),
    Event("exact_kill", "Combat", "Exact kill", "An attack defeats the enemy exactly: it joins your deck.", -17, 2.4),
    Event("new_enemy", "Combat", "A new enemy", "The next enemy is drawn from the castle.", -20, 2.0),
    Event("suffer", "Combat", "Take a hit", "The enemy attacks and you must suffer damage.", -18, 1.4),
    Event("jester", "Combat", "Jester", "A Jester is played (immunity cancelled, or a solo Jester power).", -19, 2.0),
    Event("yield", "Combat", "Yield", "You yield your turn.", -23, 1.2),
    # class powers
    Event("power_heal", "Class powers", "Heal (Cleric)", "Cards return from the discard pile to the reserve.", -21, 1.6),
    Event("power_double", "Class powers", "Double damage (Warrior)", "A Warrior doubles the attack's damage.", -19, 1.2),
    Event("power_shield", "Class powers", "Shield (Paladin)", "A Paladin's shield lowers the enemy's attack.", -20, 1.2),
    Event("power_blocked", "Class powers", "Immune", "The enemy is immune: a class power does nothing.", -21, 1.0),
    # menus and the rest of the table
    Event("button", "Table and menus", "Button", "Any button tap (Play, Yield, menus).", -27, 0.15),
    Event("popup", "Table and menus", "Card pop-up", "A card pop-up opens (rules, a relic, a mercenary).", -24, 0.7),
    Event("coin", "Table and menus", "Coins", "You hire a mercenary or earn coins.", -20, 1.2),
    Event("error", "Table and menus", "Not allowed", "A tap that cannot be done (an illegal play).", -24, 0.6),
    # jingles
    Event("victory", "Jingles", "Victory", "You win a game or a mission.", -17, 6.0, 0.5, "jingle"),
    Event("loss", "Jingles", "Loss", "You lose a game or a mission attempt.", -19, 6.0, 0.5, "jingle"),
    Event("mission_start", "Jingles", "Mission start", "A new mission or attempt begins.", -19, 5.0, 0.5, "jingle"),
    # info pop-ups: one clip per card (INFO_EVENTS above)
    *INFO_EVENTS,
    # music: any track can be picked for the menus or for each stage of the castle
    Event("music", "Music", "Music", "A looping track; pick one for the menus and one for each stage of the castle: "
                                        "the Jacks, the Queens and the Kings (or none).", -21, 150.0, 20.0, "music"),
]

EVENT_BY_ID: Dict[str, Event] = {e.id: e for e in EVENTS}


@dataclass
class Candidate:
    event: str                       # an Event id
    id: str                          # short, unique within the event: lowercase, digits and _
    name: str                        # what the picker page shows ("Paper flick")
    note: str                        # one line: what it sounds like
    render: Callable[[], np.ndarray] = field(repr=False)
    tags: List[str] = field(default_factory=list)     # e.g. ["warm", "wooden"]; music: ["menu", "jack", "queen", "king"]
    loop_seconds: Optional[float] = None              # music: the loop's exact length (render_loop's)
    bpm: Optional[float] = None                       # music, optional

    def key(self) -> str:
        return "%s/%s" % (self.event, self.id)
