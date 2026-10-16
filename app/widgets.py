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


def fit_title(b: ui.Button, max_size: float = 0, min_size: float = 11, bold: bool = True) -> None:
    """Shrink a button's title font until the title fits its width (UIButton would cut it
    in the middle otherwise). The font is always set by the app's own names: on iOS,
    reading ``b.font`` back gives the system font's internal name (".SFUI-…"), which
    can't be set again and falls back to a serif font."""
    size = float(max_size or (b.font[1] if b.font else 16))
    room = b.width - 10
    while size > min_size and text_size(b.title or "", 0, size, bold)[0] > room:
        size -= 1
    b.font = (T.FONT_BOLD if bold else T.FONT, size)


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


# Card faces (a setting): "simple" draws the number, a small class icon and one big icon;
# "classic" lays numbered cards out like playing cards (a 7 shows seven icons, the number
# and icon in two corners, the lower half turned) and gives a royal a big letter.
FACE_STYLE = "simple"
CLASSIC_MIN_WIDTH = 54.0   # narrower cards (a 320-pt phone's hand) keep the simple face: too small to read

# pip positions (x, y in 0..1 of the pip area), the standard playing-card layouts
_PL, _PR = 0.18, 0.82
PIP_LAYOUT = {
    2: [(0.5, 0.0), (0.5, 1.0)],
    3: [(0.5, 0.0), (0.5, 0.5), (0.5, 1.0)],
    4: [(_PL, 0.0), (_PR, 0.0), (_PL, 1.0), (_PR, 1.0)],
    5: [(_PL, 0.0), (_PR, 0.0), (0.5, 0.5), (_PL, 1.0), (_PR, 1.0)],
    6: [(_PL, 0.0), (_PR, 0.0), (_PL, 0.5), (_PR, 0.5), (_PL, 1.0), (_PR, 1.0)],
    7: [(_PL, 0.0), (_PR, 0.0), (0.5, 0.25), (_PL, 0.5), (_PR, 0.5), (_PL, 1.0), (_PR, 1.0)],
    8: [(_PL, 0.0), (_PR, 0.0), (0.5, 0.25), (_PL, 0.5), (_PR, 0.5), (0.5, 0.75), (_PL, 1.0), (_PR, 1.0)],
    9: [(_PL, 0.0), (_PR, 0.0), (_PL, 1 / 3.0), (_PR, 1 / 3.0), (0.5, 0.5), (_PL, 2 / 3.0), (_PR, 2 / 3.0),
        (_PL, 1.0), (_PR, 1.0)],
    10: [(_PL, 0.0), (_PR, 0.0), (0.5, 1 / 6.0), (_PL, 1 / 3.0), (_PR, 1 / 3.0), (_PL, 2 / 3.0), (_PR, 2 / 3.0),
         (0.5, 5 / 6.0), (_PL, 1.0), (_PR, 1.0)],
}


def classic_kind(card: Card) -> str:
    """How a card is drawn with classic faces: "pips" (an ace to a 10 with a class, its
    value as printed), "royal" (a Jack, Queen or King: a big letter) or "" (the simple face:
    cards above 10, beasts, 2/5s, Wild Animals, Jesters, classless and named cards)."""
    if card.is_jester or card.name or card.has("twofive") or card.has("choosable"):
        return ""
    if card.is_royal:
        return "royal"
    if not card.suits:
        return ""
    if card.rank == "A" and card.value == 1:
        return "pips"
    if card.rank.isdigit() and 2 <= int(card.rank) <= 10 and card.value == int(card.rank):
        return "pips"
    return ""


def turned(cx: float, cy: float):
    """Draw the next things turned upside down about (cx, cy): ``with turned(x, y):`` then
    draw centred on (0, 0). Without transforms (an old ui module) they stay upright."""
    import contextlib

    @contextlib.contextmanager
    def ctx():
        if not (hasattr(ui, "GState") and hasattr(ui, "concat_ctm") and hasattr(ui, "Transform")):
            yield False
            return
        with ui.GState():
            ui.concat_ctm(ui.Transform.translation(cx, cy))
            ui.concat_ctm(ui.Transform.rotation(math.pi))
            yield True
    return ctx()


def draw_symbol(sym: str, cx: float, cy: float, size: float, color: str, upside_down: bool = False) -> None:
    """One class icon (or the Evergreen tree) of font size ``size`` centred on (cx, cy)."""
    def draw(x: float, y: float) -> None:
        if sym == TREE_PIP:
            draw_tree(x - size * 0.45, y - size * 0.5, size * 0.9, size, T.EVERGREEN)
            return
        ui.draw_string(SUIT_SYMBOL.get(sym, sym), (x - size, y - size * 0.62, size * 2, size * 1.3),
                       (T.FONT_BOLD, size), T.SUIT_COLOR.get(sym, color), ui.ALIGN_CENTER)
    if upside_down:
        with turned(cx, cy) as ok:
            if ok:
                draw(0.0, 0.0)
                return
    draw(cx, cy)


def card_caption(card: Card) -> str:
    """The small word under a card's pips: a story character's name, "pilgrim" on a
    pilgrim; nothing on a plain card (a Wild Animal shows a class icon in each corner). An enemy card (a royal)
    shows its value there instead: its name is on the enemy panel."""
    if card.is_royal:
        return ""
    if card.name:
        return card.name
    if card.has("pilgrim") or card.has("evergreen_puppy"):
        return "pilgrim"
    return ""


def coin_metrics(W: float, H: float) -> tuple:
    """(diameter, right padding) of the coins on a card W x H."""
    return (min(W * 0.17, H * 0.105), max(3.0, W * 0.05))


def draw_coin(x: float, y: float, d: float) -> None:
    """One gold coin, diameter ``d``, top-left corner at (x, y)."""
    ui.set_color(T.COIN_RIM)
    ui.Path.oval(x, y, d, d).fill()
    ui.set_color(T.COIN)
    inset = max(1.0, d * 0.1)
    ui.Path.oval(x + inset, y + inset, d - 2 * inset, d - 2 * inset).fill()
    ring = ui.Path.oval(x + d * 0.27, y + d * 0.27, d * 0.46, d * 0.46)
    ring.line_width = max(1.0, d * 0.08)
    ui.set_color(T.COIN_RIM)
    ring.stroke()


def draw_coin_column(n: int, W: float, H: float) -> None:
    """A mercenary's cost: ``n`` coins down the right side of a card W x H, from just below
    where a corner class icon sits (the Wild Animal's top-right icon), the same place on
    every card."""
    d, pad = coin_metrics(W, H)
    step = d * 1.12
    x = W - pad - d
    y = max(H * 0.24, pad * 0.5 + H * 0.16 * 1.3 + 2)
    # keep five coins clear of the bottom corner
    if y + step * n > H - pad:
        step = max(d * 0.8, (H - pad - y) / float(n))
    for i in range(int(n)):
        draw_coin(x, y + i * step, d)


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
        self.order = 0                # selection order shown top right (0: none)
        self.shaded = False           # greyed out (a mercenary still in the box), coins stay bright
        self.coins = 0                # a mercenary's cost, drawn as coins down the right side
        self.background_color = None  # drawn in draw()

    def coin_room(self) -> float:
        """The width the coin column takes at the right of the face (0 without coins)."""
        if not self.coins or not self.face_up:
            return 0.0
        d, pad = coin_metrics(self.width, self.height)
        return d + pad

    def draw(self) -> None:
        self._draw_face()
        if self.shaded and self.face_up:
            # a shade over the whole card; the coins are drawn after it, so they stay bright
            W, H = self.width, self.height
            r = max(6.0, min(W, H) * 0.12)
            ui.set_color(T.SHADE)
            ui.Path.rounded_rect(1, 1, W - 2, H - 2, r).fill()
            if self.selected:
                # the gold selection border stays bright on a shaded card
                border = ui.Path.rounded_rect(1.5, 1.5, W - 3, H - 3, r)
                border.line_width = 3
                ui.set_color(T.ACCENT)
                border.stroke()
        if self.coins and self.face_up:
            draw_coin_column(self.coins, self.width, self.height)
        if self.order and self.face_up:
            # the order the card was selected in: it enters play (or is discarded) in this
            # order, the last one ending on top of the pile
            W, H = self.width, self.height
            d = max(13.0, min(W, H) * (0.3 if self.small else 0.22))
            x, y = W - d - 2, 2.0
            ui.set_color(T.ACCENT)
            ui.Path.oval(x, y, d, d).fill()
            size = d * 0.62
            ui.draw_string(str(self.order), (x, y + (d - size * 1.2) / 2.0, d, size * 1.3), (T.FONT_BOLD, size),
                           T.BG, ui.ALIGN_CENTER)

    def _draw_face(self) -> None:
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
            jw = w - self.coin_room()      # a mercenary Jester's coins take the right edge
            band = ((max(9.0, h * 0.24) if self.small else max(12.0, h * 0.13)) if self.badge else 0.0)
            hh = h - band                  # a tag ("swap", "flute") takes a band along the bottom
            ui.draw_string("J", (ox, oy + hh * 0.12, jw, hh * 0.4), (T.FONT_BOLD, hh * 0.34), col, ui.ALIGN_CENTER)
            ui.draw_string("JESTER", (ox, oy + hh * 0.62, jw, hh * 0.3), (T.FONT_BOLD, max(8, min(hh * 0.12, jw * 0.16))),
                           col, ui.ALIGN_CENTER)
            if self.badge:
                text = str(self.badge)
                fs = max(7.0, min(band * 0.62, (w - 2) / (0.62 * max(1, len(text)))))
                ui.set_color(T.ACCENT)
                ui.Path.rounded_rect(ox + 1, oy + h - band - 1, w - 2, band, 3).fill()
                ui.draw_string(text, (ox + 1, oy + h - band - 1 + (band - fs * 1.2) / 2.0, w - 2, fs * 1.3),
                               (T.FONT_BOLD, fs), T.BG, ui.ALIGN_CENTER)
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
        kind = (classic_kind(c) if (FACE_STYLE == "classic" and not self.small and W >= CLASSIC_MIN_WIDTH)
                else "")
        if kind:
            self._draw_classic(c, kind, rank, pips, col, ox, oy, w, h)
            return
        if c.has("choosable") and not suits:
            self._draw_wild(c, ox, oy, w, h, rank)
            return
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

    def _draw_classic(self, c: Card, kind: str, rank: str, pips: List[str], col: str, ox: float, oy: float,
                      w: float, h: float) -> None:
        """A playing card's face: the rank and the class icons in the top-left corner and,
        turned, in the bottom-right one; the rank's number of icons of the first class in
        the usual layout (the lower half turned), one big icon on an ace, a big letter on
        a royal. A tag ("stuck", "flute") takes a band along the bottom as on the simple face."""
        band = max(12.0, h * 0.13) if self.badge else 0.0
        hh = h - band
        iw = w * (0.22 if kind == "royal" else 0.3)   # the corner index's column (a royal's letter is narrow)
        rs = w * (0.2 if len(rank) > 1 else 0.23)     # its rank (a 10 a little smaller)
        ps = w * 0.17                                 # its class icons
        icons = pips[:3]

        def index(x: float, y: float) -> None:
            ui.draw_string(rank, (x, y + w * 0.04, iw, rs * 1.25), (T.FONT_BOLD, rs), col, ui.ALIGN_CENTER)
            for i, s in enumerate(icons):
                draw_symbol(s, x + iw / 2.0, y + w * 0.04 + rs * 1.2 + ps * 0.62 + i * ps * 1.05, ps, col)

        pad = max(2.0, w * 0.04)                      # clear of the card's border and the selection's
        index(ox + pad, oy)
        tall = w * 0.04 + rs * 1.2 + ps * 1.05 * len(icons) + ps * 0.2
        with turned(ox + w - pad - iw / 2.0, oy + hh - tall / 2.0) as ok:
            if ok:
                index(-iw / 2.0, -tall / 2.0)
            else:
                index(ox + w - pad - iw, oy + hh - tall)
        if kind == "royal":
            # the frame between the two corner columns, the letter and the royal's value in it
            fx, fw = ox + pad + iw + 1, w - 2 * (pad + iw + 1)
            frame = ui.Path.rounded_rect(fx, oy + hh * 0.12, fw, hh * 0.76, 4)
            frame.line_width = 1
            ui.set_color(col)
            frame.stroke()
            size = min(fw * 0.8, hh * 0.42)
            ui.draw_string(rank, (fx, oy + hh * 0.44 - size * 0.65, fw, size * 1.3), (T.FONT_BOLD, size), col,
                           ui.ALIGN_CENTER)
            vs = max(8.0, hh * 0.09)
            ui.draw_string("%d" % c.value, (fx, oy + hh * 0.7, fw, vs * 1.3), (T.FONT_BOLD, vs), col, ui.ALIGN_CENTER)
        else:
            sym = pips[0] if pips else ""
            n = 1 if rank == "A" else int(rank)
            if n == 1:
                draw_symbol(sym, ox + w / 2.0, oy + hh / 2.0, w * 0.5, col)
            else:
                spots = PIP_LAYOUT[n]
                size = w * (0.24 if n <= 3 else 0.2 if n <= 8 else 0.18)
                x0, x1, y0, y1 = ox + w * 0.3, ox + w * 0.7, oy + hh * 0.2, oy + hh * 0.8
                for px, py in spots:
                    draw_symbol(sym, x0 + (x1 - x0) * px, y0 + (y1 - y0) * py, size, col, upside_down=py > 0.5)
        if self.badge:
            ui.set_color(T.ACCENT)
            ui.Path.rounded_rect(ox + 3, oy + h - 3 - band, w - 6, band, 4).fill()
            ui.draw_string(self.badge, (ox + 3, oy + h - 3 - band, w - 6, band), (T.FONT_BOLD, max(8, h * 0.09)), T.BG,
                           ui.ALIGN_CENTER)

    def _draw_wild(self, c: Card, ox: float, oy: float, w: float, h: float, rank: str) -> None:
        """A Wild Animal (any one class, declared when it enters play): one class icon in
        each corner, each in its own colour, set apart from a multi-class card's row of
        icons; the rank sits large in the middle."""
        band = (max(9.0, h * 0.24) if self.small else max(12.0, h * 0.13)) if self.badge else 0.0
        size = h * (0.2 if self.small else 0.16)
        pad = 2.0 if self.small else 5.0
        top, low = oy + pad * 0.5, oy + h - band - pad * 0.5 - size * 1.25
        corners = (("H", top, ui.ALIGN_LEFT), ("D", top, ui.ALIGN_RIGHT),
                   ("C", low, ui.ALIGN_LEFT), ("S", low, ui.ALIGN_RIGHT))
        for suit, y, align in corners:
            ui.draw_string(SUIT_SYMBOL[suit], (ox + pad, y, w - 2 * pad, size * 1.3), (T.FONT_BOLD, size),
                           T.SUIT_COLOR[suit], align)
        big = (h - band) * (0.36 if self.small else 0.3)
        ui.draw_string(rank, (ox, oy + (h - band - big * 1.2) / 2.0, w, big * 1.3), (T.FONT_BOLD, big),
                       card_color(c), ui.ALIGN_CENTER)
        if self.badge:
            text = str(self.badge)
            fs = max(7.0, min(band * 0.62, (w - 2) / (0.62 * max(1, len(text)))))
            ui.set_color(T.ACCENT)
            ui.Path.rounded_rect(ox + 1, oy + h - band - 1, w - 2, band, 3).fill()
            ui.draw_string(text, (ox + 1, oy + h - band - 1 + (band - fs * 1.2) / 2.0, w - 2, fs * 1.3),
                           (T.FONT_BOLD, fs), T.BG, ui.ALIGN_CENTER)

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


class PeekButton(ui.View):
    """Hold to look at the game: while a finger rests on it, ``on_hold(True)`` (the choice
    box fades away and the table shows); lifting it calls ``on_hold(False)`` (the box comes
    back). A hold ending anywhere still counts, and a tap on it while the box is away
    brings the box back too, so it can never stay hidden."""

    def __init__(self, on_hold: Callable[[bool], None], title: str = "Hold to view game",
                 held_title: str = "Release to return", **kw) -> None:
        super().__init__(**kw)
        self.on_hold = on_hold
        self.title = title
        self.held_title = held_title
        self.held = False
        self.background_color = None

    def draw(self) -> None:
        w, h = self.width, self.height
        ui.set_color(T.ACCENT if self.held else T.PANEL_2)
        ui.Path.rounded_rect(0, 0, w, h, 10).fill()
        text = self.held_title if self.held else self.title
        size = 13.0
        while size > 10 and text_size(text, 0, size, True)[0] > w - 10:
            size -= 1
        ui.draw_string(text, (4, (h - size * 1.25) / 2.0, w - 8, size * 1.3), (T.FONT_BOLD, size),
                       T.BG if self.held else T.BTN_TEXT, ui.ALIGN_CENTER)

    def _set(self, held: bool) -> None:
        if held != self.held:
            self.held = held
            self.set_needs_display()
            self.on_hold(held)

    def touch_began(self, touch) -> None:
        self._set(True)

    def touch_moved(self, touch) -> None:
        pass

    def touch_ended(self, touch) -> None:
        self._set(False)


class RelicCard(ui.View):
    """A relic as a small card: its symbol in its colour on a card face, "relic" below.
    A tap reports through ``on_tap`` (the deck list opens the relic's card)."""

    def __init__(self, relic_id: str, on_tap: Optional[Callable[["RelicCard"], None]] = None, **kw) -> None:
        super().__init__(**kw)
        self.relic_id = relic_id
        self.on_tap = on_tap
        self.background_color = None

    def touch_ended(self, touch) -> None:
        x, y = touch.location
        if 0 <= x <= self.width and 0 <= y <= self.height and self.on_tap:
            self.on_tap(self)

    def draw(self) -> None:
        from regicide.campaign.relics import RELICS
        r = RELICS.get(self.relic_id, {})
        w, h = self.width, self.height
        col = str(r.get("color", T.ACCENT))
        ui.set_color(T.CARD_FACE)
        ui.Path.rounded_rect(1, 1, w - 2, h - 2, max(5.0, min(w, h) * 0.12)).fill()
        edge = ui.Path.rounded_rect(2, 2, w - 4, h - 4, max(5.0, min(w, h) * 0.12))
        edge.line_width = 2.5
        ui.set_color(col)
        edge.stroke()
        size = h * 0.42
        ui.draw_string(str(r.get("symbol", "?")), (0, h * 0.14, w, size * 1.3), (T.FONT_BOLD, size), col, ui.ALIGN_CENTER)
        ui.draw_string("relic", (0, h * 0.7, w, h * 0.2), (T.FONT, max(8.0, h * 0.14)), "#555555", ui.ALIGN_CENTER)


def tap_cover(view: ui.View) -> ui.Button:
    """A clear button with ``view``'s frame that calls ``view.on_tap(view)``; add it to the
    same scroll view right after the card, which then takes no touches itself. On the phone
    taps on the mercenary camp's cards (in a scroll view) did not hire; a button is the
    dependable way to take a tap there, whatever the scroll view does with a custom view's."""
    view.touch_enabled = False
    b = ui.Button(frame=view.frame)
    b.title = ""
    b.background_color = None
    b.action = lambda sender: view.on_tap(view) if view.on_tap else None
    return b


class PlayingCardFace(ui.View):
    """The face of a card pop-up, drawn like the game's playing cards: a cream face with
    rounded corners, an edge in the card's colour and a small index (``corner``: a list of
    (text, colour)) in the top-left and bottom-right corners. Its content (name, icon,
    text) is added as subviews by ``card_popup_face``."""

    def __init__(self, edge: str = "", corner=None, **kw) -> None:
        super().__init__(**kw)
        self.edge = edge or T.CARD_BORDER
        self.corner = list(corner or [])
        self.background_color = None

    # A tap on the card (its labels pass their touches up to it) stops here: on the phone
    # an unhandled touch travels on to the pop-up behind, which closes on a tap beside the card.
    def touch_began(self, touch) -> None:
        pass

    def touch_ended(self, touch) -> None:
        pass

    def draw(self) -> None:
        w, h = self.width, self.height
        r = 18.0
        ui.set_color(T.CARD_FACE)
        ui.Path.rounded_rect(1, 1, w - 2, h - 2, r).fill()
        edge = ui.Path.rounded_rect(3, 3, w - 6, h - 6, r - 2)
        edge.line_width = 3
        ui.set_color(self.edge)
        edge.stroke()
        if not self.corner:
            return
        size = 17.0
        for i, (text, color) in enumerate(self.corner[:4]):
            ui.draw_string(text, (12, 10 + i * size * 1.05, size * 1.6, size * 1.3), (T.FONT_BOLD, size), color,
                           ui.ALIGN_CENTER)
            ui.draw_string(text, (w - 12 - size * 1.6, h - 10 - (i + 1) * size * 1.05 - size * 0.25, size * 1.6,
                                  size * 1.3), (T.FONT_BOLD, size), color, ui.ALIGN_CENTER)


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
        ui.draw_string(card.rank, (cx + 4 + sw, cy + 2 + sw, cw, 26), (T.FONT_BOLD, 22), col)
        # each class in its own colour (a Hydra Head's two classes, the Evergreen tree)
        CardView._pips(face_pips(card), cx + sw + 2, cy + ch * 0.34, cw - 2 * sw - 4, ch * 0.4, ui.ALIGN_CENTER)
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
        self._number()
        self.layout()

    def _number(self) -> None:
        """Selected cards show the order they were tapped in (once two or more are selected):
        they are played, or discarded one at a time, in that order, the last on top."""
        for cid, v in self.views.items():
            order = self.selected.index(cid) + 1 if (cid in self.selected and len(self.selected) >= 2) else 0
            if v.order != order:
                v.order = order
                v.set_needs_display()

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
        self._number()
        self.layout()
        v.set_needs_display()
        if self.on_change:
            self.on_change()

    def set_selection(self, ids: Sequence[str]) -> None:
        self.selected = [i for i in ids if i in self.views]
        for cid, v in self.views.items():
            v.selected = cid in self.selected
            v.set_needs_display()
        self._number()
        self.layout()
        if self.on_change:
            self.on_change()

    def clear_selection(self) -> None:
        self.set_selection([])

    def refresh_dim(self) -> None:
        # only the cards whose state changes are redrawn (every tap comes through here)
        for c, v in ((c, self.views[c.id]) for c in self.cards):
            dim = not self.selectable(c)
            if v.dimmed != dim:
                v.dimmed = dim
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
