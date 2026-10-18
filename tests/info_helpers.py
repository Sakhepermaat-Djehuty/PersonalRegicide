"""Helpers for the info pop-up tests: the cards one action makes, as the app builds them."""
from typing import Callable, List, Optional

from app import info

ON = {"info_popups": True}


def cards_for(g, action: Callable[[], None], settings: Optional[dict] = None) -> List[info.InfoCard]:
    """Run ``action`` on ``g`` and build its queue (the snapshot before it, as the app's
    undo stack holds it)."""
    before = g.to_dict()
    action()
    return info.build(g, g.last_events, dict(ON, **(settings or {})), before=before)


def start_cards(g, settings: Optional[dict] = None) -> List[info.InfoCard]:
    """The queue of a fresh game (Battle start and what follows)."""
    return info.build(g, g.last_events, dict(ON, **(settings or {})), start=True)


def ids(cards) -> List[str]:
    return [c.id for c in cards]


def card(cards, row_id: str) -> info.InfoCard:
    found = [c for c in cards if c.id == row_id]
    assert found, "no %s card in %s" % (row_id, ids(cards))
    return found[0]


def text(c: info.InfoCard) -> str:
    """Everything a card says, for searching."""
    return "\n".join([c.title, c.number, c.middle, c.caption] + list(c.lines))


LINE_CHARS = 40


def fits(cards) -> None:
    """Every card keeps to the catalogue's limits: a title, at most 3 lines under a middle
    number and 6 otherwise, each line 40 characters at most."""
    for c in cards:
        assert c.title, c
        assert len(c.lines) <= c.max_lines(), (c, c.lines)
        for line in c.lines:
            assert len(line) <= LINE_CHARS, (c, line)
