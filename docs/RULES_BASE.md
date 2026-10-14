# Regicide — implementation-grade rules spec (base game)

This is the rule set the engine in `regicide/` implements. It was assembled from the
official rulebook (Badgers From Mars, "Regicide", `RegicideRulesA4.pdf`, the revision
that includes solo play), the Board Game Arena help page, and cross-checked against two
independent open-source engines (`ahgamut/regi-py`, `Kautiontape/regicide`). The
rulebook text itself is the publisher's and is not reproduced here; every sentence
below was checked against it.
Where sources disagree or wording is ambiguous the spec says so and names the
config switch the engine exposes.

## Components

* Tavern deck: A, 2–10 of ♥ ♦ ♣ ♠ (40 cards) plus 0–2 Jesters depending on player count.
* Castle deck: the 12 royals (J, Q, K of each suit).

## Setup

| Players | Jesters in the tavern deck | Max hand size |
|---------|----------------------------|---------------|
| 1       | 0 (both Jesters are set aside as solo powers, see Solo) | 8 |
| 2       | 0 | 7 |
| 3       | 1 | 6 |
| 4       | 2 | 5 |

1. Shuffle the four Kings and place them face down. Shuffle the four Queens and put
   them on top. Shuffle the four Jacks and put them on top. This is the castle deck.
   Reveal the top card: the first enemy is always a Jack.
2. Shuffle the tavern deck (number cards + the Jesters for the player count).
3. Deal every player a full hand (max hand size).
4. The rulebook's only first-player rule is "the player to have most recently committed
   regicide goes first"; the app lets seat 1 start. Play proceeds clockwise.

## Enemies

| Rank  | Health | Attack | Immune to |
|-------|--------|--------|-----------|
| Jack  | 20     | 10     | its own suit's power |
| Queen | 30     | 15     | its own suit's power |
| King  | 40     | 20     | its own suit's power |

Immunity: the enemy ignores the suit power of its own suit (a Jack of Clubs is not
damaged double by Clubs; a Queen of Hearts does not let Hearts heal, etc.). The
damage of a card is always dealt; only the power is ignored. A Jester cancels the
immunity for the rest of that enemy's life.

## Card values

| Card | Value (attack and defence) |
|------|----------------------------|
| A (Animal Companion) | 1 |
| 2–10 | face value |
| Jester | 0 |
| Jack / Queen / King (when they come back into the tavern and are later discarded) | 10 / 15 / 20 |

## A turn

### Step 1 — play a card (or yield)

Play one of the following face up in front of the enemy:

* A single card (any card).
* **Animal Companion**: an Ace together with one other card. Ace + Ace is allowed. An
  Ace may not be paired with a Jester. The pair counts as one attack; both suit
  powers trigger with the combined value. If both cards share a suit, that suit's
  power is applied once (with the combined value).
* **Set combo**: 2, 3 or 4 cards of the same number whose total is 10 or less. So only
  2s, 3s, 4s and 5s can be combined (e.g. 5+5, 3+3+3, 2+2+2+2). All suits in the combo
  trigger, each with the combo's total value.
* **Jester**: must be played alone (see Jester).

Or **yield**: say "yield", skip steps 2 and 3, go straight to step 4. A player may not
yield if every other player yielded on their most recent turn (so with 2 players you
cannot yield if the other player just yielded; with 1 player you can never yield). The
engine records each player's last turn action and applies this literally: it is not a
"consecutive yields" counter, so the bonus turn after a kill is still restricted if the
other players' last turns were yields. The record is not reset when a new enemy appears
(strict reading; no official ruling found).

A player who cannot play a card and may not yield loses the game for everybody.

### Step 2 — activate suit powers

Attack value = sum of the values of the cards played.

* ♥ **Hearts — heal**: shuffle the discard pile, count out `attack value` cards face
  down and put them under the tavern deck. The rest go back as the discard pile.
* ♦ **Diamonds — draw**: starting with the current player and going clockwise, each
  player draws one card at a time until `attack value` cards have been drawn in total.
  A player at max hand size is skipped. Stop early if the tavern deck runs out or every
  hand is full.
* ♣ **Clubs — double damage**: the damage dealt in step 3 is doubled.
* ♠ **Spades — shield**: reduce the enemy's attack by `attack value` for the rest of its
  life. Shields accumulate.

Resolution order: Hearts before Diamonds whenever both trigger (the official rule is
explicit about this), then Clubs applies in step 3 and Spades in step 4. The engine
resolves ♥ → ♦ → ♣ → ♠.

Immunity interaction with the Jester: if the Jester is played against a ♠ enemy,
Spades played earlier start reducing its attack from now on (retroactive). Clubs played
earlier against a ♣ enemy do **not** retroactively double (that damage is already done).

### Step 3 — deal damage

Damage = attack value, doubled if Clubs applied. Subtract from the enemy's health.

* Health exactly 0: the enemy is defeated and placed face **down on top of the tavern
  deck** (it becomes a strong card to draw later).
* Health below 0: the enemy is defeated and goes to the discard pile.

When an enemy is defeated, all cards played against it go to the discard pile, the next
enemy is revealed, and the **same player takes a new turn** (step 4 is skipped).
If that was the last enemy, the players win.

### Step 4 — suffer damage

Damage to suffer = enemy attack − total shields (never below 0). The current player
discards cards from hand with a total value **at least** the damage (over-paying is
allowed, and the player chooses which cards). If the player cannot reach the damage
with their whole hand, everyone loses. Then the next player clockwise starts their turn.

### Jester

Value 0, played alone. Step 2: cancel the enemy's immunity. Steps 3 and 4 are skipped
(no damage dealt, no damage suffered). Then the player who played the Jester chooses
who takes the next turn. Until that player starts, the normal "no hand talk" rule is
relaxed: players may say that they would like, or would rather not, go next (but may
not reveal their hand).

Open point (config `jester_may_choose_self`, default **true**): sources describe the
choice as "any player"; it is not spelled out whether that includes the Jester's own
player. Default allows it.

### Communication

Players may not reveal the contents of their hand or discuss what they will play. The
engine does not enforce this; the pass-and-play UI simply hides other hands.

## Solo rules

* Hand size 8. Both Jesters are set aside face up as two one-shot powers.
* At the **start of step 1** (before playing) or at the **start of step 4** (before
  discarding) you may flip a Jester: discard your whole hand and draw 8 new cards.
  This does not count as "drawing" for ♦ immunity purposes and does **not** cancel the
  enemy's immunity.
* You can never yield.
* Victory tiers: Gold = won without using a Jester, Silver = used one, Bronze = used both.

## Losing

Any of: a player cannot discard enough to suffer the damage; a player has no card to
play and may not yield.

## Edge cases the engine pins with tests

* Diamonds draw with every hand full: nothing happens.
* Hearts with an empty discard pile: nothing happens.
* A combo containing both ♥ and ♦ heals first; the healed cards go under the tavern deck,
  so they are drawn by the same play only if the deck is shorter than the draw.
* Exact kill with Clubs doubling: it is the doubled damage that must match exactly.
* Shield larger than attack: damage to suffer is 0; the turn still passes.
* Discarding a ♠ to suffer damage does not add a shield.
* The player who defeats an enemy keeps the turn and may yield on it only if allowed by
  the yield rule as usual.
* Jester against a ♠ enemy: previously played Spades now count as shield.

## Unofficial variants (switchable, off by default)

These are house rules or companion-app style knobs, not part of the base rulebook:
number of Jesters override, hand size override, open hands (one person driving all
seats), `solo_can_yield` (some fan engines allow it; the official reading forbids it),
`yield_reset_per_enemy` (forget who yielded when a new enemy appears), and
`strict_minimal_discard` (reject a damage payment that contains a card it does not
need). They are listed so the UI can offer them honestly labelled.

**Owner's hidden house rule (on by default, every mode):** every opening hand holds a
card that can draw, a Diamond (a Bard in Legacy; a multi-class card with the Diamond
counts), because a game dealt without one cannot recover. A hand dealt without one
swaps a random card of its own with the first Diamond in the reserve (tavern) deck,
the rest of the deck keeping its order; deals that already have one are unchanged.
It is not announced in the game. `GameConfig.opening_diamond=False` turns it off.
