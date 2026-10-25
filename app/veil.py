"""The Veil look (after Veilwraith): monochrome, fog behind everything, black cards with
pale marks, the thin inset frame of its number tiles, text panels with a torn and
scratched top edge, and a hand-brushed wordmark. Everything here is drawn with paths
or comes from ``app/art`` (made by tools/art/make_art.py from noise), so the headless
renderer draws it as Pythonista does.

The marks a card or panel carries (its tear, its scratches) are seeded by something
stable (a card id, a title), so a card keeps the same scars every time it is drawn."""
from __future__ import annotations

import math
import os
import random
import zlib
from typing import Dict, List, Optional, Sequence, Tuple

import ui

from . import theme as T

Point = Tuple[float, float]
ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art")


# ---------------------------------------------------------------------------- textures
_images: Dict[str, object] = {}


def image(name: str):
    """A picture from ``app/art`` (cached), or None when it is missing."""
    if name not in _images:
        path = os.path.join(ART, name)
        img = ui.Image.named(path) if os.path.exists(path) else None
        _images[name] = img if (img is not None and getattr(img, "size", (0, 0))[0]) else None
    return _images[name]


def draw_fog(x: float, y: float, w: float, h: float, name: str = "fog_l.jpg") -> None:
    """The fog filling the rect (cut to it), inside a view's draw()."""
    img = image(name)
    if img is None:
        return
    iw, ih = img.size
    k = max(w / iw, h / ih)
    dw, dh = iw * k, ih * k
    with ui.GState():
        ui.Path.rect(x, y, w, h).add_clip()
        img.draw(x + (w - dw) / 2.0, y + (h - dh) / 2.0, dw, dh)


# ---------------------------------------------------------------------------- seeded marks
def rng(seed) -> random.Random:
    return random.Random(zlib.crc32(str(seed).encode("utf-8")))


def fill_poly(pts: Sequence[Point], colour) -> None:
    if len(pts) < 3:
        return
    ui.set_color(colour)
    p = ui.Path()
    p.move_to(*pts[0])
    for q in pts[1:]:
        p.line_to(*q)
    p.close()
    p.fill()


def polyline(pts: Sequence[Point], colour, width: float = 1.0) -> None:
    if len(pts) < 2:
        return
    ui.set_color(colour)
    p = ui.Path()
    p.move_to(*pts[0])
    for q in pts[1:]:
        p.line_to(*q)
    p.line_width = width
    p.line_join_style = ui.LINE_JOIN_ROUND
    p.stroke()


def torn_edge(x0: float, x1: float, y: float, depth: float, seed, step: float = 5.0) -> List[Point]:
    """A ragged edge from (x0, y) to (x1, y): a wandering line with small teeth and now
    and then a deeper bite, all within ``depth`` of y (up and down)."""
    r = rng(seed)
    n = max(4, int(abs(x1 - x0) / step))
    pts = [(x0, y)]
    drift = 0.0
    for i in range(1, n):
        drift = drift * 0.85 + r.uniform(-1, 1) * depth * 0.35
        tooth = r.uniform(-1, 1) * depth * 0.25
        if r.random() < 0.08:
            tooth -= depth * r.uniform(0.5, 0.9)   # a bite
        pts.append((x0 + (x1 - x0) * i / float(n), y + max(-depth, min(depth, drift + tooth))))
    pts.append((x1, y))
    return pts


def lit_tear(top: Sequence[Point], rim, seed) -> None:
    """Light a tear as card torn under a lamp: a dark line just under it, the lit edge as a
    ragged band (now thin, now thick) and tufts of short fibres standing off it."""
    polyline([(px, py + 0.8) for px, py in top], TEAR_SHADOW, 1.4)
    r = rng((seed, "fibres"))
    upper, lower = [], []
    for px, py in top:
        wd = r.uniform(0.8, 2.2)
        upper.append((px, py - wd * 0.55))
        lower.append((px, py + wd * 0.45))
    fill_poly(upper + lower[::-1], rim)
    x = top[0][0] + r.uniform(2, 6)
    end = top[-1][0]
    i = 0
    while x < end - 2:
        while i < len(top) - 2 and top[i + 1][0] < x:
            i += 1
        (ax, ay), (bx, by) = top[i], top[i + 1]
        t = (x - ax) / (bx - ax) if bx != ax else 0.0
        y = ay + (by - ay) * t - 0.6
        for _ in range(r.randint(1, 3)):
            length = r.uniform(3.0, 4.5) if r.random() < 0.15 else r.uniform(0.8, 2.4)
            ang = -math.pi / 2 + r.uniform(-1.1, 1.1)
            fx = x + r.uniform(-1.5, 1.5)
            polyline([(fx, y), (fx + math.cos(ang) * length, y + math.sin(ang) * length)], rim, r.uniform(0.4, 0.7))
        x += r.uniform(3, 12)


TEAR_SHADOW = (0.0, 0.0, 0.0, 0.6)


def torn_panel(x: float, y: float, w: float, h: float, seed, fill, rim=None, depth: float = 4.5,
               bottom_radius: float = 0.0) -> List[Point]:
    """A panel filling the rect whose top edge is torn (the text panel of a Veilwraith
    Foe card): filled with ``fill``, the tear lit along its edge with ``rim``. Returns
    the tear's points."""
    top = torn_edge(x, x + w, y + depth, depth, seed)
    r = min(bottom_radius, w / 2.0, h / 2.0)
    pts = list(top)
    if r > 0:
        for i in range(7):
            a = (math.pi / 2) * i / 6.0
            pts.append((x + w - r + r * math.cos(a), y + h - r + r * math.sin(a)))
        for i in range(7):
            a = math.pi / 2 + (math.pi / 2) * i / 6.0
            pts.append((x + r + r * math.cos(a), y + h - r + r * math.sin(a)))
    else:
        pts += [(x + w, y + h), (x, y + h)]
    fill_poly(pts, fill)
    if rim:
        lit_tear(top, rim, seed)
    return top


def scratches(x: float, y: float, w: float, h: float, seed, n: int, colour, width: float = 0.75,
              slant: float = 0.35) -> None:
    """``n`` thin scratches across the rect, mostly along one slant (scored, not random
    noise): each a straight line or with one slight kink, kept inside the rect."""
    r = rng(seed)
    for _ in range(int(n)):
        length = r.uniform(0.25, 0.8) * w
        ang = slant + r.uniform(-0.25, 0.25)
        cx, cy = x + r.uniform(0.1, 0.9) * w, y + r.uniform(0.1, 0.9) * h
        dx, dy = math.cos(ang) * length / 2.0, -math.sin(ang) * length / 2.0
        a = (cx - dx, cy - dy)
        b = (cx + dx, cy + dy)
        mid = (cx + r.uniform(-1.5, 1.5), cy + r.uniform(-1.5, 1.5))
        pts = [_inside(p, x, y, w, h) for p in (a, mid, b)]
        polyline(pts, colour, width * r.uniform(0.6, 1.2))


def hatching(x: float, y: float, w: float, h: float, seed, colour, n: int = 10, width: float = 0.8) -> None:
    """Long scored strokes, roughly along one slant, cut into a panel (the marks across the
    text panel of a Foe card)."""
    r = rng(seed)
    for _ in range(int(n)):
        length = r.uniform(0.3, 0.7) * w
        ang = 0.3 + r.uniform(-0.2, 0.2)
        cx, cy = x + r.uniform(0.05, 0.95) * w, y + r.uniform(0.1, 0.9) * h
        dx, dy = math.cos(ang) * length / 2.0, -math.sin(ang) * length / 2.0
        p0 = _inside((cx - dx, cy - dy), x, y, w, h)
        p1 = _inside((cx + dx, cy + dy), x, y, w, h)
        polyline([p0, p1], colour, width * r.uniform(0.75, 1.25))


def cracks(x: float, y: float, w: float, h: float, seed, colour, n: int = 3, width: float = 0.9) -> None:
    """Branching cracks starting at the rect's edge (a scarred, corrupted sleeve)."""
    r = rng(seed)
    for i in range(int(n)):
        side = r.randrange(4)
        if side == 0:
            p, ang = (x + r.uniform(0.2, 0.8) * w, y), math.pi / 2
        elif side == 1:
            p, ang = (x + w, y + r.uniform(0.2, 0.8) * h), math.pi
        elif side == 2:
            p, ang = (x + r.uniform(0.2, 0.8) * w, y + h), -math.pi / 2
        else:
            p, ang = (x, y + r.uniform(0.2, 0.8) * h), 0.0
        _crack(p, ang, min(w, h) * r.uniform(0.25, 0.45), r, colour, width, x, y, w, h, 2)


def _crack(p: Point, ang: float, length: float, r: random.Random, colour, width: float, x, y, w, h,
           depth: int) -> None:
    pts = [p]
    seg = max(2.0, length / 5.0)
    for _ in range(5):
        ang += r.uniform(-0.6, 0.6)
        q = (pts[-1][0] + math.cos(ang) * seg, pts[-1][1] + math.sin(ang) * seg)
        pts.append(_inside(q, x, y, w, h))
    polyline(pts, colour, width)
    if depth > 0 and r.random() < 0.7:
        k = r.randrange(1, len(pts) - 1)
        _crack(pts[k], ang + r.choice((-1, 1)) * r.uniform(0.6, 1.1), length * 0.5, r, colour, width * 0.7,
               x, y, w, h, depth - 1)


def _inside(p: Point, x: float, y: float, w: float, h: float) -> Point:
    return (min(max(p[0], x + 0.5), x + w - 0.5), min(max(p[1], y + 0.5), y + h - 0.5))


def inset_frame(x: float, y: float, w: float, h: float, inset: float, colour, width: float = 1.0,
                radius: float = 2.0) -> None:
    """The thin pale frame inside a black tile (Veilwraith's 1/2/3 action tiles)."""
    f = ui.Path.rounded_rect(x + inset, y + inset, w - 2 * inset, h - 2 * inset, max(0.5, radius))
    f.line_width = width
    ui.set_color(colour)
    f.stroke()


def rough_rule(x0: float, x1: float, y: float, seed, colour, width: float = 1.0) -> None:
    """A hand-scored horizontal rule: slightly uneven, thinning to nothing at both ends."""
    r = rng(seed)
    n = max(6, int((x1 - x0) / 6.0))
    top, bottom = [], []
    for i in range(n + 1):
        t = i / float(n)
        px = x0 + (x1 - x0) * t
        py = y + r.uniform(-0.35, 0.35)
        half = width * 0.5 * math.sin(math.pi * t) ** 0.4 * r.uniform(0.7, 1.3)
        top.append((px, py - half))
        bottom.append((px, py + half))
    fill_poly(top + bottom[::-1], colour)


def number_tile(x: float, y: float, s: float, text: str, lit: bool = True, w: Optional[float] = None,
                ink=None) -> None:
    """A number on a small black tile with the pale frame inside it (Veilwraith's 1/2/3
    tiles): a pile's count, the order a card was picked in, a stop on the map."""
    w = s if w is None else w
    ui.set_color(T.BTN)
    ui.Path.rounded_rect(x, y, w, s, 2.5).fill()
    edge = ui.Path.rounded_rect(x + 0.5, y + 0.5, w - 1, s - 1, 2.5)
    edge.line_width = 1
    ui.set_color(T.CARD_RIM)
    edge.stroke()
    fi = max(2.5, s * 0.12)
    inset_frame(x, y, w, s, fi, T.FRAME if lit else T.FRAME_QUIET, 1.0, 1.5)
    size = s * (0.58 if len(text) < 2 else 0.5 if len(text) < 3 else 0.4)
    ui.draw_string(text, (x, y + (s - size * 1.3) / 2.0, w, size * 1.35), (T.FONT_BOLD, size),
                   ink or T.BTN_TEXT, ui.ALIGN_CENTER)


class RoughRule(ui.View):
    """A scored rule across its width (in place of a flat line)."""

    def __init__(self, colour=None, seed="rule", **kw) -> None:
        super().__init__(**kw)
        self.colour = colour or T.RIM
        self.seed = seed
        self.background_color = None
        self.touch_enabled = False

    def draw(self) -> None:
        rough_rule(0, self.width, self.height / 2.0, self.seed, self.colour, max(1.0, min(1.6, self.height)))


# ---------------------------------------------------------------------------- the inset frame on buttons
class InsetFrame(ui.View):
    """The pale frame inside a button (a black tile), drawn over it; it follows the
    button's size and never takes a touch. ``look`` is how the button is dressed: "lit",
    "quiet", "off", "chosen" or "bare"."""

    def __init__(self, colour=None, inset: float = 3.0, **kw) -> None:
        super().__init__(**kw)
        self.colour = colour or T.FRAME
        self.inset = inset
        self.line = 1.0
        self.look = "lit"
        self.flex = "WH"
        self.touch_enabled = False
        self.background_color = None
        self.name = "veil_frame"

    def draw(self) -> None:
        if self.colour is None:
            return
        inset_frame(0, 0, self.width, self.height, self.inset + (self.line - 1) * 0.5, self.colour, self.line, 2.0)


def frame_of(button) -> Optional[InsetFrame]:
    for v in getattr(button, "subviews", ()):
        if isinstance(v, InsetFrame):
            return v
    return None


# how each look dresses a button: (fill, title, frame colour, frame width, edge)
LOOKS = {
    "lit": (lambda: (T.BTN_LIT, T.BRIGHT, T.FRAME, 2.0, T.BTN_EDGE)),
    "quiet": (lambda: (T.BTN, T.TEXT, T.FRAME_QUIET, 1.0, T.BTN_EDGE)),
    "off": (lambda: (T.BTN_DISABLED, T.BTN_TEXT_OFF, T.FRAME_OFF, 1.0, T.BTN_EDGE)),
    "chosen": (lambda: (T.TEXT, T.BG, None, 1.0, T.TEXT)),
    "bare": (lambda: (None, T.TEXT, None, 1.0, None)),
}


def dress_button(b, primary: bool = True, enabled: bool = True, chosen: bool = False, bare: bool = False) -> None:
    """A black tile with a dark edge and the pale frame inside it: "lit" for the one main
    action (a heavier frame, a white title), "quiet" (a dim frame), "off" when it can't be
    pressed, "chosen" for the picked one of a set (pale, the title in black, as a ticked
    box) and "bare" for a plain line of text (a menu's lesser entries)."""
    look = "off" if not enabled else "chosen" if chosen else "bare" if bare else "lit" if primary else "quiet"
    fill, title, frame, line, edge = LOOKS[look]()
    b.background_color = fill
    b.border_width = 1 if edge else 0
    b.border_color = edge or T.BG
    b.corner_radius = 4
    b.tint_color = title
    f = frame_of(b)
    if f is None:
        f = InsetFrame()
        f.frame = (0, 0, b.width, b.height)
        b.add_subview(f)
    f.colour, f.line, f.look = frame, line, look
    f.set_needs_display()


def dress_field(tf) -> None:
    """A text field inside a black tile (``field_box``): the text in bone, no frame of its own."""
    tf.background_color = None
    tf.text_color = T.TEXT
    tf.tint_color = T.TEXT
    tf.bordered = False


def field_box(tf, frame) -> ui.View:
    """A black tile with a grey edge holding the text field 8pt in from its sides (a field
    with no frame of its own has no inset on the phone)."""
    box = ui.View(frame=frame)
    box.background_color = T.BTN
    box.border_width = 1
    box.border_color = T.BTN_EDGE
    box.corner_radius = 4
    tf.frame = (8, 0, frame[2] - 16, frame[3])
    tf.flex = "WH"
    dress_field(tf)
    box.add_subview(tf)
    return box


def force_dark(view) -> bool:
    """The look is black: ask iOS for its dark appearance on this view and on the view
    controller that shows it (so the keyboard, the status bar and the phone's own controls
    stay dark whatever the phone is set to), on the main thread. Pythonista's own window is
    left alone. Returns whether the controller was found (True off the phone, where there is
    nothing to do; False: try again once the view is shown)."""
    try:
        from objc_util import ObjCClass, ObjCInstance, on_main_thread
    except ImportError:
        return True
    found = []

    @on_main_thread
    def apply():
        o = ObjCInstance(view)
        o.setOverrideUserInterfaceStyle_(2)
        vc = ObjCClass("UIViewController")
        r = o.nextResponder()
        while r is not None and not r.isKindOfClass_(vc):
            r = r.nextResponder()
        if r is not None:
            r.setOverrideUserInterfaceStyle_(2)
            r.setNeedsStatusBarAppearanceUpdate()
            found.append(True)

    try:
        apply()
    except Exception as e:      # an older iOS: the look still works, only the phone's own bits stay light
        print("force_dark:", e)
        return True
    return bool(found)


# ---------------------------------------------------------------------------- panels
class Panel(ui.View):
    """A choice box: a near-black card with the fog showing faintly through, torn along its
    top (the tear lit, with fibres), long dark scores across it and a dim frame inside.
    ``ghost`` hides it (the box fades away while "Hold to view game" is held)."""

    DEPTH = 4.5

    def __init__(self, seed="panel", **kw) -> None:
        super().__init__(**kw)
        self.seed = seed
        self.ghost = False
        self.background_color = None

    def draw(self) -> None:
        if self.ghost:
            return
        W, H = self.width, self.height
        depth = self.DEPTH
        top = torn_edge(0, W, depth, depth, self.seed)
        with ui.GState():
            p = ui.Path()
            p.move_to(*top[0])
            for q in top[1:]:
                p.line_to(*q)
            p.line_to(W, H)
            p.line_to(0, H)
            p.close()
            ui.set_color(T.PANEL)
            p.fill()
            p.add_clip()
            draw_fog(0, 0, W, H, "fog_l.jpg")
            ui.set_color(T.PANEL_VEIL)
            ui.Path.rect(0, 0, W, H).fill()
            hatching(6, 10, W - 12, H - 18, (self.seed, "h"), T.SCAR, 10, 0.8)
        lit_tear(top, T.RIM, self.seed)
        f = ui.Path.rect(5, depth * 2 + 4, W - 10, H - depth * 2 - 9)
        f.line_width = 1.0
        ui.set_color(T.FRAME_QUIET)
        f.stroke()


class Toast(ui.View):
    """A short message over the table (a Hint, a refusal): bone text on a dark scrap torn
    along its top. ``text`` as a label's."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self._text = ""
        self.background_color = None
        self.touch_enabled = False

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = str(value)
        self.set_needs_display()

    def draw(self) -> None:
        W, H = self.width, self.height
        torn_panel(0, 0, W, H, ("toast", self._text), T.TORN_PANEL, T.RIM, 3.0)
        # two lines if it needs them, smaller type before anything is lost
        size = 13.0
        while True:
            tw, th = ui.measure_string(self._text, W - 12, (T.FONT_BOLD, size))
            if th <= H - 8 or size <= 10:
                break
            size -= 0.5
        ui.draw_string(self._text, (6, 3 + (H - 3 - th) / 2.0, W - 12, th + 2), (T.FONT_BOLD, size), T.TEXT,
                       ui.ALIGN_CENTER)


# ---------------------------------------------------------------------------- the wordmark
# "Regicide" in heavy brush strokes, cut rather than written: each stroke is a list of
# (x, y, width) in letter units (the x-height is 1, the baseline 0, y up), tapering to a
# point at both ends; the stems rise as horns, the tails run on below the line, and a few
# dark scratches are scored through the letters (the same ones every time).
_LETTERS: Dict[str, Tuple[float, List[List[Tuple[float, float, float]]]]] = {
    "R": (0.98, [
        [(0.06, 2.65, 0.0), (0.17, 1.95, 0.3), (0.2, 0.95, 0.3), (0.13, 0.12, 0.26), (-0.06, -0.62, 0.0)],
        [(0.2, 1.92, 0.03), (0.56, 2.22, 0.18), (0.9, 1.9, 0.28), (0.74, 1.3, 0.22), (0.4, 1.06, 0.08),
         (0.22, 1.02, 0.0)],
        [(0.4, 1.08, 0.05), (0.64, 0.58, 0.27), (0.8, 0.06, 0.21), (1.08, -0.32, 0.0)],
    ]),
    "e": (0.6, [
        [(0.08, 0.56, 0.0), (0.42, 0.68, 0.12), (0.5, 0.92, 0.15), (0.28, 1.03, 0.19), (0.06, 0.6, 0.29),
         (0.14, 0.08, 0.22), (0.4, 0.0, 0.1), (0.66, 0.25, 0.0)],
    ]),
    "g": (0.67, [
        [(0.55, 0.88, 0.0), (0.3, 1.03, 0.18), (0.05, 0.6, 0.29), (0.16, 0.12, 0.2), (0.45, 0.1, 0.08),
         (0.58, 0.32, 0.0)],
        [(0.7, 1.14, 0.0), (0.62, 0.82, 0.28), (0.6, 0.0, 0.3), (0.5, -0.8, 0.2), (0.2, -1.25, 0.07),
         (-0.2, -1.32, 0.0)],
    ]),
    "i": (0.41, [
        [(0.03, 1.08, 0.0), (0.18, 0.84, 0.29), (0.17, 0.18, 0.27), (0.43, -0.16, 0.0)],
        [(0.07, 1.55, 0.0), (0.18, 1.39, 0.23), (0.27, 1.22, 0.0)],
    ]),
    "c": (0.61, [
        [(0.6, 0.86, 0.0), (0.36, 1.03, 0.17), (0.06, 0.6, 0.29), (0.12, 0.1, 0.22), (0.38, 0.0, 0.1),
         (0.66, 0.21, 0.0)],
    ]),
    "d": (0.8, [
        [(0.52, 0.86, 0.0), (0.28, 1.03, 0.18), (0.04, 0.6, 0.29), (0.13, 0.12, 0.2), (0.42, 0.08, 0.08),
         (0.58, 0.3, 0.0)],
        [(0.98, 2.78, 0.0), (0.74, 2.02, 0.24), (0.67, 1.0, 0.3), (0.65, 0.15, 0.28), (0.92, -0.22, 0.0)],
    ]),
}
LOGO_ASCENT, LOGO_DESCENT = 2.8, 1.35     # the wordmark's height above and below the line, in x-heights


def _catmull(points: Sequence[Tuple[float, float, float]], steps: int = 5) -> List[Tuple[float, float, float]]:
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(steps):
            t = s / float(steps)
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                                    + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in range(3)))
    out.append(points[-1])
    return out


def _stroke_poly(stroke, ox: float, base: float, unit: float, slant: float, r: random.Random) -> List[Point]:
    """One brush stroke as a filled outline: the centre line smoothed a little (it stays
    angular), each side offset by half its width (a broad nib held at an angle thickens
    the down strokes), the edges roughened as a dry brush leaves them."""
    pts = _catmull(stroke)
    left, right = [], []
    nib = math.radians(35)
    for i, (x, y, wd) in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        ang = math.atan2(dy, dx)
        k = 0.4 + 0.6 * abs(math.sin(ang - nib))
        half = max(0.0, wd) * k * 0.5
        rough = 0.018 if half > 0.02 else 0.0
        hl = half + r.uniform(-rough, rough)
        hr = half + r.uniform(-rough, rough)
        sx = x + y * slant
        left.append((ox + (sx - dy / n * hl) * unit, base - (y + dx / n * hl) * unit))
        right.append((ox + (sx + dy / n * hr) * unit, base - (y - dx / n * hr) * unit))
    return left + right[::-1]


def _adv(ch: str, small: bool) -> float:
    """A letter's advance; small (a pile's back), the round letters stand further apart."""
    return _LETTERS[ch][0] + (0.08 if small and ch in "gic" else 0.0)


def logo_size(unit: float, word: str = "Regicide", small: bool = False) -> Tuple[float, float]:
    """(width, height) of the wordmark at an x-height of ``unit`` points."""
    w = sum(_adv(ch, small) for ch in word) * unit
    return (w + unit * 0.7, (LOGO_ASCENT + LOGO_DESCENT) * unit)


def logo_path(x: float, y: float, w: float, h: float, word: str = "Regicide", slant: float = 0.1):
    """The wordmark fitted in the rect and centred: (one Path of every stroke, x-height)."""
    lw, lh = logo_size(1.0, word)
    unit = min(w / lw, h / lh)
    small = unit < 12
    if small:
        lw, lh = logo_size(1.0, word, True)
        unit = min(w / lw, h / lh)
    ox = x + (w - lw * unit) / 2.0 + unit * 0.35
    base = y + (h - lh * unit) / 2.0 + LOGO_ASCENT * unit
    r = rng(word)
    p = ui.Path()
    for ch in word:
        adv, strokes = _LETTERS[ch]
        for s in strokes:
            pts = _stroke_poly(s, ox, base, unit, slant, r)
            p.move_to(*pts[0])
            for q in pts[1:]:
                p.line_to(*q)
            p.close()
        ox += _adv(ch, small) * unit
    return p, unit


def draw_logo(x: float, y: float, w: float, h: float, colour, word: str = "Regicide", slant: float = 0.1,
              scored: bool = True) -> None:
    """The wordmark; ``scored``: with dark scratches through the letters (left out when it
    is small, where they would only muddy it)."""
    p, unit = logo_path(x, y, w, h, word, slant)
    ui.set_color(colour)
    p.fill()
    if scored and unit >= 9:
        with ui.GState():
            p.add_clip()
            nicks(x, y, w, h, (word, "scored"), int(w / unit * 9), unit, slant)


def nicks(x: float, y: float, w: float, h: float, seed, n: int, unit: float, slant: float) -> None:
    """Thin black gaps running along the down strokes, as a dry brush leaves them."""
    r = rng(seed)
    for _ in range(int(n)):
        cx, cy = x + r.uniform(0, w), y + r.uniform(0, h)
        length = unit * r.uniform(0.2, 0.45)
        ang = math.pi / 2 + slant + r.uniform(-0.35, 0.35)       # near the stroke direction
        dx, dy = math.cos(ang) * length / 2.0, -math.sin(ang) * length / 2.0
        polyline([(cx - dx, cy - dy), (cx + dx, cy + dy)], LOGO_SCORE, unit * r.uniform(0.012, 0.02))


LOGO_SCORE = (0.0, 0.0, 0.0, 0.9)


class LogoView(ui.View):
    """The wordmark filling the view."""

    def __init__(self, colour=None, **kw) -> None:
        super().__init__(**kw)
        self.colour = colour or T.TEXT
        self.background_color = None
        self.touch_enabled = False

    def draw(self) -> None:
        draw_logo(0, 0, self.width, self.height, self.colour)
