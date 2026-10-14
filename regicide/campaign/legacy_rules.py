"""Rule sets for Regicide Legacy missions (hooks on top of BaseRules)."""
from __future__ import annotations

import itertools
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..cards import BASIC_SUITS, CLASS_NAME, SUIT_NAME, SUIT_SYMBOL, Card, jester_card
from ..rules import BaseRules, classify_combo, register_rules
from ..rules import HAND_SIZE, JESTERS_IN_DECK


MYLA_ID = "MYLA7"   # Myla (7, Elf Pilgrim): missions 5 and 6 start her outside the party
TWOFIVE_VALUES = (2, 5)   # the strengths a 2/5 mercenary may take in play (rulebook p.25)


class LegacyRules(BaseRules):
    """Mission 1 rules: base Regicide plus the Legacy-wide changes."""

    id = "legacy_m1"
    mission = 1
    legacy = True                 # UIs: Legacy names (classes, reserve deck) and rules
    uses_mission_zone = False     # UIs: show the mission zone strip from the start
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
        if not extra.get("capture"):
            # Mission 8: "shuffle the pilgrims into the reserve deck" (ordinary classless
            # cards there). Mission 9 shuffles them in itself, after dealing its piles.
            reserve.extend(Card.from_dict(d) for d in extra.get("pilgrims_in_reserve", []))
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
        if self.fixed_immunity(game, suit):
            return True
        for c in cards:
            if suit in c.suits and (c.has("corrupted") or c.has("restored") or c.has("ignores_immunity")):
                return False
        return True

    def fixed_immunity(self, game, suit: str) -> bool:
        """Mission 9's Myla (flag ``fixed_immunity``): "her immunity to bards and paladins
        can never be ignored (e.g. via corruption and jesters)"."""
        enemy = game.enemy
        if enemy is None or suit not in enemy.suits:
            return False
        card = game.cards.get(enemy.card_id)
        return card is not None and card.has("fixed_immunity")

    def unlocked_hand(self, game, player: int) -> List[str]:
        """The ids a player may give away from hand (not the locked ones, p. mission 7)."""
        return [cid for cid in game.players[player].hand if not self.hand_locked(game, game.cards[cid])]

    def extra_card_ids(self, game) -> List[str]:
        ids = list(game.extra.get("pilgrim_deck", []))
        ids.extend(game.extra.get("flute", []))           # the solo Kinfolk Flute's stored cards
        for pile in game.extra.get("captured", []):
            ids.extend(pile)
        ids.extend(game.extra.get("beast_deck", []))     # mission 11's face-down beast deck
        ids.extend(game.extra.get("beasts_out", []))     # and its face-up pile
        return ids

    def zone_suits(self, game) -> Tuple[str, ...]:
        """The classes of the cards in the mission zone, each once (missions 3 and 12 make
        the enemy immune to them). A beast grants no class (mission 11's note)."""
        suits: List[str] = []
        for cid in game.mission_zone:
            card = game.cards[cid]
            if card.has("beast"):
                continue
            for s in card.suits:
                if s not in suits:
                    suits.append(s)
        return tuple(suits)

    @staticmethod
    def pile_top(pile: Sequence[str], top_last: bool) -> Optional[str]:
        """The top card of a pile: the discard pile's top is index 0, the banished pile's
        top is its last card."""
        if not pile:
            return None
        return pile[-1] if top_last else pile[0]

    def top_card_strength(self, game, pile: Sequence[str], top_last: bool) -> int:
        """Strength the top card of a pile grants an enemy (missions 4 and 11, Evergreen
        banes 17 and 18): a beast or classless card still counts its strength (0 for a
        beast or a Jester)."""
        top = self.pile_top(pile, top_last)
        return self.strength(game.cards[top]) if top else 0

    def top_card_suits(self, game, pile: Sequence[str], top_last: bool) -> Tuple[str, ...]:
        """Classes the top card of a pile grants immunity to (mission 11, Evergreen banes
        19 and 20): none for a beast, a Jester or a classless card."""
        top = self.pile_top(pile, top_last)
        if top is None or game.cards[top].has("beast"):
            return ()
        return tuple(game.cards[top].suits)

    def jester_mode(self, game) -> str:
        return "claim"

    def solo_jester_mode(self, game) -> str:
        return "attack"

    def feign_death_allowed(self, game) -> bool:
        return len(game.active_player.hand) >= game.config.max_hand

    def sequential_discard(self, game) -> bool:
        """Rulebook p.18: damage is paid one card at a time, never past the damage."""
        return True

    def discard_top_feeds_enemy(self, game) -> bool:
        """Does the top card of the discard pile strengthen the enemy (missions 4, 10 and 11,
        Evergreen banes 10, 17 and 19)? Bots then put the weakest card on top."""
        return False

    def discard_top_matters(self, game) -> bool:
        """Does the top card of the discard pile count: towards the enemy
        (``discard_top_feeds_enemy``) or, solo, for the Scarlet Whistle, which takes it into
        an attack? The player then orders a mage's unchosen cards (``discard_order``); the
        clean-up is never asked (the order the cards entered play)."""
        return self.discard_top_feeds_enemy(game) or (self._whistle(game) and game.config.players == 1)

    def banished_top_matters(self, game) -> bool:
        """Missions 5, 11 and 12 (and some Evergreen setups) read the top of the banished
        pile: the player then orders a reaver's revealed cards (``reaver_order``); a mage
        attack's cards keep the order they entered play."""
        return False

    @staticmethod
    def strength(card: Card) -> int:
        """A card's strength on its own: the 2/5 mercenary counts 2, a beast 0 (rulebook
        p.21: alone, in hand, in the discard pile or the mission zone a beast is 0)."""
        return 2 if card.has("twofive") else card.value

    @staticmethod
    def _card_in_play(game, card_id: str) -> bool:
        return any(card_id in p.card_ids for p in game.plays)

    def _declared_value(self, game, card: Card) -> Optional[int]:
        """The strength a 2/5 in play was given when it entered the playmat (declared by
        its player or forced by its kinfolk set), or None."""
        if card.has("twofive") and self._card_in_play(game, card.id):
            declared = (game.extra.get("declared_value") or {}).get(card.id)
            if declared is not None:
                return int(declared)
        return None

    def _held_value(self, game, card: Card) -> Optional[int]:
        """The value a 2/5 keeps out of play (owner's rulings): one moved from play into the
        mission zone counts what it was declared as; one stored on the solo Kinfolk Flute
        counts the value declared when it was stored. Kept in ``extra["held_value"]`` only
        while the card is in the zone or on the flute (entries are dropped once it leaves)."""
        held = game.extra.get("held_value")
        if not held:
            return None
        here = set(game.mission_zone) | set(game.extra.get("flute", []))
        for cid in [c for c in held if c not in here]:
            held.pop(cid)
        if not held:
            game.extra.pop("held_value", None)
            return None
        v = held.get(card.id) if card.has("twofive") else None
        return None if v is None else int(v)

    def _hold_value(self, game, card_id: str, value: Optional[int]) -> None:
        if value is not None and game.cards[card_id].has("twofive"):
            game.extra.setdefault("held_value", {})[card_id] = int(value)

    def card_strength(self, game, card: Card) -> int:
        """A card's strength where it is: in play the value it was given there, in the
        mission zone or on the flute a 2/5's held value (``_held_value``), else ``strength``."""
        v = self._declared_value(game, card)
        if v is None:
            v = self._held_value(game, card)
        return self.strength(card) if v is None else v

    def zone_entered_from_play(self, game, card_ids: Sequence[str]) -> None:
        """A 2/5 moved from play into the mission zone keeps the value it was declared as."""
        for cid in card_ids:
            self._hold_value(game, cid, self._declared_value(game, game.cards[cid]))

    def in_play_strength(self, game, card: Card) -> int:
        """A card's strength while it is in play: a 2/5 keeps the value it was given when it
        entered the playmat (rulebook p.25: declared by its player, or the only value its
        kinfolk set allows), otherwise ``strength``."""
        declared = self._declared_value(game, card)
        return self.strength(card) if declared is None else declared

    def set_strengths(self, game, card: Card) -> Tuple[int, ...]:
        """A 2/5 may join a kinfolk set as a 2 or as a 5 (``Game.legal_plays``)."""
        if card.has("twofive"):
            held = self._held_value(game, card)       # on the flute: the value it was stored as
            return (held,) if held is not None else TWOFIVE_VALUES
        return (self.strength(card),)

    def kinfolk_values(self, game, cards: Sequence[Card]) -> List[int]:
        """The strengths a kinfolk set of ``cards`` may have (rulebook p.22 and p.25), lowest
        first: the cards' common strength, every 2/5 without a value yet taking 2 or 5 as
        needed, with the total within the kinfolk limit. 2/5 + 5 is a set of 5s, 2/5 + 2 a
        set of 2s, two 2/5s either (4 or 10), three 2/5s only 2s (6, under a limit of 10).
        Empty when no strength works. Aces, beasts and Jesters are the caller's business."""
        fixed = set()
        free = 0
        for c in cards:
            v = self._declared_value(game, c) if c.has("twofive") else self.strength(c)
            if v is None and c.has("twofive"):
                v = self._held_value(game, c)       # a 2/5 played from the flute
            if v is None:
                free += 1
            else:
                fixed.add(v)
        if len(fixed) > 1:
            return []
        candidates = sorted(fixed) if fixed else list(TWOFIVE_VALUES)
        if free:
            candidates = [v for v in candidates if v in TWOFIVE_VALUES]
        limit = self.kinfolk_limit(game)
        return [v for v in candidates if v * len(cards) <= limit]

    @staticmethod
    def _kinfolk_batch(cards: Sequence[Card]) -> bool:
        """Do these cards, entering play together, form a kinfolk set (not a single card,
        a companion or beast pair, or a Jester)?"""
        return len(cards) >= 2 and not any(c.is_ace or c.is_jester or c.has("beast") for c in cards)

    def _forced_value(self, game, cards: Sequence[Card]) -> Optional[int]:
        """The value the 2/5s without one must take in the kinfolk set ``cards`` (the
        attack's non-beast cards), or None: not a set, or a free choice still to declare."""
        if not self._kinfolk_batch(cards) or not any(c.has("twofive") for c in cards):
            return None
        values = self.kinfolk_values(game, cards)
        return values[0] if len(values) == 1 else None

    def card_suits(self, game, card: Card) -> Tuple[str, ...]:
        """A Wild Animal mercenary (flag ``choosable``, rulebook p.25) has the class its
        player declared when it entered the playmat, for as long as it is in play; anywhere
        else it is classless."""
        if card.has("choosable"):
            declared = (game.extra.get("declared") or {}).get(card.id)
            if declared and self._card_in_play(game, card.id):
                return (str(declared),)
            return ()
        return tuple(card.suits)

    def on_enemy_revealed(self, game) -> None:
        # the plays are cleared before the next enemy appears: the declarations are spent
        game.extra.pop("declared", None)
        game.extra.pop("declared_value", None)

    def zone_strength(self, game) -> int:
        """Combined strength of the mission zone (missions 5 and 6)."""
        return sum(self.card_strength(game, game.cards[c]) for c in game.mission_zone)

    def validate_combo(self, game, cards: Sequence[Card]) -> Tuple[str, Optional[str]]:
        # Kinfolk (rulebook p.22): any number of cards of equal STRENGTH totalling at most
        # 10 (``kinfolk_limit``), so five 2s are legal. No four-card cap. A 2/5 takes
        # whichever of 2 or 5 makes the set legal (p.25, ``kinfolk_values``): it pairs with
        # a 2 or with a 5, but 2/5 + 2 + 5 has no common strength and 2/5 + 5 + 5 is 15.
        as_value = None   # type: Optional[int]
        if any(c.has("twofive") for c in cards):
            values = self.kinfolk_values(game, cards)
            plain = set(self.strength(c) for c in cards if not c.has("twofive"))
            if values:
                as_value = values[0]
            elif len(plain) == 1 and plain <= set(TWOFIVE_VALUES):
                as_value = plain.pop()   # a common strength, but over the limit: say so
            # otherwise the 2/5 counts 2 and the set reports the mismatch

        def strength(c: Card) -> int:
            return as_value if as_value is not None and c.has("twofive") else self.strength(c)

        kind, err = classify_combo(cards, strength=strength, max_cards=None,
                                   max_total=self.kinfolk_limit(game))
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
        add later come after it). A 2/5 counts the value it was given when it entered play
        (p.25); before that, in a kinfolk set that allows only one value (2/5 + 5, three
        2/5s) it already counts that value, and otherwise 2 until its player declares."""
        others = [c for c in cards if not c.has("beast")]
        beasts = len(cards) - len(others)
        forced = self._forced_value(game, others)
        values = []
        for c in others:
            v = self._declared_value(game, c) if c.has("twofive") else None
            if v is None:
                v = forced if forced is not None and c.has("twofive") else self.strength(c)
            values.append(v)
        total = sum(values)
        if beasts and values:
            total += beasts * values[0]
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
        ids = self.unlocked_hand(game, game.active)
        ids.extend(game.extra.get("flute", []))
        return ids

    def remove_played(self, game, card_id: str) -> None:
        hand = game.active_player.hand
        if card_id in hand:
            hand.remove(card_id)
            return
        flute = game.extra.get("flute", [])
        if card_id in flute:
            held = self._held_value(game, game.cards[card_id])
            if held is not None:
                game.extra.setdefault("flute_carry", {})[card_id] = held
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
                here = self.card_strength(game, game.cards[flute[0]]) if flute else None
                suffering = game.phase == "suffer"
                defence = game.hand_defence_value() if suffering else 0
                # any 2 to 5 may go there, named characters (Oaken, Tolman, the 2/5s...)
                # included; mission 7's pilgrims are kept out by the hand lock alone
                for cid in self.unlocked_hand(game, game.active):
                    c = game.cards[cid]
                    if suffering and not self._payable_without(game, c, defence):
                        continue   # storing it would leave the damage unpayable: the mission would be lost
                    if c.has("twofive"):
                        # a 2/5 declares 2 or 5 as it goes on the flute (owner); the flute's
                        # strength decides when cards are already there
                        for v in TWOFIVE_VALUES:
                            if here is None or v == here:
                                acts.append({"type": "special", "name": "flute_store", "card": cid, "value": v,
                                             "label": "Store %s on the Kinfolk Flute as a %d" % (c.label(), v)})
                        continue
                    v = self.strength(c)
                    if not (2 <= v <= 5 and c.is_number and (here is None or v == here)):
                        continue
                    acts.append({"type": "special", "name": "flute_store", "card": cid,
                                 "label": "Store %s on the Kinfolk Flute" % c.label()})
        return acts

    def _payable_without(self, game, card: Card, defence: int) -> bool:
        """Could the active player still pay the pending damage without ``card`` in hand
        (by value, or by feigning death with the rest)?"""
        if defence - card.defence_value >= game.pending_damage:
            return True
        rest = [c for c in game.active_player.hand if c != card.id]
        return len(rest) >= game.config.max_hand and not any(self.hand_locked(game, game.cards[c]) for c in rest)

    def do_special(self, game, action: Dict[str, Any]) -> None:
        if action.get("name") == "flute_store":
            cid = action["card"]
            legal = [a for a in self.special_actions(game) if a.get("name") == "flute_store" and a["card"] == cid]
            if game.cards[cid].has("twofive"):
                if "value" in action:
                    legal = [a for a in legal if int(a["value"]) == int(action["value"])]
                elif len(legal) > 1:
                    from ..engine import IllegalAction
                    raise IllegalAction("Store the 2/5 on the flute as a 2 or as a 5.")
            if not legal:
                from ..engine import IllegalAction
                raise IllegalAction("That card cannot go on the flute now.")
            value = legal[0].get("value")
            game.active_player.hand.remove(cid)
            game.extra.setdefault("flute", []).append(cid)
            game.extra["flute_turn"] = game.turn
            self._hold_value(game, cid, value)
            game._event("flute_store", card=cid, value=value)
            game._say("%s stores %s on the Kinfolk Flute%s." % (game.active_player.name, game.cards[cid].label(),
                                                                "" if value is None else " as a %d" % int(value)))
            if game.phase == "play":
                game._check_can_act()
            else:
                game._check_can_suffer()
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
            strengths.add(self.in_play_strength(game, c))   # a 2/5 counts its value in play
        if len(strengths) != 1:
            return None
        s = strengths.pop()
        return s if s > 0 else None

    def _flute_candidates(self, game, player: int, strength: int, total: int) -> List[Card]:
        """Cards ``player`` could add: same strength (a 2/5 joins 2s or 5s and takes the
        set's strength), and at least one still fits under the kinfolk limit (10, or 12
        with an Evergreen boon)."""
        if total + strength > self.kinfolk_limit(game):
            return []
        out = []
        for cid in self.unlocked_hand(game, player):
            c = game.cards[cid]
            if c.is_ace or c.is_jester or c.has("beast"):
                continue
            if strength in self.set_strengths(game, c):
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
        # Effects owed to the cards that just entered play (the Evergreen Mother's banish,
        # mission 7's pilgrim matches) are settled before the relics look at the attack: the
        # Scarlet Whistle offers the top of the discard pile, which the Mother may banish.
        entry = self._pending_entry_decision(game)
        if entry is not None:
            entry["resume_step"] = "after_attack"
            return entry
        return self._relic_after_attack(game, play)

    def _relic_after_attack(self, game, play) -> Optional[Dict[str, Any]]:
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
        if d and d.get("kind") == "druid_assign":
            # A forecast must not show the deal: everything goes back to the discard pile.
            return {"type": "druid_assign", "player": int(d["player"]), "forecast": True}
        if d and d.get("kind") == "chanter_declare":
            return {"type": "chanter_declare", "player": int(d["player"]), "count": 0, "forecast": True}
        if d and d.get("kind") == "chanter_discard":
            acts = self._actions_chanter_discard(game, d)
            if acts:
                t = acts[0]
                lowest = sorted(t["pick_from"], key=lambda c: (game.cards[c].defence_value, game.cards[c].value))
                return {"type": "chanter_discard", "player": int(d["player"]), "cards": lowest[:int(t["needs"])],
                        "forecast": True}
        if d and d.get("kind") == "declare_class":
            # a forecast does not ask: a Wild Animal is assumed a warrior, 2/5s with a free
            # choice 5s (a value their kinfolk set forces is set without a question)
            return {"type": "declare_class", "player": int(d["player"]), "option": "C", "forecast": True}
        if d and d.get("kind") == "declare_value":
            return {"type": "declare_value", "player": int(d["player"]), "option": "5", "forecast": True}
        if d and d.get("kind") == "mother_choice":
            return {"type": "mother_choice", "player": int(d["player"]), "option": "reserve", "forecast": True}
        if d and d.get("kind") == "mother_banish":
            acts = self._actions_mother_banish(game, d)
            if acts:
                return dict(acts[0], forecast=True)
        if d and d.get("kind") in ("discard_order", "reaver_order"):
            # the order nothing is asked in: as revealed (a reaver's chosen card last)
            options = [str(c) for c in d.get("options", [])]
            chosen = str(d.get("reaver_card", ""))
            if chosen in options:
                options = [c for c in options if c != chosen] + [chosen]
            return {"type": str(d["kind"]), "player": int(d["player"]), "cards": options, "forecast": True}
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
                for cid in self.unlocked_hand(game, player)]
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
        room = (self.kinfolk_limit(game) - play.value) // strength
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
            # the whole attack stays one kinfolk set: an added 2/5 takes its strength
            for entry in game.extra.get("declare_pending") or []:
                if entry.get("what") == "value" and set(entry.get("cards") or ()) & set(ids):
                    entry["group"] = list(play.card_ids)
            game._say("%s adds %s to the attack (Kinfolk Flute): strength %d." % (
                name, " + ".join(game.cards[c].label() for c in ids), play.value))
            if self._interrupt(game, d, "flute"):
                return
        else:
            game._event("flute_pass", player=player)
            game._say("%s adds nothing to the attack." % name)
        self._continue_flute(game, d)

    def _continue_flute(self, game, d: Dict[str, Any]) -> None:
        """After a Kinfolk Flute player acted: ask the next one who can add, or resolve."""
        play_index = int(d["play_index"])
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
        return [cid for cid in self.unlocked_hand(game, player) if not game.cards[cid].is_jester]

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
            if self._interrupt(game, d, "resolve"):
                return
        else:
            game._event("whistle_skip", player=player)
            game._say("%s leaves the discard pile alone." % game.players[player].name)
        game.resolve_pending_attack()

    def _continue_resolve(self, game, d: Dict[str, Any]) -> None:
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
            if self._interrupt(game, d, "resolve"):
                return
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
        if suit == "U":
            return self._druid_start(game)
        if suit == "T":
            return self._chanter_start(game)
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
    # The revealed cards are banished with the chosen one last, unless the top of the
    # banished pile matters (missions 5, 11, 12, some Evergreen setups) and two or more of
    # them reach the pile: the player then names their order (``reaver_order``, a template
    # filled with the permutation: the first named is banished first, the last ends on
    # top; games saved on the older ``banish_top`` question still resolve). A 2/5 adds 5
    # (the player chooses its value when it matters), a Jester or a beast adds 0. With an
    # empty reserve there is nothing to reveal and the reaver only doubles.
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
        others = [c for c in revealed if c != cid]
        reaching = self._reach_banished(game, revealed)
        if len(reaching) >= 2 and self.banished_top_matters(game):
            # "banish all revealed cards in any order": the top of the banished pile counts
            # in this mission, so the player names the order (the last ends on top)
            d["kind"] = "reaver_order"
            d["reaver_card"] = cid
            d["options"] = reaching
            game._event("decide", **d)
            game._say("Reaver: %s adds %s's strength; in what order are %s banished (the last ends on top)?" % (
                game.players[player].name, game.cards[cid].label(), " / ".join(game.cards[c].label() for c in reaching)))
            return
        self._reaver_finish(game, d, cid, others + [cid])

    def _actions_reaver_order(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        options = [str(c) for c in d.get("options", [])]
        return [{"type": "reaver_order", "player": int(d["player"]), "pick_from": options, "needs": len(options),
                 "ordered": True, "label": "Banish the revealed cards in this order (the last ends on top)"}]

    def _decide_reaver_order(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        order = self._full_order(d, action, "Name every revealed card exactly once.")
        # a restored card the mission 12 relic keeps off the pile goes first (under the reserve)
        revealed = [str(c) for c in d.get("revealed", [])]
        self._reaver_finish(game, d, str(d["reaver_card"]), [c for c in revealed if c not in order] + order, order)

    def _reaver_finish(self, game, d: Dict[str, Any], cid: str, order: List[str],
                       named: Optional[List[str]] = None) -> None:
        """The chosen card's strength joins the damage, the revealed cards are banished in
        ``order`` (the last ends on top) and the damage is doubled. ``named``: the order
        the player gave (``reaver_order``), announced after the pick."""
        player = int(d["player"])
        added = self.reaver_value(game.cards[cid])
        game.banish_cards(order)
        d["revealed"] = []
        for key in ("source", "reaver_card", "options"):
            d.pop(key, None)
        before = int(d["damage"])
        d["damage"] = (before + added) * 2
        play = game.plays[int(d["play_index"])]
        game._event("reaver_pick", player=player, card=cid, added=added, banished=order, damage=d["damage"])
        game._event("power", suit="R", value=play.value, added=added, doubled=True)
        game._say("Reaver: %s adds %s's strength (+%d) and doubles the damage: %d + %d = %d, doubled to %d. %s banished." % (
            game.players[player].name, game.cards[cid].label(), added, before, added, before + added, d["damage"],
            " + ".join(game.cards[c].label() for c in order)))
        if named:
            game._event("reaver_order", player=player, cards=list(named))
            game._say("%s banished them in the order %s: %s ends on top of the banished pile." % (
                game.players[player].name, ", ".join(game.cards[c].label() for c in named), game.cards[named[-1]].label()))
        game.resolve_pending_attack()

    # ------------------------------------------------------------------ druids
    # Rulebook p.16 (confirmed): "players set their hands aside; shuffle the discard pile
    # and deal it out clockwise starting with the druid's player; each player picks 4 of
    # their dealt cards and moves one each to the banished pile, their hand (ignoring the
    # limit), the top of the reserve and the bottom of the reserve; everything else goes
    # back to the discard pile, which is shuffled. The druid's strength is not used."
    # One ``druid_assign`` decision per player who was dealt cards, clockwise from the
    # druid's player; a player dealt fewer than four cards assigns each of them to a
    # distinct destination of their choice. The action list holds a template (``needs``
    # cards from ``pick_from``) that the player fills in: {"type": "druid_assign",
    # "player": i, "banish": id, "hand": id, "top": id, "bottom": id}.
    DRUID_SLOTS = ("banish", "hand", "top", "bottom")

    def _druid_start(self, game) -> Any:
        if not game.discard:
            game._say("Druid: the discard pile is empty, there is nothing to sort.")
            return {"dealt": 0}
        pile = list(game.discard)
        game.rng.shuffle(pile)
        game.discard = []
        dealt: List[List[str]] = [[] for _ in range(game.n_players)]
        for i, cid in enumerate(pile):
            dealt[(game.active + i) % game.n_players].append(cid)
        game._event("druid_deal", player=game.active, dealt=[list(x) for x in dealt])
        game._say("Druid: the discard pile (%d card%s) is shuffled and dealt out, starting with %s." % (
            len(pile), "" if len(pile) == 1 else "s", game.players[game.active].name))
        queue = [(game.active + k) % game.n_players for k in range(game.n_players)]
        first, rest = self._druid_next(game, queue, dealt)
        return {"decision": {"kind": "druid_assign", "player": first, "dealt": dealt, "queue": rest}}

    @staticmethod
    def _druid_next(game, queue: Sequence[int], dealt: Sequence[Sequence[str]]) -> Tuple[Optional[int], List[int]]:
        rest = list(queue)
        while rest:
            p = rest.pop(0)
            if dealt[p]:
                return p, rest
        return None, []

    def druid_options(self, game) -> List[str]:
        """The cards dealt to the player who must assign them now (for UIs)."""
        d = game.decision or {}
        if d.get("kind") != "druid_assign":
            return []
        return [str(c) for c in d["dealt"][int(d["player"])]]

    def _actions_druid_assign(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        options = [str(c) for c in d["dealt"][player]]
        needs = min(4, len(options))
        return [{"type": "druid_assign", "player": player, "pick_from": options, "needs": needs,
                 "slots": list(self.DRUID_SLOTS),
                 "label": "Assign %d card%s: banish, hand, top and bottom of the reserve" % (needs, "" if needs == 1 else "s")}]

    def _decide_druid_assign(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        from ..engine import IllegalAction
        player = int(d["player"])
        dealt = [list(x) for x in d["dealt"]]
        mine = dealt[player]
        if not action.get("forecast"):
            picks = {slot: str(action[slot]) for slot in self.DRUID_SLOTS if action.get(slot)}
            ids = list(picks.values())
            needs = min(4, len(mine))
            if len(ids) != needs or len(set(ids)) != needs:
                raise IllegalAction("Assign %d distinct card%s." % (needs, "" if needs == 1 else "s"))
            for cid in ids:
                if cid not in mine:
                    raise IllegalAction("Card %s was not dealt to you." % cid)
            name = game.players[player].name
            said = []
            for slot in self.DRUID_SLOTS:
                cid = picks.get(slot)
                if cid is None:
                    continue
                mine.remove(cid)
                label = game.cards[cid].label()
                if slot == "banish":
                    game.banish_cards([cid])
                    said.append("%s banished" % label)
                elif slot == "hand":
                    game.players[player].hand.append(cid)
                    said.append("%s to hand" % label)
                elif slot == "top":
                    game.to_reserve(cid)
                    said.append("%s on top of the reserve" % label)
                else:
                    game.to_reserve(cid, bottom=True)
                    said.append("%s under the reserve" % label)
            game._event("druid_assign", player=player, **picks)
            game._say("Druid: %s sorts: %s." % (name, ", ".join(said)))
            d["dealt"] = dealt
            nxt, rest = self._druid_next(game, d.get("queue", []), dealt)
            if nxt is not None:
                d["player"] = nxt
                d["queue"] = rest
                game._event("decide", **d)
                game._say("Druid: %s assigns %d of the %d cards dealt." % (
                    game.players[nxt].name, min(4, len(dealt[nxt])), len(dealt[nxt])))
                return
        rest_cards = [c for lst in dealt for c in lst]
        game.rng.shuffle(rest_cards)
        game.discard = rest_cards
        d["dealt"] = [[] for _ in dealt]
        game._event("druid_done", returned=len(rest_cards))
        game._say("Druid: the %d other card%s go back to the discard pile, shuffled." % (
            len(rest_cards), "" if len(rest_cards) == 1 else "s"))
        game.resolve_pending_attack()

    # ------------------------------------------------------------------ chanters
    # Rulebook p.16 (confirmed): "declare any number; starting with the current player and
    # going clockwise, each player draws that many cards ignoring the hand limit, then
    # discards down to the limit." The attacker declares (0 to the size of the reserve),
    # everyone draws, then each player over the limit, clockwise from the attacker,
    # chooses what to discard (a template action filled in with ``cards``).
    def _chanter_start(self, game) -> Any:
        game._say("Chanter: %s declares how many cards everyone draws (0 to %d)." % (
            game.players[game.active].name, len(game.tavern)))
        return {"decision": {"kind": "chanter_declare", "player": game.active, "max": len(game.tavern)}}

    def _actions_chanter_declare(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        return [{"type": "chanter_declare", "player": player, "count": n,
                 "label": "Everyone draws %d" % n if n else "Nobody draws"}
                for n in range(0, len(game.tavern) + 1)]

    def _decide_chanter_declare(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        from ..engine import IllegalAction
        player = int(d["player"])
        n = int(action.get("count", 0))
        if not 0 <= n <= len(game.tavern):
            raise IllegalAction("Declare between 0 and %d." % len(game.tavern))
        drawn: List[Dict[str, Any]] = []
        for k in range(game.n_players):
            p = (player + k) % game.n_players
            got = []
            for _ in range(n):
                if not game.tavern:
                    break
                cid = game.tavern.pop(0)
                game.players[p].hand.append(cid)
                got.append(cid)
            drawn.append({"player": p, "cards": got})
        game._event("chanter_declare", player=player, count=n, drawn=drawn)
        if n == 0:
            game._say("Chanter: %s declares 0, nobody draws." % game.players[player].name)
        else:
            game._say("Chanter: %s declares %d; %s." % (
                game.players[player].name, n,
                ", ".join("%s draws %d" % (game.players[x["player"]].name, len(x["cards"])) for x in drawn)))
        d["kind"] = "chanter_discard"
        d.pop("max", None)
        d["queue"] = [(player + k) % game.n_players for k in range(game.n_players)]
        self._chanter_next(game, d)

    def _chanter_excess(self, game, player: int) -> int:
        """Cards a player must discard down to the limit (never a locked card)."""
        over = len(game.players[player].hand) - game.config.max_hand
        return max(0, min(over, len(self.unlocked_hand(game, player))))

    def _chanter_next(self, game, d: Dict[str, Any]) -> None:
        queue = list(d.get("queue", []))
        while queue:
            p = queue.pop(0)
            if self._chanter_excess(game, p) > 0:
                d["player"] = p
                d["queue"] = queue
                game._event("decide", **d)
                game._say("Chanter: %s discards down to %d cards." % (game.players[p].name, game.config.max_hand))
                return
        d["queue"] = []
        game.resolve_pending_attack()

    def _actions_chanter_discard(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        needs = self._chanter_excess(game, player)
        if needs <= 0:
            return []
        return [{"type": "chanter_discard", "player": player, "pick_from": self.unlocked_hand(game, player),
                 "needs": needs, "label": "Discard %d card%s" % (needs, "" if needs == 1 else "s")}]

    def _decide_chanter_discard(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        from ..engine import IllegalAction
        player = int(d["player"])
        needs = self._chanter_excess(game, player)
        ids = [str(c) for c in action.get("cards", [])]
        allowed = self.unlocked_hand(game, player)
        if len(ids) != needs or len(set(ids)) != needs:
            raise IllegalAction("Discard exactly %d card%s." % (needs, "" if needs == 1 else "s"))
        for cid in ids:
            if cid not in allowed:
                raise IllegalAction("Card %s cannot be discarded." % cid)
        for cid in ids:
            game.players[player].hand.remove(cid)
        game._discard_cards([game.cards[c] for c in ids])
        game._event("chanter_discard", player=player, cards=ids)
        game._say("Chanter: %s discards %s." % (game.players[player].name, " + ".join(game.cards[c].label() for c in ids)))
        self._chanter_next(game, d)

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
            game.mage_add_to_play(cid)
            d["picked"] = cid
            if self._interrupt(game, d, "mage_picked"):
                return
            self._continue_mage_picked(game, d)
            return
        if not action.get("forecast") and self._ask_discard_order(game, d, "skip"):
            game._event("mage_skip", player=player, discarded=[])
            game._say("Mage: nothing may join the attack; the revealed cards go to the discard pile.")
            self._show_discard_order(game, d)
            return
        rest = self._mage_discard_rest(game, d)
        game._event("mage_skip", player=player, discarded=rest)
        if rest:
            game._say("Mage: nothing may join the attack; %s to the discard pile." % (
                " + ".join(game.cards[c].label() for c in rest)))
        else:
            game._say("Mage: nothing to add.")
        game.resolve_pending_attack()

    # The revealed cards a mage does not choose go to the discard pile "in any order" (p.16):
    # when the top of the pile matters and two or more go, the player names their order
    # (``discard_order``, a template filled with the permutation: the first named goes
    # first, the last ends on top); otherwise they go in the order revealed. Games saved
    # while the app asked only for the top card (``discard_top``) still resolve.
    def _ask_discard_order(self, game, d: Dict[str, Any], then: str) -> bool:
        rest = [str(c) for c in d.get("revealed", [])]
        if len(rest) < 2 or not self.discard_top_matters(game):
            return False
        d["kind"] = "discard_order"
        d["options"] = rest
        d["then"] = then
        d.pop("eligible", None)
        return True

    def _show_discard_order(self, game, d: Dict[str, Any]) -> None:
        game._event("decide", **d)
        game._say("%s chooses the order in which %s go to the discard pile (the last ends on top)." % (
            game.players[int(d["player"])].name, " / ".join(game.cards[c].label() for c in d["options"])))

    def _actions_discard_order(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        options = [str(c) for c in d.get("options", [])]
        return [{"type": "discard_order", "player": int(d["player"]), "pick_from": options, "needs": len(options),
                 "ordered": True, "label": "Discard the revealed cards in this order (the last ends on top)"}]

    def _decide_discard_order(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        order = self._full_order(d, action, "Name every revealed card exactly once.")
        game._event("discard_order", player=int(d["player"]), cards=order)
        game._say("%s go to the discard pile in that order, %s on top." % (
            " + ".join(game.cards[c].label() for c in order), game.cards[order[-1]].label()))
        self._mage_rest_discarded(game, d, order)

    @staticmethod
    def _full_order(d: Dict[str, Any], action: Dict[str, Any], error: str) -> List[str]:
        """The cards of a ``*_order`` action: every option of the decision exactly once."""
        order = [str(c) for c in action.get("cards") or []]
        if sorted(order) != sorted(str(c) for c in d.get("options", [])):
            from ..engine import IllegalAction
            raise IllegalAction(error)
        return order

    def _actions_discard_top(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        # a game saved before the full-order question: which card ends on top
        player = int(d["player"])
        return [{"type": "discard_top", "player": player, "card": str(cid),
                 "label": "Put %s on top of the discard pile" % game.cards[str(cid)].label()}
                for cid in d.get("options", [])]

    def _decide_discard_top(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        top = str(action["card"])
        rest = [str(c) for c in d.get("revealed", [])]
        order = [c for c in rest if c != top] + [top]
        game._event("discard_top", player=int(d["player"]), card=top, discarded=order)
        game._say("%s to the discard pile, %s on top." % (" + ".join(game.cards[c].label() for c in order),
                                                          game.cards[top].label()))
        self._mage_rest_discarded(game, d, order)

    def _mage_rest_discarded(self, game, d: Dict[str, Any], order: List[str]) -> None:
        """The unchosen cards go to the discard pile in the player's ``order`` (one at a time,
        the last on top), then the mage goes on: the chain after a pick, else the attack."""
        for cid in order:
            game.discard.insert(0, cid)
        d["revealed"] = []
        then = str(d.pop("then", "skip"))
        d.pop("options", None)
        if then == "picked":
            self._mage_continue(game, d, game.cards[str(d["picked"])])
            return
        game.resolve_pending_attack()

    def _continue_mage_picked(self, game, d: Dict[str, Any]) -> None:
        """The chosen card joined the attack (and any effect it owed is settled): the
        Emblem's solo keep, or the rest to the discard pile and the chain."""
        player = int(d["player"])
        name = game.players[player].name
        cid = str(d["picked"])
        play = game.plays[int(d["play_index"])]
        card = game.cards[cid]
        if self._emblem(game) and game.config.players == 1 and d.get("revealed"):
            # Azure Emblem, solo side: the rest is not discarded yet, one of those cards
            # may go back on top of the reserve first (``_emblem_keep_decide``).
            game._event("mage_pick", player=player, card=cid, value=play.value, discarded=[])
            game._say("%s adds %s to the attack (Mage): strength %d." % (name, card.label(), play.value))
            d["kind"] = "emblem_keep"
            d.pop("eligible", None)
            game._event("decide", **d)
            game._say("Azure Emblem: %s may put one of the other revealed cards back on top of the reserve deck." % name)
            return
        if self._ask_discard_order(game, d, "picked"):
            game._event("mage_pick", player=player, card=cid, value=play.value, discarded=[])
            game._say("%s adds %s to the attack (Mage): strength %d." % (name, card.label(), play.value))
            self._show_discard_order(game, d)
            return
        rest = self._mage_discard_rest(game, d)
        game._event("mage_pick", player=player, card=cid, value=play.value, discarded=rest)
        tail = " %s to the discard pile." % " + ".join(game.cards[c].label() for c in rest) if rest else ""
        game._say("%s adds %s to the attack (Mage): strength %d.%s" % (name, card.label(), play.value, tail))
        self._mage_continue(game, d, card)

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
            if self.unlocked_hand(game, p):
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
            if cid not in self.unlocked_hand(game, player):
                from ..engine import IllegalAction
                raise IllegalAction("Card %s is not in hand." % cid)
            hand.remove(cid)
            game.to_reserve(cid)
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
            game.to_reserve(cid)
            if self._ask_discard_order(game, d, "picked"):
                game._event("emblem_keep", player=player, card=cid, discarded=[])
                game._say("Azure Emblem: %s puts %s back on top of the reserve deck." % (name, game.cards[cid].label()))
                self._show_discard_order(game, d)
                return
            rest = self._mage_discard_rest(game, d)
            game._event("emblem_keep", player=player, card=cid, discarded=rest)
            tail = " %s to the discard pile." % " + ".join(game.cards[c].label() for c in rest) if rest else ""
            game._say("Azure Emblem: %s puts %s back on top of the reserve deck.%s" % (name, game.cards[cid].label(), tail))
        else:
            if self._ask_discard_order(game, d, "picked"):
                game._event("emblem_skip", player=player, discarded=[])
                game._say("Azure Emblem: nothing kept.")
                self._show_discard_order(game, d)
                return
            rest = self._mage_discard_rest(game, d)
            game._event("emblem_skip", player=player, discarded=rest)
            game._say("Azure Emblem: nothing kept; %s to the discard pile." % " + ".join(game.cards[c].label() for c in rest))
        self._mage_continue(game, d, game.cards[str(d["picked"])])

    # ------------------------------------------------------------------ corruption
    def on_cards_played(self, game, cards: Sequence[Card], player: Optional[int] = None) -> None:
        owner = game.active if player is None else int(player)
        twofives = [c.id for c in cards if c.has("twofive")]
        for c in cards:
            # Rulebook p.25: a Wild Animal declares a class, a 2/5 a value, when it enters a
            # playmat; settled before the attack goes on (see ``_declare_next``). The 2/5s
            # entering together share one value: one entry for them all; ``group`` is the
            # kinfolk set whose strength they must match (none: a free choice).
            if c.has("choosable"):
                game.extra.setdefault("declare_pending", []).append({"card": c.id, "what": "class", "player": owner})
            elif c.has("twofive") and c.id == twofives[0]:
                entry = {"card": c.id, "cards": list(twofives), "what": "value", "player": owner}
                if self._kinfolk_batch(cards):
                    entry["group"] = [x.id for x in cards]
                for cid in twofives:     # a value from an earlier visit to the playmat is spent
                    (game.extra.get("declared_value") or {}).pop(cid, None)
                carry = game.extra.get("flute_carry") or {}
                for cid in twofives:     # ...but one played from the flute keeps its stored value
                    if cid in carry:
                        game.extra.setdefault("declared_value", {})[cid] = int(carry.pop(cid))
                if not carry:
                    game.extra.pop("flute_carry", None)
                game.extra.setdefault("declare_pending", []).append(entry)
            if c.has("corrupted"):
                self._corrupted_banish(game, c, owner)
            if c.has("restored") and game.banished:
                back = game.banished.pop()
                game.to_reserve(back, bottom=True)
                game._event("restore", card=c.id, returned=back)
                game._say("%s (restored) returns %s under the reserve deck." % (c.label(), game.cards[back].label()))

    def _mother(self, game) -> bool:
        return "mother" in game.extra.get("relics", [])

    def banish_redirect(self, game, card: Card) -> Optional[str]:
        """Evergreen Mother, restored relic (mission 12 on, confirmed, both sides the
        same): "Restored cards can never enter the banished pile. If they would, instead
        put them on the bottom of the reserve deck." Every banish (clean-up, a mission
        zone, the discard pile, the corrupt relic's hand banish, a beast or a corrupted
        card's effect) goes through ``Game.banish_cards``, which asks here."""
        if card.has("restored") and "mother_restored" in game.extra.get("relics", []):
            return "reserve_bottom"
        return None

    def _corrupted_banish(self, game, card: Card, owner: int) -> None:
        """Rulebook p.15: when a corrupted card enters play, banish the top card of the
        reserve deck. With the Evergreen Mother (corrupt relic, confirmed) the banish may
        need a choice, which is queued in ``extra["mother_pending"]`` and asked before the
        attack goes on (see ``_pending_entry_decision``): solo, "if the discard pile is not
        empty, you may choose to banish a card from the top of the discard pile instead";
        2+ players, "another player must banish a card from their hand; if all other
        players' hands are empty, do not banish any card"."""
        if self._mother(game):
            if game.n_players == 1 and game.discard:
                game.extra.setdefault("mother_pending", []).append({"card": card.id, "player": owner})
                return
            if game.n_players >= 2:
                if self._mother_hand(game, owner) is None:
                    game._event("corrupt_banish_none", card=card.id)
                    game._say("%s is corrupted, but every other hand is empty: nothing is banished (Evergreen Mother)." % card.label())
                    return
                game.extra.setdefault("mother_pending", []).append({"card": card.id, "player": owner})
                return
        self._banish_from(game, card, "reserve")

    def _banish_from(self, game, card: Card, source: str) -> None:
        if source == "discard" and game.discard:
            lost = game.discard.pop(0)
            src = "discard pile"
        elif game.tavern:
            lost = game.tavern.pop(0)
            src = "reserve deck"
        else:
            game._event("corrupt_banish_none", card=card.id)
            game._say("%s is corrupted, but the reserve deck is empty: nothing is banished." % card.label())
            return
        game.banish_cards([lost])
        game._event("corrupt_banish", card=card.id, banished=lost, source=src)
        game._say("%s is corrupted: %s banished from the %s." % (card.label(), game.cards[lost].label(), src))

    def _mother_hand(self, game, owner: int) -> Optional[int]:
        """The first other player clockwise from the corrupted card's owner with a card
        they may banish from hand."""
        for k in range(1, game.n_players):
            p = (owner + k) % game.n_players
            if self.unlocked_hand(game, p):
                return p
        return None

    def _mother_next(self, game) -> Optional[Dict[str, Any]]:
        """The next Evergreen Mother decision owed, popped from the queue, or None."""
        queue = game.extra.get("mother_pending") or []
        while queue:
            entry = queue.pop(0)
            card = game.cards[str(entry["card"])]
            owner = int(entry["player"])
            if game.n_players == 1:
                if not game.discard:
                    self._banish_from(game, card, "reserve")
                    continue
                game._say("Evergreen Mother: %s is corrupted; banish the top of the discard pile or of the reserve deck?" % card.label())
                return {"kind": "mother_choice", "player": game.active, "card": card.id}
            p = self._mother_hand(game, owner)
            if p is None:
                game._event("corrupt_banish_none", card=card.id)
                game._say("%s is corrupted, but every other hand is empty: nothing is banished (Evergreen Mother)." % card.label())
                continue
            game._say("Evergreen Mother: %s is corrupted; %s must banish a card from hand." % (
                card.label(), game.players[p].name))
            return {"kind": "mother_banish", "player": p, "card": card.id, "owner": owner}
        game.extra.pop("mother_pending", None)
        return None

    def _actions_mother_choice(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts: List[Dict[str, Any]] = []
        if game.discard:
            acts.append({"type": "mother_choice", "player": player, "option": "discard",
                         "label": "Banish %s, top of the discard pile" % game.cards[game.discard[0]].label()})
        # "you may choose to banish a card from the top of the discard pile instead of the
        # reserve deck": the reserve stays an option even when it is empty (nothing is
        # banished then, as without the relic)
        acts.append({"type": "mother_choice", "player": player, "option": "reserve",
                     "label": "Banish the top card of the reserve deck" if game.tavern
                     else "Banish nothing (the reserve deck is empty)"})
        return acts

    def _decide_mother_choice(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        card = game.cards[str(d["card"])]
        option = str(action.get("option"))
        if option == "discard" and not game.discard:
            from ..engine import IllegalAction
            raise IllegalAction("The discard pile is empty.")
        self._banish_from(game, card, "discard" if option == "discard" else "reserve")
        self._entry_done(game, d)

    def _actions_mother_banish(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        return [{"type": "mother_banish", "player": player, "card": cid,
                 "label": "Banish %s from hand" % game.cards[cid].label()}
                for cid in self.unlocked_hand(game, player)]

    def _decide_mother_banish(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        cid = str(action["card"])
        if cid not in self.unlocked_hand(game, player):
            from ..engine import IllegalAction
            raise IllegalAction("Card %s is not in hand." % cid)
        game.players[player].hand.remove(cid)
        game.banish_cards([cid])
        card = game.cards[str(d["card"])]
        game._event("corrupt_banish", card=card.id, banished=cid, source="hand", player=player)
        game._say("%s is corrupted: %s banishes %s from hand (Evergreen Mother)." % (
            card.label(), game.players[player].name, game.cards[cid].label()))
        self._entry_done(game, d)

    # ------------------------------------------------------------------ effects owed to cards entering play
    # A card entering play may owe a decision (the Evergreen Mother's banish; mission 7's
    # pilgrim matches add theirs). ``_pending_entry_decision`` builds the next one. Such a
    # decision can arise inside another decision's flow (a Kinfolk Flute or Scarlet Whistle
    # addition, a mage's pick): ``_interrupt`` parks the running decision inside the new
    # one and ``_entry_done`` restores it and calls its ``_continue_<step>`` method; from
    # ``after_attack_formed`` the step is "after_attack" (the relics' turn, then the
    # resolution).
    def _pending_entry_decision(self, game) -> Optional[Dict[str, Any]]:
        d = self._declare_next(game)
        if d is not None:
            return d
        return self._mother_next(game)

    # ------------------------------------------------------------------ declarations (rulebook p.25)
    # "2/5 mercenaries: declare 2 or 5 when the card enters your playmat and keep that value
    # while it is in play ... Wild Animal mercenaries show four class icons: declare one class
    # when the card enters your playmat; at other times you decide which class it is." The
    # declaration is settled through the entry-effect queue, first, whenever such a card
    # enters play (played, or added by a Kinfolk Flute, a Scarlet Whistle or a mage). The
    # 2/5s entering play together get one value and one question at most: in a kinfolk set
    # they take the set's strength (2/5 + 5 counts 5, 2/5 + 2 counts 2, three 2/5s count 2
    # under the limit of 10: recorded and logged, no question), two 2/5s on their own may
    # be 2s or 5s (asked), and a 2/5 alone, with a companion or a beast, or added by a mage
    # or a Scarlet Whistle is declared freely (asked; a beast copies the value). A Kinfolk
    # Flute addition joins the attack's set and takes its strength. The values live in
    # ``extra["declared"]`` and ``extra["declared_value"]`` until the next enemy appears
    # (``on_enemy_revealed``); ``card_suits`` and ``in_play_strength`` read them while the
    # card is in play (attack strength, a beast's copy, mission 7's pilgrim matches, the
    # Evergreen attack checks, the multiplayer Kinfolk Flute).
    @staticmethod
    def _play_of(game, card_id: str):
        for play in game.plays:
            if card_id in play.card_ids:
                return play
        return None

    def _value_options(self, game, entry: Dict[str, Any], ids: Sequence[str]) -> List[int]:
        """The values the 2/5s ``ids`` (one pending entry) may take: those their kinfolk set
        allows, or 2 and 5 when nothing constrains them."""
        group = entry.get("group")
        if group is None and "cards" not in entry:
            # an entry saved before 2/5s shared one: the attack it joined was its batch
            play = self._play_of(game, ids[0])
            if play is not None and self._kinfolk_batch([game.cards[c] for c in play.card_ids]):
                group = list(play.card_ids)
        if group:
            cards = [game.cards[str(c)] for c in group if self._play_of(game, str(c)) is not None]
            values = self.kinfolk_values(game, cards)
            if values:
                return values
        return list(TWOFIVE_VALUES)

    @staticmethod
    def _value_ids(d: Dict[str, Any]) -> List[str]:
        """The 2/5s a pending entry or a ``declare_value`` decision is about."""
        return [str(c) for c in (d.get("cards") or [d["card"]])]

    def declare_value_question(self, game, d: Dict[str, Any]) -> str:
        """What a ``declare_value`` decision asks, naming its cards (for UIs)."""
        ids = [c for c in self._value_ids(d) if c in game.cards]
        return "%s: strength 2 or 5?" % (" + ".join(game.cards[c].label() for c in ids) or "2/5")

    def _declare_next(self, game) -> Optional[Dict[str, Any]]:
        queue = game.extra.get("declare_pending") or []
        while queue:
            entry = queue.pop(0)
            player = int(entry.get("player", game.active))
            if entry.get("what") == "class":
                cid = str(entry["card"])
                if self._play_of(game, cid) is None:
                    continue
                game._say("%s enters play: %s declares its class." % (game.cards[cid].label(), game.players[player].name))
                return {"kind": "declare_class", "player": player, "card": cid}
            ids = [c for c in self._value_ids(entry) if self._play_of(game, c) is not None]
            if not ids:
                continue
            options = self._value_options(game, entry, ids)
            if len(options) == 1:
                # the kinfolk set allows one value only: recorded without a question
                self._set_values(game, None, ids, options[0], player, forced=True)
                continue
            d = {"kind": "declare_value", "player": player, "card": ids[0], "cards": ids}
            game._say("%s %s declares." % (self.declare_value_question(game, d), game.players[player].name))
            return d
        game.extra.pop("declare_pending", None)
        return None

    def _actions_declare_class(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        return [{"type": "declare_class", "player": player, "option": s,
                 "label": "%s %s" % (SUIT_SYMBOL[s], CLASS_NAME[s])} for s in BASIC_SUITS]

    def _actions_declare_value(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        return [{"type": "declare_value", "player": player, "option": str(v), "label": "Strength %d" % v}
                for v in TWOFIVE_VALUES]

    def _refresh_declared_play(self, game, d: Optional[Dict[str, Any]], cid: str) -> None:
        """The attack holding a just-declared card gets its strength and classes again; a
        paused resolution's running damage follows the strength."""
        play = self._play_of(game, cid)
        if play is None:
            return
        before = play.value
        cards = [game.cards[c] for c in play.card_ids]
        play.value = self.play_value(game, cards)
        play.suits = game.play_suits(cards)
        saved = d.get("resume_decision") if d else None
        if isinstance(saved, dict) and "damage" in saved:
            saved["damage"] = int(saved["damage"]) + play.value - before

    def _set_values(self, game, d: Optional[Dict[str, Any]], ids: Sequence[str], value: int, player: int,
                    forced: bool = False) -> None:
        """The 2/5s ``ids`` (entering play together) count ``value`` while they are in play;
        their attack is refreshed. ``forced``: their kinfolk set allowed nothing else."""
        store = game.extra.setdefault("declared_value", {})
        for cid in ids:
            store[cid] = int(value)
        self._refresh_declared_play(game, d, ids[0])
        play = self._play_of(game, ids[0])
        attack = play.value if play is not None else 0
        for cid in ids:
            game._event("declare", player=player, card=cid, value=int(value), forced=forced, attack=attack)
        labels = " + ".join(game.cards[c].label() for c in ids)
        if forced:
            game._say("%s %s %d: the kinfolk set allows no other strength." % (
                labels, "counts" if len(ids) == 1 else "each count", value))
        else:
            game._say("%s declares %s %s %d." % (game.players[player].name, labels,
                                                 "a" if len(ids) == 1 else "each a", value))

    def _decide_declare_class(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        suit = str(action.get("option"))
        if suit not in BASIC_SUITS:
            from ..engine import IllegalAction
            raise IllegalAction("Declare one of the four basic classes.")
        cid = str(d["card"])
        game.extra.setdefault("declared", {})[cid] = suit
        self._refresh_declared_play(game, d, cid)
        game._event("declare", player=int(d["player"]), card=cid, suit=suit)
        game._say("%s declares %s a %s." % (game.players[int(d["player"])].name, game.cards[cid].label(), CLASS_NAME[suit]))
        self._entry_done(game, d)

    def _decide_declare_value(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        value = int(action.get("option", 0))
        if value not in TWOFIVE_VALUES:
            from ..engine import IllegalAction
            raise IllegalAction("Declare 2 or 5.")
        # one declaration for every 2/5 of the question (a save from before the shared
        # questions names a single ``card``)
        ids = [c for c in self._value_ids(d) if self._play_of(game, c) is not None]
        if ids:
            self._set_values(game, d, ids, value, int(d["player"]))
        self._entry_done(game, d)

    def _interrupt(self, game, d: Dict[str, Any], step: str) -> bool:
        nd = self._pending_entry_decision(game)
        if nd is None:
            return False
        nd["play_index"] = d["play_index"]
        if "choice" in d:
            nd["choice"] = d["choice"]
        nd["resume_decision"] = dict(d)
        nd["resume_step"] = step
        game.decision = nd
        game._event("decide", **nd)
        return True

    def _entry_done(self, game, d: Dict[str, Any]) -> None:
        nd = self._pending_entry_decision(game)
        if nd is not None:
            for key in ("play_index", "choice", "resume_decision", "resume_step"):
                if key in d:
                    nd[key] = d[key]
            game.decision = nd
            game._event("decide", **nd)
            return
        step = str(d.get("resume_step", "after_attack"))
        if step == "after_attack":
            play = game.plays[int(d["play_index"])]
            rd = self._relic_after_attack(game, play)
            if rd is None:
                game.resolve_pending_attack()
                return
            rd["play_index"] = d["play_index"]
            if "choice" in d:
                rd["choice"] = d["choice"]
            game.decision = rd
            game._event("decide", **rd)
            return
        saved = dict(d["resume_decision"])
        game.decision = saved
        getattr(self, "_continue_" + step)(game, saved)

    # ------------------------------------------------------------------ continuing after a decision
    # A mission decision that is not part of an attack's resolution ends by calling
    # ``_decision_done``: the engine's ``resume`` field says which flow it interrupted
    # (the enemy-defeated steps, the end or start of a turn, the damage just paid) and
    # the matching ``_<flow>_done`` method resumes it. Rule sets that chain several
    # decisions in one flow (Evergreen) override those methods.
    def _decision_done(self, game, d: Dict[str, Any]) -> None:
        resume = str(d.get("resume", "defeat"))
        if resume == "end_turn":
            self._eot_done(game, d)
        elif resume == "turn_start":
            self._turn_start_done(game, d)
        elif resume == "suffered":
            self._suffered_done(game, d)
        elif resume == "resolve":
            game.resolve_pending_attack()
        else:
            self._defeat_step_done(game, d)

    def _eot_done(self, game, d: Dict[str, Any]) -> None:
        game.resume_end_turn()

    def _turn_start_done(self, game, d: Dict[str, Any]) -> None:
        game.resume_turn_start()

    def _suffered_done(self, game, d: Dict[str, Any]) -> None:
        game.resume_suffered()

    def _defeat_step_done(self, game, d: Dict[str, Any]) -> None:
        game.resume_defeat()

    # ------------------------------------------------------------------ team damage (mission 6 style)
    # Mission 6's rules card (confirmed): "cards may be discarded one at a time by any
    # player (in any order) until a total amount of strength has been discarded at least
    # equal to the team damage suffered. If this team damage cannot be satisfied the
    # mission is lost." Evergreen's Hills and bane 13 use the same rules.
    def _start_team_damage(self, game, d: Dict[str, Any], damage: int, source: str) -> bool:
        """Turn ``d`` (the pending decision dict) into a ``team_discard`` decision for
        ``damage`` from ``source``. Returns True when the players must now discard; False
        when nothing is owed (0 damage or a Guardian) or the game was just lost."""
        if game.extra.get("guardian"):
            game._event("team_damage_prevented", damage=damage, source=source)
            game._say("Guardian: %s's %d team damage is prevented." % (source, damage))
            return False
        if damage <= 0:
            return False
        total = sum(game.hand_defence_value(i) for i in range(game.n_players))
        game._event("team_damage", damage=damage, available=total, source=source)
        game._say("%s deals %d team damage: the players discard cards one at a time until %d strength is discarded." % (
            source, damage, damage))
        if total < damage:
            game.decision = None
            game._lose("The team cannot suffer %s's %d damage (%d in hand)." % (source, damage, total))
            return False
        d["kind"] = "team_discard"
        d["damage"] = damage
        d["paid"] = 0
        d["source"] = source
        game._event("decide", **d)
        return True

    def _actions_team_discard(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        acts: List[Dict[str, Any]] = []
        for i, p in enumerate(game.players):
            for cid in self.unlocked_hand(game, i):
                acts.append({"type": "team_discard", "player": i, "card": cid,
                             "label": "%s discards %s" % (p.name, game.cards[cid].label())})
        return acts

    def _decide_team_discard(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        cid = str(action["card"])
        owner = None
        for i, p in enumerate(game.players):
            if cid in self.unlocked_hand(game, i):
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
            self._decision_done(game, d)
            return
        game._event("decide", **d)

    # ------------------------------------------------------------------ cleanup
    # Rulebook p.19 step 2: "Gather all cards played against the enemy and put them on top of
    # the discard pile in any order you wish" (and mission 5: the cards of a mage attack go to
    # the banished pile in the order the current player chooses). Nothing is asked: the app
    # takes the order the cards entered play as that order (the attacks in sequence; within
    # an attack the order its cards were selected, then the cards added to it by a mage, the
    # Scarlet Whistle or the Kinfolk Flute), so the last card to enter play ends on top of
    # its pile (``Game._cleanup_played``; ``order_for_discard`` and ``order_for_banish``
    # keep that order). Games saved while the app still asked which card ends on top
    # (``cleanup_top``, ``banish_top`` from the clean-up) resolve as before: the choice waits
    # in ``extra["cleanup_choice"]`` / ``extra["banish_choice"]`` until the engine cleans up.
    def _reach_banished(self, game, ids: Sequence[str]) -> List[str]:
        """The cards that would really land on the banished pile (mission 12's restored relic
        sends restored cards under the reserve instead)."""
        return [str(c) for c in ids if self.banish_redirect(game, game.cards[str(c)]) is None]

    # --- questions of games saved before the clean-up stopped asking -----------------------
    def _actions_cleanup_top(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"type": "cleanup_top", "player": int(d["player"]), "card": str(cid),
                 "label": "Put %s on top of the discard pile" % game.cards[str(cid)].label()}
                for cid in d.get("options", [])]

    def _decide_cleanup_top(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        cid = str(action["card"])
        game.extra["cleanup_choice"] = cid
        game._event("cleanup_top", player=int(d["player"]), card=cid)
        game._say("%s puts %s on top of the discard pile." % (game.players[int(d["player"])].name, game.cards[cid].label()))
        game.resume_defeat()

    def _actions_banish_top(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"type": "banish_top", "player": int(d["player"]), "card": str(cid),
                 "label": "Put %s on top of the banished pile" % game.cards[str(cid)].label()}
                for cid in d.get("options", [])]

    def _decide_banish_top(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        # the reaver's reveal (``source`` "reaver") or a mage attack at clean-up
        cid = str(action["card"])
        player = int(d["player"])
        game._event("banish_top", player=player, card=cid, source=str(d.get("source", "cleanup")))
        if d.get("source") == "reaver":
            revealed = [str(c) for c in d.get("revealed", [])]
            game._say("%s puts %s on top of the banished pile." % (game.players[player].name, game.cards[cid].label()))
            self._reaver_finish(game, d, str(d["reaver_card"]), [c for c in revealed if c != cid] + [cid])
            return
        game.extra["banish_choice"] = cid
        game._say("%s puts %s on top of the banished pile." % (game.players[player].name, game.cards[cid].label()))
        game.resume_defeat()

    def order_for_discard(self, game, cards: List[Card]) -> List[Card]:
        """A batch in the order given (the clean-up: the order the cards entered play), the
        last on top; the campaign option ``discard_low_to_high`` puts the lowest on top
        instead, and an old save's clean-up choice (``cleanup_choice``) goes on top."""
        if game.config.extra.get("discard_low_to_high"):
            # last inserted ends on top: insert highest first so the lowest is on top
            cards = sorted(cards, key=lambda c: -c.value)
        top = game.extra.get("cleanup_choice")
        if top is not None and any(c.id == top for c in cards):
            game.extra.pop("cleanup_choice", None)
            cards = [c for c in cards if c.id != top] + [c for c in cards if c.id == top]
        return cards

    def order_for_banish(self, game, ids: List[str]) -> List[str]:
        """A mage attack's cards in the order they entered play, the last on top (an old
        save's clean-up choice, ``banish_choice``, goes on top)."""
        top = game.extra.get("banish_choice")
        if top is not None and top in ids:
            game.extra.pop("banish_choice", None)
            ids = [c for c in ids if c != top] + [top]
        return list(ids)


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
    the order they entered play, the last on top (no question; a mage's unchosen cards go
    in the order the player names, ``discard_order``). The twelve
    experiments are in corrupted sleeves, so one drawn into a hand plays as a corrupted
    card (``_lab_castle`` flags them)."""

    id = "legacy_m4"
    mission = 4

    def attack_bonus(self, game) -> int:
        if not game.discard:
            return 0
        return self.strength(game.cards[game.discard[0]])

    def discard_top_feeds_enemy(self, game) -> bool:
        # the clean-up order (the last card to enter play on top) decides the next bonus
        return True


@register_rules
class Mission5Rules(LegacyRules):
    """High and Mighty (confirmed from the cards). Myla starts in the banished pile. End of
    turn: the top card of the banished pile goes face up into the mission zone. Each enemy
    has additional strength equal to the combined strength of the zone. Enemy defeated: the
    enemy and all zone cards are shuffled into the banished pile; on exact damage the next
    enemy takes damage equal to the defeated enemy's strength (the strength shown as it
    fell: printed, plus the zone, less paladin reductions), chaining if that kills it. A
    mage attack's cards are banished in the order the current player chooses (its "Rules
    continued"): the order they entered play, the last on top; a reaver's revealed cards
    in the order the player names (``reaver_order``): the top of the banished pile feeds
    the zone."""

    id = "legacy_m5"
    mission = 5
    uses_mission_zone = True

    def banished_top_matters(self, game) -> bool:
        return True

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
        # Nothing in play may move to the zone (a solo Jester alone killed the enemy): the
        # exact-kill rescue and Myla's team damage happen all the same.
        rescue = [c for c in game.mission_zone if c != MYLA_ID]
        if exact and rescue:
            game._say("Exact kill: %s may move one mission zone card except Myla to the discard pile." % (
                game.players[game.active].name))
            return {"kind": "zone_rescue", "player": game.active, "options": rescue}
        d: Dict[str, Any] = {"player": game.active, "exact": exact}
        if self._start_team_damage(game, d, self.zone_strength(game), "Myla"):
            return d
        return None

    def _actions_zone_move(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [{"type": "zone_move", "player": int(d["player"]), "card": str(cid),
                 "label": "Move %s to the mission zone" % game.cards[str(cid)].label()}
                for cid in d.get("options", [])]

    def _decide_zone_move(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        cid = str(action["card"])
        self.zone_entered_from_play(game, [cid])
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
        if not self._start_team_damage(game, d, self.zone_strength(game), "Myla") and not game.is_over:
            game.resume_defeat()


@register_rules
class Mission7Rules(LegacyRules):
    """Tales of Rebirth (confirmed from the cards). Pack P's pilgrims form a face-down
    pilgrim deck in the mission zone (``extra["pilgrim_deck"]``, top first). Start of
    turn: the top pilgrim is turned face up into the zone. When a card enters play, if a
    zone pilgrim has the same strength the player may banish that pilgrim (once per
    card). Pilgrims may never leave players' hands. Enemy defeated: cards equal to the
    zone's total strength go from the top of the reserve to the discard pile, then the
    zone goes to the discard pile and the enemy is banished; on exact damage one zone
    card may first be moved to the banished pile."""

    id = "legacy_m7"
    mission = 7
    uses_mission_zone = True

    def build_decks(self, game) -> None:
        super().build_decks(game)
        pilgrims = [Card.from_dict(d) for d in game.config.extra.get("pilgrims", [])]
        for c in pilgrims:
            if c.id in game.cards:
                raise ValueError("duplicate card id %s" % c.id)
            game.cards[c.id] = c
        game.extra["pilgrim_deck"] = [c.id for c in pilgrims]

    def hand_locked(self, game, card: Card) -> bool:
        return card.has("pilgrim")

    def zone_pilgrims(self, game) -> List[str]:
        return [cid for cid in game.mission_zone if game.cards[cid].has("pilgrim")]

    def on_turn_start(self, game) -> None:
        deck = game.extra.get("pilgrim_deck", [])
        if not deck:
            return
        cid = deck.pop(0)
        game.mission_zone.append(cid)
        game._event("zone_add", card=cid, zone=list(game.mission_zone), source="pilgrims")
        game._say("Start of turn: %s is turned face up in the mission zone (zone strength %d, %d left in the pilgrim deck)." % (
            game.cards[cid].label(), self.zone_strength(game), len(deck)))

    # --- a card entering play may banish a zone pilgrim of the same strength ---------------
    def on_cards_played(self, game, cards: Sequence[Card], player: Optional[int] = None) -> None:
        super().on_cards_played(game, cards, player)
        for c in cards:
            game.extra.setdefault("pilgrim_pending", []).append(c.id)

    def _strength_in_play(self, game, cid: str) -> int:
        """A card's strength as it entered play: a beast's equals its partner's (p.14), a
        2/5 has the value it was given, declared or forced by its kinfolk set (p.25)."""
        card = game.cards[cid]
        if not card.has("beast"):
            return self.in_play_strength(game, card)
        for play in game.plays:
            if cid in play.card_ids:
                others = [c for c in play.card_ids if not game.cards[c].has("beast")]
                return self.in_play_strength(game, game.cards[others[0]]) if others else 0
        return 0

    def _pending_entry_decision(self, game) -> Optional[Dict[str, Any]]:
        d = super()._pending_entry_decision(game)
        if d is not None:
            return d
        queue = game.extra.get("pilgrim_pending") or []
        while queue:
            cid = str(queue.pop(0))
            if cid not in game.cards:
                continue
            strength = self._strength_in_play(game, cid)
            matches = [p for p in self.zone_pilgrims(game) if self.strength(game.cards[p]) == strength]
            if not matches:
                continue
            game._say("%s matches %s in the mission zone: %s may banish one pilgrim." % (
                game.cards[cid].label(), " / ".join(game.cards[p].label() for p in matches),
                game.players[game.active].name))
            return {"kind": "pilgrim_banish", "player": game.active, "entering": cid, "options": matches}
        game.extra.pop("pilgrim_pending", None)
        return None

    def _actions_pilgrim_banish(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "pilgrim_banish", "player": player, "card": str(cid),
                 "label": "Banish %s" % game.cards[str(cid)].label()}
                for cid in d.get("options", []) if str(cid) in game.mission_zone]
        acts.append({"type": "pilgrim_skip", "player": player, "skip": True, "label": "Keep the pilgrims"})
        return acts

    def _decide_pilgrim_banish(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        entering = str(d.get("entering", ""))
        if action["type"] == "pilgrim_banish":
            cid = str(action["card"])
            if cid not in game.mission_zone or cid not in [str(c) for c in d.get("options", [])]:
                from ..engine import IllegalAction
                raise IllegalAction("%s is not a matching pilgrim in the mission zone." % cid)
            game.mission_zone.remove(cid)
            game.banish_cards([cid])
            game._event("pilgrim_banish", player=player, card=entering, pilgrim=cid, zone=list(game.mission_zone))
            game._say("%s banishes %s from the mission zone (matched by %s)." % (
                game.players[player].name, game.cards[cid].label(),
                game.cards[entering].label() if entering in game.cards else "the played card"))
        else:
            game._event("pilgrim_skip", player=player, card=entering)
            game._say("%s leaves the pilgrims in the mission zone." % game.players[player].name)
        self._entry_done(game, d)

    # --- enemy defeated -------------------------------------------------------------------
    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        return {"enemy_to": "banish", "played_to": "discard", "zone_to": "discard",
                "reserve_to_discard": self.zone_strength(game)}

    def before_defeat(self, game, exact: bool) -> Optional[Dict[str, Any]]:
        if exact and game.mission_zone:
            game._say("Exact kill: %s may move one mission zone card to the banished pile first." % (
                game.players[game.active].name))
            return {"kind": "zone_banish", "player": game.active, "options": list(game.mission_zone)}
        return None

    def _actions_zone_banish(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "zone_banish", "player": player, "card": str(cid),
                 "label": "Banish %s" % game.cards[str(cid)].label()}
                for cid in d.get("options", []) if str(cid) in game.mission_zone]
        acts.append({"type": "zone_banish_skip", "player": player, "skip": True, "label": "Banish nothing"})
        return acts

    def _decide_zone_banish(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        if action["type"] == "zone_banish":
            cid = str(action["card"])
            if cid not in game.mission_zone:
                from ..engine import IllegalAction
                raise IllegalAction("%s is not in the mission zone." % cid)
            game.mission_zone.remove(cid)
            game.banish_cards([cid])
            game._event("zone_banish", player=player, card=cid, zone=list(game.mission_zone))
            game._say("%s moves %s from the mission zone to the banished pile." % (
                game.players[player].name, game.cards[cid].label()))
        else:
            game._event("zone_banish_skip", player=player)
            game._say("%s banishes nothing from the mission zone." % game.players[player].name)
        game.resume_defeat()


@register_rules
class Mission8Rules(LegacyRules):
    """Winds of Chaos (confirmed from the cards). The pilgrim puppy starts in the mission
    zone and the other pilgrims are shuffled into the reserve as ordinary classless cards.
    Each enemy has additional strength equal to the combined strength of the non-pilgrim
    zone cards. Enemy defeated: banish the enemy; then the player may move cards in play
    to the zone one at a time, each exactly one strength higher than the zone's highest
    (the puppy is 1). When a 10 is moved the zone goes to the discard pile, the player
    banishes any discards they want, the rest is shuffled under the reserve, and no more
    cards may be moved for the rest of the mission. On exact damage any one discard pile
    card may go on top of the reserve (asked once the piles are final)."""

    id = "legacy_m8"
    mission = 8
    uses_mission_zone = True

    def attack_bonus(self, game) -> int:
        return sum(self.card_strength(game, game.cards[c]) for c in game.mission_zone if not game.cards[c].has("pilgrim"))

    def _in_play(self, game) -> List[str]:
        solo = game.n_players == 1 and self.solo_jester_mode(game) == "attack"
        return [c for p in game.plays for c in p.card_ids if not (solo and game.cards[c].is_jester)]

    def zone_highest(self, game) -> int:
        return max([self.card_strength(game, game.cards[c]) for c in game.mission_zone] or [0])

    def _build_options(self, game) -> List[str]:
        if game.extra.get("zone_filled"):
            return []
        want = self.zone_highest(game) + 1
        return [c for c in self._in_play(game) if self.card_strength(game, game.cards[c]) == want]

    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        return {"enemy_to": "banish", "played_to": "discard"}   # the zone stays

    def before_defeat(self, game, exact: bool) -> Optional[Dict[str, Any]]:
        options = self._build_options(game)
        if options:
            game._say("Enemy defeated: %s may move cards in play to the mission zone, one strength at a time (next: %d)." % (
                game.players[game.active].name, self.zone_highest(game) + 1))
            return {"kind": "zone_build", "player": game.active, "options": options}
        return None

    def _actions_zone_build(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "zone_build", "player": player, "card": str(cid),
                 "label": "Move %s to the mission zone" % game.cards[str(cid)].label()}
                for cid in d.get("options", [])]
        acts.append({"type": "zone_build_stop", "player": player, "skip": True, "label": "Stop"})
        return acts

    def _decide_zone_build(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        if action["type"] != "zone_build":
            game._event("zone_build_stop", player=player)
            game._say("%s moves nothing more to the mission zone." % game.players[player].name)
            d.pop("options", None)
            game.resume_defeat()
            return
        cid = str(action["card"])
        if cid not in self._build_options(game):
            from ..engine import IllegalAction
            raise IllegalAction("%s cannot go to the mission zone now." % cid)
        self.zone_entered_from_play(game, [cid])     # a 2/5 counts what it was declared as
        for play in game.plays:
            if cid in play.card_ids:
                play.card_ids.remove(cid)
                break
        game.mission_zone.append(cid)
        game._event("zone_build", player=player, card=cid, zone=list(game.mission_zone), bonus=self.attack_bonus(game))
        game._say("%s moves %s to the mission zone (enemy strength +%d)." % (
            game.players[player].name, game.cards[cid].label(), self.attack_bonus(game)))
        if self.strength(game.cards[cid]) == 10:
            self._zone_filled(game, d)
            return
        options = self._build_options(game)
        if not options:
            d.pop("options", None)
            game.resume_defeat()
            return
        d["options"] = options
        game._event("decide", **d)

    def _zone_filled(self, game, d: Dict[str, Any]) -> None:
        """Mission zone filled (confirmed): the zone goes to the discard pile, the player
        banishes any discards, the rest is shuffled under the reserve, no more moves."""
        zone = list(game.mission_zone)
        game.mission_zone = []
        game._discard_cards([game.cards[c] for c in zone])
        game.extra["zone_filled"] = True
        game._event("zone_cleared", cards=zone, to="discard")
        game._say("Mission zone filled! The zone (%d cards) goes to the discard pile; %s may banish any cards from the discard pile, the rest heals under the reserve deck." % (
            len(zone), game.players[int(d["player"])].name))
        d.pop("options", None)
        d["kind"] = "discard_banish"
        game._event("decide", **d)

    def _actions_discard_banish(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts: List[Dict[str, Any]] = []
        if game.discard:
            acts.append({"type": "discard_banish", "player": player, "pick_from": list(game.discard), "needs": None,
                         "max": len(game.discard), "label": "Banish the selected discards"})
        acts.append({"type": "discard_banish_skip", "player": player, "skip": True, "label": "Banish nothing"})
        return acts

    def _decide_discard_banish(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        ids = [str(c) for c in action.get("cards", [])] if action["type"] == "discard_banish" else []
        if len(set(ids)) != len(ids) or any(cid not in game.discard for cid in ids):
            from ..engine import IllegalAction
            raise IllegalAction("Choose distinct cards from the discard pile.")
        for cid in ids:
            game.discard.remove(cid)
            game.banish_cards([cid])
        healed = list(game.discard)
        game.rng.shuffle(healed)
        game.discard = []
        for x in healed:
            game.to_reserve(x, bottom=True)
        game._event("zone_filled", player=player, banished=ids, healed=len(healed))
        game._say("%s banishes %s; %d card%s are shuffled under the reserve deck. No more cards may be moved to the mission zone." % (
            game.players[player].name, " + ".join(game.cards[c].label() for c in ids) or "nothing",
            len(healed), "" if len(healed) == 1 else "s"))
        game.resume_defeat()

    # --- exact damage: a discard pile card on top of the reserve ---------------------------
    def after_cleanup(self, game, exact: bool, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if exact and game.discard:
            game._say("Exact kill: %s may put any one card from the discard pile on top of the reserve deck." % (
                game.players[game.active].name))
            return {"kind": "discard_pick", "player": game.active}
        return None

    def _actions_discard_pick(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts = [{"type": "discard_pick", "player": player, "card": cid,
                 "label": "Put %s on top of the reserve" % game.cards[cid].label()} for cid in game.discard]
        acts.append({"type": "discard_pick_skip", "player": player, "skip": True, "label": "Leave the discard pile"})
        return acts

    def _decide_discard_pick(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        if action["type"] == "discard_pick":
            cid = str(action["card"])
            if cid not in game.discard:
                from ..engine import IllegalAction
                raise IllegalAction("%s is not in the discard pile." % cid)
            game.discard.remove(cid)
            game.to_reserve(cid)
            game._event("discard_pick", player=player, card=cid)
            game._say("%s puts %s from the discard pile on top of the reserve deck." % (
                game.players[player].name, game.cards[cid].label()))
        else:
            game._event("discard_pick_skip", player=player)
            game._say("%s leaves the discard pile as it is." % game.players[player].name)
        game.resume_defeat()


@register_rules
class Mission9Rules(LegacyRules):
    """Hope From Ashes (confirmed from the cards). Setup: Gøran, the chosen beast, Jesters
    and mercenaries are set aside; the rest of the reserve is shuffled and dealt into
    three captured piles of ten (``extra["captured"]``, index 0 = the face-up top); the
    pilgrims and the set-aside cards are shuffled into the remaining reserve. End of turn
    (skipped on a kill): the player may banish a card from hand to move the top card of
    one pile to the discard pile, or every pile's top card goes to its bottom. Enemy
    defeated: banish the enemy; on exact damage one pile's top card may go on top of the
    reserve. Myla's immunity to bards and paladins can never be ignored."""

    id = "legacy_m9"
    mission = 9
    uses_mission_zone = True

    def build_decks(self, game) -> None:
        super().build_decks(game)
        extra = game.config.extra
        cap = extra.get("capture") or {}
        exempt = set(str(x) for x in cap.get("exempt", []))
        aside = [cid for cid in game.tavern if cid in exempt or game.cards[cid].is_jester]
        rest = [cid for cid in game.tavern if cid not in aside]
        game.rng.shuffle(rest)
        n_piles = int(cap.get("piles", 3))
        size = int(cap.get("size", 10))
        piles: List[List[str]] = [[] for _ in range(n_piles)]
        for i in range(min(n_piles * size, len(rest))):
            piles[i % n_piles].append(rest.pop(0))
        pilgrims = [Card.from_dict(d) for d in extra.get("pilgrims_in_reserve", [])]
        for c in pilgrims:
            if c.id in game.cards:
                raise ValueError("duplicate card id %s" % c.id)
            game.cards[c.id] = c
        reserve = rest + aside + [c.id for c in pilgrims]
        game.rng.shuffle(reserve)
        game.tavern = reserve
        game.extra["captured"] = piles

    def piles(self, game) -> List[List[str]]:
        return [list(p) for p in game.extra.get("captured", [])]

    def pile_tops(self, game) -> List[Optional[str]]:
        return [p[0] if p else None for p in game.extra.get("captured", [])]

    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        return {"enemy_to": "banish", "played_to": "discard"}

    # --- end of turn: rescue or rotate -------------------------------------------------------
    def on_turn_end(self, game) -> Optional[Dict[str, Any]]:
        if game.is_over or not any(game.extra.get("captured", [])):
            return None
        game._say("End of turn: %s may banish a card from hand to rescue a captured card, or the piles rotate." % (
            game.players[game.active].name))
        return {"kind": "pile_rescue", "player": game.active}

    def _actions_pile_rescue(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts: List[Dict[str, Any]] = []
        piles = game.extra.get("captured", [])
        for k, pile in enumerate(piles):
            if not pile:
                continue
            top = game.cards[pile[0]].label()
            for cid in self.unlocked_hand(game, player):
                acts.append({"type": "pile_rescue", "player": player, "pile": k, "card": cid,
                             "label": "Banish %s: rescue %s (pile %d)" % (game.cards[cid].label(), top, k + 1)})
        acts.append({"type": "pile_rotate", "player": player, "skip": True, "label": "Rotate the piles"})
        return acts

    def _decide_pile_rescue(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        from ..engine import IllegalAction
        player = int(d["player"])
        piles = game.extra.get("captured", [])
        if action["type"] == "pile_rescue":
            k = int(action["pile"])
            cid = str(action["card"])
            if not 0 <= k < len(piles) or not piles[k]:
                raise IllegalAction("That pile is empty.")
            if cid not in self.unlocked_hand(game, player):
                raise IllegalAction("Card %s cannot be banished from hand." % cid)
            game.players[player].hand.remove(cid)
            game.banish_cards([cid])
            rescued = piles[k].pop(0)
            game.discard.insert(0, rescued)
            game._event("pile_rescue", player=player, card=cid, rescued=rescued, pile=k,
                        tops=self.pile_tops(game))
            game._say("%s banishes %s and rescues %s from captured pile %d to the discard pile." % (
                game.players[player].name, game.cards[cid].label(), game.cards[rescued].label(), k + 1))
        else:
            for pile in piles:
                if len(pile) >= 2:
                    pile.append(pile.pop(0))
            game._event("pile_rotate", player=player, tops=self.pile_tops(game))
            game._say("%s banishes nothing: the top card of each captured pile goes to its bottom." % (
                game.players[player].name))
        game.resume_end_turn()

    # --- exact damage: a pile's top card on top of the reserve -------------------------------
    def before_defeat(self, game, exact: bool) -> Optional[Dict[str, Any]]:
        if exact and any(game.extra.get("captured", [])):
            game._say("Exact kill: %s may move the top card of one captured pile to the top of the reserve deck." % (
                game.players[game.active].name))
            return {"kind": "pile_to_reserve", "player": game.active}
        return None

    def _actions_pile_to_reserve(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        acts: List[Dict[str, Any]] = []
        for k, pile in enumerate(game.extra.get("captured", [])):
            if pile:
                acts.append({"type": "pile_to_reserve", "player": player, "pile": k,
                             "label": "%s (pile %d) on top of the reserve" % (game.cards[pile[0]].label(), k + 1)})
        acts.append({"type": "pile_to_reserve_skip", "player": player, "skip": True, "label": "Leave the piles"})
        return acts

    def _decide_pile_to_reserve(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        piles = game.extra.get("captured", [])
        if action["type"] == "pile_to_reserve":
            k = int(action["pile"])
            if not 0 <= k < len(piles) or not piles[k]:
                from ..engine import IllegalAction
                raise IllegalAction("That pile is empty.")
            cid = piles[k].pop(0)
            game.to_reserve(cid)
            game._event("pile_to_reserve", player=player, card=cid, pile=k, tops=self.pile_tops(game))
            game._say("%s moves %s from captured pile %d to the top of the reserve deck." % (
                game.players[player].name, game.cards[cid].label(), k + 1))
        else:
            game._event("pile_to_reserve_skip", player=player)
            game._say("%s leaves the captured piles alone." % game.players[player].name)
        game.resume_defeat()


@register_rules
class Mission10Rules(LegacyRules):
    """Pride to Fall (confirmed from the cards). The corrupted party members form the
    enemy deck, face up, 2 on top down to 9 (health five times the base strength, which
    the card data carries). Start of turn: the top card of the reserve deck goes into the
    mission zone; every enemy has additional strength equal to the zone's combined
    strength. Enemy class powers (a two-class enemy has both): warrior, double total
    strength (base plus zone, the paladin shields come off afterwards); paladin, the
    damage dealt to it is reduced by its base strength; cleric, at the end of each turn
    the top card of the discard pile goes into the zone; bard, at the end of each turn
    the current player must put a hand card into the zone if able. Enemy defeated: banish
    the zone and discard the enemy; on exact damage the zone goes to the discard pile
    instead. A defeated member drawn later plays as the corrupted party card it is."""

    id = "legacy_m10"
    mission = 10
    uses_mission_zone = True

    def discard_top_feeds_enemy(self, game) -> bool:
        return True     # a cleric enemy moves the top discard into the zone at the end of a turn

    def attack_bonus(self, game) -> int:
        return self.zone_strength(game)

    def attack_multiplier(self, game) -> int:
        return 2 if game.enemy is not None and "C" in game.enemy.suits else 1

    def damage_reduction(self, game) -> int:
        if game.enemy is not None and "S" in game.enemy.suits:
            return game.enemy.attack
        return 0

    def on_turn_start(self, game) -> Optional[Dict[str, Any]]:
        if not game.tavern:
            game._say("Start of turn: the reserve deck is empty, nothing goes into the mission zone.")
            return None
        cid = game.tavern.pop(0)
        game.mission_zone.append(cid)
        game._event("zone_add", card=cid, zone=list(game.mission_zone), source="reserve")
        game._say("Start of turn: %s goes from the reserve deck into the mission zone (enemy strength +%d)." % (
            game.cards[cid].label(), self.zone_strength(game)))
        return None

    def on_turn_end(self, game) -> Optional[Dict[str, Any]]:
        if game.is_over or game.enemy is None:
            return None
        if "H" in game.enemy.suits:
            if game.discard:
                cid = game.discard.pop(0)
                game.mission_zone.append(cid)
                game._event("zone_add", card=cid, zone=list(game.mission_zone), source="discard")
                game._say("End of turn (cleric): %s goes from the discard pile into the mission zone (enemy strength +%d)." % (
                    game.cards[cid].label(), self.zone_strength(game)))
            else:
                game._say("End of turn (cleric): the discard pile is empty, nothing goes into the mission zone.")
        if "D" in game.enemy.suits:
            if self.unlocked_hand(game, game.active):
                game._say("End of turn (bard): %s must put a card from hand into the mission zone." % (
                    game.players[game.active].name))
                return {"kind": "zone_feed", "player": game.active, "reason": "bard"}
            game._say("End of turn (bard): %s has no card to put into the mission zone." % game.players[game.active].name)
        return None

    def _actions_zone_feed(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        player = int(d["player"])
        return [{"type": "zone_feed", "player": player, "card": cid,
                 "label": "Put %s into the mission zone" % game.cards[cid].label()}
                for cid in self.unlocked_hand(game, player)]

    def _decide_zone_feed(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        player = int(d["player"])
        cid = str(action["card"])
        if cid not in self.unlocked_hand(game, player):
            from ..engine import IllegalAction
            raise IllegalAction("Card %s is not in hand." % cid)
        game.players[player].hand.remove(cid)
        game.mission_zone.append(cid)
        game._event("zone_feed", player=player, card=cid, zone=list(game.mission_zone), bonus=self.attack_bonus(game))
        game._say("%s puts %s into the mission zone (enemy strength +%d)." % (
            game.players[player].name, game.cards[cid].label(), self.attack_bonus(game)))
        self._decision_done(game, d)

    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        return {"enemy_to": "discard", "played_to": "discard", "zone_to": "discard" if exact else "banish"}


@register_rules
class Mission11Rules(LegacyRules):
    """Descent Into Darkness (confirmed from the cards). Gøran's four beasts form a
    face-down beast deck in the mission zone (``extra["beast_deck"]``, top first) with a
    face-up pile beside it (``extra["beasts_out"]``). Start of every turn (the first one
    included): reveal the top beast and apply its class: warrior, the top discard is
    banished; paladin, the top reserve card is discarded; cleric, the current player
    discards a hand card; bard, the current player banishes a hand card (an empty hand
    skips it). The beast then joins the face-up pile; when all four are out they are
    shuffled into a new deck. The Justicars (10/30) and the Corrupted Evergreen (20/90)
    have no class of their own: each is immune to the classes of the top cards of the
    discard and banished piles and gains their strengths (a beast or a classless card
    grants strength 0 and no immunity). Enemy defeated: banish the enemy; on exact damage
    no beast is revealed at the start of the next turn."""

    id = "legacy_m11"
    mission = 11
    uses_mission_zone = True

    def discard_top_feeds_enemy(self, game) -> bool:
        return True     # the enemies gain the top discard's strength and classes

    def banished_top_matters(self, game) -> bool:
        return True     # and the top banished card's

    def build_decks(self, game) -> None:
        super().build_decks(game)
        beasts = [Card.from_dict(d) for d in game.config.extra.get("beast_deck", [])]
        for c in beasts:
            if c.id in game.cards:
                raise ValueError("duplicate card id %s" % c.id)
            game.cards[c.id] = c
        game.extra["beast_deck"] = [c.id for c in beasts]
        game.extra["beasts_out"] = []

    def immune_suits(self, game) -> Tuple[str, ...]:
        base = list(super().immune_suits(game))
        if game.enemy is None:
            return tuple(base)
        for s in self.top_card_suits(game, game.discard, False) + self.top_card_suits(game, game.banished, True):
            if s not in base:
                base.append(s)
        return tuple(base)

    def attack_bonus(self, game) -> int:
        return self.top_card_strength(game, game.discard, False) + self.top_card_strength(game, game.banished, True)

    # --- start of turn: the beast deck ------------------------------------------------------
    def on_turn_start(self, game) -> Optional[Dict[str, Any]]:
        if game.extra.pop("skip_beast", False):
            game._event("beast_skip")
            game._say("Start of turn: no beast is revealed (the last enemy fell to exact damage).")
            return None
        deck = game.extra.get("beast_deck", [])
        if not deck:
            return None
        cid = deck.pop(0)
        game.extra.setdefault("beasts_out", []).append(cid)
        beast = game.cards[cid]
        suit = beast.suits[0] if beast.suits else ""
        game._event("beast_reveal", card=cid, suit=suit, player=game.active)
        game._say("Start of turn: %s (%s beast) is revealed." % (beast.name or beast.label(), CLASS_NAME.get(suit, suit)))
        who = game.players[game.active].name
        if suit == "C":
            if game.discard:
                lost = game.discard.pop(0)
                done = game.banish_cards([lost])
                game._event("beast_effect", card=cid, suit=suit, moved=lost, to="banished")
                game._say("Warrior beast: %s, the top card of the discard pile, is banished." % game.cards[lost].label()
                          if done else "Warrior beast: %s leaves the discard pile." % game.cards[lost].label())
            else:
                game._say("Warrior beast: the discard pile is empty, nothing is banished.")
        elif suit == "S":
            if game.tavern:
                lost = game.tavern.pop(0)
                game.discard.insert(0, lost)
                game._event("beast_effect", card=cid, suit=suit, moved=lost, to="discard")
                game._say("Paladin beast: %s, the top card of the reserve deck, is discarded." % game.cards[lost].label())
            else:
                game._say("Paladin beast: the reserve deck is empty, nothing is discarded.")
        elif suit in ("H", "D"):
            if self.unlocked_hand(game, game.active):
                kind = "beast_discard" if suit == "H" else "beast_banish"
                game._say("%s beast: %s must %s a card from hand." % (
                    CLASS_NAME[suit], who, "discard" if suit == "H" else "banish"))
                return {"kind": kind, "player": game.active, "beast": cid}
            game._say("%s beast: %s has no card in hand, nothing happens." % (CLASS_NAME[suit], who))
        self._beast_effect_done(game)
        return None

    def _beast_effect_done(self, game) -> None:
        deck = game.extra.get("beast_deck", [])
        out = game.extra.get("beasts_out", [])
        if not deck and len(out) >= 4:
            reformed = list(out)
            game.rng.shuffle(reformed)
            game.extra["beast_deck"] = reformed
            game.extra["beasts_out"] = []
            game._event("beast_reshuffle", count=len(reformed))
            game._say("All four beasts are out: they are shuffled into a new beast deck.")

    def _hand_card_actions(self, game, d: Dict[str, Any], verb: str) -> List[Dict[str, Any]]:
        player = int(d["player"])
        return [{"type": str(d["kind"]), "player": player, "card": cid,
                 "label": "%s %s" % (verb, game.cards[cid].label())} for cid in self.unlocked_hand(game, player)]

    def _actions_beast_discard(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._hand_card_actions(game, d, "Discard")

    def _actions_beast_banish(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._hand_card_actions(game, d, "Banish")

    def _decide_beast_discard(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        self._beast_hand_card(game, d, action, banish=False)

    def _decide_beast_banish(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        self._beast_hand_card(game, d, action, banish=True)

    def _beast_hand_card(self, game, d: Dict[str, Any], action: Dict[str, Any], banish: bool) -> None:
        player = int(d["player"])
        cid = str(action["card"])
        if cid not in self.unlocked_hand(game, player):
            from ..engine import IllegalAction
            raise IllegalAction("Card %s is not in hand." % cid)
        game.players[player].hand.remove(cid)
        if banish:
            game.banish_cards([cid])
        else:
            game._discard_cards([game.cards[cid]])
        game._event("beast_effect", card=str(d.get("beast", "")), suit="D" if banish else "H", moved=cid,
                    to="banished" if banish else "discard", player=player)
        game._say("%s %s %s (%s beast)." % (game.players[player].name, "banishes" if banish else "discards",
                                           game.cards[cid].label(), "Bard" if banish else "Cleric"))
        self._beast_effect_done(game)
        self._decision_done(game, d)

    # --- enemy defeated ------------------------------------------------------------------------
    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        return {"enemy_to": "banish", "played_to": "discard"}

    def after_cleanup(self, game, exact: bool, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if exact:
            game.extra["skip_beast"] = True
            game._say("Exact kill: no beast will be revealed at the start of the next turn.")
        return None


@register_rules
class Mission12Rules(LegacyRules):
    """Decay to Growth (confirmed from the cards). Four corrupted Queens (15/30), four
    corrupted Kings (20/40), then the High Arcana (25/120, no class, corrupted). Start of
    turn: the top card of the banished pile goes into the mission zone (skipped after an
    exact kill); the zone adds its combined strength to the enemy and grants immunity to
    its classes. Enemy defeated: banish the zone in the order the player chooses, then the
    enemy, then the whole discard pile in its order. Corrupted cards (the royals, the
    Arcana) never enter the reserve deck: they go to the bottom of the banished pile
    instead. The restored Evergreen Mother relic keeps restored cards out of the banished
    pile (they go under the reserve deck), see ``LegacyRules.banish_redirect``."""

    id = "legacy_m12"
    mission = 12
    uses_mission_zone = True

    def banished_top_matters(self, game) -> bool:
        return True     # the top banished card enters the zone at the start of the next turn

    def attack_bonus(self, game) -> int:
        return self.zone_strength(game)

    def immune_suits(self, game) -> Tuple[str, ...]:
        base = list(super().immune_suits(game))
        if game.enemy is None:
            return tuple(base)
        for s in self.zone_suits(game):
            if s not in base:
                base.append(s)
        return tuple(base)

    def reserve_redirect(self, game, card: Card) -> Optional[str]:
        return "banished_bottom" if card.has("corrupted") else None

    def on_turn_start(self, game) -> Optional[Dict[str, Any]]:
        if game.extra.pop("skip_zone", False):
            game._event("zone_skip")
            game._say("Start of turn: nothing goes into the mission zone (the last enemy fell to exact damage).")
            return None
        if not game.banished:
            game._say("Start of turn: the banished pile is empty, nothing goes into the mission zone.")
            return None
        cid = game.banished.pop()
        game.mission_zone.append(cid)
        game._event("zone_add", card=cid, zone=list(game.mission_zone), source="banished")
        game._say("Start of turn: %s leaves the banished pile for the mission zone (enemy strength +%d%s)." % (
            game.cards[cid].label(), self.zone_strength(game),
            ", immune to " + " / ".join(CLASS_NAME.get(s, s) + "s" for s in self.zone_suits(game)) if self.zone_suits(game) else ""))
        return None

    def defeat_plan(self, game, exact: bool) -> Dict[str, Any]:
        return {"enemy_to": "banish", "played_to": "discard", "zone_to": "banish", "zone_first": True,
                "discard_to": "banish"}

    def before_defeat(self, game, exact: bool) -> Optional[Dict[str, Any]]:
        if len(game.mission_zone) >= 2:
            game._say("Enemy defeated: %s chooses the order in which the mission zone is banished." % (
                game.players[game.active].name))
            return {"kind": "banish_order", "player": game.active}
        return None

    def _actions_banish_order(self, game, d: Dict[str, Any]) -> List[Dict[str, Any]]:
        zone = list(game.mission_zone)
        return [{"type": "banish_order", "player": int(d["player"]), "pick_from": zone, "needs": len(zone),
                 "ordered": True, "label": "Banish the mission zone in this order (the last ends on top)"}]

    def _decide_banish_order(self, game, d: Dict[str, Any], action: Dict[str, Any]) -> None:
        from ..engine import IllegalAction
        ids = [str(c) for c in action.get("cards", [])]
        if sorted(ids) != sorted(game.mission_zone):
            raise IllegalAction("Name every mission zone card exactly once.")
        game.mission_zone = ids
        game._event("banish_order", player=int(d["player"]), cards=ids)
        game._say("%s banishes the mission zone in the order %s (%s on top)." % (
            game.players[int(d["player"])].name, ", ".join(game.cards[c].label() for c in ids), game.cards[ids[-1]].label()))
        self._decision_done(game, d)

    def after_cleanup(self, game, exact: bool, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if exact:
            game.extra["skip_zone"] = True
            game._say("Exact kill: the banished pile stays put at the start of the next turn.")
        return None
