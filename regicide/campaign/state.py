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
        self.mercenaries: List[str] = []     # hired for the current mission
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
        return c

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
        extra = M.build_setup(self, number, rng)
        cfg = GameConfig(players=self.players, names=tuple(self.names), rules_id=M.mission(number)["rules_id"],
                         extra=extra)
        self.attempts[str(number)] = self.attempts_on(number) + 1
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
        # Mercenaries are hired for one attempt only (official: never kept).
        if self.mercenaries:
            self.log.append("The mercenaries go back to their lives.")
            self.mercenaries = []
        if game.result != "loss":
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
            self.coins = 0
            if number >= len(M.MISSIONS):
                self.finished = True
                self.log.append("Campaign complete!")
                self.reveal_lore("campaign_end")
            else:
                self.mission = number + 1
            return {"won": True, "rewards": applied, "pending": list(self.pending)}
        self.losses[str(number)] = self.losses_on(number) + 1
        # Official: coins for an attempt equal the number of times the mission has been
        # failed so far; nothing carries over.
        self.coins = self.losses_on(number)
        self.log.append("Mission %d (%s) lost (attempt %d). %d coin%s to spend on the next attempt." % (
            number, name, self.attempts_on(number), self.coins, "" if self.coins == 1 else "s"))
        opened = False
        if not self.m_box_opened:
            self.m_box_opened = True
            opened = True
            self.log.append("Pack M opened: mercenaries are for hire between attempts.")
            self.reveal_lore("pack_m")
        return {"won": False, "coins": self.coins, "earned": self.coins, "m_box_opened_now": opened}

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
