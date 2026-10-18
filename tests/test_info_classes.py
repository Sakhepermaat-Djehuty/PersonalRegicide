"""Info pop-ups, the Classes group (app/info_classes.py): one card per class in the engine's
power order, the Warrior card carrying the damage (else the Damage card), Paladin and
Guardian after the damage and never on a kill, the IMMUNITY stamp, the Mage, Druid, Chanter
and Reaver cards before their boxes with what was chosen as one line on the next card, the
formation line, hidden hands and the reserve kept hidden, names with 2+ players and the base
game's wording. Every scenario is a real game flow."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()

import pytest  # noqa: E402

from app import info, info_classes  # noqa: E402
from helpers import _pull, new_game, set_discard, set_enemy, set_hand, set_mission_enemy, set_tavern_top  # noqa: E402
from info_helpers import ON, card, cards_for, fits, ids, text  # noqa: E402
from regicide.campaign import CampaignState  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402

MINE = ("mage", "druid", "cleric", "bard", "chanter", "reaver", "warrior", "paladin", "guardian", "damage")


@pytest.fixture(autouse=True)
def _no_swallowed_errors():
    info_classes.ERRORS.clear()
    yield
    assert info_classes.ERRORS == []


def mine(cards):
    """This group's cards (other groups' cards may stand around them)."""
    return [c for c in cards if c.id in MINE]


def my_ids(cards):
    return ids(mine(cards))


def all_text(cards):
    return "\n".join(text(c) for c in cards)


def off(*rows):
    return {"info_popups_off": list(rows)}


def run(g, action, settings=None):
    """The queue of one action; this group's cards keep the catalogue's size limits."""
    cards = cards_for(g, action, settings)
    fits(mine(cards))
    return cards


def twice(make, action, row):
    """The same flow built with every row on and with ``row`` off (fresh games)."""
    g = make()
    on_cards = run(g, lambda: action(g))
    g = make()
    off_cards = run(g, lambda: action(g), off(row))
    return on_cards, off_cards


LONG_NAMES = ("Maximilian Ash", "Bartholomew Kay", "Christabel Moon", "Dorothea Vance")


def camp(players=1, seed=100, number=1, cards=(), relics=(), corrupted=(), beast=None, mercs=(),
         names=("Ana", "Ben", "Cy")):
    """A Legacy attempt (mission ``number``) with these party cards, flags and relics."""
    c = CampaignState.new(players, list(names)[:players], seed=seed)
    c.mission = number
    c.completed = list(range(1, number))
    for d in cards:
        if P.find(c.party, str(d["id"])) is None:
            P.add_card(c.party, dict(d))
    for cid in corrupted:
        P.add_flag(c.party, cid, "corrupted")
    c.relics.extend(relics)
    if beast:
        c.flags["beasts"] = True
        c.set_beast(beast)
    if mercs:
        c.m_box_opened = True
        c.coins = 20
        for m in mercs:
            c.hire(m)
    return c.start_attempt(seed=seed)


def evergreen(location="A", banes=(), seed=5000):
    c = CampaignState.new(1, ["Ana"], seed=seed)
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
    c.evergreen["setup"] = {"location": location, "banes": sorted(banes), "boons": []}
    return c.start_evergreen_attempt(seed=seed)


def rig(g, attr, ids_):
    """Exactly ``ids_`` in the pile ``attr`` (its cards go under the reserve)."""
    old = list(getattr(g, attr))
    setattr(g, attr, [])
    g.tavern.extend(old)
    for x in ids_:
        _pull(g, x)
    setattr(g, attr, list(ids_))


def capture_state(monkeypatch):
    """The builder's scratch state of every build (to read ``guardian_shown``)."""
    seen = []
    monkeypatch.setattr(info, "FINISHERS", info.FINISHERS + [lambda ctx: seen.append(dict(ctx.state))])
    return seen


# ---------------------------------------------------------------- base game: Cleric, Bard, Warrior, Damage
def _base_5h():
    g = new_game(1, seed=5)
    set_enemy(g, "J", "C")
    set_hand(g, ["5H", "9S", "8S", "7D"])
    set_discard(g, ["2H", "3H", "4H", "6H", "7H", "8H"])
    return g


def test_base_cleric_then_the_damage_card_in_the_tavern_decks_words():
    on_cards, off_cards = twice(_base_5h, lambda g: g.play(["5H"]), "cleric")
    assert my_ids(on_cards) == ["cleric", "damage"]
    cleric, damage = mine(on_cards)
    assert (cleric.title, cleric.number, cleric.immune) == ("♥ Hearts", "5", False)
    assert cleric.lines[-2:] == ["Heal 5: the discard pile is shuffled", "5 go face down under the tavern deck"]
    assert (damage.title, damage.number, damage.middle, damage.caption) == ("Damage", "5", "5", "damage")
    assert damage.lines[-2:] == ["Attack 5", "Health 20 → 15"]
    assert cleric.sounds[0] == "info_cleric" and damage.sounds[0] == "info_damage"
    # switched off: no card and no line in its place
    assert my_ids(off_cards) == ["damage"] and "Heal 5" not in all_text(off_cards)


def test_base_bard_counts_the_draw_and_never_names_the_cards():
    g = new_game(1, seed=5)
    set_enemy(g, "J", "C")
    set_hand(g, ["5D", "9S", "8S", "7D"])
    cards = run(g, lambda: g.play(["5D"]))
    drawn = [g.cards[e["card"]].label() for e in g.last_events if e["t"] == "draw"]
    bard = card(cards, "bard")
    assert my_ids(cards) == ["bard", "damage"] and (bard.title, bard.number) == ("♦ Diamonds", "5")
    assert bard.lines[-2:] == ["Draw 5 from the tavern deck", "You drew 5"]
    assert drawn and not any(label in all_text(cards) for label in drawn)
    g = new_game(1, seed=5)
    set_enemy(g, "J", "C")
    set_hand(g, ["5D", "9S", "8S", "7D"])
    cards = run(g, lambda: g.play(["5D"]), off("bard"))
    assert my_ids(cards) == ["damage"] and "Draw" not in all_text(cards)


def test_bard_with_two_players_names_them_and_counts_each_hand():
    g = new_game(2, seed=7)
    set_enemy(g, "J", "H")
    set_hand(g, ["4D", "9S"], 0)
    set_hand(g, ["4C"], 1)
    cards = run(g, lambda: g.play(["4D"]))
    bard = card(cards, "bard")
    assert bard.lines == ["Draw 4, one card at a time,", "clockwise from Player 1; full hands skip",
                          "Player 1 +2 · Player 2 +2"]
    assert "You" not in all_text(mine(cards))
    drawn = [g.cards[e["card"]].label() for e in g.last_events if e["t"] == "draw"]
    assert not any(label in all_text(cards) for label in drawn)


def test_a_bard_that_empties_the_tavern_deck_says_so():
    g = new_game(2, seed=7)
    set_enemy(g, "J", "H")
    set_hand(g, ["6D", "9S"], 0)
    set_hand(g, ["4C"], 1)
    g.discard.extend(g.tavern[3:])
    del g.tavern[3:]
    cards = run(g, lambda: g.play(["6D"]))
    assert card(cards, "bard").lines[-2:] == ["Player 1 +2 · Player 2 +1", "The tavern deck ran out: 3 of 6"]


def _base_5c():
    g = new_game(1, seed=5)
    set_enemy(g, "J", "H")
    set_hand(g, ["5C", "9S", "8S", "7D"])
    return g


def test_base_warrior_carries_the_damage_and_falls_back_to_the_damage_card():
    on_cards, off_cards = twice(_base_5c, lambda g: g.play(["5C"]), "warrior")
    warrior = card(on_cards, "warrior")
    assert my_ids(on_cards) == ["warrior"]
    assert (warrior.title, warrior.number, warrior.middle, warrior.caption) == ("♣ Clubs", "5", "10", "damage")
    assert warrior.lines == ["5 ×2 = 10", "Health 20 → 10"]
    # the Warrior row off: the Damage card takes its slot, with the same damage
    damage = card(off_cards, "damage")
    assert my_ids(off_cards) == ["damage"] and (damage.middle, damage.lines) == ("10", ["Attack 5", "Health 20 → 10"])
    g = _base_5c()
    assert my_ids(run(g, lambda: g.play(["5C"]), off("warrior", "damage"))) == []


def test_the_damage_row_off_leaves_no_damage_card():
    on_cards, off_cards = twice(_base_5h, lambda g: g.play(["5H"]), "damage")
    assert my_ids(on_cards) == ["cleric", "damage"] and my_ids(off_cards) == ["cleric"]
    assert "Health" not in all_text(off_cards)


# ---------------------------------------------------------------- IMMUNITY
def _base_5h_immune():
    g = new_game(1, seed=5)
    set_enemy(g, "J", "H")
    set_hand(g, ["5H", "9S", "8S"])
    set_discard(g, ["2D"])
    return g


def test_immunity_stamps_the_blocked_class_and_its_row_governs_every_stamp():
    g = _base_5h_immune()
    cards = run(g, lambda: g.play(["5H"]), off("cleric"))     # the class row does not matter
    cleric = card(cards, "cleric")
    assert my_ids(cards) == ["cleric", "damage"] and cleric.immune and cleric.title == "♥ Hearts"
    assert cleric.number == "5" and cleric.lines == ["Would heal 5", "Immune: printed ♥"]
    assert cleric.sounds == ["info_immunity", "power_blocked"]
    g = _base_5h_immune()
    cards = run(g, lambda: g.play(["5H"]), off("immunity"))
    assert my_ids(cards) == ["damage"] and "Would" not in all_text(cards) and "Immune" not in all_text(cards)


def _base_set():
    g = new_game(1, seed=5)
    set_enemy(g, "J", "C")
    set_hand(g, ["2H", "2D", "2C", "2S", "9S"])
    set_discard(g, ["3D", "4D"])
    return g


def test_a_blocked_warrior_is_stamped_then_the_damage_card_then_the_paladin():
    g = _base_set()
    cards = run(g, lambda: g.play(["2H", "2D", "2C", "2S"]))
    assert my_ids(cards) == ["cleric", "bard", "warrior", "damage", "paladin"]
    cleric, bard, warrior, damage, paladin = mine(cards)
    assert cleric.lines[0] == "Combo 2♥ 2♦ 2♣ 2♠ = 8"           # the attack's formation, on its first card
    assert warrior.immune and warrior.lines == ["Would double 8 → 16", "Immune: printed ♣"]
    assert (damage.middle, damage.lines[-1]) == ("8", "Health 20 → 12")
    assert paladin.title == "♠ Spades" and paladin.lines[:2] == ["Shield +8: enemy attack 10 → 2",
                                                                 "Shields total 8 until it falls"]
    assert "Hand full: 7 of 8" in bard.lines                  # solo: one hand


def test_immunity_sources_myla_high_arcana_zones_and_the_top_discard():
    # Myla's fixed immunity: even a corrupted paladin is stamped, after the damage
    c = CampaignState.new(1, ["Ana"], seed=823)
    c.mission = 9
    c.completed = list(range(1, 9))
    P.add_card(c.party, dict(M.GORAN))
    g = c.start_attempt(seed=823)
    g.cards["9S"] = g.cards["9S"].with_changes(flags=("corrupted",))
    set_mission_enemy(g, "MYLA_BOSS")
    set_hand(g, ["9S", "2C"])
    cards = run(g, lambda: g.play(["9S"]))
    assert my_ids(cards) == ["damage", "paladin"] and card(cards, "paladin").immune
    assert card(cards, "paladin").lines == ["Would shield 9", "Immune: never ignored (Myla)"]
    # the High Arcana (Evergreen bane 8): immune to the four basic classes
    g = evergreen("B", banes=[5, 8])
    set_mission_enemy(g, "TH_ARCANA")
    set_hand(g, ["9S", "6H", "AS"])
    cards = run(g, lambda: g.play(["9S"]))
    assert card(cards, "paladin").lines == ["Would shield 9", "Immune: all four basics (High Arcana)"]
    # the Shrine: the zone's classes
    g = evergreen("A")
    rig(g, "mission_zone", ["6C"])
    g.enemy.suits = ("H",)
    set_hand(g, ["9C", "AS"])
    cards = run(g, lambda: g.play(["9C"]))
    assert my_ids(cards) == ["warrior", "damage"]
    assert card(cards, "warrior").lines == ["Would double 9 → 18", "Immune: zone 6♣"]
    # mission 11: the top of the discard pile
    g = camp(1, seed=1100, number=11, cards=M.MAGE_DECK, beast="B_H")
    while g.decision:
        g.decide(g.legal_actions()[0])
    set_discard(g, ["6D"])
    set_hand(g, ["5D", "9S", "8S"])
    cards = run(g, lambda: g.play(["5D"]))
    assert card(cards, "bard").immune and card(cards, "bard").lines == ["Would draw 5", "Immune: top discard 6♦"]


def test_an_immunity_that_an_earlier_power_brought_still_names_its_source():
    # mission 11: the heal reshuffles the discard pile, and its new top (a ♦) blocks the bard
    g = camp(1, seed=1100, number=11, cards=M.MAGE_DECK, beast="B_H")
    while g.decision:
        g.decide(g.legal_actions()[0])
    rig(g, "banished", ["7S"])
    set_discard(g, ["6C", "2D", "3D", "4D", "6D", "7D", "8D", "9D", "10D", "AD", "2S", "3S"])
    set_hand(g, ["5H", "5D", "9S"])
    cards = run(g, lambda: g.play(["5H", "5D"]))
    assert not card(cards, "cleric").immune and card(cards, "bard").immune
    assert card(cards, "bard").lines == ["Would draw 10", "Immune: top discard %s" % g.cards[g.discard[0]].label()]


def test_the_druid_chanter_reaver_and_guardian_have_stamped_would_forms():
    would = {"U": "Would deal the discard pile (2)", "T": "Would draw, then discard to the limit",
             "R": "Would reveal and double", "G": "Would protect the party"}
    for cid, deck, row in (("5U", M.DRUIDS, "druid"), ("5T", M.CHANTERS, "chanter"), ("5R", M.REAVERS, "reaver"),
                           ("5G", M.GUARDIANS, "guardian")):
        g = camp(1, seed=450, cards=deck)
        set_enemy(g, "K", "H")
        g.enemy.suits = (cid[1],)
        set_hand(g, [cid, "9S"])
        set_discard(g, ["2H", "3H"])
        cards = run(g, lambda: g.play([cid]))
        stamped = card(cards, row)
        assert stamped.immune and stamped.lines[0] == would[cid[1]] and stamped.lines[1].startswith("Immune: printed")
        # no box behind a stamp; a stamped Guardian follows the damage and stands in for nothing
        assert g.decision is None
        assert my_ids(cards) == (["damage", row] if row == "guardian" else [row, "damage"])


def test_ignored_immunity_is_a_line_on_the_normal_card():
    # an Evergreen card (Gøran renewed) against a warrior enemy: Cleric, Bard, Warrior, Paladin
    g = camp(1, seed=460, cards=[M.GORAN_RENEWED])
    set_enemy(g, "J", "C", hp=40)
    set_hand(g, ["GOR8E", "9S"])
    set_discard(g, ["2H", "3H"])
    cards = run(g, lambda: g.play(["GOR8E"]))
    assert my_ids(cards) == ["cleric", "bard", "warrior", "paladin"]
    warrior = card(cards, "warrior")
    assert not warrior.immune and warrior.middle == "16"
    assert warrior.lines == ["8 ×2 = 16", "8♥♦♣♠ ignores immunity (Evergreen)", "Health 40 → 24"]
    # a corrupted card
    g = camp(1, seed=470, corrupted=("6C",))
    set_enemy(g, "J", "C")
    set_hand(g, ["6C", "9S", "8S"])
    assert "6♣ ignores immunity (corrupted)" in card(run(g, lambda: g.play(["6C"])), "warrior").lines
    # the Legacy solo Jester
    g = camp(1, seed=2)
    set_enemy(g, "J", "C")
    set_hand(g, ["9S", "8S", "7S"])
    cards = run(g, lambda: g.use_solo_jester({"suit": "C"}))
    assert card(cards, "warrior").lines == ["8 ×2 = 16", "Ignores immunity (Jester)", "Health 20 → 4"]


def test_a_claimed_jester_and_the_base_jester_ignore_immunity_with_names():
    g = camp(3, seed=3)
    set_enemy(g, "J", "H")
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_hand(g, [jester, "9S"], 0)
    set_hand(g, ["5H", "8S"], 1)
    set_hand(g, ["2C"], 2)
    g.play([jester])
    g.choose_next(1)
    cards = run(g, lambda: g.play(["5H"]))
    assert "Ignores immunity (Jester)" in card(cards, "cleric").lines
    g = new_game(2, seed=7, jesters=1)
    set_enemy(g, "J", "H")
    set_hand(g, ["X1", "9S"], 0)
    set_hand(g, ["5H", "8S", "4C"], 1)
    g.play(["X1"])
    g.choose_next(1)
    cards = run(g, lambda: g.play(["5H"]))
    assert card(cards, "cleric").title == "♥ Hearts" and "Ignores immunity (Jester)" in card(cards, "cleric").lines


# ---------------------------------------------------------------- Paladin and Guardian
def _base_5s():
    g = new_game(1, seed=5)
    set_enemy(g, "J", "C")
    set_hand(g, ["5S", "9S", "8S", "7D"])
    return g


def test_the_paladin_follows_the_damage_when_the_enemy_survives():
    on_cards, off_cards = twice(_base_5s, lambda g: g.play(["5S"]), "paladin")
    assert my_ids(on_cards) == ["damage", "paladin"]
    paladin = card(on_cards, "paladin")
    assert (paladin.title, paladin.number) == ("♠ Spades", "5")
    assert paladin.lines == ["Shield +5: enemy attack 10 → 5", "Shields total 5 until it falls"]
    assert my_ids(off_cards) == ["damage"] and "Shield" not in all_text(off_cards)


def test_a_killing_blow_shows_no_paladin_and_no_guardian():
    # a 2/5 and a 5 of paladins: the forced kinfolk set kills exactly
    g = camp(1, seed=481, mercs=("merc_25C",))
    set_enemy(g, "J", "H")
    set_hand(g, ["M25C", "5S", "9S", "8S"])
    cards = run(g, lambda: g.play(["M25C", "5S"]))
    assert my_ids(cards) == ["warrior"]
    assert card(cards, "warrior").lines[-2:] == ["10 ×2 = 20", "Health 20 → 0: exact kill!"]
    assert "Kinfolk 2/5♣ 5♠ = 10" in all_text(cards)
    # a guardian's kill, and a stamped paladin's kill (Myla): nothing either
    g = camp(1, seed=450, cards=M.GUARDIANS)
    set_enemy(g, "K", "H", hp=5)
    set_hand(g, ["5G", "9S"])
    cards = run(g, lambda: g.play(["5G"]))
    assert my_ids(cards) == ["damage"] and card(cards, "damage").lines[-1] == "Health 5 → 0: exact kill!"
    c = CampaignState.new(1, ["Ana"], seed=823)
    c.mission = 9
    c.completed = list(range(1, 9))
    g = c.start_attempt(seed=823)
    g.cards["9S"] = g.cards["9S"].with_changes(flags=("corrupted",))
    set_mission_enemy(g, "MYLA_BOSS", hp=4)
    set_hand(g, ["9S", "2C"])
    cards = run(g, lambda: g.play(["9S"]))
    assert my_ids(cards) == ["damage"] and "Would shield" not in all_text(cards)
    assert card(cards, "damage").lines[-1] == "Health 4 → 0: defeated!"


def test_a_paladin_that_ignores_immunity_keeps_shielding_where_immunity_changes():
    g = camp(1, seed=470, number=3, corrupted=("5S",))
    while g.decision:
        g.decide(g.legal_actions()[0])
    set_hand(g, ["5S", "9H", "8H"])
    cards = run(g, lambda: g.play(["5S"]))
    assert card(cards, "paladin").lines[-1] == "Keeps shielding if ♠ immunity comes"


def test_a_paused_attacks_own_shield_is_not_counted_twice():
    """A mage or reaver box keeps the attack on the table, so the snapshot already counts
    its paladin: the card still reads the enemy's attack before this shield."""
    g = camp(1, seed=101, cards=M.MAGE_DECK)
    set_enemy(g, "K", "H")
    set_hand(g, ["3M", "3S", "9S"])
    set_tavern_top(g, ["2C", "6D", "4C"])
    run(g, lambda: g.play(["3M", "3S"]))
    cards = run(g, lambda: g.decide({"type": "mage_pick", "card": "4C"}))
    assert card(cards, "paladin").lines == ["Shield +10: enemy attack 20 → 10", "Shields total 10 until it falls"]
    g = camp(1, seed=440, cards=M.REAVERS)
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["5S", "5R", "9S"])
    set_tavern_top(g, ["7H", "2D", "3D"])
    run(g, lambda: g.play(["5S", "5R"]))
    run(g, lambda: g.decide({"type": "reaver_count", "count": 2}))
    cards = run(g, lambda: g.decide({"type": "reaver_pick", "card": "7H"}))
    assert my_ids(cards) == ["damage", "paladin"] and card(cards, "damage").middle == "34"
    assert card(cards, "paladin").lines[:2] == ["Shield +10: enemy attack 20 → 10", "Shields total 10 until it falls"]


def test_a_kill_that_waits_on_a_defeat_box_shows_no_paladin():
    # mission 4: the played cards' discard order is asked before the defeat event
    g = camp(1, seed=401, number=4)
    while g.decision:
        g.decide(g.legal_actions()[0])
    set_hand(g, ["5S", "5C", "9H"])
    g.enemy.hp = 20
    cards = run(g, lambda: g.play(["5S", "5C"]))
    assert g.decision["kind"] == "played_discard_order" and not any(e["t"] == "defeat" for e in g.last_events)
    assert my_ids(cards) == ["warrior"] and card(cards, "warrior").lines[-1] == "Health 20 → 0: exact kill!"


def _guardian_game():
    g = camp(1, seed=450, cards=M.GUARDIANS)
    set_enemy(g, "K", "H")
    set_hand(g, ["5G", "9S", "2D"])
    return g


def test_the_guardian_stands_in_for_no_damage_and_tells_the_defeat_module(monkeypatch):
    seen = capture_state(monkeypatch)
    g = _guardian_game()
    cards = run(g, lambda: g.play(["5G"]))
    assert my_ids(cards) == ["damage", "guardian"] and seen[-1].get("guardian_shown") is True
    guardian = card(cards, "guardian")
    assert (guardian.title, guardian.number) == ("Guardian", "5")
    assert guardian.lines == ["You suffer no damage this turn:", "no enemy attack, no mission damage"]
    g = _guardian_game()
    cards = run(g, lambda: g.play(["5G"]), off("guardian"))
    assert my_ids(cards) == ["damage"] and "guardian_shown" not in seen[-1]
    assert "suffer no damage" not in all_text(cards)


# ---------------------------------------------------------------- Mage
def _mage_game(**kw):
    g = camp(1, seed=101, cards=M.MAGE_DECK, **kw)
    set_enemy(g, "K", "H")
    set_hand(g, ["AC", "3M", "9S"])
    set_tavern_top(g, ["2M", "6D", "2C", "3C", "5S", "4S"])
    return g


def _mage_chain(g, settings=None):
    """Peek, pick the 2 of mages (it looks again), pick the 5 of paladins: three queues."""
    first = run(g, lambda: g.play(["AC", "3M"]), settings)
    second = run(g, lambda: g.decide({"type": "mage_pick", "card": "2M"}), settings)
    third = run(g, lambda: g.decide({"type": "mage_pick", "card": "5S"}), settings)
    return first, second, third


def test_the_mage_card_stands_before_each_peek_and_the_pick_is_a_line():
    first, second, third = _mage_chain(_mage_game())
    mage = card(first, "mage")
    assert my_ids(first) == ["mage"] and (mage.title, mage.number) == ("Mage", "4")
    assert mage.lines == ["Companion A♣ + 3⚝ = 4", "You look in secret at the top 4", "Pick one to join the attack",
                          "(no Jesters, no corrupted cards)", "The rest go to the discard pile"]
    # the peeked cards are hidden (they are still in the reserve)
    assert not any(label in all_text(first) for label in ("2⚝", "6♦", "2♣", "3♣"))
    again = card(second, "mage")
    assert my_ids(second) == ["mage"] and (again.title, again.number) == ("Mage again", "2")
    assert again.lines[0] == "Mage: 2⚝ joins (4 → 6), 3 discarded"
    assert my_ids(third) == ["warrior", "paladin"]
    assert card(third, "warrior").lines == ["Mage: 5♠ joins (6 → 11), 1 discarded", "11 ×2 = 22",
                                            "Health 40 → 18"]
    assert card(third, "paladin").number == "11"


def test_the_mage_row_off_leaves_no_card_and_no_line():
    queues = _mage_chain(_mage_game(), off("mage"))
    assert [my_ids(q) for q in queues] == [[], [], ["warrior", "paladin"]]
    assert not any("Mage" in all_text(q) for q in queues)


def test_an_immune_mage_and_a_chained_mage_stopped_by_immunity_are_stamped():
    g = camp(1, seed=103, cards=M.MAGE_DECK)
    set_enemy(g, "K", "H")
    g.enemy.suits = ("M",)
    set_hand(g, ["4M", "9S", "8S"])
    cards = run(g, lambda: g.play(["4M"]))
    assert my_ids(cards) == ["mage", "damage"] and card(cards, "mage").immune
    assert card(cards, "mage").lines == ["Would look at the top 4", "Immune: printed ⚝",
                                         "The attack is still banished at clean-up"]
    # a corrupted mage ignores the immunity; the plain mage it picks cannot look again

    def corrupted():
        g = camp(1, seed=106, cards=M.MAGE_DECK, corrupted=("3M",))
        set_enemy(g, "K", "H")
        g.enemy.suits = ("M",)
        set_hand(g, ["3M", "9S", "8S"])
        set_tavern_top(g, ["AD", "2M", "6D", "2C"])
        first = run(g, lambda: g.play(["3M"]))
        return g, first
    g, first = corrupted()
    assert "3⚝ ignores immunity (corrupted)" in card(first, "mage").lines
    cards = run(g, lambda: g.decide({"type": "mage_pick", "card": "2M"}))
    again = card(cards, "mage")
    assert my_ids(cards) == ["mage", "damage"] and again.immune and (again.title, again.number) == ("Mage again", "2")
    assert again.lines == ["Mage: 2⚝ joins (3 → 5), 2 discarded", "Would look at the top 2", "Immune: printed ⚝"]
    # IMMUNITY off: no stamp, the pick's line moves on to the next card
    g, first = corrupted()
    cards = run(g, lambda: g.decide({"type": "mage_pick", "card": "2M"}), off("immunity"))
    assert my_ids(cards) == ["damage"] and card(cards, "damage").lines[0].startswith("Mage: 2⚝ joins")


def test_a_mage_with_nothing_to_pick_and_an_empty_reserve():
    g = camp(1, seed=102, cards=M.MAGE_DECK, corrupted=("7D", "8D"))
    set_enemy(g, "K", "H")
    set_hand(g, ["2M", "9S", "8S"])
    set_tavern_top(g, ["7D", "8D"])
    run(g, lambda: g.play(["2M"]))
    cards = run(g, lambda: g.decide({"type": "mage_skip"}))
    assert card(cards, "damage").lines[0] == "Mage: nothing could join, 2 discarded"
    g = camp(1, seed=104, cards=M.MAGE_DECK)
    set_enemy(g, "K", "H")
    set_hand(g, ["4M", "9S", "8S"])
    g.discard.extend(g.tavern)
    g.tavern = []
    assert card(run(g, lambda: g.play(["4M"])), "mage").lines == ["Nothing to look at: reserve empty"]


def test_the_mage_with_the_azure_emblem_and_two_players_names_the_attacker_once():
    g = camp(2, seed=322, cards=M.MAGE_DECK, relics=("emblem",))
    set_enemy(g, "K", "H")
    set_hand(g, ["4M", "9S"], 0)
    set_hand(g, ["6D", "8S"], 1)
    cards = run(g, lambda: g.play(["4M"]))
    mage = card(cards, "mage")
    assert my_ids(cards) == ["mage"] and mage.lines[0] == "Ana will look in secret at the top 4"
    assert ids(cards) == ["mage", "azure_emblem"]       # the Mage first, then the Emblem before its box
    assert "You" not in all_text(mine(cards))
    cards = run(g, lambda: g.decide({"type": "emblem_place", "player": 1, "card": "6D"}))
    assert my_ids(cards) == []                       # the peek: its card stood before the placements
    pick = g.decision["eligible"][1]
    cards = run(g, lambda: g.decide({"type": "mage_pick", "card": pick}))
    assert "Mage: %s joins (4 → " % g.cards[pick].label() in all_text(cards)
    assert "6♦" not in all_text(cards)               # the placed card stays hidden


# ---------------------------------------------------------------- Druid
def _druid_game():
    g = camp(2, seed=700, cards=M.DRUIDS)
    set_enemy(g, "J", "H")
    set_hand(g, ["5U", "9S"], 0)
    set_hand(g, ["4C", "3D"], 1)
    set_discard(g, ["2H", "3H", "4H", "5H", "6H", "7H", "8H", "AC", "7C"])
    return g


def _druid_flow(g, settings=None):
    queues = [run(g, lambda: g.play(["5U"]), settings)]
    for p in (0, 1):
        dl = g.decision["dealt"][p]
        queues.append(run(g, lambda: g.decide({"type": "druid_assign", "player": p, "banish": dl[0], "hand": dl[1],
                                                "top": dl[2], "bottom": dl[3]}), settings))
    return queues


def test_the_druid_card_before_the_sorting_and_its_counts_as_one_line():
    g = _druid_game()
    first, second, third = _druid_flow(g)
    druid = card(first, "druid")
    assert my_ids(first) == ["druid"] and (druid.title, druid.number) == ("Druid", "5")
    assert druid.number_muted and druid.lines == ["Discard pile (9) shuffled and dealt out", "clockwise from Ana",
                           "Each sorts 4: one banished, one to hand,", "one on top and one under the reserve"]
    assert my_ids(second) == [] and my_ids(third) == ["damage"]
    assert card(third, "damage").lines[0] == "Druid: banished 2 · hands 2 · reserve 4"
    assert "You" not in all_text(mine(first + second + third))


def test_the_druid_never_names_a_card_dealt_to_a_hand_or_the_reserve():
    g = _druid_game()
    queues = [run(g, lambda: g.play(["5U"]))]
    moved = []
    for p in (0, 1):
        dl = g.decision["dealt"][p]
        moved.extend(g.cards[c].label() for c in dl[1:4])
        queues.append(run(g, lambda: g.decide({"type": "druid_assign", "player": p, "banish": dl[0], "hand": dl[1],
                                                "top": dl[2], "bottom": dl[3]})))
    assert not any(label in all_text(mine(q)) for q in queues for label in moved)


def test_the_druid_row_off_and_an_empty_discard_pile():
    queues = _druid_flow(_druid_game(), off("druid"))
    assert [my_ids(q) for q in queues] == [[], [], ["damage"]]
    assert not any("Druid" in all_text(q) or "Strength not used" in all_text(q) for q in queues)
    g = camp(1, seed=701, cards=M.DRUIDS)
    set_enemy(g, "J", "H")
    set_hand(g, ["5U", "9S"])
    g.tavern.extend(g.discard)
    g.discard = []
    cards = run(g, lambda: g.play(["5U"]))
    assert my_ids(cards) == ["druid", "damage"]
    assert card(cards, "druid").lines == ["Discard pile empty: nothing to deal"]


# ---------------------------------------------------------------- Chanter
def _chanter_game():
    g = camp(2, seed=710, cards=M.CHANTERS)
    set_enemy(g, "J", "H")
    set_hand(g, ["5T", "9S", "8S", "7S", "6S", "5S", "4S"], 0)
    set_hand(g, ["4C", "3D", "2D", "AC", "2C", "3C", "6C"], 1)
    return g


def _chanter_flow(g, settings=None):
    queues = [run(g, lambda: g.play(["5T"]), settings),
              run(g, lambda: g.decide({"type": "chanter_declare", "player": 0, "count": 2}), settings)]
    while g.decision and g.decision.get("kind") == "chanter_discard":
        a = g.legal_actions()[0]
        queues.append(run(g, lambda: g.decide({"type": "chanter_discard", "player": a["player"],
                                               "cards": a["pick_from"][:a["needs"]]}), settings))
    return queues


def test_the_chanter_card_before_the_number_box_and_the_draws_as_counts():
    g = _chanter_game()
    queues = _chanter_flow(g)
    chanter = card(queues[0], "chanter")
    assert my_ids(queues[0]) == ["chanter"] and (chanter.title, chanter.number) == ("Chanter", "5")
    assert chanter.number_muted and chanter.lines == ["Ana names 0 to 30 (the reserve)",
                             "Everyone draws that many, even over", "the limit, then discards down to 7"]
    assert [my_ids(q) for q in queues[1:]] == [[], [], ["damage"]]
    assert card(queues[-1], "damage").lines[0] == "Chanter 2: Ana +2 −1 · Ben +2 −2"


def test_the_chanter_never_names_the_cards_drawn():
    g = _chanter_game()
    run(g, lambda: g.play(["5T"]))
    cards = run(g, lambda: g.decide({"type": "chanter_declare", "player": 0, "count": 2}))
    drawn = [g.cards[c].label() for e in g.last_events if e["t"] == "chanter_declare"
             for d in e["drawn"] for c in d["cards"]]
    queues = [cards]
    while g.decision and g.decision.get("kind") == "chanter_discard":
        a = g.legal_actions()[0]
        queues.append(run(g, lambda: g.decide({"type": "chanter_discard", "player": a["player"],
                                               "cards": a["pick_from"][:a["needs"]]})))
    assert drawn and not any(label in all_text(mine(q)) for q in queues for label in drawn)


def test_the_chanter_row_off_and_a_solo_chanter():
    queues = _chanter_flow(_chanter_game(), off("chanter"))
    assert [my_ids(q) for q in queues] == [[], [], [], ["damage"]]
    assert not any("Chanter" in all_text(q) for q in queues)
    g = camp(1, seed=711, cards=M.CHANTERS)
    set_enemy(g, "J", "H")
    set_hand(g, ["5T", "9S"])
    first = run(g, lambda: g.play(["5T"]))
    assert card(first, "chanter").lines == ["Name 0 to 42 (the reserve's size)",
                                                "Draw that many, even over the limit,", "then discard down to 8"]
    cards = run(g, lambda: g.decide({"type": "chanter_declare", "player": 0, "count": 2}))
    assert card(cards, "damage").lines[0] == "Chanter 2: you drew 2"


# ---------------------------------------------------------------- Reaver
def _reaver_game():
    g = camp(1, seed=440, cards=M.REAVERS)
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["5C", "5R", "9S", "8S", "7S"])
    set_tavern_top(g, ["7H", "2D", "3D"])
    return g


def _reaver_flow(g, settings=None):
    return [run(g, lambda: g.play(["5C", "5R"]), settings),
            run(g, lambda: g.decide({"type": "reaver_count", "count": 2}), settings),
            run(g, lambda: g.decide({"type": "reaver_pick", "card": "7H"}), settings)]


def test_the_reaver_card_before_the_count_box_and_the_pick_on_the_warrior_card():
    first, second, third = _reaver_flow(_reaver_game())
    reaver = card(first, "reaver")
    assert my_ids(first) == ["reaver"] and (reaver.title, reaver.number) == ("Reaver", "10")
    assert reaver.lines == ["Kinfolk 5♣ 5⛏︎ = 10", "Reveal 1 to 39 reserve cards",
                            "Add one's strength to the damage (10)", "No powers; 2/5 adds 5, Jester/beast 0",
                            "Banish all revealed, then the damage ×2"]
    assert my_ids(second) == []
    warrior = card(third, "warrior")
    assert my_ids(third) == ["warrior"] and warrior.middle == "68"
    assert warrior.lines == ["Reaver: 10 + 7 (7♥) = 17, ×2 = 34", "34 ×2 = 68 (Reaver first: ×4 in all)",
                             "Health 100 → 32"]


def test_waiting_lines_crowd_out_the_least_needed_reaver_and_chanter_lines():
    waiting = ["Mage: 2⚝ joins (4 → 6)", "Druid: banished 1 · hand 1 · reserve 2", "Ben put a card on the reserve"]
    g = _reaver_game()
    g.extra["info_carry"] = {"lines": list(waiting)}
    events = [{"t": "decide", "kind": "reaver_count", "player": 0, "max": 39, "damage": 10}]
    reaver = card(info.build(g, events, dict(ON), before=g.to_dict()), "reaver")
    assert reaver.lines == waiting + ["Reveal 1 to 39 reserve cards", "Add one's strength to the damage (10)",
                                      "Banish all revealed, then the damage ×2"]
    g = _chanter_game()
    g.extra["info_carry"] = {"lines": list(waiting)}
    events = [{"t": "decide", "kind": "chanter_declare", "player": 0, "max": 30}]
    chanter = card(info.build(g, events, dict(ON), before=g.to_dict()), "chanter")
    assert chanter.lines[3:] == ["Ana names 0 to 30 (the reserve)", "Everyone draws that many, even over",
                                 "the limit, then discards down to 7"]


def test_the_reaver_row_off_and_an_empty_reserve():
    queues = _reaver_flow(_reaver_game(), off("reaver"))
    assert [my_ids(q) for q in queues] == [[], [], ["warrior"]]
    assert not any("Reaver:" in all_text(q) or "Reveal" in all_text(q) for q in queues)
    g = camp(1, seed=441, cards=M.REAVERS)
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["5R", "9S"])
    g.discard.extend(g.tavern)
    g.tavern = []
    cards = run(g, lambda: g.play(["5R"]))
    assert my_ids(cards) == ["reaver", "damage"]
    assert card(cards, "reaver").lines == ["Reserve empty: nothing to reveal", "The damage just doubles: 5 → 10"]
    assert card(cards, "damage").lines[0] == "Attack 5 · after the Reaver: 10" and card(cards, "damage").middle == "10"


# ---------------------------------------------------------------- formation, reductions, Mission 12
def test_formation_lines_kinfolk_companion_and_beast():
    g = camp(1, seed=300, relics=("flute",))
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "3S", "9S", "8D"])
    cards = run(g, lambda: g.play(["3C", "3S"]))
    assert card(cards, "warrior").lines[0] == "Kinfolk 3♣ 3♠ = 6"
    g = camp(1, seed=330, beast="B_H")
    set_enemy(g, "J", "C")
    set_hand(g, ["B_H", "7C", "9S"])
    set_discard(g, ["2D"])
    cards = run(g, lambda: g.play(["B_H", "7C"]))
    assert my_ids(cards) == ["cleric", "warrior", "damage"]
    assert mine(cards)[0].lines[0] == "Beast copies 7: B♥ + 7♣ = 14"


def test_damage_reductions_name_the_paladin_enemy():
    g = evergreen("B", banes=[11])
    paladin = [x for x in [g.enemy.card_id] + g.castle if "S" in g.cards[x].suits][0]
    set_mission_enemy(g, paladin)
    set_hand(g, ["9C", "6H", "AS"])
    cards = run(g, lambda: g.play(["9C"]))
    assert card(cards, "warrior").middle == "8"
    assert card(cards, "warrior").lines == ["9 ×2 = 18", "− 10: Immovable Paladins", "Health 30 → 22"]


def test_mission_12_heal_counts_the_corrupted_card_sent_to_the_banished_pile():
    c = CampaignState.new(1, ["Ana"], seed=1200)
    c.mission = 12
    c.completed = list(range(1, 12))
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    for cid in ("2S", "3H", "4D", "5C", "7S", "8H", "9D"):
        P.add_flag(c.party, cid, "corrupted")
        c.corrupted.append(cid)
    g = c.start_attempt(seed=1200)
    corrupted = [x for x in g.castle if g.cards[x].has("corrupted")][-1]
    set_discard(g, [corrupted, "2C"])
    set_hand(g, ["6H", "10S", "10C"])
    g.enemy.suits = ()
    cards = run(g, lambda: g.play(["6H"]))
    assert card(cards, "cleric").lines == ["Heal 6: the discard pile is shuffled", "1 goes face down under the reserve",
                                           "M12: 1 corrupted → banished bottom"]


# ---------------------------------------------------------------- long names, 2+ wording
def no_cut(cards):
    """No line of this group's cards was cut short to fit."""
    assert not any(line.endswith("…") for c in mine(cards) for line in c.lines), [c.lines for c in mine(cards)]


def test_long_names_take_a_shorter_wording_and_keep_every_count():
    g = camp(4, seed=7, names=LONG_NAMES)
    set_enemy(g, "J", "H")
    for p, hand in enumerate((["4D", "9S"], ["4C"], ["2C"], ["3C"])):
        set_hand(g, hand, p)
    cards = run(g, lambda: g.play(["4D"]))
    no_cut(cards)
    assert card(cards, "bard").lines == ["Draw 4, one card at a time,", "clockwise from Maximilian Ash",
                                         "Maximilian Ash +1 · Bartholomew Kay +1",
                                         "Christabel Moon +1 · Dorothea Vance +1"]
    g = camp(4, seed=101, cards=M.MAGE_DECK, names=LONG_NAMES)
    set_enemy(g, "K", "H")
    set_hand(g, ["4M", "9S"], 0)
    cards = run(g, lambda: g.play(["4M"]))
    no_cut(cards)
    assert card(cards, "mage").lines[0] == "Maximilian Ash looks at the top 4"
    g = camp(4, seed=322, cards=M.MAGE_DECK, relics=("emblem",), names=LONG_NAMES)
    set_enemy(g, "K", "H")
    for p, hand in enumerate((["4M", "9S"], ["6D"], ["2C"], ["3C"])):
        set_hand(g, hand, p)
    cards = run(g, lambda: g.play(["4M"]))
    no_cut(cards)
    assert card(cards, "mage").lines[0] == "Maximilian Ash will look at the top 4"


def test_a_long_named_chanter_and_druid_keep_to_a_line():
    g = camp(4, seed=710, cards=M.CHANTERS, names=LONG_NAMES)
    set_enemy(g, "J", "H")
    hands = (["5T", "9S", "8S", "7S", "6S"], ["4C", "3D", "2D", "AC", "2C"], ["4H", "3H", "2H", "AH", "5C"],
             ["4S", "3S", "2S", "AD", "5D"])
    for p, hand in enumerate(hands):
        set_hand(g, hand, p)
    queues = [run(g, lambda: g.play(["5T"])),
              run(g, lambda: g.decide({"type": "chanter_declare", "player": 0, "count": 3}))]
    while g.decision and g.decision.get("kind") == "chanter_discard":
        a = g.legal_actions()[0]
        queues.append(run(g, lambda: g.decide({"type": "chanter_discard", "player": a["player"],
                                               "cards": a["pick_from"][:a["needs"]]})))
    for q in queues:
        no_cut(q)
    assert card(queues[0], "chanter").lines[0] == "Maximilian Ash names 0 to 26"
    assert card(queues[-1], "damage").lines[0] == "Chanter 3: each drew 3, 11 discarded"
    for first, line in (("Wilhelmina", "clockwise from Wilhelmina"),
                        ("Bartholomew", "clockwise from the druid's player")):    # shared with Bartholomew Kay
        g = camp(4, seed=700, cards=M.DRUIDS, names=(first + " Montgomery-Smythe",) + LONG_NAMES[1:])
        set_enemy(g, "J", "H")
        set_hand(g, ["5U", "9S"], 0)
        set_discard(g, ["2H", "3H", "4D", "5H"])
        cards = run(g, lambda: g.play(["5U"]))
        no_cut(cards)
        assert line in card(cards, "druid").lines


def test_shared_first_names_are_never_shortened():
    """'Player 1' and 'Player 2' would both shorten to 'Player': the line sums up instead."""
    g = camp(2, seed=710, cards=M.CHANTERS, names=("Player 1", "Player 2"))
    set_enemy(g, "J", "H")
    set_hand(g, ["5T", "9S", "8S", "7S", "6S", "5S", "4S"], 0)
    set_hand(g, ["4C", "3D", "2D", "AC", "2C", "3C", "6C"], 1)
    run(g, lambda: g.play(["5T"]))
    cards = run(g, lambda: g.decide({"type": "chanter_declare", "player": 0, "count": 9}))
    while g.decision and g.decision.get("kind") == "chanter_discard":
        a = g.legal_actions()[0]
        cards = run(g, lambda: g.decide({"type": "chanter_discard", "player": a["player"],
                                         "cards": a["pick_from"][:a["needs"]]}))
    assert card(cards, "damage").lines[0] == "Chanter 9: each drew 9, 17 discarded"


def test_two_players_never_read_your_order():
    g = camp(2, seed=402, number=4, cards=M.MAGE_DECK)
    while g.decision:
        g.decide(g.legal_actions()[0])
    set_hand(g, ["4M", "9S"], 0)
    set_hand(g, ["8S"], 1)
    set_tavern_top(g, ["2C", "6D", "3C", "5S"])
    cards = run(g, lambda: g.play(["4M"]))
    assert card(cards, "mage").lines[-1] == "The rest: discard pile, in chosen order"
    assert "your" not in all_text(mine(cards)).lower()


def test_a_mage_of_strength_0_has_nothing_to_look_at():
    g = camp(1, seed=101, cards=M.MAGE_DECK)
    events = [{"t": "play", "player": 0, "cards": ["3M"], "value": 0, "kind": "single"},
              {"t": "power", "suit": "M", "value": 0, "result": {"peek": 0}},
              {"t": "damage", "amount": 0, "hp": 40, "max_hp": 40}]
    cards = info.build(g, events, dict(ON), before=g.to_dict())
    assert my_ids(cards) == ["mage", "damage"] and card(cards, "mage").lines == ["Nothing to look at: strength 0"]


# ---------------------------------------------------------------- robustness
def test_events_from_older_saves_never_raise():
    """Events missing their fields still build (on the phone a raising builder loses the queue)."""
    g = camp(1, seed=711, cards=M.CHANTERS)
    events = [{"t": "play"}, {"t": "power"}, {"t": "power", "suit": "H"}, {"t": "power", "suit": "C"},
              {"t": "mage_peek"}, {"t": "mage_pick"}, {"t": "druid_deal"}, {"t": "druid_assign"}, {"t": "druid_done"},
              {"t": "decide", "kind": "reaver_count"}, {"t": "decide", "kind": "chanter_declare"},
              {"t": "chanter_declare"}, {"t": "chanter_declare", "count": 2, "drawn": ["x", None, {"player": 1}]},
              {"t": "chanter_discard"}, {"t": "reaver_pick"},
              {"t": "decide", "kind": "emblem_place"}, {"t": "power", "suit": "S"}, {"t": "power", "suit": "G"},
              {"t": "power", "suit": "M", "immune": True}, {"t": "damage"}]
    ctx = info.Ctx(g, events, dict(ON), before=None)
    for i, ev in enumerate(ctx.events):
        ctx.i = i
        for fn in info.HANDLERS.get(ev["t"], ()):
            if fn.__module__ == info_classes.__name__:
                fn(ctx, ev)
    assert info_classes.ERRORS == [] and ctx.cards
    fits(ctx.cards)


def test_a_stand_in_game_without_piles_never_raises():
    """Real events replayed on a bare game object (no piles, no snapshot)."""
    from types import SimpleNamespace as NS
    flows = []
    g = camp(1, seed=450, cards=M.DRUIDS)
    set_enemy(g, "K", "H")
    g.enemy.suits = ("U",)
    set_hand(g, ["5U", "9S"])
    g.play(["5U"])
    flows.append(g.last_events)
    g = _mage_game()
    g.play(["AC", "3M"])
    flows.append(g.last_events)
    g.decide({"type": "mage_pick", "card": "2M"})
    flows.append(g.last_events)
    stand = NS(n_players=2, players=[NS(name="Ana", hand=[]), NS(name="Ben", hand=[])],
               config=NS(rules_id="legacy", max_hand=7), rules=NS(mission=11), cards={}, extra={})
    for events in flows:
        ctx = info.Ctx(stand, events, dict(ON), before=None)
        for i, ev in enumerate(ctx.events):
            ctx.i = i
            for fn in info.HANDLERS.get(ev["t"], ()):
                if fn.__module__ == info_classes.__name__:
                    fn(ctx, ev)
        assert info_classes.ERRORS == [] and ctx.cards
        fits(ctx.cards)
