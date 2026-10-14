"""Persistent campaign state and the attempt / result flow."""
from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional

from ..engine import Game
from ..rules import GameConfig
from . import missions as M
from . import party as P
from .mercenaries import by_id


class CampaignState:
    VERSION = 1

    def __init__(self) -> None:
        self.created = time.strftime("%Y-%m-%d")
        self.last_played = time.strftime("%Y-%m-%d %H:%M")
        self.slot = ""                       # save-slot id (set by the app's store)
        self.name = "Campaign"
        self.players = 1
        self.names: List[str] = ["Player 1"]
        self.party: List[dict] = P.starting_party()
        self.relics: List[str] = []
        self.corrupted: List[str] = []
        self.flags: Dict[str, Any] = {}
        self.mission = 1                 # current mission number
        self.completed: List[int] = []
        self.attempts: Dict[str, int] = {}   # mission -> attempts
        self.losses: Dict[str, int] = {}     # mission -> losses
        self.coins = 0
        self.m_box_opened = False
        self.beast: Optional[str] = None     # Gøran's beast chosen for the next attempt (mission 4 reward)
        self.mercenaries: List[str] = []     # hired for the current mission (kept across failed attempts)
        self.swaps_allowed = False           # same-cost swaps are allowed after a failure, until the next attempt
        self.pending: List[dict] = []        # reward steps awaiting a choice
        self.log: List[str] = []
        self.lore_seen: List[str] = []       # lore entry ids revealed in this campaign
        self.reveal_all = False
        self.seed = random.SystemRandom().randrange(2 ** 31)
        self.rng_calls = 0
        self.finished = False

    # ------------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        return {
            "version": self.VERSION, "created": self.created, "last_played": self.last_played,
            "slot": self.slot, "name": self.name, "lore_seen": list(self.lore_seen),
            "players": self.players,
            "names": list(self.names), "party": [dict(c) for c in self.party],
            "relics": list(self.relics), "corrupted": list(self.corrupted), "flags": dict(self.flags),
            "mission": self.mission, "completed": list(self.completed),
            "attempts": dict(self.attempts), "losses": dict(self.losses), "coins": self.coins,
            "m_box_opened": self.m_box_opened, "mercenaries": list(self.mercenaries),
            "swaps_allowed": self.swaps_allowed, "beast": self.beast,
            "pending": [dict(s) for s in self.pending], "log": list(self.log),
            "reveal_all": self.reveal_all, "seed": self.seed, "rng_calls": self.rng_calls,
            "finished": self.finished,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CampaignState":
        c = cls()
        for k, v in d.items():
            if k == "version":
                continue
            setattr(c, k, v)
        if "swaps_allowed" not in d:
            c._migrate_coin_rule()
        return c

    def _migrate_coin_rule(self) -> None:
        """Saves from before the rulebook coin rule gave coins = failures of the current
        mission per attempt and dropped hired mercenaries. Under the rulebook each failure
        adds its number of coins (1, 3, 6, 10 in total), so such a save undercounts. Bring
        the balance up to the rulebook total minus the cost of whatever is hired; coins
        already spent on mercenaries that vanished cannot be reconstructed."""
        if self.finished:
            return
        losses = self.losses_on(self.mission)
        total = losses * (losses + 1) // 2
        spent = 0
        for mid in self.mercenaries:
            try:
                spent += int(by_id(mid)["cost"])
            except KeyError:
                pass
        self.coins = max(int(self.coins), total - spent)
        if losses:
            self.swaps_allowed = True

    @classmethod
    def new(cls, players: int, names: Optional[List[str]] = None, seed: Optional[int] = None,
            name: str = "Campaign") -> "CampaignState":
        c = cls()
        c.players = players
        c.name = name
        c.names = list(names or ["Player %d" % (i + 1) for i in range(players)])
        if seed is not None:
            c.seed = seed
        c.log.append("Campaign started with %d player%s." % (players, "" if players == 1 else "s"))
        c.reveal_lore("m1_intro")
        return c

    def touch(self) -> None:
        self.last_played = time.strftime("%Y-%m-%d %H:%M")

    def reveal_lore(self, entry_id: str) -> None:
        if entry_id not in self.lore_seen:
            self.lore_seen.append(entry_id)

    def _rng(self) -> random.Random:
        """A deterministic stream per campaign; advances per use so saves replay."""
        self.rng_calls += 1
        return random.Random((self.seed * 1000003 + self.rng_calls) & 0x7FFFFFFF)

    # ------------------------------------------------------------------ queries
    def current(self) -> dict:
        return M.mission(self.mission)

    def revealed(self, number: int) -> bool:
        return self.reveal_all or number <= self.mission

    def attempts_on(self, number: int) -> int:
        return self.attempts.get(str(number), 0)

    def losses_on(self, number: int) -> int:
        return self.losses.get(str(number), 0)

    def party_cards(self):
        return [P.to_card(c) for c in self.party]

    # ------------------------------------------------------------------ attempts
    def start_attempt(self, seed: Optional[int] = None) -> Game:
        if self.pending:
            raise RuntimeError("resolve the pending reward choices first")
        if self.finished:
            raise RuntimeError("the campaign is complete")
        number = self.mission
        rng = self._rng()
        if self.attempts_on(number) == 0:
            # the mission's setup cards (permanent changes before the first attempt)
            for step in M.start_steps(self, number):
                self.log.append(M.apply_step(self, step, rng))
        extra = M.build_setup(self, number, rng)
        cfg = GameConfig(players=self.players, names=tuple(self.names), rules_id=M.mission(number)["rules_id"],
                         extra=extra)
        self.attempts[str(number)] = self.attempts_on(number) + 1
        self.swaps_allowed = False
        self.touch()
        self.reveal_lore("m%d_intro" % number)
        g = Game.new(cfg, seed=seed if seed is not None else rng.randrange(2 ** 31))
        return g

    def finish_attempt(self, game: Game) -> dict:
        """Record a finished attempt. Returns a summary dict for the UI."""
        number = int(game.config.extra.get("mission", self.mission))
        if number != self.mission:
            raise RuntimeError("attempt is for mission %d but the campaign is at %d" % (number, self.mission))
        name = M.mission(number)["title"]
        self.touch()
        if game.result != "loss":
            # Rulebook p.25 (sticker): on success all mercenaries return to the mercenary
            # box and the next mission starts with none.
            if self.mercenaries:
                self.log.append("The mercenaries go back to their lives.")
                self.mercenaries = []
            self.completed.append(number)
            self.log.append("Mission %d (%s) completed on attempt %d." % (number, name, self.attempts_on(number)))
            self.reveal_lore("m%d_outcome" % number)
            applied = []
            rng = self._rng()
            for step in M.reward_steps(self, number, rng):
                if step["kind"].startswith("choice"):
                    self.pending.append(step)
                else:
                    line = M.apply_step(self, step, rng)
                    applied.append(line)
                    self.log.append(line)
            # Unspent coins are dropped here too. The sticker says nothing about coins on
            # success; this is an engine assumption the owner has not confirmed.
            self.coins = 0
            if number >= len(M.MISSIONS):
                self.finished = True
                self.log.append("Campaign complete!")
                self.reveal_lore("campaign_end")
            else:
                self.mission = number + 1
            return {"won": True, "rewards": applied, "pending": list(self.pending)}
        self.losses[str(number)] = self.losses_on(number) + 1
        # Rulebook p.25 (sticker), confirmed by the owner: each time you lose a mission
        # you GAIN coins equal to the number of times you have lost it (1, then 2, then
        # 3: 1 -> 3 -> 6 -> 10 in total). Hired mercenaries stay for the next attempt and
        # unspent coins carry over; after each failure one may be swapped for another of
        # the same cost (see ``swap``).
        earned = self.losses_on(number)
        self.coins += earned
        self.swaps_allowed = True
        kept = ""
        if self.mercenaries:
            kept = " %d mercenar%s stay%s on." % (len(self.mercenaries), "y" if len(self.mercenaries) == 1 else "ies",
                                                 "s" if len(self.mercenaries) == 1 else "")
        self.log.append("Mission %d (%s) lost (attempt %d). +%d coin%s (%d to spend).%s" % (
            number, name, self.attempts_on(number), earned, "" if earned == 1 else "s", self.coins, kept))
        opened = False
        if not self.m_box_opened:
            self.m_box_opened = True
            opened = True
            self.log.append("Pack M opened: mercenaries are for hire between attempts.")
            self.reveal_lore("pack_m")
        return {"won": False, "coins": self.coins, "earned": earned, "m_box_opened_now": opened}

    # ------------------------------------------------------------------ Gøran's beasts
    def beasts_available(self) -> List[dict]:
        """The beasts that may be included in the next attempt (after mission 4)."""
        if not self.flags.get("beasts"):
            return []
        return [dict(b) for b in M.BEASTS]

    def set_beast(self, beast_id: Optional[str]) -> None:
        """Rulebook p.7: for each attempt you may choose one of Gøran's beasts and include
        it in your reserve; after each attempt you may swap it for one of the others."""
        if beast_id is not None:
            if not self.flags.get("beasts"):
                raise ValueError("Gøran's beasts are not with the party yet")
            if M.beast_by_id(beast_id) is None:
                raise ValueError("unknown beast %s" % beast_id)
        self.beast = beast_id
        self.touch()

    # ------------------------------------------------------------------ reward choices
    def pending_choice(self) -> Optional[dict]:
        """The reward step waiting for the player's decision, if any."""
        return dict(self.pending[0]) if self.pending else None

    def resolve_choice(self, option: Any) -> str:
        """Apply the first pending reward step with the player's ``option``; returns the
        log line. Raises ValueError when the option is not allowed."""
        if not self.pending:
            raise ValueError("nothing to choose")
        step = self.pending[0]
        line = M.apply_step(self, step, self._rng(), option=option)
        self.pending.pop(0)
        self.log.append(line)
        self.touch()
        return line

    # ------------------------------------------------------------------ mercenaries
    def hireable(self) -> List[dict]:
        if not self.m_box_opened:
            return []
        out = []
        from .mercenaries import MERCENARIES
        for m in MERCENARIES:
            if m["id"] in self.mercenaries:
                continue
            out.append({"id": m["id"], "name": m["name"], "cost": m["cost"], "affordable": self.coins >= m["cost"]})
        return out

    def hire(self, mid: str) -> None:
        m = by_id(mid)
        if mid in self.mercenaries:
            raise ValueError("already hired")
        if self.coins < m["cost"]:
            raise ValueError("not enough coins")
        self.coins -= int(m["cost"])
        self.mercenaries.append(mid)
        self.log.append("Hired %s for %d coin%s." % (m["name"], m["cost"], "" if m["cost"] == 1 else "s"))

    def swappable(self, mid: str) -> List[dict]:
        """Mercenaries that ``mid`` (already hired) may be swapped for: same cost, not hired."""
        if mid not in self.mercenaries or not self.swaps_allowed:
            return []
        cost = by_id(mid)["cost"]
        from .mercenaries import MERCENARIES
        return [{"id": m["id"], "name": m["name"], "cost": m["cost"]}
                for m in MERCENARIES if m["cost"] == cost and m["id"] not in self.mercenaries]

    def swap(self, old_id: str, new_id: str) -> None:
        """Rulebook p.25 (sticker): after each failure you may swap any previously selected
        mercenary with another of the same cost. Free; allowed until the next attempt starts."""
        if old_id not in self.mercenaries:
            raise ValueError("not hired")
        if not self.swaps_allowed:
            raise ValueError("swaps are only allowed after a failed attempt")
        if new_id in self.mercenaries:
            raise ValueError("already hired")
        old, new = by_id(old_id), by_id(new_id)
        if old["cost"] != new["cost"]:
            raise ValueError("swaps must be for a mercenary of the same cost")
        self.mercenaries[self.mercenaries.index(old_id)] = new_id
        self.log.append("Swapped %s for %s." % (old["name"], new["name"]))
