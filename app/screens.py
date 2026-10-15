"""Screens and app flow for the Pythonista client."""
from __future__ import annotations

import os
import random
from typing import Callable, Dict, List, Optional

import ui

from regicide.bots import greedy_policy, min_waste_discard, simple_decision, team_discard_choice
from regicide.campaign import CampaignState
from regicide.campaign import lore as L
from regicide.campaign import party as P
from regicide.campaign.missions import MISSIONS, mission as mission_info
from regicide.cards import BASIC_SUITS, CLASS_NAME, SUIT_NAME, SUIT_SYMBOL, Card
from regicide.engine import (PHASE_CHOOSE_NEXT, PHASE_DECIDE, PHASE_LOST, PHASE_PLAY, PHASE_SUFFER,
                             PHASE_WON, Game, IllegalAction)
from regicide.rules import GameConfig

from . import store
from . import theme as T
from .widgets import (CardStrip, CardView, HandGrid, TableHeader, fit_label, fit_title, make_button, make_label,
                      set_enabled, text_size)

VERSION = "alpha 5.1"

# Relic ids (campaign saves, ``game.extra["relics"]``) -> names and card texts.
from regicide.campaign.relics import relic_name, relic_text  # noqa: E402


def suit_name(game: Game, s: str) -> str:
    if getattr(game.rules, "legacy", False):
        return CLASS_NAME.get(s, SUIT_NAME.get(s, s))
    return SUIT_NAME.get(s, s)


def class_list(suits) -> str:
    """Class names, short: "Cleric, Bard, Paladin"."""
    return ", ".join(CLASS_NAME.get(s, s) for s in suits)


def zone_caption(g: Game) -> tuple:
    """(cards, title) for the mission zone strip of a Legacy game: what the zone holds and
    what it does to the enemy right now (strength, immunity, team damage, pile counts).
    Kept short: the title has two lines of the strip's width (354pt at 11pt on a 390pt
    screen)."""
    zone_cards = [g.card(c) for c in g.mission_zone]
    imm = [s for s in g.rules.immune_suits(g) if g.enemy is not None and s not in g.enemy.suits]
    number = getattr(g.rules, "mission", 0)
    title = "Mission zone"
    parts: List[str] = []
    if number == 9:
        # Mission 9: the zone holds the captured piles; the strip shows their top cards.
        piles = g.extra.get("captured", [])
        zone_cards = [g.card(p[0]) for p in piles if p]
        return zone_cards, ("Captured piles · " + " / ".join(str(len(p)) for p in piles) if piles else "Captured piles (none)")
    if number == 11:
        # Mission 11: the beast deck (face down) and the revealed beasts (face up).
        deck = g.extra.get("beast_deck", [])
        out = g.extra.get("beasts_out", [])
        zone_cards = [g.card(c) for c in out]
        title = "Beast deck · %d face down" % len(deck)
        if out:
            title += " · revealed: " + class_list(g.card(c).suits[0] if g.card(c).suits else "?" for c in out)
        if g.extra.get("skip_beast"):
            title += " · no reveal next turn"
        return zone_cards, title
    if number == 7:
        pilgrims = [c for c in zone_cards if c.has("pilgrim")]
        parts.append("%d pilgrim%s, total %d" % (len(pilgrims), "" if len(pilgrims) == 1 else "s", g.rules.zone_strength(g)))
        parts.append("%d in the pilgrim deck" % len(g.extra.get("pilgrim_deck", [])))
        return zone_cards, title + " · " + " · ".join(parts)
    if number == 13:
        loc = g.rules.location(g)
        title = "Mission zone (the %s)" % g.rules.location_name(g)
        if loc == "E":
            parts.append("%d in the pilgrim deck" % len(g.extra.get("pilgrim_deck", [])))
        if loc == "B" and g.enemy is not None:
            parts.append("strength %d of %d to banish" % (g.rules.zone_strength(g), g.enemy.attack))
        if loc == "D" and zone_cards:
            parts.append("team damage %d at end of turn" % g.rules.zone_strength(g))
        if loc == "C" and zone_cards:
            parts.append("enemy strength +%d" % g.rules.zone_strength(g))
    elif zone_cards and number in (5, 8, 10, 12):
        bonus = g.rules.zone_strength(g) if number != 8 else g.rules.attack_bonus(g)
        parts.append("enemy strength +%d" % bonus)
    if imm and number != 11:
        parts.append("immune: " + class_list(imm))
    if number == 6 and zone_cards:
        parts.append("Myla's team damage %d" % g.rules.zone_strength(g))
    if number == 12 and g.extra.get("skip_zone"):
        parts.append("no card next turn")
    if parts:
        title += " · " + " · ".join(parts)
    elif not zone_cards:
        title += " (empty)"
    return zone_cards, title


def status_text(g: Game, width: float, size: int = 13) -> str:
    """The status line: Turn · Reserve · Discard · Banished · Jesters, as much as fits in
    ``width``: the turn number goes first, then the banished count; the solo Jester count
    (shown nowhere else) stays."""
    legacy = bool(getattr(g.rules, "legacy", False))
    turn = "Turn %d" % g.turn
    core = ["%s %d" % ("Reserve" if legacy else "Tavern", len(g.tavern)), "Discard %d" % len(g.discard)]
    banished = ["Banished %d" % len(g.banished)] if g.banished else []
    jesters = ["Jesters %d" % g.solo_jesters] if g.n_players == 1 else []
    for parts in ([turn] + core + banished + jesters, core + banished + jesters, core + jesters):
        text = " · ".join(parts)
        if text_size(text, 0, size)[0] <= width:
            return text
    return " · ".join(core + jesters)


# ============================================================================ base
class Screen(ui.View):
    def __init__(self, app: "App", **kw) -> None:
        super().__init__(**kw)
        self.app = app
        self.background_color = T.BG

    def on_show(self) -> None:
        pass

    def layout(self) -> None:
        pass


def apply_face_style(settings: dict) -> None:
    """Card faces follow the "classic_faces" setting (see ``widgets.FACE_STYLE``)."""
    from . import widgets
    widgets.FACE_STYLE = "classic" if settings.get("classic_faces") else "simple"


class App(ui.View):
    """Root view; shows one Screen at a time."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        w, h = ui.get_screen_size()
        self.frame = (0, 0, w, h)
        self.background_color = T.BG
        self.name = "PersonalRegicide"
        self.settings = store.load_settings()
        apply_face_style(self.settings)
        self.game: Optional[Game] = None
        self.undo_stack: List[dict] = []
        self.current: Optional[Screen] = None
        self.campaign: Optional[CampaignState] = None
        last = self.settings.get("last_campaign")
        if last and store.has_campaign(last):
            self.campaign = store.load_campaign(last)
        self.in_campaign = False

    def show(self, screen: Screen) -> None:
        if self.current is not None:
            self.remove_subview(self.current)
        T.apply_safe_area(self)
        self.current = screen
        screen.frame = (0, 0, self.width, self.height)
        self.add_subview(screen)
        screen.layout()
        screen.on_show()

    def layout(self) -> None:
        cur = getattr(self, "current", None)
        if cur is not None:
            T.apply_safe_area(self)
            cur.frame = (0, 0, self.width, self.height)
            cur.layout()

    # ------------------------------------------------------------- game flow
    def start_game(self, config: GameConfig, seed: Optional[int] = None) -> None:
        self.in_campaign = False
        self.game = Game.new(config, seed=seed)
        self.undo_stack = []
        self.autosave()
        self.show(GameScreen(self))

    def resume_game(self) -> bool:
        g = store.load_game()
        if g is None:
            return False
        self.in_campaign = False
        self.game = g
        self.undo_stack = []
        self.show(GameScreen(self))
        return True

    # campaign ----------------------------------------------------------
    def new_campaign(self, players: int, names: List[str], name: str = "Campaign") -> None:
        self.campaign = CampaignState.new(players, names, name=name)
        self.campaign.slot = store.new_slot_id(name)
        self.save_campaign()
        self.show(CampaignScreen(self))

    def open_campaign(self, slot: str) -> bool:
        c = store.load_campaign(slot)
        if c is None:
            return False
        self.campaign = c
        self.settings["last_campaign"] = slot
        self.save_settings()
        self.show(CampaignScreen(self))
        return True

    def save_campaign(self) -> None:
        if self.campaign is None:
            return
        store.save_campaign(self.campaign)
        self.settings["last_campaign"] = self.campaign.slot
        self.save_settings()

    def open_hands(self) -> bool:
        """The "Open hands by default (pass and play)" setting, for multiplayer games."""
        return bool(self.settings.get("open_hands", False))

    def start_attempt(self) -> None:
        assert self.campaign is not None
        self.in_campaign = True
        self.game = self.campaign.start_attempt(open_hands=self.open_hands())
        self.undo_stack = []
        self.save_campaign()
        self.autosave()
        screen = GameScreen(self)
        screen.rules_pending = self.rules_card_due()
        self.show(screen)

    def rules_card_due(self) -> bool:
        """The rules card pops up the first time a mission loads, until it is dismissed
        (``RulesOverlay`` records it in ``flags["rules_seen"]``); Settings can turn it off.
        Evergreen attempts show their setup on the Evergreen screen instead."""
        camp = self.campaign
        if camp is None or camp.finished or not bool(self.settings.get("rules_card", True)):
            return False
        return camp.mission not in camp.flags.get("rules_seen", [])

    def start_evergreen_attempt(self) -> None:
        """Pack E: play the drawn Evergreen setup with the finished campaign's party."""
        assert self.campaign is not None
        self.in_campaign = True
        self.game = self.campaign.start_evergreen_attempt(open_hands=self.open_hands())
        self.undo_stack = []
        self.save_campaign()
        self.autosave()
        self.show(GameScreen(self))

    def resume_attempt(self) -> bool:
        if self.campaign is None:
            return False
        try:
            g = store.load_attempt(self.campaign.slot)
        except Exception:   # a save from an older build, or damaged: never a dead end
            g = None
        if g is None:
            self._attempt_unreadable()
            return False
        self.in_campaign = True
        self.game = g
        self.undo_stack = []
        screen = GameScreen(self)
        screen.rules_pending = self.rules_card_due()
        self.show(screen)
        return True

    @ui.in_background
    def _attempt_unreadable(self) -> None:
        """The attempt file cannot be loaded: offer to delete it (no loss is recorded) so the
        campaign can go on."""
        import console
        if self.campaign is None or not store.has_attempt(self.campaign.slot):
            return
        if console.alert("The saved attempt could not be loaded",
                         "It may come from an older version of the app. Delete it and start the mission again? "
                         "No loss is recorded.", "Delete the attempt", "Cancel") == 1:
            store.delete_attempt(self.campaign.slot)
            self.show(CampaignScreen(self))

    def finish_attempt(self) -> dict:
        assert self.campaign is not None and self.game is not None
        res = self.campaign.finish_attempt(self.game)
        self.save_campaign()
        store.delete_attempt(self.campaign.slot)
        return res

    def autosave(self) -> None:
        if self.game is None or self.game.is_over:
            return
        if self.in_campaign and self.campaign is not None:
            store.save_attempt(self.game, self.campaign.slot)
        else:
            store.save_game(self.game, store.AUTOSAVE)

    def lore_entries(self, local: bool) -> List[dict]:
        allv = L.entries(store.lore_overlay_path())
        if local:
            seen = set(self.campaign.lore_seen) if self.campaign else set()
        else:
            seen = set(store.global_lore_seen())
        return [e for e in allv if e["id"] in seen]

    def remember_for_undo(self) -> None:
        if self.game is not None:
            self.undo_stack.append(self.game.to_dict())
            del self.undo_stack[:-30]

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        self.game = Game.from_dict(self.undo_stack.pop())
        self.autosave()
        return True

    def save_settings(self) -> None:
        store.save_settings(self.settings)

    def will_close(self) -> None:
        self.autosave()


# ============================================================================ menu
class MenuScreen(Screen):
    def layout(self) -> None:
        if not hasattr(self, "app"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        app = self.app
        w = self.width
        y = T.TOP_INSET + 24
        self.add_subview(make_label("REGICIDE", (0, y, w, 44), 36, True, T.ACCENT, ui.ALIGN_CENTER))
        y += 46
        self.add_subview(make_label("legacy · personal edition · %s" % VERSION, (0, y, w, 20), 13, False, T.MUTED, ui.ALIGN_CENTER))
        y += 40
        bw, bh, gap = min(300, w - 2 * T.MARGIN), 48, 12
        x = (w - bw) / 2
        items: List = []
        camp = app.campaign
        if camp is not None and store.has_campaign(camp.slot):
            items.append(("Continue: %s" % camp.name, lambda s: app.open_campaign(camp.slot), True))
        items += [
            ("Load game", lambda s: app.show(LoadGameScreen(app)), bool(store.list_campaigns())),
            ("New game", lambda s: app.show(NewGameScreen(app, 1, campaign=True)), True),
            ("Quick play (base Regicide)", lambda s: app.show(QuickPlayScreen(app)), False),
            ("Lore", lambda s: app.show(LoreScreen(app, local=False)), False),
            ("Settings", lambda s: app.show(SettingsScreen(app)), False),
            ("Rules", lambda s: app.show(RulesScreen(app)), False),
            ("Quit", lambda s: app.close(), False),
        ]
        for title, action, primary in items:
            b = make_button(title, action, (x, y, bw, bh), primary)
            if title == "Load game" and not store.list_campaigns():
                set_enabled(b, False)
            self.add_subview(b)
            y += bh + gap


class QuickPlayScreen(Screen):
    """Base Regicide outside the campaign."""

    def layout(self) -> None:
        if not hasattr(self, "app"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        app = self.app
        w = self.width
        m = T.MARGIN
        y = T.TOP_INSET
        self.add_subview(make_button("‹ Menu", lambda s: app.show(MenuScreen(app)), (m, y, 80, 36), False, 14))
        self.add_subview(make_label("Quick play", (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 60
        bw, bh, gap = min(300, w - 2 * m), 48, 12
        x = (w - bw) / 2
        items: List = []
        if store.has_game():
            items.append(("Continue game", self._continue, True))
        items += [
            ("Solo game", lambda s: app.show(NewGameScreen(app, 1)), True),
            ("Pass and play (2–4)", lambda s: app.show(NewGameScreen(app, max(2, app.settings.get("last_players", 2)))), True),
            ("History", lambda s: app.show(HistoryScreen(app)), False),
        ]
        for title, action, primary in items:
            self.add_subview(make_button(title, action, (x, y, bw, bh), primary))
            y += bh + gap

    def _continue(self, sender) -> None:
        if not self.app.resume_game():
            import console
            console.hud_alert("No saved game", "error")
            self.layout()


class LoadGameScreen(Screen):
    def layout(self) -> None:
        if not hasattr(self, "app"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        app = self.app
        w, h = self.width, self.height
        m = T.MARGIN
        y = T.TOP_INSET
        self.add_subview(make_button("‹ Menu", lambda s: app.show(MenuScreen(app)), (m, y, 80, 36), False, 14))
        self.add_subview(make_label("Load game", (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 50
        sv = ui.ScrollView(frame=(m, y, w - 2 * m, h - y - T.BOTTOM_INSET))
        yy = 0
        rows = store.list_campaigns()
        if not rows:
            sv.add_subview(make_label("No saved games yet.", (0, 0, w - 2 * m, 30), 14, False, T.MUTED))
        for r in rows:
            panel = ui.View(frame=(0, yy, w - 2 * m, 92))
            panel.background_color = T.PANEL
            panel.corner_radius = 10
            state = "complete" if r["finished"] else "mission %d%s" % (r["mission"], " · attempt in progress" if r["has_attempt"] else "")
            panel.add_subview(make_label(r["name"], (12, 8, w - 2 * m - 24, 24), 17, True, T.TEXT))
            panel.add_subview(make_label("%d player%s · %s · %s" % (r["players"], "" if r["players"] == 1 else "s", state, r["last_played"]),
                                         (12, 32, w - 2 * m - 24, 20), 12, False, T.MUTED))
            panel.add_subview(make_button("Open", (lambda slot: lambda s: app.open_campaign(slot))(r["slot"]), (12, 54, 110, 32), True, 14))
            panel.add_subview(make_button("Delete", (lambda slot, name: lambda s: self._delete(slot, name))(r["slot"], r["name"]), (w - 2 * m - 12 - 90, 54, 90, 32), False, 14))
            sv.add_subview(panel)
            yy += 100
        sv.content_size = (w - 2 * m, yy + 20)
        self.add_subview(sv)

    @ui.in_background
    def _delete(self, slot: str, name: str) -> None:
        import console
        if console.alert("Delete game?", "'%s' will be deleted. Lore you unlocked stays in the Lore screen." % name, "Delete", "Cancel") == 1:
            store.delete_campaign(slot)
            if self.app.campaign is not None and self.app.campaign.slot == slot:
                self.app.campaign = None
            self.app.show(LoadGameScreen(self.app))


# ============================================================================ new game
class NewGameScreen(Screen):
    def __init__(self, app: "App", players: int, campaign: bool = False, **kw) -> None:
        super().__init__(app, **kw)
        self.players = players
        self.campaign = campaign
        self.game_name_field: Optional[ui.TextField] = None
        self.name_fields: List[ui.TextField] = []

    def layout(self) -> None:
        if not hasattr(self, "name_fields"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        self.name_fields = []
        w = self.width
        m = T.MARGIN
        y = T.TOP_INSET
        back = (lambda s: self.app.show(MenuScreen(self.app))) if self.campaign else (lambda s: self.app.show(QuickPlayScreen(self.app)))
        self.add_subview(make_button("‹ Back", back, (m, y, 80, 36), False, 14))
        self.add_subview(make_label("New game" if self.campaign else "Quick game", (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 56
        if self.campaign:
            self.add_subview(make_label("Game name", (m, y, 120, 36), 15, False, T.MUTED))
            tf = ui.TextField(frame=(m + 120, y, w - 2 * m - 120, 36))
            tf.text = self.game_name_field.text if self.game_name_field is not None else "Campaign %d" % (len(store.list_campaigns()) + 1)
            tf.font = (T.FONT, 16)
            self.game_name_field = tf
            self.add_subview(tf)
            y += 48
        self.add_subview(make_label("Players", (m, y, 120, 32), 16, True))
        seg = ui.SegmentedControl(frame=(m + 120, y, w - 2 * m - 120, 32))
        seg.segments = ["1", "2", "3", "4"]
        seg.selected_index = self.players - 1
        seg.action = self._players_changed
        self.add_subview(seg)
        y += 48
        names = self.app.settings.get("names", ["Player 1", "Player 2", "Player 3", "Player 4"])
        for i in range(self.players):
            self.add_subview(make_label("Name %d" % (i + 1), (m, y, 90, 36), 15, False, T.MUTED))
            tf = ui.TextField(frame=(m + 90, y, w - 2 * m - 90, 36))
            tf.text = names[i] if i < len(names) else "Player %d" % (i + 1)
            tf.font = (T.FONT, 16)
            self.name_fields.append(tf)
            self.add_subview(tf)
            y += 44
        y += 8
        hand = {1: 8, 2: 7, 3: 6, 4: 5}[self.players]
        jesters = {1: "2 Jester powers", 2: "no Jesters", 3: "1 Jester", 4: "2 Jesters"}[self.players]
        self.add_subview(make_label("Hand size %d · %s" % (hand, jesters), (m, y, w - 2 * m, 24), 14, False, T.MUTED))
        y += 34
        if self.players > 1:
            self.add_subview(make_label("Open hands (one person plays every seat)", (m, y, w - 2 * m - 60, 32), 14, False, T.TEXT, lines=2))
            sw = ui.Switch(frame=(w - m - 51, y, 51, 31))
            sw.value = bool(self.app.settings.get("open_hands", False))
            sw.action = self._open_hands
            self.add_subview(sw)
            y += 48
        y += 10
        bw = min(300, w - 2 * m)
        self.add_subview(make_button("Start", self._start, ((w - bw) / 2, y, bw, 52), True, 18))
        y += 70
        if self.campaign:
            note = ("The campaign keeps one party for its 12 missions. The player count can change "
                    "between attempts. Mission rules appear as you reach them.")
        else:
            note = ("Solo: 8-card hand, two Jester powers (discard hand, draw 8), no yielding. "
                    "Gold / Silver / Bronze medal by Jesters used.")
        self.add_subview(make_label(note, (m, y, w - 2 * m, 60), 13, False, T.MUTED, lines=3))

    def _players_changed(self, sender) -> None:
        self.players = sender.selected_index + 1
        self.layout()

    def _open_hands(self, sender) -> None:
        self.app.settings["open_hands"] = bool(sender.value)
        self.app.save_settings()

    def _start(self, sender) -> None:
        names = [tf.text.strip() or "Player %d" % (i + 1) for i, tf in enumerate(self.name_fields)]
        saved = list(self.app.settings.get("names", []))
        while len(saved) < 4:
            saved.append("Player %d" % (len(saved) + 1))
        for i, n in enumerate(names):
            saved[i] = n
        self.app.settings["names"] = saved
        self.app.settings["last_players"] = self.players
        self.app.save_settings()
        if self.campaign:
            gname = (self.game_name_field.text.strip() if self.game_name_field is not None else "") or "Campaign"
            self.app.new_campaign(self.players, names, gname)
            return
        cfg = GameConfig(players=self.players, names=tuple(names),
                         jester_may_choose_self=bool(self.app.settings.get("jester_may_choose_self", True)),
                         open_hands=bool(self.app.settings.get("open_hands", False)) if self.players > 1 else True)
        self.app.start_game(cfg)


# ============================================================================ game
class GameScreen(Screen):
    def __init__(self, app: "App", **kw) -> None:
        super().__init__(app, **kw)
        self.game: Game = app.game  # type: ignore[assignment]
        self.shown_player: Optional[int] = None
        self.team_seat: Optional[int] = None   # mission 6 team damage: whose hand is shown
        self.pile_choice: Optional[int] = None  # mission 9 end of turn: the captured pile to rescue from
        self.overlay: Optional[ui.View] = None
        # what Back returns to from the game menu, the piles, the log or the rules card:
        # the choice box that was up (its picks intact), or the bare table (its selection intact)
        self.return_overlay: Optional[ui.View] = None
        self.rules_pending = False   # show the mission's rules card before play starts
        self.message_text = ""
        self.forecast = ""   # what the selected cards would do, in words (the attack's card)
        self.status = make_label("", (0, 0, 10, 10), 13, False, T.MUTED)
        # a tap on the status line ("Reserve 54 · Discard 17") opens the piles
        self.piles_btn = ui.Button(frame=(0, 0, 10, 10))
        self.piles_btn.title = ""
        self.piles_btn.background_color = None
        self.piles_btn.action = lambda s: self._show_piles()
        self.menu_btn = make_button("Menu", self._menu, (0, 0, 70, 30), False, 14)
        # the enemy large in the middle, its attack on the left and its health on the right
        self.enemy = TableHeader()
        self.enemy.on_attack = self._show_attack
        self.enemy.on_enemy = self._show_enemy
        self.flute_slot: Optional[ui.Button] = None   # the action bar button standing in for the Flute
        self.strip = CardStrip()
        self.zone = CardStrip()
        self.zone.empty_text = ""    # its title says "(empty)"
        self.zone.hidden = True
        self.message = make_label("", (0, 0, 10, 10), 14, False, T.TEXT, ui.ALIGN_CENTER, lines=3)
        self.hand = HandGrid()
        self.hand.on_change = self._selection_changed
        self.left_btn = make_button("Yield", self._left, (0, 0, 10, 10), False)
        self.mid_btn = make_button("Jester", self._mid, (0, 0, 10, 10), False)
        self.right_btn = make_button("Play", self._right, (0, 0, 10, 10), True)
        self.special_btn = make_button("Relics", self._special, (0, 0, 10, 10), False, 13)
        self.special_btn.hidden = True
        self.toast = make_label("", (0, 0, 10, 10), 13, True, T.BG, ui.ALIGN_CENTER)
        self.toast.background_color = T.ACCENT
        self.toast.corner_radius = 8
        self.toast.hidden = True
        for v in (self.status, self.piles_btn, self.menu_btn, self.enemy, self.strip, self.zone, self.message, self.hand,
                  self.left_btn, self.mid_btn, self.right_btn, self.special_btn, self.toast):
            self.add_subview(v)

    # ------------------------------------------------------------------ layout
    def layout(self) -> None:
        if not hasattr(self, "toast"):
            return
        w, h = self.width, self.height
        m = T.MARGIN
        y = T.TOP_INSET
        self.status.frame = (m, y, w - 2 * m - 80, 30)
        self.piles_btn.frame = self.status.frame
        self.menu_btn.frame = (w - m - 70, y, 70, 30)
        y += 34
        # the header grows with the screen (its card keeps a playing card's proportions)
        eh = max(112.0, min(190.0, h * 0.21))
        self.enemy.frame = (m, y, w - 2 * m, eh)
        y += eh + 4
        bar_h = 48
        bar_y = h - T.BOTTOM_INSET - bar_h
        below = self.app.settings.get("played_below", True)
        strip_h = 64
        zone = not self.zone.hidden
        # on a short screen the mission zone and the played cards share a row
        shared = zone and h < 760
        full = w - 2 * m

        def strips(top: float) -> None:
            if shared:
                half = (full - 8) / 2.0
                self.zone.frame = (m, top, half, strip_h)
                self.strip.frame = (m + half + 8, top, half - (90 if not self.special_btn.hidden else 0), strip_h)
            else:
                self.strip.frame = (m, top, full - 90, strip_h)
            self.special_btn.frame = (w - m - 84, top + 14, 84, 36)

        if not below:
            strips(y)
            y += strip_h + 6
        if zone and not shared:
            self.zone.frame = (m, y, full, 64)
            y += 70
        self.message.frame = (m, y, full, 56)
        y += 58
        bottom = bar_y - 8
        if below:
            # the cards played against this enemy, between the hand and the action bar
            bottom -= strip_h + 4
            strips(bottom + 4)
        self.hand.frame = (m, y, full, max(100, bottom - y))
        bw = (w - 2 * m - 16) / 3
        self.left_btn.frame = (m, bar_y, bw, bar_h)
        self.mid_btn.frame = (m + bw + 8, bar_y, bw, bar_h)
        self.right_btn.frame = (m + 2 * (bw + 8), bar_y, bw, bar_h)
        self.toast.frame = (m + 20, bar_y - 40, w - 2 * m - 40, 32)
        if self.overlay is not None:
            self.overlay.frame = (0, 0, w, h)
            if hasattr(self.overlay, "layout"):
                self.overlay.layout()

    def on_show(self) -> None:
        self.refresh(after_action=False)

    # ------------------------------------------------------------------ refresh
    def refresh(self, after_action: bool = True) -> None:
        self.return_overlay = None
        g = self.game = self.app.game  # type: ignore[assignment]
        # (mission 10's face-up enemy deck shows its next enemy in the enemy panel)
        self.status.text = status_text(g, self.status.width)
        self.enemy.game = g
        self.enemy.projection, self.enemy.warn, self.enemy.paying = None, False, None
        self.enemy.refresh()
        self.hand.warned = set()
        self.hand.can_start = lambda c: False
        uses_zone = bool(g.mission_zone) or getattr(g.rules, "uses_mission_zone", False)
        if uses_zone != (not self.zone.hidden):
            self.zone.hidden = not uses_zone
            self.layout()
        # in the order the cards entered play (the clean-up's default order); beside the
        # mission zone on a short screen, a short title
        played = [g.card(c) for p in g.plays for c in p.card_ids]
        title = "Played against this enemy"
        if text_size(title, 0, CardStrip.TITLE_FONT)[0] > self.strip.width - 8:
            title = "Played"
        self.strip.set_cards(played, title)
        self.strip.set_needs_display()
        if uses_zone:
            zone_cards, title = zone_caption(g)
            self.zone.set_cards(zone_cards, title)
            self.zone.set_needs_display()
        if g.is_over:
            self._table_under_box(None if self._hand_hidden() else self.shown_player)
            if self.app.in_campaign:
                if not hasattr(self, "campaign_result"):
                    self.campaign_result = self.app.finish_attempt()
                self._show_overlay(CampaignResultOverlay(self))
            else:
                self._show_overlay(ResultOverlay(self))
            return
        if g.phase == PHASE_CHOOSE_NEXT:
            # the phone may be with any player: no hand under the box when hands are hidden
            self._table_under_box(None if self._hand_hidden() else g.active)
            self._show_overlay(ChooseNextOverlay(self))
            return
        if self.rules_pending:
            self._show_overlay(RulesOverlay(self))
            return
        kind = (g.decision or {}).get("kind") if g.phase == PHASE_DECIDE else None
        if kind == "team_discard":
            self._refresh_team_damage()
            return
        if kind != "pile_rescue":
            self.pile_choice = None
        if kind == "pile_rescue" and self.pile_choice is None:
            # Mission 9's end of turn: pick the pile (or rotate) first, then a hand card.
            seat = g.deciding
            if g.n_players > 1 and self.shown_player != seat and not g.config.open_hands:
                self._table_under_box(None)
                self._show_overlay(HandoverOverlay(self))
                return
            self.shown_player = seat
            self._table_under_box(seat)
            self._show_overlay(PileRescueOverlay(self))
            return
        if kind is not None and kind not in HAND_DECISIONS:
            # A decision of the current player's own with a short list of options: the
            # mage's secret look, the reaver's reveal, which zone card to rescue, the order
            # a mage's leftovers, a reaver's reveals or the played cards after a kill go onto
            # a pile, the card moved to the zone, the Scarlet Whistle's take. In
            # pass-and-play another player may hold the phone (a Kinfolk Flute, Scarlet
            # Whistle or Azure Emblem decision came first): hand it back first.
            seat = g.deciding
            if g.n_players > 1 and self.shown_player != seat and not g.config.open_hands:
                self._table_under_box(None)
                self._show_overlay(HandoverOverlay(self))
                return
            self.shown_player = seat
            self._table_under_box(seat)
            self._show_overlay(PICK_OVERLAYS.get(kind, PickOverlay)(self))
            return
        # The seat whose hand is shown: the attacker, or whoever must decide (Kinfolk
        # Flute, Azure Emblem).
        seat = g.deciding
        needs_handover = (g.n_players > 1 and self.shown_player != seat
                          and (not g.config.open_hands or g.phase == PHASE_DECIDE))
        if needs_handover:
            self._table_under_box(None)
            self._show_overlay(DecisionOverlay(self) if g.phase == PHASE_DECIDE else HandoverOverlay(self))
            return
        self._hide_overlay()
        self.shown_player = seat
        locked = dict((c.id, "stuck") for c in g.hand(seat) if g.hand_locked(c.id))
        if g.phase == PHASE_DECIDE:
            self.hand.badges = locked
            self.hand.set_cards(g.hand(seat), keep_selection=False)
        else:
            flute = list(g.extra.get("flute", []))
            self.hand.badges = dict((cid, "flute") for cid in flute)
            self.hand.badges.update(locked)
            self.hand.set_cards(g.hand() + [g.card(c) for c in flute], keep_selection=False)
        self._update_controls()

    def reveal_hand(self) -> None:
        self.shown_player = self.game.deciding
        self.refresh(after_action=False)

    def _table_under_box(self, seat: Optional[int]) -> None:
        """Before a box covers the table, make what lies under it current and public (it shows
        when the player holds "Hold to view game"): ``seat``'s hand as it is now, or no hand
        while the phone may be passing to another player; the last public message instead
        of what a selection would do (a pass-and-play player's selection names cards they
        kept); the action buttons off (the box decides)."""
        g = self.game
        self.hand.badges = {}
        self.hand.set_cards(g.hand(seat) if seat is not None else [], keep_selection=False)
        self.message.text = self.message_text
        for b, primary in ((self.left_btn, False), (self.mid_btn, False), (self.right_btn, True)):
            set_enabled(b, False, primary)
        self.special_btn.hidden = True
        self.flute_slot = None
        self.forecast = ""
        self.hand.warned = set()
        self.enemy.projection, self.enemy.warn, self.enemy.paying = None, False, None
        self.enemy.refresh()
        self.toast.hidden = True      # a Hint names a card of the hand that was shown

    def _hand_hidden(self) -> bool:
        """Pass-and-play with hidden hands: a hand is shown only to the player holding it."""
        g = self.game
        return g.n_players > 1 and not g.config.open_hands

    def _refresh_team_damage(self) -> None:
        """Mission 6: Myla's team damage is discarded one card at a time by any player.
        Solo, the hand is shown at once; in pass-and-play a seat picker names who discards
        next, then that player's hand is shown with one card selectable."""
        g = self.game
        seat = 0 if g.n_players == 1 else self.team_seat
        if seat is None or not g.players[seat].hand:
            self.team_seat = None
            if self._hand_hidden():
                # whoever is picked next, even the same player, takes the phone through a
                # handover; until then no hand counts as the holder's (the piles viewer)
                self.shown_player = None
            self._table_under_box(None)
            self._show_overlay(TeamDamageOverlay(self))
            return
        if g.n_players > 1 and not g.config.open_hands and self.shown_player != seat:
            # pass the phone first: nobody else sees that hand
            self._table_under_box(None)
            self._show_overlay(HandoverOverlay(self, seat=seat))
            return
        self._hide_overlay()
        self.shown_player = seat
        self.hand.badges = {}
        self.hand.set_cards(g.hand(seat), keep_selection=False)
        self.special_btn.hidden = True
        self._update_controls()

    def pick_team_seat(self, seat: Optional[int]) -> None:
        self.team_seat = seat
        self.refresh(after_action=False)

    def reveal_seat(self, seat: int) -> None:
        """The team damage's chosen player holds the phone: show their hand."""
        self.shown_player = seat
        self.team_seat = seat
        self.refresh(after_action=False)

    def pick_pile(self, pile: Optional[int]) -> None:
        """Mission 9: the captured pile to rescue from (None: back to the pile choice)."""
        self.pile_choice = pile
        self.refresh(after_action=False)

    def _update_controls(self) -> None:
        g = self.game
        sel = list(self.hand.selected)
        name = g.active_player.name
        self.forecast = ""
        self.flute_slot = None
        had_special = not self.special_btn.hidden
        self.special_btn.hidden = True
        self.hand.can_start = lambda c: False
        self.hand.warned = set()
        projection: Optional[dict] = None
        warn, paying = False, None
        if g.phase == PHASE_PLAY:
            # Greyed: a card that no legal play has together with the cards selected so far.
            # A card the solo Kinfolk Flute stores only joins a kinfolk set already begun.
            # A greyed card that is a legal play on its own starts a new selection.
            hand_ids = set(g.active_player.hand)
            plays = [set(p) for p in g.legal_plays()]
            chosen = set(sel)
            fits = [p for p in plays if chosen <= p]
            self.hand.selectable = lambda c: c.id in chosen or (
                (c.id in hand_ids or bool(chosen)) and any(c.id in p for p in fits))
            self.hand.can_start = lambda c: c.id in hand_ids and set([c.id]) in plays
            self.left_btn.title = "Yield"
            set_enabled(self.left_btn, g.can_yield(), False)
            if g.n_players == 1:
                narrow = self.width < 385
                attack = g.rules.solo_jester_mode(g) == "attack"
                self.mid_btn.title = ("Jester" if narrow else "Jester attack") if attack else ("Jester" if narrow else "Jester power")
                self.mid_btn.hidden = False
                set_enabled(self.mid_btn, g.can_use_solo_jester(), False)
            else:
                self.mid_btn.title = "Hint"
                self.mid_btn.hidden = not self.app.settings.get("show_hints", True)
                set_enabled(self.mid_btn, True, False)
            self.right_btn.title = "Play"
            if g.extra.get("jester_attack"):
                self.message_text = "%s claimed the Jester: this attack ignores immunity." % name
            if sel:
                ok, info = g.check_play(sel)
                pv = g.preview_play(sel) if ok else {}
                if pv.get("ok"):
                    # what the play would do shows on the header (and in full on a tap on the
                    # attack); a class power the enemy blocks puts a red edge on the card
                    # and on the enemy
                    projection = pv
                    self.forecast = describe_preview(g, pv)
                    blocked = [suit for suit, ev in pv["powers"].items() if ev.get("immune")]
                    self.hand.warned = set(c for c in sel if any(s_ in g.card(c).suits for s_ in blocked))
                    warn = bool(self.hand.warned)
                    self.message.text = ""
                else:
                    self.message.text = pv.get("reason") or info
                set_enabled(self.right_btn, bool(pv.get("ok")))
            else:
                self.message.text = self.message_text or ("%s: tap cards to play, then Play." % name)
                set_enabled(self.right_btn, False)
            specials = g.rules.special_actions(g)
            if specials and not g.can_yield():
                # the solo Kinfolk Flute takes Yield's place (a solo player never yields)
                self.flute_slot = self.left_btn
                self.left_btn.title = special_title(specials)
                set_enabled(self.left_btn, True, False)
            elif specials:
                self.special_btn.hidden = False
                self.special_btn.title = special_title(specials)
            self.hand.refresh_dim()
        elif g.phase == PHASE_SUFFER:
            need = g.pending_damage
            hand_ids = set(g.active_player.hand)
            if any(c not in hand_ids for c in sel):
                self.hand.set_selection([c for c in sel if c in hand_ids])
                return
            total = sum(g.card(c).defence_value for c in sel)
            # Legacy (p.18): one card at a time, in the order tapped; no card may follow once
            # the damage is covered (the last one ends on top of the discard pile)
            one_by_one = g.rules.sequential_discard(g)
            covered = one_by_one and total >= need
            chosen = set(sel)
            # only hand cards pay damage (not the solo Kinfolk Flute's stored cards); greyed
            # once a one-at-a-time discard is covered
            self.hand.selectable = lambda c: c.id in chosen or (
                c.id in hand_ids and not g.hand_locked(c.id) and not covered)
            feign = g.feign_death_available()
            self.left_btn.title = "Feign death" if feign else "Suggest"
            set_enabled(self.left_btn, True, False)
            self.mid_btn.title = "Jester" if self.width < 385 else "Jester power"
            self.mid_btn.hidden = not (g.n_players == 1 and g.rules.solo_jester_mode(g) == "refresh")
            set_enabled(self.mid_btn, g.can_use_solo_jester(), False)
            self.right_btn.title = "Discard %d/%d" % (total, need) if need > 0 else "Discard"
            whole = set(sel) == hand_ids and bool(sel)
            in_order = not one_by_one or sum(g.card(c).defence_value for c in sel[:-1]) < need
            set_enabled(self.right_btn, (total >= need and need > 0 and in_order) or (feign and whole))
            paying = (total, need)
            self.message.text = "" if sel else "%s suffers %d damage: select cards worth at least %d." % (name, need, need)
            # one hint at most (the message has three lines)
            if one_by_one and total >= need and not in_order and not (feign and whole):
                self.message.text = ("In this order the damage is covered before %s: tap the cards in the order they "
                                     "are discarded, without a card too many." % g.card(sel[-1]).label())
            elif g.hand_defence_value() < need and g.can_use_solo_jester():
                self.message.text += " Your hand is short: use the Jester power."
            elif feign:
                self.message.text += " At the hand limit you may feign death: discard everything."
            elif sel:
                pass
            elif one_by_one:
                self.message.text += " One at a time: the last card ends on top of the discard pile."
            elif any(g.hand_locked(c) for c in g.active_player.hand):
                self.message.text += " Pilgrims never leave your hand."
            self.message.text = self.message.text.strip()
            specials = g.rules.special_actions(g)
            if specials and self.mid_btn.hidden:
                # the solo Kinfolk Flute in the Jester's place (the Jester has no power here)
                self.flute_slot = self.mid_btn
                self.mid_btn.hidden = False
                self.mid_btn.title = special_title(specials)
                set_enabled(self.mid_btn, True, False)
            elif specials:
                self.special_btn.hidden = False
                self.special_btn.title = special_title(specials)
            self.hand.refresh_dim()
        elif g.phase == PHASE_DECIDE and (g.decision or {}).get("kind") == "chanter_discard":
            # Chanter: the shown hand belongs to a player over the limit, who discards down to it.
            d = g.decision or {}
            acts = [a for a in g.legal_actions() if a["type"] == "chanter_discard"]
            needs = int(acts[0]["needs"]) if acts else 0
            allowed = set(acts[0]["pick_from"]) if acts else set()
            self.hand.selectable = lambda c: c.id in allowed
            self.hand.refresh_dim()
            self.left_btn.title = "Suggest"
            set_enabled(self.left_btn, True, False)
            self.mid_btn.hidden = True
            self.right_btn.title = "Discard %d" % needs
            set_enabled(self.right_btn, len(sel) == needs and needs > 0)
            who = g.players[g.deciding].name
            self.message.text = "Chanter: %s drew to %d cards and must discard down to %d. Select %d card%s and tap Discard (%d selected)." % (
                who, len(g.players[g.deciding].hand), g.config.max_hand, needs, "" if needs == 1 else "s", len(sel))
        elif g.phase == PHASE_DECIDE and (g.decision or {}).get("kind") in HAND_PICKS:
            # One hand card leaves: into the mission zone (mission 10's bard, bane 12), the
            # discard or banished pile (mission 11's beasts, bane 21, bane 23's choice).
            if len(sel) > 1:
                self.hand.set_selection(sel[-1:])
                return
            kind = str((g.decision or {}).get("kind"))
            spec = HAND_PICKS[kind]
            acts = g.legal_actions()
            allowed = set(a["card"] for a in acts if a.get("card"))
            skip = [a for a in acts if a.get("skip")]
            self.hand.selectable = lambda c: c.id in allowed
            self.hand.refresh_dim()
            self.left_btn.title = spec.get("skip", "No pass")
            set_enabled(self.left_btn, bool(skip), False)
            self.mid_btn.hidden = True
            self.right_btn.title = spec["verb"]
            set_enabled(self.right_btn, len(sel) == 1 and sel[0] in allowed)
            who = g.players[g.deciding].name
            if sel and sel[0] in allowed:
                self.message.text = spec["chosen"] % {"who": who, "card": g.card(sel[0]).label()}
            else:
                self.message.text = spec["text"] % {"who": who}
        elif g.phase == PHASE_DECIDE and (g.decision or {}).get("kind") == "mother_banish":
            # Evergreen Mother, 2+ players: another player must banish one card from hand.
            if len(sel) > 1:
                self.hand.set_selection(sel[-1:])
                return
            allowed = set(a["card"] for a in g.legal_actions() if a["type"] == "mother_banish")
            self.hand.selectable = lambda c: c.id in allowed
            self.hand.refresh_dim()
            self.left_btn.title = "No pass"
            set_enabled(self.left_btn, False, False)
            self.mid_btn.hidden = True
            self.right_btn.title = "Banish"
            set_enabled(self.right_btn, len(sel) == 1 and sel[0] in allowed)
            d = g.decision or {}
            who = g.players[g.deciding].name
            corrupt = g.card(str(d.get("card"))).label() if d.get("card") in g.cards else "a corrupted card"
            if sel:
                self.message.text = "%s banishes %s from hand (Evergreen Mother, for %s)." % (who, g.card(sel[0]).label(), corrupt)
            else:
                self.message.text = ("Evergreen Mother: %s entered play, so %s must banish one card from hand instead of "
                                     "the reserve. Select it and tap Banish." % (corrupt, who))
        elif g.phase == PHASE_DECIDE and (g.decision or {}).get("kind") == "pile_rescue":
            # Mission 9: the pile is chosen; now the hand card to banish for the rescue.
            if len(sel) > 1:
                self.hand.set_selection(sel[-1:])
                return
            k = int(self.pile_choice or 0)
            allowed = set(a["card"] for a in g.legal_actions() if a["type"] == "pile_rescue" and int(a["pile"]) == k)
            self.hand.selectable = lambda c: c.id in allowed
            self.hand.refresh_dim()
            self.left_btn.title = "Back"
            set_enabled(self.left_btn, True, False)
            self.mid_btn.hidden = True
            self.right_btn.title = "Banish"
            set_enabled(self.right_btn, len(sel) == 1 and sel[0] in allowed)
            piles = g.extra.get("captured", [])
            top = g.card(piles[k][0]).label() if k < len(piles) and piles[k] else "?"
            if sel:
                self.message.text = "%s banishes %s: %s is rescued from pile %d to the discard pile." % (
                    name, g.card(sel[0]).label(), top, k + 1)
            else:
                self.message.text = "Rescue %s from captured pile %d: select the card to banish from hand and tap Banish." % (top, k + 1)
        elif g.phase == PHASE_DECIDE and (g.decision or {}).get("kind") == "team_discard":
            # Mission 6: the shown hand belongs to whoever discards next for Myla's team damage.
            if len(sel) > 1:
                self.hand.set_selection(sel[-1:])
                return
            self.hand.selectable = lambda c: True
            self.hand.refresh_dim()
            d = g.decision or {}
            remaining = int(d.get("damage", 0)) - int(d.get("paid", 0))
            seat = 0 if g.n_players == 1 else self.team_seat
            who = g.players[seat].name if seat is not None else name
            self.left_btn.title = "Players" if g.n_players > 1 else "Suggest"
            set_enabled(self.left_btn, True, False)
            self.mid_btn.hidden = True
            self.right_btn.title = "Discard"
            set_enabled(self.right_btn, len(sel) == 1)
            self.message.text = "Team damage: %d to go. %s: select one card and tap Discard." % (remaining, who)
            if sel:
                worth = g.card(sel[0]).defence_value
                self.message.text = "Team damage: %d to go. %s discards %s (worth %d)%s." % (
                    remaining, who, g.card(sel[0]).label(), worth, ", enough" if worth >= remaining else "")
        elif g.phase == PHASE_DECIDE and (g.decision or {}).get("kind") == "whistle_add":
            # Scarlet Whistle, 2+ players: the shown hand belongs to another player, who may
            # add one card (not a Jester) to the attacker's solitary companion or beast.
            if len(sel) > 1:
                self.hand.set_selection(sel[-1:])
                return
            adds = set(a["card"] for a in g.legal_actions() if a["type"] == "whistle_add")
            self.hand.selectable = lambda c: c.id in adds
            self.hand.refresh_dim()
            self.left_btn.title = "Pass"
            set_enabled(self.left_btn, True, False)
            self.mid_btn.hidden = True
            self.right_btn.title = "Add"
            set_enabled(self.right_btn, len(sel) == 1 and sel[0] in adds)
            d = g.decision or {}
            play = g.plays[int(d.get("play_index", len(g.plays) - 1))]
            attacker = g.players[play.player].name
            attack = " + ".join(g.card(c).label() for c in play.card_ids)
            who = g.players[g.deciding].name
            if sel and sel[0] in adds:
                pv = g.preview_decision({"type": "whistle_add", "card": sel[0]})
                projection = pv if pv.get("ok") else None
                self.message.text = "%s adds %s (attack %d): %s" % (
                    who, g.card(sel[0]).label(), pv.get("attack", 0), describe_preview(g, pv))
            else:
                self.message.text = ("%s: add one card to %s's %s attack (Scarlet Whistle)? Any card but a Jester. "
                                     "Select it and tap Add, or Pass." % (who, attacker, attack))
        elif g.phase == PHASE_DECIDE and (g.decision or {}).get("kind") == "emblem_place":
            # Azure Emblem, 2+ players: the shown hand belongs to another player, who may
            # place one card face down on top of the reserve before the attacker's mage looks.
            if len(sel) > 1:
                self.hand.set_selection(sel[-1:])   # re-enters here with one card selected
                return
            places = set(a["card"] for a in g.legal_actions() if a["type"] == "emblem_place")
            self.hand.selectable = lambda c: c.id in places   # a locked pilgrim never leaves the hand
            self.hand.refresh_dim()
            self.left_btn.title = "Pass"
            set_enabled(self.left_btn, True, False)
            self.mid_btn.hidden = True
            self.right_btn.title = "Place"
            set_enabled(self.right_btn, len(sel) == 1 and sel[0] in places)
            d = g.decision or {}
            play = g.plays[int(d.get("play_index", len(g.plays) - 1))]
            attacker = g.players[play.player].name
            attack = " + ".join(g.card(c).label() for c in play.card_ids)
            who = g.players[g.deciding].name
            if sel:
                self.message.text = "%s places %s face down on top of the reserve deck: %s's mage reveals it first." % (
                    who, g.card(sel[0]).label(), attacker)
            else:
                self.message.text = ("%s: place one card on the reserve deck for %s's %s attack (Azure Emblem)? "
                                     "Select a card and tap Place, or Pass." % (who, attacker, attack))
        elif g.phase == PHASE_DECIDE:
            # Kinfolk Flute: the shown hand belongs to the deciding player; only cards that
            # keep the attack a valid kinfolk attack may be selected.
            acts = g.legal_actions()
            adds = [a for a in acts if a["type"] == "flute_add"]
            eligible = set(cid for a in adds for cid in a["card_ids"])
            self.hand.selectable = lambda c: c.id in eligible
            self.hand.refresh_dim()
            self.left_btn.title = "Pass"
            set_enabled(self.left_btn, True, False)
            self.mid_btn.hidden = True
            self.right_btn.title = "Add"
            legal = bool(sel) and any(sorted(a["card_ids"]) == sorted(sel) for a in adds)
            set_enabled(self.right_btn, legal)
            d = g.decision or {}
            play = g.plays[int(d.get("play_index", len(g.plays) - 1))]
            attacker = g.players[play.player].name
            attack = " + ".join(g.card(c).label() for c in play.card_ids)
            who = g.players[g.deciding].name
            if legal:
                pv = g.preview_decision({"type": "flute_add", "card_ids": sel})
                projection = pv if pv.get("ok") else None
                self.message.text = "%s adds %s (attack %d): %s" % (
                    who, " + ".join(g.card(c).label() for c in sel), pv.get("attack", 0), describe_preview(g, pv))
            elif sel:
                self.message.text = "Only %ss may join, and the attack must stay at 10 or less." % d.get("strength")
            else:
                self.message.text = "%s: add to %s's %s attack? Select %ss (total at most 10) and tap Add, or Pass." % (
                    who, attacker, attack, d.get("strength"))
        for b in (self.left_btn, self.mid_btn, self.right_btn):
            fit_title(b, 16)     # the action bar's size, smaller only for a long title
        self.message.set_needs_display()
        self.enemy.show(projection, warn, paying)
        if had_special == self.special_btn.hidden:
            self.layout()     # the played cards make room for the button beside them, or take it back

    def _selection_changed(self) -> None:
        self.message_text = ""
        self._update_controls()

    # ------------------------------------------------------------------ actions
    def _act(self, fn: Callable[[], None]) -> None:
        g = self.game
        self.app.remember_for_undo()
        try:
            fn()
        except IllegalAction as e:
            self.app.undo_stack.pop()
            self.show_toast(str(e))
            return
        self.message_text = describe_events(g)
        if g.is_over:
            if self.app.in_campaign:
                self.campaign_result = self.app.finish_attempt()
            else:
                store.record_result(g)
                store.delete_game()
        else:
            self.app.autosave()
        self.refresh()

    def _left(self, sender) -> None:
        g = self.game
        if self.flute_slot is self.left_btn:
            self._special(sender)
        elif g.phase == PHASE_PLAY:
            self._act(g.yield_turn)
        elif g.phase == PHASE_SUFFER:
            if g.feign_death_available():
                self.hand.set_selection(list(g.active_player.hand))
            else:
                self.hand.set_selection(min_waste_discard(g))
        elif g.phase == PHASE_DECIDE:
            kind = (g.decision or {}).get("kind")
            if kind == "emblem_place":
                self._act(lambda: g.decide({"type": "emblem_pass"}))
            elif kind == "whistle_add":
                self._act(lambda: g.decide({"type": "whistle_pass"}))
            elif kind == "team_discard":
                if g.n_players > 1:
                    self.team_seat = None
                    self.refresh(after_action=False)
                else:
                    act = team_discard_choice(g, g.legal_actions())
                    self.hand.set_selection([act["card"]])
            elif kind == "chanter_discard":
                act = simple_decision(g)
                if act is not None:
                    self.hand.set_selection(list(act.get("cards", [])))
            elif kind == "pile_rescue":
                self.pick_pile(None)
            elif kind == "mother_banish":
                pass
            elif kind in HAND_PICKS:
                skip = [a for a in g.legal_actions() if a.get("skip")]
                if skip:
                    self._act(lambda: g.decide(skip[0]))
            else:
                self._act(g.flute_pass)

    def _special(self, sender) -> None:
        self._show_overlay(SpecialOverlay(self))

    def _mid(self, sender) -> None:
        g = self.game
        if self.flute_slot is self.mid_btn:
            self._special(sender)
        elif g.n_players == 1 and g.rules.solo_jester_mode(g) == "attack":
            self._table_under_box(g.active)
            self._show_overlay(ClassChoiceOverlay(self))
        elif g.n_players == 1 or g.phase == PHASE_SUFFER:
            self._act(g.use_solo_jester)
        else:
            act = greedy_policy(g)
            if act["type"] == "play":
                self.hand.set_selection(act["cards"])
                self.show_toast("Hint: " + " + ".join(g.card(c).label() for c in act["cards"]))
            else:
                self.show_toast("Hint: " + act["type"])

    def _right(self, sender) -> None:
        g = self.game
        sel = list(self.hand.selected)
        if g.phase == PHASE_PLAY:
            self._act(lambda: g.play(sel))
        elif g.phase == PHASE_SUFFER:
            self._act(lambda: g.suffer(sel))
        elif g.phase == PHASE_DECIDE:
            kind = (g.decision or {}).get("kind")
            if kind == "emblem_place":
                self._act(lambda: g.decide({"type": "emblem_place", "card": sel[0]}))
            elif kind == "whistle_add":
                self._act(lambda: g.decide({"type": "whistle_add", "card": sel[0]}))
            elif kind == "team_discard":
                seat = 0 if g.n_players == 1 else self.team_seat
                self.team_seat = None   # the next card may come from any player
                self._act(lambda: g.decide({"type": "team_discard", "player": seat, "card": sel[0]}))
            elif kind == "chanter_discard":
                self._act(lambda: g.decide({"type": "chanter_discard", "player": g.deciding, "cards": sel}))
            elif kind == "mother_banish":
                self._act(lambda: g.decide({"type": "mother_banish", "card": sel[0]}))
            elif kind == "pile_rescue":
                k = self.pile_choice
                self.pile_choice = None
                self._act(lambda: g.decide({"type": "pile_rescue", "pile": k, "card": sel[0]}))
            elif kind in HAND_PICKS:
                self._act(lambda: g.decide({"type": kind, "card": sel[0]}))
            else:
                self._act(lambda: g.flute_add(sel))

    def choose_next(self, player: int) -> None:
        g = self.game
        self._act(lambda: g.choose_next(player))

    def decide(self, action: dict) -> None:
        g = self.game
        self._act(lambda: g.decide(action))

    def _menu(self, sender) -> None:
        self._remember_place()
        self._show_overlay(GameMenuOverlay(self))

    def _show_piles(self, pile: Optional[str] = None) -> None:
        """The piles viewer, on the discard pile (the reserve while nothing is discarded)."""
        self._remember_place()
        self._show_overlay(PilesOverlay(self, pile or ("discard" if self.game.discard else "reserve")))

    def _show_attack(self) -> None:
        """The attack's card (a tap on the attack number): the enemy's attack beside the shield."""
        g = self.game
        if g.enemy is None or self.overlay is not None:
            return
        sel = list(self.hand.selected)
        pv = self.enemy.projection
        popup = CardPopup("Attack", "", [("Close", lambda s: popup.close(), False)], dismissable=True,
                          make_face=lambda w, h: attack_face(g, sel, pv, self.forecast, w, h))
        show_card_popup(self, popup)

    def _show_enemy(self) -> None:
        """The enemy's card (a tap on the enemy or its health): health, immunity, the castle."""
        g = self.game
        if g.enemy is None or self.overlay is not None:
            return
        from .widgets import card_color
        card = g.card(g.enemy.card_id)
        col = card_color(card)
        sel = " + ".join(g.card(c).label() for c in self.hand.selected)
        popup = CardPopup(g.enemy.name, enemy_text(g, self.forecast, sel), [("Close", lambda s: popup.close(), False)],
                          icon=[(card.rank, col)], edge=col, dismissable=True)
        show_card_popup(self, popup)

    def _remember_place(self) -> None:
        """Before a menu or a viewer opens over the table or a choice box, remember where Back
        goes (a menu opened from a viewer keeps the place remembered first)."""
        if not isinstance(self.overlay, (GameMenuOverlay, PilesOverlay, LogOverlay, RulesOverlay)):
            self.return_overlay = self.overlay

    def _back_to_game(self) -> None:
        """Close a menu or viewer: show the choice box that was up again (the same one, picks
        and all) or the bare table, untouched (the hand keeps its selection and tap order).
        Nothing in the game changed while it was open, so nothing is rebuilt."""
        prev, self.return_overlay = self.return_overlay, None
        if prev is not None and prev is not self.overlay:
            self._show_overlay(prev)
        else:
            self._hide_overlay()

    # ------------------------------------------------------------------ overlays
    def _show_overlay(self, v: ui.View) -> None:
        self._hide_overlay()
        self.overlay = v
        v.frame = (0, 0, self.width, self.height)
        self.add_subview(v)
        if hasattr(v, "layout"):
            v.layout()

    def _hide_overlay(self) -> None:
        if self.overlay is not None:
            self.remove_subview(self.overlay)
            self.overlay = None

    def show_toast(self, text: str) -> None:
        self.toast.text = text
        self.toast.hidden = False
        self.toast.bring_to_front()
        ui.delay(self._hide_toast, 2.0)

    def _hide_toast(self) -> None:
        self.toast.hidden = True


class Overlay(ui.View):
    """Semi-transparent full-screen panel with a centred card. A choice box (``peekable``)
    also offers "Hold to view game": while it is held the box fades away and the table
    shows, and letting go brings it back (``PeekButton``); it sits beside the box's "Game
    menu" button when there is one."""

    peekable = True

    def __init__(self, screen: GameScreen, **kw) -> None:
        super().__init__(**kw)
        self.screen = screen
        self.background_color = (0, 0, 0, 0.72)
        self.panel = ui.View()
        self.panel.background_color = T.PANEL
        self.panel.corner_radius = 16
        self.peek_btn = None
        self.peeking = False
        self._peek_saved: tuple = ()
        self.add_subview(self.panel)

    def _add_peek(self, pw: float, y: float) -> float:
        """Put the "Hold to view game" button in the panel: beside a closing "Game menu"
        button, or as a row of its own below ``y``. Returns the panel's new bottom."""
        self.peeking = False
        self.peek_btn = None
        if not self.peekable:
            return y
        from .widgets import PeekButton
        last = self.panel.subviews[-1] if self.panel.subviews else None
        if isinstance(last, ui.Button) and last.title == "Game menu":
            x, ly, w, h = last.frame
            half = (w - 8) / 2.0
            last.frame = (x, ly, half, h)
            fit_title(last)
            self.peek_btn = PeekButton(self._peek, frame=(x + half + 8, ly, half, h))
        else:
            self.peek_btn = PeekButton(self._peek, frame=(20, y, pw - 40, 36))
            y += 36 + 12
        self.panel.add_subview(self.peek_btn)
        return y

    def _peek(self, on: bool) -> None:
        """Fade the box away (all but the held button) so the table shows, or bring it back."""
        if on == self.peeking:
            return
        self.peeking = on
        if on:
            hidden = [v for v in list(self.panel.subviews) + list(self.subviews)
                      if v is not self.panel and v is not self.peek_btn and not v.hidden]
            self._peek_saved = (self.background_color, self.panel.background_color, hidden)
            for v in hidden:
                v.hidden = True
            self.background_color = (0, 0, 0, 0.0)
            self.panel.background_color = None
        elif self._peek_saved:
            bg, panel_bg, hidden = self._peek_saved
            self.background_color = bg
            self.panel.background_color = panel_bg
            for v in hidden:
                v.hidden = False
            self._peek_saved = ()

    def touch_ended(self, touch) -> None:
        # a second finger on the screen while the button is held does not end the hold; a
        # hold the phone lost (a notification) ends with a tap on the button, which still
        # shows "Release to return"
        if self.peeking and (self.peek_btn is None or not self.peek_btn.held):
            self._peek(False)

    def build(self) -> List[ui.View]:
        return []

    def text_width(self) -> float:
        """The width of the panel's content (labels, buttons)."""
        return min(340, self.width - 2 * T.MARGIN) - 40

    def text(self, text: str, size: int = 13, bold: bool = False, color: str = T.TEXT, align=None,
             min_height: float = 0) -> ui.Label:
        """An instruction label as tall as its text: the panel grows with it."""
        return fit_label(text, self.text_width(), size, bold, color, ui.ALIGN_CENTER if align is None else align,
                         min_height)

    def layout(self) -> None:
        if not hasattr(self, "panel") or not hasattr(self, "screen"):
            return
        self._unpeek_for_layout()
        for v in list(self.panel.subviews):
            self.panel.remove_subview(v)
        pw = min(340, self.width - 2 * T.MARGIN)
        items = self.build()
        y = 20
        for v in items:
            v.frame = (20, y, pw - 40, v.height)
            if isinstance(v, ui.Button):
                fit_title(v)
            self.panel.add_subview(v)
            y += v.height + 12
        y = self._add_peek(pw, y)
        ph = y + 8
        self.panel.frame = ((self.width - pw) / 2, max(T.TOP_INSET, (self.height - ph) / 2), pw, ph)

    def _unpeek_for_layout(self) -> None:
        """A rebuild while the box is away brings it back first (the colours are restored)."""
        if self.peeking:
            self._peek(False)


class HandoverOverlay(Overlay):
    """The "Pass the phone to X" screen: the deciding player's hand (or ``seat``'s, for the
    team damage seat picker) stays hidden until that player taps."""

    peekable = False   # not a choice: it closes with its own button

    def __init__(self, screen: "GameScreen", seat: Optional[int] = None, **kw) -> None:
        super().__init__(screen, **kw)
        self.seat = seat

    def build(self) -> List[ui.View]:
        g = self.screen.game
        fixed = getattr(self, "seat", None)
        seat = g.deciding if fixed is None else int(fixed)
        name = g.players[seat].name
        reveal = (lambda s: self.screen.reveal_hand()) if fixed is None else (lambda s: self.screen.reveal_seat(seat))
        items: List[ui.View] = [
            make_label("Pass the phone to", (0, 0, 10, 24), 15, False, T.MUTED, ui.ALIGN_CENTER),
            make_label(name, (0, 0, 10, 40), 28, True, T.ACCENT, ui.ALIGN_CENTER),
            self.text("%s's hand stays hidden until you tap." % name, 14),
            make_button("Show my hand", reveal, (0, 0, 10, 50)),
        ]
        if fixed is not None:
            items.append(make_button("Back", lambda s: self.screen.pick_team_seat(None), (0, 0, 10, 40), False, 14))
        return items


class DecisionOverlay(Overlay):
    """Another player must decide about the attack on the table (Kinfolk Flute: add to it;
    Azure Emblem: place a card on the reserve before the mage looks). Names the deciding
    player and the attack, then reveals that player's hand on request."""

    def build(self) -> List[ui.View]:
        g = self.screen.game
        d = g.decision or {}
        who = g.players[g.deciding].name
        play = g.plays[int(d.get("play_index", len(g.plays) - 1))] if g.plays else None
        attacker = g.players[play.player].name if play else g.active_player.name
        attack = " + ".join(g.card(c).label() for c in play.card_ids) if play else ""
        items: List[ui.View] = []
        if not g.config.open_hands:
            items.append(make_label("Pass the phone to", (0, 0, 10, 24), 15, False, T.MUTED, ui.ALIGN_CENTER))
        items.append(make_label(who, (0, 0, 10, 40), 28, True, T.ACCENT, ui.ALIGN_CENTER))
        if d.get("kind") == "chanter_discard":
            needs = int(((g.rules.decision_actions(g) or [{}])[0]).get("needs", 0))
            items.append(self.text("%s: discard down to %d cards" % (who, g.config.max_hand), 16, bold=True))
            items.append(self.text("Chanter: everyone drew cards ignoring the hand limit. You hold %d and must discard %d." % (
                len(g.players[g.deciding].hand), needs), 13))
        elif d.get("kind") == "mother_banish":
            corrupt = g.card(str(d.get("card"))).label() if d.get("card") in g.cards else "a corrupted card"
            items.append(self.text("%s: banish a card from hand" % who, 16, bold=True))
            items.append(self.text("Evergreen Mother: %s played %s, a corrupted card. Instead of the top of the reserve, "
                                   "you must banish one card from your hand." % (attacker, corrupt), 13))
        elif d.get("kind") == "emblem_place":
            items.append(self.text("%s: place a card for %s's %s attack?" % (who, attacker, attack), 16, bold=True))
            items.append(self.text("Azure Emblem: before the mage looks at the reserve deck you may place one card "
                                   "from your hand face down on top of it, or pass.", 13))
        elif d.get("kind") == "whistle_add":
            items.append(self.text("%s: add to %s's %s attack?" % (who, attacker, attack), 16, bold=True))
            items.append(self.text("Scarlet Whistle: the attack is a solitary companion or beast. You may add any one "
                                   "card from your hand except a Jester, or pass.", 13))
        elif d.get("kind") in HAND_PICKS:
            spec = HAND_PICKS[str(d.get("kind"))]
            items.append(self.text(spec["title"], 16, bold=True))
            items.append(self.text(spec["text"] % {"who": who}, 13))
        else:
            items.append(self.text("%s: add to %s's %s attack?" % (who, attacker, attack), 16, bold=True))
            items.append(self.text("Kinfolk Flute: you may add %ss from your hand as long as the whole attack stays "
                                   "at %d or less, or pass." % (d.get("strength"), g.rules.kinfolk_limit(g)), 13))
        items.append(make_button("Show my hand", lambda s: self.screen.reveal_hand(), (0, 0, 10, 50)))
        return items


class PickOverlay(Overlay):
    """A decision for the current player with a short list of options (one button each),
    e.g. mission 3's exact kill: which mission zone card goes to the discard pile. Many
    options go in two columns with short titles; subclasses add a card strip (the mage's
    and the reaver's revealed cards) or a number grid (how many the reaver reveals)."""

    TEXTS = {
        "zone_rescue": ("Exact kill!", "Choose one mission zone card to rescue to the discard pile. "
                                       "The enemy and the rest of the zone are banished."),
        "whistle_take": ("Scarlet Whistle", "Your attack is a solitary companion or beast: you may add the top card "
                                            "of the discard pile to it (the beast copies its strength), or skip."),
        "zone_move": ("Enemy defeated", "Choose one card in play to move to the mission zone. Its strength joins "
                                        "Myla's team damage."),
        "pilgrim_banish": ("A pilgrim matches", "The card that entered play has the strength of a pilgrim in the "
                                                "mission zone: you may banish that pilgrim (once per card)."),
        "zone_banish": ("Exact kill!", "You may first move one mission zone card to the banished pile. Then cards "
                                       "equal to the zone's total strength go from the reserve to the discard pile "
                                       "and the zone is discarded."),
        "zone_build": ("Enemy defeated", "You may move cards in play to the mission zone one at a time, each exactly "
                                         "one strength higher than the zone's highest card. Non-pilgrims there add "
                                         "their strength to the enemies; a 10 fills the zone and heals."),
        "mother_choice": ("Evergreen Mother", "A corrupted card entered play. Banish the top card of the discard pile "
                                              "instead of the top card of the reserve deck?"),
        "pile_to_reserve": ("Exact kill!", "You may move the top card of one captured pile to the top of the "
                                           "reserve deck."),
        "zone_discard": ("Exact kill!", "You may first discard one card from the mission zone. The enemy and the "
                                        "rest of the zone are then shuffled into the banished pile."),
        "zone_sibling": ("Squad of Siblings", "A mission zone card has the same strength as a card in your attack: "
                                              "you may move it to the discard pile."),
        "zone_match": ("Selfless Rescue", "A card you discarded to suffer damage matches a mission zone card's "
                                          "strength: you may move that card to the discard pile."),
        "precision_strike": ("Precision Strike", "Exact kill: take any card from the mission zone, or the top card "
                                                 "of the discard pile, into your hand."),
    }
    VERBS = {"mage_pick": "Add", "emblem_keep": "Keep", "reaver_pick": "Add", "zone_rescue": "Rescue",
             "zone_move": "Move", "cleanup_top": "Top", "banish_top": "Top", "discard_top": "Top",
             "whistle_take": "Add", "pilgrim_banish": "Banish",
             "zone_banish": "Banish", "zone_build": "Move", "discard_pick": "Top", "zone_discard": "Discard",
             "zone_sibling": "Move", "zone_match": "Move", "precision_strike": "Take"}
    MANY = 4   # more card options than this go in two columns with short titles

    def heading(self, g: Game, d: dict) -> tuple:
        kind = str(d.get("kind"))
        if kind == "zone_rescue" and getattr(g.rules, "mission", 0) == 6:
            return ("Exact kill!", "Choose one mission zone card except Myla to move to the discard pile. "
                                   "Myla then deals team damage equal to the zone's strength.")
        return self.TEXTS.get(kind, ("Your choice", "Choose one option."))

    def strip(self, g: Game, d: dict) -> Optional[CardStrip]:
        return None

    def columns(self, n: int) -> int:
        return 2 if n > self.MANY else 1

    def is_option(self, a: dict) -> bool:
        return bool(a.get("card")) or "count" in a or ("pile" in a and not a.get("skip"))

    def option_title(self, g: Game, a: dict, short: bool) -> str:
        if not short:
            return a.get("label", a["type"])
        if a.get("card"):
            tail = " (discard)" if a.get("pile") == "discard" else ""
            return "%s %s%s" % (self.VERBS.get(a["type"], "Pick"), g.card(a["card"]).label(), tail)
        return str(a.get("count", a.get("label", a["type"])))

    def build_parts(self) -> tuple:
        """(heading views, one button per option, trailing views)."""
        g = self.screen.game
        d = g.decision or {}
        title, text = self.heading(g, d)
        size = 20
        while size > 13 and text_size(title, 0, size, True)[0] > self.text_width():
            size -= 1                       # a long title shrinks rather than being cut off
        head: List[ui.View] = [
            make_label(title, (0, 0, 10, 36), size, True, T.ACCENT, ui.ALIGN_CENTER),
            self.text(text, 13),
        ]
        strip = self.strip(g, d)
        if strip is not None:
            head.append(strip)
        acts = g.legal_actions()
        cards = [a for a in acts if self.is_option(a)]
        short = self.columns(len(cards)) > 1
        options: List[ui.View] = []
        for a in cards:
            options.append(make_button(self.option_title(g, a, short),
                                       (lambda act: lambda s: self.screen.decide(act))(a), (0, 0, 10, 44)))
        tail: List[ui.View] = []
        for a in acts:
            if not self.is_option(a):
                tail.append(make_button(a.get("label", a["type"]),
                                        (lambda act: lambda s: self.screen.decide(act))(a), (0, 0, 10, 44), not a.get("skip")))
        # The decision cannot be dismissed, so the game menu (undo, log, save) is offered here.
        tail.append(make_button("Game menu", lambda s: self.screen._menu(s), (0, 0, 10, 36), False, 13))
        return head, options, tail

    def build(self) -> List[ui.View]:
        head, options, tail = self.build_parts()
        return head + options + tail

    def layout(self) -> None:
        if not hasattr(self, "panel") or not hasattr(self, "screen"):
            return
        self._unpeek_for_layout()
        for v in list(self.panel.subviews):
            self.panel.remove_subview(v)
        pw = min(340, self.width - 2 * T.MARGIN)
        head, options, tail = self.build_parts()
        y = 20
        for v in head:
            v.frame = (20, y, pw - 40, v.height)
            self.panel.add_subview(v)
            y += v.height + 12
        cols = self.columns(len(options))
        gap = 8 if cols > 1 else 12
        bw = (pw - 40 - gap * (cols - 1)) / cols
        bh = 40 if cols > 1 else 44
        rows = (len(options) + cols - 1) // cols
        grid_h = rows * (bh + gap) - gap if rows else 0
        # the option buttons scroll when the box would be taller than the screen, so the
        # heading, the closing buttons and "Hold to view game" stay in view
        tail_h = sum(v.height + 12 for v in tail) + (48 if not tail else 0)
        room = self.height - T.TOP_INSET - T.BOTTOM_INSET - 8 - y - tail_h - 12
        holder = self.panel
        oy, x0 = y, 20
        if rows and grid_h > room and room >= bh:
            # end halfway through a button (never between two, never on a sliver), so the
            # hidden ones are hinted at; the area only ever shrinks
            k = int((room - bh * 0.5) // (bh + gap))
            if k >= 1:
                room = k * (bh + gap) + bh * 0.5
            holder = ui.ScrollView(frame=(20, y, pw - 40, room))
            holder.content_size = (pw - 40, grid_h)
            self.panel.add_subview(holder)
            oy, x0 = 0, 0
        for i, b in enumerate(options):
            r, c = divmod(i, cols)
            b.frame = (x0 + c * (bw + gap), oy + r * (bh + gap), bw, bh)
            fit_title(b)
            holder.add_subview(b)
        if rows:
            y += (holder.height if holder is not self.panel else grid_h) + 12
        for v in tail:
            v.frame = (20, y, pw - 40, v.height)
            if isinstance(v, ui.Button):
                fit_title(v)
            self.panel.add_subview(v)
            y += v.height + 12
        y = self._add_peek(pw, y)
        ph = y + 8
        self.panel.frame = ((self.width - pw) / 2, max(T.TOP_INSET, (self.height - ph) / 2), pw, ph)


def attack_summary(g: Game, play_index) -> str:
    """The attack a decision is about, for players weighing an addition (the Mage's look):
    its cards, strength and classes, and the enemy's immunity."""
    try:
        play = g.plays[int(play_index)] if play_index is not None else (g.plays[-1] if g.plays else None)
    except (IndexError, TypeError, ValueError):
        play = None
    if play is None:
        return ""
    cards = " + ".join(g.card(c).label() for c in play.card_ids)
    classes = ", ".join("%s %s" % (SUIT_SYMBOL.get(x, x), CLASS_NAME.get(x, x)) for x in play.suits) or "no class"
    text = "Your attack: %s, strength %d (%s)." % (cards, play.value, classes)
    immune = g.rules.immune_suits(g) if g.enemy is not None else ()
    if immune and not g.immunity_cancelled:
        text += " %s is immune to %s." % (g.enemy.name, ", ".join(CLASS_NAME.get(x, x) + "s" for x in immune))
    return text


class MagePeekOverlay(PickOverlay):
    """The Mage's secret look: the cards taken from the top of the reserve in a row (Jesters
    and corrupted cards dimmed, they are discarded), one button per card that may join the
    attack, or a single "Nothing to add" when none may."""

    def heading(self, g: Game, d: dict) -> tuple:
        revealed = list(d.get("revealed", []))
        n = len(revealed)
        if n == 0:
            return ("Mage: the reserve deck is empty", "There was nothing to look at. The attack goes on resolving as it is.")
        title = "Mage: %d card%s revealed" % (n, "" if n == 1 else "s")
        summary = attack_summary(g, d.get("play_index"))
        strength = int(d.get("strength", n))
        text = "You looked at the top %d card%s of the reserve deck%s. Jesters and corrupted cards are discarded. " \
               "Choose one of the rest to add to the attack; the others go to the discard pile." % (
                   n, "" if n == 1 else "s", "" if n == strength else " (the mage's strength is %d, the deck was short)" % strength)
        if not d.get("eligible"):
            text = "You looked at the top %d card%s of the reserve deck, but none of them may join the attack: " \
                   "Jesters and corrupted cards are discarded." % (n, "" if n == 1 else "s")
        return (title, (summary + "\n\n" + text) if summary else text)

    def dimmed_ids(self, g: Game, d: dict) -> List[str]:
        eligible = set(str(c) for c in d.get("eligible", []))
        return [str(c) for c in d.get("revealed", []) if str(c) not in eligible]

    def strip_title(self) -> str:
        return "Revealed from the reserve deck (top first)"

    def strip(self, g: Game, d: dict) -> Optional[CardStrip]:
        revealed = [g.card(str(c)) for c in d.get("revealed", [])]
        if not revealed:
            return None
        strip = CardStrip(frame=(0, 0, 10, 84))
        strip.set_cards(revealed, self.strip_title(), self.dimmed_ids(g, d))
        return strip


class EmblemKeepOverlay(MagePeekOverlay):
    """Azure Emblem, solo: after the pick, one of the other revealed cards may go back on
    top of the reserve deck before the rest is discarded."""

    def heading(self, g: Game, d: dict) -> tuple:
        picked = g.card(str(d.get("picked", ""))).label() if d.get("picked") in g.cards else "the chosen card"
        return ("Azure Emblem", "%s joined the attack. You may put one of the other revealed cards on top of the "
                                "reserve deck before the rest goes to the discard pile." % picked)

    def dimmed_ids(self, g: Game, d: dict) -> List[str]:
        return []


class ReaverPickOverlay(MagePeekOverlay):
    """Reaver, second step: the revealed cards in a row; one adds its strength to the damage,
    all are banished, then the damage is doubled."""

    def heading(self, g: Game, d: dict) -> tuple:
        n = len(d.get("revealed", []))
        return ("Reaver: %d card%s revealed" % (n, "" if n == 1 else "s"),
                "Choose the card whose strength is added to the damage (%d so far). All revealed cards are "
                "banished, then the damage is doubled." % int(d.get("damage", 0)))

    def dimmed_ids(self, g: Game, d: dict) -> List[str]:
        return []

    def strip_title(self) -> str:
        return "Revealed from the reserve deck (all are banished)"


def pile_top_why(g: Game, pile: str) -> str:
    """Why the top card of the discard or the banished pile matters in this game (the order
    questions explain themselves with it)."""
    number = getattr(g.rules, "mission", 0)
    if pile == "banished":
        return {5: "The top banished card goes into the mission zone at the end of the turn.",
                11: "The enemy gains the top banished card's strength and classes.",
                12: "The top banished card goes into the mission zone at the start of the next turn."}.get(
            number, "The top banished card counts for the enemy.")
    if getattr(g.rules, "discard_top_feeds_enemy", lambda game: False)(g):
        return {4: "The top card's strength adds to the enemy's.",
                10: "A cleric enemy moves the top card into the mission zone at the end of the turn.",
                11: "The enemy gains the top card's strength and classes."}.get(number, "The top card counts for the enemy.")
    return "The Scarlet Whistle can add the top card of the discard pile to a later attack."


class TopChoiceOverlay(PickOverlay):
    """Retired: only a game saved while the app asked which card ends on top of a pile (the
    played cards at clean-up, a mage's unchosen cards, a reaver's or a mage attack's
    banished cards) still shows it. Those questions now ask for the whole order
    (``OrderOverlay``)."""

    def heading(self, g: Game, d: dict) -> tuple:
        kind = str(d.get("kind"))
        if kind == "cleanup_top":
            text = "Enemy defeated: the played cards go on top of the discard pile in any order you wish."
        elif kind == "discard_top":
            text = "Mage: the revealed cards you did not choose go to the discard pile in any order."
        elif d.get("source") == "reaver":
            text = "Reaver: the revealed cards are banished in any order."
        else:
            text = "Enemy defeated: the cards of the mage attack are banished in the order you choose."
        return ("Which card ends on top?", text + " " + pile_top_why(g, "banished" if kind == "banish_top" else "discard"))

    def strip(self, g: Game, d: dict) -> Optional[CardStrip]:
        cards = [g.card(str(c)) for c in d.get("options", []) if str(c) in g.cards]
        if not cards:
            return None
        strip = CardStrip(frame=(0, 0, 10, 84))
        strip.set_cards(cards, "To the %s pile" % ("banished" if str(d.get("kind")) == "banish_top" else "discard"))
        return strip

    def option_title(self, g: Game, a: dict, short: bool) -> str:
        if a.get("card"):
            return ("Top %s" if short else "Put %s on top") % g.card(a["card"]).label()
        return super().option_title(g, a, short)


class DeclareOverlay(PickOverlay):
    """Rulebook p.25: a Wild Animal declares a class, 2/5s whose strength is a free choice a
    strength (one for all of them), when they enter a playmat; they keep it while in play."""

    def heading(self, g: Game, d: dict) -> tuple:
        card = g.card(str(d.get("card"))).label() if str(d.get("card")) in g.cards else "The card"
        if str(d.get("kind")) == "declare_value":
            return ("2 or 5?", "%s Declare it now; it is kept while in play (discarded to suffer damage a "
                               "2/5 always counts 5)." % g.rules.declare_value_question(g, d))
        imm = [CLASS_NAME.get(s, s) + "s" for s in g.rules.immune_suits(g) if s in BASIC_SUITS] if g.enemy else []
        text = "%s enters play: declare its class. It keeps it while it is in play." % card
        if imm and not g.extra.get("jester_attack"):
            text += " The enemy is immune to %s." % " / ".join(imm)
        return ("Wild Animal", text)

    def strip(self, g: Game, d: dict) -> Optional[CardStrip]:
        cid = str(d.get("card"))
        if cid not in g.cards:
            return None
        strip = CardStrip(frame=(0, 0, 10, 84))
        strip.set_cards([g.card(str(c)) for c in d.get("cards") or [cid] if str(c) in g.cards], "Entering play")
        return strip


class ReaverCountOverlay(PickOverlay):
    """Reaver, first step: how many cards to reveal from the top of the reserve deck (a grid
    of numbers when the deck is big)."""

    def heading(self, g: Game, d: dict) -> tuple:
        return ("Reaver", "Choose how many cards to reveal from the top of the reserve deck (%d left). One of "
                          "them adds its strength to the damage, all of them are banished, then the damage is "
                          "doubled." % len(g.tavern))

    def columns(self, n: int) -> int:
        return 5 if n > self.MANY else 1


class ChanterDeclareOverlay(PickOverlay):
    """Chanter: how many cards everyone draws (a grid of numbers, 0 included)."""

    def heading(self, g: Game, d: dict) -> tuple:
        return ("Chanter", "Declare any number from 0 to %d: starting with you and going clockwise, every player "
                           "draws that many cards ignoring the hand limit, then discards down to it." % len(g.tavern))

    def columns(self, n: int) -> int:
        return 5 if n > self.MANY else 1


class PileToReserveOverlay(PickOverlay):
    """Mission 9's exact kill: the top card of one captured pile may go on top of the reserve."""

    def strip(self, g: Game, d: dict) -> Optional[CardStrip]:
        tops = [g.card(p[0]) for p in g.extra.get("captured", []) if p]
        if not tops:
            return None
        strip = CardStrip(frame=(0, 0, 10, 84))
        strip.set_cards(tops, "Captured piles (top cards)")
        return strip

    def columns(self, n: int) -> int:
        return 1


class CardGridOverlay(Overlay):
    """A decision over many cards (a Druid's deal, the discard pile): a scrollable grid of
    small tappable cards; subclasses say which cards, how many may be picked and which
    buttons follow. ``picked`` holds the selection in tap order."""

    columns = 6
    grid_height = 196
    single = False

    def __init__(self, screen: GameScreen, **kw) -> None:
        super().__init__(screen, **kw)
        self.picked: List[str] = []
        self.card_views: Dict[str, CardView] = {}

    def heading(self, g: Game, d: dict) -> tuple:
        return ("Your choice", "")

    def card_ids(self, g: Game, d: dict) -> List[str]:
        return []

    def badges(self, g: Game, d: dict) -> Dict[str, str]:
        return {}

    def buttons(self, g: Game, d: dict) -> List[ui.View]:
        return []

    def tapped(self, v: CardView) -> None:
        cid = v.card.id
        if cid in self.picked:
            self.picked.remove(cid)
        elif self.single:
            self.picked = [cid]
        else:
            self.picked.append(cid)
        self.layout()

    def build(self) -> List[ui.View]:
        g = self.screen.game
        d = g.decision or {}
        title, text = self.heading(g, d)
        items: List[ui.View] = [make_label(title, (0, 0, 10, 36), 20, True, T.ACCENT, ui.ALIGN_CENTER)]
        if text:
            items.append(self.text(text, 13))
        ids = self.card_ids(g, d)
        pw = min(340, self.width - 2 * T.MARGIN) - 40
        cols = self.columns
        gap = 5.0
        cw = (pw - gap * (cols - 1)) / cols
        ch = cw * 1.42
        rows = (len(ids) + cols - 1) // cols
        need = rows * (ch + gap)
        sv = ui.ScrollView(frame=(0, 0, pw, min(self.grid_height, need) if ids else 24))
        sv.content_size = (pw, need + 4)
        badges = self.badges(g, d)
        self.card_views = {}
        for i, cid in enumerate(ids):
            r, c = divmod(i, cols)
            v = CardView(g.card(cid), on_tap=self.tapped)
            v.small = True
            v.selected = cid in self.picked
            v.badge = badges.get(cid, "")
            v.frame = (c * (cw + gap), r * (ch + gap) + (0 if v.selected else 3), cw, ch - 3)
            sv.add_subview(v)
            self.card_views[cid] = v
        items.append(sv)
        items.extend(self.buttons(g, d))
        items.append(make_button("Game menu", lambda s: self.screen._menu(s), (0, 0, 10, 36), False, 13))
        return items


class DruidOverlay(CardGridOverlay):
    """Druid: the cards dealt to one player in a grid; tap a card, then one of the four
    destination slots (Banish / Hand / Reserve top / Reserve bottom); Confirm when every
    needed slot is filled. A player dealt fewer than four cards fills that many slots."""

    SLOTS = (("banish", "Banish"), ("hand", "Hand"), ("top", "Top"), ("bottom", "Bottom"))   # of the reserve
    single = True

    def __init__(self, screen: GameScreen, **kw) -> None:
        super().__init__(screen, **kw)
        self.assign: Dict[str, str] = {}   # slot -> card id

    def _template(self, g: Game) -> dict:
        acts = [a for a in g.legal_actions() if a["type"] == "druid_assign"]
        return acts[0] if acts else {"pick_from": [], "needs": 0}

    def heading(self, g: Game, d: dict) -> tuple:
        t = self._template(g)
        who = g.players[g.deciding].name
        n, needs = len(t.get("pick_from", [])), int(t.get("needs", 0))
        return ("Druid: sort %d card%s" % (n, "" if n == 1 else "s"),
                "%s was dealt these from the shuffled discard pile. Tap a card, then where it goes: one each to the "
                "banished pile, your hand (ignoring the limit), the top and the bottom of the reserve deck%s. The "
                "rest goes back to the discard pile." % (
                    who, "" if needs == 4 else " (%d of the four with %d card%s)" % (needs, n, "" if n == 1 else "s")))

    def card_ids(self, g: Game, d: dict) -> List[str]:
        return [str(c) for c in self._template(g).get("pick_from", [])]

    def badges(self, g: Game, d: dict) -> Dict[str, str]:
        names = dict(self.SLOTS)
        return dict((cid, names[slot].lower()) for slot, cid in self.assign.items())

    def set_slot(self, slot: str) -> None:
        g = self.screen.game
        if self.picked:
            cid = self.picked[0]
            for k, v in list(self.assign.items()):
                if v == cid:
                    del self.assign[k]
            self.assign[slot] = cid
            self.picked = []
        else:
            self.assign.pop(slot, None)
        self.layout()

    def buttons(self, g: Game, d: dict) -> List[ui.View]:
        t = self._template(g)
        needs = int(t.get("needs", 0))
        row = ui.View(frame=(0, 0, 10, 92))
        pw = min(340, self.width - 2 * T.MARGIN) - 40
        bw = (pw - 8) / 2
        for i, (slot, title) in enumerate(self.SLOTS):
            cid = self.assign.get(slot)
            label = "%s: %s" % (title, g.card(cid).label() if cid else "—")
            b = make_button(label, (lambda sl: lambda s: self.set_slot(sl))(slot),
                            ((i % 2) * (bw + 8), (i // 2) * 48, bw, 40), bool(cid), 13)
            fit_title(b)
            row.add_subview(b)
        confirm = make_button("Confirm", lambda s: self.confirm(), (0, 0, 10, 46))
        set_enabled(confirm, len(self.assign) == needs)
        return [row, confirm]

    def confirm(self) -> None:
        g = self.screen.game
        act = {"type": "druid_assign", "player": g.deciding}
        act.update(self.assign)
        self.screen.decide(act)


class DiscardBanishOverlay(CardGridOverlay):
    """Mission 8's filled zone: banish any cards from the discard pile (multi-select), the
    rest is shuffled under the reserve."""

    def heading(self, g: Game, d: dict) -> tuple:
        return ("Mission zone filled!", "The zone went to the discard pile. Search it and banish any cards you want "
                                        "(Jesters, pilgrims, weak cards); the rest is shuffled under the reserve deck. "
                                        "No more cards may be moved to the zone this mission.")

    def card_ids(self, g: Game, d: dict) -> List[str]:
        return list(g.discard)

    def buttons(self, g: Game, d: dict) -> List[ui.View]:
        n = len(self.picked)
        title = "Banish %d selected" % n if n else "Banish nothing"
        return [make_button(title, lambda s: self.confirm(), (0, 0, 10, 46))]

    def confirm(self) -> None:
        g = self.screen.game
        if self.picked:
            self.screen.decide({"type": "discard_banish", "player": g.deciding, "cards": list(self.picked)})
        else:
            self.screen.decide({"type": "discard_banish_skip"})


class DiscardPickOverlay(CardGridOverlay):
    """Mission 8's exact kill: any one card of the discard pile goes on top of the reserve."""

    single = True

    def heading(self, g: Game, d: dict) -> tuple:
        return ("Exact kill!", "You may put any one card from the discard pile on top of the reserve deck. Tap it, "
                               "then confirm, or leave the pile as it is.")

    def card_ids(self, g: Game, d: dict) -> List[str]:
        return list(g.discard)

    def buttons(self, g: Game, d: dict) -> List[ui.View]:
        title = "Put %s on top of the reserve" % g.card(self.picked[0]).label() if self.picked else "Put the selected card on top"
        b = make_button(title, lambda s: self.screen.decide({"type": "discard_pick", "card": self.picked[0]}), (0, 0, 10, 46))
        set_enabled(b, bool(self.picked))
        return [b, make_button("Leave the discard pile", lambda s: self.screen.decide({"type": "discard_pick_skip"}), (0, 0, 10, 44), False)]


class PileRescueOverlay(Overlay):
    """Mission 9's end of turn: rescue the top card of one captured pile by banishing a card
    from hand (pick the pile here, then the card from the hand), or rotate every pile."""

    def build(self) -> List[ui.View]:
        g = self.screen.game
        who = g.players[g.deciding].name
        piles = g.extra.get("captured", [])
        items: List[ui.View] = [
            make_label("End of turn", (0, 0, 10, 36), 20, True, T.ACCENT, ui.ALIGN_CENTER),
            self.text("%s may banish a card from hand to move the top card of one captured pile to the discard "
                      "pile. Otherwise the top card of every pile goes to its bottom." % who, 13),
        ]
        tops = [g.card(p[0]) for p in piles if p]
        if tops:
            strip = CardStrip(frame=(0, 0, 10, 84))
            strip.set_cards(tops, "Captured piles (top cards)")
            items.append(strip)
        can = bool(g.rules.unlocked_hand(g, g.deciding))
        for k, pile in enumerate(piles):
            if not pile:
                continue
            b = make_button("Rescue %s (pile %d, %d cards)" % (g.card(pile[0]).label(), k + 1, len(pile)),
                            (lambda idx: lambda s: self.screen.pick_pile(idx))(k), (0, 0, 10, 44))
            set_enabled(b, can)
            items.append(b)
        items.append(make_button("Rotate the piles", lambda s: self.screen.decide({"type": "pile_rotate"}), (0, 0, 10, 44), False))
        items.append(make_button("Game menu", lambda s: self.screen._menu(s), (0, 0, 10, 36), False, 13))
        return items


class OrderOverlay(CardGridOverlay):
    """The "What order?" question: tap the cards in the order they go to a pile, numbered
    as tapped (the first tapped goes first, the last ends on top). The cards are the
    decision template's ``pick_from``: the mission zone for mission 12's banish order and
    the Lake's discard order, a mage's unchosen cards (``discard_order``), a reaver's
    revealed cards (``reaver_order``), the played cards after a kill
    (``played_discard_order``, ``played_banish_order``, shown in the order they entered
    play with a one-tap "Keep the order played"); all but the first two are asked only
    where the top of that pile matters."""

    KEEP = ("played_discard_order", "played_banish_order")

    def heading(self, g: Game, d: dict) -> tuple:
        kind = str(d.get("kind"))
        if kind == "banish_order":
            return ("Enemy defeated", "The mission zone is banished first, then the enemy, then the whole discard "
                                      "pile. Tap the zone cards in the order they are banished: the last one ends "
                                      "on top and comes back into the zone next turn.")
        if kind == "discard_order":
            return ("What order?", "Mage: the revealed cards you did not choose go to the discard pile in any order. "
                                   "Tap them in order: the first tapped goes first, the last ends on top. "
                                   + pile_top_why(g, "discard"))
        if kind == "reaver_order":
            return ("What order?", "Reaver: the revealed cards are banished in any order. Tap them in order: the "
                                   "first tapped goes first, the last ends on top. " + pile_top_why(g, "banished"))
        if kind == "played_discard_order":
            return ("What order?", "Enemy defeated: the played cards go on top of the discard pile in any order. "
                                   "Tap them in order (the first tapped goes first, the last ends on top) or keep "
                                   "the order they were played. " + pile_top_why(g, "discard"))
        if kind == "played_banish_order":
            return ("What order?", "Enemy defeated: the mage attack's cards are banished in any order. Tap them in "
                                   "order (the first tapped goes first, the last ends on top) or keep the order "
                                   "they were played. " + pile_top_why(g, "banished"))
        return ("Enemy defeated", "The Lake: the mission zone goes to the discard pile in any order. Tap the cards "
                                  "in order: the last one ends on top of the discard pile.")

    def card_ids(self, g: Game, d: dict) -> List[str]:
        acts = [a for a in g.legal_actions() if "needs" in a]
        return [str(c) for c in acts[0].get("pick_from", [])] if acts else []

    def badges(self, g: Game, d: dict) -> Dict[str, str]:
        return dict((cid, str(i + 1)) for i, cid in enumerate(self.picked))

    def buttons(self, g: Game, d: dict) -> List[ui.View]:
        n, total = len(self.picked), len(self.card_ids(g, d))
        b = make_button("Confirm the order (%d of %d)" % (n, total), lambda s: self.confirm(), (0, 0, 10, 46))
        set_enabled(b, n == total and total > 0)
        if str(d.get("kind")) in self.KEEP:
            # the cards are shown in the order they entered play: keep it in one tap
            keep = make_button("Keep the order played", lambda s: self.confirm(self.card_ids(g, d)), (0, 0, 10, 44), False)
            return [b, keep]
        return [b]

    def confirm(self, order: Optional[List[str]] = None) -> None:
        g = self.screen.game
        cards = list(self.picked) if order is None else list(order)
        self.screen.decide({"type": str((g.decision or {}).get("kind")), "player": g.deciding, "cards": cards})


class CloseCallOverlay(CardGridOverlay):
    """Evergreen boon 35: the damage was paid exactly; one discard pile card goes on top of
    the reserve deck."""

    single = True

    def heading(self, g: Game, d: dict) -> tuple:
        return ("A Close Call", "You paid the damage exactly: the discarded cards went under the reserve deck. "
                                "Now put any one card from the discard pile on top of the reserve deck.")

    def card_ids(self, g: Game, d: dict) -> List[str]:
        return list(g.discard)

    def buttons(self, g: Game, d: dict) -> List[ui.View]:
        title = "Put %s on top of the reserve" % g.card(self.picked[0]).label() if self.picked else "Put the selected card on top"
        b = make_button(title, lambda s: self.screen.decide({"type": "close_call", "card": self.picked[0]}), (0, 0, 10, 46))
        set_enabled(b, bool(self.picked))
        return [b]


class RestoredArrowsOverlay(CardGridOverlay):
    """Evergreen boon 33: on an exact kill any one banished card may go under the reserve."""

    single = True

    def heading(self, g: Game, d: dict) -> tuple:
        return ("Restored Arrows", "Exact kill: you may put any one card from the banished pile on the bottom of "
                                   "the reserve deck. Tap it, then confirm, or leave the pile.")

    def card_ids(self, g: Game, d: dict) -> List[str]:
        return list(reversed(g.banished))   # the top of the pile first

    def buttons(self, g: Game, d: dict) -> List[ui.View]:
        title = "Put %s under reserve" % g.card(self.picked[0]).label() if self.picked else "Put under reserve"
        b = make_button(title, lambda s: self.screen.decide({"type": "restored_arrows", "card": self.picked[0]}), (0, 0, 10, 46))
        set_enabled(b, bool(self.picked))
        return [b, make_button("Leave the banished pile", lambda s: self.screen.decide({"type": "restored_arrows_skip"}), (0, 0, 10, 44), False)]


# Decisions where one card leaves the deciding player's hand: shown as the hand with one
# selectable card. ``verb`` is the right button, ``skip`` the left one when the rules offer
# a "do nothing" option, ``text`` / ``chosen`` the message before and after a selection.
HAND_PICKS: Dict[str, Dict[str, str]] = {
    "zone_feed": {"title": "A card from hand into the mission zone", "verb": "To the zone",
                  "text": "End of turn: %(who)s must put a card from hand into the mission zone (it adds to the enemy's strength). Select it and tap To the zone.",
                  "chosen": "%(who)s puts %(card)s into the mission zone."},
    "beast_discard": {"title": "Cleric beast: discard a card", "verb": "Discard",
                      "text": "A cleric beast was revealed: %(who)s must discard a card from hand. Select it and tap Discard.",
                      "chosen": "%(who)s discards %(card)s (cleric beast)."},
    "beast_banish": {"title": "Bard beast: banish a card", "verb": "Banish",
                     "text": "A bard beast was revealed: %(who)s must banish a card from hand. Select it and tap Banish.",
                     "chosen": "%(who)s banishes %(card)s (bard beast)."},
    "attack_discard": {"title": "Eye-Level Sticks: discard a card", "verb": "Discard",
                       "text": "Eye-Level Sticks: the attack holds a card of strength 8 or more, so %(who)s must discard a card from hand before it resolves.",
                       "chosen": "%(who)s discards %(card)s (Eye-Level Sticks)."},
    "poison": {"title": "Choose Your Poison", "verb": "Discard", "skip": "Reserve → zone",
               "text": "Choose Your Poison: %(who)s may discard a card from hand; otherwise the top card of the reserve deck goes into the mission zone.",
               "chosen": "%(who)s discards %(card)s; the reserve deck stays put."},
}

# Decision kinds shown as the deciding player's hand (flute-style) rather than as a list
# of buttons; the team damage of mission 6 has its own seat picker, mission 9's rescue
# its pile picker first.
HAND_DECISIONS = ("flute_add", "emblem_place", "whistle_add", "team_discard", "chanter_discard", "mother_banish",
                  "pile_rescue") + tuple(HAND_PICKS)
PICK_OVERLAYS = {"mage_peek": MagePeekOverlay, "emblem_keep": EmblemKeepOverlay,
                 "reaver_count": ReaverCountOverlay, "reaver_pick": ReaverPickOverlay,
                 "druid_assign": DruidOverlay, "chanter_declare": ChanterDeclareOverlay,
                 "discard_banish": DiscardBanishOverlay, "discard_pick": DiscardPickOverlay,
                 "pile_to_reserve": PileToReserveOverlay,
                 "banish_order": OrderOverlay, "zone_order": OrderOverlay,
                 "discard_order": OrderOverlay, "reaver_order": OrderOverlay,
                 "played_discard_order": OrderOverlay, "played_banish_order": OrderOverlay,
                 "close_call": CloseCallOverlay, "restored_arrows": RestoredArrowsOverlay,
                 # the top-card questions of games saved before the order questions
                 "cleanup_top": TopChoiceOverlay, "banish_top": TopChoiceOverlay, "discard_top": TopChoiceOverlay,
                 "declare_class": DeclareOverlay, "declare_value": DeclareOverlay}


class TeamDamageOverlay(Overlay):
    """Mission 6: Myla's team damage (Evergreen: the Hills, Explosive Spores). Names what is
    left to discard and asks who discards the next card. Hands stay secret (rulebook p.24:
    never share hand information): the seats show names and card counts only, and in
    pass-and-play the phone is passed before that player's hand is shown."""

    def build(self) -> List[ui.View]:
        g = self.screen.game
        d = g.decision or {}
        remaining = int(d.get("damage", 0)) - int(d.get("paid", 0))
        source = str(d.get("source") or "Myla")
        items: List[ui.View] = [
            make_label("Team damage: %d to go" % remaining, (0, 0, 10, 36), 22, True, T.DANGER, ui.ALIGN_CENTER),
            self.text("%s deals %d team damage. Any player discards one card at a time, in any order and without "
                      "talking about their hands, until that much strength is discarded. Who discards next?" % (
                          source, int(d.get("damage", 0))), 13),
        ]
        for i, p in enumerate(g.players):
            if not p.hand:
                continue
            title = "%s (%d card%s)" % (p.name, len(p.hand), "" if len(p.hand) == 1 else "s")
            items.append(make_button(title, (lambda idx: lambda s: self.screen.pick_team_seat(idx))(i), (0, 0, 10, 46)))
        items.append(make_button("Game menu", lambda s: self.screen._menu(s), (0, 0, 10, 36), False, 13))
        return items


class ChooseNextOverlay(Overlay):
    def build(self) -> List[ui.View]:
        g = self.screen.game
        if g.extra.get("jester_claim"):
            text = "Who claims the Jester? That player attacks now, ignoring the enemy's immunity for this attack."
        else:
            text = "%s chooses who goes next. Players may say if they would like to go." % g.active_player.name
        items: List[ui.View] = [
            make_label("Jester!", (0, 0, 10, 36), 24, True, T.ACCENT, ui.ALIGN_CENTER),
            self.text(text, 14),
        ]
        for a in g.legal_actions():
            if a["type"] == "choose_next":
                i = a["player"]
                title = "%s (%d cards)" % (g.players[i].name, len(g.players[i].hand))
                items.append(make_button(title, (lambda idx: lambda s: self.screen.choose_next(idx))(i), (0, 0, 10, 46)))
        return items


class ResultOverlay(Overlay):
    def build(self) -> List[ui.View]:
        g = self.screen.game
        if g.phase == PHASE_WON:
            title = "Victory!"
            if g.result in ("gold", "silver", "bronze"):
                title = "%s victory!" % g.result.capitalize()
            detail = "All 12 enemies defeated in %d turns." % g.turn
            if g.n_players == 1:
                detail += " Jester powers used: %d." % g.solo_jesters_used
            color = T.ACCENT
        else:
            title = "Defeat"
            detail = "%s Enemies defeated: %d of 12." % (g.loss_reason, g.enemies_defeated)
            color = T.DANGER
        return [
            make_label(title, (0, 0, 10, 40), 28, True, color, ui.ALIGN_CENTER),
            self.text(detail, 14),
            make_button("Play again", lambda s: self.screen.app.start_game(g.config), (0, 0, 10, 48)),
            make_button("Main menu", lambda s: self.screen.app.show(MenuScreen(self.screen.app)), (0, 0, 10, 48), False),
        ]


class GameMenuOverlay(Overlay):

    peekable = False   # not a choice: it closes with its own button

    def build(self) -> List[ui.View]:
        app = self.screen.app
        items: List[ui.View] = [
            make_label("Game menu", (0, 0, 10, 32), 20, True, T.TEXT, ui.ALIGN_CENTER),
            make_button("Resume", lambda s: self.screen._back_to_game(), (0, 0, 10, 46)),
        ]
        if app.undo_stack:
            items.append(make_button("Undo last action", self._undo, (0, 0, 10, 46), False))
        if app.in_campaign:
            items.append(make_button("Mission rules", lambda s: self.screen._show_overlay(RulesOverlay(self.screen)),
                                     (0, 0, 10, 46), False))
        items.append(make_button("Discard and reserve piles", lambda s: self.screen._show_piles(), (0, 0, 10, 46), False))
        items.append(make_button("Game log", lambda s: self.screen._show_overlay(LogOverlay(self.screen)), (0, 0, 10, 46), False))
        items.append(make_button("Save and go to menu", lambda s: (app.autosave(), app.show(MenuScreen(app))), (0, 0, 10, 46), False))
        if app.in_campaign:
            items.append(make_button("Abandon attempt (counts as a loss)", self._abandon_attempt, (0, 0, 10, 46), False, 14))
        else:
            items.append(make_button("Abandon game", self._abandon, (0, 0, 10, 46), False))
        return items

    def _undo(self, sender) -> None:
        app = self.screen.app
        if app.undo():
            self.screen.shown_player = None if (app.game.n_players > 1 and not app.game.config.open_hands) else app.game.deciding
            self.screen.message_text = "Undone."
            self.screen.refresh(after_action=False)

    @ui.in_background
    def _abandon(self, sender) -> None:
        import console
        if console.alert("Abandon game?", "The current game will be deleted.", "Abandon", "Cancel") == 1:
            store.delete_game()
            self.screen.app.game = None
            self.screen.app.show(MenuScreen(self.screen.app))

    @ui.in_background
    def _abandon_attempt(self, sender) -> None:
        """A campaign or Evergreen attempt given up: it is recorded as a loss (coins and all,
        as any lost attempt) and its save is deleted; the quick-play game is left alone."""
        import console
        if console.alert("Abandon this attempt?", "It counts as a lost attempt.", "Abandon", "Cancel") == 1:
            g = self.screen.game
            self.screen._act(g.abandon)


def mission_rules_text(camp, game: Optional[Game] = None) -> str:
    """The rules card: the mission's rules (or the drawn Evergreen setup), then what each
    relic the party holds does, with the side for this number of players."""
    parts: List[str] = []
    evergreen = game is not None and str(getattr(game.config, "rules_id", "")) == "evergreen"
    if evergreen:
        setup = camp.evergreen_setup() if camp is not None else None
        if setup:
            loc = setup["location"]
            parts.append("Evergreen mission: the %s" % loc["name"])
            parts.append(EvergreenScreen._location_text(loc))
            for b in setup.get("banes", []):
                parts.append("Bane %d, %s: %s" % (b["n"], b["name"], b["text"]))
            for b in setup.get("boons", []):
                parts.append("Boon %d, %s: %s" % (b["n"], b["name"], b["text"]))
    elif camp is not None:
        info = mission_info(camp.mission)
        parts.append("Mission %d · %s" % (camp.mission, info["title"]))
        parts.append(info["location"])
        parts.append(info["summary"])
    players = game.n_players if game is not None else (camp.players if camp is not None else 1)
    relics = list(game.extra.get("relics", [])) if game is not None else list(camp.relics if camp is not None else [])
    if game is None and camp is not None and not camp.finished:
        # the mission's setup cards may swap a relic (mission 12: the restored Mother)
        from regicide.campaign import missions as M
        for step in M.start_steps(camp, camp.mission):
            if step.get("kind") == "relic_swap" and step.get("old") in relics:
                relics[relics.index(step["old"])] = step["new"]
    if relics:
        parts.append("Your relics (%s side):" % ("solo" if players == 1 else "two or more players"))
        for r in relics:
            parts.append("%s: %s" % (relic_name(r), relic_text(r, players)))
    return "\n\n".join(x for x in parts if x)


class RulesOverlay(Overlay):
    """The mission's rules card, shown when a mission first loads and from the in-game
    menu: drawn as a playing card (``card_face``), scrolling when the text is longer than
    the screen."""

    def layout(self) -> None:
        if not hasattr(self, "panel") or not hasattr(self, "screen"):
            return
        for v in list(self.panel.subviews):
            self.panel.remove_subview(v)
        self.panel.background_color = None
        app = self.screen.app
        pw = min(330, self.width - 2 * T.MARGIN)
        head, subtitle, text, corner = rules_card(app.campaign, self.screen.game)
        room = self.height - T.TOP_INSET - T.BOTTOM_INSET - 58 - 6
        face = card_face(head, text, pw, room, None, T.ACCENT, subtitle, corner, 13)
        self.panel.add_subview(face)
        ok = make_button("Got it", self._close, (0, face.height + 12, pw, 46))
        fit_title(ok)
        self.panel.add_subview(ok)
        ph = face.height + 12 + 46
        self.panel.frame = ((self.width - pw) / 2, max(T.TOP_INSET, (self.height - ph) / 2), pw, ph)

    def _close(self, sender) -> None:
        app = self.screen.app
        if not self.screen.rules_pending:
            self.screen._back_to_game()      # opened from the in-game menu
            return
        if self.screen.rules_pending and app.campaign is not None and not app.campaign.finished:
            seen = app.campaign.flags.setdefault("rules_seen", [])
            if app.campaign.mission not in seen:
                seen.append(app.campaign.mission)
                app.save_campaign()
        self.screen.rules_pending = False
        self.screen.refresh(after_action=False)


def choice_title(step: dict) -> str:
    """A few words naming a pending reward or setup choice (the game menu's button)."""
    kind = step.get("kind")
    if kind == "choice_classes":
        return "class stickers"
    if kind == "choice_suit":
        return "a %s sticker" % CLASS_NAME.get(str(step.get("suit", "")), "class")
    if kind == "choice_mage_student":
        return "a new mage"
    if kind == "choice_corrupt":
        return "corruption"
    if kind == "choice_rip":
        return "the Eternal Vine"
    return "choose"


def choice_icon(step: dict) -> list:
    """The icon on a reward's card: the class a sticker gives, the mage's star, else a star."""
    kind = step.get("kind")
    if kind == "choice_suit":
        suit = str(step.get("suit", ""))
        return [(SUIT_SYMBOL.get(suit, "★"), T.SUIT_COLOR.get(suit, T.ACCENT))]
    if kind == "choice_mage_student":
        return [(SUIT_SYMBOL["M"], T.SUIT_COLOR["M"])]
    if kind == "choice_corrupt" or kind == "choice_rip":
        return [("◆", T.CORRUPTED)]
    return [("★", T.ACCENT)]


def choice_text(camp, step: dict) -> str:
    """The reward card's text: the reward as the mission card states it, then what the
    choice does and what is on offer."""
    def labels(ids):
        out = []
        for cid in ids:
            c = P.find(camp.party, str(cid)) if camp is not None else None
            out.append(P.to_card(c).label() if c else str(cid))
        return ", ".join(out)

    kind = step.get("kind")
    parts = [str(step.get("label", ""))]
    if kind == "choice_classes":
        parts.append("Revealed from the shuffled party: %s. Give each one class sticker: each class is used "
                     "once and no card gets a class it already has. The stickers stay for the rest of the "
                     "campaign." % labels(step.get("cards", [])))
    elif kind == "choice_suit":
        parts.append("Choose one of %s. It keeps its own class and gains the %s class for the rest of the "
                     "campaign." % (labels(step.get("options", [])), CLASS_NAME.get(str(step.get("suit", "")), "new")))
    elif kind == "choice_mage_student":
        parts.append("Choose the 4s or the 8s. The party is shuffled and the first card of that strength with "
                     "no sticker (never Gøran or a mage) gains the Mage class.")
    elif kind == "choice_corrupt":
        parts.append("Choose the character who takes the corruption. Corrupted cards banish the top card of "
                     "the reserve when played, and their own class ignores immunity.")
    elif kind == "choice_rip":
        parts.append("Choose the corrupted character who wears a cloak of the Eternal Vine. The card is torn "
                     "up and leaves the campaign for good.")
    return "\n\n".join(x for x in parts if x)


def card_face(title: str, body: str, width: float, max_height: float, icon=None, edge: str = "",
              subtitle: str = "", corner=None, body_size: int = 14):
    """A card pop-up's face, drawn like the game's playing cards (``PlayingCardFace``): the
    icon (a list of (text, colour), side by side) and the name at the top, an optional
    subtitle, a rule in the card's colour, then the text (scrolling when it is longer than
    the card). The card keeps a playing card's proportions unless the screen is too short;
    ``corner`` is the small index in two corners (by default the icon). Returns the face,
    sized ``width`` wide."""
    from .widgets import PlayingCardFace
    tokens = [(str(t), str(c)) for t, c in (icon or [])]
    corner = tokens[:4] if corner is None else [(str(t), str(c)) for t, c in corner][:4]
    edge = edge or (tokens[0][1] if tokens else T.CARD_BORDER)
    face = PlayingCardFace(edge, corner)
    inner = width - 84          # clear of the corner index
    y = 18.0
    if tokens:
        size = 44.0
        widths = [max(size * 1.25, text_size(t, 0, size, True)[0] + 10) for t, _ in tokens]
        x = (width - sum(widths)) / 2.0
        for (t, c), tw_ in zip(tokens, widths):
            face.add_subview(make_label(t, (x, y, tw_, size * 1.25), int(size), True, c, ui.ALIGN_CENTER))
            x += tw_
        y += size * 1.25 + 4
    name = fit_label(title, inner, 19, True, T.CARD_INK, ui.ALIGN_CENTER)
    name.frame = (42, y, inner, name.height)
    face.add_subview(name)
    y += name.height + 2
    if subtitle:
        sub = fit_label(subtitle, inner, 12, False, T.CARD_INK_MUTED, ui.ALIGN_CENTER)
        sub.frame = (42, y, inner, sub.height)
        face.add_subview(sub)
        y += sub.height + 2
    rule = ui.View(frame=(30, y + 6, width - 60, 1.5))
    rule.background_color = edge
    face.add_subview(rule)
    y += 16
    bw = width - 44
    _, th = text_size(body, bw - 4, body_size)
    th = float(th)
    bottom = 14 + (len(corner) * 17.0 * 1.05 + 4 if corner else 0)   # clear of the bottom-right index
    room = max(80.0, max_height - y - bottom)
    bh = min(th + 10, room)
    sv = ui.ScrollView(frame=(22, y, bw, bh))
    sv.add_subview(make_label(body, (0, 0, bw, th + 8), body_size, False, T.CARD_INK, ui.ALIGN_LEFT, 0))
    sv.content_size = (bw, th + 10)
    face.add_subview(sv)
    height = min(max(y + bh + bottom, width * 1.4), max(max_height, y + bh + bottom))
    face.frame = (0, 0, width, height)
    return face


def special_title(specials: List[dict]) -> str:
    """The button that opens the rules' special actions: "Flute" when they are all the solo
    Kinfolk Flute's."""
    return "Flute" if all(a.get("name") == "flute_store" for a in specials) else "Actions"


def shield_rows(g: Game) -> List[tuple]:
    """(cards, value, counts) for each paladin (Spades) play against the enemy: what it adds
    to the shield, or why it adds nothing (the enemy's immunity), as ``Game.shield`` counts."""
    rows = []
    for p in g.plays:
        if "S" not in p.suits:
            continue
        cards = " + ".join(g.card(c).label() for c in p.card_ids)
        counts = not g.rules.fixed_immunity(g, "S") and (
            p.jester or not g.immune("S", [g.card(c) for c in p.card_ids]))
        rows.append((cards, p.value, counts))
    return rows


def attack_face(g: Game, sel: List[str], pv: Optional[dict], forecast: str, width: float, max_height: float):
    """The attack's card: the enemy's attack (printed, the mission's bonus, a multiplier)
    beside the players' shield (each paladin play), what is suffered, and with cards
    selected what the play would change (``forecast``)."""
    from .widgets import PlayingCardFace, card_color
    e = g.enemy
    card = g.card(e.card_id)
    col = card_color(card)
    face = PlayingCardFace(col, [(card.rank, col)])
    ink, muted = T.CARD_INK, T.CARD_INK_MUTED
    y = 22.0
    face.add_subview(make_label("Attack", (42, y, width - 84, 26), 20, True, ink, ui.ALIGN_CENTER))
    y += 26
    face.add_subview(fit_label(e.name, width - 84, 12, False, muted, ui.ALIGN_CENTER))
    face.subviews[-1].frame = (42, y, width - 84, 18)
    y += 22
    rule = ui.View(frame=(30, y, width - 60, 1.5))
    rule.background_color = col
    face.add_subview(rule)
    y += 10
    gap = 14.0
    cw = (width - 44 - gap) / 2.0
    bonus = g.rules.attack_bonus(g)
    mult = g.rules.attack_multiplier(g)
    left = [("Printed", "%d" % e.attack, ink)]
    if bonus:
        left.append(("Mission", "%+d" % bonus, ink))
    if mult != 1:
        left.append(("Doubled" if mult == 2 else "Multiplied", "×%d" % mult, ink))
    right = [(cards if counts else cards + " immune", "%d" % v if counts else "0", ink if counts else muted)
             for cards, v, counts in shield_rows(g)]
    if len(right) > 5:
        hidden = len(right) - 4
        right = right[-4:] + [("%d more" % hidden, "", muted)]
    if not right:
        right = [("None yet", "", muted)]
    total_atk = (e.attack + bonus) * mult

    def column(x: float, head: str, rows: List[tuple], total: str) -> float:
        yy = y
        face.add_subview(make_label(head, (x, yy, cw, 18), 12, True, muted, ui.ALIGN_CENTER))
        yy += 22
        for name, value, c in rows:
            face.add_subview(make_label(name, (x, yy, cw - 30, 20), 14, False, c, ui.ALIGN_LEFT))
            face.add_subview(make_label(value, (x + cw - 34, yy, 34, 20), 14, True, c, ui.ALIGN_RIGHT))
            yy += 21
        line = ui.View(frame=(x, yy + 2, cw, 1))
        line.background_color = muted
        face.add_subview(line)
        yy += 6
        face.add_subview(make_label(total, (x, yy, cw, 28), 22, True, ink, ui.ALIGN_CENTER))
        return yy + 30

    bottom = max(column(22, "ENEMY", left, "%d" % total_atk),
                 column(22 + cw + gap, "SHIELD", right, ("−%d" % g.shield) if g.shield else "0"))
    y = bottom + 6
    face.add_subview(make_label("You suffer %d" % g.enemy_attack, (22, y, width - 44, 30), 22, True, T.DANGER,
                                ui.ALIGN_CENTER))
    y += 34
    if pv and forecast:
        rule2 = ui.View(frame=(30, y, width - 60, 1.5))
        rule2.background_color = col
        face.add_subview(rule2)
        y += 8
        head = "With " + " + ".join(g.card(c).label() for c in sel)
        face.add_subview(fit_label(head, width - 44, 13, True, ink, ui.ALIGN_LEFT))
        face.subviews[-1].frame = (22, y, width - 44, 18)
        y += 20
        _, th = text_size(forecast, width - 48, 13)
        face.add_subview(make_label(forecast, (22, y, width - 44, float(th) + 6), 13, False, ink, ui.ALIGN_LEFT, 0))
        y += float(th) + 8
    height = max(y + 40, min(width * 1.4, max_height))
    face.frame = (0, 0, width, min(height, max(max_height, y + 40)))
    return face


def enemy_text(g: Game, forecast: str = "", sel_label: str = "") -> str:
    """The enemy's card text: health, immunity, what is left in the castle (mission 10's
    face-up enemy deck shows the next one) and what the selected cards would do."""
    from .widgets import immunity_text
    e = g.enemy
    lines = ["Health %d of %d. Attack %d." % (max(0, e.hp), e.max_hp, g.enemy_attack), immunity_text(g)[0] + "."]
    castle = "%d more in the castle." % len(g.castle)
    if getattr(g.rules, "mission", 0) == 10 and g.castle:
        castle = "%d more in the castle, next: %s." % (len(g.castle), g.card(g.castle[0]).label())
    lines.append(castle)
    if forecast:
        lines.append("")
        lines.append("With %s: %s" % (sel_label, forecast))
    return "\n".join(lines)


class CardPopup(ui.View):
    """A pop-up drawn as a playing card (``card_face``: name and icon at the top, the text
    below) over a dimmed screen, with its buttons under the card. A button is (title,
    action, primary) or (title, action, primary, enabled). With ``dismissable`` a tap
    beside the card closes it."""

    def __init__(self, title: str, text: str, buttons, icon=None, edge: str = "", subtitle: str = "",
                 corner=None, dismissable: bool = False, make_face=None, **kw) -> None:
        super().__init__(**kw)
        self.make_face = make_face   # (width, max height) -> a face of its own instead of ``card_face``
        self.title_text = title
        self.body = text
        self.buttons = list(buttons)
        self.icon = icon
        self.edge = edge
        self.subtitle = subtitle
        self.corner = corner
        self.dismissable = dismissable
        self.face: Optional[ui.View] = None
        self.background_color = (0, 0, 0, 0.72)

    def layout(self) -> None:
        if not hasattr(self, "buttons"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        pw = min(300, self.width - 2 * T.MARGIN)
        buttons_h = 58 * len(self.buttons)
        room = self.height - T.TOP_INSET - T.BOTTOM_INSET - buttons_h - 6
        face = (self.make_face(pw, room) if self.make_face is not None else
                card_face(self.title_text, self.body, pw, room, self.icon, self.edge, self.subtitle, self.corner))
        total = face.height + 12 + buttons_h
        x = (self.width - pw) / 2.0
        y = max(T.TOP_INSET, (self.height - total) / 2.0)
        face.frame = (x, y, pw, face.height)
        self.add_subview(face)
        self.face = face
        y += face.height + 12
        for spec in self.buttons:
            title_, action, primary = spec[0], spec[1], spec[2]
            b = make_button(title_, action, (x, y, pw, 46), primary)
            fit_title(b)
            if len(spec) > 3 and not spec[3]:
                set_enabled(b, False, primary)
            self.add_subview(b)
            y += 58

    def touch_ended(self, touch) -> None:
        if not self.dismissable:
            return
        x, y = touch.location
        f = self.face
        # the card and the buttons under it, gaps included, count as on the card: a near
        # miss of a button (or a tap on a greyed-out one) never closes the pop-up
        bottom = max([f.y + f.height] + [v.y + v.height for v in self.subviews if isinstance(v, ui.Button)]) if f else 0
        if f is None or not (f.x <= x <= f.x + f.width and f.y <= y <= bottom):
            self.close()

    def close(self) -> None:
        if self.superview is not None:
            self.superview.remove_subview(self)


def show_card_popup(screen: ui.View, popup: CardPopup) -> CardPopup:
    """Lay ``popup`` over the whole of ``screen``."""
    popup.frame = (0, 0, screen.width, screen.height)
    screen.add_subview(popup)
    popup.layout()
    return popup


def rules_card(camp, game: Optional[Game] = None) -> tuple:
    """(name, subtitle, text, corner) of the rules card: the mission's name ("Mission 4 ·
    ...") on top with its location below it, the rules after, and the mission number (or
    E for Evergreen) as the corner index."""
    text = mission_rules_text(camp, game)
    head, _, rest = text.partition("\n\n")
    evergreen = game is not None and str(getattr(game.config, "rules_id", "")) == "evergreen"
    subtitle = ""
    if head.startswith("Mission ") and rest:
        place, _, after = rest.partition("\n\n")
        if after and len(place) <= 40:
            subtitle, rest = place, after
    elif not (head.startswith("Evergreen mission") and rest):
        head, rest = "Mission rules", text
    mark = "E" if evergreen or (camp is not None and camp.finished) else str(getattr(camp, "mission", "") or "")
    return head, subtitle, rest, ([(mark, T.CARD_INK_MUTED)] if mark else [])


class LogOverlay(Overlay):

    peekable = False   # not a choice: it closes with its own button

    def build(self) -> List[ui.View]:
        g = self.screen.game
        lines = g.log[-14:]
        text = "\n".join(lines) if lines else "Nothing yet."
        body = self.text(text, 12, align=ui.ALIGN_LEFT)
        # the lines scroll when they would push Back off the screen; the newest show first
        room = self.height - T.TOP_INSET - T.BOTTOM_INSET - 30 - 44 - 3 * 12 - 28
        tw = self.text_width()
        sv = ui.ScrollView(frame=(0, 0, tw, max(60.0, min(body.height, room))))
        body.frame = (0, 0, tw, body.height)
        sv.add_subview(body)
        sv.content_size = (tw, body.height)
        sv.content_offset = (0, max(0.0, body.height - sv.height))
        return [
            make_label("Game log", (0, 0, 10, 30), 18, True, T.TEXT, ui.ALIGN_CENTER),
            sv,
            make_button("Back", lambda s: self.screen._back_to_game(), (0, 0, 10, 44)),
        ]


def deck_list_key(card: Card) -> tuple:
    """The order cards are listed in the deck list (and the piles viewer's reserve): by
    their first class (classless cards, a Jester among them, last), then by strength."""
    return (card.suits[0] if card.suits else "Z", card.value)


class PilesOverlay(Overlay):
    """The piles at a glance: the discard pile and the banished pile in order, the top card
    first, and the reserve (tavern) deck sorted like the deck list (by class, then
    strength; equal-looking cards by id), which shows what is left without giving its
    order away. One pile at a time, picked with a segmented control."""

    columns = 5
    peekable = False   # not a choice: it closes with its own button

    def __init__(self, screen: "GameScreen", pile: str = "discard", **kw) -> None:
        super().__init__(screen, **kw)
        self.pile = pile

    def hidden_hands(self, g: Game) -> bool:
        """Pass-and-play with hidden hands: listing the reserve alone would give the other
        players' hands away (every other card is public or in the player's own hand), so the
        reserve is shown together with those hands, as the cards this player has not seen."""
        return g.n_players > 1 and not g.config.open_hands

    def unseen(self, g: Game) -> List[str]:
        """The reserve, plus every hand but the one shown (all hands while none is shown)."""
        me = self.screen.shown_player
        return list(g.tavern) + [c for i, p in enumerate(g.players) if i != me for c in p.hand]

    def piles(self, g: Game) -> List[tuple]:
        """(key, segment title) of the piles to show."""
        legacy = bool(getattr(g.rules, "legacy", False))
        reserve = ("Unseen %d" % len(self.unseen(g)) if self.hidden_hands(g)
                   else "%s %d" % ("Reserve" if legacy else "Tavern", len(g.tavern)))
        out = [("discard", "Discard %d" % len(g.discard)), ("reserve", reserve)]
        if legacy or g.banished:
            out.append(("banished", "Banished %d" % len(g.banished)))
        return out

    def pile_cards(self, g: Game) -> tuple:
        """(card ids in the order shown, the line under the control, a badge per id)."""
        legacy = bool(getattr(g.rules, "legacy", False))
        if self.pile == "reserve":
            name = "reserve deck" if legacy else "tavern deck"
            if self.hidden_hands(g):
                ids = sorted(self.unseen(g), key=lambda c: (deck_list_key(g.card(c)), c))
                note = ("Nothing you have not seen." if not ids else
                        "The cards you have not seen: the %s and the other players' hands together, sorted like "
                        "the deck list." % name)
                return ids, note, {}
            ids = sorted(g.tavern, key=lambda c: (deck_list_key(g.card(c)), c))
            note = ("The %s is empty." % name if not ids else
                    "What is left in the %s, sorted like the deck list: its order stays hidden." % name)
            return ids, note, {}
        if self.pile == "banished":
            ids = list(reversed(g.banished))          # the last banished is on top
            note = "The banished pile is empty." if not ids else "In order, the top card first."
        else:
            ids = list(g.discard)                     # the first is the top card
            note = "The discard pile is empty." if not ids else "In order, the top card first."
        return ids, note, ({ids[0]: "top"} if ids else {})

    def build(self) -> List[ui.View]:
        g = self.screen.game
        piles = self.piles(g)
        keys = [k for k, _ in piles]
        if self.pile not in keys:
            self.pile = "discard"
        seg = ui.SegmentedControl(frame=(0, 0, 10, 32))
        seg.segments = [t for _, t in piles]
        seg.selected_index = keys.index(self.pile)
        seg.action = lambda s: self._switch(keys[s.selected_index])
        ids, note, badges = self.pile_cards(g)
        pw = self.text_width()
        cols = self.columns
        gap = 5.0
        cw = (pw - gap * (cols - 1)) / cols
        ch = cw * 1.42
        rows = (len(ids) + cols - 1) // cols
        need = rows * (ch + gap)
        note_label = self.text(note, 12, color=T.MUTED, min_height=34)
        # the grid takes the room the screen has left and scrolls past it; it is as tall for
        # every pile (the biggest one's height), so switching piles does not move the panel
        room = self.height - T.TOP_INSET - T.BOTTOM_INSET - 36 - 32 - note_label.height - 44 - 5 * 12 - 28
        biggest = max(len(g.discard), len(self.unseen(g)) if self.hidden_hands(g) else len(g.tavern), len(g.banished), 1)
        tallest = ((biggest + cols - 1) // cols) * (ch + gap)
        sv = ui.ScrollView(frame=(0, 0, pw, max(ch + gap, min(tallest, room))))
        sv.content_size = (pw, need + 4)
        self.card_views = {}
        for i, cid in enumerate(ids):
            r, c = divmod(i, cols)
            v = CardView(g.card(cid))
            v.small = True
            v.touch_enabled = False
            v.badge = badges.get(cid, "")
            v.frame = (c * (cw + gap), r * (ch + gap), cw, ch)
            sv.add_subview(v)
            self.card_views[cid] = v
        self.grid = sv
        return [make_label("Piles", (0, 0, 10, 36), 20, True, T.ACCENT, ui.ALIGN_CENTER), seg, note_label, sv,
                make_button("Back", lambda s: self.screen._back_to_game(), (0, 0, 10, 44))]

    def _switch(self, pile: str) -> None:
        self.pile = pile
        self.layout()


class ClassChoiceOverlay(Overlay):
    """Legacy solo: the Jester attacks as an 8 of a chosen class."""

    def build(self) -> List[ui.View]:
        items: List[ui.View] = [
            make_label("Jester attack", (0, 0, 10, 36), 22, True, T.ACCENT, ui.ALIGN_CENTER),
            self.text("Strength 8, ignores immunity. Choose its class:", 14),
        ]
        for s in BASIC_SUITS:
            title = "%s %s" % (SUIT_SYMBOL[s], CLASS_NAME[s])
            items.append(make_button(title, (lambda suit: lambda b: self.screen._act(lambda: self.screen.game.use_solo_jester({"suit": suit})))(s), (0, 0, 10, 46)))
        items.append(make_button("Cancel", lambda b: self.screen.refresh(after_action=False), (0, 0, 10, 44), False))
        return items


class SpecialOverlay(Overlay):
    """Relic and mission actions offered by the rules."""

    peekable = False   # not a choice: it closes with its own button

    def build(self) -> List[ui.View]:
        g = self.screen.game
        items: List[ui.View] = [make_label("Actions", (0, 0, 10, 32), 20, True, T.TEXT, ui.ALIGN_CENTER)]
        for a in g.rules.special_actions(g):
            items.append(make_button(a.get("label", a.get("name", "?")), (lambda act: lambda b: self.screen._act(lambda: g.special(act)))(a), (0, 0, 10, 46)))
        items.append(make_button("Back", lambda b: self.screen.refresh(after_action=False), (0, 0, 10, 44), False))
        return items


class CampaignResultOverlay(Overlay):
    def build(self) -> List[ui.View]:
        app = self.screen.app
        g = self.screen.game
        res = getattr(self.screen, "campaign_result", {})
        items: List[ui.View] = []
        if res.get("evergreen"):
            # Pack E: no coins, no rewards; retry the same setup or draw another
            if res.get("won"):
                items.append(make_label("Evergreen mission won!", (0, 0, 10, 36), 22, True, T.ACCENT, ui.ALIGN_CENTER))
                items.append(self.text("The %s is cleared in %d turns (attempt %d)." % (
                    g.rules.location_name(g), g.turn, int(res.get("attempts", 1))), 13))
            else:
                items.append(make_label("Evergreen mission lost", (0, 0, 10, 36), 22, True, T.DANGER, ui.ALIGN_CENTER))
                items.append(self.text("%s Enemies defeated: %d. No coins in Evergreen mode: retry this setup or draw another." % (
                    g.loss_reason, g.enemies_defeated), 13))
            items.append(make_button("Play this setup again", lambda b: app.start_evergreen_attempt(), (0, 0, 10, 46), not res.get("won")))
            items.append(make_button("Evergreen missions", lambda b: app.show(EvergreenScreen(app)), (0, 0, 10, 46), bool(res.get("won"))))
            items.append(make_button("Game menu", lambda b: app.show(CampaignScreen(app)), (0, 0, 10, 46), False))
            return items
        num = int(g.config.extra.get("mission", 1))
        info = mission_info(num)
        if res.get("won"):
            items.append(make_label("Mission %d complete" % num, (0, 0, 10, 36), 22, True, T.ACCENT, ui.ALIGN_CENTER))
            lines = list(res.get("rewards") or [])
            for step in res.get("pending") or []:
                lines.append("To choose: %s" % step.get("label", "a reward"))
            lines = lines or ["No rewards."]
            items.append(self.text("\n".join(lines), 13, align=ui.ALIGN_LEFT))
            if app.campaign and app.campaign.finished:
                items.append(make_label("The campaign is complete!", (0, 0, 10, 30), 16, True, T.OK, ui.ALIGN_CENTER))
        else:
            items.append(make_label("Mission %d lost" % num, (0, 0, 10, 36), 22, True, T.DANGER, ui.ALIGN_CENTER))
            text = "%s %d coin%s earned (%d total)." % (g.loss_reason, res.get("earned", 0), "" if res.get("earned") == 1 else "s", res.get("coins", 0))
            if res.get("m_box_opened_now"):
                text += " Pack M is open: mercenaries can be hired between attempts."
            items.append(self.text(text, 13))
            if app.campaign and app.campaign.m_box_opened:
                items.append(make_button("Mercenary camp", lambda b: app.show(MercenaryScreen(app, back="menu")),
                                         (0, 0, 10, 46)))
            items.append(make_button("Try again", lambda b: app.start_attempt(), (0, 0, 10, 46), not (app.campaign and app.campaign.m_box_opened)))
        items.append(make_button("Game menu", lambda b: app.show(CampaignScreen(app)), (0, 0, 10, 46), False))
        return items


class CampaignScreen(Screen):
    """The game menu of one campaign save."""

    def layout(self) -> None:
        if not hasattr(self, "app"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        app = self.app
        w, h = self.width, self.height
        m = T.MARGIN
        y = T.TOP_INSET
        self.add_subview(make_button("‹ Menu", lambda s: app.show(MenuScreen(app)), (m, y, 80, 36), False, 14))
        camp = app.campaign
        self.add_subview(make_label(camp.name if camp else "No game", (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 50
        if camp is None:
            self.add_subview(make_label("Open a game from the main menu.", (m, y, w - 2 * m, 30), 14, False, T.MUTED))
            return
        info = mission_info(camp.mission)
        bw = min(320, w - 2 * m)
        x = (w - bw) / 2
        if camp.finished:
            self.add_subview(make_label("Campaign complete!", (m, y, w - 2 * m, 30), 18, True, T.OK, ui.ALIGN_CENTER))
            y += 34
            record = camp.evergreen or {}
            self.add_subview(make_label("Evergreen mode (pack E): %d mission%s played, %d won." % (
                int(record.get("played", 0)), "" if int(record.get("played", 0)) == 1 else "s", int(record.get("wins", 0))),
                (m, y, w - 2 * m, 20), 12, False, T.MUTED, ui.ALIGN_CENTER))
            y += 28
            if store.has_attempt(camp.slot):
                self.add_subview(make_button("Continue attempt", lambda s: app.resume_attempt(), (x, y, bw, 46)))
                y += 54
            # Pack E: Evergreen mode, generated missions with the finished party deck
            self.add_subview(make_button("Evergreen mission", lambda s: app.show(EvergreenScreen(app)), (x, y, bw, 46)))
            y += 54
        else:
            self.add_subview(make_label("Mission %d · %s" % (camp.mission, info["title"]), (m, y, w - 2 * m, 28), 18, True, T.ACCENT))
            y += 28
            self.add_subview(make_label(info["location"], (m, y, w - 2 * m, 20), 13, False, T.MUTED))
            y += 24
            flavour = fit_label(info.get("flavour") or info["summary"], w - 2 * m, 14, False, T.TEXT, ui.ALIGN_LEFT)
            flavour.frame = (m, y, w - 2 * m, min(flavour.height, 60))
            self.add_subview(flavour)
            y += flavour.height + 6
            stats = "Attempts %d · Losses %d" % (camp.attempts_on(camp.mission), camp.losses_on(camp.mission))
            if camp.m_box_opened:
                stats += " · Coins %d" % camp.coins
            if not info.get("verified", False):
                stats += " · rules unverified"
            self.add_subview(make_label(stats, (m, y, w - 2 * m, 20), 12, False, T.MUTED))
            y += 26
            # (Gøran's beast and the mercenary camp are chosen in the deck list)
            in_progress = store.has_attempt(camp.slot)
            if not in_progress and info.get("playable") and not camp.pending and camp.prepare_mission():
                app.save_campaign()
            choice = camp.pending_choice()
            if in_progress:
                self.add_subview(make_button("Continue attempt", lambda s: app.resume_attempt(), (x, y, bw, 46)))
                y += 54
            elif choice is not None:
                # a short title here; the pop-up card explains the reward before choosing
                prefix = "Mission setup" if choice.get("phase") == "setup" else "Reward"
                rb = make_button("%s: %s" % (prefix, choice_title(choice)), lambda s: self._show_choice_card(),
                                 (x, y, bw, 46))
                fit_title(rb)
                self.add_subview(rb)
                y += 54
            elif info.get("playable"):
                attempt = camp.attempts_on(camp.mission) + 1
                title = "Next mission: start" if attempt == 1 else "Retry mission (attempt %d)" % attempt
                self.add_subview(make_button(title, lambda s: app.start_attempt(), (x, y, bw, 46)))
                y += 54
            else:
                b = make_button("Mission %d arrives in a later build" % camp.mission, lambda s: None, (x, y, bw, 46))
                set_enabled(b, False)
                self.add_subview(b)
                y += 54
        y += 6
        row_h, gap = 44, 10
        buttons = [] if camp.finished else [("Mission rules", lambda s: self._show_rules_card())]
        buttons += [
            ("Deck list", lambda s: app.show(PartyScreen(app))),
            ("Map", lambda s: app.show(MapScreen(app))),
            ("Progress", lambda s: app.show(ProgressScreen(app))),
            ("Lore", lambda s: app.show(LoreScreen(app, local=True))),
        ]
        for title, action in buttons:
            self.add_subview(make_button(title, action, (x, y, bw, row_h), False))
            y += row_h + gap


    def _show_choice_card(self) -> None:
        """The pending reward (or setup) choice as a card: what it is and what it does, then
        Choose (the choice screen) or Later."""
        app = self.app
        choice = app.campaign.pending_choice() if app.campaign else None
        if choice is None:
            return
        heading = "Mission setup" if choice.get("phase") == "setup" else "Reward"
        popup = CardPopup(choice_title(choice)[:1].upper() + choice_title(choice)[1:], choice_text(app.campaign, choice),
                          [("Choose", lambda s: app.show(ChoiceScreen(app)), True),
                           ("Later", lambda s: popup.close(), False)],
                          icon=choice_icon(choice), edge=T.ACCENT, subtitle=heading)
        show_card_popup(self, popup)

    def _show_rules_card(self) -> None:
        """The mission's rules card as a card pop-up over the game menu."""
        head, subtitle, text, corner = rules_card(self.app.campaign)
        popup = CardPopup(head, text, [("Got it", lambda s: popup.close(), True)], edge=T.ACCENT, subtitle=subtitle,
                          corner=corner, dismissable=True)
        show_card_popup(self, popup)


class MapScreen(Screen):
    """A stylised route across Deccaria: one stop per mission."""

    STOPS = [(0.14, 0.92), (0.40, 0.86), (0.70, 0.84), (0.86, 0.72), (0.62, 0.64), (0.32, 0.60),
             (0.14, 0.48), (0.40, 0.42), (0.70, 0.40), (0.84, 0.28), (0.56, 0.20), (0.26, 0.12)]

    def __init__(self, app: "App", **kw) -> None:
        super().__init__(app, **kw)
        self.selected: Optional[int] = None
        self.canvas = _MapCanvas(self)
        self.caption = make_label("", (0, 0, 10, 10), 13, False, T.TEXT, ui.ALIGN_CENTER, lines=3)
        self.add_subview(self.canvas)
        self.add_subview(self.caption)

    def layout(self) -> None:
        if not hasattr(self, "caption"):
            return
        for v in list(self.subviews):
            if v not in (self.canvas, self.caption):
                self.remove_subview(v)
        app = self.app
        w, h = self.width, self.height
        m = T.MARGIN
        y = T.TOP_INSET
        self.add_subview(make_button("‹ Back", lambda s: app.show(CampaignScreen(app)), (m, y, 80, 36), False, 14))
        self.add_subview(make_label("Map of Deccaria", (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 46
        self.caption.frame = (m, h - T.BOTTOM_INSET - 60, w - 2 * m, 56)
        self.canvas.frame = (m, y, w - 2 * m, self.caption.y - y - 6)
        self.canvas.set_needs_display()
        self._update_caption()

    def _update_caption(self) -> None:
        camp = self.app.campaign
        if camp is None:
            return
        n = self.selected or camp.mission
        info = mission_info(n)
        if camp.revealed(n):
            state = "completed" if n in camp.completed else ("current" if n == camp.mission else "locked")
            self.caption.text = "%d. %s — %s (%s)" % (n, info["title"], info["location"], state)
        else:
            self.caption.text = "%d. Unknown. Complete mission %d to reveal it." % (n, n - 1)

    def select(self, n: int) -> None:
        self.selected = n
        self._update_caption()
        self.canvas.set_needs_display()


class _MapCanvas(ui.View):
    def __init__(self, screen: MapScreen, **kw) -> None:
        super().__init__(**kw)
        self.screen = screen
        self.background_color = "#1f2a26"
        self.corner_radius = 14

    def _points(self):
        w, h = self.width, self.height
        return [(x * w, y * h) for x, y in MapScreen.STOPS]

    def draw(self) -> None:
        camp = self.screen.app.campaign
        pts = self._points()
        # terrain hint: a few soft shapes
        ui.set_color("#26332e")
        ui.Path.oval(self.width * 0.05, self.height * 0.55, self.width * 0.5, self.height * 0.3).fill()
        ui.Path.oval(self.width * 0.45, self.height * 0.08, self.width * 0.5, self.height * 0.32).fill()
        ui.set_color("#2b3c55")
        ui.Path.oval(self.width * 0.55, self.height * 0.56, self.width * 0.42, self.height * 0.2).fill()
        # route
        route = ui.Path()
        route.line_width = 3
        route.move_to(*pts[0])
        for p in pts[1:]:
            route.line_to(*p)
        ui.set_color("#6b5d3a")
        route.stroke()
        for i, (x, y) in enumerate(pts):
            n = i + 1
            r = 15
            if camp is not None and n in camp.completed:
                fill, ring, txt = T.ACCENT, T.ACCENT, T.BG
            elif camp is not None and n == camp.mission and not camp.finished:
                fill, ring, txt = T.PANEL, T.ACCENT, T.TEXT
            else:
                fill, ring, txt = "#2a2f3a", "#4a5060", T.MUTED
            if self.screen.selected == n:
                ui.set_color(T.TEXT)
                ui.Path.oval(x - r - 4, y - r - 4, 2 * r + 8, 2 * r + 8).stroke()
            ui.set_color(fill)
            ui.Path.oval(x - r, y - r, 2 * r, 2 * r).fill()
            ring_path = ui.Path.oval(x - r, y - r, 2 * r, 2 * r)
            ring_path.line_width = 2
            ui.set_color(ring)
            ring_path.stroke()
            ui.draw_string(str(n), (x - r, y - 9, 2 * r, 18), (T.FONT_BOLD, 13), txt, ui.ALIGN_CENTER)
            if camp is not None and camp.revealed(n):
                title = mission_info(n)["title"]
                ty = y + r + 2 if i % 2 == 0 else y - r - 16
                ui.draw_string(title, (x - 60, ty, 120, 16), (T.FONT, 10), T.MUTED, ui.ALIGN_CENTER)

    def touch_ended(self, touch) -> None:
        x, y = touch.location
        best = None
        for i, (px, py) in enumerate(self._points()):
            if (px - x) ** 2 + (py - y) ** 2 <= 24 ** 2:
                best = i + 1
        if best is not None:
            self.screen.select(best)


def mercenary_icon(card: Card) -> tuple:
    """(icon, corner) of a mercenary's card pop-up: its class icons (all four for a Wild
    Animal), its rank for a classless 19, a J for a Jester; the corner index is the rank
    and the class."""
    from .widgets import card_color
    col = card_color(card)
    rank = "2/5" if card.has("twofive") else ("J" if card.is_jester else card.rank)
    if card.has("choosable") and not card.suits:
        icon = [(SUIT_SYMBOL[s], T.SUIT_COLOR[s]) for s in BASIC_SUITS]
    elif card.suits:
        icon = [(SUIT_SYMBOL.get(s, s), T.SUIT_COLOR.get(s, col)) for s in card.suits]
    else:
        icon = [(rank, col)]
    # a playing card's index: the rank and its one class (a Wild Animal shows its rank only)
    corner = [(rank, col)] + (icon if len(icon) == 1 and icon[0][0] != rank else [])
    return icon, corner


def mercenary_text(merc: dict, card: Card, evergreen: bool) -> str:
    """What a mercenary is and what hiring it means."""
    cls = CLASS_NAME.get(card.suits[0], "") if card.suits else ""
    if card.has("twofive"):
        what = ("A 2/5 of the %s class: it counts as a 2 or a 5, declared when it enters play, so it can join a "
                "set of 2s or of 5s." % cls)
    elif card.has("choosable"):
        what = ("A Wild Animal: an animal companion (an ace) that declares one of the four basic classes when it "
                "enters play and has that class while it is in play.")
    elif card.is_jester:
        what = "A Jester for the reserve deck."
    elif not card.suits:
        what = "A %s with no class: it attacks for %d but has no class power." % (card.rank, card.value)
    else:
        what = "A %s of the %s class." % (card.rank, cls)
    cost = int(merc["cost"])
    stay = ("It joins the reserve deck for every attempt at this Evergreen setup." if evergreen else
            "It joins the reserve deck for every attempt until this mission is won, then goes back to the box.")
    return "%s\n\nCost: %d coin%s. %s" % (what, cost, "" if cost == 1 else "s", stay)


class MercenaryScreen(Screen):
    """The mercenary camp: every mercenary as a playing card, shaded while it waits in the
    box, its cost in bright gold coins down the right side; the hired ones are bright with
    the gold selection border. A tap opens the mercenary's card (``CardPopup``) to hire it,
    or, after a failure, to swap a hired one for another of the same cost. ``evergreen``:
    Evergreen boon 24's five coins for the drawn setup (no swaps). ``back``: where Back
    goes: the deck list (default), the game menu or the Evergreen screen."""

    swapping = None  # id of a hired mercenary being swapped, or None

    def __init__(self, app: "App", evergreen: bool = False, back: str = "deck", **kw) -> None:
        super().__init__(app, **kw)
        self.evergreen = evergreen
        self.back = back
        self.card_views: Dict[str, CardView] = {}

    def _scope(self) -> str:
        return "evergreen" if self.evergreen else "mission"

    def _go_back(self) -> None:
        app = self.app
        if self.back == "evergreen":
            app.show(EvergreenScreen(app))
        elif self.back == "menu":
            app.show(CampaignScreen(app))
        else:
            app.show(PartyScreen(app))

    def layout(self) -> None:
        if not hasattr(self, "app"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        app = self.app
        camp = app.campaign
        w, h = self.width, self.height
        m = T.MARGIN
        y = T.TOP_INSET
        tw = w - 2 * m
        self.add_subview(make_button("‹ Back", lambda s: self._go_back(), (m, y, 80, 36), False, 14))
        self.add_subview(make_label("Mercenary camp", (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 46
        self.card_views = {}
        if camp is None:
            return
        from regicide.campaign.mercenaries import MERCENARIES, by_id
        coins, hired = camp._purse(self._scope())
        offset = getattr(self, "scroll_offset", (0, 0))
        self.add_subview(make_label("Coins: %d" % coins, (m, y, tw, 24), 16, True, T.ACCENT))
        y += 26
        if self.evergreen:
            text = ("This Is Noble, Sir: five coins to spend on mercenaries for this Evergreen setup. "
                    "Tap a card to hire it.")
        else:
            text = ("Each failure earns coins equal to the losses on this mission. Hired mercenaries stay until the "
                    "mission is won; after a failure one may be swapped for another of the same cost. Tap a card.")
        info = fit_label(text, tw, 12, False, T.MUTED, ui.ALIGN_LEFT)
        info.frame = (m, y, tw, info.height)
        self.add_subview(info)
        y += info.height + 8
        candidates: List[str] = []
        if self.swapping is not None and self.swapping in hired and not self.evergreen:
            cur = by_id(self.swapping)
            candidates = [o["id"] for o in camp.swappable(self.swapping)]
            lab = fit_label("Swap %s: tap a mercenary of the same cost (gold border)." % cur["name"], tw - 96, 13, True,
                            T.OK, ui.ALIGN_LEFT)
            lab.frame = (m, y, tw - 96, max(36, lab.height))
            self.add_subview(lab)
            self.add_subview(make_button("Cancel", lambda s: self._cancel_swap(), (w - m - 86, y + 2, 86, 32), False, 13))
            y += max(36, lab.height) + 8
        else:
            self.swapping = None
        sv = ui.ScrollView(frame=(m, y, tw, h - y - T.BOTTOM_INSET))
        cols = 4
        gap = 8
        cw = (tw - gap * (cols - 1)) / cols
        ch = cw * 1.42
        for i, merc in enumerate(MERCENARIES):
            mid = str(merc["id"])
            r, col = divmod(i, cols)
            v = CardView(P.to_card(merc["card"]), on_tap=(lambda x: lambda view: self._tapped(x))(mid))
            v.frame = (col * (cw + gap), r * (ch + gap), cw, ch)
            v.coins = int(merc["cost"])
            v.shaded = mid not in hired
            # gold border: the hired mercenaries, or while swapping only the ones that can be taken
            v.selected = (mid in candidates) if self.swapping is not None else (mid in hired)
            if self.swapping is not None and mid != self.swapping and mid not in candidates:
                v.alpha = 0.4
            if mid == self.swapping:
                v.badge = "swap"
            sv.add_subview(v)
            self.card_views[mid] = v
        rows = (len(MERCENARIES) + cols - 1) // cols
        content_h = rows * (ch + gap) + 20
        sv.content_size = (tw, content_h)
        # a hire or a swap rebuilds the grid: keep the cards where they were on screen
        sv.content_offset = (0, max(0.0, min(float(offset[1]), content_h - sv.height)))
        self.grid = sv
        self.add_subview(sv)

    def _tapped(self, mid: str) -> None:
        """A mercenary's card: what it is, then Hire (in the box), Swap (hired, after a
        failure) or Take (the one a hired mercenary is being swapped for)."""
        from regicide.campaign.mercenaries import by_id
        camp = self.app.campaign
        if camp is None:
            return
        coins, hired = camp._purse(self._scope())
        merc = by_id(mid)
        card = P.to_card(merc["card"])
        icon, corner = mercenary_icon(card)
        from .widgets import card_color
        edge = card_color(card)          # the card's own colour (a Wild Animal's is neutral)
        cost = int(merc["cost"])
        text = mercenary_text(merc, card, self.evergreen)
        close = lambda s: popup.close()  # noqa: E731
        if self.swapping is not None:
            if mid == self.swapping:
                self._cancel_swap()
                return
            if mid not in [o["id"] for o in camp.swappable(self.swapping)]:
                import console
                console.hud_alert("Swap for a mercenary of the same cost that is still in the box.", "error")
                return
            old = by_id(self.swapping)
            buttons = [("Take it in place of %s" % old["name"], lambda s: self._swap(mid), True), ("Cancel", close, False)]
            subtitle = "Swap · free, same cost"
        elif mid in hired:
            buttons = []
            if not self.evergreen and camp.swappable(mid):
                buttons.append(("Swap", lambda s: self._begin_swap(mid), True))
            buttons.append(("Close", close, False))
            subtitle = "Hired" if self.evergreen else "Hired · until mission %d is won" % camp.mission
        else:
            afford = coins >= cost
            buttons = [("Hire for %d coin%s" % (cost, "" if cost == 1 else "s"), lambda s: self._hire(mid), True, afford),
                       ("Close", close, False)]
            subtitle = "In the box" if afford else "In the box · not enough coins (%d)" % coins
        popup = CardPopup(str(merc["name"]), text, buttons, icon=icon, edge=edge, corner=corner, subtitle=subtitle,
                          dismissable=True)
        show_card_popup(self, popup)

    def _keep_scroll(self) -> None:
        """Remember the grid's scroll position before the screen is rebuilt."""
        grid = getattr(self, "grid", None)
        if grid is not None:
            self.scroll_offset = tuple(grid.content_offset)

    def _hire(self, mid: str) -> None:
        self._keep_scroll()
        try:
            self.app.campaign.hire(mid, self._scope())
        except ValueError as e:
            import console
            console.hud_alert(str(e), "error")
            return
        self.app.save_campaign()
        self.layout()

    def _begin_swap(self, mid: str) -> None:
        self._keep_scroll()
        self.swapping = mid
        self.layout()

    def _cancel_swap(self) -> None:
        self._keep_scroll()
        self.swapping = None
        self.layout()

    def _swap(self, new_id: str) -> None:
        self._keep_scroll()
        try:
            self.app.campaign.swap(self.swapping, new_id)
        except ValueError as e:
            import console
            console.hud_alert(str(e), "error")
            return
        self.swapping = None
        self.app.save_campaign()
        self.layout()


class EvergreenScreen(Screen):
    """Pack E, Evergreen mode: draw a generated mission (one location, banes and boons),
    read its cards, hire boon 24's mercenaries, start or continue an attempt."""

    TIER_LABEL = {"grey": "grey, setup", "yellow": "yellow, rule change", "red": "red, ongoing"}

    def layout(self) -> None:
        if not hasattr(self, "app"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        app = self.app
        camp = app.campaign
        w, h = self.width, self.height
        m = T.MARGIN
        y = T.TOP_INSET
        self.add_subview(make_button("‹ Back", lambda s: app.show(CampaignScreen(app)), (m, y, 80, 36), False, 14))
        self.add_subview(make_label("Evergreen mission", (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 46
        if camp is None or not camp.finished:
            self.add_subview(make_label("Evergreen mode opens when the campaign is complete.", (m, y, w - 2 * m, 30), 14, False, T.MUTED))
            return
        record = camp.evergreen or {}
        setup = camp.evergreen_setup()
        in_progress = store.has_attempt(camp.slot)
        bw = min(320, w - 2 * m)
        x = (w - bw) / 2
        if in_progress:
            self.add_subview(make_button("Continue attempt", lambda s: app.resume_attempt(), (x, y, bw, 46)))
            y += 54
        elif setup is not None:
            attempt = int(record.get("attempts", 0)) + 1
            title = "Start" if attempt == 1 else "Retry this setup (attempt %d)" % attempt
            self.add_subview(make_button(title, lambda s: app.start_evergreen_attempt(), (x, y, bw, 46)))
            y += 54
        if not in_progress:
            # the two variants of the rules card, applied to the next draw
            options = record.get("options") or {}
            for key, label in (("extra_red", "Swap a grey bane for a second red bane"), ("extra_bane", "Add another bane")):
                self.add_subview(make_label(label, (m, y + 4, w - 2 * m - 60, 24), 13, False, T.TEXT))
                sw = ui.Switch(frame=(w - m - 51, y, 51, 31))
                sw.value = bool(options.get(key, False))
                sw.action = (lambda k: lambda s: self._set_option(k, s.value))(key)
                self.add_subview(sw)
                y += 36
            draw_title = "Redraw" if setup is not None else "New Evergreen mission"
            self.add_subview(make_button(draw_title, lambda s: self._draw(), (x, y, bw, 44), setup is None))
            y += 52
            if setup is not None and any(b["n"] == 24 for b in setup["boons"]):
                coins = int(record.get("coins", 0))
                self.add_subview(make_button("Mercenaries (%d coin%s left)" % (coins, "" if coins == 1 else "s"),
                                             lambda s: app.show(MercenaryScreen(app, evergreen=True, back="evergreen")),
                                             (x, y, bw, 44), False))
                y += 52
        if setup is None:
            self.add_subview(make_label("Draw a mission: one location, two grey banes (or one grey and a second red), "
                                        "one yellow and one red bane, one grey and one yellow boon. The enemies are the "
                                        "Phase II and Phase III experiments.", (m, y, w - 2 * m, 72), 13, False, T.MUTED, lines=4))
            return
        stats = "This setup: %d attempt%s, %d lost" % (int(record.get("attempts", 0)), "" if int(record.get("attempts", 0)) == 1 else "s",
                                                       int(record.get("losses", 0)))
        self.add_subview(make_label(stats, (m, y, w - 2 * m, 20), 12, False, T.MUTED))
        y += 24
        sv = ui.ScrollView(frame=(m, y, w - 2 * m, h - y - T.BOTTOM_INSET))
        yy = 0
        tw = w - 2 * m - 8
        loc = setup["location"]
        yy = self._card_block(sv, yy, tw, "Location %s: the %s" % (loc["id"], loc["name"]), self._location_text(loc), T.ACCENT)
        for b in setup["banes"]:
            yy = self._card_block(sv, yy, tw, "Bane %d: %s (%s)" % (b["n"], b["name"], self.TIER_LABEL.get(b["tier"], b["tier"])), b["text"], T.DANGER)
        for b in setup["boons"]:
            yy = self._card_block(sv, yy, tw, "Boon %d: %s (%s)" % (b["n"], b["name"], self.TIER_LABEL.get(b["tier"], b["tier"])), b["text"], T.OK)
        sv.content_size = (w - 2 * m, yy + 20)
        self.add_subview(sv)

    @staticmethod
    def _location_text(loc: dict) -> str:
        bits = []
        for key, label in (("setup", "Setup"), ("start_of_turn", "Start of turn"), ("end_of_turn", "End of turn"),
                           ("special", "Special"), ("defeated", "Enemy defeated")):
            if loc.get(key):
                bits.append("%s: %s" % (label, loc[key]))
        return " ".join(bits)

    def _card_block(self, sv: ui.ScrollView, yy: float, tw: float, title: str, text: str, color: str) -> float:
        sv.add_subview(make_label(title, (4, yy, tw, 22), 14, True, color))
        yy += 22
        _, th = ui.measure_string(text, tw - 4, (T.FONT, 12))
        sv.add_subview(make_label(text, (4, yy, tw, th + 6), 12, False, T.TEXT, ui.ALIGN_LEFT, 0))
        return yy + th + 14

    def _set_option(self, key: str, value: bool) -> None:
        self.app.campaign.set_evergreen_option(key, bool(value))
        self.app.save_campaign()

    def _draw(self) -> None:
        self.app.campaign.draw_evergreen()
        self.app.save_campaign()
        self.layout()


class ChoiceScreen(Screen):
    """Resolve a pending reward choice: pick one party card (corruption) or assign one
    class sticker to each revealed card (mission 2's class stickers)."""

    chosen = None       # choice_corrupt: the picked card id
    assign = None       # choice_classes: {card id: class}

    def layout(self) -> None:
        if not hasattr(self, "app"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        app = self.app
        camp = app.campaign
        w, h = self.width, self.height
        m = T.MARGIN
        y = T.TOP_INSET
        self.add_subview(make_button("‹ Back", lambda s: app.show(CampaignScreen(app)), (m, y, 80, 36), False, 14))
        step = camp.pending_choice() if camp is not None else None
        heading = "Mission setup" if step is not None and step.get("phase") == "setup" else "Reward"
        self.add_subview(make_label(heading, (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 48
        if step is None:
            self.add_subview(make_label("Nothing to choose.", (m, y, w - 2 * m, 30), 14, False, T.MUTED))
            return
        self.add_subview(make_label(step.get("label", ""), (m, y, w - 2 * m, 44), 15, True, T.ACCENT, lines=2))
        y += 48
        self.confirm_btn = make_button("Confirm", lambda s: self._confirm(), (m, h - T.BOTTOM_INSET - 50, w - 2 * m, 46))
        if step["kind"] == "choice_classes":
            self._layout_classes(step, y)
        elif step["kind"] == "choice_mage_student":
            self._layout_options(step, y, {"4": "The 4s", "8": "The 8s"})
        else:
            self._layout_pick(step, y)
        self.add_subview(self.confirm_btn)

    # -- pick one option from a short list ----------------------------------
    def _layout_options(self, step: dict, y: float, titles: dict) -> None:
        w = self.width
        m = T.MARGIN
        self.add_subview(make_label("The first unstickered card of the chosen strength revealed from the shuffled party "
                                    "gains the Mage class (never Gøran or a mage).", (m, y, w - 2 * m, 56), 12, False, T.MUTED, lines=3))
        y += 60
        options = [str(o) for o in step.get("options", [])]
        for o in options:
            b = make_button(titles.get(o, o), (lambda opt: lambda s: self._pick_option(opt))(o), (m, y, w - 2 * m, 44), self.chosen == o)
            self.add_subview(b)
            y += 52
        set_enabled(self.confirm_btn, self.chosen in options)

    def _pick_option(self, opt: str) -> None:
        self.chosen = opt
        self.layout()

    # -- pick one card ------------------------------------------------------
    def _layout_pick(self, step: dict, y: float) -> None:
        camp = self.app.campaign
        w, h = self.width, self.height
        m = T.MARGIN
        hint = {"choice_corrupt": "Tap the character who takes the corruption. Corrupted cards banish the top "
                                  "card of the reserve when played and their own class ignores immunity.",
                "choice_suit": "Tap the character who gets the %s sticker. The card keeps its own class and "
                               "gains this one too." % CLASS_NAME.get(str(step.get("suit", "")), "class"),
                "choice_rip": "Tap the corrupted character who wears a cloak of the Eternal Vine. The card is "
                              "torn up and leaves the campaign for good."}.get(step["kind"], "")
        if hint:
            self.add_subview(make_label(hint, (m, y, w - 2 * m, 56), 12, False, T.MUTED, lines=3))
            y += 60
        options = list(step.get("options") or [])
        from .widgets import CardView
        set_enabled(self.confirm_btn, self.chosen in options)
        sv = ui.ScrollView(frame=(m, y, w - 2 * m, h - y - T.BOTTOM_INSET - 60))
        cols = 5
        gap = 6
        cw = (w - 2 * m - gap * (cols - 1)) / cols
        ch = cw * 1.42
        self._views = []
        for i, cid in enumerate(options):
            d = P.find(camp.party, cid)
            if d is None:
                continue
            r, col = divmod(i, cols)
            v = CardView(P.to_card(d), on_tap=self._pick)
            v.small = True
            v.selected = cid == self.chosen
            v.frame = (col * (cw + gap), r * (ch + gap), cw, ch)
            sv.add_subview(v)
            self._views.append(v)
        rows = (len(options) + cols - 1) // cols
        sv.content_size = (w - 2 * m, rows * (ch + gap) + 20)
        self.add_subview(sv)
        if not options:
            self.add_subview(make_label("No character qualifies; confirm to skip.", (m, y, w - 2 * m, 30), 13, False, T.MUTED))
            set_enabled(self.confirm_btn, True)

    def _pick(self, view) -> None:
        self.chosen = view.card.id
        for v in self._views:
            v.selected = v.card.id == self.chosen
            v.set_needs_display()
        set_enabled(self.confirm_btn, True)

    # -- assign one class sticker per card ----------------------------------
    def _layout_classes(self, step: dict, y: float) -> None:
        camp = self.app.campaign
        w, h = self.width, self.height
        m = T.MARGIN
        cards = [str(c) for c in step.get("cards", [])]
        classes = [str(c) for c in step.get("classes", [])]
        if self.assign is None:
            self.assign = {}
        self.add_subview(make_label("Give each revealed card one sticker. Each class is used once and a card "
                                    "never gets a class it already has.", (m, y, w - 2 * m, 40), 12, False, T.MUTED, lines=2))
        y += 46
        from .widgets import CardView
        row_h = 92
        cw = row_h / 1.42
        bw = (w - 2 * m - cw - 8 - 6 * (len(classes) - 1)) / max(1, len(classes))
        used = {v: k for k, v in self.assign.items()}
        for cid in cards:
            d = P.find(camp.party, cid)
            if d is None:
                continue
            v = CardView(P.to_card(d))
            v.small = True
            v.touch_enabled = False
            v.frame = (m, y, cw, row_h)
            self.add_subview(v)
            x = m + cw + 8
            for s in classes:
                picked = self.assign.get(cid) == s
                b = make_button(CLASS_NAME[s], (lambda c, k: lambda btn: self._set_class(c, k))(cid, s),
                                (x, y + (row_h - 40) / 2, bw, 40), picked, 12)
                blocked = s in d.get("suits", []) or (s in used and used[s] != cid)
                set_enabled(b, not blocked)
                self.add_subview(b)
                x += bw + 6
            y += row_h + 10
        complete = len(cards) > 0 and all(c in self.assign for c in cards)
        set_enabled(self.confirm_btn, complete or not cards)

    def _set_class(self, cid: str, s: str) -> None:
        if self.assign.get(cid) == s:
            del self.assign[cid]
        else:
            self.assign[cid] = s
        self.layout()

    # -- confirm ---------------------------------------------------------------
    def _confirm(self) -> None:
        camp = self.app.campaign
        step = camp.pending_choice()
        if step is None:
            self.app.show(CampaignScreen(self.app))
            return
        try:
            if step["kind"] == "choice_classes":
                if step.get("cards"):
                    camp.resolve_choice(dict(self.assign or {}))
                else:
                    camp.pending.pop(0)
                    camp.log.append("%s: no card qualified." % step.get("label", "reward"))
            elif step.get("options"):
                camp.resolve_choice(self.chosen)  # one card id, or "4" / "8" for the mage student
            else:
                camp.pending.pop(0)
                camp.log.append("%s: nothing qualified." % step.get("label", "reward"))
        except ValueError as e:
            import console
            console.hud_alert(str(e), "error")
            return
        self.app.save_campaign()
        self.app.show(CampaignScreen(self.app))


class PartyScreen(Screen):
    """The deck list: the relics (a row of cards; a tap opens the relic's card), the
    mercenaries hired and the mercenary camp, Gøran's beasts (all four; a tap chooses the
    one the next attempt takes, shown with the gold selection border), then the party."""

    def layout(self) -> None:
        if not hasattr(self, "app"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        app = self.app
        camp = app.campaign
        w, h = self.width, self.height
        m = T.MARGIN
        y = T.TOP_INSET
        self.add_subview(make_button("‹ Back", lambda s: app.show(CampaignScreen(app)), (m, y, 80, 36), False, 14))
        self.add_subview(make_label("Deck list", (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 48
        self.beast_views: Dict[str, CardView] = {}
        self.beast_note: Optional[ui.Label] = None
        if camp is None:
            return
        from .widgets import RelicCard
        from regicide.campaign.mercenaries import by_id as merc_by_id
        from regicide.campaign import missions as M
        in_progress = store.has_attempt(camp.slot)
        sv = ui.ScrollView(frame=(m, y, w - 2 * m, h - y - T.BOTTOM_INSET))
        tw = w - 2 * m
        cols = 5
        gap = 6
        cw = (tw - gap * (cols - 1)) / cols
        ch = cw * 1.42
        yy = 0.0

        def heading(text: str, yy: float) -> float:
            sv.add_subview(make_label(text, (0, yy, tw, 22), 15, True, T.ACCENT))
            return yy + 26

        def note(text: str, yy: float) -> float:
            lab = fit_label(text, tw, 12, False, T.MUTED, ui.ALIGN_LEFT)
            lab.frame = (0, yy, tw, lab.height)
            sv.add_subview(lab)
            return yy + lab.height + 6

        def card_row(cards, yy: float, on_tap=None, views: Optional[List[CardView]] = None) -> float:
            for i, c in enumerate(cards):
                r, col = divmod(i, cols)
                v = CardView(c, on_tap=on_tap)
                v.small = True
                v.touch_enabled = on_tap is not None
                v.frame = (col * (cw + gap), yy + r * (ch + gap), cw, ch)
                sv.add_subview(v)
                if views is not None:
                    views.append(v)
            rows = (len(cards) + cols - 1) // cols
            return yy + rows * (ch + gap) + 8

        # relics: a row of cards; a tap shows what the relic does
        relics = [r for r in camp.relics if relic_text(r, camp.players)]
        if relics:
            yy = heading("Relics", yy)
            for i, r in enumerate(relics):
                row, col = divmod(i, cols)
                tile = RelicCard(r, on_tap=lambda v: self._show_relic(v.relic_id),
                                 frame=(col * (cw + gap), yy + row * (ch + gap), cw, ch))
                sv.add_subview(tile)
            yy += ((len(relics) + cols - 1) // cols) * (ch + gap) + 8
        # mercenaries: the ones hired (they leave when the mission is won) and the camp
        bw = min(320, tw)
        if camp.finished:
            setup = camp.evergreen_setup()
            mercs = list((camp.evergreen or {}).get("mercenaries", []))
            boon24 = setup is not None and any(int(b["n"]) == 24 for b in setup.get("boons", []))
            if mercs or boon24:
                yy = heading("Mercenaries · this Evergreen setup", yy)
                if mercs:
                    yy = card_row([P.to_card(merc_by_id(mid)["card"]) for mid in mercs], yy)
                if boon24:
                    coins = int((camp.evergreen or {}).get("coins", 0))
                    title = ("Mercenaries (%d coin%s left)" % (coins, "" if coins == 1 else "s") if not in_progress
                             else "Mercenaries (after this attempt)")
                    b = make_button(title, lambda s: app.show(MercenaryScreen(app, evergreen=True)),
                                    ((tw - bw) / 2, yy, bw, 44), False)
                    fit_title(b)
                    set_enabled(b, not in_progress, False)
                    sv.add_subview(b)
                    yy += 52
        elif camp.m_box_opened or camp.mercenaries:
            mercs = list(camp.mercenaries)
            yy = heading("Mercenaries · until mission %d is won" % camp.mission if mercs else "Mercenaries", yy)
            if mercs:
                yy = card_row([P.to_card(merc_by_id(mid)["card"]) for mid in mercs], yy)
            if camp.m_box_opened:
                title = ("Mercenary camp (%d coin%s)" % (camp.coins, "" if camp.coins == 1 else "s") if not in_progress
                         else "Mercenary camp (after this attempt)")
                b = make_button(title, lambda s: app.show(MercenaryScreen(app)), ((tw - bw) / 2, yy, bw, 44), False)
                fit_title(b)
                set_enabled(b, not in_progress, False)
                sv.add_subview(b)
                yy += 52
        # Gøran's beasts: all four on display. Rulebook p.7: each attempt may take one of
        # them (a tap chooses it, a tap on the chosen one goes without); mission 11 makes
        # its beast deck of all four and Evergreen boon 26 brings all four.
        if camp.flags.get("beasts"):
            setup = camp.evergreen_setup() if camp.finished else None
            beast_cards = [P.to_card(b) for b in M.BEASTS]
            shown: List[CardView] = []
            if setup is not None and any(int(b["n"]) == 26 for b in setup.get("boons", [])):
                yy = heading("Gøran's beasts · all four join this setup", yy)
                yy = card_row(beast_cards, yy, views=shown)
                for v in shown:
                    v.selected = True
            elif not camp.finished and camp.mission == 11:
                yy = heading("Gøran's beasts · mission 11's beast deck", yy)
                yy = card_row(beast_cards, yy)
                yy = note("All four form the beast deck this mission; none joins the reserve.", yy)
            else:
                yy = heading("Gøran's beast · %s attempt" % ("this" if in_progress else "next"), yy)
                yy = card_row(beast_cards, yy, None if in_progress else (lambda v: self._toggle_beast(v.card.id)), shown)
                for v in shown:
                    v.selected = v.card.id == camp.beast
                    self.beast_views[v.card.id] = v
                # sized for its longest text: a tap changes it in place, nothing below moves
                tallest = max(text_size(t, tw, 12)[1] for t in self._beast_texts(in_progress))
                self.beast_note = fit_label(self._beast_text(in_progress), tw, 12, False, T.MUTED, ui.ALIGN_LEFT,
                                            float(tallest) + 4)
                self.beast_note.frame = (0, yy, tw, self.beast_note.height)
                sv.add_subview(self.beast_note)
                yy += self.beast_note.height + 6
        cards = sorted(camp.party_cards(), key=deck_list_key)
        yy = heading("Party · %d cards" % len(cards), yy)
        yy = card_row(cards, yy)
        sv.content_size = (tw, yy + 20)
        self.add_subview(sv)

    def _beast_texts(self, in_progress: bool) -> List[str]:
        """Every text the beast note can show (with each beast chosen, and with none)."""
        from regicide.campaign import missions as M
        return [self._beast_text(in_progress, b["id"]) for b in M.BEASTS] + [self._beast_text(in_progress, "")]

    def _beast_text(self, in_progress: bool, beast_id: Optional[str] = None) -> str:
        from regicide.campaign import missions as M
        camp = self.app.campaign
        bid = camp.beast if beast_id is None else beast_id
        beast = M.beast_by_id(bid) if bid else None
        chosen = P.to_card(dict(beast)).label() if beast is not None else ""
        if in_progress:
            return ("%s is in this attempt's reserve; change it after the attempt." % chosen if chosen
                    else "No beast in this attempt; choose one after the attempt.")
        return ("%s joins the next attempt. Tap another to swap, or tap it again to go without." % chosen if chosen
                else "No beast for the next attempt. Tap one to take it.")

    def _toggle_beast(self, beast_id: str) -> None:
        """Choose (or, tapped again, drop) the beast the next attempt takes; the cards show
        the choice with the gold selection border."""
        camp = self.app.campaign
        if camp is None or store.has_attempt(camp.slot):
            return
        camp.set_beast(None if camp.beast == beast_id else beast_id)
        self.app.save_campaign()
        for bid, v in self.beast_views.items():
            v.selected = bid == camp.beast
            v.set_needs_display()
        if self.beast_note is not None:
            self.beast_note.text = self._beast_text(False)

    def _show_relic(self, relic_id: str) -> None:
        """The relic's card: its icon and name on top, what it does below (the side for
        this number of players)."""
        from regicide.campaign.relics import RELICS
        camp = self.app.campaign
        r = RELICS.get(relic_id, {})
        color = str(r.get("color", T.ACCENT))
        side = "solo side" if camp.players == 1 else "side for two or more players"
        popup = CardPopup(relic_name(relic_id), relic_text(relic_id, camp.players),
                          [("Close", lambda s: popup.close(), False)],
                          icon=[(str(r.get("symbol", "?")), color)], edge=color, subtitle="Relic · %s" % side,
                          dismissable=True)
        show_card_popup(self, popup)


# ============================================================================ descriptions
def describe_preview(g: Game, pv: dict) -> str:
    parts: List[str] = []
    for suit, ev in pv["powers"].items():
        sym = SUIT_SYMBOL.get(suit, suit)
        if ev.get("immune"):
            parts.append("%s immune" % sym)
        elif suit == "H":
            parts.append("%s heal %d" % (sym, ev.get("healed", 0)))
        elif suit == "D":
            parts.append("%s draw %d" % (sym, len(ev.get("drawn", []))))
        elif suit == "C":
            parts.append("%s double" % sym)
        elif suit == "S":
            parts.append("%s shield +%d" % (sym, ev.get("shield", 0)))
        elif suit == "R":
            parts.append("%s +%d then double" % (sym, ev.get("added", 0)))
        elif suit == "G":
            parts.append("%s no damage this turn" % sym)
        elif suit == "U":
            parts.append("%s sort the discard pile" % sym)
        elif suit == "T":
            parts.append("%s everyone draws" % sym)
    s = "%d damage" % pv["damage"]
    if pv["defeats"]:
        tail = ""
        if pv["exact"]:
            legacy = bool(getattr(g.rules, "legacy", False))
            to_deck = g.enemy is not None and g.rules.defeat_plan(g, True).get("enemy_to") == "tavern_top"
            tail = " exactly!" + (" (goes to the %s)" % ("reserve" if legacy else "tavern") if to_deck else "")
        s += " — defeats it%s" % tail
    else:
        s += " (%d left), then suffer %d" % (pv["enemy_hp_after"], pv["enemy_attack_after"])
    if parts:
        s = ", ".join(parts) + ". " + s
    # Forecasts assume nobody adds anything: not the other players (Kinfolk Flute, Azure
    # Emblem) and not the mage, whose revealed cards stay secret until the play is made.
    prefix = ""
    if pv.get("decision_kind") == "flute_add":
        prefix = "If nobody adds (Kinfolk Flute): "
    elif pv.get("decision_kind") == "emblem_place":
        prefix = "Azure Emblem: the others may place cards on the reserve first. "
    elif pv.get("decision_kind") == "whistle_take":
        prefix = "Scarlet Whistle: you may add the top discard first. If not: "
    elif pv.get("decision_kind") == "whistle_add":
        prefix = "Scarlet Whistle: another player may add a card. If nobody does: "
    elif pv.get("decision_kind") == "reaver_count":
        prefix = "Reaver: reveal reserve cards and add one's strength (counted as 0 here). "
    elif pv.get("decision_kind") == "druid_assign":
        prefix = "Druid: the discard pile is dealt out and sorted first. "
    elif pv.get("decision_kind") == "chanter_declare":
        prefix = "Chanter: declare how many cards everyone draws (0 here). "
    elif pv.get("decision_kind") == "mother_choice":
        prefix = "Evergreen Mother: banish from the discard pile or the reserve first. "
    elif pv.get("decision_kind") == "mother_banish":
        prefix = "Evergreen Mother: another player banishes a card from hand first. "
    elif pv.get("decision_kind") == "pilgrim_banish":
        prefix = "A pilgrim of the same strength may be banished first. "
    elif pv.get("decision_kind") == "attack_discard":
        prefix = "Eye-Level Sticks: discard a hand card first (the weakest here). "
    elif pv.get("decision_kind") == "zone_sibling":
        prefix = "Squad of Siblings: you may move a matching zone card to the discard pile first. "
    elif pv.get("decision_kind") == "declare_class":
        prefix = "Wild Animal: you declare its class (a warrior here). "
    elif pv.get("decision_kind") == "declare_value":
        prefix = "2/5: you declare 2 or 5 (5 here). "
    peeks = pv.get("mage_peeks") or []
    if peeks:
        n = int(peeks[0])
        if n:
            prefix += "The mage reveals %d card%s from the reserve. If nothing is added: " % (n, "" if n == 1 else "s")
        else:
            prefix += "The reserve deck is empty, the mage has nothing to reveal. "
    return prefix + s


def describe_events(g: Game) -> str:
    parts: List[str] = []
    for ev in g.last_events:
        t = ev["t"]
        if t == "power":
            sym = SUIT_SYMBOL.get(ev["suit"], ev["suit"])
            if ev.get("immune"):
                parts.append("%s immune" % sym)
            elif "healed" in ev:
                parts.append("%s healed %d" % (sym, ev["healed"]))
            elif "drawn" in ev:
                parts.append("%s drew %d" % (sym, len(ev["drawn"])))
            elif ev["suit"] == "R" and ev.get("doubled"):
                parts.append("%s +%d, doubled" % (sym, int(ev.get("added", 0))))
            elif ev.get("doubled"):
                parts.append("%s doubled" % sym)
            elif "shield" in ev:
                parts.append("%s shield +%d" % (sym, ev["shield"]))
            elif ev["suit"] == "G":
                parts.append("%s no damage this turn" % sym)
        elif t == "damage":
            parts.append("%d damage" % ev["amount"])
        elif t == "carry_damage":
            parts.append("%d carry-over damage to the next enemy." % ev["amount"])
        elif t == "defeat":
            plan = ev.get("plan") or {}
            if ev["exact"] and plan.get("enemy_to") == "tavern_top":
                parts.append("Exact kill! Enemy to the tavern.")
            elif ev["exact"]:
                parts.append("Exact kill!")
            else:
                parts.append("Enemy defeated!")
        elif t == "reveal":
            parts.append("%s appears." % ev["enemy"]["name"])
        elif t == "jester":
            parts.append("Jester cancels the immunity.")
        elif t == "yield":
            parts.append("Yielded.")
        elif t == "solo_jester":
            parts.append("Jester power: new hand (%d left)." % ev["remaining"])
        elif t == "suffer":
            parts.append("Discarded %d to suffer %d." % (ev["paid"], ev["damage"]))
        elif t == "no_damage":
            parts.append("Guardian: no damage this turn." if ev.get("guardian") else "No damage to suffer.")
        elif t == "decide" and ev.get("kind") == "flute_add":
            parts.append("Kinfolk Flute: %s may add %ss." % (g.players[int(ev["player"])].name, ev.get("strength")))
        elif t == "add_to_play" and ev.get("source") != "mage":
            parts.append("%s adds %s (attack %d)." % (
                g.players[int(ev["player"])].name, " + ".join(g.card(c).label() for c in ev["cards"]), ev["value"]))
        elif t == "flute_pass":
            parts.append("%s adds nothing." % g.players[int(ev["player"])].name)
        elif t == "mage_peek":
            n = int(ev.get("count", 0))
            if n:
                parts.append("Mage: %s looks at %d card%s from the reserve." % (
                    g.players[int(ev["player"])].name, n, "" if n == 1 else "s"))
            else:
                parts.append("Mage: the reserve deck is empty.")
        elif t == "mage_pick":
            parts.append("%s adds %s to the attack (Mage, strength %d)." % (
                g.players[int(ev["player"])].name, g.card(ev["card"]).label(), int(ev["value"])))
            if ev.get("discarded"):
                parts.append("%s to the discard pile." % " + ".join(g.card(c).label() for c in ev["discarded"]))
        elif t == "mage_skip":
            if ev.get("discarded"):
                parts.append("Mage: nothing may join the attack; %s to the discard pile." % (
                    " + ".join(g.card(c).label() for c in ev["discarded"])))
            else:
                parts.append("Mage: nothing to add.")
        elif t == "decide" and ev.get("kind") == "emblem_keep":
            parts.append("Azure Emblem: keep one of the other revealed cards on top of the reserve?")
        elif t == "emblem_keep":
            parts.append("Azure Emblem: %s goes back on top of the reserve." % g.card(ev["card"]).label())
            if ev.get("discarded"):
                parts.append("%s to the discard pile." % " + ".join(g.card(c).label() for c in ev["discarded"]))
        elif t == "emblem_skip":
            parts.append("Azure Emblem: nothing kept%s." % (
                "; %s to the discard pile" % " + ".join(g.card(c).label() for c in ev["discarded"]) if ev.get("discarded") else ""))
        elif t == "decide" and ev.get("kind") == "emblem_place":
            parts.append("Azure Emblem: %s may place a card on the reserve." % g.players[int(ev["player"])].name)
        elif t == "emblem_place":
            parts.append("%s places a card on top of the reserve (Azure Emblem)." % g.players[int(ev["player"])].name)
        elif t == "emblem_pass":
            parts.append("%s places nothing." % g.players[int(ev["player"])].name)
        elif t == "zone_add":
            parts.append("%s goes into the mission zone." % g.card(ev["card"]).label())
        elif t == "decide" and ev.get("kind") == "zone_rescue":
            parts.append("Exact kill: choose a mission zone card to rescue.")
        elif t == "zone_rescue":
            parts.append("%s rescued to the discard pile." % g.card(ev["card"]).label())
        elif t == "zone_cleared":
            where = {"banish": "banished", "banish_shuffle": "shuffled into the banished pile"}.get(str(ev.get("to")), "discarded")
            parts.append("Mission zone %s (%d card%s)." % (where, len(ev["cards"]), "" if len(ev["cards"]) == 1 else "s"))
        elif t == "decide" and ev.get("kind") == "whistle_take":
            parts.append("Scarlet Whistle: add %s from the discard pile?" % g.card(ev["card"]).label())
        elif t == "decide" and ev.get("kind") == "whistle_add":
            parts.append("Scarlet Whistle: %s may add a card." % g.players[int(ev["player"])].name)
        elif t == "whistle_take":
            parts.append("%s adds %s from the discard pile (Scarlet Whistle, attack %d)." % (
                g.players[int(ev["player"])].name, g.card(ev["card"]).label(), int(ev["value"])))
        elif t == "whistle_skip":
            parts.append("Scarlet Whistle: nothing taken.")
        elif t == "whistle_pass":
            parts.append("%s adds nothing." % g.players[int(ev["player"])].name)
        elif t == "decide" and ev.get("kind") == "reaver_count":
            parts.append("Reaver: how many cards to reveal?")
        elif t == "reaver_reveal":
            parts.append("Reaver: %s revealed." % " + ".join(g.card(c).label() for c in ev["revealed"]))
        elif t == "reaver_pick":
            parts.append("Reaver: +%d from %s, damage doubled to %d; %s banished." % (
                int(ev["added"]), g.card(ev["card"]).label(), int(ev["damage"]),
                " + ".join(g.card(c).label() for c in ev["banished"])))
        elif t == "decide" and ev.get("kind") == "discard_order":
            parts.append("What order? The other revealed cards go to the discard pile.")
        elif t == "discard_order":
            parts.append("%s to the discard pile, %s on top." % (
                " + ".join(g.card(c).label() for c in ev["cards"]), g.card(ev["cards"][-1]).label()))
        elif t == "decide" and ev.get("kind") == "reaver_order":
            parts.append("What order? The revealed cards are banished.")
        elif t == "reaver_order":
            parts.append("%s on top of the banished pile." % g.card(ev["cards"][-1]).label())
        elif t == "decide" and ev.get("kind") in ("played_discard_order", "played_banish_order"):
            parts.append("What order? The played cards go to the %s pile." % (
                "discard" if ev["kind"] == "played_discard_order" else "banished"))
        elif t == "cleanup_order":
            parts.append("%s ends on top of the %s pile." % (g.card(ev["cards"][-1]).label(), ev.get("pile", "discard")))
        # the answers to the top-card questions of games saved before the order questions
        elif t == "cleanup_top":
            parts.append("%s on top of the discard pile." % g.card(ev["card"]).label())
        elif t == "discard_top":
            parts.append("%s to the discard pile, %s on top." % (
                " + ".join(g.card(c).label() for c in ev.get("discarded", [])), g.card(ev["card"]).label()))
        elif t == "banish_top":
            parts.append("%s on top of the banished pile." % g.card(ev["card"]).label())
        elif t == "decide" and ev.get("kind") == "declare_class":
            parts.append("%s: declare a class for %s." % (g.players[int(ev["player"])].name, g.card(ev["card"]).label()))
        elif t == "decide" and ev.get("kind") == "declare_value":
            parts.append("%s: declare 2 or 5 for %s." % (g.players[int(ev["player"])].name,
                                                          " + ".join(g.card(c).label() for c in ev.get("cards") or [ev["card"]])))
        elif t == "declare":
            if ev.get("suit"):
                parts.append("%s is a %s while in play." % (g.card(ev["card"]).label(), CLASS_NAME.get(str(ev["suit"]), ev["suit"])))
            else:
                parts.append("%s counts %d while in play." % (g.card(ev["card"]).label(), int(ev.get("value", 0))))
        elif t == "decide" and ev.get("kind") == "zone_move":
            parts.append("Choose a card in play to move to the mission zone.")
        elif t == "zone_move":
            parts.append("%s moves to the mission zone." % g.card(ev["card"]).label())
        elif t == "team_damage":
            parts.append("Myla deals %d team damage." % int(ev["damage"]))
        elif t == "team_damage_prevented":
            parts.append("Guardian: Myla's %d team damage is prevented." % int(ev["damage"]))
        elif t == "team_discard":
            parts.append("%s discards %s (%d of %d)." % (
                g.players[int(ev["player"])].name, g.card(ev["card"]).label(), int(ev["paid"]), int(ev["damage"])))
        elif t == "team_damage_done":
            parts.append("Team damage satisfied.")
        elif t == "corrupt_banish":
            if ev.get("source") == "hand":
                parts.append("%s banishes %s from hand (Evergreen Mother)." % (
                    g.players[int(ev["player"])].name, g.card(ev["banished"]).label()))
            else:
                parts.append("%s is corrupted: %s banished from the %s." % (
                    g.card(ev["card"]).label(), g.card(ev["banished"]).label(), ev.get("source", "reserve deck")))
        elif t == "corrupt_banish_none":
            parts.append("%s is corrupted, but nothing is banished." % g.card(ev["card"]).label())
        elif t == "decide" and ev.get("kind") == "mother_choice":
            parts.append("Evergreen Mother: banish from the discard pile or the reserve?")
        elif t == "decide" and ev.get("kind") == "mother_banish":
            parts.append("Evergreen Mother: %s must banish a card from hand." % g.players[int(ev["player"])].name)
        elif t == "druid_deal":
            dealt = ev.get("dealt", [])
            parts.append("Druid: the discard pile is dealt out (%s)." % ", ".join(
                "%s %d" % (g.players[i].name, len(x)) for i, x in enumerate(dealt) if x))
        elif t == "decide" and ev.get("kind") == "druid_assign":
            parts.append("%s sorts the dealt cards." % g.players[int(ev["player"])].name)
        elif t == "druid_assign":
            bits = []
            for slot, word in (("banish", "banished"), ("hand", "to hand"), ("top", "on top of the reserve"), ("bottom", "under the reserve")):
                if ev.get(slot):
                    bits.append("%s %s" % (g.card(ev[slot]).label(), word))
            parts.append("Druid: %s: %s." % (g.players[int(ev["player"])].name, ", ".join(bits)))
        elif t == "druid_done":
            parts.append("%d card%s back to the discard pile, shuffled." % (int(ev["returned"]), "" if int(ev["returned"]) == 1 else "s"))
        elif t == "decide" and ev.get("kind") == "chanter_declare":
            parts.append("Chanter: declare how many cards everyone draws.")
        elif t == "chanter_declare":
            n = int(ev["count"])
            parts.append("Chanter: %s declares %d%s." % (
                g.players[int(ev["player"])].name, n,
                "; " + ", ".join("%s draws %d" % (g.players[int(x["player"])].name, len(x["cards"])) for x in ev.get("drawn", [])) if n else ""))
        elif t == "decide" and ev.get("kind") == "chanter_discard":
            parts.append("%s discards down to the limit." % g.players[int(ev["player"])].name)
        elif t == "chanter_discard":
            parts.append("%s discards %s." % (g.players[int(ev["player"])].name, " + ".join(g.card(c).label() for c in ev["cards"])))
        elif t == "decide" and ev.get("kind") == "pilgrim_banish":
            parts.append("%s matches a pilgrim in the mission zone: banish it?" % g.card(ev["entering"]).label())
        elif t == "pilgrim_banish":
            parts.append("%s banished from the mission zone." % g.card(ev["pilgrim"]).label())
        elif t == "pilgrim_skip":
            parts.append("The pilgrims stay.")
        elif t == "reserve_discard":
            parts.append("%d card%s from the reserve to the discard pile." % (len(ev["cards"]), "" if len(ev["cards"]) == 1 else "s"))
        elif t == "decide" and ev.get("kind") == "zone_banish":
            parts.append("Exact kill: banish a mission zone card first?")
        elif t == "zone_banish":
            parts.append("%s banished from the mission zone." % g.card(ev["card"]).label())
        elif t == "decide" and ev.get("kind") == "zone_build":
            parts.append("Move cards in play to the mission zone?")
        elif t == "zone_build":
            parts.append("%s moves to the mission zone (enemy strength +%d)." % (g.card(ev["card"]).label(), int(ev.get("bonus", 0))))
        elif t == "zone_build_stop":
            parts.append("Nothing more moves to the zone.")
        elif t == "decide" and ev.get("kind") == "discard_banish":
            parts.append("Mission zone filled: banish any discards?")
        elif t == "zone_filled":
            parts.append("Banished %d; %d card%s healed under the reserve. The zone is closed." % (
                len(ev["banished"]), int(ev["healed"]), "" if int(ev["healed"]) == 1 else "s"))
        elif t == "decide" and ev.get("kind") == "discard_pick":
            parts.append("Exact kill: put a discard pile card on top of the reserve?")
        elif t == "discard_pick":
            parts.append("%s from the discard pile on top of the reserve." % g.card(ev["card"]).label())
        elif t == "discard_pick_skip":
            parts.append("The discard pile stays.")
        elif t == "decide" and ev.get("kind") == "pile_rescue":
            parts.append("End of turn: rescue a captured card or rotate the piles.")
        elif t == "pile_rescue":
            parts.append("%s banished; %s rescued from pile %d to the discard pile." % (
                g.card(ev["card"]).label(), g.card(ev["rescued"]).label(), int(ev["pile"]) + 1))
        elif t == "pile_rotate":
            parts.append("The captured piles rotate.")
        elif t == "decide" and ev.get("kind") == "pile_to_reserve":
            parts.append("Exact kill: move a captured card on top of the reserve?")
        elif t == "pile_to_reserve":
            parts.append("%s from pile %d on top of the reserve." % (g.card(ev["card"]).label(), int(ev["pile"]) + 1))
        elif t == "pile_to_reserve_skip":
            parts.append("The captured piles stay.")
        # missions 10 to 12
        elif t == "decide" and ev.get("kind") == "zone_feed":
            parts.append("%s must put a hand card into the mission zone." % g.players[int(ev["player"])].name)
        elif t == "zone_feed":
            parts.append("%s goes into the mission zone." % g.card(ev["card"]).label())
        elif t == "beast_reveal":
            parts.append("%s beast revealed." % CLASS_NAME.get(str(ev.get("suit")), "A"))
        elif t == "beast_effect":
            where = "banished" if ev.get("to") == "banished" else "discarded"
            parts.append("%s %s." % (g.card(ev["moved"]).label(), where))
        elif t == "beast_skip":
            parts.append("No beast this turn (exact kill).")
        elif t == "beast_reshuffle":
            parts.append("The beast deck is reformed.")
        elif t == "decide" and ev.get("kind") in ("beast_discard", "beast_banish"):
            parts.append("%s must %s a hand card." % (g.players[int(ev["player"])].name,
                                                   "discard" if ev.get("kind") == "beast_discard" else "banish"))
        elif t == "decide" and ev.get("kind") == "banish_order":
            parts.append("Choose the order in which the mission zone is banished.")
        elif t == "banish_order":
            parts.append("Mission zone banished, %s on top." % g.card(ev["cards"][-1]).label())
        elif t == "discard_banished":
            parts.append("The discard pile (%d) is banished." % len(ev["cards"]))
        elif t == "zone_skip":
            parts.append("No card into the zone (exact kill).")
        elif t == "banish_redirect":
            parts.append("%s is restored: under the reserve instead of banished." % g.card(ev["card"]).label())
        elif t == "reserve_redirect":
            parts.append("%s is corrupted: bottom of the banished pile instead of the reserve." % g.card(ev["card"]).label())
        # Evergreen
        elif t == "bane":
            parts.append("%s: %s." % ({16: "Lingering Dread: banished", 22: "The Fiery Crucible: discarded"}.get(int(ev.get("n", 0)), "Bane"),
                                      g.card(ev["card"]).label()))
        elif t == "zone_absorb":
            parts.append("Absorbtion: the killing attack goes into the mission zone.")
        elif t == "banished_shuffled":
            parts.append("The banished pile is shuffled.")
        elif t == "lake_banish":
            parts.append("The Lake: %d reserve card%s banished." % (len(ev["cards"]), "" if len(ev["cards"]) == 1 else "s"))
        elif t == "decide" and ev.get("kind") in ("zone_order", "zone_discard", "precision_strike", "restored_arrows",
                                                   "zone_sibling", "zone_match", "close_call", "attack_discard", "poison"):
            parts.append({"zone_order": "Choose the order of the mission zone.", "zone_discard": "Exact kill: discard a zone card first?",
                          "precision_strike": "Precision Strike: take a card into hand.",
                          "restored_arrows": "Restored Arrows: a banished card under the reserve?",
                          "zone_sibling": "Squad of Siblings: move a matching zone card?",
                          "zone_match": "Selfless Rescue: move a matching zone card?",
                          "close_call": "A Close Call: pick a discard for the top of the reserve.",
                          "attack_discard": "Eye-Level Sticks: discard a hand card.",
                          "poison": "Choose Your Poison: discard, or the reserve feeds the zone."}[str(ev.get("kind"))])
        elif t in ("zone_sibling", "zone_match", "zone_discard"):
            parts.append("%s from the mission zone to the discard pile." % g.card(ev["card"]).label())
        elif t in ("zone_sibling_skip", "zone_match_skip", "zone_discard_skip"):
            parts.append("The mission zone stays.")
        elif t == "zone_order":
            parts.append("Mission zone discarded, %s on top." % g.card(ev["cards"][-1]).label())
        elif t == "precision_strike":
            parts.append("Precision Strike: %s into hand." % g.card(ev["card"]).label())
        elif t == "restored_arrows":
            parts.append("Restored Arrows: %s under the reserve." % g.card(ev["card"]).label())
        elif t == "restored_arrows_skip":
            parts.append("The banished pile stays.")
        elif t == "close_call":
            parts.append("A Close Call: the payment goes under the reserve.")
        elif t == "close_call_pick":
            parts.append("%s on top of the reserve." % g.card(ev["card"]).label())
        elif t == "attack_discard":
            parts.append("Eye-Level Sticks: %s discarded." % g.card(ev["card"]).label())
        elif t == "poison":
            parts.append("Choose Your Poison: %s discarded." % g.card(ev["card"]).label())
        elif t == "poison_skip":
            parts.append("Choose Your Poison: the top reserve card goes into the zone.")
    return " ".join(parts)


# ============================================================================ other screens
class TextScreen(Screen):
    title = ""

    def body(self) -> str:
        return ""

    def layout(self) -> None:
        if not hasattr(self, "app"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        w, h = self.width, self.height
        m = T.MARGIN
        y = T.TOP_INSET
        if isinstance(self, (MissionListScreen, CampaignLogScreen, ProgressScreen)) or (isinstance(self, LoreScreen) and self.local):
            back_to = CampaignScreen
        elif isinstance(self, HistoryScreen):
            back_to = QuickPlayScreen
        else:
            back_to = MenuScreen
        self.add_subview(make_button("‹ Back", lambda s: self.app.show(back_to(self.app)), (m, y, 80, 36), False, 14))
        self.add_subview(make_label(self.title, (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 48
        sv = ui.ScrollView(frame=(m, y, w - 2 * m, h - y - T.BOTTOM_INSET))
        text = self.body()
        tw, th = ui.measure_string(text, w - 2 * m - 8, (T.FONT, 14))
        lab = make_label(text, (4, 0, w - 2 * m - 8, th + 20), 14, False, T.TEXT, ui.ALIGN_LEFT, 0)
        sv.add_subview(lab)
        sv.content_size = (w - 2 * m, th + 40)
        self.add_subview(sv)


class RulesScreen(TextScreen):
    title = "Rules"

    def body(self) -> str:
        return RULES_TEXT


class HistoryScreen(TextScreen):
    title = "History"

    def body(self) -> str:
        rows = store.load_history()
        if not rows:
            return "No finished games yet."
        lines = []
        wins = sum(1 for r in rows if r["result"] != "loss")
        lines.append("%d games, %d won." % (len(rows), wins))
        for r in reversed(rows[-40:]):
            res = r["result"]
            if res == "loss":
                res = "lost after %d enemies" % r.get("defeated", 0)
            lines.append("%s · %dp · %s · %d turns" % (r["when"], r["players"], res, r.get("turns", 0)))
        return "\n".join(lines)


class SettingsScreen(Screen):
    def layout(self) -> None:
        if not hasattr(self, "app"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        w = self.width
        m = T.MARGIN
        y = T.TOP_INSET
        self.add_subview(make_button("‹ Back", lambda s: self.app.show(MenuScreen(self.app)), (m, y, 80, 36), False, 14))
        self.add_subview(make_label("Settings", (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 56
        rows = [
            ("show_hints", "Hint button in multiplayer games", False),
            ("jester_may_choose_self", "Jester's player may choose themselves", False),
            ("open_hands", "Open hands by default (pass and play)", False),
            ("rules_card", "Show a mission's rules card when it first loads", True),
            ("classic_faces", "Classic card faces: a 7 shows seven symbols, like a playing card", False),
            ("played_below", "Played cards under the hand (off: above it)", True),
        ]
        for key, label, default in rows:
            self.add_subview(make_label(label, (m, y, w - 2 * m - 60, 44), 15, False, T.TEXT, lines=2))
            sw = ui.Switch(frame=(w - m - 51, y + 6, 51, 31))
            sw.value = bool(self.app.settings.get(key, default))
            sw.action = (lambda k: lambda s: self._toggle(k, s.value))(key)
            self.add_subview(sw)
            y += 56
        y += 10
        self.add_subview(make_label("Saves live in %s" % store.save_dir(), (m, y, w - 2 * m, 60), 12, False, T.MUTED, lines=3))

    def _toggle(self, key: str, value: bool) -> None:
        self.app.settings[key] = bool(value)
        self.app.save_settings()
        apply_face_style(self.app.settings)


RULES_TEXT = """Defeat all 12 enemies: four Jacks (20 health, 10 attack), then four Queens (30/15), then four Kings (40/20).

Your turn
1. Play a card, a combo, or yield.
2. Suit power, with the attack value of what you played: Hearts heal that many cards from the discard pile under the tavern deck; Diamonds draw that many cards (you first, then clockwise, nobody above the hand limit); Clubs double the damage; Spades reduce this enemy's attack by that much for as long as it lives.
3. Deal the damage. Exactly its remaining health: the enemy goes face down on top of the tavern deck. More: it goes to the discard pile. The player who defeats an enemy skips step 4 and takes another turn against the next enemy.
4. Suffer damage: discard cards worth at least the enemy's attack minus the shields. If you cannot, everyone loses.

Plays
A single card. An Animal Companion (Ace, value 1) with one other card, both powers apply. Two to four cards of the same number totalling 10 or less, all powers apply with the total. A Jester alone.

Immunity
Each enemy ignores the power of its own suit. A Jester cancels that immunity for the rest of the fight, deals no damage, skips the enemy's attack, and lets its player choose who goes next.

Yielding
Skip steps 2 and 3 and go straight to suffering damage. Not allowed if every other player yielded on their last turn, and never in a solo game.

Solo
Hand of 8. Instead of Jesters in the deck you have two Jester powers: at the start of your turn or before suffering damage, discard your hand and draw 8. Win without using them for a gold medal, with one for silver, with both for bronze.

Losing
A player cannot cover the damage, or has no card to play and may not yield."""


class MissionListScreen(TextScreen):
    title = "Missions"

    def body(self) -> str:
        camp = self.app.campaign
        lines = []
        for mi in MISSIONS:
            n = mi["number"]
            if camp is None:
                state = ""
            elif n in camp.completed:
                state = "done in %d attempt%s" % (camp.attempts_on(n), "" if camp.attempts_on(n) == 1 else "s")
            elif n == camp.mission:
                state = "current"
            else:
                state = "locked"
            if camp is not None and camp.revealed(n):
                lines.append("%d. %s — %s (%s)\n   %s" % (n, mi["title"], mi["location"], state, mi["summary"]))
                if n in camp.completed or camp.reveal_all:
                    lines.append("   Rewards: %s" % mi["rewards_text"])
            else:
                lines.append("%d. ??? (%s)" % (n, state))
            lines.append("")
        return "\n".join(lines)


class CampaignLogScreen(TextScreen):
    title = "Campaign log"

    def body(self) -> str:
        camp = self.app.campaign
        if camp is None:
            return "No campaign."
        return "\n".join(camp.log[-80:]) or "Nothing yet."


class ProgressScreen(TextScreen):
    title = "Progress"

    def body(self) -> str:
        camp = self.app.campaign
        if camp is None:
            return "No game."
        lines = ["%s · %d player%s · started %s" % (camp.name, camp.players, "" if camp.players == 1 else "s", camp.created)]
        total_attempts = sum(camp.attempts.values())
        total_losses = sum(camp.losses.values())
        lines.append("Missions completed: %d of 12 · attempts %d · losses %d" % (len(camp.completed), total_attempts, total_losses))
        lines.append("Party %d cards · corrupted %d · relics: %s" % (
            len(camp.party), len(camp.corrupted), ", ".join(relic_name(r) for r in camp.relics) or "none"))
        lines.append("")
        for mi in MISSIONS:
            n = mi["number"]
            if n in camp.completed:
                state = "done in %d attempt%s" % (camp.attempts_on(n), "" if camp.attempts_on(n) == 1 else "s")
            elif n == camp.mission:
                state = "current (%d attempt%s so far)" % (camp.attempts_on(n), "" if camp.attempts_on(n) == 1 else "s")
            else:
                state = "locked"
            if camp.revealed(n):
                lines.append("%d. %s — %s (%s)" % (n, mi["title"], mi["location"], state))
            else:
                lines.append("%d. ??? (%s)" % (n, state))
        lines.append("")
        lines.append("Campaign log")
        lines.extend(camp.log[-60:] or ["Nothing yet."])
        return "\n".join(lines)


class LoreScreen(TextScreen):
    title = "Lore"

    def __init__(self, app: "App", local: bool = True, **kw) -> None:
        super().__init__(app, **kw)
        self.local = local
        self.title = "Lore" if local else "Lore (all games)"

    def body(self) -> str:
        entries = self.app.lore_entries(self.local)
        if not entries:
            return "Nothing revealed yet. Lore appears as missions are reached and completed."
        out = []
        for e in entries:
            out.append(e["title"])
            out.append(e["text"])
            out.append("")
        if not os.path.exists(store.lore_overlay_path()):
            out.append("(These are summaries written for this app. Put the real card text in %s to replace them; that file stays private.)" % store.LORE_OVERLAY)
        return "\n".join(out)
