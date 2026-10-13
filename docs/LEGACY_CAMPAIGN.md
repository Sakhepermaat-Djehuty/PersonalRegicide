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

## Permanent mechanics (as transcribed)

* **Corrupted cards**: a party card can become corrupted (it gets a corrupted sleeve).
  When a corrupted card is played, banish the top card of the tavern deck. Corrupted
  cards ignore enemy immunity for their own suits. VERIFY exact wording.
* **Banished pile**: cards removed from the mission (face up pile; order matters in
  some missions).
* **Mission zone**: a mission-specific area on the playmat that several missions fill.
* **Relics** (persist between missions):
  * Kinfolk Flute (after M1): once per turn store one card of value 2–5 from hand on the
    flute; flute cards can be played as part of a combo later (all flute cards must share
    a rank). VERIFY.
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
* **Special party members**: Archmage (25, no suit; M2 only), Goran (8, gains a suit
  after each of M5–M8, ignores immunity after M9, removed after M10), Myla (7; joins
  after M5, leaves at M6, is the boss of M9), Esme (the 6♣; removed for M11, returns with
  all four suits).
* **Mercenaries ("M" box, opened after your first loss)**: **confirmed by the owner:**
  coins are given at the start of each attempt and equal the number of times that
  mission has been failed (none on the first attempt, one on the second, two on the
  third, and so on); nothing carries over, and hired mercenaries are never kept. Spend
  them on mercenaries with a printed cost: 4 × "12" (one per basic class), 4 × "2/5"
  (play as a 2 or a 5; counts 5 when discarded), 2 × "19" (no class), 2 × Animal
  Companion with a chosen class, 2 × extra Jesters. VERIFY the printed costs.
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

1. **Call to Arms** (fan name: The Beginning) — plain Regicide (4 J 10/20, 4 Q 15/30, 4 K 20/40). Reward: corrupt
   one random party card (value 2–9, never repeating a rank, never the same suit more
   than twice), gain the Kinfolk Flute, Archmage joins (for M2).
2. **Shadow and Mist** (fan name: The Hydra Assault; location Umbera cavern) — 6 Hydras 10/20, each with a distinct pair of basic suits
   (immune to both). Imperfect kill: the Hydra goes to the bottom of the enemy deck.
   Perfect kill: banished. Reward: pick one random 3, 5, 7 and 9 and give each a second
   basic suit (every suit used once; not a suit the card has); corrupt another card;
   Archmage leaves.
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
the fan engine allows it unless the previous action was a yield), the mercenary cost/coin rule, the exact class-ability text and
resolution order for Mage, Reaver, Guardian, Druid and Chanter, the Evergreen Mother
effects, the Mission 6 second-printing rules, the E-box procedure, and what pack F is.
