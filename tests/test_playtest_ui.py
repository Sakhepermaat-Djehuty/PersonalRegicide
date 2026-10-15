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
    _tap(app, "Mission rules")
    ui.tap(app, 4, app.height - 4)
    assert not ui.find(app, lambda v: isinstance(v, CardPopup))


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


@pytest.mark.parametrize("step, title", [
    ({"kind": "choice_suit", "suit": "G", "options": ["8H", "8D", "8C"], "label": "Guardian sticker"}, "a Guardian sticker"),
    ({"kind": "choice_mage_student", "options": ["4", "8"], "label": "A new student"}, "a new mage"),
    ({"kind": "choice_corrupt", "options": ["5H"], "label": "Corrupt a character"}, "corruption"),
    ({"kind": "choice_rip", "options": ["5H"], "label": "The Eternal Vine"}, "the Eternal Vine"),
    ({"kind": "choice_classes", "cards": ["5H", "6D"], "label": "Class stickers"}, "class stickers"),
])
def test_every_reward_kind_opens_a_playing_card_with_its_icon(app, step, title):
    from app.screens import CampaignScreen, CardPopup, choice_icon
    _tap(app, "New game")
    _tap(app, "Start")
    app.campaign.pending = [dict(step)]
    app.save_campaign()
    app.show(CampaignScreen(app))
    _tap(app, "Reward: %s" % title)
    popup = ui.find(app, lambda v: isinstance(v, CardPopup))[0]
    face = ui.find(popup, lambda v: isinstance(v, widgets.PlayingCardFace))[0]
    assert _texts(face)[0] == choice_icon(step)[0][0] and "Reward" in _texts(face)
    assert step["label"] in " ".join(_texts(face)) and ui.render(app).size[0] > 0
    ui.tap(app, 4, app.height - 4)                     # a reward waits for Choose or Later
    assert ui.find(app, lambda v: isinstance(v, CardPopup))


def test_a_fresh_campaigns_deck_list_has_no_beasts_and_no_camp(app):
    from app.screens import PartyScreen
    _tap(app, "New game")
    _tap(app, "Start")
    app.show(PartyScreen(app))
    texts = _texts(app)
    assert not app.current.beast_views and not any(t.startswith("Gøran") for t in texts)
    assert "Mercenaries" not in texts and not any(t.startswith("Mercenaries") for t in texts)
    assert not any(b.title.startswith("Mercenary camp") for b in ui.find(app, lambda v: isinstance(v, ui.Button)))


def test_the_beast_note_has_room_for_every_text_it_can_show(app):
    from app.screens import PartyScreen
    for w in (320, 375, 390, 430):
        ui.set_screen_size(w, 844)
        _tap(app, "New game") if not app.campaign else None
        if app.campaign is None:
            _tap(app, "Start")
        camp = app.campaign
        camp.flags["beasts"] = True
        camp.set_beast(None)
        app.show(PartyScreen(app))
        ps = app.current
        for bid in ("B_S", "B_S", "B_H"):                 # take, drop, take
            ui.tap(app, *ui.root_point(app, ps.beast_views[bid]))
            assert not ui.label_truncated(ps.beast_note), (w, ps.beast_note.text)
    ui.set_screen_size(390, 844)


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


def test_coins_sit_in_the_same_place_on_every_mercenary_below_the_corner_icons():
    W, H = 86.0, 122.0
    d, pad = widgets.coin_metrics(W, H)
    ovals = []
    real = ui.Path.oval
    ui.Path.oval = staticmethod(lambda x, y, w, h: (ovals.append((x, y, w, h)), real(x, y, w, h))[1])
    try:
        cols = {}
        for mid, n in (("merc_ace_1", 3), ("merc_jester_1", 5), ("merc_12H", 1), ("merc_19_1", 3), ("merc_25C", 1)):
            card = [m for m in MERCENARIES if m["id"] == mid][0]["card"]
            del ovals[:]
            v = CardView(P.to_card(card), frame=(0, 0, W, H))
            v.coins, v.shaded = n, True
            ui.render(v)
            coins = [o for o in ovals if abs(o[2] - d) < 1e-6]
            assert len(coins) == n and all(abs(o[0] - (W - pad - d)) < 1e-6 for o in coins), mid
            cols[mid] = coins
        first = set(round(c[0][1], 3) for c in cols.values())
        assert len(first) == 1                                     # the same place on every card
        top = first.pop()
        # below the Wild Animal's top-right class icon (its row ends at pad/2 + 0.16 H x 1.3)
        assert top >= 2.5 + 0.16 * H * 1.3
        # five coins stay clear of the bottom; the Wild Animal's three end above its ♠ corner
        assert max(o[1] + o[3] for o in cols["merc_jester_1"]) <= H - pad
        spade_top = H - 2.5 - 0.16 * H * 1.25
        assert max(o[1] + o[3] for o in cols["merc_ace_1"]) <= spade_top
    finally:
        ui.Path.oval = real


def test_a_mercenary_jesters_text_makes_room_for_its_coins():
    calls = []
    real = ui.draw_string
    ui.draw_string = lambda text, rect=None, font=None, color=None, *a, **kw: (calls.append((text, rect)), real(text, rect, font, color, *a, **kw))[1]
    try:
        card = [m for m in MERCENARIES if m["id"] == "merc_jester_1"][0]["card"]
        v = CardView(P.to_card(card), frame=(0, 0, 86, 122))
        v.coins = 5
        ui.render(v)
        widths = dict((t, r[2]) for t, r in calls if t in ("J", "JESTER"))
        d, pad = widgets.coin_metrics(86, 122)
        assert widths["J"] == widths["JESTER"] == 86 - v.coin_room() and widths["J"] <= 86 - pad - d
        del calls[:]
        v.coins = 0
        ui.render(v)
        assert dict((t, r[2]) for t, r in calls if t in ("J", "JESTER"))["J"] == 86
        del calls[:]
        v.coins, v.badge = 5, "swap"                                # a tag draws on a Jester too
        ui.render(v)
        assert "swap" in [t for t, _ in calls]
    finally:
        ui.draw_string = real


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


def test_hiring_keeps_the_mercenary_camp_scrolled_where_it_was(app):
    from app.screens import CardPopup, MercenaryScreen
    ui.set_screen_size(320, 568)
    try:
        _tap(app, "New game")
        _tap(app, "Start")
        camp = app.campaign
        camp.m_box_opened, camp.coins = True, 9
        app.save_campaign()
        app.frame = (0, 0, 320, 568)                       # a small phone: the grid scrolls
        app.show(MercenaryScreen(app))
        ms = app.current
        room = ms.grid.content_size[1] - ms.grid.height
        assert room > 60, room
        ms.grid.content_offset = (0, 60)
        ui.tap(app, *ui.root_point(app, ms.card_views["merc_jester_1"]))
        _tap(app, "Hire for 5 coins")
        assert camp.mercenaries == ["merc_jester_1"] and not ui.find(app, lambda v: isinstance(v, CardPopup))
        assert ms.grid.content_offset[1] == 60 and ms.card_views["merc_jester_1"].selected
        # a bigger offset than the grid allows is clamped
        ms.grid.content_offset = (0, 5000)
        ms._begin_swap("merc_jester_1")
        assert 0 <= ms.grid.content_offset[1] <= ms.grid.content_size[1] - ms.grid.height
    finally:
        ui.set_screen_size(390, 844)


def _piles_game(app):
    """A mission 4 attempt with cards in all three piles."""
    app.settings["rules_card"] = False
    _tap(app, "New game")
    _tap(app, "Start")
    app.campaign.mission, app.campaign.completed = 4, [1, 2, 3]
    for d in M.MAGE_DECK:
        P.add_card(app.campaign.party, dict(d))
    app.save_campaign()
    app.start_attempt()
    gs, g = app.current, app.game
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    moved = g.tavern[:7]
    del g.tavern[:7]
    g.discard[:0] = moved                         # discard[0] is the top card
    g.banished.extend(g.tavern[:3])               # banished[-1] is the top card
    del g.tavern[:3]
    gs.refresh(after_action=False)
    return gs, g


def test_the_piles_show_the_discard_and_banished_piles_in_order_and_the_reserve_like_the_deck_list(app):
    import json
    from app.screens import PilesOverlay, deck_list_key
    gs, g = _piles_game(app)
    before = json.dumps(g.to_dict(), sort_keys=True)
    # a tap on the status line opens the piles, the discard pile first
    ui.tap(app, *ui.root_point(app, gs.piles_btn))
    ov = gs.overlay
    assert isinstance(ov, PilesOverlay) and ov.pile == "discard"
    seg = ui.find(ov, lambda v: isinstance(v, ui.SegmentedControl))[0]
    assert seg.segments == ["Discard %d" % len(g.discard), "Reserve %d" % len(g.tavern), "Banished 3"]
    shown = [v.card.id for v in sorted(ov.card_views.values(), key=lambda v: (v.y, v.x))]
    assert shown == g.discard and ov.card_views[g.discard[0]].badge == "top"
    assert "In order, the top card first." in _texts(ov) and ui.render(app).size[0] > 0
    assert not any(ui.label_truncated(v) for v in ui.find(ov, lambda v: isinstance(v, ui.Label)))
    height = ov.panel.frame[3]
    # the reserve: every card, sorted like the deck list (class, then strength), not in the deck's order
    seg.selected_index = 1
    seg.action(seg)
    shown = [v.card.id for v in sorted(ov.card_views.values(), key=lambda v: (v.y, v.x))]
    assert sorted(shown) == sorted(g.tavern) and shown != g.tavern
    keys = [deck_list_key(g.card(c)) for c in shown]
    assert keys == sorted(keys) and shown == sorted(g.tavern, key=lambda c: (deck_list_key(g.card(c)), c))
    assert any("sorted like the deck list" in t for t in _texts(ov)) and not any(v.badge for v in ov.card_views.values())
    # the same cards in another order show the same way: the view gives nothing away
    order = list(g.tavern)
    g.tavern.reverse()
    ov._switch("reserve")
    assert [v.card.id for v in sorted(ov.card_views.values(), key=lambda v: (v.y, v.x))] == shown
    g.tavern[:] = order
    assert ov.panel.frame[3] == height                     # switching piles does not move the panel
    # the banished pile, the top (last banished) first
    seg.selected_index = 2
    seg.action(seg)
    shown = [v.card.id for v in sorted(ov.card_views.values(), key=lambda v: (v.y, v.x))]
    assert shown == list(reversed(g.banished)) and ov.card_views[g.banished[-1]].badge == "top"
    # looking changes nothing in the game, not even its random state
    assert json.dumps(g.to_dict(), sort_keys=True) == before
    _tap(app, "Back")
    assert gs.overlay is None
    # the in-game menu has it too
    _tap(app, "Menu")
    _tap(app, "Discard and reserve piles")
    assert isinstance(gs.overlay, PilesOverlay)


def test_the_piles_during_a_decision_and_in_the_base_game(app):
    from app.screens import GameScreen, PilesOverlay, QuickPlayScreen
    from regicide.rules import GameConfig
    gs, g = _piles_game(app)
    # a decision is waiting: Back from the piles returns to it
    from helpers import set_hand, set_mission_enemy, set_tavern_top
    set_mission_enemy(g, "LABJD", hp=100)
    set_hand(g, ["3M", "9S", "8S"])
    set_tavern_top(g, ["4C", "10H", "2D"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3M"])
    _tap(app, "Play")
    assert g.decision["kind"] == "mage_peek"
    decision_overlay = type(gs.overlay)
    gs._show_piles("reserve")
    shown = set(gs.overlay.card_views)
    assert shown == set(g.tavern) and not shown & set(g.decision["revealed"])   # the mage's cards are out
    _tap(app, "Back")
    assert type(gs.overlay) is decision_overlay
    # base Regicide: a tavern deck, no banished pile until something is banished
    app.start_game(GameConfig(players=1), seed=3)
    gs = app.current
    assert isinstance(gs, GameScreen)
    ui.tap(app, *ui.root_point(app, gs.piles_btn))
    seg = ui.find(gs.overlay, lambda v: isinstance(v, ui.SegmentedControl))[0]
    assert seg.segments == ["Discard 0", "Tavern %d" % len(app.game.tavern)]
    assert "The discard pile is empty." in _texts(gs.overlay)


def test_choice_boxes_offer_hold_to_view_the_game(app):
    import json
    from app.screens import ClassChoiceOverlay, GameMenuOverlay, LogOverlay, MagePeekOverlay, PilesOverlay
    from helpers import set_hand, set_mission_enemy, set_tavern_top
    gs, g = _piles_game(app)
    set_mission_enemy(g, "LABJD", hp=100)
    set_hand(g, ["3M", "9S", "8S"])
    set_tavern_top(g, ["4C", "10H", "2D"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3M"])
    _tap(app, "Play")
    ov = gs.overlay
    assert isinstance(ov, MagePeekOverlay) and isinstance(ov.peek_btn, widgets.PeekButton)
    menu = ui.button(ov, "Game menu")
    # beside the Game menu button, on the same row: the box is no taller for it
    assert ov.peek_btn.y == menu.y and ov.peek_btn.x > menu.x and abs(ov.peek_btn.width - menu.width) < 1
    before = json.dumps(g.to_dict(), sort_keys=True)
    shown = [v for v in ov.panel.subviews if not v.hidden]
    ov.peek_btn.touch_began(None)                  # held: the box fades, the table shows
    assert ov.peeking and ov.peek_btn.held and ov.background_color[3] == 0 and ov.panel.background_color is None
    assert [v for v in ov.panel.subviews if not v.hidden] == [ov.peek_btn]
    assert ui.render(app).size[0] > 0
    ov.peek_btn.touch_ended(None)                  # released: the same box again
    assert not ov.peeking and [v for v in ov.panel.subviews if not v.hidden] == shown
    assert ov.background_color[3] > 0.5 and gs.overlay is ov
    assert json.dumps(g.to_dict(), sort_keys=True) == before and g.decision["kind"] == "mage_peek"
    # a hold the phone cancels: any tap brings the box back
    ov.peek_btn.touch_began(None)
    ov.touch_ended(None)
    assert not ov.peeking and not ov.peek_btn.held and ui.button(ov, "Game menu")
    # a rebuild while held brings it back too
    ov.peek_btn.touch_began(None)
    ov.layout()
    assert not ov.peeking and all(not v.hidden for v in ov.panel.subviews)
    # the choice still works
    _tap(app, "Add 4♣ to the attack")
    assert g.decision is None or g.decision["kind"] != "mage_peek"
    # a choice box without a Game menu button gets its own row; menus and information do not
    gs._show_overlay(ClassChoiceOverlay(gs))
    assert gs.overlay.peek_btn is not None and gs.overlay.peek_btn.width > ui.button(gs.overlay, "Cancel").width * 0.9
    for cls in (GameMenuOverlay, LogOverlay, PilesOverlay):
        gs._show_overlay(cls(gs))
        assert gs.overlay.peek_btn is None and not ui.find(gs.overlay, lambda v: isinstance(v, widgets.PeekButton))
