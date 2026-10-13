"""Regicide Legacy campaign: missions 1-2, rewards, losses, mercenaries, relics, rules."""
import json
import random

import pytest

from regicide.bots import apply_action, greedy_policy, play_out
from regicide.campaign import CampaignState
from regicide.campaign import party as P
from regicide.campaign.missions import MISSIONS
from regicide.engine import PHASE_CHOOSE_NEXT, PHASE_LOST, PHASE_PLAY, PHASE_SUFFER, PHASE_WON, Game, IllegalAction
from regicide.rules import GameConfig
from helpers import set_enemy, set_hand


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
    # old saves without the field default to no swaps
    d.pop("swaps_allowed")
    assert CampaignState.from_dict(d).swaps_allowed is False


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
