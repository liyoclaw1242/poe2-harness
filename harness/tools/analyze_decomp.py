"""Aggregate multiplier decompositions: how 0.5.5 builds stack multipliers on one skill.

Usage: PYTHONPATH=harness python3 harness/tools/analyze_decomp.py data/results
Inputs: decomp_055.json (decompose_sample.py), profiles_055.json (conditions)
Outputs: decomp_analysis.json, decomp_analysis.md
"""

import collections
import json
import math
import statistics as st
import sys
from pathlib import Path

d = Path(sys.argv[1] if len(sys.argv) > 1 else "data/results")
INF = 1e9


def m(v):
    return INF if v == "inf" else float(v)


prof = {p["file"]: p for p in json.loads((d / "profiles_055.json").read_text())}
builds = []
for r in json.loads((d / "decomp_055.json").read_text()):
    if r.get("error") or not r.get("base_dps") or not r.get("main_skill"):
        continue
    p = prof.get(r["file"], {})
    srcs = [dict(s, mult=m(s["mult"])) for s in r["sources"]]
    for c in p.get("conditional") or []:
        if c.get("dps_pct") and c["dps_pct"] >= 1 and c["kind"] != "scenario":
            srcs.append({"layer": "condition", "name": c["var"], "mult": 1 + c["dps_pct"] / 100, "kind": c["kind"]})
    layers = {k: m(v) for k, v in r["layers"].items()}
    if p.get("dps") and p.get("dewatered_dps"):
        layers["conditions"] = p["dps"] / p["dewatered_dps"]
    srcs.sort(key=lambda s: -s["mult"])
    builds.append({"file": r["file"], "title": r.get("title"), "asc": r.get("ascendancy") or r.get("class"),
                   "skill": r["main_skill"], "dps": r["base_dps"], "layers": layers, "sources": srcs})

md, out = [], {"n": len(builds)}
fmt = lambda x: "∞" if x >= INF else f"x{x:.2f}"

# 1. layer medians
LAY = ["supports", "ascendancy", "tree", "tree_small", "gear_product", "conditions"]
lay_med = {k: st.median([b["layers"][k] for b in builds if k in b["layers"]]) for k in LAY}
out["layer_median"] = lay_med
md.append(f"# Multiplier decomposition — {len(builds)} PoE2 0.5.5 builds\n")
md.append("Leave-one-out: x2.00 = removing that layer/source halves the main skill's DPS. "
          "gear_product = product of per-slot (item vs blank same base).\n")
md.append("## Layer medians\n\n| layer | median | p75 | p90 |\n|---|---|---|---|")
for k in LAY:
    v = sorted(b["layers"][k] for b in builds if k in b["layers"])
    md.append(f"| {k} | {fmt(st.median(v))} | {fmt(v[int(len(v)*.75)])} | {fmt(v[int(len(v)*.9)])} |")

# 2. where is each build's biggest single source
top_layer = collections.Counter()
for b in builds:
    finite = [s for s in b["sources"] if s["mult"] < INF and not (s["layer"] == "gear" and s.get("slot") == "Weapon 1")]
    if finite:
        top_layer[finite[0]["layer"]] += 1
out["top_source_layer"] = top_layer
md.append("\n## Layer of each build's largest single multiplier (excluding the main weapon)\n")
md.append(", ".join(f"{k} {v}" for k, v in top_layer.most_common()))

# 3. source catalog
cat = collections.defaultdict(list)
for b in builds:
    for s in b["sources"]:
        if s["mult"] < INF:
            cat[(s["layer"], s["name"])].append(s["mult"])
rows = [{"layer": k[0], "name": k[1], "n": len(v), "median": st.median(v), "max": max(v),
         "weight": len(v) * math.log(st.median(v))} for k, v in cat.items() if len(v) >= 2]
rows.sort(key=lambda r: -r["weight"])
out["catalog"] = rows[:80]
md.append("\n## Most impactful recurring sources (n builds × log median multiplier)\n")
md.append("| layer | source | builds | median | max |\n|---|---|---|---|---|")
for r in rows[:45]:
    md.append(f"| {r['layer']} | {r['name']} | {r['n']} | {fmt(r['median'])} | {fmt(r['max'])} |")

for layer in ("ascendancy", "support", "keystone", "notable", "gear"):
    lr = sorted([r for r in rows if r["layer"] == layer], key=lambda r: -r["weight"])[:12]
    md.append(f"\n### Top {layer} sources\n\n| source | builds | median | max |\n|---|---|---|---|")
    for r in lr:
        md.append(f"| {r['name']} | {r['n']} | {fmt(r['median'])} | {fmt(r['max'])} |")

# 4. per skill recipes
by_skill = collections.defaultdict(list)
for b in builds:
    by_skill[b["skill"]].append(b)
recipes = {}
md.append("\n## Per-skill construction recipes (skills with ≥3 builds; sources in ≥40% of them)\n")
for skill, bs in sorted(by_skill.items(), key=lambda kv: -len(kv[1])):
    if len(bs) < 3:
        continue
    c = collections.defaultdict(list)
    for b in bs:
        seen = set()
        for s in b["sources"]:
            k = (s["layer"], s["name"])
            if k not in seen and s["mult"] < INF:
                seen.add(k)
                c[k].append(s["mult"])
    rec = sorted([(k, len(v), st.median(v)) for k, v in c.items() if len(v) / len(bs) >= 0.4],
                 key=lambda x: -(x[1] * math.log(x[2])))
    lm = {k: st.median([b["layers"][k] for b in bs if k in b["layers"]]) for k in LAY}
    recipes[skill] = {"n": len(bs), "ascendancies": collections.Counter(b["asc"] for b in bs).most_common(),
                      "layers": lm, "recipe": [{"layer": k[0], "name": k[1], "n": n, "median": med} for k, n, med in rec]}
    md.append(f"### {skill} ({len(bs)} builds: " + ", ".join(f"{a} {n}" for a, n in recipes[skill]["ascendancies"]) + ")\n")
    md.append("layers: " + ", ".join(f"{k} {fmt(v)}" for k, v in lm.items()) + "\n")
    md.append("| layer | source | in builds | median |\n|---|---|---|---|")
    for k, n, med in rec[:14]:
        md.append(f"| {k[0]} | {k[1]} | {n}/{len(bs)} | {fmt(med)} |")
    md.append("")
out["recipes"] = recipes

# 5. example stacks
md.append("## Example stacks (top 8 sources of the 6 highest-DPS builds)\n")
for b in sorted(builds, key=lambda b: -b["dps"])[:6]:
    md.append(f"- **{b['skill']} / {b['asc']}** ({b['dps']/1e6:.2f}M, {b['file']}): " +
              ", ".join(f"{s['name']} [{s['layer']}] {fmt(s['mult'])}" for s in b["sources"][:8]))
out["builds"] = builds
(d / "decomp_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
(d / "decomp_analysis.md").write_text("\n".join(md))
print("\n".join(md))
