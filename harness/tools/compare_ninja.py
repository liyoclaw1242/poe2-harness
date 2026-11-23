"""PoB-only build-up vs poe.ninja usage for the same skill (top ascendancy).

Usage: PYTHONPATH=harness python3 harness/tools/compare_ninja.py data/ninja/forbiddenrites_2026-11-23.json data/results
"""

import json
import statistics as st
import sys
from pathlib import Path

from pob_agent.engine import Engine
from pob_agent.scan import TIERS

nin = json.loads(Path(sys.argv[1]).read_text())
out_dir = Path(sys.argv[2])


def parse(s):
    out = {}
    for part in s.split(";"):
        name, _, p = part.strip().rpartition(" ")
        out[name] = float(p)
    return out


rows = []
with Engine() as eng:
    for skill, d in nin["skills"].items():
        asc = d["cls"][0].rsplit(" ", 1)[0]
        gems, passives = parse(d["gems"]), parse(d["passives"])
        try:
            r = eng.call("build_up", skill=skill, ascendancy=asc, allowLineage=True, uniqueTop=5, **TIERS["mid"])
        except Exception as e:
            rows.append({"skill": skill, "asc": asc, "error": str(e)[:160]})
            continue
        sup = [s["name"] for s in r["steps"] if s["layer"] == "support"]
        ascn = r.get("ascNodes") or []
        tree = [s["name"] for s in r["steps"] if s["layer"] in ("notable", "keystone")]
        uniq = [u["name"].split(",")[0] for sl in r.get("uniques") or [] for u in sl["uniques"]]
        items = parse(d["items"])
        top5 = sorted(gems, key=lambda k: -gems[k])[:5]
        rows.append({
            "skill": skill, "asc": asc, "found": d["found"],
            "opt_supports": sup, "ninja_top5": top5,
            "sup_hits": [s for s in sup if s in gems],
            "sup_recall_top5": sum(1 for t in top5 if t in sup) / 5,
            "opt_asc": ascn, "asc_hits": [a for a in ascn if a in passives],
            "opt_keystones": [s["name"] for s in r["steps"] if s["layer"] == "keystone"],
            "keystone_hits": [t for t in tree if t in passives],
            "unique_hits": [u for u in uniq if u in items],
            "ninja_passives": list(passives)[:6], "ninja_uniques": [k for k in items if not k.startswith(("Rare", "Magic"))],
        })
        print("done", skill, file=sys.stderr)

md = ["# PoB build-up vs poe.ninja (Forbidden Rites, 2026-11-23)\n",
      "Supports: optimizer's 5 picks vs the skill's top-10 linked gems on poe.ninja. Ascendancy: optimizer's notables vs "
      "poe.ninja's top passives (ascendancy + keystone mix).\n",
      "| skill | asc (ninja top) | chars | supports hit (of 5) | ninja top-5 recalled | asc nodes hit | optimizer supports | ninja top-5 linked |",
      "|---|---|---|---|---|---|---|---|"]
sh, rc, ah = [], [], []
for r in rows:
    if r.get("error"):
        md.append(f"| {r['skill']} | {r['asc']} | - | error {r['error'][:50]} | | | | |")
        continue
    sh.append(len(r["sup_hits"]) / max(len(r["opt_supports"]), 1))
    rc.append(r["sup_recall_top5"])
    ah.append(len(r["asc_hits"]) / max(len(r["opt_asc"]), 1))
    md.append(f"| {r['skill']} | {r['asc']} | {r['found']} | {len(r['sup_hits'])}/{len(r['opt_supports'])} | "
              f"{r['sup_recall_top5']:.0%} | {len(r['asc_hits'])}/{len(r['opt_asc'])} ({', '.join(r['asc_hits'])}) | "
              f"{', '.join(r['opt_supports'])} | {', '.join(r['ninja_top5'])} |")
md.append(f"\nMean: support precision {st.mean(sh):.0%}, ninja top-5 recall {st.mean(rc):.0%}, ascendancy-node precision {st.mean(ah):.0%}")
md.append("\n## Uniques: optimizer's per-slot top-5 vs poe.ninja's most-used uniques\n")
for r in rows:
    if not r.get("error"):
        md.append(f"- **{r['skill']}**: ninja {', '.join(r['ninja_uniques']) or '-'}; optimizer hit {', '.join(r['unique_hits']) or 'none'}")
(out_dir / "ninja_compare.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
(out_dir / "ninja_compare.md").write_text("\n".join(md))
print("\n".join(md))
