## 0. Access constraints that shaped this report (read first)

- Every primary host the task names was unreachable from this container. `WebFetch` failed with DNS errors, and `curl` through the environment proxy got `CONNECT tunnel failed, response 403` for apps.apple.com, play.google.com, boardgamegeek.com, boardgamearena.com, badgersfrommars.com, kickstarter.com, store.steampowered.com, tabletopia.com and wikipedia.org. Only github.com / raw.githubusercontent.com / api.github.com and pypi.org are allowed. The shared per-turn `WebSearch` budget (200 calls) was already exhausted by sibling agents before my first search call.
- Remedy for the owner: in the cloud environment settings (title bar -> environment menu -> Edit -> Network access) add those hosts under Allowed domains (keep "Allow package managers" ticked), per https://code.claude.com/docs/en/cloud-environments#network-access. A follow-up run can then read the App Store / Play Store listings, the BGG thread 2776625, the BGA game panel and the Kickstarter updates directly.
- Consequently: everything below is from GitHub-mirrored primary material (official rulebook text, BGA's official help page text, a BGG XML API record, an APK manifest analysis, the source of the fan "Regicide Companion Plus", a BGA stats scraper, and mirrored blog/Reddit posts). Store descriptions, version history, IAP price, star ratings and individual user reviews could NOT be read; where I add recollection it is labelled UNVERIFIED.
- Sibling agents already left useful files: `/home/user/PersonalRegicide/docs/RULES_BASE.md` (base-game spec), `/home/user/PersonalRegicide/docs/LEGACY_CAMPAIGN.md` (Legacy spoilers), and the official rulebook text at `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl/rules/RegicideRulesA4_main.txt`. My downloads are under `.../scratchpad/dl2/` (regicide-plus source in `dl2/regicide-plus-src/`, BGA help mirror in `dl2/bga-help-zh-main/file`, BGG XML in `dl2/bgg-307002-xml/file`, APK analysis in `dl2/taptrap-json/file`).

## 1. The official "Regicide Companion" app — verified facts

| Fact | Value | Source |
|---|---|---|
| Name | "Regicide Companion" | official rulebook PDF last page: `LEARN TO PLAY! DOWNLOAD THE FREE 'REGICIDE COMPANION' APP!` |
| Publisher | Badgers From Mars (NZ); "bfm" prefix in the Android package | package id |
| iOS | https://apps.apple.com/us/app/regicide-companion/id1565706782 | community Indonesian rules translation (agung96tm/board-game-indonesia) lists both store links under "Unduh Gratis Aplikasi" = download free app |
| Android | https://play.google.com/store/apps/details?id=com.bfm.regicidecompanion | same |
| Price | Free download, with in-app purchases (Google Play Billing library present in the APK) | rulebook ("FREE"), APK manifest |
| Official app page (historic) | https://www.regicidegame.com/the-app/ | wikiHow guide (2024-09-19): "Use the free Regicide Companion App to help keep track of enemy health and attack values." regicidegame.com was the original site; a May-2025 bookmark of https://www.regicidegame.com/ resolved to the title "Regicide Legacy", i.e. it now points at the Badgers From Mars site. |
| Engine | Unity. Launcher activity `com.unity3d.player.UnityPlayerActivity` (launchMode singleTask, exported) | APK manifest analysis in beerphilipp/taptrap (APK harvested 2024-12-18, analysed 2025-05-20) |
| Android targetSdk | 33 (Android 13) as of the Dec-2024 APK | same |
| Other activities in the APK | `com.android.billingclient.api.ProxyBillingActivity` (Google Play Billing => IAP exists); `com.google.ar.core.InstallActivity` (ARCore installer; most likely a Unity AR Foundation dependency, no evidence of an actual AR feature) | same |
| BGG classification | Regicide (BGG 307002) carries families "Digital Implementations: Google Play", "Digital Implementations: Board Game Arena", "Digital Implementations: Tabletopia" | BGG XML record mirrored in MrHinsh/board-games |

What third parties say the app does (all consistent):
- sdjmchattie review, 2026-04-25: "there is a free Regicide companion app available for both iOS and Android. The app tracks each enemy's hit points as you deal damage, displays the correct attack and hit point values for every enemy, and helps enforce the rules if your group is still learning. It is a clean and practical companion that removes the need for pen and paper entirely."
- melvinzhang/garden notes: "Android/iOS Companion App to keep track of the health/attack and solo mode."
- Chernowi/RegiSide rules doc: "A free 'Regicide Companion' app is available to help track enemy health and attack, which can be useful."
- Poukame (author of the fan "Regicide Companion Plus", repo created ~Sept 2022): "In the online version on BGA, there are some interesting options to increase or decrease the difficulty of the game. I found them interesting and was disappointed by the official app not proposing them." => as of 2022 the official app had NO difficulty/variant options.
- Kautiontape (2026, docs/itch.md): "Badgers from Mars sell Regicide and ship their own Regicide Companion app, so a listing called Regicide competes with them under their own name." (trademark caution for fan apps: keep "Regicide" out of the title/URL/tags, name it in the description).
- The rulebook's "LEARN TO PLAY!" call-out implies the app contains a learn-to-play / tutorial element (inference from the rulebook wording only).

## 2. Official app: feature set and UI flow (reconstructed)

The best available proxy is `Poukame/regicide-plus` ("Regicide Companion Plus", React/Chakra/Vite PWA, live at https://regicide-plus.netlify.app), whose README states "Everything from the official companion app plus: ..." (list in section 8). The screens and logic it reproduces as the baseline are:

1. **Select current enemy** (`SelectCurrentEnemy.tsx`): shows the 4 cards of the current rank (Jacks first, then Queens, then Kings — `sliceIndex(0..4, numberOfDeadFigure)`), using card artwork for J/Q/K of each suit; already-defeated cards are greyed (opacity .3, grayscale) and not clickable. Rationale: the physical castle deck is shuffled, so the tracker must be told which royal was revealed.
2. **Fight screen** (`FightScreen.tsx`): enemy card image in the centre; big red **Health** counter (clamped at 0) and **Attack** counter (clamped at 0); thumbnails of the remaining "enemies to come" of the current rank; suit buttons **heart / diamond / club / spade** and a **Jester** toggle (enemy image goes grayscale with a yellow outline while a Jester is active); an **instant-kill** button (double-tap within 600 ms); an **undo/back** button restoring the previous saved snapshot (enemy health/attack, jester state, cached spade damage); a settings drawer.
3. **Select card value** (`SelectCardValue.tsx`): buttons A, 2..10, plus J / Q / K which only appear after at least one Jack / Queen / King respectively has been defeated (defeated royals can be drawn and played as 10 / 15 / 20).
4. **Select combo / animal companion** (`SelectCardCombo.tsx`): after choosing the base card, either add more cards of the same value in other suits (only shown when the value can legally combo, i.e. index < floor(maxCombo/2) => 2..5 by default; disabled once the combo cap would be exceeded) or add an Ace (animal companion) of a suit; an Ace cannot be paired with a card above the "max animal companion" setting. Then **Validate Attack** or **Cancel**.
5. Back on the fight screen the attack resolves: damage = total (doubled if any club in the play and the enemy is not immune); spades reduce the Attack counter (animated count-down); hearts show "Heal N Cards"; diamonds show "Draw N Cards"; immunity = suits equal to the enemy's suit are filtered out unless a Jester is active; when a Jester is toggled against a **spade** enemy, spades played earlier are retroactively subtracted from attack (`spadeDmgCache`) — matching the rulebook; exact-zero health shows "PERFECT KILL! Put the enemy on top of the Tavern"; health < 0 or instant-kill = normal kill; on kill the jester flag and spade cache reset and the app returns to Select enemy; after 12 kills => **Victory** screen with "Retry with the same options" / "Return to options".
6. Settings drawer: Restart game, Difficulty options (Plus only), Show reminders ON/OFF, Music, Sound FX, Install app (PWA), About/credits.

Caveat: which of these the official app does exactly, and its exact visual design (it uses the Sketchgoblin card art, which the fan app replaced with generated SVG cards), could not be verified from the store pages. The core (choose enemy -> tap suit + value -> health/attack counters update, jester, perfect-kill notice) is consistent with every third-party description above.

## 3. Solo mode in the app

Verified:
- The app contains in-app purchases (Billing library) and third parties describe it as having a "solo mode". The task-supplied BGG thread title "Regicide Solo Mode now available in the app" (thread 2776625) exists; its content could not be fetched.
- BGG files the app under "Digital Implementations: Google Play", which BGG only does for playable implementations, consistent with the solo mode being a full digital game rather than a tracker.

UNVERIFIED (recollection, not confirmed by any source reachable here): the solo mode is a one-time paid unlock (roughly US$2–3), added late 2021, implementing the official solo rules with the official art; whether it has stats, undo, save/resume, or difficulty settings is unknown.

The exact rules the solo mode has to implement (official rulebook, verbatim): "Set up the game as per usual but place the two Jesters to the side. You play with a single hand limited to 8 cards. Play as normal, playing each turn one after the other. A Jester can be flipped to activate the following power: 'Discard your hand and refill to 8 cards - this does not count as drawing for the purpose of enemy diamond immunity.' Since you have two Jesters this can be done twice per game. Flipping the Jesters in this way does not cancel enemy immunity. You are allowed to use the Jester power a) at the start of Step 1 before you play a card or b) at the start of Step 4 before you have to take damage. A win having used 2 Jesters = Bronze Victory. A win having used 1 Jester = Silver Victory. A win having used 0 Jesters = Gold Victory." BGA's official help adds: "A player may not Yield in solo" and the solo loss condition "unable to play a card when the player cannot yield (... in solo mode)".

## 4. Rule data every digital implementation shares (official rulebook, exact values)

- Castle deck: 4 Kings shuffled at bottom, 4 Queens shuffled on top, 4 Jacks shuffled on top; first enemy is always a Jack. Tavern deck: 2–10 of all suits + 4 Animal Companions (Aces) + Jesters by player count.
- Players / Jesters in tavern / max hand size: 1 / 0 / 8; 2 / 0 / 7; 3 / 1 / 6; 4 / 2 / 5. First player: "The player to have most recently committed regicide goes first."
- Enemies: Jack attack 10 health 20; Queen 15 / 30; King 20 / 40. Each enemy is immune to the suit power of its own suit (damage still counts).
- Turn: Step 1 play a card or yield; Step 2 suit power; Step 3 deal damage and check; Step 4 suffer damage.
- Hearts: shuffle discard, count out cards equal to attack value face down under the Tavern deck. Diamonds: current player draws first then clockwise one at a time until value drawn; players at max hand size skipped; never over max; no penalty if tavern empty. Clubs: damage doubled in Step 3. Spades: reduce enemy attack by the value; cumulative across all players against this enemy; persists until the enemy is defeated. "Suit powers are mandatory and cannot be skipped." Red suits resolve immediately; Hearts before Diamonds when both.
- Combos: 2, 3 or 4 cards of the same number with total <= 10 (pairs of 2–5, triples of 2–3, quadruple 2s); all suit powers resolve at the combined value. Animal Companions: value 1, playable alone or paired with exactly one other card (never a Jester, never inside a combo); may pair with another Ace; same suit twice applies the power once.
- Jester: attack 0, played alone, cancels the enemy's immunity, skip Steps 3 and 4, the Jester's player chooses who goes next; communication exception ("I have a good play" / "I would rather not go next"). Spades played before the Jester against a spades enemy start reducing attack; clubs played before the Jester against a clubs enemy do not retroactively double.
- Defeat: total damage >= health. Exactly equal => enemy goes face down on top of the Tavern deck; otherwise to discard. All cards played against it go to discard. Reveal next enemy. The killer skips Step 4 and immediately starts a new turn (Step 1) against the new enemy.
- Step 4: discard cards from hand with total value >= (enemy attack − spades shield); Animal Companion = 1, Jester = 0, Jack/Queen/King in hand = 10/15/20 (same values when played as attacks; their suit power applies normally). Empty hand is fine. Cannot cover => everyone loses.
- Yield: say "Yield", skip to Step 4. "A player may not yield if every other player has yielded on their last turn."
- Game end: win on the last King; lose if a player cannot satisfy damage, or "if any player is unable to play a card or yield on their turn".
- Rulebook URLs: https://badgersfrommars.com/assets/RegicideRulesA4.pdf (current) and https://www.regicidegame.com/site_files/33132/upload_files/RegicideRulesA4.pdf (original; SHA-256 46a7fb460b38f29e7644094267bf5bf097552258be5fdc43f35c25c123ba54be per ariel-hi/who-goes-first). Learn-to-play video: https://www.youtube.com/watch?v=7XoRlKzLobk.
- 2nd edition (product page https://badgersfrommars.com/en-us/products/regicide-2nd-edition): plastic flip-top box, new "Bards" art for the Diamonds suit, touched-up illustrations, card backs match the box colour, bold border on backs; rules unchanged.

## 5. Board Game Arena implementation (gamepanel?id=1606, ?game=regicide)

- Player count on BGA: **1–4** (brownbat/bga-ranked table row: "[593 BGG rank] Regicide | 1-4 | 30m | Card Game, Fantasy, Fighting"). Solo is playable on BGA.
- Official BGA help page (https://en.doc.boardgamearena.com/Gamehelpregicide; English text recovered from the funbinary/boardgame-rules mirror) restates the rulebook with these BGA-specific notes: "Hand Size is 8-5 for 1-4 players respectively"; "A royal's suit blocks the use of that power against it"; Jesters "prevent the Royal from attacking the player" and "the next player to take a turn is chosen by the active player, rather than clockwise"; "Jesters have a value of 0 for the purposes of taking damage"; "Royals as allies - Royals retain their attack value when players play them (J10, Q15, K20) and that is also the amount of damage they can take"; "Yielding - A player may not Yield in solo, or if every other player has Yielded on their last turn"; "Discarding - Cards are only discarded once a Royal is defeated, this is mainly because any Spades played previously or by other players will stack. No other powers stack"; limited-communication rule enforced socially, with the Jester exception implemented as two buttons: "I'd like to go next" / "I'd rather not go next"; identical Solo Game paragraph (Bronze/Silver/Gold).
- **Difficulty options exist on BGA** (this is the thing the official app lacks). From the DOM ids used by teapowell/BGA_Scraper (a Reddit-announced scraper of the author's own Regicide tables, 2025-02-05): `gameoption_100` = modifications Enabled/Disabled (when "Disabled" the scraper records hand_size 0, health_modifier 0, attack_modifier 0, difficulty 1); `gameoption_101` = **hand size** modifier; `gameoption_103` = **enemy health modifier**; `gameoption_104` = **enemy attack modifier**; table stats expose "enemies defeated" (win = 12) and a computed **difficulty** value. `gameoption_102` was not read by the scraper (unknown; plausibly Jesters). Reddit 2025-02-19: "What is the hardest regicide modifier score people have achieved on Board Game Arena and what difficulty settings did you use?" confirms BGA shows a "modifier score".
- The fan "Companion Plus" author says his option set copies BGA's; his list (treat the mapping to BGA as his, not verified against BGA): Maximum hand size change (Default, +1, +2, −1, −2); Remove Jesters (Default, −1, −2); Enemy health boost (Default, +5, +10, −5, −10; applied to every enemy, e.g. Jack 25/Queen 35/King 45 at +5); Enemy attack boost (Default, +2, +5, −2, −5); Yield (On default / Off); Max combo limit (10 default; harder: 9, 8, 6, 4, No combo; easier: 12, 15, 18); Max animal companion limit (Default = K i.e. any card; Q, J, 10, 9 ... 2, A; or No animal companion).
- Not verifiable here: BGA release date, developer credits, real-time vs turn-based availability, number of games played, BGA rating. (Recollection, UNVERIFIED: released on BGA around 2022.)

## 6. Tabletopia

BGG carries the family "Digital Implementations: Tabletopia" on Regicide, so a Tabletopia room/implementation exists. Nothing else (official or fan-made, player count, cost) could be verified; tabletopia.com is blocked.

## 7. Steam

No evidence of any Steam release by Badgers From Mars (no BGG "Digital Implementations: Steam" family, no mention anywhere in mirrored sources). The only Steam/Android "Regicide" is **Warhammer 40,000: Regicide** (Hammerfall Publishing, 2015; Android `com.hammerfall.regicide`) — unrelated, do not confuse.

## 8. What users wish the app had / gaps a fan replica can fill

Direct store reviews and BGG threads could not be read. Evidence of gaps comes from what fan projects explicitly built *because* the official app lacks it, and from community posts:
- **Difficulty / variant options** (hand-size, health, attack, jester count, yield on/off, combo cap, companion cap) — stated reason for Companion Plus; BGA has them, the app doesn't.
- **Progress percentage / score** to compare partial losses (Plus: damage dealt ÷ total enemy health, 480 at default).
- **Action reminders** after each play ("Heal N", "Draw N", "Perfect kill — put the enemy on top of the tavern") so nobody forgets or miscounts.
- **Undo / step back** (Plus keeps a snapshot stack; Paper Crowns keeps history).
- **Landscape + portrait**, **offline/installable** (Plus is a PWA).
- Fan solo implementations add things a tracker cannot: computer-managed deck, automated suit resolution, on-screen damage/shield **forecasts**, a **tutorial**, **save/resume mid-game** (Not-Regicide persists via MMKV; Kill The Face Cards prompts to save), **battle log**, **records/stats** (ggottli "record"; Paper Crowns local records), a **daily seeded challenge with shareable results** and a wished-for leaderboard (Paper Crowns TODO), **manual choice of which cards to discard** when hit, keyboard shortcuts, EN/FR i18n, and **online multiplayer rooms** (Kill The Face Cards: 4-letter room codes on Firebase, reconnect, 30-second disconnect pause, host turn timers; pixelcide: socket.io rooms).
- House-rule/hard-mode ideas seen in fan code: mulligan if no Diamonds in the opening hand (noted as non-official), Octacles7's Godot "hard mode" list (locked 7-card hand, +5 enemy health, halved spade efficiency, joker/ace bosses) and a gold economy.
- Community pain points: the base game is punishing ("I've never made it past the first queen", Reddit 2025-10-25); Regicide Legacy mission 1 "seems impossibly hard — six attempts" (Reddit 2025-08-12) => a replica should surface win-rate stats and adjustable difficulty.

## 9. Regicide Legacy / Inferno / Crown Duels — digital status

- No official digital version of Regicide Legacy was found in any reachable source: no BGA entry, no app, no announcement text. (Kickstarter and badgersfrommars.com could not be read, so an announcement there cannot be excluded.)
- BGG link data on Regicide (307002): reimplementations "Regicide Legacy" (BGG 412963, 2025), "Regicide: Crown Duels" (BGG 460930), "Regidice" (BGG 350604, the April-1st dice game); compilation "Regicide Inferno" (BGG 460927). Inferno is therefore a BGG "compilation" item that contains Regicide — presumably a bundle/new edition with Crown Duels; contents, date and any digital component are UNVERIFIED.
- Regicide Legacy facts from mirrored data: designers Paul Abrahams, Luke Badger, Andy Richdale; publisher Badgers from Mars; 1–4 players, 60 min, age 10+, "best with 2" in one collection export; BGG rating ~8.1 vs base game 7.4 in a 2025/26 snapshot; copies sold at GenCon Aug 2025 (Reddit 2025-08-12), broad availability April 2026 ("It's finally here!" 2026-04-24), SU&SD video review 2026-04-09 (https://www.youtube.com/watch?v=boATqYrk61c) and a Dice Tower review; 2026 Golden Geek nominee list; excluded from Spiel des Jahres 2026 consideration for "no German release". Blurb: 12 missions, "Golden Blade Syndicate" of 40 adventurers, new enemies/classes/items. The sibling's docs/LEGACY_CAMPAIGN.md (Kickstarter 2024, backer delivery 2026, retail est. Nov 2026, rulebook details) is that agent's claim, not re-verified by me.
- Fan digital Legacy: DorkDad141/regicide-js (Vue solo implementation with a full fan transcription CAMPAIGN_RULES.md) — already downloaded by a sibling at `.../scratchpad/dl/repos/regicide-js/`.

## 10. Kickstarter

Regicide was "funded by Kickstarter in May 2020" (https://www.kickstarter.com/projects/badgersfrommars/regicide; melvinzhang/garden). The Kickstarter update announcing the app could not be fetched.

## 11. BGG snapshot for the base game (XML record, mid-2025)

9,466 ratings, average 7.39 (Bayes 6.96), Board Game Rank 542, Strategy rank 385, weight 1.97/5, 16,738 owners; player-count poll (206 votes): best with 2, recommended 1–4; playing time 10–30 min; age 10+; alternate names レジサイド / 레지사이드; publishers Badgers from Mars, BoardM Factory, Devir, Gameplay Publishing ApS, Hobby Japan, IELLO; families include "Contests: 54-Card Game Design", "Series: Pocket Games (Devir)".

## 12. Open-source implementations worth mining (for the engineer)

Rules engines: ch1nq/regicide (Rust framework, 10 stars), ahgamut/regi-py (C++ core + Python bindings + web driver; sibling downloaded), ettoremodina/RegicideRL (Python env + full rules text + tests; sibling downloaded game.py/tests), sanjitdp/ai-madrl-regicide, Rabmuk/Reinforcement-Regicide, olevandermast/regibot (bots). Python game loops: snsutton/regicide, fbec76/regicide, NameError1/Regicide-Engine, mahocitrus/RegicideRemake, BakaAic/Regicide, lythienne/regicide (solo, terminal). Mobile/web solo: Kautiontape/regicide "Paper Crowns" (Svelte, daily challenge, tutorial; sibling downloaded), Casc0/Not-Regicide (React Native + XState + MMKV, EN/ES), wedk/regicide (vanilla TS), ggottli.github.io/games/regicide (single-file solo table with records), javirs85/Regicide (React -> Capacitor Android), Erebuz/regicide (RN). Companion/tracker: Poukame/regicide-plus. Multiplayer web: Blackbol/KillTheFaceCards (React + Firebase, solo medals, save), john-carlo-flores/pixelcide (React + Express + socket.io), esotix/regicide (local 2–4 + solo, FR). Legacy: DorkDad141/regicide-js. BGA Studio structure example: ugoanyaegbunam/gba-comps-submission-2025 (ethan/RegicideC: states.inc.php, Game.php, dbmodel.sql, regicidec.js). Variants: Octacles7/Regicide (Godot, currency + hard mode), lazypool/RegiBeast (roguelike), jonathonthill/1789 (retheme).

UNCERTAINTIES:
- App Store and Google Play listings (description text, version history/what's-new, screenshots, ratings count/average, individual reviews, IAP names and prices, release date, size, languages) could not be read: both hosts are blocked by the environment network policy (CONNECT 403).
- BGG thread 2776625 ('Regicide Solo Mode now available in the app') and the Kickstarter update about the app could not be read (boardgamegeek.com and kickstarter.com blocked). Exact solo-mode IAP price, launch date, and whether the solo mode includes stats/undo/save/difficulty are UNVERIFIED; my recollection (paid unlock ~US$2–3, late 2021) is not confirmed by any source reached.
- The official app's exact screen flow is reconstructed from the fan 'Regicide Companion Plus', whose author claims it includes 'everything from the official companion app'. The official app's precise UI, animations, tutorial/learn-to-play content and whether it has undo/instant-kill could not be confirmed.
- Board Game Arena: the game panel (id=1606) could not be fetched. Player count 1–4 and the existence of hand-size / enemy-health / enemy-attack modifiers and a 'difficulty'/'modifier score' are confirmed indirectly (BGA-ranked table, scraper DOM ids, Reddit). The full option list (what gameoption_102 is; whether yield-off, combo cap, companion cap, jester removal are real BGA options or only the fan app's additions), developer credits, BGA release date, play counts and real-time/turn-based support are unverified.
- Tabletopia: existence inferred only from the BGG 'Digital Implementations: Tabletopia' family; no details.
- Steam: absence of a Badgers From Mars Steam game is inferred from the lack of any mention and no BGG Steam family; not proven.
- Regicide Inferno (BGG 460927, 'compilation') and Regicide: Crown Duels (BGG 460930): nothing beyond the BGG link types; contents, dates and any digital plans unknown. No announcement of a digital Regicide Legacy was found, but badgersfrommars.com/Kickstarter could not be checked.
- The ARCore InstallActivity in the Android APK may indicate an AR feature or merely a bundled Unity dependency; unknown.
- Dates derived from GitHub repository ids (e.g. regicide-plus created ~Sept 2022) are approximate.
- Regicide Legacy production/shipping dates in the sibling's docs/LEGACY_CAMPAIGN.md were not re-verified by me.

SOURCES:
- Official rulebook text (RegicideRulesA4.pdf) as mirrored in ettoremodina/RegicideRL rules/RegicideRulesA4.txt — local copy /tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl/rules/RegicideRulesA4_main.txt
- https://raw.githubusercontent.com/Poukame/regicide-plus/main/README.md and src/ (App.tsx, OptionsContext.tsx, Components/*.tsx, assets/*.ts) — Regicide Companion Plus
- https://raw.githubusercontent.com/funbinary/boardgame-rules/main/games/bga/regicide.html — mirror of https://en.doc.boardgamearena.com/Gamehelpregicide
- https://raw.githubusercontent.com/teapowell/BGA_Scraper/main/README.md and BGA_Scraper.py — BGA Regicide option/stat DOM ids
- https://raw.githubusercontent.com/brownbat/bga-ranked/main/README.md — BGA games ranked by BGG (Regicide 1-4 players, 30m)
- https://raw.githubusercontent.com/MrHinsh/board-games/main/data/raw/bgg/details/307002.xml — BGG XML API record for Regicide
- https://raw.githubusercontent.com/beerphilipp/taptrap/main/vulnerable_app_detection/results/2025-05-20/output/com.bfm.regicidecompanion.json — Android manifest analysis of the companion app
- https://raw.githubusercontent.com/sdjmchattie/sdjmchattie.github.io/main/content/posts/2026/04-25-regicide-game-review/index.md — 2026 review with 'The Free Companion App' section
- https://raw.githubusercontent.com/SeeSharpSi/obs_pixie_8/main/plugin-folders/Clippings/Card%20Games/How%20to%20Play%20Regicide%20Card%20Game%20Rules%20%26%20Strategy%20Guide.md — clipping of wikiHow 'Regicide Card Game' (2024-09-19) citing regicidegame.com/the-app/
- https://raw.githubusercontent.com/melvinzhang/garden/master/content/posts/regicide.md — notes: Kickstarter May 2020, companion app solo mode, BGA link
- GitHub code search: agung96tm/board-game-indonesia regicide/regicide-rules-id.txt (store URLs, 'free app')
- GitHub code search: Chernowi/RegiSide docs/regicide_rules.md; IorMemorE/regicide_pure_text_demo README (official mobile app link)
- Local sibling download: /tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/dl/repos/regicide-kautiontape/{README.md,NOTICE.md,TODO.md,docs/itch.md}
- https://raw.githubusercontent.com/Blackbol/KillTheFaceCards/main/README.md
- https://raw.githubusercontent.com/esotix/regicide/main/README.md
- https://raw.githubusercontent.com/wedk/regicide/main/README.md
- https://raw.githubusercontent.com/ggottli/ggottli.github.io/main/games/regicide/index.html
- https://raw.githubusercontent.com/Octacles7/Regicide/main/README.md
- https://raw.githubusercontent.com/john-carlo-flores/pixelcide/main/README.md
- GitHub code search: Casc0/Not-Regicide README/i18n fragments
- GitHub code search: rumca-js/RSS-Link-Database-2025 and -2026 (mirrored r/boardgames posts: BGA modifier score 2025-02-19, BGA scraper 2025-02-05, Regicide Legacy GenCon 2025-08-12, 'finally here' 2026-04-24, SU&SD review 2026-04-09, win/loss ratio 2025-10-25)
- GitHub code search: steinea/xyz regicide-legacy.md and regicide.md (Legacy blurb, 2nd edition blurb); sportomax1/board-game-lab licenses (BGG ratings 8.1 / 7.4); recommend-games/spiel-des-jahres exclude.csv; MatheusFaria/our-boardgames collection export
- GitHub code search: ariel-hi/who-goes-first regicide-badgers-2021-en.json (rulebook URL + SHA-256, first-player rule)
- GitHub code search: ugoanyaegbunam/gba-comps-submission-2025 ethan/RegicideC (BGA Studio implementation structure)
- Sibling agents' repo docs: /home/user/PersonalRegicide/docs/RULES_BASE.md and docs/LEGACY_CAMPAIGN.md
- Environment documentation page environment.network (network allowlist remedy)