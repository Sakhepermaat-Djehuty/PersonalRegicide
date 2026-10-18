"""Mission 11 (Descent Into Darkness) regression: the owner's turn 10, Ace of Mages + the
corrupted 8 of clubs (Guardian sticker) with the corrupt Evergreen Mother, solo.

The table before the play (from the owner's screenshots): a Justicar (10/30, no class) at
20 health with the 10 of diamonds already in play against it; the Corrupted Evergreen the
last card of the castle; discard pile 12 cards, 9 of spades on top, then the 6 of mages, then
the 6 of clubs; banished pile 15 cards, 3 of mages on top; reserve 24; the next beast the
warrior (clubs) one. The enemy is immune to paladins (9S) and mages (3M) and strikes for
10 + 9 + 3 = 22.

What happens (rulebook p.15 corruption, the Mother's solo text, p.18 Guardian, p.20 mages,
mission 11's card): step 1, the corrupted 8 banishes; the Mother lets the player take the top
of the discard pile (9S) instead of the top of the reserve, which uncovers the 6 of mages on
the discard pile, so the Ace's mage power stays blocked. Clubs double 9 to 18 (20 -> 2), the
Guardian means no damage is suffered, and the next turn's warrior beast banishes the 6 of
mages from the discard pile: immune to warriors (6C) and mages (6M), attack 10 + 6 + 6 = 22.
"""
import pytest

from helpers import _pull, keep_played_order, set_hand, set_tavern_top
from test_missions_10_12 import _campaign, _ids_everywhere, _rig, _rig_beasts, _switch_enemy
from regicide.bots import greedy_policy
from regicide.campaign import missions as M
from regicide.campaign import party as P
from regicide.engine import PHASE_DECIDE, PHASE_PLAY, Play

# top first (the discard pile's top is index 0); the 9 cards under the 6C are not known
DISCARD = ["9S", "6M", "6C", "2D", "3S", "4H", "5D", "7H", "8S", "4C", "5S", "7C"]
# top last (the banished pile's top is its last card); the three Justicars already fell
BANISHED = ["2H", "CV_J2", "3H", "4D", "CV_J3", "5H", "6D", "CV_J4", "7D", "8D", "9D", "2M", "4M", "5M", "3M"]


def _owner_turn10(reserve_top=()):
    c = _campaign(11, 1, 1100, relics=("flute", "mother"), corrupted=("8C", "3D"), stickers=(("8C", "G"),))
    for d in M.CHANTERS:
        if d["id"] != "3T":              # 54 party cards: the owner's 24 + 12 + 12 + 5 + 1
            P.add_card(c.party, dict(d))
    g = c.start_attempt(seed=1100)
    while g.phase == PHASE_DECIDE:       # the first turn's beast
        g.decide(greedy_policy(g))
    _switch_enemy(g, "CV_J1", hp=20)
    set_hand(g, ["2S", "8C", "AM", "9T"])
    _pull(g, "3D")                       # the corrupted 3 sits on the Kinfolk Flute
    g.extra["flute"] = ["3D"]
    g.extra["flute_turn"] = 8
    _pull(g, "10D")                      # played against this Justicar on an earlier turn
    g.plays = [Play(0, ["10D"], 10, ("D",))]
    _rig(g, "discard", DISCARD)
    _rig(g, "banished", BANISHED)
    _rig(g, "mission_zone", [])
    _rig_beasts(g, ["B_C", "B_S"], ["B_D", "B_H"])     # the warrior beast comes next
    if reserve_top:
        set_tavern_top(g, list(reserve_top))
    g.turn = 10
    # the owner's table
    assert g.phase == PHASE_PLAY and g.decision is None and g.solo_jesters == 2
    assert g.extra["relics"] == ["flute", "mother"] and g.n_players == 1
    assert (g.enemy.card_id, g.enemy.attack, g.enemy.max_hp, g.enemy.hp, g.enemy.suits) == ("CV_J1", 10, 30, 20, ())
    assert g.castle == ["CV_EVERGREEN"]
    assert (len(g.discard), len(g.banished), len(g.tavern)) == (12, 15, 24)
    assert g.cards["8C"].suits == ("C", "G") and g.cards["8C"].has("corrupted") and g.cards["3D"].has("corrupted")
    assert not g.cards["AM"].has("corrupted") and g.cards["9T"].suits == ("T",)
    assert g.enemy_attack == 22 and g.rules.attack_bonus(g) == 9 + 3
    assert g.rules.immune_suits(g) == ("S", "M")
    assert g.can_yield() and g.can_use_solo_jester()           # solo may yield (the owner's ruling)
    _ids_everywhere(g)
    return c, g


def _spy_immune(g):
    """Record every immunity check of the attack's resolution: (class, top discard, top
    banished, enemy immune to the class, power blocked). Installed on the instance only
    after the forecasts (a forecast deep-copies the game)."""
    seen = []
    real = g.immune

    def spy(suit, cards=()):
        blocked = real(suit, cards)
        seen.append((suit, g.discard[0] if g.discard else None, g.banished[-1] if g.banished else None,
                     suit in g.rules.immune_suits(g), blocked))
        return blocked

    g.immune = spy
    return seen


def _forecast_copies(g, ids):
    return [g._forecast_once("companion", lambda x: x.play(ids), seed, k) for k, seed in enumerate(g.FORECAST_SEEDS)]


def test_m11_owner_turn_ace_mage_corrupted_8_mother_banishes_the_discard_top():
    c, g = _owner_turn10()
    piles = (list(g.discard), list(g.banished), list(g.tavern))

    # (1) The Ace alone: the 3M on top of the banished pile blocks its mage power (the
    # red "!" alert: the lab's _clash marks a power whose forecast says immune), 20 -> 19.
    pv = g.preview_play(["AM"])
    assert pv["ok"] and pv["powers"]["M"]["immune"] is True and not pv["uncertain"]
    assert pv["mage_peeks"] == [] and pv["decision_kind"] is None
    assert (pv["attack"], pv["damage"], pv["enemy_hp_after"], pv["enemy_attack_after"]) == (1, 1, 19, 22)

    # (2) Ace + corrupted 8 (companion, strength 9). The forecast takes the Mother's reserve
    # option (it never picks the discard for the player) on copies whose reserve is
    # shuffled: the banished top becomes a face-down card, so whether the mage is blocked
    # is not known and the Mage is never reported certainly immune -- the alert goes away. Clubs
    # double whatever happens (the 8 is a corrupted warrior), the Guardian stops the damage.
    pv = g.preview_play(["AM", "8C"])
    assert pv["ok"] and pv["decision"] and pv["decision_kind"] == "mother_choice"
    assert (pv["attack"], pv["damage"], pv["enemy_hp_after"], pv["suffer"]) == (9, 18, 2, 0)
    assert not pv["defeats"] and pv["powers"]["C"].get("doubled") and pv["powers"]["G"]["result"] == {"guardian": True}
    assert not (pv["powers"].get("M") or {}).get("immune")          # no alert
    assert pv["uncertain"] and pv["enemy_attack_after"] is None       # the piles' tops after the banish are unknown
    for run in _forecast_copies(g, ["AM", "8C"]):
        # in each copy: the Mage is blocked exactly when the reserve card banished is a mage
        run_blocked = bool((run["powers"].get("M") or {}).get("immune"))
        assert run_blocked == (run["mage_peeks"] == [])
        assert (run["damage"], run["enemy_hp_after"], run["suffer"]) == (18, 2, 0)
    assert (list(g.discard), list(g.banished), list(g.tavern)) == piles and g.phase == PHASE_PLAY

    # (3) The play: step 1 (the corrupted 8 enters play) asks the Mother's choice before
    # any spell is cast; nothing is banished yet.
    g.play(["AM", "8C"])
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "mother_choice" and g.decision["card"] == "8C"
    acts = {a["option"]: a for a in g.legal_actions()}
    assert set(acts) == {"discard", "reserve"}
    assert acts["discard"]["label"] == "Banish %s, top of the discard pile" % g.cards["9S"].label()
    assert acts["reserve"]["label"] == "Banish the top card of the reserve deck"
    assert g.discard[0] == "9S" and g.banished[-1] == "3M" and len(g.tavern) == 24
    assert not any(ev["t"] in ("power", "mage_peek", "damage") for ev in g.last_events)
    assert g.plays[-1].card_ids == ["AM", "8C"] and g.plays[-1].value == 9 and g.plays[-1].mage

    # (4) The discard option: 9S is banished (the reserve is untouched), which uncovers 6M
    # on the discard pile: the mage stays blocked (no peek). Clubs: 9 x 2 = 18, 20 -> 2.
    # Guardian: the turn ends with no damage to suffer.
    seen = _spy_immune(g)
    try:
        g.decide(acts["discard"])
    finally:
        del g.immune
    ev = g.last_events
    kinds = [e["t"] for e in ev]
    banish = [e for e in ev if e["t"] == "corrupt_banish"]
    assert banish == [{"t": "corrupt_banish", "card": "8C", "banished": "9S", "source": "discard pile"}]
    assert kinds.index("corrupt_banish") < kinds.index("power")      # step 1 before the spells
    powers = {e["suit"]: e for e in ev if e["t"] == "power"}
    assert powers["M"]["immune"] is True and "mage_peek" not in kinds
    assert all(e.get("kind") != "mage_peek" for e in ev if e["t"] == "decide")
    assert powers["C"].get("doubled") and not powers["C"].get("immune")
    assert powers["G"]["result"] == {"guardian": True}
    assert [e["amount"] for e in ev if e["t"] == "damage"] == [18]
    assert {"t": "no_damage", "player": 0, "guardian": True} in ev and "suffer_due" not in kinds
    # at the mage's turn to act the 6M was the top discard (the 9S now on the banished pile)
    assert seen[:3] == [("M", "6M", "9S", True, True), ("C", "6M", "9S", False, False),
                        ("G", "6M", "9S", False, False)]

    # (5) Turn 11: the warrior beast banishes the top discard, the 6M.
    assert g.turn == 11 and g.phase == PHASE_PLAY and g.decision is None and "guardian" not in g.extra
    assert kinds.index("turn") > kinds.index("no_damage")
    assert {"t": "beast_reveal", "card": "B_C", "suit": "C", "player": 0} in ev
    assert {"t": "beast_effect", "card": "B_C", "suit": "C", "moved": "6M", "to": "banished"} in ev
    assert g.extra["beasts_out"] == ["B_D", "B_H", "B_C"] and g.extra["beast_deck"] == ["B_S"]
    assert g.enemy.card_id == "CV_J1" and g.enemy.hp == 2
    assert g.discard[0] == "6C" and g.banished[-2:] == ["9S", "6M"]
    assert set(g.rules.immune_suits(g)) == {"C", "M"}
    assert g.rules.attack_bonus(g) == 6 + 6 and g.enemy_attack == 22
    assert (len(g.discard), len(g.banished), len(g.tavern)) == (10, 17, 24)
    assert g.players[0].hand == ["2S", "9T"] and g.extra["flute"] == ["3D"]
    assert [p.card_ids for p in g.plays] == [["10D"], ["AM", "8C"]]
    assert g.can_yield() and g.can_use_solo_jester()
    _ids_everywhere(g)


def test_m11_owner_turn_reserve_option_with_a_non_mage_top_lets_the_mage_peek():
    # The other button: the reserve's top card (here the 6 of clerics) covers the 3M on the
    # banished pile, so the enemy is immune to paladins (9S) and clerics (6H), no longer to
    # mages: the Ace looks at the top 9 reserve cards and must add one.
    c, g = _owner_turn10(reserve_top=["6H", "2C", "AS", "4S", "7S", "10S", "AH", "8H", "9H", "9C"])
    g.play(["AM", "8C"])
    g.decide({"type": "mother_choice", "player": 0, "option": "reserve"})
    ev = g.last_events
    assert {"t": "corrupt_banish", "card": "8C", "banished": "6H", "source": "reserve deck"} in ev
    assert g.banished[-1] == "6H" and g.discard[0] == "9S" and g.rules.immune_suits(g) == ("S", "H")
    peek = [e for e in ev if e["t"] == "mage_peek"]
    revealed = ["2C", "AS", "4S", "7S", "10S", "AH", "8H", "9H", "9C"]
    assert len(peek) == 1 and peek[0]["count"] == 9 and peek[0]["revealed"] == revealed
    assert g.phase == PHASE_DECIDE and g.decision["kind"] == "mage_peek" and len(g.tavern) == 24 - 1 - 9
    acts = g.legal_actions()
    assert sorted(a["card"] for a in acts) == sorted(revealed) and not any(a.get("skip") for a in acts)   # a pick is owed

    g.decide({"type": "mage_pick", "player": 0, "card": "2C"})        # strength 9 + 2 = 11
    assert g.plays[-1].card_ids == ["AM", "8C", "2C"] and g.plays[-1].value == 11
    # the 8 others go to the discard pile in the player's order (the top matters here)
    assert g.decision["kind"] == "discard_order" and sorted(g.decision["options"]) == sorted(revealed[1:])
    order = [x for x in revealed[1:] if x != "9C"] + ["9C"]          # a warrior ends on top
    seen = _spy_immune(g)
    try:
        g.decide({"type": "discard_order", "player": 0, "cards": order})
    finally:
        del g.immune
    ev = g.last_events
    # The 9C on the discard pile makes the enemy immune to warriors before the clubs resolve,
    # but the corrupted 8C ignores immunity for its own classes: 11 x 2 = 22, the Justicar
    # (20 health) falls, not exactly.
    assert ("C", "9C", "6H", True, False) in seen
    powers = {e["suit"]: e for e in ev if e["t"] == "power"}
    assert powers["C"].get("doubled") and not powers["C"].get("immune")
    assert [e["amount"] for e in ev if e["t"] == "damage"] == [22]
    assert keep_played_order(g) == [["AM", "8C", "2C"]]                # the mage attack is banished
    ev = g.last_events
    defeat = [e for e in ev if e["t"] == "defeat"]
    assert len(defeat) == 1 and defeat[0]["enemy"] == "CV_J1" and not defeat[0]["exact"]
    assert defeat[0]["mage_banished"] == ["AM", "8C", "2C"]
    # the next enemy, then turn 11: the warrior beast banishes the 10D the clean-up discarded
    assert g.enemy.card_id == "CV_EVERGREEN" and g.enemy.hp == 90 and g.turn == 11 and g.phase == PHASE_PLAY
    assert {"t": "beast_effect", "card": "B_C", "suit": "C", "moved": "10D", "to": "banished"} in ev
    assert g.banished[-5:] == ["CV_J1", "AM", "8C", "2C", "10D"] and g.discard[0] == "9C"
    assert set(g.rules.immune_suits(g)) == {"C", "D"} and g.enemy_attack == 20 + 9 + 10
    assert (len(g.discard), len(g.banished), len(g.tavern)) == (12 + 8 + 1 - 1, 15 + 1 + 1 + 3 + 1, 14)
    assert g.players[0].hand == ["2S", "9T"] and g.plays == []
    _ids_everywhere(g)


def test_m11_owner_turn_reserve_option_with_a_mage_top_keeps_the_mage_blocked():
    # The reserve's top card is a mage: it lands on the banished pile and the mage stays
    # blocked; the 9S stays on the discard pile, so the next warrior beast banishes it and
    # uncovers the 6M: immune to mages (6M) and paladins (9S), attack 10 + 6 + 9 = 25.
    c, g = _owner_turn10(reserve_top=["7M"])
    g.play(["AM", "8C"])
    g.decide({"type": "mother_choice", "player": 0, "option": "reserve"})
    ev = g.last_events
    kinds = [e["t"] for e in ev]
    assert {"t": "corrupt_banish", "card": "8C", "banished": "7M", "source": "reserve deck"} in ev
    powers = {e["suit"]: e for e in ev if e["t"] == "power"}
    assert powers["M"]["immune"] is True and "mage_peek" not in kinds and powers["C"].get("doubled")
    assert [e["amount"] for e in ev if e["t"] == "damage"] == [18] and "suffer_due" not in kinds
    assert {"t": "beast_effect", "card": "B_C", "suit": "C", "moved": "9S", "to": "banished"} in ev
    assert g.turn == 11 and g.enemy.hp == 2 and g.discard[0] == "6M" and g.banished[-2:] == ["7M", "9S"]
    assert set(g.rules.immune_suits(g)) == {"M", "S"} and g.enemy_attack == 25
    assert (len(g.discard), len(g.banished), len(g.tavern)) == (11, 17, 23)
    _ids_everywhere(g)


def test_m11_forecast_merges_the_mage_over_every_copy():
    """The forecast compares a power's immunity over every copy, not only the first: a mage
    that looks at the reserve reports no power, a blocked one reports it immune, so copies
    that disagree make it None ("?"), and the number of cards a mage reveals too."""
    c, g = _owner_turn10()
    runs = _forecast_copies(g, ["AM", "8C"])
    blocked = [bool((r["powers"].get("M") or {}).get("immune")) for r in runs]
    pv = g.preview_play(["AM", "8C"])
    if all(blocked):
        assert pv["powers"]["M"]["immune"] is True and pv["mage_peeks"] == []
    elif any(blocked):
        assert pv["powers"]["M"]["immune"] is None and pv["mage_peeks"] is None and pv["uncertain"]
    else:
        assert "M" not in pv["powers"] and pv["mage_peeks"] == [9]
    # the same merge whichever copy comes first (the numbers and the immunities)
    keys = ("attack", "damage", "defeats", "exact", "enemy_hp_after", "suffer", "uncertain", "mage_peeks")
    for k in range(1, len(runs)):
        other = g._merge_forecasts(runs[k:] + runs[:k])
        assert [other[x] for x in keys] == [pv[x] for x in keys]
        assert {s: ev.get("immune") for s, ev in other["powers"].items()} == {
            s: ev.get("immune") for s, ev in pv["powers"].items()}
    # the powers keep the order they resolve in
    assert list(pv["powers"]) == [s for s in g.rules.power_order if s in pv["powers"]]


@pytest.mark.parametrize("size", [3, 4, 24, 28])
def test_m11_forecast_never_depends_on_the_reserves_hidden_order(size):
    """The copies sort the reserve before shuffling it: two reserves holding the same cards
    in a different order give the same forecast, whatever is really on top (before, each
    copy's top was the real card at a fixed position, the real top itself for some sizes)."""
    c, g = _owner_turn10()
    keep = list(g.tavern)
    mages = [x for x in keep if g.cards[x].suits == ("M",)]
    others = [x for x in keep if x not in mages]
    assert mages, "the reserve holds a mage"
    extra = others[:max(0, len(keep) - size)]
    for x in extra:                                   # trim the reserve to ``size`` cards
        g.tavern.remove(x)
        g.discard.append(x)
    base = list(g.tavern)
    previews = []
    for order in (base, list(reversed(base)), [mages[0]] + [x for x in base if x != mages[0]],
                  [x for x in base if x != mages[0]] + [mages[0]]):
        g.tavern[:] = order
        previews.append((g.preview_play(["AM", "8C"]), g.preview_play(["AM"])))
    assert all(p == previews[0] for p in previews[1:])


def test_m11_forecast_with_a_small_reserve_tries_every_card_on_top():
    """With three cards left in the reserve each copy puts a different one on top, so a
    mage block that hangs on which one is banished is a "?" whatever the real order (the
    copies once tried only two of them and could state a block for certain)."""
    c, g = _owner_turn10()
    for x in [x for x in g.tavern if x not in ("9H", "7M", "8M")]:
        g.tavern.remove(x)
        g.discard.append(x)
    import itertools
    for order in itertools.permutations(["9H", "7M", "8M"]):
        g.tavern[:] = list(order)
        pv = g.preview_play(["AM", "8C"])
        assert pv["powers"]["M"]["immune"] is None and pv["uncertain"], order


def test_main_ui_text_keeps_the_mage_qualifier_when_the_peek_is_uncertain():
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
    import fakeui
    fakeui.install()
    from app.screens import describe_preview
    c, g = _owner_turn10()
    pv = g.preview_play(["AM", "8C"])
    pv = dict(pv, mage_peeks=None)
    assert "The mage may reveal cards from the reserve. If nothing is added: " in describe_preview(g, pv)
    assert "The mage reveals 9 cards" in describe_preview(g, dict(pv, mage_peeks=[9]))
