# Completeness critique — Regicide / Regicide Legacy / Pythonista replica

## 0. What this pass could and could not reach

- **WebSearch**: the shared 200-call budget was already exhausted before my first query; no searches were possible this turn (a follow-up message resets it).
- **WebFetch / curl**: the proxy still returns `CONNECT 403` for badgersfrommars.com, regicidelegacy.com, rulespal.com, boardgamegeek.com, boardgamearena.com, kickstarter.com, archive.org, talkingshelfspace.com, hiewandboardgames.blogspot.com, spacebiff.com, omz-software.com, docs.python.org, youtube.com. Reachable: raw.githubusercontent.com, api.github.com (search only; issue bodies via `search_issues`), gitlab.com, pypi.org, developer.apple.com.
- Consequently every new fact below comes from GitHub-hosted material plus the local corpus under `/tmp/claude-0/-home-user-PersonalRegicide/c972a6cb-7652-5df8-b9d6-11296453c906/scratchpad/`. Items I could not verify are marked **[UNVERIFIED]**.

---

## 1. (c) Was the official rules PDF actually read? — YES, byte-verified

- Two byte-identical copies of `RegicideRulesA4.pdf` are on disk: `scratchpad/verify_pdf/rules_2e32e4.pdf` and `rules_e00a01.pdf`, SHA-256 `46a7fb460b38f29e7644094267bf5bf097552258be5fdc43f35c25c123ba54be` = the hash the `who-goes-first` project recorded for the publisher URL. `pdfinfo`: Adobe InDesign 16.4, created **2021-10-19 20:29:43 UTC**, 2 pages — i.e. the "19 Oct 2021, final rules incl. solo" revision.
- Full text dump: `scratchpad/verify_pdf/layout.txt` (`pdftotext -layout`, 22,317 bytes). I re-read it end to end; every rule sentence quoted in the reports is present verbatim (setup table 1/2/3/4 → 0/0/1/2 Jesters, hand 8/7/6/5; J/Q/K 10/20, 15/30, 20/40; Hearts/Diamonds/Clubs/Spades text; immunity; Jester incl. the spades-retro/clubs-not-retro clause; combos; yielding; game end; solo; "Drawing a defeated enemy"; communication; the "DOWNLOAD THE FREE 'REGICIDE COMPANION' APP!" footer).
- **Correction to base report §0**: `drpaj12_rules_in_text.txt` is *not* an independent transcription and must not be canonical — it inserts "(or choose randomly)" after the first-player sentence, which is not in the PDF. Use `verify_pdf/layout.txt` as the canonical text; implement first player as random/host choice and document that as an implementation fallback.
- The PDF contains **no** difficulty variants, no FAQ, no Legacy rules, no licence statement.

---

## 2. (b) Base-rule edge cases the reports disagree on — reconciled, and checked against the engine in `/home/user/PersonalRegicide/regicide/`

| # | Disputed point | Resolution (source) | What the repo does today (`regicide/engine.py`, `rules.py`, `docs/RULES_BASE.md`) |
|---|---|---|---|
| 1 | Combo "duplicate suits" (report §7 vs verdicts 1/3) | Same-number combos from one deck always have distinct suits; the "apply once" clause only matters for Ace + same-suit card. Engine should still dedupe suits as a set. | OK: `play()` builds `suits = set(...)`. `RULES_BASE.md` wording is fine. |
| 2 | Ace + 10/J/Q/K (A+K = 21) | Inferred-but-universal (BGA lists Ace pairs separately from the ≤10 combo rule). | OK: `classify_combo` returns `companion` for any 2-card set containing an Ace and no Jester; `legal_plays` includes royals. **Gap:** no `max_companion_pair_rank` knob (BGA/Companion-Plus option). Optional. |
| 3 | Exact kill measured after Clubs doubling | Yes ("dealt damage exactly equal"). | OK: `_deal_damage` compares `enemy.hp == 0` after doubling; test `test_exact_kill_with_doubling_counts_doubled_damage`. |
| 4 | Step 2 fully resolves before the Step 3 check (Diamonds draws before an exact-killed enemy lands on the Tavern; Hearts cannot heal this play's cards) | Universal inference. | OK: `_resolve_attack` runs H→D→C→S then `_deal_damage`; played cards sit in `self.plays`, not discard. **Nit:** `RULES_BASE.md` says "heals first, so the healed cards can be drawn" — healed cards go *under* the Tavern, so they are drawable only when the Tavern is shorter than the draw; reword. |
| 5 | Jester playable when immunity already cancelled (second Jester) | Legal; still skips Steps 3–4 and chooses next. | OK: `classify_combo` has no immunity precondition. |
| 6 | Turn order after a Jester choice | Continues clockwise from the *chosen* player. | OK: `choose_next` sets `active=player`; `_end_turn` advances from there. |
| 7 | Jester may choose self | Unresolved officially; engines split (CuatroSeis forbids, RegicideRL/HelloClaraCards allow). | OK: `jester_may_choose_self` (default True) + test. |
| 8 | Yield window semantics | Per-player `lastAction`, initial None = may yield; any play (incl. Jester) sets `played`; no reset on new enemy (strict). | OK: `rules.can_yield` literal; `last_action` not reset on defeat. **Gap:** no `yield_reset_per_enemy` toggle (multiplayr behaviour). Optional. |
| 9 | Solo yield | Not allowed (vacuous reading + BGA "A player may not Yield in solo"; RegicideRL, multiplayr, pholser, HelloClaraCards, 1789 agree; ayrat555/AleDM1/CuatroSeis allow). | OK: vacuous truth in `can_yield`; message "You cannot yield in a solo game." **Gap:** no `solo_can_yield` opt-in toggle. Optional. |
| 10 | Step 4 when effective attack is 0 | No discard offered; turn passes. | OK: `_enter_suffer` ends the turn when `pending_damage <= 0`; test `test_zero_damage_turn_passes_automatically`. |
| 11 | Over-paying / surplus discards | Allowed by "at least"; strict-minimal is a possible variant. | OK (allowed); **Gap:** no `strict_minimal_discard` toggle. Optional. |
| 12 | Hearts shortfall / empty discard | min(N, |discard|); empty → no-op; Heart never unplayable. | OK: `_heal`. |
| 13 | Diamonds wrap-around incl. current player; stop on empty Tavern / all full; never reshuffle discard | Universal. | OK: `_draw_round_robin`. |
| 14 | Spades banked while ♠-immune, unmasked by Jester; Clubs not retro | Official. | OK: `shield` property is computed lazily from `self.plays`. |
| 15 | Loss sequencing in solo (flip before declaring loss; flips repeatable in a window; flip may draw 0) | Official windows + inference. | OK: `_check_can_act`/`_check_can_suffer` defer loss while `can_use_solo_jester()`; `use_solo_jester` draws `min(8, |tavern|)`; repeat allowed. |
| 16 | Jester recycled by Hearts | Legal (it is an ordinary discard card). | OK: defeated plays incl. Jester go to `discard`. |
| 17 | First player | PDF: "most recently committed regicide" only. | `RULES_BASE.md` says "Any player may start" — fine as fallback; cite the PDF sentence. |
| 18 | BGA option list | Only hand-size / enemy-health / enemy-attack modifiers behind a "modifications" switch are evidenced (scraper DOM ids 100/101/103/104; 102 unknown). Combo cap / companion cap / yield-off / Jester-count exist only in the fan Companion-Plus app. | Repo exposes `hand_size`, `jesters` overrides only. Label anything else "unofficial". |

**Base-rule conclusion:** no blocking disagreement remains; the engine matches the verified spec. The only open items are three optional toggles (`yield_reset_per_enemy`, `solo_can_yield`, `strict_minimal_discard`) and one doc nit.

---

## 3. (d) Solo-mode rules — fully verified

Verbatim from the PDF (`layout.txt`, "SOLO PLAY"): set the two Jesters aside; single hand of 8; "A Jester can be flipped to activate the following power: 'Discard your hand and refill to 8 cards - this does not count as drawing for the purpose of enemy diamond immunity.' Since you have two Jesters this can be done twice per game. Flipping the Jesters in this way does not cancel enemy immunity. You are allowed to use the Jester power a) at the start of Step 1 before you play a card or b) at the start of Step 4 before you have to take damage." Bronze/Silver/Gold = 2/1/0 Jesters used.

BGA's licensed help page (local mirror `scratchpad/dl2/bga-help-zh-main/file`, English body) adds: "A player may not Yield in solo", and the loss wording "unable to play a card when the player cannot yield (because all the other players have yielded or in solo mode)".

Inferred, not in any source: Tavern < 8 → draw what exists; flips may be repeated in the same window; flip legal even if it draws 0 or attack is already 0. The engine implements all of this (tests `test_solo_*`, `test_empty_hand_no_jester_loses_solo`, `test_cannot_pay_but_solo_jester_available_keeps_playing`).

**Still unverified for solo:** (i) the official *Companion app* solo mode's rule modifiers and whether it allows yielding (one fan author says it does not) — needs the user to open the app; (ii) **Regicide Legacy solo** (Jester "played as an attack on its own, strength 8, choose one of the four basic classes, ignores immunity, twice per attempt, flipped face-down when the enemy is defeated") is known only from a rulespal search snippet [UNVERIFIED]; (iii) whether Legacy solo may yield — the fan engine lets solo yield unless the previous action was a yield ("cannot yield twice in a row", reset on each play and on a new enemy), which contradicts the base rule the repo applies in Legacy mode. Flag `VERIFY` in `legacy_rules.py`.

---

## 4. (a) Regicide Legacy — what is public but not captured, and what is wrong

### 4.1 No further public source exists on reachable hosts
GitHub code search for "Kinfolk Flute", "Scarlet Whistle", "Azure Emblem", "Evergreen Mother", "regicidelegacy.com", "feign death" + regicide, "Form an Attack", "Reserve deck", "Golden Blade Syndicate", "Deccaria", and the printed mission titles returns **0 results**; repository search for "regicide legacy" returns only `DorkDad141/regicide-js`. GitLab has nothing. So the only machine-readable Legacy content is that one fan repo; everything else (rulebook on BGG Files by JediLuke, the regicidelegacy.com compendium, the Talking Shelf Space repack guide, Hiew's photo book, the "Mission 6 Rules Changes" file, the Optimal Play videos) is behind the blocked hosts and must be read by the user or by a run with those hosts allow-listed.

### 4.2 Details present in the fan **source code** that the reports and `docs/LEGACY_CAMPAIGN.md` did not capture (all **[F] fan-sourced**, but the author owned the game)
- **Mercenary shop** (`src/stores/game.ts` `initShop`): `12♠/12♥/12♦/12♣` cost **1** each (max 1 each); `2/5♥/♦/♣/♠` cost **1** each (max 1 each); `19` cost **3** (max 2); "Any-suit Ace" cost **3** (max 2); extra **Jester** cost **5** (max 2). Coins: after each loss `missionCoins += missionLosses` (the n-th loss on a mission grants n coins); re-entering a mission with k prior losses gives `k(k+1)/2` coins in total (so coins accumulate across attempts; purchases are re-made each attempt). **The repo's `regicide/campaign/mercenaries.py` placeholders (12→3, 2/5→1, 19→4, Ace→1, Jester→2) differ from the fan values; the fan values are the better guess** — swap them and keep the "unverified" tag.
- **Corruption selection** (`campaign.ts` `selectRandomCorruption`): ranks 2–9 only, never repeat a rank, at most 2 per suit, and **rank 6 must be ♣ (Esme) with one ♣ slot reserved until the 6♣ is corrupted** — i.e. the fan author knew the story-driven corruption targets include Esme (6♣). The repo's rule ("never the same suit more than twice") misses the Esme constraint.
- **Dual-class enemies**: Hydras (M2), Trolls and Wyverns (M8) use **all six C(4,2) pairs of basic classes**, one each (`buildHydraCastle`, `buildTrollCastle`).
- **M3 boss name** is "Dean" in `missionSetup.ts` (the prose says "Grand Wizard"); M11 minions are "Minion" (10/30, no class).
- **M9 end-of-turn option (a)** sends the captured pile's top card to the **discard**, not the hand (`resolveMission9EndOfTurnBanish`); perfect kill sends a pile top to the Tavern top.
- **M8** attack bonus = total **value** of non-pilgrim zone cards (`getMissionAttackBonus`), and pilgrim matching applies in M7 **and M8** (`matchPilgrims`). The placing-a-10 bonus's "choose discard cards to banish + shuffle rest under the Tavern" is **not implemented** in the fan code (comment says "handled by a follow-up UI step") — treat that sub-rule as doubly unverified.
- **M10** enemy abilities: ♣ doubles the *total* (base + zone) attack; ♠ reduces **all incoming damage** by the enemy's base value (`getM10SpadeReduction`); ♥ end-of-turn top discard → zone; ♦ end-of-turn you choose a hand card → zone.
- **M5** perfect kill: carry-over = defeated enemy's **base attack** (10/15), applied before your next turn; the in-app description ("excess damage carries over") is wrong — trust the code.
- **M6**: Guardian flag is reset at the start of each play and after defeat; mission-zone damage is "standard suffer-damage" and must be survived even on the final enemy.
- **Interactive class abilities as actually coded** (`suitpower.ts` + store): order Mages → Druids → Hearts → Diamonds → Drums → Clubs → Reavers → Spades → Guardians (note: the code array lists Spades/Guardians before Clubs/Reavers, but Clubs/Reavers only change damage, so the effective order for N is as the README states). **N for every ability = the combo's running damage value at that point** (so Reavers see the Clubs-doubled value). Mage: reveal `min(N, |tavern|)`, pick 1 (its classes merge into the combo; corrupted/restored on-play effects fire; a picked Mage chains with N = its value; Azure Emblem lets you keep one of the rest on top of the Tavern). Druid: with ≥4 discard cards you must assign exactly one card each to hand / Tavern top / Tavern bottom / banish and the rest back to the discard in your order; with <4 cards every card must go to a zone. Drums: player chooses how many (≤ N, ≤ |tavern|) to draw **past the hand limit**, then discards down to the limit. Reaver: player chooses a reveal count (1..|tavern|, presumably ≤ N), all revealed are banished, damage = **(current + kept value) × 2**; empty Tavern → ×2 immediately. Guardian: no damage this turn. Spades are banked with a separate "bypass" counter so M3/M11/M12 dynamic immunity can recalculate the shield.
- **Beast**: value 0 alone; paired, the pair's value = partner × 2 (Beast copies partner); Beast + Beast = 0; cannot join a same-rank combo. **2/5**: resolves to the partner's rank in a combo, 2 when three or more 2/5s are played together, always **5 when discarded for damage**. **Flute**: one card per combo play, value 2–5 (2/5 counts as 2 for eligibility), all same rank, flute cards playable alone; `usedThisTurn` resets each turn.
- **Jester pool**: 2 per attempt (+ bought extras), played as **strength 8 of a chosen basic class**, bypasses immunity for that attack, consumed. This is the *solo* Legacy rule; the fan app is **solo-only (`playerCount = 1`)** — it contains no multiplayer "claim" Jester, so the repo's multiplayer claim rule rests solely on the rulespal snippet [UNVERIFIED].
- **Feign death** in the fan code = "6 or more cards discarded always satisfies" (a solo-8-hand simplification); the repo's "entire hand while at the hand limit" matches the rulebook snippet better.
- **Fan royal names** (`deck.ts`: "Squire Aethelred", "Lady Isolde", "King Vortigern"…) are **invented**, not the printed Legacy names (the only printed name known is "Letholdus the Justicar"); do not surface them as official.
- **Internal contradictions in the fan repo**: its in-app mission descriptions disagree with its engine in four places (M5 carry-over, M8 "number" vs value, M9 pile→hand vs discard, M10 "spade damage" vs all damage). `docs/LEGACY_CAMPAIGN.md` already follows the engine in all four — good; add a note saying so.

### 4.3 Still missing from every reachable source (blocking for Stages 4–6 unless the user supplies them)
1. Official class-ability text and helper-card resolution order for Mage, Reaver, Guardian, Druid, Chanter (fan calls Chanter "Drums").
2. Per-mission rules cards (exact wording, strength/health, immunities, defeat sequence, perfect-kill variant), especially M3, M5, M6 (first *and* second printing), M8 (the 10-placement cleanse), M9, M10, M12.
3. Mercenary card costs and the printed coin rule (incl. carry-over of unspent coins).
4. Reaver pack ranks (3/5/7/10 per repack guide vs 3/5/7/9 fan) and which single class card stays after each mission.
5. Pack F contents; which two extra packs ship in the Reset Box; the 4-vs-8 corrupted-sticker reconciliation.
6. Eternal mode procedure (how Location + Bane 1–23 + Boon 24–35 combine).
7. Legacy multiplayer Jester ("claim") exact text, Legacy communication rules (p.24), Legacy solo yield.
8. Mission 1 location name; Myla's "hand" cards in M9; the Evergreen Mother (Corrupted) effect (reviewer vs fan disagree).

URLs the user can open (all blocked here): `https://regicidelegacy.com/compendium/` (+ `/mission-1/`, `/mission-2/rewards`, `/mission-6/`, `/mission-7/`, `/mission-8/`, `/c/helper`), `https://www.rulespal.com/regicide-legacy/rulebook`, BGG Files for game 412963 (JediLuke rulebook spreads; "Mission 6 Rules Changes"), BGG thread 3644294 (repack guide).

---

## 5. (e) Pythonista specifics the engineer needs — verified against the official `ui` reference source (`scratchpad/dl4/pythonista/ui_master.txt`, mirror of omz-software.com/pythonista/docs/ios/ui.html) and the current stubs

**Presenting full-screen**
- Signature (docs): `View.present(style='default', animated=True, popover_location=None, hide_title_bar=False, title_bar_color=None, title_color=None, orientations=None)`; 3.3+ adds `hide_close_button=False` (Amoosekerrason stub).
- Style strings: the reference lists `'full_screen'`, `'sheet'`, `'popover'`, `'panel'`, `'sidebar'`; the same document's intro says `'fullscreen'`; both spellings are accepted in practice (258 public scripts use `'fullscreen'`, 53 use `'full_screen'`). "On the iPhone, all views are presented in full-screen." `orientations=['portrait']` etc. applies only to full-screen. With `hide_title_bar=True` the user closes with a **two-finger swipe down** or `View.close()`. The repo's `app.present("fullscreen", hide_title_bar=True, orientations=["portrait"])` is correct.
- **Status bar / safe area — not covered by any report, and there is no `ui` API for it** (issue #380 "hide_status_bar" open since 2017). Do not lay out from `ui.get_screen_size()`; size from `self.bounds` inside `layout()` (called on every resize) and inset by `self.objc_instance.safeAreaInsets()` via `objc_util` (community pattern, e.g. mikaelho/youey `wkwebview.py`: `insets.top/left/bottom/right`). Expect ~47–59 pt top and 34 pt bottom on notch/Dynamic-Island iPhones; measure on device (gate G1). `ui.get_window_size()` differs from screen size in iPad split view.
- Issues #119/#620/#638: a `frame` you set before `present('full_screen')` is not updated (use `bounds`); two old iPad reports of full-screen presenting as a sheet were closed.

**Touch handling** (docs, verbatim attributes)
- Subclass `ui.View` and define `touch_began(self, touch)`, `touch_moved(self, touch)`, `touch_ended(self, touch)`. `Touch.location` = (x, y) "in the coordinate system of the View that the touch belongs to"; `Touch.prev_location`; `Touch.phase` ∈ `'began' | 'moved' | 'stationary' | 'ended' | 'cancelled'` (handle `'cancelled'` in `touch_ended`); `Touch.touch_id` (int, stable across events); `Touch.timestamp` (ms since 1970). `View.multitouch_enabled=False` → only the first finger is delivered; `View.touch_enabled=False` for overlay labels so they do not block touches.
- **Gotcha (issue #118, still open):** a touch on a touch-enabled subview that has no touch methods bubbles up to the superview **with the subview's coordinates**. The repo's `CardView.touch_ended` handles its own touches, which avoids this; keep decorative subviews `touch_enabled=False`.
- All touch/action/delegate callbacks run on the UI thread: anything slower than a few ms goes in `@ui.in_background` (signature `in_background(fn)`); setting view attributes from that thread is fine; `console.alert` must not run on the UI thread. `ui.delay(func, seconds)` — function first. `View.wait_modal()` returns immediately when called from the UI thread.

**Drawing a rounded card** (docs)
```python
class CardView(ui.View):
    def draw(self):                       # never call directly; call self.set_needs_display()
        w, h = self.bounds.width, self.bounds.height   # bounds, not frame
        ui.set_color('#f4ecd8')
        p = ui.Path.rounded_rect(1, 1, w - 2, h - 2, 10); p.fill()
        ui.set_color('#4a3b2a'); p.line_width = 1.5; p.stroke()
        ui.draw_string('7', rect=(6, 4, w - 12, 28), font=('<system-bold>', 20),
                       color='#4a3b2a', alignment=ui.ALIGN_LEFT)
```
`Path.rounded_rect(x, y, width, height, corner_radius)` / `.rect` / `.oval`; `.fill()`, `.stroke()`, `.line_width`, `.hit_test(x, y)`, `.add_clip()`; `ui.set_color` accepts CSS names/hex, RGBA tuples or a grey float; `ui.set_shadow(color, dx, dy, blur)`; `with ui.GState():` to scope state. Pre-render faces once with `with ui.ImageContext(w, h, scale=0) as ctx: ...; img = ctx.get_image()` then `img.draw(x, y, w, h)`. Custom View subclasses default to `CONTENT_MODE_REDRAW`, so resizing redraws; `View.corner_radius` also exists for simple clipping. The repo's `app/widgets.py` already uses exactly these calls.

**Persisting JSON**
- `os.path.expanduser('~/Documents')` on Pythonista is the **local** app-group folder (`/private/var/mobile/Containers/Shared/AppGroup/<uuid>/Pythonista3/Documents`, shown as "On My iPhone ▸ Pythonista 3"). It is **not** iCloud Drive — **`PLAN.md`'s "(iCloud-backed)" is wrong**; the iCloud folder is `/private/var/mobile/Library/Mobile Documents/iCloud~com~omz-software~Pythonista3/Documents` (only exists if the user enabled iCloud for Pythonista; files there can be evicted to `.icloud` placeholders), so keep autosaves local (they are still included in the device's iCloud/iTunes backup) and offer an explicit export. `sys.platform == 'ios'` on Pythonista (corroborated by community code). Write atomically (tmp file + `os.replace`) — `app/store.py` already does this — and also save in `View.will_close()` ("good place to save data"); there is no foreground/background callback in `ui`, so save after every action.
- Version context: App Store build is 3.4 with CPython 3.10.4 (issue #746, Oct 2024, "Default interpreter 3.10.4, iOS 17.7, iPhone15,4"; #795/#800 in 2025–26 agree); 3.5 is TestFlight-only with Python 3.13. Known live bug: #793 "Latest iOS upgrade freeze" (iOS 26) → enable "Launch in Safe Mode" in iOS Settings ▸ Pythonista. #775: buttons inside a `ui.ScrollView` lose the tap highlight unless held (cosmetic).

---

## 6. Remaining unknowns, ranked by implementation impact

1. **Legacy official rule texts** (class abilities, per-mission cards, mercenary coins/costs, M6 2nd-printing, Eternal mode, Legacy Jester/feign/communication/solo-yield) — needed for Stages 4–6; only the user's box or the blocked compendium/rulebook can answer. Until then: adopt the fan engine semantics (not its prose), replace the placeholder mercenary costs with the fan values, add the Esme-6♣ corruption constraint, and keep every line `VERIFY`-tagged.
2. **Device layout facts** (safe-area insets, actual `bounds` after `present`, Pythonista version) — gate G0/G1; cannot be verified without the phone.
3. **Official Companion app** modifier list and solo-yield behaviour; **BGA** full option list (`gameoption_102`) — nice-to-have for the "difficulty knobs" stage; blocked hosts.
4. **Regicide Inferno / Crown Duels** rules — nothing beyond snippets; out of scope until the user has the rulebooks.
5. Three optional base toggles (`yield_reset_per_enemy`, `solo_can_yield`, `strict_minimal_discard`) and the `RULES_BASE.md` wording nit — cheap, non-blocking.

Sources: official PDF `scratchpad/verify_pdf/rules_2e32e4.pdf` and `layout.txt`; BGA help mirror `scratchpad/dl2/bga-help-zh-main/file`; `scratchpad/dl/gh/regicide-js/{CAMPAIGN_RULES.md,README.md,src/game/*.ts,src/stores/game.ts}`; `scratchpad/dl4/pythonista/ui_master.txt` (from https://raw.githubusercontent.com/lewdlime/pythonista-docs3/master/Documentation/py3/_sources/ios/ui.txt); https://raw.githubusercontent.com/Amoosekerrason/Pythonista.ui/master/ui_stub.pyi; GitHub code search results (iCloud path in cvpe/Pythonista-scripts, 0xDA41/pysh, booyaa/til; safeAreaInsets in mikaelho/youey); omz/Pythonista-Issues #118, #119, #380, #620, #638, #746, #775, #793 (titles/bodies via GitHub issue search); project files `/home/user/PersonalRegicide/{PLAN.md,docs/RULES_BASE.md,docs/LEGACY_CAMPAIGN.md,regicide/engine.py,regicide/rules.py,regicide/campaign/mercenaries.py,app/main.py,app/store.py,app/widgets.py,tests/test_rules_base.py}`.