"""The Regicide game engine: state, legal actions, and action resolution.

Design notes
* All state is plain data (ids, ints, lists) so a game can be saved as JSON after
  every action and resumed on another device.
* ``Game`` methods that change state are the *actions*: ``play``, ``yield_turn``,
  ``use_solo_jester``, ``suffer``, ``choose_next``, ``decide``. Each validates, mutates,
  and appends structured events to ``last_events`` (for the UI to animate) and lines to
  ``log``.
* Rule variations (Legacy missions) are injected through ``rules.BaseRules`` hooks.
* Mid-turn choices by other players (Legacy: the Kinfolk Flute, later Mage picks and the
  like) pause the game in the ``decide`` phase with a serialisable ``decision`` dict: the
  rules object produces the decision, lists its legal actions and applies them; the
  engine stores it and resolves the paused attack afterwards.
* Pile convention: index 0 is the TOP of a face-down deck (tavern, castle) and the top
  of the discard pile.
"""
from __future__ import annotations

import copy
import itertools
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .cards import (BASIC_SUITS, CLUBS, DIAMONDS, HEARTS, SPADES, SUIT_NAME, SUIT_SYMBOL,
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
    """Cards played against the current enemy in one action."""
    player: int
    card_ids: List[str]
    value: int
    suits: Tuple[str, ...]

    def to_dict(self) -> dict:
        return {"player": self.player, "card_ids": list(self.card_ids), "value": self.value,
                "suits": list(self.suits)}

    @staticmethod
    def from_dict(d: dict) -> "Play":
        return Play(int(d["player"]), list(d["card_ids"]), int(d["value"]), tuple(d["suits"]))


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
        g._reveal_next_enemy()
        g._say("Game start: %d player%s, hand size %d." % (
            config.players, "" if config.players == 1 else "s", config.max_hand))
        g._start_turn()
        return g

    # ---------------------------------------------------------------- queries
    def card(self, card_id: str) -> Card:
        return self.cards[card_id]

    def hand(self, player: Optional[int] = None) -> List[Card]:
        idx = self.active if player is None else player
        return [self.cards[c] for c in self.players[idx].hand]

    def hand_defence_value(self, player: Optional[int] = None) -> int:
        return sum(c.defence_value for c in self.hand(player))

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
        if self.extra.get("jester_attack"):
            return False  # Legacy: the attack formed with a claimed Jester ignores immunity
        return self.rules.immune(self, suit, cards)

    @property
    def shield(self) -> int:
        """Total Spades shield against the current enemy.

        Computed from the plays on the table so that a Jester cancelling a ♠ enemy's
        immunity retroactively activates earlier Spades (official rule).
        """
        if self.enemy is None or self.immune(SPADES):
            return 0
        return sum(p.value for p in self.plays if SPADES in p.suits)

    @property
    def enemy_attack(self) -> int:
        """Effective attack: printed attack + mission bonus − shield, never below 0."""
        if self.enemy is None:
            return 0
        return max(0, self.enemy.attack + self.rules.attack_bonus(self) - self.shield)

    def can_yield(self) -> bool:
        return self.phase == PHASE_PLAY and self.rules.can_yield(self)

    def can_use_solo_jester(self) -> bool:
        if self.n_players != 1 or self.solo_jesters <= 0:
            return False
        if self.rules.solo_jester_mode(self) == "attack":
            return self.phase == PHASE_PLAY
        return self.phase in (PHASE_PLAY, PHASE_SUFFER)

    def feign_death_available(self) -> bool:
        return (self.phase == PHASE_SUFFER and self.rules.feign_death_allowed(self)
                and self.hand_defence_value() < self.pending_damage)

    def check_play(self, card_ids: Sequence[str]) -> Tuple[bool, str]:
        if self.phase != PHASE_PLAY:
            return False, "Not the moment to play cards."
        hand = self.rules.playable_ids(self)
        for cid in card_ids:
            if cid not in hand:
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
        # Sets: grouped by single-card strength (the rank in the base game; Legacy's 2/5
        # cards count as 2). Sizes and mixes the rules reject are vetoed below.
        by_strength: Dict[int, List[Card]] = {}
        for c in hand:
            if c.is_number and not c.is_ace:
                by_strength.setdefault(self.rules.play_value(self, [c]), []).append(c)
        for strength, group in by_strength.items():
            if len(group) < 2 or strength * 2 > 10:
                continue
            for n in range(2, len(group) + 1):
                if strength * n > 10:
                    break
                for combo in itertools.combinations(group, n):
                    plays.append([c.id for c in combo])
        plays.extend(self.rules.extra_plays(self, hand))
        # keep only what the rules accept (lets a mission veto base plays)
        out = []
        for p in plays:
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
        # Other players may still change the attack (Kinfolk Flute): forecast as if they
        # all declined.
        while g.phase == PHASE_DECIDE and g.skip_decision():
            events.extend(g.last_events)
        damage = 0
        attack = 0
        powers: Dict[str, Any] = {}
        for ev in events:
            if ev["t"] == "damage":
                damage = ev["amount"]
            if ev["t"] in ("play", "add_to_play"):
                attack = ev["value"]
            if ev["t"] == "power":
                powers[ev["suit"]] = ev
        defeated = any(ev["t"] == "defeat" for ev in events)
        exact = any(ev["t"] == "defeat" and ev["exact"] for ev in events)
        return {"ok": True, "kind": kind, "attack": attack, "damage": damage, "powers": powers,
                "defeats": defeated, "exact": exact, "decision": decision,
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
        play = Play(me, [c.id for c in cards], value, suits)
        self.plays.append(play)
        self.last_action[me] = "played"
        self._event("play", player=me, cards=[c.id for c in cards], value=value, kind=kind)
        self._say("%s plays %s." % (self.players[me].name, " + ".join(c.label() for c in cards)))

        if kind == "jester":
            mode = self.rules.jester_mode(self)
            self.rules.on_cards_played(self, cards)
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

        self.rules.on_cards_played(self, cards)
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
        self._resolve_attack(cards, suits, value, choice)

    def play_suits(self, cards: Sequence[Card]) -> Tuple[str, ...]:
        """The suits of an attack, each once, in resolution order."""
        return tuple(sorted(set(s for c in cards for s in c.suits), key=_suit_sort_key))

    # --- decisions (decide phase) ------------------------------------------------
    def decide(self, action: dict) -> None:
        """Apply the deciding player's choice (one of ``rules.decision_actions``)."""
        self.last_events = []
        if self.phase != PHASE_DECIDE or self.decision is None:
            raise IllegalAction("No decision pending.")
        wanted = _action_key(action)
        if wanted not in [_action_key(a) for a in self.rules.decision_actions(self)]:
            raise IllegalAction("That choice is not available.")
        self.rules.decide(self, action)

    def skip_decision(self) -> bool:
        """Take the decision's "do nothing" option if there is one (forecasts, bots)."""
        for a in self.legal_actions():
            if a.get("skip"):
                self.decide(a)
                return True
        return False

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
        play.card_ids.extend(ids)
        cards = [self.cards[c] for c in play.card_ids]
        play.value = self.rules.play_value(self, cards)
        play.suits = self.play_suits(cards)
        self._event("add_to_play", player=player, cards=ids, play_index=play_index, value=play.value)
        self.rules.on_cards_played(self, [self.cards[c] for c in ids])
        return play

    def resolve_pending_attack(self) -> None:
        """Leave the decide phase and resolve the attack the decision was about (step 2 on)."""
        decision = self.decision
        if decision is None:
            raise IllegalAction("No decision pending.")
        play = self.plays[int(decision["play_index"])]
        self.decision = None
        self.phase = PHASE_PLAY
        cards = [self.cards[c] for c in play.card_ids]
        self._resolve_attack(cards, play.suits, play.value, decision.get("choice"))

    def _resolve_attack(self, cards: List[Card], suits: Tuple[str, ...], value: int,
                        choice: Optional[dict] = None) -> None:
        damage = value
        for suit in self.rules.power_order:
            if suit not in suits:
                continue
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
                res = self.rules.resolve_power(self, suit, value, cards)
                if isinstance(res, dict) and "damage" in res:
                    damage = int(res["damage"])
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
            self.plays.append(Play(self.active, [jid], 8, (suit,)))
            self.last_action[self.active] = "played"
            self.extra["jester_attack"] = True
            self._event("play", player=self.active, cards=[jid], value=8, kind="jester_attack")
            self._event("solo_jester", mode="attack", suit=suit, remaining=self.solo_jesters)
            self._say("Jester attacks as an 8 of %s, ignoring immunity (%d left)." % (
                SUIT_NAME.get(suit, suit), self.solo_jesters))
            self._resolve_attack([played], (suit,), 8, None)
            return
        p = self.active_player
        old = list(p.hand)
        self._discard_cards([self.cards[c] for c in old])
        p.hand = []
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
        cards = [self.cards[c] for c in ids]
        total = sum(c.defence_value for c in cards)
        feign = False
        if total < self.pending_damage:
            if self.feign_death_available() and set(ids) == set(hand):
                feign = True
            else:
                raise IllegalAction("Those cards cover %d damage; %d is needed." % (total, self.pending_damage))
        elif self.config.strict_minimal_discard:
            for c in cards:
                if total - c.defence_value >= self.pending_damage:
                    raise IllegalAction("%s is not needed to cover the damage." % c.label())
        for c in cards:
            hand.remove(c.id)
        self._discard_cards(cards)
        if feign:
            self._event("feign_death", player=self.active, cards=ids, damage=self.pending_damage)
            self._say("%s feigns death, discarding the whole hand." % self.active_player.name)
        self._event("suffer", player=self.active, cards=ids, damage=self.pending_damage, paid=total)
        self._say("%s discards %s to suffer %d." % (
            self.active_player.name, " ".join(c.label() for c in cards) or "nothing", self.pending_damage))
        self.pending_damage = 0
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
        self.tavern.extend(moved)  # under the tavern deck
        self._event("heal", cards=moved)
        return len(moved)

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

    def _defeat_enemy(self, exact: bool) -> None:
        enemy = self.enemy
        assert enemy is not None
        plan = self.rules.defeat_plan(self, exact)
        played = [self.cards[c] for p in self.plays for c in p.card_ids]
        if self.rules.solo_jester_mode(self) == "attack":
            # Official solo rule: the Jester is never cleaned up to any pile; it goes back
            # to the side, face down, unusable for the rest of this attempt.
            spent = [c for c in played if c.is_jester]
            played = [c for c in played if not c.is_jester]
            self.set_aside.extend(c.id for c in spent)
        self._event("defeat", enemy=enemy.card_id, exact=exact, plan=plan)
        self._say("%s is defeated%s" % (enemy.name, " with exact damage! It joins the tavern deck." if exact else "."))
        self.enemies_defeated += 1
        if plan.get("played_to", "discard") == "discard":
            self._discard_cards(played)
        elif plan["played_to"] == "banish":
            self.banished.extend(c.id for c in played)
        dest = plan.get("enemy_to", "discard")
        if dest == "tavern_top":
            self.tavern.insert(0, enemy.card_id)
        elif dest == "discard":
            self.discard.insert(0, enemy.card_id)
        elif dest == "banish":
            self.banished.append(enemy.card_id)
        elif dest == "castle_bottom":
            self.castle.append(enemy.card_id)
        self.plays = []
        self.immunity_cancelled = False
        self.enemy = None
        if self.config.yield_reset_per_enemy:
            self.last_action = [None] * self.n_players
        if not self.castle:
            self._win()
            return
        self._reveal_next_enemy()
        # The player who defeated the enemy takes a new turn (no damage suffered).
        self.turn += 1
        self.phase = PHASE_PLAY
        self._start_turn()

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
        self.rules.on_turn_end(self)
        if self.is_over:
            return
        self.active = (self.active + 1) % self.n_players
        self.turn += 1
        self.phase = PHASE_PLAY
        self._start_turn()

    def _start_turn(self) -> None:
        if self.is_over:
            return
        self.phase = PHASE_PLAY
        self.pending_damage = 0
        self._event("turn", player=self.active, turn=self.turn)
        self.rules.on_turn_start(self)
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


def _action_key(action: dict) -> Tuple[str, Tuple[str, ...]]:
    """What identifies a decision action: its type and the (order-free) cards it names."""
    cards = action.get("card_ids") or action.get("cards") or []
    return str(action.get("type")), tuple(sorted(str(c) for c in cards))
