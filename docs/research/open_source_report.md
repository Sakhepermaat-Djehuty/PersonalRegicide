# Regicide: open-source implementations, solvers, assets and licensing — research dump

## 0. Access constraints (read first)

- The session's web-search budget was already exhausted (200/turn shared cap) before this task started, so **no web search was performed**. All discovery was via the GitHub Search API (repos + code), the GitLab API, the PyPI JSON API, the npm registry search API, and direct `git clone` of ~140 repositories into the scratchpad (`/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/repos/`).
- The egress proxy returned **403 policy denials** (CONNECT refused) for: `badgersfrommars.com`, `regicidegame.com` (not tried directly but same publisher), `itch.io` and `*.itch.io` (incl. `jacoblillywhite.itch.io`), `boardgamegeek.com`, `api.geekdo.com`, `kickstarter.com`, `web.archive.org`, `reddit.com`, `arxiv.org`, `huggingface.co`, `codeberg.org`, `sourcegraph.com`, plus (seen in proxy log) `merchantsofplay.com`, `scribd.com`, `thesoloboardgamer.com`, `gathertogethergames.com`, `homeofmark.com`, `decksplain.github.io`. Reachable: `github.com`, `raw.githubusercontent.com`, `api.github.com` (search only; file reads restricted to the user's own repo), `gitlab.com`, `pypi.org`, `registry.npmjs.org`.
- Consequence: **the itch.io "regicide assets" pack, the official rules PDF, the official site, BGG files/forums and the Kickstarter page could not be read directly.** Everything reported about them below is reconstructed from mirrored copies/transcriptions inside GitHub repos and is flagged in Uncertainties.

---

## 1. Landscape summary

GitHub repo search returns ~46 repos for "regicide card game", 31 for "regicide language:python", 36 JS, 28 TS, 4 Godot, 4 Unity-ish, 1 Swift (unrelated), 1 Dart, 2 Kotlin, 1 Lua; ~239 for bare "regicide" (many unrelated: RegicideOS Linux distro, AoE4 mods, Minecraft plugin, a chess platform, a Go regex tester, a checkers site). GitLab: 4 (3 relevant). PyPI: 1 relevant package (`regicide`, Rust ext). npm: 0 relevant (`regicide` on npm is an unrelated "collection of one-off functions", ISC). itch.io: could not be queried; two fan games are known to be published there via their GitHub repos (Paper Crowns by Kautiontape; the Lexaloffle BBS/PICO-8 "Replicide").

Star counts are tiny everywhere (max 10). Quality signal therefore comes from test counts, rule-fidelity docs, and recency. Test-case counts I measured by grepping `it(`/`test(`/`def test_`/`#[test]`:

| Repo | Tests | Notes |
|---|---|---|
| DorkDad141/regicide-js (Regicide **Legacy**) | 452 | Vitest; covers all 12 campaign missions |
| CuatroSeis/regicide-web | 201 | engine package + server rooms; rules traced to `[R-x]` IDs |
| pholser/regicide-python | 194 | pure Python, solo, value-model solver, hint command |
| ahgamut/regi-py | 158 | C++ core + Python + WASM; RL nets |
| Kautiontape/regicide ("Paper Crowns") | 53 | Svelte solo; forecasts; daily challenge |
| Blackbol/KillTheFaceCards | 44 | React; solo + Firebase multiplayer |
| HelloClaraCards/regicide (PWA) | 36 + 300 random self-play games with card-conservation invariant | vanilla JS; WebRTC multi-device |
| ch1nq/regicide (PyPI `regicide`) | 6 (Rust) | MCTS framework |
| olevandermast/regibot | 0 | MCTS with determinization; good GAME_MECHANICS.md |

---

## 2. Notable repositories (detailed)

### 2.1 Engines / frameworks / solvers (AI-relevant)

**ch1nq/regicide** — https://github.com/ch1nq/regicide
- Language: Rust (pyo3 bindings via maturin) + Python examples. Published to PyPI as **`regicide` 0.1.5** (Cargo package name `regicide-rl`, author "askepen <aske@daske.dk>", last commit 2024-03-23 "Video explaining rules"). 10 stars.
- License: **none in repo, none on PyPI** (`license: None`) → all-rights-reserved by default. Do not copy code; API ideas are fine.
- Implements: full 1–4 player rules per the official PDF. `State::new` config table (src/game/state.rs:57): players→(jesters, max hand, solo hand refills) = `1→(0,8,2)`, `2→(0,7,0)`, `3→(1,6,0)`, `4→(2,5,0)`. Enemy HP J/Q/K = 20/30/40 (enemy.rs), attack = card attack value 10/15/20. Actions: `Play(card)`, `AnimalCombo(c1,c2)`, `Combo(cards)` (2–4 same value, sum ≤ 10), `Yield`, `Discard(cards)`, `ChangePlayer(id)` (after Jester), `RefillHand` (solo jester). Players: `InputPlayer`, `RandomPlayer(seed)`, `MCTSPlayer(playouts, num_threads, use_heuristics, policy_variation, deterministic_samples)` with `ranked_actions()`.
- Edge-case handling worth borrowing:
  - Exact kill: `health == 0` → enemy to **top of tavern deck**; `< 0` → discard (state.rs:251–266).
  - Spade shield floors at 0 (`decrease_attack ... unwrap_or(0)`); if effective attack is 0 the discard step is skipped and play passes (state.rs:276–283).
  - Jester vs spades enemy: shields played *before* the Jester are retroactively applied (`prior_spades_played`), matching the rulebook sentence; clubs are not retroactive.
  - Loss check in Step 4 is "total hand value < enemy attack" (so the discard is always coverable if the check passes).
  - Yield: `times_yielded` counter; yielding when `times_yielded >= players.len()` ends the game as a loss (slightly stricter than the rulebook's "may not yield" — treats an illegal yield as loss; note `< self.players.len()` means in a 1-player game the first yield is allowed, i.e. solo yield IS allowed here, unlike most other implementations).
  - Discard action space = all subsets with sum ≥ damage (no minimality filter) — blows up combinatorially; regibot's "inclusion-minimal" filter is better.
- Experiments (python/performance_tests.py + plots.py): grid over MCTS playouts 10^0..10^6, player counts 1–4, five UCT tree-policy variations (`UCTBase`, `UCTVariation2/3/4` from policy.rs), and "deterministic_samples" (determinizations) with playouts×samples = 1e6; score = enemies defeated (0–12), "win" = score 12. **Result CSVs/plots are not committed**, so no win-rate numbers are recoverable from the repo (see Uncertainties). Looks like a student thesis project (LaTeX table export in code).
- PyPI wheels exist for cp37–cp311 manylinux/macOS/win + pypy37; **no pure-Python sdist usable on iOS** → not usable in Pythonista.

**ahgamut/regi-py** — https://github.com/ahgamut/regi-py (last commit 2026-10-01)
- Language: C++ core (`src/regi_py/core/*.cc`), pybind11 Python wrapper, Emscripten WASM build + onnxruntime-web bots, PyTorch RL (AlphaZero-style "AZ" nets and "ADZ"/DouZero-style nets), R analysis scripts.
- License: **MIT** ("Copyright © 2026 Marie Hardt and Gautham Venkatasubramanian").
- Implements: 2–4 players only (`initHandSize`: 2→7, 3→6, 4→5; `totalPlayers() > 4 || < 2` → game ends INVALID_START_PLAYER_COUNT) — **no solo mode**. Jokers: 1 for 3p, 2 for 4p. Enemy HP = 2×strength (enemy.cc). Diamonds draw is round-robin starting from active player, stopping when all hands full (effects.cc `refreshDraws`). Hearts: shuffle discard, move up to n to draw pile bottom (`refreshDiscards`). Spade/Jester semantics centralised in `comboBlock/currentBlock` with a `JOKER_NERF` power bit: once any used combo on the current enemy carries JOKER_NERF, the enemy's SPADES_BLOCK immunity is cleared and all spades in `usedPile` count (i.e. retroactive spade shields, consistent with rulebook).
- Strategies (`__strat_name__`): `dummy`, `trim-random`, `sub-random`, `preserve`, `suitpref` (24 suit-priority permutations CDHS…SHDC), `expansion`, `brute`/`brute-N` (brute sampling), `mcts-explorer`/`mcts-N`, `mcts-saver`, plus net bots. Has a `RecommenderMixin.getRecommendedMoves()` contract for hint UIs.
- Benchmark tooling: `game_json/bench_summary.py` defines **progress 0–360 where win = 360** (each enemy worth 30; bands 0–80 / 81–200 / 201–360), R scripts label progress breaks "Start, 1st Jack … 4th King, Win". Files are named `asa_poster_plots.R` / `sep_seminar_plots.R` (academic poster/seminar) but **no numeric results or paper link are committed**.
- WASM UI ships **opening-deal presets** per player count in Easy/Medium/Hard tiers (5 each) — a neat "difficulty by seed" idea (`webdriver/wasm/tables/presets_{2,3,4}p.json`).
- Quality: high (158 tests, parity tests JS↔Python, golden files). Heavy toolchain (C++/pybind/torch) → not Pythonista-portable, but the rule semantics and strategy roster are worth mirroring.

**olevandermast/regibot** — https://github.com/olevandermast/regibot (2026-05-09)
- Python 3.10+, **no license file**. MCTS bot with two modes: `FULL_INFORMATION` (tree reuse) and `PLAYER_VIEW` (observation + determinization; one-ply root aggregation, many rollouts). Rewards: win 1.0, loss shaped in (0, 0.22] by bosses defeated.
- `GAME_MECHANICS.md` is an unusually explicit spec of how its code interprets rules. Borrowable: **defend legality = total ≥ D and inclusion-minimal** (no proper subset already covers D). Hand cap formula `max(min(9 - num_players, 8), 1)`. Jack/Queen/King stored as distinct ranks (not value 10/15/20) to avoid aliasing with 10s. Draw deck modelled as `top_cards_ordered` (FIFO, for exact-kill enemies) + `cards_unordered`.
- Divergences to be aware of: spades reduce incoming hit only on the attack that contains spades and by the *whole* combo value (not cumulative across turns) — **not rulebook-accurate**; no Jester/joker; no yield-restriction logic.
- Rollout heuristics (rollout_policy.py): penalty 4.0 for playing the boss's suit, overkill penalty 1.0/point, yield base cost 12 (+4 if holding diamonds, +5 if hand sum > boss HP + 5), yield "less bad" (5.0) only when no diamonds and hand not much larger than boss HP; defend heuristics lightly penalise total value and card count.

**pholser/regicide-python** — https://github.com/pholser/regicide-python (2026-10-06, 194 tests, **no license**)
- Pure Python 3 (dataclasses, no numpy at runtime), solo-focused: `solo.py` implements the two set-aside Jesters (flip at start of Step 1 or Step 4; does not cancel immunity; Gold/Silver/Bronze = 0/1/2 used), `legal_moves.py`, `hints.py` (simulates a turn from a reshuffled tavern), `benchmark.py` with a ladder of policies: `RandomDecisions`, `GreedyDecisions` (highest-attack play; cheapest cover), `GreedyRescueDecisions` (flip Jester when hand < effective attack), `ShieldFirstDecisions` (prefer highest Spades play unless enemy immune), `DiamondsTimingDecisions` (hold Diamonds while hand value ≥ 2× effective attack), `SuitAwareDecisions` (discard preference keep-values Spades 2, Diamonds 1, Clubs 0, Hearts 0), `LookaheadDecisions` (8 rollouts per candidate, reshuffled tavern, win-rate then mean enemies), `ValueGuidedDecisions` (4 samples per play, linear value model).
- Fitted linear value model (`value_weights.json`, 21 observable features): intercept 8.727; notable coefficients: `solo_jesters_remaining` **+1.139**, `castle_size` **−0.509** (fewer enemies left = better), `enemy_is_diamonds` **−0.153** (Diamonds enemies are the dangerous ones), `enemy_attack` +0.110, `enemy_effective_attack` −0.037, `hand_diamonds` +0.057, `hand_size` +0.051, `tavern_size` +0.029, `enemy_remaining_health` −0.024, `enemy_shield` −0.026. Benchmark **win-rate numbers are not committed** (run `python -m regicide.benchmark`).
- This is the closest thing to a drop-in pure-Python solo engine + heuristic AI for a Pythonista project, but **no license** → treat as reference only.

**pinniped-9bb7d9/Regicide-ISMCTS** — https://github.com/pinniped-9bb7d9/Regicide-ISMCTS (2025-11-11)
- Python, no license, no README. Information-Set MCTS vs human (player 0 human, others AI), configurable max runs/time, logs bosses defeated and turns survived. Hand sizes via `"??765"[num_players]` (2→7, 3→6, 4→5; no solo). Combo generation hard-codes pairs for any rank, triples only ranks 2–3, quad only rank 2 (correct for ≤10 rule). Yield allowed only if `consecutive_yields < players-1`. Loss band-aid: empty hand while boss attack ≠ 0.

**sanjitdp/ai-madrl-regicide** — https://github.com/sanjitdp/ai-madrl-regicide (MIT, 2025-01-14)
- Python gymnasium env for a **2-player** game, 7-card hands, DQN-style self-play. Rewards: Jack +1, Queen +2, King +3, lose −1, invalid move −999999. No results committed.

**Chernowi/KingSlayer** — https://github.com/Chernowi/KingSlayer (2026-01-19, no license)
- MARL research framework (extension of pymarl_transformers): QMIX, TransfQMix, MAPPO on a fixed **4-player** Regicide env (hand 5), action masking of "suicidal attacks" and illegal yields, entity-based observations; includes a *hidden discard pile* concept (after a Hearts heal the remaining discard is turned face-down so players cannot infer which cards went back). Contains a LaTeX report whose Conclusions/Results chapters are `\todo` — **no win-rate results**. `docs/regicide_game_rules.md` is a full transcription of the official rulebook (components line: "52-CARD DECK + 2 JESTERS | PAUL ABRAHAMS, LUKE BADGER, ANDY RICHDALE | SKETCHGOBLIN; PLAYERS 1-4; TIME 5-20 min; AGE 10+").
- Related: Chernowi/RegiSide (Flask REST backend) — its README states suit powers **wrongly** ("Spades double damage, Clubs heal all"); do not use as a rules source.

**Rabmuk/Reinforcement-Regicide** (Jupyter, no license): DQN attempts; action-space pivots documented; no results. **kunal-kapur/regicide-rl**, **RemiZheng1/Regicide** (Dueling DDQN with attention, logs winrate CSVs not committed): no results. **mahocitrus/RegicideRemake** (Python, no license): solo AI with a documented strategy (`RegicideAI_Strategy.md`, Chinese) — priorities: (1) prefer **exact kill** over overkill, (2) if no kill, prefer plays that reduce enemy attack to 0 or leave a hand that can absorb the hit (simulate post-play hand incl. expected draws at 5.5/card), (3) prefer same-rank combos, (4) use Clubs only when not immune and damage matters, (5) hold Hearts for late deck, (6) treat Aces/low cards/Hearts as cheap discard fodder and avoid wasting them in attacks, (7) when discarding prefer low-value Hearts, keep Diamonds and Aces, (8) Jester (solo refill) only as a last resort.

### 2.2 Regicide **Legacy** (the campaign game the user wants)

**DorkDad141/regicide-js** — https://github.com/DorkDad141/regicide-js — "Regicide Legacy: Pure front-end implementation of the solo game" (TypeScript/Vue 3/Pinia/Vite, Vitest **452 tests**, single commit 2026-04-04 by "Jeff Till", **no license**). This is the only public Legacy implementation found. Its `CAMPAIGN_RULES.md` + README encode the full 12-mission campaign; I could not verify these against the official Legacy rulebook (blocked), so treat as "one fan's transcription", but it is extremely detailed and internally consistent (tests per mission). Key data:

- New card types: Standard A,2–10,**12**; **Nineteen** (19, no suit, no powers); **Archmage** (25, no suit); **Beast** (value 0; copies partner's value in a 2-card combo; cannot be in a same-rank combo with >1 non-Beast card); **2/5 (TwoFive)** (player chooses 2 or 5; auto-resolves next to a real 2/5; three+ together → 2 each; always worth 5 when discarding for damage); **Jester** (value 8 for Legacy, played from a separate pool, always bypasses immunity, removed from game after use); **Choosable Ace** (pick one of the 4 base suits at play time); **Corrupted** cards (asterisk; on play banish top card of tavern — or of discard with Evergreen Mother (Corrupted); bypass immunity for their suits); **Restored** cards (on play move top of banished pile to bottom of tavern; bypass immunity).
- Campaign suits and resolution order: 1 **Mages ★** (reveal N from tavern, pick 1 to add to combo, rest discarded; chains if a Mage is picked), 2 **Druids** (sort entire discard into Hand/Top/Bottom/Banish/Remaining), 3 Hearts, 4 Diamonds, 5 **Drums** (draw up to N extra, discard down to hand size), 6 Clubs ("Warrior", double), 7 **Reavers ⚔** (reveal N, banish all, add chosen card's value to damage; free double if tavern empty), 8 Spades, 9 **Guardians 🛡** (take no damage this turn). N = combo damage at the point that suit resolves. Immunity blocks a suit unless the combo contains a corrupted/restored card of that suit.
- Relics: **Kinfolk Flute** (store one card value 2–5 per turn, all same rank; flute cards playable alone), **Scarlet Whistle** (play Ace/Beast with top discard card), **Azume/Azure Emblem** (after a Mage pick, save one remaining revealed card to top of tavern), **Evergreen Mother (Corrupted)** / **(Restored)**.
- Yield in Legacy: "You cannot yield twice in a row against the same enemy" (`hasYielded` flag reset on enemy defeat).
- Loss: pending damage > hand value (2/5 counts 5); or no pending damage, hand empty, Jester pool 0 and Flute empty. Between attempts a "Mercenary Camp" shop sells 12s, 19s, Choosable Aces, extra Jesters, 2/5s for coins.
- Missions (atk/hp): M1 standard 12 royals (J 10/20, Q 15/30, K 20/40) → corrupt 1 random card (value 2–9, never repeat a rank, same suit ≤ 2×), gain Flute, add Archmage. M2 six Hydras 10/20 each with a distinct pair of basic suits; imperfect kill → bottom of enemy deck, perfect → banished; post: add one basic suit to a random 3,5,7,9 (each suit used once), corrupt another. M3 Mage Tower: 4 Mages 10/30, 2 Wizards 15/45, 1 Grand Wizard 20/60, all Mage-suited; end of turn put top tavern card in mission zone; enemies immune to all suits in mission zone; post: add A★–10★, corrupt. M4 Gauntlet: standard 12, enemies corrupted from now on, enemy attack += value of top discard card; post: add Goran (8, no suit), Scarlet Whistle, corrupt; from M5 choose 1 Beast per mission. M5 Siege: 4×10/40 + 4×15/60; add Reaver 3/5/7/9 and Myla (7); end of turn top banished → mission zone; attack += sum of mission zone; perfect kill deals defeated enemy's base attack to next enemy; post: keep Reaver 5, add Reaver suit to 6♥/6♦/6♠ (choice), add ♣ to Goran, corrupt. M6 Evergreen Siege: 4 Guardians 15/30 + 4 Evergreens 20/40; defeat → banish enemy, move 1 play-area card to zone, suffer damage = zone total (skipped if Guardian suit activated; perfect kill ignores highest card); post: Azure Emblem, keep Guardian 3, add Guardian suit to 8♦/8♥/8♣, add ♠ to Goran, corrupt. M7 Pilgrimage: Pilgrim deck = 4×(2–7) + 1 Ace (25 suitless cards); start of turn top pilgrim → zone; played card value matching a pilgrim banishes it; defeat → N top tavern cards to discard (N = zone total); post: keep Druid 7, add Druid suit to 4♦/4♠/4♣, add ♥ to Goran, corrupt. M8 Troll Bridge: 6 Trolls 10/20 dual-suited then 6 Wyverns 25/50; attack += non-pilgrim zone total; optional ascending placement of played cards into zone, placing a 10 triggers a one-time discard-cleanse; post: keep Drum 9, add ♦ to Goran, add Drum suit to 2♠/2♣/2♥, corrupt. M9 Rescue: 3 captured piles of 10; 4×15/30 + 4×20/40 then **Myla 20/80 (♠♦ immune, permanent)**; end-of-turn choice (banish from hand + take top of a pile → discard) or rotate piles; post: permanent Mage Beast, Mage suit to a random 4 or 8, Goran ignores immunities, pilgrim deck dissolved. M10 Corruption: your corrupted cards become enemies, HP = 5×value, attack = value + zone total, with per-suit abilities (♣ doubles total attack, ♠ reduces incoming by value, ♥ end-of-turn top discard → zone, ♦ end-of-turn choose a hand card → zone); post: cards return, Goran removed. M11 Beast Hunt: 4×10/30 no suit + **Evil Goran 20/90**; immune to suits on top of banished and discard; attack += both top values; start of turn random Beast into zone with suit effect; post: add Esme 6♣♠♥♦. M12 Final Stand: corrupted → restored; 4 Queens 15/30 + 4 Kings 20/40 + **High Arcana 25/120**; attack += zone total; immune to zone suits; defeat banishes zone, enemy and the whole discard pile.

### 2.3 Full-rules digital games (solo and multiplayer)

- **Blackbol/KillTheFaceCards** — https://github.com/Blackbol/KillTheFaceCards — React 18/TS/Tailwind/Vite/Vitest, **MIT** (2026-08-09). 1–4 players via Firebase Realtime DB rooms (4-letter codes, reconnection tokens, 30s disconnect auto-pause, host kick/timer), official solo mode (8-card hand, 2 solo Jokers = cancel immunity **or** refill — note: the rulebook solo Jester does *not* cancel immunity; this repo lets it), medals, save/resume, Pixel-7 phone layout with pinned bottom action bar and horizontal hand scroll, EN/FR i18n, integrated rulebook. Tests include "forbids passing if all other players passed consecutively", "retroactively activates Spade shields when Joker is played against a Spade enemy", "skips discard phase if Spade shield completely blocks", "places enemy FACE DOWN on TOP of Tavern deck on Perfect Execution (HP === 0)". Disclaimer: "Unauthorised fan-made adaptation. No official artwork or trademarks used. Standard 54-card deck mechanics."
- **Kautiontape/regicide ("Paper Crowns")** — https://github.com/Kautiontape/regicide — Svelte/TS, **MIT (code only)**, published on itch.io at `kautiontape.itch.io/paper-crowns` and `regicide.kautiontape.com` (2026-10-12). Solo only; 40-card tavern (no jesters in deck), 2 Jester flips (usable in play or damage phase; *does not* cancel immunity; "does NOT refill hand after taking damage"), on-screen **forecast** of every candidate play (damage after doubling, enemy HP after, exact-kill flag, new shield, new effective ATK, new hand/discard/tavern sizes), rule-explanation strings that fade with repetition, tutorial, **daily challenge** (FNV-1a seed of local date; Daily #1 = 2026-05-12) with shareable results, undo via history. `NOTICE.md`: "shares no text or art with the published game… cards are Unicode suit glyphs". `docs/itch.md` documents the deliberate naming policy: never put "Regicide" in the title/URL/tags (competes with the publisher's own Companion app), only in the description as attribution.
- **CuatroSeis/regicide-web** — https://github.com/CuatroSeis/regicide-web — TS monorepo (pnpm): pure engine package + React/Vite web + Socket.io server + Supabase auth, **MIT**, 201 tests, Spanish. Rules are documented in `docs/rules-source.md` with traceable IDs `[R-1]…` quoting the official PDF (good template for a spec). Solo + 2–4 online. Art: Kenney UI packs + game-icons.net avatars (both permissive) — not official art.
- **HelloClaraCards/regicide** — https://github.com/HelloClaraCards/regicide — vanilla JS **offline-first PWA for phones**, no license file (2026-08-26). Solo (official solo rules), pass-and-play 2–4 on one phone, and multi-device 2–4 phones over local Wi-Fi/hotspot via WebRTC bootstrapped by QR codes (no internet); host-authoritative engine with per-seat redacted views. Test names enumerate rulebook edge cases (see §3). Default branch is a Claude-generated branch name; "vibe-coded".
- **Casc0/Not-Regicide** — https://github.com/Casc0/Not-Regicide — React Native/Expo, XState FSM game core, Zustand UI state, MMKV persistence, EN/ES; solo only; README shows an MIT badge but **no LICENSE file in repo**. Live at not-regicide.vercel.app.
- **GutuGaluppo/regicide ("Regicide Tracker")** — React Native/Expo (iOS/Android/web), four modes: full digital game, online multiplayer (Firebase), physical-deck tracker with undo, in-app rulebook; PT/EN/ES/FR; no license.
- **xunserver/regicide** — https://github.com/xunserver/regicide — mobile H5 (Vite+React+TS+Phaser 4), Chinese UI; solo engine as an explicit FSM: phases `play | defend | won | lost`; actions `PLAY/YIELD/FLIP_JESTER` in play, `DEFEND/FLIP_JESTER` in defend; documented transitions (e.g. "PLAY/YIELD when shield reduces damage to 0 → stay in play"; "lost when cannot cover damage, or empty hand and just yielded"). No license.
- **Joat917/Regicide4** — JS, **MIT**, solo console/mobile; "without art (copyright issues)". Its README (Chinese) is the best-sourced rules clarification doc I found, citing the official How-to-Play page, the BGA rules page (`en.doc.boardgamearena.com/Gamehelpregicide`), the BGA tips page, merchantsofplay, rmwinslow, gamerules.com and gamesnightguru. Clarifications it records: each suit power uses the **whole combo total** (A♣+8♦ = 9: draw 9 and deal 18); same suit in one play resolves once; "**only Spades accumulate**, everything else is one-shot"; Hearts before Diamonds; Jester-played may choose **themselves** as next player (its reading); immunity cancel lasts until the enemy dies; solo cannot yield; "mulligan if no Diamonds in opening hand" (also in rmwinslow's summary — **not in the snsutton transcription of the official PDF**, so likely a BGA/house rule); the counter-attack must be paid by the current player alone (sites saying "next player continues discarding" are wrong — RMWinslow's summary contains exactly that erroneous variant).
- Other complete-ish implementations (no license unless noted): **ayrat555/regicide** (Rust TUI, solo + multi, save/continue, 2026-07), **str4nge-m4g1c/kingslayer** (Rust Ratatui TUI, **GPL-3.0**), **dhryniewicz/regicide-cli** (Clojure, **MIT**, solo/hot-seat/online), **kritzmurf/Kill-The-Kings** (Rust, MIT), **MGibson1/regicide_gleam** (Gleam, on hex.pm as `regicide@1`), **cbrown4652/regicide-go** (Go, MIT, 2024), **QuicheSama/regicide** (MIT, 2021, empty-ish), **wedk/regicide** (vanilla TS solo, MIT, live at wedk.github.io/regicide), **john-carlo-flores/pixelcide** (React+Express+Socket.io+Postgres multiplayer, NES.css look, 4 stars, no license), **jonathonthill/1789** (Régicide rethemed to the French Revolution with public-domain period paintings for the 12 royals; solo + 2–4 via 4-letter "salon" codes; no license), **W-Hodgson/web-regicide**, **SoupeWonton/regicide-web** (Vue multiplayer beta), **manzzaano/Regicide** (Spring Boot + Angular + WebSocket; JavaFX branch), **cnco1221/regicide-game** (Korean, 2–4 online), **Diismas19/Regicide_online** (pygame GUI + custom client/server), **DarkPaper2022/regicideGame** (Python TCP room server, MIT), **lgutierrezgomez/regicide** (Flutter web + Node/Socket.IO server-authoritative, "mobile later"), **Octacles7/Regicide** (Godot C#; adds a gold economy and hard-mode ideas — see §4), **austindingtian/regicide-clone**, **10gianluca/Regicide-Godot**, **varzival/RegicideGodot**, **lazypool/RegiBeast** (Godot roguelike adaptation), **DJackly/Regicide-Re-creation** (Unity roguelike), **u1e2k/regitate** (Godot 4 solo "card RPG" for the ANBERNIC RG Rotate 720×720 handheld with gamepad controls and difficulty settings), **3gatsunolion/heart2heart** (Discord bot; 2 solo jesters, yields-in-a-row counter), **roopesuoraniemi/regicide** (Discord embedded activity), **ar0ne/bg-server** (BGA-like Python server with Regicide), **Erebuz/regicide** (React Native stat tracker, Russian), **doulosHector/regicide-enemy-tracker** (Spanish PWA combat tracker), **Brunodrapi/Regicide-** (companion), **jchansard/regicide-helper**, **JoshUndefined/regicide-playingcards.io** (**GPL-3.0**; a `regicide-solo.pcio` playingcards.io room template), GitLab **AlanDeSmet/end-the-morachy** ("End the Monarchy" VirtualTabletop.io module, **GPL-3.0-or-later**, 2021), GitLab **michaelzinn/replicide** (PICO-8, Signalis-themed; code **MIT-No-Attribution**, graphics unlicensed/derivative; playable on the Lexaloffle BBS pid 178450; author notes the game is 1 % AI code but tests are 100 % AI-generated), GitLab **roguehashrate/regicide** (mirror of the GitHub "vibe coded" web version).
- Pure-Python solo CLIs relevant to Pythonista (all **no license** unless noted): **awweide/regicide** (compact solo engine with a plain-text CLI "easy for text-only agents", plus an Ollama LLM-agent runner that scores `10000×enemies + 100×hand value + draw-pile size − 1000×illegal moves`), **mahocitrus/Regicide.py** (**MIT**, solo CLI; adds a "secret ending": when enemy ATK is 0 and no valid moves exist the game is a defeat rather than an infinite yield loop — author says Bad Prod told them this situation is not an oversight; also forbids yielding when enemy ATK is 0 and notes the official Companion app has no solo yield at all), **fbec76/regicide**, **Et3rn1ty/terminal-regicide**, **NameError1/Regicide-Engine**, **JoNoToPo/Regicide**, **Diismas19/regicide**, **patryk-panski/regicide-game** (unittest), **w233w/Regicide** (tkinter), **pckreischer/regicide-tui**, **snsutton/regicide** (**MIT**; pygame v1 archived; has excellent `RULES.md` transcription + `CLARIFICATIONS.md`; roadmap toward Textual TUI + LAN play).
- Unrelated despite the name: thrgamon/regicide (Go regex tester), JKumarAvi/Regicide-AI (chess), Yabaisaka/Regicide (Swift health-monitor app), Bekjj/regicide (checkers), awdemos/RegicideOS, cchck/regicide (E-Card game), han-perry/Regicide (LinkedIn Queens solver), Hachounet/regicide-* (a different "Regicide" draft/placement game for 3–4), NMTMinecraftClub, BradyBrenot/chivalry-regicide, HSZemi/rr3.

### 2.4 Companion apps with difficulty options (directly relevant to "more" variants)

**Poukame/regicide-plus ("Regicide Companion Plus")** — https://github.com/Poukame/regicide-plus — React/Chakra/Vite PWA (offline), live at regicide-plus.netlify.app, no license file, 2 stars. Author built it because the **BGA implementation offers difficulty options the official Companion app lacks**. Option set (`SelectOptions.tsx`/`Types.ts`): `maxHandSize` Default/+1/+2/−1/−2; `removeJesters` Default/−1/−2; `enemyHealthBoost` 0/+5/+10/−5/−10; `enemyAttackBoost` 0/+2/+5/−2/−5; `yieldTurn` On/Off; `maxComboLimit` 10 (default)/9/8/6/4/No Combo/12/15/18; `maxAnimalCompanionLimit` K (default; i.e. Ace may pair with up to a King)/Q/J/10/…/A/Off. Also: progress-percentage score for comparing runs under harder settings, action reminders (heal/draw/perfect-kill), landscape/portrait, music by Alexander Nakarada (CC BY 4.0), SFX zapsplat, **card images generated with www.me.uk/cards/makeadeck.cgi**, jester icon from pngtree. These mirror BGA's options (unverified directly; BGA was unreachable).

---

## 3. Rules edge cases as resolved by implementations (consensus + divergences)

Official-rule text (as transcribed verbatim in snsutton/RULES.md and Chernowi/KingSlayer docs — both say "transcribed from the official rules PDF"): setup table 1/2/3/4 players → 0/0/1/2 Jesters, max hand 8/7/6/5; J/Q/K attack 10/15/20, health 20/30/40; combos 2–4 same number, total ≤ 10 ("pairs of 2s,3s,4s,5s, triple 2s and 3s, quadruple 2s"); Animal Companion = 1, pairs with one other card except Jester, two Companions may pair, same-suit pairing applies the power once; Hearts before Diamonds; "Suit powers are mandatory and cannot be skipped"; Diamonds "no penalty for failing to draw from an empty Tavern deck"; Jester attack 0, cancels immunity, skip Steps 3–4, chooser picks "any player to go next"; "If the Jester is played against a spades enemy, spades played prior to the Jester will begin reducing the attack value… however clubs played prior… will not count for double"; drawn J/Q/K count 10/15/20 and their suit power applies; yield → straight to Step 4; "A player may not yield if every other player has yielded on their last turn"; lose if a player can't cover damage, **or** "if any player is unable to play a card or yield on their turn"; solo: two Jesters set aside, 8-card hand, flip = "Discard your hand and refill to 8 cards — this does not count as drawing for the purpose of enemy diamond immunity", usable at start of Step 1 or start of Step 4, does not cancel immunity, Bronze/Silver/Gold = 2/1/0 used.

Ambiguity audit (ymonnet/regicide-pre-print-ambiguity-audit, AI-assisted, 13 findings: 4 High, 5 Medium, 4 Low) and how implementations resolve each:
1. **Hearts with fewer cards in discard than value** (audit H2): every engine moves as many as available (ch1nq `take(n)`, regi-py `refreshDiscards`, snsutton CLARIFICATIONS, HelloClaraCards test "hearts heal caps at discard size"). Adopt.
2. **Jester chooser may pick self?** (H3): ch1nq `jester_actions` lists **all** players incl. self; HelloClaraCards "chooser picks anyone"; Joat917 "可以选自己"; regi-py `getRedirectIndex` picks a *different* player (offset 1..n−1); pholser's solo stubs return self. Divergent — make it a setting (default: any player incl. self).
3. **Duration of immunity cancel** (H4): all engines: rest of that enemy's battle (`enemy.jester_applied` flag reset on next enemy).
4. **Ace + high card vs ≤10 cap** (M1): all engines allow Ace + any card (incl. 10/J/Q/K) — pairing is not a combo. Poukame exposes "max animal companion card" as a difficulty knob.
5. **Exact kill measured after Clubs doubling** (M2): consensus yes (snsutton CLARIFICATIONS example 5♣ on a 10-damaged Jack = exact).
6. **Diamonds looping past one lap** (M3): regi-py `refreshDraws` and ch1nq loop around the table repeatedly, skipping full hands, until N drawn, deck empty, or all hands full; HelloClaraCards test "a drawer hitting max hand passes remaining draws on". Adopt.
7. **Yield window** (M4): HelloClaraCards/KillTheFaceCards use a per-player "yielded on last turn" flag cleared when that player plays a card; ISMCTS/ch1nq use a consecutive-yield counter; snsutton: "only checks immediately preceding turn(s)". For 2 players: A yields → B must play → A may yield again. Solo: **no yield** in almost every implementation (Joat917, Kautiontape, pholser, HelloClaraCards, mahocitrus notes the official Companion app has no solo yield); exceptions: ch1nq allows one, mahocitrus/Regicide.py allows yield unless enemy ATK is 0.
8. **Spade floor and banked shields** (M5): floor at 0 everywhere; when effective attack is 0 the discard step is skipped (ch1nq, KillTheFaceCards test, xunserver FSM). Spades played while immune are **banked** and switched on by a Jester (ch1nq, regi-py JOKER_NERF, KillTheFaceCards, HelloClaraCards); clubs/hearts/diamonds are not retroactive. fridge-dev's refresher phrases it as "Shield value is always updated, it is just not used… while immune".
9. **Loss when nothing to play**: xunserver "empty hand and just yielded → lost"; Kautiontape "empty hand at start of play with no Jester → loss, with a Jester → not a loss"; mahocitrus "enemy ATK 0 + no valid moves → defeat (secret ending)". Solo deadlock (empty hand, enemy at 0 attack, no jesters) must be a loss or the game loops — taverna_regicide.md notes exactly this.
10. **Solo Jester refill in Step 4 while still short**: HelloClaraCards "loss if still short after last flip"; Kautiontape "Jester can fail to refill if the tavern is empty → loss"; Kautiontape also "does NOT refill hand after taking damage".
11. **Drawn royals**: J/Q/K in hand count 10/15/20 for attack and discard; their suit power applies; they cannot be in same-number combos (value > 10) but can pair with an Ace (snsutton CLARIFICATIONS). regibot stores them as distinct ranks to avoid confusing a Jack with a 10.
12. **Played cards stay on the table until the enemy dies** (so Hearts cannot recycle them) — Joat917 §六, fridge-dev.
13. **Hidden information after Hearts heal**: KingSlayer turns the remaining discard face-down so players can't deduce what went back; the rulebook says to return the discard pile face up (snsutton transcription) — treat KingSlayer's as a variant.
14. **Defend legality**: regibot requires inclusion-minimal discards (rulebook says "discard cards… with a total value at least equal"; nothing forbids over-discarding, but minimality is the only sane UI/AI constraint; pholser's "cheapest cover" = least excess then fewest cards).
15. **First player**: "most recently committed regicide" (joke); ariel-hi/who-goes-first records this verbatim with SHA-256 of the official PDF `46a7fb460b38f29e7644094267bf5bf097552258be5fdc43f35c25c123ba54be` (official URL cited there: `https://www.regicidegame.com/site_files/33132/upload_files/RegicideRulesA4.pdf?dl=1`; older URL `https://www.badgersfrommars.com/assets/RegicideRulesA4.pdf?v=2`).

---

## 4. Variant / difficulty / "more game" ideas found in the wild

- BGA-style knobs (via Poukame): hand size ±1/±2, remove 1–2 Jesters, enemy HP ±5/±10, enemy ATK ±2/±5, yield on/off, combo cap 4–18 or off, companion cap A–K or off.
- Octacles7/Regicide (Godot) **gold economy**: earn 10 gold per damage, 10 per attack reduced, 50 for a critical, 100 for reducing attack to 0, 1.5× on an ace combo, N× on an N-card combo, time bonus up to 50, 5 per card healed/drawn; spend 100 to draw, 1000 to refresh discard, 500 mulligan (only if no diamonds), 250/1000/2500/5000 for permanent +1 hand size (to 12), 500 next diamond may exceed limit, 500 next diamond draws from discard, 500 elevate face cards to top of tavern, 750 next combo may exceed cap, 1000 aces act as 14, 2000 nullify boss suit power, 2500 bank 1.25× after boss, 10000 "finisher" play whole hand. Hard-mode ideas: locked 7 hand, +5 boss HP, half spade efficiency, Joker final bosses, Aces as bosses, poker-hand "mashup" bosses.
- lyz-code/blue-book "Variations" (untested house rules): per-enemy situation modifiers rolled on a die (Disloyal, Cornered 2×level dmg/turn, Exterminator, Ambush, Spy, Necromancer, Represor, Dexterous 20%×level dodge, Quick, Stronger +2×level, Tougher +3×level, Blind, Random, Softer −3×level, Weaker, Clumsy, Resistance Spies remove immunity, Enemy Cornered, Loyal) with level J=1/Q=2/K=3; player suit affinity (+level on own suit, −level on opposite: ♠↔♥, ♣↔♦); player classes stub.
- Kautiontape: daily seeded challenge + share text; forecasting UI; tutorial; undo/history.
- regi-py: Easy/Medium/Hard **preset opening deals** per player count (5 each) and net-guided hint bots.
- Legacy campaign content (§2.2) is the richest source of "more" — new suits, relics, bosses, shop.

---

## 5. Strategy / solver analyses found

- **No committed quantitative win-rate tables exist in any repo** (ch1nq, regi-py, pholser, KingSlayer, RemiZheng1 all generate CSVs locally; none checked in). BGG strategy threads and BGA stats were unreachable.
- Heuristics with the most evidence behind them (converging across pholser's policy ladder, regibot's rollout policy, mahocitrus' AI doc, Joat917/BGA tips, sdjmchattie's review):
  1. Prefer **exact kills** (royal to top of tavern) and avoid overkill; count remaining HP before playing.
  2. **Spades early** in each fight; reduce attack toward 0 (then yields/weak plays are free). Against a Clubs enemy, shield to 0 first, then "run the engine" with Hearts/Diamonds.
  3. **Diamonds enemies are the most dangerous** (no drawing); enter with a full hand; pholser's fitted model gives `enemy_is_diamonds` the largest negative weight (−0.153) among enemy-type features. Hearts enemies are described as "hard to leave alive" (immune to recycling).
  4. Hold **Diamonds** until hand value < 2× effective attack (pholser DiamondsTimingDecisions); Hearts early while the discard is small so key cards (♦/♣) cycle back.
  5. Save high Clubs for Kings; a 10♣ = 20; exact-kill the King/Queen of Clubs early and retrieve with Diamonds (K♣ in hand = 40 doubled, one-shots any King; most valuable vs K♠ which can't be shielded).
  6. Don't yield (regibot: base cost 12) except with no diamonds and a modest hand; never play the enemy's own suit if avoidable (penalty 4).
  7. Discard low-value cards first (Aces, 2–5, Hearts); keep Diamonds, Spades, combo pairs, Clubs; in solo keep Jesters as emergency refills (pholser weight +1.139 per unused Jester).
  8. Combos: always look for same-rank pairs/triples (double power + damage in one action).
- Solver designs available to copy: MCTS with UCT variants and determinization (ch1nq, Rust), ISMCTS (pinniped), PLAYER_VIEW determinized one-ply MCTS with heuristic rollouts (regibot), 8-rollout lookahead and linear value model over 21 observable features (pholser, pure Python — the most Pythonista-friendly), brute sampling / AZ-style nets (regi-py).

---

## 6. Assets, art and licensing

- **itch.io `jacoblillywhite.itch.io/regicide-assets`: NOT VERIFIED.** itch.io is blocked by the proxy; GitHub code search for "jacoblillywhite"/"lillywhite"/"regicide-assets" found zero references in any repo. I cannot report its contents or license. Flagged in Uncertainties.
- **Official rules PDF / print-and-play**: multiple repos state the publisher gives the rules away free so the game can be played with any 52-card deck + 2 jokers (lyz: "they give the rules for free"; ymonnet: "deliberately released free to the public… so anyone can play with a standard 52-card deck"; taverna: "regole pubblicate gratis… il nome è loro"). **No repo reproduces a license statement from the PDF**, and I found no evidence of an official print-and-play *card* file — only the rules sheet. "Regicide" is treated as a trademark of **Bad Prod** (mahocitrus disclaimers: "*Regicide* is a trademark of Bad Prod… No official assets are included") and the art is by **Sketchgoblin** (sketchgoblin.co.nz). Several fan projects explicitly ship *no* official art (KillTheFaceCards, Paper Crowns, Joat917 "without art (copyright issues)", austindingtian "No copyrighted assets"); Press-Play-On-Tape's Pokitto port says its graphics "were adapted from the artwork of the original game" (status of permission unknown). For a personal project: rules mechanics are not copyrightable; card art and the name/trademark are — use your own/CC assets and keep "Regicide" out of any public title (Paper Crowns' policy is a good model).
- Permissively licensed card art used by fan projects: **Caz Wolf** pixel playing-card pack from cazwolf.itch.io (terms shipped in OpenNingia/regicide-game-clone: free for non-commercial and paid projects with credit, editing allowed with credit, don't redistribute without linking the itch page); **www.me.uk/cards/makeadeck.cgi** generated decks (Poukame); **Kenney** UI/texture packs + **game-icons.net** (CuatroSeis); **AnNingUI/svg-pk** (SVG card generator) and **Lykae/cards** (own card assets) on GitHub; Unicode suit glyphs (Paper Crowns); public-domain period paintings (1789). Music: Alexander Nakarada CC BY 4.0 (Poukame).
- Code licenses recap (copyable): MIT — regi-py, KillTheFaceCards, CuatroSeis, Paper Crowns, wedk, Joat917/Regicide4, mahocitrus/Regicide.py & .ms, snsutton, cbrown4652, dhryniewicz, kritzmurf, QuicheSama, DarkPaper2022, sanjitdp, Superbladexd; Apache-2.0 — araujorenato/wizards-vs-goblins; GPL-3.0 — str4nge-m4g1c/kingslayer, JoshUndefined pcio template, AlanDeSmet (GitLab); AGPL-3.0 — mosfrompa (empty); MIT-0 — replicide code only. **No license** (all rights reserved): ch1nq (PyPI `regicide`), DorkDad141 Legacy, regibot, pholser, HelloClaraCards, Poukame, pixelcide, xunserver, ISMCTS, KingSlayer, 1789, and most others.

---

## 7. Platform notes for a Pythonista build

- PyPI `regicide` is a compiled Rust extension (wheels only for cp37–cp311 on linux/macOS/win) → unusable in Pythonista; its API shape (`state.action_space()`, `RegicideGame(players, seed).playout()`, `reward()` = enemies defeated) is a good model though.
- Pure-Python, dependency-free engines to study: pholser/regicide-python (best structured: `cards/decks/enemy/encounter/game_state/legal_moves/solo/turn_order/features/value_model/hints/benchmark`), awweide/regicide (compact, text-agent friendly), mahocitrus/Regicide.py (single file), snsutton (pygame archive + Textual demo), w233w (tkinter). None are licensed except mahocitrus (MIT) and snsutton (MIT).
- Mobile UI patterns worth copying: KillTheFaceCards (pinned bottom action bar, horizontally scrolling hand, 100dvh no-scroll), Paper Crowns (forecast before committing a play; rule hints that fade), xunserver/Not-Regicide (explicit FSM: play/defend/won/lost with FLIP_JESTER allowed in both play and defend), HelloClaraCards (pass-and-play hand-guard screen; host-authoritative redacted views).

---

## 8. Other registries

- GitLab search "regicide": roguehashrate/regicide (mirror), michaelzinn/replicide (PICO-8, 2025-11-30), AlanDeSmet/end-the-morachy (2021), Mayor-Adam/regicide (empty, 2019).
- npm search "regicide": only `regicide@1.0.5` by reggi, "A collection of one-off functions", ISC — unrelated.
- hex.pm: `regicide` (Gleam) by MGibson1.
- Lexaloffle BBS: Replicide (PICO-8) pid 178450.
- itch.io: Paper Crowns (kautiontape.itch.io/paper-crowns) confirmed via its deploy workflow; jacoblillywhite pack unverified.


UNCERTAINTIES:
- Web search was unavailable (per-turn budget exhausted before this task) and the proxy blocked badgersfrommars.com, regicidegame.com, itch.io, boardgamegeek.com, kickstarter.com, reddit, archive.org, arxiv, huggingface, codeberg. Everything about the official site, the rules PDF, BGG files/forums, BGA options and the itch.io asset pack is second-hand from GitHub mirrors/transcriptions.
- jacoblillywhite.itch.io/regicide-assets: contents, price and license are completely unverified; no GitHub project references it. Need the user (or a later session with itch.io access) to open the page and read its license text before using any art.
- Official rules PDF license: no repo reproduces a license notice from the PDF; 'free to play with a standard deck' is asserted by several third parties but the PDF's own terms were not read. No evidence found of an official print-and-play card set (only the rules sheet).
- The Regicide Legacy campaign data comes from a single unlicensed fan repo (DorkDad141/regicide-js, one commit). It could not be checked against the official Legacy rulebook; mission numbers (e.g. Myla 20/80, High Arcana 25/120, Evil Goran 20/90, Pilgrim deck 4x(2-7)+1 Ace) should be verified by the user against their physical copy.
- No repository commits numerical win-rate results; all solver/strategy repos generate stats locally. Claimed effects of heuristics are qualitative; the only fitted numbers are pholser's linear value-model coefficients (trained on an unknown number of self-play games).
- The 'mulligan if the opening hand has no Diamonds' rule appears in RMWinslow's summary and Joat917's BGA-sourced notes but not in the two verbatim transcriptions of the official PDF; likely a BGA/house rule.
- Whether the Jester player may choose themselves as next player is unresolved in the rulebook; implementations split (ch1nq/HelloClaraCards/Joat917 allow self, regi-py forces another player).
- mahocitrus claims Bad Prod confirmed by email that the 'enemy at 0 attack, no valid move' situation is not a rules oversight; unverifiable.
- Star counts, dates and test counts are as of 2026-10-13 from the GitHub API / cloned HEADs; several repos have AI-generated default branches ('claude/...') and may be low-fidelity despite high test counts.
- GitHub file reads via the MCP were restricted to the user's own repo; all file contents came from git clones, so private/unlisted branches were not inspected.

SOURCES:
- https://github.com/ch1nq/regicide
- https://pypi.org/pypi/regicide/json
- https://github.com/ahgamut/regi-py
- https://github.com/olevandermast/regibot
- https://github.com/pholser/regicide-python
- https://github.com/pinniped-9bb7d9/Regicide-ISMCTS
- https://github.com/sanjitdp/ai-madrl-regicide
- https://github.com/Chernowi/KingSlayer
- https://github.com/Chernowi/RegiSide
- https://github.com/Rabmuk/Reinforcement-Regicide
- https://github.com/RemiZheng1/Regicide
- https://github.com/kunal-kapur/regicide-rl
- https://github.com/mahocitrus/RegicideRemake
- https://github.com/mahocitrus/Regicide.py
- https://github.com/mahocitrus/Regicide.ms-unofficial
- https://github.com/DorkDad141/regicide-js
- https://github.com/Blackbol/KillTheFaceCards
- https://github.com/Kautiontape/regicide
- https://github.com/CuatroSeis/regicide-web
- https://github.com/HelloClaraCards/regicide
- https://github.com/Casc0/Not-Regicide
- https://github.com/GutuGaluppo/regicide
- https://github.com/xunserver/regicide
- https://github.com/Joat917/Regicide4
- https://github.com/Poukame/regicide-plus
- https://github.com/ymonnet/regicide-pre-print-ambiguity-audit
- https://github.com/snsutton/regicide
- https://github.com/awweide/regicide
- https://github.com/ayrat555/regicide
- https://github.com/str4nge-m4g1c/kingslayer
- https://github.com/dhryniewicz/regicide-cli
- https://github.com/kritzmurf/Kill-The-Kings
- https://github.com/MGibson1/regicide_gleam
- https://github.com/cbrown4652/regicide-go
- https://github.com/wedk/regicide
- https://github.com/john-carlo-flores/pixelcide
- https://github.com/jonathonthill/1789
- https://github.com/Octacles7/Regicide
- https://github.com/OpenNingia/regicide-game-clone
- https://github.com/JoshUndefined/regicide-playingcards.io
- https://github.com/lgutierrezgomez/regicide
- https://github.com/u1e2k/regitate
- https://github.com/3gatsunolion/heart2heart
- https://github.com/fridge-dev/regicide
- https://github.com/lyz-code/blue-book/blob/main/docs/regicide.md
- https://github.com/RMWinslow/games/blob/main/rules/othercards-regicide.md
- https://github.com/sdjmchattie/sdjmchattie.github.io/blob/main/content/posts/2026/04-25-regicide-game-review/index.md
- https://github.com/melvinzhang/garden/blob/master/content/posts/regicide.md
- https://github.com/AngeloBerardi/La-taverna-dei-giochi/blob/main/docs/rules/regicide.md
- https://github.com/ariel-hi/who-goes-first/blob/main/src/content/games/regicide-badgers-2021-en.json
- https://github.com/Press-Play-On-Tape/press-play-on-tape.github.io/blob/master/pokitto_regicide.php
- https://github.com/EllieAtWHL/myPortfolioWebsite
- https://gitlab.com/michaelzinn/replicide
- https://gitlab.com/AlanDeSmet/end-the-morachy
- https://gitlab.com/roguehashrate/regicide
- https://registry.npmjs.org/-/v1/search?text=regicide&size=50
- https://gitlab.com/api/v4/projects?search=regicide
- https://www.regicidegame.com/site_files/33132/upload_files/RegicideRulesA4.pdf (cited by repos; not fetched)
- https://www.badgersfrommars.com/assets/RegicideRulesA4.pdf (cited by repos; not fetched)
- https://jacoblillywhite.itch.io/regicide-assets (blocked; not fetched)
- https://en.doc.boardgamearena.com/Gamehelpregicide (cited by Joat917; not fetched)
- https://en.doc.boardgamearena.com/Tips_regicide (cited by Joat917; not fetched)