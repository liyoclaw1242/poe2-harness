"""Target vs bridge: at each campaign stage, how the chosen target skill clears next to the best leveling skill.

Both come from the same per-class probes (same stage, same greedy tree from the class start, PoB-picked supports),
so model errors shared by the two partly cancel; the ratio is a paired comparison, not a ranking of everything.
The target is the player's choice, so it is not scaled by the off-family factor; the bridge is the top of the
leveling ranking (which is). A stage before the target's gate (switch.gates) shows the target as not available.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import leveling, scan, switch

STAGES = ["act1", "pre_asc1", "asc1", "asc2"]
_MISC = Path(__file__).resolve().parents[2] / "vendor" / "PathOfBuilding-PoE2" / "src" / "Data" / "Misc.lua"
_GOLD: list[int] = []


def respec_gold(level: int) -> int:
    """Gold to refund one passive point at a character level (PoB's data.goldRespecPrices)."""
    if not _GOLD:
        m = re.search(r"data\.goldRespecPrices = \{([^}]*)\}", _MISC.read_text())
        _GOLD.extend(int(x) for x in re.findall(r"\d+", m.group(1)))
    return _GOLD[max(1, min(level, len(_GOLD))) - 1]


def off_path(stage: str, cls: str, skill: str, members, target_nodes: set[str]) -> int:
    """Passive points the free-tree bridge spends on notables outside the target build (paths included)."""
    d = leveling.load(stage, cls)
    r = d.get(skill) or d.get((members or [skill])[-1]) or {}
    return sum(p.get("cost") or 0 for p in r.get("picks") or [] if p.get("name") not in target_nodes)


def _is(m: dict, skill: str) -> bool:
    return m["skill"] == skill or skill in (m.get("members") or [])


def compare(target: str, cls: str, stages=None, gate: dict | None = None, tree: str | None = None) -> dict:
    """tree: a target-build suffix from leveling.register_target; the tree is then limited to its notables."""
    gate = gate or switch.gates(target, cls)
    open_from = gate.get("playable_from")
    out = []
    sfx = f"+{tree}" if tree else ""
    for st0 in stages or STAGES:
        st = st0 + sfx
        level = scan.STAGES[st0]["level"]
        key = f"{st},{st0}+clearsup{sfx}"
        if not leveling.load(st, cls):
            out.append({"stage": st0, "level": level, "missing": True})
            continue
        rows = leveling.rank(key, cls)
        bridge = next((m for m in rows if not _is(m, target)), None)
        tgt = [m for m in rows if _is(m, target)]
        # the target as played: its best row, by clear, without the family factor
        t = max(tgt, key=lambda m: m["clear"]) if tgt else None
        gated = open_from is None or level < open_from or t is None
        row = {"stage": st0, "level": level, "members": bridge and bridge.get("members"), "bridge": bridge and bridge["skill"],
               "bridge_clear": bridge and bridge["clear"], "bridge_st": bridge and bridge["st"],
               "target_row": t and t["skill"], "target_clear": t and t["clear"], "target_st": t and t["st"],
               "gated": gated}
        if t and bridge and bridge["clear"] > 0:
            row["ratio"] = t["clear"] / bridge["clear"]
            row["st_ratio"] = t["st"] / bridge["st"] if bridge["st"] else None
        # Switch as soon as the gate opens (rule A, 40/44 vs guides). Gating on ratio >= 1 as well (rule B) matched
        # only 14/44: guides switch while our model still has the bridge ahead, so the ratio is shown, not obeyed.
        row["use_target"] = not gated
        out.append(row)
    return {"target": target, "class": cls, "playable_from": open_from, "tree": tree, "stages": out}


def plan(target: str, cls: str, target_nodes: list[str] | None = None, stages=None) -> dict:
    """Free-tree and (with a target build) on-path bridges per stage, and the respec bill at the switch."""
    gate = switch.gates(target, cls)
    free = compare(target, cls, stages, gate)
    res = {"target": target, "class": cls, "gate": gate, "free": free}
    if target_nodes:
        key = leveling.register_target(target_nodes)
        res["on_path"] = compare(target, cls, stages, gate, tree=key)
        nodes = set(target_nodes)
        for row in free["stages"]:
            if row.get("bridge"):
                pts = off_path(row["stage"], cls, row["bridge"], row.get("members"), nodes)
                row["off_path_points"] = pts
                row["respec_gold"] = pts * respec_gold(row["level"])
    return res
