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
    """Smallest-total set of hand cards covering the pending damage.

    Ties: fewer cards first, then keep high-value cards in hand. Returns the whole hand
    if nothing covers the damage (the caller will lose anyway).
    """
    need = game.pending_damage
    hand = game.hand(player)
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
    else:  # large Legacy hands: greedy by value descending
        total = 0
        for c in sorted(hand, key=lambda c: -c.defence_value):
            if total >= need:
                break
            best_ids.append(c.id)
            total += c.defence_value
        if total < need:
            best_ids = [c.id for c in hand]
        return best_ids
    return best_ids if best is not None else [c.id for c in hand]


# --------------------------------------------------------------------------- policies
def random_policy(game: Game, rng) -> dict:
    acts = [a for a in game.legal_actions() if a["type"] != "special"]
    if game.phase == PHASE_SUFFER:
        if game.hand_defence_value() < game.pending_damage:
            if game.can_use_solo_jester():
                return {"type": "solo_jester"}  # the only way out (else the game would be lost)
            return {"type": "suffer", "cards": [c.id for c in game.hand()]}
        # random legal cover: shuffle and take until covered
        hand = list(game.hand())
        rng.shuffle(hand)
        ids: List[str] = []
        total = 0
        for c in hand:
            if total >= game.pending_damage:
                break
            ids.append(c.id)
            total += c.defence_value
        return {"type": "suffer", "cards": ids}
    return rng.choice(acts)


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
    pick take the strongest card; a reaver reveals one card; the clean-up top (mission 4)
    and the card moved to the zone (mission 6) are the weakest, the rescued zone card the
    strongest; Myla's team damage is paid with the cheapest cover over every hand."""
    acts = g.legal_actions()
    if not acts:
        return None
    skip = [a for a in acts if a.get("skip")]
    if skip:
        return skip[0]
    kind = (g.decision or {}).get("kind")
    value = lambda a: g.cards[a["card"]].value  # noqa: E731
    if kind in ("mage_peek", "reaver_pick"):
        return max(acts, key=value)
    if kind == "reaver_count":
        return min(acts, key=lambda a: int(a.get("count", 1)))
    if kind in ("cleanup_top", "zone_move"):
        return min(acts, key=value)
    if kind == "zone_rescue":
        return max(acts, key=value)
    if kind == "team_discard":
        return team_discard_choice(g, acts)
    return acts[0]


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
            return {"type": "suffer", "cards": [c.id for c in game.hand()]}  # feign death or lose
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
    reaver reveals one card and adds the strongest; the mission choices (clean-up top,
    zone move, zone rescue, team damage) follow ``simple_decision``."""
    acts = game.legal_actions()
    skip = [a for a in acts if a.get("skip")]
    kind = (game.decision or {}).get("kind")
    picks = [a for a in acts if a["type"] == "mage_pick"]
    if picks:
        return max(picks, key=lambda a: _mage_pick_key(game, a))
    if kind == "emblem_keep":
        return max(acts, key=lambda a: (evaluate(_simulate_turn(game, a)), 1 if a.get("skip") else 0))
    if kind in ("reaver_count", "reaver_pick", "cleanup_top", "zone_move", "zone_rescue", "team_discard"):
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
