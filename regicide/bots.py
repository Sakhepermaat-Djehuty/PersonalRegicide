"""Heuristic players.

Used for (a) simulation tests that play thousands of games, (b) the "autoplay" /
"AI teammate" features, and (c) hints in the UI (suggested discard). Bots see every
hand; that is fine for testing and for teammates the human explicitly asked for.
"""
from __future__ import annotations

import copy
import itertools
from typing import Callable, Dict, List, Optional, Sequence

from .cards import CLUBS, DIAMONDS, HEARTS, SPADES
from .engine import (PHASE_CHOOSE_NEXT, PHASE_DECIDE, PHASE_LOST, PHASE_PLAY, PHASE_SUFFER, PHASE_WON,
                     Game)


# --------------------------------------------------------------------------- helpers
def min_waste_discard(game: Game, player: Optional[int] = None) -> List[str]:
    """Smallest-total set of hand cards covering the pending damage, in a legal order.

    Ties: fewer cards first, then keep high-value cards in hand. Returns the whole hand
    if nothing covers the damage (the caller will lose anyway). The cards are listed in
    the order they are discarded, smallest first and the largest last: Legacy pays damage
    one card at a time and never past the damage (rulebook p.18), which this order always
    respects since no card of the set can be left out.
    """
    need = game.pending_damage
    hand = game.payable_hand(player)
    if need <= 0:
        return []
    n = len(hand)
    best: Optional[tuple] = None
    best_ids: List[str] = []
    if n <= 12:
        for mask in range(1, 1 << n):
            total = 0
            count = 0
            kept = 0
            for i in range(n):
                if mask & (1 << i):
                    total += hand[i].defence_value
                    count += 1
                else:
                    kept += hand[i].value
            if total < need:
                continue
            key = (total, count, -kept)
            if best is None or key < best:
                best = key
                best_ids = [hand[i].id for i in range(n) if mask & (1 << i)]
        if best is None:
            return [c.id for c in hand]
    else:
        # Large Legacy hands: the largest cards until the smallest single card covers what
        # is left. No card of the result can be dropped (the last one was the smallest to
        # cover the rest, and every earlier one is at least as large as it).
        pool = sorted(hand, key=lambda c: -c.defence_value)
        if sum(c.defence_value for c in pool) < need:
            return [c.id for c in hand]
        left = need
        while left > 0:
            covering = [c for c in pool if c.defence_value >= left]
            pick = min(covering, key=lambda c: (c.defence_value, c.value)) if covering else pool[0]
            pool.remove(pick)
            best_ids.append(pick.id)
            left -= pick.defence_value
    return payment_order(game, best_ids)


def payment_order(game: Game, ids: Sequence[str]) -> List[str]:
    """The cards of a damage payment in discard order: smallest first, the largest last."""
    return sorted(ids, key=lambda c: (game.cards[c].defence_value, game.cards[c].value))


def sequential_payment_ok(game: Game, ids: Sequence[str]) -> bool:
    """Could these cards, discarded one at a time in this order, pay the pending damage
    without discarding past it (rulebook p.18)?"""
    need = game.pending_damage
    vals = [game.cards[c].defence_value for c in ids]
    return bool(vals) and sum(vals) >= need and sum(vals[:-1]) < need


# --------------------------------------------------------------------------- policies
def random_policy(game: Game, rng) -> dict:
    acts = [a for a in game.legal_actions() if a["type"] != "special"]
    if game.phase == PHASE_SUFFER:
        if game.hand_defence_value() < game.pending_damage:
            if game.can_use_solo_jester():
                return {"type": "solo_jester"}  # the only way out (else the game would be lost)
            return {"type": "suffer", "cards": [c.id for c in game.hand()]}  # feign death
        # random legal cover: shuffle and take until covered
        hand = list(game.payable_hand())
        rng.shuffle(hand)
        ids: List[str] = []
        total = 0
        for c in hand:
            if total >= game.pending_damage:
                break
            ids.append(c.id)
            total += c.defence_value
        return {"type": "suffer", "cards": ids}
    act = rng.choice(acts)
    if "needs" in act:
        return randomize_action(game, act, rng)
    return act


def randomize_action(game: Game, template: dict, rng) -> dict:
    """Fill in a template action (one with ``needs``) at random: the Druid's four
    destinations, a Chanter's or mission 8's discards (any number when ``needs`` is None)."""
    pool = [str(c) for c in template.get("pick_from", [])]
    needs = template.get("needs")
    if template["type"] == "druid_assign":
        k = min(int(needs or 0), len(pool))
        cards = rng.sample(pool, k)
        slots = rng.sample(list(template.get("slots") or ("banish", "hand", "top", "bottom")), k)
        act = {"type": "druid_assign", "player": template.get("player")}
        for slot, cid in zip(slots, cards):
            act[slot] = cid
        return act
    if needs is None:
        k = rng.randint(0, len(pool))
    else:
        k = min(int(needs), len(pool))
    return {"type": template["type"], "player": template.get("player"), "cards": rng.sample(pool, k)}


def evaluate(game: Game) -> float:
    """Material evaluation of a position from the players' point of view."""
    if game.phase == PHASE_WON:
        return 100000.0
    if game.phase == PHASE_LOST:
        return -100000.0
    score = 1000.0 * game.enemies_defeated
    e = game.enemy
    if e is not None:
        score += 2.0 * (e.max_hp - e.hp)
        score += 1.5 * min(game.shield, e.attack)
    for i in range(game.n_players):
        hand = game.hand(i)
        score += 3.0 * len(hand) + 0.6 * sum(c.value for c in hand)
    score += 0.4 * len(game.tavern)
    score += 12.0 * game.solo_jesters
    return score


def simple_decision(g: Game) -> Optional[dict]:
    """A cheap, lookahead-free choice for the pending decision (used inside simulations
    and as the fallback of ``decision_policy``): decline when a "do nothing" option exists
    (Kinfolk Flute, Scarlet Whistle, Azure Emblem); a mage's mandatory pick and a reaver's
    pick take the strongest card; a reaver reveals one card; the order a mage's unchosen or
    a reaver's revealed cards go to their pile ends with the card that weakens the enemy
    most where the top feeds it, the strongest where only the solo Scarlet Whistle reads it
    (``pile_order_choice``; ``top_card_choice`` for the top-card questions of older saved
    games); the card moved to the zone
    (mission 6) is the weakest, the rescued zone card the strongest; a Wild Animal and a 2/5
    declare as ``declare_class_choice`` / ``declare_value_choice`` say; Myla's team damage
    is paid with the cheapest cover over every hand. The Druid keeps the strongest dealt
    cards (hand, top, bottom) and banishes the weakest or a Jester / corrupted / locked
    card; the Chanter fills the attacker's hand and discards the lowest cards; the
    Evergreen Mother takes the discard pile (solo, unless the empty reserve banishes
    nothing) or the lowest card (another hand); mission 7 banishes matching pilgrims and the strongest zone card on an
    exact kill; mission 8 builds the zone (pilgrims first), banishes Jesters, pilgrims and
    the lowest discards up to five and puts the strongest discard back on the reserve;
    mission 9 rescues when a cheap hand card buys a clearly better one, else rotates."""
    acts = g.legal_actions()
    if not acts:
        return None
    kind = (g.decision or {}).get("kind")
    value = lambda a: g.cards[a["card"]].value  # noqa: E731
    special = _mission_decision(g, kind, acts)
    if special is not None:
        return special
    skip = [a for a in acts if a.get("skip")]
    if skip:
        return skip[0]
    if kind in ("mage_peek", "reaver_pick"):
        return max(acts, key=value)
    if kind == "reaver_count":
        return min(acts, key=lambda a: int(a.get("count", 1)))
    if kind in ("discard_order", "reaver_order"):
        return pile_order_choice(g, acts)
    if kind in ("cleanup_top", "banish_top", "discard_top"):
        return top_card_choice(g, acts)
    if kind == "zone_move":
        return min(acts, key=value)
    if kind == "zone_rescue":
        return max(acts, key=value)
    if kind == "team_discard":
        return team_discard_choice(g, acts)
    return acts[0]


def _top_feeds_enemy(g: Game, kind: Optional[str]) -> bool:
    """Does the top of the pile this decision fills feed the enemy (the banished pile
    wherever it is asked; the discard pile in missions 4, 10, 11 and Evergreen banes), as
    opposed to only the solo Scarlet Whistle reading it?"""
    return (kind in ("banish_top", "reaver_order")
            or bool(getattr(g.rules, "discard_top_feeds_enemy", lambda game: False)(g)))


def _top_key(g: Game, kind: Optional[str]) -> Callable[[str], tuple]:
    """Rank card ids for the top of a pile, the best last: where the top feeds the enemy
    the one that weakens it least goes first (strong class cards) and a Jester, a
    classless or the weakest card last; where only the solo Whistle reads it, the
    strongest last."""
    strength = getattr(g.rules, "strength", lambda c: c.value)
    if _top_feeds_enemy(g, kind):
        return lambda c: (-strength(g.cards[c]), 0 if g.cards[c].suits else 1)
    return lambda c: (strength(g.cards[c]), g.cards[c].value)


def pile_order_choice(g: Game, acts: List[dict]) -> dict:
    """The full order of a mage's unchosen cards (``discard_order``) or a reaver's revealed
    cards (``reaver_order``): the card ``top_card_choice`` would put on top is named last,
    the others before it in the same ranking (``_top_key``)."""
    kind = (g.decision or {}).get("kind")
    t = [a for a in acts if "needs" in a]
    if not t:
        return acts[0]
    pool = sorted((str(c) for c in t[0]["pick_from"]), key=_top_key(g, kind))
    return {"type": t[0]["type"], "player": t[0]["player"], "cards": pool}


def top_card_choice(g: Game, acts: List[dict]) -> dict:
    """Which card ends on top of a pile, for decisions of games saved while the app asked
    only for the top card (clean-up, a mage's unchosen cards, a reaver's or a mage attack's
    banish): the best card by ``_top_key``."""
    kind = (g.decision or {}).get("kind")
    cards = [a for a in acts if a.get("card")]
    if not cards:
        return acts[0]
    key = _top_key(g, kind)
    return max(cards, key=lambda a: key(a["card"]))


def declare_class_choice(g: Game, acts: List[dict]) -> dict:
    """A Wild Animal's class: one the enemy is not immune to, a warrior when doubling the
    attack could kill, else a bard when the hand is short of the limit, else a cleric,
    else a paladin."""
    d = g.decision or {}
    by = dict((str(a.get("option")), a) for a in acts if a.get("option"))
    play = None
    for p in g.plays:
        if str(d.get("card")) in p.card_ids:
            play = p
    cards = [g.cards[c] for c in play.card_ids] if play is not None else []
    allowed = [s for s in ("C", "D", "H", "S") if s in by and not g.immune(s, cards)]
    enemy = g.enemy
    value = play.value if play is not None else 1
    if "C" in allowed and enemy is not None and value * 2 >= enemy.hp:
        return by["C"]
    player = int(d.get("player", g.active))
    if "D" in allowed and len(g.players[player].hand) < g.config.max_hand and g.tavern:
        return by["D"]
    for s in ("H", "S", "C", "D"):
        if s in allowed:
            return by[s]
    return by.get("C", acts[0])


def declare_value_choice(g: Game, acts: List[dict]) -> dict:
    """2/5s whose strength is a free choice (alone, with a companion or a beast, two 2/5s
    together; one value for all of them): 5, the stronger attack, unless declaring 2 kills
    the enemy exactly (the enemy then goes to the reserve instead of the discard pile)."""
    by = dict((str(a.get("option")), a) for a in acts if a.get("option"))
    if "2" in by:
        sim = copy.deepcopy(g)
        apply_action(sim, by["2"])
        _settle_decisions(sim)
        if any(ev["t"] == "defeat" and ev.get("exact") for ev in sim.last_events):
            return by["2"]
        if sim.phase == PHASE_DECIDE and (sim.decision or {}).get("exact") and \
                (sim.decision or {}).get("resume") in ("defeat", "defeat_tail"):
            return by["2"]
    return by.get("5", acts[0])


NEW_KINDS = ("druid_assign", "chanter_declare", "chanter_discard", "mother_choice", "mother_banish",
             "pilgrim_banish", "zone_banish", "zone_build", "discard_banish", "discard_pick",
             "pile_rescue", "pile_to_reserve",
             # missions 10 to 12
             "zone_feed", "beast_discard", "beast_banish", "banish_order",
             # Evergreen locations, banes and boons
             "zone_order", "zone_discard", "attack_discard", "zone_sibling", "zone_match", "close_call",
             "precision_strike", "restored_arrows", "poison",
             # declarations (rulebook p.25)
             "declare_class", "declare_value")


def _keep_key(g: Game, cid: str) -> tuple:
    """How much a bot wants to keep a card: bad cards first (lowest), then by strength."""
    c = g.cards[cid]
    return (0 if _bad_card(g, cid) else 1, c.value)


def _good_pick(g: Game, acts: List[dict]) -> Optional[dict]:
    """The strongest card option that is not a Jester, corrupted or locked, else None."""
    cards = [a for a in acts if a.get("card") and not a.get("skip")]
    good = [a for a in cards if not _bad_card(g, a["card"])]
    if good:
        return max(good, key=lambda a: g.cards[a["card"]].value)
    return None


def _bad_card(g: Game, cid: str) -> bool:
    """A card worth banishing rather than keeping: a Jester, a corrupted card or one that
    could never leave the hand (mission 7's pilgrims)."""
    c = g.cards[cid]
    return c.is_jester or c.has("corrupted") or c.has("pilgrim") or g.hand_locked(cid)


def _mission_decision(g: Game, kind: Optional[str], acts: List[dict]) -> Optional[dict]:
    """``simple_decision`` for the decision kinds of the Druid, the Chanter, the Evergreen
    Mother and missions 7 to 9 (see there)."""
    if kind not in NEW_KINDS:
        return None
    value = lambda a: g.cards[a["card"]].value  # noqa: E731
    if kind == "druid_assign":
        return druid_bot_action(g, acts[0])
    if kind == "chanter_declare":
        room = max(0, g.config.max_hand - len(g.active_player.hand))
        counts = [int(a["count"]) for a in acts]
        return next(a for a in acts if int(a["count"]) == min(room, max(counts)))
    if kind == "chanter_discard":
        t = acts[0]
        lowest = sorted(t["pick_from"], key=lambda c: (g.cards[c].defence_value, g.cards[c].value))
        return {"type": "chanter_discard", "player": t["player"], "cards": lowest[:int(t["needs"])]}
    if kind == "declare_class":
        return declare_class_choice(g, acts)
    if kind == "declare_value":
        return declare_value_choice(g, acts)
    if kind == "mother_choice":
        # an empty reserve banishes nothing: better than losing the top discard
        want = "reserve" if not g.tavern else "discard"
        for a in acts:
            if a.get("option") == want:
                return a
        return acts[0]
    if kind == "mother_banish":
        return min(acts, key=lambda a: (0 if _bad_card(g, a["card"]) else 1, value(a)))
    if kind == "pilgrim_banish":
        cards = [a for a in acts if a.get("card")]
        return max(cards, key=value) if cards else acts[0]
    if kind == "zone_banish":
        cards = [a for a in acts if a.get("card")]
        return max(cards, key=value) if cards else acts[0]
    if kind == "zone_build":
        cards = [a for a in acts if a.get("card")]
        if not cards:
            return acts[0]
        pilgrims = [a for a in cards if g.cards[a["card"]].has("pilgrim")]
        return (pilgrims or cards)[0]
    if kind == "discard_banish":
        t = [a for a in acts if "needs" in a]
        if not t:
            return acts[0]
        pool = list(t[0]["pick_from"])
        bad = [c for c in pool if g.cards[c].is_jester or g.cards[c].has("pilgrim")]
        rest = sorted([c for c in pool if c not in bad], key=lambda c: g.cards[c].value)
        picks = (bad + rest)[:5]
        if not picks:
            return [a for a in acts if a.get("skip")][0]
        return {"type": "discard_banish", "player": t[0]["player"], "cards": picks}
    if kind == "discard_pick":
        cards = [a for a in acts if a.get("card") and not g.cards[a["card"]].has("pilgrim") and not g.cards[a["card"]].is_jester]
        if cards:
            return max(cards, key=value)
        return [a for a in acts if a.get("skip")][0]
    if kind == "pile_rescue":
        rescues = [a for a in acts if a["type"] == "pile_rescue"]
        rotate = [a for a in acts if a.get("skip")][0]
        if not rescues or len(g.players[int(rescues[0]["player"])].hand) < 3:
            return rotate
        piles = g.extra.get("captured", [])

        def gain(a):
            top = g.cards[piles[int(a["pile"])][0]].value
            return top - g.cards[a["card"]].value
        best = max(rescues, key=lambda a: (gain(a), -value(a)))
        return best if gain(best) >= 3 else rotate
    if kind == "pile_to_reserve":
        piles = g.extra.get("captured", [])
        moves = [a for a in acts if a["type"] == "pile_to_reserve"]
        if moves:
            return max(moves, key=lambda a: g.cards[piles[int(a["pile"])][0]].value)
        return acts[0]
    # --- missions 10 to 12 ------------------------------------------------------------------
    if kind in ("zone_feed", "beast_discard", "beast_banish", "attack_discard"):
        # the cheapest card leaves the hand: a Jester, a corrupted or locked card first
        cards = [a for a in acts if a.get("card")]
        return min(cards, key=lambda a: _keep_key(g, a["card"])) if cards else acts[0]
    if kind in ("banish_order", "zone_order"):
        t = [a for a in acts if "needs" in a]
        if not t:
            return acts[0]
        pool = list(t[0]["pick_from"])
        if kind == "banish_order":
            # the last card ends on top and feeds the next mission zone: a classless or weak
            # card there, the strong class cards underneath
            pool.sort(key=lambda c: (1 if g.cards[c].suits else 0, g.cards[c].value), reverse=True)
        return {"type": kind, "player": t[0]["player"], "cards": pool}
    # --- Evergreen --------------------------------------------------------------------------
    if kind == "zone_discard":
        cards = [a for a in acts if a.get("card")]
        return max(cards, key=value) if cards else acts[0]
    if kind in ("zone_sibling", "zone_match"):
        cards = [a for a in acts if a.get("card")]
        return max(cards, key=value) if cards else acts[0]
    if kind in ("close_call", "precision_strike"):
        best = _good_pick(g, acts)
        if best is not None:
            return best
        cards = [a for a in acts if a.get("card")]
        return cards[0] if cards else acts[0]
    if kind == "restored_arrows":
        best = _good_pick(g, acts)
        if best is not None and not g.cards[best["card"]].has("pilgrim"):
            return best
        return [a for a in acts if a.get("skip")][0]
    if kind == "poison":
        cards = [a for a in acts if a.get("card")]
        skip = [a for a in acts if a.get("skip")]
        if cards and len(g.players[int(cards[0]["player"])].hand) >= 3:
            return min(cards, key=lambda a: _keep_key(g, a["card"]))
        return skip[0] if skip else acts[0]
    return None


def druid_bot_action(g: Game, template: dict) -> dict:
    """Fill the Druid's template: the strongest dealt card to hand, the next on top of the
    reserve, the next under it and the weakest banished; a Jester, corrupted or locked
    card is banished first. With fewer than four cards the destinations are taken in
    the order hand, top, bottom, banish (banish first for a bad card)."""
    pool = [str(c) for c in template.get("pick_from", [])]
    k = min(int(template.get("needs") or 0), len(pool))
    bad = sorted([c for c in pool if _bad_card(g, c)], key=lambda c: g.cards[c].value)
    good = sorted([c for c in pool if not _bad_card(g, c)], key=lambda c: -g.cards[c].value)
    act = {"type": "druid_assign", "player": template.get("player")}
    slots = ["hand", "top", "bottom", "banish"]
    if bad and k:
        act["banish"] = bad.pop(0)
        slots.remove("banish")
        k -= 1
    picks = (good + bad)[:k]
    if len(picks) == 4:
        order = ["hand", "top", "bottom", "banish"]
    else:
        order = slots[:len(picks)]
    for slot, cid in zip(order, picks):
        act[slot] = cid
    return act


def team_discard_choice(g: Game, acts: List[dict]) -> dict:
    """Mission 6: the next card any player discards for Myla's team damage, aiming at the
    cheapest cover overall: the smallest single card that covers what is left, else the
    largest card available (then the rest is covered next time round)."""
    d = g.decision or {}
    remaining = int(d.get("damage", 0)) - int(d.get("paid", 0))
    worth = lambda a: g.cards[a["card"]].defence_value  # noqa: E731
    covering = [a for a in acts if worth(a) >= remaining]
    if covering:
        return min(covering, key=lambda a: (worth(a), g.cards[a["card"]].value))
    return max(acts, key=lambda a: (worth(a), -g.cards[a["card"]].value))


def _settle_decisions(g: Game) -> None:
    """Finish the decisions a simulated action runs into with ``simple_decision``."""
    steps = 0
    while g.phase == PHASE_DECIDE and steps < 100:
        steps += 1
        act = simple_decision(g)
        if act is None:
            break
        apply_action(g, act)


def _pay_cheapest(g: Game, actor: int) -> None:
    """If ``actor`` must suffer damage now, pay it with the cheapest cover (a solo Jester
    refresh first when the hand cannot cover it)."""
    if g.phase == PHASE_SUFFER and g.active == actor:
        if g.hand_defence_value() >= g.pending_damage:
            g.suffer(min_waste_discard(g))
        elif g.can_use_solo_jester():
            g.use_solo_jester()
            if g.phase == PHASE_SUFFER and g.hand_defence_value() >= g.pending_damage:
                g.suffer(min_waste_discard(g))


def _simulate_turn(game: Game, action: dict) -> Game:
    """Apply an action on a copy and, if damage follows, pay it with the cheapest cover.

    A play that pauses for other players' decisions (Kinfolk Flute, Azure Emblem) is
    forecast as if they all declined; a mage peek as if the strongest eligible card were
    added."""
    g = copy.deepcopy(game)
    apply_action(g, action)
    _settle_decisions(g)
    _pay_cheapest(g, game.active)
    return g


def _mage_pick_key(game: Game, act: dict) -> tuple:
    """Rank a mage pick by its one-ply outcome: an exact kill first, then any kill, then
    the damage dealt, then the material evaluation, then the card's own strength."""
    g = copy.deepcopy(game)
    apply_action(g, act)
    _settle_decisions(g)
    # The resolution ends in the last decision applied, whose events are still in place.
    exact = any(ev["t"] == "defeat" and ev.get("exact") for ev in g.last_events)
    damage = max([int(ev["amount"]) for ev in g.last_events if ev["t"] == "damage"] or [0])
    defeated = g.enemies_defeated > game.enemies_defeated
    _pay_cheapest(g, game.active)
    return (1 if exact else 0, 1 if defeated else 0, damage, evaluate(g), game.cards[act["card"]].value)


def greedy_policy(game: Game, rng=None) -> dict:
    """One-turn lookahead with a material evaluation. Plays every seat the same way."""
    if game.phase == PHASE_SUFFER:
        if game.hand_defence_value() < game.pending_damage:
            if game.can_use_solo_jester():
                return {"type": "solo_jester"}
            return {"type": "suffer", "cards": [c.id for c in game.hand()]}  # feign death (else lost already)
        if game.can_use_solo_jester():
            # Refreshing before paying is worth it when the hand would be gutted.
            after = _simulate_turn(game, {"type": "suffer", "cards": min_waste_discard(game)})
            via_jester = _simulate_turn(game, {"type": "solo_jester"})
            if evaluate(via_jester) > evaluate(after) + 6.0:
                return {"type": "solo_jester"}
        return {"type": "suffer", "cards": min_waste_discard(game)}
    if game.phase == PHASE_CHOOSE_NEXT:
        choices = [a["player"] for a in game.legal_actions() if a["type"] == "choose_next"]
        return {"type": "choose_next",
                "player": max(choices, key=lambda i: sum(c.value for c in game.hand(i)))}
    if game.phase == PHASE_DECIDE:
        return decision_policy(game)
    if game.phase != PHASE_PLAY:
        raise RuntimeError("game over")
    candidates: List[dict] = [a for a in game.legal_actions() if a["type"] != "suffer"]
    best: Optional[dict] = None
    best_score = None
    for act in candidates:
        g = _simulate_turn(game, act)
        score = evaluate(g)
        if act["type"] == "solo_jester":
            score -= 4.0  # keep the powers for emergencies unless clearly better
        if act["type"] == "yield":
            score -= 2.0
        if act["type"] == "special":
            score -= 1.0  # relic bookkeeping is rarely urgent
        if best_score is None or score > best_score:
            best_score = score
            best = act
    if best is None:
        raise RuntimeError("no legal action")
    return best


def decision_policy(game: Game) -> dict:
    """Kinfolk Flute, Scarlet Whistle and the Azure Emblem's placing: give cards to the
    attack only when that finishes the enemy.

    Among the additions that defeat the enemy, prefer an exact kill (the enemy joins the
    tavern deck), then the fewest / cheapest cards; otherwise keep the cards and pass. A
    mage's pick is mandatory: take the revealed card whose one-ply outcome ranks best
    (``_mage_pick_key``); with nothing eligible the only option is to add nothing. The
    Emblem's solo keep takes whichever option (a kept card or none) evaluates best. The
    reaver reveals one card and adds the strongest; the pile orders and the mission
    choices (zone move, zone rescue, team damage) follow ``simple_decision``."""
    acts = game.legal_actions()
    skip = [a for a in acts if a.get("skip")]
    kind = (game.decision or {}).get("kind")
    picks = [a for a in acts if a["type"] == "mage_pick"]
    if picks:
        return max(picks, key=lambda a: _mage_pick_key(game, a))
    if kind == "emblem_keep":
        return max(acts, key=lambda a: (evaluate(_simulate_turn(game, a)), 1 if a.get("skip") else 0))
    if kind in ("reaver_count", "reaver_pick", "discard_order", "reaver_order", "cleanup_top", "banish_top",
                "discard_top", "zone_move", "zone_rescue", "team_discard") or kind in NEW_KINDS:
        act = simple_decision(game)
        if act is not None:
            return act
    best: Optional[dict] = None
    best_key = None
    for act in acts:
        if act.get("skip"):
            continue
        g = copy.deepcopy(game)
        apply_action(g, act)
        _settle_decisions(g)
        defeated = g.enemies_defeated > game.enemies_defeated
        if not defeated:
            continue
        exact = any(ev["t"] == "defeat" and ev.get("exact") for ev in g.last_events)
        given = game.cards[act["card"]].value if act.get("card") else 0
        key = (0 if exact else 1, len(act.get("card_ids") or []), given)
        if best_key is None or key < best_key:
            best_key = key
            best = act
    if best is not None:
        return best
    if skip:
        return skip[0]
    return acts[0]


def apply_action(game: Game, action: dict) -> None:
    t = action["type"]
    if t == "play":
        game.play(action["cards"], action.get("choice"))
    elif t == "yield":
        game.yield_turn()
    elif t == "solo_jester":
        game.use_solo_jester({"suit": action["suit"]} if "suit" in action else None)
    elif t == "suffer":
        game.suffer(action["cards"])
    elif t == "choose_next":
        game.choose_next(action["player"])
    elif t == "special":
        game.special(action)
    elif t == "flute_add":
        game.flute_add(action["card_ids"])
    elif t == "flute_pass":
        game.flute_pass()
    elif game.phase == PHASE_DECIDE:
        game.decide(action)
    else:
        raise ValueError("unknown action %r" % (t,))


def play_out(game: Game, policy: Callable[[Game, object], dict] = greedy_policy, rng=None,
             max_steps: int = 2000) -> Game:
    """Drive a game to its end with one policy for every seat."""
    steps = 0
    while not game.is_over:
        apply_action(game, policy(game, rng))
        steps += 1
        if steps > max_steps:
            raise RuntimeError("game did not finish in %d steps" % max_steps)
    return game
