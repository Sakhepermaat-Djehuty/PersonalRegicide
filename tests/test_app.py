"""Drive the Pythonista client headlessly through the fake ui."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402

from regicide.bots import greedy_policy, min_waste_discard  # noqa: E402
from regicide.engine import PHASE_CHOOSE_NEXT, PHASE_DECIDE, PHASE_PLAY, PHASE_SUFFER  # noqa: E402
from regicide.rules import GameConfig  # noqa: E402
from helpers import set_enemy, set_hand, set_tavern_top  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app.screens import App, MenuScreen
    ui.set_screen_size(390, 844)
    a = App()
    a.show(MenuScreen(a))
    return a


def _game_screen(app):
    from app.screens import GameScreen
    assert isinstance(app.current, GameScreen)
    return app.current


def _tap_button(app, title):
    b = ui.button(app, title)
    assert b.enabled, "button %s disabled" % title
    ui.tap(app, *ui.root_point(app, b))


def _tap_card(app, gs, card_id):
    v = gs.hand.views[card_id]
    ui.tap(app, *ui.root_point(app, v))


def test_menu_to_solo_game_and_play_with_taps(app):
    _tap_button(app, "Quick play (base Regicide)")
    _tap_button(app, "Solo game")
    _tap_button(app, "Start")
    gs = _game_screen(app)
    g = app.game
    assert g.n_players == 1 and g.phase == PHASE_PLAY
    # select the bot's suggestion by tapping cards
    act = greedy_policy(g)
    assert act["type"] == "play"
    for cid in act["cards"]:
        _tap_card(app, gs, cid)
    assert sorted(gs.hand.selected) == sorted(act["cards"])
    assert gs.right_btn.enabled
    _tap_button(app, "Play")
    assert g.turn >= 1
    # play through until the game ends, using the UI for every step
    steps = 0
    while not app.game.is_over and steps < 400:
        g = app.game
        gs = _game_screen(app)
        if g.phase == PHASE_PLAY:
            act = greedy_policy(g)
            if act["type"] == "play":
                gs.hand.set_selection(act["cards"])
                _tap_button(app, "Play")
            elif act["type"] == "solo_jester":
                _tap_button(app, "Jester power")
            else:
                _tap_button(app, "Yield")
        elif g.phase == PHASE_SUFFER:
            if g.hand_defence_value() < g.pending_damage:
                _tap_button(app, "Jester power")
            else:
                _tap_button(app, "Suggest")
                assert gs.right_btn.enabled
                _tap_button(app, "Discard")
        steps += 1
    assert app.game.is_over
    # result overlay present with both buttons
    assert ui.button(app, "Play again") is not None
    assert ui.button(app, "Main menu") is not None


def test_illegal_selection_disables_play_and_shows_reason(app):
    app.start_game(GameConfig(players=1), seed=2)
    gs = _game_screen(app)
    g = app.game
    hand = g.hand()
    # two different non-ace numbers can never be played together
    bad = [c for c in hand if not c.is_ace][:2]
    if len(bad) == 2 and bad[0].rank != bad[1].rank:
        gs.hand.set_selection([bad[0].id, bad[1].id])
        assert not gs.right_btn.enabled
        assert "same number" in gs.message.text or "Companion" in gs.message.text or "combo" in gs.message.text.lower()


def test_pass_and_play_handover_and_jester_choice(app):
    app.start_game(GameConfig(players=3, names=("Ana", "Ben", "Cy")), seed=5)
    gs = _game_screen(app)
    assert gs.overlay is not None and ui.button(app, "Show my hand")
    assert gs.hand.cards == []  # hidden until revealed
    _tap_button(app, "Show my hand")
    assert gs.hand.cards
    g = app.game
    jester = [c for c in g.cards.values() if c.is_jester][0]
    for p in g.players:
        if jester.id in p.hand:
            p.hand.remove(jester.id)
    if jester.id in g.tavern:
        g.tavern.remove(jester.id)
    g.players[0].hand.append(jester.id)
    gs.refresh(after_action=False)
    gs.hand.set_selection([jester.id])
    _tap_button(app, "Play")
    assert app.game.phase == PHASE_CHOOSE_NEXT
    _tap_button(app, "Cy (6 cards)")
    assert app.game.active == 2 and app.game.phase == PHASE_PLAY
    # Cy's hand is hidden behind the handover overlay
    assert ui.button(app, "Show my hand")


def test_autosave_and_continue(app, tmp_path):
    from app import store
    app.start_game(GameConfig(players=2), seed=9)
    gs = _game_screen(app)
    gs.reveal_hand()
    act = greedy_policy(app.game)
    assert act["type"] == "play"
    gs.hand.set_selection(act["cards"])
    _tap_button(app, "Play")
    assert store.has_game()
    saved = store.load_game()
    assert saved.to_dict() == app.game.to_dict()
    from app.screens import MenuScreen
    app.show(MenuScreen(app))
    _tap_button(app, "Quick play (base Regicide)")
    _tap_button(app, "Continue game")
    assert app.game.to_dict() == saved.to_dict()


def test_undo_restores_previous_state(app):
    app.start_game(GameConfig(players=1), seed=4)
    gs = _game_screen(app)
    before = app.game.to_dict()
    act = greedy_policy(app.game)
    gs.hand.set_selection(act["cards"])
    _tap_button(app, "Play")
    assert app.game.to_dict() != before
    _tap_button(app, "Menu")
    _tap_button(app, "Undo last action")
    assert app.game.to_dict() == before


def test_all_screens_render(app, tmp_path):
    from app.screens import HistoryScreen, NewGameScreen, RulesScreen, SettingsScreen
    for scr in (NewGameScreen(app, 4), RulesScreen(app), HistoryScreen(app), SettingsScreen(app)):
        app.show(scr)
        img = ui.render(app)
        assert img.size[0] > 0
    app.start_game(GameConfig(players=1), seed=1)
    ui.render(app, str(tmp_path / "game.png"))
    assert (tmp_path / "game.png").exists()


def test_small_screen_layout_keeps_hand_visible(app):
    ui.set_screen_size(375, 667)
    from app.screens import App, MenuScreen
    small = App()
    small.show(MenuScreen(small))
    small.start_game(GameConfig(players=1), seed=1)
    gs = _game_screen(small)
    bottom = max(v.y + v.height for v in gs.hand.subviews)
    assert gs.hand.y + bottom < gs.left_btn.y, "hand overlaps the action bar on a 667pt screen"
    ui.set_screen_size(390, 844)


# ---------------------------------------------------------------------------- campaign
def _rig_win(app):
    g = app.game
    g.castle = []
    g.enemy.hp = 1
    g.enemy.max_hp = 1


def test_campaign_flow_win_then_mission2(app):
    from app import store
    _tap_button(app, "New game")
    _tap_button(app, "Start")
    assert app.campaign is not None and store.has_campaign(app.campaign.slot)
    assert app.campaign.name.startswith("Campaign")
    _tap_button(app, "Next mission: start")
    gs = _game_screen(app)
    assert app.in_campaign and app.game.config.rules_id == "legacy_m1"
    assert gs.mid_btn.title == "Jester attack"
    _rig_win(app)
    gs.refresh(after_action=False)
    first = app.game.hand()[0]
    gs.hand.set_selection([first.id])
    _tap_button(app, "Play")
    assert app.game.phase == "won"
    assert ui.button(app, "Game menu")
    assert app.campaign.mission == 2 and "flute" in app.campaign.relics
    assert "m1_outcome" in app.campaign.lore_seen and "m2_intro" not in app.campaign.lore_seen
    _tap_button(app, "Game menu")
    # the corruption is a player choice: it blocks the next mission until made
    with pytest.raises(KeyError):
        ui.button(app, "Next mission: start")
    reward = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Reward:"))]
    assert reward and "corrupt" in reward[0].title
    ui.tap(app, *ui.root_point(app, reward[0]))
    from app.widgets import CardView
    confirm = ui.button(app, "Confirm")
    assert confirm and not confirm.enabled
    cards = ui.find(app, lambda v: isinstance(v, CardView))
    options = app.campaign.pending_choice()["options"]
    assert {v.card.id for v in cards} == set(options)
    ui.tap(app, *ui.root_point(app, cards[0]))
    assert ui.button(app, "Confirm").enabled
    chosen = cards[0].card.id
    _tap_button(app, "Confirm")
    assert app.campaign.corrupted == [chosen] and not app.campaign.pending
    assert store.load_campaign(app.campaign.slot).corrupted == [chosen]
    assert ui.button(app, "Next mission: start")
    _tap_button(app, "Next mission: start")
    assert "m2_intro" in app.campaign.lore_seen
    assert app.game.config.rules_id == "legacy_m2"
    assert app.game.enemy.name == "Hydra Head"
    # the flute button appears when a 2-5 is in hand
    gs = _game_screen(app)
    g = app.game
    smalls = [c for c in g.hand() if 2 <= c.value <= 5 and c.is_number]
    if not smalls:
        for cid in list(g.tavern):
            c = g.cards[cid]
            if 2 <= c.value <= 5 and c.is_number and not c.name:
                g.tavern.remove(cid)
                g.players[0].hand[0] = cid
                break
        gs.refresh(after_action=False)
    assert not gs.special_btn.hidden
    _tap_button(app, "Flute")
    labels = [b.title for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Store"))]
    assert labels
    ui.tap(app, *ui.root_point(app, ui.button(app, labels[0])))
    assert len(app.game.extra["flute"]) == 1
    assert any(v.badge == "flute" for v in gs.hand.views.values())


def test_campaign_loss_opens_mercenary_camp(app):
    app.new_campaign(1, ["Solo"])
    app.start_attempt()
    gs = _game_screen(app)
    app.game._lose("test loss")
    gs.refresh(after_action=False)
    assert app.campaign.coins == 1 and app.campaign.m_box_opened
    _tap_button(app, "Mercenary camp")
    hires = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title == "Hire" and v.enabled)]
    assert hires
    ui.tap(app, *ui.root_point(app, hires[0]))
    assert len(app.campaign.mercenaries) == 1 and app.campaign.coins == 0
    hired = app.campaign.mercenaries[0]
    # after a failure the hired mercenary may be swapped for another of the same cost
    _tap_button(app, "Swap")
    assert ui.button(app, "Cancel")
    assert not ui.find(app, lambda v: isinstance(v, ui.Button) and v.title == "Hire")
    # cancel returns to the camp with nothing changed
    _tap_button(app, "Cancel")
    assert app.campaign.mercenaries == [hired] and app.current.swapping is None
    assert ui.find(app, lambda v: isinstance(v, ui.Button) and v.title == "Hire")
    _tap_button(app, "Swap")
    takes = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title == "Take")]
    assert takes
    ui.tap(app, *ui.root_point(app, takes[0]))
    assert len(app.campaign.mercenaries) == 1 and app.campaign.mercenaries[0] != hired
    assert app.campaign.coins == 0
    _tap_button(app, "‹ Back")
    assert ui.button(app, "Retry mission (attempt 2)")
    _tap_button(app, "Retry mission (attempt 2)")
    # the hired mercenary is in this attempt's reserve and swaps are closed
    assert any(x.startswith("M") for x in app.game.cards) and not app.campaign.swaps_allowed


def test_solo_jester_class_choice_overlay(app):
    app.new_campaign(1, ["Solo"])
    app.start_attempt()
    gs = _game_screen(app)
    _tap_button(app, "Jester attack")
    _tap_button(app, "♣ Warrior")
    assert app.game.solo_jesters == 1
    assert any("X1" in p.card_ids for p in app.game.plays)


def _flute_attempt(app, names=("Ana", "Ben")):
    app.new_campaign(len(names), list(names))
    app.campaign.relics.append("flute")
    app.start_attempt()
    gs = _game_screen(app)
    g = app.game
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3D", "3H", "7C", "AS"], player=1)
    gs.reveal_hand()
    return gs, g


def test_kinfolk_flute_decision_overlay_add(app, tmp_path):
    from app import store
    from app.screens import DecisionOverlay, HandoverOverlay
    gs, g = _flute_attempt(app)
    gs.hand.set_selection(["3C"])
    assert "Kinfolk Flute" in gs.message.text and "6 damage" in gs.message.text
    _tap_button(app, "Play")
    assert g.phase == PHASE_DECIDE and g.deciding == 1
    # a handover-style overlay names the deciding player and the attack; the hand stays hidden
    assert isinstance(gs.overlay, DecisionOverlay) and gs.hand.cards == []
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert any("Ben: add to Ana's 3♣ attack?" in t for t in texts)
    assert ui.render(app).size[0] > 0
    assert store.load_attempt(app.campaign.slot).phase == PHASE_DECIDE   # autosaved mid-decision
    _tap_button(app, "Show my hand")
    assert gs.overlay is None and [c.id for c in gs.hand.cards] == ["3D", "3H", "7C", "AS"]
    assert gs.left_btn.title == "Pass" and gs.left_btn.enabled
    assert gs.right_btn.title == "Add" and not gs.right_btn.enabled
    assert gs.mid_btn.hidden
    assert "Ben: add to Ana's 3♣ attack?" in gs.message.text
    # only 3s are selectable
    assert gs.hand.views["7C"].dimmed and gs.hand.views["AS"].dimmed and not gs.hand.views["3D"].dimmed
    _tap_card(app, gs, "7C")
    assert gs.hand.selected == [] and not gs.right_btn.enabled
    _tap_card(app, gs, "3D")
    assert gs.hand.selected == ["3D"] and gs.right_btn.enabled
    assert "12 damage" in gs.message.text
    _tap_card(app, gs, "3H")
    assert gs.right_btn.enabled and "18 damage" in gs.message.text  # 3 + 3 + 3 = 9, doubled
    _tap_card(app, gs, "3H")
    _tap_button(app, "Add")
    assert g.phase == PHASE_SUFFER and g.active == 0 and g.enemy.hp == 8
    assert g.plays[0].card_ids == ["3C", "3D"] and "3D" not in g.players[1].hand
    # back to the attacker, whose hand is hidden again until the phone is passed
    assert isinstance(gs.overlay, HandoverOverlay) and ui.button(app, "Show my hand")
    assert store.load_attempt(app.campaign.slot).to_dict() == g.to_dict()
    _tap_button(app, "Show my hand")
    assert "Ben adds 3♦ (attack 6)" in gs.message_text and gs.right_btn.title == "Discard"
    assert "suffers 10 damage" in gs.message.text


def test_kinfolk_flute_decision_overlay_pass_and_undo(app):
    gs, g = _flute_attempt(app)
    before = g.to_dict()
    gs.hand.set_selection(["3C"])
    _tap_button(app, "Play")
    _tap_button(app, "Show my hand")
    _tap_button(app, "Pass")
    assert g.phase == PHASE_SUFFER and g.enemy.hp == 14 and g.plays[0].card_ids == ["3C"]
    assert "3D" in g.players[1].hand
    # undo steps back into the decision, then to before the play
    _tap_button(app, "Show my hand")
    _tap_button(app, "Menu")
    _tap_button(app, "Undo last action")
    assert app.game.phase == PHASE_DECIDE and app.game.deciding == 1
    _tap_button(app, "Show my hand")
    assert gs.right_btn.title == "Add"
    _tap_button(app, "Menu")
    _tap_button(app, "Undo last action")
    assert app.game.to_dict() == before


def test_kinfolk_flute_open_hands_shows_the_decision_overlay_once(app):
    gs, g = _flute_attempt(app)
    g.config.open_hands = True
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3C"])
    _tap_button(app, "Play")
    assert g.phase == PHASE_DECIDE
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert any("Ben: add to Ana's 3♣ attack?" in t for t in texts)
    assert not any(t == "Pass the phone to" for t in texts)
    _tap_button(app, "Show my hand")
    gs.hand.set_selection(["3D"])
    _tap_button(app, "Add")
    # open hands: no handover, straight to Ana's damage
    assert g.phase == PHASE_SUFFER and gs.overlay is None and gs.right_btn.title == "Discard"


def test_campaign_screens_render(app):
    from app.screens import (CampaignScreen, MercenaryScreen, MissionListScreen, PartyScreen, CampaignLogScreen,
                             MapScreen, ProgressScreen, LoreScreen, LoadGameScreen, QuickPlayScreen, MenuScreen)
    app.new_campaign(2, ["A", "B"], "Test game")
    app.campaign.m_box_opened = True
    for scr in (CampaignScreen(app), MercenaryScreen(app), MissionListScreen(app), PartyScreen(app), CampaignLogScreen(app),
                MapScreen(app), ProgressScreen(app), LoreScreen(app, local=True), LoreScreen(app, local=False),
                LoadGameScreen(app), QuickPlayScreen(app), MenuScreen(app)):
        app.show(scr)
        assert ui.render(app).size[0] > 0


def test_save_slots_load_and_delete(app, tmp_path):
    from app import store
    from app.screens import LoadGameScreen, MenuScreen
    app.new_campaign(1, ["Solo"], "First run")
    first = app.campaign.slot
    app.new_campaign(2, ["A", "B"], "Second run")
    second = app.campaign.slot
    assert first != second
    rows = store.list_campaigns()
    assert [r["name"] for r in rows] == ["Second run", "First run"] or len(rows) == 2
    app.show(MenuScreen(app))
    assert ui.button(app, "Continue: Second run")
    _tap_button(app, "Load game")
    opens = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title == "Open")]
    assert len(opens) == 2
    app.open_campaign(first)
    assert app.campaign.name == "First run" and app.settings["last_campaign"] == first
    # delete through the screen (alert answers 1 = Delete)
    import console
    console.script_answers(1)
    app.show(LoadGameScreen(app))
    dels = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title == "Delete")]
    ui.tap(app, *ui.root_point(app, dels[0]))
    assert len(store.list_campaigns()) == 1


def test_lore_is_global_and_survives_delete(app):
    from app import store
    app.new_campaign(1, ["Solo"], "Lore run")
    assert "m1_intro" in app.campaign.lore_seen
    assert any(e["id"] == "m1_intro" for e in app.lore_entries(local=True))
    assert any(e["id"] == "m1_intro" for e in app.lore_entries(local=False))
    store.delete_campaign(app.campaign.slot)
    assert "m1_intro" in store.global_lore_seen()


def test_map_screen_selection(app):
    from app.screens import MapScreen
    app.new_campaign(1, ["Solo"], "Map run")
    scr = MapScreen(app)
    app.show(scr)
    pts = scr.canvas._points()
    x, y = pts[0]
    ui.tap(app, scr.canvas.x + x, scr.canvas.y + y)
    assert scr.selected == 1 and "Call to Arms" in scr.caption.text
    x, y = pts[4]
    ui.tap(app, scr.canvas.x + x, scr.canvas.y + y)
    assert scr.selected == 5 and "Unknown" in scr.caption.text


def test_mission2_class_sticker_assignment_screen(app):
    from app import store
    from app.screens import CampaignScreen
    from regicide.campaign import party as P
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    # reach the end of mission 2 through the engine, then drive the reward screens
    g = camp.start_attempt(seed=31)
    g.castle = []
    g.enemy.hp = g.enemy.max_hp = 1
    g.play([g.active_player.hand[0]])
    camp.finish_attempt(g)
    camp.resolve_choice(camp.pending_choice()["options"][0])
    g = camp.start_attempt(seed=32)
    g.castle = []
    for cid in list(g.active_player.hand):
        info = g.preview_play([cid])
        if info.get("ok") and info.get("damage", 0) > 0:
            g.enemy.hp = g.enemy.max_hp = info["damage"]
            g.play([cid])
            break
    assert g.phase == "won"
    camp.finish_attempt(g)
    app.save_campaign()
    app.show(CampaignScreen(app))
    # first the corruption choice
    reward = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Reward:"))]
    assert reward and "corrupt" in reward[0].title
    ui.tap(app, *ui.root_point(app, reward[0]))
    from app.widgets import CardView
    cards = ui.find(app, lambda v: isinstance(v, CardView))
    ui.tap(app, *ui.root_point(app, cards[0]))
    _tap_button(app, "Confirm")
    assert len(app.campaign.corrupted) == 2
    # then the class stickers
    reward = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Reward:"))]
    assert reward and "stickers" in reward[0].title
    ui.tap(app, *ui.root_point(app, reward[0]))
    step = app.campaign.pending_choice()
    assert step["kind"] == "choice_classes"
    assert not ui.button(app, "Confirm").enabled
    names = {"H": "Cleric", "D": "Bard", "C": "Warrior", "S": "Paladin"}
    shown = ui.find(app, lambda v: isinstance(v, CardView))
    assert [v.card.id for v in shown] == step["cards"]
    # a card's own class is disabled on its row
    rows = {}
    for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title in names.values()):
        rows.setdefault(round(b.y), []).append(b)
    assert len(rows) == 4
    for (y, btns), cid in zip(sorted(rows.items()), step["cards"]):
        own = P.find(app.campaign.party, cid)["suits"][0]
        for b in btns:
            assert b.enabled == (b.title != names[own])
    # pick a legal assignment up front (greedy row by row can dead-end), then tap it
    import itertools
    plan = None
    for perm in itertools.permutations(step["classes"], len(step["cards"])):
        if all(s not in P.find(app.campaign.party, cid)["suits"] for cid, s in zip(step["cards"], perm)):
            plan = dict(zip(step["cards"], perm))
            break
    assert plan is not None
    chosen = {}
    for i, cid in enumerate(step["cards"]):
        btns = sorted(ui.find(app, lambda v: isinstance(v, ui.Button) and v.title in names.values()), key=lambda b: (round(b.y), b.x))
        row = [b for b in btns if round(b.y) == sorted({round(x.y) for x in btns})[i]]
        pick = [b for b in row if b.title == names[plan[cid]]][0]
        assert pick.enabled
        ui.tap(app, *ui.root_point(app, pick))
        chosen[cid] = pick.title
    assert ui.button(app, "Confirm").enabled
    # a class chosen on one row is disabled on the others
    btns = ui.find(app, lambda v: isinstance(v, ui.Button) and v.title in names.values())
    for title in set(chosen.values()):
        assert sum(1 for b in btns if b.title == title and b.enabled) == 1
    _tap_button(app, "Confirm")
    assert not app.campaign.pending
    for cid, title in chosen.items():
        suits = P.find(app.campaign.party, cid)["suits"]
        assert len(suits) == 2 and names[suits[1]] == title
    assert store.load_campaign(app.campaign.slot).pending == []


def test_swap_button_only_when_a_same_cost_alternative_exists(app):
    from app.screens import MercenaryScreen
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.m_box_opened = True
    camp.coins = 20
    camp.swaps_allowed = True
    camp.hire("merc_jester_1")
    camp.hire("merc_jester_2")  # both cost-5 mercenaries hired: nothing to swap them for
    camp.hire("merc_12H")
    app.show(MercenaryScreen(app))
    swaps = ui.find(app, lambda v: isinstance(v, ui.Button) and v.title == "Swap")
    assert len(swaps) == 1
    camp.swaps_allowed = False  # swaps close once an attempt starts
    app.show(MercenaryScreen(app))
    assert not ui.find(app, lambda v: isinstance(v, ui.Button) and v.title == "Swap")


def test_mission3_zone_strip_and_exact_kill_pick_overlay(app):
    from app.screens import PickOverlay
    from regicide.campaign import missions as M
    from regicide.campaign import party as P
    from regicide.engine import PHASE_DECIDE
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.mission = 3
    camp.completed = [1, 2]
    P.add_card(camp.party, dict(M.HIGH_ARCANA))
    app.save_campaign()
    app.show(__import__("app.screens", fromlist=["CampaignScreen"]).CampaignScreen(app))
    assert ui.button(app, "Next mission: start")
    _tap_button(app, "Next mission: start")
    gs = _game_screen(app)
    g = app.game
    assert "ARC25" not in g.cards and g.enemy.name == "Instructor"
    assert not gs.zone.hidden and gs.zone.title.startswith("Mission zone")
    set_hand(g, ["9S", "8H", "7D", "5C", "6D"])
    set_tavern_top(g, ["4H", "3S", "2D"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["9S"])
    _tap_button(app, "Play")
    gs.hand.set_selection(["7D"])
    _tap_button(app, "Discard")
    assert g.mission_zone == ["4H"] and "immune to Clerics" in gs.zone.title
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert any("mission zone" in t for t in texts)
    # exact kill: the pick overlay offers each zone card
    g.enemy.hp = 10
    set_hand(g, ["5C", "2D", "AS"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["5C"])
    _tap_button(app, "Play")
    assert g.phase == PHASE_DECIDE and isinstance(gs.overlay, PickOverlay)
    assert ui.render(app).size[0] > 0
    btns = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Rescue"))]
    assert [b.title for b in btns] == ["Rescue 4♥ to the discard pile"]
    ui.tap(app, *ui.root_point(app, btns[0]))
    assert g.phase == "play" and g.enemies_defeated == 1 and "4H" in g.discard and gs.overlay is None
    assert g.mission_zone == [] and "(empty)" in gs.zone.title


def test_mission11_setup_choice_shows_before_the_first_attempt(app, monkeypatch):
    from app.screens import CampaignScreen
    from regicide.campaign import party as P
    from regicide.campaign.missions import mission as mission_info
    monkeypatch.setitem(mission_info(11), "playable", True)   # setup choices are queued for playable missions
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.mission = 11
    camp.completed = list(range(1, 11))
    for cid in ("2S", "6C"):
        P.add_flag(camp.party, cid, "corrupted")
        camp.corrupted.append(cid)
    app.save_campaign()
    app.show(CampaignScreen(app))
    # the setup card's choice is queued and offered instead of the start button
    with pytest.raises(KeyError):
        ui.button(app, "Next mission: start")
    setup = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Mission setup:"))]
    assert setup and "rip up" in setup[0].title
    ui.tap(app, *ui.root_point(app, setup[0]))
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert any(t == "Mission setup" for t in texts)
    from app.widgets import CardView
    cards = ui.find(app, lambda v: isinstance(v, CardView))
    assert [v.card.id for v in cards] == ["6C"]
    ui.tap(app, *ui.root_point(app, cards[0]))
    _tap_button(app, "Confirm")
    assert P.find(app.campaign.party, "6C") is None and app.campaign.flags.get("vine_ripped")
    assert not app.campaign.pending
    # nothing is queued again: the start button is back
    assert ui.button(app, "Next mission: start")
