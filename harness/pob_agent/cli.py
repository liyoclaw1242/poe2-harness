"""pob-agent CLI. Compact markdown output by default (agent-friendly); --json for raw data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import analysis, checkpoints, decompose, enablers, scan, scenario, sources, thresholds, trade
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


TIER_LABEL = {"map": "map monsters", "boss": "map boss", "pinnacle": "pinnacle boss", "uber": "uber pinnacle"}


def render_scenarios(sc: dict):
    print("## Scenarios (which enemy the numbers assume)")
    conf = {"None": "map", "Boss": "boss", "Pinnacle": "pinnacle", "Uber": "uber"}.get(sc["configured"], sc["configured"])
    print(f"The build is configured against: {TIER_LABEL.get(conf, conf)}. Every DPS/multiplier elsewhere in "
          "this report uses that enemy unless stated.")
    print("| enemy | DPS | vs configured | EHP | enemy level | ele res* | armour | damage taken |")
    print("|---|---|---|---|---|---|---|---|")
    base = sc["as_configured"]["dps"] or 0
    for t in sc["tiers"]:
        e = t.get("enemy") or {}
        res = f"{e.get('fireResist', 0):.0f}/{e.get('coldResist', 0):.0f}/{e.get('lightningResist', 0):.0f}"
        dt = e.get("damageTakenMore")
        dts = f"x{dt:.2f}" if dt is not None and abs(dt - 1) > 1e-6 else "x1"
        print(f"| {TIER_LABEL[t['name']]} | {fmt(t['dps'])} | {fpct(analysis.pct(t['dps'], base))} | {fmt(t['ehp'])} | "
              f"{e.get('level', '?')} | {res} | {fmt(e.get('armour'))} | {dts} |")
    print("(*fire/cold/lightning after your own curses/exposure; uber pinnacles take 70% less damage in PoB.)")
    if sc["overrides"]:
        print("The author hand-set these enemy values; the table above uses PoB defaults instead:")
        for o in sc["overrides"]:
            print(f"- {(o.get('label') or o['var']).strip()} = {o['value']}")
    dep = scenario.dependent(sc["sources"])
    if dep:
        print("\nPieces whose worth depends on the enemy (leave-one-out multiplier per enemy):")
        print("| piece | map monsters | map boss | pinnacle | uber | worth more vs |\n|---|---|---|---|---|---|")
        mx = lambda v: "∞" if v == scenario.INF else f"x{v:.2f}"
        for r in dep:
            m = r["mult"]
            print(f"| {r['name']} | {mx(m['map'])} | {mx(m['boss'])} | {mx(m['pinnacle'])} | {mx(m['uber'])} | "
                  f"{TIER_LABEL[r['favours']]} |")
        if any(v < 1 for r in dep for v in r["mult"].values()):
            print("x<1 means the piece costs damage against that enemy (removing it raises DPS).")
        print("Typical causes: resistance penetration/inversion and armour-related damage only matter when the "
              "enemy has resistances/armour (bosses); culling, on-kill and count-of-enemies effects favour maps.")
    elif sc["sources"]:
        print("\nNo measured piece changes its multiplier by 15% or more between map monsters and pinnacle bosses.")


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


def render_headroom(hr):
    rows, margins = (hr["slots"], hr.get("margins")) if isinstance(hr, dict) else (hr, None)
    print("## Slot headroom (share of stats coming from each item's mods)")
    print("| slot | item | DPS from item | EHP from item | threshold it holds |\n|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: (r.get("dps_from_item_pct") or 0) + (r.get("ehp_from_item_pct") or 0)):
        if r.get("note"):
            print(f"| {r['slot']} | {r['item']} | {r['note']} | | |")
            continue
        br = r.get("breaks") or []
        ehp = fpct(r["ehp_from_item_pct"])
        if any(b.get("cliff") for b in br):
            ehp += " ⚠"
        print(f"| {r['slot']} | {r['item']} | {fpct(r['dps_from_item_pct'])} | {ehp} | "
              f"{'; '.join(b['text'] for b in br)} |")
    if any(b.get("cliff") for r in rows for b in r.get("breaks") or []):
        print("⚠ = removing the item crosses a cliff. Mind over Matter: the EHP % is mostly the cliff, not the "
              "item's own stats. Spirit / attributes: PoB does not switch off the skill or gem, so the real loss is "
              "larger than the % shown. Replace it only with something that keeps the threshold.")
    if margins and margins["edges"]:
        print("\nThresholds at the edge (current build):")
        for e in margins["edges"]:
            print(f"- {'NOT MET: ' if e['broken'] else ''}{e['text']}")


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


def _scenario_with_sources(eng, d=None):
    if d is None:
        d = decompose.decompose(eng, conditions=False)
    items = {i["slot"]: i for i in eng.call("items")["items"]}
    main = next((g for g in eng.call("skills")["groups"] if g["main"]), None)
    sups = [g["name"] for g in (main or {}).get("gems", []) if g["support"] and g["enabled"] and g["name"]]
    return scenario.scenarios(eng, scenario.sources_from_decompose(d, items, supports=sups))


def cmd_scenarios(args):
    with Engine(args.verbose) as eng:
        load(eng, args.build)
        emit(args, _scenario_with_sources(eng), render_scenarios)


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
        hr = {"slots": trade.slot_headroom(eng, parse_weights(args.weights)), "margins": thresholds.margins(eng)}
        emit(args, hr, render_headroom)


def cmd_diagnose(args):
    """One-shot report: summary + audit + ramp + scaling + slot headroom."""
    with Engine(args.verbose) as eng:
        info = load(eng, args.build)
        en = enablers.measure(eng)
        a = analysis.audit(eng, keep=set(args.keep or []), backed=enablers.backed_vars(en))
        r = eng.call("ramp")
        r["summary"] = analysis.summarize_ramp(r["ramp"], r["base"])
        el = analysis.elasticity(eng)
        hr = {"slots": trade.slot_headroom(eng), "margins": thresholds.margins(eng)}
        sc = _scenario_with_sources(eng)
        data = {"summary": info, "scenarios": sc, "enablers": en, "audit": a, "ramp": r, "scales": el, "headroom": hr}

        def render(_):
            render_summary(info, eng.version)
            print()
            render_scenarios(sc)
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


def render_campaign(r, stage):
    st = scan.STAGES[stage]
    print(f"## Campaign stage {stage}: level {st['level']}, skill tier <= {st['maxSkillTier']}, gem level <= "
          f"{st['gemLevel']}, support tier <= {st['maxSupportTier']} ({st['supports']} supports), "
          f"{st['treePoints']} passive points, no ascendancy")
    print(f"{r['withDamage']} of {r['scanned']} allowed skills deal damage; top {len(r['results'])} taken to the tree step.")
    best = {}
    for x in r["results"]:
        for c in x["classes"]:
            if c.get("error"):
                continue
            best.setdefault(c["class"], []).append((c["dps"], x, c))
    print("\n### Best skills per class start\n| class | 1st | 2nd | 3rd |\n|---|---|---|---|")
    for cls in sorted(best):
        rows = sorted(best[cls], key=lambda t: -t[0])[:3]
        print(f"| {cls} | " + " | ".join(f"{x['skill']} {fmt(d)}" for d, x, _ in rows) + " |")
    print("\n### Setups\n| skill | weapon | gem lv | supports | best class | DPS | notables taken |\n|---|---|---|---|---|---|---|")
    for x in sorted(r["results"], key=lambda x: -max((c.get("dps") or 0) for c in x["classes"])):
        ok = [c for c in x["classes"] if not c.get("error")]
        if not ok:
            continue
        c = max(ok, key=lambda c: c["dps"])
        print(f"| {x['skill']} | {x.get('weaponType') or '-'} | {x['gemLevel']} | "
              f"{', '.join(s['name'] for s in x.get('supports') or [])} | {c['class']} | {fmt(c['dps'])} | "
              f"{', '.join(p['name'] for p in c['picks'])} |")
    print("\nnote: normal monsters (0% resist), plain weapon base, no gear mods, single target DPS only — this ranks "
          "skills against each other; clear speed, defence and gem availability timing are not modelled. "
          "Stage limits are assumptions to calibrate against real campaign exports. Item-granted skills "
          "(e.g. werewolf Shred) have no tier in PoB data and are not included.")


def render_leveling(rows, cls, stage, top, boss=None):
    base = stage.split(",")[0].split("+")[0]
    st = scan.STAGES[base]
    print(f"## Leveling picks for {cls} — stage {base}: level {st['level']}, gems to level {st['gemLevel']} "
          f"(skill tier <= {st['maxSkillTier']}), {st['supports']} supports of tier <= {st['maxSupportTier']}, "
          f"{st['treePoints']} passive points from the {cls} start, "
          + ((f"{st['ascPoints']} ascendancy points" if st.get("ascScored", True)
              else f"ascendancy not scored ({st['ascPoints']} points barely change PoB's numbers; ranked per class)")
             if st.get("ascPoints") else "no ascendancy"))
    if st.get("ascPoints"):
        print("\n> **Experimental.** Strongest generic class skills at this snapshot, ascendancy-blind. Not a build "
              "recommendation: at asc1 the per-ascendancy ranking scored at chance on a held-out key, and at asc2 it was "
              "not robust (class-clustered p 0.068). Minions, totems and poison are not modelled. To plan a switch to "
              "a target skill, see the ascendancy checkpoints.")
    print("\n| # | skill | clear (monsters/s) | white packs only | single target DPS | monsters per use | "
          "time per pack | notes |")
    print("|---|---|---|---|---|---|---|---|")
    for i, m in enumerate(rows[:top], 1):
        notes = []
        if m.get("members"):
            notes.append("Contagion spreads the partner's chaos DoT")
        if m.get("off_weapon"):
            notes.append("outside the class's weapon/spell family")
        if m.get("needs_setup"):
            notes.append("needs corpses or a prepared target")
        if m.get("attr_points"):
            notes.append(f"~{m['attr_points']} points of attributes short")
        if m.get("asc_nodes"):
            notes.append("ascendancy: " + ", ".join(m["asc_nodes"]))
        if m.get("stored_uses") and m.get("stored_uses") > 1:
            notes.append(f"{m['stored_uses']:.0f} stored uses per pack")
        mx = m.get("clear_mixed")
        mxs = f"{mx:.2f}" if mx is not None else "—"
        print(f"| {i} | {m['skill']} | {m['clear']:.2f} | {mxs} | {fmt(m['st'])} | {m['targets']:.1f} | "
              f"{m['kill_time']:.2f}s | {'; '.join(notes)} |")
    if boss:
        print("\n### Boss skill (single target)")
        print("\n| # | skill | single target DPS | after factors | notes |\n|---|---|---|---|---|")
        for i, m in enumerate(boss[:min(top, 5)], 1):
            notes = []
            if m.get("off_weapon"):
                notes.append("outside the class's weapon/spell family")
            if m.get("needs_setup"):
                notes.append("needs corpses or a prepared target")
            if m.get("attr_points"):
                notes.append(f"~{m['attr_points']} points of attributes short")
            print(f"| {i} | {m['skill']} | {fmt(m['st'])} | {fmt(m['boss'])} | {'; '.join(notes)} |")
        print("\nboss DPS is measured against a level-matched monster with no boss resistances or armour, so "
              "physical attacks read high next to what a real act boss takes.")
    print("\nclear: monsters per second over a campaign pack mix (60% white, 30% magic at 2.48x life, 10% rare-led "
          "with the rare at 8x life, which the boss skill below may finish), with 2s walking between packs. "
          "Off-family skills are scaled x0.25.")
    print("\nnote: PoB numbers on a plain weapon base with no gear mods against white monsters of the stage level; "
          "no credit for overkill; a DoT that kills within its duration lets the player move on, its time to kill "
          "overlapping the walk. Backtested against community leveling picks: see "
          "docs/research/2026-11-24-leveling-builds.md §6.")


def cmd_leveling(args):
    """Rank leveling skills for one class at a campaign stage (collects PoB data on first use)."""
    from . import leveling
    st_def = scan.STAGES[args.stage]
    scored = st_def.get("ascPoints") and st_def.get("ascScored", True)
    asc = f"+asc-{args.ascendancy}" if args.ascendancy and scored else ""
    if args.ascendancy and not scored:
        print(f"note: stage {args.stage} is ranked per class; --ascendancy is ignored", file=sys.stderr)
    if scored and not asc:
        raise SystemExit(f"stage {args.stage} spends ascendancy points: pass --ascendancy")
    stages = [args.stage + asc, args.stage + "+clearsup" + asc]
    for st in stages:
        if not leveling.load(st, args.cls):
            print(f"collecting {st} for {args.cls} (first run takes a few minutes)...", file=sys.stderr)
            leveling.collect(st, [args.cls], verbose=args.verbose)
    cfg = {"off_weapon_factor": args.off_weapon}
    rows = leveling.rank(",".join(stages), args.cls, cfg)
    boss = leveling.rank_boss(",".join(stages), args.cls, cfg)
    # same skills on white packs only, for comparison with the campaign-mix ranking
    mixed = {m["skill"]: m["clear"] for m in
             leveling.rank(",".join(stages), args.cls, {**cfg, **leveling.WHITE_ONLY})}
    for m in rows:
        m["clear_mixed"] = mixed.get(m["skill"])

    def plain(ms):
        return [{k: (sorted(v) if isinstance(v, set) else v) for k, v in m.items()} for m in ms[:args.top]]
    emit(args, {"clear": plain(rows), "boss": plain(boss)},
         lambda _: render_leveling(rows, args.cls, ",".join(stages), args.top, boss))


def cmd_campaign(args):
    """Strongest pre-ascendancy skills per class start at a campaign stage."""
    r = scan.run_campaign(lambda: Engine(args.verbose), args.stage, top=args.top, classes=args.classes)
    emit(args, r, lambda r: render_campaign(r, args.stage))


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


def render_checkpoints(r):
    st = scan.STAGES[r["stage"]]
    sup = ", ".join(s["name"] for s in r.get("supports") or [])
    print(f"## Ascendancy checkpoints: {r['skill']} ({r['class']}) — level {st['level']}, gem level "
          f"{st['gemLevel']}, supports: {sup or 'none'}")
    print("\n| ascendancy | x DPS at 8 | 2 points | 4 points | 6 points | 8 points |\n|---|---|---|---|---|---|")
    for a in r["ascendancies"]:
        if a.get("error"):
            print(f"| {a['ascendancy']} | error | {a['error'][:60]} | | | |")
            continue
        cells = []
        for s in a["steps"]:
            nodes = ", ".join(s["nodes"]) or "—"
            gain = "no DPS gain" if s["no_gain"] else f"x{s['step_lift']:.2f}"
            cells.append(f"{nodes} ({gain})")
        print(f"| {a['ascendancy']} | x{a['lift']:.2f} | " + " | ".join(cells) + " |")
    print("\nEach step spends two points notable-first on the node that adds most DPS to this skill, on a class "
          "template with no passive tree or gear. \"no DPS gain\": no notable helps this skill there; take it "
          "for defence or utility, which is not scored. Conditions an ascendancy node sustains (e.g. Eldritch "
          "Empowerment's sacrifice) are assumed on.")
    print("\nThis is a damage-only order, not the guides' order: guides often take a defensive or utility notable "
          "first. Against 20 frozen guide builds it matched the guide's first notable 6 times (random: 3.6, p 0.13) "
          "and the first two no better than random. Read it as \"what each notable adds to this skill's damage\".")


def cmd_checkpoints(args):
    """Ascendancy checkpoints for one skill: nodes and DPS after each trial, per ascendancy."""
    r = checkpoints.run(args.skill, args.cls, stage=args.stage, ascendancy=args.ascendancy, verbose=args.verbose)
    emit(args, r, render_checkpoints)


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
        cfg = {v["var"]: v["value"] for v in eng.call("config")["values"]}
        d["enemy"] = TIER_LABEL.get({"None": "map", "Boss": "boss", "Pinnacle": "pinnacle", "Uber": "uber"}
                                    .get(cfg.get("enemyIsBoss", "Pinnacle"), "pinnacle"))
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
        if args.scenarios:
            d["scenarios"] = _scenario_with_sources(eng, d)

    def render(d):
        ms = (info.get("mainSkill") or {}).get("name")
        print(f"[{ENV_STAMP.format(ver=eng.version)}]")
        print(f"## {ms} — {info.get('ascendancy') or info.get('className')} — DPS {fmt(d['base_dps'])}")
        print("Leave-one-out: x2.00 = removing it halves DPS. "
              f"Enemy: {d.get('enemy', 'pinnacle boss')} (see `scenarios` for map monsters).\n")
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
        if d.get("scenarios"):
            print()
            render_scenarios(d["scenarios"])
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
    build_cmd("scenarios", cmd_scenarios, "the build vs map monsters / bosses / ubers, and enemy-dependent pieces")
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
    p.add_argument("--scenarios", action="store_true", help="also measure the top sources vs map monsters and bosses")
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

    p = sub.add_parser("leveling", help="rank leveling skills for a class (backtested pre-ascendancy; asc1/asc2 experimental, per class)")
    p.add_argument("--class", dest="cls", required=True)
    p.add_argument("--stage", choices=list(scan.STAGES), default="pre_asc1")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--off-weapon", type=float, default=0.25, help="score factor for skills outside the class family")
    p.add_argument("--ascendancy", help="ignored for leveling ranking (asc1/asc2 are ranked per class)")
    p.set_defaults(fn=cmd_leveling)
    p = sub.add_parser("checkpoints", help="ascendancy checkpoints: nodes and DPS after each trial for one skill")
    p.add_argument("--skill", required=True)
    p.add_argument("--class", dest="cls", required=True)
    p.add_argument("--ascendancy", help="only this ascendancy")
    p.add_argument("--stage", choices=list(scan.STAGES), default="asc2", help="character the skill is measured on")
    p.set_defaults(fn=cmd_checkpoints)
    p = sub.add_parser("campaign", help="strongest pre-ascendancy skills per class start at a campaign stage")
    p.add_argument("--stage", choices=list(scan.STAGES), default="pre_asc1")
    p.add_argument("--top", type=int, default=15, help="skills taken to the per-class tree step")
    p.add_argument("--classes", nargs="*")
    p.set_defaults(fn=cmd_campaign)
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
