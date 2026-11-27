"""Multiplier decomposition: where a build's main-skill DPS comes from.

Every source is measured leave-one-out: mult = DPS with everything / DPS without that source.
A mult of 1.30 means removing it costs 23% of DPS. Layers are measured the same way with the whole
layer removed (all supports off, all ascendancy nodes removed, every item swapped for a blank of the
same base, every conditional config reset). Leave-one-out multipliers do not multiply back to the
total exactly (sources interact), so read them as "how much this piece carries".
"""

from __future__ import annotations

from . import enablers as enablers_mod
from .analysis import DPS_KEYS, audit, dps_of
from .engine import Engine
from .trade import active_slots, blank_item

INF = float("inf")


def _m(v):
    return INF if v == "inf" else float(v)


def decompose(eng: Engine, min_mult: float = 1.01, conditions: bool = True) -> dict:
    d = eng.call("decompose")
    base = d.get("base") or 0
    out = {"base_dps": base, "layers": {}, "sources": []}
    if base <= 0:
        return out
    for k, v in (d.get("layers") or {}).items():
        out["layers"][k] = _m(v)

    def add(layer, name, mult, **extra):
        if mult >= min_mult:
            out["sources"].append({"layer": layer, "name": name, "mult": mult, **extra})

    for s in d.get("supports") or []:
        add("support", s["name"], _m(s["mult"]))
    for s in d.get("ascendancy") or []:
        add("ascendancy", s["name"], _m(s["mult"]), node_type=s.get("type"))
    for s in d.get("tree") or []:
        add("jewel" if s.get("type") == "Socket" else ("keystone" if s.get("type") == "Keystone" else "notable"),
            s["name"], _m(s["mult"]))

    # gear: each item vs a blank of the same base (uniques lose their unique mods too)
    ir = eng.call("items")
    items = {i["slot"]: i for i in ir["items"]}
    gear_total = 1.0
    for slot in active_slots(ir):
        it = items.get(slot)
        if not it or not it.get("raw"):
            continue
        blank_raw = blank_item(it["raw"], it.get("base"))
        res = blank_raw and eng.call("try_items", slot=slot, candidates=[{"name": "blank", "raw": blank_raw}],
                                     fields=list(DPS_KEYS))
        c = res["candidates"][0] if res else {}
        if not c.get("ok"):
            out.setdefault("unmeasured", []).append({"slot": slot, "item": it["name"]})
            continue
        b, n = dps_of(res["base"]), dps_of(c["stats"])
        mult = INF if n <= 0 else b / n
        gear_total *= mult if mult != INF else 1.0
        add("gear", it["name"], mult, slot=slot, rarity=it.get("rarity"))
    out["layers"]["gear_product"] = gear_total

    if not conditions:
        out["sources"].sort(key=lambda s: -(s["mult"] if s["mult"] != INF else 1e9))
        return out
    # enablers: pieces whose weight hides in a config box (leave-one-out reads them ~x1.0)
    en = enablers_mod.measure(eng)
    out["enablers"] = en
    for r in enablers_mod.hidden_weight(en["rows"]):
        add("enabler", f"{r['name']} (with the conditions it keeps)", r["with"], alone=r["alone"],
            conditions=r["active"])
    backed = enablers_mod.backed_vars(en)
    # conditions (config): per-value contribution and the dewatered layer
    a = audit(eng)
    for i in a["items"]:
        if i.dps_delta_pct is not None and i.kind in ("ramp", "enemy_state", "self_condition", "skill_option", "custom_mod"):
            add("condition", i.label or i.var, 1.0 + i.dps_delta_pct / 100.0, var=i.var, kind=i.kind,
                backed_by=backed.get(i.var))
    dw = dps_of(a["dewatered"] or {})
    cfg = dps_of(a["base"])
    out["layers"]["conditions"] = (cfg / dw) if dw > 0 else INF

    out["sources"].sort(key=lambda s: -(s["mult"] if s["mult"] != INF else 1e9))
    return out
