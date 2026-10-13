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
from regicide.engine import PHASE_CHOOSE_NEXT, PHASE_PLAY, PHASE_SUFFER  # noqa: E402
from regicide.rules import GameConfig  # noqa: E402


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
    _tap_button(app, "Legacy campaign")
    _tap_button(app, "Start a campaign")
    _tap_button(app, "Start")
    assert app.campaign is not None and store.has_campaign()
    _tap_button(app, "Start attempt 1")
    gs = _game_screen(app)
    assert app.in_campaign and app.game.config.rules_id == "legacy_m1"
    assert gs.mid_btn.title == "Jester attack"
    _rig_win(app)
    gs.refresh(after_action=False)
    first = app.game.hand()[0]
    gs.hand.set_selection([first.id])
    _tap_button(app, "Play")
    assert app.game.phase == "won"
    assert ui.button(app, "Campaign overview")
    assert app.campaign.mission == 2 and "flute" in app.campaign.relics
    _tap_button(app, "Campaign overview")
    assert ui.button(app, "Start attempt 1")
    _tap_button(app, "Start attempt 1")
    assert app.game.config.rules_id == "legacy_m2"
    assert app.game.enemy.name == "Hydra"
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
    _tap_button(app, "‹ Back")
    assert ui.button(app, "Start attempt 2")


def test_solo_jester_class_choice_overlay(app):
    app.new_campaign(1, ["Solo"])
    app.start_attempt()
    gs = _game_screen(app)
    _tap_button(app, "Jester attack")
    _tap_button(app, "♣ Warrior")
    assert app.game.solo_jesters == 1
    assert any("X1" in p.card_ids for p in app.game.plays)


def test_campaign_screens_render(app):
    from app.screens import CampaignScreen, MercenaryScreen, MissionListScreen, PartyScreen, CampaignLogScreen
    app.new_campaign(2, ["A", "B"])
    app.campaign.m_box_opened = True
    for scr in (CampaignScreen(app), MercenaryScreen(app), MissionListScreen(app), PartyScreen(app), CampaignLogScreen(app)):
        app.show(scr)
        assert ui.render(app).size[0] > 0
