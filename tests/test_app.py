"""Drive the Pythonista client headlessly through the fake ui."""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402
from regicide.campaign import party as P  # noqa: E402

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
    a.settings["rules_card"] = False    # the rules card has its own tests (tests/test_playtest_ui.py)
    a.show(MenuScreen(a))
    return a


def _game_screen(app):
    from app.screens import GameScreen
    assert isinstance(app.current, GameScreen)
    return app.current


def _tap_button(app, title):
    try:
        b = ui.button(app, title)
    except KeyError:
        # "Discard" also finds the suffer step's "Discard 8/10" (the tally rides on the button)
        b = [v for v in ui.find(app, lambda v: isinstance(v, ui.Button) and not v.hidden
                                and re.match(re.escape(title) + r" \d+/\d+$", v.title or ""))][0]
    assert b.enabled, "button %s disabled" % title
    ui.tap(app, *ui.root_point(app, b))


def _pv(gs):
    """What the selected cards would do, as the table shows it (no running text): the
    ``Game.preview_play`` dict behind the header's numbers and the attack card's rows; {}
    with nothing (or nothing legal) selected."""
    return gs.enemy.projection or {}


def _rows(gs):
    """The attack card's rows for the selection, {name: value} (``forecast_rows``)."""
    from app.screens import forecast_rows
    pv = gs.enemy.projection
    return dict(forecast_rows(gs.game, pv)) if pv else {}


def _zone_ids(gs):
    """The mission zone's row on the table (oldest first): the row has no title, the cards
    and the header (the enemy's immunity icons) say what the zone does."""
    return [c.id for c in gs.zone.cards]


def _attack_card(app, gs):
    """The attack's card (a tap left of the enemy's card in the header): its labels' texts,
    top to bottom. The card is closed again."""
    from app.screens import CardPopup
    ui.tap(app, gs.enemy.x + 10, ui.root_point(app, gs.enemy)[1])
    pops = [v for v in gs.subviews if isinstance(v, CardPopup)]
    assert pops, "no attack card"
    texts = [v.text for v in ui.find(pops[-1], lambda v: isinstance(v, ui.Label) and not v.hidden)]
    pops[-1].close()
    return texts


def _logged(g):
    """The engine's game log (Menu > Game log): what an action did lives there, the table
    carries no running text."""
    return "\n".join(g.log)


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


def test_illegal_selection_disables_play_and_says_nothing(app):
    app.start_game(GameConfig(players=1), seed=2)
    gs = _game_screen(app)
    g = app.game
    hand = g.hand()
    # two different non-ace numbers can never be played together
    bad = [c for c in hand if not c.is_ace][:2]
    if len(bad) == 2 and bad[0].rank != bad[1].rank:
        gs.hand.set_selection([bad[0].id, bad[1].id])
        assert not gs.right_btn.enabled
        # nothing forecast: the header keeps the enemy's own numbers, the attack card adds no rows
        assert gs.enemy.projection is None and _rows(gs) == {} and not gs.enemy.warn


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
    # the corruption is random (pack C in a themeless deck): no choice blocks the next mission
    assert len(app.campaign.corrupted) == 1 and not app.campaign.pending
    assert store.load_campaign(app.campaign.slot).corrupted == app.campaign.corrupted
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
    # solo: the Flute takes the Yield button's place (a solo player never yields)
    assert gs.left_btn.title == "Flute" and gs.left_btn.enabled and gs.special_btn.hidden
    _tap_button(app, "Flute")
    labels = [b.title for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Store"))]
    assert labels
    ui.tap(app, *ui.root_point(app, ui.button(app, labels[0])))
    assert len(app.game.extra["flute"]) == 1
    assert any(v.badge == "flute" for v in gs.hand.views.values())


def _texts(view):
    return [v.text for v in ui.find(view, lambda v: isinstance(v, ui.Label))]


def _merc_card(app, mid):
    """Tap a mercenary's card in the camp; returns its card pop-up."""
    from app.screens import CardPopup
    v = app.current.card_views[mid]
    ui.tap(app, *ui.root_point(app, v))
    popups = ui.find(app, lambda x: isinstance(x, CardPopup))
    assert len(popups) == 1
    return popups[0]


def test_campaign_loss_opens_mercenary_camp(app):
    from app.screens import CardPopup, MercenaryScreen
    app.new_campaign(1, ["Solo"])
    app.start_attempt()
    gs = _game_screen(app)
    app.game._lose("test loss")
    gs.refresh(after_action=False)
    assert app.campaign.coins == 1 and app.campaign.m_box_opened
    _tap_button(app, "Mercenary camp")
    ms = app.current
    assert isinstance(ms, MercenaryScreen) and len(ms.card_views) == 14
    # every mercenary is a card, shaded while in the box, with its cost in coins
    assert all(v.shaded and not v.selected for v in ms.card_views.values())
    assert [ms.card_views[m].coins for m in ("merc_12H", "merc_25D", "merc_19_1", "merc_ace_1", "merc_jester_1")] == [1, 1, 3, 3, 5]
    assert ui.render(app).size[0] > 0
    # every mercenary has its card: its name, icons and what it is
    from app.widgets import PlayingCardFace, card_color
    from regicide.campaign.mercenaries import MERCENARIES
    for merc in MERCENARIES:
        popup = _merc_card(app, merc["id"])
        face = ui.find(popup, lambda v: isinstance(v, PlayingCardFace))[0]
        assert merc["name"] in _texts(face) and any("Cost: %d coin" % merc["cost"] in t for t in _texts(face))
        if merc["id"] == "merc_ace_1":
            # the Wild Animal: all four class icons, its rank alone in the corner, a neutral edge
            assert _texts(face)[:4] == ["♥", "♦", "♣", "♠"] and [t for t, _ in face.corner] == ["A"]
            assert face.edge == card_color(P.to_card(merc["card"])) and any("Wild Animal" in t for t in _texts(face))
        ui.tap(app, 4, app.height - 4)                  # a tap beside the card closes it
        assert not ui.find(app, lambda v: isinstance(v, CardPopup))
    # a Jester costs 5: its card says so and Hire is off
    popup = _merc_card(app, "merc_jester_1")
    hire = [v for v in ui.find(popup, lambda v: isinstance(v, ui.Button)) if v.title == "Hire for 5 coins"]
    assert len(hire) == 1 and not hire[0].enabled
    ui.tap(app, *ui.root_point(app, hire[0]))
    assert app.campaign.mercenaries == [] and app.campaign.coins == 1
    assert any("not enough coins (1)" in t for t in _texts(popup))
    # a tap on the card, or in the gap above its buttons, leaves it open
    face = popup.face
    ui.tap(app, *ui.root_point(app, face))
    ui.tap(app, face.x + 20, face.y + face.height + 6)
    assert ui.find(app, lambda v: isinstance(v, CardPopup))
    _tap_button(app, "Close")
    assert not ui.find(app, lambda v: isinstance(v, CardPopup))
    popup = _merc_card(app, "merc_12H")
    assert "12 Cleric" in _texts(popup) and any("Cost: 1 coin." in t for t in _texts(popup))
    assert ui.render(app).size[0] > 0
    _tap_button(app, "Hire for 1 coin")
    assert app.campaign.mercenaries == ["merc_12H"] and app.campaign.coins == 0
    ms = app.current
    assert not ms.card_views["merc_12H"].shaded and ms.card_views["merc_12H"].selected
    # after a failure the hired mercenary may be swapped for another of the same cost
    _merc_card(app, "merc_12H")
    _tap_button(app, "Swap")
    ms = app.current
    assert ms.swapping == "merc_12H" and ui.button(app, "Cancel")
    # only the mercenaries that can be taken have the gold border; the others fade
    assert ms.card_views["merc_12D"].selected and not ms.card_views["merc_19_1"].selected
    assert not ms.card_views["merc_12H"].selected and ms.card_views["merc_12H"].badge == "swap"
    assert ms.card_views["merc_19_1"].alpha < 1 and ms.card_views["merc_25D"].alpha == 1
    # cancel returns to the camp with nothing changed
    _tap_button(app, "Cancel")
    assert app.campaign.mercenaries == ["merc_12H"] and app.current.swapping is None
    # so does a tap on the card being swapped
    popup = _merc_card(app, "merc_12H")
    assert "Hired · until mission 1 is won" in _texts(popup)
    _tap_button(app, "Swap")
    ui.tap(app, *ui.root_point(app, app.current.card_views["merc_12H"]))
    assert app.current.swapping is None and not ui.find(app, lambda v: isinstance(v, CardPopup))
    _merc_card(app, "merc_12H")
    _tap_button(app, "Swap")
    # a mercenary of another cost cannot be taken
    ui.tap(app, *ui.root_point(app, app.current.card_views["merc_19_1"]))
    assert not ui.find(app, lambda v: isinstance(v, CardPopup)) and app.current.swapping == "merc_12H"
    _merc_card(app, "merc_25D")
    _tap_button(app, "Take it in place of 12 Cleric")
    assert app.campaign.mercenaries == ["merc_25D"] and app.campaign.coins == 0 and app.current.swapping is None
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
    # forecast as if nobody adds (the Kinfolk Flute's decision comes first): 3, doubled
    assert _pv(gs)["decision_kind"] == "flute_add" and _pv(gs)["damage"] == 6 and _rows(gs)["Damage"] == "6"
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
    # Ben decides on the Kinfolk Flute for Ana's 3♣ (the decision names itself nowhere on the table)
    assert g.decision["kind"] == "flute_add" and g.deciding == 1
    assert g.plays[-1].player == 0 and g.plays[-1].card_ids == ["3C"]
    # only 3s are selectable
    assert gs.hand.views["7C"].shaded and gs.hand.views["AS"].shaded and not gs.hand.views["3D"].shaded
    _tap_card(app, gs, "7C")
    assert gs.hand.selected == [] and not gs.right_btn.enabled
    _tap_card(app, gs, "3D")
    assert gs.hand.selected == ["3D"] and gs.right_btn.enabled
    assert _pv(gs)["damage"] == 12 and _pv(gs)["attack"] == 6 and _rows(gs)["Damage"] == "12"
    _tap_card(app, gs, "3H")
    assert gs.right_btn.enabled and _pv(gs)["damage"] == 18  # 3 + 3 + 3 = 9, doubled
    _tap_card(app, gs, "3H")
    _tap_button(app, "Add")
    assert g.phase == PHASE_SUFFER and g.active == 0 and g.enemy.hp == 8
    assert g.plays[0].card_ids == ["3C", "3D"] and "3D" not in g.players[1].hand
    # back to the attacker, whose hand is hidden again until the phone is passed
    assert isinstance(gs.overlay, HandoverOverlay) and ui.button(app, "Show my hand")
    assert store.load_attempt(app.campaign.slot).to_dict() == g.to_dict()
    _tap_button(app, "Show my hand")
    assert "Ben adds 3♦ to the attack (Kinfolk Flute): strength 6." in _logged(g)
    assert gs.right_btn.title.startswith("Discard")
    assert gs.right_btn.title == "Discard 0/10"


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
    assert g.phase == PHASE_SUFFER and gs.overlay is None and gs.right_btn.title.startswith("Discard")


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
    assert len(app.campaign.corrupted) == 2      # both corruptions were random, no choice
    from app.widgets import CardView
    # the class stickers
    reward = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Reward:"))]
    assert reward and "stickers" in reward[0].title
    ui.tap(app, *ui.root_point(app, reward[0]))
    # a card explains the reward first (what is revealed, how stickers work)
    from app.screens import CardPopup
    popup = ui.find(app, lambda v: isinstance(v, CardPopup))
    assert popup and any("Give each one class sticker" in v.text for v in ui.find(popup[0], lambda v: isinstance(v, ui.Label)))
    _tap_button(app, "Choose")
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

    def swaps(mid):
        popup = _merc_card(app, mid)
        found = ui.find(popup, lambda v: isinstance(v, ui.Button) and v.title == "Swap")
        popup.close()
        return len(found)

    assert swaps("merc_jester_1") == 0 and swaps("merc_12H") == 1
    camp.swaps_allowed = False  # swaps close once an attempt starts
    app.show(MercenaryScreen(app))
    assert swaps("merc_12H") == 0


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
    assert not gs.zone.hidden and _zone_ids(gs) == g.mission_zone == []
    set_hand(g, ["9S", "8H", "7D", "5C", "6D"])
    set_tavern_top(g, ["4H", "3S", "2D"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["9S"])
    _tap_button(app, "Play")
    gs.hand.set_selection(["7D"])
    _tap_button(app, "Discard")
    # the 4♥ lies in the zone's row and makes the enemy immune to clerics (an icon on its card)
    assert g.mission_zone == ["4H"] and _zone_ids(gs) == ["4H"]
    assert "H" not in g.enemy.suits and "H" in g.rules.immune_suits(g) and "H" in gs.enemy.card_view.center_icons
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "End of turn: 4♥ goes into the mission zone." in _logged(g)   # (the game log; the table says nothing)
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
    assert g.mission_zone == [] and not gs.zone.hidden and _zone_ids(gs) == [] and not gs.zone.overflows()


# ---------------------------------------------------------------------------- mages
def _mage_attempt(app, names=("Solo",), relics=("emblem",), corrupted=()):
    from regicide.campaign import missions as M
    from regicide.campaign import party as P
    app.new_campaign(len(names), list(names))
    for d in M.MAGE_DECK:
        P.add_card(app.campaign.party, dict(d))
    for cid in corrupted:
        P.add_flag(app.campaign.party, cid, "corrupted")
    app.campaign.relics.extend(relics)
    app.start_attempt()
    gs = _game_screen(app)
    return gs, app.game


def test_mage_peek_overlay_then_emblem_keep_overlay(app):
    from app import store
    from app.screens import EmblemKeepOverlay, MagePeekOverlay
    from app.widgets import CardStrip
    gs, g = _mage_attempt(app, corrupted=("7D",))
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S", "8S", "7S", "6S"])
    set_tavern_top(g, ["6C", "7D", "4H", "3S", "2S", "AD"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["5M"])
    # the mage reveals 5 cards from the reserve (never which): forecast as if nothing were added
    assert _pv(gs)["mage_peeks"][0] == 5 and _pv(gs)["damage"] == 5 and _rows(gs)["Damage"] == "5"
    assert g.tavern[:6] == ["6C", "7D", "4H", "3S", "2S", "AD"]       # the preview left the reserve alone
    _tap_button(app, "Play")
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "mage_peek"
    assert isinstance(gs.overlay, MagePeekOverlay)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Mage: 5 cards revealed" in texts
    strip = ui.find(gs.overlay, lambda v: isinstance(v, CardStrip))[0]
    assert [c.id for c in strip.cards] == ["6C", "7D", "4H", "3S", "2S"] and strip.dimmed == ["7D"]
    assert len(strip.subviews) == 5 and [v.dimmed for v in strip.subviews] == [False, True, False, False, False]
    adds = [b.title for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Add"))]
    assert adds == ["Add 6♣ to the attack", "Add 4♥ to the attack", "Add 3♠ to the attack", "Add 2♠ to the attack"]
    assert ui.render(app).size[0] > 0
    assert store.load_attempt(app.campaign.slot).phase == PHASE_DECIDE  # autosaved mid-peek
    _tap_button(app, "Add 6♣ to the attack")
    assert g.plays[0].card_ids == ["5M", "6C"] and g.plays[0].value == 11
    assert "Solo adds 6♣ to the attack (Mage): strength 11." in _logged(g)
    assert "Azure Emblem: Solo may put one of the other revealed cards back on top of the reserve" in _logged(g)
    # Azure Emblem, solo: one of the other revealed cards may go back on top of the reserve
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "emblem_keep"
    assert isinstance(gs.overlay, EmblemKeepOverlay)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Azure Emblem" in texts
    keeps = [b.title for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Keep"))]
    assert keeps == ["Keep 7♦ on top of the reserve", "Keep 4♥ on top of the reserve",
                     "Keep 3♠ on top of the reserve", "Keep 2♠ on top of the reserve"]
    assert ui.button(app, "Discard them all")
    assert ui.render(app).size[0] > 0
    _tap_button(app, "Keep 4♥ on top of the reserve")
    assert g.tavern[:2] == ["4H", "AD"] and {"7D", "3S", "2S"} <= set(g.discard)
    assert g.decision is None and g.phase == PHASE_SUFFER and g.enemy.hp == 40 - 22
    assert gs.overlay is None and gs.right_btn.title.startswith("Discard")
    assert "Azure Emblem: Solo puts 4♥ back on top of the reserve deck." in _logged(g)
    assert "22 damage to King of H (18/40)." in _logged(g)
    assert store.load_attempt(app.campaign.slot).to_dict() == g.to_dict()
    # undo steps back into the keep decision, then (through the overlay's own menu button,
    # the decision cannot be dismissed) into the peek; Resume brings the overlay back
    _tap_button(app, "Menu")
    _tap_button(app, "Undo last action")
    assert app.game.decision["kind"] == "emblem_keep" and isinstance(gs.overlay, EmblemKeepOverlay)
    _tap_button(app, "Game menu")
    _tap_button(app, "Resume")
    assert isinstance(gs.overlay, EmblemKeepOverlay)
    _tap_button(app, "Game menu")
    _tap_button(app, "Undo last action")
    assert app.game.decision["kind"] == "mage_peek" and isinstance(gs.overlay, MagePeekOverlay)
    assert ui.render(app).size[0] > 0


def test_mage_peek_overlay_with_nothing_to_add(app):
    from app.screens import MagePeekOverlay
    gs, g = _mage_attempt(app, relics=(), corrupted=("7D",))
    set_enemy(g, "K", "H")
    set_hand(g, ["AM", "9S", "8S", "7S", "6S"])
    set_tavern_top(g, ["7D"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["AM"])
    assert _pv(gs)["mage_peeks"][0] == 1               # the short reserve: the mage reveals 1 card
    _tap_button(app, "Play")
    assert isinstance(gs.overlay, MagePeekOverlay)
    assert not ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Add"))
    _tap_button(app, "Nothing to add")
    assert g.decision is None and g.phase == PHASE_SUFFER and g.enemy.hp == 39 and "7D" in g.discard
    assert "Mage: nothing may join the attack; 7♦ to the discard pile." in _logged(g)


def test_emblem_place_handover_flow_for_two_players(app):
    from app.screens import DecisionOverlay, HandoverOverlay, MagePeekOverlay
    gs, g = _mage_attempt(app, names=("Ana", "Ben"))
    set_enemy(g, "J", "H")
    set_hand(g, ["5M", "9S", "8S"], player=0)
    set_hand(g, ["7C", "3D", "AS"], player=1)
    set_tavern_top(g, ["6C", "4H", "3S", "2S", "2D"])
    gs.reveal_hand()
    gs.hand.set_selection(["5M"])
    # the others may place cards for the Azure Emblem first, then the mage reveals 5
    assert _pv(gs)["decision_kind"] == "emblem_place" and _pv(gs)["mage_peeks"][0] == 5
    _tap_button(app, "Play")
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "emblem_place" and g.deciding == 1
    # Ben is asked first, flute-style: a handover panel, then his hand
    assert isinstance(gs.overlay, DecisionOverlay) and gs.hand.cards == []
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert any("Ben: place a card for Ana's 5⚝ attack?" in t for t in texts)
    assert any(t.startswith("Azure Emblem") for t in texts)
    assert ui.render(app).size[0] > 0
    _tap_button(app, "Show my hand")
    assert gs.overlay is None and [c.id for c in gs.hand.cards] == ["7C", "3D", "AS"]
    assert gs.left_btn.title == "Pass" and gs.left_btn.enabled
    assert gs.right_btn.title == "Place" and not gs.right_btn.enabled and gs.mid_btn.hidden
    # Ben's hand decides the Azure Emblem for Ana's attack (no caption: the buttons say it)
    assert g.decision["kind"] == "emblem_place" and g.deciding == 1 and gs.shown_player == 1
    assert g.plays[-1].player == 0 and g.plays[-1].card_ids == ["5M"]
    _tap_card(app, gs, "7C")
    assert gs.hand.selected == ["7C"] and gs.right_btn.enabled and g.decision["kind"] == "emblem_place"
    _tap_card(app, gs, "3D")                       # only one card may be placed
    assert gs.hand.selected == ["3D"] and gs.right_btn.enabled
    _tap_card(app, gs, "3D")
    assert gs.hand.selected == [] and not gs.right_btn.enabled
    _tap_card(app, gs, "7C")
    _tap_button(app, "Place")
    # Ben was the last to ask, so the mage looks at once: his card is the first revealed
    assert "7C" not in g.players[1].hand and g.tavern[0] == "2D"
    assert "Ben places a card from hand on top of the reserve deck (Azure Emblem)." in _logged(g)
    # the phone goes back to Ana before her secret look
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "mage_peek" and g.deciding == 0
    assert isinstance(gs.overlay, HandoverOverlay) and gs.hand.cards == []
    _tap_button(app, "Show my hand")
    assert isinstance(gs.overlay, MagePeekOverlay)
    assert g.decision["revealed"] == ["7C", "6C", "4H", "3S", "2S"]
    assert ui.render(app).size[0] > 0
    _tap_button(app, "Add 7♣")          # five options: two columns with short titles
    # (5 + 7) doubled kills the Justicar; the mage attack is banished and Ana plays on
    assert g.enemies_defeated == 1 and "5M" in g.banished and "7C" in g.banished
    assert g.phase == PHASE_PLAY and g.active == 0 and gs.overlay is None

def test_mission_setup_choices_are_offered_before_the_first_attempt(app, monkeypatch):
    """Setup cards that need a decision appear as a 'Mission setup' step (none of the
    twelve missions needs one now that corruption is random, so a fake step is queued)."""
    from app.screens import CampaignScreen
    from regicide.campaign import missions as M
    from regicide.campaign.missions import mission as mission_info
    monkeypatch.setitem(mission_info(11), "playable", True)
    real = M.start_steps

    def fake_steps(camp, number):
        steps = real(camp, number)
        if number == 11 and not camp.flags.get("fake_done"):
            steps.append({"kind": "choice_suit", "phase": "setup", "suit": "M", "options": ["2H", "2S"],
                          "label": "test: a setup sticker"})
        return steps
    monkeypatch.setattr(M, "start_steps", fake_steps)
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.mission = 11
    camp.completed = list(range(1, 11))
    app.save_campaign()
    app.show(CampaignScreen(app))
    with pytest.raises(KeyError):
        ui.button(app, "Next mission: start")
    setup = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Mission setup:"))]
    assert setup and "sticker" in setup[0].title
    ui.tap(app, *ui.root_point(app, setup[0]))
    _tap_button(app, "Choose")
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert any(t == "Mission setup" for t in texts)
    from app.widgets import CardView
    cards = ui.find(app, lambda v: isinstance(v, CardView))
    assert [v.card.id for v in cards] == ["2H", "2S"]
    ui.tap(app, *ui.root_point(app, cards[1]))
    camp.flags["fake_done"] = True       # the "card" is used up once resolved
    _tap_button(app, "Confirm")
    assert P.find(app.campaign.party, "2S")["suits"] == ["S", "M"] and not app.campaign.pending
    assert ui.button(app, "Next mission: start")


# ---------------------------------------------------------------------------- missions 4 to 6
def _mission_attempt(app, number, names=("Solo",), relics=(), beast=None):
    from regicide.campaign import missions as M
    from regicide.campaign import party as P
    app.new_campaign(len(names), list(names))
    camp = app.campaign
    camp.mission = number
    camp.completed = list(range(1, number))
    camp.relics.extend(relics)
    if number >= 5:
        P.add_card(camp.party, dict(M.GORAN))
        camp.flags["beasts"] = True
        camp.set_beast(beast)
    if number >= 6:
        P.add_card(camp.party, dict(M.MYLA))
    for d in M.MAGE_DECK:
        P.add_card(camp.party, dict(d))
    app.save_campaign()
    app.start_attempt()
    gs = _game_screen(app)
    return gs, app.game


def test_reaver_count_grid_then_pick_overlay(app):
    from app import store
    from app.screens import ReaverCountOverlay, ReaverPickOverlay
    from app.widgets import CardStrip
    from helpers import set_mission_enemy
    gs, g = _mission_attempt(app, 5)
    assert not gs.zone.hidden and _zone_ids(gs) == g.mission_zone
    set_mission_enemy(g, "GRJH", hp=100)
    set_hand(g, ["5C", "5R", "9S", "8S", "7S"])
    set_tavern_top(g, ["7H", "2D", "3D"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["5C", "5R"])
    # the forecast counts the reaver's addition as 0: 10, doubled twice
    assert _pv(gs)["decision_kind"] == "reaver_count" and _pv(gs)["damage"] == 40
    assert _pv(gs)["powers"]["R"]["added"] == 0 and _rows(gs)["Reaver"] == "+0 ×2"
    assert g.tavern[:3] == ["7H", "2D", "3D"]
    _tap_button(app, "Play")
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "reaver_count"
    assert isinstance(gs.overlay, ReaverCountOverlay)
    numbers = [b.title for b in ui.find(gs.overlay, lambda v: isinstance(v, ui.Button) and v.title.isdigit())]
    assert numbers == [str(n) for n in range(1, len(g.tavern) + 1)]   # a grid of counts, five per row
    assert ui.render(app).size[0] > 0
    assert store.load_attempt(app.campaign.slot).phase == PHASE_DECIDE
    _tap_button(app, "2")
    assert g.decision["kind"] == "reaver_pick" and g.decision["revealed"] == ["7H", "2D"]
    assert isinstance(gs.overlay, ReaverPickOverlay)
    strip = ui.find(gs.overlay, lambda v: isinstance(v, CardStrip))[0]
    assert [c.id for c in strip.cards] == ["7H", "2D"] and strip.dimmed == []
    adds = [b.title for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title.startswith("Add"))]
    assert adds == ["Add 7♥'s strength (+7)", "Add 2♦'s strength (+2)"]
    assert ui.render(app).size[0] > 0
    _tap_button(app, "Add 7♥'s strength (+7)")
    # mission 5 feeds the zone from the top of the banished pile: "What order?", the revealed
    # cards numbered as they are tapped, the last one on top
    from app.screens import OrderOverlay
    assert g.decision["kind"] == "reaver_order" and g.decision["options"] == ["7H", "2D"]
    assert isinstance(gs.overlay, OrderOverlay) and sorted(gs.overlay.card_views) == ["2D", "7H"]
    texts = [v.text for v in ui.find(gs.overlay, lambda v: isinstance(v, ui.Label))]
    assert "What order?" in texts
    assert any("banished in any order" in t and "into the mission zone at the end of the turn" in t for t in texts)
    _assert_nothing_cut(gs.overlay)
    assert not ui.button(app, "Confirm the order (0 of 2)").enabled and ui.render(app).size[0] > 0
    ui.tap(app, *ui.root_point(app, gs.overlay.card_views["7H"]))
    ui.tap(app, *ui.root_point(app, gs.overlay.card_views["2D"]))
    assert gs.overlay.picked == ["7H", "2D"] and gs.overlay.card_views["2D"].badge == "2"
    _tap_button(app, "Confirm the order (2 of 2)")
    assert g.decision is None and g.enemy.hp == 100 - 68 and g.banished == ["MYLA7", "7H", "2D"]
    assert gs.overlay is None and gs.right_btn.title.startswith("Discard")
    assert "10 + 7 = 17, doubled to 34. 7♥ + 2♦ banished." in _logged(g)
    assert "68 damage to Sporeling (32/40)." in _logged(g)
    assert "Solo banished them in the order 7♥, 2♦: 2♦ ends on top of the banished pile." in _logged(g)
    assert gs.right_btn.title == "Discard 0/10"


def test_scarlet_whistle_solo_pick_overlay_and_the_beast_choice(app):
    from app.screens import CampaignScreen, OrderOverlay, PickOverlay
    from helpers import set_discard
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.relics.append("whistle")
    camp.flags["beasts"] = True
    app.save_campaign()
    app.show(CampaignScreen(app))
    # the deck list shows Gøran's four beasts: a tap takes one on the next attempt
    _tap_button(app, "Deck list")
    ps = app.current
    assert sorted(ps.beast_views) == ["B_C", "B_D", "B_H", "B_S"] and not any(v.selected for v in ps.beast_views.values())
    ui.tap(app, *ui.root_point(app, ps.beast_views["B_C"]))
    assert camp.beast == "B_C" and [b for b, v in ps.beast_views.items() if v.selected] == ["B_C"]
    _tap_button(app, "‹ Back")
    _tap_button(app, "Next mission: start")
    gs = _game_screen(app)
    g = app.game
    assert "B_C" in g.cards
    set_enemy(g, "J", "H")
    set_hand(g, ["B_C", "7H", "3D", "9S", "8S"])
    set_discard(g, ["6D"])
    gs.refresh(after_action=False)
    assert ui.render(app).size[0] > 0                 # the B rank and the beast badge draw
    gs.hand.set_selection(["B_C"])
    # the Scarlet Whistle may add the top discard first; forecast without it: no damage
    assert _pv(gs)["decision_kind"] == "whistle_take" and _pv(gs)["damage"] == 0
    _tap_button(app, "Play")
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "whistle_take"
    assert isinstance(gs.overlay, PickOverlay)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Scarlet Whistle" in texts
    assert ui.button(app, "Add 6♦ from the discard pile") and ui.button(app, "Skip")
    assert ui.render(app).size[0] > 0
    _tap_button(app, "Add 6♦ from the discard pile")
    # beast + 6♦ is a 12, doubled by the beast's warrior class: the Justicar falls; the solo
    # Scarlet Whistle reads the discard pile, so the clean-up asks "What order?", the cards
    # shown in the order they entered play; keeping it puts the Whistle's 6♦ (added last) on top
    assert isinstance(gs.overlay, OrderOverlay) and g.decision["kind"] == "played_discard_order"
    assert g.decision["options"] == ["B_C", "6D"] and "What order?" in [v.text for v in _labels(gs.overlay)]
    assert "Solo adds 6♦ from the discard pile to the attack (Scarlet Whistle): strength 12." in _logged(g)
    _tap_button(app, "Keep the order played")
    assert g.decision is None and g.enemies_defeated == 1 and gs.overlay is None and g.discard[:2] == ["6D", "B_C"]
    assert "The played cards go on top of the discard pile in this order: B♣, 6♦ (6♦ ends on top)." in _logged(g)


def test_scarlet_whistle_two_players_hand_decision_overlay(app):
    from app.screens import DecisionOverlay
    from helpers import set_mission_enemy
    gs, g = _mission_attempt(app, 5, names=("Ana", "Ben"), relics=("whistle",), beast="B_H")
    set_mission_enemy(g, "GRJH", hp=100)
    set_hand(g, ["AS", "9S", "8S"], player=0)
    set_hand(g, ["7C", "3D", "2D"], player=1)
    gs.reveal_hand()
    gs.hand.set_selection(["AS"])
    assert _pv(gs)["decision_kind"] == "whistle_add"   # another player may add a card first
    _tap_button(app, "Play")
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "whistle_add" and g.deciding == 1
    assert isinstance(gs.overlay, DecisionOverlay) and gs.hand.cards == []
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert any("Ben: add to Ana's A♠ attack?" in t for t in texts) and any(t.startswith("Scarlet Whistle") for t in texts)
    assert ui.render(app).size[0] > 0
    _tap_button(app, "Show my hand")
    assert gs.overlay is None and [c.id for c in gs.hand.cards] == ["7C", "3D", "2D"]
    assert gs.left_btn.title == "Pass" and gs.right_btn.title == "Add" and not gs.right_btn.enabled
    _tap_card(app, gs, "7C")
    assert gs.hand.selected == ["7C"] and gs.right_btn.enabled and _pv(gs)["attack"] == 8 and _rows(gs)["Attack"] == "8"
    _tap_card(app, gs, "3D")                       # one card only
    assert gs.hand.selected == ["3D"]
    _tap_card(app, gs, "7C")
    _tap_button(app, "Add")
    assert g.decision is None and g.plays[0].card_ids == ["AS", "7C"] and g.plays[0].value == 8
    assert g.enemy.hp == 100 - 16 and g.phase == PHASE_SUFFER and g.active == 0


def test_mission6_team_damage_seat_picker_flow(app):
    from app import store
    from app.screens import HandoverOverlay, PickOverlay, TeamDamageOverlay
    from helpers import set_mission_enemy
    gs, g = _mission_attempt(app, 6, names=("Ana", "Ben"))
    # Myla in the zone's row: her team damage is 7
    assert g.mission_zone == ["MYLA7"] and not gs.zone.hidden and _zone_ids(gs) == ["MYLA7"]
    assert g.rules.zone_strength(g) == 7
    set_mission_enemy(g, "GDQH", hp=9)
    set_hand(g, ["9S", "8D", "AD"], player=0)
    set_hand(g, ["3H", "4D", "7S", "2C"], player=1)
    gs.reveal_hand()
    gs.hand.set_selection(["9S"])
    _tap_button(app, "Play")
    # the kill: move a card in play to the zone
    assert g.decision["kind"] == "zone_move" and isinstance(gs.overlay, PickOverlay)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Enemy defeated" in texts
    _tap_button(app, "Move 9♠ to the mission zone")
    # exact: rescue one zone card except Myla
    assert g.decision["kind"] == "zone_rescue" and isinstance(gs.overlay, PickOverlay)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert any("except Myla" in t for t in texts)
    assert not ui.find(app, lambda v: isinstance(v, ui.Button) and "Myla" in v.title)
    _tap_button(app, "Rescue 9♠ to the discard pile")
    # team damage: a seat picker, then the chosen player's hand
    assert g.decision["kind"] == "team_discard" and isinstance(gs.overlay, TeamDamageOverlay)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Team damage: 7 to go" in texts
    # names and card counts only: the hands' values stay secret (rulebook p.24)
    assert ui.button(app, "Ana (2 cards)") and ui.button(app, "Ben (4 cards)")
    assert not ui.find(app, lambda v: isinstance(v, ui.Button) and "worth" in v.title)
    assert ui.render(app).size[0] > 0
    assert store.load_attempt(app.campaign.slot).decision["kind"] == "team_discard"
    _tap_button(app, "Ben (4 cards)")
    # Ana holds the phone: it goes to Ben before his hand shows
    assert isinstance(gs.overlay, HandoverOverlay) and gs.hand.cards == []
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Pass the phone to" in texts and "Ben" in texts
    _tap_button(app, "Show my hand")
    assert gs.overlay is None and [c.id for c in gs.hand.cards] == ["3H", "4D", "7S", "2C"]
    assert gs.left_btn.title == "Players" and gs.right_btn.title == "Discard 0/7" and not gs.right_btn.enabled
    # Ben discards for the team damage: his hand, the 7 owed on the attack side
    assert g.decision["kind"] == "team_discard" and gs.team_seat == 1 and gs.shown_player == 1
    assert gs.enemy.paying == (0, 7)
    _tap_card(app, gs, "3H")
    assert gs.right_btn.enabled and gs.right_btn.title == "Discard 3/7"
    _tap_card(app, gs, "4D")
    assert gs.hand.selected == ["4D"]                 # one card at a time
    _tap_button(app, "Players")                        # back to the picker without discarding
    assert isinstance(gs.overlay, TeamDamageOverlay) and g.decision["paid"] == 0
    # at the picker the phone may be with anyone: no hand counts as the holder's, so the
    # piles viewer counts Ben's cards as unseen, and picking Ben again goes through a handover
    assert gs.shown_player is None and gs.hand.cards == []
    from app.screens import PilesOverlay
    assert set(["3H", "4D", "7S", "2C"]) <= set(PilesOverlay(gs).unseen(g))
    _tap_button(app, "Ben (4 cards)")
    assert isinstance(gs.overlay, HandoverOverlay) and gs.hand.cards == []
    _tap_button(app, "Show my hand")
    assert gs.overlay is None
    _tap_card(app, gs, "3H")
    _tap_button(app, "Discard")
    assert g.decision["paid"] == 3 and g.discard[0] == "3H"
    assert isinstance(gs.overlay, TeamDamageOverlay)   # any player may discard the next card
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Team damage: 4 to go" in texts
    _tap_button(app, "Ana (2 cards)")
    assert isinstance(gs.overlay, HandoverOverlay)
    _tap_button(app, "Show my hand")
    _tap_card(app, gs, "8D")
    assert gs.right_btn.title == "Discard 8/4" and gs.enemy.paying == (8, 4)   # enough
    _tap_button(app, "Discard")
    assert g.decision is None and g.enemies_defeated == 1 and g.phase == PHASE_PLAY and g.active == 0
    # the team damage is satisfied: the last discard brought the total past the 7 owed
    assert "Ana discards 8♦ for the team damage (11 of 7)." in _logged(g) and gs.overlay is None
    assert [c.id for c in gs.hand.cards] == ["AD"] and gs.right_btn.title == "Play"
    assert _zone_ids(gs) == g.mission_zone and "MYLA7" in g.mission_zone and g.rules.zone_strength(g) == 7


def test_mission6_solo_team_damage_shows_the_hand_at_once(app):
    from helpers import set_mission_enemy
    gs, g = _mission_attempt(app, 6)
    set_mission_enemy(g, "GDQH", hp=5)
    set_hand(g, ["5S", "8S", "AD", "3C"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["5S"])
    _tap_button(app, "Play")
    _tap_button(app, "Move 5♠ to the mission zone")
    _tap_button(app, "Rescue 5♠ to the discard pile")
    assert g.decision["kind"] == "team_discard" and gs.overlay is None
    assert gs.left_btn.title == "Suggest" and gs.right_btn.title == "Discard 0/7" and gs.enemy.paying == (0, 7)
    assert [c.id for c in gs.hand.cards] == g.players[0].hand    # the hand at once, no seat picker
    _tap_button(app, "Suggest")
    assert gs.hand.selected == ["8S"]                  # the smallest card that covers 7
    _tap_button(app, "Discard")
    assert g.decision is None and g.enemies_defeated == 1 and sorted(g.players[0].hand) == ["3C", "AD"]


def test_mission4_cleanup_follows_the_selection_order_and_enemy_bonus(app):
    from app.screens import OrderOverlay
    from helpers import set_discard, set_mission_enemy
    gs, g = _mission_attempt(app, 4)
    set_mission_enemy(g, "LABJD", hp=10)
    set_hand(g, ["AS", "9C", "3D", "2H"])
    set_discard(g, ["7D"])
    gs.refresh(after_action=False)
    assert g.enemy_attack == 17 and ui.render(app).size[0] > 0   # the panel shows 10 + 7
    gs.hand.set_selection(["9C", "AS"])                # 9♣ selected first, the ace last
    assert [gs.hand.views[c].order for c in ("9C", "AS")] == [1, 2]
    _tap_button(app, "Play")
    # the top of the discard pile feeds the next enemy: "What order?", the cards shown in the
    # order they were selected; keeping it puts the ace on top, so the next experiment gains 1
    assert isinstance(gs.overlay, OrderOverlay) and g.decision["kind"] == "played_discard_order"
    assert gs.overlay.card_ids(g, g.decision) == ["9C", "AS"] and g.enemies_defeated == 0
    texts = [v.text for v in _labels(gs.overlay)]
    assert "What order?" in texts and any("Enemy defeated" in t and "strength adds to the enemy" in t for t in texts)
    _assert_nothing_cut(gs.overlay)
    assert not ui.button(app, "Confirm the order (0 of 2)").enabled and ui.render(app).size[0] > 0
    _tap_button(app, "Keep the order played")
    assert g.decision is None and gs.overlay is None
    assert g.discard == ["AS", "9C", "LABJD", "7D"] and g.enemies_defeated == 1
    assert "The played cards go on top of the discard pile in this order: 9♣, A♠ (A♠ ends on top)." in _logged(g)
    assert g.enemy_attack == 11


def test_mission4_cleanup_what_order_takes_the_order_tapped(app):
    from helpers import set_discard, set_mission_enemy
    gs, g = _mission_attempt(app, 4)
    set_mission_enemy(g, "LABJD", hp=10)
    set_hand(g, ["AS", "9C", "3D", "2H"])
    set_discard(g, ["7D"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["9C", "AS"])
    _tap_button(app, "Play")
    ui.tap(app, *ui.root_point(app, gs.overlay.card_views["AS"]))
    ui.tap(app, *ui.root_point(app, gs.overlay.card_views["9C"]))
    assert [gs.overlay.card_views[c].badge for c in ("AS", "9C")] == ["1", "2"]
    _tap_button(app, "Confirm the order (2 of 2)")
    # the first tapped went first, the last (9♣) ends on top and feeds the next enemy
    assert g.decision is None and gs.overlay is None and g.discard == ["9C", "AS", "LABJD", "7D"]
    assert "The played cards go on top of the discard pile in this order: A♠, 9♣ (9♣ ends on top)." in _logged(g)
    assert g.enemy_attack == 19


def _mage_leftovers_to_order(app):
    """Mission 4: a 3 mage reveals 4♣, 10♥ and 2♦; 4♣ joins the attack, the other two go to
    the discard pile, whose top adds to the enemy: the app asks for their order."""
    from helpers import set_discard, set_mission_enemy
    gs, g = _mission_attempt(app, 4)
    set_mission_enemy(g, "LABJD")
    set_discard(g, ["2S"])
    set_hand(g, ["3M", "9S", "8S", "AS"])
    set_tavern_top(g, ["4C", "10H", "2D"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3M"])
    _tap_button(app, "Play")
    assert g.decision["kind"] == "mage_peek"
    _tap_button(app, "Add 4♣ to the attack")
    assert g.decision["kind"] == "discard_order"
    return gs, g


def test_mage_leftovers_what_order_overlay_numbers_the_cards_as_tapped(app):
    from app.screens import OrderOverlay
    gs, g = _mage_leftovers_to_order(app)
    assert isinstance(gs.overlay, OrderOverlay) and sorted(gs.overlay.card_views) == ["10H", "2D"]
    texts = [v.text for v in _labels(gs.overlay)]
    assert "What order?" in texts
    assert any("did not choose" in t and "the last ends on top" in t and "strength adds to the enemy" in t for t in texts)
    _assert_nothing_cut(gs.overlay)
    assert not ui.button(app, "Confirm the order (0 of 2)").enabled and ui.render(app).size[0] > 0
    # a tap numbers a card, a second tap takes the number back
    ui.tap(app, *ui.root_point(app, gs.overlay.card_views["2D"]))
    assert gs.overlay.picked == ["2D"] and gs.overlay.card_views["2D"].badge == "1"
    assert not ui.button(app, "Confirm the order (1 of 2)").enabled
    ui.tap(app, *ui.root_point(app, gs.overlay.card_views["2D"]))
    assert gs.overlay.picked == [] and gs.overlay.card_views["2D"].badge == ""
    ui.tap(app, *ui.root_point(app, gs.overlay.card_views["10H"]))
    ui.tap(app, *ui.root_point(app, gs.overlay.card_views["2D"]))
    assert [gs.overlay.card_views[c].badge for c in ("10H", "2D")] == ["1", "2"]
    assert ui.render(app).size[0] > 0
    _tap_button(app, "Confirm the order (2 of 2)")
    # the first tapped went first, the last ends on top: 10 + 2 against the next attack
    assert g.decision is None and gs.overlay is None and g.discard[:3] == ["2D", "10H", "2S"]
    assert g.phase == PHASE_SUFFER and g.pending_damage == 12
    assert "10♥ + 2♦ go to the discard pile in that order, 2♦ on top." in _logged(g)


def test_a_game_saved_on_the_old_top_card_question_still_shows_it(app):
    from app import store
    from app.screens import TopChoiceOverlay
    from regicide.engine import Game
    gs, g = _mage_leftovers_to_order(app)
    data = g.to_dict()
    data["decision"]["kind"] = "discard_top"           # what the app saved before the order questions
    store.save_attempt(Game.from_dict(data), app.campaign.slot)
    assert app.resume_attempt()
    gs, g = _game_screen(app), app.game
    assert g.decision["kind"] == "discard_top" and isinstance(gs.overlay, TopChoiceOverlay)
    texts = [v.text for v in _labels(gs.overlay)]
    assert "Which card ends on top?" in texts and any("strength adds to the enemy" in t for t in texts)
    assert ui.render(app).size[0] > 0
    _tap_button(app, "Put 2♦ on top")
    assert g.decision is None and gs.overlay is None and g.discard[:3] == ["2D", "10H", "2S"]
    assert g.phase == PHASE_SUFFER and "10♥ + 2♦ to the discard pile, 2♦ on top." in _logged(g)



# ---------------------------------------------------------------------------- missions 7 to 9
def _empty_pilgrim_zone(g):
    """Mission 7: no pilgrim face up, so no card can match one (the rigged plays stay simple)."""
    g.extra["pilgrim_deck"].extend(g.mission_zone)
    g.mission_zone = []


def test_druid_overlay_assigns_the_dealt_cards_to_four_slots(app):
    from app import store
    from app.screens import DruidOverlay
    from app.widgets import CardView
    from helpers import set_discard, set_mission_enemy
    gs, g = _mission_attempt(app, 7)
    # one pilgrim face up in the zone's row, the rest in the pilgrim deck
    assert _zone_ids(gs) == g.mission_zone and [c.has("pilgrim") for c in gs.zone.cards] == [True]
    assert g.extra["pilgrim_deck"]
    set_mission_enemy(g, "WLJH", hp=100)
    _empty_pilgrim_zone(g)
    set_hand(g, ["5U", "9S", "8S"])
    set_discard(g, ["2H", "3H", "4H", "6C", "7C", "AD"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["5U"])
    # the Druid's deal and sort come first (forecast without them): 5 damage; the forecast dealt nothing
    assert _pv(gs)["decision_kind"] == "druid_assign" and _pv(gs)["damage"] == 5 and len(g.discard) == 6
    _tap_button(app, "Play")
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "druid_assign" and isinstance(gs.overlay, DruidOverlay)
    dealt = g.decision["dealt"][0]
    assert sorted(dealt) == ["2H", "3H", "4H", "6C", "7C", "AD"] and g.discard == []
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Druid: sort 6 cards" in texts and any(t.startswith("Solo was dealt these") for t in texts)
    cards = ui.find(gs.overlay, lambda v: isinstance(v, CardView))
    assert [v.card.id for v in cards] == dealt
    confirm = ui.find(gs.overlay, lambda v: isinstance(v, ui.Button) and v.title == "Confirm")[0]
    assert not confirm.enabled and ui.render(app).size[0] > 0
    assert store.load_attempt(app.campaign.slot).decision["kind"] == "druid_assign"

    def slot(prefix):
        return ui.find(gs.overlay, lambda v: isinstance(v, ui.Button) and v.title.startswith(prefix))[0]

    def card(cid):
        return ui.find(gs.overlay, lambda v: isinstance(v, CardView) and v.card.id == cid)[0]

    # tap a card, then a slot; a card may be moved to another slot; a slot tapped with nothing selected empties
    ui.tap(app, *ui.root_point(app, card("7C")))
    assert gs.overlay.picked == ["7C"]
    ui.tap(app, *ui.root_point(app, slot("Hand:")))
    assert gs.overlay.assign == {"hand": "7C"} and slot("Hand:").title == "Hand: 7♣" and card("7C").badge == "hand"
    ui.tap(app, *ui.root_point(app, card("7C")))
    ui.tap(app, *ui.root_point(app, slot("Banish:")))
    assert gs.overlay.assign == {"banish": "7C"} and slot("Hand:").title == "Hand: —"
    ui.tap(app, *ui.root_point(app, slot("Banish:")))
    assert gs.overlay.assign == {}
    for cid, prefix in (("AD", "Banish:"), ("7C", "Hand:"), ("6C", "Top:"), ("4H", "Bottom:")):
        ui.tap(app, *ui.root_point(app, card(cid)))
        ui.tap(app, *ui.root_point(app, slot(prefix)))
    confirm = ui.find(gs.overlay, lambda v: isinstance(v, ui.Button) and v.title == "Confirm")[0]
    assert confirm.enabled and ui.render(app).size[0] > 0
    ui.tap(app, *ui.root_point(app, confirm))
    assert g.decision is None and gs.overlay is None
    assert g.banished[-1] == "AD" and "7C" in g.players[0].hand and g.tavern[0] == "6C" and g.tavern[-1] == "4H"
    assert sorted(g.discard) == ["2H", "3H"] and g.enemy.hp == 95 and g.phase == PHASE_SUFFER
    assert "Druid: Solo sorts: A♦ banished, 7♣ to hand, 6♣ on top of the reserve, 4♥ under the reserve." in _logged(g)
    assert "Druid: the 2 other cards go back to the discard pile, shuffled." in _logged(g)
    assert [c.id for c in gs.hand.cards] == g.players[0].hand


def test_chanter_declare_grid_then_the_other_players_discard_down(app):
    from app.screens import ChanterDeclareOverlay, DecisionOverlay
    from helpers import set_mission_enemy
    gs, g = _mission_attempt(app, 8, names=("Ana", "Ben"))
    # the zone's pilgrim adds nothing to the enemy's strength: no mission line on the attack card
    assert g.mission_zone == ["PILA"] and _zone_ids(gs) == ["PILA"] and g.rules.attack_bonus(g) == 0
    set_mission_enemy(g, "HEJ6", hp=100)
    set_hand(g, ["3T", "9S"], player=0)
    set_hand(g, ["2C", "3C", "4C", "5C", "6C", "7C"], player=1)
    set_tavern_top(g, ["AH", "2H", "3H", "4H", "5H", "6H", "7H", "8H"])
    gs.reveal_hand()
    assert g.rules.attack_bonus(g) == 0 and "Mission" not in _attack_card(app, gs) and gs.overlay is None
    gs.hand.set_selection(["3T"])
    assert _pv(gs)["decision_kind"] == "chanter_declare"   # the Chanter's declaration comes first
    _tap_button(app, "Play")
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "chanter_declare" and isinstance(gs.overlay, ChanterDeclareOverlay)
    numbers = [b.title for b in ui.find(gs.overlay, lambda v: isinstance(v, ui.Button) and v.title.isdigit())]
    assert numbers == [str(n) for n in range(0, len(g.tavern) + 1)]
    assert ui.render(app).size[0] > 0
    _tap_button(app, "3")
    # Ana drew to 4 cards, Ben to 9: Ben must discard two; the phone goes to him first
    assert g.decision["kind"] == "chanter_discard" and g.deciding == 1
    assert isinstance(gs.overlay, DecisionOverlay) and gs.hand.cards == []
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert any("Ben: discard down to 7 cards" in t for t in texts) and any("must discard 2" in t for t in texts)
    assert "Chanter: Ana declares 3; Ana draws 3, Ben draws 3." in _logged(g)
    _tap_button(app, "Show my hand")
    assert gs.overlay is None and len(gs.hand.cards) == 9 and gs.right_btn.title == "Discard 0/2" and not gs.right_btn.enabled
    assert gs.left_btn.title == "Suggest" and gs.mid_btn.hidden
    _tap_card(app, gs, "7C")
    assert not gs.right_btn.enabled and gs.right_btn.title == "Discard 1/2"
    _tap_card(app, gs, "6C")
    assert gs.right_btn.enabled
    _tap_button(app, "Suggest")
    assert sorted(gs.hand.selected) == ["2C", "3C"]
    _tap_button(app, "Discard 2/2")
    assert g.decision is None and len(g.players[1].hand) == 7 and set(g.discard[:2]) == {"2C", "3C"}
    assert g.phase == PHASE_SUFFER and g.active == 0 and "Chanter: Ben discards 2♣ + 3♣." in _logged(g)
    # back to Ana for her damage
    from app.screens import HandoverOverlay
    assert isinstance(gs.overlay, HandoverOverlay)
    _tap_button(app, "Show my hand")
    assert gs.right_btn.title.startswith("Discard") and len(gs.hand.cards) == 4


def test_mission7_zone_title_and_pilgrim_banish_pick_overlay(app):
    from app.screens import PickOverlay
    from helpers import set_mission_enemy
    gs, g = _mission_attempt(app, 7)
    set_mission_enemy(g, "WLJH", hp=100)
    _empty_pilgrim_zone(g)
    g.extra["pilgrim_deck"].remove("PIL3_1")
    g.mission_zone = ["PIL3_1"]
    set_hand(g, ["3H", "9S", "8S", "PIL4_1"])
    g.extra["pilgrim_deck"].remove("PIL4_1") if "PIL4_1" in g.extra["pilgrim_deck"] else None
    gs.refresh(after_action=False)
    # one pilgrim in the zone's row, strength 3
    assert _zone_ids(gs) == ["PIL3_1"] and g.rules.zone_strength(g) == 3
    assert gs.hand.badges.get("PIL4_1") == "stuck" and gs.hand.views["PIL4_1"].shaded
    _tap_card(app, gs, "PIL4_1")
    assert gs.hand.selected == []                       # a locked card cannot be selected
    gs.hand.set_selection(["3H"])
    assert _pv(gs)["decision_kind"] == "pilgrim_banish"   # a pilgrim of the same strength may be banished first
    _tap_button(app, "Play")
    assert g.decision["kind"] == "pilgrim_banish" and isinstance(gs.overlay, PickOverlay)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "A pilgrim matches" in texts
    assert ui.button(app, "Banish Pilgrim 3") and ui.button(app, "Keep the pilgrims")
    assert ui.render(app).size[0] > 0
    _tap_button(app, "Banish Pilgrim 3")
    assert g.mission_zone == [] and "PIL3_1" in g.banished and g.decision is None and gs.overlay is None
    assert "Solo banishes Pilgrim 3 from the mission zone (matched by 3♥)." in _logged(g)
    assert _zone_ids(gs) == [] and not gs.zone.hidden and g.rules.zone_strength(g) == 0


def test_mission9_pile_strip_rescue_flow_and_exact_kill_overlay(app):
    from app import store
    from app.screens import PileRescueOverlay, PileToReserveOverlay
    from helpers import set_mission_enemy
    gs, g = _mission_attempt(app, 9)
    piles = g.extra["captured"]
    # the zone's row shows the three captured piles' top cards (10 cards each)
    assert not gs.zone.hidden and [len(p) for p in piles] == [10, 10, 10]
    assert [c.id for c in gs.zone.cards] == [p[0] for p in piles]
    set_mission_enemy(g, "TTQH")
    set_hand(g, ["9S", "4C", "3C", "5D", "6D"])          # pulls those cards out of the piles too
    tops = [p[0] for p in piles]
    sizes = [len(p) for p in piles]
    gs.refresh(after_action=False)
    assert _zone_ids(gs) == tops                       # the piles' new tops
    gs.hand.set_selection(["9S"])
    _tap_button(app, "Play")
    assert g.phase == PHASE_SUFFER and g.pending_damage == 6
    gs.hand.set_selection(["4C", "3C"])
    _tap_button(app, "Discard")
    # end of turn: the pile picker first
    assert g.decision["kind"] == "pile_rescue" and isinstance(gs.overlay, PileRescueOverlay)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "End of turn" in texts
    labels = [b.title for b in ui.find(gs.overlay, lambda v: isinstance(v, ui.Button) and v.title.startswith("Rescue"))]
    assert labels == ["Rescue %s (pile %d, %d cards)" % (g.card(tops[k]).label(), k + 1, sizes[k]) for k in range(3)]
    assert ui.button(app, "Rotate the piles") and ui.render(app).size[0] > 0
    assert store.load_attempt(app.campaign.slot).decision["kind"] == "pile_rescue"
    ui.tap(app, *ui.root_point(app, ui.button(app, labels[1])))
    # then the hand: one card to banish
    assert gs.overlay is None and gs.pile_choice == 1 and [c.id for c in gs.hand.cards] == ["5D", "6D"]
    assert gs.right_btn.title == "Banish" and not gs.right_btn.enabled and gs.left_btn.title == "Back"
    # rescuing pile 2's top: the cards not greyed are those the rules let go for pile 2
    assert g.decision["kind"] == "pile_rescue" and piles[1][0] == tops[1]
    allowed = set(a["card"] for a in g.legal_actions() if a["type"] == "pile_rescue" and int(a["pile"]) == 1)
    assert allowed and set(cid for cid, v in gs.hand.views.items() if not v.shaded) == allowed
    _tap_button(app, "Back")
    assert isinstance(gs.overlay, PileRescueOverlay) and gs.pile_choice is None
    ui.tap(app, *ui.root_point(app, ui.button(app, labels[1])))
    _tap_card(app, gs, "5D")
    assert gs.right_btn.enabled
    _tap_button(app, "Banish")
    assert g.decision is None and g.banished[-1] == "5D" and g.discard[0] == tops[1] and len(piles[1]) == sizes[1] - 1
    assert gs.pile_choice is None and g.turn == 2
    assert [len(p) for p in piles] == [sizes[0], sizes[1] - 1, sizes[2]] and _zone_ids(gs) == [p[0] for p in piles if p]
    assert ("Solo banishes 5♦ and rescues %s from captured pile 2 to the discard pile."
            % g.card(tops[1]).label()) in _logged(g)
    # an exact kill: the pile-to-reserve overlay
    set_mission_enemy(g, "TTQD", hp=9)
    set_hand(g, ["9S", "2C"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["9S"])
    assert _pv(gs)["defeats"] and _pv(gs)["exact"] and _rows(gs)["Enemy health"] == "exact"
    _tap_button(app, "Play")
    assert g.decision["kind"] == "pile_to_reserve" and isinstance(gs.overlay, PileToReserveOverlay)
    tops = [p[0] for p in piles]
    btn = ui.button(app, "%s (pile 1) on top of the reserve" % g.card(tops[0]).label())
    assert ui.button(app, "Leave the piles") and ui.render(app).size[0] > 0
    ui.tap(app, *ui.root_point(app, btn))
    assert g.decision is None and g.tavern[0] == tops[0] and g.enemies_defeated == 1 and gs.overlay is None
    assert _zone_ids(gs) == [p[0] for p in piles if p]   # pile 1's next card on top


def _finished_campaign(app, names=("Solo",)):
    """A campaign that has completed mission 12, shown on its game menu."""
    from app.screens import CampaignScreen
    from regicide.campaign import missions as M
    app.new_campaign(len(names), list(names))
    camp = app.campaign
    camp.mission = 12
    camp.completed = list(range(1, 13))
    camp.finished = True
    camp.relics.append("mother_restored")
    camp.flags["beasts"] = True
    camp.set_beast("B_H")
    for d in M.MAGE_DECK:
        P.add_card(camp.party, dict(d))
    P.add_card(camp.party, dict(M.ASH))
    P.add_card(camp.party, dict(M.ESME_REBORN))
    for cid in ("2S", "3H", "4D", "5C", "7S", "8H", "9D", "ESME6E"):
        P.add_flag(camp.party, cid, "restored")
    app.save_campaign()
    app.show(CampaignScreen(app))
    return camp


def test_evergreen_screen_draw_redraw_options_mercenaries_start_and_continue(app):
    from app import store
    from app.screens import CampaignResultOverlay, CampaignScreen, EvergreenScreen, GameScreen, MercenaryScreen
    camp = _finished_campaign(app)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Campaign complete!" in texts and ui.button(app, "Evergreen mission").enabled
    _tap_button(app, "Evergreen mission")
    assert isinstance(app.current, EvergreenScreen) and ui.button(app, "New Evergreen mission")
    with pytest.raises(KeyError):
        ui.button(app, "Start")                        # nothing drawn yet
    assert ui.render(app).size[0] > 0
    # the two options of the rules card are switches, remembered in the save
    switches = ui.find(app, lambda v: isinstance(v, ui.Switch))
    assert len(switches) == 2 and not switches[0].value
    switches[0].value = True
    switches[0].action(switches[0])
    assert camp.evergreen["options"]["extra_red"] is True and store.load_campaign(camp.slot).evergreen["options"]["extra_red"]
    _tap_button(app, "New Evergreen mission")
    setup = camp.evergreen["setup"]
    assert setup and len(setup["banes"]) == 4 and len(setup["boons"]) == 2
    tiers = [b["tier"] for b in camp.evergreen_setup()["banes"]]
    assert tiers.count("red") == 2 and tiers.count("grey") == 1
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    loc = camp.evergreen_setup()["location"]
    assert "Location %s: the %s" % (loc["id"], loc["name"]) in texts
    assert all(any(b["name"] in t for t in texts) for b in camp.evergreen_setup()["banes"] + camp.evergreen_setup()["boons"])
    assert ui.button(app, "Start") and ui.button(app, "Redraw") and ui.render(app).size[0] > 0
    calls = camp.rng_calls
    _tap_button(app, "Redraw")
    assert camp.rng_calls > calls and store.load_campaign(camp.slot).evergreen["setup"] == camp.evergreen["setup"]
    # boon 24: the five-coin mercenary camp scoped to this setup
    camp.evergreen["setup"] = {"location": "A", "banes": [2, 9, 11], "boons": [24, 30]}
    camp.evergreen["coins"] = 5
    app.save_campaign()
    app.show(EvergreenScreen(app))
    _tap_button(app, "Mercenaries (5 coins left)")
    assert isinstance(app.current, MercenaryScreen) and app.current.evergreen
    assert len(app.current.card_views) == 14 and all(v.shaded for v in app.current.card_views.values())
    _merc_card(app, "merc_12H")
    _tap_button(app, "Hire for 1 coin")
    assert camp.evergreen["coins"] == 4 and camp.evergreen["mercenaries"] == ["merc_12H"] and camp.mercenaries == [] and camp.coins == 0
    popup = _merc_card(app, "merc_12H")                 # no swaps in Evergreen mode
    assert not ui.find(popup, lambda v: isinstance(v, ui.Button) and v.title == "Swap")
    _tap_button(app, "Close")
    _tap_button(app, "‹ Back")
    assert isinstance(app.current, EvergreenScreen) and ui.button(app, "Mercenaries (4 coins left)")
    # start: an Evergreen game with the hired mercenary, saved as the campaign's attempt
    _tap_button(app, "Start")
    gs = _game_screen(app)
    g = app.game
    assert g.config.rules_id == "evergreen" and app.in_campaign and store.has_attempt(camp.slot)
    assert any(x.startswith("M") and g.cards[x].has("mercenary") for x in g.cards) and len(g.discard) == 30
    assert not gs.zone.hidden and _zone_ids(gs) == g.mission_zone and g.rules.location_name(g) == "Shrine"
    assert camp.evergreen["attempts"] == 1 and ui.render(app).size[0] > 0
    # the rules card names the drawn setup, E in its corner
    from app.screens import PartyScreen, rules_card
    from app.widgets import CardView
    from app import theme as T
    head, subtitle, body, corner = rules_card(camp, g)
    setup = camp.evergreen_setup()
    assert head == "Evergreen mission: the %s" % setup["location"]["name"] and corner == [("E", T.CARD_INK_MUTED)]
    assert all(("Bane %d, %s" % (b["n"], b["name"])) in body for b in setup["banes"])
    assert all(("Boon %d, %s" % (b["n"], b["name"])) in body for b in setup["boons"])
    # the deck list shows boon 24's mercenary; hiring waits while the attempt runs
    app.show(PartyScreen(app))
    assert any(v.card.id == "M12H" for v in ui.find(app, lambda v: isinstance(v, CardView)))
    b = [v for v in ui.find(app, lambda v: isinstance(v, ui.Button)) if v.title.startswith("Mercenaries")]
    assert [v.title for v in b] == ["Mercenaries (after this attempt)"] and not b[0].enabled
    # continue from both menus
    app.show(CampaignScreen(app))
    assert ui.button(app, "Continue attempt")
    _tap_button(app, "Evergreen mission")
    assert ui.button(app, "Continue attempt")
    with pytest.raises(KeyError):
        ui.button(app, "Redraw")                       # no redraw while an attempt is in progress
    _tap_button(app, "Continue attempt")
    gs = _game_screen(app)
    assert app.game.config.rules_id == "evergreen"
    # a loss: no coins, the setup may be retried or redrawn
    app.game._lose("test loss")
    gs.refresh(after_action=False)
    assert isinstance(gs.overlay, CampaignResultOverlay)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Evergreen mission lost" in texts and camp.evergreen["losses"] == 1 and camp.coins == 0 and camp.finished
    assert not store.has_attempt(camp.slot) and ui.button(app, "Play this setup again")
    _tap_button(app, "Evergreen missions")
    assert isinstance(app.current, EvergreenScreen) and ui.button(app, "Retry this setup (attempt 2)")
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "This setup: 1 attempt, 1 lost" in texts


def _late_mission_attempt(app, number, names=("Solo",)):
    from regicide.campaign import missions as M
    app.new_campaign(len(names), list(names))
    camp = app.campaign
    camp.mission = number
    camp.completed = list(range(1, number))
    camp.flags["beasts"] = True
    camp.set_beast("B_H")
    for d in M.MAGE_DECK:
        P.add_card(camp.party, dict(d))
    P.add_card(camp.party, dict(M.ASH))
    if number == 10:
        P.add_card(camp.party, dict(M.GORAN_RENEWED))
    if number == 12:
        P.add_card(camp.party, dict(M.ESME_REBORN))
    for cid in ("2S", "3H", "4D", "5C", "6C", "7S", "8H", "9D")[: 7 if number == 12 else 8]:
        P.add_flag(camp.party, cid, "corrupted")
        camp.corrupted.append(cid)
    app.save_campaign()
    app.start_attempt()
    gs = _game_screen(app)
    return gs, app.game


def test_mission11_beast_hand_pick_and_mission12_banish_order_overlay(app):
    from app.screens import OrderOverlay
    from helpers import set_mission_enemy
    gs, g = _late_mission_attempt(app, 11)
    # the zone's row holds the revealed beasts; three more lie face down in the beast deck
    assert not gs.zone.hidden and len(g.extra["beast_deck"]) == 3
    assert g.extra["beasts_out"] and _zone_ids(gs) == g.extra["beasts_out"]
    if g.phase == PHASE_DECIDE:
        gs.decide(greedy_policy(g))
    # a cleric beast at the next start of turn: the hand is shown with one card to discard
    for play in g.plays:
        g.discard.extend(play.card_ids)
    g.plays = []
    set_mission_enemy(g, "CV_J1", hp=100)
    g.extra["beast_deck"] = ["B_H"] + [x for x in g.extra["beast_deck"] if x != "B_H"]
    g.extra["beasts_out"] = [x for x in g.extra["beasts_out"] if x != "B_H"]
    set_hand(g, ["AS", "9S", "8S", "2C"])
    g.tavern.extend(g.discard)
    g.discard = []
    g.banished = []
    gs.refresh(after_action=False)
    gs.hand.set_selection(["AS"])
    _tap_button(app, "Play")
    # 9 damage after the ace's shield: 8 then 9 is legal one at a time (9 then 8 is not)
    gs.hand.set_selection(["8S", "9S"])
    _tap_button(app, "Discard")
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "beast_discard" and gs.overlay is None
    assert gs.right_btn.title == "Discard" and not gs.right_btn.enabled and gs.left_btn.title == "No pass" and not gs.left_btn.enabled
    # the cleric beast (B♥) is out, in the zone's row
    assert "B_H" in g.extra["beasts_out"] and [c.id for c in gs.hand.cards] == ["2C"]
    assert "B_H" in _zone_ids(gs) and _zone_ids(gs) == g.extra["beasts_out"] and ui.render(app).size[0] > 0
    _tap_card(app, gs, "2C")
    assert gs.right_btn.enabled
    _tap_button(app, "Discard")
    assert g.decision is None and g.discard[0] == "2C" and g.phase == PHASE_PLAY
    assert "Solo discards 2♣ (Cleric beast)." in _logged(g)
    # mission 12: the banish order is picked by tapping the zone cards in order
    gs, g = _late_mission_attempt(app, 12)
    assert not gs.zone.hidden and _zone_ids(gs) == [] == g.mission_zone
    set_mission_enemy(g, "THQH", hp=9)
    for x in ("6D", "4H"):                             # neither is restored: both can be banished
        for pile in (g.tavern, g.discard, g.banished, g.players[0].hand):
            if x in pile:
                pile.remove(x)
    g.mission_zone = ["6D", "4H"]
    set_hand(g, ["9S", "AS"])
    gs.refresh(after_action=False)
    # the zone's 6♦ + 4♥: the enemy's strength +10 (the attack card's mission line), immune
    # to bards (an icon on the enemy's card)
    assert _zone_ids(gs) == ["6D", "4H"] and g.rules.zone_strength(g) == 10
    card = _attack_card(app, gs)
    assert card[card.index("Mission") + 1] == "+10"
    assert "D" not in g.enemy.suits and "D" in g.rules.immune_suits(g) and "D" in gs.enemy.card_view.center_icons
    gs.hand.set_selection(["9S"])
    assert _pv(gs)["defeats"] and _pv(gs)["exact"] and _rows(gs)["Enemy health"] == "exact"
    _tap_button(app, "Play")
    assert g.decision["kind"] == "banish_order" and isinstance(gs.overlay, OrderOverlay)
    confirm = ui.button(app, "Confirm the order (0 of 2)")
    assert not confirm.enabled and ui.render(app).size[0] > 0
    ui.tap(app, *ui.root_point(app, gs.overlay.card_views["4H"]))
    assert gs.overlay.picked == ["4H"] and gs.overlay.card_views["4H"].badge == "1"
    ui.tap(app, *ui.root_point(app, gs.overlay.card_views["6D"]))
    assert gs.overlay.picked == ["4H", "6D"]
    _tap_button(app, "Confirm the order (2 of 2)")
    assert g.decision is None and g.banished[:3] == ["4H", "6D", "THQH"] and g.enemies_defeated == 1
    assert "Solo banishes the mission zone in the order 4♥, 6♦ (6♦ on top)." in _logged(g) and gs.overlay is None


def test_evergreen_mother_solo_pick_overlay_and_two_player_hand_banish(app):
    from app.screens import DecisionOverlay, PickOverlay
    from helpers import set_discard
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.relics.append("mother")
    P.add_flag(camp.party, "7D", "corrupted")
    app.save_campaign()
    app.start_attempt()
    gs = _game_screen(app)
    g = app.game
    set_enemy(g, "J", "H")
    set_hand(g, ["7D", "9S", "8S"])
    set_discard(g, ["4C", "2C"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["7D"])
    assert _pv(gs)["decision_kind"] == "mother_choice"   # the corrupted 7♦: the Evergreen Mother's banish first
    _tap_button(app, "Play")
    assert g.decision["kind"] == "mother_choice" and isinstance(gs.overlay, PickOverlay)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Evergreen Mother" in texts
    assert ui.button(app, "Banish 4♣, top of the discard pile") and ui.button(app, "Banish the top card of the reserve deck")
    assert ui.render(app).size[0] > 0
    _tap_button(app, "Banish 4♣, top of the discard pile")
    assert g.banished == ["4C"] and g.decision is None and "7♦ is corrupted: 4♣ banished from the discard pile" in _logged(g)
    # two players: the other player's hand, no pass
    app.new_campaign(2, ["Ana", "Ben"])
    camp = app.campaign
    camp.relics.append("mother")
    P.add_flag(camp.party, "7D", "corrupted")
    app.save_campaign()
    app.start_attempt()
    gs = _game_screen(app)
    g = app.game
    set_enemy(g, "J", "H")
    set_hand(g, ["7D", "9S"], player=0)
    set_hand(g, ["5C", "2C"], player=1)
    gs.reveal_hand()
    gs.hand.set_selection(["7D"])
    _tap_button(app, "Play")
    assert g.decision["kind"] == "mother_banish" and g.deciding == 1 and isinstance(gs.overlay, DecisionOverlay)
    texts = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert any("Ben: banish a card from hand" in t for t in texts)
    _tap_button(app, "Show my hand")
    assert [c.id for c in gs.hand.cards] == ["5C", "2C"] and gs.right_btn.title == "Banish" and not gs.right_btn.enabled
    assert gs.left_btn.title == "No pass" and not gs.left_btn.enabled
    _tap_card(app, gs, "2C")
    # Ben's hand banishes for the Evergreen Mother (the Banish button, no caption)
    assert gs.right_btn.enabled and g.decision["kind"] == "mother_banish" and g.deciding == 1 and gs.shown_player == 1
    _tap_button(app, "Banish")
    assert g.banished == ["2C"] and "2C" not in g.players[1].hand and "5C" in g.players[1].hand and g.decision is None
    assert "7♦ is corrupted: Ben banishes 2♣ from hand (Evergreen Mother)." in _logged(g)


# ---------------------------------------------------------------------------- the review's UI findings
def _labels(view):
    return [v for v in ui.find(view, lambda v: isinstance(v, ui.Label) and not v.hidden)]


def _assert_nothing_cut(view):
    """Every label shows its whole text (UILabel truncates the tail of what does not fit)."""
    cut = [lab.text for lab in _labels(view) if ui.label_truncated(lab)]
    assert not cut, cut


def test_finding_2_ui_discards_one_card_at_a_time_in_the_tap_order(app):
    from helpers import set_discard, set_mission_enemy
    gs, g = _mission_attempt(app, 4)
    set_mission_enemy(g, "LABJD", hp=30)              # Phase I bard: 10 + the top discard
    set_discard(g, ["4D"])
    set_hand(g, ["3S", "AS", "9C", "10C", "8S"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3S"])
    _tap_button(app, "Play")                           # shield 3: 10 + 4 - 3 = 11 to suffer
    assert g.phase == PHASE_SUFFER and g.pending_damage == 11
    _tap_button(app, "Suggest")
    assert gs.hand.selected == ["AS", "10C"] and gs.right_btn.enabled   # the legal order: the 10 last
    assert gs.right_btn.title == "Discard 11/11"
    gs.hand.clear_selection()
    for cid in ("10C", "8S", "AS"):                    # 18 covers it: the ace is greyed and stays out
        _tap_card(app, gs, cid)
    assert gs.hand.selected == ["10C", "8S"] and gs.hand.views["AS"].shaded and gs.right_btn.enabled
    gs.hand.set_selection(["10C", "8S", "AS"])         # (a selection made some other way) one card too many
    assert not gs.right_btn.enabled
    gs.hand.clear_selection()
    for cid in ("AS", "10C"):
        _tap_card(app, gs, cid)
    assert gs.right_btn.enabled
    _tap_button(app, "Discard")
    assert g.discard[:2] == ["10C", "AS"] and g.phase == PHASE_PLAY


def test_finding_20_abandoning_an_attempt_counts_as_a_loss_and_keeps_the_quick_play_save(app):
    from app import store
    from app.screens import CampaignResultOverlay, GameMenuOverlay
    import console
    app.start_game(GameConfig(players=1), seed=2)     # a quick-play game, autosaved
    assert store.has_game()
    app.new_campaign(1, ["Solo"])
    app.start_attempt()
    gs = _game_screen(app)
    slot = app.campaign.slot
    assert store.has_attempt(slot)
    _tap_button(app, "Menu")
    assert isinstance(gs.overlay, GameMenuOverlay)
    assert not ui.find(app, lambda v: isinstance(v, ui.Button) and v.title == "Abandon game")
    console.script_answers(2)                          # Cancel: nothing happens
    _tap_button(app, "Abandon attempt (counts as a loss)")
    assert not app.game.is_over and store.has_attempt(slot)
    console.script_answers(1)
    _tap_button(app, "Abandon attempt (counts as a loss)")
    g = app.game
    assert g.is_over and g.result == "loss" and "abandoned" in g.loss_reason
    camp = app.campaign
    assert camp.losses_on(1) == 1 and camp.coins == 1 and camp.m_box_opened
    assert not store.has_attempt(slot) and store.has_game()   # the quick-play save is untouched
    assert isinstance(gs.overlay, CampaignResultOverlay) and ui.button(app, "Try again")
    texts = [v.text for v in _labels(app)]
    assert "Mission 1 lost" in texts
    # quick play keeps its own "Abandon game"
    assert store.load_game() is not None


def test_finding_21_open_hands_setting_reaches_campaign_and_evergreen_attempts(app):
    from app.screens import HandoverOverlay
    app.settings["open_hands"] = True
    app.new_campaign(2, ["Ana", "Ben"])
    app.start_attempt()
    gs = _game_screen(app)
    assert app.game.config.open_hands and not isinstance(gs.overlay, HandoverOverlay)
    app.settings["open_hands"] = False
    app.new_campaign(2, ["Ana", "Ben"])
    app.start_attempt()
    assert not app.game.config.open_hands and isinstance(_game_screen(app).overlay, HandoverOverlay)
    camp = app.campaign
    camp.mission, camp.completed, camp.finished = 12, list(range(1, 13)), True
    camp.draw_evergreen()
    app.settings["open_hands"] = True
    app.start_evergreen_attempt()
    assert app.game.config.open_hands and app.game.config.rules_id == "evergreen"


def _zone_fits(gs):
    """The zone's row (no title: its caption is gone) sits above the hand, the played cards
    below it, and shows the zone's cards whole inside its frame, oldest first (all of them,
    or the newest beside a card back holding the total)."""
    zone = gs.zone
    assert not zone.hidden and zone.y + zone.height <= gs.hand.y + 0.5
    assert gs.strip.y >= gs.hand.y + gs.hand.height - 0.5
    shown = [v.card.id for v in zone.subviews]
    assert shown == [c.id for c in zone.shown()] and shown == _zone_ids(gs)[len(_zone_ids(gs)) - len(shown):]
    assert len(shown) == len(zone.cards) or zone.overflows()
    for v in zone.subviews:
        assert v.x >= 0 and v.x + v.width <= zone.width + 0.5 and v.y >= 0 and v.y + v.height <= zone.height + 0.5


def test_finding_23_long_zone_captions_fit_two_lines_above_the_cards(app):
    from regicide.campaign import missions as M
    from helpers import _pull, set_mission_enemy
    ui.set_screen_size(390, 844)
    # mission 3: the zone makes the enemy immune to four more classes
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.mission, camp.completed = 3, [1, 2]
    app.save_campaign()
    app.start_attempt()
    gs, g = _game_screen(app), app.game
    for x in ("4H", "3S", "2D", "6C"):
        _pull(g, x)
    g.mission_zone = ["4H", "3S", "2D", "6C"]
    gs.refresh(after_action=False)
    # the four zone cards in the row; the enemy (a mage) is immune to their four classes too,
    # every one an icon on its card
    assert _zone_ids(gs) == ["4H", "3S", "2D", "6C"]
    assert [s_ for s_ in g.rules.immune_suits(g) if s_ not in g.enemy.suits] == ["H", "S", "D", "C"]
    assert list(gs.enemy.card_view.center_icons) == list(g.rules.immune_suits(g))
    _zone_fits(gs)
    assert ui.render(app).size[0] > 0
    # mission 11: four beasts out and no reveal next turn
    gs, g = _late_mission_attempt(app, 11)
    g.extra["beasts_out"] = g.extra["beasts_out"] + g.extra["beast_deck"]
    g.extra["beast_deck"] = []
    g.extra["skip_beast"] = True
    gs.refresh(after_action=False)
    # every beast out, in the zone's row (the deck is empty)
    assert g.extra["beast_deck"] == [] and len(g.extra["beasts_out"]) == 4 and _zone_ids(gs) == g.extra["beasts_out"]
    _zone_fits(gs)
    assert ui.render(app).size[0] > 0
    # mission 12: strength, four classes, no card next turn
    gs, g = _late_mission_attempt(app, 12)
    set_mission_enemy(g, "THQH", hp=30)
    zone = ["9C", "8D", "7H", "6S"] if "6S" in g.cards else ["9C", "8D", "7H", "4S"]
    for x in zone:
        _pull(g, x)
    g.mission_zone = list(zone)
    g.extra["skip_zone"] = True
    gs.refresh(after_action=False)
    # the zone's cards add to the enemy's strength (the attack card's mission line) and make it
    # immune to their classes (icons on its card)
    assert _zone_ids(gs) == zone and g.rules.zone_strength(g) > 0
    card = _attack_card(app, gs)
    assert card[card.index("Mission") + 1] == "+%d" % g.rules.attack_bonus(g) and g.rules.attack_bonus(g) > 0
    assert [s_ for s_ in g.rules.immune_suits(g) if s_ not in g.enemy.suits] == ["C", "D", "S"]
    assert list(gs.enemy.card_view.center_icons) == list(g.rules.immune_suits(g))
    _zone_fits(gs)
    assert ui.render(app).size[0] > 0


def _drawn(monkeypatch, view):
    """Render ``view`` and return the strings drawn with their rects and fonts."""
    calls = []
    real = ui.draw_string

    def spy(text, rect=(0, 0, 0, 0), font=None, color="black", alignment=ui.ALIGN_LEFT, line_break_mode=ui.LB_WORD_WRAP):
        calls.append((text, tuple(rect), font))
        return real(text, rect, font, color, alignment, line_break_mode)
    monkeypatch.setattr(ui, "draw_string", spy)
    ui.render(view)
    monkeypatch.setattr(ui, "draw_string", real)
    return calls


def test_finding_24_a_long_immunity_shows_every_class_on_the_enemy_and_in_its_card(app, monkeypatch):
    from helpers import _pull
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.mission, camp.completed = 3, [1, 2]
    app.save_campaign()
    app.start_attempt()
    gs, g = _game_screen(app), app.game
    for x in ("4H", "3S", "2D", "6C"):
        _pull(g, x)
    g.mission_zone = ["4H", "3S", "2D", "6C"]
    gs.refresh(after_action=False)
    assert len(g.rules.immune_suits(g)) == 5
    # the enemy's card in the header shows all five classes under its letter
    assert list(gs.enemy.card_view.center_icons) == list(g.rules.immune_suits(g))
    assert ui.render(app).size[0] > 0
    # no enemy card in words any more: a tap on the enemy does nothing; the castle's count is
    # on its pile
    from app.screens import CardPopup
    ui.tap(app, *ui.root_point(app, gs.enemy))
    assert gs.overlay is None and not [v for v in gs.subviews if isinstance(v, CardPopup)]
    assert not any("Immune to " in t for t in _texts(app))
    assert gs.pile_views["castle"].count == len(g.castle) > 0 and not gs.pile_views["castle"].hidden
    _assert_nothing_cut(app)


def test_finding_25_overlay_instructions_are_never_cut_short(app):
    from app.screens import (DecisionOverlay, DiscardBanishOverlay, DruidOverlay, MagePeekOverlay, OrderOverlay,
                             PickOverlay, PileRescueOverlay)
    from helpers import _pull, set_discard, set_mission_enemy
    # the Druid with two dealt cards: the longest heading
    gs, g = _mission_attempt(app, 7)
    g.extra["pilgrim_deck"].extend(g.mission_zone)
    g.mission_zone = []
    set_mission_enemy(g, "WLJH", hp=100)
    set_hand(g, ["5U", "9S", "8S"])
    set_discard(g, ["2H", "3H"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["5U"])
    _tap_button(app, "Play")
    assert isinstance(gs.overlay, DruidOverlay)
    assert any("(2 of the four with 2 cards)" in lab.text for lab in _labels(gs.overlay))
    _assert_nothing_cut(gs.overlay)
    # crafted decisions for the other long texts
    cases = [
        ({"kind": "discard_banish", "player": 0, "resume": "defeat", "exact": False}, DiscardBanishOverlay),
        ({"kind": "zone_build", "player": 0, "options": [], "resume": "defeat", "exact": False}, PickOverlay),
        ({"kind": "pile_rescue", "player": 0, "resume": "end_turn"}, PileRescueOverlay),
    ]
    for decision, cls in cases:
        g.phase, g.decision = "decide", dict(decision)
        if decision["kind"] == "pile_rescue":
            g.extra["captured"] = [[g.tavern.pop(0)], [g.tavern.pop(0)], []]
        gs.refresh(after_action=False)
        assert isinstance(gs.overlay, cls), decision
        _assert_nothing_cut(gs.overlay)
        assert ui.render(app).size[0] > 0
    # the mage's short-deck look
    g.extra.pop("captured", None)
    revealed = [g.tavern.pop(0), g.tavern.pop(0)]
    g.phase, g.decision = "decide", {"kind": "mage_peek", "player": 0, "strength": 9, "revealed": revealed,
                                     "eligible": revealed, "play_index": 0, "resume": "resolve"}
    g.plays = g.plays or []
    gs.refresh(after_action=False)
    assert isinstance(gs.overlay, MagePeekOverlay)
    assert any("the deck was short" in lab.text for lab in _labels(gs.overlay))
    _assert_nothing_cut(gs.overlay)
    # mission 12's banish order
    gs, g = _late_mission_attempt(app, 12)
    set_mission_enemy(g, "THQH", hp=9)
    for x in ("6D", "4H"):
        _pull(g, x)
    g.mission_zone = ["6D", "4H"]
    set_hand(g, ["9S", "AS"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["9S"])
    _tap_button(app, "Play")
    assert isinstance(gs.overlay, OrderOverlay)
    _assert_nothing_cut(gs.overlay)
    # the Evergreen Mother in a two-player game
    app.new_campaign(2, ["Ana", "Ben"])
    camp = app.campaign
    camp.relics.append("mother")
    P.add_flag(camp.party, "7D", "corrupted")
    app.save_campaign()
    app.start_attempt()
    gs, g = _game_screen(app), app.game
    set_enemy(g, "J", "H")
    set_hand(g, ["7D", "9S"], player=0)
    set_hand(g, ["5C", "2C"], player=1)
    gs.reveal_hand()
    gs.hand.set_selection(["7D"])
    _tap_button(app, "Play")
    assert isinstance(gs.overlay, DecisionOverlay)
    _assert_nothing_cut(gs.overlay)


def _titles_fit(view):
    """Every visible button's title fits its width at the font it is drawn with."""
    for b in ui.find(view, lambda v: isinstance(v, ui.Button) and not v.hidden and v.title):
        w = ui.measure_string(b.title, 0, b.font)[0]
        assert w <= b.width - 4, (b.title, w, b.width, b.font)


def test_finding_26_button_titles_fit_their_buttons(app):
    from app import theme as T
    from app.screens import HAND_PICKS
    bold = lambda size: (T.FONT_BOLD, size)  # noqa: E731
    assert HAND_PICKS["poison"]["skip"] == "Reserve → zone"
    for title in ("Put under reserve", "Put 10♥ under reserve", "Take top of discard (10♥)"):
        assert ui.measure_string(title, 0, bold(16))[0] <= 300, title
    for title in ("Bottom: 10♥", "Top: 10♥", "Banish: 10♥", "Hand: 10♥"):
        assert ui.measure_string(title, 0, bold(13))[0] <= (300 - 8) / 2.0, title
    # Choose Your Poison: the action bar's skip button shrinks its title to fit (115pt wide)
    from app.screens import PickOverlay, RestoredArrowsOverlay
    from helpers import _pull
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.mission, camp.completed, camp.finished = 12, list(range(1, 13)), True
    camp.evergreen["setup"] = {"location": "A", "banes": [23], "boons": []}
    app.save_campaign()
    app.start_evergreen_attempt()
    gs, g = _game_screen(app), app.game
    g.enemy.hp = g.enemy.max_hp = 100
    set_hand(g, ["AS", "9S", "8S", "7C", "6C"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["AS"])
    _tap_button(app, "Play")
    if g.phase == PHASE_SUFFER:
        _tap_button(app, "Suggest")
        _tap_button(app, "Discard")
    assert g.decision["kind"] == "poison" and gs.left_btn.title == "Reserve → zone"
    _titles_fit(app)
    # the Restored Arrows and Precision Strike overlays
    _pull(g, "10H")
    g.discard.insert(0, "10H")
    g.banished = [g.tavern.pop(0), g.tavern.pop(0)]
    g.decision = {"kind": "restored_arrows", "player": 0, "resume": "defeat", "exact": True}
    gs.refresh(after_action=False)
    assert isinstance(gs.overlay, RestoredArrowsOverlay) and ui.find(app, lambda v: isinstance(v, ui.Button) and v.title == "Put under reserve")
    _titles_fit(app)
    g.decision = {"kind": "precision_strike", "player": 0, "resume": "defeat", "exact": True}
    gs.refresh(after_action=False)
    assert isinstance(gs.overlay, PickOverlay) and ui.button(app, "Take top of discard (10♥)")
    _titles_fit(app)


def test_finding_27_status_line_keeps_the_jester_count_and_mission10_shows_the_next_enemy(app, monkeypatch):
    from app.screens import status_text
    from app import theme as T
    app.new_campaign(1, ["Solo"])
    app.start_attempt()
    gs, g = _game_screen(app), app.game
    g.banished = [g.tavern.pop(0) for _ in range(12)]
    gs.refresh(after_action=False)
    text = gs.status.text
    assert "Jesters 2" in text and ui.measure_string(text, 0, (T.FONT, 13))[0] <= gs.status.width
    assert not ui.label_truncated(gs.status)
    assert status_text(g, 1000) .startswith("Turn ")      # with room, the turn is shown
    # mission 10: the next enemy of the face-up deck lies face up on the castle pile (the
    # enemy's card in words is gone)
    gs, g = _late_mission_attempt(app, 10)
    gs.refresh(after_action=False)
    assert "next:" not in gs.status.text
    castle = gs.pile_views["castle"]
    assert g.castle and castle.top is not None and castle.top.id == g.castle[0] and castle.count == len(g.castle)
    assert castle.top_view is not None and castle.top_view.card.id == g.castle[0]


def test_finding_28_azure_emblem_place_never_offers_a_locked_pilgrim(app):
    gs, g = _mission_attempt(app, 7, names=("Ana", "Ben"), relics=("emblem",))
    from helpers import set_mission_enemy, _pull
    g.extra["pilgrim_deck"].extend(g.mission_zone)
    g.mission_zone = []
    set_mission_enemy(g, "WLJH", hp=100)
    pilgrim = [x for x in g.extra["pilgrim_deck"]][0]
    g.extra["pilgrim_deck"].remove(pilgrim)
    set_hand(g, ["5M", "9S"], player=0)
    set_hand(g, ["7C", "AS"], player=1)
    g.players[1].hand.append(pilgrim)
    gs.reveal_hand()
    gs.hand.set_selection(["5M"])
    _tap_button(app, "Play")
    assert g.decision["kind"] == "emblem_place" and g.deciding == 1
    _tap_button(app, "Show my hand")
    assert gs.right_btn.title == "Place"
    assert not gs.hand.selectable(g.card(pilgrim)) and gs.hand.views[pilgrim].shaded
    _tap_card(app, gs, pilgrim)
    assert gs.hand.selected == [] and not gs.right_btn.enabled
    _tap_card(app, gs, "7C")
    assert gs.right_btn.enabled


def test_finding_29_flute_cards_are_not_selectable_while_suffering(app):
    from helpers import set_enemy as _set_enemy
    app.new_campaign(1, ["Solo"])
    app.campaign.relics.append("flute")
    app.save_campaign()
    app.start_attempt()
    gs, g = _game_screen(app), app.game
    _set_enemy(g, "J", "H")
    set_hand(g, ["6C", "3C", "5H", "5D", "8S"])
    g.extra["flute"] = []
    gs.refresh(after_action=False)
    g.special([a for a in g.legal_actions() if a.get("name") == "flute_store" and a["card"] == "3C"][0])
    gs.hand.set_selection(["6C"])
    _tap_button(app, "Play")
    assert g.phase == PHASE_SUFFER and "3C" in [c.id for c in gs.hand.cards]      # shown, badged "flute"
    assert not gs.hand.selectable(g.card("3C")) and gs.hand.views["3C"].shaded
    _tap_card(app, gs, "3C")
    assert "3C" not in gs.hand.selected
    gs.hand.set_selection(["3C", "8S"])
    assert gs.hand.selected == ["8S"] and not gs.right_btn.enabled


def test_finding_30_an_unreadable_attempt_can_be_deleted_from_the_campaign_screen(app):
    from app import store
    from app.screens import CampaignScreen
    import console
    app.new_campaign(1, ["Solo"])
    app.start_attempt()
    slot = app.campaign.slot
    with open(store.attempt_path(slot), "w") as f:
        f.write("{ not json")
    app.show(CampaignScreen(app))
    assert ui.button(app, "Continue attempt")
    console.script_answers(2)                          # Cancel: the file stays
    _tap_button(app, "Continue attempt")
    assert isinstance(app.current, CampaignScreen) and store.has_attempt(slot)
    assert console.history[-1][1] == "The saved attempt could not be loaded"
    console.script_answers(1)                          # delete it
    _tap_button(app, "Continue attempt")
    assert not store.has_attempt(slot) and isinstance(app.current, CampaignScreen)
    assert ui.button(app, "Retry mission (attempt 2)") and app.campaign.losses_on(1) == 0


def test_finding_17_ui_declarations_use_pick_buttons(app):
    from app.screens import DeclareOverlay
    from helpers import set_mission_enemy, set_discard
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.m_box_opened, camp.coins = True, 5
    camp.hire("merc_ace_1")
    camp.hire("merc_25C")
    app.save_campaign()
    app.start_attempt()
    gs, g = _game_screen(app), app.game
    set_enemy(g, "Q", "H")
    set_hand(g, ["MA_1", "4D", "9S", "M25C"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["MA_1", "4D"])
    # the Wild Animal's class is declared after the play: the forecast assumes one, its numbers end in "?"
    assert _pv(gs)["decision_kind"] == "declare_class" and _rows(gs)["Attack"].endswith("?")
    _tap_button(app, "Play")
    assert g.decision["kind"] == "declare_class" and isinstance(gs.overlay, DeclareOverlay)
    titles = [b.title for b in ui.find(gs.overlay, lambda v: isinstance(v, ui.Button))]
    assert titles[:4] == ["♥ Cleric", "♦ Bard", "♣ Warrior", "♠ Paladin"]
    texts = [lab.text for lab in _labels(gs.overlay)]
    assert "Wild Animal" in texts and any("immune to Clerics" in t for t in texts)
    _assert_nothing_cut(gs.overlay)
    assert ui.render(app).size[0] > 0
    _tap_button(app, "♠ Paladin")
    assert g.decision is None and g.plays[-1].suits == ("D", "S")
    assert "Solo declares Wild Animal a Paladin." in _logged(g)
    # a 2/5 alone
    for play in g.plays:
        g.discard.extend(play.card_ids)
    set_enemy(g, "Q", "D")
    set_hand(g, ["M25C", "9S"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["M25C"])
    _tap_button(app, "Play")
    assert g.decision["kind"] == "declare_value" and isinstance(gs.overlay, DeclareOverlay)
    _tap_button(app, "Strength 5")
    assert g.plays[-1].value == 5 and g.enemy.hp == 30 - 10
