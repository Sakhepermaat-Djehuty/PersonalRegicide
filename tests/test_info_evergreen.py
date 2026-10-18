"""Info pop-ups of the Evergreen group (app/info_evergreen.py), from real Evergreen flows:
each location, bane and boon card shows in its place in the queue (the location's card
first at the end of a turn, then banes 10, 12 and 23, all before Turn; the Lake and banes
16 and 22 after Turn; a box's card right before its box), keeps to the size limits and
leaves nothing (no card, no line) when its row is switched off. With 2+ players the cards
name the player, and a card going into a hidden hand or the reserve is never named."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()

import pytest  # noqa: E402

from app import info_missions  # noqa: E402
from helpers import _pull, set_discard, set_hand, set_tavern_top  # noqa: E402
from info_helpers import card, cards_for, fits, ids, start_cards, text  # noqa: E402
from regicide.campaign import CampaignState  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402

NAMES = ["Ana", "Ben", "Cy"]
LONG = ["Bartholomew Quill", "Maximilian Ash", "Cy"]      # the longest names the other modules test
RESTORED = ("2S", "3H", "4D", "5C", "7S", "8H", "9D", "ESME6E")
HAND = ("10S", "10C", "10D", "9S", "9C")


@pytest.fixture(autouse=True)
def _no_swallowed_errors():
    info_missions.ERRORS[:] = []
    yield
    assert info_missions.ERRORS == [], info_missions.ERRORS[-1]


def off(row_id):
    return {"info_popups_off": [row_id]}


def everything(cards):
    return "\n".join(text(c) for c in cards)


def in_order(cards, *row_ids):
    """These rows' cards come in this order (rows absent from the queue are passed over)."""
    seen = [r for r in row_ids if r in ids(cards)]
    assert [i for i in ids(cards) if i in seen] == seen, (ids(cards), row_ids)


def ever(location="A", banes=(), boons=(), players=1, seed=5000, names=NAMES):
    """An Evergreen attempt after a finished campaign, with this location, banes and boons."""
    c = CampaignState.new(players, list(names[:players]), seed=seed)
    c.mission = 12
    c.completed = list(range(1, 13))
    c.finished = True
    c.relics.append("mother_restored")
    c.flags["beasts"] = True
    c.set_beast("B_H")
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    P.add_card(c.party, dict(M.ASH))
    P.add_card(c.party, dict(M.ESME_REBORN))
    for cid in RESTORED:
        P.add_flag(c.party, cid, "restored")
    c.evergreen["setup"] = {"location": location, "banes": sorted(banes), "boons": sorted(boons)}
    g = c.start_evergreen_attempt(seed=seed)
    g.enemy.suits = ()
    return g


def rig(g, attr, card_ids):
    """Put exactly these cards in a pile (the old ones back into the reserve)."""
    for cid in list(getattr(g, attr)):
        g.tavern.append(cid)
    setattr(g, attr, [])
    for cid in card_ids:
        _pull(g, cid)
    setattr(g, attr, list(card_ids))


def pay(g, cards):
    out, paid = [], 0
    for cid in cards:
        if paid >= g.pending_damage:
            break
        out.append(cid)
        paid += g.cards[cid].defence_value
    return out


def turn_end(g, play="AS", hand=HAND, settings=None):
    """Play ``play``, then pay the damage with the strongest cards: the payment's queue."""
    set_hand(g, [play] + list(hand))
    g.play([play])
    assert g.phase == "suffer", g.phase
    return cards_for(g, lambda: g.suffer(pay(g, list(hand))), settings)


def answer(g, action, settings=None):
    return cards_for(g, lambda: g.decide(action), settings)


def test_the_evergreen_cards_load_whichever_module_is_imported_first():
    code = ("from app import info_missions\nfrom app import info\n"
            "assert info.LOAD_ERRORS == {}, info.LOAD_ERRORS\nassert 'app.info_evergreen' in __import__('sys').modules")
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


# ---------------------------------------------------------------------------- the locations
def test_shrine_comes_first_at_the_end_of_the_turn():
    g = ever("A", seed=5101)
    cards = turn_end(g)
    in_order(cards, "damage_paid", "shrine", "turn")
    c = card(cards, "shrine")
    assert c.title == "Shrine" and c.number == "6" and c.icon is None
    assert c.lines == ["End of turn: reserve top 6♦ to the zone", "Enemies are immune to the zone classes:", "♦"]
    assert c.face_args({})["icon"] == "⛰︎"
    fits(cards)
    g = ever("A", seed=5101)
    cards = turn_end(g, settings=off("shrine"))
    assert "shrine" not in ids(cards) and "6♦" not in everything(cards)


def test_cave_grows_then_collapses_before_turn():
    g = ever("B", seed=5102)
    cards = turn_end(g)
    c = card(cards, "cave")
    assert c.title == "Cave" and c.number == "2"
    assert c.lines == ["End of turn: reserve top 2♣ to the zone", "Zone 2 of 15: at 15 or more", "the cave collapses"]
    assert "cave_collapse" not in ids(cards)
    g = ever("B", seed=5102)
    rig(g, "mission_zone", ["9H"])
    set_discard(g, ["2D", "3D"])
    set_tavern_top(g, ["8H"])
    cards = turn_end(g)
    in_order(cards, "damage_paid", "cave", "cave_collapse", "mother_restored", "turn")
    c = card(cards, "cave_collapse")
    assert c.title == "Cave collapses" and c.number == "17"
    assert c.lines == ["The zone (17) reached the enemy's base", "strength 15: the zone and the whole",
                       "discard pile (4 cards) are banished"]
    fits(cards)
    g = ever("B", seed=5102)
    rig(g, "mission_zone", ["9H"])
    set_tavern_top(g, ["8H"])
    cards = turn_end(g, settings={"info_popups_off": ["cave", "cave_collapse"]})
    assert not {"cave", "cave_collapse"} & set(ids(cards)) and "collapse" not in everything(cards)


def test_cave_collapse_spilling_a_restored_discard_is_not_tread_carefully():
    # the restored Mother sends the restored 8♥ under the reserve: its redirect comes
    # between the zone's banish and the discard pile's, which is still the Cave's
    g = ever("B", banes=(15,), seed=5102)
    rig(g, "mission_zone", ["9H"])
    set_discard(g, ["8H", "3D"])
    set_tavern_top(g, ["7D"])
    g.enemy.attack = 15
    cards = turn_end(g, hand=("10S", "10C", "10D"))
    assert "banish_redirect" in [e["t"] for e in g.last_events]
    in_order(cards, "cave", "cave_collapse", "mother_restored", "turn")
    assert "bane15" not in ids(cards)


def test_forest_feeds_the_enemy():
    g = ever("C", seed=5103)
    cards = turn_end(g)
    in_order(cards, "damage_paid", "forest", "turn")
    c = card(cards, "forest")
    assert c.title == "Forest" and c.number == "10"
    assert c.lines == ["End of turn: banished top J♣ to the zone", "Enemy attack +10"]
    fits(cards)
    g = ever("C", seed=5103)
    assert "forest" not in ids(turn_end(g, settings=off("forest")))


def test_hills_come_before_their_team_damage_or_say_a_guardian_prevents_it():
    g = ever("D", seed=5104)
    rig(g, "banished", ["3D"])
    cards = turn_end(g)
    in_order(cards, "damage_paid", "hills", "team_damage")
    c = card(cards, "hills")
    assert c.title == "Hills" and c.number == "3"
    assert c.lines == ["End of turn: banished top 3♦ to the zone", "Team damage 3 follows"]
    fits(cards)
    g = ever("D", seed=5104)
    rig(g, "banished", ["3D"])
    g.extra["guardian"] = True             # a Guardian played this turn: no damage, no team damage
    set_hand(g, ["AS", "10S"])
    cards = cards_for(g, lambda: g.play(["AS"]))
    in_order(cards, "hills", "turn")
    assert card(cards, "hills").lines[-1] == "A Guardian prevents the team damage"
    assert "team_damage" not in ids(cards)
    g = ever("D", seed=5104)
    rig(g, "banished", ["3D"])
    assert "hills" not in ids(turn_end(g, settings=off("hills")))


def test_lake_comes_after_turn_and_at_the_start():
    g = ever("E", seed=5105)
    cards = start_cards(g)
    assert ids(cards) == ["battle_start", "lake"]
    c = cards[1]
    assert c.title == "Lake" and c.number == "5"
    assert c.lines == ["Start of turn: Pilgrim 5 joins the zone", "On defeat: 1 reserve card is banished",
                       "per zone card (1 now)"]
    cards = turn_end(g)
    in_order(cards, "damage_paid", "turn", "lake")
    assert card(cards, "lake").lines[-1] == "per zone card (2 now)"
    fits(cards)
    g = ever("E", seed=5105)
    assert ids(start_cards(g, off("lake"))) == ["battle_start"]


def test_lake_with_the_pilgrims_out_takes_the_reserve_top():
    g = ever("E", seed=5105)
    g.extra["pilgrim_deck"] = []
    set_tavern_top(g, ["7D"])
    cards = turn_end(g)
    in_order(cards, "turn", "lake")
    c = card(cards, "lake")
    assert c.number == "7" and c.lines[0] == "Start of turn: reserve top 7♦ → zone"


# ---------------------------------------------------------------------------- the banes
def test_banes_10_12_and_23_follow_the_location_in_order_with_their_boxes():
    g = ever("A", banes=(10, 12, 23), seed=5110)
    set_discard(g, ["2D"])
    set_hand(g, ["AS"] + list(HAND) + ["2C"])
    g.play(["AS"])
    g.enemy.suits = ("H", "D")
    cards = cards_for(g, lambda: g.suffer(pay(g, list(HAND))))
    assert g.decision["kind"] == "zone_feed"
    in_order(cards, "damage_paid", "shrine", "bane10", "bane12")
    assert ids(cards)[-1] == "bane12"
    c = card(cards, "bane10")
    assert c.title == "Poisonous Clerics" and c.number == "10"
    assert c.lines == ["End of turn: the enemy is a cleric,", "so the top discard (10♣) joins the zone"]
    c = card(cards, "bane12")
    assert c.title == "Duplicitous Bards" and c.number == ""
    assert c.lines == ["End of turn: the enemy is a bard,", "so put a card from your hand in the zone"]
    fits(cards)
    cards = answer(g, {"type": "zone_feed", "player": 0, "card": "2C"})
    assert ids(cards) == ["bane23"] and g.decision["kind"] == "poison"
    assert cards[0].title == "Choose Your Poison"
    assert cards[0].lines == ["You put 2♣ in the zone", "End of turn: discard a card from hand,",
                              "or the reserve top joins the zone"]
    cards = answer(g, {"type": "poison_skip", "player": 0})
    assert "shrine" not in ids(cards) and "bane23" not in ids(cards)
    assert card(cards, "turn").lines[0] == "Reserve top 7♠ joins the zone"
    fits(cards)


def test_bane10_switched_off_leaves_the_other_cards():
    g = ever("A", banes=(10,), seed=5110)
    set_discard(g, ["2D"])
    set_hand(g, ["AS"] + list(HAND))
    g.play(["AS"])
    g.enemy.suits = ("H",)
    cards = cards_for(g, lambda: g.suffer(pay(g, list(HAND))), off("bane10"))
    assert "bane10" not in ids(cards) and "cleric" not in everything(cards)
    in_order(cards, "damage_paid", "shrine", "turn")


def test_bane23_discard_is_a_line_and_an_empty_hand_shows_the_card_alone():
    g = ever("A", banes=(23,), seed=5111)
    cards = turn_end(g, hand=("10S", "10C", "10D", "2C"))
    in_order(cards, "shrine", "bane23")
    cards = answer(g, {"type": "poison", "player": 0, "card": "2C"})
    assert card(cards, "turn").lines[0] == "You discarded 2♣ (Choose Your Poison)"
    g = ever("A", banes=(23,), seed=5111)
    cards = turn_end(g, hand=("10S", "10C"))
    in_order(cards, "shrine", "bane23", "turn")
    c = card(cards, "bane23")
    assert c.number == "8"
    assert c.lines == ["End of turn: no hand card to discard,", "so reserve top 8♠ joins the zone"]
    fits(cards)
    g = ever("A", banes=(23,), seed=5111)
    cards = turn_end(g, hand=("10S", "10C", "10D", "2C"), settings=off("bane23"))
    assert "bane23" not in ids(cards)
    cards = answer(g, {"type": "poison", "player": 0, "card": "2C"}, off("bane23"))
    assert "Poison" not in everything(cards) and "2♣" not in everything(cards)


def test_bane12_names_the_player_with_two_players_and_switched_off_leaves_no_line():
    g = ever("A", banes=(12,), players=2, seed=5110)
    set_hand(g, ["AS"] + list(HAND) + ["2C"])
    g.play(["AS"])
    g.enemy.suits = ("D",)
    cards = cards_for(g, lambda: g.suffer(pay(g, list(HAND))))
    assert card(cards, "bane12").lines[1] == "so Ana puts a hand card in the zone"
    cards = answer(g, {"type": "zone_feed", "player": 0, "card": "2C"})
    assert cards[0].lines[0] == "Ana put 2♣ in the zone" and "You" not in everything(cards)
    g = ever("A", banes=(12,), seed=5110)
    set_hand(g, ["AS"] + list(HAND) + ["2C"])
    g.play(["AS"])
    g.enemy.suits = ("D",)
    cards = cards_for(g, lambda: g.suffer(pay(g, list(HAND))), off("bane12"))
    assert "bane12" not in ids(cards)
    cards = answer(g, {"type": "zone_feed", "player": 0, "card": "2C"}, off("bane12"))
    assert "2♣" not in everything(cards)


def test_banes_14_and_15_at_a_kill_that_is_not_exact():
    g = ever("A", banes=(14, 15), seed=5118)
    set_discard(g, ["2D", "3D"])
    g.enemy.hp = 1
    set_hand(g, ["2S", "10S", "10C", "9C"])
    cards = cards_for(g, lambda: g.play(["2S"]))
    in_order(cards, "defeated", "bane15", "bane14", "new_enemy", "turn")
    c = card(cards, "bane15")
    assert c.title == "Tread Carefully"
    assert c.lines == ["Not exact: the whole discard pile (2)", "is banished before the location's steps"]
    c = card(cards, "bane14")
    assert c.title == "Absorbtion"
    assert c.lines == ["The killing attack (2♠) joins the zone,", "not the discard pile · zone now 2"]
    fits(cards)
    g = ever("A", banes=(14, 15), seed=5118)
    set_discard(g, ["2D", "3D"])
    g.enemy.hp = 1
    set_hand(g, ["2S", "10S", "10C", "9C"])
    cards = cards_for(g, lambda: g.play(["2S"]), {"info_popups_off": ["bane14", "bane15"]})
    assert not {"bane14", "bane15"} & set(ids(cards)) and "killing attack" not in everything(cards)


def test_bane14_follows_the_clean_up_of_a_paid_explosive_spores():
    g = ever("A", banes=(13, 14), seed=5118)
    g.enemy.hp = 1
    set_hand(g, ["2S", "10S", "10C", "9C"])
    cards_for(g, lambda: g.play(["2S"]))
    while g.decision and g.decision["kind"] == "team_discard":
        cards = answer(g, g.legal_actions()[0])
    in_order(cards, "cleanup", "bane14", "new_enemy")


def test_banes_16_and_22_come_after_turn():
    g = ever("A", banes=(16, 22), seed=5109)
    cards = start_cards(g)
    assert ids(cards) == ["battle_start", "bane22"]        # the discard pile is empty at the start: no bane 16 card
    assert cards[1].title == "The Fiery Crucible"
    assert cards[1].lines == ["Start of turn: the reserve top (5♠)", "goes to the discard pile"]
    cards = turn_end(g)
    in_order(cards, "damage_paid", "shrine", "turn", "bane16", "bane22")
    c = card(cards, "bane16")
    assert c.title == "Lingering Dread" and c.lines == ["Start of turn: the top discard (10♣)", "is banished"]
    fits(cards)
    g = ever("A", banes=(16, 22), seed=5109)
    cards = turn_end(g, settings={"info_popups_off": ["bane16", "bane22"]})
    assert not {"bane16", "bane22"} & set(ids(cards)) and "Start of turn: the" not in everything(cards)


def test_bane16_does_not_name_a_restored_top_discard_going_under_the_reserve():
    g = ever("A", banes=(16,), seed=5109)
    g.enemy.attack = 1                     # shielded to 0: no damage, nothing discarded
    set_discard(g, ["8H", "2D"])
    set_hand(g, ["AS", "10S"])
    cards = cards_for(g, lambda: g.play(["AS"]))
    in_order(cards, "turn", "bane16", "mother_restored")
    c = card(cards, "bane16")
    assert c.lines == ["Start of turn: top discard is banished", "Restored: it goes under the reserve"]
    assert "8♥" not in text(c)
    fits(cards)


def test_bane16_with_the_discard_pile_empty_follows_the_lake():
    g = ever("E", banes=(16, 22), seed=5109)
    g.enemy.attack = 1                     # shielded to 0: no damage, nothing discarded
    set_discard(g, [])
    set_hand(g, ["AS", "10S"])
    cards = cards_for(g, lambda: g.play(["AS"]))
    in_order(cards, "turn", "lake", "bane16", "bane22")
    assert card(cards, "bane16").lines == ["Start of turn: top discard is banished",
                                           "Discard pile empty: nothing moves"]
    assert ids(cards).count("bane16") == 1
    fits(cards)
    g = ever("A", banes=(16,), seed=5109)
    g.enemy.attack = 1
    set_discard(g, [])
    set_hand(g, ["AS", "10S"])
    cards = cards_for(g, lambda: g.play(["AS"]))
    in_order(cards, "shrine", "turn", "bane16")


def test_bane21_comes_before_its_box_and_boon30_after_it():
    g = ever("A", banes=(21,), boons=(30,), seed=5112)
    rig(g, "mission_zone", ["8H"])
    set_hand(g, ["8C", "2C", "10S", "10C"])
    cards = cards_for(g, lambda: g.play(["8C"]))
    assert ids(cards) == ["bane21"] and g.decision["kind"] == "attack_discard"
    c = cards[0]
    assert c.title == "Eye-Level Sticks" and c.number == "8"
    assert c.lines == ["Your attack holds a card of strength 8+:", "discard a card from your hand"]
    cards = answer(g, {"type": "attack_discard", "player": 0, "card": "2C"})
    assert ids(cards) == ["boon30"] and g.decision["kind"] == "zone_sibling"
    c = cards[0]
    assert c.title == "Squad of Siblings" and c.number == "8"
    assert c.lines == ["You discarded 2♣ (Eye-Level Sticks)", "Zone card 8♥ matches your attack (8)",
                       "Move it to the discard pile?"]
    cards = answer(g, {"type": "zone_sibling", "player": 0, "card": "8H"})
    assert cards[0].lines[0] == "8♥: zone → discard pile"
    fits(cards)


def test_boon30_names_each_matching_strength():
    g = ever("A", boons=(30,), seed=5112)
    rig(g, "mission_zone", ["AD", "8H"])
    set_hand(g, ["AH", "8C", "10S", "10C"])
    cards = cards_for(g, lambda: g.play(["AH", "8C"]))
    c = card(cards, "boon30")
    assert c.number == "9" and c.lines[-2:] == ["Zone cards A♦ 8♥ match your attack (1/8)",
                                                "Move one to the discard pile?"]


def test_bane21_and_boon30_switched_off_leave_no_card_and_no_line():
    g = ever("A", banes=(21,), boons=(30,), seed=5112)
    rig(g, "mission_zone", ["8H"])
    set_hand(g, ["8C", "2C", "10S", "10C"])
    settings = {"info_popups_off": ["bane21", "boon30"]}
    assert cards_for(g, lambda: g.play(["8C"]), settings) == []
    assert answer(g, {"type": "attack_discard", "player": 0, "card": "2C"}, settings) == []
    cards = answer(g, {"type": "zone_sibling_skip", "player": 0}, settings)
    assert "Siblings" not in everything(cards) and "Sticks" not in everything(cards)


def test_bane21_names_the_player_with_two_players():
    g = ever("A", banes=(21,), players=2, seed=5112)
    set_hand(g, ["8C", "2C", "10S", "10C"])
    cards = cards_for(g, lambda: g.play(["8C"]))
    assert cards[0].lines == ["Ana's attack has a card of 8+:", "Ana discards a card from hand"]


def test_banes_keep_a_long_name_whole():
    g = ever("A", banes=(12,), players=2, seed=5110, names=LONG)
    set_hand(g, ["AS"] + list(HAND) + ["2C"])
    g.play(["AS"])
    g.enemy.suits = ("D",)
    cards = cards_for(g, lambda: g.suffer(pay(g, list(HAND))))
    assert card(cards, "bane12").lines == ["End of turn: the enemy is a bard,", "so Bartholomew Quill must put",
                                           "a hand card in the zone"]
    g = ever("A", banes=(21,), players=2, seed=5112, names=LONG)
    set_hand(g, ["8C", "2C", "10S", "10C"])
    cards += cards_for(g, lambda: g.play(["8C"]))
    assert card(cards, "bane21").lines == ["Bartholomew Quill's attack has an 8+:",
                                           "Bartholomew Quill discards a hand card"]
    g = ever("A", banes=(23,), players=2, seed=5111, names=LONG)
    cards += turn_end(g, hand=("10S", "10C", "10D", "2C"))
    assert card(cards, "bane23").lines[0] == "Bartholomew Quill may discard a card,"
    assert "…" not in everything(cards)
    fits(cards)


# ---------------------------------------------------------------------------- the boons
def _close_call(boons=(31, 35), players=1, names=NAMES):
    g = ever("A", boons=boons, players=players, seed=5114, names=names)
    rig(g, "mission_zone", ["10H", "5H"])
    set_discard(g, ["2D", "3D"])
    g.enemy.attack = 11
    set_hand(g, ["AS", "10S", "9C"])
    g.play(["AS"])
    return g


def test_a_close_call_and_selfless_rescue_follow_damage_paid():
    g = _close_call()
    cards = cards_for(g, lambda: g.suffer(["10S"]))
    in_order(cards, "damage_paid", "boon35", "boon31")
    assert ids(cards)[-1] == "boon31" and g.decision["kind"] == "zone_match"
    c = card(cards, "boon35")
    assert c.title == "A Close Call" and c.number == "10"
    assert c.lines == ["Paid exactly 10: the discarded cards go", "under the reserve, not the discard pile",
                       "Now put a discard on top of the reserve"]
    assert "10♠" not in text(c)                     # hidden: the cards now under the reserve
    c = card(cards, "boon31")
    assert c.title == "Selfless Rescue" and c.number == "10"
    assert c.lines == ["You discarded a 10; the zone holds a 10", "Move that zone card to the discard pile?"]
    fits(cards)
    assert answer(g, {"type": "zone_match", "player": 0, "card": "10H"}) == []      # the pick box asks itself
    cards = answer(g, {"type": "close_call", "player": 0, "card": "3D"})
    in_order(cards, "shrine", "turn")
    # hidden: the card put on the reserve is not named (the Shrine then shows it joining the zone)
    assert card(cards, "shrine").lines[:2] == ["10♥: zone → discard pile", "A discard went on top of the reserve"]
    fits(cards)


def test_a_close_call_with_two_players_and_switched_off():
    g = _close_call(boons=(35,), players=2)
    cards = cards_for(g, lambda: g.suffer(["10S"]))
    assert card(cards, "boon35").lines[-1] == "Ana puts a discard on top of the reserve"
    assert "You" not in text(card(cards, "boon35"))
    g = _close_call(boons=(31, 35))
    settings = {"info_popups_off": ["boon31", "boon35"]}
    cards = cards_for(g, lambda: g.suffer(["10S"]), settings)
    assert not {"boon31", "boon35"} & set(ids(cards))
    answer(g, {"type": "zone_match", "player": 0, "card": "10H"}, settings)
    cards = answer(g, {"type": "close_call", "player": 0, "card": "3D"}, settings)
    assert "zone → discard" not in everything(cards) and "A discard went" not in everything(cards)


def test_boons_keep_a_long_name_whole():
    g = _close_call(players=2, names=LONG)
    cards = cards_for(g, lambda: g.suffer(["10S"]))
    assert card(cards, "boon35").lines[-2:] == ["Now Bartholomew Quill puts a discard", "on top of the reserve"]
    assert card(cards, "boon31").lines == ["Bartholomew Quill discarded a 10;", "the zone holds a 10: move that card",
                                           "to the discard pile?"]
    g = ever("A", boons=(33,), players=2, seed=5116, names=LONG)
    rig(g, "banished", ["6D"])
    g.enemy.hp = 1
    set_hand(g, ["AS", "9S"])
    cards += cards_for(g, lambda: g.play(["AS"]))
    assert card(cards, "boon33").lines == ["Exact kill: Bartholomew Quill may put", "a banished card under the reserve"]
    assert "…" not in everything(cards)
    fits(cards)


def test_selfless_rescue_asked_again_shows_no_second_card():
    g = ever("A", boons=(31,), seed=5114)
    rig(g, "mission_zone", ["10H", "10D"])
    g.enemy.attack = 20
    set_hand(g, ["AS", "10S", "10C", "9C"])
    g.play(["AS"])
    cards = cards_for(g, lambda: g.suffer(["10S", "10C"]))
    assert ids(cards)[-1] == "boon31"
    assert answer(g, {"type": "zone_match", "player": 0, "card": "10H"}) == [] and g.decision["kind"] == "zone_match"
    cards = answer(g, {"type": "zone_match_skip", "player": 0})
    assert card(cards, "shrine").lines[:2] == ["10♥: zone → discard pile", "The zone card stays (Selfless Rescue)"]


def test_selfless_rescue_names_the_player_with_two_players():
    g = _close_call(boons=(31,), players=2)
    cards = cards_for(g, lambda: g.suffer(["10S"]))
    assert card(cards, "boon31").lines[0] == "Ana discarded a 10; the zone holds a 10"


def test_precision_strike_and_restored_arrows_come_before_their_boxes():
    g = ever("A", boons=(32, 33), seed=5116)
    rig(g, "mission_zone", ["4H"])
    rig(g, "banished", ["6D"])
    g.enemy.hp = 1
    set_hand(g, ["AS", "9S"])
    cards = cards_for(g, lambda: g.play(["AS"]))
    in_order(cards, "exact_kill", "boon32")
    assert ids(cards)[-1] == "boon32" and g.decision["kind"] == "precision_strike"
    c = card(cards, "boon32")
    assert c.title == "Precision Strike" and c.lines == ["Exact kill: put a zone card or the top",
                                                         "discard into your hand"]
    cards = answer(g, {"type": "precision_strike", "player": 0, "card": "4H", "pile": "zone"})
    assert ids(cards)[-1] == "boon33" and g.decision["kind"] == "restored_arrows"
    c = card(cards, "boon33")
    assert c.title == "Restored Arrows" and c.lines[-2:] == ["Exact kill: you may put a banished card",
                                                            "under the reserve"]
    later = answer(g, {"type": "restored_arrows", "player": 0, "card": "6D"})
    # hidden: the card taken into the hand and the card put under the reserve are never named
    assert "4♥" not in everything(cards + later) and "6♦" not in everything(later)
    fits(cards + later)


def test_precision_strike_names_the_player_with_two_players():
    g = ever("A", boons=(32, 33), players=2, seed=5116)
    rig(g, "mission_zone", ["4H"])
    rig(g, "banished", ["6D"])
    g.enemy.hp = 1
    set_hand(g, ["AS", "9S"])
    cards = cards_for(g, lambda: g.play(["AS"]))
    assert card(cards, "boon32").lines[-1] == "discard into Ana's hand" and "You" not in everything(cards)
    cards = answer(g, {"type": "precision_strike", "player": 0, "card": "4H", "pile": "zone"})
    assert card(cards, "boon33").lines[-2:] == ["Exact kill: Ana may put a banished card", "under the reserve"]


def test_precision_strike_and_restored_arrows_switched_off():
    g = ever("A", boons=(32, 33), seed=5116)
    rig(g, "mission_zone", ["4H"])
    rig(g, "banished", ["6D"])
    g.enemy.hp = 1
    set_hand(g, ["AS", "9S"])
    settings = {"info_popups_off": ["boon32", "boon33"]}
    cards = cards_for(g, lambda: g.play(["AS"]), settings)
    assert "boon32" not in ids(cards) and g.decision["kind"] == "precision_strike"
    cards = answer(g, {"type": "precision_strike", "player": 0, "card": "4H", "pile": "zone"}, settings)
    assert "boon33" not in ids(cards) and "Restored Arrows" not in everything(cards)
