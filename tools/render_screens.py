"""Render the app's screens to PNG with the fake ui, for visual review on a desktop.

    python tools/render_screens.py [out_dir] [--size 390x844]
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("REGICIDE_SAVE_DIR", os.path.join(ROOT, "tools", "out", "saves"))

import fakeui  # noqa: E402
fakeui.install()
import ui  # noqa: E402

from app.screens import App, GameScreen, MenuScreen, NewGameScreen, RulesScreen, SettingsScreen  # noqa: E402
from regicide.bots import greedy_policy, min_waste_discard  # noqa: E402
from regicide.engine import PHASE_PLAY, PHASE_SUFFER  # noqa: E402
from regicide.rules import GameConfig  # noqa: E402


def main(argv):
    out = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else os.path.join(ROOT, "tools", "out")
    size = (390, 844)
    for a in argv:
        if a.startswith("--size"):
            w, h = a.split("=")[1].split("x")
            size = (int(w), int(h))
    os.makedirs(out, exist_ok=True)
    ui.set_screen_size(*size)

    def shot(app, name):
        path = os.path.join(out, name + ".png")
        ui.render(app, path)
        print("wrote", path)

    app = App()
    app.show(MenuScreen(app))
    shot(app, "01_menu")
    app.show(NewGameScreen(app, 3))
    shot(app, "02_new_game_3p")
    app.show(RulesScreen(app))
    shot(app, "03_rules")
    app.show(SettingsScreen(app))
    shot(app, "04_settings")

    # solo game, fresh
    app.start_game(GameConfig(players=1), seed=11)
    gs = app.current
    assert isinstance(gs, GameScreen)
    shot(app, "10_solo_start")
    # select the bot's suggested play to show the forecast
    act = greedy_policy(app.game)
    if act["type"] == "play":
        gs.hand.set_selection(act["cards"])
    shot(app, "11_solo_selected")
    ui.tap(app, *ui.root_point(app, gs.right_btn))
    shot(app, "12_solo_after_play")
    if app.game.phase == PHASE_SUFFER:
        ui.tap(app, *ui.root_point(app, gs.left_btn))  # suggest
        shot(app, "13_solo_suffer_suggested")
        ui.tap(app, *ui.root_point(app, gs.right_btn))
        shot(app, "14_solo_after_suffer")
    # play a few turns with the bot to reach a mid-game
    from regicide.bots import apply_action
    for _ in range(6):
        if app.game.is_over:
            break
        apply_action(app.game, greedy_policy(app.game))
    gs.message_text = ""
    gs.refresh(after_action=False)
    shot(app, "15_solo_midgame")
    ui.tap(app, *ui.root_point(app, gs.menu_btn))
    shot(app, "16_game_menu")
    gs.refresh(after_action=False)

    # 3 player pass and play
    app.start_game(GameConfig(players=3, names=("Ana", "Ben", "Cy")), seed=5)
    gs = app.current
    shot(app, "20_3p_handover")
    ui.tap(app, *ui.root_point(app, ui.button(app, "Show my hand")))
    shot(app, "21_3p_hand")
    # give Ana a Jester to show the choose-next overlay
    g = app.game
    jester = [c for c in g.cards.values() if c.is_jester][0]
    for p in g.players:
        if jester.id in p.hand:
            p.hand.remove(jester.id)
    if jester.id in g.tavern:
        g.tavern.remove(jester.id)
    g.players[0].hand.append(jester.id)
    gs.refresh(after_action=False)
    gs.hand.set_selection([jester.id])
    shot(app, "22_3p_jester_selected")
    ui.tap(app, *ui.root_point(app, gs.right_btn))
    shot(app, "23_3p_choose_next")

    # a finished game (loss) to show the result overlay
    app.start_game(GameConfig(players=1), seed=3)
    gs = app.current
    from regicide.bots import play_out
    play_out(app.game, greedy_policy)
    gs.refresh(after_action=False)
    shot(app, "30_result")
    # campaign
    from app.screens import CampaignScreen, MercenaryScreen, MissionListScreen, PartyScreen, MapScreen, LoreScreen, LoadGameScreen, ProgressScreen
    from app import store
    for r in store.list_campaigns():
        store.delete_campaign(r["slot"])
    app.campaign = None
    app.show(MenuScreen(app))
    shot(app, "40_menu_no_games")
    app.new_campaign(1, ["Solo"], "First run")
    shot(app, "41_campaign_mission1")
    app.start_attempt()
    gs = app.current
    shot(app, "42_campaign_attempt")
    ui.tap(app, *ui.root_point(app, gs.mid_btn))
    shot(app, "43_jester_class_choice")
    gs.refresh(after_action=False)
    # win mission 1 quickly, show rewards
    g = app.game
    g.castle = []
    g.enemy.hp = 1
    gs.refresh(after_action=False)
    gs.hand.set_selection([g.hand()[0].id])
    ui.tap(app, *ui.root_point(app, gs.right_btn))
    shot(app, "44_mission_complete")
    app.show(CampaignScreen(app))
    shot(app, "45_campaign_mission2")
    app.start_attempt()
    gs = app.current
    g = app.game
    for cid in list(g.tavern):
        c = g.cards[cid]
        if 2 <= c.value <= 5 and c.is_number and not c.name:
            g.tavern.remove(cid)
            g.players[0].hand[0] = cid
            break
    gs.refresh(after_action=False)
    shot(app, "46_hydra_attempt")
    ui.tap(app, *ui.root_point(app, gs.special_btn))
    shot(app, "47_flute_actions")
    gs.refresh(after_action=False)
    g._lose("The hydra was too much.")
    gs.refresh(after_action=False)
    shot(app, "48_mission_lost")
    app.show(MercenaryScreen(app))
    shot(app, "49_mercenary_camp")
    app.show(PartyScreen(app))
    shot(app, "50_party")
    app.show(ProgressScreen(app))
    shot(app, "51_progress")
    app.show(MapScreen(app))
    shot(app, "52_map")
    app.show(LoreScreen(app, local=True))
    shot(app, "53_lore")
    app.new_campaign(3, ["Ana", "Ben", "Cy"], "Second run")
    app.show(LoadGameScreen(app))
    shot(app, "54_load_game")
    app.show(MenuScreen(app))
    shot(app, "55_menu_with_games")
    print("done")


if __name__ == "__main__":
    main(sys.argv)
