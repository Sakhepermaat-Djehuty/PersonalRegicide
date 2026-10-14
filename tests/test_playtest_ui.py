"""Changes from the owner's first phone playtest: the rules card, relics and mercenaries
in the deck list, the button font, multi-class colours and the Wild Animal's face."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402

from app import theme as T  # noqa: E402
from app import widgets  # noqa: E402
from app.widgets import CardView, make_button, fit_title  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402
from regicide.campaign.mercenaries import MERCENARIES  # noqa: E402
from regicide.campaign.relics import RELICS, relic_name, relic_text  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app.screens import App, MenuScreen
    ui.set_screen_size(390, 844)
    a = App()
    a.show(MenuScreen(a))
    return a


def _texts(view):
    return [v.text for v in ui.find(view, lambda v: isinstance(v, ui.Label))]


def _tap(app, title):
    b = ui.button(app, title)
    assert b.enabled, title
    b.action(b)


def test_fit_title_never_reuses_the_font_name_ios_returns():
    """On iOS ``button.font`` reads back as the system font's internal name, which can't be
    set again (the title fell back to a serif font on the owner's phone)."""
    b = make_button("Jester attack", lambda s: None, (0, 0, 60, 40))
    b.font = (".SFUI-Semibold", 16)
    fit_title(b)
    assert b.font[0] == T.FONT_BOLD and b.font[1] < 16
    fit_title(b, bold=False)
    assert b.font[0] == T.FONT


def test_rules_card_shows_once_when_a_mission_first_loads_and_from_the_menus(app):
    from app.screens import GameScreen, RulesOverlay, MissionRulesScreen, CampaignScreen
    _tap(app, "New game")
    _tap(app, "Start")
    camp = app.campaign
    # the game menu shows one line of flavour, not the rules
    assert M.MISSIONS[0]["flavour"] in _texts(app) and M.MISSIONS[0]["summary"] not in _texts(app)
    _tap(app, "Next mission: start")
    gs = app.current
    assert isinstance(gs, GameScreen) and isinstance(gs.overlay, RulesOverlay)
    text = "\n".join(_texts(gs.overlay))
    assert "Mission 1 · Call to Arms" in text and M.MISSIONS[0]["summary"] in text
    assert ui.render(app).size[0] > 0
    _tap(app, "Got it")
    assert gs.overlay is None and gs.mid_btn.title == "Jester attack" and camp.flags["rules_seen"] == [1]
    # again from the in-game menu
    _tap(app, "Menu")
    _tap(app, "Mission rules")
    assert isinstance(gs.overlay, RulesOverlay)
    _tap(app, "Got it")
    # a second attempt of the same mission does not pop it up
    app.show(CampaignScreen(app))
    app.start_attempt()
    assert app.current.overlay is None
    # the game menu has it too, as a screen
    app.show(CampaignScreen(app))
    _tap(app, "Mission rules")
    assert isinstance(app.current, MissionRulesScreen) and any(M.MISSIONS[0]["summary"] in t for t in _texts(app))


def test_the_rules_card_setting_turns_the_pop_up_off(app):
    from app.screens import GameScreen
    app.settings["rules_card"] = False
    _tap(app, "New game")
    _tap(app, "Start")
    _tap(app, "Next mission: start")
    assert isinstance(app.current, GameScreen) and app.current.overlay is None
    assert app.campaign.flags.get("rules_seen", []) == []      # it still pops up once turned back on


def test_relics_are_explained_in_rewards_on_the_rules_card_and_in_the_deck_list(app):
    from app.screens import PartyScreen, mission_rules_text
    _tap(app, "New game")
    _tap(app, "Start")
    camp = app.campaign
    line = M.apply_step(camp, {"kind": "relic", "relic": "flute", "label": "Relic: Kinfolk Flute"}, None)
    assert line.startswith("Gained relic: Kinfolk Flute. Once per turn at any time")     # solo side
    camp.relics.append("whistle")
    assert "Scarlet Whistle: When you form an attack with a solitary animal companion" in mission_rules_text(camp)
    camp.m_box_opened = True
    camp.coins = 5
    camp.hire("merc_12H")
    camp.hire("merc_ace_1")
    app.save_campaign()
    app.show(PartyScreen(app))
    texts = _texts(app)
    assert "Relics" in texts and "Kinfolk Flute" in texts and "Scarlet Whistle" in texts
    assert relic_text("flute", 1) in texts
    assert any(t.startswith("Mercenaries · until mission 1 is won") for t in texts)
    relic_cards = ui.find(app, lambda v: isinstance(v, widgets.RelicCard))
    assert [v.relic_id for v in relic_cards] == ["flute", "whistle"]
    shown = [v.card.id for v in ui.find(app, lambda v: isinstance(v, CardView))]
    assert "M12H" in shown and "MA_1" in shown
    assert ui.render(app).size[0] > 0
    # two players read the other side
    assert relic_text("flute", 2).startswith("After you form an attack")
    assert all(relic_name(r) for r in RELICS)


def test_wild_animal_has_a_class_icon_in_each_corner_and_multi_class_pips_keep_their_colours():
    calls = []
    real = ui.draw_string
    ui.draw_string = lambda text, rect=None, font=None, color=None, *a, **kw: (calls.append((text, color)), real(text, rect, font, color, *a, **kw))[1]
    try:
        wild = [m["card"] for m in MERCENARIES if m["id"] == "merc_ace_1"][0]
        for small in (False, True):
            del calls[:]
            v = CardView(P.to_card(wild), frame=(0, 0, 80, 114))
            v.small = small
            ui.render(v)
            drawn = dict((t, c) for t, c in calls)
            assert all(drawn.get(sym) == T.SUIT_COLOR[s] for s, sym in (("H", "♥"), ("D", "♦"), ("C", "♣"), ("S", "♠")))
            assert "A" in drawn
        # a two-class card: each icon in its own colour, on cards and on the enemy panel
        del calls[:]
        v = CardView(P.to_card({"id": "8H", "rank": "8", "suits": ["H", "G"], "value": 8}), frame=(0, 0, 80, 114))
        ui.render(v)
        assert ("⛨", T.SUIT_COLOR["G"]) in calls and ("♥", T.SUIT_COLOR["H"]) in calls
    finally:
        ui.draw_string = real
