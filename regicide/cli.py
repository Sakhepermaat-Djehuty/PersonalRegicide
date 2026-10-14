"""Text client. Works in a terminal and in the Pythonista console.

    python -m regicide.cli --players 2 --seed 7
    python -m regicide.cli --load saves/cli.json
    python -m regicide.cli --players 1 --bot      (watch the heuristic bot play)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from .bots import apply_action, greedy_policy, min_waste_discard
from .engine import PHASE_CHOOSE_NEXT, PHASE_DECIDE, PHASE_PLAY, PHASE_SUFFER, Game, IllegalAction
from .rules import GameConfig

DEFAULT_SAVE = os.path.join("saves", "cli.json")


def save_game(game: Game, path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w") as f:
        json.dump(game.to_dict(), f)


def load_game(path: str) -> Game:
    with open(path) as f:
        return Game.from_dict(json.load(f))


def show(game: Game) -> None:
    print()
    print(game.summary())
    for line in game.log[-6:]:
        print("  > " + line)
    if game.is_over:
        return
    seat = game.deciding
    p = game.players[seat]
    print("%s's hand (%d/%d):" % (p.name, len(p.hand), game.config.max_hand))
    for i, c in enumerate(game.hand(seat), 1):
        print("  %2d. %s" % (i, c.label()))


def parse_indices(text: str, n: int) -> Optional[List[int]]:
    out: List[int] = []
    for tok in text.replace(",", " ").split():
        if not tok.isdigit():
            return None
        i = int(tok)
        if not 1 <= i <= n:
            return None
        out.append(i - 1)
    return out


def human_turn(game: Game, save_path: Optional[str]) -> bool:
    """Prompt once; return False to quit."""
    hand = game.hand()
    if game.phase == PHASE_PLAY:
        opts = "numbers=play"
        if game.can_yield():
            opts += ", y=yield"
        if game.can_use_solo_jester():
            opts += ", j=Jester power"
        opts += ", h=hint, s=save, q=quit"
        ans = input("[%s] > " % opts).strip().lower()
        if ans == "q":
            return False
        if ans == "s":
            save_game(game, save_path or DEFAULT_SAVE)
            print("saved to", save_path or DEFAULT_SAVE)
            return True
        if ans == "h":
            act = greedy_policy(game)
            if act["type"] == "play":
                print("hint: play " + " + ".join(game.card(c).label() for c in act["cards"]))
            else:
                print("hint:", act["type"])
            return True
        try:
            if ans == "y":
                game.yield_turn()
            elif ans == "j":
                game.use_solo_jester()
            else:
                idx = parse_indices(ans, len(hand))
                if not idx:
                    print("type card numbers separated by spaces")
                    return True
                game.play([hand[i].id for i in idx])
        except IllegalAction as e:
            print("!", e)
        return True
    if game.phase == PHASE_SUFFER:
        sugg = min_waste_discard(game)
        print("Suffer %d damage. Suggested: %s" % (
            game.pending_damage, " ".join(game.card(c).label() for c in sugg) or "-"))
        opts = "numbers=discard, a=accept suggestion"
        if game.can_use_solo_jester():
            opts += ", j=Jester power"
        ans = input("[%s, q=quit] > " % opts).strip().lower()
        if ans == "q":
            return False
        try:
            if ans == "a":
                game.suffer(sugg)
            elif ans == "j":
                game.use_solo_jester()
            else:
                idx = parse_indices(ans, len(hand))
                if idx is None:
                    print("type card numbers separated by spaces")
                    return True
                game.suffer([hand[i].id for i in idx])
        except IllegalAction as e:
            print("!", e)
        return True
    if game.phase == PHASE_CHOOSE_NEXT:
        names = ", ".join("%d=%s" % (i + 1, p.name) for i, p in enumerate(game.players))
        ans = input("Who goes next? [%s] > " % names).strip()
        try:
            game.choose_next(int(ans) - 1)
        except (ValueError, IllegalAction) as e:
            print("!", e)
        return True
    if game.phase == PHASE_DECIDE and (game.decision or {}).get("kind") == "mage_peek":
        # Mage: the attacker looks at the revealed reserve cards and adds one to the attack.
        d = game.decision or {}
        revealed = [game.card(c) for c in d.get("revealed", [])]
        eligible = [str(c) for c in d.get("eligible", [])]
        print("Mage: %d card%s revealed from the reserve deck%s" % (
            len(revealed), "" if len(revealed) == 1 else "s", ":" if revealed else " (it is empty)."))
        for i, c in enumerate(revealed, 1):
            note = "" if c.id in eligible else "   (%s: discarded)" % ("Jester" if c.is_jester else "corrupted")
            print("  %2d. %s%s" % (i, c.label(), note))
        if eligible:
            ans = input("[number=add that card to the attack, q=quit] > ").strip().lower()
        else:
            ans = input("Nothing may join the attack. [enter=continue, q=quit] > ").strip().lower()
        if ans == "q":
            return False
        try:
            if not eligible:
                game.decide({"type": "mage_skip"})
            else:
                idx = parse_indices(ans, len(revealed))
                if not idx or len(idx) != 1:
                    print("type the number of one revealed card")
                    return True
                game.decide({"type": "mage_pick", "card": revealed[idx[0]].id})
        except IllegalAction as e:
            print("!", e)
        return True
    if game.phase == PHASE_DECIDE and (game.decision or {}).get("kind") == "whistle_add":
        # Scarlet Whistle, 2+ players: another player may add one card (not a Jester).
        d = game.decision or {}
        hand = game.hand(game.deciding)
        play = game.plays[int(d.get("play_index", len(game.plays) - 1))]
        print("Scarlet Whistle: %s may add one card to %s's %s attack." % (
            game.players[game.deciding].name, game.players[play.player].name,
            " + ".join(game.card(c).label() for c in play.card_ids)))
        ans = input("[number=add that card, p=pass, q=quit] > ").strip().lower()
        if ans == "q":
            return False
        try:
            if ans == "p":
                game.decide({"type": "whistle_pass"})
            else:
                idx = parse_indices(ans, len(hand))
                if not idx or len(idx) != 1:
                    print("type the number of one card, or p to pass")
                    return True
                game.decide({"type": "whistle_add", "card": hand[idx[0]].id})
        except IllegalAction as e:
            print("!", e)
        return True
    if game.phase == PHASE_DECIDE and (game.decision or {}).get("kind") == "druid_assign":
        # Druid: the dealt cards are assigned one per destination (banish, hand, top, bottom).
        d = game.decision or {}
        template = [a for a in game.legal_actions() if a["type"] == "druid_assign"][0]
        dealt = [game.card(c) for c in template["pick_from"]]
        needs = int(template["needs"])
        print("Druid: %s was dealt %d card%s from the shuffled discard pile:" % (
            game.players[game.deciding].name, len(dealt), "" if len(dealt) == 1 else "s"))
        for i, c in enumerate(dealt, 1):
            print("  %2d. %s" % (i, c.label()))
        print("Assign %d card%s, one per destination (enter=leave a destination empty, q=quit)." % (
            needs, "" if needs == 1 else "s"))
        act = {"type": "druid_assign", "player": game.deciding}
        used = set()
        for slot, title in (("banish", "banished"), ("hand", "to your hand"), ("top", "on top of the reserve"),
                            ("bottom", "under the reserve")):
            if len(used) >= needs:
                break
            ans = input("  card %s > " % title).strip().lower()
            if ans == "q":
                return False
            if not ans:
                continue
            idx = parse_indices(ans, len(dealt))
            if not idx or len(idx) != 1 or dealt[idx[0]].id in used:
                print("type the number of one card not yet assigned")
                return True
            act[slot] = dealt[idx[0]].id
            used.add(dealt[idx[0]].id)
        try:
            game.decide(act)
        except IllegalAction as e:
            print("!", e)
        return True
    if game.phase == PHASE_DECIDE and (game.decision or {}).get("kind") in ("chanter_discard", "discard_banish",
                                                                             "banish_order", "zone_order"):
        # Templates filled in with a list of cards: the Chanter's discard down to the limit,
        # mission 8's banish from the discard pile (any number, enter for none), the order in
        # which a mission zone is banished (mission 12) or discarded (Evergreen's Lake).
        d = game.decision or {}
        kind = str(d.get("kind"))
        acts = game.legal_actions()
        template = [a for a in acts if "needs" in a][0] if any("needs" in a for a in acts) else None
        pool = [game.card(c) for c in (template or {}).get("pick_from", [])]
        if kind == "chanter_discard":
            print("Chanter: %s holds %d cards and must discard %d:" % (
                game.players[game.deciding].name, len(game.players[game.deciding].hand), int(template["needs"])))
        elif kind in ("banish_order", "zone_order"):
            print("Enemy defeated: name every mission zone card in the order it goes to the %s pile (the last ends on top):" % (
                "banished" if kind == "banish_order" else "discard"))
        else:
            print("Mission zone filled: banish any cards from the discard pile (the rest heals under the reserve):")
        for i, c in enumerate(pool, 1):
            print("  %2d. %s" % (i, c.label()))
        ans = input("[numbers=choose those cards%s, q=quit] > " % (", enter=none" if kind == "discard_banish" else "")).strip().lower()
        if ans == "q":
            return False
        try:
            if not ans and kind == "discard_banish":
                game.decide({"type": "discard_banish_skip"})
                return True
            idx = parse_indices(ans, len(pool))
            if idx is None:
                print("type card numbers separated by spaces")
                return True
            game.decide({"type": kind, "player": game.deciding, "cards": [pool[i].id for i in idx]})
        except IllegalAction as e:
            print("!", e)
        return True
    if game.phase == PHASE_DECIDE and (game.decision or {}).get("kind") != "flute_add":
        # A choice offered as a short list: which mission zone card to rescue, the Azure
        # Emblem's keep (solo) or place (another player's card goes on the reserve), the
        # Scarlet Whistle's take, the Reaver's count and pick, the clean-up order, the
        # card moved to the mission zone, Myla's team damage.
        d = game.decision or {}
        if d.get("kind") == "emblem_keep":
            print("Azure Emblem: %s may put one of the other revealed cards back on top of the reserve deck." % (
                game.players[game.deciding].name))
        elif d.get("kind") == "emblem_place":
            print("Azure Emblem: %s may place one card from hand on top of the reserve deck before %s's mage looks." % (
                game.players[game.deciding].name, game.players[game.active].name))
        elif d.get("kind") == "reaver_count":
            print("Reaver: how many cards does %s reveal from the reserve deck?" % game.players[game.deciding].name)
        elif d.get("kind") == "reaver_pick":
            print("Reaver: revealed %s. Which strength is added to the damage?" % (
                " + ".join(game.card(c).label() for c in d.get("revealed", []))))
        elif d.get("kind") == "team_discard":
            print("Team damage: %d to go. Any player discards one card." % (int(d.get("damage", 0)) - int(d.get("paid", 0))))
        elif d.get("kind") == "chanter_declare":
            print("Chanter: %s declares how many cards everyone draws (ignoring the hand limit, then discarding down to it)." % (
                game.players[game.deciding].name))
        elif d.get("kind") == "mother_choice":
            print("Evergreen Mother: a corrupted card entered play. Banish from the discard pile or the reserve?")
        elif d.get("kind") == "mother_banish":
            print("Evergreen Mother: %s must banish one card from hand." % game.players[game.deciding].name)
        elif d.get("kind") == "pilgrim_banish":
            print("%s matches a pilgrim in the mission zone: banish one?" % game.card(str(d.get("entering"))).label())
        elif d.get("kind") == "zone_build":
            print("Enemy defeated: move a card in play to the mission zone (one strength higher than its highest)?")
        elif d.get("kind") == "pile_rescue":
            print("End of turn: banish a card from hand to rescue a captured card, or rotate the piles. Piles: %s" % (
                " / ".join(game.card(p[0]).label() if p else "empty" for p in game.extra.get("captured", []))))
        elif d.get("kind") == "zone_feed":
            print("%s must put a card from hand into the mission zone." % game.players[game.deciding].name)
        elif d.get("kind") in ("beast_discard", "beast_banish"):
            print("A %s beast was revealed: %s must %s a card from hand." % (
                "cleric" if d.get("kind") == "beast_discard" else "bard", game.players[game.deciding].name,
                "discard" if d.get("kind") == "beast_discard" else "banish"))
        elif d.get("kind") in ("precision_strike", "restored_arrows", "close_call", "zone_discard", "zone_sibling",
                               "zone_match", "attack_discard", "poison"):
            print("%s: %s" % (d.get("kind").replace("_", " ").capitalize(), game.log[-1] if game.log else ""))
        acts = game.legal_actions()
        for i, a in enumerate(acts, 1):
            print("  %2d. %s" % (i, a.get("label", a["type"])))
        ans = input("[number=choose, q=quit] > ").strip().lower()
        if ans == "q":
            return False
        idx = parse_indices(ans, len(acts))
        if not idx or len(idx) != 1:
            print("type the number of one option")
            return True
        try:
            game.decide(acts[idx[0]])
        except IllegalAction as e:
            print("!", e)
        return True
    if game.phase == PHASE_DECIDE:
        # Kinfolk Flute: another player may add kinfolk cards to the attack on the table.
        d = game.decision or {}
        hand = game.hand(game.deciding)
        play = game.plays[int(d.get("play_index", len(game.plays) - 1))]
        print("%s may add %ss to %s's attack (%s, strength %d, total at most 10)." % (
            game.players[game.deciding].name, d.get("strength"), game.players[play.player].name,
            " + ".join(game.card(c).label() for c in play.card_ids), play.value))
        ans = input("[numbers=add those cards, p=pass, q=quit] > ").strip().lower()
        if ans == "q":
            return False
        try:
            if ans == "p":
                game.flute_pass()
            else:
                idx = parse_indices(ans, len(hand))
                if not idx:
                    print("type card numbers separated by spaces, or p to pass")
                    return True
                game.flute_add([hand[i].id for i in idx])
        except IllegalAction as e:
            print("!", e)
        return True
    return True


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Regicide in the terminal")
    ap.add_argument("--players", type=int, default=1)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--load", default=None, help="resume a saved game")
    ap.add_argument("--save", default=None, help="save path (default saves/cli.json)")
    ap.add_argument("--bot", action="store_true", help="let the heuristic bot play every seat")
    ap.add_argument("--bots", default="", help="comma separated seat numbers played by the bot, e.g. 2,3")
    args = ap.parse_args(argv)

    if args.load:
        game = load_game(args.load)
    else:
        game = Game.new(GameConfig(players=args.players), seed=args.seed)
    bot_seats = set()
    if args.bot:
        bot_seats = set(range(game.n_players))
    for tok in args.bots.split(","):
        if tok.strip().isdigit():
            bot_seats.add(int(tok) - 1)

    while not game.is_over:
        show(game)
        if game.deciding in bot_seats:
            act = greedy_policy(game)
            if act["type"] == "play":
                print("bot plays " + " + ".join(game.card(c).label() for c in act["cards"]))
            elif act["type"] == "flute_add":
                print("bot adds " + " + ".join(game.card(c).label() for c in act["card_ids"]))
            elif act["type"] == "mage_pick":
                print("bot adds %s to the attack (Mage)" % game.card(act["card"]).label())
            elif act["type"] == "emblem_place":
                print("bot places a card on top of the reserve (Azure Emblem)")
            elif act["type"] == "whistle_add":
                print("bot adds %s to the attack (Scarlet Whistle)" % game.card(act["card"]).label())
            elif act["type"] == "druid_assign":
                print("bot sorts the dealt cards (Druid)")
            elif act["type"] in ("chanter_discard", "discard_banish", "banish_order", "zone_order"):
                print("bot picks %s" % (" + ".join(game.card(c).label() for c in act.get("cards", [])) or "nothing"))
            else:
                print("bot:", act.get("label", act["type"]))
            apply_action(game, act)
            continue
        if not human_turn(game, args.save):
            print("bye")
            return 0
    show(game)
    print("Result:", game.result, game.loss_reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
