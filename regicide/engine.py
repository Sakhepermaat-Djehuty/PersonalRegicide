"""The Regicide game engine: state, legal actions, and action resolution.

Design notes
* All state is plain data (ids, ints, lists) so a game can be saved as JSON after
  every action and resumed on another device.
* ``Game`` methods that change state are the *actions*: ``play``, ``yield_turn``,
  ``use_solo_jester``, ``suffer``, ``choose_next``, ``decide``. Each validates, mutates,
  and appends structured events to ``last_events`` (for the UI to animate) and lines to
  ``log``.
* Rule variations (Legacy missions) are injected through ``rules.BaseRules`` hooks.
* Mid-turn choices (Legacy: the Kinfolk Flute or Scarlet Whistle before an attack
  resolves, the Mage's pick or the Reaver's reveal during its resolution, a Druid's
  sorting of the discard pile or a Chanter's draw, a mission zone rescue, the clean-up
  order or Myla's team damage after a kill, a mission's end-of-turn choice) pause the game
  in the ``decide`` phase with a serialisable ``decision`` dict: the rules object produces
  the decision, lists its legal actions and applies them; the engine stores it together
  with the state needed to resume (``play_index``, and for a pause mid-resolution the
  suits already done and the damage so far) and continues the paused attack afterwards.
  An action list may contain a *template* (an action with ``needs``: the deciding player
  fills in cards of their own choice, e.g. the Druid's four destinations); a submitted
  action fills a template when its type (and player) match, and the rules validate it.
* Pile convention: index 0 is the TOP of a face-down deck (tavern, castle) and the top
  of the discard pile.
"""
from __future__ import annotations

import copy
import itertools
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .cards import (BASIC_SUITS, CLUBS, DIAMONDS, HEARTS, MAGE, SPADES, SUIT_NAME, SUIT_SYMBOL,
                    Card)
from .rules import BaseRules, GameConfig, get_rules

PHASE_PLAY = "play"
PHASE_SUFFER = "suffer"
PHASE_CHOOSE_NEXT = "choose_next"
PHASE_DECIDE = "decide"          # another player decides something before an attack resolves
PHASE_WON = "won"
PHASE_LOST = "lost"

LOG_LIMIT = 300


class IllegalAction(Exception):
    """Raised when an action is not legal in the current state."""


@dataclass
class Enemy:
    card_id: str
    name: str
    suits: Tuple[str, ...]
    attack: int
    max_hp: int
    hp: int

    def to_dict(self) -> dict:
        return {"card_id": self.card_id, "name": self.name, "suits": list(self.suits),
                "attack": self.attack, "max_hp": self.max_hp, "hp": self.hp}

    @staticmethod
    def from_dict(d: dict) -> "Enemy":
        return Enemy(d["card_id"], d["name"], tuple(d["suits"]), int(d["attack"]),
                     int(d["max_hp"]), int(d["hp"]))


@dataclass
class Play:
    """Cards played against the current enemy in one action.

    ``jester`` marks an attack formed with a claimed Jester (Legacy): it ignored immunity
    when it resolved and, per rulebook p.20, a paladin in it keeps reducing the enemy's
    strength even if the enemy later gains paladin immunity. ``mage`` marks an attack that
    contains a mage (Legacy): it is banished instead of discarded when the enemy falls,
    even if the enemy was immune to mages (p.20)."""
    player: int
    card_ids: List[str]
    value: int
    suits: Tuple[str, ...]
    jester: bool = False
    mage: bool = False

    def to_dict(self) -> dict:
        d = {"player": self.player, "card_ids": list(self.card_ids), "value": self.value,
             "suits": list(self.suits)}
        if self.jester:
            d["jester"] = True
        if self.mage:
            d["mage"] = True
        return d

    @staticmethod
    def from_dict(d: dict) -> "Play":
        return Play(int(d["player"]), list(d["card_ids"]), int(d["value"]), tuple(d["suits"]),
                    bool(d.get("jester", False)), bool(d.get("mage", False)))


@dataclass
class Player:
    name: str
    hand: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "hand": list(self.hand)}

    @staticmethod
    def from_dict(d: dict) -> "Player":
        return Player(d["name"], list(d["hand"]))


class Game:
    """A game in progress. Create with ``Game.new(config, seed)``."""

    # ------------------------------------------------------------------ setup
    def __init__(self, config: GameConfig, rules: Optional[BaseRules] = None) -> None:
        self.config = config
        self.rules: BaseRules = rules if rules is not None else get_rules(config.rules_id)
        self.rng = random.Random()
        self.cards: Dict[str, Card] = {}
        self.players: List[Player] = [Player(n) for n in config.names]
        self.tavern: List[str] = []
        self.castle: List[str] = []
        self.discard: List[str] = []
        self.banished: List[str] = []      # Legacy: cards removed from the mission
        self.mission_zone: List[str] = []  # Legacy: mission specific area
        self.set_aside: List[str] = []     # Legacy solo: Jesters flipped after an attack
        self.enemy: Optional[Enemy] = None
        self.plays: List[Play] = []
        self.immunity_cancelled = False
        self.active = 0
        self.phase = PHASE_PLAY
        self.pending_damage = 0
        # The pending mid-turn choice while phase == PHASE_DECIDE (see rules.after_attack_formed):
        # plain data, saved with the game. ``active`` stays the attacking player throughout.
        self.decision: Optional[Dict[str, Any]] = None
        # Each player's last turn action: "played", "yielded" or None. The official yield
        # rule reads "every other player has yielded on their last turn".
        self.last_action: List[Optional[str]] = [None] * config.players
        self.solo_jesters = config.solo_jesters
        self.solo_jesters_used = 0
        self.turn = 1
        self.enemies_defeated = 0
        self.result: Optional[str] = None   # "win", "gold", "silver", "bronze", "loss"
        self.loss_reason = ""
        self.log: List[str] = []
        self.last_events: List[dict] = []
        self.extra: Dict[str, Any] = {}    # mission scratch state (serialised as-is)

    @classmethod
    def new(cls, config: GameConfig, seed: Optional[int] = None,
            rules: Optional[BaseRules] = None) -> "Game":
        g = cls(config, rules)
        if seed is None:
            seed = random.SystemRandom().randrange(2 ** 31)
        g.seed = seed
        g.rng.seed(seed)
        g.rules.build_decks(g)
        for p in g.players:
            for _ in range(config.max_hand):
                if g.tavern:
                    p.hand.append(g.tavern.pop(0))
        g._guarantee_opening_draw()
        g._reveal_next_enemy()
        g._say("Game start: %d player%s, hand size %d." % (
            config.players, "" if config.players == 1 else "s", config.max_hand))
        g._start_turn()
        return g

    def _guarantee_opening_draw(self) -> None:
        """Owner's hidden house rule: every opening hand holds a card that can draw, a
        Diamond (a Bard in Legacy; a multi-class card with the Diamond counts). A hand
        without one swaps a random card of its own with the first such card in the reserve
        deck, the rest of the reserve keeping its order; nothing changes when the hand has
        one already or the reserve has none. Not announced in the log."""
        if not self.config.opening_diamond:
            return

        def draws(cid: str) -> bool:
            c = self.cards[cid]
            return "D" in c.suits and not c.is_jester

        for p in self.players:
            if not p.hand or any(draws(c) for c in p.hand):
                continue
            at = next((i for i, c in enumerate(self.tavern) if draws(c)), None)
            if at is None:
                continue
            j = self.rng.randrange(len(p.hand))
            p.hand[j], self.tavern[at] = self.tavern[at], p.hand[j]

    # ---------------------------------------------------------------- queries
    def card(self, card_id: str) -> Card:
        return self.cards[card_id]

    def hand(self, player: Optional[int] = None) -> List[Card]:
        idx = self.active if player is None else player
        return [self.cards[c] for c in self.players[idx].hand]

    def hand_defence_value(self, player: Optional[int] = None) -> int:
        """What the hand can pay when suffering damage (locked cards pay nothing)."""
        return sum(c.defence_value for c in self.payable_hand(player))

    def hand_locked(self, card_id: str) -> bool:
        """May this card never leave its holder's hand (see ``rules.hand_locked``)?"""
        return self.rules.hand_locked(self, self.cards[card_id])

    def payable_hand(self, player: Optional[int] = None) -> List[Card]:
        """The hand cards that may be discarded to suffer damage (not the locked ones)."""
        return [c for c in self.hand(player) if not self.rules.hand_locked(self, c)]

    @property
    def n_players(self) -> int:
        return self.config.players

    @property
    def active_player(self) -> Player:
        return self.players[self.active]

    @property
    def is_over(self) -> bool:
        return self.phase in (PHASE_WON, PHASE_LOST)

    def immune(self, suit: str, cards: Sequence[Card] = ()) -> bool:
        if self.extra.get("jester_attack") and not self.rules.fixed_immunity(self, suit):
            return False  # Legacy: the attack formed with a claimed Jester ignores immunity
        return self.rules.immune(self, suit, cards)

    @property
    def shield(self) -> int:
        """Total Spades shield against the current enemy.

        Computed from the plays on the table so that a Jester cancelling a ♠ enemy's
        immunity retroactively activates earlier Spades (base game), and so that an enemy
        gaining paladin immunity mid-fight (Legacy mission zones) silences the plain
        paladins already played while a claimed-Jester attack or a corrupted paladin
        keeps its reduction (rulebook p.20).
        """
        if self.enemy is None:
            return 0
        total = 0
        for p in self.plays:
            if SPADES not in p.suits:
                continue
            if self.rules.fixed_immunity(self, SPADES):
                continue   # Legacy mission 9: nothing ignores Myla's paladin immunity
            if p.jester or not self.immune(SPADES, [self.cards[c] for c in p.card_ids]):
                total += p.value
        return total

    @property
    def enemy_attack(self) -> int:
        """Effective attack: (printed attack + mission bonus) × mission multiplier − shield,
        never below 0 (Legacy mission 10's warriors double their total strength and the
        paladin shields come off afterwards)."""
        if self.enemy is None:
            return 0
        total = (self.enemy.attack + self.rules.attack_bonus(self)) * self.rules.attack_multiplier(self)
        return max(0, total - self.shield)

    def can_yield(self) -> bool:
        return self.phase == PHASE_PLAY and self.rules.can_yield(self)

    def can_use_solo_jester(self) -> bool:
        if self.n_players != 1 or self.solo_jesters <= 0:
            return False
        if self.rules.solo_jester_mode(self) == "attack":
            return self.phase == PHASE_PLAY
        return self.phase in (PHASE_PLAY, PHASE_SUFFER)

    def feign_death_available(self) -> bool:
        """Feigning death discards the entire hand, so a locked card in it rules it out."""
        return (self.phase == PHASE_SUFFER and self.rules.feign_death_allowed(self)
                and self.hand_defence_value() < self.pending_damage
                and len(self.payable_hand()) == len(self.active_player.hand))

    def check_play(self, card_ids: Sequence[str]) -> Tuple[bool, str]:
        if self.phase != PHASE_PLAY:
            return False, "Not the moment to play cards."
        hand = self.rules.playable_ids(self)
        for cid in card_ids:
            if cid not in hand:
                if cid in self.active_player.hand and self.hand_locked(cid):
                    return False, "%s may never leave your hand." % self.cards[cid].label()
                return False, "Card %s is not in hand." % cid
        kind, err = self.rules.validate_combo(self, [self.cards[c] for c in card_ids])
        if err:
            return False, err
        return True, kind

    def legal_plays(self) -> List[List[str]]:
        """Every legal set of card ids the active player may play right now."""
        if self.phase != PHASE_PLAY:
            return []
        hand = [self.cards[c] for c in self.rules.playable_ids(self)]
        plays: List[List[str]] = []
        for c in hand:
            plays.append([c.id])
        aces = [c for c in hand if c.is_ace]
        for a in aces:
            for other in hand:
                if other.id == a.id or other.is_jester:
                    continue
                if other.is_ace and other.id < a.id:
                    continue  # count Ace+Ace once
                plays.append([a.id, other.id])
        # Sets: grouped by the strengths a card may take in a set (the rank in the base
        # game; Legacy's 2/5 cards join both the 2s and the 5s). Sizes and mixes the rules
        # reject are vetoed below, and a set listed under two strengths is kept once.
        by_strength: Dict[int, List[Card]] = {}
        for c in hand:
            if c.is_number and not c.is_ace:
                for s in self.rules.set_strengths(self, c):
                    by_strength.setdefault(s, []).append(c)
        limit = self.rules.kinfolk_limit(self)
        for strength, group in by_strength.items():
            if len(group) < 2 or strength * 2 > limit:
                continue
            for n in range(2, len(group) + 1):
                if strength * n > limit:
                    break
                for combo in itertools.combinations(group, n):
                    plays.append([c.id for c in combo])
        plays.extend(self.rules.extra_plays(self, hand))
        # keep only what the rules accept (lets a mission veto base plays), each set once
        out = []
        seen = set()
        for p in plays:
            key = frozenset(p)
            if key in seen:
                continue
            seen.add(key)
            kind, err = self.rules.validate_combo(self, [self.cards[c] for c in p])
            if not err:
                out.append(p)
        return out

    def legal_actions(self) -> List[dict]:
        """High-level action list for UIs and bots."""
        acts: List[dict] = []
        if self.phase == PHASE_PLAY:
            for p in self.legal_plays():
                acts.append({"type": "play", "cards": p})
            if self.can_yield():
                acts.append({"type": "yield"})
        if self.can_use_solo_jester():
            if self.rules.solo_jester_mode(self) == "attack" and self.phase == PHASE_PLAY:
                for suit in BASIC_SUITS:
                    acts.append({"type": "solo_jester", "suit": suit})
            elif self.rules.solo_jester_mode(self) == "refresh":
                acts.append({"type": "solo_jester"})
        if self.phase == PHASE_SUFFER:
            acts.append({"type": "suffer", "damage": self.pending_damage})
            if self.feign_death_available():
                acts.append({"type": "suffer", "cards": list(self.active_player.hand), "feign": True})
        if self.phase in (PHASE_PLAY, PHASE_SUFFER):
            acts.extend(self.rules.special_actions(self))
        if self.phase == PHASE_CHOOSE_NEXT:
            for i in range(self.n_players):
                if i == self.active and not self.config.jester_may_choose_self:
                    continue
                acts.append({"type": "choose_next", "player": i})
        if self.phase == PHASE_DECIDE:
            acts.extend(self.rules.decision_actions(self))
        return acts

    @property
    def deciding(self) -> int:
        """Index of the player who must act now: the decider in the decide phase."""
        if self.phase == PHASE_DECIDE and self.decision is not None:
            return int(self.decision["player"])
        return self.active

    def preview_play(self, card_ids: Sequence[str]) -> dict:
        """Simulate a play on a copy and report what would happen (for UI forecasts)."""
        ok, info = self.check_play(card_ids)
        if not ok:
            return {"ok": False, "reason": info}
        return self._forecast(info, lambda g: g.play(card_ids))

    def preview_decision(self, action: dict) -> dict:
        """Simulate a decision (e.g. a Kinfolk Flute addition) the way ``preview_play`` does."""
        if self.phase != PHASE_DECIDE:
            return {"ok": False, "reason": "No decision pending."}
        return self._forecast(str(action.get("type")), lambda g: g.decide(action))

    def _forecast(self, kind: str, act: Callable[["Game"], None]) -> dict:
        """Run ``act`` on a copy and summarise its events for a UI forecast."""
        g = copy.deepcopy(self)
        enemy_hp_before = g.enemy.hp if g.enemy else 0
        try:
            act(g)
        except IllegalAction as e:
            return {"ok": False, "reason": str(e)}
        events = list(g.last_events)
        decision = g.phase == PHASE_DECIDE
        decision_kind = (g.decision or {}).get("kind") if decision else None
        # Other players may still change the attack (Kinfolk Flute): forecast as if they
        # all declined. A mage peek is forecast as if nothing were added; only the number
        # of cards it reveals is reported, never which ones (the copy's reserve is the
        # real one and the player must not learn its order from a forecast).
        while g.phase == PHASE_DECIDE and g.forecast_decision():
            events.extend(g.last_events)
        damage = 0
        attack = 0
        powers: Dict[str, Any] = {}
        peeks: List[int] = []
        for ev in events:
            if ev["t"] == "damage":
                damage = ev["amount"]
            if ev["t"] in ("play", "add_to_play"):
                attack = ev["value"]
            if ev["t"] == "declare" and "attack" in ev:
                attack = ev["attack"]     # a Legacy 2/5's declared strength changed the attack
            if ev["t"] == "power":
                powers[ev["suit"]] = ev
            if ev["t"] == "mage_peek":
                peeks.append(int(ev["count"]))
        # A kill may pause on the mission's enemy-defeated choice (which zone card to rescue,
        # the clean-up order): the enemy is down all the same.
        pending_defeat = g.phase == PHASE_DECIDE and (g.decision or {}).get("resume") in ("defeat", "defeat_tail")
        defeated = any(ev["t"] == "defeat" for ev in events) or pending_defeat
        exact = any(ev["t"] == "defeat" and ev["exact"] for ev in events) or (
            pending_defeat and bool((g.decision or {}).get("exact")))
        return {"ok": True, "kind": kind, "attack": attack, "damage": damage, "powers": powers,
                "defeats": defeated, "exact": exact, "decision": decision,
                "decision_kind": decision_kind, "mage_peeks": peeks,
                "enemy_hp_after": max(0, enemy_hp_before - damage),
                "enemy_attack_after": g.enemy_attack if not defeated else 0,
                "phase_after": g.phase}

    # ---------------------------------------------------------------- actions
    def play(self, card_ids: Sequence[str], choice: Optional[dict] = None) -> None:
        self.last_events = []
        ok, info = self.check_play(card_ids)
        if not ok:
            raise IllegalAction(info)
        kind = info
        cards = [self.cards[c] for c in card_ids]
        for c in cards:
            self.rules.remove_played(self, c.id)
        me = self.active
        suits = self.play_suits(cards)
        value = self.rules.play_value(self, cards)
        play = Play(me, [c.id for c in cards], value, suits, jester=bool(self.extra.get("jester_attack")),
                    mage=any(MAGE in c.suits for c in cards))
        self.plays.append(play)
        self.last_action[me] = "played"
        self._event("play", player=me, cards=[c.id for c in cards], value=value, kind=kind)
        self._say("%s plays %s." % (self.players[me].name, " + ".join(c.label() for c in cards)))

        if kind == "jester":
            mode = self.rules.jester_mode(self)
            self.rules.on_cards_played(self, cards, me)
            if mode == "claim":
                # Legacy: someone claims the Jester and attacks now, ignoring immunity.
                self._event("jester", player=me, mode="claim")
                self._say("Jester! Whoever claims it attacks now, ignoring immunity.")
                self.phase = PHASE_CHOOSE_NEXT
                self.extra["jester_claim"] = True
                return
            self.immunity_cancelled = True
            self._event("jester", player=me, mode="base")
            self._say("Jester! %s's immunity is cancelled." % self._enemy_label())
            # Steps 3 and 4 are skipped. Someone is chosen to go next.
            if self.n_players == 1:
                self.turn += 1
                self._start_turn()
            else:
                self.phase = PHASE_CHOOSE_NEXT
            return

        self.rules.on_cards_played(self, cards, me)
        decision = self.rules.after_attack_formed(self, play)
        if decision is not None:
            # Step 1 is done; someone else acts before step 2 (e.g. adds kinfolk cards).
            decision = dict(decision)
            decision["play_index"] = len(self.plays) - 1
            if choice is not None:
                decision["choice"] = choice
            self.decision = decision
            self.phase = PHASE_DECIDE
            self._event("decide", **decision)
            return
        self._resolve_attack(len(self.plays) - 1, choice)

    def play_suits(self, cards: Sequence[Card]) -> Tuple[str, ...]:
        """The suits of an attack, each once, in resolution order."""
        return tuple(sorted(set(s for c in cards for s in self.rules.card_suits(self, c)), key=_suit_sort_key))

    # --- decisions (decide phase) ------------------------------------------------
    def decide(self, action: dict) -> None:
        """Apply the deciding player's choice (one of ``rules.decision_actions``)."""
        self.last_events = []
        if self.phase != PHASE_DECIDE or self.decision is None:
            raise IllegalAction("No decision pending.")
        if action.get("forecast"):
            # Forecast-only options (a druid deal returned unseen, a mage adding nothing) are
            # applied on copies by ``forecast_decision``; a player never takes them.
            raise IllegalAction("That choice is not available.")
        legal = self.rules.decision_actions(self)
        wanted = _action_key(action)
        plain = [_action_key(a) for a in legal if "needs" not in a]
        if wanted not in plain and not any(_fills_template(a, action) for a in legal):
            raise IllegalAction("That choice is not available.")
        self.rules.decide(self, action)

    def skip_decision(self) -> bool:
        """Take the decision's "do nothing" option if there is one (bots)."""
        for a in self.legal_actions():
            if a.get("skip"):
                self.decide(a)
                return True
        return False

    def forecast_decision(self) -> bool:
        """Forecasts only (on a copy): apply the neutral option the rules assume for the
        pending decision (see ``rules.forecast_action``). It skips the legality check
        because that option need not be offered to players: a mage must add a card when
        one is eligible, yet a forecast must not pick one for the player."""
        act = self.rules.forecast_action(self)
        if act is None or self.decision is None:
            return False
        self.last_events = []
        self.rules.decide(self, act)
        return True

    def flute_add(self, card_ids: Sequence[str]) -> None:
        """Kinfolk Flute: the deciding player adds these hand cards to the pending attack."""
        self.decide({"type": "flute_add", "card_ids": list(card_ids)})

    def flute_pass(self) -> None:
        """Kinfolk Flute: the deciding player adds nothing."""
        self.decide({"type": "flute_pass"})

    def add_cards_to_play(self, play_index: int, player: int, card_ids: Sequence[str]) -> Play:
        """Move cards from ``player``'s hand into an attack already on the table.

        Value and suits are recomputed over the whole attack and ``on_cards_played`` runs
        for the newcomers (corrupted / restored effects). The caller resolves the attack."""
        play = self.plays[play_index]
        hand = self.players[player].hand
        ids = list(card_ids)
        if len(set(ids)) != len(ids):
            raise IllegalAction("Duplicate card.")
        for cid in ids:
            if cid not in hand:
                raise IllegalAction("Card %s is not in hand." % cid)
        for cid in ids:
            hand.remove(cid)
        return self._join_play(play_index, player, ids, "hand")

    def mage_add_to_play(self, card_id: str) -> Play:
        """Mage pick: move one of the pending peek's revealed cards into the attack the
        decision is about. The paused resolution's running damage grows with the attack
        (the mage resolves before anything else touches the damage). The rules then
        discard the other revealed cards and continue or chain (see ``LegacyRules``)."""
        d = self.decision
        if d is None or d.get("kind") != "mage_peek":
            raise IllegalAction("No mage peek pending.")
        revealed = list(d.get("revealed", []))
        if card_id not in revealed:
            raise IllegalAction("Card %s was not revealed." % card_id)
        if card_id not in d.get("eligible", []):
            raise IllegalAction("%s cannot join the attack." % self.cards[card_id].label())
        revealed.remove(card_id)
        d["revealed"] = revealed
        play_index = int(d["play_index"])
        before = self.plays[play_index].value
        play = self._join_play(play_index, int(d["player"]), [card_id], "mage")
        if "damage" in d:
            d["damage"] = int(d["damage"]) + play.value - before
        return play

    def _join_play(self, play_index: int, player: int, ids: List[str], source: str) -> Play:
        """Append cards (already taken from wherever they were) to an attack on the table:
        value, suits and the mage flag are recomputed over the whole attack and
        ``on_cards_played`` runs for the newcomers (corrupted / restored effects)."""
        play = self.plays[play_index]
        play.card_ids.extend(ids)
        cards = [self.cards[c] for c in play.card_ids]
        play.value = self.rules.play_value(self, cards)
        play.suits = self.play_suits(cards)
        play.mage = play.mage or any(MAGE in c.suits for c in cards)
        self._event("add_to_play", player=player, cards=ids, play_index=play_index, value=play.value,
                    source=source)
        self.rules.on_cards_played(self, [self.cards[c] for c in ids], player)
        return play

    def resume_defeat(self) -> None:
        """Leave the decide phase and finish the enemy-defeated steps the decision paused:
        from the mission's enemy-defeated steps (``resume == "defeat"``) or, after the
        clean-up, from revealing the next enemy (``resume == "defeat_tail"``)."""
        decision = self.decision
        if decision is None or decision.get("resume") not in ("defeat", "defeat_tail"):
            raise IllegalAction("No defeat is pending.")
        self.decision = None
        self.phase = PHASE_PLAY
        if decision.get("resume") == "defeat_tail":
            self._finish_defeat(dict(decision.get("plan") or {}))
            return
        self._defeat_enemy(bool(decision.get("exact")), resumed=True)

    def resume_end_turn(self) -> None:
        """Leave the decide phase after a mission's end-of-turn choice: the next turn starts."""
        decision = self.decision
        if decision is None or decision.get("resume") != "end_turn":
            raise IllegalAction("No end of turn is pending.")
        self.decision = None
        self.phase = PHASE_PLAY
        self._next_turn()

    def resume_turn_start(self) -> None:
        """Leave the decide phase after a mission's start-of-turn choice (Legacy mission
        11's beast effects): the player may now act."""
        decision = self.decision
        if decision is None or decision.get("resume") != "turn_start":
            raise IllegalAction("No start of turn is pending.")
        self.decision = None
        self.phase = PHASE_PLAY
        self._check_can_act()

    def resume_suffered(self) -> None:
        """Leave the decide phase after a choice that followed the damage paid (Evergreen
        boons): the end-of-turn effects run and the next turn starts."""
        decision = self.decision
        if decision is None or decision.get("resume") != "suffered":
            raise IllegalAction("No suffered damage is pending.")
        self.decision = None
        self.phase = PHASE_PLAY
        self._end_turn()

    def resolve_pending_attack(self) -> None:
        """Leave the decide phase and resolve the attack the decision was about (step 2 on)."""
        decision = self.decision
        if decision is None:
            raise IllegalAction("No decision pending.")
        self.decision = None
        self.phase = PHASE_PLAY
        self._resolve_attack(int(decision["play_index"]), decision.get("choice"),
                             decision.get("done_suits", ()), decision.get("damage"))

    def _resolve_attack(self, play_index: int, choice: Optional[dict] = None,
                        done_suits: Sequence[str] = (), damage: Optional[int] = None) -> None:
        """Steps 2 and 3 for the attack ``self.plays[play_index]``: every class power in
        ``rules.power_order``, then the damage. A power may pause the game (the Legacy mage
        looks at the reserve and picks): ``rules.resolve_power`` then returns a dict with a
        ``decision`` and the resolution state (suits done, damage so far, the player's
        original choice) is kept in that decision until ``resolve_pending_attack`` resumes
        here with the (possibly larger) attack."""
        play = self.plays[play_index]
        cards = [self.cards[c] for c in play.card_ids]
        suits = play.suits
        value = play.value
        done = list(done_suits)
        if damage is None:
            damage = value
        for suit in self.rules.power_order:
            if suit not in suits or suit in done:
                continue
            done.append(suit)
            if self.immune(suit, cards):
                self._event("power", suit=suit, value=value, immune=True)
                self._say("%s is immune to %s." % (self._enemy_label(), SUIT_NAME.get(suit, suit)))
                continue
            if suit == HEARTS:
                n = self._heal(value)
                self._event("power", suit=suit, value=value, healed=n)
                self._say("Hearts heal %d card%s under the tavern deck." % (n, "" if n == 1 else "s"))
            elif suit == DIAMONDS:
                drawn = self._draw_round_robin(value, self.active)
                self._event("power", suit=suit, value=value, drawn=drawn)
                self._say("Diamonds draw %d card%s." % (len(drawn), "" if len(drawn) == 1 else "s"))
            elif suit == CLUBS:
                damage *= 2
                self._event("power", suit=suit, value=value, doubled=True)
                self._say("Clubs double the damage.")
            elif suit == SPADES:
                self._event("power", suit=suit, value=value, shield=value)
                self._say("Spades add %d shield (attack now %d)." % (value, self.enemy_attack))
            else:
                res = self.rules.resolve_power(self, suit, value, cards, damage=damage)
                if isinstance(res, dict) and "damage" in res:
                    damage = int(res["damage"])
                if isinstance(res, dict) and res.get("decision"):
                    decision = dict(res["decision"])
                    decision["play_index"] = play_index
                    decision["resume"] = "resolve"
                    decision["done_suits"] = done
                    decision["damage"] = damage
                    if choice is not None:
                        decision["choice"] = choice
                    self.decision = decision
                    self.phase = PHASE_DECIDE
                    self._event("decide", **decision)
                    return
                self._event("power", suit=suit, value=value, result=res)
        damage = max(0, damage - self.rules.damage_reduction(self))
        self.extra.pop("jester_attack", None)
        self._deal_damage(damage)

    def yield_turn(self) -> None:
        self.last_events = []
        if self.phase != PHASE_PLAY:
            raise IllegalAction("Not the moment to yield.")
        if not self.can_yield():
            raise IllegalAction("You may not yield now." if self.n_players > 1
                                else "You cannot yield in a solo game.")
        self.last_action[self.active] = "yielded"
        # A claimer who yields forms no attack: the Jester's "ignores immunity" is spent
        # (rulebook p.20: paladins played after the Jester attack do not ignore immunity).
        self.extra.pop("jester_attack", None)
        self._event("yield", player=self.active)
        self._say("%s yields." % self.active_player.name)
        self._enter_suffer()

    def use_solo_jester(self, choice: Optional[dict] = None) -> None:
        self.last_events = []
        if not self.can_use_solo_jester():
            raise IllegalAction("No Jester power available now.")
        if self.rules.solo_jester_mode(self) == "attack":
            suit = (choice or {}).get("suit")
            if suit not in BASIC_SUITS:
                raise IllegalAction("Choose a class for the Jester.")
            jid = "X%d" % (self.solo_jesters_used + 1)
            card = self.cards.get(jid)
            if card is None:
                card = Card(id=jid, rank="X", suits=(), value=0, name="Jester")
                self.cards[jid] = card
            self.solo_jesters -= 1
            self.solo_jesters_used += 1
            played = card.with_changes(suits=(suit,), value=8)
            self.cards[jid] = played
            # ``jester=True``: the attack ignores immunity and a paladin Jester keeps its
            # strength reduction even against a paladin-immune enemy (rulebook p.20).
            self.plays.append(Play(self.active, [jid], 8, (suit,), jester=True))
            self.last_action[self.active] = "played"
            self.extra["jester_attack"] = True
            self._event("play", player=self.active, cards=[jid], value=8, kind="jester_attack")
            self._event("solo_jester", mode="attack", suit=suit, remaining=self.solo_jesters)
            self._say("Jester attacks as an 8 of %s, ignoring immunity (%d left)." % (
                SUIT_NAME.get(suit, suit), self.solo_jesters))
            self._resolve_attack(len(self.plays) - 1)
            return
        p = self.active_player
        old = [c for c in p.hand if not self.hand_locked(c)]
        self._discard_cards([self.cards[c] for c in old])
        p.hand = [c for c in p.hand if c not in old]
        drawn = []
        while len(p.hand) < self.config.max_hand and self.tavern:
            cid = self.tavern.pop(0)
            p.hand.append(cid)
            drawn.append(cid)
        self.solo_jesters -= 1
        self.solo_jesters_used += 1
        self._event("solo_jester", discarded=old, drawn=drawn, remaining=self.solo_jesters)
        self._say("Jester power: discard %d, draw %d (%d left)." % (len(old), len(drawn), self.solo_jesters))
        if self.phase == PHASE_PLAY:
            self._check_can_act()
        else:
            self._check_can_suffer()

    def suffer(self, card_ids: Sequence[str]) -> None:
        self.last_events = []
        if self.phase != PHASE_SUFFER:
            raise IllegalAction("Not the moment to suffer damage.")
        ids = list(card_ids)
        if len(set(ids)) != len(ids):
            raise IllegalAction("Duplicate card.")
        hand = self.active_player.hand
        for cid in ids:
            if cid not in hand:
                raise IllegalAction("Card %s is not in hand." % cid)
            if self.hand_locked(cid):
                raise IllegalAction("%s may never leave your hand." % self.cards[cid].label())
        cards = [self.cards[c] for c in ids]
        total = sum(c.defence_value for c in cards)
        feign = False
        if total < self.pending_damage:
            if self.feign_death_available() and set(ids) == set(hand):
                feign = True
            else:
                raise IllegalAction("Those cards cover %d damage; %d is needed." % (total, self.pending_damage))
        elif self.rules.sequential_discard(self):
            # Rulebook p.18: "discard cards one at a time ... you may not keep discarding
            # once the damage is satisfied". The cards are discarded in the order given, so
            # the total before the last one must still be below the damage ([9, 10] for 10
            # is legal, [10, A] is not); the last card discarded ends on top of the pile.
            running = 0
            for c in cards[:-1]:
                running += c.defence_value
                if running >= self.pending_damage:
                    raise IllegalAction("Discard one card at a time: the damage is covered before %s." % cards[-1].label())
        elif self.config.strict_minimal_discard:
            for c in cards:
                if total - c.defence_value >= self.pending_damage:
                    raise IllegalAction("%s is not needed to cover the damage." % c.label())
        for c in cards:
            hand.remove(c.id)
        damage = self.pending_damage
        self.rules.discard_suffered(self, cards, damage, feign)
        if feign:
            self._event("feign_death", player=self.active, cards=ids, damage=damage)
            self._say("%s feigns death, discarding the whole hand." % self.active_player.name)
        self._event("suffer", player=self.active, cards=ids, damage=damage, paid=total)
        self._say("%s discards %s to suffer %d." % (
            self.active_player.name, " ".join(c.label() for c in cards) or "nothing", damage))
        self.pending_damage = 0
        decision = self.rules.after_suffer(self, cards, damage, feign)
        if decision is not None:
            # An Evergreen boon wants a choice about the cards just discarded before the
            # end-of-turn effects; ``resume_suffered`` then runs them.
            decision = dict(decision)
            decision["resume"] = "suffered"
            self.decision = decision
            self.phase = PHASE_DECIDE
            self._event("decide", **decision)
            return
        self._end_turn()

    def choose_next(self, player: int) -> None:
        self.last_events = []
        if self.phase != PHASE_CHOOSE_NEXT:
            raise IllegalAction("No player choice pending.")
        if not 0 <= player < self.n_players:
            raise IllegalAction("No such player.")
        if player == self.active and not self.config.jester_may_choose_self:
            raise IllegalAction("The Jester's player must choose someone else.")
        self._event("choose_next", chooser=self.active, player=player)
        if self.extra.pop("jester_claim", False):
            self._say("%s claims the Jester and attacks." % self.players[player].name)
            self.active = player
            self.extra["jester_attack"] = True
            self.phase = PHASE_PLAY
            self._event("turn", player=self.active, turn=self.turn)
            self._check_can_act()
            return
        self._say("%s chooses %s to go next." % (self.active_player.name, self.players[player].name))
        self.active = player
        self.turn += 1
        self.phase = PHASE_PLAY
        self._start_turn()

    def abandon(self) -> None:
        """The players give up: the game is lost (a Legacy attempt then counts as a loss)."""
        self.last_events = []
        if self.is_over:
            raise IllegalAction("The game is over.")
        self.decision = None
        self._lose("The attempt was abandoned.")

    def special(self, action: dict) -> None:
        """Relic / mission action provided by the rules (see rules.special_actions)."""
        self.last_events = []
        self.rules.do_special(self, action)

    # ------------------------------------------------------------- internals
    def _enemy_label(self) -> str:
        return self.enemy.name if self.enemy else "nobody"

    def _say(self, text: str) -> None:
        self.log.append(text)
        if len(self.log) > LOG_LIMIT:
            del self.log[: len(self.log) - LOG_LIMIT]

    def _event(self, t: str, **kw: Any) -> None:
        ev = {"t": t}
        ev.update(kw)
        self.last_events.append(ev)

    def _heal(self, n: int) -> int:
        if not self.discard or n <= 0:
            return 0
        pile = list(self.discard)
        self.rng.shuffle(pile)
        moved, rest = pile[:n], pile[n:]
        self.discard = rest
        for cid in moved:
            self.to_reserve(cid, bottom=True)  # under the tavern deck
        self._event("heal", cards=moved)
        return len(moved)

    # --- pile helpers that every rule set uses -----------------------------------------
    def banish_cards(self, ids: Sequence[str], where: str = "top") -> List[str]:
        """Put cards on the banished pile: on top in order (the last ends on top), at
        random positions (``"shuffle"``) or at the bottom (``"bottom"``). Every banish in
        the game goes through here so that ``rules.banish_redirect`` can send a card
        elsewhere (Legacy mission 12's restored cards go under the reserve deck instead).
        Returns the ids that reached the banished pile."""
        done: List[str] = []
        for cid in ids:
            redirect = self.rules.banish_redirect(self, self.cards[cid])
            if redirect == "reserve_bottom":
                self.tavern.append(cid)
                self._event("banish_redirect", card=cid, to="reserve_bottom")
                self._say("%s is restored and never enters the banished pile: it goes under the reserve deck." % (
                    self.cards[cid].label()))
                continue
            if where == "shuffle":
                self.banished.insert(self.rng.randrange(len(self.banished) + 1), cid)
            elif where == "bottom":
                self.banished.insert(0, cid)
            else:
                self.banished.append(cid)
            done.append(cid)
        return done

    def to_reserve(self, card_id: str, bottom: bool = False) -> bool:
        """Put a card on top of (or under) the reserve deck, unless ``rules.reserve_redirect``
        sends it elsewhere (Legacy mission 12: a corrupted card can never enter the reserve
        deck and goes to the bottom of the banished pile). Returns True if it joined the deck."""
        redirect = self.rules.reserve_redirect(self, self.cards[card_id])
        if redirect == "banished_bottom":
            self.banished.insert(0, card_id)
            self._event("reserve_redirect", card=card_id, to="banished_bottom")
            self._say("%s is corrupted and never enters the reserve deck: it goes to the bottom of the banished pile." % (
                self.cards[card_id].label()))
            return False
        if bottom:
            self.tavern.append(card_id)
        else:
            self.tavern.insert(0, card_id)
        return True

    def _draw_round_robin(self, n: int, start: int) -> List[dict]:
        drawn: List[dict] = []
        i = start
        max_hand = self.config.max_hand
        while n > 0 and self.tavern:
            if all(len(p.hand) >= max_hand for p in self.players):
                break
            p = self.players[i]
            if len(p.hand) < max_hand:
                cid = self.tavern.pop(0)
                p.hand.append(cid)
                drawn.append({"player": i, "card": cid})
                self._event("draw", player=i, card=cid)
                n -= 1
            i = (i + 1) % self.n_players
        return drawn

    def _discard_cards(self, cards: List[Card]) -> None:
        ordered = self.rules.order_for_discard(self, list(cards))
        for c in ordered:
            self.discard.insert(0, c.id)

    def _deal_damage(self, damage: int) -> None:
        enemy = self.enemy
        assert enemy is not None
        enemy.hp -= damage
        self._event("damage", amount=damage, hp=max(0, enemy.hp), max_hp=enemy.max_hp)
        self._say("%d damage to %s (%d/%d)." % (damage, enemy.name, max(0, enemy.hp), enemy.max_hp))
        if enemy.hp <= 0:
            self._defeat_enemy(exact=enemy.hp == 0)
        else:
            self._enter_suffer()

    def _defeat_enemy(self, exact: bool, resumed: bool = False) -> None:
        enemy = self.enemy
        assert enemy is not None
        if not resumed:
            decision = self.rules.before_defeat(self, exact)
            if self.is_over:
                return   # the mission's enemy-defeated step lost the game (mission 6's team damage)
            if decision is not None:
                # The mission's enemy-defeated steps need a choice first (e.g. which mission
                # zone card to rescue). The defeat continues via ``resume_defeat``.
                self._pause_defeat(decision, exact)
                return
        plan = self.rules.defeat_plan(self, exact)
        played = [self.cards[c] for p in self.plays for c in p.card_ids]
        # Legacy p.23: an attack that contains a mage (the mage, the cards played with it
        # and everything it added) is banished at clean-up, other attacks against the
        # same enemy are not.
        mage_ids = [c for p in self.plays if p.mage for c in p.card_ids]
        spent: List[Card] = []
        if self.n_players == 1 and self.rules.solo_jester_mode(self) == "attack":
            # Official solo rule (Legacy p.26): the Jester is never cleaned up to any pile;
            # it goes back to the side, face down, unusable for the rest of this attempt.
            # With two or more players the Jester is a reserve card cleaned up like the rest.
            # (Set aside below, once no clean-up question pauses the defeat any more.)
            spent = [c for c in played if c.is_jester]
            played = [c for c in played if not c.is_jester]
        # Evergreen bane 14: the attack that dealt the final damage goes into the mission
        # zone (after the location's enemy-defeated rules) instead of the discard pile.
        last_ids: List[str] = []
        if plan.get("last_play_to") == "zone" and self.plays:
            last_ids = [c.id for c in played if c.id in self.plays[-1].card_ids]
            played = [c for c in played if c.id not in last_ids]
            mage_ids = [c for c in mage_ids if c not in last_ids]
        # Rulebook p.19: the played cards go on the discard pile "in any order you wish" (and
        # a mage attack is banished in the player's order, mission 5). The rules ask only when
        # the top of the pile matters; ``resume_defeat`` comes back here (``resumed``) and the
        # rules see the recorded choice.
        to_discard = [c.id for c in played if c.id not in mage_ids] if plan.get("played_to", "discard") == "discard" else []
        decision = self.rules.before_cleanup(self, exact, plan, to_discard, list(mage_ids))
        if decision is not None:
            self._pause_defeat(decision, exact)
            return
        self.set_aside.extend(c.id for c in spent)
        self._event("defeat", enemy=enemy.card_id, exact=exact, plan=plan, mage_banished=mage_ids)
        self._say("%s is defeated%s" % (enemy.name, (" with exact damage!" + (
            " It joins the tavern deck." if plan.get("enemy_to") == "tavern_top" else "")) if exact else "."))
        self.enemies_defeated += 1
        # Legacy p.19: step 1 moves the enemy (and the mission zone) first, step 2 then puts
        # the played cards on top of the discard pile. The base game keeps its old order
        # (enemy on top), which changes nothing there. A mission may clear the zone before
        # moving the enemy (``zone_first``) and banish the whole discard pile (``discard_to``).
        self._reserve_to_discard(int(plan.get("reserve_to_discard", 0) or 0))
        if self.rules.played_on_top:
            self._mission_defeat_moves(enemy.card_id, plan)
        self._cleanup_played(played, mage_ids, plan)
        if not self.rules.played_on_top:
            self._mission_defeat_moves(enemy.card_id, plan)
        if last_ids:
            self.rules.zone_entered_from_play(self, last_ids)
            self.mission_zone.extend(last_ids)
            self._event("zone_absorb", cards=last_ids, zone=list(self.mission_zone))
            self._say("The killing attack (%s) goes into the mission zone." % " + ".join(self.cards[c].label() for c in last_ids))
        self.plays = []
        self.immunity_cancelled = False
        self.enemy = None
        if self.config.yield_reset_per_enemy:
            self.last_action = [None] * self.n_players
        decision = self.rules.after_cleanup(self, exact, plan)
        if self.is_over:
            return   # an Evergreen bane's team damage could not be paid
        if decision is not None:
            # The mission wants a choice once the piles are final (mission 8's exact-kill
            # pick from the discard pile); ``resume_defeat`` then reveals the next enemy.
            decision = dict(decision)
            decision["exact"] = exact
            decision["resume"] = "defeat_tail"
            decision["plan"] = dict(plan)
            self.decision = decision
            self.phase = PHASE_DECIDE
            self._event("decide", **decision)
            return
        self._finish_defeat(plan)

    def _pause_defeat(self, decision: Dict[str, Any], exact: bool) -> None:
        """Park the enemy-defeated steps behind a decision; ``resume_defeat`` continues them."""
        decision = dict(decision)
        decision["exact"] = exact
        decision["resume"] = "defeat"
        self.decision = decision
        self.phase = PHASE_DECIDE
        self._event("decide", **decision)

    def _finish_defeat(self, plan: Dict[str, Any]) -> None:
        """The end of the enemy-defeated steps: win, or reveal the next enemy (with
        mission 5's carry-over damage) and start the same player's new turn."""
        if self.is_over:
            return
        if not self.castle:
            self._win()
            return
        self._reveal_next_enemy()
        carry = int(plan.get("carry_damage", 0) or 0)
        if carry > 0 and self.enemy is not None:
            # Legacy mission 5: on an exact kill the next enemy takes damage equal to the
            # defeated enemy's strength; at 0 or less it falls too and the chain goes on.
            nxt = self.enemy
            nxt.hp -= carry
            self._event("carry_damage", amount=carry, enemy=nxt.card_id, hp=max(0, nxt.hp), max_hp=nxt.max_hp)
            self._say("%d carry-over damage to %s (%d/%d)." % (carry, nxt.name, max(0, nxt.hp), nxt.max_hp))
            if nxt.hp <= 0:
                self._defeat_enemy(exact=nxt.hp == 0)
                return
        # The player who defeated the enemy takes a new turn (no damage suffered).
        self.turn += 1
        self.phase = PHASE_PLAY
        self._start_turn()

    def _reserve_to_discard(self, n: int) -> None:
        """Legacy mission 7: ``n`` cards from the top of the reserve go to the discard pile
        (fewer when the reserve runs out)."""
        if n <= 0:
            return
        moved = []
        while n > 0 and self.tavern:
            cid = self.tavern.pop(0)
            self.discard.insert(0, cid)
            moved.append(cid)
            n -= 1
        self._event("reserve_discard", cards=moved, wanted=n + len(moved))
        self._say("%d card%s from the top of the reserve deck go to the discard pile." % (
            len(moved), "" if len(moved) == 1 else "s"))

    def _cleanup_played(self, played: List[Card], mage_ids: List[str], plan: Dict[str, Any]) -> None:
        if plan.get("played_to", "discard") == "discard":
            self._discard_cards([c for c in played if c.id not in mage_ids])
            self.banish_cards(self.rules.order_for_banish(self, [c.id for c in played if c.id in mage_ids]))
            if mage_ids:
                self._say("The mage attack is banished: %s." % " + ".join(self.cards[c].label() for c in mage_ids))
        elif plan["played_to"] == "banish":
            self.banish_cards([c.id for c in played])

    def _mission_defeat_moves(self, enemy_id: str, plan: Dict[str, Any]) -> None:
        """The mission's enemy-defeated moves in the plan's order: the enemy and the zone
        (zone first when ``zone_first``), then the whole discard pile if the mission banishes
        it (Legacy mission 12)."""
        if plan.get("zone_first"):
            self._clear_zone(plan)
            self._move_defeated_enemy(enemy_id, plan)
        else:
            self._move_defeated_enemy(enemy_id, plan)
            self._clear_zone(plan)
        if plan.get("discard_to") == "banish" and self.discard:
            pile = list(self.discard)
            self.discard = []
            # the pile keeps its order: its bottom card is banished first, its top ends on top
            self.banish_cards(list(reversed(pile)))
            self._event("discard_banished", cards=pile)
            self._say("The whole discard pile (%d card%s) is banished in its order." % (len(pile), "" if len(pile) == 1 else "s"))
        if plan.get("shuffle_banished"):
            # Evergreen's Forest and Hills: "then shuffle the banished pile"
            self.rng.shuffle(self.banished)
            self._event("banished_shuffled", count=len(self.banished))

    def _move_defeated_enemy(self, card_id: str, plan: Dict[str, Any]) -> None:
        dest = plan.get("enemy_to", "discard")
        if dest == "tavern_top":
            self.to_reserve(card_id)
        elif dest == "discard":
            self.discard.insert(0, card_id)
        elif dest == "banish":
            self.banish_cards([card_id])
        elif dest == "banish_shuffle":
            self.banish_cards([card_id], "shuffle")
        elif dest == "castle_bottom":
            self.castle.append(card_id)

    def _clear_zone(self, plan: Dict[str, Any]) -> None:
        zone_to = plan.get("zone_to")
        if zone_to and self.mission_zone:
            zone = list(self.mission_zone)
            self.mission_zone = []
            if zone_to == "banish":
                self.banish_cards(zone)
            elif zone_to == "banish_shuffle":
                self.banish_cards(zone, "shuffle")
            elif zone_to == "discard":
                self._discard_cards([self.cards[c] for c in zone])
            self._event("zone_cleared", cards=zone, to=zone_to)

    def _reveal_next_enemy(self) -> None:
        cid = self.castle.pop(0)
        card = self.cards[cid]
        attack, hp = self.rules.enemy_stats(self, card)
        name = card.name or ("%s of %s" % ({"J": "Jack", "Q": "Queen", "K": "King"}.get(card.rank, card.rank),
                                           SUIT_NAME.get(card.suit or "", "no suit")))
        self.enemy = Enemy(cid, name, tuple(card.suits), attack, hp, hp)
        self._event("reveal", enemy=self.enemy.to_dict())
        self._say("%s appears (%d health, %d attack)." % (name, hp, attack))
        self.rules.on_enemy_revealed(self)

    def _enter_suffer(self) -> None:
        self.pending_damage = self.enemy_attack
        if self.extra.get("guardian"):
            # Legacy Guardian (rulebook p.18): players suffer no damage this turn.
            self.pending_damage = 0
            self._event("no_damage", player=self.active, guardian=True)
            self._say("Guardian: %s suffers no damage this turn." % self.active_player.name)
            self._end_turn()
            return
        if self.pending_damage <= 0:
            self._event("no_damage", player=self.active)
            self._say("%s suffers no damage." % self.active_player.name)
            self._end_turn()
            return
        self.phase = PHASE_SUFFER
        self._event("suffer_due", player=self.active, damage=self.pending_damage)
        self._check_can_suffer()

    def _check_can_suffer(self) -> None:
        if self.phase != PHASE_SUFFER:
            return
        if self.hand_defence_value() >= self.pending_damage:
            return
        if self.can_use_solo_jester() or self.feign_death_available():
            return  # the Jester power / feigning death may still rescue the player
        self._lose("%s cannot suffer %d damage." % (self.active_player.name, self.pending_damage))

    def _end_turn(self) -> None:
        self.extra.pop("jester_attack", None)   # a claimed Jester's turn ends without an attack
        decision = self.rules.on_turn_end(self)
        if self.is_over:
            return
        if decision is not None:
            # The mission's end of turn needs a choice (mission 9: rescue a captured card
            # or rotate the piles); ``resume_end_turn`` then starts the next turn.
            decision = dict(decision)
            decision["resume"] = "end_turn"
            self.decision = decision
            self.phase = PHASE_DECIDE
            self._event("decide", **decision)
            return
        self._next_turn()

    def _next_turn(self) -> None:
        self.active = (self.active + 1) % self.n_players
        self.turn += 1
        self.phase = PHASE_PLAY
        self._start_turn()

    def _start_turn(self) -> None:
        if self.is_over:
            return
        self.phase = PHASE_PLAY
        self.pending_damage = 0
        self.extra.pop("guardian", None)   # a Guardian's protection lasts for its turn only
        self.extra.pop("jester_attack", None)   # and a claimed Jester's "ignores immunity" too
        self._event("turn", player=self.active, turn=self.turn)
        decision = self.rules.on_turn_start(self)
        if self.is_over:
            return
        if decision is not None:
            # The mission's start of turn needs a choice (mission 11: a beast makes the
            # player discard or banish a hand card); ``resume_turn_start`` then goes on.
            decision = dict(decision)
            decision["resume"] = "turn_start"
            self.decision = decision
            self.phase = PHASE_DECIDE
            self._event("decide", **decision)
            return
        self._check_can_act()

    def _check_can_act(self) -> None:
        if self.phase != PHASE_PLAY or self.is_over:
            return
        if self.legal_plays() or self.can_yield() or self.can_use_solo_jester():
            return
        if any(a.get("ends_turn") for a in self.rules.special_actions(self)):
            return
        self._lose("%s has no card to play and may not yield." % self.active_player.name)

    def _win(self) -> None:
        self.phase = PHASE_WON
        if self.n_players == 1 and self.config.jesters is None:
            self.result = {0: "gold", 1: "silver"}.get(self.solo_jesters_used, "bronze")
        else:
            self.result = "win"
        self._event("won", result=self.result)
        self._say("All enemies defeated. Victory%s!" % ("" if self.result == "win" else " (%s)" % self.result))

    def _lose(self, reason: str) -> None:
        self.phase = PHASE_LOST
        self.result = "loss"
        self.loss_reason = reason
        self._event("lost", reason=reason)
        self._say("Defeat: " + reason)

    # ------------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        st = self.rng.getstate()
        return {
            "version": 1,
            "config": self.config.to_dict(),
            "rules_id": self.rules.id,
            "seed": getattr(self, "seed", None),
            "rng": [st[0], list(st[1]), st[2]],
            "cards": [c.to_dict() for c in self.cards.values()],
            "players": [p.to_dict() for p in self.players],
            "tavern": list(self.tavern), "castle": list(self.castle),
            "discard": list(self.discard), "banished": list(self.banished),
            "mission_zone": list(self.mission_zone), "set_aside": list(self.set_aside),
            "enemy": self.enemy.to_dict() if self.enemy else None,
            "plays": [p.to_dict() for p in self.plays],
            "immunity_cancelled": self.immunity_cancelled,
            "active": self.active, "phase": self.phase,
            "pending_damage": self.pending_damage,
            "decision": copy.deepcopy(self.decision),
            "last_action": list(self.last_action),
            "solo_jesters": self.solo_jesters, "solo_jesters_used": self.solo_jesters_used,
            "turn": self.turn, "enemies_defeated": self.enemies_defeated,
            "result": self.result, "loss_reason": self.loss_reason,
            "log": list(self.log), "extra": copy.deepcopy(self.extra),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Game":
        config = GameConfig.from_dict(d["config"])
        g = cls(config, get_rules(d.get("rules_id", config.rules_id)))
        g.seed = d.get("seed")
        st = d["rng"]
        g.rng.setstate((st[0], tuple(st[1]), st[2]))
        g.cards = {}
        for cd in d["cards"]:
            c = Card.from_dict(cd)
            g.cards[c.id] = c
        g.players = [Player.from_dict(p) for p in d["players"]]
        g.tavern = list(d["tavern"]); g.castle = list(d["castle"])
        g.discard = list(d["discard"]); g.banished = list(d.get("banished", []))
        g.mission_zone = list(d.get("mission_zone", []))
        g.set_aside = list(d.get("set_aside", []))
        g.enemy = Enemy.from_dict(d["enemy"]) if d.get("enemy") else None
        g.plays = [Play.from_dict(p) for p in d.get("plays", [])]
        g.immunity_cancelled = bool(d.get("immunity_cancelled", False))
        g.active = int(d["active"]); g.phase = d["phase"]
        g.pending_damage = int(d.get("pending_damage", 0))
        g.decision = copy.deepcopy(d.get("decision")) or None
        g.last_action = list(d.get("last_action", [None] * config.players))
        g.solo_jesters = int(d.get("solo_jesters", 0))
        g.solo_jesters_used = int(d.get("solo_jesters_used", 0))
        g.turn = int(d.get("turn", 1)); g.enemies_defeated = int(d.get("enemies_defeated", 0))
        g.result = d.get("result"); g.loss_reason = d.get("loss_reason", "")
        g.log = list(d.get("log", [])); g.extra = copy.deepcopy(d.get("extra", {}))
        return g

    # --------------------------------------------------------------- summary
    def all_card_ids(self) -> List[str]:
        """Every card id currently somewhere in the game (used by invariant tests)."""
        ids: List[str] = []
        for p in self.players:
            ids.extend(p.hand)
        ids.extend(self.tavern); ids.extend(self.castle); ids.extend(self.discard)
        ids.extend(self.banished); ids.extend(self.mission_zone); ids.extend(self.set_aside)
        for p in self.plays:
            ids.extend(p.card_ids)
        if self.enemy:
            ids.append(self.enemy.card_id)
        d = self.decision
        while d:
            ids.extend(d.get("revealed", []))      # a mage's or reaver's reveal, out of the reserve
            for dealt in d.get("dealt", []):       # a druid's deal, out of the discard pile
                ids.extend(dealt)
            d = d.get("resume_decision")           # a decision parked behind another one
        ids.extend(self.rules.extra_card_ids(self))
        return ids

    def summary(self) -> str:
        e = self.enemy
        lines = []
        if e:
            imm = "none" if self.immunity_cancelled else "/".join(SUIT_NAME.get(s, s) for s in e.suits)
            lines.append("Enemy: %s  HP %d/%d  ATK %d (shield %d)  immune: %s" % (
                e.name, max(0, e.hp), e.max_hp, self.enemy_attack, self.shield, imm))
        lines.append("Tavern %d | Discard %d | Castle left %d | Turn %d | Phase %s" % (
            len(self.tavern), len(self.discard), len(self.castle), self.turn, self.phase))
        if self.n_players == 1:
            lines.append("Jester powers left: %d" % self.solo_jesters)
        return "\n".join(lines)


def _suit_sort_key(s: str) -> int:
    order = list(BASIC_SUITS) + ["M", "R", "G", "U", "T"]
    return order.index(s) if s in order else 99


def _action_key(action: dict) -> Tuple[str, Tuple[str, ...], str, str]:
    """What identifies a decision action: its type, the (order-free) cards it names, the
    single card, option or count it picks and the pile it names."""
    cards = action.get("card_ids") or action.get("cards") or []
    single = action.get("card")
    if single is None:
        single = action.get("option")
    if single is None:
        single = action.get("count", "")
    return (str(action.get("type")), tuple(sorted(str(c) for c in cards)), str(single),
            str(action.get("pile", "")))


def _fills_template(template: dict, action: dict) -> bool:
    """Does ``action`` fill in ``template`` (an action with ``needs``: the player names the
    cards)? Type and player must match; the rules validate the cards themselves."""
    if "needs" not in template or str(template.get("type")) != str(action.get("type")):
        return False
    if "player" in action and "player" in template and str(action["player"]) != str(template["player"]):
        return False
    return True
