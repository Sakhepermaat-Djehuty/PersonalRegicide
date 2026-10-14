"""Regression tests for the adversarial review's findings (one test or more per finding;
the UI findings are in test_app.py)."""
import copy
import json
import random

import pytest

from helpers import set_discard, set_enemy, set_hand, set_mission_enemy, set_tavern_top, _pull
from regicide.bots import (apply_action, greedy_policy, min_waste_discard, play_out, random_policy,
                           sequential_payment_ok, simple_decision)
from regicide.campaign import CampaignState
from regicide.campaign import evergreen as E
from regicide.campaign import missions as M
from regicide.campaign import party as P
from regicide.campaign.mercenaries import by_id
from regicide.engine import PHASE_DECIDE, PHASE_LOST, PHASE_PLAY, PHASE_SUFFER, Game, IllegalAction
from regicide.rules import GameConfig


def mission(number, players=1, seed=800, relics=(), beast=None, corrupted=(), extra_cards=(), mages=True,
            stickers=(), mercs=()):
    names = ["Ana", "Ben", "Cy", "Dee"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.mission = number
    c.completed = list(range(1, number))
    c.relics.extend(relics)
    if number >= 4:
        P.add_card(c.party, dict(M.GORAN))
        c.flags["beasts"] = True
        c.set_beast(beast)
    if mages and number >= 4:
        for d in M.MAGE_DECK:
            if P.find(c.party, str(d["id"])) is None:
                P.add_card(c.party, dict(d))
    for d in extra_cards:
        if P.find(c.party, str(d["id"])) is None:
            P.add_card(c.party, dict(d))
    for cid in corrupted:
        P.add_flag(c.party, cid, "corrupted")
        c.corrupted.append(cid)
    for cid, s in stickers:
        P.add_suit(c.party, cid, s)
    if mercs:
        c.m_box_opened = True
        c.coins = 20
        for m in mercs:
            c.hire(m)
    g = c.start_attempt(seed=seed)
    return c, g


def enemy_by_suit(g, suit, rank=None, hp=None):
    """Make the castle card with this suit (and rank) the current enemy."""
    for cid in [g.enemy.card_id] + list(g.castle):
        card = g.cards[cid]
        if suit in card.suits and (rank is None or card.rank == rank):
            set_mission_enemy(g, cid, hp=hp)
            return cid
    raise RuntimeError("no such enemy")


def ids_everywhere(g):
    ids = g.all_card_ids()
    assert len(ids) == len(set(ids)) == len(g.cards), (len(ids), len(set(ids)), len(g.cards))


def round_trip(g):
    return Game.from_dict(json.loads(json.dumps(g.to_dict())))


# ---------------------------------------------------------------- 1 / 7: Gøran is never corrupted
def test_findings_1_7_goran_with_class_stickers_is_never_a_corruption_candidate():
    c = CampaignState.new(1, ["Ana"], seed=1)
    P.add_card(c.party, dict(M.GORAN))
    for s in ("C", "S", "H", "D"):
        P.add_suit(c.party, "GOR8", s)
    assert P.find(c.party, "GOR8")["suits"] == ["C", "S", "H", "D"]
    cands = P.corruption_candidates(c.party)
    assert "GOR8" not in cands and "8C" in cands
    rng = random.Random(7)
    assert all(P.pick_corruption_target(c.party, rng) != "GOR8" for _ in range(3000))
    # the real reward chain of missions 5 to 8 never picks him either
    for seed in range(60):
        c = CampaignState.new(1, ["Ana"], seed=seed)
        c.mission, c.completed = 5, [1, 2, 3, 4]
        P.add_card(c.party, dict(M.GORAN))
        rng = random.Random(seed)
        for number in (5, 6, 7, 8):
            c.mission = number
            for step in M.reward_steps(c, number, rng):
                if not step["kind"].startswith("choice"):
                    M.apply_step(c, step, rng)
        assert "corrupted" not in P.find(c.party, "GOR8")["flags"] and "GOR8" not in c.corrupted


# ---------------------------------------------------------------- 2: one card at a time (p.18)
def test_finding_2_legacy_damage_is_paid_one_card_at_a_time_with_the_last_on_top():
    c, g = mission(4, seed=460)
    set_mission_enemy(g, "LABJD")                       # a Phase I bard, strength 10
    set_hand(g, ["AS", "2D", "9C", "10C", "3H"])
    g.yield_turn() if g.can_yield() else None
    g.phase, g.pending_damage = PHASE_SUFFER, 10
    assert g.rules.sequential_discard(g)
    for bad in (["AS", "2D", "9C", "10C"], ["10C", "AS"], ["9C", "2D", "10C"]):
        with pytest.raises(IllegalAction):
            g.suffer(bad)                               # the damage is covered before the last card
    copy_g = round_trip(g)
    copy_g.suffer(["AS", "10C"])                        # 1 < 10, then 11: legal, the 10 ends on top
    assert copy_g.discard[0] == "10C"
    g.suffer(["9C", "10C"])                             # 9 < 10, then 19: legal
    assert g.discard[:2] == ["10C", "9C"] and g.players[0].hand == ["AS", "2D", "3H"]
    # the base game keeps accepting surplus (the strict variant is unofficial)
    b = Game.new(GameConfig(players=1), seed=3)
    set_enemy(b, "J", "H")
    set_hand(b, ["9C", "10C", "AS"])
    b.phase, b.pending_damage = PHASE_SUFFER, 10
    assert not b.rules.sequential_discard(b)
    b.suffer(["10C", "AS"])
    assert b.phase != PHASE_SUFFER


def test_finding_2_bots_build_legal_payments_including_hands_over_twelve_cards():
    c, g = mission(4, seed=461)
    set_mission_enemy(g, "LABJD")
    g.phase = PHASE_SUFFER
    hands = [["9C", "10C", "AS", "2D"], ["5H", "5D", "4S", "AS", "2C"], ["10C", "10H", "10S", "9D"]]
    for hand in hands:
        for need in range(1, 31):
            set_hand(g, hand)
            g.pending_damage = need
            if g.hand_defence_value() < need:
                continue
            pay = min_waste_discard(g)
            assert sequential_payment_ok(g, pay), (hand, need, pay)
            assert [g.cards[x].defence_value for x in pay] == sorted(g.cards[x].defence_value for x in pay)
    # a big hand (13 cards: Chanter draws ignore the limit) goes through the greedy branch
    big = ["AS", "2S", "3S", "4S", "5S", "6S", "7S", "8S", "9S", "10S", "2H", "3H", "4H"]
    for need in range(1, 60):
        set_hand(g, big)
        g.pending_damage = need
        pay = min_waste_discard(g)
        assert sequential_payment_ok(g, pay), (need, pay)
        assert g.cards[pay[-1]].defence_value == max(g.cards[x].defence_value for x in pay)
        total = sum(g.cards[x].defence_value for x in pay)
        assert all(total - g.cards[x].defence_value < need for x in pay)   # no card is surplus
    # and the bots' payments are accepted by the engine in every mission
    for number in (3, 4, 5, 6):
        c, g = mission(number, seed=470 + number)
        play_out(g, greedy_policy, random.Random(number))
        assert g.is_over


# ---------------------------------------------------------------- 3: a mage's unchosen cards, in any order
def _m4_mage(seed=462):
    c, g = mission(4, seed=seed)
    set_mission_enemy(g, "LABJD")                       # Phase I bard: 10 + the top discard
    set_discard(g, ["2S"])
    set_hand(g, ["3M", "9S", "8S", "AS"])
    set_tavern_top(g, ["4C", "10H", "2D"])
    return c, g


def test_finding_3_mission4_mage_player_chooses_which_unchosen_card_ends_on_top():
    c, g = _m4_mage()
    g.play(["3M"])
    g.decide({"type": "mage_pick", "card": "4C"})
    d = g.decision
    assert d["kind"] == "discard_top" and d["options"] == ["10H", "2D"] and d["revealed"] == ["10H", "2D"]
    assert [a["label"] for a in g.legal_actions()] == ["Put 10♥ on top of the discard pile",
                                                       "Put 2♦ on top of the discard pile"]
    ids_everywhere(g)                                   # the two cards are counted while the choice waits
    g2 = round_trip(g)
    assert g2.decision == g.decision
    with pytest.raises(IllegalAction):
        g.decide({"type": "discard_top", "card": "4C"})
    g.decide({"type": "discard_top", "card": "2D"})
    assert g.discard[:3] == ["2D", "10H", "2S"] and g.pending_damage == 12 and g.phase == PHASE_SUFFER
    g2.decide({"type": "discard_top", "card": "10H"})
    assert g2.discard[0] == "10H" and g2.phase == PHASE_LOST    # 20 damage: the hand cannot pay
    # the bot puts the weakest on top in mission 4
    c, g = _m4_mage(seed=463)
    g.play(["3M"])
    g.decide({"type": "mage_pick", "card": "4C"})
    assert simple_decision(g)["card"] == "2D" and greedy_policy(g)["card"] == "2D"
    # where the top of the discard pile does not matter, nothing is asked: reveal order
    c, g = mission(8, seed=50)
    assert not g.rules.discard_top_matters(g)
    g.enemy.hp = g.enemy.max_hp = 100
    set_hand(g, ["3M", "9S"])
    set_tavern_top(g, ["4C", "10H", "2D"])
    g.play(["3M"])
    g.decide({"type": "mage_pick", "card": "4C"})
    assert g.decision is None and g.discard[:2] == ["2D", "10H"]


def test_finding_3_mage_skip_and_azure_emblem_keep_then_choose_the_top():
    # nothing eligible (a Jester and corrupted cards): all revealed go, the player picks the top
    c, g = mission(4, players=1, seed=464, corrupted=("4C", "2D"), relics=("emblem",))
    set_mission_enemy(g, "LABJD", hp=100)
    set_hand(g, ["3M", "9S", "8S"])
    set_tavern_top(g, ["4C", "2D", "7S"])
    g.play(["3M"])
    assert g.decision["kind"] == "mage_peek"
    g.decide({"type": "mage_pick", "card": "7S"})
    # the Emblem (solo) comes first: keep one on the reserve, then the rest's order
    assert g.decision["kind"] == "emblem_keep"
    g.decide({"type": "emblem_skip"})
    assert g.decision["kind"] == "discard_top" and g.decision["options"] == ["4C", "2D"]
    g.decide({"type": "discard_top", "card": "4C"})
    assert g.discard[0] == "4C" and g.decision is None
    ids_everywhere(g)


# ---------------------------------------------------------------- 4: the reaver's banish order
def _m5(seed=471, **kw):
    kw.setdefault("relics", ())
    c, g = mission(5, seed=seed, **kw)
    return c, g


def test_finding_4_mission5_reaver_player_chooses_the_top_banished_card():
    c, g = _m5()
    set_mission_enemy(g, "GRJH", hp=40)                 # the Sporeling cleric, 10 / 40
    g.mission_zone = []
    set_hand(g, ["5R", "9S", "8S", "7S"])
    set_tavern_top(g, ["10C", "2D", "3D"])
    g.play(["5R"])
    g.decide({"type": "reaver_count", "count": 3})
    g.decide({"type": "reaver_pick", "card": "10C"})
    d = g.decision
    assert d["kind"] == "banish_top" and d["source"] == "reaver" and d["options"] == ["10C", "2D", "3D"]
    assert [a["label"] for a in g.legal_actions()][0] == "Put 10♣ on top of the banished pile"
    ids_everywhere(g)
    g = round_trip(g)
    g.decide({"type": "banish_top", "card": "2D"})
    assert g.banished[-3:] == ["10C", "3D", "2D"] and g.enemy.hp == 40 - 30   # (5 + 10) doubled
    assert any(ev["t"] == "reaver_pick" and ev["card"] == "10C" for ev in g.last_events)
    assert g.phase == PHASE_SUFFER
    g.suffer(min_waste_discard(g))
    # the end of turn moves the top banished card into the zone: 2, not 10
    assert g.mission_zone == ["2D"] and g.enemy_attack == 12
    # mission 1 (the top does not matter): the chosen card goes last, no question
    c = CampaignState.new(1, ["Ana"], seed=4)
    for r in M.REAVERS:
        P.add_card(c.party, dict(r))
    g = c.start_attempt(seed=4)
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["5R", "9S"])
    set_tavern_top(g, ["10C", "2D"])
    g.play(["5R"])
    g.decide({"type": "reaver_count", "count": 2})
    g.decide({"type": "reaver_pick", "card": "10C"})
    assert g.decision is None and g.banished == ["2D", "10C"]


def test_finding_4_bot_leaves_the_weakest_card_on_top_of_the_banished_pile():
    c, g = _m5(seed=472)
    set_mission_enemy(g, "GRJH", hp=100)
    set_hand(g, ["5R", "9S", "8S"])
    set_tavern_top(g, ["10C", "2D", "3D"])
    g.play(["5R"])
    g.decide({"type": "reaver_count", "count": 3})
    g.decide({"type": "reaver_pick", "card": "10C"})
    assert greedy_policy(g)["card"] == "2D"


# ---------------------------------------------------------------- 5: mission 5, a mage attack's banish order
def test_finding_5_mission5_mage_attack_is_banished_in_the_players_order():
    c, g = _m5(seed=473)
    set_mission_enemy(g, "GRJH", hp=40)
    set_hand(g, ["AS", "9M", "8S", "7S", "2H"])
    set_tavern_top(g, ["10C"])
    g.play(["AS", "9M"])
    g.decide({"type": "mage_pick", "card": "10C"})      # 1 + 9 + 10 = 20, doubled: 40, exact
    d = g.decision
    assert d["kind"] == "banish_top" and d["source"] == "cleanup" and d["options"] == ["AS", "9M", "10C"]
    assert d["resume"] == "defeat" and d["exact"] is True and g.enemies_defeated == 0
    assert [a["label"] for a in g.legal_actions()][0] == "Put A♠ on top of the banished pile"
    ids_everywhere(g)
    other = round_trip(g)
    g.decide({"type": "banish_top", "card": "AS"})
    assert g.enemies_defeated >= 1 and g.banished[-1] == "AS" and set(g.banished[-3:]) == {"AS", "9M", "10C"}
    assert "banish_choice" not in g.extra
    ids_everywhere(g)
    other.decide({"type": "banish_top", "card": "10C"})
    assert other.banished[-1] == "10C"
    # the same player's next turn does not kill: the end of turn moves the ace, not the 10
    if g.phase == PHASE_PLAY and g.enemy is not None:
        g.enemy.hp = 50
        set_hand(g, ["2H", "8S", "7S", "9S"])
        g.play(["2H"])
        if g.phase == PHASE_SUFFER:
            g.suffer(min_waste_discard(g))
        assert g.mission_zone[-1] == "AS"
    # the bot leaves the weakest on top
    c, g = _m5(seed=474)
    set_mission_enemy(g, "GRJH", hp=40)
    set_hand(g, ["AS", "9M", "8S"])
    set_tavern_top(g, ["10C"])
    g.play(["AS", "9M"])
    g.decide({"type": "mage_pick", "card": "10C"})
    assert greedy_policy(g)["card"] == "AS"


# ---------------------------------------------------------------- 6: the clean-up order wherever the top matters
def test_finding_6_solo_whistle_cleanup_order_is_asked_and_the_whistle_offers_the_chosen_card():
    c, g = mission(6, seed=482, relics=("whistle",))
    set_mission_enemy(g, "GDQH", hp=10)                 # a Guardian Statue
    set_hand(g, ["2C", "3C", "4C", "5C", "8S"])
    set_discard(g, ["7D"])
    g.play(["2C"])                                      # 2 doubled: 4, the statue survives
    g.suffer(min_waste_discard(g))
    set_hand(g, ["AS", "9C", "8S", "5C", "6C"])
    g.play(["AS", "9C"])                                # 10 doubled: 20, a kill
    g.decide({"type": "zone_move", "card": "2C"})
    while g.decision is not None and g.decision["kind"] == "team_discard":
        g.decide(greedy_policy(g))
    # two played cards go to the discard pile and the solo Whistle reads its top: asked
    assert g.decision["kind"] == "cleanup_top" and g.decision["options"] == ["AS", "9C"]
    assert greedy_policy(g)["card"] == "9C"             # the Whistle wants the strongest on top
    ids_everywhere(g)
    g = round_trip(g)
    g.decide({"type": "cleanup_top", "card": "AS"})
    assert g.discard[0] == "AS" and g.decision is None and g.enemies_defeated == 1
    ids_everywhere(g)
    # the next solitary companion's Whistle offers the chosen card
    set_hand(g, ["AH", "8S", "7S"])
    g.play(["AH"])
    assert g.decision["kind"] == "whistle_take" and g.decision["card"] == "AS"


def test_finding_6_mission11_two_players_choose_the_top_of_the_discard_pile():
    c, g = mission(11, players=2, seed=1100, corrupted=("2S", "3H", "4D", "5C", "6H", "7S", "8H", "9D"))
    while g.decision is not None:                       # the first turn's beast
        g.decide(g.legal_actions()[0])
    g.tavern.extend(g.banished)
    g.banished = []
    set_hand(g, ["5S", "5C", "9H"], player=0)
    set_discard(g, ["7D"])
    g.enemy.hp = 20
    g.play(["5S", "5C"])                                # 10, doubled: 20, exact
    assert g.decision["kind"] == "cleanup_top" and g.decision["options"] == ["5S", "5C"]
    assert g.rules.discard_top_feeds_enemy(g) and g.rules.banished_top_matters(g)
    g.decide({"type": "cleanup_top", "card": "5S"})
    assert g.discard[0] == "5S" and "S" in g.rules.immune_suits(g) and "C" not in g.rules.immune_suits(g)


def test_finding_6_nothing_is_asked_where_the_top_does_not_matter():
    c, g = mission(1, players=2, seed=11)
    set_enemy(g, "J", "H", hp=10)
    set_hand(g, ["5S", "5C", "9H"], player=0)
    g.play(["5S", "5C"])
    assert g.decision is None and g.enemies_defeated == 1 and g.discard[0] == "5C"   # play order, the last on top
    for number in (2, 3, 7, 8, 9):
        assert not mission(number, seed=12)[1].rules.discard_top_matters(mission(number, seed=12)[1])


def test_finding_6_evergreen_flags_follow_the_banes_and_locations():
    def rules_for(location, banes, players=1, relics=()):
        c = CampaignState.new(players, ["Ana", "Ben"][:players], seed=5)
        c.mission, c.completed, c.finished = 12, list(range(1, 13)), True
        c.relics.extend(relics)
        c.evergreen["setup"] = {"location": location, "banes": list(banes), "boons": []}
        g = c.start_evergreen_attempt(seed=5)
        return g.rules, g
    for banes, want in (((10,), True), ((17,), True), ((19,), True), ((16,), False), ((1, 2), False)):
        r, g = rules_for("A", banes, players=2)
        assert r.discard_top_matters(g) is want, banes
    for location, banes, want in (("C", (), True), ("D", (), True), ("A", (18,), True), ("B", (20,), True),
                                  ("A", (), False), ("E", (), False)):
        r, g = rules_for(location, banes, players=2)
        assert r.banished_top_matters(g) is want, (location, banes)
    r, g = rules_for("A", (), players=1, relics=("whistle",))
    assert r.discard_top_matters(g) and not r.discard_top_feeds_enemy(g)


# ---------------------------------------------------------------- 8 / 16: the flute takes named 2 to 5s
def test_findings_8_16_flute_stores_named_cards_but_never_a_locked_pilgrim():
    c, g = mission(5, seed=7, relics=("flute",), extra_cards=[by_id("merc_25H")["card"]])
    set_mission_enemy(g, "GRJH", hp=40)
    set_hand(g, ["3R", "3H", "M25H", "2C"])
    stores = sorted(a["card"] for a in g.legal_actions() if a.get("name") == "flute_store")
    assert stores == ["2C", "3H", "3R", "M25H", "M25H"]          # the 2/5 goes on as a 2 or as a 5
    c, g = mission(7, seed=31, relics=("flute",))
    pilgrim = [x for x in g.cards if g.cards[x].has("pilgrim") and g.rules.strength(g.cards[x]) in (2, 3, 4, 5)][0]
    _pull(g, pilgrim)
    g.players[0].hand = [pilgrim, "3U", "3H"]
    stores = sorted(a["card"] for a in g.legal_actions() if a.get("name") == "flute_store")
    assert pilgrim not in stores and "3U" in stores and "3H" in stores


# ---------------------------------------------------------------- 10: bane 2's order
def test_finding_10_bane2_puts_the_reserves_top_card_on_top_of_the_discard_pile():
    c = CampaignState.new(1, ["Ana"], seed=5000)
    c.mission, c.completed, c.finished = 12, list(range(1, 13)), True
    c.evergreen["setup"] = {"location": "A", "banes": [], "boons": []}
    plain = c.start_evergreen_attempt(seed=5000)
    c2 = CampaignState.new(1, ["Ana"], seed=5000)
    c2.mission, c2.completed, c2.finished = 12, list(range(1, 13)), True
    c2.evergreen["setup"] = {"location": "A", "banes": [2], "boons": []}
    g = c2.start_evergreen_attempt(seed=5000)
    # the same shuffle: rebuild the shuffled reserve (the plain game's hand came off its top);
    # bane 2 moved its first 30 cards, the reserve's top card ending on top of the pile
    full = list(plain.players[0].hand) + plain.tavern
    assert len(g.discard) == 30 and g.discard[0] == full[0]
    assert g.discard == full[:30]
    assert g.players[0].hand == full[30:30 + len(plain.players[0].hand)]


# ---------------------------------------------------------------- 11: the solo Jester attack is a Jester attack
def test_finding_11_solo_jester_paladin_keeps_its_shield_against_a_paladin_immune_enemy():
    c, g = mission(1, seed=11)
    enemy_by_suit(g, "S", "J")                          # Paladin Justicar, 10 / 20, immune to paladins
    g.use_solo_jester({"suit": "S"})
    assert g.plays[-1].jester and g.shield == 8 and g.pending_damage == 2 and g.enemy.hp == 12
    g.suffer(min_waste_discard(g))
    assert g.shield == 8 and g.enemy_attack == 2        # and for the rest of the fight
    g2 = round_trip(g)
    assert g2.plays[-1].jester and g2.shield == 8


# ---------------------------------------------------------------- 12: a claimer who yields
def test_finding_12_a_yielding_jester_claimer_does_not_pass_on_ignores_immunity():
    c, g = mission(1, players=3, seed=5)
    enemy_by_suit(g, "S", "J")
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_hand(g, [jester, "2H"], 0)
    set_hand(g, ["5H", "5D"], 1)
    set_hand(g, ["7S", "2D"], 2)
    g.active = 0
    g.play([jester])
    g.choose_next(1)
    assert g.extra.get("jester_attack") and g.can_yield()
    g.yield_turn()
    assert "jester_attack" not in g.extra
    g.suffer(["5H", "5D"])
    assert g.active == 2
    g.play(["7S"])
    assert not g.plays[-1].jester and g.shield == 0 and g.pending_damage == 10


# ---------------------------------------------------------------- 13 / 19: the flute while suffering
def test_findings_13_19_flute_store_never_leaves_the_damage_unpayable():
    c, g = mission(1, seed=3, relics=("flute",))
    enemy_by_suit(g, "H", "J")                          # Cleric Justicar, strength 10
    set_hand(g, ["6C", "3C", "8S"])
    g.play(["6C"])
    assert g.phase == PHASE_SUFFER and g.pending_damage == 10 and g.hand_defence_value() == 11
    assert not [a for a in g.legal_actions() if a.get("name") == "flute_store"]   # 8 would be left
    c, g = mission(1, seed=4, relics=("flute",))
    enemy_by_suit(g, "H", "J")
    set_hand(g, ["6C", "2C", "5H", "5D"])
    g.play(["6C"])
    stores = [a for a in g.legal_actions() if a.get("name") == "flute_store"]
    assert [a["card"] for a in stores] == ["2C"]        # 10 left: still payable
    g.special(stores[0])
    assert g.phase == PHASE_SUFFER and g.extra["flute"] == ["2C"]
    ids_everywhere(g)
    # a store that does leave the hand short (forced here) ends the game at once
    c, g = mission(1, seed=5, relics=("flute",))
    enemy_by_suit(g, "H", "J")
    set_hand(g, ["6C", "3C", "8S"])
    g.play(["6C"])
    g.players[0].hand.remove("3C")
    g.extra["flute"].append("3C")
    g._check_can_suffer()
    assert g.phase == PHASE_LOST


# ---------------------------------------------------------------- 14: mission 6, a solo Jester kill
def test_finding_14_mission6_solo_jester_kill_still_brings_the_rescue_and_mylas_team_damage():
    c, g = mission(6, seed=93)
    enemy_by_suit(g, "H", "Q", hp=8)
    set_hand(g, ["2C", "3C", "4C", "5C"])
    assert g.mission_zone == ["MYLA7"]
    g.use_solo_jester({"suit": "S"})                    # 8, exact (a paladin draws nothing)
    assert g.decision["kind"] == "team_discard" and g.decision["damage"] == 7 and g.decision["resume"] == "defeat"
    assert g.enemies_defeated == 0 and g.set_aside == []
    ids_everywhere(g)
    g2 = round_trip(g)
    while g.decision is not None:
        g.decide(greedy_policy(g))
    assert g.enemies_defeated == 1 and g.set_aside == ["X1"] and g.mission_zone == ["MYLA7"]
    assert sum(g.cards[x].value for x in g.discard if x in ("2C", "3C", "4C", "5C")) >= 7
    ids_everywhere(g)
    # with another zone card the exact kill rescues it first
    c, g = mission(6, seed=94)
    enemy_by_suit(g, "H", "Q", hp=8)
    _pull(g, "9D")
    g.mission_zone.append("9D")
    set_hand(g, ["2C", "3C", "4C", "5C", "8S"])
    g.use_solo_jester({"suit": "S"})
    assert g.decision["kind"] == "zone_rescue" and g.decision["options"] == ["9D"]
    g.decide({"type": "zone_rescue", "card": "9D"})
    assert g.decision["kind"] == "team_discard" and g.decision["damage"] == 7 and g.discard[0] == "9D"
    # too little in hand: the mission is lost
    c, g = mission(6, seed=95)
    enemy_by_suit(g, "H", "Q", hp=8)
    set_hand(g, ["2C", "3C"])
    g.use_solo_jester({"suit": "S"})
    assert g.phase == PHASE_LOST and "Myla" in g.loss_reason
    # a non-exact kill: no rescue, the team damage all the same
    c, g = mission(6, seed=96)
    enemy_by_suit(g, "H", "Q", hp=5)
    _pull(g, "9D")
    g.mission_zone.append("9D")
    set_hand(g, ["2C", "3C", "4C", "5C", "8S", "9S"])
    g.use_solo_jester({"suit": "S"})
    assert g.decision["kind"] == "team_discard" and g.decision["damage"] == 16


# ---------------------------------------------------------------- 15: forecast-only options
def test_finding_15_decide_rejects_forecast_only_actions():
    c, g = mission(7, seed=31)
    enemy_by_suit(g, "H", "J", hp=20)
    set_hand(g, ["7U", "2C"])
    set_discard(g, ["5H", "6H", "8D", "9D", "10S", "4C"])
    g.play(["7U"])
    assert g.decision["kind"] == "druid_assign"
    with pytest.raises(IllegalAction):
        g.decide({"type": "druid_assign", "player": 0, "forecast": True})
    with pytest.raises(IllegalAction):
        g.decide({"type": "mage_skip", "player": 0, "skip": True, "forecast": True})
    assert g.decision["kind"] == "druid_assign" and g.discard == []
    # the forecast path itself still works on copies
    g2 = copy.deepcopy(g)
    assert g2.forecast_decision() and g2.decision is None


# ---------------------------------------------------------------- 17: declarations (rulebook p.25)
def _wild(seed=62, players=1, enemy=("H", "Q"), hp=None, mercs=("merc_ace_1", "merc_25C")):
    c, g = mission(9, players=players, seed=seed, mercs=mercs)
    enemy_by_suit(g, enemy[0], enemy[1], hp=hp)
    return c, g


def test_finding_17_wild_animal_declares_a_class_when_it_enters_play():
    c, g = _wild()
    assert g.cards["MA_1"].has("choosable") and g.rules.card_suits(g, g.cards["MA_1"]) == ()
    set_hand(g, ["MA_1", "4D", "9S", "8S"])
    hp = g.enemy.hp
    g.play(["MA_1", "4D"])
    d = g.decision
    assert d["kind"] == "declare_class" and d["card"] == "MA_1" and d["player"] == 0
    acts = g.legal_actions()
    assert [a["option"] for a in acts] == ["H", "D", "C", "S"] and [a["label"] for a in acts][3] == "♠ Paladin"
    assert g.enemy.hp == hp                             # nothing resolved yet
    ids_everywhere(g)
    g = round_trip(g)                                   # a save mid-declaration
    with pytest.raises(IllegalAction):
        g.decide({"type": "declare_class", "option": "M"})
    g.decide({"type": "declare_class", "option": "S"})
    play = g.plays[-1]
    assert play.suits == ("D", "S") and play.value == 5 and g.shield == 5 and g.extra["declared"] == {"MA_1": "S"}
    assert g.enemy.hp == hp - 5
    assert any(ev["t"] == "declare" and ev["suit"] == "S" for ev in g.last_events)
    assert g.rules.card_suits(g, g.cards["MA_1"]) == ("S",)


def test_finding_17_a_declared_class_matching_the_enemys_immunity_is_blocked():
    c, g = _wild(enemy=("C", "Q"), hp=30)                # immune to warriors
    set_hand(g, ["MA_1", "7H", "9S"])
    g.play(["MA_1", "7H"])
    g.decide({"type": "declare_class", "option": "C"})
    powers = dict((ev["suit"], ev) for ev in g.last_events if ev["t"] == "power")
    assert powers["C"]["immune"] and g.enemy.hp == 30 - 8


def test_finding_17_declarations_end_with_the_enemy_and_the_card_is_classless_again():
    c, g = _wild(enemy=("H", "Q"), hp=8)
    set_hand(g, ["MA_1", "7D", "9S"])
    g.play(["MA_1", "7D"])
    g.decide({"type": "declare_class", "option": "C"})  # 8 doubled: the queen falls
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    assert g.enemies_defeated == 1 and "declared" not in g.extra
    assert "MA_1" in g.discard and g.rules.card_suits(g, g.cards["MA_1"]) == ()
    # back in a hand later, it declares again (anew)
    set_hand(g, ["MA_1", "4D", "9S"])
    g.play(["MA_1", "4D"])
    assert g.decision["kind"] == "declare_class"


def test_finding_17_two_five_takes_its_sets_strength_and_declares_when_free():
    # (more in test_twofive.py: 2/5 + 5, two 2/5s asked once, companions, beasts, the flute)
    c, g = _wild(enemy=("H", "Q"), hp=30)
    set_hand(g, ["M25C", "2D", "2S", "9S"])
    g.play(["M25C", "2D"])                              # a kinfolk set of 2s: it counts 2, nothing asked
    assert g.decision is None and g.plays[-1].value == 4 and g.extra["declared_value"] == {"M25C": 2}
    c, g = _wild(enemy=("H", "Q"), hp=30)
    set_hand(g, ["M25C", "9S", "8S"])
    g.play(["M25C"])
    assert g.decision["kind"] == "declare_value" and [a["option"] for a in g.legal_actions()] == ["2", "5"]
    g2 = round_trip(g)
    g.decide({"type": "declare_value", "option": "5"})
    assert g.plays[-1].value == 5 and g.enemy.hp == 30 - 10 and g.extra["declared_value"] == {"M25C": 5}
    g2.decide({"type": "declare_value", "option": 2})
    assert g2.plays[-1].value == 2 and g2.enemy.hp == 30 - 4
    # its strength elsewhere is 2 again (a zone, a bonus), its defence 5
    assert g.rules.strength(g.cards["M25C"]) == 2 and g.cards["M25C"].defence_value == 5


def test_finding_17_bots_and_forecasts_declare():
    c, g = _wild(enemy=("H", "Q"), hp=30)
    set_hand(g, ["MA_1", "7D", "9S"])
    pv = g.preview_play(["MA_1", "7D"])                 # assumed a warrior: 8 doubled
    assert pv["ok"] and pv["decision_kind"] == "declare_class" and pv["damage"] == 16
    g.play(["MA_1", "7D"])
    assert greedy_policy(g)["option"] == "D"            # no kill with doubling; the hand is short
    c, g = _wild(enemy=("H", "Q"), hp=16)
    set_hand(g, ["MA_1", "7D", "9S"])
    g.play(["MA_1", "7D"])
    assert greedy_policy(g)["option"] == "C"            # doubling kills
    c, g = _wild(enemy=("C", "Q"), hp=16)
    set_hand(g, ["MA_1", "7D", "9S"])
    g.play(["MA_1", "7D"])
    assert greedy_policy(g)["option"] != "C"            # never a class the enemy is immune to
    # a 2/5: 5, unless 2 is an exact kill
    c, g = _wild(enemy=("H", "Q"), hp=30)
    set_hand(g, ["M25C", "9S"])
    assert g.preview_play(["M25C"])["damage"] == 10
    g.play(["M25C"])
    assert greedy_policy(g)["option"] == "5"
    c, g = _wild(enemy=("H", "Q"), hp=4)
    set_hand(g, ["M25C", "9S"])
    g.play(["M25C"])
    assert greedy_policy(g)["option"] == "2"            # 2 doubled is exactly 4


def test_finding_17_cards_added_mid_attack_declare_too():
    # the mage adds a Wild Animal: it declares before the attack goes on, and its class resolves
    c, g = _wild(enemy=("H", "Q"), hp=40)
    set_hand(g, ["5M", "9S", "8S"])
    _pull(g, "MA_1")
    set_tavern_top(g, ["MA_1", "2H", "3H", "4H", "6H"])
    g.play(["5M"])
    g.decide({"type": "mage_pick", "card": "MA_1"})
    assert g.decision["kind"] == "declare_class" and g.decision["resume_step"] == "mage_picked"
    ids_everywhere(g)
    g = round_trip(g)
    g.decide({"type": "declare_class", "option": "C"})
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    assert g.plays[-1].suits == ("C", "M") and g.enemy.hp == 40 - 12   # 6 doubled by the declared warrior
    # the solo Scarlet Whistle adds a 2/5 to a solitary beast: alone with the beast, it declares
    c, g = mission(9, seed=63, relics=("whistle",), beast="B_H", mercs=("merc_25C",))
    enemy_by_suit(g, "H", "Q", hp=40)
    set_hand(g, ["B_H", "9S", "8S"])
    set_discard(g, ["M25C"])
    g.play(["B_H"])
    assert g.decision["kind"] == "whistle_take"
    g.decide({"type": "whistle_take", "card": "M25C"})
    assert g.decision["kind"] == "declare_value"
    g.decide({"type": "declare_value", "option": "5"})
    assert g.plays[-1].value == 10 and g.enemy.hp == 40 - 20   # the beast copies the 5, the warrior doubles


def test_finding_17_random_games_with_wild_animals_and_two_fives_keep_their_cards():
    rng = random.Random(17)
    seen = set()
    for seed in range(12):
        c, g = mission(5 + seed % 4, players=1 + seed % 3, seed=1700 + seed,
                       mercs=("merc_ace_1", "merc_ace_2", "merc_25H", "merc_25C"))
        policy = greedy_policy if seed % 2 else random_policy
        while not g.is_over:
            act = policy(g, rng)
            if act.get("type") in ("declare_class", "declare_value"):
                seen.add(act["type"])
            apply_action(g, act)
            ids_everywhere(g)
    assert seen == {"declare_class", "declare_value"}


# ---------------------------------------------------------------- 18: the flute's cards are counted
def test_finding_18_all_card_ids_counts_the_flute():
    c, g = mission(1, seed=4, relics=("flute",))
    set_hand(g, ["2C", "5H", "9S"])
    g.special([a for a in g.legal_actions() if a.get("name") == "flute_store"][0])
    assert g.extra["flute"] == ["2C"] and "2C" in g.all_card_ids()
    assert sorted(g.all_card_ids()) == sorted(g.cards)


# ---------------------------------------------------------------- part 1's defeat pause keeps the solo Jester once
def test_cleanup_question_after_a_solo_jester_kill_sets_the_jester_aside_once():
    c, g = mission(4, seed=465)
    set_mission_enemy(g, "LABJD", hp=30)
    set_hand(g, ["9S", "8S", "AS", "7H"])
    g.play(["9S"])
    g.suffer(min_waste_discard(g)) if g.phase == PHASE_SUFFER else None
    g.enemy.hp = 8
    g.use_solo_jester({"suit": "H"})
    assert g.decision is None or g.decision["kind"] != "cleanup_top"   # the Jester is not cleaned up
    c, g = mission(4, seed=466)
    set_mission_enemy(g, "LABJD", hp=30)
    set_hand(g, ["9S", "8S", "AS", "7H", "6H"])
    g.play(["9S"])
    g.suffer(min_waste_discard(g)) if g.phase == PHASE_SUFFER else None
    g.play(["6H"])
    g.suffer(min_waste_discard(g)) if g.phase == PHASE_SUFFER else None
    g.enemy.hp = 8
    g.use_solo_jester({"suit": "H"})
    assert g.decision["kind"] == "cleanup_top" and sorted(g.decision["options"]) == ["6H", "9S"]
    g = round_trip(g)
    g.decide({"type": "cleanup_top", "card": "6H"})
    assert g.set_aside == ["X1"] and g.discard[0] == "6H"
    ids_everywhere(g)
