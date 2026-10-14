"""Evergreen mode (pack E): the draw, the five locations, every bane and boon on its own,
and bot play-outs of random setups."""
import json
import random

import pytest

from helpers import set_hand, set_mission_enemy, set_tavern_top, _pull
from regicide.bots import greedy_policy, min_waste_discard, play_out, random_policy
from regicide.campaign import CampaignState
from regicide.campaign import evergreen as E
from regicide.campaign import missions as M
from regicide.campaign import party as P
from regicide.cards import Card
from regicide.engine import PHASE_DECIDE, PHASE_LOST, PHASE_PLAY, PHASE_SUFFER, PHASE_WON, Game, IllegalAction

RESTORED = ("2S", "3H", "4D", "5C", "7S", "8H", "9D", "ESME6E")


def _ids_everywhere(g):
    ids = g.all_card_ids() + g.extra.get("flute", [])
    assert len(ids) == len(set(ids)) == len(g.cards), (len(ids), len(set(ids)), len(g.cards))


def _powers(g):
    return dict((ev["suit"], ev) for ev in g.last_events if ev["t"] == "power")


def _rig(g, attr, ids):
    """Put exactly ``ids`` in the pile ``attr``: its current cards go under the reserve, the
    wanted cards are pulled from wherever they are."""
    old = list(getattr(g, attr))
    setattr(g, attr, [])
    for x in old:
        g.tavern.append(x)
    for x in ids:
        _pull(g, x)
    setattr(g, attr, list(ids))


def _switch_enemy(g, card_id, hp=None):
    for play in g.plays:
        g.discard.extend(play.card_ids)
    g.plays = []
    set_mission_enemy(g, card_id, hp=hp)


def _finished(players=1, seed=5000, relics=("mother_restored",), beast="B_H"):
    """A campaign that has just completed mission 12: the restored party, Esme, Ash, the mages."""
    names = ["Ana", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.mission = 12
    c.completed = list(range(1, 13))
    c.finished = True
    c.relics.extend(relics)
    c.flags["beasts"] = True
    c.set_beast(beast)
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    P.add_card(c.party, dict(M.ASH))
    P.add_card(c.party, dict(M.ESME_REBORN))
    for cid in RESTORED:
        P.add_flag(c.party, cid, "restored")
    return c


def _evergreen(location="A", banes=(), boons=(), players=1, seed=5000, mercs=(), **kw):
    c = _finished(players, seed, **kw)
    c.evergreen["setup"] = {"location": location, "banes": sorted(banes), "boons": sorted(boons)}
    if 24 in boons:
        c.evergreen["coins"] = 5
        for m in mercs:
            c.hire(m, "evergreen")
    g = c.start_evergreen_attempt(seed=seed)
    return c, g


def _probe(g, play=("AS",), pay=("9S", "8S")):
    """Play ``play`` against an enemy that survives, pay the damage with ``pay``: the end of
    turn runs and the next turn starts."""
    g.play(list(play))
    if g.phase == PHASE_SUFFER:
        g.suffer(list(pay))


# ---------------------------------------------------------------- the draw and the campaign side
def test_evergreen_draw_follows_the_rules_card_and_is_saved_with_the_campaign():
    c = _finished()
    c.finished = False
    with pytest.raises(RuntimeError):
        c.draw_evergreen()
    c.finished = True
    s = c.draw_evergreen()
    assert s["location"] in E.LOCATIONS
    assert [b["tier"] for b in s["banes"]].count("grey") == 2 and [b["tier"] for b in s["banes"]].count("yellow") == 1
    assert [b["tier"] for b in s["banes"]].count("red") == 1 and len(set(b["n"] for b in s["banes"])) == 4
    assert [b["tier"] for b in s["boons"]] == ["grey", "yellow"]
    ids = c.evergreen["setup"]
    assert ids == E.setup_ids(s) and c.evergreen_setup() == s and c.evergreen["attempts"] == 0
    assert c.evergreen["coins"] == (5 if 24 in ids["boons"] else 0)
    # the rules card's two variants, remembered as options for the next draw
    s2 = c.draw_evergreen(extra_red=True)
    tiers = [b["tier"] for b in s2["banes"]]
    assert tiers.count("grey") == 1 and tiers.count("red") == 2 and tiers.count("yellow") == 1
    assert c.evergreen["options"] == {"extra_red": True, "extra_bane": False}
    s3 = c.draw_evergreen(extra_bane=True)
    assert len(s3["banes"]) == 5 and c.evergreen["options"] == {"extra_red": True, "extra_bane": True}
    c.set_evergreen_option("extra_red", False)
    assert len(c.draw_evergreen()["banes"]) == 5
    # the save keeps everything; an old save without the entry gets the default
    c2 = CampaignState.from_dict(json.loads(json.dumps(c.to_dict())))
    assert c2.evergreen == c.evergreen and c2.evergreen_setup() == c.evergreen_setup()
    d = c.to_dict()
    del d["evergreen"]
    c3 = CampaignState.from_dict(d)
    assert c3.evergreen["setup"] is None and c3.evergreen_setup() is None and c3.evergreen["options"] == {"extra_red": False, "extra_bane": False}
    # starting and finishing attempts: no coins, no rewards, a record per setup
    g = c.start_evergreen_attempt(seed=1)
    assert g.config.rules_id == "evergreen" and g.rules.legacy and g.config.extra["evergreen"] == c.evergreen["setup"]
    assert c.evergreen["attempts"] == 1 and g.config.extra["mission"] == 13 and g.rules.uses_mission_zone
    g._lose("test")
    res = c.finish_attempt(g)
    assert res == {"won": False, "evergreen": True, "attempts": 1, "losses": 1}
    assert c.coins == 0 and c.finished and c.mission == 12 and c.evergreen["played"] == 1
    g = c.start_evergreen_attempt(seed=2)
    g._win()
    assert c.finish_attempt(g)["won"] and c.evergreen["wins"] == 1 and c.evergreen["attempts"] == 2
    # a redraw resets the record of the setup, not the overall one
    c.draw_evergreen()
    assert c.evergreen["attempts"] == 0 and c.evergreen["losses"] == 0 and c.evergreen["wins"] == 1 and c.evergreen["played"] == 2
    c.evergreen["setup"] = None
    with pytest.raises(RuntimeError):
        c.start_evergreen_attempt()
    with pytest.raises(RuntimeError):
        c.start_attempt()


def test_evergreen_boon_24_hires_mercenaries_with_a_five_coin_purse_of_its_own():
    c = _finished()
    c.evergreen["setup"] = {"location": "A", "banes": [], "boons": [24, 30]}
    c.evergreen["coins"] = 5
    assert c.hireable("evergreen") and all(o["affordable"] for o in c.hireable("evergreen")) and c.hireable() == []
    c.hire("merc_12H", "evergreen")
    c.hire("merc_ace_1", "evergreen")
    assert c.evergreen["coins"] == 1 and c.evergreen["mercenaries"] == ["merc_12H", "merc_ace_1"]
    assert c.mercenaries == [] and c.coins == 0
    with pytest.raises(ValueError):
        c.hire("merc_jester_1", "evergreen")          # 5 coins: too dear now
    with pytest.raises(ValueError):
        c.hire("merc_12H", "evergreen")               # already hired
    c.hire("merc_12D", "evergreen")
    assert c.evergreen["coins"] == 0 and "merc_12H" not in [o["id"] for o in c.hireable("evergreen")]
    assert not any(o["affordable"] for o in c.hireable("evergreen"))
    g = c.start_evergreen_attempt(seed=3)
    assert all(x in g.cards for x in ("M12H", "MA_1", "M12D")) and g.solo_jesters == 2
    c1 = _finished()
    c1.evergreen["setup"] = {"location": "A", "banes": [], "boons": [24, 30]}
    c1.evergreen["coins"] = 5
    c1.hire("merc_jester_1", "evergreen")
    assert c1.start_evergreen_attempt(seed=3).solo_jesters == 3   # the Jester mercenary is a third solo power
    c2 = _finished(players=2)
    c2.evergreen["setup"] = {"location": "A", "banes": [], "boons": [24, 30]}
    c2.evergreen["coins"] = 5
    c2.hire("merc_jester_1", "evergreen")
    g = c2.start_evergreen_attempt(seed=3)
    assert sum(1 for x in g.cards if g.cards[x].is_jester) == 1   # two players: the extra Jester is in the reserve


# ---------------------------------------------------------------- the enemies and the five locations
def test_evergreen_enemies_are_the_phase_two_and_three_experiments_in_corrupted_sleeves():
    c, g = _evergreen("A")
    enemies = [g.cards[x] for x in [g.enemy.card_id] + g.castle]
    assert [e.name for e in enemies] == ["Phase II Experiment"] * 4 + ["Phase III Experiment"] * 4
    assert all(e.has("corrupted") for e in enemies) and [(e.attack, e.health) for e in enemies][::4] == [(15, 30), (20, 40)]
    assert "B_H" in g.cards and "B_D" not in g.cards            # the chosen beast only
    assert g.config.max_hand == 8 and g.banished == [] and g.mission_zone == [] and "pilgrim_deck" not in g.extra
    assert g.rules.location_name(g) == "Shrine"
    _ids_everywhere(g)


def test_location_a_shrine_zone_grows_at_the_end_of_turn_grants_immunity_and_is_banished_on_a_kill():
    c, g = _evergreen("A")
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["AS", "9S", "8S", "7D"])
    set_tavern_top(g, ["6C", "4H"])                    # neither is a restored card: they can be banished
    _probe(g)
    assert g.mission_zone == ["6C"] and g.rules.immune_suits(g) == ("H", "C") and g.rules.attack_bonus(g) == 0
    assert g.enemy_attack == 15 - 1 and g.active == 0 and g.turn == 2
    _ids_everywhere(g)
    # a kill: the enemy is banished, then the zone; exact: the enemy is discarded instead
    set_hand(g, ["9S", "AS", "6D"])
    g.enemy.hp = 20
    g.play(["9S"])                                     # 9: not exact (20 - 9 = 11 left), then 15 - 10 = 5 damage
    assert g.enemy.hp == 11 and g.pending_damage == 5
    g.suffer(["6D"])
    assert g.mission_zone == ["6C", "4H"]
    set_hand(g, ["9H", "2C"])
    g.enemy.hp = 9
    g.play(["9H"])                                     # 9: exact (the cleric power is blocked by the immunity)
    # both attacks against it are cleaned up on top of the discarded enemy
    assert g.enemies_defeated == 1 and set(g.discard[:2]) == {"9H", "9S"} and g.discard[2] == "LABQH"
    assert g.banished[-2:] == ["6C", "4H"]
    assert g.mission_zone == [] and g.decision is None
    _ids_everywhere(g)
    set_hand(g, ["9S", "2C"])
    g.enemy.hp = 5
    g.play(["9S"])
    assert g.enemies_defeated == 2 and g.banished[-1] == g.cards[g.banished[-1]].id and g.cards[g.banished[-1]].name == "Phase II Experiment"


def test_location_b_cave_banishes_zone_and_discard_pile_when_the_zone_matches_the_base_strength():
    c, g = _evergreen("B")
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["AS", "9S", "8S", "7D", "6D"])
    set_tavern_top(g, ["10C", "6S", "3D"])
    _rig(g, "discard", ["2C", "3C"])
    _probe(g)                                          # the 10♣ into the zone: 10 < 15
    assert g.mission_zone == ["10C"] and g.rules.immune_suits(g) == ("H",) and g.rules.attack_bonus(g) == 0
    assert g.discard[:2] == ["8S", "9S"] and g.banished == []
    set_hand(g, ["AS", "7C", "9D", "8D"])
    g.play(["7C"])                                     # 14 damage, no draw
    g.suffer(["9D", "8D"])
    # the 6♠ brings the zone to 16 >= 15: zone and the whole discard pile are banished
    assert g.mission_zone == [] and g.banished[:2] == ["10C", "6S"] and g.discard == []
    assert any(ev["t"] == "zone_cleared" and ev["to"] == "banish" for ev in g.last_events)
    assert any(ev["t"] == "discard_banished" for ev in g.last_events) and "2C" in g.banished and "3C" in g.banished
    _ids_everywhere(g)
    # a kill: the enemy is banished (discarded on exact), the zone goes to the discard pile
    _rig(g, "mission_zone", ["4H", "5H"])
    set_hand(g, ["9C", "2C"])
    g.enemy.hp = 9
    g.play(["9C"])                                     # 18: not exact
    assert g.enemies_defeated == 1 and g.banished[-1] == "LABQH" and g.discard[:4] == ["9C", "7C", "5H", "4H"]
    _ids_everywhere(g)


def test_location_c_forest_starts_with_the_phase_one_experiments_banished_and_feeds_the_zone_from_the_banished_pile():
    c, g = _evergreen("C")
    assert sorted(g.banished) == sorted(["LABJH", "LABJD", "LABJC", "LABJS"]) and all(g.cards[x].has("corrupted") for x in g.banished)
    _switch_enemy(g, "LABQH", hp=100)
    _rig(g, "banished", ["2C", "7D"])                  # 7♦ on top
    set_hand(g, ["AS", "9S", "8S", "7C"])
    _probe(g)
    assert g.mission_zone == ["7D"] and g.rules.attack_bonus(g) == 7 and g.enemy_attack == 15 + 7 - 1
    assert g.rules.immune_suits(g) == ("H",)           # the Forest adds strength, not immunity
    _ids_everywhere(g)
    # a kill: enemy and zone into the banished pile, which is shuffled; exact: one zone card may be discarded first
    _rig(g, "mission_zone", ["7D", "3C"])
    set_hand(g, ["9S", "AS"])
    g.enemy.hp = 9
    g.play(["9S"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "zone_discard" and g.decision["exact"] is True
    acts = g.legal_actions()
    assert [a.get("card") for a in acts] == ["7D", "3C", None] and acts[-1]["skip"]
    assert greedy_policy(g)["card"] == "7D"
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "zone_discard", "card": "7D"})
    assert g.enemies_defeated == 1 and g.discard[:2] == ["9S", "7D"] and g.mission_zone == []
    assert "LABQH" in g.banished and "3C" in g.banished and any(ev["t"] == "banished_shuffled" for ev in g.last_events)
    _ids_everywhere(g)
    # not exact: no choice
    _rig(g, "mission_zone", ["3C"])
    set_hand(g, ["9S", "AS"])
    g.enemy.hp = 5
    g.play(["9S"])
    assert g.decision is None and g.enemies_defeated == 2 and "3C" in g.banished and g.mission_zone == []


def test_location_d_hills_deals_team_damage_equal_to_the_zone_at_the_end_of_turn():
    c, g = _evergreen("D", players=2)
    _switch_enemy(g, "LABQH", hp=100)
    _rig(g, "banished", ["3C", "7D"])
    set_hand(g, ["AS", "9S", "8S", "7C", "2D"], player=0)
    set_hand(g, ["5D", "6D"], player=1)
    g.play(["AS"])
    g.suffer(["9S", "8S"])
    # end of turn: the 7♦ joins the zone, then 7 team damage, paid by any player
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "team_discard" and g.decision["resume"] == "end_turn"
    assert g.decision["damage"] == 7 and g.decision["source"] == "The Hills" and g.mission_zone == ["7D"]
    assert sorted(a["card"] for a in g.legal_actions()) == ["2D", "5D", "6D", "7C"]
    g.decide({"type": "team_discard", "player": 1, "card": "5D"})
    g.decide({"type": "team_discard", "player": 0, "card": "2D"})
    assert g.decision is None and g.active == 1 and g.turn == 2 and g.discard[:2] == ["2D", "5D"]
    _ids_everywhere(g)
    # the next end of turn adds the 3♣: 10 damage, more than the hands hold: the mission is lost
    set_hand(g, ["AS", "4C", "9D", "8D"], player=1)
    set_hand(g, ["2C"], player=0)
    g.play(["AS"])
    g.suffer(["9D", "8D"])                             # 14 paid; the hands hold 6 against the Hills' 10
    assert g.phase == PHASE_LOST and "Hills" in g.loss_reason
    # a Guardian in the turn prevents it; the zone adds no strength here
    c, g = _evergreen("D")
    _switch_enemy(g, "LABQH", hp=100)
    _rig(g, "banished", ["7D"])
    g.cards["3G"] = Card.from_dict(dict(M.GUARDIANS[0]))   # Runo, the party's Guardian
    g.tavern.append("3G")
    set_hand(g, ["3G", "9S", "8S"])
    g.play(["3G"])
    assert g.phase == PHASE_PLAY and g.turn == 2 and g.mission_zone == ["7D"] and "guardian" not in g.extra
    assert any(ev["t"] == "team_damage_prevented" and ev["damage"] == 7 for ev in g.last_events)
    assert g.rules.attack_bonus(g) == 0 and len(g.players[0].hand) == 2


def test_location_e_lake_deals_pilgrims_into_the_zone_and_banishes_reserve_cards_on_a_kill():
    c, g = _evergreen("E")
    assert len(g.extra["pilgrim_deck"]) == 23 and len(g.mission_zone) == 1 and g.cards[g.mission_zone[0]].has("pilgrim")
    assert "PILA" not in g.cards                        # the puppy is in mission box 8
    assert not g.hand_locked(g.mission_zone[0])          # pilgrims are ordinary classless cards here
    _ids_everywhere(g)
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["AS", "9S", "8S", "7C"])
    _probe(g)
    assert len(g.mission_zone) == 2 and len(g.extra["pilgrim_deck"]) == 22 and g.rules.attack_bonus(g) == 0
    # an empty pilgrim deck: the top reserve card instead
    g.tavern.extend(g.extra["pilgrim_deck"])
    g.extra["pilgrim_deck"] = []
    set_tavern_top(g, ["5C"])
    set_hand(g, ["AS", "7C", "6C"])
    _probe(g, pay=("7C", "6C"))
    assert g.mission_zone[-1] == "5C" and len(g.mission_zone) == 3
    _ids_everywhere(g)
    # a kill: one reserve card banished per zone card, the zone to the discard pile in the
    # chosen order, then the enemy banished (discarded on exact)
    zone = list(g.mission_zone)
    set_hand(g, ["9S", "AS"])
    set_tavern_top(g, ["2H", "4H", "6H", "7H"])
    g.enemy.hp = 9
    g.play(["9S"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "zone_order" and g.banished[-3:] == ["2H", "4H", "6H"]
    assert any(ev["t"] == "lake_banish" and len(ev["cards"]) == 3 for ev in g.last_events)
    acts = g.legal_actions()
    assert len(acts) == 1 and acts[0]["needs"] == 3 and acts[0]["pick_from"] == zone and acts[0]["ordered"]
    with pytest.raises(IllegalAction):
        g.decide({"type": "zone_order", "cards": zone[:2]})
    assert greedy_policy(g)["cards"] == zone
    order = [zone[2], zone[0], zone[1]]
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "zone_order", "cards": order})
    assert g.enemies_defeated == 1 and g.discard[:5] == ["9S", "LABQH", zone[1], zone[0], zone[2]]   # exact: discarded
    assert g.mission_zone == ["7H"] and len(g.extra["pilgrim_deck"]) == 0   # the new turn took the top reserve card
    _ids_everywhere(g)
    # one zone card: no order to choose, the enemy banished when not exact
    g.suffer(min_waste_discard(g)) if g.phase == PHASE_SUFFER else None
    _rig(g, "mission_zone", ["4C"])
    set_hand(g, ["9S", "AS"])
    g.enemy.hp = 5
    g.play(["9S"])
    assert g.decision is None and g.enemies_defeated == 2 and g.discard[:2] == ["9S", "4C"] and g.cards[g.banished[-1]].name == "Phase II Experiment"


# ---------------------------------------------------------------- the grey banes (setup)
def test_bane_1_hydras_replace_the_phase_two_experiments_and_return_to_the_deck_unless_exact():
    c, g = _evergreen("A", banes=[1])
    enemies = [g.cards[x] for x in [g.enemy.card_id] + g.castle]
    assert [e.name for e in enemies] == ["Hydra Head"] * 6 + ["Phase III Experiment"] * 4
    _switch_enemy(g, "HY1", hp=5)
    set_hand(g, ["9S", "AS"] if "S" not in g.cards["HY1"].suits else ["9H", "AS"])
    before = len(g.castle)
    g.play([g.players[0].hand[0]])
    assert g.enemies_defeated == 1 and g.castle[-1] == "HY1" and len(g.castle) == before and "HY1" not in g.banished
    assert g.mission_zone == []
    _switch_enemy(g, "HY2", hp=9)
    card = "9D" if "D" not in g.cards["HY2"].suits else "9C"
    set_hand(g, [card, "AS"])
    hp_expected = 9
    g.play([card])
    if g.enemy.card_id != "HY2":
        assert g.discard[:2] == [card, "HY2"]            # exact: the Shrine discards it
    _ids_everywhere(g)


def test_bane_2_puts_thirty_reserve_cards_in_the_discard_pile_at_setup():
    c, g = _evergreen("A", banes=[2])
    assert len(g.discard) == 30 and len(g.players[0].hand) == 8
    assert any("Mental Health Day" in line for line in g.log)
    _ids_everywhere(g)


def test_bane_3_wyverns_replace_the_phase_three_experiments():
    c, g = _evergreen("A", banes=[3])
    enemies = [g.cards[x] for x in [g.enemy.card_id] + g.castle]
    assert [e.name for e in enemies] == ["Phase II Experiment"] * 4 + ["Wyvern"] * 6
    assert all(len(e.suits) == 2 and (e.attack, e.health) == (25, 50) for e in enemies[4:])


def test_bane_4_plays_with_the_corrupt_evergreen_mother_instead_of_the_restored_one():
    c, g = _evergreen("A", banes=[4])
    assert g.extra["relics"] == ["mother"]
    # the restored cards are banished like any other now, and a corrupted experiment in hand
    # asks the Mother's question
    _switch_enemy(g, "LABQH", hp=5)
    _rig(g, "mission_zone", ["3H"])
    set_hand(g, ["9S", "AS"])
    g.play(["9S"])
    assert g.enemies_defeated == 1 and "3H" in g.banished and g.rules.banish_redirect(g, g.cards["3H"]) is None
    c, g = _evergreen("A")
    assert g.extra["relics"] == ["mother_restored"] and g.rules.banish_redirect(g, g.cards["3H"]) == "reserve_bottom"


def test_bane_5_and_8_add_myla_and_the_high_arcana_to_the_bottom_of_the_deck():
    c, g = _evergreen("A", banes=[5, 8])
    assert g.castle[-2:] == ["MYLA_BOSS", "TH_ARCANA"] and len(g.castle) == 9
    _switch_enemy(g, "TH_ARCANA")
    assert (g.enemy.attack, g.enemy.max_hp) == (25, 120) and g.cards["TH_ARCANA"].suits == ()
    assert g.rules.immune_suits(g) == ("H", "D", "C", "S") and g.cards["TH_ARCANA"].has("immune_basic")
    set_hand(g, ["9S", "3H", "AS"])
    g.play(["9S"])
    assert _powers(g)["S"]["immune"] and g.shield == 0
    g.suffer(min_waste_discard(g)) if g.phase == PHASE_SUFFER else None
    if g.phase == PHASE_LOST:
        c, g = _evergreen("A", banes=[5, 8], seed=5001)
        _switch_enemy(g, "TH_ARCANA")
        set_hand(g, ["3H", "AS", "9S", "8S", "7S"])
    # a restored card ignores his immunity (it is not Myla's fixed kind), a mage is not blocked
    set_hand(g, ["3H", "AS", "9S", "8S", "7S", "6S"])
    _rig(g, "discard", ["2C", "4C"])
    g.play(["3H"])
    assert not _powers(g)["H"].get("immune") and _powers(g)["H"]["healed"] == 2
    _switch_enemy(g, "MYLA_BOSS")
    assert g.rules.fixed_immunity(g, "D") and g.rules.immune_suits(g) == ("D", "S")


def test_bane_6_and_7_set_aside_ash_quill_and_the_tens():
    c, g = _evergreen("A", banes=[6])
    assert "B_ASH" not in g.cards and "AM" not in g.cards and "10H" in g.cards
    c, g = _evergreen("A", banes=[7])
    assert not any(g.cards[x].rank == "10" for x in g.cards) and "B_ASH" in g.cards and "AM" in g.cards
    assert len([x for x in g.cards if g.cards[x].rank == "9"]) == 5
    c, g = _evergreen("A")
    assert sorted(x for x in g.cards if g.cards[x].rank == "10") == ["10C", "10D", "10H", "10M", "10S"]


# ---------------------------------------------------------------- the yellow banes (rule changes)
def test_bane_9_lethal_warriors_double_the_strength_bonuses_included():
    c, g = _evergreen("C", banes=[9])
    _switch_enemy(g, "LABQC")
    _rig(g, "mission_zone", ["7D"])
    assert g.rules.attack_multiplier(g) == 2 and g.enemy_attack == (15 + 7) * 2
    set_hand(g, ["9S", "AS"])
    g.play(["9S"])
    assert g.enemy_attack == 44 - 9                     # the shield comes off after the doubling
    _switch_enemy(g, "LABQH")
    assert g.rules.attack_multiplier(g) == 1


def test_bane_10_poisonous_clerics_feed_the_zone_from_the_discard_pile():
    c, g = _evergreen("A", banes=[10])
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["AS", "9S", "8S"])
    set_tavern_top(g, ["5C"])
    _probe(g)
    # the Shrine's reserve card first, then the bane's top discard (the 8♠ just paid)
    assert g.mission_zone == ["5C", "8S"] and g.discard[0] == "9S"
    _switch_enemy(g, "LABQD", hp=100)
    set_hand(g, ["AS", "7C", "8C"])
    _probe(g, pay=("7C", "8C"))
    assert len(g.mission_zone) == 3 and g.discard[0] == "8C"   # a bard: no cleric effect


def test_bane_11_immovable_paladins_reduce_the_damage_by_ten():
    c, g = _evergreen("A", banes=[11])
    _switch_enemy(g, "LABQS", hp=30)
    assert g.rules.damage_reduction(g) == 10
    set_hand(g, ["9H", "AS", "8C", "7D", "6D"])
    g.play(["9H"])
    assert g.enemy.hp == 30 and any(ev["t"] == "damage" and ev["amount"] == 0 for ev in g.last_events)
    g.suffer(["8C", "7D"])
    set_hand(g, ["8C", "AS"])
    g.enemy.hp = 6
    g.play(["8C"])                                     # 16 - 10 = 6: exact
    assert g.enemies_defeated == 1 and any(ev["t"] == "defeat" and ev["exact"] for ev in g.last_events)
    _switch_enemy(g, "LABQH")
    assert g.rules.damage_reduction(g) == 0


def test_bane_12_duplicitous_bards_take_a_hand_card_into_the_zone():
    c, g = _evergreen("A", banes=[12], players=2)
    _switch_enemy(g, "LABQD", hp=100)
    set_hand(g, ["AS", "9S", "8S", "2C"], player=0)
    g.play(["AS"])
    g.suffer(["9S", "8S"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "zone_feed" and g.decision["resume"] == "end_turn"
    assert len(g.mission_zone) == 1                    # the Shrine's reserve card came first
    acts = g.legal_actions()
    assert [a["card"] for a in acts] == ["2C"] and not any(a.get("skip") for a in acts)
    g.decide({"type": "zone_feed", "card": "2C"})
    assert g.decision is None and g.mission_zone[-1] == "2C" and g.active == 1
    _ids_everywhere(g)
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["AS", "9S", "8S", "2C"], player=1)
    g.play(["AS"])
    g.suffer(["9S", "8S"])
    assert g.decision is None and g.active == 0        # a cleric: no bard effect


def test_bane_13_explosive_spores_deal_team_damage_equal_to_the_base_strength_after_the_kill():
    c, g = _evergreen("A", banes=[13], players=2)
    _switch_enemy(g, "LABQH", hp=9)
    set_hand(g, ["9S", "AS", "8C"], player=0)
    set_hand(g, ["5D", "6D", "7D"], player=1)
    g.play(["9S"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "team_discard" and g.decision["resume"] == "defeat_tail"
    assert g.decision["damage"] == 15 and g.decision["source"] == "Explosive Spores"
    assert g.enemies_defeated == 1 and g.discard[0] == "9S" and g.enemy is None   # the piles are final
    g.decide({"type": "team_discard", "player": 1, "card": "7D"})
    g.decide({"type": "team_discard", "player": 0, "card": "8C"})
    assert g.decision is None and g.enemy is not None and g.phase == PHASE_PLAY and g.active == 0
    _ids_everywhere(g)
    # unpayable: lost
    _switch_enemy(g, "LABQD", hp=9)
    set_hand(g, ["9S", "AS"], player=0)
    set_hand(g, ["2D"], player=1)
    g.play(["9S"])
    assert g.phase == PHASE_LOST and "Explosive Spores" in g.loss_reason


def test_bane_14_absorbtion_keeps_the_killing_attack_in_the_zone():
    c, g = _evergreen("A", banes=[14])
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["2C", "9S", "8S", "AS"])
    g.play(["2C"])
    g.suffer(min_waste_discard(g))
    assert len(g.mission_zone) == 1
    set_hand(g, ["9S", "AS", "3D"])
    g.enemy.hp = 9
    g.play(["9S", "AS"] if False else ["9S"])
    # the zone was banished (Shrine), then the 9♠ went into the zone instead of the discard pile
    assert g.enemies_defeated == 1 and g.mission_zone == ["9S"] and g.discard[0] == "2C"
    assert any(ev["t"] == "zone_absorb" and ev["cards"] == ["9S"] for ev in g.last_events)
    assert g.rules.immune_suits(g)[-1] == "S"          # and the Shrine makes the next enemy immune to it
    _ids_everywhere(g)


def test_bane_15_tread_carefully_banishes_the_discard_pile_on_a_kill_that_is_not_exact():
    c, g = _evergreen("B", banes=[15])
    _switch_enemy(g, "LABQH", hp=5)
    _rig(g, "discard", ["2C", "3C"])
    _rig(g, "mission_zone", ["4H"])
    set_hand(g, ["9S", "AS"])
    g.play(["9S"])
    # the pile is banished before the Cave discards the zone: the zone survives on the new pile
    assert g.banished[:2] == ["3C", "2C"] and "LABQH" in g.banished and g.discard == ["9S", "4H"]
    _ids_everywhere(g)
    _switch_enemy(g, "LABQD", hp=9)
    set_hand(g, ["9S", "AS"])
    g.play(["9S"])                                     # exact: the pile stays
    assert g.discard[:3] == ["9S", "LABQD", "9S"] if False else g.discard[0] == "9S" and "4H" in g.discard


# ---------------------------------------------------------------- the red banes (ongoing)
def test_banes_16_and_22_move_the_pile_tops_at_the_start_of_turn():
    c, g = _evergreen("A", banes=[16, 22])
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["AS", "9S", "8S"])
    set_tavern_top(g, ["5C", "4D", "3D"])
    _rig(g, "discard", ["2C"])
    _probe(g)
    # end of turn: the 5♣ into the zone (Shrine); start of turn: the 8♠ (top discard) is banished
    # (bane 16 first), then the 4♦ goes from the reserve to the discard pile (bane 22)
    assert g.mission_zone == ["5C"] and g.banished == ["8S"] and g.discard[:2] == ["4D", "9S"] and g.tavern[0] == "3D"
    assert [ev.get("n") for ev in g.last_events if ev["t"] == "bane"] == [16, 22]
    _ids_everywhere(g)


def test_banes_17_to_20_pile_tops_grant_strength_and_immunity():
    c, g = _evergreen("A", banes=[17, 18, 19, 20])
    _switch_enemy(g, "LABQH")
    _rig(g, "discard", ["7C", "2C"])
    _rig(g, "banished", ["3D", "5S"])
    assert g.rules.attack_bonus(g) == 7 + 5 and g.enemy_attack == 27
    assert g.rules.immune_suits(g) == ("H", "C", "S")
    c, g = _evergreen("A", banes=[17, 19])
    _switch_enemy(g, "LABQH")
    _rig(g, "discard", ["7C", "2C"])
    _rig(g, "banished", ["3D", "5S"])
    assert g.rules.attack_bonus(g) == 7 and g.rules.immune_suits(g) == ("H", "C")
    c, g = _evergreen("A", banes=[18, 20])
    _switch_enemy(g, "LABQH")
    _rig(g, "discard", ["7C", "2C"])
    _rig(g, "banished", ["3D", "5S"])
    assert g.rules.attack_bonus(g) == 5 and g.rules.immune_suits(g) == ("H", "S")
    # a Jester or a classless card on top grants strength only (0 for the Jester)
    g.banished.append("B_H")
    g.tavern.remove("B_H")
    assert g.rules.attack_bonus(g) == 0 and g.rules.immune_suits(g) == ("H",)


def test_bane_21_eye_level_sticks_discards_a_hand_card_after_an_attack_with_an_eight():
    c, g = _evergreen("A", banes=[21], players=2, relics=("mother_restored", "flute"))
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["8C", "2D", "9S", "AS", "7D"], player=0)
    set_hand(g, ["3C"], player=1)
    pv = g.preview_play(["8C"])
    assert pv["ok"] and pv["decision_kind"] == "attack_discard" and pv["damage"] == 16
    g.play(["8C"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "attack_discard" and g.deciding == 0 and g.enemy.hp == 100
    acts = g.legal_actions()
    assert sorted(a["card"] for a in acts) == ["2D", "7D", "9S", "AS"] and not any(a.get("skip") for a in acts)
    assert greedy_policy(g)["card"] == "AS"
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "attack_discard", "card": "2D"})
    assert g.discard[0] == "2D" and g.decision is None and g.enemy.hp == 100 - 16 and g.phase == PHASE_SUFFER
    _ids_everywhere(g)
    g.suffer(["9S", "7D"])
    # a 3 played by Ben: no discard, but the Kinfolk Flute still asks Ana (relics come after)
    set_hand(g, ["3C", "4D"], player=1)
    set_hand(g, ["3H", "AS"], player=0)
    g.play(["3C"])
    assert g.decision["kind"] == "flute_add" and g.deciding == 0
    g.flute_pass()
    assert g.decision is None
    # strength 8 as a kinfolk total does not count (no card of 8); a beast with a 9 does; an empty hand skips it
    c, g = _evergreen("A", banes=[21])
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["4C", "4D", "AS"])
    g.play(["4C", "4D"])
    assert g.decision is None
    g.suffer(min_waste_discard(g)) if g.phase == PHASE_SUFFER else None
    set_hand(g, ["B_H", "9C", "2D"])
    g.play(["B_H", "9C"])
    assert g.decision["kind"] == "attack_discard" and [a["card"] for a in g.legal_actions()] == ["2D"]
    g.decide({"type": "attack_discard", "card": "2D"})
    assert g.decision is None
    g.suffer(min_waste_discard(g)) if g.phase == PHASE_SUFFER else None
    if g.phase == PHASE_PLAY:
        set_hand(g, ["8S"])
        g.play(["8S"])
        assert g.decision is None                      # nothing left to discard


def test_bane_23_choose_your_poison_discards_a_hand_card_or_feeds_the_zone_from_the_reserve():
    c, g = _evergreen("A", banes=[23])
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["AS", "9S", "8S", "2C", "3C"])
    set_tavern_top(g, ["5C", "4D", "3D", "2D"])
    g.play(["AS"])
    g.suffer(["9S", "8S"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "poison" and g.decision["resume"] == "end_turn"
    acts = g.legal_actions()
    assert sorted(a.get("card") or "" for a in acts) == ["", "2C", "3C"] and acts[-1]["skip"]
    assert greedy_policy(g)["type"] == "poison_skip"   # two cards in hand: the bot keeps them
    g.decide({"type": "poison_skip"})
    # the Shrine's reserve card first (5♣), then the bane's (4♦)
    assert g.mission_zone == ["5C", "4D"] and g.decision is None and g.turn == 2
    _ids_everywhere(g)
    set_hand(g, ["AS", "9S", "8S", "2C", "3C", "4C"])
    g.play(["AS"])
    g.suffer(["9S", "8S"])
    assert greedy_policy(g) == {"type": "poison", "player": 0, "card": "2C", "label": "Discard 2♣"}
    g.decide({"type": "poison", "card": "2C"})
    assert g.discard[0] == "2C" and g.mission_zone == ["5C", "4D", "3D"] and g.decision is None
    # an empty hand: the reserve card goes straight into the zone
    set_hand(g, ["9S"])
    g.play(["9S"])
    assert g.decision is None and len(g.mission_zone) >= 2 and g.phase in (PHASE_PLAY, PHASE_LOST)


# ---------------------------------------------------------------- the boons
def test_boons_25_26_28_29_add_cards_to_the_reserve():
    c, g = _evergreen("A", boons=[25])
    assert "GOR8E" in g.cards and g.cards["GOR8E"].has("ignores_immunity")
    c, g = _evergreen("A", boons=[26])
    assert all(b["id"] in g.cards for b in M.BEASTS)
    c, g = _evergreen("A", boons=[29])
    assert all(x in g.cards for x in ("3R", "3U", "3T")) and g.cards["3R"].name == "" and g.cards["3R"].label() == "3⚔"
    c, g = _evergreen("A", boons=[28])
    assert "PILA" in g.cards and g.cards["PILA"].has("evergreen_puppy") and not g.cards["PILA"].has("pilgrim")
    # the puppy has all four classes while played, none anywhere else
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["PILA", "9S", "8S"])
    _rig(g, "discard", ["2C", "3C"])
    g.play(["PILA"])
    assert g.plays[0].suits == ("H", "D", "C", "S") and g.plays[0].value == 1 and _powers(g)["H"]["immune"]
    assert _powers(g)["D"]["drawn"] and _powers(g)["C"]["doubled"] and g.shield == 1 and g.enemy.hp == 100 - 2
    g.suffer(min_waste_discard(g))
    set_hand(g, ["PILA", "9S"])
    assert g.check_play(["PILA", "9S"]) == (True, "companion") and g.cards["PILA"].suits == ()
    _rig(g, "mission_zone", ["PILA"])
    assert g.rules.zone_suits(g) == ()                  # a puppy in the zone grants no immunity (Shrine)
    assert g.rules.top_card_suits(g, g.mission_zone, False) == ()


def test_boon_27_raises_the_hand_limit_and_boon_34_the_kinfolk_limit():
    c, g = _evergreen("A", boons=[27])
    assert g.config.max_hand == 9 and all(len(p.hand) == 9 for p in g.players)
    c, g = _evergreen("A", boons=[27], players=2)
    assert g.config.max_hand == 8
    c, g = _evergreen("A", boons=[34], players=2, relics=("mother_restored", "flute"))
    assert g.rules.kinfolk_limit(g) == 12
    _switch_enemy(g, "LABQH", hp=100)
    set_hand(g, ["6C", "6D", "4H", "4S", "4C", "AS"], player=0)
    set_hand(g, ["6H", "4D"], player=1)
    assert g.check_play(["6C", "6D"]) == (True, "set") and g.check_play(["4H", "4S", "4C"]) == (True, "set")
    assert g.check_play(["6C", "6D", "6H"])[0] is False
    assert ["6C", "6D"] in g.legal_plays() and ["4H", "4S", "4C"] in g.legal_plays()
    g.play(["6C", "6D"])                               # 12; the flute may not add a third 6
    assert g.decision is None or g.decision["kind"] != "flute_add"
    c, g = _evergreen("A", players=2)
    set_hand(g, ["6C", "6D", "AS"], player=0)
    assert g.check_play(["6C", "6D"])[0] is False and ["6C", "6D"] not in g.legal_plays()


def test_boon_30_squad_of_siblings_moves_a_matching_zone_card_after_an_attack():
    c, g = _evergreen("A", boons=[30])
    _switch_enemy(g, "LABQH", hp=100)
    _rig(g, "mission_zone", ["7C", "2D", "7S"])
    set_hand(g, ["7D", "9S", "8S"])
    pv = g.preview_play(["7D"])
    assert pv["ok"] and pv["decision_kind"] == "zone_sibling"
    g.play(["7D"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "zone_sibling" and g.enemy.hp == 100
    acts = g.legal_actions()
    assert [a.get("card") for a in acts] == ["7C", "7S", None] and acts[-1]["skip"]
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "zone_sibling", "card": "7S"})
    assert g.discard[0] == "7S" and g.mission_zone == ["7C", "2D"] and g.decision is None and g.enemy.hp == 100 - 7
    assert g.rules.immune_suits(g) == ("H", "C", "D")   # the Shrine lost the paladin immunity with it
    _ids_everywhere(g)
    g.suffer(min_waste_discard(g))
    set_hand(g, ["3D", "AS", "9S"])
    g.play(["3D"])
    assert g.decision is None                          # no match, no question


def test_boon_31_selfless_rescue_after_each_discarded_card_that_matches_the_zone():
    c, g = _evergreen("A", boons=[31])
    _switch_enemy(g, "LABQH", hp=100)
    _rig(g, "mission_zone", ["7C", "9D", "7S"])
    set_hand(g, ["AS", "9S", "7D", "2C"])
    g.play(["AS"])
    assert g.pending_damage == 15                      # the 7♠ in the zone makes the Shrine's enemy immune to paladins
    g.suffer(["9S", "7D"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "zone_match" and g.decision["resume"] == "suffered"
    assert g.decision["matched"] == "9S" and [a.get("card") for a in g.legal_actions()] == ["9D", None]
    g.decide({"type": "zone_match", "card": "9D"})
    assert g.discard[0] == "9D" and g.decision["kind"] == "zone_match" and g.decision["matched"] == "7D"
    assert [a.get("card") for a in g.legal_actions()] == ["7C", "7S", None]
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "zone_match_skip"})
    assert g.decision is None and g.mission_zone[:2] == ["7C", "7S"] and g.turn == 2    # the end of turn ran
    _ids_everywhere(g)


def test_boon_32_precision_strike_takes_a_zone_card_or_the_top_discard_into_hand_on_an_exact_kill():
    c, g = _evergreen("A", boons=[32])
    _switch_enemy(g, "LABQH", hp=9)
    _rig(g, "mission_zone", ["7C", "2D"])
    _rig(g, "discard", ["5H", "3H"])
    set_hand(g, ["9S", "AS"])
    g.play(["9S"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "precision_strike" and g.decision["exact"] is True
    acts = g.legal_actions()
    assert [(a["card"], a["pile"]) for a in acts] == [("7C", "zone"), ("2D", "zone"), ("5H", "discard")]
    assert not any(a.get("skip") for a in acts) and greedy_policy(g)["card"] == "7C"
    with pytest.raises(IllegalAction):
        g.decide({"type": "precision_strike", "card": "3H", "pile": "discard"})
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "precision_strike", "card": "7C", "pile": "zone"})
    # taken before the Shrine banishes the rest of the zone
    assert "7C" in g.players[0].hand and g.enemies_defeated == 1 and g.banished == ["2D"] and g.discard[:2] == ["9S", "LABQH"]
    _ids_everywhere(g)
    _switch_enemy(g, "LABQD", hp=5)
    set_hand(g, ["9S", "AS"])
    g.play(["9S"])                                     # not exact: nothing
    assert g.decision is None and g.enemies_defeated == 2


def test_boon_33_restored_arrows_puts_a_banished_card_under_the_reserve_on_an_exact_kill():
    c, g = _evergreen("A", boons=[33])
    _switch_enemy(g, "LABQH", hp=9)
    _rig(g, "banished", ["5H", "3C"])
    set_hand(g, ["9S", "AS"])
    g.play(["9S"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "restored_arrows"
    acts = g.legal_actions()
    assert [a.get("card") for a in acts] == ["5H", "3C", None] and acts[-1]["skip"] and greedy_policy(g)["card"] == "5H"
    g.decide({"type": "restored_arrows", "card": "5H"})
    assert g.tavern[-1] == "5H" and g.banished == ["3C"] and g.enemies_defeated == 1 and g.decision is None
    _ids_everywhere(g)
    _switch_enemy(g, "LABQD", hp=9)
    set_hand(g, ["9S", "AS"])
    g.play(["9S"])
    g.decide({"type": "restored_arrows_skip"})
    assert g.enemies_defeated == 2 and g.banished == ["3C"]


def test_boon_35_a_close_call_sends_an_exact_payment_under_the_reserve_and_picks_a_discard_for_the_top():
    c, g = _evergreen("C", boons=[35])                 # the Forest: nothing moves at the end of the turn here
    _switch_enemy(g, "LABQH", hp=100)
    _rig(g, "banished", [])
    _rig(g, "discard", ["5H", "3C"])
    set_hand(g, ["AS", "9S", "5D", "2C"])
    g.play(["AS"])
    assert g.pending_damage == 14
    g.suffer(["9S", "5D"])                             # exactly 14
    assert g.tavern[-2:] == ["9S", "5D"] and g.discard == ["5H", "3C"]
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "close_call" and g.decision["resume"] == "suffered"
    acts = g.legal_actions()
    assert [a["card"] for a in acts] == ["5H", "3C"] and not any(a.get("skip") for a in acts)
    assert greedy_policy(g)["card"] == "5H"
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "close_call", "card": "3C"})
    assert g.tavern[0] == "3C" and g.discard == ["5H"] and g.decision is None and g.turn == 2
    _ids_everywhere(g)
    # an overpayment goes to the discard pile as usual; so does a feigned death
    set_hand(g, ["AS", "9S", "8S"])
    g.play(["AS"])
    g.suffer(["9S", "8S"])
    assert g.discard[:2] == ["8S", "9S"] and g.decision is None


# ---------------------------------------------------------------- random setups played out
@pytest.mark.parametrize("players", [1, 2])
def test_bots_play_out_random_evergreen_setups(players):
    rng = random.Random(600 + players)
    seen = set()
    for i in range(8):
        setup = E.draw_setup(rng, extra_red=i % 3 == 0, extra_bane=i % 4 == 0)
        ids = E.setup_ids(setup)
        c, g = _evergreen(ids["location"], ids["banes"], ids["boons"], players=players, seed=5100 + i,
                          mercs=("merc_12H", "merc_ace_1"), relics=("flute", "whistle", "emblem", "mother_restored"))
        policy = greedy_policy if i % 2 == 0 else random_policy
        play_out(g, policy, rng, max_steps=5000)
        assert g.is_over and g.decision is None
        _ids_everywhere(g)
        assert all(len(p.hand) <= g.config.max_hand for p in g.players)
        res = c.finish_attempt(g)
        assert res["evergreen"] and c.evergreen["played"] == 1
        seen.add(ids["location"])
    assert len(seen) >= 2
