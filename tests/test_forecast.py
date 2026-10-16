"""Forecasts (``Game.preview_play``) never show what a hidden card or a coming shuffle
holds, stop where the acting player's turn ends and say what that player would suffer;
the rules fixes found with them: a 2/5 stored on the Kinfolk Flute keeps its value, a
claimed Jester does not turn earlier immune paladins into shield, and an enemy of several
classes is named by them."""
import itertools
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import fakeui  # noqa: E402

fakeui.install()

from helpers import _pull, set_discard, set_enemy, set_hand, set_mission_enemy, set_tavern_top  # noqa: E402
from regicide.campaign import CampaignState  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402
from regicide.cards import Card  # noqa: E402
from regicide.engine import PHASE_PLAY, Game, Play, enemy_name  # noqa: E402
from regicide.rules import GameConfig  # noqa: E402
from test_twofive import OVER, SAME, campaign_game  # noqa: E402


def _attempt(number, seed=462, guardians=False, beast=None):
    c = CampaignState.new(1, ["Ana"], seed=seed)
    c.mission, c.completed = number, list(range(1, number))
    P.add_card(c.party, dict(M.GORAN))
    c.flags["beasts"] = True
    if beast:
        c.set_beast(beast)
    for d in list(M.MAGE_DECK) + (list(M.GUARDIANS) if guardians else []):
        if P.find(c.party, str(d["id"])) is None:
            P.add_card(c.party, dict(d))
    g = c.start_attempt(seed=seed)
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    return g


def _key(pv):
    """What a forecast shows: the numbers and the powers' immunity."""
    return (pv["attack"], pv["damage"], pv["defeats"], pv["exact"], pv["enemy_hp_after"], pv["enemy_attack_after"],
            pv["suffer"], sorted((s, ev.get("immune")) for s, ev in pv["powers"].items()))


def test_a_mage_forecast_does_not_depend_on_the_hidden_reserve():
    # mission 4: the enemy gains the top discard's strength, and a mage's reveals end on
    # the discard pile; the forecast must read the same whatever the reserve holds
    seen = set()
    for top in (["2C", "9H"], ["2C", "4H"], ["10D", "2H"]):
        g = _attempt(4)
        set_mission_enemy(g, "LABJD", hp=100)
        set_discard(g, ["5S"])
        set_hand(g, ["2M", "9S", "8S", "7C"])
        set_tavern_top(g, top)
        before = (list(g.tavern), list(g.discard))
        pv = g.preview_play(["2M"])
        assert (list(g.tavern), list(g.discard)) == before           # the real game is untouched
        seen.add(repr(_key(pv)))
    assert len(seen) == 1


def test_a_heal_whose_shuffle_feeds_the_enemy_is_uncertain_not_foretold():
    # mission 4: a heal shuffles the discard pile, whose new top sets the enemy's strength
    shown = set()
    for seed in (1, 2, 3, 4):
        g = _attempt(4, seed=seed)
        set_mission_enemy(g, "LABJD", hp=100)
        set_discard(g, ["2C", "9S", "4D", "7C", "10S", "3D", "6C", "8D", "5S", "2D"])
        set_hand(g, ["8H", "9S"])
        g.rng.seed(seed)                       # the real shuffle to come differs each time
        pv = g.preview_play(["8H"])
        assert pv["uncertain"] and pv["suffer"] is None and pv["enemy_attack_after"] is None
        shown.add(repr(_key(pv)))
    assert len(shown) == 1                     # nothing about the real shuffle leaks


def test_a_guardian_forecast_stops_with_the_turn_whatever_beast_comes_next():
    from app.screens import describe_preview
    for top in ("B_C", "B_S", "B_H", "B_D"):
        g = _attempt(11, seed=1101, guardians=True, beast="B_H")
        set_mission_enemy(g, "CV_J1", hp=100)
        g.extra["beast_deck"] = [top] + [b for b in ("B_C", "B_S", "B_H", "B_D") if b != top]
        g.extra["beasts_out"] = []
        set_hand(g, ["3G", "9S", "8S", "2C"])
        g.phase = PHASE_PLAY
        pv = g.preview_play(["3G"])
        assert pv["suffer"] == 0 and pv["phase_after"] == PHASE_PLAY, top
        assert "nothing to suffer" in describe_preview(g, pv)
        assert g.extra["beast_deck"][0] == top                        # the real deck is untouched


def test_an_ordinary_play_forecasts_the_damage_to_suffer():
    g = Game.new(GameConfig(players=1), seed=4)
    set_enemy(g, "J", "C")
    set_hand(g, ["5H", "9D", "2S"])
    pv = g.preview_play(["5H"])
    assert pv["suffer"] == 10 and not pv["uncertain"] and pv["enemy_hp_after"] == 15
    pv = g.preview_play(["2S"])                                       # a shield of 2
    assert pv["suffer"] == 8


def test_a_two_five_stored_on_the_flute_keeps_its_value():
    c, g = campaign_game(number=2, seed=2601, relics=("flute",))
    set_hand(g, ["M25D", "2C", "5C", "M25S", "M25H"])
    g.special([a for a in g.legal_actions()
               if a.get("name") == "flute_store" and a["card"] == "M25D" and a.get("value") == 5][0])
    assert g.check_play(["M25D", "2C"]) == (False, SAME)               # a 5 and a 2
    assert g.check_play(["M25D", "M25S", "2C"]) == (False, SAME)
    assert g.check_play(["M25D", "M25S", "M25H"]) == (False, OVER)     # three 5s: 15
    assert g.check_play(["M25D", "5C"]) == (True, "set")
    legal = set(frozenset(p) for p in g.legal_plays())
    ids = g.rules.playable_ids(g)
    for n in range(1, len(ids) + 1):
        for combo in itertools.combinations(ids, n):
            assert g.check_play(list(combo))[0] == (frozenset(combo) in legal), combo


def test_a_claimed_jester_does_not_make_earlier_immune_paladins_shield():
    g = Game.new(GameConfig(players=1), seed=7)
    set_enemy(g, "J", "S")
    _pull(g, "5S")
    g.plays.append(Play(player=0, card_ids=["5S"], suits=("S",), value=5, jester=False))
    assert g.shield == 0
    g.extra["jester_attack"] = True            # a Jester claimed for the next attack
    assert g.shield == 0 and g.enemy_attack == 10
    _pull(g, "4S")
    g.plays.append(Play(player=0, card_ids=["4S"], suits=("S",), value=4, jester=True))
    assert g.shield == 4                       # the claimed attack's own paladin counts


def test_an_enemy_of_several_classes_is_named_by_them():
    four = Card(id="4D", rank="4", suits=("D", "U"), value=4)
    assert enemy_name(four, legacy=True) == "4 · Bard / Druid"
    assert enemy_name(Card(id="5R", rank="5", suits=("R",), value=5), legacy=True) == "5 of Reavers"
    assert enemy_name(Card(id="JH", rank="J", suits=("H",), value=10)) == "Jack of Hearts"
    assert enemy_name(Card(id="X", rank="Q", suits=("H",), value=15, name="Myla")) == "Myla"
