"""Scenario semantics: what enemy a number assumes, and which pieces only work against some enemies.

PoB's default enemy is a Guardian/Pinnacle boss (level 82+, 50% elemental resistances, boss armour).
Veterans spend most of their time mapping against 0%-resistance monsters, so a panel number and the
multiplier of each piece can mean different things depending on the enemy. Example: Rakiata's Flow
inverts enemy elemental resistance; it is x2.18 against a 50%-resistance pinnacle boss and does
nothing against 0%-resistance map monsters.

`scenarios()` evaluates the build against PoB's four enemy tiers (author overrides of enemy stats
are cleared so every tier uses PoB's own defaults, and the overrides are listed), and measures the
given sources leave-one-out in each tier. `dependent()` picks the pieces whose multiplier moves the
most between tiers.
"""

from __future__ import annotations

from .engine import Engine
from .trade import blank_item

INF = float("inf")
TIERS = ("map", "boss", "pinnacle", "uber")


def _m(v):
    return INF if v == "inf" else float(v)


def sources_from_decompose(d: dict, items: dict, limit: int = 18, min_mult: float = 1.05,
                           supports: list[str] | None = None) -> list[dict]:
    """Synergy-format sources from a decompose result: every main-group support, then the strongest
    ascendancy/notable/keystone nodes and gear (jewels are not measured here)."""
    out = []
    # supports are always measured: a support can be worthless under the author's enemy and large
    # under another (Rakiata's Flow against hand-set negative resistances)
    if supports is None:
        supports = [s["name"] for s in d["sources"] if s["layer"] == "support" and s["mult"] != INF]
    for name in supports:
        out.append({"kind": "support", "name": name, "layer": "support"})
    for s in d["sources"]:
        if s["mult"] == INF or s["mult"] < min_mult or s["layer"] == "support":
            continue
        if s["layer"] in ("notable", "keystone", "ascendancy"):
            out.append({"kind": "node", "name": s["name"], "layer": s["layer"]})
        elif s["layer"] == "gear" and s.get("slot") in items and items[s["slot"]].get("base"):
            out.append({"kind": "slot", "name": s["name"], "slot": s["slot"], "layer": "gear",
                        "raw": blank_item(items[s["slot"]]["raw"], items[s["slot"]]["base"])})
        if len(out) >= limit:
            break
    return out


def scenarios(eng: Engine, sources: list[dict] | None = None, keep_overrides: bool = False) -> dict:
    req = [{k: v for k, v in s.items() if k in ("kind", "name", "slot", "raw")} for s in sources or []]
    res = eng.call("scenarios", sources=req, keepOverrides=keep_overrides)
    tiers = {sc["name"]: sc for sc in res["scenarios"]}
    rows = []
    for i, s in enumerate(sources or []):
        mults = {t: _m(tiers[t]["sources"][i]) for t in TIERS if t in tiers and i < len(tiers[t]["sources"])}
        rows.append({"name": s["name"], "layer": s.get("layer", s["kind"]), "mult": mults})
    return {"configured": res["configured"], "overrides": res["overrides"],
            "tiers": [tiers[t] for t in TIERS if t in tiers], "as_configured": res["asConfigured"],
            "sources": rows}


def dependent(rows: list[dict], min_spread: float = 1.15) -> list[dict]:
    """Sources whose multiplier differs between map monsters and pinnacle bosses by >= min_spread.

    `favours` is the tier where the piece is worth more; `spread` = larger mult / smaller mult.
    """
    out = []
    for r in rows:
        m = r["mult"]
        a, b = m.get("map"), m.get("pinnacle")
        if a is None or b is None or INF in (a, b):
            continue
        spread = max(a, b) / min(a, b)
        if spread >= min_spread:
            out.append({**r, "spread": spread, "favours": "pinnacle" if b > a else "map"})
    out.sort(key=lambda r: -r["spread"])
    return out


def headline(sc: dict) -> dict:
    """Map vs pinnacle DPS in one line, for the summary."""
    t = {x["name"]: x for x in sc["tiers"]}
    return {"configured": sc["configured"], "map": t.get("map", {}).get("dps"),
            "pinnacle": t.get("pinnacle", {}).get("dps"), "uber": t.get("uber", {}).get("dps"),
            "overrides": sc["overrides"]}
