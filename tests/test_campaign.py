"""Regicide Legacy campaign: missions 1-9, rewards, losses, mercenaries, relics, rules."""
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
        ids = g.all_card_ids()
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
    assert "5R" not in cands and "3R" not in cands         # Reavers are not the original deck
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


def test_only_the_original_reserve_deck_is_ever_corrupted():
    """Mission 10 has rules for the original classes as enemies, none for corrupted mages or
    class-deck members: corruption picks only from the 40 starting cards, stickers and all."""
    party = P.starting_party()
    for card in list(M.MAGE_DECK) + list(M.REAVERS) + list(M.GUARDIANS) + list(M.DRUIDS) + list(M.CHANTERS):
        if P.find(party, str(card["id"])) is None:
            P.add_card(party, dict(card))
    P.add_card(party, dict(M.ESME_REBORN))
    P.add_card(party, dict(M.GORAN_RENEWED))
    P.add_suit(party, "8C", "G")                           # a class sticker keeps it original
    cands = P.corruption_candidates(party)
    assert cands and all(cid in P.ORIGINAL_IDS for cid in cands)
    assert "8C" in cands and not any(cid.endswith("M") for cid in cands)
    for seed in range(200):
        p = [dict(c, flags=list(c.get("flags", []))) for c in party]
        rng = random.Random(seed)
        for _ in range(8):
            tgt = P.pick_corruption_target(p, rng)
            assert tgt in P.ORIGINAL_IDS, tgt
            P.add_flag(p, tgt, "corrupted")
        assert P.pick_corruption_target(p, rng) is None
    # the choice form (a choice step offers the candidates) offers originals only too
    c = CampaignState.new(1, ["Ana"], seed=4)
    for card in M.MAGE_DECK:
        if P.find(c.party, str(card["id"])) is None:
            P.add_card(c.party, dict(card))
    assert all(cid in P.ORIGINAL_IDS for cid in P.corruption_candidates(c.party))


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
    # themeless: plain cards, rank and class only (no names, no races)
    assert [P.to_card(P.find(c.party, x)).label() for x in ("3R", "5R", "7R", "9R")] == ["3⛏︎", "5⛏︎", "7⛏︎", "9⛏︎"]
    assert all("name" not in P.find(c.party, x) and "subtitle" not in P.find(c.party, x) for x in ("3R", "5R", "7R", "9R"))
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
    assert [P.to_card(P.find(c.party, x)).label() for x in ("3G", "5G", "7G", "9G")] == ["3♜", "5♜", "7♜", "9♜"]
    assert all("name" not in P.find(c.party, x) for x in ("3G", "5G", "7G", "9G"))
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
        assert sorted(g.all_card_ids()) == sorted(g.cards)
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
    assert [P.to_card(P.find(c.party, x)).label() for x in ("3U", "5U", "7U", "9U")] == ["3☘︎", "5☘︎", "7☘︎", "9☘︎"]
    assert all("name" not in P.find(c.party, x) for x in ("3U", "5U", "7U", "9U"))
    assert M.start_steps(c, 7) == []
    extra = M.build_setup(c, 7, rng)
    enemies = extra["castle"]
    assert [e["name"] for e in enemies] == ["Shoal Pondkin"] * 4 + ["Deep Pondkin"] * 4 + ["Abyssal Pondkin"] * 4
    assert (enemies[0]["attack"], enemies[0]["health"], enemies[-1]["attack"], enemies[-1]["health"]) == (10, 20, 20, 40)
    pil = extra["pilgrims"]
    # pack P: four classless pilgrims of every strength 2 to 7, no ace (it is in mission 8's box)
    assert len(pil) == 24 and all("pilgrim" in d["flags"] and d["suits"] == [] for d in pil)
    assert sorted(d["value"] for d in pil) == sorted([v for v in range(2, 8) for _ in range(4)])
    assert len({d["id"] for d in pil}) == 24 and M.PUPPY["id"] not in {d["id"] for d in pil}
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
    assert [P.to_card(P.find(c.party, x)).label() for x in ("3T", "5T", "7T", "9T")] == ["3𝄞", "5𝄞", "7𝄞", "9𝄞"]
    assert all("name" not in P.find(c.party, x) for x in ("3T", "5T", "7T", "9T"))
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
        names.setdefault(d["value"], set()).add(P.to_card(d).label())
    # themeless: every pilgrim is a plain classless card, "Pilgrim 2" to "Pilgrim 7"
    assert all(names[v] == {"Pilgrim %d" % v} for v in names) and not any("name" in d for d in extra["pilgrims_in_reserve"])
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


# ---------------------------------------------------------------- Beasts (rulebook p.14, p.21)
def _beast_game(players=1, seed=400, relics=(), beast="B_C", corrupted=()):
    """A mission 1 attempt with Gøran's beasts available and one of them chosen."""
    names = ["Ana", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.flags["beasts"] = True
    c.set_beast(beast)
    c.relics.extend(relics)
    for cid in corrupted:
        P.add_flag(c.party, cid, "corrupted")
    g = c.start_attempt(seed=seed)
    return c, g


def test_beast_pairs_like_a_companion_and_copies_its_partners_strength():
    c, g = _beast_game()
    beast = g.cards["B_C"]
    assert beast.has("beast") and beast.rank == "B" and beast.value == 0 and beast.defence_value == 0
    assert sorted(g.all_card_ids()) == sorted(g.cards)
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["B_C", "7H", "5D", "5S", "AS", "9S"])
    plays = [sorted(p) for p in g.legal_plays()]
    assert ["B_C"] in plays and ["7H", "B_C"] in plays and ["AS", "B_C"] in plays and ["5D", "B_C"] in plays
    assert plays.count(["AS", "B_C"]) == 1
    assert g.check_play(["B_C", "7H"]) == (True, "companion")
    assert g.check_play(["B_C", "5D", "5S"])[0] is False          # a beast never joins a kinfolk set
    assert g.check_play(["5D", "5S"]) == (True, "set")
    g.play(["B_C", "7H"])
    play = g.plays[0]
    assert play.value == 14 and set(play.suits) == {"C", "H"}      # the beast copies the 7
    powers = dict(_powers(g))
    assert powers["H"]["value"] == 14 and powers["C"]["doubled"]
    assert g.enemy.hp == 100 - 28 and g.phase == PHASE_SUFFER
    # companion + beast: the beast copies the companion's 1
    c, g = _beast_game(seed=401)
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["B_C", "AS", "9S", "8S"])
    g.play(["AS", "B_C"])
    assert g.plays[0].value == 2 and set(g.plays[0].suits) == {"S", "C"} and g.enemy.hp == 100 - 4
    assert g.shield == 2


def test_beast_alone_is_a_legal_play_of_strength_zero_and_discards_for_zero():
    c, g = _beast_game(seed=402)
    set_enemy(g, "J", "H")
    set_hand(g, ["B_C", "9S", "AS", "3D"])
    g.play(["B_C"])
    played = [ev for ev in g.last_events if ev["t"] == "play"][0]
    assert played["value"] == 0 and played["kind"] == "single"
    assert dict(_powers(g))["C"]["doubled"] and g.enemy.hp == 20     # doubling 0 is still 0
    assert g.phase == PHASE_SUFFER and g.pending_damage == 10
    with pytest.raises(IllegalAction):
        g.suffer(["B_C", "3D"])                                        # 0 + 3 does not cover 10
    g.suffer(["9S", "AS"])
    assert g.phase == PHASE_PLAY and g.turn == 2 and g.plays[0].card_ids == ["B_C"] and g.players[0].hand == ["3D"]
    # a beast never pairs with a Jester and never joins the Kinfolk Flute
    c, g = _beast_game(players=3, seed=403, relics=["flute"])
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_enemy(g, "J", "H")
    set_hand(g, ["5C", "9S", "8S"], player=0)
    set_hand(g, ["B_C", jester, "5D"], player=1)
    assert g.check_play([jester, "B_C"])[0] is False
    g.play(["5C"])
    assert g.deciding == 1 and _adds(g) == [("5D",)]


# ---------------------------------------------------------------- Scarlet Whistle (both sides)
def test_scarlet_whistle_solo_takes_the_top_of_the_discard_pile_or_skips():
    from helpers import set_discard
    c, g = _beast_game(seed=410, relics=["whistle"])
    set_enemy(g, "J", "H")
    set_hand(g, ["AS", "B_C", "7H", "3D", "9S"])
    set_discard(g, ["6D", "2H"])
    g.play(["AS"])
    assert g.phase == PHASE_DECIDE and g.deciding == 0 and g.active == 0
    assert g.decision["kind"] == "whistle_take" and g.decision["card"] == "6D" and g.decision["play_index"] == 0
    acts = g.legal_actions()
    assert [a["label"] for a in acts] == ["Add 6♦ from the discard pile", "Skip"] and acts[1]["skip"]
    assert g.legal_plays() == []
    with pytest.raises(IllegalAction):
        g.decide({"type": "whistle_take", "card": "2H"})
    g.decide({"type": "whistle_take", "card": "6D"})
    play = g.plays[0]
    assert play.card_ids == ["AS", "6D"] and play.value == 7 and set(play.suits) == {"S", "D"}
    assert g.discard == ["2H"] and g.decision is None
    assert any(ev["t"] == "whistle_take" and ev["card"] == "6D" and ev["value"] == 7 for ev in g.last_events)
    powers = dict(_powers(g))
    assert powers["D"]["value"] == 7 and powers["S"]["shield"] == 7
    assert g.enemy.hp == 20 - 7 and g.shield == 7 and g.phase == PHASE_SUFFER and g.pending_damage == 3
    assert sorted(g.all_card_ids()) == sorted(g.cards)
    # skipping resolves the attack as formed
    c, g = _beast_game(seed=411, relics=["whistle"])
    set_enemy(g, "J", "H")
    set_hand(g, ["B_C", "7H", "3D", "9S", "8S"])
    set_discard(g, ["6D"])
    g.play(["B_C"])
    assert g.decision["kind"] == "whistle_take"
    g.decide({"type": "whistle_skip"})
    assert g.decision is None and g.plays[0].card_ids == ["B_C"] and g.plays[0].value == 0
    assert g.enemy.hp == 20 and g.discard == ["6D"] and g.phase == PHASE_SUFFER
    assert any(ev["t"] == "whistle_skip" for ev in g.last_events)
    # a beast copies the card it takes: beast + 6♦ is a 12, doubled by the beast's class
    c, g = _beast_game(seed=412, relics=["whistle"])
    set_enemy(g, "J", "H", hp=30)
    set_hand(g, ["B_C", "7H", "3D", "9S", "8S"])
    set_discard(g, ["6D"])
    g.play(["B_C"])
    g.decide({"type": "whistle_take", "card": "6D"})
    assert g.plays[0].value == 12 and set(g.plays[0].suits) == {"C", "D"} and g.enemy.hp == 30 - 24
    # no decision with an empty discard pile, for a two-card attack, or without the relic
    c, g = _beast_game(seed=413, relics=["whistle"])
    set_enemy(g, "J", "H")
    set_hand(g, ["AS", "B_C", "7H", "3D", "9S"])
    g.discard = []
    g.play(["AS"])
    assert g.decision is None and g.phase == PHASE_SUFFER
    c, g = _beast_game(seed=414, relics=["whistle"])
    set_enemy(g, "J", "H")
    set_hand(g, ["AS", "B_C", "7H", "3D", "9S"])
    set_discard(g, ["6D"])
    g.play(["AS", "7H"])
    assert g.decision is None
    c, g = _beast_game(seed=415)
    set_enemy(g, "J", "H")
    set_hand(g, ["AS", "B_C", "7H", "3D", "9S"])
    set_discard(g, ["6D"])
    g.play(["AS"])
    assert g.decision is None
    # the forecast assumes nothing is taken
    c, g = _beast_game(seed=416, relics=["whistle"])
    set_enemy(g, "J", "H")
    set_hand(g, ["AS", "B_C", "7H", "3D", "9S"])
    set_discard(g, ["6D"])
    pv = g.preview_play(["AS"])
    assert pv["ok"] and pv["decision"] and pv["decision_kind"] == "whistle_take" and pv["damage"] == 1
    assert g.discard == ["6D"] and g.decision is None


def test_scarlet_whistle_taken_corrupted_card_banishes_and_ignores_immunity():
    from helpers import set_discard
    c, g = _beast_game(seed=417, relics=["whistle"], corrupted=("6D",))
    set_enemy(g, "J", "D")                           # immune to bards
    set_hand(g, ["AS", "7H", "3D", "9S"])
    set_discard(g, ["6D"])
    g.play(["AS"])
    top = g.tavern[0]
    g.decide({"type": "whistle_take", "card": "6D"})
    assert g.banished == [top] and any(ev["t"] == "corrupt_banish" for ev in g.last_events)
    bards = dict(_powers(g))["D"]
    assert not bards.get("immune") and bards["value"] == 7
    assert g.plays[0].value == 7 and g.enemy.hp == 13


def test_scarlet_whistle_multiplayer_asks_the_others_clockwise_until_one_adds():
    c, g = _beast_game(players=3, seed=420, relics=["whistle"])
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_enemy(g, "J", "H")
    set_hand(g, ["AS", "9S", "8S"], player=0)
    set_hand(g, ["7C", jester], player=1)
    set_hand(g, ["4D", "3H"], player=2)
    g.play(["AS"])
    assert g.phase == PHASE_DECIDE and g.active == 0 and g.deciding == 1
    assert g.decision["kind"] == "whistle_add" and g.decision["queue"] == [2] and g.decision["play_index"] == 0
    acts = g.legal_actions()
    assert [a["label"] for a in acts] == ["Add 7♣ to the attack", "Pass"] and acts[-1]["skip"]   # never a Jester
    with pytest.raises(IllegalAction):
        g.decide({"type": "whistle_add", "card": jester})
    with pytest.raises(IllegalAction):
        g.decide({"type": "whistle_add", "card": "4D"})          # not Ben's card
    g.decide({"type": "whistle_pass"})
    assert g.phase == PHASE_DECIDE and g.deciding == 2 and g.decision["queue"] == []
    assert any(ev["t"] == "whistle_pass" and ev["player"] == 1 for ev in g.last_events)
    assert [a["card"] for a in g.legal_actions() if a.get("card")] == ["4D", "3H"]
    g.decide({"type": "whistle_add", "card": "4D"})
    assert g.decision is None and g.plays[0].card_ids == ["AS", "4D"] and g.plays[0].value == 5
    assert "4D" not in g.players[2].hand and g.players[1].hand[:2] == ["7C", jester]   # the bards drew for everyone
    assert g.enemy.hp == 15 and g.shield == 5 and g.phase == PHASE_SUFFER and g.active == 0 and g.pending_damage == 5
    assert sorted(g.all_card_ids()) == sorted(g.cards)
    # the first player to add ends the round: Cy is not asked; a beast copies the newcomer
    c, g = _beast_game(players=3, seed=421, relics=["whistle"])
    set_enemy(g, "J", "H")
    set_hand(g, ["B_C", "9S", "8S"], player=0)
    set_hand(g, ["7C", "2D"], player=1)
    set_hand(g, ["4D"], player=2)
    g.play(["B_C"])
    assert g.deciding == 1
    g.decide({"type": "whistle_add", "card": "7C"})
    assert g.decision is None and g.plays == [] and g.enemies_defeated == 1     # 14 doubled: 28 damage
    assert g.players[2].hand == ["4D"] and g.active == 0 and g.phase == PHASE_PLAY
    # players holding nothing but Jesters are skipped; when everyone passes the attack resolves as formed
    c, g = _beast_game(players=3, seed=422, relics=["whistle"])
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_enemy(g, "J", "H")
    set_hand(g, ["AS", "9S", "8S"], player=0)
    set_hand(g, [jester], player=1)
    set_hand(g, ["4D"], player=2)
    g.play(["AS"])
    assert g.deciding == 2 and g.decision["queue"] == []
    g.decide({"type": "whistle_pass"})
    assert g.decision is None and g.plays[0].card_ids == ["AS"] and g.enemy.hp == 19 and g.phase == PHASE_SUFFER
    # nobody can add: no decision at all; the forecast assumes nobody adds
    c, g = _beast_game(players=2, seed=423, relics=["whistle"])
    set_enemy(g, "J", "H")
    set_hand(g, ["AS", "9S", "8S"], player=0)
    set_hand(g, [], player=1)
    g.play(["AS"])
    assert g.decision is None and g.phase == PHASE_SUFFER
    c, g = _beast_game(players=2, seed=424, relics=["whistle"])
    set_enemy(g, "J", "H")
    set_hand(g, ["AS", "9S", "8S"], player=0)
    set_hand(g, ["7C"], player=1)
    pv = g.preview_play(["AS"])
    assert pv["decision_kind"] == "whistle_add" and pv["damage"] == 1 and g.players[1].hand == ["7C"]
    # the one-ply bot adds only to finish the enemy
    g.enemy.hp = 8
    g.play(["AS"])
    assert greedy_policy(g) == {"type": "whistle_add", "player": 1, "card": "7C", "label": "Add 7♣ to the attack"}
    g.enemy.hp = 20
    assert greedy_policy(g)["type"] == "whistle_pass"


def test_whistle_decision_survives_a_save_round_trip_and_bots_play_with_it():
    c, g = _beast_game(players=2, seed=425, relics=["whistle"])
    set_enemy(g, "J", "H")
    set_hand(g, ["AS", "9S", "8S"], player=0)
    set_hand(g, ["7C", "2D"], player=1)
    g.play(["AS"])
    g2 = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    assert g2.decision == g.decision and g2.legal_actions() == g.legal_actions() and g2.deciding == 1
    g2.decide({"type": "whistle_add", "card": "2D"})
    assert g2.plays[0].value == 3 and g2.phase == PHASE_SUFFER
    # the random bot picks either whistle option; both bots play whole games with the relic
    rng = random.Random(7)
    seen = set()
    for _ in range(30):
        g3 = Game.from_dict(json.loads(json.dumps(g.to_dict())))
        act = random_policy(g3, rng)
        assert act["type"] in ("whistle_add", "whistle_pass")
        apply_action(g3, act)
        seen.add(act["type"])
        assert g3.phase == PHASE_SUFFER and sorted(g3.all_card_ids()) == sorted(g3.cards)
    assert seen == {"whistle_add", "whistle_pass"}
    offers = 0
    for players in (1, 2, 3):
        for seed in range(6):
            c, g = _beast_game(players=players, seed=430 + seed, relics=["whistle", "flute"], beast="B_H")
            play_out(g, greedy_policy if seed % 2 == 0 else random_policy, rng)
            assert g.is_over and g.decision is None
            assert sorted(g.all_card_ids()) == sorted(g.cards)
            offers += sum(1 for line in g.log if line.startswith("Scarlet Whistle:"))
    assert offers > 0


# ---------------------------------------------------------------- Reavers (rulebook p.17, p.22)
def _reaver_game(players=1, seed=440):
    names = ["Ana", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    for r in M.REAVERS:
        P.add_card(c.party, dict(r))
    g = c.start_attempt(seed=seed)
    return c, g


def test_reaver_example_five_warrior_five_reaver_reveal_two_add_seven_deals_68():
    c, g = _reaver_game()
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["5C", "5R", "9S", "8S", "7S"])
    set_tavern_top(g, ["7H", "2D", "3D"])
    assert g.check_play(["5C", "5R"]) == (True, "set")
    g.play(["5C", "5R"])
    # step 3 pauses on the reaver before the warrior: the attacker chooses how many to reveal
    assert g.phase == PHASE_DECIDE and g.deciding == 0 and g.active == 0
    d = g.decision
    assert d["kind"] == "reaver_count" and d["damage"] == 10 and d["done_suits"] == ["R"] and d["resume"] == "resolve"
    acts = g.legal_actions()
    assert [a["label"] for a in acts][:3] == ["Reveal 1", "Reveal 2", "Reveal 3"] and len(acts) == len(g.tavern)
    assert [a["count"] for a in acts] == list(range(1, len(g.tavern) + 1)) and not any(a.get("skip") for a in acts)
    assert g.enemy.hp == 100 and g.tavern[0] == "7H"
    with pytest.raises(IllegalAction):
        g.decide({"type": "reaver_count", "count": 0})
    with pytest.raises(IllegalAction):
        g.decide({"type": "reaver_count", "count": len(g.tavern) + 1})
    g.decide({"type": "reaver_count", "count": 2})
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "reaver_pick" and g.decision["revealed"] == ["7H", "2D"]
    assert g.tavern[0] == "3D" and sorted(g.all_card_ids()) == sorted(g.cards)
    assert any(ev["t"] == "reaver_reveal" and ev["revealed"] == ["7H", "2D"] for ev in g.last_events)
    assert [a["label"] for a in g.legal_actions()] == ["Add 7♥'s strength (+7)", "Add 2♦'s strength (+2)"]
    with pytest.raises(IllegalAction):
        g.decide({"type": "reaver_pick", "card": "3D"})
    g.decide({"type": "reaver_pick", "card": "7H"})
    # 10 + 7 = 17, the reaver doubles to 34, the warrior to 68; both revealed cards are banished
    assert g.decision is None and g.banished == ["2D", "7H"]
    powers = dict(_powers(g))
    assert powers["R"]["added"] == 7 and powers["R"]["doubled"] and powers["C"]["doubled"]
    assert [s for s, _ in _powers(g)] == ["R", "C"]
    assert any(ev["t"] == "damage" and ev["amount"] == 68 for ev in g.last_events)
    assert any(ev["t"] == "reaver_pick" and ev["card"] == "7H" and ev["damage"] == 34 for ev in g.last_events)
    assert g.enemy.hp == 32 and g.phase == PHASE_SUFFER
    assert g.plays[0].card_ids == ["5C", "5R"] and g.plays[0].value == 10   # the 7 did not join the attack
    assert sorted(g.all_card_ids()) == sorted(g.cards)


def test_reaver_immunity_empty_reserve_forecast_and_save_round_trip():
    # immunity blocks the whole ability: no reveal, no doubling
    c, g = _reaver_game(seed=441)
    set_enemy(g, "K", "H", hp=100)
    g.enemy.suits = ("R",)
    set_hand(g, ["5R", "9S", "8S"])
    reserve = list(g.tavern)
    g.play(["5R"])
    assert dict(_powers(g))["R"]["immune"] and g.decision is None and g.tavern == reserve
    assert g.enemy.hp == 95 and g.banished == []
    # an empty reserve: nothing to reveal, the damage is still doubled
    c, g = _reaver_game(seed=442)
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["5R", "9S", "8S"])
    g.discard = g.tavern + g.discard
    g.tavern = []
    g.play(["5R"])
    assert g.decision is None and g.enemy.hp == 90 and dict(_powers(g))["R"]["result"]["doubled"]
    # the forecast assumes a reveal that adds 0 (then doubles) and leaves the reserve alone
    c, g = _reaver_game(seed=443)
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["5C", "5R", "9S", "8S"])
    before = list(g.tavern)
    pv = g.preview_play(["5C", "5R"])
    assert pv["ok"] and pv["decision"] and pv["decision_kind"] == "reaver_count" and pv["damage"] == 40
    assert pv["powers"]["R"]["added"] == 0 and pv["powers"]["R"]["forecast"] and pv["enemy_hp_after"] == 60
    assert g.tavern == before and g.decision is None and g.banished == []
    # a save in either reaver decision resumes with the same options
    set_tavern_top(g, ["7H", "2D", "3D"])
    g.play(["5C", "5R"])
    g2 = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    assert g2.decision == g.decision and g2.legal_actions() == g.legal_actions()
    g.decide({"type": "reaver_count", "count": 2})
    g2.decide({"type": "reaver_count", "count": 2})
    g3 = Game.from_dict(json.loads(json.dumps(g2.to_dict())))
    assert g3.decision["kind"] == "reaver_pick" and g3.decision["revealed"] == ["7H", "2D"]
    assert sorted(g3.all_card_ids()) == sorted(g3.cards) and g3.legal_actions() == g.legal_actions()
    g3.decide({"type": "reaver_pick", "card": "2D"})
    g.decide({"type": "reaver_pick", "card": "2D"})
    assert g3.to_dict() == g.to_dict() and g.enemy.hp == 100 - 48
    # bots: reveal one card and take the strongest
    c, g = _reaver_game(seed=444)
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["5R", "9S", "8S"])
    set_tavern_top(g, ["3D", "7H"])
    g.play(["5R"])
    act = greedy_policy(g)
    assert act["type"] == "reaver_count" and act["count"] == 1
    apply_action(g, act)
    assert g.decision["revealed"] == ["3D"]
    assert greedy_policy(g) == g.legal_actions()[0]
    apply_action(g, greedy_policy(g))
    assert g.enemy.hp == 100 - 16 and g.banished == ["3D"]
    c, g = _reaver_game(seed=445)
    set_enemy(g, "K", "H", hp=100)
    set_hand(g, ["5R", "9S", "8S"])
    set_tavern_top(g, ["3D", "7H"])
    g.play(["5R"])
    g.decide({"type": "reaver_count", "count": 2})
    assert greedy_policy(g)["card"] == "7H"


# ---------------------------------------------------------------- Guardians (rulebook p.18)
def test_guardian_prevents_the_players_damage_for_the_turn():
    c = CampaignState.new(1, ["Ana"], seed=450)
    for gd in M.GUARDIANS:
        P.add_card(c.party, dict(gd))
    g = c.start_attempt(seed=450)
    set_enemy(g, "K", "H")
    set_hand(g, ["5G", "9S", "2D"])
    g.play(["5G"])
    assert dict(_powers(g))["G"]["result"] == {"guardian": True}
    assert g.enemy.hp == 35
    # no damage to suffer: straight to the next turn, the hand untouched, the flag gone
    assert any(ev["t"] == "no_damage" and ev.get("guardian") for ev in g.last_events)
    assert g.phase == PHASE_PLAY and g.turn == 2 and g.players[0].hand == ["9S", "2D"]
    assert "guardian" not in g.extra
    set_hand(g, ["2D", "9S", "8S", "7S"])
    g.play(["2D"])
    assert g.phase == PHASE_SUFFER and g.pending_damage == 20       # the next turn is unprotected
    # immunity to guardians blocks it
    c = CampaignState.new(1, ["Ana"], seed=451)
    for gd in M.GUARDIANS:
        P.add_card(c.party, dict(gd))
    g = c.start_attempt(seed=451)
    set_enemy(g, "K", "H")
    g.enemy.suits = ("G",)
    set_hand(g, ["7G", "9S", "8S", "7S"])
    g.play(["7G"])
    assert dict(_powers(g))["G"]["immune"] and g.phase == PHASE_SUFFER and g.pending_damage == 20
    assert "guardian" not in g.extra


# ---------------------------------------------------------------- Mission 4: Fusion of Darkness
def _mission4(players=1, seed=460, merc_25=False):
    names = ["Ana", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.mission = 4
    c.completed = [1, 2, 3]
    c.relics.append("flute")
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    if merc_25:
        c.m_box_opened = True
        c.coins = 1
        c.hire("merc_25H")
    g = c.start_attempt(seed=seed)
    return c, g


def test_mission4_enemy_strength_follows_the_top_of_the_discard_pile():
    from helpers import set_discard, set_mission_enemy
    c, g = _mission4(merc_25=True)
    assert g.config.rules_id == "legacy_m4" and MISSIONS[3]["playable"]
    enemies = [g.cards[x] for x in [g.enemy.card_id] + g.castle]
    assert [e.name for e in enemies] == ["Phase I Experiment"] * 4 + ["Phase II Experiment"] * 4 + ["Phase III Experiment"] * 4
    assert all(e.has("corrupted") for e in enemies)
    assert [(e.attack, e.health) for e in enemies][::4] == [(10, 20), (15, 30), (20, 40)]
    set_mission_enemy(g, "LABJD")                     # a Phase I bard: immune to bards
    assert g.enemy_attack == 10 and g.rules.attack_bonus(g) == 0
    set_discard(g, ["7D", "2S"])
    assert g.rules.attack_bonus(g) == 7 and g.enemy_attack == 17
    set_discard(g, ["M25H", "7D"])                    # a 2/5 counts 2
    assert g.enemy_attack == 12
    # a cleric's shuffle changes the top card, and with it the enemy's strength
    set_discard(g, ["7D", "2S", "3S", "4S", "6C"])
    set_hand(g, ["4H", "9S", "8S", "AS"])
    assert g.enemy_attack == 17
    g.play(["4H"])
    assert len(g.discard) == 1 and g.enemy.hp == 16
    assert g.enemy_attack == 10 + g.rules.strength(g.cards[g.discard[0]]) == g.pending_damage
    # frozen while suffering: the damage was fixed when the step began
    due = g.pending_damage
    g.discard.insert(0, "7D") if "7D" in g.tavern and not g.tavern.remove("7D") else None
    assert g.pending_damage == due
    # a defeated experiment on top of the pile adds its printed strength (10)
    c, g = _mission4(seed=461)
    set_mission_enemy(g, "LABJD", hp=5)
    set_hand(g, ["9S", "8S", "AS"])
    g.play(["9S"])                                    # 9: not exact, the experiment goes to the discard pile
    assert g.enemies_defeated == 1 and g.discard == ["9S", "LABJD"]   # the played card on top (p.19)
    assert g.enemy_attack == 10 + 9
    g.discard.remove("9S")
    g.discard.append("9S")
    assert g.enemy_attack == 10 + 10


def test_mission4_cleanup_asks_what_order_offering_the_order_the_cards_entered_play():
    from helpers import keep_played_order, set_discard, set_mission_enemy
    c, g = _mission4(seed=462)
    set_mission_enemy(g, "LABJD", hp=10)
    set_hand(g, ["AS", "9C", "3D", "2H"])
    set_discard(g, ["7D"])
    g.play(["AS", "9C"])                              # 10, doubled: 20, not exact
    # p.19 "in any order you wish": the top of the discard pile feeds the next enemy, so the
    # player names the order, offered in the order the cards entered play (as selected);
    # keeping it, the experiment goes to the pile first, the played cards on top of it, 9♣
    # (selected last) on top
    d = g.decision
    assert d["kind"] == "played_discard_order" and d["options"] == ["AS", "9C"] and d["resume"] == "defeat"
    assert g.enemies_defeated == 0 and g.discard == ["7D"] and g.legal_actions()[0]["ordered"]
    assert keep_played_order(g) == [["AS", "9C"]]
    assert g.decision is None and g.phase == PHASE_PLAY and g.active == 0 and g.enemies_defeated == 1
    assert g.discard == ["9C", "AS", "LABJD", "7D"] and g.enemy_attack == 10 + 9
    assert [ev for ev in g.last_events if ev["t"] == "cleanup_order"] == [
        {"t": "cleanup_order", "pile": "discard", "cards": ["AS", "9C"]}]
    assert any("A♠, 9♣ (9♣ ends on top)" in line for line in g.log[-6:])
    # selected the other way round: the ace is offered last; naming 9♣ last puts it on top
    set_mission_enemy(g, "LABJS", hp=10)
    set_hand(g, ["AD", "9C", "2H"])
    g.play(["9C", "AD"])
    assert g.decision["options"] == ["9C", "AD"]
    g.decide({"type": "played_discard_order", "cards": ["AD", "9C"]})
    assert g.decision is None and g.discard[:3] == ["9C", "AD", "LABJS"] and g.enemy_attack == 10 + 9
    assert [ev["cards"] for ev in g.last_events if ev["t"] in ("played_order", "cleanup_order")] == [
        ["AD", "9C"], ["AD", "9C"]]
    assert "played_order" not in g.extra
    # one played card: nothing to order; an exact kill puts the experiment on top of the reserve
    set_mission_enemy(g, "LABJC", hp=9)
    set_hand(g, ["9D", "2H", "3S"])
    g.play(["9D"])
    assert g.decision is None and g.enemies_defeated == 3 and g.tavern[0] == "LABJC" and g.discard[0] == "9D"
    assert not any(ev["t"] == "cleanup_order" for ev in g.last_events)
    # two plays against one enemy (a multiplayer Jester, then the claimer's attack): the
    # second play's card entered play last and ends on top
    c, g = _mission4(players=3, seed=463)
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_mission_enemy(g, "LABJD", hp=9)
    set_hand(g, [jester, "4D"], player=0)
    set_hand(g, ["9S", "3H"], player=1)
    g.play([jester])
    g.choose_next(1)
    g.play(["9S"])
    assert g.decision["player"] == 1 and keep_played_order(g) == [[jester, "9S"]]
    assert g.decision is None and g.discard[:2] == ["9S", jester] and g.enemy_attack == 10 + 9
    assert sorted(g.all_card_ids()) == sorted(g.cards)


def test_mission4_defeated_experiment_plays_from_hand_as_a_corrupted_card():
    from helpers import set_mission_enemy
    c, g = _mission4(seed=464)
    set_mission_enemy(g, "LABJS", hp=9)
    set_hand(g, ["9D", "8S", "7S", "AS"])
    g.play(["9D"])                                    # exact: the paladin experiment tops the reserve
    assert g.tavern[0] == "LABJS" and g.enemies_defeated == 1
    set_hand(g, ["LABJS", "8S", "7S", "AS"])
    set_mission_enemy(g, "LABQS", hp=30)              # a Phase II paladin: immune to paladins
    assert g.check_play(["LABJS"]) == (True, "single") and g.check_play(["AS", "LABJS"]) == (True, "companion")
    assert g.check_play(["LABJS", "8S", "7S"])[0] is False
    top = g.tavern[0]
    g.play(["LABJS"])
    assert g.banished == [top] and any(ev["t"] == "corrupt_banish" and ev["card"] == "LABJS" for ev in g.last_events)
    assert g.plays[0].value == 10 and g.enemy.hp == 20
    assert dict(_powers(g))["S"]["shield"] == 10 and g.shield == 10     # its own class ignores immunity
    assert g.rules.attack_bonus(g) == 9 and g.enemy_attack == 15 + 9 - 10 and g.phase == PHASE_SUFFER
    assert sorted(g.all_card_ids()) == sorted(g.cards)


# ---------------------------------------------------------------- Mission 5: High and Mighty
def _mission5(players=1, seed=470, relics=("whistle",), beast=None):
    names = ["Ana", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.mission = 5
    c.completed = [1, 2, 3, 4]
    c.relics.extend(relics)
    P.add_card(c.party, dict(M.GORAN))
    c.flags["beasts"] = True
    c.set_beast(beast)
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    g = c.start_attempt(seed=seed)
    return c, g


def test_mission5_myla_starts_banished_and_the_banished_pile_feeds_the_zone():
    from helpers import set_mission_enemy
    c, g = _mission5()
    assert g.config.rules_id == "legacy_m5" and MISSIONS[4]["playable"] and g.rules.uses_mission_zone
    assert g.banished == ["MYLA7"] and g.mission_zone == [] and "MYLA7" not in g.tavern
    myla = g.cards["MYLA7"]
    assert myla.name == "Myla" and myla.value == 7 and myla.suits == () and myla.label() == "Myla (7)"
    assert all(x in g.cards for x in ("3R", "5R", "7R", "9R", "GOR8"))
    assert sorted(g.all_card_ids()) == sorted(g.cards)
    set_mission_enemy(g, "GRJH")                      # a Sporeling cleric
    assert g.enemy_attack == 10
    set_hand(g, ["9S", "8S", "7D", "6C"])
    g.play(["9S"])
    assert g.shield == 9 and g.pending_damage == 1
    g.suffer(["7D"])
    # end of turn: the top of the banished pile (Myla) went into the zone, the enemy grew by 7
    assert g.mission_zone == ["MYLA7"] and g.banished == [] and g.turn == 2
    assert any(ev["t"] == "zone_add" and ev["card"] == "MYLA7" and ev.get("source") == "banished" for ev in g.last_events)
    assert g.rules.attack_bonus(g) == 7 and g.enemy_attack == 10 + 7 - 9
    assert g.rules.immune_suits(g) == ("H",)          # the zone grants no immunity here
    # cards a reaver banishes feed the pile: the last banished is the next into the zone
    set_hand(g, ["5R", "8S", "6C"])
    set_tavern_top(g, ["3H", "4H"])
    g.play(["5R"])
    g.decide({"type": "reaver_count", "count": 1})
    g.decide({"type": "reaver_pick", "card": "3H"})
    assert g.banished == ["3H"] and g.enemy.hp == 40 - 9 - 16 and g.pending_damage == 8
    g.suffer(["8S"])
    assert g.mission_zone == ["MYLA7", "3H"] and g.rules.attack_bonus(g) == 10 and g.enemy_attack == 20 - 9
    # Myla plays like an ordinary card if she ever reaches a hand
    set_hand(g, ["MYLA7", "6C", "2D"])
    assert g.check_play(["MYLA7"]) == (True, "single")
    g.play(["MYLA7"])
    assert g.plays[-1].value == 7 and g.plays[-1].suits == () and g.enemy.hp == 40 - 9 - 16 - 7


def test_mission5_defeat_shuffles_enemy_and_zone_into_the_banished_pile_and_exact_kills_carry_over():
    from helpers import keep_played_order, set_mission_enemy
    c, g = _mission5(seed=471)
    set_mission_enemy(g, "GRJH", hp=12)
    set_hand(g, ["AC", "5D", "9S", "8S"])
    for cid in ("2C", "3C"):
        g.tavern.remove(cid)
        g.banished.append(cid)
    g.mission_zone = ["MYLA7"]
    g.banished.remove("MYLA7")
    assert g.enemy_attack == 17
    g.play(["AC", "5D"])                              # 6 doubled: 12, exact
    # solo with the Scarlet Whistle the top of the discard pile counts: "What order?" (p.19);
    # kept as they entered play, 5♦ (selected last) ends on top
    assert keep_played_order(g) == [["AC", "5D"]]
    assert g.enemies_defeated == 1 and g.decision is None and g.discard[0] == "5D"
    assert set(g.banished) == {"MYLA7", "2C", "3C", "GRJH"} and len(g.banished) == 4   # shuffled in, without looking
    assert g.mission_zone == [] and set(g.discard[:2]) == {"AC", "5D"}
    assert any(ev["t"] == "zone_cleared" and ev["to"] == "banish_shuffle" for ev in g.last_events)
    # carry-over: the defeated enemy's strength as it fell (10 + 7 zone, no shield)
    carry = [ev for ev in g.last_events if ev["t"] == "carry_damage"]
    assert carry and carry[0]["amount"] == 17 and g.enemy.hp == g.enemy.max_hp - 17
    assert g.phase == PHASE_PLAY and g.active == 0 and g.turn == 2 and "zone_add" not in [ev["t"] for ev in g.last_events]
    assert sorted(g.all_card_ids()) == sorted(g.cards)
    # not exact: no carry-over
    g.enemy.hp = 5
    set_hand(g, ["9S", "8S", "7C"])
    g.play(["9S"])
    assert g.enemies_defeated == 2 and g.enemy.hp == g.enemy.max_hp
    assert not any(ev["t"] == "carry_damage" for ev in g.last_events)
    # a paladin's reduction lowers the carry-over, never below 0
    c, g = _mission5(seed=472)
    set_mission_enemy(g, "GRJH", hp=19)
    set_hand(g, ["9S", "10C", "8S"])
    g.play(["9S"])                                    # 9 damage, shield 9: enemy strength 1
    g.suffer(["8S"]) if g.phase == PHASE_SUFFER else None
    assert g.mission_zone == ["MYLA7"] and g.enemy_attack == 10 + 7 - 9
    set_hand(g, ["10C", "2D"])
    g.enemy.hp = 20
    g.play(["10C"])                                   # 20: exact
    # two plays against this enemy: the second one's card entered play last, it ends on top
    assert keep_played_order(g) == [["9S", "10C"]]
    assert g.decision is None and g.enemies_defeated == 1 and g.discard[:2] == ["10C", "9S"]
    assert [ev["amount"] for ev in g.last_events if ev["t"] == "carry_damage"] == [8]
    # a chain: the carry-over kills the next enemy exactly, whose own strength carries on
    c, g = _mission5(seed=473)
    set_mission_enemy(g, "GRJH", hp=10)
    set_hand(g, ["10H", "9S", "8S"])
    for cid in ("10S", "10C", "3C"):
        g.tavern.remove(cid)
    g.mission_zone = ["MYLA7", "10S", "10C", "3C"]   # 30: the Sporeling strikes for 40
    g.banished = []
    assert g.enemy_attack == 40
    g.play(["10H"])                                   # clerics are immune: exactly 10
    assert g.enemies_defeated == 2                    # the next Sporeling (40) fell to the carry-over, exactly
    carries = [ev["amount"] for ev in g.last_events if ev["t"] == "carry_damage"]
    assert carries == [40, 10]                        # then its own 10 (the zone was banished) hits the third
    assert g.enemy.hp == g.enemy.max_hp - 10 and g.phase == PHASE_PLAY and g.active == 0
    assert set(["GRJH", "MYLA7", "10S", "10C", "3C"]) <= set(g.banished) and len(g.banished) == 6
    assert g.mission_zone == [] and sorted(g.all_card_ids()) == sorted(g.cards)


# ---------------------------------------------------------------- Mission 6: Shards of Memory
def _mission6(players=1, seed=480, relics=("whistle",), beast=None):
    names = ["Ana", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.mission = 6
    c.completed = [1, 2, 3, 4, 5]
    c.relics.extend(relics)
    P.add_card(c.party, dict(M.GORAN))
    P.add_suit(c.party, "GOR8", "C")
    P.add_card(c.party, dict(M.MYLA))
    c.flags["beasts"] = True
    c.set_beast(beast)
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    g = c.start_attempt(seed=seed)
    return c, g


def test_mission6_kill_moves_a_card_to_the_zone_rescues_one_on_exact_and_myla_deals_team_damage():
    from helpers import set_mission_enemy
    c, g = _mission6(players=2)
    assert g.config.rules_id == "legacy_m6" and MISSIONS[5]["playable"] and g.rules.uses_mission_zone
    assert g.mission_zone == ["MYLA7"] and g.banished == [] and P.find(c.party, "MYLA7") is None
    assert all(x in g.cards for x in ("3G", "5G", "7G", "9G")) and sorted(g.all_card_ids()) == sorted(g.cards)
    assert g.enemy_attack == 15 and g.rules.attack_bonus(g) == 0     # the zone adds no strength here
    set_mission_enemy(g, "GDQH", hp=9)
    assert g.rules.immune_suits(g) == ("H",)                           # and no immunity
    set_hand(g, ["9S", "8D", "AD"], player=0)
    set_hand(g, ["3H", "4D", "7S", "2C"], player=1)
    g.play(["9S"])                                                     # 9: exact
    assert g.phase == PHASE_DECIDE and g.deciding == 0 and g.enemies_defeated == 0
    assert g.decision["kind"] == "zone_move" and g.decision["options"] == ["9S"] and g.decision["exact"] is True
    assert [a["label"] for a in g.legal_actions()] == ["Move 9♠ to the mission zone"]
    with pytest.raises(IllegalAction):
        g.decide({"type": "zone_move", "card": "8D"})
    g.decide({"type": "zone_move", "card": "9S"})
    assert g.mission_zone == ["MYLA7", "9S"] and g.plays[0].card_ids == []
    assert any(ev["t"] == "zone_move" and ev["card"] == "9S" for ev in g.last_events)
    # exact damage: one zone card except Myla goes to the discard pile
    assert g.decision["kind"] == "zone_rescue" and g.decision["options"] == ["9S"]
    assert [a["card"] for a in g.legal_actions()] == ["9S"]
    with pytest.raises(IllegalAction):
        g.decide({"type": "zone_rescue", "card": "MYLA7"})
    g.decide({"type": "zone_rescue", "card": "9S"})
    assert g.discard == ["9S"] and g.mission_zone == ["MYLA7"]
    # Myla's team damage: 7, discarded one card at a time by any player
    assert g.decision["kind"] == "team_discard" and g.decision["damage"] == 7 and g.decision["paid"] == 0
    assert any(ev["t"] == "team_damage" and ev["damage"] == 7 and ev["available"] == 25 for ev in g.last_events)
    acts = g.legal_actions()
    assert sorted((a["player"], a["card"]) for a in acts) == sorted(
        [(0, "8D"), (0, "AD"), (1, "3H"), (1, "4D"), (1, "7S"), (1, "2C")])
    assert not any(a.get("skip") for a in acts) and g.legal_plays() == []
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    assert g.decision["kind"] == "team_discard" and g.legal_actions() == acts
    g.decide({"type": "team_discard", "player": 1, "card": "3H"})
    assert g.decision["kind"] == "team_discard" and g.decision["paid"] == 3 and g.discard[0] == "3H"
    assert "3H" not in g.players[1].hand and g.enemies_defeated == 0
    assert any(ev["t"] == "team_discard" and ev["remaining"] == 4 for ev in g.last_events)
    with pytest.raises(IllegalAction):
        g.decide({"type": "team_discard", "player": 0, "card": "3H"})   # gone
    g.decide({"type": "team_discard", "player": 0, "card": "AD"})
    assert g.decision["paid"] == 4
    g.decide({"type": "team_discard", "player": 1, "card": "4D"})       # 3 + 1 + 4 = 8 >= 7
    assert g.decision is None and g.enemies_defeated == 1 and g.phase == PHASE_PLAY and g.active == 0
    assert any(ev["t"] == "team_damage_done" for ev in g.last_events)
    assert g.banished == ["GDQH"] and g.mission_zone == ["MYLA7"]
    assert g.discard == ["4D", "AD", "3H", "9S"] and g.players[0].hand == ["8D"] and g.players[1].hand == ["7S", "2C"]
    assert sorted(g.all_card_ids()) == sorted(g.cards)


def test_mission6_not_exact_no_rescue_zone_grows_mage_rest_is_banished_and_the_bot_pays_cheaply():
    from helpers import set_mission_enemy
    c, g = _mission6(seed=481)
    set_mission_enemy(g, "GDQH", hp=9)
    set_hand(g, ["5M", "AS", "9S", "8S", "7S", "6S"])
    set_tavern_top(g, ["4C", "2D", "3D", "2S", "3S"])
    g.play(["5M"])
    g.decide({"type": "mage_pick", "card": "4C"})                     # 9, doubled: 18, not exact
    # solo with the Scarlet Whistle: the unchosen cards go to the discard pile in the order
    # the player names (p.16 "in any order"): the first named goes first, the last on top
    assert g.decision["kind"] == "discard_order" and g.decision["options"] == ["2D", "3D", "2S", "3S"]
    t = g.legal_actions()
    assert len(t) == 1 and t[0]["pick_from"] == ["2D", "3D", "2S", "3S"] and t[0]["needs"] == 4 and t[0]["ordered"]
    g.decide({"type": "discard_order", "cards": ["3D", "2D", "2S", "3S"]})
    assert g.decision["kind"] == "zone_move" and g.decision["options"] == ["5M", "4C"] and g.decision["exact"] is False
    assert g.discard[:4] == ["3S", "2S", "2D", "3D"]
    g.decide({"type": "zone_move", "card": "5M"})
    # no rescue; team damage is 7 + 5 = 12 and the bot covers it with the least waste
    assert g.decision["kind"] == "team_discard" and g.decision["damage"] == 12 and g.mission_zone == ["MYLA7", "5M"]
    assert "zone_rescue" not in [ev.get("kind") for ev in g.last_events]
    act = greedy_policy(g)
    assert act["type"] == "team_discard" and act["card"] == "9S"       # no single card covers 12: the largest first
    apply_action(g, act)
    assert g.decision["paid"] == 9
    act = greedy_policy(g)
    assert act["card"] == "6S"                                          # then the smallest card that covers the rest (3)
    apply_action(g, act)
    assert g.decision is None and g.enemies_defeated == 1
    assert "4C" in g.banished and "GDQH" in g.banished and "5M" in g.mission_zone and "5M" not in g.banished
    assert "9S" in g.discard and "6S" in g.discard and sorted(g.players[0].hand) == ["7S", "8S", "AS"]
    assert sorted(g.all_card_ids()) == sorted(g.cards)
    # the next kill's team damage is 12 again (the zone keeps growing)
    set_mission_enemy(g, "GDQD", hp=7)
    set_hand(g, ["7S", "8S", "10C", "9H"])
    g.play(["7S"])
    g.decide({"type": "zone_move", "card": "7S"})
    assert g.decision["kind"] == "zone_rescue" and sorted(g.decision["options"]) == ["5M", "7S"]
    g.decide({"type": "zone_rescue", "card": "5M"})
    assert g.decision["kind"] == "team_discard" and g.decision["damage"] == 14 and g.mission_zone == ["MYLA7", "7S"]


def test_mission6_team_damage_is_lost_when_the_hands_cannot_pay_and_a_guardian_prevents_it():
    from helpers import set_mission_enemy
    c, g = _mission6(players=2, seed=482)
    set_mission_enemy(g, "GDQH", hp=9)
    set_hand(g, ["9S"], player=0)
    set_hand(g, ["3H", "2C"], player=1)
    g.play(["9S"])
    g.decide({"type": "zone_move", "card": "9S"})
    g.decide({"type": "zone_rescue", "card": "9S"})
    assert g.phase == PHASE_LOST and g.decision is None and "Myla" in g.loss_reason and g.enemies_defeated == 0
    assert any(ev["t"] == "lost" for ev in g.last_events)
    # a Guardian in the killing attack: no team damage at all
    c, g = _mission6(seed=483)
    set_mission_enemy(g, "GDQH", hp=9)
    set_hand(g, ["9G", "2C"])
    g.play(["9G"])
    assert g.extra.get("guardian") and g.decision["kind"] == "zone_move"
    g.decide({"type": "zone_move", "card": "9G"})
    assert g.decision["kind"] == "zone_rescue"
    g.decide({"type": "zone_rescue", "card": "9G"})
    assert g.decision is None and g.enemies_defeated == 1 and g.players[0].hand == ["2C"]
    assert any(ev["t"] == "team_damage_prevented" and ev["damage"] == 7 for ev in g.last_events)
    assert g.phase == PHASE_PLAY and "guardian" not in g.extra         # the new turn clears it
    assert sorted(g.all_card_ids()) == sorted(g.cards)
    # the zone never grants immunity nor strength in this mission
    assert g.rules.immune_suits(g) == tuple(g.enemy.suits) and g.rules.attack_bonus(g) == 0


@pytest.mark.parametrize("number,players", [(4, 1), (4, 2), (5, 1), (5, 2), (6, 1), (6, 2)])
def test_bots_play_out_missions_4_to_6(number, players):
    builders = {4: _mission4, 5: _mission5, 6: _mission6}
    rng = random.Random(number * 10 + players)
    decisions = set()
    for seed in range(4):
        kw = {"players": players, "seed": 500 + number * 10 + seed}
        if number in (5, 6):
            kw["beast"] = ("B_H", "B_C", "B_D", "B_S")[seed]
        c, g = builders[number](**kw)
        policy = greedy_policy if seed % 2 == 0 else random_policy
        play_out(g, policy, rng)
        assert g.is_over and g.decision is None
        ids = g.all_card_ids()
        assert len(ids) == len(set(ids)) == len(g.cards)
        for line in g.log:
            for key in ("Reaver:", "Guardian:", "team damage", "mission zone", "top of the discard pile"):
                if key in line:
                    decisions.add(key)
    expected = {4: {"top of the discard pile"}, 5: {"Reaver:", "mission zone"}, 6: {"Guardian:", "mission zone"}}[number]
    assert expected <= decisions, decisions


def test_forecast_reports_a_kill_that_pauses_on_the_missions_defeat_choice():
    from helpers import set_discard, set_mission_enemy
    c, g = _mission4(seed=490)
    set_mission_enemy(g, "LABJD", hp=10)
    set_hand(g, ["AS", "9C", "3D", "2H"])
    set_discard(g, ["7D"])
    pv = g.preview_play(["AS", "9C"])                 # the kill pauses on the clean-up's "What order?"
    assert pv["ok"] and pv["defeats"] and not pv["exact"] and pv["decision_kind"] == "played_discard_order"
    assert pv["damage"] == 20 and pv["enemy_hp_after"] == 0 and g.phase == PHASE_PLAY and g.enemies_defeated == 0
    assert g.discard == ["7D"] and "played_order" not in g.extra
    c, g = _mission6(seed=491)
    set_mission_enemy(g, "GDQH", hp=9)
    set_hand(g, ["9S", "8D", "AD"])
    pv = g.preview_play(["9S"])
    assert pv["defeats"] and pv["exact"] and pv["decision_kind"] == "zone_move" and g.mission_zone == ["MYLA7"]

def test_mission3_yield_still_runs_end_of_turn_effects():
    c, g = _mission3(players=2, seed=55)
    set_tavern_top(g, ["4H", "3S"])
    assert g.can_yield()
    g.yield_turn()
    # the yielding player suffers, then the end of turn puts the top reserve card in the zone
    if g.phase == "suffer":
        g.suffer(min_waste_discard(g))
    assert g.mission_zone == ["4H"] and g.active == 1


# ================================================================ Druids, Chanters, the Evergreen Mother, missions 7 to 9
from helpers import set_discard, set_mission_enemy  # noqa: E402
from regicide.cards import Card  # noqa: E402


def _class_campaign(players=1, seed=700, cards=(), relics=(), corrupted=(), number=1):
    """A mission ``number`` attempt whose party also holds ``cards`` (e.g. the Druids)."""
    names = ["Ana", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.mission = number
    c.completed = list(range(1, number))
    for d in cards:
        if P.find(c.party, str(d["id"])) is None:
            P.add_card(c.party, dict(d))
    for cid in corrupted:
        P.add_flag(c.party, cid, "corrupted")
    c.relics.extend(relics)
    g = c.start_attempt(seed=seed)
    return c, g


def _mission(number, players=1, seed=800, relics=(), beast=None, corrupted=(), extra_cards=()):
    names = ["Ana", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.mission = number
    c.completed = list(range(1, number))
    c.relics.extend(relics)
    P.add_card(c.party, dict(M.GORAN))
    c.flags["beasts"] = True
    c.set_beast(beast)
    for d in list(M.MAGE_DECK) + list(extra_cards):
        if P.find(c.party, str(d["id"])) is None:
            P.add_card(c.party, dict(d))
    for cid in corrupted:
        P.add_flag(c.party, cid, "corrupted")
    g = c.start_attempt(seed=seed)
    return c, g


def _ids_everywhere(g):
    ids = g.all_card_ids()
    assert len(ids) == len(set(ids)) == len(g.cards), (len(ids), len(set(ids)), len(g.cards))


def _fresh_enemy(g, rank, suit):
    """A new royal enemy for the next check; the cards in play go to the discard pile first
    (``set_enemy`` simply forgets them, which breaks the card-conservation checks)."""
    for play in g.plays:
        g.discard.extend(play.card_ids)
    set_enemy(g, rank, suit)


def _rig_pilgrims(g, zone, deck_top=()):
    """Mission 7: put ``zone`` face up in the mission zone and ``deck_top`` on top of the
    pilgrim deck (pulled from wherever they are); the other pilgrims stay in the deck."""
    from helpers import _pull
    for x in list(zone) + list(deck_top):
        _pull(g, x)
    rest = [x for x in g.mission_zone + g.extra["pilgrim_deck"] if x not in zone and x not in deck_top]
    g.mission_zone = list(zone)
    g.extra["pilgrim_deck"] = list(deck_top) + rest


# ---------------------------------------------------------------- Druids
def test_druid_deals_the_discard_pile_and_each_player_assigns_four_destinations():
    c, g = _class_campaign(players=2, cards=M.DRUIDS)
    set_enemy(g, "J", "H")
    set_hand(g, ["5U", "9S"], player=0)
    set_hand(g, ["4C", "3D"], player=1)
    pile = ["2H", "3H", "4H", "5H", "6H", "7H", "8H", "AC", "7C"]
    set_discard(g, pile)
    reserve_before = list(g.tavern)
    g.play(["5U"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "druid_assign" and g.deciding == 0
    dealt = g.decision["dealt"]
    assert len(dealt[0]) == 5 and len(dealt[1]) == 4 and sorted(dealt[0] + dealt[1]) == sorted(pile)
    assert g.discard == [] and g.tavern == reserve_before
    assert any(ev["t"] == "druid_deal" for ev in g.last_events)
    acts = g.legal_actions()
    assert len(acts) == 1 and acts[0]["type"] == "druid_assign" and acts[0]["needs"] == 4
    assert acts[0]["pick_from"] == dealt[0] and acts[0]["player"] == 0 and acts[0]["slots"] == ["banish", "hand", "top", "bottom"]
    assert g.rules.druid_options(g) == dealt[0]
    a, b, c_, d_, e = dealt[0]
    with pytest.raises(IllegalAction):
        g.decide({"type": "druid_assign", "player": 0, "banish": a, "hand": a, "top": b, "bottom": c_})   # a card twice
    with pytest.raises(IllegalAction):
        g.decide({"type": "druid_assign", "player": 0, "banish": a, "hand": b, "top": c_})               # three only
    with pytest.raises(IllegalAction):
        g.decide({"type": "druid_assign", "player": 0, "banish": dealt[1][0], "hand": b, "top": c_, "bottom": d_})  # not mine
    with pytest.raises(IllegalAction):
        g.decide({"type": "druid_assign", "player": 1, "banish": a, "hand": b, "top": c_, "bottom": d_})   # not my turn
    # the dealt cards are still counted while the pile is out, across a save
    _ids_everywhere(g)
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    assert g.decision["kind"] == "druid_assign" and g.decision["dealt"] == dealt
    _ids_everywhere(g)
    g.decide({"type": "druid_assign", "player": 0, "banish": a, "hand": b, "top": c_, "bottom": d_})
    assert g.banished[-1] == a and b in g.players[0].hand and g.tavern[0] == c_ and g.tavern[-1] == d_
    assert g.decision["kind"] == "druid_assign" and g.deciding == 1 and g.decision["dealt"][0] == [e]
    assert any(ev["t"] == "druid_assign" and ev["hand"] == b for ev in g.last_events)
    # the second player has exactly four
    f, h, i, j = dealt[1]
    g.decide({"type": "druid_assign", "player": 1, "banish": f, "hand": h, "top": i, "bottom": j})
    # the rest went back to the discard pile (shuffled), then the attack resolved (5 damage)
    assert g.decision is None and g.discard == [e] and g.phase == PHASE_SUFFER
    assert g.tavern[0] == i and g.tavern[-1] == j and g.tavern[1] == c_ and g.tavern[-2] == d_
    assert h in g.players[1].hand and g.banished[-2:] == [a, f]
    assert g.enemy.hp == 20 - 5 and any(ev["t"] == "druid_done" and ev["returned"] == 1 for ev in g.last_events)
    _ids_everywhere(g)


def test_druid_short_deals_empty_pile_immunity_and_the_strength_is_not_used():
    c, g = _class_campaign(players=2, seed=701, cards=M.DRUIDS)
    set_enemy(g, "J", "H")
    set_hand(g, ["9U", "9S"], player=0)
    set_hand(g, ["4C"], player=1)
    set_discard(g, ["2H"])
    g.play(["9U"])
    # one card dealt to the druid's player, none to the other: one slot to fill, any of the four
    assert g.decision["kind"] == "druid_assign" and g.deciding == 0 and g.decision["dealt"] == [["2H"], []]
    assert g.legal_actions()[0]["needs"] == 1
    with pytest.raises(IllegalAction):
        g.decide({"type": "druid_assign", "player": 0})
    g.decide({"type": "druid_assign", "player": 0, "bottom": "2H"})
    assert g.decision is None and g.tavern[-1] == "2H" and g.discard == [] and g.enemy.hp == 20 - 9
    # three cards: two to the druid's player (two destinations of their choice), one to the other
    _fresh_enemy(g, "J", "H")
    set_hand(g, ["3U", "9S"], player=0)
    g.tavern.extend(g.discard)                         # exactly three cards in the pile
    g.discard = []
    set_discard(g, ["2H", "3H", "4H"])
    g.play(["3U"])
    mine, other = g.decision["dealt"]
    assert len(mine) == 2 and len(other) == 1 and g.legal_actions()[0]["needs"] == 2
    with pytest.raises(IllegalAction):
        g.decide({"type": "druid_assign", "player": 0, "hand": mine[0]})      # two are needed
    g.decide({"type": "druid_assign", "player": 0, "hand": mine[0], "banish": mine[1]})
    assert g.deciding == 1 and g.decision["dealt"] == [[], other]
    g.decide({"type": "druid_assign", "player": 1, "top": other[0]})
    assert g.decision is None and g.tavern[0] == other[0] and mine[0] in g.players[0].hand and mine[1] in g.banished
    assert g.discard == [] and g.enemy.hp == 20 - 3
    # an empty discard pile: nothing happens, no decision
    _fresh_enemy(g, "J", "H")
    set_hand(g, ["5U", "9S", "2C"], player=0)
    g.tavern.extend(g.discard)
    g.discard = []
    g.play(["5U"])
    assert g.decision is None and g.phase == PHASE_SUFFER and any("nothing to sort" in line for line in g.log)
    # immunity to druids blocks the whole ability
    _fresh_enemy(g, "J", "H")
    g.enemy.suits = ("U",)
    set_hand(g, ["7U", "9S"], player=0)
    g.tavern.extend(g.discard)
    g.discard = []
    set_discard(g, ["2H", "3H"])
    g.play(["7U"])
    assert g.decision is None and g.discard == ["2H", "3H"] and dict(_powers(g))["U"]["immune"]
    _ids_everywhere(g)


def test_druid_forecast_hides_the_deal_and_bots_sort_sensibly():
    c, g = _class_campaign(players=2, seed=702, cards=M.DRUIDS, corrupted=("7H",))
    set_enemy(g, "J", "S")
    set_hand(g, ["5U", "9S"], player=0)
    set_hand(g, ["4C"], player=1)
    set_discard(g, ["2H", "3H", "4H", "7H", "6H", "8H", "AC", "7C", "5C", "9C"])
    pv = g.preview_play(["5U"])
    assert pv["ok"] and pv["damage"] == 5 and pv["decision_kind"] == "druid_assign" and g.discard[0] == "2H"
    assert len(g.discard) == 10 and g.phase == PHASE_PLAY
    g.play(["5U"])
    mine = g.decision["dealt"][0]
    act = greedy_policy(g)
    assert act["type"] == "druid_assign" and act["player"] == 0
    chosen = [act[k] for k in ("banish", "hand", "top", "bottom")]
    assert len(set(chosen)) == 4 and all(x in mine for x in chosen)
    by_value = sorted(mine, key=lambda x: -g.cards[x].value)
    if "7H" in mine:
        assert act["banish"] == "7H"                                   # the corrupted card goes first
        good = [x for x in by_value if x != "7H"]
        assert [act["hand"], act["top"], act["bottom"]] == good[:3]
    else:
        assert [act["hand"], act["top"], act["bottom"], act["banish"]] == by_value[:4]
    # the random policy fills the template at random but legally
    rnd = random_policy(g, random.Random(3))
    assert rnd["type"] == "druid_assign" and len(set(rnd[k] for k in ("banish", "hand", "top", "bottom"))) == 4
    apply_action(g, act)
    apply_action(g, greedy_policy(g))
    assert g.decision is None and g.phase == PHASE_SUFFER
    _ids_everywhere(g)


# ---------------------------------------------------------------- Chanters
def test_chanter_declares_everyone_draws_then_discards_down_in_order():
    c, g = _class_campaign(players=2, seed=710, cards=M.CHANTERS)
    set_enemy(g, "J", "H")
    set_hand(g, ["3T", "9S"], player=0)
    set_hand(g, ["2C", "3C", "4C", "5C", "6C", "7C"], player=1)
    set_tavern_top(g, ["AH", "2H", "3H", "4H", "5H", "6H", "7H", "8H"])
    g.play(["3T"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "chanter_declare" and g.deciding == 0
    acts = g.legal_actions()
    assert [a["count"] for a in acts] == list(range(0, len(g.tavern) + 1)) and acts[0]["label"] == "Nobody draws"
    assert not any(a.get("skip") for a in acts)
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "chanter_declare", "count": 3})
    # Ana (1 card) drew to 4, Ben (6) drew to 9 and must discard 2 (limit 7)
    assert g.players[0].hand == ["9S", "AH", "2H", "3H"] and g.players[1].hand[-3:] == ["4H", "5H", "6H"]
    assert any(ev["t"] == "chanter_declare" and ev["count"] == 3 for ev in g.last_events)
    assert g.decision["kind"] == "chanter_discard" and g.deciding == 1
    acts = g.legal_actions()
    assert len(acts) == 1 and acts[0]["needs"] == 2 and acts[0]["pick_from"] == g.players[1].hand
    with pytest.raises(IllegalAction):
        g.decide({"type": "chanter_discard", "player": 1, "cards": ["2C"]})
    with pytest.raises(IllegalAction):
        g.decide({"type": "chanter_discard", "player": 1, "cards": ["2C", "9S"]})
    with pytest.raises(IllegalAction):
        g.decide({"type": "chanter_discard", "player": 0, "cards": ["2C", "3C"]})
    _ids_everywhere(g)
    g.decide({"type": "chanter_discard", "player": 1, "cards": ["2C", "3C"]})
    assert g.decision is None and set(g.discard[:2]) == {"2C", "3C"} and len(g.players[1].hand) == 7
    assert g.enemy.hp == 20 - 3 and g.phase == PHASE_SUFFER
    _ids_everywhere(g)


def test_chanter_zero_immunity_short_reserve_locked_pilgrims_and_bots():
    c, g = _class_campaign(players=2, seed=711, cards=M.CHANTERS)
    set_enemy(g, "J", "H")
    set_hand(g, ["3T", "9S", "2C"], player=0)
    set_hand(g, ["4C"], player=1)
    g.play(["3T"])
    g.decide({"type": "chanter_declare", "count": 0})
    assert g.decision is None and g.players[0].hand == ["9S", "2C"] and g.players[1].hand == ["4C"] and g.phase == PHASE_SUFFER
    # a short reserve: as many as there are, and the count list stops at the reserve size
    _fresh_enemy(g, "J", "H")
    set_hand(g, ["5T", "9S"], player=0)
    g.discard.extend(g.tavern[3:])
    g.tavern = g.tavern[:3]
    g.play(["5T"])
    assert [a["count"] for a in g.legal_actions()] == [0, 1, 2, 3]
    g.decide({"type": "chanter_declare", "count": 3})
    assert len(g.players[0].hand) == 4 and len(g.players[1].hand) == 1 and g.tavern == [] and g.decision is None
    _ids_everywhere(g)
    # immunity to chanters blocks the ability
    _fresh_enemy(g, "J", "H")
    g.enemy.suits = ("T",)
    set_hand(g, ["7T", "9S"], player=0)
    set_tavern_top(g, ["AH", "2H"])
    g.play(["7T"])
    assert g.decision is None and dict(_powers(g))["T"]["immune"] and g.tavern[:2] == ["AH", "2H"]
    # the bot declares what fills the attacker's hand and discards the lowest cards
    c, g = _class_campaign(players=2, seed=712, cards=M.CHANTERS)
    set_enemy(g, "J", "H")
    set_hand(g, ["3T", "9S", "8S"], player=0)                           # 2 left after the play: room for 5
    set_hand(g, ["2C", "3C", "4C", "5C", "6C", "7C", "8C"], player=1)
    g.play(["3T"])
    act = greedy_policy(g)
    assert act["type"] == "chanter_declare" and act["count"] == 5
    apply_action(g, act)
    assert g.decision["kind"] == "chanter_discard" and g.deciding == 1
    act = greedy_policy(g)
    low = sorted(g.players[1].hand, key=lambda x: (g.cards[x].defence_value, g.cards[x].value))[:5]
    assert act["type"] == "chanter_discard" and sorted(act["cards"]) == sorted(low)
    rnd = random_policy(g, random.Random(2))
    assert rnd["type"] == "chanter_discard" and len(rnd["cards"]) == 5 and set(rnd["cards"]) <= set(g.players[1].hand)
    apply_action(g, act)
    assert len(g.players[1].hand) == 7 and g.decision is None
    _ids_everywhere(g)
    # mission 7: pilgrims never leave a hand, so they are not discarded down (and the hand may stay over the limit)
    c, g = _mission(7, players=1, seed=713, extra_cards=M.CHANTERS)
    set_mission_enemy(g, "WLJH")
    _rig_pilgrims(g, zone=["PIL7_1"])
    set_hand(g, ["3T", "PIL2_1", "PIL2_2", "PIL2_3", "PIL2_4", "PIL3_1", "PIL3_2", "PIL3_3"])
    set_tavern_top(g, ["2H", "3H", "4H"])
    g.play(["3T"])
    g.decide({"type": "chanter_declare", "count": 3})
    # 7 pilgrims + 3 drawn = 10 > 8: only the 3 drawn may go, needs = min(2 over, 3 unlocked) = 2
    assert g.decision["kind"] == "chanter_discard" and g.legal_actions()[0]["needs"] == 2
    assert sorted(g.legal_actions()[0]["pick_from"]) == ["2H", "3H", "4H"]
    with pytest.raises(IllegalAction):
        g.decide({"type": "chanter_discard", "player": 0, "cards": ["PIL2_1", "2H"]})
    g.decide({"type": "chanter_discard", "player": 0, "cards": ["2H", "3H"]})
    assert g.decision is None and len(g.players[0].hand) == 8
    _ids_everywhere(g)


# ---------------------------------------------------------------- the Evergreen Mother
def test_evergreen_mother_solo_banishes_from_the_discard_pile_or_the_reserve_by_choice():
    c, g = _class_campaign(players=1, seed=720, relics=("mother",), corrupted=("7D",))
    set_enemy(g, "J", "H")
    set_hand(g, ["7D", "9S", "8S"])
    top = g.tavern[0]
    g.play(["7D"])                                     # an empty discard pile: the reserve as usual, no decision
    assert g.decision is None and g.banished == [top] and g.phase == PHASE_SUFFER
    _fresh_enemy(g, "J", "H")
    set_hand(g, ["7D", "9S", "8S"])
    set_discard(g, ["4C", "2C"])
    top = g.tavern[0]
    g.play(["7D"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "mother_choice" and g.deciding == 0 and g.enemy.hp == 20
    acts = g.legal_actions()
    assert [a["option"] for a in acts] == ["discard", "reserve"] and not any(a.get("skip") for a in acts)
    assert acts[0]["label"] == "Banish 4♣, top of the discard pile"
    pv = g.preview_decision({"type": "mother_choice", "option": "discard"})
    assert pv["ok"] and pv["damage"] == 7
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "mother_choice", "option": "discard"})
    assert g.banished[-1] == "4C" and g.discard == ["2C"] and top not in g.banished
    assert any(ev["t"] == "corrupt_banish" and ev["banished"] == "4C" and ev["source"] == "discard pile" for ev in g.last_events)
    assert g.decision is None and g.enemy.hp == 20 - 7 and len([ev for ev in g.last_events if ev["t"] == "power"]) == 1
    # the reserve as the other choice
    _fresh_enemy(g, "J", "H")
    set_hand(g, ["7D", "9S", "8S"])
    set_discard(g, ["4C", "2C"])
    top = g.tavern[0]
    g.play(["7D"])
    g.decide({"type": "mother_choice", "option": "reserve"})
    assert g.banished[-1] == top and g.discard == ["4C", "2C"]
    # an empty reserve with a discard pile: the relic's "may" keeps both options; the
    # reserve banishes nothing then (as without the relic), which the bot prefers
    _fresh_enemy(g, "J", "H")
    set_hand(g, ["7D", "9S", "8S"])
    g.discard.extend(g.tavern)
    g.tavern = []
    g.play(["7D"])
    acts = g.legal_actions()
    assert [a["option"] for a in acts] == ["discard", "reserve"]
    assert acts[1]["label"] == "Banish nothing (the reserve deck is empty)"
    assert greedy_policy(g)["option"] == "reserve"
    pile, banished = list(g.discard), list(g.banished)
    g.decide(greedy_policy(g))
    assert g.decision is None and g.discard == pile and g.banished == banished
    assert any(ev["t"] == "corrupt_banish_none" for ev in g.last_events)
    _ids_everywhere(g)


def test_evergreen_mother_multiplayer_another_player_banishes_from_hand_or_nothing():
    c, g = _class_campaign(players=3, seed=721, relics=("mother",), corrupted=("7D",))
    set_enemy(g, "J", "H")
    set_hand(g, ["7D", "9S"], player=0)
    set_hand(g, [], player=1)
    set_hand(g, ["3C", "4C"], player=2)
    top = g.tavern[0]
    g.play(["7D"])
    # Ben's hand is empty, so Cy (next clockwise) must banish; no pass
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "mother_banish" and g.deciding == 2
    acts = g.legal_actions()
    assert sorted(a["card"] for a in acts) == ["3C", "4C"] and not any(a.get("skip") for a in acts)
    with pytest.raises(IllegalAction):
        g.decide({"type": "mother_banish", "card": "9S"})
    assert g.tavern[0] == top and g.enemy.hp == 20
    g.decide({"type": "mother_banish", "card": "3C"})
    assert g.banished == ["3C"] and "3C" not in g.players[2].hand and "4C" in g.players[2].hand and top not in g.banished
    assert g.decision is None and g.enemy.hp == 13 and g.phase == PHASE_SUFFER and g.active == 0   # the bard drew 7
    _ids_everywhere(g)
    # every other hand empty: nothing is banished, no decision
    _fresh_enemy(g, "J", "H")
    set_hand(g, ["7D", "9S"], player=0)
    set_hand(g, [], player=1)
    set_hand(g, [], player=2)
    g.play(["7D"])
    assert g.decision is None and g.banished == ["3C"] and g.enemy.hp == 13
    assert any(ev["t"] == "corrupt_banish_none" for ev in g.last_events)
    _ids_everywhere(g)
    # the bot banishes its lowest card
    c, g = _class_campaign(players=2, seed=722, relics=("mother",), corrupted=("7D",))
    set_enemy(g, "J", "H")
    set_hand(g, ["7D", "9S"], player=0)
    set_hand(g, ["5C", "2C", "8C"], player=1)
    g.play(["7D"])
    assert g.deciding == 1 and greedy_policy(g) == {"type": "mother_banish", "player": 1, "card": "2C",
                                                     "label": "Banish 2♣ from hand"}


def test_evergreen_mother_is_queued_behind_a_flute_addition_and_before_the_whistle():
    c, g = _class_campaign(players=2, seed=723, relics=("flute", "mother"), corrupted=("3H",))
    set_enemy(g, "J", "C")
    set_hand(g, ["3S", "9S", "2D"], player=0)
    set_hand(g, ["3H", "4C"], player=1)
    g.play(["3S"])
    assert g.decision["kind"] == "flute_add" and g.deciding == 1
    g.flute_add(["3H"])
    # Ben's corrupted 3 joined: Ana (clockwise from Ben) must banish from hand before the attack resolves
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "mother_banish" and g.deciding == 0
    assert g.decision["resume_step"] == "flute" and g.decision["resume_decision"]["kind"] == "flute_add"
    assert g.plays[0].card_ids == ["3S", "3H"] and g.enemy.hp == 20
    assert sorted(a["card"] for a in g.legal_actions()) == ["2D", "9S"]
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "mother_banish", "card": "2D"})
    # nobody else to ask: the kinfolk attack resolves at 6 (heal 6, shield 6)
    assert g.banished == ["2D"] and g.decision is None and g.enemy.hp == 20 - 6 and g.shield == 6
    assert g.phase == PHASE_SUFFER and g.active == 0
    _ids_everywhere(g)
    # solo: the Mother's choice comes before the Scarlet Whistle offers the (new) top discard
    c, g = _class_campaign(players=1, seed=724, relics=("whistle", "mother"), corrupted=("AC",))
    set_enemy(g, "J", "H")
    set_hand(g, ["AC", "9S", "8S"])
    set_discard(g, ["6D", "5C"])
    g.play(["AC"])
    assert g.decision["kind"] == "mother_choice" and g.decision["resume_step"] == "after_attack"
    g.decide({"type": "mother_choice", "option": "discard"})
    assert g.banished == ["6D"] and g.decision["kind"] == "whistle_take" and g.decision["card"] == "5C"
    g.decide({"type": "whistle_take", "card": "5C"})
    assert g.plays[0].card_ids == ["AC", "5C"] and g.enemy.hp == 20 - 12 and g.decision is None
    _ids_everywhere(g)


# ---------------------------------------------------------------- Mission 7: Tales of Rebirth
def test_pack_p_is_four_pilgrims_of_every_strength_2_to_7_and_the_ace_is_mission_8s():
    from collections import Counter
    from regicide.campaign import evergreen as E
    pack = Counter(d["rank"] for d in M.PILGRIMS)
    assert pack == {r: 4 for r in ("2", "3", "4", "5", "6", "7")} and len(M.PILGRIMS) == 24
    assert all(d["suits"] == [] and d["flags"] == ["pilgrim"] and d["value"] == int(d["rank"]) for d in M.PILGRIMS)
    assert len({d["id"] for d in M.PILGRIMS}) == 24 and M.PUPPY["id"] not in {d["id"] for d in M.PILGRIMS}
    rng = random.Random(7)
    # every game that opens pack P gets exactly those 24; only mission 8 adds the ace (in its zone)
    for number in (7, 8, 9):
        c = CampaignState.new(1, ["Ana"], seed=number)
        P.add_card(c.party, dict(M.GORAN))
        extra = M.build_setup(c, number, rng)
        deck = extra["pilgrims"] or extra["pilgrims_in_reserve"]
        assert Counter(d["rank"] for d in deck) == pack, number
        assert [d["id"] for d in extra["zone_start"] if d["id"] == M.PUPPY["id"]] == (["PILA"] if number == 8 else [])
    c, g = _mission(7, seed=801)
    pilgrims = [x for x in g.cards if g.cards[x].has("pilgrim")]
    assert len(pilgrims) == 24 and "PILA" not in g.cards
    assert Counter(g.cards[x].rank for x in pilgrims) == pack
    c, g = _mission(8, seed=802)
    assert g.mission_zone == ["PILA"] and Counter(g.cards[x].rank for x in g.cards if g.cards[x].has("pilgrim")) == dict(pack, A=1)
    lake = E.build_setup(c, {"location": "E", "banes": [], "boons": []}, rng)    # Evergreen's Lake
    assert Counter(d["rank"] for d in lake["pilgrims"]) == pack


def test_mission7_attempts_saved_with_the_ace_in_the_pilgrim_deck_lose_it_on_load(tmp_path, monkeypatch):
    from regicide.engine import Game
    c, g = _mission(7, seed=803)
    # an attempt saved before the fix: the ace dealt into pack P's pilgrim deck
    from regicide.cards import Card
    puppy = Card.from_dict(dict(M.PUPPY))
    g.cards[puppy.id] = puppy
    g.extra["pilgrim_deck"].insert(3, puppy.id)
    g.config.extra["pilgrims"] = list(g.config.extra["pilgrims"]) + [dict(M.PUPPY)]
    old = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    assert M.drop_stray_puppy(old) and "PILA" not in old.cards and "PILA" not in old.extra["pilgrim_deck"]
    assert len(old.extra["pilgrim_deck"]) == 23 and all(d["id"] != "PILA" for d in old.config.extra["pilgrims"])
    assert old.log[-1] == "The pilgrim ace goes back in mission 8's box: it is not part of pack P."
    _ids_everywhere(old)
    assert not M.drop_stray_puppy(old)                       # once only
    # wherever it waits: the zone, a hand, the discard pile
    for where in ("zone", "hand", "discard"):
        old = Game.from_dict(json.loads(json.dumps(g.to_dict())))
        old.extra["pilgrim_deck"].remove("PILA")
        {"zone": old.mission_zone, "hand": old.players[0].hand, "discard": old.discard}[where].append("PILA")
        assert M.drop_stray_puppy(old) and "PILA" not in old.all_card_ids(), where
        _ids_everywhere(old)
    # the app repairs it when the attempt is loaded
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app import store
    store.save_attempt(Game.from_dict(json.loads(json.dumps(g.to_dict()))), "slot1")
    loaded = store.load_attempt("slot1")
    assert loaded is not None and "PILA" not in loaded.cards and len(loaded.extra["pilgrim_deck"]) == 23
    # mission 8's own ace is never touched
    c8, g8 = _mission(8, seed=804)
    assert not M.drop_stray_puppy(g8) and g8.mission_zone == ["PILA"]


def test_mission7_pilgrim_deck_flips_at_every_start_of_turn_and_pilgrims_never_leave_hands():
    c, g = _mission(7, players=2, seed=800)
    assert g.config.rules_id == "legacy_m7" and MISSIONS[6]["playable"] and g.rules.uses_mission_zone
    assert all(x in g.cards for x in ("3U", "5U", "7U", "9U", "GOR8"))
    # pack P's 24 pilgrims: one flipped before the first turn, 23 left face down; no ace
    assert len(g.extra["pilgrim_deck"]) == 23 and len(g.mission_zone) == 1 and g.cards[g.mission_zone[0]].has("pilgrim")
    assert M.PUPPY["id"] not in g.cards
    assert not any(g.cards[x].has("pilgrim") for x in g.tavern)
    _ids_everywhere(g)
    set_mission_enemy(g, "WLJH")
    _rig_pilgrims(g, zone=[], deck_top=["PIL3_1", "PIL6_1", "PIL3_2", "PIL2_1"])
    set_hand(g, ["9S", "PIL4_1", "PIL5_1", "2D"], player=0)
    set_hand(g, ["8S", "3C"], player=1)
    set_tavern_top(g, ["5C", "6C"])
    # pilgrims in hand: not playable, not discardable, no feign death, and they count in the limit
    assert g.check_play(["PIL4_1"]) == (False, "Pilgrim 4 may never leave your hand.")
    assert all("PIL" not in x for p in g.legal_plays() for x in p)
    assert g.hand_defence_value() == 9 + 2 and g.hand_locked("PIL4_1") and not g.hand_locked("9S")
    g.play(["2D"])                                     # bard: Ana and Ben draw one each
    assert g.players[0].hand == ["9S", "PIL4_1", "PIL5_1", "5C"] and g.players[1].hand == ["8S", "3C", "6C"]
    assert g.phase == PHASE_SUFFER and g.pending_damage == 10
    with pytest.raises(IllegalAction):
        g.suffer(["PIL4_1", "PIL5_1", "9S"])
    assert not g.feign_death_available()
    g.suffer(["9S", "5C"])
    assert g.players[0].hand == ["PIL4_1", "PIL5_1"]
    # Ben's turn started: the next pilgrim was flipped
    assert g.active == 1 and g.mission_zone == ["PIL3_1"] and g.extra["pilgrim_deck"][0] == "PIL6_1"
    assert any(ev["t"] == "zone_add" and ev.get("source") == "pilgrims" for ev in g.last_events)
    # a hand full of pilgrims cannot act: if yielding is barred too, the mission is lost (p.14)
    set_hand(g, ["PIL2_2", "PIL2_3", "PIL2_4", "PIL3_3", "PIL3_4", "PIL4_2", "PIL4_3"], player=1)
    assert g.legal_plays() == [] and g.can_yield()
    g.last_action = ["yielded", None]
    g._check_can_act()
    assert g.phase == PHASE_LOST
    _ids_everywhere(g)
    # feign death needs the whole hand: fine without a pilgrim, impossible with one (the hand cannot pay: lost)
    c, g = _mission(7, players=1, seed=801)
    set_mission_enemy(g, "WLQH")                       # a Deep Pondkin: 15 strength
    _rig_pilgrims(g, zone=["PIL7_1"])
    set_hand(g, ["AD", "AS", "AC", "AH", "2S", "2C", "2H", "AM"])
    set_tavern_top(g, ["3H"])
    g.play(["AD"])                                     # the bard draws the hand back to 8
    assert g.phase == PHASE_SUFFER and g.pending_damage == 15 and g.hand_defence_value() == 13
    assert g.feign_death_available() and any(a.get("feign") for a in g.legal_actions())
    c, g = _mission(7, players=1, seed=801)
    set_mission_enemy(g, "WLQH")
    _rig_pilgrims(g, zone=["PIL7_1"])
    set_hand(g, ["AD", "AS", "AC", "AH", "2S", "2C", "2H", "PIL2_1"])
    set_tavern_top(g, ["3H"])
    g.play(["AD"])
    assert g.phase == PHASE_LOST and "cannot suffer" in g.loss_reason
    _ids_everywhere(g)


def test_mission7_a_card_entering_play_may_banish_one_matching_pilgrim_once_per_card():
    c, g = _mission(7, players=1, seed=802, relics=("whistle",))
    set_mission_enemy(g, "WLJH", hp=100)
    _rig_pilgrims(g, zone=["PIL3_1", "PIL3_2", "PIL6_1"])
    set_hand(g, ["3H", "3C", "9S", "6D", "AS"])
    g.play(["3H", "3C"])                               # kinfolk 6: each 3 may banish one 3-pilgrim
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "pilgrim_banish" and g.decision["entering"] == "3H"
    assert sorted(g.decision["options"]) == ["PIL3_1", "PIL3_2"] and g.enemy.hp == 100
    acts = g.legal_actions()
    assert [a.get("card") for a in acts] == ["PIL3_1", "PIL3_2", None] and acts[-1]["skip"]
    with pytest.raises(IllegalAction):
        g.decide({"type": "pilgrim_banish", "card": "PIL6_1"})
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "pilgrim_banish", "card": "PIL3_2"})
    assert g.banished[-1] == "PIL3_2" and g.mission_zone == ["PIL3_1", "PIL6_1"]
    # the second 3 may banish the other 3
    assert g.decision["kind"] == "pilgrim_banish" and g.decision["entering"] == "3C" and g.decision["options"] == ["PIL3_1"]
    g.decide({"type": "pilgrim_skip"})                 # keep it
    assert g.decision is None and g.mission_zone == ["PIL3_1", "PIL6_1"]
    assert g.enemy.hp == 100 - 12 and g.phase == PHASE_SUFFER        # 6 doubled by the warrior
    assert g.rules.zone_strength(g) == 9
    g.suffer(["9S", "6D"])
    # a lone 6 banishes one pilgrim only, even if two 6s sit in the zone
    _rig_pilgrims(g, zone=["PIL3_1", "PIL6_1", "PIL6_2"])
    set_hand(g, ["6D", "AS", "2C"])
    set_tavern_top(g, ["9H", "8H", "7H", "6H", "5H", "4H"])
    g.play(["6D"])
    assert g.decision["kind"] == "pilgrim_banish" and sorted(g.decision["options"]) == ["PIL6_1", "PIL6_2"]
    assert greedy_policy(g)["type"] == "pilgrim_banish"
    g.decide({"type": "pilgrim_banish", "card": "PIL6_1"})
    assert g.decision is None and g.mission_zone == ["PIL3_1", "PIL6_2"] and g.phase == PHASE_SUFFER
    g.suffer(min_waste_discard(g))
    # no match: no decision at all; a card the Scarlet Whistle adds (solo) is checked too
    _rig_pilgrims(g, zone=["PIL3_1", "PIL2_1"])
    set_hand(g, ["AS", "2C", "9C"])
    set_discard(g, ["2H"] + [x for x in g.discard if x != "2H"])
    g.play(["AS"])                                     # the ace matches nothing; the whistle offers the 2♥
    assert g.decision["kind"] == "whistle_take"
    g.decide({"type": "whistle_take", "card": "2H"})
    assert g.decision["kind"] == "pilgrim_banish" and g.decision["entering"] == "2H" and g.decision["options"] == ["PIL2_1"]
    assert g.decision["resume_step"] == "resolve"
    g.decide({"type": "pilgrim_banish", "card": "PIL2_1"})
    assert g.decision is None and g.mission_zone == ["PIL3_1"] and g.plays[-1].value == 3 and g.phase == PHASE_SUFFER
    _ids_everywhere(g)


def test_mission7_mage_and_flute_additions_check_the_pilgrims_too():
    c, g = _mission(7, players=2, seed=803, relics=("flute",))
    set_mission_enemy(g, "WLJH", hp=100)
    _rig_pilgrims(g, zone=["PIL3_1", "PIL4_1"])
    set_hand(g, ["3M", "9S", "8S"], player=0)
    set_hand(g, ["3C", "2D"], player=1)
    set_tavern_top(g, ["4H", "2S", "5S"])
    g.play(["3M"])
    # the 3 of mages matches a 3-pilgrim first; then the flute asks Ben; then the mage looks
    assert g.decision["kind"] == "pilgrim_banish" and g.decision["entering"] == "3M"
    g.decide({"type": "pilgrim_banish", "card": "PIL3_1"})
    assert g.decision["kind"] == "flute_add" and g.deciding == 1
    g.flute_add(["3C"])
    assert g.decision["kind"] == "mage_peek" and g.deciding == 0
    assert g.decision["revealed"][:3] == ["4H", "2S", "5S"] and len(g.decision["revealed"]) == 6
    g.decide({"type": "mage_pick", "card": "4H"})
    # the 4 of clerics joined: it matches the 4-pilgrim; the mage flow resumes afterwards
    assert g.decision["kind"] == "pilgrim_banish" and g.decision["entering"] == "4H" and g.decision["resume_step"] == "mage_picked"
    assert g.decision["resume_decision"]["kind"] == "mage_peek" and g.plays[0].card_ids == ["3M", "3C", "4H"]
    _ids_everywhere(g)                                 # the revealed cards parked in the nested decision count
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "pilgrim_banish", "card": "PIL4_1"})
    assert g.mission_zone == [] and g.decision is None
    # strength 10: the cleric heals, the warrior doubles: 20
    assert g.plays[0].value == 10 and g.enemy.hp == 100 - 20 and g.phase == PHASE_SUFFER
    _ids_everywhere(g)


def test_mission7_defeat_discards_reserve_cards_equal_to_the_zone_then_the_zone_and_banishes_the_enemy():
    c, g = _mission(7, players=1, seed=804)
    set_mission_enemy(g, "WLJS", hp=9)                 # a Shoal paladin
    _rig_pilgrims(g, zone=["PIL3_1", "PIL6_1"])
    set_hand(g, ["9H", "2C", "AS"])
    reserve = list(g.tavern)
    g.play(["9H"])                                     # 9: exact
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "zone_banish" and g.decision["exact"] is True
    acts = g.legal_actions()
    assert [a.get("card") for a in acts] == ["PIL3_1", "PIL6_1", None] and acts[-1]["skip"]
    assert greedy_policy(g)["card"] == "PIL6_1"       # the bot banishes the strongest
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "zone_banish", "card": "PIL6_1"})
    # the zone is now 3: three reserve cards to the discard pile, then the zone, then the played card on top
    assert g.enemies_defeated == 1 and g.decision is None
    assert g.discard == ["9H", "PIL3_1", reserve[2], reserve[1], reserve[0]] and g.tavern == reserve[3:]
    assert "PIL6_1" in g.banished and "WLJS" in g.banished
    assert len(g.mission_zone) == 1 and g.cards[g.mission_zone[0]].has("pilgrim")   # the new turn flipped one
    assert any(ev["t"] == "reserve_discard" and len(ev["cards"]) == 3 for ev in g.last_events)
    assert any(ev["t"] == "zone_cleared" and ev["to"] == "discard" for ev in g.last_events)
    assert g.phase == PHASE_PLAY and g.active == 0
    _ids_everywhere(g)
    # not exact: no choice; the whole zone counts, and a short reserve gives what it has
    set_mission_enemy(g, "WLJH", hp=5)
    _rig_pilgrims(g, zone=["PIL6_1", "PIL7_1"])
    set_hand(g, ["9C", "2C"])
    g.discard.extend(g.tavern[5:])
    g.tavern = g.tavern[:5]
    before = len(g.discard)
    g.play(["9C"])
    assert g.enemies_defeated == 2 and g.decision is None
    assert g.tavern == [] and len(g.discard) == before + 5 + 2 + 1
    assert any(ev["t"] == "reserve_discard" and len(ev["cards"]) == 5 for ev in g.last_events)
    _ids_everywhere(g)
    # the mission is won when the last pondkin falls
    g.castle = []
    set_hand(g, ["9S", "2C"])
    g.enemy.hp = 5
    g.play(["9S"])
    assert g.phase == PHASE_WON and g.result == "gold"    # solo: a medal, no Jester attack used


# ---------------------------------------------------------------- Mission 8: Winds of Chaos
def test_mission8_puppy_in_the_zone_pilgrims_in_the_reserve_and_the_bonus_skips_pilgrims():
    from helpers import _pull
    c, g = _mission(8, players=1, seed=810)
    assert g.config.rules_id == "legacy_m8" and MISSIONS[7]["playable"] and g.rules.uses_mission_zone
    assert g.mission_zone == ["PILA"] and g.cards["PILA"].value == 1 and "pilgrim_deck" not in g.extra
    everywhere = g.tavern + [x for p in g.players for x in p.hand]
    assert sum(1 for x in everywhere if g.cards[x].has("pilgrim")) == 24
    assert all(x in g.cards for x in ("3T", "5T", "7T", "9T"))
    _ids_everywhere(g)
    set_mission_enemy(g, "HEJ1")                       # a Troll: cleric and bard
    assert g.rules.immune_suits(g) == ("H", "D") and g.enemy_attack == 10 and g.rules.attack_bonus(g) == 0
    # pilgrims are ordinary classless cards here: playable, pairable with the puppy, discardable
    set_hand(g, ["PIL3_1", "PIL3_2", "9S", "8S", "PILA"])
    assert g.mission_zone == []
    assert g.check_play(["PIL3_1"]) == (True, "single") and g.check_play(["PIL3_1", "PIL3_2"]) == (True, "set")
    assert g.check_play(["PILA", "PIL3_1"]) == (True, "companion") and not g.hand_locked("PIL3_1")
    _pull(g, "PILA")
    g.mission_zone = ["PILA"]
    g.play(["PIL3_1", "PIL3_2"])
    assert g.enemy.hp == 20 - 6 and g.plays[0].suits == () and g.phase == PHASE_SUFFER
    assert not any(ev["t"] == "power" for ev in g.last_events)
    g.suffer(["9S", "8S"])
    _ids_everywhere(g)
    # the zone's non-pilgrim cards add to the enemy, pilgrims add nothing
    for x in ("PIL2_1", "3H"):
        _pull(g, x)
    g.mission_zone = ["PILA", "PIL2_1", "3H"]
    assert g.rules.attack_bonus(g) == 3 and g.enemy_attack == 13
    _ids_everywhere(g)


def test_mission8_defeat_moves_cards_to_the_zone_in_ascending_order_and_a_ten_fills_it():
    from helpers import _pull
    c, g = _mission(8, players=1, seed=811)
    set_mission_enemy(g, "HEJ6", hp=4)                 # a warrior / paladin troll
    set_hand(g, ["2H", "3H", "4D", "AS", "9S"])
    g.play(["2H"])
    assert g.enemy.hp == 2 and g.phase == PHASE_SUFFER
    g.suffer(["9S", "AS"])
    set_hand(g, ["3H", "4D", "AS", "7C"])
    g.play(["3H"])                                     # a kill, not exact; 2♥ and 3♥ are in play
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "zone_build" and g.decision["options"] == ["2H"]
    acts = g.legal_actions()
    assert [a.get("card") for a in acts] == ["2H", None] and acts[-1]["label"] == "Stop"
    with pytest.raises(IllegalAction):
        g.decide({"type": "zone_build", "card": "3H"})
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "zone_build", "card": "2H"})
    assert g.mission_zone == ["PILA", "2H"] and g.decision["kind"] == "zone_build" and g.decision["options"] == ["3H"]
    g.decide({"type": "zone_build", "card": "3H"})
    # nothing in play is a 4: the kill completes; enemy banished, nothing left to discard
    assert g.decision is None and g.enemies_defeated == 1 and g.banished == ["HEJ6"] and g.mission_zone == ["PILA", "2H", "3H"]
    assert g.rules.attack_bonus(g) == 5 and g.enemy_attack == g.enemy.attack + 5
    assert g.discard == [] and "9S" in g.tavern          # the 3 of clerics healed the two discards first
    assert g.phase == PHASE_PLAY and g.active == 0
    _ids_everywhere(g)
    # Stop keeps the rest in play for the clean-up
    set_mission_enemy(g, "HEJ1", hp=3)
    set_hand(g, ["4D", "PIL4_1", "AS"])
    g.play(["4D"])                                     # immune to bards: 4, not exact
    assert g.decision["kind"] == "zone_build" and g.decision["options"] == ["4D"]
    assert greedy_policy(g)["card"] == "4D"
    g.decide({"type": "zone_build_stop"})
    assert g.decision is None and g.discard[0] == "4D" and g.mission_zone == ["PILA", "2H", "3H"] and g.enemies_defeated == 2
    # a 10 fills the zone: the zone is discarded, any discards banished, the rest healed under the reserve
    zone = ["PILA", "2H", "3H", "4D", "PIL5_1", "6C", "7C", "8C", "9C"]
    for x in zone:
        _pull(g, x)
    g.mission_zone = list(zone)
    assert g.rules.attack_bonus(g) == 2 + 3 + 4 + 6 + 7 + 8 + 9
    set_mission_enemy(g, "HEJ4", hp=10)               # bard / warrior troll: the 10 of bards is a plain 10
    set_hand(g, ["10D", "AS"])
    set_discard(g, ["2S", "3S"] + [x for x in g.discard if x not in ("2S", "3S")])
    pile_before = list(g.discard)
    reserve_before = list(g.tavern)
    g.play(["10D"])
    assert g.decision["kind"] == "zone_build" and g.decision["options"] == ["10D"] and g.decision["exact"] is True
    g.decide({"type": "zone_build", "card": "10D"})
    assert g.mission_zone == [] and g.extra.get("zone_filled") is True
    assert g.decision["kind"] == "discard_banish" and sorted(g.discard) == sorted(pile_before + zone + ["10D"])
    acts = g.legal_actions()
    template = [a for a in acts if "needs" in a][0]
    assert template["needs"] is None and sorted(template["pick_from"]) == sorted(g.discard) and acts[-1]["skip"]
    with pytest.raises(IllegalAction):
        g.decide({"type": "discard_banish", "cards": ["AS"]})
    bot = greedy_policy(g)
    assert bot["type"] == "discard_banish" and "PILA" in bot["cards"] and "PIL5_1" in bot["cards"] and len(bot["cards"]) == 5
    rnd = random_policy(g, random.Random(5))
    assert rnd["type"] in ("discard_banish", "discard_banish_skip")
    _ids_everywhere(g)
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "discard_banish", "cards": ["PILA", "2S", "10D"]})
    healed = sorted(set(pile_before + zone + ["10D"]) - {"PILA", "2S", "10D"})
    assert {"PILA", "2S", "10D"} <= set(g.banished) and g.discard == []
    assert g.tavern[:len(reserve_before)] == reserve_before and sorted(g.tavern[len(reserve_before):]) == healed
    assert any(ev["t"] == "zone_filled" and ev["banished"] == ["PILA", "2S", "10D"] and ev["healed"] == len(healed) for ev in g.last_events)
    # the exact kill's pick from the discard pile: nothing was left in play, the pile is empty, no pick
    assert g.decision is None and g.enemies_defeated == 3 and g.phase == PHASE_PLAY
    _ids_everywhere(g)
    # no more moves for the rest of the mission
    set_mission_enemy(g, "HEJ3", hp=2)
    set_hand(g, ["2C", "AS"])
    g.play(["2C"])                                     # 4: a kill, not exact; a 2 would otherwise be movable
    assert g.decision is None and g.enemies_defeated == 4 and g.mission_zone == [] and g.rules.attack_bonus(g) == 0
    _ids_everywhere(g)


def test_mission8_exact_kill_lets_the_player_put_a_discard_card_on_top_of_the_reserve():
    c, g = _mission(8, players=1, seed=812)
    set_mission_enemy(g, "HEJ1", hp=9)
    set_hand(g, ["9S", "AS", "2C"])
    set_discard(g, ["5H", "6H"])
    g.play(["9S"])                                     # exact; nothing can move (a 2 is needed)
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "discard_pick" and g.decision["resume"] == "defeat_tail"
    # the enemy is already banished and the played card is on the discard pile when the pick is offered
    assert g.banished == ["HEJ1"] and g.discard == ["9S", "5H", "6H"] and g.enemy is None
    acts = g.legal_actions()
    assert [a.get("card") for a in acts] == ["9S", "5H", "6H", None] and acts[-1]["skip"]
    assert greedy_policy(g)["card"] == "9S"
    _ids_everywhere(g)
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "discard_pick", "card": "6H"})
    assert g.tavern[0] == "6H" and g.discard == ["9S", "5H"] and g.decision is None
    assert g.enemies_defeated == 1 and g.enemy is not None and g.phase == PHASE_PLAY and g.active == 0
    _ids_everywhere(g)
    # skipping leaves the pile alone; the forecast reports the kill
    set_mission_enemy(g, "HEJ2", hp=9)
    set_hand(g, ["9S", "AS", "2C"])
    pv = g.preview_play(["9S"])
    assert pv["ok"] and pv["defeats"] and pv["exact"] and pv["decision_kind"] == "discard_pick"
    g.play(["9S"])
    g.decide({"type": "discard_pick_skip"})
    assert g.discard[0] == "9S" and g.enemies_defeated == 2 and g.decision is None
    # moves to the zone come first, the pick after the clean-up (the played cards are in the pile by then)
    set_mission_enemy(g, "HEJ3", hp=4)                 # cleric / paladin troll
    set_hand(g, ["2D", "AS", "9C", "8C"])
    g.mission_zone = ["PILA"]
    g.play(["2D"])
    assert g.enemy.hp == 2 and g.phase == PHASE_SUFFER
    g.suffer(min_waste_discard(g))
    set_hand(g, ["2S", "AS"])
    g.play(["2S"])                                     # immune to paladins: 2, exact
    assert g.decision["kind"] == "zone_build" and sorted(g.decision["options"]) == ["2D", "2S"]
    g.decide({"type": "zone_build", "card": "2S"})
    assert g.decision["kind"] == "discard_pick" and g.mission_zone == ["PILA", "2S"] and g.discard[0] == "2D"
    g.decide({"type": "discard_pick", "card": "2D"})
    assert g.tavern[0] == "2D" and g.decision is None and g.enemies_defeated == 3
    _ids_everywhere(g)


# ---------------------------------------------------------------- Mission 9: Hope From Ashes
def _mission9(players=1, seed=820, relics=(), beast="B_H", merc=True):
    names = ["Ana", "Ben", "Cy"][:players]
    c = CampaignState.new(players, names, seed=seed)
    c.mission = 9
    c.completed = list(range(1, 9))
    c.relics.extend(relics)
    P.add_card(c.party, dict(M.GORAN))
    for s in ("C", "S", "H", "D"):
        P.add_suit(c.party, "GOR8", s)
    c.flags["beasts"] = True
    c.set_beast(beast)
    for d in M.MAGE_DECK:
        P.add_card(c.party, dict(d))
    if merc:
        c.m_box_opened = True
        c.coins = 5
        c.hire("merc_12H")
    g = c.start_attempt(seed=seed)
    return c, g


def test_mission9_setup_deals_three_captured_piles_and_shuffles_the_rest_back_with_the_pilgrims():
    c, g = _mission9(players=3)
    assert g.config.rules_id == "legacy_m9" and MISSIONS[8]["playable"] and g.rules.uses_mission_zone
    piles = g.extra["captured"]
    assert len(piles) == 3 and all(len(p) == 10 for p in piles) and g.mission_zone == []
    captured = [x for p in piles for x in p]
    assert len(set(captured)) == 30
    # Gøran, the beast, the mercenary, the Jester and the pilgrims are never captured
    assert not any(x in captured for x in ("GOR8", "B_H", "M12H")) and not any(g.cards[x].is_jester for x in captured)
    assert not any(g.cards[x].has("pilgrim") for x in captured)
    loose = g.tavern + [x for p in g.players for x in p.hand]
    assert all(x in loose for x in ("GOR8", "B_H", "M12H")) and sum(1 for x in loose if g.cards[x].is_jester) == 1
    assert sum(1 for x in loose if g.cards[x].has("pilgrim")) == 24
    _ids_everywhere(g)
    enemies = [g.cards[x] for x in [g.enemy.card_id] + g.castle]
    assert [e.name for e in enemies] == ["Loreguard"] * 4 + ["Lorekeeper"] * 4 + ["Myla"]
    assert g.rules.pile_tops(g) == [p[0] for p in piles]
    # the save keeps the piles
    g2 = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    assert g2.extra["captured"] == piles and sorted(g2.all_card_ids()) == sorted(g2.cards)


def test_mission9_end_of_turn_rescues_a_captured_card_for_a_hand_card_or_rotates_the_piles():
    c, g = _mission9(players=2, seed=821)
    set_mission_enemy(g, "TTQH")
    set_hand(g, ["9S", "4C", "3C", "5D", "6D"], player=0)
    set_hand(g, ["8S", "4D"], player=1)
    piles = [list(p) for p in g.extra["captured"]]     # after the hands were rigged (that pulls from the piles)
    tops = [p[0] for p in piles]
    g.play(["9S"])                                     # shield 9: suffer 6
    assert g.phase == PHASE_SUFFER and g.pending_damage == 6
    g.suffer(["4C", "3C"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "pile_rescue" and g.decision["resume"] == "end_turn"
    assert g.deciding == 0 and g.active == 0 and g.turn == 1
    acts = g.legal_actions()
    assert sorted((a["pile"], a["card"]) for a in acts if a["type"] == "pile_rescue") == sorted(
        (k, cid) for k in range(3) for cid in ("5D", "6D"))
    assert acts[-1] == {"type": "pile_rotate", "player": 0, "skip": True, "label": "Rotate the piles"}
    with pytest.raises(IllegalAction):
        g.decide({"type": "pile_rescue", "pile": 0, "card": "8S"})
    _ids_everywhere(g)
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "pile_rescue", "pile": 1, "card": "5D"})
    assert g.banished[-1] == "5D" and g.discard[0] == tops[1] and g.extra["captured"][1] == piles[1][1:]
    assert g.extra["captured"][0] == piles[0] and g.extra["captured"][2] == piles[2]
    assert g.decision is None and g.active == 1 and g.turn == 2 and g.phase == PHASE_PLAY
    assert any(ev["t"] == "pile_rescue" and ev["pile"] == 1 for ev in g.last_events)
    _ids_everywhere(g)
    # rotating: every top card goes to the bottom of its pile (no damage: Ben's shield covers it)
    before = [list(p) for p in g.extra["captured"]]
    g.play(["8S"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "pile_rescue" and g.deciding == 1
    g.decide({"type": "pile_rotate"})
    assert g.extra["captured"] == [p[1:] + p[:1] for p in before] and g.active == 0 and g.decision is None
    # an empty hand: only the rotation is offered; a kill skips the end of turn entirely
    set_hand(g, ["9S"], player=0)
    g.enemy.hp = 30
    g.play(["9S"])
    assert g.decision["kind"] == "pile_rescue" and [a["type"] for a in g.legal_actions()] == ["pile_rotate"]
    g.decide(greedy_policy(g))
    assert g.active == 1
    set_hand(g, ["9C", "2C"], player=1)
    g.enemy.hp = 9
    g.play(["9C"])                                     # 18 damage: a kill, not exact
    assert g.enemies_defeated == 1 and g.decision is None and g.phase == PHASE_PLAY and g.active == 1
    assert g.banished[-1] == "TTQH"
    _ids_everywhere(g)


def test_mission9_exact_kill_may_move_a_captured_top_card_onto_the_reserve():
    c, g = _mission9(players=1, seed=822)
    set_mission_enemy(g, "TTQH", hp=9)
    set_hand(g, ["9S", "2C"])
    tops = [p[0] for p in g.extra["captured"]]
    g.play(["9S"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "pile_to_reserve" and g.decision["exact"] is True
    acts = g.legal_actions()
    assert [a.get("pile") for a in acts] == [0, 1, 2, None] and acts[-1]["skip"]
    assert greedy_policy(g)["pile"] == max(range(3), key=lambda k: g.cards[tops[k]].value)
    g = Game.from_dict(json.loads(json.dumps(g.to_dict())))
    g.decide({"type": "pile_to_reserve", "pile": 2})
    assert g.tavern[0] == tops[2] and len(g.extra["captured"][2]) == 9 and g.enemies_defeated == 1
    assert g.banished[-1] == "TTQH" and g.decision is None and g.phase == PHASE_PLAY
    _ids_everywhere(g)
    # an emptied pile is skipped in the offers
    g.banished.extend(g.extra["captured"][0])
    g.extra["captured"][0] = []
    set_mission_enemy(g, "TTQD", hp=9)
    set_hand(g, ["9S", "2C"])
    g.play(["9S"])
    assert [a.get("pile") for a in g.legal_actions()] == [1, 2, None]
    g.decide({"type": "pile_to_reserve_skip"})
    assert g.enemies_defeated == 2
    # no piles left: no end-of-turn choice either
    for k in (1, 2):
        g.banished.extend(g.extra["captured"][k])
        g.extra["captured"][k] = []
    set_mission_enemy(g, "TTQC", hp=30)
    set_hand(g, ["9S", "7C"])
    g.play(["9S"])
    g.suffer(["7C"])
    assert g.decision is None and g.active == 0 and g.phase == PHASE_PLAY and g.turn > 1
    _ids_everywhere(g)


def test_mission9_mylas_immunity_to_bards_and_paladins_can_never_be_ignored():
    c, g = _mission9(players=3, seed=823)
    g.cards["9S"] = g.cards["9S"].with_changes(flags=("corrupted",))
    set_mission_enemy(g, "MYLA_BOSS")
    assert g.enemy.name == "Myla" and (g.enemy.attack, g.enemy.max_hp) == (20, 80) and g.rules.immune_suits(g) == ("D", "S")
    assert g.rules.fixed_immunity(g, "S") and g.rules.fixed_immunity(g, "D") and not g.rules.fixed_immunity(g, "H")
    assert g.immune("S", [g.cards["9S"]]) and g.immune("D", [g.cards["5D"]]) and not g.immune("H", [g.cards["5H"]])
    # a corrupted paladin: still banishes a reserve card, deals its damage, gives no shield
    set_hand(g, ["9S", "2C"], player=0)
    top = g.tavern[0]
    g.play(["9S"])
    assert g.banished[-1] == top and g.enemy.hp == 80 - 9 and g.shield == 0 and g.enemy_attack == 20
    assert dict(_powers(g))["S"]["immune"]
    # the renewed Gøran ignores immunity anywhere else, not against Myla
    c, g = _mission9(players=3, seed=824)
    set_mission_enemy(g, "MYLA_BOSS")
    g.cards["GOR8E"] = Card.from_dict(dict(M.GORAN_RENEWED))
    g.tavern.append("GOR8E")
    set_hand(g, ["GOR8E", "2C"], player=0)
    g.play(["GOR8E"])
    powers = dict(_powers(g))
    assert powers["D"]["immune"] and powers["S"]["immune"] and not powers["H"].get("immune") and not powers["C"].get("immune")
    assert g.enemy.hp == 80 - 16 and g.shield == 0
    # a claimed Jester's attack ignores nothing against her: the paladin gives no shield, the bard draws nothing
    c, g = _mission9(players=3, seed=825)
    set_mission_enemy(g, "MYLA_BOSS")
    jester = [x for x in g.cards if g.cards[x].is_jester][0]
    set_hand(g, [jester, "2C"], player=0)
    set_hand(g, ["AD", "9S", "3H"], player=1)
    g.play([jester])
    g.choose_next(1)
    assert g.extra.get("jester_attack")
    hands_before = sum(len(p.hand) for p in g.players)
    g.play(["AD", "9S"])
    powers = dict(_powers(g))
    assert powers["D"]["immune"] and powers["S"]["immune"] and g.plays[-1].jester
    assert g.shield == 0 and g.enemy_attack == 20 and g.enemy.hp == 80 - 10
    assert sum(len(p.hand) for p in g.players) == hands_before - 2
    # against a Loreguard the usual rules hold: a corrupted paladin keeps its shield
    c, g = _mission9(players=3, seed=826)
    g.cards["9S"] = g.cards["9S"].with_changes(flags=("corrupted",))
    set_mission_enemy(g, "TTQS")
    set_hand(g, ["9S", "2C"], player=0)
    g.play(["9S"])
    assert g.shield == 9 and not g.rules.fixed_immunity(g, "S")


# ---------------------------------------------------------------- bot play-outs
@pytest.mark.parametrize("number,players", [(7, 1), (7, 2), (8, 1), (8, 2), (9, 1), (9, 2)])
def test_bots_play_out_missions_7_to_9(number, players):
    rng = random.Random(number * 10 + players)
    seen = set()
    expected = {7: {"Druid:", "pilgrim deck", "from the top of the reserve deck go"},
                8: {"Chanter:"} | ({"mission zone"} if players == 2 else set()),
                9: {"captured pile"}}[number]
    for seed in range(10):
        if seed >= 4 and expected <= seen:
            break
        kw = {"players": players, "seed": 900 + number * 10 + seed, "beast": ("B_H", "B_C", "B_D", "B_S")[seed % 4],
              "relics": ("flute", "whistle", "emblem", "mother"), "corrupted": ("7D", "5S")}
        if number == 9:
            c, g = _mission9(players=players, seed=kw["seed"], relics=kw["relics"], beast=kw["beast"])
            for cid in kw["corrupted"]:
                g.cards[cid] = g.cards[cid].with_changes(flags=("corrupted",))
        else:
            c, g = _mission(number, **kw)
        policy = greedy_policy if seed % 2 == 0 else random_policy
        play_out(g, policy, rng, max_steps=4000)
        assert g.is_over and g.decision is None
        _ids_everywhere(g)
        if number != 7:                                # a druid may leave a hand over the limit
            assert all(len(p.hand) <= g.config.max_hand for p in g.players)
        for line in g.log:
            for key in ("Druid:", "Chanter:", "Evergreen Mother", "pilgrim deck", "matches", "mission zone", "captured pile",
                        "from the top of the reserve deck go"):
                if key in line:
                    seen.add(key)
    assert expected <= seen, seen
