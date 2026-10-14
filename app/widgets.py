"""Custom views: cards, the enemy panel, the hand grid, buttons.

Everything is drawn with ``ui.Path`` and ``ui.draw_string`` so no image assets are
needed and nothing from the published games is copied.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence

import ui

from regicide.cards import CLASS_NAME, SUIT_NAME, SUIT_SYMBOL, Card
from regicide.engine import Enemy, Game

from . import theme as T


def make_button(title: str, action: Callable, frame=(0, 0, 100, 44), primary: bool = True,
                font_size: int = 16) -> ui.Button:
    b = ui.Button(frame=frame)
    b.title = title
    b.action = action
    b.font = (T.FONT_BOLD, font_size)
    b.background_color = T.BTN if primary else T.PANEL_2
    b.tint_color = T.BTN_TEXT
    b.corner_radius = 10
    return b


def set_enabled(b: ui.Button, on: bool, primary: bool = True) -> None:
    b.enabled = on
    b.background_color = (T.BTN if primary else T.PANEL_2) if on else T.BTN_DISABLED
    b.tint_color = T.BTN_TEXT if on else T.MUTED


def make_label(text: str, frame, size: int = 15, bold: bool = False, color: str = T.TEXT,
               align=None, lines: int = 1) -> ui.Label:
    l = ui.Label(frame=frame)
    l.text = text
    l.font = (T.FONT_BOLD if bold else T.FONT, size)
    l.text_color = color
    l.alignment = ui.ALIGN_LEFT if align is None else align
    l.number_of_lines = lines
    return l


def card_color(card: Card) -> str:
    if card.is_jester:
        return T.JESTER_COLOR
    if card.suits:
        return T.SUIT_COLOR.get(card.suits[0], T.TEXT)
    return "#444444"


class CardView(ui.View):
    """A playing card. Tap toggles selection through ``on_tap``."""

    def __init__(self, card: Card, on_tap: Optional[Callable[["CardView"], None]] = None, **kw) -> None:
        super().__init__(**kw)
        self.card = card
        self.on_tap = on_tap
        self.selected = False
        self.dimmed = False
        self.face_up = True
        self.small = False
        self.badge = ""
        self.background_color = None  # drawn in draw()

    def draw(self) -> None:
        w, h = self.width, self.height
        r = max(6.0, min(w, h) * 0.12)
        if not self.face_up:
            ui.set_color(T.CARD_BACK)
            ui.Path.rounded_rect(1, 1, w - 2, h - 2, r).fill()
            ui.set_color("#7c6bc2")
            ui.Path.rounded_rect(5, 5, w - 10, h - 10, r * 0.7).stroke()
            return
        ui.set_color(T.CARD_FACE_DIM if self.dimmed else T.CARD_FACE)
        ui.Path.rounded_rect(1, 1, w - 2, h - 2, r).fill()
        border = ui.Path.rounded_rect(1.5, 1.5, w - 3, h - 3, r)
        border.line_width = 3 if self.selected else 1
        ui.set_color(T.ACCENT if self.selected else T.CARD_BORDER)
        border.stroke()
        c = self.card
        col = card_color(c)
        if c.is_jester:
            ui.draw_string("J", (0, h * 0.12, w, h * 0.4), (T.FONT_BOLD, h * 0.34), col, ui.ALIGN_CENTER)
            ui.draw_string("JESTER", (0, h * 0.62, w, h * 0.3), (T.FONT_BOLD, max(8, h * 0.12)), col, ui.ALIGN_CENTER)
            return
        rank = c.rank
        sym = "".join(SUIT_SYMBOL.get(s, s) for s in c.suits)
        if self.small:
            ui.draw_string(rank, (0, h * 0.08, w, h * 0.45), (T.FONT_BOLD, h * 0.36), col, ui.ALIGN_CENTER)
            ui.draw_string(sym, (0, h * 0.5, w, h * 0.45), (T.FONT_BOLD, h * 0.34), col, ui.ALIGN_CENTER)
            return
        ui.draw_string(rank, (5, 3, w - 10, h * 0.3), (T.FONT_BOLD, h * 0.22), col, ui.ALIGN_LEFT)
        ui.draw_string(sym, (5, h * 0.22, w - 10, h * 0.25), (T.FONT_BOLD, h * 0.16), col, ui.ALIGN_LEFT)
        ui.draw_string(sym, (0, h * 0.38, w, h * 0.45), (T.FONT_BOLD, h * 0.42), col, ui.ALIGN_CENTER)
        if c.name:
            ui.draw_string(c.name, (2, h * 0.8, w - 4, h * 0.18), (T.FONT, max(8, h * 0.1)), "#333333", ui.ALIGN_CENTER)
        if c.is_royal:
            ui.draw_string("%d" % c.value, (0, h * 0.8, w - 5, h * 0.18), (T.FONT_BOLD, h * 0.12), col, ui.ALIGN_RIGHT)
        badge = self.badge or ("corrupted" if c.has("corrupted") else "restored" if c.has("restored") else "")
        if badge:
            ui.set_color("#5a1f6b" if badge == "corrupted" else "#1f6b3a" if badge == "restored" else T.ACCENT)
            ui.Path.rounded_rect(3, 3, w - 6, max(12, h * 0.13), 4).fill()
            ui.draw_string(badge, (3, 3, w - 6, max(12, h * 0.13)), (T.FONT_BOLD, max(8, h * 0.09)),
                           "white" if badge in ("corrupted", "restored") else T.BG, ui.ALIGN_CENTER)

    def touch_ended(self, touch) -> None:
        x, y = touch.location
        if 0 <= x <= self.width and 0 <= y <= self.height and self.on_tap:
            self.on_tap(self)


class EnemyPanel(ui.View):
    """Current enemy with health bar, attack after shields, immunity state."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.game: Optional[Game] = None
        self.background_color = T.PANEL
        self.corner_radius = 12

    def draw(self) -> None:
        g = self.game
        w, h = self.width, self.height
        if g is None or g.enemy is None:
            ui.draw_string("No enemy", (0, h / 2 - 12, w, 24), (T.FONT_BOLD, 18), T.MUTED, ui.ALIGN_CENTER)
            return
        e: Enemy = g.enemy
        card = g.card(e.card_id)
        col = card_color(card)
        # card on the left
        cw, ch = min(78.0, w * 0.22), min(110.0, h - 16)
        cx, cy = 10, (h - ch) / 2
        ui.set_color(T.CARD_FACE)
        ui.Path.rounded_rect(cx, cy, cw, ch, 8).fill()
        ui.set_color(T.CARD_BORDER)
        ui.Path.rounded_rect(cx + 0.5, cy + 0.5, cw - 1, ch - 1, 8).stroke()
        sym = "".join(SUIT_SYMBOL.get(s, s) for s in card.suits)
        ui.draw_string(card.rank, (cx + 4, cy + 2, cw, 26), (T.FONT_BOLD, 22), col)
        ui.draw_string(sym, (cx, cy + ch * 0.32, cw, ch * 0.5), (T.FONT_BOLD, ch * 0.4), col, ui.ALIGN_CENTER)
        # text block
        tx = cx + cw + 12
        tw = w - tx - 10
        ui.draw_string(e.name, (tx, 8, tw, 24), (T.FONT_BOLD, 18), T.TEXT)
        # health bar
        hp = max(0, e.hp)
        frac = hp / float(e.max_hp) if e.max_hp else 0
        bx, by, bw, bh = tx, 38, tw, 16
        ui.set_color("#3b2f2f")
        ui.Path.rounded_rect(bx, by, bw, bh, 8).fill()
        ui.set_color(T.DANGER if frac > 0.5 else "#e09a3f" if frac > 0.25 else T.OK)
        if frac > 0:
            ui.Path.rounded_rect(bx, by, max(bh, bw * frac), bh, 8).fill()
        ui.draw_string("Health %d / %d" % (hp, e.max_hp), (bx, by - 1, bw, bh + 2), (T.FONT_BOLD, 12), T.TEXT, ui.ALIGN_CENTER)
        atk = g.enemy_attack
        sh = g.shield
        atk_text = "Attack %d" % atk
        if sh:
            atk_text += "  (%d − %d shield)" % (e.attack + g.rules.attack_bonus(g), sh)
        ui.draw_string(atk_text, (tx, 60, tw, 20), (T.FONT_BOLD, 15), T.TEXT)
        if g.immunity_cancelled:
            imm = "Immunity cancelled by the Jester"
            icol = T.OK
        elif e.suits:
            legacy = g.config.rules_id.startswith("legacy")
            names = [(CLASS_NAME.get(s, s) + "s") if legacy else SUIT_NAME.get(s, s) for s in e.suits]
            imm = "Immune to %s" % " / ".join(names)
            icol = T.MUTED
        else:
            imm = "No immunity"
            icol = T.MUTED
        ui.draw_string(imm, (tx, 82, tw, 20), (T.FONT, 13), icol)
        ui.draw_string("%d more in the castle" % len(g.castle), (tx, 102, tw, 18), (T.FONT, 12), T.MUTED)


class HandGrid(ui.View):
    """Cards laid out in rows of four. Taps toggle selection and report through ``on_change``."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.cards: List[Card] = []
        self.views: Dict[str, CardView] = {}
        self.selected: List[str] = []
        self.on_change: Optional[Callable[[], None]] = None
        self.selectable: Callable[[Card], bool] = lambda c: True
        self.badges: Dict[str, str] = {}
        self.background_color = None
        self.columns = 4

    def set_cards(self, cards: Sequence[Card], keep_selection: bool = False) -> None:
        for v in list(self.subviews):
            self.remove_subview(v)
        self.views = {}
        self.cards = list(cards)
        if not keep_selection:
            self.selected = []
        else:
            ids = set(c.id for c in cards)
            self.selected = [s for s in self.selected if s in ids]
        for c in self.cards:
            v = CardView(c, on_tap=self._tapped)
            v.selected = c.id in self.selected
            v.badge = self.badges.get(c.id, "")
            self.views[c.id] = v
            self.add_subview(v)
        self.layout()

    def layout(self) -> None:
        if not hasattr(self, "views"):
            return
        n = len(self.cards)
        if not n:
            return
        cols = self.columns if n > 3 else max(1, n)
        rows = int(math.ceil(n / float(cols)))
        gap = 8.0
        cw = (self.width - gap * (cols - 1)) / cols
        ch = min(cw * 1.42, (self.height - gap * (rows - 1) - 8) / rows)
        cw = min(cw, ch / 1.42)
        total_w = cols * cw + gap * (cols - 1)
        x0 = (self.width - total_w) / 2
        for i, c in enumerate(self.cards):
            r, col = divmod(i, cols)
            v = self.views[c.id]
            lift = 8 if v.selected else 0
            v.frame = (x0 + col * (cw + gap), 8 + r * (ch + gap) - lift, cw, ch)

    def _tapped(self, v: CardView) -> None:
        if not self.selectable(v.card):
            return
        if v.card.id in self.selected:
            self.selected.remove(v.card.id)
            v.selected = False
        else:
            self.selected.append(v.card.id)
            v.selected = True
        self.layout()
        v.set_needs_display()
        if self.on_change:
            self.on_change()

    def set_selection(self, ids: Sequence[str]) -> None:
        self.selected = [i for i in ids if i in self.views]
        for cid, v in self.views.items():
            v.selected = cid in self.selected
            v.set_needs_display()
        self.layout()
        if self.on_change:
            self.on_change()

    def clear_selection(self) -> None:
        self.set_selection([])

    def refresh_dim(self) -> None:
        for c, v in ((c, self.views[c.id]) for c in self.cards):
            v.dimmed = not self.selectable(c)
            v.set_needs_display()


class CardStrip(ui.View):
    """Small face-up cards in a row (cards played against the enemy, etc.)."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.cards: List[Card] = []
        self.background_color = None
        self.title = ""

    def set_cards(self, cards: Sequence[Card], title: str = "") -> None:
        for v in list(self.subviews):
            self.remove_subview(v)
        self.cards = list(cards)
        self.title = title
        self.layout()

    def layout(self) -> None:
        if not hasattr(self, "cards"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        n = len(self.cards)
        if not n:
            return
        ch = self.height - 18
        cw = ch / 1.42
        gap = 6.0
        max_w = self.width - 8
        step = cw + gap
        if n * step - gap > max_w:
            step = (max_w - cw) / max(1, n - 1)
        for i, c in enumerate(self.cards):
            v = CardView(c)
            v.small = True
            v.touch_enabled = False
            v.frame = (4 + i * step, 16, cw, ch)
            self.add_subview(v)

    def draw(self) -> None:
        if self.title:
            ui.draw_string(self.title, (4, 0, self.width - 8, 14), (T.FONT, 11), T.MUTED)
        if not self.cards:
            ui.draw_string("nothing played yet", (4, 20, self.width - 8, 20), (T.FONT, 12), T.MUTED)
