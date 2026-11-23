"""Enablers: pieces whose value is that they keep a config condition true.

PoB models many conditions as config boxes the author ticks ("Are you always on Low Life?",
"Twister gained Fire Element", "Combo: 20"). The piece that makes the condition permanent in game
(Eternal Life, The Taming, Martial Master) often has no parsed mod that sets it, so leave-one-out
reads it ~x1.0: the box stays ticked when the piece is removed.

Each entry names the piece and the config values that become unreachable without it (`off`;
None = reset to default). We report three multipliers (DPS with everything / DPS after removal):

  alone  remove the piece only (what plain decompose shows)
  cond   turn off only the conditions it guarantees
  with   both: the piece's real weight in this build

Entries are hand-written from the piece's text, so each carries the text it relies on and a note on
what else the condition needs. `detect` adds pieces whose parsed mods set a Condition flag that a
config box also sets (PoB already applies those, so they mostly confirm the box is redundant).

Keep entries to cases where removing the piece really makes the condition unreachable for the
build; when that depends on the build (another source could provide it), say so in `note`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .engine import Engine
from .trade import active_slots, blank_item

INF = float("inf")


@dataclass(frozen=True)
class Enabler:
    id: str
    kind: str                    # "node" (passive / ascendancy) or "item" (unique name)
    name: str
    off: dict                    # config var -> value without the piece (None = default)
    text: str                    # the piece's text this entry relies on
    note: str = ""
    credit_slot: str | None = None   # for transforms: the slot whose item already holds the effect
    confidence: str = "medium"   # high: text states it directly; medium: needs a usual setup


TABLE: list[Enabler] = [
    Enabler(
        id="eternal_life", kind="node", name="Eternal Life",
        off={"conditionLowLife": False},
        text="Your Life cannot change while you have Energy Shield",
        note="Keeps Life where it is while ES is up. Low Life still needs a way down (life reservation/"
             "costs); this entry assumes the build uses Eternal Life to hold it.",
        confidence="medium",
    ),
    Enabler(
        id="the_taming", kind="item", name="The Taming",
        off={"twisterCold": False, "twisterFire": False, "twisterLightning": False},
        text="Wind Skills ... count as being boosted by Ignited, Shocked, and Chilled Ground",
        note="Without it Twister needs real elemental ground or elemental Whirlwinds for each element.",
        confidence="high",
    ),
    Enabler(
        id="martial_master", kind="node", name="Martial Master",
        off={"multiplierCombo": None},
        text="Skills can build and retain Combo regardless of Weapon Set; Gain Combo from all Attack Hits",
        note="Only an enabler when the main attacks would not build Combo otherwise (non-Strike or "
             "non-Quarterstaff attacks, weapon swapping).",
        confidence="medium",
    ),
    Enabler(
        id="way_of_the_stonefist", kind="node", name="Way of the Stonefist",
        off={},
        text="Gloves you equip have their Base Type transformed to Fists of Stone ... Explicit Modifiers "
             "are transformed into more powerful related Modifiers",
        note="Imported gloves already carry the transformed mods, so the node reads x1.0 and the credit "
             "sits in the Gloves slot. 'with' removes the node and blanks the gloves (upper bound).",
        credit_slot="Gloves",
        confidence="high",
    ),
]


def _m(v):
    return INF if v == "inf" else float(v)


def measure(eng: Engine, table: list[Enabler] | None = None, detect: bool = True) -> dict:
    """Measure every table entry present in the loaded build."""
    table = TABLE if table is None else table
    ir = eng.call("items")
    items = {i["slot"]: i for i in ir["items"]}
    slots = active_slots(ir)
    by_name = {}
    for s in slots:
        it = items.get(s)
        if it:
            # PoB names items "<unique name>, <base type>"
            by_name.setdefault(it["name"].split(",")[0].strip(), s)

    entries, meta = [], {}
    for e in table:
        sources, extra = [], []
        if e.kind == "node":
            sources.append({"kind": "node", "name": e.name})
        else:
            slot = by_name.get(e.name)
            if not slot:
                continue
            sources.append({"kind": "slot", "slot": slot, "raw": blank_item(items[slot]["raw"])})
        if e.credit_slot:
            cs = next((s for s in slots if s.startswith(e.credit_slot) and s in items), None)
            if cs:
                extra.append({"kind": "slot", "slot": cs, "raw": blank_item(items[cs]["raw"])})
        entries.append({"id": e.id, "sources": sources, "off": e.off, "extra": extra})
        meta[e.id] = e

    res = eng.call("enablers", entries=entries, detect=detect)
    rows = []
    for r in res["rows"]:
        if not r.get("present"):
            continue
        e = meta[r["id"]]
        alone, cond, with_ = _m(r["alone"]), _m(r["cond"]), _m(r["with"])
        relies = bool(r["active"]) or bool(e.credit_slot)
        rows.append({
            "id": e.id, "name": e.name, "kind": e.kind, "alone": alone, "cond": cond, "with": with_,
            "active": r["active"], "relies": relies, "guards": sorted(e.off), "confidence": e.confidence,
            "text": e.text, "note": e.note,
        })
    rows.sort(key=lambda x: -(x["with"] if x["with"] != INF else 1e9))
    detected = []
    seen = set()
    for d in res.get("detected") or []:
        key = (d["name"], d["condition"])
        if key in seen:
            continue
        seen.add(key)
        detected.append(d)
    return {"base_dps": res["base"], "rows": rows, "detected": detected}


def hidden_weight(rows: list[dict], min_gap: float = 1.05) -> list[dict]:
    """Rows where plain leave-one-out understates the piece by at least `min_gap`."""
    out = []
    for r in rows:
        if not r["relies"]:
            continue
        a, w = r["alone"], r["with"]
        if w == INF or (a != INF and w / a >= min_gap):
            out.append(r)
    return out


def backed_vars(result: dict) -> dict[str, str]:
    """Config vars kept true by a piece the build actually has: var -> piece name.

    Table rows count when the build ticks the condition; detected pieces count only when their
    Condition flag is unconditional (a tagged flag, e.g. "while on Low Life", may not hold).
    """
    out: dict[str, str] = {}
    for r in result.get("rows") or []:
        for var in r["active"]:
            out.setdefault(var, r["name"])
    for d in result.get("detected") or []:
        if d.get("conditional"):
            continue
        for var in d.get("vars") or []:
            out.setdefault(var, d["name"].split(",")[0].strip())
    return out
