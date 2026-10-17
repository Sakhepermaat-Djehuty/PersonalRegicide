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


EVENTS: List[Event] = [
    # cards in the hand and on the table
    Event("card_select", "Cards", "Select a card", "You tap a card in your hand to add it to your play.", -24, 0.25),
    Event("card_deselect", "Cards", "Deselect a card", "You tap a selected card again to take it back.", -26, 0.25),
    Event("play", "Cards", "Play an attack", "Your selected cards go onto the table against the enemy.", -19, 0.9),
    Event("draw", "Cards", "Draw cards", "Cards come into your hand (a Bard's draw, a refill).", -21, 1.0),
    Event("shuffle", "Cards", "Shuffle", "A pile is shuffled (a Cleric's heal, a new castle).", -21, 1.6),
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
    # music: any track can be picked for the menus, the table or the final enemies
    Event("music", "Music", "Music", "A looping track; pick one for the menus, one for the table and one for the "
                                        "Kings (or none).", -21, 150.0, 20.0, "music"),
]

EVENT_BY_ID: Dict[str, Event] = {e.id: e for e in EVENTS}


@dataclass
class Candidate:
    event: str                       # an Event id
    id: str                          # short, unique within the event: lowercase, digits and _
    name: str                        # what the picker page shows ("Paper flick")
    note: str                        # one line: what it sounds like
    render: Callable[[], np.ndarray] = field(repr=False)
    tags: List[str] = field(default_factory=list)     # e.g. ["warm", "wooden"]; music: ["menu", "table", "boss"]
    loop_seconds: Optional[float] = None              # music: the loop's exact length (render_loop's)
    bpm: Optional[float] = None                       # music, optional

    def key(self) -> str:
        return "%s/%s" % (self.event, self.id)
