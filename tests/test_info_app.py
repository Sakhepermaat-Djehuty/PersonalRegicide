"""The info pop-ups in the app: a fresh mission opens on its Battle start card (after the
rules card), an action's cards show over the table one tap at a time, a decision box waits
under them, a long press skips the rest, the step sounds give way to the cards' clips, and
the master box off brings the step sounds back."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import sound  # noqa: E402
import ui  # noqa: E402

from helpers import set_enemy, set_hand, set_tavern_top  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app.screens import App, MenuScreen
    ui.set_screen_size(390, 844)
    a = App()
    a.settings["rules_card"] = False
    a.settings["info_popups"] = True
    a.show(MenuScreen(a))
    return a


def _queue(app):
    return app.info_queue()


def _tap_queue(app):
    q = _queue(app)
    ui.tap(app, q.width / 2.0, 30)            # anywhere on it, even off the card


def _attempt(app, number=5):
    from test_app import _mission_attempt
    return _mission_attempt(app, number)


def _played():
    return [os.path.basename(h[1]).rsplit(".", 1)[0] for h in sound.history if h[0] == "effect"]


def test_a_fresh_mission_opens_on_battle_start_and_a_tap_shows_the_table(app):
    gs, g = _attempt(app, 3)
    q = _queue(app)
    assert q is not None and [c.id for c in q.cards][0] == "battle_start"
    from regicide.campaign.missions import MISSIONS
    assert q.face.title == [m["title"] for m in MISSIONS if m["number"] == 3][0]
    while _queue(app) is not None:
        _tap_queue(app)
    assert gs.overlay is None and gs.right_btn.title == "Play"


def _listen(app, monkeypatch):
    """What the app asks to hear: (kind, name) for step sounds and the cards' clips."""
    heard = []
    real_effect, real_clip = app.audio.effect, app.audio.clip
    monkeypatch.setattr(app.audio, "effect", lambda name, delay=0.0: heard.append(("effect", name)) or real_effect(name, delay))
    monkeypatch.setattr(app.audio, "clip", lambda names: heard.append(("clip", names[0])) or real_clip(names))
    return heard


def _ready(app, number=1):
    gs, g = _attempt(app, number)
    while _queue(app) is not None:
        _tap_queue(app)
    g.enemy.hp = 100
    return gs, g


def test_an_attack_shows_its_cards_one_tap_at_a_time_and_the_box_waits_under_them(app, monkeypatch):
    from app.screens import MagePeekOverlay
    gs, g = _ready(app)
    set_hand(g, ["3M", "9S", "8S"])
    set_tavern_top(g, ["2C", "6D", "4H"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3M"])
    heard = _listen(app, monkeypatch)
    ui.tap(app, *ui.root_point(app, ui.button(app, "Play")))
    q = _queue(app)
    assert q is not None and [c.id for c in q.cards] == ["mage"] and q.face.title == "Mage"
    assert isinstance(gs.overlay, MagePeekOverlay)              # already there, under the card
    assert q.superview is app and app.subviews.index(q) > app.subviews.index(gs)
    ui.run_delays()
    assert ("clip", "info_mage") in heard and not [h for h in heard if h[0] == "effect" and h[1] != "button"]
    _tap_queue(app)
    assert _queue(app) is None and isinstance(gs.overlay, MagePeekOverlay) and ("effect", "card_down") in heard


def test_a_long_press_skips_the_rest_of_the_queue(app):
    gs, g = _ready(app)
    g.enemy.hp = 6
    set_hand(g, ["6H", "9S", "8S"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["6H"])
    ui.tap(app, *ui.root_point(app, ui.button(app, "Play")))
    q = _queue(app)
    assert q is not None and len(q.cards) >= 2                   # the blow, the kill, the next enemy...
    ui.cancel_delays()
    q.touch_began(ui.Touch((10, 10), (10, 10), "began"))
    ui.run_delays()
    assert _queue(app) is None and q.closed
    q.touch_ended(ui.Touch((10, 10), (10, 10), "ended"))
    assert gs.right_btn.title == "Play" and gs.overlay is None


def test_the_master_box_off_brings_the_step_sounds_back_and_shows_no_card(app, monkeypatch):
    gs, g = _ready(app)
    app.settings["info_popups"] = False
    set_hand(g, ["9S", "8S", "7D", "6D", "5D"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["9S"])
    heard = _listen(app, monkeypatch)
    ui.tap(app, *ui.root_point(app, ui.button(app, "Play")))
    ui.run_delays()
    assert _queue(app) is None and ("effect", "hit") in heard and not [h for h in heard if h[0] == "clip"]
