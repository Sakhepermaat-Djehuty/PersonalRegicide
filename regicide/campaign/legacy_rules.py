"""Rule sets for Regicide Legacy missions (hooks on top of BaseRules)."""
from __future__ import annotations

import itertools
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..cards import BASIC_SUITS, SUIT_NAME, Card, jester_card
from ..rules import BaseRules, classify_combo, register_rules
from ..rules import HAND_SIZE, JESTERS_IN_DECK


class LegacyRules(BaseRules):
    """Mission 1 rules: base Regicide plus the Legacy-wide changes."""

    id = "legacy_m1"
    mission = 1
    # Resolution order from the printed player helper card (confirmed by the owner):
    # step 2 "cast spells": Mage, Druid, Cleric (H), Bard (D), Chanter;
    # step 3 "deal damage": Reaver, Warrior (C);
    # step 4a "suffer damage": Paladin (S), Guardian.
    power_order = ("M", "U", "H", "D", "T", "R", "C", "S", "G")

    # ------------------------------------------------------------------ setup
    def build_decks(self, game) -> None:
        extra = game.config.extra
        party = [Card.from_dict(d) for d in extra.get("party", [])]
        castle = [Card.from_dict(d) for d in extra.get("castle", [])]
        reserve = list(party)
        jesters = game.config.deck_jesters + int(extra.get("extra_jesters", 0)) if game.n_players > 1 else 0
        for i in range(jesters):
            reserve.append(jester_card(i + 1))
        if game.n_players == 1:
            game.solo_jesters = 2 + int(extra.get("extra_jesters", 0))
        game.cards = {}
        for c in reserve + castle:
            if c.id in game.cards:
                raise ValueError("duplicate card id %s" % c.id)
            game.cards[c.id] = c
        game.rng.shuffle(reserve)
        game.tavern = [c.id for c in reserve]
        game.castle = [c.id for c in castle]
        game.extra["relics"] = list(extra.get("relics", []))
        if "flute" in game.extra["relics"]:
            game.extra["flute"] = []
            game.extra["flute_turn"] = -1

    # ------------------------------------------------------------------ queries
    def immune(self, game, suit: str, cards: Sequence[Card] = ()) -> bool:
        if not super().immune(game, suit, cards):
            return False
        for c in cards:
            if suit in c.suits and (c.has("corrupted") or c.has("restored") or c.has("ignores_immunity")):
                return False
        return True

    def jester_mode(self, game) -> str:
        return "claim"

    def solo_jester_mode(self, game) -> str:
        return "attack"

    def feign_death_allowed(self, game) -> bool:
        return len(game.active_player.hand) >= game.config.max_hand

    @staticmethod
    def strength(card: Card) -> int:
        """A card's strength in an attack (the 2/5 mercenary attacks as a 2)."""
        return 2 if card.has("twofive") else card.value

    def validate_combo(self, game, cards: Sequence[Card]) -> Tuple[str, Optional[str]]:
        # Kinfolk (rulebook p.22): any number of cards of equal STRENGTH totalling at most
        # 10, so five 2s are legal and a 2/5 card pairs with a 2. No four-card cap.
        return classify_combo(cards, strength=self.strength, max_cards=None)

    def play_value(self, game, cards: Sequence[Card]) -> int:
        return sum(self.strength(c) for c in cards)

    def playable_ids(self, game) -> List[str]:
        ids = list(game.active_player.hand)
        if game.n_players == 1 or True:
            ids.extend(game.extra.get("flute", []))
        return ids

    def remove_played(self, game, card_id: str) -> None:
        hand = game.active_player.hand
        if card_id in hand:
            hand.remove(card_id)
            return
        flute = game.extra.get("flute", [])
        if card_id in flute:
            flute.remove(card_id)
            return
        raise ValueError("card %s is neither in hand nor on the flute" % card_id)

    # ------------------------------------------------------------------ relics
    def special_actions(self, game) -> List[Dict[str, Any]]:
        """Kinfolk Flute, solo side (unverified, from the fan implementation): once per
        turn store one card of strength 2–5 on the flute; flute cards may later join a
        kinfolk attack. The multiplayer side (confirmed from the card) is not a special
        action but a decision: see ``after_attack_formed`` below."""
        acts: List[Dict[str, Any]] = []
        if "flute" in game.extra.get("relics", []) and game.phase == "play" and game.config.players == 1:
            if game.extra.get("flute_turn") != game.turn:
                flute = game.extra.get("flute", [])
                rank = game.cards[flute[0]].rank if flute else None
                for cid in game.active_player.hand:
                    c = game.cards[cid]
                    v = self.strength(c)
                    if 2 <= v <= 5 and c.is_number and (rank is None or c.rank == rank) and not c.name:
                        acts.append({"type": "special", "name": "flute_store", "card": cid,
                                     "label": "Store %s on the Kinfolk Flute" % c.label()})
        return acts

    def do_special(self, game, action: Dict[str, Any]) -> None:
        if action.get("name") == "flute_store":
            cid = action["card"]
            legal = [a for a in self.special_actions(game) if a.get("name") == "flute_store" and a["card"] == cid]
            if not legal:
                from ..engine import IllegalAction
                raise IllegalAction("That card cannot go on the flute now.")
            game.active_player.hand.remove(cid)
            game.extra.setdefault("flute", []).append(cid)
            game.extra["flute_turn"] = game.turn
            game._event("flute_store", card=cid)
            game._say("%s stores %s on the Kinfolk Flute." % (game.active_player.name, game.cards[cid].label()))
            game._check_can_act()
            return
        raise NotImplementedError(action)

    # ------------------------------------------------------- Kinfolk Flute, 2+ players
    # Card text (confirmed): "After you form an attack (before proceeding to Step 2), other
    # players may add cards from their hand to the attack, as long as the added cards form
    # a valid Kinfolk Attack. Animal Companions may not be added this way as they cannot
    # be a part of Kinfolk Attacks." Reading used here: the attack plus everything added
    # must be one valid kinfolk attack (equal strength, total at most 10, no companion,
    # beast or Jester on either side). Players are asked clockwise from the attacker's
    # left; each may add any legal subset of their hand or pass; players with nothing to
    # add are skipped. The combined attack then resolves as usual (abilities at the total,
    # corrupted newcomers banish, everything goes to the discard at clean-up); only the
    # attacker suffers damage.
    def _flute_multiplayer(self, game) -> bool:
        return "flute" in game.extra.get("relics", []) and game.config.players >= 2

    def _kinfolk_strength(self, game, play) -> Optional[int]:
        """The common strength of an attack that may grow into a kinfolk attack, or None."""
        strengths = set()
        for cid in play.card_ids:
            c = game.cards[cid]
            if c.is_ace or c.is_jester or c.has("beast"):
                return None
            strengths.add(self.strength(c))
        if len(strengths) != 1:
            return None
        s = strengths.pop()
        return s if s > 0 else None

    def _flute_candidates(self, game, player: int, strength: int, total: int) -> List[Card]:
        """Cards ``player`` could add: same strength, and at least one still fits under 10."""
        if total + strength > 10:
            return []
        out = []
        for cid in game.players[player].hand:
            c = game.cards[cid]
            if c.is_ace or c.is_jester or c.has("beast"):
                continue
            if self.strength(c) == strength:
                out.append(c)
        return out

    def _flute_next(self, game, queue: Sequence[int], strength: int, total: int) -> Tuple[Optional[int], List[int]]:
        """First queued player with something to add, and the players after them."""
        rest = list(queue)
        while rest:
            p = rest.pop(0)
            if self._flute_candidates(game, p, strength, total):
                return p, rest
        return None, []

    def after_attack_formed(self, game, play) -> Optional[Dict[str, Any]]:
        if not self._flute_multiplayer(game):
            return None
        strength = self._kinfolk_strength(game, play)
        if strength is None:
            return None
        queue = [(play.player + k) % game.n_players for k in range(1, game.n_players)]
        player, rest = self._flute_next(game, queue, strength, play.value)
        if player is None:
            return None
        game._say("Kinfolk Flute: %s may add %ss to %s's attack." % (
            game.players[player].name, strength, game.players[play.player].name))
        return {"kind": "flute_add", "player": player, "strength": strength, "queue": rest}

    def decision_actions(self, game) -> List[Dict[str, Any]]:
        d = game.decision
        if not d or d.get("kind") != "flute_add":
            return []
        play = game.plays[int(d["play_index"])]
        strength = int(d["strength"])
        player = int(d["player"])
        cands = self._flute_candidates(game, player, strength, play.value)
        acts: List[Dict[str, Any]] = []
        room = (10 - play.value) // strength
        for n in range(1, min(room, len(cands)) + 1):
            for combo in itertools.combinations(cands, n):
                acts.append({"type": "flute_add", "player": player, "card_ids": [c.id for c in combo],
                             "label": "Add %s (attack %d)" % (" + ".join(c.label() for c in combo),
                                                              play.value + n * strength)})
        acts.append({"type": "flute_pass", "player": player, "skip": True, "label": "Pass"})
        return acts

    def decide(self, game, action: Dict[str, Any]) -> None:
        d = game.decision
        if not d or d.get("kind") != "flute_add":
            raise NotImplementedError(action)
        player = int(d["player"])
        play_index = int(d["play_index"])
        name = game.players[player].name
        if action["type"] == "flute_add":
            ids = list(action["card_ids"])
            play = game.add_cards_to_play(play_index, player, ids)
            game._say("%s adds %s to the attack (Kinfolk Flute): strength %d." % (
                name, " + ".join(game.cards[c].label() for c in ids), play.value))
        else:
            game._event("flute_pass", player=player)
            game._say("%s adds nothing to the attack." % name)
        play = game.plays[play_index]
        nxt, rest = self._flute_next(game, d.get("queue", []), int(d["strength"]), play.value)
        if nxt is None:
            game.resolve_pending_attack()
            return
        d["player"] = nxt
        d["queue"] = rest
        game._event("decide", **d)
        game._say("Kinfolk Flute: %s may add %ss to %s's attack." % (
            game.players[nxt].name, d["strength"], game.players[play.player].name))

    # ------------------------------------------------------------------ corruption
    def on_cards_played(self, game, cards: Sequence[Card]) -> None:
        for c in cards:
            if c.has("corrupted"):
                self._corrupted_banish(game, c)
            if c.has("restored") and game.banished:
                back = game.banished.pop()
                game.tavern.append(back)
                game._event("restore", card=c.id, returned=back)
                game._say("%s (restored) returns %s under the reserve deck." % (c.label(), game.cards[back].label()))

    def _corrupted_banish(self, game, card: Card) -> None:
        relics = game.extra.get("relics", [])
        if "evergreen_corrupted" in relics and game.discard:
            lost = game.discard.pop(0)
            src = "discard pile"
        elif game.tavern:
            lost = game.tavern.pop(0)
            src = "reserve deck"
        else:
            return
        game.banished.append(lost)
        game._event("corrupt_banish", card=card.id, banished=lost)
        game._say("%s is corrupted: %s banished from the %s." % (card.label(), game.cards[lost].label(), src))

    # ------------------------------------------------------------------ cleanup
    def order_for_discard(self, game, cards: List[Card]) -> List[Card]:
        if game.config.extra.get("discard_low_to_high"):
            # last inserted ends on top: insert highest first so the lowest is on top
            return sorted(cards, key=lambda c: -c.value)
        return cards


@register_rules
class Mission1Rules(LegacyRules):
    id = "legacy_m1"
    mission = 1


@register_rules
class Mission2Rules(LegacyRules):
    """Shadow and Mist: six two-class Hydras. Imperfect kills recycle the Hydra."""

    id = "legacy_m2"
    mission = 2

    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        if exact:
            return {"enemy_to": "banish", "played_to": "discard"}
        return {"enemy_to": "castle_bottom", "played_to": "discard"}
