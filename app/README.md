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
Game menu: Next mission / Retry mission / Continue attempt, Mission rules, Deck list, Map,
Progress, Lore (this game). Deck list: the relics as a row of cards (a tap opens the
relic's card), the hired mercenaries and the Mercenary camp, Gøran's four beasts (a tap
chooses the one the next attempt takes, shown with the gold selection border), the party.
Mercenary camp: every mercenary as a card, shaded while it waits in the box, its cost as
gold coins down the right side; a tap opens its card to hire it or, after a failure, swap
it. Card pop-ups (a relic, a mercenary, a reward, the rules card) are drawn like the
game's playing cards: name and icon on top, the text below. A mission's rules card pops up
the first time it loads (Settings can turn that off) and is in the in-game Menu and the
game menu too. In a game, a tap on the status line ("Reserve 54 · Discard 17"), or
"Discard and reserve piles" in the in-game Menu, shows the piles: the discard pile and the
banished pile in order (the top card first) and the reserve deck sorted like the deck list
(what is left, never its order). Every choice box has "Hold to view game": while it is held the box fades
away and the table shows; letting go brings the box back. Settings: "Classic card faces"
lays numbered cards out like playing cards (a 7 shows seven class icons, the number and
icon in two corners, the lower half turned; royals show a big letter); cards above 10,
beasts, 2/5s, Wild Animals, Jesters and the deck list's small cards keep the simple face.

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
