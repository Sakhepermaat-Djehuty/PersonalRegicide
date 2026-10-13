## 0. Source access and verification status

- The environment's egress proxy **denied CONNECT** to badgersfrommars.com, regicidegame.com, boardgamegeek.com, boardgamearena.com, rulespal.com, gamerules.com, kickstarter.com, tvtropes, merchantsofplay, scribd, web.archive.org. Only github.com / raw.githubusercontent.com were reachable, plus the server-side WebSearch tool (snippets only).
- **The full official rulebook text WAS obtained** via two independent plain-text transcriptions of the official PDF `RegicideRulesA4.pdf` hosted on GitHub, which agree word-for-word on every rule sentence:
  - `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl/rules/RegicideRulesA4_main.txt` (raw pdftotext dump, column order interleaved; from github.com/ettoremodina/RegicideRL `rules/RegicideRulesA4.txt`)
  - `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl/rules/drpaj12_rules_in_text.txt` (clean, section-ordered transcription; from github.com/drpaj12/LetsPlay_FLC2025_MiamiUniversity). **Use this file as the canonical rules text for the engine.**
  - A third copy (Super-Set-Deck adaptation, `superset_en.adoc`, enemy names swapped) matches sentence-for-sentence.
- The PDF's provenance is corroborated by the `who-goes-first` project JSON (SHA-256 of the official PDF `46a7fb46…54be`, checked 2026-09-24 at `https://www.regicidegame.com/site_files/33132/upload_files/RegicideRulesA4.pdf`). The current publisher URL `https://badgersfrommars.com/assets/RegicideRulesA4.pdf` is the same document per the itch.io asset page.
- Rulebook version: BGG filepage 199721 lists two versions — April 2020 (2–4 players) and **19 Oct 2021 ("final and comprehensive rules… including solo")**. A commenter asked whether the 2021 update was more than clarifications + solo rules; the reply: **"Nope no substantive changes just clarifications and solo rules."** The text below is the 2021 version (it contains the solo section).
- **2nd Edition (plastic flip-top box, Bards art for Diamonds, bolder card backs)** — publisher page says same components; no gameplay changes found anywhere.
- WARNING about an LLM-generated "reference" found on GitHub (`leroy9472/MeepleLM` 307002.md): it claims "1 Jester for 2 players" and a "redraw if no Diamonds" rule. **Both are wrong / not in the official rules.** Do not use it.

---

## 1. Components

- A standard 52-card deck + 2 Jokers ("Jesters"). Official product has custom art by Sketchgoblin, but any 54-card deck works.
- Roles: 2–10 = attack cards; **Aces = "Animal Companions"**; **J/Q/K = the 12 enemies**; **Jokers = Jesters**.
- Rulebook credits: Design — Paul Abrahams, Luke Badger, Andy Richdale. Art — Sketchgoblin.

## 2. Setup (verbatim where it matters)

> "Shuffle the 4 Kings and put them facedown in a pile on the table. Shuffle the 4 Queens and put them facedown on top of the Kings. Shuffle the 4 Jacks and put them facedown on top of the Queens. This is the Castle deck."
> "Place the Castle deck in the centre of the table and turn the top card face up to reveal a Jack. This will become the current enemy."
> "Shuffle together all the cards numbered 2 to 10 with the 4 Animal Companions (A) and a number of Jesters based on the number of players (see table below) to form your Tavern deck."
> "The Tavern deck is where cards are dealt and drawn from. During the game place any discarded cards into a shared discard pile beside the Tavern deck. Deal cards to each player up to their maximum hand size."

**Official table (verified in 3 transcriptions + BGA help page + rulespal snippet):**

| Players | Jesters in Tavern | Max hand size |
|---|---|---|
| 1 | 0 (the 2 Jesters are set aside for the solo flip power) | 8 |
| 2 | 0 | 7 |
| 3 | 1 | 6 |
| 4 | 2 | 5 |

Derived deck sizes: Castle = 12. Tavern = 36 (2–10 ×4 suits) + 4 Aces + Jesters = 40 / 40 / 41 / 42 for 1/2/3/4 players. After the deal, Tavern holds 32 / 26 / 23 / 22 cards. Discard starts empty.

First player: "The player to have most recently committed regicide goes first." (drpaj12 copy appends "(or choose randomly)"; the who-goes-first project notes it is a joke with no fallback — implement as random/choice.)

**Enemy stats (verbatim table):**

| Enemy | Attack | Health |
|---|---|---|
| Jack | 10 | 20 |
| Queen | 15 | 30 |
| King | 20 | 40 |

Total health to chew through in a game = 4×20 + 4×30 + 4×40 = 360.

## 3. Aim / win / lose (verbatim)

> "Regicide is a cooperative game where players work together to defeat 12 powerful enemies. … The players win when the last King is defeated. But beware! Each turn the enemy strikes back. Players will discard cards to satisfy the damage and if they can't discard enough, everyone loses!"
> GAME END: "The game ends when the players win by defeating the last King or when the players lose because a player is unable to satisfy the damage dealt by an enemy. The players also lose if any player is unable to play a card or yield on their turn."

Loss conditions, precisely: (a) current player cannot discard cards totalling ≥ the enemy's (shield-reduced) attack in Step 4; (b) at Step 1 the current player has no legal play AND is not permitted to yield (see §8).

## 4. Turn structure (verbatim)

> "Each turn has four steps: Step 1 - Play a card or yield; Step 2 - Activate the suit power; Step 3 - Deal damage to the enemy and check; Step 4 - Suffer damage from the enemy"

### Step 1 — Play a card or yield
> "Play a card from your hand onto the table in front of you. The number of the card determines the attack value. So if a 7 of Hearts is played, the attack value is 7. Instead of playing a card a player may choose to yield (see Yielding)."

Legal plays in Step 1 (union of all rulebook clauses):
1. Any single card 2–10 (value = number).
2. A single Animal Companion (Ace), value 1.
3. An Ace paired with exactly **one** other card that is not a Jester — including another Ace, a 2–10, or a J/Q/K drawn from the Tavern (see §7). Value = 1 + other card's value.
4. A **combo**: 2, 3 or 4 cards of the **same number** whose **total ≤ 10** → pairs of 2/3/4/5, triples of 2/3, quadruple 2s. Aces can NOT be in a combo; J/Q/K can't either (two Jacks = 20 > 10).
5. A Jester, **always alone** (value 0).
6. Yield (if permitted).
7. A J/Q/K held in hand, as a single card (value 10/15/20) or paired with an Ace.
Played cards stay **on the table in front of the player** (NOT in the discard) until the enemy is defeated — this matters for Hearts (see §5) and for Spade bookkeeping.

### Step 2 — Activate suit power(s)
> "Playing a card to damage the enemy also grants a power associated with the suit of that card. Powers from red suits are resolved straight away, powers from black suits take effect in later steps."
> "Suit powers are mandatory and cannot be skipped."

Powers (verbatim):
- **HEARTS** — "Heal from the discard: Shuffle the discard pile then count out a number of cards facedown equal to the attack value played. Place them under the Tavern deck (no peeking!) then, return the discard pile to the table, faceup."
- **DIAMONDS** — "Draw cards: The current player draws a card. The other players follow in clockwise order drawing one card at a time until a number of cards equal to the attack value played have been drawn. Players that have reached their maximum hand size are skipped. Players may never draw cards over their maximum hand size. There is no penalty for failing to draw cards from an empty Tavern deck."
- **CLUBS** — "Double damage: During Step 3, damage dealt by clubs counts for double. E.g., The 8 of Clubs deals 16 damage."
- **SPADES** — "Shield against enemy attack: During Step 4, reduce the attack value of the current enemy by the attack value played. The shield effects of spades are cumulative for all spades played against this enemy by any player, and remain in effect until the enemy is defeated."

Multi-card plays: "When these cards are played together all suit powers are resolved at the total attack value." and (for Ace pairs) "the effects of both suit powers are applied for 9: 9 cards are drawn and 18 damage is dealt." → **every distinct suit in the play gets its power at the play's TOTAL value**, and Clubs doubles the TOTAL (8♦+A♣ = 9 attack → 18 damage; 3♦3♠3♣ → draw 9, shield 9, 18 damage). "If you play an Animal Companion with another card of the same suit, you only apply the suit power once." (i.e., no double-counting a suit; the power is applied once at the total value).

**Resolution order (official):** "Any time where both a Hearts power and Diamonds power are resolved together, resolve the Hearts healing before drawing with Diamonds." Hearts → Diamonds in Step 2; Clubs applies in Step 3; Spades applies in Step 4 (and persists). So the effective order is **Hearts, Diamonds, Clubs, Spades**. The orchestrator's guess was correct.

### Step 3 — Deal damage and check
> "Damage equal to the attack value of the played card is now dealt to the enemy. Check to see if the total damage dealt by all players so far is equal to or greater than the enemy's health. For example if facing a Jack and one player deals 9 damage in their turn, then another player deals 12 damage in their turn, the total damage currently dealt would be 21 so the enemy would be defeated."
> "If the enemy is defeated, do the following:
> (i) Place the enemy in the discard pile. If the players have dealt damage exactly equal to the enemy's health, place it facedown on top of the Tavern deck instead.
> (ii) Place all cards played by players against the enemy in the discard pile.
> (iii) Turn the next card of the Castle deck face up.
> (iv) The player who has just defeated the enemy skips Step 4 and begins a new turn against the enemy just revealed, starting at Step 1."

Notes: damage is cumulative across all players' turns; overkill is not carried over. Exact kill (total == health, e.g. exactly 20/30/40) → enemy card goes face-down on TOP of the Tavern (next card to be drawn). Overkill → enemy to discard. On defeat, all played cards go to discard, spade shields and Jester immunity-cancel are gone (they were "against this enemy"), the new enemy has full health, full attack, and its own immunity. If the defeated enemy was the 12th (last King) → win immediately.

### Step 4 — Suffer damage
> "If not defeated, the enemy attacks the current player by dealing damage equal to that enemy's attack value. Remember to reduce the enemy's attack value by the total value of Spades that players have played against the enemy."
> "The current player must discard cards from their hand with a total value at least equal to the enemy's attack value. Discard the cards one at a time, faceup to the discard pile. Animal Companions (A) have a value of 1 and the Jester a value of 0 when discarded to cover damage. If the player cannot discard enough cards to satisfy the damage, they die and all players lose the game. It's ok to have an empty hand. After suffering damage, the next player in clockwise order begins their turn, starting at Step 1."

Discard values: 2–10 face value; A = 1; Jester = 0; J = 10, Q = 15, K = 20 (see §7). Player chooses which cards; over-paying is allowed; discarding more than necessary is legal (rule only says "at least equal"). If effective attack is 0 (fully shielded) nothing need be discarded. Effective attack floor at 0 is not stated but implied (you cannot discard a negative amount); all implementations use max(0, atk − shield).

## 5. Enemy immunity (verbatim)
> "Each enemy is immune to the suit powers of cards played against them which match their suit. For example, players will not draw cards when a diamond is played against the Jack of Diamonds (however the number is still added to the damage total). The Jester can be played to cancel an enemy's immunity."
> Caption: "Enemy suit power immunity (Spades won't block damage against Jack of Spades)"

Implications: vs ♥ enemy, Hearts don't heal; vs ♦ enemy, no draw; vs ♣ enemy, Clubs do NOT double (damage = face value); vs ♠ enemy, Spades add 0 shield. The card still counts its full attack value for damage. In a mixed-suit play (Ace pair / combo) only the matching suit's power is suppressed; the other suits still resolve at the total value (e.g. 3♦3♠3♣ vs J♣ → draw 9, shield 9, damage 9). (This mixed-play consequence is a direct inference; all three open-source engines implement it this way; not separately stated in the rulebook.)

## 6. Animal Companions (verbatim)
> "In Step 1, Animal Companions can be played on their own, but may also be paired with one other card (except the Jester). Animal Companions count as 1 towards the attack total and their suit power is also applied. For example, when playing the 8 of Diamonds with the Animal Companion of Clubs the attack value is 9 and the effects of both suit powers are applied for 9: 9 cards are drawn and 18 damage is dealt. Any time where both a Hearts power and Diamonds power are resolved together, resolve the Hearts healing before drawing with Diamonds. Animal Companions can also be paired with one other Animal Companion. If you play an Animal Companion with another card of the same suit, you only apply the suit power once."
And from COMBOS: "Animal Companions cannot be added to a combo or played as a combo on their own; they can only ever be paired with one other card (which could be another Animal Companion)."

So: A alone (1); A + X (1 + X, both suits' powers at the total); A + A (2, both suits); never A + Jester; never A + combo; never 3+ cards containing an Ace. A + K is legal (value 21).

## 7. Combos (verbatim)
> "In Step 1, instead of playing a single card, players can combine cards together in sets of 2, 3 or 4 of the same number as long as the combined total of the cards played equals 10 or less. … So players can play a pair of 2s, 3s, 4s, or 5s, triple 2s and 3s, or quadruple 2s. When these cards are played together all suit powers are resolved at the total attack value. For example, if a player plays the 3 of Diamonds, Spades and Clubs together, players will draw 9 cards, reduce the enemy's attack value by 9 and deal 18 damage. Any time where both a Hearts power and Diamonds power are resolved together, resolve the Hearts healing before drawing with Diamonds."

Exhaustive legal combo set: {2,2},{2,2,2},{2,2,2,2},{3,3},{3,3,3},{4,4},{5,5}. (Not 4-4-4=12, not 3×4=12, not 6+ pairs.) A combo may contain duplicate suits (e.g. 2♣2♣ is impossible in one deck, but 5♣5♠ etc.); a suit appearing twice applies its power once at the total.

## 8. Yielding (verbatim)
> "During Step 1 it may be beneficial to yield instead of playing a card. To yield simply say 'Yield' and move directly to Step 4 (Suffer damage from the enemy), skipping Steps 2 and 3. A player may not yield if every other player has yielded on their last turn. For example, in a three player game, if two players have yielded in a row the third player may not yield."

Implementation semantics: track each player's most recent turn action (played / yielded). Current player may yield iff NOT (every other player's last action == yielded). Playing anything (including a Jester) counts as "played". 2-player: you cannot yield if the other player yielded on their last turn (so no two consecutive yields). Whether a new enemy resets "last turn" is NOT stated; strictly it does not (it's each player's last turn, regardless of enemy). multiplayr resets per enemy; RegicideRL/BGA semantics unknown. **Solo:** rulebook silent; **BGA (licensed implementation) rules "A player may not Yield in solo"** and lists "cannot play a card when the player cannot yield (because all the other players have yielded or in solo mode)" as a loss. Under vacuous truth ("every other player" of zero players) the official sentence also yields "cannot yield". RegicideRL implements "solo cannot yield"; ayrat555's terminal version allows it. Recommend: solo cannot yield (matches BGA), optionally as a toggle.

Empty hand at Step 1: you cannot play a card; if yielding is permitted you yield and go to Step 4 (survivable only if effective attack is 0); if not permitted → loss ("unable to play a card or yield").

## 9. Jester (verbatim)
> "In Step 1 when playing a card the Jester may be played (always on its own). The Jester has an attack value of 0. The power of the Jester is that it negates the immunity of the enemy meaning the suit powers of cards with the same suit as the enemy will now take effect when played. After playing the Jester, skip steps 3 and 4 then, instead of play moving to the next player the player of the Jester chooses any player to go next."
> "After playing the Jester the normal restrictions on player communication (see Communication) are temporarily changed. Until the next player starts their turn players may express their desire (or reluctance) to go next in a general way. For example you may say 'I have a good play' or 'I would rather not go next'. You still may not reveal the contents of your hand."
> "If the Jester is played against a spades enemy, spades played prior to the Jester will begin reducing the attack value of the enemy however clubs played prior to the Jester against a clubs enemy will not count for double."

Implementation: Jester has no suit; value 0 for attack and 0 for discard; Step 2 power = set `immunityCancelled = true` on the current enemy (persists until that enemy is defeated — inferred; all engines do this; the rulebook says powers "will now take effect when played", i.e., for subsequent plays). Skip Step 3 and Step 4 (no damage check, no enemy attack). The Jester player then chooses ANY player to go next — "any player" is read by Home of Mark and the RegicideRL tests as including themselves (not explicitly stated by the rulebook; BGA snippet says "the next player to take a turn is chosen by the active player"). Retroactivity: Spades already on the table vs a ♠ enemy start counting once immunity is cancelled (so compute effective shield lazily: `shield = enemy.suit=='S' && !cancelled ? 0 : spadesTotal`). Clubs already played vs a ♣ enemy are NOT retroactively doubled (damage was already banked). Hearts/Diamonds already played were simply lost. A played Jester stays on the table with the other played cards and goes to discard when the enemy is defeated. A Jester cannot be yielded "with", cannot be paired with an Ace, cannot be in a combo. Multiplayer Jesters only exist in 3p (1) and 4p (2) games. The "discard hand" effect is SOLO ONLY (see §12) — the orchestrator's doubt was correct: in multiplayer the Jester does NOT discard anyone's hand.

## 10. Drawing a defeated enemy (verbatim)
> "Jacks in hand count as a 10, Queens in hand count as a 15 and Kings in hand count as a 20. These values are applied when either playing them as an attack card or discarding them from hand to suffer damage. Their suit power is applied as normal when played."
So an exact-killed J/Q/K placed on top of the Tavern will be drawn by the next Diamonds draw / solo refill, and is a 10/15/20 card with its suit power (e.g. K♣ = 40 damage; Q♥ heals 15; J♦ draws 10; A♠ + K♠ = 21 shield). It cannot join a combo (total would exceed 10). It is subject to the current enemy's immunity like any card.

## 11. Communication (verbatim; relevant only for a multiplayer UI/hint system)
> "Players may not communicate to the other players any information which may reveal or suggest the contents of their hand. They may however remind other players of any public information such as how many cards they have in their hand. Some examples of allowed communication are: 'I have two cards in hand' or 'We only have 3 cards left in the Tavern deck!'. Some examples of prohibited communication are: 'I've got a 10 of clubs' or 'I hope someone plays a Diamond soon!' or 'If you play a Heart then I can probably help us get some cards in hand' or 'Don't kill that enemy, leave them for me!'"
Public information therefore includes: hand counts, Tavern deck count, discard pile contents (it is face-up), cards on the table, damage dealt so far, shield total.

## 12. Solo play (verbatim — the whole section)
> "When playing with only 1 player note the following rule changes: Set up the game as per usual but place the two Jesters to the side. You play with a single hand limited to 8 cards. Play as normal, playing each turn one after the other. A Jester can be flipped to activate the following power: 'Discard your hand and refill to 8 cards - this does not count as drawing for the purpose of enemy diamond immunity.' Since you have two Jesters this can be done twice per game. Flipping the Jesters in this way does not cancel enemy immunity. You are allowed to use the Jester power a) at the start of Step 1 before you play a card or b) at the start of Step 4 before you have to take damage.
> A win having used 2 Jesters = Bronze Victory; A win having used 1 Jester = Silver Victory; A win having used 0 Jesters = Gold Victory"

Implementation: solo Tavern = 40 cards (no Jesters). Two "flip" tokens. Flip = move entire hand to discard (face up), then draw up to 8 from Tavern (works vs a ♦ enemy; does not cancel immunity; the enemy's attack still happens if flipped at start of Step 4 — you then discard from the NEW hand). Timing windows: start of Step 1 (before playing/yielding) or start of Step 4 (before discarding). Diamonds draws in solo all go to the one hand (up to 8). Victory tier = Gold/Silver/Bronze by flips used (0/1/2). Solo yielding: see §8 (BGA: not allowed). If the Tavern has fewer than 8 cards when refilling, the rulebook is silent (an App Store reviewer explicitly notes this gap); by analogy with "no penalty for failing to draw from an empty Tavern deck", draw what is available.

## 13. Edge cases — official vs inferred (for the engine's test suite)

Official (quoted above):
- Tavern deck empty during Diamonds: draw what you can, no penalty, **no reshuffle of the discard** (the only mechanism returning cards to the Tavern is Hearts). The BGG thread "What to do when the deck runs out?" (2591267) surfaced by search references Friedemann Friese and is almost certainly about a different game — ignore it. A Topping-The-Table guide's "reshuffle the discard" is a house rule, not official.
- Exact kill → enemy face-down on top of Tavern; overkill → discard.
- Played cards remain on the table until the enemy dies → they are NOT available to Hearts healing, and ARE used for cumulative Spade totals; they go to discard on defeat (together with the enemy unless exact).
- Hearts moves cards to the BOTTOM of the Tavern (under); exact-killed enemies go on TOP.
- Diamonds: round-robin starting with current player; skip full hands; never exceed max; stop when N drawn or Tavern empty (or everyone full).
- Spades persist for the enemy's life, cumulative across all players; Clubs are per-play; Hearts/Diamonds immediate.
- Immunity: own-suit power blocked, damage still counts; Jester cancels; retroactive for Spades only.
- Defeating player skips Step 4 and takes another full turn vs the new enemy.
- Max hand size is also the deal size; "It's ok to have an empty hand."
- Lose if unable to cover damage, or unable to play or yield.

Inferred / consensus (NOT in rulebook text — flag in code comments):
- Hearts when discard has fewer than N cards: move all of them (min(N, |discard|)); empty discard → no effect. (All engines; no official ruling found.)
- Effective attack = max(0, attack − shieldTotal).
- Immunity cancellation lasts until the enemy is defeated; new enemy starts immune again.
- Jester player may pick themselves as next player ("any player").
- Mixed-suit play vs an immune suit: only that suit's power is suppressed.
- Solo: yielding not allowed (BGA ruling); Jester flip refills as many as available if Tavern short.
- Yield tracking does not reset on enemy defeat (strict reading); some engines reset it.
- Nothing says you may not discard more than needed in Step 4 → allowed.

## 14. Difficulty variants — official status
- **The official rulebook contains NO difficulty variants** other than the solo Gold/Silver/Bronze tiers. Jester count is fixed by player count (0/0/1/2). There is no official "0 Jesters = hard" setting.
- Fan variants seen on BGG: "Inferno variant" (thread 3681898) — shuffle only ONE Jester into the Tavern for 2–4 players, normal hand limits; "Is Regicide too easy?" (2718237) — suggestion to cut hand size to 3; "Alternate Regicide rules. Do they exist?" (2814892) — not readable. "Regicide Duel" (2909781) — fan competitive 2-player variant (no Jesters, 7 cards each, first Jack not flipped).
- Official later products (out of scope but exist): **Regicide: Inferno** (BGG 460927) and **Regicide: Crown Duels** (Kickstarter "Regicide Inferno and Regicide: Crown Duels" by Badgers from Mars, English-only), and **Regicide Legacy** (BGG 412963, 12-mission campaign, 2025; 2nd printing has a "Mission 6 Rules Changes" file).
- BGA offers table "variants" that relax the Ace/combo exceptions (per BGG thread 3286672), and the official Android companion app was observed by a BGG poster to allow more card combinations than the printed rules; replies: "the printed rules are correct unless rule modifiers are in use." Exact modifier lists could not be retrieved.
- Two-player: no special rules at all beyond the table (0 Jesters, 7 cards); the yield rule degenerates to "no two consecutive yields".

## 15. FAQ / errata status
- No official FAQ or errata document for base Regicide was found. The original Kickstarter project's FAQ page is empty ("The creator hasn't listed any questions"). Kickstarter updates (#10 "Diamonds & Distribution", #13 "App Stuff", "App Update, Second Print Run Update") concern art/app/printing, not rules.
- The only "errata-like" event is the Oct 2021 rulebook revision (clarifications + solo rules, "no substantive changes").
- **Regicide Legacy Kickstarter FAQ** explicitly offers two rules "you're welcome to incorporate into your existing games of Regicide": (1) Jester change — "The player of the Jester no longer decides who plays next. The players simply wait for someone to play next" (the later Legacy rulebook snippet instead says "play proceeds clockwise as normal from the person who took the jester" — the two Legacy sources conflict; Legacy rulebook p.20 (p.26 solo) is the final word and was not readable); (2) **Feign Death** — a player may discard a full hand of cards (e.g. 6 cards in a 3-player game) to satisfy the strike even if their values don't add up; Legacy rulebook adds "You must be at your hand limit to feign death." Legacy solo Jester: "twice per game, a jester can be played to form an attack on its own instead of playing cards from hand" (snippet; unverified wording). Treat all of these as Legacy/optional, not base rules.
- Open question seen on the Companion app listing (unanswered): whether Animal Companion suit powers work when paired with face cards — per the base rulebook they do ("paired with one other card (except the Jester)" + "Their suit power is applied as normal").

## 16. The "mobile game" the user has
- Almost certainly **"Regicide Companion"** by Badgers From Mars Limited (iOS App Store id1565706782, Google Play `com.bfm.regicidecompanion`, also Windows). Free tracker (enemy HP/attack, combo/companion legality reminders) + one-off IAP "Regicide Solo Play" ($2.99 / £2.99) which is "the full, official single player version". Version 2.5–2.6 (Nov 2025); 2.2 added solo stats. Reviewer complaints: no pause, Jester button not limited to 2 per game, no suit-power reference in solo, no win/loss stats, rules hard to find. The official rulebook back page says "DOWNLOAD THE FREE 'REGICIDE COMPANION' APP!". (Not the Warhammer 40k: Regicide chess game.)

## 17. Reference implementations downloaded (for cross-checking the engine; not authoritative)
- `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl/rules/regicideRL_game.py` + `regicideRL_tests.py` (Python; tests enumerate: castle order, tavern composition, hand sizes, enemy stats, combo validity incl. Ace rules, hearts partial/empty, diamonds skip-full/empty-tavern, clubs doubling only damage, spades cumulative & floor 0, immunity, Jester cancel + retroactive spades + non-retroactive clubs, yield chains incl. solo-cannot-yield, exact-kill to tavern top, same player continues after defeat, empty-hand lose/continue).
- `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl/rules/multiplayr_state.ts` (TypeScript; lazy shield computation `effective_shield`, yield tracking reset per enemy, solo refill).
- `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl/rules/ayrat_rules.rs` (Rust terminal game rules summary; allows solo yield — minority view).

UNCERTAINTIES:
- Network policy blocked direct fetches of every non-GitHub source (publisher PDF, BGG, BGA, rulespal, gamerules, Kickstarter). The rulebook text is therefore verified via two independent GitHub transcriptions that agree word-for-word (plus a third adapted copy and a SHA-256 provenance record), but not against the PDF bytes themselves. Secondary sources (BGA help, BGG threads, Legacy FAQ) are known only through search-result snippets.
- Solo yielding: the rulebook never addresses it. BGA (licensed digital version) rules 'A player may not Yield in solo'; RegicideRL agrees; ayrat555's engine allows it. No designer statement found. Recommend 'not allowed' with a toggle.
- Hearts when the discard pile holds fewer cards than the attack value: no official ruling found; all engines move all available cards. Empty discard → no effect.
- Jester player choosing themselves as the next player: rulebook says 'any player'; a reviewer (Home of Mark) and RegicideRL treat self-selection as legal; no explicit official confirmation.
- Duration of Jester immunity cancellation: rulebook does not state when it ends; consensus (all engines) is until that enemy is defeated.
- Whether yield-tracking ('yielded on their last turn') resets when a new enemy is revealed: rulebook silent; strict reading = no reset; multiplayr resets per enemy.
- Solo Jester flip when the Tavern has fewer than 8 cards: rulebook silent (an App Store reviewer explicitly flags this gap); draw-what-is-available is the natural reading.
- Regicide Legacy's revised Jester rule: Kickstarter FAQ says 'players simply wait for someone to play next' while the later Legacy rulebook snippet says 'play proceeds clockwise from the person who took the jester'; Legacy rulebook pages 20/26 not readable. Legacy solo Jester ('played to form an attack on its own, twice per game') is snippet-only.
- Exact option/modifier lists of the official Regicide Companion app's solo mode and of BGA's table variants could not be retrieved; a BGG poster reports the app allows combinations beyond the printed rules when modifiers are on.
- The BGG thread 'What to do when the deck runs out?' (2591267) returned by search mentions Friedemann Friese and is likely about a different game; it should not be used as a Regicide ruling. Official Regicide text: no reshuffle, no penalty.
- Could not confirm the exact release date of the Oct 2021 rulebook revision beyond the BGG file page listing, nor whether the current badgersfrommars.com PDF differs from the regicidegame.com one (the who-goes-first project checked the latter on 2026-09-24 and found the solo section present).

SOURCES:
- https://badgersfrommars.com/assets/RegicideRulesA4.pdf (official PDF; blocked by network policy, text obtained via GitHub transcriptions)
- https://www.regicidegame.com/site_files/33132/upload_files/RegicideRulesA4.pdf (official PDF mirror, same document; blocked)
- https://raw.githubusercontent.com/ettoremodina/RegicideRL/main/rules/RegicideRulesA4.txt (pdftotext dump of official rulebook)
- https://raw.githubusercontent.com/drpaj12/LetsPlay_FLC2025_MiamiUniversity/main/INDIVIDUAL_FOLDERS/jamie/REGICIDE_with_CHATBOTS/rules_in_text.txt (clean transcription of official rulebook)
- https://raw.githubusercontent.com/Impactful-Games/Super-Set-Deck-Games/main/games/Regicide/en.adoc (official text adapted; sentence-identical)
- https://raw.githubusercontent.com/ariel-hi/who-goes-first/main/src/content/games/regicide-badgers-2021-en.json (PDF provenance, SHA-256, first-player rule)
- https://raw.githubusercontent.com/ettoremodina/RegicideRL/main/game/regicide.py and tests/test_game_rules.py
- https://raw.githubusercontent.com/zichun/multiplayr/master/src/rules/regicide/RegicideGameState.ts
- https://raw.githubusercontent.com/ayrat555/regicide/master/src/ui/rules.rs
- https://en.boardgamearena.com/doc/Gamehelpregicide (via search snippets only: hand/jester table, solo no-yield ruling, Jester wording)
- https://en.boardgamearena.com/gamepanel?game=regicide (snippets)
- https://www.rulespal.com/regicide/rulebook (snippets)
- https://www.rulespal.com/regicide-legacy/rulebook (snippets: Jester rule changed p.20/p.26, Feign Death hand-limit)
- https://gamerules.com/rules/regicide/ (snippets)
- https://boardgamegeek.com/filepage/199721/rules-for-regicide (snippets: 2020 vs Oct-2021 rulebook versions, 'no substantive changes')
- https://boardgamegeek.com/thread/3286672/regicide-rules (snippets: app allowed extra combos; printed rules correct unless modifiers)
- https://boardgamegeek.com/thread/3681898/regicide-inferno-variant (fan variant, 1 Jester)
- https://boardgamegeek.com/thread/2718237/is-regicide-too-easy (fan hand-size variant)
- https://boardgamegeek.com/thread/2875995/the-10-commandments-of-regicide-solo (solo strategy)
- https://boardgamegeek.com/thread/2909781/regicide-duel-competitive-regicide-for-two-players (fan variant)
- https://www.kickstarter.com/projects/badgersfrommars/regicide/faqs (empty FAQ)
- https://www.kickstarter.com/projects/badgersfrommars/regicide-legacy/faqs (Jester change + Feign Death optional base rules)
- https://badgersfrommars.com/en-eu/products/regicide-2nd-edition (2nd edition: cosmetic changes only)
- https://apps.apple.com/us/app/regicide-companion/id1565706782 and https://play.google.com/store/apps/details?id=com.bfm.regicidecompanion (official Companion app with solo IAP)
- https://homeofmark.com/regicide-card-game-review/ (snippet: Jester player may choose themselves)
- https://gathertogethergames.com/blog/how-to-play-regicide, https://merchantsofplay.com/howtoplay/regicide/, https://thesoloboardgamer.com/regicide-solo-rules/, https://toppingthetable.com/how-to-play/how-to-play-regicide/ (secondary summaries, snippets only)
- https://jacoblillywhite.itch.io/regicide-assets (links official PDF URL)