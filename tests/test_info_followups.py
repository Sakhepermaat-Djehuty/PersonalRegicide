"""Info pop-ups: what the builders' reviews left to the core and across modules. A row
switched off takes its outcome lines with it; a card that replaces another falls back to it
(Battle start -> New enemy); the Turn card keeps the enemy when the card that would say it
is off; a lost campaign mission names the coins it earns."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()

from app import info  # noqa: E402
from info_helpers import ON, card, cards_for, fits, ids, start_cards, text  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from helpers import set_hand  # noqa: E402

import test_info_defeat as D  # noqa: E402
import test_info_evergreen as E  # noqa: E402
import test_info_missions as MI  # noqa: E402


def off(*rows):
    return {"info_popups_off": list(rows)}


def everything(cards):
    return "\n".join(text(c) for c in cards)


def test_new_enemy_shows_the_first_enemy_when_battle_start_is_off():
    g = D.base()
    assert ids(start_cards(g)) == ["battle_start"]
    cards = start_cards(g, off("battle_start"))
    assert ids(cards) == ["new_enemy"] and cards[0].middle == str(g.enemy.hp)
    assert start_cards(g, off("battle_start", "new_enemy")) == []


def test_the_turn_card_keeps_the_enemy_when_the_zone_card_that_states_it_is_off():
    def turn(settings):
        g = MI.mission(10, cards=list(M.MAGE_DECK) + [M.GORAN_RENEWED, M.ASH], corrupted=MI.CORRUPT)
        return card(MI.turn_end(g, play="AH", hand=("9C", "8C", "7C"), settings=settings), "turn")
    assert not any("attack" in line for line in turn(None).lines)            # the zone card says it
    assert any("attack" in line for line in turn(off("m10_zone")).lines)      # nobody else does


def test_a_switched_off_boon_takes_its_outcome_line_with_it():
    def flow(settings):
        g = E.ever("A", boons=(32,), seed=5116)
        E.rig(g, "mission_zone", ["4H"])
        g.enemy.hp = 1
        set_hand(g, ["AS", "9S"])
        first = cards_for(g, lambda: g.play(["AS"]), settings)
        later = cards_for(g, lambda: g.decide({"type": "precision_strike", "player": 0, "card": "4H", "pile": "zone"}),
                          settings)
        return first + later
    assert "into hand" in everything(flow(None))
    cards = flow(off("boon32"))
    assert "boon32" not in ids(cards) and "into hand" not in everything(cards)


def test_a_lost_campaign_mission_names_the_coins_it_earns():
    def lose(app):
        g = D.base(hand=("2C",))
        g.solo_jesters = 0
        before = g.to_dict()
        g.play(["2C"])
        return info.build(g, g.last_events, dict(ON), before=before, app=app)
    plain = lose(None)
    assert ids(plain)[-1] == "loss" and "coin" not in everything(plain)
    cards = lose({"coins_on_loss": 3})
    assert "+3 coins (loss 3 on this mission)" in card(cards, "loss").lines
    assert "+1 coin (loss 1 on this mission)" in card(lose({"coins_on_loss": 1}), "loss").lines
    fits(cards)
