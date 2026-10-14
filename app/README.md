# Running on the phone (Pythonista 3)

1. In Pythonista, create a new empty script, paste the contents of `app/bootstrap.py`
   into it and run it. It downloads this repository and installs it at
   `~/Documents/PersonalRegicide`.
2. Open `PersonalRegicide/app/main.py` and run it. The game presents fullscreen; use
   the in-game Quit button to leave.
3. Updating: run the bootstrap script again. Saves and settings are in
   `~/Documents/PersonalRegicide-saves`, which the installer never touches.

Home-screen icon: in Pythonista's script menu use "Shortcuts" → "Home Screen" for
`app/main.py` (or add a Shortcuts-app action that runs the script).

Requirements: Pythonista 3.4 or newer (Python 3.10). Only the `ui` and `console`
modules are used.

## Menus

Main menu: Continue (last game), Load game (save slots), New game, Quick play (base
Regicide solo or pass-and-play), Lore (across all games), Settings, Rules, Quit.
Game menu: Next mission / Retry mission / Continue attempt, Mercenary camp, Mission rules,
Deck list (relics with what they do, hired mercenaries, the attempt's beast, the party),
Map, Progress, Lore (this game). A mission's rules card pops up the first time it loads
(Settings can turn that off) and is in the in-game Menu too.

## What the client offers

Solo and pass-and-play Regicide with full rules enforcement, play forecasts, suggested
discards, undo, autosave, history and medals; the whole Legacy campaign (missions 1–12)
with the party, mercenary camp, relics and a mission list that reveals missions as you
reach them, then Evergreen missions from the game menu once the campaign is won.

Story text: the app ships without the cards' story text. To read it in the Lore screens,
import your private `lore_private.json` into Pythonista (it lands in Pythonista's
Documents folder or its Inbox); the app finds it there and copies it into
`~/Documents/PersonalRegicide-saves/`, which updates never touch.

## Desktop preview

The same code runs headlessly with the stand-in in `tools/fakeui`:

    python tools/render_screens.py        # writes PNGs of every screen to tools/out/
    python -m pytest tests/test_app.py    # drives the UI through a game
