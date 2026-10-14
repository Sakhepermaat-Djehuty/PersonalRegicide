# Regicide Legacy — campaign reference for the engine

> **SPOILER WARNING.** This file describes all 12 missions of Regicide Legacy, the
> relics, the corruption mechanic and the ending. If you have not played the physical
> campaign and want to keep the surprises, do not read past the first section. The app
> itself reveals a mission's rules only when you reach it.

## Where this comes from, and how much to trust it

* Regicide Legacy (Badgers From Mars, Kickstarter 2024) shipped to backers in 2026;
  retail preorders are estimated for November 2026. Reviews and playthroughs exist, and
  a copy of the rulebook is reproduced on RulesPal, but the mission cards themselves are
  not published anywhere official.
* The mission-by-mission content below is a **fan transcription**: the author of the
  open-source project `DorkDad141/regicide-js` wrote `CAMPAIGN_RULES.md` from their own
  copy while building a solo web version. It is detailed and internally consistent, but
  it is one person's reading, it was adapted for **solo** play, and in a few places the
  author notes their own simplifications. Treat every line here as "probably right,
  verify against the physical cards".
* Confirmed from the rulebook (RulesPal copy), the publisher's compendium site
  (regicidelegacy.com) and retailer listings: 12 missions, boxes opened in order; a box
  "M" (Mercenaries) opened after your first lost mission; extra packs F, C (corruption
  stickers), M, P (pilgrims) and E (Eternal mode); 42 party cards (the 40 number cards
  plus 2 Jesters) are the starting party, the "Golden Blade Syndicate"; 12 skull tokens
  (cover defeated enemies on the mission's enemy stat card); 2 metal tracker tokens on
  the central playmat's health and strength tracks.
* Where the fan repo's prose and its engine disagree (mission 5 carry-over, mission 8
  zone value, mission 9 pile card to discard, mission 10 Paladin reduction), this file
  follows the engine, which the author tested against their copy.
* Legacy vocabulary: the tavern deck is the **Reserve deck**, the castle deck is the
  **Enemy deck**, attack is **strength**, suits are **classes** with their own icons:
  Cleric (= ♥ heal), Bard (= ♦ draw), Warrior (= ♣ double), Paladin (= ♠ shield). New
  classes arrive later: Mage, Reaver, Guardian, Druid, Chanter. The engine keeps the
  letters H/D/C/S internally and shows class names in Legacy mode.
* Turn structure in Legacy: 1 Form an attack, 2 Cast spells, 3 Deal damage, 4a Suffer
  damage, 4b Enemy defeated. The rulebook warns that the order of the "enemy defeated"
  step matters in later missions, and that the communication rules changed (p.24).
* **Jester, changed in Legacy** (rulebook p.20): the Jester is played alone; then any
  player, including the one who played it, may claim it, put it on their playmat and
  take over the current turn, forming an attack from their hand as normal. The enemy
  ignores immunity only for that attack, not for later turns. VERIFY the multiplayer
  text. Solo (p.26, **confirmed by the owner, quoted**): "Twice per game, a jester can be
  played to form an attack on its own instead of playing cards from hand. When a jester
  is played move it to your personal playmat, then choose one of the four basic classes.
  It always attacks with a strength of 8 and activates the selected class ability. It
  may not be played with any other cards. This attack ignores the immunity of the enemy.
  During the enemy defeated step, remove the jester from play and flip it facedown so it
  may not be used again during this mission attempt. Although the jester is played to
  your playmat, it is never cleaned up to the discard pile (or any other zone specified
  by the mission rules). It always goes back to the side during the Enemy Defeated
  step." The engine keeps used Jesters in a set-aside zone accordingly.
* **Feign death** (official): when you are at your hand limit you may discard your
  entire hand to satisfy a strike even if its total is lower than the strength.
* Setup per mission: shuffle the party plus Jesters by player count (same table as the
  base game) into the reserve; draw to the hand limit; enemy deck grouped by strength,
  weakest group on top; set the trackers. Banished party cards return at mission end.
* The second printing rewrote Mission 6 to be easier; the compendium lets first-edition
  owners use the new rules. The owner's copy is the second edition, so the app will
  implement the second-edition Mission 6.

### What I need from you (the owner of the physical game) — see PLAN.md gate G2

When your copy arrives, the engine's open questions are listed per mission below with
the tag **VERIFY**. Answering them is a matter of reading one card each; you can send
photos of the mission rule cards and I will reconcile the data files.

---

## Player helper card (confirmed, transcribed from the owner's photo)

Front, with the stickers that were added during the campaign:

* Evergreen (p.15): a cleric, bard, warrior and paladin; ignores immunity.
* Step 1, form an attack: Jester (p.20): anyone takes over the turn, the attack ignores
  immunity. Animal Companion (p.14): play with one card, has strength 1. Beast (p.14):
  play with one card, has the strength of that card. Corruption (p.15): banish the top
  card of the reserve, ignores immunity. Restoration (p.15): heal the top card of the
  banished pile, ignores immunity.
* Step 2, cast spells, in this order: Mage (p.16): look at cards from the reserve,
  choose one to add. Druid (p.16): deal the discard pile, allocate one card each to four
  zones. Cleric (p.16): heal from the discard pile. Bard (p.16): draw cards as a team.
  Chanter (p.16): players draw a chosen number, discard to the hand limit.
* Step 3, deal damage: Reaver (p.17): banish from the reserve to add damage, then
  double. Warrior (p.17): double damage.
* Either step 4a, suffer damage: Paladin (p.18): reduce enemy strength. Guardian
  (p.18): players suffer no damage this turn. Or step 4b, enemy defeated.

Back: start-of-turn effects resolve before step 1. Step 1: play cards to your playmat
to form an attack; the attack strength is the combined strength of all cards in the
attack; or yield and play no cards. Step 2: resolve the class abilities of the
magic-using classes. Step 3: deal damage equal to the attack strength; fighter-class
abilities resolve here; move the health counter. Enemy alive: step 4a: the enemy deals
damage equal to its strength, protector-class abilities resolve here, discard cards from
hand to satisfy the damage, and if you cannot, the mission is lost; end-of-turn effects
resolve now; the next player starts their turn. Enemy defeated: step 4b: follow the
enemy-defeated step in the mission rules, clean up the played cards, turn the next enemy
face up; end-of-turn effects are skipped; the same player starts another turn.

Still needed for exact numbers: rulebook pages 14 to 18 and 20 (how many cards a Mage
looks at, which four zones a Druid uses, how a Chanter chooses, how many cards a Reaver
banishes, and the Jester claim text).

## Rulebook, pages 2–19 (confirmed, transcribed from the owner's photos)

**Party (p.5).** 42 party cards: the 40 members of the Golden Blade Syndicate (four
classes, each with characters numbered 2 to 10 plus one animal companion) and 2
Jesters. Cards added or removed by missions stay that way. Temporary cards (such as
Jesters) are added to the reserve for one attempt only and reset afterwards.

**Setting up a mission (p.7).** The enemy stat card lists the mission's enemies grouped
by strength. Shuffle the strongest group face down, then each weaker group face down on
top; turn the top card face up. Reserve = party + Jesters by player count (1/0, 2/0,
3/1, 4/2; hand limits 8/7/6/5); it is face down, may be counted but never looked at.
Draw to the hand limit. The starting player is whoever plays the first card.
**Gøran's Beasts** (rulebook box): for each attempt you may choose one of Gøran's Beasts
and include it in your reserve; after each attempt you may swap it for one of the other
three.

**Play area (p.8–9).** Relics stay in play once gained. The banished pile is face up and
may be inspected at any time (unused in mission 1). The mission zone is unused in
missions 1 and 2. The discard pile is face up and may be inspected.

**Cards (p.10–11).** Strength is both the damage and the power of the class ability.
Enemies are immune to the class abilities of cards whose class matches their icon. A
defeated enemy that reaches your hand plays like any card (its strength, its class
ability); its health is meaningless. Enemy cards never join the party.

**Turn (p.14).** Start-of-turn effects from the mission rules resolve before playing
cards; at the start of a mission they resolve before deciding who goes first. Ways to
form an attack: basic (any single card); kinfolk (any number of cards of the same
strength, total at most 10); animal (an animal companion, strength 1, with any one other
card); beast (a beast with any one other card; the beast's strength equals that card's
strength during this step and is 0 at all other times). All class abilities are
mandatory. Yielding: go straight to step 4a; not allowed if every other player yielded
on their previous turn; if you can neither yield nor play, the mission is lost.

**Special card effects (p.15).** Evergreen: cleric, bard, warrior and paladin at once,
ignoring immunity to those four. Restoration: when a restored card enters play, put the
top card of the banished pile under the reserve; its own abilities ignore immunity;
other cards in the attack do not. Corruption: when a corrupted card enters play, put the
top card of the reserve on the banished pile; its own abilities ignore immunity; other
cards in the attack do not.

**Step 2, cast spells (p.16), in rulebook order.**
* Mage: secretly look at cards from the top of the reserve equal to the attack
  strength; discard any Jesters or corrupted cards among them; choose one of the rest
  and add it to the attack (tucked underneath); put the others in the discard pile in
  any order. If the chosen card is a mage, repeat using that mage's own strength. All
  chosen cards join the attack; the other classes then resolve with the new attack
  strength. In the enemy-defeated step an attack that used a mage is banished instead
  of discarded.
* Druid: players set their hands aside; shuffle the discard pile and deal it out
  clockwise starting with the druid's player; each player picks 4 of their dealt cards
  and moves one each to the banished pile, their hand (ignoring the limit), the top of
  the reserve and the bottom of the reserve; everything else goes back to the discard
  pile, which is shuffled. The druid's strength is not used.
* Cleric: shuffle the discard pile, count out cards equal to the attack strength face
  down under the reserve, return the rest face up.
* Bard: the current player draws, then the others clockwise, one card at a time, until
  cards drawn equal the attack strength; players at the limit are skipped; no penalty
  for an empty reserve.
* Chanter: declare any number; starting with the current player and going clockwise,
  each player draws that many cards ignoring the hand limit, then discards down to the
  limit.

**Step 3, deal damage (p.17).** Attack damage starts equal to the attack strength.
Reaver: choose any number (at least one), reveal that many cards from the top of the
reserve, choose one and add its strength to the attack damage (no class powers), banish
all revealed cards in any order, then double the attack damage. Warrior: double the
attack damage (once per attack, however many warriors). A reaver and a warrior together
quadruple. Health at 0 or less: defeated.

**Step 4a, suffer damage (p.18).** The enemy strikes for its strength. Discard cards one
at a time with combined strength at least equal to the damage; you may not keep
discarding once the damage is satisfied. Animal companions count 1, Jesters 0. An empty
hand is fine. Feign death: you may always discard a full hand (you must be at the hand
limit) to satisfy any damage. Paladin: at the start of step 4a reduce the enemy's
strength by the attack strength; cumulative for all paladins played against this
enemy; lasts until it is defeated. Guardian: players suffer no damage this turn, from
enemy attacks or mission effects; it also applies in step 4b. End-of-turn effects
resolve, then the next player clockwise starts.

**Step 4b, enemy defeated (p.19).** The current player makes any decisions. 1. Follow
the mission's enemy-defeated steps, including where the enemy goes. 2. Gather all cards
played against the enemy and put them on top of the discard pile in any order you wish.
3. Turn the next enemy face up. Exact damage: the mission rules say what happens.
End-of-turn effects are skipped and the same player starts another turn.

## Rulebook, pages 20–26 (confirmed, transcribed from the owner's photos)

**Enemy immunity (p.20).** An enemy is immune to the class ability of cards matching its
class icon; their strength still counts as damage. Mage immunity: an attack containing a
mage is still banished at clean-up even when the mage ability was blocked. Enemies that
gain an immunity during a mission: gaining paladin immunity means every paladin played
against it so far stops reducing its strength (it is immune to past and future paladins);
paladins that ignore immunity (corrupted, or part of a Jester attack) keep working.
Gaining warrior immunity does not undo damage already doubled; later warriors do not
double.

**Jester, multiplayer (p.20).** The Jester is played alone in step 1 to a central spot.
Any player, including the one who played it, may claim it without talking: they put it on
their playmat, take over the current turn and form an attack from their hand. That attack
is added to the Jester and ignores the enemy's immunity, so all of its class abilities
resolve. The immunity itself is not lost for later turns, but a paladin that benefited
from the Jester keeps reducing the enemy's strength in later turns. Paladins played
before or after the Jester attack do not ignore immunity. Play then continues clockwise
from the claimer. The Jester has strength 0.

**Multi-class attacks (p.21).** All class abilities in the attack apply, in rulebook
order, each class at most once per attack. Animal companion: played alone or with any one
other card (never a Jester); strength 1; its ability applies; the same class twice counts
once; it cannot join a kinfolk attack; two companions may pair with each other. Beast:
pairs like a companion but copies the paired card's strength; alone, in hand or in the
discard pile its strength is 0. Multi-class cards: resolve every class on the card in
rulebook order; a corrupted multi-class card ignores immunity for all of its classes.

**Kinfolk (p.22).** Sets of equal strength totalling at most 10: pairs of 2 to 5, three
2s or 3s, four or five 2s. Abilities resolve at the total strength. Example: corrupted 3
of warriors with 3 of paladins: banish the top reserve card first, deal 12, reduce the
enemy's strength by 6; only the corrupted card's own class ignores immunity. Reaver
example: 5 of warriors with 5 of reavers, reveal 2, add a 7 for 17, reaver doubles to 34,
warrior doubles to 68.

**Mages (p.23).** The mage, the cards played with it and every card it added form one
attack and are banished at the enemy-defeated step. Examples: an ace with a 9 of mages
peeks at 10 cards and adds a 6 of bards for strength 16 (draw 16, deal 32). Mage into
mage: ace plus 8 of mages (strength 9) peeks at 9, chooses a 7 of mages, peeks at 7,
chooses a 3 of paladins: strength 19 (1+8+7+3). Kinfolk 3 corrupted warrior, 3 mage, 3
paladin: peek 9, add a 4 of clerics: heal 13, deal 26, reduce strength by 13.

**Relics (p.24).** Permanent once gained; kept in the relics area for the rest of the
campaign. Each relic card has two sides: one for solo play and one for two or more
players. **Communication (p.24).** Never share hand information. Public information
(piles, the enemy, the discard) may be discussed. When any player may act (the starting
player, claiming the Jester) communicate only through the speed of play.

**Mission end (p.25).** Win when the last enemy is defeated. Lose when damage cannot be
satisfied or a player can neither play nor yield. On success: reform the party; set
aside non-party cards such as Jesters; (sticker) return all mercenaries to the mercenary
box, the next mission starts with none; return the mission cards to the box; open the
reward pack in the order shown; some rewards are kept permanently, in the party or in
the box next to it. On failure: the first time, open pack M; otherwise reset the mission
as its overview card says. **Mercenaries (sticker).** Each time you lose a mission you
gain coins equal to the number of times you have lost this mission. Spend them on
mercenaries for the next attempt; the cost is top-right on the card; coins may be spent
on several mercenaries. After each failure you may swap any previously selected
mercenary with another of the same cost. **2/5 mercenaries:** declare 2 or 5 when the
card enters your playmat and keep that value while it is in play; at all other times
(mission zone, discarding, discard pile) choose 2 or 5 when the value matters. **Wild
Animal mercenaries** show four class icons: declare one class when the card enters your
playmat; at other times you decide which class it is.

**Game end (p.26).** The campaign ends after mission 12. **Solo play (p.26)** matches the
quoted text at the top of this file: play the Jester alone, choose one of the four basic
classes for it, strength 8, ignores immunity, set aside face down after the enemy is
defeated, never cleaned up to the discard pile or any mission zone.

### Mercenary persistence (p.25, confirmed by the owner)

Mercenaries hired after a failure stay for every later attempt of that mission, each
failure *adds* coins equal to the number of failures so far (1, then 2, then 3: totals
1, 3, 6, 10), unspent coins carry over, and after each failure any hired mercenary may be
swapped for another of the same cost. On success all mercenaries return to the box. The
engine implements this (`CampaignState.finish_attempt`, `hire`, `swap`) and also drops
unspent coins on success, which the sticker does not say (unverified).

### Engine work implied by pages 20–26 (tracked for Stage 4)

* A per-play "ignores immunity" flag so a Jester or corrupted paladin keeps its strength
  reduction even after the enemy gains paladin immunity; plain paladins lose theirs.
* Enemies gaining immunity mid-mission (mission rules), with the paladin recalculation.
* Legacy kinfolk: any number of equal-strength cards totalling at most 10 (no four-card
  cap, strength-based rather than rank-based so 2/5 cards work: a 2/5 joins 2s or 5s,
  see the declarations below).
* **Done:** beasts (a beast with any one other card copies that card's strength, so beast
  + 7 attacks as 14 and companion + beast as 2; alone, in hand, in the discard pile or
  the mission zone it is 0; never in a kinfolk set, never with a Jester), companions
  pairing with companions.
* Mage attacks are banished even if the mage ability was blocked.
* Interactive mid-resolution decisions: mage peek, pick and chain; druid deal and
  allocate per player; chanter declared number; reaver count and choice. These need a
  serialisable "decision pending" phase in the engine. **Done** for the mage and the
  reaver (count, then pick; the revealed cards are banished with the chosen one last,
  or in the player's order where the top of the banished pile matters, see below;
  immunity blocks the whole ability; an empty reserve only doubles; the p.22 example
  deals 68) and for the Guardian (a turn flag: no enemy damage, no mission damage, and
  no team damage in step 4b).
* **Done:** suffering damage one card at a time with no over-discarding (p.18): in
  Legacy games the cards are discarded in the order given, the total before the last one
  must be below the damage (9 then 10 for 10 damage is legal, 10 then an ace is not) and
  the last one ends on top of the discard pile; the app's Discard button follows the tap
  order and its suggestion lists the largest card last; the bots pay the same way. Team
  damage was already paid one card at a time; feign death is unchanged. The base game
  keeps accepting surplus (the strict variant stays optional).
* **Done:** order choices wherever the top card of a pile matters. "In any order" (p.19
  clean-up, p.16 a mage's unchosen cards, p.17 a reaver's revealed cards, mission 5's
  mage attack banish) becomes a question "which card ends on top?" only when two or more
  cards go together and the top of that pile counts: the discard pile in missions 4, 10
  and 11, with Evergreen banes 10, 17 or 19, and in any solo game holding the Scarlet
  Whistle (`cleanup_top`, `discard_top`); the banished pile in missions 5, 11 and 12 and
  in Evergreen setups with the Forest, the Hills or banes 18 or 20 (`banish_top`; a
  restored card that the mission 12 relic sends under the reserve is left out of it).
  Elsewhere the cards go in play order, the last on top. Legacy games move the enemy
  first and the played cards on top of it (p.19). The bots put the card that weakens the
  enemy most on top (a Jester, a classless or the weakest card), and the strongest where
  only the solo Whistle reads the pile.
* **Done:** 2/5 and Wild Animal declarations (p.25). A Wild Animal entering play (played,
  or added by a Kinfolk Flute, a Scarlet Whistle or a mage) declares a basic class
  (`declare_class`), asked first among the effects of cards entering play; it has that
  class while it is in play (an enemy immune to it blocks it) and none anywhere else. A
  2/5's strength is 2 or 5, fixed when it enters play and kept while it is in play
  (confirmed by the owner). In a kinfolk set (p.22: equal strength, total within the
  kinfolk limit, normally 10, 12 with Evergreen boon 34) it takes whichever value makes
  the set legal: 2/5 + 5 is a set of 5s (10), 2/5 + 2 (+ 2 ...) a set of 2s, and three
  2/5s can only be 2s (6) under 10; 2/5 + 2 + 5 has no common strength and 2/5 + 5 + 5
  is 15, both illegal. Every 2/5 of one set has the same value. Such a forced value is
  recorded and logged without a question. When the value is a genuine choice the player
  is asked once per attack (`declare_value`, naming the cards: "2/5♥ + 2/5♠: strength 2
  or 5?") and every 2/5 of that attack takes the answer: two 2/5s on their own (4 or 10),
  a 2/5 alone, with a companion (which adds 1) or with a beast (which copies the value),
  or a 2/5 a mage or a Scarlet Whistle adds. A 2/5 a Kinfolk Flute adds to another
  player's attack joins that set and takes its strength. The value is the card's
  strength for everything while it is in play (the attack, a beast's copy, mission 7's
  pilgrim matches, the Evergreen attack checks, the multiplayer Flute's strength). Owner's
  rulings: a 2/5 moved from play into the mission zone (missions 6 and 8, Evergreen bane
  14) counts what it was declared as for as long as it stays there; storing a 2/5 on the
  solo Kinfolk Flute is a declaration ("as a 2" or "as a 5", only the flute's strength
  when cards are already there), and it plays from the flute as that value; a 2/5 a mage
  adds is always asked, even in a set of 5s. Anywhere else out of play a 2/5 counts 2
  (a pile top's bonus to an enemy, a card entering the zone from a pile), and 5 when
  discarded to suffer damage or added by a reaver. `legal_plays` lists every 2/5
  combination once (with 2s, with 5s, 2/5s together, singles, companion and beast
  pairs). The declarations end when the next enemy appears. Forecasts assume a warrior
  and, for a free 2/5 choice, 5s (a forced value forecasts as itself); the bots pick a
  class the enemy is not immune to (a warrior when doubling could kill, else a bard when
  the hand is short, else a cleric, else a paladin) and 5 unless 2 kills exactly.
* Relics with separate solo and multiplayer sides. **Done:** Kinfolk Flute, Scarlet
  Whistle (solo: take the top discard into a solitary companion or beast attack; 2+
  players: one other player, asked clockwise, adds any card but a Jester) and Azure
  Emblem.
* **Done:** the Mage decision (peek, mandatory pick, chained mages, banished at clean-up even when immunity blocked the ability) and both sides of the Azure Emblem (solo keep after each pick; 2+ players place on the reserve once per attack, before the first peek).
* **Done:** the Druid (the shuffled discard pile is dealt out clockwise from the druid's
  player; each player with cards fills four destinations, or as many as they were dealt,
  one card each: banished, hand ignoring the limit, top and bottom of the reserve; the
  rest is shuffled back; immunity blocks it all; an empty pile does nothing; the dealt
  cards stay counted while out, across a save) and the Chanter (the attacker declares 0
  to the size of the reserve; everyone draws that many clockwise from the attacker,
  ignoring the limit; each player over the limit then discards down to it, in the same
  order; locked cards never count as discardable).
* **Done:** cards that may never leave a hand (mission 7's pilgrims): a rules hook
  (`hand_locked`) that the plays, the damage paid, feign death (the whole hand is
  needed), the hand limit (they count), team damage and every "take a card from a hand"
  effect (Flute, Whistle, Emblem, Mother, Chanter, mission 9's rescue) respect.
* **Done:** the Evergreen Mother (corrupt relic), both sides, as a decision queued when a
  corrupted card enters play and settled before the relics look at the attack (so the
  Scarlet Whistle sees the discard pile after the banish) and inside the Flute, Whistle
  and Mage flows when their additions are corrupted; the engine restores the interrupted
  decision afterwards. Solo: discard top or reserve top (reserve only when the pile is
  empty, no choice; with an empty reserve the "reserve" option stays offered and banishes
  nothing, the relic's "may"). 2+ players: the first other
  player clockwise from the corrupted card's owner with a card banishes one from hand,
  no pass; empty hands banish nothing.
* **Done:** an end-of-turn decision (`on_turn_end` may return one; mission 9) and a
  decision after the clean-up, before the next enemy is revealed (`after_cleanup`;
  mission 8's exact-kill pick), plus enemies whose immunity nothing can ignore
  (`fixed_immunity`: Myla in mission 9, for corrupted and restored cards, Evergreens and
  claimed-Jester attacks alike; such a paladin gives no shield).

## Mission 1, Call to Arms (confirmed, transcribed from the owner's photos)

**Location card:** Ostrana (town art and a QR code to the FAQ on the front; a piece of
the kingdom map on the back, labelled Ostrana).

**Enemy stats card:** Justicars 10 / 20, Queens 15 / 30, Kings 20 / 40; one of each
class (cleric, bard, warrior, paladin) per tier. Each enemy is immune to its own class.
The example enemy is Nobutada, "Paladin Justicar", strength 10, health 20.

**Mission rules card.** *Enemy defeated:* place the enemy in the discard pile. If the
enemy was dealt exact damage, place it on top of the reserve deck instead. *Example:*
Tanathil (7, elf paladin), Kazaghan (10, Deccary cleric) and River (3, halfling bard)
deal exactly 20 to Nobutada, so Nobutada goes on top of the reserve deck.
*Rules continued:* remember to reduce the enemy's strength on the strength tracker
when you play a paladin, so you know how much damage to suffer. When a player defeats
an enemy that same player must take the next turn. The QR code on the location card
leads to frequently asked questions.

**Rules summary card:** Enemy defeated: place enemy in discard pile. Exact kill (skull
icon): place enemy on top of reserve deck instead.

**Story cards:** an intro ("A corruption ravages the land ... the Syndicate ready their
weapons to fight"), an outcome ("The royal hall has lost all pretense of decorum ...")
and three reward cards. The card texts are kept out of this public repository; see the
private lore overlay described in regicide/campaign/lore.py.

**Reward cards, in order:**
1. "Open pack C and corrupt a character in your party." Random in the app (pack C
   section).
2. "Add the High Arcana to your party." The High Arcana: strength 25, subtitle "Elf
   Mage", no class icon on the card (so no class ability; to be confirmed).
3. "Acquire the new relic." Kinfolk Flute, relic, two sides. *Two or more players:*
   "After you form an attack (before proceeding to Step 2), other players may add cards
   from their hand to the attack, as long as the added cards form a valid Kinfolk Attack.
   Animal Companions may not be added this way as they cannot be a part of Kinfolk
   Attacks." *Solo relic:* "Once per turn at any time you may put a 2, 3, 4 or 5 from
   hand here as long as there are no other cards of a different strength already here.
   While forming a Kinfolk Attack you may play cards from here as though they were from
   your hand."

**Engine status:** mission 1 is marked verified. The corruption is random (pack C in a
themeless deck, see the Pack C section). The flute's
multiplayer side is implemented as the engine's first "decide" phase: after the active
player forms an attack that could be kinfolk (equal strengths, no companion, beast or
Jester) the other players are asked in clockwise order from the attacker's left; each may
add any cards of that strength from hand as long as the whole attack stays at 10 or less,
or pass; players with nothing to add are skipped. The combined attack then resolves as one
kinfolk attack (abilities at the total, corrupted newcomers banish, everything to the
discard at clean-up) and only the attacker suffers damage. The solo side is implemented
as the card says: store a 2 to 5 once per turn at any time in your turn, same strength
only, and flute cards may only be played as part of a kinfolk attack.

## Mission 2, Shadow and Mist (confirmed, transcribed from the owner's photos)

**Location card:** Umbra Cavern (cave art and a QR code; map piece on the back with a
dotted route from the north ending at a cave marked with a cross).

**Enemy stats card:** Hydra Heads 10 / 20, six of them, one for every pair of the four
classes (cleric+bard, cleric+warrior, paladin+cleric, warrior+bard, paladin+bard,
paladin+warrior). The example head is Gilgulp, "Hydra Head", strength 10, health 20,
immune to both warriors and clerics.

**Mission rules card.** Each enemy has two classes, so it is immune to the abilities of
two classes. *Enemy defeated:* if the enemy was dealt exact damage, banish it (put it in
the banished pile); if not, put it face down on the bottom of the enemy deck. You will
have to fight that enemy again later. Only exact kills will allow you to complete this
mission. *Rules continued, remember:* when you play a corrupted card (or if someone adds
one to your attack with the Kinfolk Flute), immediately put the top card of the reserve
deck into the banished pile.

**Rules summary card:** Enemy defeated: place enemy on the bottom of the enemy deck.
Exact kill (skull icon): banish enemy instead.

**Story cards:** an intro (a collapsed bridge, the Arcana's path through the Umbra
Caverns, six reptilian heads) and an outcome (Esme of the Eternal Vine, on to the
Academy); texts in the private lore overlay only.

**Reward cards, in order:**
1. "Open pack C and corrupt another character in your party." Player's choice again.
2. Class stickers: "Shuffle your party and place upside down. Reveal cards from the top
   and set aside the first Halfling (3), Avion (5), Elf (7) and Drakonid (9) you find.
   Take those four cards and apply the class stickers (on the cards not sleeves) so that
   each card has one sticker. You may not put a class sticker on a card that already has
   that class. Add the new sticker directly below the card's existing class icon." The
   card carries four stickers, one per class. (The races go by strength: 3s are
   halflings, 5s avions, 7s elves, 9s drakonids.)

No mission 2 card removes the High Arcana; the fan transcription had him leaving after
this mission. The app keeps him until a later card says otherwise.

**Engine status:** mission 2 is marked verified. The sticker reward reveals one random
3, 5, 7 and 9 from the party and the player assigns the four class stickers on a reward
screen (each class once, never a card's own class). If all four revealed cards share the
same single class no assignment is possible, so the app reshuffles and reveals again.

## Mission 3, Lessons in Flames (confirmed, transcribed from the owner's photos)

**Location card:** Magic Academy (towers under a swirling moon, QR code; map piece on the
back with the route ending at a castle marked with a cross).

**Setup card (story side, then):** "Remove the High Arcana from your party. Store the card
in mission box 3." So the High Arcana leaves at the start of mission 3, not after
mission 2.

**Enemy stats card:** Instructors 10 / 30 (four), Professors 15 / 45 (two), Dean 20 / 60
(one); every enemy is of the Mage class (flame icon), so immune to mage abilities.

**Mission rules card (front).** *End of turn:* put the top card of the reserve deck face
up into the mission zone if able. Enemies have immunity to the classes of every card in
the mission zone. *Enemy defeated:* banish the enemy (put it in the banished pile) along
with all cards in the mission zone. If the enemy was dealt exact damage, put one card
from the mission zone into the discard pile before banishing the mission zone.

**Rules continued.** *Example:* Blast (10, Artifact Instructor, mage, 30 health) with
Plates (A, animal paladin) and Pūriri (5, avion cleric) in the mission zone: Blast is
now immune to paladins and clerics. *Remember:* skip end of turn effects when you
defeat an enemy (i.e. don't put a card from the reserve deck into the mission zone).
But also remember you don't skip the end of turn effects if you yield! (The engine
already does both: yielding goes through the normal end of turn.)

**Rules summary card:** Enemies have immunity to classes in the mission zone. End of
turn: put top card of reserve deck into the mission zone. Enemy defeated: banish enemy
and cards in the mission zone. Remember to skip end of turn effects. Exact kill (skull):
discard one card from the mission zone.

**Story cards:** intro (the Academy's towers, Mānuka the honey badger, students strapped
to tables) and outcome (the Head Prefect, "that's where the Arcana went"); texts in the
private lore overlay only.

**Reward cards, in order:**
1. "Open pack C and corrupt another character in your party." Player's choice.
2. "A party member takes Tōtara aside for a chat. Open pack F." **Pack F (confirmed):**
   an F card (the Head Prefect: "We shall join you, those of us who can") reading "Add
   the 10 mages to your party": the Mage class A to 10 (flame icon); Quill, Animal Mage,
   is the ace.

**Engine status:** mission 3 is playable and its rules are marked verified. The reserve
card enters the zone at the end of every turn that is not a kill (end-of-turn effects
are skipped when an enemy is defeated, p.19), immunities follow the zone, paladins
already played stop reducing the enemy's strength when a paladin enters the zone unless
they ignore immunity (corrupted, or part of a claimed-Jester attack), the zone is
banished with the enemy, and an exact kill asks the current player which zone card to
rescue to the discard pile.

## Mission 4, Fusion of Darkness (confirmed, transcribed from the owner's photos)

**Location card:** Biology Laboratory (a glasshouse lab full of cages, QR code; map
piece on the back with the lab marked by a cross).

**Enemy stats card:** Phase I 10 / 20, Phase II 15 / 30, Phase III 20 / 40; one of each
class (cleric, bard, warrior, paladin) per phase, twelve enemies. The example enemy is
Subject 9, "Phase II Experiment", cleric, strength 15, health 30.

**Mission rules card (front).** Each enemy has additional strength equal to the strength
of the top card of the discard pile. *Enemy defeated:* place the enemy in the discard
pile. If the enemy was dealt exact damage, place it on top of the reserve deck instead.
*Example:* Subject 9 (15) with Vegarian (10, Deccari paladin) on top of the discard pile
has a total strength of 25.

**Rules continued.** *Remember:* an enemy's strength could increase or decrease during
your turn, before damage is suffered; for example a cleric shuffles the discard pile and
may change its top card. *Note:* an enemy's strength does not change while you are
suffering damage one card at a time. It may be useful to flip the strength tracker token
to track negative strength values. *Remember:* because enemies are always in corrupted
sleeves, when you play them you should follow the normal rules for corruption.

**Rules summary card:** The top of the discard adds its strength to the enemy. Enemy
defeated: place enemy in discard pile; exact kill: on top of the reserve deck instead.

**Story cards:** intro (the tower laboratory, the High Arcana's betrayal, the Evergreen
in a cage, the Arcana escapes through the window) and outcome (the Evergreen on the four
veils, the Crimson Grove in danger); texts in the private lore overlay only.

**Reward cards, in order:**
1. "Add Gøran to your party." Gøran: strength 8, "Feltrix Evergreen", no class icon.
   (A sticker card with the four class icons sits behind it: his later classes.)
2. "Keep Gøran's four beasts in the box beside your party. Each mission attempt you may
   include one of these four beasts in your reserve deck." Four beast cards, rank B, one
   per class ("Gøran's Beast"): Bonty the cleric, Cosmo the bard (a violin), Tui the
   warrior (an axe) and Lola the paladin (a shield). The app shows them as plain B
   cards, B♥ B♦ B♣ B♠, with no names (owner's choice; see "Themeless cards" below).
3. "Open pack C and corrupt another character in your party." Player's choice.
4. "Acquire the new relic." Scarlet Whistle. *Two or more players:* "After you form an
   attack with a solitary Animal Companion or Beast, one other player may add any card
   from their hand to the attack (except a Jester). This must be done before proceeding to
   Step 2." *Solo relic:* "When you form an attack with a solitary animal companion or
   beast you may take the top card of the discard pile and add it to the attack."

**Engine status:** mission 4 is playable. The enemy's strength is the printed strength
plus the strength of the top card of the discard pile, recomputed live (a cleric's
shuffle or a banish from the pile changes it) and frozen once damage is being suffered;
a Jester on top counts 0, a 2/5 counts 2, a defeated experiment its printed strength. On
a kill the experiment goes to the discard pile first (on top of the reserve on exact
damage), then the player chooses which played card ends on top of the pile (the rest go
under it; a mage attack is banished instead), as rulebook p.19 orders the steps; a
mage's unchosen cards likewise go to the pile in the order the player chooses (the
top card is asked). The
twelve experiments carry the corrupted flag, so one drawn from the reserve plays as a
corrupted card (banishes the top reserve card, its own class ignores immunity). The
rewards add Gøran, the four beasts (one may be chosen on the campaign screen for each
attempt) and the Scarlet Whistle, both sides implemented.

## Mission 5, High and Mighty (confirmed, transcribed from the owner's photos)

**Location card:** Crimson Grove (a valley of giant mushrooms, QR code; map piece on the
back with the grove marked by a cross).

**Setup cards.** Story: the Reavers, custodians of the veil, ask for help; "Add the four
Reavers to your party": Oaken (3, Halfling Reaver), Harore (5, Avion Reaver), a 7 (Elf
Reaver) and a 9 (Drakonid Reaver), all of the Reaver class (mushroom icon). Mission
rules *Setup:* put Myla (7) in a standard sleeve then place her in the banished pile.
Myla: strength 7, "Elf Pilgrim", no class icon.

**Enemy stats card:** Sporelings 10 / 40 (four, one per class) and Gloomspores 15 / 60
(four, one per class). The example enemy is Embercap, "Sporeling", warrior, 10 / 40.

**Mission rules card (front).** *End of turn:* put the top card of the banished pile
face up into the mission zone. Each enemy has additional strength equal to the combined
strength of cards in the mission zone. *Enemy defeated:* take the enemy and all cards in
the mission zone and shuffle them into the banished pile (without looking). If the enemy
was dealt exact damage, deal damage to the next enemy equal to the strength of the enemy
you just defeated.

**Rules continued.** *Remember:* during the Enemy Defeated step, for an attack
containing a mage, the current player can choose the order in which the cards are moved
to the banished pile. *Example:* Embercap (10) with Theodoric (3, halfling warrior) and
Kōwhai (5, avion bard) in the mission zone has a total strength of 18.

**Rules summary card:** Cards in the mission zone add their strength to the enemy's
strength. End of turn: put top card of the banished pile into the mission zone. Enemy
defeated: shuffle enemy and mission zone into banished pile; remember to skip end of turn
effects; exact kill: deal damage to next enemy equal to the defeated enemy's strength.

**Story cards:** intro (the Crimson Grove, Gøran leaning on Esme, the Reavers, a girl in
a sinking pit, mushrooms erupting) and outcome (Myla, the emerald ring, the Garden of
Remembrance); texts in the private lore overlay only.

**Reward cards, in order:**
1. "Add a Warrior sticker to Gøran." (Gøran becomes an 8 of warriors.)
2. "Add Myla to your party. Harore (5 Reaver) remains in your party. Remove the other
   three Reavers from your party and return them to mission box 5."
3. "Open pack C and corrupt another character in your party." Player's choice.
4. "Choose either James (6 cleric), Jakhim (6 bard) or Lee (6 paladin), then put a Reaver
   sticker on them." Player's choice; the chosen 6 gains the Reaver class.

**Open question:** "deal damage to the next enemy equal to the strength of the enemy you
just defeated". The app reads this as the enemy's strength at the moment it fell, as the
strength tracker shows it (printed strength plus the mission zone bonus, less any paladin
reductions). If the table plays it as the printed strength only, say so.

**Engine status:** mission 5 is playable. Myla starts in the banished pile; at the end
of every turn that is not a kill the top card of the banished pile (the last card
banished) goes face up into the mission zone, whose combined strength adds to the
enemy's (a beast 0, a 2/5 2, a recycled enemy its printed strength). On a kill the enemy
and the whole zone are inserted at random positions of the banished pile; on exact
damage the next enemy, once revealed, takes damage equal to the fallen enemy's strength
as the tracker showed it (printed, plus the zone, less paladin reductions, never below
0), and if that brings it to 0 or less it falls too (exactly only at 0) and the chain
continues; the same player then takes the next turn. The Reaver ability is implemented
(see above). Since the top banished card feeds the zone, the player chooses which card
ends on top whenever several are banished together: a reaver's revealed cards, and a
mage attack's cards at clean-up ("Rules continued").

## Mission 6, Shards of Memory (second edition; confirmed, transcribed from the owner's photos)

**Location card:** Garden of Remembrance (statues and stone arches, QR code; map piece
on the back with the garden marked by a cross).

**Setup cards.** "Remove Myla from your party. She will be in the mission zone for this
mission." "Add the four Guardians to your party": Runo (3, Halfling Guardian), Teko (5,
Avion Guardian), a 7 (Elf Guardian) and a 9 (Drakonid Guardian), all of the Guardian
class (broken-rock icon).

**Enemy stats card:** Guardians 15 / 30 (four statues, one per class) and Evergreens
20 / 40 (four statues, one per class).

**Mission rules card (front).** *Setup:* place Myla (7) face up into the mission zone.
*Enemy defeated:* banish the enemy. Choose one card in play (on any player's playmat)
and move it to the mission zone. If the enemy was dealt exact damage, choose any one
card from the mission zone, except Myla, and move it to the discard pile. Myla then
deals team damage to the players equal to the combined strength of cards in the mission
zone (including her strength of 7). To satisfy this damage, cards are discarded one at
a time by any player until a total strength at least equal to the damage has been
discarded. This can be done by any player in any order, without communication. If this
team damage cannot be satisfied the mission is lost.

**Rules continued.** *Notes:* if a mage is moved to the mission zone in this way, the
remaining cards in the attack are still banished as normal during the Enemy Defeated
step. *Remember:* if an attack with a Guardian defeats an enemy, players take no team
damage, as the class ability means all players take no damage for the turn. *Example:*
mission zone Myla (7), a 2 (gnome cleric), Mānuka (A, animal warrior) and River (3,
halfling bard): 13 team damage.

**Rules summary card:** Enemy defeated: banish the enemy; move one card in play into the
mission zone; exact kill: move one card, except Myla, from the mission zone to the
discard pile; players take team damage equal to the strength in the mission zone.

**Story cards:** intro (the Garden of stone and wind, the Arcana's machines, Myla's
betrayal) and outcome (the statues crumble, the cursed ring, on to the Well of Tears);
texts in the private lore overlay only.

**Reward cards, in order:**
1. "Add a Paladin sticker to Gøran."
2. "Open pack C and corrupt another character in your party." Player's choice.
3. "Acquire the new relic." Azure Emblem. *Two or more players:* "When you form an
   attack with a mage, before peeking at any cards, each other player may place one card
   from their hand on the top of the reserve deck. This power only happens once per
   attack: if you use a mage to add an additional mage to an attack, this relic power
   does not happen another time." *Solo relic:* "When resolving a mage class ability,
   after selecting a card to be added to the attack, you may put one of the other cards
   you looked at on top of the reserve deck before discarding the rest."
4. "Choose either Bronze (8 cleric), Snow (8 bard) or Shadow (8 warrior), then put a
   Guardian sticker on them." Player's choice; the chosen 8 gains the Guardian class.
5. "Runo (3 Guardian) remains in your party. Remove the other three Guardians from your
   party and return them to the mission 6 box."

**Engine status:** mission 6 is playable. Myla starts face up in the mission zone,
which grants no immunity and no strength to the enemy here. On a kill the enemy is
banished, the current player must move one card in play (any playmat; in a solo game
never the set-aside Jester) to the zone, on exact damage may then move one zone card
except Myla to the discard pile, and Myla deals team damage equal to the zone's combined
strength (her 7 included): any player discards one card at a time (its value when
discarded: a companion 1, a Jester 0, a 2/5 5) until the total is at least the damage,
in any order; the app offers a seat picker in pass-and-play (names and card counts only;
the phone is passed before a hand is shown). When nothing in play can move (a solo
Jester alone made the kill) the exact-kill rescue and the team damage happen all the
same. If every hand together
cannot pay, the mission is lost at once. A Guardian in the killing attack prevents the
team damage (the clean-up still happens). A mage moved to the zone leaves the rest of
its attack to be banished as usual. Feign death is not offered against team damage (the
rulebook ties it to a player suffering a strike).

## Mission 7, Tales of Rebirth (confirmed, transcribed from the owner's photos)

**Location card:** Well of Tears (a lake village under a great metal spider, QR code;
map piece on the back with the well marked by a cross).

**Setup card.** "Add the four Druids to your party": Tolman (3, Halfling Druid), a 5
(Avion Druid), Alantha (7, Elf Druid) and a 9 (Drakonid Druid), all of the Druid class
(red feather icon).

**Enemy stats card:** Shoal 10 / 20, Deep 15 / 30, Abyssal 20 / 40; one pondkin of each
class per tier, twelve enemies. **Enemy fronts** (photographed): all twelve pondkin sit in
plain sleeves, not corrupted ones. Shoal: Reed (cleric), a bard, a warrior and Bob
(paladin); Deep: Pearl (paladin), Sirena (cleric), Lily (warrior), Nieven (bard);
Abyssal: a paladin, Helion (bard), Ettran (cleric), Cerulea (warrior).

**Mission rules card (front).** *Setup:* open pack P. Shuffle the pilgrims and place
them in a face-down pilgrim deck in the mission zone. *Start of turn:* place a card from
the top of the pilgrim deck face up in the mission zone. When a card enters play (placed
on your playmat), if it matches the strength of a pilgrim in the mission zone, you may
banish that pilgrim (once per card). Pilgrims may never leave players' hands (for this
mission only).

**Rules continued.** *Enemy defeated:* put a number of cards from the top of the reserve
deck into the discard pile equal to the total strength of all cards in the mission zone.
Then move all cards from the mission zone to the discard pile and banish the enemy. If
the enemy was dealt exact damage you may first choose one card in the mission zone and
move it to the banished pile. *Example:* mission zone Follower (3, halfling pilgrim),
Acolyte (6, human pilgrim), Follower (3), Follower (3); two 3s are played, so two
3-strength pilgrims are banished.

**Rules summary card:** Start of turn: flip pilgrim into mission zone. Banish pilgrims
from the mission zone if they match the strength of cards you play. Pilgrims may never
leave players' hands. Enemy defeated: discard cards from the reserve equal to total
strength in the mission zone; discard mission zone and banish enemy; exact kill: banish
one card in mission zone.

**Pack P (pilgrims), confirmed by the owner:** four classless cards of every strength 2
to 7 (24 cards, each with its own name: Seeker and Traveller among the gnome 2s,
Follower 3, Servant 4, Acolyte 6, an elf 7), plus the puppy, the animal pilgrim that
mission 8 places in the mission zone.

**Story cards:** intro (the driftwood village, the metal spider, trapped pilgrims, the
pondkin) and outcome (Gøran reborn on the island, the afflicted refuse the cure, on to
Heaven's Edge); texts in the private lore overlay only.

**Reward cards, in order:**
1. "Add a Cleric sticker to Gøran."
2. "Open pack C and corrupt another character in your party." Player's choice.
3. "Alantha (7 Druid) remains in your party. Remove the other three Druids from your
   party and return them to the mission 7 box."
4. "Choose either Glamelyn (4 bard), Herbod (4 warrior) or Dhonatir (4 paladin), then
   put a Druid sticker on them." Player's choice.

**Engine status:** mission 7 is playable (`Mission7Rules`). The pilgrims form a face-down
deck (`extra["pilgrim_deck"]`); at the start of every turn, the first included and the
turn after a kill too, the top one is turned face up into the zone. Every card entering
play (the attack's cards, and cards the Flute, Whistle or a Mage add) offers to banish
one zone pilgrim of the same strength (`pilgrim_banish`, skippable, once per card: two
3s may banish two 3-pilgrims, one 6 banishes at most one of two 6s; a beast counts as its
partner's strength, p.14). Pilgrims in hand are locked: not playable, never discarded for
damage (they pay nothing), no feign death, no Flute / Whistle / Emblem / Chanter / team
damage; they still fill the hand limit, so a hand of pilgrims that cannot yield loses the
mission (p.14). Enemy defeated: on exact damage one zone card may first be banished
(`zone_banish`, optional); then cards equal to the zone's total strength go from the top
of the reserve to the discard pile (fewer if it runs out), the zone is discarded, the
enemy banished, the played cards go on top. The pondkin are plain enemies (their fronts
show plain sleeves). Decision: the pilgrim match is decided by the active player also for
cards other players add through the Flute.

## Mission 8, Winds of Chaos (confirmed, transcribed from the owner's photos)

**Location card:** Heaven's Edge (red cliffs, waterfalls, QR code; map piece on the back
with the edge marked by a cross).

**Setup card.** "Add the four Chanters to your party": Roslyn (3, Halfling Chanter), a 5
(Avion Chanter), a 7 (Elf Chanter) and Druldox (9, Drakonid Chanter), all of the
Chanter class (drum icon).

**Enemy stats card:** Trolls 10 / 20 (six, one for every pair of the four classes) and
Wyverns 25 / 50 (six, the same pairs). Each is immune to both of its classes.

**Mission rules card (front).** *Setup:* place the pilgrim puppy into the mission zone.
Open pack P and shuffle the pilgrims into the reserve deck. Each enemy has additional
strength equal to the combined strength of non-pilgrim cards in the mission zone.
*Enemy defeated:* banish the enemy. Then, from the cards in play, you may move them one
at a time to the mission zone provided each card you move has strength exactly one
higher than the highest-strength card in the mission zone (the stray puppy has strength
1). If the enemy was dealt exact damage you may place any one card from the discard pile
on top of the reserve deck.

**Rules continued.** *Mission zone filled:* when you move a 10-strength card to the
mission zone, you gain the following bonus instantly (in order): 1. place the entire
mission zone into the discard pile; 2. search through the discard pile and banish any
cards you want from it; 3. shuffle the remaining cards in the discard pile and put them
on the bottom of the reserve deck. You may no longer move cards to the mission zone.
*Example:* mission zone Puppy (A, animal pilgrim), Traveller (2, gnome pilgrim), River
(3, halfling bard), Servant (4, dwarf pilgrim): +3 enemy strength. After the enemy is
defeated, a 2, 3, then 4 are moved to the mission zone. (So pilgrims drawn from the
reserve are playable cards this mission and may be moved into the zone, where they add
nothing to the enemy.)

**Rules summary card:** Non-pilgrims in mission zone add their strength to enemy. Enemy
defeated: banish enemy; you may add cards in play to mission zone; cards must be added
in numerical order (2 to 10); exact kill: put any one card from discard pile on top of
reserve deck. Mission zone filled: when a 10 is added, discard all cards from mission
zone, banish any cards in discard pile, heal the rest.

**Pilgrim names from the card:** Puppy (A, Animal Pilgrim), Traveller (2, Gnome Pilgrim),
Follower (3, Halfling Pilgrim), Servant (4, Dwarf Pilgrim), Acolyte (6, Human Pilgrim).

**Story cards:** intro (Heaven's Edge untouched, trolls at the base, wyverns on the
horizon, Gøran: do not kill the trolls) and outcome (the corrupted got carried away,
Gøran's stolen memory of the Twinseed Temple); texts in the private lore overlay only.

**Reward cards, in order:**
1. "Add a Bard sticker to Gøran." (Gøran now has all four basic classes.)
2. "Open pack C and corrupt another character in your party." Player's choice.
3. "Druldox (9 Chanter) remains in your party. Remove the other three Chanters from your
   party and return them to the mission 8 box."
4. "Choose either Sprinkle (2 cleric), Dinky (2 warrior) or Wicket (2 paladin), then put
   a Chanter sticker on them." Player's choice.
5. "Put the puppy back in the mission 8 box."

**Open question:** nothing on these cards says where the other pilgrims go after the
mission (back into pack P, presumably, since mission 9's fan transcription shuffles them
into the reserve again). The app keeps them in the pack.

**Engine status:** mission 8 is playable (`Mission8Rules`). The puppy starts in the zone
and the 24 pilgrims are shuffled into the reserve as ordinary classless cards (playable
alone or as kinfolk, pairable with the puppy, discardable); only non-pilgrim zone cards
add their strength to the enemy. Enemy defeated: the enemy is banished; then
`zone_build` offers the cards in play whose strength is exactly one above the zone's
highest (the puppy is 1), one at a time, with Stop; a 10 fills the zone: the whole zone
goes to the discard pile, `discard_banish` lets the player banish any subset of the
pile, the rest is shuffled under the reserve, and `extra["zone_filled"]` ends the moves
for the mission. The remaining played cards are discarded as usual. Exact damage: once
the clean-up is done (the played cards are in the pile by then) `discard_pick` lets the
player put any one discard pile card on top of the reserve, or skip. Decision taken: the
card lists the exact-kill pick before the clean-up (step 1 of 4b), which would keep the
just-played cards out of reach; the app asks after the clean-up so the whole pile is
available, as requested, and notes the difference here.

## Mission 9, Hope From Ashes (confirmed, transcribed from the owner's photos)

**Location card:** Twinseed Temple (a vast tree in sunlight, QR code; map piece on the
back with the temple at the tree's roots marked by a cross).

**Enemy stats card:** Loreguards 15 / 30 (four, one per class), Lorekeepers 20 / 40
(four, one per class), then Myla 20 / 80, bard and paladin.

**Mission rules card (front).** *Setup:* set Gøran, your chosen beast and any Jesters or
mercenaries in your reserve deck aside. Shuffle the remainder of your reserve deck, deal
30 cards face down into three "captured piles" in the mission zone with 10 cards in
each, then flip over the top card of each pile. Shuffle the pilgrims and the cards you
set aside into your remaining reserve deck. *End of turn:* you may banish a card from
hand and put a card from the top of one captured pile into the discard pile, then flip
the next card in that pile face up. If you choose not to banish a card, put the top
card of each captured pile on the bottom of its pile and flip the top card of each
captured pile face up. Myla's immunity to bards and paladins can never be ignored (e.g.
via corruption and jesters).

**Rules continued.** *Enemy defeated:* banish the enemy. If you defeated the enemy with
exact damage, you may move a card from the top of one captured pile to the top of the
reserve deck, then flip the next card in that pile face up. *Remember:* skip end of turn
effects when you defeat an enemy (i.e. you can't banish a card from your hand).
*Example:* piles showing Bite (8, feltrix paladin), Duck (A, animal bard) and Eragar (9,
drakonid cleric): at end of turn the player banishes a card from hand and rescues Eragar
to the discard pile.

**Rules summary card:** Myla's immunity to paladins and bards cannot be ignored. End of
turn: you may banish a card from hand to put a captured card in the discard pile; if
you don't, put the top of all captured piles on the bottom. Enemy defeated: banish
enemy; remember to skip end of turn effects; exact kill: may put a card from a captured
pile on top of the reserve deck.

**Story cards:** intro (the Winter Wastes, the Dreamfields, the Rootmarsh; the temple
set ablaze; Myla's lorekeepers; the Syndicate cut in two) and outcome (Gøran steps on
Myla's back; her last breath; the pilgrims must depart); texts in the private lore
overlay only.

**Reward cards, in order:**
1. "Acquire the new relic." Evergreen Mother, corrupt relic. *Solo:* "Whenever a
   corrupted card enters play, if the discard pile is not empty, you may choose to
   banish a card from the top of the discard pile instead of the reserve deck." *Two or
   more players:* "Whenever a corrupted card enters play, instead of banishing a card
   from the top of the reserve deck, another player must banish a card from their hand.
   If all other players' hands are empty, do not banish any card."
2. "Remove Gøran from your party. Add the new, renewed Gøran (8, Evergreen) to your
   party." The renewed card: 8, Feltrix Evergreen, holographic, a single Evergreen icon
   (rulebook p.15: cleric, bard, warrior and paladin at once, ignoring immunity to those
   four).
3. "Choose either dwarves (4) or feltrix (8). Flip cards from your reserve until you
   reveal one of the chosen race (except Gøran or a mage) that has no stickers on them.
   Put a Mage sticker on them." Player chooses the strength; the card is random.
4. "Add Ash (B, Mage) to your party." Ash: B, Beast, Mage class, a permanent party
   member (not one of Gøran's four).

**Notes.** "No stickers" for the mage student: the app excludes cards with a class
sticker; pack C showed corruption is a sleeve, so a corrupted card may be chosen. The
outcome card says the pilgrims depart; no reward card returns pack P, so the app keeps
the pilgrims in the pack (mission 8's puppy and Evergreen boons use it again).

**Engine status:** mission 9 is playable (`Mission9Rules`). Setup: Gøran, the chosen
beast (and Ash), the Jesters and the mercenaries are set aside; the rest of the reserve is
shuffled and dealt round-robin into three captured piles of ten (`extra["captured"]`,
index 0 face up; fewer if the party is short); the pilgrims and the set-aside cards are
shuffled into the remaining reserve. End of turn (skipped on a kill): `pile_rescue`
offers, for every non-empty pile and every unlocked hand card, to banish that card and
move the pile's top card to the discard pile, or `pile_rotate` (every pile's top card to
its bottom); with an empty hand only the rotation remains, with no piles left no
question. Enemy defeated: banish the enemy; on exact damage `pile_to_reserve` may move
one pile's top card to the top of the reserve, or skip. Myla carries `fixed_immunity`:
her bard and paladin immunity holds against corrupted and restored cards, the Evergreens
and claimed-Jester attacks, and paladins played against her never shield. The Evergreen
Mother reward is implemented on both sides (see the relics bullet). The app's zone strip
shows the three pile tops with their sizes.

## Mission 10, Pride to Fall (confirmed, transcribed from the owner's photos)

**Location card:** Twinseed Temple Ruins (grey smoke under a red sky, QR code; map piece
on the back with the ruined tree marked by a cross).

**Setup card.** "Remove the corrupted characters from your party. For this mission they
will form the enemy deck."

**Enemy stats card:** eight unknown enemies: 2 / 10, 3 / 15, 4 / 20, 5 / 25, 6 / 30,
7 / 35, 8 / 40, 9 / 45. So the eight corruptions of missions 1 to 8 are one each of
strengths 2 to 9, which confirms the "never repeat a strength" rule the app uses for
corruption candidates.

**Mission rules card (front).** *Setup:* take the eight corrupted cards previously in
your party and place these face up into the enemy deck, ordered from 9 on the bottom to
2 on the top. *Start of turn:* take the top card of the reserve deck and place it into
the mission zone. Each enemy has health equal to five times their base strength. Each
enemy has additional strength equal to the combined strength of all cards in the
mission zone. *Enemy defeated:* banish all cards in the mission zone and put the enemy
in the discard pile. If the enemy was dealt exact damage, place the cards in the mission
zone in the discard pile instead.

**Rules continued.** Each enemy is immune to class powers matching its own class (as
normal), and has additional class powers: *Warrior:* has double total strength,
including additional strength from cards in the mission zone. *Paladin:* reduces the
damage you deal to this enemy by the enemy's base strength. *Cleric:* at the end of each
turn place the top card of the discard pile into the mission zone. *Bard:* at the end of
each turn the current player must put a card from their hand into the mission zone if
able. *Example:* Wicket (2, gnome paladin, corrupted) as the enemy with a 6 and Glamelyn
(4, dwarf bard) in the mission zone: the player deals 2 less damage to Wicket, then
suffers 12 damage from the enemy's strike back.

**Rules summary card:** Start of turn: put the top of the reserve into the mission
zone. Cards in the mission zone add strength to the enemy. Enemy powers: warrior has
double total strength; paladin reduces damage taken by base strength. End of turn enemy
powers: cleric puts the top card of the discard pile into the mission zone; bard puts a
card from hand into the mission zone. Enemy defeated: banish mission zone and discard
enemy; exact kill: discard mission zone instead of banishing it.

**Story cards:** intro (the fires die down, Gøran admits they need the corruption, the
High Arcana steps out of the shadows: "you brought an army right to me") and outcome
(the Syndicate subdues its corrupt members and corners the Arcana; Gøran bolts in);
texts in the private lore overlay only.

**Reward cards, in order:**
1. "Remove Gøran (8, Evergreen) from your party." The Arcana decays the floor and both
   fall into the darkness.
2. "Return the corrupted characters (the enemies from the previous mission) to your
   party." They come back still corrupted ("halted but not fully cured").

**Notes.** Defeated enemies go to the discard pile, so a corrupted character defeated
early can be drawn and played as the corrupted party card it is, with its stickers. A
corrupted card with a class sticker is a two-class enemy: immune to both classes and,
if a second class is among the four, with both powers (the app's reading).

**Engine status:** mission 10 is playable (`Mission10Rules`). The corrupted cards move
to the campaign's "away" list for the mission and return afterwards; the enemy deck is
face up, 2 on top down to 9 (the game screen's status line names the next enemy),
health five times the base strength. Start of turn: the top reserve card goes into the
zone, which adds its combined strength. Powers by class, a stickered card having both:
warrior, the total strength (base plus zone) is doubled and the paladin shields come off
afterwards (`attack_multiplier`); paladin, the damage dealt is reduced by the base
strength, an exact kill being judged after the reduction (`damage_reduction`); cleric,
at the end of the turn the top discard goes into the zone; bard, the current player must
put a hand card into the zone (`zone_feed`, no pass while the hand has an unlocked card).
Both end-of-turn powers are skipped on a kill (p.19). Enemy defeated: the zone is
banished and the enemy discarded; on exact damage the zone is discarded. A defeated
member drawn later plays as the corrupted card it is (its banish, its classes).

## Mission 11, Descent Into Darkness (confirmed, transcribed from the owner's photos)

**Location card:** Caverns of Decay (a crystal cavern with dark tendrils, QR code; map
piece on the back with the cross at the tree's roots below the ruins).

**Setup card.** "From your corrupted party members, choose one of them that has a cloak
of the Eternal Vine. Rip up the chosen card." (A green cloak is pictured.) The reward is
Esme reborn, so Esme, the 6 of warriors, is the cloaked member; which other characters
wear the cloak is not visible on the cards photographed.

**Enemy stats card:** Justicars 10 / 30 (four) and the Corrupted Evergreen 20 / 90, all
marked with a dark gem icon rather than a class icon.

**Mission rules card (front).** *Setup:* take all four of Gøran's Beasts, shuffle them
and form a face-down beast deck in the mission zone. *Start of turn:* reveal the top
card of the beast deck and do the following depending on the class revealed: warrior:
put the top card of the discard pile into the banished pile; paladin: put the top card
of the reserve deck into the discard pile; cleric: the current player puts a card from
hand into the discard pile; bard: the current player puts a card from hand into the
banished pile. After carrying out the class effect, place the revealed beast card into
a separate face-up pile in the mission zone.

**Rules continued (1).** *Note:* when starting the game, perform the first start of
turn effect (reveal a beast), then when a player decides to go first, they must carry
out the beast effect. *Remember:* you can't include any of Gøran's Beasts in your
reserve deck for this mission (but you can keep Ash in your deck since he's in your
party). *Mission success:* when you successfully complete the mission, return Gøran's
Beasts to the box by your party and you may include one of them in your reserve deck
for each mission attempt, as normal.

**Rules continued (2).** When all four beasts are in the face-up pile in the mission
zone, shuffle them and place them face down in the mission zone to reform the beast
deck. Each enemy has immunity to the classes of the cards on the top of the discard
pile and banished pile. Each enemy has additional strength equal to the combined
strength of the cards on top of the discard pile and banished pile. *Remember:* beasts
in the mission zone don't grant any immunity to the enemy. *Enemy defeated:* banish the
enemy. If the enemy was dealt exact damage, do not reveal a card from the beast deck at
the start of the next turn.

**Rules summary card:** Start of turn, reveal effect card: bard: banish a card from
hand; cleric: discard a card from hand; warrior: banish the top card of the discard
pile; paladin: discard the top card of the reserve deck. Top of discard and banished
pile grant strength and immunity to the enemy. Enemy defeated: banish enemy; exact
kill: don't reveal an effect card next turn.

**Story cards:** intro (the grand cavern, Gøran strapped to the machine, the justicars,
the shackled beasts, "Welcome to the Veil of Decay"), setup (a dozen dart to save him;
one dies, wearing the green cloak; a corrupted Evergreen lumbers towards the Syndicate)
and outcome (the machine explodes, Gøran lies dead, a radiant light, "Who is that?");
texts in the private lore overlay only.

**Reward card:** "Add the reborn Evergreen to your party." Esme: 6, Human Evergreen,
holographic, the Evergreen icon (all four basic classes, ignoring immunity, p.15).

**Open questions.** The dark gem icon on the enemies: the app treats it as no innate
class, so their immunities come only from the pile tops. Whether a player with an empty
hand simply skips the cleric or bard effect (the app assumes yes). If the top of the
discard pile is a beast or a classless card it grants strength but no immunity.

**Engine status:** mission 11 is playable (`Mission11Rules`). The four beasts form a
face-down beast deck in the zone (`extra["beast_deck"]`) with a face-up pile beside it
(`extra["beasts_out"]`; the zone strip shows the revealed beasts and the deck's count).
Every start of turn, the first one included (the app's first player is seat 0), the top
beast is revealed and applied: warrior, the top discard is banished; paladin, the top
reserve card is discarded; cleric, the current player discards a hand card
(`beast_discard`); bard, the current player banishes one (`beast_banish`); an empty hand
skips the last two. The beast then joins the face-up pile; with all four out they are
shuffled into a new deck. The enemies have no class of their own: each is immune to the
classes of the top discard and the top banished card and gains their strengths (a Jester,
a beast or a classless card grants its strength, 0 for the first two, and no immunity; a
corrupted card's own class still ignores the immunity). Enemy defeated: banished (it then
grants its strength from the top of the pile); on exact damage no beast is revealed at
the start of the next turn (`extra["skip_beast"]`, cleared after skipping). Since both
pile tops count, the player chooses which played card ends on top of the discard pile at
clean-up and which card ends on top of the banished pile when several are banished
together (a reaver's reveal, a mage attack).

## Mission 12, Decay to Growth (confirmed, transcribed from the owner's photos)

**Location card:** Throne of Corruption (a red throne under a chandelier among black
roots, QR code; the map on the back is the Caverns of Decay piece again).

**Setup cards.** "Take all the corrupted party members, remove their corrupted sleeve
and replace them with restored sleeves. These cards are no longer corrupted. Sleeve
Esme (6, Evergreen) with a restored sleeve." "Put the corrupted Evergreen Mother relic in
the mission 12 box. Acquire the new restored Evergreen Mother relic." Both sides of the
restored relic read: "Restored cards can never enter the banished pile. If they would,
instead put them on the bottom of the reserve deck."

**Enemy stats card:** Queens 15 / 30 (four, one per class), Kings 20 / 40 (four, one
per class), then the High Arcana 25 / 120 (dark gem icon, no class).

**Mission rules card (front).** *Start of turn:* place the top card of the banished
pile into the mission zone. Each enemy has additional strength equal to the combined
strength of cards in the mission zone. Each enemy has immunity to the classes of the
cards in the mission zone. *Enemy defeated:* banish all cards in the mission zone (in
any order), then banish the enemy, then banish the discard pile (without changing the
order). If the enemy was dealt exact damage, do not place the top card of the banished
pile into the mission zone at the start of the next turn.

**Rules continued (back).** *Note:* "If a corrupted card would ever enter the reserve
deck, put it on the bottom of the banished pile instead." *Remember:* "When a restored
card enters play on your playmat place the top card of the banished pile under the
reserve deck." *Example:* Edward (20, Mutated King, cleric, health 40) faces a mission
zone of Dhonatir (4, dwarf paladin), River (3, halfling bard) and Bite (8, feltrix
paladin): "Edward is immune to clerics, bards and paladins. He has strength of 35 (20 +
4 + 3 + 8)." (His own class plus the zone's classes; strength printed plus the zone.)

**Rules summary card:** Start of turn: put the top of the banished pile into the
mission zone. Cards in the mission zone grant strength and immunity to the enemy.
Corrupted cards (purple icon) can't enter the reserve: put them on the bottom of the
banished pile. Enemy defeated: banish the mission zone, the enemy and the entire discard
pile; exact kill: skip the start of turn effect next turn.

**Story cards:** intro ("How fortuitous", the underground throne room, the eight
hobbled royals), outcome (the High Arcana keels over, the Rootmarsh, a new dawn) and the
epilogue ("Many moons pass... 'I need your help.' 'Always.' Herbod grabs his axe. Open
pack E."); texts in the private lore overlay only.

**Rewards:** none for the party. "Open pack E": the campaign is complete and Eternal
mode begins.

**Notes.** The royals are corrupted (the intro and the summary's corrupted-card rule),
so a restored card's effect that would return a banished royal under the reserve sends
it to the bottom of the banished pile instead. The restored party cards each return the
top banished card under the reserve when played (rulebook p.15) and never enter the
banished pile (the relic), so the whole-discard-pile banish at each kill is the
mission's pressure.

**Engine status:** mission 12 is playable (`Mission12Rules`); the campaign is marked
complete when the High Arcana (25/120) falls, and the game menu then offers Evergreen
mode. Start of turn: the top banished card goes into the zone (skipped after an exact
kill, `extra["skip_zone"]`); the zone adds its combined strength and grants immunity to
its classes. Enemy defeated: the zone is banished in the order the player chooses
(`banish_order`, a template the player fills with the permutation; the last card ends on
top and feeds the zone next turn; the bots put the weakest or a classless card last),
then the enemy, then the whole discard pile in its order (its top ends on top), and only
then the played cards go on the new discard pile. A reaver's revealed cards and a mage
attack's cards are banished in the order the player chooses as well (the top card is
asked). The restored relic is implemented once
in the engine: every banish goes through `Game.banish_cards`, and `banish_redirect`
sends a restored card under the reserve deck instead (clean-up of a mage attack, the
zone, the discard pile, a corrupted card's effect, a reaver's reveal, a druid's slot, the
corrupt Mother's hand banish, a beast's effect). Likewise `Game.to_reserve` asks
`reserve_redirect`: in this mission a corrupted card (the royals, the Arcana) that would
enter the reserve, for instance returned by a restored card's p.15 effect, goes to the
bottom of the banished pile. The restored cards' own entry effect (top banished card
under the reserve; their abilities ignore immunity) was already in `on_cards_played`
and is tested here, as is the card's Edward example (strength 35, immune to clerics,
bards and paladins). All twelve missions are transcribed and playable.

## Themeless cards (owner's decision)

The owner plays a themeless deck: "for the same reason as not giving the reserve or
enemies names", Gøran's beasts are "plain B playing cards". The app applies the same rule
to every card the party holds. The transcriptions in this document keep the names
printed on the physical cards; the app shows none of them.

* **Plain cards, rank and class only:** Gøran's four beasts (B♥ B♦ B♣ B♠), Myla's beast
  (B★, "Ash"), the ten mages (the ace was "Quill"), the four Reavers, Guardians, Druids
  and Chanters (3, 5, 7 and 9 of their class), the 24 pilgrims and the pilgrim ace (the
  puppy), shown as "Pilgrim 4", and the mercenaries ("12 Cleric", "2/5 Bard", "19 (no
  class)", "Wild Animal (choose a class)", "Jester"). Reward texts name the cards the same
  way ("the 5 Reaver teaches a 6: the Cleric, Bard or Paladin 6 gains the Reaver class").
  Races (dwarves, feltrix and so on) are not shown either: mission 9's student choice is
  "the 4s or the 8s".
* **Still named:** the story characters the mission cards name (Gøran, Myla, Esme and the
  High Arcana) and the enemies' type names (Sporeling, Troll, Justicar and so on), as
  before.
* **Card faces:** the rank in the corner over the class pips, the pips large in the
  middle, each in its own colour (an Evergreen card shows four small ones). A classless
  card shows its rank large in the middle. The word under the pips is a story character's
  name, "pilgrim" on a pilgrim or "any class" on a Wild Animal, and nothing on a plain
  card. A 2/5 shows "2/5".
* **Sleeves (owner's choice):** a corrupted card sits in a purple sleeve and a restored
  card in a green one, drawn as a thick coloured edge around the face instead of a word.
  There is no corrupted class icon: the purple icon on mission 12's cards depicts the
  corrupted sleeve (owner). Other tags ("stuck" for a pilgrim, "flute" for a stored card,
  an order number) keep a gold band along the bottom, on small faces too.
* **The tree (owner):** the Evergreen cards, the renewed Gøran and Esme only, carry a
  small geometric tree that represents the four base classes (and they ignore immunity,
  p.15); it replaces the cleric, bard, warrior and paladin icons on their faces. Restored
  cards are marked only by their green border and keep their own classes and icons.
* **Other theme names (owner, for now):** mission titles, locations, enemy names, relics,
  class names, card types, Evergreen card titles and the story characters all stay as
  they are; the owner will decide about them later ("functioning game first").
* **Saves:** campaigns and attempts saved before the change lose these names when loaded.

## Pack C, corruption (confirmed, transcribed from the owner's photos)

**C card:** story text ("Corruption is as old as the land itself...").

**Corruption rules card.** To corrupt a card: 1. Take the race cards in this box,
shuffle them and reveal one. Set aside all characters from your party with that race.
2. Take the feature cards in this box, shuffle them and reveal one. From the characters
you set aside in 1, choose one that has the feature in their image. 3. Take the chosen
character, remove its sleeve and put it in a corrupted sleeve. This is now a corrupted
card. 4. Since the selected race and feature cards can't be used again, do not return
them to the corruption box. Return the rest of the unselected race and feature cards to
the corruption box.

**Race cards** ("First, find all the Dwarves..."): one per race, and races go by
strength (gnomes 2, halflings 3, dwarves 4, avions 5, humans 6, elves 7, feltrix 8,
drakonids 9), so the eight corruptions of the campaign are one of each strength 2 to 9,
as mission 10's enemy stat card shows. **Feature cards** ("Then corrupt one that has a
badge"): a picture detail that narrows the set-aside characters to one or a few.

**Owner's decision:** the app plays a themeless deck, so corruption is simply random:
a random strength among 2 to 9 not yet corrupted, then a random eligible card of that
strength. Eligible cards have a class, are not corrupted or restored, are not special
characters (Gøran, Myla, the Evergreens, beasts, pilgrims, mercenaries) and are not
class-deck visitors that leave after the mission. Corruption is a sleeve, not a sticker,
so a corrupted card still counts as "no stickers" for mission 9's mage student. Mission
11's rip-up takes the corrupted 6, whatever its class, since the reborn Evergreen is a 6.

## Map and game mat (the owner's photos)

**Map:** the inside of the box lid shows Deccaria: a forested west, a great tree in the
middle, mountains and a crater in the east, with the mission locations drawn as small
white landmarks. The location cards' backs are pieces of it. The app's map screen keeps
its themeless serpentine of twelve stops (owner's choice).

**Game mat:** the same map as a playmat with boxes for the reserve deck, the discard
pile, the mission zone (a tall box in the middle), the enemy deck, the enemy stats card,
the banished pile, the relics, and three unlabelled boxes on the right edge (relics
overflow and set-aside cards). Two trackers run along the long edges: enemy strength
along the top and enemy health along the bottom, both numbered 0 to 60 with a token
each (mission 4 notes the strength token is flipped for negative values; enemies above
60 health, Myla and the High Arcana, need the track counted twice). The app shows the
same two numbers on the enemy panel.

**Coverage check (everything the owner photographed):** rulebook pages 2 and 5 to 26
(3 and 4 are the contents list), the four player helper cards, all twelve missions
(location, story, setup, rules, summary, enemy stats and reward cards, with an example
enemy for most), every relic on both sides, packs C, F, M, P and E in full, the map and
the mat, the back of mission 12's rules card, Gøran's four beasts and mission 7's
pondkin fronts. Not photographed and not needed: the 40 party card fronts (names are not
wanted), the 12s' and 2/5s' names, the 5 and 7 pilgrims' names. Nothing from the box is
left open.

## Permanent mechanics (as transcribed)

* **Corrupted cards**: a party card can become corrupted (it gets a corrupted sleeve).
  When a corrupted card is played, banish the top card of the tavern deck. Corrupted
  cards ignore enemy immunity for their own suits. VERIFY exact wording.
* **Banished pile**: cards removed from the mission (face up pile; order matters in
  some missions).
* **Mission zone**: a mission-specific area on the playmat that several missions fill.
* **Relics** (persist between missions):
  * Kinfolk Flute (after M1): **confirmed and implemented, both sides.** 2+ players: after the active
    player forms an attack, before step 2, other players may add cards from hand that
    form a valid kinfolk attack with it; no animal companions. Solo: once per turn at
    any time put a 2, 3, 4 or 5 from hand on the flute if no card of a different
    strength is already there; while forming a kinfolk attack, flute cards may be played
    as though from hand.
  * Scarlet Whistle (after M4): **confirmed, both sides.** 2+ players: after an attack
    formed with a solitary animal companion or beast, one other player may add any card
    from hand except a Jester, before step 2. Solo: when you form such an attack you may
    take the top card of the discard pile and add it to the attack.
  * Azure Emblem (after M6): **confirmed, both sides.** 2+ players: when you form an
    attack with a mage, before peeking, each other player may place one card from hand
    on top of the reserve deck; once per attack even if a mage adds another mage. Solo:
    when resolving a mage ability, after selecting the card to add, you may put one of
    the other cards you looked at on top of the reserve deck before discarding the rest.
  * Evergreen Mother, corrupt relic (after M9): **confirmed, both sides.** Solo: when a
    corrupted card enters play you may banish the top card of the discard pile instead
    of the reserve deck (if the discard pile is not empty). 2+ players: another player
    must banish a card from hand instead of the reserve deck; if all other hands are
    empty nothing is banished. Replaced at the start of M12 by the Evergreen Mother,
    restored relic (**confirmed, both sides the same**): restored cards can never enter
    the banished pile; if they would, put them on the bottom of the reserve deck.
* **New suits / classes** (each has 3/5/7/9 cards that join temporarily, one stays):
  * ★ Mages (M3, permanent A–10★ added): reveal N cards from the tavern, pick one to add
    to the combo (its suits and value join), discard the rest; a picked Mage chains.
    Cards from a combo containing a Mage are banished at cleanup instead of discarded.
  * ⚔ Reavers (M5): reveal N cards, banish them all, add the chosen one's value to the
    damage. With an empty tavern: just double the damage.
  * 🛡 Guardians (M6): take no damage this turn.
  * 🪶 Druids (M7): sort the discard pile: one card to hand, one on top of the tavern,
    one under it, one banished, the rest stay.
  * 🥁 Drums (M8): draw up to N extra cards, then discard down to hand size.
  * Suit resolution order in regicide-js: Mages, Druids, Hearts, Diamonds, Drums,
    Spades, Guardians, Clubs, Reavers. VERIFY against the Legacy rulebook.
* **Beasts**: value 0 alone; paired with another card they copy its value. From M5 you
  pick one Beast of a basic suit to add to the deck for the mission (M11 excluded). A
  permanent ★ Beast joins after M9.
* **Special party members**: the High Arcana (25, "Elf Mage", no class, confirmed by the owner; joins after M1; the fan transcription has him leaving after M2 but no M2 card does it), Goran (8, gains a suit
  after each of M5–M8, ignores immunity after M9, removed after M10), Myla (7; joins
  after M5, leaves at M6, is the boss of M9), Esme (the 6♣; removed for M11, returns with
  all four suits).
* **Mercenaries ("M" box, opened after your first loss)**: **confirmed from the cards.**
  Mercenary rules card: "When you fail a mission, you gain coins equal to the number of
  losses you've had for this mission. You can use those coins to hire mercenaries to join
  you on your next attempt. You may also swap any mercenaries currently in your deck with
  other mercenaries of the same cost. When you successfully complete a mission, all the
  mercenaries you've hired will return to the mercenary box. As you have just tasted
  defeat, you may spend 1 coin now!" The M card itself is story text. Costs (coins in the
  top-right corner): 4 × "12" (one per class; Hella is the paladin) cost 1; 4 × "2/5"
  (one per class; Zimis & Ora are the clerics) cost 1; 2 × "19" (Raki, Mountain Warden;
  Taitonga, Forest Warden; no class) cost 3; 2 × Wild Animal (Bristle the squirrel,
  Thistle the sparrow; A, all four class icons, declare one when entering a playmat) cost
  3; 2 × Jester (Nelle, Xam) cost 5. The engine's coin and swap rules match; unspent
  coins on success are still assumed lost.
* **Feign death** is official (see above); regicide-js' "6 or more cards" is a
  simplification of "entire hand while at the hand limit".
* **Jester**: regicide-js treats Jesters as a pool of 2 (plus bought extras), played from
  the pool with value 8 and a chosen basic class, bypassing immunity, removed after use.
  That matches the official solo rule; multiplayer uses the claim rule above.
* **Cleanup ordering** (from M4): played cards go to the discard pile lowest value on
  top; mage-banished cards likewise. (This matters because several missions look at
  the top of the discard / banished piles.)

## Missions

Numbers are attack / health.

1. **Call to Arms** (Ostrana; fan name: The Beginning) — **confirmed:** 4 Justicars
   10/20, 4 Queens 15/30, 4 Kings 20/40, one per class. Enemy defeated: discard pile;
   exact damage: top of the reserve deck. Rewards: open pack C and corrupt a character
   (random in the app, one strength 2 to 9 each; see the Pack C section), add the High
   Arcana (25, no class icon), acquire the Kinfolk Flute.
2. **Shadow and Mist** (Umbra Cavern; fan name: The Hydra Assault) — **confirmed:** 6
   Hydra Heads 10/20, each with a distinct pair of classes (immune to both). Imperfect
   kill: face down to the bottom of the enemy deck. Exact kill: banished. Rewards: open
   pack C and corrupt another character (random); reveal the first 3, 5, 7 and 9
   from the shuffled party and give each one class sticker (each class once, never the
   card's own class; the player assigns). No card removes the High Arcana here.
3. **Lessons in Flames** (Magic Academy; fan name: The Mage Tower) — **confirmed:** the
   High Arcana leaves first. 4 Instructors 10/30, 2 Professors 15/45, 1 Dean 20/60, all
   Mages. End of each turn (skipped on a kill): top reserve card face up into the
   mission zone. Enemies are immune to every class in the zone. Enemy defeated: banish it
   with the whole zone; exact kill: rescue one zone card to the discard pile first.
   Rewards: open pack C and corrupt another character (random); open pack F: the
   ten mages (A to 10) join the party.
4. **Fusion of Darkness** (Biology Laboratory; fan name: The Gauntlet) — **confirmed:**
   twelve corrupted experiments, Phase I 10/20, Phase II 15/30, Phase III 20/40, one per
   class. Each enemy's strength is increased by the strength of the top card of the
   discard pile (recomputed whenever the pile changes before damage is suffered; fixed
   while suffering). Enemy defeated: discard pile; exact: top of the reserve deck.
   Experiments drawn into a hand play as corrupted cards. Rewards: Gøran (8, no class)
   joins; Gøran's four beasts, one per attempt in the reserve; corrupt another character
   (player's choice); Scarlet Whistle.
5. **High and Mighty** (Crimson Grove; fan name: The Siege) — **confirmed:** four Reavers
   (3, 5, 7, 9) join for the mission; Myla (7, no class) starts in the banished pile. 4
   Sporelings 10/40 and 4 Gloomspores 15/60, one per class. End of turn: top banished
   card face up into the mission zone; the zone's combined strength is added to the
   enemy's. Enemy defeated: enemy and zone shuffled into the banished pile; exact kill:
   the next enemy takes damage equal to the defeated enemy's strength. Rewards: Gøran
   gains Warrior; Myla joins; Harore (5 Reaver) stays, the other Reavers leave; corrupt
   another character (player's choice); James, Jakhim or Lee (the 6s) gains Reaver
   (player's choice).
6. **Shards of Memory** (Garden of Remembrance; second edition, fan name: The Evergreen
   Siege) — **confirmed:** Myla leaves the party and starts face up in the
   mission zone; four Guardians (3, 5, 7, 9) join. 4 Guardian statues 15/30 and 4
   Evergreen statues 20/40, one per class. Enemy defeated: banish it; move one card in
   play into the zone; exact kill: one zone card except Myla to the discard pile; then
   team damage equal to the zone's strength (Myla's 7 included), discarded one card at a
   time by any players; a Guardian in the killing attack prevents it. Rewards: Gøran
   gains Paladin; corrupt another character (random); Azure Emblem; Bronze,
   Snow or Shadow (the 8s of cleric, bard, warrior) gains Guardian (player's choice);
   Runo (3 Guardian) stays, the other Guardians leave.
7. **Tales of Rebirth** (Well of Tears; fan name: The Pilgrimage) — **confirmed:** four
   Druids (3, 5, 7, 9) join for the mission. 4 Shoal 10/20, 4 Deep 15/30, 4 Abyssal
   20/40 pondkin, one per class. Pack P's pilgrims form a face-down deck in the zone;
   start of turn: one pilgrim face up. A card entering play may banish a zone pilgrim of
   the same strength (once per card). Pilgrims never leave players' hands. Enemy
   defeated: discard reserve cards equal to the zone's total strength, discard the zone,
   banish the enemy; exact kill: banish one zone card first. Rewards: Gøran gains
   Cleric; corrupt another character (random); Alantha (7 Druid) stays, the
   other Druids leave; Glamelyn, Herbod or Dhonatir (the 4s) gains Druid (player's
   choice). Pack P: four classless cards of each strength 2 to 7, plus the puppy.
8. **Winds of Chaos** (Heaven's Edge; fan name: The Troll Bridge) — **confirmed:** four
   Chanters (3, 5, 7, 9) join for the mission; the puppy starts in the mission zone and
   the other pilgrims are shuffled into the reserve. 6 Trolls 10/20 and 6 Wyverns 25/50,
   each immune to a distinct pair of classes. Non-pilgrim zone cards add their strength
   to the enemy. Enemy defeated: banish it; cards in play may be moved to the zone one at
   a time, each exactly one higher than the zone's highest; a 10 clears the zone to the
   discard pile, lets you banish any discards, and heals the rest under the reserve (no
   more moves afterwards). Exact kill: any discard pile card to the top of the reserve.
   Rewards: Gøran gains Bard; corrupt another character (random); Druldox (9
   Chanter) stays, the other Chanters leave; Sprinkle, Dinky or Wicket (the 2s) gains
   Chanter (player's choice); the puppy goes back in the box.
9. **Hope From Ashes** (Twinseed Temple; fan name: The Rescue) — **confirmed:** Gøran, the
   chosen beast, Jesters and mercenaries are set aside; 30 of the remaining party cards
   are dealt into three captured piles of 10 in the mission zone, tops face up; the
   pilgrims and the set-aside cards are shuffled into the rest of the reserve. 4
   Loreguards 15/30, 4 Lorekeepers 20/40, then Myla 20/80 (bard and paladin, immunity
   never ignorable). End of turn: banish a hand card to rescue a pile's top card to the
   discard pile, or rotate every pile. Enemy defeated: banish it; exact kill: a pile's
   top card may go on top of the reserve. Rewards: Evergreen Mother (corrupt relic, both
   sides confirmed); Gøran renewed (8, Evergreen: all four classes, ignores immunity);
   the first unstickered 4 or 8 revealed (player picks the strength) gains Mage; Ash
   (B, Mage beast) joins permanently.
10. **Pride to Fall** (Twinseed Temple Ruins; fan name: The Corruption) — **confirmed:**
    the corrupted characters leave the party and form the enemy deck face up, 2 on top
    to 9 at the bottom; health 5 × strength; strength + the whole mission zone; start of
    turn: top reserve card into the zone. Enemy powers: warrior doubles the total
    strength; paladin reduces damage taken by its base strength; cleric moves the top
    discard into the zone at end of turn; bard makes the current player put a hand card
    into the zone at end of turn. Enemy defeated: banish the zone, discard the enemy;
    exact kill: discard the zone instead. Rewards: Gøran is lost; the corrupted
    characters return (still corrupted).
11. **Descent Into Darkness** (Caverns of Decay; fan name: The Beast Hunt) —
    **confirmed:** a corrupted member of the Eternal Vine (Esme, the 6 of warriors) is
    ripped up at setup. Gøran's four beasts form a face-down beast deck in the mission
    zone (none in the reserve; Ash stays). Start of turn: reveal a beast and apply its
    class (warrior: top discard banished; paladin: top reserve card discarded; cleric:
    discard a hand card; bard: banish a hand card); revealed beasts pile face up and
    reform the deck when all four are out. 4 Justicars 10/30 then the Corrupted
    Evergreen 20/90, no innate class; each enemy is immune to the classes of, and gains
    the strength of, the top cards of the discard and banished piles (beasts grant no
    immunity). Enemy defeated: banish it; exact kill: no beast revealed next turn.
    Reward: the reborn Evergreen, Esme (6, Evergreen); the beasts return to the box.
12. **Decay to Growth** (Throne of Corruption; fan name: The Final Stand) —
    **confirmed:** at setup every corrupted party member and Esme become restored, and
    the restored Evergreen Mother replaces the corrupt one (restored cards never enter
    the banished pile: bottom of the reserve instead). 4 Queens 15/30 and 4 Kings
    20/40, one per class, then the High Arcana 25/120 (no class); all corrupted. Start
    of turn: top banished card into the mission zone; the zone adds strength and grants
    immunity to its classes. Enemy defeated: banish the zone (any order), the enemy,
    then the whole discard pile in order; exact kill: skip the next start of turn.
    Corrupted cards never enter the reserve (bottom of the banished pile). Reward: open
    pack E; the campaign is complete.

## Evergreen mode (pack E; confirmed, transcribed from the owner's photos)

The pack's own name for the mode is **Evergreen mode**. The owner wants it offered from
the game menu of a finished campaign as an "Evergreen mission" button.

**Evergreen rules card.** "Evergreen mode allows you to play Regicide Legacy over and
over again using your party deck from the end of Mission 12. Use the Evergreen cards in
this pack to construct unique missions. Set the game up like a normal mission (rulebook
pg. 7) with the following changes: use the 4 Phase III Experiments and 4 Phase II
Experiments (from mission box 4) as your 8 enemies. From this box randomly select: one
location card; two grey banes, one yellow bane and one red bane; one grey boon and one
yellow boon. Greys are low complexity and mostly affect the setup. Yellows are medium
complexity and usually introduce a rule change. Reds are high complexity and often
introduce new rules along with changes to the game state as you play. Keep boons and
banes by the mat as you play as reminders of the rules." *Rules continued:* "To increase
complexity you can swap one of the grey banes with a second red bane. For an extra
challenge just add another bane! Feel free to try any combination of cards you'd like
or check out our pre-constructed setups via the QR code below."

**Location cards (five, lettered A to E; back: "Location").**
* **A, Shrine.** End of turn: put the top card of the reserve deck into the mission
  zone. Special rules: each enemy has immunity to the classes of cards in the mission
  zone. Enemy defeated: banish the enemy, or discard it if exact damage was dealt; then
  banish cards in the mission zone.
* **B, Cave.** End of turn: put the top card of the reserve deck into the mission zone;
  if the combined strength of cards in the mission zone equals or exceeds the base
  strength of the current enemy, banish the mission zone and the entire discard pile.
  Enemy defeated: banish the enemy, or discard it if exact damage was dealt; then
  discard cards in the mission zone.
* **C, Forest.** Setup: shuffle Phase I Experiment enemies (from mission box 4) into the
  banished pile. Special rules: each enemy has additional strength equal to the
  combined strength of cards in the mission zone. End of turn: put the top card of the
  banished pile into the mission zone. Enemy defeated: put the enemy and cards in the
  mission zone into the banished pile then shuffle the banished pile; if exact damage
  was dealt, you may first discard one card from the mission zone.
* **D, Hills.** End of turn: put the top card of the banished pile into the mission
  zone; players suffer team damage equal to the combined strength of cards in the
  mission zone (same rules as team damage in mission 6); if the damage can't be
  satisfied the game is lost. Enemy defeated: as the Forest.
* **E, Lake.** Setup: shuffle pilgrims and place in a pilgrim deck in the mission zone.
  Start of turn: put the top card of the pilgrim deck (or reserve deck if the pilgrim
  deck is empty) into the mission zone. Enemy defeated: for each card in the mission
  zone banish a card from the reserve deck, then move the cards in the mission zone to
  the discard pile in any order; then banish the enemy, or discard it if exact damage
  was dealt.

**Bane cards (23, numbered; the chevron colour is the tier; back: a banner over hills,
"Bane").** Grey (setup), 1 to 8: 1 Six is the New Four (replace the Phase II Experiments
with the Hydra enemies from mission box 2; a Hydra not dealt exact damage goes to the
bottom of the enemy deck, overriding the location's cleanup rule for the enemy); 2
Mental Health Day (put 30 cards from the top of the reserve deck into the discard
pile); 3 A Dozen Ways to Die (replace the Phase III Experiments with the Wyvern enemies
from mission box 8); 4 Seeds of Corruption (replace the Restored Evergreen Mother relic
with the Corrupted one); 5 Somehow, Myla Returned (add Myla, High Arcana's Apprentice,
to the bottom of the enemy deck); 6 Full Moon (set aside Ash and Quill, the mage beast
and animal); 7 Solstice (set aside all five Deccari, the 10s); 8 Ghosts From The Past
(add the High Arcana to the bottom of the enemy deck; he is immune to the four base
classes). Yellow (rule changes), 9 to 15: 9 Lethal Warriors (enemies with a warrior
icon have double strength, other bonuses included); 10 Poisonous Clerics (end of turn:
if the current enemy has a cleric icon, the top card of the discard pile goes into the
mission zone); 11 Immovable Paladins (enemies with a paladin icon reduce damage dealt to
them by 10); 12 Duplicitous Bards (end of turn: if the current enemy has a bard icon,
put a card from your hand into the mission zone); 13 Explosive Spores (enemy defeated:
team damage equal to the defeated enemy's base strength, mission 6 style; lost if it
cannot be satisfied); 14 Absorbtion (enemy defeated: after the location's rules, the
cards of the killing attack go into the mission zone); 15 Tread Carefully (enemy
defeated without exact damage: the entire discard pile goes to the banished pile before
the location's rules). Red (ongoing), 16 to 23: 16 Lingering Dread (start of turn: top
discard into the banished pile); 17 Beastly Vigor (enemies gain the strength of the top
discard); 18 Mutated Beasts (enemies gain the strength of the top banished card); 19
Shapeshift (enemies are immune to the classes of the top discard); 20 Fused Bones
(immune to the classes of the top banished card); 21 Eye-Level Sticks (after forming an
attack containing a card of strength 8 or more, discard a hand card if you can); 22 The
Fiery Crucible (start of turn: top reserve card into the discard pile); 23 Choose Your
Poison (end of turn: discard a hand card, or the top reserve card goes into the mission
zone).

**Boon cards (12, numbered 24 to 35; back: a banner over green hills, "Boon").** Grey
(setup), 24 to 29: 24 This Is Noble, Sir (spend 5 coins on mercenaries from pack M and
add them to the reserve deck); 25 There Are Two of Them! (add Gøran the Evergreen, from
mission box 10, to the reserve deck); 26 Call for Help (add all four of Gøran's Beasts
to the reserve deck instead of one); 27 Too Easy! (the hand size limit is increased by
1); 28 Best Friend (add the puppy from mission box 8 to the reserve deck; when played it
has all four base classes for that attack); 29 Second Breakfast (add Oaken, 3 reaver,
Tolman, 3 druid, and Roslyn, 3 chanter, to the reserve deck). Yellow (rule changes), 30
to 35: 30 Squad of Siblings (immediately after forming an attack you may move one
mission zone card of the same strength as a card in the attack to the discard pile); 31
Selfless Rescue (immediately after discarding a card to satisfy damage, if it matches
the strength of a mission zone card you may move that card to the discard pile); 32
Precision Strike (exact kill: put any mission zone card, or the top discard, into your
hand); 33 Restored Arrows (exact kill: you may put any one banished card on the bottom
of the reserve deck); 34 An Alliance (the Kinfolk Attack strength limit rises from 10 to
12, so two 6s or three 4s are legal); 35 A Close Call (when you satisfy damage for the
exact amount suffered, not team damage and not 0, the discarded cards go to the bottom
of the reserve deck instead of the discard pile, then put any discard pile card on top
of the reserve deck).

**Names learned here:** Gøran's Beasts (Call for Help): a griffin, a boar, a moose and a
tortoise-shelled panther. Roslyn is the 3 chanter, Tolman the 3 druid, Oaken the 3
reaver (already recorded).

**Races by strength (from Solstice and the mission cards):** gnomes 2, halflings 3,
dwarves 4, avions 5, humans 6, elves 7, feltrix 8, drakonids 9, Deccari 10; the party
holds five 10s (the four basic classes and the mage).

**Engine status:** Evergreen mode is playable. `evergreen.py` holds the transcription,
the draw (`draw_setup`, with the two rules-card variants) and `build_setup`, which turns
a drawn setup into a mission (the Phase II and III experiments, the grey banes' and
boons' setup changes); `evergreen_rules.py` implements every location, bane and boon as
small handlers keyed by card number on one rule set (`EvergreenRules`, id `evergreen`),
tested one card at a time. The campaign save keeps the current setup, its options and
its record (`CampaignState.evergreen`); the game menu of a finished campaign opens the
Evergreen screen (draw, redraw, the two options, the cards' texts, boon 24's five-coin
mercenary camp, start, continue); a lost mission allows a retry or a redraw, no coins.
Readings the pack leaves open, as the app plays them: effects sharing a moment resolve
location first, then banes and boons by number (end of turn: the location, bane 10, bane
12, bane 23; start of turn: the location, bane 16, bane 22; setup: bane 5's Myla above
bane 8's Arcana at the bottom). On a kill, the exact-kill boons 32 and 33 resolve
before bane 15 and the location's steps (boon 32 names the zone, which the location then
empties), bane 14 keeps the killing attack (its last play, a mage attack included) in
the zone after the location's steps, and bane 13's team damage comes once the piles are
final. Bane 21 and boon 30 judge the attack as formed in step 1, before the relics let
others add to it; a beast counts as its partner. Bane 2 moves the 30 cards before the
hands are drawn, the reserve's top card ending on top of the discard pile. Boon 31
applies to a player's own damage, not to team damage. Boons 32 and 35 are mandatory when
they have an option (their cards say "put"); boons 30, 31 and 33 may be declined. Boon
28's puppy has no classes anywhere but in an attack. The corrupted-card rule of mission
12 is not applied in Evergreen mode (it is a mission 12 card), so a discarded experiment
or Arcana may be healed into the reserve and drawn.

## Verification checklist for the owner (gate G2 in PLAN.md)

The official compendium at regicidelegacy.com/compendium has a page per mission; the
cards themselves are definitive. For each mission, confirm: enemy strength/health per
tier, immunities, the start/end-of-turn effects, the enemy-defeated sequence and its
perfect-kill variant, what joins and leaves the party, and the reward pack contents.
Globally confirm: whether a solo player may yield in Legacy (the base reading forbids it;
the fan engine allows it unless the previous action was a yield; the solo rules on p.26
do not mention yielding), whether unspent coins are lost when a mission is won, the
nothing else: pack E is complete. Already confirmed from the cards: every
mission, every relic on both sides, the class-ability text and resolution order, the
coin and mercenary rules and costs, the Jester claim rules, the 2/5 and Wild Animal
declarations, pack C's corruption procedure, pack F (the ten mages) and pack P.
