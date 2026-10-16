"""The mercenary camp and the deck list take taps on their cards through clear buttons laid
over them (on the phone, taps on the camp's cards did not hire), and an error in such a
tap is shown on screen and kept in errors.log instead of going only to the console hidden
under the full-screen app."""
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


def _covered(app, view) -> bool:
    """A tap on ``view``'s centre lands on a clear button with its frame, beside it."""
    hit = ui.hit_test(app, *ui.root_point(app, view))
    return (isinstance(hit, ui.Button) and hit.superview is view.superview and not hit.title
            and (hit.x, hit.y, hit.width, hit.height) == (view.x, view.y, view.width, view.height))


def test_every_camp_card_takes_its_tap_through_a_button_and_hiring_works(app):
    from app import store
    ms = _camp(app)
    assert len(ms.card_views) == 14
    for mid, v in ms.card_views.items():
        assert _covered(app, v) and not v.touch_enabled, mid
    hit = ui.tap(app, *ui.root_point(app, ms.card_views["merc_12D"]))
    assert isinstance(hit, ui.Button) and len(_popups(app)) == 1
    _tap_button(app, "Hire for 1 coin")
    ms = app.current
    assert app.campaign.mercenaries == ["merc_12D"] and app.campaign.coins == 2
    assert not ms.card_views["merc_12D"].shaded and ms.card_views["merc_12D"].selected
    assert "Coins: 2" in _texts(ms) and not _popups(app)
    assert store.load_campaign(app.campaign.slot).mercenaries == ["merc_12D"]
    # the rebuilt grid has its buttons again: a second hire goes the same way
    assert all(_covered(app, v) for v in ms.card_views.values())
    ui.tap(app, *ui.root_point(app, ms.card_views["merc_25S"]))
    _tap_button(app, "Hire for 1 coin")
    assert app.campaign.mercenaries == ["merc_12D", "merc_25S"] and app.campaign.coins == 1


def test_the_deck_lists_relics_and_beasts_take_their_taps_through_buttons(app):
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
    assert _covered(app, relic) and all(_covered(app, v) for v in ps.beast_views.values())
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
    _tap_button(app, "Hire for 1 coin")
    assert ("hud", "Hiring failed: RuntimeError purse jammed") in console.history
    log = (tmp_path / "errors.log").read_text()
    assert "RuntimeError: purse jammed" in log and "in _hire" in log


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
