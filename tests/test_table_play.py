"""Playing the lab table: the suffer step counts down in red, and the action bar never
flickers while cards are selected (a button is only touched when its look changes)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402

from app import theme as T  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402
from regicide.engine import PHASE_PLAY, PHASE_SUFFER  # noqa: E402
from helpers import _pull, set_hand, set_mission_enemy  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app.screens import App, MenuScreen
    ui.set_screen_size(390, 844)
    a = App()
    a.settings["rules_card"] = False
    a.show(MenuScreen(a))
    return a


def _mission(app, number, relics=()):
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.mission, camp.completed = number, list(range(1, number))
    camp.relics.extend(relics)
    if number >= 5:
        P.add_card(camp.party, dict(M.GORAN))
        camp.flags["beasts"] = True
    for d in M.MAGE_DECK:
        P.add_card(camp.party, dict(d))
    app.save_campaign()
    app.start_attempt()
    g = app.game
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    gs = app.current
    gs.refresh(after_action=False)
    return gs, g


def _header_strings(gs, monkeypatch):
    calls = []
    real = ui.draw_string

    def spy(text, rect=(0, 0, 0, 0), font=None, color=None, *a, **k):
        calls.append((str(text), color))
        return real(text, rect, font, color, *a, **k)
    monkeypatch.setattr(ui, "draw_string", spy)
    ui.render(gs.enemy)
    monkeypatch.setattr(ui, "draw_string", real)
    return calls


def test_the_suffer_step_counts_down_in_red_to_covered(app, monkeypatch):
    gs, g = _mission(app, 4)
    set_mission_enemy(g, "LABJD", hp=30)
    set_hand(g, ["3S", "AS", "9C", "10C", "8S", "2H"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3S"])
    gs._right(None)
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
        gs.refresh(after_action=False)
    assert g.phase == PHASE_SUFFER and g.pending_damage == 7
    shown = _header_strings(gs, monkeypatch)
    assert ("SUFFER", T.DANGER) in shown and ("7", T.DANGER) in shown and ("of 7", T.MUTED) in shown
    gs.hand.set_selection(["2H"])
    shown = _header_strings(gs, monkeypatch)
    assert ("5", T.DANGER) in shown and not any(t == "covered" for t, _ in shown)
    gs.hand.set_selection(["2H", "AS"])
    assert ("4", T.DANGER) in _header_strings(gs, monkeypatch)
    gs.hand.set_selection(["2H", "AS", "9C"])                # 12 covers 7
    shown = _header_strings(gs, monkeypatch)
    assert ("0", T.OK) in shown and ("covered", T.OK) in shown
    assert not any(t.endswith("to go") for t, _ in shown)


def test_selecting_cards_never_resets_the_flute_button(app, monkeypatch):
    gs, g = _mission(app, 5, relics=("flute",))
    set_hand(g, ["5S", "5C", "3D", "3H", "7C", "AS", "9D", "2H"])
    gs.refresh(after_action=False)
    assert g.phase == PHASE_PLAY and gs.left_btn.title == "Flute" and gs.left_btn.enabled
    touched = []
    real_setattr = type(gs.left_btn).__setattr__
    buttons = (gs.left_btn, gs.mid_btn, gs.right_btn, gs.special_btn)

    def spy(obj, name, value):
        if obj in buttons and name in ("title", "enabled", "hidden", "background_color", "tint_color"):
            touched.append((buttons.index(obj), name, value))
        real_setattr(obj, name, value)
    monkeypatch.setattr(type(gs.left_btn), "__setattr__", spy)
    for sel in (["5C"], ["5C", "5S"], ["5C"], [], ["9D"], []):
        gs.hand.set_selection(sel)
    # the Flute button (0) and the Jester button (1) look the same throughout: never touched;
    # only Play (2) turns on and off with the selection
    assert not [t for t in touched if t[0] in (0, 1, 3)], touched
    assert ("enabled" in [n for i, n, _ in touched if i == 2])
    assert gs.left_btn.title == "Flute" and gs.left_btn.enabled
    assert gs.flute_slot is gs.left_btn                      # the real button, not a stand-in
    # it still opens the Flute
    from app.screens import SpecialOverlay
    gs._left(gs.left_btn)
    assert isinstance(gs.overlay, SpecialOverlay)


def test_the_flute_takes_the_jester_slot_while_suffering_without_blinking(app, monkeypatch):
    gs, g = _mission(app, 5, relics=("flute",))
    set_hand(g, ["3S", "AS", "9C", "10C", "8S", "2H", "4D"])
    set_mission_enemy(g, [c for c in [g.enemy.card_id] + list(g.castle) if "C" in g.cards[c].suits][0])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3S"])
    gs._right(None)
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
        gs.refresh(after_action=False)
    assert g.phase == PHASE_SUFFER and gs.mid_btn.title == "Flute" and gs.flute_slot is gs.mid_btn
    touched = []
    real_setattr = type(gs.mid_btn).__setattr__

    def spy(obj, name, value):
        if obj is gs.mid_btn and name in ("title", "enabled", "hidden"):
            touched.append((name, value))
        real_setattr(obj, name, value)
    monkeypatch.setattr(type(gs.mid_btn), "__setattr__", spy)
    gs.hand.set_selection(["2H"])
    gs.hand.set_selection(["2H", "AS"])
    assert touched == []
