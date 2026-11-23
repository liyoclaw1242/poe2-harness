# PoB-only build-up vs real builds (same skill + ascendancy)

Load-bearing = leave-one-out mult ≥ 1.03. precision = share of optimizer picks seen in real builds; recall = share of the real most-used pieces the optimizer also picked.

| skill | ascendancy | n | sup P/R | asc P/R | tree P/R | optimizer supports | real top supports |
|---|---|---|---|---|---|---|---|
| Earthshatter | Titan | 3 | 20%/0% | - | 12%/0% | Bleed III, Zerphi's Infamy, Brutality III, Concentrated Area, Heavy Swing | Branching Fissures II, Aftershock II, Rapid Attacks II, Stoicism II, Dialla's Desire |
| Ember Fusillade | Oracle | 3 | 0%/0% | 33%/100% | 44%/11% | Rakiata's Flow, Uhtred's Omen | Compressed Duration II, Swift Affliction III |
| Meteors | Shaman | - | error: build_up failed: harness/ |||||
| Arc | Gemling Legionnaire | 3 | 50%/0% | 100%/75% | 0%/0% | Rakiata's Flow, Uhtred's Omen | SupportMetaTotemSpellTotemPlayer, Urgent Totems III |
| Comet | Infernalist | 2 | 50%/50% | 40%/40% | 11%/0% | Rakiata's Flow, Uhtred's Omen | SupportMetaCastOnCritPlayer, Rakiata's Flow |
| Twister | Gemling Legionnaire | 2 | 0%/0% | 25%/50% | 0%/0% | Zerphi's Infamy, Bleed III, Brutality III, Concentrated Area, Heightened Accuracy I | Projectile Acceleration III, Retreat II, Garukhan's Resolve, Rakiata's Flow, Execute III |
| Living Bomb | Gemling Legionnaire | 2 | 33%/0% | 50%/67% | - | Rakiata's Flow, Considered Casting, Uhtred's Augury | SupportMetaCastOnElementalAilmentPlayer, Overabundance II, Withering Touch |
| Comet | Gemling Legionnaire | 2 | 0%/0% | 100%/33% | - | Rakiata's Flow, Uhtred's Omen | Zenith II, Execute III |

Mean: ascendancy_P 58%, ascendancy_R 52%, supports_P 22%, supports_R 7%, tree_P 14%, tree_R 2%

## What real builds carry that the optimizer cannot pick (conditions, gear)

- **Earthshatter / Titan**: conditions multiplierRage (1); gear Mageblood, Utility Belt (2), Skull Blow, Flanged Mace (1), Foe Clutches, Ornate Mitts (1), Victory Gyre, Prismatic Ring (1), Grim Blunt, Massive Greathammer (1)
- **Ember Fusillade / Oracle**: conditions ; gear Dream Fragments, Sapphire Ring (2), Runeseeker's Call, Runic Fork (1), Woe Noose, Absent Amulet (1), Miracle Anthem, Sacred Focus (1), Gloom Fist, Runeforged Sirenscale Gloves (1)
- **Arc / Gemling Legionnaire**: conditions usePowerCharges (1), useFrenzyCharges (1); gear Runeseeker's Call, Runemastered Runic Fork (2), Kalandra's Touch, Ring (2), Phoenix Song, Attuned Wand (1), Havoc Rosary, Bloodstone Amulet (1), Behemoth Hand, Vaal Gloves (1)
- **Comet / Infernalist**: conditions conditionEnemyShocked (1), usePowerCharges (1), arcLightningInfused (1), conditionEnemyImmobilised (1), conditionEnemyDazed (1); gear Runeseeker's Call, Runemastered Runic Fork (2), Carrion Charm, Absent Amulet (1), Sacred Flame, Shrine Sceptre (1), Dusk Palm, Runeforged Vaal Mitts (1), Phoenix Knuckle, Amethyst Ring (1)
- **Twister / Gemling Legionnaire**: conditions conditionEnemyChilled (1), conditionEnemyIgnited (1), whirlwindStages (1), conditionHitMeleeRecently (1), twisterLightning (1); gear The Taming, Prismatic Ring (2), Skysliver, Winged Spear (1), Spirit Paw, Runeforged Secured Wraps (1), Spirit Spiral, Gold Ring (1), Woe Medallion, Absent Amulet (1)
- **Living Bomb / Gemling Legionnaire**: conditions multiplierWitheredStackCount (1); gear Rathpith Globe, Sacred Focus (2), Runeseeker's Call, Runemastered Runic Fork (2), Kaom's Heart, Conqueror Plate (2), Veil of the Night, Martyr Crown (2), Corruption Fingers, Massive Mitts (2)
- **Comet / Gemling Legionnaire**: conditions usePowerCharges (2), conditionCritRecently (1), configResonanceCount (1), conditionEnemyFrozen (1), overridePowerCharges (1); gear Adonia's Ego, Siphoning Wand (2), Dusk Gorget, Absent Amulet (2), Tempest Halo, Runeforged Ancestral Tiara (2), Maligaro's Virtuosity, Runemastered Fine Bracers (1), Sacred Flame, Shrine Sceptre (1)