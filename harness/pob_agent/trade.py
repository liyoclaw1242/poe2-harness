"""Trade-side helpers: PoB-weighted trade2 queries, slot headroom, cost-efficiency (CP值) ranking.

Nothing here searches or buys on the trade site. Queries are turned into
trade2 URLs for the player to open; listings the player copies back are
evaluated locally with PoB.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import thresholds
from .analysis import DPS_KEYS, dps_of, pct
from .engine import Engine

EQUIP_SLOTS = ["Weapon 1", "Weapon 2", "Helmet", "Body Armour", "Gloves", "Boots", "Amulet",
               "Ring 1", "Ring 2", "Belt"]

SWAP = {"Weapon 1": "Weapon 1 Swap", "Weapon 2": "Weapon 2 Swap"}


def active_slots(items_result: dict) -> list[str]:
    """EQUIP_SLOTS with the weapon slots mapped to the weapon set the build actually uses."""
    if items_result.get("weaponSet") == 2:
        return [SWAP.get(s, s) for s in EQUIP_SLOTS]
    return list(EQUIP_SLOTS)


DEFAULT_WEIGHTS = [{"stat": "FullDPS", "weightMult": 1.0}, {"stat": "TotalEHP", "weightMult": 0.5}]


def weighted_query(eng: Engine, slot: str, league: str, weights=None, max_price=None,
                   price_currency=None, top: int = 12) -> dict:
    return eng.call("trade_query", slot=slot, league=league, statWeights=weights or DEFAULT_WEIGHTS,
                    maxPrice=max_price, maxPriceType=price_currency, topWeights=top)


def blank_item(raw: str) -> str:
    """Strip an item down to rarity + name + base so we can measure what its mods are worth."""
    lines = [l for l in raw.splitlines() if l.strip()]
    keep = []
    for l in lines:
        if l.startswith("Rarity:"):
            keep.append("Rarity: RARE")
        elif len(keep) == 1:
            keep.append("Blank")
        elif len(keep) == 2:
            keep.append(l)  # base type line
            break
    return "\n".join(keep)


def slot_headroom(eng: Engine, weights=None) -> list[dict]:
    """How much each equipped item contributes (vs. a blank item of the same base).

    A slot whose item adds little is usually the cheapest place to upgrade.
    """
    weights = weights or DEFAULT_WEIGHTS
    ir = eng.call("items")
    items = {i["slot"]: i for i in ir["items"]}
    rows = []
    for slot in active_slots(ir):
        it = items.get(slot)
        if not it:
            continue
        # uniques are measured the same way: a blank of the same base loses the unique's mods
        res = eng.call("try_items", slot=slot, candidates=[{"name": "blank", "raw": blank_item(it["raw"])}],
                       fields=list(DPS_KEYS) + ["TotalEHP"] + thresholds.FIELDS)
        cand = res["candidates"][0]
        if not cand.get("ok"):
            continue
        base, blank = res["base"], cand["stats"]
        dps_share = pct(dps_of(base), dps_of(blank))
        ehp_share = pct(base.get("TotalEHP") or 0, blank.get("TotalEHP") or 0)
        rows.append({"slot": slot, "item": it["name"], "rarity": it.get("rarity"),
                     "dps_from_item_pct": dps_share, "ehp_from_item_pct": ehp_share,
                     # a threshold the item holds: its % deltas are dominated by that, read them as such
                     "breaks": thresholds.breaks(base, blank)})
    return rows


def _score(base: dict, new: dict, weights) -> float:
    total = 0.0
    for w in weights:
        stat = w["stat"]
        if stat == "FullDPS":
            b, n = dps_of(base), dps_of(new)
        else:
            b, n = base.get(stat) or 0, new.get(stat) or 0
        if b:
            total += (n / b - 1.0) * w["weightMult"]
    return total * 100.0


def rank_candidates(eng: Engine, candidates: list[dict], weights=None) -> list[dict]:
    """candidates: [{slot, raw, price, currency?, name?}] with price in one common currency.

    Returns each candidate's PoB delta, a weighted score (% points) and score per unit of price.
    """
    weights = weights or DEFAULT_WEIGHTS
    out = []
    by_slot: dict[str, list[dict]] = {}
    for c in candidates:
        by_slot.setdefault(c["slot"], []).append(c)
    for slot, cands in by_slot.items():
        res = eng.call("try_items", slot=slot,
                       candidates=[{"name": c.get("name") or f"#{i}", "raw": c["raw"]} for i, c in enumerate(cands)],
                       fields=list(DPS_KEYS) + ["TotalEHP", "Life", "EnergyShield", "FireResist", "ColdResist",
                                                "LightningResist", "ChaosResist"])
        base = res["base"]
        for c, r in zip(cands, res["candidates"]):
            row = {"slot": slot, "name": r["name"], "price": c.get("price"), "currency": c.get("currency")}
            if not r.get("ok"):
                row["error"] = r.get("error")
            else:
                s = r["stats"]
                row.update({
                    "dps_pct": pct(dps_of(s), dps_of(base)),
                    "ehp_pct": pct(s.get("TotalEHP") or 0, base.get("TotalEHP") or 0),
                    "res_change": {k: (s.get(k) or 0) - (base.get(k) or 0)
                                   for k in ("FireResist", "ColdResist", "LightningResist", "ChaosResist")
                                   if (s.get(k) or 0) != (base.get(k) or 0)},
                    "score": _score(base, s, weights),
                })
                price = c.get("price")
                row["score_per_price"] = row["score"] / price if price else None
            out.append(row)
    out.sort(key=lambda r: -(r.get("score_per_price") or r.get("score") or -1e9))
    return out


def load_candidates(path: str) -> list[dict]:
    """JSON list, or a text file of items separated by lines of '---' with 'price: N' / 'slot: X' headers."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix == ".json":
        return json.loads(text)
    out = []
    for chunk in text.split("\n---"):
        meta, body = {}, []
        for line in chunk.strip().splitlines():
            low = line.lower()
            if low.startswith(("price:", "slot:", "currency:", "name:")) and not body:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
            else:
                body.append(line)
        if body:
            out.append({"slot": meta.get("slot"), "raw": "\n".join(body),
                        "price": float(meta["price"]) if "price" in meta else None,
                        "currency": meta.get("currency"), "name": meta.get("name")})
    return out
