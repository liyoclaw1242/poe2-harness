"""Backtest the leveling ranking against community picks, with an ablation over scoring terms.

    python3 tools/leveling_backtest.py pre_asc1 [--detail]

Needs `leveling.collect` to have filled data/results/leveling_cache/<stage>/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pob_agent import leveling  # noqa: E402

# each step adds one scoring term on top of the previous one
OFF = {"sets": False, "no_conditional": False, "attrs": False, "attr_pool": False, "clear": False, "pairs": False,
       "mana": False, "class_weapon": False, "caster_family": False, "setup": False,
       "rotation": 1, "burst": False, "fire_forget": False, "family": "weapon", "off_weapon_factor": 0.5}
ABLATION = [
    ("v0 first stat set, single-target DPS", {**OFF}),
    ("+ all stat sets and minions", {**OFF, "sets": True}),
    ("+ skip conditional variants", {**OFF, "sets": True, "no_conditional": True}),
    ("+ attribute requirements (free pool)", {**OFF, "sets": True, "no_conditional": True, "attrs": True,
                                              "attr_pool": True}),
    ("+ pack-clear proxy", {**OFF, "sets": True, "no_conditional": True, "attrs": True, "attr_pool": True,
                            "clear": True}),
    ("+ spread pairs (Contagion)", {**OFF, "sets": True, "no_conditional": True, "attrs": True,
                                    "attr_pool": True, "clear": True, "pairs": True}),
    ("+ class starting weapon (off-weapon x0.5)", {**OFF, "sets": True, "no_conditional": True, "attrs": True,
                                                  "attr_pool": True, "clear": True, "pairs": True,
                                                  "class_weapon": True}),
    ("+ spells off-family for martial classes", {**OFF, "sets": True, "no_conditional": True, "attrs": True,
                                                 "attr_pool": True, "clear": True, "pairs": True,
                                                 "class_weapon": True, "caster_family": True}),
    ("+ setup skills (corpses, consume) x0.5", {**OFF, "sets": True, "no_conditional": True, "attrs": True,
                                                "attr_pool": True, "clear": True, "pairs": True,
                                                "class_weapon": True, "caster_family": True, "setup": True}),
    ("+ cooldown rotation x3", {**OFF, "sets": True, "no_conditional": True, "attrs": True, "attr_pool": True,
                                "clear": True, "pairs": True, "class_weapon": True, "caster_family": True,
                                "setup": True, "rotation": 3}),
    ("+ stored-use burst", {**OFF, "sets": True, "no_conditional": True, "attrs": True, "attr_pool": True,
                            "clear": True, "pairs": True, "class_weapon": True, "caster_family": True,
                            "setup": True, "rotation": 3, "burst": True}),
    ("+ DoT fire-and-forget", {**OFF, "sets": True, "no_conditional": True, "attrs": True, "attr_pool": True,
                               "clear": True, "pairs": True, "class_weapon": True, "caster_family": True,
                               "setup": True, "rotation": 3, "burst": True, "fire_forget": True}),
    ("+ family = gem colour and weapon (x0.25)", {**OFF, "sets": True, "no_conditional": True, "attrs": True,
                                                  "attr_pool": True, "clear": True, "pairs": True,
                                                  "class_weapon": True, "caster_family": True, "setup": True,
                                                  "rotation": 3, "burst": True, "fire_forget": True,
                                                  "family": "attr", "off_weapon_factor": 0.25}),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage")
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--only", help="run one ablation step by index")
    args = ap.parse_args()
    steps = ABLATION if args.only is None else [ABLATION[int(args.only)]]
    classes = list(leveling.BACKTEST)
    print("| step | passed | MRR | " + " | ".join(classes) + " |")
    print("|---|---|---|" + "---|" * len(classes))
    results = []
    for name, cfg in steps:
        bt = leveling.backtest(args.stage, cfg)
        results.append((name, bt))
        cells = []
        for c in classes:
            r = bt["classes"].get(c)
            if not r:
                cells.append("—")
            else:
                cells.append(f"{r['best_rank'] or '×'}{'' if r['pass'] else '✗'}")
        print(f"| {name} | {bt['passed']}/{bt['total']} | {bt['mrr']:.2f} | " + " | ".join(cells) + " |")
    if args.detail:
        name, bt = results[-1]
        print(f"\n### top 5 per class ({name})")
        for c, r in bt["classes"].items():
            print(f"- {c}: " + ", ".join(r["top"]) + f"  (picks: {r['ranks']})")


if __name__ == "__main__":
    main()
