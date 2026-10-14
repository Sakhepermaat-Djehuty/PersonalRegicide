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
from app.widgets import CardView, card_caption  # noqa: E402
from regicide.campaign import CampaignState  # noqa: E402
from regicide.campaign import evergreen as E  # noqa: E402
from regicide.campaign import missions as M  # noqa: E402
from regicide.campaign import party as P  # noqa: E402
from regicide.campaign.mercenaries import MERCENARIES  # noqa: E402
from regicide.cards import Card  # noqa: E402

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
    assert mercs["merc_12H"] == ("12 Cleric", "12♥") and mercs["merc_25S"] == ("2/5 Paladin", "2♠")
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
        corrupted = dict(M.BEASTS[0], flags=["beast", "corrupted"])
        assert face(corrupted)[-1] == "corrupted"
    finally:
        ui.draw_string = real
    assert card_caption(P.to_card(M.BEASTS[0])) == "" and card_caption(P.to_card(M.PUPPY)) == "pilgrim"
    assert card_caption(P.to_card([m["card"] for m in MERCENARIES if m["id"] == "merc_ace_1"][0])) == "any class"


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
