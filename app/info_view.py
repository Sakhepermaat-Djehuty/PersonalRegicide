"""The info pop-ups' queue on screen: one landscape card at a time over the whole app.

A tap anywhere moves on to the next card; a long press skips the rest. Each card's clip
starts as it appears and stops when it is moved on from; the last dismissal lays the
card down (``card_down``). The view sits on the app's root, above the screen, so a
decision box, a handover or a result screen shown underneath waits until it is done.
"""
from __future__ import annotations

from typing import Callable, List, Optional, Sequence

import ui

from . import theme as T
from .info import InfoCard
from .widgets import InfoCardFace, make_label


class InfoQueue(ui.View):
    HOLD = 0.6        # seconds a press must last to skip the rest

    def __init__(self, cards: Sequence[InfoCard], settings: dict, play: Optional[Callable] = None,
                 stop: Optional[Callable] = None, effect: Optional[Callable[[str], None]] = None,
                 done: Optional[Callable[[], None]] = None, **kw) -> None:
        super().__init__(**kw)
        self.cards: List[InfoCard] = list(cards)
        self.settings = settings
        self.play = play            # (sounds) -> a handle for ``stop``
        self.stop = stop
        self.effect = effect        # a short sound by name (the last card laid down)
        self.done = done
        self.k = 0
        self.face: Optional[InfoCardFace] = None
        self.handle = None
        self.down = False           # a touch began on the queue (the tap that opened it never counts)
        self.skipped = False
        self._token = 0
        self.closed = False
        self.background_color = (0, 0, 0, 0.55)
        self.note = make_label("", (0, 0, 10, 20), 12, False, T.MUTED, ui.ALIGN_CENTER)
        self.add_subview(self.note)
        self.shown_for: Optional[tuple] = None

    # ------------------------------------------------------------------ cards
    def extend(self, cards: Sequence[InfoCard]) -> None:
        """More cards from a later action join the end of the queue."""
        self.cards.extend(cards)
        self._note()

    def card_frame(self) -> tuple:
        w = min(360.0, self.width - 2 * T.MARGIN)
        h = round(w * InfoCardFace.RATIO)
        return ((self.width - w) / 2.0, max(T.TOP_INSET, (self.height - h) / 2.0 - 16), w, h)

    def layout(self) -> None:
        if not hasattr(self, "cards"):
            return
        size = (float(self.width), float(self.height))
        if self.face is None:
            self.show(self.k)
        elif self.shown_for != size:
            self.face.frame = self.card_frame()
            self.shown_for = size
        x, y, w, h = self.card_frame()
        self.note.frame = (x, y + h + 8, w, 20)

    def show(self, k: int) -> None:
        if not 0 <= k < len(self.cards):
            return
        self.k = k
        card = self.cards[k]
        if self.face is not None:
            self.remove_subview(self.face)
        face = InfoCardFace(frame=self.card_frame(), **card.face_args(self.settings))
        face.touch_enabled = False             # a tap anywhere moves on
        self.add_subview(face)
        self.face = face
        self.shown_for = (float(self.width), float(self.height))
        self._note()
        self._stop_clip()
        if self.play is not None:
            self.handle = self.play(card.sounds)

    def _note(self) -> None:
        n = len(self.cards)
        hint = "tap to go on · hold to skip" if n > 1 else "tap to go on"
        self.note.text = ("%d of %d · %s" % (self.k + 1, n, hint)) if n > 1 else hint

    def _stop_clip(self) -> None:
        if self.handle is not None and self.stop is not None:
            self.stop(self.handle)
        self.handle = None

    def advance(self) -> None:
        if self.k + 1 < len(self.cards):
            self.show(self.k + 1)
        else:
            self.close()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self._stop_clip()
        if self.effect is not None:
            self.effect("card_down")
        if self.superview is not None:
            self.superview.remove_subview(self)
        if self.done is not None:
            self.done()

    # ------------------------------------------------------------------ touches
    def touch_began(self, touch) -> None:
        self.down = True
        self.skipped = False
        self._token += 1
        tok = self._token
        ui.delay(lambda: self._held(tok), self.HOLD)

    def _held(self, tok: int) -> None:
        if self.down and tok == self._token and not self.closed:
            self.skipped = True
            self.close()

    def touch_moved(self, touch) -> None:
        pass

    def touch_ended(self, touch) -> None:
        if not self.down:
            return
        self.down = False
        self._token += 1
        if self.skipped or self.closed:
            return
        self.advance()
