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

### Round: magic and rare packs

Monster life by rarity comes from the hidden rarity mods on poe2wiki: MonsterMagic2 gives 148% more life
(x2.48), MonsterRare2 gives 700% more (x8). PoB has no rarity life table. Clear is now taken over a pack mix by
count: total monsters / total time.

The first try ranked the clear skill alone against tougher packs, and the backtest got worse as packs got harder:

| mix (white/magic/rare) | pre_asc1 | act1 |
|---|---|---|
| white only | 8/8, 0.77 | 8/8, 0.71 |
| 80/20/0 | 8/8, 0.65 | 8/8, 0.69 |
| 60/30/10 | 7/8, 0.59 | 7/8, 0.68 |
| rare only | 5/8, 0.51 | 5/8, 0.46 |

It drags high single-target skills up. Community setups do not clear rares with the clear skill: they carry a
boss skill. Modelled as a loadout, a rare-led pack is cleared by whichever is faster: the clear skill alone, or the
clear skill on the whites plus the class's top boss skill on the rare. With that, 60/30/10 holds 8/8 on both stages
(MRR 0.65 / 0.71) and 50/35/15 gives 8/8 (0.67 / 0.71).

It still does not beat white-only on pre_asc1 (0.77). Sorceress moves from Contagion + ED to Living Bomb (2.40 vs
2.27), and Mercenary from Explosive Grenade to Rapid Shot. The mix is an assumption; the pack counts were not
measured. (This round first kept white-only ranking for its higher MRR; the review round below reverses that.)

The mixed figure is still informative. For Witch it puts Contagion + ED (4.14) well above Essence Drain alone
(2.05). On white packs alone the solo clear-support ED edged ahead of the pair (8.02 vs 7.80), which read wrong
against how the build is played.

### Round: independent review (Fable) and evaluation fixes

An independent review, given the code and this log without conclusions, made these points. The numbers were checked
before acting on them.

- **Top-3 is a weak bar once the family filter is on.** Families hold 9–25 rows, so a random order within the family
  passes about 4.3 of 8 classes on pre_asc1. Druid, with 7 accepted rows out of 13, passes by chance 93% of the time.
  Top-1 was only 5/8 (pre_asc1) and 4/8 (act1).
- **act1 is not held out.** It uses the same classes and answer key, and it was consulted throughout the loop; x0.25
  was preferred over x0.35 on act1's word.
- **Fire-and-forget scored a DoT at cast time however long it took to kill.** Vine Arrow (37 DoT DPS against 89-life
  act1 monsters, 2.4s to kill) was scored at 0.65s. It ranked 1st for act1 Ranger and 2nd for act1 Warrior, despite
  being off-family there.
- **Keeping white-only ranking for MRR 0.77 vs 0.65 was fitting to the key.** The gap is two classes moving from rank
  1 to rank 2 at n=8.

Changes:

1. **Evaluation.** The backtest now also reports:
   - top-1;
   - the rank within the class family against a uniformly random within-family order (expected top-1, top-3, MRR);
   - a permutation p-value.

   The answer key is frozen and a test pins its hash.
2. **DoT.** A DoT that kills within its duration now costs `max(cast time, time to die − travel)`, and every pack adds
   2s of walking. Travel of 1–5s gives the same backtest; 0s with the honest DoT drops to 7/8.
3. **Ranking uses the campaign mix (60/30/10) with the clear + boss loadout.** White-only is a CLI column.

| config | pre_asc1 top-3 / top-1 / MRR | family MRR (random) | p | act1 top-3 / top-1 / MRR | p |
|---|---|---|---|---|---|
| before (white, cast-time DoT) | 8/8, 5/8, 0.77 | 0.77 (0.44) | 0.003 | 8/8, 4/8, 0.71 | 0.009 |
| honest DoT, no travel | 7/8, 3/8, 0.65 | 0.65 (0.44) | 0.038 | 7/8, 2/8, 0.62 | 0.09 |
| + travel 2s | 8/8, 5/8, 0.75 | 0.75 (0.44) | 0.004 | 8/8, 4/8, 0.75 | 0.009 |
| + campaign mix and boss loadout (shipped) | 8/8, 4/8, 0.69 | 0.69 (0.44) | 0.018 | 8/8, 4/8, 0.73 | 0.015 |

The shipped config ranks Contagion + ED first for Witch and Sorceress, above ED alone. Vine Arrow leaves Warrior's
top 4.

Still open:

- **Vine Arrow is still act1 Ranger's #1.** Its DoT is a planted ground area. Monsters that chase the player leave it,
  but the model treats it like a debuff. A ground/debuff split for fire-and-forget is the principled fix; it was not
  applied to one skill by hand.
- **Mana and EHP** are next, as displayed vetoes rather than fitted factors.
- **Independent labels are needed before more tuning.** Sources: asc1 picks for other classes, a second guide
  source, or 0.4 vs 0.5 changes.

### Round: held-out keys, scored once (2026-11-24)

Two new answer keys were frozen before scoring (`HELDOUT_SOURCE2`, `HELDOUT_ASC1`; a test pins their hash). Each was
scored once with the shipped config. Neither was used for tuning.

| key | n | top-3 | top-1 | MRR | family MRR (random) | p |
|---|---|---|---|---|---|---|
| pre_asc1, second guide source | 8 classes | 8/8 | 6/8 | 0.83 | 0.83 (0.58) | 0.018 |
| asc1 (level 32, 2 ascendancy points) | 19 ascendancies | 8/19 | 3/19 | 0.36 | 0.37 (0.32) | 0.20 |

The pre-ascendancy model holds on an independent source. **At asc1 it is no better than chance.**

Why, from the per-ascendancy output:

- **The ascendancy barely moves the ranking.** Every ascendancy of a class gets nearly the same top 5. Witch's three
  all show Contagion + ED, Living Bomb, Bonestorm. Monk's two are identical.
- **Guides pick skills that the ascendancy is built around.** Those are the misses:

  | ascendancy | guide pick | our rank |
  |---|---|---|
  | Blood Mage | Spark | 6 |
  | Stormweaver | Ice Nova | 7 |
  | Tactician | Galvanic Shards | 21 |
  | Shaman | Fury of the Mountain | 45 |
  | Acolyte of Chayula | Staggering Palm | 12 |
  | Pathfinder | Poisonburst Arrow | 7 |
  | Ritualist | Spearfield | 7 |

  Two points of ascendancy at level 32 add little DPS in PoB. Guides still pick these skills because they scale with
  the later ascendancy nodes and gear. Our model scores the level-32 snapshot only.
- **Hits:** Infernalist and Lich (Contagion + ED, #1), Deadeye (Ice Shot, #1), Witchhunter and Gemling (Explosive
  Grenade, #2), Titan and Warbringer (Leap Slam, #2), Oracle (Entangle, #3).
- **Sorceress inherits Witch's list.** The family filter only checks gem colours and the starting weapon, so both
  classes rank the same Intelligence spells.

Conclusion: do not tune on this key; it is spent. The asc1 output should not be shown as a recommendation without a
caveat. Candidate fixes need a fresh key: score with the ascendancy's full node set or a later stage (for example
level 45, 4 points), or rank skills by the ascendancy's own tags.

### Round: asc2 held-out, one tuning round, and a change of direction (2026-11-25)

Changes before the asc2 run:

- **asc1 is ranked per class.** It no longer uses an ascendancy.
- **asc2 stage facts corrected from 0.5.x guides.** Trial of Chaos, Act 3, about level 38–40:

  | setting | was | now |
  |---|---|---|
  | level | 45 | 40 |
  | gem level | 11 | 10 |
  | support tier | 4 | 3 |

- **All four ascendancy points are spent, notable-first** (`ascFill`). The greedy pick used to stop at zero gain.
- **"Any Martial Weapon" skills** are probed with the class weapon. Shockwave Totem had 0 DPS before.
- **When two variants tie on DPS**, the one with an area is kept.

`HELDOUT_ASC2` was frozen and hash-pinned before collection. It covers 21 ascendancies from maxroll and poe-vault
0.5.x guides; Smith of Kitava has no current guide and is excluded.

Scored once:

| test | family MRR (random) | p |
|---|---|---|
| independent entries, as in earlier rounds | 0.52 (0.38) | 0.023 |
| class-clustered: one random order per class | 0.52 (0.38) | **0.068** |
| ascendancy-blind: per-class median across ascendancies | 0.55 (0.38) | 0.039 |

The pass rests on Monk (Storm Wave, ×3) and Witch (Essence Drain, ×3). Huntress, Ranger and Sorceress score below
random. The ascendancy-blind ranking does as well as the per-ascendancy one, so the ascendancy adds no measurable
signal.

**Tuning round 1.** The split was pre-registered by class:

- tune half: Witch, Mercenary, Druid, Ranger;
- check half: Sorceress, Huntress, Monk, Warrior.

| change | result | decision |
|---|---|---|
| **DoT bug fix.** A DoT part's combined DPS can include the hit (Vine Arrow Vines: 684, of which 68 is DoT). The DoT part now counts only its DoT. | tune 0.554 → 0.562; check unchanged; no regression | kept |
| no movement penalty for attack dashes | no change | dropped |
| melee-strike reach default | no change | dropped |
| pack cap 8 or 10 | asc2 clustered p falls to about 0.02, but pre_asc1 regresses (p 0.017 → 0.07) | rejected |

A stage-specific pack size would have no source and would be fitted to the key, so it was not tried.

After the round: family MRR 0.525 vs 0.382, clustered p 0.061.

**Direction review (independent).** Ranking every skill by a PoB snapshot is the wrong model after ascendancy:

- Before ascendancy, the decision is which class skill clears fastest now. The model answers that and holds on an
  independent source.
- After ascendancy, a player already has a target skill. The questions are:
  - when that skill becomes playable;
  - what bridges until then;
  - what each ascendancy step buys.
- The asc keys mix two things: the strongest skill now, and the build's identity skill. A correct snapshot model
  could still fail them.
- The known gaps form a long tail: minions counted as one body, totems, poison, melee targets, conditional variants,
  ascendancy-granted skills, and a pack cap that saturates casters.

Decision:

- asc1 and asc2 leveling output is ascendancy-blind and labelled experimental.
- Per-ascendancy lists are no longer shown.
- No further tuning on `HELDOUT_ASC2`.
- Post-ascendancy work moves to target-based tools, in this order:
  1. ascendancy checkpoints at 2/4/6/8 points;
  2. a switch-readiness checklist (discrete gates per stage);
  3. target vs bridge ratio;
  4. a bridge on the target's tree path, with respec gold;
  5. a patch-diff re-run of gates and checkpoints.

  Each is validated on a new key of about 15 guide builds, frozen before scoring.

### Round: ascendancy checkpoints, scored once (2026-11-25)

**Tool.** `checkpoints --skill X --class C` puts one skill on a class template at the asc2 stage. It spends two
points per trial, notable-first, on the node that adds most DPS, and records the nodes and the DPS after 2/4/6/8
points. A step that adds nothing is flagged "no DPS gain".

**Key.** `pob_agent/checkpoint_key.py`, frozen and hash-pinned before the run:

- 23 guide builds from maxroll and poe-vault 0.5.x, all 8 classes;
- every node name checked against the PoB 0.5 tree.

**Pre-registered metrics:**

- **M1:** our first notable is the guide's first.
- **M2:** overlap of the first two notables.

There were 20 scorable entries. The two minion builds were skipped because their target is not a gem; Spiral Volley
was skipped because its order is only in an image.

| metric | ours | random |
|---|---|---|
| M1, first notable | 6/20 | 3.6 (p 0.13) |
| M2, first two notables | 0.38 | ~0.36 |

The damage-greedy order does not reproduce guide orders. What the per-entry output shows:

- **Hits are damage-first notables:**
  - Eldritch Empowerment (Essence Drain Lich);
  - Constant Gale (Arc and Ice Nova Stormweaver);
  - Unleash Hell! and A Solid Plan (Tactician);
  - Critical Strike (Rake Amazon);
  - the Gemling order, which matched all four.
- **Misses are mostly defensive or utility firsts:**
  - Soulless Form;
  - Zealous Inquisition;
  - Predatory Instinct;
  - The Lesser Harm;
  - Answered Call.

  Survivability is not scored, so a damage-only order cannot match these.
- **Many steps add no DPS**, and there the pick is arbitrary: tree order among equals.
- **Three targets had zero DPS on the template** (Walking Calamity, Shield Wall ×2). They are now reported as errors
  instead of arbitrary picks.

**Decision.**

- The tool is kept as a damage view: what each notable adds to this skill.
- Its output now says it is not a recommended order and gives the score above.
- A recommended order would need a survivability or utility score, which is not built.
- The key is spent for order and is not tuned on. Its switch fields (bridge, switch level, gate) are still unscored,
  for the switch-readiness checklist.

### Round: switch-readiness checklist, scored once (2026-11-25)

**Tool.** `switch --skill X --class C` reads each gate from game data. Nothing is fitted.

| gate | how it is read |
|---|---|
| skill gem | The tier is the uncut gem level the skill needs. poe2wiki gives the area level where each uncut level drops: L2 at 4, L5 at 15, L10 at 37, L14 at 58. Levels in between are interpolated, and character level is assumed to track area level. |
| tier 0 | The ascendancy notable whose text grants the skill is named. It counts from the first trial, about level 22. With no granting notable, the skill comes from an item or reward. |
| weapon | The weapon types the skill accepts, against the class's starting weapon. |
| attributes | The gem's attribute requirement at the level usable then. |
| spirit | The reservation is shown; spirit income is not modelled. |

**Scoring.** The switch fields of `CHECKPOINT_KEY` were scored with metrics registered in its docstring before the
run. 16 entries were scorable. Seven were skipped: three targets come from items or rewards, two are no-switch
builds, and two give no switch point.

| metric | result |
|---|---|
| S1: the guide never switches before our gate | 16/16 |
| S2: the guide switches in the same act as our gate | 13/16 (a naive "Act 1 for everything" baseline: 6/16) |

Numeric cases land within 3 levels:

| build | our gate | guide switch |
|---|---|---|
| Ice Shot | 33 | 31 |
| Walking Calamity | 53 | 52 |
| Spiral Volley | 53 | 54 |
| Shield Wall | 24 | 22 |
| Arc | 15 | 14 |

The three misses all switch later than the gate, for reasons the gates do not cover:

- Supporting Fire (Tactician) at 36: respec gold and four supports.
- Whirling Assault in maps: needs a 400+ physical DPS quarterstaff.
- poe-vault Ice Nova in Act 2: waits for level-5 gems.

The gate is the earliest point; whether to switch then is a build decision.

## Target vs bridge, bridge on the target tree, patch tie-in (2026-11-25)

### Fixes found on the way

- Shield Wall and Shield Charge probed 0 DPS: the weapon template had no shield. `templateWeapon` now builds an
  armour shield. Shockwave Totem probed 0 DPS: "Any Martial Weapon" now resolves to the class's martial weapon.
  act1 and pre_asc1 caches were re-probed for these skills. The backtests did not move: pre_asc1 8/8 in top 5,
  4 at #1, MRR 0.69, p 0.015; act1 MRR 0.73; second source 0.83.

### Target vs bridge (`bridge`, free tree)

For each stage the target skill, as played (no family factor), is compared with the best leveling skill
probed the same way. Scoring was registered in `checkpoint_key.py` before the run: the guide plays the target
at a stage iff the stage level is at or past its switch point. Rule A plays the target iff our gate is open;
rule B also needs target clear >= bridge clear.

Disclosure: a syntax check of the scoring script printed two rows from partly collected data. The rules were
already written; nothing was changed after it.

| rule | agreement with guides (44 entry-stage pairs, 11 builds) |
|---|---|
| always play the target | 36/44 |
| A: gate only | **40/44** |
| B: gate and ratio >= 1 | 14/44 |

Rule B is worse than doing nothing. Guides switch as soon as the target is usable, even where our ratio puts it
at x0.2–x0.9 of the bridge (Bleed Rake x0.19, Ice Strike x0.37, Arc x0.55–0.73). Either the guides take a
slower skill to avoid a second respec and gem budget, or the model underrates targets on a leveling tree
without their supports; this data cannot separate the two. `use_target` now follows rule A; the ratio is
shown as information only.

### Bridge on the target build's tree (`bridge --build`)

`register_target` stores a build's notables; the class is re-probed with the tree restricted to them, and the
free-tree bridge's notables off that path are priced with PoB's `goldRespecPrices`. Sample (Twister Gemling
Legionnaire): free tree act1 x0.87 (10 points, 1,280 gold to respec), pre_asc1 x1.19 (25 points, 8,600 gold);
on the target tree x1.15 and x1.49.

Check registered before running: the class's pre_asc1 leveling pick stays in the top 3 on the target tree.
Passed for both builds tried (Mercenary: Explosive Grenade #2; Witch on the Werewolf Lich tree: Contagion +
Essence Drain #2). Two builds is a smoke test, not an evaluation.

### Patch tie-in (`gate-diff`)

`Engine(pob_src=...)` runs another PoB checkout; `gate_diff` compares each skill's tier, weapon types, spirit
cost and ascendancy grant between two checkouts. Same-checkout diff is empty (test). A dry run against an
older PoB-PoE2 has not been done: it needs a download.

## Third source: devilcatpoe.com (2026-11-25)

devilcatpoe.com is a Traditional Chinese guide site written by veteran players. From its build and leveling
guides we took facts only: skill names, levels and acts. No text or tables were copied. Labels and scoring
rules were registered before the run. Every guide is tagged 0.5 and marked under review, so these are weak
labels.

Guides used, one primary class each:
- chaos/Bonestorm (Witch);
- Oil Barrage (Huntress);
- grenade crossbow (Mercenary);
- Twister (Huntress);
- Lightning Arrow into Ice Shot (Ranger);
- Invoker (Monk);
- Titan (Warrior);
- Chronomancer (Sorceress);
- dragon Druid.

| check | result | random / baseline |
|---|---|---|
| act1 ranking: family top 3 | 7/8, MRR 0.52 | 3.0, 0.32 (p 0.029) |
| pre_asc1 ranking: family top 3 | 6/8, MRR 0.60 | 3.3, 0.36 (p 0.019) |
| switch: never before our gate | 9/9 | |
| switch: same act as our gate | 9/9 | "Act 1 for all" 3/9 |

**Ranking.** Most guide picks overlap the development key: Contagion + Essence Drain, Lightning Arrow,
Rolling Slam, Twister and grenades. The ranking therefore mostly shows this source agrees with ones we tuned
on, rather than testing it independently. The new picks are Flash Grenade (Mercenary, #2–3), Frozen Locus
(Monk pre_asc1, #4) and Cross Slash (Druid, #6). Misses:
- Monk's act1 "Contagion spells" has no setup given and ranks low.
- Druid's Contagion and Essence Drain, from a speedrunner, rank low.
- Huntress's Tear is not probed for Huntress.

**Switch.** All 9 numeric switches fall within 2 levels of our gate:
- Essence Drain: gate 8, guide 6.
- Ember Fusillade: gate 15, guide 13.
- Ice Shot and Oil Barrage: gate 33, guide 31.
- Whirling Assault: gate 43, guide 45.

**Ascendancy order.** Not scorable: only the Monk guide gives an order, and its node names cannot be verified.

## DoT skills: support choice and run-to-run determinism (2026-11-26)

**Problem.** PoB splits some skills into stat sets. Supports and passives were judged on the first set only. For
Essence Drain that is the projectile hit, but its clear comes from the DoT set, so hit supports were picked.

**Fix.** A skill with a DoT-only stat set (no hit, not one of the conditional labels the ranking skips) is now
valued as the first set plus the best DoT-only set. The DoT set gets full credit only if one cast kills a magic
monster at the stage level within its duration:

`ddps × min(1, ddps × duration / magic life)`

This stops supports that buy DoT DPS with a shorter duration (Swift Affliction) from winning. Every other skill
is valued exactly as before. On the Python side, the fire-and-forget kill time is no longer a cliff. When one
cast deals fraction f of a monster's life, the time is f × fire-and-forget + (1 − f) × standing (config
`ff_soft`, default on).

**Rounds.** Five rounds, each registered before its run, with gates fixed in advance and an independent review
(Fable) after each.
- **Round 3** failed: Swift Affliction cost the Contagion + Essence Drain pair its one-cast kill on act1 magic
  packs.
- **Round 4** valued every hit set as well. It failed for three reasons:
  - Enemy-state-gated sets scored at full value (Shockwave on a Shocked, Marked or Primed enemy).
  - Lua and Python disagreed on which hit set counts (Ember Fusillade's chaining Beam).
  - A zero-DPS first set blinded the tree search (Frozen Locus).

  These three are pre-existing model issues, filed separately.
- **Round 5** is the narrow fix above.

**Round 5 result.** Baseline and new code collected with the same template and the same determinism fixes, for 8
classes across act1 and pre_asc1, with and without clear supports. Every gate passed:
- **Rankings:** dev pre_asc1 0.771 = 0.771, dev act1 0.729 = 0.729, source2 0.771 = 0.771, devilcat pooled
  0.656 = 0.656. No class moved.
- **DoT-dominant skills:** pre_asc1 Essence Drain clear ×1.165 (Witch) and ×1.077 (Sorceress), Vine Arrow
  ×1.36 / ×1.32. Nothing went down.
- **Per-skill score:** 736 multi-set entries, none down more than 5%.
- **One-cast kill:** the act1 pair now kills a magic pack per cast (276 and 271 against 221 life).
- **Equality check:** 3136 of 3200 cache entries are identical. The 64 that differ are Essence Drain and Vine
  Arrow, the only skills with a DoT-only set.

The review then found the DoT factor was set only by `leveling_probe`. Checkpoints in a fresh engine had no
factor, and a shared engine used whatever the last probe left. The factor is now set per skill, and a test
checks that both commands pick the same supports.

**Nondeterminism found on the way (all fixed).** LuaJIT seeds its string hash per process, so `pairs` order
changes between runs:
- **Earthquake's Aftershock radius:** the set has two stats both mapped to skill radius, so it came out 2.1 or
  3.0 per run. The set's own mapping now wins. It is the only such stat in the data; a test pins the count.
- **Exact ties:** support candidates (Cold vs Fire Attunement) and tree nodes went either way. Both are now
  iterated in sorted order.
- **Shared gem names:** four names are shared, e.g. Unleash is both a spell and a support. A chosen Unleash
  support sometimes resolved to the spell and did nothing (Druid Arc act1: 39.6 or 32.2). Support lookups now
  ask for a support.

**Headline numbers move: a re-score, not tuning.** The determinism fixes and the new template change the
committed act1/pre_asc1 caches in about half their entries:

| metric | previous cache | after |
|---|---|---|
| dev pre_asc1 fam MRR | 0.646 | 0.771 |
| dev act1 fam MRR | 0.583 | 0.729 |
| source2 (held-out) fam MRR | 0.792 | 0.771 |

On source2, Warrior 2 → 3, Druid 1 → 2, Monk 2 → 1. The DoT fix itself moved no rank metric; the baseline equals
the new code on every one.

**Recollected since.** The asc1, asc2, ascendancy-specific and bridge-target caches were recollected on
2026-11-27; see "Recollection and one-time re-score" below for the re-scored held-out numbers.

**Open, not fixed here.**
- **Hourglass picks.** Vine Arrow with clear supports picks Hourglass + Prolonged Duration I. This was first
  blamed on cooldown; the actual cause is target attribution (see the Vine Arrow section below).
- **Single-set DoT skills get no duration factor** (Contagion, Profane Ritual).
- **Reports use a different measure than the picker.** Fixed for ascendancy checkpoints (2026-11-27). Their DPS
  is now the first set plus the DoT set, with no kill factor, so Essence Drain Lich's 8-point lift reads x1.43
  instead of x1.59. Infernalist goes 2.39 → 1.96 and Blood Mage 1.11 → 1.05. Picks and the checkpoint-key score
  are unchanged. Build-up, campaign and ascendancy-lift still report first-set DPS: switching them needs the
  support scan's numbers in the same unit.

## Vine Arrow: hit ailments counted once (2026-11-27)

**Problem.** PoB's hit set for Vine Arrow (Impact) already includes the hit's poison and bleed in its combined
DPS. The DoT-only Vines set's TotalDotDPS repeats that same ailment on top of the vines' own DoT. Example, Ranger
act1:
- Impact: 20.64, of which 5.52 is the ailment.
- Vines: 15.98 of its own DoT, plus the same 5.52.

Both the support picker and the ranking added the two sets, so single-target DPS was overstated by up to 31%
(mean 5%). Over the whole cache, only Vine Arrow has this gap. Essence Drain's DoT set has none.

**Fix.** When a hit set is counted, a DoT-only set adds only its own DoT (TotalDot), in both Lua and Python.
Vine Arrow's single-target DPS now equals PoB's Vines combined DPS. The `dot` field used by Contagion pairs is
unchanged.

**Gates and result.** Registered before the run, with gates approved and the result reviewed by Fable. All
passed:
- **Essence Drain:** entries identical to before.
- **Vine Arrow:** single-target DPS equals PoB's total within 0.5% in all 32 entries.
- **Picks:** the picker's own value never fell below the old picks'.
- **Rankings:** unchanged (0.771 / 0.729 / 0.771, devilcat 0.656).
- **Other skills:** over 37,212 metrics on the whole cache, nothing changed for any other skill.

Ranger's Vine Arrow scores lower but keeps its rank: act1 served 0.999 → 0.903, still #1; pre_asc1 0.850 →
0.801, still #2.

**Exposed, not fixed here.** With the inflated ailment gone, Vine Arrow in the pre_asc1 clear-support collection
now picks Prolonged Duration I + Hourglass in every class, as act1's already did. Python scores that entry
lower, and every consumer takes the better of the plain and clear-support collections, so served ranks do not
change (the plain entry wins in all 75 Vine Arrow class × stage pairs).

The cause was first thought to be cooldown. It is target attribution: the Lua picker weights Impact's hit by
its own target count (1) and the Vines by their area (5.4 targets), while Python multiplies hit plus DoT by the
larger count, so it credits Impact's 0.8 m hit with 5.4 targets. Fixing that moves served ranks (Vine Arrow is
Ranger #1 / #2), so it is left for a decision. Hourglass is also picked for other skills in served stages
(Contagion, Profane Ritual, Rain of Arrows, Thunderstorm), where uptime against its cooldown is not checked.

**Filed.** Witchhunter's combined DPS carries a multiplier that TotalDot lacks. It affects 2 Vine Arrow asc2
entries (single-target DPS 7.3% below PoB's total) and does not touch the gated stages.

## Recollection and one-time re-score (2026-11-27)

Every leveling cache other than act1 / pre_asc1 (and their clear-support variants, already current) was
recollected with the committed code: 116 class × stage files. Vine Arrow was then re-probed in all of them with
the hit-ailment fix. Two bridge-target files for the Lich target cannot be recollected because their target
definition no longer exists; they keep their old entries. 6,430 entries changed.

The held-out keys were then scored once, frozen, with no tuning. "Before" is the live cache immediately before
the swap, so it differs from the asc2 figures published earlier in this note:

| test | before | after |
|---|---|---|
| asc2 class-clustered fam MRR (random 0.38) | 0.549, p 0.038 | 0.571, p 0.024 |
| asc2 tune half | 0.613 | 0.662 |
| asc2 check half (random 0.36) | 0.491, p 0.148 | 0.488, p 0.154 |
| asc1 per-class fam MRR (random 0.31) | 0.346, p 0.30 | 0.342, p 0.32 |

The gain is all in the tune half; the check half is flat and still not significant, so it is not evidence of
better generalisation. asc1 stays at chance. The pre_asc1 / act1 numbers (0.771 / 0.729 / source2 0.771,
devilcat act1 0.60, pre_asc1 0.76) and the ascendancy checkpoint key (M1 6/19, random 3.4) do not read these
caches and are unchanged.
