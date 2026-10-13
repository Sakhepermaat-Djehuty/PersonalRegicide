Adversarial verification of the base rules report by three independent agents (numbers, resolution order, edge cases).

# Verification verdict 1

- **Claim:** §7: "A combo may contain duplicate suits (e.g. 2♣2♣ is impossible in one deck, but 5♣5♠ etc.); a suit appearing twice applies its power once at the total."
  **Problem:** Self-contradictory and misleading. In a single 52-card deck every rank has exactly one card per suit, so a same-number combo of 2–4 cards ALWAYS has distinct suits; '5♣5♠' is not a duplicate-suit example. The only case where one suit can appear twice in a play is Animal Companion + a card of the same suit (e.g. A♣ + 8♣), which the rulebook addresses explicitly.
  **Corrected:** Combos (2–4 cards of the same number) never contain duplicate suits in a standard deck; the 'apply the suit power only once' rule applies only to an Ace paired with a same-suit card ("If you play an Animal Companion with another card of the same suit, you only apply the suit power once"). Engines should still de-duplicate suits generically (set of suits in the play) so custom/multi-deck variants behave correctly.
  **Source:** RegicideRulesA4 raw pdftotext (scratchpad/dl/rules/RegicideRulesA4_main.txt), ANIMAL COMPANIONS and COMBOS sections

- **Claim:** §6: "A + K is legal (value 21)" and §4 item 3, stated as settled fact.
  **Problem:** The rulebook never states that Ace pairs are exempt from the 'combined total of the cards played equals 10 or less' cap; the exemption is an inference from the cap living in the COMBOS section plus 'Animal Companions cannot be added to a combo'. The report presents an inference as official text. (The independent ambiguity audit flags this as finding M1.)
  **Corrected:** Treat as INFERRED-but-strongly-corroborated: the ≤10 cap applies only to same-number combos; an Ace may pair with any one non-Jester card including 10 (=11), J (=11), Q (=16), K (=21) and both suit powers resolve at that total. Corroboration: BGA official help lists 'Play an Ace and another card together' separately from 'a group of matching number cards whose sum is 10 or less'; the fan Companion-Plus app (which copies BGA's options) defaults 'Max Animal Companion card' to K; engines HelloClaraCards (test K♠+A♥ = 21), DorkDad141 (validateCombo Ace+King), CasmiroGranado (Ace+9 accepted), awweide (cap only when ≥2 non-Aces) all allow it; no engine found that caps Ace pairs. Expose as a config knob (maxCompanionPairRank, default K) and comment the inference.
  **Source:** RegicideRulesA4 COMBOS/ANIMAL COMPANIONS; BGA help text (scratchpad/dl2/bga-help-zh-main/file); scratchpad/dl2/regicide-plus-src/src_OptionsContext.tsx; repos/HelloClaraCards__regicide/tests/engine.test.mjs:254; repos/ymonnet__regicide-pre-print-ambiguity-audit/README.md (M1)

- **Claim:** §4 Step 3 / §13: "Exact kill (total == health, e.g. exactly 20/30/40) → enemy card goes face-down on TOP of the Tavern."
  **Problem:** Does not say which number is compared. The rulebook's phrase is 'dealt damage exactly equal to the enemy's health', i.e. the cumulative DAMAGE DEALT (after Clubs doubling), not the card values. Left implicit, an engine could compare raw attack value. The ambiguity audit flags this (M2); BGA's wording 'killed by an exact finishing value' is itself loose.
  **Corrected:** Exact-kill test = (cumulativeDamageDealtThisEnemy == enemy.health) where each play's contribution is attackTotal × (2 if Clubs power active and not blocked by immunity else 1). Example: King at 24/40, play 8♣ (16 dmg) → 40 exactly → King face-down on top of Tavern. Overkill (> health) → discard.
  **Source:** RegicideRulesA4 STEP THREE (i): 'If the players have dealt damage exactly equal to the enemy's health'; ambiguity audit M2

- **Claim:** §4 Step 2 / §13: Resolution order given as 'Hearts, Diamonds, Clubs, Spades' with no statement about the kill check.
  **Problem:** Omits a load-bearing sequencing rule: Step 2 (Hearts heal, Diamonds draw) fully resolves BEFORE Step 3's defeat check. Consequences the engine must honour: (a) on a killing blow with Diamonds, the draws happen while the enemy is still on the table, so an exact-killed enemy placed on top of the Tavern afterwards is NOT drawn by that same play; (b) on a killing blow with Hearts, the cards played against the enemy and the enemy itself are still on the table (not in discard) and so cannot be healed by that play; (c) the played cards go to discard only in Step 3 (ii), after Step 2.
  **Corrected:** Engine order per play: remove cards from hand → place on table → [Step 2] Hearts (shuffle discard, move min(N,|discard|) under Tavern) → Diamonds (draw N round-robin) → [Step 3] add damage (Clubs ×2 if active) → defeat check → if defeated: enemy to discard or Tavern-top (exact), played cards to discard, reveal next, same player starts Step 1 → else [Step 4] attack with Spades shield. Hearts before Diamonds whenever both occur (official).
  **Source:** RegicideRulesA4 'Powers from red suits are resolved straight away'; HOW TO PLAY step list; corroborated by repos/jonathonthill__1789/test/engine.test.js:430 ('Heart and Diamond powers resolve on a killing blow before the royal is defeated')

- **Claim:** §3 / §8 / §12: Loss condition (b) 'at Step 1 the current player has no legal play AND is not permitted to yield' and solo section.
  **Problem:** Incomplete for solo: the solo Jester flip is explicitly allowed 'at the start of Step 1 before you play a card', so an empty-handed solo player who still has a flip can refill and continue. Loss in solo occurs only when hand is empty AND no flips remain (and yield is disallowed). The report never states this rescue.
  **Corrected:** Solo Step-1 loss check: lose iff hand is empty AND soloFlipsRemaining == 0 (AND yield not permitted, which is the recommended solo default). If a flip remains the player may (must, to continue) flip: discard hand (empty), draw up to 8. Multiplayer: lose iff hand empty AND cannot yield.
  **Source:** RegicideRulesA4 SOLO PLAY ('at the start of Step 1 before you play a card'); GAME END; RegicideRL game.py:965 (`if not hand and not self.can_yield() and not self.can_use_solo_jester()`); notes/taverna_regicide.md 'Casi limite'

- **Claim:** §13: "Diamonds: round-robin starting with current player; skip full hands; never exceed max; stop when N drawn or Tavern empty (or everyone full)." presented as official.
  **Problem:** The rulebook sentence ('The current player draws a card. The other players follow in clockwise order ... until a number of cards equal to the attack value played have been drawn') reads like a single pass; that the loop wraps back to the current player for a second lap is an interpretation (ambiguity audit M3). All engines and BGA ('Draw cards in turn order to the value of the card, skipping players at max hand size') loop. Also 'everyone full' as a stop condition is not in the text (implied: no eligible drawer).
  **Corrected:** Official: order = current player, then clockwise, one card each, skip players at max, never exceed max, no penalty if Tavern empties. Inferred (consensus): continue wrapping around the table (current player included) until N cards drawn, or Tavern empty, or no player below max. Mark the wrap-around as inferred in code comments.
  **Source:** RegicideRulesA4 DIAMONDS; BGA help; ambiguity audit M3; multiplayr_state.ts:466-481; RegicideRL game.py:618-625

- **Claim:** §9: "A played Jester stays on the table with the other played cards and goes to discard when the enemy is defeated." (no further consequence noted)
  **Problem:** Omits an edge case that follows: once in the discard, a Jester (and likewise a defeated enemy card, or a drawn enemy discarded for damage) is an ordinary discard card and can be shuffled back under the Tavern by a Hearts heal and drawn again later. Engines that special-case the discard pile by card type will diverge from the physical game.
  **Corrected:** The discard pile may hold any card type (2–10, A, Jester, J/Q/K). Hearts moves a uniformly random subset of min(N,|discard|) cards under the Tavern regardless of type. A recycled Jester played again cancels immunity of whichever enemy is current and again skips Steps 3–4 / chooses next player; a second Jester against an already-cancelled enemy is still a legal play with those turn effects.
  **Source:** RegicideRulesA4 STEP THREE (i)-(ii), HEARTS; STEP FOUR ('the Jester a value of 0 when discarded')

- **Claim:** §9: After the Jester, 'the player of the Jester chooses any player to go next' (no statement of what happens after that chosen player's turn).
  **Problem:** Turn-order continuation is unspecified in the report. The rulebook's general rule 'After suffering damage, the next player in clockwise order begins their turn' resumes from the CHOSEN player, not from the Jester player.
  **Corrected:** After a Jester: chosen player P takes the next turn; subsequent turns proceed clockwise from P (the Jester player's seat position no longer matters). Self-selection remains an open question (report's flag stands): 'any player' literally includes the Jester player; BGA help says 'the next player to take a turn is chosen by the active player'; recommend allow with a toggle.
  **Source:** RegicideRulesA4 PLAYING THE JESTER + STEP FOUR last sentence; BGA help

- **Claim:** §0: "BGG filepage 199721 lists two versions — April 2020 and 19 Oct 2021 ... reply: 'Nope no substantive changes just clarifications and solo rules.'"
  **Problem:** Could not be verified from this environment: boardgamegeek.com is unreachable (DNS/proxy) and the WebSearch budget was exhausted before my first query. The claim rests on a search snippet only. Nothing contradicts it, but it should not be labelled 'verified'.
  **Corrected:** Mark UNVERIFIED (snippet-only). What IS verified: the text used (raw pdftotext + clean transcription, identical sentence-for-sentence) contains the SOLO PLAY section and the back-page 'DOWNLOAD THE FREE REGICIDE COMPANION APP' blurb, so it is the later (post-solo) revision; the who-goes-first project recorded SHA-256 46a7fb46…54be for the regicidegame.com PDF on 2026-09-24 with the solo section present.
  **Source:** scratchpad/dl/rules/RegicideRulesA4_main.txt; scratchpad/dl/rules/whogoesfirst.json; WebFetch errors for boardgamegeek.com in this session

- **Claim:** §14: "Fan variants seen on BGG: 'Inferno variant' (thread 3681898) — shuffle only ONE Jester into the Tavern for 2–4 players"; "BGA offers table variants that relax the Ace/combo exceptions (per BGG thread 3286672)"; "Exact modifier lists could not be retrieved."
  **Problem:** The BGG thread claims are snippet-only and unverifiable here (BGG unreachable). The BGA-options claim is partially corroborated but the report missed the concrete option list that WAS retrievable: the fan 'Regicide Companion Plus' source (author states its options copy BGA's) and the teapowell BGA scraper DOM ids.
  **Corrected:** Keep the BGG-thread items as UNVERIFIED. Add (as 'fan mirror of BGA options, mapping unverified against BGA'): Max hand size Default/+1/+2/−1/−2; Remove Jesters Default/−1/−2; Enemy health boost Default/+5/+10/−5/−10 (applied to every enemy); Enemy attack boost Default/+2/+5/−2/−5; Yield On/Off; Max combo limit 10 default (harder 9/8/6/4/No combo; easier 12/15/18; max combo card = floor(limit/2)); Max Animal Companion pair card K default … A, or No companion. BGA scraper ids: gameoption_100 modifications on/off, 101 hand size, 103 enemy health, 104 enemy attack, 102 unknown.
  **Source:** scratchpad/dl2/regicide-plus-src/src_Components_SelectOptions.tsx and src_OptionsContext.tsx; research/companion.md §BGA (teapowell/BGA_Scraper DOM ids)

- **Claim:** §16: Regicide Companion app 'one-off IAP "Regicide Solo Play" ($2.99 / £2.99)', 'Version 2.5–2.6 (Nov 2025); 2.2 added solo stats', reviewer complaints list.
  **Problem:** None of this is verifiable from this environment (App Store / Google Play / BGG blocked); the sibling companion-app research explicitly labels the price and dates as UNVERIFIED recollection (~US$2–3). The report states them as facts.
  **Corrected:** Label price, version numbers, dates and review quotes UNVERIFIED. Verified facts only: the official rulebook's back page says 'DOWNLOAD THE FREE REGICIDE COMPANION APP!'; Android package com.bfm.regicidecompanion is a Unity app with Google Play Billing (so IAP exists); BGG files it under 'Digital Implementations: Google Play'; third-party reviews describe it as an enemy HP/attack tracker with a solo mode.
  **Source:** research/companion.md §0, §3; scratchpad/dl2/taptrap-json/file (APK manifest); RegicideRulesA4 back page

- **Claim:** §15: Regicide Legacy 'Feign Death — a player may discard a full hand of cards (e.g. 6 cards in a 3-player game) ... Legacy rulebook adds "You must be at your hand limit to feign death."' and Legacy solo Jester wording.
  **Problem:** Snippet-only; not verifiable here. The only Legacy artefact reachable (fan engine DorkDad141/regicide-js) implements 'discarding 6+ cards always satisfies damage' regardless of player count/hand limit, which is a fan simplification and should not be read back as the official wording.
  **Corrected:** Keep all Legacy rule statements as UNVERIFIED/out-of-scope for the base engine; implement Feign Death, if at all, behind a campaign flag with the condition parameterised (hand-at-limit vs fixed 6) until the Legacy rulebook is read.
  **Source:** repos/DorkDad141__regicide-js/src/game/gamestate.ts:350-352; research/legacy.md confidence tags

- **Claim:** §8 (solo yielding): 'RegicideRL implements solo cannot yield; ayrat555's terminal version allows it' — presented as the only two data points.
  **Problem:** Incomplete survey. Engines are genuinely split and some use third variants; the report's recommendation is right but the evidence base understated.
  **Corrected:** Disallow: BGA official help ('A player may not Yield in solo'; loss 'unable to play a card when the player cannot yield (... in solo mode)'), RegicideRL, multiplayr, pholser (vacuous-truth reading), HelloClaraCards, jonathonthill/1789. Allow: ayrat555, AleDM1, CuatroSeis. Variants: xunserver (solo cannot yield twice in a row), pawel-schmidt (solo may yield only if Tavern non-empty). Recommendation stands: default disallow (matches licensed BGA), expose `soloCanYield` toggle.
  **Source:** scratchpad/dl2/bga-help-zh-main/file; engine grep across scratchpad/repos (ayrat555 query.rs:42, AleDM1 game.js:157, CuatroSeis turn.ts:174, pholser turn_order.py:36, HelloClaraCards engine.js:158, 1789 engine.test.js:529, xunserver types.ts:50, pawel-schmidt rules.ts:226)

- **Claim:** §8: yield-tracking reset on new enemy — 'multiplayr resets per enemy; RegicideRL/BGA semantics unknown.'
  **Problem:** Minor omission: the report does not note that the 'last turn' window also matters for the defeating player's bonus turn and that the ambiguity audit (M4) treats the window itself as undefined for 3–4 players.
  **Corrected:** Implement `lastAction[player] ∈ {played, yielded, none}` updated at the end of each player's turn (a defeat-bonus turn is a new turn; a Jester play counts as 'played'). canYield(p) = !(all others have lastAction == yielded). Default: do NOT reset on new enemy (strict reading); provide `resetYieldOnNewEnemy` toggle (multiplayr behaviour). Document as inferred.
  **Source:** RegicideRulesA4 YIELDING; multiplayr_state.ts:99,308; ambiguity audit M4

- **Claim:** §13 'Hearts when discard has fewer than N cards: move all of them (min(N, |discard|)); empty discard → no effect. (All engines; no official ruling found.)'
  **Problem:** Correct, but the report under-states the evidence and misses that the rulebook's asymmetry (Diamonds has a shortfall clause, Hearts does not) is a recognised ambiguity (audit H2). Also missing: Hearts moves cards from the discard only — never from the cards currently on the table or from hands.
  **Corrected:** Confirmed consensus across ≥10 engines (1789, Cinglein, HelloClaraCards, heart2heart, str4nge-m4g1c/kingslayer, pholser test 'heal caps at available cards', Diismas19, stealthfire, xunserver, RegicideRL). Spec: heal = min(N, |discard|); shuffle discard, take `heal` cards, place under Tavern bottom in random order; remaining discard returns face-up. Zero-length is legal and the play is still legal ('mandatory' power with nothing to do).
  **Source:** engine grep across scratchpad/repos; ambiguity audit H2


## Corrected spec

# Regicide — base rules, implementation-grade spec (verified)

Legend: **[O]** = backed by official rulebook text (RegicideRulesA4, post-solo revision; two independent transcriptions identical sentence-for-sentence; corroborated by the BGA official help text). **[I]** = inferred / engine consensus, not stated in the rulebook — put a code comment and, where sensible, a config toggle. **[U]** = could not be verified from this environment (BGG, publisher site, app stores unreachable; WebSearch budget exhausted).

Canonical text files: `scratchpad/dl/rules/RegicideRulesA4_main.txt` (raw pdftotext) and `scratchpad/dl/rules/drpaj12_rules_in_text.txt` (clean; note its "(or choose randomly)" is a transcriber's addition). BGA official help (English): `scratchpad/dl2/bga-help-zh-main/file`.

---

## 1. Components / card model [O]

- 52-card deck + 2 Jokers ("Jesters") = 54 cards. Any deck works; official art by Sketchgoblin.
- Ranks: 2–10 attack cards; **A = Animal Companion** (value 1); **J/Q/K = enemies** (also playable/discardable from hand at 10/15/20); **Jester** = no suit, value 0 (attack and discard).
- Card value function: `2–10 → face; A → 1; J → 10; Q → 15; K → 20; Jester → 0`. Same function for attack and for Step-4 discard.
- Suits: ♥ ♦ ♣ ♠. Jesters have no suit.

## 2. Setup [O]

1. **Castle deck**: shuffle 4 Kings → bottom; shuffle 4 Queens → on top; shuffle 4 Jacks → on top. 12 cards. Flip the top card: the current enemy is always a random Jack.
2. **Tavern deck**: all 2–10 (36) + 4 Aces + N Jesters (table), shuffled.
3. **Discard pile**: starts empty, face-up.
4. Deal each player up to max hand size.

| Players | Jesters in Tavern | Max hand size | Tavern before deal | Tavern after deal |
|---|---|---|---|---|
| 1 | 0 (both Jesters set aside as solo flip tokens) | 8 | 40 | 32 |
| 2 | 0 (both Jesters out of the game) | 7 | 40 | 26 |
| 3 | 1 (other Jester out of the game) | 6 | 41 | 23 |
| 4 | 2 | 5 | 42 | 22 |

Verified identically in: raw PDF dump, clean transcription, BGA help ("Hand Size is 8-5 for 1-4 players"), 3 other transcriptions, 15+ independent engines. No dissent anywhere.

**Enemy stats** [O]:

| Enemy | Attack | Health |
|---|---|---|
| Jack | 10 | 20 |
| Queen | 15 | 30 |
| King | 20 | 40 |

Total health in a game = 360. Each enemy's suit = its immunity suit.

**First player** [O]: "The player to have most recently committed regicide goes first." No fallback in the rulebook → implement random / user choice.

## 3. State the engine must track

```
castle: [Card]            # face-down, top = next enemy
enemy: {card, health, attack, suit, damageTaken, spadesPlayedTotal, immunityCancelled}
tavern: [Card]            # top = draw position; "under the Tavern" = bottom
discard: [Card]           # any card type may be here
table: [Card]             # cards played against the current enemy (incl. Jesters) — NOT discard
hands: {player: [Card]}; maxHandSize
turn: current player; lastAction[player] ∈ {none, played, yielded}
solo: flipsRemaining (2), flipsUsed
awaitingJesterChoice: player | null
```

## 4. Turn structure [O]

Step 1 play or yield → Step 2 suit power(s) → Step 3 damage & defeat check → Step 4 suffer damage. **Fully resolve each step before the next** (the exact-kill placement, Hearts-before-Diamonds and killing-blow sequencing all depend on this) [I, universal].

### Step 1 — legal plays (exactly one of) [O unless marked]
1. One card 2–10 (value = number).
2. One Ace (value 1).
3. **Ace + exactly one other non-Jester card**: another Ace, a 2–10, or a J/Q/K in hand. Value = 1 + other. Both suits' powers at the total; same suit twice → power once. **No ≤10 cap on Ace pairs** [I — rulebook puts the cap only in COMBOS and says Aces "cannot be added to a combo"; BGA and all engines agree; A+10=11, A+J=11, A+Q=16, A+K=21 legal]. Config: `maxCompanionPairRank` (default K).
4. **Combo**: 2, 3 or 4 cards of the **same number**, total ≤ 10. Exhaustive set: {2,2}, {2,2,2}, {2,2,2,2}, {3,3}, {3,3,3}, {4,4}, {5,5}. No Aces in combos; no J/Q/K (2 Jacks = 20). All distinct suits in a single deck. Config: `maxComboTotal` (default 10).
5. **Jester**, always alone (value 0). Never with an Ace, never in a combo.
6. One J/Q/K from hand alone (10/15/20) or with an Ace.
7. **Yield** (if permitted, §8).
Played cards go to `table` (in front of the player), not to discard.

### Step 2 — suit powers [O]
"Suit powers are mandatory and cannot be skipped." Compute `total` = sum of card values; `suits` = set of suits in the play minus the enemy's suit **unless** `enemy.immunityCancelled`. Each remaining suit's power resolves once at `total`:
- **♥ Hearts**: shuffle discard; move `min(total, |discard|)` cards face-down **under (bottom of) the Tavern**; rest of discard back face-up. Shortfall handling is [I] (ambiguity H2) but universal. Cards on `table` and in hands are never healed.
- **♦ Diamonds**: current player draws 1, then clockwise one at a time, skipping players at max hand size, never exceeding max, until `total` drawn, or Tavern empty (no penalty), or nobody can draw. Wrap-around to the current player on later laps is [I] (ambiguity M3), universal.
- **♣ Clubs**: Step-3 damage for this play = `2 × total`.
- **♠ Spades**: `enemy.spadesPlayedTotal += total`; persists, cumulative across all players, until the enemy is defeated.
Order: **Hearts, then Diamonds** [O: "resolve the Hearts healing before drawing with Diamonds"]; Clubs applies in Step 3; Spades in Step 4. Step 2 completes **before** the defeat check (see §6).

### Step 3 — damage & check [O]
`damage = total × (2 if ♣ active-and-not-immune else 1)`; `enemy.damageTaken += damage`. Defeated iff `damageTaken ≥ health` (cumulative over all players' plays; overkill is not carried over). Example from rulebook: 9 then 12 vs a Jack (20) → 21 → defeated.

### Step 4 — suffer damage [O]
If the enemy is not defeated (or the player yielded): `effectiveAttack = max(0, enemy.attack − effectiveShield)` where `effectiveShield = spadesPlayedTotal` unless (enemy.suit == ♠ and !immunityCancelled) in which case 0 [lazy computation makes the Jester retroactivity automatic]. The floor at 0 is [I]. The player discards cards (face-up, to discard) whose values sum to **≥ effectiveAttack**; over-paying is allowed [I: text says "at least"]; if effectiveAttack is 0 nothing is discarded; an empty hand is fine. If the player cannot reach the total → **everyone loses**. Then the next player clockwise starts Step 1.

## 5. Enemy immunity [O]
An enemy is immune to the suit power of cards matching its suit; the card's value still counts for damage. ♥ enemy: no heal. ♦ enemy: no draw. ♣ enemy: no doubling. ♠ enemy: no shield. In a mixed-suit play only the matching suit is suppressed [I, universal]. A Jester cancels the immunity for the rest of that enemy's fight [I on duration — rulebook says "will now take effect when played"; universal]. New enemy → immune again. In 1- and 2-player games immunity can never be cancelled (no Jesters in play; solo flips "do not cancel enemy immunity").

## 6. Defeating an enemy [O]
When `damageTaken ≥ health`, after Step 2 has fully resolved:
1. If `damageTaken == health` (post-Clubs damage) → enemy card **face-down on top of the Tavern** (next card drawn). Otherwise → discard.
2. All `table` cards (including any Jesters) → discard.
3. Reveal the next Castle card as the new enemy (full health, 0 damage, 0 spades, immune).
4. The defeating player **skips Step 4 and immediately starts a new turn (Step 1)** against the new enemy.
5. If the defeated enemy was the 12th (last King) → **win** immediately.
Sequencing consequences [I, from step order]: Diamonds draws of the killing play happen before the enemy is placed on the Tavern, so an exact-killed enemy is not drawn by that same play; Hearts of the killing play cannot heal the cards of that play or the enemy.

## 7. Drawn enemies in hand [O]
J=10, Q=15, K=20 both as attack and as discard value. Suit power applies normally at that value (e.g. K♣ alone = 40 damage; Q♥ heals 15; J♦ draws 10; A♠+K♠ = 21 shield, power once). Subject to the current enemy's immunity. Cannot be in a combo. Can pair with an Ace.

## 8. Yielding [O]
Yield = skip Steps 2 and 3, go straight to Step 4. "A player may not yield if every other player has yielded on their last turn." Implementation: `canYield(p) = !all(lastAction[q] == yielded for q != p)`. Any play (including a Jester) sets `played`. 2-player: no two consecutive yields. Window/reset is [I]: default no reset on new enemy (strict reading); toggle `resetYieldOnNewEnemy` (multiplayr behaviour). **Solo**: rulebook silent; BGA official help: "A player may not Yield in solo" (vacuous-truth reading) → default **not allowed**, toggle `soloCanYield` (ayrat555/AleDM1/CuatroSeis allow it).

## 9. Jester — multiplayer (3p: 1 Jester, 4p: 2) [O]
Played alone, value 0. Effects: (a) `enemy.immunityCancelled = true`; (b) **skip Steps 3 and 4** (no damage, no enemy attack); (c) the Jester's player **chooses any player to go next**; play then continues clockwise from the chosen player. Self-selection: "any player" literally includes self [I; allow by default, toggle `jesterMayChooseSelf`]. Retroactivity [O]: Spades already on the table vs a ♠ enemy start shielding once cancelled (lazy shield formula handles this); Clubs already played vs a ♣ enemy are **not** retroactively doubled; earlier blocked ♥/♦ are simply lost. The Jester card stays on `table` and goes to discard on defeat; from the discard it can be healed back under the Tavern by Hearts and drawn again [I]. A second Jester against an already-cancelled enemy is still a legal play with effects (b) and (c). Communication relaxation after a Jester ("I have a good play" / "I'd rather not go next") is social only. **No hand-discard effect in multiplayer** (that is solo-only).

## 10. Solo play [O]
Tavern = 40 cards, hand limit 8, both Jesters set aside as **two flip tokens**. Flip: **discard your whole hand, then draw up to 8 from the Tavern** ("does not count as drawing for the purpose of enemy diamond immunity" → works vs a ♦ enemy; does **not** cancel immunity). Timing: (a) at the start of Step 1 before playing/yielding, or (b) at the start of Step 4 before discarding for damage (the attack still happens; you discard from the new hand). Twice per game. If the Tavern has < 8 cards, draw what is available [I; rulebook silent]. Diamonds draws all go to the single hand up to 8. Victory tiers: 0 flips = Gold, 1 = Silver, 2 = Bronze. Empty hand at Step 1 with a flip remaining → flip and continue; empty hand with no flips (and no yield) → loss [I].

## 11. Game end [O]
Win: last King defeated. Lose: (a) current player cannot discard enough in Step 4; (b) at Step 1 the current player has no legal play and may not yield (solo: and has no flip remaining).

## 12. Communication (UI/hint boundary) [O]
Public: hand counts, Tavern count, discard contents (face-up), table cards, damage dealt, shield total. Private: hand contents and anything suggesting them.

## 13. Edge-case checklist for tests

| Case | Rule | Status |
|---|---|---|
| Tavern empty during Diamonds | draw what you can, no penalty, **never reshuffle discard** | O |
| Discard smaller than Hearts value | move all, no penalty | I (universal) |
| Exact kill with Clubs | compare doubled cumulative damage | O wording "damage dealt", I on explicitness |
| Exact kill of last King | game ends; placement moot | O |
| Killing blow with ♦ | draws resolve first; enemy on Tavern-top afterwards | I from step order |
| Spades vs ♠ enemy, then Jester | shield becomes spadesPlayedTotal immediately | O |
| Clubs vs ♣ enemy, then Jester | earlier damage unchanged | O |
| Shield ≥ attack | effective attack 0, discard nothing | I |
| Empty hand, may yield, attack 0 | survives | O ("It's ok to have an empty hand") |
| Empty hand, may not yield | lose (solo: unless a flip remains) | O / I |
| Ace + Jester / Ace in combo / Ace+Ace+X / 3 cards with Ace | illegal | O |
| A + K | legal, 21, both powers | I (BGA + all engines) |
| {4,4,4}, {6,6}, {J,J} | illegal (>10) | O |
| Jester recycled by Hearts | legal, ordinary card | I |
| Defeating player's bonus turn | new Step 1 vs new enemy, no Step 4 | O |
| Immunity after new enemy | restored | I (universal) |

## 14. Optional modifiers (config surface; NOT official base rules)
Fan "Companion Plus" (claims to mirror BGA table options; mapping **[U]** against BGA): hand size Default/+1/+2/−1/−2; Remove Jesters Default/−1/−2; enemy health Default/+5/+10/−5/−10 (all enemies); enemy attack Default/+2/+5/−2/−5; Yield On/Off; max combo total 10 default (9, 8, 6, 4, none; 12, 15, 18); max Ace-pair card K default … A, or none. BGA scraper DOM ids: gameoption_100 modifications on/off, 101 hand size, 103 enemy health, 104 enemy attack, 102 unknown. The official rulebook has **no** difficulty variants beyond the solo Gold/Silver/Bronze tiers. Regicide Legacy rules (Feign Death, revised Jester) are **[U]** and out of scope for the base engine.

## 15. Unverified-from-here items (flag in docs)
BGG filepage version note ("no substantive changes"), BGG fan-variant threads, Companion app IAP price/version history/review quotes, Regicide Legacy FAQ/rulebook wording, BGA release details. None contradict anything above; none should be cited as verified.

# Verification verdict 2

- **Claim:** §0: the rulebook text is "verified via two independent GitHub transcriptions … but not against the PDF bytes themselves"; and "Use [drpaj12_rules_in_text.txt] as the canonical rules text for the engine."
  **Problem:** The PDF bytes ARE obtainable: raw.githubusercontent.com/ettoremodina/RegicideRL/main/rules/RegicideRulesA4.pdf (2,079,061 bytes) hashes to SHA-256 46a7fb460b38f29e7644094267bf5bf097552258be5fdc43f35c25c123ba54be — exactly the hash the who-goes-first project recorded for the publisher URL. pdfinfo: Adobe InDesign 16.4, CreationDate 2021-10-19 20:29:43 UTC (= the BGG '19 Oct 2021' version). My own `pdftotext` output diffs with ZERO differences against RegicideRulesA4_main.txt, so that file is a verified extraction, not an independent transcription. The drpaj12 copy is not independent either and contains an insertion that is NOT in the official PDF: "(or choose randomly)" after "goes first". Calling it canonical propagates a non-official sentence.
  **Corrected:** Treat the verified PDF extraction as canonical: /tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/verify_pdf/layout.txt (pdftotext -layout) and raw.txt; PDF itself at …/verify_pdf/rules_2e32e4.pdf. Official first-player sentence is only: "The player to have most recently committed regicide goes first." (random choice is an implementation fallback, not rules text). Also: pypi.org and the GitHub code-search API were reachable, not only github.com.
  **Source:** sha256sum + pdfinfo + diff run in this session on the downloaded PDF; who-goes-first JSON (…/dl/rules/whogoesfirst.json) internalEvidence SHA-256; drpaj12_rules_in_text.txt line 'regicide goes first (or choose randomly)' vs PDF 'regicide goes first.'

- **Claim:** §4 Step 3 / §13: "Exact kill (total == health, e.g. exactly 20/30/40) → enemy card goes face-down on TOP of the Tavern" — with no statement of which quantity is compared when Clubs doubled the hit.
  **Problem:** The rulebook's test is "If the players have dealt damage exactly equal to the enemy's health" and Clubs says "damage dealt by clubs counts for double", so the compared quantity is post-doubling damage dealt, not card pips. The report never says so; the third-party ambiguity audit lists this as a recurring table argument (M2). All examined engines compare the doubled amount (multiplayr HitEvent.amount is 'already doubled by Clubs'; RegicideRL compares damage_taken).
  **Corrected:** exact_kill := (cumulative damage dealt against this enemy, where each hit = play total ×2 if a non-immune Club was in the play) == enemy.health. Example: King at 24/40 damage, play 8♣ (not immune) → +16 → 40 → exact → King face-down on top of Tavern. Overkill (>health) → discard.
  **Source:** PDF Clubs text + Step Three (i); ymonnet/regicide-pre-print-ambiguity-audit M2; multiplayr_state.ts HitEvent comment; regicideRL_game.py is_defeated().

- **Claim:** §9: a Jester is described only as the way to cancel immunity ("Step 2 power = set immunityCancelled = true").
  **Problem:** Omission: nothing in the rulebook conditions playing a Jester on the enemy still being immune. A second Jester (4-player game) or a Jester vs an already-cancelled enemy is a fully legal Step-1 play whose remaining effects (skip Steps 3 and 4 — i.e. no enemy attack — and choose who goes next) are often the point. An engine that rejects it would be wrong.
  **Corrected:** A Jester in hand is always a legal single-card play. Effects, in order: (1) immunityCancelled := true (idempotent); (2) skip Step 3 and Step 4; (3) the Jester's player chooses the next player; clockwise order then resumes from the chosen player. The Jester stays on the table with the other played cards and goes to the discard when the enemy is defeated.
  **Source:** PDF 'Playing the Jester' (no precondition stated); multiplayr play_jester() only checks the card; Step Four last sentence for resumption order.

- **Claim:** §8: "track each player's most recent turn action (played / yielded). Current player may yield iff NOT (every other player's last action == yielded)."
  **Problem:** Incomplete in three ways. (a) Initial state undefined: players who have not yet had a turn must count as NOT yielded (so the first player may yield at game start; in 3p P1-yield, P2-yield ⇒ P3 may not). (b) Turn order after a Jester choice undefined: play continues clockwise from the CHOSEN player ("After suffering damage, the next player in clockwise order begins their turn"), not from the Jester player. (c) The report cites RegicideRL as implementing the rule, but RegicideRL actually uses a different semantic — it clears everyone's yield flag whenever anyone plays a card (_reset_yield_tracking) — which diverges from the literal per-player rule only in Jester-reordered sequences. (d) The concrete case where the 'reset per enemy?' question decides a game: a player who kills the enemy with their last card takes a new turn (Step 3 iv) with an empty hand; under the literal reading they may yield only if some other player's last turn was a play, otherwise they lose immediately; multiplayr's per-enemy reset lets them yield.
  **Corrected:** lastAction[p] ∈ {None, PLAYED, YIELDED}, initialised None. canYield(p) := solo ? false : exists q≠p with lastAction[q] != YIELDED. PLAYED includes Jester plays. lastAction is NOT reset when a new enemy is revealed (literal reading; config `yield_reset_per_enemy` default false). After a Jester choice, currentPlayer := chosen; subsequent turns proceed clockwise from there.
  **Source:** PDF Yielding + Step Four; regicideRL_game.py _reset_yield_tracking/choose_next_player; multiplayr_state.ts line 308 ('A new enemy is fresh context: yield tracking resets') and choose_next_player → begin_turn(nextId).

- **Claim:** §9 / §13: Jester self-selection — "'any player' is read by Home of Mark and the RegicideRL tests as including themselves" presented as the consensus.
  **Problem:** There is no consensus. CuatroSeis/regicide-web's engine throws 'jester_self_target' ("The Jester must choose another player"); Chernowi/RegiSide's rules doc says "any player (including themselves)"; RegicideRL's test picks self. BGA's official help only says "the next player to take a turn is chosen by the active player, rather than clockwise". The ambiguity audit rates this High (H3) because choosing yourself = two consecutive turns with full hand knowledge.
  **Corrected:** Unresolved by any primary source. Literal text ("any player") permits self. Expose `jester_may_choose_self` (default true = literal reading) and surface it in the UI; do not describe either reading as official.
  **Source:** PDF Jester text; BGA help mirror (…/dl2/bga-help-zh-main/file); CuatroSeis__regicide-web/packages/engine/src/turn.ts:310; Chernowi RegiSide docs/regicide_rules.md; regicideRL_tests.py:411; ymonnet audit H3.

- **Claim:** §4 Step 4: "over-paying is allowed; discarding more than necessary is legal … If effective attack is 0 (fully shielded) nothing need be discarded."
  **Problem:** Leaves two engine-relevant questions open: whether a player may discard voluntarily when the effective attack is 0, and whether unnecessary extra cards may be added to an already-sufficient discard. The rulebook frames discarding solely as covering damage ("discard cards … with a total value at least equal to the enemy's attack value"); when the attack is 0 there is no damage to cover and no engine examined offers a discard prompt (multiplayr skips when pendingDamage is 0; RegicideRL reports 'No enemy damage due to Spades protection'). Over-payment with surplus cards is permitted by the text's 'at least' and is explicitly tested as legal in pholser/regicide-python.
  **Corrected:** If effectiveAttack == 0: Step 4 is a no-op (no discard allowed). Else the player chooses any subset S of hand with sum(value) ≥ effectiveAttack; surplus is legal (optional `strict_minimal_discard` toggle, default off). Cannot reach the total with the whole hand ⇒ loss.
  **Source:** PDF Step Four; multiplayr_state.ts pendingDamage handling; regicideRL_game.py yield_turn messages; pholser regicide-python tests/test_legal_moves.py test_includes_overpaying_discard.

- **Claim:** §5 Hearts (and §13): "Hearts when discard has fewer than N cards: move all of them … empty discard → no effect."
  **Problem:** Correct but incomplete for an engine. (1) At Hearts resolution the cards just played are on the table, not in the discard, so a play can never heal itself; cards discarded in earlier Step 4s and overkilled enemies ARE healable. (2) The moved cards are placed under the Tavern in shuffled, hidden order ("no peeking") — this is hidden information and a determinism/seed point. (3) Hearts resolves even if the Tavern is empty (the healed cards simply become the Tavern). (4) Hearts resolves before Diamonds in the same play, so a Diamonds draw can only reach healed cards if the Tavern held fewer cards than the draw count. The ambiguity audit rates the shortfall case High (H2) because 'mandatory' + undefined shortfall.
  **Corrected:** heal(n): k = min(n, |discard|); if k == 0 return; shuffle discard (hidden RNG); move k cards face-down to the BOTTOM of the Tavern; remaining discard stays face-up. Resolve before any Diamonds draw of the same play.
  **Source:** PDF Hearts text, Step Three (ii), Animal Companions/Combos 'resolve the Hearts healing before drawing with Diamonds'; ymonnet audit H2; regicideRL _hearts_power (min(value, len(discard))).

- **Claim:** §12 Solo: flip = "move entire hand to discard, then draw up to 8"; timing windows start of Step 1 / start of Step 4.
  **Problem:** Omissions that affect the engine: (1) the flip windows are "at the start of Step 1 before you play a card" — therefore the solo loss check for an empty hand must run AFTER the flip opportunity (a solo player with an empty hand and a Jester left may flip, refill and then play); (2) nothing forbids flipping both Jesters in the same window (two consecutive discard-refills); (3) the refill draws from the top of the Tavern, so an exact-killed royal sitting on top is drawn by it; (4) the discarded hand goes to the discard pile (later healable by Hearts); (5) the flip is also available on the fresh Step 1 that follows a defeat (Step 3 iv); (6) Tavern < 8 ⇒ draw what exists (inferred, no official ruling); (7) the setup table's '1 player → 0 Jesters' means zero in the Tavern while two are set aside (the audit flags this apparent inconsistency, L3).
  **Corrected:** Solo flip(window ∈ {START_STEP1, START_STEP4}): require solo && flipsRemaining > 0; discard whole hand to discard pile; draw min(8, |Tavern|) from the top; flipsRemaining -= 1; flipsUsed += 1; does not cancel immunity; allowed vs a ♦ enemy; may be repeated in the same window while flips remain. Empty-hand loss check in solo occurs only once no flip is taken/available.
  **Source:** PDF Solo Play section verbatim; BGA help 'Solo Game'; ymonnet audit L3; multiplayr solo_refill(); regicideRL solo_jesters_remaining.

- **Claim:** §3: loss condition (b) "at Step 1 the current player has no legal play AND is not permitted to yield".
  **Problem:** Should be made precise: every card is playable on its own (2–10, A, Jester, J/Q/K), so with a non-empty hand there is always a legal play; condition (b) can only trigger with an EMPTY hand when yielding is forbidden. In solo (yield never allowed) an empty hand at Step 1 with no flips left is an immediate loss; the BGA help states this explicitly ('unable to play a card when the player cannot yield (because all the other players have yielded or in solo mode)').
  **Corrected:** lose_b := hand(current).empty && !canYield(current) && !(solo && flipsRemaining > 0 && player chooses to flip). A player with an empty hand who MAY yield does so and survives Step 4 only if effectiveAttack == 0.
  **Source:** PDF Game End + Step One; BGA help 'Game End'; multiplayr RegicideViews ('an empty hand with yielding blocked'); regicideRL _check_player_can_act.

- **Claim:** §8 / uncertainties: solo yielding — 'BGA rules not allowed; RegicideRL agrees; ayrat555's engine allows it. No designer statement found. Recommend not allowed with a toggle.'
  **Problem:** Verified and the weight of evidence is stronger than stated: BGA (the licensed implementation), RegicideRL (test_solo_player_cannot_yield), multiplayr (can_yield: 'if solo return false'), and pholser/regicide-python (explicit vacuous-truth comment) all forbid; only ayrat555 allows. The literal rule ('may not yield if every other player has yielded on their last turn') is vacuously satisfied with zero other players, so 'not allowed' is also the strict textual reading, not merely BGA's house ruling.
  **Corrected:** Solo: yielding is never allowed (strict reading + BGA). Keep `solo_can_yield` as an opt-in variant only.
  **Source:** BGA help mirror 'A player may not Yield in solo'; regicideRL_tests.py:480; multiplayr_state.ts:531; pholser regicide-python regicide/turn_order.py; ayrat_rules.rs ('solo: always allowed').

- **Claim:** §5 DIAMONDS / §13: "round-robin starting with current player; skip full hands; never exceed max; stop when N drawn or Tavern empty (or everyone full)".
  **Problem:** Correct, but the rulebook sentence ('The other players follow in clockwise order…') reads like a single pass; the audit (M3) flags whether the current player draws again on later laps. Both reference engines loop around the table including the current player until N drawn / Tavern empty / all hands full — make the looping explicit so nobody implements a single pass.
  **Corrected:** draw(n): i := current; drawn := 0; while drawn < n && Tavern non-empty: if |hand[i]| < maxHand then hand[i] += Tavern.pop_top(); drawn++; i := (i+1) mod P; if i == current && every hand full: break. Solo: equivalent to drawing min(n, 8−|hand|, |Tavern|).
  **Source:** PDF Diamonds text; regicideRL _diamonds_power; multiplayr Diamonds loop; ymonnet audit M3.

- **Claim:** §2 Setup: 'Deal cards to each player up to their maximum hand size.'
  **Problem:** Deal order is unspecified; irrelevant for fairness but must be fixed for seeded/replayable games.
  **Corrected:** Define deterministically: shuffle Tavern with the game seed, then deal one card at a time clockwise starting with the first player until every hand holds maxHand (any fixed scheme is acceptable; document it).
  **Source:** PDF Setup (silent on order).

- **Claim:** §16: Regicide Companion app 'Version 2.5–2.6 (Nov 2025); 2.2 added solo stats; IAP $2.99/£2.99; reviewer complaints …'.
  **Problem:** None of this is verifiable from this environment (App Store / Play Store / BGG blocked; the sibling companion-app research explicitly labels price, version history and reviews UNVERIFIED and sourced from recollection). Not a rules issue, but it should not be presented as verified.
  **Corrected:** Mark store version numbers, IAP price and reviewer complaints as unverified; the only verified app facts are: name 'Regicide Companion' (rulebook back page), Badgers From Mars, Unity-based Android package com.bfm.regicidecompanion with Google Play Billing (IAP exists), iOS id1565706782.
  **Source:** …/scratchpad/research/companion.md §0–§3; …/dl2/taptrap-json/file.

- **Claim:** §15: Regicide Legacy Kickstarter FAQ offers 'Feign Death' and the Jester change as rules 'you're welcome to incorporate into your existing games of Regicide'.
  **Problem:** Outside this verifier's base-rules lens and not verifiable here (Kickstarter blocked; known only via search snippets). Must not leak into the base engine's default rule set.
  **Corrected:** Keep as clearly-labelled optional Legacy variants, default off; base Regicide has no Feign Death and the Jester player chooses the next player.
  **Source:** …/scratchpad/research/legacy.md (snippet-derived, tagged C by that agent but not independently confirmable here).

- **Claim:** §4 Step 1 list item 3 cross-reference '(see §7)' for J/Q/K drawn from the Tavern; §7 statement that combos 'may contain duplicate suits'.
  **Problem:** Editorial: the cross-reference should point to §10 (Drawing a defeated enemy). Combo note is correct (e.g. 5♣+5♠ legal; the same physical suit twice is impossible in one deck except via no mechanism — a suit appearing in more than one card of a combo applies its power once at the total, exactly like the Animal-Companion same-suit rule).
  **Corrected:** Fix cross-reference; keep rule.
  **Source:** PDF 'Drawing a defeated enemy' and 'Combos'.


## Corrected spec

# Regicide (base game) — implementation-grade rules spec, verified against the official PDF

**Provenance.** Official rulebook `RegicideRulesA4.pdf`, Badgers From Mars, SHA-256 `46a7fb460b38f29e7644094267bf5bf097552258be5fdc43f35c25c123ba54be`, created 2021-10-19 (InDesign; the "19 Oct 2021 final and comprehensive rules incl. solo" revision). Local copy: `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/verify_pdf/rules_2e32e4.pdf`; text: `…/verify_pdf/layout.txt`. Secondary: Board Game Arena official help page (licensed implementation; mirror at `…/scratchpad/dl2/bga-help-zh-main/file`). Tags: **[R]** rulebook text, **[BGA]** BGA help, **[INF]** inference/consensus not stated by the rulebook, **[CFG]** genuinely ambiguous → engine switch.

## 1. Components and constants [R]
- 52 cards + 2 Jokers ("Jesters"). 2–10 = attack cards; A = Animal Companion; J/Q/K = the 12 enemies.
- Card values (attack AND discard): 2–10 face; A = 1; Jester = 0; J = 10, Q = 15, K = 20 (face cards only ever reach hands via exact kills).
- Enemies: Jack attack 10 / health 20; Queen 15 / 30; King 20 / 40. Total health 360.
- Each enemy is immune to the suit power of its own suit (damage still counts).

| Players | Jesters shuffled into Tavern | Max hand size |
|---|---|---|
| 1 | 0 (both Jesters set aside as solo flips) | 8 |
| 2 | 0 (Jesters unused) | 7 |
| 3 | 1 | 6 |
| 4 | 2 | 5 |

Tavern size = 36 + 4 + Jesters = 40 / 40 / 41 / 42; after the deal 32 / 26 / 23 / 22.

## 2. Setup [R]
1. Castle: shuffle 4 Kings face-down; shuffle 4 Queens on top; shuffle 4 Jacks on top. Flip the top card: the first enemy is always a Jack.
2. Tavern: shuffle 2–10 (all suits) + 4 Aces + Jesters per table. Discard pile starts empty.
3. Deal every player a full hand (max hand size). Deal order unspecified [R] → deal one card at a time clockwise from the first player [CFG, cosmetic].
4. First player: "The player to have most recently committed regicide goes first." No fallback in the text → engine picks seat 0 / random [INF].
5. Players sit in a fixed clockwise order.

## 3. State
```
enemy: {rank, suit, health, attack, damageTaken, spadesPlayedTotal, immunityCancelled}
castle: [face-down enemies]; tavern: [stack, top = next draw]; discard: [face-up]
table: cards played against the current enemy (incl. Jesters)
hands[p]; lastAction[p] ∈ {None, PLAYED, YIELDED} (init None)
current: player index; pendingChooser (Jester)
solo: flipsRemaining (2), flipsUsed
```
Derived: `effectiveShield = (enemy.suit == ♠ && !immunityCancelled) ? 0 : spadesPlayedTotal` [R: Spades + Jester retro clause]; `effectiveAttack = max(0, enemy.attack − effectiveShield)` [INF floor].

## 4. Turn flow [R]
```
turn(p):
  [solo] optional flip(s)                      # start of Step 1, before playing
  if hand[p] empty and !canYield(p): LOSE      # "unable to play a card or yield"
  Step1: play(cards) | yield
  if yield: goto Step4
  Step2: resolve powers (Hearts → Diamonds now; Clubs/Spades noted for Steps 3/4)
  if Jester: immunityCancelled=true; skip Step3 & Step4; p chooses next player; return
  Step3: deal damage; if defeated: resolve defeat; if last King: WIN; same player starts new turn(p) (Step 4 skipped)
  [solo] optional flip(s)                      # start of Step 4, before discarding
  Step4: suffer effectiveAttack; next = clockwise(p)
```
Each step fully resolves before the next [INF, load-bearing]. Played cards stay on the table (not in the discard) until the enemy is defeated [R].

## 5. Step 1 — legal plays [R]
With a non-empty hand there is always a legal play (any single card). Exactly one of:
1. One card: any 2–10, an Ace (1), a J/Q/K (10/15/20), or a Jester (0, see §10).
2. Animal Companion pair: one Ace + exactly one other non-Jester card (another Ace, a 2–10, or a J/Q/K). Value = 1 + other. NOT a combo: the ≤10 cap does not apply (A+10 = 11, A+K = 21 legal) [R: "cannot be added to a combo"; ambiguity noted by third-party audit, BGA exposes an optional cap].
3. Combo: 2, 3 or 4 cards of the same number with total ≤ 10 → exactly {2,2},{2,2,2},{2,2,2,2},{3,3},{3,3,3},{4,4},{5,5}. No Aces, no Jesters, no face cards. Any suits.
4. Yield (if permitted, §9).
Never: Ace + Jester, Ace inside a combo, 3+ cards containing an Ace, Jester with anything.

## 6. Step 2 — suit powers [R]
Let `T` = total attack value of the play (sum of card values). Collect the set of distinct suits in the play; a suit appearing on two cards (e.g. A♣+8♣) applies once. Drop suits equal to the enemy's suit unless `immunityCancelled` (per-card immunity, so mixed plays keep the other suits) [R + INF]. Then, in this order:
1. **Hearts — heal(T)**: k = min(T, |discard|); if k>0, shuffle the discard (hidden order), move k cards face-down to the BOTTOM of the Tavern; rest returns face-up. Works with an empty Tavern. The cards just played are on the table and cannot be healed by their own play. Shortfall rule is [INF] (rulebook silent).
2. **Diamonds — draw(T)**: `i=current; drawn=0; while drawn<T && tavern nonempty: if |hand[i]|<max: hand[i]+=tavern.pop(); drawn++; i=(i+1)%P; if i==current && all full: break`. Loops around the table including the current player; players at max are skipped; no penalty for an empty Tavern; the discard is never reshuffled into the Tavern. Solo: draw min(T, 8−|hand|, |tavern|).
3. **Clubs — damage ×2** in Step 3: the whole play total is doubled (8♦+A♣ → 18; 3♦3♠3♣ → draw 9, shield 9, 18 damage). Doubling never changes the T used by Hearts/Diamonds/Spades.
4. **Spades — shield(T)** in Step 4: `spadesPlayedTotal += T` ALWAYS (even if currently immune, so a later Jester makes them count); cumulative across all players; lasts until the enemy is defeated.
Powers are mandatory (no declining a draw/heal). A Jester play has no suit power.

## 7. Step 3 — damage and defeat [R]
`hit = T × (2 if Clubs active and not immune else 1)`; `damageTaken += hit`. Defeated iff `damageTaken ≥ health` (cumulative over all players' turns; overkill is not carried over).
On defeat, in order: (i) if `damageTaken == health` exactly — measured on damage dealt, i.e. after Clubs doubling — put the enemy FACE-DOWN ON TOP of the Tavern (it is the next card drawn, by Diamonds or a solo refill; its identity is public); otherwise put it in the discard. (ii) All cards on the table (incl. Jesters) → discard. (iii) Reset `spadesPlayedTotal=0, immunityCancelled=false, damageTaken=0`; reveal the next Castle card (full health/attack, own immunity). (iv) If that was the 12th enemy → WIN immediately. Otherwise the same player skips Step 4 and starts a new turn (Step 1) against the new enemy; `lastAction` is NOT reset by the new enemy [CFG `yield_reset_per_enemy`, default false].

## 8. Step 4 — suffer damage [R]
`need = effectiveAttack`. If `need == 0`: nothing happens (no discard offered) [INF]. Else the player must choose a subset of hand with total value ≥ need (values per §1; Jester 0; J/Q/K 10/15/20); over-payment and surplus cards are legal ("at least") [CFG `strict_minimal_discard`, default off]; discards go face-up to the discard pile. If the whole hand's total < need → everyone LOSES. An empty hand is fine when need == 0. Then the next player clockwise from the current player begins Step 1.

## 9. Yielding [R]
Yield = skip Steps 2–3, go straight to Step 4 with shields still applying. `canYield(p) = !solo && ∃ q≠p : lastAction[q] != YIELDED` (players who have not yet acted count as not-yielded; "every other player has yielded on their last turn" is vacuously true in solo → solo can never yield [R strict reading + BGA]). Any play, including a Jester, sets `lastAction=PLAYED`. 2-player: no two consecutive yields. Loss: empty hand and `!canYield` at Step 1 (after any solo flip opportunity).

## 10. Jester (3–4 players only) [R]
Always playable alone, even if immunity is already cancelled. Attack 0, discard value 0, no suit. Effects: `immunityCancelled = true` for the rest of this enemy [INF duration; BGA: "remove the suit of the royal"]; skip Steps 3 and 4 (no damage check, no enemy attack); the Jester's player chooses the next player — literal "any player" includes themselves [CFG `jester_may_choose_self`, default true; engines are split]. Clockwise order then resumes from the chosen player. Retroactivity: Spades already on the table vs a ♠ enemy start counting (handled by the derived `effectiveShield`); Clubs already banked vs a ♣ enemy are NOT re-doubled; earlier blocked Hearts/Diamonds are simply lost. Communication relaxation until the chosen player starts is UI-only. There is no "discard a hand" effect in multiplayer.

## 11. Royals in hand [R]
J/Q/K drawn from the Tavern: value 10/15/20 as attack or discard; suit power applies normally (K♣ = 40 damage unless vs a ♣ enemy; Q♥ heals 15; J♦ draws 10); subject to immunity like any card; may pair with an Ace; can never be in a combo.

## 12. Solo [R]
Hand limit 8; 0 Jesters in the Tavern, 2 set aside as flips. `flip()` allowed at the start of Step 1 (before playing) or the start of Step 4 (before discarding), while `flipsRemaining > 0`; may be used twice in the same window [INF, not prohibited]: discard the whole hand to the discard pile, then draw min(8, |tavern|) from the top (shortfall [INF]); counts as neither a draw for ♦ immunity nor an immunity cancel; the enemy still attacks after a Step-4 flip (discard from the new hand). Yield never allowed. Win tier by flips used: 0 Gold, 1 Silver, 2 Bronze. Solo empty hand at Step 1 with no flip taken → loss.

## 13. Game end [R]
Win: 12th enemy (last King) defeated — checked in Step 3 immediately. Lose: (a) a player cannot cover `effectiveAttack` in Step 4; (b) a player has an empty hand and may not yield at Step 1.

## 14. Config switches (ambiguities — none settled by a primary source)
`jester_may_choose_self` (default true) · `yield_reset_per_enemy` (false) · `solo_can_yield` (false) · `strict_minimal_discard` (false) · `hearts_shortfall = move_all` (fixed) · `solo_refill_shortfall = draw_available` (fixed). Legacy/BGA/app variants (Feign Death, no-choice Jester, hand/health/attack modifiers, combo cap, companion cap, Jester count) are NOT base rules; keep off by default.

## 15. Test matrix (minimum)
Castle order J→Q→K; tavern composition and post-deal counts per player count; enemy stats; all 7 combos legal and 4-4-4/6-6/A-in-combo/A+Jester illegal; A+10 and A+K legal at 11/21; same-suit pair applies power once; mixed play vs immune suit suppresses only that suit; 8♦+A♣ = draw 9 / 18 dmg; 3♦3♠3♣ = draw 9 / shield 9 / 18 dmg; Hearts before Diamonds (healed cards reachable only when Tavern short); Hearts shortfall/empty; Diamonds round-robin incl. current player, skip full, stop on empty Tavern/all full; Clubs doubled exact kill → Tavern top; overkill → discard; exact kill vs ♣ enemy not doubled; Spades floor 0 and persistence across turns/players; spades banked while ♠-immune then Jester → counted; Clubs before Jester not re-doubled; second Jester legal; Jester skips Steps 3–4 and chooser semantics (self allowed per config); clockwise resumes from chosen player; yield chains (2p alternate, 3p P1/P2 yield ⇒ P3 cannot, first player may yield at start); killer's new turn with empty hand under both yield-reset settings; Step 4 with attack 0 offers no discard; over-pay legal; cannot-cover ⇒ loss; empty hand + cannot yield ⇒ loss; same player continues after a kill; win on 12th kill; solo: flip at both windows, twice, refill draws exact-killed royal, Gold/Silver/Bronze, solo never yields, solo empty hand with flip available survives.

# Verification verdict 3

- **Claim:** §0: 'The rulebook text is verified via two independent GitHub transcriptions that agree word-for-word ... but not against the PDF bytes themselves.'
  **Problem:** Out of date / understated. The official PDF bytes ARE available locally in two byte-identical copies (from GitHub repos jonathonthill/1789 and 1412kaito/regicide). SHA-256 = 46a7fb460b38f29e7644094267bf5bf097552258be5fdc43f35c25c123ba54be, identical to the hash the who-goes-first project recorded for https://www.regicidegame.com/site_files/33132/upload_files/RegicideRulesA4.pdf (checked 2026-09-24). pdfinfo: Adobe InDesign 16.4, CreationDate Tue 19 Oct 2021 20:29:43 UTC, 2 pages — i.e. exactly the BGG '19 Oct 2021 final rules incl. solo' version. A word-multiset diff of pdftotext output vs the drpaj12 transcription shows ONLY these differences: the transcriber appended '(or choose randomly)' to the first-player sentence, added a 'Rules for Regicide' heading, substituted '(K) (Q) (J) (A) (*)' for suit/card glyphs, and the PDF additionally carries flavour text, credits, and the 'LEARN TO PLAY! / DOWNLOAD THE FREE REGICIDE COMPANION APP!' footer. No rule sentence differs.
  **Corrected:** Treat the PDF itself as canonical: /tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/verify_pdf/rules_2e32e4.pdf (text dumps: verify_pdf/layout.txt = `pdftotext -layout`, verify_pdf/out/plain_mine.txt, verify_pdf/out/raw_mine.txt). The official first-player sentence is exactly 'The player to have most recently committed regicide goes first.' with no fallback; implement as random/host choice.
  **Source:** verify_pdf/rules_2e32e4.pdf + sha256sum + pdfinfo; verify_pdf/layout.txt; dl/rules/whogoesfirst.json (internalEvidence SHA-256); my word-multiset diff run this session.

- **Claim:** §7: 'A combo may contain duplicate suits (e.g. 2♣2♣ is impossible in one deck, but 5♣5♠ etc.); a suit appearing twice applies its power once at the total.'
  **Problem:** Garbled/false. A combo is 2–4 cards of the SAME number from a single 52-card deck, so every card in a combo necessarily has a distinct suit; duplicate suits in a combo are impossible. The only play in which one suit can appear twice is an Animal Companion pairing with a same-suit card (e.g. A♣ + 8♣), and that is the case the rulebook addresses ('you only apply the suit power once').
  **Corrected:** Combo cards always have distinct suits. The 'apply once' rule matters only for Ace + same-suit card; implement powers as a SET of suits present in the play, each resolved once at the play's total value.
  **Source:** Official PDF, COMBOS and ANIMAL COMPANIONS sections; deck composition.

- **Claim:** §3 loss condition (b): 'at Step 1 the current player has no legal play AND is not permitted to yield' and §4 Step 4: lose if the player cannot discard enough.
  **Problem:** Incomplete for solo. In solo the Jester flip is usable 'at the start of Step 1 before you play a card' and 'at the start of Step 4 before you have to take damage', so a loss must NOT be declared while a flip remains: an empty hand at Step 1, or a hand whose total value is below the effective attack at Step 4, is only a loss once no flips remain or the flip has been used and the condition still holds (e.g. the Tavern was empty so the refill drew nothing). Also, 'no legal play' is equivalent to 'empty hand' — any single card in hand (including a Jester, Ace or royal) is always a legal Step-1 play.
  **Corrected:** Loss checks: Step 1 start — if hand empty: (solo) offer flip while flipsRemaining>0, re-check after flip; (multi) if canYield → forced yield, else lose. Step 4 start — if sum(hand values) < effectiveAttack: (solo) offer flip while flipsRemaining>0, re-check; else lose. Never auto-lose while a solo flip is available.
  **Source:** Official PDF SOLO PLAY timing windows a)/b); Paper Crowns engine (dl/repos/regicide-kautiontape/src/lib/engine/game.ts damageCheck/playStartCheck/useJester and tests 'triggers loss ... when the last Jester refills nothing (empty tavern)'); multiplayr_state.ts ('Refilling can rescue a stuck pending-damage step').

- **Claim:** §4 Step 3 / §13: exact kill → enemy face-down on top of Tavern; overkill → discard. (No statement of what 'damage' is measured.)
  **Problem:** Omission. 'Exactly equal' must be measured on cumulative DAMAGE DEALT after Clubs doubling (and after immunity suppression of Clubs), not on card face value. E.g. King at 24/40, play 8♣ (enemy not ♣) → 16 dealt → 40 total → exact kill. Independent audit flags this as an unstated ambiguity (M2); every engine implements the dealt-damage reading.
  **Corrected:** exact = (enemy.damageTaken + damageDealtThisPlay == enemy.maxHP) where damageDealtThisPlay = playTotal × (2 if a ♣ power was active else 1).
  **Source:** Official PDF Step 3 wording 'If the players have dealt damage exactly equal to the enemy's health'; ymonnet pre-print ambiguity audit M2; Paper Crowns engine test 'exact kill ... club's double power is suppressed → damage = 10 vs HP 10 = exact'; multiplayr defeat_enemy(exact).

- **Claim:** §4/§13: Hearts → Diamonds → Clubs → Spades order; 'Played cards remain on the table until the enemy dies → NOT available to Hearts healing'.
  **Problem:** Omission of a load-bearing sequencing rule: Step 2 fully resolves BEFORE Step 3. Consequences the engine must honour: (a) a Diamonds draw completes before the defeat check, so the drawn cards come off the Tavern before an exact-killed enemy is placed on top of it; (b) Hearts shuffles/heals the discard before this turn's played cards and the defeated enemy reach the discard; (c) with Hearts+Diamonds in one play, Hearts goes first so healed cards can in principle be drawn only if the Tavern was nearly empty (they go UNDER the Tavern). The rulebook never states 'finish each step before the next' but every worked example assumes it (audit L4).
  **Corrected:** Resolution order per play: validate → Step 2 Hearts (heal to bottom of Tavern) → Step 2 Diamonds (draw) → Step 3 damage (×2 if ♣ active) → defeat processing (enemy to Tavern-top or discard; table → discard; reveal next; same player new turn) → else Step 4 (Spades shield applied as max(0, attack − effectiveShield)).
  **Source:** Official PDF 'Each turn has four steps' + Step 2 'Powers from red suits are resolved straight away'; ymonnet audit L4; all three engines.

- **Claim:** §9 Jester: 'Implementation: ... Step 2 power = set immunityCancelled = true ... Skip Step 3 and Step 4 ... The Jester player then chooses ANY player to go next'.
  **Problem:** Three omissions. (1) A Jester may legally be played even when the enemy's immunity is already cancelled (second Jester in a 4-player game) — it still skips Steps 3 and 4 (a free 'dodge' of the enemy attack) and still lets the player pick who goes next. (2) After the chosen player finishes their turn (Step 4), play continues clockwise FROM THE CHOSEN PLAYER, not from the Jester player (inferred; rulebook says only 'the next player in clockwise order'). (3) In 1- and 2-player games there are zero Jesters in the Tavern, so immunity can never be cancelled (audit H1); the engine must never expose a 'play Jester'/'cancel immunity' action at those counts, and the solo flip explicitly 'does not cancel enemy immunity'.
  **Corrected:** Add to spec: Jester legality does not depend on immunity state; next-player pointer after a Jester-chosen turn advances clockwise from the chosen player; immunityCancelled is unreachable for numPlayers ≤ 2.
  **Source:** Official PDF PLAYING THE JESTER, SETUP table, SOLO PLAY; ymonnet audit H1/H3/H4; multiplayr_state.ts (awaitingJesterChoice flow).

- **Claim:** §14: 'BGA offers table "variants" that relax the Ace/combo exceptions (per BGG thread 3286672)' and 'Exact modifier lists could not be retrieved.'
  **Problem:** Misattributed/unverified. The only concrete evidence available for BGA's option set is the DOM ids read by teapowell/BGA_Scraper: gameoption_100 = modifications Enabled/Disabled, gameoption_101 = hand-size modifier, gameoption_103 = enemy-health modifier, gameoption_104 = enemy-attack modifier (gameoption_102 unknown), plus a derived 'difficulty'/'modifier score'. The Ace-cap / combo-cap / yield-off / remove-Jesters options are documented only in the FAN app 'Regicide Companion Plus' (Poukame), whose author says he copied BGA's options — not verified against BGA. The official Regicide Companion app had NO difficulty options as of 2022 per that author.
  **Corrected:** State: BGA has (at least) hand-size, enemy-health and enemy-attack modifiers behind a 'modifications enabled' switch; whether BGA also has combo/companion caps, yield-off or Jester-count options is unverified (fan-app claim only). None of these are in the official rulebook; implement as clearly-labelled non-official modifiers if at all.
  **Source:** research/companion.md §4 (teapowell/BGA_Scraper DOM ids; Poukame/regicide-plus README and OptionsContext); official PDF contains no variants beyond solo medal tiers.

- **Claim:** §8: 'BGA (licensed implementation) rules "A player may not Yield in solo"' — known only from a search snippet.
  **Problem:** Verification upgrade, plus two extra BGA statements the report lacks. The full English body of en.doc.boardgamearena.com/Gamehelpregicide is available locally (mirrored inside a zh-CN wrapper page). It states verbatim: 'Yielding - A player may choose to Yield (pass) entirely, not playing a card but skipping straight to step 4. A player may not Yield in solo, or if every other player has Yielded on their last turn.'; 'Lose - A player is unable to defend an attack from a Royal or unable to play a card when the player cannot yield (because all the other players have yielded or in solo mode).'; 'Jester ... the next player to take a turn is chosen by the active player, rather than clockwise.'; 'Royals as allies - Royals retain their attack value when players play them (J10, Q15, K20) and that is also the amount of damage they can take'; 'Discarding - Cards are only discarded once a Royal is defeated ... any Spades played previously or by other players will stack. No other powers stack.' Caveat: BGA's summary says a Royal is defeated 'If the damage exceeds the Health' — imprecise; the official 'equal to or greater' governs (exact-damage rule proves equality defeats).
  **Corrected:** Solo yield = not allowed (official text vacuously implies it; BGA states it; RegicideRL and multiplayr implement it; only ayrat555's terminal game allows it). Ship 'solo cannot yield' as default; optional toggle.
  **Source:** dl2/bga-help-zh-main/file (English body of the BGA help page, source link to en.doc.boardgamearena.com/Gamehelpregicide); dl/rules/ayrat_rules.rs; dl/rules/regicideRL_tests.py test_solo_player_cannot_yield; multiplayr_state.ts can_yield.

- **Claim:** §4 Step 4: 'Player chooses which cards; over-paying is allowed; discarding more than necessary is legal (rule only says "at least equal").'
  **Problem:** Overstated certainty. The rule also says 'Discard the cards one at a time, faceup to the discard pile', which reads as 'discard until satisfied' and arguably forbids throwing extra cards once the total is met. The rulebook never explicitly permits or forbids surplus discards beyond the last card's overshoot. No engine/BGA evidence either way was obtainable.
  **Corrected:** Default: accept any subset with total ≥ effective attack (most permissive, matches report). Flag as inferred and expose an optional strict mode that rejects a discard set if removing any single card would still satisfy the attack.
  **Source:** Official PDF STEP FOUR wording.

- **Claim:** §12 solo: 'If the Tavern has fewer than 8 cards when refilling ... draw what is available.' (No statement on repeated flips.)
  **Problem:** Two omissions: (1) nothing in the rulebook prevents flipping BOTH Jesters in the same window (flip, dislike the new hand, flip again) — engines allow it (multiplayr: 'Solo refill is always an option while a Jester remains'); (2) the flip is also legal when it draws zero cards (empty Tavern) and when the effective attack is already 0 — pointless but legal. Confirmed refill = min(8, |Tavern|).
  **Corrected:** allowFlip = solo && flipsRemaining>0 && phase ∈ {start of Step 1, start of Step 4}; repeatable; refill count = min(8, tavern.length). Flips are the only solo rescue; loss is evaluated only after the player declines/exhausts flips.
  **Source:** Official PDF SOLO PLAY; Paper Crowns useJester (Math.min(limit, tavern.length)); multiplayr solo_refill.

- **Claim:** §8: yield tracking semantics ('each player's most recent turn action').
  **Problem:** Incomplete for a subtle case: the defeating player takes consecutive turns (rule (iv)), so turns do not strictly alternate; a naive 'previous N turns were yields' window is wrong. Also initial state must be 'nobody has yielded' so everyone may yield at game start. The independent audit (M4) flags the 'last turn' window as ambiguous; the per-player-last-action model is the only reading consistent with the 3-player example.
  **Corrected:** lastAction[p] ∈ {null,'played','yielded'}; canYield(cur) = numPlayers>1 && !all(lastAction[p]=='yielded' for p≠cur). Any play (incl. Jester) sets 'played'; yield sets 'yielded'; a defeat-then-new-turn keeps 'played'. Do not reset on new enemy by default (strict reading); optional toggle 'resetYieldOnNewEnemy' (multiplayr behaviour).
  **Source:** Official PDF YIELDING + Step 3 (iv); ymonnet audit M4; regicideRL_game.py can_yield; multiplayr_state.ts lastAction comment 'reset per enemy'.

- **Claim:** §0 warning covers only the MeepleLM file for the bogus 'redraw if no Diamonds' rule.
  **Problem:** The same non-official 'if nobody holds a ♦ after the deal, shuffle all hands back and redeal' rule also appears in Joat917/Regicide4's Chinese README (which cites merchantsofplay / gamerules.com / Games Night Guru). It is absent from the official PDF and from BGA's help page. MeepleLM additionally has the wrong Jester table (1 Jester for 2 players; 2 for 3–4).
  **Corrected:** No redeal rule exists officially. Jester table is 0/0/1/2 for 1/2/3/4 players (confirmed in the PDF layout dump and BGA page). Do not use MeepleLM or the Joat917 README as rule sources.
  **Source:** verify_pdf/layout.txt SETUP table; dl2/bga-help-zh-main/file; repos/Joat917__Regicide4/README.md; dl/rules/meeplelm_307002.md.

- **Claim:** §13 inferred list: 'Hearts when discard has fewer than N cards: move all of them ... (All engines; no official ruling found.)'
  **Problem:** Correct but under-flagged: the independent audit rates this High severity (H2) because Hearts is MANDATORY and, unlike Diamonds, has no shortfall clause; a stricter table reading ('you may not play it') exists. Also confirm: healed cards go to the BOTTOM ('under the Tavern deck'), the remainder of the discard stays face-up; if the Tavern is empty the healed cards simply become the Tavern.
  **Corrected:** Implement heal(k = min(value, |discard|)); never make a Heart unplayable; empty discard → no-op; comment the inference in code and tests.
  **Source:** Official PDF HEARTS + 'Suit powers are mandatory'; ymonnet audit H2; regicideRL_game.py min(value, len(discard_pile)); Paper Crowns applyPower.

- **Claim:** §5: mixed-suit play vs an immune suit suppresses only that suit's power; §9: Spades retroactive after Jester.
  **Problem:** Correct, but the engine detail is missing: because Spades played while the enemy is ♠-immune must 'begin reducing' once a Jester is played, the shield must be BANKED at play time for every play containing a ♠ (at the play's total value, once per play) and only MASKED while immunity is live. Hearts/Diamonds suppressed by immunity are simply lost; Clubs suppressed by immunity are not retro-doubled.
  **Corrected:** spadesTotal += playTotal whenever the play contains ≥1 ♠ (regardless of immunity); effectiveShield = (enemy.suit=='♠' && !immunityCancelled) ? 0 : spadesTotal; effectiveAttack = max(0, enemy.attack − effectiveShield).
  **Source:** Official PDF SPADES + Jester paragraph 'spades played prior to the Jester will begin reducing...'; multiplayr effective_shield; ymonnet audit M5.


## Corrected spec

# Regicide (base game, 2021 rulebook) — implementation-grade rules spec

Canonical source: official PDF `RegicideRulesA4.pdf` (Badgers From Mars, Adobe InDesign, created 2021-10-19; SHA-256 `46a7fb460b38f29e7644094267bf5bf097552258be5fdc43f35c25c123ba54be`), local copy `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/verify_pdf/rules_2e32e4.pdf`, text dump `verify_pdf/layout.txt`. Everything marked **[OFFICIAL]** is quoted/derived from that PDF. **[BGA]** = Board Game Arena's licensed help page (full English text at `scratchpad/dl2/bga-help-zh-main/file`). **[INFERRED]** = not stated anywhere official; consensus of engines/audit. Put the tag in code comments and tests.

## 1. Components and values
- 52-card deck + 2 Jokers ("Jesters"). 2–10 = attack cards; A = Animal Companion; J/Q/K = the 12 enemies; Jokers = Jesters. **[OFFICIAL]**
- Card value (attack AND discard): 2–10 face value; A = 1; Jester = 0; J = 10, Q = 15, K = 20 (royals only exist in hand after an exact kill). **[OFFICIAL]**
- Jester has no suit. **[OFFICIAL — implied; no suit power]**

## 2. Setup **[OFFICIAL]**
- Castle deck (face-down, top first): shuffle 4 Kings (bottom), shuffle 4 Queens on top, shuffle 4 Jacks on top. Flip the top card: first enemy is always a Jack.
- Tavern deck: shuffle 2–10 of all suits (36) + 4 Aces + Jesters per table. Discard pile starts empty.
- Table:

| Players | Jesters in Tavern | Max hand size |
|---|---|---|
| 1 | 0 (both Jesters set aside as solo flip tokens) | 8 |
| 2 | 0 | 7 |
| 3 | 1 | 6 |
| 4 | 2 | 5 |

- Tavern size 40/40/41/42; after dealing each player to max hand: 32/26/23/22. Castle = 12. Total enemy HP = 360.
- Deal each player up to their max hand size.
- First player: "The player to have most recently committed regicide goes first." (no fallback in the PDF) → implement as random / host choice. **[OFFICIAL text; fallback INFERRED]**
- Enemy stats: Jack 10 atk / 20 hp; Queen 15 / 30; King 20 / 40. Each enemy is immune to the suit power matching its own suit.

## 3. Win / lose **[OFFICIAL]**
- Win: the 12th enemy (last King) is defeated — immediately, no Step 4.
- Lose: (a) in Step 4 the current player cannot discard cards totalling ≥ the effective attack; (b) in Step 1 the current player "is unable to play a card or yield". A non-empty hand always has a legal play (any single card), so (b) ⇔ empty hand AND yield not permitted.
- Solo: loss (a)/(b) is only declared after the player has declined or exhausted Jester flips (see §11). **[OFFICIAL windows; sequencing INFERRED]**

## 4. State model (suggested)
```
Game: numPlayers(1..4), maxHand, castle[], tavern[] (index 0 = top), discard[] (face-up),
      hands[p][], table[] (cards played vs current enemy, incl. Jesters),
      enemy {card, suit, attack, maxHP, damageTaken, spadesTotal, immunityCancelled},
      current, lastAction[p] in {null,'played','yielded'},
      solo {flipsRemaining=2, flipsUsed=0}, phase, pendingJesterChoice (playerIdx|null)
effectiveShield = (enemy.suit=='S' && !enemy.immunityCancelled) ? 0 : enemy.spadesTotal
effectiveAttack = max(0, enemy.attack - effectiveShield)
```
Spades are BANKED at play time (even while ♠-immune) and only masked by live immunity, because "spades played prior to the Jester will begin reducing the attack value". **[OFFICIAL]**

## 5. Turn structure **[OFFICIAL]**
Step 1 play or yield → Step 2 suit powers (red immediate) → Step 3 damage + defeat check → Step 4 suffer damage. Fully resolve each step before the next **[INFERRED but load-bearing]**.

### Step 1 — legal plays (exactly one of)
1. One card of any kind (2–10, A, J/Q/K, Jester). Jester must be alone.
2. Ace + exactly one other non-Jester card (2–10, J/Q/K, or another Ace). Not a combo; the ≤10 cap does NOT apply (A+K = 21 is legal). Never 3+ cards with an Ace.
3. Combo: 2, 3 or 4 cards of the same number with total ≤ 10 → exactly {2,2},{2,2,2},{2,2,2,2},{3,3},{3,3,3},{4,4},{5,5}. Aces and royals can never be in a combo.
4. Yield (if permitted, §9).
Play value = sum of card values. Played cards go face-up on the table in front of the player and stay there until the enemy is defeated (they are NOT in the discard, so Hearts cannot heal them).
```
valid(cards): n=len(cards); n>0;
  if any Jester: n==1
  elif n==1: ok
  elif n==2 and any Ace: ok (other card is non-Jester)
  elif any Ace: invalid
  else: 2<=n<=4 and all same rank and sum<=10
```

### Step 2 — suit powers
- Powers are mandatory. Each DISTINCT suit in the play resolves ONCE at the play's TOTAL value (8♦+A♣ → draw 9 and 18 damage; 3♦3♠3♣ → draw 9, shield 9, 18 damage; A♣+8♣ → clubs once). Immune suit (== enemy suit, unless immunityCancelled) is suppressed; the card's value still counts for damage and other suits in the same play still resolve. **[OFFICIAL; mixed-play immunity INFERRED]**
- Order: Hearts, then Diamonds (Step 2); Clubs in Step 3; Spades in Step 4.
- HEARTS: shuffle discard; move k = min(value, |discard|) cards face-down to the BOTTOM of the Tavern; rest of discard stays face-up. Empty discard → no effect; a Heart is never unplayable. **[shortfall INFERRED]**
- DIAMONDS: round-robin starting with current player, one card each, clockwise, skipping players at max hand, looping (current player draws again on later laps) until value cards drawn OR Tavern empty OR everyone full. No penalty for an empty Tavern. NEVER reshuffle the discard into the Tavern. Solo: all draws go to the one hand up to 8.
- CLUBS: this play's damage ×2 (once per play, not per club card). Not retroactive.
- SPADES: enemy.spadesTotal += value (banked always); applies via effectiveShield in Step 4; cumulative over all players; cleared when the enemy is defeated.

### Step 3 — damage and defeat
- damage = value × (2 if a ♣ power was active else 1); enemy.damageTaken += damage. Cumulative over turns/players; overkill not carried.
- If damageTaken ≥ maxHP: defeated. exact = (damageTaken == maxHP) measured on DEALT damage (after Clubs). **[exact-after-clubs INFERRED, universal]**
  (i) exact → enemy card face-down on TOP of the Tavern (next card drawn); else → discard.
  (ii) all table cards (incl. Jesters) → discard.
  (iii) reveal next Castle card: reset damageTaken=0, spadesTotal=0, immunityCancelled=false. If the Castle is empty → WIN.
  (iv) same player skips Step 4 and starts a new turn (Step 1) vs the new enemy; lastAction[current]='played'.
- Because Step 2 finished first, Diamonds draws happen BEFORE the exact-killed enemy lands on the Tavern, and Hearts healed BEFORE this turn's cards reached the discard.

### Step 4 — suffer damage
- eff = effectiveAttack. If eff == 0 nothing is discarded (empty hand is fine).
- Player chooses cards from hand with total value ≥ eff; discard face-up one at a time. If sum(hand values) < eff → LOSE (solo: only after flips, §11). Surplus discards: default allowed; optional strict mode. **[INFERRED/ambiguous]**
- Then the next player clockwise begins Step 1.

## 6. Enemy immunity **[OFFICIAL]**
Enemy ignores the suit power of its own suit (♥ enemy: no heal; ♦: no draw; ♣: no doubling; ♠: no shield) but the number still counts as damage. Only a Jester cancels it (so never in 1–2 player games; the solo flip does NOT cancel immunity).

## 7. Jester (multiplayer only; 1 Jester in 3p, 2 in 4p) **[OFFICIAL unless noted]**
- Played alone, value 0, no suit. Legal whenever held, even if immunity is already cancelled. **[INFERRED]**
- Effect: enemy.immunityCancelled = true for the rest of this enemy **[duration INFERRED]**. Spades already banked now count (retroactive); Clubs already played are NOT re-doubled; lost Hearts/Diamonds stay lost.
- Skip Steps 3 and 4 (no damage, no enemy attack). Jester → table; lastAction='played'.
- The Jester's player chooses ANY player to go next — including themselves by default **[INFERRED; toggle]**. After that player's Step 4, play continues clockwise from THAT player. **[INFERRED]**
- Communication is loosened until the next player starts (UI: "I'd like to go next" / "I'd rather not" buttons as on BGA).
- Jester in Step 4 discards for 0.

## 8. Royals in hand (after an exact kill) **[OFFICIAL]**
J=10, Q=15, K=20 for both attack and discard; suit power applies normally (K♣ vs non-♣ enemy = 40 damage; A♠+K♠ = 21 shield once); subject to immunity; may pair with an Ace; can never be in a combo. Counts toward max hand size.

## 9. Yielding **[OFFICIAL text; model INFERRED]**
- Yield = skip Steps 2–3, go straight to Step 4.
- canYield(cur) = numPlayers > 1 AND NOT every other player's lastAction == 'yielded'. Initial lastAction = null (everyone may yield at start). Playing anything (incl. Jester) sets 'played'. Consecutive turns by the defeating player are handled naturally. 2p ⇒ no two consecutive yields. Default: no reset on a new enemy; toggle `resetYieldOnNewEnemy` (multiplayr behaviour).
- Solo: cannot yield (vacuous reading of the rule; **[BGA]** "A player may not Yield in solo"; toggle `allowSoloYield` default off).
- Empty hand at Step 1: forced yield if permitted (survives Step 4 only if eff == 0); else lose.

## 10. Game end **[OFFICIAL]**
See §3. Solo victory tier: flipsUsed 0 = Gold, 1 = Silver, 2 = Bronze.

## 11. Solo mode **[OFFICIAL unless noted]**
- Tavern = 40 cards (no Jesters); single hand, max 8; both Jesters set aside = 2 flips.
- Flip: discard entire hand face-up, then draw min(8, |Tavern|) **[shortfall INFERRED]**. Does not count as drawing for ♦ immunity (works vs ♦ enemy); does not cancel immunity.
- Windows: start of Step 1 before playing; start of Step 4 before discarding. Repeatable in the same window while flips remain **[INFERRED]**; legal even if it draws 0.
- After a Step-4 flip you must still cover the attack from the NEW hand. After a Step-1 flip you must still play (no yield).
- Loss only when: (Step 1) hand empty and flipsRemaining==0 (or flip used and still empty); (Step 4) sum(hand) < eff and flipsRemaining==0 (or flip used and still short).

## 12. Public information (for UI) **[OFFICIAL examples]**
Hand counts, Tavern count, table cards, damage dealt, shield total are public; discard is face-up (browsing it is a digital convenience **[INFERRED]**). Hidden: hand contents, Tavern order, Castle order (beyond J→Q→K structure).

## 13. Non-official toggles (ship OFF / labelled)
allowSoloYield; jesterMaySelectSelf (default ON); resetYieldOnNewEnemy; strictDiscard. Difficulty modifiers seen on BGA (hand size ±, enemy HP ±, enemy attack ± behind a 'modifications' switch) and in the fan Companion Plus app (Jester count, combo cap, companion cap, yield off) are NOT official. No official variants exist besides the solo medal tiers. Regicide Legacy house-rule offers (Feign Death, revised Jester) are Legacy, not base.

## 14. Test matrix (minimum)
Setup counts per player count; castle order J/Q/K; first enemy is a Jack; play validation table (incl. A+K ok, A+Jester no, A+A ok, 5+5 ok, 6+6 no, 2×4 ok, A in combo no, Jester alone only); powers at total value, once per suit; Hearts partial/empty discard → bottom of Tavern; Diamonds loops, skips full hands, stops on empty Tavern, no reshuffle; Clubs doubles once; exact kill after Clubs → Tavern top; overkill → discard; drawn royal values 10/15/20 + powers; immunity per suit, damage still counts, mixed-play partial suppression; Jester: cancel persists, Spades retroactive, Clubs not, skips 3–4, any-player choice, clockwise continues from chosen player, second Jester legal; shield floor 0; yield chains 2p/3p/4p incl. defeating-player consecutive turns; solo: no yield, flip windows, flip min(8,|Tavern|), flip then cover, loss only after flips, medal tiers; win on 12th kill with no Step 4; Hearts-before-Diamonds; Diamonds-before-exact-kill placement.

## 15. Unverifiable this session (flag)
badgersfrommars.com / regicidegame.com / BGG / BGA / Kickstarter were unreachable (DNS) and the WebSearch budget was exhausted; verification relied on the byte-verified PDF plus local mirrors. Not confirmed: whether the 2nd-edition rulebook text differs (none found); BGA's full option list; any designer FAQ rulings on solo yield, Hearts shortfall, Jester self-selection, immunity-cancel duration, yield reset per enemy, or surplus discards (an independent ambiguity audit, `scratchpad/repos/ymonnet__regicide-pre-print-ambiguity-audit/README.md`, lists exactly these as open).
