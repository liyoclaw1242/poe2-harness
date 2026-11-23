"""Build-level analysis on top of the engine: summary, audit, ramp, stat elasticity."""

from __future__ import annotations

from dataclasses import dataclass, field

from .engine import Engine

# Main-skill DPS first. FullDPS is the sum of every group the author ticked (gem counts, culling,
# secondary skills) and is reported separately as "full_dps" composition.
DPS_KEYS = ("CombinedDPS", "FullDPS", "TotalDPS")


def dps_of(stats: dict) -> float:
    for k in DPS_KEYS:
        v = stats.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    return 0.0


def pct(new: float, old: float) -> float | None:
    if not old:
        return None
    return (new / old - 1.0) * 100.0


# ---------------------------------------------------------------------------
# Config classification ("去水")
# ---------------------------------------------------------------------------
PERMANENT_PREFIXES = ("quest",)
SCENARIO_VARS = {"enemyIsBoss", "resistancePenalty", "enemyLevel", "enemyArmour", "enemyEvasion"}
RAMP_HINTS = ("stage", "stack", "charge", "rage", "combo", "multiplier", "count", "seconds", "override",
              "glory", "infusion", "fortification", "tailwind", "killed", "recently")


@dataclass
class ConfigItem:
    var: str
    value: object
    label: str | None
    type: str | None
    section: str | None
    kind: str = "other"
    dps_delta_pct: float | None = None
    ehp_delta_pct: float | None = None
    backed_by: str | None = None   # an equipped piece / allocated node keeps this condition true


def classify(item: dict, section: str | None) -> str:
    var = item["var"]
    if var.startswith(PERMANENT_PREFIXES) or var == "customMods":
        return "permanent"
    if var in SCENARIO_VARS or section == "Enemy Stats":
        return "scenario"
    low = var.lower()
    if low.startswith(("conditionenemy", "enemy")) or section == "For Effective DPS":
        return "enemy_state"
    if item.get("type") == "count" and any(h in low for h in RAMP_HINTS):
        return "ramp"
    if low.startswith(("use", "condition", "buff", "have")) or section == "When In Combat":
        return "self_condition"
    return "skill_option"


def audit(eng: Engine, keep: set[str] | None = None, backed: dict[str, str] | None = None) -> dict:
    """Attribute DPS/EHP to every non-default config value and build a dewatered baseline.

    Each conditional value is reset to its default on its own (others untouched);
    the dewatered baseline resets all of them except `keep` and the vars in `backed`
    (var -> the enabler that keeps that condition true, see enablers.backed_vars).
    """
    backed = backed or {}
    keep = set(keep or set()) | set(backed)
    catalog = {o["var"]: o for o in eng.call("config", catalog=True)["options"]}
    state = eng.call("config")
    items: list[ConfigItem] = []
    for v in state["values"]:
        sec = catalog.get(v["var"], {}).get("section")
        items.append(ConfigItem(var=v["var"], value=v["value"], label=v.get("label"), type=v.get("type"),
                                section=sec, kind=classify(v, sec), backed_by=backed.get(v["var"])))

    # custom modifier lines are author claims (buffs, mantras, manual numbers): audit each line
    custom = [l for l in (state.get("customMods") or "").splitlines() if l.strip()]
    for n, line in enumerate(custom):
        items.append(ConfigItem(var=f"custom:{n}", value=line.strip(), label="custom mod", type="custom",
                                section="Custom", kind="custom_mod"))

    conditional = [i for i in items if i.kind in ("ramp", "enemy_state", "self_condition", "skill_option")]
    variants = [{"name": i.var, "values": {i.var: None}} for i in conditional]
    for n, line in enumerate(custom):
        rest = "\n".join(l for k, l in enumerate(custom) if k != n)
        variants.append({"name": f"custom:{n}", "values": {}, "customMods": rest})
    dewater_reset = {i.var: None for i in conditional if i.var not in keep}
    dw = {"name": "__dewatered__", "values": dewater_reset}
    if custom and "customMods" not in keep:
        dw["customMods"] = ""
    variants.append(dw)
    ramp_reset = {i.var: 0 for i in conditional if i.kind == "ramp"}
    # PoB ignores a "count" of 0 (it means "use the maximum"), so zero stacks behind a checkbox
    # (e.g. # of Power Charges behind "Do you use Power Charges?") means turning the checkbox off.
    for var in list(ramp_reset):
        gate = catalog.get(var, {}).get("ifOption")
        if gate:
            ramp_reset[gate] = False
    # charges the build uses at maximum (no count set) also start at zero
    for i in conditional:
        if i.var.startswith("use") and i.var.endswith("Charges") and i.value is True:
            ramp_reset[i.var] = False
    if ramp_reset:
        variants.append({"name": "__ramp_start__", "values": ramp_reset})
    variants.append({"name": "__mapping__", "values": {"enemyIsBoss": "None"}})
    variants.append({"name": "__uber__", "values": {"enemyIsBoss": "Uber"}})

    res = eng.call("variants", variants=variants, fields=list(DPS_KEYS) + ["TotalEHP"])
    base = res["base"]
    by_name = {v["name"]: v for v in res["variants"]}
    for i in conditional + [i for i in items if i.kind == "custom_mod"]:
        v = by_name.get(i.var)
        if v and v.get("ok"):
            i.dps_delta_pct = pct(dps_of(base), dps_of(v["stats"]))  # how much this value adds
            i.ehp_delta_pct = pct(base.get("TotalEHP") or 0, v["stats"].get("TotalEHP") or 0)

    def scen(name):
        v = by_name.get(name)
        return v["stats"] if v and v.get("ok") else None

    return {
        "base": base,
        "items": items,
        "dewatered": scen("__dewatered__"),
        "ramp_start": scen("__ramp_start__"),
        "mapping": scen("__mapping__"),
        "uber": scen("__uber__"),
        "kept": sorted(keep),
        "backed": dict(backed),
    }


# ---------------------------------------------------------------------------
# Ramp
# ---------------------------------------------------------------------------
def summarize_ramp(ramp: list[dict], base_dps: float) -> list[dict]:
    """Collapse curves; drop options with no effect; dedupe options feeding the same variable."""
    out = []
    by_feed: dict[tuple, dict] = {}
    for r in ramp:
        dps = [c["dps"] for c in r["curve"]]
        lo, hi = min(dps), max(dps)
        if hi <= 0 or hi - lo < 1e-6 * max(hi, 1):
            continue
        # value where the curve stops rising = the mechanic's cap
        cap_value = r["curve"][-1]["value"]
        for c in r["curve"]:
            if c["dps"] >= hi * 0.999:
                cap_value = c["value"]
                break
        monotonic = all(b >= a - 1e-9 for a, b in zip(dps, dps[1:])) or all(b <= a + 1e-9 for a, b in zip(dps, dps[1:]))
        entry = {
            "monotonic": monotonic,
            "var": r["var"], "label": r["label"], "type": r["type"], "current": r.get("current"),
            "feeds": r.get("feeds", []), "from_dps": lo, "to_dps": hi, "ratio": hi / lo if lo else None,
            "cap_value": cap_value,
            # charge sweeps stop at the build's own maximum, so their last point is a real cap
            "capped": cap_value != r["curve"][-1]["value"] or r["type"] == "check"
                      or (r["var"].startswith("override") and r["var"].endswith("Charges")),
            "curve": [(c["value"], round(c["dps"], 1)) for c in r["curve"]],
        }
        key = tuple(entry["feeds"]) or (entry["var"],)
        prev = by_feed.get(key)
        # Same variable written by several options: trust the capped one (real mechanics cap).
        if prev is None or (entry["capped"] and not prev["capped"]):
            by_feed[key] = entry
    entries = list(by_feed.values())
    # An uncapped option that only writes variables a capped option also writes is a
    # duplicate path into the same mechanic (e.g. Voltaxic Burst's option also sets
    # Multiplier:WhirlwindStages, but without the in-game cap) - drop it.
    capped_feeds = [set(e["feeds"]) for e in entries if e["capped"] and e["feeds"]]
    entries = [e for e in entries
               if e["capped"] or not e["feeds"] or not any(set(e["feeds"]) <= cf for cf in capped_feeds)]
    return sorted(entries, key=lambda e: -(e["ratio"] or 0))


# ---------------------------------------------------------------------------
# Stat elasticity ("what does this build scale with")
# ---------------------------------------------------------------------------
OFFENCE_PROBES = [
    ("+1 all skill levels", "+1 to Level of all Skills"),
    ("+20% increased damage", "20% increased Damage"),
    ("+10% skill speed", "10% increased Skill Speed"),
    ("+50% crit chance", "50% increased Critical Hit Chance"),
    ("+30% crit damage", "30% increased Critical Damage Bonus"),
    ("+10% dmg as extra fire", "Gain 10% of Damage as Extra Fire Damage"),
    ("+10% dmg as extra cold", "Gain 10% of Damage as Extra Cold Damage"),
    ("+10% dmg as extra lightning", "Gain 10% of Damage as Extra Lightning Damage"),
    ("+10% dmg as extra chaos", "Gain 10% of Damage as Extra Chaos Damage"),
    ("10% ele penetration", "Damage Penetrates 10% Elemental Resistances"),
    ("+20 flat phys to attacks", "Adds 10 to 20 Physical Damage to Attacks"),
    ("+20% duration", "20% increased Skill Effect Duration"),
    ("+20% area", "20% increased Area of Effect"),
    ("+20% projectile speed", "20% increased Projectile Speed"),
    ("+100 to each attribute", "+100 to all Attributes"),
    ("+20% minion damage", "Minions deal 20% increased Damage"),
]
DEFENCE_PROBES = [
    ("+100 life", "+100 to maximum Life"),
    ("+100 energy shield", "+100 to maximum Energy Shield"),
    ("+20% armour", "20% increased Armour"),
    ("+20% evasion", "20% increased Evasion Rating"),
    ("+10% all ele res", "+10% to all Elemental Resistances"),
    ("+10% chaos res", "+10% to Chaos Resistance"),
]


def elasticity(eng: Engine) -> dict:
    probes = OFFENCE_PROBES + DEFENCE_PROBES
    variants = [{"name": name, "appendMods": mod} for name, mod in probes]
    res = eng.call("variants", variants=variants, fields=list(DPS_KEYS) + ["TotalEHP", "Life", "EnergyShield"])
    base = res["base"]
    rows = []
    for v in res["variants"]:
        if not v.get("ok"):
            continue
        rows.append({
            "probe": v["name"],
            "dps_pct": pct(dps_of(v["stats"]), dps_of(base)) or 0.0,
            "ehp_pct": pct(v["stats"].get("TotalEHP") or 0, base.get("TotalEHP") or 0) or 0.0,
        })
    return {"base": base, "rows": rows}
