"""Info pop-ups of the Damage & defeat, Enemy, Enemy strikes and Game end groups, and mission
2's Hydra regrows (app/info_defeat.py), from real game flows: Defeated, Exact kill! and
Hydra regrows at the kill (each falling back to the one it replaces), Clean-up folded into
them or on its own after a box, Team damage, New enemy, Enemy changes, Enemy attacks, No
damage, Feign death, Damage paid, Victory and Defeat. Each card shows in its place in the
queue, keeps to the size limits and leaves nothing when its row is switched off; cards
going into a hidden hand or the reserve are never named, names replace "You" with 2+
players and the base game says "tavern deck"."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()

import pytest  # noqa: E402

from app import info, info_defeat  # noqa: E402
from helpers import _pull, new_game, set_discard, set_enemy, set_hand, set_tavern_top  # noqa: E402
from info_helpers import ON, card, cards_for, fits, ids, start_cards, text  # noqa: E402
from regicide.campaign import CampaignState  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402

NAMES = ["Ana", "Ben", "Cy"]
MINE = ("defeated", "exact_kill", "hydra_regrows", "cleanup", "team_damage", "new_enemy", "enemy_shift",
        "enemy_attack", "shielded", "feign_death", "damage_paid", "victory", "loss")
CORRUPT = ("2S", "3H", "4D", "5C", "6C", "7S", "8H", "9D")


@pytest.fixture(autouse=True)
def _no_swallowed_errors():
    info_defeat.ERRORS.clear()
    yield
    assert info_defeat.ERRORS == []


def mine(cards):
    return [c for c in cards if c.id in MINE]


def my_ids(cards):
    return ids(mine(cards))


def everything(cards):
    return "\n".join(text(c) for c in cards)


def off(*rows):
    return {"info_popups_off": list(rows)}


def run(g, action, settings=None):
    """The queue of one action; this group's cards keep the catalogue's size limits."""
    cards = cards_for(g, action, settings)
    fits(mine(cards))
    return cards


def in_order(cards, *row_ids):
    """These rows' cards come in this order (rows absent from the queue are passed over)."""
    seen = [r for r in row_ids if r in ids(cards)]
    assert [i for i in ids(cards) if i in seen] == seen, (ids(cards), row_ids)


# ---------------------------------------------------------------------------- games
def base(players=1, seed=5, hp=None, attack=None, hand=("5C", "9S"), castle=True):
    g = new_game(players, seed=seed)
    set_enemy(g, "J", "H", hp=hp, attack=attack)
    set_hand(g, list(hand))
    if not castle:
        g.castle = []
    return g


def camp(players=1, seed=100, number=1, cards=(), corrupted=(), beast="B_H"):
    """A Legacy attempt at mission ``number`` (its setup choices taken) with these party
    cards and corrupted cards."""
    c = CampaignState.new(players, NAMES[:players], seed=seed)
    c.mission = number
    c.completed = list(range(1, number))
    for d in cards:
        if P.find(c.party, str(d["id"])) is None:
            P.add_card(c.party, dict(d))
    for cid in corrupted:
        P.add_flag(c.party, cid, "corrupted")
        c.corrupted.append(cid)
    c.flags["beasts"] = True
    c.set_beast(beast)
    if c.prepare_mission():
        while c.pending:
            step = c.pending_choice()
            c.resolve_choice(step["options"][0] if step.get("options") else {})
    return c.start_attempt(seed=seed)


def evergreen(location="A", banes=(), boons=(), seed=5000):
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
    c.evergreen["setup"] = {"location": location, "banes": sorted(banes), "boons": sorted(boons)}
    return c.start_evergreen_attempt(seed=seed)


def rig(g, attr, ids_):
    """Exactly ``ids_`` in the pile ``attr`` (its cards go under the reserve)."""
    old = list(getattr(g, attr))
    setattr(g, attr, [])
    g.tavern.extend(old)
    for x in ids_:
        _pull(g, x)
    setattr(g, attr, list(ids_))


# ---------------------------------------------------------------------------- Exact kill!, Defeated
def test_a_base_exact_kill_names_the_tavern_deck_and_folds_the_clean_up():
    g = base(hp=10)
    cards = run(g, lambda: g.play(["5C"]))
    in_order(cards, "warrior", "exact_kill", "new_enemy", "turn")
    assert "cleanup" not in ids(cards) and "defeated" not in ids(cards)
    exact = card(cards, "exact_kill")
    assert (exact.title, exact.number) == ("Exact kill!", "10")
    assert exact.lines == ["Jack of H → top of the tavern deck", "You go again", "5♣ → discard pile"]
    assert exact.sounds == ["info_exact_kill", "exact_kill"]


def test_exact_kill_falls_back_to_defeated_then_to_clean_up():
    g = base(hp=10)
    cards = run(g, lambda: g.play(["5C"]), off("exact_kill"))
    assert my_ids(cards) == ["defeated", "new_enemy"]
    assert card(cards, "defeated").lines[0] == "Jack of H → top of the tavern deck"
    g = base(hp=10)
    cards = run(g, lambda: g.play(["5C"]), off("exact_kill", "defeated"))
    assert my_ids(cards) == ["cleanup", "new_enemy"]       # Defeated replaces Clean-up
    assert card(cards, "cleanup").lines == ["Jack of H → top of the tavern deck", "5♣ → discard pile"]
    g = base(hp=10)
    cards = run(g, lambda: g.play(["5C"]), off("exact_kill", "defeated", "cleanup"))
    assert my_ids(cards) == ["new_enemy"] and "discard pile" not in everything(cards)


def test_defeated_folds_the_clean_up_and_its_row_off_takes_the_lines_too():
    g = base(hp=8, hand=("5C", "9S"))
    cards = run(g, lambda: g.play(["5C"]))
    in_order(cards, "warrior", "defeated", "new_enemy", "turn")
    defeated = card(cards, "defeated")
    assert (defeated.title, defeated.number, defeated.icon) == ("Defeated", "10", None)
    assert defeated.lines == ["Jack of H → discard pile", "5♣ → discard pile"]
    g = base(hp=8)
    cards = run(g, lambda: g.play(["5C"]), off("cleanup"))
    assert card(cards, "defeated").lines == ["Jack of H → discard pile"]


def test_the_exact_kill_names_who_goes_again_with_two_players():
    g = base(players=2, seed=7, hp=10)
    cards = run(g, lambda: g.play(["5C"]))
    assert "Player 1 goes again" in card(cards, "exact_kill").lines
    assert "You" not in everything(mine(cards))


def test_a_mage_attack_is_banished_at_the_clean_up():
    g = camp(1, seed=101, cards=M.MAGE_DECK)
    set_enemy(g, "J", "H", hp=6)
    set_hand(g, ["3M", "9S", "8S"])
    set_tavern_top(g, ["3C", "2D", "4H"])
    run(g, lambda: g.play(["3M"]))
    cards = run(g, lambda: g.decide({"type": "mage_pick", "card": "3C"}))
    in_order(cards, "warrior", "defeated", "new_enemy")
    assert card(cards, "defeated").lines == ["Jack of H → discard pile", "2 played → banished (a mage attack)"]


# ---------------------------------------------------------------------------- a box before the clean-up
def _m3_exact():
    g = camp(1, seed=903, number=3, cards=M.MAGE_DECK)
    set_hand(g, ["3C", "9S", "8S", "7D"])
    set_tavern_top(g, ["4H", "5D"])
    g.play(["3C"])
    g.suffer(["9S", "7D"])                 # the end of turn: 4♥ joins the zone
    set_hand(g, ["6H", "9S"])
    g.enemy.hp = 6
    return g


def test_a_box_before_the_defeat_gives_the_kill_card_then_its_own_clean_up():
    g = _m3_exact()
    first = run(g, lambda: g.play(["6H"]))
    assert my_ids(first) == ["exact_kill"] and g.decision["kind"] == "zone_rescue"
    exact = card(first, "exact_kill")
    assert exact.lines == ["Instructor falls exactly → banished", "Zone → banished", "Bonus: rescue a zone card",
                           "You go again; no end-of-turn effects"]
    second = run(g, lambda: g.decide({"type": "zone_rescue", "player": 0, "card": "4H"}))
    in_order(second, "cleanup", "new_enemy", "turn")
    cleanup = card(second, "cleanup")
    assert (cleanup.title, cleanup.number) == ("Clean-up", "2")
    assert cleanup.lines == ["Instructor → banished", "2 played → discard pile, 6♥ on top",
                             "Rescued 4♥ to the discard pile"]
    assert "dft" not in g.extra["info_carry"]


def test_the_clean_up_row_off_leaves_no_card_and_no_choice_line():
    g = _m3_exact()
    run(g, lambda: g.play(["6H"]), off("cleanup"))
    cards = run(g, lambda: g.decide({"type": "zone_rescue", "player": 0, "card": "4H"}), off("cleanup"))
    assert "cleanup" not in ids(cards) and "Rescued" not in everything(cards)


def test_an_order_box_has_no_card_the_defeated_card_says_why_it_matters():
    g = camp(1, seed=904, number=4, cards=M.MAGE_DECK)
    set_discard(g, ["7C"])
    set_hand(g, ["AH", "6C", "9S", "8S"])
    g.enemy.hp = 10
    first = run(g, lambda: g.play(["AH", "6C"]))
    assert g.decision["kind"] == "played_discard_order"
    defeated = card(first, "defeated")
    assert defeated.number == "17"                         # 10 + the top discard 7♣
    assert defeated.lines == ["Phase I Experiment → discard pile", "Next: order the played cards; top counts"]
    second = run(g, lambda: g.decide({"type": "played_discard_order", "player": 0, "cards": ["6C", "AH"]}))
    in_order(second, "cleanup", "new_enemy")
    assert card(second, "cleanup").lines[1] == "2 played → discard pile, A♥ on top"
    assert "Attack 10 +1 top discard" in card(second, "new_enemy").lines


def test_mission_8_choices_and_the_pick_after_the_clean_up_are_lines():
    g = camp(1, seed=908, number=8, cards=list(M.CHANTERS) + [M.GORAN])
    g.enemy.hp = 3
    g.enemy.suits = ()
    set_hand(g, ["AH", "2S", "9S"])
    first = run(g, lambda: g.play(["AH", "2S"]))
    assert "Next: build the zone, one strength up" in card(first, "exact_kill").lines
    assert "Bonus: a discard on top of the reserve" in card(first, "exact_kill").lines
    second = run(g, lambda: g.decide({"type": "zone_build", "player": 0, "card": "2S"}))
    assert card(second, "cleanup").lines == ["Troll → banished", "A♥ → discard pile",
                                             "Zone built: 2♠ (enemies +2)", "Next: a discard on top of the reserve"]
    picked = g.discard[0]
    third = run(g, lambda: g.decide({"type": "discard_pick", "player": 0, "card": picked}))
    assert card(third, "new_enemy").lines[0] == "A discard → top of the reserve"
    assert g.cards[picked].label() not in everything(mine(third))        # it went into the reserve


def test_mission_9_and_the_boons_never_name_a_card_going_to_a_hand_or_the_reserve():
    g = camp(1, seed=909, number=9, cards=[M.GORAN])
    g.enemy.hp = 6
    g.enemy.suits = ()
    set_hand(g, ["3C", "9S"])
    first = run(g, lambda: g.play(["3C"]))
    assert "Bonus: a pile's top → top of the reserve" in card(first, "exact_kill").lines
    second = run(g, lambda: g.decide({"type": "pile_to_reserve", "player": 0, "pile": 1}))
    moved = [e for e in g.last_events if e["t"] == "pile_to_reserve"][0]["card"]
    assert "A captured pile's top → reserve top" in card(second, "cleanup").lines
    assert g.cards[moved].label() not in everything(mine(second))
    g = evergreen("A", boons=(32, 33), seed=5116)
    rig(g, "mission_zone", ["4H"])
    rig(g, "banished", ["6D"])
    g.enemy.hp = 1
    g.enemy.suits = ()
    set_hand(g, ["AS", "9S"])
    first = run(g, lambda: g.play(["AS"]))
    assert "Bonus: Precision Strike, Restored Arrows" in card(first, "exact_kill").lines
    run(g, lambda: g.decide({"type": "precision_strike", "player": 0, "card": "4H", "pile": "zone"}))
    third = run(g, lambda: g.decide({"type": "restored_arrows", "player": 0, "card": "6D"}))
    cleanup = card(third, "cleanup")
    assert cleanup.lines[-2:] == ["You took a zone card into hand", "A banished card → under the reserve"]
    assert "4♥" not in everything(mine(third)) and "6♦" not in everything(mine(third))


def test_the_zone_cards_are_named_at_the_clean_up_and_the_forest_shuffles():
    g = evergreen("C", seed=5106)
    rig(g, "mission_zone", ["4H", "5H"])
    g.enemy.hp = 1
    g.enemy.suits = ()
    set_hand(g, ["AS", "9S"])
    first = run(g, lambda: g.play(["AS"]))
    assert "Bonus: discard a zone card first" in card(first, "exact_kill").lines
    second = run(g, lambda: g.decide({"type": "zone_discard", "player": 0, "card": "4H"}))
    assert card(second, "cleanup").lines == ["Phase II Experiment → banished", "Zone 5♥ → banished",
                                             "A♠ → discard pile", "Discarded 4♥ from the zone",
                                             "Banished pile shuffled"]


def test_the_lake_banishes_reserve_cards_as_a_line_on_the_kill_card():
    g = evergreen("E", seed=5108)
    rig(g, "mission_zone", ["4H", "5H"])
    g.enemy.hp = 1
    g.enemy.suits = ()
    set_hand(g, ["AS", "9S"])
    cards = run(g, lambda: g.play(["AS"]))
    exact = card(cards, "exact_kill")
    assert "2 reserve cards banished (Lake)" in exact.lines
    assert "Next: name the zone's discard order" in exact.lines


# ---------------------------------------------------------------------------- Hydra regrows
def test_a_hydra_not_dealt_exact_damage_regrows_and_falls_back_to_defeated():
    g = camp(1, seed=902, number=2)
    g.enemy.hp = 3
    hydra = g.cards[g.enemy.card_id]
    set_hand(g, ["5H", "9S", "8D"])
    cards = run(g, lambda: g.play(["5H"]))
    in_order(cards, "damage", "hydra_regrows", "new_enemy", "turn")
    regrows = card(cards, "hydra_regrows")
    assert (regrows.title, regrows.number) == ("Hydra regrows", "10")
    assert regrows.icon == "".join({"H": "♥", "C": "♣", "D": "♦", "S": "♠"}[s] for s in hydra.suits)
    assert regrows.lines == ["Not exact: Hydra Head goes face down", "under the castle; it will come back",
                             "Exact damage banishes a Hydra for good", "5♥ → discard pile"]
    g = camp(1, seed=902, number=2)
    g.enemy.hp = 3
    set_hand(g, ["5H", "9S", "8D"])
    cards = run(g, lambda: g.play(["5H"]), off("hydra_regrows"))
    assert "hydra_regrows" not in ids(cards)
    assert card(cards, "defeated").lines[0] == "Hydra Head → bottom of the castle"


def test_evergreen_bane_1_regrows_a_hydra_head_too():
    g = evergreen("A", banes=(1,), seed=5119)
    g.enemy.hp = 1
    g.enemy.suits = ()
    set_hand(g, ["2S", "10S"])
    cards = run(g, lambda: g.play(["2S"]))
    assert "hydra_regrows" in ids(cards) and "defeated" not in ids(cards)


# ---------------------------------------------------------------------------- mission 5's carry kill
def test_a_carry_kill_shows_its_card_after_the_new_enemy_and_the_carry_damage():
    g = camp(1, seed=990, number=5, cards=list(M.MAGE_DECK) + list(M.REAVERS) + [M.GORAN])
    rig(g, "mission_zone", ["9H", "8H"])
    nxt = g.castle[0]
    g.cards[nxt] = g.cards[nxt].with_changes(health=20)
    g.enemy.hp = 6
    set_hand(g, ["3C", "9S"])
    cards = run(g, lambda: g.play(["3C"]))
    assert my_ids(cards) == ["exact_kill", "new_enemy", "defeated", "new_enemy"]
    in_order(cards, "exact_kill", "m5_carry", "defeated")
    exact = card(cards, "exact_kill")
    assert exact.number == "27" and "Bonus: next enemy takes 27" in exact.lines
    assert exact.lines[-1] == "Banished pile shuffled"
    second = [c for c in cards if c.id == "defeated"][0]
    assert second.lines == ["Sporeling → banished", "Banished pile shuffled"]


# ---------------------------------------------------------------------------- Team damage
def _m6(players, seed, hp, hands):
    g = camp(players, seed=seed, number=6, cards=list(M.GUARDIANS) + [M.GORAN])
    g.enemy.hp = hp
    for p, hand in enumerate(hands):
        set_hand(g, hand, p)
    return g


def test_mission_6_team_damage_with_two_players_hides_the_hands_total():
    g = _m6(2, 906, 5, (["5D", "9S", "8S"], ["7D", "6H", "AH"]))
    first = run(g, lambda: g.play(["5D"]))
    exact = card(first, "exact_kill")
    assert exact.lines[-3:] == ["Ana goes again", "Next: move a played card into the zone",
                                "Then Myla's team damage: zone strength"]
    assert my_ids(run(g, lambda: g.decide({"type": "zone_move", "player": 0, "card": "5D"}))) == []
    third = run(g, lambda: g.decide({"type": "zone_rescue", "player": 0, "card": "5D"}))
    team = card(third, "team_damage")
    assert (team.title, team.number, team.middle, team.caption) == ("Team damage", "", "7", "for the whole party")
    assert team.lines == ["Myla: 7, the zone's strength", "Anyone, one at a time; no feign death"]
    assert "hand" not in everything([team]).lower()
    assert my_ids(run(g, lambda: g.decide({"type": "team_discard", "player": 1, "card": "6H"}))) == []
    last = run(g, lambda: g.decide({"type": "team_discard", "player": 1, "card": "AH"}))
    in_order(last, "cleanup", "new_enemy", "turn")
    assert card(last, "cleanup").lines == ["Team damage paid: 7 of 7", "Guardian Statue → banished",
                                           "Ana moved 5♦ into the zone", "Rescued 5♦ to the discard pile"]


def test_the_team_damage_row_off_leaves_no_card_and_no_paid_line():
    g = _m6(2, 906, 5, (["5D", "9S", "8S"], ["7D", "6H", "AH"]))
    settings = off("team_damage")
    run(g, lambda: g.play(["5D"]), settings)
    run(g, lambda: g.decide({"type": "zone_move", "player": 0, "card": "5D"}), settings)
    cards = run(g, lambda: g.decide({"type": "zone_rescue", "player": 0, "card": "5D"}), settings)
    assert "team_damage" not in ids(cards)
    run(g, lambda: g.decide({"type": "team_discard", "player": 1, "card": "6H"}), settings)
    cards = run(g, lambda: g.decide({"type": "team_discard", "player": 1, "card": "AH"}), settings)
    assert "Team damage paid" not in everything(cards)


def test_team_damage_too_high_loses_the_mission_and_the_loss_is_last():
    g = _m6(1, 962, 3, (["AH", "3S"],))
    run(g, lambda: g.play(["AH", "3S"]))
    set_hand(g, [])
    cards = run(g, lambda: g.decide({"type": "zone_move", "player": 0, "card": "AH"}))
    assert my_ids(cards) == ["team_damage", "loss"] and ids(cards)[-1] == "loss"
    assert "Not enough in hand: the mission is lost" in card(cards, "team_damage").lines
    loss = card(cards, "loss")
    assert loss.title == "Mission lost"
    assert loss.lines == ["Team damage too high", "Guardian Statue fell; 7 enemies left"]
    assert loss.sounds == ["info_loss", "loss"]


def test_a_guardian_prevents_myla_and_the_prevention_is_a_line():
    g = _m6(1, 961, 3, (["AH", "3G", "9S"],))
    first = run(g, lambda: g.play(["AH", "3G"]))
    assert "guardian" not in ids(first)                    # a killing blow: no Guardian card
    assert card(first, "defeated").lines[-1] == "A Guardian prevents Myla's team damage"
    second = run(g, lambda: g.decide({"type": "zone_move", "player": 0, "card": "AH"}))
    assert "team_damage" not in ids(second)
    assert card(second, "cleanup").lines[0] == "Guardian: no team damage (Myla 8)"


def test_explosive_spores_team_damage_comes_after_the_kill_and_its_payment_on_the_clean_up():
    g = evergreen("A", banes=(13, 14, 15), seed=5118)
    set_discard(g, ["2D", "3D"])
    g.enemy.hp = 1
    g.enemy.suits = ()
    set_hand(g, ["2S", "10S", "10C", "9C"])
    first = run(g, lambda: g.play(["2S"]))
    in_order(first, "damage", "defeated", "bane15", "team_damage")
    assert card(first, "defeated").lines == ["Phase II Experiment → banished"]
    assert card(first, "team_damage").lines == ["Explosive Spores: 15, its strength",
                                                "Anyone, one at a time; no feign death", "Your hand holds 29"]
    run(g, lambda: g.decide({"type": "team_discard", "player": 0, "card": "10S"}))
    last = run(g, lambda: g.decide({"type": "team_discard", "player": 0, "card": "10C"}))
    in_order(last, "cleanup", "bane14", "new_enemy", "turn")
    cleanup = card(last, "cleanup")
    assert cleanup.number == "" and cleanup.lines == ["Team damage paid: 20 of 15", "Phase II Experiment → banished"]


def test_the_hills_team_damage_follows_the_hills_card_and_is_paid_on_the_turn_card():
    g = evergreen("D", seed=5104)
    rig(g, "banished", ["3D"])
    g.enemy.suits = ()
    set_hand(g, ["AS", "10S", "10C", "10D", "9S", "9C"])
    run(g, lambda: g.play(["AS"]))
    cards = run(g, lambda: g.suffer(["10S", "10C"]))
    in_order(cards, "damage_paid", "hills", "team_damage")
    assert card(cards, "team_damage").lines[0] == "The Hills: 3, the zone's strength"
    cards = run(g, lambda: g.decide(g.legal_actions()[0]))
    assert "Team damage paid: 10 of 3" in card(cards, "turn").lines


# ---------------------------------------------------------------------------- New enemy
def test_new_enemy_after_a_kill_but_never_at_the_start():
    g = new_game(1, seed=5)
    assert "new_enemy" not in ids(start_cards(g))
    g = base(hp=8)
    cards = run(g, lambda: g.play(["5C"]))
    new = card(cards, "new_enemy")
    assert (new.title, new.number, new.middle, new.caption, new.icon) == ("Jack of Diamonds", "10", "20", "health", "D")
    assert new.lines == ["Immune: ♦", "10 more in the castle"]
    assert new.sounds == ["info_new_enemy", "new_enemy"]
    g = base(hp=8)
    assert "new_enemy" not in ids(run(g, lambda: g.play(["5C"]), off("new_enemy")))


def test_new_enemy_shows_the_pile_tops_and_a_classless_enemy_has_no_icon():
    g = camp(1, seed=911, number=11, cards=list(M.MAGE_DECK) + [M.GORAN_RENEWED, M.ASH], corrupted=CORRUPT, beast=None)
    if g.decision:
        g.decide(g.legal_actions()[0])
    g.enemy.hp = 1
    set_hand(g, ["AS", "9S"])
    cards = run(g, lambda: g.play(["AS"]))
    new = card(cards, "new_enemy")
    assert (new.title, new.icon, new.number) == ("Justicar", "", "21")
    assert new.lines == ["Immune: ♠ (pile tops)", "Attack 10 +11 pile tops", "3 more in the castle"]
    assert "Bonus: no beast next turn" in card(cards, "exact_kill").lines


def test_new_enemy_shows_the_enemy_as_it_came_before_the_start_of_turn_zone_card():
    g = camp(1, seed=912, number=12, cards=list(M.MAGE_DECK) + [M.ESME_REBORN, M.ASH], corrupted=CORRUPT[:4],
             beast=None)
    g.enemy.hp = 1
    g.enemy.suits = ()
    set_hand(g, ["3S", "9S"])
    cards = run(g, lambda: g.play(["3S"]))                 # not exact: the zone grows at the turn's start
    assert any(e["t"] == "zone_add" for e in g.last_events)
    new = card(cards, "new_enemy")
    assert int(new.number) == g.enemy.attack                 # before the banished top joined the zone
    assert g.enemy_attack > int(new.number)


# ---------------------------------------------------------------------------- Enemy changes
def _m4_druid():
    g = camp(1, seed=904, number=4, cards=list(M.DRUIDS))
    set_discard(g, ["7C", "2H", "3H", "4H", "5H", "6H"])
    set_hand(g, ["5U", "9S", "8S"])
    return g


def test_enemy_changes_when_a_step_moves_a_pile_top_before_a_box():
    g = _m4_druid()
    cards = run(g, lambda: g.play(["5U"]))
    assert ids(cards)[-2:] == ["druid", "enemy_shift"]
    shift = card(cards, "enemy_shift")
    assert (shift.title, shift.number) == ("Enemy changes", "10")
    assert shift.lines == ["Attack 17 → 10 (discard pile empty)"]
    g = _m4_druid()
    assert "enemy_shift" not in ids(run(g, lambda: g.play(["5U"]), off("enemy_shift")))


def test_enemy_changes_stands_after_the_step_that_changed_it_and_names_new_immunity():
    g = camp(1, seed=911, number=11, cards=list(M.MAGE_DECK) + [M.GORAN_RENEWED, M.ASH], corrupted=CORRUPT, beast=None)
    if g.decision:
        g.decide(g.legal_actions()[0])
    set_hand(g, ["5C", "5M", "9S"])
    set_tavern_top(g, ["8S", "2D", "4C", "5H", "7D", "AD"])
    cards = run(g, lambda: g.play(["5C", "5M"]))
    in_order(cards, "corrupted", "enemy_shift", "mage")
    assert card(cards, "enemy_shift").lines == ["Attack 11 → 19 (banished top 8♠)", "Immune: ♣ → ♣♠"]


def test_enemy_changes_stays_away_when_the_strike_states_the_attack():
    g = camp(1, seed=904, number=4)
    set_discard(g, ["7C", "2D"])
    set_hand(g, ["5H", "10S", "9S", "8S"])
    cards = run(g, lambda: g.play(["5H"]))              # the heal moves the top discard
    assert "enemy_attack" in ids(cards) and "enemy_shift" not in ids(cards)


# ---------------------------------------------------------------------------- Enemy attacks, No damage
def test_enemy_attacks_in_the_base_game_and_with_shields():
    g = base(hand=("3C", "9S", "8D"))
    cards = run(g, lambda: g.play(["3C"]))
    in_order(cards, "warrior", "enemy_attack")
    strike = card(cards, "enemy_attack")
    assert (strike.title, strike.number, strike.middle, strike.caption) == ("Enemy attacks", "10", "10", "to discard")
    assert strike.lines == ["Attack 10, no shields", "Discard cards worth 10 or more"]
    g = evergreen("D", seed=5104)
    g.enemy.suits = ()
    set_hand(g, ["AS", "10S", "10C"])
    cards = run(g, lambda: g.play(["AS"]))
    in_order(cards, "damage", "paladin", "enemy_attack")
    assert card(cards, "enemy_attack").lines == ["15 − 1 shields = 14", "Discard one at a time; stop once covered"]


def test_enemy_attacks_names_who_pays_and_its_row_off_leaves_nothing():
    g = new_game(2, seed=7)
    set_enemy(g, "J", "H")
    set_hand(g, ["5H", "9S"], 0)
    set_hand(g, ["4C", "8S"], 1)
    cards = run(g, lambda: g.yield_turn())
    in_order(cards, "yield", "enemy_attack")
    assert card(cards, "enemy_attack").lines[-1] == "Player 1 discards cards worth 10 or more"
    g = new_game(2, seed=7)
    set_enemy(g, "J", "H")
    set_hand(g, ["5H", "9S"], 0)
    assert "enemy_attack" not in ids(run(g, lambda: g.yield_turn(), off("enemy_attack")))


def test_enemy_attacks_offers_feign_death_then_feign_death_and_damage_paid():
    g = camp(1, seed=4)
    set_enemy(g, "K", "H")
    set_hand(g, ["2C", "AS", "AD", "AH", "2D", "2S", "2H", "3C", "3D"])
    cards = run(g, lambda: g.play(["2C"]))
    assert card(cards, "enemy_attack").lines[-1] == "Not enough in hand: feign death instead"
    cards = run(g, lambda: g.suffer(list(g.active_player.hand)))
    in_order(cards, "feign_death", "damage_paid", "turn")
    feign = card(cards, "feign_death")
    assert (feign.title, feign.number, feign.icon) == ("Feign death", "20", None)
    assert feign.lines == ["You discard the whole hand: 8 cards", "At the limit (8) it covers any damage",
                           "20 damage satisfied"]
    paid = card(cards, "damage_paid")
    assert (paid.number, paid.middle, paid.caption) == ("20", "15", "paid")
    assert paid.lines == ["You discarded 8: A♠ A♦ A♥ 2♦ 2♠ 2♥ 3♣ 3♦", "Hand: 0 left"]
    g = camp(1, seed=4)
    set_enemy(g, "K", "H")
    set_hand(g, ["2C", "AS", "AD", "AH", "2D", "2S", "2H", "3C", "3D"])
    g.play(["2C"])
    cards = run(g, lambda: g.suffer(list(g.active_player.hand)), off("feign_death"))
    assert my_ids(cards) == ["damage_paid"]


def test_feign_death_names_the_player_with_two_players():
    g = camp(2, seed=4)
    set_enemy(g, "K", "H")
    set_hand(g, ["2C", "AS", "AD", "AH", "2D", "2S", "2H", "3C"], 0)
    g.play(["2C"])
    assert len(g.players[0].hand) == g.config.max_hand
    cards = run(g, lambda: g.suffer(list(g.players[0].hand)))
    assert card(cards, "feign_death").lines[0] == "Ana discards the whole hand: 7 cards"
    assert card(cards, "damage_paid").lines[0] == "Ana discarded 7: A♠ A♦ A♥ 2♦ 2♠ 2♥ 3♣"
    assert "You" not in everything(mine(cards))


def test_no_damage_when_the_shields_cover_and_the_guardian_card_stands_in():
    g = base(attack=5, hand=("6S", "9S"))
    cards = run(g, lambda: g.play(["6S"]))
    in_order(cards, "paladin", "shielded", "turn")
    shield = card(cards, "shielded")
    assert (shield.title, shield.number, shield.middle, shield.icon) == ("No damage", "5", "0", None)
    assert shield.lines == ["Shields 6 cover the attack 5", "Nothing to discard; the turn ends"]
    assert shield.face_args({})["edge"] == info.T.SUIT_COLOR["S"]
    g = base(attack=5, hand=("6S", "9S"))
    assert "shielded" not in ids(run(g, lambda: g.play(["6S"]), off("shielded")))

    def guardian():
        g = camp(1, seed=450, cards=M.GUARDIANS)
        set_enemy(g, "K", "H")
        set_hand(g, ["5G", "9S", "2D"])
        return g
    g = guardian()
    cards = run(g, lambda: g.play(["5G"]))
    assert "guardian" in ids(cards) and "shielded" not in ids(cards)
    g = guardian()
    cards = run(g, lambda: g.play(["5G"]), off("guardian"))
    shield = card(cards, "shielded")
    assert shield.icon == "G" and shield.lines[0] == "A Guardian protects the party"


# ---------------------------------------------------------------------------- Damage paid
def test_damage_paid_names_the_discards_and_counts_the_hand_left():
    g = base(hand=("3C", "9S", "8D", "4H"))
    g.play(["3C"])
    cards = run(g, lambda: g.suffer(["9S", "8D"]))
    in_order(cards, "damage_paid", "turn")
    paid = card(cards, "damage_paid")
    assert (paid.title, paid.number, paid.middle) == ("Damage paid", "10", "17")
    assert paid.lines == ["You discarded 2: 9♠ 8♦", "Hand: 1 left"]
    g = new_game(2, seed=7)
    set_enemy(g, "J", "H")
    set_hand(g, ["5H", "9S"], 0)
    g.yield_turn()
    cards = run(g, lambda: g.suffer(["9S", "5H"]))
    assert card(cards, "damage_paid").lines[0] == "Player 1 discarded 2: 9♠ 5♥"
    g = base(hand=("3C", "9S", "8D"))
    g.play(["3C"])
    assert "damage_paid" not in ids(run(g, lambda: g.suffer(["9S", "8D"]), off("damage_paid")))


def test_a_close_call_payment_goes_under_the_reserve_and_is_never_named():
    g = evergreen("A", boons=(35,), seed=5114)
    rig(g, "mission_zone", ["10H", "5H"])
    g.enemy.suits = ()
    set_discard(g, ["2D", "3D"])
    g.enemy.attack = 11
    set_hand(g, ["AS", "10S", "9C"])
    g.play(["AS"])
    cards = run(g, lambda: g.suffer(["10S"]))
    assert card(cards, "damage_paid").lines == ["You discarded 1 card", "Hand: 1 left"]
    assert "10♠" not in everything(mine(cards))


# ---------------------------------------------------------------------------- Victory, Defeat
def test_a_solo_base_victory_is_the_last_card_with_its_medal():
    g = base(hp=5, castle=False)
    cards = run(g, lambda: g.play(["5C"]))
    assert ids(cards)[-1] == "victory" and "new_enemy" not in ids(cards) and "turn" not in ids(cards)
    win = card(cards, "victory")
    assert (win.title, win.icon) == ("Gold victory!", None)
    assert win.lines == ["Jack of H was the last enemy, in 1 turn", "Jesters used: 0"]
    assert win.sounds == ["info_victory", "victory"]
    g = base(hp=5, castle=False)
    cards = run(g, lambda: g.play(["5C"]), off("victory"))
    assert "victory" not in ids(cards) and ids(cards)[-1] == "defeated"


def test_a_legacy_victory_names_the_mission_and_stays_last_after_other_finishers(monkeypatch):
    late = info.InfoCard("turn", "A late card")
    monkeypatch.setattr(info, "FINISHERS", info.FINISHERS + [lambda ctx: ctx.add(late)])
    g = camp(1, seed=901)
    g.castle = []
    g.enemy.hp = 2
    set_hand(g, ["2C", "9S"])
    cards = run(g, lambda: g.play(["2C"]))
    assert ids(cards)[-1] == "victory" and late in cards
    win = card(cards, "victory")
    assert win.title == "Victory!"
    assert win.lines == ["Bard Justicar was the last enemy", "Won in 1 turn", "Mission 1 complete: rewards next"]


def test_defeat_after_the_strike_is_the_last_card_with_its_reason():
    g = base(hand=("2C",))
    g.solo_jesters = 0
    cards = run(g, lambda: g.play(["2C"]))
    assert my_ids(cards) == ["enemy_attack", "loss"] and ids(cards)[-1] == "loss"
    assert card(cards, "enemy_attack").lines[-1] == "Not enough in hand: the game is lost"
    loss = card(cards, "loss")
    assert (loss.title, loss.icon) == ("Defeat", None)
    assert loss.lines == ["Cannot pay 10 damage", "Jack of H: 16 health left", "12 enemies left"]
    g = base(hand=("2C",))
    g.solo_jesters = 0
    cards = run(g, lambda: g.play(["2C"]), off("loss"))
    assert "loss" not in ids(cards)


def test_a_legacy_loss_names_the_player_with_two_players_and_an_abandon():
    g = camp(3, seed=3)
    set_enemy(g, "J", "H")
    jid = [x for x in g.cards if g.cards[x].is_jester][0]
    set_hand(g, [jid, "9S"], 0)
    set_hand(g, ["5H", "8S"], 1)
    set_hand(g, ["2C"], 2)
    g.play([jid])
    g.choose_next(1)
    cards = run(g, lambda: g.play(["5H"]))
    loss = card(cards, "loss")
    assert loss.title == "Mission lost" and loss.lines[0] == "Ben cannot pay 10 damage"
    assert card(cards, "enemy_attack").lines[1] == "Ben discards one at a time until covered"
    g = new_game(1, seed=5)
    cards = run(g, lambda: g.abandon())
    assert ids(cards) == ["loss"] and card(cards, "loss").lines[0] == "Abandoned"


# ---------------------------------------------------------------------------- robustness
def test_events_from_older_saves_never_raise():
    """Events missing their fields still build (on the phone a raising builder loses the queue)."""
    g = camp(1, seed=711)
    events = [{"t": "damage", "hp": 0}, {"t": "defeat"}, {"t": "reveal"}, {"t": "carry_damage", "hp": 0},
              {"t": "defeat", "enemy": "nope", "plan": None}, {"t": "zone_cleared"}, {"t": "team_damage"},
              {"t": "team_damage_done"}, {"t": "team_damage_prevented"}, {"t": "suffer_due"}, {"t": "no_damage"},
              {"t": "feign_death"}, {"t": "suffer"}, {"t": "zone_move"}, {"t": "precision_strike"},
              {"t": "pile_to_reserve"}, {"t": "zone_filled"}, {"t": "won"}, {"t": "lost"}]
    cards = info.build(g, events, dict(ON), before=g.to_dict())
    assert info_defeat.ERRORS == [] and cards
    fits(mine(cards))
