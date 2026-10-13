"""Rule sets for Regicide Legacy missions (hooks on top of BaseRules)."""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..cards import BASIC_SUITS, SUIT_NAME, Card, jester_card
from ..rules import BaseRules, classify_combo, register_rules
from ..rules import HAND_SIZE, JESTERS_IN_DECK


class LegacyRules(BaseRules):
    """Mission 1 rules: base Regicide plus the Legacy-wide changes."""

    id = "legacy_m1"
    mission = 1

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

    def validate_combo(self, game, cards: Sequence[Card]) -> Tuple[str, Optional[str]]:
        kind, err = classify_combo(cards)
        if err:
            return kind, err
        for c in cards:
            if c.has("twofive") and kind == "set":
                pass
        return kind, err

    def play_value(self, game, cards: Sequence[Card]) -> int:
        total = 0
        for c in cards:
            if c.has("twofive"):
                total += 2
            else:
                total += c.value
        return total

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
        acts: List[Dict[str, Any]] = []
        if "flute" in game.extra.get("relics", []) and game.phase == "play":
            if game.extra.get("flute_turn") != game.turn:
                flute = game.extra.get("flute", [])
                rank = game.cards[flute[0]].rank if flute else None
                for cid in game.active_player.hand:
                    c = game.cards[cid]
                    if c.has("twofive"):
                        v = 2
                    else:
                        v = c.value
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
