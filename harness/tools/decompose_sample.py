"""Run multiplier decomposition over a directory of builds.

Usage: PYTHONPATH=harness python3 harness/tools/decompose_sample.py data/builds/sample055 data/results/decomp_055.json
"""

import json
import math
import sys
from pathlib import Path

from pob_agent.decompose import decompose
from pob_agent.engine import Engine, EngineError

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
manifest = {m["file"]: m for m in json.loads((src / "manifest.json").read_text())}
rows = []


def clean(o):
    if isinstance(o, float) and math.isinf(o):
        return "inf"
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    return o


RESTART_EVERY = 20  # one long-lived LuaJIT engine grows; restart it periodically and after any failure
part = dst.with_suffix(".partial.json")
files = sorted(src.glob("*.code"))
eng = None
for n, f in enumerate(files):
    if eng is None or n % RESTART_EVERY == 0:
        if eng is not None:
            eng.close()
        eng = Engine()
        eng.start()
    m = manifest.get(f.name, {})
    try:
        info = eng.call("load", code=f.read_text().strip())
        d = decompose(eng, conditions=False)  # conditions come from profiles_055.json
        ms = info.get("mainSkill") or {}
        rows.append(clean({"file": f.name, "title": m.get("title"), "ascendancy": info.get("ascendancy"),
                           "class": info.get("className"), "main_skill": ms.get("name"),
                           "normalized": info.get("normalized"), **d}))
        print("ok", f.name, ms.get("name"), file=sys.stderr)
    except (EngineError, Exception) as e:  # keep going on bad pastes; restart a dead engine
        rows.append({"file": f.name, "error": str(e)[:300]})
        print("err", f.name, str(e)[:120], file=sys.stderr)
        try:
            eng.close()
        except Exception:
            pass
        eng = None
    part.write_text(json.dumps(rows, ensure_ascii=False, indent=1))  # progress survives a crash
if eng is not None:
    eng.close()
ok = sum(1 for r in rows if not r.get("error"))
if ok < 0.9 * len(files):
    print(f"only {ok}/{len(files)} decomposed; NOT overwriting {dst} (see {part})")
    sys.exit(1)
dst.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
part.unlink(missing_ok=True)
print(f"{ok}/{len(rows)} decomposed -> {dst}")
