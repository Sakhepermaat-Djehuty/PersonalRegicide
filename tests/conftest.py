import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_info_popups_unless_asked(monkeypatch):
    """The info pop-ups cover the screen after each action: the suite plays without them
    (its taps would land on the queue) unless a test switches them on in its settings
    (``app.settings["info_popups"] = True``)."""
    try:
        from app import info
    except Exception:          # the engine's own tests need no app
        return
    monkeypatch.setattr(info, "DEFAULT_ON", False)
