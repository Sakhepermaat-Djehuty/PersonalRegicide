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

If something you tap fails, the app says so in a short message ("Hiring failed: ...")
and writes the details to `errors.log` in the saves folder; send that file along with
the report.

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
away and the table shows; letting go brings the box back. A choice of a card on the table
(a mission zone card to rescue, banish or discard, a played card to move, the top discard)
shows where the cards lie as a grid, the ones that may not be chosen dimmed: tap one, then
the button that names it (a single card comes picked). The Kinfolk Flute's box is the hand
as a grid, the cards already on the flute above it. The Chanter's and the Reaver's numbers
are chosen with − and + (hold a key to run on), a line under the number saying what it does. Settings: "Classic card faces"
lays numbered cards out like playing cards (a 7 shows seven class icons, the number and
icon in two corners, the lower half turned; royals show a big letter); cards above 10,
beasts, 2/5s, Wild Animals, Jesters and the deck list's small cards keep the simple face.

## The table

The enemy sits large in the middle of the top, drawn as a royal with the classes it is
immune to under its letter. Its attack (after the players' shield) is on the left and its
health on the right, in big numbers. While cards are selected, the numbers show what the
play would do ("→ 6" left to suffer, "→ 11" health left, "exact!" or "defeated"). A tap
left of the enemy opens the attack's card: the enemy's attack (printed, the mission's
bonus, any multiplier) beside the shield (each paladin play, or why it adds nothing), what
you suffer, and the selected play's forecast in words. A tap on the enemy opens its card:
health, immunity, the castle count (mission 10: the next enemy) and the forecast.

Under the enemy lie the piles as stacks of cards: the castle and the reserve (tavern)
face down with their count in the circle on the back, the discard and banished piles face
up with the top card showing and the count in a badge (mission 10's enemy deck is face up
too). A tap opens a pile: the castle shows every enemy of the game, the defeated ones
greyed and the one faced marked; the discard and banished piles are in order, the top card
first; the reserve is sorted like the deck list. Settings, "Card backs": Lattice, Crowns,
Sunburst or Flat.

The table carries no running text. The status line holds the turn and, solo, the Jester
powers left (in pass and play, whose turn it is); what happened is in the game log (Menu).
A decision made with the hand (an Azure Emblem, a Chanter's discard, a cleric beast...)
names itself in one line above the hand.

Cards that cannot join the selection are greyed. A greyed card that can be played alone
starts a new selection when tapped. The solo Kinfolk Flute's stored cards stay greyed
until a set of their strength is begun (or they make a set on their own). A selected card
whose class power the enemy is immune to gets a red edge and a "!" in its corner, and so
does the enemy. While suffering, the Discard button shows the tally ("Discard 8/12"),
where cards go one at a time the rest grey out once the damage is covered, and a hand too
short to pay lights the Jester power up.

The Kinfolk Flute has a button of its own at the end of the played cards' row, solo
too (a solo player may yield, though not twice running). The cards played against the
enemy sit under the hand, above the buttons (Settings: "Played cards under the hand" puts them back above it). On a short
screen they share a row with the mission zone.

## Sound

Sound effects for the table (card taps, plays, the class powers, hits, defeats, the
Jester...), jingles (mission start, victory, loss) and looping music for the menus and
for each stage of the castle: the Jacks, the Queens and the Kings (an enemy of another
rank, as in mission 10, goes by its strength). The sounds are made for the game with
tools/audio (see tools/audio/build.py) from real instrument recordings, the MIT-licensed
Fluid R3 and MuseScore General sample banks, and modelled table sounds; the chosen files
live in app/sounds/. Settings,
"Sound": sound effects, music, and "Play sound when the phone is on silent" (on by
default; off honours the ring/silent switch).

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
