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
  - gear: per equipment slot, the affixes PoB's trade generator ranks highest for the build (see gear()).
Gem and support availability come from the drop tables in `switch` (area level ~ character level).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import switch
from .engine import Engine, EngineError
from . import sources
from . import leveling
from . import trade


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


GEAR_TOP = 5


def dps_basis(full_dps, main_dps) -> tuple[str, float]:
    """Which DPS PoB's trade generator weighs, and its base value. The generator uses FullDPS whenever the calculator
    reports it (a Lua number, so 0 counts too) and the main skill's DPS otherwise. A FullDPS of 0 is named as the main
    skill but its base is 0: the generator gives such a slot no DPS term, so it is defence only."""
    if isinstance(full_dps, (int, float)) and full_dps > 0:
        return "full", float(full_dps)
    if isinstance(full_dps, (int, float)):
        return "main", 0.0
    return "main", float(main_dps or 0)


def clean_error(msg: str) -> str:
    """First line of an engine error without the Lua source position (no local paths in text or JSON)."""
    msg = msg.splitlines()[0] if msg else ""
    if re.search(r"(?:[A-Za-z]:)?[/\\][^\s:]*:\d+:", msg):
        msg = msg.rsplit(": ", 1)[-1]
    return re.sub(r"(?:[A-Za-z]:)?[/\\]\S+", "<path>", msg)


def gear(eng, group: int | None) -> list[dict]:
    """Affixes to look for per active equipment slot: PoB's TradeQueryGenerator tests each affix at a mid roll on a
    blank item of the slot's base (the current item removed) and ranks by the gain in DPS + half-weighted EHP (the
    trade-query weights); trade_query topMods keeps affixes that can drop on that base, merged by trade text. The
    main skill is pinned for the calls (PoB uses it when no skill is in Full DPS). An empty off-hand that no
    off-hand can fill (a two-handed main hand, by PoB's own slot rule) is reported as blocked, not measured."""
    ir = eng.call("items")
    items = {i["slot"]: i for i in ir["items"]}
    out = []
    for slot in trade.active_slots(ir):
        it = items.get(slot)
        row = {"slot": slot, "mods": []}
        try:
            info = eng.call("checkup_gear_slot", slot=slot)
        except EngineError as exc:
            row["error"] = clean_error(str(exc))
            out.append(row)
            continue
        if not it:
            row["empty"] = True
            if info.get("blocked"):
                row["blocked"] = True
                out.append(row)
                continue
        else:
            row["type"], row["subType"] = info.get("type"), info.get("subType")
            if (it.get("rarity") or "").upper() == "UNIQUE":
                row["unique"] = it["name"]
        kw = {"group": group} if group is not None else {}
        try:
            q = eng.call("trade_query", slot=slot, statWeights=trade.DEFAULT_WEIGHTS, includeRunes=False,
                         includeCorrupted=False, topMods=GEAR_TOP, **kw)
        except EngineError as exc:
            row["error"] = clean_error(str(exc))
            out.append(row)
            continue
        row["mods"] = [{"text": m["text"], "meanStatDiff": m["meanStatDiff"]} for m in q.get("mods") or []]
        row["dpsBasis"], base = dps_basis(q.get("fullDPS"), q.get("mainDPS"))
        if not base:
            row["defenceOnly"] = True
        out.append(row)
    return out


CONFIG_COUNT = ("count", "countAllowZero", "integer")
# a build-level flag only for options PoB shows because of the build's own mechanics (a skill, a flag such as
# CanWither, a passive), not situational states it shows for anything (enemy frozen, crit recently, ...)
MECHANIC_GATES = {"ifFlag", "ifPlayerFlag", "ifSkill", "ifSkillType", "ifSkillFlag", "ifSkillData", "ifGemFamily",
                  "ifNode", "ifMinionFlag"}
COUNT_GAIN, CHECK_GAIN = 0.001, 0.01   # a count is reported per unit when it adds over 0.1%; a check or list over 1%


def _empty(v) -> bool:
    return v is None or v is False or v == 0 or v == ""


def measure_options(eng, group: int, options: list[dict], base: float, plain_value: float) -> list[dict]:
    """Value of the group with each configuration option on, against `base` (the build before any change):
    a check at true; a count at 1 (reported per unit, with the check options revealed alongside it on, e.g. a banner's
    valour stacks with 'Is Banner Planted?'); a list at each value, the best kept. Only options left empty count, and
    only results above the plain value (and above the report band) are kept. The options are restored after each
    measurement; nothing else in the build changes."""
    rows, ref = [], {}
    checks = {o["var"]: True for o in options if o.get("type") == "check" and _empty(o.get("value"))}
    labels = {o["var"]: o.get("label") or o["var"] for o in options}
    for o in options:
        ty = o.get("type")
        if not _empty(o.get("value")):
            continue
        values_for = (lambda var: (lambda n: {**checks, var: n}))
        if ty == "check":
            tries = [({o["var"]: True}, True)]
        elif ty in CONFIG_COUNT:
            tries = [({**checks, o["var"]: 1}, 1)]
        elif ty == "list":
            tries = [({o["var"]: v}, v) for v in o.get("list") or [] if not _empty(v)]
        else:
            continue
        best = None
        for values, shown in tries:
            v = eng.call("checkup_config_value", group=group, values=values)["value"]
            if best is None or v > best[0]:
                best = (v, shown)
        if best is None:
            continue
        v, shown = best
        # a count's unit is measured against the same character without it: the plain value, or with the checks it
        # is measured alongside already on
        base_v = plain_value
        if ty in CONFIG_COUNT and checks:
            if "checks" not in ref:
                ref["checks"] = eng.call("checkup_config_value", group=group, values=checks)["value"]
            base_v = ref["checks"]
        gain = (v - base_v) / base if base else 0.0
        if gain <= (COUNT_GAIN if ty in CONFIG_COUNT else CHECK_GAIN) or v <= base_v or v <= plain_value:
            continue
        row = {"var": o["var"], "label": o.get("label") or o["var"], "type": ty, "value": shown, "mult": v / base}
        if ty in CONFIG_COUNT and checks:
            row["with"] = sorted(labels[k] for k in checks)
            row["refMult"] = base_v / base
        if ty in CONFIG_COUNT:
            row["unit"] = count_unit(row["label"])
            cap = count_cap(eng, group, values_for(o["var"]), v)
            if cap:
                row["max"] = cap
        if o.get("sources"):
            row["sources"] = o["sources"]
        if o.get("ascendancyNode"):
            row["ascendancyNode"] = o["ascendancyNode"]
        rows.append(row)
    return rows


def count_unit(label: str) -> str | None:
    """The unit a count option counts, from its label: '# of Withered Stacks' -> 'Withered stack'. None when the label
    does not say."""
    m = re.match(r"#\s+of\s+(.+?)[:?]?$", label or "")
    if not m:
        return None
    words = m.group(1).split()
    last = words[-1].lower()
    if last.endswith("ies"):
        last = last[:-3] + "y"
    elif last.endswith("s") and not last.endswith("ss"):
        last = last[:-1]
    return " ".join(words[:-1] + [last])


CAP_STEPS = (2, 4, 8, 16, 32, 64, 128)


def count_cap(eng, group: int, values_for, v1: float) -> int | None:
    """PoB's cap on a count: measured at 2, 4, 8, ... 128 until the value stops rising, then the smallest count with
    the plateau value (bisected between the last rising step and the first flat one). None when it keeps rising."""
    def val(n):
        return eng.call("checkup_config_value", group=group, values=values_for(n))["value"]
    prev_n, prev_v = 1, v1
    for n in CAP_STEPS:
        v = val(n)
        if v <= prev_v * (1 + 1e-12):
            # flat from prev_n on; prev_n // 2 was still rising, so the cap is in (prev_n // 2, prev_n]
            a, b = prev_n // 2, prev_n
            while b - a > 1:
                mid = (a + b) // 2
                if val(mid) >= prev_v * (1 - 1e-12):
                    b = mid
                else:
                    a = mid
            return b
        prev_n, prev_v = n, v
    return None


def best_mult(opt: dict) -> float:
    sup = (opt.get("blasphemy") or {}).get("supports") or []
    return max([opt["mult"]] + [c["mult"] for c in opt.get("config") or []] + [x["mult"] for x in sup])


def baseline_config(build: str, group: int, verbose: bool) -> tuple[list[dict], list[dict]]:
    """Configuration options PoB shows for the build as loaded (the same path a Spirit candidate's engine takes,
    without the paste: a candidate is credited only for options it newly reveals), and the build-level flags: options
    the build itself already makes PoB show (gated by a skill, flag or condition) but leaves empty, which would raise
    the main skill, e.g. a wand's Chaos Bolt can wither yet '# of Withered Stacks' is empty. Each is measured alone."""
    with Engine(verbose) as eng:
        eng.call("load", **sources.resolve(build))
        eng.call("checkup_prepare")
        base = eng.call("checkup_value", group=group)["value"]
        shown = eng.call("checkup_config_shown")["options"]
        flags = []
        if base:
            for o in shown:
                if o.get("gates") and set(o["gates"]) <= MECHANIC_GATES:
                    flags += measure_options(eng, group, [o], base, base)
        return shown, flags


def spirit_sweep(build: str, gems: list[dict], level: int, group: int, shown0: list[dict], flags: list[dict],
                 base: float, verbose: bool = False) -> list[dict]:
    """Each Spirit skill in a fresh engine (spirit_candidate). A candidate is credited for options its paste newly
    reveals; one that only feeds an option the build already shows (Withering Presence also applies the wither a wand's
    Chaos Bolt already enables) is listed under that build-level flag as `spirit_sources`, with no number credited."""
    before = {o["var"] for o in shown0}
    src0 = {o["var"]: set(o.get("sources") or []) for o in shown0}
    by_var = {f["var"]: f for f in flags}
    opts = []
    for gem in gems:
        try:
            r, cfg = spirit_candidate(build, gem["name"], level, group, before, base, verbose)
        except Exception:
            continue
        if (r.get("spiritUnreserved") or 0) < 0:
            continue
        for o in r.get("shown") or []:
            f = by_var.get(o["var"])
            new = set(o.get("sources") or []) - src0.get(o["var"], set())
            if f is not None and gem["name"] in new:
                f.setdefault("spirit_sources", []).append({"name": gem["name"], "spirit": gem["spirit"]})
        plain = r["value"] / base
        if plain > 1.01 or cfg:
            opts.append({**gem, "mult": plain, "spirit_left": r["spiritUnreserved"], "config": cfg})
    for f in flags:
        if f.get("spirit_sources"):
            f["spirit_sources"].sort(key=lambda x: x["name"])
    opts.sort(key=lambda x: (-best_mult(x), x["name"]))
    return opts


def spirit_candidate(build: str, name: str, level: int, group: int, before: set, base: float,
                     verbose: bool = False) -> tuple[dict, list[dict]]:
    """One Spirit skill pasted into a fresh engine: the main group's plain value, and its value with each configuration
    option the paste newly reveals (`before` = options shown without it) set on."""
    with Engine(verbose) as eng:
        eng.call("load", **sources.resolve(build))
        eng.call("checkup_prepare")
        eng.call("paste_skill", text=f"{name} {level}/0  1\n", main=False)
        r = eng.call("checkup_value", group=group)
        r["shown"] = eng.call("checkup_config_shown")["options"]
        revealed = [o for o in r["shown"] if o["var"] not in before]
        return r, measure_options(eng, group, revealed, base, r["value"])


def blasphemy_candidate(build: str, curse: str, level: int, sup_tier: int, group: int, before: set, base: float,
                        verbose: bool = False) -> tuple[dict, list[dict]]:
    """Blasphemy + one curse in a fresh engine (checkup_blasphemy: the plain pair, then up to 2 supports picked greedily
    within the free Spirit), and the configuration options the plain pair newly reveals, measured on the plain pair."""
    with Engine(verbose) as eng:
        eng.call("load", **sources.resolve(build))
        eng.call("checkup_prepare")
        r = eng.call("checkup_blasphemy", group=group, curse=curse, level=level, maxSupportTier=sup_tier, slots=2)
        if r.get("skipped") or not r.get("aura"):
            return r, []
        r2 = eng.call("checkup_value", group=group)
        shown = eng.call("checkup_config_shown")["options"]
        revealed = [o for o in shown if o["var"] not in before]
        return r, measure_options(eng, group, revealed, base, r2["value"])


def hand_cast_value(build: str, curse: str, level: int, group: int, verbose: bool = False) -> float:
    """The main skill's value with the curse cast by hand (pasted alone), for comparison with Blasphemy."""
    with Engine(verbose) as eng:
        eng.call("load", **sources.resolve(build))
        eng.call("checkup_prepare")
        eng.call("paste_skill", text=f"{curse} {level}/0  1\n", main=False)
        return eng.call("checkup_value", group=group)["value"]


def blasphemy_sweep(build: str, blas: dict, level: int, sup_tier: int, group: int, shown0: list[dict], base: float,
                    verbose: bool = False) -> tuple[list[dict], str | None]:
    """Blasphemy with each curse it could carry at this level, one curse at a time. Kept when PoB makes the curse an
    aura, the pair fits the free Spirit, and the plain pair, a support set or a revealed option beats x1.01. Spirit costs
    are PoB's (free Spirit minus what is left). Returns (options, reason skipped)."""
    if not blas or not blas.get("blasphemy"):
        return [], None
    before = {o["var"] for o in shown0}
    opts = []
    for c in blas.get("curses") or []:
        try:
            r, cfg = blasphemy_candidate(build, c["name"], level, sup_tier, group, before, base, verbose)
        except Exception:
            continue
        if r.get("skipped"):
            return [], r["skipped"]
        if not r.get("aura") or (r.get("spirit") or 0) <= 0 or (r.get("spiritUnreserved") or 0) < 0:
            continue
        sups = [{"name": x["name"], "tier": x["tier"], "mult": x["value"] / base, "spirit": x["spirit"],
                 "spirit_left": x["spiritUnreserved"], **({"elsewhere": True} if x.get("elsewhere") else {})}
                for x in r.get("picks") or []]
        opt = {"name": f"Blasphemy + {c['name']}", "tier": max(blas["blasphemy"], c["tier"]), "spirit": r["spirit"],
               "mult": r["value"] / base, "spirit_left": r["spiritUnreserved"], "config": cfg,
               "blasphemy": {"curse": c["name"], "supports": sups, "replaced": r.get("replaced") or []}}
        if best_mult(opt) > 1.01:
            try:
                opt["hand_mult"] = hand_cast_value(build, c["name"], level, group, verbose) / base
            except Exception:
                pass
            opts.append(opt)
    return opts, None


def spirit_together(build: str, opts: list[dict], flags: list[dict], level: int, verbose: bool = False) -> dict | None:
    """The best Blasphemy option with the best other Spirit skill: a listed Spirit option, else a Spirit skill listed
    under a build setting it also feeds (Withering Presence under '# of Withered Stacks'). PoB's Spirit left with both
    pasted in one engine, for the plain pair and for the support set. No combined multiplier is computed."""
    b = next((o for o in opts if o.get("blasphemy")), None)
    o = next((o for o in opts if not o.get("blasphemy")), None)
    if o is None:
        fed = sorted((f for f in flags or [] if f.get("spirit_sources")), key=lambda f: (-f["mult"], f["var"]))
        if fed:
            o = fed[0]["spirit_sources"][0]
    if not b or not o:
        return None
    bl = b["blasphemy"]
    sets = [("plain", [])] + ([("supports", [x["name"] for x in bl["supports"]])] if bl["supports"] else [])
    out = {"blasphemy": b["name"], "other": o["name"], "other_spirit": o["spirit"]}
    for key, sup in sets:
        with Engine(verbose) as eng:
            eng.call("load", **sources.resolve(build))
            eng.call("checkup_prepare")
            eng.call("paste_skill", text=f"{o['name']} {level}/0  1\n", main=False)
            text = f"Blasphemy {level}/0  1\n{bl['curse']} {level}/0  1\n" + "".join(f"{n} 1/0  1\n" for n in sup)
            eng.call("paste_skill", text=text, main=False)
            out[key] = eng.call("eval", code="recalc() return {left = build.calcsTab.mainOutput.SpiritUnreserved or 0}")["left"]
    return out


def run(build: str, top: int = 2, spirit: bool = True, verbose: bool = False, nxt: bool = True,
        gear_check: bool = True) -> dict:
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
        sg = (eng.call("checkup_spirit_gems", maxTier=gem_max, spirit=val.get("spiritUnreserved") or 0)
              if spirit else {})
        spirit_gems = sg.get("gems") or []
        blas_info = {"blasphemy": sg.get("blasphemy"), "curses": sg.get("curses") or []}
        gear_rows = gear(eng, main[0]["index"] if main else None) if gear_check else None
    out = {"minions": prep, "level": level, "gem_max": gem_max, "support_tier": sup_tier, "groups": groups, "main": main,
           "tree": tree, "spirit_free": val.get("spiritUnreserved"), "thresholds": th, "spirit_options": [],
           "spirit_checked": bool(spirit), "next": nexts}
    if main:
        shown0, out["config_flags"] = baseline_config(build, main[0]["index"], verbose)
    if spirit and main and (val.get("spiritUnreserved") or 0) > 0:
        out["spirit_options"] = spirit_sweep(build, spirit_gems, gem_max, main[0]["index"], shown0, out["config_flags"],
                                             val["value"], verbose)
        if val.get("value"):
            blas, skipped = blasphemy_sweep(build, blas_info, gem_max, sup_tier, main[0]["index"], shown0, val["value"],
                                            verbose)
            if skipped:
                out["blasphemy_skipped"] = skipped
            if blas:
                out["spirit_options"] = sorted(out["spirit_options"] + blas, key=lambda x: (-best_mult(x), x["name"]))
                try:
                    tg = spirit_together(build, out["spirit_options"], out.get("config_flags"), gem_max, verbose)
                except Exception:
                    tg = None
                if tg:
                    out["spirit_together"] = tg
    if gear_rows is not None:
        out["gear"] = gear_rows
    return out


# ---------------------------------------------------------------------------
# checkup --guide: bases to pick up and jewels, read from data.itemBases and the check-up's own trade-query rows

# official Traditional Chinese base names (poe2db.tw, CC BY-NC-SA 3.0; see data/NOTICE). They cover every equippable
# item type except trap tools (ZH_UNCOVERED); a base missing from the table prints in English.
ZH_FILE = Path(__file__).resolve().parent / "data" / "base_names_zh_tw.json"
ZH_TYPES = ("Amulet", "Belt", "Body Armour", "Boots", "Bow", "Charm", "Claw", "Crossbow", "Dagger", "Flail", "Focus",
            "Gloves", "Helmet", "Jewel", "One Hand Axe", "One Hand Mace", "One Hand Sword", "Quiver", "Ring", "Sceptre",
            "Shield", "Spear", "Staff", "Talisman", "Two Hand Axe", "Two Hand Mace", "Two Hand Sword", "Wand")
ZH_UNCOVERED = ("TrapTool",)
GUIDE_LEVEL_AHEAD = 3   # a base is listed when its level requirement is at most character level + 3 (display window)
ARMOUR_TYPES = ("Helmet", "Body Armour", "Gloves", "Boots", "Shield", "Focus", "Buckler")
JEWELRY_TYPES = ("Amulet", "Ring", "Belt")
GUIDE_AFFIXES = 4      # affix texts per slot in the guide
JEWEL_BASES = ("Emerald", "Ruby", "Sapphire")


def load_zh() -> dict:
    """en -> zh base names; empty when the table is absent or unreadable (every base then prints in English)."""
    try:
        return json.loads(ZH_FILE.read_text(encoding="utf-8")).get("names") or {}
    except (OSError, ValueError):
        return {}


def zh_name(en: str | None, names: dict) -> str | None:
    """The table's name for a base, trying the name without a trailing " (...)" (PoB's Shrine Sceptre variants)."""
    if not en:
        return None
    return names.get(en) or names.get(re.sub(r" \([^()]*\)$", "", en))


def norm_mod(line: str) -> str:
    """A mod line as trade text: {variant} tags dropped, (a-b) ranges and numbers -> #, leading + stripped, (Local)
    ignored. "+(20-30)% to Fire Resistance" -> "#% to Fire Resistance"."""
    line = re.sub(r"\{[^}]*\}", "", line)
    line = re.sub(r"\(-?\d+(?:\.\d+)?--?\d+(?:\.\d+)?\)", "#", line)
    line = re.sub(r"\d+(?:\.\d+)?", "#", line)
    line = line.replace("(Local)", "")
    return " ".join(line.split()).lstrip("+")


def defence_value(b: dict) -> float:
    """A base's listed defences summed (hybrids add their defences)."""
    return sum((b.get("defences") or {}).values())


def _defence_keys(b: dict) -> frozenset:
    return frozenset(k for k, v in (b.get("defences") or {}).items() if v)


def _grants_skill(b: dict) -> bool:
    return any(x.startswith("Grants Skill:") for x in b.get("implicits") or [])


def guide_bases(row: dict, info: dict | None, level: int) -> dict:
    """Bases for one gear slot (`row` = the check-up's gear row, `info` = checkup_gear_bases). Candidates need
    reqLevel <= level + GUIDE_LEVEL_AHEAD.
      - armour, focus, shield: the same subType (when the equipped base has one) and the same set of defence keys,
        summed defence strictly above the equipped base's; up to 2, highest first (ties: lower reqLevel, then name).
        An empty slot: the top base of each subType (defence type), without Ward (runeforged) bases.
      - weapons: no pick-up; up to 2 bases of the same type and subType with a higher reqLevel than the equipped one,
        highest first; a base that grants a skill only lists bases granting the same skill. Empty: nothing.
      - amulet, ring, belt: a base whose implicit (as trade text) equals one of the slot's ranked affixes, ordered by
        that affix's rank, up to 3; the equipped base is marked.
      - a unique: no base list; a blocked off-hand: nothing."""
    out = {"slot": row["slot"], "affixes": [m["text"] for m in (row.get("mods") or [])[:GUIDE_AFFIXES]], "picks": []}
    if row.get("error"):
        out["error"] = row["error"]
    if row.get("blocked"):
        out["blocked"] = True
        return out
    info = info or {}
    eq = info.get("equipped")
    if eq:
        out["equipped"] = {"base": eq["base"], "reqLevel": eq["reqLevel"], "type": eq["type"],
                           "defences": dict(eq.get("defences") or {}), "implicits": list(eq.get("implicits") or [])}
    else:
        out["empty"] = True
    if row.get("unique") or (eq and (eq.get("rarity") or "").upper() == "UNIQUE"):
        out["unique"] = row.get("unique") or eq.get("name")
        return out
    cands = [c for c in info.get("candidates") or [] if c["reqLevel"] <= level + GUIDE_LEVEL_AHEAD]
    ty = eq["type"] if eq else (cands[0]["type"] if cands else None)
    if not ty:
        return out

    def pick(c, **extra):
        return {"base": c["base"], "reqLevel": c["reqLevel"], "defences": dict(c.get("defences") or {}),
                "implicits": list(c.get("implicits") or []), **extra}

    if ty in ARMOUR_TYPES:
        out["rule"] = "armour"
        if eq:
            keys, value = _defence_keys(eq), defence_value(eq)
            pool = [c for c in cands if (not eq.get("subType") or c.get("subType") == eq["subType"])
                    and _defence_keys(c) == keys and defence_value(c) > value]
            pool.sort(key=lambda c: (-defence_value(c), c["reqLevel"], c["base"]))
            out["picks"] = [pick(c, value=defence_value(c)) for c in pool[:2]]
        else:
            # an empty slot is not ranked across defence types: the top base of each subType (no Ward runeforged)
            best = {}
            for c in sorted((c for c in cands if defence_value(c) > 0 and "ward" not in _defence_keys(c)),
                            key=lambda c: (-defence_value(c), c["reqLevel"], c["base"])):
                best.setdefault(c.get("subType") or "", c)
            out["picks"] = [pick(best[k], value=defence_value(best[k]), subType=best[k].get("subType"))
                            for k in sorted(best)]
    elif ty in JEWELRY_TYPES:
        out["rule"] = "jewelry"
        ranked = [norm_mod(m["text"]) for m in row.get("mods") or []]
        pool = []
        for c in cands:
            hits = [(ranked.index(norm_mod(x)), x) for x in c.get("implicits") or [] if norm_mod(x) in ranked]
            if hits:
                rank, line = min(hits)
                pool.append((rank, c["reqLevel"], c["base"], c, row["mods"][rank]["text"]))
        pool.sort(key=lambda x: x[:3])
        out["picks"] = [pick(c, affix=text, **({"equipped": True} if eq and c["base"] == eq["base"] else {}))
                        for _, _, _, c, text in pool[:3]]
    elif eq:
        out["rule"] = "weapon"
        skill = _grants_skill(eq)
        out["grantsSkill"] = skill
        same = [norm_mod(x) for x in eq.get("implicits") or []]
        pool = [c for c in cands if c["reqLevel"] > eq["reqLevel"]
                and (not eq.get("subType") or c.get("subType") == eq["subType"])
                and (not skill or [norm_mod(x) for x in c.get("implicits") or []] == same)]
        pool.sort(key=lambda c: (-c["reqLevel"], c["base"]))
        out["picks"] = [pick(c) for c in pool[:2]]
    return out


def jewel_singles(mods: list[dict], base: float, values: list[float]) -> list[dict]:
    """Jewel mods whose test jewel (the mod alone, mean roll) raises the check-up value, best first (ties: text, id).
    Each row keeps its mult = value / base."""
    rows = [{**m, "text": " / ".join(norm_mod(x) for x in m["lines"]), "mult": v / base}
            for m, v in zip(mods, values) if base > 0 and v > base]
    rows.sort(key=lambda m: (-m["mult"], m["text"], m["modId"]))
    return rows


def jewel_sets(singles: list[dict]) -> list[dict]:
    """Per base jewel, the set measured as one jewel: mods taken greedily in single-mod order while the base allows
    them (spawn weight > 0), at most 2 prefixes and 2 suffixes, one mod per mod group."""
    out = []
    for base in JEWEL_BASES:
        picked, groups, kinds = [], set(), {"Prefix": 0, "Suffix": 0}
        for m in singles:
            if base in m["bases"] and m["group"] not in groups and kinds[m["type"]] < 2:
                picked.append(m)
                groups.add(m["group"])
                kinds[m["type"]] += 1
        if picked:
            out.append({"base": base, "modIds": [m["modId"] for m in picked], "affixes": [m["text"] for m in picked]})
    return out


def jewel_pick(sets: list[dict]) -> dict | None:
    """The set with the highest measured value; ties: more affixes, then the base name."""
    return min(sets, key=lambda x: (-x["value"], -len(x["modIds"]), x["base"])) if sets else None


def guide(build: str, r: dict, verbose: bool = False) -> dict:
    """The guide pass after run(): per gear slot the bases to pick up (checkup_gear_bases + guide_bases); per empty
    allocated jewel socket the base jewel and affixes measured on the check-up value of the main skill (each droppable
    Jewel mod alone as a test jewel at mean rolls, then each base's greedy set as one jewel); the skills reserving
    Spirit. Every base carries its zh name from the table (None when missing)."""
    names = load_zh()
    level = r["level"]
    main = r.get("main") or []
    group = main[0]["index"] if main else None
    out = {"gear": [], "jewels": [], "zh_types": list(ZH_TYPES), "zh_uncovered": list(ZH_UNCOVERED)}
    with Engine(verbose) as eng:
        eng.call("load", **sources.resolve(build))
        eng.call("checkup_prepare")
        out["spirit_in_use"] = eng.call("checkup_spirit_in_use")["names"]
        for row in r.get("gear") or []:
            info = None
            if not row.get("blocked"):
                try:
                    info = eng.call("checkup_gear_bases", slot=row["slot"])
                except EngineError as exc:
                    out["gear"].append({"slot": row["slot"], "picks": [], "error": clean_error(str(exc)),
                                        "affixes": [m["text"] for m in (row.get("mods") or [])[:GUIDE_AFFIXES]]})
                    continue
            g = guide_bases(row, info, level)
            for b in ([g["equipped"]] if g.get("equipped") else []) + g["picks"]:
                b["zh"] = zh_name(b["base"], names)
            out["gear"].append(g)
        jewels = (r.get("next") or {}).get("jewels") or []
        if group is not None:
            # the check-up value with no test jewel, and PoB's main-output DPS of the same skill (for the gear caveat)
            v0 = eng.call("checkup_jewel_values", group=group, jewels=[])
            out["value"], out["mainDps"] = v0["base"], v0["mainDps"]
        mods = eng.call("checkup_jewel_mods")["mods"] if jewels and group is not None else []
        for j in jewels:
            row = {"name": j["name"], "id": j["id"], "base": None, "affixes": [], "sets": []}
            if group is None:
                out["jewels"].append(row)
                continue
            slot = f"Jewel {j['id']}"
            try:
                single = eng.call("checkup_jewel_values", group=group, slot=slot,
                                  jewels=[{"base": m["bases"][0], "modIds": [m["modId"]]} for m in mods])
                singles = jewel_singles(mods, single["base"], single["values"])
                sets = jewel_sets(singles)
                if sets:
                    full = eng.call("checkup_jewel_values", group=group, slot=slot,
                                    jewels=[{"base": x["base"], "modIds": x["modIds"]} for x in sets])
                    for x, v in zip(sets, full["values"]):
                        x["value"], x["mult"] = v, v / full["base"]
            except EngineError as exc:
                row["error"] = clean_error(str(exc))
                out["jewels"].append(row)
                continue
            row["singles"] = [{"modId": m["modId"], "text": m["text"], "mult": m["mult"]} for m in singles]
            row["sets"] = sets
            best = jewel_pick(sets)
            if best:
                row.update(base=best["base"], affixes=best["affixes"], modIds=best["modIds"], mult=best["mult"])
            row["zh"] = zh_name(row["base"], names)
            out["jewels"].append(row)
    return out
