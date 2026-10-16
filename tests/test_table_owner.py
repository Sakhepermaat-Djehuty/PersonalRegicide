"""The owner's table: rows of cards that overflow behind a card back (the mission zone above
the hand, the played cards under it), no running text on the table, greyed cards that ignore
a tap, an attack card with no suit or class symbols whose paladin rows say "(immune)" (also
after the enemy becomes immune mid-fight), "(corrupted)" and "(Jester)", a test copy of the
app with saves of its own, and main.py dropping another copy's modules."""
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402

from regicide.cards import SUIT_SYMBOL  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402
from regicide.engine import PHASE_DECIDE, PHASE_PLAY, PHASE_SUFFER, Play  # noqa: E402
from regicide.rules import GameConfig  # noqa: E402
from helpers import _pull, set_discard, set_enemy, set_hand, set_mission_enemy, set_tavern_top  # noqa: E402

SIZES = [(320, 568), (375, 667), (390, 844), (430, 932)]
# every suit and Legacy class symbol, without the "text style" selector some carry
SYMBOLS = [s.replace("︎", "") for s in SUIT_SYMBOL.values()]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app import widgets
    from app.screens import App, MenuScreen
    ui.set_screen_size(390, 844)
    monkeypatch.setattr(widgets, "BACK_STYLE", widgets.BACK_STYLE)    # whatever a test changes
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
    """Tap a visible, enabled button by title ("Discard" also finds "Discard 8/10")."""
    try:
        b = ui.button(app, title)
    except KeyError:
        b = [v for v in ui.find(app, lambda v: isinstance(v, ui.Button) and not v.hidden
                                and re.match(re.escape(title) + r" \d+/\d+$", v.title or ""))][0]
    assert b.enabled, "button %s disabled" % title
    ui.tap(app, *ui.root_point(app, b))


def _tap_card(app, gs, card_id):
    ui.tap(app, *ui.root_point(app, gs.hand.views[card_id]))


def _show_hand(app, gs):
    if gs.overlay is not None and ui.find(gs.overlay, lambda v: isinstance(v, ui.Button) and v.title == "Show my hand"):
        _tap_button(app, "Show my hand")


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


def _origin(root, view):
    """A view's top-left corner in root coordinates."""
    cx, cy = ui.root_point(root, view)
    return cx - view.width / 2.0, cy - view.height / 2.0


def _row_ids(strip):
    """The face-up cards a row shows, left to right."""
    from app.widgets import CardView
    views = sorted((v for v in strip.subviews if isinstance(v, CardView)), key=lambda v: v.x)
    return [v.card.id for v in views]


def _row_views(strip):
    from app.widgets import CardView
    return sorted((v for v in strip.subviews if isinstance(v, CardView)), key=lambda v: v.x)


def _tap_row(app, strip, x):
    """A tap on a row of cards ``x`` points from its left edge, halfway down its cards."""
    ox, oy = _origin(app, strip)
    top = strip.top() if hasattr(strip, "top") else 0.0
    _, ch = strip.card_size()
    ui.tap(app, ox + x, oy + top + 2 + ch / 2.0)


def _tap_back(app, strip):
    """A tap on the card back that starts a full row."""
    cw, _ = strip.card_size()
    _tap_row(app, strip, cw / 2.0)


def _list_title(ov):
    """(name, count) of a card list's title ("Mission zone · 9")."""
    found = [re.match(r"^(.+) · (\d+)$", t) for t in _texts(ov)]
    found = [m for m in found if m]
    assert len(found) == 1, _texts(ov)
    return found[0].group(1), int(found[0].group(2))


def _table_labels(gs):
    """The labels showing on the table itself (not in a box over it)."""
    out = []

    def walk(v):
        if v.hidden or v is gs.overlay:
            return
        if isinstance(v, ui.Label):
            out.append(v)
        for s in v.subviews:
            walk(s)
    for s in gs.subviews:
        walk(s)
    return out


def _popup(gs):
    from app.screens import CardPopup
    pops = [v for v in gs.app.subviews if isinstance(v, CardPopup)]
    assert pops
    return pops[-1]


def _open_attack(app, gs):
    """Tap left of the enemy's card in the header: the attack's card."""
    ui.tap(app, gs.enemy.x + 10, ui.root_point(app, gs.enemy)[1])
    return _popup(gs)


def _attack_card(app, gs):
    """The attack's card as (labels, drawn strings); it is closed again."""
    pop = _open_attack(app, gs)
    texts, drawn = _texts(pop), _drawn_text(pop)
    pop.close()
    assert not [v for v in gs.subviews if v is pop]
    return texts, drawn


def _shield_rows(pop):
    """The SHIELD column's rows, top to bottom: [(name, value)]."""
    labels = [v for v in ui.find(pop, lambda v: isinstance(v, ui.Label) and not v.hidden)]
    head = [v for v in labels if v.text == "SHIELD"][0]
    col = [v for v in labels if v.x >= head.x - 0.5 and v.y > head.y and v is not head]
    names = [v for v in col if v.x < head.x + 0.5 and v.width < head.width]       # the cards, left
    rows = []
    for n in sorted(names, key=lambda v: v.y):
        rows.append((n.text, " ".join(v.text for v in col if v is not n and abs(v.y - n.y) < 0.5)))
    return rows


def _attack_shield(app, gs):
    """The attack card's SHIELD rows and its total; the card is closed again."""
    pop = _open_attack(app, gs)
    rows = _shield_rows(pop)
    texts = _texts(pop)
    pop.close()
    total = [t for t in texts if re.match(r"^−\d+$", t)]
    return rows, (int(total[0][1:]) if total else 0), texts


def _this_play(app, gs):
    """The attack card's rows for the selected cards ("THIS PLAY"), in order; closed again."""
    texts = _texts(_open_attack(app, gs))
    _popup(gs).close()
    rows = texts[texts.index("THIS PLAY") + 1:]
    return list(zip(rows[::2], rows[1::2]))


def _assert_no_symbols(strings, where=""):
    bad = [(t, s) for t in strings for s in SYMBOLS if s in t]
    assert not bad, (where, bad)


def _new_campaign(app, names, seed=4242):
    """A new campaign whose attempts deal the same cards every run."""
    app.new_campaign(len(names), list(names))
    app.campaign.seed = seed
    return app.campaign


def _mission_attempt(app, number, names=("Solo",), relics=(), corrupted=(), restored=()):
    """A Legacy mission attempt with the party it would have (Gøran from 5, Myla from 6) and
    these party cards corrupted; the start's decisions are taken."""
    _new_campaign(app, names)
    camp = app.campaign
    camp.mission = number
    camp.completed = list(range(1, number))
    camp.relics.extend(relics)
    if number >= 5:
        P.add_card(camp.party, dict(M.GORAN))
        camp.flags["beasts"] = True
        camp.set_beast("B_H")
    if number >= 6:
        P.add_card(camp.party, dict(M.MYLA))
    for d in M.MAGE_DECK:
        if P.find(camp.party, str(d["id"])) is None:
            P.add_card(camp.party, dict(d))
    for cid in corrupted:
        P.add_flag(camp.party, cid, "corrupted")
        camp.corrupted.append(cid)
    for cid in restored:
        P.add_flag(camp.party, cid, "restored")
    app.save_campaign()
    app.start_attempt()
    gs, g = app.current, app.game
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    gs.refresh(after_action=False)
    return gs, g


def _base_game(app, seed=4):
    app.start_game(GameConfig(players=1), seed=seed)
    return app.current, app.game


# the cards played one at a time against a King that never strikes back
PLAYS = ["2C", "3C", "4C", "5C", "6C", "7C", "8C", "9C", "10C", "2D", "3D", "4D", "5D", "6D"]


def _play_one(app, gs, g, cid):
    """The active player plays ``cid`` alone, with the Play button."""
    set_hand(g, [cid, "AS"])
    gs.refresh(after_action=False)
    _tap_card(app, gs, cid)
    _tap_button(app, "Play")
    assert g.phase == PHASE_PLAY and g.plays[-1].card_ids == [cid]


# ---------------------------------------------------------------------------- 1. a row that overflows
def _bare_strip(width, height=56.0):
    from app.widgets import TableStrip
    s = TableStrip()
    s.frame = (0, 0, width, height)
    return s


def _assert_slots(strip, back):
    """The face-up cards side by side left to right, none over another, all inside the row;
    with a card back, the first face card starts after the back's room."""
    cw, ch = strip.card_size()
    views = _row_views(strip)
    assert views
    if back:
        assert views[0].x >= cw + 1
    for left, right in zip(views, views[1:]):
        assert right.x >= left.x + left.width
    for v in views:
        assert v.width == cw and v.height == ch and v.x >= 0 and v.x + v.width <= strip.width + 0.5
        assert v.y >= 0 and v.y + v.height <= strip.height + 0.5


def _spy_backs(monkeypatch):
    from app import widgets
    calls = []
    real = widgets.draw_back

    def spy(x, y, w, h, count=None, plain=False):
        calls.append((x, y, w, h, count))
        real(x, y, w, h, count, plain)
    monkeypatch.setattr(widgets, "draw_back", spy)
    return calls


def _cards(ids):
    from helpers import new_game
    g = new_game()
    return [g.card(c) for c in ids]


def test_a_row_shows_every_card_until_full_then_a_back_with_the_total_and_the_newest(monkeypatch):
    strip = _bare_strip(300)
    cap = strip.capacity()
    cw, ch = strip.card_size()
    assert 3 <= cap < len(PLAYS) - 2
    taps = []
    strip.on_more = lambda: taps.append(1)
    backs = _spy_backs(monkeypatch)
    # exactly full: every card face up, oldest on the left, no back
    strip.set_cards(_cards(PLAYS[:cap]))
    assert not strip.overflows() and [c.id for c in strip.shown()] == PLAYS[:cap]
    assert _row_ids(strip) == PLAYS[:cap] and _row_views(strip)[0].x == 0
    _assert_slots(strip, back=False)
    ui.render(strip)
    assert backs == []
    strip.touch_ended(ui.Touch((cw / 2.0, ch / 2.0), (cw / 2.0, ch / 2.0), "ended"))
    assert taps == []                                     # a face card: nothing to open
    # one more: a back first, holding the total, then the newest cap-1 cards in order
    strip.set_cards(_cards(PLAYS[:cap + 1]))
    assert strip.overflows() and [c.id for c in strip.cards] == PLAYS[:cap + 1]
    assert [c.id for c in strip.shown()] == PLAYS[2:cap + 1]
    assert _row_ids(strip) == PLAYS[2:cap + 1]
    _assert_slots(strip, back=True)
    ui.render(strip)
    assert len(backs) == 1
    x, y, w, h, count = backs[0]
    assert (x, round(w, 3), round(h, 3), count) == (0, round(cw, 3), round(ch, 3), cap + 1)
    monkeypatch.undo()
    assert "%d" % (cap + 1) in _drawn_text(strip)         # the total, on the back itself
    # each new card pushes the oldest shown out of sight
    strip.set_cards(_cards(PLAYS[:cap + 2]))
    assert [c.id for c in strip.shown()] == PLAYS[3:cap + 2] and _row_ids(strip) == PLAYS[3:cap + 2]
    assert PLAYS[2] not in _row_ids(strip) and _row_ids(strip)[-1] == PLAYS[cap + 1]
    assert "%d" % (cap + 2) in _drawn_text(strip)
    # only a tap on the back opens the list
    strip.touch_ended(ui.Touch((cw / 2.0, ch / 2.0), (0, 0), "ended"))
    assert taps == [1]
    last = _row_views(strip)[-1]
    strip.touch_ended(ui.Touch((last.x + cw / 2.0, ch / 2.0), (0, 0), "ended"))
    strip.touch_ended(ui.Touch((_row_views(strip)[0].x + cw / 2.0, ch / 2.0), (0, 0), "ended"))
    assert taps == [1]


def test_an_empty_row_draws_only_its_outline(monkeypatch):
    strip = _bare_strip(300)
    strip.on_more = lambda: pytest.fail("an empty row opens nothing")
    strip.set_cards([])
    assert strip.subviews == [] and not strip.overflows() and strip.shown() == []
    backs = _spy_backs(monkeypatch)
    strokes, fills = [], []
    real_stroke, real_fill = ui.Path.stroke, ui.Path.fill
    monkeypatch.setattr(ui.Path, "stroke", lambda self: (strokes.append((self.kind, self.box)), real_stroke(self)))
    monkeypatch.setattr(ui.Path, "fill", lambda self: (fills.append((self.kind, self.box)), real_fill(self)))
    drawn = _drawn_text(strip)
    assert backs == [] and fills == []
    assert len(strokes) == 1 and strokes[0][0] == "rrect"          # one outlined slot
    cw, ch = strip.card_size()
    x, y, w, h = strokes[0][1]
    assert 0 <= x and x + w <= cw and 0 <= y and y + h <= strip.height
    assert all(t == getattr(strip, "label", "") for t in drawn), drawn   # no words about what is in it
    strip.touch_ended(ui.Touch((cw / 2.0, ch / 2.0), (0, 0), "ended"))


def test_the_played_row_overflows_behind_a_back_that_lists_every_card_played(app):
    from app.screens import CardListOverlay
    from app.widgets import CardView
    gs, g = _base_game(app)
    set_enemy(g, "K", "H", hp=500, attack=0)              # never defeated, never strikes back
    gs.refresh(after_action=False)
    strip = gs.strip
    assert not [v for v in strip.subviews if isinstance(v, CardView)]      # nothing played: an empty row
    cap = strip.capacity()
    played = []
    for cid in PLAYS[:cap]:
        _play_one(app, gs, g, cid)
        played.append(cid)
    assert [c.id for c in strip.cards] == played and not strip.overflows() and _row_ids(strip) == played
    _tap_back(app, strip)                                 # a full row's first card is a card, not a back
    assert gs.overlay is None
    _play_one(app, gs, g, PLAYS[cap])
    played.append(PLAYS[cap])
    assert len(g.plays) == cap + 1 and strip.overflows()
    assert [c.id for c in strip.cards] == played == [c for p in g.plays for c in p.card_ids]
    assert _row_ids(strip) == played[-(cap - 1):] and "%d" % (cap + 1) in _drawn_text(strip)
    _play_one(app, gs, g, PLAYS[cap + 1])                 # the next play pushes the oldest shown out
    played.append(PLAYS[cap + 1])
    assert _row_ids(strip) == played[-(cap - 1):] and played[-cap] not in _row_ids(strip)
    assert "%d" % (cap + 2) in _drawn_text(strip)
    # a card picked in the hand, then a tap on a face card in the row: nothing
    set_hand(g, ["9D", "AS"])
    gs.refresh(after_action=False)
    _tap_card(app, gs, "9D")
    pv = gs.enemy.projection
    assert gs.hand.selected == ["9D"] and pv is not None
    cw, _ = strip.card_size()
    _tap_row(app, strip, _row_views(strip)[-1].x + cw / 2.0)
    assert gs.overlay is None
    # a tap on the back: every card played against the enemy, oldest first, with the total
    _tap_back(app, strip)
    ov = gs.overlay
    assert isinstance(ov, CardListOverlay)
    assert list(ov.card_views) == played and [v.card.id for v in ov.card_views.values()] == played
    name, count = _list_title(ov)
    assert count == len(played) and name.lower() in ("played", "play zone")
    # Back: the table as it was, the selection and what it would do kept
    _tap_button(app, "Back")
    assert gs.overlay is None and gs.hand.selected == ["9D"] and gs.hand.views["9D"].selected
    assert gs.enemy.projection is not None and gs.enemy.projection["damage"] == pv["damage"] == 9
    assert gs.right_btn.enabled and _row_ids(strip) == played[-(cap - 1):]


def test_the_mission_zone_overflows_behind_a_back_that_lists_the_whole_zone(app):
    from app.screens import CardListOverlay
    from app.widgets import CardView
    gs, g = _mission_attempt(app, 3)                      # Lessons in Flames: the zone grows each turn
    set_mission_enemy(g, g.enemy.card_id, hp=200)
    gs.refresh(after_action=False)
    zone = gs.zone
    assert not zone.hidden and g.mission_zone == [] and zone.cards == []
    assert not [v for v in zone.subviews if isinstance(v, CardView)]       # an empty zone: its outline
    cap = zone.capacity()
    fill = [c for c in g.tavern if c not in ("9S", "5H", "6H", "7H", "8H")][:cap + 1]
    for c in fill:
        _pull(g, c)
    g.mission_zone.extend(fill[:cap])
    gs.refresh(after_action=False)
    assert [c.id for c in zone.cards] == fill[:cap] and not zone.overflows() and _row_ids(zone) == fill[:cap]
    _tap_back(app, zone)
    assert gs.overlay is None                             # not full: no back, nothing opens
    g.mission_zone.append(fill[cap])
    gs.refresh(after_action=False)
    assert zone.overflows() and _row_ids(zone) == fill[-(cap - 1):]
    assert "%d" % (cap + 1) in _drawn_text(zone)
    # the end of a real turn puts the reserve's top card into the zone: it is the newest shown
    set_tavern_top(g, ["9S"])
    set_hand(g, ["5H", "6H", "7H", "8H"])
    gs.refresh(after_action=False)
    _tap_card(app, gs, "5H")
    _tap_button(app, "Play")
    assert g.phase == PHASE_SUFFER
    for cid in ("6H", "7H"):                              # 13 pays the 10 suffered, one card at a time
        _tap_card(app, gs, cid)
    _tap_button(app, "Discard")
    assert g.phase == PHASE_PLAY and g.mission_zone[-1] == "9S" and len(g.mission_zone) == cap + 2
    ids = list(g.mission_zone)
    assert [c.id for c in zone.cards] == ids and _row_ids(zone)[-1] == "9S"
    assert _row_ids(zone) == ids[-(cap - 1):] and fill[2] not in _row_ids(zone)
    # a card picked, a tap on a face card of the zone: nothing; on the back: the whole zone
    _tap_card(app, gs, gs.hand.cards[0].id)
    sel = list(gs.hand.selected)
    assert sel
    cw, _ = zone.card_size()
    _tap_row(app, zone, _row_views(zone)[0].x + cw / 2.0)
    assert gs.overlay is None
    _tap_back(app, zone)
    ov = gs.overlay
    assert isinstance(ov, CardListOverlay) and list(ov.card_views) == ids
    name, count = _list_title(ov)
    assert count == len(ids) and name.lower() == "mission zone"
    _tap_button(app, "Back")
    assert gs.overlay is None and gs.hand.selected == sel and gs.enemy.projection is not None


def _own_strings(strip):
    """The strings a row draws itself (its name, a card back's total), not its face cards'."""
    from app.widgets import CardView
    calls = []
    real_draw, real_card = ui.draw_string, CardView.draw
    ui.draw_string = lambda text, *a, **k: calls.append(str(text))
    CardView.draw = lambda self: None
    try:
        ui.render(strip)
    finally:
        ui.draw_string, CardView.draw = real_draw, real_card
    return calls


def test_the_rows_draw_their_names_and_a_backs_total_and_no_words_about_their_cards(app):
    from app.screens import MISSION_ZONE, PLAY_ZONE
    gs, g = _mission_attempt(app, 3)
    set_mission_enemy(g, g.enemy.card_id, hp=200)
    gs.refresh(after_action=False)
    zone, strip = gs.zone, gs.strip
    assert zone.label in ("", MISSION_ZONE) and strip.label in ("", PLAY_ZONE)
    names = dict((s, [s.label] if s.label else []) for s in (zone, strip))
    assert _own_strings(zone) == names[zone] and _own_strings(strip) == names[strip]      # empty rows
    fill = list(g.tavern)[:zone.capacity() + 1]
    for c in fill + ["4C"]:
        _pull(g, c)
    g.mission_zone.extend(fill[:2])
    g.plays.append(Play(player=0, card_ids=["4C"], suits=("C",), value=4, jester=False))
    gs.refresh(after_action=False)
    assert len(zone.cards) == 2 and len(strip.cards) == 1
    assert _own_strings(zone) == names[zone] and _own_strings(strip) == names[strip]      # a few cards
    g.mission_zone.extend(fill[2:])
    gs.refresh(after_action=False)
    assert zone.overflows()
    assert _own_strings(zone) == names[zone] + ["%d" % len(g.mission_zone)]              # a full row


# ---------------------------------------------------------------------------- 2. the layout
def _rect(v):
    return (v.x, v.y, v.x + v.width, v.y + v.height)


def _overlap(a, b):
    ax0, ay0, ax1, ay1 = _rect(a)
    bx0, by0, bx1, by1 = _rect(b)
    return min(ax1, bx1) - max(ax0, bx0) > 0.5 and min(ay1, by1) - max(ay0, by0) > 0.5


@pytest.mark.parametrize("size", SIZES)
def test_the_zone_sits_above_the_hand_and_the_played_row_below_it_on_every_phone(app, size):
    w, h = size
    _resize(app, w, h)
    for start in ("zone mission", "base game"):
        if start == "zone mission":
            gs, g = _mission_attempt(app, 3)
            g.mission_zone.extend(c for c in list(g.tavern)[:2])
            for c in g.mission_zone:
                g.tavern.remove(c)
        else:
            gs, g = _base_game(app)
            _pull(g, "4C")
            g.plays.append(Play(player=0, card_ids=["4C"], suits=("C",), value=4, jester=False))
        assert gs.frame == (0, 0, w, h)
        gs.refresh(after_action=False)
        hand, strip, zone = gs.hand, gs.strip, gs.zone
        bar = [gs.left_btn, gs.mid_btn, gs.right_btn]
        assert len(hand.cards) >= 7
        assert zone.hidden == (start == "base game")
        if not zone.hidden:
            # the mission zone under the piles, above the hand, as wide as the played row
            for p in gs.pile_views.values():
                assert p.hidden or p.y + p.height <= zone.y
            assert zone.y + zone.height <= hand.y and zone.x == strip.x and zone.width >= strip.width
        # the played row between the hand and the action buttons
        assert hand.y + hand.height <= strip.y and all(strip.y + strip.height <= b.y for b in bar)
        assert [c.id for c in strip.cards] == [c for p in g.plays for c in p.card_ids]
        # nothing on the table overlaps, everything is on the screen
        shown = [v for v in gs.subviews if not v.hidden and v is not gs.overlay]
        for v in shown:
            assert v.x >= -0.5 and v.y >= -0.5 and v.x + v.width <= w + 0.5 and v.y + v.height <= h + 0.5, v
        clashes = [(type(a).__name__, type(b).__name__) for i, a in enumerate(shown) for b in shown[i + 1:]
                   if _overlap(a, b)]
        assert not clashes, (size, start, clashes)
        # the hand's cards inside the hand, readable
        for v in hand.views.values():
            assert v.x >= 0 and v.y >= 0 and v.x + v.width <= hand.width + 0.5 and v.y + v.height <= hand.height + 0.5
            assert v.width >= (32 if h <= 568 else 40), (size, start, v.width)
        # no running text: no message label, no caption, no forecast; the only label on the
        # table is the status line
        for gone in ("message", "_caption", "forecast", "_strips_shared"):
            assert not hasattr(gs, gone), gone
        labels = _table_labels(gs)
        assert labels == [gs.status], [v.text for v in labels]
        # the old setting for played cards above the hand is gone
        app.settings["played_below"] = False
        gs.layout()
        assert hand.y + hand.height <= strip.y and (zone.hidden or zone.y + zone.height <= hand.y)
        app.settings.pop("played_below", None)
        assert ui.render(app).size[0] > 0


# ---------------------------------------------------------------------------- 3. greyed cards
def _counting_changes(gs):
    calls = []
    real = gs.hand.on_change

    def counted():
        calls.append(list(gs.hand.selected))
        real()
    gs.hand.on_change = counted
    return calls


def test_a_tap_on_a_greyed_card_does_nothing_in_the_play_step(app):
    gs, g = _base_game(app)
    set_enemy(g, "J", "S")
    set_hand(g, ["5S", "5C", "3D", "3H", "7C", "AS", "9D", "2H"])
    gs.refresh(after_action=False)
    _tap_card(app, gs, "5C")
    shaded = sorted(c for c, v in gs.hand.views.items() if v.shaded)
    assert gs.hand.selected == ["5C"] and shaded == ["2H", "3D", "3H", "7C", "9D"]
    before = dict(gs.enemy.projection)
    changes = _counting_changes(gs)
    for cid in shaded:                                   # 9D alone is a legal play: it still starts nothing
        _tap_card(app, gs, cid)
        assert gs.hand.selected == ["5C"] and not gs.hand.views[cid].selected and gs.hand.views[cid].shaded
    assert changes == []
    assert gs.enemy.projection["attack"] == before["attack"] == 5 and gs.right_btn.enabled
    assert sorted(c for c, v in gs.hand.views.items() if v.shaded) == shaded
    # a lit card still joins, a selected one still leaves
    _tap_card(app, gs, "5S")
    assert gs.hand.selected == ["5C", "5S"] and gs.enemy.projection["attack"] == 10
    _tap_card(app, gs, "5S")
    _tap_card(app, gs, "5C")
    assert gs.hand.selected == [] and gs.enemy.projection is None
    assert not any(v.shaded for v in gs.hand.views.values())


def test_a_tap_on_a_greyed_card_does_nothing_in_the_kinfolk_flute_decision(app):
    _new_campaign(app, ["Ana", "Ben"])
    app.campaign.relics.append("flute")
    app.start_attempt()
    gs, g = app.current, app.game
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3D", "3H", "7C", "AS"], player=1)
    gs.reveal_hand()
    gs.hand.set_selection(["3C"])
    _tap_button(app, "Play")
    _show_hand(app, gs)
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "flute_add" and g.deciding == 1
    assert gs.shown_player == 1 and gs.right_btn.title == "Add" and not gs.right_btn.enabled
    assert sorted(c for c, v in gs.hand.views.items() if v.shaded) == ["7C", "AS"]
    changes = _counting_changes(gs)
    _tap_card(app, gs, "7C")                              # nothing picked yet: still nothing
    assert gs.hand.selected == [] and not gs.right_btn.enabled and gs.enemy.projection is None
    _tap_card(app, gs, "3D")
    assert gs.hand.selected == ["3D"] and gs.right_btn.enabled
    attack = gs.enemy.projection["attack"]
    del changes[:]
    for cid in ("7C", "AS"):
        _tap_card(app, gs, cid)
        assert gs.hand.selected == ["3D"] and not gs.hand.views[cid].selected and gs.hand.views[cid].shaded
    assert changes == [] and gs.right_btn.enabled and gs.enemy.projection["attack"] == attack == 6
    assert g.decision["kind"] == "flute_add"


# ---------------------------------------------------------------------------- 4. the attack's card
def test_the_attack_card_names_cards_by_rank_with_no_suit_or_class_symbols(app):
    from app.screens import shield_rows
    gs, g = _base_game(app)
    set_enemy(g, "K", "H")
    for ids, suits, value in ((["5S", "5C"], ("S", "C"), 10), (["4S"], ("S",), 4), (["AS", "9S"], ("S",), 10)):
        for c in ids:
            _pull(g, c)
        g.plays.append(Play(player=0, card_ids=list(ids), suits=suits, value=value, jester=False))
    set_hand(g, ["9D", "8C", "7H"])
    gs.refresh(after_action=False)
    assert [r[0] for r in shield_rows(g)] == ["5 + 5", "4", "A + 9"]
    gs.hand.set_selection(["9D"])
    rows, total, texts = _attack_shield(app, gs)
    assert rows == [("5 + 5", "10"), ("4", "4"), ("A + 9", "10")] and total == 24 == g.shield
    labels, drawn = _attack_card(app, gs)
    assert "THIS PLAY" in labels
    _assert_no_symbols(labels + drawn, "base game")
    # a Legacy table: a mage enemy, mages and a corrupted paladin in play
    gs, g = _mission_attempt(app, 3, corrupted=("6S",))
    mage = [c for c in g.cards if g.card(c).suits == ("M",) and g.card(c).rank not in ("J", "Q", "K")][0]
    for ids, suits, value in (([mage], ("M",), g.card(mage).value), (["6S"], ("S",), 6)):
        for c in ids:
            _pull(g, c)
        g.plays.append(Play(player=0, card_ids=list(ids), suits=suits, value=value, jester=False))
    set_hand(g, ["9D", "8C", "7H", "5S"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["5S"])
    labels, drawn = _attack_card(app, gs)
    assert "6" in labels and "THIS PLAY" in labels
    _assert_no_symbols(labels + drawn, "legacy")


def test_a_plain_paladin_against_a_paladin_enemy_is_immune_and_adds_nothing(app):
    from app.screens import shield_rows
    gs, g = _base_game(app)
    set_enemy(g, "J", "S")
    set_hand(g, ["4S", "9D", "8C", "7H"])
    gs.refresh(after_action=False)
    _tap_card(app, gs, "4S")
    _tap_button(app, "Play")
    assert g.phase == PHASE_SUFFER and g.shield == 0 and g.enemy_attack == 10
    assert shield_rows(g) == [("4", 4, False, "immune")]
    rows, total, texts = _attack_shield(app, gs)
    assert rows == [("4 (immune)", "0")] and total == 0 and "You suffer 10" in texts


def test_a_paladin_played_before_the_enemy_turns_immune_is_immune_from_then_on(app):
    """Mission 3: the zone's classes make the enemy immune. A plain paladin counted when it
    was played; once a spade enters the zone it adds nothing, and its row says so. A
    corrupted paladin played after still counts and says why."""
    from app.screens import shield_rows
    gs, g = _mission_attempt(app, 3, corrupted=("6S",))
    set_mission_enemy(g, g.enemy.card_id, hp=100)
    assert "S" not in g.enemy.suits and g.mission_zone == []
    printed = g.enemy.attack
    set_hand(g, ["5S", "9D", "8C", "7H", "6S"])
    set_tavern_top(g, ["9S", "2C", "3C"])                 # the card the turn's end puts in the zone
    gs.refresh(after_action=False)
    _tap_card(app, gs, "5S")
    _tap_button(app, "Play")
    assert g.phase == PHASE_SUFFER and g.shield == 5 and g.enemy_attack == printed - 5
    assert shield_rows(g) == [("5", 5, True, "")]
    rows, total, texts = _attack_shield(app, gs)
    assert rows == [("5", "5")] and total == 5 and "You suffer %d" % (printed - 5) in texts
    _tap_card(app, gs, "9D")
    _tap_button(app, "Discard")
    # the turn ended: the 9♠ went into the zone and the enemy is immune to paladins now
    assert g.phase == PHASE_PLAY and g.mission_zone == ["9S"] and "S" in g.rules.immune_suits(g)
    assert any("immune to Paladins" in line for line in g.log)
    assert g.shield == 0 and g.enemy_attack == printed
    assert shield_rows(g) == [("5", 5, False, "immune")]
    rows, total, texts = _attack_shield(app, gs)
    assert rows == [("5 (immune)", "0")] and total == 0 and "You suffer %d" % printed in texts
    # a corrupted paladin ignores the immunity: it shields its value and says why
    gs.hand.set_selection(["6S"])
    pv = gs.enemy.projection
    assert pv["powers"]["S"].get("shield") == 6 and not pv["powers"]["S"].get("immune")
    assert ("Shield", "+6") in _this_play(app, gs)
    _tap_button(app, "Play")
    assert g.shield == 6 and g.enemy_attack == printed - 6
    assert shield_rows(g) == [("5", 5, False, "immune"), ("6", 6, True, "corrupted")]
    rows, total, texts = _attack_shield(app, gs)
    assert rows == [("5 (immune)", "0"), ("6 (corrupted)", "6")] and total == 6


def test_a_restored_paladin_ignores_the_zones_immunity_and_says_restored(app):
    """Mission 3 with a paladin in the zone: the enemy is immune to paladins. A plain one
    would add nothing; a restored one shields its value, and its row says why."""
    from app.screens import shield_rows
    gs, g = _mission_attempt(app, 3, restored=("6S",))
    set_mission_enemy(g, g.enemy.card_id, hp=100)
    assert g.card("6S").has("restored") and not g.card("6S").has("corrupted")
    printed = g.enemy.attack
    _pull(g, "9S")
    g.mission_zone.append("9S")
    set_hand(g, ["6S", "5S", "9D", "8C"])
    gs.refresh(after_action=False)
    assert "S" in g.rules.immune_suits(g) and "S" not in g.enemy.suits
    assert g.rules.immune(g, "S", [g.card("5S")]) and not g.rules.immune(g, "S", [g.card("6S")])
    _tap_card(app, gs, "6S")
    _tap_button(app, "Play")
    assert g.shield == 6 and g.enemy_attack == printed - 6
    assert shield_rows(g) == [("6", 6, True, "restored")]
    rows, total, _ = _attack_shield(app, gs)
    assert rows == [("6 (restored)", "6")] and total == 6


def test_a_claimed_jester_attacks_paladin_says_jester_and_counts(app):
    from app.screens import shield_rows
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
    gs.hand.set_selection([jester])
    _tap_button(app, "Play")
    _tap_button(app, "Ben (3 cards)")                     # Ben claims it: his attack ignores immunity
    _show_hand(app, gs)
    assert g.extra.get("jester_attack") and g.active == 1
    _tap_card(app, gs, "7S")
    _tap_button(app, "Play")
    assert g.plays[-1].jester and g.shield == 7
    assert shield_rows(g) == [("7", 7, True, "Jester")]
    rows, total, _ = _attack_shield(app, gs)
    assert rows == [("7 (Jester)", "7")] and total == 7


def test_mylas_fixed_immunity_makes_even_a_corrupted_paladin_immune(app):
    from app.screens import shield_rows
    gs, g = _mission_attempt(app, 9, corrupted=("6S",))
    set_mission_enemy(g, "MYLA_BOSS")
    assert g.rules.fixed_immunity(g, "S") and g.card("6S").has("corrupted")
    set_hand(g, ["6S", "9D", "8C", "7H", "10C"])
    gs.refresh(after_action=False)
    _tap_card(app, gs, "6S")
    pv = gs.enemy.projection
    assert pv["powers"]["S"]["immune"] is True
    assert ("Shield", "immune") in _this_play(app, gs)
    _tap_button(app, "Play")
    assert g.shield == 0
    assert shield_rows(g) == [("6", 6, False, "immune")]
    rows, total, _ = _attack_shield(app, gs)
    assert rows == [("6 (immune)", "0")] and total == 0


def test_this_plays_rows_give_the_attack_powers_damage_health_and_what_is_suffered(app):
    from app.screens import forecast_rows
    gs, g = _base_game(app)
    set_enemy(g, "J", "S")
    set_hand(g, ["5S", "5C", "9D", "AS", "4H"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["5S"])
    rows = _this_play(app, gs)
    assert rows == forecast_rows(g, gs.enemy.projection)
    assert rows == [("Attack", "5"), ("Shield", "immune"), ("Damage", "5"), ("Enemy health", "15"),
                    ("You suffer", "10")]
    gs.hand.set_selection(["5C", "5S"])                   # doubled by clubs: exactly 20
    assert _this_play(app, gs) == [("Attack", "10"), ("Double", "×2"), ("Shield", "immune"), ("Damage", "20"),
                                   ("Enemy health", "exact"), ("You suffer", "0")]
    # numbers that hang on a value declared later end with "?"
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
    gs.hand.set_selection(["M25H", "M25S"])
    assert gs.enemy.projection["decision_kind"] == "declare_value"
    rows = dict(_this_play(app, gs))
    assert all(rows[k].endswith("?") for k in ("Attack", "Damage", "Enemy health", "You suffer")), rows
    gs.hand.set_selection(["M25H", "5D"])
    assert not any(v.endswith("?") for _, v in _this_play(app, gs))
    # what is suffered after a heal that reshuffles what feeds the enemy is not known: "?"
    gs, g = _mission_attempt(app, 4)
    set_mission_enemy(g, "LABJD", hp=100)
    set_discard(g, ["2C", "9S", "4D", "7C", "10S", "3D", "6C", "8D", "5S", "2D"])
    set_hand(g, ["8H", "9S"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["8H"])
    assert gs.enemy.projection["uncertain"]
    rows = dict(_this_play(app, gs))
    assert rows["You suffer"] == "?" and rows["Enemy health"] == "92" and rows["Attack"] == "8"
    # a power whose immunity is not known yet, and a fight whose outcome is not known
    pv = {"attack": 6, "damage": 12, "powers": {"C": {"immune": None}, "S": {"immune": True}},
          "defeats": None, "exact": False, "enemy_hp_after": None, "suffer": None, "uncertain": True}
    assert forecast_rows(g, pv) == [("Attack", "6"), ("Double", "?"), ("Shield", "immune"), ("Damage", "12"),
                                    ("Enemy health", "?"), ("You suffer", "?")]


# ---------------------------------------------------------------------------- 5. the test copy's saves
def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def _read(path):
    with open(path) as f:
        return f.read()


def test_the_usual_install_and_unrelated_folders_use_the_usual_saves(tmp_path):
    from app import store
    docs = str(tmp_path)
    usual = os.path.join(docs, "PersonalRegicide-saves")
    assert store.saves_folder(docs, "PersonalRegicide") == usual
    for name in ("Regicide", "Games", "regicide-lab"):
        assert store.saves_folder(docs, name) == usual, name
    assert not os.path.exists(os.path.join(docs, "Regicide-saves"))
    assert store.install_name() == os.path.basename(ROOT)


def test_a_test_copy_starts_from_a_copy_of_the_usual_saves_and_keeps_its_own(tmp_path):
    from app import store
    docs = str(tmp_path)
    usual = os.path.join(docs, "PersonalRegicide-saves")
    _write(os.path.join(usual, "settings.json"), '{"names": ["Usual"]}')
    _write(os.path.join(usual, "campaigns", "solo", "campaign.json"), '{"name": "Solo"}')
    lab = store.saves_folder(docs, "PersonalRegicide-lab")
    assert lab == os.path.join(docs, "PersonalRegicide-lab-saves")
    assert _read(os.path.join(lab, "settings.json")) == '{"names": ["Usual"]}'
    assert _read(os.path.join(lab, "campaigns", "solo", "campaign.json")) == '{"name": "Solo"}'
    # the lab copy plays on: its changes stay, the usual saves never see them
    _write(os.path.join(lab, "settings.json"), '{"names": ["Lab"]}')
    _write(os.path.join(lab, "campaigns", "solo", "attempt.json"), "{}")
    _write(os.path.join(usual, "history.jsonl"), "{}\n")
    assert store.saves_folder(docs, "PersonalRegicide-lab") == lab          # a second run
    assert _read(os.path.join(lab, "settings.json")) == '{"names": ["Lab"]}'
    assert os.path.exists(os.path.join(lab, "campaigns", "solo", "attempt.json"))
    assert not os.path.exists(os.path.join(lab, "history.jsonl"))          # copied once, not kept in step
    assert _read(os.path.join(usual, "settings.json")) == '{"names": ["Usual"]}'
    assert not os.path.exists(os.path.join(usual, "campaigns", "solo", "attempt.json"))
    assert store.saves_folder(docs, "PersonalRegicide") == usual


def _as_pythonista(monkeypatch, tmp_path, install):
    from app import store
    home = tmp_path / "home"
    (home / "Documents").mkdir(parents=True)
    monkeypatch.delenv("REGICIDE_SAVE_DIR", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(store, "_is_pythonista", lambda: True)
    monkeypatch.setattr(store, "install_name", lambda: install)
    return str(home / "Documents")


def test_with_no_usual_saves_the_test_copys_folder_is_made_empty_by_save_dir(tmp_path, monkeypatch):
    from app import store
    docs = _as_pythonista(monkeypatch, tmp_path, "PersonalRegicide-lab")
    lab = os.path.join(docs, "PersonalRegicide-lab-saves")
    assert store.saves_folder(docs, "PersonalRegicide-lab") == lab and not os.path.exists(lab)
    assert store.save_dir() == lab and os.path.isdir(lab) and os.listdir(lab) == []
    assert not os.path.exists(os.path.join(docs, "PersonalRegicide-saves"))


def test_the_test_copy_saves_its_settings_beside_its_own_games_only(tmp_path, monkeypatch):
    from app import store
    docs = _as_pythonista(monkeypatch, tmp_path, "PersonalRegicide-lab")
    usual = os.path.join(docs, "PersonalRegicide-saves")
    _write(os.path.join(usual, "settings.json"), json.dumps({"names": ["Usual"]}))
    assert store.load_settings()["names"] == ["Usual"]                     # copied the first time
    s = store.load_settings()
    s["names"] = ["Lab"]
    store.save_settings(s)
    assert json.loads(_read(os.path.join(usual, "settings.json"))) == {"names": ["Usual"]}
    assert store.load_settings()["names"] == ["Lab"]
    monkeypatch.setattr(store, "install_name", lambda: "PersonalRegicide")
    assert store.save_dir() == usual and store.load_settings()["names"] == ["Usual"]


# ---------------------------------------------------------------------------- 6. main.py drops another copy's modules
def _run_python(code, cwd, *args):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("REGICIDE_SAVE_DIR", None)
    out = subprocess.run([sys.executable, "-c", code] + list(args), cwd=str(cwd), env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


PURGE_KEEPS = r'''
import json, os, runpy, sys, types
root = sys.argv[1]
sys.path.insert(0, root)
import app.store, regicide.engine          # this copy's own modules
mine = dict((n, id(m)) for n, m in sys.modules.items() if n.split(".")[0] in ("app", "regicide"))

def foreign(name, path):
    m = types.ModuleType(name)
    m.__file__ = path
    sys.modules[name] = m

sibling = root + "-lab"                    # a copy whose folder name starts with this one's
foreign("app.fake_other", os.path.join(sibling, "app", "fake_other.py"))
foreign("regicide.ghost", os.path.join(os.sep + "elsewhere", "regicide", "ghost.py"))
foreign("fakeui.ghost", os.path.join(sibling, "tools", "fakeui", "ghost.py"))
foreign("appliance", os.path.join(sibling, "appliance.py"))          # not one of the app's packages
foreign("regicide_notes", os.path.join(sibling, "regicide_notes.py"))
runpy.run_path(os.path.join(root, "app", "main.py"), run_name="purge_check")
print(json.dumps({
    "gone": [n for n in ("app.fake_other", "regicide.ghost", "fakeui.ghost") if n not in sys.modules],
    "kept_other": [n for n in ("appliance", "regicide_notes") if n in sys.modules],
    "mine_kept": all(n in sys.modules and id(sys.modules[n]) == i for n, i in mine.items()),
    "mine": sorted(mine),
    "first_app": next(os.path.abspath(p or ".") for p in sys.path if os.path.isdir(os.path.join(p or ".", "app"))),
    "ui": os.path.abspath(sys.modules["ui"].__file__),
}))
'''

PURGE_REPLACES = r'''
import json, os, runpy, sys
root, other, root_on_path = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
if root_on_path:
    sys.path.insert(0, root)               # this copy ran earlier in the same Python, then the other
sys.path.insert(0, other)
import app.screens, regicide               # the other copy, run first in the same Python
before = [os.path.abspath(sys.modules[n].__file__) for n in ("app", "app.screens", "regicide")]
runpy.run_path(os.path.join(root, "app", "main.py"), run_name="purge_check")
left = [n for n in ("app", "app.screens", "regicide") if n in sys.modules]
import app.screens as screens
import regicide.engine as engine
first_app = next(os.path.abspath(p or ".") for p in sys.path if os.path.isdir(os.path.join(p or ".", "app")))
print(json.dumps({"before": before, "left": left, "first_app": first_app,
                  "screens": os.path.abspath(screens.__file__), "engine": os.path.abspath(engine.__file__),
                  "has_app": hasattr(screens, "App")}))
'''


def test_main_drops_modules_another_copy_left_loaded_and_keeps_its_own(tmp_path):
    out = _run_python(PURGE_KEEPS, tmp_path, ROOT)
    assert out["gone"] == ["app.fake_other", "regicide.ghost", "fakeui.ghost"]
    assert out["kept_other"] == ["appliance", "regicide_notes"]
    assert out["mine_kept"] and "app.store" in out["mine"] and "regicide.engine" in out["mine"]
    assert out["first_app"] == ROOT                         # this copy's packages are found first
    assert out["ui"].startswith(os.path.join(ROOT, "tools") + os.sep)


@pytest.mark.parametrize("root_on_path", [False, True])
def test_main_replaces_another_copys_app_with_its_own(tmp_path, root_on_path):
    other = tmp_path / "PersonalRegicide"
    for rel, text in (("app/__init__.py", ""), ("app/screens.py", "COPY = 'other'\n"),
                      ("regicide/__init__.py", "COPY = 'other'\n")):
        _write(str(other / rel), text)
    out = _run_python(PURGE_REPLACES, tmp_path, ROOT, str(other), "1" if root_on_path else "0")
    assert all(p.startswith(str(other) + os.sep) for p in out["before"])
    assert out["left"] == []
    assert out["first_app"] == ROOT
    assert out["screens"] == os.path.join(ROOT, "app", "screens.py") and out["has_app"]
    assert out["engine"] == os.path.join(ROOT, "regicide", "engine.py")
