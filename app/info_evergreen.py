"""Info pop-ups: the Evergreen group (locations, banes, boons). See docs/INFO_POPUPS.md and app/info.py.

Each card comes at the event that tells of its step, in the engine's order: the
location's end-of-turn card first (Shrine, Cave and its collapse, Forest, Hills), then
banes 10, 12 and 23, before Turn; after Turn the Lake, then banes 16 and 22; A Close Call
and Selfless Rescue after Damage paid; Eye-Level Sticks and Squad of Siblings before
their boxes as the attack forms; Tread Carefully, Precision Strike and Restored Arrows at
a kill, Absorbtion after its clean-up. A card that stands before a box comes at the event
that asks it, and what the box chose is a line on the next card, while its row is on.
Cards going into a hidden hand or the reserve are never named (A Close Call's cards and
its pick). The defeat steps' choices (Precision Strike, Restored Arrows) are Clean-up's lines.

A location's zone card is told from the banes' by where it comes: right after the damage
paid (or the boon's answer after it) at the end of a turn, right after Turn for the Lake.
"""
from __future__ import annotations

from typing import Any

from .info import Ctx, InfoCard, on
from .info_missions import (TURN_ENDERS, asked_before, classes, count, enemy_name, fit, icons, joins, num, once,
                            outcome, previous, safe, start_of_turn, strength, total, until_turn, who, your, zone_card,
                            zone_of)


def location(ctx: Ctx) -> str:
    return str((ctx.g.config.extra.get("evergreen") or {}).get("location", ""))


def bane(ctx: Ctx, n: int) -> bool:
    banes = (ctx.g.config.extra.get("evergreen") or {}).get("banes", [])
    return n in [num(b) for b in banes]


def play_value(ctx: Ctx, ev: dict) -> Any:
    """The strength of the attack a box is about (its ``play_index``)."""
    try:
        return ctx.g.plays[int(ev.get("play_index", -1))].value
    except (IndexError, TypeError, ValueError):
        return ""


# ---------------------------------------------------------------------------- the zone steps
@on("zone_add")
@safe
def _zone_add(ctx: Ctx, ev: dict) -> None:
    """A card joins the zone: the location's step, bane 10's, or bane 23's."""
    if not ctx.evergreen:
        return
    source = str(ev.get("source") or "")
    loc = location(ctx)
    before = previous(ctx)
    if source == "discard":
        _bane10(ctx, ev)
    elif loc == "E" and before == "turn":
        _lake(ctx, ev)
        _dread_empty(ctx)
    elif loc in ("A", "B") and source in ("reserve", "") and before in TURN_ENDERS:
        (_shrine if loc == "A" else _cave)(ctx, ev)
    elif loc in ("C", "D") and source in ("banished", ""):
        (_forest if loc == "C" else _hills)(ctx, ev)
    elif before == "poison_skip":
        label = ctx.label(ev.get("card"))
        outcome(ctx, "bane23", "No discard: reserve top %s joins the zone" % label,
                "Reserve top %s joins the zone" % label)
    elif bane(ctx, 23):
        _bane23_hand_empty(ctx, ev)


def _shrine(ctx: Ctx, ev: dict) -> None:
    suits = icons(classes(ctx, zone_of(ctx, ev)))
    lines = [joins("End of turn", "reserve top", ctx.label(ev.get("card"))),
             "Enemies are immune to the zone classes:", suits or "none yet (no classes in the zone)"]
    zone_card(ctx, "shrine", "Shrine", ev, lines)


def _cave(ctx: Ctx, ev: dict) -> None:
    zone = total(ctx, zone_of(ctx, ev))
    base = ctx.g.enemy.attack if ctx.g.enemy is not None else 0
    lines = [joins("End of turn", "reserve top", ctx.label(ev.get("card"))),
             "Zone %d of %d: at %d or more" % (zone, base, base), "the cave collapses"]
    zone_card(ctx, "cave", "Cave", ev, lines)


@on("zone_cleared")
@safe
def _cave_collapse(ctx: Ctx, ev: dict) -> None:
    """The Cave's zone reached the enemy's base strength: zone and discard pile banished."""
    if not ctx.evergreen or location(ctx) != "B" or ev.get("to") != "banish":
        return
    zone = total(ctx, ev.get("cards") or ())
    base = ctx.g.enemy.attack if ctx.g.enemy is not None else 0
    spilled = until_turn(ctx, "discard_banished")
    n = len(spilled[0].get("cards") or ()) if spilled else 0
    lines = [fit("The zone (%d) reached %s's base" % (zone, enemy_name(ctx)),
                 "The zone (%d) reached the enemy's base" % zone)]
    if n:
        lines += ["strength %d: the zone and the whole" % base, "discard pile (%s) are banished" % count(n, "card")]
    else:
        lines += ["strength %d: the zone is banished" % base, "(the discard pile is empty)"]
    ctx.add(InfoCard("cave_collapse", "Cave collapses", zone, lines=lines))


def _forest(ctx: Ctx, ev: dict) -> None:
    lines = [joins("End of turn", "banished top", ctx.label(ev.get("card"))),
             "Enemy attack +%d" % total(ctx, zone_of(ctx, ev))]
    zone_card(ctx, "forest", "Forest", ev, lines)


def _hills(ctx: Ctx, ev: dict) -> None:
    damage = total(ctx, zone_of(ctx, ev))
    if until_turn(ctx, "team_damage_prevented"):
        follows = "A Guardian prevents the team damage"
    elif damage > 0:
        follows = "Team damage %d follows" % damage
    else:
        follows = "No team damage (the zone is 0)"
    lines = [joins("End of turn", "banished top", ctx.label(ev.get("card"))), follows]
    zone_card(ctx, "hills", "Hills", ev, lines)


def _lake(ctx: Ctx, ev: dict) -> None:
    label = ctx.label(ev.get("card"))
    what = label if ev.get("source") == "pilgrims" else "reserve top %s" % label
    lines = [fit("Start of turn: %s joins the zone" % what, "%s joins the zone" % what),
             "On defeat: 1 reserve card is banished", "per zone card (%d now)" % len(zone_of(ctx, ev))]
    zone_card(ctx, "lake", "Lake", ev, lines)


# ---------------------------------------------------------------------------- the banes
def _bane10(ctx: Ctx, ev: dict) -> None:
    label = ctx.label(ev.get("card"))
    lines = ["End of turn: the enemy is a cleric,",
             fit("so the top discard (%s) joins the zone" % label, "so the top discard joins the zone")]
    zone_card(ctx, "bane10", "Poisonous Clerics", ev, lines)


def _bane12(ctx: Ctx, ev: dict) -> None:
    if ctx.solo:
        second = "so put a card from your hand in the zone"
    else:
        name = who(ctx, ev.get("player"))
        second = fit("so %s puts a hand card in the zone" % name, "%s puts a hand card in the zone" % name)
    ctx.add(InfoCard("bane12", "Duplicitous Bards", lines=["End of turn: the enemy is a bard,", second]))


@on("zone_feed")
@safe
def _bane12_answer(ctx: Ctx, ev: dict) -> None:
    if ctx.evergreen:
        name, label = who(ctx, ev.get("player")), ctx.label(ev.get("card"))
        outcome(ctx, "bane12", "%s put %s in the zone" % (name, label))


@on("zone_absorb")
@safe
def _bane14(ctx: Ctx, ev: dict) -> None:
    """Absorbtion: the killing attack stays in the zone (after the clean-up)."""
    cards = [str(c) for c in ev.get("cards") or ()]
    lines = [fit("The killing attack (%s) joins the zone," % ctx.labels(cards), "The killing attack joins the zone,"),
             "not the discard pile · zone now %d" % total(ctx, zone_of(ctx, ev))]
    ctx.add(InfoCard("bane14", "Absorbtion", lines=lines))


@on("discard_banished")
@safe
def _bane15(ctx: Ctx, ev: dict) -> None:
    """Tread Carefully: a non-exact kill banishes the whole discard pile (the Cave's spill
    follows its zone instead)."""
    if not ctx.evergreen or not bane(ctx, 15) or previous(ctx) == "zone_cleared":
        return
    n = len(ev.get("cards") or ())
    lines = ["Not exact: the whole discard pile (%d)" % n, "is banished before the location's steps"]
    ctx.add(InfoCard("bane15", "Tread Carefully", lines=lines))


@on("bane")
@safe
def _bane_start(ctx: Ctx, ev: dict) -> None:
    """Banes 16 and 22 at the start of a turn."""
    n = num(ev.get("n"))
    label = ctx.label(ev.get("card"))
    if n == 16:
        lines = [fit("Start of turn: the top discard (%s)" % label, "Start of turn: the top discard"), "is banished"]
        ctx.add(InfoCard("bane16", "Lingering Dread", lines=lines))
    elif n == 22:
        _dread_empty(ctx)
        lines = [fit("Start of turn: the reserve top (%s)" % label, "Start of turn: the reserve top"),
                 "goes to the discard pile"]
        ctx.add(InfoCard("bane22", "The Fiery Crucible", lines=lines))


@on("turn")
@safe
def _turn_starts(ctx: Ctx, ev: dict) -> None:
    """Bane 16 with no discard to banish still gets its card (after the Lake's, if any)."""
    if ctx.evergreen and not ctx.start and start_of_turn(ctx) is not None and not until_turn(ctx, "zone_add", "bane"):
        _dread_empty(ctx)


def _dread_empty(ctx: Ctx) -> None:
    """Lingering Dread found the discard pile empty at this start of turn (one card a turn)."""
    if ctx.start or not bane(ctx, 16):
        return
    turn = max([j for j in range(ctx.i + 1) if ctx.events[j].get("t") == "turn"] or [-1])
    for e in ctx.events[turn + 1:]:
        if e.get("t") == "turn":
            break
        if e.get("t") == "bane" and num(e.get("n")) == 16:
            return
    if turn < 0 or not once(ctx, "dread:%d" % turn):
        return
    lines = ["Start of turn: top discard is banished", "Discard pile empty: nothing moves"]
    ctx.add(InfoCard("bane16", "Lingering Dread", lines=lines))


def _bane21(ctx: Ctx, ev: dict) -> None:
    player = ev.get("player")
    if ctx.solo:
        lines = ["Your attack holds a card of strength 8+:", "discard a card from your hand"]
    else:
        name = who(ctx, player)
        lines = [fit("%s's attack holds a card of strength 8+:" % name, "%s's attack has a card of 8+:" % name,
                     "The attack holds a card of strength 8+:"),
                 fit("%s discards a card from hand" % name, "Discard a card from hand")]
    ctx.add(InfoCard("bane21", "Eye-Level Sticks", play_value(ctx, ev), lines=lines))


@on("attack_discard")
@safe
def _bane21_answer(ctx: Ctx, ev: dict) -> None:
    name, label = who(ctx, ev.get("player")), ctx.label(ev.get("card"))
    outcome(ctx, "bane21", "%s discarded %s (Eye-Level Sticks)" % (name, label), "%s discarded %s" % (name, label))


def _bane23(ctx: Ctx, ev: dict) -> None:
    if ctx.solo:
        first = "End of turn: discard a card from hand,"
    else:
        name = who(ctx, ev.get("player"))
        first = fit("End of turn: %s may discard a hand card," % name, "%s may discard a hand card," % name)
    ctx.add(InfoCard("bane23", "Choose Your Poison", lines=[first, "or the reserve top joins the zone"]))


def _bane23_hand_empty(ctx: Ctx, ev: dict) -> None:
    """No hand card to discard: the reserve top joined the zone with no box."""
    label = ctx.label(ev.get("card"))
    lines = ["End of turn: no hand card to discard,",
             fit("so reserve top %s joins the zone" % label, "so the reserve top joins the zone")]
    zone_card(ctx, "bane23", "Choose Your Poison", ev, lines)


@on("poison", "poison_skip")
@safe
def _bane23_answer(ctx: Ctx, ev: dict) -> None:
    if ev.get("t") == "poison":
        name, label = who(ctx, ev.get("player")), ctx.label(ev.get("card"))
        outcome(ctx, "bane23", "%s discarded %s (Choose Your Poison)" % (name, label),
                "%s discarded %s" % (name, label))
    elif not (ctx.later() and ctx.later()[0].get("t") == "zone_add"):
        outcome(ctx, "bane23", "No discard; the reserve is empty")


# ---------------------------------------------------------------------------- the boons
def _boon30(ctx: Ctx, ev: dict) -> None:
    options = [str(c) for c in ev.get("options") or ()]
    n = strength(ctx, options[0]) if options else ""
    whose = your(ctx, ev.get("player"))
    if len(options) > 1:
        first = fit("Zone cards %s match %s attack (%s)" % (ctx.labels(options), whose, n),
                    "Zone cards of strength %s match the attack" % n)
        second = "Move one to the discard pile?"
    else:
        first = fit("Zone card %s matches %s attack (%s)" % (ctx.labels(options), whose, n),
                    "Zone card %s matches the attack (%s)" % (ctx.labels(options), n))
        second = "Move it to the discard pile?"
    ctx.add(InfoCard("boon30", "Squad of Siblings", play_value(ctx, ev), lines=[first, second]))


def _zone_answer(ctx: Ctx, ev: dict, row: str, why: str) -> None:
    if ev.get("t", "").endswith("_skip"):
        outcome(ctx, row, "The zone card stays (%s)" % why, "The zone card stays")
        return
    label = ctx.label(ev.get("card"))
    outcome(ctx, row, "%s: zone → discard pile (%s)" % (label, why), "%s: zone → discard pile" % label)


@on("zone_sibling", "zone_sibling_skip")
@safe
def _boon30_answer(ctx: Ctx, ev: dict) -> None:
    _zone_answer(ctx, ev, "boon30", "Squad of Siblings")


def _boon31(ctx: Ctx, ev: dict) -> None:
    n = strength(ctx, ev.get("matched") or (ev.get("options") or [None])[0])
    name = who(ctx, ev.get("player"))
    lines = [fit("%s discarded a %d; the zone holds a %d" % (name, n, n),
                 "Discarded a %d; the zone holds a %d" % (n, n)),
             "Move that zone card to the discard pile?"]
    ctx.add(InfoCard("boon31", "Selfless Rescue", n, lines=lines))


@on("zone_match", "zone_match_skip")
@safe
def _boon31_answer(ctx: Ctx, ev: dict) -> None:
    _zone_answer(ctx, ev, "boon31", "Selfless Rescue")


def _boon32(ctx: Ctx, ev: dict) -> None:
    whose = your(ctx, ev.get("player"))
    lines = ["Exact kill: put a zone card or the top", fit("discard into %s hand" % whose, "discard into a hand")]
    ctx.add(InfoCard("boon32", "Precision Strike", lines=lines))


def _boon33(ctx: Ctx, ev: dict) -> None:
    name = who(ctx, ev.get("player"))
    first = "Exact kill: you may put a banished card" if ctx.solo else fit(
        "Exact kill: %s may put a banished card" % name, "%s may put a banished card" % name)
    ctx.add(InfoCard("boon33", "Restored Arrows", lines=[first, "under the reserve"]))


@on("suffer")
@safe
def _boon35(ctx: Ctx, ev: dict) -> None:
    """A Close Call (its event comes before the damage paid; its card after it)."""
    if not ctx.evergreen or previous(ctx) != "close_call":
        return
    damage = num(ev.get("damage"))
    lines = ["Paid exactly %d: the discarded cards go" % damage, "under the reserve, not the discard pile"]
    queue = (ctx.g.extra or {}).get("suffer_queue") or []
    if any(e.get("kind") == "close_call" for e in ctx.later("decide")) or "close_call" in queue:
        if ctx.solo:
            lines.append("Now put a discard on top of the reserve")
        else:
            name = who(ctx, ev.get("player"))
            lines.append(fit("%s puts a discard on top of the reserve" % name,
                             "Then a discard goes on top of the reserve"))
    else:
        lines.append("No discards to put on the reserve")
    ctx.add(InfoCard("boon35", "A Close Call", damage, lines=lines))


@on("close_call_pick")
@safe
def _boon35_answer(ctx: Ctx, ev: dict) -> None:
    outcome(ctx, "boon35", "A discard went on top of the reserve")


# ---------------------------------------------------------------------------- the boxes
BOXES = {"zone_feed": _bane12, "attack_discard": _bane21, "poison": _bane23, "zone_sibling": _boon30,
         "zone_match": _boon31, "precision_strike": _boon32, "restored_arrows": _boon33}


@on("decide")
@safe
def _box(ctx: Ctx, ev: dict) -> None:
    """A bane or boon that asks a box gets its card right before it (once an action; a box
    asked again shows none)."""
    kind = str(ev.get("kind", ""))
    if ctx.evergreen and kind in BOXES and not asked_before(ctx, kind) and once(ctx, kind):
        BOXES[kind](ctx, ev)
