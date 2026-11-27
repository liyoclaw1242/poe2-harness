"""Find multiplier engines: pairs of load-bearing sources that are worth more together than apart.

Usage: PYTHONPATH=harness python3 harness/tools/synergy_sample.py data/builds/sample055 data/results [K]
"""

import collections
import json
import math
import statistics as st
import sys
from pathlib import Path

from pob_agent.engine import Engine
from pob_agent.trade import blank_item

src, d = Path(sys.argv[1]), Path(sys.argv[2])
K = int(sys.argv[3]) if len(sys.argv) > 3 else 10
an = json.loads((d / "decomp_analysis.json").read_text())
INF = 1e9
rows = []
eng, done, failed = None, 0, 0
for bi, b in enumerate(an["builds"]):
    if eng is None or bi % 20 == 0:  # restart periodically: the engine's memory grows
        if eng is not None:
            eng.close()
        eng = Engine()
        eng.start()
    f = src / b["file"]
    try:
        eng.call("load", code=f.read_text().strip())
        items = {i["slot"]: i for i in eng.call("items")["items"]}
        cands = []
        for s in b["sources"]:
            mult = s["mult"] if isinstance(s["mult"], (int, float)) else INF
            if mult >= INF or mult < 1.05:
                continue
            if s["layer"] in ("notable", "keystone", "ascendancy", "jewel") and s["layer"] != "jewel":
                cands.append({"kind": "node", "name": s["name"], "layer": s["layer"]})
            elif s["layer"] == "gear" and s.get("slot") in items and items[s["slot"]].get("base"):
                cands.append({"kind": "slot", "name": s["name"], "slot": s["slot"], "layer": "gear",
                              "raw": blank_item(items[s["slot"]]["raw"], items[s["slot"]]["base"])})
            elif s["layer"] == "support":
                cands.append({"kind": "support", "name": s["name"], "layer": "support"})
            if len(cands) >= K:
                break
        if len(cands) < 2:
            continue
        r = eng.call("synergy", sources=cands)
        layer = {c["name"]: c["layer"] for c in cands}
        for p in r["pairs"]:
            p["la"], p["lb"] = layer[p["a"]], layer[p["b"]]
            p.update(file=b["file"], skill=b["skill"], asc=b["asc"])
            rows.append(p)
        done += 1
        print("ok", b["file"], len(r["pairs"]), file=sys.stderr)
    except Exception as e:
        failed += 1
        print("err", b["file"], str(e)[:120], file=sys.stderr)
        try:
            eng.close()
        except Exception:
            pass
        eng = None
if eng is not None:
    eng.close()
if failed > 0.1 * (done + failed):
    print(f"{failed} builds failed; NOT overwriting results")
    sys.exit(1)

num = lambda v: INF if v == "inf" else v
eng_rows = [p for p in rows if num(p["synergy"]) >= 1.15]
agg = collections.defaultdict(list)
for p in eng_rows:
    k = tuple(sorted([(p["la"], p["a"]), (p["lb"], p["b"])]))
    agg[k].append(p)
cat = sorted(agg.items(), key=lambda kv: (-len(kv[1]), -st.median(min(num(p["synergy"]), 50) for p in kv[1])))
md = ["# Multiplier engines — pairs worth more together than apart\n",
      f"synergy = mult(both removed) / (mult_a × mult_b); listed when ≥ 1.15. {len(rows)} pairs tested over "
      f"{len({p['file'] for p in rows})} builds; {len(eng_rows)} synergistic.\n",
      "| A | B | builds | median synergy | median joint mult | skills |", "|---|---|---|---|---|---|"]
for k, ps in cat[:40]:
    (la, a), (lb, b) = k
    syn = st.median(min(num(p["synergy"]), 50) for p in ps)
    jm = st.median(min(num(p["joint"]), 1e3) for p in ps)
    sk = ", ".join(sorted({p["skill"] for p in ps})[:4])
    md.append(f"| {a} [{la}] | {b} [{lb}] | {len(ps)} | x{syn:.2f} | x{jm:.2f} | {sk} |")
lp = collections.Counter(tuple(sorted([p["la"], p["lb"]])) for p in eng_rows)
md.append("\n## Synergistic pairs by layer combination\n")
md.append(", ".join(f"{a}+{b} {n}" for (a, b), n in lp.most_common()))
per_build = collections.Counter(p["file"] for p in eng_rows)
md.append(f"\nBuilds with ≥1 synergistic pair: {len(per_build)}/{len({p['file'] for p in rows})}")
(d / "synergy_055.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
(d / "synergy_analysis.md").write_text("\n".join(md))
print("\n".join(md))
