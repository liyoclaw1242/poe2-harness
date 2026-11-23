"""pob-agent CLI. Compact markdown output by default (agent-friendly); --json for raw data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import analysis, decompose, enablers, scan, sources, trade
from .engine import Engine, EngineError

ENV_STAMP = "PoE2 | PoB-PoE2 {ver} | values are PoB calculations, not in-game measurements"


def fmt(v, digits=0):
    if v is None:
        return "-"
    if isinstance(v, str):
        return v
    if abs(v) >= 1e6:
        return f"{v / 1e6:.2f}M"
    if abs(v) >= 1e4:
        return f"{v / 1e3:.1f}k"
    return f"{v:.{digits}f}"


def fpct(v):
    return "-" if v is None else f"{v:+.1f}%"


def emit(args, data, render):
    if args.json:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=1, default=lambda o: o.__dict__)
        sys.stdout.write("\n")
    else:
        render(data)


def load(eng: Engine, ref: str) -> dict:
    info = eng.call("load", **sources.resolve(ref))
    try:
        info["full_dps"] = eng.call("full_dps")
    except EngineError:
        info["full_dps"] = None
    return info


def parse_weights(s: str | None):
    if not s:
        return None
    out = []
    for part in s.split(","):
        stat, _, w = part.partition(":")
        out.append({"stat": stat.strip(), "weightMult": float(w or 1)})
    return out


# ---------------------------------------------------------------------------
# renderers
# ---------------------------------------------------------------------------
def render_summary(info: dict, ver: str):
    s = info["stats"]
    ms = info.get("mainSkill") or {}
    print(f"[{ENV_STAMP.format(ver=ver)}]")
    print(f"## {info.get('ascendancy') or info.get('className')} lv{info.get('level')} — {ms.get('name')}")
    print(f"supports: {', '.join(ms.get('supports') or []) or '-'}")
    raw_ids = [x for x in (ms.get("supports") or []) if x.startswith("Support") and x.endswith("Player")]
    if raw_ids:
        print(f"⚠ PoB shows {', '.join(raw_ids)} by internal id: a meta/granted effect it may not fully model "
              f"(e.g. Hollow Form images, totem/trigger wrappers). Treat DPS as a lower bound.")
    print(f"DPS {fmt(analysis.dps_of(s))} (main skill; hit {fmt(s.get('TotalDPS'))}) | "
          f"speed {fmt(s.get('Speed'), 2)}/s | crit {fmt(s.get('CritChance'), 1)}% x{fmt(s.get('CritMultiplier'), 2)}")
    fd = info.get("full_dps") or {}
    if fd.get("full") and fd["full"] > 1.05 * analysis.dps_of(s):
        parts = ", ".join(f"{r['name']}{' x' + str(r['count']) if (r.get('count') or 1) > 1 else ''} {fmt(r['dps'])}"
                          for r in sorted(fd.get("skills") or [], key=lambda r: -(r.get("dps") or 0))[:6])
        print(f"Full DPS (author-ticked groups summed) {fmt(fd['full'])}: {parts}")
    for n in info.get("normalized") or []:
        if n.get("skipped"):
            print(f"⚠ {n['skill']} granted by {n['itemSource'].split(':', 2)[-1]} also appears in {n['copies']} plain "
                  f"gem groups; PoB charges Spirit for each copy. Spirit below may be understated.")
        else:
            print(f"note: merged duplicate of item-granted {n['skill']} ({n['itemSource'].split(':', 2)[-1]}) "
                  f"so it is not charged Spirit twice")
    print(f"Life {fmt(s.get('Life'))} | ES {fmt(s.get('EnergyShield'))} | Armour {fmt(s.get('Armour'))} | "
          f"Evasion {fmt(s.get('Evasion'))} | EHP {fmt(s.get('TotalEHP'))} | Spirit {fmt(s.get('SpiritUnreserved'))}/{fmt(s.get('Spirit'))}")
    print("Max hit: " + " / ".join(f"{k[:4]} {fmt(s.get(k + 'MaximumHitTaken'))}"
                                   for k in ("Physical", "Fire", "Cold", "Lightning", "Chaos")))
    print(f"Res: fire {fmt(s.get('FireResist'))} cold {fmt(s.get('ColdResist'))} "
          f"light {fmt(s.get('LightningResist'))} chaos {fmt(s.get('ChaosResist'))}")


def render_audit(a: dict):
    base = a["base"]
    print("## Config audit (去水)")
    print("| kind | config | value | DPS from it | EHP from it |\n|---|---|---|---|---|")
    for i in sorted(a["items"], key=lambda i: (i.kind == "permanent", -(abs(i.dps_delta_pct or 0)))):
        if i.kind == "permanent":
            continue
        label = (i.label or i.var).strip()
        if i.backed_by:
            label += f" (kept true by {i.backed_by})"
        print(f"| {i.kind} | {label} | {i.value} | {fpct(i.dps_delta_pct)} | {fpct(i.ehp_delta_pct)} |")
    b = analysis.dps_of(base)
    rows = [("as configured", base), ("dewatered (unbacked conditions off)" if a.get("backed") else "dewatered (all conditions off)", a["dewatered"]),
            ("ramp start (stacks = 0)", a["ramp_start"]),
            ("vs normal monsters (mapping)", a["mapping"]), ("vs uber pinnacle", a["uber"])]
    print("\n(PoB default enemy = Guardian/Pinnacle boss)")
    print("| scenario | DPS | vs configured | EHP |\n|---|---|---|---|")
    for name, st in rows:
        if st:
            print(f"| {name} | {fmt(analysis.dps_of(st))} | {fpct(analysis.pct(analysis.dps_of(st), b))} | {fmt(st.get('TotalEHP'))} |")
    if a["kept"]:
        print(f"kept on: {', '.join(a['kept'])}")


def render_enablers(e: dict):
    print("## Enablers (pieces that keep a config condition true)")
    print("alone = remove the piece only (what decompose shows); cond = turn off only the conditions it "
          "guarantees; with = both.")
    if not e["rows"]:
        print("no enabler from the table in this build")
    else:
        print("| piece | alone | cond | with | conditions | confidence |\n|---|---|---|---|---|---|")
        for r in e["rows"]:
            mx = lambda v: "∞" if v == decompose.INF else f"x{v:.2f}"
            conds = ", ".join(r["active"]) or ("credit in gloves" if r["id"] == "way_of_the_stonefist" else "not ticked")
            cond = mx(r["cond"]) if r.get("guards") else "—"
            print(f"| {r['name']} | {mx(r['alone'])} | {cond} | {mx(r['with'])} | {conds} | {r['confidence']} |")
        for r in e["rows"]:
            if r["relies"] and r["note"]:
                print(f"- {r['name']}: {r['note']}")
            elif r.get("guards") and not r["active"]:
                print(f"- {r['name']} is in the build but {', '.join(r['guards'])} is not ticked: "
                      "PoB may understate this build (the author left the condition off).")
    if e["detected"]:
        print("\nPieces whose parsed mods already set a condition PoB also offers as a config box "
              "(the box is redundant for these):")
        for d in e["detected"]:
            tag = " (conditional)" if d.get("conditional") else ""
            print(f"- {d['name']}: {d['condition']} → {', '.join(d['vars'])}{tag}")


def render_ramp(r: dict):
    print(f"## Ramp for {r['skill']} (PoB stack/stage/condition options this skill reads)")
    if not r["summary"]:
        print("no stack-dependent damage found")
    for e in r["summary"]:
        cap = f"caps at {e['cap_value']}" if e["capped"] else "no cap in PoB (check in-game)"
        if not e.get("monotonic", True):
            cap = "cyclic/non-monotonic (timer-like mechanic)"
        print(f"- {e['label'].strip()} [{e['var']}={e['current']}]: {fmt(e['from_dps'])} -> {fmt(e['to_dps'])} "
              f"(x{e['ratio']:.2f}, {cap}) curve {e['curve']}")


def render_scales(r: dict):
    print("## What this build scales with (one standard unit each)")
    print("| probe | DPS | EHP |\n|---|---|---|")
    for row in sorted(r["rows"], key=lambda x: -max(x["dps_pct"], x["ehp_pct"])):
        if abs(row["dps_pct"]) < 0.05 and abs(row["ehp_pct"]) < 0.05:
            continue
        print(f"| {row['probe']} | {fpct(row['dps_pct'])} | {fpct(row['ehp_pct'])} |")


def render_headroom(rows):
    print("## Slot headroom (share of stats coming from each item's mods)")
    print("| slot | item | DPS from item | EHP from item |\n|---|---|---|---|")
    for r in sorted(rows, key=lambda r: (r.get("dps_from_item_pct") or 0) + (r.get("ehp_from_item_pct") or 0)):
        if r.get("note"):
            print(f"| {r['slot']} | {r['item']} | {r['note']} | |")
        else:
            print(f"| {r['slot']} | {r['item']} | {fpct(r['dps_from_item_pct'])} | {fpct(r['ehp_from_item_pct'])} |")


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_summary(args):
    with Engine(args.verbose) as eng:
        info = load(eng, args.build)
        emit(args, info, lambda d: render_summary(d, eng.version))


def cmd_audit(args):
    with Engine(args.verbose) as eng:
        load(eng, args.build)
        en = enablers.measure(eng)
        a = analysis.audit(eng, keep=set(args.keep or []), backed=enablers.backed_vars(en))
        emit(args, a, render_audit)


def cmd_enablers(args):
    with Engine(args.verbose) as eng:
        load(eng, args.build)
        emit(args, enablers.measure(eng), render_enablers)


def cmd_ramp(args):
    with Engine(args.verbose) as eng:
        load(eng, args.build)
        r = eng.call("ramp")
        r["summary"] = analysis.summarize_ramp(r["ramp"], r["base"])
        emit(args, r, render_ramp)


def cmd_scales(args):
    with Engine(args.verbose) as eng:
        load(eng, args.build)
        emit(args, analysis.elasticity(eng), render_scales)


def cmd_headroom(args):
    with Engine(args.verbose) as eng:
        load(eng, args.build)
        emit(args, trade.slot_headroom(eng, parse_weights(args.weights)), render_headroom)


def cmd_diagnose(args):
    """One-shot report: summary + audit + ramp + scaling + slot headroom."""
    with Engine(args.verbose) as eng:
        info = load(eng, args.build)
        en = enablers.measure(eng)
        a = analysis.audit(eng, keep=set(args.keep or []), backed=enablers.backed_vars(en))
        r = eng.call("ramp")
        r["summary"] = analysis.summarize_ramp(r["ramp"], r["base"])
        el = analysis.elasticity(eng)
        hr = trade.slot_headroom(eng)
        data = {"summary": info, "enablers": en, "audit": a, "ramp": r, "scales": el, "headroom": hr}

        def render(_):
            render_summary(info, eng.version)
            print()
            render_enablers(en)
            print()
            render_audit(a)
            print()
            render_ramp(r)
            print()
            render_scales(el)
            print()
            render_headroom(hr)
        emit(args, data, render)


def cmd_trade_query(args):
    with Engine(args.verbose) as eng:
        load(eng, args.build)
        slots = args.slot or trade.active_slots(eng.call("items"))
        out = []
        for slot in slots:
            try:
                q = trade.weighted_query(eng, slot, args.league, parse_weights(args.weights),
                                         args.max_price, args.currency, top=args.top)
                out.append({"slot": slot, **q})
            except EngineError as exc:
                out.append({"slot": slot, "error": str(exc).splitlines()[0]})

        def render(rows):
            for q in rows:
                print(f"## {q['slot']}")
                if q.get("error"):
                    print(f"error: {q['error']}")
                    continue
                for w in q["weights"]:
                    print(f"- {w['weight']:.3f}/pt  {w['text']}")
                print(f"open: {q['url']}\n")
        emit(args, out, render)


def cmd_upgrade(args):
    with Engine(args.verbose) as eng:
        load(eng, args.build)
        cands = trade.load_candidates(args.candidates)
        if args.slot:
            for c in cands:
                c["slot"] = c.get("slot") or args.slot
        rows = trade.rank_candidates(eng, cands, parse_weights(args.weights))

        def render(rs):
            print("## Candidates by cost efficiency (score = weighted % gain; per price unit)")
            print("| slot | item | price | DPS | EHP | res change | score | score/price |\n|---|---|---|---|---|---|---|---|")
            for r in rs:
                if r.get("error"):
                    print(f"| {r['slot']} | {r['name']} | {r.get('price')} | error | | | | |")
                    continue
                res = ", ".join(f"{k[:-6]} {v:+.0f}" for k, v in r["res_change"].items()) or "-"
                print(f"| {r['slot']} | {r['name']} | {fmt(r.get('price'), 1)} {r.get('currency') or ''} | "
                      f"{fpct(r['dps_pct'])} | {fpct(r['ehp_pct'])} | {res} | {r['score']:.1f} | "
                      f"{fmt(r.get('score_per_price'), 2)} |")
        emit(args, rows, render)


def cmd_scan(args):
    with Engine(args.verbose) as eng:
        results = scan.run_scan(eng, tier=args.tier, skills=args.skills, allow_lineage=args.lineage,
                                progress=args.verbose)
    if args.out:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False))
    rows = scan.score(results)

    def render(rs):
        print(f"## PoB-only skill scan (tier={args.tier}, {len(rs)} skills with damage on template)")
        print("| # | skill | family | supported DPS | ramp | potential | z(fam) | flags | supports |\n|---|---|---|---|---|---|---|---|---|")
        for r in rs[: args.top]:
            print(f"| {r['rank']} | {r['skill']} | {r['family']} | {fmt(r['supported_dps'])} | x{r['ramp_factor']:.2f} | "
                  f"{fmt(r['potential_dps'])} | {r['z_in_family']:+.2f} | {' '.join(r['flags'])} | {', '.join(r['supports'])} |")
    emit(args, rows, render)


def cmd_export_build(args):
    """Write the in-game Build Planner file (.build) for a build."""
    with Engine(args.verbose) as eng:
        load(eng, args.build)
        res = eng.call("export_build", name=args.name, description=args.description)
    Path(args.out).write_text(res["build"], encoding="utf-8")
    print(f"wrote {args.out} (import in-game: Build Planner)")


def cmd_lift(args):
    """Skill x ascendancy: how much each ascendancy multiplies a skill (8 points spent greedily by PoB)."""
    with Engine(args.verbose) as eng:
        params = dict(scan.TIERS[args.tier])
        res = eng.call("ascendancy_lift", skills=args.skills, points=args.points, **params)["results"]

    def render(rs):
        for r in rs:
            print(f"## {r['skill']} (template DPS {fmt(r.get('baseDPS'))}; supports {', '.join(s['name'] for s in r.get('supports') or [])})")
            print("| ascendancy | lift | DPS after | nodes |\n|---|---|---|---|")
            for a in r.get("ascendancies", [])[: args.top]:
                if a.get("error"):
                    continue
                print(f"| {a['ascendancy']} | x{a['lift']:.2f} | {fmt(a['after'])} | {', '.join(a['nodes'])} |")
    emit(args, res, render)


def cmd_profile_batch(args):
    """Load many builds; record ascendancy, main skill, DPS/EHP, dewatered ratio, ramp."""
    files = sorted(Path(args.dir).glob("*.code")) + sorted(Path(args.dir).glob("*.xml"))
    meta = {}
    mf = Path(args.dir) / "manifest.json"
    if mf.exists():
        meta = {m["file"]: m for m in json.loads(mf.read_text())}
    out = []
    with Engine(args.verbose) as eng:
        for f in files:
            row = {"file": f.name, "title": meta.get(f.name, {}).get("title")}
            try:
                info = load(eng, str(f))
                ms = info.get("mainSkill") or {}
                row.update({"ascendancy": info.get("ascendancy"), "class": info.get("className"),
                            "level": info.get("level"), "main_skill": ms.get("name"),
                            "supports": ms.get("supports"), "dps": analysis.dps_of(info["stats"]),
                            "ehp": info["stats"].get("TotalEHP")})
                if args.deep:
                    a = analysis.audit(eng)
                    row["dewatered_dps"] = analysis.dps_of(a["dewatered"] or {})
                    row["conditional"] = [{"var": i.var, "kind": i.kind, "dps_pct": i.dps_delta_pct}
                                          for i in a["items"] if i.kind != "permanent"]
                    r = eng.call("ramp")
                    row["ramp"] = [{k: e[k] for k in ("var", "label", "ratio", "capped", "cap_value", "current")}
                                   for e in analysis.summarize_ramp(r["ramp"], r["base"])]
            except Exception as exc:  # keep going on bad pastes
                row["error"] = str(exc).splitlines()[0][:200]
            out.append(row)
            if args.verbose:
                print(f"{f.name}: {row.get('ascendancy')} {row.get('main_skill')} {row.get('error') or ''}", file=sys.stderr)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    ok = [r for r in out if not r.get("error")]
    print(f"profiled {len(ok)}/{len(out)} builds -> {args.out}")


def cmd_backtest(args):
    results = json.loads(Path(args.scan).read_text())
    rows = scan.score(results)
    profiles = json.loads(Path(args.profiles).read_text())
    observed = [p["main_skill"] for p in profiles if p.get("main_skill")]
    bt = scan.backtest(rows, observed, top_n=args.top)
    emit(args, bt, lambda d: print(json.dumps(d, ensure_ascii=False, indent=1)))


def cmd_decompose(args):
    """Where the main skill's DPS comes from: each support, ascendancy node, notable, item, condition."""
    with Engine(args.verbose) as eng:
        info = load(eng, args.build)
        d = decompose.decompose(eng)
        pairs = None
        if args.synergy:
            items = {i["slot"]: i for i in eng.call("items")["items"]}
            cands = []
            for s in d["sources"]:
                if s["mult"] == decompose.INF or s["mult"] < 1.05:
                    continue
                if s["layer"] in ("notable", "keystone", "ascendancy"):
                    cands.append({"kind": "node", "name": s["name"]})
                elif s["layer"] == "gear" and s.get("slot") in items:
                    cands.append({"kind": "slot", "name": s["name"], "slot": s["slot"],
                                  "raw": trade.blank_item(items[s["slot"]]["raw"])})
                elif s["layer"] == "support":
                    cands.append({"kind": "support", "name": s["name"]})
                if len(cands) >= 10:
                    break
            pairs = [p for p in eng.call("synergy", sources=cands)["pairs"]
                     if p["synergy"] == "inf" or p["synergy"] >= 1.1]
            pairs.sort(key=lambda p: -(1e9 if p["synergy"] == "inf" else p["synergy"]))
        d["synergy"] = pairs

    def render(d):
        ms = (info.get("mainSkill") or {}).get("name")
        print(f"[{ENV_STAMP.format(ver=eng.version)}]")
        print(f"## {ms} — {info.get('ascendancy') or info.get('className')} — DPS {fmt(d['base_dps'])}")
        print("Leave-one-out: x2.00 = removing it halves DPS.\n")
        print("layers: " + ", ".join(f"{k} {'∞' if v == decompose.INF else f'x{v:.2f}'}" for k, v in d["layers"].items()))
        print("\n| layer | source | mult |\n|---|---|---|")
        for s in d["sources"][: args.top]:
            m = "∞ (required)" if s["mult"] == decompose.INF else f"x{s['mult']:.2f}"
            name = s["name"]
            if s.get("backed_by"):
                name += f" — kept true by {s['backed_by']}"
            if s["layer"] == "enabler" and s.get("alone") is not None:
                a = "∞" if s["alone"] == decompose.INF else f"x{s['alone']:.2f}"
                name += f" (alone {a})"
            print(f"| {s['layer']} | {name} | {m} |")
        if d.get("synergy"):
            print("\n### Engines (pairs worth more together than apart)\n| A | B | together | synergy |\n|---|---|---|---|")
            for p in d["synergy"][:10]:
                j = p["joint"] if p["joint"] == "inf" else f"x{p['joint']:.2f}"
                sy = p["synergy"] if p["synergy"] == "inf" else f"x{p['synergy']:.2f}"
                print(f"| {p['a']} | {p['b']} | {j} | {sy} |")
    emit(args, d, render)


def cmd_build_up(args):
    """Construct one skill greedily with PoB: supports -> ascendancy -> passive tree, showing each multiplier."""
    with Engine(args.verbose) as eng:
        params = dict(scan.TIERS[args.tier])
        r = eng.call("build_up", skill=args.skill, ascendancy=args.ascendancy, treePoints=args.tree_points,
                     allowLineage=not args.no_lineage, **params)

    def render(r):
        print(f"## {r['skill']} / {r.get('ascendancy') or 'no ascendancy'} — template {args.tier}")
        print(f"bare gem {fmt(r['bareDPS'])} -> final {fmt(r['finalDPS'])} "
              f"(x{(r['finalDPS'] / r['bareDPS']) if r['bareDPS'] else 0:.1f})")
        print("layers: " + ", ".join(f"{k} x{v:.2f}" for k, v in (r.get("layers") or {}).items() if v))
        print("\n| step | layer | pick | mult |\n|---|---|---|---|")
        for i, s in enumerate(r["steps"], 1):
            cost = f" ({s['cost']} pts)" if s.get("cost") else ""
            print(f"| {i} | {s['layer']} | {s['name']}{cost} | x{(s.get('mult') or 0):.2f} |")
        if r.get("uniques"):
            print("\nuniques that raise this skill (vs empty slot on the template):")
            for sl in r["uniques"]:
                if sl["uniques"]:
                    print(f"- {sl['slot']}: " + ", ".join(f"{u['name']} x{u['mult']:.2f}" for u in sl["uniques"]))
        caps = [x for x in analysis.summarize_ramp(r.get("ramp") or [], r.get("finalDPS") or 0) if x.get("capped")] \
            if r.get("ramp") else []
        if caps:
            print("\nramp (not in the numbers above): " + ", ".join(f"{c['label'] or c['var']} x{c['ratio']:.2f}" for c in caps))
        print("\nnote: greedy, one pick at a time on a template character — it cannot find cross-layer engines "
              "(keystone + unique + node) whose pieces are weak alone; compare with `decompose --synergy` on real builds.")
    emit(args, r, render)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pob-agent", description=__doc__)
    ap.add_argument("--json", action="store_true", help="raw JSON output")
    ap.add_argument("--verbose", action="store_true", help="show PoB engine output")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def build_cmd(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("build", help="file (.code/.xml), share code, pobb.in or poe.ninja/poe2/pob link")
        p.set_defaults(fn=fn)
        return p

    build_cmd("summary", cmd_summary, "key stats of a build")
    p = build_cmd("diagnose", cmd_diagnose, "one-shot: summary + audit + ramp + scaling + slot headroom")
    p.add_argument("--keep", nargs="*", help="config vars to keep on when dewatering")
    p = build_cmd("audit", cmd_audit, "attribute DPS/EHP to config conditions; dewatered and boss scenarios")
    p.add_argument("--keep", nargs="*")
    build_cmd("enablers", cmd_enablers, "pieces that keep a config condition true, and what they really carry")
    build_cmd("ramp", cmd_ramp, "stack/stage/condition curves for the main skill")
    build_cmd("scales", cmd_scales, "stat elasticity: what one unit of each stat is worth")
    p = build_cmd("headroom", cmd_headroom, "how much each equipped item contributes")
    p.add_argument("--weights")
    p = build_cmd("trade-query", cmd_trade_query, "PoB-weighted trade2 search links per slot")
    p.add_argument("--slot", nargs="*")
    p.add_argument("--league", required=True)
    p.add_argument("--weights", help="e.g. FullDPS:1,TotalEHP:0.5")
    p.add_argument("--max-price", type=float)
    p.add_argument("--currency", help="exalted|divine|chaos (trade2 price option)")
    p.add_argument("--top", type=int, default=12)
    p = build_cmd("upgrade", cmd_upgrade, "rank candidate items by PoB gain per price (CP值)")
    p.add_argument("--candidates", required=True, help="JSON list or text file of items with price:/slot: headers")
    p.add_argument("--slot")
    p.add_argument("--weights")

    p = build_cmd("decompose", cmd_decompose, "multiplier stack: what each support/node/item/condition is worth")
    p.add_argument("--synergy", action="store_true", help="also test pairs of the top sources for engines")
    p.add_argument("--top", type=int, default=25)
    p = sub.add_parser("build-up", help="construct one skill greedily with PoB and show each multiplier")
    p.add_argument("skill")
    p.add_argument("--ascendancy")
    p.add_argument("--tier", choices=list(scan.TIERS), default="mid")
    p.add_argument("--tree-points", type=int, default=40)
    p.add_argument("--no-lineage", action="store_true")
    p.set_defaults(fn=cmd_build_up)

    p = sub.add_parser("scan", help="PoB-only skill strength scan on a standardised character")
    p.add_argument("--tier", choices=list(scan.TIERS), default="mid")
    p.add_argument("--skills", nargs="*")
    p.add_argument("--lineage", action="store_true", help="allow lineage (unique) supports")
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--out", help="save raw scan results (JSON)")
    p.set_defaults(fn=cmd_scan)

    p = build_cmd("export-build", cmd_export_build, "write the in-game Build Planner .build file")
    p.add_argument("--out", required=True)
    p.add_argument("--name")
    p.add_argument("--description")

    p = sub.add_parser("lift", help="skill x ascendancy multiplier (PoB-only)")
    p.add_argument("skills", nargs="+")
    p.add_argument("--tier", choices=list(scan.TIERS), default="mid")
    p.add_argument("--points", type=int, default=8)
    p.add_argument("--top", type=int, default=10)
    p.set_defaults(fn=cmd_lift)

    p = sub.add_parser("profile-batch", help="profile a directory of builds")
    p.add_argument("dir")
    p.add_argument("--out", required=True)
    p.add_argument("--deep", action="store_true", help="also run audit and ramp per build")
    p.set_defaults(fn=cmd_profile_batch)

    p = sub.add_parser("backtest", help="compare a saved scan with observed main skills")
    p.add_argument("--scan", required=True)
    p.add_argument("--profiles", required=True)
    p.add_argument("--top", type=int, default=30)
    p.set_defaults(fn=cmd_backtest)

    args = ap.parse_args(argv)
    try:
        args.fn(args)
    except EngineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
