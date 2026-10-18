"""Info pop-ups: the Classes group (IMMUNITY, each class, Damage). See docs/INFO_POPUPS.md and app/info.py.

One card per class in the attack, in the engine's power order (its ``power`` events). The
Mage, Druid, Chanter and Reaver cards stand before their boxes; what was chosen there is one
line on the next card shown (the owner's ruling: no result cards). The Warrior card carries
the damage at the ``damage`` event; with no unblocked Warrior (or its row off) the Damage
card takes that slot. Paladin and Guardian follow the damage when the enemy survives, and
show nothing on a killing blow (the owner's ruling). A class the enemy is immune to shows
its own card in "would" form, stamped IMMUNITY. The first card of an attack carries its
formation line ("Kinfolk 3♣ 3♠ = 6").

Hidden information stays hidden: cards drawn, dealt to hands or put in the reserve are
counted, never named. Lines are 40 characters at most; a card's own lines make room for the
outcome lines waiting for it (the least needed go first).
"""
from __future__ import annotations

import functools
import traceback
from typing import Any, Dict, List, Optional, Sequence

from regicide.cards import BASIC_SUITS, SUIT_SYMBOL

from .info import MAX_LINES, MAX_LINES_MIDDLE, Ctx, InfoCard, on

ROW_OF = {"M": "mage", "U": "druid", "H": "cleric", "D": "bard", "T": "chanter", "R": "reaver",
          "C": "warrior", "S": "paladin", "G": "guardian"}
AFTER_DAMAGE = "classes_after_damage"      # the deferred slot of the Paladin and Guardian cards
LINE = 40
STRENGTH_KEYS = {"play": "value", "add_to_play": "value", "mage_pick": "value", "whistle_take": "value",
                 "declare": "attack", "power": "value"}
MAGE_RESULTS = ("mage_pick", "mage_skip", "emblem_keep", "emblem_skip", "discard_order", "discard_top")
MAGE_BOXES = ("emblem_keep", "discard_order", "discard_top")
IGNORE_FLAGS = (("corrupted", "corrupted"), ("restored", "restored"), ("ignores_immunity", "Evergreen"))
CARRY_KEYS = ("cls_mage", "cls_mage_emblem", "cls_druid", "cls_chanter")
ERRORS: List[str] = []                     # what a handler swallowed (the tests check it stays empty)


def _safe(fn):
    """A handler that never raises (on the phone a raising builder loses the whole queue):
    what it swallowed goes to ``ERRORS`` and, on the phone, to errors.log."""
    @functools.wraps(fn)
    def run(ctx: Ctx, ev: dict) -> None:
        try:
            fn(ctx, ev)
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


# ---------------------------------------------------------------------------- helpers
def _fit(*variants: str) -> str:
    """The first wording that fits on a line (the last one cut to fit)."""
    for text in variants:
        if len(text) <= LINE:
            return text
    return variants[-1][:LINE - 1] + "…"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _attr(obj: Any, name: str, default: Any = 0) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _call(obj: Any, name: str, *args: Any, default: Any = None) -> Any:
    fn = getattr(obj, name, None)
    if fn is None:
        return default
    try:
        return fn(*args)
    except Exception:
        return default


def _was(ctx: Ctx) -> Any:
    """The game as the attack met it: the snapshot before the action, else the game after."""
    return ctx.before if ctx.before is not None else ctx.g


def _paused_play(ctx: Ctx) -> Any:
    """The attack the snapshot was resolving (its decision's play), or its last play."""
    gs = _was(ctx)
    plays = list(getattr(gs, "plays", None) or [])
    if not plays:
        return None
    idx = (getattr(gs, "decision", None) or {}).get("play_index")
    try:
        return plays[int(idx)] if idx is not None else plays[-1]
    except (IndexError, TypeError, ValueError):
        return plays[-1]


def _strength(ctx: Ctx) -> Any:
    """The attack's strength now: the last value this action gave it (the play, a card
    added, a declaration, a power), else the paused attack's."""
    for ev in reversed(ctx.events[:ctx.i + 1]):
        key = STRENGTH_KEYS.get(str(ev.get("t")))
        if key is None or ev.get(key) is None or ev.get("forecast"):
            continue
        if ev.get("t") == "play" and ev.get("kind") == "jester":
            continue
        return _int(ev[key])
    play = _paused_play(ctx)
    return play.value if play is not None else ""


def _attacker(ctx: Ctx) -> int:
    for ev in reversed(ctx.events[:ctx.i + 1]):
        if ev.get("t") == "play" and ev.get("player") is not None:
            return _int(ev["player"])
    return _int(getattr(_was(ctx), "active", 0))


def _attack_cards(ctx: Ctx) -> List[str]:
    """The ids in the attack being resolved: this action's play (or the paused one) and
    the cards added to it since."""
    ids: Optional[List[str]] = None
    added: List[str] = []
    for ev in ctx.events[:ctx.i + 1]:
        if ev.get("t") == "play":
            ids, added = [str(c) for c in ev.get("cards") or []], []
        elif ev.get("t") == "add_to_play":
            added.extend(str(c) for c in ev.get("cards") or [])
    if ids is None:
        play = _paused_play(ctx)
        ids = [str(c) for c in play.card_ids] if play is not None else []
    return ids + [c for c in added if c not in ids]


def _jester_attack(ctx: Ctx) -> bool:
    """A Jester's attack: the Legacy solo Jester, or the attack of a claimed Jester."""
    claimed = bool((getattr(ctx.before, "extra", None) or {}).get("jester_attack"))
    for ev in ctx.events[:ctx.i + 1]:
        if ev.get("t") == "play":
            return ev.get("kind") == "jester_attack" or claimed
    return claimed


def _kill(ctx: Ctx) -> bool:
    """The action's damage felled the enemy (a defeat may wait for a box first)."""
    return ctx.killed or any(e.get("t") == "damage" and _int(e.get("hp"), 1) <= 0 for e in ctx.events)


def _card_suits(gs: Any, card: Any) -> tuple:
    suits = _call(gs.rules, "card_suits", gs, card, default=()) or ()
    return tuple(suits) + tuple(card.suits)


def _later_box(ctx: Ctx, kinds: Sequence[str]) -> bool:
    """Does this action end on one of these boxes (the step goes on in a later action)?"""
    return any(e.get("t") == "decide" and e.get("kind") in kinds for e in ctx.later())


def _asked_before(ctx: Ctx, kind: str) -> bool:
    """A box of this kind already asked earlier in the action (a re-ask shows no card)."""
    return any(e.get("t") == "decide" and e.get("kind") == kind for e in ctx.earlier())


def _trim(ctx: Ctx, lines: Sequence[Any], limit: int, room: bool = True) -> List[str]:
    """A card's own lines, in display order: plain text, or (rank, text) where rank 0 is
    the most needed. With ``room`` the least needed give way to the lines waiting for
    the card (at least one stays under a middle number, two otherwise)."""
    items = [x if isinstance(x, tuple) else (k, x) for k, x in enumerate(lines)]
    items = [(r, t) for r, t in items if t]
    n = max(1 if limit == MAX_LINES_MIDDLE else 2, limit - len(ctx.pending)) if room else limit
    keep = sorted(sorted(range(len(items)), key=lambda k: items[k][0])[:n])
    return [_fit(items[k][1]) for k in keep]


def _card(ctx: Ctx, suit: str, number: Any, lines: Sequence[Any], immune: bool = False, title: str = "",
          middle: Any = "", caption: str = "", room: bool = True) -> InfoCard:
    limit = MAX_LINES_MIDDLE if middle != "" else MAX_LINES
    return InfoCard(ROW_OF[suit], title or ctx.class_title(suit), number, lines=_trim(ctx, lines, limit, room),
                    immune=immune, middle=middle, caption=caption)


def _first(name: str) -> str:
    return name.split()[0] if name.strip() else name


def _short(ctx: Ctx, player: Any) -> str:
    """The player's first name when no other player shares it ("Player 1" stays whole)."""
    name = ctx.name(player)
    firsts = [_first(str(getattr(p, "name", ""))) for p in getattr(ctx.g, "players", ())]
    return _first(name) if firsts.count(_first(name)) == 1 else name


def _pack(parts: Sequence[str]) -> List[str]:
    """Parts joined with ' · ', wrapped onto lines of 40 characters."""
    lines: List[str] = []
    for part in parts:
        if lines and len(lines[-1] + " · " + part) <= LINE:
            lines[-1] += " · " + part
        else:
            lines.append(part)
    return lines


def _counts(ctx: Ctx, counts: Dict[str, int], most: int = 2) -> List[str]:
    """'Ana +2 · Ben +1': a count per player, in the order given, on at most ``most``
    lines (first names when the full ones do not fit)."""
    for short in (False, True):
        lines = _pack(["%s +%d" % (_short(ctx, p) if short else ctx.name(p), n) for p, n in counts.items()])
        if len(lines) <= most:
            break
    return [_fit(x) for x in lines[:most]]


# ---------------------------------------------------------------------------- immunity
def _would_be_immune(gs: Any, suit: str) -> bool:
    """Is the enemy immune to ``suit`` (before any card or Jester ignores it)?"""
    enemy = getattr(gs, "enemy", None)
    if enemy is None:
        return False
    if getattr(gs, "immunity_cancelled", False):
        return suit in enemy.suits
    immune = _call(gs.rules, "immune_suits", gs)
    return suit in (enemy.suits if immune is None else immune)


def _ignore_line(ctx: Ctx, suit: str) -> str:
    """'{card} ignores immunity ({why})' when the enemy is immune to this class but the
    attack ignores it (Myla's fixed immunity never is: those powers come immune)."""
    gs = _was(ctx)
    if not _would_be_immune(gs, suit):
        return ""
    if getattr(gs, "immunity_cancelled", False) or _jester_attack(ctx):
        return "Ignores immunity (Jester)"
    for cid in _attack_cards(ctx):
        card = gs.cards.get(cid) or ctx.g.cards.get(cid)
        if card is None or suit not in _card_suits(gs, card):
            continue
        for flag, why in IGNORE_FLAGS:
            if card.has(flag):
                return _fit("%s ignores immunity (%s)" % (card.label(), why))
    return ""


def _bane(gs: Any, n: int) -> bool:
    return bool(_call(gs.rules, "has_bane", gs, n, default=False))


def _immune_source(ctx: Ctx, suit: str) -> str:
    """One line naming why the enemy is immune to ``suit``: from the snapshot, else from
    the game after the action (a pile top an earlier power changed, such as mission 11's
    top discard after a heal) while the same enemy stands."""
    was = _was(ctx)
    line = _source_in(ctx, was, suit)
    if line or ctx.g is was or _enemy_id(ctx.g) != _enemy_id(was):
        return line
    return _source_in(ctx, ctx.g, suit)


def _enemy_id(gs: Any) -> Any:
    enemy = getattr(gs, "enemy", None)
    return getattr(enemy, "card_id", None)


def _source_in(ctx: Ctx, gs: Any, suit: str) -> str:
    enemy = getattr(gs, "enemy", None)
    if enemy is None:
        return ""
    if _call(gs.rules, "fixed_immunity", gs, suit, default=False):
        return "Immune: never ignored (Myla)"
    if suit in enemy.suits:
        return "Immune: printed %s" % SUIT_SYMBOL.get(suit, suit)
    boss = gs.cards.get(enemy.card_id)
    if boss is not None and boss.has("immune_basic") and suit in BASIC_SUITS:
        return "Immune: all four basics (High Arcana)"
    piles = []
    discard, banished = getattr(gs, "discard", None) or [], getattr(gs, "banished", None) or []
    if ctx.mission in (3, 12) or (ctx.evergreen and _call(gs.rules, "location", gs) == "A"):
        piles.extend(("zone", cid) for cid in getattr(gs, "mission_zone", None) or ())
    if ctx.mission == 11 or _bane(gs, 19):
        piles.append(("top discard", discard[0] if discard else None))
    if ctx.mission == 11 or _bane(gs, 20):
        piles.append(("top banished", banished[-1] if banished else None))
    for where, cid in piles:
        card = gs.cards.get(cid) if cid else None
        if card is not None and not card.has("beast") and suit in card.suits:
            return _fit("Immune: %s %s" % (where, card.label()))
    return ""


def _would(ctx: Ctx, suit: str, value: Any) -> str:
    """The class's own breakdown in 'would' form."""
    if suit == "M":
        return "Would look at the top %s" % value
    if suit == "U":
        return "Would deal the discard pile (%d)" % len(getattr(_was(ctx), "discard", None) or ())
    if suit == "H":
        return "Would heal %s" % value
    if suit == "D":
        return "Would draw %s" % value
    if suit == "T":
        return "Would draw, then discard to the limit" if ctx.solo else "Would have everyone draw"
    if suit == "R":
        return "Would reveal and double"
    if suit == "C":
        before = _reaver_damage(ctx) or _int(value)
        return "Would double %d → %d" % (before, before * 2)
    if suit == "S":
        return "Would shield %s" % value
    return "Would protect the party"


def _blocked(ctx: Ctx, suit: str, value: Any) -> None:
    """The class's own card greyed and stamped IMMUNITY, in its slot (a Paladin or
    Guardian after the damage, and not at all on a kill)."""
    lines = [_would(ctx, suit, value), _immune_source(ctx, suit)]
    if suit == "M":
        lines.append("The attack is still banished at clean-up")
    if suit in ("S", "G"):
        if not _kill(ctx):
            ctx.defer(AFTER_DAMAGE, _card(ctx, suit, value, lines, immune=True, room=False))
        return
    ctx.add(_card(ctx, suit, value, lines, immune=True))


# ---------------------------------------------------------------------------- the attack
@on("play")
@_safe
def _formation(ctx: Ctx, ev: dict) -> None:
    """A new attack: what the classes gathered for the last one is spent; the first card
    of this one carries its formation line."""
    for key in CARRY_KEYS:
        ctx.carry.pop(key, None)
    line = _formation_line(ctx, ev)
    if line:
        ctx.line(line)


def _formation_line(ctx: Ctx, ev: dict) -> str:
    ids = [str(c) for c in ev.get("cards") or []]
    if ev.get("kind") not in ("companion", "set") or len(ids) < 2:
        return ""
    value = ev.get("value", "")
    labels = [ctx.label(c) for c in ids]
    if any(ctx.g.cards[c].has("beast") for c in ids if c in ctx.g.cards):
        return _fit("Beast copies %d: %s = %s" % (_int(value) // 2, " + ".join(labels), value))
    if ev.get("kind") == "companion":
        return _fit("Companion %s = %s" % (" + ".join(labels), value))
    return _fit("%s %s = %s" % ("Combo" if ctx.base else "Kinfolk", " ".join(labels), value))


@on("power")
@_safe
def _power(ctx: Ctx, ev: dict) -> None:
    suit = str(ev.get("suit", ""))
    if suit not in ROW_OF or ev.get("forecast"):
        return
    if ev.get("immune"):
        _blocked(ctx, suit, ev.get("value", ""))
        return
    builder = POWERS.get(suit)
    if builder is not None:
        builder(ctx, ev, ev.get("value", ""))


@on("decide")
@_safe
def _decide(ctx: Ctx, ev: dict) -> None:
    kind = ev.get("kind")
    if kind == "chanter_declare":
        _chanter_card(ctx, ev)
    elif kind == "reaver_count":
        _reaver_card(ctx, ev)
    elif kind == "emblem_place":
        _mage_emblem(ctx, ev)


# ---------------------------------------------------------------------------- Mage
def _mage_lines(ctx: Ctx, player: Any, count: Any, order: bool = False, will: bool = False) -> List[Any]:
    """The Mage card's breakdown: who looks (a name with 2+ players) and what follows."""
    if ctx.solo:
        who = _fit("You %slook in secret at the top %s" % ("will " if will else "", count))
    else:
        name, verb = ctx.name(player), "will look" if will else "looks"
        who = _fit("%s %s in secret at the top %s" % (name, verb, count), "%s %s at the top %s" % (name, verb, count),
                   "%s %s at the top %s" % (_short(ctx, player), verb, count),
                   "The mage %s at the top %s" % (verb, count))
    rest = "The rest go to the discard pile"
    if order:
        rest = "The rest: discard pile, in your order" if ctx.solo else "The rest: discard pile, in chosen order"
    return [(0, who), (1, "Pick one to join the attack"), (3, "(no Jesters, no corrupted cards)"), (2, rest)]


@on("mage_peek")
@_safe
def _mage_peek(ctx: Ctx, ev: dict) -> None:
    """The Mage card before its private peek box ('Mage again' for a chained mage)."""
    chained = any(e.get("t") in MAGE_RESULTS for e in ctx.earlier())
    ctx.carry["cls_mage"] = {"old": _strength(ctx)}
    if ctx.carry.pop("cls_mage_emblem", None) and not chained:
        return                     # the Mage card stood before the Azure Emblem's boxes
    count = _int(ev.get("count", len(ev.get("revealed") or [])))
    if count <= 0:
        lines: List[Any] = ["Nothing to look at: %s empty" % ctx.reserve]
    else:
        order = bool(_call(ctx.g.rules, "discard_top_matters", ctx.g, default=False)) and count > 1
        lines = _mage_lines(ctx, ev.get("player", _attacker(ctx)), count, order) + [(4, _ignore_line(ctx, "M"))]
    ctx.add(_card(ctx, "M", ev.get("strength", ""), lines, title="Mage again" if chained else "Mage"))


def _mage_emblem(ctx: Ctx, ev: dict) -> None:
    """2+ players with the Azure Emblem: the Mage card comes before the Azure Emblem card
    (info_turn queues that one after this event's cards) and the placements; its peek
    arrives an action later and shows no second card."""
    if any(e.get("t") in ("emblem_place", "emblem_pass") for e in ctx.earlier()) or _asked_before(ctx, "emblem_place"):
        return
    ctx.carry["cls_mage_emblem"] = True
    strength = ev.get("strength", _strength(ctx))
    lines = _mage_lines(ctx, _attacker(ctx), strength, will=True) + [(4, _ignore_line(ctx, "M"))]
    ctx.add(_card(ctx, "M", strength, lines, title="Mage"))


@on(*MAGE_RESULTS)
@_safe
def _mage_result(ctx: Ctx, ev: dict) -> None:
    """What the mage's boxes chose: one line on the next card once its last box is done;
    a chosen mage that the immunity stops gives a stamped 'Mage again' card."""
    m = ctx.carry.setdefault("cls_mage", {})
    t = ev.get("t")
    if t == "mage_pick":
        m["picked"], m["value"] = ev.get("card"), ev.get("value")
    gone = ev.get("cards") if t == "discard_order" else ev.get("discarded")
    m["discarded"] = _int(m.get("discarded")) + len(gone or [])
    if _later_box(ctx, MAGE_BOXES):
        return
    ctx.carry.pop("cls_mage", None)
    if ctx.on("mage"):
        ctx.line(_mage_line(ctx, m))
    picked = ctx.g.cards.get(str(m.get("picked")))
    told = any(e.get("t") == "mage_peek" or (e.get("t") == "power" and e.get("suit") == "M") for e in ctx.later())
    if picked is not None and _mage_chains(ctx, picked) and not told:
        strength = _mage_strength(ctx, picked)
        lines = ["Would look at the top %d" % strength, _immune_source(ctx, "M")]
        ctx.add(_card(ctx, "M", strength, lines, immune=True, title="Mage again"))


def _mage_strength(ctx: Ctx, card: Any) -> int:
    return _int(_call(ctx.g.rules, "strength", card, default=card.value))


def _mage_chains(ctx: Ctx, card: Any) -> bool:
    return "M" in card.suits and _mage_strength(ctx, card) > 0


def _mage_line(ctx: Ctx, m: dict) -> str:
    discarded = _int(m.get("discarded"))
    tail = ", %d discarded" % discarded if discarded else ""
    if not m.get("picked"):
        return "Mage: nothing could join" + tail
    value, picked = _int(m.get("value")), ctx.g.cards.get(str(m["picked"]))
    old = m.get("old", value - _mage_strength(ctx, picked) if picked is not None else "?")
    head = "Mage: %s joins (%s → %d)" % (ctx.label(m["picked"]), old, value)
    return head + tail if len(head + tail) <= LINE else _fit(head)


def _mage_zero(ctx: Ctx, ev: dict, value: Any) -> None:
    if isinstance(ev.get("result"), dict):
        ctx.add(_card(ctx, "M", value, ["Nothing to look at: strength 0"]))


# ---------------------------------------------------------------------------- Druid
@on("druid_deal")
@_safe
def _druid_deal(ctx: Ctx, ev: dict) -> None:
    """The Druid card before the first sorting box."""
    dealt = ev.get("dealt") or []
    total = sum(len(x) if isinstance(x, list) else _int(x) for x in dealt)
    ctx.carry["cls_druid"] = {}
    if ctx.solo:
        lines = [(3, "Strength not used"), (0, "Discard pile (%d) shuffled, dealt to you" % total),
                 (1, "Sort up to 4: one banished, one to hand,"), (2, "one on top and one under the reserve")]
    else:
        player = ev.get("player", _attacker(ctx))
        lines = [(4, "Strength not used"), (0, "Discard pile (%d) shuffled and dealt out" % total),
                 (3, _fit("clockwise from %s" % ctx.name(player), "clockwise from %s" % _short(ctx, player),
                          "clockwise from the druid's player")),
                 (1, "Each sorts 4: one banished, one to hand,"), (2, "one on top and one under the reserve")]
    ctx.add(_card(ctx, "U", _strength(ctx), lines + [(5, _ignore_line(ctx, "U"))]))


@on("druid_assign", "druid_done")
@_safe
def _druid_result(ctx: Ctx, ev: dict) -> None:
    """The sorting, over several actions: one line (counts only) once the druid is done."""
    d = ctx.carry.setdefault("cls_druid", {})
    if ev.get("t") == "druid_assign":
        for slot in ("banish", "hand", "top", "bottom"):
            if ev.get(slot):
                d[slot] = _int(d.get(slot)) + 1
        return
    ctx.carry.pop("cls_druid", None)
    if not ctx.on("druid"):
        return
    head = "Druid: banished %d · %s %d · reserve %d" % (
        _int(d.get("banish")), "hand" if ctx.solo else "hands", _int(d.get("hand")),
        _int(d.get("top")) + _int(d.get("bottom")))
    back = " · back %d" % _int(ev.get("returned"))
    ctx.line(head + back if len(head + back) <= LINE else head)


def _druid_empty(ctx: Ctx, ev: dict, value: Any) -> None:
    if isinstance(ev.get("result"), dict):
        ctx.add(_card(ctx, "U", value, ["Strength not used", "Discard pile empty: nothing to deal"]))


# ---------------------------------------------------------------------------- Cleric, Bard
def _cleric(ctx: Ctx, ev: dict, value: Any) -> None:
    healed = _int(ev.get("healed"))
    redirected = 0
    for e in reversed(ctx.events[:ctx.i]):
        if e.get("t") == "reserve_redirect":
            redirected += 1
        elif e.get("t") != "heal":
            break
    under = healed - redirected
    if healed <= 0:
        lines = ["Heal %s" % value, "Discard pile empty: nothing to heal"]
    else:
        lines = ["Heal %s: the discard pile is shuffled" % value]
        if under > 0:
            lines.append("%d go%s face down under the %s" % (under, "es" if under == 1 else "", ctx.reserve))
        if redirected:
            lines.append("M12: %d corrupted → banished bottom" % redirected)
    lines.append(_ignore_line(ctx, "H"))
    ctx.add(_card(ctx, "H", value, lines))


def _bard(ctx: Ctx, ev: dict, value: Any) -> None:
    """Counts per player, never the cards drawn."""
    counts: Dict[str, int] = {}
    for d in ev.get("drawn") or []:
        key = str(d.get("player", 0)) if isinstance(d, dict) else "0"
        counts[key] = counts.get(key, 0) + 1
    drawn = sum(counts.values())
    if ctx.solo:
        lines: List[Any] = [(0, "Draw %s from the %s" % (value, ctx.reserve)), (1, "You drew %d" % drawn)]
    else:
        player = _attacker(ctx)
        name = ctx.name(player)
        lines = [(0, "Draw %s, one card at a time," % value),
                 (3, _fit("clockwise from %s; full hands skip" % name, "clockwise from %s" % name,
                          "clockwise from %s" % _short(ctx, player), "clockwise; full hands are skipped"))]
        lines += [(1, x) for x in _counts(ctx, counts)] if counts else [(1, "Nobody drew")]
    if drawn < _int(value):
        full = all(len(p.hand) >= ctx.g.config.max_hand for p in ctx.g.players)
        short = ("Hand full" if ctx.solo else "Hands full") if full else "The %s ran out" % ctx.reserve
        lines.append((2, "%s: %d of %s" % (short, drawn, value)))
    lines.append((4, _ignore_line(ctx, "D")))
    ctx.add(_card(ctx, "D", value, lines))


# ---------------------------------------------------------------------------- Chanter
def _chanter_card(ctx: Ctx, ev: dict) -> None:
    """The Chanter card before the number box."""
    if _asked_before(ctx, "chanter_declare"):
        return
    ctx.carry["cls_chanter"] = {"count": 0, "drawn": {}, "discarded": {}}
    most, limit = ev.get("max", 0), ctx.g.config.max_hand
    if ctx.solo:
        lines = [(3, "Strength not used"), (0, "Name 0 to %s (the reserve's size)" % most),
                 (1, "Draw that many, even over the limit,"), (2, "then discard down to %s" % limit)]
    else:
        player = ev.get("player", 0)
        name = ctx.name(player)
        lines = [(3, "Strength not used"),
                 (0, _fit("%s names 0 to %s (the reserve)" % (name, most), "%s names 0 to %s" % (name, most),
                          "%s names 0 to %s" % (_short(ctx, player), most), "The chanter names 0 to %s" % most)),
                 (1, "Everyone draws that many, even over"), (2, "the limit, then discards down to %s" % limit)]
    ctx.add(_card(ctx, "T", _strength(ctx), lines + [(4, _ignore_line(ctx, "T"))]))


@on("chanter_declare", "chanter_discard")
@_safe
def _chanter_result(ctx: Ctx, ev: dict) -> None:
    """The draws and discards, over several actions: one line (counts only) once the last
    player is down to the limit."""
    c = ctx.carry.setdefault("cls_chanter", {"count": 0, "drawn": {}, "discarded": {}})
    if ev.get("t") == "chanter_declare":
        c["count"] = _int(ev.get("count"))
        for d in ev.get("drawn") or []:
            if isinstance(d, dict):
                c["drawn"][str(d.get("player", 0))] = len(d.get("cards") or [])
    else:
        key = str(ev.get("player", 0))
        c["discarded"][key] = _int(c["discarded"].get(key)) + len(ev.get("cards") or [])
    if _later_box(ctx, ("chanter_discard",)):
        return
    ctx.carry.pop("cls_chanter", None)
    if ctx.on("chanter"):
        ctx.line(_chanter_line(ctx, c))


def _chanter_line(ctx: Ctx, c: dict) -> str:
    """'Chanter 2: Ana +2 −1 · Ben +2': drawn (+) and discarded (−) per player."""
    count = _int(c.get("count"))
    if count <= 0:
        return "Chanter 0: nobody draws"
    drawn, gone = c.get("drawn") or {}, c.get("discarded") or {}
    if ctx.solo:
        out = _int(gone.get("0"))
        return "Chanter %d: you drew %d%s" % (count, _int(drawn.get("0")), ", discarded %d" % out if out else "")
    if not drawn:
        return "Chanter: %d declared" % count

    def each(short: bool) -> str:
        return " · ".join("%s +%d%s" % (_short(ctx, p) if short else ctx.name(p), n,
                                         " −%d" % _int(gone.get(p)) if _int(gone.get(p)) else "")
                          for p, n in drawn.items())
    took = sorted(set(drawn.values()))
    total = "each drew %d" % took[0] if len(took) == 1 else "%d drawn" % sum(drawn.values())
    out = sum(_int(n) for n in gone.values())
    return _fit("Chanter %d: %s" % (count, each(False)), "Chanter %d: %s" % (count, each(True)),
                "Chanter %d: %s, %d discarded" % (count, total, out))


# ---------------------------------------------------------------------------- Reaver
def _reaver_card(ctx: Ctx, ev: dict) -> None:
    """The Reaver card before the count box."""
    if _asked_before(ctx, "reaver_count"):
        return
    lines = [(0, "Reveal 1 to %s %s cards" % (ev.get("max", "?"), ctx.reserve)),
             (1, "Add one's strength to the damage (%s)" % ev.get("damage", _strength(ctx))),
             (3, "No powers; 2/5 adds 5, Jester/beast 0"), (2, "Banish all revealed, then the damage ×2"),
             (4, _ignore_line(ctx, "R"))]
    ctx.add(_card(ctx, "R", _strength(ctx), lines))


@on("reaver_pick")
@_safe
def _reaver_result(ctx: Ctx, ev: dict) -> None:
    """The pick, one line on the next card (the revealed cards are banished: public)."""
    if not ctx.on("reaver") or not ev.get("card"):
        return
    added, damage = _int(ev.get("added")), _int(ev.get("damage"))
    total = damage // 2
    ctx.line(_fit("Reaver: %d + %d (%s) = %d, ×2 = %d" % (total - added, added, ctx.label(ev.get("card")),
                                                         total, damage)))


def _reaver_empty(ctx: Ctx, ev: dict, value: Any) -> None:
    """An empty reserve: no box, the Reaver card says what happened."""
    result = ev.get("result")
    if not isinstance(result, dict):
        return
    damage = _int(result.get("damage"))
    lines = ["%s empty: nothing to reveal" % ctx.reserve.capitalize(),
             "The damage just doubles: %d → %d" % (damage // 2, damage)]
    ctx.add(_card(ctx, "R", value, lines))


def _reaver_damage(ctx: Ctx) -> int:
    """The damage after this action's Reaver (0: no Reaver)."""
    for e in reversed(ctx.events[:ctx.i + 1]):
        if e.get("t") == "reaver_pick":
            return _int(e.get("damage"))
        if e.get("t") == "power" and e.get("suit") == "R" and isinstance(e.get("result"), dict):
            return _int(e["result"].get("damage"))
    return 0


# ---------------------------------------------------------------------------- Warrior, Damage
def _warrior(ctx: Ctx, ev: dict, value: Any) -> None:
    """The Warrior waits for the damage event: its card carries the damage."""
    ctx.state["cls_warrior"] = (dict(ev), _ignore_line(ctx, "C"))


@on("damage")
@_safe
def _damage(ctx: Ctx, ev: dict) -> None:
    """The step-3 slot: the Warrior card with the damage, else the Damage card; then the
    Paladin and Guardian cards when the enemy survives."""
    amount = ev.get("amount", "")
    reduction, health = _reduction_line(ctx), _health_line(ctx, ev)
    reaver = _reaver_damage(ctx)
    warrior = ctx.state.pop("cls_warrior", None)
    shown = False
    if warrior is not None:
        power, ignore = warrior
        before = reaver or _int(power.get("value"))
        double = "%d ×2 = %d%s" % (before, before * 2, " (Reaver first: ×4 in all)" if reaver else "")
        lines = [(0, double), (3, ignore), (2, reduction), (1, health)]
        shown = ctx.add(_card(ctx, "C", power.get("value", ""), lines, middle=amount, caption="damage"))
    if not shown:
        strength = _strength(ctx)
        attack = "Attack %s%s" % (strength, " · after the Reaver: %d" % reaver if reaver else "")
        lines = _trim(ctx, [(2, attack), (1, reduction), (0, health)], MAX_LINES_MIDDLE)
        ctx.add(InfoCard("damage", "Damage", strength, lines=lines, middle=amount, caption="damage"))
    if _kill(ctx):
        ctx.deferred.pop(AFTER_DAMAGE, None)
        return
    held = list(ctx.deferred.get(AFTER_DAMAGE, []))
    ctx.flush(AFTER_DAMAGE)
    if any(c.id == "guardian" and not c.immune and any(c is x for x in ctx.cards) for c in held):
        ctx.state["guardian_shown"] = True


def _reduction_line(ctx: Ctx) -> str:
    gs = _was(ctx)
    r = _int(_call(gs.rules, "damage_reduction", gs, default=0))
    if r <= 0:
        return ""
    return "− %d: Immovable Paladins" % r if ctx.evergreen else "− %d: Paladin enemy" % r


def _health_line(ctx: Ctx, ev: dict) -> str:
    if ev.get("hp") is None:
        return ""
    hp, amount = _int(ev.get("hp")), _int(ev.get("amount"))
    if hp > 0:
        return "Health %d → %d" % (hp + amount, hp)
    enemy = getattr(ctx.before, "enemy", None)
    before = enemy.hp if enemy is not None else None
    exact = before is not None and before == amount
    for e in ctx.later():
        if e.get("t") == "defeat" or (e.get("t") == "decide" and "exact" in e):
            exact = bool(e.get("exact"))
            break
    end = ": exact kill!" if exact else ": defeated!"
    return "Health %d → 0%s" % (before, end) if before is not None else "Health 0%s" % end


# ---------------------------------------------------------------------------- Paladin, Guardian
def _paladin(ctx: Ctx, ev: dict, value: Any) -> None:
    """The shield, after the damage; nothing on a kill (the owner's ruling)."""
    if _kill(ctx):
        return
    shield = _int(ev.get("shield", value))
    before, others = _shields_before(ctx)
    total = others + shield
    lines = ["Shield +%d: enemy attack %d → %d" % (shield, before, max(0, before - shield)),
             "Shields total %d until it falls" % total, _ignore_line(ctx, "S") or _keeps_shielding(ctx)]
    ctx.defer(AFTER_DAMAGE, _card(ctx, "S", value, lines, room=False))


def _shields_before(ctx: Ctx) -> tuple:
    """The enemy's attack and the shields on it before this attack's paladins. A paused
    attack (a mage, druid, chanter or reaver box) is already on the snapshot's table and
    its shield counted there, so it is left out."""
    gs = _was(ctx)
    ids = set(_attack_cards(ctx))
    plays = getattr(gs, "plays", None)
    others = [p for p in plays or () if not ids & set(getattr(p, "card_ids", None) or ())]
    if not plays or len(others) == len(plays):
        return _int(_attr(gs, "enemy_attack")), _int(_attr(gs, "shield"))
    gs.plays = others
    try:
        return _int(_attr(gs, "enemy_attack")), _int(_attr(gs, "shield"))
    finally:
        gs.plays = plays


def _keeps_shielding(ctx: Ctx) -> str:
    """A paladin that ignores immunity keeps its shield if the enemy gains ♠ immunity
    later (where immunity changes: missions 3, 11 and 12, Evergreen)."""
    if not (ctx.mission in (3, 11, 12) or ctx.evergreen):
        return ""
    if _jester_attack(ctx):
        return "Keeps shielding if ♠ immunity comes"
    gs = _was(ctx)
    for cid in _attack_cards(ctx):
        card = gs.cards.get(cid) or ctx.g.cards.get(cid)
        if card is not None and "S" in _card_suits(gs, card) and any(card.has(f) for f, _ in IGNORE_FLAGS):
            return "Keeps shielding if ♠ immunity comes"
    return ""


def _guardian(ctx: Ctx, ev: dict, value: Any) -> None:
    """The Guardian card stands in for No damage when the enemy survives; nothing on a kill."""
    if _kill(ctx):
        return
    lines = ["%s no damage this turn:" % ("You suffer" if ctx.solo else "The party suffers"),
             "no enemy attack, no mission damage", _ignore_line(ctx, "G")]
    ctx.defer(AFTER_DAMAGE, _card(ctx, "G", value, lines, room=False))


POWERS = {"M": _mage_zero, "U": _druid_empty, "H": _cleric, "D": _bard, "R": _reaver_empty,
          "C": _warrior, "S": _paladin, "G": _guardian}
