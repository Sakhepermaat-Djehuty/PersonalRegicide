"""Info pop-ups of the Missions group (app/info_missions.py), from real Legacy mission flows:
each mission card shows in its place in the queue (the end-of-turn cards before Turn, the
start-of-turn cards after it, a box's card right before its box), keeps to the size limits
and leaves nothing (no card, no line) when its row is switched off. A step that moved
nothing still gets its card; with 2+ players the cards name the player."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()

import pytest  # noqa: E402

from app import info, info_missions  # noqa: E402
from app import theme as T  # noqa: E402
from helpers import _pull, set_discard, set_hand, set_tavern_top  # noqa: E402
from info_helpers import card, cards_for, fits, ids, start_cards, text  # noqa: E402
from regicide.campaign import CampaignState  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402

NAMES = ["Ana", "Ben", "Cy"]
LONG = ["Bartholomew Quill", "Maximilian Ash", "Cy"]      # the longest names the other modules test
CORRUPT = ("2S", "3H", "4D", "5C", "6C", "7S", "8H", "9D")
M11_CORRUPT = ("2S", "3H", "4D", "5C", "6H", "7S", "8H", "9D")


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


def mission(n, players=1, cards=(), corrupted=(), beast=None, seed=None, names=NAMES):
    """A Legacy mission prepared the way the campaign does it (setup choices taken)."""
    seed = seed or 900 + n
    c = CampaignState.new(players, list(names[:players]), seed=seed)
    c.mission = n
    c.completed = list(range(1, n))
    for d in cards:
        if P.find(c.party, str(d["id"])) is None:
            P.add_card(c.party, dict(d))
    if beast:
        c.flags["beasts"] = True
        c.set_beast(beast)
    for cid in corrupted:
        P.add_flag(c.party, cid, "corrupted")
        c.corrupted.append(cid)
    if c.prepare_mission():
        while c.pending:
            step = c.pending_choice()
            c.resolve_choice(step["options"][0] if step.get("options") else {})
    return c.start_attempt(seed=seed)


def rig(g, attr, card_ids):
    """Put exactly these cards in a pile (the old ones back into the reserve)."""
    for cid in list(getattr(g, attr)):
        g.tavern.append(cid)
    setattr(g, attr, [])
    for cid in card_ids:
        _pull(g, cid)
    setattr(g, attr, list(card_ids))


def pay(g, cards):
    """The fewest of these cards, in order, that cover the damage due."""
    out, paid = [], 0
    for cid in cards:
        if paid >= g.pending_damage:
            break
        out.append(cid)
        paid += g.cards[cid].defence_value
    return out


def suffer_cards(g, settings=None, hand=("10S", "10C", "10D", "9S", "9C")):
    """The queue of paying the damage due with the strongest of these hand cards."""
    return cards_for(g, lambda: g.suffer(pay(g, list(hand))), settings)


def turn_end(g, play="AS", hand=("10S", "10C", "10D", "9S", "9C"), settings=None):
    """Play ``play``, then pay the damage: the queue of the payment (the end of the turn)."""
    set_hand(g, [play] + list(hand))
    g.play([play])
    assert g.phase == "suffer", g.phase
    return suffer_cards(g, settings, hand)


def m10(enemy, players=1, names=NAMES):
    """Mission 10 with this corrupted party member as the enemy."""
    g = mission(10, players=players, cards=list(M.MAGE_DECK) + [M.GORAN_RENEWED, M.ASH], corrupted=CORRUPT,
                names=names)
    g.castle.insert(0, g.enemy.card_id)
    g.enemy = None
    g.castle.remove(enemy)
    g.castle.insert(0, enemy)
    g._reveal_next_enemy()
    return g


def m11(players=1, beasts=None):
    """Mission 11; with ``beasts``, past its first beast's box, the beast deck in this order."""
    g = mission(11, players=players, cards=list(M.MAGE_DECK) + [M.GORAN_RENEWED, M.ASH], corrupted=M11_CORRUPT)
    if beasts:
        g.decide(g.legal_actions()[0])
        g.extra["beast_deck"] = list(beasts)
        g.extra["beasts_out"] = []
    return g


# ---------------------------------------------------------------------------- 3 Lessons in Flames
def test_m3_zone_grows_at_the_end_of_the_turn_before_turn():
    g = mission(3, cards=M.MAGE_DECK)
    set_hand(g, ["3C", "9S", "8S", "7D"])
    set_tavern_top(g, ["4H", "5D"])
    g.play(["3C"])
    cards = cards_for(g, lambda: g.suffer(["9S", "7D"]))
    in_order(cards, "damage_paid", "m3_zone", "turn")
    c = card(cards, "m3_zone")
    assert c.title == "Zone: new immunity" and c.number == "4"
    assert c.lines == ["End of turn: reserve top 4♥ to the zone", "Enemies are immune to every zone class:",
                       "♥ (new: ♥)"]
    fits(cards)
    g = mission(3, cards=M.MAGE_DECK)
    set_hand(g, ["3C", "9S", "8S", "7D"])
    set_tavern_top(g, ["4H", "5D"])
    g.play(["3C"])
    cards = cards_for(g, lambda: g.suffer(["9S", "7D"]), off("m3_zone"))
    assert "m3_zone" not in ids(cards) and "4♥" not in everything(cards) and "turn" in ids(cards)


def test_m3_zone_with_the_reserve_empty_says_nothing_joins():
    g = mission(3, cards=M.MAGE_DECK)
    rig(g, "mission_zone", ["4H"])
    set_hand(g, ["3C", "10S", "10C", "9S"])
    g.play(["3C"])
    g.tavern[:] = []
    cards = suffer_cards(g, hand=("10S", "10C", "9S"))
    in_order(cards, "damage_paid", "m3_zone", "turn")
    c = card(cards, "m3_zone")
    assert c.number == "" and c.lines[:2] == ["End of turn: reserve empty,", "nothing joins the zone"]
    assert c.lines[-1] == "♥"
    fits(cards)


# ---------------------------------------------------------------------------- 5 High and Mighty
def test_m5_zone_takes_the_banished_top_and_then_finds_the_pile_empty():
    g = mission(5, cards=[M.GORAN])
    cards = turn_end(g, play="3C")
    in_order(cards, "damage_paid", "m5_zone", "turn")
    c = card(cards, "m5_zone")
    assert c.title == "Zone: enemy stronger" and c.number == "7"
    assert c.lines == ["Banished top Myla (7) joins the zone", "Enemy attack +7 (zone: Myla (7))"]
    cards = turn_end(g, play="3C")
    c = card(cards, "m5_zone")
    assert c.number == "" and c.lines[:2] == ["End of turn: banished pile empty,", "nothing joins the zone"]
    assert c.lines[2] == "Enemy attack +7 (zone: Myla (7))"
    fits(cards)
    cards = turn_end(g, play="3C", settings=off("m5_zone"))
    assert "m5_zone" not in ids(cards) and "nothing joins" not in everything(cards)


def test_m5_carry_damage_follows_new_enemy_and_a_second_kill_goes_on():
    g = mission(5, cards=[M.GORAN])
    turn_end(g, play="3C")
    g.enemy.hp = 6
    set_hand(g, ["3C", "9S", "8S"])
    cards = cards_for(g, lambda: g.play(["3C"]))
    in_order(cards, "exact_kill", "new_enemy", "m5_carry", "turn")
    c = card(cards, "m5_carry")
    assert c.title == "Carry damage" and c.number == "17" and c.middle == "17" and c.caption == "to Sporeling"
    assert c.lines == ["Exact kill: Sporeling takes 17", "(the fallen enemy's strength)", "Health 40 → 23"]
    fits(cards)
    # a carry that kills: the queue goes on with the next defeat and New enemy
    g.enemy.hp = 6
    g.enemy.attack = 40
    set_hand(g, ["3C", "9S", "8S"])
    cards = cards_for(g, lambda: g.play(["3C"]))
    c = card(cards, "m5_carry")
    assert c.lines[-1] == "Health 40 → 0: it falls too!"
    assert ids(cards).index("m5_carry") < max(i for i, r in enumerate(ids(cards)) if r == "new_enemy")
    fits(cards)
    g = mission(5, cards=[M.GORAN])
    g.enemy.hp = 6
    set_hand(g, ["3C", "9S", "8S"])
    cards = cards_for(g, lambda: g.play(["3C"]), off("m5_carry"))
    assert "m5_carry" not in ids(cards) and "fallen enemy" not in everything(cards)


# ---------------------------------------------------------------------------- 7 Tales of Rebirth
def test_m7_pilgrim_arrives_at_the_start_and_after_turn():
    g = mission(7, cards=list(M.DRUIDS) + [M.GORAN])
    cards = start_cards(g)
    assert ids(cards) == ["battle_start", "m7_pilgrim"]
    c = card(cards, "m7_pilgrim")
    assert c.title == "Pilgrim arrives" and c.number == "7"
    assert c.lines == ["Start of turn: Pilgrim 7 joins the zone", "A card of strength 7 entering play",
                       "may banish it from the zone", "On defeat: 7 reserve cards → discard"]
    cards = turn_end(g, play="9S", hand=("10S", "10C", "10D"))
    in_order(cards, "damage_paid", "turn", "m7_pilgrim")
    assert card(cards, "m7_pilgrim").lines[0] == "Start of turn: Pilgrim 6 joins the zone"
    assert card(cards, "m7_pilgrim").lines[-1] == "On defeat: 13 reserve cards → discard"
    fits(cards)
    g = mission(7, cards=list(M.DRUIDS) + [M.GORAN])
    assert ids(start_cards(g, off("m7_pilgrim"))) == ["battle_start"]


def test_m7_two_players_show_turn_before_the_pilgrim():
    g = mission(7, players=2, cards=list(M.DRUIDS) + [M.GORAN])
    assert ids(start_cards(g)) == ["battle_start", "turn", "m7_pilgrim"]


def test_m7_pilgrim_match_comes_before_its_box_and_its_answer_is_a_line():
    g = mission(7, cards=list(M.DRUIDS) + [M.GORAN])
    set_hand(g, ["7C", "9S", "8S", "7S", "6S"])
    cards = cards_for(g, lambda: g.play(["7C"]))
    assert ids(cards) == ["m7_match"] and g.decision["kind"] == "pilgrim_banish"
    c = cards[0]
    assert c.title == "Pilgrim match" and c.number == "7"
    assert c.lines == ["7♣ matches Pilgrim 7 in the zone", "Banish the pilgrim from the zone?"]
    cards = cards_for(g, lambda: g.decide({"type": "pilgrim_banish", "player": 0, "card": "PIL7_3"}))
    assert cards[0].lines[0] == "You banished Pilgrim 7"
    fits(cards)
    g = mission(7, cards=list(M.DRUIDS) + [M.GORAN])
    set_hand(g, ["7C", "9S", "8S", "7S", "6S"])
    assert cards_for(g, lambda: g.play(["7C"]), off("m7_match")) == []
    cards = cards_for(g, lambda: g.decide({"type": "pilgrim_skip", "player": 0}), off("m7_match"))
    assert "pilgrim" not in everything(cards).lower()


def test_m7_pilgrim_skip_is_a_line():
    g = mission(7, cards=list(M.DRUIDS) + [M.GORAN])
    set_hand(g, ["7C", "9S", "8S", "7S", "6S"])
    cards_for(g, lambda: g.play(["7C"]))
    cards = cards_for(g, lambda: g.decide({"type": "pilgrim_skip", "player": 0}))
    assert cards[0].lines[0] == "The pilgrim stays in the zone"


# ---------------------------------------------------------------------------- 8 Winds of Chaos
def _m8_ready(players=1, names=NAMES):
    g = mission(8, players=players, seed=982, cards=list(M.CHANTERS) + [M.GORAN], names=names)
    rig(g, "mission_zone", ["PILA", "2H", "3H", "4H", "5H", "6H", "7H", "8H", "9H"])
    g.enemy.hp = 10
    g.enemy.suits = ()
    set_hand(g, ["10C", "9S"])
    set_discard(g, ["2D", "3D", "4D"])
    g.play(["10C"])
    assert g.decision["kind"] == "zone_build"
    return g


def test_m8_zone_filled_comes_before_the_banish_box():
    g = _m8_ready()
    cards = cards_for(g, lambda: g.decide({"type": "zone_build", "player": 0, "card": "10C"}))
    assert ids(cards) == ["m8_filled"] and g.decision["kind"] == "discard_banish"
    c = cards[0]
    assert c.title == "Zone filled!" and c.number == "10"
    assert c.lines[-5:] == ["A 10 completes the zone (10 cards):", "it goes to the discard pile",
                            "Banish any discards you choose;", "the rest heal under the reserve",
                            "No more zone moves this mission"]
    fits(cards)
    g = _m8_ready()
    assert cards_for(g, lambda: g.decide({"type": "zone_build", "player": 0, "card": "10C"}), off("m8_filled")) == []


def test_m8_zone_filled_names_the_player_with_two_players():
    for names, line in ((NAMES, "Ana may banish any discards;"), (LONG, "Bartholomew Quill may banish discards;")):
        g = _m8_ready(players=2, names=names)
        cards = cards_for(g, lambda: g.decide({"type": "zone_build", "player": 0, "card": "10C"}))
        c = card(cards, "m8_filled")
        assert line in c.lines and " you " not in text(c)
        fits(cards)


# ---------------------------------------------------------------------------- 9 Hope From Ashes
def _m9(players=1):
    g = mission(9, players=players, cards=[M.GORAN])
    g.enemy.suits = ()
    set_hand(g, ["3C", "9S", "8S", "7S", "6S"])
    g.play(["3C"])
    return g


def test_m9_captured_piles_come_before_their_box_and_the_rescue_is_a_line_on_turn():
    g = _m9()
    tops = " ".join(g.cards[p[0]].label() for p in g.extra["captured"])
    cards = cards_for(g, lambda: g.suffer(["9S", "6S"]))
    in_order(cards, "damage_paid", "m9_piles")
    assert ids(cards)[-1] == "m9_piles" and g.decision["kind"] == "pile_rescue"
    c = card(cards, "m9_piles")
    assert c.title == "Captured piles" and c.number == ""
    assert c.lines == ["End of turn: banish a hand card", "to rescue a pile's top to the discard,",
                       "or every pile's top goes to its bottom", "Pile tops: %s" % tops]
    fits(cards)
    rescued = g.cards[g.extra["captured"][0][0]].label()
    cards = cards_for(g, lambda: g.decide({"type": "pile_rescue", "player": 0, "pile": 0, "card": "8S"}))
    assert card(cards, "turn").lines[0] == "You banished 8♠: %s rescued" % rescued
    fits(cards)


def test_m9_rotate_is_a_line_and_two_players_are_named():
    g = _m9(players=2)
    cards = cards_for(g, lambda: g.suffer(["9S", "6S"]))
    c = card(cards, "m9_piles")
    assert c.lines[:2] == ["End of turn: Ana may banish a hand card", "to rescue a pile's top to the discard,"]
    assert "You" not in everything(cards)
    cards = cards_for(g, lambda: g.decide({"type": "pile_rotate", "player": 0}))
    assert cards[0].lines[0].startswith("Piles rotated: tops ")
    fits(cards)


def test_m9_switched_off_leaves_no_card_and_no_line():
    g = _m9()
    cards = cards_for(g, lambda: g.suffer(["9S", "6S"]), off("m9_piles"))
    assert "m9_piles" not in ids(cards)
    cards = cards_for(g, lambda: g.decide({"type": "pile_rotate", "player": 0}), off("m9_piles"))
    assert "rotated" not in everything(cards)


# ---------------------------------------------------------------------------- 10 Pride to Fall
def test_m10_zone_grows_at_the_start_and_after_turn():
    g = mission(10, cards=list(M.MAGE_DECK) + [M.GORAN_RENEWED, M.ASH], corrupted=CORRUPT)
    cards = start_cards(g)
    assert ids(cards) == ["battle_start", "m10_zone"]
    c = cards[1]
    assert c.title == "Zone: enemy stronger" and c.number == "1"
    assert c.lines == ["Start of turn: reserve top A♠ → zone", "Enemy attack +1", "2 of Spades: attack 3"]
    cards = turn_end(g, play="AH", hand=("9C", "8C", "7C"))
    in_order(cards, "damage_paid", "turn", "m10_zone")
    assert card(cards, "m10_zone").lines[1:] == ["Enemy attack +3", "2 of Spades: attack 5"]
    fits(cards)
    g = mission(10, cards=list(M.MAGE_DECK) + [M.GORAN_RENEWED, M.ASH], corrupted=CORRUPT)
    assert ids(start_cards(g, off("m10_zone"))) == ["battle_start"]


def test_m10_zone_doubles_for_a_warrior_and_says_when_the_reserve_is_empty():
    g = m10("5C")
    set_hand(g, ["2S", "10S", "10C", "10D", "9S", "9C"])
    g.play(["2S"])
    g.tavern[:] = []
    cards = suffer_cards(g)
    in_order(cards, "turn", "m10_zone")
    c = card(cards, "m10_zone")
    assert c.lines[:2] == ["Start of turn: reserve empty,", "nothing joins the zone"]
    assert c.lines[2].endswith(", then ×2 (warrior)")
    fits(cards)
    # a zone worth two digits still fits (the fuzz found 41 characters)
    from app.info_missions import _m10_bonus
    from info_helpers import ON
    from app import info as core
    ctx = core.Ctx(g, [], dict(ON))
    g.mission_zone = [c for c in g.cards if g.cards[c].value == 10 and g.cards[c].is_number][:3]
    assert len(_m10_bonus(ctx, g.mission_zone)) <= 40 and "×2" in _m10_bonus(ctx, g.mission_zone)


def test_m10_cleric_enemy_comes_first_at_the_end_of_the_turn():
    g = m10("3H")
    set_discard(g, ["5S"])
    cards = turn_end(g, play="2C", hand=("9C", "8C", "7C"))
    in_order(cards, "damage_paid", "m10_cleric", "turn", "m10_zone")
    c = card(cards, "m10_cleric")
    assert c.title == "Cleric enemy" and c.number == "9" and c.icon is None
    assert c.lines == ["End of turn: the corrupted cleric takes", "the top discard (9♣) into the zone",
                       "Enemy attack +9 (zone 10)"]
    assert c.face_args({})["icon"] == "H"
    fits(cards)
    g = m10("3H")
    cards = turn_end(g, play="2C", hand=("9C", "8C", "7C"), settings=off("m10_cleric"))
    assert "m10_cleric" not in ids(cards) and "cleric" not in everything(cards)


def test_m10_cleric_enemy_with_the_discard_pile_empty():
    g = m10("3H")
    set_hand(g, ["10S", "9C"])
    set_discard(g, [])
    cards = cards_for(g, lambda: g.play(["10S"]))     # shielded to 0: no damage, nothing discarded
    in_order(cards, "m10_cleric", "turn", "m10_zone")
    assert card(cards, "m10_cleric").lines[-1] == "Discard pile empty: nothing moves"
    fits(cards)


def test_m10_bard_enemy_comes_before_its_box_and_the_card_fed_is_a_line():
    g = m10("4D")
    cards = turn_end(g, play="2C", hand=("10C", "10S", "10H", "6S"))
    in_order(cards, "damage_paid", "m10_bard")
    assert ids(cards)[-1] == "m10_bard" and g.decision["kind"] == "zone_feed"
    c = card(cards, "m10_bard")
    assert c.title == "Bard enemy" and c.face_args({})["icon"] == "D"
    assert c.lines == ["End of turn: put a hand card in the zone", "Enemy attack + its strength"]
    cards = cards_for(g, lambda: g.decide({"type": "zone_feed", "player": 0, "card": "6S"}))
    in_order(cards, "turn", "m10_zone")
    assert card(cards, "turn").lines[0] == "You put 6♠ in the zone: attack +6"
    fits(cards)


def test_m10_bard_enemy_with_an_empty_hand_and_with_two_players():
    g = m10("4D")
    g.enemy.attack = 1
    set_hand(g, ["2C", "10C"])
    g.play(["2C"])
    cards = cards_for(g, lambda: g.suffer(["10C"]))
    in_order(cards, "damage_paid", "m10_bard", "turn")
    assert card(cards, "m10_bard").lines[-1] == "Hand empty: nothing moves"
    g = m10("4D", players=2)
    cards = turn_end(g, play="2C", hand=("10C", "10S", "10H", "6S"))
    assert card(cards, "m10_bard").lines[0] == "Ana puts a hand card in the zone"
    cards = cards_for(g, lambda: g.decide({"type": "zone_feed", "player": 0, "card": "6S"}))
    assert "Ana put 6♠ in the zone" in everything(cards) and "You" not in everything(cards)
    fits(cards)


def test_m10_bard_enemy_keeps_a_long_name_whole():
    g = m10("4D", players=2, names=LONG)
    cards = turn_end(g, play="2C", hand=("10C", "10S", "10H", "6S"))
    assert card(cards, "m10_bard").lines == ["End of turn: Bartholomew Quill must put", "a hand card in the zone",
                                             "Enemy attack + its strength"]
    assert "…" not in everything(cards)
    fits(cards)


def test_m10_bard_switched_off_leaves_no_card_and_no_line():
    g = m10("4D")
    cards = turn_end(g, play="2C", hand=("10C", "10S", "10H", "6S"), settings=off("m10_bard"))
    assert "m10_bard" not in ids(cards)
    cards = cards_for(g, lambda: g.decide({"type": "zone_feed", "player": 0, "card": "6S"}), off("m10_bard"))
    assert "6♠" not in everything(cards)


# ---------------------------------------------------------------------------- 11 Descent Into Darkness
def test_m11_beast_at_the_start_comes_before_its_box_and_its_answer_is_a_line():
    g = m11()
    cards = start_cards(g)
    assert ids(cards) == ["battle_start", "m11_beast"] and g.decision["kind"] == "beast_discard"
    c = cards[1]
    assert c.title == "Beast: Cleric" and c.icon == "H" and c.number == ""
    # the Turn card leaves the enemy to the Beast card, which states it even when nothing moves yet
    assert c.lines == ["Start of turn: discard a hand card", "Justicar: attack 10"]
    hand_card = g.legal_actions()[0]["card"]
    label = g.cards[hand_card].label()
    cards = cards_for(g, lambda: g.decide(g.legal_actions()[0]))
    assert cards == [] and g.extra["info_carry"]["lines"][0].startswith("You discarded %s" % label)
    fits(start_cards(m11()))
    g = m11()
    assert "m11_beast" not in ids(start_cards(g, off("m11_beast")))
    assert cards_for(g, lambda: g.decide(g.legal_actions()[0]), off("m11_beast")) == []
    assert "lines" not in g.extra.get("info_carry", {})


def test_m11_warrior_and_paladin_beasts_change_the_enemy():
    g = m11(beasts=["B_C", "B_S", "B_D", "B_H"])
    set_hand(g, ["AS", "10S", "10C", "10D"])
    set_discard(g, [])
    g.play(["AS"])
    cards = suffer_cards(g, hand=("10S", "10C", "10D"))
    in_order(cards, "damage_paid", "turn", "m11_beast")
    c = card(cards, "m11_beast")
    assert c.title == "Beast: Warrior" and c.icon == "C" and c.face_args({})["edge"] == T.SUIT_COLOR["C"]
    # the 10 moves from the discard top to the banished top: the same attack, a new immunity
    assert c.lines == ["Top discard 10♠ is banished", "Justicar: attack 20 · immune ♠"]
    fits(cards)
    cards = turn_end(g, play="AS", hand=("10S", "10C", "10D"))
    c = card(cards, "m11_beast")
    assert c.title == "Beast: Paladin" and c.icon == "S"
    assert c.lines == ["Reserve top A♥ is discarded", "Justicar: attack 18 → 9 · immune ♥"]
    fits(cards)


def test_m11_beast_with_nothing_to_move_and_the_reshuffle():
    g = m11(beasts=["B_S"])
    g.extra["beasts_out"] = ["B_H", "B_C", "B_D"]
    set_hand(g, ["AS", "10S", "10C", "10D"])
    g.play(["AS"])
    g.tavern[:] = []
    cards = suffer_cards(g, hand=("10S", "10C", "10D"))
    c = card(cards, "m11_beast")
    assert c.lines == ["Nothing to move: no effect", "Justicar: attack 19 · immune ♣",
                       "All four out: the beasts reshuffle"]
    fits(cards)


def test_m11_two_players_name_the_player():
    g = m11(players=2)
    cards = start_cards(g)
    assert ids(cards) == ["battle_start", "turn", "m11_beast"]
    assert card(cards, "m11_beast").lines == ["Start of turn: Ana discards a hand card", "Justicar: attack 10"]


# ---------------------------------------------------------------------------- 12 Decay to Growth
def _m12():
    return mission(12, cards=list(M.MAGE_DECK) + [M.ESME_REBORN, M.ASH], corrupted=CORRUPT[:4] + CORRUPT[5:])


def test_m12_zone_grows_after_turn_and_says_when_the_pile_is_empty():
    g = _m12()
    assert "m12_zone" not in ids(start_cards(g))          # nothing banished yet at the start: no card
    rig(g, "banished", ["2C", "6D"])
    cards = turn_end(g, hand=("10S", "10C", "10H", "9C"))
    in_order(cards, "damage_paid", "turn", "m12_zone")
    c = card(cards, "m12_zone")
    assert c.title == "Zone: stronger, immune" and c.number == "6"
    assert c.lines == ["Start of turn: banished top 6♦ → zone", "Enemy attack +6 from the zone",
                       "Immune to the zone's classes: ♦", "Bard Queen: attack 20"]
    g.banished[:] = []
    cards = turn_end(g, hand=("10S", "10C", "10H", "9C"))
    c = card(cards, "m12_zone")
    assert c.number == "" and c.lines[:2] == ["Start of turn: banished pile empty,", "nothing joins the zone"]
    fits(cards)
    rig(g, "banished", ["2C", "6D"])
    cards = turn_end(g, hand=("10S", "10C", "10H", "9C"), settings=off("m12_zone"))
    assert "m12_zone" not in ids(cards) and "6♦" not in everything(cards)


def test_m12_exact_kill_skips_the_zone_card():
    g = _m12()
    g.enemy.hp = 1
    g.enemy.suits = ()
    set_hand(g, ["AS", "9S"])
    cards = cards_for(g, lambda: g.play(["AS"]))
    assert "zone_skip" in [e["t"] for e in g.last_events] and "m12_zone" not in ids(cards)


def test_missions_one_and_four_have_no_cards_of_their_own():
    mine = set(r[0] for r in info.ROWS if r[1] == "Missions")
    for n in (1, 4):
        g = mission(n, cards=M.MAGE_DECK)
        cards = start_cards(g) + turn_end(g, play="3C", hand=("10S", "10C", "10D"))
        assert not set(ids(cards)) & mine
