"""Pythonista entry point. Run this file in Pythonista (or `python app/main.py`
on a desktop with tools/fakeui for a headless check)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import ui  # noqa: F401  (real Pythonista)
except ImportError:  # desktop: use the headless stand-in
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import fakeui
    fakeui.install()


def run() -> None:
    from app.screens import App, MenuScreen
    app = App()
    app.show(MenuScreen(app))
    app.present("fullscreen", hide_title_bar=True, orientations=["portrait"])
    return app


if __name__ == "__main__":
    run()
