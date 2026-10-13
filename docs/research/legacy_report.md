# Regicide Legacy — Research Dossier for Implementation

## 0. How this was researched (read first — affects confidence)

- **Direct page fetches were impossible.** The sandbox's egress proxy returned 403 policy denials for kickstarter.com, badgersfrommars.com, regicidelegacy.com, boardgamegeek.com, spacebiff.com, rulespal.com, talkingshelfspace.com, youtube.com, etc. (`curl -sS "$HTTPS_PROXY/__agentproxy/status"` lists them as `connect_rejected`). WebFetch failed with ENOTFOUND on the same hosts. Per the proxy README these are org policy denials, not to be routed around.
- **What worked:** ~190 WebSearch queries (the tool returns page-derived summaries with quoted fragments), GitHub cloning, and files the parent session pre-staged in my scratchpad. The per-turn search budget (200) is now exhausted; a follow-up message would be needed to search further.
- **Local primary materials available to the engineer (absolute paths):**
  - Base Regicide rulebook, full text (official PDF transcription): `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl/rules/RegicideRulesA4_main.txt` (11,391 bytes; `_master.txt` is identical). Other base-rules transcriptions/engines in the same `rules/` folder: `regicideRL_game.py` + `regicideRL_tests.py`, `multiplayr_state.ts`, `kingslayer_rules.md`, `superset_en.adoc`, `drpaj12_rules_in_text.txt`, `steinea_regicide_legacy.md` (official BGG blurb).
  - Fan Regicide Legacy implementation (Vue/TS), cloned: `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl/gh/regicide-js/` — key files `CAMPAIGN_RULES.md`, `README.md`, `src/game/{types,campaign,missionSetup,enemy,suitpower,flute,deck,turnRules,defeatRules,missionActions,gamestate}.ts`. Single commit 2026-04-04, author DorkDad141. **Unofficial**, but its enemy counts/tiers per mission match the physical-contents guide (see §6), so it is a usable rules skeleton with renamed entities.
  - Pre-staged base-game engines: `/tmp/.../scratchpad/dl/repos/regi-py` (ahgamut/regi-py: C++ core + Python/WASM wrappers + RL bots, base Regicide) and `/tmp/.../scratchpad/dl/repos/regicide` (Kautiontape "Paper Crowns": Svelte solo base Regicide, MIT).
- **Confidence tags used below:** **[C]** = confirmed by official source (publisher site, rulebook transcription on rulespal.com, official compendium regicidelegacy.com, Kickstarter FAQ/updates) or by ≥2 independent reviewers; **[S]** = single secondary source (one reviewer/fan guide); **[F]** = only from the fan `regicide-js` reconstruction (unverified naming/wording); **[?]** = conflicting or unverified.

---

## 1. Identity, credits, and status

| Field | Value | Tag |
|---|---|---|
| Title | Regicide Legacy | C |
| Publisher | Badgers From Mars (Auckland, New Zealand) | C |
| Designers | Paul Abrahams, Luke Badger, Andy Richdale (same trio as Regicide); KS announcement signed "Paul, Luke, Andy, and DJ" | C |
| Art | Sketchgoblin | C |
| BGG ID | 412963 (English edition version id 699723, release **Aug 2025**, status Released) | C |
| Players / time / age | 1–4; 20–60 min; 12+ | C |
| BGG stats (snapshot ~Sept 2026) | avg 8.6 from 696 ratings; overall rank 2,498; weight 2.44/5. Older snapshots: 8.5 avg, rank 3,521–3,857, weight 2.6. Lankyrobot review: weight 3, rating 8, 30–45 min | C |
| Base Regicide for comparison | BGG 307002, rank 544, ~7.39 from ~9,600 ratings, weight 1.98 | C |
| Dev time | "in development for 3 years" at KS launch (May 2024) | C |
| Shown at | SPIEL Essen 2024 | S |
| SKUs | Base: BFMLEG001; Reset Box: BFMLEG002; Amazon ASIN B0H3NNF9Q4 (no price captured) | C |

### Kickstarter (https://www.kickstarter.com/projects/badgersfrommars/regicide-legacy)
- Funding period **May 8 – June 7, 2024** (29–30 days). Goal **NZ$35,000**. Final: **3,082 backers, NZ$506,235** [C]. Mid-campaign snapshots: TGN (May 9, 2024): US$82,591 vs US$21,021 goal with 28 days left; Kicktraq: 2,503 backers / NZ$409,131 / avg pledge NZ$163.
- **No stretch goals by design** — Update 2 "We've almost hit 250k, and still no stretch goals?": "Short answer, we don't like them… we don't try to make artificial goals." [C]
- **No Kickstarter exclusives**; retail version identical; KS price below MSRP; backers fulfilled first [C, KS FAQ]. A German backer reported **€62 game + €16 shipping** [S]; a retailer lists the "Kickstarter edition" at $94.99 [S]. **Pledge tier names/prices could not be retrieved** [?].
- Original delivery estimate: March 2025 (cwowd forum title) [S].
- Known updates (titles): **U2** "We've almost hit 250k, and still no stretch goals?" (during campaign); **U6** "Forging on with art and pre-production copies" (art completion is the big task; manufacturer doing box-size tweaks on next pre-production copy); **U16** "Fulfillment Update & More" (**Sept 12, 2025**): NZ finished ~4 weeks prior, Australia finished the week prior, USA + Central/South America fulfilment "finally kicked off", Canada stock landed, EU/UK stock "on a slow boat from China" landing end of month, EU shipping to backers targeted early September; some add-ons being restocked (pledges with add-ons delayed). Project page shows "Last updated April 13, 2026" (content unknown) and one snapshot says "8 updates listed" (inconsistent with U16 existing) [?]. Titles of other updates not retrievable.
- KS FAQ items confirmed [C]: starting player = whoever plays the first card; after a Jester, the Jester's player no longer picks who goes next — "players simply wait for someone to play next"; **Feign Death** (discard a full hand to satisfy a strike regardless of total) is in the rules and the designers suggest both as house rules for base Regicide; each mission pack has a **QR code** to online compendium videos (optional — all rules are on the cards); the rulebook at campaign time was deliberately incomplete ("new rules come in as you complete missions"); you can run concurrent campaigns with Reset Boxes ("a copy of Regicide Legacy and three reset boxes could run up to four concurrent campaigns"); eternal mode can be played with the finished deck while a new campaign runs from a Reset Box; the FAQ contains a "No you don't" answer (question text cut off — almost certainly "do you need base Regicide?") [?]; "the playmats, tokens and 4 special add-on packs come only with Legacy" (note: says 4, retail listing says 5 extra packs) [?].
- In the 2026 Inferno/Crown Duels campaign, Legacy was offered as an add-on shipped with that pledge [C].

### Shipping / availability as of 2026-10-13
- First printing retail: **August 2025** (BGG version date); KS fulfilment Jul–Sept 2025 by region (above) [C].
- **Sold out** in USA and Europe quickly; December 2025 publisher newsletter: reprint "well underway", new stock USA Feb 2026, Europe March 2026 [C]. Second printing changes Mission 6 rules (see §6) [C].
- **Publisher store today:** "Regicide Legacy (Preorder)" **US$95.00**, "We estimate preorders to begin shipping in **November 2026**" [C]. Another publisher page (Regicide reviews page) says "In stock and shipping now!" — contradictory; likely a further printing/restock [?]. Regicide Inferno preorder also lists Nov 2026.
- Retail prices seen: Miniature Market $89.00 (out of stock); Game Nerdz $71.97 (OOS); Gamers Guild AZ $80.75 (OOS); Noble Knight $80.00; Cardhaus $85 preorder "Q1 2026"; Philibert €79.95; Gus & Co paid €75; Geek Culture NZ RRP $139.99 (NZD); eBay $169.32. 
- **Reset Box:** publisher **US$65.00** (page shows both "Sold out" and "In stock" fragments) [?]; Miniature Market $55; Game Nerdz $45.97–$59; Gamers Guild $57.35–$59; Philibert €54.95; Gamers-HQ €44.95. EU resellers at one point had only Reset Boxes in stock.

---

## 2. Theme and story premise [C]
Official blurb: "A terrible corruption has spread over the world of **Deccaria**. The royalty have succumbed to its maddening haze. The **Golden Blade Syndicate** (a 40-strong band of professional adventurers) has been called upon by the **High Crown Council** to solve the mystery of this growing blight… Mission 1 familiarises the players with Regicide… subsequent missions bring new enemies, dynamic challenges and powerful upgrades. Recruit new adventurers to the party, access all-new classes and unlock powerful items." Reviewers: story is light ("just another fantasy story", Hiew; "less important than most legacy games"); Spacebiff liked it more than most. Named recurring characters that appear in the campaign (spoilers): Goran, Myla, Esme, the Evergreen (Mother), "High Arcana/High Arcane". Rulebook example enemy: "Letholdus the Justicar; he has 20 health!" [C].

---

## 3. Components

### Base box [C — publisher listing]
- 42 Party cards (40 adventurers + 2 Jesters)
- 4 Player helper cards (double-sided; icons + class-ability resolution order)
- 145 custom sleeves (matte; reviewers complain they blur text)
- 12 Skull tokens
- 2 Metal tracker tokens
- 5 Neoprene playmats
- 12 Mission boxes
- 5 Extra content packs
- 400+ cards inside packs
- 1 Rulebook (has blank spaces that stickers fill in)
- Compact box with magnetic lid [S]. One retailer phrase: "15 content packs unlocked during play plus 5 extra packs included" [?].

### Reset Box [C]
42 Party cards, 4 Player helpers, 145 sleeves, 12 Mission boxes, **2** Extra content packs, 300+ cards, 1 Rulebook. "Essentially a brand new copy of the game, minus the playmats and other shared components." **Not standalone** — requires base Legacy (for playmats, tokens, and the extra packs not duplicated). Lets you restart or run concurrent campaigns. A retailer photo caption describes reset-box spines "numbered 1 through 12, with two additional boxes marked G and F" [?].

### The 5 extra content packs — labelled **F, C, M, P, E** [S — Hiew, spoiler-free first look]
- **M** = Mercenaries. Opened "the first time you fail/lose a mission" [C, rulebook]. Contents [S, TSS repack guide]: M card, mercenary rules, rules stickers 25a/25b/25c, mercenary cards: **4× "12", 4× "2/5", 2× "19", 2× A, 2× Jester**.
- **E** = Eternal/Endless ("E-box"), opened at campaign end [C]. Contents [S]: "Evergreen rules", 5 Location cards (**Shrine, Cave, Forest, Hills, Lake**), **Bane cards 1–23**, **Boon cards 24–35**.
- **C** = Corruption pack: contains **4 corrupted-card stickers** (BGG "Pack C sticker question") and rules stickers 15c, 22a–c [S]; official compendium has a "Corruption Helper" page: "when corrupting a character you are asked to search the artwork of each party character" for particular features [C].
- **P** = almost certainly the **Pilgrim deck** introduced at Mission 7 (25 suitless cards, see §6) [S/F inference].
- **F** = unknown [?] (possibly "Feign Death"/"Flute"/"Beast(s)" — pure speculation).

### Playmats (5 neoprene) [C]
- **1 large central playmat:** background is the **map of Deccaria** (the mission's Location card shows where the party is on it). Zones: **Enemy deck** (face-down, current enemy face-up), **Reserve deck** (Legacy's name for the Tavern deck), **Discard pile**, **Banished pile** (face-up, inspectable, not used in Mission 1), **Mission zone** (mission-specific card area), **Enemy stat card** slot, and **health/strength tracks** for the two metal tracker tokens.
- **4 small player playmats:** each player's play area; the player helper card sits beside it; Jesters claimed are placed on it.
- **Skull tokens (12):** when an enemy is defeated, place a skull over that enemy's icon on the **enemy stat card** so you can see which enemies remain (one reviewer calls them wooden discs) [C].
- **Metal tracker tokens (2):** set on the central mat to the enemy's starting **health** and **strength** (Legacy's term for attack); strength changes during missions (Paladins reduce it; some missions raise it) [C].

### Card types (what the 400+ cards are) [C unless noted]
Party/adventurer cards (named characters, class icon(s), strength 2–10, Animal Companions = strength 1); Jesters; enemy cards per mission (grouped by strength, ordered weakest group to strongest); enemy stat cards; Location cards; Story cards; Mission rules cards (double-sided); 4 rules-summary cards per mission; sticker cards (rules stickers + card stickers); artifact/item cards; new party members (e.g., Goran, Myla, Esme, class decks Reaver/Guardian/Druid/Chanter 3/5/7/9, Beasts); mercenary cards; Pilgrim cards; Eternal-mode Location/Bane/Boon cards; "Arcane 25"-type special cards.

---

## 4. Core rules: base Regicide → Legacy mapping

### Base Regicide (full text local; key numbers) [C]
- Enemies: **Jack 10 atk/20 hp, Queen 15/30, King 20/40**; Castle deck = shuffled Jacks on shuffled Queens on shuffled Kings.
- Tavern = 2–10 ×4 suits + 4 Animal Companions (Aces) + Jesters by player count. **Players/Jesters/Max hand: 1→0/8, 2→0/7, 3→1/6, 4→2/5.**
- Turn: (1) play a card or yield; (2) suit power (red suits immediate; black later); (3) deal damage, check defeat; (4) suffer damage (discard ≥ enemy attack, Companions=1, Jester=0; can't → everyone loses).
- Suits: ♥ heal (shuffle discard, count N face-down under Tavern); ♦ draw N, current player first then clockwise, skip full hands; ♣ double damage; ♠ reduce enemy attack by N, cumulative while that enemy lives. Mandatory.
- Immunity: enemy immune to its own suit's power (number still counts). Jester (value 0, played alone) cancels immunity; player of Jester chooses who goes next (communication loosened until next turn). ♠ played before a Jester vs ♠ enemy start counting; ♣ played before a Jester vs ♣ enemy do not retro-double.
- Combos: 2/3/4 cards of the same number, total ≤10; Companion pairs with exactly one other card (incl. another Companion); same-suit pair applies power once; ♥ before ♦.
- Exact kill → enemy face-down on top of Tavern (J=10, Q=15, K=20 in hand; suit power applies when played); otherwise → discard. Defeating player skips step 4 and starts a new turn vs next enemy.
- Yield: can't if every other player yielded on their last turn. Lose also if a player can't play or yield.
- Solo: single hand of 8, two Jesters set aside, flip one to "discard hand and refill to 8" (twice/game; Bronze/Silver/Gold by Jesters used).

### Legacy terminology [C — rulebook transcription]
Tavern → **Reserve deck**; Castle → **Enemy deck**; attack value → **strength**; suit → **class**; suit power → **class ability**; new: **Mission zone**, **Banished pile**, **Enemy stat card**, **Location card**, **Mission rules card** + **rules summary cards**. Classes have their own icons and colours instead of French suits ("A Change of Suits" article).

### Legacy turn structure [C — rulebook table of contents]
"Turn Structure & Class Abilities": **Step 1: Form An Attack**, **Step 2: Cast Spells**, **Step 3: Deal Damage**, **Step 4a: Suffer Damage**, **Step 4b: Enemy Defeated**. Players finish their whole turn before the next player. Rulebook warns: the **order in which the Enemy Defeated step is resolved becomes very important in later missions**; **Communication rules (p.24) changed** — read them even if experienced. "If you cannot yield or play any cards, all players lose the mission." Protector classes (Paladin) resolve in the suffer-damage step; when several class abilities trigger, resolve in rulebook/helper-card order; worked example: paladin cuts enemy strength by 7 so it strikes back for 3; warriors double damage; bard draw goes current player first then clockwise until N drawn.

### Setup per mission [C]
Shuffle party + Jesters by player count (same table as base: 1→0/8, 2→0/7, 3→1/6, 4→2/5 — one garbled snippet said "2 jesters for two players"; treat the standard table as correct [?]) into the Reserve deck; players may count but not look at it; draw to hand limit; set trackers to the enemy's starting health/strength; enemy deck grouped by strength, weakest group on top. If player count changes between attempts, update Jesters. Discard pile may be inspected in Legacy [S — playthrough comment; consistent with Druid ability].

### Jester — changed in Legacy [C]
- Multiplayer (rulebook p.20): Jester is played alone; then **any player (including the one who played it) may claim the Jester** and put it on their player playmat; the claimer **takes over the current turn** and forms an attack from hand as normal; the enemy "doesn't lose immunity for following turns, only for the attack formed with the jester." (KS FAQ: no one is chosen; players wait for someone to play.)
- Solo (rulebook p.26): two Jesters set aside; **twice per game** you may play a Jester as an attack on its own: move it to your playmat, **choose one of the four basic classes**, it has **strength 8**, that class ability activates, it **ignores enemy immunity**, cannot be combined with other cards, and is flipped face-down once the enemy is defeated (unusable for the rest of that attempt). Hiew paraphrases it as "strength 8, any suit, suit applies despite immunity."
- Fan code treats Jesters as a separate pool of 2, value 8, chosen base class, removed after use (matches solo rule) [F].

### Feign Death [C]
When you are **at your hand limit**, you may discard your **entire hand** to satisfy an enemy strike even if the total is less than the strength. Added to remove unsatisfying losses where you draw to a full hand and still can't pay. Mission 7 compendium: a pilgrim in hand (which can't leave your hand that mission) makes feigning death impossible. (Fan code's "≥6 cards always satisfies" is a simplification [F].) BGG thread notes you usually need a draw ability to be at limit during step 4.

### Classes and party [C]
- 40 party cards = **4 classes × 10 characters** (strengths 2–10 plus one Animal Companion each) = the Golden Blade Syndicate; every card is a named character with race and class (examples: River, Herbod). Each class has a unique icon and colour. Animal Companions: strength 1, class ability applies, may pair with one other card (not a Jester), value 1 when discarded.
- Base classes: **Cleric** (♥-equivalent: heal from discard), **Bard** (♦: draw), **Warrior** (♣: double damage), **Paladin** (♠: reduce enemy strength). Icons: axe = Warrior, shield = Paladin, potion = Cleric, violin/musical instrument = Bard [S — Hiew/Spacebiff/TV Tropes]. (Base Regicide 2nd-ed companion art: pangolin ♠, fennec fox ♥, badger ♣, dove/duck ♦ — Legacy art may differ [?].)
- Enemies carry class icons and are **immune to class abilities of cards whose class matches their icon**; some later enemies have two icons (dual immunity). Corrupted/Restored cards and Jesters bypass immunity (see §5).
- New classes unlocked by missions (names **[C]** via physical-contents guide + Spacebiff: "the distinction between a Mage and a Reaver or between a Druid and a Chanter"): **Mage** (M3), **Reaver** (M5), **Guardian** (M6), **Druid** (M7), **Chanter** (M8). Their official ability text was not captured; fan reconstruction [F]:
  - Mage (★): reveal top N cards of reserve (N = attack value), pick 1 to add to the combo (its classes and value join), rest discarded; if the pick is a Mage it chains.
  - Druid: inspect the whole discard pile and redistribute up to 4 cards: one to hand, one to top of reserve, one to bottom, one banished; rest stay in chosen order.
  - Chanter (fan calls it "Drums", icon drum): draw up to N extra cards even beyond hand size, then discard down to hand size.
  - Reaver: reveal N cards, banish all of them, add the chosen card's value to damage and double the total (free double if reserve empty).
  - Guardian: take no damage from the enemy this turn.
  - Fan resolution order: Mages, Druids, Hearts, Diamonds, Drums, Spades, Guardians, Clubs, Reavers [F].
  - Icon hints from Hiew's photos: "drum" cards and a "mushroom" card in Myla's hand → drum = Chanter, mushroom likely Druid [S/?].

### Mission end [C]
Success: open the mission's sealed reward/booster pack; mercenaries leave; proceed. Failure: reset per the mission overview card and retry (first failure ever → open pack M). Banished party cards are gathered back with the discard at mission end (compendium, Mission 2).

---

## 5. Legacy mechanisms (items, stickers, corruption, mercenaries, beasts)

### Mission box contents [C]
Each of the 12 boxes: Location card (map progress), story cards, mission rules card (double-sided; e.g., Mission 5's back has a Mage rule), 4 rules-summary cards (one per player, kept beside their mat), enemy stat card, that mission's enemy cards (grouped/ordered by strength), and a **sealed reward pack** ("booster") opened only on success containing story cards, new party cards, stickers, artifacts and permanent rules. Boxes are opened only after completing the previous mission; "keep the cards in order, read each card and resolve instructions before proceeding; return resolved cards to the pack unless told otherwise."

### Stickers [C]
- **Rules stickers** (most stickers): "contain permanent new rules, to be read aloud"; **blue-coded** stickers go on the rulebook page with the matching code (codes seen: 9a/24a, 21b, 15a, 15c, 16d, 17a/17c/22c, 18a/i, 22a–c, 25a–c, k/l, g, h); **green-lettered** stickers go on the matching **player helper card**.
- **Card stickers** are few: add a second class icon to specific cards (M2: one card each of ranks 3/5/7/9 gains a basic class; M5: a chosen 6 gains Reaver; M6: a chosen 8 gains Guardian; M7: a chosen 4 gains Druid; M8: a chosen 2 gains Chanter; M9: a chosen 4 or 8 gains Mage [F]); Goran gains Warrior/Paladin/Cleric/Bard icons over M5–M8 [F] and is finally replaced by a version with all four plus "evergreen" symbol [S]; **corrupted** stickers (4 in pack C) [S]. Reviewers: since cards are sleeved, post-its/sleeve inserts substitute; TSS published a full reset/repack guide.

### Artifacts / items (persist for the rest of the campaign) [S names via repack guide; effects F]
- **Kinfolk Flute** (M1): store one card of value 2–5 per turn on the flute; stored cards may be added to combos (fan: same rank only; playable alone to avoid a loss).
- **Scarlet Whistle** (M4): play an Animal Companion or Beast together with the top card of the discard pile as a two-card combo (reviewer: "joint Animal or Beast attacks").
- **Azure Emblem** (M6; fan spells "Azume"): after a Mage reveal/pick, save one of the remaining revealed cards to the top of the reserve deck instead of discarding.
- **Evergreen Mother (Corrupted)** (M9): changes the corruption cost — fan: banish from discard instead of reserve; Hiew: "one of your partners must banish a hand card instead of the top card of the deck" [?].
- **Evergreen Mother (Restored)** (M12): restored cards are never banished; go to the bottom of the reserve instead.

### Corruption [C concept / F details]
After each of Missions 1–8 the story corrupts one party character (the reward cards describe artwork features; "Corruption Helper" page assists finding the card). A **corrupted** card **bypasses enemy immunity** for its class(es) but when played **banishes a random card** (fan: top card of the reserve deck). Mission 10 uses "the eight corrupted" party members as enemies [S — rules-card fragment + Hiew]. Mission 12 converts corrupted → **restored** (restored: ignores immunity and returns the top banished card to the bottom of the reserve when played) [S/F]. Enemy cards are themselves corrupted from Mission 4 onward [F].

### Mercenaries (pack M) [C concept; numbers S]
Designers ("A Surprising Challenge"): the game is meant to be lost first; "each time you lose you'll get to add a new mercenary to your party… if you lose 4 in a row, you'll be facing the 5th attempt with 4 additional heavy hitters"; mercs "have fat stats and some cool flexibility"; they "disappear off to their normal lives" when the mission is completed. Reviewers: each merc has a **cost in its corner**; coins: "one loss means you have one gold to spend. Second loss, two gold" (Spacebiff) and "fourth failure → four coins… next time they lose it's five coins" (BGG review) — consistent with **coins granted per loss = number of losses so far on that mission**; Hiew mentions paying "with leftover coins" (so unspent coins may carry) [?]. Cards: 4×"12" (one per basic class [F]), 4×"2/5" (choose 2 or 5 when played; fan: counts 5 when discarded), 2×"19" (no class), 2× Ace (choose class when played [F]), 2× extra Jesters.

### Beasts [S/F]
Four "Beast" cards (one per basic class) arrive in the M4 reward; from M5 choose one Beast per mission to add temporarily (fan: Beast = value 0 alone, copies partner's value in a pair). A permanent Mage-class Beast ("B Ash") arrives at M9. Mission 11 uses Beasts as mission-zone tokens.

---

## 6. The 12 missions (titles/locations/enemy cards = physical-contents guide [S]; rules = fan reconstruction [F] unless tagged)

| # | Title / Location | Enemy deck (physical) | Fan-reconstructed stats & rules | Reward pack / persistent changes |
|---|---|---|---|---|
| 1 | **Call to Arms** / (location not captured) | "Justice" 4×10, 4×15, 4×20 | = base Regicide: 10/20, 15/30, 20/40; immune to own class; exact kill → top of reserve. "99% / exactly base Regicide" [C] | 4 story cards, **"25 Arcane"** card (strength 25, no class; fan calls it "Archmage"; a search summary rendered it as "25-card Arcane deck" — treat as one card [?]), **Kinfolk Flute**, rules sticker 9a/24a; corrupt 1 character |
| 2 | **Shadow and Mist** / Umbera cavern | Hydra (stat card "Shadow and Mist") | 6 Hydras, 10 atk/20 hp, each with a distinct pair of basic classes (dual immunity); imperfect kill → bottom of enemy deck (fight again); perfect kill → banished. Arcane 25 in party for this mission | 3 story cards ("Every foe…"), rules sticker; stickers: one card each of ranks 3,5,7,9 gains one basic class (each class once, not one it has); corrupt 1; Arcane removed after [F]. Banished cards return to party at mission end [C] |
| 3 | **Lessons in Flames** / Magic Academy | Fusion 4×10, 2×15, 1×20 | 4× 10/30, 2× 15/45, 1× 20/60, all Mage-class; end of each turn (not when enemy defeated) top reserve card → mission zone; enemies immune to every class present in the zone; on defeat banish the whole zone (perfect kill: rescue 1 zone card to discard first). Permanent: recalc Paladin shield when immunity changes | 3 story cards; **Mage class cards** (fan: A–10 Mage, i.e., 10 cards) [?]; corrupt 1. Hard mission (BGG threads) |
| 4 | **Fusion of Darkness** / Biology Laboratory | Experiment 4×10, 4×15, 4×20 | standard tiers; enemy strength += value of top discard card (dynamic); enemy cards corrupted from now on; cleanup discards low-to-high (lowest on top) | **Scarlet Whistle**; deck: **4× Beast, Goran (8, no class)**; rules stickers; corrupt 1; from M5 pick one Beast per mission |
| 5 | **High and Mighty** / (not captured) | Sporeling 4×10, 4×15; party adds **Reaver 3,5,7,10** (guide) vs 3/5/7/9 (fan) [?] + **Myla** (7, no class) in reserve | 4× 10/40 + 4× 15/60; end of turn top banished → zone; enemy strength += zone total; defeat: enemy + zone shuffled into banished; **perfect kill: next enemy takes damage equal to defeated enemy's strength** [C — BGG thread]; back of rules card has a Mage rule [C] | 5 story cards; Myla joins party; keep Reaver 5 only; sticker: chosen 6 (♥/♦/♠) gains Reaver; Goran gains Warrior; corrupt 1. One group: 7 tries |
| 6 | **Shards of Memory** / Garden of Remembrance | Statue 4×15, 4×20; party adds **Guardian 3,5,7,9**; **Myla removed from party into mission zone at setup, returned to pack 6 after** [C] | 4× 15/30 + 4× 20/40; after each kill choose 1 played card → zone; then **suffer damage = zone total** (skip if Guardian active; perfect kill ignores highest card). **Second edition rewrote this mission to be easier**; official compendium says first-edition owners may use the new rules; BGG file "Mission 6 Rules Changes" [C]; tekeli.li: the 2-player version "was fixed" [S] | 6 "Shards of Memory" story cards; **Azure Emblem**; keep Guardian 3; chosen 8 gains Guardian; Goran gains Paladin; rules sticker 18a/i; corrupt 1 |
| 7 | **Tales of Rebirth** / Well of Tears | standard 12 (corrupted); party adds **Druid 3,5,7,9**; **Pilgrim deck** 25 cards (4× each of 2–7 + 1 Ace, no class) | start of turn: top pilgrim → zone; playing a card whose value matches a zone pilgrim banishes that pilgrim (one per card); **pilgrims in hand cannot be played or discarded this mission only** [C]; defeat: discard N from reserve (N = zone total), zone → discard, banish enemy; perfect: banish one zone card first | keep Druid 7; chosen 4 gains Druid; Goran gains Cleric; corrupt 1 |
| 8 | **Winds of Chaos** / Heaven's Edge | Troll/Wyvern **6×10, 6×25**; party adds **Chanter 3,5,7,9**; "Puppy Animal Pilgrim" (pilgrim Ace) placed in zone | 6 Trolls 10/20 + 6 Wyverns 25/50, each dual-class; strength += non-pilgrim zone total; after cleanup may place played cards into zone in strictly ascending sequence; placing a **10**: zone → discard, banish chosen discard cards, shuffle rest under reserve (once); perfect kill: 1 discard card → top of reserve. Pilgrims playable/discardable from M8 on [C] | 6 story cards; rules stickers 16d, g; keep Chanter 9; chosen 2 gains Chanter; Goran gains Bard; pilgrim Ace removed. BGG: very hard solo and non-solo |
| 9 | **Hope From Ashes** / Twinseed Temple | 8 enemies + **Myla boss** | 4× 15/30 + 4× 20/40 then **Myla 20/80**, immune to Bard (violin) and Paladin (shield) — immunity **cannot be removed even by corrupted cards** [S Hiew + F]; Myla's "hand": two Chanter(drum) cards + a mushroom card [S]; 30 party cards dealt into 3 captured piles of 10 (Goran, Beast, mercs held aside; pilgrims shuffled into reserve); end of turn: banish a hand card to take a pile's top card to discard, **or** rotate all piles; perfect kill: pile top → reserve top. "We reached the four veils and completed Goran's mission" (playthrough) | 4 story cards; rules stickers 15a, a; deck: **"B Ash"** (permanent Mage Beast) + **new Goran (evergreen symbol)** with axe+shield+potion+violin, ignores immunity [S]; **Evergreen Mother (Corrupted)**; chosen 4-or-8 gains Mage [F]; pilgrim deck dissolved. Hardest for a 2p group (6 tries) |
| 10 | **Pride to Fall** / Twinseed Temple Ruins | "Take the eight corrupted…" — the 8 corrupted party cards become enemies [S] | each: health 5×value, strength = value + zone total; Warrior-class enemy doubles total strength; Paladin-class reduces incoming damage by its value; Cleric-class: end of turn top discard → zone; Bard-class: end of turn you put a hand card → zone; start of turn top reserve → zone; defeat: banish zone (perfect: discard instead), enemy → discard | corrupted cards return; **Goran removed** (captured) [S/F]; story mentions "the high arcane" |
| 11 | **Descent Into Darkness** / Caverns of Decay | **Justicar 4×10, Goran 20**; Esme (6, Warrior) removed at setup | 4× 10/30 (no class) + **Evil Goran 20/90** (no class); immunity = classes of top banished + top discard cards (dynamic); strength += both top values; start of turn a random Beast → zone with effect (♣ top discard→banished; ♠ top reserve→discard; ♥ you put a hand card→discard; ♦ a hand card→banished); perfect kill skips next Beast | **Esme** returns with all four basic classes ("the new Evergreen", Restored) [S] |
| 12 | **Decay to Growth** / Throne of Corruption | **Mutates 4×15, 4×20, "High Arcana (dark)" 25** | 4× 15/30 + 4× 20/40 + High Arcana 25/120 (no class); all corrupted cards become restored; immune to every class in zone; strength += zone total; start of turn top banished → zone; defeat: banish zone (player order), enemy, and entire discard pile; corrupted cards entering the reserve are redirected under the banished pile | **Evergreen Mother (Restored)**; campaign complete → open E-box |

Permanent-rule introduction points per fan reconstruction: M3 shield recalculation; M4 enemy cards corrupted + low-to-high discard ordering; M5 Beast selection + banish ordering; M6 Azure Emblem; M9 Evergreen Mother + permanent Mage Beast; M12 Restored.

Difficulty data points [C/S]: Hiew's group 25 games for 12 missions (~2.1 attempts each, max 6); reviewers warn newcomers may need 5+ attempts per mission; one 2p group one-shot M3 and M4 but M5 took 7; M9 took a 2p family 6 tries; BGG has threads asking whether M3/M8 are beatable solo/non-solo.

---

## 7. Eternal mode ("E-box") [C concept; contents S]
Unlocked by finishing Mission 12. Official: "Once you've completed Regicide Legacy you'll have a deck unique to your game group… an 'eternal' mode that you can continue to play over and over… each time a different scenario… regular community scenarios… create your own scenarios, customising the difficulty." Reviewers: a **mission generator** — new combinations of setup + enemies + benefits with your finished party deck; variable setup each game. Physical contents: Evergreen rules, 5 Location cards (Shrine, Cave, Forest, Hills, Lake), Bane 1–23, Boon 24–35. The campaign itself is officially not replayable (hence the Reset Box), though reviewers say post-its make it resettable.

---

## 8. Designers' stated goals [C — regicidelegacy.com articles and KS]
- "A New Adventure" (2023): 12 missions in order; each mission pack has a sealed reward pack with new cards, stickers that augment existing cards, and "[redacted] which add new, permanent rules"; starting 40-card deck of "familiar faces from the Tavern".
- "A Change of Suits": original used French suits so the deck could double as a regular deck; Legacy moves to thematic class icons/colours "to help players get lost in the world and bond with the characters"; 40 named characters with race/class; players adapted to icons faster than expected.
- "A Surprising Challenge": intentionally hard; expect to lose each mission first; losing adds mercenaries so there is "usually a path forward"; balance is hard to tune.
- "Eternally Yours" (Mar 2024): eternal mode + separate reset box ("won't come in the box").
- KS Update 2: no stretch goals ("we don't like them").
- Mission 1 is deliberately base Regicide as the on-ramp; "the initial rulebook will be very familiar… new rules come in as you complete missions."

---

## 9. Relationship to other Regicide products [C]
- **Base Regicide (2020)**: Mission 1 ≈ identical; same classes with new art/icons; Legacy adds mission zone, banished pile, enemy stat cards, trackers, class decks, artifacts, corruption, mercenaries, feign death, revised Jester, campaign. Base 2nd edition introduced "Bards" art for Diamonds.
- **Regicide Inferno** (BGG 460927) and **Regicide: Crown Duels** (BGG 460930): one Kickstarter, **Mar 17 – Apr 14/15, 2026**, **2,569 backers / NZ$285,358**. Inferno: standalone 1–4p co-op with a **fifth suit, Flames** ("combo with a card from your deck… chew through your deck and banish cards"), 3 new nasty royals/mini-bosses; win condition: at least one player must win their hand to advance to the final boss. Crown Duels: competitive 2-player duel reusing corruption/equipment names. Both preorder ship est. Nov 2026; rulebooks on BGG. Dec 2025 newsletter announced three new games for 2026. Not Legacy-style; no campaign.

---

## 10. Public spoilers / resources an implementer can use
- **Optimal Play YouTube series** "Regicide Legacy Campaign Playthrough — Mission N" (M1…M11 found; several "Again"/"Still" retries; M12 not found) [C].
- **Talking Shelf Space "Repacking/Resetting Guide"** (BGG thread 3644294): mission-by-mission list of every box/booster's story cards, stickers, artifacts, enemy cards and party cards — the most complete public contents list [S].
- **DorkDad141/regicide-js** GitHub: playable reconstruction with rules for all 12 missions (cloned locally) [F].
- **BGG Files**: JediLuke "Regicide Legacy Rule Book" in page spreads (the full rulebook, 1 yr old); Japanese rulebook (nagamine); Spanish solo mission notes (peterzuel, reveals mission info); "Mission 6 Rules Changes" print files (ferakiii).
- **rulespal.com/regicide-legacy/rulebook**: third-party transcription of the core rulebook (TOC, setup, feign death, jester, solo).
- **regicidelegacy.com**: /learn-to-play (Mission 1 video), /compendium with per-mission pages (mission-1, mission-2/rewards, mission-6 (2nd-ed rules), mission-7, mission-8, c/helper "Corruption Helper"), articles (a-new-adventure, a-change-of-suits, a-surprising-challenge, eternally-yours, live), /news.
- **Hiew's Boardgame Blog / boardgamecafe.net**: spoiler-free first glance (Apr 11, 2026) and "review and photo book" (Aug 8, 2026) with card photos.
- Reviews: Dice Tower "Royal Clash" (Tom Vasel 8.5, Mike Dilisio 9.0); Shut Up & Sit Down video (very positive, "chunky love-letter to an absolute banger"); Space-Biff "It's Always the Ides of March Somewhere" (May 5, 2026; "thrilling, brilliant, and exhausting"); BGG "Once more unto the breach" (critical of stickers, no easy mode); Lankyrobot (8/10); Talking Shelf Space (mixed: stickers unnecessary, matte sleeves blur); Gus & Co (FR, Nov 26, 2025, very positive, €75); German solo playthrough (BGG video 596587); "A Review for Two" video (designer Paul Abrahams notes the helpers shown contain slight spoilers).
- **No official digital version** exists (no TTS/Tabletopia/BGA module found; base Regicide is on BGA and has the "Regicide Companion" app).

---

## 11. Engineering notes distilled from the above
- Model a card as {name, strength, classes[] (multi-class allowed), flags: companion/jester/beast/pilgrim/corrupted/restored/mercenary, special value types ("2/5", choosable-class ace, 12, 19, 25)}. Enemies: {name, strength, health, classes[] (0–2), permanentImmunity flag (Myla), mission-specific modifiers}.
- Zones: hand(s), reserve deck (orderable: top/bottom inserts, no peeking but countable), discard (inspectable, order matters — several rules place cards low-to-high), banished (face-up, inspectable, order matters: "top of banished" is used), mission zone, captured piles (M9), flute, player playmats (claimed Jesters), enemy stat card (skulls), trackers.
- Class-ability pipeline needs: immunity check per class (with bypass for corrupted/restored/Jester-attack), recalculation of accumulated Paladin shield when immunity changes (M3/M11/M12), interactive abilities (Mage pick, Druid sort, Chanter draw/discard, Reaver reveal), and ordered resolution per helper card.
- Hooks per mission: start-of-turn, end-of-turn (skipped when enemy defeated), dynamic strength bonus, dynamic immunity set, defeat handler (destination of enemy; zone action; perfect-kill branch; carry-over damage), cleanup ordering, loss handler (coins/mercenaries), post-mission mutation of the persistent party (stickers, additions/removals, artifacts, corruption).
- Campaign persistence: party deck composition, per-card class additions, corrupted/restored set, artifacts, pilgrim deck, mission progress/attempts/losses, coins, applied rules stickers (as feature flags), Eternal-mode unlock.

UNCERTAINTIES:
- ACCESS: No page was read directly; every web fact comes from search-engine summaries/quoted fragments of the pages (proxy policy blocked kickstarter.com, badgersfrommars.com, regicidelegacy.com, boardgamegeek.com, rulespal.com, spacebiff.com, talkingshelfspace.com, youtube.com). Exact rule wording for Legacy-only rules should be re-verified against the physical rulebook or the JediLuke rulebook PDF on BGG Files before shipping an engine.
- The per-mission RULES (turn hooks, defeat handlers, stats like 10/30, 15/45, 20/60, Myla 20/80, Evil Goran 20/90, High Arcana 25/120, hydra/troll dual-class pairs, captured piles, mission-zone math) come from the unofficial DorkDad141/regicide-js reconstruction. Its enemy counts/tiers match the physical-contents guide for every mission, which is strong circumstantial support, but health values, exact timing, and naming are unverified. Its mission titles ('The Hydra Assault', 'The Mage Tower', 'The Siege', 'The Troll Bridge', 'The Rescue', etc.) are NOT the printed titles; the printed titles/locations come from the Talking Shelf Space repack guide.
- Mission 1's printed location was not captured (likely a throne room/castle); 'Justice 4×10…' may be the enemy group name on the stat card or a misread.
- Mission 1 reward: the repack guide line was summarized as 'Deck: 25 Arcane' — almost certainly one card of strength 25 ('Arcane'), which the fan code calls 'Archmage'; one search rendering said '25-card Arcane deck'. The fan code also removes it after Mission 2 — unverified.
- Mission 3 reward: fan code adds ten Mage-class cards A–10; the physical guide only shows a 3-story-card booster snippet, so the real Mage card count/ranks are unverified.
- Reaver deck ranks: repack guide says 3, 5, 7, 10; fan code says 3/5/7/9 (and keeps only the 5 afterwards). Guardian/Druid/Chanter decks are 3,5,7,9 in both sources; which single card is kept after each mission is fan-sourced.
- New-class ability texts (Mage, Reaver, Guardian, Druid, Chanter) and their resolution order are from the fan code only; official helper-card wording not captured. The fan code names Chanter 'Drums'. Icon mapping drum=Chanter and mushroom=Druid is inferred from one reviewer's photo description.
- Mercenary coin rule: two reviewers' numbers (loss1→1 gold, loss2→2; loss4→4 coins, loss5→5) are consistent with 'coins per loss = number of losses so far', but the exact rule text, whether unspent coins carry over (one reviewer mentions 'leftover coins'), and each mercenary card's printed cost were not captured.
- The five extra packs are 'F, C, M, P, E' per one reviewer; M (mercenaries), E (eternal) and C (corruption stickers) are corroborated; P = pilgrims is an inference; F is unknown. A reset-box photo caption mentions boxes 'G and F'. The KS FAQ said '4 special add-on packs' vs retail '5 extra content packs'. Which 2 extra packs are in the Reset Box is unknown.
- Corruption details: official text only says the story identifies which character to corrupt via artwork; 'banish top card of the reserve when played' and 'bypasses immunity' are from a reviewer + fan code; Evergreen Mother's effect is described differently by the reviewer (partner banishes a hand card) and the fan code (banish from discard instead of reserve). Only 4 corrupted stickers are in Pack C, yet Mission 10 uses 'eight corrupted' cards — reconciliation unknown (perhaps stickers for only some corruptions, or additional stickers elsewhere).
- Hand-size/Jester table for Legacy: rulespal transcription matches the base table (1→0/8, 2→0/7, 3→1/6, 4→2/5); one search snippet claimed '2 jesters, hand 7 for two players' — treated as a garble.
- Whether solo players may yield in Legacy was not confirmed (base-game third-party summaries say solo cannot yield; the official base PDF text in hand does not state it).
- Playmat artwork: central mat = Deccaria map with zones; the four player mats' artwork is undescribed beyond 'illustrated'. Skull tokens are called 'wooden discs' by one reviewer despite the publisher listing them as skull tokens.
- Kickstarter pledge tiers, prices, add-on prices, and the titles/contents of updates other than 2, 6, and 16 could not be retrieved; the 'Last updated April 13, 2026' content is unknown. The 'No you don't' FAQ answer's question text was cut off.
- Second printing: only the Mission 6 change is documented; any other second-edition changes (sleeves, errata) are unknown. The exact Mission 6 rule differences (first vs second edition) were not captured.
- Publisher store status is contradictory today: 'Preorder, ships Nov 2026, $95' on the product page vs 'In stock and shipping now!' on another publisher page; most US retailers show out of stock.
- Eternal mode: setup procedure and how Location/Bane/Boon cards combine were not found; only the card list and the 'mission generator' description.
- No Mission 12 playthrough video was found; Optimal Play's series was confirmed through Mission 11.
- BGG stats are a ~Sept 2026 snapshot (8.6 / rank 2,498 / weight 2.44) and will drift.
- Web search budget (200/turn) was exhausted at the end; a few last checks (official new-class wording, Mission 1 enemy naming, icon key) were not run.

SOURCES:
- https://www.kickstarter.com/projects/badgersfrommars/regicide-legacy
- https://www.kickstarter.com/projects/badgersfrommars/regicide-legacy/posts
- https://www.kickstarter.com/projects/badgersfrommars/regicide-legacy/posts/4105425
- https://www.kickstarter.com/projects/badgersfrommars/regicide-legacy/posts/4157902
- https://www.kickstarter.com/projects/badgersfrommars/regicide-legacy/posts/4464966
- https://www.kickstarter.com/projects/badgersfrommars/regicide-legacy/faqs
- https://www.kickstarter.com/projects/badgersfrommars/regicide/posts/4111518
- https://www.kickstarter.com/projects/badgersfrommars/regicide-inferno-and-regicide-crown-duels
- https://badgersfrommars.com/en-us/products/regicide-legacy-preorder
- https://badgersfrommars.com/en-us/products/regicide-legacy-reset-box
- https://badgersfrommars.com/en-us/collections/regicide-legacy
- https://badgersfrommars.com/en-us/pages/announcing-new-games-for-2026
- https://badgersfrommars.com/assets/RegicideRulesA4.pdf (local copy: scratchpad/dl/rules/RegicideRulesA4_main.txt)
- https://regicidelegacy.com/
- https://regicidelegacy.com/learn-to-play
- https://regicidelegacy.com/compendium/
- https://regicidelegacy.com/compendium/mission-1/
- https://regicidelegacy.com/compendium/mission-2/rewards
- https://regicidelegacy.com/compendium/mission-6/
- https://www.regicidelegacy.com/compendium/mission-7/
- https://regicidelegacy.com/compendium/mission-8/
- https://regicidelegacy.com/compendium/c/helper
- https://regicidelegacy.com/articles/a-new-adventure
- https://regicidelegacy.com/articles/a-change-of-suits
- https://regicidelegacy.com/articles/a-surprising-challenge
- https://regicidelegacy.com/articles/eternally-yours
- https://regicidelegacy.com/articles/live
- https://www.rulespal.com/regicide-legacy/rulebook
- https://boardgamegeek.com/boardgame/412963/regicide-legacy
- https://boardgamegeek.com/boardgameversion/699723/english-edition
- https://boardgamegeek.com/thread/3646772/review-of-regicide-legacy-once-more-unto-the-breac
- https://boardgamegeek.com/thread/3661485/simple-cards-epic-fantasy-lankyrobot-reviews-regic
- https://boardgamegeek.com/thread/3600278/mission-6-update-for-second-printing
- https://boardgamegeek.com/thread/3644294/reset-guide
- https://boardgamegeek.com/thread/3585241/feign-death
- https://boardgamegeek.com/thread/3587343/mission-5-question
- https://boardgamegeek.com/thread/3589413/mission-5-questions
- https://boardgamegeek.com/thread/3735697/mission-5-mission-rules-question
- https://boardgamegeek.com/thread/3586080/spoiler-mission-8
- https://boardgamegeek.com/thread/3608174/has-anyone-beaten-mission-8-non-solo-spoilers
- https://boardgamegeek.com/thread/3590127/mission-3-struggling-getting-past-it
- https://boardgamegeek.com/thread/3575529/questions-after-5-missions
- https://boardgamegeek.com/thread/3638984/pack-c-sticker-question
- https://boardgamegeek.com/thread/3263449/replayability-in-regicide-legacy
- https://boardgamegeek.com/thread/3261604/regicide-legacy-eternally-yours
- https://boardgamegeek.com/thread/3237600/regicide-legacy-a-change-of-suits
- https://boardgamegeek.com/thread/3086347/announcing-regicide-legacy
- https://boardgamegeek.com/thread/3297738/any-gameplay-info-answered
- https://boardgamegeek.com/video/606560/regicide-legacy/shut-up-and-sit-down-review-regicide-legacy
- https://boardgamegeek.com/video/572359/regicide-legacy/regicide-legacy-a-review-for-two
- https://boardgamegeek.com/video/596587/regicide-legacy/regicide-legacy-solo-playthrough-kampagnenstart-an
- https://boardgamegeek.com/video/603963/regicide-legacy/regicide-legacy-campaign-playthrough-mission-9
- https://boardgamegeek.com/video/616167/regicide-legacy/regicide-legacy-campaign-playthrough-mission-11
- https://www.youtube.com/watch?v=6iUH7uLxkcw (Optimal Play Mission 2)
- https://www.youtube.com/watch?v=53eJtKERScw (Optimal Play Mission 4)
- https://www.youtube.com/watch?v=oM2g5tm8_MQ (Optimal Play Mission 5)
- https://www.youtube.com/watch?v=NtHRgQyEXsg (Optimal Play Mission 7)
- https://www.youtube.com/watch?v=CS-gfvcrTlQ (Dice Tower review)
- https://dicetower.com/review/regicide-legacy-review-royal-clash
- https://www.shutupandsitdown.com/videos/review-regicide-legacy/
- https://spacebiff.com/2026/05/05/regicide-legacy/
- https://talkingshelfspace.com/review-of-regicide-legacy/
- https://talkingshelfspace.com/regicide-legacy-repacking-resetting-guide/
- http://hiewandboardgames.blogspot.com/2026/04/regicide-legacy-spoiler-free-first.html
- https://boardgamecafe.net/2026/04/11/regicide-legacy-spoiler-free-first-glance/
- http://hiewandboardgames.blogspot.com/2026/08/regicide-legacy-review-and-photo-book.html
- https://boardgamecafe.net/2026/08/08/regicide-legacy-review-and-photo-book/
- https://discussion.tekeli.li/t/regicide-legacy-a-chunky-love-letter-to-an-absolute-banger/6693
- https://gusandco.net/2025/11/26/regicide-legacy-critique-jeu-cooperatif/
- https://www.tabletopgamingnews.com/regicide-legacy-continues-success-in-follow-up-campaign/
- https://www.kicktraq.com/projects/badgersfrommars/regicide-legacy/
- https://forum.cwowd.com/t/regicide-legacy-par-badgers-from-mars-livraison-mars-2025/59603
- https://unknowns.de/forum/thread/25326-regicide-legacy-2025-luke-badger-badgers-from-mars/
- https://www.miniaturemarket.com/regicide-legacy-bfmleg001.html
- https://www.miniaturemarket.com/regicide-legacy-reset-pack-bfmleg002.html
- https://www.gamenerdz.com/regicide-legacy
- https://www.gamenerdz.com/regicide-legacy-reset-box
- https://www.nobleknight.com/P/2148348759/Regicide-Legacy
- https://www.philibertnet.com/en/badgers-from-mars/151508-regicide-legacy-726436669412.html
- https://www.philibertnet.com/en/badgers-from-mars/165396-regicide-legacy-reset-box-726436669429.html
- https://gamers-hq.de/en/board-and-cardgames/adventure-games/regicide-legacy-reset-box
- https://www.cardhaus.com/regicide-legacy/
- https://geekculture.co.nz/product/regicide-legacy/
- https://www.boardgameoracle.com/en-CA/boardgame/price/UM3loyEkEx/regicide-legacy
- https://boardgamegeek.com/boardgame/460927/regicide-inferno
- https://boardgamegeek.com/boardgame/460930/regicide-crown-duels
- https://www.backseatgamer.com/news/regicide-expands-with-two-new-games-as-kickstarter-closes-tomorrow
- https://tvtropes.org/pmwiki/pmwiki.php/TabletopGame/Regicide
- https://github.com/DorkDad141/regicide-js (cloned to scratchpad/dl/gh/regicide-js)
- https://github.com/ahgamut/regi-py (pre-staged in scratchpad/dl/repos/regi-py)
- https://github.com/Kautiontape/regicide (pre-staged in scratchpad/dl/repos/regicide)
- https://en.boardgamearena.com/gamepanel?game=regicide
- https://merchantsofplay.com/howtoplay/regicide/