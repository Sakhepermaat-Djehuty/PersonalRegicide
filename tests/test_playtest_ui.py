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
    from app.screens import GameScreen, RulesOverlay, CardPopup, CampaignScreen
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
    # drawn as a playing card: the mission's name and place on top, the rules below
    face = ui.find(gs.overlay, lambda v: isinstance(v, widgets.PlayingCardFace))
    assert len(face) == 1 and face[0].corner == [("1", T.CARD_INK_MUTED)]
    assert M.MISSIONS[0]["location"] in _texts(face[0])
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
    # the game menu has it too, as the same card over the menu
    app.show(CampaignScreen(app))
    _tap(app, "Mission rules")
    popups = ui.find(app, lambda v: isinstance(v, CardPopup))
    assert len(popups) == 1 and any(M.MISSIONS[0]["summary"] in t for t in _texts(popups[0]))
    assert ui.render(app).size[0] > 0
    _tap(app, "Got it")
    assert not ui.find(app, lambda v: isinstance(v, CardPopup)) and isinstance(app.current, CampaignScreen)


def test_the_rules_card_setting_turns_the_pop_up_off(app):
    from app.screens import GameScreen
    app.settings["rules_card"] = False
    _tap(app, "New game")
    _tap(app, "Start")
    _tap(app, "Next mission: start")
    assert isinstance(app.current, GameScreen) and app.current.overlay is None
    assert app.campaign.flags.get("rules_seen", []) == []      # it still pops up once turned back on


def test_relics_are_explained_in_rewards_on_the_rules_card_and_in_the_deck_list(app):
    from app.screens import CardPopup, PartyScreen, mission_rules_text
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
    # the relics are a row of cards with no text beside them; a tap opens the relic's card
    assert "Relics" in texts and "Kinfolk Flute" not in texts and relic_text("flute", 1) not in texts
    assert any(t.startswith("Mercenaries · until mission 1 is won") for t in texts)
    relic_cards = ui.find(app, lambda v: isinstance(v, widgets.RelicCard))
    assert [v.relic_id for v in relic_cards] == ["flute", "whistle"]
    assert relic_cards[0].y == relic_cards[1].y                 # side by side
    shown = [v.card.id for v in ui.find(app, lambda v: isinstance(v, CardView))]
    assert "M12H" in shown and "MA_1" in shown
    assert ui.render(app).size[0] > 0
    ui.tap(app, *ui.root_point(app, relic_cards[0]))
    popup = ui.find(app, lambda v: isinstance(v, CardPopup))[0]
    face = ui.find(popup, lambda v: isinstance(v, widgets.PlayingCardFace))[0]
    labels = ui.find(face, lambda v: isinstance(v, ui.Label))
    # name and icon on top, the description below
    icon = [v for v in labels if v.text == RELICS["flute"]["symbol"]][0]
    name = [v for v in labels if v.text == "Kinfolk Flute"][0]
    body = [v for v in labels if v.text == relic_text("flute", 1)][0]
    assert icon.y < name.y and name.text_color == T.CARD_INK and "Relic · solo side" in _texts(face)
    assert body.superview.y > name.y + name.height
    assert face.edge == RELICS["flute"]["color"] and ui.render(app).size[0] > 0
    _tap(app, "Close")
    assert not ui.find(app, lambda v: isinstance(v, CardPopup))
    # a tap beside the card closes it too
    ui.tap(app, *ui.root_point(app, relic_cards[1]))
    popup = ui.find(app, lambda v: isinstance(v, CardPopup))[0]
    assert relic_text("whistle", 1) in _texts(popup)
    ui.tap(app, 4, app.height - 4)
    assert not ui.find(app, lambda v: isinstance(v, CardPopup))
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
        assert ("♜", T.SUIT_COLOR["G"]) in calls and ("♥", T.SUIT_COLOR["H"]) in calls
    finally:
        ui.draw_string = real


def test_the_rules_card_counts_as_seen_only_once_dismissed_and_returns_on_resume(app):
    from app.screens import GameScreen, RulesOverlay
    _tap(app, "New game")
    _tap(app, "Start")
    _tap(app, "Next mission: start")
    assert isinstance(app.current.overlay, RulesOverlay)
    assert app.campaign.flags.get("rules_seen", []) == []          # not yet dismissed
    app.autosave()
    assert app.resume_attempt()
    assert isinstance(app.current, GameScreen) and isinstance(app.current.overlay, RulesOverlay)
    _tap(app, "Got it")
    assert app.campaign.flags["rules_seen"] == [1]
    assert app.resume_attempt() and app.current.overlay is None


def test_mission_rules_before_mission_12_show_the_restored_mother(app):
    from app.screens import mission_rules_text
    _tap(app, "New game")
    _tap(app, "Start")
    camp = app.campaign
    camp.mission, camp.completed = 12, list(range(1, 12))
    camp.relics.extend(["flute", "mother"])
    text = mission_rules_text(camp)
    assert "Evergreen Mother (restored)" in text and "Evergreen Mother (corrupt)" not in text


def test_deck_list_beasts_follow_the_setup_rules(app):
    from app import store
    from app.screens import PartyScreen
    _tap(app, "New game")
    _tap(app, "Start")
    camp = app.campaign
    camp.flags["beasts"] = True
    camp.set_beast("B_H")
    camp.mission = 10
    app.show(PartyScreen(app))
    # all four beasts on display, the chosen one with the gold selection border
    ps = app.current
    assert "Gøran's beast · next attempt" in _texts(app)
    assert [b for b, v in ps.beast_views.items() if v.selected] == ["B_H"] and len(ps.beast_views) == 4
    ui.tap(app, *ui.root_point(app, ps.beast_views["B_S"]))       # another: it swaps
    assert camp.beast == "B_S" and [b for b, v in ps.beast_views.items() if v.selected] == ["B_S"]
    assert any(t.startswith("B♠ joins the next attempt") for t in _texts(app))
    ui.tap(app, *ui.root_point(app, ps.beast_views["B_S"]))       # the chosen one again: no beast
    assert camp.beast is None and not any(v.selected for v in ps.beast_views.values())
    assert store.load_campaign(camp.slot).beast is None
    ui.tap(app, *ui.root_point(app, ps.beast_views["B_H"]))
    assert store.load_campaign(camp.slot).beast == "B_H"
    camp.mission = 11                                                  # all four form the beast deck
    app.show(PartyScreen(app))
    texts = _texts(app)
    assert "Gøran's beasts · mission 11's beast deck" in texts and not app.current.beast_views
    assert not any(t.startswith("Gøran's beast · ") for t in texts)
    # during an attempt the choice is locked
    camp.mission = 1
    app.save_campaign()
    app.start_attempt()
    app.show(PartyScreen(app))
    ps = app.current
    assert "Gøran's beast · this attempt" in _texts(app)
    ui.tap(app, *ui.root_point(app, ps.beast_views["B_C"]))
    assert camp.beast == "B_H" and ps.beast_views["B_H"].selected


def test_the_game_menu_names_a_reward_briefly_and_a_card_explains_it(app):
    from app.screens import CampaignScreen, CardPopup, ChoiceScreen
    _tap(app, "New game")
    _tap(app, "Start")
    camp = app.campaign
    camp.pending = [{"kind": "choice_suit", "suit": "R", "options": ["6H", "6D", "6S"],
                     "label": "The 5 Reaver teaches a 6: the Cleric, Bard or Paladin 6 gains the Reaver class"}]
    app.save_campaign()
    app.show(CampaignScreen(app))
    b = ui.button(app, "Reward: a Reaver sticker")                 # short, fits the button
    b.action(b)
    popup = ui.find(app, lambda v: isinstance(v, CardPopup))[0]
    text = " ".join(_texts(popup))
    assert "The 5 Reaver teaches a 6" in text and "Choose one of 6♥, 6♦, 6♠" in text
    assert ui.render(app).size[0] > 0
    _tap(app, "Later")
    assert not ui.find(app, lambda v: isinstance(v, CardPopup))
    b = ui.button(app, "Reward: a Reaver sticker")
    b.action(b)
    _tap(app, "Choose")
    assert isinstance(app.current, ChoiceScreen)


def test_selected_cards_show_the_order_they_were_tapped_in():
    from app.widgets import HandGrid
    from regicide.cards import Card
    grid = HandGrid(frame=(0, 0, 360, 300))
    cards = [Card(id=x, rank=x[0], suits=(x[1],), value=int(x[0])) for x in ("4C", "4H", "9S", "2D")]
    grid.set_cards(cards)
    grid._tapped(grid.views["4H"])
    assert [grid.views[c].order for c in ("4C", "4H", "9S", "2D")] == [0, 0, 0, 0]   # one card: no number
    grid._tapped(grid.views["4C"])
    grid._tapped(grid.views["2D"])
    assert [grid.views[c].order for c in ("4C", "4H", "9S", "2D")] == [2, 1, 0, 3]
    grid._tapped(grid.views["4H"])                                              # untapping renumbers
    assert [grid.views[c].order for c in ("4C", "4H", "9S", "2D")] == [1, 0, 0, 2]
    drawn = []
    real = ui.draw_string
    ui.draw_string = lambda text, *a, **kw: (drawn.append(text), real(text, *a, **kw))[1]
    try:
        ui.render(grid.views["2D"])
    finally:
        ui.draw_string = real
    assert drawn[-1] == "2"                                                     # drawn last, on top of the face
    grid.clear_selection()
    assert all(v.order == 0 for v in grid.views.values())


def test_the_mage_look_shows_the_attack_so_far(app):
    from app.screens import attack_summary
    from helpers import set_hand, set_tavern_top, _pull, set_mission_enemy
    from regicide.campaign import CampaignState
    c = CampaignState.new(1, ["Ana"], seed=91)
    c.mission, c.completed = 5, [1, 2, 3, 4]
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    g = c.start_attempt(seed=91)
    set_hand(g, ["4M", "4C", "9S", "8S"])
    for x in ("3H", "2S", "6C", "7D"):
        _pull(g, x)
    set_tavern_top(g, ["3H", "2S", "6C", "7D"])
    g.play(["4M", "4C"])
    assert g.decision["kind"] == "mage_peek"
    text = attack_summary(g, g.decision.get("play_index"))
    assert text.startswith("Your attack: 4%s + 4♣, strength 8" % P.to_card(M.MAGE_DECK[3]).label()[1:])
    assert "Warrior" in text and "Mage" in text


def test_mercenary_camp_is_reached_from_the_deck_list_not_the_game_menu(app):
    from app.screens import CampaignScreen, MercenaryScreen, PartyScreen
    _tap(app, "New game")
    _tap(app, "Start")
    camp = app.campaign
    camp.m_box_opened, camp.coins = True, 3
    camp.flags["beasts"] = True
    app.save_campaign()
    app.show(CampaignScreen(app))
    titles = [b.title for b in ui.find(app, lambda v: isinstance(v, ui.Button))]
    # the game menu no longer holds the camp nor the beast picker
    assert not any(t.startswith("Mercenary camp") for t in titles) and "None" not in titles
    assert not any(t.startswith("♣") for t in titles)
    _tap(app, "Deck list")
    assert isinstance(app.current, PartyScreen) and "Mercenaries" in _texts(app)
    _tap(app, "Mercenary camp (3 coins)")
    assert isinstance(app.current, MercenaryScreen) and app.current.back == "deck"
    _tap(app, "‹ Back")
    assert isinstance(app.current, PartyScreen)
    # during an attempt hiring waits
    app.start_attempt()
    app.show(PartyScreen(app))
    b = [v for v in ui.find(app, lambda v: isinstance(v, ui.Button)) if v.title == "Mercenary camp (after this attempt)"]
    assert b and not b[0].enabled


def test_mercenary_coins_stay_bright_on_a_shaded_card():
    calls = []
    real_set_color = ui.set_color
    ui.set_color = lambda c: (calls.append(c), real_set_color(c))[1]
    try:
        jester = [m for m in MERCENARIES if m["id"] == "merc_jester_1"][0]
        v = CardView(P.to_card(jester["card"]), frame=(0, 0, 86, 122))
        v.shaded, v.coins = True, 5
        ui.render(v)
        shade = calls.index(T.SHADE)
        coins = [i for i, c in enumerate(calls) if c == T.COIN]
        assert len(coins) == 5 and min(coins) > shade          # the coins are drawn over the shade
        # the coins sit down the right side, below the corner icons, clear of the bottom
        d, pad = widgets.coin_metrics(86, 122)
        assert 86 - pad - d > 86 * 0.6
        del calls[:]
        v.shaded, v.selected = True, True                      # a swap candidate keeps a bright border
        ui.render(v)
        assert T.ACCENT in calls[calls.index(T.SHADE):]
        del calls[:]
        v.shaded, v.coins, v.selected = False, 0, False        # an ordinary card: no coins, no shade
        ui.render(v)
        assert T.SHADE not in calls and T.COIN not in calls
    finally:
        ui.set_color = real_set_color


def test_evergreen_boon_26_shows_all_four_beasts_and_boon_24_hires_from_the_deck_list(app):
    from app.screens import MercenaryScreen, PartyScreen
    _tap(app, "New game")
    _tap(app, "Start")
    camp = app.campaign
    camp.flags["beasts"] = True
    camp.finished = True
    camp.evergreen = {"setup": {"location": "A", "banes": [2, 9, 11], "boons": [24, 26]}, "coins": 5, "mercenaries": []}
    app.save_campaign()
    app.show(PartyScreen(app))
    texts = _texts(app)
    assert "Gøran's beasts · all four join this setup" in texts and "Mercenaries · this Evergreen setup" in texts
    beasts = [v for v in ui.find(app, lambda v: isinstance(v, CardView)) if v.card.id.startswith("B_")]
    assert len(beasts) == 4 and all(v.selected for v in beasts) and not app.current.beast_views
    _tap(app, "Mercenaries (5 coins left)")
    assert isinstance(app.current, MercenaryScreen) and app.current.evergreen and app.current.back == "deck"
    assert ui.render(app).size[0] > 0
