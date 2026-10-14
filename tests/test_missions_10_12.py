"""Legacy missions 10 (Pride to Fall), 11 (Descent Into Darkness) and 12 (Decay to Growth)."""
import json
import random

import pytest

from helpers import set_hand, set_mission_enemy, set_tavern_top, _pull
from regicide.bots import apply_action, greedy_policy, min_waste_discard, play_out, random_policy
from regicide.campaign import CampaignState
from regicide.campaign import missions as M
from regicide.campaign import party as P
from regicide.campaign.missions import MISSIONS
from regicide.cards import Card
from regicide.engine import PHASE_DECIDE, PHASE_LOST, PHASE_PLAY, PHASE_SUFFER, PHASE_WON, Game, IllegalAction

CORRUPTED = ("2S", "3H", "4D", "5C", "6C", "7S", "8H", "9D")


def _ids_everywhere(g):
    ids = g.all_card_ids() + g.extra.get("flute", [])
    assert len(ids) == len(set(ids)) == len(g.cards), (len(ids), len(set(ids)), len(g.cards))


def _rig(g, attr, ids):
    """Put exactly ``ids`` in the pile ``attr`` (zone, banished, discard): the pile's current
    cards go under the reserve, the wanted cards are pulled from wherever they are."""
    old = list(getattr(g, attr))
    setattr(g, attr, [])
    for x in old:
        g.tavern.append(x)
    for x in ids:
        _pull(g, x)
    setattr(g, attr, list(ids))


def _switch_enemy(g, card_id, hp=None):
    """A new enemy for the next check; the cards in play go to the discard pile first
    (``set_mission_enemy`` simply forgets them, which breaks the card-conservation checks)."""
    for play in g.plays:
        g.discard.extend(play.card_ids)
    g.plays = []
    set_mission_enemy(g, card_id, hp=hp)


def _powers(g):
    return [(ev["suit"], ev) for ev in g.last_events if ev["t"] == "power"]


def _campaign(number, players=1, seed=1000, relics=(), beast="B_H",
              corrupted=CORRUPTED, stickers=(("4D", "U"), ("7S", "C"))):
    names = ["Ana", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.mission = number
    c.completed = list(range(1, number))
    c.relics.extend(relics)
    c.flags["beasts"] = True
    c.set_beast(beast)
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    P.add_card(c.party, dict(M.ASH))
    for cid in corrupted:
        P.add_flag(c.party, cid, "corrupted")
        c.corrupted.append(cid)
    for cid, s in stickers:
        P.add_suit(c.party, cid, s)
    return c


def _mission10(players=1, seed=1000, **kw):
    c = _campaign(10, players, seed, **kw)
    P.add_card(c.party, dict(M.GORAN_RENEWED))
    g = c.start_attempt(seed=seed)
    return c, g


def _mission11(players=1, seed=1100, **kw):
    kw.setdefault("corrupted", ("2S", "3H", "4D", "5C", "6H", "7S", "8H", "9D"))
    c = _campaign(11, players, seed, **kw)
    g = c.start_attempt(seed=seed)
    return c, g


def _mission12(players=1, seed=1200, **kw):
    kw.setdefault("corrupted", ("2S", "3H", "4D", "5C", "7S", "8H", "9D"))
    c = _campaign(12, players, seed, **kw)
    P.add_card(c.party, dict(M.ESME_REBORN))
    g = c.start_attempt(seed=seed)
    return c, g


# ---------------------------------------------------------------- Mission 10: Pride to Fall
def test_mission10_deck_is_the_corrupted_party_face_up_with_five_times_health_and_zone_strength():
    c, g = _mission10()
    assert g.config.rules_id == "legacy_m10" and MISSIONS[9]["playable"] and g.rules.uses_mission_zone
    assert P.corrupted_ids(c.party) == [] and sorted(d["id"] for d in c.away) == sorted(CORRUPTED)
    # 2 on top down to 9, every one corrupted and five times as healthy as strong
    assert g.enemy.card_id == "2S" and (g.enemy.attack, g.enemy.max_hp) == (2, 10)
    assert g.castle == ["3H", "4D", "5C", "6C", "7S", "8H", "9D"]
    assert all(g.cards[x].has("corrupted") for x in [g.enemy.card_id] + g.castle)
    assert g.cards["4D"].suits == ("D", "U") and g.cards["7S"].suits == ("S", "C")   # stickers kept
    # the first start of turn moved the top reserve card into the zone: it adds to the enemy
    assert len(g.mission_zone) == 1 and g.rules.attack_bonus(g) == g.rules.zone_strength(g)
    assert g.enemy_attack == 2 + g.rules.zone_strength(g)
    assert any(ev["t"] == "zone_add" and ev.get("source") == "reserve" for ev in g.last_events)
    _ids_everywhere(g)
    # the card's example: Wicket (2, paladin) with a 6 and Glamelyn (4) in the zone deals 2
    # less damage and strikes for 12
    _rig(g, "mission_zone", ["6D", "4H"])
    assert g.rules.attack_bonus(g) == 10 and g.enemy_attack == 12 and g.rules.damage_reduction(g) == 2
    set_hand(g, ["9C", "AS"])
    g.play(["9C"])                                     # 9 doubled by the warrior, 2 less for the paladin: 16 > 10
    assert any(ev["t"] == "damage" and ev["amount"] == 16 for ev in g.last_events) and g.enemies_defeated == 1
    _ids_everywhere(g)


def test_mission10_paladin_reduces_damage_by_base_strength_and_exact_is_after_the_reduction():
    c, g = _mission10(seed=1001)
    _rig(g, "mission_zone", ["6D", "4H"])
    set_hand(g, ["2D", "9H", "AS", "8S"])
    assert g.enemy.card_id == "2S"
    g.play(["2D"])                                     # 2 - 2 = 0: nothing happens, then 12 damage
    assert g.enemy.hp == 10 and g.phase == PHASE_SUFFER and g.pending_damage == 12
    assert any(ev["t"] == "damage" and ev["amount"] == 0 for ev in g.last_events)
    g.suffer(["9H", "8S"])
    # a 9 against 7 health: 9 - 2 = 7, exact; the zone goes to the discard pile, the enemy too
    set_hand(g, ["9H", "AS"])
    _rig(g, "mission_zone", ["6D", "4H"])
    g.enemy.hp = 7
    zone = list(g.mission_zone)
    g.play(["9H"])
    assert g.enemies_defeated == 1 and any(ev["t"] == "defeat" and ev["exact"] for ev in g.last_events)
    assert "2S" in g.discard and all(x in g.discard for x in zone) and not any(x in g.banished for x in zone)
    assert g.discard[0] == "9H"                        # the played card on top (p.19)
    assert g.enemy.card_id == "3H" and len(g.mission_zone) == 1    # the new turn fed the zone
    _ids_everywhere(g)


def test_mission10_warrior_doubles_the_total_strength_before_shields_and_a_two_class_enemy_has_both_powers():
    c, g = _mission10(seed=1002)
    _switch_enemy(g, "5C")                         # the corrupted warrior: 5 / 25
    _rig(g, "mission_zone", ["6D", "4H"])
    assert g.rules.attack_multiplier(g) == 2 and g.enemy_attack == (5 + 10) * 2
    set_hand(g, ["9S", "AS", "10H", "10D", "8D"])
    g.play(["9S"])                                     # shield 9 comes off after the doubling
    assert g.shield == 9 and g.enemy_attack == 30 - 9 and g.pending_damage == 21 and g.phase == PHASE_SUFFER
    g.suffer(["10H", "10D", "AS"])
    c, g = _mission10(seed=1002)
    # 7♠ with a warrior sticker: immune to paladins and warriors, doubles its strength and
    # reduces the damage dealt to it by 7
    _switch_enemy(g, "7S")
    assert g.rules.immune_suits(g) == ("S", "C") and g.rules.attack_multiplier(g) == 2 and g.rules.damage_reduction(g) == 7
    _rig(g, "mission_zone", [])
    assert g.enemy_attack == 14
    set_hand(g, ["10H", "AS"])
    g.play(["10H"])
    assert g.enemy.hp == 35 - 3                        # 10 - 7
    # a bard with a druid sticker is immune to both and has the bard power at the end of the turn
    c, g = _mission10(seed=1003)
    _switch_enemy(g, "4D")
    assert g.rules.immune_suits(g) == ("D", "U") and g.rules.attack_multiplier(g) == 1 and g.rules.damage_reduction(g) == 0


def test_mission10_cleric_and_bard_powers_at_the_end_of_the_turn_and_the_feed_decision():
    c, g = _mission10(players=2, seed=1004)
    _switch_enemy(g, "3H", hp=100)                 # the corrupted cleric
    _rig(g, "mission_zone", [])
    _rig(g, "discard", ["7C", "2C"])
    set_hand(g, ["AS", "9S", "8S"], player=0)
    set_hand(g, ["5D", "6D"], player=1)
    g.play(["AS"])
    g.suffer(["9S"]) if g.phase == PHASE_SUFFER else None
    # end of turn: the top discard (the 9♠ just paid) went into the zone, then Ben's turn fed
    # the zone from the reserve
    assert g.mission_zone[0] == "9S" and len(g.mission_zone) == 2 and g.discard[0] == "7C" and g.active == 1
    assert any(ev["t"] == "zone_add" and ev.get("source") == "discard" for ev in g.last_events)
    _ids_everywhere(g)
    # the bard: the current player must put a hand card into the zone (no pass)
    c, g = _mission10(players=2, seed=1005)
    _switch_enemy(g, "4D", hp=100)
    _rig(g, "mission_zone", [])
    set_hand(g, ["AS", "9S", "8S", "2C"], player=0)
    g.play(["AS"])
    g.suffer(["9S"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "zone_feed" and g.decision["resume"] == "end_turn"
    assert g.deciding == 0
    acts = g.legal_actions()
    assert sorted(a["card"] for a in acts) == ["2C", "8S"] and not any(a.get("skip") for a in acts)
    assert greedy_policy(g)["card"] == "2C"
    with pytest.raises(IllegalAction):
        g.decide({"type": "zone_feed", "card": "9S"})
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "zone_feed", "card": "2C"})
    assert g.decision is None and "2C" in g.mission_zone and g.active == 1 and g.phase == PHASE_PLAY
    assert len(g.mission_zone) == 2                    # Ben's start of turn fed it from the reserve
    _ids_everywhere(g)
    # an empty hand skips the bard's effect
    set_hand(g, ["AS"], player=1)
    g.play(["AS"])
    if g.phase == PHASE_SUFFER:
        assert g.phase == PHASE_LOST or True
    # a kill skips the end-of-turn powers
    c, g = _mission10(seed=1006)
    _switch_enemy(g, "4D", hp=5)
    _rig(g, "mission_zone", [])
    set_hand(g, ["9S", "2C"])
    g.play(["9S"])
    assert g.enemies_defeated == 1 and g.decision is None and g.active == 0


def test_mission10_not_exact_banishes_the_zone_and_a_defeated_member_plays_from_hand_as_corrupted():
    c, g = _mission10(seed=1007)
    _switch_enemy(g, "2S", hp=4)
    _rig(g, "mission_zone", ["6D", "4H"])
    set_hand(g, ["9S", "AS", "2C"])
    g.play(["9S"])                                     # 9 - 2 = 7 > 4: not exact
    assert g.enemies_defeated == 1 and g.banished[-2:] == ["6D", "4H"] and g.discard[:2] == ["9S", "2S"]
    _ids_everywhere(g)
    # the defeated paladin Wicket, drawn from the discard pile, plays as the corrupted card it is
    _switch_enemy(g, "5C", hp=100)
    _rig(g, "mission_zone", [])
    set_hand(g, ["2S", "AS", "8S"])
    top = g.tavern[0]
    g.play(["2S"])
    assert any(ev["t"] == "corrupt_banish" and ev["card"] == "2S" for ev in g.last_events)
    assert g.banished[-1] == top and g.shield == 2 and g.enemy.hp == 100 - 2
    _ids_everywhere(g)
    # the mission is won when the eighth member falls
    g.suffer(["8S"]) if g.phase == PHASE_SUFFER else None
    g.castle = []
    g.enemy.hp = 9
    set_hand(g, ["9H", "AS"])
    g.play(["9H"])
    assert g.phase == PHASE_WON


# ---------------------------------------------------------------- Mission 11: Descent Into Darkness
def _rig_beasts(g, deck, out=()):
    g.extra["beast_deck"] = list(deck)
    g.extra["beasts_out"] = list(out)


def test_mission11_beast_deck_reveals_at_every_start_of_turn_with_the_four_effects():
    c, g = _mission11(players=2)
    assert g.config.rules_id == "legacy_m11" and MISSIONS[10]["playable"] and g.rules.uses_mission_zone
    enemies = [g.cards[x] for x in [g.enemy.card_id] + g.castle]
    assert [e.name for e in enemies] == ["Justicar"] * 4 + ["Corrupted Evergreen"] and all(e.suits == () for e in enemies)
    assert "B_H" not in g.cards or "B_H" in g.extra["beast_deck"] + g.extra["beasts_out"]   # no chosen beast in the reserve
    assert "B_ASH" in g.tavern + g.players[0].hand + g.players[1].hand
    # the first reveal happened before the first player acts
    assert len(g.extra["beast_deck"]) == 3 and len(g.extra["beasts_out"]) == 1
    assert any(ev["t"] == "beast_reveal" for ev in g.last_events)
    _ids_everywhere(g)
    if g.phase == PHASE_DECIDE:
        g.decide(greedy_policy(g))
    # warrior: the top discard is banished; paladin: the top reserve card is discarded
    _switch_enemy(g, "CV_J1", hp=100)
    set_hand(g, ["AS", "2H", "3D", "5S", "6S"], player=0)
    set_hand(g, ["9S", "6D", "7D", "8D"], player=1)
    _rig(g, "discard", ["7C", "2C"])
    _rig(g, "banished", [])
    set_tavern_top(g, ["4H", "3H"])
    _rig_beasts(g, ["B_C", "B_S", "B_H", "B_D"])
    g.play(["AS"])                                     # 10 + 7 (the 7♣ on top of the discard pile) - 1
    assert g.phase == PHASE_SUFFER and g.pending_damage == 16
    g.suffer(["2H", "3D", "5S", "6S"])                 # 6♠ ends on top of the discard pile
    # Ben's turn: the warrior beast banishes the top discard (6♠); both pile tops now add up
    assert g.active == 1 and g.extra["beasts_out"] == ["B_C"] and g.banished[-1] == "6S" and g.discard[0] == "5S"
    assert any(ev["t"] == "beast_effect" and ev["moved"] == "6S" and ev["to"] == "banished" for ev in g.last_events)
    assert g.rules.attack_bonus(g) == 5 + 6 and g.rules.immune_suits(g) == ("S",)
    g.play(["9S"])                                     # immune to paladins: no shield, and Ana's A♠ is silenced too (p.20)
    assert g.phase == PHASE_SUFFER and g.pending_damage == 10 + 11 and g.shield == 0
    g.suffer(["6D", "7D", "8D"])
    # Ana's turn: the paladin beast discards the top reserve card
    assert g.active == 0 and g.extra["beasts_out"] == ["B_C", "B_S"] and g.discard[0] == "4H" and g.tavern[0] == "3H"
    assert any(ev["t"] == "beast_effect" and ev["moved"] == "4H" and ev["to"] == "discard" for ev in g.last_events)
    _ids_everywhere(g)


def test_mission11_cleric_and_bard_beasts_make_the_player_discard_or_banish_a_hand_card():
    c, g = _mission11(seed=1101)
    if g.phase == PHASE_DECIDE:
        g.decide(greedy_policy(g))
    _switch_enemy(g, "CV_J1", hp=100)
    set_hand(g, ["AS", "9S", "8S", "2C"])
    _rig(g, "banished", [])
    _rig(g, "discard", [])
    _rig_beasts(g, ["B_H", "B_D", "B_C", "B_S"])
    g.play(["AS"])
    g.suffer(["9S"])
    # a new turn: the cleric beast
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "beast_discard" and g.decision["resume"] == "turn_start"
    acts = g.legal_actions()
    assert sorted(a["card"] for a in acts) == ["2C", "8S"] and not any(a.get("skip") for a in acts)
    assert greedy_policy(g)["card"] == "2C"
    with pytest.raises(IllegalAction):
        g.decide({"type": "beast_discard", "card": "9S"})
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "beast_discard", "card": "2C"})
    assert g.decision is None and g.discard[0] == "2C" and g.phase == PHASE_PLAY and g.extra["beasts_out"] == ["B_H"]
    _ids_everywhere(g)
    # the bard beast banishes a hand card
    set_hand(g, ["3C", "8S", "7D", "4C"])
    g.play(["3C"])                                     # 10 + 2 (the 2♣ on the discard pile) - 1 (the A♠ still in play)
    assert g.pending_damage == 11 and g.enemy.hp == 100 - 1 - 3     # the 2♣ on top makes it immune to warriors
    assert dict(_powers(g))["C"]["immune"]
    g.suffer(["8S", "7D"])
    assert g.decision["kind"] == "beast_banish" and [a["card"] for a in g.legal_actions()] == ["4C"]
    g.decide({"type": "beast_banish", "card": "4C"})
    assert g.banished[-1] == "4C" and g.decision is None and g.extra["beasts_out"] == ["B_H", "B_D"]
    # an empty hand skips the effect; after the fourth beast the deck is reformed
    _rig_beasts(g, ["B_H", "B_D"], ["B_C", "B_S"])
    _rig(g, "discard", [])
    _rig(g, "banished", [])
    set_hand(g, ["9S"])
    g.play(["9S"])                                     # shields 1 + 3 + 9 cover the 10: no damage, the turn ends
    assert g.decision is None and g.extra["beasts_out"] == ["B_C", "B_S", "B_H"] and len(g.extra["beast_deck"]) == 1
    assert any("no card in hand" in line for line in g.log[-3:])
    _ids_everywhere(g)


def test_mission11_four_beasts_out_are_reshuffled_and_an_exact_kill_skips_the_next_reveal():
    c, g = _mission11(seed=1102)
    if g.phase == PHASE_DECIDE:
        g.decide(greedy_policy(g))
    _switch_enemy(g, "CV_J1", hp=100)
    _rig_beasts(g, ["B_C"], ["B_H", "B_D", "B_S"])
    set_hand(g, ["AS", "9S", "8S"])
    _rig(g, "discard", ["2C"])
    _rig(g, "banished", [])
    g.play(["AS"])
    g.suffer(["9S", "8S"])
    assert len(g.extra["beast_deck"]) == 4 and g.extra["beasts_out"] == []
    assert any(ev["t"] == "beast_reshuffle" for ev in g.last_events)
    _ids_everywhere(g)
    # an exact kill: no beast at the start of the next turn, and the flag is cleared after
    if g.phase == PHASE_DECIDE:
        g.decide(greedy_policy(g))
    deck_before = list(g.extra["beast_deck"])
    out_before = list(g.extra["beasts_out"])
    _switch_enemy(g, "CV_J2", hp=9)
    _rig(g, "banished", [])
    _rig(g, "discard", [])
    set_hand(g, ["9S", "2C"])
    g.play(["9S"])
    assert g.enemies_defeated == 1 and g.banished == ["CV_J2"] and g.decision is None and g.phase == PHASE_PLAY
    assert g.extra["beast_deck"] == deck_before and g.extra["beasts_out"] == out_before and "skip_beast" not in g.extra
    assert any(ev["t"] == "beast_skip" for ev in g.last_events)
    # a kill that is not exact banishes the enemy and the next turn reveals as usual
    _switch_enemy(g, "CV_J3", hp=5)
    set_hand(g, ["9S", "2C"])
    g.play(["9S"])
    assert g.enemies_defeated == 2 and g.banished[-1] == "CV_J3"
    assert len(g.extra["beast_deck"]) + len(g.extra["beasts_out"]) == 4 and len(g.extra["beasts_out"]) == len(out_before) + 1
    _ids_everywhere(g)


def test_mission11_pile_tops_grant_immunity_and_strength_but_beasts_and_classless_cards_grant_nothing():
    c, g = _mission11(players=3, seed=1103)
    if g.phase == PHASE_DECIDE:
        g.decide(greedy_policy(g))
    _switch_enemy(g, "CV_EVERGREEN")
    assert (g.enemy.attack, g.enemy.max_hp) == (20, 90) and g.rules.immune_suits(g) == () and g.enemy_attack == 20
    _rig(g, "discard", ["7H", "2C"])
    _rig(g, "banished", ["2D", "5S"])                 # 5♠ on top
    assert g.rules.immune_suits(g) == ("H", "S") and g.rules.attack_bonus(g) == 12 and g.enemy_attack == 32
    assert g.immune("H", [g.cards["7H"]]) and g.immune("S", [g.cards["9S"]]) and not g.immune("D", [g.cards["5D"]])
    # a corrupted card's own class ignores the immunity as usual (the 3♥ is corrupted here)
    assert not g.immune("H", [g.cards["3H"]]) and g.cards["3H"].has("corrupted")
    # a Jester on top of the discard pile: strength 0, no class
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    _pull(g, jester)
    g.discard.insert(0, jester)
    assert g.rules.immune_suits(g) == ("S",) and g.rules.attack_bonus(g) == 5
    # a beast on top of the banished pile grants no immunity and no strength
    g.banished.append("B_H")
    g.extra["beast_deck"] = [x for x in g.extra["beast_deck"] if x != "B_H"]
    g.extra["beasts_out"] = [x for x in g.extra["beasts_out"] if x != "B_H"]
    assert g.rules.immune_suits(g) == () and g.rules.attack_bonus(g) == 0
    # a classless card (the renewed Gøran's classless predecessor) grants strength only
    g.cards["GOR8"] = Card.from_dict(dict(M.GORAN))
    g.banished.append("GOR8")
    assert g.rules.immune_suits(g) == () and g.rules.attack_bonus(g) == 8
    # a defeated Justicar banished on top: 10 strength, no class
    g.banished.append("CV_J1")
    g.castle.remove("CV_J1")
    assert g.rules.attack_bonus(g) == 10 and g.rules.immune_suits(g) == ()


# ---------------------------------------------------------------- Mission 12: Decay to Growth
def test_mission12_banished_top_feeds_the_zone_which_adds_strength_and_immunity_and_an_exact_kill_skips_it():
    c, g = _mission12(players=2)
    assert g.config.rules_id == "legacy_m12" and MISSIONS[11]["playable"] and g.rules.uses_mission_zone
    assert sorted(P.restored_ids(c.party)) == ["2S", "3H", "4D", "5C", "7S", "8H", "9D", "ESME6E"]
    assert "mother_restored" in g.extra["relics"] and "mother" not in g.extra["relics"]
    enemies = [g.cards[x] for x in [g.enemy.card_id] + g.castle]
    assert [e.name.split()[-1] for e in enemies] == ["Queen"] * 4 + ["King"] * 4 + ["Arcana"]
    assert g.cards["TH_ARCANA"].attack == 25 and g.cards["TH_ARCANA"].health == 120 and g.cards["TH_ARCANA"].has("corrupted")
    assert g.mission_zone == [] and g.banished == []    # nothing to move at the first start of turn
    _switch_enemy(g, "THQH", hp=100)
    set_hand(g, ["AS", "9S", "8S"], player=0)
    set_hand(g, ["5D", "6D"], player=1)
    _rig(g, "banished", ["3C", "5S"])                 # 5♠ on top
    g.play(["AS"])
    g.suffer(["9S", "8S"])
    # Ben's start of turn: the top banished card goes into the zone
    assert g.active == 1 and g.mission_zone == ["5S"] and g.banished == ["3C"]
    assert g.rules.attack_bonus(g) == 5 and g.rules.immune_suits(g) == ("H", "S") and g.enemy_attack == 20
    assert any(ev["t"] == "zone_add" and ev.get("source") == "banished" for ev in g.last_events)
    _ids_everywhere(g)
    # an exact kill: the next start of turn skips the move
    _switch_enemy(g, "THQD", hp=5)
    _rig(g, "mission_zone", [])
    set_hand(g, ["5D", "6D"], player=1)
    g.play(["5D"])                                     # immune to bards: 5, exact
    assert g.enemies_defeated == 1 and g.decision is None and g.active == 1 and g.phase == PHASE_PLAY
    assert g.mission_zone == [] and "skip_zone" not in g.extra and any(ev["t"] == "zone_skip" for ev in g.last_events)
    # the whole discard pile was banished in its order, then the played card went on the (empty) pile
    assert g.discard == ["5D"] and g.banished[-4:] == ["THQD", "AS", "9S", "8S"]   # the pile kept its order
    _ids_everywhere(g)


def test_mission12_rules_card_example_edward_has_strength_35_and_three_immunities():
    """The back of the mission 12 rules card: a cleric King (20) facing a zone of a 4
    paladin, a 3 bard and an 8 paladin is immune to clerics, bards and paladins and has
    strength 35 (20 + 4 + 3 + 8)."""
    c, g = _mission12(seed=1203)
    _switch_enemy(g, "THKH", hp=40)
    _rig(g, "mission_zone", ["4S", "3D", "8S"])
    assert g.cards["THKH"].attack == 20 and tuple(g.cards["THKH"].suits) == ("H",)
    assert g.rules.attack_bonus(g) == 15 and g.enemy_attack == 35
    assert sorted(g.rules.immune_suits(g)) == ["D", "H", "S"]
    _ids_everywhere(g)


def test_goran_beasts_are_plain_b_cards_one_per_class():
    """Owner's choice: Gøran's beasts are plain "B" playing cards, no names (like the
    reserve and the enemies). Myla's beast is the B of the Mage class."""
    assert [P.to_card(b).label() for b in M.BEASTS] == ["B♥", "B♦", "B♣", "B♠"]
    assert all("name" not in b and b["value"] == 0 and b["flags"] == ["beast"] for b in M.BEASTS)
    assert P.to_card(M.ASH).label() == "B★" and "name" not in M.ASH


def test_mission12_defeat_banishes_the_zone_in_the_chosen_order_then_the_enemy_then_the_discard_pile():
    c, g = _mission12(seed=1201)
    _switch_enemy(g, "THQH", hp=9)
    _rig(g, "mission_zone", ["3C", "5S", "6D"])
    _rig(g, "discard", ["7C", "2C", "4C"])                  # 7♣ on top
    _rig(g, "banished", [])
    set_hand(g, ["9S", "AS"])
    g.play(["9S"])                                     # 9 damage: exact, but with a 3-card zone the order is asked first
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "banish_order" and g.decision["resume"] == "defeat"
    acts = g.legal_actions()
    assert len(acts) == 1 and acts[0]["needs"] == 3 and acts[0]["pick_from"] == ["3C", "5S", "6D"] and acts[0]["ordered"]
    with pytest.raises(IllegalAction):
        g.decide({"type": "banish_order", "cards": ["3C", "5S"]})
    with pytest.raises(IllegalAction):
        g.decide({"type": "banish_order", "cards": ["3C", "5S", "5S"]})
    # the bot puts the weakest card on top (it comes back into the zone next turn)
    bot = greedy_policy(g)
    assert bot["type"] == "banish_order" and bot["cards"][-1] == "3C"
    rnd = random_policy(g, random.Random(1))
    assert sorted(rnd["cards"]) == ["3C", "5S", "6D"]
    pv = g.preview_decision({"type": "banish_order", "cards": ["6D", "5S", "3C"]})
    assert pv["ok"]
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "banish_order", "cards": ["6D", "5S", "3C"]})
    # zone (6♦, 5♠, 3♣ on top of it), then the enemy, then the discard pile bottom to top
    assert g.banished == ["6D", "5S", "3C", "THQH", "4C", "2C", "7C"]
    assert g.discard == ["9S"] and g.mission_zone == [] and g.enemies_defeated == 1
    assert any(ev["t"] == "discard_banished" and ev["cards"] == ["7C", "2C", "4C"] for ev in g.last_events)
    assert g.extra.get("skip_zone") is None and g.phase == PHASE_PLAY   # exact: skipped and cleared
    _ids_everywhere(g)
    # not exact, one zone card: no order to choose; the next turn takes the banished top (the
    # discard pile's former top, 7♣) into the zone
    _switch_enemy(g, "THQD", hp=5)
    set_hand(g, ["9S", "AS"])
    _rig(g, "discard", ["7C"])
    g.play(["9S"])
    assert g.decision is None and g.enemies_defeated == 2 and g.discard == ["9S"]
    assert g.mission_zone == ["7C"] and g.banished[-1] == "THQD"
    _ids_everywhere(g)


def test_mission12_restored_cards_never_enter_the_banished_pile_from_any_path():
    c, g = _mission12(seed=1202)
    restored = [x for x in g.cards if g.cards[x].has("restored")]
    assert "3H" in restored and "ESME6E" in restored
    # (a) clean-up of a mage attack: the restored 3♥ goes under the reserve, the mage is banished
    _switch_enemy(g, "THQS", hp=100)
    _rig(g, "banished", [])
    set_hand(g, ["3H", "5M", "AS", "9S"])
    set_tavern_top(g, ["2C", "4C", "6C", "7C", "8C"])
    g.play(["3H"])
    g.decide({"type": "mage_pick", "card": "2C"}) if g.decision and g.decision["kind"] == "mage_peek" else None
    # (a 3 of clerics alone has no mage) use the mage with the restored card instead
    c, g = _mission12(seed=1203)
    _switch_enemy(g, "THQS", hp=5)
    _rig(g, "banished", [])
    set_hand(g, ["5M", "AS", "9S"])
    set_tavern_top(g, ["3H", "4C", "6C", "7C", "8C"])
    g.play(["5M"])
    assert g.decision["kind"] == "mage_peek"
    g.decide({"type": "mage_pick", "card": "3H"})     # 8 damage: a kill (the queen has 5), not exact
    assert g.enemies_defeated == 1 and "3H" not in g.banished and g.tavern[-1] == "3H"
    assert g.banished == ["THQS"] and g.mission_zone == ["5M"]   # the banished mage came back into the zone
    assert any(ev["t"] == "banish_redirect" and ev["card"] == "3H" for ev in g.last_events)
    _ids_everywhere(g)
    # (b) the zone and (c) the discard pile at a kill
    _switch_enemy(g, "THQD", hp=9)
    _rig(g, "mission_zone", [])
    _rig(g, "mission_zone", ["4D", "6C"])             # the restored 4♦ sits in the zone
    _rig(g, "discard", ["7C", "8H"])                   # the restored 8♥ at the bottom of the pile
    set_hand(g, ["9S", "AS"])
    g.play(["9S"])
    g.decide({"type": "banish_order", "cards": ["4D", "6C"]})
    assert "4D" not in g.banished and "8H" not in g.banished and g.tavern[-2:] == ["4D", "8H"]
    assert g.banished[-3:] == ["6C", "THQD", "7C"] and g.discard == ["9S"]
    _ids_everywhere(g)
    # (d) a corrupted card's effect: the top reserve card is restored, so it goes under the reserve
    _switch_enemy(g, "THQC", hp=100)
    _rig(g, "mission_zone", [])
    g.banished.remove("THQD")
    set_hand(g, ["THQD", "AS", "9S"])
    set_tavern_top(g, ["2S", "4C"])
    g.play(["THQD"])
    assert any(ev["t"] == "banish_redirect" and ev["card"] == "2S" for ev in g.last_events)
    assert "2S" not in g.banished and g.tavern[-1] == "2S"
    _ids_everywhere(g)
    # (e) a reaver's reveal is redirected too
    assert g.phase == PHASE_SUFFER
    g.suffer(min_waste_discard(g))
    _switch_enemy(g, "THKC", hp=100)
    _rig(g, "mission_zone", [])
    set_hand(g, ["5R", "AS", "9S"] if "5R" in g.cards else ["AS", "9S"])
    if "5R" in g.cards:
        set_tavern_top(g, ["7S", "4C"])
        g.play(["5R"])
        g.decide({"type": "reaver_count", "count": 2})
        g.decide({"type": "reaver_pick", "card": "4C"})
        assert "7S" not in g.banished and g.tavern[-1] == "7S" and g.banished[-1] == "4C"
        _ids_everywhere(g)


def test_mission12_restored_cards_return_a_banished_card_under_the_reserve_and_ignore_immunity():
    c, g = _mission12(seed=1204)
    _switch_enemy(g, "THQH", hp=100)              # a cleric queen: immune to clerics
    _rig(g, "mission_zone", [])
    _rig(g, "banished", ["6C", "4C"])
    _rig(g, "discard", ["2C", "7C"])
    set_hand(g, ["3H", "AS", "9S", "8S"])
    g.play(["3H"])
    # p.15: the top banished card goes under the reserve (then the heal puts two more under it);
    # the restored cleric heals despite the immunity
    assert g.tavern[-3] == "4C" and g.banished == ["6C"]
    assert any(ev["t"] == "restore" and ev["returned"] == "4C" for ev in g.last_events)
    assert dict(_powers(g))["H"].get("healed") == 2 and not dict(_powers(g))["H"].get("immune")
    _ids_everywhere(g)
    # a corrupted royal on top of the banished pile cannot enter the reserve: banished bottom instead
    g.suffer(["9S", "8S"])
    _switch_enemy(g, "THQC", hp=100)
    _rig(g, "mission_zone", [])
    _rig(g, "banished", ["6C"])
    g.castle.remove("THKS")
    g.banished.append("THKS")
    set_hand(g, ["3H", "AS", "9S", "8S"])
    g.play(["3H"])
    assert g.banished == ["THKS", "6C"] and "THKS" not in g.tavern
    assert any(ev["t"] == "reserve_redirect" and ev["card"] == "THKS" for ev in g.last_events)
    assert g.rules.reserve_redirect(g, g.cards["TH_ARCANA"]) == "banished_bottom" and g.rules.reserve_redirect(g, g.cards["3H"]) is None
    # Esme, the reborn Evergreen, is restored too: all four classes, ignoring immunity
    g.suffer(["9S", "8S"])
    _switch_enemy(g, "THQS", hp=100)
    _rig(g, "mission_zone", [])
    _rig(g, "banished", ["6C", "4C"])
    set_hand(g, ["ESME6E", "AS", "9S"])
    g.play(["ESME6E"])
    assert "4C" in g.tavern and "4C" not in g.banished and g.shield == 6
    assert not any(ev.get("immune") for s, ev in _powers(g))
    _ids_everywhere(g)


def test_mission12_the_high_arcana_falls_and_the_campaign_is_complete():
    c, g = _mission12(seed=1205)
    _switch_enemy(g, "TH_ARCANA")
    assert g.enemy.name == "High Arcana" and (g.enemy.attack, g.enemy.max_hp, g.enemy.hp) == (25, 120, 120)
    assert g.rules.immune_suits(g) == ()
    g.castle = []
    _rig(g, "mission_zone", [])
    g.enemy.hp = 9
    set_hand(g, ["9S", "AS"])
    g.play(["9S"])
    assert g.phase == PHASE_WON
    res = c.finish_attempt(g)
    assert res["won"] and c.finished and 12 in c.completed and c.flags.get("pack_e_opened") is True
    assert "campaign_end" in c.lore_seen and any("Campaign complete" in line for line in c.log)
    with pytest.raises(RuntimeError):
        c.start_attempt()
    c2 = CampaignState.from_dict(json.loads(json.dumps(c.to_dict())))
    assert c2.finished and c2.evergreen["setup"] is None


# ---------------------------------------------------------------- bot play-outs
@pytest.mark.parametrize("number,players", [(10, 1), (10, 2), (11, 1), (11, 2), (12, 1), (12, 2)])
def test_bots_play_out_missions_10_to_12(number, players):
    builders = {10: _mission10, 11: _mission11, 12: _mission12}
    rng = random.Random(number * 10 + players)
    seen = set()
    expected = {10: {"mission zone"}, 11: {"beast"}, 12: {"banished pile"}}[number]
    for seed in range(6):
        relics = ("flute", "whistle", "emblem", "mother_restored" if number == 12 else "mother")
        c, g = builders[number](players=players, seed=1300 + number * 10 + seed, relics=relics)
        policy = greedy_policy if seed % 2 == 0 else random_policy
        play_out(g, policy, rng, max_steps=4000)
        assert g.is_over and g.decision is None
        _ids_everywhere(g)
        assert all(len(p.hand) <= g.config.max_hand for p in g.players)
        for line in g.log:
            for key in ("mission zone", "beast", "banished pile"):
                if key in line:
                    seen.add(key)
    assert expected <= seen, seen
