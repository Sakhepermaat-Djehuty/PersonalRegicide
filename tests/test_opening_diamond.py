"""Owner's hidden house rule: every opening hand holds a card that can draw (a Diamond, a
Bard in Legacy; a multi-class card with the Diamond counts), or the game cannot recover."""
import pytest

from regicide.campaign import CampaignState
from regicide.engine import Game
from regicide.rules import GameConfig


def _has_diamond(g, hand):
    return any("D" in g.cards[c].suits for c in hand)


@pytest.mark.parametrize("players", [1, 2, 3, 4])
def test_every_opening_hand_can_draw_in_the_base_game(players):
    swapped = 0
    for seed in range(300):
        g = Game.new(GameConfig(players=players), seed=seed)
        plain = Game.new(GameConfig(players=players, opening_diamond=False), seed=seed)
        for p, q in zip(g.players, plain.players):
            assert _has_diamond(g, p.hand)
            if p.hand != q.hand:
                swapped += 1
                # one card traded with the reserve's first Diamond; the rest of the deal is the same
                assert len(set(p.hand) - set(q.hand)) == 1 and not _has_diamond(plain, q.hand)
        assert sorted(g.all_card_ids()) == sorted(plain.all_card_ids())
        assert len(g.all_card_ids()) == len(set(g.all_card_ids()))
        if all(_has_diamond(plain, q.hand) for q in plain.players):
            assert [p.hand for p in g.players] == [q.hand for q in plain.players] and g.tavern == plain.tavern
    assert swapped > 0


def test_campaign_attempts_and_the_switch():
    for seed in range(60):
        c = CampaignState.new(1, ["Ana"], seed=seed)
        g = c.start_attempt(seed=seed)
        assert _has_diamond(g, g.players[0].hand)
    cfg = GameConfig(players=1, opening_diamond=False)
    assert GameConfig.from_dict(cfg.to_dict()).opening_diamond is False
    assert GameConfig.from_dict({}).opening_diamond is True
