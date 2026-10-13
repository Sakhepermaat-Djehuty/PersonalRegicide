"""Whole-game invariants over many random and greedy games."""
import random

import pytest

from regicide.bots import greedy_policy, play_out, random_policy
from regicide.engine import PHASE_LOST, PHASE_WON
from regicide.rules import GameConfig
from regicide.engine import Game


def _check_invariants(g):
    assert sorted(g.all_card_ids()) == sorted(g.cards)
    for p in g.players:
        assert len(p.hand) <= g.config.max_hand
    if g.enemy:
        assert g.enemy.hp > 0


@pytest.mark.parametrize("players", [1, 2, 3, 4])
def test_greedy_games_finish_with_invariants(players):
    results = []
    defeated = []
    for seed in range(40):
        g = Game.new(GameConfig(players=players), seed=seed)
        play_out(g, greedy_policy)
        assert g.phase in (PHASE_WON, PHASE_LOST)
        _check_invariants(g)
        results.append(g.result)
        defeated.append(g.enemies_defeated)
    if players > 1:
        assert any(r != "loss" for r in results), "greedy bot never wins at %d players" % players
    else:
        # Solo Regicide is hard; the one-ply bot rarely wins but should reach the Queens.
        assert sum(defeated) / len(defeated) >= 4.0, "solo bot defeats too few enemies"


@pytest.mark.parametrize("players", [1, 3])
def test_random_games_never_crash(players):
    rng = random.Random(1)
    for seed in range(40):
        g = Game.new(GameConfig(players=players), seed=seed)
        play_out(g, random_policy, rng)
        _check_invariants(g)
