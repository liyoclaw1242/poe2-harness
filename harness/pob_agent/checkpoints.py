"""Ascendancy checkpoints: what each trial's two points buy one chosen skill, per ascendancy.

The skill sits on a class template at a campaign stage (gem level, supports and weapon as in leveling probes, no
passive tree). Points are spent the way a player does: every point, a notable with the small node in front of it,
choosing the notable that adds most DPS to this skill. A step that adds nothing is flagged: there the choice is
free and belongs to defence or utility, which this does not score.
"""
from __future__ import annotations

from .engine import Engine
from . import leveling

STEPS = [2, 4, 6, 8]


def run(skill: str, cls: str, stage: str = "asc2", ascendancy: str | None = None, steps=None,
        verbose: bool = False) -> dict:
    p = leveling.stage_params(stage, cls)
    req = {**p, "skill": skill, "class": cls, "steps": steps or STEPS}
    if ascendancy:
        req["ascendancies"] = {ascendancy: True}
    with Engine(verbose) as eng:
        res = eng.call("ascendancy_checkpoints", **req)
    rows = []
    for a in res.get("ascendancies", []):
        if a.get("error"):
            rows.append(a)
            continue
        if not any(s["nodes"] for s in a["steps"]):
            continue  # an ascendancy with no allocatable nodes in this tree version (legacy)
        base = a["before"] or 0
        if base <= 0:
            a["error"] = "no DPS for this skill on the template (the picks would be arbitrary)"
            rows.append(a)
            continue
        prev = base
        for s in a["steps"]:
            s["lift"] = s["dps"] / base if base > 0 else None
            s["step_lift"] = s["dps"] / prev if prev > 0 else None
            s["no_gain"] = s["step_lift"] is not None and s["step_lift"] < 1.005
            prev = s["dps"]
        a["lift"] = a["steps"][-1]["lift"] if a["steps"] else None
        rows.append(a)
    rows.sort(key=lambda a: -(a.get("lift") or 0))
    return {"skill": skill, "class": cls, "stage": stage, "supports": res.get("supports"),
            "weapon": res.get("weaponType"), "ascendancies": rows}
