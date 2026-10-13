"""Rule-by-rule tests of the base game against docs/RULES_BASE.md."""
import pytest

from regicide.engine import (PHASE_CHOOSE_NEXT, PHASE_LOST, PHASE_PLAY, PHASE_SUFFER, PHASE_WON,
                             Game, IllegalAction)
from regicide.rules import GameConfig, classify_combo
from regicide.cards import make_card, jester_card
from helpers import new_game, set_discard, set_enemy, set_hand, set_tavern_top


# ---------------------------------------------------------------- setup table
@pytest.mark.parametrize("players,hand,jesters", [(1, 8, 0), (2, 7, 0), (3, 6, 1), (4, 5, 2)])
def test_setup_table(players, hand, jesters):
    g = new_game(players)
    assert g.config.max_hand == hand
    assert sum(1 for c in g.cards.values() if c.is_jester) == jesters
    for p in g.players:
        assert len(p.hand) == hand
    assert g.enemy is not None and g.cards[g.enemy.card_id].rank == "J"
    assert len(g.castle) == 11
    assert len(g.tavern) == 40 + jesters - players * hand
    if players == 1:
        assert g.solo_jesters == 2


def test_enemy_stats():
    g = new_game(1)
    stats = {r: g.rules.enemy_stats(g, make_card(r, "H")) for r in "JQK"}
    assert stats == {"J": (10, 20), "Q": (15, 30), "K": (20, 40)}


# ---------------------------------------------------------------- combos
def c(rank, suit="H"):
    return make_card(rank, suit)


def test_combo_classification():
    assert classify_combo([c("7")]) == ("single", None)
    assert classify_combo([jester_card(1)]) == ("jester", None)
    assert classify_combo([c("A", "S"), c("9", "C")]) == ("companion", None)
    assert classify_combo([c("A", "S"), c("A", "C")]) == ("companion", None)
    assert classify_combo([c("5", "H"), c("5", "C")]) == ("set", None)
    assert classify_combo([c("2", "H"), c("2", "C"), c("2", "S"), c("2", "D")]) == ("set", None)
    assert classify_combo([c("3", "H"), c("3", "C"), c("3", "S")]) == ("set", None)
    assert classify_combo([c("6", "H"), c("6", "C")])[0] == ""        # 12 > 10
    assert classify_combo([c("5", "H"), c("4", "C")])[0] == ""        # mixed ranks
    assert classify_combo([c("A", "S"), c("A", "C"), c("A", "H")])[0] == ""
    assert classify_combo([c("A", "S"), jester_card(1)])[0] == ""     # Ace + Jester
    assert classify_combo([jester_card(1), c("7")])[0] == ""
    assert classify_combo([])[0] == ""


def test_legal_plays_enumeration():
    g = new_game(3, seed=2)
    set_hand(g, ["AS", "AC", "5H", "5C", "6D", "X1"])
    plays = {tuple(p) for p in g.legal_plays()}
    assert ("AS",) in plays and ("X1",) in plays
    ace_pairs = [p for p in plays if set(p) == {"AS", "AC"}]
    assert len(ace_pairs) == 1
    assert ("AS", "5H") in plays and ("AS", "X1") not in plays
    assert ("5H", "5C") in plays
    assert ("6D", "5C") not in plays


# ---------------------------------------------------------------- suit powers
def test_clubs_double_and_immunity():
    g = new_game(1)
    set_enemy(g, "J", "H")
    set_hand(g, ["5C", "2D", "3D"])
    g.play(["5C"])
    assert g.enemy.hp == 10
    g2 = new_game(1)
    set_enemy(g2, "J", "C")
    set_hand(g2, ["5C", "2D", "3D"])
    g2.play(["5C"])
    assert g2.enemy.hp == 15  # immune: no doubling


def test_spades_shield_and_accumulation():
    g = new_game(1)
    set_enemy(g, "J", "H")
    set_hand(g, ["5S", "3S", "9D", "9C", "10D"])
    g.play(["5S"])
    assert g.shield == 5 and g.enemy_attack == 5
    assert g.phase == PHASE_SUFFER and g.pending_damage == 5
    g.suffer(["9D"])
    g.play(["3S"])
    assert g.shield == 8 and g.enemy_attack == 2


def test_spade_shield_uses_combo_total():
    g = new_game(1)
    set_enemy(g, "J", "H")
    set_hand(g, ["AS", "7C", "9D"])
    g.play(["AS", "7C"])
    assert g.shield == 8            # Ace♠ + 7♣ = 8 shield (combo total)
    assert g.enemy.hp == 20 - 16    # and clubs doubled 8 -> 16


def test_spades_against_spade_enemy_are_ignored_until_jester():
    g = new_game(3, seed=3)
    set_enemy(g, "J", "S")
    set_hand(g, ["5S", "9D", "X1", "4H"], player=0)
    g.play(["5S"])
    assert g.shield == 0 and g.enemy_attack == 10
    g.suffer(["9D", "4H"])
    assert g.active == 1
    set_hand(g, ["X1", "2H"], player=1)
    g.play(["X1"])
    assert g.immunity_cancelled and g.phase == PHASE_CHOOSE_NEXT
    assert g.shield == 5  # retroactive
    g.choose_next(0)
    assert g.active == 0 and g.enemy_attack == 5


def test_hearts_heal_moves_discard_under_tavern():
    g = new_game(1)
    set_enemy(g, "J", "S")
    set_discard(g, ["2D", "3D", "4D"])
    set_hand(g, ["2H", "9C"])
    n_before = len(g.tavern)
    g.play(["2H"])
    assert len(g.discard) == 1
    assert len(g.tavern) == n_before + 2
    assert set(g.tavern[-2:]) <= {"2D", "3D", "4D"}


def test_hearts_immune_and_empty_discard():
    g = new_game(1)
    set_enemy(g, "J", "H")
    set_discard(g, ["2D"])
    set_hand(g, ["2H", "9C"])
    g.play(["2H"])
    assert g.discard == ["2D"]
    g2 = new_game(1)
    set_enemy(g2, "J", "S")
    g2.discard = [] if not g2.discard else g2.discard
    set_hand(g2, ["2H", "9C"])
    assert g2.discard == []
    g2.play(["2H"])
    assert g2.discard == [] and g2.enemy.hp == 18


def test_diamonds_draw_respects_hand_limit_and_tavern():
    g = new_game(1)
    set_enemy(g, "J", "S")
    set_hand(g, ["5D", "2C", "3C"])
    g.play(["5D"])
    assert len(g.players[0].hand) == 7   # 2 left + 5 drawn
    g2 = new_game(1)
    set_enemy(g2, "J", "S")
    set_hand(g2, ["5D", "2C", "3C"])
    g2.tavern = g2.tavern[:2]
    g2.play(["5D"])
    assert len(g2.players[0].hand) == 4
    assert g2.tavern == []


def test_diamonds_draw_round_robin_skips_full_hands():
    g = new_game(3, seed=4)
    set_enemy(g, "J", "S")
    set_hand(g, ["6D", "2C"], player=0)
    # player 1 full (6 cards), player 2 has 4 cards
    assert len(g.players[1].hand) == 6
    g.tavern.extend(g.players[2].hand[3:])
    g.players[2].hand = g.players[2].hand[:3]
    before2 = len(g.players[2].hand)
    g.play(["6D"])
    drawn = [e for e in g.last_events if e["t"] == "draw"]
    assert len(drawn) == 6
    assert [e["player"] for e in drawn] == [0, 2, 0, 2, 0, 2]
    assert len(g.players[0].hand) == 4 and len(g.players[2].hand) == before2 + 3


def test_diamonds_immune_draws_nothing():
    g = new_game(1)
    set_enemy(g, "J", "D")
    set_hand(g, ["5D", "9C"])
    g.play(["5D"])
    assert len(g.players[0].hand) == 1


def test_hearts_before_diamonds_in_combo():
    """A 5♥ + 5♦ combo must heal first so the healed cards can be drawn."""
    g = new_game(1)
    set_enemy(g, "J", "S")
    set_hand(g, ["5H", "5D"])
    set_discard(g, ["2C", "3C", "4C"])
    g.tavern = []
    g.play(["5H", "5D"])
    assert g.enemy.hp == 10
    assert sorted(g.players[0].hand) == ["2C", "3C", "4C"]
    assert g.discard == []


# ---------------------------------------------------------------- damage / defeat
def test_exact_kill_goes_to_tavern_top_and_same_player_continues():
    g = new_game(2, seed=5)
    set_enemy(g, "J", "H", hp=10)
    set_hand(g, ["10C", "2D"], player=0)
    g.play(["10C"])        # clubs double -> 20, not exact
    assert g.phase == PHASE_PLAY and g.active == 0
    assert g.discard[0] == "JH"
    g2 = new_game(2, seed=5)
    set_enemy(g2, "J", "C", hp=10)
    set_hand(g2, ["10C", "2D"], player=0)
    g2.play(["10C"])       # immune to clubs -> exactly 10
    assert g2.tavern[0] == "JC"
    assert g2.phase == PHASE_PLAY and g2.active == 0
    assert g2.enemy is not None and g2.cards[g2.enemy.card_id].rank == "J"
    assert "10C" in g2.discard


def test_exact_kill_with_doubling_counts_doubled_damage():
    g = new_game(1)
    set_enemy(g, "J", "H", hp=10)
    set_hand(g, ["5C", "2D"])
    g.play(["5C"])
    assert g.tavern[0] == "JH"


def test_played_cards_go_to_discard_on_defeat():
    g = new_game(1)
    set_enemy(g, "J", "H", hp=12)
    set_hand(g, ["5S", "7D", "9C", "8C"])
    g.play(["5S"])
    g.suffer(["9C"])
    g.play(["7D"])
    assert set(["5S", "7D", "9C"]) <= set(g.discard)
    assert g.plays == [] and g.shield == 0


def test_win_after_twelve_enemies():
    g = new_game(1)
    set_enemy(g, "K", "H", hp=1)
    g.castle = []
    set_hand(g, ["2C"])
    g.play(["2C"])
    assert g.phase == PHASE_WON and g.result == "gold"


def test_solo_victory_tiers():
    for used, tier in ((0, "gold"), (1, "silver"), (2, "bronze")):
        g = new_game(1)
        g.solo_jesters_used = used
        set_enemy(g, "K", "H", hp=1)
        g.castle = []
        set_hand(g, ["2C"])
        g.play(["2C"])
        assert g.result == tier


# ---------------------------------------------------------------- suffering
def test_suffer_requires_enough_and_allows_overpay():
    g = new_game(1)
    set_enemy(g, "J", "H")
    set_hand(g, ["2C", "4D", "9S", "3H"])
    g.play(["2C"])
    assert g.pending_damage == 10
    with pytest.raises(IllegalAction):
        g.suffer(["4D", "3H"])
    g.suffer(["9S", "3H"])
    assert sorted(g.players[0].hand) == ["4D"]
    assert g.shield == 0  # discarded spade is not a shield


def test_cannot_pay_loses():
    g = new_game(2, seed=6)
    set_enemy(g, "K", "H")
    set_hand(g, ["2C", "3D"], player=0)
    g.play(["2C"])
    assert g.phase == PHASE_LOST and "cannot suffer" in g.loss_reason


def test_cannot_pay_but_solo_jester_available_keeps_playing():
    g = new_game(1)
    set_enemy(g, "K", "H")
    set_hand(g, ["2C", "3D"])
    g.play(["2C"])
    assert g.phase == PHASE_SUFFER
    g.use_solo_jester()
    assert len(g.players[0].hand) == 8
    assert g.solo_jesters == 1
    assert g.phase in (PHASE_SUFFER, PHASE_LOST)


def test_zero_damage_turn_passes_automatically():
    g = new_game(2, seed=7)
    set_enemy(g, "J", "H")
    set_hand(g, ["10S", "2C"], player=0)
    g.play(["10S"])
    assert g.enemy_attack == 0
    assert g.phase == PHASE_PLAY and g.active == 1


# ---------------------------------------------------------------- yielding
def test_yield_rules():
    g1 = new_game(1)
    assert not g1.can_yield()
    with pytest.raises(IllegalAction):
        g1.yield_turn()
    g = new_game(2, seed=8)
    set_enemy(g, "J", "H")
    set_hand(g, ["9C", "9D"], player=0)
    set_hand(g, ["9S", "9H"], player=1)
    assert g.can_yield()
    g.yield_turn()
    assert g.phase == PHASE_SUFFER and g.pending_damage == 10
    g.suffer(["9C", "9D"])
    assert g.active == 1 and not g.can_yield()
    with pytest.raises(IllegalAction):
        g.yield_turn()
    g.play(["9S"])
    g.suffer(["9H"])
    assert g.active == 0 and g.can_yield()


def test_yield_count_three_players():
    g = new_game(3, seed=9)
    set_enemy(g, "J", "H")
    for i in range(3):
        set_hand(g, ["%s%s" % (r, s) for r, s in (("9", "CDS"[i]), ("8", "CDS"[i]))], player=i)
    g.yield_turn(); g.suffer(g.players[0].hand[:2])
    g.yield_turn(); g.suffer(g.players[1].hand[:2])
    assert g.active == 2 and not g.can_yield()


# ---------------------------------------------------------------- jester
def test_jester_cancels_immunity_skips_damage_and_chooses_next():
    g = new_game(4, seed=10)
    set_enemy(g, "J", "C")
    set_hand(g, ["X1", "5C"], player=0)
    g.play(["X1"])
    assert g.phase == PHASE_CHOOSE_NEXT
    assert g.enemy.hp == 20 and g.pending_damage == 0
    acts = [a["player"] for a in g.legal_actions()]
    assert acts == [0, 1, 2, 3]
    g.choose_next(2)
    assert g.active == 2 and g.phase == PHASE_PLAY
    set_hand(g, ["5C", "2D"], player=2)
    g.play(["5C"])
    assert g.enemy.hp == 10  # clubs now doubles


def test_jester_self_choice_configurable():
    g = Game.new(GameConfig(players=3, jester_may_choose_self=False), seed=11)
    set_enemy(g, "J", "C")
    set_hand(g, ["X1", "5C"], player=0)
    g.play(["X1"])
    assert [a["player"] for a in g.legal_actions()] == [1, 2]
    with pytest.raises(IllegalAction):
        g.choose_next(0)


def test_jester_resets_yield_streak():
    g = new_game(3, seed=12)
    set_enemy(g, "J", "H")
    set_hand(g, ["9C", "9D"], player=0)
    set_hand(g, ["X1", "9H"], player=1)
    g.yield_turn(); g.suffer(["9C", "9D"])
    g.play(["X1"])
    assert g.last_action == ["yielded", "played", None]
    g.choose_next(2)
    assert g.can_yield()  # player 1 played, so not everyone else yielded


def test_yield_rule_uses_last_turn_of_each_other_player():
    """After a kill the same player takes a bonus turn; whether they may yield depends on
    what the OTHER players did on their last turns, not on a consecutive-yield streak."""
    g = new_game(3, seed=21)
    set_enemy(g, "J", "H", hp=100)
    set_hand(g, ["9C", "9D"], player=0)
    set_hand(g, ["9S", "9H"], player=1)
    set_hand(g, ["10C", "2D"], player=2)
    g.yield_turn(); g.suffer(["9C", "9D"])      # P1 yielded
    g.yield_turn(); g.suffer(["9S", "9H"])      # P2 yielded
    assert g.active == 2 and not g.can_yield()  # everyone else yielded
    g.enemy.hp = 20
    g.play(["10C"])                             # kills -> bonus turn for P3
    assert g.active == 2 and g.phase == PHASE_PLAY
    assert not g.can_yield()                    # P1 and P2 still yielded on their last turns


# ---------------------------------------------------------------- solo jester power
def test_solo_jester_power_discards_and_refills():
    g = new_game(1)
    set_enemy(g, "J", "H")
    old = list(g.players[0].hand)
    g.use_solo_jester()
    assert g.solo_jesters == 1 and g.solo_jesters_used == 1
    assert len(g.players[0].hand) == 8
    assert all(c in g.discard for c in old)
    assert not g.immunity_cancelled


def test_solo_jester_not_available_multiplayer():
    g = new_game(2)
    assert not g.can_use_solo_jester()
    with pytest.raises(IllegalAction):
        g.use_solo_jester()


def test_solo_jester_does_not_count_as_diamond_draw():
    g = new_game(1)
    set_enemy(g, "J", "D")
    g.use_solo_jester()
    assert len(g.players[0].hand) == 8


def test_empty_hand_no_jester_loses_solo():
    g = new_game(1)
    set_enemy(g, "J", "H", hp=100)
    g.solo_jesters = 0
    set_hand(g, ["10C"])
    g.play(["10C"])
    assert g.phase == PHASE_LOST  # cannot suffer 10 with nothing


def test_empty_hand_can_yield_multiplayer():
    g = new_game(2, seed=13)
    set_enemy(g, "J", "H", hp=100)
    set_hand(g, ["10S"], player=0)
    g.play(["10S"])            # shield 10 -> no damage, turn passes with empty hand
    assert g.active == 1
    set_hand(g, ["2C"], player=1)
    g.play(["2C"])             # player 1 then must suffer 0 (shield) -> turn passes
    assert g.active == 0 and g.phase == PHASE_PLAY
    assert g.legal_actions() == [{"type": "yield"}]


# ---------------------------------------------------------------- misc
def test_preview_does_not_mutate():
    g = new_game(1, seed=14)
    before = g.to_dict()
    p = g.legal_plays()[0]
    pv = g.preview_play(p)
    assert pv["ok"] and "damage" in pv
    assert g.to_dict() == before


def test_illegal_actions_raise():
    g = new_game(1)
    with pytest.raises(IllegalAction):
        g.play(["ZZ"])
    with pytest.raises(IllegalAction):
        g.suffer([])
    with pytest.raises(IllegalAction):
        g.choose_next(0)


def test_save_load_roundtrip_and_determinism():
    import json
    from regicide.bots import apply_action, greedy_policy, play_out
    g = new_game(4, seed=15)
    for _ in range(5):
        apply_action(g, greedy_policy(g))
    d = json.loads(json.dumps(g.to_dict()))
    g2 = Game.from_dict(d)
    assert g2.to_dict() == g.to_dict()
    play_out(g); play_out(g2)
    assert g.to_dict() == g2.to_dict()


# ---------------------------------------------------------------- optional variants
def test_variant_solo_can_yield():
    g = Game.new(GameConfig(players=1, solo_can_yield=True), seed=30)
    set_enemy(g, "J", "H")
    assert g.can_yield()
    g.yield_turn()
    assert g.phase == PHASE_SUFFER
    g.suffer(min_cover(g))
    assert not g.can_yield()  # not twice in a row


def test_variant_strict_minimal_discard():
    g = Game.new(GameConfig(players=1, strict_minimal_discard=True), seed=31)
    set_enemy(g, "J", "H")
    set_hand(g, ["2C", "9S", "3D", "8D"])
    g.play(["2C"])
    with pytest.raises(IllegalAction):
        g.suffer(["9S", "3D", "8D"])  # 3D not needed
    g.suffer(["9S", "3D"])
    assert g.phase == PHASE_PLAY


def test_variant_yield_reset_per_enemy():
    g = Game.new(GameConfig(players=2, yield_reset_per_enemy=True), seed=32)
    set_enemy(g, "J", "H", hp=100)
    set_hand(g, ["9C", "9D"], player=0)
    set_hand(g, ["10C", "2D"], player=1)
    g.yield_turn(); g.suffer(["9C", "9D"])
    assert not g.can_yield()
    g.enemy.hp = 20
    g.play(["10C"])  # kill -> new enemy, yields forgotten
    assert g.active == 1 and g.can_yield()


def min_cover(g):
    from regicide.bots import min_waste_discard
    return min_waste_discard(g)
