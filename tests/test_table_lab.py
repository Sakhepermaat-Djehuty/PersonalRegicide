"""The table's lab layout: the enemy large in the header with its attack and health beside
it, cards greyed when they cannot join the selection, a red edge where a class power
clashes with the enemy's immunity, the solo Kinfolk Flute in the Yield button's place,
the played cards under the hand, and the attack's and the enemy's cards on a tap."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402

from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402
from regicide.engine import PHASE_PLAY, PHASE_SUFFER, Play  # noqa: E402
from helpers import _pull, set_enemy, set_hand, set_mission_enemy  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app.screens import App, MenuScreen
    ui.set_screen_size(390, 844)
    a = App()
    a.settings["rules_card"] = False
    a.show(MenuScreen(a))
    return a


def _texts(view):
    return [v.text for v in ui.find(view, lambda v: isinstance(v, ui.Label))]


def _quick(app):
    """A base game, solo: the enemy is the Jack of Spades."""
    for title in ("Quick play (base Regicide)", "Solo game", "Start"):
        b = ui.button(app, title)
        b.action(b)
    gs, g = app.current, app.game
    set_enemy(g, "J", "S")
    return gs, g


def _flute_mission(app, number=5):
    """A solo Legacy mission with the Kinfolk Flute."""
    app.new_campaign(1, ["Solo"])
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


def test_cards_that_cannot_join_the_selection_are_greyed(app):
    gs, g = _quick(app)
    set_hand(g, ["5S", "5C", "3D", "3H", "7C", "AS", "9D", "2H"])
    gs.refresh(after_action=False)
    assert not any(v.shaded for v in gs.hand.views.values())      # nothing selected: all lit
    gs.hand.set_selection(["5C"])
    lit = sorted(c for c, v in gs.hand.views.items() if not v.shaded)
    assert lit == ["5C", "5S", "AS"]                               # a pair of fives or the companion
    gs.hand.set_selection(["5C", "5S"])
    assert [c for c, v in gs.hand.views.items() if not v.shaded] == ["5S", "5C"]
    # a tap on a greyed card does not join it; a card playable alone starts a new selection
    gs.hand._tapped(gs.hand.views["9D"])
    assert gs.hand.selected == ["9D"]
    lit = sorted(c for c, v in gs.hand.views.items() if not v.shaded)
    assert lit == ["9D", "AS"]
    # the message stays quiet while cards are selected; the forecast is on the attack's card
    assert gs.message.text == "" and "damage" in gs.forecast


def test_a_clash_with_the_enemys_immunity_puts_a_red_edge_on_the_card_and_the_enemy(app):
    gs, g = _quick(app)
    set_hand(g, ["5S", "5C", "3D", "3H", "7C", "AS", "9D", "2H"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["5C"])
    assert not gs.enemy.warn and not gs.hand.views["5C"].warn
    gs.hand.set_selection(["5C", "5S"])                 # a spade against the Jack of Spades
    assert gs.hand.warned == {"5S"} and gs.hand.views["5S"].warn and not gs.hand.views["5C"].warn
    assert gs.enemy.warn and gs.enemy.card_view.warn
    assert ui.render(app).size[0] > 0
    gs.hand.set_selection(["5C"])
    assert not gs.enemy.warn and not gs.hand.views["5S"].warn
    # a Jester cancels the immunity: no clash, no icon on the enemy's card
    g.immunity_cancelled = True
    gs.refresh(after_action=False)
    assert gs.enemy.card_view.center_icons == []
    gs.hand.set_selection(["5S"])
    assert not gs.enemy.warn and not gs.hand.warned


def test_the_header_projects_what_the_selection_would_do(app):
    gs, g = _quick(app)
    set_hand(g, ["5C", "5D", "9D", "AS"])
    gs.refresh(after_action=False)
    assert gs.enemy.projection is None
    gs.hand.set_selection(["9D"])
    pv = gs.enemy.projection
    assert pv["enemy_hp_after"] == 11 and not pv["defeats"]
    gs.hand.set_selection(["5C", "5D"])                 # 10, doubled by clubs: 20, exactly
    assert gs.enemy.projection["exact"]
    ui.render(app)
    # under a choice box the projection is gone
    gs._table_under_box(None)
    assert gs.enemy.projection is None and gs.forecast == ""


def test_the_attack_and_the_enemy_open_their_cards_on_a_tap(app):
    from app.screens import CardPopup
    gs, g = _quick(app)
    set_hand(g, ["5C", "5D", "9D", "AS"])
    g.plays.append(Play(player=0, card_ids=["4S"], suits=("S",), value=4, jester=False))
    _pull(g, "4S")
    gs.refresh(after_action=False)
    gs.hand.set_selection(["9D"])
    x0, y0 = ui.root_point(app, gs.enemy)
    # left of the enemy's card: the attack, the enemy's side beside the players' shield
    ui.tap(app, gs.enemy.x + 20, y0)
    pop = [v for v in gs.subviews if isinstance(v, CardPopup)]
    assert pop
    texts = _texts(pop[0])
    assert "ENEMY" in texts and "SHIELD" in texts and "You suffer 10" in texts
    assert "4♠ immune" in texts                        # a spade against a spade enemy adds nothing
    assert "With 9♦" in texts and any("9 damage" in t for t in texts)
    pop[0].close()
    # the enemy's card itself: health, immunity, the castle and the selection's forecast
    ui.tap(app, x0, y0)
    pop = [v for v in gs.subviews if isinstance(v, CardPopup)]
    assert pop
    text = " ".join(_texts(pop[0]))
    assert "Health 20 of 20" in text and "Immune to Spades" in text and "more in the castle" in text
    assert "With 9♦" in text
    pop[0].close()


def test_the_solo_flute_takes_the_yield_buttons_place_and_its_cards_wait_for_a_set(app):
    from app.screens import SpecialOverlay
    gs, g = _flute_mission(app)
    set_hand(g, ["5S", "3D", "3H", "7C", "9D", "2H"])
    g.extra["flute"] = ["3C"]
    _pull(g, "3C")
    gs.refresh(after_action=False)
    assert g.phase == PHASE_PLAY and not g.can_yield()
    assert gs.left_btn.title == "Flute" and gs.left_btn.enabled and gs.special_btn.hidden
    # the flute's 3 is greyed until a 3 from the hand starts a kinfolk set
    assert gs.hand.views["3C"].shaded
    gs.hand._tapped(gs.hand.views["3C"])
    assert gs.hand.selected == []
    gs.hand.set_selection(["3D"])
    assert not gs.hand.views["3C"].shaded
    gs.hand.set_selection([])
    gs._left(gs.left_btn)
    assert isinstance(gs.overlay, SpecialOverlay)


def test_suffering_shows_the_tally_and_greys_the_rest_once_one_at_a_time_is_covered(app):
    gs, g = _flute_mission(app, 4)
    set_mission_enemy(g, "LABJD", hp=30)
    set_hand(g, ["3S", "AS", "9C", "10C", "8S"])
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3S"])
    gs._right(None)
    assert g.phase == PHASE_SUFFER and g.rules.sequential_discard(g)
    need = g.pending_damage
    assert gs.right_btn.title == "Discard 0/%d" % need and gs.enemy.paying == (0, need)
    assert need == 7                                                        # 10 less the 3 shield
    gs.hand._tapped(gs.hand.views["AS"])
    assert gs.right_btn.title == "Discard 1/7" and not gs.right_btn.enabled and gs.enemy.paying == (1, 7)
    gs.hand._tapped(gs.hand.views["9C"])
    assert gs.right_btn.title == "Discard 10/7" and gs.right_btn.enabled
    assert gs.hand.views["10C"].shaded and gs.hand.views["8S"].shaded      # covered: nothing more
    gs.hand._tapped(gs.hand.views["10C"])
    assert gs.hand.selected == ["AS", "9C"]
    gs.hand._tapped(gs.hand.views["9C"])                                    # a selected card still leaves
    assert gs.hand.selected == ["AS"] and not gs.hand.views["10C"].shaded
    assert ui.render(app).size[0] > 0


@pytest.mark.parametrize("size", [(390, 844), (375, 667), (320, 568)])
def test_the_played_cards_sit_under_the_hand_and_everything_fits(app, size):
    w, h = size
    ui.set_screen_size(w, h)
    gs, g = _flute_mission(app)
    app.frame = (0, 0, w, h)
    gs.frame = (0, 0, w, h)
    gs.layout()
    gs.refresh(after_action=False)
    hand, strip, bar = gs.hand, gs.strip, gs.left_btn
    assert hand.y + hand.height <= strip.y <= strip.y + strip.height <= bar.y
    assert gs.enemy.y + gs.enemy.height <= gs.message.y <= hand.y
    for v in hand.views.values():
        assert v.y >= 0 and v.y + v.height <= hand.height and v.width >= 40
    if not gs.zone.hidden:
        if h < 760:
            assert gs.zone.y == strip.y                 # a short screen: side by side
            assert gs.zone.x + gs.zone.width <= strip.x
        else:
            assert gs.zone.y + gs.zone.height <= gs.message.y
    # the setting puts them back above the hand
    app.settings["played_below"] = False
    gs.layout()
    assert strip.y + strip.height <= hand.y
    assert ui.render(app).size[0] > 0
