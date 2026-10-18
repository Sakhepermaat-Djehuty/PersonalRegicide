"""Settings, Info Pop Ups [✓] ›: the master box, the list behind ›, its collapsible groups
and each pop-up's own box (the owner's design)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402

from app import info  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("REGICIDE_SAVE_DIR", str(tmp_path))
    from app.screens import App, SettingsScreen
    ui.set_screen_size(390, 844)
    a = App()
    a.show(SettingsScreen(a))
    return a


def _boxes(app):
    from app.widgets import TickBox
    return ui.find(app, lambda v: isinstance(v, TickBox))


def _labels(app):
    return [v.text for v in ui.find(app, lambda v: isinstance(v, ui.Label))]


def _tap(app, view):
    ui.tap(app, *ui.root_point(app, view))


def _scroll_to(app, view):
    sv = [v for v in ui.find(app, lambda v: isinstance(v, ui.ScrollView))][0]
    sv.content_offset = (0, max(0.0, min(view.y - 100, sv.content_size[1] - sv.height)))


def test_the_master_box_and_the_list_behind_it(app):
    from app import store
    app.settings["info_popups"] = True
    app.current.layout()
    assert "Info Pop Ups" in _labels(app) and "Turn" not in _labels(app)       # the list starts closed
    master = _boxes(app)[0]
    assert master.value and len(_boxes(app)) == 1
    chevron = ui.button(app, "›")
    _scroll_to(app, chevron)
    _tap(app, chevron)
    labels = _labels(app)
    assert all(g in labels for g in info.GROUPS)                               # every group, collapsed
    assert "Cleric" not in labels and len(_boxes(app)) == 1
    head = [b for b in ui.find(app, lambda v: isinstance(v, ui.Button) and v.title == "")][info.GROUPS.index("Classes")]
    _scroll_to(app, head)
    _tap(app, head)
    labels = _labels(app)
    rows = [r for r in info.ROWS if r[1] == "Classes"]
    assert all(r[2] in labels for r in rows) and len(_boxes(app)) == 1 + len(rows)
    assert "%d of %d  ⌄" % (len(rows), len(rows)) in labels
    # a row's box switches that pop-up off, and back on
    cleric = _boxes(app)[1 + [r[0] for r in rows].index("cleric")]
    _scroll_to(app, cleric)
    _tap(app, cleric)
    assert app.settings["info_popups_off"] == ["cleric"] and store.load_settings()["info_popups_off"] == ["cleric"]
    assert not info.row_on(app.settings, "cleric") and info.row_on(app.settings, "bard")
    assert "%d of %d  ⌄" % (len(rows) - 1, len(rows)) in _labels(app)
    # the master box: no pop-ups; the rows keep their choices but cannot be pressed
    master = _boxes(app)[0]
    _scroll_to(app, master)
    _tap(app, master)
    assert app.settings["info_popups"] is False and not info.row_on(app.settings, "bard")
    assert app.settings["info_popups_off"] == ["cleric"]
    boxes = _boxes(app)
    assert not any(b.enabled for b in boxes[1:])
    before = list(app.settings["info_popups_off"])
    _scroll_to(app, boxes[2])
    _tap(app, _boxes(app)[2])
    assert app.settings["info_popups_off"] == before                           # a dimmed box does nothing
    _scroll_to(app, _boxes(app)[0])
    _tap(app, _boxes(app)[0])
    assert app.settings["info_popups"] is True and info.row_on(app.settings, "bard")
    assert ui.render(app).size[0] > 0
