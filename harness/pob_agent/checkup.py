"""Leveling check-up: what to change on a campaign character, measured on the character's own PoB export.

Each line is a PoB calculation on the imported build, except the clear-speed estimate (the leveling ranking's pack
model):
  - main skills: every damaging socket group valued as the leveling ranking values a skill (best hit stat set
    plus best DoT-only stat set), so a DoT skill is judged by its DoT.
  - supports: what each socketed support adds (x1.00 = PoB sees no effect, e.g. a minion-draining support with
    no minion PoB counts), and the best support set of the same size from supports the character can have now,
    once for clearing packs (DPS x monsters a use reaches; a DoT counts fully only if one cast kills a magic
    monster) and once for bosses (single-target DPS).
  - gem levels: the main skills at the levels uncut gems reach by the character's level.
  - Spirit: free Spirit, and the persistent skill that adds most to the main skill with it.
  - passives: allocated points against level - 1, and nodes that add nothing to the main skill.
Gem and support availability come from the drop tables in `switch` (area level ~ character level).
"""
from __future__ import annotations

from . import switch
from .engine import Engine
from . import sources
from . import leveling


def support_checks(eng, group: int, sup_tier: int, spreader: int | None = None) -> dict:
    """Best support set for bosses (single-target DPS, greedy in PoB) and for clearing packs.

    Clear is the leveling ranking's own pack model (an estimate, not a PoB number) over the candidate sets the
    ranking itself chooses between: the supports socketed now, the DPS-best set and the area-best set (the
    "clearsup" variant). When the build also uses a spreader (Contagion) and this skill is a chaos DoT, the sets are
    scored as the ranking scores the pair (leveling.pair_metrics): the spreader covers the pack, so reach supports
    that cost DPS lose. `spreader` is that skill's socket group."""
    kw = dict(group=group, maxSupportTier=sup_tier, slots=2)
    out = {}
    runs = {obj: eng.call("checkup_supports", objective=obj, **kw) for obj in ("boss", None, "clear")}
    for obj, sc in runs.items():
        if any(p.get("elsewhere") for p in sc["best"]):
            sc["own"] = eng.call("checkup_supports", objective=obj, excludeElsewhere=True, **kw)
    out["boss"] = runs["boss"]
    current = runs["boss"]["current"]

    # (label, picks); picks None = as socketed now
    cands = [("current", None)]
    for obj in (None, "clear"):
        sc = runs[obj]
        cands.append((obj or "dps", sc["best"]))
        if sc.get("own"):
            cands.append(((obj or "dps") + "-own", sc["own"]["best"]))
    rows = eng.call("checkup_probe_sets", group=group,
                    sets=[None if p is None else [x["name"] for x in p] for _, p in cands])["rows"]
    cfg = {**leveling.DEFAULT, "loadout": False}
    sp = None
    if spreader is not None and spreader != group:
        sp_row = eng.call("checkup_probe_sets", group=spreader, sets=[None])["rows"][0]
        sp = leveling.metrics(sp_row, cfg)
    scored = []
    for (label, picks), row in zip(cands, rows):
        m = leveling.metrics(row, cfg)
        if not m:
            continue
        pair = leveling.pair_metrics(sp, m, cfg) if sp else None
        scored.append({"label": label, "picks": picks, "elsewhere": any(x.get("elsewhere") for x in picks or []),
                       "clear": (pair or m)["clear"], "st": m["st"], "pair": pair["skill"] if pair else None})
    cur = next((c for c in scored if c["label"] == "current"), None)
    if not cur or cur["clear"] <= 0:
        out["clear"] = {"best": [], "mult": None, "current": current, "candidates": scored, "unscored": True}
        return out
    best = max(scored, key=lambda c: c["clear"])
    own = [c for c in scored if not c["elsewhere"]]
    best_own = max(own, key=lambda c: c["clear"]) if own else None

    def view(c):
        picks = [{"name": n} for n in current] if c["picks"] is None else \
            [{"name": x["name"], "elsewhere": x.get("elsewhere")} for x in c["picks"]]
        return {"best": picks, "mult": c["clear"] / cur["clear"], "dpsMult": c["st"] / cur["st"] if cur["st"] else None,
                "from": c["label"], "pair": c["pair"]}
    clear = view(best)
    clear.update(current=current, candidates=scored)
    if best["elsewhere"] and best_own:
        clear["own"] = view(best_own)
    out["clear"] = clear
    return out


def max_level_for(level: int, table) -> int:
    """Highest uncut gem level / support tier that can have dropped by this character level."""
    best = 1
    for t in range(1, table[-1][0] + 1):   # the table's last row is the highest tier/level there is
        if switch.level_for_tier(t, table) <= level:
            best = t
    return best


def run(build: str, top: int = 2, spirit: bool = True, verbose: bool = False, nxt: bool = True) -> dict:
    with Engine(verbose) as eng:
        info = eng.call("load", **sources.resolve(build))
        prep = eng.call("checkup_prepare")
        level = int(info.get("level") or eng.call("tree_nodes").get("level") or 1)
        gem_max = max_level_for(level, switch.GEM_DROP)
        sup_tier = max_level_for(level, switch.SUPPORT_DROP)
        groups = sorted(eng.call("checkup_groups")["groups"], key=lambda g: -g["value"])
        main = groups[:top]
        spreader = next((g["index"] for g in groups if g["skill"] in leveling.SPREAD), None)
        for g in main:
            # a skill granted by an item (a wand's Chaos Bolt) has no gem to level
            if not g.get("source"):
                g["levels"] = eng.call("checkup_gem_levels", group=g["index"], maxLevel=gem_max)
            g["support_checks"] = support_checks(eng, g["index"], sup_tier, spreader)
        tree = eng.call("checkup_tree", group=main[0]["index"]) if main else None
        val = eng.call("checkup_value", group=main[0]["index"]) if main else {}
        # next passives / next ascendancy trial / mana sustain / empty jewel sockets (after checkup_value: the call
        # selects the main group the same way)
        nexts = eng.call("checkup_next", group=main[0]["index"]) if main and nxt else None
        th = eng.call("thresholds")
        spirit_gems = (eng.call("checkup_spirit_gems", maxTier=gem_max, spirit=val.get("spiritUnreserved") or 0)["gems"]
                       if spirit else [])
    out = {"minions": prep, "level": level, "gem_max": gem_max, "support_tier": sup_tier, "groups": groups, "main": main,
           "tree": tree, "spirit_free": val.get("spiritUnreserved"), "thresholds": th, "spirit_options": [],
           "spirit_checked": bool(spirit), "next": nexts}
    if spirit and main and (val.get("spiritUnreserved") or 0) > 0:
        base = val["value"]
        for gem in spirit_gems:
            with Engine(verbose) as eng:
                eng.call("load", **sources.resolve(build))
                eng.call("checkup_prepare")
                try:
                    eng.call("paste_skill", text=f"{gem['name']} {gem_max}/0  1\n", main=False)
                    r = eng.call("checkup_value", group=main[0]["index"])
                except Exception:
                    continue
            if (r.get("spiritUnreserved") or 0) >= 0 and r["value"] > base * 1.01:
                out["spirit_options"].append({**gem, "mult": r["value"] / base, "spirit_left": r["spiritUnreserved"]})
        out["spirit_options"].sort(key=lambda x: -x["mult"])
    return out
