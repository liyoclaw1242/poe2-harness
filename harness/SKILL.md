---
name: pob-agent-poe2
description: Path of Exile 2 build analysis through headless Path of Building (PoB-PoE2) - build diagnosis, config "dewatering", ramp-up (stack/stage) curves, stat scaling, slot upgrade priorities, PoB-weighted trade2 search links, cost-efficiency (CP值) ranking of candidate items, and PoB-only skill/ascendancy strength scans. Trigger on PoE2, 流亡黯道2, PoB, pobb.in, poe.ninja/poe2, 配裝, 天賦, 寶石, DPS, EHP, 去水, 熱機, 疊層, 換裝, 交易所, CP值, 強勢 build, meta.
---

# pob-agent (PoE2) — agent skill

Run from the repo root: `PYTHONPATH=harness python3 -m pob_agent.cli <command> ...`
(or `pob-agent <command>` after `pip install -e .`). One-time setup: `scripts/setup.sh`.

## Golden rules
1. **PoE2 only.** Never apply PoE1 mechanics (Awakened gems, crafting bench, Harvest, 6-links).
2. **Numbers come from PoB, not memory.** Never estimate DPS/EHP/resists yourself; run a command.
   Every output is a PoB calculation, not an in-game measurement — say so when it matters.
3. **Dewater before advising.** PoB defaults to max stacks and the build's own config. Quote the
   dewatered / ramp-start / mapping numbers next to the configured one (`diagnose` gives all of them).
4. **Never buy or whisper.** Trade commands only build search links and evaluate items the player pastes.
5. **Keep context small.** Default output is compact markdown; use `--json` only with a file redirect.
   `diagnose` already includes summary, audit, ramp, scaling and slot headroom — don't re-run them.

## Recipes
**A. "Why is my build weak / dying / is it good?"** (1 step)
```
pob-agent diagnose <build>            # build = file, share code, pobb.in or poe.ninja/poe2/pob link
pob-agent diagnose <build> --keep multiplierRage conditionEnemyShocked   # keep realistic conditions on
```
Read in order: summary → audit (which config values inflate DPS, scenarios) → ramp (how long/how many
stacks before full damage) → scales (what one unit of each stat is worth) → headroom (weakest slots).

**B. "What should I buy next?"**
```
pob-agent trade-query <build> --league "<trade league>" [--slot Gloves "Ring 1"] [--weights FullDPS:1,TotalEHP:0.5] [--max-price 5 --currency divine]
```
Gives PoB-derived stat weights per slot and a trade2 URL for the player to open. Ask the player to
paste promising listings (Ctrl+C item text, plus price) into a file separated by `---` lines with
`slot:` / `price:` / `name:` headers, then:
```
pob-agent upgrade <build> --candidates items.txt [--weights FullDPS:1,TotalEHP:0.5]
```
→ ranked by weighted % gain per price unit, with resist changes (check caps before recommending).

**C. "Is this mechanic/stack worth it?"** `pob-agent ramp <build>` and `pob-agent scales <build>`.

**D. Meta / new league: "what will be strong?"** (PoB data only, no ladder)
```
pob-agent scan --tier start|mid [--skills "Twister" "Spark"] [--out scan.json]
```
Ranks skills on a standardised character (best supports chosen by PoB, hidden stack multipliers
measured). Flags: `hidden-multiplier` (big capped multiplier behind stages/stacks — e.g. Twister ×4.8),
`scales-with-gem-level`, `family-outlier`. Treat as a shortlist, not a verdict: it does not model
meta gems (Hollow Form, Cast on X), totems/minion AI, or ascendancy synergy — see docs/research.

**E. "How do I get the most out of skill X?" (multiplier stacking)**
```
pob-agent decompose <build> [--synergy]       # what each support / ascendancy node / notable / item / condition is worth
pob-agent build-up "<skill>" --ascendancy "<name>" [--tree-points 40] [--no-lineage]
```
`decompose` is leave-one-out (x2.00 = removing it halves DPS); `--synergy` tests pairs of the top sources
and lists "engines" (pairs worth more together than apart, e.g. Eldritch Battery + Runeseeker's Call on
Arc Gemling). `build-up` constructs the skill greedily (supports → ascendancy → tree → best unique per
slot) and shows each step's multiplier plus capped ramp. It is greedy: it finds independent multipliers
well (ascendancy picks match real builds ~half the time) but misses cross-layer engines and conditions
(Rage, Shocked, power charges) that real builds carry — run `decompose` on a strong real build of the
same skill and diff.

## Caveats to state when relevant
- Trigger/meta gems, minion behaviour and uptime are approximations in PoB.
- "No cap in PoB" on a ramp curve means PoB does not limit that stack; check the in-game maximum.
- Prices are whatever the player provides; the harness does not read live listings.
