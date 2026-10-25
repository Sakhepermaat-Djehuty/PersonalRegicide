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


def fog_view(name: str = "fog.jpg") -> ui.View:
    """The fog, filling its superview (flex), behind everything and never touched."""
    img = image(name)
    if img is None:
        v = ui.View()
        v.background_color = T.BG
    else:
        v = ui.ImageView()
        v.image = img
        v.content_mode = ui.CONTENT_SCALE_ASPECT_FILL
        v.background_color = T.BG
    v.flex = "WH"
    v.touch_enabled = False
    v.name = "veil_fog"
    return v


def add_fog(view: ui.View, name: str = "fog.jpg") -> ui.View:
    """Lay the fog at the back of ``view`` (a screen) and keep it there."""
    f = fog_view(name)
    f.frame = (0, 0, view.width, view.height)
    view.add_subview(f)
    f.send_to_back()
    return f


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


def torn_edge(x0: float, x1: float, y: float, depth: float, seed, step: float = 3.0) -> List[Point]:
    """A ragged edge from (x0, y) to (x1, y): small jagged teeth with now and then a
    deeper bite, all within ``depth`` of y (up and down)."""
    r = rng(seed)
    n = max(4, int(abs(x1 - x0) / step))
    pts = [(x0, y)]
    drift = 0.0
    for i in range(1, n):
        drift = drift * 0.6 + r.uniform(-0.5, 0.5) * depth * 0.6
        tooth = r.uniform(-1, 1) * depth * 0.45
        if r.random() < 0.08:
            tooth -= depth * r.uniform(0.6, 1.0)   # a bite
        pts.append((x0 + (x1 - x0) * i / float(n), y + max(-depth, min(depth, drift + tooth))))
    pts.append((x1, y))
    return pts


def torn_panel(x: float, y: float, w: float, h: float, seed, fill, rim=None, depth: float = 3.0,
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
        polyline(top, rim, 1.0)
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


def hatching(x: float, y: float, w: float, h: float, seed, colour, n: int = 9, width: float = 0.6) -> None:
    """Short parallel strokes in a few loose clusters, like the scored marks in the text
    panel of a Foe card."""
    r = rng(seed)
    for _ in range(max(1, n // 3)):
        cx, cy = x + r.uniform(0.1, 0.9) * w, y + r.uniform(0.15, 0.85) * h
        ang = r.uniform(0.2, 0.7)
        size = r.uniform(0.1, 0.25) * min(w, 3 * h)
        for k in range(3):
            ox = (k - 1) * size * 0.18
            dx, dy = math.cos(ang) * size / 2.0, -math.sin(ang) * size / 2.0
            p0 = _inside((cx + ox - dx, cy - dy), x, y, w, h)
            p1 = _inside((cx + ox + dx, cy + dy), x, y, w, h)
            polyline([p0, p1], colour, width)


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


# ---------------------------------------------------------------------------- the inset frame on buttons
class InsetFrame(ui.View):
    """The pale hairline frame inside a button (a black tile), drawn over it; it follows
    the button's size and never takes a touch."""

    def __init__(self, colour=None, inset: float = 3.0, **kw) -> None:
        super().__init__(**kw)
        self.colour = colour or T.FRAME
        self.inset = inset
        self.flex = "WH"
        self.touch_enabled = False
        self.background_color = None
        self.name = "veil_frame"

    def draw(self) -> None:
        inset_frame(0, 0, self.width, self.height, self.inset, self.colour, 1.0, 2.0)


def frame_of(button) -> Optional[InsetFrame]:
    for v in getattr(button, "subviews", ()):
        if isinstance(v, InsetFrame):
            return v
    return None


def dress_button(b, primary: bool = True, enabled: bool = True) -> None:
    """A black tile with a dark edge and the pale inset frame (bright on a main action,
    dim on a quiet one, faint when it can't be pressed)."""
    b.background_color = T.BTN if enabled else T.BTN_DISABLED
    b.border_width = 1
    b.border_color = T.BTN_EDGE
    b.corner_radius = 4
    b.tint_color = (T.BTN_TEXT if primary else T.TEXT) if enabled else T.FAINT
    f = frame_of(b)
    if f is None:
        f = InsetFrame()
        f.frame = (0, 0, b.width, b.height)
        b.add_subview(f)
    f.colour = (T.FRAME if primary else T.FRAME_QUIET) if enabled else T.FRAME_OFF
    f.set_needs_display()


def dress_switch(sw) -> None:
    """A switch in greys: pale when on (the phone's knob stays white)."""
    sw.tint_color = T.SWITCH_ON
    sw.background_color = None


def dress_segments(seg) -> None:
    """A segmented control in greys: the chosen segment pale, the others framed in grey."""
    seg.tint_color = T.SWITCH_ON


def dress_field(tf) -> None:
    """A text field as a black tile with a grey edge, the text in bone."""
    tf.background_color = T.BTN
    tf.text_color = T.TEXT
    tf.tint_color = T.TEXT
    tf.bordered = False
    tf.border_width = 1
    tf.border_color = T.BTN_EDGE
    tf.corner_radius = 4


# ---------------------------------------------------------------------------- panels
class Panel(ui.View):
    """A choice box: a near-black card with the fog showing faintly through, the pale
    inset frame and a torn top edge lit along its tear. ``ghost`` hides it (the box fades
    away while "Hold to view game" is held)."""

    def __init__(self, seed="panel", **kw) -> None:
        super().__init__(**kw)
        self.seed = seed
        self.ghost = False
        self.background_color = None

    def draw(self) -> None:
        if self.ghost:
            return
        W, H = self.width, self.height
        depth = 3.0
        with ui.GState():
            p = ui.Path()
            top = torn_edge(0, W, depth, depth, self.seed)
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
            hatching(6, 8, W - 12, H - 16, (self.seed, "h"), T.SCAR, 10, 0.6)
        polyline(top, T.RIM, 1.0)
        f = ui.Path.rect(5, depth * 2 + 4, W - 10, H - depth * 2 - 9)
        f.line_width = 1.0
        ui.set_color(T.FRAME_QUIET)
        f.stroke()


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
    "g": (0.62, [
        [(0.55, 0.88, 0.0), (0.3, 1.03, 0.18), (0.05, 0.6, 0.29), (0.16, 0.12, 0.2), (0.45, 0.1, 0.08),
         (0.58, 0.32, 0.0)],
        [(0.7, 1.14, 0.0), (0.62, 0.82, 0.28), (0.6, 0.0, 0.3), (0.5, -0.8, 0.2), (0.2, -1.25, 0.07),
         (-0.2, -1.32, 0.0)],
    ]),
    "i": (0.36, [
        [(0.03, 1.08, 0.0), (0.18, 0.84, 0.29), (0.17, 0.18, 0.27), (0.43, -0.16, 0.0)],
        [(0.07, 1.55, 0.0), (0.18, 1.39, 0.23), (0.27, 1.22, 0.0)],
    ]),
    "c": (0.56, [
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


def logo_size(unit: float, word: str = "Regicide") -> Tuple[float, float]:
    """(width, height) of the wordmark at an x-height of ``unit`` points."""
    w = sum(_LETTERS[ch][0] for ch in word) * unit
    return (w + unit * 0.7, (LOGO_ASCENT + LOGO_DESCENT) * unit)


def logo_path(x: float, y: float, w: float, h: float, word: str = "Regicide", slant: float = 0.1):
    """The wordmark fitted in the rect and centred: (one Path of every stroke, x-height)."""
    lw, lh = logo_size(1.0, word)
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
        ox += adv * unit
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
            chips(x, y, w, h, (word, "scored"), int(w / unit * 7), unit, LOGO_SCORE)


def chips(x: float, y: float, w: float, h: float, seed, n: int, unit: float, colour) -> None:
    """Short dark nicks at loose angles, scattered over the rect (the wear on brushed
    letters, cut into a stone)."""
    r = rng(seed)
    for _ in range(int(n)):
        cx, cy = x + r.uniform(0, w), y + r.uniform(0, h)
        length = unit * r.uniform(0.25, 0.9)
        ang = r.uniform(-0.4, 0.9)
        dx, dy = math.cos(ang) * length / 2.0, -math.sin(ang) * length / 2.0
        bend = (cx + r.uniform(-0.08, 0.08) * unit, cy + r.uniform(-0.08, 0.08) * unit)
        polyline([(cx - dx, cy - dy), bend, (cx + dx, cy + dy)], colour, unit * r.uniform(0.025, 0.06))


LOGO_SCORE = (0.0, 0.0, 0.0, 0.62)


class LogoView(ui.View):
    """The wordmark filling the view."""

    def __init__(self, colour=None, **kw) -> None:
        super().__init__(**kw)
        self.colour = colour or T.TEXT
        self.background_color = None
        self.touch_enabled = False

    def draw(self) -> None:
        draw_logo(0, 0, self.width, self.height, self.colour)
