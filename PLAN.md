# PersonalRegicide — staged plan

Goal: a phone-first digital replica of Regicide and the Regicide Legacy campaign that
does more than the official companion app's solo mode: full rules enforcement for 1–4
players (solo and pass-and-play), the 12-mission campaign with persistent party, relics,
corruption and mercenaries, Eternal mode, stats, undo, bots as teammates, and honest
difficulty knobs.

Every stage ends in something playable, so there is always a working build between the
points where I need you. The gates where I need you are marked **G0–G4**.

## Decisions taken

| Question | Decision | Why |
|---|---|---|
| Runtime on the phone | **Pythonista 3** (`ui` module), engine in pure Python | It is what you use; saves live as plain JSON in Pythonista's Documents (iCloud-backed), which matters for a campaign you will play for weeks. No App Store, no hosting. |
| Alternative kept open | A browser build (PWA on GitHub Pages) later, if you want to share it with friends or play on another device | Would need the engine in the browser (Pyodide, ~10 MB) or a second engine in JS; iOS can purge web storage for rarely used sites, risky for campaign saves. |
| Engine portability | `regicide/` has no dependencies and avoids syntax newer than Python 3.8 (CI checks with `vermin`) | Pythonista 3.4 ships Python 3.10; older Pythonista 3.3 ships 3.6 and is not supported. |
| How I test the UI without an iPhone | A headless stand-in for `ui` (`tools/fakeui`) renders every screen to PNG and drives taps, so layout and flows are exercised on Linux | The first real-device run is still yours (G1). |
| Rules source of truth | `docs/RULES_BASE.md`, checked sentence by sentence against the official rulebook text | Two independent open-source engines were used as cross-checks. |
| Legacy content | `docs/LEGACY_CAMPAIGN.md`: fan transcription (DorkDad141) reconciled with the rulebook, the publisher's compendium and reviews; every unverified line is tagged VERIFY | The physical cards are definitive; the app flags unverified rules in-game until you confirm them (G2). |
| Spoilers | The app reveals a mission's rules, enemies and rewards only when you reach it (default); a setting can show everything | Keeps the legacy experience if you have not played the box yet. |

## Stage ladder

| Stage | Deliverable (always playable) | Status |
|---|---|---|
| 0 | Research, this plan, rules spec, campaign reference | done |
| 1 | **Alpha 0 — engine + console**: full base Regicide for 1–4 players, solo Jester powers and medals, legal-move enumeration, save/load, bots, text client (`python -m regicide.cli`), test suite (rule-by-rule tests, thousands of bot games checking invariants), CI on Python 3.8/3.10/3.12 | done |
| 2 | **Alpha 1 — phone UI**: Pythonista touch client for the base game (solo + pass-and-play with a hand-over screen), tap-to-select cards, forecast of a play, discard picker, Jester choice, autosave/resume, undo, game log, history, settings, one-file bootstrap installer | done |
| 3 | **Alpha 2 — campaign skeleton**: party deck with per-card classes and flags, relics, corruption, mission log and attempts, coins and mercenaries, campaign save file, progressive reveal; Missions 1–2 playable (Call to Arms, Shadow and Mist) with the Kinfolk Flute, the Arcane 25, corrupted cards, feign death and the Legacy Jester rules (claim in multiplayer, strength-8 class attack in solo) | done (content unverified, see G2) |
| 4 | **Alpha 3 — Missions 3–6**: Mage class with the interactive reveal/pick, mission zone, dynamic immunities, shield recalculation, Reavers, Guardians, Beasts, Scarlet Whistle, Azure Emblem, carry-over damage, mission-zone damage | after G2 answers where they matter, otherwise built on the transcription |
| 5 | **Alpha 4 — Missions 7–9**: Druids (discard sorting), Pilgrim deck, Chanters, ascending placement, captured piles, Evergreen Mother | same |
| 6 | **Alpha 5 — Missions 10–12 and Eternal mode**: corrupted party as enemies, Beast hunt, restored cards, final boss, Location/Bane/Boon generator | needs E-box transcription (G2) |
| 7 | **Polish**: bot teammates in solo-multiplayer, undo, animations, statistics and medals history, BGA-style difficulty modifiers, daily seeded challenge, iPad layout, optional web build | shaped by G4 |

## Where I need you

**G0 — before you first run Alpha 1 (no blocker for me):**
1. Which Pythonista version do you have (Settings → About; 3.4 or newer expected) and which iPhone (screen size)?
2. How do you like to get code onto the phone: the bootstrap script in `app/README.md`
   (downloads the repo zip from GitHub, no other apps needed), Working Copy (git), or
   iCloud Drive? I default to the bootstrap script.

**G1 — after Alpha 1 lands:** run it on the phone, send screenshots and anything that
is cramped, slow, or unclear. I render the same screens headlessly, but touch target
sizes and font rendering need a real device.

**G2 — Legacy verification (when you have the game, or by reading the official
compendium at regicidelegacy.com/compendium):** the checklist at the end of
`docs/LEGACY_CAMPAIGN.md`. The most valuable items, in order: the mercenary coin/cost
rule, the exact class-ability texts (Mage, Reaver, Guardian, Druid, Chanter) and their
resolution order, each mission's rules card (photos are ideal), the Mission 6 second
printing rules, the Eternal-mode cards. Until then those parts are built from the fan
transcription and labelled "unverified" in the app.

**G3 — a choice:** should the campaign ship with the transcribed content now (default:
yes, flagged) or should I hold each mission until you have verified it? Also: keep
progressive reveal on (default) or show everything?

**G4 — "more":** tell me which extras matter most so Stage 7 is ordered right: bot
teammates, undo, stats/medals, difficulty modifiers, daily challenge, iPad layout, a
shareable web build, Inferno/Crown Duels content later.

## What is in the build right now

* Base Regicide, 1–4 players, every official rule, in the terminal and on the phone.
* Legacy campaign: missions 1 and 2, relics (Kinfolk Flute), corruption, mercenaries
  after a loss, feign death, the Legacy Jester, campaign save, mission list with
  progressive reveal. Missions 3–12 are listed and described but not yet playable.
* Tests: 82 in `tests/`, run by GitHub Actions on Python 3.8, 3.10 and 3.12.

## Getting it onto the phone (Stage 2 deliverable)

1. In Pythonista create `bootstrap.py`, paste the contents of `app/bootstrap.py` from
   this repo, run it. It downloads the current `main` branch as a zip, unpacks it to
   `~/Documents/PersonalRegicide`, and keeps your saves in `~/Documents/PersonalRegicide-saves`
   so updates never touch them.
2. Run `PersonalRegicide/app/main.py`. Add it to the home screen via Pythonista's
   "Shortcuts" / "Home Screen" action if you like.
3. To update, run `bootstrap.py` again.

## Risks and how they are handled

* Legacy rules accuracy: fan-sourced; mitigated by G2, VERIFY tags, per-mission data
  files that are easy to edit, and an in-app "report a rule" note.
* Pythonista API drift: the UI uses only the long-stable subset (`ui.View`, `Button`,
  `Label`, `ScrollView`, `Path`, `draw_string`, `present`). The fake-ui shim documents
  exactly which calls are relied on.
* Performance: the engine previews plays by copying the state; on a phone this is well
  under a frame at base-game sizes. Legacy's larger decks stay small too.
* Copyright: no art or text from the published games; names of characters and missions
  are used as references to the physical game you own.
