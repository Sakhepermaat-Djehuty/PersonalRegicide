"""Info pop-ups of the Turn, Attack and Jester groups (app/info_turn.py), from real game
flows: Battle start, Turn, Yield, Corrupted, Restored, Declared, the three relics, the
Evergreen Mother's two cards and the four Jester cards. Each card shows in its place in
the queue, keeps to the size limits and leaves nothing when its row is switched off;
cards going into a hidden hand or the reserve are never named."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()

from app import info  # noqa: E402
from app.info_turn import enemy_lines  # noqa: E402
from helpers import _pull, new_game, set_discard, set_enemy, set_hand, set_mission_enemy, set_tavern_top  # noqa: E402
from info_helpers import card, cards_for, fits, ids, start_cards, text  # noqa: E402
from regicide.campaign import CampaignState  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402

NAMES = ["Ana", "Ben", "Cy"]
CORRUPT = ("2S", "3H", "4D", "5C", "6C", "7S", "8H", "9D")
RESTORED = ("2S", "3H", "4D", "5C", "7S", "8H", "9D")


def off(row_id):
    return {"info_popups_off": [row_id]}


def everything(cards):
    return "\n".join(text(c) for c in cards)


def in_order(cards, *row_ids):
    """These rows' cards come in this order (rows absent from the queue are passed over)."""
    seen = [r for r in row_ids if r in ids(cards)]
    assert [i for i in ids(cards) if i in seen] == [r for r in seen], (ids(cards), row_ids)


def legacy(players=1, seed=100, number=1, cards=(), relics=(), corrupted=(), mercs=(), names=NAMES):
    """A Legacy attempt at mission ``number`` with these extra party cards, relics and
    corrupted cards (or mercenaries hired for it)."""
    c = CampaignState.new(players, list(names)[:players], seed=seed)
    c.mission = number
    c.completed = list(range(1, number))
    for d in cards:
        if P.find(c.party, str(d["id"])) is None:
            P.add_card(c.party, dict(d))
    for cid in corrupted:
        P.add_flag(c.party, cid, "corrupted")
    c.relics.extend(relics)
    if mercs:
        c.m_box_opened = True
        c.coins = 20
        for m in mercs:
            c.hire(m)
    return c.start_attempt(seed=seed)


def mission(n, players=1, cards=(), corrupted=(), beast=None, seed=None):
    """A Legacy mission prepared the way the campaign does it (setup choices taken)."""
    seed = seed or 900 + n
    c = CampaignState.new(players, NAMES[:players], seed=seed)
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


def evergreen(location="A", banes=(), boons=(), players=1, seed=5000):
    """An Evergreen attempt with the restored Mother and some restored party cards."""
    c = CampaignState.new(players, NAMES[:players], seed=seed)
    c.mission = 12
    c.completed = list(range(1, 13))
    c.finished = True
    c.relics.append("mother_restored")
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    for cid in RESTORED:
        P.add_flag(c.party, cid, "restored")
    c.evergreen["setup"] = {"location": location, "banes": sorted(banes), "boons": sorted(boons)}
    return c.start_evergreen_attempt(seed=seed)


def rig(g, pile, card_ids):
    """Make a pile hold exactly these cards (its old cards go to the reserve)."""
    old = list(getattr(g, pile))
    setattr(g, pile, [])
    g.tavern.extend(old)
    for cid in card_ids:
        _pull(g, cid)
    setattr(g, pile, list(card_ids))


def m12_restored():
    g = mission(12, cards=list(M.MAGE_DECK) + [M.ESME_REBORN, M.ASH], corrupted=RESTORED)
    rest = [x for x in g.cards if g.cards[x].has("restored") and x != "ESME6E"]
    return g, rest


# ---------------------------------------------------------------------------- Battle start
def test_battle_start_opens_a_base_game_with_the_first_enemy_and_no_turn_card_solo():
    g = new_game(1, seed=3)
    cards = start_cards(g)
    assert ids(cards)[0] == "battle_start" and "turn" not in ids(cards) and "new_enemy" not in ids(cards)
    c = card(cards, "battle_start")
    assert c.title == "Regicide" and c.number == "" and c.icon is None
    assert c.lines[0] == "12 enemies · hand limit 8"
    assert c.lines[1] == "First: %s 10/20, immune ♠" % g.enemy.name
    assert "2 Jesters: a new hand each" in c.lines
    assert c.sounds == ["info_battle_start", "mission_start"]
    fits(cards)
    gone = start_cards(new_game(1, seed=3), off("battle_start"))
    assert "battle_start" not in ids(gone) and "First:" not in everything(gone)


def test_battle_start_names_the_mission_then_a_turn_card_says_who_starts_with_two_players():
    g = legacy(2, seed=1, number=1)
    cards = start_cards(g)
    assert ids(cards)[:2] == ["battle_start", "turn"]
    c = card(cards, "battle_start")
    assert c.title == "Call to Arms" and c.number == "1"
    assert c.lines[0] == "12 enemies · hand limit 7"
    assert "Exact kill: enemy on top of the reserve" in c.lines
    t = card(cards, "turn")
    assert t.title == "Ana's turn" and t.number == "1" and t.lines[0] == "Hand 7 of 7"
    fits(cards)
    m5 = start_cards(mission(5, cards=[M.GORAN], beast="B_H"))
    c = card(m5, "battle_start")
    assert c.title == "High and Mighty" and c.number == "5"
    assert c.lines[-2:] == ["Myla starts in the banished pile", "End of turn: banished top joins the zone"]
    fits(m5)


def test_battle_start_in_evergreen_is_the_location_with_one_setup_note_and_a_long_name_split():
    g = evergreen("A", banes=(2, 5), boons=(27,), players=2)
    cards = start_cards(g)
    c = card(cards, "battle_start")
    assert c.title == "Shrine" and c.number == ""
    assert c.lines[0] == "9 enemies · hand limit 8"
    assert c.lines[1] == "First: Phase II Experiment 15/30"        # too long with the immunity
    assert c.lines[2].startswith("Immune to ")
    assert "Mental Health Day: 30 to the discard" in c.lines and "Too Easy!: hand limit +1" not in c.lines
    assert c.lines[-1] == "End of turn: reserve top joins the zone"
    t = card(cards, "turn")
    assert t.lines[1:3] == ["Phase II Experiment", "Attack 15, health 30/30"]
    fits(cards)
    lake = card(start_cards(evergreen("E", boons=(27,))), "battle_start")
    assert lake.title == "Lake" and "Too Easy!: hand limit +1" in lake.lines


def test_battle_start_base_wording_names_the_tavern_deck():
    cards = start_cards(new_game(3, seed=3))
    assert "1 Jester in the tavern deck" in card(cards, "battle_start").lines
    assert card(cards, "turn").title == "Player 1's turn"


def test_battle_start_holds_the_first_enemy_as_revealed_when_the_first_turn_changes_it():
    g = mission(10, cards=list(M.MAGE_DECK) + [M.GORAN], corrupted=CORRUPT, beast="B_H", seed=944)
    assert g.enemy_attack > g.enemy.attack                 # the zone fed it at the first turn's start
    cards = start_cards(g)
    e = g.enemy
    assert card(cards, "battle_start").lines[1] == "First: %s %d/%d, immune ♠" % (e.name, e.attack, e.hp)
    in_order(cards, "battle_start", "m10_zone")
    g = mission(11, cards=list(M.MAGE_DECK) + [M.GORAN], corrupted=CORRUPT, beast="B_H", seed=962)
    assert any(ev["t"] == "beast_effect" for ev in g.last_events) and g.rules.immune_suits(g)
    e = g.enemy
    assert card(start_cards(g), "battle_start").lines[1] == "First: %s %d/%d" % (e.name, e.attack, e.hp)


def test_battle_start_notes_keep_to_a_line():
    from app import info_turn
    notes = [n for pair in info_turn.MISSION_NOTES.values() for n in pair]
    notes += list(info_turn.LOCATION_RULES.values()) + list(info_turn.LOCATION_SETUP.values())
    notes += [n for _, _, n in info_turn.EVERGREEN_SETUP]
    assert [n for n in notes if len(n) > 40] == []
    cards = start_cards(evergreen("A", banes=(6,), players=3))
    assert "Full Moon: Ash and mage ace set aside" in card(cards, "battle_start").lines
    fits(cards)


# ---------------------------------------------------------------------------- Turn
def test_turn_after_the_damage_is_paid_holds_the_hand_and_the_enemy():
    g = new_game(1, seed=5)
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "9S", "8D", "4D"])
    g.play(["3C"])
    cards = cards_for(g, lambda: g.suffer(["9S", "8D"]))
    assert ids(cards)[-1] == "turn"
    t = card(cards, "turn")
    assert t.title == "Your turn" and t.number == "2" and t.icon is None
    assert t.lines[:2] == ["Hand 1 of 8", "%s: attack 10, health 14/20" % g.enemy.name]
    assert t.sounds == ["info_turn"]
    fits(cards)
    g = new_game(1, seed=5)
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "9S", "8D", "4D"])
    g.play(["3C"])
    gone = cards_for(g, lambda: g.suffer(["9S", "8D"]), off("turn"))
    assert "turn" not in ids(gone) and "Hand 1 of 8" not in everything(gone)


def test_turn_with_two_players_names_the_player_and_no_hand_card():
    g = new_game(2, seed=7)
    set_enemy(g, "J", "H")
    set_hand(g, ["5H", "9S"], 0)
    set_hand(g, ["4C", "8S", "6D"], 1)
    g.yield_turn()
    cards = cards_for(g, lambda: g.suffer(["9S", "5H"]))
    t = card(cards, "turn")
    assert t.title == "Player 2's turn" and t.lines[0] == "Hand 3 of 7"
    for cid in g.players[1].hand:
        assert g.card(cid).label() not in text(t)
    fits(cards)


def test_turn_after_a_kill_is_the_same_player_again_and_skips_end_of_turn_effects_in_a_mission():
    g = new_game(1, seed=5)
    set_enemy(g, "J", "H", hp=10)
    set_hand(g, ["5C", "9S"])
    cards = cards_for(g, lambda: g.play(["5C"]))
    t = card(cards, "turn")
    assert ids(cards)[-1] == "turn" and t.title == "Your turn again"
    assert "After a kill: no end-of-turn effects" not in t.lines        # the base game has none
    g = mission(3, players=2, cards=list(M.MAGE_DECK) + [M.GORAN], beast="B_H")
    g.enemy.hp = 5
    g.enemy.suits = ()
    set_hand(g, ["5C", "9S"], 0)
    cards = cards_for(g, lambda: g.play(["5C"]))
    t = card(cards, "turn")
    assert t.title == "Ana again" and "After a kill: no end-of-turn effects" in t.lines
    fits(cards)


def test_turn_after_an_exact_kill_says_no_beast_or_no_zone_card_this_turn():
    g = mission(11, cards=list(M.MAGE_DECK) + [M.GORAN_RENEWED, M.ASH], corrupted=CORRUPT)
    if g.decision:
        g.decide(g.legal_actions()[0])
    g.enemy.hp = 1
    set_hand(g, ["AS", "9S"])
    cards = cards_for(g, lambda: g.play(["AS"]))
    assert "Exact kill: no beast this turn" in card(cards, "turn").lines
    fits(cards)
    g, _ = m12_restored()
    g.enemy.hp = 1
    g.enemy.suits = ()
    set_hand(g, ["AS", "9S"])
    cards = cards_for(g, lambda: g.play(["AS"]))
    while g.decision:
        a = dict(g.legal_actions()[0])
        if "pick_from" in a:
            a["cards"] = list(a["pick_from"])
        cards = cards_for(g, lambda: g.decide(a))
    assert "Exact kill: no zone card this turn" in card(cards, "turn").lines
    fits(cards)


def test_turn_leaves_out_the_enemy_when_a_start_of_turn_card_changes_it():
    g = mission(10, players=2, cards=list(M.MAGE_DECK) + [M.GORAN], corrupted=CORRUPT, beast="B_H")
    t = card(start_cards(g), "turn")
    assert t.lines == ["Hand %d of 7" % len(g.players[0].hand)]     # the zone grows right after
    for g in (mission(7, players=2, cards=list(M.MAGE_DECK) + [M.GORAN], beast="B_H"), evergreen("E", players=2)):
        cards = start_cards(g)                              # a pilgrim joins the zone: the enemy stays
        assert any(e["t"] == "zone_add" for e in g.last_events)
        assert card(cards, "turn").lines[1:] == enemy_lines(g), card(cards, "turn").lines
    g = evergreen("A", banes=(16, 22), seed=5109)          # the banes' cards do not state the enemy
    g.enemy.suits = ()
    set_hand(g, ["AS", "10S", "10C", "10D"])
    set_discard(g, ["2D"])
    g.play(["AS"])
    cards = cards_for(g, lambda: g.suffer(["10S", "10C"]))
    assert [e["n"] for e in g.last_events if e["t"] == "bane"] == [16, 22]
    in_order(cards, "turn", "bane16", "bane22")
    assert card(cards, "turn").lines[1:] == enemy_lines(g)


# ---------------------------------------------------------------------------- Yield
def test_yield_names_the_player_and_comes_first():
    g = new_game(2, seed=7)
    set_enemy(g, "J", "H")
    set_hand(g, ["5H", "9S"], 0)
    set_hand(g, ["4C", "8S"], 1)
    cards = cards_for(g, lambda: g.yield_turn())
    assert ids(cards)[0] == "yield"
    y = card(cards, "yield")
    assert y.title == "Yield" and y.number == ""
    assert y.lines == ["Player 1 yields: no attack this turn", "The enemy strikes next"]
    assert y.sounds == ["info_yield", "yield"]
    fits(cards)
    g = new_game(2, seed=7)
    set_enemy(g, "J", "H")
    set_hand(g, ["5H", "9S"], 0)
    gone = cards_for(g, lambda: g.yield_turn(), off("yield"))
    assert "yield" not in ids(gone) and "yields" not in everything(gone)


def _claimed():
    g = legacy(3, seed=3)
    set_enemy(g, "J", "H")
    jid = [x for x in g.cards if g.cards[x].is_jester][0]
    set_hand(g, [jid, "9S"], 0)
    set_hand(g, ["5H", "8S"], 1)
    set_hand(g, ["2C"], 2)
    return g, jid


def test_a_claimer_who_yields_spends_the_jester():
    g, jid = _claimed()
    g.play([jid])
    g.choose_next(1)
    cards = cards_for(g, lambda: g.yield_turn())
    y = card(cards, "yield")
    assert y.lines == ["Ben yields: no attack this turn", "The enemy strikes next",
                       "The claimed Jester's chance is spent"]
    fits(cards)


LONG = ["Maximilian Ash", "Bartholomew Quill", "Constantina Vale"]


def test_long_names_stay_on_the_yield_mother_and_flute_cards():
    g = legacy(3, seed=3, names=LONG)
    set_enemy(g, "J", "H")
    set_hand(g, ["5H", "9S"], 0)
    cards = cards_for(g, lambda: g.yield_turn())
    assert card(cards, "yield").lines[0] == "Maximilian Ash yields: no attack"
    g = legacy(2, seed=331, relics=("mother",), corrupted=("6C",), names=LONG)
    set_enemy(g, "J", "H")
    set_hand(g, ["6C", "9S"], 0)
    set_hand(g, ["4D", "8S"], 1)
    c = card(cards_for(g, lambda: g.play(["6C"])), "mother_corrupt")
    assert c.lines[1] == "Bartholomew Quill banishes a hand card"
    g = legacy(3, seed=301, relics=("flute",), names=LONG)
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "9S"], 0)
    set_hand(g, ["3D", "8S"], 1)
    set_hand(g, ["3H", "8C"], 2)
    cards = cards_for(g, lambda: g.play(["3C"]))
    assert card(cards, "kinfolk_flute").lines[-1] == "Asked in turn, from Bartholomew Quill"
    fits(cards)


# ---------------------------------------------------------------------------- Corrupted, Restored
def test_corrupted_card_tells_what_it_banished_before_its_class_cards():
    g = legacy(1, seed=470, corrupted=("6C",))
    set_enemy(g, "J", "C")
    set_hand(g, ["6C", "9S", "8S"])
    top = g.tavern[0]
    cards = cards_for(g, lambda: g.play(["6C"]))
    assert ids(cards)[0] == "corrupted"
    in_order(cards, "corrupted", "warrior", "damage")
    c = card(cards, "corrupted")
    assert c.title == "Corrupted" and c.number == "6" and c.icon is None
    assert c.lines == ["6♣ enters play corrupted", "Reserve top banished: %s" % g.card(top).label(),
                       "Its ♣ ignores immunity"]
    assert c.face_args({})["edge"] == info.T.CORRUPTED
    fits(cards)
    g = legacy(1, seed=471, corrupted=("6C",))
    set_enemy(g, "J", "H")
    set_hand(g, ["6C", "9S", "8S"])
    g.discard.extend(g.tavern)
    g.tavern = []
    cards = cards_for(g, lambda: g.play(["6C"]))
    assert card(cards, "corrupted").lines[1] == "Nothing to banish: reserve empty"
    g = legacy(1, seed=470, corrupted=("6C",))
    set_enemy(g, "J", "C")
    set_hand(g, ["6C", "9S", "8S"])
    gone = cards_for(g, lambda: g.play(["6C"]), off("corrupted"))
    assert "corrupted" not in ids(gone)
    assert "enters play corrupted" not in everything(gone) and "banished" not in everything(gone)


def test_corrupted_cards_and_the_solo_jester_never_ignore_mylas_immunity():
    g = mission(9, cards=[M.GORAN], corrupted=("7S",), beast="B_H")
    set_mission_enemy(g, "MYLA_BOSS")
    set_hand(g, ["7S", "9C", "8C"])
    cards = cards_for(g, lambda: g.play(["7S"]))
    assert card(cards, "corrupted").lines[2] == "Its ♠ ignores immunity (not Myla's)"
    g = mission(9, cards=[M.GORAN], beast="B_H")
    set_mission_enemy(g, "MYLA_BOSS")
    set_hand(g, ["9C", "8C"])
    cards = cards_for(g, lambda: g.use_solo_jester({"suit": "S"}))
    assert card(cards, "solo_jester_attack").lines[1] == "Myla's ♠ immunity is never ignored"
    fits(cards)


def test_a_restored_reserve_top_is_not_named_and_the_mother_follows_the_corrupted_card():
    g = evergreen("A")
    g.enemy.suits = ()
    six = g.cards["6C"]
    g.cards["6C"] = six.with_changes(flags=tuple(six.flags) + ("corrupted",))
    set_hand(g, ["6C", "10S", "10C", "10D"])
    set_tavern_top(g, ["8H"])
    cards = cards_for(g, lambda: g.play(["6C"]))
    assert ids(cards)[:2] == ["corrupted", "mother_restored"]
    assert card(cards, "corrupted").lines[1] == "Reserve top is restored: not banished"
    assert "8♥" not in everything(cards)
    fits(cards)


def test_restored_card_returns_the_banished_top_unnamed_under_the_reserve():
    g, rest = m12_restored()
    rig(g, "banished", ["2C", "6D"])
    r = rest[0]
    set_hand(g, [r, "10S", "10C", "10H", "9C"])
    cards = cards_for(g, lambda: g.play([r]))
    assert ids(cards)[0] == "restored"
    c = card(cards, "restored")
    assert c.title == "Restored" and c.number == str(g.card(r).value)
    assert c.lines[0] == "%s enters play restored" % g.card(r).label()
    assert c.lines[1] == "Banished top goes under the reserve"
    assert "6♦" not in everything(cards)                   # it is in the reserve now
    assert c.face_args({})["edge"] == info.T.RESTORED
    fits(cards)
    gone_g, rest = m12_restored()
    rig(gone_g, "banished", ["2C", "6D"])
    set_hand(gone_g, [rest[0], "10S", "10C"])
    gone = cards_for(gone_g, lambda: gone_g.play([rest[0]]), off("restored"))
    assert "restored" not in ids(gone) and "restored" not in everything(gone)


def test_restored_card_in_mission_12_sends_a_corrupted_top_to_the_banished_bottom_or_finds_nothing():
    g, rest = m12_restored()
    corrupted = [x for x in g.castle if g.cards[x].has("corrupted")][0]
    rig(g, "banished", [corrupted])
    set_hand(g, [rest[0], "10S", "10C"])
    cards = cards_for(g, lambda: g.play([rest[0]]))
    assert card(cards, "restored").lines[1].endswith("is corrupted → banished bottom")
    fits(cards)
    g, rest = m12_restored()
    rig(g, "banished", [])
    set_hand(g, [rest[0], "10S", "10C"])
    cards = cards_for(g, lambda: g.play([rest[0]]))
    assert card(cards, "restored").lines[1] == "Banished pile empty: nothing returns"


def test_a_restored_card_with_nothing_to_return_still_opens_its_attack():
    """With or without a banished card to return, the Restored card is the attack's first
    card and carries its formation line."""
    def restored(banished):
        g = evergreen("A")
        g.enemy.suits = ()
        rig(g, "banished", banished)
        set_hand(g, ["2S", "2H", "10S", "10C"])
        return card(cards_for(g, lambda: g.play(["2S", "2H"])), "restored")
    empty, back = restored([]), restored(["6D"])
    assert empty.lines[1:3] == ["2♠ enters play restored", "Banished pile empty: nothing returns"]
    assert back.lines[1:3] == ["2♠ enters play restored", "Banished top goes under the reserve"]
    assert empty.lines[0] == back.lines[0] and "2♥" in empty.lines[0]


# ---------------------------------------------------------------------------- Declared
def test_declared_follows_its_box_with_the_value_and_the_new_strength():
    g = legacy(1, seed=480, mercs=("merc_25C", "merc_ace_1"))
    set_enemy(g, "J", "H")
    set_hand(g, ["M25C", "9S", "8S", "MA_1", "7D"])
    assert cards_for(g, lambda: g.play(["M25C"])) == []                  # the box asks itself
    cards = cards_for(g, lambda: g.decide({"type": "declare_value", "player": 0, "option": "5"}))
    assert ids(cards)[0] == "declared"
    in_order(cards, "declared", "warrior", "damage")
    c = card(cards, "declared")
    assert c.title == "Declared" and c.number == "5" and c.icon == "2/5"
    assert c.lines[-2:] == ["2/5♣ counts 5", "Attack strength 2 → 5"]
    fits(cards)
    g.suffer(["9S", "8S"])
    set_hand(g, ["MA_1", "7D", "9S", "8S"])
    g.play(["MA_1", "7D"])
    cards = cards_for(g, lambda: g.decide({"type": "declare_class", "player": 0, "option": "C"}))
    c = card(cards, "declared")
    assert c.icon == "C" and c.number == "8" and c.face_args({})["edge"] == info.T.SUIT_COLOR["C"]
    assert c.lines[-2:] == ["Wild Animal is a Warrior while in play", "Its Warrior power joins this attack"]
    fits(cards)


def test_declared_by_a_kinfolk_set_is_forced_and_its_row_off_leaves_nothing():
    g = legacy(1, seed=481, mercs=("merc_25C",))
    set_enemy(g, "J", "H")
    set_hand(g, ["M25C", "5S", "9S", "8S"])
    cards = cards_for(g, lambda: g.play(["M25C", "5S"]))
    c = card(cards, "declared")
    assert c.number == "10" and c.lines[-3:] == ["2/5♣ counts 5", "Forced by the kinfolk set", "Attack strength 10"]
    in_order(cards, "declared", "warrior", "paladin", "defeated", "turn")
    fits(cards)
    g = legacy(1, seed=481, mercs=("merc_25C",))
    set_enemy(g, "J", "H")
    set_hand(g, ["M25C", "5S", "9S", "8S"])
    gone = cards_for(g, lambda: g.play(["M25C", "5S"]), off("declared"))
    assert "declared" not in ids(gone) and "counts 5" not in everything(gone)


# ---------------------------------------------------------------------------- Kinfolk Flute
def test_kinfolk_flute_solo_store_then_its_cards_are_a_line_on_the_next_card():
    g = legacy(1, seed=300, relics=("flute",))
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "3S", "9S", "8D"])
    cards = cards_for(g, lambda: g.special({"type": "special", "name": "flute_store", "card": "3C"}))
    assert ids(cards) == ["kinfolk_flute"]
    c = cards[0]
    assert c.title == "Kinfolk Flute" and c.number == "3"
    assert c.lines == ["Stored 3♣ on the flute (once a turn)", "Play flute cards in a kinfolk set",
                       "as if from your hand"]
    cards = cards_for(g, lambda: g.play(["3S", "3C"]))
    assert "3♣ from the flute" in cards[0].lines
    fits(cards)
    g = legacy(1, seed=300, relics=("flute",))
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "3S", "9S", "8D"])
    assert cards_for(g, lambda: g.special({"type": "special", "name": "flute_store", "card": "3C"}),
                     off("kinfolk_flute")) == []
    gone = cards_for(g, lambda: g.play(["3S", "3C"]), off("kinfolk_flute"))
    assert "flute" not in everything(gone).lower()


def _flute_three():
    g = legacy(3, seed=301, relics=("flute",))
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "9S"], 0)
    set_hand(g, ["3D", "8S"], 1)
    set_hand(g, ["3H", "8C"], 2)
    return g


def test_kinfolk_flute_with_three_players_asks_once_and_the_addition_is_a_line():
    g = _flute_three()
    cards = cards_for(g, lambda: g.play(["3C"]))
    assert ids(cards)[-1] == "kinfolk_flute"
    c = card(cards, "kinfolk_flute")
    assert c.number == "3" and c.icon is None
    assert c.lines == ["Others may add cards of strength 3", "to make a kinfolk set of up to 10",
                       "No animal companions", "Asked in turn: Ben, Cy"]
    assert c.sounds == ["info_kinfolk_flute"]
    fits(cards)
    assert "kinfolk_flute" not in ids(cards_for(g, lambda: g.decide({"type": "flute_pass", "player": 1})))
    cards = cards_for(g, lambda: g.decide({"type": "flute_add", "player": 2, "card_ids": ["3H"]}))
    assert "Cy adds 3♥ (Kinfolk Flute)" in cards[0].lines
    fits(cards)
    g = _flute_three()
    gone = cards_for(g, lambda: g.play(["3C"]), off("kinfolk_flute"))
    assert "kinfolk_flute" not in ids(gone)
    gone = cards_for(g, lambda: g.decide({"type": "flute_add", "player": 1, "card_ids": ["3D"]}), off("kinfolk_flute"))
    assert "Kinfolk Flute" not in everything(gone)


# ---------------------------------------------------------------------------- Scarlet Whistle
def _whistle_solo():
    g = legacy(1, seed=310, number=5, relics=("whistle",), cards=[M.GORAN])
    set_hand(g, ["AC", "9S", "8S"])
    set_discard(g, ["7D", "2H"])
    return g


def test_scarlet_whistle_solo_offers_the_top_discard_and_the_take_is_a_line():
    g = _whistle_solo()
    cards = cards_for(g, lambda: g.play(["AC"]))
    assert ids(cards)[-1] == "scarlet_whistle"
    c = card(cards, "scarlet_whistle")
    assert c.title == "Scarlet Whistle" and c.number == "1"
    assert c.lines == ["A lone companion or beast attack (1)", "Add the top discard 7♦? 1 → 8"]
    cards = cards_for(g, lambda: g.decide({"type": "whistle_take", "player": 0, "card": "7D"}))
    assert "7♦ joins: 1 → 8" in cards[0].lines
    fits(cards)
    g = _whistle_solo()
    assert "scarlet_whistle" not in ids(cards_for(g, lambda: g.play(["AC"]), off("scarlet_whistle")))
    gone = cards_for(g, lambda: g.decide({"type": "whistle_take", "player": 0, "card": "7D"}), off("scarlet_whistle"))
    assert "joins" not in everything(gone)


def test_scarlet_whistle_with_two_players_lets_one_other_player_add():
    g = legacy(2, seed=312, relics=("whistle",))
    set_enemy(g, "J", "H")
    set_hand(g, ["AC", "9S"], 0)
    set_hand(g, ["7D", "8S"], 1)
    c = card(cards_for(g, lambda: g.play(["AC"])), "scarlet_whistle")
    assert c.lines == ["A lone companion or beast attack (1)", "One other player may add any card",
                       "from hand, except a Jester"]
    cards = cards_for(g, lambda: g.decide({"type": "whistle_add", "player": 1, "card": "7D"}))
    assert "Ben adds 7♦: 1 → 8" in cards[0].lines
    fits(cards)
    g = legacy(3, seed=312, relics=("whistle",))
    set_enemy(g, "J", "H")
    set_hand(g, ["AC", "9S"], 0)
    set_hand(g, ["8S"], 1)
    set_hand(g, ["7D", "8C"], 2)
    assert ids(cards_for(g, lambda: g.play(["AC"])))[-1] == "scarlet_whistle"
    again = cards_for(g, lambda: g.decide({"type": "whistle_pass", "player": 1}))
    assert g.decision["kind"] == "whistle_add" and "scarlet_whistle" not in ids(again)    # asked again: no card
    cards = cards_for(g, lambda: g.decide({"type": "whistle_add", "player": 2, "card": "7D"}))
    assert "Cy adds 7♦: 1 → 8" in cards[0].lines


# ---------------------------------------------------------------------------- Azure Emblem
def _emblem_solo():
    g = legacy(1, seed=320, cards=M.MAGE_DECK, relics=("emblem",))
    set_enemy(g, "K", "H")
    set_hand(g, ["4M", "9S", "8S"])
    set_tavern_top(g, ["2C", "3D", "4S", "5H"])
    return g


def test_azure_emblem_solo_comes_after_the_pick_and_the_keep_is_a_count():
    g = _emblem_solo()
    g.play(["4M"])
    cards = cards_for(g, lambda: g.decide({"type": "mage_pick", "card": "2C"}))
    assert ids(cards)[-1] == "azure_emblem"
    c = card(cards, "azure_emblem")
    assert c.title == "Azure Emblem" and c.number == "4"
    assert c.lines == ["Put one of the other cards you looked at", "back on the reserve? The rest: discard"]
    fits(cards)
    cards = cards_for(g, lambda: g.decide({"type": "emblem_keep", "player": 0, "card": "5H"}))
    lines = cards[0].lines
    assert lines[0].startswith("Mage: 2♣ joins") and lines[1] == "Emblem: 1 card back on the reserve"
    assert "5♥" not in everything(cards)                   # the kept card is on the reserve
    g = _emblem_solo()
    g.play(["4M"])
    assert "azure_emblem" not in ids(cards_for(g, lambda: g.decide({"type": "mage_pick", "card": "2C"}),
                                               off("azure_emblem")))
    gone = cards_for(g, lambda: g.decide({"type": "emblem_keep", "player": 0, "card": "5H"}), off("azure_emblem"))
    assert "Emblem" not in everything(gone)


def test_azure_emblem_with_three_players_follows_the_mage_and_never_names_a_placed_card():
    g = legacy(3, seed=322, cards=M.MAGE_DECK, relics=("emblem",))
    set_enemy(g, "K", "H")
    set_hand(g, ["4M", "9S"], 0)
    set_hand(g, ["6D", "8S"], 1)
    set_hand(g, ["7C", "8C"], 2)
    cards = cards_for(g, lambda: g.play(["4M"]))
    assert ids(cards)[-1] == "azure_emblem"
    in_order(cards, "mage", "azure_emblem")
    c = card(cards, "azure_emblem")
    assert c.number == "4" and c.lines == ["Before the mage looks, each other player",
                                           "may put one hand card on the reserve",
                                           "Once per attack, even for a chained mage"]
    fits(cards)
    seen = []
    first = cards_for(g, lambda: g.decide({"type": "emblem_place", "player": 1, "card": "6D"}))
    assert "azure_emblem" not in ids(first)                 # asked again: no second card
    seen += first
    seen += cards_for(g, lambda: g.decide({"type": "emblem_place", "player": 2, "card": "7C"}))
    assert seen == []                                       # placements wait for the mage's line
    pick = g.decision["eligible"][-1]
    seen += cards_for(g, lambda: g.decide({"type": "mage_pick", "card": pick}))
    # the mage's line, then one counted Emblem line: both fit on the Warrior card
    assert seen[0].id == "warrior" and seen[0].lines[0].startswith("Mage: ")
    assert seen[0].lines[1] == "Emblem: Ben, Cy placed a card each"
    said = everything(seen)
    for placed in ("6♦", "7♣"):
        assert placed not in said
    fits(seen)
    g = legacy(3, seed=322, cards=M.MAGE_DECK, relics=("emblem",))
    set_enemy(g, "K", "H")
    set_hand(g, ["4M", "9S"], 0)
    set_hand(g, ["6D", "8S"], 1)
    set_hand(g, ["7C", "8C"], 2)
    g.play(["4M"])
    g.decide({"type": "emblem_place", "player": 1, "card": "6D"})
    g.decide({"type": "emblem_place", "player": 2, "card": "7C"})
    gone = cards_for(g, lambda: g.decide({"type": "mage_pick", "card": g.decision["eligible"][-1]}),
                     off("azure_emblem"))
    assert "Emblem" not in everything(gone) and "Mage: " in everything(gone)


def test_azure_emblem_shows_once_an_attack_for_a_solo_mage_chain():
    g = legacy(1, seed=320, cards=M.MAGE_DECK, relics=("emblem",))
    set_enemy(g, "K", "H")
    set_hand(g, ["4M", "10S", "10C", "10D", "3M"])
    set_tavern_top(g, ["2M", "3D", "4S", "5H", "6C", "7D"])
    g.play(["4M"])
    assert ids(cards_for(g, lambda: g.decide({"type": "mage_pick", "card": "2M"}))) == ["azure_emblem"]
    cards = cards_for(g, lambda: g.decide({"type": "emblem_keep", "player": 0, "card": "5H"}))
    assert "Emblem: 1 card back on the reserve" in cards[0].lines        # on the chained mage's card
    again = cards_for(g, lambda: g.decide({"type": "mage_pick", "card": g.decision["eligible"][0]}))
    assert g.decision["kind"] == "emblem_keep" and "azure_emblem" not in ids(again)
    cards = cards_for(g, lambda: g.decide({"type": "emblem_skip", "player": 0}))
    assert "Emblem: no card kept" in cards[0].lines
    fits(cards)
    g.suffer(["10S", "10C"])
    set_tavern_top(g, ["2D", "3C", "4H"])
    g.play(["3M"])                                          # a new attack: the Emblem card again
    assert ids(cards_for(g, lambda: g.decide({"type": "mage_pick", "card": "2D"}))) == ["azure_emblem"]


# ---------------------------------------------------------------------------- Evergreen Mother
def _mother(players):
    g = legacy(players, seed=330 if players == 1 else 331, relics=("mother",), corrupted=("6C",))
    set_enemy(g, "J", "H")
    if players == 1:
        set_hand(g, ["6C", "9S", "8S"])
        set_discard(g, ["2D", "3D"])
    else:
        set_hand(g, ["6C", "9S"], 0)
        set_hand(g, ["4D", "8S"], 1)
    return g


def test_mother_corrupt_solo_asks_before_its_box_and_its_corrupted_card_follows():
    g = _mother(1)
    cards = cards_for(g, lambda: g.play(["6C"]))
    assert ids(cards) == ["mother_corrupt"]
    c = cards[0]
    assert c.title == "Evergreen Mother" and c.number == "6" and c.icon is None
    assert c.lines == ["6♣ entered corrupted", "Banish the top discard (2♦) instead", "of the reserve's top?"]
    assert c.face_args({})["edge"] == info.T.CORRUPTED
    cards = cards_for(g, lambda: g.decide({"type": "mother_choice", "player": 0, "option": "discard"}))
    assert ids(cards)[0] == "corrupted"
    assert card(cards, "corrupted").lines[1] == "Top discard banished: 2♦ (Mother)"
    fits(cards)
    g = _mother(1)
    assert cards_for(g, lambda: g.play(["6C"]), off("mother_corrupt")) == []


def test_mother_corrupt_with_two_players_names_who_banishes():
    g = _mother(2)
    c = card(cards_for(g, lambda: g.play(["6C"])), "mother_corrupt")
    assert c.lines == ["6♣ entered corrupted", "Ben must banish a card from hand", "instead of the reserve's top"]
    cards = cards_for(g, lambda: g.decide({"type": "mother_banish", "player": 1, "card": "4D"}))
    assert card(cards, "corrupted").lines[1] == "Ben banishes 4♦ from hand (Mother)"
    fits(cards)
    g = _mother(2)
    set_hand(g, [], 1)
    cards = cards_for(g, lambda: g.play(["6C"]))
    assert "mother_corrupt" not in ids(cards)
    assert card(cards, "corrupted").lines[1] == "Nothing to banish: other hands empty"


def _m12_mage_kill():
    g, rest = m12_restored()
    rig(g, "mission_zone", ["2C", "6D"])
    g.enemy.hp = 4
    g.enemy.suits = ()
    r = [x for x in rest if x not in g.players[0].hand][1]
    set_hand(g, ["4M", "9S"])
    set_tavern_top(g, [r, "2D", "3D", "AD"])
    g.play(["4M"])
    g.decide({"type": "mage_pick", "card": r})
    return g, r


def test_mother_restored_counts_the_restored_cards_kept_out_of_the_banished_pile():
    g, r = _m12_mage_kill()
    a = dict(g.legal_actions()[0])
    a["cards"] = list(a.get("pick_from") or g.decision.get("options") or [])
    cards = cards_for(g, lambda: g.decide(a))
    assert any(e["t"] == "banish_redirect" for e in g.last_events)
    in_order(cards, "defeated", "mother_restored", "new_enemy", "turn")
    c = card(cards, "mother_restored")
    assert c.title == "Evergreen Mother" and c.number == ""
    assert c.lines == ["1 restored card would be banished", "It goes under the reserve instead"]
    assert c.face_args({})["edge"] == info.T.RESTORED
    assert g.card(r).label() not in text(c)                 # it is in the reserve now
    fits(cards)
    g, r = _m12_mage_kill()
    a = dict(g.legal_actions()[0])
    a["cards"] = list(a.get("pick_from") or g.decision.get("options") or [])
    gone = cards_for(g, lambda: g.decide(a), off("mother_restored"))
    assert "mother_restored" not in ids(gone) and "would be banished" not in everything(gone)


def test_mother_restored_follows_the_step_that_banished():
    g = evergreen("B", seed=5102)
    rig(g, "mission_zone", ["9H"])
    set_discard(g, ["2D", "3D"])
    set_tavern_top(g, ["8H"])
    g.enemy.suits = ()
    set_hand(g, ["AS", "10S", "10C", "10D"])
    g.play(["AS"])
    cards = cards_for(g, lambda: g.suffer(["10S", "10C"]))
    in_order(cards, "cave_collapse", "mother_restored", "turn")
    assert ids(cards)[-2:] == ["mother_restored", "turn"]
    fits(cards)


# ---------------------------------------------------------------------------- the Jesters
def _base_jester():
    g = new_game(2, seed=7, jesters=1)
    set_enemy(g, "J", "H")
    set_hand(g, ["X1", "5H", "9S"], 0)
    set_hand(g, ["4C", "8S"], 1)
    return g


def test_base_jester_cancels_immunity_and_its_choice_is_a_line_on_the_turn_card():
    g = _base_jester()
    cards = cards_for(g, lambda: g.play(["X1"]))
    assert ids(cards) == ["jester"]
    c = cards[0]
    assert c.title == "Jester" and c.number == "" and c.icon is None
    assert c.lines == ["%s loses its immunity" % g.enemy.name, "for the rest of this fight",
                       "No damage and no enemy attack this turn", "Player 1 chooses who goes next"]
    assert c.face_args({})["edge"] == info.T.JESTER_COLOR and c.sounds == ["info_jester", "jester"]
    cards = cards_for(g, lambda: g.choose_next(1))
    t = card(cards, "turn")
    assert t.title == "Player 2's turn" and t.lines[0] == "Player 2 goes next (Jester)"
    fits(cards)
    g = _base_jester()
    assert cards_for(g, lambda: g.play(["X1"]), off("jester")) == []
    gone = cards_for(g, lambda: g.choose_next(1), off("jester"))
    assert "(Jester)" not in everything(gone)


def test_base_jester_lets_earlier_spades_shield():
    g = new_game(2, seed=7, jesters=1)
    set_enemy(g, "J", "S")
    set_hand(g, ["5S", "10H", "9D"], 0)
    set_hand(g, ["X1", "8C"], 1)
    g.play(["5S"])
    g.suffer(["10H"])
    c = card(cards_for(g, lambda: g.play(["X1"])), "jester")
    assert "Earlier ♠ shields count: attack 10 → 5" in c.lines


def test_jester_claim_then_the_turn_card_names_the_claimer():
    g, jid = _claimed()
    cards = cards_for(g, lambda: g.play([jid]))
    assert ids(cards) == ["jester_claim"]
    assert cards[0].title == "Jester" and cards[0].lines == [
        "Anyone may claim it and attack now", "That attack ignores immunity",
        "Its paladins keep shielding after it", "Play goes on clockwise from the claimer"]
    cards = cards_for(g, lambda: g.choose_next(1))
    t = card(cards, "turn")
    assert t.title == "Ben claims the Jester" and t.number == "1"
    fits(cards)
    g, jid = _claimed()
    assert cards_for(g, lambda: g.play([jid]), off("jester_claim")) == []


def test_jester_claim_against_myla_keeps_her_immunity():
    g = mission(9, players=3, cards=[M.GORAN], beast="B_H")
    set_mission_enemy(g, "MYLA_BOSS")
    jid = [x for x in g.cards if g.cards[x].is_jester][0]
    set_hand(g, [jid, "9S"], 0)
    c = card(cards_for(g, lambda: g.play([jid])), "jester_claim")
    assert c.lines[1] == "That attack ignores immunity, not Myla's"


def test_solo_jester_new_hand_in_step_1_and_step_4():
    g = new_game(1, seed=5)
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "2S"])
    cards = cards_for(g, lambda: g.use_solo_jester())
    assert ids(cards) == ["solo_jester_refresh"]
    c = cards[0]
    assert c.title == "Jester" and c.number == "1"
    assert c.lines == ["Hand discarded (2), drew 8 back to 8", "Jesters left: 1",
                       "Gold: none used · silver: 1 · bronze: 2"]
    for cid in g.players[0].hand:
        assert g.card(cid).label() not in text(c)
    g = new_game(1, seed=5)
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "2S", "2D"])
    g.play(["3C"])
    cards = cards_for(g, lambda: g.use_solo_jester())
    assert cards[-1].lines[-1] == "Now pay the damage: 10"
    fits(cards)
    g = new_game(1, seed=5)
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "2S"])
    assert cards_for(g, lambda: g.use_solo_jester(), off("solo_jester_refresh")) == []


def test_solo_jester_attack_comes_before_its_class_card():
    g = legacy(1, seed=2)
    set_enemy(g, "J", "C")
    set_hand(g, ["9S", "8S", "7S"])
    cards = cards_for(g, lambda: g.use_solo_jester({"suit": "C"}))
    assert ids(cards)[0] == "solo_jester_attack"
    in_order(cards, "solo_jester_attack", "warrior", "damage")
    c = card(cards, "solo_jester_attack")
    assert c.title == "Jester" and c.number == "8"
    assert c.lines == ["The Jester is a Warrior of strength 8", "Ignores %s's immunity" % g.enemy.name,
                       "Jesters left: 1", "It is set aside when this enemy falls"]
    fits(cards)
    g = legacy(1, seed=2)
    set_enemy(g, "J", "C")
    set_hand(g, ["9S", "8S", "7S"])
    gone = cards_for(g, lambda: g.use_solo_jester({"suit": "C"}), off("solo_jester_attack"))
    assert "solo_jester_attack" not in ids(gone) and "strength 8" not in everything(gone)


# ---------------------------------------------------------------------------- old saves
def test_events_missing_their_fields_never_break_the_queue():
    g = legacy(2, seed=331, relics=("mother", "flute", "whistle", "emblem"))
    bare = [{"t": t} for t in ("turn", "yield", "corrupt_banish", "corrupt_banish_none", "restore", "declare",
                               "flute_store", "whistle_take", "emblem_place", "emblem_keep", "emblem_skip",
                               "banish_redirect", "jester", "solo_jester", "choose_next", "play", "add_to_play")]
    bare += [{"t": "decide", "kind": k} for k in ("flute_add", "whistle_add", "whistle_take", "emblem_place",
                                                   "emblem_keep", "mother_choice", "mother_banish")]
    cards = info.build(g, bare, {"info_popups": True}, before=g.to_dict())
    fits(cards)
    for game in (legacy(1, seed=331, relics=("emblem",)), new_game(3, seed=3)):
        for ev in bare:                                     # alone, with no snapshot, and in the base game
            fits(info.build(game, [ev], {"info_popups": True}, before=None))
            fits(info.build(game, [ev], {"info_popups": True}, before=game.to_dict(), start=True))
    for ev in bare:                                         # nothing unknown is spelled out
        game = legacy(2, seed=331, relics=("mother", "flute", "whistle", "emblem"))
        for c in info.build(game, [ev], {"info_popups": True}, before=game.to_dict()):
            assert "None" not in text(c) and "()" not in text(c), c.lines
            assert not any(re.search(r"(^|\s)\?(\s|$)", line) for line in c.lines), c.lines   # an unknown player
    g = legacy(1, seed=2)
    set_enemy(g, "J", "C")
    old = info.build(g, [{"t": "solo_jester", "suit": "C", "remaining": 1}], {"info_popups": True})
    assert ids(old) == ["solo_jester_attack"] and old[0].lines[0] == "The Jester is a Warrior of strength 8"
