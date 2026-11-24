"""PoB-data-only skill strength scan and backtest against observed builds.

At a new league launch only Path of Building's data is reliable. The scan puts
every active skill on the same standardised character, greedily picks its best
supports with PoB's own calculator, measures the multipliers PoB hides behind
stack/stage config (ramp), and how strongly it scales with cheap stats.
"""

from __future__ import annotations

import math
from collections import Counter

from .engine import Engine

# Standardised characters. Mods are applied as PoB custom modifiers so every
# skill sees the same generic power; weapons are a plain base of the right type.
TIERS = {
    "start": {
        "level": 70, "weaponLevel": 45, "gemLevel": 16, "gemQuality": 0, "supports": 3,
        "templateMods": "60% increased Damage\n20% increased Critical Hit Chance",
        "weaponMods": "60% increased Physical Damage\nAdds 8 to 14 Physical Damage",
    },
    "mid": {
        "level": 90, "weaponLevel": 65, "gemLevel": 20, "gemQuality": 20, "supports": 5,
        "templateMods": "150% increased Damage\n60% increased Critical Hit Chance\n+40% to Critical Damage Bonus\n"
                        "+2 to Level of all Skills\n10% increased Skill Speed",
        "weaponMods": "150% increased Physical Damage\nAdds 20 to 38 Physical Damage\n15% increased Attack Speed",
    },
}

# Campaign stages follow ascendancy trials (each trial = 2 ascendancy points):
#   pre_asc1  before the first trial (no ascendancy)        <- implemented
#   asc1      after trial 1, before trial 2 (2 points)      <- todo
#   asc2      after trial 2, before trial 3 (4 points)      <- todo
#   endgame   the target build itself
# "act1" is an early snapshot inside pre_asc1. Levels and the gem/support tier limits are assumptions
# about when uncut gems of each level drop; calibrate them against real campaign exports. Enemy =
# normal monsters (PoB tier "None": enemy level = character level, 0% resistances). No gear mods: a
# plain weapon base of the stage's level only, so these numbers rank skills, they are not in-game DPS.
# Calibration (docs/research/2026-11-24-leveling-builds.md): fixed quest rewards give uncut skill gems
# L2-L5 in Act 1 and L6-L7 in Act 2; support tier 2 drops from area level ~16; a gem has 2 support
# sockets until Lesser Jeweller's Orbs (monster level 25+). Trial 1 is in Act 2 (level ~21-28).
STAGES = {
    "act1": {"level": 12, "maxSkillTier": 5, "gemLevel": 5, "maxSupportTier": 1, "supports": 2,
             "treePoints": 12, "weaponLevel": 10},
    "pre_asc1": {"level": 24, "maxSkillTier": 7, "gemLevel": 7, "maxSupportTier": 2, "supports": 2,
                 "treePoints": 25, "weaponLevel": 22},
    # after trial 1 (2 ascendancy points) and after trial 2 (4 points). Assumptions: trial 1 in Act 2, trial 2
    # in Act 3; quest gems L9/L10 in Act 3; support tier 3 from area ~33, tier 4 from ~45; third socket from
    # Lesser Jeweller's Orbs (monster level 25+).
    "asc1": {"level": 32, "maxSkillTier": 9, "gemLevel": 9, "maxSupportTier": 2, "supports": 3,
             "treePoints": 33, "weaponLevel": 30, "ascPoints": 2},
    "asc2": {"level": 45, "maxSkillTier": 11, "gemLevel": 11, "maxSupportTier": 4, "supports": 3,
             "treePoints": 47, "weaponLevel": 43, "ascPoints": 4},
}
STAGE_COMMON = {"impliedConditions": True, "capGemByLevel": True, "gemQuality": 0, "enemyIsBoss": "None", "templateMods": "",
                "weaponMods": ""}


def run_campaign(eng_factory, stage: str = "pre_asc1", top: int = 15, classes: list[str] | None = None,
                 progress: bool = False, chunk: int = 3) -> dict:
    """Rank the stage's skills once, then run the per-class tree step a few skills per fresh engine
    (one engine building hundreds of characters runs out of memory)."""
    params = {**STAGE_COMMON, **STAGES[stage], "progress": progress}
    params.setdefault("maxPath", params["treePoints"])
    if classes:
        params["classes"] = {c: True for c in classes}
    with eng_factory() as eng:
        scanned = eng.call("skill_scan", **params)["results"]
    ranked = sorted((r for r in scanned if (r.get("supportedDPS") or 0) > 0), key=lambda r: -r["supportedDPS"])
    names = [r["gem"] for r in ranked[:top]]
    results = []
    for i in range(0, len(names), chunk):
        part = names[i:i + chunk]
        with eng_factory() as eng:
            res = eng.call("campaign", **{**params, "skills": part, "top": len(part)})
        order = {n: k for k, n in enumerate(part)}
        results += sorted(res["results"], key=lambda x: order.get(x["skill"], 99))
    return {"scanned": len(scanned), "withDamage": len(ranked), "results": results}


PROBES = [
    {"name": "gem_level", "mod": "+1 to Level of all Skills"},
    {"name": "inc_damage", "mod": "20% increased Damage"},
    {"name": "skill_speed", "mod": "10% increased Skill Speed"},
    {"name": "crit_chance", "mod": "50% increased Critical Hit Chance"},
    {"name": "extra_ele", "mod": "Gain 10% of Damage as Extra Lightning Damage"},
]


def run_scan(eng: Engine, tier: str = "mid", skills: list[str] | None = None,
             allow_lineage: bool = False, progress: bool = False) -> list[dict]:
    params = dict(TIERS[tier])
    params.update({"probes": PROBES, "allowLineage": allow_lineage, "progress": progress})
    if skills:
        params["skills"] = skills
    return eng.call("skill_scan", **params)["results"]


def ramp_factor(result: dict) -> tuple[float, list[str]]:
    """Largest capped multiplier hidden behind a single stack/stage/condition option.

    Options that feed the same variable are deduped (trust the capped curve);
    uncapped curves are ignored as unreliable (PoB has no cap for them).
    """
    best, notes, by_feed = 1.0, [], {}
    for r in result.get("ramp") or []:
        dps = [c["dps"] for c in r["curve"]]
        lo, hi = dps[0], max(dps)
        if lo <= 0 or hi <= lo * 1.02:
            continue
        capped = r["type"] == "check" or dps[-1] <= dps[-2] * 1.0001 if len(dps) > 1 else True
        key = tuple(r.get("feeds") or [r["var"]])
        prev = by_feed.get(key)
        if prev is None or (capped and not prev[1]):
            by_feed[key] = (hi / lo, capped, r["label"] or r["var"])
    capped_feeds = [set(k) for k, v in by_feed.items() if v[1]]
    for key, (ratio, capped, label) in by_feed.items():
        if not capped and any(set(key) <= cf for cf in capped_feeds):
            continue  # duplicate uncapped path into a capped mechanic
        if capped:
            notes.append(f"{label.strip()} x{ratio:.2f}")
            best = max(best, ratio)
    return best, notes


# Only hard gates: a resource that must be built before the skill can be used at all.
# ("Consume X" is deliberately not here - consuming stacks is usually the power source.)
GATING_TAGS = {"Conditional", "Detonator"}
GATING_WORDS = ("glory", "corpse", "when you have maximum")


def gating(result: dict) -> list[str]:
    """Reasons a skill cannot simply be pressed at will (PoB's DPS ignores the setup cost)."""
    reasons = [t for t in (result.get("tags") or "").replace(" ", "").split(",") if t in GATING_TAGS]
    desc = (result.get("description") or "").lower()
    reasons += [w for w in GATING_WORDS if w in desc]
    return reasons


def score(results: list[dict], descriptions: dict[str, str] | None = None) -> list[dict]:
    rows = []
    for r in results:
        if descriptions and not r.get("description"):
            r["description"] = descriptions.get(r.get("gem"))
    for r in results:
        dps = r.get("supportedDPS") or r.get("baseDPS") or 0
        if not dps or r.get("error"):
            continue
        rf, notes = ramp_factor(r)
        el = r.get("elasticity") or {}
        rows.append({
            "skill": r["gem"], "type": r.get("gemType"), "weapon": r.get("weaponType"), "tags": r.get("tags"),
            "base_dps": r.get("baseDPS"), "supported_dps": dps, "support_mult": r.get("supportMult"),
            "supports": [s["name"] for s in r.get("supports", [])],
            "ramp_factor": rf, "ramp_notes": notes, "potential_dps": dps * rf,
            "gem_level_elasticity": el.get("gem_level"), "elasticity": el,
            "gated": gating(r),
        })
    # Rank inside each damage family: attacks of one weapon class, spells, minions.
    def family(row):
        return f"Attack/{row['weapon']}" if row["type"] == "Attack" and row["weapon"] else row["type"]

    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(family(row), []).append(row)
    allvals = [math.log(r["potential_dps"]) for r in rows if r["potential_dps"] > 0]
    for fam, members in groups.items():
        vals = [math.log(m["potential_dps"]) for m in members]
        mu = sum(vals) / len(vals)
        sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1.0
        for m in members:
            m["family"] = fam
            m["z_in_family"] = (math.log(m["potential_dps"]) - mu) / sd if len(members) > 2 else 0.0
    gmu = sum(allvals) / len(allvals)
    gsd = (sum((v - gmu) ** 2 for v in allvals) / len(allvals)) ** 0.5 or 1.0
    for r in rows:
        r["z_global"] = (math.log(r["potential_dps"]) - gmu) / gsd
        flags = []
        if r["ramp_factor"] >= 2:
            flags.append("hidden-multiplier")
        if (r["gem_level_elasticity"] or 0) >= 0.12:
            flags.append("scales-with-gem-level")
        if r["z_in_family"] >= 1.0:
            flags.append("family-outlier")
        if r["gated"]:
            flags.append("needs-setup")
        r["flags"] = flags
        # PoB's DPS assumes the skill can be used freely; skills gated behind a resource
        # (Glory, consumed charges, corpses, triggers) are discounted.
        r["score"] = 0.6 * r["z_in_family"] + 0.4 * r["z_global"] - (0.75 if r["gated"] else 0.0)
    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                rk[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return rk
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else 0.0


def backtest(scored: list[dict], observed_skills: list[str], top_n: int = 30) -> dict:
    """Compare the PoB-only ranking with how often each skill is a main skill in real builds."""
    counts = Counter(observed_skills)
    by_skill = {r["skill"]: r for r in scored}
    used = [s for s in counts if s in by_skill]
    xs = [by_skill[s]["score"] for s in used]
    ys = [counts[s] for s in used]
    top = {r["skill"] for r in scored[:top_n]}
    popular = [s for s, _ in counts.most_common(15) if s in by_skill]
    recall = sum(1 for s in popular if s in top) / len(popular) if popular else 0.0
    return {
        "observed_main_skills": dict(counts.most_common()),
        "matched": len(used),
        "unmatched": [s for s in counts if s not in by_skill],
        "spearman_score_vs_usage": spearman(xs, ys) if len(used) > 2 else None,
        f"top{top_n}_recall_of_15_most_used": recall,
        "popular_ranks": {s: by_skill[s]["rank"] for s in popular},
        "pool_size": len(scored),
    }
