"""2/5 mercenaries (rulebook p.25, confirmed by the owner): a 2/5's strength is 2 or 5,
fixed when it enters play and kept while it is in play. In a kinfolk set it takes the value
that makes the set legal (2/5 + 5 is a set of 5s, 2/5 + 2 a set of 2s); two 2/5s on their
own may be 2s or 5s (one question for both); three 2/5s can only be 2s under the limit of
10; alone, with a companion or with a beast the player declares 2 or 5."""
import json
import os
import random
import sys

import pytest

from helpers import set_enemy, set_hand
from regicide.bots import (apply_action, declare_value_choice, greedy_policy, min_waste_discard, random_policy,
                           simple_decision)
from regicide.campaign import CampaignState
from regicide.campaign import missions as M
from regicide.campaign import party as P
from regicide.engine import PHASE_DECIDE, PHASE_PLAY, PHASE_SUFFER, Game, IllegalAction

SAME = "Combos need cards of the same number, or an Ace with one other card."
OVER = "A combo's total must be 10 or less."
ALL_25 = ("merc_25H", "merc_25D", "merc_25C", "merc_25S")


def campaign_game(number=1, players=1, seed=2500, mercs=ALL_25, relics=(), beast=None):
    """A Legacy attempt at mission ``number`` with the given mercenaries hired."""
    c = CampaignState.new(players, ["Ana", "Ben", "Cy", "Dee"][:players], seed=seed)
    c.mission = number
    c.completed = list(range(1, number))
    c.relics.extend(relics)
    if number >= 4:
        P.add_card(c.party, dict(M.GORAN))
        c.flags["beasts"] = True
        c.set_beast(beast)
        for d in M.MAGE_DECK:
            if P.find(c.party, str(d["id"])) is None:
                P.add_card(c.party, dict(d))
    c.m_box_opened = True
    c.coins = 20
    for m in mercs:
        c.hire(m)
    g = c.start_attempt(seed=seed)
    return c, g


def round_trip(g):
    return Game.from_dict(json.loads(json.dumps(g.to_dict())))


def ids_everywhere(g):
    ids = g.all_card_ids()
    assert len(ids) == len(set(ids)) == len(g.cards), (len(ids), len(set(ids)), len(g.cards))


def declared(g):
    return dict(g.extra.get("declared_value") or {})


def enemy_by_suit(g, suit, rank=None, hp=None):
    """Make the mission's castle card with this suit (and rank) the current enemy."""
    from helpers import set_mission_enemy
    for cid in [g.enemy.card_id] + list(g.castle):
        card = g.cards[cid]
        if suit in card.suits and (rank is None or card.rank == rank):
            set_mission_enemy(g, cid, hp=hp)
            return cid
    raise RuntimeError("no such enemy")


def settle(g):
    while g.phase == PHASE_DECIDE:
        g.decide(simple_decision(g))


# ---------------------------------------------------------------- kinfolk sets
def test_two_five_with_a_five_is_a_set_of_fives_without_a_question():
    c, g = campaign_game()
    set_enemy(g, "Q", "S", hp=30)                      # immune to paladins: the hearts and diamonds work
    set_hand(g, ["M25H", "5D", "9S", "8S"])
    assert g.check_play(["M25H", "5D"]) == (True, "set")           # the owner's report: it was refused
    pv = g.preview_play(["M25H", "5D"])
    assert pv["ok"] and not pv["decision"] and pv["attack"] == 10 and pv["damage"] == 10
    g.play(["M25H", "5D"])
    assert g.decision is None and g.plays[-1].value == 10 and g.enemy.hp == 20
    assert declared(g) == {"M25H": 5}
    played = [ev for ev in g.last_events if ev["t"] == "play"][0]
    assert played["value"] == 10 and played["kind"] == "set"
    assert [ev for ev in g.last_events if ev["t"] == "declare"] == [
        {"t": "declare", "player": 0, "card": "M25H", "value": 5, "forced": True, "attack": 10}]
    assert any("2/5♥ counts 5" in line for line in g.log)
    assert g.rules.in_play_strength(g, g.cards["M25H"]) == 5


def test_two_five_with_twos_is_a_set_of_twos():
    c, g = campaign_game()
    set_enemy(g, "Q", "S", hp=30)
    set_hand(g, ["M25H", "2C", "2D", "9S"])
    assert g.check_play(["M25H", "2C"]) == (True, "set")
    g.play(["M25H", "2C"])
    assert g.decision is None and g.plays[-1].value == 4 and declared(g) == {"M25H": 2}
    assert g.enemy.hp == 30 - 8                        # 4 doubled by the warrior 2
    # and with several 2s
    c, g = campaign_game()
    set_enemy(g, "Q", "S", hp=30)
    set_hand(g, ["M25H", "2C", "2D", "9S"])
    g.play(["M25H", "2C", "2D"])
    assert g.decision is None and g.plays[-1].value == 6 and declared(g) == {"M25H": 2}


def test_two_two_fives_ask_once_and_both_take_the_declared_value():
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=30)                      # immune to warriors: no doubling anywhere
    set_hand(g, ["M25H", "M25S", "9S", "8S"])
    assert g.check_play(["M25H", "M25S"]) == (True, "set")
    g.play(["M25H", "M25S"])
    d = g.decision
    assert d["kind"] == "declare_value" and d["cards"] == ["M25H", "M25S"] and d["card"] == "M25H"
    assert [a["option"] for a in g.legal_actions()] == ["2", "5"]
    assert [a["label"] for a in g.legal_actions()] == ["Strength 2", "Strength 5"]
    assert g.rules.declare_value_question(g, d) == "2/5♥ + 2/5♠: strength 2 or 5?"
    assert "2/5♥ + 2/5♠: strength 2 or 5? Ana declares." in g.log
    assert g.enemy.hp == 30                            # nothing resolved yet
    g2 = round_trip(g)
    g.decide({"type": "declare_value", "option": "5"})
    assert g.decision is None and g.plays[-1].value == 10 and declared(g) == {"M25H": 5, "M25S": 5}
    assert g.enemy.hp == 20 and g.shield == 10
    assert len([ev for ev in g.last_events if ev["t"] == "declare"]) == 2
    g2.decide({"type": "declare_value", "option": "2"})
    assert g2.decision is None and g2.plays[-1].value == 4 and declared(g2) == {"M25H": 2, "M25S": 2}
    assert g2.enemy.hp == 26 and g2.shield == 4


def test_three_two_fives_can_only_be_twos_under_the_limit_of_ten():
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=30)
    set_hand(g, ["M25H", "M25S", "M25D", "9S"])
    assert g.check_play(["M25H", "M25S", "M25D"]) == (True, "set")
    assert g.rules.kinfolk_values(g, [g.cards[c] for c in ("M25H", "M25S", "M25D")]) == [2]
    g.play(["M25H", "M25S", "M25D"])
    assert g.decision is None and g.plays[-1].value == 6
    assert declared(g) == {"M25H": 2, "M25S": 2, "M25D": 2}
    # the limit decides: at 15 the three could be 5s too, so the player is asked
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=30)
    g.rules.kinfolk_limit = lambda game: 15
    set_hand(g, ["M25H", "M25S", "M25D", "5C", "9S"])
    assert g.rules.kinfolk_values(g, [g.cards[c] for c in ("M25H", "M25S", "M25D")]) == [2, 5]
    assert g.check_play(["M25H", "M25S", "5C"]) == (True, "set")    # 2/5 + 2/5 + 5 is 15
    g.play(["M25H", "M25S", "M25D"])
    assert g.decision["kind"] == "declare_value" and g.decision["cards"] == ["M25H", "M25S", "M25D"]
    g.decide({"type": "declare_value", "option": "5"})
    assert g.plays[-1].value == 15


def test_illegal_mixes_and_totals_keep_their_messages():
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=30)
    set_hand(g, ["M25H", "M25S", "2C", "5D", "5C", "4C", "9S"])
    assert g.check_play(["M25H", "5D", "5C"]) == (False, OVER)     # a set of 5s, but 15
    assert g.check_play(["M25H", "M25S", "5D"]) == (False, OVER)
    assert g.check_play(["M25H", "2C", "5D"]) == (False, SAME)     # no common strength
    assert g.check_play(["M25H", "4C"]) == (False, SAME)           # 4 is neither 2 nor 5
    assert g.check_play(["M25H", "M25S", "2C", "5D"]) == (False, SAME)
    with pytest.raises(IllegalAction):
        g.play(["M25H", "2C", "5D"])
    # the base game has no 2/5 cards and its sets are untouched
    from helpers import new_game
    b = new_game(1, seed=3)
    set_hand(b, ["5C", "5D", "2C", "2H"])
    assert b.check_play(["5C", "5D"]) == (True, "set") and b.check_play(["2C", "5D"])[0] is False


def test_legal_plays_list_every_two_five_combination_once():
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=30)
    hand = ["M25H", "M25S", "5D", "2C", "AS", "9S"]
    set_hand(g, hand)
    plays = g.legal_plays()
    keys = [frozenset(p) for p in plays]
    assert len(keys) == len(set(keys))                 # no duplicates
    for p in plays:
        assert g.check_play(p)[0], p
    want = [{"M25H", "5D"}, {"M25S", "5D"}, {"M25H", "2C"}, {"M25S", "2C"}, {"M25H", "M25S"},
            {"M25H", "M25S", "2C"}, {"AS", "M25H"}, {"AS", "M25S"}, {"M25H"}, {"M25S"}]
    for w in want:
        assert frozenset(w) in keys, w
    assert frozenset({"M25H", "2C", "5D"}) not in keys and frozenset({"M25H", "M25S", "5D"}) not in keys
    # exactly the legal subsets (brute force over the hand)
    import itertools
    brute = set()
    for n in range(1, len(hand) + 1):
        for combo in itertools.combinations(hand, n):
            if g.check_play(list(combo))[0]:
                brute.add(frozenset(combo))
    assert brute == set(keys)


# ---------------------------------------------------------------- a free choice
def test_companion_and_two_five_asks():
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=30)
    set_hand(g, ["AS", "M25H", "9S"])
    pv = g.preview_play(["AS", "M25H"])
    assert pv["decision_kind"] == "declare_value" and pv["attack"] == 6 and pv["damage"] == 6
    g.play(["AS", "M25H"])
    assert g.decision["kind"] == "declare_value" and g.decision["cards"] == ["M25H"]
    g2 = round_trip(g)
    g.decide({"type": "declare_value", "option": "5"})
    assert g.plays[-1].value == 6 and g.enemy.hp == 24 and g.shield == 6
    g2.decide({"type": "declare_value", "option": "2"})
    assert g2.plays[-1].value == 3 and g2.enemy.hp == 27


def test_beast_and_two_five_asks_and_the_beast_copies_the_value():
    c, g = campaign_game(number=9, seed=63, beast="B_H", mercs=("merc_25C",))
    enemy_by_suit(g, "H", "Q", hp=40)
    set_hand(g, ["B_H", "M25C", "9S", "8S"])
    assert ["B_H", "M25C"] in g.legal_plays() or ["M25C", "B_H"] in g.legal_plays()
    g.play(["B_H", "M25C"])
    assert g.decision["kind"] == "declare_value" and g.decision["cards"] == ["M25C"]
    g2 = round_trip(g)
    g.decide({"type": "declare_value", "option": "5"})
    assert g.plays[-1].value == 10 and g.enemy.hp == 40 - 20          # 5 + the beast's 5, doubled
    g2.decide({"type": "declare_value", "option": "2"})
    assert g2.plays[-1].value == 4 and g2.enemy.hp == 40 - 8


def test_the_value_is_kept_while_in_play_and_spent_with_the_enemy():
    c, g = campaign_game()
    set_enemy(g, "Q", "S", hp=40)
    set_hand(g, ["M25H", "5D", "9C", "8C", "7C", "6C", "4C", "3C"])
    g.play(["M25H", "5D"])
    assert g.enemy.hp == 30 and declared(g) == {"M25H": 5}
    assert g.phase == PHASE_SUFFER
    g.suffer(min_waste_discard(g))
    assert g.phase == PHASE_PLAY
    # a later turn under the same enemy: still a 5 in play
    assert g.rules.in_play_strength(g, g.cards["M25H"]) == 5
    assert g.plays[0].value == 10
    g.enemy.hp = 1
    g.play([max(g.active_player.hand, key=lambda x: g.cards[x].value)])
    settle(g)
    assert g.enemies_defeated == 1 and "declared_value" not in g.extra
    assert g.rules.in_play_strength(g, g.cards["M25H"]) == 2 and g.cards["M25H"].defence_value == 5
    ids_everywhere(g)


def test_a_value_from_an_earlier_visit_does_not_leak_into_a_new_set():
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=40)
    g.extra["declared_value"] = {"M25H": 5}            # stale (the card is not in play)
    set_hand(g, ["M25H", "2C", "9S"])
    assert g.preview_play(["M25H", "2C"])["attack"] == 4
    g.play(["M25H", "2C"])
    assert g.plays[-1].value == 4 and declared(g) == {"M25H": 2}


def test_a_two_five_a_mage_adds_is_declared_and_the_paused_damage_follows():
    from helpers import _pull, set_tavern_top
    for option, value in (("2", 7), ("5", 10)):
        c, g = campaign_game(number=9, seed=62, mercs=("merc_25H",))
        enemy_by_suit(g, "H", "Q", hp=40)                 # immune to clerics: no heal
        set_hand(g, ["5M", "9S", "8S"])
        _pull(g, "M25H")
        set_tavern_top(g, ["M25H", "2C", "3C", "4C", "6C"])
        g.play(["5M"])
        g.decide({"type": "mage_pick", "card": "M25H"})   # not a kinfolk set: a free choice
        d = g.decision
        assert d["kind"] == "declare_value" and d["cards"] == ["M25H"] and d["resume_step"] == "mage_picked"
        g = round_trip(g)
        g.decide({"type": "declare_value", "option": option})
        settle(g)
        assert g.plays[-1].value == value and g.enemy.hp == 40 - value and declared(g) == {"M25H": int(option)}


# ---------------------------------------------------------------- missions and relics
def _rig_pilgrims(g, zone):
    from helpers import _pull
    for x in zone:
        _pull(g, x)
    rest = [x for x in g.mission_zone + g.extra["pilgrim_deck"] if x not in zone]
    g.mission_zone = list(zone)
    g.extra["pilgrim_deck"] = rest


def test_mission7_pilgrims_match_the_two_fives_value_in_play():
    c, g = campaign_game(number=7, seed=707, mercs=("merc_25H",))
    enemy_by_suit(g, "S", hp=60)
    _rig_pilgrims(g, ["PIL5_1", "PIL2_1"])
    set_hand(g, ["M25H", "5D", "9C", "8C"])
    g.play(["M25H", "5D"])                             # forced 5: it matches the 5-pilgrim, not the 2
    d = g.decision
    assert d["kind"] == "pilgrim_banish" and d["entering"] == "M25H" and d["options"] == ["PIL5_1"]
    # declared alone: a 2 matches the 2-pilgrim, a 5 the 5-pilgrim
    for option, want in (("2", ["PIL2_1"]), ("5", ["PIL5_1"])):
        c, g = campaign_game(number=7, seed=707, mercs=("merc_25H",))
        enemy_by_suit(g, "S", hp=60)
        _rig_pilgrims(g, ["PIL5_1", "PIL2_1"])
        set_hand(g, ["M25H", "9C", "8C"])
        g.play(["M25H"])
        assert g.decision["kind"] == "declare_value"
        g = round_trip(g)
        g.decide({"type": "declare_value", "option": option})
        assert g.decision["kind"] == "pilgrim_banish" and g.decision["options"] == want


def test_kinfolk_flute_another_player_adds_a_two_five_to_a_set_of_fives():
    c, g = campaign_game(players=2, seed=2020, relics=("flute",))
    set_enemy(g, "J", "C", hp=40)
    set_hand(g, ["5D", "9S", "8S"], player=0)
    set_hand(g, ["M25S", "2C", "7C"], player=1)
    g.play(["5D"])
    d = g.decision
    assert d["kind"] == "flute_add" and d["player"] == 1 and d["strength"] == 5
    adds = [a["card_ids"] for a in g.legal_actions() if a["type"] == "flute_add"]
    assert adds == [["M25S"]]
    g.decide({"type": "flute_add", "card_ids": ["M25S"]})
    assert g.decision is None and g.plays[-1].value == 10 and declared(g) == {"M25S": 5}
    assert g.enemy.hp == 30
    # a lone 2/5 declared 2 invites 2s (and 2/5s, which then count 2)
    c, g = campaign_game(players=2, seed=2021, relics=("flute",))
    set_enemy(g, "J", "C", hp=40)
    set_hand(g, ["M25H", "9S", "8S"], player=0)
    set_hand(g, ["M25S", "2C", "5C"], player=1)
    g.play(["M25H"])
    g.decide({"type": "declare_value", "option": "2"})
    assert g.decision["kind"] == "flute_add" and g.decision["strength"] == 2
    adds = sorted(sorted(a["card_ids"]) for a in g.legal_actions() if a["type"] == "flute_add")
    assert adds == [["2C"], ["2C", "M25S"], ["M25S"]]
    g.decide({"type": "flute_add", "card_ids": ["2C", "M25S"]})
    assert g.decision is None and g.plays[-1].value == 6 and declared(g) == {"M25H": 2, "M25S": 2}


# ---------------------------------------------------------------- saves, bots, CLI, forecasts
def test_save_and_load_in_the_middle_of_the_question():
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=30)
    set_hand(g, ["M25H", "M25D", "9S"])
    g.play(["M25H", "M25D"])
    raw = json.dumps(g.to_dict())
    g2 = Game.from_dict(json.loads(raw))
    assert g2.phase == PHASE_DECIDE and g2.decision == g.decision
    assert json.dumps(g2.to_dict()) == raw
    with pytest.raises(IllegalAction):
        g2.decide({"type": "declare_value", "option": "3"})
    g2.decide({"type": "declare_value", "option": "5"})
    assert g2.plays[-1].value == 10 and declared(g2) == {"M25H": 5, "M25D": 5} and g2.enemy.hp == 20
    ids_everywhere(g2)
    # a question saved before the shared questions (one ``card``, no ``cards``) still works
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=30)
    set_hand(g, ["M25H", "9S"])
    g.play(["M25H"])
    del g.decision["cards"]
    g = round_trip(g)
    g.decide({"type": "declare_value", "option": "5"})
    assert g.plays[-1].value == 5 and declared(g) == {"M25H": 5}


def test_forecasts_bots_and_the_question_text():
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=30)
    set_hand(g, ["M25H", "M25S", "5D", "9S"])
    pv = g.preview_play(["M25H", "M25S"])            # a choice: forecast as 5s
    assert pv["decision_kind"] == "declare_value" and pv["attack"] == 10 and pv["damage"] == 10
    pv = g.preview_play(["M25S", "5D"])               # forced: no question
    assert pv["decision_kind"] is None and pv["attack"] == 10 and pv["damage"] == 10
    assert g.phase == PHASE_PLAY and g.decision is None and "declared_value" not in g.extra
    g.play(["M25H", "M25S"])
    assert declare_value_choice(g, g.legal_actions())["option"] == "5"
    # 2s finish the enemy exactly: the bot takes them
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=4)
    set_hand(g, ["M25H", "M25S", "9S"])
    g.play(["M25H", "M25S"])
    assert greedy_policy(g)["option"] == "2"


def test_cli_names_every_two_five_in_the_question(monkeypatch, capsys):
    from regicide import cli
    c, g = campaign_game()
    set_enemy(g, "Q", "C", hp=30)
    set_hand(g, ["M25H", "M25S", "9S"])
    g.play(["M25H", "M25S"])
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")
    assert cli.human_turn(g, None)
    out = capsys.readouterr().out
    assert "2/5♥ + 2/5♠: strength 2 or 5? Ana declares one value for all of them" in out
    assert "Strength 2" in out and "Strength 5" in out
    assert g.plays[-1].value == 10 and declared(g) == {"M25H": 5, "M25S": 5}


def test_random_and_greedy_games_with_all_four_two_fives_keep_their_cards():
    rng = random.Random(25)
    seen_kinds = set()
    for seed in range(8):
        c, g = campaign_game(number=1 + seed % 3, players=1 + seed % 2, seed=2600 + seed)
        policy = greedy_policy if seed % 2 else random_policy
        steps = 0
        while not g.is_over and steps < 600:
            act = policy(g, rng)
            if act.get("type") == "play":
                ids = act["cards"]
                n25 = sum(1 for x in ids if g.cards[x].has("twofive"))
                if n25 and len(ids) > 1:
                    seen_kinds.add("set" if not any(g.cards[x].is_ace for x in ids) else "companion")
            apply_action(g, act)
            ids_everywhere(g)
            steps += 1
    assert "set" in seen_kinds


# ---------------------------------------------------------------- the app
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def app(tmp_path, monkeypatch):
    tools = os.path.join(ROOT, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import fakeui
    fakeui.install()
    import ui
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app.screens import App, MenuScreen
    ui.set_screen_size(390, 844)
    a = App()
    a.settings["rules_card"] = False    # the mission rules card has its own tests
    a.show(MenuScreen(a))
    return a


def test_ui_plays_two_five_with_a_five_and_asks_once_for_two_two_fives(app):
    import ui
    from app.screens import DeclareOverlay, GameScreen
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.m_box_opened, camp.coins = True, 5
    camp.hire("merc_25H")
    camp.hire("merc_25S")
    app.save_campaign()
    app.start_attempt()
    gs, g = app.current, app.game
    assert isinstance(gs, GameScreen)
    set_enemy(g, "Q", "C", hp=30)
    set_hand(g, ["M25H", "5D", "M25S", "9S"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["M25H", "5D"])              # the owner's report: refused before
    # (the forecast is on the attack's card, a tap on the attack number)
    assert "Combos need" not in gs.message.text and "10 damage" in gs.forecast
    assert "declare" not in gs.forecast
    gs.hand.set_selection(["M25H", "M25S"])
    assert gs.forecast.startswith("2/5: you declare 2 or 5 (5 here).") and "10 damage" in gs.forecast
    b = ui.button(app, "Play")
    assert b.enabled
    ui.tap(app, *ui.root_point(app, b))
    assert g.decision["kind"] == "declare_value" and isinstance(gs.overlay, DeclareOverlay)
    texts = [v.text for v in ui.find(gs.overlay, lambda v: isinstance(v, ui.Label) and not v.hidden)]
    assert any("2/5♥ + 2/5♠: strength 2 or 5?" in t for t in texts)
    b = ui.button(app, "Strength 2")
    ui.tap(app, *ui.root_point(app, b))
    assert g.decision is None and g.plays[-1].value == 4 and g.enemy.hp == 26


# ---------------------------------------------------------------- owner's rulings (second playtest)
def test_mission8_a_two_five_moved_into_the_zone_counts_what_it_was_declared_as():
    """Owner: a 2/5 moved from play into mission 8's zone counts the value it was declared
    as, there and for the rest of its stay (not 2)."""
    from helpers import _pull, set_mission_enemy
    c, g = campaign_game(number=8, seed=811, mercs=("merc_25H",))
    for x in ("2C", "3C", "4C", "M25H"):
        _pull(g, x)
    g.mission_zone = ["PILA", "2C", "3C", "4C"]            # the next card must be a 5
    set_mission_enemy(g, "HEJ6", hp=4)
    set_hand(g, ["M25H", "9S", "8S"])
    g.play(["M25H"])
    assert g.decision["kind"] == "declare_value"
    g.decide({"type": "declare_value", "option": "5"})
    while g.phase == PHASE_DECIDE and g.decision["kind"] != "zone_build":
        g.decide(simple_decision(g))
    assert g.decision["kind"] == "zone_build" and g.decision["options"] == ["M25H"]
    g = round_trip(g)
    g.decide({"type": "zone_build", "card": "M25H"})
    settle(g)
    assert "M25H" in g.mission_zone and g.rules.zone_highest(g) == 5
    assert g.rules.attack_bonus(g) == 2 + 3 + 4 + 5          # its declaration was spent with the enemy, its value stays
    assert "declared_value" not in g.extra or "M25H" not in g.extra["declared_value"]
    g = round_trip(g)
    assert g.rules.attack_bonus(g) == 14
    # once it leaves the zone, the value is forgotten
    g.mission_zone.remove("M25H")
    g.discard.append("M25H")
    assert g.rules.card_strength(g, g.cards["M25H"]) == 2 and "held_value" not in g.extra
    ids_everywhere(g)


def test_solo_flute_a_two_five_is_declared_as_it_is_stored_and_plays_as_that_value():
    """Owner: storing a 2/5 on the solo Kinfolk Flute is a declaration; the flute's strength
    then follows it, and it plays from the flute as that value."""
    c, g = campaign_game(number=2, seed=2601, mercs=("merc_25H", "merc_25S"), relics=("flute",))
    set_hand(g, ["M25H", "5D", "M25S", "2C", "9S"])
    stores = [a for a in g.legal_actions() if a.get("name") == "flute_store" and a["card"] == "M25H"]
    assert sorted(a["value"] for a in stores) == [2, 5] and stores[-1]["label"].endswith("as a 5")
    with pytest.raises(IllegalAction):
        g.special({"type": "special", "name": "flute_store", "card": "M25H"})      # 2 or 5 must be said
    g.special([a for a in stores if a["value"] == 5][0])
    assert g.extra["flute"] == ["M25H"] and g.extra["held_value"] == {"M25H": 5}
    # only 5s may join it now (a later turn)
    g.extra["flute_turn"] = -1
    joins = [(a["card"], a.get("value")) for a in g.legal_actions() if a.get("name") == "flute_store"]
    assert ("M25S", 5) in joins and ("M25S", 2) not in joins and not any(cid == "2C" for cid, _ in joins)
    g = round_trip(g)
    # played from the flute with a 2/5 from hand: both 5s, no question
    ok, kind = g.check_play(["M25H", "M25S"])
    assert ok
    g.play(["M25H", "M25S"])
    assert g.decision is None or g.decision["kind"] != "declare_value"
    assert declared(g) == {"M25H": 5, "M25S": 5} and g.plays[-1].value == 10
    ids_everywhere(g)


def test_a_mage_adding_a_two_five_to_a_set_of_fives_still_asks():
    """Owner: a 2/5 a mage adds is declared (asked), even when the attack is a set of 5s."""
    from helpers import _pull, set_tavern_top
    c, g = campaign_game(number=9, seed=63, mercs=("merc_25H",))
    enemy_by_suit(g, "H", "Q", hp=60)
    set_hand(g, ["5M", "5S", "9S", "8S"])
    _pull(g, "M25H")
    set_tavern_top(g, ["M25H", "2C", "3C", "4C", "6C"])
    g.play(["5M", "5S"])
    g.decide({"type": "mage_pick", "card": "M25H"})
    assert g.decision["kind"] == "declare_value" and g.decision["cards"] == ["M25H"]
    assert sorted(a["option"] for a in g.legal_actions() if a.get("type") == "declare_value") == ["2", "5"]
