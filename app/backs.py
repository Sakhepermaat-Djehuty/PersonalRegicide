"""Card backs: the back of every face-down card, and of the reserve and castle piles on the
table, where a plain circle in the middle holds the pile's count. Four styles, picked in
Settings (``card_back``): Lattice (the default), Crowns, Sunburst and Flat.

Each style is ``draw(x, y, w, h, count=None, plain=False)``: one back filling the rect;
``count`` puts the number in the circle (without it the circle's place shows the style's
emblem); ``plain`` draws only the edge and the field, for the cards under the top one of a
pile (only a 2pt strip of them shows). Drawn with fills, ovals, rounded rects and one Path
per line segment, so the headless test renderer draws them as Pythonista does; nothing is
drawn outside the card."""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import ui

from . import theme as T

Point = Tuple[float, float]


def _rr(x: float, y: float, w: float, h: float, r: float, colour: str) -> None:
    ui.set_color(colour)
    ui.Path.rounded_rect(x, y, w, h, max(0.5, r)).fill()


def _oval(cx: float, cy: float, d: float, colour: str) -> None:
    ui.set_color(colour)
    ui.Path.oval(cx - d / 2.0, cy - d / 2.0, d, d).fill()


def _fill_poly(pts: Sequence[Point]) -> None:
    if len(pts) < 3:
        return
    p = ui.Path()
    p.move_to(*pts[0])
    for q in pts[1:]:
        p.line_to(*q)
    p.close()
    p.fill()


def _count(cx: float, cy: float, d: float, count: int, ink: str, scale: float = 1.0) -> None:
    """The count, centred in a circle of diameter ``d``."""
    txt = "%d" % count
    size = d * scale * (0.56 if len(txt) == 1 else 0.5 if len(txt) == 2 else 0.36)
    font = (T.FONT_BOLD, size)
    measure = getattr(ui, "measure_string", None)
    lh = (measure(txt, 0, font)[1] if measure else 0) or size * 1.2
    ui.draw_string(txt, (cx - d / 2.0, cy - lh / 2.0, d, lh), font, ink, ui.ALIGN_CENTER)


# ---------------------------------------------------------------------------- Lattice
# A deep indigo field with a fine violet diamond lattice and a muted gold inner frame.
LAT_RIM = "#211a42"       # the 1pt dark edge: the layers of a pile stay apart
LAT_FIELD = T.CARD_BACK
LAT_LINE = "#7162bc"
LAT_FRAME = "#b8924a"     # muted gold (the bright gold marks a selected card)


def _clip_line(p0: Point, d: Point, poly: Sequence[Point]) -> Optional[Tuple[Point, Point]]:
    """The infinite line p0 + t*d cut to a convex polygon (clockwise on screen): its two
    ends, or None (Cyrus-Beck)."""
    t0, t1 = -1e9, 1e9
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        nx, ny = -(by - ay), bx - ax
        num = nx * (p0[0] - ax) + ny * (p0[1] - ay)
        den = nx * d[0] + ny * d[1]
        if abs(den) < 1e-12:
            if num < 0:
                return None
            continue
        t = -num / den
        if den > 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 >= t1:
            return None
    return (p0[0] + t0 * d[0], p0[1] + t0 * d[1]), (p0[0] + t1 * d[0], p0[1] + t1 * d[1])


def _octagon(l: float, t: float, r: float, b: float, c: float) -> List[Point]:
    return [(l + c, t), (r - c, t), (r, t + c), (r, b - c), (r - c, b), (l + c, b), (l, b - c), (l, t + c)]


def _crown_points(cx: float, cy: float, cw: float, ch: float) -> List[Point]:
    pts = ((-0.5, 0.5), (0.5, 0.5), (0.5, -0.45), (0.24, -0.02), (0.0, -0.62), (-0.24, -0.02), (-0.5, -0.45))
    return [(cx + u * cw, cy + v * ch) for u, v in pts]


def lattice(x: float, y: float, w: float, h: float, count: Optional[int] = None, plain: bool = False) -> None:
    rad = max(6.0, min(w, h) * 0.12)
    big = min(w, h) > 100
    cx, cy = x + w / 2.0, y + h / 2.0
    _rr(x, y, w, h, rad, LAT_RIM)
    _rr(x + 1, y + 1, w - 2, h - 2, rad - 1, LAT_FIELD)
    if plain:
        return
    fi = 7.0 if big else 4.0
    frad = max(2.0, rad - fi + 1)
    frame = ui.Path.rounded_rect(x + fi, y + fi, w - 2 * fi, h - 2 * fi, frad)
    frame.line_width = 1.5 if big else 1.0
    ui.set_color(LAT_FRAME)
    frame.stroke()
    # the lattice, cut by hand to an octagon a little inside the frame
    li = fi + (3.5 if big else 2.0)
    region = _octagon(x + li, y + li, x + w - li, y + h - li, frad * 0.6)
    a = max(8.0, min(w / 5.2, 16.0))
    b = a * 1.4
    reach = int((w / 2.0) / a + (h / 2.0) / b) + 1
    ui.set_color(LAT_LINE)
    for n in range(-reach, reach + 1):
        for p0, d in (((cx + n * a / 2.0, cy + n * b / 2.0), (a, -b)),
                      ((cx + n * a / 2.0, cy - n * b / 2.0), (a, b))):
            seg = _clip_line(p0, d, region)
            if seg is None:
                continue
            (x0, y0), (x1, y1) = seg
            if (x1 - x0) ** 2 + (y1 - y0) ** 2 < 9.0:
                continue          # a stub squeezed into a corner
            ln = ui.Path()
            ln.move_to(x0, y0)
            ln.line_to(x1, y1)
            ln.line_width = 0.6
            ln.stroke()
    if count is None:
        # no count: a small crown in a clear oval
        cw = w * 0.34
        ch = cw * 0.72
        ui.set_color(LAT_FIELD)
        ui.Path.oval(cx - cw * 0.85, cy - ch * 1.05, cw * 1.7, ch * 2.1).fill()
        ui.set_color(LAT_FRAME)
        _fill_poly(_crown_points(cx, cy, cw, ch))
        return
    d = w * 0.64
    gap = 5.0 if big else 2.5
    _oval(cx, cy, d + 2 * gap, LAT_FIELD)      # the lattice stops short of the circle
    _oval(cx, cy, d, T.CARD_FACE)
    _count(cx, cy, d, count, LAT_FIELD)


# ---------------------------------------------------------------------------- Crowns
# An oxblood field in a gold frame with a small crown in each corner.
CR_RIM = "#7f3e4a"        # lighter than the field: the layers of a pile stay apart
CR_FIELD = "#5a1624"
CR_BAND = "#45101c"
CR_GOLD = "#b8924a"
CR_CROWN = "#c39b50"
CR_HALO = "#3a0c16"
CR_INK = "#4a0f1b"
CR_SHAPE = ((0.08, 1.0), (0.92, 1.0), (0.95, 0.7), (1.0, 0.16), (0.73, 0.5), (0.5, -0.04),
            (0.27, 0.5), (0.0, 0.16), (0.05, 0.7))
CR_JEWELS = ((0.0, 0.16), (0.5, -0.04), (1.0, 0.16))


def _crown(cx: float, cy: float, cw: float, ch: float, detail: bool) -> None:
    ui.set_color(CR_CROWN)
    _fill_poly([(cx + (u - 0.5) * cw, cy + (v - 0.5) * ch) for u, v in CR_SHAPE])
    if detail:
        j = cw * 0.15
        for (u, v) in CR_JEWELS:
            ui.Path.oval(cx + (u - 0.5) * cw - j / 2.0, cy + (v - 0.5) * ch - j / 2.0, j, j).fill()


def crowns(x: float, y: float, w: float, h: float, count: Optional[int] = None, plain: bool = False) -> None:
    s = w / 58.0                                        # 1 at the table's pile size
    r = max(6.0, min(w, h) * 0.12)
    _rr(x, y, w, h, r, CR_RIM)
    _rr(x + 1, y + 1, w - 2, h - 2, r - 1, CR_FIELD)
    if plain:
        return
    lw = max(1.0, round(s * 0.8 * 2) / 2.0)
    a = max(3.0, round(3.0 * s * 2) / 2.0)
    if s >= 1.5:
        # large: a double frame
        b = a + lw + max(1.5, round(1.5 * s * 2) / 2.0)
        _rr(x + a, y + a, w - 2 * a, h - 2 * a, r - a, CR_GOLD)
        _rr(x + a + lw, y + a + lw, w - 2 * (a + lw), h - 2 * (a + lw), r - a - lw, CR_BAND)
        c = b + lw
        _rr(x + b, y + b, w - 2 * b, h - 2 * b, r - b, CR_GOLD)
    else:
        # pile size: one frame line, so the circle reads first
        c = a + lw
        _rr(x + a, y + a, w - 2 * a, h - 2 * a, r - a, CR_GOLD)
    _rr(x + c, y + c, w - 2 * c, h - 2 * c, r - c, CR_FIELD)
    cw, ch = 10.0 * s, 7.0 * s
    mx, my = c + 3.0 * s + cw / 2.0, c + 3.0 * s + ch / 2.0
    for (u, v) in ((mx, my), (w - mx, my), (mx, h - my), (w - mx, h - my)):
        _crown(x + u, y + v, cw, ch, s >= 1.5)
    cx, cy = x + w / 2.0, y + h / 2.0
    d = w * 0.62
    if count is None:
        ring = d * 0.62
        _oval(cx, cy, ring, CR_GOLD)
        _oval(cx, cy, ring - 2 * lw, CR_FIELD)
        _crown(cx, cy, ring * 0.56, ring * 0.4, s >= 1.5)
        return
    rim = max(1.0, d * 0.035)
    _oval(cx, cy, d + 2 * max(1.0, s), CR_HALO)
    _oval(cx, cy, d, CR_GOLD)
    _oval(cx, cy, d - 2 * rim, T.CARD_FACE)
    _count(cx, cy, d - 2 * rim, count, CR_INK, 1.1)


# ---------------------------------------------------------------------------- Sunburst
# A dark purple field with thin rays fanning out from behind the circle.
SB_RIM = "#7c6bc2"        # not a sleeve colour (corrupted is a brighter purple)
SB_BORDER = "#1f1630"
SB_FIELD = "#2a1e45"
SB_RAY = "#3a2961"
SB_HUB = "#140e22"
SB_INK = "#2a1f4a"
SB_RAYS = 12
SB_SHARE = 0.42


def _rounded_poly(l: float, t: float, r: float, b: float, rad: float, steps: int = 4) -> List[Point]:
    rad = max(0.0, min(rad, (r - l) / 2.0, (b - t) / 2.0))
    pts = []
    for (ccx, ccy, a0) in ((r - rad, t + rad, -90), (r - rad, b - rad, 0), (l + rad, b - rad, 90),
                           (l + rad, t + rad, 180)):
        for k in range(steps + 1):
            a = math.radians(a0 + 90.0 * k / steps)
            pts.append((ccx + rad * math.cos(a), ccy + rad * math.sin(a)))
    return pts


def _clip_poly(subject: List[Point], clip: Sequence[Point]) -> List[Point]:
    """Sutherland-Hodgman: the convex polygon ``subject`` cut by the convex ``clip``."""
    out = subject
    n = len(clip)
    for i in range(n):
        ax, ay = clip[i]
        bx, by = clip[(i + 1) % n]

        def inside(p: Point) -> bool:
            return (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) >= 0

        def cross(p: Point, q: Point) -> Point:
            dx, dy = q[0] - p[0], q[1] - p[1]
            ex, ey = bx - ax, by - ay
            den = dx * ey - dy * ex
            if abs(den) < 1e-12:
                return q
            s_ = ((ax - p[0]) * ey - (ay - p[1]) * ex) / den
            return (p[0] + s_ * dx, p[1] + s_ * dy)

        src, out = out, []
        if not src:
            break
        prev = src[-1]
        for cur in src:
            if inside(cur):
                if not inside(prev):
                    out.append(cross(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cross(prev, cur))
            prev = cur
    return out


def sunburst(x: float, y: float, w: float, h: float, count: Optional[int] = None, plain: bool = False) -> None:
    rad = max(6.0, min(w, h) * 0.12)
    big = min(w, h) > 100
    cx, cy = x + w / 2.0, y + h / 2.0
    _rr(x, y, w, h, rad, SB_RIM)
    _rr(x + 1, y + 1, w - 2, h - 2, rad - 1, SB_BORDER if not plain else SB_FIELD)
    if plain:
        return
    m = 6.0 if big else 3.0
    region = _rounded_poly(x + m, y + m, x + w - m, y + h - m, rad - m)
    ui.set_color(SB_FIELD)
    _fill_poly(region)
    far = (w + h) * 2.0
    period = 2.0 * math.pi / SB_RAYS
    half = period * SB_SHARE / 2.0
    ui.set_color(SB_RAY)
    for k in range(SB_RAYS):
        a = -math.pi / 2.0 + k * period
        wedge = [(cx, cy), (cx + far * math.cos(a - half), cy + far * math.sin(a - half)),
                 (cx + far * math.cos(a + half), cy + far * math.sin(a + half))]
        _fill_poly(_clip_poly(wedge, region))
    d = w * 0.64
    if count is None:
        hub = d * 0.42
        _oval(cx, cy, hub, SB_HUB)
        _oval(cx, cy, hub * 0.36, SB_RIM)
        return
    gap = max(1.8, d * 0.03)
    _oval(cx, cy, d + 2 * gap, SB_HUB)
    _oval(cx, cy, d, T.CARD_FACE)
    _count(cx, cy, d, count, SB_INK)


# ---------------------------------------------------------------------------- Flat
# A quiet slate back in the app's own flat style: one inset line, a dot in each corner.
FL_RIM = "#0f1116"
FL_EDGE = "#454d65"       # a light bevel inside the dark rim: a pile's layers alternate
FL_FIELD = T.PANEL_2
FL_LINE = "#5c6580"
FL_MOTIF = "#6f7892"


def flat(x: float, y: float, w: float, h: float, count: Optional[int] = None, plain: bool = False) -> None:
    rad = max(6.0, min(w, h) * 0.12)
    u = min(w / 58.0, h / 82.0)
    big = u > 1.6
    cx, cy = x + w / 2.0, y + h / 2.0
    _rr(x, y, w, h, rad, FL_RIM)
    _rr(x + 1, y + 1, w - 2, h - 2, rad - 1, FL_EDGE)
    _rr(x + 2, y + 2, w - 4, h - 4, rad - 2, FL_FIELD)
    if plain:
        return
    fi = 4.0 * u if big else 5.0
    lw = 1.25 if big else 1.0
    frad = max(2.0, rad - fi + 1.0)
    _rr(x + fi, y + fi, w - 2 * fi, h - 2 * fi, frad, FL_LINE)
    _rr(x + fi + lw, y + fi + lw, w - 2 * (fi + lw), h - 2 * (fi + lw), max(1.0, frad - lw), FL_FIELD)
    k = fi + lw + (4.0 * u if big else 4.0)
    dot = 3.0 * u if big else 3.0
    for px, py in ((x + k, y + k), (x + w - k, y + k), (x + k, y + h - k), (x + w - k, y + h - k)):
        _oval(px, py, dot, FL_MOTIF)
    d = w * 0.64
    if count is None:
        _oval(cx, cy, d, FL_LINE)
        _oval(cx, cy, d - 2 * lw, FL_FIELD)
        _oval(cx, cy, dot * 1.4, FL_MOTIF)
        return
    _oval(cx, cy, d, T.CARD_FACE)
    _count(cx, cy, d, count, FL_FIELD)


STYLES: Dict[str, Callable[..., None]] = {"lattice": lattice, "crowns": crowns, "sunburst": sunburst, "flat": flat}
NAMES = {"lattice": "Lattice", "crowns": "Crowns", "sunburst": "Sunburst", "flat": "Flat"}
ORDER = ("lattice", "crowns", "sunburst", "flat")
