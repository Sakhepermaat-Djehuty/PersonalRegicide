"""Custom views: cards, the enemy panel, the hand grid, buttons.

Everything is drawn with ``ui.Path`` and ``ui.draw_string`` so no image assets are
needed and nothing from the published games is copied.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence

import ui

from regicide.cards import BASIC_SUITS, CLASS_NAME, SUIT_NAME, SUIT_SYMBOL, Card
from regicide.engine import Game

from . import theme as T
from . import veil


TAP_SOUND: Optional[Callable[[], None]] = None   # set by the app: the button sound


def with_tap_sound(action: Optional[Callable]) -> Optional[Callable]:
    """``action`` preceded by the button sound (when the app has one)."""
    if action is None:
        return None

    def run(sender):
        if TAP_SOUND is not None:
            TAP_SOUND()
        return action(sender)
    return run


def make_button(title: str, action: Callable, frame=(0, 0, 100, 44), primary: bool = True,
                font_size: int = 16) -> ui.Button:
    b = ui.Button(frame=frame)
    b.title = title
    b.action = with_tap_sound(action)
    b.font = (T.FONT_BOLD, font_size)
    veil.dress_button(b, primary)      # a black tile with the pale frame inside it
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


def set_enabled(b: ui.Button, on: bool, primary: bool = True, chosen: bool = False) -> None:
    b.enabled = on
    veil.dress_button(b, primary, on, chosen)


def button_look(b: ui.Button) -> str:
    """How a button is dressed: "lit" (a main action: the bright frame), "quiet" (the dim
    frame), "off" (it can't be pressed), "chosen" (the picked one of a set) or "bare"."""
    f = veil.frame_of(b)
    return f.look if f is not None else ""


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
    return T.TEXT


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
    """The sleeve a card sits in: dark and cracked when corrupted, grey with a pale line inside
    when restored, none otherwise."""
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
BACK_STYLE = "veil"        # the card backs (``app.backs``), from the "card_back" setting
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
            draw_tree(x - size * 0.45, y - size * 0.5, size * 0.9, size, color)
            return
        ui.draw_string(SUIT_SYMBOL.get(sym, sym), (x - size, y - size * 0.62, size * 2, size * 1.3),
                       (T.FONT_BOLD, size), color, ui.ALIGN_CENTER)
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
    """One coin (tarnished silver), diameter ``d``, top-left corner at (x, y)."""
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


def draw_back(x: float, y: float, w: float, h: float, count: Optional[int] = None, plain: bool = False) -> None:
    """The back of a card filling the rect, in the chosen style (``BACK_STYLE``); with
    ``count`` a plain circle in the middle holds it (a pile's number of cards); ``plain``:
    the edge and field only (a card under the top one of a pile)."""
    from . import backs
    backs.STYLES.get(BACK_STYLE, backs.lattice)(x, y, w, h, count, plain)


def draw_count_circle(cx: float, cy: float, d: float, count: int, fill: str, ink: str, rim: str = "") -> None:
    """A plain circle centred on (cx, cy) with a number in it."""
    if rim:
        ui.set_color(rim)
        ui.Path.oval(cx - d / 2.0 - 1.5, cy - d / 2.0 - 1.5, d + 3, d + 3).fill()
    ui.set_color(fill)
    ui.Path.oval(cx - d / 2.0, cy - d / 2.0, d, d).fill()
    text = "%d" % count
    size = d * (0.56 if len(text) < 2 else 0.5 if len(text) < 3 else 0.36)
    ui.draw_string(text, (cx - d / 2.0, cy - size * 0.66, d, size * 1.32), (T.FONT_BOLD, size), ink, ui.ALIGN_CENTER)


def draw_clash(W: float, H: float) -> None:
    """A warning (a class power the enemy is immune to): a jagged white edge round the
    card, set apart from a selection's smooth one, and a white "!" disc in its bottom-left
    corner."""
    teeth = jagged_outline(2.5, 2.5, W - 5, H - 5, max(2.0, min(W, H) * 0.05))
    veil.polyline(teeth, T.DANGER, 1.6)
    d = max(14.0, min(W, H) * 0.22)
    x, y = 3.0, H - d - 3.0
    ui.set_color(T.BG)
    ui.Path.oval(x - 1.5, y - 1.5, d + 3, d + 3).fill()
    ui.set_color(T.DANGER)
    ui.Path.oval(x, y, d, d).fill()
    size = d * 0.7
    ui.draw_string("!", (x, y + (d - size * 1.2) / 2.0, d, size * 1.3), (T.FONT_BOLD, size), T.BG, ui.ALIGN_CENTER)


def jagged_outline(x: float, y: float, w: float, h: float, tooth: float) -> list:
    """A closed saw-toothed line round the rect, its teeth pointing in."""
    pts = []
    for (x0, y0, x1, y1, nx, ny) in ((x, y, x + w, y, 0, 1), (x + w, y, x + w, y + h, -1, 0),
                                     (x + w, y + h, x, y + h, 0, -1), (x, y + h, x, y, 1, 0)):
        length = math.hypot(x1 - x0, y1 - y0)
        n = max(2, int(length / (tooth * 1.6)))
        for i in range(n):
            t0, t1 = i / float(n), (i + 0.5) / float(n)
            pts.append((x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0))
            pts.append((x0 + (x1 - x0) * t1 + nx * tooth, y0 + (y1 - y0) * t1 + ny * tooth))
    pts.append((x, y))
    return pts


def card_radius(W: float, H: float) -> float:
    """A card's corner: small and tight, as a printed card's (not a phone's tile)."""
    return max(3.0, min(W, H) * 0.045)


def draw_tag(x: float, y: float, w: float, band: float, text: str) -> None:
    """A tag along the bottom of a card ("flute", "stuck", "swap", an order): bone capitals
    on a band a shade lighter than the face, a scored line above it."""
    ui.set_color(T.BTN_LIT)
    ui.Path.rect(x, y, w, band).fill()
    veil.rough_rule(x, x + w, y + 0.5, ("tag", text), T.RIM, 1.0)
    size = max(7.0, min(band * 0.62, (w - 2) / (0.62 * max(1, len(text)))))
    ui.draw_string(text, (x, y + (band - size * 1.25) / 2.0 + 0.5, w, size * 1.3), (T.FONT_BOLD, size), T.TEXT,
                   ui.ALIGN_CENTER)


def draw_card_ground(w: float, h: float, r: float, edge=None, seed="card", veil_alpha: float = 0.62) -> None:
    """A large card's ground (the pop-ups): black, the fog showing through (the more, the
    lower ``veil_alpha``), a few dark scores, the faint frame inside its edge and a pale rim."""
    ui.set_color(T.CARD_FACE)
    outer = ui.Path.rounded_rect(1, 1, w - 2, h - 2, r)
    outer.fill()
    with ui.GState():
        outer.add_clip()
        veil.draw_fog(0, 0, w, h, "fog_l.jpg")
        ui.set_color((0.03, 0.03, 0.03, veil_alpha))
        ui.Path.rect(0, 0, w, h).fill()
        veil.scratches(8, 8, w - 16, h - 16, seed, 4, T.SCAR, 0.7)
    rim = ui.Path.rounded_rect(1.5, 1.5, w - 3, h - 3, r)
    rim.line_width = 1.5
    ui.set_color(T.RIM)
    rim.stroke()


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
        self.warn = False             # its class power clashes with the enemy's immunity: jagged white edge and "!"
        self.force_kind = ""          # "royal": the classic royal face whatever the setting (the enemy)
        self.center_icons = None      # a royal: these class icons under the letter instead of its value
        self.struck_icons = None      # the enemy: classes whose immunity a Jester cancelled (struck through)
        self.background_color = None  # drawn in draw()

    def coin_room(self) -> float:
        """The width the coin column takes at the right of the face (0 without coins)."""
        if not self.coins or not self.face_up:
            return 0.0
        d, pad = coin_metrics(self.width, self.height)
        return d + pad

    def draw(self) -> None:
        self._draw_face()
        if self.dimmed and self.face_up and not self.shaded:
            # a dark veil over a card that can't be played: it sinks back (its face only: a
            # sleeve keeps its grey, so restored and corrupted stay apart)
            ui.set_color(T.CARD_VEIL)
            self._face_path().fill()
        if self.shaded and self.face_up:
            # a shade over the card's face; the coins are drawn after it, so they stay bright
            W, H = self.width, self.height
            r = card_radius(W, H)
            ui.set_color(T.SHADE)
            self._face_path().fill()
            if self.selected:
                # the white selection border stays bright on a shaded card
                border = ui.Path.rounded_rect(1.5, 1.5, W - 3, H - 3, r)
                border.line_width = 2.5
                ui.set_color(T.ACCENT)
                border.stroke()
        if self.coins and self.face_up:
            draw_coin_column(self.coins, self.width, self.height)
        if self.warn and self.face_up:
            draw_clash(self.width, self.height)
        if self.order and self.face_up:
            # the order the card was selected in: it enters play (or is discarded) in this
            # order, the last one ending on top of the pile
            W, H = self.width, self.height
            d = max(15.0, min(26.0, min(W, H) * (0.3 if self.small else 0.26)))
            veil.number_tile(W - d - 2.5, 2.5, d, str(self.order), True)

    def _face_path(self):
        """The card's face: all of it, or inside its sleeve."""
        W, H = self.width, self.height
        r = card_radius(W, H)
        sw = max(2.5, min(W, H) * 0.08) if sleeve_color(self.card) else 0.0
        return ui.Path.rounded_rect(1 + sw, 1 + sw, W - 2 - 2 * sw, H - 2 - 2 * sw, max(2.0, r - sw * 0.6))

    def _draw_face(self) -> None:
        W, H = self.width, self.height
        r = card_radius(W, H)
        if not self.face_up:
            draw_back(0, 0, W, H)
            return
        c = self.card
        if self.force_kind == "royal" and self.center_icons is not None:
            self._draw_foe(c, r)
            return
        # A black card, as Veilwraith's action cards, with a thin grey edge; a selected one
        # has a white rim instead (and lifts). Sleeves, as on the physical cards: a corrupted
        # card sits in a dark sleeve, cracked (the cracks run on over the lower face), a
        # restored one in a grey sleeve with a pale line inside it, whole.
        sleeve = sleeve_color(c)
        sw = max(2.5, min(W, H) * 0.08) if sleeve else 0.0
        if sleeve:
            ui.set_color(sleeve)
            ui.Path.rounded_rect(1, 1, W - 2, H - 2, r).fill()
        inner = ui.Path.rounded_rect(1 + sw, 1 + sw, W - 2 - 2 * sw, H - 2 - 2 * sw, max(2.0, r - sw * 0.6))
        ui.set_color(T.CARD_FACE)
        inner.fill()
        if c.has("restored"):
            inner.line_width = 1
            ui.set_color(T.RESTORED_LINE)
            inner.stroke()
        if c.has("corrupted"):
            big = min(W, H) >= 40
            veil.cracks(1, H * 0.42, W - 2, H * 0.58 - 1, (c.id, "crack"), T.CORRUPTED_CRACK, 3 if big else 2,
                        1.0 if big else 0.7)
        if self.selected or not sleeve:
            border = ui.Path.rounded_rect(1.5, 1.5, W - 3, H - 3, r)
            border.line_width = 2.5 if self.selected else 1
            ui.set_color(T.ACCENT if self.selected else T.CARD_RIM)
            border.stroke()
        if self.selected and sleeve:
            ring = ui.Path.rounded_rect(1 + sw, 1 + sw, W - 2 - 2 * sw, H - 2 - 2 * sw, max(2.0, r - sw * 0.6))
            ring.line_width = 2
            ui.set_color(T.ACCENT)
            ring.stroke()
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
                draw_tag(ox + 1, oy + h - band - 1, w - 2, band, str(self.badge))
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
        kind = self.force_kind or (classic_kind(c) if (FACE_STYLE == "classic" and not self.small
                                                       and W >= CLASSIC_MIN_WIDTH) else "")
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
                draw_tag(ox + 1, oy + h - band - 1, w - 2, band, str(self.badge))
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
            ui.draw_string(caption, (ox + 2, oy + bottom - cap_h, w - 4, cap_h), (T.FONT_ITALIC, max(8, h * 0.1)),
                           T.CARD_INK_MUTED, ui.ALIGN_CENTER)
        if c.is_royal:
            ui.draw_string("%d" % c.value, (ox, oy + bottom - cap_h, w - 5, cap_h), (T.FONT_BOLD, h * 0.12), col,
                           ui.ALIGN_RIGHT)
        if badge:
            draw_tag(ox + 3, oy + h - 3 - band, w - 6, band, str(badge))

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
            if self.center_icons is not None:
                # the enemy: the classes it is immune to under its letter
                icons = list(self.center_icons)
                isz = min(hh * 0.11, fw / float(max(1, len(icons))) * 0.9)
                for i, s_ in enumerate(icons):
                    draw_symbol(s_, fx + fw * (i + 0.5) / len(icons), oy + hh * 0.76, isz, col)
            else:
                ui.draw_string("%d" % c.value, (fx, oy + hh * 0.7, fw, vs * 1.3), (T.FONT_BOLD, vs), col,
                               ui.ALIGN_CENTER)
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
            draw_tag(ox + 3, oy + h - 3 - band, w - 6, band, str(self.badge))

    def _draw_foe(self, c: Card, r: float) -> None:
        """The enemy as a Veilwraith Foe card, the one pale card on the table: a billow lit
        from behind, its letter dark in it, its rank and class small and upright in the
        corner, and across the bottom a dark panel torn along its top holding the classes
        it is immune to (empty when it has none, or they are cancelled). A corrupted enemy
        sits in its dark, cracked sleeve."""
        W, H = self.width, self.height
        sleeve = sleeve_color(c)
        sw = max(2.5, min(W, H) * 0.06) if sleeve else 0.0
        if sleeve:
            ui.set_color(sleeve)
            ui.Path.rounded_rect(1, 1, W - 2, H - 2, r).fill()
        x, y, w, h = 1 + sw, 1 + sw, W - 2 - 2 * sw, H - 2 - 2 * sw
        field = ui.Path.rounded_rect(x, y, w, h, max(2.0, r - sw * 0.6))
        ui.set_color(T.FOE_FIELD)
        field.fill()
        ink = T.FOE_INK
        rank = c.rank
        panel_h = h * 0.32
        with ui.GState():
            field.add_clip()
            veil.draw_fog(x, y, w, h, "foe.jpg")
            # the letter, large and dark in the light
            size = min(w * 0.9, (h - panel_h) * 0.62)
            ui.draw_string(rank, (x, y + (h - panel_h) * 0.47 - size * 0.62, w, size * 1.3), (T.FONT_BOLD, size), ink,
                           ui.ALIGN_CENTER)
            # its rank and class, small and upright in the corner
            rs = max(w * 0.17, 13.0)
            pad = max(3.0, w * 0.05)
            ui.draw_string(rank, (x + pad, y + pad * 0.6, rs * 1.4, rs * 1.3), (T.FONT_BOLD, rs), ink, ui.ALIGN_CENTER)
            for i, s_ in enumerate(face_pips(c)[:3]):
                draw_symbol(s_, x + pad + rs * 0.7, y + pad * 0.6 + rs * 1.25 + rs * 0.5 + i * rs * 0.95, rs * 0.8,
                            ink)
            # the torn panel and what the enemy is immune to on it
            veil.torn_panel(x, y + h - panel_h, w, panel_h + 1, ("foe", c.id), T.FOE_PANEL, T.FOE_RIM, 3.5)
            icons = list(self.center_icons or [])
            struck = [s_ for s_ in (self.struck_icons or []) if s_ not in icons]
            shown = [(s_, False) for s_ in icons] + [(s_, True) for s_ in struck]
            if shown:
                # the classes it is immune to; a cancelled immunity (a Jester) muted and struck through
                isz = min(panel_h * 0.42, w / float(len(shown)) * 0.7)
                for i, (s_, off) in enumerate(shown):
                    cx_, cy_ = x + w * (i + 0.5) / len(shown), y + h - panel_h * 0.45
                    draw_symbol(s_, cx_, cy_, isz, T.MUTED if off else T.TEXT)
                    if off:
                        veil.polyline([(cx_ - isz * 0.55, cy_ + isz * 0.45), (cx_ + isz * 0.55, cy_ - isz * 0.45)],
                                      T.TEXT, 1.5)
            if c.has("corrupted"):
                veil.cracks(x, y + h - panel_h, w, panel_h, (c.id, "crack"), T.CORRUPTED_CRACK, 2, 1.0)
        rim = ui.Path.rounded_rect(1.5, 1.5, W - 3, H - 3, r)
        rim.line_width = 1
        ui.set_color(T.FOE_EDGE)
        rim.stroke()

    def _draw_wild(self, c: Card, ox: float, oy: float, w: float, h: float, rank: str) -> None:
        """A Wild Animal (any one class, declared when it enters play): one class icon in
        each corner, in ink, set apart from a multi-class card's row of
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
            draw_tag(ox + 1, oy + h - band - 1, w - 2, band, str(self.badge))

    @staticmethod
    def _pips(pips, x: float, y: float, width: float, size: float, align) -> None:
        """Class symbols in a row, in ink, shrunk to fit ``width``; the
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
        # a black tile with a dim frame; held, it turns pale (the box is away)
        ui.set_color(T.ACCENT if self.held else T.BTN)
        ui.Path.rounded_rect(0, 0, w, h, 4).fill()
        edge = ui.Path.rounded_rect(0.5, 0.5, w - 1, h - 1, 4)
        edge.line_width = 1
        ui.set_color(T.BTN_EDGE)
        edge.stroke()
        if not self.held:
            veil.inset_frame(0, 0, w, h, 3.0, T.FRAME_QUIET, 1.0, 2.0)
        text = self.held_title if self.held else self.title
        size = 13.0
        while size > 10 and text_size(text, 0, size, True)[0] > w - 10:
            size -= 1
        ui.draw_string(text, (4, (h - size * 1.25) / 2.0, w - 8, size * 1.3), (T.FONT_BOLD, size),
                       T.BG if self.held else T.TEXT, ui.ALIGN_CENTER)

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


class CountStepper(ui.View):
    """A number chosen with a − key and a + key either side of it (the Chanter's
    declaration, the Reaver's reveal). A tap on a side steps once; held, it steps on, slowly
    and then faster, until it is lifted or the end is reached. A key at its end greys and is
    silent. ``on_change(value)`` follows each step."""

    KEY = 60.0

    def __init__(self, value: int, lo: int, hi: int, on_change: Optional[Callable[[int], None]] = None,
                 **kw) -> None:
        super().__init__(**kw)
        self.lo, self.hi = int(lo), int(hi)
        self.value = max(self.lo, min(self.hi, int(value)))
        self.on_change = on_change
        self.held = 0            # -1 or +1 while a key is held
        self._token = 0          # a lifted finger ends the repeats asked for while it was down
        self.background_color = None

    def can(self, step: int) -> bool:
        return self.lo <= self.value + step <= self.hi

    def key_rect(self, step: int) -> tuple:
        k = min(self.KEY, self.height)
        y = (self.height - k) / 2.0
        return (0, y, k, k) if step < 0 else (self.width - k, y, k, k)

    def draw(self) -> None:
        for step, sign in ((-1, "−"), (1, "+")):
            x, y, w, h = self.key_rect(step)
            on = self.can(step)
            held = self.held == step
            ui.set_color(T.ACCENT if held else T.BTN)
            ui.Path.rounded_rect(x, y, w, h, 4).fill()
            if not held:
                edge = ui.Path.rounded_rect(x + 0.5, y + 0.5, w - 1, h - 1, 4)
                edge.line_width = 1
                ui.set_color(T.BTN_EDGE)
                edge.stroke()
                veil.inset_frame(x, y, w, h, 3.0, T.FRAME if on else T.FRAME_OFF, 1.0, 2.0)
            size = h * 0.55
            ui.draw_string(sign, (x, y + (h - size * 1.25) / 2.0, w, size * 1.3), (T.FONT_BOLD, size),
                           T.BG if held else (T.BTN_TEXT if on else T.FAINT), ui.ALIGN_CENTER)
        k = self.key_rect(1)[2]
        size = min(46.0, self.height * 0.7)
        ui.draw_string(str(self.value), (k, (self.height - size * 1.25) / 2.0, self.width - 2 * k, size * 1.3),
                       (T.FONT_BOLD, size), T.TEXT, ui.ALIGN_CENTER)

    def set_value(self, value: int) -> None:
        self.value = max(self.lo, min(self.hi, int(value)))
        self.set_needs_display()

    def _step(self, step: int) -> bool:
        if not self.can(step):
            return False
        self.value += step
        self.set_needs_display()
        if self.on_change is not None:
            self.on_change(self.value)
        return True

    def touch_began(self, touch) -> None:
        x = touch.location[0]
        if self.width / 3.0 <= x <= self.width * 2 / 3.0:
            return                                  # the number itself is not a key
        step = -1 if x < self.width / 2.0 else 1
        if not self.can(step):
            return
        if TAP_SOUND is not None:
            TAP_SOUND()
        self.held = step
        self._token += 1
        self._step(step)
        tok = self._token
        ui.delay(lambda: self._repeat(tok, 0), 0.45)

    def _repeat(self, tok: int, n: int) -> None:
        if tok != self._token or not self.held:
            return
        if not self._step(self.held):
            self.held = 0
            self.set_needs_display()
            return
        ui.delay(lambda: self._repeat(tok, n + 1), 0.12 if n < 6 else 0.05)

    def touch_moved(self, touch) -> None:
        pass

    def touch_ended(self, touch) -> None:
        self.held = 0
        self._token += 1
        self.set_needs_display()


def draw_tick_box(x: float, y: float, s: float, value: bool, enabled: bool = True) -> None:
    """A box ticked (a pale tile, a black tick) or crossed (a black tile, framed, a grey
    cross), dimmer when it can't be pressed."""
    box = ui.Path.rounded_rect(x, y, s, s, 4)
    ui.set_color((T.TEXT if enabled else T.MUTED) if value else T.BTN)
    box.fill()
    if not value:
        edge = ui.Path.rounded_rect(x + 0.5, y + 0.5, s - 1, s - 1, 4)
        edge.line_width = 1
        ui.set_color(T.BTN_EDGE if enabled else T.FRAME_OFF)
        edge.stroke()
        veil.inset_frame(x, y, s, s, 3.0, T.FRAME_QUIET if enabled else T.FRAME_OFF, 1.0, 2.0)
    mark = "✓" if value else "✗"
    size = s * 0.62
    ink = T.BG if value else (T.MUTED if enabled else T.FAINT)
    ui.draw_string(mark, (x, y + (s - size * 1.25) / 2.0, s, size * 1.3), (T.FONT_BOLD, size), ink, ui.ALIGN_CENTER)


class TickBox(ui.View):
    """A box ticked (✓) or crossed (✗): a tap turns it over and reports ``on_change(value)``.
    One that cannot be pressed (``enabled`` False) is dimmed and silent."""

    def __init__(self, value: bool, on_change: Optional[Callable[[bool], None]] = None, enabled: bool = True,
                 **kw) -> None:
        super().__init__(**kw)
        self.value = bool(value)
        self.on_change = on_change
        self.enabled = enabled
        self.background_color = None

    def draw(self) -> None:
        s = min(self.width, self.height) - 2
        draw_tick_box((self.width - s) / 2.0, (self.height - s) / 2.0, s, self.value, self.enabled)

    def touch_began(self, touch) -> None:
        pass

    def touch_ended(self, touch) -> None:
        if getattr(touch, "phase", "ended") == "cancelled":
            return                                  # a scroll took the touch
        x, y = touch.location
        if not self.enabled or not (0 <= x <= self.width and 0 <= y <= self.height):
            return
        if TAP_SOUND is not None:
            TAP_SOUND()
        self.value = not self.value
        self.set_needs_display()
        if self.on_change is not None:
            self.on_change(self.value)


class Toggle(ui.View):
    """An on/off setting drawn as a tick box at the right of its frame (the phone's own
    switch keeps its colours, whatever the look asks), with a switch's ``value`` and
    ``action(sender)``."""

    def __init__(self, value: bool = False, action: Optional[Callable] = None, **kw) -> None:
        super().__init__(**kw)
        self.value = bool(value)
        self.action = action
        self.enabled = True
        self.background_color = None

    def draw(self) -> None:
        s = min(self.width, self.height) - 2
        draw_tick_box(self.width - s - 1, (self.height - s) / 2.0, s, self.value, self.enabled)

    def touch_began(self, touch) -> None:
        pass

    def touch_ended(self, touch) -> None:
        if getattr(touch, "phase", "ended") == "cancelled":
            return                                  # a scroll took the touch
        x, y = touch.location
        if not self.enabled or not (0 <= x <= self.width and 0 <= y <= self.height):
            return
        if TAP_SOUND is not None:
            TAP_SOUND()
        self.value = not self.value
        self.set_needs_display()
        if self.action is not None:
            self.action(self)


class Segments(ui.View):
    """A row of tiles, one chosen (in place of the phone's segmented control, whose colours
    the look can't set): ``segments``, ``selected_index`` and ``action(sender)`` as there.
    Each tile is a button named by its segment."""

    _segments: Sequence[str] = ()
    _index = -1
    action: Optional[Callable] = None

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.background_color = None

    @property
    def segments(self) -> List[str]:
        return list(self._segments)

    @segments.setter
    def segments(self, value) -> None:
        self._segments = [str(v) for v in value]
        self._build()

    @property
    def selected_index(self) -> int:
        return self._index

    @selected_index.setter
    def selected_index(self, i: int) -> None:
        self._index = int(i)
        self._dress()

    def _build(self) -> None:
        for v in list(self.subviews):
            self.remove_subview(v)
        for i, title in enumerate(self._segments):
            b = make_button(title, (lambda k: lambda sender: self._tapped(k))(i), (0, 0, 10, 10), False, 14)
            self.add_subview(b)
        self.layout()
        self._dress()

    def _dress(self) -> None:
        for i, b in enumerate(self.subviews):
            veil.dress_button(b, False, True, chosen=(i == self._index))

    def _tapped(self, i: int) -> None:
        if i == self._index:
            return
        self.selected_index = i
        if self.action is not None:
            self.action(self)

    def layout(self) -> None:
        n = len(getattr(self, "_segments", ()))
        if not n:
            return
        gap = 4.0
        w = (self.width - gap * (n - 1)) / n
        if w <= 0:
            return                                  # (not laid out yet)
        for i, b in enumerate(self.subviews):
            b.frame = (i * (w + gap), 0, w, self.height)
            fit_title(b, 14)


class RelicCard(ui.View):
    """A relic as a small card: its symbol in ink on a black card face, "relic" below (the
    corrupt Mother's tile cracked, the restored one's with a pale line inside).
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
        col = T.TEXT          # (a relic's own colour belongs to the coloured look)
        rad = card_radius(w, h)
        ui.set_color(T.CARD_FACE)
        ui.Path.rounded_rect(1, 1, w - 2, h - 2, rad).fill()
        edge = ui.Path.rounded_rect(1.5, 1.5, w - 3, h - 3, rad)
        edge.line_width = 1
        ui.set_color(T.CARD_RIM)
        edge.stroke()
        size = h * 0.42
        if self.relic_id == "mother":
            # the corrupt Mother: cracked
            veil.cracks(2, 2, w - 4, h - 4, "mother", T.CORRUPTED_CRACK, 3, 0.8)
        elif self.relic_id == "mother_restored":
            # the restored Mother: a pale line inside the edge, whole
            line = ui.Path.rounded_rect(4, 4, w - 8, h - 8, max(1.5, rad - 3))
            line.line_width = 1
            ui.set_color(T.RESTORED_LINE)
            line.stroke()
        ui.draw_string(str(r.get("symbol", "?")), (0, h * 0.14, w, size * 1.3), (T.FONT_BOLD, size), col, ui.ALIGN_CENTER)
        ui.draw_string("relic", (0, h * 0.7, w, h * 0.2), (T.FONT_ITALIC, max(8.0, h * 0.14)), T.MUTED, ui.ALIGN_CENTER)


class PlayingCardFace(ui.View):
    """The face of a card pop-up, drawn like the game's playing cards: a cream face with
    rounded corners, an edge in the card's colour and a small index (``corner``: a list of
    (text, colour)) in the top-left and bottom-right corners. Its content (name, icon,
    text) is added as subviews by ``card_popup_face``."""

    def __init__(self, edge: str = "", corner=None, **kw) -> None:
        super().__init__(**kw)
        self.edge = edge or T.CARD_BORDER
        self.corner = list(corner or [])
        self.panel_y = 0.0            # where the text's torn panel starts (0: none)
        self.background_color = None

    # A tap on the card (its labels pass their touches up to it) stops here: on the phone
    # an unhandled touch travels on to the pop-up behind, which closes on a tap beside the card.
    def touch_began(self, touch) -> None:
        pass

    def touch_ended(self, touch) -> None:
        pass

    def draw(self) -> None:
        w, h = self.width, self.height
        r = max(3.0, min(w, h) * 0.035)
        seed = ("face",) + tuple(t for t, _ in self.corner[:1])
        draw_card_ground(w, h, r, self.edge, seed=seed, veil_alpha=0.38)
        if self.panel_y:
            veil.torn_panel(6, self.panel_y, w - 12, h - self.panel_y - 6, seed, T.TORN_PANEL, T.RIM, 3.0,
                            bottom_radius=max(0.0, r - 3))
            veil.hatching(10, self.panel_y + 8, w - 20, h - self.panel_y - 16, seed + ("h",), T.SCAR, 9, 0.6)
        if not self.corner:
            return
        size = 17.0
        for i, (text, color) in enumerate(self.corner[:4]):
            ui.draw_string(text, (12, 10 + i * size * 1.05, size * 1.6, size * 1.3), (T.FONT_BOLD, size), color,
                           ui.ALIGN_CENTER)
            ui.draw_string(text, (w - 12 - size * 1.6, h - 10 - (i + 1) * size * 1.05 - size * 0.25, size * 1.6,
                                  size * 1.3), (T.FONT_BOLD, size), color, ui.ALIGN_CENTER)


class InfoCardFace(ui.View):
    """An info pop-up's card, landscape: the descriptor of one game phase (portrait stays for
    the playable cards). Top left the strength that matters (``number``), the class icon
    right of it (``icon``: a class letter, ``TREE_PIP`` or any short text), the title right of
    that; a rule in the card's colour; a brief breakdown (``lines``); and, for a damage card,
    a big number in the middle (``middle``, with ``middle_caption`` under it). When the
    enemy is immune (``immune``) the card is greyed a little and IMMUNITY is stamped across
    it: bold, white and diagonal. A strength that does nothing (``number_muted``: a Druid's or
    a Chanter's) is drawn muted and struck through. The breakdown's type shrinks until every
    line fits on one line and every line fits on the card."""

    RATIO = 0.64          # height / width: a playing card turned on its side

    def __init__(self, title: str, number: str = "", icon: str = "", lines: Sequence[str] = (),
                 middle: str = "", middle_caption: str = "", immune: bool = False, edge: str = "",
                 number_muted: bool = False, **kw) -> None:
        super().__init__(**kw)
        self.title = title
        self.number = str(number)
        self.number_muted = number_muted
        self.icon = icon
        self.lines = [str(x) for x in lines]
        self.middle = str(middle)
        self.middle_caption = middle_caption
        self.immune = immune
        self.edge = edge or T.SUIT_COLOR.get(icon, T.CARD_BORDER)
        self.background_color = None

    # taps on the card stop here (see PlayingCardFace)
    def touch_began(self, touch) -> None:
        pass

    def touch_ended(self, touch) -> None:
        pass

    def draw(self) -> None:
        w, h = float(self.width), float(self.height)
        r = max(3.0, min(w, h) * 0.035)
        draw_card_ground(w, h, r, self.edge, seed=("info", self.title), veil_alpha=0.38)
        ink = T.CARD_INK_MUTED if self.immune else T.CARD_INK
        pad = 16.0
        top = 12.0
        # the strength, the class icon, the title, side by side
        x = pad
        row = 40.0
        if self.number:
            nw = text_size(self.number, 0, 34, True)[0]
            ui.draw_string(self.number, (x, top - 2, nw + 4, row + 4), (T.FONT_BOLD, 34),
                           T.CARD_INK_MUTED if (self.number_muted or self.immune) else T.BRIGHT, ui.ALIGN_LEFT)
            if self.number_muted:
                strike = ui.Path.rect(x - 1, top + row * 0.5 - 1, nw + 2, 2.5)
                ui.set_color(T.CARD_INK_MUTED)
                strike.fill()
            x += nw + 10
        if self.icon:
            size = 28.0
            # one class symbol (or the tree), several class symbols side by side, or a glyph
            parts = list(self.icon) if len(self.icon) > 1 and all(ch in SUIT_SYMBOL for ch in self.icon) else [self.icon]
            for part in parts:
                if part == TREE_PIP or part in SUIT_SYMBOL:
                    pw = size * 1.2
                else:
                    pw = max(size * 1.2, text_size(part, 0, size, True)[0] + 4)
                draw_symbol(part, x + pw / 2.0, top + row * 0.55, size, ink)
                x += pw
            x += 8
        tsize = 22
        while tsize > 14 and text_size(self.title, 0, tsize, True)[0] > w - x - pad:
            tsize -= 1
        ui.draw_string(self.title, (x, top + (row - tsize * 1.25) / 2 + 1, w - x - pad, tsize * 1.3),
                       (T.FONT_BOLD, tsize), ink, ui.ALIGN_LEFT)
        y = top + row + 6
        # the breakdown sits on a panel torn along its top (a Veilwraith Foe card's text panel)
        veil.torn_panel(6, y - 2, w - 12, h - y - 4, ("info", self.title), T.TORN_PANEL, T.RIM, 2.5,
                        bottom_radius=r - 6)
        veil.hatching(10, y + 6, w - 20, h - y - 14, ("info", self.title, "h"), T.SCAR, 9, 0.6)
        y += 10
        body = "\n".join(self.lines)
        if self.middle:
            # top down: the number, its caption, the lines; the lines shrink first, then the
            # number, so nothing overlaps on a small phone
            cap = 12 if self.middle_caption else 0
            free = h - y - pad
            msize, size = 60.0, 14.0
            while True:
                mh = msize * 1.12
                room = free - mh - cap * 1.25 - (4 if body else 0)
                size = self.body_size(w - 2 * pad, room, 14) if body else 14.0
                text_h = len(self.lines) * size * 1.25 if body else 0.0
                if text_h <= room or msize <= 30:
                    break
                msize -= 3
            block = mh + cap * 1.25 + (4 + text_h if body else 0)
            my = y + max(0.0, (free - block) / 2.0)
            ui.draw_string(self.middle, (pad, my - msize * 0.08, w - 2 * pad, msize * 1.25), (T.FONT_BOLD, msize), ink,
                           ui.ALIGN_CENTER)
            yy = my + mh
            if cap:
                ui.draw_string(self.middle_caption, (pad, yy, w - 2 * pad, cap * 1.3), (T.FONT, cap),
                               T.CARD_INK_MUTED, ui.ALIGN_CENTER)
                yy += cap * 1.25
            if body:
                ui.draw_string(body, (pad, yy + 4, w - 2 * pad, text_h + 2), (T.FONT, size), ink, ui.ALIGN_CENTER)
        elif body:
            size = self.body_size(w - 2 * pad, h - y - pad, 15)
            ui.draw_string(body, (pad, y, w - 2 * pad, h - y - pad), (T.FONT, size), ink, ui.ALIGN_LEFT)
        if self.immune:
            self.draw_stamp(w, h)

    def body_size(self, width: float, height: float, largest: float) -> float:
        """The largest type size, down to 10 pt, at which no line wraps and all of them fit
        in ``height``."""
        size = float(largest)
        while size > 10:
            widest = max([text_size(line, 0, size)[0] for line in self.lines] or [0.0])
            if widest <= width - 2 and len(self.lines) * size * 1.25 <= height:
                break
            size -= 0.5
        return size

    @staticmethod
    def draw_stamp(w: float, h: float) -> None:
        """IMMUNITY across the card: bold capitals in a stamp's double frame, turned up to
        the right; white, as the only bright thing on the greyed card."""
        ink = T.BRIGHT
        size = max(26.0, min(48.0, w / 7.5))
        tw = text_size("IMMUNITY", 0, size, True)[0] + size * 1.0
        th = size * 1.75
        with ui.GState():
            # turned about its own centre, then moved to the card's (concat: the first applies first)
            ui.concat_ctm(ui.Transform.rotation(-0.32).concat(ui.Transform.translation(w / 2.0, h / 2.0 + 10)))
            for inset, width in ((0.0, 4.0), (7.0, 1.5)):          # a stamp's double frame
                x0, y0, x1, y1 = -tw / 2 + inset, -th / 2 + inset, tw / 2 - inset, th / 2 - inset
                box = ui.Path()
                box.move_to(x0, y0)
                for px, py in ((x1, y0), (x1, y1), (x0, y1), (x0, y0)):
                    box.line_to(px, py)
                box.line_width = width
                ui.set_color(ink)
                box.stroke()
            ui.draw_string("IMMUNITY", (-tw / 2, -size * 0.66, tw, size * 1.3), (T.FONT_BOLD, size), ink,
                           ui.ALIGN_CENTER)


def draw_label(text: str, x: float, y: float, w: float, size: float, colour) -> None:
    """A small capital label centred in the width from ``x`` (over a number)."""
    ui.draw_string(text, (x, y, w, size * 1.35), (T.FONT_BOLD, size), colour, ui.ALIGN_CENTER)


class TableHeader(ui.View):
    """The enemy at the top of the table: its card large in the middle (drawn as a royal:
    letter, the classes it is immune to, a corrupted sleeve), the attack it will deal on
    the left and its health on the right, in big numbers. While cards are selected the
    numbers show what the attack would do (``projection``, a ``Game.preview_play``) and a
    clash with the enemy's immunity puts a jagged white edge on the card (``warn``). While damage is
    paid (``paying``: selected, needed) the attack side shows what is left to pay. A tap
    left of the card calls ``on_attack``, anywhere else ``on_enemy``."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.game: Optional[Game] = None
        self.projection: Optional[dict] = None
        self.warn = False
        self.paying: Optional[tuple] = None
        self.on_attack: Optional[Callable[[], None]] = None
        self.on_enemy: Optional[Callable[[], None]] = None
        self.card_view: Optional[CardView] = None
        self.background_color = None

    def card_frame(self) -> tuple:
        h = self.height - 6
        w = h / 1.42
        return ((self.width - w) / 2.0, 3.0, w, h)

    def layout(self) -> None:
        if getattr(self, "card_view", None) is not None:
            self.card_view.frame = self.card_frame()

    def show(self, projection: Optional[dict], warn: bool, paying: Optional[tuple]) -> None:
        """What the selection would do: redrawn only when it changes (every tap comes here)."""
        if (projection, warn, paying) == (self.projection, self.warn, self.paying):
            return
        self.projection, self.warn, self.paying = projection, warn, paying
        if self.card_view is not None and self.card_view.warn != warn:
            self.card_view.warn = warn
            self.card_view.set_needs_display()
        self.set_needs_display()

    def refresh(self) -> None:
        """Rebuild the enemy's card (a new enemy, a corruption, a change of immunity)."""
        g = self.game
        if self.card_view is not None:
            self.remove_subview(self.card_view)
            self.card_view = None
        if g is not None and g.enemy is not None:
            v = CardView(g.card(g.enemy.card_id), frame=self.card_frame())
            v.force_kind = "royal"
            v.touch_enabled = False
            immune = list(g.rules.immune_suits(g) or ())
            icons = immune if not g.immunity_cancelled else []
            if g.extra.get("jester_attack"):
                # a claimed Jester's attack ignores immunity (all but a fixed one, Myla's)
                icons = [s_ for s_ in icons if g.rules.fixed_immunity(g, s_)]
            v.center_icons = icons
            v.struck_icons = [s_ for s_ in immune if s_ not in icons]     # cancelled: shown struck through
            v.warn = self.warn
            self.add_subview(v)
            self.card_view = v
        self.set_needs_display()

    def draw(self) -> None:
        g = self.game
        w, h = self.width, self.height
        if g is None or g.enemy is None:
            # the enemy's place, empty
            fx, fy, fw, fh = self.card_frame()
            slot = ui.Path.rounded_rect(fx + 0.5, fy + 0.5, fw - 1, fh - 1, card_radius(fw, fh))
            slot.line_width = 1
            ui.set_color(T.RIM)
            slot.stroke()
            return
        e = g.enemy
        cx, cy, cw, ch = self.card_frame()
        side = cx - 6
        # the number, a line under it and a note (what the selection changes) fit between the
        # label and the health bar, at the same height on both sides
        big = max(20.0, min(side * 0.55, h * 0.42, (h - 76) / 1.2))
        top = 20 + max(0.0, (h - 14 - 20 - (big * 1.2 + 40)) / 2.0)
        pv = self.projection or {}

        def block(x: float, label: str, value: str, color: str, note: str, note_color: str, extra: str = "",
                  label_color: str = T.MUTED, plate: bool = False) -> None:
            if plate:
                # suffering: the label stands black on a pale plate, the one loud thing on the table
                lw = text_size(label, 0, 10.5, True)[0] + 16
                ui.set_color(T.BRIGHT)
                ui.Path.rounded_rect(x + (side - lw) / 2.0, 3, lw, 16, 2).fill()
            draw_label(label, x, 4.5, side, 10.5, T.BG if plate else label_color)
            ui.draw_string(value, (x, top, side, big * 1.25), (T.FONT_BOLD, big), color, ui.ALIGN_CENTER)
            y = top + big * 1.2
            if extra:
                ui.draw_string(extra, (x, y, side, 16), (T.FONT_ITALIC, 12), T.MUTED, ui.ALIGN_CENTER)
                y += 16
            if note:
                ui.draw_string(note, (x, y + 1, side, 22), (T.FONT_BOLD, 15), note_color, ui.ALIGN_CENTER)

        # A "?" marks what depends on a card still face down (the forecast never tells it), or
        # follows from a value the player declares later (the forecast assumes one).
        q = "?" if pv.get("decision_kind") in ("declare_value", "declare_class") else ""
        # the attack: what the enemy will deal (after shields), and with the selection what
        # would be suffered; while damage is paid, what is left to pay (no shield line: it
        # is counted already, and team damage ignores it)
        atk = g.enemy_attack
        note, note_col = "", T.ACCENT
        label, extra = "ATTACK", ("shield %d" % g.shield) if g.shield else ""
        value_col, label_col, plate = T.TEXT, T.MUTED, False
        if self.paying is not None:
            # suffering: what is still to pay, bright, falling with each card selected
            paid, need = self.paying
            label, atk, extra, plate = "SUFFER", max(0, need - paid), "of %d" % need, True
            value_col = T.BRIGHT
            if paid >= need:
                note, note_col = "covered", T.BRIGHT
        elif pv and pv.get("defeats") is False:
            suffer = pv.get("suffer")
            if suffer is None and pv.get("uncertain"):
                note = "→ ?"
            else:
                after_atk = suffer if suffer is not None else pv.get("enemy_attack_after")
                if after_atk is None:
                    note = "→ ?"
                elif after_atk != atk:
                    note = "→ %d%s" % (after_atk, q)
        block(0, label, "%d" % atk, value_col, note, note_col, extra, label_col, plate)
        # the health: what is left, and with the selection what would be
        hp = max(0, e.hp)
        after = pv.get("enemy_hp_after", hp) if pv else hp
        note, note_col = "", T.ACCENT
        if pv:
            if pv.get("exact"):
                note, note_col = "exact!" + q, T.BRIGHT
            elif pv.get("defeats"):
                note, note_col = "defeated" + q, T.BRIGHT
            elif after is None or pv.get("defeats") is None:
                note, after = "→ ?", hp
            elif after != hp:
                note = "→ %d%s" % (after, q)
        block(cx + cw + 6, "HEALTH", "%d" % hp, T.TEXT, note, note_col, "of %d" % e.max_hp)
        # a thin, square-ended health bar under the number: what is left in white, what the
        # selection would take in grey, and nothing but an outline when it would kill
        bx, by, bw, bh = cx + cw + 6 + side * 0.18, h - 9, side * 0.64, 4.0
        ui.set_color(T.PANEL_2)
        ui.Path.rect(bx, by, bw, bh).fill()
        if e.max_hp and hp > 0:
            span = bw * hp / float(e.max_hp)
            if pv and pv.get("defeats"):
                edge = ui.Path.rect(bx + 0.5, by + 0.5, max(1.0, span - 1), bh - 1)
                edge.line_width = 1
                ui.set_color(T.BRIGHT)
                edge.stroke()
            else:
                keep = after if (pv and after is not None and after < hp) else hp
                kw = bw * max(0, keep) / float(e.max_hp)
                if kw > 0:
                    ui.set_color(T.BRIGHT)
                    ui.Path.rect(bx, by, kw, bh).fill()
                if span > kw:
                    ui.set_color(T.LOSS)
                    ui.Path.rect(bx + kw, by, span - kw, bh).fill()

    def touch_ended(self, touch) -> None:
        x, y = touch.location
        cx, _, cw, _ = self.card_frame()
        if x < cx:
            if self.on_attack:
                self.on_attack()
        elif self.on_enemy:
            self.on_enemy()


def immunity_text(g: Game) -> tuple:
    """(text, colour) of the enemy's immunity: "Immune to Paladins / Mages", or the Jester's
    cancellation, or none."""
    if g.immunity_cancelled:
        return "Immunity cancelled by the Jester", T.OK
    if g.rules.immune_suits(g):
        legacy = bool(getattr(g.rules, "legacy", False))
        names = [(CLASS_NAME.get(s, s) + "s") if legacy else SUIT_NAME.get(s, s) for s in g.rules.immune_suits(g)]
        return "Immune to %s" % " / ".join(names), T.MUTED
    return "No immunity", T.MUTED


class PileView(ui.View):
    """A pile on the table drawn as a stack of cards, its name under it: face down (the
    reserve, the castle) with the count in the circle on its back, or face up (the discard
    and banished piles, mission 10's face-up castle) with the top card showing and the
    count in a badge on it. An empty pile is an outline. A tap calls ``on_tap``."""

    LABEL_H = 15.0

    def __init__(self, label: str = "", **kw) -> None:
        super().__init__(**kw)
        self.label = label
        self.count = 0
        self.top: Optional[Card] = None      # the face-up top card; None: face down
        self.on_tap: Optional[Callable[[], None]] = None
        self.top_view: Optional[CardView] = None
        self.badge_view: Optional[ui.View] = None
        self.background_color = None

    def card_rect(self) -> tuple:
        h = max(20.0, self.height - self.LABEL_H - 2)
        w = h / 1.42
        if w > self.width - 4:
            w = self.width - 4
            h = w * 1.42
        return ((self.width - w) / 2.0, 0.0, w, h)

    def layers(self) -> int:
        """Cards drawn in the stack: one, two, or three for a pile of ten or more."""
        return 0 if self.count <= 0 else 1 if self.count == 1 else 2 if self.count < 10 else 3

    def set_pile(self, count: int, top: Optional[Card] = None) -> None:
        if (count, top) == (self.count, self.top) and (top is None) == (self.top_view is None):
            return
        self.count, self.top = count, top
        self.layout()
        self.set_needs_display()

    def top_rect(self) -> tuple:
        x, y, w, h = self.card_rect()
        step = 2.0 * (max(1, self.layers()) - 1)
        return (x, y, w - step, h - step)

    def layout(self) -> None:
        if not hasattr(self, "badge_view"):
            return
        for v in (self.top_view, self.badge_view):
            if v is not None:
                self.remove_subview(v)
        self.top_view = self.badge_view = None
        if self.top is None or self.count <= 0:
            return
        x, y, w, h = self.top_rect()
        v = CardView(self.top, frame=(x, y, w, h))
        v.small = True
        v.touch_enabled = False
        self.add_subview(v)
        self.top_view = v
        # over the top card's bottom-right corner, big enough to read, never into the name
        d = max(24.0, min(w * 0.55, 32.0))
        bx = min(x + w - d * 0.7, self.width - d)
        by = min(y + h - d * 0.8, self.height - self.LABEL_H - d)
        badge = CountBadge(self.count, frame=(bx, by, d, d))
        self.add_subview(badge)
        self.badge_view = badge

    def draw(self) -> None:
        x, y, w, h = self.card_rect()
        n = self.layers()
        r = card_radius(w, h)
        if n == 0:
            edge = ui.Path.rounded_rect(x + 1, y + 1, w - 2, h - 2, r)
            edge.line_width = 1
            ui.set_color(T.FRAME_QUIET)
            edge.stroke()
            s_ = min(24.0, w * 0.5)
            veil.number_tile(x + (w - s_) / 2.0, y + (h - s_) / 2.0, s_, "0", False, ink=T.MUTED)
        else:
            step = 2.0
            cw, ch = w - step * (n - 1), h - step * (n - 1)
            for i in range(n - 1, -1, -1):          # the bottom card first, peeking out down-right
                cx_, cy_ = x + step * i, y + step * i
                if self.top is None:
                    if i == 0:
                        draw_back(cx_, cy_, cw, ch, self.count)
                    else:
                        draw_back(cx_, cy_, cw, ch, plain=True)
                elif i > 0:
                    # the edges of the face-up cards under the top one
                    ui.set_color(T.CARD_BORDER)
                    ui.Path.rounded_rect(cx_, cy_, cw, ch, r).fill()
                    ui.set_color(T.CARD_FACE_DIM)
                    ui.Path.rounded_rect(cx_ + 1, cy_ + 1, cw - 2, ch - 2, r - 1).fill()
        ui.draw_string(self.label, (0, self.height - self.LABEL_H, self.width, self.LABEL_H), (T.FONT, 11), T.MUTED,
                       ui.ALIGN_CENTER)

    def touch_ended(self, touch) -> None:
        if self.on_tap is not None:
            self.on_tap()


class BackSample(ui.View):
    """A card back in the chosen style (Settings shows it beside the style's name)."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.background_color = None
        self.touch_enabled = False

    def draw(self) -> None:
        draw_back(0, 0, self.width, self.height, 7)


class CountBadge(ui.View):
    """A pile's count on its face-up top card."""

    def __init__(self, count: int, **kw) -> None:
        super().__init__(**kw)
        self.count = count
        self.touch_enabled = False
        self.background_color = None

    def draw(self) -> None:
        d = min(self.width, self.height) - 3
        veil.number_tile((self.width - d) / 2.0, (self.height - d) / 2.0, d, "%d" % self.count, False)


class HandGrid(ui.View):
    """Cards laid out in rows of four. Taps toggle selection and report through ``on_change``."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.cards: List[Card] = []
        self.views: Dict[str, CardView] = {}
        self.selected: List[str] = []
        self.on_change: Optional[Callable[[], None]] = None
        self.on_card_tap: Optional[Callable[[bool], None]] = None   # a tap selected (True) or dropped a card
        self.selectable: Callable[[Card], bool] = lambda c: True
        self.warned: set = set()      # selected cards whose class power the enemy blocks (jagged white edge)
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
        gap = 8.0

        def size(cols: int) -> tuple:
            rows = int(math.ceil(n / float(cols)))
            cw = (self.width - gap * (cols - 1)) / cols
            ch = min(cw * 1.42, (self.height - gap * (rows - 1) - 8) / rows)
            return min(cw, ch / 1.42), ch, cols

        # rows of four, or of five or six when that gives bigger cards (a short screen)
        cw, ch, cols = size(self.columns) if n > 3 else size(max(1, n))
        if n > self.columns:
            # (a Chanter's draw can make a hand of 13 or more: up to half of it in a row)
            widest = max(self.columns + 3, int(math.ceil(n / 2.0)) + 1)
            cw, ch, cols = max([size(k) for k in range(self.columns, widest)], key=lambda t: (round(t[0], 1), -t[2]))
        total_w = cols * cw + gap * (cols - 1)
        x0 = (self.width - total_w) / 2
        # at the bottom of the grid's room, near the thumb and the action bar (8pt above
        # for a selected card's lift)
        rows = int(math.ceil(n / float(cols)))
        y0 = max(8.0, self.height - rows * ch - gap * (rows - 1))
        for i, c in enumerate(self.cards):
            r, col = divmod(i, cols)
            v = self.views[c.id]
            lift = 8 if v.selected else 0
            v.frame = (x0 + col * (cw + gap), y0 + r * (ch + gap) - lift, cw, ch)

    def _tapped(self, v: CardView) -> None:
        if not self.selectable(v.card):
            return      # greyed: a tap does nothing
        if v.card.id in self.selected:
            self.selected.remove(v.card.id)
            v.selected = False
        else:
            self.selected.append(v.card.id)
            v.selected = True
        self._number()
        self.layout()
        v.set_needs_display()
        if self.on_card_tap:
            self.on_card_tap(v.selected)
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
        # greyed (the mercenary camp's shade) when it cannot join the selection now; only
        # the cards whose state changes are redrawn (every tap comes through here)
        for c, v in ((c, self.views[c.id]) for c in self.cards):
            dim = not self.selectable(c) and c.id not in self.selected
            warn = c.id in self.warned and c.id in self.selected
            if v.shaded != dim or v.warn != warn or v.dimmed:
                v.shaded, v.warn, v.dimmed = dim, warn, False
                v.set_needs_display()


class TableStrip(ui.View):
    """A row of small face-up cards on the table (the mission zone, the cards played against
    the enemy), the oldest on the left, under its name (``label``: "Mission Zone", "Play
    Zone"; nothing about what is in it). When more cards lie there than the row holds, a
    card back with their total comes first and only the newest follow (each new card pushes
    the oldest out of sight); a tap on that back calls ``on_more``. An empty row shows an
    outlined slot."""

    GAP = 6.0
    LABEL_H = 13.0

    def __init__(self, label: str = "", **kw) -> None:
        super().__init__(**kw)
        self.label = label
        self.label_h = self.LABEL_H      # (a little less on a very short screen)
        self.cards: List[Card] = []
        self.on_more: Optional[Callable[[], None]] = None
        self.background_color = None

    def top(self) -> float:
        """Where the cards start, under the name."""
        return self.label_h if self.label else 0.0

    def card_size(self) -> tuple:
        ch = max(16.0, self.height - self.top() - 4)
        return ch / 1.42, ch

    def capacity(self) -> int:
        """How many cards the row shows side by side."""
        cw, _ = self.card_size()
        return max(1, int((self.width + self.GAP) // (cw + self.GAP)))

    def slot_x(self, i: int) -> float:
        """Where slot ``i`` starts: the slots spread over the whole width, so a full row
        lines up with both edges of the table (the piles and the buttons)."""
        cap = self.capacity()
        cw, _ = self.card_size()
        step = (self.width - cw) / float(cap - 1) if cap > 1 else 0.0
        return i * step

    def overflows(self) -> bool:
        return len(self.cards) > self.capacity()

    def shown(self) -> List[Card]:
        """The cards drawn face up: all of them, or the newest beside the back."""
        if not self.overflows():
            return list(self.cards)
        keep = self.capacity() - 1
        return list(self.cards[-keep:]) if keep > 0 else []

    def set_cards(self, cards: Sequence[Card]) -> None:
        self.cards = list(cards)
        self.layout()
        self.set_needs_display()

    def layout(self) -> None:
        if not hasattr(self, "on_more"):
            return
        for v in list(self.subviews):
            self.remove_subview(v)
        cw, ch = self.card_size()
        first = 1 if self.overflows() else 0      # (the card back takes the first slot)
        y = self.top() + 2
        for i, c in enumerate(self.shown()):
            v = CardView(c, frame=(self.slot_x(first + i), y, cw, ch))
            v.small = True
            v.touch_enabled = False
            self.add_subview(v)

    def draw(self) -> None:
        cw, ch = self.card_size()
        y = self.top() + 2
        if self.label:
            ui.draw_string(self.label, (0, 0, self.width, self.label_h), (T.FONT, min(11.0, self.label_h - 2)), T.OK)
        if not self.cards:
            slot = ui.Path.rounded_rect(1, y + 1, cw - 2, ch - 2, card_radius(cw, ch))
            slot.line_width = 1
            ui.set_color(T.RIM)
            slot.stroke()
        elif self.overflows():
            draw_back(0, y, cw, ch, len(self.cards))

    def touch_ended(self, touch) -> None:
        x, _ = touch.location
        cw, _ = self.card_size()
        # the card back, or anywhere in the row's first 44pt (a small back is a small target;
        # the cards beside it take no taps)
        if self.overflows() and x <= max(44.0, (cw + self.slot_x(1)) / 2.0) and self.on_more is not None:
            self.on_more()


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
        self.empty_text = "nothing played yet"
        self.on_tap: Optional[Callable[[], None]] = None

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

    def shown_title(self) -> str:
        """The title as drawn: cut to two lines with "…" when it is longer."""
        w = max(1.0, self.width - 8)
        text = self.title
        if text_size(text, w, self.TITLE_FONT)[1] <= self.LINE * 2.4:
            return text
        words = text.split(" ")
        while len(words) > 1 and text_size(" ".join(words) + "…", w, self.TITLE_FONT)[1] > self.LINE * 2.4:
            words.pop()
        return " ".join(words).rstrip(" ·,:") + "…"

    def touch_ended(self, touch) -> None:
        if self.on_tap is not None:
            self.on_tap()

    def draw(self) -> None:
        th = self.title_height()
        if self.title:
            ui.draw_string(self.shown_title(), (4, 0, self.width - 8, th), (T.FONT, self.TITLE_FONT), T.MUTED)
        if not self.cards and self.empty_text:
            ui.draw_string(self.empty_text, (4, max(20.0, th + 4), self.width - 8, 20), (T.FONT, 12), T.MUTED)
