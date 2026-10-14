"""Persistent campaign state and the attempt / result flow."""
from __future__ import annotations

import copy
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from ..engine import Game
from ..rules import HAND_SIZE, GameConfig
from . import evergreen as E
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
        self.away: List[dict] = []           # party cards temporarily out of the party (mission 10's corrupted enemies)
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
        # Evergreen mode (pack E, after mission 12): the current generated setup and its
        # record. ``setup`` is the compact form (location letter, bane and boon numbers),
        # ``options`` the two rules-card variants for the next draw, ``coins`` and
        # ``mercenaries`` boon 24's five-coin budget for this setup only.
        self.evergreen: Dict[str, Any] = self._fresh_evergreen()

    @staticmethod
    def _fresh_evergreen() -> Dict[str, Any]:
        return {"setup": None, "options": {"extra_red": False, "extra_bane": False}, "attempts": 0, "losses": 0,
                "coins": 0, "mercenaries": [], "wins": 0, "played": 0}

    # ------------------------------------------------------------------ persistence
    def to_dict(self) -> dict:
        return {
            "version": self.VERSION, "created": self.created, "last_played": self.last_played,
            "slot": self.slot, "name": self.name, "lore_seen": list(self.lore_seen),
            "players": self.players,
            "names": list(self.names), "party": [dict(c) for c in self.party],
            "relics": list(self.relics), "corrupted": list(self.corrupted), "flags": dict(self.flags),
            "away": [dict(c) for c in self.away],
            "mission": self.mission, "completed": list(self.completed),
            "attempts": dict(self.attempts), "losses": dict(self.losses), "coins": self.coins,
            "m_box_opened": self.m_box_opened, "mercenaries": list(self.mercenaries),
            "swaps_allowed": self.swaps_allowed, "beast": self.beast,
            "pending": [dict(s) for s in self.pending], "log": list(self.log),
            "reveal_all": self.reveal_all, "seed": self.seed, "rng_calls": self.rng_calls,
            "finished": self.finished, "evergreen": copy.deepcopy(self.evergreen),
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
        c._migrate_plain_cards()
        return c

    def _migrate_plain_cards(self) -> None:
        """The app's cards are themeless: beasts, class decks, mages, pilgrims and
        mercenaries carry no names. Older saves stored names on the party's cards and on
        cards waiting in reward steps; drop them."""
        M.strip_flavour_names(self.party)
        M.strip_flavour_names(self.away)
        for step in self.pending:
            if isinstance(step.get("card"), dict):
                M.strip_flavour_names([step["card"]])
            if isinstance(step.get("cards"), list):
                M.strip_flavour_names(step["cards"])

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
    def start_attempt(self, seed: Optional[int] = None, open_hands: bool = False) -> Game:
        if self.pending:
            raise RuntimeError("resolve the pending reward choices first")
        if self.finished:
            raise RuntimeError("the campaign is complete")
        number = self.mission
        if self.prepare_mission():
            raise RuntimeError("resolve the mission's setup choices first")
        rng = self._rng()
        if self.attempts_on(number) == 0:
            # the mission's setup cards (permanent changes before the first attempt)
            for step in M.start_steps(self, number):
                self.log.append(M.apply_step(self, step, rng))
        extra = M.build_setup(self, number, rng)
        cfg = GameConfig(players=self.players, names=tuple(self.names), rules_id=M.mission(number)["rules_id"],
                         extra=extra, open_hands=bool(open_hands) and self.players > 1)
        self.attempts[str(number)] = self.attempts_on(number) + 1
        self.swaps_allowed = False
        self.touch()
        self.reveal_lore("m%d_intro" % number)
        g = Game.new(cfg, seed=seed if seed is not None else rng.randrange(2 ** 31))
        return g

    def prepare_mission(self) -> bool:
        """Queue the current mission's setup choices (cards read before the first attempt
        that need a decision, e.g. mission 11's rip-up). Returns True when a choice is now
        pending, so the caller shows the choice screen before starting the attempt."""
        if self.finished or self.attempts_on(self.mission) > 0:
            return bool(self.pending)
        for step in M.start_steps(self, self.mission):
            if step["kind"].startswith("choice") and step not in self.pending:
                self.pending.append(step)
        return bool(self.pending)

    def finish_attempt(self, game: Game) -> dict:
        """Record a finished attempt. Returns a summary dict for the UI."""
        if game.config.extra.get("evergreen"):
            return self.finish_evergreen_attempt(game)
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

    # ------------------------------------------------------------------ Evergreen mode (pack E)
    def evergreen_setup(self) -> Optional[dict]:
        """The current Evergreen setup with its card dicts (location, banes, boons), or None."""
        ids = self.evergreen.get("setup")
        if not ids:
            return None
        return E.expand_setup(ids)

    def draw_evergreen(self, extra_red: Optional[bool] = None, extra_bane: Optional[bool] = None) -> dict:
        """Draw a new Evergreen mission (rules card: one location, two grey banes or one
        grey and a second red, one yellow and one red bane, one grey and one yellow boon;
        ``extra_bane`` adds one more). Replaces the current setup and its record; boon 24
        funds five coins of mercenaries for this setup. Returns the expanded setup."""
        if not self.finished:
            raise RuntimeError("Evergreen mode opens when the campaign is complete")
        options = dict(self.evergreen.get("options") or {})
        if extra_red is not None:
            options["extra_red"] = bool(extra_red)
        if extra_bane is not None:
            options["extra_bane"] = bool(extra_bane)
        setup = E.draw_setup(self._rng(), extra_red=bool(options.get("extra_red")), extra_bane=bool(options.get("extra_bane")))
        ids = E.setup_ids(setup)
        record = dict(self.evergreen)
        record.update({"setup": ids, "options": options, "attempts": 0, "losses": 0, "mercenaries": [],
                       "coins": 5 if 24 in ids["boons"] else 0})
        self.evergreen = record
        self.log.append("Evergreen mission drawn: the %s, banes %s, boons %s." % (
            setup["location"]["name"], ", ".join("%d %s" % (b["n"], b["name"]) for b in setup["banes"]),
            ", ".join("%d %s" % (b["n"], b["name"]) for b in setup["boons"])))
        self.touch()
        return setup

    def set_evergreen_option(self, key: str, value: bool) -> None:
        options = dict(self.evergreen.get("options") or {})
        options[str(key)] = bool(value)
        self.evergreen["options"] = options

    def start_evergreen_attempt(self, seed: Optional[int] = None, open_hands: bool = False) -> Game:
        if not self.finished:
            raise RuntimeError("Evergreen mode opens when the campaign is complete")
        ids = self.evergreen.get("setup")
        if not ids:
            raise RuntimeError("draw an Evergreen mission first")
        rng = self._rng()
        extra = E.build_setup(self, ids, rng, list(self.evergreen.get("mercenaries") or []))
        hand = HAND_SIZE[self.players] + int(extra.pop("hand_bonus", 0) or 0)
        cfg = GameConfig(players=self.players, names=tuple(self.names), rules_id="evergreen", hand_size=hand, extra=extra,
                         open_hands=bool(open_hands) and self.players > 1)
        self.evergreen["attempts"] = int(self.evergreen.get("attempts", 0)) + 1
        self.touch()
        self.reveal_lore("campaign_end")
        return Game.new(cfg, seed=seed if seed is not None else rng.randrange(2 ** 31))

    def finish_evergreen_attempt(self, game: Game) -> dict:
        """An Evergreen mission ends: no coins, no rewards; the same setup may be retried
        or a new one drawn."""
        self.touch()
        self.evergreen["played"] = int(self.evergreen.get("played", 0)) + 1
        won = game.result != "loss"
        if won:
            self.evergreen["wins"] = int(self.evergreen.get("wins", 0)) + 1
            self.log.append("Evergreen mission won (attempt %d)." % int(self.evergreen.get("attempts", 0)))
        else:
            self.evergreen["losses"] = int(self.evergreen.get("losses", 0)) + 1
            self.log.append("Evergreen mission lost (attempt %d). Try the same setup again or draw another." % (
                int(self.evergreen.get("attempts", 0))))
        return {"won": won, "evergreen": True, "attempts": int(self.evergreen.get("attempts", 0)),
                "losses": int(self.evergreen.get("losses", 0))}

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
    def _purse(self, scope: str) -> Tuple[int, List[str]]:
        """(coins, hired ids) of a scope: the mission's camp, or an Evergreen setup's boon 24."""
        if scope == "evergreen":
            return int(self.evergreen.get("coins", 0)), list(self.evergreen.get("mercenaries") or [])
        return int(self.coins), list(self.mercenaries)

    def hireable(self, scope: str = "mission") -> List[dict]:
        if scope != "evergreen" and not self.m_box_opened:
            return []
        coins, hired = self._purse(scope)
        out = []
        from .mercenaries import MERCENARIES
        for m in MERCENARIES:
            if m["id"] in hired:
                continue
            out.append({"id": m["id"], "name": m["name"], "cost": m["cost"], "affordable": coins >= m["cost"]})
        return out

    def hire(self, mid: str, scope: str = "mission") -> None:
        m = by_id(mid)
        coins, hired = self._purse(scope)
        if mid in hired:
            raise ValueError("already hired")
        if coins < m["cost"]:
            raise ValueError("not enough coins")
        if scope == "evergreen":
            self.evergreen["coins"] = coins - int(m["cost"])
            self.evergreen["mercenaries"] = hired + [mid]
            self.log.append("Evergreen: hired %s for %d coin%s." % (m["name"], m["cost"], "" if m["cost"] == 1 else "s"))
            return
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
