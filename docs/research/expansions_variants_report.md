## 0. How this was researched (read first; it bounds every confidence level below)

- **Network policy blocked every primary host.** The sandbox egress proxy answered `403` to CONNECT for badgersfrommars.com, regicidegame.com, regicidelegacy.com, boardgamegeek.com, api.geekdo.com, kickstarter.com, boardgamearena.com, youtube.com, reddit.com, itch.io, apps.apple.com, play.google.com, tabletopia.com, store.steampowered.com, wikipedia.org, web.archive.org, codeberg.org (verified with `curl -sS "$HTTPS_PROXY/__agentproxy/status"`; the proxy README says these are org policy denials not to be routed around). `WebFetch` fails with `ENOTFOUND` on the same hosts. The shared per-turn `WebSearch` budget (200 calls) was already exhausted by sibling agents before my first search, so **no new web searches were possible**.
- **What worked:** api.github.com, raw.githubusercontent.com, GitHub code/repo/user search via the GitHub MCP tools, and the ~150 Regicide repositories plus notes that sibling agents had already cloned into the scratchpad (`/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/{repos,dl,dl2,notes,research}`).
- Consequently this report is built from: (a) the official rulebook text (two independent transcriptions of `RegicideRulesA4.pdf` on GitHub that agree word-for-word), (b) a mirror of Board Game Arena's official help page, (c) BGG XML/JSON records mirrored on GitHub, (d) publisher-page text quoted in GitHub repos, (e) fan-project source code, and (f) the sibling agents' earlier reports (which did have WebSearch snippets). Items that only sibling snippets support are tagged **[snippet]**; items I verified from a mirrored primary text are tagged **[verified-mirror]**; my own inferences are tagged **[inference]**.
- **Local files I created for the engineer** (absolute paths):
  - `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl3/bggxml/307002.xml` — BGG XML record for Regicide (links to Inferno/Crown Duels/Regidice/Legacy, families, publishers).
  - `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl3/raw/regidice_page.json` — mirrored BGG record for Regidice (id 350604).
  - `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl3/raw/regiside_rules.md`, `ayrat_readme.md`, `vendors_dump.json` (GenCon exhibitor dump).
  - Already present from siblings: official rulebook text `scratchpad/dl/rules/RegicideRulesA4_main.txt` and `drpaj12_rules_in_text.txt`; BGA help mirror `scratchpad/dl2/bga-help-zh-main/file`; fan option code `scratchpad/repos/Poukame__regicide-plus/src/Components/SelectOptions.tsx`; fan variant notes `scratchpad/notes/lyz_regicide.md`; `scratchpad/repos/Octacles7__Regicide/README.md`.

---

## 1. The official Regicide product family (what exists)

From the BGG XML record for Regicide (id 307002) [verified-mirror, MrHinsh/board-games `data/raw/bgg/details/307002.xml`]:

| BGG link type | Item | BGG id |
|---|---|---|
| boardgamecompilation | **Regicide Inferno** | 460927 |
| boardgameimplementation | **Regicide Legacy** | 412963 |
| boardgameimplementation | **Regicide: Crown Duels** | 460930 |
| boardgameimplementation | **Regidice** | 350604 |
| boardgamefamily | **Series: Regicide** | 116972 |
| boardgamefamily | Digital Implementations: Board Game Arena / Google Play / Tabletopia | 70360 / 78432 / 70948 |
| boardgamefamily | Contests: 54-Card Game Design; Crowdfunding: Kickstarter; Misc: LongPack Games; Series: Pocket Games (Devir); Theme: Anthropomorphic Animals; Components: Traditional Playing Cards | — |
| designers | Paul Abrahams (126153), Luke Badger (126151), Andy Richdale (126152) | — |
| artist | Sketchgoblin (130909) | — |
| publishers | Badgers from Mars (45406), BoardM Factory (25074, Korea), Devir (2366, ES/LatAm), Gameplay Publishing ApS (50675, DK), Hobby Japan (1391), IELLO (8923, FR) | — |

Base record: year 2020, 1–4 players, 30 min, age 10+, mechanics "Card Play Conflict Resolution, Communication Limits, Cooperative Game, Hand Management, Solo / Solitaire Game, Sudden Death Ending, Variable Set-up"; alternate names レジサイド / 레지사이드. Official BGG description ends: "For a dice-based, typo-inspired, April 1st-announced game from the same designers, try Regidice!"

**Note:** BGG classes Inferno as a *compilation* (an item that contains Regicide) and Crown Duels as an *implementation* (a reimplementation of Regicide's system). The sibling WebSearch snippets instead describe Inferno as a standalone game; both can be true (a standalone box that includes base-Regicide play). Unresolved.

### 1a. Regicide Inferno (BGG 460927) — everything known
- **No rules text, card list, or rulebook was reachable** from this sandbox (BGG Files and Kickstarter are blocked; no GitHub repo transcribes or implements it — GitHub code search for "Regicide Inferno", "Crown Duels", and `Regicide Inferno Flames suit` returns only the BGG XML link above).
- [snippet, from sibling legacy report §9]: one Kickstarter, **"Regicide Inferno and Regicide: Crown Duels"** by Badgers from Mars, English-only, ran **Mar 17 – Apr 14/15, 2026**, **2,569 backers / NZ$285,358**. Inferno is described as a **standalone 1–4 player co-op** with a **fifth suit, "Flames"** (quoted fragment: "combo with a card from your deck… chew through your deck and banish cards"), **3 new "nasty" royals / mini-bosses**, and a win condition fragment: "at least one player must win their hand to advance to the final boss". Preorder on the publisher store: ships est. **November 2026**. "Rulebooks on BGG" (files exist on the BGG pages but were unreadable). Regicide Legacy was offered as an add-on in that campaign. The December 2025 publisher newsletter ("Announcing new games for 2026", URL `badgersfrommars.com/en-us/pages/announcing-new-games-for-2026`) announced three new games for 2026.
- [verified-mirror, local store page quote] a publisher page quoted by the sibling says "Regicide Inferno preorder also lists Nov 2026".
- **Implementation status:** not implementable from available data. What an engine would plausibly need, by inference from the fragments: a 5th suit with its own power (Flames: deck-thinning/banishing — i.e., a "banished" zone like Legacy), at least 3 extra enemy cards with special rules, and possibly a per-player "hand win" sub-goal before a final boss. Treat all of that as **[inference]** until the rulebook is read.
- Related fan item: BGG thread 3681898 "regicide inferno variant" [snippet]: a fan variant — shuffle **only ONE Jester** into the Tavern for 2–4 players, normal hand limits. Unclear whether it predates or riffs on the official Inferno.

### 1b. Regicide: Crown Duels (BGG 460930) — everything known
- [snippet, sibling]: **competitive 2-player duel** sold alongside Inferno in the 2026 campaign; reuses "corruption/equipment" naming from Legacy; ships est. Nov 2026. No rules obtained. GitHub has zero content about it (the only "Crown Duels" hits are an unrelated music act, an Economist headline and a Steam game).
- This is the **only official 2-player-specific product**; base Regicide has no 2-player-specific rules beyond the setup table (see §4).

### 1c. Regidice (BGG 350604) — official April-Fools spin-off [verified-mirror]
From the mirrored BGG record (`jordyn-liegl/Capstone boardum/data/page_274.json`): "Regidice was born when Luke Badger accidentally typed Regidice instead of Regicide. 24 hours later, Paul had given birth to the dice-based beast you see before you. Regidice was announced April 1st, 2021... Yes, April 1st... Regidice is a cooperative game where 2 to 4 players work together to defeat three powerful enemies. Players take turns to roll dice, pick actions and attack the three enemies, represented by black dice. Once enough damage is dealt, the enemy is defeated. The players win when the last enemy is defeated. But beware! Each turn the enemy strikes back. Players will discard dice to satisfy the damage and if they can't discard enough, everyone loses. — description from the designer. For a more refined "Regi"-based experience, try out Regicide from Badgers From Mars!" Data: 2–4 players, 30 min, age 10, categories Dice/Fantasy, mechanics Action Drafting, Communication Limits, Cooperative Game, Dice Rolling, Variable Phase Order, Variable Set-up. No rules sheet obtained. (Whether it was ever physically sold is unknown; it reads as a joke release/PnP.)

### 1d. Regicide Legacy — covered by the sibling dossier at `/home/user/PersonalRegicide/docs/research/legacy_report.md`; not repeated here except where it supplies official base-game variants (§3).

### 1e. Promo cards
- **Nothing found.** No GitHub-mirrored source (BGG XML, store quotes, fan READMEs, rules transcriptions, news-feed datasets) mentions any promo card, promo pack, Kickstarter-exclusive card or foil for base Regicide; the Legacy KS FAQ explicitly says there are **no Kickstarter exclusives** and the retail version is identical [snippet]. The BGG family "Series: Regicide" (116972) would list any promo items but is unreachable. Treat "no promos exist" as **unverified-likely**.
- Edition variants that do exist (not promos): first-edition **teal** and **red** cardboard tuck boxes (same cards, different back/box colour), and the **2nd Edition** (plastic flip-top box). See §8 for the 2nd-edition text.

---

## 2. Official "Learn to Play" page and video

- **Official video:** YouTube id **`7XoRlKzLobk`** ("Regicide Learn to Play"). Confirmed by four independent GitHub sources that embed/cite it as the official how-to-play: ch1nq/regicide README (`img.youtube.com/vi/7XoRlKzLobk` captioned "Regicide Learn to Play"), melvinzhang/garden ("Learn to play"), agung96tm/board-game-indonesia ("Youtube - Regicide: How to Play"), and a wikiHow clipping citing `https://youtu.be/7XoRlKzLobk?t=18`. The channel owner could not be verified (YouTube blocked), but every citer treats it as the publisher's.
- **Official pages (URL history):**
  - Original site: `https://www.regicidegame.com/` ("Regicide | Badgers From Mars"; by May 2025 it resolved to the title "Regicide Legacy" — i.e., redirected to the new site), `https://www.regicidegame.com/the-app/` (companion app page), `https://www.regicidegame.com/the-game_copy/` (archived game page that "still displays the original teal and red cardboard tuck boxes" per the who-goes-first provenance note).
  - 2020–2022 site: `https://www.badgersfrommars.com/regicide` (learn-to-play page: hosts the video and the rules PDF; cited by Lyz 2021: "they explain them in this video" linking that URL), `https://www.badgersfrommars.com/buy-regicide` (shop).
  - Current Shopify-era site: `https://badgersfrommars.com/en-eu/pages/learn-to-play-regicide` (cited by ayrat555/regicide README, 2026), store `https://badgersfrommars.com/en-us/products/regicide-2nd-edition`, `.../en-us/collections/regicide`, Legacy preorder `.../en-us/products/regicide-legacy-preorder`.
  - Rules PDF: `https://badgersfrommars.com/assets/RegicideRulesA4.pdf` (a `?v=2` query was seen in Nov 2021) and the original `https://www.regicidegame.com/site_files/33132/upload_files/RegicideRulesA4.pdf` (SHA-256 `46a7fb460b38f29e7644094267bf5bf097552258be5fdc43f35c25c123ba54be`, checked 2026-09-24 by ariel-hi/who-goes-first). The rulebook's back page reads verbatim: `LEARN TO PLAY!` / `DOWNLOAD THE FREE 'REGICIDE COMPANION' APP!`
  - Regicide Legacy: `https://regicidelegacy.com/learn-to-play` (Mission 1 video) and `https://regicidelegacy.com/compendium/` (per-mission pages, QR-coded from the mission packs) [snippet].
- Official companion app: iOS `https://apps.apple.com/us/app/regicide-companion/id1565706782`, Android `https://play.google.com/store/apps/details?id=com.bfm.regicidecompanion` (Unity; free tracker + paid "Regicide Solo Play" unlock) — details in the sibling companion report.

---

## 3. Official variants and official difficulty levels (exact status)

### 3a. What the official rulebook contains [verified-mirror]
- **No difficulty levels, no optional rules, no variants** in the base rulebook (April 2020 original; Oct 19 2021 revision added "clarifications and solo rules", "no substantive changes" per the BGG file page [snippet]). The only tiering is the **solo medal**: "A win having used 2 Jesters = Bronze Victory / A win having used 1 Jester = Silver Victory / A win having used 0 Jesters = Gold Victory".
- Jester count is fixed by player count (1→0 [set aside], 2→0, 3→1, 4→2); hand size 8/7/6/5. There is no official "fewer Jesters = hard" mode.

### 3b. "Royal Decree" and "Scorched Earth"
- **No trace anywhere.** GitHub code search for `regicide "Royal Decree"` (112 hits) and `regicide "Scorched Earth"` (183 hits) returns only Magic: The Gathering card lists, an Encyclopaedia Britannica entry, a chess roguelike, etc. — nothing connected to Badgers From Mars. Neither sibling report (190+ web searches) saw these names either. **Treat them as non-existent / mis-remembered** unless the user has a source. Do not implement under those names.

### 3c. Variants Badgers From Mars has actually endorsed for base Regicide [snippet, Kickstarter Legacy FAQ, via sibling]
The Regicide Legacy Kickstarter FAQ offers two Legacy rules "you're welcome to incorporate into your existing games of Regicide":
1. **Jester change:** "The player of the Jester no longer decides who plays next. The players simply wait for someone to play next." (The later Legacy rulebook p.20 instead says any player — including the Jester's player — may *claim* the Jester, take over the turn and attack; immunity is ignored only for that attack. The two official Legacy sources conflict; implement the FAQ wording as the base-game house rule and the rulebook wording as the Legacy rule.)
2. **Feign Death:** a player may discard a **full hand** of cards (e.g., 6 cards in a 3-player game) to satisfy the strike even if their values don't add up. Legacy rulebook adds: "You must be at your hand limit to feign death." (BGG thread 3585241 notes you normally need a draw power to be at the limit during Step 4.)
Also from Legacy, usable as an optional base rule: **starting player = whoever plays the first card** (vs the base joke "most recently committed regicide").

### 3d. Board Game Arena (licensed digital version) — official-ish difficulty options
- BGA's official help page (mirror of `https://en.doc.boardgamearena.com/Gamehelpregicide`, local copy `scratchpad/dl2/bga-help-zh-main/file`) [verified-mirror] contains these rulings not in the PDF: "Hand Size is 8-5 for 1-4 players respectively"; "A royal's suit blocks the use of that power against it"; Jesters "prevent the Royal from attacking the player" and "the next player to take a turn is chosen by the active player, rather than clockwise"; "Jesters have a value of 0 for the purposes of taking damage"; "Royals as allies - Royals retain their attack value when players play them (J10, Q15, K20) and that is also the amount of damage they can take"; "**A player may not Yield in solo**, or if every other player has Yielded on their last turn"; "Cards are only discarded once a Royal is defeated, this is mainly because any Spades played previously or by other players will stack. No other powers stack"; Lose: "A player is unable to defend an attack from a Royal or unable to play a card when the player cannot yield (because all the other players have yielded or in solo mode)"; the Jester communication exception is implemented as two buttons "I'd like to go next" / "I'd rather not go next"; the Solo paragraph is the rulebook's verbatim with "the ever-elusive Gold Victory".
- BGA table options (from DOM ids used by teapowell/BGA_Scraper, 2025-02) [verified-mirror of the scraper]: `gameoption_100` = **Modifications Enabled/Disabled**; `gameoption_101` = **hand size modifier**; `gameoption_103` = **enemy health modifier**; `gameoption_104` = **enemy attack modifier**; `gameoption_102` not read (unknown; plausibly Jesters). With modifications disabled the scraper records hand_size 0, health_modifier 0, attack_modifier 0, **difficulty 1**. BGA shows a computed **"modifier score"/difficulty** (Reddit 2025-02-19 asks for the hardest achieved) [snippet]. BGG thread 3286672 [snippet]: BGA "variants" relax the Ace/combo exceptions; a poster saw the official Android app allow more combos than printed; reply: "the printed rules are correct unless rule modifiers are in use" → **the official Companion app also has "rule modifiers"** (exact list unobtainable).
- **Fan reconstruction of the option set (exact values, verified from source `Poukame/regicide-plus src/Components/SelectOptions.tsx`; the author says he copied BGA's options because the official app lacked them):**
  - Max hand size: `0 (Default), +1, +2, -1, -2`
  - Remove Jesters: `Default, -1, -2`
  - Enemy health boost (every enemy): `0, +5, +10, -5, -10` (→ Jack 25/Queen 35/King 45 at +5)
  - Enemy attack boost: `0, +2, +5, -5, -2`
  - Yield: `On (Default), Off`
  - Max combo limit (sum cap): `10 (Default), 9, 8, 6, 4, No Combo, 18, 15, 12`
  - Max animal-companion partner: `K (Default = any), Q, J, 10, 9, 8, 7, 6, 5, 4, 3, 2, A, No Animal Companion`
  - Treat the mapping to BGA's real options as the fan author's claim (unverified); the +5/+10 health and +2/+5 attack steps are consistent with the scraper's "health_modifier/attack_modifier" integers.
- BGA player count is 1–4 (solo playable) [verified-mirror of brownbat/bga-ranked].

### 3e. Legacy difficulty [snippet]
No easy mode (a BGG review complains); the design intent is "lose first, then mercenaries"; the 2nd printing rewrote Mission 6 to be easier. See the legacy dossier.

---

## 4. Official solo and two-player rules (implementation-exact)

**Solo (rulebook verbatim) [verified-mirror]:** "Set up the game as per usual but place the two Jesters to the side. You play with a single hand limited to 8 cards. Play as normal, playing each turn one after the other. A Jester can be flipped to activate the following power: 'Discard your hand and refill to 8 cards - this does not count as drawing for the purpose of enemy diamond immunity.' Since you have two Jesters this can be done twice per game. Flipping the Jesters in this way does not cancel enemy immunity. You are allowed to use the Jester power a) at the start of Step 1 before you play a card or b) at the start of Step 4 before you have to take damage. A win having used 2 Jesters = Bronze Victory; A win having used 1 Jester = Silver Victory; A win having used 0 Jesters = Gold Victory."
- Derived: solo Tavern = 40 cards (2–10 ×4 + 4 Aces, no Jesters); 8 dealt → 32 remain; two flip tokens; BGA ruling: **no yielding in solo**; loss if no legal play (empty hand with non-zero effective attack, or cannot cover damage). Gap: refill when the Tavern holds <8 cards is unaddressed (draw what is available is the consensus).
- Solo-rules coverage from a 2026 review (sdjmchattie) matches: "exactly two lifelines across the whole game… discard your entire hand and draw eight fresh cards… then continue from that same point in the turn"; suggests using the two physical Jokers as tokens.

**Two players [verified-mirror]:** no special rules. Setup row: 0 Jesters, 7-card hands. Consequences: no Jester ever appears; the yield rule degenerates to "you may not yield if the other player yielded on their last turn" (so never two consecutive yields); Diamonds alternate draws between the two hands starting with the current player. Official competitive 2p is **Crown Duels** (§1b). Fan competitive variant: BGG thread 2909781 "Regicide Duel" [snippet] — no Jesters, 7 cards each, first Jack not flipped (details unread).

**Three/four players:** 1 / 2 Jesters, 6 / 5 cards; Jester = value 0, played alone, cancels immunity, skip Steps 3–4, Jester's player picks who goes next (rulebook) — Legacy/FAQ variants in §3c.

---

## 5. Community house rules / variants (precise enough to implement)

BGG itself was unreadable; thread IDs and one-line contents come from sibling search snippets [snippet]; the GitHub-sourced variants below were read in full [verified-mirror].

### 5a. BGG threads (titles/IDs; contents only as far as snippets showed)
- 3681898 "Regicide Inferno variant" — only one Jester in the Tavern for 2–4 players, normal hand limits.
- 2718237 "Is Regicide too easy?" — cut hand size to 3 (extreme hard mode suggestion).
- 2814892 "Alternate Regicide rules. Do they exist?" — unread.
- 2909781 "Regicide Duel – competitive Regicide for two players" — no Jesters, 7 cards each, first Jack not flipped.
- 2875995 "The 10 commandments of Regicide solo" — strategy, not rules.
- 2734400 "Custom Regicide room (playingcards.io)" — community online room (fan, not publisher).
- 3286672 "Regicide rules" — app/BGA allow extra combos only with modifiers on.
- 3585241 "Feign death" (Legacy) — hand-limit timing discussion.
- Reddit r/boardgames 2025-10-25 "win/loss ratio… never made it past the first queen"; 2025-02-19 BGA modifier-score thread; 2026-04-15 "Regicide can be actually played in every franchise/theme" (re-skinning with any deck).

### 5b. Variants documented in full on GitHub (fan, not endorsed)
1. **"Situation modifiers" + "Player modifiers"** — lyz-code blue-book `regicide.md` (2021, explicitly "untested ideas"). Enemy level L: J=1, Q=2, K=3. When a new enemy appears, roll a die for a situation: *Disloyal* (your cards matching the enemy's suit join the enemy next round as minions that must be killed first and also deal damage); *Cornered* (start of each player turn take 2×L damage); *Exterminator* (1×L of the cards you discard to damage are removed from the game); *Enemy ambush* (2×L damage to players when it appears); *Enemy Spy* (discard 1×L cards of its suit when it appears); *Necromancer* (the smallest discarded card becomes a minion); *Represor* (removes 1×L Tavern cards per player turn); *Dexterous* (20%×L chance to dodge an attack); *Quick* (enemy hits in phase 1 instead of phase 4); *Stronger* (+2×L attack); *Tougher* (+3×L health); *Blind* (also attacks any player who makes noise); *Random* (attacks a random player); *Uneventful*; and favourable ones: *Softer* (−3×L health), *Weaker* (−2×L attack), *Clumsy* (20%×L chance to miss), *Resistance Spies* (no suit immunity), *Ambush* (players deal 2×L on arrival), *Anarchist enemy* (+1×L to all your cards, +2×L to its suit), *Enemy Cornered* (takes 2×L at the start of each player turn), *Loyal* (your matching-suit cards are not discarded when the enemy dies). Player modifiers: each player picks a suit; bonus +1/+2/+3 vs J/Q/K on their suit and the same penalty on the opposite suit (♠↔♥, ♣↔♦); e.g., 8♦ vs J♥ by a ♦ player draws and deals 9.
2. **Hard mode + gold economy** — Octacles7/Regicide (Godot): hard-mode ideas: hand permanently locked to 7; +5 health to all bosses; spade efficiency halved; Joker final bosses; Aces as bosses; "mashup" bosses made of poker hands. Gold: 10 per damage, 10 per attack reduced, 50 for a critical, 100 for reducing attack to 0, 1.5× for an Ace combo, N× for an N-card combo, up to 50 time bonus, 5 per Hearts-refreshed card, 5 per Diamonds-drawn card; spend: 100 draw a card (not over limit), 500 mulligan a Diamond-less hand, 250/1000/2500/5000 for permanent +1 hand size (max 12), 500 next Diamond draw may exceed limit, 500 next Diamond draws from discard, 500 move all face cards to the top of the Tavern, 750 next combo may exceed the cap, 1000 Aces count as 14, 2000 nullify boss suit immunity, 2500 bank 1.25× after a boss, 10000 "finisher" (empty hand, all suits resolve), 1000 refresh the whole discard.
3. **Mulligan if no Diamonds in the opening hand** — mentioned by RegiSide docs as "one source… not in the primary rules"; Octacles7 sells it for 500 gold.
4. **Reshuffle the discard when the Tavern runs out** — Topping-the-Table guide house rule (official text: no reshuffle, no penalty).
5. **Daily seeded challenge with shareable result** — Kautiontape "Paper Crowns" (solo; same deal for everyone).
6. **Progress score for losses** — regicide-plus: damage dealt ÷ total enemy health (note: total health at default values is 4×20+4×30+4×40 = **360**; the sibling report quoted 480 — treat 480 as that app's own constant, unverified).
7. **Online rooms with reconnect/timers** — KillTheFaceCards (Firebase room codes), pixelcide (socket.io); **1789** (jonathonthill) retheme adds a once-per-tier shared "Rally/Raid/Rise/Barricade" power by majority vote.
8. The "Super-Set-Deck" project (Impactful-Games) re-expresses the official rules sentence-for-sentence for a generic deck (useful as a second transcription; not a variant).

---

## 6. Badgers From Mars' public stance on fan projects and digital clones

**No explicit public statement, licence, or takedown was found anywhere reachable.** Evidence assembled:
- **Free rules:** the full rulebook has been a free public PDF since 2020 (`.../assets/RegicideRulesA4.pdf`), and the publisher's own marketing says the game is **"Playable with any deck"** (sdjmchattie review quoting the product pitch: "Enjoy a rich cooperative game using either the official illustrated edition or any standard pack of cards"). The game design is therefore deliberately playable without buying anything; the sellable parts are the art, the box, the companion app's solo mode, and the later products.
- **Licensed digital versions exist:** Board Game Arena (1–4p, with difficulty modifiers) and the publisher's own Regicide Companion app (Unity, iOS/Android/Windows). BGG also lists a Tabletopia implementation (official or fan unknown). No Steam/TTS evidence.
- **Fan ecosystem tolerated for 6 years:** ~150 public GitHub Regicide implementations (2019-07 → 2026-10; e.g., ch1nq/regicide 10★, pixelcide, regicide-plus, Paper Crowns, KillTheFaceCards, DorkDad141/regicide-js — a full Legacy campaign reconstruction public since 2026-04-04), live fan web apps (regicide-plus.netlify.app, regicide.kautiontape.com / itch "Paper Crowns", ggottli.github.io/games/regicide), a Pokitto handheld port (2021), a playingcards.io room thread on BGG (2734400), a Discord bot (heart2heart). I found **no DMCA, cease-and-desist, or takedown mention** in any README, issue, or mirrored forum post (code searches for `regicide badgers permission`, `trademark`, `takedown`, `cease` → nothing relevant).
- **Fan-community norms (what the clones do, which is the de-facto safe practice):** (1) state "unofficial / not affiliated with or endorsed by Badgers From Mars"; (2) link to the official store and tell people to buy it (Kautiontape NOTICE: "Regicide is a great game and the physical copy is better than this. Buy one"); (3) use **no official art or text** — every fan repo I inspected that bundles royal images uses generic public-domain decks (the "PNG-cards-1.3" set, or a weathered standard King of Hearts texture in varzival/RegicideGodot, which I viewed), and regicide-plus uses its own SVG cards + the "Vecna" fantasy font; (4) several **avoid "Regicide" as the product title** ("Paper Crowns", "Kill The Face Cards", "Not-Regicide", "KingSlayer", "replicide", "RegiSide", "Regicide Companion Plus"). Kautiontape's reasoning (docs/itch.md): "Badgers from Mars sell Regicide and ship their own Regicide Companion app, so a listing called Regicide competes with them under their own name" — keep the name in a sentence that credits them, never in the title/URL/tags. (5) One vibe-coded repo (mahocitrus) claims "Regicide is a trademark of Bad Prod" — that is wrong/hallucinated; ignore.
- **Legal reality [inference]:** the rulebook text and Sketchgoblin's illustrations are copyrighted; game mechanics are not; the name "Regicide" is used as a brand by BfM (registered-trademark status unknown). For a *personal* Pythonista app that shares no art/text, isn't distributed under the name, and credits the publisher, there is no sign of any risk, and the publisher's conduct to date is permissive. Do not redistribute the PDF, the app's art, or Legacy card text/story.

---

## 7. The company and the people

- **Badgers From Mars** — indie tabletop publisher in **New Zealand** (BGG/steinea "location: New Zealand"; sibling: Auckland). BGG publisher id 45406. App-store developer name "Badgers From Mars Limited" [snippet]. GenCon exhibitor record: "Badgers From Mars, Exhibitor #2957" (gencon_id 14862; year not stored in the dump, repo circa 2025) [verified-mirror]. Kickstarter profile `https://www.kickstarter.com/profile/badgersfrommars/created`.
- **Products/campaigns:** Regicide (Kickstarter funded May 2020; 2nd Edition later; localized by BoardM Factory, Devir, Gameplay Publishing, Hobby Japan, IELLO; manufactured by LongPack per BGG family), Regidice (April 1 2021 joke), Regicide Companion app (2021; solo mode IAP added late 2021 [snippet]), Regicide Legacy (KS May 8–Jun 7 2024, **3,082 backers, NZ$506,235**, no stretch goals by policy, retail Aug 2025, reprint 2026) [snippet], Regicide Inferno + Crown Duels (KS Mar–Apr 2026, 2,569 backers, NZ$285,358) [snippet]. Three new games announced for 2026 [snippet].
- **People:** designers **Paul Abrahams** (BGG 126153), **Luke Badger** (126151), **Andy Richdale** (126152) — credited on every product; artist **Sketchgoblin** (130909). Signals about roles: the Regidice blurb ("Luke Badger accidentally typed Regidice… 24 hours later, Paul had given birth to the dice-based beast") and Kautiontape's credit "designed by Paul Abrahams" suggest Paul is the lead designer/prototyper [inference]; the Legacy KS announcement was signed "Paul, Luke, Andy, and DJ" [snippet] → a fourth team member "DJ". Designer Paul Abrahams appears in a "Regicide Legacy: A Review for Two" video noting the helper cards contain slight spoilers [snippet]. **Company size:** no headcount published; all evidence points to a micro-publisher of 3–4 people plus a contract illustrator [inference]. No GitHub organisation or designer accounts exist (user searches for "badgersfrommars", "Luke Badger", "Andy Richdale" return nothing relevant; "Paul Abrahams" → an unrelated account). Luke Badger is also listed among playtesters of an unrelated game ("Dark Providence" manual, original version credits) — same-name coincidence not excluded.
- Sibling detail (not re-verified): BGG stats mid-2025 for Regicide: ~9,466 ratings, avg 7.39, rank ~542, weight 1.97, 16.7k owners; Legacy avg ~8.6, Golden Geek 2025 nominee.

---

## 8. Official art / style facts (no style guide exists; use these to be "similar, not copied")

- **No published style guide, palette, or brand kit** was found on any mirrored source; nothing on GitHub quotes one.
- **Illustration:** all art by **Sketchgoblin**; "dark fantasy" painted illustrations; BGG family **"Theme: Anthropomorphic Animals"** — the adventurers/royals are animal characters (the 2nd-edition animal companions were reported as pangolin ♠, fennec fox ♥, badger ♣, dove/duck ♦ [snippet, unverified]). The rulebook's flavour text sets the tone: "A sinister corruption has spread throughout the four great kingdoms, blackening the hearts of once-loved Kings and Queens and those that protect them… Overthrow the corrupted monarchs, purge them of their darkness and add them to your ranks so that life can be brought to the land once more."
- **Box/back colours:** first edition = cardboard **tuck box in TEAL** (the standard) and a **RED** variant; both shipped with **teal card backs** (2nd-edition blurb: "No more teal card backs with your red deck box"). The rulebook cover shows "the armored figure and palette" matching the teal box [who-goes-first provenance]. RegiSide's rules doc: "There are Red and Teal versions, differing only in card back color."
- **2nd Edition product text (publisher, verbatim via steinea mirror):** "This new edition of Regicide comes in a hardy, plastic, flip-top box to keep your cards safe and secure! Also featuring the Bards as the new art for the Diamonds suit. All illustrations have been touched up and improved with extra detail. Card backs now match the deck box colour! No more teal card backs with your red deck box. And lastly, card backs now feature a bold border. This will help players easily identify the number of cards in other players' hands at a glance. Regicide is a cooperative, fantasy card game for 1 to 4 players, with a deck of playing cards uniquely illustrated by Sketchgoblin. Recruit heroes, storm the castle and defeat the corrupted Monarchy! In Regicide players must work together and use the unique powers of each suit to achieve victory." → design cue: card backs with a **bold border** so hand counts are readable; a replica should likewise give card backs a high-contrast border.
- **Suit semantics as a colour system:** the rulebook ties timing to suit colour ("powers from red suits are resolved straight away, powers from black suits take effect in later steps") — a UI can legitimately colour-code Hearts/Diamonds (immediate) vs Clubs/Spades (deferred). Legacy replaced French suits with **class icons and per-class colours**: axe = Warrior (♣ double), shield = Paladin (♠ shield), potion = Cleric (♥ heal), violin = Bard (♦ draw) [snippet]; 2nd-edition base game calls the Diamonds characters "Bards".
- **Companion app look** [snippet/fan reconstruction]: enemy card centred, big red Health and Attack counters, suit buttons, Jester toggle (card greys with a yellow outline), "PERFECT KILL!" notice, victory screen.
- **Typography:** unknown. (The fan app's "Vecna" font is its own choice.)
- **Practical non-infringing palette advice [inference]:** a teal primary with parchment neutrals and a red accent evokes the first edition without copying anything protectable; use Unicode suit glyphs or original icons; never reuse the logo, the box art, or Sketchgoblin's character art; name the app something other than "Regicide" if it is ever published; keep names of mechanics (Tavern, Castle, Jester, Animal Companion, Yield, Gold/Silver/Bronze) — these are unprotectable rule terms and every fan clone uses them.

---

## 9. What the engineer can safely build now vs. what needs the user

- **Build now (fully specified):** base game (sibling spec `docs/RULES_BASE.md`), solo medals, BGA rulings (no solo yield), **BGA-style modifiers** (hand ±1/±2, Jesters −1/−2, enemy health ±5/±10, enemy attack ±2/±5, yield off, combo cap 4/6/8/9/10/12/15/18/none, companion-partner cap A…K/none) honestly labelled "unofficial / BGA-style", the two **BfM-endorsed house rules** (FAQ Jester rule; Feign Death with hand-limit condition), the fan "one Jester" and "hand size −N" hardness knobs, a daily seeded solo challenge, loss-progress score (÷360).
- **Needs the user (gate):** Inferno rulebook (fifth suit "Flames", 3 new royals, hand-win condition), Crown Duels rulebook, Regidice sheet, BGG "Series: Regicide" promo list, and the Companion app's actual modifier list (open the app → settings and photograph). The user can also lift the sandbox block by allow-listing badgersfrommars.com, boardgamegeek.com, kickstarter.com, regicidelegacy.com and boardgamearena.com in the cloud environment's Network access settings so a follow-up run can read primary pages.

UNCERTAINTIES:
- ACCESS: every publisher/BGG/Kickstarter/BGA/YouTube/app-store page was blocked by the sandbox egress policy (CONNECT 403) and the WebSearch budget was already exhausted; all Inferno, Crown Duels, Legacy-FAQ and BGG-thread facts come from sibling agents' search snippets, not from reading the pages. A follow-up run with those hosts allow-listed (or a fresh search budget) should re-verify them.
- Regicide Inferno: no rules text, card list, player-count confirmation, price, or rulebook was obtained. The 'fifth suit Flames', '3 new royals/mini-bosses', 'at least one player must win their hand to advance to the final boss', Kickstarter dates (Mar 17–Apr 14/15 2026) and totals (2,569 backers / NZ$285,358) are snippet-level. BGG classes Inferno as a 'compilation' while snippets call it standalone — unreconciled.
- Regicide: Crown Duels: only known as an official competitive 2-player product in the same 2026 campaign; no rules at all.
- Regidice: only the BGG description is known; whether it was physically produced or is a free PnP is unknown.
- Promo cards: no evidence of any promo/KS-exclusive card was found, but the BGG 'Series: Regicide' family page (which would list promos) could not be read, so absence is unproven.
- 'Royal Decree' and 'Scorched Earth': no Regicide-related source anywhere mentions these; they are most likely not real Badgers From Mars variants. Flag to the user before implementing anything under those names.
- Official Companion app 'rule modifiers': their existence is inferred from a BGG thread snippet ('printed rules are correct unless rule modifiers are in use'); the actual list could not be read. The exact BGA option values are inferred from scraper DOM ids plus a fan app that claims to copy BGA; gameoption_102 is unknown.
- The Legacy Kickstarter FAQ's house rules (Jester: 'players simply wait for someone to play next'; Feign Death) conflict with the Legacy rulebook's Jester-claim rule; both are snippet-sourced and the FAQ page itself was not read.
- The Learn-to-Play video id 7XoRlKzLobk is corroborated by four independent citers, but the uploading channel (presumed Badgers From Mars) could not be verified.
- Badgers From Mars' stance on fan projects: no explicit statement, licence, or takedown was found, but absence of evidence on GitHub-mirrored sources is not proof; BGG/Reddit/Discord posts by the designers could not be read. Trademark registration status of 'Regicide' is unknown.
- Company details: 'Badgers From Mars Limited' (legal name) and 'Auckland' come from sibling snippets; headcount is an inference (3 designers + 'DJ' + contract artist). The GenCon exhibitor record has no year field (repo context suggests 2025).
- Art/style: no official style guide exists; colour facts (teal/red boxes, teal backs, bold-border 2nd-edition backs, Bards art) are from publisher text quoted on GitHub, but no official image could be viewed; the animal-companion species mapping (pangolin/fennec/badger/dove) is an unverified sibling snippet; typography unknown.
- BGG thread contents (3681898 'Inferno variant' = one Jester; 2718237 = hand size 3; 2909781 'Regicide Duel') are one-line snippet summaries and may be incomplete or mis-summarised.
- The regicide-plus 'progress score' denominator reported by a sibling as 480 does not match the true total enemy health of 360; the app's actual constant was not checked.

SOURCES:
- https://raw.githubusercontent.com/MrHinsh/board-games/main/data/raw/bgg/details/307002.xml (BGG XML record for Regicide; local copy scratchpad/dl3/bggxml/307002.xml)
- https://raw.githubusercontent.com/jordyn-liegl/Capstone/master/boardum/data/page_274.json (mirrored BGG record for Regidice 350604)
- https://raw.githubusercontent.com/ettoremodina/RegicideRL/main/rules/RegicideRulesA4.txt (official rulebook transcription; local scratchpad/dl/rules/RegicideRulesA4_main.txt)
- https://raw.githubusercontent.com/drpaj12/LetsPlay_FLC2025_MiamiUniversity/main/INDIVIDUAL_FOLDERS/jamie/REGICIDE_with_CHATBOTS/rules_in_text.txt (second rulebook transcription)
- https://raw.githubusercontent.com/funbinary/boardgame-rules/main/games/bga/regicide.html (mirror of https://en.doc.boardgamearena.com/Gamehelpregicide; local scratchpad/dl2/bga-help-zh-main/file)
- https://raw.githubusercontent.com/teapowell/BGA_Scraper/main/BGA_Scraper.py (BGA gameoption DOM ids)
- https://raw.githubusercontent.com/Poukame/regicide-plus/main/src/Components/SelectOptions.tsx (fan difficulty option values; local clone scratchpad/repos/Poukame__regicide-plus)
- https://raw.githubusercontent.com/steinea/xyz/main/pages/library/games/board-games/regicide.md (2nd Edition publisher blurb quoted)
- https://raw.githubusercontent.com/ariel-hi/who-goes-first/main/src/content/games/regicide-badgers-2021-en.json (PDF SHA-256, first-player rule, teal/red box provenance; local scratchpad/dl/rules/whogoesfirst.json)
- https://raw.githubusercontent.com/Chernowi/RegiSide/main/docs/regicide_rules.md (Red/Teal editions, mulligan variant note)
- https://raw.githubusercontent.com/ayrat555/regicide/master/README.md (Learn-to-Play page URL badgersfrommars.com/en-eu/pages/learn-to-play-regicide)
- https://raw.githubusercontent.com/ch1nq/regicide/main/readme.md and melvinzhang/garden content/posts/regicide.md and agung96tm/board-game-indonesia regicide/README.md (official Learn to Play video 7XoRlKzLobk; BGG thread 2734400)
- https://raw.githubusercontent.com/lyz-code/blue-book/main/docs/regicide.md (fan situation/player modifiers; local scratchpad/notes/lyz_regicide.md)
- https://raw.githubusercontent.com/Octacles7/Regicide/main/README.md (fan hard mode and gold economy)
- https://raw.githubusercontent.com/Kautiontape/regicide/main/NOTICE.md and docs/itch.md (fan trademark/naming practice; local scratchpad/dl/repos/regicide-kautiontape)
- https://raw.githubusercontent.com/Blackbol/KillTheFaceCards/main/README.md, mahocitrus/Regicide.py README.md, Casc0/Not-Regicide README.md, esotix/regicide README.md, kritzmurf/Kill-The-Kings README.md (fan disclaimers)
- https://raw.githubusercontent.com/jakedub/alpha/main/backend/vendors_dump.json (GenCon exhibitor record for Badgers From Mars, booth 2957)
- https://raw.githubusercontent.com/sdjmchattie/sdjmchattie.github.io/main/content/posts/2026/04-25-regicide-game-review/index.md (2026 review: 'Playable with any deck', solo lifelines, companion app)
- https://raw.githubusercontent.com/Press-Play-On-Tape/press-play-on-tape.github.io/main/pokitto_regicide.php (2021 Pokitto fan port quoting the official flavour text)
- GitHub code search results (api.github.com) for 'Regicide Inferno', 'Crown Duels', 'Royal Decree', 'Scorched Earth', 'Sketchgoblin', 'Badgers from Mars', 'Luke Badger', '7XoRlKzLobk', 'learn-to-play-regicide', rumca-js/RSS-Link-Database-2025 and -2026 (mirrored Reddit/YouTube feed entries)
- Sibling agent reports (snippet-sourced): /home/user/PersonalRegicide/docs/research/base_rules_report.md, legacy_report.md, companion_app_report.md
- https://badgersfrommars.com/assets/RegicideRulesA4.pdf (official rules; blocked, text verified via the two transcriptions above)
- https://www.regicidegame.com/site_files/33132/upload_files/RegicideRulesA4.pdf (original official rules URL; blocked)
- https://www.youtube.com/watch?v=7XoRlKzLobk (official Learn to Play video; blocked)
- https://badgersfrommars.com/en-eu/pages/learn-to-play-regicide and https://www.badgersfrommars.com/regicide (official learn-to-play pages; blocked)
- https://www.kickstarter.com/projects/badgersfrommars/regicide-inferno-and-regicide-crown-duels (blocked; snippet data via sibling)
- https://www.kickstarter.com/projects/badgersfrommars/regicide-legacy/faqs (blocked; endorsed house rules via sibling snippets)
- https://boardgamegeek.com/boardgame/460927/regicide-inferno and https://boardgamegeek.com/boardgame/460930/regicide-crown-duels (blocked)
- https://boardgamegeek.com/thread/3681898/regicide-inferno-variant, /thread/2718237, /thread/2909781, /thread/3286672, /thread/2734400, /thread/3585241 (blocked; snippet-level only)
- https://en.boardgamearena.com/gamepanel?game=regicide (blocked)
- https://apps.apple.com/us/app/regicide-companion/id1565706782 and https://play.google.com/store/apps/details?id=com.bfm.regicidecompanion (blocked)