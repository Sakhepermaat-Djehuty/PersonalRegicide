"""Headless stand-in for Pythonista's ``ui`` (plus ``console`` and ``dialogs``).

Only the subset the app uses is implemented. Views keep the same attributes and
callbacks as on the phone; ``render(view, path)`` paints the hierarchy to a PNG with
Pillow and ``tap(view, x, y)`` delivers a touch the way Pythonista would, so screens
and flows can be exercised on Linux. Install with ``install()`` before importing the
app modules; on a real Pythonista the real ``ui`` is used and this package is unused.

Layout follows the phone: adding or removing a subview marks the receiving view, whose
``layout()`` runs later, after the tap (``ui.flush``); see ``ui.set_deferred_layout``.
"""
from __future__ import annotations

import sys


def install() -> None:
    """Register this package's modules as ``ui``, ``console``, ``dialogs`` and ``sound``."""
    from . import ui as fake_ui
    from . import console as fake_console
    from . import dialogs as fake_dialogs
    from . import sound as fake_sound
    sys.modules.setdefault("ui", fake_ui)
    sys.modules.setdefault("console", fake_console)
    sys.modules.setdefault("dialogs", fake_dialogs)
    sys.modules.setdefault("sound", fake_sound)
