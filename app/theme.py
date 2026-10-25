"""Colours, fonts and metrics shared by the screens."""
from __future__ import annotations

# The Veil look (after Veilwraith): black and greys only. Colour is what this world has
# lost, so nothing here has a hue; what matters is told by brightness (the brighter, the
# more it matters), by shape (the suits) and by marks (a cracked sleeve, a torn edge).
BG = "#060606"
PANEL = "#121212"
PANEL_2 = "#1c1c1c"
PANEL_VEIL = (0.03, 0.03, 0.03, 0.62)   # laid over the fog inside a panel: it shows faintly
TEXT = "#e2dfd9"          # bone: the text on black
BRIGHT = "#ffffff"        # the brightest mark: a selection, a number that matters now
MUTED = "#8a8885"
FAINT = "#4c4b49"         # what can't be used now
ACCENT = "#ffffff"        # selection, highlights (white, as the gold was)
DANGER = "#ffffff"        # a warning stands out by brightness (and its torn edge), not by red
OK = "#b9b6b0"
BTN = "#0b0b0b"           # a button: a black tile...
BTN_EDGE = "#353533"      # ...with a dark edge...
FRAME = "#d9d5ce"         # ...and the pale frame inside it (Veilwraith's number tiles)
FRAME_QUIET = "#4e4d4a"   # the frame of a quieter button, and of a panel
FRAME_OFF = "#262625"
BTN_TEXT = "#f1eee8"
BTN_DISABLED = "#0b0b0b"
SWITCH_ON = "#8f8c86"     # an on switch, a chosen segment
RIM = "#9d9a94"           # the lit edge along a tear
SCAR = (1.0, 1.0, 1.0, 0.07)   # the faint scratches scored into a card or a panel
CARD_FACE = "#0e0e0e"     # a black card...
CARD_FACE_DIM = "#0e0e0e"
CARD_RIM = "#4a4946"      # ...its edge...
CARD_FRAME = "#2c2b29"    # ...and the faint frame inside it
CARD_VEIL = (0.28, 0.28, 0.28, 0.55)   # the grey veil over a card that can't be played
TORN_PANEL = (0.07, 0.07, 0.07, 0.92)  # a text panel with a torn top edge
CORRUPTED = "#2e2d2b"     # the corrupted sleeve: dark and cracked
CORRUPTED_CRACK = "#d0ccc5"
RESTORED = "#e9e6e0"      # the restored sleeve: pale and whole
EVERGREEN = "#e9e6e0"     # the Evergreen tree (Gøran and Esme): the four basic classes
CARD_BACK = "#000000"
CARD_INK = "#e2dfd9"      # text printed on a card face (the card pop-ups)
CARD_INK_MUTED = "#8f8c87"
SHADE = (0.18, 0.18, 0.18, 0.62)   # over a card that is not available yet (a mercenary in the box)
COIN = "#cfccc6"          # tarnished silver
COIN_RIM = "#4f4e4b"
CARD_BORDER = "#4a4946"
JESTER_COLOR = "#ffffff"
SUIT_COLOR = {"H": TEXT, "D": TEXT, "C": TEXT, "S": TEXT,
              "M": TEXT, "R": TEXT, "G": TEXT, "U": TEXT, "T": TEXT}

# Iowan Old Style: a book serif with a calligraphic warmth, the nearest to the card
# titles' type among the phone's fonts.
FONT = "IowanOldStyle-Roman"
FONT_BOLD = "IowanOldStyle-Bold"
FONT_ITALIC = "IowanOldStyle-Italic"

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
