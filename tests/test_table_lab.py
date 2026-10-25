"""The table's lab layout: the enemy large in the header with its attack and health beside
it, cards greyed when they cannot join the selection, a red edge where a class power
clashes with the enemy's immunity, the solo Kinfolk Flute on a button of its own,
the mission zone above the hand and the played cards under it (a full row behind a card
back), and the attack's card on a tap (the enemy's card opens nothing)."""
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
    # a tap on a greyed card does nothing: it neither joins nor starts a new selection
    gs.hand._tapped(gs.hand.views["9D"])
    assert gs.hand.selected == ["5C", "5S"]
    assert [c for c, v in gs.hand.views.items() if not v.shaded] == ["5S", "5C"]
    # what the pair would do is a projection (the header's numbers, the attack's card)
    pv = gs.enemy.projection
    assert pv["attack"] == 10 and pv["damage"] == 20 and pv["exact"]
    # the selected cards still leave on a tap; then a card playable alone lights its companion
    gs.hand._tapped(gs.hand.views["5S"])
    gs.hand._tapped(gs.hand.views["5C"])
    assert gs.hand.selected == [] and gs.enemy.projection is None
    gs.hand._tapped(gs.hand.views["9D"])
    assert gs.hand.selected == ["9D"]
    lit = sorted(c for c, v in gs.hand.views.items() if not v.shaded)
    assert lit == ["9D", "AS"]
    assert gs.enemy.projection["damage"] == 9 and gs.enemy.projection["enemy_hp_after"] == 11


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
    assert gs.enemy.card_view.struck_icons == ["S"]          # shown struck through on its panel
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
    assert "THIS PLAY" in _attack_card_texts(gs)
    # under a choice box the projection is gone, from the header and from the attack's card
    gs._table_under_box(None)
    assert gs.enemy.projection is None and not gs.enemy.warn and gs.enemy.paying is None
    assert "THIS PLAY" not in _attack_card_texts(gs)


def _attack_card_texts(gs):
    """The labels of the attack's card (a tap left of the enemy), closed again."""
    from app.screens import CardPopup
    gs._show_attack()
    pop = [v for v in gs.app.subviews if isinstance(v, CardPopup)]
    assert pop
    texts = _texts(pop[0])
    pop[0].close()
    return texts


def _rows(texts):
    """(name, value) for each name label followed by its value label on a card."""
    return list(zip(texts, texts[1:]))


def test_the_attack_opens_its_card_on_a_tap_and_the_enemy_does_nothing(app):
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
    pop = [v for v in gs.app.subviews if isinstance(v, CardPopup)]
    assert pop
    texts = _texts(pop[0])
    assert "ENEMY" in texts and "SHIELD" in texts and "You suffer 10" in texts
    # a spade against a spade enemy adds nothing; the card is named by its rank alone
    assert ("4 (immune)", "0") in _rows(texts)
    assert not any(sym in t for t in texts for sym in "♠♥♦♣")
    # what the 9 would do, as numbers
    i = texts.index("THIS PLAY")
    assert _rows(texts[i + 1:])[::2] == [("Attack", "9"), ("Draw", "5"), ("Damage", "9"), ("Enemy health", "11"),
                                         ("You suffer", "10")]
    pop[0].close()
    # the enemy's card itself opens nothing (no running text on the table): its health and
    # immunity are on the header
    ui.tap(app, x0, y0)
    assert not [v for v in gs.app.subviews if isinstance(v, CardPopup)] and gs.overlay is None
    drawn = _drawn_text(gs.enemy)
    assert "20" in drawn and "of 20" in drawn and gs.enemy.card_view.center_icons == ["S"]
    assert gs.pile_views["castle"].count == len(g.castle) == 11


def test_the_solo_flute_has_its_own_button_beside_yield_and_its_cards_wait_for_a_set(app):
    from app.screens import SpecialOverlay
    gs, g = _flute_mission(app)
    set_hand(g, ["5S", "3D", "3H", "7C", "9D", "2H"])
    g.extra["flute"] = ["3C"]
    _pull(g, "3C")
    gs.refresh(after_action=False)
    assert g.phase == PHASE_PLAY and g.can_yield()
    assert gs.left_btn.title == "Yield" and gs.left_btn.enabled
    assert not gs.special_btn.hidden and gs.special_btn.title == "Flute" and gs.special_btn.enabled
    # the flute's 3 is greyed until a 3 from the hand starts a kinfolk set
    assert gs.hand.views["3C"].shaded
    gs.hand._tapped(gs.hand.views["3C"])
    assert gs.hand.selected == []
    gs.hand.set_selection(["3D"])
    assert not gs.hand.views["3C"].shaded
    gs.hand.set_selection([])
    gs._special(gs.special_btn)
    assert isinstance(gs.overlay, SpecialOverlay)
    gs._hide_overlay()
    # a yield leaves the Flute where it was, while suffering and after; only Yield greys
    # (a solo player may not yield twice running)
    gs._left(gs.left_btn)
    assert g.phase == PHASE_SUFFER and gs.special_btn.title == "Flute" and not gs.special_btn.hidden
    gs._left(gs.left_btn)                                   # Suggest a discard
    gs._right(gs.right_btn)
    assert g.phase == PHASE_PLAY and not g.can_yield()
    assert gs.left_btn.title == "Yield" and not gs.left_btn.enabled
    assert not gs.special_btn.hidden and gs.special_btn.title == "Flute"


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


def _flute_table(app, size):
    """Mission 5 with the Kinfolk Flute, laid out on a phone of this size."""
    w, h = size
    ui.set_screen_size(w, h)
    gs, g = _flute_mission(app)
    app.frame = (0, 0, w, h)
    gs.frame = (0, 0, w, h)
    gs.layout()
    gs.refresh(after_action=False)
    return gs, g


@pytest.mark.parametrize("size", [(390, 844), (375, 667), (320, 568)])
def test_the_played_cards_sit_under_the_hand_and_everything_fits(app, size):
    w, h = size
    gs, g = _flute_table(app, size)
    hand, strip, bar = gs.hand, gs.strip, gs.left_btn
    assert hand.y + hand.height <= strip.y <= strip.y + strip.height <= bar.y
    piles = [gs.pile_views[k] for k in ("castle", "reserve", "discard", "banished")]
    for p in piles:                                     # the piles in a row between the enemy and the hand
        assert gs.enemy.y + gs.enemy.height <= p.y and p.y + p.height <= hand.y and p.card_rect()[2] >= (32 if h < 600 else 40)
    assert [p.x for p in piles] == sorted(p.x for p in piles) and piles[-1].x + piles[-1].width <= w
    for v in hand.views.values():
        assert v.y >= 0 and v.y + v.height <= hand.height
    # the mission zone above the hand on every screen, a row of its own as wide as the played row
    assert not gs.zone.hidden
    assert gs.pile_views["castle"].y + gs.pile_views["castle"].height <= gs.zone.y
    assert gs.zone.y + gs.zone.height <= hand.y and gs.zone.x == strip.x and gs.zone.width >= strip.width
    # the old 'played cards above the hand' setting is gone: the played row stays under it
    app.settings["played_below"] = False
    gs.layout()
    assert hand.y + hand.height <= strip.y <= strip.y + strip.height <= bar.y
    assert gs.zone.y + gs.zone.height <= hand.y
    assert ui.render(app).size[0] > 0


@pytest.mark.parametrize("size", [(390, 844), (375, 667), (320, 568)])
def test_the_hands_cards_stay_40pt_wide_beside_both_named_rows(app, size):
    gs, g = _flute_table(app, size)
    assert not gs.zone.hidden and gs.zone.label and gs.strip.label and gs.hand.views
    assert min(v.width for v in gs.hand.views.values()) >= 40


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


def test_a_set_made_only_of_flute_cards_can_be_tapped_even_with_an_empty_hand(app):
    gs, g = _flute_mission(app)
    set_hand(g, ["9D", "7C", "8S"])
    for c in ("3C", "3H"):
        _pull(g, c)
    g.extra["flute"] = ["3C", "3H"]
    gs.refresh(after_action=False)
    assert ["3C", "3H"] in g.legal_plays()
    assert not gs.hand.views["3C"].shaded
    gs.hand._tapped(gs.hand.views["3C"])
    assert gs.hand.selected == ["3C"] and not gs.hand.views["3H"].shaded
    gs.hand._tapped(gs.hand.views["3H"])
    assert gs.hand.selected == ["3C", "3H"] and gs.right_btn.enabled
    # with no hand card left the flute pair is the only play: it must stay reachable
    set_hand(g, [])
    g.solo_jesters = 0
    gs.refresh(after_action=False)
    gs.hand._tapped(gs.hand.views["3C"])
    gs.hand._tapped(gs.hand.views["3H"])
    assert gs.hand.selected == ["3C", "3H"] and gs.right_btn.enabled


def test_a_guardian_play_shows_nothing_left_to_suffer(app):
    from app.screens import describe_preview, forecast_rows
    app.new_campaign(1, ["Solo"])
    camp = app.campaign
    camp.mission, camp.completed = 6, list(range(1, 6))
    P.add_card(camp.party, dict(M.GORAN))
    camp.flags["beasts"] = True
    for d in list(M.MAGE_DECK) + list(M.GUARDIANS):
        if P.find(camp.party, str(d["id"])) is None:
            P.add_card(camp.party, dict(d))
    app.save_campaign()
    app.start_attempt()
    g, gs = app.game, app.current
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    set_hand(g, ["3G", "9D", "4C"])
    g.mission_zone[:] = []
    gs.refresh(after_action=False)
    gs.hand.set_selection(["3G"])
    pv = gs.enemy.projection
    assert pv["phase_after"] == PHASE_PLAY and g.enemy_attack > 0
    assert "→ 0" in _drawn_text(gs.enemy)
    assert "nothing to suffer" in describe_preview(g, pv) and pv["suffer"] == 0
    assert ("You suffer", "0") in forecast_rows(g, pv)
    gs.hand.set_selection(["9D"])                        # an ordinary play: the attack still comes
    pv = gs.enemy.projection
    assert pv["suffer"] == g.enemy_attack > 0 and pv["defeats"] is False
    assert ("You suffer", "%d" % g.enemy_attack) in forecast_rows(g, pv)


def test_a_short_screen_keeps_the_zone_above_the_hand_and_a_full_row_behind_a_card_back(app):
    from app.screens import MISSION_ZONE, CardListOverlay, CardPopup
    for w, h in ((375, 667), (320, 568)):
        ui.set_screen_size(w, h)
        gs, g = _flute_mission(app, 7)
        app.frame = gs.frame = (0, 0, w, h)
        gs.layout()
        gs.refresh(after_action=False)
        zone, strip, hand = gs.zone, gs.strip, gs.hand
        # no shared row any more: the zone above the hand, the played cards under it
        assert not zone.hidden and zone.x == strip.x and zone.width >= strip.width
        assert zone.y + zone.height <= hand.y and hand.y + hand.height <= strip.y
        # the hand never runs under the rows or the buttons, its cards stay readable
        for v in hand.views.values():
            assert v.y + v.height <= hand.height + 0.5 and v.width >= 32
        # mission 7's pilgrim, face up, oldest first; a row that is not full opens nothing
        assert [c.id for c in zone.cards] == g.mission_zone and len(g.mission_zone) == 1
        assert not zone.overflows() and [c.id for c in zone.shown()] == g.mission_zone
        zx, zy = ui.root_point(app, zone)
        ui.tap(app, zx - zone.width / 2.0 + zone.card_size()[0] / 2.0, zy)     # where a full row's back lies
        assert gs.overlay is None and not [v for v in gs.app.subviews if isinstance(v, CardPopup)]
        # a full row: a card back with the total first, then the newest cards
        extra = [c for c in g.tavern if c not in g.mission_zone][:zone.capacity()]
        for c in extra:
            _pull(g, c)
        g.mission_zone.extend(extra)
        gs.refresh(after_action=False)
        ids = list(g.mission_zone)
        assert [c.id for c in zone.cards] == ids and len(ids) == zone.capacity() + 1 and zone.overflows()
        assert [c.id for c in zone.shown()] == ids[-(zone.capacity() - 1):]
        cw = zone.card_size()[0]
        x0 = zone.subviews[0].x                       # the first face card: slot 1, the back's slot left free
        assert round(x0, 3) == round(zone.slot_x(1), 3) and x0 >= cw + zone.GAP - 0.001
        assert "%d" % len(ids) in _drawn_text(zone)
        # one more card pushes the oldest shown out of sight
        newest = [c for c in g.tavern if c not in g.mission_zone][0]
        _pull(g, newest)
        g.mission_zone.append(newest)
        gs.refresh(after_action=False)
        assert zone.shown()[-1].id == newest and ids[-(zone.capacity() - 1)] not in [c.id for c in zone.shown()]
        # a tap on the back lists every card in the zone, oldest first; Back returns
        zx, zy = ui.root_point(app, zone)
        ui.tap(app, zx - zone.width / 2.0 + cw / 2.0, zy)
        ov = gs.overlay
        assert isinstance(ov, CardListOverlay) and list(ov.card_views) == g.mission_zone
        assert "%s · %d" % (MISSION_ZONE, len(g.mission_zone)) in _texts(ov)
        ui.button(ov, "Back").action(None)
        assert gs.overlay is None


def test_the_attack_cards_rows_show_a_question_mark_for_an_amount_that_hangs_on_a_hidden_card():
    """The forecast marks a power whose amount differs between its copies (``uncertain``):
    the attack card shows "?" for it rather than the first copy's number."""
    from app.screens import forecast_rows
    from test_m11_corrupt_mage_mother import _owner_turn10
    from helpers import set_hand
    c, g = _owner_turn10()
    for x in [x for x in g.tavern if x not in ("9H", "7M", "8M")]:
        g.tavern.remove(x)
        g.discard.append(x)
    set_hand(g, ["AM", "3D", "2S", "9T"])
    g.extra["flute"] = []
    pv = g.preview_play(["AM", "3D"])
    assert pv["powers"]["D"].get("uncertain")
    rows = dict(forecast_rows(g, pv))
    assert rows["Draw"] == "?", rows


def test_the_flute_box_is_the_hand_as_a_grid_and_a_two_five_gets_a_button_per_value(app):
    """The Kinfolk Flute's box: the hand as cards, those that may go on the flute bright; the
    flute's cards in a row above; a tap picks one and Store acts; a 2/5 on an empty flute
    may go on as a 2 or as a 5."""
    from app.screens import SpecialOverlay
    from app.widgets import CardStrip
    from regicide.cards import make_card
    gs, g = _flute_mission(app)
    g.cards["M25H"] = make_card("2", "H", id="M25H", name="2/5", flags=("twofive",))
    set_hand(g, ["M25H", "3D", "9D", "7C"])
    gs.refresh(after_action=False)
    gs._special(gs.special_btn)
    ov = gs.overlay
    assert isinstance(ov, SpecialOverlay) and list(ov.card_views) == ["M25H", "3D", "9D", "7C"]
    assert [c for c, v in ov.card_views.items() if v.dimmed] == ["9D", "7C"]
    assert not ui.find(ov, lambda v: isinstance(v, CardStrip))           # nothing on the flute yet
    choose = ui.find(ov, lambda v: isinstance(v, ui.Button) and v.title == "Choose a card to store")
    assert choose and not choose[0].enabled
    ui.tap(app, *ui.root_point(app, ov.card_views["M25H"]))
    stores = [b.title for b in ui.find(ov, lambda v: isinstance(v, ui.Button) and v.title.startswith("Store"))]
    assert stores == ["Store 2/5♥ on the Kinfolk Flute as a 2", "Store 2/5♥ on the Kinfolk Flute as a 5"]
    ui.tap(app, *ui.root_point(app, ov.card_views["3D"]))               # the pick moves
    stores = [b.title for b in ui.find(ov, lambda v: isinstance(v, ui.Button) and v.title.startswith("Store"))]
    assert stores == ["Store 3♦ on the Kinfolk Flute"]
    ui.tap(app, *ui.root_point(app, ui.button(app, stores[0])))
    assert g.extra["flute"] == ["3D"] and gs.overlay is None
    # next turn the flute's cards show above the grid and only 3s may join them
    g.extra["flute_turn"] = None
    set_hand(g, ["M25H", "3H", "4D"])
    gs.refresh(after_action=False)
    gs._special(gs.special_btn)
    ov = gs.overlay
    strips = ui.find(ov, lambda v: isinstance(v, CardStrip))
    assert strips and [c.id for c in strips[0].cards] == ["3D"]
    assert [c for c, v in ov.card_views.items() if not v.dimmed] == ["3H"]
    assert any("another 3" in t for t in [v.text for v in ui.find(ov, lambda v: isinstance(v, ui.Label))])
    assert ui.render(app).size[0] > 0


def test_a_zone_card_box_shows_the_whole_zone_and_picks_before_it_acts(app):
    """A mission zone choice as a card grid: the zone whole, cards that may not be chosen
    dimmed, nothing picked while there is a choice (the button says so), a tap picks and
    names the action, another tap moves the pick, the skip stays a button of its own."""
    from app.screens import CardPickOverlay
    from regicide.engine import PHASE_DECIDE
    gs, g = _flute_mission(app, 7)
    g.mission_zone = ["4H", "3S", "2D"]
    for c in g.mission_zone:
        _pull(g, c)
    g.phase = PHASE_DECIDE
    g.decision = {"kind": "zone_banish", "player": 0, "options": ["4H", "2D"], "resume": "defeat", "exact": True}
    gs.refresh(after_action=False)
    ov = gs.overlay
    assert isinstance(ov, CardPickOverlay) and list(ov.card_views) == ["4H", "3S", "2D"]
    assert [c for c, v in ov.card_views.items() if v.dimmed] == ["3S"] and ov.picked == []
    none = ui.find(ov, lambda v: isinstance(v, ui.Button) and v.title == "Choose a card")
    assert none and not none[0].enabled and ui.button(app, "Banish nothing")
    ui.tap(app, *ui.root_point(app, ov.card_views["3S"]))                # dimmed: nothing
    assert ov.picked == []
    ui.tap(app, *ui.root_point(app, ov.card_views["4H"]))
    assert ov.picked == ["4H"] and ui.button(app, "Banish 4♥")
    ui.tap(app, *ui.root_point(app, ov.card_views["2D"]))
    assert ov.picked == ["2D"] and ui.button(app, "Banish 2♦")
    assert not ui.find(ov, lambda v: isinstance(v, ui.Button) and v.title == "Banish 4♥")
    assert ui.render(app).size[0] > 0
