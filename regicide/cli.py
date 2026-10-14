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
            else:
                print("bot:", act["type"])
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
