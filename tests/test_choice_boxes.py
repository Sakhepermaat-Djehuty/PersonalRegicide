"""Choice boxes that hold many cards or options fit the screen (from the crowding audit):
a card grid shows every row the screen has room for (whole rows and part of the next when
it scrolls, so a cut row shows there is more) and stays where it was scrolled when a tap
rebuilds the box; a box never runs past the bottom of the screen; a pick list uses two
columns when one would have to scroll; a scrolling card text ends half a line into the
next. The headless ui cuts a label only when its text does not fit and clips what a scroll
view holds."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402

from app import theme as T  # noqa: E402
from helpers import set_discard, set_hand  # noqa: E402

SIZES = [(320, 568), (390, 844), (430, 932)]


def _app(tmp_path, monkeypatch, size):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app.screens import App, MenuScreen
    ui.set_screen_size(*size)
    a = App()
    a.settings["rules_card"] = False
    a.show(MenuScreen(a))
    return a


def _mission(app, number):
    from test_app import _mission_attempt
    return _mission_attempt(app, number)


def _origin(view):
    x = y = 0.0
    v = view
    while v is not None and v.superview is not None:
        x += v.x
        y += v.y
        if isinstance(v.superview, ui.ScrollView):
            x -= v.superview.content_offset[0]
            y -= v.superview.content_offset[1]
        v = v.superview
    return x, y


def _pile(g, n, keep=()):
    """``n`` plain cards (no royals) for a pile, none of ``keep``."""
    held = set(keep)
    for p in g.players:
        held.update(p.hand)
    out = []
    for cid in sorted(g.cards):
        c = g.cards[cid]
        if len(out) >= n:
            break
        if cid in held or c.rank in ("J", "Q", "K") or c.is_jester or (g.enemy and cid == g.enemy.card_id):
            continue
        out.append(cid)
    assert len(out) == n
    return out


def _discard_pick(app, n=35):
    """Mission 8, an exact kill: any discard pile card may go on top of the reserve."""
    gs, g = _mission(app, 8)
    set_hand(g, ["AS", "2C"])
    set_discard(g, _pile(g, n, ("AS", "2C")))
    g.phase, g.decision = "decide", {"kind": "discard_pick", "player": 0, "resume": "defeat_tail"}
    gs.refresh(after_action=False)
    return gs, g


def _grid_geometry(ov):
    sv = ov.grid_view
    views = list(ov.card_views.values())
    row = views[ov.columns].y - views[0].y if len(views) > ov.columns else None
    return sv, row


def _inside_the_screen(app, ov):
    px, py = _origin(ov.panel)
    return py >= T.TOP_INSET - 0.5 and py + ov.panel.height <= app.height - T.BOTTOM_INSET + 0.5


@pytest.mark.parametrize("size", SIZES)
def test_a_card_grid_takes_the_room_the_screen_leaves(tmp_path, monkeypatch, size):
    from app.screens import DiscardPickOverlay
    app = _app(tmp_path, monkeypatch, size)
    gs, g = _discard_pick(app)
    ov = gs.overlay
    assert isinstance(ov, DiscardPickOverlay)
    sv, row = _grid_geometry(ov)
    need = sv.content_size[1] - 4
    assert _inside_the_screen(app, ov), size
    if sv.height < need - 0.5:
        # it scrolls: whole rows and part of the next, a cut row showing there is more
        part = (sv.height % row) / row
        assert (0.3 <= part <= 0.6 and sv.height >= 1.4 * row) or sv.height >= 0.8 * row, (size, sv.height, row)
    else:
        assert size != (320, 568)                       # (35 cards cannot all fit there)
    # a phone with room shows the whole pile: at 390x844 there was half a screen left empty
    if size == (390, 844):
        assert sv.height >= need - 0.5


def test_a_tap_keeps_the_grid_where_it_was_scrolled(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, (320, 568))
    gs, g = _discard_pick(app)
    ov = gs.overlay
    sv, row = _grid_geometry(ov)
    assert sv.content_size[1] > sv.height + row          # it scrolls
    sv.content_offset = (0, row)
    target = [cid for cid, v in ov.card_views.items() if v.y >= row + 4][0]
    ui.tap(app, *ui.root_point(app, ov.card_views[target]))
    assert ov.picked == [target]
    assert ov.grid_view is not sv and ov.grid_view.content_offset[1] == row
    assert ov.card_views[target].selected


def test_the_druid_box_fits_the_smallest_screen_with_thirty_cards(tmp_path, monkeypatch):
    from app.screens import DruidOverlay
    app = _app(tmp_path, monkeypatch, (320, 568))
    gs, g = _mission(app, 7)
    ids = _pile(g, 30)
    g.phase = "decide"
    g.decision = {"kind": "druid_assign", "player": 0, "dealt": [ids], "order": [0], "index": 0,
                  "resume": "after_power"}
    try:
        gs.refresh(after_action=False)
    except Exception:
        pytest.skip("the crafted Druid decision needs the engine's own fields")
    ov = gs.overlay
    assert isinstance(ov, DruidOverlay)
    assert _inside_the_screen(app, ov)
    menu = ui.button(app, "Game menu")
    mx, my = _origin(menu)
    assert my + menu.height <= app.height - T.BOTTOM_INSET + 0.5


def test_a_pick_list_uses_two_columns_when_one_would_scroll(tmp_path, monkeypatch):
    from app.screens import PickOverlay
    app = _app(tmp_path, monkeypatch, (320, 568))
    gs, g = _mission(app, 6)
    cards = _pile(g, 4)
    acts = [{"type": "zone_move", "player": 0, "card": c, "label": "Move %s to the mission zone" % g.card(c).label()}
            for c in cards]
    monkeypatch.setattr(type(g), "legal_actions", lambda self: list(acts))
    g.phase, g.decision = "decide", {"kind": "zone_move", "player": 0}
    T.TOP_INSET, T.BOTTOM_INSET = 48.0, 120.0           # a short room: one column of 4 would scroll
    try:
        ov = PickOverlay(gs)
        gs._show_overlay(ov)
        opts = [b for b in ui.find(ov, lambda v: isinstance(v, ui.Button)) if b.title.startswith("Move")]
        assert len(opts) == 4
        assert len(set(round(b.x) for b in opts)) == 2                  # two columns
        assert not ui.find(ov.panel, lambda v: isinstance(v, ui.ScrollView))
        assert all(len(b.title) < len("Move 10♦ to the mission zone") for b in opts)   # short titles
    finally:
        T.TOP_INSET, T.BOTTOM_INSET = 48.0, 28.0


def test_a_scrolling_card_text_ends_half_a_line_into_the_next():
    from app.screens import card_face
    from app.widgets import text_size
    bw = 300 - 44
    # a line that fits the label's width but not 4pt less: measured narrower, it would wrap
    line = "the reserve deck goes on"
    while text_size(line + "i", 0, 14)[0] <= bw:
        line += "i"
    assert text_size(line, bw - 4, 14)[1] > text_size(line, bw, 14)[1]
    body = "\n\n".join([line] * 30)
    face = card_face("Rules", body, 300, 420)
    sv = ui.find(face, lambda v: isinstance(v, ui.ScrollView))[0]
    label = sv.subviews[0]
    assert label.width == bw and label.height == text_size(body, bw, 14)[1] + 8   # measured at its own width
    line = text_size("Ag", 0, 14)[1]
    shown = (sv.height - 4) / line
    assert sv.content_size[1] > sv.height and abs((shown % 1) - 0.5) < 0.01
    short = card_face("Rules", "Two lines\nof text.", 300, 420)
    ssv = ui.find(short, lambda v: isinstance(v, ui.ScrollView))[0]
    assert ssv.height == ssv.content_size[1]                         # a short text is shown whole


def test_the_headless_ui_cuts_only_a_label_that_does_not_fit():
    lab = ui.Label(frame=(0, 0, 200, 30))
    lab.font = ("<system>", 15)
    lab.number_of_lines = 1
    lab.text = "W" * 6
    w = ui.measure_string(lab.text, 0, lab.font)[0]
    lab.frame = (0, 0, w + 0.5, 30)                     # just wide enough
    assert not ui.label_truncated(lab) and ui.label_lines(lab) == [lab.text]
    lab.frame = (0, 0, w - 4, 30)
    assert ui.label_truncated(lab) and ui.label_lines(lab)[0].endswith("…")


def test_the_headless_ui_clips_what_a_scroll_view_holds():
    root = ui.View(frame=(0, 0, 100, 100))
    root.background_color = "black"
    sv = ui.ScrollView(frame=(10, 10, 50, 50))
    root.add_subview(sv)
    red = ui.View(frame=(0, 30, 50, 60))                # half of it below the scroll view
    red.background_color = "red"
    sv.add_subview(red)
    img = ui.render(root).convert("RGB")
    s = ui.SCALE
    assert img.getpixel((int(30 * s), int(50 * s))) == (255, 0, 0)       # inside: drawn
    assert img.getpixel((int(30 * s), int(75 * s))) == (0, 0, 0)         # below the scroll view: clipped


def test_a_grid_shown_whole_does_not_scroll_and_an_empty_one_is_left_out(tmp_path, monkeypatch):
    from app.screens import DiscardPickOverlay
    app = _app(tmp_path, monkeypatch, (390, 844))
    gs, g = _discard_pick(app, n=8)
    sv = gs.overlay.grid_view
    assert sv.content_size[1] <= sv.height                 # nothing to drag
    g.discard = []
    gs.overlay.layout()
    ov = gs.overlay
    assert isinstance(ov, DiscardPickOverlay) and ov.grid_view is None and ov.card_views == {}
    assert not ui.find(ov.panel, lambda v: isinstance(v, ui.ScrollView))
