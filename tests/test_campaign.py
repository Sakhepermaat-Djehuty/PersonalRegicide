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
    # reward card: "Open pack C and corrupt a character in your party" -> the player chooses
    assert c.corrupted == [] and len(c.pending) == 1 and res["pending"][0]["kind"] == "choice_corrupt"
    step = c.pending_choice()
    options = step["options"]
    assert options and all(P.find(c.party, o)["rank"] in "23456789" for o in options)
    assert "6H" not in options and "6C" in options  # the 6 is always Esme (clubs)
    with pytest.raises(RuntimeError):
        c.start_attempt(seed=3)  # must choose first
    with pytest.raises(ValueError):
        c.resolve_choice("10S")  # not an option
    line = c.resolve_choice("4H")
    assert "corrupted" in line and c.corrupted == ["4H"] and "corrupted" in P.find(c.party, "4H")["flags"]
    assert not c.pending
    # the choice survives a save round trip while pending
    c2 = CampaignState.new(1, ["Solo"], seed=2)
    g2 = c2.start_attempt(seed=2)
    win_quickly(g2)
    c2.finish_attempt(g2)
    c3 = CampaignState.from_dict(c2.to_dict())
    assert c3.pending_choice()["options"] == c2.pending_choice()["options"]


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


def test_corruption_targets_respect_esme_and_class_limits():
    rng = random.Random(1)
    party = P.starting_party()
    picked = []
    for _ in range(8):
        t = P.pick_corruption_target(party, rng)
        assert t is not None
        P.add_flag(party, t, "corrupted")
        picked.append(t)
    ranks = [P.find(party, t)["rank"] for t in picked]
    assert len(set(ranks)) == 8 and set(ranks) == set("23456789")
    six = [t for t in picked if P.find(party, t)["rank"] == "6"][0]
    assert P.find(party, six)["suits"] == ["C"]  # Esme
    for s in "HDCS":
        assert sum(1 for t in picked if P.find(party, t)["suits"][0] == s) <= 2
    assert P.pick_corruption_target(party, rng) is None


def test_mercenary_costs_follow_fan_shop():
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


def test_mission2_rewards_are_corruption_choice_and_class_sticker_assignment():
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
    assert kinds == ["choice_corrupt", "choice_classes"]
    # second corruption: a different strength than the first
    first = c.corrupted[0]
    opts = c.pending_choice()["options"]
    assert first not in opts and all(P.find(c.party, o)["rank"] != P.find(c.party, first)["rank"] for o in opts)
    c.resolve_choice(opts[0])
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
    assert kinds == ["add_suit", "add_card", "remove_card", "remove_card", "remove_card", "choice_corrupt", "choice_suit"]
    for s in steps:
        if s["kind"].startswith("choice"):
            c.pending.append(s)
        else:
            M.apply_step(c, s, rng)
    assert P.find(c.party, "GOR8")["suits"] == ["C"]
    assert P.find(c.party, "MYLA7")["name"] == "Myla" and P.find(c.party, "MYLA7")["suits"] == []
    assert P.find(c.party, "5R") is not None and all(P.find(c.party, x) is None for x in ("3R", "7R", "9R"))
    c.resolve_choice(c.pending_choice()["options"][0])
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
    assert [s["kind"] for s in steps] == ["add_suit", "choice_corrupt", "relic", "choice_suit", "remove_card", "remove_card", "remove_card"]
    for s in steps:
        if s["kind"].startswith("choice"):
            c.pending.append(s)
        else:
            M.apply_step(c, s, rng)
    assert P.find(c.party, "GOR8")["suits"] == ["C", "S"] and "emblem" in c.relics
    assert P.find(c.party, "3G") is not None and all(P.find(c.party, x) is None for x in ("5G", "7G", "9G"))
    c.resolve_choice(c.pending_choice()["options"][0])
    step = c.pending_choice()
    assert step["kind"] == "choice_suit" and step["options"] == ["8H", "8D", "8C"]
    c.resolve_choice("8C")
    assert P.find(c.party, "8C")["suits"] == ["C", "G"] and not c.pending


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
    assert [s["kind"] for s in steps] == ["add_suit", "choice_corrupt", "remove_card", "remove_card", "remove_card", "choice_suit"]
    for s in steps:
        if s["kind"].startswith("choice"):
            c.pending.append(s)
        else:
            M.apply_step(c, s, rng)
    assert P.find(c.party, "GOR8")["suits"] == ["H"]
    assert P.find(c.party, "7U") is not None and all(P.find(c.party, x) is None for x in ("3U", "5U", "9U"))
    c.resolve_choice(c.pending_choice()["options"][0])
    step = c.pending_choice()
    assert step["kind"] == "choice_suit" and step["options"] == ["4D", "4C", "4S"]
    c.resolve_choice("4S")
    assert P.find(c.party, "4S")["suits"] == ["S", "U"] and not c.pending
