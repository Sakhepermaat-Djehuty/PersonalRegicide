"""Builders for hand-crafted game states."""
from __future__ import annotations

from typing import List, Optional, Sequence

from regicide.cards import make_card
from regicide.engine import PHASE_PLAY, Enemy, Game
from regicide.rules import GameConfig


def new_game(players: int = 1, seed: int = 1, **cfg) -> Game:
    return Game.new(GameConfig(players=players, **cfg), seed=seed)


def set_hand(g: Game, ids: Sequence[str], player: int = 0) -> None:
    """Give a player exactly these cards, pulling them from wherever they are."""
    for cid in ids:
        _pull(g, cid)
    # return the player's current hand to the tavern bottom
    old = list(g.players[player].hand)
    g.players[player].hand = []
    for cid in old:
        if cid not in ids:
            g.tavern.append(cid)
    g.players[player].hand = list(ids)


def set_enemy(g: Game, rank: str, suit: str, hp: Optional[int] = None, attack: Optional[int] = None) -> None:
    cid = rank + suit
    # make sure the chosen royal is not somewhere else
    if g.enemy and g.enemy.card_id != cid:
        g.castle.insert(0, g.enemy.card_id)
    _pull(g, cid)
    card = g.cards[cid]
    atk, mhp = g.rules.enemy_stats(g, card)
    if hp is not None:
        mhp = hp
    if attack is not None:
        atk = attack
    names = {"J": "Jack", "Q": "Queen", "K": "King"}
    g.enemy = Enemy(cid, "%s of %s" % (names[rank], suit), (suit,), atk, mhp, mhp)
    g.plays = []
    g.immunity_cancelled = False
    g.phase = PHASE_PLAY


def set_tavern_top(g: Game, ids: Sequence[str]) -> None:
    for cid in ids:
        _pull(g, cid)
    g.tavern = list(ids) + g.tavern


def set_discard(g: Game, ids: Sequence[str]) -> None:
    for cid in ids:
        _pull(g, cid)
    g.discard = list(ids)


def _pull(g: Game, cid: str) -> None:
    """Remove a card id from any zone it sits in (no-op if absent)."""
    for p in g.players:
        if cid in p.hand:
            p.hand.remove(cid)
            return
    for pile in (g.tavern, g.castle, g.discard, g.banished, g.mission_zone):
        if cid in pile:
            pile.remove(cid)
            return
    for play in g.plays:
        if cid in play.card_ids:
            play.card_ids.remove(cid)
            return
    if g.enemy and g.enemy.card_id == cid:
        g.enemy = None
