"""Enabler coverage over a build sample, and candidates for the table.

Usage: enabler_sample.py data/builds/sample055 data/results/enablers_055.json
Per build: table rows present, detected Condition flags, and config conditions worth >= 20% DPS that
no known enabler keeps true (those are where a hidden enabler, or plain author optimism, sits).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pob_agent import analysis, enablers, sources  # noqa: E402
from pob_agent.engine import Engine  # noqa: E402

KINDS = ("self_condition", "skill_option", "enemy_state", "ramp")


def one(eng, path):
    info = eng.call("load", **sources.resolve(str(path)))
    en = enablers.measure(eng)
    backed = enablers.backed_vars(en)
    a = analysis.audit(eng, backed=backed)
    unbacked = [{"var": i.var, "label": (i.label or "").strip(), "kind": i.kind, "dps_pct": i.dps_delta_pct}
                for i in a["items"]
                if i.kind in KINDS and not i.backed_by and (i.dps_delta_pct or 0) >= 20]
    return {"build": path.stem, "skill": (info.get("mainSkill") or {}).get("name"),
            "ascendancy": info.get("ascendancy"),
            "rows": [{k: r[k] for k in ("id", "alone", "cond", "with", "active")} for r in en["rows"]],
            "detected": en["detected"], "backed": backed, "unbacked": unbacked}


def main(src, dst):
    files = sorted(Path(src).glob("*.code"))
    out, errors = [], []
    eng = None
    for n, f in enumerate(files):
        if eng is None or n % 20 == 0:
            if eng:
                eng.close()
            eng = Engine().__enter__()
        try:
            out.append(one(eng, f))
        except Exception as e:  # noqa: BLE001
            errors.append({"build": f.stem, "error": str(e)[:200]})
            eng.close(); eng = None
        print(f"{n + 1}/{len(files)} {f.stem}", file=sys.stderr, flush=True)
    if eng:
        eng.close()
    if len(out) < 0.9 * len(files):
        print(f"only {len(out)}/{len(files)} ok, not writing", file=sys.stderr)
        sys.exit(1)
    table = Counter(r["id"] for b in out for r in b["rows"] if r["active"] or r["id"] == "way_of_the_stonefist")
    det = Counter(d["condition"] for b in out for d in b["detected"])
    unb = Counter(u["label"] or u["var"] for b in out for u in b["unbacked"])
    summary = {"builds": len(out), "errors": errors, "table_hits": table.most_common(),
               "detected": det.most_common(), "unbacked_big_conditions": unb.most_common(40)}
    Path(dst).write_text(json.dumps({"summary": summary, "builds": out}, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
