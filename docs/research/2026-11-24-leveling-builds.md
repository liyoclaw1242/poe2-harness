# Early (pre-ascendancy) builds in 0.4 and 0.5: methodology notes

Date: 2026-11-24. Sources: public guides and official patch notes, gathered by two web-research passes. Reddit,
mobalytics, poe2wiki, game8 and pobarchives blocked automated fetches, so several facts rest on search snippets;
those are marked. "Fastest" claims come from video titles and commercial blogs, not measured data.

## 1. What people actually level with

| archetype | 0.4 | 0.5 | damage comes from | clear comes from | source |
|---|---|---|---|---|---|
| Essence Drain + Contagion (chaos DoT, "凋零"), Bonestorm/Dark Effigy for bosses | Witch standard | still the Witch standard, guides carried forward unchanged | gem level and +skill levels, not the weapon | Contagion spreads the DoT | maxroll ED Lich leveling guide; poe-vault chaos leveling |
| Grenades (Explosive, then Gas/Oil) | Mercenary | Mercenary, Ranger/Huntress variants | crossbow base (upgrades at about lv 4/10/16/33) | overlapping AoE | maxroll grenade leveling guides |
| Whirling Slash + Twister | Huntress | Spear Huntress on maxroll list | spear base | Twister projectiles; movement built in | video titles, snippets |
| Werewolf (Lunar Assault/Shred, Pounce, Cross Slash) | Druid | Druid (Oracle) | talisman base | Lunar Assault; freeze then shatter | maxroll werewolf Oracle; poe-vault |
| Bear (Volcano, Maul, slams, Rampage) | Druid | Druid (Shaman) | talisman base, Rage | slams | maxroll shapeshift leveling |
| Minions (Snipers, Raging Spirits) | Witch | Sorceress→Varashta spike after ascending | minion gems | minions | snippets |
| Ice Shot / Lightning Arrow, Glacial Cascade, Boneshatter | various | maxroll 0.5.5 list | weapon | projectiles / AoE | maxroll list |

No 0.5 evidence for Rapid Shot, Galvanic Shards or Living Bomb as leveling skills (guides only from 0.2–0.3), or
for Wither on its own (only as an amplifier inside ED/Contagion via Withering Presence).

## 2. Availability facts (calibrate the campaign stages)

- Fixed quest uncut skill gems: L2 (Clearfell stash, Devourer), L3 (Rust King), L4 (Hunting Grounds, Ogham
  Farmlands), L5 (Act 1 end), L6/L7 (Act 2), L9/L10 (Act 3). Source: maxroll league-start guide.
- Drops by area level (poe2wiki, snippet): skill gem L2@4, L5@15, L10@37, L14@58; support tier 2@16, 3@33, 4@45,
  5@55. poe-vault agrees on supports by act.
- Gems have 2 support sockets until Lesser Jeweller's Orbs (monster level 25+); 4th socket in Act 4 (poe-vault).
- Trial 1 (2 points) in Act 2, level about 21–28 (sources conflict, some say delay to 28); Trial 2 in Act 3.
- 0.5.0: campaign martial weapons are more likely to be the highest base for the level (helps attack levelers);
  areas shortened, density reduced in the second half.
- Shred is granted by any talisman set to Werewolf form, gem level 1 has no level requirement (poe2db).
  Changeling Talisman has no requirements; Nettle lv5 9 Str/8 Int; Familial lv16 21/16; Frenzied lv22 28/20.
  Maxroll: werewolf melee is weak at levels 1–3, use Entangle first. Leveling uniques: Amor Mandragora (1–16),
  Hysseg's Claw (16–38).

## 3. Methodology: what makes a good pre-ascendancy build

1. **Damage source vs gear supply.** Gem-scaled spells (ED) need no weapon luck; weapon-scaled attacks need a
   steady stream of bases, which 0.5 made more reliable. A leveling pick should state which one it is and plan
   weapon breakpoints when it is weapon-scaled.
2. **Clear mechanism, not single-target DPS.** Every popular leveler has a cheap clear engine (spread, overlapping
   AoE, projectiles, minions). Single-target is handled by a second skill (Bonestorm, Dark Effigy, Shred).
3. **Availability timeline.** The quest gem schedule is fixed, so a skill's usable level is known; talisman skills
   are available from level 1 if a talisman is found.
4. **Tree start and attributes.** Class start decides nearby notables and the attribute cost of off-colour weapons
   (talisman Str, crossbow Str/Dex for a Witch).
5. **Transition cost.** The best leveler for a target build is not the strongest leveler overall but the one whose
   tree and gear carry into the target (ED Witch → respec; werewolf Druid → no switch).
6. **Safety.** Ranged, minions, freeze or stun.

## 4. Where our PoB-only campaign scan disagrees, and why

Our pre_asc1 scan ranked Rapid Shot, Ember Fusillade, Bonestorm and Living Bomb on top and Essence Drain 27th,
Contagion 64th, minions unranked. The research says ED/Contagion is the Witch standard. The gap is in our model:

- Essence Drain: only the projectile hit is measured; its DoT is another skill part (TotalDot = 0).
- Contagion: value is spreading to a pack; single-target DoT is 21.
- Minions: minion DPS lives in mainOutput.Minion, which the scan does not read.
- Galvanic Shards: likely multi-projectile counting; unverified.
- Item-granted skills (Shred) have Tier 0 and are filtered out.
- No clear-speed, safety or attribute-requirement terms; no weapon upgrade curve.

Fixes, in order: read all skill parts and minion DPS; add a pack/clear proxy (spread, AoE, projectile count);
enforce attribute requirements with the threshold module; model weapon breakpoints per stage; include
talisman-granted skills.

## 5. How leveling builds are derived (reverse-engineered), and the harness plan

Players satisfice constraints, then choose by clear mechanism; our scan maximises one scalar (single-target DPS).
Inferred procedure (E = evidenced by §1–3, I = inferred):
1. Enumerate what exists at each point: quest gem schedule, support tiers, sockets (E).
2. Classify damage source: gem-scaled vs weapon-scaled, plan weapon breakpoints (E).
3. Pick a clear engine by mechanism, then a separate boss skill (E).
4. Gate on attributes / tree from the class start, mana with no gear, safety (E for attributes and safety, I for mana).
5. Bridge weak windows with a stopgap (E for werewolf lv1–3, I as a rule).
6. Minimise transition cost to the target build (E).
7. Optimise time per zone, not DPS; overkill is worthless (I).
8. Carry guides forward until patch notes break them (E as outcome).

Harness changes, in order (PoB hooks verified by grep, not yet by running):
1. Measure the whole skill: every stat set (Essence Drain's DoT is a stat set, `srcInstance.statSet`,
   Build.lua:385) and minion output (`output.Minion`; FullDPS with `includeInFullDPS`). Small.
2. Feasibility gates: ReqStr/Dex/Int (thresholds), mana `ManaPerSecondCost` vs `ManaRegenRecovery`, Spirit. Small.
3. Availability from the quest schedule; include item-granted skills (talisman Shred) by equipping the base. Medium.
4. Pack-clear proxy: targets covered (AoE radius, projectile/pierce/chain count, duration, spread tag) ×
   min(1, damage per use / white monster life from `data.monsterLifeTable`); boss time-to-kill separately. Medium.
5. Rank pairs (clear + boss skill) on the same class/tree/weapon. Medium.
6. Gear robustness: DPS at weapon one tier behind / best base / typical magic roll. Small–medium.
7. Continuity cost to a target build (respec nodes, weapon type, attributes). Medium.
8. Safety tags + EHP as a displayed veto, not scored.

Validation: per-class backtest (Witch → ED+Contagion, Mercenary → grenades, Huntress → Twister, Druid → werewolf/bear)
must land in the top 3 pairs; negative controls (Rapid Shot, Galvanic Shards, Living Bomb not top for Witch);
ablation one change at a time; tune on 0.4 picks, test on 0.5 differences.

## 6. Backtest loop (2026-11-24)

Setup: `leveling.collect` probes every skill a stage allows, per class start (greedy tree from that start, no
ascendancy), and caches raw PoB facts (all stat sets, minion output, area/projectile/pierce/chain, mana,
attributes, cooldown/stored uses, white monster life). `leveling.rank` scores from the cache; `tools/
leveling_backtest.py` checks each class's community pick lands in its top 3 and runs an ablation (each row adds
one term). 111 skills x 8 classes per stage; a collection takes ~12 min on 3 processes.

Engine fixes found by the loop:
- Support gems with levels (Unleash) were pasted at level 20: Int requirement 157 at character level 24.
  Now capped like skill gems.
- Greedy supports by single-target DPS picked Concentrated Area in 447 of 888 probes, shrinking every area.
  A "clear" support objective (DPS x monsters reached) now picks Magnified Area for grenades.
- Minion skills were invisible (DPS lives in output.Minion); Essence Drain's DoT is its second stat set.
- PoE2 attribute nodes are a free choice but PoB books them as Str, so a Witch shows Str 47 at level 24;
  attribute shortfall is computed against the pool gained over the class base.

pre_asc1, first collection (supports by DPS):

| step | passed | MRR |
|---|---|---|
| v0 first stat set, single-target DPS | 0/8 | 0.07 |
| + all stat sets and minions | 0/8 | 0.06 |
| + skip conditional variants (Charged/Infused/Enraged) | 0/8 | 0.07 |
| + attribute requirements (free pool) | 0/8 | 0.07 |
| + pack-clear proxy | 1/8 | 0.08 |
| + Contagion spread pairs | 2/8 | 0.21 |
| + class starting weapon (off-weapon x0.5) | 3/8 | 0.38 |
| + spells off-family for martial classes | 5/8 | 0.42 |
| + setup skills (corpses, consume a state) x0.5 | 5/8 | 0.51 |

Act 1 snapshot (level 12, gems to L5, tier-1 supports): 4/8, MRR 0.51 with the same terms.

Reading: single-target DPS alone ranks the community picks 5th–54th. What moves them is (a) the Contagion
pair, (b) the class's weapon family, (c) clear over single-target. Off-weapon x0.25 gives 6/8 (MRR 0.62);
at that strength the term is close to a hard family filter, i.e. the backtest then measures ranking within the
class's weapon family, which is the question a player who has picked a class actually asks.

Second round (supports chosen per role, burst, fire-and-forget), pre_asc1 using both collections (damage
supports and clear supports; a skill keeps its better solo score, pairs use damage supports):

| step | passed | MRR |
|---|---|---|
| + spells off-family for martial classes | 5/8 | 0.34 |
| + setup skills x0.5 | 4/8 | 0.38 |
| + stored-use burst (grenades: 3 uses cover a pack, cooldown refills between packs) | 5/8 | 0.44 |
| + DoT fire-and-forget (a DoT that kills within its duration costs one cast, not the kill time) | 6/8 | 0.56 |
| off-weapon factor 0.25 (≈ ranking within the class's weapon/spell family) | 7/8 | 0.74 |

Held-out check: the Act 1 snapshot (level 12) was not used for any tuning: 7/8, MRR 0.66 at the same settings.
Sensitivity at 0.25: pack 4/6/10 → 6/7/6 passed; density 0.15/0.3/0.6 → 6/7/6; setup factor 0.3–0.8 → 7/7/7.
Terms that moved nothing: default radius for radius-less area skills, cooldown rotation (burst covers it),
attribute point cost (the free attribute pool covers every requirement at level 24).

Boss skill (single-target DPS, same family factors, no tuning): Witch → Bonestorm 1st, which matches the
community's ED/Contagion + Bonestorm pairing.

Still failing: Druid (shapeshift picks rank 13–21; spells and ED/Contagion outrank them). Two engine causes
found: Lunar Assault has no radius in PoB data (crescent), and tree mods "while shapeshifted" were off because
the probe did not set PoB's `conditionShapeshifted` — now implied by any shapeshift skill (recollecting).
Warrior passes at 0.25 (Boneshatter 2nd behind Earthquake).

User's Witch → Werewolf Lich: restricting the tree to the target build's notables (no-respec path) keeps
Contagion + Essence Drain first (96% of its free-tree clear); werewolf skills before ascendancy clear 8–20x
slower (Shred is single-target; no Wildwood Solace or Eternal Life yet). The research's Witch fallback (level
with ED/Contagion, respec to Shred) is what the model also says.

Third round: class family from gem colour. PoE2 gem attribute splits follow the class archetypes (Int: Witch/
Sorceress; Str/Int: Druid; Dex/Int: Monk; Str/Dex: Mercenary; Str: Warrior; Dex: Ranger/Huntress), and a
class's base attributes above 7 are exactly its archetype. A skill is in the class family when its gem split
equals the class's primary attributes AND (for weapon skills) the weapon is the class's starting weapon. This
replaced the hand-written caster list and fixed Druid (spells like Essence Drain are Int-only, Druid is Str/Int).
Correction recorded: the first Druid expectation list missed Cross Slash, Pounce and Shockwave Totem, which the
research table rows list; it was corrected before this round.

Final config (`leveling.DEFAULT`), leave-one-out:

| removed term | pre_asc1 passed | MRR | act1 (held out) passed | MRR |
|---|---|---|---|---|
| (none: final config) | 8/8 | 0.77 | 8/8 | 0.71 |
| all stat sets + minions | 4/8 | 0.54 | 6/8 | 0.62 |
| skip conditional variants | 8/8 | 0.83 | 6/8 | 0.75 |
| attribute check | 8/8 | 0.77 | 8/8 | 0.71 |
| pack-clear proxy | 6/8 | 0.32 | 3/8 | 0.32 |
| Contagion pairs | 8/8 | 0.77 | 8/8 | 0.67 |
| family (gem colour + weapon) | 2/8 | 0.31 | 2/8 | 0.31 |
| setup skills x0.5 | 7/8 | 0.61 | 7/8 | 0.68 |
| stored-use burst | 7/8 | 0.67 | 7/8 | 0.61 |
| cooldown rotation | 8/8 | 0.77 | 8/8 | 0.71 |
| DoT fire-and-forget | 7/8 | 0.65 | 7/8 | 0.62 |

Terms that earn nothing on this set: attribute check (the free attribute pool always covers level-24
requirements) and cooldown rotation (burst covers grenades). Kept for later stages where they may bind, flagged.
The shapeshift condition fix also changed nothing (no "while shapeshifted" damage within 25 points of Druid).

Ascendancy stages (asc1 = after trial 1, 2 points; asc2 = after trial 2, 4 points). The greedy ascendancy pick
missed Eldritch Empowerment (the ED Lich guide's first node) because its 30% more needs PoB's "Are you
Sacrificing?" box. Config checks gated on a flag that one of the ascendancy's own nodes grants are now turned on
(same idea as the enabler table); the greedy pick then matches the guide. Two scoring holes found at asc1:
Incinerate's "Ignited Ground" variant (a lingering ground effect, now treated as conditional) and Lightning Warp
(a movement skill, now x0.2 as a main skill). With both fixed, Witch asc1 is Contagion + Essence Drain first for
Lich, Infernalist and Blood Mage; pre_asc1 and act1 backtests unchanged (8/8, 8/8).

Known limits: white monsters only (clear saturates once a DoT kills within its duration, so extra damage stops
counting); no gear beyond a plain weapon base (Eldritch Empowerment's ES cost, Necromantic Conduit's mana drain
are not checked); the backtest set is 8 classes x 1–8 picks, mostly from maxroll/poe-vault guides.
