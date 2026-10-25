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
first; the reserve is sorted like the deck list. Settings, "Card backs": Veil (black, the
wordmark), Lattice, Crowns, Sunburst or Flat.

The table carries no running text. The status line holds the turn and, solo, the Jester
powers left (in pass and play, whose turn it is); what happened is in the game log (Menu).
A decision made with the hand (an Azure Emblem, a Chanter's discard, a cleric beast...)
names itself in one line above the hand.

Cards that cannot join the selection are greyed. A greyed card that can be played alone
starts a new selection when tapped. The solo Kinfolk Flute's stored cards stay greyed
until a set of their strength is begun (or they make a set on their own). A selected card
whose class power the enemy is immune to gets a jagged white edge and a white "!" in its
corner, and so does the enemy. While suffering, the Discard button shows the tally ("Discard 8/12"),
where cards go one at a time the rest grey out once the damage is covered, and a hand too
short to pay lights the Jester power up.

The Kinfolk Flute has a button of its own at the end of the played cards' row, solo
too (a solo player may yield, though not twice running). The cards played against the
enemy sit under the hand, above the buttons (Settings: "Played cards under the hand" puts them back above it). On a short
screen they share a row with the mission zone.

## The look

The lab is dressed after Veilwraith (Hall or Nothing): black and greys only, no hue
anywhere (colour is what that world lost). What matters is told by brightness (white: a
selection, a warning, the main action, a number that counts now), by shape (the suits and
classes) and by marks. Fog drifts behind every screen, glowing a little behind the enemy.

The enemy is the one pale card on the table, as a Veilwraith Foe card: lit from behind,
its letter dark in it, its rank and class small in the corner and the classes it is
immune to on a dark panel torn along its top. The other cards are black with a thin
edge; a selected one has a white rim and lifts; one that can't be played sinks into the
dark. A corrupted card sits in a dark sleeve with cracks over its lower face, a restored
one in a grey sleeve with a pale line inside. Counts (piles, the play order, the map's
stops) sit on small black number tiles, as Veilwraith's 1/2/3 tiles.

Buttons are black tiles with a pale frame inside: the main action has the heaviest frame
and a white title, quieter ones a dim frame, one that can't be pressed a faint one, and
the picked one of a set turns pale. The phone's own switches and segmented controls keep
their colours whatever the app asks, so on/off settings are tick boxes and choices like
the number of players are rows of tiles. Choice boxes, the info cards' text and the toast
sit on panels torn along their top, lit along the tear. The menu and the Veil card backs
carry a brushed "Regicide" wordmark; type is Iowan Old Style. Everything is drawn in code
(app/veil.py); the fog and the Foe card's light come from tools/art/make_art.py (noise,
no pictures), nothing from the game.

## Info pop-ups

Every phase of the game is told on a landscape info card that shows over the table after
the action that caused it: the strength top left, the phase's icon and title, a short
breakdown and, for a blow, a big number in the middle. A class power the enemy is immune
to shows its card greyed with a white IMMUNITY stamp. A tap anywhere moves on to the next
card, a long press skips the rest; a choice box, a handover or the result waits underneath
until the last card is gone. A fresh mission opens on its Battle start card (after the
rules card). Settings, "Info Pop Ups": the box switches them all off (the short step sounds
come back) and › lists every pop-up in groups, each with its own box; a pop-up switched off
is gone completely. Mage, Druid, Chanter and Reaver show one card before their box (what was
chosen is a line on the next card); a killing blow shows no Paladin or Guardian card. The
cards never name a card that goes into a hidden hand or the reserve. See
docs/INFO_POPUPS.md for every card.

## Sound

Sound effects for the table (card taps, plays, the class powers, hits, defeats, the
Jester...), jingles (mission start, victory, loss) and looping music for the menus and
for each stage of the castle: the Jacks, the Queens and the Kings (an enemy of another
rank, as in mission 10, goes by its strength). The sounds are made for the game with
tools/audio (see tools/audio/build.py) from real instrument recordings, the MIT-licensed
Fluid R3 and MuseScore General sample banks, and modelled table sounds; the chosen files
live in app/sounds/ (tools/audio/install.py puts the picker page's picks there). Every
info pop-up has its own tune of about 2 seconds, all in D, played as its card appears
(the Jester's is the Whistle jig); one not yet picked plays its default. Settings,
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
