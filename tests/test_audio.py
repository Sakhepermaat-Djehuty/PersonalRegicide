"""Sound effects and music (app/audio.py): what each game action plays and in what order,
the taps, buttons and pop-ups, the settings (effects, music, playing on silent), each
screen's music (the Kings' track for the castle's last four enemies, none once the game is
over), and silence, never an error, when a sound file is missing."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import sound  # noqa: E402  (the fake)
import ui  # noqa: E402

from app import audio as AU  # noqa: E402
from helpers import set_enemy, set_hand  # noqa: E402

EFFECTS = ["card_select", "card_deselect", "play", "draw", "shuffle", "discard", "hit", "defeat_enemy",
           "exact_kill", "new_enemy", "suffer", "jester", "yield", "power_heal", "power_double",
           "power_shield", "power_blocked", "button", "popup", "coin", "error", "victory", "loss",
           "mission_start"]


@pytest.fixture
def sounds(tmp_path, monkeypatch):
    """A sounds folder with a (silent, fake) file for every effect and music slot."""
    root = tmp_path / "sounds"
    (root / "effects").mkdir(parents=True)
    (root / "music").mkdir()
    for e in EFFECTS:
        (root / "effects" / (e + ".wav")).write_bytes(b"RIFF")
    for s in AU.MUSIC_SLOTS:
        (root / "music" / (s + ".m4a")).write_bytes(b"\0")
    monkeypatch.setattr(AU, "SOUNDS", str(root))
    del sound.history[:]
    ui.cancel_delays()
    return root


@pytest.fixture
def app(tmp_path, monkeypatch, sounds):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path / "saves"))
    from app.screens import App, MenuScreen
    ui.set_screen_size(390, 844)
    a = App()
    a.settings["rules_card"] = False
    a.show(MenuScreen(a))
    del sound.history[:]
    return a


def _played():
    """The effects played, by event name, in order."""
    return [os.path.basename(h[1])[:-4] for h in sound.history if h[0] == "effect"]


def _music():
    return [(h[0], os.path.basename(h[1])[:-4]) for h in sound.history if h[0] in ("play", "stop")]


def _tap_button(app, title):
    b = ui.button(app, title)
    ui.tap(app, *ui.root_point(app, b))


# ----------------------------------------------------------------------------- the mapping
def test_an_attack_plays_its_steps_in_order():
    evs = [{"t": "play"}, {"t": "power", "suit": "C", "doubled": True}, {"t": "damage", "amount": 10},
           {"t": "suffer_due", "amount": 10}]
    assert AU.sounds_for(evs) == [(0.0, "play"), (0.18, "power_double"), (0.42, "hit"), (1.15, "suffer")]


def test_a_kill_plays_the_defeat_then_the_next_enemy():
    evs = [{"t": "play"}, {"t": "damage"}, {"t": "defeat", "exact": False}, {"t": "reveal"}]
    assert AU.sounds_for(evs) == [(0.0, "play"), (0.42, "defeat_enemy"), (0.95, "new_enemy")]
    exact = AU.sounds_for([{"t": "play"}, {"t": "damage"}, {"t": "defeat", "exact": True}, {"t": "reveal"}])
    assert (0.42, "exact_kill") in exact and not any(n == "hit" for _, n in exact)


def test_the_powers_and_the_other_moves_have_their_own_sounds():
    s = lambda *evs: [n for _, n in AU.sounds_for(list(evs))]  # noqa: E731
    assert s({"t": "power", "immune": True}) == ["power_blocked"]
    assert s({"t": "power", "healed": 3}) == ["power_heal"]
    assert s({"t": "power", "shield": 4}) == ["power_shield"]
    assert s({"t": "power", "drawn": 2}, {"t": "draw"}, {"t": "draw"}) == ["draw"]       # once, however many
    assert s({"t": "suffer"}) == ["discard"]
    assert s({"t": "jester"}) == ["jester"] and s({"t": "solo_jester"}) == ["jester"]
    assert s({"t": "yield"}, {"t": "suffer_due"}) == ["yield", "suffer"]
    assert s({"t": "decide"}, {"t": "turn"}) == []


def test_the_last_blow_then_the_jingle_and_nothing_of_a_next_turn():
    won = AU.sounds_for([{"t": "play"}, {"t": "damage"}, {"t": "defeat", "exact": False}, {"t": "reveal"},
                         {"t": "won"}])
    assert [n for _, n in won] == ["play", "defeat_enemy", "victory"]
    lost = AU.sounds_for([{"t": "suffer_due"}, {"t": "lost"}])
    assert [n for _, n in lost] == ["loss"]


# ----------------------------------------------------------------------------- in the app
def _solo(app):
    from app.screens import GameScreen
    from regicide.rules import GameConfig
    app.start_game(GameConfig(players=1), seed=3)
    gs = app.current
    assert isinstance(gs, GameScreen)
    return gs, app.game


def test_a_game_starts_with_its_jingle_and_the_table_music(app):
    gs, g = _solo(app)
    assert _played() == ["mission_start"]
    assert _music()[-1] == ("play", "table")


def test_card_taps_buttons_and_an_attack(app):
    gs, g = _solo(app)
    set_enemy(g, "J", "C")
    set_hand(g, ["5H", "9D", "2S", "3C"])
    gs.refresh(after_action=False)
    del sound.history[:]
    ui.tap(app, *ui.root_point(app, gs.hand.views["5H"]))
    ui.tap(app, *ui.root_point(app, gs.hand.views["5H"]))
    ui.tap(app, *ui.root_point(app, gs.hand.views["9D"]))
    assert _played() == ["card_select", "card_deselect", "card_select"]
    del sound.history[:]
    _tap_button(app, "Play")
    assert _played()[:2] == ["button", "play"]            # the rest follows, spaced out
    ui.run_delays()
    assert _played() == ["button", "play", "hit", "draw", "suffer"]   # 9♦: the blow, the Bard's draw, the enemy's


def test_an_illegal_play_says_no(app):
    from regicide.engine import IllegalAction
    gs, g = _solo(app)
    del sound.history[:]

    def nope():
        raise IllegalAction("not allowed")
    gs._act(nope)
    assert _played() == ["error"]


def test_a_card_pop_up_and_a_hire_have_their_sounds(app):
    from app.screens import CampaignScreen, MercenaryScreen
    app.new_campaign(1, ["Solo"])
    app.campaign.m_box_opened, app.campaign.coins = True, 2
    app.show(CampaignScreen(app))
    del sound.history[:]
    _tap_button(app, "Mission rules")
    assert _played() == ["button", "popup"]
    app.show(MercenaryScreen(app))
    del sound.history[:]
    ui.tap(app, *ui.root_point(app, app.current.card_views["merc_12C"]))
    _tap_button(app, "Hire for 1 coin")
    assert _played() == ["popup", "button", "coin"]


def test_each_screen_has_its_music_and_the_kings_theirs(app):
    from app.screens import MenuScreen
    gs, g = _solo(app)
    assert _music()[-1] == ("play", "table")
    while len(g.castle) > 3:                              # on to the last four enemies
        g.castle.pop(0)
    gs.refresh(after_action=False)
    assert _music()[-2:] == [("stop", "table"), ("play", "boss")]
    del sound.history[:]
    gs.refresh(after_action=False)
    assert _music() == []                                 # the same track goes on
    g._lose("test")
    gs.refresh(after_action=False)
    assert _music()[-1] == ("stop", "boss")               # the game is over: silence for its jingle
    app.show(MenuScreen(app))
    assert _music()[-1] == ("play", "menu")


def test_the_settings_turn_effects_music_and_silent_mode_on_and_off(app):
    from app.screens import SettingsScreen
    app.show(SettingsScreen(app))
    switches = {v: v for v in ui.find(app, lambda v: isinstance(v, ui.Switch))}
    labels = [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]
    assert "Sound effects" in labels and "Music" in labels and "Play sound when the phone is on silent" in labels
    assert len(switches) == 8
    scr = app.current
    del sound.history[:]
    scr._toggle("sound_in_silent_mode", False)
    assert ("honors_silent_switch", True) in sound.history and app.settings["sound_in_silent_mode"] is False
    scr._toggle("music", False)
    assert _music()[-1] == ("stop", "menu") and app.audio.player is None
    scr._toggle("music", True)
    assert _music()[-1] == ("play", "menu")
    scr._toggle("sound_effects", False)
    del sound.history[:]
    app.audio.effect("hit")
    ui.tap(app, 4, 4)
    assert _played() == []


def test_silent_mode_plays_by_default(sounds):
    a = AU.Audio({})
    assert ("honors_silent_switch", False) in sound.history
    del sound.history[:]
    AU.Audio({"sound_in_silent_mode": False})
    assert ("honors_silent_switch", True) in sound.history


def test_a_missing_file_is_silence_not_an_error(sounds, monkeypatch, tmp_path):
    monkeypatch.setattr(AU, "SOUNDS", str(tmp_path / "nowhere"))
    a = AU.Audio({})
    del sound.history[:]
    a.effect("hit")
    a.game_events([{"t": "play"}, {"t": "damage"}])
    a.music("table")
    assert sound.history == [] and a.player is None
