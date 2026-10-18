# Info pop-ups: the catalogue

Every game phase gets a landscape info card with its own clip of about 2 seconds. This document lists them grouped like the settings list, **Info Pop Ups [✓] ›**. Each pop-up has its own row there, and every row is on by default.

How to read an entry:

- **Shows**: what is on the card, with the number top left, the icon and the big middle number.
- **Lines**: the breakdown. `{...}` is filled in from the game, and `a | b` means one of these.
- **When**: what makes the card appear, and where it sits in the queue.
- **Melody**: the brief for its clip.

A Gøran attack that kills, for example, shows Cleric → Bard → Warrior (with the damage) → Paladin ('Not needed') → Defeated, each card with its own melody. Against an immune enemy, the blocked class's card is greyed and stamped **IMMUNITY**, and the IMMUNITY jig plays.

Contents: Turn · Attack · Jester · Classes · Damage & defeat · Enemy · Enemy strikes · Game end · Missions · Evergreen · then the rules for the order of cards, landscape and portrait, UI sounds, the melody plan and the open questions.


## Turn


#### Battle start

- **Shows**: title **{mission title} (base: 'Regicide'; Evergreen: '{location}')**; top left: mission number (base and Evergreen: blank); icon: mission (⚑).
- **Lines**:
  - {castle} enemies · hand limit {limit}
  - First: {enemy} {attack}/{health}{, immune {icons}}
  - {one setup note: 'Myla starts in the zone' | 'Mental Health Day: 30 to the discard' | 'Too Easy!: hand limit +1'}
  - {the rule to watch: 'End of turn: banished top joins the zone'}
- **When**: The app's new-game and new-attempt paths only (a fresh Game.new, never a resumed save), after the mission rules card closes. The first 'reveal' folds into this card, so New enemy does not show at game start. Setup notes come from the rules id and the starting state (setup emits no events).
- **Where in the queue**: first card of a game; then Turn (2+ players only: who starts), then the start-of-turn cards (Pilgrim arrives, Zone: enemy stronger, Beast, Lake).
- **Replaces**: new_enemy (at game start only).
- **Melody**: The mission-start jingle (catalog event mission_start, the owner's pick) is this card's clip. While this card is on, the app no longer plays mission_start by itself (screens.py:259, 309, 329), so it never plays twice.

#### Turn

- **Shows**: title **Your turn (solo) | {player}'s turn | {player} again (after a kill) | {player} claims the Jester**; top left: turn number (turn.turn); icon: turn (↻).
- **Lines**:
  - Hand {h} of {limit}
  - {enemy}: attack {a}, health {hp}/{max}
  - {one carried line: 'After a kill: no end-of-turn effects' | 'Exact kill: no beast this turn' | 'Exact kill: no zone card this turn' | 'Rescued 7♥ (captured piles)' | 'Ben goes next (Jester)' | 'Team damage paid: 12 of 11'}
- **When**: turn, except the first turn of a solo game (2+ players: it names who starts). beast_skip and zone_skip of the same action fold into it. The hand count comes from the state after the action (start-of-turn boxes have not run yet). The enemy line comes from the final state and is left out when a start-of-turn card that follows changes it. Outcomes of end-of-turn boxes from the carry buffer become its carried line.
- **Where in the queue**: after the end-of-turn cards (or New enemy / Carry damage after a kill), before the start-of-turn cards; with 2+ players it shows before the handover screen and names no hand cards.
- **Melody**: Lute and hand bell: two plucked notes, A then D, and a soft bell, 'your move'. The quietest clip of the set (3 dB under the others), still 2.0 s.

#### Yield

- **Shows**: title **Yield**; icon: yield (⚐).
- **Lines**:
  - {player} yields: no attack this turn
  - The enemy strikes next
  - {'The claimed Jester's chance is spent'}
- **When**: yield.
- **Where in the queue**: the whole of step 1; before Enemy attacks, No damage or Guardian's protection.
- **Melody**: A viol sighs two quiet falling notes (A to F#) over one soft lute D: resigned but warm (3 dB softer).

## Attack


#### Corrupted

- **Shows**: title **Corrupted**; top left: the corrupted card's strength; icon: none: the card's edge is the purple corrupted sleeve (T.CORRUPTED); there is no corrupted icon.
- **Lines**:
  - {card} enters play corrupted
  - {Reserve top banished: {card} | Top discard banished: {card} (Mother) | {player} banishes {card} from hand (Mother) | Nothing to banish: reserve empty | Nothing to banish: other hands empty}
  - Its {class icons} ignore immunity{ (not Myla's)}
- **When**: corrupt_banish or corrupt_banish_none: one card per corrupted card entering play (played, or added by a mage, a flute or a whistle). Mission 4's experiments play as Corrupted. The Myla note appears only against the 20/80 boss (mission 9, Evergreen bane 5) and only for bards and paladins.
- **Where in the queue**: in event order: right after play / add_to_play (the banish is immediate), or right after the Mother's box; before the Declared, relic and class cards.
- **Melody**: Viol drone in D minor with a cracked bell and a falling half step (B flat to A) as a card slides off to the banished pile: ominous and short.

#### Restored

- **Shows**: title **Restored**; top left: the restored card's strength; icon: none: the card's edge is the green restored sleeve (T.RESTORED).
- **Lines**:
  - {card} enters play restored
  - {Banished top {returned} → under the reserve | M12: {returned} is corrupted → banished bottom | Banished pile empty: nothing returns}
  - Its {class icons} ignore immunity{ (not Myla's)}
- **When**: restore (one per restored card entering play). A reserve_redirect just before it gives the mission 12 variant. A restored card that entered play with no restore event gives 'nothing returns' (derived; the engine logs it only).
- **Where in the queue**: with Corrupted, in entry order, before the Declared, relic and class cards.
- **Melody**: Harp and wooden flute in D major: the Corrupted figure turned upward (B flat lifting to B and on to D), light returning.

#### Declared

- **Shows**: title **Declared**; top left: the attack's strength after the declaration (the play's current value; declare.attack is absent in the class form); icon: Wild Animal: the class it takes; 2/5: the text '2/5'.
- **Lines**:
  - 2/5: '{cards} count {value}{ (forced by the kinfolk set)}
  - Attack strength {old} → {new}' | Wild Animal: '{card} is a {Class} while in play
  - Its {Class} power joins this attack'
- **When**: declare (value or class form). One card per action, however many 2/5s enter together. The declare_value / declare_class box comes first with no card before it: the box asks the question itself (the one exception to 'a card before every box').
- **Where in the queue**: after its box (or with the entry events when forced), before the Mother, Pilgrim match, bane, boon, relic and class cards.
- **Melody**: Lute and tabor: two quick plucks and a decisive strummed chord, a card slapped down with its value called, ending on D.

#### Kinfolk Flute

- **Shows**: title **Kinfolk Flute**; top left: attack strength; icon: flute (♪).
- **Lines**:
  - 2+ players: 'Others may add cards of strength {n}
  - to make a kinfolk set, total {10 | 12: An Alliance}
  - No animal companions · asked in turn: {names}' | solo store: 'Stored {card} on the flute (once a turn)
  - Play flute cards in a kinfolk set as if from hand'
- **When**: the first decide{kind:flute_add} of an attack (2+ players; the attack need not be kinfolk yet: any single card except an Ace, a beast or a Jester can grow into a set); flute_store (solo special action, a card on its own). Additions (add_to_play source=hand while the snapshot's decision is flute_add) and solo plays from the flute (ids in the snapshot's extra['flute']) become the formation line of the next card.
- **Where in the queue**: 2+: attack step 1b, after the entry cards, right before the first flute box; solo store: alone, whenever used.
- **Melody**: Two wooden flutes in parallel thirds play a little kinfolk tune in D, family voices together, ending on D and F#.

#### Scarlet Whistle

- **Shows**: title **Scarlet Whistle**; top left: attack strength; icon: whistle (♬).
- **Lines**:
  - A lone companion or beast attack ({strength})
  - {2+: 'One other player may add any card (no Jester)' | solo: 'Add the top discard {card}? {old} → {new}'}
- **When**: the first decide{kind:whistle_add} or decide{kind:whistle_take}. The outcome (whistle_take, or add_to_play source=hand while the snapshot's decision is whistle_add) is a line on the next card: '{card} joins: {old} → {value}'. A lone beast is 0 and copies the added card, so the gain is whistle_take.value minus the old strength, never the card's own value.
- **Where in the queue**: attack step 1b, after the entry cards, right before the whistle box.
- **Melody**: A shrill tin-whistle call, two quick rising whistles (A to high D), answered by a hammered dulcimer: over here!

#### Azure Emblem

- **Shows**: title **Azure Emblem**; top left: the mage's peek strength; icon: emblem (◈).
- **Lines**:
  - 2+: 'Before the mage looks, each other player
  - may put one hand card on top of the reserve
  - Once per attack, even for a chained mage' | solo: 'Put one of the other cards you looked at
  - back on top of the reserve? The rest: discard'
- **When**: the first decide{kind:emblem_place} (2+) or decide{kind:emblem_keep} (solo). Placements and the keep stay hidden: Mage's pick shows them as counts. In mission 12 a corrupted card placed or kept goes to the banished bottom (reserve_redirect from to_reserve, legacy_rules.py:1396, 1424): a line on Mage's pick.
- **Where in the queue**: 2+: right after the Mage card, before the first placement box; solo: after the pick box, before the keep box and Mage's pick.
- **Melody**: Glockenspiel and harp in D lydian, a cool shimmering rising triad: the blue emblem glints.

#### Mother (corrupt)

- **Shows**: title **Evergreen Mother**; top left: the corrupted card's strength; icon: mother (❦, purple).
- **Lines**:
  - {card} entered corrupted
  - {solo: 'Banish the top discard ({top}) instead
  - of the reserve's top?' | 2+: '{player} must banish a card from hand
  - instead of the reserve's top'}
- **When**: decide{kind:mother_choice} (solo) or decide{kind:mother_banish} (2+). The Corrupted card that follows gives the outcome. 2+ with every other hand empty: corrupt_banish_none and no box, so the Corrupted card alone.
- **Where in the queue**: attack step 1b, after the declarations, right before its box and the Corrupted card it changes.
- **Melody**: A viol and low flute lullaby in D minor over a slow heartbeat drum: a mother's song gone dark.

#### Mother (restored)

- **Shows**: title **Evergreen Mother**; icon: mother (❦, green).
- **Lines**:
  - Restored {cards} would be banished
  - They go under the reserve instead
- **When**: banish_redirect (every one of an action merged into one card).
- **Where in the queue**: right after the card that banished them (Corrupted, Reaver's pick, Druid's sorting, Defeated or Clean-up, Cave collapses, Lingering Dread, Beast).
- **Melody**: The Mother's lullaby in D major on harp and wooden flute, warm and rising: the same tune healed.

## Jester


#### Jester (base)

- **Shows**: title **Jester**; icon: jester ('J' in Jester purple, as on the Jester's face).
- **Lines**:
  - {enemy}'s immunity is cancelled for this fight
  - {'Earlier ♠ shields now count: attack {a} → {b}'}
  - No damage and no enemy attack this turn
  - {player} chooses who goes next
- **When**: jester{mode:base} (base game, 2+ players); choose_next names the next player on the Turn card.
- **Where in the queue**: attack step 1, alone; before the choose-next box.
- **Melody**: The Whistle jig, the owner's pick, re-rendered to about 2.2 s (one more bar and a held cadence on D: today's render is 1.92 s). One clip shared by all four Jester rows.

#### Jester claim

- **Shows**: title **Jester**; icon: jester ('J', Jester purple).
- **Lines**:
  - Anyone may claim it and attack now
  - That attack ignores the immunity{ (not Myla's)}
  - Its paladins keep shielding after it
  - Play goes on clockwise from the claimer
- **When**: jester{mode:claim} (Legacy, 2+ players); choose_next names the claimer on the Turn card. The enemy keeps its immunity for later turns (rulebook p.20).
- **Where in the queue**: attack step 1, alone; before the claim box.
- **Melody**: The Whistle jig (the shared Jester clip). A variant stopping on a teasing high E with a shake of cap bells is an extra candidate only.

#### Solo Jester: new hand

- **Shows**: title **Jester**; top left: Jesters left (solo_jester.remaining); icon: jester ('J', Jester purple).
- **Lines**:
  - Hand discarded ({n}), drew {m} back to {limit}
  - Jesters left: {remaining}
  - (none used: gold · one: silver · two: bronze)
  - {in step 4: 'Now pay the damage'}
- **When**: solo_jester without mode='attack': the refresh event carries only discarded, drawn and remaining (engine.py:926), no mode field (base solo).
- **Where in the queue**: step 1 or step 4, alone.
- **Melody**: The Whistle jig (the shared Jester clip). A variant over a card riffle is an extra candidate only.

#### Solo Jester: attack

- **Shows**: title **Jester**; top left: 8; icon: jester ('J', Jester purple).
- **Lines**:
  - The Jester attacks as a {Class}, strength 8
  - Ignores {enemy}'s immunity{ (not Myla's)}
  - Jesters left: {remaining}; set aside after this enemy
- **IMMUNITY**: never: its class card shows 'ignores immunity (Jester)' with no stamp; only Myla's bard and paladin immunity stamps it.
- **When**: play{kind:jester_attack} then solo_jester{mode:'attack'} (Legacy solo).
- **Where in the queue**: attack step 1; then its class card, the Warrior/Damage card and the rest of the attack.
- **Melody**: The Whistle jig (the shared Jester clip). A double-time variant on whistle and fiddle is an extra candidate only.

## Classes


#### IMMUNITY

- **Shows**: title **{the blocked class's own title}**; top left: attack strength (Mage: the strength it would look with); icon: the blocked class's icon.
- **Lines**:
  - The class's own breakdown in 'would' form:
  - 'Would heal 9' | 'Would draw 9' | 'Would double 9 → 18' | 'Would shield 9' | 'Would look at the top 9' | ...
  - {source: 'Immune: printed ♥' | 'Immune: zone 7♣' | 'Immune: top discard 6♦' | 'Immune: top banished 9♠' | 'Immune: all four basics (High Arcana)' | 'Immune: never ignored (Myla)'}
  - {Mage: 'The attack is still banished at clean-up'}
- **IMMUNITY**: This row IS the stamp: the blocked class's card greyed (CARD_FACE_DIM, muted ink) with the bold red diagonal IMMUNITY stamp in a double frame (InfoCardFace immune=True). This row governs every stamped card, whatever the class rows say.
- **When**: power{immune:true}, any class. A chained mage that is blocked (legacy_rules.py:1343 ends the chain silently) gives a stamped 'Mage again' card: from the new event, or inferred from a mage_pick whose card has M, strength above 0 and an immune enemy, with no mage_peek after it. The source line comes from the snapshot: printed suits, zone, discard or banished top, the High Arcana's immune_basic, Myla's fixed_immunity.
- **Where in the queue**: in the blocked class's slot; a blocked Warrior is followed by the Damage card; a blocked Paladin or Guardian shows on a kill too.
- **Replaces**: the blocked class's normal card.
- **Melody**: The IMMUNITY jig, shared by every stamped card: the Whistle jig's rhythm on bassoon and fiddle in D minor runs into a wooden stamp thump (timed to the stamp landing) and droops away on a comic falling slide; 2.2 s, 1 to 2 dB louder than the rest.
- **Engine**: power{suit:'M', immune:True, chained:True} where _mage_continue (legacy_rules.py:1343) ends a chain on an immune mage (or infer it, see trigger).

#### Mage

- **Shows**: title **Mage | Mage again (a chained mage)**; top left: peek strength (mage_peek.strength: the attack's strength, or a chained mage's own strength); icon: M.
- **Lines**:
  - {You look | {player} looks} in secret at the top {count}
  - Pick one to join the attack
  - (Jesters and corrupted cards can't)
  - The rest go to the discard pile{, in your order}
  - {'Nothing to look at: strength 0' | 'Nothing to look at: reserve empty' | 2+ with the Emblem, line 1: 'Will look at the top {strength}'}
- **IMMUNITY**: IMMUNITY variant (row 'IMMUNITY'): this same card in 'would' form ('Would look at the top {strength}'), greyed, stamped, with one line naming the source, and the IMMUNITY jig, plus 'The attack is still banished at clean-up'.
- **When**: mage_peek (one per peek, chains included); power{suit:M, result:{peek:0}}; 2+ players with the Azure Emblem: the first decide{kind:emblem_place} (the peek comes an action later); immune: power{M, immune}.
- **Where in the queue**: attack step 2, first class; right before the private peek box (2+ with the Emblem: before the Azure Emblem card).
- **Melody**: Celesta and harp harmonics in D lydian: a curious rising figure with the raised fourth (D E G# A) that stops on A, unresolved, like peeking behind a curtain.

#### Mage's pick

- **Shows**: title **Mage's pick**; top left: new attack strength (mage_pick.value); icon: M.
- **Lines**:
  - {card} joins: strength {old} → {value} | Nothing could join
  - {n} to the discard pile{, {card} on top}
  - {one of: 'Azure Emblem: 1 card back on the reserve' | 'Including {n} placed by others (Emblem)' | '{card} is a mage: it looks again' | '{card} is a mage of strength 0: no more looks' | 'M12: {n} corrupted → banished bottom'}
- **When**: mage_pick or mage_skip, completed by emblem_keep / emblem_skip / discard_order and reserve_redirect of the same mage, which may arrive an action later (carry buffer). Placed cards are among the cards looked at (count = min(strength, reserve), legacy_rules.py:1190), so they are counted inside, not added.
- **Where in the queue**: after the mage's boxes; before a chained Mage card (or its stamped card) or the next class.
- **Melody**: Celesta answers the Mage: the same figure turns back down and resolves on D with a glockenspiel sparkle.

#### Druid

- **Shows**: title **Druid**; top left: attack strength, drawn muted and marked 'not used'; icon: U.
- **Lines**:
  - Strength not used: the discard pile ({total})
  - is shuffled and dealt from {player} clockwise
  - Each sorts up to 4: one banished, one to hand
  - (even over the limit), one on top and one
  - under the reserve | 'Discard pile empty: nothing to deal'
- **IMMUNITY**: IMMUNITY variant (row 'IMMUNITY'): this same card in 'would' form ('Would deal the discard pile ({total})'), greyed, stamped, with one line naming the source, and the IMMUNITY jig.
- **When**: druid_deal; power{suit:U, result:{dealt:0}}; immune: power{U, immune}.
- **Where in the queue**: attack step 2: after Mage, before Cleric; right before the first sorting box.
- **Melody**: Wooden pan flute in D dorian with bird-like trills over a soft leaf rustle (shaker), an earthy call left hanging on A. The pickup is our shuffle sound (modelled on CardFan1), then a quick deal.

#### Druid's sorting

- **Shows**: title **Druid's sorting**; top left: attack strength; icon: U.
- **Lines**:
  - Banished: {cards}
  - To hands: {A} {n} · {B} {n} (solo: 'To your hand: {n}')
  - Reserve: {t} on top, {b} under · {r} back to
  - the discard pile, shuffled
  - {'Restored → reserve bottom' | 'M12: corrupted → banished bottom'}
- **When**: druid_done, with this Druid's druid_assign events, which are spread over several actions (carry buffer); banish_redirect / reserve_redirect of those moves give the last line. Hand and reserve cards are counts, never names.
- **Where in the queue**: after the last sorting box, before Cleric.
- **Melody**: The pan flute answers its call, stepping down to D; cards squared with a wooden click, leaves settling.

#### Cleric

- **Shows**: title **Cleric (base: ♥ Hearts)**; top left: attack strength (power.value); icon: H.
- **Lines**:
  - Heal {strength}: the discard pile is shuffled
  - and {k} go face down under the reserve
  - {one of: 'Discard pile empty: nothing to heal' | '{card} ignores immunity ({why})' | 'M12: {m} corrupted → banished bottom'}
- **IMMUNITY**: IMMUNITY variant (row 'IMMUNITY'): this same card in 'would' form ('Would heal {strength}'), greyed, stamped, with one line naming the source, and the IMMUNITY jig.
- **When**: power{suit:H} not immune (healed may be 0). k = power.healed minus this step's reserve_redirect events: _heal (engine.py:1040) counts redirected cards in healed and heal.cards. Base wording: 'under the tavern deck'.
- **Where in the queue**: attack step 2: after Mage and Druid, before Bard (Legacy order M U H D T R C S G); first in the base order H D C S.
- **Melody**: Harp: a gentle rising D-major arpeggio (D F# A D') that lifts and rings on high D, a hand bell touching the top note. The pickup is our shuffle sound (modelled on CardFan1).

#### Bard

- **Shows**: title **Bard (base: ♦ Diamonds)**; top left: attack strength (power.value); icon: D.
- **Lines**:
  - Draw {strength}: one card at a time from
  - {player}, clockwise; full hands are skipped
  - {solo: 'You drew {k}' | 2+: '{A} {n} · {B} {n} · {C} {n}'}
  - {'The reserve ran out: {k} of {strength}'}
- **IMMUNITY**: IMMUNITY variant (row 'IMMUNITY'): this same card in 'would' form ('Would draw {strength}'), greyed, stamped, with one line naming the source, and the IMMUNITY jig.
- **When**: power{suit:D} not immune; its draw events (one per card, just before it) give the per-player counts, never card names. Base wording: 'tavern deck'.
- **Where in the queue**: attack step 2: after Cleric, before Chanter.
- **Melody**: Lute: a bright strummed run up the D-major scale into a rolled chord and a skipping turn, a tavern bard's flourish. The pickup is our draw sound (single cards dealt, modelled on CardShuffle).

#### Chanter

- **Shows**: title **Chanter**; top left: attack strength, drawn muted and marked 'not used'; icon: T.
- **Lines**:
  - Strength not used. {player} names 0 to {max}
  - (the reserve): everyone draws that many,
  - even over the limit, then from {player}
  - clockwise each discards down to {limit}
- **IMMUNITY**: IMMUNITY variant (row 'IMMUNITY'): this same card in 'would' form ('Would have everyone draw'), greyed, stamped, with one line naming the source, and the IMMUNITY jig.
- **When**: decide{kind:chanter_declare} (the only marker of the Chanter's start); immune: power{suit:T, immune}.
- **Where in the queue**: attack step 2: after Bard, before Reaver; right before the number box.
- **Melody**: Humming voices (oohs) over a low drone: a short plainchant call D E F# E that rises and waits on E.

#### Chanter's draw

- **Shows**: title **Chanter's draw**; top left: attack strength; icon: T.
- **Lines**:
  - Declared {count}{: nobody draws}
  - Drew: {A} {n} · {B} {n}{ (the reserve ran short)}
  - Discarded down to {limit}: {A} {n} · {B} {n}
  - {solo: 'You drew {n} and discarded {m}'}
- **When**: chanter_declare (its per-player drawn lists: later players draw fewer when the reserve runs short, legacy_rules.py:1122) and its chanter_discard events (carry buffer). Shown when the next power or damage event arrives: there is no chanter_done event.
- **Where in the queue**: after the last discard box (or right after the number box when nobody is over the limit), before Reaver.
- **Melody**: The voices answer the call, settling on a full D-major chord with one soft drum tap.

#### Reaver

- **Shows**: title **Reaver**; top left: attack strength; icon: R.
- **Lines**:
  - Reveal 1 to {max} reserve cards
  - Add one's strength to the damage ({damage})
  - No powers; a 2/5 adds 5, Jester or beast 0
  - Banish all revealed, then the damage ×2
- **IMMUNITY**: IMMUNITY variant (row 'IMMUNITY'): this same card in 'would' form ('Would reveal and double'), greyed, stamped, with one line naming the source, and the IMMUNITY jig.
- **When**: decide{kind:reaver_count} (first ask; the only marker of the Reaver's start); immune: power{suit:R, immune}. An empty reserve has no box: Reaver's pick alone.
- **Where in the queue**: attack step 3, first: after the step-2 classes, right before the count box.
- **Melody**: Cello and woodblock: a low digging figure (D A F D falling) with pick strikes on the woodblock, stopping on an open low A.

#### Reaver's pick

- **Shows**: title **Reaver's pick**; top left: attack strength; icon: R.
- **Lines**:
  - Revealed {count}: {cards}
  - {before} + {added} ({card}) = {sum}, ×2 = {damage}
  - All banished{, {top} on top} | 'Reserve empty: the damage just doubles, {before} → {damage}'
- **When**: power{suit:R, added, doubled} with reaver_reveal and reaver_pick before it and reaver_order after it; before = reaver_pick.damage / 2 − added (legacy_rules.py:972-976); the empty-reserve power{R, result}. banish_redirect brings the Mother (restored) card after it.
- **Where in the queue**: after the reaver's boxes, before the Warrior or Damage card.
- **Melody**: Cello and frame drum: the digging figure, then a leap up an octave on a doubled drum hit (the doubling), heavy and dark, ending on D.

#### Warrior

- **Shows**: title **Warrior (base: ♣ Clubs)**; top left: attack strength; icon: C; middle: damage dealt (damage.amount), caption 'damage'.
- **Lines**:
  - {before} ×2 = {doubled}{ (Reaver first: ×4 in all)}
  - {'− {r}: Paladin enemy' | '− 10: Immovable Paladins'}
  - Health {hp_before} → {hp}{: defeated! | : exact kill!}
- **IMMUNITY**: The Warrior card stamped IMMUNITY ('Would double {before} → {doubled}', the source line) with the IMMUNITY jig, then the plain Damage card (the owner's rule: Warrior first with IMMUNITY, then the damage pop-up).
- **When**: power{suit:C, doubled} not immune; the middle number from the damage event of the same action. before = the Reaver's damage, else the strength; r = rules.damage_reduction on the paused state; hp_before from the snapshot; exact when hp_before equals the amount.
- **Where in the queue**: attack step 3: after Reaver's pick, in the Damage card's slot, before Paladin and Guardian.
- **Replaces**: damage (with the Warrior row off, the Damage card shows in its place).
- **Melody**: Fiddle and tabor: a stamping two-note double-stop figure played twice, the second time an octave higher (the doubling), each landing on a hard tabor hit; driving jig rhythm, ends on D.

#### Paladin

- **Shows**: title **Paladin (base: ♠ Spades)**; top left: attack strength; icon: S.
- **Lines**:
  - Enemy survives: 'Shield +{strength}: enemy attack {a} → {b}
  - All shields on {enemy}: {total}, until it falls
  - {'Ignores immunity: keeps shielding if ♠ immunity comes'}' | On a kill: 'Not needed: {enemy} fell
  - (it would have shielded {strength})'
- **IMMUNITY**: IMMUNITY variant (row 'IMMUNITY'): this same card in 'would' form ('Would shield {strength}'), greyed, stamped, with one line naming the source, and the IMMUNITY jig; shown on a kill too.
- **When**: power{suit:S}, always: the enemy survives (shield) or falls ('Not needed'), so a Gøran or Evergreen play always gives its four class cards. a and b from the paused state (the enemy's attack before and after this shield).
- **Where in the queue**: after the Warrior/Damage card, before Guardian; on a kill before Defeated.
- **Melody**: French horn: a calm sustained D-A fifth with a struck shield ringing under it, steady and noble, held to the end on D.

#### Guardian

- **Shows**: title **Guardian**; top left: attack strength; icon: G.
- **Lines**:
  - Enemy survives: 'The party suffers no damage this turn:
  - no enemy attack, no mission damage' | On a kill: 'Not needed: {enemy} fell' | m6 / bane 13 kill: '{Myla | Explosive Spores}: team damage {n} prevented'
- **IMMUNITY**: IMMUNITY variant (row 'IMMUNITY'): this same card in 'would' form ('Would protect the party'), greyed, stamped, with one line naming the source, and the IMMUNITY jig; shown on a kill too.
- **When**: power{suit:G, result guardian}, always. team_damage_prevented of the same action becomes its line (mission 6 and bane 13 kills); for the Hills it is a line on the Hills card.
- **Where in the queue**: last class, after Paladin; enemy survives: in place of Enemy attacks / No damage; on a kill before Defeated.
- **Replaces**: shielded's Guardian variant (no_damage with guardian=True); with the Guardian row off, the No damage card shows instead.
- **Melody**: Low bowed strings and a timpani swell: a broad D-major chord rising like a wall and held firm (half time).

## Damage & defeat


#### Damage

- **Shows**: title **Damage**; top left: attack strength; middle: damage dealt (damage.amount), caption 'damage'.
- **Lines**:
  - Attack {strength}{ · after the Reaver: {r}}
  - {'− {n}: Paladin enemy' | '− 10: Immovable Paladins'}
  - Health {hp_before} → {hp}{: defeated! | : exact kill!}
- **IMMUNITY**: never: damage always lands (after a blocked Warrior this card follows the stamped Warrior card).
- **When**: damage, when the attack has no unblocked Warrior, or the Warrior row is off.
- **Where in the queue**: attack step 3, in the Warrior's slot: after Reaver's pick (or the stamped Warrior), before Paladin and Guardian.
- **Melody**: Bodhrán and lute: one deep drum strike under a strummed D-minor stab in a dotted strike rhythm (D D A), ringing out briefly; plain and solid, no class colour.

#### Defeated

- **Shows**: title **Defeated**; top left: the fallen enemy's attack; icon: defeat (⚔︎).
- **Lines**:
  - {enemy} → {discard pile | banished | shuffled into the banished pile}{; zone → {where}}
  - {Lake: '{n} reserve cards banished'}
  - Next: {the mission's steps: 'move a played card into the zone' | 'build the zone' | 'Myla's team damage {n}'}
  - {folded Clean-up: '{n} played → discard pile, {card} on top'}
- **When**: the killing damage (damage.hp = 0, or carry_damage.hp = 0), not exact. Shown at the kill from the paused state (rules.defeat_plan), before any defeat box. When no box comes between the kill and the defeat event, the Clean-up lines fold into this card and no Clean-up card shows.
- **Where in the queue**: after Paladin and Guardian (or Carry damage), before boons 32/33, bane 15, the defeat boxes, Team damage (m6), Zone filled and Clean-up.
- **Replaces**: cleanup, when no box came between the kill and the clean-up.
- **Melody**: A lute flourish falling over a fading low drum roll: the enemy topples (D minor resolving to D major).

#### Exact kill!

- **Shows**: title **Exact kill!**; top left: the fallen enemy's attack; icon: exact (◎).
- **Lines**:
  - {enemy} falls exactly → {top of the reserve (base: tavern deck) | discard pile | banished | shuffled into the banished pile}
  - Bonus: {m3: rescue a zone card | m5: next enemy takes {n} | m6: rescue a zone card (not Myla) | m7: banish a zone card first | m8: after clean-up, a discard on top of the reserve | m9: a pile's top on top of the reserve | m10: the zone is discarded, not banished | m11: no beast next turn | m12: no zone card next turn | Forest/Hills: discard a zone card first | boons 32/33}
  - {player} goes again; no end-of-turn effects
  - {folded Clean-up lines}
- **When**: as Defeated, with exact (defeat.exact, or the paused decision's exact). The destination comes from rules.defeat_plan: base and mission 4 → top of the reserve; mission 5 → shuffled into the banished pile; Shrine, Cave, Lake → discard pile.
- **Where in the queue**: as Defeated.
- **Replaces**: defeated (with the row off, Defeated shows).
- **Melody**: The defeat flourish turned upward: a harp glissando to high D, a golden celesta sparkle and a pipe trill; bright and triumphant (1 to 2 dB louder).

#### Clean-up

- **Shows**: title **Clean-up**; top left: played cards cleaned up (count); icon: cleanup (≡).
- **Lines**:
  - {enemy} → {where}{; zone {cards} → {where}}
  - {n} played → {discard pile, {card} on top | banished (a mage attack)}
  - {choices since the kill: 'Rescued 6♣' | 'Moved 7♦ into the zone' | 'Zone filled: {b} banished, {h} healed'}
  - {one more: '{k} reserve → discard pile' | 'Whole discard pile banished' | 'Banished pile shuffled' | 'Next: a discard on top of the reserve (m8)'}
- **When**: defeat, with the clean-up events of its action (cleanup_order, zone_cleared, reserve_discard, discard_banished in m12, banished_shuffled, banish_redirect, defeat.mage_banished) and the choices since the kill from the carry buffer (zone_rescue, zone_move, zone_banish, zone_build, zone_filled, pile_to_reserve, precision_strike, restored_arrows, zone_discard, lake_banish, played_order, banish_order). Its own card only when a box came between the kill and the clean-up; otherwise its lines fold into Defeated / Exact kill!.
- **Where in the queue**: after every defeat-step box, before Absorbtion, Explosive Spores' Team damage, New enemy or Victory.
- **Melody**: Cards swept and squared on felt, then a short descending lute run settling on D: the table tidied.

#### Team damage

- **Shows**: title **Team damage**; icon: team (⁂); middle: team damage (team_damage.damage), caption 'for the whole party'.
- **Lines**:
  - {Myla | The Hills | Explosive Spores}: {damage}
  - Anyone, one card at a time; no feign death
  - {solo: 'Your hand holds {available}' | any: 'Not enough in hand: the mission is lost'}
- **When**: team_damage. The duplicated decide is ignored. team_discard and team_damage_done become a line on the next card ('Team damage paid: {paid} of {damage}'). team_damage_prevented is a line on the Guardian card (m6, bane 13) or on the Hills card, never this card. With 2+ players the hands' total is not shown (it would reveal hidden hands), only the lost verdict.
- **Where in the queue**: m6: after the zone move and rescue boxes, before Clean-up; Hills: end of turn, after the Hills card; bane 13: after Clean-up, before New enemy.
- **Melody**: Frame drums from all sides with a low unison horn in D minor: everyone braces.

## Enemy


#### New enemy

- **Shows**: title **{enemy name}**; top left: effective attack; icon: the enemy's printed class icons (one draw_symbol each; none for a classless enemy); middle: health (reveal.enemy.hp), caption 'health'.
- **Lines**:
  - Immune: {icons}{ + zone/pile icons}{ · all four basics (High Arcana)}{ · never ignored (Myla)}
  - Attack {printed}{ +{bonus} {source}}{ ×2 {Warrior enemy | Lethal Warriors}}
  - {n} more in the castle{ · takes {r} less damage (Paladin enemy | Immovable Paladins)}
- **When**: reveal after a kill (the first reveal folds into Battle start). Effective attack and immunity from g.enemy_attack and rules.immune_suits on the final state, unless a start-of-turn card in the same queue changes them (that card then states the change).
- **Where in the queue**: after Clean-up (or Absorbtion / Explosive Spores), before Carry damage and Turn.
- **Melody**: Horn call over a low drum, the enemy motif: a rising minor third D-F falling back through E to D, firm and dark.
- **Engine**: optional: reveal.attack and reveal.immune (the effective values at the reveal), so a start-of-turn change needs no arithmetic.

#### Enemy changes

- **Shows**: title **Enemy changes**; top left: new attack; icon: enemy (♚).
- **Lines**:
  - Attack {old} → {new} ({cause: top discard 6♣ | banished top 9♦ | zone +4})
  - Immune: {old icons} → {new icons}{; earlier ♠ shields stop counting}
- **When**: enemy_change inside an attack: a heal, a peek, a corrupt banish or a reaver banish changes a pile top between two powers (mission 4, mission 11, banes 17-20) and so changes a later power or the coming strike. Never shown on its own when Enemy attacks, Turn, New enemy, a zone card or a Beast card in the same queue already states the attack and immunity (otherwise it would show almost every turn).
- **Where in the queue**: right after the card whose step changed the pile (Cleric, Corrupted, Mage's pick, Reaver's pick...), before the next class card.
- **Melody**: The enemy motif on low strings with a twisting turn (D E-flat D C# D) and a creak of wood: it changes shape.
- **Engine**: enemy_change{attack_before, attack_after, immune_before, immune_after, cause}, emitted by the engine after an entry effect or a power when g.enemy_attack or rules.immune_suits changed.

## Enemy strikes


#### Enemy attacks

- **Shows**: title **Enemy attacks**; top left: the enemy's attack before shields; icon: enemy (♚); middle: damage to pay (suffer_due.damage), caption 'to discard'.
- **Lines**:
  - {printed}{ +{bonus}}{ ×2} − {shields} shields = {damage}
  - {Legacy: 'Discard one at a time; stop once covered' | base: 'Discard cards worth {damage} or more'}
  - {'Or feign death: your whole hand, at the limit' | 'Not enough in hand: the mission is lost'}
- **When**: suffer_due; the breakdown from the paused state (attack_bonus, attack_multiplier, shield). Legacy pays one card at a time and may not keep discarding once covered (rulebook p.18).
- **Where in the queue**: step 4a: after Paladin, before the discard box (or before Mission lost when the hand cannot pay).
- **Melody**: Low brass and war drum in D minor: the enemy motif struck hard on a heavy downbeat, ending on a grim low D (1 to 2 dB louder).

#### No damage

- **Shows**: title **No damage**; top left: the enemy's attack before shields; icon: S (the Guardian fallback: G); middle: 0, caption 'to discard'.
- **Lines**:
  - {'Shields {shield} cover the attack {attack}' | Guardian row off: 'A Guardian protects the party'}
  - Nothing to discard; the turn ends
- **When**: no_damage without guardian; no_damage with guardian when the Guardian row is off.
- **Where in the queue**: step 4a, in place of Enemy attacks.
- **Replaces**: enemy_attack.
- **Melody**: The enemy motif blocked: a drum blow muffled by the Paladin's horn fifth, then a relieved lute chord in D major.

#### Feign death

- **Shows**: title **Feign death**; top left: damage due.
- **Lines**:
  - {player} discards the whole hand: {n} cards
  - (at the limit, {limit}): it covers any damage
  - {damage} satisfied
- **When**: feign_death (never offered against team damage).
- **Where in the queue**: the suffer action's first card, before Damage paid.
- **Melody**: A comic fiddle slide falling to a soft cloth thump and a held breath, then one plucked lute note: playing dead.

#### Damage paid

- **Shows**: title **Damage paid**; top left: damage due (suffer.damage); middle: paid (suffer.paid), caption 'paid'.
- **Lines**:
  - {player} discarded {n}: {cards}
  - Hand: {h} left
- **When**: suffer. The hand count is the snapshot's hand minus the cards paid. The discarded cards are public (the discard pile is face up).
- **Where in the queue**: after Feign death, before A Close Call, Selfless Rescue and the end-of-turn cards.
- **Melody**: Our discard sound (a few cards set on a stack, modelled on CardTakeOutPackage2) as the pickup, then a lute settles the enemy motif softly into D major: the blow absorbed.

## Game end


#### Victory

- **Shows**: title **Victory! (solo base: Gold / Silver / Bronze victory!)**; icon: crown (♛).
- **Lines**:
  - {enemy} was the last enemy{, in {turns} turns}
  - {solo base: 'Jesters used: {n}'}
  - {campaign: 'Mission {n} complete: rewards next'}
- **When**: won.
- **Where in the queue**: last card of the action, after the last Defeated / Clean-up (no New enemy, no Turn).
- **Replaces**: new_enemy and turn; it is also the heading of ResultOverlay / CampaignResultOverlay (screens.py:2426, 3218): the overlay shows this landscape card with its buttons under it (row off: the overlay as today).
- **Melody**: The Victory jingle (catalog event victory, the owner's pick) as this card's clip; it no longer plays on its own.

#### Defeat

- **Shows**: title **Mission lost (base and Evergreen: Defeat)**; icon: loss (✕).
- **Lines**:
  - {Cannot pay {n} damage | No legal play or yield | Team damage too high | Abandoned}
  - {enemy}: {hp} health left · {n} enemies left
  - {campaign only: '+{coins} coins: one per loss on this mission'}
- **When**: lost; the reason is classified from context: after suffer_due → cannot pay; after turn → cannot act; after team_damage → team damage; alone → abandoned.
- **Where in the queue**: always the last card: after Enemy attacks, Team damage or Turn, or alone (abandon).
- **Replaces**: the heading of ResultOverlay / CampaignResultOverlay, as Victory.
- **Melody**: The Loss jingle (catalog event loss) as this card's clip; it no longer plays on its own.

## Missions


### 2 Shadow and Mist (also Evergreen bane 1)


#### Hydra regrows

- **Shows**: title **Hydra regrows**; top left: the Hydra's attack; icon: the Hydra's printed class icons.
- **Lines**:
  - Not exact: {enemy} goes face down
  - under the castle; it will come back
  - Exact damage banishes a Hydra for good
- **When**: a non-exact kill whose plan has enemy_to=castle_bottom (mission 2; Evergreen bane 1, Six is the New Four).
- **Where in the queue**: at the kill, in Defeated's place; then Clean-up lines as for Defeated.
- **Replaces**: defeated (with the row off, Defeated shows).
- **Melody**: The defeat flourish, then a bassoon slithers back up from low D to A with a hiss of shaker: heads growing back.

### 3 Lessons in Flames


#### Zone grows

- **Shows**: title **Zone: new immunity**; top left: the card's strength; icon: zone (▦).
- **Lines**:
  - End of turn: reserve top {card} joins the zone
  - Enemies are immune to every zone class:
  - {icons}{ (new: {icon})} | 'Reserve empty: nothing joins'
- **When**: zone_add in mission 3 (no source field); the empty variant when a mission 3 end of turn passes with no zone_add (derived).
- **Where in the queue**: end of turn, after Damage paid, before Turn.
- **Melody**: The zone motif (dulcimer D E A, three cards laid down) with celesta and a crackle of flame: the academy learns your class.

### 5 High and Mighty


#### Zone grows

- **Shows**: title **Zone: enemy stronger**; top left: the card's strength; icon: zone (▦).
- **Lines**:
  - End of turn: banished top {card} joins the zone
  - Enemy attack +{total} (zone: {cards}) | 'Banished pile empty: nothing joins'
- **When**: zone_add source=banished in mission 5; the empty variant derived.
- **Where in the queue**: end of turn, after Damage paid, before Turn.
- **Melody**: The zone motif on dulcimer with a bassoon swelling underneath, each note a step higher: something grows heavier.

#### Carry damage

- **Shows**: title **Carry damage**; top left: amount (carry_damage.amount); icon: carry (»); middle: amount, caption 'to {next enemy}'.
- **Lines**:
  - Exact kill: {next} takes {amount}
  - (the fallen enemy's strength)
  - Health {max} → {hp}{: it falls too!}
- **When**: carry_damage.
- **Where in the queue**: after New enemy, before Turn; a kill here continues with Defeated / Exact kill!, Clean-up and New enemy again.
- **Melody**: The Damage strike echoing twice into the distance, the echo a fifth higher: the blow carries on.

### 7 Tales of Rebirth


#### Pilgrim arrives

- **Shows**: title **Pilgrim arrives**; top left: the pilgrim's strength; icon: pilgrim (♙).
- **Lines**:
  - Start of turn: pilgrim {card} joins the zone
  - A card of strength {n} entering play may
  - banish it · on defeat: {total} reserve → discard
- **When**: zone_add source=pilgrims (also at game start).
- **Where in the queue**: start of turn, after Turn.
- **Melody**: A recorder walking tune over soft frame-drum footsteps, the zone motif as a traveller's song: gentle and hopeful.

#### Pilgrim match

- **Shows**: title **Pilgrim match**; top left: the matching strength; icon: pilgrim (♙).
- **Lines**:
  - {card} matches pilgrim {pilgrim} ({n})
  - Banish the pilgrim from the zone?
- **When**: decide{kind:pilgrim_banish}: one card per action, however many matches; the outcome is a line on the next card.
- **Where in the queue**: attack step 1b (or after a mage, flute or whistle addition), before the pilgrim box.
- **Melody**: The pilgrim's recorder tune answered by a harp on the same note (a match), then a light rising release.

### 8 Winds of Chaos


#### Zone filled!

- **Shows**: title **Zone filled!**; top left: 10; icon: zone (▦).
- **Lines**:
  - A 10 completes the zone: it goes to the
  - discard pile. Banish any discards you choose;
  - the rest heal under the reserve
  - No more zone moves this mission
- **When**: zone_cleared from a zone build, with decide{kind:discard_banish}; zone_filled (banished, healed) becomes a line on Clean-up.
- **Where in the queue**: at a defeat, during the zone building: before the banish box and Clean-up.
- **Melody**: Pan flute climbs a ladder of steps to a high D with gusts of wind (breath) and a bright bell: the zone reaches the top.

### 9 Hope From Ashes


#### Captured piles

- **Shows**: title **Captured piles**; icon: zone (▦).
- **Lines**:
  - End of turn: banish a hand card to rescue
  - a pile's top ({tops}) to the discard pile,
  - or every pile's top goes to its bottom
- **When**: decide{kind:pile_rescue} (never after a kill); pile_rescue / pile_rotate become a line on Turn.
- **Where in the queue**: end of turn, after Damage paid, before its box and Turn.
- **Melody**: Temple bells and low voices: the zone motif tolled slowly on tubular bells, a captive's plea, ending open.

### 10 Pride to Fall


#### Zone grows

- **Shows**: title **Zone: enemy stronger**; top left: the card's strength; icon: zone (▦).
- **Lines**:
  - Start of turn: reserve top {card} joins the zone
  - Enemy attack +{total}{, then ×2 (warrior enemy)} | 'Reserve empty: nothing joins'
- **When**: zone_add source=reserve in mission 10 (also at game start); the empty variant derived.
- **Where in the queue**: start of turn, after Turn.
- **Melody**: The zone motif on a dark hammered dulcimer over a slow drum in D minor: the corrupted party draws strength from the rubble.

#### Cleric enemy

- **Shows**: title **Cleric enemy**; top left: the card's strength; icon: H.
- **Lines**:
  - End of turn: the corrupted cleric takes the
  - top discard ({card}) into the zone: attack +{n} | 'Discard pile empty: nothing moves'
- **When**: zone_add source=discard in mission 10; the empty variant derived. Its Evergreen twin is bane 10, Poisonous Clerics.
- **Where in the queue**: end of turn, first, before Bard enemy and Turn.
- **Melody**: The Cleric's harp arpeggio inverted and falling in D minor into the zone motif: healing turned against you.

#### Bard enemy

- **Shows**: title **Bard enemy**; icon: D.
- **Lines**:
  - End of turn: put a hand card into the zone
  - Enemy attack + its strength | 'Hand empty: nothing moves'
- **When**: decide{kind:zone_feed, reason:bard}; zone_feed becomes a line on Turn; the empty variant derived. Its Evergreen twin is bane 12, Duplicitous Bards.
- **Where in the queue**: end of turn, after Cleric enemy, before its box and Turn.
- **Melody**: The Bard's lute run backwards and in D minor, a sly detuned strum: the corrupted bard demands a card.

### 11 Descent Into Darkness


#### Beast

- **Shows**: title **Beast: {Class}**; icon: the beast's class letter (H, D, C or S).
- **Lines**:
  - Start of turn: {Warrior: 'top discard {card} is banished' | Paladin: 'reserve top {card} is discarded' | Cleric: 'discard a card from your hand' | Bard: 'banish a card from your hand'} | 'Nothing to move: no effect'
  - {enemy}: attack {a} → {b}{ · immune {icons}} (the pile tops changed)
  - {'All four out: the beasts reshuffle'}
- **When**: beast_reveal with beast_effect and beast_reshuffle. Cleric and Bard pause on decide beast_discard / beast_banish (their effect is a line on the next card). No beast_effect and no decide: 'Nothing to move' (derived). The enemy line shows because mission 11's enemies take the discard and banished tops' strength and classes.
- **Where in the queue**: start of turn, after Turn (also at game start); before its box.
- **Melody**: A low horn growl over a frame drum (the beast motif), answered by its class's instrument in D minor (harp, lute, fiddle or horn): four renders, one row.

### 12 Decay to Growth


#### Zone grows

- **Shows**: title **Zone: stronger, immune**; top left: the card's strength; icon: zone (▦).
- **Lines**:
  - Start of turn: banished top {card} joins the zone
  - Enemy attack +{n}; immune to zone classes:
  - {icons} | 'Banished pile empty: nothing joins'
- **When**: zone_add source=banished in mission 12; the empty variant derived; zone_skip folds into Turn.
- **Where in the queue**: start of turn, after Turn.
- **Melody**: The zone motif on harp and wooden flute in D minor, brightening to D major on the last note: decay giving way to growth.

## Evergreen


### Locations


#### Shrine

- **Shows**: title **Shrine**; top left: the card's strength; icon: location (⛰︎).
- **Lines**:
  - End of turn: reserve top {card} joins the zone
  - Enemies are immune to the zone's classes:
  - {icons}
- **When**: zone_add source=reserve, location Shrine.
- **Where in the queue**: end of turn, the location first, before banes 10, 12, 23 and Turn.
- **Melody**: Hand bells and a soft chime ring the zone motif, serene as a temple.

#### Cave

- **Shows**: title **Cave**; top left: the card's strength; icon: location (⛰︎).
- **Lines**:
  - End of turn: reserve top {card} joins the zone
  - Zone {total} of {base}: at {base} or more
  - the cave collapses
- **When**: zone_add source=reserve, location Cave.
- **Where in the queue**: end of turn, the location first, before Cave collapses, the banes and Turn.
- **Melody**: Low marimba and woodblock drips in D minor, the zone motif echoing in a cave.

#### Cave collapses

- **Shows**: title **Cave collapses**; top left: zone total; icon: location (⛰︎).
- **Lines**:
  - The zone ({total}) reached {enemy}'s base
  - strength {base}: the zone and the whole
  - discard pile ({n} cards) are banished
- **When**: zone_cleared at end of turn (Cave) with discard_banished and any banish_redirect.
- **Where in the queue**: right after the Cave card, before the banes and Turn.
- **Melody**: The cave motif collapsing: tumbling drum rolls and falling marimba notes, stones settling on a low D.

#### Forest

- **Shows**: title **Forest**; top left: the card's strength; icon: location (⛰︎).
- **Lines**:
  - End of turn: banished top {card} joins the zone
  - Enemy attack +{total}
- **When**: zone_add source=banished, location Forest.
- **Where in the queue**: end of turn, the location first, before the banes and Turn.
- **Melody**: Pan flute and birdsong trills with a shaker rustle: the zone motif in the woods.

#### Hills

- **Shows**: title **Hills**; top left: the card's strength; icon: location (⛰︎).
- **Lines**:
  - End of turn: banished top {card} joins the zone
  - Team damage {total} follows{ | 'A Guardian prevents the team damage'}
- **When**: zone_add source=banished, location Hills; team_damage_prevented of the same action gives its second variant.
- **Where in the queue**: end of turn, the location first, then Team damage, then the banes and Turn.
- **Melody**: A horn calls across the hills with an echo and a distant drum: the zone motif as a warning.

#### Lake

- **Shows**: title **Lake**; top left: the card's strength; icon: location (⛰︎).
- **Lines**:
  - Start of turn: {pilgrim | reserve top} {card} joins the zone
  - On defeat: banish 1 reserve card per zone card
- **When**: zone_add, location Lake (also at game start). Its defeat step (lake_banish) is a line on Defeated / Exact kill!.
- **Where in the queue**: start of turn, after Turn, before banes 16 and 22.
- **Melody**: Harp ripples like water under a recorder: the zone motif rippling.

### Banes


#### Poisonous Clerics

- **Shows**: title **Poisonous Clerics**; top left: the card's strength; icon: bane (☠︎).
- **Lines**:
  - End of turn: the enemy has a cleric icon:
  - the top discard ({card}) joins the zone
- **When**: zone_add source=discard under bane 10 (mission 10's Cleric enemy is its twin).
- **Where in the queue**: end of turn, after the location card, before bane 12, bane 23 and Turn.
- **Melody**: The bane sting, then the Cleric's harp arpeggio falling in D minor into the zone motif.

#### Duplicitous Bards

- **Shows**: title **Duplicitous Bards**; icon: bane (☠︎).
- **Lines**:
  - End of turn: the enemy has a bard icon:
  - put a card from your hand into the zone
- **When**: decide{kind:zone_feed, reason:bane12}; zone_feed becomes a line on Turn (mission 10's Bard enemy is its twin).
- **Where in the queue**: end of turn, after bane 10, before its box.
- **Melody**: The bane sting, then a sly lute strum doubled slightly out of tune with itself.

#### Absorbtion

- **Shows**: title **Absorbtion**; icon: bane (☠︎).
- **Lines**:
  - The killing attack ({cards}) joins the zone,
  - not the discard pile · zone now {total}
- **When**: zone_absorb.
- **Where in the queue**: at a defeat, after Clean-up, before Explosive Spores and New enemy.
- **Melody**: The bane sting, then a low bassoon slide down that swallows the zone motif.

#### Tread Carefully

- **Shows**: title **Tread Carefully**; icon: bane (☠︎).
- **Lines**:
  - Not exact: the whole discard pile ({n})
  - is banished before the location's steps
- **When**: discard_banished emitted before defeat on a non-exact kill (its position tells it apart from m12 and the Cave).
- **Where in the queue**: after Defeated, before the location's steps and Clean-up.
- **Melody**: The bane sting, then tiptoeing pizzicato that trips into a spill of cards.

#### Lingering Dread

- **Shows**: title **Lingering Dread**; icon: bane (☠︎).
- **Lines**:
  - Start of turn: the top discard ({card})
  - is banished | 'Discard pile empty: nothing moves'
- **When**: bane{n:16}; the empty variant derived (bane 16 in play, no bane event at the start of turn).
- **Where in the queue**: start of turn, after the Lake card, before bane 22.
- **Melody**: The bane sting, then a slow tolling bell over a viol drone, in half time.

#### Eye-Level Sticks

- **Shows**: title **Eye-Level Sticks**; top left: attack strength; icon: bane (☠︎).
- **Lines**:
  - Your attack holds a card of strength 8+:
  - discard a card from your hand (if you can)
- **When**: decide{kind:attack_discard}; attack_discard becomes a line on the next card.
- **Where in the queue**: attack step 1b, after the entry cards, before boon 30 and the relic cards; before its box.
- **Melody**: The bane sting, then sharp woodblock knocks (sticks) and a startled fiddle yelp.

#### The Fiery Crucible

- **Shows**: title **The Fiery Crucible**; icon: bane (☠︎).
- **Lines**:
  - Start of turn: the reserve top ({card})
  - goes to the discard pile
- **When**: bane{n:22}.
- **Where in the queue**: start of turn, last.
- **Melody**: The bane sting, a crackle of fire (shaker), and a fiddle figure flaring upward then falling.

#### Choose Your Poison

- **Shows**: title **Choose Your Poison**; icon: bane (☠︎).
- **Lines**:
  - End of turn: discard a card from your hand,
  - or the reserve top joins the zone
- **When**: decide{kind:poison}; poison, or poison_skip and its zone_add, become a line on Turn.
- **Where in the queue**: end of turn, last before Turn; before its box.
- **Melody**: The bane sting, then an oboe asking the same two notes again and again (D, E-flat): a question that will not go away.

### Boons


#### Squad of Siblings

- **Shows**: title **Squad of Siblings**; top left: attack strength; icon: boon (✦).
- **Lines**:
  - Zone card {card} matches your attack ({n})
  - Move it to the discard pile?
- **When**: decide{kind:zone_sibling}; the outcome is a line on the next card.
- **Where in the queue**: attack step 1b, after bane 21, before the relic cards; before its box.
- **Melody**: The boon lift, then two recorders in unison stepping along together.

#### Selfless Rescue

- **Shows**: title **Selfless Rescue**; top left: the matched strength; icon: boon (✦).
- **Lines**:
  - You discarded a {n}; the zone holds a {n}
  - Move that zone card to the discard pile?
- **When**: decide{kind:zone_match}: one card per action, however many matches; the outcome is a line on the next card.
- **Where in the queue**: after Damage paid, before its box and the end-of-turn cards.
- **Melody**: The boon lift, then a horn call answered by a harp: a rescue.

#### Precision Strike

- **Shows**: title **Precision Strike**; icon: boon (✦).
- **Lines**:
  - Exact kill: put a zone card or the top
  - discard into your hand
- **When**: decide{kind:precision_strike}; precision_strike becomes a line on Clean-up.
- **Where in the queue**: at an exact kill, after Exact kill!, before boon 33, the location's steps and Clean-up; before its box.
- **Melody**: The boon lift, then one bright pluck and a bell ringing on high D: right on target.

#### Restored Arrows

- **Shows**: title **Restored Arrows**; icon: boon (✦).
- **Lines**:
  - Exact kill: you may put one banished card
  - under the reserve
- **When**: decide{kind:restored_arrows}; the outcome is a line on Clean-up.
- **Where in the queue**: at an exact kill, after boon 32; before its box.
- **Melody**: The boon lift, arrows whooshing past (breath), then a harp run upward.

#### A Close Call

- **Shows**: title **A Close Call**; top left: damage paid; icon: boon (✦).
- **Lines**:
  - Paid exactly {damage}: the discarded cards
  - go under the reserve, not the discard pile
  - Now put any discard on top of the reserve
- **When**: close_call (emitted before suffer; the builder shows it after Damage paid) with decide{kind:close_call}; close_call_pick becomes a line on the next card.
- **Where in the queue**: after Damage paid, before the pick box and the end-of-turn cards.
- **Melody**: The boon lift, then a nervous fiddle tremolo that resolves to D at the very last moment.

## How one action becomes a queue of cards

1. ONE ACTION, ONE QUEUE, PLUS A CARRY BUFFER.
- After each action (_act), a builder turns three things into an ordered list of cards: the pre-action snapshot (undo_stack[-1]), g.last_events and the pending decision.
- The table refreshes underneath. The queue then plays on the App root, one landscape card at a time, before any decision box, handover or result screen; those wait underneath and appear when the last card closes.
- A tap anywhere on the card advances. The tap that started the action never skips card 1.
- Some cards gather events from several actions (Mage's pick, Druid's sorting, Chanter's draw, Clean-up, outcome lines, the Emblem count). The builder keeps those in a carry buffer, App.info_carry:
  - it is saved with the autosave;
  - it is pushed with each undo snapshot, so Undo restores it;
  - a save resumed mid-sequence shows the result card with what the buffer holds. A save without a buffer shows only the current action's part.
  - Lines that arrive after their card was shown (mission 8's discard_pick, bane 13's team discards) go on New enemy or Turn.

2. CARD ORDER IS EVENT AND BOX ORDER, with these placements.
- (a) A Jester alone: the Jester card ends step 1 (base, claim or solo new hand). The Legacy solo Jester gives its Jester card, then its class card.
- (b) Entry effects, in the engine's order:
  - Corrupted and Restored come at once, as each card enters (on_cards_played).
  - Then the declarations: the declare box, then Declared; or Declared at once when the kinfolk set forces the value.
  - Then the Evergreen Mother card and its box, then that card's Corrupted card.
  - Then Pilgrim match, Eye-Level Sticks, Squad of Siblings, Scarlet Whistle and Kinfolk Flute, each card right before its box.
  - A card added later (a mage pick, a flute or a whistle) runs its entry cards again.
- (c) Classes, in the engine's power order (Legacy M U H D T R C S G; base H D C S): one card per class present. A class shows once per attack, however many cards carry it. A multi-class card gives one card per class (Gøran renewed, Esme, the Best Friend puppy, Evergreen cards, multi-sticker cards, a Wild Animal's declared class). A Gøran or Evergreen play therefore always gives Cleric, Bard, Warrior and Paladin, each with its own melody, on a kill too.
- (d) The step-3 slot: Reaver's pick, then the Warrior card with the big damage number. With no unblocked Warrior, the Damage card takes that slot. A blocked Warrior gives the stamped Warrior card, then the Damage card.
- (e) Paladin and Guardian always show:
  - When the enemy survives they give their effect, and the Guardian card stands in for No damage.
  - On a kill they read 'Not needed: {enemy} fell', or for the Guardian, the team damage it prevents. They come before Defeated.
- Top left: the attack's strength at that moment, after declarations, relic additions and mage picks. The Mage shows its peek strength.
- The first card of each attack carries one formation line, for example 'Beast copies 7: 7♥ + B = 14', 'Kinfolk 3♣ 3♠ = 6', '3♦ from the flute' or 'Ben adds 2♦ (Kinfolk Flute)'.
- 2+ players with the Azure Emblem: the Mage card comes first, then the Azure Emblem card, then the placement boxes.

3. IMMUNITY.
- Any power{immune} shows that class's own card, as the owner asked: the same breakdown in 'would' form, greyed, with the red diagonal IMMUNITY stamp, at most one line naming the source, and the shared IMMUNITY jig.
- A chained mage that the immunity blocks gets a stamped 'Mage again' card.
- The IMMUNITY row governs every stamped card, whatever the class rows say.
- When immunity is ignored, the card is normal, with an 'ignores immunity ({why})' line. The reasons are corrupted, restored or Evergreen cards; a claimed Jester attack; the Legacy solo Jester; and the base Jester's cancellation (game.immunity_cancelled).
- Myla's fixed immunity is never ignored. It belongs to the 20/80 boss only (mission 9 and Evergreen bane 5) and covers bards and paladins only. The Myla of missions 5 and 6 is a different card.

4. DECISIONS IN BETWEEN.
- A phase that pauses gets its card BEFORE its box: Mage, Druid, Chanter, Reaver, relic triggers, bane and boon choices, Captured piles, Bard enemy, Pilgrim match, Zone filled, Beast (Cleric/Bard), Defeated / Exact kill! before the defeat boxes. The queue ends there, and the answering action's queue continues the same attack.
- The one exception is declare_value / declare_class: the box asks itself, and Declared follows as the outcome.
- Mage, Druid, Chanter and Reaver also get a result card once their boxes are done: Mage's pick, Druid's sorting, Chanter's draw, Reaver's pick. Each chained mage gives another Mage card.
- Every other rule's outcome becomes one line on the next card shown. End-of-turn choices go on the Turn card. Defeat-step choices go on Clean-up, or on New enemy or Turn when Clean-up was already shown.
- A re-ask of the same kind never repeats a card: flute, whistle and emblem queues, each druid sort, chanter discards, team discards, and the duplicated team-damage decide. Pilgrim match, Selfless Rescue and Declared show one card per action.
- Order-only questions have no card: discard order, reaver order, clean-up order, banish order and zone order. The card before them says why the order matters.

5. A KILL.
- The Warrior or Damage card (health → 0), then Paladin, then Guardian.
- Then Defeated, Exact kill! or Hydra regrows: what happens now, with the mission's steps.
- Then the defeat-step cards, each before its box: boons 32 and 33, bane 15, Team damage (m6), Zone filled (m8).
- Then Clean-up (what happened). With no box between the kill and the clean-up, Clean-up folds into Defeated or Exact kill!.
- Then Absorbtion (bane 14) and Team damage (bane 13).
- Then either Victory, or New enemy, then Carry damage (m5; a second kill repeats from Defeated), then Turn ('{player} again', with 'no end-of-turn effects' and the m11/m12 skip lines), then the start-of-turn cards.

6. THE ENEMY SURVIVES.
- Enemy attacks, or Mission lost when the hand cannot pay.
- Then the suffer action: Feign death, Damage paid, A Close Call, Selfless Rescue.
- Then the end-of-turn cards in engine order:
  - the mission: Zone new immunity (m3), Zone enemy stronger (m5), Captured piles, Cleric enemy, Bard enemy;
  - the location: Shrine, Cave, Cave collapses, Forest, Hills plus Team damage;
  - banes 10, 12 and 23.
- Then Turn for the next player.
- Then the start-of-turn cards: Pilgrim arrives, Zone enemy stronger (m10), Zone stronger immune (m12), Beast, Lake, banes 16 and 22.
- Mission lost comes last if the new player cannot act.

7. YIELD. Yield, then Enemy attacks, No damage or Guardian, then as in 6.

8. GAME START AND GAME OVER.
- A fresh game queues: the mission rules card (if on), Battle start (holding the first enemy), Turn (2+ players only), then the start-of-turn cards. A resumed save shows no cards.
- Victory or Mission lost is always the last card. Its clip is the victory or loss jingle, which no longer plays separately. It is the heading of the result overlay, with the overlay's buttons under it.

9. MERGING AND PRECEDENCE, in this order.
- (1) The master box ✗: no cards; today's short step sounds (audio.sounds_for) come back.
- (2) A row switched off: its card is skipped.
  - A replacing card falls back to the card it replaces, if that card's row is on: Warrior → Damage; Guardian → No damage; Exact kill! and Hydra regrows → Defeated; Victory or Mission lost → the result overlay as today.
  - The stamped card with IMMUNITY off becomes one line, '{Class} blocked by immunity', on the next card.
- (3) A skipped card's outcome moves as one line to the next card shown. A pre-box card that is skipped leaves nothing, because its box asks for itself.
- (4) These events are always lines, never cards: heal, draw, add_to_play, whistle_take, mage_pick parts, emblem_keep, druid_assign, chanter_discard, reaver_reveal/pick/order, cleanup_order, zone_cleared, reserve_discard, banished_shuffled, team_discard, team_damage_done, team_damage_prevented, reserve_redirect, zone_filled.
- (5) Paladin and Guardian show on a kill whenever their rows are on; item (3) never removes them.
- (6) banish_redirect events from one action make one Mother (restored) card.
- (7) Enemy changes is dropped when another card in the queue already states the attack and immunity.
- (8) Missions 1 and 4 have no cards of their own. Mission 4's top-discard strength shows on New enemy, Enemy changes and Enemy attacks; its experiments play as Corrupted.

10. SETTINGS.
- The row reads 'Info Pop Ups [✓] ›'. ✗ shows no cards and brings back the short step sounds.
- › opens every pop-up's own row, one row per pop-up, as the owner asked. The rows sit in collapsible groups, collapsed by default, in turn order: Turn, Attack, Jester, Classes (IMMUNITY first, each class followed by its result card), Damage & defeat, Enemy, Enemy strikes, Game end, Missions (one group, sub-headed per mission), Evergreen (locations, banes, boons).
- Each row shows its icon, its fixed settings label and a ✓/✗ box. Tapping a row's label previews that card with its clip.
- The master box keeps the per-row choices: info_popups plus an info_popups_off list, so new rows default to on.

11. WORDING.
- Base mode: class titles become ♥ Hearts, ♦ Diamonds, ♣ Clubs, ♠ Spades; 'reserve' becomes 'tavern deck'; Exact kill! reads '→ top of the tavern deck'.
- 'You' appears only in solo. With 2+ players every card uses names, because the phone passes between players.
- Lines are 40 characters at most. A card with a middle number holds 3 lines at most (about 58 pt under the number); other cards hold 6. The longest variants are rendered with render_info.py before building.
- Never name cards that go into hidden hands or the reserve (Bard, Chanter, Druid, Azure Emblem, the mage's peek): show counts per player. Team damage never shows the hands' total with 2+ players.

12. SOUND.
- Each card's clip starts as the card appears. Clips play through sound.Player, so they can fade: advancing ramps the volume to 0 over 50 ms, stops the clip and starts the next one.
- Music ducks to about 40% through the music Player's volume while a clip plays.
- A step that a shown card covers loses its short sound (hit, power_*, draw, suffer, discard, new_enemy, jester, yield).
- The info queue never goes through show_card_popup, which always plays the 'popup' flip (screens.py:2972).


## Landscape and portrait

LANDSCAPE: InfoCardFace (already in app/widgets.py).
- Size: 360 × 230 pt on a 390-pt phone, min(360, width − 2·MARGIN) wide, 0.64 × width high.
- Layout: the number top left, the icon to its right, the title after it, a rule in the card's colour, then the breakdown. Damage cards have a 60-pt middle number with a caption.
- The owner said 'landscape does well for descriptors or non-playable/game cards', so these are landscape:
  - every info card in this catalogue, including New enemy (it describes the arrival; the enemy's own card stays portrait everywhere else);
  - the result overlays' heading (Victory / Defeat);
  - the existing descriptor pop-ups:
    - the attack card from the table header (_show_attack / attack_face);
    - relic cards (PartyScreen._show_relic; the RelicCard tile in the deck list becomes a landscape tile);
    - reward and setup choice cards (_show_choice_card);
    - Evergreen location, bane and boon cards (EvergreenScreen._card_block);
    - the mission rules card, landscape with a scrolling body.

PORTRAIT stays exclusive to playable and game cards:
- hand and table cards, and cards in pile views;
- castle and enemy cards;
- the party deck list;
- mercenary cards (MercenaryScreen);
- Jesters, beasts, pilgrims, Myla, Gøran and the High Arcana.

EDGES: the class colour (T.SUIT_COLOR); corrupted purple (T.CORRUPTED); restored green (T.RESTORED); Jester purple; locations Evergreen green; banes T.DANGER; boons T.ACCENT; enemy and defeat cards T.CARD_BORDER.

ICONS: draw_symbol draws any short text, so each icon is a text-style glyph (with U+FE0E where an emoji form exists).
- Classes: SUIT_SYMBOL; the Evergreen tree: TREE_PIP.
- Jester: 'J' in Jester purple, as on the Jester's face.
- Turn ↻, yield ⚐, mission ⚑, enemy ♚ (or the enemy's own printed class icons), defeat ⚔︎, exact ◎, clean-up ≡, team ⁂, victory ♛, loss ✕.
- Zone ▦, location ⛰︎, pilgrim ♙, bane ☠︎, boon ✦, carry ».
- Relics: flute ♪, whistle ♬, emblem ◈, mother ❦ (purple corrupt, green restored).
- A 2/5 shows the text '2/5'.
- Corrupted and Restored have no icon: the owner ruled out a corrupted icon, so the sleeve colour is the card's edge. Damage, Feign death and Damage paid have no icon either.
- Every new glyph must be checked on the phone, as the class glyphs were.

TOUCHES: InfoCardFace swallows touches today (touch_began/ended pass). Queue cards set touch_enabled = False so that a tap anywhere advances. Portrait card faces keep swallowing touches as they do now.


## UI sounds

THE OWNER'S PICKS ARE MODELS.
- The owner clarified that the Pythonista built-ins are references for our own acoustic sounds, not sounds to play (commit a91043a; tools/export_sound_refs.py exports them for study). The critic's suggestion to play them by name is therefore set aside.
- Because every card sound is our own render, the card-sound pickups can be baked into the info clips.
- card_select (modelled on casino:CardPlace1) and card_deselect (CardPlace4) cover every card tap: the hand, decision grids (Druid sorting, discard and banish picks, mage, reaver and emblem picks, zone choices, close call, restored arrows, precision strike), reward picks, the beast picker and cards moved in order boxes.
- Play an attack: no sound (audio.SILENT). Its pop-ups speak for it.
- draw (modelled on CardShuffle, with less shuffle and more single cards): one card slide per card, up to four, then a short riffle. It plays for hand refills, draws, the Jester's new hand and Chanter draws. It is the pickup of the Bard card.
- shuffle (modelled on CardFan1, a bit less speedy): any shuffle (Cleric heal, Druid deal, banished-pile shuffles, the beast deck reforming). It is the pickup of the Cleric and Druid cards.
- discard (modelled on CardTakeOutPackage2, a few cards put on a stack): discards to pay damage, and chanter, team and bane discards. It is the pickup of Damage paid.
- button (modelled on ui:switch21, with a deeper wooden-knock candidate, since the owner asked 'or maybe something deeper?'): every enabled navigation button (menus, Resume, Undo, Back, Save, settings rows, the handover's ready button).

ACTION BUTTONS. make_button wraps every action with TAP_SOUND (widgets.py:21-31). Under the new rules:
- Play never clicks.
- Yield, Discard, decision-box Confirm and decision options do not click when their action starts an info card or a card sound: the result speaks.
- When such an action produces nothing audible (rows off, nothing shown), the click plays, so no press is silent.

NEW ACOUSTIC SOUNDS, to add to tools/audio/catalog.py for the owner to pick:
- toggle: a wooden peg click, higher for ✓ and lower for ✗. For the Info Pop Ups box, every row's box and the settings switches. The master box is a new control, a tick/cross box with a separate › tap target, not a ui.Switch (screens.py:4377).
- expand / collapse: a small wooden box lid opening and closing, for the › chevron and each collapsible group.
- segment: an abacus bead sliding and clicking, for segmented controls (number of players, pile tabs).
- pile_open: a short fan of cards spread on felt, when a pile (discard, banished, castle, reserve) or the row of played cards is tapped to view it.
- card_down: one card laid softly on a stack. It plays when a portrait pop-up or pile view is closed by a tap beside it, when the last info card of a queue is dismissed, and when 'Hold to view game' is released.
- peek_lift: a card lifted off felt, when 'Hold to view game' (PeekButton) is pressed. That button can be pressed, so it is not silent.
- map_stop: a wooden token set down on parchment, for the campaign map's stops.

EXISTING SOUNDS TO KEEP, made acoustic:
- coin: hiring a mercenary or gaining coins.
- error: an enabled control that refuses, such as an illegal play.
- popup: a card flip, for portrait pop-ups and for player-opened descriptor cards that have no clip of their own (see the open questions).

TEXT FIELDS (player names on the new-game screen): the iOS keyboard's own clicks only.

INSIDE INFO QUEUES:
- Each card's clip is its sound. The tap that advances is silent, because the next clip starts at once.
- Only the last dismissal plays card_down.
- A settings row preview plays that card's clip.

SILENCE RULES:
- Anything that cannot be pressed is silent: greyed hand cards, disabled buttons, dimmed grid cards, the enemy card, text, the background, scrolling and dragging.
- While an info card shows, nothing else plays under its clip, apart from the ducked music.
- A step that a shown card covers loses its short sound.


## Melody plan

ONE FAMILY.
- 74 rows. Battle start, Victory and Mission lost reuse the mission_start, victory and loss jingles. The four Jester rows share one clip, the Whistle jig.
- The Beast row needs four renders, one per class.
- That makes 71 new renders: 67 one-row clips, the extended Whistle jig and the extra Beast renders. IMMUNITY is a row, counted once.
- Every clip is 2.0 to 2.4 s, never under 2.0 s.

THE WHISTLE JIG.
- Today's whistle_jig.wav is 1.92 s (families/combat.py:783 calls _finish(..., 1.95, ...)), and catalog.py:52 caps the jester event at 2.0 s.
- Re-render it at about 2.2 s, with one more bar and a held cadence on D, and raise the cap to 2.6 s.
- It is the default clip for all four Jester rows. The claim, new-hand and attack variants are extra candidates only.

THE GRAMMAR EVERY CLIP SHARES.
- KEY: D, like the Whistle jig (D major: A B A F# D F# A B D').
  - Party news is in D major (mixolydian for folk colour).
  - The enemy and the banes are in D minor or dorian.
  - Magic is in D lydian.
  - Every clip ends on D. A card shown just before a box ends open on A (a question), and its result card answers on D.
- PULSE: the jig's grid. An eighth note is 0.11 s and a dotted quarter 0.33 s, in 6/8. Slow cards (Guardian, Enemy attacks, Lingering Dread) move at half time on the same grid.
- SHAPE, in three parts:
  1. The pickup, about 0.12 s: a soft card flick and one plucked harp D, the info-card signature. Cards that stand for a card action use our own card sound instead, baked into the clip: the shuffle for Cleric and Druid, the draw for Bard, the discard stack for Damage paid.
  2. A two-bar motif on the card's signature instrument, about 1.3 s.
  3. A held cadence and the shared tail, about 0.6 s.
- ROOM AND MASTER:
  - The Whistle jig's tavern reverb (room 0.35, wet 0.16), high-pass at 100 Hz and low-pass at 7.5 kHz, mono.
  - Mastered as jingles at about −20 dB gated RMS.
  - Turn and Yield are 3 dB softer. Enemy attacks, Exact kill! and IMMUNITY are 1 to 2 dB louder.
- BAND: acoustic only, from the General MIDI set in tools/audio/sf.py:
  - winds: recorder, tin whistle, wooden flute, pan flute, French horn, bassoon, oboe;
  - strings: fiddle, viol, cello, lute (nylon guitar), harp, hammered dulcimer;
  - bells: celesta, glockenspiel, hand bells, tubular bells;
  - voices and drums: humming voices, bodhrán, frame drum, tabor, timpani, woodblock, shaker.
  - No synths.

LEITMOTIFS: about 20 ideas in different colours.
- CLASSES, one instrument each:
  - Mage: celesta, a lydian question; Mage's pick answers it.
  - Druid: pan flute, dorian trills; Druid's sorting answers.
  - Cleric: harp, a rising arpeggio.
  - Bard: lute, a strummed run.
  - Chanter: humming voices, a plainchant call; Chanter's draw settles it.
  - Reaver: cello and woodblock, a digging figure; Reaver's pick leaps an octave.
  - Warrior: fiddle and tabor, a figure played twice, the second time an octave up (the doubling).
  - Paladin: French horn, a sustained fifth with a shield ring.
  - Guardian: low strings and timpani, a wall chord.
  - A Gøran attack therefore sounds like the band taking turns.
- STRIKE: bodhrán and lute for Damage, echoed for Carry damage.
- JIGS: the Whistle jig is every Jester. The IMMUNITY jig is its dark twin: the same rhythm on bassoon and fiddle in D minor, stopped by the stamp thump.
- ENEMY MOTIF (D F E D, horn and low drum), heard in:
  - New enemy;
  - Enemy changes, twisted on low strings;
  - Enemy attacks, on brass and war drum;
  - No damage, blocked by the Paladin's horn;
  - Damage paid, resolved on lute;
  - Team damage, with frame drums all round.
- DEFEAT FLOURISH (a falling lute run): Defeated. Exact kill! turns it upward (harp glissando, celesta). Hydra regrows adds a bassoon climbing back. Clean-up sweeps the cards.
- ZONE MOTIF (hammered dulcimer D E A: three cards laid down), coloured by each place:
  - Missions: m3 celesta and a flame crackle; m5 a swelling bassoon; m7 recorder and footsteps; m8 a pan-flute ladder and wind; m9 temple bells and voices; m10 a dark dulcimer and drum; m12 minor turning major.
  - Locations: Shrine hand bells; Cave marimba drips; Forest pan flute and birds; Hills an echoing horn; Lake harp ripples.
  - Mission 11's beasts: a horn growl answered by the beast's class instrument (four renders).
- RELICS sound like what they are named after:
  - Kinfolk Flute: two flutes in thirds.
  - Scarlet Whistle: tin whistle and dulcimer.
  - Azure Emblem: glockenspiel and harp.
  - Evergreen Mother: one lullaby, on viol and low flute in D minor when corrupt, on harp and flute in D major when restored.
- CORRUPTED AND RESTORED mirror each other: a falling half step, B flat to A, on viol with a cracked bell; then the same notes rising to D on harp and flute.
- EVERGREEN: every bane opens with the bane sting (a low pizzicato D rubbing against E flat, with bassoon). Every boon opens with the boon lift (recorder A rising to D over harp). Then comes the card's own phrase.
- QUIETEST CLIPS: Turn (lute A then D, with a hand bell) and Yield (a viol sigh).

PRODUCTION.
- Add an 'Info pop-ups' group to EVENTS in tools/audio/catalog.py: one jingle event per row (info_<id>), 2.0 to 2.4 s, min_seconds 2.0 so nothing shorter passes.
- Write a family module, families/info.py, that builds every clip from the shared pickup, a motif table and the shared tail. A change to the room or the pickup then re-renders the whole set.
- Render two candidates for the cards heard most (the nine classes, IMMUNITY, Damage, New enemy, Enemy attacks, Defeated, Exact kill!, Turn) and one for the rest.
- The picker page plays them in queue order, so the owner judges them as a sequence. A Gøran kill plays Cleric, Bard, Warrior, Paladin, Defeated.
- Size: 71 × about 2.2 s comes to about 14 MB as 44.1 kHz WAV, about 7 MB at 22.05 kHz, or 1 to 2 MB as m4a.


## The owner's answers (these override the catalogue above)

1. A killing blow shows no Paladin and no Guardian card.
2. Mage, Druid, Chanter and Reaver show one card each, before their box; there are no
   result cards (Mage's pick, Druid's sorting, Chanter's draw, Reaver's pick): what was
   chosen is an outcome line on the next card shown.
3. A pop-up switched off in the settings is removed from the experience completely: no
   card, no sound and no line in its place. A card that replaces another falls back to it
   (Warrior to Damage, Guardian to No damage, Exact kill! and Hydra regrows to Defeated,
   Battle start to New enemy); with the IMMUNITY row off, stamped cards are not shown.
4. A long press skips the rest of a queue.
5. Cards the player opens (the rules card, relics) keep the short card-flip sound.
6. Clips are WAV.
7. Icons are chosen on a picker page, where every slot may also have no icon.

Built in the lab: app/info.py (the card spec, the rows, the builder context), the builders
app/info_turn.py, info_classes.py, info_defeat.py, info_missions.py and info_evergreen.py,
and the queue on screen, app/info_view.py. The Druid's and the Chanter's strength is drawn
muted and struck through (it does nothing).
