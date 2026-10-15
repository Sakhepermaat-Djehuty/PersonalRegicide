"""Colours, fonts and metrics shared by the screens."""
from __future__ import annotations

BG = "#171a21"
PANEL = "#242938"
PANEL_2 = "#2e3447"
TEXT = "#f3f4f6"
MUTED = "#9aa3b5"
ACCENT = "#e3b84f"        # gold: selection, highlights
DANGER = "#e0605a"
OK = "#6ccf7a"
BTN = "#3a62c7"
BTN_TEXT = "#ffffff"
BTN_DISABLED = "#3a4053"
CARD_FACE = "#f8f4ea"
CARD_FACE_DIM = "#cfcabd"
CORRUPTED = "#9440c8"     # the corrupted sleeve (purple)
RESTORED = "#21b05f"      # the restored sleeve (green)
EVERGREEN = "#1f9e55"     # the Evergreen tree (Gøran and Esme): the four basic classes
CARD_BACK = "#4b3d8a"
CARD_INK = "#262626"        # text printed on a card face (the card pop-ups)
CARD_INK_MUTED = "#6b6458"
SHADE = (0.09, 0.10, 0.13, 0.25)   # over a card that is not available yet (a mercenary in the box)
COIN = "#f5c542"
COIN_RIM = "#a87410"
CARD_BORDER = "#1e1e1e"
JESTER_COLOR = "#8e44ad"
SUIT_COLOR = {"H": "#d6453f", "D": "#d9842b", "C": "#2f8f47", "S": "#2f5fb3",
              "M": "#7b3fbf", "R": "#b3372f", "G": "#2f7f8f", "U": "#5f8f2f", "T": "#b37f2f"}

FONT = "<system>"
FONT_BOLD = "<system-bold>"

TOP_INSET = 48      # below the notch when presented fullscreen with no title bar
BOTTOM_INSET = 28   # above the home indicator
MARGIN = 14


def apply_safe_area(view) -> None:
    """Pythonista's ui has no safe-area API; read UIKit's insets through objc_util when
    available and update TOP_INSET / BOTTOM_INSET. Falls back to the constants above."""
    global TOP_INSET, BOTTOM_INSET
    try:
        ins = view.objc_instance.safeAreaInsets()
        top, bottom = float(ins.top), float(ins.bottom)
    except Exception:
        return
    if top > 0:
        TOP_INSET = max(24.0, top + 4.0)
    if bottom >= 0:
        BOTTOM_INSET = max(16.0, bottom + 8.0)
