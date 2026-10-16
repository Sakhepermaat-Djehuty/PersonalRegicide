"""The lab table, part two: the castle view, the piles after real plays, the status line,
the card backs, the decision captions (and the table under a handover box), the Jester
power's cue, the header under a claimed Jester, clash warnings, the header's projection
notes, the attack's card, the Kinfolk Flute's greying, a Chanter-sized hand and the piles
viewer's notes. What happened lives in the game log; the table shows piles, the header and
one caption line for a decision made with the hand."""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402

from regicide.campaign import CampaignState  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402
from regicide.engine import PHASE_DECIDE, PHASE_PLAY, PHASE_SUFFER, Play  # noqa: E402
from regicide.rules import GameConfig  # noqa: E402
from helpers import (_pull, set_discard, set_enemy, set_hand, set_mission_enemy,  # noqa: E402
                     set_tavern_top)

LONG_NAMES = ("Maximilian Ash", "Christopher Ab")     # 14 characters each


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app import widgets
    from app.screens import App, MenuScreen
    ui.set_screen_size(390, 844)
    monkeypatch.setattr(widgets, "BACK_STYLE", widgets.BACK_STYLE)    # put back after a card-backs test
    a = App()
    a.settings["rules_card"] = False
    a.show(MenuScreen(a))
    yield a
    ui.set_screen_size(390, 844)


# ---------------------------------------------------------------------------- helpers
def _texts(view):
    return [v.text for v in ui.find(view, lambda v: isinstance(v, ui.Label))]


def _resize(app, w, h):
    """A phone of another size (the App and its screen follow)."""
    ui.set_screen_size(w, h)
    app.frame = (0, 0, w, h)
    app.layout()


def _tap_button(app, title):
    """Tap a visible button by title ("Discard" also finds "Discard 8/10")."""
    try:
        b = ui.button(app, title)
    except KeyError:
        b = [v for v in ui.find(app, lambda v: isinstance(v, ui.Button) and not v.hidden
                                and re.match(re.escape(title) + r" \d+/\d+$", v.title or ""))][0]
    assert b.enabled, "button %s disabled" % title
    ui.tap(app, *ui.root_point(app, b))


def _tap_card(app, gs, card_id):
    ui.tap(app, *ui.root_point(app, gs.hand.views[card_id]))


def _shown(gs):
    """The caption as the player sees it ("" while it is hidden)."""
    return "" if gs.message.hidden else gs.message.text


def _drawn_text(view):
    """The strings a view draws."""
    calls = []
    real = ui.draw_string

    def spy(text, rect=(0, 0, 0, 0), font=None, *a, **k):
        calls.append(str(text))
    ui.draw_string = spy
    try:
        ui.render(view)
    finally:
        ui.draw_string = real
    return calls


def _popup(gs):
    from app.screens import CardPopup
    pops = [v for v in gs.subviews if isinstance(v, CardPopup)]
    assert pops
    return pops[-1]


def _open_attack(app, gs):
    """Tap left of the enemy's card in the header: the attack's card."""
    ui.tap(app, gs.enemy.x + 10, ui.root_point(app, gs.enemy)[1])
    return _popup(gs)


def _open_enemy(app, gs):
    """Tap the enemy's card in the header."""
    ui.tap(app, *ui.root_point(app, gs.enemy))
    return _popup(gs)


def _new_campaign(app, names, seed=4242):
    """A new campaign whose attempts deal the same cards every run."""
    app.new_campaign(len(names), list(names))
    app.campaign.seed = seed
    return app.campaign


def _flute_mission(app, number=5):
    """A solo Legacy mission with the Kinfolk Flute."""
    _new_campaign(app, ["Solo"])
    camp = app.campaign
    camp.mission, camp.completed = number, list(range(1, number))
    camp.relics.append("flute")
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


def _mission_attempt(app, number, names=("Solo",), relics=(), beast=None, guardians=False):
    """A Legacy mission attempt with the party it would have (Gøran from 5, Myla from 6)."""
    _new_campaign(app, names)
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
    for d in list(M.MAGE_DECK) + (list(M.GUARDIANS) if guardians else []):
        if P.find(camp.party, str(d["id"])) is None:
            P.add_card(camp.party, dict(d))
    app.save_campaign()
    app.start_attempt()
    return app.current, app.game


def _late_mission_attempt(app, number, names=("Solo",), guardians=False, seed=4242):
    """Missions 10 to 12, with the party those missions are played with."""
    camp = _new_campaign(app, names, seed)
    camp.mission = number
    camp.completed = list(range(1, number))
    camp.flags["beasts"] = True
    camp.set_beast("B_H")
    for d in list(M.MAGE_DECK) + (list(M.GUARDIANS) if guardians else []):
        if P.find(camp.party, str(d["id"])) is None:
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
    return app.current, app.game


def _evergreen_attempt(app, location, players=1, names=("Ana", "Ben", "Cy"), banes=(), boons=()):
    """An Evergreen attempt (pack E) with a finished campaign's party."""
    from app import store
    c = CampaignState.new(players, list(names[:players]), seed=5000)
    c.mission, c.completed, c.finished = 12, list(range(1, 13)), True
    c.relics.append("mother_restored")
    c.flags["beasts"] = True
    c.set_beast("B_H")
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    P.add_card(c.party, dict(M.ASH))
    P.add_card(c.party, dict(M.ESME_REBORN))
    for cid in ("2S", "3H", "4D", "5C", "7S", "8H", "9D", "ESME6E"):
        P.add_flag(c.party, cid, "restored")
    c.evergreen["setup"] = {"location": location, "banes": sorted(banes), "boons": sorted(boons)}
    c.slot = store.new_slot_id("Evergreen")
    app.campaign = c
    app.start_evergreen_attempt()
    return app.current, app.game


# ---------------------------------------------------------------------------- 1. the castle view
def test_the_base_games_castle_is_the_twelve_royals(app):
    from app.screens import enemy_deck
    app.start_game(GameConfig(players=1), seed=4)
    g = app.game
    deck = enemy_deck(g)
    assert [g.card(c).rank for c in deck] == ["J"] * 4 + ["Q"] * 4 + ["K"] * 4
    assert set(deck) == set(g.castle) | {g.enemy.card_id} and len(set(deck)) == 12


def test_a_legacy_missions_castle_view_shows_its_enemy_deck_and_greys_nothing_at_the_start(app):
    from app.screens import PilesOverlay, enemy_deck
    gs, g = _flute_mission(app, 4)                     # the lab's experiments
    setup = set(str(e["id"]) for e in g.config.extra["castle"])
    deck = enemy_deck(g)
    assert set(deck) == setup == set(g.castle) | {g.enemy.card_id}
    ui.tap(app, *ui.root_point(app, gs.pile_views["castle"]))
    ov = gs.overlay
    assert isinstance(ov, PilesOverlay) and ov.pile == "castle"
    assert sorted(ov.card_views) == sorted(deck)
    assert not any(v.shaded for v in ov.card_views.values())
    assert [c for c, v in ov.card_views.items() if v.badge == "now"] == [g.enemy.card_id]


def test_the_evergreen_forests_banished_experiments_stay_out_of_the_castle(app):
    from app.screens import PilesOverlay, enemy_deck
    gs, g = _evergreen_attempt(app, "C")
    experiments = [c for c in g.banished if g.card(c).health > 0]
    assert len(experiments) == 4                       # the Forest's Phase I experiments, banished
    deck = enemy_deck(g)
    assert not set(experiments) & set(deck)
    assert set(deck) == set(g.castle) | {g.enemy.card_id}
    ui.tap(app, *ui.root_point(app, gs.pile_views["castle"]))
    ov = gs.overlay
    assert isinstance(ov, PilesOverlay) and ov.pile == "castle"
    assert sorted(ov.card_views) == sorted(deck)
    assert not any(v.shaded for v in ov.card_views.values())      # nothing defeated yet
    assert "%d enemies left after this one" % len(g.castle) in " ".join(_texts(ov))


def test_after_a_kill_the_castle_greys_the_defeated_and_marks_the_enemy_faced(app):
    from app.screens import PilesOverlay, enemy_deck
    app.start_game(GameConfig(players=1), seed=4)
    gs, g = app.current, app.game
    first, deck = g.enemy.card_id, enemy_deck(g)
    g.enemy.hp = 3
    set_hand(g, ["5S", "9D", "8C", "7H"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["5S"])
    _tap_button(app, "Play")
    assert g.enemies_defeated == 1 and g.enemy.card_id != first
    assert gs.pile_views["castle"].count == len(g.castle) == 10
    ui.tap(app, *ui.root_point(app, gs.pile_views["castle"]))
    ov = gs.overlay
    assert isinstance(ov, PilesOverlay) and ov.pile == "castle" and sorted(ov.card_views) == sorted(deck)
    assert [c for c, v in ov.card_views.items() if v.shaded] == [first]
    assert [c for c, v in ov.card_views.items() if v.badge == "now"] == [g.enemy.card_id]
    assert [c for c, v in ov.card_views.items() if v.selected] == [g.enemy.card_id]
    assert "10 enemies left after this one; the defeated are greyed." in _texts(ov)


def test_mission10s_castle_pile_lies_face_up_with_the_next_enemy_on_top(app):
    gs, g = _late_mission_attempt(app, 10)
    gs.refresh(after_action=False)
    pv = gs.pile_views["castle"]
    assert g.castle and pv.count == len(g.castle)
    assert pv.top_view is not None and pv.top_view.card.id == g.castle[0]
    assert pv.badge_view is not None and pv.badge_view.count == len(g.castle)
    # another mission's castle lies face down: no card shows
    gs, g = _late_mission_attempt(app, 9)
    gs.refresh(after_action=False)
    assert gs.pile_views["castle"].count == len(g.castle) and gs.pile_views["castle"].top_view is None


# ---------------------------------------------------------------------------- 2. the piles on the table
def _assert_piles_match(gs, g):
    v = gs.pile_views
    assert v["castle"].count == len(g.castle) and v["castle"].top_view is None
    assert v["reserve"].count == len(g.tavern) and v["reserve"].top is None and v["reserve"].top_view is None
    assert v["discard"].count == len(g.discard)
    if g.discard:
        assert v["discard"].top_view.card.id == g.discard[0] and v["discard"].badge_view.count == len(g.discard)
    else:
        assert v["discard"].top_view is None and v["discard"].badge_view is None
    assert v["banished"].count == len(g.banished)
    if g.banished:
        assert v["banished"].top_view.card.id == g.banished[-1] and v["banished"].badge_view.count == len(g.banished)


def test_pile_counts_and_top_cards_follow_real_plays(app):
    app.start_game(GameConfig(players=1), seed=4)
    gs, g = app.current, app.game
    _assert_piles_match(gs, g)
    assert gs.pile_views["discard"].layers() == 0 and gs.pile_views["banished"].hidden
    set_hand(g, ["5C", "8D", "9S", "2H", "3H"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["5C"])
    _tap_button(app, "Play")
    assert g.phase == PHASE_SUFFER
    gs.hand.set_selection(["9S", "2H"])
    _tap_button(app, "Discard")
    assert g.phase == PHASE_PLAY and g.discard
    _assert_piles_match(gs, g)
    assert gs.pile_views["discard"].count == len(g.discard) >= 2


def test_hearts_that_empty_the_discard_pile_leave_its_outline(app):
    from app import widgets
    app.start_game(GameConfig(players=1), seed=4)
    gs, g = app.current, app.game
    set_discard(g, ["7C", "4D"])
    set_hand(g, ["5H", "9S", "8S", "7S"])
    gs.refresh(after_action=False)
    assert gs.pile_views["discard"].count == 2 and gs.pile_views["discard"].top_view.card.id == "7C"
    gs.hand.set_selection(["5H"])
    _tap_button(app, "Play")
    pv = gs.pile_views["discard"]
    assert g.discard == [] and pv.count == 0 and pv.top_view is None and pv.badge_view is None
    backs = []
    real_back = widgets.draw_back
    widgets.draw_back = lambda *a, **k: backs.append(a)
    try:
        drawn = _drawn_text(pv)
    finally:
        widgets.draw_back = real_back
    assert drawn == ["0", "Discard"] and backs == []       # an outline with a 0, no card


def test_the_banished_pile_comes_onto_the_base_games_table_once_a_card_is_banished(app):
    app.start_game(GameConfig(players=1), seed=4)
    gs, g = app.current, app.game
    assert gs.pile_views["banished"].hidden
    xs = [gs.pile_views[k].x for k in ("castle", "reserve", "discard")]
    g.banished.append(g.tavern.pop(0))
    gs.refresh(after_action=False)
    v = gs.pile_views
    assert not v["banished"].hidden
    assert [v[k].x for k in ("castle", "reserve", "discard")] != xs          # the others make room
    assert v["discard"].x + v["discard"].width <= v["banished"].x + 0.5
    assert v["banished"].x + v["banished"].width <= gs.width
    g.banished.append(g.tavern.pop(0))
    gs.refresh(after_action=False)
    _assert_piles_match(gs, g)


@pytest.mark.parametrize("size", [(390, 844), (375, 667), (320, 568)])
def test_a_piles_count_badge_stays_on_the_pile_above_its_name(app, size):
    _resize(app, *size)
    gs, g = _flute_mission(app, 4)
    g.discard[:0] = g.tavern[:12]                      # two-digit counts: the widest badge
    del g.tavern[:12]
    g.banished.extend(g.tavern[:1])
    del g.tavern[:1]
    gs.refresh(after_action=False)
    for key in ("discard", "banished"):
        pile = gs.pile_views[key]
        badge = pile.badge_view
        assert badge is not None and badge.count == pile.count and badge.superview is pile
        assert badge.y >= 0 and badge.y + badge.height <= pile.height - pile.LABEL_H + 0.01
        assert badge.x >= 0 and badge.x + badge.width <= pile.width + 0.01
        assert badge.width >= 24                       # big enough to read
    assert ui.render(app).size[0] > 0


# ---------------------------------------------------------------------------- 3. the status line
def test_the_solo_status_line_counts_the_turn_and_the_jesters_left(app):
    from app.screens import status_text
    app.start_game(GameConfig(players=1), seed=6)
    gs, g = app.current, app.game
    assert gs.status.text == "Turn 1 · Jesters 2" == "Turn %d · Jesters %d" % (g.turn, g.solo_jesters)
    g.solo_jesters = 1
    gs.refresh(after_action=False)
    assert gs.status.text == "Turn 1 · Jesters 1"
    assert status_text(g, 30) == "Jesters 1"            # too narrow for both: the Jesters stay


def test_the_pass_and_play_status_line_names_whose_turn_it_is(app):
    from app.screens import status_text
    app.start_game(GameConfig(players=2, names=("Ana", "Ben"), open_hands=True), seed=6)
    gs, g = app.current, app.game
    assert gs.status.text == "Turn 1 · Ana" and "Jesters" not in gs.status.text
    _tap_button(app, "Yield")
    assert g.phase == PHASE_SUFFER
    _tap_button(app, "Suggest")
    ui.tap(app, *ui.root_point(app, gs.right_btn))
    assert g.active == 1 and g.turn == 2 and gs.status.text == "Turn 2 · Ben"
    assert status_text(g, 30) == "Ben"                  # too narrow for both: the player stays


def test_a_long_name_on_a_small_phone_keeps_the_name_in_the_status_line(app):
    from app.widgets import text_size
    _resize(app, 320, 568)
    name = "Bartholomew Montgomery"
    app.start_game(GameConfig(players=2, names=(name, "Ben"), open_hands=True), seed=6)
    gs = app.current
    assert text_size("Turn 1 · " + name, 0, 13)[0] > gs.status.width >= text_size(name, 0, 13)[0]
    assert gs.status.text == name and not ui.label_truncated(gs.status)


# ---------------------------------------------------------------------------- 4. the card backs
def test_the_card_back_setting_picks_the_style_and_an_unknown_one_falls_back_to_the_lattice(app):
    from app import backs, widgets
    from app.screens import apply_face_style
    for style in backs.ORDER:
        apply_face_style({"card_back": style})
        assert widgets.BACK_STYLE == style
    apply_face_style({"card_back": "no such style"})
    assert widgets.BACK_STYLE == "lattice"
    apply_face_style({})
    assert widgets.BACK_STYLE == "lattice"


def test_draw_back_draws_the_chosen_style(app, monkeypatch):
    from app import backs, widgets
    calls = []
    for name in backs.ORDER:
        monkeypatch.setitem(backs.STYLES, name, (lambda n: lambda *a: calls.append((n,) + a))(name))
    for name in backs.ORDER:
        monkeypatch.setattr(widgets, "BACK_STYLE", name)
        widgets.draw_back(1, 2, 30, 40, 7)
        widgets.draw_back(1, 2, 30, 40, plain=True)
    assert calls == [c for n in backs.ORDER for c in ((n, 1, 2, 30, 40, 7, False), (n, 1, 2, 30, 40, None, True))]


def _back_button(app):
    return [v for v in ui.find(app, lambda v: isinstance(v, ui.Button) and (v.title or "").endswith(" ›"))][0]


def test_the_settings_button_cycles_the_card_backs_saves_them_and_the_table_draws_them(app, monkeypatch):
    from app import backs, store, widgets
    from app.screens import SettingsScreen
    from app.widgets import BackSample, CardView
    app.show(SettingsScreen(app))
    assert _back_button(app).title == "Lattice ›" and ui.find(app, lambda v: isinstance(v, BackSample))
    seen = []
    for _ in range(len(backs.ORDER)):
        b = _back_button(app)
        seen.append(b.title)
        ui.tap(app, *ui.root_point(app, b))
        assert widgets.BACK_STYLE == app.settings["card_back"] == store.load_settings()["card_back"]
    assert seen == ["Lattice ›", "Crowns ›", "Sunburst ›", "Flat ›"]
    assert app.settings["card_back"] == "lattice" and _back_button(app).title == "Lattice ›"
    for _ in range(3):
        ui.tap(app, *ui.root_point(app, _back_button(app)))
    assert widgets.BACK_STYLE == "flat"
    # the table's face-down piles and cards use it
    used = []
    monkeypatch.setitem(backs.STYLES, "flat", lambda *a: used.append(a))
    app.start_game(GameConfig(players=1), seed=6)
    ui.render(app.current.pile_views["reserve"])
    assert used and used[-1][4] == len(app.game.tavern)        # the count on the top card's back
    v = CardView(app.game.card("5C"), frame=(0, 0, 60, 86))
    v.face_up = False
    used.clear()
    ui.render(v)
    assert used == [(0, 0, 60, 86, None, False)]


def test_an_unknown_stored_card_back_shows_as_lattice_and_moves_on_to_crowns(app):
    from app import store, widgets
    from app.screens import App, MenuScreen, SettingsScreen
    app.settings["card_back"] = "velvet"                 # a style from another build
    app.save_settings()
    a = App()                                            # a fresh start reads it
    a.show(MenuScreen(a))
    assert widgets.BACK_STYLE == "lattice"
    a.show(SettingsScreen(a))
    assert _back_button(a).title == "Lattice ›"
    ui.tap(a, *ui.root_point(a, _back_button(a)))
    assert a.settings["card_back"] == "crowns" == store.load_settings()["card_back"]
    assert widgets.BACK_STYLE == "crowns" and _back_button(a).title == "Crowns ›"


# ---------------------------------------------------------------------------- 5. the captions
# Each flow plays to a decision made with a hand in a two-player game with hidden hands
# and shows that hand ("Show my hand"); it returns the screen, the game and the decision.
def _cap_flute(app, names):
    _new_campaign(app, names)
    app.campaign.relics.append("flute")
    app.start_attempt()
    gs, g = app.current, app.game
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3D", "3H", "7C", "AS"], player=1)
    gs.reveal_hand()
    gs.hand.set_selection(["3C"])
    _tap_button(app, "Play")
    return gs, g


def _cap_emblem(app, names):
    _new_campaign(app, names)
    for d in M.MAGE_DECK:
        P.add_card(app.campaign.party, dict(d))
    app.campaign.relics.append("emblem")
    app.start_attempt()
    gs, g = app.current, app.game
    set_enemy(g, "J", "H")
    set_hand(g, ["5M", "9S", "8S"], player=0)
    set_hand(g, ["7C", "3D", "AS"], player=1)
    set_tavern_top(g, ["6C", "4H", "3S", "2S", "2D"])
    gs.reveal_hand()
    gs.hand.set_selection(["5M"])
    _tap_button(app, "Play")
    return gs, g


def _cap_whistle(app, names):
    gs, g = _mission_attempt(app, 5, names=names, relics=("whistle",), beast="B_H")
    set_mission_enemy(g, "GRJH", hp=100)
    set_hand(g, ["AS", "9S", "8S"], player=0)
    set_hand(g, ["7C", "3D", "2D"], player=1)
    gs.reveal_hand()
    gs.hand.set_selection(["AS"])
    _tap_button(app, "Play")
    return gs, g


def _cap_chanter(app, names):
    gs, g = _mission_attempt(app, 8, names=names)
    set_mission_enemy(g, "HEJ6", hp=100)
    set_hand(g, ["3T", "9S"], player=0)
    set_hand(g, ["2C", "3C", "4C", "5C", "6C", "7C"], player=1)
    set_tavern_top(g, ["AH", "2H", "3H", "4H", "5H", "6H", "7H", "8H"])
    gs.reveal_hand()
    gs.hand.set_selection(["3T"])
    _tap_button(app, "Play")
    _tap_button(app, "3")                              # everyone draws 3: the second player is over 7
    return gs, g


def _cap_mother(app, names):
    _new_campaign(app, names)
    app.campaign.relics.append("mother")
    P.add_flag(app.campaign.party, "7D", "corrupted")
    app.save_campaign()
    app.start_attempt()
    gs, g = app.current, app.game
    set_enemy(g, "J", "H")
    set_hand(g, ["7D", "9S"], player=0)
    set_hand(g, ["5C", "2C"], player=1)
    gs.reveal_hand()
    gs.hand.set_selection(["7D"])
    _tap_button(app, "Play")
    return gs, g


def _cap_team(app, names):
    gs, g = _mission_attempt(app, 6, names=names)
    set_mission_enemy(g, "GDQH", hp=9)
    set_hand(g, ["9S", "8D", "AD"], player=0)
    set_hand(g, ["3H", "4D", "7S", "2C"], player=1)
    gs.reveal_hand()
    gs.hand.set_selection(["9S"])
    _tap_button(app, "Play")
    _tap_button(app, "Move 9♠ to the mission zone")
    _tap_button(app, "Rescue 9♠ to the discard pile")
    _tap_button(app, "%s (4 cards)" % names[1])        # the seat picker: the second player discards
    return gs, g


def _cap_rescue(app, names):
    from app.screens import PileRescueOverlay
    gs, g = _mission_attempt(app, 9, names=names)
    set_mission_enemy(g, "TTQH")
    set_hand(g, ["9S", "4C", "3C", "5D", "6D"], player=0)
    gs.reveal_hand()
    gs.hand.set_selection(["9S"])
    _tap_button(app, "Play")
    gs.hand.set_selection(["4C", "3C"])
    _tap_button(app, "Discard")
    assert isinstance(gs.overlay, PileRescueOverlay)
    b = [v for v in ui.find(gs.overlay, lambda v: isinstance(v, ui.Button) and v.title.startswith("Rescue"))][1]
    ui.tap(app, *ui.root_point(app, b))
    return gs, g


def _cap_zone_feed(app, names):
    gs, g = _late_mission_attempt(app, 10, names=names)
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    for play in g.plays:
        g.discard.extend(play.card_ids)
    set_mission_enemy(g, "4D", hp=100)                 # mission 10's bard: a hand card into the zone
    g.mission_zone[:] = []
    set_hand(g, ["AS", "9S", "8S", "2C"], player=0)
    g.active = 0
    gs.shown_player = None
    gs.reveal_hand()
    gs.hand.set_selection(["AS"])
    _tap_button(app, "Play")
    gs.hand.set_selection(["9S"])
    _tap_button(app, "Discard")
    return gs, g


def _cap_beast(app, names):
    gs, g = _late_mission_attempt(app, 11, names=names)
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    for play in g.plays:
        g.discard.extend(play.card_ids)
    g.plays = []
    set_mission_enemy(g, "CV_J1", hp=100)
    g.extra["beast_deck"] = ["B_H"] + [x for x in g.extra["beast_deck"] if x != "B_H"]
    g.extra["beasts_out"] = [x for x in g.extra["beasts_out"] if x != "B_H"]
    g.active = 0
    set_hand(g, ["AS", "9S", "8S"], player=0)
    set_hand(g, ["2C", "6D"], player=1)
    g.tavern.extend(g.discard + g.banished)          # the top discard and banished cards feed the enemy
    g.discard, g.banished = [], []
    gs.shown_player = None
    gs.reveal_hand()
    gs.hand.set_selection(["AS"])
    _tap_button(app, "Play")
    gs.hand.set_selection(["8S", "9S"])
    _tap_button(app, "Discard")                        # the next player's turn: a cleric beast
    return gs, g


CAPTION_FLOWS = {"flute_add": _cap_flute, "emblem_place": _cap_emblem, "whistle_add": _cap_whistle,
                 "chanter_discard": _cap_chanter, "mother_banish": _cap_mother, "team_discard": _cap_team,
                 "pile_rescue": _cap_rescue, "zone_feed": _cap_zone_feed, "beast_discard": _cap_beast}

# what each caption is about, whatever form fits
CAPTION_TOPIC = {"flute_add": "Kinfolk Flute", "emblem_place": "Azure Emblem", "whistle_add": "Scarlet Whistle",
                 "chanter_discard": "Chanter", "mother_banish": "Evergreen Mother", "team_discard": "Team damage",
                 "pile_rescue": "Rescue", "zone_feed": "mission zone", "beast_discard": "Cleric beast"}


def _show_hand(app, gs):
    if gs.overlay is not None and ui.find(gs.overlay, lambda v: isinstance(v, ui.Button) and v.title == "Show my hand"):
        _tap_button(app, "Show my hand")


@pytest.mark.parametrize("size", [(375, 667), (320, 568)])
@pytest.mark.parametrize("kind", sorted(CAPTION_FLOWS))
def test_a_decision_made_with_the_hand_names_itself_in_a_caption_that_is_never_cut(app, kind, size):
    from app import theme as T
    from app.widgets import text_size
    for names in (("Ana", "Ben"), LONG_NAMES):
        _resize(app, *size)
        gs, g = CAPTION_FLOWS[kind](app, names)
        _show_hand(app, gs)
        assert g.phase == PHASE_DECIDE and g.decision["kind"] == kind and gs.overlay is None and gs.hand.cards
        who = g.players[gs.shown_player].name            # whose hand it is (the team damage's chosen seat)
        caption, m = _shown(gs), gs.message
        assert CAPTION_TOPIC[kind] in caption, (names, caption)
        assert not ui.label_truncated(m), (size, names, ui.label_lines(m))
        assert m.width <= size[0] - 2 * T.MARGIN + 0.5 and gs.hand.y >= m.y + m.height    # the hand starts under it
        if names == ("Ana", "Ben"):
            # short names: one line; on a 375-pt phone it names whose hand decides (the
            # rescue is the active player's own)
            assert m.number_of_lines == 1, caption
            assert size[0] < 375 or kind == "pile_rescue" or who in caption, caption
        elif m.number_of_lines != 1:
            # long names: a shorter form when the long one does not fit; two whole lines only
            # when even the shortest is wider than the room at the smallest size
            assert text_size(caption, 0, 11, True)[0] > m.width and m.height >= 36, caption


def test_the_caption_comes_with_the_decision_and_goes_while_playing_and_suffering(app):
    gs, g = _cap_flute(app, ("Ana", "Ben"))
    _show_hand(app, gs)
    assert g.decision["kind"] == "flute_add" and _shown(gs) == "Kinfolk Flute: Ben may add to Ana's 3♣"
    y_with = gs.hand.y
    _tap_button(app, "Pass")
    assert _shown(gs) == ""                              # under the handover box: nothing
    _show_hand(app, gs)
    assert g.phase == PHASE_SUFFER and g.active == 0 and gs.overlay is None
    assert gs.message.hidden and gs.hand.y < y_with      # suffering: no caption, the hand takes the room
    _tap_button(app, "Suggest")
    _tap_button(app, "Discard")
    _show_hand(app, gs)
    assert g.phase == PHASE_PLAY and g.active == 1 and gs.overlay is None
    gs.hand.set_selection([gs.hand.cards[0].id])
    assert gs.message.hidden and _shown(gs) == ""        # playing: none either


def test_under_a_handover_box_the_action_buttons_lose_the_tally_picked_before(app):
    from app.screens import HandoverOverlay, TeamDamageOverlay
    tally = re.compile(r"\d+/\d+$")
    gs, g = _cap_team(app, ("Ana", "Ben"))
    _show_hand(app, gs)
    _tap_card(app, gs, "3H")
    assert gs.right_btn.title == "Discard 3/7"
    _tap_button(app, "Players")                          # back to the seat picker: the phone may pass
    assert isinstance(gs.overlay, TeamDamageOverlay) and gs.hand.cards == []
    bar = (gs.left_btn, gs.mid_btn, gs.right_btn)
    assert not any(tally.search(b.title or "") for b in bar) and not any(b.enabled for b in bar)
    assert gs.right_btn.title == "Discard" and gs.message.hidden
    # a suffer step paid in pass and play: the next player does not see what was picked
    app.start_game(GameConfig(players=2, names=("Ana", "Ben")), seed=6)
    gs, g = app.current, app.game
    _show_hand(app, gs)
    _tap_button(app, "Yield")
    assert g.phase == PHASE_SUFFER
    _tap_button(app, "Suggest")
    paid = gs.right_btn.title
    assert tally.search(paid)
    _tap_button(app, "Discard")
    assert isinstance(gs.overlay, HandoverOverlay) and g.active == 1
    assert not any(tally.search(b.title or "") for b in (gs.left_btn, gs.mid_btn, gs.right_btn)), paid


# ---------------------------------------------------------------------------- 6. the Jester power's cue
def test_the_jester_power_lights_up_when_the_hand_cannot_pay(app):
    from app import theme as T
    app.start_game(GameConfig(players=1), seed=5)
    gs, g = app.current, app.game
    set_enemy(g, "K", "S")
    set_hand(g, ["2C", "3D", "4H", "10S", "9S", "8C"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["2C"])
    _tap_button(app, "Play")
    assert g.phase == PHASE_SUFFER and g.rules.solo_jester_mode(g) == "refresh"
    assert g.hand_defence_value() >= g.pending_damage
    assert not gs.mid_btn.hidden and gs.mid_btn.enabled and gs.mid_btn.background_color == T.PANEL_2
    set_hand(g, ["2D", "3H"])                             # 5 cannot pay 20
    gs.refresh(after_action=False)
    assert g.hand_defence_value() < g.pending_damage
    assert gs.mid_btn.enabled and gs.mid_btn.background_color == T.BTN            # lit: the way out
    _tap_button(app, "Suggest")
    assert not gs.right_btn.enabled                       # nothing the hand holds pays it
    g.solo_jesters = 0
    gs.refresh(after_action=False)
    assert not gs.mid_btn.enabled and gs.mid_btn.background_color == T.BTN_DISABLED
    # the cue is for the suffer step only: while playing the Jester stays a plain button
    app.start_game(GameConfig(players=1), seed=5)
    gs, g = app.current, app.game
    set_hand(g, ["2D"])
    gs.refresh(after_action=False)
    assert g.phase == PHASE_PLAY and gs.mid_btn.enabled and gs.mid_btn.background_color == T.PANEL_2


# ---------------------------------------------------------------------------- 7. the header under a claimed Jester
def _claimed_jester_game(app):
    """Three players, the first about to play a Jester against the Paladin Justicar (immune
    to Paladins); the second has 5♥ 5♦ 7♠. Returns the screen, the game and the Jester."""
    _new_campaign(app, ["Ana", "Ben", "Cy"])
    app.start_attempt()
    gs, g = app.current, app.game
    sj = [c for c in [g.enemy.card_id] + list(g.castle) if g.card(c).suits == ("S",) and g.card(c).rank == "J"][0]
    set_mission_enemy(g, sj)
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_hand(g, [jester, "2H"], 0)
    set_hand(g, ["5H", "5D", "7S"], 1)
    set_hand(g, ["6C", "2D"], 2)
    gs.reveal_hand()
    return gs, g, jester


def test_a_claimed_jester_attack_drops_the_enemys_immunity_icons_and_its_card_says_so(app):
    gs, g, jester = _claimed_jester_game(app)
    assert gs.enemy.card_view.center_icons == ["S"]
    gs.hand.set_selection([jester])
    _tap_button(app, "Play")
    _tap_button(app, "Ben (3 cards)")                     # Ben claims it: his attack ignores immunity
    _show_hand(app, gs)
    assert g.extra.get("jester_attack") and not g.immunity_cancelled and g.active == 1
    assert gs.enemy.card_view.center_icons == []
    gs.hand.set_selection(["7S"])
    assert not gs.enemy.warn and not gs.hand.warned and "shield +7" in gs.forecast
    text = " ".join(_texts(_open_enemy(app, gs)))
    assert "This attack ignores immunity" in text and "Immune to" not in text


def test_mylas_fixed_immunity_keeps_its_icons_under_a_claimed_jester(app):
    _new_campaign(app, ["Ana", "Ben", "Cy"])
    camp = app.campaign
    camp.mission, camp.completed = 9, list(range(1, 9))
    P.add_card(camp.party, dict(M.GORAN))
    camp.flags["beasts"] = True
    camp.set_beast("B_H")
    for d in M.MAGE_DECK:
        P.add_card(camp.party, dict(d))
    app.save_campaign()
    app.start_attempt()
    gs, g = app.current, app.game
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    set_mission_enemy(g, "MYLA_BOSS")
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_hand(g, [jester, "2C"], 0)
    set_hand(g, ["AD", "9S", "3H"], 1)
    set_hand(g, ["6C", "2D"], 2)
    g.active, gs.shown_player = 0, None
    gs.reveal_hand()
    assert gs.enemy.card_view.center_icons == ["D", "S"]
    gs.hand.set_selection([jester])
    _tap_button(app, "Play")
    _tap_button(app, "Ben (3 cards)")
    _show_hand(app, gs)
    assert g.extra.get("jester_attack") and g.active == 1
    assert gs.enemy.card_view.center_icons == ["D", "S"]           # nothing ignores Myla's immunity
    gs.hand.set_selection(["9S"])
    assert gs.enemy.warn and gs.hand.warned == {"9S"} and gs.hand.views["9S"].warn
    text = " ".join(_texts(_open_enemy(app, gs)))
    assert "This attack ignores immunity" in text and "but not to" in text and "Paladin" in text


# ---------------------------------------------------------------------------- 8. clash warnings
def test_a_clash_is_found_by_the_classes_a_card_has_in_play(app):
    # Evergreen boon 28: the puppy has no class in hand but all four while played, so
    # against an enemy immune to Clerics its cleric power clashes
    gs, g = _evergreen_attempt(app, "A", boons=[28])
    assert g.card("PILA").suits == () and "H" in g.rules.card_suits(g, g.card("PILA"))
    for play in g.plays:
        g.discard.extend(play.card_ids)
    g.plays = []
    set_mission_enemy(g, "LABQH", hp=100)
    set_hand(g, ["PILA", "9S", "8S", "5C"])
    gs.refresh(after_action=False)
    assert gs.enemy.card_view.center_icons == ["H"]
    gs.hand.set_selection(["PILA"])
    assert gs.hand.warned == {"PILA"} and gs.hand.views["PILA"].warn and gs.enemy.warn
    gs.hand.set_selection(["5C"])
    assert not gs.hand.warned and not gs.enemy.warn and not gs.hand.views["PILA"].warn


def test_the_kinfolk_flute_decision_warns_of_a_clash_too(app):
    _new_campaign(app, ["Ana", "Ben"])
    app.campaign.relics.append("flute")
    app.start_attempt()
    gs, g = app.current, app.game
    set_enemy(g, "J", "S")
    set_hand(g, ["3C", "9H", "8H"], player=0)
    set_hand(g, ["3S", "3H", "7C", "AD"], player=1)
    gs.reveal_hand()
    gs.hand.set_selection(["3C"])
    _tap_button(app, "Play")
    _show_hand(app, gs)
    assert g.decision["kind"] == "flute_add" and g.deciding == 1 and not gs.enemy.warn
    _tap_card(app, gs, "3S")                              # a paladin added against a paladin enemy
    assert gs.hand.selected == ["3S"] and gs.right_btn.enabled
    assert gs.hand.warned == {"3S"} and gs.hand.views["3S"].warn and gs.enemy.warn and gs.enemy.card_view.warn
    _tap_card(app, gs, "3S")
    _tap_card(app, gs, "3H")
    assert gs.hand.selected == ["3H"] and not gs.hand.warned and not gs.enemy.warn
    assert not gs.hand.views["3S"].warn


def _mission11_top_discard_immunity(app, discard):
    """Mission 11: the enemy is immune to the classes of the top discard (a 2♣: warriors)."""
    gs, g = _late_mission_attempt(app, 11, seed=1100)
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    for play in g.plays:
        g.discard.extend(play.card_ids)
    g.plays = []
    set_mission_enemy(g, "CV_J1", hp=100)
    g.tavern.extend(g.banished)
    g.banished[:] = []
    set_discard(g, discard)
    set_hand(g, ["4H", "4C", "9C", "8C", "AH", "10H"])
    gs.refresh(after_action=False)
    return gs, g


def test_a_power_whose_immunity_hangs_on_a_hidden_shuffle_is_not_marked(app):
    rest = ["9S", "10D", "7H", "10S", "3D", "6D", "8D", "5S", "2D", "3C", "10C"]
    for k in range(len(rest)):
        gs, g = _mission11_top_discard_immunity(app, ["2C"] + rest[k:] + rest[:k])
        assert "C" in g.rules.immune_suits(g)
        gs.hand.set_selection(["4C"])                     # the top discard decides: immune
        assert gs.hand.warned == {"4C"} and gs.enemy.warn and "♣ immune." in gs.forecast
        # 4♥ heals first and shuffles the discard pile: the new top card, and so the
        # warriors' immunity, may not be known
        gs.hand.set_selection(["4H", "4C"])
        pv = gs.enemy.projection
        if pv["powers"]["C"].get("immune", False) is None:
            break
    else:
        pytest.fail("no discard order left the warriors' immunity to the shuffle")
    assert pv["uncertain"]
    assert not gs.hand.warned and not gs.enemy.warn and not gs.hand.views["4C"].warn
    assert "♣ immune?" in gs.forecast


# ---------------------------------------------------------------------------- 9. the header's projection notes
def _header_notes(gs):
    """What the header draws: [label, number, notes..., label, number, notes...]."""
    return _drawn_text(gs.enemy)


def _attack_side(gs):
    drawn = _header_notes(gs)
    return drawn[:drawn.index("HEALTH")]


def _health_side(gs):
    drawn = _header_notes(gs)
    return drawn[drawn.index("HEALTH"):]


@pytest.mark.parametrize("beast", ["B_C", "B_S", "B_H", "B_D"])
def test_a_guardian_play_projects_no_attack_whatever_beast_comes_next(app, beast):
    gs, g = _late_mission_attempt(app, 11, guardians=True, seed=1101)
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    for play in g.plays:
        g.discard.extend(play.card_ids)
    g.plays = []
    set_mission_enemy(g, "CV_J1")
    g.extra["beast_deck"] = [beast] + [b for b in ("B_C", "B_S", "B_H", "B_D") if b != beast]
    g.extra["beasts_out"] = []
    set_hand(g, ["3G", "9S", "8S", "2C"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3G"])
    atk = _attack_side(gs)
    assert g.enemy_attack > 0 and atk[:2] == ["ATTACK", "%d" % g.enemy_attack] and "→ 0" in atk
    assert "nothing to suffer" in gs.forecast and "then suffer" not in gs.forecast
    assert "→ %d" % (g.enemy.hp - 3) in _health_side(gs)
    gs.hand.set_selection(["9S"])                         # an ordinary play: the attack still comes
    assert "→ 0" not in _attack_side(gs) and "then suffer" in gs.forecast


def test_a_heal_that_reshuffles_what_feeds_the_enemy_projects_an_unknown_attack(app):
    # mission 4: the Phase I bard's attack is 10 plus the top discard; a heal shuffles the
    # discard pile first, so what is suffered after it is not known
    gs, g = _flute_mission(app, 4)
    set_mission_enemy(g, "LABJD", hp=100)
    set_discard(g, ["2C", "9S", "4D", "7C", "10S", "3D", "6C", "8D", "5S", "2D"])
    set_hand(g, ["8H", "9S"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["8H"])
    pv = gs.enemy.projection
    assert pv["uncertain"] and pv["suffer"] is None
    assert "→ ?" in _attack_side(gs) and "then suffer ?" in gs.forecast
    assert "→ 92" in _health_side(gs)                     # the damage itself is known
    gs.hand.set_selection(["9S"])                         # no shuffle: the number is known
    pv = gs.enemy.projection
    assert not pv["uncertain"] and "→ ?" not in _header_notes(gs)
    assert "→ %d" % pv["suffer"] in _attack_side(gs)


def test_a_two_five_play_marks_the_numbers_that_assume_a_declared_value(app):
    _new_campaign(app, ["Solo"])
    camp = app.campaign
    camp.m_box_opened, camp.coins = True, 5
    camp.hire("merc_25H")
    camp.hire("merc_25S")
    app.save_campaign()
    app.start_attempt()
    gs, g = app.current, app.game
    set_enemy(g, "Q", "C", hp=30)
    set_hand(g, ["M25H", "5D", "M25S", "9S"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["M25H", "M25S"])               # two 2/5s: declared later (5 assumed)
    assert gs.enemy.projection["decision_kind"] == "declare_value"
    assert "→ 5?" in _attack_side(gs) and "→ 20?" in _health_side(gs)
    gs.hand.set_selection(["M25H", "5D"])                 # with a 5 its value is fixed: no "?"
    assert gs.enemy.projection["decision_kind"] != "declare_value"
    assert "→ 20" in _health_side(gs) and not any(t.endswith("?") for t in _header_notes(gs))


# ---------------------------------------------------------------------------- 10. the attack's card
def _shield_rows(pop):
    """The SHIELD column's rows, top to bottom: [(label, ...labels on the same row)]."""
    labels = [v for v in ui.find(pop, lambda v: isinstance(v, ui.Label) and not v.hidden)]
    head = [v for v in labels if v.text == "SHIELD"][0]
    col = [v for v in labels if v.x >= head.x - 0.5 and v.y > head.y and v is not head]
    names = [v for v in col if v.x < head.x + 0.5 and v.width < head.width]       # the cards, left
    rows = []
    for n in sorted(names, key=lambda v: v.y):
        rows.append([n] + [v for v in col if v is not n and abs(v.y - n.y) < 0.5])
    return rows


@pytest.mark.parametrize("size", [(390, 844), (320, 568)])
def test_the_attack_card_wraps_a_long_paladin_play_instead_of_cutting_it(app, size):
    _resize(app, *size)
    app.start_game(GameConfig(players=1), seed=4)
    gs, g = app.current, app.game
    set_enemy(g, "K", "H")
    for ids, suits, value in ((["2S", "2C", "2H", "2D"], ("S", "C", "H", "D"), 8), (["AS", "10S"], ("S",), 11),
                              (["3S", "3D", "3C"], ("S", "D", "C"), 9)):
        for c in ids:
            _pull(g, c)
        g.plays.append(Play(player=0, card_ids=list(ids), suits=suits, value=value, jester=False))
    set_hand(g, ["5C", "9D"])
    gs.refresh(after_action=False)
    pop = _open_attack(app, gs)
    labels = [v for v in ui.find(pop, lambda v: isinstance(v, ui.Label) and not v.hidden)]
    assert not [v.text for v in labels if ui.label_truncated(v)]
    rows = _shield_rows(pop)
    assert [r[0].text for r in rows] == ["2♠ + 2♣ + 2♥ + 2♦", "A♠ + 10♠", "3♠ + 3♦ + 3♣"]
    assert [[v.text for v in r[1:]] for r in rows] == [["8"], ["11"], ["9"]]
    assert rows[0][0].height > 20                         # more than one line
    for upper, lower in zip(rows, rows[1:]):              # a wrapped row pushes the next one down
        assert upper[0].y + upper[0].height <= lower[0].y + 0.5
    assert "−28" in _texts(pop) and "You suffer 0" in _texts(pop)


def test_the_attack_card_says_an_immune_paladin_play_adds_nothing(app):
    app.start_game(GameConfig(players=1), seed=4)
    gs, g = app.current, app.game
    set_enemy(g, "J", "S")
    _pull(g, "4S")
    g.plays.append(Play(player=0, card_ids=["4S"], suits=("S",), value=4, jester=False))
    _pull(g, "5D")
    g.plays.append(Play(player=0, card_ids=["5D"], suits=("D",), value=5, jester=False))
    gs.refresh(after_action=False)
    assert g.shield == 0
    pop = _open_attack(app, gs)
    rows = _shield_rows(pop)
    assert len(rows) == 1                                 # the diamond adds no shield: no row
    row = " ".join(v.text for v in rows[0])
    assert "4♠" in row and "immune" in row and "4" not in [v.text for v in rows[0][1:]]
    assert "You suffer 10" in _texts(pop)


def _team_damage_with_a_shield(app):
    """Mission 6, solo: a 4♠ shields 4, then a kill brings Myla's team damage of 7."""
    gs, g = _mission_attempt(app, 6)
    set_mission_enemy(g, "GDQH", hp=9)
    set_hand(g, ["5S", "8S", "AD", "3C", "4S", "9C", "10D"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["4S"])
    _tap_button(app, "Play")
    gs.hand.set_selection(["8S", "3C"])
    _tap_button(app, "Discard")
    assert g.phase == PHASE_PLAY and g.shield == 4 and "shield 4" in _attack_side(gs)
    gs.hand.set_selection(["5S"])                         # exact: the Guardian Statue falls
    _tap_button(app, "Play")
    _tap_button(app, "Move 5♠ to the mission zone")
    _tap_button(app, "Rescue 5♠ to the discard pile")
    assert g.decision["kind"] == "team_discard" and gs.overlay is None
    return gs, g


def test_during_team_damage_the_attack_card_and_the_header_show_what_is_owed(app):
    gs, g = _team_damage_with_a_shield(app)
    atk = _attack_side(gs)
    assert atk[:2] == ["SUFFER", "7"] and not any(t.startswith("shield") for t in atk)
    texts = _texts(_open_attack(app, gs))
    assert "Team damage 7" in texts and not any(t.startswith("You suffer") for t in texts)
    _popup(gs).close()
    _tap_card(app, gs, "9C")                              # paying it: the header counts it down
    atk = _attack_side(gs)
    assert atk[:2] == ["SUFFER", "7"] and "covered" in atk and not any(t.startswith("shield") for t in atk)


def test_the_attack_cards_shield_total_matches_the_rows_it_shows(app):
    gs, g = _team_damage_with_a_shield(app)
    pop = _open_attack(app, gs)
    shown = sum(int(v.text) for r in _shield_rows(pop) for v in r[1:] if v.text.isdigit())
    assert "−%d" % shown in _texts(pop), (_texts(pop), shown)


# ---------------------------------------------------------------------------- 11. the Kinfolk Flute's greying
def test_the_flute_decision_greys_a_card_that_would_pass_ten_with_the_one_picked(app):
    _new_campaign(app, ["Ana", "Ben"])
    app.campaign.relics.append("flute")
    app.start_attempt()
    gs, g = app.current, app.game
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "3S", "9S", "8S"], player=0)
    set_hand(g, ["3D", "3H", "7C", "AS"], player=1)
    gs.reveal_hand()
    gs.hand.set_selection(["3C", "3S"])                   # 6: one more 3 makes 9, two make 12
    _tap_button(app, "Play")
    _show_hand(app, gs)
    assert g.decision["kind"] == "flute_add" and g.deciding == 1
    lit = sorted(c for c, v in gs.hand.views.items() if not v.shaded)
    assert lit == ["3D", "3H"]
    _tap_card(app, gs, "3D")
    assert gs.hand.selected == ["3D"] and gs.right_btn.enabled and "attack 9" in gs.forecast
    assert gs.hand.views["3H"].shaded and not gs.hand.views["3D"].shaded
    _tap_card(app, gs, "3H")                              # a greyed card that may be added alone: a new pick
    assert gs.hand.selected == ["3H"] and gs.right_btn.enabled and gs.hand.views["3D"].shaded
    _tap_card(app, gs, "3H")
    assert gs.hand.selected == [] and not any(gs.hand.views[c].shaded for c in ("3D", "3H"))


def test_a_flute_pair_stays_selected_without_a_hand_card(app):
    gs, g = _flute_mission(app)
    set_hand(g, ["9D", "7C", "8S", "3D"])
    for c in ("3C", "3H"):
        _pull(g, c)
    g.extra["flute"] = ["3C", "3H"]
    gs.refresh(after_action=False)
    for c in ("3D", "3C", "3H"):
        _tap_card(app, gs, c)
    assert gs.hand.selected == ["3D", "3C", "3H"] and gs.right_btn.enabled
    _tap_card(app, gs, "3D")                              # the flute's own pair is a set by itself
    assert gs.hand.selected == ["3C", "3H"] and gs.right_btn.enabled


def test_a_lone_flute_card_left_without_its_hand_card_is_dropped_from_the_selection(app):
    gs, g = _flute_mission(app)
    set_hand(g, ["5S", "3D", "7C", "9D", "2H"])
    _pull(g, "3C")
    g.extra["flute"] = ["3C"]
    gs.refresh(after_action=False)
    _tap_card(app, gs, "3D")
    _tap_card(app, gs, "3C")
    assert gs.hand.selected == ["3D", "3C"] and gs.right_btn.enabled
    _tap_card(app, gs, "3D")
    assert gs.hand.selected == [] and not gs.hand.views["3C"].selected


# ---------------------------------------------------------------------------- 12. a Chanter-sized hand
def test_a_thirteen_card_hand_after_a_chanters_draw_keeps_readable_cards_on_a_small_phone(app):
    _resize(app, 375, 667)
    gs, g = _mission_attempt(app, 8)
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    set_mission_enemy(g, "HEJ6", hp=100)
    set_hand(g, ["3T", "9S", "8S", "7S", "6S", "5S", "4S", "2S"])
    set_tavern_top(g, ["AH", "2H", "3H", "4H", "5H", "6H", "7H", "8H"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3T"])
    _tap_button(app, "Play")
    _tap_button(app, "6")                                 # 7 left + 6 drawn
    assert g.decision["kind"] == "chanter_discard" and len(gs.hand.cards) == 13 and not gs.message.hidden
    hand = gs.hand
    cols = len(set(round(v.x, 1) for v in hand.views.values()))
    assert cols > 6                                       # more columns than a short screen's six
    for v in hand.views.values():
        assert v.width >= 40 and v.x >= 0 and v.x + v.width <= hand.width + 0.5
        assert v.y >= 0 and v.y + v.height <= hand.height + 0.5
    assert hand.y >= gs.message.y + gs.message.height and hand.y + hand.height <= gs.strip.y


# ---------------------------------------------------------------------------- 13. the piles viewer's notes
def test_the_piles_viewer_counts_a_single_card_as_one_card(app):
    gs, g = _flute_mission(app, 4)
    set_discard(g, ["7C"])
    g.tavern.extend(g.banished)
    _pull(g, "4D")
    g.banished[:] = ["4D"]
    gs.refresh(after_action=False)
    for key in ("discard", "banished"):
        ui.tap(app, *ui.root_point(app, gs.pile_views[key]))
        texts = _texts(gs.overlay)
        assert "1 card in order, the top card first." in texts, texts
        _tap_button(app, "Back")
    _pull(g, "8C")
    g.discard.insert(0, "8C")
    gs.refresh(after_action=False)
    ui.tap(app, *ui.root_point(app, gs.pile_views["discard"]))
    assert "2 cards in order, the top card first." in _texts(gs.overlay)
    _tap_button(app, "Back")
    reserve = list(g.tavern)
    g.tavern[:] = reserve[:1]
    g.discard.extend(reserve[1:])
    gs.refresh(after_action=False)
    ui.tap(app, *ui.root_point(app, gs.pile_views["reserve"]))
    assert any(t.startswith("1 card left in the reserve deck") for t in _texts(gs.overlay)), _texts(gs.overlay)


def test_a_one_card_hand_is_counted_as_one_card_on_the_choose_next_buttons(app):
    gs, g, jester = _claimed_jester_game(app)
    gs.hand.set_selection([jester])
    _tap_button(app, "Play")
    titles = [b.title for b in ui.find(gs.overlay, lambda v: isinstance(v, ui.Button))]
    assert "Ana (1 card)" in titles, titles
