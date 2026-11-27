"""Thresholds: stats where one item flips the build from fine to broken.

Percent deltas mislead around a threshold. Example: with 91 unreserved life and Mind over Matter at
100%, every hit is taken from mana; a ring that supplies part of that 100% reads as "+1200% EHP"
because without it the 91 life is exposed. The honest statement is "this ring holds MoM at 100%".

Thresholds checked:
  mom        Mind over Matter (damage taken from mana before life) reaching 100%
  resist     elemental/chaos resistance at its cap
  spirit     unreserved Spirit >= 0 (below 0 a reserved skill/buff cannot actually be kept up;
             PoB still counts it)
  attribute  Str/Dex/Int meeting the highest requirement (below it gems/items stop working in game)
"""

from __future__ import annotations

from .engine import Engine

ELEMS = ("Fire", "Cold", "Lightning", "Chaos")
# cliffs: crossing them changes the build discontinuously (exposed life, a buff that cannot run, a gem
# that cannot be used). Resist caps are a gradual loss and are reported without the cliff warning.
CLIFFS = {"mom", "spirit", "attribute"}
ATTRS = ("Str", "Dex", "Int")
FIELDS = (["sharedMindOverMatter", "LifeUnreserved", "ManaUnreserved", "SpiritUnreserved"]
          + [f"{e}Resist" for e in ELEMS] + [f"Missing{e}Resist" for e in ELEMS]
          + list(ATTRS) + [f"Req{a}" for a in ATTRS])


def _v(d: dict, k: str) -> float:
    v = d.get(k)
    return float(v) if isinstance(v, (int, float)) else 0.0


def breaks(base: dict, new: dict) -> list[dict]:
    """Thresholds that hold with `base` and fail with `new` (e.g. after blanking one item)."""
    out = []
    bm, nm = _v(base, "sharedMindOverMatter"), _v(new, "sharedMindOverMatter")
    if bm >= 100 and nm < 100:
        out.append({"kind": "mom", "text": f"Mind over Matter {bm:.0f}% → {nm:.0f}% "
                                           f"(exposes {max(_v(new, 'LifeUnreserved'), 0):.0f} unreserved life)"})
    for e in ELEMS:
        if _v(base, f"Missing{e}Resist") <= 0 and _v(new, f"Missing{e}Resist") > 0:
            out.append({"kind": "resist", "text": f"{e} resistance uncapped: {_v(base, e + 'Resist'):.0f}% → "
                                                  f"{_v(new, e + 'Resist'):.0f}%"})
    bs, ns = _v(base, "SpiritUnreserved"), _v(new, "SpiritUnreserved")
    if bs >= 0 and ns < 0:
        out.append({"kind": "spirit", "text": f"Spirit goes negative ({bs:.0f} → {ns:.0f}): a reserved skill or "
                                              "buff could not be kept up in game"})
    for a in ATTRS:
        if _v(base, a) >= _v(base, "Req" + a) and _v(new, a) < _v(new, "Req" + a):
            out.append({"kind": "attribute", "text": f"{a} below requirement ({_v(new, a):.0f} < "
                                                     f"{_v(new, 'Req' + a):.0f}): some gem or item stops working"})
    for b in out:
        b["cliff"] = b["kind"] in CLIFFS
    return out


def margins(eng: Engine, resist_slack: float = 5, attr_slack: float = 10, spirit_slack: float = 10) -> dict:
    """Current build: how close each threshold is to breaking. `edges` lists the tight or broken ones."""
    t = eng.call("thresholds")
    edges = []
    if t["momCapped"] >= 100:
        extra = t["mom"] - 100
        edges.append({"kind": "mom", "broken": False,
                      "text": f"Mind over Matter at 100% ({t['mom']:.0f}% before the cap, {extra:.0f}% slack) with "
                              f"{t['lifeUnreserved']:.0f} unreserved life: losing any MoM source exposes that life"})
    for e, r in t["resists"].items():
        if r["missing"] > 0:
            edges.append({"kind": "resist", "broken": False, "text": f"{e} resistance {r['value']:.0f}% is "
                                                                   f"{r['missing']:.0f}% below its cap"})
        elif r["overCap"] < resist_slack:
            edges.append({"kind": "resist", "broken": False, "text": f"{e} resistance capped with only "
                                                                    f"{r['overCap']:.0f}% over the cap"})
    s = t["spiritUnreserved"]
    if s < 0:
        edges.append({"kind": "spirit", "broken": True,
                      "text": f"Spirit is {s:.0f} unreserved: PoB counts a reservation this build cannot pay"})
    elif s < spirit_slack:
        edges.append({"kind": "spirit", "broken": False, "text": f"only {s:.0f} Spirit unreserved"})
    for a, r in t["attributes"].items():
        # PoB omits "req" when nothing equipped or socketed has a requirement for this attribute
        if (r.get("req") or 0) <= 0:
            continue
        slack = r["value"] - r["req"]
        if slack < 0:
            edges.append({"kind": "attribute", "broken": True,
                          "text": f"{a} {r['value']:.0f} is below the requirement {r['req']:.0f}"})
        elif slack < attr_slack:
            edges.append({"kind": "attribute", "broken": False,
                          "text": f"{a} only {slack:.0f} above the requirement {r['req']:.0f}"})
    return {"raw": t, "edges": edges}
