"""Rule sets for Regicide Legacy missions (hooks on top of BaseRules)."""
from __future__ import annotations

import itertools
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..cards import BASIC_SUITS, CLASS_NAME, SUIT_NAME, Card, jester_card
from ..rules import BaseRules, classify_combo, register_rules
from ..rules import HAND_SIZE, JESTERS_IN_DECK


MYLA_ID = "MYLA7"   # Myla (7, Elf Pilgrim): missions 5 and 6 start her outside the party


class LegacyRules(BaseRules):
    """Mission 1 rules: base Regicide plus the Legacy-wide changes."""

    id = "legacy_m1"
    mission = 1
    # Resolution order from the printed player helper card (confirmed by the owner):
    # step 2 "cast spells": Mage, Druid, Cleric (H), Bard (D), Chanter;
    # step 3 "deal damage": Reaver, Warrior (C);
    # step 4a "suffer damage": Paladin (S), Guardian.
    power_order = ("M", "U", "H", "D", "T", "R", "C", "S", "G")
    # Rulebook p.19: the enemy goes where the mission says first, then the played cards
    # go on top of the discard pile (in mission 4 the order decides the next bonus).
    played_on_top = True

    # ------------------------------------------------------------------ setup
    def build_decks(self, game) -> None:
        extra = game.config.extra
        party = [Card.from_dict(d) for d in extra.get("party", [])]
        castle = [Card.from_dict(d) for d in extra.get("castle", [])]
        # Cards a mission starts outside the reserve: in the banished pile (mission 5's
        # Myla) or face up in the mission zone (mission 6's Myla, mission 8's puppy).
        banished = [Card.from_dict(d) for d in extra.get("banished_start", [])]
        zone = [Card.from_dict(d) for d in extra.get("zone_start", [])]
        reserve = list(party)
        jesters = game.config.deck_jesters + int(extra.get("extra_jesters", 0)) if game.n_players > 1 else 0
        for i in range(jesters):
            reserve.append(jester_card(i + 1))
        if game.n_players == 1:
            game.solo_jesters = 2 + int(extra.get("extra_jesters", 0))
        game.cards = {}
        for c in reserve + castle + banished + zone:
            if c.id in game.cards:
                raise ValueError("duplicate card id %s" % c.id)
            game.cards[c.id] = c
        game.rng.shuffle(reserve)
        game.tavern = [c.id for c in reserve]
        game.castle = [c.id for c in castle]
        game.banished = [c.id for c in banished]
        game.mission_zone = [c.id for c in zone]
        game.extra["relics"] = list(extra.get("relics", []))
        if "flute" in game.extra["relics"]:
            game.extra["flute"] = []
            game.extra["flute_turn"] = -1

    # ------------------------------------------------------------------ queries
    def immune(self, game, suit: str, cards: Sequence[Card] = ()) -> bool:
        if suit not in self.immune_suits(game):
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
        """A card's strength on its own: the 2/5 mercenary counts 2, a beast 0 (rulebook
        p.21: alone, in hand, in the discard pile or the mission zone a beast is 0)."""
        return 2 if card.has("twofive") else card.value

    def zone_strength(self, game) -> int:
        """Combined strength of the mission zone (missions 5 and 6)."""
        return sum(self.strength(game.cards[c]) for c in game.mission_zone)

    def validate_combo(self, game, cards: Sequence[Card]) -> Tuple[str, Optional[str]]:
        # Kinfolk (rulebook p.22): any number of cards of equal STRENGTH totalling at most
        # 10, so five 2s are legal and a 2/5 card pairs with a 2. No four-card cap.
        kind, err = classify_combo(cards, strength=self.strength, max_cards=None)
        if err:
            return kind, err
        # Solo Kinfolk Flute: "While forming a Kinfolk Attack you may play cards from here
        # as though they were from your hand" -- so only as part of a kinfolk attack.
        flute = game.extra.get("flute", [])
        if flute and kind != "set" and any(c.id in flute for c in cards):
            return kind, "cards on the Kinfolk Flute can only be played in a kinfolk attack"
        return kind, err

    def play_value(self, game, cards: Sequence[Card]) -> int:
        """Attack strength. Rulebook p.14 / p.21: a beast "with any one other card; the
        beast's strength equals that card's strength during this step" (so beast + 7 is a
        14, companion + beast a 2); a beast alone is 0. The card it copies is the one it
        was played with: the first non-beast card of the attack (cards a mage or a relic
        add later come after it)."""
        others = [c for c in cards if not c.has("beast")]
        beasts = len(cards) - len(others)
        total = sum(self.strength(c) for c in others)
        if beasts and others:
            total += beasts * self.strength(others[0])
        return total

    def extra_plays(self, game, hand: Sequence[Card]) -> List[List[str]]:
        """Beast attacks: a beast with any one other card (never a Jester). Ace + beast is
        already listed by the engine's companion loop."""
        out: List[List[str]] = []
        for b in hand:
            if not b.has("beast"):
                continue
            for other in hand:
                if other.id == b.id or other.is_jester or other.is_ace:
                    continue
                if other.has("beast") and other.id < b.id:
                    continue  # count beast + beast once
                out.append([b.id, other.id])
        return out

    def playable_ids(self, game) -> List[str]:
        ids = list(game.active_player.hand)
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
        """Kinfolk Flute, solo side (card text, confirmed): "Once per turn at any time you
        may put a 2, 3, 4 or 5 from hand here as long as there are no other cards of a
        different strength already here. While forming a Kinfolk Attack you may play cards
        from here as though they were from your hand." Storing is offered during the play
        step and the suffer step (any time in the turn); ``validate_combo`` keeps flute
        cards out of non-kinfolk attacks. The multiplayer side is not a special action but
        a decision: see ``after_attack_formed`` below."""
        acts: List[Dict[str, Any]] = []
        if ("flute" in game.extra.get("relics", []) and game.phase in ("play", "suffer")
                and game.config.players == 1 and not game.is_over):
            if game.extra.get("flute_turn") != game.turn:
                flute = game.extra.get("flute", [])
                here = self.strength(game.cards[flute[0]]) if flute else None
                for cid in game.active_player.hand:
                    c = game.cards[cid]
                    v = self.strength(c)
                    if 2 <= v <= 5 and c.is_number and (here is None or v == here) and not c.name:
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
            if game.phase == "play":
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
        # The Scarlet Whistle wants a solitary companion or beast, which is never a kinfolk
        # attack, so the two relics never compete for the same attack.
        whistle = self._whistle_after_attack(game, play)
        if whistle is not None:
            return whistle
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

    # ------------------------------------------------------------------ decisions
    # One pair of methods per decision kind: ``_actions_<kind>`` lists the legal actions,
    # ``_decide_<kind>`` applies one and advances the decision or resumes the game.
    def decision_actions(self, game) -> List[Dict[str, Any]]:
        d = game.decision
        if not d:
            return []
        fn = getattr(self, "_actions_" + str(d.get("kind")), None)
        if fn is None:
            return []
        return fn(game, d)

    def decide(self, game, action: Dict[str, Any]) -> None:
        d = game.decision
        fn = getattr(self, "_decide_" + str((d or {}).get("kind")), None) if d else None
        if fn is None:
            raise NotImplementedError(action)
        fn(game, d, action)

    def forecast_action(self, game) -> Optional[Dict[str, Any]]:
        d = game.decision
        if d and d.get("kind") == "mage_peek":
            # Forecasts assume the mage adds nothing, whether or not a pick is possible.
            return {"type": "mage_skip", "player": int(d["player"]), "skip": True, "forecast": True}
        if d and d.get("kind") == "reaver_count":
            # Revealing nothing is not allowed, and a forecast must not look at the reserve:
            # it assumes a reveal that adds 0, then the doubling.
            return {"type": "reaver_count", "player": int(d["player"]), "count": 0, "forecast": True}
        return super().forecast_action(game)

    # --- mission zone rescue (missions 3 and 6) -----------------------------------
    def _actions_zone_rescue(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        options = [str(c) for c in d.get("options", game.mission_zone) if str(c) in game.mission_zone]
        return [{"type": "zone_rescue", "player": int(d["player"]), "card": cid,
                 "label": "Rescue %s to the discard pile" % game.cards[cid].label()}
                for cid in options]

    def _decide_zone_rescue(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        # Exact kill with a mission zone: one zone card goes to the discard pile instead
        # of being banished with the rest (missions 3 onward).
        cid = str(action["card"])
        game.mission_zone.remove(cid)
        game.discard.insert(0, cid)
        game._event("zone_rescue", card=cid, player=int(d["player"]))
        game._say("%s rescues %s from the mission zone to the discard pile." % (
            game.players[int(d["player"])].name, game.cards[cid].label()))
        self._after_zone_rescue(game, d)

    def _after_zone_rescue(self, game, d: Dict[str, Any]) -> None:
        game.resume_defeat()

    # --- mage ------------------------------------------------------------------------
    def _actions_mage_peek(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        # The pick is mandatory: "nothing to add" exists only when no revealed card may join.
        player = int(d["player"])
        eligible = [str(c) for c in d.get("eligible", [])]
        if eligible:
            return [{"type": "mage_pick", "player": player, "card": cid,
                     "label": "Add %s to the attack" % game.cards[cid].label()} for cid in eligible]
        return [{"type": "mage_skip", "player": player, "skip": True, "label": "Nothing to add"}]

    def _decide_mage_peek(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        self._mage_decide(game, d, action)

    def _actions_emblem_keep(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "emblem_keep", "player": player, "card": str(cid),
                 "label": "Keep %s on top of the reserve" % game.cards[str(cid)].label()}
                for cid in d.get("revealed", [])]
        acts.append({"type": "emblem_skip", "player": player, "skip": True, "label": "Discard them all"})
        return acts

    def _decide_emblem_keep(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        self._emblem_keep_decide(game, d, action)

    def _actions_emblem_place(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "emblem_place", "player": player, "card": cid,
                 "label": "Place %s on top of the reserve" % game.cards[cid].label()}
                for cid in game.players[player].hand]
        acts.append({"type": "emblem_pass", "player": player, "skip": True, "label": "Pass"})
        return acts

    def _decide_emblem_place(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        self._emblem_place_decide(game, d, action)

    # --- Kinfolk Flute, 2+ players -----------------------------------------------------
    def _actions_flute_add(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
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

    def _decide_flute_add(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
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

    # ------------------------------------------------------------------ Scarlet Whistle
    # Card text (confirmed). Solo side: "When you form an attack with a solitary animal
    # companion or beast you may take the top card of the discard pile and add it to the
    # attack." Two or more players: "After you form an attack with a solitary Animal
    # Companion or Beast, one other player may add any card from their hand to the attack
    # (except a Jester). This must be done before proceeding to Step 2." The other players
    # are asked clockwise from the attacker's left until one adds a card or all pass;
    # players holding nothing but Jesters are skipped. The added card joins the attack
    # like a Kinfolk Flute addition: strength and classes are recomputed over the whole
    # attack (a beast then copies the newcomer's strength), a corrupted newcomer banishes
    # the top reserve card, and everything is cleaned up together.
    def _whistle(self, game) -> bool:
        return "whistle" in game.extra.get("relics", [])

    @staticmethod
    def _solitary_companion(game, play) -> bool:
        if len(play.card_ids) != 1:
            return False
        c = game.cards[play.card_ids[0]]
        return c.is_ace or c.has("beast")

    def _whistle_candidates(self, game, player: int) -> List[str]:
        return [cid for cid in game.players[player].hand if not game.cards[cid].is_jester]

    def _whistle_next(self, game, queue: Sequence[int]) -> Tuple[Optional[int], List[int]]:
        rest = list(queue)
        while rest:
            p = rest.pop(0)
            if self._whistle_candidates(game, p):
                return p, rest
        return None, []

    def _whistle_after_attack(self, game, play) -> Optional[Dict[str, Any]]:
        if not self._whistle(game) or not self._solitary_companion(game, play):
            return None
        attacker = play.player
        if game.config.players == 1:
            if not game.discard:
                return None
            top = game.discard[0]
            game._say("Scarlet Whistle: %s may add %s, the top card of the discard pile, to the attack." % (
                game.players[attacker].name, game.cards[top].label()))
            return {"kind": "whistle_take", "player": attacker, "card": top}
        queue = [(attacker + k) % game.n_players for k in range(1, game.n_players)]
        player, rest = self._whistle_next(game, queue)
        if player is None:
            return None
        game._say("Scarlet Whistle: %s may add a card to %s's attack." % (
            game.players[player].name, game.players[attacker].name))
        return {"kind": "whistle_add", "player": player, "queue": rest}

    def _actions_whistle_take(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts: List[Dict[str, Any]] = []
        if game.discard and str(d.get("card")) == game.discard[0]:
            top = game.discard[0]
            acts.append({"type": "whistle_take", "player": player, "card": top,
                         "label": "Add %s from the discard pile" % game.cards[top].label()})
        acts.append({"type": "whistle_skip", "player": player, "skip": True, "label": "Skip"})
        return acts

    def _decide_whistle_take(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        if action["type"] == "whistle_take":
            cid = game.discard.pop(0)
            play = game._join_play(int(d["play_index"]), player, [cid], "whistle")
            game._event("whistle_take", player=player, card=cid, value=play.value)
            game._say("%s adds %s from the discard pile to the attack (Scarlet Whistle): strength %d." % (
                game.players[player].name, game.cards[cid].label(), play.value))
        else:
            game._event("whistle_skip", player=player)
            game._say("%s leaves the discard pile alone." % game.players[player].name)
        game.resolve_pending_attack()

    def _actions_whistle_add(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "whistle_add", "player": player, "card": cid,
                 "label": "Add %s to the attack" % game.cards[cid].label()}
                for cid in self._whistle_candidates(game, player)]
        acts.append({"type": "whistle_pass", "player": player, "skip": True, "label": "Pass"})
        return acts

    def _decide_whistle_add(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        play_index = int(d["play_index"])
        name = game.players[player].name
        if action["type"] == "whistle_add":
            cid = str(action["card"])
            play = game.add_cards_to_play(play_index, player, [cid])
            game._say("%s adds %s to the attack (Scarlet Whistle): strength %d." % (
                name, game.cards[cid].label(), play.value))
            game.resolve_pending_attack()   # one other player adds: the others are not asked
            return
        game._event("whistle_pass", player=player)
        game._say("%s adds nothing to the attack." % name)
        nxt, rest = self._whistle_next(game, d.get("queue", []))
        if nxt is None:
            game.resolve_pending_attack()
            return
        d["player"] = nxt
        d["queue"] = rest
        game._event("decide", **d)
        game._say("Scarlet Whistle: %s may add a card to %s's attack." % (
            game.players[nxt].name, game.players[game.plays[play_index].player].name))

    # ------------------------------------------------------------------ mages
    # Rulebook p.16 (confirmed): "secretly look at cards from the top of the reserve deck
    # equal to the attack strength; discard any Jesters or corrupted cards among them;
    # choose one of the rest and add it to the attack (tucked underneath); put the others
    # in the discard pile in any order. If the chosen card is a mage, repeat using that
    # mage's own strength." The chosen cards' classes resolve with the new attack strength
    # (p.23: an ace with a 9 of mages adding a 6 of bards draws 16 and deals 32) and the
    # whole attack is banished at clean-up (``Play.mage``, set by the engine). A short
    # reserve shows what there is; with nothing eligible everything revealed is discarded.
    # The Azure Emblem (see below) hooks in before the first peek (2+ players) and after
    # each pick (solo).
    def resolve_power(self, game, suit: str, value: int, cards: Sequence[Card],
                      damage: Optional[int] = None) -> Any:
        if suit == "M":
            if value <= 0:
                return {"peek": 0}
            if self._emblem(game) and game.config.players >= 2:
                placing = self._emblem_place_start(game, value)
                if placing is not None:
                    return {"decision": placing}
            return {"decision": self._mage_peek(game, value)}
        if suit == "R":
            return self._reaver_start(game, value if damage is None else int(damage))
        if suit == "G":
            # Rulebook p.18: "players suffer no damage this turn, from enemy attacks or
            # mission effects; it also applies in step 4b". A turn flag the engine clears
            # when the next turn starts; ``_enter_suffer`` and mission 6's team damage read it.
            game.extra["guardian"] = True
            game._say("Guardian: the players suffer no damage this turn.")
            return {"guardian": True}
        return super().resolve_power(game, suit, value, cards, damage)

    # ------------------------------------------------------------------ reavers
    # Rulebook p.17 (confirmed): "choose any number (at least one), reveal that many cards
    # from the top of the reserve, choose one and add its strength to the attack damage
    # (no class powers), banish all revealed cards in any order, then double the attack
    # damage." Two decisions of the attacker: how many to reveal, then which card counts.
    # The revealed cards are banished with the chosen one last; a 2/5 adds 5 (the player
    # chooses its value when it matters), a Jester or a beast adds 0. With an empty
    # reserve there is nothing to reveal and the reaver only doubles.
    def reaver_value(self, card: Card) -> int:
        return 5 if card.has("twofive") else self.strength(card)

    def _reaver_start(self, game, damage: int) -> Any:
        if not game.tavern:
            game._say("Reaver: the reserve deck is empty; the damage is doubled to %d." % (damage * 2))
            return {"damage": damage * 2, "revealed": [], "added": 0, "doubled": True}
        game._say("Reaver: %s chooses how many reserve cards to reveal (1 to %d)." % (
            game.players[game.active].name, len(game.tavern)))
        return {"decision": {"kind": "reaver_count", "player": game.active, "max": len(game.tavern)}}

    def _actions_reaver_count(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        return [{"type": "reaver_count", "player": player, "count": n, "label": "Reveal %d" % n}
                for n in range(1, len(game.tavern) + 1)]

    def _decide_reaver_count(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        if action.get("forecast"):
            # Forecast only (a copy): no reveal, nothing added, the doubling applied.
            play = game.plays[int(d["play_index"])]
            d["damage"] = int(d["damage"]) * 2
            game._event("power", suit="R", value=play.value, added=0, doubled=True, forecast=True)
            game.resolve_pending_attack()
            return
        n = int(action["count"])
        if not 1 <= n <= len(game.tavern):
            from ..engine import IllegalAction
            raise IllegalAction("Reveal between 1 and %d cards." % len(game.tavern))
        revealed = game.tavern[:n]
        del game.tavern[:n]
        d["kind"] = "reaver_pick"
        d["revealed"] = list(revealed)
        d.pop("max", None)
        game._event("reaver_reveal", player=player, count=n, revealed=list(revealed))
        game._say("Reaver: %s reveals %s from the reserve deck." % (
            game.players[player].name, " + ".join(game.cards[c].label() for c in revealed)))
        game._event("decide", **d)

    def _actions_reaver_pick(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        return [{"type": "reaver_pick", "player": player, "card": str(cid),
                 "label": "Add %s's strength (+%d)" % (game.cards[str(cid)].label(), self.reaver_value(game.cards[str(cid)]))}
                for cid in d.get("revealed", [])]

    def _decide_reaver_pick(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        cid = str(action["card"])
        revealed = [str(c) for c in d.get("revealed", [])]
        if cid not in revealed:
            from ..engine import IllegalAction
            raise IllegalAction("Card %s was not revealed." % cid)
        added = self.reaver_value(game.cards[cid])
        order = [c for c in revealed if c != cid] + [cid]
        game.banished.extend(order)
        d["revealed"] = []
        before = int(d["damage"])
        d["damage"] = (before + added) * 2
        play = game.plays[int(d["play_index"])]
        game._event("reaver_pick", player=player, card=cid, added=added, banished=order, damage=d["damage"])
        game._event("power", suit="R", value=play.value, added=added, doubled=True)
        game._say("Reaver: %s adds %s's strength (+%d) and doubles the damage: %d + %d = %d, doubled to %d. %s banished." % (
            game.players[player].name, game.cards[cid].label(), added, before, added, before + added, d["damage"],
            " + ".join(game.cards[c].label() for c in order)))
        game.resolve_pending_attack()

    @staticmethod
    def mage_eligible(card: Card) -> bool:
        """May a revealed card join the attack? Jesters and corrupted cards never do."""
        return not card.is_jester and not card.has("corrupted")

    def _mage_peek(self, game, strength: int) -> Dict[str, Any]:
        """Take the top ``strength`` reserve cards (fewer if the reserve is short) out of
        the reserve into a mage_peek decision; returns the decision's own fields."""
        n = min(int(strength), len(game.tavern))
        revealed = game.tavern[:n]
        del game.tavern[:n]
        eligible = [cid for cid in revealed if self.mage_eligible(game.cards[cid])]
        game._event("mage_peek", player=game.active, strength=int(strength), count=n,
                    revealed=list(revealed), eligible=list(eligible))
        if n == 0:
            game._say("Mage: the reserve deck is empty, there is nothing to look at.")
        else:
            game._say("Mage: %s looks at the top %d card%s of the reserve deck." % (
                game.players[game.active].name, n, "" if n == 1 else "s"))
        return {"kind": "mage_peek", "player": game.active, "strength": int(strength),
                "revealed": list(revealed), "eligible": eligible}

    def _mage_discard_rest(self, game, d: Dict[str, Any]) -> List[str]:
        """The revealed cards not chosen go to the discard pile (Jesters and corrupted ones too)."""
        rest = [str(c) for c in d.get("revealed", [])]
        game._discard_cards([game.cards[c] for c in rest])
        d["revealed"] = []
        return rest

    def _mage_decide(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        name = game.players[player].name
        if action["type"] == "mage_pick":
            cid = str(action["card"])
            play = game.mage_add_to_play(cid)
            card = game.cards[cid]
            if self._emblem(game) and game.config.players == 1 and d.get("revealed"):
                # Azure Emblem, solo side: the rest is not discarded yet, one of those cards
                # may go back on top of the reserve first (``_emblem_keep_decide``).
                game._event("mage_pick", player=player, card=cid, value=play.value, discarded=[])
                game._say("%s adds %s to the attack (Mage): strength %d." % (name, card.label(), play.value))
                d["kind"] = "emblem_keep"
                d["picked"] = cid
                d.pop("eligible", None)
                game._event("decide", **d)
                game._say("Azure Emblem: %s may put one of the other revealed cards back on top of the reserve deck." % name)
                return
            rest = self._mage_discard_rest(game, d)
            game._event("mage_pick", player=player, card=cid, value=play.value, discarded=rest)
            tail = " %s to the discard pile." % " + ".join(game.cards[c].label() for c in rest) if rest else ""
            game._say("%s adds %s to the attack (Mage): strength %d.%s" % (name, card.label(), play.value, tail))
            self._mage_continue(game, d, card)
            return
        rest = self._mage_discard_rest(game, d)
        game._event("mage_skip", player=player, discarded=rest)
        if rest:
            game._say("Mage: nothing may join the attack; %s to the discard pile." % (
                " + ".join(game.cards[c].label() for c in rest)))
        else:
            game._say("Mage: nothing to add.")
        game.resolve_pending_attack()

    def _mage_continue(self, game, d: Dict[str, Any], card: Card) -> None:
        """After a pick (and the Emblem's keep, if any): a chosen mage looks again with its
        own strength, unless its ability is blocked by immunity; otherwise the attack goes
        on resolving with its new strength."""
        d.pop("picked", None)
        if "M" in card.suits and self.strength(card) > 0 and not game.immune("M", [card]):
            game._say("%s is a mage too: look again with its own strength, %d." % (card.label(), self.strength(card)))
            d.update(self._mage_peek(game, self.strength(card)))
            game._event("decide", **d)
            return
        game.resolve_pending_attack()

    # ------------------------------------------------------------------ Azure Emblem
    # Card text (confirmed). Solo side: "When resolving a mage class ability, after
    # selecting a card to be added to the attack, you may put one of the other cards you
    # looked at on top of the reserve deck before discarding the rest." Offered after every
    # pick of a chain (the once-per-attack limit is printed on the multiplayer side only),
    # over every other revealed card, Jesters and corrupted ones included: they were looked
    # at too, and the wording does not exclude them.
    # Two or more players: "When you form an attack with a mage, before peeking at any
    # cards, each other player may place one card from their hand on the top of the reserve
    # deck. This power only happens once per attack: if you use a mage to add an additional
    # mage to an attack, this relic power does not happen another time." Players are asked
    # clockwise from the attacker's left, players with an empty hand are skipped, the
    # placed cards stack with the last placed on top, then the mage peeks. A chained mage
    # peeks without it, and nothing happens when immunity blocks the mage.
    def _emblem(self, game) -> bool:
        return "emblem" in game.extra.get("relics", [])

    def _emblem_next(self, game, queue: Sequence[int]) -> Tuple[Optional[int], List[int]]:
        """First queued player holding a card, and the players after them."""
        rest = list(queue)
        while rest:
            p = rest.pop(0)
            if game.players[p].hand:
                return p, rest
        return None, []

    def _emblem_place_start(self, game, strength: int) -> Optional[Dict[str, Any]]:
        attacker = game.active
        queue = [(attacker + k) % game.n_players for k in range(1, game.n_players)]
        player, rest = self._emblem_next(game, queue)
        if player is None:
            return None
        game._say("Azure Emblem: %s may place a card on top of the reserve deck before %s's mage looks." % (
            game.players[player].name, game.players[attacker].name))
        return {"kind": "emblem_place", "player": player, "queue": rest, "strength": int(strength)}

    def _emblem_place_decide(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        name = game.players[player].name
        if action["type"] == "emblem_place":
            cid = str(action["card"])
            hand = game.players[player].hand
            if cid not in hand:
                from ..engine import IllegalAction
                raise IllegalAction("Card %s is not in hand." % cid)
            hand.remove(cid)
            game.tavern.insert(0, cid)
            game._event("emblem_place", player=player, card=cid)
            game._say("%s places a card from hand on top of the reserve deck (Azure Emblem)." % name)
        else:
            game._event("emblem_pass", player=player)
            game._say("%s places nothing on the reserve deck." % name)
        nxt, rest = self._emblem_next(game, d.get("queue", []))
        if nxt is not None:
            d["player"] = nxt
            d["queue"] = rest
            game._event("decide", **d)
            game._say("Azure Emblem: %s may place a card on top of the reserve deck." % game.players[nxt].name)
            return
        d.pop("queue", None)
        d.update(self._mage_peek(game, int(d["strength"])))
        game._event("decide", **d)

    def _emblem_keep_decide(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        name = game.players[player].name
        if action["type"] == "emblem_keep":
            cid = str(action["card"])
            revealed = [str(c) for c in d.get("revealed", [])]
            if cid not in revealed:
                from ..engine import IllegalAction
                raise IllegalAction("Card %s was not revealed." % cid)
            revealed.remove(cid)
            d["revealed"] = revealed
            game.tavern.insert(0, cid)
            rest = self._mage_discard_rest(game, d)
            game._event("emblem_keep", player=player, card=cid, discarded=rest)
            tail = " %s to the discard pile." % " + ".join(game.cards[c].label() for c in rest) if rest else ""
            game._say("Azure Emblem: %s puts %s back on top of the reserve deck.%s" % (name, game.cards[cid].label(), tail))
        else:
            rest = self._mage_discard_rest(game, d)
            game._event("emblem_skip", player=player, discarded=rest)
            game._say("Azure Emblem: nothing kept; %s to the discard pile." % " + ".join(game.cards[c].label() for c in rest))
        self._mage_continue(game, d, game.cards[str(d["picked"])])

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
            cards = sorted(cards, key=lambda c: -c.value)
        top = game.extra.get("cleanup_top")
        if top is not None and any(c.id == top for c in cards):
            # Rulebook p.19 step 2: the played cards go on the discard pile "in any order
            # you wish"; the player chose which one ends on top (mission 4's ``cleanup_top``).
            game.extra.pop("cleanup_top", None)
            cards = [c for c in cards if c.id != top] + [c for c in cards if c.id == top]
        return cards


@register_rules
class Mission1Rules(LegacyRules):
    id = "legacy_m1"
    mission = 1


@register_rules
class Mission3Rules(LegacyRules):
    """Lessons in Flames (confirmed from the cards). End of turn: the top card of the
    reserve deck goes face up into the mission zone if able. Enemies are immune to the
    classes of every card in the mission zone. Enemy defeated: banish the enemy along with
    all cards in the mission zone; on exact damage put one card from the mission zone
    into the discard pile first. End-of-turn effects are skipped when an enemy is defeated
    (rulebook p.19)."""

    id = "legacy_m3"
    mission = 3
    uses_mission_zone = True

    def zone_suits(self, game) -> Tuple[str, ...]:
        suits: List[str] = []
        for cid in game.mission_zone:
            for s in game.cards[cid].suits:
                if s not in suits:
                    suits.append(s)
        return tuple(suits)

    def immune_suits(self, game) -> Tuple[str, ...]:
        base = list(super().immune_suits(game))
        if game.enemy is None:
            return tuple(base)
        for s in self.zone_suits(game):
            if s not in base:
                base.append(s)
        return tuple(base)

    def on_turn_end(self, game) -> None:
        if game.is_over or not game.tavern:
            return
        before = self.immune_suits(game)
        cid = game.tavern.pop(0)
        game.mission_zone.append(cid)
        game._event("zone_add", card=cid, zone=list(game.mission_zone))
        card = game.cards[cid]
        game._say("End of turn: %s goes into the mission zone." % card.label())
        gained = [s for s in self.immune_suits(game) if s not in before]
        if gained and game.enemy is not None:
            game._say("%s is now immune to %s." % (
                game.enemy.name, " / ".join(CLASS_NAME.get(s, s) + "s" for s in gained)))

    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        return {"enemy_to": "banish", "played_to": "discard", "zone_to": "banish"}

    def before_defeat(self, game, exact: bool) -> Optional[Dict[str, Any]]:
        if exact and game.mission_zone:
            return {"kind": "zone_rescue", "player": game.active, "options": list(game.mission_zone)}
        return None


@register_rules
class Mission2Rules(LegacyRules):
    """Shadow and Mist: six two-class Hydras. Imperfect kills recycle the Hydra."""

    id = "legacy_m2"
    mission = 2

    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        if exact:
            return {"enemy_to": "banish", "played_to": "discard"}
        return {"enemy_to": "castle_bottom", "played_to": "discard"}


@register_rules
class Mission4Rules(LegacyRules):
    """Fusion of Darkness (confirmed from the cards). Each enemy has additional strength
    equal to the strength of the top card of the discard pile (a Jester 0, a 2/5 2, a
    defeated experiment its printed strength); it changes whenever the pile changes before
    damage is suffered (a cleric's shuffle, a corrupted banish from the pile) and is
    frozen while suffering. Enemy defeated: into the discard pile, or on top of the
    reserve deck on exact damage; then the played cards go on top of the discard pile in
    the order the player chooses (``cleanup_top``: which card ends on top). The twelve
    experiments are in corrupted sleeves, so one drawn into a hand plays as a corrupted
    card (``_lab_castle`` flags them)."""

    id = "legacy_m4"
    mission = 4

    def attack_bonus(self, game) -> int:
        if not game.discard:
            return 0
        return self.strength(game.cards[game.discard[0]])

    def _cleanup_options(self, game) -> List[str]:
        """The played cards that will go to the discard pile: not a mage attack's cards
        (banished) and not a solo Jester (set aside)."""
        solo = game.n_players == 1 and self.solo_jester_mode(game) == "attack"
        return [c for p in game.plays if not p.mage for c in p.card_ids
                if not (solo and game.cards[c].is_jester)]

    def before_defeat(self, game, exact: bool) -> Optional[Dict[str, Any]]:
        options = self._cleanup_options(game)
        if len(options) >= 2:
            return {"kind": "cleanup_top", "player": game.active, "options": options}
        return None

    def _actions_cleanup_top(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"type": "cleanup_top", "player": int(d["player"]), "card": str(cid),
                 "label": "Put %s on top of the discard pile" % game.cards[str(cid)].label()}
                for cid in d.get("options", [])]

    def _decide_cleanup_top(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        cid = str(action["card"])
        game.extra["cleanup_top"] = cid
        game._event("cleanup_top", player=int(d["player"]), card=cid)
        game._say("%s puts %s on top of the discard pile." % (game.players[int(d["player"])].name, game.cards[cid].label()))
        game.resume_defeat()


@register_rules
class Mission5Rules(LegacyRules):
    """High and Mighty (confirmed from the cards). Myla starts in the banished pile. End of
    turn: the top card of the banished pile goes face up into the mission zone. Each enemy
    has additional strength equal to the combined strength of the zone. Enemy defeated: the
    enemy and all zone cards are shuffled into the banished pile; on exact damage the next
    enemy takes damage equal to the defeated enemy's strength (the strength shown as it
    fell: printed, plus the zone, less paladin reductions), chaining if that kills it. A
    mage attack's cards are banished in play order (the card lets the player choose)."""

    id = "legacy_m5"
    mission = 5
    uses_mission_zone = True

    def attack_bonus(self, game) -> int:
        return self.zone_strength(game)

    def on_turn_end(self, game) -> None:
        if game.is_over or not game.banished:
            return
        cid = game.banished.pop()
        game.mission_zone.append(cid)
        game._event("zone_add", card=cid, zone=list(game.mission_zone), source="banished")
        game._say("End of turn: %s leaves the banished pile for the mission zone (enemy strength +%d)." % (
            game.cards[cid].label(), self.zone_strength(game)))

    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        plan = {"enemy_to": "banish_shuffle", "played_to": "discard", "zone_to": "banish_shuffle"}
        if exact:
            plan["carry_damage"] = game.enemy_attack
        return plan


@register_rules
class Mission6Rules(LegacyRules):
    """Shards of Memory, second edition (confirmed from the cards). Myla (7) starts face up
    in the mission zone. Enemy defeated: banish the enemy; the current player moves one
    card in play (any playmat) to the mission zone; on exact damage one zone card except
    Myla goes to the discard pile; then Myla deals team damage equal to the zone's
    combined strength, discarded one card at a time by any player in any order; if it
    cannot be satisfied the mission is lost. A Guardian in the killing attack prevents the
    team damage. A mage moved to the zone leaves the rest of its attack to be banished."""

    id = "legacy_m6"
    mission = 6
    uses_mission_zone = True

    def _in_play(self, game) -> List[str]:
        solo = game.n_players == 1 and self.solo_jester_mode(game) == "attack"
        return [c for p in game.plays for c in p.card_ids if not (solo and game.cards[c].is_jester)]

    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        return {"enemy_to": "banish", "played_to": "discard"}   # the zone stays

    def before_defeat(self, game, exact: bool) -> Optional[Dict[str, Any]]:
        options = self._in_play(game)
        if options:
            return {"kind": "zone_move", "player": game.active, "options": options}
        return None

    def _actions_zone_move(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"type": "zone_move", "player": int(d["player"]), "card": str(cid),
                 "label": "Move %s to the mission zone" % game.cards[str(cid)].label()}
                for cid in d.get("options", [])]

    def _decide_zone_move(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        cid = str(action["card"])
        for play in game.plays:
            if cid in play.card_ids:
                play.card_ids.remove(cid)
                break
        else:
            from ..engine import IllegalAction
            raise IllegalAction("%s is not in play." % cid)
        game.mission_zone.append(cid)
        game._event("zone_move", player=int(d["player"]), card=cid, zone=list(game.mission_zone))
        game._say("%s moves %s to the mission zone." % (game.players[int(d["player"])].name, game.cards[cid].label()))
        d.pop("options", None)
        rescue = [c for c in game.mission_zone if c != MYLA_ID]
        if d.get("exact") and rescue:
            d["kind"] = "zone_rescue"
            d["options"] = rescue
            game._event("decide", **d)
            game._say("Exact kill: %s may move one mission zone card except Myla to the discard pile." % (
                game.players[int(d["player"])].name))
            return
        self._team_damage(game, d)

    def _after_zone_rescue(self, game, d: Dict[str, Any]) -> None:
        d.pop("options", None)
        self._team_damage(game, d)

    def _team_damage(self, game, d: Dict[str, Any]) -> None:
        damage = self.zone_strength(game)
        if game.extra.get("guardian"):
            game._event("team_damage_prevented", damage=damage)
            game._say("Guardian: Myla's %d team damage is prevented." % damage)
            game.resume_defeat()
            return
        if damage <= 0:
            game.resume_defeat()
            return
        total = sum(game.hand_defence_value(i) for i in range(game.n_players))
        game._event("team_damage", damage=damage, available=total)
        game._say("Myla deals %d team damage: the players discard cards one at a time until %d strength is discarded." % (
            damage, damage))
        if total < damage:
            game.decision = None
            game._lose("The team cannot suffer Myla's %d damage (%d in hand)." % (damage, total))
            return
        d["kind"] = "team_discard"
        d["damage"] = damage
        d["paid"] = 0
        game._event("decide", **d)

    def _actions_team_discard(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        acts: List[Dict[str, Any]] = []
        for i, p in enumerate(game.players):
            for cid in p.hand:
                acts.append({"type": "team_discard", "player": i, "card": cid,
                             "label": "%s discards %s" % (p.name, game.cards[cid].label())})
        return acts

    def _decide_team_discard(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        cid = str(action["card"])
        owner = None
        for i, p in enumerate(game.players):
            if cid in p.hand:
                owner = i
                break
        if owner is None:
            from ..engine import IllegalAction
            raise IllegalAction("Card %s is not in a hand." % cid)
        card = game.cards[cid]
        game.players[owner].hand.remove(cid)
        game._discard_cards([card])
        d["paid"] = int(d.get("paid", 0)) + card.defence_value
        remaining = max(0, int(d["damage"]) - int(d["paid"]))
        game._event("team_discard", player=owner, card=cid, paid=int(d["paid"]), damage=int(d["damage"]),
                    remaining=remaining)
        game._say("%s discards %s for the team damage (%d of %d)." % (
            game.players[owner].name, card.label(), d["paid"], d["damage"]))
        if remaining <= 0:
            game._event("team_damage_done", damage=int(d["damage"]), paid=int(d["paid"]))
            game.resume_defeat()
            return
        game._event("decide", **d)
