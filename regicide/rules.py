"""Game configuration and the rule hooks that Legacy missions override.

``GameConfig`` is pure data (serialisable). ``BaseRules`` is behaviour: the engine calls
its hooks at well-defined points so that a mission can change enemy immunity, add
attack bonuses, react to played cards, decide what happens to a defeated enemy, and
resolve suit powers the base game does not have. The base game uses ``BaseRules``
unchanged; missions subclass it (see ``regicide/campaign``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

from .cards import CLUBS, DIAMONDS, HEARTS, SPADES, Card

if TYPE_CHECKING:  # pragma: no cover
    from .engine import Game

# Official setup table: players -> (max hand size, Jesters shuffled into the tavern deck)
HAND_SIZE: Dict[int, int] = {1: 8, 2: 7, 3: 6, 4: 5}
JESTERS_IN_DECK: Dict[int, int] = {1: 0, 2: 0, 3: 1, 4: 2}
SOLO_JESTER_POWERS = 2


@dataclass
class GameConfig:
    players: int = 1
    names: Tuple[str, ...] = ()
    hand_size: Optional[int] = None        # None = official table
    jesters: Optional[int] = None          # None = official table (deck Jesters, or solo powers)
    jester_may_choose_self: bool = True    # see docs/RULES_BASE.md, open point
    open_hands: bool = False               # UI hint only: one person drives all seats
    solo_can_yield: bool = False           # unofficial variant
    yield_reset_per_enemy: bool = False    # unofficial variant: forget yields on a new enemy
    strict_minimal_discard: bool = False   # base game, unofficial variant: no surplus cards when paying
    rules_id: str = "base"
    extra: Dict[str, Any] = field(default_factory=dict)  # mission / variant parameters

    def __post_init__(self) -> None:
        if not 1 <= self.players <= 4:
            raise ValueError("players must be 1..4")
        names = list(self.names)
        while len(names) < self.players:
            names.append("Player %d" % (len(names) + 1))
        self.names = tuple(names[: self.players])

    @property
    def max_hand(self) -> int:
        return self.hand_size if self.hand_size is not None else HAND_SIZE[self.players]

    @property
    def deck_jesters(self) -> int:
        """Jesters shuffled into the tavern deck (0 in solo: they are powers instead)."""
        if self.players == 1:
            return 0
        return self.jesters if self.jesters is not None else JESTERS_IN_DECK[self.players]

    @property
    def solo_jesters(self) -> int:
        if self.players != 1:
            return 0
        return self.jesters if self.jesters is not None else SOLO_JESTER_POWERS

    def to_dict(self) -> dict:
        return {
            "players": self.players, "names": list(self.names), "hand_size": self.hand_size,
            "jesters": self.jesters, "jester_may_choose_self": self.jester_may_choose_self,
            "open_hands": self.open_hands, "rules_id": self.rules_id, "extra": dict(self.extra),
            "solo_can_yield": self.solo_can_yield, "yield_reset_per_enemy": self.yield_reset_per_enemy,
            "strict_minimal_discard": self.strict_minimal_discard,
        }

    @staticmethod
    def from_dict(d: dict) -> "GameConfig":
        return GameConfig(
            players=int(d.get("players", 1)), names=tuple(d.get("names", ())),
            hand_size=d.get("hand_size"), jesters=d.get("jesters"),
            jester_may_choose_self=bool(d.get("jester_may_choose_self", True)),
            open_hands=bool(d.get("open_hands", False)), rules_id=d.get("rules_id", "base"),
            extra=dict(d.get("extra", {})),
            solo_can_yield=bool(d.get("solo_can_yield", False)),
            yield_reset_per_enemy=bool(d.get("yield_reset_per_enemy", False)),
            strict_minimal_discard=bool(d.get("strict_minimal_discard", False)),
        )


class BaseRules:
    """Hooks with base-game behaviour. Missions override what they need."""

    id = "base"
    # Order in which suit powers resolve. Hearts before Diamonds is an explicit official
    # rule; Clubs and Spades only matter for damage / defence so they come last.
    power_order: Tuple[str, ...] = (HEARTS, DIAMONDS, CLUBS, SPADES)
    # Clean-up order when an enemy falls: Legacy (p.19) moves the enemy first and puts the
    # played cards on top of the discard pile; the base game leaves the enemy on top.
    played_on_top: bool = False

    # --- setup ---------------------------------------------------------------
    def build_decks(self, game: "Game") -> None:
        """Populate game.cards, game.tavern and game.castle (ids). Base: official decks."""
        from .cards import build_castle, build_tavern, card_table
        tavern = build_tavern(game.config.deck_jesters)
        castle = build_castle(game.rng)
        game.cards = card_table(tavern + castle)
        game.rng.shuffle(tavern)
        game.tavern = [c.id for c in tavern]
        game.castle = [c.id for c in castle]

    def enemy_stats(self, game: "Game", card: Card) -> Tuple[int, int]:
        """(attack, health) for a revealed castle card."""
        from .cards import ROYAL_ATTACK, ROYAL_HEALTH
        if card.attack or card.health:
            return card.attack, card.health
        return ROYAL_ATTACK[card.rank], ROYAL_HEALTH[card.rank]

    # --- queries ---------------------------------------------------------------
    def immune(self, game: "Game", suit: str, cards: Sequence[Card] = ()) -> bool:
        """Is the enemy immune to this suit's power, for a play of ``cards``?"""
        enemy = game.enemy
        if enemy is None:
            return False
        if game.immunity_cancelled:
            return False
        return suit in enemy.suits

    def playable_ids(self, game: "Game") -> List[str]:
        """Card ids the active player may include in a play (hand, plus e.g. a flute)."""
        return [cid for cid in game.active_player.hand if not self.hand_locked(game, game.cards[cid])]

    def hand_locked(self, game: "Game", card: Card) -> bool:
        """May this card never leave its holder's hand (Legacy mission 7's pilgrims)? A
        locked card cannot be played, discarded to suffer damage (so it blocks feigning
        death and pays nothing), banished or moved by any effect that takes a card from a
        hand; it still counts against the hand limit."""
        return False

    def fixed_immunity(self, game: "Game", suit: str) -> bool:
        """Is the enemy's immunity to ``suit`` one that nothing can ignore (Legacy mission
        9's Myla): not a corrupted or restored card, not a claimed Jester's attack?"""
        return False

    def extra_card_ids(self, game: "Game") -> List[str]:
        """Card ids the rules keep outside the engine's piles (a mission's own decks)."""
        return []

    def remove_played(self, game: "Game", card_id: str) -> None:
        """Take a card out of wherever playable_ids() offered it from."""
        game.active_player.hand.remove(card_id)

    def jester_mode(self, game: "Game") -> str:
        """'base': cancel immunity for the fight, choose who goes next.
        'claim': (Legacy) a player claims the Jester and attacks now ignoring immunity."""
        return "base"

    def solo_jester_mode(self, game: "Game") -> str:
        """'refresh': discard hand and draw to the limit (base game).
        'attack': (Legacy) a strength-8 attack of a chosen basic class ignoring immunity."""
        return "refresh"

    def feign_death_allowed(self, game: "Game") -> bool:
        """May the active player discard their whole hand to satisfy any damage?"""
        return False

    def special_actions(self, game: "Game") -> List[Dict[str, Any]]:
        """Extra actions (relics, mission choices) available right now."""
        return []

    def do_special(self, game: "Game", action: Dict[str, Any]) -> None:
        raise NotImplementedError("no special actions in these rules")

    def attack_bonus(self, game: "Game") -> int:
        """Added to the enemy's printed attack before shields (Legacy missions)."""
        return 0

    def attack_multiplier(self, game: "Game") -> int:
        """Multiplies the enemy's total strength (printed plus bonus) before the paladin
        shields are subtracted (Legacy mission 10's warriors double it)."""
        return 1

    def damage_reduction(self, game: "Game") -> int:
        """Subtracted from the damage a combo deals (Legacy mission 10)."""
        return 0

    def kinfolk_limit(self, game: "Game") -> int:
        """The most a set / kinfolk attack may total (10; an Evergreen boon makes it 12)."""
        return 10

    def card_suits(self, game: "Game", card: Card) -> Tuple[str, ...]:
        """The classes a card brings to an attack (its printed suits; an Evergreen boon
        gives the puppy all four basic classes while it is played)."""
        return tuple(card.suits)

    def banish_redirect(self, game: "Game", card: Card) -> Optional[str]:
        """Where a card goes instead of the banished pile, or None for the pile itself.
        ``"reserve_bottom"``: under the reserve deck (Legacy mission 12's restored relic:
        restored cards can never enter the banished pile)."""
        return None

    def reserve_redirect(self, game: "Game", card: Card) -> Optional[str]:
        """Where a card goes instead of the reserve deck, or None for the deck itself.
        ``"banished_bottom"``: the bottom of the banished pile (Legacy mission 12:
        corrupted cards can never enter the reserve deck)."""
        return None

    def discard_suffered(self, game: "Game", cards: Sequence[Card], damage: int, feign: bool) -> None:
        """Put the cards a player discarded to suffer damage where they go (the discard
        pile; an Evergreen boon sends an exact payment under the reserve deck)."""
        game._discard_cards(list(cards))

    def after_suffer(self, game: "Game", cards: Sequence[Card], damage: int, feign: bool) -> Optional[Dict[str, Any]]:
        """Called after a player paid the enemy's damage and before the end-of-turn
        effects. Return a decision dict (with a ``player``) to ask something first (the
        rules' ``decide`` then ends with ``game.resume_suffered()``), or None."""
        return None

    def can_yield(self, game: "Game") -> bool:
        """Official: "A player may not yield if every other player has yielded on their
        last turn." With one player the condition is vacuously true, so solo never yields."""
        me = game.active
        if game.n_players == 1:
            return bool(game.config.solo_can_yield) and game.last_action[0] != "yielded"
        return not all(game.last_action[i] == "yielded" for i in range(game.n_players) if i != me)

    def sequential_discard(self, game: "Game") -> bool:
        """Must damage be paid one card at a time (rulebook p.18: "you may not keep
        discarding once the damage is satisfied")? ``Game.suffer`` then validates the cards
        in the order given: the total before the last card must be below the damage. The
        base game accepts surplus unless ``config.strict_minimal_discard`` is set; Legacy
        always applies the sequential rule."""
        return False

    def discard_top_matters(self, game: "Game") -> bool:
        """Does the TOP card of the discard pile change the game right now (Legacy mission
        4's enemy bonus, the solo Scarlet Whistle, ...)? When it does, the player is asked
        which card ends on top whenever two or more cards go to the pile at once (the
        clean-up, a mage's unchosen cards); otherwise the default order is used."""
        return False

    def banished_top_matters(self, game: "Game") -> bool:
        """Does the TOP card of the banished pile change the game (Legacy missions 5, 11 and
        12 feed it into the mission zone)? When it does, the player orders the cards a
        reaver or a mage attack banishes together."""
        return False

    def extra_plays(self, game: "Game", hand: Sequence[Card]) -> List[List[str]]:
        """Additional legal plays beyond singles / companions / sets (Legacy: beasts...)."""
        return []

    def set_strengths(self, game: "Game", card: Card) -> Tuple[int, ...]:
        """The strengths a card may take in a set, for ``Game.legal_plays``: its value in
        the base game; Legacy's 2/5 mercenary may count 2 or 5 there."""
        return (self.play_value(game, [card]),)

    def validate_combo(self, game: "Game", cards: Sequence[Card]) -> Tuple[str, Optional[str]]:
        """Return (kind, error). Kinds: single, jester, companion, set."""
        return classify_combo(cards)

    def after_attack_formed(self, game: "Game", play: Any) -> Optional[Dict[str, Any]]:
        """Called after a non-Jester play is recorded and before its abilities resolve.

        Return a serialisable decision dict to pause the game in the decide phase (another
        player gets to act first, e.g. the Kinfolk Flute), or None to resolve at once.
        The dict must carry ``kind`` and the index of the deciding ``player``; the engine
        adds the ``play_index`` of the attack it concerns and stores it as ``game.decision``."""
        return None

    def before_defeat(self, game: "Game", exact: bool) -> Optional[Dict[str, Any]]:
        """Called when the enemy's health reaches 0, before the enemy-defeated steps.

        Return a serialisable decision dict (with a ``player``) to ask the current player
        something first (e.g. which mission zone card to rescue); the rules' ``decide``
        must then end with ``game.resume_defeat()``. None continues at once."""
        return None

    def before_cleanup(self, game: "Game", exact: bool, plan: Dict[str, Any], discard_ids: Sequence[str],
                       banish_ids: Sequence[str]) -> Optional[Dict[str, Any]]:
        """Called once the mission's enemy-defeated choices are made and before the played
        cards are cleaned up: ``discard_ids`` go on top of the discard pile, ``banish_ids``
        (a mage attack) on the banished pile. Return a decision dict (with a ``player``) to
        ask about their order (Legacy: which card ends on top); the rules' ``decide`` must
        then end with ``game.resume_defeat()``, which asks here again, so the rules must
        record the choice where this hook can see it (``order_for_discard`` and
        ``order_for_banish`` then apply it). None cleans up at once."""
        return None

    def immune_suits(self, game: "Game") -> Tuple[str, ...]:
        """Every suit the current enemy is immune to right now (for displays)."""
        enemy = game.enemy
        if enemy is None or game.immunity_cancelled:
            return ()
        return tuple(enemy.suits)

    def decision_actions(self, game: "Game") -> List[Dict[str, Any]]:
        """Legal actions for the deciding player while ``game.decision`` is pending.

        Each action is a dict with a ``type``; exactly one may be marked ``"skip": True``
        (the "do nothing" choice, used by forecasts and the one-ply bot)."""
        return []

    def decide(self, game: "Game", action: Dict[str, Any]) -> None:
        """Apply one of ``decision_actions``. Must end by advancing the decision or by
        calling ``game.resolve_pending_attack()`` / ``game.resume_defeat()``."""
        raise NotImplementedError("no decisions in these rules")

    def forecast_action(self, game: "Game") -> Optional[Dict[str, Any]]:
        """The action a forecast (``Game.preview_play``) assumes for the pending decision:
        the "do nothing" option by default. Rules may return an option players cannot
        take (a mage forecast adds nothing although the pick is mandatory). None stops
        the forecast in the decide phase."""
        for a in self.decision_actions(game):
            if a.get("skip"):
                return a
        return None

    def play_value(self, game: "Game", cards: Sequence[Card]) -> int:
        """Attack value of a play (Legacy beasts copy their partner's value)."""
        return sum(c.value for c in cards)

    # --- resolution hooks --------------------------------------------------------
    def on_turn_start(self, game: "Game") -> Optional[Dict[str, Any]]:
        """Start-of-turn effects. May return a serialisable decision dict (with a
        ``player``) to ask something before the player acts (Legacy mission 11's beast
        effects); the rules' ``decide`` then ends with ``game.resume_turn_start()``."""
        return None

    def on_turn_end(self, game: "Game") -> Optional[Dict[str, Any]]:
        """End-of-turn effects. May return a serialisable decision dict (with a ``player``)
        to ask something before the next turn starts (Legacy mission 9); the rules'
        ``decide`` then ends with ``game.resume_end_turn()``."""
        return None

    def on_cards_played(self, game: "Game", cards: Sequence[Card], player: Optional[int] = None) -> None:
        """``cards`` just entered play from ``player``'s hand (or from a pile on that
        player's behalf): corrupted / restored effects and mission reactions."""
        pass

    def after_cleanup(self, game: "Game", exact: bool, plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Called after a defeated enemy and the played cards have been cleaned up and
        before the next enemy is revealed. Return a decision dict (with a ``player``) to
        ask the current player something first (Legacy mission 8's exact-kill pick from the
        discard pile); the rules' ``decide`` must then end with ``game.resume_defeat()``."""
        return None

    def resolve_power(self, game: "Game", suit: str, value: int, cards: Sequence[Card],
                      damage: Optional[int] = None) -> Any:
        """Resolve a non-basic suit power (Legacy). ``damage`` is the attack damage so far
        (step 3 powers such as the Reaver change it). The return value is logged; a dict
        with ``damage`` replaces the running damage, and a dict with a ``decision``
        (``kind``, ``player``, ...) pauses the resolution in the decide phase: the rules'
        ``decide`` ends it with ``game.resolve_pending_attack()``, which resumes after
        this suit."""
        raise NotImplementedError("suit %s has no power in these rules" % suit)

    def defeat_plan(self, game: "Game", exact: bool) -> Dict[str, Any]:
        """Where the defeated enemy and the played cards go."""
        return {"enemy_to": "tavern_top" if exact else "discard", "played_to": "discard"}

    def order_for_discard(self, game: "Game", cards: List[Card]) -> List[Card]:
        """Order in which a batch of cards is put on the discard pile (last = on top)."""
        return cards

    def order_for_banish(self, game: "Game", ids: List[str]) -> List[str]:
        """Order in which a mage attack's cards are banished at clean-up (last = on top)."""
        return list(ids)

    def on_enemy_revealed(self, game: "Game") -> None:
        pass


# ---------------------------------------------------------------------------
# Combo classification (shared by rules and bots)
# ---------------------------------------------------------------------------

def classify_combo(cards: Sequence[Card], strength: Optional[Callable[[Card], int]] = None,
                   max_cards: Optional[int] = 4, max_total: int = 10) -> Tuple[str, Optional[str]]:
    """Classify a set of cards as a legal play.

    Returns ``(kind, None)`` or ``("", reason)``. With the defaults this is the base game:
    a set is two to four cards of the same number totalling at most 10. ``strength``
    (card -> int) makes a set a matter of equal *strength* rather than rank and sums with
    it (Legacy kinfolk, where a 2/5 card counts as a 2); ``max_cards=None`` lifts the
    four-card cap (Legacy allows five 2s); ``max_total`` is the set's cap (an Evergreen
    boon raises it to 12). A Legacy beast (flag ``beast``) pairs like an Animal
    Companion: with any one other card, never in a set, never with a Jester.
    """
    if not cards:
        return "", "Pick at least one card."
    ids = [c.id for c in cards]
    if len(set(ids)) != len(ids):
        return "", "Duplicate card."
    jesters = [c for c in cards if c.is_jester]
    if jesters:
        if len(cards) == 1:
            return "jester", None
        return "", "A Jester must be played alone."
    if len(cards) == 1:
        return "single", None
    aces = [c for c in cards if c.is_ace]
    beasts = [c for c in cards if c.has("beast")]
    if len(cards) == 2 and (aces or beasts):
        # Animal Companion (or beast): with any one other card (Ace + Ace allowed).
        return "companion", None
    if beasts:
        return "", "A beast pairs with exactly one other card."
    if aces:
        return "", "An Animal Companion pairs with exactly one other card."
    if strength is None:
        same = len(set(c.rank for c in cards)) == 1
        total = sum(c.value for c in cards)
    else:
        values = [strength(c) for c in cards]
        same = len(set(values)) == 1
        total = sum(values)
    if not same:
        return "", "Combos need cards of the same number, or an Ace with one other card."
    if max_cards is not None and len(cards) > max_cards:
        return "", "A combo has at most %s cards." % ("four" if max_cards == 4 else max_cards)
    if total > max_total:
        return "", "A combo's total must be %d or less." % max_total
    return "set", None


RULES_REGISTRY: Dict[str, type] = {"base": BaseRules}


def register_rules(cls: type) -> type:
    RULES_REGISTRY[cls.id] = cls  # type: ignore[attr-defined]
    return cls


def get_rules(rules_id: str) -> BaseRules:
    try:
        return RULES_REGISTRY[rules_id]()
    except KeyError:
        raise KeyError("unknown rules id %r (registered: %s)" % (rules_id, sorted(RULES_REGISTRY)))
