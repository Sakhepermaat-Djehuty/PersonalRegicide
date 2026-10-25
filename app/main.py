"""Pythonista entry point. Run this file in Pythonista (or `python app/main.py`
on a desktop with tools/fakeui for a headless check)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT in sys.path:
    sys.path.remove(ROOT)
sys.path.insert(0, ROOT)
# Pythonista keeps modules loaded between runs: another copy of the app run earlier (the
# usual install beside a test copy) may have left its own. Drop those, so this copy's code
# is the code that runs.
for _name, _mod in list(sys.modules.items()):
    if _name.split(".")[0] in ("app", "regicide", "fakeui"):
        _file = os.path.abspath(getattr(_mod, "__file__", None) or "")
        if not _file.startswith(ROOT + os.sep):
            del sys.modules[_name]

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
    force_dark(app)
    return app


def force_dark(view) -> None:
    """The look is black: ask iOS for its dark appearance on this view and its window, so
    the keyboard and the phone's own controls stay dark whatever the phone is set to."""
    try:
        obj = view.objc_instance
        obj.setOverrideUserInterfaceStyle_(2)
        win = obj.window()
        if win is not None:
            win.setOverrideUserInterfaceStyle_(2)
    except Exception:
        pass


if __name__ == "__main__":
    run()
