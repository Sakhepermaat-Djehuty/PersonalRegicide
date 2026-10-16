"""The headless ui lays views out as the phone does: adding or removing a subview marks the
receiving view and the run loop (``flush``, run after every ``tap``) calls its layout()
later; a view's own changes during its layout() do not mark it again; a layout that never
settles is an error. A card pop-up added to a screen that rebuilds itself in layout() was
removed this way on the phone before it was ever drawn."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402


@pytest.fixture(autouse=True)
def deferred():
    ui.set_deferred_layout(True)
    yield
    ui.set_deferred_layout(True)


class Rebuilding(ui.View):
    """Like the app's screens: layout() removes every subview and builds them again."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.runs = 0

    def layout(self):
        if not hasattr(self, "runs"):
            return                                     # (the frame set in View.__init__)
        self.runs += 1
        for v in list(self.subviews):
            self.remove_subview(v)
        self.add_subview(ui.Button(frame=(10, 10, 80, 40)))


def _root():
    root = ui.View(frame=(0, 0, 390, 844))
    screen = Rebuilding(frame=(0, 0, 390, 844))
    root.add_subview(screen)
    ui.flush(root)
    return root, screen


def test_a_view_added_from_outside_is_gone_after_the_rebuilding_screens_layout():
    root, screen = _root()
    popup = ui.View(frame=(0, 0, 390, 844))
    screen.add_subview(popup)
    assert popup.superview is screen                   # until the run loop comes round
    runs = screen.runs
    ui.flush(root)
    assert screen.runs == runs + 1 and popup.superview is None


def test_a_view_on_the_root_survives_and_a_layout_does_not_mark_its_own_view():
    root, screen = _root()
    popup = ui.View(frame=(0, 0, 390, 844))
    root.add_subview(popup)
    runs = screen.runs
    assert ui.flush(root) == 0                         # the root has no layout of its own here
    assert popup.superview is root and screen.runs == runs
    screen.layout()                                    # called from outside: marks it
    assert ui.flush(root) == 1 and ui.flush(root) == 0


def test_a_tap_ends_with_the_run_loop():
    root, screen = _root()
    hit = []

    class Opener(ui.View):
        def touch_ended(self, touch):
            hit.append(1)
            screen.add_subview(ui.View(frame=(0, 0, 50, 50)))
    o = Opener(frame=(100, 100, 50, 50))
    root.add_subview(o)
    ui.flush(root)
    runs = screen.runs
    o2 = Opener(frame=(0, 300, 50, 50))
    screen.add_subview(o2)                             # (marks the screen too)
    ui.flush(root)
    ui.tap(root, 125, 125)
    assert hit == [1] and screen.runs == runs + 2 and len(screen.subviews) == 1


def test_a_layout_that_never_settles_is_an_error():
    root = ui.View(frame=(0, 0, 390, 844))

    class Feeding(ui.View):
        """Each one's layout adds a view to the other, marking it: they never settle."""
        other = None

        def layout(self):
            if self.other is not None:
                self.other.add_subview(ui.View())
    a, b = Feeding(frame=(0, 0, 10, 10)), Feeding(frame=(0, 20, 10, 10))
    a.other, b.other = b, a
    root.add_subview(a)
    root.add_subview(b)
    a.add_subview(ui.View())                            # sets it going
    with pytest.raises(RuntimeError):
        ui.flush(root)


def test_off_it_lays_out_only_on_a_size_change():
    ui.set_deferred_layout(False)
    root, screen = _root()
    popup = ui.View(frame=(0, 0, 390, 844))
    screen.add_subview(popup)
    ui.flush(root)
    assert popup.superview is screen
