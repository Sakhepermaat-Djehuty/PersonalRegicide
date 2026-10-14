"""The owner plays a themeless deck: the cards the party holds are plain playing cards,
rank and class only. Gøran's beasts are plain B cards; the class decks, the mages, the
pilgrims and the mercenaries carry no names either. Only the story characters the mission
cards name (Gøran, Myla, Esme, the High Arcana) keep theirs."""
import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402

from app import store  # noqa: E402
from app import theme as T  # noqa: E402
from app import widgets  # noqa: E402
from app.widgets import CardView, card_caption  # noqa: E402
from regicide.campaign import CampaignState  # noqa: E402
from regicide.campaign import evergreen as E  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402
from regicide.campaign.mercenaries import MERCENARIES  # noqa: E402
from regicide.cards import Card  # noqa: E402
from regicide.engine import Enemy  # noqa: E402

STORY_IDS = {"GOR8", "GOR8E", "MYLA7", "ESME6E", "ARC25"}
# Names printed on the physical cards (and races) that the app no longer shows.
FLAVOUR = ["Bonty", "Cosmo", "Tui", "Lola", "Ash", "Quill", "Puppy", "puppy", "Roslyn", "Tolman", "Alantha",
           "Druldox", "Runo", "Teko", "Oaken", "Harore", "Hella", "Zimis", "Nelle", "Xam", "Raki", "Taitonga",
           "Bristle", "Thistle", "James", "Jakhim", "Lee", "Bronze", "Snow", "Glamelyn", "Herbod", "Dhonatir",
           "Sprinkle", "Dinky", "Wicket", "Deccari", "dwarves", "Dwarves", "feltrix", "Feltrix", "Follower",
           "Servant", "Acolyte", "Seeker", "Traveller", "Halfling", "Avion", "Drakonid", "Elf", "Gnome"]
_FLAVOUR_RE = re.compile(r"\b(%s)\b" % "|".join(FLAVOUR))


def _party_side_cards():
    return (M.BEASTS + [M.ASH] + M.MAGE_DECK + M.CHANTERS + M.DRUIDS + M.GUARDIANS + M.REAVERS + M.PILGRIMS
            + [m["card"] for m in MERCENARIES])


def test_party_side_cards_are_plain_and_only_the_story_characters_keep_a_name():
    assert all("name" not in d and "subtitle" not in d for d in _party_side_cards())
    named = [M.GORAN, M.GORAN_RENEWED, M.MYLA, M.ESME_REBORN, M.HIGH_ARCANA]
    assert {d["id"] for d in named} == STORY_IDS
    assert all(d.get("name") and "subtitle" not in d for d in named)
    assert M.plain_card_ids() == {str(d["id"]) for d in _party_side_cards()}


def test_plain_labels_read_like_playing_cards():
    label = lambda d: P.to_card(d).label()   # noqa: E731
    assert [label(b) for b in M.BEASTS] == ["B♥", "B♦", "B♣", "B♠"]
    assert label(M.ASH) == "B★" and label(M.MAGE_DECK[0]) == "A★"
    assert [label(d) for d in M.REAVERS] == ["3⚔", "5⚔", "7⚔", "9⚔"]
    assert label(M.PUPPY) == "Pilgrim A" and {label(d) for d in M.PILGRIMS if d["rank"] == "4"} == {"Pilgrim 4"}
    mercs = {m["id"]: (m["name"], label(m["card"])) for m in MERCENARIES}
    assert mercs["merc_12H"] == ("12 Cleric", "12♥") and mercs["merc_25S"] == ("2/5 Paladin", "2/5♠")
    assert mercs["merc_19_1"] == mercs["merc_19_2"] == ("19 (no class)", "19")
    assert mercs["merc_ace_1"] == ("Wild Animal (choose a class)", "Wild Animal")
    assert mercs["merc_jester_2"] == ("Jester", "Jester")
    assert label(M.GORAN) == "Gøran (8)" and label(M.MYLA) == "Myla (7)" and label(M.HIGH_ARCANA) == "High Arcana (25)"
    puppy = dict(M.PUPPY, flags=["evergreen_puppy"])     # Evergreen boon 28's copy
    assert label(puppy) == "Pilgrim A"


def test_texts_the_app_shows_name_no_flavour_card():
    texts = []
    for m in M.MISSIONS:
        texts += [m.get("summary", ""), m.get("rewards_text", "")]
    camp = CampaignState.new(1, ["Ana"], seed=7)
    for n in range(1, 13):
        texts += [str(s.get("label", "")) for s in M.reward_steps(camp, n, random.Random(n))]
        texts += [str(s.get("label", "")) for s in M.start_steps(camp, n)]
    texts += [str(m["name"]) for m in MERCENARIES]
    texts += [b["text"] for b in E.BANES + E.BOONS]
    hits = sorted({(t[:60], h) for t in texts for h in _FLAVOUR_RE.findall(t)})
    assert hits == []


def test_card_faces_show_rank_and_class_and_names_only_the_story_characters():
    drawn = []
    real = ui.draw_string

    def spy(text, *a, **kw):
        drawn.append(text)
        return real(text, *a, **kw)

    ui.draw_string = spy
    try:
        def face(d, small=False):
            del drawn[:]
            v = CardView(P.to_card(d), frame=(0, 0, 80, 114))
            v.small = small
            ui.render(v)
            return [t for t in drawn if t]

        beast = face(M.BEASTS[2])
        assert beast == ["B", "♣", "♣"]                    # corner index and centre pip, no badge, no name
        assert face(M.BEASTS[2], small=True) == ["B", "♣"]
        assert face(M.PILGRIMS[5]) == ["3", "3", "pilgrim"]  # classless: the rank large in the middle
        nineteen = [m["card"] for m in MERCENARIES if m["id"] == "merc_19_1"][0]
        assert face(nineteen) == ["19", "19"]
        assert face(M.GORAN) == ["8", "8", "Gøran"]
        # corrupted and restored cards are shown by their sleeve only (a purple or green
        # edge) and keep their own class icons; the tree replaces the four basic class icons
        # on the Evergreen cards only (the renewed Gøran, Esme)
        corrupted = {"id": "6C", "rank": "6", "suits": ["C"], "value": 6, "flags": ["corrupted"]}
        restored = {"id": "6C", "rank": "6", "suits": ["C"], "value": 6, "flags": ["restored"]}
        stickered = {"id": "4D", "rank": "4", "suits": ["D", "U"], "value": 4, "flags": ["restored"]}
        assert face(corrupted) == ["6", "♣", "♣"] and face(restored) == ["6", "♣", "♣"]
        assert face(stickered) == ["4", "♦", "✿", "♦", "✿"]
        assert face(dict(M.GORAN_RENEWED)) == ["8", "Gøran"]          # its pips are trees
    finally:
        ui.draw_string = real
    assert widgets.sleeve_color(P.to_card(corrupted)) == T.CORRUPTED
    assert widgets.sleeve_color(P.to_card(restored)) == T.RESTORED
    assert widgets.sleeve_color(P.to_card(M.GORAN_RENEWED)) == "" and widgets.sleeve_color(P.to_card(M.BEASTS[0])) == ""
    assert widgets.face_pips(P.to_card(stickered)) == ["D", "U"]
    assert widgets.face_pips(P.to_card(M.ESME_REBORN)) == [widgets.TREE_PIP]
    assert widgets.card_color(P.to_card(M.GORAN_RENEWED)) == T.EVERGREEN
    assert widgets.card_color(P.to_card(restored)) == T.SUIT_COLOR["C"]
    trees = []
    real_tree = widgets.draw_tree
    widgets.draw_tree = lambda *a: trees.append(a)
    try:
        for d, small in ((restored, False), (restored, True), (corrupted, False), (M.ESME_REBORN, False)):
            v = CardView(P.to_card(d), frame=(0, 0, 80, 114))
            v.small = small
            ui.render(v)
    finally:
        widgets.draw_tree = real_tree
    # none on a restored or corrupted card; corner + centre on Esme
    assert len(trees) == 2 and all(t[-1] == T.EVERGREEN for t in trees)
    assert card_caption(P.to_card(M.BEASTS[0])) == "" and card_caption(P.to_card(M.PUPPY)) == "pilgrim"
    assert card_caption(P.to_card([m["card"] for m in MERCENARIES if m["id"] == "merc_ace_1"][0])) == ""   # corners say it


def test_saves_from_before_lose_the_flavour_names(tmp_path, monkeypatch):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    c = CampaignState.new(1, ["Ana"], seed=3)
    d = c.to_dict()
    d["party"] += [
        {"id": "B_H", "rank": "B", "suits": ["H"], "value": 0, "name": "Bonty", "flags": ["beast"]},
        {"id": "5R", "rank": "5", "suits": ["R"], "value": 5, "name": "Harore", "subtitle": "Avion Reaver", "flags": []},
        {"id": "GOR8", "rank": "8", "suits": [], "value": 8, "name": "Gøran", "subtitle": "Feltrix Evergreen", "flags": []},
    ]
    d["away"] = [{"id": "3U", "rank": "3", "suits": ["U"], "value": 3, "name": "Tolman", "flags": []}]
    d["pending"] = [{"kind": "add_card", "label": "x",
                     "card": {"id": "B_ASH", "rank": "B", "suits": ["M"], "value": 0, "name": "Ash", "subtitle": "Beast",
                              "flags": ["beast"]}}]
    c2 = CampaignState.from_dict(json.loads(json.dumps(d)))
    assert "name" not in P.find(c2.party, "B_H") and "name" not in P.find(c2.party, "5R")
    assert "subtitle" not in P.find(c2.party, "5R")
    assert P.find(c2.party, "GOR8")["name"] == "Gøran" and "subtitle" not in P.find(c2.party, "GOR8")
    assert "name" not in c2.away[0] and "name" not in c2.pending[0]["card"]
    assert P.find(c2.party, "5R")["suits"] == ["R"] and P.find(c2.party, "B_H")["flags"] == ["beast"]
    # an attempt saved before the change: its plain cards lose their names, the rest keep theirs
    c2.pending = []
    g = c2.start_attempt(seed=5)
    g.cards["B_H"] = g.cards["B_H"].with_changes(name="Bonty")
    g.cards["GOR8"] = g.cards["GOR8"].with_changes(name="Gøran")
    enemy_name = g.cards[g.enemy.card_id].name
    store.save_attempt(g, c2.slot)
    g2 = store.load_attempt(c2.slot)
    assert g2.cards["B_H"].name == "" and g2.cards["B_H"].label() == "B♥"
    assert g2.cards["GOR8"].name == "Gøran" and g2.cards[g2.enemy.card_id].name == enemy_name


def test_restored_cards_keep_their_own_classes():
    """Owner: restored cards have green borders and keep their classes; only the Evergreen
    cards (Gøran and Esme) are the four base classes. A short-lived build gave restored
    cards all four; such saves and attempts go back to the printed classes."""
    c = CampaignState.new(1, ["Ana"], seed=4)
    for cid in ("3H", "4D"):
        P.add_flag(c.party, cid, "corrupted")
        c.corrupted.append(cid)
    P.add_suit(c.party, "4D", "U")
    M.apply_step(c, {"kind": "restore_all", "label": "x"}, random.Random(1))
    assert P.find(c.party, "3H")["suits"] == ["H"] and P.find(c.party, "4D")["suits"] == ["D", "U"]
    assert P.find(c.party, "3H")["flags"] == ["restored"] and P.to_card(P.find(c.party, "3H")).label() == "3♥"
    # a save from the short-lived build: with and without its record of the printed classes
    d = c.to_dict()
    for card in d["party"]:
        if card["id"] == "3H":
            card["suits"], card["base_suits"] = ["H", "D", "C", "S"], ["H"]
        if card["id"] == "4D":
            card["suits"] = ["H", "D", "C", "S", "U"]
    esme = dict(M.ESME_REBORN, flags=["evergreen", "ignores_immunity", "restored"])
    d["party"].append(esme)
    c2 = CampaignState.from_dict(json.loads(json.dumps(d)))
    assert P.find(c2.party, "3H")["suits"] == ["H"] and "base_suits" not in P.find(c2.party, "3H")
    assert P.find(c2.party, "4D")["suits"] == ["D", "U"]
    assert P.find(c2.party, "ESME6E")["suits"] == ["H", "D", "C", "S"]       # the Evergreen stays all four
    # an attempt saved by that build
    g = c2.start_attempt(seed=8)
    if "3H" in g.cards:
        g.cards["3H"] = g.cards["3H"].with_changes(suits=("H", "D", "C", "S"))
        M.strip_game_names(g)
        assert g.cards["3H"].suits == ("H",)


def test_old_save_text_and_attempt_enemy_are_rewritten(tmp_path, monkeypatch):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    c = CampaignState.new(1, ["Ash"], seed=5)        # a player called Ash keeps the name
    d = c.to_dict()
    d["flags"].pop("plain_text")
    d["log"] += ["Oaken leaves the party.", "Hired Hella (12, Paladin) for 1 coin.", "Ash wins the mission.",
                 "Follower (3) banished from the mission zone."]
    d["pending"] = [
        {"kind": "choice_suit", "suit": "R", "options": ["6H"],
         "label": "Harore teaches a 6: James (Cleric), Jakhim (Bard) or Lee (Paladin) gains the Reaver class"},
        {"kind": "choice_mage_student", "options": ["4", "8"],
         "label": "A new student: choose dwarves (4) or feltrix (8); the first unstickered one revealed gains the Mage class"},
        {"kind": "remove_card", "card_id": "5G", "label": "Teko stays to rebuild the garden"},
    ]
    c2 = CampaignState.from_dict(json.loads(json.dumps(d)))
    assert c2.log[-4:] == ["3⚔ leaves the party.", "Hired 12 Paladin for 1 coin.", "Ash wins the mission.",
                           "Pilgrim 3 banished from the mission zone."]
    assert [s["label"] for s in c2.pending] == [M.CHOICE_SUIT_LABELS["R"], M.MAGE_STUDENT_LABEL,
                                                "5⛨ stays to rebuild the garden"]
    assert c2.flags["plain_text"] is True
    c3 = CampaignState.from_dict(json.loads(json.dumps(c2.to_dict())))
    assert c3.log == c2.log                                   # rewritten once only
    # a saved attempt whose current enemy is a once-named party card (mission 10)
    c2.pending = []
    g = c2.start_attempt(seed=6)
    g.cards["5R"] = Card(id="5R", rank="5", suits=("R",), value=5, name="Harore", flags=("corrupted",))
    g.castle.append(g.enemy.card_id)
    g.enemy = Enemy("5R", "Harore", ("R",), 5, 25, 25)
    store.save_attempt(g, c2.slot)
    g2 = store.load_attempt(c2.slot)
    assert g2.cards["5R"].name == "" and g2.enemy.name == "5 of Reavers" and g2.enemy.hp == 25


def test_small_faces_show_their_tag():
    drawn = []
    real = ui.draw_string
    ui.draw_string = lambda text, *a, **kw: (drawn.append(text), real(text, *a, **kw))[1]
    try:
        v = CardView(P.to_card({"id": "7S", "rank": "7", "suits": ["S"], "value": 7}), frame=(0, 0, 32, 46))
        v.small = True
        v.badge = "2"
        ui.render(v)
    finally:
        ui.draw_string = real
    assert drawn == ["7", "♠", "2"]


def test_an_imported_lore_file_is_found_and_kept_in_the_saves_folder(tmp_path, monkeypatch):
    """The phone won't let the owner put files in Pythonista's folders by hand; a file
    imported into Pythonista lands in its Documents root (or Inbox). The app finds it there
    and copies it into the saves folder, which updates never touch."""
    saves = tmp_path / "PersonalRegicide-saves"
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(saves))
    assert store.lore_overlay_path() == str(saves / "lore_private.json")     # nothing anywhere yet
    (tmp_path / "Inbox").mkdir()
    (tmp_path / "Inbox" / "lore_private.json").write_text("not json")      # an unreadable file is ignored
    assert not (saves / "lore_private.json").exists() and store.lore_overlay_path() == str(saves / "lore_private.json")
    (tmp_path / "lore_private.json").write_text(json.dumps({"m1_intro": {"title": "T", "text": "Private."}}))
    path = store.lore_overlay_path()
    assert path == str(saves / "lore_private.json") and json.loads((saves / "lore_private.json").read_text())["m1_intro"]["text"] == "Private."
