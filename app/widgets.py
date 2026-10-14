"""Custom views: cards, the enemy panel, the hand grid, buttons.

Everything is drawn with ``ui.Path`` and ``ui.draw_string`` so no image assets are
needed and nothing from the published games is copied.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence

import ui

from regicide.cards import BASIC_SUITS, CLASS_NAME, SUIT_NAME, SUIT_SYMBOL, Card
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


def fit_title(b: ui.Button, max_size: float = 0, min_size: float = 11) -> None:
    """Shrink a button's title font until the title fits its width (UIButton would cut it
    in the middle otherwise)."""
    name, size = b.font if b.font else (T.FONT_BOLD, 16)
    size = float(max_size or size)
    room = b.width - 10
    while size > min_size and text_size(b.title or "", 0, size, True)[0] > room:
        size -= 1
    b.font = (name, size)


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


def text_size(text: str, max_width: float, size: float, bold: bool = False) -> tuple:
    """(width, height) of ``text`` wrapped at ``max_width`` (0: one line) in the app font:
    ``ui.measure_string`` where the ui module has it (Pythonista, the fake ui), else an
    estimate of 0.55 x the font size per character and 1.25 x the size per line."""
    measure = getattr(ui, "measure_string", None)
    if measure is not None:
        w, h = measure(text, max_width, (T.FONT_BOLD if bold else T.FONT, size))
        return (float(w), float(h))
    per_char = 0.55 * size
    lines = 0
    widest = 0.0
    for para in str(text).split("\n"):
        wide = len(para) * per_char
        if max_width and wide > max_width:
            lines += int(math.ceil(wide / float(max_width)))
            widest = max(widest, float(max_width))
        else:
            lines += 1
            widest = max(widest, wide)
    return (widest, lines * size * 1.25)


def fit_label(text: str, width: float, size: int = 13, bold: bool = False, color: str = T.TEXT,
              align=None, min_height: float = 0) -> ui.Label:
    """A label as tall as its text wrapped at ``width`` (overlay instructions): nothing is
    cut off whatever the text's length."""
    _, h = text_size(text, width, size, bold)
    return make_label(text, (0, 0, width, max(min_height, math.ceil(h) + 4)), size, bold, color, align, 0)


def card_color(card: Card) -> str:
    if card.is_jester:
        return T.JESTER_COLOR
    if all_classes(card):
        return T.EVERGREEN
    if card.suits:
        return T.SUIT_COLOR.get(card.suits[0], T.TEXT)
    return "#444444"


TREE_PIP = "tree"   # pseudo-suit: the Evergreen tree, standing for the four basic classes


def all_classes(card: Card) -> bool:
    """Whether the card is an Evergreen card (the renewed Gøran, Esme): a cleric, bard,
    warrior and paladin at once, ignoring immunity. Restored cards keep their own classes."""
    return card.has("evergreen") and all(s in card.suits for s in BASIC_SUITS)


def face_pips(card: Card) -> List[str]:
    """The class pips on a card's face. On an Evergreen card the tree replaces the four
    basic class icons (owner: the tree represents the four base classes); any other class
    keeps its own icon beside it."""
    suits = list(card.suits)
    if all_classes(card):
        return [TREE_PIP] + [s for s in suits if s not in BASIC_SUITS]
    return suits


def sleeve_color(card: Card) -> str:
    """The sleeve a card sits in: purple when corrupted, green when restored, none otherwise."""
    if card.has("corrupted"):
        return T.CORRUPTED
    if card.has("restored"):
        return T.RESTORED
    return ""


def draw_tree(x: float, y: float, w: float, h: float, color: str) -> None:
    """The restoration icon: a small geometric tree (three stacked triangles on a trunk)
    filling the box (x, y, w, h)."""
    ui.set_color(color)
    cx = x + w / 2.0
    for apex, base, half in ((0.0, 0.42, 0.26), (0.2, 0.62, 0.36), (0.4, 0.82, 0.46)):
        t = ui.Path()
        t.move_to(cx, y + h * apex)
        t.line_to(cx + w * half, y + h * base)
        t.line_to(cx - w * half, y + h * base)
        t.close()
        t.fill()
    ui.Path.rect(cx - w * 0.08, y + h * 0.8, w * 0.16, h * 0.2).fill()


def card_caption(card: Card) -> str:
    """The small word under a card's pips: a story character's name, "pilgrim" on a
    pilgrim, "any class" on a Wild Animal; nothing on a plain card. An enemy card (a royal)
    shows its value there instead: its name is on the enemy panel."""
    if card.is_royal:
        return ""
    if card.name:
        return card.name
    if card.has("pilgrim") or card.has("evergreen_puppy"):
        return "pilgrim"
    if card.has("choosable"):
        return "any class"
    return ""


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
        W, H = self.width, self.height
        r = max(6.0, min(W, H) * 0.12)
        if not self.face_up:
            ui.set_color(T.CARD_BACK)
            ui.Path.rounded_rect(1, 1, W - 2, H - 2, r).fill()
            ui.set_color("#7c6bc2")
            ui.Path.rounded_rect(5, 5, W - 10, H - 10, r * 0.7).stroke()
            return
        c = self.card
        # Sleeves, as on the physical cards: a corrupted card sits in a purple sleeve, a
        # restored one in a green sleeve. The sleeve is a thick coloured edge around the face.
        sleeve = sleeve_color(c)
        sw = max(2.5, min(W, H) * 0.08) if sleeve else 0.0
        if sleeve:
            ui.set_color(sleeve)
            ui.Path.rounded_rect(1, 1, W - 2, H - 2, r).fill()
        ui.set_color(T.CARD_FACE_DIM if self.dimmed else T.CARD_FACE)
        ui.Path.rounded_rect(1 + sw, 1 + sw, W - 2 - 2 * sw, H - 2 - 2 * sw, max(3.0, r - sw * 0.6)).fill()
        if self.selected or not sleeve:
            border = ui.Path.rounded_rect(1.5, 1.5, W - 3, H - 3, r)
            border.line_width = 3 if self.selected else 1
            ui.set_color(T.ACCENT if self.selected else T.CARD_BORDER)
            border.stroke()
        # everything below is drawn inside the face (the sleeve's inner edge)
        ox, oy = sw, sw
        w, h = W - 2 * sw, H - 2 * sw
        col = card_color(c)
        if c.is_jester:
            ui.draw_string("J", (ox, oy + h * 0.12, w, h * 0.4), (T.FONT_BOLD, h * 0.34), col, ui.ALIGN_CENTER)
            ui.draw_string("JESTER", (ox, oy + h * 0.62, w, h * 0.3), (T.FONT_BOLD, max(8, h * 0.12)), col, ui.ALIGN_CENTER)
            return
        # Themeless faces: rank and class like a playing card. A beast is a plain "B" with
        # its class; a classless card (a pilgrim, a 19) shows its rank large in the middle.
        # Only the story characters (Gøran, Myla, Esme, the High Arcana) carry a name, and a
        # pilgrim or a Wild Animal a one-word reminder of what it is. Each class pip is drawn
        # in its own colour and shrinks so that four (an Evergreen card) still fit. A
        # restored card adds the restoration pip, a small tree, after its classes.
        rank = "2/5" if c.has("twofive") else c.rank
        suits = list(c.suits)
        pips = face_pips(c)
        caption = card_caption(c)
        if self.small:
            # a tag (an order number, a Druid's slot) takes a band along the bottom and the
            # rank and pips move up above it
            band = max(9.0, h * 0.24) if self.badge else 0.0
            a = h - band
            if suits:
                ui.draw_string(rank, (ox, oy + a * 0.08, w, a * 0.45), (T.FONT_BOLD, a * 0.36), col, ui.ALIGN_CENTER)
                self._pips(pips, ox + 2, oy + a * 0.5, w - 4, a * 0.34, ui.ALIGN_CENTER)
            else:
                ui.draw_string(rank, (ox, oy + a * 0.27, w, a * 0.46), (T.FONT_BOLD, a * 0.36), col, ui.ALIGN_CENTER)
            if self.badge:
                text = str(self.badge)
                size = max(7.0, min(band * 0.62, (w - 2) / (0.62 * max(1, len(text)))))
                ui.set_color(T.ACCENT)
                ui.Path.rounded_rect(ox + 1, oy + h - band - 1, w - 2, band, 3).fill()
                ui.draw_string(text, (ox + 1, oy + h - band - 1 + (band - size * 1.2) / 2.0, w - 2, size * 1.3),
                               (T.FONT_BOLD, size), T.BG, ui.ALIGN_CENTER)
            return
        badge = self.badge
        band = max(12.0, h * 0.13) if badge else 0.0
        bottom = h - 3 - band                      # a tag ("stuck", "flute", an order) sits at the bottom
        cap_h = h * 0.17
        ui.draw_string(rank, (ox + 5, oy + 3, w - 10, h * 0.3), (T.FONT_BOLD, h * 0.22), col, ui.ALIGN_LEFT)
        low = bottom - (cap_h if (caption or c.is_royal) else 2)
        if suits:
            self._pips(pips, ox + 5, oy + h * 0.22, w - 10, h * 0.16, ui.ALIGN_LEFT)
            top = h * 0.38
            size = min(h * 0.42, (low - top) * 0.85)
            size = min(size, min(size * 0.95, (w - 8) / float(len(pips))) / 0.95)   # as _pips shrinks it
            self._pips(pips, ox + 4, oy + top + max(0.0, (low - top) - size * 1.15) / 2.0, w - 8, size, ui.ALIGN_CENTER)
        else:
            top = h * 0.36
            size = min(h * 0.32, (low - top) * 0.8)
            ui.draw_string(rank, (ox, oy + top + max(0.0, (low - top) - size * 1.2) / 2.0, w, size * 1.3),
                           (T.FONT_BOLD, size), col, ui.ALIGN_CENTER)
        if caption:
            ui.draw_string(caption, (ox + 2, oy + bottom - cap_h, w - 4, cap_h), (T.FONT, max(8, h * 0.1)), "#333333",
                           ui.ALIGN_CENTER)
        if c.is_royal:
            ui.draw_string("%d" % c.value, (ox, oy + bottom - cap_h, w - 5, cap_h), (T.FONT_BOLD, h * 0.12), col,
                           ui.ALIGN_RIGHT)
        if badge:
            ui.set_color(T.ACCENT)
            ui.Path.rounded_rect(ox + 3, oy + h - 3 - band, w - 6, band, 4).fill()
            ui.draw_string(badge, (ox + 3, oy + h - 3 - band, w - 6, band), (T.FONT_BOLD, max(8, h * 0.09)), T.BG,
                           ui.ALIGN_CENTER)

    @staticmethod
    def _pips(pips, x: float, y: float, width: float, size: float, align) -> None:
        """Class symbols in a row, each in its own colour, shrunk to fit ``width``; the
        restoration pip is drawn as a small geometric tree."""
        if not pips:
            return
        step = min(size * 0.95, width / float(len(pips)))
        size = min(size, step / 0.95)
        total = step * len(pips)
        x0 = x + (width - total) / 2.0 if align == ui.ALIGN_CENTER else x
        for i, s in enumerate(pips):
            if s == TREE_PIP:
                draw_tree(x0 + i * step + step * 0.08, y + size * 0.18, step * 0.84, size * 0.92, T.EVERGREEN)
                continue
            ui.draw_string(SUIT_SYMBOL.get(s, s), (x0 + i * step, y, step, size * 1.3), (T.FONT_BOLD, size),
                           T.SUIT_COLOR.get(s, T.TEXT), ui.ALIGN_CENTER)

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
        sleeve = sleeve_color(card)   # a corrupted enemy (an experiment, a royal) sits in a purple sleeve
        sw = max(2.5, cw * 0.08) if sleeve else 0.0
        if sleeve:
            ui.set_color(sleeve)
            ui.Path.rounded_rect(cx, cy, cw, ch, 8).fill()
            ui.set_color(T.CARD_FACE)
            ui.Path.rounded_rect(cx + sw, cy + sw, cw - 2 * sw, ch - 2 * sw, max(3.0, 8 - sw * 0.6)).fill()
        else:
            ui.set_color(T.CARD_FACE)
            ui.Path.rounded_rect(cx, cy, cw, ch, 8).fill()
            ui.set_color(T.CARD_BORDER)
            ui.Path.rounded_rect(cx + 0.5, cy + 0.5, cw - 1, ch - 1, 8).stroke()
        sym = "".join(SUIT_SYMBOL.get(s, s) for s in card.suits)
        ui.draw_string(card.rank, (cx + 4 + sw, cy + 2 + sw, cw, 26), (T.FONT_BOLD, 22), col)
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
        bonus = g.rules.attack_bonus(g)
        atk_text = "Attack %d" % atk
        if sh or bonus:
            detail = "%d" % e.attack
            if bonus:
                detail += " + %d" % bonus   # Legacy mission bonus (discard top, mission zone)
            if sh:
                detail += " − %d shield" % sh
            atk_text += "  (%s)" % detail
        ui.draw_string(atk_text, (tx, 60, tw, 20), (T.FONT_BOLD, 15), T.TEXT)
        imm, icol = self.immunity_text(g)
        # The immunity line wraps onto a second line in a smaller font when it is long (a
        # mission zone can make an enemy immune to five classes); the castle count follows.
        size = 13
        _, ih = text_size(imm, tw, size)
        if ih > 20:
            size = 11
            _, ih = text_size(imm, tw, size)
        ih = min(max(ih, 16.0), 30.0)
        iy = 80 if ih <= 20 else 79
        ui.draw_string(imm, (tx, iy, tw, ih), (T.FONT, size), icol)
        castle = "%d more in the castle" % len(g.castle)
        if getattr(g.rules, "mission", 0) == 10 and g.castle:
            # mission 10's enemy deck is face up, 2 on top down to 9: the next one is known
            castle += " · next: %s" % g.card(g.castle[0]).label()
        ui.draw_string(castle, (tx, iy + ih + 1, tw, 16), (T.FONT, 11 if size == 11 else 12), T.MUTED)

    @staticmethod
    def immunity_text(g: Game) -> tuple:
        """(text, colour) of the immunity line."""
        if g.immunity_cancelled:
            return "Immunity cancelled by the Jester", T.OK
        if g.rules.immune_suits(g):
            legacy = bool(getattr(g.rules, "legacy", False))
            names = [(CLASS_NAME.get(s, s) + "s") if legacy else SUIT_NAME.get(s, s) for s in g.rules.immune_suits(g)]
            return "Immune to %s" % " / ".join(names), T.MUTED
        return "No immunity", T.MUTED


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
    """Small face-up cards in a row (cards played against the enemy, etc.). The title takes
    one line, or two when it is long (a mission zone's effects); the cards shrink to fit."""

    TITLE_FONT = 11
    LINE = 14

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.cards: List[Card] = []
        self.background_color = None
        self.title = ""
        self.dimmed: List[str] = []   # ids drawn greyed out (e.g. revealed cards that may not be picked)

    def title_height(self) -> float:
        """The room the title takes: one line (14pt) or two (28pt)."""
        if not self.title:
            return 0.0
        _, h = text_size(self.title, max(1.0, self.width - 8), self.TITLE_FONT)
        return float(self.LINE if h <= self.LINE * 1.4 else 2 * self.LINE)

    def set_cards(self, cards: Sequence[Card], title: str = "", dimmed: Sequence[str] = ()) -> None:
        for v in list(self.subviews):
            self.remove_subview(v)
        self.cards = list(cards)
        self.title = title
        self.dimmed = list(dimmed)
        self.layout()

    def layout(self) -> None:
        if not hasattr(self, "cards"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        n = len(self.cards)
        if not n:
            return
        top = self.title_height() + 2 if self.title else 16
        ch = max(20.0, self.height - top - 2)
        cw = ch / 1.42
        gap = 6.0
        max_w = self.width - 8
        step = cw + gap
        if n * step - gap > max_w:
            step = (max_w - cw) / max(1, n - 1)
        for i, c in enumerate(self.cards):
            v = CardView(c)
            v.small = True
            v.dimmed = c.id in self.dimmed
            v.touch_enabled = False
            v.frame = (4 + i * step, top, cw, ch)
            self.add_subview(v)

    def draw(self) -> None:
        th = self.title_height()
        if self.title:
            ui.draw_string(self.title, (4, 0, self.width - 8, th), (T.FONT, self.TITLE_FONT), T.MUTED)
        if not self.cards:
            ui.draw_string("nothing played yet", (4, max(20.0, th + 4), self.width - 8, 20), (T.FONT, 12), T.MUTED)
