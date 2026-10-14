"""Evergreen mode (pack E, confirmed from the cards): one rule set parameterised by the
drawn location, banes and boons (``config.extra["evergreen"]``, see ``evergreen.py``).

The location gives the base behaviour (its setup is applied by ``evergreen.build_setup``,
its start/end of turn, special rule and enemy-defeated step live here). Each bane and
boon is a small handler keyed by its card number so that every card can be tested on its
own. Where several effects share a moment they resolve in a fixed order: the location's
first, then the banes and boons by number (the pack gives no order; see the docstrings).

Flows with several decisions in a row (end of turn: the Hills' team damage, bane 12's
hand card, bane 23's choice; enemy defeated: the exact-kill boons 32 and 33, the Forest's
and Hills' optional discard, the Lake's zone order; after an attack: bane 21, boon 30;
after suffering: boon 31 per discarded card, boon 35's pick) keep a task queue in
``game.extra`` and chain through ``LegacyRules._decision_done``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..cards import BASIC_SUITS, CLASS_NAME, Card
from ..rules import register_rules
from .legacy_rules import LegacyRules
from . import evergreen as E


@register_rules
class EvergreenRules(LegacyRules):
    id = "evergreen"
    mission = 13
    uses_mission_zone = True

    # ------------------------------------------------------------------ the drawn setup
    def setup(self, game) -> Dict[str, Any]:
        return game.config.extra.get("evergreen", {})

    def location(self, game) -> str:
        return str(self.setup(game).get("location", "A"))

    def banes(self, game) -> List[int]:
        return [int(n) for n in self.setup(game).get("banes", [])]

    def boons(self, game) -> List[int]:
        return [int(n) for n in self.setup(game).get("boons", [])]

    def has_bane(self, game, n: int) -> bool:
        return n in self.banes(game)

    def has_boon(self, game, n: int) -> bool:
        return n in self.boons(game)

    def location_name(self, game) -> str:
        return str(E.location_by_id(self.location(game))["name"])

    # ------------------------------------------------------------------ setup
    def build_decks(self, game) -> None:
        super().build_decks(game)
        # the Lake: "shuffle pilgrims and place in pilgrim deck in mission zone" (face down,
        # top first; mission 7's deck without mission 7's hand lock)
        pilgrims = [Card.from_dict(d) for d in game.config.extra.get("pilgrims", [])]
        if pilgrims:
            for c in pilgrims:
                if c.id in game.cards:
                    raise ValueError("duplicate card id %s" % c.id)
                game.cards[c.id] = c
            game.extra["pilgrim_deck"] = [c.id for c in pilgrims]
        if self.has_bane(game, 2):
            # Mental Health Day: "put 30 cards from top of reserve deck into the discard
            # pile" (at setup, before the hands are drawn)
            n = min(30, len(game.tavern))
            moved = game.tavern[:n]
            del game.tavern[:n]
            # the pile's top is index 0: the reserve's former top card ends on top of the pile
            game.discard = moved + game.discard
            game._say("Mental Health Day: %d cards from the top of the reserve deck start in the discard pile." % n)

    # ------------------------------------------------------------------ queries
    def kinfolk_limit(self, game) -> int:
        # boon 34, An Alliance: "increase the Kinfolk Attack strength limit from 10 to 12"
        return 12 if self.has_boon(game, 34) else 10

    def card_suits(self, game, card: Card) -> Tuple[str, ...]:
        # boon 28, Best Friend: "when you play the puppy it has all four base classes"
        if card.has("evergreen_puppy"):
            return tuple(BASIC_SUITS)
        return super().card_suits(game, card)    # a Wild Animal's declared class

    def discard_top_feeds_enemy(self, game) -> bool:
        # bane 10 moves the top discard into the zone, 17 adds its strength, 19 its classes
        return any(self.has_bane(game, n) for n in (10, 17, 19))

    def banished_top_matters(self, game) -> bool:
        # the Forest and the Hills move the top banished card into the zone; bane 18 adds
        # its strength, bane 20 its classes
        return self.location(game) in ("C", "D") or self.has_bane(game, 18) or self.has_bane(game, 20)

    def attack_bonus(self, game) -> int:
        bonus = 0
        if self.location(game) == "C":
            # the Forest: additional strength equal to the zone's combined strength
            bonus += self.zone_strength(game)
        if self.has_bane(game, 17):   # Beastly Vigor: the top discard's strength
            bonus += self.top_card_strength(game, game.discard, False)
        if self.has_bane(game, 18):   # Mutated Beasts: the top banished card's strength
            bonus += self.top_card_strength(game, game.banished, True)
        return bonus

    def attack_multiplier(self, game) -> int:
        # bane 9, Lethal Warriors: "enemies with a warrior icon have double strength
        # (including from other strength bonuses)"
        if self.has_bane(game, 9) and game.enemy is not None and "C" in game.enemy.suits:
            return 2
        return 1

    def damage_reduction(self, game) -> int:
        # bane 11, Immovable Paladins: "enemies with a paladin icon reduce damage dealt to them by 10"
        if self.has_bane(game, 11) and game.enemy is not None and "S" in game.enemy.suits:
            return 10
        return 0

    def immune_suits(self, game) -> Tuple[str, ...]:
        base = list(super().immune_suits(game))
        if game.enemy is None:
            return tuple(base)
        extra: List[str] = []
        card = game.cards.get(game.enemy.card_id)
        if card is not None and card.has("immune_basic"):
            extra.extend(BASIC_SUITS)                          # bane 8: the High Arcana
        if self.location(game) == "A":
            extra.extend(self.zone_suits(game))               # the Shrine: the zone's classes
        if self.has_bane(game, 19):
            extra.extend(self.top_card_suits(game, game.discard, False))    # Shapeshift
        if self.has_bane(game, 20):
            extra.extend(self.top_card_suits(game, game.banished, True))    # Fused Bones
        for s in extra:
            if s not in base:
                base.append(s)
        return tuple(base)

    # ------------------------------------------------------------------ small moves
    def _zone_add(self, game, cid: str, source: str, why: str) -> None:
        game.mission_zone.append(cid)
        game._event("zone_add", card=cid, zone=list(game.mission_zone), source=source)
        game._say("%s: %s goes into the mission zone (zone strength %d)." % (why, game.cards[cid].label(), self.zone_strength(game)))

    def _banish_discard_pile(self, game, why: str) -> None:
        pile = list(game.discard)
        if not pile:
            return
        game.discard = []
        game.banish_cards(list(reversed(pile)))    # the pile keeps its order, its top ends on top
        game._event("discard_banished", cards=pile)
        game._say("%s: the whole discard pile (%d card%s) is banished." % (why, len(pile), "" if len(pile) == 1 else "s"))

    def _hand_options(self, game, kind: str, player: int, verb: str) -> List[Dict[str, Any]]:
        return [{"type": kind, "player": player, "card": cid, "label": "%s %s" % (verb, game.cards[cid].label())}
                for cid in self.unlocked_hand(game, player)]

    # ------------------------------------------------------------------ start of turn
    def on_turn_start(self, game) -> Optional[Dict[str, Any]]:
        if game.is_over:
            return None
        if self.location(game) == "E":
            # the Lake: the top pilgrim, or the top reserve card once the pilgrims are out
            deck = game.extra.get("pilgrim_deck", [])
            if deck:
                self._zone_add(game, deck.pop(0), "pilgrims", "Start of turn (the Lake)")
            elif game.tavern:
                self._zone_add(game, game.tavern.pop(0), "reserve", "Start of turn (the Lake, no pilgrims left)")
        if self.has_bane(game, 16) and game.discard:
            # Lingering Dread: the top discard goes to the banished pile
            lost = game.discard.pop(0)
            game.banish_cards([lost])
            game._event("bane", n=16, card=lost)
            game._say("Lingering Dread: %s, the top card of the discard pile, is banished." % game.cards[lost].label())
        if self.has_bane(game, 22) and game.tavern:
            # The Fiery Crucible: the top reserve card goes to the discard pile
            lost = game.tavern.pop(0)
            game.discard.insert(0, lost)
            game._event("bane", n=22, card=lost)
            game._say("The Fiery Crucible: %s, the top card of the reserve deck, is discarded." % game.cards[lost].label())
        return None

    # ------------------------------------------------------------------ end of turn
    def on_turn_end(self, game) -> Optional[Dict[str, Any]]:
        if game.is_over or game.enemy is None:
            return None
        loc = self.location(game)
        tasks: List[str] = []
        if loc in ("A", "B"):
            if game.tavern:
                self._zone_add(game, game.tavern.pop(0), "reserve", "End of turn (the %s)" % self.location_name(game))
            if loc == "B" and game.mission_zone and self.zone_strength(game) >= game.enemy.attack:
                # the Cave: "if the combined strength of cards in the mission zone equal or
                # exceed the base strength of the current enemy, banish the mission zone
                # and the entire discard pile"
                zone = list(game.mission_zone)
                game.mission_zone = []
                game.banish_cards(zone)
                game._event("zone_cleared", cards=zone, to="banish")
                game._say("The Cave: the mission zone (%d) reaches %s's base strength (%d): it is banished." % (
                    sum(self.card_strength(game, game.cards[c]) for c in zone), game.enemy.name, game.enemy.attack))
                self._banish_discard_pile(game, "The Cave")
        elif loc in ("C", "D"):
            if game.banished:
                self._zone_add(game, game.banished.pop(), "banished", "End of turn (the %s)" % self.location_name(game))
            if loc == "D":
                tasks.append("hills")
        if self.has_bane(game, 10) and "H" in game.enemy.suits:
            tasks.append("bane10")
        if self.has_bane(game, 12) and "D" in game.enemy.suits:
            tasks.append("bane12")
        if self.has_bane(game, 23):
            tasks.append("bane23")
        game.extra["eot_queue"] = tasks
        return self._eot_next(game)

    def _eot_next(self, game) -> Optional[Dict[str, Any]]:
        queue = game.extra.get("eot_queue") or []
        while queue:
            task = queue.pop(0)
            d = self._eot_task(game, task)
            if game.is_over:
                game.extra.pop("eot_queue", None)
                return None
            if d is not None:
                return d
        game.extra.pop("eot_queue", None)
        return None

    def _eot_task(self, game, task: str) -> Optional[Dict[str, Any]]:
        who = game.players[game.active].name
        if task == "hills":
            # the Hills: team damage equal to the zone's combined strength, mission 6 rules
            d: Dict[str, Any] = {"player": game.active}
            if self._start_team_damage(game, d, self.zone_strength(game), "The Hills"):
                return d
            return None
        if task == "bane10":
            # Poisonous Clerics: the top discard goes into the zone
            if game.discard:
                self._zone_add(game, game.discard.pop(0), "discard", "Poisonous Clerics")
            return None
        if task == "bane12":
            # Duplicitous Bards: "put a card from your hand into the mission zone"
            if self.unlocked_hand(game, game.active):
                game._say("Duplicitous Bards: %s must put a card from hand into the mission zone." % who)
                return {"kind": "zone_feed", "player": game.active, "reason": "bane12"}
            return None
        if task == "bane23":
            # Choose Your Poison: "you may discard a card from hand; if you don't, put the
            # top card of the reserve deck into the mission zone"
            if self.unlocked_hand(game, game.active):
                game._say("Choose Your Poison: %s may discard a card from hand, or the top reserve card goes into the mission zone." % who)
                return {"kind": "poison", "player": game.active}
            self._poison_reserve(game)
            return None
        return None

    def _poison_reserve(self, game) -> None:
        if game.tavern:
            self._zone_add(game, game.tavern.pop(0), "reserve", "Choose Your Poison")
        else:
            game._say("Choose Your Poison: the reserve deck is empty, nothing goes into the mission zone.")

    def _eot_done(self, game, d: Dict[str, Any]) -> None:
        nd = self._eot_next(game)
        if game.is_over:
            return
        if nd is None:
            game.resume_end_turn()
            return
        nd["resume"] = "end_turn"
        game.decision = nd
        game._event("decide", **nd)

    # --- zone_feed (bane 12; the same decision as mission 10's bard) --------------------------
    def _actions_zone_feed(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._hand_options(game, "zone_feed", int(d["player"]), "Put into the mission zone:")

    def _decide_zone_feed(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        cid = str(action["card"])
        if cid not in self.unlocked_hand(game, player):
            from ..engine import IllegalAction
            raise IllegalAction("Card %s is not in hand." % cid)
        game.players[player].hand.remove(cid)
        game.mission_zone.append(cid)
        game._event("zone_feed", player=player, card=cid, zone=list(game.mission_zone), bonus=self.attack_bonus(game))
        game._say("%s puts %s into the mission zone." % (game.players[player].name, game.cards[cid].label()))
        self._decision_done(game, d)

    # --- poison (bane 23) --------------------------------------------------------------------
    def _actions_poison(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = self._hand_options(game, "poison", player, "Discard")
        acts.append({"type": "poison_skip", "player": player, "skip": True,
                     "label": "Discard nothing: the top reserve card goes into the mission zone"})
        return acts

    def _decide_poison(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        if action["type"] == "poison":
            cid = str(action["card"])
            if cid not in self.unlocked_hand(game, player):
                from ..engine import IllegalAction
                raise IllegalAction("Card %s is not in hand." % cid)
            game.players[player].hand.remove(cid)
            game._discard_cards([game.cards[cid]])
            game._event("poison", player=player, card=cid)
            game._say("Choose Your Poison: %s discards %s." % (game.players[player].name, game.cards[cid].label()))
        else:
            game._event("poison_skip", player=player)
            self._poison_reserve(game)
        self._decision_done(game, d)

    # ------------------------------------------------------------------ after an attack is formed
    # Bane 21 (Eye-Level Sticks) and boon 30 (Squad of Siblings) say "immediately after you
    # form an attack": they are the attacker's own and resolve on the attack as formed in
    # step 1, before the relics (Kinfolk Flute, Scarlet Whistle) let others add to it and
    # before any mage looks. Bane 21 first (by number), then boon 30.
    def _relic_after_attack(self, game, play) -> Optional[Dict[str, Any]]:
        idx = len(game.plays) - 1
        queue = game.extra.get("attack_queue")
        if not queue or int(queue.get("play_index", -1)) != idx:
            tasks: List[str] = []
            if self.has_bane(game, 21):
                tasks.append("bane21")
            if self.has_boon(game, 30):
                tasks.append("boon30")
            game.extra["attack_queue"] = {"play_index": idx, "tasks": tasks}
        d = self._attack_next(game, play)
        if d is not None:
            return d
        return super()._relic_after_attack(game, play)

    def _attack_strengths(self, game, play) -> List[int]:
        return [self.in_play_strength(game, game.cards[c]) for c in play.card_ids if not game.cards[c].has("beast")]

    def _attack_next(self, game, play) -> Optional[Dict[str, Any]]:
        queue = game.extra.get("attack_queue") or {}
        tasks = queue.get("tasks") or []
        who = game.players[play.player].name
        while tasks:
            task = tasks.pop(0)
            if task == "bane21":
                if any(s >= 8 for s in self._attack_strengths(game, play)) and self.unlocked_hand(game, play.player):
                    game._say("Eye-Level Sticks: the attack holds a card of strength 8 or more; %s must discard a card from hand." % who)
                    return {"kind": "attack_discard", "player": play.player, "resume": "attack"}
            elif task == "boon30":
                options = self._sibling_options(game, play)
                if options:
                    game._say("Squad of Siblings: %s may move a mission zone card of the same strength as an attack card to the discard pile." % who)
                    return {"kind": "zone_sibling", "player": play.player, "options": options, "resume": "attack"}
        game.extra.pop("attack_queue", None)
        return None

    def _sibling_options(self, game, play) -> List[str]:
        strengths = set(self._attack_strengths(game, play))
        return [c for c in game.mission_zone if self.card_strength(game, game.cards[c]) in strengths]

    def _decision_done(self, game, d: Dict[str, Any]) -> None:
        if str(d.get("resume")) == "attack":
            self._attack_step_done(game, d)
            return
        super()._decision_done(game, d)

    def _attack_step_done(self, game, d: Dict[str, Any]) -> None:
        play_index = int(d["play_index"])
        play = game.plays[play_index]
        nd = self._attack_next(game, play)
        if nd is None:
            nd = LegacyRules._relic_after_attack(self, game, play)
            if nd is None:
                game.resolve_pending_attack()
                return
        nd["play_index"] = play_index
        if "choice" in d:
            nd["choice"] = d["choice"]
        game.decision = nd
        game._event("decide", **nd)

    def _actions_attack_discard(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._hand_options(game, "attack_discard", int(d["player"]), "Discard")

    def _decide_attack_discard(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        cid = str(action["card"])
        if cid not in self.unlocked_hand(game, player):
            from ..engine import IllegalAction
            raise IllegalAction("Card %s is not in hand." % cid)
        game.players[player].hand.remove(cid)
        game._discard_cards([game.cards[cid]])
        game._event("attack_discard", player=player, card=cid)
        game._say("Eye-Level Sticks: %s discards %s." % (game.players[player].name, game.cards[cid].label()))
        self._decision_done(game, d)

    def _actions_zone_sibling(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "zone_sibling", "player": player, "card": str(cid),
                 "label": "Move %s to the discard pile" % game.cards[str(cid)].label()}
                for cid in d.get("options", []) if str(cid) in game.mission_zone]
        acts.append({"type": "zone_sibling_skip", "player": player, "skip": True, "label": "Leave the mission zone"})
        return acts

    def _decide_zone_sibling(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        self._zone_to_discard(game, d, action, "zone_sibling", "Squad of Siblings")
        self._decision_done(game, d)

    def _zone_to_discard(self, game, d: Dict[str, Any], action: Dict[str, Any], kind: str, why: str) -> None:
        player = int(d["player"])
        if action["type"] == kind:
            cid = str(action["card"])
            if cid not in game.mission_zone or cid not in [str(c) for c in d.get("options", [])]:
                from ..engine import IllegalAction
                raise IllegalAction("%s cannot leave the mission zone now." % cid)
            game.mission_zone.remove(cid)
            game.discard.insert(0, cid)
            game._event(kind, player=player, card=cid, zone=list(game.mission_zone))
            game._say("%s: %s moves %s from the mission zone to the discard pile." % (why, game.players[player].name, game.cards[cid].label()))
        else:
            game._event(kind + "_skip", player=player)
            game._say("%s: the mission zone is left alone." % why)

    def forecast_action(self, game) -> Optional[Dict[str, Any]]:
        d = game.decision
        if d and d.get("kind") == "attack_discard":
            # a forecast assumes the attacker discards the weakest hand card
            hand = self.unlocked_hand(game, int(d["player"]))
            if hand:
                low = min(hand, key=lambda c: (game.cards[c].value, c))
                return {"type": "attack_discard", "player": int(d["player"]), "card": low, "forecast": True}
        if d and d.get("kind") in ("banish_order", "zone_order"):
            acts = self.decision_actions(game)
            if acts:
                return {"type": str(d["kind"]), "player": int(d["player"]), "cards": list(acts[0]["pick_from"]), "forecast": True}
        return super().forecast_action(game)

    # ------------------------------------------------------------------ suffering damage
    def discard_suffered(self, game, cards: Sequence[Card], damage: int, feign: bool) -> None:
        total = sum(c.defence_value for c in cards)
        if self.has_boon(game, 35) and not feign and damage > 0 and total == damage:
            # A Close Call: "place the discarded cards on the bottom of the reserve deck
            # instead of the discard pile, then search the discard pile and put a card from
            # it on top of the reserve deck"
            for c in cards:
                game.to_reserve(c.id, bottom=True)
            game.extra["close_call"] = True
            game._event("close_call", cards=[c.id for c in cards])
            game._say("A Close Call: the damage was paid exactly, %s go under the reserve deck." % (
                " + ".join(c.label() for c in cards)))
            return
        game._discard_cards(list(cards))

    def after_suffer(self, game, cards: Sequence[Card], damage: int, feign: bool) -> Optional[Dict[str, Any]]:
        tasks: List[str] = []
        if self.has_boon(game, 31):
            # Selfless Rescue: per discarded card, a matching zone card may be discarded too
            for c in cards:
                tasks.append("match:" + c.id)
        if game.extra.pop("close_call", False) and game.discard:
            tasks.append("close_call")
        game.extra["suffer_queue"] = tasks
        return self._suffer_next(game)

    def _suffer_next(self, game) -> Optional[Dict[str, Any]]:
        queue = game.extra.get("suffer_queue") or []
        while queue:
            task = queue.pop(0)
            if task.startswith("match:"):
                cid = task[6:]
                strength = self.strength(game.cards[cid])
                options = [c for c in game.mission_zone if self.card_strength(game, game.cards[c]) == strength]
                if options:
                    game._say("Selfless Rescue: %s matches %s in the mission zone; %s may move it to the discard pile." % (
                        game.cards[cid].label(), " / ".join(game.cards[c].label() for c in options), game.players[game.active].name))
                    return {"kind": "zone_match", "player": game.active, "options": options, "matched": cid}
            elif task == "close_call" and game.discard:
                game._say("A Close Call: %s puts any card from the discard pile on top of the reserve deck." % game.players[game.active].name)
                return {"kind": "close_call", "player": game.active}
        game.extra.pop("suffer_queue", None)
        return None

    def _suffered_done(self, game, d: Dict[str, Any]) -> None:
        nd = self._suffer_next(game)
        if nd is None:
            game.resume_suffered()
            return
        nd["resume"] = "suffered"
        game.decision = nd
        game._event("decide", **nd)

    def _actions_zone_match(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "zone_match", "player": player, "card": str(cid),
                 "label": "Move %s to the discard pile" % game.cards[str(cid)].label()}
                for cid in d.get("options", []) if str(cid) in game.mission_zone]
        acts.append({"type": "zone_match_skip", "player": player, "skip": True, "label": "Leave the mission zone"})
        return acts

    def _decide_zone_match(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        self._zone_to_discard(game, d, action, "zone_match", "Selfless Rescue")
        self._decision_done(game, d)

    def _actions_close_call(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        return [{"type": "close_call", "player": player, "card": cid,
                 "label": "Put %s on top of the reserve" % game.cards[cid].label()} for cid in game.discard]

    def _decide_close_call(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        cid = str(action["card"])
        if cid not in game.discard:
            from ..engine import IllegalAction
            raise IllegalAction("%s is not in the discard pile." % cid)
        game.discard.remove(cid)
        game.to_reserve(cid)
        game._event("close_call_pick", player=player, card=cid)
        game._say("A Close Call: %s puts %s from the discard pile on top of the reserve deck." % (
            game.players[player].name, game.cards[cid].label()))
        self._decision_done(game, d)

    # ------------------------------------------------------------------ enemy defeated
    # Order of the enemy-defeated effects (the pack gives none): the exact-kill boons 32
    # and 33 first (boon 32 names the mission zone, which the location then empties), bane
    # 15 (its card says "before carrying out the Location rules"), the location's own
    # steps (with the Forest's and Hills' optional discard and the Lake's reserve banish
    # and zone order), then the engine moves the enemy and the zone as the plan says, bane
    # 14 keeps the killing attack in the zone (its card says "after"), and bane 13's team
    # damage comes once the piles are final.
    def before_defeat(self, game, exact: bool) -> Optional[Dict[str, Any]]:
        tasks: List[str] = []
        if exact and self.has_boon(game, 32):
            tasks.append("boon32")
        if exact and self.has_boon(game, 33):
            tasks.append("boon33")
        if not exact and self.has_bane(game, 15):
            tasks.append("bane15")
        loc = self.location(game)
        if loc in ("C", "D") and exact:
            tasks.append("zone_discard")
        if loc == "E":
            tasks.append("lake_banish")
            tasks.append("lake_order")
        game.extra["defeat_queue"] = tasks
        return self._defeat_next(game, exact)

    def _defeat_next(self, game, exact: bool) -> Optional[Dict[str, Any]]:
        queue = game.extra.get("defeat_queue") or []
        while queue:
            task = queue.pop(0)
            d = self._defeat_task(game, task, exact)
            if d is not None:
                return d
        game.extra.pop("defeat_queue", None)
        return None

    def _defeat_task(self, game, task: str, exact: bool) -> Optional[Dict[str, Any]]:
        who = game.players[game.active].name
        if task == "boon32":
            # Precision Strike: "put any card from the mission zone into your hand or put
            # the top card of the discard pile into your hand"
            if game.mission_zone or game.discard:
                game._say("Precision Strike: %s takes a mission zone card or the top discard into hand." % who)
                return {"kind": "precision_strike", "player": game.active}
            return None
        if task == "boon33":
            # Restored Arrows: "you may put any one card from the banished pile to the
            # bottom of the reserve deck"
            if game.banished:
                game._say("Restored Arrows: %s may put a banished card under the reserve deck." % who)
                return {"kind": "restored_arrows", "player": game.active}
            return None
        if task == "bane15":
            self._banish_discard_pile(game, "Tread Carefully")
            return None
        if task == "zone_discard":
            if game.mission_zone:
                game._say("Exact kill (the %s): %s may first discard one card from the mission zone." % (self.location_name(game), who))
                return {"kind": "zone_discard", "player": game.active, "options": list(game.mission_zone)}
            return None
        if task == "lake_banish":
            # the Lake: "for each card in the mission zone, banish a card from reserve deck"
            n = min(len(game.mission_zone), len(game.tavern))
            if n:
                lost = game.tavern[:n]
                del game.tavern[:n]
                game.banish_cards(lost)
                game._event("lake_banish", cards=lost, wanted=len(game.mission_zone))
                game._say("The Lake: %d card%s from the top of the reserve deck %s banished, one per mission zone card." % (
                    n, "" if n == 1 else "s", "is" if n == 1 else "are"))
            return None
        if task == "lake_order":
            if len(game.mission_zone) >= 2:
                game._say("The Lake: %s chooses the order in which the mission zone goes to the discard pile." % who)
                return {"kind": "zone_order", "player": game.active}
            return None
        return None

    def _defeat_step_done(self, game, d: Dict[str, Any]) -> None:
        if str(d.get("resume")) == "defeat_tail":
            game.resume_defeat()
            return
        nd = self._defeat_next(game, bool(d.get("exact")))
        if nd is None:
            game.resume_defeat()
            return
        nd["exact"] = d.get("exact")
        nd["resume"] = "defeat"
        game.decision = nd
        game._event("decide", **nd)

    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        loc = self.location(game)
        plan: Dict[str, Any] = {"played_to": "discard", "base_strength": game.enemy.attack if game.enemy else 0}
        if loc == "A":      # the Shrine: banish (discard on exact) the enemy, then banish the zone
            plan.update(enemy_to="discard" if exact else "banish", zone_to="banish")
        elif loc == "B":    # the Cave: banish (discard on exact) the enemy, then discard the zone
            plan.update(enemy_to="discard" if exact else "banish", zone_to="discard")
        elif loc in ("C", "D"):   # the Forest, the Hills: enemy and zone into the banished pile, then shuffle it
            plan.update(enemy_to="banish", zone_to="banish", shuffle_banished=True)
        else:               # the Lake: the zone to the discard pile, then banish (discard on exact) the enemy
            plan.update(enemy_to="discard" if exact else "banish", zone_to="discard", zone_first=True)
        if self.has_bane(game, 1) and not exact and game.enemy is not None and game.enemy.name == "Hydra Head":
            # Six is the New Four: a Hydra not dealt exact damage returns to the bottom of
            # the enemy deck, whatever the location says
            plan["enemy_to"] = "castle_bottom"
        if self.has_bane(game, 14):
            plan["last_play_to"] = "zone"     # Absorbtion
        return plan

    def after_cleanup(self, game, exact: bool, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self.has_bane(game, 13):
            # Explosive Spores: team damage equal to the defeated enemy's base strength
            d: Dict[str, Any] = {"player": game.active}
            if self._start_team_damage(game, d, int(plan.get("base_strength", 0)), "Explosive Spores"):
                return d
        return None

    # --- the decisions of the enemy-defeated chain --------------------------------------------
    def _actions_precision_strike(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "precision_strike", "player": player, "card": cid, "pile": "zone",
                 "label": "Take %s from the mission zone" % game.cards[cid].label()} for cid in game.mission_zone]
        if game.discard:
            top = game.discard[0]
            acts.append({"type": "precision_strike", "player": player, "card": top, "pile": "discard",
                         "label": "Take top of discard (%s)" % game.cards[top].label()})
        return acts

    def _decide_precision_strike(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        from ..engine import IllegalAction
        player = int(d["player"])
        cid = str(action["card"])
        pile = str(action.get("pile", "zone"))
        if pile == "zone" and cid in game.mission_zone:
            game.mission_zone.remove(cid)
        elif pile == "discard" and game.discard and game.discard[0] == cid:
            game.discard.pop(0)
        else:
            raise IllegalAction("%s cannot be taken now." % cid)
        game.players[player].hand.append(cid)
        game._event("precision_strike", player=player, card=cid, pile=pile)
        game._say("Precision Strike: %s takes %s from the %s into hand." % (
            game.players[player].name, game.cards[cid].label(), "mission zone" if pile == "zone" else "discard pile"))
        self._decision_done(game, d)

    def _actions_restored_arrows(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "restored_arrows", "player": player, "card": cid,
                 "label": "Put %s under the reserve deck" % game.cards[cid].label()} for cid in game.banished]
        acts.append({"type": "restored_arrows_skip", "player": player, "skip": True, "label": "Leave the banished pile"})
        return acts

    def _decide_restored_arrows(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        if action["type"] == "restored_arrows":
            cid = str(action["card"])
            if cid not in game.banished:
                from ..engine import IllegalAction
                raise IllegalAction("%s is not in the banished pile." % cid)
            game.banished.remove(cid)
            game.to_reserve(cid, bottom=True)
            game._event("restored_arrows", player=player, card=cid)
            game._say("Restored Arrows: %s puts %s from the banished pile under the reserve deck." % (
                game.players[player].name, game.cards[cid].label()))
        else:
            game._event("restored_arrows_skip", player=player)
            game._say("Restored Arrows: the banished pile is left alone.")
        self._decision_done(game, d)

    def _actions_zone_discard(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "zone_discard", "player": player, "card": str(cid),
                 "label": "Discard %s" % game.cards[str(cid)].label()}
                for cid in d.get("options", []) if str(cid) in game.mission_zone]
        acts.append({"type": "zone_discard_skip", "player": player, "skip": True, "label": "Discard nothing"})
        return acts

    def _decide_zone_discard(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        self._zone_to_discard(game, d, action, "zone_discard", "Exact kill")
        self._decision_done(game, d)

    def _actions_zone_order(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        zone = list(game.mission_zone)
        return [{"type": "zone_order", "player": int(d["player"]), "pick_from": zone, "needs": len(zone),
                 "ordered": True, "label": "Discard the mission zone in this order (the last ends on top)"}]

    def _decide_zone_order(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        from ..engine import IllegalAction
        ids = [str(c) for c in action.get("cards", [])]
        if sorted(ids) != sorted(game.mission_zone):
            raise IllegalAction("Name every mission zone card exactly once.")
        game.mission_zone = ids
        game.extra["zone_order_keep"] = True
        game._event("zone_order", player=int(d["player"]), cards=ids)
        game._say("%s discards the mission zone in the order %s (%s on top)." % (
            game.players[int(d["player"])].name, ", ".join(game.cards[c].label() for c in ids), game.cards[ids[-1]].label()))
        self._decision_done(game, d)

    def order_for_discard(self, game, cards: List[Card]) -> List[Card]:
        # the Lake's chosen zone order (the zone is discarded before the played cards) must
        # survive the campaign's low-to-high habit
        if game.extra.pop("zone_order_keep", False):
            return list(cards)
        return super().order_for_discard(game, cards)
