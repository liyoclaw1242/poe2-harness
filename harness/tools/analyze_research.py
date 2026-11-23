"""Turn the overnight research outputs into ranked tables + backtests.

Inputs (data/results): scan_mid.json, scan_start.json, lift_mid.json, profiles_055.json
Output: data/results/analysis.json and analysis.md

Usage: PYTHONPATH=harness python3 harness/tools/analyze_research.py data/results
"""

import collections
import json
import math
import statistics as st
import sys
from pathlib import Path

from pob_agent import scan
from pob_agent.engine import Engine

d = Path(sys.argv[1] if len(sys.argv) > 1 else "data/results")

# Third-party ascendancy shares for 0.5.5 SC (LFCarry, 2026-11-21) - not poe.ninja-verified.
LADDER_SHARE = {
    "Gemling Legionnaire": 33.6, "Martial Artist": 10.4, "Spirit Walker": 7.0, "Disciple of Varashta": 7.0,
    "Oracle": 7.0, "Deadeye": 6.0, "Infernalist": 5.3, "Titan": 3.0, "Stormweaver": 3.0, "Blood Mage": 3.0,
    "Acolyte of Chayula": 1.6, "Tactician": 1.0, "Lich": 1.0, "Pathfinder": 1.0, "Invoker": 0.3,
}
# Main skills named by the meta write-ups for the top builds (see docs/research/*fable-meta*).
META_SKILLS = ["Twister", "Whirling Assault", "Falling Thunder", "Spark", "Ember Fusillade", "Snipe", "Ice Shot",
               "Comet", "Arc", "Flameblast", "Entangle", "Galvanic Shards", "Frostbolt", "Contagion",
               "Essence Drain", "Sunder", "Earthshatter", "Oil Grenade", "Tempest Flurry"]

with Engine() as eng:
    desc = {s["name"]: s.get("description") for s in eng.call("list_skills")["skills"]}

out = {}
md = []
profiles = [p for p in json.loads((d / "profiles_055.json").read_text()) if not p.get("error") and p.get("main_skill")]
observed = [p["main_skill"] for p in profiles]

for tier in ("start", "mid"):
    rows = scan.score(json.loads((d / f"scan_{tier}.json").read_text()), desc)
    bt = scan.backtest(rows, observed, top_n=40)
    by = {r["skill"]: r for r in rows}
    meta_ranks = {m: by[m]["rank"] for m in META_SKILLS if m in by}
    in_top40 = sum(1 for r in meta_ranks.values() if r <= 40)
    out[f"scan_{tier}"] = {"backtest": bt, "meta_ranks": meta_ranks, "top": rows[:40]}
    md.append(f"## Skill scan — tier {tier} ({len(rows)} skills)\n")
    md.append(f"- Spearman(score, usage in 126-build sample): {bt['spearman_score_vs_usage']:.2f}")
    md.append(f"- Meta skills (write-ups) in top 40: {in_top40}/{len(meta_ranks)} — ranks {meta_ranks}\n")
    md.append("| # | skill | family | DPS | ramp | flags |\n|---|---|---|---|---|---|")
    for r in rows[:25]:
        md.append(f"| {r['rank']} | {r['skill']} | {r['family']} | {r['supported_dps']:.0f} | x{r['ramp_factor']:.2f} | {' '.join(r['flags'])} |")
    md.append("")

# --- ascendancy lift ---
rows = scan.score(json.loads((d / "scan_mid.json").read_text()), desc)
by = {r["skill"]: r for r in rows}
lifts = json.loads((d / "lift_mid.json").read_text())
per_asc = collections.defaultdict(list)
best_nodes = collections.defaultdict(collections.Counter)
pairs = []
for s in lifts:
    r = by.get(s["skill"])
    if not r:
        continue
    for a in s["ascendancies"]:
        if not a.get("lift"):
            continue
        per_asc[a["ascendancy"]].append(a["lift"])
        for n in a.get("nodes", []):
            best_nodes[a["ascendancy"]][n] += 1
        pairs.append({"skill": s["skill"], "asc": a["ascendancy"], "lift": a["lift"], "gated": bool(r["gated"]),
                      "family": r["family"], "pot": a["after"] * r["ramp_factor"]})

sample_asc = collections.Counter(p["ascendancy"] for p in profiles)
asc_rows = []
for a, ls in per_asc.items():
    asc_rows.append({"ascendancy": a, "median_lift": st.median(ls), "p90_lift": sorted(ls)[int(len(ls) * 0.9)],
                     "skills_lift_1_5": sum(l >= 1.5 for l in ls), "sample": sample_asc.get(a, 0),
                     "ladder_share": LADDER_SHARE.get(a), "top_nodes": [n for n, _ in best_nodes[a].most_common(4)]})
asc_rows.sort(key=lambda r: -r["median_lift"])
with_share = [r for r in asc_rows if r["ladder_share"] is not None]
out["ascendancy"] = {
    "rows": asc_rows,
    "spearman_median_lift_vs_ladder": scan.spearman([r["median_lift"] for r in with_share], [r["ladder_share"] for r in with_share]),
    "top2_by_lift": [r["ascendancy"] for r in asc_rows[:2]],
    "top2_by_ladder": sorted(LADDER_SHARE, key=lambda a: -LADDER_SHARE[a])[:2],
}
md.append("## Ascendancy damage lift (8 points spent greedily by PoB, same skill + supports)\n")
md.append(f"- Top 2 by median lift: {out['ascendancy']['top2_by_lift']}; top 2 by ladder share: {out['ascendancy']['top2_by_ladder']}")
md.append(f"- Spearman(median lift, ladder share) over {len(with_share)} ascendancies: {out['ascendancy']['spearman_median_lift_vs_ladder']:.2f} "
          "(damage-only; defensive/minion/companion ascendancies read as x1.00)\n")
md.append("| ascendancy | median lift | p90 lift | skills ≥x1.5 | sample n | ladder % | most-picked nodes |\n|---|---|---|---|---|---|---|")
for r in asc_rows:
    md.append(f"| {r['ascendancy']} | x{r['median_lift']:.2f} | x{r['p90_lift']:.2f} | {r['skills_lift_1_5']} | {r['sample']} | "
              f"{r['ladder_share'] if r['ladder_share'] is not None else '-'} | {', '.join(r['top_nodes'])} |")
md.append("")

# --- pairs ---
fam = collections.defaultdict(list)
for p in pairs:
    fam[p["family"]].append(p)
for ps in fam.values():
    v = [math.log(max(p["pot"], 1e-9)) for p in ps]
    mu, sd = st.mean(v), (st.pstdev(v) or 1.0)
    for p in ps:
        p["score"] = (math.log(max(p["pot"], 1e-9)) - mu) / sd - (0.75 if p["gated"] else 0.0)
pairs.sort(key=lambda p: -p["score"])
for i, p in enumerate(pairs, 1):
    p["rank"] = i
pr = {(p["asc"], p["skill"]): p for p in pairs}
obs_pairs = collections.Counter((p["ascendancy"], p["main_skill"]) for p in profiles)
hits = [(k, c, pr[k]["rank"]) for k, c in obs_pairs.items() if k in pr]
n_obs = sum(c for _, c, _ in hits)
out["pairs"] = {"pool": len(pairs), "matched_builds": n_obs,
                "median_rank": st.median([r for _, _, r in hits]) if hits else None,
                "top": pairs[:30],
                "recall": {N: sum(c for _, c, r in hits if r <= N) / n_obs for N in (100, 250, 500, 1000)} if n_obs else {}}
md.append(f"## Skill × ascendancy pairs ({len(pairs)} pairs)\n")
md.append(f"- Observed (ascendancy, main skill) pairs matched: {n_obs} builds; median rank {out['pairs']['median_rank']} "
          f"(random ≈ {len(pairs) // 2})")
md.append(f"- Share of observed builds whose pair is in top N: " +
          ", ".join(f"top{N} {v:.0%}" for N, v in out['pairs']['recall'].items()) + "\n")
md.append("| # | skill | ascendancy | lift | gated |\n|---|---|---|---|---|")
for p in pairs[:20]:
    md.append(f"| {p['rank']} | {p['skill']} | {p['asc']} | x{p['lift']:.2f} | {'yes' if p['gated'] else ''} |")

(d / "analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
(d / "analysis.md").write_text("\n".join(md))
print("\n".join(md))
