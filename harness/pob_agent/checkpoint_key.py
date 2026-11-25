"""Answer key for ascendancy checkpoints and switch planning (spine items 3 and 4).

Collected 2026-11-25 by an independent reviewer from maxroll.gg and poe-vault.com 0.5.x build/leveling guides
(23 builds, all 8 classes, at most 3 per class), frozen before any run against it; tests pin its hash. Node and
skill names were checked against the vendored PoB 0.5 data (all ascendancy node names found; "Bind Spectre" is
not a gem). Guide pages were read through a summarising fetch, not raw HTML.

Scoring, registered before the first run (checkpoint order):
  scorable: the target skill is a gem PoB can probe and asc_order names at least two notables.
  "RESPEC ..." steps are skipped; guide_first = the first notable, guide_first2 = the first two distinct ones.
  M1 first pick: our 2-point notable == guide_first; baseline 1/k per entry, k = notables affordable at 2 points.
  M2 first two: |our first two notables & guide_first2| / 2; baseline from the same random draw (k candidates).
  Scored once; the key is not tuned on.

Scoring, registered 2026-11-25 before the first run (switch-readiness checklist, `switch.gates`):
  scorable: the target is a gem with tier >= 1 or granted by a named ascendancy notable, and the guide gives a
  real switch (not "no switch") with a numeric level or an act ("Act N", "Interludes", "maps"/"early maps").
  Our act = the act of the gate level (Act 1 1-15, Act 2 16-28, Act 3 29-40, Act 4 41-50, Interludes 51-64,
  maps 65+). Guide act = act of switch.level if numeric, else the act named in switch.point.
  S1 never early: the guide does not switch before our gate (numeric: guide level >= gate level - 3; else
  guide act >= our act).
  S2 same act: guide act == our act. Baseline for S2: "available from Act 1" for every target.

Scoring, registered 2026-11-25 before the first run (target vs bridge, `bridge.compare`, free tree):
  scorable entries: as for the switch checklist, and the target appears in the class-level probes.
  For each stage (act1 12, pre_asc1 24, asc1 32, asc2 40) with class-level data: the guide plays the target
  at that stage iff stage level >= guide switch level (numeric) or >= the first level of the named act
  (Act 1 1, Act 2 16, Act 3 29, Act 4 41, Interludes 51, maps 65).
  Rule A (gate only): play the target iff its gate is open. Rule B (gate + ratio): iff the gate is open and the
  target clears at least as fast as the best bridge (ratio >= 1).
  Report agreement of A and B with the guide over all (entry, stage) pairs; B is useful only if it beats A.

Check, registered 2026-11-25 before running (bridge on a target build's tree): for each target build tried, the
class's pre_asc1 leveling pick (leveling.BACKTEST) stays in the top 3 of the pre_asc1 ranking on that tree.
"""
M = "https://maxroll.gg/poe2/build-guides/"
V = "https://www.poe-vault.com/poe2/"
CHECKPOINT_KEY = [
 {"build": "Minion Army Infernalist", "class": "Witch", "asc": "Infernalist", "skill": "Bind Spectre (Vaal Guard)",
  "asc_order": ["Loyal Hellhound", "Altered Flesh", "Beidat's Will", "Beidat's Hand"],
  "bridge": ["Skeletal Sniper", "Skeletal Arsonist", "Raging Spirits"],
  "switch": {"level": None, "point": "end of Act 3 (Utzaal)", "gate": "Bind Spectre on Vaal Guard, 50 Spirit each"},
  "source": M + "minion-army-infernalist-build-guide"},
 {"build": "Infernal Legion Lich", "class": "Witch", "asc": "Lich", "skill": "Infernal Legion II",
  "asc_order": ["Soulless Form", "Necromantic Conduit", "Rupture the Soul", "Eternal Life"],
  "bridge": ["Skeletal Sniper", "Raging Spirits", "Skeletal Reaver"],
  "switch": {"level": 58, "point": "Interludes", "gate": "level 58, 18 weapon set points, ~34,000 gold respec, both companions captured"},
  "source": M + "infernal-legion-lich-build-guide"},
 {"build": "Essence Drain Lich", "class": "Witch", "asc": "Lich", "skill": "Essence Drain",
  "asc_order": ["Eldritch Empowerment", "Soulless Form", "Eternal Life", "Crystalline Phylactery"],
  "bridge": ["Chaos Bolt", "Flame Wall", "Unearth"],
  "switch": {"level": 6, "point": "Act 1 (Red Vale)", "gate": None},
  "source": M + "essence-drain-lich-build-guide"},
 {"build": "Arc Stormweaver", "class": "Sorceress", "asc": "Stormweaver", "skill": "Arc",
  "asc_order": ["Constant Gale", "Strike Twice", "Storm's Recollection", "Heavy Snows"],
  "bridge": ["Spark", "Orb of Storms"],
  "switch": {"level": 14, "point": "Act 1", "gate": None},
  "source": M + "arc-stormweaver-build-guide"},
 {"build": "Ice Nova Snap Stormweaver (Maxroll)", "class": "Sorceress", "asc": "Stormweaver", "skill": "Ice Nova",
  "asc_order": ["Constant Gale", "RESPEC Constant Gale -> Strike Twice + Shaper of Storms", "Constant Gale", "Refracted Infusion"],
  "bridge": ["Spark", "Flame Wall", "Frost Bomb"],
  "switch": {"level": 3, "point": "Act 1", "gate": "Ice Nova and Frost Darts engraved"},
  "source": M + "cold-snap-frostbolt-stormweaver-leveling-guide"},
 {"build": "Ice Nova Stormweaver (poe-vault)", "class": "Sorceress", "asc": "Stormweaver", "skill": "Ice Nova",
  "asc_order": ["Refracted Infusion", "Storm's Recollection", "Constant Gale", "Force of Will"],
  "bridge": ["Spark", "Volcano", "Essence Drain", "Contagion"],
  "switch": {"level": None, "point": "Act 2", "gate": "Level 5 Uncut Skill Gems for Snap and Ice Nova"},
  "source": V + "sorceress/stormweaver/ice-nova-leveling-build"},
 {"build": "Supporting Fire Tactician", "class": "Mercenary", "asc": "Tactician", "skill": "Supporting Fire",
  "asc_order": ["Unleash Hell!", "A Solid Plan", "Polish That Gear", "Stay Light, Use Cover"],
  "bridge": ["Permafrost Bolts", "Fragmentation Rounds"],
  "switch": {"level": 36, "point": "act not stated", "gate": "~21,700 gold respec; Fire Attunement, Multishot II, Bidding I, Muster"},
  "source": M + "supporting-fire-tactician-build-guide"},
 {"build": "Oil Grenade Witchhunter", "class": "Mercenary", "asc": "Witchhunter", "skill": "Oil Grenade",
  "asc_order": ["Zealous Inquisition", "Pitiless Killer", "Judge, Jury, and Executioner", "RESPEC Judge, Jury, and Executioner -> Obsessive Rituals + Ceremonial Ablution"],
  "bridge": ["Explosive Grenade", "Gas Grenade"],
  "switch": {"level": None, "point": "Act 3", "gate": "Level 9 Uncut Skill Gem"},
  "source": M + "oil-grenade-witchhunter-build-guide"},
 {"build": "Twister Gemling Legionnaire", "class": "Mercenary", "asc": "Gemling Legionnaire", "skill": "Twister",
  "asc_order": ["Essence of Virtue", "Advanced Thaumaturgy", "Gem Studded", "Integrated Efficiency"],
  "bridge": [],
  "switch": {"level": None, "point": "not stated", "gate": "Spear, Whirling Slash and Twister gems from a Huntress mule"},
  "source": M + "gemling-legionnaire-twister-build-guide"},
 {"build": "Lightning Spear Amazon", "class": "Huntress", "asc": "Amazon", "skill": "Lightning Spear",
  "asc_order": ["Predatory Instinct", "In for the Kill", "RESPEC In for the Kill -> Critical Strike + Penetrate", "In for the Kill"],
  "bridge": ["Explosive Spear", "Contagion", "Frost Bomb"],
  "switch": {"level": 5, "point": "Act 1", "gate": None},
  "source": M + "lightning-spear-amazon"},
 {"build": "Bleed Rake Amazon", "class": "Huntress", "asc": "Amazon", "skill": "Rake",
  "asc_order": ["Critical Strike", "Predatory Instinct", "Penetrate", "In for the Kill"],
  "bridge": ["Explosive Spear", "Spear Stab"],
  "switch": {"level": None, "point": "Act 1, soon after Disengage", "gate": None},
  "source": M + "bleed-rake-amazon-build-guide"},
 {"build": "Minion Army Spirit Walker", "class": "Huntress", "asc": "Spirit Walker", "skill": "Wild Protector minion army (Skeletal Sniper, Skeletal Warrior)",
  "asc_order": ["Wild Protector", "The Natural Order", "The Catha's Balance", "Idolatry"],
  "bridge": ["Twister", "Whirling Slash", "Explosive Grenade"],
  "switch": {"level": 22, "point": "after first ascendancy (Trial of the Sekhemas, Act 2)", "gate": "Wild Protector notable; full passive respec 5-7k gold"},
  "source": M + "minion-army-spirit-walker-build-guide"},
 {"build": "Grim Pillars Spell Totem Oracle", "class": "Druid", "asc": "Oracle", "skill": "Grim Pillars",
  "asc_order": ["The Unseen Path", "The Lesser Harm", "Forced Outcome", "Unnamed Heartwood"],
  "bridge": ["Contagion", "Bone Cage", "Bonestorm", "Entangle"],
  "switch": {"level": None, "point": "Act 4, when the gem is obtained", "gate": "Grim Pillars gem (drop location unknown per guide)"},
  "source": M + "grim-pillars-spell-totem-oracle-build-guide"},
 {"build": "Demon Calamity Bear Shaman", "class": "Druid", "asc": "Shaman", "skill": "Walking Calamity",
  "asc_order": ["Turning of the Seasons", "RESPEC Turning of the Seasons at 2nd ascension", "Furious Wellspring"],
  "bridge": ["Furious Slam", "Maul"],
  "switch": {"level": 52, "point": "not stated", "gate": "level 52 for Walking Calamity"},
  "source": M + "demon-calamity-bear-shaman-build-guide"},
 {"build": "Lunar Assault Werewolf Oracle", "class": "Druid", "asc": "Oracle", "skill": "Lunar Assault",
  "asc_order": ["The Lesser Harm", "Forced Outcome", "The Unseen Path", "Entwined Realities"],
  "bridge": ["Entangle"],
  "switch": {"level": None, "point": "no switch stated", "gate": None},
  "source": M + "lunar-assault-werewolf-oracle-build-guide"},
 {"build": "Ice Strike Invoker", "class": "Monk", "asc": "Invoker", "skill": "Ice Strike",
  "asc_order": ["I am the Thunder...", "...and I Shall Rage", "Lead me through Grace...", "Sunder my Enemies..."],
  "bridge": ["Glacial Cascade"],
  "switch": {"level": None, "point": "end of Act 1, at Count Geonor", "gate": None},
  "source": M + "tempest-flurry-invoker-leveling-guide"},
 {"build": "Whirling Assault Martial Artist", "class": "Monk", "asc": "Martial Artist", "skill": "Whirling Assault",
  "asc_order": ["Hollow Focus Technique", "Way of the Stonefist", "Runic Meridians", "Way of the Mountain"],
  "asc_order_campaign": ["Way of the Mountain", "Hollow Focus Technique"],
  "bridge": ["Glacial Cascade", "Storm Wave"],
  "switch": {"level": 68, "point": "early maps, after campaign", "gate": "400+ physical DPS Quarterstaff; gold to respec ascendancy and passives"},
  "source": M + "whirling-assault-martial-artist-build-guide"},
 {"build": "Staggering Palm Martial Artist (poe-vault)", "class": "Monk", "asc": "Martial Artist", "skill": "Whirling Assault",
  "asc_order": ["Runic Meridians", "Way of the Mountain", "Way of the Stonefist"],
  "bridge": ["Tempest Flurry", "Wind Blast", "Staggering Palm"],
  "switch": {"level": None, "point": "Act 4", "gate": "Level 11 Uncut Skill Gem"},
  "source": V + "monk/martial-artist/staggering-palm-leveling-build"},
 {"build": "Ice Shot Deadeye", "class": "Ranger", "asc": "Deadeye", "skill": "Ice Shot",
  "asc_order": ["Gathering Winds", "Called Shots", "Bullseye", "Point Blank"],
  "bridge": ["Lightning Arrow", "Stormcaller Arrow", "Freezing Salvo"],
  "switch": {"level": 31, "point": "act not stated", "gate": None},
  "source": M + "ice-shot-deadeye-build-guide"},
 {"build": "Twister Deadeye", "class": "Ranger", "asc": "Deadeye", "skill": "Twister",
  "asc_order": ["Gathering Winds", "Avidity", "Thrilling Chase", "Called Shots"],
  "bridge": ["Lightning Arrow", "Lightning Rod"],
  "switch": {"level": None, "point": "no switch (Twister from level 1 with a Huntress mule)", "gate": "Spear + Whirling Slash/Twister gems from a Huntress mule"},
  "source": M + "twister-deadeye-build-guide"},
 {"build": "Spiral Volley Deadeye", "class": "Ranger", "asc": "Deadeye", "skill": "Spiral Volley",
  "asc_order": [],
  "bridge": ["Lightning Arrow", "Lightning Rod"],
  "switch": {"level": 54, "point": "act not stated", "gate": "Resonance allocated on the passive tree"},
  "source": M + "spiral-volley-deadeye-build-guide"},
 {"build": "Shield Wall Warbringer", "class": "Warrior", "asc": "Warbringer", "skill": "Shield Wall",
  "asc_order": ["Answered Call", "Warcaller's Bellow", "Anvil's Weight", "Imploding Impacts", "Jade Heritage"],
  "bridge": [],
  "switch": {"level": 22, "point": "act not stated", "gate": "level 7 gem for Shield Wall"},
  "source": M + "shield-wall-warbringer-build-guide"},
 {"build": "Shield Wall Smith of Kitava (poe-vault)", "class": "Warrior", "asc": "Smith of Kitava", "skill": "Shield Wall",
  "asc_order": ["Coal Stoker", "Smith's Masterwork"],
  "bridge": ["Boneshatter", "Rolling Slam"],
  "switch": {"level": None, "point": "Act 2", "gate": "Tier 7 Skill Gem"},
  "source": V + "warrior/smith-of-kitava/warrior-build-leveling-guide"},
]
