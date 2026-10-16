"""The mercenary camp and the deck list: their cards take their own taps, with nothing laid
over them (a button over a card in a scroll view would keep a held finger from scrolling);
hiring works; an error in such a tap is shown on screen and kept in errors.log instead of
going only to the console hidden under the full-screen app. (On the phone the camp's cards
did not hire because their card pop-up was removed before it was drawn: see
tests/test_card_popups.py.)"""
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


def _camp(app, coins=3):
    from app.screens import MercenaryScreen
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.m_box_opened = True
    camp.coins = coins
    app.save_campaign()
    app.show(MercenaryScreen(app))
    return app.current


def _texts(view):
    return [v.text for v in ui.find(view, lambda v: isinstance(v, ui.Label))]


def _popups(app):
    from app.screens import CardPopup
    return ui.find(app, lambda v: isinstance(v, CardPopup))


def _tap_button(app, title):
    b = ui.button(app, title)
    assert b.enabled, "button %s disabled" % title
    return ui.tap(app, *ui.root_point(app, b))


def _own_tap(app, view) -> bool:
    """A tap on ``view``'s centre lands on the card itself, and no button lies over it."""
    hit = ui.hit_test(app, *ui.root_point(app, view))
    over = [b for b in ui.find(view.superview, lambda v: isinstance(v, ui.Button))
            if b.x < view.x + view.width and view.x < b.x + b.width and b.y < view.y + view.height and view.y < b.y + b.height]
    return hit is view and view.touch_enabled and not over


def test_every_camp_card_takes_its_own_tap_and_hiring_works(app):
    from app import store
    ms = _camp(app)
    assert len(ms.card_views) == 14
    for mid, v in ms.card_views.items():
        assert _own_tap(app, v), mid
    card = ms.card_views["merc_12D"]
    hit = ui.tap(app, *ui.root_point(app, card))
    assert hit is card and len(_popups(app)) == 1
    _tap_button(app, "Hire for 1 coin")
    ms = app.current
    assert app.campaign.mercenaries == ["merc_12D"] and app.campaign.coins == 2
    assert not ms.card_views["merc_12D"].shaded and ms.card_views["merc_12D"].selected
    assert "Coins: 2" in _texts(ms) and not _popups(app)
    assert store.load_campaign(app.campaign.slot).mercenaries == ["merc_12D"]
    # the rebuilt grid takes its taps the same way: a second hire
    assert all(_own_tap(app, v) for v in ms.card_views.values())
    ui.tap(app, *ui.root_point(app, ms.card_views["merc_25S"]))
    _tap_button(app, "Hire for 1 coin")
    assert app.campaign.mercenaries == ["merc_12D", "merc_25S"] and app.campaign.coins == 1


def test_the_deck_lists_relics_and_beasts_take_their_own_taps(app):
    from app.screens import CampaignScreen
    from app.widgets import RelicCard
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.relics.append("flute")
    camp.flags["beasts"] = True
    app.save_campaign()
    app.show(CampaignScreen(app))
    _tap_button(app, "Deck list")
    ps = app.current
    relic = ui.find(app, lambda v: isinstance(v, RelicCard))[0]
    assert _own_tap(app, relic) and all(_own_tap(app, v) for v in ps.beast_views.values())
    ui.tap(app, *ui.root_point(app, relic))
    assert len(_popups(app)) == 1
    _tap_button(app, "Close")
    ui.tap(app, *ui.root_point(app, ps.beast_views["B_S"]))
    assert camp.beast == "B_S" and ps.beast_views["B_S"].selected


def test_an_error_while_hiring_is_shown_and_logged_on_the_phone(app, monkeypatch, tmp_path):
    from app import store
    from regicide.campaign import CampaignState
    _camp(app)

    def jammed(self, mid, scope="mission"):
        raise RuntimeError("purse jammed")
    monkeypatch.setattr(CampaignState, "hire", jammed)
    ui.tap(app, *ui.root_point(app, app.current.card_views["merc_12H"]))
    with pytest.raises(RuntimeError):                 # off the phone it is raised as usual
        _tap_button(app, "Hire for 1 coin")
    monkeypatch.setattr(store, "_is_pythonista", lambda: True)
    del console.history[:]
    assert not _popups(app)                           # the card closed as Hire was tapped
    ui.tap(app, *ui.root_point(app, app.current.card_views["merc_12H"]))
    _tap_button(app, "Hire for 1 coin")
    assert ("hud", "Hiring failed: RuntimeError purse jammed") in console.history
    log = (tmp_path / "errors.log").read_text()
    assert "RuntimeError: purse jammed" in log and "in _hire" in log
    # a second error is added after the first, not in its place
    from app import screens

    def broken(*a):
        raise KeyError("text")
    monkeypatch.setattr(screens, "mercenary_text", broken)
    ui.tap(app, *ui.root_point(app, app.current.card_views["merc_12H"]))
    log = (tmp_path / "errors.log").read_text()
    assert "RuntimeError: purse jammed" in log and "KeyError: 'text'" in log
    assert log.index("purse jammed") < log.index("KeyError: 'text'")


def test_an_error_opening_a_card_is_shown_too(app, monkeypatch):
    from app import screens, store
    _camp(app)
    monkeypatch.setattr(store, "_is_pythonista", lambda: True)

    def broken(*a):
        raise KeyError("text")
    monkeypatch.setattr(screens, "mercenary_text", broken)
    del console.history[:]
    ui.tap(app, *ui.root_point(app, app.current.card_views["merc_12H"]))
    assert ("hud", "Opening the card failed: KeyError 'text'") in console.history and not _popups(app)


def test_an_error_swapping_is_shown_on_the_phone(app, monkeypatch):
    from app import store
    from regicide.campaign import CampaignState
    ms = _camp(app)
    app.campaign.hire("merc_12H")
    app.campaign.swaps_allowed = True
    ms.layout()
    monkeypatch.setattr(store, "_is_pythonista", lambda: True)

    def stuck(self, old, new):
        raise RuntimeError("no swap")
    monkeypatch.setattr(CampaignState, "swap", stuck)
    del console.history[:]
    ui.tap(app, *ui.root_point(app, app.current.card_views["merc_12H"]))
    _tap_button(app, "Swap")
    ui.tap(app, *ui.root_point(app, app.current.card_views["merc_12D"]))
    _tap_button(app, "Take it in place of 12 Cleric")
    assert ("hud", "Swapping failed: RuntimeError no swap") in console.history and not _popups(app)


def test_an_error_choosing_a_beast_is_shown_on_the_phone(app, monkeypatch):
    from app import store
    from app.screens import CampaignScreen
    from regicide.campaign import CampaignState
    app.new_campaign(1, ["Solo"])
    app.campaign.flags["beasts"] = True
    app.save_campaign()
    app.show(CampaignScreen(app))
    _tap_button(app, "Deck list")
    monkeypatch.setattr(store, "_is_pythonista", lambda: True)

    def wild(self, beast):
        raise ValueError("no beast")
    monkeypatch.setattr(CampaignState, "set_beast", wild)
    del console.history[:]
    ui.tap(app, *ui.root_point(app, app.current.beast_views["B_S"]))
    assert ("hud", "Choosing the beast failed: ValueError no beast") in console.history


def test_a_hire_whose_save_fails_still_shows_and_says_so(app, monkeypatch):
    from app import store
    _camp(app)
    monkeypatch.setattr(store, "_is_pythonista", lambda: True)

    def full(camp):
        raise OSError("disk full")
    monkeypatch.setattr(store, "save_campaign", full)
    del console.history[:]
    ui.tap(app, *ui.root_point(app, app.current.card_views["merc_12H"]))
    _tap_button(app, "Hire for 1 coin")
    ms = app.current
    assert app.campaign.mercenaries == ["merc_12H"] and not ms.card_views["merc_12H"].shaded
    assert "Coins: 2" in _texts(ms) and not _popups(app)            # the camp was rebuilt
    assert ("hud", "Hiring failed: OSError disk full") in console.history
