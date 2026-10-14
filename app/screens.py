"""Screens and app flow for the Pythonista client."""
from __future__ import annotations

import os
import random
from typing import Callable, Dict, List, Optional

import ui

from regicide.bots import greedy_policy, min_waste_discard
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
from .widgets import (CardStrip, EnemyPanel, HandGrid, make_button, make_label, set_enabled)

VERSION = "alpha 3"

# Relic ids (campaign saves, ``game.extra["relics"]``) -> the names printed on the cards.
RELIC_NAMES: Dict[str, str] = {"flute": "Kinfolk Flute", "whistle": "Scarlet Whistle", "emblem": "Azure Emblem"}


def relic_name(relic_id: str) -> str:
    return RELIC_NAMES.get(relic_id, relic_id)


def suit_name(game: Game, s: str) -> str:
    if game.config.rules_id.startswith("legacy"):
        return CLASS_NAME.get(s, SUIT_NAME.get(s, s))
    return SUIT_NAME.get(s, s)



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


class App(ui.View):
    """Root view; shows one Screen at a time."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        w, h = ui.get_screen_size()
        self.frame = (0, 0, w, h)
        self.background_color = T.BG
        self.name = "PersonalRegicide"
        self.settings = store.load_settings()
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

    def start_attempt(self) -> None:
        assert self.campaign is not None
        self.in_campaign = True
        self.game = self.campaign.start_attempt()
        self.undo_stack = []
        self.save_campaign()
        self.autosave()
        self.show(GameScreen(self))

    def resume_attempt(self) -> bool:
        if self.campaign is None:
            return False
        g = store.load_attempt(self.campaign.slot)
        if g is None:
            return False
        self.in_campaign = True
        self.game = g
        self.undo_stack = []
        self.show(GameScreen(self))
        return True

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
        self.overlay: Optional[ui.View] = None
        self.message_text = ""
        self.status = make_label("", (0, 0, 10, 10), 13, False, T.MUTED)
        self.menu_btn = make_button("Menu", self._menu, (0, 0, 70, 30), False, 14)
        self.enemy = EnemyPanel()
        self.strip = CardStrip()
        self.zone = CardStrip()
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
        for v in (self.status, self.menu_btn, self.enemy, self.strip, self.zone, self.message, self.hand,
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
        self.menu_btn.frame = (w - m - 70, y, 70, 30)
        y += 36
        eh = 128
        self.enemy.frame = (m, y, w - 2 * m, eh)
        y += eh + 6
        self.strip.frame = (m, y, w - 2 * m - 90, 64)
        self.special_btn.frame = (w - m - 84, y + 14, 84, 36)
        y += 70
        if not self.zone.hidden:
            self.zone.frame = (m, y, w - 2 * m, 64)
            y += 70
        self.message.frame = (m, y, w - 2 * m, 56)
        y += 60
        bar_h = 48
        bar_y = h - T.BOTTOM_INSET - bar_h
        self.hand.frame = (m, y, w - 2 * m, max(120, bar_y - 10 - y))
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
        g = self.game = self.app.game  # type: ignore[assignment]
        legacy = g.config.rules_id.startswith("legacy")
        deck = "Reserve" if legacy else "Tavern"
        self.status.text = "Turn %d · %s %d · Discard %d" % (g.turn, deck, len(g.tavern), len(g.discard))
        if g.banished:
            self.status.text += " · Banished %d" % len(g.banished)
        if g.n_players == 1:
            self.status.text += " · Jesters %d" % g.solo_jesters
        self.enemy.game = g
        self.enemy.set_needs_display()
        played = [g.card(c) for p in g.plays for c in p.card_ids]
        self.strip.set_cards(played, "Played against this enemy")
        self.strip.set_needs_display()
        uses_zone = bool(g.mission_zone) or getattr(g.rules, "uses_mission_zone", False)
        if uses_zone != (not self.zone.hidden):
            self.zone.hidden = not uses_zone
            self.layout()
        if uses_zone:
            zone_cards = [g.card(c) for c in g.mission_zone]
            imm = [s for s in g.rules.immune_suits(g) if g.enemy is not None and s not in g.enemy.suits]
            title = "Mission zone"
            if imm:
                title += " · immune to " + " / ".join(CLASS_NAME.get(s, s) + "s" for s in imm)
            elif not zone_cards:
                title += " (empty)"
            self.zone.set_cards(zone_cards, title)
            self.zone.set_needs_display()
        if g.is_over:
            if self.app.in_campaign:
                if not hasattr(self, "campaign_result"):
                    self.campaign_result = self.app.finish_attempt()
                self._show_overlay(CampaignResultOverlay(self))
            else:
                self._show_overlay(ResultOverlay(self))
            return
        if g.phase == PHASE_CHOOSE_NEXT:
            self._show_overlay(ChooseNextOverlay(self))
            return
        kind = (g.decision or {}).get("kind") if g.phase == PHASE_DECIDE else None
        if kind is not None and kind not in ("flute_add", "emblem_place", "mage_peek", "emblem_keep"):
            # a decision of the current player's own with a short list of options (which
            # mission zone card to rescue, and whatever later missions add)
            self._show_overlay(PickOverlay(self))
            return
        if kind in ("mage_peek", "emblem_keep"):
            # The attacker's secret look at the reserve. In pass-and-play another player may
            # hold the phone (a Kinfolk Flute or Azure Emblem decision came first): hand it
            # back before the revealed cards are shown.
            seat = g.deciding
            if g.n_players > 1 and self.shown_player != seat and not g.config.open_hands:
                self.hand.set_cards([])
                self._show_overlay(HandoverOverlay(self))
                return
            self.shown_player = seat
            self._show_overlay(MagePeekOverlay(self) if kind == "mage_peek" else EmblemKeepOverlay(self))
            return
        # The seat whose hand is shown: the attacker, or whoever must decide (Kinfolk
        # Flute, Azure Emblem).
        seat = g.deciding
        needs_handover = (g.n_players > 1 and self.shown_player != seat
                          and (not g.config.open_hands or g.phase == PHASE_DECIDE))
        if needs_handover:
            self.hand.set_cards([])
            self._show_overlay(DecisionOverlay(self) if g.phase == PHASE_DECIDE else HandoverOverlay(self))
            return
        self._hide_overlay()
        self.shown_player = seat
        if g.phase == PHASE_DECIDE:
            self.hand.badges = {}
            self.hand.set_cards(g.hand(seat), keep_selection=False)
        else:
            flute = list(g.extra.get("flute", []))
            self.hand.badges = dict((cid, "flute") for cid in flute)
            self.hand.set_cards(g.hand() + [g.card(c) for c in flute], keep_selection=False)
        specials = g.rules.special_actions(g)
        self.special_btn.hidden = not specials
        if specials:
            self.special_btn.title = "Flute" if all(a.get("name") == "flute_store" for a in specials) else "Actions"
        self._update_controls()

    def reveal_hand(self) -> None:
        self.shown_player = self.game.deciding
        self.refresh(after_action=False)

    def _update_controls(self) -> None:
        g = self.game
        sel = list(self.hand.selected)
        name = g.active_player.name
        if g.phase == PHASE_PLAY:
            self.hand.selectable = lambda c: True
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
                if ok:
                    pv = g.preview_play(sel)
                    self.message.text = describe_preview(g, pv)
                    set_enabled(self.right_btn, True)
                else:
                    self.message.text = info
                    set_enabled(self.right_btn, False)
            else:
                self.message.text = self.message_text or ("%s: tap cards to play, then Play." % name)
                set_enabled(self.right_btn, False)
        elif g.phase == PHASE_SUFFER:
            need = g.pending_damage
            self.hand.selectable = lambda c: True
            total = sum(g.card(c).defence_value for c in sel)
            feign = g.feign_death_available()
            self.left_btn.title = "Feign death" if feign else "Suggest"
            set_enabled(self.left_btn, True, False)
            self.mid_btn.title = "Jester" if self.width < 385 else "Jester power"
            self.mid_btn.hidden = not (g.n_players == 1 and g.rules.solo_jester_mode(g) == "refresh")
            set_enabled(self.mid_btn, g.can_use_solo_jester(), False)
            self.right_btn.title = "Discard"
            whole = set(sel) == set(g.active_player.hand) and bool(sel)
            set_enabled(self.right_btn, (total >= need and need > 0) or (feign and whole))
            self.message.text = "%s suffers %d damage. Select cards worth at least %d (selected: %d)." % (
                name, need, need, total)
            if g.hand_defence_value() < need and g.can_use_solo_jester():
                self.message.text += " Your hand is short: use the Jester power."
            elif feign:
                self.message.text += " At the hand limit you may feign death: discard everything."
        elif g.phase == PHASE_DECIDE and (g.decision or {}).get("kind") == "emblem_place":
            # Azure Emblem, 2+ players: the shown hand belongs to another player, who may
            # place one card face down on top of the reserve before the attacker's mage looks.
            if len(sel) > 1:
                self.hand.set_selection(sel[-1:])   # re-enters here with one card selected
                return
            self.hand.selectable = lambda c: True
            self.hand.refresh_dim()
            self.left_btn.title = "Pass"
            set_enabled(self.left_btn, True, False)
            self.mid_btn.hidden = True
            self.right_btn.title = "Place"
            set_enabled(self.right_btn, len(sel) == 1)
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
                self.message.text = "%s adds %s (attack %d): %s" % (
                    who, " + ".join(g.card(c).label() for c in sel), pv.get("attack", 0), describe_preview(g, pv))
            elif sel:
                self.message.text = "Only %ss may join, and the attack must stay at 10 or less." % d.get("strength")
            else:
                self.message.text = "%s: add to %s's %s attack? Select %ss (total at most 10) and tap Add, or Pass." % (
                    who, attacker, attack, d.get("strength"))
        self.message.set_needs_display()

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
        if g.phase == PHASE_PLAY:
            self._act(g.yield_turn)
        elif g.phase == PHASE_SUFFER:
            if g.feign_death_available():
                self.hand.set_selection(list(g.active_player.hand))
            else:
                self.hand.set_selection(min_waste_discard(g))
        elif g.phase == PHASE_DECIDE:
            if (g.decision or {}).get("kind") == "emblem_place":
                self._act(lambda: g.decide({"type": "emblem_pass"}))
            else:
                self._act(g.flute_pass)

    def _special(self, sender) -> None:
        self._show_overlay(SpecialOverlay(self))

    def _mid(self, sender) -> None:
        g = self.game
        if g.n_players == 1 and g.rules.solo_jester_mode(g) == "attack":
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
            if (g.decision or {}).get("kind") == "emblem_place":
                self._act(lambda: g.decide({"type": "emblem_place", "card": sel[0]}))
            else:
                self._act(lambda: g.flute_add(sel))

    def choose_next(self, player: int) -> None:
        g = self.game
        self._act(lambda: g.choose_next(player))

    def decide(self, action: dict) -> None:
        g = self.game
        self._act(lambda: g.decide(action))

    def _menu(self, sender) -> None:
        self._show_overlay(GameMenuOverlay(self))

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
    """Semi-transparent full-screen panel with a centred card."""

    def __init__(self, screen: GameScreen, **kw) -> None:
        super().__init__(**kw)
        self.screen = screen
        self.background_color = (0, 0, 0, 0.72)
        self.panel = ui.View()
        self.panel.background_color = T.PANEL
        self.panel.corner_radius = 16
        self.add_subview(self.panel)

    def build(self) -> List[ui.View]:
        return []

    def layout(self) -> None:
        if not hasattr(self, "panel") or not hasattr(self, "screen"):
            return
        for v in list(self.panel.subviews):
            self.panel.remove_subview(v)
        pw = min(340, self.width - 2 * T.MARGIN)
        items = self.build()
        y = 20
        for v in items:
            v.frame = (20, y, pw - 40, v.height)
            self.panel.add_subview(v)
            y += v.height + 12
        ph = y + 8
        self.panel.frame = ((self.width - pw) / 2, max(T.TOP_INSET, (self.height - ph) / 2), pw, ph)


class HandoverOverlay(Overlay):
    def build(self) -> List[ui.View]:
        g = self.screen.game
        name = g.active_player.name
        return [
            make_label("Pass the phone to", (0, 0, 10, 24), 15, False, T.MUTED, ui.ALIGN_CENTER),
            make_label(name, (0, 0, 10, 40), 28, True, T.ACCENT, ui.ALIGN_CENTER),
            make_label("%s's hand stays hidden until you tap." % name, (0, 0, 10, 44), 14, False, T.TEXT, ui.ALIGN_CENTER, 2),
            make_button("Show my hand", lambda s: self.screen.reveal_hand(), (0, 0, 10, 50)),
        ]


class DecisionOverlay(Overlay):
    """Another player must decide about the attack on the table (Kinfolk Flute: add to it;
    Azure Emblem: place a card on the reserve before the mage looks). Names the deciding
    player and the attack, then reveals that player's hand on request."""

    def build(self) -> List[ui.View]:
        g = self.screen.game
        d = g.decision or {}
        who = g.players[g.deciding].name
        play = g.plays[int(d.get("play_index", len(g.plays) - 1))]
        attacker = g.players[play.player].name
        attack = " + ".join(g.card(c).label() for c in play.card_ids)
        items: List[ui.View] = []
        if not g.config.open_hands:
            items.append(make_label("Pass the phone to", (0, 0, 10, 24), 15, False, T.MUTED, ui.ALIGN_CENTER))
        items.append(make_label(who, (0, 0, 10, 40), 28, True, T.ACCENT, ui.ALIGN_CENTER))
        if d.get("kind") == "emblem_place":
            items.append(make_label("%s: place a card for %s's %s attack?" % (who, attacker, attack), (0, 0, 10, 44), 16, True, T.TEXT, ui.ALIGN_CENTER, 2))
            items.append(make_label("Azure Emblem: before the mage looks at the reserve deck you may place one card "
                                    "from your hand face down on top of it, or pass.", (0, 0, 10, 60), 13, False, T.TEXT, ui.ALIGN_CENTER, 3))
        else:
            items.append(make_label("%s: add to %s's %s attack?" % (who, attacker, attack), (0, 0, 10, 44), 16, True, T.TEXT, ui.ALIGN_CENTER, 2))
            items.append(make_label("Kinfolk Flute: you may add %ss from your hand as long as the whole attack stays "
                                    "at 10 or less, or pass." % d.get("strength"), (0, 0, 10, 60), 13, False, T.TEXT, ui.ALIGN_CENTER, 3))
        items.append(make_button("Show my hand", lambda s: self.screen.reveal_hand(), (0, 0, 10, 50)))
        return items


class PickOverlay(Overlay):
    """A decision for the current player with a short list of options (one button each),
    e.g. mission 3's exact kill: which mission zone card goes to the discard pile."""

    TEXTS = {
        "zone_rescue": ("Exact kill!", "Choose one mission zone card to rescue to the discard pile. "
                                       "The enemy and the rest of the zone are banished."),
    }

    def build(self) -> List[ui.View]:
        g = self.screen.game
        d = g.decision or {}
        title, text = self.TEXTS.get(str(d.get("kind")), ("Your choice", "Choose one option."))
        items: List[ui.View] = [
            make_label(title, (0, 0, 10, 36), 24, True, T.ACCENT, ui.ALIGN_CENTER),
            make_label(text, (0, 0, 10, 60), 14, False, T.TEXT, ui.ALIGN_CENTER, 3),
        ]
        for a in g.legal_actions():
            items.append(make_button(a.get("label", a["type"]),
                                     (lambda act: lambda s: self.screen.decide(act))(a), (0, 0, 10, 46)))
        return items


class MagePeekOverlay(Overlay):
    """The Mage's secret look: the cards taken from the top of the reserve in a row (Jesters
    and corrupted cards dimmed, they are discarded), one button per card that may join the
    attack, or a single "Nothing to add" when none may."""

    def heading(self, g: Game, d: dict) -> tuple:
        revealed = list(d.get("revealed", []))
        n = len(revealed)
        if n == 0:
            return ("Mage: the reserve deck is empty", "There was nothing to look at. The attack goes on resolving as it is.")
        title = "Mage: %d card%s revealed" % (n, "" if n == 1 else "s")
        strength = int(d.get("strength", n))
        text = "You looked at the top %d card%s of the reserve deck%s. Jesters and corrupted cards are discarded. " \
               "Choose one of the rest to add to the attack; the others go to the discard pile." % (
                   n, "" if n == 1 else "s", "" if n == strength else " (the mage's strength is %d, the deck was short)" % strength)
        if not d.get("eligible"):
            text = "You looked at the top %d card%s of the reserve deck, but none of them may join the attack: " \
                   "Jesters and corrupted cards are discarded." % (n, "" if n == 1 else "s")
        return (title, text)

    def dimmed_ids(self, g: Game, d: dict) -> List[str]:
        eligible = set(str(c) for c in d.get("eligible", []))
        return [str(c) for c in d.get("revealed", []) if str(c) not in eligible]

    MANY = 4   # more card options than this go in two columns with short titles

    def build_parts(self) -> tuple:
        """(heading views, one button per card option, trailing views)."""
        g = self.screen.game
        d = g.decision or {}
        title, text = self.heading(g, d)
        head: List[ui.View] = [
            make_label(title, (0, 0, 10, 36), 20, True, T.ACCENT, ui.ALIGN_CENTER),
            make_label(text, (0, 0, 10, 76), 13, False, T.TEXT, ui.ALIGN_CENTER, 4),
        ]
        revealed = [g.card(str(c)) for c in d.get("revealed", [])]
        if revealed:
            strip = CardStrip(frame=(0, 0, 10, 84))
            strip.set_cards(revealed, "Revealed from the reserve deck (top first)", self.dimmed_ids(g, d))
            head.append(strip)
        acts = g.legal_actions()
        cards = [a for a in acts if a.get("card")]
        options: List[ui.View] = []
        for a in cards:
            title = a.get("label", a["type"])
            if len(cards) > self.MANY:
                title = "%s %s" % ("Keep" if a["type"] == "emblem_keep" else "Add", g.card(a["card"]).label())
            options.append(make_button(title, (lambda act: lambda s: self.screen.decide(act))(a), (0, 0, 10, 44)))
        tail: List[ui.View] = []
        for a in acts:
            if not a.get("card"):
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
        for v in list(self.panel.subviews):
            self.panel.remove_subview(v)
        pw = min(340, self.width - 2 * T.MARGIN)
        head, options, tail = self.build_parts()
        y = 20
        for v in head:
            v.frame = (20, y, pw - 40, v.height)
            self.panel.add_subview(v)
            y += v.height + 12
        cols = 2 if len(options) > self.MANY else 1
        gap = 8 if cols == 2 else 12
        bw = (pw - 40 - gap * (cols - 1)) / cols
        bh = 40 if cols == 2 else 44
        for i, b in enumerate(options):
            r, c = divmod(i, cols)
            b.frame = (20 + c * (bw + gap), y + r * (bh + gap), bw, bh)
            self.panel.add_subview(b)
        rows = (len(options) + cols - 1) // cols
        if rows:
            y += rows * (bh + gap) - gap + 12
        for v in tail:
            v.frame = (20, y, pw - 40, v.height)
            self.panel.add_subview(v)
            y += v.height + 12
        ph = y + 8
        self.panel.frame = ((self.width - pw) / 2, max(T.TOP_INSET, (self.height - ph) / 2), pw, ph)


class EmblemKeepOverlay(MagePeekOverlay):
    """Azure Emblem, solo: after the pick, one of the other revealed cards may go back on
    top of the reserve deck before the rest is discarded."""

    def heading(self, g: Game, d: dict) -> tuple:
        picked = g.card(str(d.get("picked", ""))).label() if d.get("picked") in g.cards else "the chosen card"
        return ("Azure Emblem", "%s joined the attack. You may put one of the other revealed cards on top of the "
                                "reserve deck before the rest goes to the discard pile." % picked)

    def dimmed_ids(self, g: Game, d: dict) -> List[str]:
        return []


class ChooseNextOverlay(Overlay):
    def build(self) -> List[ui.View]:
        g = self.screen.game
        if g.extra.get("jester_claim"):
            text = "Who claims the Jester? That player attacks now, ignoring the enemy's immunity for this attack."
        else:
            text = "%s chooses who goes next. Players may say if they would like to go." % g.active_player.name
        items: List[ui.View] = [
            make_label("Jester!", (0, 0, 10, 36), 24, True, T.ACCENT, ui.ALIGN_CENTER),
            make_label(text, (0, 0, 10, 60), 14, False, T.TEXT, ui.ALIGN_CENTER, 3),
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
            make_label(detail, (0, 0, 10, 66), 14, False, T.TEXT, ui.ALIGN_CENTER, 4),
            make_button("Play again", lambda s: self.screen.app.start_game(g.config), (0, 0, 10, 48)),
            make_button("Main menu", lambda s: self.screen.app.show(MenuScreen(self.screen.app)), (0, 0, 10, 48), False),
        ]


class GameMenuOverlay(Overlay):
    def build(self) -> List[ui.View]:
        app = self.screen.app
        items: List[ui.View] = [
            make_label("Game menu", (0, 0, 10, 32), 20, True, T.TEXT, ui.ALIGN_CENTER),
            make_button("Resume", lambda s: self.screen.refresh(after_action=False), (0, 0, 10, 46)),
        ]
        if app.undo_stack:
            items.append(make_button("Undo last action", self._undo, (0, 0, 10, 46), False))
        items.append(make_button("Game log", lambda s: self.screen._show_overlay(LogOverlay(self.screen)), (0, 0, 10, 46), False))
        items.append(make_button("Save and go to menu", lambda s: (app.autosave(), app.show(MenuScreen(app))), (0, 0, 10, 46), False))
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


class LogOverlay(Overlay):
    def build(self) -> List[ui.View]:
        g = self.screen.game
        lines = g.log[-14:]
        text = "\n".join(lines) if lines else "Nothing yet."
        return [
            make_label("Game log", (0, 0, 10, 30), 18, True, T.TEXT, ui.ALIGN_CENTER),
            make_label(text, (0, 0, 10, 20 * max(1, len(lines))), 12, False, T.TEXT, ui.ALIGN_LEFT, 0),
            make_button("Back", lambda s: self.screen.refresh(after_action=False), (0, 0, 10, 44)),
        ]


class ClassChoiceOverlay(Overlay):
    """Legacy solo: the Jester attacks as an 8 of a chosen class."""

    def build(self) -> List[ui.View]:
        items: List[ui.View] = [
            make_label("Jester attack", (0, 0, 10, 36), 22, True, T.ACCENT, ui.ALIGN_CENTER),
            make_label("Strength 8, ignores immunity. Choose its class:", (0, 0, 10, 40), 14, False, T.TEXT, ui.ALIGN_CENTER, 2),
        ]
        for s in BASIC_SUITS:
            title = "%s %s" % (SUIT_SYMBOL[s], CLASS_NAME[s])
            items.append(make_button(title, (lambda suit: lambda b: self.screen._act(lambda: self.screen.game.use_solo_jester({"suit": suit})))(s), (0, 0, 10, 46)))
        items.append(make_button("Cancel", lambda b: self.screen.refresh(after_action=False), (0, 0, 10, 44), False))
        return items


class SpecialOverlay(Overlay):
    """Relic and mission actions offered by the rules."""

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
        num = int(g.config.extra.get("mission", 1))
        info = mission_info(num)
        items: List[ui.View] = []
        if res.get("won"):
            items.append(make_label("Mission %d complete" % num, (0, 0, 10, 36), 22, True, T.ACCENT, ui.ALIGN_CENTER))
            lines = list(res.get("rewards") or [])
            for step in res.get("pending") or []:
                lines.append("To choose: %s" % step.get("label", "a reward"))
            lines = lines or ["No rewards."]
            items.append(make_label("\n".join(lines), (0, 0, 10, 24 * len(lines) + 10), 13, False, T.TEXT, ui.ALIGN_LEFT, 0))
            if app.campaign and app.campaign.finished:
                items.append(make_label("The campaign is complete!", (0, 0, 10, 30), 16, True, T.OK, ui.ALIGN_CENTER))
        else:
            items.append(make_label("Mission %d lost" % num, (0, 0, 10, 36), 22, True, T.DANGER, ui.ALIGN_CENTER))
            text = "%s %d coin%s earned (%d total)." % (g.loss_reason, res.get("earned", 0), "" if res.get("earned") == 1 else "s", res.get("coins", 0))
            if res.get("m_box_opened_now"):
                text += " Pack M is open: mercenaries can be hired between attempts."
            items.append(make_label(text, (0, 0, 10, 80), 13, False, T.TEXT, ui.ALIGN_CENTER, 5))
            if app.campaign and app.campaign.m_box_opened:
                items.append(make_button("Mercenary camp", lambda b: app.show(MercenaryScreen(app)), (0, 0, 10, 46)))
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
            y += 40
        else:
            self.add_subview(make_label("Mission %d · %s" % (camp.mission, info["title"]), (m, y, w - 2 * m, 28), 18, True, T.ACCENT))
            y += 28
            self.add_subview(make_label(info["location"], (m, y, w - 2 * m, 20), 13, False, T.MUTED))
            y += 24
            self.add_subview(make_label(info["summary"], (m, y, w - 2 * m, 84), 13, False, T.TEXT, lines=5))
            y += 88
            stats = "Attempts %d · Losses %d" % (camp.attempts_on(camp.mission), camp.losses_on(camp.mission))
            if camp.m_box_opened:
                stats += " · Coins %d" % camp.coins
            if not info.get("verified", False):
                stats += " · rules unverified"
            self.add_subview(make_label(stats, (m, y, w - 2 * m, 20), 12, False, T.MUTED))
            y += 26
            in_progress = store.has_attempt(camp.slot)
            choice = camp.pending_choice()
            if in_progress:
                self.add_subview(make_button("Continue attempt", lambda s: app.resume_attempt(), (x, y, bw, 46)))
                y += 54
            elif choice is not None:
                self.add_subview(make_button("Reward: %s" % choice.get("label", "choose"),
                                             lambda s: app.show(ChoiceScreen(app)), (x, y, bw, 46)))
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
            if camp.m_box_opened and not in_progress:
                self.add_subview(make_button("Mercenary camp (%d coin%s)" % (camp.coins, "" if camp.coins == 1 else "s"),
                                             lambda s: app.show(MercenaryScreen(app)), (x, y, bw, 44), False))
                y += 52
        y += 6
        row_h, gap = 44, 10
        buttons = [
            ("Deck list", lambda s: app.show(PartyScreen(app))),
            ("Map", lambda s: app.show(MapScreen(app))),
            ("Progress", lambda s: app.show(ProgressScreen(app))),
            ("Lore", lambda s: app.show(LoreScreen(app, local=True))),
        ]
        for title, action in buttons:
            self.add_subview(make_button(title, action, (x, y, bw, row_h), False))
            y += row_h + gap


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


class MercenaryScreen(Screen):
    swapping = None  # id of a hired mercenary being swapped, or None

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
        self.add_subview(make_label("Mercenary camp", (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 48
        if camp is None:
            return
        self.add_subview(make_label("Coins: %d. Each failure of a mission earns coins equal to the number of times it "
                                    "has been failed. Hired mercenaries stay until the mission is won; after a failure "
                                    "you may swap one for another of the same cost." % camp.coins,
                                    (m, y, w - 2 * m, 72), 13, False, T.TEXT, lines=4))
        y += 78
        sv = ui.ScrollView(frame=(m, y, w - 2 * m, h - y - T.BOTTOM_INSET))
        yy = 0
        from regicide.campaign.mercenaries import by_id
        if self.swapping is not None and self.swapping in camp.mercenaries:
            cur = by_id(self.swapping)
            sv.add_subview(make_label("Swap %s for:" % cur["name"], (0, yy + 2, w - 2 * m - 90, 28), 14, True, T.OK))
            sv.add_subview(make_button("Cancel", lambda s: self._cancel_swap(), (w - 2 * m - 80, yy, 80, 32), False, 13))
            yy += 38
            for o in camp.swappable(self.swapping):
                lab = make_label(o["name"], (0, yy, w - 2 * m - 90, 40), 14, False, T.TEXT, lines=2)
                sv.add_subview(lab)
                b = make_button("Take", (lambda nid: lambda s: self._swap(nid))(o["id"]), (w - 2 * m - 80, yy + 2, 80, 36), True, 14)
                sv.add_subview(b)
                yy += 46
        else:
            for mid in list(camp.mercenaries):
                mm = by_id(mid)
                sv.add_subview(make_label("Hired: %s" % mm["name"], (0, yy + 2, w - 2 * m - 90, 28), 14, True, T.OK))
                if camp.swappable(mid):
                    sv.add_subview(make_button("Swap", (lambda hid: lambda s: self._begin_swap(hid))(mid),
                                               (w - 2 * m - 80, yy, 80, 32), False, 13))
                yy += 38
            for o in camp.hireable():
                lab = make_label("%s — %d coin%s" % (o["name"], o["cost"], "" if o["cost"] == 1 else "s"), (0, yy, w - 2 * m - 90, 40), 14, False, T.TEXT, lines=2)
                sv.add_subview(lab)
                b = make_button("Hire", (lambda mid: lambda s: self._hire(mid))(o["id"]), (w - 2 * m - 80, yy + 2, 80, 36), True, 14)
                set_enabled(b, bool(o["affordable"]))
                sv.add_subview(b)
                yy += 46
        sv.content_size = (w - 2 * m, yy + 20)
        self.add_subview(sv)

    def _hire(self, mid: str) -> None:
        try:
            self.app.campaign.hire(mid)
        except ValueError as e:
            import console
            console.hud_alert(str(e), "error")
            return
        self.app.save_campaign()
        self.layout()

    def _begin_swap(self, mid: str) -> None:
        self.swapping = mid
        self.layout()

    def _cancel_swap(self) -> None:
        self.swapping = None
        self.layout()

    def _swap(self, new_id: str) -> None:
        try:
            self.app.campaign.swap(self.swapping, new_id)
        except ValueError as e:
            import console
            console.hud_alert(str(e), "error")
            return
        self.swapping = None
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
        self.add_subview(make_label("Reward", (96, y, w - 110, 36), 18, True, T.TEXT, ui.ALIGN_LEFT))
        y += 48
        step = camp.pending_choice() if camp is not None else None
        if step is None:
            self.add_subview(make_label("Nothing to choose.", (m, y, w - 2 * m, 30), 14, False, T.MUTED))
            return
        self.add_subview(make_label(step.get("label", ""), (m, y, w - 2 * m, 44), 15, True, T.ACCENT, lines=2))
        y += 48
        self.confirm_btn = make_button("Confirm", lambda s: self._confirm(), (m, h - T.BOTTOM_INSET - 50, w - 2 * m, 46))
        if step["kind"] == "choice_classes":
            self._layout_classes(step, y)
        else:
            self._layout_pick(step, y)
        self.add_subview(self.confirm_btn)

    # -- pick one card ------------------------------------------------------
    def _layout_pick(self, step: dict, y: float) -> None:
        camp = self.app.campaign
        w, h = self.width, self.height
        m = T.MARGIN
        hint = {"choice_corrupt": "Tap the character who takes the corruption. Corrupted cards banish the top "
                                  "card of the reserve when played and their own class ignores immunity.",
                "choice_suit": "Tap the character who gets the %s sticker. The card keeps its own class and "
                               "gains this one too." % CLASS_NAME.get(str(step.get("suit", "")), "class")}.get(step["kind"], "")
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
                camp.resolve_choice(self.chosen)
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
        if camp is None:
            return
        from .widgets import CardView
        sv = ui.ScrollView(frame=(m, y, w - 2 * m, h - y - T.BOTTOM_INSET))
        cols = 5
        gap = 6
        cw = (w - 2 * m - gap * (cols - 1)) / cols
        ch = cw * 1.42
        cards = sorted(camp.party_cards(), key=lambda c: (c.suits[0] if c.suits else "Z", c.value))
        for i, c in enumerate(cards):
            r, col = divmod(i, cols)
            v = CardView(c)
            v.small = True
            v.touch_enabled = False
            v.frame = (col * (cw + gap), r * (ch + gap), cw, ch)
            sv.add_subview(v)
        rows = (len(cards) + cols - 1) // cols
        sv.content_size = (w - 2 * m, rows * (ch + gap) + 20)
        self.add_subview(sv)


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
    s = "%d damage" % pv["damage"]
    if pv["defeats"]:
        s += " — defeats it%s" % (" exactly! (goes to the tavern)" if pv["exact"] else "")
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
            elif ev.get("doubled"):
                parts.append("%s doubled" % sym)
            elif "shield" in ev:
                parts.append("%s shield +%d" % (sym, ev["shield"]))
        elif t == "damage":
            parts.append("%d damage" % ev["amount"])
        elif t == "defeat":
            parts.append("Exact kill! Enemy to the tavern." if ev["exact"] else "Enemy defeated!")
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
            parts.append("No damage to suffer.")
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
            parts.append("Mission zone %s (%d card%s)." % (
                "banished" if ev.get("to") == "banish" else "discarded", len(ev["cards"]), "" if len(ev["cards"]) == 1 else "s"))
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
            ("show_hints", "Hint button in multiplayer games"),
            ("jester_may_choose_self", "Jester's player may choose themselves"),
            ("open_hands", "Open hands by default (pass and play)"),
        ]
        for key, label in rows:
            self.add_subview(make_label(label, (m, y, w - 2 * m - 60, 44), 15, False, T.TEXT, lines=2))
            sw = ui.Switch(frame=(w - m - 51, y + 6, 51, 31))
            sw.value = bool(self.app.settings.get(key, False))
            sw.action = (lambda k: lambda s: self._toggle(k, s.value))(key)
            self.add_subview(sw)
            y += 56
        y += 10
        self.add_subview(make_label("Saves live in %s" % store.save_dir(), (m, y, w - 2 * m, 60), 12, False, T.MUTED, lines=3))

    def _toggle(self, key: str, value: bool) -> None:
        self.app.settings[key] = bool(value)
        self.app.save_settings()


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
