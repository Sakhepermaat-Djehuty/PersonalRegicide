"""Card pop-ups (the game menu's rules card and reward card, a mercenary's card, a relic's
card) did not appear on the phone over the game menu or the mercenary camp, while the
game's own boxes did. These pin what keeps a pop-up up there: it sits on the app's root
view above the screen (a screen removes every subview when it rebuilds); it builds its card
and buttons once per size (a layout run again replaces nothing); only a whole tap on the
dimmed screen closes it (never the end of the touch that opened it); a tap on one of its
buttons closes it, then acts; leaving the screen takes it away."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import fakeui  # noqa: E402

fakeui.install()
import console  # noqa: E402
import ui  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app.screens import App, MenuScreen
    ui.set_screen_size(390, 844)
    a = App()
    a.settings["rules_card"] = False
    a.show(MenuScreen(a))
    return a


def _popups(app):
    from app.screens import CardPopup
    return ui.find(app, lambda v: isinstance(v, CardPopup))


def _buttons(view):
    return [v for v in ui.find(view, lambda v: isinstance(v, ui.Button))]


def _tap_button(app, title):
    b = ui.button(app, title)
    assert b.enabled, "button %s disabled" % title
    return ui.tap(app, *ui.root_point(app, b))


def _game_menu(app, coins=0):
    from app.screens import CampaignScreen
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.m_box_opened = bool(coins)
    camp.coins = coins
    app.save_campaign()
    app.show(CampaignScreen(app))
    return app.current


def _open_rules(app):
    _tap_button(app, "Mission rules")
    popups = _popups(app)
    assert len(popups) == 1
    return popups[0]


def test_the_rules_card_sits_above_the_game_menu_and_outlives_its_rebuilds(app):
    menu = _game_menu(app)
    popup = _open_rules(app)
    assert popup.superview is app and app.subviews[-1] is popup          # on the root, on top
    assert (popup.x, popup.y, popup.width, popup.height) == (0, 0, app.width, app.height)
    for _ in range(3):
        menu.layout()                                                    # the menu rebuilds itself
        app.layout()
    assert _popups(app) == [popup] and app.subviews[-1] is popup
    # a tap on the card's centre lands on the card, not on the menu under it
    hit = ui.hit_test(app, *ui.root_point(app, popup.face))
    assert hit is not None and popup in _ancestors(hit)
    _tap_button(app, "Got it")
    assert not _popups(app) and app.current is menu


def _ancestors(v):
    out = []
    while v is not None:
        out.append(v)
        v = v.superview
    return out


def test_a_pop_up_builds_its_card_and_buttons_once_per_size(app):
    _game_menu(app)
    popup = _open_rules(app)
    face, buttons = popup.face, _buttons(popup)
    for _ in range(3):
        popup.layout()                                                   # the same size again
    assert popup.face is face and _buttons(popup) == buttons and all(b.superview is popup for b in buttons)
    # a new size (the phone turned) lays it out afresh
    popup.frame = (0, 0, 844, 390)
    popup.layout()
    assert popup.face is not face and popup.face.superview is popup
    assert popup.face.x + popup.face.width <= 844 and popup.built_for == (844.0, 390.0)


def test_only_a_whole_tap_on_the_dimmed_screen_closes_a_pop_up(app):
    _game_menu(app)
    popup = _open_rules(app)
    beside = (4.0, app.height - 4.0)
    # the end of a touch that began elsewhere (the tap that opened the card) leaves it open
    popup.touch_ended(ui.Touch(beside, beside, "ended"))
    assert _popups(app) == [popup]
    # a touch that began on the card and ended beside it leaves it open too
    popup.touch_began(ui.Touch((popup.face.x + 10, popup.face.y + 10), (0, 0), "began"))
    popup.touch_ended(ui.Touch((popup.face.x + 10, popup.face.y + 10), (0, 0), "ended"))
    assert _popups(app) == [popup]
    ui.tap(app, *beside)                                                 # began and ended beside the card
    assert not _popups(app)


def test_every_pop_up_button_closes_it_before_acting(app):
    from app.screens import CampaignScreen, ChoiceScreen, MercenaryScreen
    # the mercenary card: Hire closes it, then the camp shows the hire
    _game_menu(app, coins=2)
    app.show(MercenaryScreen(app, back="menu"))
    seen = []
    real = MercenaryScreen._hire

    def hire(self, mid):
        seen.append(list(_popups(app)))
        real(self, mid)
    MercenaryScreen._hire = hire
    try:
        ui.tap(app, *ui.root_point(app, app.current.card_views["merc_12C"]))
        assert len(_popups(app)) == 1 and _popups(app)[0].superview is app
        _tap_button(app, "Hire for 1 coin")
    finally:
        MercenaryScreen._hire = real
    assert seen == [[]] and not _popups(app)
    assert app.campaign.mercenaries == ["merc_12C"] and not app.current.card_views["merc_12C"].shaded
    # a reward card: Choose closes it and opens the choice screen
    app.campaign.pending.append({"kind": "choice_corrupt", "phase": "reward",
                                 "options": [str(app.campaign.party[0]["id"])]})
    app.show(CampaignScreen(app))
    reward = [b for b in _buttons(app) if b.title.startswith("Reward:")]
    assert reward
    ui.tap(app, *ui.root_point(app, reward[0]))
    assert len(_popups(app)) == 1
    _tap_button(app, "Choose")
    assert isinstance(app.current, ChoiceScreen) and not _popups(app)


def test_leaving_the_screen_takes_the_pop_up_away(app):
    from app.screens import MenuScreen
    _game_menu(app)
    _open_rules(app)
    app.show(MenuScreen(app))
    assert not _popups(app) and isinstance(app.current, MenuScreen)


def test_the_relic_card_in_the_deck_list_sits_above_it_too(app):
    from app.screens import PartyScreen
    from app.widgets import RelicCard
    _game_menu(app)
    app.campaign.relics.append("flute")
    app.show(PartyScreen(app))
    relic = ui.find(app, lambda v: isinstance(v, RelicCard))[0]
    ui.tap(app, *ui.root_point(app, relic))
    popups = _popups(app)
    assert len(popups) == 1 and popups[0].superview is app
    app.current.layout()
    assert _popups(app) == popups
    ui.tap(app, 4, app.height - 4)
    assert not _popups(app)


def test_an_error_opening_the_rules_is_shown_on_the_phone(app, monkeypatch):
    from app import screens, store
    _game_menu(app)
    monkeypatch.setattr(store, "_is_pythonista", lambda: True)

    def broken(*a):
        raise ValueError("no rules")
    monkeypatch.setattr(screens, "rules_card", broken)
    del console.history[:]
    _tap_button(app, "Mission rules")
    assert ("hud", "Opening the rules failed: ValueError no rules") in console.history and not _popups(app)


def test_a_pop_up_follows_the_app_when_it_changes_size(app):
    _game_menu(app)
    popup = _open_rules(app)
    app.frame = (0, 0, 844, 390)                                         # the phone turned
    assert (popup.width, popup.height) == (844, 390) and popup.built_for == (844.0, 390.0)
    assert app.subviews[-1] is popup and _popups(app) == [popup]
