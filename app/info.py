"""Info pop-ups: a landscape card for every phase of the game (docs/INFO_POPUPS.md).

After each action the builder turns what the action did (the engine's ``last_events``, the
game before it and the game after it) into a queue of cards (``InfoCard``) that the app
shows one at a time over the table: a tap moves on, a long press skips the rest. A
decision box, a handover or a result screen waits underneath until the queue is done.

The card builders live in their own modules, one per group of the settings list
(``info_turn``, ``info_classes``, ``info_defeat``, ``info_missions``, ``info_evergreen``).
Each registers handlers for the engine's event types with ``on``; a handler adds cards
(``Ctx.add``) or lines for the next card shown (``Ctx.line``). ``starters`` run before the
events and ``finishers`` after them (for the cards that stand before a decision box).

The owner's rulings on the catalogue (its questions):
- a killing blow shows no Paladin or Guardian card;
- Mage, Druid, Chanter and Reaver show one card, before their box; what was chosen is a
  line on the next card (no result cards);
- a pop-up switched off in the settings is gone: no card, no sound, no line in its place
  (a card that stands in for another, like the Warrior for Damage, falls back to it);
- a long press skips the rest of a queue;
- cards the player opens (rules, relics) keep the short card-flip sound.

Settings (App.settings): "info_popups" (the master box, on by default) and
"info_popups_off" (the rows switched off), so a new row is on; "info_icons" ({row id:
glyph, "" for none}) overrides the icons the picker page chose.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from regicide.cards import CLASS_NAME, SUIT_NAME, SUIT_SYMBOL

from . import theme as T

TREE = "tree"            # widgets.TREE_PIP: the Evergreen tree as an icon

# ---------------------------------------------------------------------------- the rows
# (id, group, settings label, default icon, edge colour); the settings list's order.
# An icon is a class letter (drawn as its class symbol), TREE, or a short text glyph.
ROWS: List[tuple] = [
    ("battle_start", "Turn", "Battle start", "⚑", T.CARD_BORDER),
    ("turn", "Turn", "Turn", "↻", T.CARD_BORDER),
    ("yield", "Turn", "Yield", "⚐", T.CARD_BORDER),
    ("corrupted", "Attack", "Corrupted", "", T.CORRUPTED),
    ("restored", "Attack", "Restored", "", T.RESTORED),
    ("declared", "Attack", "Declared", "", T.CARD_BORDER),
    ("kinfolk_flute", "Attack", "Kinfolk Flute", "♪", T.ACCENT),
    ("scarlet_whistle", "Attack", "Scarlet Whistle", "♬", T.SUIT_COLOR["H"]),
    ("azure_emblem", "Attack", "Azure Emblem", "◈", T.SUIT_COLOR["S"]),
    ("mother_corrupt", "Attack", "Mother (corrupt)", "❦", T.CORRUPTED),
    ("mother_restored", "Attack", "Mother (restored)", "❦", T.RESTORED),
    ("jester", "Jester", "Jester (base)", "J", T.JESTER_COLOR),
    ("jester_claim", "Jester", "Jester claim", "J", T.JESTER_COLOR),
    ("solo_jester_refresh", "Jester", "Solo Jester: new hand", "J", T.JESTER_COLOR),
    ("solo_jester_attack", "Jester", "Solo Jester: attack", "J", T.JESTER_COLOR),
    ("immunity", "Classes", "IMMUNITY", "", "#c8261f"),
    ("mage", "Classes", "Mage", "M", ""),
    ("druid", "Classes", "Druid", "U", ""),
    ("cleric", "Classes", "Cleric", "H", ""),
    ("bard", "Classes", "Bard", "D", ""),
    ("chanter", "Classes", "Chanter", "T", ""),
    ("reaver", "Classes", "Reaver", "R", ""),
    ("warrior", "Classes", "Warrior", "C", ""),
    ("paladin", "Classes", "Paladin", "S", ""),
    ("guardian", "Classes", "Guardian", "G", ""),
    ("damage", "Damage & defeat", "Damage", "", T.CARD_BORDER),
    ("defeated", "Damage & defeat", "Defeated", "⚔︎", T.CARD_BORDER),
    ("exact_kill", "Damage & defeat", "Exact kill!", "◎", T.ACCENT),
    ("cleanup", "Damage & defeat", "Clean-up", "≡", T.CARD_BORDER),
    ("team_damage", "Damage & defeat", "Team damage", "⁂", T.DANGER),
    ("new_enemy", "Enemy", "New enemy", "♚", T.CARD_BORDER),
    ("enemy_shift", "Enemy", "Enemy changes", "♚", T.CARD_BORDER),
    ("enemy_attack", "Enemy strikes", "Enemy attacks", "♚", T.DANGER),
    ("shielded", "Enemy strikes", "No damage", "S", ""),
    ("feign_death", "Enemy strikes", "Feign death", "", T.CARD_BORDER),
    ("damage_paid", "Enemy strikes", "Damage paid", "", T.CARD_BORDER),
    ("victory", "Game end", "Victory", "♛", T.ACCENT),
    ("loss", "Game end", "Defeat", "✕", T.DANGER),
    ("hydra_regrows", "Missions", "2 · Hydra regrows", "", T.CARD_BORDER),
    ("m3_zone", "Missions", "3 · Zone grows", "▦", T.CARD_BORDER),
    ("m5_zone", "Missions", "5 · Zone grows", "▦", T.CARD_BORDER),
    ("m5_carry", "Missions", "5 · Carry damage", "»", T.CARD_BORDER),
    ("m7_pilgrim", "Missions", "7 · Pilgrim arrives", "♙", T.CARD_BORDER),
    ("m7_match", "Missions", "7 · Pilgrim match", "♙", T.CARD_BORDER),
    ("m8_filled", "Missions", "8 · Zone filled!", "▦", T.ACCENT),
    ("m9_piles", "Missions", "9 · Captured piles", "▦", T.CARD_BORDER),
    ("m10_zone", "Missions", "10 · Zone grows", "▦", T.CARD_BORDER),
    ("m10_cleric", "Missions", "10 · Cleric enemy", "H", ""),
    ("m10_bard", "Missions", "10 · Bard enemy", "D", ""),
    ("m11_beast", "Missions", "11 · Beast", "", T.CARD_BORDER),
    ("m12_zone", "Missions", "12 · Zone grows", "▦", T.CARD_BORDER),
    ("shrine", "Evergreen", "Shrine", "⛰︎", T.EVERGREEN),
    ("cave", "Evergreen", "Cave", "⛰︎", T.EVERGREEN),
    ("cave_collapse", "Evergreen", "Cave collapses", "⛰︎", T.EVERGREEN),
    ("forest", "Evergreen", "Forest", "⛰︎", T.EVERGREEN),
    ("hills", "Evergreen", "Hills", "⛰︎", T.EVERGREEN),
    ("lake", "Evergreen", "Lake", "⛰︎", T.EVERGREEN),
    ("bane10", "Evergreen", "Poisonous Clerics", "☠︎", T.DANGER),
    ("bane12", "Evergreen", "Duplicitous Bards", "☠︎", T.DANGER),
    ("bane14", "Evergreen", "Absorbtion", "☠︎", T.DANGER),
    ("bane15", "Evergreen", "Tread Carefully", "☠︎", T.DANGER),
    ("bane16", "Evergreen", "Lingering Dread", "☠︎", T.DANGER),
    ("bane21", "Evergreen", "Eye-Level Sticks", "☠︎", T.DANGER),
    ("bane22", "Evergreen", "The Fiery Crucible", "☠︎", T.DANGER),
    ("bane23", "Evergreen", "Choose Your Poison", "☠︎", T.DANGER),
    ("boon30", "Evergreen", "Squad of Siblings", "✦", T.ACCENT),
    ("boon31", "Evergreen", "Selfless Rescue", "✦", T.ACCENT),
    ("boon32", "Evergreen", "Precision Strike", "✦", T.ACCENT),
    ("boon33", "Evergreen", "Restored Arrows", "✦", T.ACCENT),
    ("boon35", "Evergreen", "A Close Call", "✦", T.ACCENT),
]
ROW = dict((r[0], r) for r in ROWS)
GROUPS: List[str] = []
for _r in ROWS:
    if _r[1] not in GROUPS:
        GROUPS.append(_r[1])

# The short sound a card falls back on while it has no clip of its own ("info_<id>").
FALLBACK_SOUND = {
    "battle_start": "mission_start", "yield": "yield", "jester": "jester", "jester_claim": "jester",
    "solo_jester_refresh": "jester", "solo_jester_attack": "jester", "immunity": "power_blocked",
    "cleric": "power_heal", "bard": "draw", "warrior": "power_double", "paladin": "power_shield",
    "guardian": "power_shield", "damage": "hit", "defeated": "defeat_enemy", "exact_kill": "exact_kill",
    "new_enemy": "new_enemy", "enemy_attack": "suffer", "damage_paid": "discard", "feign_death": "discard",
    "victory": "victory", "loss": "loss", "hydra_regrows": "new_enemy",
}

MAX_LINES = 6              # on a card without a middle number
MAX_LINES_MIDDLE = 3       # under a middle number


# ---------------------------------------------------------------------------- settings
DEFAULT_ON = True          # the master box's default (the test suite turns it off: tests/conftest.py)


def popups_on(settings: dict) -> bool:
    return bool(settings.get("info_popups", DEFAULT_ON))


def row_on(settings: dict, row_id: str) -> bool:
    return popups_on(settings) and row_id not in (settings.get("info_popups_off") or ())


def set_row(settings: dict, row_id: str, on: bool) -> None:
    off = [r for r in (settings.get("info_popups_off") or []) if r != row_id]
    if not on:
        off.append(row_id)
    settings["info_popups_off"] = off


def icon_for(settings: dict, row_id: str) -> str:
    chosen = settings.get("info_icons") or {}
    if row_id in chosen:
        return str(chosen[row_id] or "")
    return ROW[row_id][3] if row_id in ROW else ""


# ---------------------------------------------------------------------------- the card
class InfoCard(object):
    """One info pop-up: ``id`` (its settings row), the ``title``, the strength top left
    (``number``), the ``icon`` (a class letter, TREE, or a glyph; None: the row's), the
    breakdown ``lines``, a big ``middle`` number with its ``caption``, ``immune`` (greyed
    and stamped IMMUNITY), the ``edge`` colour ("" : the row's, or the icon's class colour),
    ``sounds``: the clip and what it falls back on, the first that exists plays, and
    ``number_muted``: the number is drawn muted and struck through (not used)."""

    def __init__(self, id: str, title: str, number: Any = "", icon: Optional[str] = None,
                 lines: Sequence[str] = (), middle: Any = "", caption: str = "", immune: bool = False,
                 edge: str = "", sounds: Optional[Sequence[str]] = None, number_muted: bool = False) -> None:
        self.id = id
        self.title = title
        self.number = "" if number is None else str(number)
        self.number_muted = number_muted       # shown but not used (a Druid's or Chanter's strength)
        self.icon = icon
        self.lines = [str(x) for x in lines if x]
        self.middle = "" if middle is None else str(middle)
        self.caption = caption
        self.immune = immune
        self.edge = edge
        if sounds is None:
            sounds = ["info_" + ("immunity" if immune else id)]
            if immune:
                sounds.append(FALLBACK_SOUND["immunity"])
            elif id in FALLBACK_SOUND:
                sounds.append(FALLBACK_SOUND[id])
        self.sounds = list(sounds)

    def max_lines(self) -> int:
        return MAX_LINES_MIDDLE if self.middle else MAX_LINES

    def __repr__(self) -> str:
        return "InfoCard(%s: %s%s)" % (self.id, self.title, " IMMUNE" if self.immune else "")

    def face_args(self, settings: dict) -> dict:
        """The InfoCardFace keyword arguments for this card."""
        row = ROW.get(self.id)
        icon = icon_for(settings, self.id) if self.icon is None else self.icon
        edge = self.edge or (row[4] if row else "") or T.SUIT_COLOR.get(icon, T.CARD_BORDER)
        return {"title": self.title, "number": self.number, "icon": icon, "lines": self.lines[:self.max_lines()],
                "middle": self.middle, "middle_caption": self.caption, "immune": self.immune, "edge": edge,
                "number_muted": self.number_muted}


# ---------------------------------------------------------------------------- the builder
Handler = Callable[["Ctx", dict], None]
HANDLERS: Dict[str, List[Handler]] = {}
EACH_EVENT: List[Handler] = []                 # before the handlers of every event, whatever its type
STARTERS: List[Callable[["Ctx"], None]] = []
FINISHERS: List[Callable[["Ctx"], None]] = []
LAST: List[Callable[["Ctx"], None]] = []        # after every finisher (the game-end card)


def on(*types: str) -> Callable[[Handler], Handler]:
    """Register a handler for these engine event types (``ev["t"]``)."""
    def wrap(fn: Handler) -> Handler:
        for t in types:
            HANDLERS.setdefault(t, []).append(fn)
        return fn
    return wrap


def each_event(fn: Handler) -> Handler:
    """Register a handler run before the type handlers of every event (e.g. to queue cards
    held for "after the previous event")."""
    EACH_EVENT.append(fn)
    return fn


def starter(fn: Callable[["Ctx"], None]) -> Callable[["Ctx"], None]:
    STARTERS.append(fn)
    return fn


def finisher(fn: Callable[["Ctx"], None]) -> Callable[["Ctx"], None]:
    FINISHERS.append(fn)
    return fn


def last(fn: Callable[["Ctx"], None]) -> Callable[["Ctx"], None]:
    """Register a finisher that runs after all the others (the card that ends a queue)."""
    LAST.append(fn)
    return fn


class Ctx(object):
    """What one action did, for the card builders, and the queue being built.

    ``g``: the game after the action; ``before``: the game before it (None at a game's
    start or when there is no snapshot); ``events``: ``g.last_events``; ``i``: the index of
    the event being handled; ``start``: the queue of a fresh game (Battle start);
    ``carry``: a dict kept with the game between actions (``g.extra["info_carry"]``: saved,
    undone and resumed with it) for cards that gather several actions; ``state``: scratch
    shared by the handlers of this one build; ``app``: what only the app knows
    ({"coins_on_loss": n}: the coins losing this campaign mission now earns)."""

    def __init__(self, g: Any, events: Sequence[dict], settings: dict, before: Any = None,
                 start: bool = False, app: Optional[dict] = None) -> None:
        self.g = g
        self.app = dict(app or {})     # what only the app knows (the coins a mission loss earns)
        self.events = list(events)
        self.settings = settings
        self._before = before
        self.start = start
        self.cards: List[InfoCard] = []
        self.pending: List[str] = []
        self.deferred: Dict[str, List[InfoCard]] = {}
        self.state: Dict[str, Any] = {}
        self.i = 0
        if g is not None and isinstance(getattr(g, "extra", None), dict):
            self.carry = g.extra.setdefault("info_carry", {})
        else:
            self.carry = {}

    # -- the game
    @property
    def before(self) -> Any:
        """The game before the action (a snapshot dict is turned into a Game once)."""
        if isinstance(self._before, dict):
            from regicide.engine import Game
            try:
                self._before = Game.from_dict(self._before)
            except Exception:
                self._before = None
        return self._before

    @property
    def solo(self) -> bool:
        return self.g.n_players == 1

    @property
    def base(self) -> bool:
        """The base game (not Legacy nor Evergreen): wording follows the base cards."""
        return str(getattr(self.g.config, "rules_id", "base")) == "base"

    @property
    def mission(self) -> int:
        return int(getattr(self.g.rules, "mission", 0) or 0)

    @property
    def evergreen(self) -> bool:
        return str(getattr(self.g.config, "rules_id", "")) == "evergreen"

    def name(self, player: Any) -> str:
        """"You" solo; the player's name with 2+ players (the phone passes around)."""
        if self.solo:
            return "You"
        try:
            return self.g.players[int(player)].name
        except (IndexError, TypeError, ValueError):
            return "?"

    def label(self, card_id: Any) -> str:
        cid = str(card_id)
        return self.g.cards[cid].label() if cid in self.g.cards else cid

    def labels(self, card_ids: Sequence[Any], sep: str = " ") -> str:
        return sep.join(self.label(c) for c in card_ids)

    def class_title(self, suit: str) -> str:
        """Cleric, Bard...; the base game names its suits (♥ Hearts)."""
        if self.base:
            return "%s %s" % (SUIT_SYMBOL.get(suit, suit), SUIT_NAME.get(suit, suit))
        return CLASS_NAME.get(suit, suit)

    @property
    def reserve(self) -> str:
        return "tavern deck" if self.base else "reserve"

    # -- the events
    @property
    def ev(self) -> dict:
        return self.events[self.i] if 0 <= self.i < len(self.events) else {}

    def later(self, *types: str) -> List[dict]:
        """The events after the current one of these types (any type when none given)."""
        return [e for e in self.events[self.i + 1:] if not types or e.get("t") in types]

    def earlier(self, *types: str) -> List[dict]:
        return [e for e in self.events[:self.i] if not types or e.get("t") in types]

    def has(self, *types: str) -> bool:
        return any(e.get("t") in types for e in self.events)

    # -- the queue
    def on(self, row_id: str) -> bool:
        return row_on(self.settings, row_id)

    @property
    def killed(self) -> bool:
        """The action's damage felled the enemy (its defeat may wait for a box first)."""
        if self.has("defeat"):
            return True
        for e in self.events:
            if e.get("t") == "damage":
                try:
                    if int(e.get("hp", 1)) <= 0:
                        return True
                except (TypeError, ValueError):
                    pass
        return False

    def add(self, card: InfoCard) -> bool:
        """Queue ``card`` if its row is on (a stamped card's row is IMMUNITY's), with the
        lines waiting for the next card on top of its own, as many as it holds (the rest
        go on the card after it). Returns whether it was queued: a row switched off leaves
        nothing (no card, no sound, no line)."""
        if not self.on("immunity" if card.immune else card.id):
            return False
        if self.pending:
            # as many as it holds; the rest wait for the card after it
            room = max(0, card.max_lines() - len(card.lines))
            card.lines = self.pending[:room] + card.lines
            self.pending = self.pending[room:]
        self.cards.append(card)
        return True

    def line(self, text: str) -> None:
        """An outcome line for the next card shown (what a box chose, a heal, a draw...)."""
        if text:
            self.pending.append(text)

    def defer(self, slot: str, card: InfoCard) -> None:
        """Hold ``card`` until ``flush(slot)`` (e.g. a Paladin card after the damage)."""
        self.deferred.setdefault(slot, []).append(card)

    def flush(self, slot: str) -> None:
        for card in self.deferred.pop(slot, []):
            self.add(card)


def _run(fn: Callable, *args: Any) -> None:
    """Run one builder function. One that fails leaves its cards out, never the whole queue:
    on the phone the error goes to errors.log; elsewhere (the tests) it is raised."""
    try:
        fn(*args)
    except Exception:
        from . import store
        if not store._is_pythonista():
            raise
        import traceback
        try:
            store.log_error("Info pop-ups (%s)\n%s" % (getattr(fn, "__name__", "?"), traceback.format_exc()))
        except Exception:
            pass


def build(g: Any, events: Sequence[dict], settings: dict, before: Any = None, start: bool = False,
          app: Optional[dict] = None) -> List[InfoCard]:
    """The queue of info cards for one action (or, with ``start``, for a fresh game)."""
    if g is None or not popups_on(settings):
        return []
    ctx = Ctx(g, events, settings, before, start, app)
    for fn in STARTERS:
        _run(fn, ctx)
    for i, ev in enumerate(ctx.events):
        ctx.i = i
        for fn in EACH_EVENT:
            _run(fn, ctx, ev)
        for fn in HANDLERS.get(str(ev.get("t")), ()):
            _run(fn, ctx, ev)
    ctx.i = len(ctx.events)
    for slot in list(ctx.deferred):
        ctx.flush(slot)
    for fn in FINISHERS + LAST:
        _run(fn, ctx)
    if ctx.pending:
        # lines with no card after them wait for the next action's first card
        ctx.carry["lines"] = (list(ctx.carry.get("lines") or []) + ctx.pending)[-MAX_LINES:]
        ctx.pending = []
    return ctx.cards


@starter
def _carried_lines(ctx: Ctx) -> None:
    """Lines an earlier action left with no card to go on come first."""
    lines = ctx.carry.pop("lines", None)
    if lines:
        ctx.pending.extend(lines)


# the card builders register themselves on import (each module imports this one); one
# that fails to load leaves the others working (LOAD_ERRORS says why: a test checks it)
BUILDERS = ("info_turn", "info_classes", "info_defeat", "info_missions", "info_evergreen")
LOAD_ERRORS: Dict[str, str] = {}


def _load_builders() -> None:
    import importlib
    import traceback
    for name in BUILDERS:
        try:
            importlib.import_module("." + name, __package__)
        except Exception:
            LOAD_ERRORS[name] = traceback.format_exc()


_load_builders()
