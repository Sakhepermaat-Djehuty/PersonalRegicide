"""Info pop-ups: the Missions group (one sub-heading per mission). See docs/INFO_POPUPS.md and app/info.py.

Missions 1 and 4 have no cards of their own, and mission 2's Hydra regrows belongs to the
defeat cards. Each card comes at the event that tells of its step, so the queue keeps the
engine's order: the end-of-turn cards (missions 3, 5, 9 and 10's cleric and bard) after
Damage paid and before Turn, the start-of-turn cards (missions 7, 10, 11 and 12) after
Turn, and a card that stands before a box at the event that asks it. A step that found
nothing to move still gets its card (the "empty" variants, told by the events missing
from the end or the start of a turn; none at a game's start). What a box chose is a line
on the next card, while the box's row is on. Cards going into a hidden hand or the
reserve are never named.

The helpers here serve the Evergreen cards too (``info_evergreen``).
"""
from __future__ import annotations

import functools
import traceback
from typing import Any, Callable, List, Optional, Sequence

from regicide.cards import SUIT_SYMBOL

from . import theme as T

LINE = 40
ERRORS: List[str] = []         # what a handler swallowed (the tests check it stays empty)
# the events a turn ends after: the damage paid (or none due), or the answer to a boon's
# box that followed the damage (Evergreen)
TURN_ENDERS = ("suffer", "no_damage", "zone_match", "zone_match_skip", "close_call_pick")


# ---------------------------------------------------------------------------- helpers
def safe(fn: Callable) -> Callable:
    """A handler that never raises (on the phone a raising builder loses the whole queue):
    what it swallowed goes to ``ERRORS`` and, on the phone, to errors.log."""
    @functools.wraps(fn)
    def run(*args: Any) -> None:
        try:
            fn(*args)
        except Exception:
            ERRORS[:] = ERRORS[-9:] + [traceback.format_exc()]
            _log(fn.__name__)
    return run


def _log(name: str) -> None:
    try:
        from . import store
        if store._is_pythonista():
            store.log_error("Info pop-ups (%s)\n%s" % (name, ERRORS[-1]))
    except Exception:
        pass


def fit(*variants: str) -> str:
    """The first wording that fits on a line (the last one cut to fit)."""
    for text in variants:
        if len(text) <= LINE:
            return text
    return variants[-1][:LINE - 1] + "…"


def num(value: Any, default: int = 0) -> int:
    """An event's number (an older save's event may lack it, or hold something else)."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def count(n: int, word: str) -> str:
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def icons(suits: Sequence[str]) -> str:
    return "".join(SUIT_SYMBOL.get(s, s) for s in suits)


def card_of(ctx: Ctx, card_id: Any) -> Any:
    return ctx.g.cards.get(str(card_id))


def strength(ctx: Ctx, card_id: Any) -> int:
    """A card's strength where it lies (a 2/5 in the zone counts its held value)."""
    card = card_of(ctx, card_id)
    if card is None:
        return 0
    try:
        return int(ctx.g.rules.card_strength(ctx.g, card))
    except Exception:
        return int(getattr(card, "value", 0) or 0)


def total(ctx: Ctx, card_ids: Sequence[Any]) -> int:
    return sum(strength(ctx, c) for c in card_ids)


def classes(ctx: Ctx, card_ids: Sequence[Any]) -> List[str]:
    """The classes of these zone cards, each once (a beast grants none)."""
    out: List[str] = []
    for cid in card_ids:
        card = card_of(ctx, cid)
        if card is None or card.has("beast"):
            continue
        for s in card.suits:
            if s not in out:
                out.append(s)
    return out


def zone_of(ctx: Ctx, ev: dict) -> List[str]:
    """The zone as the event left it (the game's zone for an event without one)."""
    zone = ev.get("zone")
    return [str(c) for c in zone] if isinstance(zone, list) else list(ctx.g.mission_zone)


def enemy_name(ctx: Ctx, card_id: Any = None) -> str:
    g = ctx.g
    if g.enemy is not None and (card_id is None or str(card_id) == g.enemy.card_id):
        return g.enemy.name
    card = card_of(ctx, card_id)
    if card is None:
        return "The enemy" if card_id is None else "the next enemy"
    from regicide.engine import enemy_name as name_of
    return name_of(card, True)


def enemy_line(ctx: Ctx) -> str:
    """"Justicar: attack 17" (the enemy as the action left it)."""
    g = ctx.g
    if g.enemy is None:
        return ""
    return fit("%s: attack %d" % (g.enemy.name, g.enemy_attack), "Enemy attack %d" % g.enemy_attack)


def who(ctx: Ctx, player: Any) -> str:
    return ctx.name(ctx.g.active if player is None else player)


def your(ctx: Ctx, player: Any) -> str:
    return "your" if ctx.solo else "%s's" % who(ctx, player)


def asked_before(ctx: Ctx, kind: str) -> bool:
    """Was the game already waiting on this box (asked again: no second card)?"""
    before = ctx.before
    decision = (getattr(before, "decision", None) or {}) if before is not None else {}
    return decision.get("kind") == kind


def once(ctx: Ctx, key: str) -> bool:
    """True the first time ``key`` is asked for in this build."""
    key = "missions:" + key
    if ctx.state.get(key):
        return False
    ctx.state[key] = True
    return True


def previous(ctx: Ctx) -> str:
    """The type of the event just before the current one."""
    return str(ctx.events[ctx.i - 1].get("t")) if ctx.i > 0 else ""


def end_of_turn(ctx: Ctx) -> Optional[List[dict]]:
    """At the event a turn ends after (``TURN_ENDERS``): the end-of-turn events up to the
    next turn (or the end-of-turn box). None when the turn does not end in this action."""
    if ctx.ev.get("t") not in TURN_ENDERS:
        return None
    out: List[dict] = []
    for e in ctx.later():
        t = e.get("t")
        if t == "turn":
            return out
        if t == "decide":
            resume = e.get("resume")
            if resume not in (None, "end_turn"):
                return None
            out.append(e)
            if resume == "end_turn":
                return out
            continue
        if t in ("defeat", "reveal", "choose_next"):
            return None
        out.append(e)
    return None


def start_of_turn(ctx: Ctx) -> Optional[List[dict]]:
    """At a turn event: the start-of-turn events after it, up to the next turn. None when
    the event starts no new turn (a claimed Jester's attack)."""
    if ctx.ev.get("t") != "turn" or previous(ctx) == "choose_next":
        return None
    out: List[dict] = []
    for e in ctx.later():
        if e.get("t") == "turn":
            break
        out.append(e)
    return out


def until_turn(ctx: Ctx, *types: str) -> List[dict]:
    """The later events of these types before the next turn event."""
    out: List[dict] = []
    for e in ctx.later():
        if e.get("t") == "turn":
            break
        if e.get("t") in types:
            out.append(e)
    return out


def zone_card(ctx: Ctx, row: str, title: str, ev: dict, lines: Sequence[str], **kw: Any) -> bool:
    """A card for a zone step: the strength of the card that joined, top left."""
    return ctx.add(InfoCard(row, title, strength(ctx, ev.get("card")), lines=lines, **kw))


def joins(when: str, what: str, label: str) -> str:
    """"End of turn: reserve top 4♥ joins the zone", shorter when it must be."""
    return fit("%s: %s %s joins the zone" % (when, what, label), "%s: %s %s to the zone" % (when, what, label),
               "%s: %s %s → zone" % (when, what, label), "%s %s joins the zone" % (what[0].upper() + what[1:], label))


def outcome(ctx: Ctx, row: str, *variants: str) -> None:
    """A box's outcome as a line on the next card, while the box's row is on."""
    if ctx.on(row):
        ctx.line(fit(*variants))


# the helpers above come first: importing ``.info`` loads ``info_evergreen``, which takes
# them from this module even when this module is the one being imported
from .info import Ctx, InfoCard, on  # noqa: E402


# ---------------------------------------------------------------------------- the zone cards
@on("zone_add")
@safe
def _zone_add(ctx: Ctx, ev: dict) -> None:
    """A card joins the mission zone: the card of the mission's step."""
    if ctx.evergreen:
        return
    source = str(ev.get("source") or "")
    m = ctx.mission
    if m == 3:
        _m3_zone(ctx, ev)
    elif m == 5:
        _m5_zone(ctx, ev)
    elif m == 7:
        _m7_pilgrim(ctx, ev)
    elif m == 10 and source == "discard":
        _m10_cleric(ctx, ev)
        _m10_bard_empty(ctx)
    elif m == 10:
        _m10_zone(ctx, ev)
    elif m == 12:
        _m12_zone(ctx, ev)


@on(*TURN_ENDERS)
@safe
def _turn_ends(ctx: Ctx, ev: dict) -> None:
    """An end of turn that moved nothing still gets its mission's card (missions 3, 5, 10)."""
    if ctx.evergreen or ctx.mission not in (3, 5, 10):
        return
    seg = end_of_turn(ctx)
    if seg is None:
        return
    adds = [e for e in seg if e.get("t") == "zone_add"]
    if ctx.mission == 3 and not adds:
        _m3_empty(ctx)
    elif ctx.mission == 5 and not adds:
        _m5_empty(ctx)
    elif ctx.mission == 10 and not any(e.get("source") == "discard" for e in adds):
        _m10_cleric_empty(ctx)
        _m10_bard_empty(ctx)


@on("turn")
@safe
def _turn_starts(ctx: Ctx, ev: dict) -> None:
    """A start of turn that moved nothing still gets its mission's card (missions 10, 12)."""
    if ctx.evergreen or ctx.start or ctx.mission not in (10, 12):
        return
    seg = start_of_turn(ctx)
    if seg is None:
        return
    types = [e.get("t") for e in seg]
    if ctx.mission == 10 and not any(e.get("t") == "zone_add" and e.get("source") != "discard" for e in seg):
        _m10_zone_empty(ctx)
    elif ctx.mission == 12 and "zone_add" not in types and "zone_skip" not in types:
        _m12_zone_empty(ctx)


# ---- 3 Lessons in Flames
def _immune_lines(ctx: Ctx, zone: Sequence[str], new: Sequence[str] = ()) -> List[str]:
    suits = classes(ctx, zone)
    if not suits:
        return ["Enemies are immune to every zone class:", "none yet (no classes in the zone)"]
    tail = " (new: %s)" % icons(new) if new else ""
    return ["Enemies are immune to every zone class:", icons(suits) + tail]


def _m3_zone(ctx: Ctx, ev: dict) -> None:
    cid = str(ev.get("card", ""))
    zone = zone_of(ctx, ev)
    new = [s for s in classes(ctx, zone) if s not in classes(ctx, [c for c in zone if c != cid])]
    label = ctx.label(cid)
    lines = [joins("End of turn", "reserve top", label)]
    zone_card(ctx, "m3_zone", "Zone: new immunity", ev, lines + _immune_lines(ctx, zone, new))


def _m3_empty(ctx: Ctx) -> None:
    lines = ["End of turn: reserve empty,", "nothing joins the zone"] + _immune_lines(ctx, ctx.g.mission_zone)
    ctx.add(InfoCard("m3_zone", "Zone: new immunity", lines=lines))


# ---- 5 High and Mighty
def _bonus_line(ctx: Ctx, zone: Sequence[str]) -> str:
    n = total(ctx, zone)
    if not zone:
        return "The zone is empty: no attack bonus"
    return fit("Enemy attack +%d (zone: %s)" % (n, ctx.labels(zone)),
               "Enemy attack +%d (%s in the zone)" % (n, count(len(zone), "card")))


def _m5_zone(ctx: Ctx, ev: dict) -> None:
    label = ctx.label(ev.get("card"))
    lines = [joins("End of turn", "banished top", label), _bonus_line(ctx, zone_of(ctx, ev))]
    zone_card(ctx, "m5_zone", "Zone: enemy stronger", ev, lines)


def _m5_empty(ctx: Ctx) -> None:
    lines = ["End of turn: banished pile empty,", "nothing joins the zone", _bonus_line(ctx, ctx.g.mission_zone)]
    ctx.add(InfoCard("m5_zone", "Zone: enemy stronger", lines=lines))


@on("carry_damage")
@safe
def _m5_carry(ctx: Ctx, ev: dict) -> None:
    """An exact kill's strength carries to the next enemy (it may fall too)."""
    amount = num(ev.get("amount"))
    name = enemy_name(ctx, ev.get("enemy"))
    hp = num(ev.get("hp"))
    max_hp = num(ev.get("max_hp"), hp + amount)
    lines = [fit("Exact kill: %s takes %d" % (name, amount), "Exact kill: the next enemy takes %d" % amount),
             "(the fallen enemy's strength)",
             "Health %d → %d%s" % (max_hp, hp, ": it falls too!" if hp <= 0 else "")]
    ctx.add(InfoCard("m5_carry", "Carry damage", amount, lines=lines, middle=amount,
                     caption=fit("to %s" % name, "to the next enemy")))


# ---- 7 Tales of Rebirth
def _m7_pilgrim(ctx: Ctx, ev: dict) -> None:
    label = ctx.label(ev.get("card"))
    n = strength(ctx, ev.get("card"))
    lines = [fit("Start of turn: %s joins the zone" % label, "%s joins the zone" % label),
             "A card of strength %d entering play" % n, "may banish it from the zone",
             "On defeat: %s → discard" % count(total(ctx, zone_of(ctx, ev)), "reserve card")]
    zone_card(ctx, "m7_pilgrim", "Pilgrim arrives", ev, lines)


def _m7_match(ctx: Ctx, ev: dict) -> None:
    pilgrims = [str(c) for c in ev.get("options") or ()]
    entering = ev.get("entering")
    n = strength(ctx, pilgrims[0]) if pilgrims else ""
    found, label = ctx.labels(pilgrims, " / "), ctx.label(entering)
    lines = [fit("%s matches %s in the zone" % (label, found), "%s matches %s" % (label, found),
                 "A card entering play matches a pilgrim"),
             "Banish the pilgrim from the zone?"]
    ctx.add(InfoCard("m7_match", "Pilgrim match", n, lines=lines))


@on("pilgrim_banish", "pilgrim_skip")
@safe
def _m7_answer(ctx: Ctx, ev: dict) -> None:
    if ev.get("t") == "pilgrim_skip":
        outcome(ctx, "m7_match", "The pilgrim stays in the zone")
        return
    label = ctx.label(ev.get("pilgrim"))
    outcome(ctx, "m7_match", "%s banished %s" % (who(ctx, ev.get("player")), label), "%s is banished" % label)


# ---- 8 Winds of Chaos
@on("zone_cleared")
@safe
def _m8_filled(ctx: Ctx, ev: dict) -> None:
    """A 10 built into the zone fills it: the card before the banish box."""
    if ctx.evergreen or ctx.mission != 8 or ev.get("to", "discard") != "discard":
        return
    n = len(ev.get("cards") or ())
    lines = ["A 10 completes the zone (%s):" % count(n, "card"), "it goes to the discard pile",
             "Banish any discards you choose;", "the rest heal under the reserve", "No more zone moves this mission"]
    ctx.add(InfoCard("m8_filled", "Zone filled!", 10, lines=lines))


# ---- 9 Hope From Ashes
def _tops(ctx: Ctx, tops: Sequence[Any]) -> str:
    return " ".join(ctx.label(t) if t else "–" for t in tops)


def _m9_piles(ctx: Ctx, ev: dict) -> None:
    g = ctx.g
    try:
        tops = g.rules.pile_tops(g)
    except Exception:
        tops = []
    if ctx.solo:
        lines = ["End of turn: banish a hand card to rescue", "a pile's top to the discard pile,"]
    else:
        name = who(ctx, ev.get("player"))
        lines = [fit("End of turn: %s may banish a hand card" % name, "%s may banish a hand card" % name),
                 "to rescue a pile's top to the discard,"]
    lines.append("or every pile's top goes to its bottom")
    if tops:
        lines.append(fit("Pile tops: %s" % _tops(ctx, tops)))
    ctx.add(InfoCard("m9_piles", "Captured piles", lines=lines))


@on("pile_rescue", "pile_rotate")
@safe
def _m9_answer(ctx: Ctx, ev: dict) -> None:
    if ev.get("t") == "pile_rotate":
        outcome(ctx, "m9_piles", "Piles rotated: tops %s" % _tops(ctx, ev.get("tops") or ()), "The piles rotated")
        return
    lost, rescued = ctx.label(ev.get("card")), ctx.label(ev.get("rescued"))
    outcome(ctx, "m9_piles", "%s banished %s: %s rescued" % (who(ctx, ev.get("player")), lost, rescued),
            "%s rescued to the discard pile" % rescued)


# ---- 10 Pride to Fall
def _m10_bonus(ctx: Ctx, zone: Sequence[str]) -> str:
    enemy = ctx.g.enemy
    double = ", then ×2 (warrior enemy)" if enemy is not None and "C" in enemy.suits else ""
    return "Enemy attack +%d%s" % (total(ctx, zone), double)


def _m10_zone(ctx: Ctx, ev: dict) -> None:
    label = ctx.label(ev.get("card"))
    lines = [joins("Start of turn", "reserve top", label), _m10_bonus(ctx, zone_of(ctx, ev)), enemy_line(ctx)]
    zone_card(ctx, "m10_zone", "Zone: enemy stronger", ev, lines)


def _m10_zone_empty(ctx: Ctx) -> None:
    lines = ["Start of turn: reserve empty,", "nothing joins the zone", _m10_bonus(ctx, ctx.g.mission_zone)]
    ctx.add(InfoCard("m10_zone", "Zone: enemy stronger", lines=lines))


def _enemy_has(ctx: Ctx, suit: str) -> bool:
    enemy = ctx.g.enemy
    return enemy is not None and suit in enemy.suits


def _m10_cleric(ctx: Ctx, ev: dict) -> None:
    cid = ev.get("card")
    lines = ["End of turn: the corrupted cleric takes",
             fit("the top discard (%s) into the zone" % ctx.label(cid), "the top discard into the zone"),
             "Enemy attack +%d (zone %d)" % (strength(ctx, cid), total(ctx, zone_of(ctx, ev)))]
    zone_card(ctx, "m10_cleric", "Cleric enemy", ev, lines)


def _m10_cleric_empty(ctx: Ctx) -> None:
    if not _enemy_has(ctx, "H"):
        return
    lines = ["End of turn: the corrupted cleric takes", "the top discard into the zone:",
             "Discard pile empty: nothing moves"]
    ctx.add(InfoCard("m10_cleric", "Cleric enemy", lines=lines))


def _m10_bard(ctx: Ctx, ev: dict) -> None:
    if ctx.solo:
        first = "End of turn: put a hand card in the zone"
    else:
        name = who(ctx, ev.get("player"))
        first = fit("End of turn: %s puts a hand card in the zone" % name, "%s puts a hand card in the zone" % name)
    ctx.add(InfoCard("m10_bard", "Bard enemy", lines=[first, "Enemy attack + its strength"]))


def _m10_bard_empty(ctx: Ctx) -> None:
    """A bard enemy at an end of turn that asks for no hand card: the hand was empty."""
    if not _enemy_has(ctx, "D") or any(e.get("kind") == "zone_feed" for e in until_turn(ctx, "decide")):
        return
    lines = ["End of turn: the corrupted bard wants", "a hand card for the zone:", "Hand empty: nothing moves"]
    ctx.add(InfoCard("m10_bard", "Bard enemy", lines=lines))


@on("zone_feed")
@safe
def _m10_answer(ctx: Ctx, ev: dict) -> None:
    if ctx.evergreen or ctx.mission != 10:
        return
    label = ctx.label(ev.get("card"))
    name = who(ctx, ev.get("player"))
    outcome(ctx, "m10_bard", "%s put %s in the zone: attack +%d" % (name, label, strength(ctx, ev.get("card"))),
            "%s put %s in the zone" % (name, label))


# ---- 11 Descent Into Darkness
BEAST_EFFECTS = {"C": "top discard %s is banished", "S": "reserve top %s is discarded"}


def _beast_steps(ctx: Ctx) -> tuple:
    """What follows a beast's reveal: its effect, its box, a reshuffle."""
    effect, box, reshuffle = None, None, False
    for e in ctx.later():
        t = e.get("t")
        if t in ("turn", "beast_reveal"):
            break
        if t == "beast_effect" and effect is None:
            effect = e
        elif t == "decide" and e.get("kind") in ("beast_discard", "beast_banish"):
            box = e
        elif t == "beast_reshuffle":
            reshuffle = True
    return effect, box, reshuffle


def _attack_before(ctx: Ctx, effect: dict) -> Optional[int]:
    """The enemy's attack before a beast moved this card (the tops of the discard and
    banished piles feed mission 11's enemies)."""
    g = ctx.g
    moved, to = str(effect.get("moved", "")), effect.get("to")
    discard, banished = list(g.discard), list(g.banished)
    if to == "discard" and discard[:1] == [moved]:
        discard = discard[1:]
    if to == "banished" and banished[-1:] == [moved]:
        banished = banished[:-1]
    if effect.get("suit") == "C":
        discard = [moved] + discard
    try:
        rules = g.rules
        now = rules.top_card_strength(g, g.discard, False) + rules.top_card_strength(g, g.banished, True)
        then = rules.top_card_strength(g, discard, False) + rules.top_card_strength(g, banished, True)
        return g.enemy_attack + then - now
    except Exception:
        return None


def _beast_enemy_lines(ctx: Ctx, effect: dict) -> List[str]:
    g = ctx.g
    if g.enemy is None:
        return []
    old, new = _attack_before(ctx, effect), g.enemy_attack
    try:
        immune = icons(g.rules.immune_suits(g))
    except Exception:
        immune = ""
    attack = "attack %d" % new if old is None or old == new else "attack %d → %d" % (old, new)
    line = "%s: %s" % (g.enemy.name, attack)
    if immune and len(line + " · immune " + immune) <= LINE:
        return [line + " · immune " + immune]
    return [fit(line, "Enemy " + attack)] + (["Immune to %s" % immune] if immune else [])


@on("beast_reveal")
@safe
def _m11_beast(ctx: Ctx, ev: dict) -> None:
    """Start of turn: a beast is revealed and its class acts (Cleric and Bard ask a hand card)."""
    suit = str(ev.get("suit", ""))
    effect, box, reshuffle = _beast_steps(ctx)
    lines: List[str] = []
    if suit in BEAST_EFFECTS and effect is not None:
        what = BEAST_EFFECTS[suit] % ctx.label(effect.get("moved"))
        lines.append(fit("Start of turn: " + what, what[0].upper() + what[1:]))
        lines += _beast_enemy_lines(ctx, effect)
    elif box is not None:
        verb = "discard" if suit == "H" else "banish"
        if ctx.solo:
            lines.append("Start of turn: %s a hand card" % verb)
        else:
            name = who(ctx, box.get("player", ev.get("player")))
            lines.append(fit("Start of turn: %s %ss a hand card" % (name, verb), "%s %ss a hand card" % (name, verb)))
    else:
        lines.append("Nothing to move: no effect")
    if reshuffle:
        lines.append("All four out: the beasts reshuffle")
    name = ctx.class_title(suit) if suit else ""
    ctx.add(InfoCard("m11_beast", "Beast: %s" % name if name else "Beast", icon=suit or None, lines=lines,
                     edge=T.SUIT_COLOR.get(suit, "")))


@on("beast_effect")
@safe
def _m11_answer(ctx: Ctx, ev: dict) -> None:
    """A Cleric or Bard beast's hand card (the answer to its box) is a line."""
    if ctx.earlier("beast_reveal"):
        return
    verb = "banished" if ev.get("to") == "banished" else "discarded"
    name, label = who(ctx, ev.get("player")), ctx.label(ev.get("moved"))
    old, new = _attack_before(ctx, ev), ctx.g.enemy_attack if ctx.g.enemy is not None else None
    change = ": attack %d → %d" % (old, new) if old is not None and new is not None and old != new else ""
    outcome(ctx, "m11_beast", "%s %s %s%s" % (name, verb, label, change), "%s %s %s" % (name, verb, label))


@on("beast_reshuffle")
@safe
def _m11_reshuffle(ctx: Ctx, ev: dict) -> None:
    if not ctx.earlier("beast_reveal"):
        outcome(ctx, "m11_beast", "All four out: the beasts reshuffle")


# ---- 12 Decay to Growth
def _m12_lines(ctx: Ctx, zone: Sequence[str]) -> List[str]:
    suits = icons(classes(ctx, zone))
    return ["Enemy attack +%d from the zone" % total(ctx, zone),
            "Immune to the zone's classes: %s" % suits if suits else "No classes in the zone yet"]


def _m12_zone(ctx: Ctx, ev: dict) -> None:
    label = ctx.label(ev.get("card"))
    lines = [joins("Start of turn", "banished top", label)] + _m12_lines(ctx, zone_of(ctx, ev)) + [enemy_line(ctx)]
    zone_card(ctx, "m12_zone", "Zone: stronger, immune", ev, lines)


def _m12_zone_empty(ctx: Ctx) -> None:
    lines = ["Start of turn: banished pile empty,", "nothing joins the zone"] + _m12_lines(ctx, ctx.g.mission_zone)
    ctx.add(InfoCard("m12_zone", "Zone: stronger, immune", lines=lines))


# ---------------------------------------------------------------------------- the boxes
@on("decide")
@safe
def _box(ctx: Ctx, ev: dict) -> None:
    """A mission step that asks a box gets its card right before it (once an action; a box
    asked again shows none)."""
    if ctx.evergreen:
        return
    kind = str(ev.get("kind", ""))
    if kind == "pilgrim_banish" and not asked_before(ctx, kind) and once(ctx, kind):
        _m7_match(ctx, ev)
    elif kind == "pile_rescue" and not asked_before(ctx, kind) and once(ctx, kind):
        _m9_piles(ctx, ev)
    elif kind == "zone_feed" and ctx.mission == 10 and not asked_before(ctx, kind) and once(ctx, kind):
        _m10_bard(ctx, ev)
