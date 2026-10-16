"""The owner's quality-of-life changes to the choice boxes: the Azure Emblem's keep is a grid
of cards (tap one, then Keep) instead of a button per card, and stays inside the screen with
a dozen revealed cards; the "What order?" box offers "Random order" while no card is tapped."""
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
    _tap_button(app, "Add 7♣")
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
