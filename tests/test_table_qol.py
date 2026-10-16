"""The owner's quality-of-life changes to the choice boxes: the Azure Emblem's keep, the
Mage's look and the Reaver's pick are grids of cards (tap one, then the button that names
it) instead of a strip and a button per card, and stay inside the screen with ten or twenty
revealed cards; the "What order?" box offers "Random order" while no card is tapped; the
table's small targets (Menu, a full row's card back, the piles viewer's tabs) are full size."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402

from app import theme as T  # noqa: E402
from helpers import set_enemy, set_hand, set_tavern_top  # noqa: E402

TWELVE = ["7C", "AD", "2S", "5C", "3H", "4D", "6S", "8H", "9C", "2D", "3S", "6H"]


def _app(tmp_path, monkeypatch, size):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app.screens import App, MenuScreen
    ui.set_screen_size(*size)
    a = App()
    a.settings["rules_card"] = False
    a.show(MenuScreen(a))
    return a


@pytest.fixture
def app(tmp_path, monkeypatch):
    return _app(tmp_path, monkeypatch, (390, 844))


def _tap_button(app, title):
    b = ui.button(app, title)
    assert b.enabled, "button %s disabled" % title
    ui.tap(app, *ui.root_point(app, b))


def _buttons(view):
    return [b for b in ui.find(view, lambda v: isinstance(v, ui.Button) and not v.hidden)]


def _emblem_keep(app, reveal=TWELVE):
    """Solo with the Azure Emblem: a 10 mage and an ace (strength 11) reveal eleven cards,
    7♣ joins the attack, ten are left to keep or discard."""
    from regicide.campaign import missions as M
    from regicide.campaign import party as P
    app.new_campaign(1, ["Solo"])
    for d in M.MAGE_DECK:
        P.add_card(app.campaign.party, dict(d))
    app.campaign.relics.append("emblem")
    app.start_attempt()
    gs, g = app.current, app.game
    set_enemy(g, "K", "H")
    set_hand(g, ["10M", "AS", "9S", "8S"])
    set_tavern_top(g, list(reveal))
    gs.refresh(after_action=False)
    gs.hand.set_selection(["10M", "AS"])
    _tap_button(app, "Play")
    assert g.decision["kind"] == "mage_peek"
    ui.tap(app, *ui.root_point(app, gs.overlay.card_views["7C"]))
    _tap_button(app, "Add 7♣ to the attack")
    assert g.decision["kind"] == "emblem_keep"
    return gs, g


def _inside(view, outer) -> bool:
    x, y = _origin(view)
    ox, oy = _origin(outer)
    return (ox - 0.5 <= x and oy - 0.5 <= y and x + view.width <= ox + outer.width + 0.5
            and y + view.height <= oy + outer.height + 0.5)


def _origin(view):
    """Root coordinates of a view's top-left corner."""
    x, y = 0.0, 0.0
    v = view
    while v is not None and v.superview is not None:
        x += v.x
        y += v.y
        if isinstance(v.superview, ui.ScrollView):
            x -= v.superview.content_offset[0]
            y -= v.superview.content_offset[1]
        v = v.superview
    return x, y


def test_the_emblem_keep_is_a_grid_of_cards_tap_one_then_keep(app):
    from app.screens import EmblemKeepOverlay
    from app.widgets import CardStrip, CardView
    gs, g = _emblem_keep(app)
    ov = gs.overlay
    assert isinstance(ov, EmblemKeepOverlay)
    left = list(g.decision["revealed"])
    assert len(left) == 10 and list(ov.card_views) == left                  # as revealed, the top first
    # no strip of overlapping cards, no button per card
    assert not ui.find(ov, lambda v: isinstance(v, CardStrip))
    titles = [b.title for b in _buttons(ov)]
    assert titles[:2] == ["Keep a card on top of the reserve", "Discard them all"]
    assert not any(t.startswith("Keep ") and t != "Keep a card on top of the reserve" for t in titles)
    assert not ui.button(app, "Keep a card on top of the reserve").enabled
    # the cards do not overlap
    views = [v for v in ui.find(ov, lambda v: isinstance(v, CardView))]
    assert len(views) == 10
    for i, a in enumerate(views):
        for b in views[i + 1:]:
            assert a.x + a.width <= b.x + 0.5 or b.x + b.width <= a.x + 0.5 or \
                a.y + a.height <= b.y + 0.5 or b.y + b.height <= a.y + 0.5
    # tap one: it is selected and the button names it; another tap moves the selection
    ui.tap(app, *ui.root_point(app, ov.card_views["AD"]))
    assert ov.picked == ["AD"] and ui.button(app, "Keep A♦ on top of the reserve").enabled
    ui.tap(app, *ui.root_point(app, ov.card_views["3H"]))
    assert ov.picked == ["3H"] and ov.card_views["3H"].selected and not ov.card_views["AD"].selected
    ui.tap(app, *ui.root_point(app, ov.card_views["3H"]))                  # a second tap takes it back
    assert ov.picked == [] and not ui.button(app, "Keep a card on top of the reserve").enabled
    ui.tap(app, *ui.root_point(app, ov.card_views["3H"]))
    under = g.tavern[0]
    _tap_button(app, "Keep 3♥ on top of the reserve")
    assert g.tavern[:2] == ["3H", under] and gs.overlay is not ov
    assert "Azure Emblem: Solo puts 3♥ back on top of the reserve deck." in "\n".join(g.log)
    assert set(left) - {"3H"} <= set(g.discard)


def test_discard_them_all_still_goes_in_one_tap(app):
    gs, g = _emblem_keep(app)
    left = list(g.decision["revealed"])
    under = g.tavern[0]
    _tap_button(app, "Discard them all")
    assert g.tavern[0] == under and set(left) <= set(g.discard)


@pytest.mark.parametrize("size", [(390, 844), (320, 568), (430, 932)])
def test_the_emblem_box_fits_the_screen_with_ten_cards(tmp_path, monkeypatch, size):
    app = _app(tmp_path, monkeypatch, size)
    gs, g = _emblem_keep(app)
    ov = gs.overlay
    panel = ov.panel
    px, py = _origin(panel)
    assert py >= T.TOP_INSET - 0.5 and py + panel.height <= app.height - T.BOTTOM_INSET + 0.5
    for b in _buttons(ov):
        assert _inside(b, panel), (b.title, size)
    # every card can be reached: in view, or in a scroll view that scrolls to it
    from app.widgets import CardView
    for v in ui.find(ov, lambda v: isinstance(v, CardView)):
        sv = v.superview
        assert isinstance(sv, ui.ScrollView) and v.y + v.height <= sv.content_size[1] + 0.5
        assert _inside(sv, panel)
    labels = [lab for lab in ui.find(ov, lambda v: isinstance(v, ui.Label) and not v.hidden)]
    assert not [lab.text for lab in labels if ui.label_truncated(lab)]
    assert ui.render(app).size[0] > 0


def _order_box(app):
    """Mission 4: a 3 mage reveals 4♣, 10♥ and 2♦; 4♣ joins the attack and the other two
    go to the discard pile, whose top adds to the enemy: "What order?"."""
    from test_app import _mage_leftovers_to_order
    return _mage_leftovers_to_order(app)


def test_the_order_box_offers_a_random_order_until_a_card_is_tapped(app, monkeypatch):
    from app import screens
    from app.screens import OrderOverlay
    gs, g = _order_box(app)
    ov = gs.overlay
    assert isinstance(ov, OrderOverlay)
    titles = [b.title for b in _buttons(ov)]
    assert "Random order" in titles and not any(t.startswith("Confirm the order") for t in titles)
    assert ui.button(app, "Random order").enabled
    # tapping a card turns it into the confirm button; untapping brings it back
    ui.tap(app, *ui.root_point(app, ov.card_views["2D"]))
    titles = [b.title for b in _buttons(ov)]
    assert "Random order" not in titles and not ui.button(app, "Confirm the order (1 of 2)").enabled
    ui.tap(app, *ui.root_point(app, ov.card_views["2D"]))
    assert ui.button(app, "Random order").enabled
    # a random order is any order of the cards (the box's own shuffle, not the game's)
    asked = []

    def sample(population, k):
        asked.append(list(population))
        return list(reversed(population))
    monkeypatch.setattr(screens.random, "sample", sample)
    rng_before = g.rng.getstate()
    ids = ov.card_ids(g, g.decision)
    _tap_button(app, "Random order")
    assert asked == [ids] and g.decision is None and not isinstance(gs.overlay, OrderOverlay)
    assert g.discard[:2] == list(ids)                     # reversed: the first id ends on top
    assert g.rng.getstate() == rng_before                 # the game's own randomness is untouched


def test_a_random_order_is_a_real_shuffle(app):
    gs, g = _order_box(app)
    ids = gs.overlay.card_ids(g, g.decision)
    _tap_button(app, "Random order")
    assert sorted(g.discard[:2]) == sorted(ids) and g.decision is None


def test_an_error_opening_the_attack_card_is_shown_on_the_phone(app, monkeypatch):
    import console
    from app import screens, store
    from app.screens import CardPopup
    app.new_campaign(1, ["Solo"])
    app.start_attempt()
    gs = app.current
    gs.refresh(after_action=False)
    monkeypatch.setattr(store, "_is_pythonista", lambda: True)

    def broken(*a, **k):
        raise ValueError("no attack")
    monkeypatch.setattr(screens, "attack_face", broken)
    del console.history[:]
    gs._show_attack()
    assert ("hud", "Opening the attack failed: ValueError no attack") in console.history
    assert not ui.find(app, lambda v: isinstance(v, CardPopup))


def _mage_look(app, reveal=TWELVE):
    """Solo: a 10 mage and an ace (strength 11) reveal eleven cards."""
    from regicide.campaign import missions as M
    from regicide.campaign import party as P
    app.new_campaign(1, ["Solo"])
    for d in M.MAGE_DECK:
        P.add_card(app.campaign.party, dict(d))
    app.start_attempt()
    gs, g = app.current, app.game
    set_enemy(g, "K", "H")
    set_hand(g, ["10M", "AS", "9S", "8S"])
    set_tavern_top(g, list(reveal))
    gs.refresh(after_action=False)
    gs.hand.set_selection(["10M", "AS"])
    _tap_button(app, "Play")
    assert g.decision["kind"] == "mage_peek"
    return gs, g


def test_the_mage_look_is_a_grid_of_cards_tap_one_then_add(app):
    from app.screens import MagePeekOverlay
    from app.widgets import CardStrip
    gs, g = _mage_look(app)
    ov = gs.overlay
    assert isinstance(ov, MagePeekOverlay) and not ui.find(ov, lambda v: isinstance(v, CardStrip))
    assert list(ov.card_views) == TWELVE[:11]                                # as revealed, the top first
    adds = [b for b in _buttons(ov) if b.title.startswith("Add")]
    assert [b.title for b in adds] == ["Add a card to the attack"] and not adds[0].enabled
    ui.tap(app, *ui.root_point(app, ov.card_views["9C"]))
    assert ui.button(app, "Add 9♣ to the attack").enabled
    ui.tap(app, *ui.root_point(app, ov.card_views["AD"]))                    # the pick moves
    assert ov.picked == ["AD"] and not ov.card_views["9C"].selected
    _tap_button(app, "Add A♦ to the attack")
    assert g.plays[0].card_ids == ["10M", "AS", "AD"]


@pytest.mark.parametrize("size", [(320, 568), (390, 844), (430, 932)])
def test_a_twenty_card_mage_look_fits_every_screen(tmp_path, monkeypatch, size):
    """Ash (the Mage beast) with the 10 mage is a strength 20 look: twenty cards, some that may
    not join (Jesters, corrupted cards: dimmed, not tappable)."""
    from app.screens import MagePeekOverlay
    from app.widgets import CardView
    app = _app(tmp_path, monkeypatch, size)
    gs, g = _mage_look(app)
    plain = [c for c in sorted(g.cards) if g.cards[c].rank in ("2", "3", "4", "5", "6", "7", "8", "9", "10", "A")
             and not g.cards[c].is_jester and c not in ("10M", "AS", "9S", "8S")][:20]
    revealed = plain
    out = (plain[3], plain[9], plain[12])               # (a Jester or corrupted cards: discarded)
    eligible = [c for c in revealed if c not in out]
    g.decision = dict(g.decision, revealed=revealed, eligible=eligible, strength=20)
    gs.refresh(after_action=False)
    ov = gs.overlay
    assert isinstance(ov, MagePeekOverlay) and len(ov.card_views) == 20
    px, py = _origin(ov.panel)
    assert py >= T.TOP_INSET - 0.5 and py + ov.panel.height <= app.height - T.BOTTOM_INSET + 0.5, size
    views = [v for v in ui.find(ov, lambda v: isinstance(v, CardView))]
    for i, a in enumerate(views):                                           # no card covers another
        for b in views[i + 1:]:
            assert a.x + a.width <= b.x + 0.5 or b.x + b.width <= a.x + 0.5 or \
                a.y + a.height <= b.y + 0.5 or b.y + b.height <= a.y + 0.5
    for cid in out:
        assert ov.card_views[cid].dimmed and not ov.card_views[cid].touch_enabled
    assert len([b for b in _buttons(ov) if b.title.startswith("Add")]) == 1
    cut = [lab.text for lab in ui.find(ov, lambda v: isinstance(v, ui.Label) and not v.hidden) if ui.label_truncated(lab)]
    assert not cut, (size, cut)                          # the long title shrinks to fit
    sv = ov.grid_view
    assert sv.height >= min(sv.content_size[1] - 4, 0.8 * views[0].height)


def test_the_table_menu_button_is_a_full_size_target(app):
    app.new_campaign(1, ["Solo"])
    app.start_attempt()
    gs = app.current
    gs.layout()
    b, st = gs.menu_btn, gs.status
    assert b.height >= 36 and abs((b.y + b.height / 2) - (st.y + st.height / 2)) < 0.5


def test_a_small_card_back_takes_taps_across_the_rows_first_44pt():
    from test_table_owner import PLAYS, _bare_strip, _cards
    strip = _bare_strip(260, 34.0 + 11)                 # the smallest screen's row
    strip.set_cards(_cards(PLAYS))
    assert strip.overflows()
    cw, ch = strip.card_size()
    assert cw < 40                                      # the back alone is a small target
    taps = []
    strip.on_more = lambda: taps.append(1)
    strip.touch_ended(ui.Touch((40.0, ch / 2), (40.0, ch / 2), "ended"))
    assert taps == [1]
    far = max(44.0, (cw + strip.slot_x(1)) / 2.0) + 6
    strip.touch_ended(ui.Touch((far, ch / 2), (far, ch / 2), "ended"))
    assert taps == [1]                                  # further along: a face card, nothing


@pytest.mark.parametrize("size", [(320, 568), (390, 844), (430, 932)])
def test_the_piles_viewer_tabs_are_full_size_targets_inside_the_screen(tmp_path, monkeypatch, size):
    from app.screens import PilesOverlay
    app = _app(tmp_path, monkeypatch, size)
    app.new_campaign(1, ["Solo"])
    app.start_attempt()
    gs = app.current
    for pile in ("reserve", "castle", "discard"):
        gs._show_piles(pile)                              # the reserve: about forty cards from the start
        assert isinstance(gs.overlay, PilesOverlay)
        seg = ui.find(gs.overlay, lambda v: isinstance(v, ui.SegmentedControl))[0]
        assert seg.height >= 36
        px, py = _origin(gs.overlay.panel)
        assert py >= T.TOP_INSET - 0.5 and py + gs.overlay.panel.height <= app.height - T.BOTTOM_INSET + 0.5, (size, pile)
        gs._back_to_game()


def test_a_lone_skip_is_the_main_button_and_a_skip_beside_a_pick_is_not(app):
    gs, g = _mage_look(app)
    g.decision = dict(g.decision, eligible=[])           # nothing may join the attack
    gs.refresh(after_action=False)
    assert not [b for b in _buttons(gs.overlay) if b.title.startswith("Add")]
    assert ui.button(app, "Nothing to add").background_color == T.BTN
    ui.tap(app, *ui.root_point(app, ui.button(app, "Nothing to add")))
    assert g.decision is None or g.decision.get("kind") != "mage_peek"


def test_discard_them_all_is_the_second_button_beside_keep(app):
    gs, g = _emblem_keep(app)
    assert ui.button(app, "Discard them all").background_color == T.PANEL_2
