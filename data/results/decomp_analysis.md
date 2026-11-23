# Multiplier decomposition — 99 PoE2 0.5.5 builds

Leave-one-out: x2.00 = removing that layer/source halves the main skill's DPS. gear_product = product of per-slot (item vs blank same base).

## Layer medians

| layer | median | p75 | p90 |
|---|---|---|---|
| supports | x1.64 | x2.09 | x5.72 |
| ascendancy | x1.24 | x1.58 | x5.80 |
| tree | x11.70 | x22.21 | x48.14 |
| tree_small | x2.03 | x2.53 | x4.14 |
| gear_product | x12.60 | x22.22 | x67.66 |
| conditions | x1.56 | x3.04 | x6.24 |

## Layer of each build's largest single multiplier (excluding the main weapon)

gear 58, condition 14, support 12, ascendancy 7, jewel 4, notable 2, keystone 1

## Most impactful recurring sources (n builds × log median multiplier)

| layer | source | builds | median | max |
|---|---|---|---|---|
| condition | multiplierRage | 36 | x1.50 | x2.97 |
| gear | Runeseeker's Call, Runemastered Runic Fork | 7 | x5.68 | x10.18 |
| support | Rakiata's Flow | 15 | x2.18 | x3.00 |
| gear | Rathpith Globe, Sacred Focus | 4 | x9.87 | x23.56 |
| gear | Wildwood Solace, Spiny Talisman | 4 | x5.74 | x5.85 |
| support | Garukhan's Resolve | 12 | x1.68 | x1.82 |
| support | Elemental Armament II | 22 | x1.25 | x1.33 |
| condition | conditionEnemyShocked | 25 | x1.20 | x1.47 |
| support | Execute III | 17 | x1.30 | x1.69 |
| keystone | Eldritch Battery | 11 | x1.50 | x1.81 |
| ascendancy | Advanced Thaumaturgy | 17 | x1.30 | x6.20 |
| gear | Mageblood, Utility Belt | 21 | x1.23 | x1.81 |
| jewel | Prism of Belief, Diamond | 19 | x1.25 | x1.63 |
| jewel | Heart of the Well, Diamond | 40 | x1.11 | x1.33 |
| gear | Fury of the King, Ashbark Talisman | 2 | x8.13 | x8.22 |
| condition | usePowerCharges | 20 | x1.23 | x19.35 |
| gear | Blight Bane, Sinister Quarterstaff | 2 | x6.52 | x7.52 |
| support | Concentrated Area | 14 | x1.30 | x1.32 |
| gear | Kalandra's Touch, Ring | 19 | x1.20 | x1.44 |
| gear | Constricting Command, Viper Cap | 4 | x2.24 | x3.15 |
| keystone | Pain Attunement | 15 | x1.23 | x1.28 |
| gear | Crown of Eyes, Vermeil Circlet | 5 | x1.80 | x3.38 |
| support | Close Combat II | 13 | x1.25 | x1.34 |
| gear | Nightfall, Glacial Fortress | 2 | x4.21 | x4.27 |
| gear | Hoghunt, Runemastered Felled Greatclub | 2 | x4.07 | x4.11 |
| notable | Arcane Intensity | 11 | x1.29 | x1.78 |
| jewel | Megalomaniac, Diamond | 31 | x1.09 | x1.28 |
| gear | Brutus' Lead Sprinkler, Morning Star | 4 | x1.95 | x2.12 |
| ascendancy | Hulking Form | 10 | x1.29 | x1.47 |
| gear | Sacred Flame, Shrine Sceptre | 8 | x1.36 | x1.43 |
| condition | whirlwindStages | 2 | x3.41 | x3.42 |
| ascendancy | Neurological Implants | 8 | x1.34 | x1.43 |
| jewel | Voices, Sapphire | 14 | x1.18 | x1.45 |
| condition | conditionEnemyDazed | 15 | x1.16 | x1.32 |
| support | Rapid Attacks II | 15 | x1.15 | x1.27 |
| notable | Killer Instinct | 23 | x1.10 | x1.36 |
| condition | conditionEnemyFrozen | 4 | x1.67 | x6.39 |
| notable | Throatseeker | 29 | x1.07 | x1.16 |
| gear | Adonia's Ego, Siphoning Wand | 2 | x2.70 | x2.78 |
| keystone | Blackflame Covenant | 4 | x1.63 | x2.79 |
| ascendancy | Forced Outcome | 8 | x1.27 | x1.34 |
| ascendancy | Grinning Immolation | 5 | x1.45 | x1.46 |
| jewel | The Adorned, Diamond | 6 | x1.36 | x1.79 |
| condition | useFrenzyCharges | 15 | x1.13 | x1.20 |
| notable | For the Jugular | 36 | x1.05 | x1.17 |

### Top ascendancy sources

| source | builds | median | max |
|---|---|---|---|
| Advanced Thaumaturgy | 17 | x1.30 | x6.20 |
| Hulking Form | 10 | x1.29 | x1.47 |
| Neurological Implants | 8 | x1.34 | x1.43 |
| Forced Outcome | 8 | x1.27 | x1.34 |
| Grinning Immolation | 5 | x1.45 | x1.46 |
| Sunder the Flesh | 3 | x1.45 | x1.84 |
| Skill Gem Quality | 41 | x1.02 | x1.35 |
| Choice of Power | 5 | x1.13 | x1.18 |
| Motoric Implants | 4 | x1.15 | x1.21 |
| Blood Barbs | 2 | x1.32 | x1.55 |
| Bolstering Implants | 4 | x1.13 | x1.19 |
| Integrated Efficiency | 3 | x1.17 | x1.19 |

### Top support sources

| source | builds | median | max |
|---|---|---|---|
| Rakiata's Flow | 15 | x2.18 | x3.00 |
| Garukhan's Resolve | 12 | x1.68 | x1.82 |
| Elemental Armament II | 22 | x1.25 | x1.33 |
| Execute III | 17 | x1.30 | x1.69 |
| Concentrated Area | 14 | x1.30 | x1.32 |
| Close Combat II | 13 | x1.25 | x1.34 |
| Rapid Attacks II | 15 | x1.15 | x1.27 |
| Hit and Run | 4 | x1.40 | x1.40 |
| Deliberation | 7 | x1.20 | x1.20 |
| Dominus' Grasp | 3 | x1.51 | x1.53 |
| Blindside | 5 | x1.26 | x1.27 |
| Heft | 7 | x1.15 | x1.24 |

### Top keystone sources

| source | builds | median | max |
|---|---|---|---|
| Eldritch Battery | 11 | x1.50 | x1.81 |
| Pain Attunement | 15 | x1.23 | x1.28 |
| Blackflame Covenant | 4 | x1.63 | x2.79 |
| Dance with Death | 4 | x1.25 | x1.25 |
| Wildsurge Incantation | 2 | x1.50 | x1.50 |
| Whispers of Doom | 2 | x1.40 | x1.42 |
| Chaos Inoculation | 3 | x1.09 | x1.09 |

### Top notable sources

| source | builds | median | max |
|---|---|---|---|
| Arcane Intensity | 11 | x1.29 | x1.78 |
| Killer Instinct | 23 | x1.10 | x1.36 |
| Throatseeker | 29 | x1.07 | x1.16 |
| For the Jugular | 36 | x1.05 | x1.17 |
| Heartbreaking | 33 | x1.05 | x1.10 |
| Struck Through | 26 | x1.06 | x1.14 |
| Heartstopping | 28 | x1.05 | x1.19 |
| Stupefy | 18 | x1.08 | x1.12 |
| True Strike | 29 | x1.05 | x1.12 |
| Crushing Verdict | 16 | x1.08 | x1.15 |
| Careful Assassin | 23 | x1.06 | x1.15 |
| Frantic Fighter | 5 | x1.22 | x1.31 |

### Top gear sources

| source | builds | median | max |
|---|---|---|---|
| Runeseeker's Call, Runemastered Runic Fork | 7 | x5.68 | x10.18 |
| Rathpith Globe, Sacred Focus | 4 | x9.87 | x23.56 |
| Wildwood Solace, Spiny Talisman | 4 | x5.74 | x5.85 |
| Mageblood, Utility Belt | 21 | x1.23 | x1.81 |
| Fury of the King, Ashbark Talisman | 2 | x8.13 | x8.22 |
| Blight Bane, Sinister Quarterstaff | 2 | x6.52 | x7.52 |
| Kalandra's Touch, Ring | 19 | x1.20 | x1.44 |
| Constricting Command, Viper Cap | 4 | x2.24 | x3.15 |
| Crown of Eyes, Vermeil Circlet | 5 | x1.80 | x3.38 |
| Nightfall, Glacial Fortress | 2 | x4.21 | x4.27 |
| Hoghunt, Runemastered Felled Greatclub | 2 | x4.07 | x4.11 |
| Brutus' Lead Sprinkler, Morning Star | 4 | x1.95 | x2.12 |

## Per-skill construction recipes (skills with ≥3 builds; sources in ≥40% of them)

### Shred (6 builds: Amazon 1, Oracle 1, Deadeye 1, Pathfinder 1, Blood Mage 1, Lich 1)

layers: supports x1.90, ascendancy x1.24, tree x13.11, tree_small x1.94, gear_product x15.08, conditions x3.63

| layer | source | in builds | median |
|---|---|---|---|
| gear | Wildwood Solace, Spiny Talisman | 4/6 | x5.74 |
| condition | multiplierRage | 6/6 | x2.10 |
| support | Close Combat II | 6/6 | x1.30 |
| jewel | Megalomaniac, Diamond | 5/6 | x1.24 |
| support | Rapid Attacks II | 6/6 | x1.19 |
| gear | Hate Braid, Absent Amulet | 4/6 | x1.30 |
| support | Crescendo II | 6/6 | x1.15 |
| jewel | Heart of the Well, Diamond | 4/6 | x1.22 |
| condition | conditionEnemyShocked | 5/6 | x1.16 |
| condition | enemyDistance | 5/6 | x1.10 |
| gear | Storm Hold, Unset Ring | 4/6 | x1.12 |
| support | Elemental Armament II | 5/6 | x1.07 |
| notable | Pack Encouragement | 5/6 | x1.07 |
| notable | Careful Assassin | 4/6 | x1.08 |

### Earthshatter (5 builds: Titan 3, Gemling Legionnaire 1, Infernalist 1)

layers: supports x1.83, ascendancy x1.31, tree x9.19, tree_small x2.40, gear_product x13.49, conditions x1.49

| layer | source | in builds | median |
|---|---|---|---|
| condition | multiplierRage | 3/5 | x1.57 |
| support | Garukhan's Resolve | 2/5 | x1.75 |
| ascendancy | Hulking Form | 3/5 | x1.25 |
| gear | Sacred Flame, Shrine Sceptre | 2/5 | x1.39 |
| gear | Mageblood, Utility Belt | 3/5 | x1.23 |
| jewel | Heart of the Well, Diamond | 4/5 | x1.10 |
| support | Rapid Attacks II | 2/5 | x1.13 |
| notable | Battle Trance | 2/5 | x1.07 |
| notable | Brutal | 2/5 | x1.07 |
| notable | Overwhelming Strike | 2/5 | x1.05 |
| jewel | Megalomaniac, Diamond | 2/5 | x1.05 |
| condition | conditionBeenHitRecently | 2/5 | x1.05 |
| notable | Sand in the Eyes | 2/5 | x1.04 |
| notable | Versatile Arms | 2/5 | x1.04 |

### Comet (5 builds: Infernalist 2, Gemling Legionnaire 2, Oracle 1)

layers: supports x0.91, ascendancy x1.71, tree x35.04, tree_small x1.64, gear_product x17.20, conditions x2.05

| layer | source | in builds | median |
|---|---|---|---|
| gear | Runeseeker's Call, Runemastered Runic Fork | 2/5 | x5.78 |
| gear | Adonia's Ego, Siphoning Wand | 2/5 | x2.70 |
| condition | usePowerCharges | 4/5 | x1.48 |
| gear | Dusk Gorget, Absent Amulet | 2/5 | x1.87 |
| ascendancy | Bringer of Flame | 2/5 | x1.63 |
| jewel | The Adorned, Diamond | 2/5 | x1.60 |
| support | Execute III | 3/5 | x1.30 |
| notable | Arcane Intensity | 3/5 | x1.29 |
| ascendancy | Grinning Immolation | 2/5 | x1.45 |
| keystone | Pain Attunement | 3/5 | x1.28 |
| ascendancy | Neurological Implants | 2/5 | x1.39 |
| gear | Sacred Flame, Shrine Sceptre | 2/5 | x1.33 |
| gear | Kalandra's Touch, Ring | 2/5 | x1.31 |
| support | Concentrated Area | 2/5 | x1.30 |

### Whirling Assault (4 builds: Smith of Kitava 1, Martial Artist 1, Titan 1, Infernalist 1)

layers: supports x2.14, ascendancy x1.39, tree x14.49, tree_small x3.25, gear_product x12.96, conditions x3.08

| layer | source | in builds | median |
|---|---|---|---|
| support | Heavy Swing | 3/4 | x1.35 |
| condition | conditionEnemyArmourBroken | 2/4 | x1.51 |
| condition | multiplierRage | 2/4 | x1.37 |
| support | Blindside | 2/4 | x1.26 |
| condition | conditionEnemyBlinded | 2/4 | x1.24 |
| support | Ancestral Call II | 2/4 | x1.19 |
| condition | conditionEnemyShocked | 2/4 | x1.15 |
| notable | Crushing Verdict | 3/4 | x1.09 |
| notable | Barbaric Strength | 2/4 | x1.09 |
| notable | Overwhelming Strike | 2/4 | x1.08 |
| notable | Singular Purpose | 2/4 | x1.07 |
| notable | Vulgar Methods | 2/4 | x1.07 |
| notable | Last Stand | 2/4 | x1.05 |
| notable | Guided Hand | 2/4 | x1.03 |

### Arc (4 builds: Gemling Legionnaire 3, Blood Mage 1)

layers: supports x1.96, ascendancy x4.82, tree x22.31, tree_small x2.04, gear_product x69.57, conditions x1.05

| layer | source | in builds | median |
|---|---|---|---|
| ascendancy | Advanced Thaumaturgy | 3/4 | x4.44 |
| gear | Runeseeker's Call, Runemastered Runic Fork | 2/4 | x5.19 |
| support | Dominus' Grasp | 3/4 | x1.51 |
| keystone | Eldritch Battery | 3/4 | x1.50 |
| notable | Arcane Intensity | 3/4 | x1.31 |
| ascendancy | Neurological Implants | 3/4 | x1.31 |
| jewel | Prism of Belief, Diamond | 3/4 | x1.30 |
| gear | Kalandra's Touch, Ring | 2/4 | x1.36 |
| keystone | Pain Attunement | 2/4 | x1.23 |
| support | Deliberation | 2/4 | x1.20 |
| notable | Pure Power | 3/4 | x1.10 |
| jewel | Heart of the Well, Diamond | 3/4 | x1.09 |
| support | Urgent Totems III | 3/4 | x1.07 |
| notable | Overzealous | 3/4 | x1.06 |

### Ember Fusillade (4 builds: Oracle 3, Gemling Legionnaire 1)

layers: supports x1.21, ascendancy x1.20, tree x20.98, tree_small x1.66, gear_product x38.30, conditions x1.00

| layer | source | in builds | median |
|---|---|---|---|
| keystone | Eldritch Battery | 3/4 | x1.36 |
| notable | Arcane Intensity | 3/4 | x1.23 |
| jewel | Prism of Belief, Diamond | 2/4 | x1.30 |
| support | Execute III | 2/4 | x1.30 |
| ascendancy | Forced Outcome | 3/4 | x1.19 |
| keystone | Blackflame Covenant | 3/4 | x1.18 |
| keystone | Pain Attunement | 2/4 | x1.27 |
| notable | Event Horizon | 2/4 | x1.12 |
| notable | Spell Haste | 2/4 | x1.11 |
| gear | Dream Fragments, Sapphire Ring | 2/4 | x1.11 |
| notable | True Strike | 2/4 | x1.09 |
| notable | For the Jugular | 2/4 | x1.09 |
| notable | Mental Alacrity | 3/4 | x1.06 |
| notable | Controlling Magic | 4/4 | x1.03 |

### Meteors (4 builds: Shaman 3, Spirit Walker 1)

layers: supports x2.27, ascendancy x1.11, tree x4.97, tree_small x1.76, gear_product x7.73, conditions x2.75

| layer | source | in builds | median |
|---|---|---|---|
| gear | Fury of the King, Ashbark Talisman | 2/4 | x8.13 |
| condition | multiplierRage | 3/4 | x1.61 |
| condition | conditionShapeshifted | 2/4 | x1.85 |
| support | Elemental Armament II | 4/4 | x1.25 |
| support | Concentrated Area | 3/4 | x1.30 |
| support | Elemental Focus | 2/4 | x1.25 |
| support | Fire Penetration II | 2/4 | x1.12 |
| notable | Crushing Verdict | 2/4 | x1.09 |
| notable | Primal Rage | 2/4 | x1.09 |
| notable | Guardian of the Wilds | 3/4 | x1.05 |
| ascendancy | Wisdom of the Maji | 2/4 | x1.08 |
| notable | Harbinger of Disaster | 3/4 | x1.05 |
| notable | Impact Force | 3/4 | x1.05 |
| notable | Piercing Claw | 2/4 | x1.07 |

### Twister (3 builds: Gemling Legionnaire 2, Acolyte of Chayula 1)

layers: supports x5.66, ascendancy x1.19, tree x5.37, tree_small x1.43, gear_product x15.03, conditions x11.29

| layer | source | in builds | median |
|---|---|---|---|
| condition | whirlwindStages | 2/3 | x3.41 |
| support | Rakiata's Flow | 2/3 | x2.40 |
| support | Garukhan's Resolve | 3/3 | x1.49 |
| support | Projectile Acceleration III | 3/3 | x1.25 |
| ascendancy | Integrated Efficiency | 2/3 | x1.16 |
| support | Retreat II | 2/3 | x1.15 |
| gear | The Taming, Prismatic Ring | 3/3 | x1.08 |
| condition | twisterFire | 2/3 | x1.13 |
| condition | twisterLightning | 2/3 | x1.12 |
| condition | twisterCold | 2/3 | x1.12 |
| notable | Throatseeker | 2/3 | x1.10 |
| notable | Killer Instinct | 2/3 | x1.09 |
| notable | Struck Through | 3/3 | x1.05 |
| notable | Heartbreaking | 3/3 | x1.05 |

### Shield Wall (3 builds: Gemling Legionnaire 1, Titan 1, Acolyte of Chayula 1)

layers: supports x1.98, ascendancy x1.24, tree x7.12, tree_small x1.59, gear_product x7.34, conditions x1.77

| layer | source | in builds | median |
|---|---|---|---|
| condition | multiplierRage | 3/3 | x1.77 |
| gear | Mageblood, Utility Belt | 2/3 | x1.23 |
| gear | Nebuloch, Execratus Hammer | 2/3 | x1.15 |
| support | Heft | 2/3 | x1.14 |
| jewel | Megalomaniac, Diamond | 2/3 | x1.11 |
| jewel | Heart of the Well, Diamond | 3/3 | x1.06 |
| notable | Crushing Verdict | 2/3 | x1.05 |

### Flicker Strike (3 builds: Gemling Legionnaire 1, Invoker 1, Acolyte of Chayula 1)

layers: supports x7.19, ascendancy x1.13, tree x16.92, tree_small x2.38, gear_product x28.92, conditions x3.83

| layer | source | in builds | median |
|---|---|---|---|
| gear | Blight Bane, Sinister Quarterstaff | 2/3 | x6.52 |
| support | Rakiata's Flow | 3/3 | x2.70 |
| condition | usePowerCharges | 3/3 | x1.55 |
| support | Hit and Run | 3/3 | x1.40 |
| gear | Mageblood, Utility Belt | 3/3 | x1.40 |
| gear | Loath Palm, Grand Bracers | 2/3 | x1.54 |
| gear | Phoenix Collar, Absent Amulet | 2/3 | x1.50 |
| jewel | Prism of Belief, Diamond | 3/3 | x1.25 |
| support | Concentrated Area | 2/3 | x1.30 |
| support | Rigwald's Ferocity | 2/3 | x1.25 |
| condition | useFrenzyCharges | 3/3 | x1.13 |
| jewel | Voices, Sapphire | 2/3 | x1.18 |
| jewel | Heart of the Well, Diamond | 3/3 | x1.12 |
| support | Close Combat II | 2/3 | x1.18 |

## Example stacks (top 8 sources of the 6 highest-DPS builds)

- **Comet / Oracle** (147.70M, pobb_in_xNKlha9elpvO.code): Dire Weaver, Dueling Wand [gear] x5.27, Rapture Clasp, Absent Amulet [gear] x2.96, Rakiata's Flow [support] x2.00, Vivid Ornament, Time-Lost Sapphire [jewel] x1.84, Miracle Finger, Breach Ring [gear] x1.81, Execute III [support] x1.69, Prism of Belief, Diamond [jewel] x1.57, Eldritch Battery [keystone] x1.50
- **Flicker Strike / Acolyte of Chayula** (147.60M, poe_ninja_2bd34.code): Blight Bane, Sinister Quarterstaff [gear] x5.52, Rakiata's Flow [support] x1.81, Cataclysm Grasp, Dusk Ring [gear] x1.71, Phoenix Collar, Absent Amulet [gear] x1.50, Loath Palm, Grand Bracers [gear] x1.50, Hit and Run [support] x1.40, usePowerCharges [condition] x1.38, Mageblood, Utility Belt [gear] x1.38
- **Flicker Strike / Invoker** (66.47M, poe_ninja_2b12d.code): Blight Bane, Sinister Quarterstaff [gear] x7.52, Rakiata's Flow [support] x2.70, Loath Palm, Grand Bracers [gear] x1.57, usePowerCharges [condition] x1.55, Phoenix Collar, Absent Amulet [gear] x1.50, Hit and Run [support] x1.40, Mageblood, Utility Belt [gear] x1.40, Concentrated Area [support] x1.30
- **Falling Thunder / Martial Artist** (47.31M, poe_ninja_27e8a.code): usePowerCharges [condition] x19.35, Victory Beam, Sinister Quarterstaff [gear] x7.40, Rakiata's Flow [support] x2.18, multiplierRage [condition] x1.52, Culmination II [support] x1.40, multiplierCombo [condition] x1.40, Overflowing Power [notable] x1.38, Mageblood, Utility Belt [gear] x1.36
- **Arc / Gemling Legionnaire** (18.13M, poe_ninja_2a9f0.code): Runeseeker's Call, Runemastered Runic Fork [gear] x5.99, Advanced Thaumaturgy [ascendancy] x5.87, Damnation Locket, Solar Amulet [gear] x3.56, Rakiata's Flow [support] x3.00, Rathpith Globe, Sacred Focus [gear] x2.42, Cataclysm Finger, Mnemonic Ring [gear] x1.86, Eldritch Battery [keystone] x1.80, Doom Cloak, Conjurer Mantle [gear] x1.60
- **Flicker Strike / Gemling Legionnaire** (14.76M, poe_ninja_2900a.code): Gloom Bane, Bolting Quarterstaff [gear] x5.55, Rakiata's Flow [support] x2.87, multiplierRage [condition] x1.76, usePowerCharges [condition] x1.62, Mageblood, Utility Belt [gear] x1.43, Storm Scarab, Absent Amulet [gear] x1.41, Hit and Run [support] x1.40, Rageforged II [support] x1.35