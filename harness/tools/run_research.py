"""Overnight research run: skill scans (start/mid) + skill x ascendancy lift for every damaging skill.

Usage: PYTHONPATH=harness python3 harness/tools/run_research.py data/results
"""

import json
import sys
import time
from pathlib import Path

from pob_agent import scan
from pob_agent.engine import Engine

out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/results")
out.mkdir(parents=True, exist_ok=True)

with Engine() as eng:
    for tier in ("mid", "start"):
        t = time.time()
        res = scan.run_scan(eng, tier=tier)
        (out / f"scan_{tier}.json").write_text(json.dumps(res, ensure_ascii=False))
        print(f"scan {tier}: {len(res)} skills in {time.time() - t:.0f}s", flush=True)

    rows = scan.score(json.loads((out / "scan_mid.json").read_text()))
    skills = [r["skill"] for r in rows]
    lifts = []
    t = time.time()
    params = dict(scan.TIERS["mid"])
    for i in range(0, len(skills), 10):
        chunk = skills[i:i + 10]
        try:
            lifts += eng.call("ascendancy_lift", skills=chunk, points=8, **params)["results"]
        except Exception as exc:  # keep the run alive
            print(f"lift chunk {chunk} failed: {exc}", flush=True)
        (out / "lift_mid.json").write_text(json.dumps(lifts, ensure_ascii=False))
        print(f"lift {i + len(chunk)}/{len(skills)} ({time.time() - t:.0f}s)", flush=True)
print("done", flush=True)
