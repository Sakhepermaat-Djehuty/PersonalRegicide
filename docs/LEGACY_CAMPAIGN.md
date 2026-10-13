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
engine implements exactly this (`CampaignState.finish_attempt`, `hire`, `swap`).

### Engine work implied by pages 20–26 (tracked for Stage 4)

* A per-play "ignores immunity" flag so a Jester or corrupted paladin keeps its strength
  reduction even after the enemy gains paladin immunity; plain paladins lose theirs.
* Enemies gaining immunity mid-mission (mission rules), with the paladin recalculation.
* Legacy kinfolk: any number of equal-strength cards totalling at most 10 (no four-card
  cap, strength-based rather than rank-based so 2/5 cards work).
* Beasts (copy partner strength), companions pairing with companions.
* Mage attacks are banished even if the mage ability was blocked.
* Interactive mid-resolution decisions: mage peek, pick and chain; druid deal and
  allocate per player; chanter declared number; reaver count and choice. These need a
  serialisable "decision pending" phase in the engine.
* Suffering damage one card at a time with no over-discarding; clean-up order chosen by
  the player.
* 2/5 and Wild Animal declarations on entering play.
* Relics with separate solo and multiplayer sides.

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
1. "Open pack C and corrupt a character in your party." The player chooses the
   character; the rules of pack C (which characters qualify) are still to be read.
2. "Add the High Arcana to your party." The High Arcana: strength 25, subtitle "Elf
   Mage", no class icon on the card (so no class ability; to be confirmed).
3. "Acquire the new relic." Kinfolk Flute, relic. Side photographed (the two-or-more
   players side): "After you form an attack (before proceeding to Step 2), other players
   may add cards from their hand to the attack, as long as the added cards form a valid
   Kinfolk Attack. Animal Companions may not be added this way as they cannot be a part
   of Kinfolk Attacks." The solo side is still to be photographed.

**Engine status:** mission 1 is marked verified. The corruption is a player choice in the
app (candidates still follow the fan constraints until pack C is read). The flute's
multiplayer side is recorded but not implemented yet; the fan "store a 2–5 on the flute"
mechanic is kept for solo play only, pending the solo side of the card.

## Permanent mechanics (as transcribed)

* **Corrupted cards**: a party card can become corrupted (it gets a corrupted sleeve).
  When a corrupted card is played, banish the top card of the tavern deck. Corrupted
  cards ignore enemy immunity for their own suits. VERIFY exact wording.
* **Banished pile**: cards removed from the mission (face up pile; order matters in
  some missions).
* **Mission zone**: a mission-specific area on the playmat that several missions fill.
* **Relics** (persist between missions):
  * Kinfolk Flute (after M1): **confirmed (2+ players side):** after the active player
    forms an attack, before step 2, other players may add cards from hand that form a
    valid kinfolk attack with it; no animal companions. Solo side: VERIFY (the fan
    engine stores one 2–5 per turn on the flute to play in a later kinfolk attack).
  * Scarlet Whistle (after M4): play an Ace or Beast together with the top card of the
    discard pile as a pair. VERIFY.
  * Azure Emblem (after M6): after a Mage pick, keep one of the other revealed cards on
    top of the tavern deck instead of discarding them all. VERIFY.
  * Evergreen Mother, corrupted (from M9): the fan engine banishes from the discard
    pile instead of the reserve; the owner remembers it banishing a card from another
    player's hand instead. VERIFY from the card (photo pending). Replaced in M12 by
    Evergreen Mother, restored: restored cards that would be banished go under the
    reserve deck instead. VERIFY.
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
* **Special party members**: the High Arcana (25, "Elf Mage", no class icon; confirmed; joins after M1, leaves after M2 per the fan transcription), Goran (8, gains a suit
  after each of M5–M8, ignores immunity after M9, removed after M10), Myla (7; joins
  after M5, leaves at M6, is the boss of M9), Esme (the 6♣; removed for M11, returns with
  all four suits).
* **Mercenaries ("M" box, opened after your first loss)**: **confirmed by the owner and
  the p.25 sticker:** each time you lose a mission you gain coins equal to the number of
  times you have lost it (1 after the first loss, 2 more after the second, 3 more after
  the third: 1, 3, 6, 10 in total). Hired mercenaries stay for the next attempt of the
  same mission and unspent coins carry over; after each failure you may swap a hired
  mercenary for another of the same cost. When the mission is won every mercenary
  returns to the box and the next mission starts with none (the engine also drops unspent
  coins at that point; unverified). Spend coins on mercenaries with a printed cost: 4 ×
  "12" (one per basic class), 4 × "2/5" (declare 2 or 5 when it enters play), 2 × "19"
  (no class), 2 × Wild Animal (declare one of four classes when it enters play), 2 ×
  extra Jesters. VERIFY the printed costs.
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
   of your choice (qualifying characters per pack C, still to be read; the fan
   constraints are value 2–9, never repeating a rank, never the same suit more than
   twice), add the High Arcana (25, no class icon), acquire the Kinfolk Flute.
2. **Shadow and Mist** (fan name: The Hydra Assault; location Umbera cavern) — 6 Hydras 10/20, each with a distinct pair of basic suits
   (immune to both). Imperfect kill: the Hydra goes to the bottom of the enemy deck.
   Perfect kill: banished. Reward: pick one random 3, 5, 7 and 9 and give each a second
   basic suit (every suit used once; not a suit the card has); corrupt another card;
   the High Arcana leaves.
3. **Lessons in Flames** (fan name: The Mage Tower; Magic Academy) — 4 Mages 10/30, 2 Wizards 15/45, 1 Grand Wizard 20/60, all ★.
   End of each turn (not on a kill): top tavern card to the mission zone. Enemies are
   immune to every suit present in the mission zone (shields are recalculated when ♠
   immunity appears or disappears). On a kill the mission zone is banished; perfect
   kill: rescue one zone card to the discard first. Reward: A–10★ join permanently;
   corrupt a card.
4. **Fusion of Darkness** (fan name: The Gauntlet; Biology Laboratory) — standard 12 royals, all corrupted. Enemy attack + value of the top
   discard card. Reward: Goran joins, Scarlet Whistle, corrupt a card, Beast picks begin.
5. **High and Mighty** (fan name: The Siege) — 4 enemies 10/40 and 4 enemies 15/60 (one per suit per tier). Reavers
   3/5/7/9 (the contents guide says 3/5/7/10; VERIFY) and Myla join for the mission. End of turn: top banished card to the mission
   zone; enemy attack + total mission zone value. Kill: enemy and mission zone shuffled
   into the banished pile; perfect kill carries the enemy's base attack as damage onto
   the next enemy. Reward: Myla and Reaver 5 stay; choose a 6 (♥♦♠) to get the Reaver
   suit; Goran gains ♣; corrupt a card.
6. **Shards of Memory** (fan name: The Evergreen Siege; Garden of Remembrance; rules changed in the 2nd printing) — 4 Guardians 15/30 and 4 Evergreens 20/40. Myla starts in
   the mission zone; Guardians 3/5/7/9 join. On each kill: banish the enemy, move one
   played card into the mission zone, then suffer damage equal to the mission zone total
   (skipped if a Guardian was active that turn; perfect kill ignores the highest zone
   card). Reward: Azure Emblem; Guardian 3 stays; choose an 8 (♦♥♣) to get the Guardian
   suit; Goran gains ♠; corrupt a card.
7. **Tales of Rebirth** (fan name: The Pilgrimage; Well of Tears) — standard royals (corrupted). Druids 3/5/7/9 join. A 25-card
   pilgrim deck (four each of 2–7 plus one Ace, no suits). Start of turn: top pilgrim to
   the mission zone. Playing a card banishes a pilgrim of the same value. Pilgrims in
   hand are dead weight this mission. Kill: move top tavern cards to the discard equal to
   the zone's total, then the zone to the discard, banish the enemy; perfect kill: banish
   one zone card first. Reward: Druid 7 stays; choose a 4 (♦♠♣) to get the Druid suit;
   Goran gains ♥; corrupt a card.
8. **Winds of Chaos** (fan name: The Troll Bridge; Heaven's Edge) — 6 Trolls 10/20 then 6 Wyverns 25/50, dual-suited. Drums
   3/5/7/9 join; the pilgrim Ace starts in the zone. Enemy attack + total of non-pilgrim
   zone cards. During cleanup you may move played cards into the zone in strictly
   ascending value (starting one above the current highest); placing a 10 clears the
   zone to the discard, lets you banish any discard cards, shuffles the rest under the
   tavern, and ends placements for the mission. Perfect kill: top discard card to the
   top of the tavern. Reward: Drum 9 stays; pilgrim Ace removed; choose a 2 (♠♣♥) to get
   the Drum suit; Goran gains ♦; corrupt a card.
9. **Hope From Ashes** (fan name: The Rescue; Twinseed Temple) — gain Evergreen Mother (corrupted). Goran, the chosen Beast and any
   mercenaries are set aside; 30 random party cards form three captured piles of 10;
   the pilgrim deck, the rest of the party and the set-aside cards form the tavern.
   Enemies: 4 at 15/30, 4 at 20/40, then Myla 20/80 (♠♦, immunity cannot be cancelled).
   End of turn: either banish a hand card and take a pile's top card to the discard, or
   rotate all three piles. Perfect kill: a pile's top card to the top of the tavern.
   Reward: permanent ★ Beast; choose "4" or "8" and a random card of that rank gains ★;
   Goran ignores immunities; the pilgrim deck is gone.
10. **Pride to Fall** (fan name: The Corruption; Twinseed Temple Ruins) — your corrupted cards leave the party and become the enemies:
    health 5 × value, attack value + mission zone total, and a suit ability (♣ doubles
    its total attack, ♠ reduces incoming damage by its value, ♥ moves the top discard to
    the zone each end of turn, ♦ makes you put a hand card in the zone). Start of turn:
    top tavern card to the zone. Kill: zone banished, enemy to discard (perfect: zone to
    discard). Reward: corrupted cards return; Goran leaves for good.
11. **Descent Into Darkness** (fan name: The Beast Hunt; Caverns of Decay) — Esme (6♣) is removed. 4 suitless enemies 10/30 then Evil Goran
    20/90. Enemies are immune to the suits on top of the banished and discard piles and
    gain attack equal to those two cards' values. Start of turn: a random basic-suit
    Beast enters the zone and triggers (♣ top discard → banished, ♠ top tavern →
    discard, ♥ you discard a hand card, ♦ you banish a hand card). Perfect kill: skip the
    next Beast. Reward: Esme returns with all four suits.
12. **Decay to Growth** (fan name: The Final Stand; Throne of Corruption) — all corrupted cards become restored; Evergreen Mother
    restored. 4 Q 15/30, 4 K 20/40, then the High Arcana 25/120. Enemy attack + zone
    total; immune to every suit in the zone. Start of turn: top banished card to the
    zone. Kill: banish the zone (your order), the enemy and the whole discard pile;
    perfect kill skips the next placement. Win = campaign complete; the E box unlocks
    endless mode (a generator: location card + bad cards + good cards per game).

## Eternal mode ("E" box)

A mission generator for the finished party deck: 5 Location cards (Shrine, Cave,
Forest, Hills, Lake), Bane cards 1–23 and Boon cards 24–35, plus "Evergreen rules". How
they combine per game is not public. VERIFY: the user will need to transcribe the
cards; the engine models it as "a location + N banes + M boons" from a data file.

## Verification checklist for the owner (gate G2 in PLAN.md)

The official compendium at regicidelegacy.com/compendium has a page per mission; the
cards themselves are definitive. For each mission, confirm: enemy strength/health per
tier, immunities, the start/end-of-turn effects, the enemy-defeated sequence and its
perfect-kill variant, what joins and leaves the party, and the reward pack contents.
Globally confirm: whether a solo player may yield in Legacy (the base reading forbids it;
the fan engine allows it unless the previous action was a yield; the solo rules on p.26
do not mention yielding), whether unspent coins are lost when a mission is won, the
Evergreen Mother effects, the Mission 6 second-printing rules, the E-box procedure, and
what pack F is. Already confirmed from the rulebook: the class-ability text and
resolution order for every class, the coin and mercenary-persistence rules, the Jester
claim rules, and the 2/5 and Wild Animal declarations.
