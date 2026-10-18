"""Info pop-ups: the Damage & defeat, Enemy, Enemy strikes and Game end groups, and mission
2's Hydra regrows. See docs/INFO_POPUPS.md and app/info.py.

A kill shows Defeated, Exact kill! or Hydra regrows right after the killing damage (the one
it replaces when its own row is off); when a box pauses the defeat first, the card reads
the paused game's defeat plan. With no box between the kill and the clean-up, the
clean-up's lines fold into that card; otherwise Clean-up shows at the defeat, with the
choices made in between (kept in the carry buffer). A mission 5 carry kill shows its card
at its defeat, after the Carry damage card. New enemy shows at a reveal after a kill (the
first enemy belongs to Battle start); Enemy changes only when no other card of the queue
states the enemy's attack and immunity. Enemy attacks or No damage at the strike, Feign
death and Damage paid at the suffer, Team damage at the team damage; Victory and Defeat
are always the last card.

Hidden information stays hidden: cards going into a hand or the reserve are counted, never
named, and team damage never shows the hands' total with 2+ players.
"""
from __future__ import annotations

import functools
import traceback
from typing import Any, List, Optional, Sequence, Tuple

from regicide.cards import BASIC_SUITS, SUIT_SYMBOL

from .info import MAX_LINES, MAX_LINES_MIDDLE, Ctx, InfoCard, finisher, last, on, starter

LINE = 40
ERRORS: List[str] = []                     # what a handler swallowed (the tests check it stays empty)

WHERE = {"tavern_top": "top of the %s", "discard": "discard pile", "banish": "banished",
         "banish_shuffle": "shuffled into the banished pile", "castle_bottom": "bottom of the castle"}
SHORT_WHERE = {"banish_shuffle": "banished, shuffled", "castle_bottom": "castle bottom"}
# the first box after a kill, as the "Next:" line of the Defeated card (an order box says
# why the order matters; the exact-kill boxes are the Exact kill! card's bonus)
NEXT = {"zone_move": "Next: move a played card into the zone",
        "zone_build": "Next: build the zone, one strength up",
        "banish_order": "Next: order the zone; its top returns",
        "zone_order": "Next: name the zone's discard order",
        "played_discard_order": "Next: order the played cards; top counts",
        "played_banish_order": "Next: order the mage attack; top counts"}
# the defeat-step choices: lines on Clean-up (or on the next card once it was shown)
CHOICES = ("zone_rescue", "zone_move", "zone_banish", "zone_build", "zone_filled", "pile_to_reserve",
           "precision_strike", "restored_arrows", "zone_discard", "discard_pick", "lake_banish")
# where the clean-up's events end
CLEANUP_END = ("reveal", "won", "lost", "decide", "turn", "damage", "carry_damage", "defeat", "team_damage")
# the cards that state the enemy's attack and immunity (Enemy changes then stays away)
STATES_ENEMY = ("enemy_attack", "shielded", "turn", "new_enemy", "battle_start", "m3_zone", "m5_zone", "m10_zone",
                "m12_zone", "m10_cleric", "m10_bard", "m11_beast", "shrine", "cave", "cave_collapse", "forest",
                "hills", "lake", "victory", "loss")
# the steps of an attack that may move a pile top the enemy reads (Enemy changes follows them)
SHIFTERS = ("power", "corrupt_banish", "corrupt_banish_none", "restore", "druid_deal", "druid_done",
            "mage_pick", "mage_skip", "discard_order", "emblem_keep", "emblem_skip", "reaver_pick",
            "zone_sibling", "attack_discard", "pilgrim_banish", "add_to_play", "chanter_discard")
# the turn's moves undone to see an enemy as it was revealed or struck
START_MOVES = ("zone_add", "bane", "beast_effect")


def _safe(fn):
    """A handler that never raises: on the phone a raising builder loses the whole queue
    (what it swallowed goes to ``ERRORS`` and, on the phone, to errors.log)."""
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


# ---------------------------------------------------------------------------- helpers
def fit(*variants: str) -> str:
    """The first wording that fits on a line (the last one cut to fit)."""
    for text in variants:
        if text and len(text) <= LINE:
            return text
    last = variants[-1] if variants else ""
    return last if len(last) <= LINE else last[:LINE - 1] + "…"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _call(obj: Any, name: str, *args: Any, default: Any = None) -> Any:
    fn = getattr(obj, name, None)
    if fn is None:
        return default
    try:
        return fn(*args)
    except Exception:
        return default


def active(ctx: Ctx) -> int:
    """The player whose turn it is (0 on a game without one)."""
    return _int(getattr(ctx.g, "active", 0))


def count(n: int, word: str) -> str:
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def icons(suits: Sequence[str]) -> str:
    return "".join(SUIT_SYMBOL.get(s, s) for s in suits)


def class_icon(suits: Sequence[str]) -> str:
    """An enemy's printed class icons as one card icon: a class letter (drawn in its class
    colour), the symbols of several, or none for a classless enemy."""
    suits = [str(s) for s in suits]
    return suits[0] if len(suits) == 1 else icons(suits)


def _trim(ctx: Ctx, items: Sequence[Tuple[int, str]], limit: int, room: bool = True) -> List[str]:
    """A card's own lines, (rank, text) in display order where rank 0 is the most needed;
    with ``room`` the least needed give way to the lines waiting for the card (one stays
    under a middle number, two otherwise)."""
    items = [(r, t) for r, t in items if t]
    n = max(1 if limit == MAX_LINES_MIDDLE else 2, limit - len(ctx.pending)) if room else limit
    keep = sorted(sorted(range(len(items)), key=lambda k: items[k][0])[:n])
    return [fit(items[k][1]) for k in keep]


def _card(ctx: Ctx, row: str, title: str, number: Any = "", items: Sequence[Tuple[int, str]] = (),
          middle: Any = "", caption: str = "", icon: Optional[str] = None, room: bool = True) -> InfoCard:
    limit = MAX_LINES_MIDDLE if middle != "" else MAX_LINES
    return InfoCard(row, title, number, icon=icon, lines=_trim(ctx, items, limit, room), middle=middle,
                    caption=caption)


def ranked(lines: Sequence[str], rank: int) -> List[Tuple[int, str]]:
    return [(rank, x) for x in lines]


def game_word(ctx: Ctx) -> str:
    """'mission' in a Legacy mission; 'game' in the base game and Evergreen."""
    return "game" if ctx.base or ctx.evergreen else "mission"


# ---------------------------------------------------------------------------- the enemy
def standing(ctx: Ctx, card_id: Any) -> Any:
    """The game in which this enemy still stands: the game after the action (a defeat
    paused on a box), else the snapshot before it; None when neither has it."""
    for game in (ctx.g, ctx.before):
        enemy = getattr(game, "enemy", None)
        if enemy is not None and str(enemy.card_id) == str(card_id):
            return game
    return None


def enemy_name(ctx: Ctx, card_id: Any) -> str:
    game = standing(ctx, card_id)
    if game is not None:
        return str(game.enemy.name)
    card = ctx.g.cards.get(str(card_id))
    if card is None:
        return "The enemy"
    from regicide.engine import enemy_name as name_of
    return name_of(card, not ctx.base)


def raw_attack(game: Any) -> Optional[int]:
    """The enemy's attack before shields: (printed + bonus) × multiplier."""
    enemy = getattr(game, "enemy", None)
    if enemy is None:
        return None
    try:
        return (enemy.attack + int(game.rules.attack_bonus(game))) * int(game.rules.attack_multiplier(game))
    except Exception:
        return int(enemy.attack)


def printed_attack(ctx: Ctx, card_id: Any) -> Any:
    card = ctx.g.cards.get(str(card_id))
    stats = _call(ctx.g.rules, "enemy_stats", ctx.g, card) if card is not None else None
    return stats[0] if stats else ""


def immune_suits(game: Any) -> Tuple[str, ...]:
    return tuple(_call(game.rules, "immune_suits", game, default=()) or ())


def _undo(game: Any, ev: dict) -> None:
    """Put back one move of the turn (a zone card, a bane's move, a beast's)."""
    t = ev.get("t")
    cid = str(ev.get("card") if t != "beast_effect" else ev.get("moved"))
    piles = {"discard": game.discard, "banished": game.banished}
    if t == "zone_add":
        if cid in game.mission_zone:
            game.mission_zone.remove(cid)
        source = ev.get("source")
        if source == "reserve":
            game.tavern.insert(0, cid)
        elif source == "banished":
            game.banished.append(cid)
        elif source == "discard":
            game.discard.insert(0, cid)
    elif t == "bane" and _int(ev.get("n")) == 16 and cid in game.banished:
        game.banished.remove(cid)
        game.discard.insert(0, cid)
    elif t == "bane" and _int(ev.get("n")) == 22 and cid in game.discard:
        game.discard.remove(cid)
        game.tavern.insert(0, cid)
    elif t == "beast_effect" and cid in piles.get(str(ev.get("to")), ()):
        piles[str(ev.get("to"))].remove(cid)
        if ev.get("suit") == "C":
            game.discard.insert(0, cid)          # the warrior beast banished the top discard
        elif ev.get("suit") == "S":
            game.tavern.insert(0, cid)           # the paladin beast discarded the reserve top


def rewound(ctx: Ctx, k: int) -> Any:
    """The game after the action with the zone, bane and beast moves after event ``k``
    undone (the turn's own cards state those changes)."""
    moves = [e for e in ctx.events[k + 1:] if e.get("t") in START_MOVES]
    if not moves:
        return ctx.g
    from regicide.engine import Game
    game = Game.from_dict(ctx.g.to_dict())
    for e in reversed(moves):
        _undo(game, e)
    return game


def at_reveal(ctx: Ctx, k: int) -> Any:
    """The game as the enemy revealed at event ``k`` met it; None when that enemy is no
    longer on the table."""
    enemy = (ctx.events[k].get("enemy") or {}) if 0 <= k < len(ctx.events) else {}
    if standing(ctx, enemy.get("card_id")) is not ctx.g:
        return None
    return rewound(ctx, k)


# ---------------------------------------------------------------------------- the kill
def defeat_after(ctx: Ctx, i: int) -> Tuple[Optional[int], dict]:
    """The defeat event of the kill at event ``i`` when no box comes first."""
    for j in range(i + 1, len(ctx.events)):
        t = ctx.events[j].get("t")
        if t == "defeat":
            return j, ctx.events[j]
        if t in ("decide", "lost", "won", "damage", "carry_damage", "reveal"):
            break
    return None, {}


def box_after(ctx: Ctx, i: int) -> dict:
    """The box the defeat of the kill at event ``i`` waits on (a decide), if any."""
    for e in ctx.events[i + 1:]:
        if e.get("t") == "decide":
            return e
        if e.get("t") in ("defeat", "lost", "won"):
            break
    return {}


def kill_facts(ctx: Ctx, i: int, j: Optional[int], dev: dict) -> dict:
    """What the kill at event ``i`` does: the enemy, exactness, its defeat plan, the game
    where it still stands, its defeat event (``j``, when no box comes first) or the box its
    defeat waits on."""
    box = {} if dev else box_after(ctx, i)
    cid = dev.get("enemy")
    if cid is None:
        # a defeat event without its enemy (an older save): the game after it shows the next one
        for game in ((ctx.before, ctx.g) if dev else (ctx.g, ctx.before)):
            if getattr(game, "enemy", None) is not None:
                cid = game.enemy.card_id
                break
    game = standing(ctx, cid)
    if dev:
        exact, plan = bool(dev.get("exact")), dict(dev.get("plan") or {})
    else:
        if "exact" in box:
            exact = bool(box.get("exact"))
        else:
            exact = game is not None and game.enemy.hp == 0
        plan = dict(_call(ctx.g.rules, "defeat_plan", ctx.g, exact, default={}) or {}) if game is ctx.g else {}
    return {"cid": cid, "exact": exact, "plan": plan, "game": game, "box": box, "dev": dev, "j": j}


def where(ctx: Ctx, dest: Any, short: bool = False) -> str:
    dest = str(dest)
    if short and dest in SHORT_WHERE:
        return SHORT_WHERE[dest]
    text = WHERE.get(dest, "discard pile")
    return text % ctx.reserve if "%s" in text else text


def zone_cleared(segment: Sequence[dict]) -> dict:
    return next((e for e in segment if e.get("t") == "zone_cleared"), {})


def zone_goes(ctx: Ctx, facts: dict, segment: Sequence[dict]) -> str:
    """Where the mission zone goes at this defeat ("" when it stays or is empty): its
    clean-up event, or the paused game's zone and plan before the defeat."""
    cleared = zone_cleared(segment)
    if cleared or facts.get("dev"):
        return where(ctx, cleared.get("to")) if cleared else ""
    game = facts["game"]
    if facts["plan"].get("zone_to") and game is not None and game.mission_zone:
        return where(ctx, facts["plan"]["zone_to"])
    return ""


def move_lines(ctx: Ctx, name: str, facts: dict, zone: str, exact_words: bool = False,
               zone_cards: Sequence[str] = ()) -> List[str]:
    """'{enemy} → {where}; zone {cards} → {where}' (two lines when one is too long; the
    zone cards are face up, so they are named when they fit)."""
    dest = facts["plan"].get("enemy_to", "tavern_top" if facts["exact"] else "discard")
    full, short = where(ctx, dest), where(ctx, dest, short=True)
    heads = ["%s falls exactly → %s" % (name, full)] if exact_words else []
    heads += ["%s → %s" % (name, full), "%s → %s" % (name, short), "→ %s" % full]
    if not zone:
        return [fit(*heads)]
    for tail in (["zone %s → %s" % (ctx.labels(zone_cards), zone)] if zone_cards else []) + ["zone → %s" % zone]:
        one = "%s; %s" % (heads[0], tail)
        if len(one) <= LINE:
            return [one]
        if len(tail) <= LINE:
            return [fit(*heads), tail[0].upper() + tail[1:]]
    return [fit(*heads), "Zone → %s" % zone]


def _location(ctx: Ctx, game: Any) -> str:
    return str(_call(game.rules, "location", game, default="") or "")


def _boon(game: Any, n: int) -> bool:
    return bool(_call(game.rules, "has_boon", game, n, default=False))


def _bane(game: Any, n: int) -> bool:
    return bool(_call(game.rules, "has_bane", game, n, default=False))


def last_enemy(facts: dict) -> bool:
    """Was the castle empty when this enemy fell (no next enemy, no next turn)?"""
    game = facts.get("game")
    return game is not None and not (getattr(game, "castle", None) or ())


def bonus_lines(ctx: Ctx, facts: dict) -> List[str]:
    """The exact kill's bonuses in this mission (or Evergreen setup), in the engine's
    order, as many lines as they need (none is dropped; none that needs a next enemy or
    turn after the last enemy)."""
    game = facts["game"] or ctx.g
    zone = bool(getattr(game, "mission_zone", None))
    m = 0 if ctx.evergreen or (last_enemy(facts) and ctx.mission in (5, 11, 12)) else ctx.mission
    parts = {3: ["rescue a zone card"] if zone else [],
             5: ["next enemy takes %d" % _int(facts["plan"]["carry_damage"])]
             if facts["plan"].get("carry_damage") else [],
             6: ["rescue a zone card (not Myla)"], 7: ["banish a zone card first"] if zone else [],
             8: ["a discard on top of the %s" % ctx.reserve], 9: ["a pile's top → top of the reserve"],
             10: ["zone discarded, not banished"], 11: ["no beast next turn"],
             12: ["no zone card next turn"]}.get(m, [])
    if ctx.evergreen:
        parts += [name for n, name in ((32, "Precision Strike"), (33, "Restored Arrows")) if _boon(game, n)]
        if _location(ctx, game) in ("C", "D") and zone:
            parts.append("discard a zone card first")
    lines: List[str] = []
    for part in parts:
        joined = "%s, %s" % (lines[-1], part) if lines else ""
        if joined and len(joined) <= LINE:
            lines[-1] = joined
        else:
            lines.append(fit("Bonus: " + part))
    return lines


def guardian_on(ctx: Ctx, game: Any) -> bool:
    """Does a Guardian protect the party this turn (its power in this action, or before)?"""
    if any(e.get("t") == "power" and e.get("suit") == "G" and not e.get("immune") for e in ctx.events):
        return True
    return bool((getattr(game, "extra", None) or {}).get("guardian"))


def next_lines(ctx: Ctx, i: int, facts: dict) -> List[str]:
    """The defeat steps still to come: the first box, then Myla's or the spores' team
    damage (unless its card or its prevention follows in this queue)."""
    game = facts["game"] or ctx.g
    kind = str(facts["box"].get("kind"))
    lines = [NEXT.get(kind, "")]
    told = kind == "team_discard" or any(e.get("t") in ("team_damage", "team_damage_prevented")
                                         for e in ctx.events[i + 1:])
    if told:
        return [x for x in lines if x]
    guardian = guardian_on(ctx, game)
    if ctx.mission == 6 and not ctx.evergreen:
        lines.append("A Guardian prevents Myla's team damage" if guardian else "Then Myla's team damage: zone strength")
    if ctx.evergreen and _bane(game, 13):
        base = getattr(game.enemy, "attack", 0) if getattr(game, "enemy", None) is not None else 0
        lines.append("A Guardian prevents the team damage" if guardian
                     else fit("Then Explosive Spores: %d team damage" % base, "Then team damage %d" % base))
    return [x for x in lines if x]


def lake_line(ctx: Ctx, i: int) -> str:
    """The Lake's reserve cards banished at this kill (before its box or its defeat)."""
    for e in ctx.events[i + 1:]:
        if e.get("t") == "lake_banish":
            return "%s banished (Lake)" % count(len(e.get("cards") or ()), "reserve card")
        if e.get("t") in ("defeat", "decide", "reveal", "won", "lost"):
            break
    return ""


def goes_again(ctx: Ctx, i: int, facts: dict) -> str:
    """Who plays on after the kill: nobody when the game ends here, or when the castle was
    empty at the kill (a box holds the win)."""
    if last_enemy(facts) or any(e.get("t") in ("won", "lost") for e in ctx.events[i:]):
        return ""
    who = ctx.name(active(ctx))
    head = "You go again" if ctx.solo else "%s goes again" % who
    return fit(head + "; no end-of-turn effects", head) if end_of_turn_effects(ctx) else head


def end_of_turn_effects(ctx: Ctx) -> bool:
    """Does this game have end-of-turn effects (that a kill skips)?"""
    if ctx.base:
        return False
    if ctx.evergreen:
        setup = ctx.g.config.extra.get("evergreen") or {}
        banes = [_int(n) for n in setup.get("banes", [])]
        return str(setup.get("location", "")) in ("A", "B", "C", "D") or any(n in (10, 12, 23) for n in banes)
    return ctx.mission in (3, 5, 9, 10)


def fallen_cards(ctx: Ctx, i: int, facts: dict, folded: List[str]) -> List[InfoCard]:
    """Hydra regrows, Exact kill! and Defeated for this kill, the first that shows wins."""
    cid, exact, plan, game = facts["cid"], facts["exact"], facts["plan"], facts["game"]
    name = enemy_name(ctx, cid)
    number = raw_attack(game) if game is not None else printed_attack(ctx, cid)
    segment = cleanup_segment(ctx, facts.get("j"))
    zone = zone_goes(ctx, facts, segment)
    zone_cards = [str(c) for c in zone_cleared(segment).get("cards") or ()]
    nexts, lake = next_lines(ctx, i, facts), lake_line(ctx, i)
    out = []
    if not exact and plan.get("enemy_to") == "castle_bottom":
        enemy = ctx.g.cards.get(str(cid))
        items = [(0, fit("Not exact: %s goes face down" % name, "Not exact: the Hydra goes face down")),
                 (1, "under the castle; it will come back"), (2, "Exact damage banishes a Hydra for good")]
        items += ranked(["Zone → %s" % zone] if zone else [], 3) + ranked(folded, 4)
        out.append(_card(ctx, "hydra_regrows", "Hydra regrows", number, items,
                         icon=class_icon(enemy.suits) if enemy is not None else None))
    bonus = bonus_lines(ctx, facts) if exact else []
    if exact:
        items = ranked(move_lines(ctx, name, facts, zone, True, zone_cards), 0)
        items += ranked(bonus, 1) + [(2, goes_again(ctx, i, facts))] + ranked(nexts, 2)
        items += [(3, lake)] + ranked(folded, 4)
        out.append(_card(ctx, "exact_kill", "Exact kill!", number, items))
    items = ranked(move_lines(ctx, name, facts, zone, False, zone_cards), 0)
    items += ranked(bonus, 1) + ranked(nexts, 1) + [(2, lake)] + ranked(folded, 3)
    out.append(_card(ctx, "defeated", "Defeated", number, items))
    return out


def show_fallen(ctx: Ctx, i: int, facts: dict, folded: List[str]) -> bool:
    for c in fallen_cards(ctx, i, facts, folded):
        if ctx.add(c):
            return True
    return False


@on("damage", "carry_damage")
@_safe
def _killed(ctx: Ctx, ev: dict) -> None:
    """The killing damage: Defeated (or Exact kill!, or Hydra regrows) at once, its
    clean-up folded in when no box comes first; a carry kill waits for its defeat (after
    the Carry damage card)."""
    if _int(ev.get("hp"), 1) > 0:
        return
    if ev.get("t") == "carry_damage":
        ctx.state["dft_carry"] = True
        return
    j, dev = defeat_after(ctx, ctx.i)
    facts = kill_facts(ctx, ctx.i, j, dev)
    folded = sum(cleanup_lines(ctx, j, dev, folded=True)[1:], []) if j is not None and ctx.on("cleanup") else []
    shown = show_fallen(ctx, ctx.i, facts, folded)
    if shown and lake_line(ctx, ctx.i):
        ctx.state["dft_lake"] = True
    if j is not None:
        ctx.state.setdefault("dft_folded", {})[j] = shown
    else:
        ctx.carry["dft"] = {"choices": []}


# ---------------------------------------------------------------------------- Clean-up
def cleanup_segment(ctx: Ctx, j: Optional[int]) -> List[dict]:
    """The clean-up events of the defeat at event ``j``."""
    out: List[dict] = []
    if j is None or not 0 <= j < len(ctx.events) or ctx.events[j].get("t") != "defeat":
        return out
    for e in ctx.events[j + 1:]:
        if e.get("t") in CLEANUP_END:
            break
        out.append(e)
    return out


def played_cards(ctx: Ctx, j: int, dev: dict) -> List[str]:
    """The cards the defeat at event ``j`` cleaned up, in the order they entered play."""
    start = max([k + 1 for k in range(j) if ctx.events[k].get("t") == "defeat"] or [0])
    ids: List[str] = []
    gs = ctx.before
    if start == 0 and gs is not None and gs.enemy is not None and str(gs.enemy.card_id) == str(dev.get("enemy")):
        ids = [str(c) for p in gs.plays for c in p.card_ids]
    moved = set()
    for e in ctx.events[start:j]:
        if e.get("t") in ("play", "add_to_play"):
            ids += [str(c) for c in e.get("cards") or () if str(c) not in ids]
        elif e.get("t") in ("zone_move", "zone_build"):
            moved.add(str(e.get("card")))
    for e in cleanup_segment(ctx, j):
        if e.get("t") == "zone_absorb":
            moved.update(str(c) for c in e.get("cards") or ())
    attack_jester = ctx.solo and _call(ctx.g.rules, "solo_jester_mode", ctx.g) == "attack"
    out = []
    for cid in ids:
        card = ctx.g.cards.get(cid)
        if cid in moved or (attack_jester and card is not None and card.is_jester):
            continue
        out.append(cid)
    return out


def discard_top(ctx: Ctx, to_discard: List[str], segment: Sequence[dict]) -> str:
    """The played card that ends on top of the discard pile."""
    for e in segment:
        if e.get("t") == "cleanup_order" and e.get("pile") == "discard" and e.get("cards"):
            return str(e["cards"][-1])
    if ctx.g.config.extra.get("discard_low_to_high"):
        return min(to_discard, key=lambda c: getattr(ctx.g.cards.get(c), "value", 0))
    return to_discard[-1]


def enemy_on_top(ctx: Ctx, dev: dict) -> bool:
    """Does the fallen enemy go onto the discard pile after the played cards (the base
    game puts it there last, so a played card is not the top)?"""
    plan = dev.get("plan") if isinstance(dev.get("plan"), dict) else {}
    return not getattr(ctx.g.rules, "played_on_top", True) and plan.get("enemy_to", "discard") == "discard"


def cleanup_lines(ctx: Ctx, j: Optional[int], dev: dict, folded: bool = False) -> Tuple[int, List[str], List[str]]:
    """(cards cleaned up, what happened to them, what else the clean-up did) for the
    defeat at event ``j``; ``folded``: the lines go on the kill card, whose bonus line
    already tells mission 8's pick."""
    if j is None:
        return 0, [], []
    segment = cleanup_segment(ctx, j)
    played = played_cards(ctx, j, dev)
    mage = [str(c) for c in dev.get("mage_banished") or () if str(c) in played]
    redirected = set(str(e.get("card")) for e in segment if e.get("t") == "banish_redirect")
    to_discard = [c for c in played if c not in mage]
    lines = []
    if len(to_discard) == 1:
        lines.append("%s → discard pile" % ctx.label(to_discard[0]))
    elif to_discard and enemy_on_top(ctx, dev):
        lines.append("%d played → discard pile" % len(to_discard))
    elif to_discard:
        top = ctx.label(discard_top(ctx, to_discard, segment))
        lines.append(fit("%d played → discard pile, %s on top" % (len(to_discard), top),
                         "%d played → discard pile" % len(to_discard)))
    banished = [c for c in mage if c not in redirected]
    if banished:
        n = len(banished)
        lines.append(fit("%d played → banished (a mage attack)" % n, "%d played → banished" % n))
    more = []
    for e in segment:
        t = e.get("t")
        if t == "reserve_discard":
            more.append("%s from the %s → discard pile" % (len(e.get("cards") or ()), ctx.reserve))
        elif t == "discard_banished":
            more.append("Whole discard pile banished (%d)" % len(e.get("cards") or ()))
        elif t == "banished_shuffled":
            more.append("Banished pile shuffled")
    tail = ctx.events[j + 1 + len(segment)] if j + 1 + len(segment) < len(ctx.events) else {}
    if tail.get("t") == "decide" and tail.get("kind") == "discard_pick" and not folded:
        more.append("Next: a discard on top of the %s" % ctx.reserve)
    return len(played), lines, more


def cleanup_card(ctx: Ctx, ev: dict) -> None:
    """The Clean-up card: a box stood between the kill and the clean-up (or the card the
    clean-up folds into did not show)."""
    choices = list((ctx.carry.get("dft") or {}).get("choices") or [])
    facts = kill_facts(ctx, ctx.i, ctx.i, ev)
    n, played, more = cleanup_lines(ctx, ctx.i, ev)
    segment = cleanup_segment(ctx, ctx.i)
    zone_cards = [str(c) for c in zone_cleared(segment).get("cards") or ()]
    moves = move_lines(ctx, enemy_name(ctx, facts["cid"]), facts, zone_goes(ctx, facts, segment), False, zone_cards)
    items = ranked(moves, 0) + ranked(played, 1) + ranked(choices, 2) + ranked(more, 2)
    ctx.add(_card(ctx, "cleanup", "Clean-up", n or "", items))


@on("defeat")
@_safe
def _defeat(ctx: Ctx, ev: dict) -> None:
    """A carry kill's Defeated card; else the Clean-up card when a box came between the
    kill and the clean-up (its lines were folded into Defeated otherwise)."""
    folded = ctx.state.get("dft_folded") or {}
    if ctx.state.pop("dft_carry", False):
        lines = sum(cleanup_lines(ctx, ctx.i, ev, folded=True)[1:], []) if ctx.on("cleanup") else []
        shown = show_fallen(ctx, ctx.i, kill_facts(ctx, ctx.i, ctx.i, ev), lines)
    else:
        shown = folded.get(ctx.i, False)
    if not shown and ctx.on("cleanup"):
        cleanup_card(ctx, ev)
    ctx.carry.pop("dft", None)
    if not ctx.later("reveal", "won", "lost"):
        ctx.carry["dft_fallen"] = enemy_name(ctx, kill_facts(ctx, ctx.i, ctx.i, ev)["cid"])


@starter
@_safe
def _fallen_carried(ctx: Ctx) -> None:
    """The enemy of a defeat whose last step waits on a box: the next action's Victory
    names it (kept for that one action only)."""
    ctx.state["dft_fallen"] = ctx.carry.pop("dft_fallen", "")


def _choice_line(ctx: Ctx, ev: dict) -> str:
    t, who = ev.get("t"), ctx.name(ev.get("player", active(ctx)))
    label = ctx.label(ev.get("card"))
    if t == "zone_rescue":
        return "Rescued %s to the discard pile" % label
    if t == "zone_move":
        return fit("%s moved %s into the zone" % (who, label), "Moved %s into the zone" % label)
    if t == "zone_banish":
        return "Banished %s from the zone" % label
    if t == "zone_build":
        if ctx.later()[:1] and ctx.later()[0].get("t") == "zone_cleared":
            return "Zone built: %s, the zone is full" % label
        return "Zone built: %s (enemies +%d)" % (label, _int(ev.get("bonus")))
    if t == "zone_filled":
        return "Zone filled: %d banished, %d healed" % (len(ev.get("banished") or ()), _int(ev.get("healed")))
    if t == "zone_discard":
        return "Discarded %s from the zone" % label
    if t == "lake_banish":
        return "%s banished (Lake)" % count(len(ev.get("cards") or ()), "reserve card")
    # the cards below go into a hand or the reserve: counted, never named
    if t == "pile_to_reserve":
        return "A captured pile's top → reserve top"
    if t == "precision_strike":
        took = "the top discard" if ev.get("pile") == "discard" else "a zone card"
        return fit("%s took %s into hand" % (who, took), "%s took %s" % (who, took),
                   "Precision Strike: %s to hand" % took)
    if t == "restored_arrows":
        return "A banished card → under the %s" % ctx.reserve
    if t == "discard_pick":
        return "A discard → top of the %s" % ctx.reserve
    return ""


# a choice asked by a pop-up of its own: with that pop-up switched off its outcome goes too
CHOICE_ROW = {"zone_filled": "m8_filled", "precision_strike": "boon32", "restored_arrows": "boon33",
              "lake_banish": "lake"}


@on(*CHOICES)
@_safe
def _choice(ctx: Ctx, ev: dict) -> None:
    """A defeat-step choice: a line on Clean-up, or on the next card once Clean-up was
    shown (mission 8's pick after the clean-up)."""
    text = _choice_line(ctx, ev)
    if not text or not ctx.on("cleanup") or (ev.get("t") == "lake_banish" and ctx.state.get("dft_lake")):
        return
    if ev.get("t") in CHOICE_ROW and not ctx.on(CHOICE_ROW[str(ev.get("t"))]):
        return
    if "dft" in ctx.carry or any(e.get("t") == "defeat" for e in ctx.later()):
        ctx.carry.setdefault("dft", {}).setdefault("choices", []).append(text)
    else:
        ctx.line(text)


# ---------------------------------------------------------------------------- Team damage
TEAM_WHY = {"Myla": "the zone's strength", "The Hills": "the zone's strength", "Explosive Spores": "its strength"}


@on("team_damage")
@_safe
def _team_damage(ctx: Ctx, ev: dict) -> None:
    """Myla (mission 6), the Hills and Explosive Spores: the party pays together. The
    hands' total shows solo only (with 2+ players it would tell the hidden hands)."""
    damage, source = _int(ev.get("damage")), str(ev.get("source") or "The enemy")
    why = TEAM_WHY.get(source, "")
    items = [(0, fit("%s: %d, %s" % (source, damage, why), "%s: %d" % (source, damage))),
             (2, "Anyone, one at a time; no feign death")]
    if any(e.get("t") == "lost" for e in ctx.later()):
        items.append((1, "Not enough in hand: the %s is lost" % game_word(ctx)))
    elif ctx.solo and ev.get("available") is not None:
        items.append((1, "Your hand holds %d" % _int(ev.get("available"))))
    ctx.add(_card(ctx, "team_damage", "Team damage", "", items, middle=damage, caption="for the whole party"))


@on("team_damage_done", "team_damage_prevented")
@_safe
def _team_outcome(ctx: Ctx, ev: dict) -> None:
    """What the team paid, or a Guardian's prevention (the Hills card tells its own): a
    line on the next card."""
    if not ctx.on("team_damage"):
        return
    damage, source = _int(ev.get("damage")), str(ev.get("source") or "")
    if ev.get("t") == "team_damage_done":
        ctx.line("Team damage paid: %d of %d" % (_int(ev.get("paid")), damage))
    elif source != "The Hills":
        ctx.line(fit("Guardian: no team damage (%s %d)" % (source, damage), "Guardian: no team damage"))


# ---------------------------------------------------------------------------- New enemy
def bonus_source(ctx: Ctx, game: Any) -> str:
    if ctx.evergreen:
        parts = []
        if _location(ctx, game) == "C":
            parts.append("zone")
        parts += [name for n, name in ((17, "top discard"), (18, "banished top")) if _bane(game, n)]
        return " + ".join(parts)
    return {4: "top discard", 11: "pile tops"}.get(ctx.mission, "zone")


def immune_line(ctx: Ctx, game: Any, suits: Sequence[str]) -> str:
    """'Immune: ♥ + ♠ (zone)': printed, then what the zone or the pile tops add."""
    printed = list(suits)
    every = list(immune_suits(game)) if game is not None else printed
    extra = [s for s in every if s not in printed]
    parts = [icons(printed)] if printed else []
    card = ctx.g.cards.get(str(game.enemy.card_id)) if game is not None else None
    if card is not None and card.has("immune_basic") and set(BASIC_SUITS) <= set(every):
        extra = [s for s in extra if s not in BASIC_SUITS]
        parts.append("all four basics (High Arcana)")
    if extra:
        zone = ctx.mission in (3, 12) or (ctx.evergreen and _location(ctx, game) == "A")
        parts.append("%s (%s)" % (icons(extra), "zone" if zone else "pile tops"))
    if not parts:
        return "No immunity"
    line = "Immune: " + " + ".join(parts)
    if game is not None and any(_call(game.rules, "fixed_immunity", game, s, default=False) for s in every):
        line = fit(line + " · never ignored (Myla)", line)
    return fit(line)


def attack_line(ctx: Ctx, game: Any, printed: int) -> str:
    """'Attack 10 +7 zone ×2 Warrior enemy' (nothing when nothing changes it)."""
    if game is None:
        return ""
    bonus = _int(_call(game.rules, "attack_bonus", game, default=0))
    mult = _int(_call(game.rules, "attack_multiplier", game, default=1), 1)
    if not bonus and mult == 1:
        return ""
    text = "Attack %d" % printed
    if bonus:
        text += " +%d %s" % (bonus, bonus_source(ctx, game))
    if mult != 1:
        text += " ×%d %s" % (mult, "Lethal Warriors" if ctx.evergreen else "Warrior enemy")
    return fit(text, text.split(" ×")[0])


def castle_lines(ctx: Ctx, game: Any, more: int) -> List[str]:
    head = "%s more in the castle" % more if more else "The last enemy"
    r = _int(_call(game.rules, "damage_reduction", game, default=0)) if game is not None else 0
    if r <= 0:
        return [head]
    why = "Immovable Paladins" if ctx.evergreen else "Paladin enemy"
    both = "%s · takes %d less damage" % (head, r)
    return [both] if len(both) <= LINE else [head, fit("Takes %d less damage (%s)" % (r, why),
                                                         "%s: %d less damage" % (why, r))]


@on("reveal")
@_safe
def _new_enemy(ctx: Ctx, ev: dict) -> None:
    """The next enemy after a kill, as it arrives (Battle start holds the first one; with
    its row off, New enemy shows the first enemy instead)."""
    if ctx.start and ctx.on("battle_start"):
        return
    enemy = ev.get("enemy") or {}
    game = at_reveal(ctx, ctx.i)
    name = str(enemy.get("name") or enemy_name(ctx, enemy.get("card_id")))
    suits = [str(s) for s in enemy.get("suits") or ()]
    printed = _int(enemy.get("attack"))
    number = game.enemy_attack if game is not None else printed
    more = len(getattr(ctx.g, "castle", None) or ()) + len(ctx.later("reveal"))
    items = [(0, immune_line(ctx, game, suits)), (1, attack_line(ctx, game, printed))]
    items += ranked(castle_lines(ctx, game, more), 2)
    hp = enemy.get("hp", enemy.get("max_hp", ""))
    ctx.add(_card(ctx, "new_enemy", fit(name), number, items, middle=hp, caption="health", icon=class_icon(suits)))


# ---------------------------------------------------------------------------- Enemy changes
@on(*SHIFTERS)
@_safe
def _shift_point(ctx: Ctx, ev: dict) -> None:
    """Remember the card of the latest step that may have moved a pile top."""
    if not ev.get("forecast"):
        ctx.state["shift_after"] = ctx.cards[-1] if ctx.cards else None
        ctx.state["shift_seen"] = True


def shift_cause(ctx: Ctx, old: Any, new: Any) -> str:
    """What changed the enemy: the top discard, the banished top or the zone."""
    top = lambda pile, last: (pile[-1] if last else pile[0]) if pile else None
    if top(old.discard, False) != top(new.discard, False):
        cid = top(new.discard, False)
        return "top discard %s" % ctx.label(cid) if cid else "discard pile empty"
    if top(old.banished, True) != top(new.banished, True):
        cid = top(new.banished, True)
        return "banished top %s" % ctx.label(cid) if cid else "banished pile empty"
    strength = [_int(_call(game.rules, "zone_strength", game, default=0)) for game in (old, new)]
    return "zone %+d" % (strength[1] - strength[0]) if strength[1] != strength[0] else ""


@finisher
@_safe
def _enemy_shift(ctx: Ctx) -> None:
    """The enemy's attack or immunity changed in the middle of an attack (a pile top it
    reads moved) and no other card of the queue states them; not when the attack killed
    it (its defeat waiting on a box): nothing reads that enemy any more."""
    old, new = ctx.before, ctx.g
    if ctx.base or old is None or new.is_over or not ctx.state.get("shift_seen") or not ctx.on("enemy_shift"):
        return
    if any(e.get("t") in ("damage", "carry_damage") and _int(e.get("hp"), 1) <= 0 for e in ctx.events):
        return
    if old.enemy is None or new.enemy is None or old.enemy.card_id != new.enemy.card_id:
        return
    if any(c.id in STATES_ENEMY for c in ctx.cards):
        return
    a, b = raw_attack(old), raw_attack(new)
    was, now = immune_suits(old), immune_suits(new)
    if a == b and set(was) == set(now):
        return
    items = []
    if a != b:
        cause = shift_cause(ctx, old, new)
        items.append((0, fit("Attack %s → %s (%s)" % (a, b, cause), "Attack %s → %s" % (a, b)) if cause
                      else "Attack %s → %s" % (a, b)))
    if set(was) != set(now):
        line = "Immune: %s → %s" % (icons(was) or "none", icons(now) or "none")
        both = line + "; earlier ♠ shields stop counting"
        if "S" not in now or "S" in was or old.shield <= 0:
            items.append((1, line))
        elif len(both) <= LINE:
            items.append((1, both))
        else:
            items += [(1, line), (2, "Earlier ♠ shields stop counting")]
    card = _card(ctx, "enemy_shift", "Enemy changes", b, items, room=False)
    anchor = ctx.state.get("shift_after")
    at = next((k + 1 for k, c in enumerate(ctx.cards) if c is anchor), len(ctx.cards) if anchor else 0)
    ctx.cards.insert(at, card)


# ---------------------------------------------------------------------------- the strike
def strike_line(game: Any, damage: int) -> str:
    """'10 +7 − 5 shields = 12' from the game at the strike (the attack alone when its
    parts no longer add up, as in an older save)."""
    enemy = getattr(game, "enemy", None)
    if enemy is None:
        return ""
    bonus = _int(_call(game.rules, "attack_bonus", game, default=0))
    mult = _int(_call(game.rules, "attack_multiplier", game, default=1), 1)
    shield = _int(getattr(game, "shield", 0))
    if max(0, (enemy.attack + bonus) * mult - shield) != damage:
        return "Attack %d" % damage
    if not bonus and mult == 1 and not shield:
        return "Attack %d, no shields" % damage
    text = "%d" % enemy.attack + (" +%d" % bonus if bonus else "")
    if mult != 1:
        text = "(%s) ×%d" % (text, mult) if bonus else "%s ×%d" % (text, mult)
    if shield:
        text += " − %d shields" % shield
    return "%s = %d" % (text, damage)


def pay_line(ctx: Ctx, game: Any, player: Any, damage: int) -> str:
    one_by_one = bool(_call(game.rules, "sequential_discard", game, default=False))
    if ctx.solo:
        return "Discard one at a time; stop once covered" if one_by_one else "Discard cards worth %d or more" % damage
    who = ctx.name(player)
    if one_by_one:
        return fit("%s discards one at a time until covered" % who, "%s: one at a time, until covered" % who,
                   "%s pays, one card at a time" % who, "%s: one card at a time" % who, "%s pays" % who)
    return fit("%s discards cards worth %d or more" % (who, damage), "%s discards %d or more" % (who, damage),
               "%s: %d or more" % (who, damage), "%s pays" % who)


@on("suffer_due")
@_safe
def _enemy_attack(ctx: Ctx, ev: dict) -> None:
    """The enemy strikes: what it deals, how to pay and what if the hand is short."""
    game, damage, player = ctx.g, _int(ev.get("damage")), ev.get("player", active(ctx))
    items = [(1, strike_line(game, damage)), (2, pay_line(ctx, game, player, damage))]
    hand = _int(_call(game, "hand_defence_value", _int(player), default=damage))
    if any(e.get("t") == "lost" for e in ctx.later()):
        items.append((0, "Not enough in hand: the %s is lost" % game_word(ctx)))
    elif hand < damage and _call(game, "feign_death_available", default=False):
        items.append((0, "Not enough in hand: feign death instead"))
    elif hand < damage and _call(game, "can_use_solo_jester", default=False):
        items.append((0, "Not enough in hand: use a Jester"))
    raw = raw_attack(game)
    ctx.add(_card(ctx, "enemy_attack", "Enemy attacks", raw if raw is not None else damage, items,
                  middle=damage, caption="to discard"))


@on("no_damage")
@_safe
def _shielded(ctx: Ctx, ev: dict) -> None:
    """No damage: the shields cover the attack, or a Guardian protects the party (the
    Guardian card, when it showed, stands in for this one)."""
    if ctx.state.get("guardian_shown"):
        return
    game = rewound(ctx, ctx.i)
    attack = raw_attack(game)
    if ev.get("guardian"):
        items, icon = [(0, "A Guardian protects the party")], "G"
    else:
        shield = _int(getattr(game, "shield", 0))
        cover = "Shields %d cover the attack %s" % (shield, attack) if attack is not None and shield >= attack \
            else "The shields cover the attack"
        items, icon = [(0, cover)], None
    items.append((1, "Nothing to discard; the turn ends"))
    ctx.add(_card(ctx, "shielded", "No damage", attack if attack is not None else "", items, middle=0,
                  caption="to discard", icon=icon))


# ---------------------------------------------------------------------------- the suffer
@on("feign_death")
@_safe
def _feign_death(ctx: Ctx, ev: dict) -> None:
    n, damage = len(ev.get("cards") or ()), _int(ev.get("damage"))
    who = ctx.name(ev.get("player", active(ctx)))
    head = "You discard the whole hand" if ctx.solo else "%s discards the whole hand" % who
    items = [(0, fit("%s: %s" % (head, count(n, "card")), head, "%s discards all %s" % (who, count(n, "card")),
                     "%s: the whole hand" % who)),
             (1, "At the limit (%d) it covers any damage" % ctx.g.config.max_hand),
             (2, "%d damage satisfied" % damage)]
    ctx.add(_card(ctx, "feign_death", "Feign death", damage, items))


@on("suffer")
@_safe
def _damage_paid(ctx: Ctx, ev: dict) -> None:
    """What was discarded (the discard pile is face up; A Close Call's cards go under the
    reserve, so they are counted) and the hand left."""
    cards = [str(c) for c in ev.get("cards") or ()]
    player = _int(ev.get("player", active(ctx)))
    who = ctx.name(player)
    hidden = any(e.get("t") == "close_call" for e in ctx.earlier())
    head = "%s discarded %d" % (who, len(cards))
    first, named = head + " " + ("card" if len(cards) == 1 else "cards"), ""
    if not hidden and cards:
        one = "%s: %s" % (head, ctx.labels(cards))
        if len(one) <= LINE:
            first = one
        else:
            named = ctx.labels(cards)          # a long name: the cards on their own line
    try:
        hand = len(ctx.before.players[player].hand) - len(cards)
    except Exception:
        hand = len(ctx.g.players[player].hand) if 0 <= player < len(ctx.g.players) else 0
    items = [(0, first), (2, named), (1, "Hand: %d left" % max(0, hand))]
    ctx.add(_card(ctx, "damage_paid", "Damage paid", _int(ev.get("damage")), items, middle=_int(ev.get("paid")),
                  caption="paid"))


# ---------------------------------------------------------------------------- Victory, Defeat
def last_fallen(ctx: Ctx) -> str:
    """The enemy whose defeat won the game (an earlier action's, when a box after the
    clean-up held the win: mission 8's pick)."""
    for e in reversed(ctx.events):
        if e.get("t") == "defeat":
            return enemy_name(ctx, e.get("enemy"))
    return str(ctx.state.get("dft_fallen") or "")


def victory_card(ctx: Ctx, ev: dict) -> InfoCard:
    result = str(ev.get("result", ""))
    title = "Victory!"
    if ctx.base and ctx.solo and result in ("gold", "silver", "bronze"):
        title = "%s victory!" % result.capitalize()
    name = last_fallen(ctx)
    turns = _int(getattr(ctx.g, "turn", 0))
    took = count(turns, "turn") if turns else ""
    both = "%s was the last enemy, in %s" % (name, took)
    if name and took and len(both) <= LINE:
        items = [(0, both)]
    else:
        items = [(0, fit("%s was the last enemy" % name) if name else ""), (2, "Won in %s" % took if took else "")]
    if ctx.base and ctx.solo:
        items.append((1, "Jesters used: %d" % _int(getattr(ctx.g, "solo_jesters_used", 0))))
    if not ctx.base and not ctx.evergreen and ctx.mission:
        items.append((1, "Mission %d complete: rewards next" % ctx.mission))
    return _card(ctx, "victory", title, "", items)


def loss_reason(ctx: Ctx, k: int, ev: dict) -> str:
    """Why the game was lost, from the event before it (else the engine's reason)."""
    prev = ctx.events[k - 1] if k > 0 else {}
    reason = str(ev.get("reason") or "")
    t = prev.get("t")
    if t == "suffer_due" or ("cannot suffer" in reason and "team" not in reason.lower()):
        damage = _int(prev.get("damage") if t == "suffer_due" else getattr(ctx.g, "pending_damage", 0))
        who = ctx.name(prev.get("player", active(ctx)))
        if ctx.solo:
            return "Cannot pay %d damage" % damage
        return fit("%s cannot pay %d damage" % (who, damage), "%s cannot pay %d" % (who, damage))
    if t == "team_damage" or "team cannot" in reason.lower():
        return "Team damage too high"
    if "abandon" in reason.lower() or not prev:
        return "Abandoned"
    who = ctx.name(active(ctx))
    return "No legal play or yield" if ctx.solo else fit("%s: no legal play or yield" % who, "No legal play or yield")


def loss_card(ctx: Ctx, k: int, ev: dict) -> InfoCard:
    title = "Defeat" if ctx.base or ctx.evergreen else "Mission lost"
    enemy = getattr(ctx.g, "enemy", None)
    items = [(0, loss_reason(ctx, k, ev))]
    alive = enemy is not None and enemy.hp > 0
    left = len(getattr(ctx.g, "castle", None) or ()) + (1 if alive else 0)
    enemies = "1 enemy left" if left == 1 else "%d enemies left" % left
    if alive:
        hp = "%s: %d health left" % (enemy.name, enemy.hp)
        both = "%s · %s" % (hp, enemies)
        items += [(1, both)] if len(both) <= LINE else [(1, fit(hp, "%d health left" % enemy.hp)), (2, enemies)]
    elif enemy is not None:
        items.append((1, fit("%s fell; %s" % (enemy.name, enemies), enemies)))
    else:
        items.append((1, enemies))
    coins = _int(ctx.app.get("coins_on_loss"))
    if coins > 0:
        # rulebook p.25: each loss of a mission earns as many coins as it has been lost
        items.append((2, "+%d coin%s (loss %d on this mission)" % (coins, "" if coins == 1 else "s", coins)))
    return _card(ctx, "loss", title, "", items)


@last
@_safe
def _game_end(ctx: Ctx) -> None:
    """Victory or Defeat: always the last card of the queue (its clip is the jingle)."""
    for k in range(len(ctx.events) - 1, -1, -1):
        ev = ctx.events[k]
        if ev.get("t") == "won":
            ctx.add(victory_card(ctx, ev))
            return
        if ev.get("t") == "lost":
            ctx.add(loss_card(ctx, k, ev))
            return
