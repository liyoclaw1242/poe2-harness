"""PoB-only build-up vs what real 0.5.5 builds of the same skill + ascendancy actually use.

For each (main skill, ascendancy) with >= MIN builds in the sample, construct the skill greedily with PoB
(supports -> ascendancy -> passive tree) and measure how many of the load-bearing pieces real builds use
(sources with leave-one-out mult >= 1.03) the optimizer also picked, and vice versa.

Usage: PYTHONPATH=harness python3 harness/tools/compare_buildup.py data/results [MIN]
"""

import collections
import json
import statistics as st
import sys
from pathlib import Path

from pob_agent.engine import Engine
from pob_agent.scan import TIERS

d = Path(sys.argv[1] if len(sys.argv) > 1 else "data/results")
MIN = int(sys.argv[2]) if len(sys.argv) > 2 else 2
LINEAGE = "--no-lineage" not in sys.argv
LOAD = 1.03
an = json.loads((d / "decomp_analysis.json").read_text())
prof = {p["file"]: p for p in json.loads((d / "profiles_055.json").read_text())}

groups = collections.defaultdict(list)
for b in an["builds"]:
    groups[(b["skill"], b["asc"])].append(b)

rows = []
with Engine() as eng:
    for (skill, asc), bs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if len(bs) < MIN or not asc:
            continue
        try:
            r = eng.call("build_up", skill=skill, ascendancy=asc, treePoints=40, allowLineage=LINEAGE, **TIERS["mid"])
        except Exception as e:
            rows.append({"skill": skill, "asc": asc, "error": str(e)[:200]})
            continue
        real = collections.defaultdict(collections.Counter)  # layer -> name -> builds using it (load-bearing)
        real_sup = collections.Counter()
        for b in bs:
            for s in b["sources"]:
                if isinstance(s["mult"], (int, float)) and s["mult"] >= LOAD:
                    lay = "tree" if s["layer"] in ("notable", "keystone") else s["layer"]
                    real[lay][s["name"]] += 1
            for sp in prof.get(b["file"], {}).get("supports") or []:
                real_sup[sp] += 1
        opt_sup = [s["name"] for s in r["steps"] if s["layer"] == "support"]
        opt_asc = r.get("ascNodes") or []
        opt_tree = [s["name"] for s in r["steps"] if s["layer"] in ("notable", "keystone")]

        def overlap(opt, realc):
            hit = [o for o in opt if o in realc]
            top = [n for n, _ in realc.most_common(len(opt) or 1)]
            return {"opt": opt, "hit": hit, "precision": len(hit) / len(opt) if opt else None,
                    "real_top": top, "recall_top": (sum(1 for t in top if t in opt) / len(top)) if top else None}

        rows.append({"skill": skill, "asc": asc, "n": len(bs), "layers": r["layers"], "bare": r["bareDPS"],
                     "final": r["finalDPS"],
                     "supports": overlap(opt_sup, real_sup),
                     "ascendancy": overlap(opt_asc, real["ascendancy"]),
                     "tree": overlap(opt_tree, real["tree"]),
                     "real_conditions": real["condition"].most_common(5),
                     "real_gear": real["gear"].most_common(5)})
        print("done", skill, asc, file=sys.stderr)

md = ["# PoB-only build-up vs real builds (same skill + ascendancy)\n",
      f"Load-bearing = leave-one-out mult ≥ {LOAD}. precision = share of optimizer picks seen in real builds; "
      "recall = share of the real most-used pieces the optimizer also picked.\n",
      "| skill | ascendancy | n | sup P/R | asc P/R | tree P/R | optimizer supports | real top supports |",
      "|---|---|---|---|---|---|---|---|"]
pr = lambda o: "-" if o["precision"] is None else f"{o['precision']:.0%}/{(o['recall_top'] or 0):.0%}"
agg = collections.defaultdict(list)
for r in rows:
    if r.get("error"):
        md.append(f"| {r['skill']} | {r['asc']} | - | error: {r['error'][:60]} |||||")
        continue
    for k in ("supports", "ascendancy", "tree"):
        if r[k]["precision"] is not None:
            agg[k + "_P"].append(r[k]["precision"])
        if r[k]["recall_top"] is not None:
            agg[k + "_R"].append(r[k]["recall_top"])
    md.append(f"| {r['skill']} | {r['asc']} | {r['n']} | {pr(r['supports'])} | {pr(r['ascendancy'])} | {pr(r['tree'])} | "
              f"{', '.join(r['supports']['opt'])} | {', '.join(r['supports']['real_top'])} |")
md.append("\nMean: " + ", ".join(f"{k} {st.mean(v):.0%}" for k, v in sorted(agg.items())))
md.append("\n## What real builds carry that the optimizer cannot pick (conditions, gear)\n")
for r in rows:
    if not r.get("error"):
        md.append(f"- **{r['skill']} / {r['asc']}**: conditions " +
                  ", ".join(f"{n} ({c})" for n, c in r["real_conditions"]) + "; gear " +
                  ", ".join(f"{n} ({c})" for n, c in r["real_gear"]))
(d / f"buildup_compare{"" if LINEAGE else "_nolineage"}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
(d / f"buildup_compare{"" if LINEAGE else "_nolineage"}.md").write_text("\n".join(md))
print("\n".join(md))
