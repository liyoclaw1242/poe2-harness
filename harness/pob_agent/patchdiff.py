"""Patch diff for the switch-readiness gates: run the same gate facts on two PoB-PoE2 checkouts (e.g. 0.5.5 and
the 1.0 data drop) and list what moved: skills added or removed, tier (so the level a skill becomes usable),
accepted weapons, spirit reservation, and the ascendancy notable that grants a tier-0 skill."""
from __future__ import annotations

from .engine import Engine
from . import switch


def _facts(pob_src, skills=None) -> tuple[str | None, dict]:
    with Engine(pob_src=pob_src) as eng:
        names = skills or [s["name"] for s in eng.call("list_skills")["skills"]]
        res = eng.call("skill_gates", skills=names)["results"]
        return eng.version, {r["skill"]: r for r in res if not r.get("error")}


def _sig(f: dict) -> dict:
    lv1 = (f.get("levels") or [{}])[0]
    return {"tier": f.get("tier"), "weapon": f.get("weapon"), "spirit": lv1.get("spirit"),
            "granted_by": sorted(f"{g['node']} ({g['ascendancy']})" for g in f.get("grantedBy") or [])}


def gate_diff(old_src, new_src=None, skills=None) -> dict:
    v_old, old = _facts(old_src, skills)
    v_new, new = _facts(new_src, skills)
    changes = []
    for name in sorted(set(old) | set(new)):
        if name not in old:
            changes.append({"skill": name, "change": "added", "new": _sig(new[name])})
        elif name not in new:
            changes.append({"skill": name, "change": "removed", "old": _sig(old[name])})
        else:
            a, b = _sig(old[name]), _sig(new[name])
            diff = {k: (a[k], b[k]) for k in a if a[k] != b[k]}
            if diff:
                row = {"skill": name, "change": "changed", "fields": diff}
                if "tier" in diff and (a["tier"] or 0) >= 1 and (b["tier"] or 0) >= 1:
                    row["level"] = (switch.level_for_tier(a["tier"]), switch.level_for_tier(b["tier"]))
                changes.append(row)
    return {"old_version": v_old, "new_version": v_new, "changes": changes}
