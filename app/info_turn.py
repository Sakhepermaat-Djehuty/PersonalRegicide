"""Info pop-ups: the Turn, Attack and Jester groups (battle start, turn, yield, the entry
cards, the relics, the Jesters). See docs/INFO_POPUPS.md and app/info.py.

A card that stands before a box (a relic's, the Evergreen Mother's) comes after every
other card of the event that asks the box; the Evergreen Mother's restored card comes
after the card of the step that banished (``after``). What a relic's box chose is a line
on the next card, and only while that relic's row is on. Cards going into a hidden hand
or the reserve are never named: the Azure Emblem's placements and keeps are counts, one
line told after the Mage's own once the mage is done (its card shows once an attack).
"""
from __future__ import annotations

import functools
import traceback
from typing import Any, Callable, List, Optional, Sequence

from regicide.cards import SUIT_SYMBOL

from . import theme as T
from .info import Ctx, InfoCard, each_event, finisher, on, starter

LINE = 40

# the events that tell of a banish just made (their banish_redirect events come first)
BANISHERS = ("corrupt_banish", "zone_cleared", "discard_banished", "pilgrim_banish", "zone_banish",
             "beast_effect", "bane", "lake_banish", "pile_rescue", "druid_assign", "reaver_pick", "cleanup_order")
# the answers to a relic's box: the box asked again after one shows no card
ANSWERS = {"flute_add": ("flute_pass", "add_to_play"), "whistle_add": ("whistle_pass", "add_to_play"),
           "emblem_place": ("emblem_place", "emblem_pass")}
# the mage's last steps (its outcome line comes at the last of them) and the boxes that follow
MAGE_RESULTS = ("mage_pick", "mage_skip", "emblem_keep", "emblem_skip", "discard_order", "discard_top")
MAGE_BOXES = ("emblem_keep", "discard_order", "discard_top")
# carry keys: the Azure Emblem's outcome, told after the mage's; the attack that showed its
# card (both keyed by the attack, so a step the builder never saw leaves nothing stale)
EMBLEM = "turn_emblem"
EMBLEM_SHOWN = "turn_emblem_card"

# Battle start: one setup note and the rule to watch, per mission
MISSION_NOTES = {
    1: ("", "Exact kill: enemy on top of the reserve"),
    2: ("", "Not exact: the head comes back later"),
    3: ("", "End of turn: reserve top joins the zone"),
    4: ("", "Enemies gain the top discard's strength"),
    5: ("Myla starts in the banished pile", "End of turn: banished top joins the zone"),
    6: ("Myla starts in the zone", "Each kill: team damage = zone strength"),
    7: ("The pilgrim deck waits in the zone", "Start of turn: a pilgrim turns face up"),
    8: ("The pilgrim ace starts in the zone", "A kill: build the zone up to a 10"),
    9: ("3 captured piles of 10 in the zone", "End of turn: rescue a card or rotate"),
    10: ("Your corrupted friends are the enemies", "Start of turn: reserve top to the zone"),
    11: ("Gøran's beasts face down in the zone", "Start of turn: a beast is revealed"),
    12: ("Restored cards ignore immunity", "Start of turn: banished top to the zone"),
}
LOCATION_RULES = {
    "A": "End of turn: reserve top joins the zone", "B": "End of turn: reserve top joins the zone",
    "C": "End of turn: banished top joins the zone", "D": "End of turn: zone grows, team damage",
    "E": "Start of turn: a pilgrim joins the zone",
}
LOCATION_SETUP = {"C": "Phase I experiments in the banished pile", "E": "The pilgrim deck waits in the zone"}
# the other Evergreen setup cards' notes (after Mental Health Day, Too Easy! and the location's)
EVERGREEN_SETUP = (
    ("bane", 1, "Hydras replace the Phase II enemies"), ("bane", 3, "Wyverns replace the Phase III enemies"),
    ("bane", 5, "Myla (20/80) waits at the castle bottom"), ("bane", 6, "Full Moon: Ash and mage ace set aside"),
    ("bane", 7, "Solstice: the five 10s are set aside"), ("bane", 8, "The High Arcana waits at the bottom"),
    ("boon", 24, "Mercenaries hired with 5 coins"), ("boon", 25, "Gøran the Evergreen joins the reserve"),
    ("boon", 26, "All four beasts join the reserve"), ("boon", 28, "The pilgrim ace joins the reserve"),
    ("boon", 29, "Second Breakfast: three 3s join"),
)


# ---------------------------------------------------------------------------- helpers
def _guard(fn: Callable) -> Callable:
    """A handler that fails leaves its cards out, never the whole queue: on the phone the
    error goes to errors.log; elsewhere (the tests) it is raised."""
    @functools.wraps(fn)
    def run(*args: Any) -> None:
        try:
            fn(*args)
        except Exception:
            from . import store
            if not store._is_pythonista():
                raise
            try:
                store.log_error("Info pop-ups (%s)\n%s" % (fn.__name__, traceback.format_exc()))
            except Exception:
                pass
    return run


def fit(*variants: str) -> str:
    """The first wording that fits on a line (the last one cut to fit)."""
    for text in variants:
        if len(text) <= LINE:
            return text
    return variants[-1][:LINE - 1] + "…"


def count(n: int, word: str) -> str:
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def icons(suits: Sequence[str]) -> str:
    return "".join(SUIT_SYMBOL.get(s, s) for s in suits)


def then(ctx: Ctx) -> Any:
    """The game as the action found it (the game after it when there is no snapshot)."""
    return ctx.before or ctx.g


def relics(game: Any) -> List[str]:
    return list((getattr(game, "extra", None) or {}).get("relics") or [])


def card_of(ctx: Ctx, card_id: Any) -> Any:
    return ctx.g.cards.get(str(card_id))


def strength(game: Any, card_id: Any) -> int:
    """A card's strength (a 2/5 counts the value it was given)."""
    cid = str(card_id)
    declared = (game.extra.get("declared_value") or {}).get(cid)
    if declared is not None:
        return int(declared)
    card = game.cards.get(cid)
    return int(card.value) if card is not None else 0


def play_at(game: Any, index: Any) -> Any:
    try:
        return game.plays[int(index)]
    except (AttributeError, IndexError, TypeError, ValueError):
        return None


def play_with(game: Any, card_id: Any) -> Any:
    """The attack on the table holding this card."""
    for play in getattr(game, "plays", None) or ():
        if str(card_id) in play.card_ids:
            return play
    return None


def old_value(ctx: Ctx, index: Any) -> Optional[int]:
    """An attack's strength before this action (the snapshot's play)."""
    play = play_at(ctx.before, index) if ctx.before is not None else None
    return int(play.value) if play is not None else None


def decision(game: Any) -> dict:
    return (getattr(game, "decision", None) or {}) if game is not None else {}


def attack_key(ctx: Ctx, index: Any = None) -> list:
    """The attack being resolved: the turn the action began in and its place on the table
    (by default the one the answered box was resolving)."""
    if index is None:
        index = decision(ctx.before).get("play_index")
    return [getattr(then(ctx), "turn", None), index]


def asked_before(ctx: Ctx, kind: str) -> bool:
    """Was this box already asked (the game was waiting on it, or this action answered
    it)? A box asked again shows no card."""
    d = decision(ctx.before)
    if kind in (d.get("kind"), (d.get("resume_decision") or {}).get("kind")):
        return True
    answers = ANSWERS.get(kind, ())
    return any(e.get("t") in answers and (e.get("t") != "add_to_play" or e.get("source") == "hand")
               for e in ctx.earlier())


def once(ctx: Ctx, key: str) -> bool:
    """True the first time ``key`` is asked for in this build."""
    if ctx.state.get(key):
        return False
    ctx.state[key] = True
    return True


def fixed_immunity(ctx: Ctx, suits: Sequence[str]) -> bool:
    """Is the enemy's immunity to one of these classes one nothing ignores (Myla, 20/80)?"""
    game = then(ctx)
    try:
        return game.enemy is not None and any(game.rules.fixed_immunity(game, s) for s in suits)
    except Exception:
        return False


def enemy_label(game: Any) -> str:
    return game.enemy.name if getattr(game, "enemy", None) is not None else "The enemy"


def ignores_line(ctx: Ctx, card: Any) -> str:
    """Its ♣ ignores immunity (a corrupted or restored card's classes)."""
    suits = tuple(card.suits)
    if not suits:
        return ""
    myla = " (not Myla's)" if fixed_immunity(ctx, suits) else ""
    return "Its %s %s immunity%s" % (icons(suits), "ignores" if len(suits) == 1 else "ignore", myla)


def after(ctx: Ctx, at: int, card: Any) -> None:
    """Queue ``card`` (or an outcome line) after the cards and lines of event ``at``
    (before those of the next event)."""
    ctx.state.setdefault("after", []).append((at, card))


def _release(ctx: Ctx, upto: int) -> None:
    waiting = ctx.state.get("after") or []
    ctx.state["after"] = [(at, c) for at, c in waiting if at >= upto]
    for at, c in waiting:
        if at >= upto:
            continue
        if isinstance(c, str):
            ctx.line(c)
        else:
            ctx.add(c)


@each_event
def _waiting(ctx: Ctx, ev: dict) -> None:
    """Cards held for "after event j" go before the cards of the events after it."""
    _release(ctx, ctx.i)


@finisher
def _waiting_last(ctx: Ctx) -> None:
    _release(ctx, len(ctx.events) + 1)


# ---------------------------------------------------------------------------- Battle start
def _mission_title(ctx: Ctx) -> str:
    g = ctx.g
    if ctx.base:
        return "Regicide"
    if ctx.evergreen:
        try:
            return g.rules.location_name(g)
        except Exception:
            return "Evergreen"
    try:
        from regicide.campaign import missions as M
        return str(M.mission(ctx.mission)["title"])
    except Exception:
        return "Regicide"


def _setup_note(ctx: Ctx) -> str:
    g = ctx.g
    if ctx.base:
        if ctx.solo:
            return ""
        n = g.config.deck_jesters
        return "%s in the tavern deck" % count(n, "Jester") if n else ""
    if not ctx.evergreen:
        return MISSION_NOTES.get(ctx.mission, ("", ""))[0]
    setup = g.config.extra.get("evergreen") or {}
    drawn = [("bane", int(n)) for n in setup.get("banes", [])] + [("boon", int(n)) for n in setup.get("boons", [])]
    if ("bane", 2) in drawn:
        return "Mental Health Day: %d to the discard" % (len(g.discard) or 30)
    if ("boon", 27) in drawn:
        return "Too Easy!: hand limit +1"
    if _location(ctx) in LOCATION_SETUP:
        return LOCATION_SETUP[_location(ctx)]
    return next((note for kind, n, note in EVERGREEN_SETUP if (kind, n) in drawn), "")


def _rule_to_watch(ctx: Ctx) -> str:
    g = ctx.g
    if ctx.base:
        return "%s: a new hand each" % count(g.solo_jesters, "Jester") if ctx.solo and g.solo_jesters else ""
    if ctx.evergreen:
        return LOCATION_RULES.get(_location(ctx), "")
    return MISSION_NOTES.get(ctx.mission, ("", ""))[1]


def _first_enemy_lines(ctx: Ctx) -> List[str]:
    """The first enemy as it was revealed: when a start-of-turn step changes it (a zone
    card, a beast), that step's card tells the change, so its printed attack and classes
    come here (nothing feeds them yet at the start)."""
    g = ctx.g
    e = g.enemy
    if e is None:
        return []
    attack, suits = g.enemy_attack, g.rules.immune_suits(g)
    turn = next((k for k, ev in enumerate(ctx.events) if ev.get("t") == "turn"), None)
    if turn is not None and _enemy_changes(ctx, _segment(ctx, turn)):
        attack, suits = e.attack * int(g.rules.attack_multiplier(g)), e.suits
    first = "First: %s %d/%d" % (e.name, attack, e.hp)
    immune = icons(suits)
    if not immune:
        return [fit(first)]
    together = "%s, immune %s" % (first, immune)
    return [together] if len(together) <= LINE else [fit(first), "Immune to %s" % immune]


@starter
@_guard
def _battle_start(ctx: Ctx) -> None:
    """A fresh game's first card: the mission, the castle, the first enemy (no New enemy
    card at the start), one setup note and the rule to watch."""
    if not ctx.start:
        return
    g = ctx.g
    castle = len(g.castle) + (1 if g.enemy is not None else 0)
    lines = ["%d %s · hand limit %d" % (castle, "enemy" if castle == 1 else "enemies", g.config.max_hand)]
    lines += _first_enemy_lines(ctx)
    lines += [_setup_note(ctx), _rule_to_watch(ctx)]
    number = ctx.mission if not ctx.base and not ctx.evergreen and ctx.mission else ""
    ctx.add(InfoCard("battle_start", _mission_title(ctx), number, lines=lines))


# ---------------------------------------------------------------------------- Turn
def _segment(ctx: Ctx, at: int) -> List[dict]:
    """The events after the turn event ``at``, up to the next one: the start of that turn."""
    out = []
    for e in ctx.events[at + 1:]:
        if e.get("t") == "turn":
            break
        out.append(e)
    return out


def _enemy_changes(ctx: Ctx, events: Sequence[dict]) -> bool:
    """Does a start-of-turn step change the enemy, with a card of its own that says how (a
    zone that feeds it, a beast) and that is switched on? The start-of-turn banes' cards do
    not state the enemy."""
    for e in events:
        t = e.get("t")
        if t in ("beast_reveal", "beast_effect"):
            if ctx.on("m11_beast"):
                return True
        elif t == "zone_add" and ctx.mission != 7 and not (ctx.evergreen and _location(ctx) == "E"):
            row = {3: "m3_zone", 5: "m5_zone", 10: "m10_zone", 12: "m12_zone"}.get(ctx.mission)
            if row is None or ctx.on(row):      # a zone card switched off states nothing
                return True
    return False


def _location(ctx: Ctx) -> str:
    return str((ctx.g.config.extra.get("evergreen") or {}).get("location", ""))


def _end_of_turn_effects(ctx: Ctx) -> bool:
    """Does this game have end-of-turn effects (that a kill skips)?"""
    if ctx.base:
        return False
    if ctx.evergreen:
        banes = (ctx.g.config.extra.get("evergreen") or {}).get("banes", [])
        return _location(ctx) in ("A", "B", "C", "D") or any(int(n) in (10, 12, 23) for n in banes)
    return ctx.mission in (3, 5, 9, 10)


def enemy_lines(g: Any) -> List[str]:
    """The enemy now: "Troll: attack 10, health 20/20" (a long name on its own line)."""
    e = g.enemy
    if e is None:
        return []
    stats = "attack %d, health %d/%d" % (g.enemy_attack, e.hp, e.max_hp)
    one = "%s: %s" % (e.name, stats)
    return [one] if len(one) <= LINE else [fit(e.name), stats[0].upper() + stats[1:]]


@on("turn")
@_guard
def _turn(ctx: Ctx, ev: dict) -> None:
    """Who plays now, their hand and the enemy (no card for a solo game's first turn)."""
    g = ctx.g
    player = ev.get("player", g.active)
    number = ev.get("turn", "")
    if ctx.solo and (ctx.start or str(number) in ("", "0", "1")):
        return
    who = ctx.name(player)
    killed = not ctx.start and bool(ctx.earlier("defeat", "reveal"))
    claim = bool(ctx.earlier("choose_next")) and bool(g.extra.get("jester_attack"))
    if claim:
        title = "%s claims the Jester" % who
    elif killed:
        title = "Your turn again" if ctx.solo else "%s again" % who
    else:
        title = "Your turn" if ctx.solo else "%s's turn" % who
    segment = _segment(ctx, ctx.i)
    lines = []
    try:
        lines.append("Hand %d of %d" % (len(g.players[int(player)].hand), g.config.max_hand))
    except (IndexError, TypeError, ValueError):
        pass
    if not _enemy_changes(ctx, segment):
        lines += enemy_lines(g)
    if killed and _end_of_turn_effects(ctx):
        lines.append("After a kill: no end-of-turn effects")
    if any(e.get("t") == "beast_skip" for e in segment):
        lines.append("Exact kill: no beast this turn")
    if any(e.get("t") == "zone_skip" for e in segment):
        lines.append("Exact kill: no zone card this turn")
    ctx.add(InfoCard("turn", fit(title, who), number, lines=lines))


@on("choose_next")
@_guard
def _chosen(ctx: Ctx, ev: dict) -> None:
    """The base Jester's choice is a line on the Turn card (a claim is its title)."""
    if ctx.g.extra.get("jester_attack") or not ctx.on("jester"):
        return
    ctx.line(fit("%s goes next (Jester)" % ctx.name(ev.get("player")), "Next: %s" % ctx.name(ev.get("player"))))


# ---------------------------------------------------------------------------- Yield
@on("yield")
@_guard
def _yield(ctx: Ctx, ev: dict) -> None:
    who = ctx.name(ev.get("player", ctx.g.active))
    verb = "yield" if ctx.solo else "yields"
    lines = [fit("%s %s: no attack this turn" % (who, verb), "%s %s: no attack" % (who, verb), "No attack this turn"),
             "The enemy strikes next"]
    before = ctx.before
    if before is not None and (before.extra or {}).get("jester_attack"):
        lines.append("The claimed Jester's chance is spent")
    ctx.add(InfoCard("yield", "Yield", lines=lines))


# ---------------------------------------------------------------------------- Corrupted, Restored
def _redirected(ctx: Ctx, card_id: Any) -> bool:
    """Did the Evergreen Mother send this card under the reserve in this action?"""
    return any(e.get("t") == "banish_redirect" and str(e.get("card")) == str(card_id) for e in ctx.events)


def _banish_line(ctx: Ctx, ev: dict) -> str:
    if ev.get("t") == "corrupt_banish_none":
        if "mother" in relics(ctx.g) and not ctx.solo:
            return "Nothing to banish: other hands empty"
        return "Nothing to banish: %s empty" % ctx.reserve
    if card_of(ctx, ev.get("banished")) is None:
        return ""
    source = str(ev.get("source", ""))
    who = ctx.name(ev.get("player"))
    if _redirected(ctx, ev.get("banished")):
        # restored: it goes under the reserve, so it is not named (the Mother card follows)
        where = {"hand": "%s's card" % who, "discard pile": "Top discard"}.get(source, "Reserve top")
        return fit("%s is restored: not banished" % where, "Restored: not banished")
    lost = ctx.label(ev.get("banished"))
    if source == "hand":
        return fit("%s banishes %s from hand (Mother)" % (who, lost), "%s banishes %s (Mother)" % (who, lost),
                   "%s banished from a hand (Mother)" % lost)
    if source == "discard pile":
        return fit("Top discard banished: %s (Mother)" % lost, "Top discard banished: %s" % lost)
    return fit("Reserve top banished: %s" % lost)


@on("corrupt_banish", "corrupt_banish_none")
@_guard
def _corrupted(ctx: Ctx, ev: dict) -> None:
    """One card per corrupted card entering play, with what it banished."""
    card = card_of(ctx, ev.get("card"))
    if card is None:
        return
    lines = [fit("%s enters play corrupted" % card.label(), "It enters play corrupted"),
             _banish_line(ctx, ev), ignores_line(ctx, card)]
    ctx.add(InfoCard("corrupted", "Corrupted", strength(ctx.g, card.id), lines=lines))


def _restored_card(ctx: Ctx, card: Any, second: str) -> InfoCard:
    lines = [fit("%s enters play restored" % card.label(), "It enters play restored"), second,
             ignores_line(ctx, card)]
    return InfoCard("restored", "Restored", strength(ctx.g, card.id), lines=lines)


@on("restore")
@_guard
def _restored(ctx: Ctx, ev: dict) -> None:
    """A restored card returns the top banished card under the reserve (not named: it is
    in the reserve now); mission 12 sends a corrupted one to the banished bottom."""
    card = card_of(ctx, ev.get("card"))
    if card is None:
        return
    returned = ev.get("returned")
    prev = ctx.events[ctx.i - 1] if ctx.i > 0 else {}
    if prev.get("t") == "reserve_redirect" and str(prev.get("card")) == str(returned):
        second = fit("M12: %s is corrupted → banished bottom" % ctx.label(returned),
                     "%s is corrupted → banished bottom" % ctx.label(returned),
                     "M12: it is corrupted → banished bottom")
    else:
        second = "Banished top goes under the %s" % ctx.reserve
    ctx.add(_restored_card(ctx, card, second))


def _entered(ctx: Ctx, ev: dict) -> None:
    """Restored cards entering play with no restore event: the banished pile was empty.
    Their card comes after this event's lines (an attack's formation line goes on it, as on
    a Restored card made at its restore event)."""
    for cid in ev.get("cards") or ():
        card = card_of(ctx, cid)
        if card is None or not card.has("restored"):
            continue
        if any(e.get("t") == "restore" and str(e.get("card")) == str(cid) for e in ctx.later()):
            continue
        after(ctx, ctx.i, _restored_card(ctx, card, "Banished pile empty: nothing returns"))


# ---------------------------------------------------------------------------- what entered play
@on("play")
@_guard
def _played(ctx: Ctx, ev: dict) -> None:
    """Solo cards played from the Kinfolk Flute make a line; restored cards may need a card."""
    before = ctx.before
    stored = [str(c) for c in ((before.extra or {}).get("flute") or [])] if before is not None else []
    from_flute = [c for c in ev.get("cards") or () if str(c) in stored]
    if from_flute and ctx.on("kinfolk_flute"):
        ctx.line(fit("%s from the flute" % ctx.labels(from_flute),
                     "%s from the flute" % count(len(from_flute), "card")))
    _entered(ctx, ev)


@on("add_to_play")
@_guard
def _added(ctx: Ctx, ev: dict) -> None:
    """A Kinfolk Flute or Scarlet Whistle addition from another hand is a line."""
    kind = decision(ctx.before).get("kind")
    if ev.get("source") == "hand" and kind in ("flute_add", "whistle_add") and ev.get("cards"):
        who = ctx.name(ev.get("player"))
        cards = ctx.labels(ev.get("cards") or ())
        if kind == "flute_add" and ctx.on("kinfolk_flute"):
            ctx.line(fit("%s adds %s (Kinfolk Flute)" % (who, cards), "%s adds %s" % (who, cards)))
        elif kind == "whistle_add" and ctx.on("scarlet_whistle"):
            old = old_value(ctx, ev.get("play_index"))
            gain = "%s → %s" % (old, ev.get("value")) if old is not None else "strength %s" % ev.get("value")
            ctx.line(fit("%s adds %s: %s" % (who, cards, gain), "%s adds %s" % (who, cards)))
    _entered(ctx, ev)


# ---------------------------------------------------------------------------- Declared
def _declared_strength(ctx: Ctx, card_id: Any) -> Any:
    for game in (ctx.g, ctx.before):
        play = play_with(game, card_id) if game is not None else None
        if play is not None:
            return play.value
    for e in reversed(ctx.earlier("play", "add_to_play")):
        if str(card_id) in [str(c) for c in e.get("cards") or ()]:
            return e.get("value", "")
    return ""


def _value_lines(ctx: Ctx, evs: List[dict]) -> List[str]:
    ids = [str(e.get("card")) for e in evs]
    value = evs[-1].get("value")
    labels = ctx.labels(ids)
    lines = [fit("%s %s %s" % (labels, "counts" if len(ids) == 1 else "count", value),
                 "The 2/5s count %s" % value)]
    if any(e.get("forced") for e in evs):
        lines.append("Forced by the kinfolk set")
    new = evs[-1].get("attack")
    old = None
    play = play_with(ctx.before, ids[0]) if ctx.before is not None else None
    if play is not None:
        old = play.value
    if old is not None and new is not None and old != new:
        lines.append("Attack strength %s → %s" % (old, new))
    elif new is not None:
        lines.append("Attack strength %s" % new)
    return lines


@on("declare")
@_guard
def _declared(ctx: Ctx, ev: dict) -> None:
    """One card for the declarations of an action: a 2/5's value, a Wild Animal's class."""
    if not once(ctx, "declared"):
        return
    evs = [e for e in ctx.events[ctx.i:] if e.get("t") == "declare" and card_of(ctx, e.get("card")) is not None]
    values = [e for e in evs if "value" in e]
    classes = [e for e in evs if e.get("suit")]
    lines: List[str] = []
    icon, edge, number = None, "", ""
    if values:
        lines += _value_lines(ctx, values)
        icon, number = "2/5", values[-1].get("attack", "")
    for e in classes:
        suit = str(e.get("suit"))
        name = ctx.class_title(suit)
        label = ctx.label(e.get("card"))
        lines += [fit("%s is a %s while in play" % (label, name), "It is a %s while in play" % name),
                  "Its %s power joins this attack" % name]
        if icon is None:
            icon, edge = suit, T.SUIT_COLOR.get(suit, "")
        if number == "":
            number = _declared_strength(ctx, e.get("card"))
    if lines:
        ctx.add(InfoCard("declared", "Declared", number, icon=icon, lines=lines, edge=edge))


# ---------------------------------------------------------------------------- the relics
def _flute_card(ctx: Ctx, ev: dict) -> InfoCard:
    play = play_at(ctx.g, ev.get("play_index"))
    limit = ctx.g.rules.kinfolk_limit(ctx.g)
    asked = [ctx.name(p) for p in [ev.get("player")] + list(ev.get("queue") or []) if p is not None]
    same = ev.get("strength", play.value if play is not None else None)
    lines = ["Others may add cards of strength %s" % same if same is not None
             else "Others may add cards of its strength", "to make a kinfolk set of up to %d" % limit]
    if limit != 10:
        lines.append("An Alliance raises the limit to %d" % limit)
    lines.append("No animal companions")
    if asked:
        lines.append(fit("Asked in turn: %s" % ", ".join(asked), "Asked: %s" % ", ".join(asked),
                         "Asked in turn, from %s" % asked[0], "Asked in turn"))
    return InfoCard("kinfolk_flute", "Kinfolk Flute", play.value if play is not None else "", lines=lines)


@on("flute_store")
@_guard
def _flute_store(ctx: Ctx, ev: dict) -> None:
    """Solo: a card stored on the Kinfolk Flute, on its own."""
    cid = ev.get("card")
    if card_of(ctx, cid) is None:
        return
    value = ev.get("value")
    held = ctx.label(cid) if value is None else "%s as a %s" % (ctx.label(cid), value)
    lines = [fit("Stored %s on the flute (once a turn)" % held, "Stored %s on the flute" % held),
             "Play flute cards in a kinfolk set", "as if from your hand"]
    number = value if value is not None else strength(ctx.g, cid)
    ctx.add(InfoCard("kinfolk_flute", "Kinfolk Flute", number, lines=lines))


def _whistle_card(ctx: Ctx, ev: dict) -> InfoCard:
    g = ctx.g
    play = play_at(g, ev.get("play_index"))
    value = play.value if play is not None else ""
    shown = " (%s)" % value if value != "" else ""
    lines = [fit("A lone companion or beast attack%s" % shown, "A lone companion or beast attack")]
    if ev.get("kind") == "whistle_take" and card_of(ctx, ev.get("card")) is not None:
        top = ev.get("card")
        new = None
        try:
            cards = [g.cards[c] for c in play.card_ids] + [g.cards[str(top)]]
            new = g.rules.play_value(g, cards)
        except Exception:
            pass
        gain = " %s → %s" % (value, new) if new is not None else ""
        lines.append(fit("Add the top discard %s?%s" % (ctx.label(top), gain),
                         "Add the top discard %s?" % ctx.label(top)))
    elif ev.get("kind") == "whistle_take":
        lines.append("Add the top discard to it?")
    else:
        lines += ["One other player may add any card", "from hand, except a Jester"]
    return InfoCard("scarlet_whistle", "Scarlet Whistle", value, lines=lines)


def _emblem_card(ctx: Ctx, ev: dict) -> InfoCard:
    if ev.get("kind") == "emblem_place":
        lines = ["Before the mage looks, each other player",
                 fit("may put one hand card on the %s" % ctx.reserve, "may put one hand card on top"),
                 "Once per attack, even for a chained mage"]
    else:
        lines = ["Put one of the other cards you looked at",
                 fit("back on the %s? The rest: discard" % ctx.reserve, "back on top? The rest: discard")]
    return InfoCard("azure_emblem", "Azure Emblem", ev.get("strength", ""), lines=lines)


def _mother_card(ctx: Ctx, ev: dict) -> InfoCard:
    g = ctx.g
    cid = ev.get("card")
    label = ctx.label(cid) if card_of(ctx, cid) is not None else "A card"
    lines = [fit("%s entered corrupted" % label, "A card entered corrupted")]
    if ev.get("kind") == "mother_choice":
        top = " (%s)" % ctx.label(g.discard[0]) if g.discard else ""
        lines += [fit("Banish the top discard%s instead" % top, "Banish the top discard instead"),
                  "of the %s's top?" % ctx.reserve]
    else:
        who = ctx.name(ev.get("player")) if ev.get("player") is not None else "Another player"
        lines += [fit("%s must banish a card from hand" % who, "%s banishes a hand card" % who,
                      "A card from hand is banished"),
                  "instead of the %s's top" % ctx.reserve]
    return InfoCard("mother_corrupt", "Evergreen Mother", strength(g, cid), lines=lines)


@on("decide")
@_guard
def _before_box(ctx: Ctx, ev: dict) -> None:
    """A relic's or the Evergreen Mother's card, right before its box (after the other
    cards of this event, such as the Mage's before the Azure Emblem's); a box asked again
    shows no card."""
    kind = str(ev.get("kind", ""))
    if kind == "flute_add" and not asked_before(ctx, kind) and once(ctx, kind):
        after(ctx, ctx.i, _flute_card(ctx, ev))
    elif kind in ("whistle_add", "whistle_take") and not asked_before(ctx, kind) and once(ctx, "whistle"):
        after(ctx, ctx.i, _whistle_card(ctx, ev))
    elif kind in ("emblem_place", "emblem_keep") and not asked_before(ctx, kind) and once(ctx, "emblem") \
            and ctx.carry.get(EMBLEM_SHOWN) != attack_key(ctx, ev.get("play_index")):
        # once an attack: the solo keep is asked again after each pick of a mage chain
        ctx.carry[EMBLEM_SHOWN] = attack_key(ctx, ev.get("play_index"))
        after(ctx, ctx.i, _emblem_card(ctx, ev))
    elif kind in ("mother_choice", "mother_banish") and once(ctx, "mother:%s" % ev.get("card")):
        after(ctx, ctx.i, _mother_card(ctx, ev))


@on("whistle_take")
@_guard
def _whistle_taken(ctx: Ctx, ev: dict) -> None:
    if not ctx.on("scarlet_whistle") or card_of(ctx, ev.get("card")) is None:
        return
    old = old_value(ctx, decision(ctx.before).get("play_index"))
    gain = "%s → %s" % (old, ev.get("value")) if old is not None else "strength %s" % ev.get("value")
    ctx.line(fit("%s joins: %s" % (ctx.label(ev.get("card")), gain), "%s joins" % ctx.label(ev.get("card"))))


def _m12_redirect(ctx: Ctx, card_id: Any) -> bool:
    return any(e.get("t") == "reserve_redirect" and str(e.get("card")) == str(card_id) for e in ctx.earlier())


def _emblem_note(ctx: Ctx) -> dict:
    """What the Emblem did in the attack being resolved (a note left by another attack is
    dropped)."""
    note = ctx.carry.get(EMBLEM)
    if not isinstance(note, dict) or note.get("at") != attack_key(ctx):
        note = ctx.carry[EMBLEM] = {"at": attack_key(ctx)}
    return note


@on("emblem_place")
@_guard
def _emblem_placed(ctx: Ctx, ev: dict) -> None:
    """A placement is counted, never named (it came from a hidden hand)."""
    key = "m12" if _m12_redirect(ctx, ev.get("card")) else "placed"
    _emblem_note(ctx).setdefault(key, []).append(ev.get("player"))


@on("emblem_keep", "emblem_skip")
@_guard
def _emblem_kept(ctx: Ctx, ev: dict) -> None:
    """Solo: one looked-at card back on the reserve (counted), or none."""
    if ev.get("t") == "emblem_skip":
        kept = "none"
    else:
        kept = "m12" if _m12_redirect(ctx, ev.get("card")) else "one"
    _emblem_note(ctx)["kept"] = kept


def _emblem_line(ctx: Ctx, note: dict) -> str:
    """What the Emblem did, as counts: the cards placed (by whom) or kept go on the reserve
    unseen; the mage's own line tells the pick and the discards."""
    kept = note.get("kept")
    if kept:
        return {"one": "Emblem: 1 card back on the %s" % ctx.reserve, "none": "Emblem: no card kept",
                "m12": "Emblem: kept card corrupted → banished"}.get(kept, "")
    m12 = list(note.get("m12") or [])
    names = [ctx.name(p) for p in list(note.get("placed") or []) + m12]
    if not names:
        return ""
    who = ", ".join(names)
    if m12:
        return fit("Emblem: %s placed; %d corrupted, banished" % (who, len(m12)),
                   "Emblem: %d placed; %d corrupted, banished" % (len(names), len(m12)))
    each = "a card" if len(names) == 1 else "a card each"
    return fit("Emblem: %s put %s on the %s" % (who, each, ctx.reserve), "Emblem: %s placed %s" % (who, each),
               "Emblem: %s placed on the %s" % (count(len(names), "card"), ctx.reserve))


@on(*MAGE_RESULTS)
@_guard
def _emblem_told(ctx: Ctx, ev: dict) -> None:
    """The Emblem's outcome is one line after the mage's own, once the mage's last box is
    done (placements by several players make one line)."""
    if any(e.get("t") == "decide" and e.get("kind") in MAGE_BOXES for e in ctx.later()):
        return
    note = ctx.carry.pop(EMBLEM, None)
    if isinstance(note, dict) and note.get("at") == attack_key(ctx) and ctx.on("azure_emblem"):
        line = _emblem_line(ctx, note)
        if line:
            after(ctx, ctx.i, line)


@on("banish_redirect")
@_guard
def _mother_restored(ctx: Ctx, ev: dict) -> None:
    """One card for an action's restored cards kept out of the banished pile, after the
    card of the step that banished them (counted: they are in the reserve now)."""
    if not once(ctx, "mother_restored"):
        return
    n = len(ctx.earlier("banish_redirect")) + 1 + len(ctx.later("banish_redirect"))
    lines = ["%s would be banished" % count(n, "restored card"),
             "%s under the %s instead" % ("It goes" if n == 1 else "They go", ctx.reserve)]
    card = InfoCard("mother_restored", "Evergreen Mother", lines=lines)
    j = ctx.i
    while j + 1 < len(ctx.events) and ctx.events[j + 1].get("t") == "banish_redirect":
        j += 1
    told = None
    while j + 1 < len(ctx.events) and ctx.events[j + 1].get("t") in BANISHERS:
        j += 1
        told = j
    if told is None:
        ctx.add(card)
    else:
        after(ctx, told, card)


# ---------------------------------------------------------------------------- the Jesters
def _base_jester(ctx: Ctx, ev: dict) -> None:
    g = ctx.g
    name = enemy_label(g)
    lines = [fit("%s loses its immunity" % name, "The enemy loses its immunity"), "for the rest of this fight"]
    before = ctx.before
    if before is not None and g.enemy is not None and "S" in g.enemy.suits:
        try:
            a, b = before.enemy_attack, g.enemy_attack
        except Exception:
            a = b = None
        if a != b:
            lines.append("Earlier ♠ shields count: attack %s → %s" % (a, b))
    lines.append("No damage and no enemy attack this turn")
    if not ctx.solo and ev.get("player") is not None:
        lines.append(fit("%s chooses who goes next" % ctx.name(ev.get("player")), "Choose who goes next"))
    elif not ctx.solo:
        lines.append("Choose who goes next")
    ctx.add(InfoCard("jester", "Jester", lines=lines))


def _claim_jester(ctx: Ctx, ev: dict) -> None:
    myla = fixed_immunity(ctx, tuple(ctx.g.enemy.suits)) if ctx.g.enemy is not None else False
    lines = ["Anyone may claim it and attack now",
             "That attack ignores immunity, not Myla's" if myla else "That attack ignores immunity",
             "Its paladins keep shielding after it", "Play goes on clockwise from the claimer"]
    ctx.add(InfoCard("jester_claim", "Jester", lines=lines))


@on("jester")
@_guard
def _jester(ctx: Ctx, ev: dict) -> None:
    """A Jester played from hand: base (immunity cancelled) or Legacy (claim it)."""
    mode = ev.get("mode")
    if mode is None:
        mode = ctx.g.rules.jester_mode(ctx.g)
    (_claim_jester if mode == "claim" else _base_jester)(ctx, ev)


def _remaining(ctx: Ctx, ev: dict) -> Any:
    remaining = ev.get("remaining")
    return ctx.g.solo_jesters if remaining is None else remaining


def _solo_refresh(ctx: Ctx, ev: dict) -> None:
    g = ctx.g
    out, drawn = len(ev.get("discarded") or ()), len(ev.get("drawn") or ())
    hand = len(g.players[0].hand) if g.players else 0
    if hand >= g.config.max_hand:
        first = "Hand discarded (%d), drew %d back to %d" % (out, drawn, g.config.max_hand)
    else:
        first = "Hand discarded (%d), drew %d: %s empty" % (out, drawn, ctx.reserve)
    remaining = _remaining(ctx, ev)
    lines = [fit(first, "Hand discarded (%d), drew %d" % (out, drawn)), "Jesters left: %s" % remaining]
    if g.config.jesters is None:
        lines.append("Gold: none used · silver: 1 · bronze: 2")
    if g.phase == "suffer" and g.pending_damage:
        lines.append("Now pay the damage: %d" % g.pending_damage)
    ctx.add(InfoCard("solo_jester_refresh", "Jester", remaining, lines=lines))


def _solo_attack(ctx: Ctx, ev: dict) -> None:
    suit = str(ev.get("suit", ""))
    name = ctx.class_title(suit)
    game = then(ctx)
    lines = [fit("The Jester is a %s of strength 8" % name, "The Jester attacks as a %s" % name)]
    if fixed_immunity(ctx, (suit,)):
        lines.append(fit("%s's %s immunity is never ignored" % (enemy_label(game), icons((suit,))),
                         "Myla's immunity is never ignored"))
    else:
        lines.append(fit("Ignores %s's immunity" % enemy_label(game), "Ignores the enemy's immunity"))
    lines += ["Jesters left: %s" % _remaining(ctx, ev), "It is set aside when this enemy falls"]
    ctx.add(InfoCard("solo_jester_attack", "Jester", 8, lines=lines))


@on("solo_jester")
@_guard
def _solo_jester(ctx: Ctx, ev: dict) -> None:
    """Solo: base (a new hand) or Legacy (the Jester attacks as a class, strength 8; an
    older event without its mode still names the class)."""
    attack = ev.get("mode") == "attack" or (ev.get("mode") is None and bool(ev.get("suit")))
    (_solo_attack if attack else _solo_refresh)(ctx, ev)
