"""Regicide Legacy campaign: missions 1-2, rewards, losses, mercenaries, relics, rules."""
import json
import random

import pytest

from regicide.bots import apply_action, greedy_policy, min_waste_discard, play_out, random_policy
from regicide.campaign import CampaignState
from regicide.campaign import party as P
from regicide.campaign import missions as M
from regicide.campaign.missions import MISSIONS
from regicide.cards import make_card
from regicide.engine import (PHASE_CHOOSE_NEXT, PHASE_DECIDE, PHASE_LOST, PHASE_PLAY, PHASE_SUFFER, PHASE_WON,
                             Game, IllegalAction)
from regicide.rules import GameConfig, classify_combo
from helpers import set_enemy, set_hand, set_tavern_top


def win_quickly(g: Game) -> None:
    """Rig the attempt so the next play wins."""
    g.castle = []
    assert g.enemy is not None
    g.enemy.hp = 1
    g.enemy.max_hp = 1
    hand = g.active_player.hand
    g.play([hand[0]])
    assert g.phase == PHASE_WON


def test_campaign_mission1_is_base_regicide_with_legacy_extras():
    c = CampaignState.new(1, ["Solo"], seed=1)
    g = c.start_attempt(seed=1)
    assert g.config.rules_id == "legacy_m1"
    assert len(g.cards) == 40 + 12
    assert g.solo_jesters == 2
    assert [g.cards[x].rank for x in [g.enemy.card_id] + g.castle] == ["J"] * 4 + ["Q"] * 4 + ["K"] * 4
    assert c.attempts_on(1) == 1


def first_valid_assignment(c: CampaignState, step: dict) -> dict:
    """A legal sticker assignment for a choice_classes step (first permutation that fits)."""
    import itertools
    cards, classes = step["cards"], step["classes"]
    for perm in itertools.permutations(classes, len(cards)):
        if all(s not in P.find(c.party, cid)["suits"] for cid, s in zip(cards, perm)):
            return dict(zip(cards, perm))
    raise AssertionError("no legal assignment")


def resolve_choices(c: CampaignState) -> None:
    """Resolve pending reward choices like a player who always takes the first option."""
    while c.pending:
        step = c.pending_choice()
        if step["kind"] == "choice_classes":
            c.resolve_choice(first_valid_assignment(c, step))
            continue
        assert step["options"], step
        c.resolve_choice(step["options"][0])


def test_mission1_win_applies_rewards_and_unlocks_mission2():
    c = CampaignState.new(1, ["Solo"], seed=2)
    g = c.start_attempt(seed=2)
    assert g.enemy.name.endswith("Justicar") and g.enemy.name.split()[0] in ("Cleric", "Bard", "Warrior", "Paladin")
    win_quickly(g)
    res = c.finish_attempt(g)
    assert res["won"]
    assert c.mission == 2 and c.completed == [1]
    assert "flute" in c.relics
    arc = P.find(c.party, "ARC25")
    assert arc is not None and arc["name"] == "High Arcana" and arc["suits"] == []
    # reward card: "Open pack C and corrupt a character in your party" -> random (pack C's
    # race and feature draws collapse to a random strength and card in a themeless deck)
    assert len(c.corrupted) == 1 and not c.pending
    corrupted = P.find(c.party, c.corrupted[0])
    assert "corrupted" in corrupted["flags"] and corrupted["rank"] in "23456789"
    assert any("corrupted" in line for line in c.log)
    assert res["rewards"] and any("corrupted" in line for line in res["rewards"])


def test_mission2_hydras_recycle_on_imperfect_kill_and_banish_on_exact():
    c = CampaignState.new(1, ["Solo"], seed=3)
    g = c.start_attempt(seed=3)
    win_quickly(g)
    c.finish_attempt(g)
    resolve_choices(c)
    g = c.start_attempt(seed=4)
    assert g.config.rules_id == "legacy_m2"
    assert g.enemy.name == "Hydra Head" and len(g.enemy.suits) == 2 and g.enemy.max_hp == 20
    assert len(g.castle) == 5
    assert "ARC25" in g.tavern or "ARC25" in g.players[0].hand
    # imperfect kill -> bottom of the castle at full health
    first = g.enemy.card_id
    g.enemy.hp = 5
    arc = "ARC25"
    if arc not in g.players[0].hand:
        g.tavern.remove(arc)
        g.players[0].hand.append(arc)
    g.play([arc])
    assert g.castle[-1] == first and g.enemy.card_id != first
    assert first not in g.banished
    # exact kill -> banished
    g.enemy.hp = 7
    hand = g.players[0].hand
    seven = [x for x in hand if g.cards[x].value == 7 and not g.immune(g.cards[x].suits[0])]
    if not seven:
        g.tavern.remove("7H") if "7H" in g.tavern else None
        hand.append("7H")
        seven = ["7H"]
        if g.immune("H"):
            g.enemy.hp = 7  # hearts immune: damage still 7
    target = g.enemy.card_id
    g.play([seven[0]])
    assert target in g.banished


def test_loss_earns_coins_opens_pack_m_and_mercenaries_join_next_attempt():
    c = CampaignState.new(1, ["Solo"], seed=5)
    g = c.start_attempt(seed=5)
    g._lose("test")
    res = c.finish_attempt(g)
    assert not res["won"] and res["m_box_opened_now"] and c.coins == 1 and c.losses_on(1) == 1
    assert res["earned"] == 1 and c.swaps_allowed
    g = c.start_attempt(seed=6)
    assert not c.swaps_allowed
    g._lose("test")
    res = c.finish_attempt(g)
    # rulebook p.25: each failure GAINS coins equal to the failures so far: 1 -> 3 -> 6 -> 10
    assert res["earned"] == 2 and c.coins == 3
    offers = c.hireable()
    assert offers and any(o["affordable"] for o in offers)
    cheap = [o for o in offers if o["cost"] <= 1][0]
    c.hire(cheap["id"])
    with pytest.raises(ValueError):
        c.hire(cheap["id"])
    assert c.coins == 2
    g = c.start_attempt(seed=7)
    merc_ids = [x for x in g.cards if x.startswith("M")]
    assert merc_ids, "hired mercenary should be in the reserve"
    # hired mercenaries stay for the next attempt of the same mission; unspent coins carry
    g._lose("test")
    res = c.finish_attempt(g)
    assert c.mercenaries == [cheap["id"]] and res["earned"] == 3 and c.coins == 5
    assert not any(x.startswith("M") for x in [cd["id"] for cd in c.party])
    g = c.start_attempt(seed=8)
    assert [x for x in g.cards if x.startswith("M")], "kept mercenary rejoins the reserve"
    win_quickly(g)
    c.finish_attempt(g)
    # on success every mercenary returns to the box and coins do not carry to the next mission
    assert c.mercenaries == [] and c.coins == 0 and c.mission == 2
    resolve_choices(c)
    g = c.start_attempt(seed=9)
    assert not [x for x in g.cards if x.startswith("M")]


def test_mercenary_swap_same_cost_after_failure_only():
    c = CampaignState.new(1, ["Solo"], seed=5)
    c.m_box_opened = True
    c.coins = 3
    c.hire("merc_12H")
    # no failure yet in this mission: swapping is not on offer
    assert c.swappable("merc_12H") == []
    with pytest.raises(ValueError):
        c.swap("merc_12H", "merc_12C")
    g = c.start_attempt(seed=5)
    g._lose("test")
    c.finish_attempt(g)
    assert c.swaps_allowed and c.coins == 3
    names = {o["id"] for o in c.swappable("merc_12H")}
    assert "merc_12C" in names and "merc_25S" in names  # same cost (1), not hired
    assert "merc_12H" not in names and "merc_19_1" not in names  # itself; cost 3
    with pytest.raises(ValueError):
        c.swap("merc_12H", "merc_19_1")  # different cost
    with pytest.raises(ValueError):
        c.swap("merc_19_1", "merc_19_2")  # not hired
    c.swap("merc_12H", "merc_12C")
    assert c.mercenaries == ["merc_12C"] and c.coins == 3  # swaps are free
    c.hire("merc_12H")
    with pytest.raises(ValueError):
        c.swap("merc_12C", "merc_12H")  # target already hired
    # a second swap of the same slot is still allowed until the next attempt starts
    c.swap("merc_12C", "merc_12D")
    g = c.start_attempt(seed=6)
    assert not c.swaps_allowed and c.swappable("merc_12D") == []
    assert {x for x in g.cards if x.startswith("M12")} == {"M12D", "M12H"}
    # round trip through the save format keeps the flag and the hires
    d = c.to_dict()
    c2 = CampaignState.from_dict(d)
    assert c2.mercenaries == c.mercenaries and c2.swaps_allowed is False and c2.coins == c.coins
    # a save from before the rulebook coin rule (no swaps_allowed field) is migrated:
    # coins become the rulebook total (1+2+... per failure) minus what is hired, and
    # the swap entitlement is granted when the mission has been failed
    d.pop("swaps_allowed")
    old = CampaignState.from_dict(d)
    assert old.swaps_allowed is True and old.coins == c.coins  # already at the rulebook total
    legacy = {"slot": "s", "name": "Old", "players": 1, "names": ["Solo"], "mission": 1, "completed": [],
              "attempts": {"1": 3}, "losses": {"1": 2}, "coins": 2, "m_box_opened": True, "mercenaries": [],
              "party": c.party, "relics": [], "corrupted": [], "flags": {}, "pending": [], "log": [],
              "reveal_all": False, "seed": 1, "rng_calls": 0, "finished": False, "lore_seen": [],
              "last_played": "", "version": 1}
    m = CampaignState.from_dict(legacy)
    assert m.coins == 3 and m.swaps_allowed is True  # 1 + 2 under the rulebook, nothing spent
    legacy["mercenaries"] = ["merc_19_1"]  # cost 3 hired under the old rule
    legacy["coins"] = 0
    m = CampaignState.from_dict(legacy)
    assert m.coins == 0  # 3 earned, 3 spent: never below what the save held
    legacy["losses"] = {"1": 0}
    legacy["attempts"] = {"1": 1}
    legacy["mercenaries"] = []
    m = CampaignState.from_dict(legacy)
    assert m.coins == 0 and m.swaps_allowed is False


def test_extra_jester_mercenary_adds_solo_power():
    c = CampaignState.new(1, ["Solo"], seed=8)
    c.m_box_opened = True
    c.coins = 10
    c.hire("merc_jester_1")
    g = c.start_attempt(seed=8)
    assert g.solo_jesters == 3


def test_solo_jester_attack_mode():
    c = CampaignState.new(1, ["Solo"], seed=9)
    g = c.start_attempt(seed=9)
    set_enemy(g, "J", "C")
    acts = [a for a in g.legal_actions() if a["type"] == "solo_jester"]
    assert sorted(a["suit"] for a in acts) == ["C", "D", "H", "S"]
    with pytest.raises(IllegalAction):
        g.use_solo_jester()  # a class must be chosen
    g.use_solo_jester({"suit": "C"})
    assert g.enemy.hp == 20 - 16  # 8 doubled, immunity ignored
    assert g.solo_jesters == 1
    assert g.phase == PHASE_SUFFER
    # the jester is on the table with the clubs class; when the enemy dies it is removed from the game
    assert any("X1" in p.card_ids for p in g.plays)
    from regicide.bots import min_waste_discard
    g.suffer(min_waste_discard(g))
    assert g.phase == PHASE_PLAY
    if not g.players[0].hand:
        g.players[0].hand.append(g.tavern.pop(0))
    g.enemy.hp = 1
    g.play([g.players[0].hand[0]])
    assert "X1" in g.set_aside and "X1" not in g.banished and "X1" not in g.discard


def test_multiplayer_jester_claim_attack_ignores_immunity_once():
    c = CampaignState.new(3, ["A", "B", "C"], seed=10)
    g = c.start_attempt(seed=10)
    set_enemy(g, "J", "C")
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_hand(g, [jester, "4H"], player=0)
    set_hand(g, ["5C", "2D", "3D"], player=2)
    g.play([jester])
    assert g.phase == PHASE_CHOOSE_NEXT and g.extra.get("jester_claim")
    g.choose_next(2)
    assert g.active == 2 and g.phase == PHASE_PLAY
    assert not g.immune("C")       # claimed Jester: this attack ignores immunity
    g.play(["5C"])
    assert g.enemy.hp == 10        # doubled
    assert g.immune("C")           # only for that attack
    assert not g.immunity_cancelled
    g.suffer(["2D", "3D"]) if g.phase == PHASE_SUFFER else None


def test_feign_death_only_at_hand_limit():
    c = CampaignState.new(1, ["Solo"], seed=11)
    g = c.start_attempt(seed=11)
    set_enemy(g, "K", "H")
    set_hand(g, ["2C", "2D", "2S", "3C", "3D", "3S", "4C", "4D"])  # 8 cards = limit, total 23 > 20? no: 2+2+2+3+3+3+4+4=23
    g.play(["2C"])  # now 7 cards, total 21 >= 20 -> can pay normally
    assert g.phase == PHASE_SUFFER
    assert not g.feign_death_available()
    g2 = c.start_attempt(seed=12)
    set_enemy(g2, "K", "H")
    g2.solo_jesters = 0
    set_hand(g2, ["2C", "2D", "2S", "3C", "3D", "3S", "4C", "9D"])
    g2.play(["9D"])  # draws up to the limit again (diamonds) -> hand full but weak
    if g2.phase == PHASE_SUFFER and len(g2.players[0].hand) == 8 and g2.hand_defence_value() < g2.pending_damage:
        assert g2.feign_death_available()
        with pytest.raises(IllegalAction):
            g2.suffer(g2.players[0].hand[:3])
        g2.suffer(list(g2.players[0].hand))
        assert g2.phase == PHASE_PLAY and g2.players[0].hand == []


def test_corrupted_card_banishes_top_of_reserve_and_bypasses_immunity():
    c = CampaignState.new(1, ["Solo"], seed=13)
    P.add_flag(c.party, "5C", "corrupted")
    g = c.start_attempt(seed=13)
    set_enemy(g, "J", "C")
    set_hand(g, ["5C", "9D"])
    top = g.tavern[0]
    g.play(["5C"])
    assert g.banished == [top]
    assert g.enemy.hp == 10  # corrupted clubs double despite immunity
    assert P.to_card(P.find(c.party, "5C")).has("corrupted")


def test_kinfolk_flute_store_and_play():
    c = CampaignState.new(1, ["Solo"], seed=14)
    c.relics.append("flute")
    g = c.start_attempt(seed=14)
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "3D", "9S", "7H", "6H"])
    acts = [a for a in g.legal_actions() if a.get("name") == "flute_store"]
    assert sorted(a["card"] for a in acts) == ["3C", "3D"]
    g.special(acts[0])
    assert g.extra["flute"] == [acts[0]["card"]]
    assert not [a for a in g.legal_actions() if a.get("name") == "flute_store"]  # once per turn
    other = "3D" if acts[0]["card"] == "3C" else "3C"
    plays = g.legal_plays()
    assert sorted([acts[0]["card"], other]) in [sorted(p) for p in plays]
    g.play([acts[0]["card"], other])
    assert g.extra["flute"] == []
    assert g.enemy.hp == 20 - 12 or g.enemy.hp == 20 - 6
    # save / load keeps the flute
    d = json.loads(json.dumps(g.to_dict()))
    g2 = Game.from_dict(d)
    assert g2.extra == g.extra


def test_solo_flute_cards_only_join_kinfolk_attacks_and_store_at_any_time():
    from regicide.engine import IllegalAction
    c = CampaignState.new(1, ["Solo"], seed=14)
    c.relics.append("flute")
    g = c.start_attempt(seed=14)
    set_enemy(g, "J", "H")
    set_hand(g, ["4C", "9S", "7H", "6H", "2D"])
    g.special({"type": "special", "name": "flute_store", "card": "4C"})
    assert g.extra["flute"] == ["4C"]
    # "While forming a Kinfolk Attack you may play cards from here": never alone
    assert ["4C"] not in g.legal_plays()
    with pytest.raises(IllegalAction):
        g.play(["4C"])
    # a 2 cannot join the flute while a 4 is there (different strength)
    assert not [a for a in g.legal_actions() if a.get("name") == "flute_store"]
    g.play(["9S"])
    assert g.phase == "suffer"
    # the flute was used this turn already: nothing more to store this turn
    assert not [a for a in g.legal_actions() if a.get("name") == "flute_store"]
    g.suffer(["7H"])
    # next turn, during the suffer step ("at any time"), a 4 may still be stored
    set_enemy(g, "J", "D")
    set_hand(g, ["4D", "9H", "6C", "3S"])
    g.play(["6C"])
    assert g.phase == "suffer" and g.pending_damage == 10
    acts = [a for a in g.legal_actions() if a.get("name") == "flute_store"]
    assert [a["card"] for a in acts] == ["4D"]
    g.special(acts[0])
    assert g.extra["flute"] == ["4C", "4D"] and g.phase == "suffer"
    g.suffer(["9H", "3S"])
    # both flute cards may now form a kinfolk attack together (or with a 4 from hand)
    assert sorted(["4C", "4D"]) in [sorted(p) for p in g.legal_plays()]


# ---------------------------------------------------------------- Kinfolk Flute, 2+ players
def _flute_game(players=2, seed=20):
    names = ["Ana", "Ben", "Cy", "Dee"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.relics.append("flute")
    g = c.start_attempt(seed=seed)
    set_enemy(g, "J", "H")
    return c, g


def _adds(g):
    return sorted(tuple(sorted(a["card_ids"])) for a in g.legal_actions() if a["type"] == "flute_add")


def test_flute_other_player_adds_a_kinfolk_card_and_abilities_resolve_on_the_total():
    c, g = _flute_game()
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3D", "3H", "7C", "AS"], player=1)
    g.play(["3C"])
    # step 1 is done, step 2 waits for Ben; Ana stays the active player
    assert g.phase == PHASE_DECIDE and g.active == 0 and g.deciding == 1
    assert g.decision == {"kind": "flute_add", "player": 1, "play_index": 0, "strength": 3, "queue": []}
    assert g.enemy.hp == 20 and g.plays[0].card_ids == ["3C"]
    assert any(ev["t"] == "decide" for ev in g.last_events)
    assert _adds(g) == [("3D",), ("3D", "3H"), ("3H",)]
    acts = g.legal_actions()
    assert [a for a in acts if a["type"] == "flute_pass" and a.get("skip")]
    assert all(a["type"] in ("flute_add", "flute_pass") for a in acts)
    # nothing else is possible meanwhile
    assert g.legal_plays() == [] and not g.can_yield()
    with pytest.raises(IllegalAction):
        g.play(["9S"])
    with pytest.raises(IllegalAction):
        g.flute_add(["7C"])          # wrong strength
    with pytest.raises(IllegalAction):
        g.flute_add(["AS"])          # companions never join a kinfolk attack
    with pytest.raises(IllegalAction):
        g.flute_add([])
    g.flute_add(["3D"])
    assert g.decision is None and g.phase == PHASE_SUFFER and g.active == 0
    play = g.plays[0]
    assert play.card_ids == ["3C", "3D"] and play.value == 6 and set(play.suits) == {"C", "D"}
    assert g.enemy.hp == 20 - 12                       # clubs double the combined strength
    assert "3D" not in g.players[1].hand
    # diamonds drew 6 for the combined strength, round robin from the attacker
    assert len(g.players[0].hand) == 2 + 3 and len(g.players[1].hand) == 3 + 3
    assert g.pending_damage == 10                      # the attacker alone suffers
    g.suffer(min_waste_discard(g))
    assert g.phase == PHASE_PLAY and g.active == 1
    # at clean-up the added card leaves with the rest of the attack
    g.enemy.hp = 1
    g.play([g.players[1].hand[0]])
    assert "3C" in g.discard and "3D" in g.discard


def test_flute_pass_resolves_the_attack_as_formed():
    c, g = _flute_game()
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3D", "7C"], player=1)
    g.play(["3C"])
    assert g.phase == PHASE_DECIDE
    g.flute_pass()
    assert g.phase == PHASE_SUFFER and g.decision is None
    assert g.enemy.hp == 14 and g.plays[0].card_ids == ["3C"] and "3D" in g.players[1].hand
    assert any(ev["t"] == "flute_pass" for ev in g.last_events)


def test_flute_is_skipped_when_nobody_can_add():
    # no card of that strength in any other hand
    c, g = _flute_game()
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["4D", "7C", "AS"], player=1)
    g.play(["3C"])
    assert g.phase == PHASE_SUFFER and g.decision is None and g.enemy.hp == 14
    # the attack is already at the cap (5 + 5 = 10; doubled it kills the Justicar outright)
    c, g = _flute_game(seed=21)
    set_hand(g, ["5C", "5S", "9S", "8S"], player=0)
    set_hand(g, ["5D", "5H"], player=1)
    g.play(["5C", "5S"])
    assert g.decision is None and g.enemies_defeated == 1 and g.players[1].hand == ["5D", "5H"]
    # a 6 cannot grow into a kinfolk attack (6 + 6 > 10)
    c, g = _flute_game(seed=22)
    set_hand(g, ["6C", "9S", "8S"], player=0)
    set_hand(g, ["6D"], player=1)
    g.play(["6C"])
    assert g.phase == PHASE_SUFFER and g.decision is None
    # animal attacks are not kinfolk attacks, whatever the others hold
    c, g = _flute_game(seed=23)
    set_hand(g, ["AS", "5C", "9S", "8S"], player=0)
    set_hand(g, ["5D", "AH"], player=1)
    g.play(["AS", "5C"])
    assert g.phase == PHASE_SUFFER and g.decision is None
    g2 = c.start_attempt(seed=24)
    set_enemy(g2, "J", "H")
    set_hand(g2, ["AS", "9S", "8S"], player=0)
    set_hand(g2, ["AH", "AD"], player=1)
    g2.play(["AS"])
    assert g2.phase == PHASE_SUFFER and g2.decision is None
    # without the relic nothing happens either
    c = CampaignState.new(2, ["Ana", "Ben"], seed=25)
    g = c.start_attempt(seed=25)
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3D"], player=1)
    g.play(["3C"])
    assert g.phase == PHASE_SUFFER and g.decision is None


def test_flute_subsets_respect_the_ten_cap_and_jesters_never_join():
    c, g = _flute_game(players=3, seed=26)   # three players: one Jester in the reserve
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_hand(g, ["5C", "9S", "8S"], player=0)
    set_hand(g, ["5D", "5H", jester], player=1)
    set_hand(g, ["7C"], player=2)
    g.play(["5C"])
    # Cy stays queued: whether he can add is only known once Ben has decided
    assert g.phase == PHASE_DECIDE and g.deciding == 1 and g.decision["queue"] == [2]
    assert _adds(g) == [("5D",), ("5H",)]  # 5 + 5 + 5 would be 15
    with pytest.raises(IllegalAction):
        g.flute_add(["5D", "5H"])
    with pytest.raises(IllegalAction):
        g.flute_add([jester])
    g.flute_add(["5H"])
    # 5♣ + 5♥ = 10, doubled = 20: the Justicar (20) dies exactly and goes on the reserve;
    # Cy (no 5) was skipped and Ana, who defeated it, plays on
    assert g.decision is None and g.enemies_defeated == 1 and g.tavern[0] == "JH"
    assert g.phase == PHASE_PLAY and g.active == 0 and "5H" in g.discard and "5C" in g.discard


def test_flute_asks_players_clockwise_and_skips_those_who_cannot_add():
    c, g = _flute_game(players=3, seed=27)
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["7C", "AS"], player=1)              # Ben has no 3: skipped
    set_hand(g, ["3D", "3H", "4S"], player=2)
    g.play(["3C"])
    assert g.phase == PHASE_DECIDE and g.deciding == 2 and g.decision["queue"] == []
    g.flute_add(["3D", "3H"])
    assert g.phase == PHASE_SUFFER and g.plays[0].value == 9 and g.enemy.hp == 20 - 18
    # everyone eligible is asked in turn; the queue shrinks as totals grow
    c, g = _flute_game(players=3, seed=28)
    set_hand(g, ["2C", "9S", "8S"], player=0)
    set_hand(g, ["2D", "7C"], player=1)
    set_hand(g, ["2H", "2S", "4S"], player=2)
    g.play(["2C"])
    assert g.deciding == 1 and g.decision["queue"] == [2]
    g.flute_add(["2D"])
    assert g.phase == PHASE_DECIDE and g.deciding == 2 and g.decision["queue"] == []
    assert g.plays[0].value == 4 and _adds(g) == [("2H",), ("2H", "2S"), ("2S",)]
    g.flute_pass()
    assert g.phase == PHASE_SUFFER and g.plays[0].card_ids == ["2C", "2D"] and g.enemy.hp == 20 - 8
    # a later player drops out of the queue once the cap is reached
    c, g = _flute_game(players=3, seed=29)
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3D", "3H"], player=1)
    set_hand(g, ["3S", "4S"], player=2)
    g.play(["3C"])
    assert g.deciding == 1 and g.decision["queue"] == [2]
    g.flute_add(["3D", "3H"])                         # 9: a fourth 3 would make 12
    assert g.phase == PHASE_SUFFER and g.decision is None and "3S" in g.players[2].hand


def test_flute_decision_survives_a_save_round_trip():
    c, g = _flute_game(players=3, seed=30)
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3D", "7C"], player=1)
    set_hand(g, ["3S", "4S"], player=2)
    g.play(["3C"])
    d = json.loads(json.dumps(g.to_dict()))
    assert d["phase"] == PHASE_DECIDE and d["decision"]["player"] == 1 and d["decision"]["queue"] == [2]
    g2 = Game.from_dict(d)
    assert g2.phase == PHASE_DECIDE and g2.decision == g.decision and g2.deciding == 1
    assert g2.legal_actions() == g.legal_actions()
    assert sorted(g2.all_card_ids()) == sorted(g2.cards)
    g2.flute_add(["3D"])
    g.flute_add(["3D"])
    assert g2.deciding == 2 and g2.to_dict() == g.to_dict()
    g2.flute_add(["3S"])
    assert g2.phase == PHASE_SUFFER and g2.plays[0].value == 9
    # old saves without the field load as "no decision pending"
    d.pop("decision")
    d["phase"] = PHASE_PLAY
    assert Game.from_dict(d).decision is None


def test_flute_added_corrupted_card_banishes_and_ignores_immunity():
    c = CampaignState.new(2, ["Ana", "Ben"], seed=31)
    c.relics.append("flute")
    P.add_flag(c.party, "3D", "corrupted")
    g = c.start_attempt(seed=31)
    set_enemy(g, "J", "D")                           # immune to diamonds
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3D", "7C"], player=1)
    g.play(["3C"])
    assert g.phase == PHASE_DECIDE and g.banished == []
    top = g.tavern[0]
    g.flute_add(["3D"])
    assert g.banished == [top]                        # corrupted newcomer banishes on entering play
    assert any(ev["t"] == "corrupt_banish" for ev in g.last_events)
    drawn = [ev for ev in g.last_events if ev["t"] == "power" and ev["suit"] == "D"]
    assert drawn and not drawn[0].get("immune") and len(drawn[0]["drawn"]) == 6
    assert g.enemy.hp == 20 - 12


def test_flute_preview_assumes_nobody_adds():
    c, g = _flute_game(seed=32)
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3D", "7C"], player=1)
    pv = g.preview_play(["3C"])
    assert pv["ok"] and pv["decision"] and pv["damage"] == 6 and pv["enemy_hp_after"] == 14
    assert pv["phase_after"] == PHASE_SUFFER
    assert g.phase == PHASE_PLAY and g.decision is None   # the preview did not touch the game
    pv2 = g.preview_play(["9S"])
    assert pv2["ok"] and not pv2["decision"] and pv2["damage"] == 9


def test_legacy_kinfolk_is_any_number_of_equal_strength_cards():
    twos = [make_card("2", s) for s in "HDCS"] + [make_card("2", "H", id="M25H", name="2/5", flags=("twofive",))]
    assert classify_combo(twos)[0] == ""                                   # base game: at most four
    assert classify_combo(twos, strength=lambda c: 2 if c.has("twofive") else c.value, max_cards=None) == ("set", None)
    c = CampaignState.new(1, ["Solo"], seed=33)
    c.m_box_opened = True
    c.coins = 1
    c.hire("merc_25H")
    g = c.start_attempt(seed=33)
    set_enemy(g, "J", "H")
    set_hand(g, ["2C", "2D", "2H", "2S", "M25H", "9S", "8S", "7S"])
    five = ["2C", "2D", "2H", "2S", "M25H"]
    assert g.check_play(five) == (True, "set")
    assert sorted(five) in [sorted(p) for p in g.legal_plays()]
    assert g.check_play(["3C", "M25H"])[0] is False                       # 3 and 2 differ in strength
    g.play(five)
    played = [ev for ev in g.last_events if ev["t"] == "play"][0]
    assert played["value"] == 10 and played["kind"] == "set"
    assert g.enemies_defeated == 1 and g.tavern[0] == "JH"                 # 10 doubled: exact kill


@pytest.mark.parametrize("players", [2, 3])
def test_bots_play_out_legacy_games_with_the_flute(players):
    offered = 0
    added = 0
    rng = random.Random(players)
    for seed in range(8):
        c = CampaignState.new(players, seed=seed)
        c.relics.append("flute")
        g = c.start_attempt(seed=seed)
        play_out(g, greedy_policy if seed % 2 == 0 else random_policy, rng)
        assert g.is_over and g.decision is None
        assert sorted(g.all_card_ids()) == sorted(g.cards)
        offered += sum(1 for line in g.log if line.startswith("Kinfolk Flute:"))
        added += sum(1 for line in g.log if "(Kinfolk Flute)" in line)
    assert offered > 0 and added > 0


def test_greedy_bot_adds_to_the_flute_attack_only_to_finish_the_enemy():
    c, g = _flute_game(seed=34)
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3D", "3H", "7C"], player=1)
    g.play(["3C"])
    assert greedy_policy(g)["type"] == "flute_pass"           # 12 or 18 damage: the Justicar survives
    g.enemy.hp = 12
    act = greedy_policy(g)
    assert act["type"] == "flute_add" and act["card_ids"] == ["3D"]   # one 3 kills it exactly
    apply_action(g, act)
    assert g.enemies_defeated == 1 and g.tavern[0] == "JH"


def test_campaign_roundtrip_and_bot_can_play_attempts():
    c = CampaignState.new(2, ["A", "B"], seed=15)
    for _ in range(3):
        g = c.start_attempt()
        play_out(g, greedy_policy)
        c.finish_attempt(g)
        resolve_choices(c)
        if c.mission == 2:
            break
    d = json.loads(json.dumps(c.to_dict()))
    c2 = CampaignState.from_dict(d)
    assert c2.to_dict() == c.to_dict()


def test_random_legacy_games_keep_invariants():
    from regicide.bots import random_policy
    rng = random.Random(3)
    for seed in range(25):
        c = CampaignState.new(1 + seed % 3, seed=seed)
        c.relics.append("flute")
        P.add_flag(c.party, "7D", "corrupted")
        g = c.start_attempt(seed=seed)
        play_out(g, random_policy, rng)
        ids = g.all_card_ids() + g.extra.get("flute", [])
        assert sorted(ids) == sorted(g.cards)
        assert all(g.cards[x].is_jester for x in g.set_aside)


def test_mission_table_is_complete():
    assert [m["number"] for m in MISSIONS] == list(range(1, 13))
    assert all(m["title"] and m["summary"] for m in MISSIONS)


def test_corruption_is_random_one_strength_each_and_skips_special_cards():
    rng = random.Random(1)
    party = P.starting_party()
    P.add_card(party, dict(M.GORAN))                       # no class: never corrupted
    P.add_card(party, dict(M.ASH))                         # beast: never
    P.add_card(party, {"id": "5R", "rank": "5", "suits": ["R"], "value": 5, "name": "Harore", "flags": []})
    P.add_card(party, {"id": "3R", "rank": "3", "suits": ["R"], "value": 3, "name": "Oaken", "flags": []})
    cands = P.corruption_candidates(party)
    assert "5R" in cands and "3R" not in cands             # Harore stays, Oaken is a visitor
    assert "GOR8" not in cands and "B_ASH" not in cands and "AH" not in cands and "10S" not in cands
    picked = []
    for _ in range(8):
        tgt = P.pick_corruption_target(party, rng)
        assert tgt is not None
        P.add_flag(party, tgt, "corrupted")
        picked.append(tgt)
    ranks = [P.find(party, x)["rank"] for x in picked]
    assert len(set(ranks)) == 8 and set(ranks) == set("23456789")
    assert P.pick_corruption_target(party, rng) is None    # one of each strength, then no more
    # every strength is drawn with equal chance, however many cards share it
    counts = {}
    for seed in range(300):
        tgt = P.pick_corruption_target(P.starting_party(), random.Random(seed))
        counts[P.find(P.starting_party(), tgt)["rank"]] = counts.get(P.find(P.starting_party(), tgt)["rank"], 0) + 1
    assert set(counts) == set("23456789") and min(counts.values()) > 15


def test_mercenary_costs_match_the_cards():
    from regicide.campaign.mercenaries import by_id
    assert by_id("merc_12H")["cost"] == 1 and by_id("merc_25H")["cost"] == 1
    assert by_id("merc_19_1")["cost"] == 3 and by_id("merc_ace_1")["cost"] == 3
    assert by_id("merc_jester_1")["cost"] == 5


def win_exactly(g: Game) -> None:
    """Rig the attempt so the next play wins with exact damage (mission 2 needs it)."""
    g.castle = []
    assert g.enemy is not None
    for cid in list(g.active_player.hand):
        info = g.preview_play([cid])
        if info.get("ok") and info.get("damage", 0) > 0:
            g.enemy.hp = info["damage"]
            g.enemy.max_hp = info["damage"]
            g.play([cid])
            assert g.phase == PHASE_WON, g.phase
            return
    raise AssertionError("no card can deal damage")


def test_mission2_rewards_are_random_corruption_and_class_sticker_assignment():
    c = CampaignState.new(1, ["Solo"], seed=21)
    g = c.start_attempt(seed=21)
    win_quickly(g)
    c.finish_attempt(g)
    resolve_choices(c)
    assert c.mission == 2 and P.find(c.party, "ARC25") is not None
    g = c.start_attempt(seed=22)
    heads = [g.cards[x] for x in [g.enemy.card_id] + g.castle]
    assert len(heads) == 6 and all(h.name == "Hydra Head" and len(h.suits) == 2 for h in heads)
    assert len({tuple(sorted(h.suits)) for h in heads}) == 6  # every pair of classes once
    win_exactly(g)
    res = c.finish_attempt(g)
    assert res["won"] and c.mission == 3
    # no mission 2 card removes the High Arcana
    assert P.find(c.party, "ARC25") is not None
    kinds = [s["kind"] for s in c.pending]
    assert kinds == ["choice_classes"]
    # second corruption: random, a different strength than the first
    assert len(c.corrupted) == 2
    assert P.find(c.party, c.corrupted[0])["rank"] != P.find(c.party, c.corrupted[1])["rank"]
    step = c.pending_choice()
    cards = step["cards"]
    assert [P.find(c.party, x)["rank"] for x in cards] == ["3", "5", "7", "9"]
    assert step["classes"] == ["H", "D", "C", "S"]
    # the player assigns: one sticker each, each class once, never the card's own class
    own = {cid: P.find(c.party, cid)["suits"][0] for cid in cards}
    bad = {cid: own[cid] for cid in cards}
    with pytest.raises(ValueError):
        c.resolve_choice(bad)
    with pytest.raises(ValueError):
        c.resolve_choice({cards[0]: "H"})  # incomplete
    good = first_valid_assignment(c, step)
    with pytest.raises(ValueError):
        dup = dict(good)
        dup[cards[1]] = good[cards[0]]
        c.resolve_choice(dup)  # a class used twice
    with pytest.raises(ValueError):
        c.resolve_choice("3H")  # not a mapping
    line = c.resolve_choice(good)
    assert line.startswith("Class stickers") and not c.pending
    for cid, s in good.items():
        suits = P.find(c.party, cid)["suits"]
        assert len(suits) == 2 and s in suits and s != own[cid]
    # a two-class card carries both classes into the next attempt
    d = CampaignState.from_dict(c.to_dict())
    assert P.find(d.party, cards[0])["suits"] == P.find(c.party, cards[0])["suits"]


def test_coins_accumulate_one_three_six_ten_and_hires_persist_over_several_attempts():
    c = CampaignState.new(1, ["Solo"], seed=40)
    totals = []
    for seed in (41, 42, 43, 44):
        g = c.start_attempt(seed=seed)
        g._lose("test")
        res = c.finish_attempt(g)
        totals.append((res["earned"], c.coins))
    assert totals == [(1, 1), (2, 3), (3, 6), (4, 10)]
    c.hire("merc_12H")
    c.hire("merc_19_1")
    assert c.coins == 6 and c.mercenaries == ["merc_12H", "merc_19_1"]
    for seed in (45, 46):
        g = c.start_attempt(seed=seed)
        assert {x for x in g.cards if x.startswith("M")} == {"M12H", "M19_1"}
        g._lose("test")
        c.finish_attempt(g)
        assert c.mercenaries == ["merc_12H", "merc_19_1"]
    assert c.coins == 6 + 5 + 6  # the 5th and 6th failures add 5 and 6
    assert "2 mercenaries stay on." in c.log[-2] or any("2 mercenaries stay on." in line for line in c.log)


# ---------------------------------------------------------------- Mission 3: Lessons in Flames
def _mission3(players=1, seed=50):
    names = ["Solo", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.mission = 3
    c.completed = [1, 2]
    c.relics.append("flute")
    P.add_card(c.party, dict(M.HIGH_ARCANA))
    g = c.start_attempt(seed=seed)
    return c, g


def test_mission3_setup_removes_the_high_arcana_and_builds_the_academy():
    c, g = _mission3()
    assert P.find(c.party, "ARC25") is None and any("High Arcana" in line for line in c.log)
    assert "ARC25" not in g.cards
    enemies = [g.cards[x] for x in [g.enemy.card_id] + g.castle]
    assert [e.name for e in enemies] == ["Instructor"] * 4 + ["Professor"] * 2 + ["Dean"]
    assert all(e.suits == ("M",) for e in enemies)
    assert (g.enemy.attack, g.enemy.max_hp) == (10, 30)
    assert [g.cards[x].health for x in g.castle] == [30, 30, 30, 45, 45, 60]
    assert g.immune("M") and not g.immune("H")
    # the second attempt does not remove anything more (idempotent start steps)
    g._lose("test")
    c.finish_attempt(g)
    n = len(c.log)
    c.start_attempt(seed=51)
    assert not any("High Arcana" in line for line in c.log[n:])


def test_mission3_zone_grows_at_end_of_turn_and_grants_immunity():
    c, g = _mission3()
    set_hand(g, ["9S", "8H", "7D", "5S", "6C"])
    set_tavern_top(g, ["4H", "3S", "2D"])
    g.play(["9S"])                       # paladin: shield 9, enemy attack 10 -> 1 damage
    assert g.shield == 9 and g.enemy_attack == 1 and g.phase == "suffer"
    g.suffer(["7D"])
    # end of turn: the top reserve card went into the zone, the next turn began
    assert g.mission_zone == ["4H"] and g.phase == "play" and g.turn == 2
    assert g.immune("H") and g.rules.immune_suits(g) == ("M", "H")
    # a cleric played now is immune (strength still counts as damage)
    set_hand(g, ["8H", "5S", "6C", "AS"])
    hp = g.enemy.hp
    g.play(["8H"])
    assert g.enemy.hp == hp - 8 and any(ev["t"] == "power" and ev.get("immune") for ev in g.last_events)
    assert len(g.tavern) >= 0 and "4H" in g.mission_zone
    g.suffer(["5S"]) if g.phase == "suffer" else None
    # a paladin entered the zone at the end of that turn: the earlier 9S stops shielding
    assert g.mission_zone == ["4H", "3S"] and g.immune("S")
    assert g.shield == 0 and g.enemy_attack == 10
    # not after a defeat: end-of-turn effects are skipped when the enemy falls
    g.enemy.hp = 1
    set_hand(g, ["6C", "AS", "2S"])
    g.play(["6C"])          # 12 damage, not exact -> no rescue decision
    assert g.phase == "play" and g.enemies_defeated == 1
    assert g.mission_zone == [] and set(["4H", "3S"]) <= set(g.banished)
    assert g.cards[g.banished[-1]].name in ("Instructor",) or any(g.cards[x].name == "Instructor" for x in g.banished)
    assert "2D" in g.tavern or "2D" in g.active_player.hand  # untouched: no end of turn


def test_mission3_corrupted_and_jester_paladins_keep_their_shield():
    c, g = _mission3()
    P.add_flag(c.party, "5S", "corrupted")
    g = c.start_attempt(seed=52)
    g.cards["5S"] = g.cards["5S"].with_changes(flags=("corrupted",))
    set_hand(g, ["5S", "9S", "8H", "7D"])
    set_tavern_top(g, ["AD", "3S", "2D", "4D"])
    g.play(["5S"])          # corrupted paladin: banishes AD, shield 5
    assert g.banished == ["AD"] and g.shield == 5
    g.suffer(["8H"])        # 3S enters the zone: paladin immunity
    assert g.mission_zone == ["3S"] and g.immune("S")
    assert g.shield == 5    # the corrupted paladin ignores immunity (rulebook p.20)
    set_hand(g, ["9S", "7D", "6C"])
    g.play(["9S"])          # a plain paladin now: immune, no extra shield
    assert g.shield == 5
    # a paladin inside a claimed-Jester attack keeps its shield too
    c2, g2 = _mission3(players=3, seed=53)
    jester = [x for x in g2.cards if g2.cards[x].is_jester][0]
    set_hand(g2, [jester, "4D"], player=0)
    set_hand(g2, ["7S", "3H", "2C"], player=1)
    set_tavern_top(g2, ["3S", "2D", "5D"])
    g2.play([jester])
    assert g2.phase == "choose_next"
    g2.choose_next(1)
    g2.play(["7S"])
    assert g2.plays[-1].jester and g2.shield == 7 and g2.phase == "suffer"
    g2.suffer(["3H"])
    assert g2.mission_zone == ["3S"] and g2.immune("S") and g2.shield == 7


def test_mission3_exact_kill_rescues_one_zone_card_by_choice():
    from regicide.engine import IllegalAction, PHASE_DECIDE
    c, g = _mission3()
    set_hand(g, ["9S", "8H", "7D", "5C", "6D"])
    set_tavern_top(g, ["4H", "3S", "2D"])
    g.play(["9S"]); g.suffer(["7D"])
    g.play(["8H"]); g.suffer(["6D"]) if g.phase == "suffer" else None
    assert g.mission_zone == ["4H", "3S"]
    g.enemy.hp = 10
    set_hand(g, ["5C", "2D", "AS"])
    g.play(["5C"])          # 10 exact
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "zone_rescue" and g.deciding == 0
    acts = g.legal_actions()
    assert sorted(a["card"] for a in acts) == ["3S", "4H"] and not any(a.get("skip") for a in acts)
    with pytest.raises(IllegalAction):
        g.decide({"type": "zone_rescue", "card": "2D"})
    with pytest.raises(IllegalAction):
        g.play(["2D"])
    # the decision survives a save round trip
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    assert g.phase == PHASE_DECIDE and g.decision["exact"] is True
    g.decide({"type": "zone_rescue", "card": "3S"})
    assert g.phase == "play" and g.enemies_defeated == 1
    assert "3S" in g.discard and g.discard[0] == "5C" and "4H" in g.banished and "3S" not in g.banished
    assert g.mission_zone == [] and g.cards[g.enemy.card_id].name == "Instructor"
    assert any(x.startswith("ACJ") for x in g.banished)  # the defeated Instructor is banished


def test_mission3_bots_play_it_out():
    from regicide.bots import play_out, greedy_policy, random_policy
    for players, seed, policy in ((1, 60, greedy_policy), (2, 61, greedy_policy), (3, 62, random_policy)):
        c, g = _mission3(players=players, seed=seed)
        play_out(g, policy, rng=random.Random(seed))
        assert g.is_over
        assert len(g.all_card_ids()) == len(set(g.all_card_ids())) == len(g.cards)


# ---------------------------------------------------------------- Mission 5 data (rules pending)
def test_mission5_setup_and_rewards_follow_the_cards():
    c = CampaignState.new(1, ["Solo"], seed=70)
    c.mission = 5
    c.completed = [1, 2, 3, 4]
    P.add_card(c.party, dict(M.GORAN))
    extra = M.build_setup(c, 5, random.Random(1))
    assert [d["id"] for d in extra["banished_start"]] == ["MYLA7"]
    enemies = extra["castle"]
    assert [e["name"] for e in enemies] == ["Sporeling"] * 4 + ["Gloomspore"] * 4
    assert [(e["attack"], e["health"]) for e in enemies][:1] == [(10, 40)] and (enemies[-1]["attack"], enemies[-1]["health"]) == (15, 60)
    # start steps: the four Reavers join once
    rng = random.Random(2)
    for step in M.start_steps(c, 5):
        M.apply_step(c, step, rng)
    assert [P.find(c.party, x)["name"] for x in ("3R", "5R", "7R", "9R")] == ["Oaken", "Harore", "Elf Reaver", "Drakonid Reaver"]
    assert M.start_steps(c, 5) == []
    # rewards
    steps = M.reward_steps(c, 5, rng)
    kinds = [s["kind"] for s in steps]
    assert kinds == ["add_suit", "add_card", "remove_card", "remove_card", "remove_card", "corrupt_random", "choice_suit"]
    for s in steps:
        if s["kind"].startswith("choice"):
            c.pending.append(s)
        else:
            M.apply_step(c, s, rng)
    assert P.find(c.party, "GOR8")["suits"] == ["C"]
    assert P.find(c.party, "MYLA7")["name"] == "Myla" and P.find(c.party, "MYLA7")["suits"] == []
    assert P.find(c.party, "5R") is not None and all(P.find(c.party, x) is None for x in ("3R", "7R", "9R"))
    step = c.pending_choice()
    assert step["kind"] == "choice_suit" and step["options"] == ["6H", "6D", "6S"]
    with pytest.raises(ValueError):
        c.resolve_choice("6C")  # Esme is not offered
    c.resolve_choice("6D")
    assert P.find(c.party, "6D")["suits"] == ["D", "R"] and not c.pending


def test_mission6_setup_and_rewards_follow_the_cards():
    c = CampaignState.new(1, ["Solo"], seed=80)
    c.mission = 6
    c.completed = [1, 2, 3, 4, 5]
    P.add_card(c.party, dict(M.GORAN))
    P.add_suit(c.party, "GOR8", "C")
    P.add_card(c.party, dict(M.MYLA))
    rng = random.Random(3)
    for step in M.start_steps(c, 6):
        M.apply_step(c, step, rng)
    assert P.find(c.party, "MYLA7") is None
    assert [P.find(c.party, x)["name"] for x in ("3G", "5G", "7G", "9G")] == ["Runo", "Teko", "Elf Guardian", "Drakonid Guardian"]
    assert M.start_steps(c, 6) == []
    extra = M.build_setup(c, 6, rng)
    assert [d["id"] for d in extra["zone_start"]] == ["MYLA7"] and extra["banished_start"] == []
    enemies = extra["castle"]
    assert [e["name"] for e in enemies] == ["Guardian Statue"] * 4 + ["Evergreen Statue"] * 4
    assert (enemies[0]["attack"], enemies[0]["health"], enemies[-1]["attack"], enemies[-1]["health"]) == (15, 30, 20, 40)
    steps = M.reward_steps(c, 6, rng)
    assert [s["kind"] for s in steps] == ["add_suit", "corrupt_random", "relic", "choice_suit", "remove_card", "remove_card", "remove_card"]
    for s in steps:
        if s["kind"].startswith("choice"):
            c.pending.append(s)
        else:
            M.apply_step(c, s, rng)
    assert P.find(c.party, "GOR8")["suits"] == ["C", "S"] and "emblem" in c.relics
    assert P.find(c.party, "3G") is not None and all(P.find(c.party, x) is None for x in ("5G", "7G", "9G"))
    step = c.pending_choice()
    assert step["kind"] == "choice_suit" and step["options"] == ["8H", "8D", "8C"]
    c.resolve_choice("8C")
    assert P.find(c.party, "8C")["suits"] == ["C", "G"] and not c.pending


# ---------------------------------------------------------------- Mages (rulebook p.16, p.23)
def _mage_campaign(players=1, seed=100, relics=(), corrupted=()):
    """A mission 1 attempt whose party also holds the Mage class deck (A to 10 of mages)."""
    names = ["Ana", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    for cid in corrupted:
        P.add_flag(c.party, cid, "corrupted")
    c.relics.extend(relics)
    g = c.start_attempt(seed=seed)
    return c, g


def _powers(g):
    return [(ev["suit"], ev) for ev in g.last_events if ev["t"] == "power"]


def test_mage_example_ace_and_nine_adds_a_bard_strength_16_draws_16_deals_32():
    # p.23: an ace (of warriors) with a 9 of mages peeks at 10 cards and adds a 6 of bards:
    # strength 16, draw 16, 32 damage. Three empty hands so that all 16 can be drawn.
    c, g = _mage_campaign(3, seed=101)
    set_enemy(g, "K", "H")
    set_hand(g, ["AC", "9M"], 0)
    set_hand(g, [], 1)
    set_hand(g, [], 2)
    top = ["6D", "2C", "3C", "4C", "5C", "2S", "3S", "4S", "5S", "6S"]
    set_tavern_top(g, top)
    rest_of_reserve = g.tavern[10:]
    g.play(["AC", "9M"])
    # step 2 pauses on the mage: the attacker decides, the revealed cards are out of the reserve
    assert g.phase == PHASE_DECIDE and g.active == 0 and g.deciding == 0
    d = g.decision
    assert d["kind"] == "mage_peek" and d["strength"] == 10 and d["revealed"] == top and d["eligible"] == top
    assert d["play_index"] == 0 and d["resume"] == "resolve" and d["done_suits"] == ["M"] and d["damage"] == 10
    assert g.tavern == rest_of_reserve and sorted(g.all_card_ids()) == sorted(g.cards)
    assert g.enemy.hp == 40 and g.plays[0].card_ids == ["AC", "9M"] and g.plays[0].mage
    assert any(ev["t"] == "mage_peek" and ev["count"] == 10 for ev in g.last_events)
    acts = g.legal_actions()
    assert [a["label"] for a in acts] == ["Add %s to the attack" % g.cards[x].label() for x in top]
    assert not any(a.get("skip") for a in acts)          # the pick is mandatory
    with pytest.raises(IllegalAction):
        g.decide({"type": "mage_skip"})
    with pytest.raises(IllegalAction):
        g.decide({"type": "mage_pick", "card": "7D"})    # not revealed
    g.decide({"type": "mage_pick", "card": "6D"})
    play = g.plays[0]
    assert play.card_ids == ["AC", "9M", "6D"] and play.value == 16 and play.mage and set(play.suits) == {"C", "M", "D"}
    assert [s for s, _ in _powers(g)] == ["D", "C"]      # the mage is done; bards then warriors at 16
    bards = dict(_powers(g))["D"]
    assert bards["value"] == 16 and len(bards["drawn"]) == 16
    assert g.enemy.hp == 40 - 32 and g.phase == PHASE_SUFFER and g.decision is None
    assert set(top) - {"6D"} <= set(g.discard) and "6D" not in g.discard
    assert sorted(g.all_card_ids()) == sorted(g.cards)


def test_mage_example_mage_into_mage_strength_19_and_shield_19():
    # p.23: ace + 8 of mages (9) peeks at 9, chooses a 7 of mages, peeks at 7, chooses a
    # 3 of paladins: strength 19 (1 + 8 + 7 + 3), so 19 damage and a shield of 19.
    c, g = _mage_campaign(1, seed=102)
    set_enemy(g, "K", "H")
    set_hand(g, ["AH", "8M", "9S", "8S", "7S"])
    first = ["7M", "2C", "3C", "4C", "5C", "2S", "4S", "5S", "6S"]
    second = ["3S", "2D", "3D", "4D", "5D", "6D", "7D"]
    set_tavern_top(g, first + second)
    g.play(["AH", "8M"])
    assert g.decision["strength"] == 9 and g.decision["revealed"] == first
    g.decide({"type": "mage_pick", "card": "7M"})
    # the chosen mage looks again with its own strength; the first rest is already discarded
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "mage_peek"
    assert g.decision["strength"] == 7 and g.decision["revealed"] == second
    assert set(first) - {"7M"} <= set(g.discard)
    assert g.plays[0].card_ids == ["AH", "8M", "7M"] and g.plays[0].value == 16
    assert any(ev["t"] == "mage_pick" and ev["card"] == "7M" for ev in g.last_events)
    g.decide({"type": "mage_pick", "card": "3S"})
    play = g.plays[0]
    assert play.card_ids == ["AH", "8M", "7M", "3S"] and play.value == 19
    assert dict(_powers(g))["S"]["shield"] == 19 and "M" not in dict(_powers(g))
    assert g.enemy.hp == 40 - 19 and g.shield == 19 and g.enemy_attack == 1
    assert g.phase == PHASE_SUFFER and g.pending_damage == 1
    assert sorted(g.all_card_ids()) == sorted(g.cards)


def test_mage_example_kinfolk_with_corrupted_warrior_heals_13_deals_26_shields_13():
    # p.23: kinfolk 3 corrupted warrior + 3 mage + 3 paladin (9) peeks at 9 and adds a
    # 4 of clerics: heal 13, 26 damage, reduce the enemy's strength by 13.
    from helpers import set_discard
    c, g = _mage_campaign(1, seed=103, corrupted=("3C",))
    set_enemy(g, "K", "D")
    set_hand(g, ["3C", "3M", "3S", "9S", "8S"])
    peek = ["4H", "2C", "4C", "5C", "2S", "4S", "5S", "6S", "2D"]
    set_tavern_top(g, ["10D"] + peek)             # the corrupted warrior banishes the top card first
    set_discard(g, ["5H", "6H", "7H", "8H", "9H", "10H", "2H", "AD", "AS", "AC", "6C", "7C", "8C", "9C", "10C"])
    assert g.check_play(["3C", "3M", "3S"]) == (True, "set")
    g.play(["3C", "3M", "3S"])
    assert g.banished == ["10D"] and g.decision["strength"] == 9 and g.decision["revealed"] == peek
    g.decide({"type": "mage_pick", "card": "4H"})
    powers = dict(_powers(g))
    assert powers["H"]["healed"] == 13 and powers["C"]["doubled"] and powers["S"]["shield"] == 13
    assert g.enemy.hp == 40 - 26 and g.shield == 13 and g.enemy_attack == 20 - 13
    assert g.plays[0].card_ids == ["3C", "3M", "3S", "4H"] and g.plays[0].value == 13 and g.plays[0].mage
    assert sorted(g.all_card_ids()) == sorted(g.cards)


def test_mage_revealed_jesters_and_corrupted_cards_are_discarded_and_not_pickable():
    c, g = _mage_campaign(3, seed=104, corrupted=("7D",))
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S", "8S", "7S"], 0)
    set_tavern_top(g, [jester, "7D", "5H", "4S", "3C"])
    g.play(["5M"])
    d = g.decision
    assert d["revealed"] == [jester, "7D", "5H", "4S", "3C"] and d["eligible"] == ["5H", "4S", "3C"]
    assert sorted(a["card"] for a in g.legal_actions()) == ["3C", "4S", "5H"]
    with pytest.raises(IllegalAction):
        g.decide({"type": "mage_pick", "card": jester})
    with pytest.raises(IllegalAction):
        g.decide({"type": "mage_pick", "card": "7D"})
    g.decide({"type": "mage_pick", "card": "5H"})
    assert g.plays[0].card_ids == ["5M", "5H"] and g.plays[0].value == 10
    assert set([jester, "7D", "4S", "3C"]) <= set(g.discard)
    assert g.banished == []                       # the corrupted card never entered play
    assert g.enemy.hp == 30 and g.phase == PHASE_SUFFER


def test_mage_with_a_short_or_empty_reserve():
    c, g = _mage_campaign(1, seed=105)
    set_enemy(g, "K", "H")
    set_hand(g, ["9M", "9S", "8S", "7S"])
    set_tavern_top(g, ["4C", "5D", "6S"])
    g.discard = g.tavern[3:] + g.discard           # a short reserve: three cards left
    g.tavern = g.tavern[:3]
    g.play(["9M"])
    d = g.decision
    assert d["strength"] == 9 and d["revealed"] == ["4C", "5D", "6S"] and g.tavern == []
    assert any(ev["t"] == "mage_peek" and ev["count"] == 3 and ev["strength"] == 9 for ev in g.last_events)
    g.decide({"type": "mage_pick", "card": "6S"})
    assert g.plays[0].value == 15 and g.enemy.hp == 25 and g.shield == 15
    assert sorted(g.all_card_ids()) == sorted(g.cards)
    # an empty reserve: nothing to look at, the only option is to add nothing and go on
    c, g = _mage_campaign(1, seed=106)
    set_enemy(g, "K", "H")
    set_hand(g, ["9M", "9S", "8S", "7S"])
    g.discard = g.tavern + g.discard
    g.tavern = []
    g.play(["9M"])
    assert g.phase == PHASE_DECIDE and g.decision["revealed"] == [] and g.decision["eligible"] == []
    acts = g.legal_actions()
    assert len(acts) == 1 and acts[0]["type"] == "mage_skip" and acts[0]["skip"]
    g.decide(acts[0])
    assert g.decision is None and g.enemy.hp == 40 - 9 and g.phase == PHASE_SUFFER
    assert any(ev["t"] == "mage_skip" for ev in g.last_events)
    assert sorted(g.all_card_ids()) == sorted(g.cards)


def _mission3_with_mages(players=1, seed=110, corrupted=()):
    names = ["Solo", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.mission = 3
    c.completed = [1, 2]
    P.add_card(c.party, dict(M.HIGH_ARCANA))
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    for cid in corrupted:
        P.add_flag(c.party, cid, "corrupted")
    g = c.start_attempt(seed=seed)
    return c, g


def test_mage_immunity_blocks_the_peek_but_the_mage_attack_is_still_banished():
    # Mission 3: every enemy is immune to mages (p.20: the attack is banished anyway).
    c, g = _mission3_with_mages()
    assert g.immune("M")
    set_hand(g, ["5H", "9M", "8S", "7S", "6S", "4D"])
    set_tavern_top(g, ["2D", "3D", "4C", "5C"])
    g.play(["5H"])                                   # a plain play against the same enemy
    assert g.enemy.hp == 25 and g.phase == PHASE_SUFFER
    g.suffer(["8S", "7S"])
    assert g.mission_zone == ["2D"]
    g.enemy.hp = 8
    set_hand(g, ["9M", "6S", "4D"])
    reserve = list(g.tavern)
    g.play(["9M"])
    # no peek, no decision: the reserve is untouched and the 9 damage finishes the enemy
    assert dict(_powers(g))["M"]["immune"] and g.decision is None
    assert g.enemies_defeated == 1 and g.phase == PHASE_PLAY
    defeat = [ev for ev in g.last_events if ev["t"] == "defeat"][0]
    assert defeat["mage_banished"] == ["9M"] and not defeat["exact"]
    assert "9M" in g.banished and "9M" not in g.discard
    assert "5H" in g.discard and "5H" not in g.banished
    assert set(reserve) <= set(g.tavern) | set(g.players[0].hand) | set(g.mission_zone) | set(g.banished)
    assert sorted(g.all_card_ids()) == sorted(g.cards)


def test_mage_pick_with_exact_kill_in_mission3_triggers_the_zone_rescue():
    c, g = _mission3_with_mages(seed=111, corrupted=("5M",))   # corrupted: its ability ignores immunity
    set_hand(g, ["9S", "8H", "7D", "5M", "6S", "2D"])
    set_tavern_top(g, ["4H", "2C", "3S", "4S", "6D", "7H", "8D"])
    g.play(["9S"])
    g.suffer(["7D"])
    assert g.mission_zone == ["4H"] and g.immune("H")
    g.enemy.hp = 9
    set_hand(g, ["5M", "6S", "2D"])
    g.play(["5M"])
    assert g.banished[-1] == "2C"                                # corruption banishes the top card first
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "mage_peek"
    assert g.decision["revealed"] == ["3S", "4S", "6D", "7H", "8D"]
    g.decide({"type": "mage_pick", "card": "4S"})               # 5 + 4 = 9: exact
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "zone_rescue" and g.deciding == 0
    assert [a["card"] for a in g.legal_actions()] == ["4H"]
    g.decide({"type": "zone_rescue", "card": "4H"})
    assert g.enemies_defeated == 1 and g.phase == PHASE_PLAY and g.decision is None
    assert "4H" in g.discard and "9S" in g.discard               # the plain paladin play is discarded
    assert "5M" in g.banished and "4S" in g.banished             # the mage attack is banished
    assert sorted(g.all_card_ids()) == sorted(g.cards)


def test_flute_added_mage_makes_the_attack_peek_for_the_attacker():
    c, g = _mage_campaign(2, seed=112, relics=["flute"])
    set_enemy(g, "J", "H")
    set_hand(g, ["3C", "9S", "8S"], player=0)
    set_hand(g, ["3M", "7C"], player=1)
    set_tavern_top(g, ["4D", "2S", "5S", "6H", "AD", "2D"])
    g.play(["3C"])
    assert g.decision["kind"] == "flute_add" and g.deciding == 1
    assert not g.plays[0].mage
    g.flute_add(["3M"])
    # the attack now contains a mage: step 2 pauses on the attacker's peek with the total
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "mage_peek" and g.deciding == 0 and g.active == 0
    assert g.decision["strength"] == 6 and g.decision["revealed"] == ["4D", "2S", "5S", "6H", "AD", "2D"]
    assert g.plays[0].card_ids == ["3C", "3M"] and g.plays[0].mage
    g.decide({"type": "mage_pick", "card": "4D"})
    # 3 + 3 + 4 = 10, doubled by the warrior: the Justicar falls and the mage attack is banished
    assert g.plays == [] and any(ev["t"] == "damage" and ev["amount"] == 20 for ev in g.last_events)
    assert g.enemies_defeated == 1 and "3M" in g.banished and "3C" in g.banished and "4D" in g.banished
    assert g.active == 0 and g.phase == PHASE_PLAY


def test_mage_peek_survives_a_save_round_trip():
    c, g = _mage_campaign(1, seed=113)
    set_enemy(g, "K", "H")
    set_hand(g, ["AH", "8M", "9S", "8S", "7S"])
    set_tavern_top(g, ["7M", "2C", "3C", "4C", "5C", "2S", "4S", "5S", "6S", "3S", "2D", "3D", "4D", "5D", "6D", "7D"])
    g.play(["AH", "8M"])
    g.decide({"type": "mage_pick", "card": "7M"})
    d = json.loads(json.dumps(g.to_dict()))
    assert d["phase"] == PHASE_DECIDE and d["decision"]["kind"] == "mage_peek" and d["plays"][0]["mage"] is True
    g2 = Game.from_dict(d)
    assert g2.phase == PHASE_DECIDE and g2.decision == g.decision and g2.deciding == 0
    assert g2.legal_actions() == g.legal_actions()
    assert sorted(g2.all_card_ids()) == sorted(g2.cards)
    assert g2.plays[0].mage and g2.plays[0].value == 16
    g.decide({"type": "mage_pick", "card": "3S"})
    g2.decide({"type": "mage_pick", "card": "3S"})
    assert g2.phase == PHASE_SUFFER and g2.to_dict() == g.to_dict()


def test_mage_preview_leaves_the_reserve_alone_and_assumes_nothing_is_added():
    c, g = _mage_campaign(1, seed=114)
    set_enemy(g, "K", "H")
    set_hand(g, ["9M", "AC", "9S", "8S", "7S"])
    before = list(g.tavern)
    pv = g.preview_play(["9M"])
    assert pv["ok"] and pv["decision"] and pv["decision_kind"] == "mage_peek" and pv["mage_peeks"] == [9]
    assert pv["damage"] == 9 and pv["enemy_hp_after"] == 31 and pv["phase_after"] == PHASE_SUFFER
    assert "M" not in pv["powers"]
    pv2 = g.preview_play(["AC", "9M"])
    assert pv2["mage_peeks"] == [10] and pv2["damage"] == 20
    assert g.tavern == before and g.phase == PHASE_PLAY and g.decision is None and g.discard == []


def test_greedy_bot_picks_the_exact_kill_else_the_most_damage():
    c, g = _mage_campaign(1, seed=115)
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S", "8S", "7S", "6S"])
    set_tavern_top(g, ["6C", "4H", "3S", "2D", "AD"])
    g.enemy.hp = 9
    g.play(["5M"])
    act = greedy_policy(g)
    assert act["type"] == "mage_pick" and act["card"] == "4H"      # 5 + 4 = 9 exactly; 6♣ would overkill
    apply_action(g, act)
    assert g.enemies_defeated == 1 and g.tavern[0] == "KH"
    c, g = _mage_campaign(1, seed=116)
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S", "8S", "7S", "6S"])
    set_tavern_top(g, ["6C", "7H", "3S", "2D", "AD"])
    g.play(["5M"])
    act = greedy_policy(g)
    assert act["card"] == "6C"                                      # 22 damage beats 12 or 8
    # and with nothing eligible the only move is to add nothing
    c, g = _mage_campaign(1, seed=117, corrupted=("7D",))
    set_enemy(g, "K", "H")
    set_hand(g, ["AM", "9S", "8S", "7S"])
    set_tavern_top(g, ["7D"])
    g.play(["AM"])
    assert greedy_policy(g)["type"] == "mage_skip"


@pytest.mark.parametrize("players", [1, 2])
def test_bots_play_out_games_with_mages_and_the_emblem(players):
    picks = 0
    emblem = 0
    rng = random.Random(players)
    for seed in range(8):
        c = _mage_campaign(players, seed=200 + seed, relics=["emblem"])[0]
        g = c.start_attempt(seed=300 + seed)
        play_out(g, greedy_policy if seed % 2 == 0 else random_policy, rng)
        assert g.is_over and g.decision is None
        assert sorted(g.all_card_ids() + g.extra.get("flute", [])) == sorted(g.cards)
        picks += sum(1 for line in g.log if "(Mage)" in line)
        emblem += sum(1 for line in g.log if "Azure Emblem" in line)
    assert picks > 0 and emblem > 0


# ---------------------------------------------------------------- Azure Emblem
def test_emblem_solo_keeps_one_revealed_card_on_top_of_the_reserve():
    c, g = _mage_campaign(1, seed=120, relics=["emblem"])
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S", "8S", "7S", "6S"])
    set_tavern_top(g, ["6C", "7H", "4C", "2S", "3S", "AD"])
    g.play(["5M"])
    g.decide({"type": "mage_pick", "card": "6C"})
    # the rest is not discarded yet: one card may go back on top of the reserve
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "emblem_keep" and g.deciding == 0
    assert g.decision["revealed"] == ["7H", "4C", "2S", "3S"] and g.decision["picked"] == "6C"
    assert g.discard == [] and sorted(g.all_card_ids()) == sorted(g.cards)
    acts = g.legal_actions()
    assert [a["label"] for a in acts] == ["Keep 7♥ on top of the reserve", "Keep 4♣ on top of the reserve",
                                          "Keep 2♠ on top of the reserve", "Keep 3♠ on top of the reserve", "Discard them all"]
    assert acts[-1]["type"] == "emblem_skip" and acts[-1]["skip"]
    with pytest.raises(IllegalAction):
        g.decide({"type": "emblem_keep", "card": "6C"})
    with pytest.raises(IllegalAction):
        g.decide({"type": "emblem_keep", "card": "AD"})
    g.decide({"type": "emblem_keep", "card": "7H"})
    assert g.tavern[0] == "7H" and g.tavern[1] == "AD"
    assert set(["4C", "2S", "3S"]) <= set(g.discard) and "7H" not in g.discard
    assert any(ev["t"] == "emblem_keep" and ev["card"] == "7H" for ev in g.last_events)
    assert g.decision is None and g.plays[0].value == 11 and g.enemy.hp == 40 - 22 and g.phase == PHASE_SUFFER
    assert sorted(g.all_card_ids()) == sorted(g.cards)
    # declining discards them all
    c, g = _mage_campaign(1, seed=121, relics=["emblem"])
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S", "8S", "7S", "6S"])
    set_tavern_top(g, ["6C", "7H", "4C", "2S", "3S", "AD"])
    g.play(["5M"])
    g.decide({"type": "mage_pick", "card": "6C"})
    g.decide({"type": "emblem_skip"})
    assert g.tavern[0] == "AD" and set(["7H", "4C", "2S", "3S"]) <= set(g.discard) and g.phase == PHASE_SUFFER
    # without the relic the pick discards the rest at once
    c, g = _mage_campaign(1, seed=122)
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S", "8S", "7S", "6S"])
    set_tavern_top(g, ["6C", "7H", "4C", "2S", "3S", "AD"])
    g.play(["5M"])
    g.decide({"type": "mage_pick", "card": "6C"})
    assert g.decision is None and g.phase == PHASE_SUFFER
    # a single revealed card: nothing else to keep, no decision
    c, g = _mage_campaign(1, seed=123, relics=["emblem"])
    set_enemy(g, "K", "H")
    set_hand(g, ["AM", "9S", "8S", "7S", "6S"])
    set_tavern_top(g, ["6C"])
    g.play(["AM"])
    g.decide({"type": "mage_pick", "card": "6C"})
    assert g.decision is None and g.phase == PHASE_SUFFER


def test_emblem_solo_applies_again_after_a_chained_mage_and_the_kept_card_is_revealed_first():
    c, g = _mage_campaign(1, seed=124, relics=["emblem"])
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S", "8S", "7S", "6S"])
    set_tavern_top(g, ["3M", "7H", "4C", "2S", "6C", "AD", "2D", "3D"])
    g.play(["5M"])
    g.decide({"type": "mage_pick", "card": "3M"})
    assert g.decision["kind"] == "emblem_keep" and g.decision["revealed"] == ["7H", "4C", "2S", "6C"]
    g.decide({"type": "emblem_keep", "card": "7H"})
    # the chosen mage peeks with its own strength: the kept card is on top of the reserve
    assert g.decision["kind"] == "mage_peek" and g.decision["strength"] == 3
    assert g.decision["revealed"] == ["7H", "AD", "2D"] and "picked" not in g.decision
    g.decide({"type": "mage_pick", "card": "7H"})
    assert g.decision["kind"] == "emblem_keep" and g.decision["revealed"] == ["AD", "2D"] and g.decision["picked"] == "7H"
    g.decide({"type": "emblem_keep", "card": "2D"})
    assert g.tavern[0] == "2D" and g.tavern[1] == "3D" and "AD" in g.discard
    assert g.decision is None and g.plays[0].card_ids == ["5M", "3M", "7H"] and g.plays[0].value == 15
    assert g.enemy.hp == 40 - 15 and g.phase == PHASE_SUFFER
    assert sorted(g.all_card_ids()) == sorted(g.cards)
    # the decision survives a save round trip
    c, g = _mage_campaign(1, seed=125, relics=["emblem"])
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S", "8S", "7S", "6S"])
    set_tavern_top(g, ["3M", "7H", "4C", "2S", "6C", "AD", "2D", "3D"])
    g.play(["5M"])
    g.decide({"type": "mage_pick", "card": "3M"})
    g2 = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    assert g2.decision == g.decision and g2.legal_actions() == g.legal_actions()
    assert sorted(g2.all_card_ids()) == sorted(g2.cards)


def test_emblem_multiplayer_others_place_cards_once_per_attack_before_the_first_peek():
    c, g = _mage_campaign(3, seed=126, relics=["emblem"])
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S"], player=0)
    set_hand(g, ["7C", "3D"], player=1)
    set_hand(g, ["4D", "2S"], player=2)
    set_tavern_top(g, ["3M", "2C", "4C", "6C", "8C", "5D", "9D"])
    g.play(["5M"])
    # before any peek: Ben (left of Ana) first, then Cy; Ana stays the active player
    assert g.phase == PHASE_DECIDE and g.active == 0 and g.deciding == 1
    assert g.decision["kind"] == "emblem_place" and g.decision["queue"] == [2] and g.decision["strength"] == 5
    assert g.decision["done_suits"] == ["M"] and "revealed" not in g.decision
    acts = g.legal_actions()
    assert [a["label"] for a in acts] == ["Place 7♣ on top of the reserve", "Place 3♦ on top of the reserve", "Pass"]
    assert acts[-1]["type"] == "emblem_pass" and acts[-1]["skip"]
    assert g.tavern[0] == "3M" and g.enemy.hp == 40
    with pytest.raises(IllegalAction):
        g.decide({"type": "emblem_place", "card": "4D"})     # not Ben's card
    g.decide({"type": "emblem_place", "card": "7C"})
    assert g.tavern[0] == "7C" and "7C" not in g.players[1].hand
    assert g.phase == PHASE_DECIDE and g.deciding == 2 and g.decision["queue"] == []
    assert any(ev["t"] == "emblem_place" and ev["card"] == "7C" for ev in g.last_events)
    g.decide({"type": "emblem_place", "card": "4D"})
    # the last card placed is on top; now the mage peeks and reveals the placed cards first
    assert g.phase == PHASE_DECIDE and g.deciding == 0 and g.decision["kind"] == "mage_peek"
    assert g.decision["strength"] == 5 and g.decision["revealed"] == ["4D", "7C", "3M", "2C", "4C"]
    assert "queue" not in g.decision
    g.decide({"type": "mage_pick", "card": "3M"})
    # a chained mage peeks without the Emblem happening again
    assert g.decision["kind"] == "mage_peek" and g.decision["strength"] == 3
    assert g.decision["revealed"] == ["6C", "8C", "5D"]
    g.decide({"type": "mage_pick", "card": "5D"})
    assert g.decision is None and g.plays[0].card_ids == ["5M", "3M", "5D"] and g.plays[0].value == 13
    assert g.enemy.hp == 40 - 13 and g.phase == PHASE_SUFFER and g.active == 0
    assert set(["4D", "7C", "2C", "4C", "6C", "8C"]) <= set(g.discard)
    assert sorted(g.all_card_ids()) == sorted(g.cards)


def test_emblem_multiplayer_pass_skip_empty_hands_and_immunity():
    c, g = _mage_campaign(2, seed=127, relics=["emblem"])
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S"], player=0)
    set_hand(g, ["7C", "3D"], player=1)
    set_tavern_top(g, ["3C", "2C", "4C", "6C", "8C"])
    g.play(["5M"])
    assert g.decision["kind"] == "emblem_place" and g.deciding == 1
    g.decide({"type": "emblem_pass"})
    assert any(ev["t"] == "emblem_pass" for ev in g.last_events)
    assert g.decision["kind"] == "mage_peek" and g.decision["revealed"] == ["3C", "2C", "4C", "6C", "8C"]
    assert g.players[1].hand == ["7C", "3D"]
    # a player with an empty hand is not asked
    c, g = _mage_campaign(2, seed=128, relics=["emblem"])
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S"], player=0)
    set_hand(g, [], player=1)
    g.play(["5M"])
    assert g.decision["kind"] == "mage_peek"
    # the forecast assumes nobody places and nothing is added, and leaves the reserve alone
    c, g = _mage_campaign(2, seed=129, relics=["emblem"])
    set_enemy(g, "K", "H")
    set_hand(g, ["5M", "9S"], player=0)
    set_hand(g, ["7C", "3D"], player=1)
    before = list(g.tavern)
    pv = g.preview_play(["5M"])
    assert pv["ok"] and pv["decision_kind"] == "emblem_place" and pv["mage_peeks"] == [5] and pv["damage"] == 5
    assert g.tavern == before and g.decision is None
    # when immunity blocks the mage nothing is placed either (mission 3)
    c, g = _mission3_with_mages(players=2, seed=130)
    c.relics.append("emblem")
    g = c.start_attempt(seed=131)
    set_hand(g, ["5M", "9S", "8S"], player=0)
    set_hand(g, ["7C", "3D"], player=1)
    g.play(["5M"])
    assert g.decision is None and g.phase == PHASE_SUFFER and dict(_powers(g))["M"]["immune"]

def test_mission7_setup_and_rewards_follow_the_cards():
    c = CampaignState.new(1, ["Solo"], seed=90)
    c.mission = 7
    c.completed = [1, 2, 3, 4, 5, 6]
    P.add_card(c.party, dict(M.GORAN))
    rng = random.Random(4)
    for step in M.start_steps(c, 7):
        M.apply_step(c, step, rng)
    assert [P.find(c.party, x)["name"] for x in ("3U", "5U", "7U", "9U")] == ["Tolman", "Avion Druid", "Alantha", "Drakonid Druid"]
    assert M.start_steps(c, 7) == []
    extra = M.build_setup(c, 7, rng)
    enemies = extra["castle"]
    assert [e["name"] for e in enemies] == ["Shoal Pondkin"] * 4 + ["Deep Pondkin"] * 4 + ["Abyssal Pondkin"] * 4
    assert (enemies[0]["attack"], enemies[0]["health"], enemies[-1]["attack"], enemies[-1]["health"]) == (10, 20, 20, 40)
    pil = extra["pilgrims"]
    assert len(pil) == 25 and all("pilgrim" in d["flags"] and d["suits"] == [] for d in pil)
    assert sorted(d["value"] for d in pil) == [1] + sorted([v for v in range(2, 8) for _ in range(4)])
    assert len({d["id"] for d in pil}) == 25
    steps = M.reward_steps(c, 7, rng)
    assert [s["kind"] for s in steps] == ["add_suit", "corrupt_random", "remove_card", "remove_card", "remove_card", "choice_suit"]
    for s in steps:
        if s["kind"].startswith("choice"):
            c.pending.append(s)
        else:
            M.apply_step(c, s, rng)
    assert P.find(c.party, "GOR8")["suits"] == ["H"]
    assert P.find(c.party, "7U") is not None and all(P.find(c.party, x) is None for x in ("3U", "5U", "9U"))
    step = c.pending_choice()
    assert step["kind"] == "choice_suit" and step["options"] == ["4D", "4C", "4S"]
    c.resolve_choice("4S")
    assert P.find(c.party, "4S")["suits"] == ["S", "U"] and not c.pending


def test_mission8_setup_and_rewards_follow_the_cards():
    c = CampaignState.new(1, ["Solo"], seed=100)
    c.mission = 8
    c.completed = [1, 2, 3, 4, 5, 6, 7]
    P.add_card(c.party, dict(M.GORAN))
    rng = random.Random(5)
    for step in M.start_steps(c, 8):
        M.apply_step(c, step, rng)
    assert [P.find(c.party, x)["name"] for x in ("3T", "5T", "7T", "9T")] == ["Roslyn", "Avion Chanter", "Elf Chanter", "Druldox"]
    assert M.start_steps(c, 8) == []
    extra = M.build_setup(c, 8, rng)
    enemies = extra["castle"]
    assert [e["name"] for e in enemies] == ["Troll"] * 6 + ["Wyvern"] * 6
    assert all(len(e["suits"]) == 2 for e in enemies)
    assert len({tuple(sorted(e["suits"])) for e in enemies[:6]}) == 6 and len({tuple(sorted(e["suits"])) for e in enemies[6:]}) == 6
    assert (enemies[0]["attack"], enemies[0]["health"], enemies[-1]["attack"], enemies[-1]["health"]) == (10, 20, 25, 50)
    assert [d["id"] for d in extra["zone_start"]] == ["PILA"] and extra["pilgrims"] == []
    assert len(extra["pilgrims_in_reserve"]) == 24 and all(d["id"] != "PILA" for d in extra["pilgrims_in_reserve"])
    names = {}
    for d in extra["pilgrims_in_reserve"]:
        names.setdefault(d["value"], set()).add(d["name"])
    assert names[2] == {"Traveller", "Seeker"} and names[3] == {"Follower"} and names[4] == {"Servant"} and names[6] == {"Acolyte"}
    assert sorted(names) == [2, 3, 4, 5, 6, 7] and all(sum(1 for d in extra["pilgrims_in_reserve"] if d["value"] == v) == 4 for v in names)
    steps = M.reward_steps(c, 8, rng)
    assert [s["kind"] for s in steps] == ["add_suit", "corrupt_random", "remove_card", "remove_card", "remove_card", "choice_suit", "set_flag"]
    for s in steps:
        if s["kind"].startswith("choice"):
            c.pending.append(s)
        else:
            M.apply_step(c, s, rng)
    assert P.find(c.party, "GOR8")["suits"] == ["D"] and c.flags.get("puppy_boxed") is True
    assert P.find(c.party, "9T") is not None and all(P.find(c.party, x) is None for x in ("3T", "5T", "7T"))
    step = c.pending_choice()
    assert step["kind"] == "choice_suit" and step["options"] == ["2H", "2C", "2S"]
    c.resolve_choice("2C")
    assert P.find(c.party, "2C")["suits"] == ["C", "T"] and not c.pending


def test_mission9_setup_and_rewards_follow_the_cards():
    c = CampaignState.new(1, ["Solo"], seed=110)
    c.mission = 9
    c.completed = [1, 2, 3, 4, 5, 6, 7, 8]
    P.add_card(c.party, dict(M.GORAN))
    for s in ("C", "S", "H", "D"):
        P.add_suit(c.party, "GOR8", s)
    c.flags["beasts"] = True
    c.beast = "B_H"
    c.m_box_opened = True
    c.coins = 5
    c.hire("merc_12H")
    P.add_suit(c.party, "4D", "U")       # Glamelyn has a Druid sticker
    P.add_flag(c.party, "8H", "corrupted")
    rng = random.Random(6)
    assert M.start_steps(c, 9) == []
    extra = M.build_setup(c, 9, rng)
    enemies = extra["castle"]
    assert [e["name"] for e in enemies] == ["Loreguard"] * 4 + ["Lorekeeper"] * 4 + ["Myla"]
    assert enemies[-1]["attack"] == 20 and enemies[-1]["health"] == 80 and sorted(enemies[-1]["suits"]) == ["D", "S"]
    assert "fixed_immunity" in enemies[-1]["flags"]
    assert len(extra["pilgrims_in_reserve"]) == 24 and extra["zone_start"] == []
    cap = extra["capture"]
    assert cap["piles"] == 3 and cap["size"] == 10
    assert set(cap["exempt"]) == {"GOR8", "B_H", "M12H"}
    steps = M.reward_steps(c, 9, rng)
    assert [s["kind"] for s in steps] == ["relic", "remove_card", "add_card", "choice_mage_student", "add_card"]
    for s in steps:
        if s["kind"].startswith("choice"):
            c.pending.append(s)
        else:
            M.apply_step(c, s, rng)
    assert "mother" in c.relics
    assert P.find(c.party, "GOR8") is None
    new = P.find(c.party, "GOR8E")
    assert new["name"] == "Gøran" and sorted(new["suits"]) == ["C", "D", "H", "S"] and "ignores_immunity" in new["flags"]
    ash = P.find(c.party, "B_ASH")
    assert ash["suits"] == ["M"] and "beast" in ash["flags"] and ash["value"] == 0
    step = c.pending_choice()
    assert step["kind"] == "choice_mage_student" and step["options"] == ["4", "8"]
    with pytest.raises(ValueError):
        c.resolve_choice("6")
    line = c.resolve_choice("4")
    assert "Mage" in line
    stickered = [x for x in c.party if x["rank"] == "4" and "M" in x.get("suits", [])]
    assert len(stickered) == 1 and stickered[0]["id"] != "4D"  # Glamelyn already has a sticker
    assert not c.pending
    # feltrix: the renewed Gøran (an 8) and stickered 8s are never chosen; a corrupted
    # sleeve is not a sticker (pack C), so a corrupted 8 may be
    c2 = CampaignState.new(1, ["Solo"], seed=111)
    P.add_card(c2.party, dict(M.GORAN_RENEWED))
    for s in ("H", "D", "C"):
        P.add_suit(c2.party, "8" + s, "G")
    P.add_flag(c2.party, "8S", "corrupted")
    c2.pending.append({"kind": "choice_mage_student", "options": ["4", "8"], "label": "x"})
    line = c2.resolve_choice("8")
    assert "8" in line and P.find(c2.party, "8S")["suits"] == ["S", "M"]
    c2.pending.append({"kind": "choice_mage_student", "options": ["4", "8"], "label": "x"})
    assert "no student" in c2.resolve_choice("8")


def test_mission10_corrupted_party_members_form_the_enemy_deck_and_return():
    c = CampaignState.new(1, ["Solo"], seed=120)
    c.mission = 10
    c.completed = list(range(1, 10))
    P.add_card(c.party, dict(M.GORAN_RENEWED))
    P.add_card(c.party, dict(M.ASH))
    for cid in ("2S", "3H", "4D", "5C", "6C", "7S", "8H", "9D"):
        P.add_flag(c.party, cid, "corrupted")
        c.corrupted.append(cid)
    P.add_suit(c.party, "4D", "U")   # Glamelyn, corrupted and a druid
    rng = random.Random(7)
    steps = M.start_steps(c, 10)
    assert [s["kind"] for s in steps] == ["corrupted_leave"]
    M.apply_step(c, steps[0], rng)
    assert P.corrupted_ids(c.party) == [] and sorted(d["id"] for d in c.away) == ["2S", "3H", "4D", "5C", "6C", "7S", "8H", "9D"]
    assert M.start_steps(c, 10) == []   # retries do not move anything more
    extra = M.build_setup(c, 10, rng)
    enemies = extra["castle"]
    assert [e["id"] for e in enemies] == ["2S", "3H", "4D", "5C", "6C", "7S", "8H", "9D"]  # 2 on top, 9 at the bottom
    assert [(e["attack"], e["health"]) for e in enemies] == [(2, 10), (3, 15), (4, 20), (5, 25), (6, 30), (7, 35), (8, 40), (9, 45)]
    assert all("corrupted" in e["flags"] for e in enemies)
    assert enemies[2]["suits"] == ["D", "U"]     # keeps her sticker as an enemy
    assert not any(d["id"] in extra_ids for d in c.away for extra_ids in [[p["id"] for p in extra["party"]]])
    # save round trip keeps the away cards
    c2 = CampaignState.from_dict(json.loads(json.dumps(c.to_dict())))
    assert c2.away == c.away
    steps = M.reward_steps(c, 10, rng)
    assert [s["kind"] for s in steps] == ["remove_card", "away_return"]
    for s in steps:
        M.apply_step(c, s, rng)
    assert P.find(c.party, "GOR8E") is None and c.away == []
    assert sorted(P.corrupted_ids(c.party)) == ["2S", "3H", "4D", "5C", "6C", "7S", "8H", "9D"]
    assert P.find(c.party, "4D")["suits"] == ["D", "U"]


def test_mission11_rips_up_the_corrupted_six_beast_deck_and_reborn_evergreen():
    c = CampaignState.new(1, ["Solo"], seed=130)
    c.mission = 11
    c.completed = list(range(1, 11))
    P.add_card(c.party, dict(M.ASH))
    c.flags["beasts"] = True
    c.beast = "B_D"
    for cid in ("2S", "3H", "4D", "5C", "6H", "7S", "8H", "9D"):
        P.add_flag(c.party, cid, "corrupted")
        c.corrupted.append(cid)
    rng = random.Random(8)
    # the setup card: the corrupted 6 (any class, corruption is random) is ripped up
    assert not c.prepare_mission()
    steps = M.start_steps(c, 11)
    assert [s["kind"] for s in steps] == ["rip_up"] and steps[0]["card_id"] == "6H"
    line = M.apply_step(c, steps[0], rng)
    assert "ripped up" in line and P.find(c.party, "6H") is None and "6H" not in c.corrupted
    assert c.flags["vine_ripped"] is True and M.start_steps(c, 11) == []
    extra = M.build_setup(c, 11, rng)
    enemies = extra["castle"]
    assert [e["name"] for e in enemies] == ["Justicar"] * 4 + ["Corrupted Evergreen"]
    assert (enemies[0]["attack"], enemies[0]["health"], enemies[-1]["attack"], enemies[-1]["health"]) == (10, 30, 20, 90)
    assert all(e["suits"] == [] for e in enemies)
    assert sorted(b["id"] for b in extra["beast_deck"]) == ["B_C", "B_D", "B_H", "B_S"]
    ids = [d["id"] for d in extra["party"]]
    assert "B_D" not in ids and "B_ASH" in ids             # no chosen beast this mission; Ash stays
    for s in M.reward_steps(c, 11, rng):
        M.apply_step(c, s, rng)
    esme = P.find(c.party, "ESME6E")
    assert esme is not None and esme["value"] == 6 and sorted(esme["suits"]) == ["C", "D", "H", "S"]
    assert "ignores_immunity" in esme["flags"] and "corrupted" not in esme["flags"]
    assert len(c.corrupted) == 7
    # no corrupted 6: nothing is ripped up, the flag is still set
    c2 = CampaignState.new(1, ["Solo"], seed=133)
    c2.mission = 11
    steps = M.start_steps(c2, 11)
    assert steps[0]["card_id"] is None
    assert "nobody" in M.apply_step(c2, steps[0], rng) and c2.flags["vine_ripped"]


def test_mission12_setup_restores_the_party_and_swaps_the_mother_relic():
    c = CampaignState.new(1, ["Solo"], seed=140)
    c.mission = 12
    c.completed = list(range(1, 12))
    P.add_card(c.party, dict(M.ESME_REBORN))
    P.add_card(c.party, dict(M.ASH))
    c.relics += ["flute", "whistle", "emblem", "mother"]
    for cid in ("2S", "3H", "4D", "5C", "7S", "8H", "9D"):
        P.add_flag(c.party, cid, "corrupted")
        c.corrupted.append(cid)
    rng = random.Random(9)
    steps = M.start_steps(c, 12)
    assert [s["kind"] for s in steps] == ["restore_all", "relic_swap"]
    for s in steps:
        M.apply_step(c, s, rng)
    assert P.corrupted_ids(c.party) == [] and c.corrupted == []
    assert sorted(P.restored_ids(c.party)) == ["2S", "3H", "4D", "5C", "7S", "8H", "9D", "ESME6E"]
    assert "mother" not in c.relics and "mother_restored" in c.relics and "flute" in c.relics
    assert M.start_steps(c, 12) == []
    extra = M.build_setup(c, 12, rng)
    enemies = extra["castle"]
    assert [e["name"].split()[-1] for e in enemies] == ["Queen"] * 4 + ["King"] * 4 + ["Arcana"]
    assert (enemies[0]["attack"], enemies[0]["health"]) == (15, 30)
    assert (enemies[4]["attack"], enemies[4]["health"]) == (20, 40)
    assert (enemies[-1]["attack"], enemies[-1]["health"], enemies[-1]["suits"]) == (25, 120, [])
    assert all("corrupted" in e["flags"] for e in enemies)
    assert sorted(e["suits"][0] for e in enemies[:4]) == ["C", "D", "H", "S"]
    steps = M.reward_steps(c, 12, rng)
    assert [s["kind"] for s in steps] == ["set_flag"]
    M.apply_step(c, steps[0], rng)
    assert c.flags["pack_e_opened"] is True


def test_mission3_yield_still_runs_end_of_turn_effects():
    c, g = _mission3(players=2, seed=55)
    set_tavern_top(g, ["4H", "3S"])
    assert g.can_yield()
    g.yield_turn()
    # the yielding player suffers, then the end of turn puts the top reserve card in the zone
    if g.phase == "suffer":
        g.suffer(sorted(g.active_player.hand, key=lambda x: -g.cards[x].value)[:3])
    assert g.mission_zone == ["4H"] and g.active == 1
