"""Switch-readiness checklist: when a target skill becomes usable in the campaign, and what blocks it.

Every gate is read from game data, not estimated:
  - skill tier: the uncut skill gem level the gem needs. When that level drops is taken from poe2wiki's drop
    table by area level (skill gem L2 at area 4, L5 at 15, L10 at 37, L14 at 58), interpolated; the character
    level is assumed to track the area level in the campaign.
  - tier 0: not a regular uncut gem. An ascendancy notable that grants it is named; otherwise item- or
    reward-granted.
  - weapon: the weapon types the skill accepts, against the class's starting weapon.
  - attributes: requirement of the gem at the level usable then, against the class's base attributes
    (PoE2 gives no attributes per level; each tree attribute node gives 5).
  - spirit: the reservation is shown; spirit income is not modelled ("not checked").
Supports are not gated: the target's supports are a build choice, not part of the skill.
"""
from __future__ import annotations

import math

from .engine import Engine
from . import leveling

# poe2wiki: uncut skill gem level that can drop at an area level (L1 from the start)
GEM_DROP = [(1, 1), (2, 4), (5, 15), (10, 37), (14, 58), (20, 80)]
# poe2wiki / poe-vault: support gem tier by area level
SUPPORT_DROP = [(1, 1), (2, 16), (3, 33), (4, 45), (5, 55)]
ACTS = [("Act 1", 1, 15), ("Act 2", 16, 28), ("Act 3", 29, 40), ("Act 4", 41, 50), ("Interludes", 51, 64),
        ("maps", 65, 100)]
ATTR_PER_NODE = 5
# first ascendancy trial (Trial of the Sekhemas, Act 2): about level 22 (maxroll), some guides delay to 27+
TRIAL1_LEVEL = 22


def level_for_tier(tier: int, table=GEM_DROP) -> int:
    """Character level at which an uncut gem of this level can drop (linear between table points)."""
    if tier <= table[0][0]:
        return table[0][1]
    for (t0, l0), (t1, l1) in zip(table, table[1:]):
        if tier <= t1:
            return math.ceil(l0 + (tier - t0) * (l1 - l0) / (t1 - t0))
    return table[-1][1]


def act_for(level: int) -> str:
    return next((name for name, lo, hi in ACTS if lo <= level <= hi), "maps")


def gates(skill: str, cls: str, facts: dict | None = None) -> dict:
    if facts is None:
        with Engine() as eng:
            facts = eng.call("skill_gates", skills=[skill])["results"][0]
    if facts.get("error"):
        return {"skill": skill, "class": cls, "error": facts["error"]}
    leveling._load_class_base()
    base = leveling.CLASS_BASE.get(cls, {})
    rows = []
    tier = facts.get("tier") or 0
    if tier >= 1:
        lvl = level_for_tier(tier)
        rows.append({"gate": "skill gem", "detail": f"tier {tier}: an uncut skill gem of level {tier} drops from "
                     f"area level ~{lvl}", "level": lvl})
    else:
        by = facts.get("grantedBy") or []
        if by:
            names = ", ".join(f"{g['node']} ({g['ascendancy']})" for g in by)
            rows.append({"gate": "granted", "detail": f"granted by the ascendancy notable {names}: from the first "
                         f"trial (~level {TRIAL1_LEVEL}) if it is your first pick", "level": TRIAL1_LEVEL,
                         "ascendancy": by[0]["ascendancy"], "node": by[0]["node"]})
        else:
            rows.append({"gate": "granted", "detail": "not a regular uncut gem: comes from an item or a reward",
                         "level": None, "blocked": True})
    own = leveling.CLASS_WEAPON.get(cls)
    ws = facts.get("weapons") or []
    if ws:
        types = [w["type"] for w in ws]
        ok = own and any(own in t for t in types)
        lvl = min((w.get("minLevel") or 1) for w in ws)
        rows.append({"gate": "weapon", "detail": f"needs {' or '.join(types)}" +
                     ("" if ok else f" (the {cls} starts with a {own}: find or buy one)"),
                     "level": lvl, "off_class": not ok})
    start = max([r["level"] for r in rows if r.get("level")] or [1])
    lv = [l for l in facts.get("levels") or [] if l["charLevel"] <= start]
    if lv:
        g = lv[-1]
        need = {a: max(0, (g[a] or 0) - base.get(a, 0)) for a in ("str", "dex", "int")}
        short = sum(need.values())
        if short:
            nodes = math.ceil(short / ATTR_PER_NODE)
            rows.append({"gate": "attributes", "detail": f"gem level {g['level']} needs "
                         + ", ".join(f"{g[a]} {a.title()}" for a in need if need[a])
                         + f": ~{nodes} attribute nodes over the {cls} base (before attributes picked up on the tree path)",
                         "level": None})
        if g.get("spirit"):
            rows.append({"gate": "spirit", "detail": f"reserves {g['spirit']} spirit (spirit income not checked)",
                         "level": None})
    blocked = [r for r in rows if r.get("blocked")]
    return {"skill": skill, "class": cls, "tier": tier, "gates": rows,
            "playable_from": None if blocked else start, "act": None if blocked else act_for(start)}
