"""Regression tests for the adversarial review's findings (one test or more per finding;
the UI findings are in test_app.py), and at the end the playtest change to the order cards
go onto a pile (no clean-up question, "What order?" for the reveals)."""
import copy
import json
import random

import pytest

from helpers import keep_played_order, set_discard, set_enemy, set_hand, set_mission_enemy, set_tavern_top, _pull
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


# Games saved before the playtest change (the clean-up asked which played card ends on top,
# a mage's unchosen and a reaver's revealed cards asked for the top card only) must still
# resolve: ``old_cleanup_question`` is the clean-up question the rules asked then (patched
# onto a game's rules to pause it the old way), ``old_save`` saves a game paused on a new
# order question as the top-card question it replaced (the same fields) and reloads it.
def old_cleanup_question(game, exact, plan, discard_ids, banish_ids):
    if plan.get("played_to", "discard") != "discard":
        return None
    if (len(discard_ids) >= 2 and game.rules.discard_top_matters(game)
            and game.extra.get("cleanup_choice") not in discard_ids):
        return {"kind": "cleanup_top", "player": game.active, "options": list(discard_ids)}
    reaching = game.rules._reach_banished(game, banish_ids)
    if (len(reaching) >= 2 and game.rules.banished_top_matters(game)
            and game.extra.get("banish_choice") not in reaching):
        return {"kind": "banish_top", "player": game.active, "options": reaching, "source": "cleanup"}
    return None


def old_save(g):
    data = json.loads(json.dumps(g.to_dict()))
    d = data.get("decision") or {}
    if d.get("kind") == "discard_order":
        d["kind"] = "discard_top"
    elif d.get("kind") == "reaver_order":
        d["kind"] = "banish_top"
        d["source"] = "reaver"
    return Game.from_dict(data)


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


def test_finding_3_mission4_mage_player_names_the_order_of_the_unchosen_cards():
    c, g = _m4_mage()
    g.play(["3M"])
    g.decide({"type": "mage_pick", "card": "4C"})
    d = g.decision
    assert d["kind"] == "discard_order" and d["options"] == ["10H", "2D"] and d["revealed"] == ["10H", "2D"]
    acts = g.legal_actions()
    assert acts == [{"type": "discard_order", "player": 0, "pick_from": ["10H", "2D"], "needs": 2, "ordered": True,
                     "label": "Discard the revealed cards in this order (the last ends on top)"}]
    assert any(ev["t"] == "decide" and ev["kind"] == "discard_order" for ev in g.last_events)
    ids_everywhere(g)                                   # the two cards are counted while the choice waits
    g2 = round_trip(g)
    assert g2.decision == g.decision
    for bad in (["2D"], ["2D", "2D"], ["2D", "4C"], ["2D", "10H", "4C"], []):
        with pytest.raises(IllegalAction):
            g.decide({"type": "discard_order", "cards": bad})
    with pytest.raises(IllegalAction):
        g.decide({"type": "discard_top", "card": "2D"})     # the old question is not on offer
    # the first tapped goes first, the last ends on top
    g.decide({"type": "discard_order", "cards": ["10H", "2D"]})
    assert g.discard[:3] == ["2D", "10H", "2S"] and g.pending_damage == 12 and g.phase == PHASE_SUFFER
    assert [ev for ev in g.last_events if ev["t"] == "discard_order"] == [
        {"t": "discard_order", "player": 0, "cards": ["10H", "2D"]}]
    ids_everywhere(g)
    g2.decide({"type": "discard_order", "player": 0, "cards": ["2D", "10H"]})
    assert g2.discard[:3] == ["10H", "2D", "2S"] and g2.phase == PHASE_LOST    # 20 damage: the hand cannot pay
    # the bot names the weakest last (on top) in mission 4
    c, g = _m4_mage(seed=463)
    g.play(["3M"])
    g.decide({"type": "mage_pick", "card": "4C"})
    assert simple_decision(g)["cards"] == ["10H", "2D"] and greedy_policy(g)["cards"] == ["10H", "2D"]
    # where the top of the discard pile does not matter, nothing is asked: reveal order
    c, g = mission(8, seed=50)
    assert not g.rules.discard_top_matters(g)
    g.enemy.hp = g.enemy.max_hp = 100
    set_hand(g, ["3M", "9S"])
    set_tavern_top(g, ["4C", "10H", "2D"])
    g.play(["3M"])
    g.decide({"type": "mage_pick", "card": "4C"})
    assert g.decision is None and g.discard[:2] == ["2D", "10H"]


def test_finding_3_mage_skip_and_azure_emblem_keep_then_name_the_order():
    # nothing eligible (a Jester and corrupted cards): all revealed go, the player names the order
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
    assert g.decision["kind"] == "discard_order" and g.decision["options"] == ["4C", "2D"]
    g.decide({"type": "discard_order", "cards": ["2D", "4C"]})
    assert g.discard[:2] == ["4C", "2D"] and g.decision is None
    ids_everywhere(g)


# ---------------------------------------------------------------- 4: the reaver's banish order
def _m5(seed=471, **kw):
    kw.setdefault("relics", ())
    c, g = mission(5, seed=seed, **kw)
    return c, g


def test_finding_4_mission5_reaver_player_names_the_banish_order():
    c, g = _m5()
    set_mission_enemy(g, "GRJH", hp=40)                 # the Sporeling cleric, 10 / 40
    g.mission_zone = []
    set_hand(g, ["5R", "9S", "8S", "7S"])
    set_tavern_top(g, ["10C", "2D", "3D"])
    g.play(["5R"])
    g.decide({"type": "reaver_count", "count": 3})
    g.decide({"type": "reaver_pick", "card": "10C"})
    d = g.decision
    assert d["kind"] == "reaver_order" and d["reaver_card"] == "10C" and d["options"] == ["10C", "2D", "3D"]
    acts = g.legal_actions()
    assert len(acts) == 1 and acts[0]["pick_from"] == ["10C", "2D", "3D"] and acts[0]["needs"] == 3 and acts[0]["ordered"]
    assert acts[0]["label"] == "Banish the revealed cards in this order (the last ends on top)"
    ids_everywhere(g)
    g = round_trip(g)
    with pytest.raises(IllegalAction):
        g.decide({"type": "reaver_order", "cards": ["10C", "2D"]})
    g.decide({"type": "reaver_order", "cards": ["10C", "3D", "2D"]})
    assert g.banished[-3:] == ["10C", "3D", "2D"] and g.enemy.hp == 40 - 30   # (5 + 10) doubled
    assert any(ev["t"] == "reaver_pick" and ev["card"] == "10C" and ev["banished"] == ["10C", "3D", "2D"]
               for ev in g.last_events)
    kinds = [ev["t"] for ev in g.last_events]
    assert kinds.index("reaver_pick") < kinds.index("reaver_order")      # the pick, then the order it was banished in
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
    act = greedy_policy(g)
    assert act == {"type": "reaver_order", "player": 0, "cards": ["10C", "3D", "2D"]}   # the weakest last, on top
    apply_action(g, act)
    assert g.banished[-1] == "2D" and g.decision is None


# ---------------------------------------------------------------- 5: mission 5, a mage attack's banish order
def test_finding_5_mission5_mage_attack_is_banished_in_the_order_it_entered_play():
    c, g = _m5(seed=473)
    set_mission_enemy(g, "GRJH", hp=40)
    set_hand(g, ["AS", "9M", "8S", "7S", "2H"])
    set_tavern_top(g, ["10C"])
    g.play(["AS", "9M"])
    g.decide({"type": "mage_pick", "card": "10C"})      # 1 + 9 + 10 = 20, doubled: 40, exact
    # "in the order the current player chooses": "What order?", offered in the order the cards
    # entered play (the ace and the mage as selected, then the card the mage added); kept
    assert g.decision["kind"] == "played_banish_order" and g.enemies_defeated == 0
    assert keep_played_order(g) == [["AS", "9M", "10C"]]
    assert g.decision is None and g.enemies_defeated >= 1 and g.banished[-3:] == ["AS", "9M", "10C"]
    assert [ev for ev in g.last_events if ev["t"] == "cleanup_order"] == [
        {"t": "cleanup_order", "pile": "banished", "cards": ["AS", "9M", "10C"]}]
    assert "banish_choice" not in g.extra
    ids_everywhere(g)
    # the same player's next turn does not kill: the end of turn moves the 10, the last to enter play
    if g.phase == PHASE_PLAY and g.enemy is not None:
        g.enemy.hp = 50
        set_hand(g, ["2H", "8S", "7S", "9S"])
        g.play(["2H"])
        if g.phase == PHASE_SUFFER:
            g.suffer(min_waste_discard(g))
        assert g.mission_zone[-1] == "10C"
    # selected the other way round: the mage before the ace
    c, g = _m5(seed=474)
    set_mission_enemy(g, "GRJH", hp=40)
    set_hand(g, ["AS", "9M", "8S"])
    set_tavern_top(g, ["10C"])
    g.play(["9M", "AS"])
    g.decide({"type": "mage_pick", "card": "10C"})
    assert g.decision["options"] == ["9M", "AS", "10C"]
    with pytest.raises(IllegalAction):
        g.decide({"type": "played_banish_order", "cards": ["9M", "AS"]})     # every card, once
    g.decide({"type": "played_banish_order", "cards": ["AS", "10C", "9M"]})  # the player's own order
    assert g.decision is None and g.banished[-3:] == ["AS", "10C", "9M"] and "played_order" not in g.extra
    ids_everywhere(g)


# ---------------------------------------------------------------- 6: the clean-up order wherever the top matters
def test_finding_6_solo_whistle_cleanup_keeps_the_play_order_and_the_whistle_offers_the_last_card():
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
    # two played cards go to the discard pile and the solo Whistle reads its top: "What
    # order?"; kept as they entered play (2♣ went to the zone), 9♣ ends on top
    assert keep_played_order(g) == [["AS", "9C"]]
    assert g.decision is None and g.enemies_defeated == 1 and g.discard[:2] == ["9C", "AS"]
    assert any(ev["t"] == "cleanup_order" and ev["cards"] == ["AS", "9C"] for ev in g.last_events)
    ids_everywhere(g)
    # the next solitary companion's Whistle offers that card
    set_hand(g, ["AH", "8S", "7S"])
    g.play(["AH"])
    assert g.decision["kind"] == "whistle_take" and g.decision["card"] == "9C"


def test_finding_6_mission11_two_players_the_last_card_played_tops_the_discard_pile():
    c, g = mission(11, players=2, seed=1100, corrupted=("2S", "3H", "4D", "5C", "6H", "7S", "8H", "9D"))
    while g.decision is not None:                       # the first turn's beast
        g.decide(g.legal_actions()[0])
    g.tavern.extend(g.banished)
    g.banished = []
    set_hand(g, ["5S", "5C", "9H"], player=0)
    set_discard(g, ["7D"])
    g.enemy.hp = 20
    g.play(["5C", "5S"])                                # 10, doubled: 20, exact
    assert g.rules.discard_top_feeds_enemy(g) and g.rules.banished_top_matters(g)
    # "What order?" offers the selection order: kept, 5♠ (selected last) ends on top
    assert keep_played_order(g) == [["5C", "5S"]]
    assert g.decision is None and g.discard[:2] == ["5S", "5C"]
    assert "S" in g.rules.immune_suits(g) and "C" not in g.rules.immune_suits(g)


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
def _solo_jester_kill(seed, patch=None):
    """Mission 4, solo: 9♠ then 6♥ against one enemy, then a Jester attack kills it."""
    c, g = mission(4, seed=seed)
    set_mission_enemy(g, "LABJD", hp=30)
    set_hand(g, ["9S", "8S", "AS", "7H", "6H"])
    g.play(["9S"])
    g.suffer(min_waste_discard(g)) if g.phase == PHASE_SUFFER else None
    g.play(["6H"])
    g.suffer(min_waste_discard(g)) if g.phase == PHASE_SUFFER else None
    g.enemy.hp = 8
    if patch is not None:
        g.rules.before_cleanup = patch
    g.use_solo_jester({"suit": "H"})
    return g


def test_cleanup_after_a_solo_jester_kill_sets_the_jester_aside_once():
    c, g = mission(4, seed=465)
    set_mission_enemy(g, "LABJD", hp=30)
    set_hand(g, ["9S", "8S", "AS", "7H"])
    g.play(["9S"])
    g.suffer(min_waste_discard(g)) if g.phase == PHASE_SUFFER else None
    g.enemy.hp = 8
    g.use_solo_jester({"suit": "H"})
    assert g.decision is None and g.set_aside == ["X1"]    # the Jester is not cleaned up
    g = _solo_jester_kill(466)
    assert g.decision["options"] == ["9S", "6H"] and g.set_aside == [] and g.enemies_defeated == 0
    g = round_trip(g)                                   # saved on the question: the Jester is still out
    assert keep_played_order(g) == [["9S", "6H"]]
    assert g.decision is None and g.set_aside == ["X1"] and g.discard[:2] == ["6H", "9S"]   # play order
    ids_everywhere(g)
    # a game saved while the clean-up still asked which card ends on top resolves the old way
    g = old_save(_solo_jester_kill(466, patch=old_cleanup_question))
    assert g.decision["kind"] == "cleanup_top" and sorted(g.decision["options"]) == ["6H", "9S"]
    assert g.set_aside == [] and g.enemies_defeated == 0
    g.decide({"type": "cleanup_top", "card": "9S"})
    assert g.set_aside == ["X1"] and g.discard[:2] == ["9S", "6H"] and g.decision is None
    assert "cleanup_choice" not in g.extra
    ids_everywhere(g)


# ---------------------------------------------------------------- playtest: the order cards go onto a pile
# The owner's playtest: cards are numbered as they are selected and the order questions ask
# for the whole order ("What order?": the first named goes first, the last ends on top), only
# where the top of that pile matters; the clean-up after a kill offers the order the cards
# entered play (the last one on top), kept in one tap.
def _m11_quiet(seed=1100, players=1):
    """Mission 11 after the first turn's beast, with no more beasts and empty piles (so no
    immunity nor bonus from the pile tops yet)."""
    c, g = mission(11, players=players, seed=seed, corrupted=("2S", "3H", "4D", "5C", "6H", "7S", "8H", "9D"))
    while g.decision is not None:
        g.decide(g.legal_actions()[0])
    g.extra["beasts_out"] = g.extra["beast_deck"] + g.extra["beasts_out"]
    g.extra["beast_deck"] = []
    g.tavern.extend(g.banished + g.discard)
    g.banished, g.discard = [], []
    return c, g


def test_pile_order_mission11_cleanup_tops_both_piles_with_the_last_card_to_enter_play():
    c, g = _m11_quiet()
    enemy = g.enemy.card_id
    g.enemy.hp = 25
    set_hand(g, ["4C", "4S", "AM", "8S", "9S"])
    g.play(["4C", "4S"])                                # 8, doubled: 16; the shield 8
    assert g.enemy.hp == 9 and g.phase == PHASE_SUFFER and g.pending_damage == 2
    g.suffer(["8S"])                                    # 8♠ tops the discard pile
    assert g.rules.immune_suits(g) == ("S",) and g.rules.attack_bonus(g) == 8
    set_tavern_top(g, ["8C"])
    g.play(["AM"])                                      # the animal mage looks at one card
    g.decide({"type": "mage_pick", "card": "8C"})       # 1 + 8 = 9, doubled: 18, a kill
    # two plays against the enemy: the first one is discarded, 4♠ (selected last) on top; the
    # mage attack is banished after the enemy, the card the mage added (last in) on top
    assert keep_played_order(g) == [["4C", "4S"], ["AM", "8C"]]
    assert g.decision is None and g.enemies_defeated == 1 and g.phase == PHASE_PLAY
    assert g.discard[:3] == ["4S", "4C", "8S"] and g.banished[-3:] == [enemy, "AM", "8C"]
    assert [(ev["pile"], ev["cards"]) for ev in g.last_events if ev["t"] == "cleanup_order"] == [
        ("discard", ["4C", "4S"]), ("banished", ["AM", "8C"])]
    # the next enemy reads both tops: 4♠ and 8♣
    assert set(g.rules.immune_suits(g)) >= {"S", "C"} and g.rules.attack_bonus(g) == 4 + 8
    ids_everywhere(g)


def test_pile_order_kinfolk_flute_and_scarlet_whistle_additions_enter_play_last():
    # the Kinfolk Flute (two players): the added 4♠ entered play after the attacker's 4♣
    c, g = mission(4, players=2, seed=1401, relics=("flute",))
    set_mission_enemy(g, "LABJD", hp=12)
    set_discard(g, ["7D"])
    set_hand(g, ["4C", "9S"], player=0)
    set_hand(g, ["4S", "2H"], player=1)
    g.play(["4C"])
    assert g.decision["kind"] == "flute_add" and g.decision["player"] == 1
    g.flute_add(["4S"])                                 # 8, doubled: 16, a kill
    assert g.decision["player"] == 0 and keep_played_order(g) == [["4C", "4S"]]
    assert g.decision is None and g.enemies_defeated == 1 and g.discard[:3] == ["4S", "4C", "LABJD"]
    ids_everywhere(g)
    # the Scarlet Whistle (solo): the top discard taken into the attack goes back on top
    c, g = mission(4, seed=1402, relics=("whistle",))
    set_mission_enemy(g, "LABJD", hp=12)
    set_discard(g, ["9C", "2D"])
    set_hand(g, ["AS", "8S", "7S"])
    g.play(["AS"])
    assert g.decision["kind"] == "whistle_take" and g.decision["card"] == "9C"
    g.decide({"type": "whistle_take", "card": "9C"})    # 1 + 9 = 10, doubled: 20, a kill
    assert keep_played_order(g) == [["AS", "9C"]]
    assert g.decision is None and g.enemies_defeated == 1 and g.discard[:4] == ["9C", "AS", "LABJD", "2D"]
    ids_everywhere(g)


def test_pile_order_discard_low_to_high_still_puts_the_lowest_on_top():
    c, g = mission(4, seed=1403)
    g.config.extra["discard_low_to_high"] = True
    set_mission_enemy(g, "LABJD", hp=10)
    set_discard(g, ["7D"])
    set_hand(g, ["AS", "9C", "3D"])
    g.play(["AS", "9C"])                                # play order would put 9♣ on top
    assert g.decision is None and g.discard[:3] == ["AS", "9C", "LABJD"]
    assert [ev["cards"] for ev in g.last_events if ev["t"] == "cleanup_order"] == [["9C", "AS"]]
    g = round_trip(g)
    assert g.config.extra["discard_low_to_high"]


def test_pile_order_questions_only_when_two_or_more_cards_go_and_the_top_matters():
    # a mage's single unchosen card: nothing to order
    c, g = mission(4, seed=1404)
    set_mission_enemy(g, "LABJD", hp=100)
    set_hand(g, ["2M", "9S", "8S", "10S"])
    set_tavern_top(g, ["4C", "10H"])
    g.play(["2M"])
    g.decide({"type": "mage_pick", "card": "4C"})
    assert g.decision is None and g.discard[0] == "10H" and g.phase == PHASE_SUFFER
    # a reaver revealing one card: nothing to order
    c, g = mission(5, seed=1405)
    set_mission_enemy(g, "GRJH", hp=100)
    set_hand(g, ["5R", "9S", "8S"])
    set_tavern_top(g, ["10C", "2D"])
    g.play(["5R"])
    g.decide({"type": "reaver_count", "count": 1})
    g.decide({"type": "reaver_pick", "card": "10C"})
    assert g.decision is None and g.banished[-1] == "10C" and g.tavern[0] == "2D"
    # solo with the Scarlet Whistle only the Whistle reads the discard pile: asked, and the
    # bot names the strongest last (on top) for the next solitary companion
    c, g = mission(1, seed=1406, relics=("whistle",), extra_cards=M.MAGE_DECK)
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["3M", "9S"])
    set_tavern_top(g, ["4C", "10H", "2D"])
    g.play(["3M"])
    g.decide({"type": "mage_pick", "card": "4C"})
    assert g.decision["kind"] == "discard_order" and g.decision["options"] == ["10H", "2D"]
    assert not g.rules.discard_top_feeds_enemy(g) and simple_decision(g)["cards"] == ["2D", "10H"]
    texts = [line for line in g.log[-3:] if "chooses the order" in line]
    assert texts and "10♥ / 2♦" in texts[0]


def test_pile_order_games_saved_on_the_old_top_card_questions_still_resolve():
    # a mage's unchosen cards (``discard_top``)
    c, g = _m4_mage()
    g.play(["3M"])
    g.decide({"type": "mage_pick", "card": "4C"})
    old = old_save(g)
    assert old.decision["kind"] == "discard_top" and [a["label"] for a in old.legal_actions()] == [
        "Put 10♥ on top of the discard pile", "Put 2♦ on top of the discard pile"]
    assert simple_decision(old)["card"] == "2D"         # the bots still answer it
    old.decide({"type": "discard_top", "card": "2D"})
    assert old.discard[:3] == ["2D", "10H", "2S"] and old.pending_damage == 12 and old.phase == PHASE_SUFFER
    ids_everywhere(old)
    # a reaver's reveal (``banish_top`` from the reaver)
    c, g = _m5()
    set_mission_enemy(g, "GRJH", hp=40)
    g.mission_zone = []
    set_hand(g, ["5R", "9S", "8S", "7S"])
    set_tavern_top(g, ["10C", "2D", "3D"])
    g.play(["5R"])
    g.decide({"type": "reaver_count", "count": 3})
    g.decide({"type": "reaver_pick", "card": "10C"})
    old = old_save(g)
    assert old.decision["kind"] == "banish_top" and old.decision["source"] == "reaver"
    assert [a["label"] for a in old.legal_actions()][0] == "Put 10♣ on top of the banished pile"
    assert greedy_policy(old)["card"] == "2D"
    old.decide({"type": "banish_top", "card": "2D"})
    assert old.banished[-3:] == ["10C", "3D", "2D"] and old.enemy.hp == 40 - 30 and old.phase == PHASE_SUFFER
    ids_everywhere(old)
    # a mage attack's clean-up (``banish_top`` from the clean-up), paused the old way
    c, g = _m5(seed=473)
    set_mission_enemy(g, "GRJH", hp=40)
    set_hand(g, ["AS", "9M", "8S", "7S", "2H"])
    set_tavern_top(g, ["10C"])
    g.rules.before_cleanup = old_cleanup_question
    g.play(["AS", "9M"])
    g.decide({"type": "mage_pick", "card": "10C"})      # 40: exact
    old = round_trip(g)
    d = old.decision
    assert d["kind"] == "banish_top" and d["source"] == "cleanup" and d["options"] == ["AS", "9M", "10C"]
    assert d["resume"] == "defeat" and d["exact"] is True and old.enemies_defeated == 0
    ids_everywhere(old)
    old.decide({"type": "banish_top", "card": "AS"})
    assert old.decision is None and old.enemies_defeated >= 1 and old.banished[-1] == "AS"
    assert set(old.banished[-3:]) == {"AS", "9M", "10C"} and "banish_choice" not in old.extra
    ids_everywhere(old)
    # the played cards' clean-up (``cleanup_top``), mission 4
    c, g = mission(4, seed=1407)
    set_mission_enemy(g, "LABJD", hp=10)
    set_discard(g, ["7D"])
    set_hand(g, ["AS", "9C", "3D"])
    g.rules.before_cleanup = old_cleanup_question
    g.play(["AS", "9C"])
    old = round_trip(g)
    assert old.decision["kind"] == "cleanup_top" and old.decision["options"] == ["AS", "9C"]
    assert greedy_policy(old)["card"] == "AS"          # the weakest on top in mission 4
    old.decide({"type": "cleanup_top", "card": "AS"})
    assert old.decision is None and old.discard == ["AS", "9C", "LABJD", "7D"] and "cleanup_choice" not in old.extra
    ids_everywhere(old)


def test_pile_order_forecasts_run_through_the_order_questions():
    # a mage pick that leaves two cards to order: the forecast assumes the revealed order
    c, g = _m4_mage()
    g.play(["3M"])
    before = copy.deepcopy(g.to_dict())
    pv = g.preview_decision({"type": "mage_pick", "card": "4C"})
    assert pv["ok"] and pv["decision"] and pv["decision_kind"] == "discard_order"
    assert pv["damage"] == 14 and pv["enemy_attack_after"] == 10 + 2 and pv["phase_after"] == PHASE_SUFFER
    assert g.to_dict() == before
    # a reaver's three revealed cards: the forecast banishes the chosen one last
    c, g = _m5()
    set_mission_enemy(g, "GRJH", hp=40)
    g.mission_zone = []
    set_hand(g, ["5R", "9S", "8S", "7S"])
    set_tavern_top(g, ["10C", "2D", "3D"])
    g.play(["5R"])
    g.decide({"type": "reaver_count", "count": 3})
    pv = g.preview_decision({"type": "reaver_pick", "card": "10C"})
    assert pv["ok"] and pv["decision_kind"] == "reaver_order" and pv["damage"] == 30 and pv["enemy_hp_after"] == 10
    assert g.decision["kind"] == "reaver_pick"
    g.decide({"type": "reaver_pick", "card": "10C"})
    sim = copy.deepcopy(g)
    assert sim.forecast_decision() and sim.decision is None and sim.banished[-3:] == ["2D", "3D", "10C"]
    with pytest.raises(IllegalAction):
        g.decide(dict(g.rules.forecast_action(g)))          # a forecast's option is not the player's


def test_pile_order_bots_and_random_games_answer_the_order_questions_and_keep_every_card():
    kinds = set()
    for number in (4, 5, 11):
        for players in (1, 2):
            for seed in range(4):
                c, g = mission(number, players=players, seed=900 + seed,
                               extra_cards=M.REAVERS if number != 5 else (),
                               corrupted=("2S", "3H", "4D", "5C", "6H", "7S", "8H", "9D") if number == 11 else (),
                               relics=("whistle",) if seed % 2 else ())
                rng = random.Random(seed)
                policy = greedy_policy if seed % 2 == 0 else random_policy
                steps = 0
                while not g.is_over and steps < 4000:
                    if g.decision:
                        kinds.add(g.decision["kind"])
                    apply_action(g, policy(g, rng))
                    steps += 1
                assert g.is_over and g.decision is None
                ids_everywhere(g)
                assert all(len(p.hand) <= g.config.max_hand for p in g.players)
    assert {"discard_order", "reaver_order", "played_discard_order"} <= kinds, kinds
    assert not kinds & {"cleanup_top", "banish_top", "discard_top"}


def test_pile_order_cleanup_question_bots_stale_answers_and_the_restored_relic():
    # mission 4: the bots name the weakest card last (it feeds the next enemy)
    c, g = mission(4, seed=1408)
    set_mission_enemy(g, "LABJD", hp=10)
    set_discard(g, ["7D"])
    set_hand(g, ["AS", "9C", "3D"])
    g.extra["played_order"] = {"enemy": "LABQD", "discard": ["9C", "AS"]}   # left over from another enemy
    g.play(["AS", "9C"])
    d = g.decision
    assert d["kind"] == "played_discard_order" and d["options"] == ["AS", "9C"] and d["player"] == 0
    assert [a["label"] for a in g.legal_actions()] == [
        "Put the played cards on the discard pile in this order (the last ends on top)"]
    act = greedy_policy(g)
    assert act == {"type": "played_discard_order", "player": 0, "cards": ["9C", "AS"]}
    apply_action(g, act)
    assert g.decision is None and g.discard[:3] == ["AS", "9C", "LABJD"] and "played_order" not in g.extra
    assert [ev["cards"] for ev in g.last_events if ev["t"] == "played_order"] == [["9C", "AS"]]
    assert any("A♠ ends on top" in line for line in g.log[-6:])
    # nothing to ask (one card): nothing is left in the save either
    set_mission_enemy(g, "LABJS", hp=9)
    set_hand(g, ["9D", "2H"])
    g.play(["9D"])
    assert g.decision is None and "played_order" not in g.extra
    ids_everywhere(g)
    # mission 12's restored relic keeps restored cards off the banished pile: the named order
    # covers the cards that land there, a restored card goes under the reserve first
    c, g = mission(5, seed=1409)
    g.extra["played_order"] = {"enemy": g.enemy.card_id, "banished": ["9M", "AS"]}
    assert g.rules.order_for_banish(g, ["AS", "RESTORED", "9M"]) == ["RESTORED", "9M", "AS"]
    assert "played_order" not in g.extra
    # a batch the answer does not cover keeps its order and leaves the answer alone
    g.extra["played_order"] = {"enemy": g.enemy.card_id, "discard": ["9C", "AS"]}
    cards = [g.cards["AS"], g.cards["9C"], g.cards["3D"]]
    assert g.rules.order_for_discard(g, cards) == cards and g.extra["played_order"]["discard"] == ["9C", "AS"]


def test_pile_order_cli_cleanup_enter_keeps_the_order_played(monkeypatch, capsys):
    from regicide import cli
    c, g = mission(4, seed=1410)
    set_mission_enemy(g, "LABJD", hp=10)
    set_discard(g, ["7D"])
    set_hand(g, ["AS", "9C", "3D"])
    g.play(["AS", "9C"])
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert cli.human_turn(g, None)
    out = capsys.readouterr().out
    assert "Enemy defeated: the played cards go to the discard pile. What order?" in out and "(enter keeps the order played)" in out
    assert g.decision is None and g.discard[:3] == ["9C", "AS", "LABJD"]


def test_pile_order_cli_asks_for_the_whole_order(monkeypatch, capsys):
    from regicide import cli
    c, g = _m4_mage()
    g.play(["3M"])
    g.decide({"type": "mage_pick", "card": "4C"})
    answers = iter(["2", "2 2", "1 2"])                 # a card missing, a card twice, then the order
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    for _ in range(3):
        assert cli.human_turn(g, None)
    out = capsys.readouterr().out
    assert "What order? Name every card, the first goes first and the last ends on top" in out
    assert "1. 10♥" in out and "2. 2♦" in out and out.count("! Name every revealed card exactly once.") == 2
    assert g.decision is None and g.discard[:3] == ["2D", "10H", "2S"]
    # the reaver's reveal
    c, g = _m5()
    set_mission_enemy(g, "GRJH", hp=40)
    g.mission_zone = []
    set_hand(g, ["5R", "9S", "8S", "7S"])
    set_tavern_top(g, ["10C", "2D", "3D"])
    g.play(["5R"])
    g.decide({"type": "reaver_count", "count": 3})
    g.decide({"type": "reaver_pick", "card": "10C"})
    monkeypatch.setattr("builtins.input", lambda prompt="": "1 3 2")
    assert cli.human_turn(g, None)
    assert "the last ends on top of the banished pile" in capsys.readouterr().out
    assert g.banished[-3:] == ["10C", "3D", "2D"] and g.phase == PHASE_SUFFER
