"""The info pop-ups' core: every builder module loads, the rows are unique and grouped,
a switched-off row leaves nothing, stamped cards follow the IMMUNITY row, and the queue
on screen moves on with a tap and skips the rest with a long press."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import fakeui  # noqa: E402

fakeui.install()
import ui  # noqa: E402

from app import info  # noqa: E402


def test_every_builder_module_loads():
    assert info.LOAD_ERRORS == {}, "\n".join(info.LOAD_ERRORS.values())


def test_rows_are_unique_and_every_group_is_listed():
    ids = [r[0] for r in info.ROWS]
    assert len(ids) == len(set(ids))
    assert info.GROUPS[0] == "Turn" and set(r[1] for r in info.ROWS) == set(info.GROUPS)
    # the owner's ruling: one card before a Mage, Druid, Chanter or Reaver box, no result card
    assert not set(ids) & {"mage_pick", "druid_result", "chanter_result", "reaver_result"}


def test_a_row_switched_off_leaves_nothing_and_stamped_cards_follow_immunity():
    ctx = info.Ctx(None, [], {"info_popups": True, "info_popups_off": ["cleric"]})
    ctx.line("waiting")
    assert not ctx.add(info.InfoCard("cleric", "Cleric")) and ctx.cards == []
    assert ctx.pending == ["waiting"]                       # the line waits for a card that shows
    assert ctx.add(info.InfoCard("cleric", "Cleric", immune=True))       # IMMUNITY's row decides
    assert ctx.cards[0].lines == ["waiting"] and ctx.cards[0].sounds[0] == "info_immunity"
    off = info.Ctx(None, [], {"info_popups": True, "info_popups_off": ["immunity"]})
    assert not off.add(info.InfoCard("bard", "Bard", immune=True))
    assert info.build(None, [], {"info_popups": False}) == []


def test_the_queue_moves_on_with_a_tap_and_a_long_press_skips_the_rest():
    from app.info_view import InfoQueue
    played, stopped, effects, done = [], [], [], []
    cards = [info.InfoCard("cleric", "Cleric", 7, lines=["Heal 7"]), info.InfoCard("damage", "Damage", middle="7"),
             info.InfoCard("turn", "Your turn")]
    root = ui.View(frame=(0, 0, 390, 844))
    q = InfoQueue(cards, {}, play=lambda s: played.append(s[0]) or s[0], stop=stopped.append,
                  effect=effects.append, done=lambda: done.append(1), frame=(0, 0, 390, 844))
    root.add_subview(q)
    q.layout()
    assert q.face.title == "Cleric" and played == ["info_cleric"] and q.note.text.startswith("1 of 3")
    ui.cancel_delays()
    ui.tap(root, 195, 422)
    ui.run_delays()                                          # a tap is not a hold
    assert q.face.title == "Damage" and played[-1] == "info_damage" and stopped == ["info_cleric"]
    q.touch_began(ui.Touch((10, 10), (10, 10), "began"))     # held: the rest is skipped
    ui.run_delays()
    assert q.closed and q.superview is None and done == [1] and effects == ["card_down"]
    q.touch_ended(ui.Touch((10, 10), (10, 10), "ended"))
    assert done == [1]
    assert ui.render(InfoQueue(cards, {}, frame=(0, 0, 320, 568))).size[0] > 0
