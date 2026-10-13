"""Screens and app flow for the Pythonista client."""
from __future__ import annotations

import random
from typing import Callable, Dict, List, Optional

import ui

from regicide.bots import greedy_policy, min_waste_discard
from regicide.cards import SUIT_NAME, SUIT_SYMBOL, Card
from regicide.engine import (PHASE_CHOOSE_NEXT, PHASE_LOST, PHASE_PLAY, PHASE_SUFFER, PHASE_WON,
                             Game, IllegalAction)
from regicide.rules import GameConfig

from . import store
from . import theme as T
from .widgets import (CardStrip, EnemyPanel, HandGrid, make_button, make_label, set_enabled)

VERSION = "alpha 1"


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

    def show(self, screen: Screen) -> None:
        if self.current is not None:
            self.remove_subview(self.current)
        self.current = screen
        screen.frame = (0, 0, self.width, self.height)
        self.add_subview(screen)
        screen.layout()
        screen.on_show()

    def layout(self) -> None:
        cur = getattr(self, "current", None)
        if cur is not None:
            cur.frame = (0, 0, self.width, self.height)
            cur.layout()

    # ------------------------------------------------------------- game flow
    def start_game(self, config: GameConfig, seed: Optional[int] = None) -> None:
        self.game = Game.new(config, seed=seed)
        self.undo_stack = []
        self.autosave()
        self.show(GameScreen(self))

    def resume_game(self) -> bool:
        g = store.load_game()
        if g is None:
            return False
        self.game = g
        self.undo_stack = []
        self.show(GameScreen(self))
        return True

    def autosave(self) -> None:
        if self.game is not None and not self.game.is_over:
            store.save_game(self.game)

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
        w = self.width
        y = T.TOP_INSET + 30
        self.add_subview(make_label("REGICIDE", (0, y, w, 44), 36, True, T.ACCENT, ui.ALIGN_CENTER))
        y += 46
        self.add_subview(make_label("personal edition · %s" % VERSION, (0, y, w, 20), 13, False, T.MUTED, ui.ALIGN_CENTER))
        y += 50
        bw, bh, gap = min(300, w - 2 * T.MARGIN), 50, 14
        x = (w - bw) / 2
        items: List = []
        if store.has_game():
            items.append(("Continue game", self._continue, True))
        items += [
            ("Solo game", lambda s: self.app.show(NewGameScreen(self.app, 1)), True),
            ("Pass and play (2–4)", lambda s: self.app.show(NewGameScreen(self.app, max(2, self.app.settings.get("last_players", 2)))), True),
            ("Legacy campaign (alpha 2)", None, False),
            ("History", lambda s: self.app.show(HistoryScreen(self.app)), False),
            ("Rules", lambda s: self.app.show(RulesScreen(self.app)), False),
            ("Settings", lambda s: self.app.show(SettingsScreen(self.app)), False),
            ("Quit", lambda s: self.app.close(), False),
        ]
        for title, action, primary in items:
            b = make_button(title, action or (lambda s: None), (x, y, bw, bh), primary)
            if action is None:
                set_enabled(b, False)
            self.add_subview(b)
            y += bh + gap

    def _continue(self, sender) -> None:
        if not self.app.resume_game():
            import console
            console.hud_alert("No saved game", "error")
            self.layout()


# ============================================================================ new game
class NewGameScreen(Screen):
    def __init__(self, app: "App", players: int, **kw) -> None:
        super().__init__(app, **kw)
        self.players = players
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
        self.add_subview(make_button("‹ Back", lambda s: self.app.show(MenuScreen(self.app)), (m, y, 80, 36), False, 14))
        self.add_subview(make_label("New game", (100, y, w - 200, 36), 20, True, T.TEXT, ui.ALIGN_CENTER))
        y += 56
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
        self.add_subview(make_label(
            "Solo: 8-card hand, two Jester powers (discard hand, draw 8), no yielding. "
            "Gold / Silver / Bronze medal by Jesters used.", (m, y, w - 2 * m, 60), 13, False, T.MUTED, lines=3))

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
        self.message = make_label("", (0, 0, 10, 10), 14, False, T.TEXT, ui.ALIGN_CENTER, lines=3)
        self.hand = HandGrid()
        self.hand.on_change = self._selection_changed
        self.left_btn = make_button("Yield", self._left, (0, 0, 10, 10), False)
        self.mid_btn = make_button("Jester", self._mid, (0, 0, 10, 10), False)
        self.right_btn = make_button("Play", self._right, (0, 0, 10, 10), True)
        self.toast = make_label("", (0, 0, 10, 10), 13, True, T.BG, ui.ALIGN_CENTER)
        self.toast.background_color = T.ACCENT
        self.toast.corner_radius = 8
        self.toast.hidden = True
        for v in (self.status, self.menu_btn, self.enemy, self.strip, self.message, self.hand,
                  self.left_btn, self.mid_btn, self.right_btn, self.toast):
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
        self.strip.frame = (m, y, w - 2 * m, 64)
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
        self.status.text = "Turn %d · Tavern %d · Discard %d" % (g.turn, len(g.tavern), len(g.discard))
        if g.n_players == 1:
            self.status.text += " · Jesters %d" % g.solo_jesters
        self.enemy.game = g
        self.enemy.set_needs_display()
        played = [g.card(c) for p in g.plays for c in p.card_ids]
        self.strip.set_cards(played, "Played against this enemy")
        self.strip.set_needs_display()
        if g.is_over:
            self._show_overlay(ResultOverlay(self))
            return
        if g.phase == PHASE_CHOOSE_NEXT:
            self._show_overlay(ChooseNextOverlay(self))
            return
        needs_handover = (g.n_players > 1 and not g.config.open_hands and self.shown_player != g.active)
        if needs_handover:
            self.hand.set_cards([])
            self._show_overlay(HandoverOverlay(self))
            return
        self._hide_overlay()
        self.shown_player = g.active
        self.hand.set_cards(g.hand(), keep_selection=False)
        self._update_controls()

    def reveal_hand(self) -> None:
        self.shown_player = self.game.active
        self.refresh(after_action=False)

    def _update_controls(self) -> None:
        g = self.game
        sel = list(self.hand.selected)
        name = g.active_player.name
        if g.phase == PHASE_PLAY:
            self.hand.selectable = lambda c: True
            self.left_btn.title = "Yield"
            set_enabled(self.left_btn, g.can_yield(), False)
            self.mid_btn.title = "Jester power" if g.n_players == 1 else "Hint"
            if g.n_players == 1:
                self.mid_btn.hidden = False
                set_enabled(self.mid_btn, g.can_use_solo_jester(), False)
            else:
                self.mid_btn.hidden = not self.app.settings.get("show_hints", True)
                set_enabled(self.mid_btn, True, False)
            self.right_btn.title = "Play"
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
            self.left_btn.title = "Suggest"
            set_enabled(self.left_btn, True, False)
            self.mid_btn.title = "Jester power"
            self.mid_btn.hidden = g.n_players != 1
            set_enabled(self.mid_btn, g.can_use_solo_jester(), False)
            self.right_btn.title = "Discard"
            set_enabled(self.right_btn, total >= need and need > 0)
            self.message.text = "%s suffers %d damage. Select cards worth at least %d (selected: %d)." % (
                name, need, need, total)
            if g.hand_defence_value() < need and g.can_use_solo_jester():
                self.message.text += " Your hand is short: use the Jester power."
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
            self.hand.set_selection(min_waste_discard(g))

    def _mid(self, sender) -> None:
        g = self.game
        if g.n_players == 1 or g.phase == PHASE_SUFFER:
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

    def choose_next(self, player: int) -> None:
        g = self.game
        self._act(lambda: g.choose_next(player))

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


class ChooseNextOverlay(Overlay):
    def build(self) -> List[ui.View]:
        g = self.screen.game
        items: List[ui.View] = [
            make_label("Jester!", (0, 0, 10, 36), 24, True, T.ACCENT, ui.ALIGN_CENTER),
            make_label("%s chooses who goes next. Players may say if they would like to go." % g.active_player.name,
                       (0, 0, 10, 60), 14, False, T.TEXT, ui.ALIGN_CENTER, 3),
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
            self.screen.shown_player = None if (app.game.n_players > 1 and not app.game.config.open_hands) else app.game.active
            self.screen.message_text = "Undone."
            self.screen.refresh(after_action=False)

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
    return s


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
        self.add_subview(make_button("‹ Back", lambda s: self.app.show(MenuScreen(self.app)), (m, y, 80, 36), False, 14))
        self.add_subview(make_label(self.title, (100, y, w - 200, 36), 20, True, T.TEXT, ui.ALIGN_CENTER))
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
        self.add_subview(make_label("Settings", (100, y, w - 200, 36), 20, True, T.TEXT, ui.ALIGN_CENTER))
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
