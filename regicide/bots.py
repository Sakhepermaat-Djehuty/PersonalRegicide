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
from .engine import PHASE_CHOOSE_NEXT, PHASE_LOST, PHASE_PLAY, PHASE_SUFFER, PHASE_WON, Game


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


def _simulate_turn(game: Game, action: dict) -> Game:
    """Apply an action on a copy and, if damage follows, pay it with the cheapest cover."""
    g = copy.deepcopy(game)
    apply_action(g, action)
    if g.phase == PHASE_SUFFER and g.active == game.active:
        if g.hand_defence_value() >= g.pending_damage:
            g.suffer(min_waste_discard(g))
        elif g.can_use_solo_jester():
            g.use_solo_jester()
            if g.phase == PHASE_SUFFER and g.hand_defence_value() >= g.pending_damage:
                g.suffer(min_waste_discard(g))
    return g


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
