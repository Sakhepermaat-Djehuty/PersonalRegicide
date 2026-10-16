"""Fake ``ui`` module. See package docstring."""
from __future__ import annotations

import os
from typing import Any, Callable, List, Optional, Tuple

try:
    from PIL import Image as PILImage, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    PILImage = ImageDraw = ImageFont = None  # type: ignore

ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT = 0, 1, 2
LB_WORD_WRAP, LB_CHAR_WRAP, LB_CLIP, LB_TRUNCATE_HEAD, LB_TRUNCATE_TAIL, LB_TRUNCATE_MIDDLE = 0, 1, 2, 3, 4, 5

_screen = [390.0, 844.0]   # iPhone 14 logical points
_presented: List["View"] = []
SCALE = 2  # render at 2x for legibility


# Deferred layout, as on the phone: adding or removing a subview marks the receiving view,
# and the UI loop later runs the layout() of every marked view (the outermost first). A
# view's changes to its own subviews during its own layout() do not mark it again; ``tap``
# ends with a ``flush`` of the root, like the run loop after a touch. On the phone this is
# how a card pop-up added to a screen that rebuilds itself in layout() vanished before it
# was drawn. On by default; FAKEUI_DEFERRED_LAYOUT=0 (or set_deferred_layout(False)) runs
# layout() only when a size changes.
_deferred = [os.environ.get("FAKEUI_DEFERRED_LAYOUT", "1") != "0"]
_marked: List["View"] = []
_laying_out: List["View"] = []


def set_deferred_layout(on: bool) -> None:
    _deferred[0] = bool(on)
    del _marked[:]


def _mark(v: "View") -> None:
    if _deferred[0] and v not in _laying_out and v not in _marked:
        _marked.append(v)


def flush(root: "View", passes: int = 20) -> int:
    """Run the layout() of every view marked by add/remove_subview under ``root``, the
    outermost first, until none is marked; returns how many ran. Raises if it never
    settles (a layout that marks its view again forever would hang the phone)."""
    ran = 0
    for _ in range(passes):
        order: List[View] = []

        def walk(v: "View") -> None:
            order.append(v)
            for sub in list(v.subviews):
                walk(sub)
        walk(root)
        todo = [v for v in order if v in _marked]
        if not todo:
            return ran
        for v in todo:
            if v not in _marked:
                continue                    # an outer view's layout already rebuilt or dropped it
            _marked.remove(v)
            if v is not root and not _attached(v, root):
                continue
            _laying_out.append(v)
            try:
                if callable(getattr(v, "layout", None)):
                    v.layout()
                    ran += 1
            finally:
                _laying_out.remove(v)
    raise RuntimeError("layout never settles: %r" % [type(v).__name__ for v in _marked])


def _attached(v: "View", root: "View") -> bool:
    while v is not None:
        if v is root:
            return True
        v = v.superview
    return False


def set_screen_size(w: float, h: float) -> None:
    _screen[0], _screen[1] = float(w), float(h)


def get_screen_size() -> Tuple[float, float]:
    return (_screen[0], _screen[1])


# ----------------------------------------------------------------------------- colours
_NAMED = {
    "white": (1, 1, 1, 1), "black": (0, 0, 0, 1), "red": (1, 0, 0, 1), "green": (0, 0.5, 0, 1),
    "blue": (0, 0, 1, 1), "gray": (0.5, 0.5, 0.5, 1), "grey": (0.5, 0.5, 0.5, 1),
    "yellow": (1, 1, 0, 1), "orange": (1, 0.5, 0, 1), "clear": (0, 0, 0, 0), "lightgray": (0.83, 0.83, 0.83, 1),
    "darkgray": (0.66, 0.66, 0.66, 1), "purple": (0.5, 0, 0.5, 1), "brown": (0.6, 0.4, 0.2, 1),
}


def parse_color(c: Any) -> Tuple[float, float, float, float]:
    if c is None:
        return (0, 0, 0, 0)
    if isinstance(c, str):
        s = c.strip().lower()
        if s in _NAMED:
            return _NAMED[s]
        if s.startswith("#"):
            s = s[1:]
            if len(s) == 3:
                s = "".join(ch * 2 for ch in s)
            if len(s) == 6:
                s += "ff"
            r, g, b, a = (int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4, 6))
            return (r, g, b, a)
        raise ValueError("unknown colour %r" % c)
    if isinstance(c, (int, float)):
        return (float(c), float(c), float(c), 1.0)
    t = tuple(float(x) for x in c)
    if len(t) == 3:
        return (t[0], t[1], t[2], 1.0)
    return (t[0], t[1], t[2], t[3])


def _rgba255(c: Any) -> Tuple[int, int, int, int]:
    r, g, b, a = parse_color(c)
    return (int(round(r * 255)), int(round(g * 255)), int(round(b * 255)), int(round(a * 255)))


# ----------------------------------------------------------------------------- fonts
_FONT_DIR_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
]


def _font_file(bold: bool) -> Optional[str]:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in _FONT_DIR_CANDIDATES:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


_font_cache = {}


def _pil_font(font: Any):
    name, size = ("<system>", 17.0) if not font else (font[0], float(font[1]))
    bold = "bold" in str(name).lower() or "black" in str(name).lower() or "heavy" in str(name).lower()
    key = (bold, int(round(size * SCALE)))
    if key not in _font_cache:
        path = _font_file(bold)
        if path and ImageFont is not None:
            _font_cache[key] = ImageFont.truetype(path, key[1])
        else:  # pragma: no cover
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def measure_string(text: str, max_width: float = 0, font: Any = None, alignment: int = ALIGN_LEFT,
                   line_break_mode: int = LB_WORD_WRAP) -> Tuple[float, float]:
    """Pythonista's ``ui.measure_string``: the size of ``text`` wrapped at ``max_width``
    (0: no wrapping), measured with PIL's metrics of the stand-in font."""
    f = _pil_font(font)
    lines = _wrap(text, f, max_width * SCALE if max_width else 0, line_break_mode)
    w = 0.0
    h = 0.0
    for ln in lines:
        bbox = f.getbbox(ln or " ")
        w = max(w, (bbox[2] - bbox[0]) / SCALE)
        h += _line_height(f) / SCALE
    return (w, h)


def _line_height(f) -> float:
    asc, desc = f.getmetrics()
    return float(asc + desc)


def _wrap(text: str, f, max_w_px: float, mode: int) -> List[str]:
    out: List[str] = []
    for para in str(text).split("\n"):
        if not max_w_px or mode in (LB_CLIP, LB_TRUNCATE_TAIL, LB_TRUNCATE_HEAD, LB_TRUNCATE_MIDDLE):
            if max_w_px and mode == LB_TRUNCATE_TAIL and f.getbbox(para)[2] > max_w_px:
                # cut only what does not fit, as UILabel does
                s = para
                while s and f.getbbox(s + "…")[2] > max_w_px and len(s) > 1:
                    s = s[:-1]
                out.append(s + "…")
            else:
                out.append(para)
            continue
        words = para.split(" ")
        line = ""
        for w in words:
            cand = (line + " " + w) if line else w
            if f.getbbox(cand)[2] <= max_w_px or not line:
                line = cand
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


# ----------------------------------------------------------------------------- drawing context
class _Ctx:
    def __init__(self, img, draw, ox: float, oy: float, clip: Tuple[float, float, float, float]):
        self.img = img
        self.draw = draw
        self.ox = ox
        self.oy = oy
        self.clip = clip
        self.color = (0, 0, 0, 255)
        self.ctm = Transform()      # the view's user space -> its own coordinates (concat_ctm)
        self.saved: List[tuple] = []  # GState: (transform, colour)


_ctx_stack: List[_Ctx] = []


def _ctx() -> _Ctx:
    if not _ctx_stack:
        raise RuntimeError("drawing outside of render()")
    return _ctx_stack[-1]


def _pt(x: float, y: float) -> Tuple[float, float]:
    c = _ctx()
    x, y = c.ctm.apply(x, y)
    return ((c.ox + x) * SCALE, (c.oy + y) * SCALE)


class Transform:
    """An affine transform like Pythonista's ui.Transform (CoreGraphics' convention: a point
    maps to (a*x + c*y + tx, b*x + d*y + ty); ``t1.concat(t2)`` applies t1, then t2)."""

    def __init__(self, a: float = 1.0, b: float = 0.0, c: float = 0.0, d: float = 1.0, tx: float = 0.0, ty: float = 0.0):
        self.a, self.b, self.c, self.d, self.tx, self.ty = a, b, c, d, tx, ty

    @staticmethod
    def rotation(rad: float) -> "Transform":
        import math
        co, si = math.cos(rad), math.sin(rad)
        return Transform(co, si, -si, co, 0.0, 0.0)

    @staticmethod
    def translation(tx: float, ty: float) -> "Transform":
        return Transform(1.0, 0.0, 0.0, 1.0, tx, ty)

    @staticmethod
    def scale(sx: float, sy: float) -> "Transform":
        return Transform(sx, 0.0, 0.0, sy, 0.0, 0.0)

    def concat(self, other: "Transform") -> "Transform":
        o = other
        return Transform(self.a * o.a + self.b * o.c, self.a * o.b + self.b * o.d,
                         self.c * o.a + self.d * o.c, self.c * o.b + self.d * o.d,
                         self.tx * o.a + self.ty * o.c + o.tx, self.tx * o.b + self.ty * o.d + o.ty)

    def apply(self, x: float, y: float) -> Tuple[float, float]:
        return (self.a * x + self.c * y + self.tx, self.b * x + self.d * y + self.ty)

    def is_translation(self) -> bool:
        return abs(self.a - 1) < 1e-9 and abs(self.d - 1) < 1e-9 and abs(self.b) < 1e-9 and abs(self.c) < 1e-9


def concat_ctm(t: Transform) -> None:
    """Like Pythonista: the new transform applies first, then the current one."""
    c = _ctx()
    c.ctm = t.concat(c.ctm)


def set_color(color: Any) -> None:
    _ctx().color = _rgba255(color)


def fill_rect(x: float, y: float, w: float, h: float) -> None:
    c = _ctx()
    x0, y0 = _pt(x, y)
    x1, y1 = _pt(x + w, y + h)
    _overlay_rect(c, (x0, y0, x1, y1), c.color)


def _overlay_rect(c: _Ctx, box, color, radius: float = 0, outline=None, width: int = 0):
    if color[3] == 0 and outline is None:
        return
    layer = PILImage.new("RGBA", c.img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if radius > 0:
        d.rounded_rectangle(box, radius=radius, fill=color if color[3] else None, outline=outline, width=width)
    else:
        d.rectangle(box, fill=color if color[3] else None, outline=outline, width=width)
    c.img.alpha_composite(layer)


class Path:
    def __init__(self) -> None:
        self.kind = "poly"
        self.points: List[Tuple[float, float]] = []
        self.box = None
        self.radius = 0.0
        self.line_width = 1.0

    @staticmethod
    def rect(x, y, w, h) -> "Path":
        p = Path(); p.kind = "rect"; p.box = (x, y, w, h); return p

    @staticmethod
    def rounded_rect(x, y, w, h, r) -> "Path":
        p = Path(); p.kind = "rrect"; p.box = (x, y, w, h); p.radius = r; return p

    @staticmethod
    def oval(x, y, w, h) -> "Path":
        p = Path(); p.kind = "oval"; p.box = (x, y, w, h); return p

    def move_to(self, x, y): self.points.append((x, y))
    def line_to(self, x, y): self.points.append((x, y))
    def close(self): pass

    def _pil_box(self):
        x, y, w, h = self.box
        pts = [_pt(x, y), _pt(x + w, y), _pt(x, y + h), _pt(x + w, y + h)]
        x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
        x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
        return (x0, y0, max(x0, x1 - 1), max(y0, y1 - 1))

    def fill(self) -> None:
        c = _ctx()
        if self.kind in ("rect", "rrect"):
            _overlay_rect(c, self._pil_box(), c.color, radius=self.radius * SCALE)
        elif self.kind == "oval":
            layer = PILImage.new("RGBA", c.img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).ellipse(self._pil_box(), fill=c.color)
            c.img.alpha_composite(layer)
        elif len(self.points) >= 3:
            layer = PILImage.new("RGBA", c.img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).polygon([_pt(*p) for p in self.points], fill=c.color)
            c.img.alpha_composite(layer)

    def stroke(self) -> None:
        c = _ctx()
        w = max(1, int(round(self.line_width * SCALE)))
        if self.kind in ("rect", "rrect"):
            _overlay_rect(c, self._pil_box(), (0, 0, 0, 0), radius=self.radius * SCALE, outline=c.color, width=w)
        elif self.kind == "oval":
            layer = PILImage.new("RGBA", c.img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).ellipse(self._pil_box(), outline=c.color, width=w)
            c.img.alpha_composite(layer)
        elif len(self.points) >= 2:
            layer = PILImage.new("RGBA", c.img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).line([_pt(*p) for p in self.points], fill=c.color, width=w)
            c.img.alpha_composite(layer)


def draw_string(text: str, rect=(0, 0, 0, 0), font=None, color="black", alignment=ALIGN_LEFT,
                line_break_mode=LB_WORD_WRAP) -> None:
    c = _ctx()
    if not c.ctm.is_translation():
        _draw_string_turned(c, text, rect, font, color, alignment, line_break_mode)
        return
    _draw_string_plain(c, text, rect, font, color, alignment, line_break_mode)


def _draw_string_turned(c, text, rect, font, color, alignment, line_break_mode) -> None:
    """The string drawn upright in its rect on a scratch image, which is turned by the
    current transform's angle and pasted where the rect's centre lands."""
    import math
    x, y, w, h = rect
    mw, mh = measure_string(text, 0, font)
    if not w or not h:
        w = w or mw
        h = h or mh
    # room for text wider or taller than its rect, which the phone draws past the rect too
    pad = 4 + int(math.ceil(max(0.0, mw - w, mh - h) * SCALE))
    W, H = int(math.ceil(w * SCALE)) + 2 * pad, int(math.ceil(h * SCALE)) + 2 * pad
    scratch = PILImage.new("RGBA", (W, H), (0, 0, 0, 0))
    sc = _Ctx(scratch, ImageDraw.Draw(scratch), pad / float(SCALE), pad / float(SCALE), (0, 0, w, h))
    _ctx_stack.append(sc)
    try:
        _draw_string_plain(sc, text, (0, 0, w, h), font, color, alignment, line_break_mode)
    finally:
        _ctx_stack.pop()
    angle = math.degrees(math.atan2(c.ctm.b, c.ctm.a))
    turned = scratch.rotate(-angle, resample=PILImage.BICUBIC, expand=True)
    cx, cy = _pt(x + w / 2.0, y + h / 2.0)
    layer = PILImage.new("RGBA", c.img.size, (0, 0, 0, 0))
    layer.paste(turned, (int(round(cx - turned.size[0] / 2.0)), int(round(cy - turned.size[1] / 2.0))), turned)
    c.img.alpha_composite(layer)


def _draw_string_plain(c, text, rect, font, color, alignment, line_break_mode) -> None:
    f = _pil_font(font)
    x, y, w, h = rect
    lines = _wrap(text, f, w * SCALE if w else 0, line_break_mode)
    lh = _line_height(f)
    layer = PILImage.new("RGBA", c.img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    col = _rgba255(color)
    cy = _pt(x, y)[1]
    for ln in lines:
        tw = f.getbbox(ln)[2] if ln else 0
        if alignment == ALIGN_CENTER and w:
            tx = _pt(x, y)[0] + (w * SCALE - tw) / 2.0
        elif alignment == ALIGN_RIGHT and w:
            tx = _pt(x, y)[0] + (w * SCALE - tw)
        else:
            tx = _pt(x, y)[0]
        d.text((tx, cy), ln, font=f, fill=col)
        cy += lh
    c.img.alpha_composite(layer)


class GState:
    """Saves the drawing state (the transform) and restores it on exit, like Pythonista."""

    def __enter__(self):
        c = _ctx()
        c.saved.append((c.ctm, c.color))
        return self

    def __exit__(self, *a):
        c = _ctx()
        if c.saved:
            c.ctm, c.color = c.saved.pop()
        else:
            c.ctm = Transform()
        return False


# ----------------------------------------------------------------------------- views
class Touch:
    def __init__(self, location, prev_location, phase, touch_id=1):
        self.location = location
        self.prev_location = prev_location
        self.phase = phase
        self.touch_id = touch_id
        self.timestamp = 0.0


class View:
    def __init__(self, *args, **kwargs) -> None:
        self.frame = kwargs.pop("frame", (0.0, 0.0, 100.0, 100.0))
        self.background_color: Any = kwargs.pop("background_color", None)
        self.name = kwargs.pop("name", "")
        self.flex = kwargs.pop("flex", "")
        defaults = dict(alpha=1.0, hidden=False, touch_enabled=True, multitouch_enabled=False,
                        corner_radius=0.0, border_width=0.0, border_color="black", tint_color=None,
                        _presented=False)
        for k, v in defaults.items():
            if k not in self.__dict__:
                setattr(self, k, v)
        self.subviews: List[View] = []
        self.superview: Optional[View] = None
        for k, v in kwargs.items():
            setattr(self, k, v)

    # geometry -------------------------------------------------------------
    @property
    def frame(self):
        return (self._x, self._y, self._w, self._h)

    @frame.setter
    def frame(self, value):
        self._x, self._y, self._w, self._h = (float(v) for v in value)
        self._relayout()

    @property
    def bounds(self):
        return (0.0, 0.0, self._w, self._h)

    @bounds.setter
    def bounds(self, value):
        self._w, self._h = float(value[2]), float(value[3])
        self._relayout()

    def _get_x(self): return self._x
    def _set_x(self, v): self._x = float(v)
    x = property(_get_x, _set_x)
    def _get_y(self): return self._y
    def _set_y(self, v): self._y = float(v)
    y = property(_get_y, _set_y)
    def _get_w(self): return self._w
    def _set_w(self, v): self._w = float(v); self._relayout()
    width = property(_get_w, _set_w)
    def _get_h(self): return self._h
    def _set_h(self, v): self._h = float(v); self._relayout()
    height = property(_get_h, _set_h)

    @property
    def center(self):
        return (self._x + self._w / 2, self._y + self._h / 2)

    @center.setter
    def center(self, c):
        self._x, self._y = c[0] - self._w / 2, c[1] - self._h / 2

    def _relayout(self):
        if hasattr(self, "layout") and callable(getattr(self, "layout")):
            _laying_out.append(self)
            try:
                self.layout()
            finally:
                _laying_out.remove(self)

    # hierarchy ------------------------------------------------------------
    def add_subview(self, v: "View") -> None:
        if v.superview is not None:
            v.superview.remove_subview(v)
        v.superview = self
        self.subviews.append(v)
        _mark(self)

    def remove_subview(self, v: "View") -> None:
        if v in self.subviews:
            self.subviews.remove(v)
            v.superview = None
            _mark(self)

    def remove_from_superview(self) -> None:
        if self.superview:
            self.superview.remove_subview(self)

    def bring_to_front(self) -> None:
        if self.superview:
            self.superview.subviews.remove(self)
            self.superview.subviews.append(self)

    def send_to_back(self) -> None:
        if self.superview:
            self.superview.subviews.remove(self)
            self.superview.subviews.insert(0, self)

    def __getitem__(self, name: str) -> "View":
        for v in self.subviews:
            if v.name == name:
                return v
            try:
                return v[name]
            except KeyError:
                pass
        raise KeyError(name)

    # presentation ---------------------------------------------------------
    def present(self, style="sheet", animated=True, hide_title_bar=False, title_bar_color=None,
                title_color=None, orientations=None, popover_location=None) -> None:
        if style == "fullscreen" or hide_title_bar:
            self.frame = (0, 0, _screen[0], _screen[1])
        self._presented = True
        _presented.append(self)
        if hasattr(self, "did_load"):
            pass

    def close(self) -> None:
        self._presented = False
        if self in _presented:
            _presented.remove(self)
        if hasattr(self, "will_close"):
            self.will_close()

    @property
    def on_screen(self) -> bool:
        return self._presented

    def wait_modal(self) -> None:
        pass

    def set_needs_display(self) -> None:
        pass

    # default drawing hook (subclasses override draw)
    def _draw_self(self, ctx_box) -> None:
        pass


class Label(View):
    def __init__(self, *args, **kwargs) -> None:
        self.text = kwargs.pop("text", "")
        self.text_color: Any = kwargs.pop("text_color", "black")
        self.font = kwargs.pop("font", ("<system>", 17))
        self.alignment = kwargs.pop("alignment", ALIGN_LEFT)
        self.number_of_lines = kwargs.pop("number_of_lines", 1)
        self.line_break_mode = kwargs.pop("line_break_mode", LB_TRUNCATE_TAIL)
        super().__init__(*args, **kwargs)
        self.touch_enabled = False

    def size_to_fit(self) -> None:
        w, h = measure_string(self.text, 0, self.font)
        self._w, self._h = w + 4, h + 2


class Button(View):
    def __init__(self, *args, **kwargs) -> None:
        self.title = kwargs.pop("title", "")
        self.action: Optional[Callable] = kwargs.pop("action", None)
        self.font = kwargs.pop("font", ("<system>", 15))
        self.tint_color = kwargs.pop("tint_color", "#007aff")
        self.enabled = kwargs.pop("enabled", True)
        self.image = kwargs.pop("image", None)
        super().__init__(*args, **kwargs)

    def _tap(self) -> None:
        if self.enabled and self.action:
            self.action(self)


class ImageView(View):
    def __init__(self, *args, **kwargs) -> None:
        self.image = kwargs.pop("image", None)
        super().__init__(*args, **kwargs)
        self.touch_enabled = False


class ScrollView(View):
    def __init__(self, *args, **kwargs) -> None:
        self.content_size = kwargs.pop("content_size", (0.0, 0.0))
        self.content_offset = kwargs.pop("content_offset", (0.0, 0.0))
        self.shows_horizontal_scroll_indicator = True
        self.shows_vertical_scroll_indicator = True
        self.paging_enabled = False
        self.bounces = True
        self.scroll_enabled = True
        self.always_bounce_vertical = False
        self.always_bounce_horizontal = False
        self.delegate = None
        super().__init__(*args, **kwargs)


class Switch(View):
    def __init__(self, *args, **kwargs) -> None:
        self.value = kwargs.pop("value", False)
        self.action = kwargs.pop("action", None)
        super().__init__(*args, **kwargs)


class SegmentedControl(View):
    def __init__(self, *args, **kwargs) -> None:
        self.segments = list(kwargs.pop("segments", []))
        self.selected_index = kwargs.pop("selected_index", 0)
        self.action = kwargs.pop("action", None)
        super().__init__(*args, **kwargs)


class TextField(View):
    def __init__(self, *args, **kwargs) -> None:
        self.text = kwargs.pop("text", "")
        self.placeholder = kwargs.pop("placeholder", "")
        self.font = kwargs.pop("font", ("<system>", 17))
        self.action = kwargs.pop("action", None)
        self.delegate = None
        super().__init__(*args, **kwargs)

    def begin_editing(self): pass
    def end_editing(self): pass


class Image:  # icons: unused in rendering
    @staticmethod
    def named(name: str) -> "Image":
        return Image()

    def draw(self, x=0, y=0, w=0, h=0): pass


def animate(fn: Callable, duration: float = 0.25, delay: float = 0.0, completion: Optional[Callable] = None) -> None:
    fn()
    if completion:
        completion()


_delayed: List[Tuple[float, Callable]] = []


def delay(fn: Callable, seconds: float) -> None:
    _delayed.append((seconds, fn))


def run_delays() -> int:
    """Test helper: run every pending ``ui.delay`` callback now."""
    n = 0
    while _delayed:
        _, fn = _delayed.pop(0)
        fn()
        n += 1
    return n


def cancel_delays() -> None:
    del _delayed[:]


def in_background(fn: Callable) -> Callable:
    return fn


def load_view(path: str, bindings=None):  # pragma: no cover
    raise NotImplementedError


# ----------------------------------------------------------------------------- rendering
def render(view: View, path: Optional[str] = None):
    """Paint ``view`` (and subviews) to an RGBA image; save it when ``path`` is given."""
    if PILImage is None:  # pragma: no cover
        raise RuntimeError("Pillow is required to render")
    w, h = int(round(view.width * SCALE)), int(round(view.height * SCALE))
    img = PILImage.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    _ctx_stack.append(_Ctx(img, draw, 0.0, 0.0, (0, 0, view.width, view.height)))
    try:
        _render_view(view, 0.0, 0.0)
    finally:
        _ctx_stack.pop()
    if path:
        img.convert("RGB").save(path)
    return img


def _render_view(v: View, ox: float, oy: float) -> None:
    if v.hidden or v.alpha <= 0:
        return
    c = _ctx()
    x0, y0 = ox + v.x, oy + v.y
    box = ((x0) * SCALE, (y0) * SCALE, (x0 + v.width) * SCALE - 1, (y0 + v.height) * SCALE - 1)
    bg = _rgba255(v.background_color) if v.background_color is not None else (0, 0, 0, 0)
    if v.alpha < 1:
        bg = (bg[0], bg[1], bg[2], int(bg[3] * v.alpha))
    outline = _rgba255(v.border_color) if v.border_width > 0 else None
    _overlay_rect(c, box, bg, radius=v.corner_radius * SCALE, outline=outline,
                  width=int(round(v.border_width * SCALE)) if outline else 0)
    _ctx_stack.append(_Ctx(c.img, c.draw, x0, y0, (x0, y0, v.width, v.height)))
    try:
        if isinstance(v, Label):
            shown = "\n".join(label_lines(v))
            tw, th = measure_string(shown, 0, v.font)
            ty = max(0.0, (v.height - th) / 2.0)
            draw_string(shown, (0, ty, v.width, v.height), v.font, v.text_color, v.alignment, LB_CLIP)
        elif isinstance(v, Button):
            tw, th = measure_string(v.title, 0, v.font)
            col = v.tint_color if v.enabled else "#9a9a9a"
            draw_string(v.title, (0, max(0.0, (v.height - th) / 2.0), v.width, v.height), v.font, col, ALIGN_CENTER)
        elif isinstance(v, Switch):
            col = "#34c759" if v.value else "#c8c8cc"
            _overlay_rect(c, (box[0], box[1], box[0] + 51 * SCALE, box[1] + 31 * SCALE), _rgba255(col), radius=15 * SCALE)
            kx = box[0] + (22 if v.value else 2) * SCALE
            _overlay_rect(c, (kx, box[1] + 2 * SCALE, kx + 27 * SCALE, box[1] + 29 * SCALE), (255, 255, 255, 255), radius=13 * SCALE)
        elif isinstance(v, SegmentedControl):
            n = max(1, len(v.segments))
            sw = v.width / n
            for i, seg in enumerate(v.segments):
                col = (0, 122, 255, 255) if i == v.selected_index else (0, 0, 0, 0)
                _overlay_rect(c, ((x0 + i * sw) * SCALE, y0 * SCALE, (x0 + (i + 1) * sw) * SCALE - 1, (y0 + v.height) * SCALE - 1),
                              col, radius=6 * SCALE, outline=(0, 122, 255, 255), width=SCALE)
                draw_string(seg, (i * sw, (v.height - 20) / 2, sw, 20), ("<system>", 14),
                            "white" if i == v.selected_index else "#007aff", ALIGN_CENTER)
        elif isinstance(v, TextField):
            _overlay_rect(c, box, (255, 255, 255, 255), radius=5 * SCALE, outline=(180, 180, 180, 255), width=SCALE)
            draw_string(v.text or v.placeholder, (8, (v.height - 20) / 2, v.width - 16, 20), v.font,
                        "black" if v.text else "#999999")
        if hasattr(v, "draw") and callable(getattr(v, "draw")):
            v.draw()
        sub_ox, sub_oy = x0, y0
        if isinstance(v, ScrollView):
            sub_ox -= v.content_offset[0]
            sub_oy -= v.content_offset[1]
            # its content is drawn on a layer and only the visible rect is kept, as on the phone
            layer = PILImage.new("RGBA", c.img.size, (0, 0, 0, 0))
            _ctx_stack.append(_Ctx(layer, ImageDraw.Draw(layer), x0, y0, (x0, y0, v.width, v.height)))
            try:
                for s in list(v.subviews):
                    sx, sy = s.x - v.content_offset[0], s.y - v.content_offset[1]
                    if sx + s.width < 0 or sy + s.height < 0 or sx > v.width or sy > v.height:
                        continue
                    _render_view(s, sub_ox, sub_oy)
            finally:
                _ctx_stack.pop()
            left, top = max(0, int(round(x0 * SCALE))), max(0, int(round(y0 * SCALE)))
            right = min(c.img.size[0], int(round((x0 + v.width) * SCALE)))
            bottom = min(c.img.size[1], int(round((y0 + v.height) * SCALE)))
            if right > left and bottom > top:
                c.img.alpha_composite(layer.crop((left, top, right, bottom)), dest=(left, top))
            return
        for s in list(v.subviews):
            _render_view(s, sub_ox, sub_oy)
    finally:
        _ctx_stack.pop()


def label_lines(label: "Label") -> List[str]:
    """The lines a UILabel would show: wrapped at its width, at most ``number_of_lines``
    lines (0: as many as fit in its height), the last one truncated with an ellipsis when
    text is left over (UILabel's default tail truncation)."""
    f = _pil_font(label.font)
    if label.number_of_lines == 1:
        return _wrap(label.text, f, label.width * SCALE, LB_TRUNCATE_TAIL)
    lines = _wrap(label.text, f, label.width * SCALE, LB_WORD_WRAP)
    room = int(label.height * SCALE // max(1.0, _line_height(f)))
    limit = label.number_of_lines if label.number_of_lines > 0 else max(1, room)
    limit = min(limit, max(1, room))
    if len(lines) <= limit:
        return lines
    kept = lines[:limit]
    last = kept[-1]
    while last and f.getbbox(last + "…")[2] > label.width * SCALE:
        last = last[:-1]
    kept[-1] = last + "…"
    return kept


def label_truncated(label: "Label") -> bool:
    """Would the label cut its text short (tests: nothing the player must read is lost)?"""
    shown = label_lines(label)
    return bool(shown) and shown[-1].endswith("…") and not str(label.text).endswith("…")


# ----------------------------------------------------------------------------- touches
def hit_test(view: View, x: float, y: float) -> Optional[View]:
    """Deepest visible touch-enabled view containing the point (view-local coords)."""
    if view.hidden or not (0 <= x <= view.width and 0 <= y <= view.height):
        return None
    for s in reversed(view.subviews):
        off = (0.0, 0.0)
        if isinstance(view, ScrollView):
            off = view.content_offset
        hit = hit_test(s, x - s.x + off[0], y - s.y + off[1])
        if hit is not None:
            return hit
    if not view.touch_enabled:
        return None
    return view


def _local(view: View, target: View, x: float, y: float) -> Tuple[float, float]:
    chain = []
    v = target
    while v is not None and v is not view:
        chain.append(v)
        v = v.superview
    lx, ly = x, y
    for v in reversed(chain):
        lx -= v.x
        ly -= v.y
        if isinstance(v.superview, ScrollView):
            lx += v.superview.content_offset[0]
            ly += v.superview.content_offset[1]
    return (lx, ly)


def tap(view: View, x: float, y: float) -> Optional[View]:
    """Deliver a tap at root coordinates, like Pythonista: Buttons fire ``action``,
    custom views get touch_began/touch_ended with local coordinates. With deferred
    layout on, the marked views are laid out afterwards, as the run loop does."""
    target = _deliver(view, x, y)
    if _deferred[0]:
        root = view
        while root.superview is not None:
            root = root.superview
        flush(root)
    return target


def _deliver(view: View, x: float, y: float) -> Optional[View]:
    target = hit_test(view, x, y)
    if target is None:
        return None
    if isinstance(target, Button):
        target._tap()
        return target
    lx, ly = _local(view, target, x, y)
    t = Touch((lx, ly), (lx, ly), "began")
    if hasattr(target, "touch_began"):
        target.touch_began(t)
    t2 = Touch((lx, ly), (lx, ly), "ended")
    if hasattr(target, "touch_ended"):
        target.touch_ended(t2)
    return target


def find(view: View, predicate: Callable[[View], bool]) -> List[View]:
    out = []
    if predicate(view):
        out.append(view)
    for s in view.subviews:
        out.extend(find(s, predicate))
    return out


def button(view: View, title: str) -> Button:
    """Find a visible, enabled button by title (test helper)."""
    for b in find(view, lambda v: isinstance(v, Button) and v.title == title and not v.hidden):
        return b
    raise KeyError("no button titled %r" % title)


def root_point(view: View, target: View) -> Tuple[float, float]:
    """Root coordinates of a view's centre (test helper for tap())."""
    x, y = target.width / 2, target.height / 2
    v = target
    while v is not None and v is not view:
        x += v.x
        y += v.y
        if isinstance(v.superview, ScrollView):
            x -= v.superview.content_offset[0]
            y -= v.superview.content_offset[1]
        v = v.superview
    return (x, y)
