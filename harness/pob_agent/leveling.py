"""Leveling (pre-ascendancy) evaluation and its backtest.

Raw facts come from the engine once per (stage, class) and are cached (`collect`); scoring runs in
Python on the cache (`score`), so a scoring change costs no engine time. `backtest` checks the
ranking against what players actually level with (docs/research/2026-11-24-leveling-builds.md).

Scoring terms, each switchable so an ablation can show what it earns:
  sets      measure every stat set (hit + DoT) and minions instead of the first set only
  attrs     penalise attribute requirements the class cannot meet at this stage
  clear     rank by a pack-clear proxy (targets reached x time to kill a white monster)
  mana      penalise skills whose mana pool supports few uses
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from . import scan
from .engine import Engine

CACHE = Path(__file__).resolve().parents[2] / "data" / "results" / "leveling_cache"

# skills with no gem tier in PoB data that a stage still allows (talisman forms grant them)
EXTRA_SKILLS = ["Shred", "Maul"]

# community leveling picks (research note §1); a class passes when one of its clear picks ranks top 3.
# FROZEN 2026-11-24: tests/test_smoke.py pins a hash of this table. Do not widen it to make a class pass; new
# labels go into a separate held-out table and are scored once.
BACKTEST = {
    "Witch": {"clear": ["Essence Drain", "Contagion"], "boss": ["Bonestorm", "Essence Drain"]},
    "Sorceress": {"clear": ["Essence Drain", "Contagion", "Ember Fusillade"], "boss": ["Essence Drain"]},
    "Mercenary": {"clear": ["Explosive Grenade", "Gas Grenade", "Fragmentation Rounds"], "boss": []},
    "Huntress": {"clear": ["Twister", "Whirling Slash"], "boss": []},
    # research table rows: werewolf "Lunar Assault + Shred, Pounce, later Cross Slash"; bear "Volcano, Maul,
    # Furious Slam, Shockwave Totem" (Cross Slash/Pounce/Shockwave Totem were missing in the first transcription)
    "Druid": {"clear": ["Shred", "Lunar Assault", "Pounce", "Cross Slash", "Volcano", "Maul", "Furious Slam",
                        "Shockwave Totem"], "boss": ["Shred"]},
    "Monk": {"clear": ["Falling Thunder", "Glacial Cascade"], "boss": []},
    "Ranger": {"clear": ["Lightning Arrow", "Poisonburst Arrow"], "boss": []},
    "Warrior": {"clear": ["Boneshatter", "Rolling Slam"], "boss": []},
}
# skills the research found no leveling evidence for; they should not be a class's top pick
NEGATIVE = {"Witch": ["Rapid Shot", "Galvanic Shards", "Living Bomb"]}

# skills whose clear comes from spreading on death (PoB cannot see the spread)
SPREAD = {"Contagion"}

RARITY_LIFE = {"white": 1.0, "magic": 2.48, "rare": 8.0}
# campaign pack mix by count (an assumption, not measured): whites, all-magic packs, rare-led packs
MIX_CAMPAIGN = {"white": (1.0, 0.6), "magic": (RARITY_LIFE["magic"], 0.3), "rare": (RARITY_LIFE["rare"], 0.1, "leader")}
DEFAULT = {"movement_factor": 0.2, "family": "attr", "area_default": 1.5, "fire_forget": True, "burst": True, "burst_rate": 1.0, "rotation": 3, "max_rate": 1.5, "caster_family": True, "setup": True, "setup_factor": 0.5, "class_weapon": True, "off_weapon_factor": 0.25, "no_conditional": True, "attr_pool": True, "pairs": True, "sets": True, "minion_cap": 3, "attrs": True, "attr_per_point": 5.0, "point_cost": 0.04,
           "clear": True, "pack": 6, "density": 0.3, "pierce_cap": 5, "mana": False, "mana_uses": 8,
           "clear_weight": 1.0,
           # pack mix by count: (monster life multiplier, share of packs). Rarity life multipliers are the
           # hidden MonsterMagic2 / MonsterRare2 mods (poe2wiki): magic 148% more, rare 700% more.
           "mix": MIX_CAMPAIGN, "loadout": True,
           # seconds walking between packs; a fire-and-forget DoT keeps ticking during it (2-5s backtest alike)
           "travel": 2.0}
WHITE_ONLY = {"mix": {"white": (1.0, 1.0)}, "loadout": False}


# collection variants: a stage key may carry a suffix that changes how the engine builds each skill
VARIANTS = {"clearsup": {"supportObjective": "clear"}}
# "target:<file>" restricts the tree to the notables of a target build (a no-respec leveling path)
TARGETS: dict[str, list[str]] = {}


def stage_params(stage: str, cls: str | None = None) -> dict:
    base, _, variant = stage.partition("+")
    p = {**scan.STAGE_COMMON, **scan.STAGES[base], "extraSkills": {s: True for s in EXTRA_SKILLS}}
    for part in variant.split("+") if variant else []:
        if part in VARIANTS:
            p.update(VARIANTS[part])
        elif part.startswith("asc-"):
            p["ascendancy"] = part[4:]
        elif part.startswith("target"):
            p["targetNodes"] = TARGETS[part]
    p["maxPath"] = p["treePoints"]
    if cls:
        p["class"] = cls
    return p


def _cache_file(stage: str, cls: str | None) -> Path:
    return CACHE / stage / f"{cls or '_classless'}.json"


def collect(stage: str, classes: list[str | None], chunk: int = 12, verbose: bool = False,
            progress=None) -> dict:
    """Probe every allowed skill for each class (None = class-less, no tree). Cached per class."""
    out = {}
    with Engine(verbose) as eng:
        info = eng.call("stage_skills", **stage_params(stage))
    names = info["skills"]
    for cls in classes:
        f = _cache_file(stage, cls)
        cached = json.loads(f.read_text()) if f.exists() else {}
        todo = [n for n in names if n not in cached]
        for i in range(0, len(todo), chunk):
            with Engine(verbose) as eng:
                res = eng.call("leveling_probe", skills=todo[i:i + chunk], **stage_params(stage, cls))["results"]
            for r in res:
                cached[r["skill"]] = r
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(cached))
            if progress:
                progress(f"{stage} {cls}: {min(i + chunk, len(todo))}/{len(todo)}")
        out[cls] = cached
    out["_classes"] = {c["name"]: c for c in info["classes"]}
    (CACHE / "classes.json").write_text(json.dumps(out["_classes"]))
    return out


def _load_class_base():
    f = CACHE / "classes.json"
    if f.exists() and not CLASS_BASE:
        CLASS_BASE.update(json.loads(f.read_text()))


def load(stage: str, cls: str | None) -> dict:
    _load_class_base()
    f = _cache_file(stage, cls)
    return json.loads(f.read_text()) if f.exists() else {}


# Weapon each class starts the campaign with (assumption from general game knowledge; Druid unverified).
# A leveling character keeps the weapon type it starts with unless it finds and can wield another.
CLASS_WEAPON = {"Witch": "Wand", "Sorceress": "Staff", "Mercenary": "Crossbow", "Huntress": "Spear",
                "Monk": "Quarterstaff", "Warrior": "Mace", "Ranger": "Bow", "Druid": "Talisman"}

# classes whose campaign tree and ascendancies build around spells (Druid: Volcano/Entangle are spells)
CASTERS = {"Witch", "Sorceress", "Druid"}
# a skill that needs something already there (corpses, a broken-armour or frozen target) cannot be the
# skill that clears a fresh pack; it is a follow-up
SETUP_TYPES = {"TargetsDestructibleCorpses", "ConsumesFullyBrokenArmour", "SkillConsumesFreeze"}
# movement skills (Lightning Warp) deal damage on arrival but are not what a character clears with
NOT_MAIN_TYPES = {"Movement"}

# "Ground": a lingering ground effect left by sustained use (Incinerate's Ignited Ground), not each use
CONDITIONAL = ("Charged", "Infused", "Enraged", "Empowered", "Frenzy", "Primed", "Fully", "Ground")
CLASS_BASE: dict[str, dict] = {}


def _main_variants(vs: list[dict], cfg: dict) -> tuple[dict | None, dict | None]:
    """The hit variant a player gets every use, and a DoT-only variant applied alongside it.

    Variants gated on a resource or state (charged, infused, enraged...) are skipped when
    cfg['no_conditional'] is set: PoB lists them as alternatives, not as the normal use."""
    pool = [v for v in vs if not (cfg["no_conditional"] and any(k in (v.get("label") or "") for k in CONDITIONAL))]
    pool = pool or vs[:1]
    hits = [v for v in pool if (v.get("TotalDot") or 0) == 0 or (v.get("AverageHit") or 0) > 0]
    dots = [v for v in pool if (v.get("TotalDot") or 0) > 0 and not (v.get("AverageHit") or 0) > 0]
    hit = max(hits, key=lambda v: v.get("dps") or 0) if hits else None
    dot = max(dots, key=lambda v: v.get("dps") or 0) if dots else None
    return hit, dot


def _targets(v: dict, cfg: dict, types: set | None = None) -> float:
    pack = cfg["pack"]
    radius = v.get("AreaOfEffectRadiusMetres") or 0
    if not radius and types and "Area" in types and cfg["area_default"]:
        # area skills PoB gives no radius for (arcs, cones) get a modest default
        radius = cfg["area_default"]
    proj = v.get("ProjectileCount") or 0
    pierce = v.get("PierceCount") or 0
    chain = v.get("ChainMax") or 0
    t_area = min(pack, max(1.0, cfg["density"] * math.pi * radius * radius)) if radius else 1.0
    t_proj = min(pack, proj * (1 + min(pierce, cfg["pierce_cap"])) + chain) if proj else 1.0
    return max(t_area, t_proj, 1.0)


def mix_clear(targets: float, pack_time, cfg: dict, life: float = 0.0) -> float:
    """Monsters per second over a mix of packs: total monsters / total time, packs weighted by count.
    `pack_time(mult)` is the time for the ranked skill to clear a pack whose monsters have `mult` x white life.
    Mix entries are (life mult, share) or (life mult, share, "leader") for a pack of whites led by one tough
    monster. With cfg["boss_dps"] set (the class's boss skill), tough monsters may be finished with that skill
    instead: the leveling loadout is a clear skill plus a single-target skill."""
    boss = cfg.get("boss_dps") or 0
    n = t = 0.0
    for e in cfg["mix"].values():
        mult, share = e[0], e[1]
        leader = len(e) > 2 and e[2] == "leader"
        own = pack_time(mult)
        if boss and life and mult > 1:
            alt = (pack_time(1.0) + mult * life / boss) if leader else targets * mult * life / boss
            own = min(own, alt + cfg.get("swap_time", 0.0))
        n += share * targets
        t += share * (own + cfg["travel"])
    return n / t if t else 0.0


def metrics(r: dict, cfg: dict, cls: str | None = None) -> dict | None:
    """Single-target DPS, clear rate and penalties for one probed skill."""
    vs = r.get("variants") or []
    if r.get("error") or not vs:
        return None
    types = set(r.get("types") or [])
    v0 = vs[0]
    hit, dot = None, None
    if not cfg["sets"]:
        st = v0.get("CombinedDPS") or 0
        hit = v0
    else:
        hit, dot = _main_variants(vs, cfg)
        st = (hit.get("dps") or 0 if hit else 0) + (dot.get("dps") or 0 if dot and dot is not hit else 0)
        if "Minion" in types and v0.get("minion"):
            per = v0["minion"].get("CombinedDPS") or v0["minion"].get("TotalDPS") or 0
            st = per * min(v0.get("ActiveMinionLimit") or 1, cfg["minion_cap"])
    if st <= 0:
        return None
    m = {"skill": r["skill"], "st": st, "weapon": r.get("weaponType"), "types": types, "asc_nodes": r.get("ascNodes"),
         "dot": (dot.get("dps") or 0) if dot else (st if "DamageOverTime" in types and not (v0.get("AverageHit") or 0) else 0)}

    # attributes: tree attribute nodes are a free choice in PoE2 (PoB books them as Str), so what the
    # class gained over its base is a pool that can go to any requirement
    short = 0.0
    base = CLASS_BASE.get(cls or "")
    if base and cfg["attr_pool"]:
        have = {a: v0.get(a) or 0 for a in ("Str", "Dex", "Int")}
        pool = sum(have[a] - base[a.lower()] for a in have)
        need = sum(max(0.0, (v0.get("Req" + a) or 0) - base[a.lower()]) for a in have)
        short = max(0.0, need - pool)
    else:
        short = sum(max(0.0, (v0.get("Req" + a) or 0) - (v0.get(a) or 0)) for a in ("Str", "Dex", "Int"))
    m["attr_short"] = short
    m["attr_points"] = math.ceil(short / cfg["attr_per_point"]) if short > 0 else 0
    m["attr_factor"] = (1 - cfg["point_cost"]) ** m["attr_points"] if cfg["attrs"] else 1.0

    # clear proxy: monsters reached per use x how fast each dies (no credit for overkill)
    life = r.get("monsterLife") or 1
    ref = hit or v0
    targets = _targets(ref, cfg, types)
    if dot and dot is not hit:
        targets = max(targets, _targets(dot, cfg, types))
    if r["skill"] in SPREAD:
        targets = cfg["pack"]
    if "Minion" in types:
        targets = min(cfg["pack"], min(v0.get("ActiveMinionLimit") or 1, cfg["minion_cap"]))
    speed0 = ref.get("Speed") or 1
    per_target = st / max(targets, 1) if "Minion" in types else st
    uses = ref.get("StoredUses") or 0

    def kill(hp):
        """Seconds the player spends on a pack whose monsters have `hp` life, and the use rate."""
        speed = speed0
        t = max(hp / per_target, 1 / speed)
        if "Cooldown" in types and r["skill"] not in SPREAD:
            hit_dmg = ref.get("AverageDamage") or ref.get("AverageHit") or (st / speed)
            need = math.ceil(hp / hit_dmg) if hit_dmg > 0 else 99
            if cfg["burst"] and uses >= need:
                # stored uses cover a pack: thrown back to back, the cooldown refills between packs
                t = need / cfg["burst_rate"]
            elif cfg["rotation"] > 1:
                # otherwise cooldown skills are used in rotation with others of the same kind
                speed = min(speed * cfg["rotation"], cfg["max_rate"])
                t = max(hp / per_target, 1 / speed)
        if cfg["fire_forget"] and dot and "Minion" not in types:
            # a DoT that kills within its duration does not hold the player: cast, move on. The pack still
            # takes hp / DoT DPS to die; only the part of that overlapping the walk to the next pack is free.
            dur = dot.get("Duration") or 0
            ddps = dot.get("dps") or 0
            if dur and ddps * dur >= hp:
                t = min(t, max(1 / speed, hp / ddps - cfg["travel"]))
        return t, speed

    kill_time, speed = kill(life)
    m["stored_uses"] = uses
    m["dot_duration"] = (dot.get("Duration") or 0) if dot else 0
    clear = mix_clear(targets, lambda mult: kill(life * mult)[0], cfg, life)
    m.update(targets=targets, kill_time=kill_time, clear=clear, life=life, speed=speed)

    # mana: uses per full pool
    cost = v0.get("ManaCost") or 0
    pool_m = v0.get("Mana") or 0
    m["mana_uses"] = pool_m / cost if cost else float("inf")
    m["mana_factor"] = min(1.0, m["mana_uses"] / cfg["mana_uses"]) if cfg["mana"] and cost else 1.0

    base_score = m["clear"] if cfg["clear"] else st
    if cfg["clear"] and cfg["clear_weight"] < 1:
        base_score = (m["clear"] ** cfg["clear_weight"]) * (st ** (1 - cfg["clear_weight"]))
    # family: is this skill part of the class's archetype?
    w = r.get("weaponType")
    if cfg["family"] == "attr" and cls in CLASS_BASE:
        # PoE2 gem colours follow the class archetypes: a gem's attribute split (Int; Str/Int; Dex/Int...)
        # matches the attributes a class starts high in. Gems with no requirement (talisman-granted forms)
        # fall back to the weapon check.
        split = {a for a in ("Str", "Dex", "Int") if (r.get("req" + a) or 0) > 0}
        primary = {a for a in ("Str", "Dex", "Int") if CLASS_BASE[cls][a.lower()] > 7}
        own = CLASS_WEAPON.get(cls or "")
        off_weapon = bool(w) and bool(own) and own not in w
        off = (split != primary or off_weapon) if split else off_weapon
    else:
        own = CLASS_WEAPON.get(cls or "")
        off = bool(w) and bool(own) and own not in w
        if cfg["caster_family"] and not w and cls and cls not in CASTERS and ("Spell" in types or "Minion" in types):
            off = True
    m["off_weapon"] = off
    m["weapon_factor"] = cfg["off_weapon_factor"] if off and cfg["class_weapon"] else 1.0
    m["needs_setup"] = bool(types & SETUP_TYPES)
    m["setup_factor"] = cfg["setup_factor"] if m["needs_setup"] and cfg["setup"] else 1.0
    if cfg["setup"] and types & NOT_MAIN_TYPES:
        m["setup_factor"] *= cfg["movement_factor"]
        m["movement"] = True
    m["score"] = base_score * m["attr_factor"] * m["mana_factor"] * m["weapon_factor"] * m["setup_factor"]
    return m


def pair_metrics(spreader: dict, dotter: dict, cfg: dict) -> dict | None:
    """Contagion-style pair: the spreader carries the other skill's chaos DoT to the whole pack."""
    if not spreader or not dotter or not dotter.get("dot") or "Chaos" not in dotter["types"]:
        return None
    dps = spreader["dot"] + dotter["dot"]

    def kill(hp):
        # Contagion is cast once per pack (it has a cooldown); the carried skill sets the pace
        if cfg["fire_forget"] and dotter.get("dot_duration") and dps * dotter["dot_duration"] >= hp:
            return max(1 / dotter["speed"], hp / dps - cfg["travel"])
        return max(hp / dps, 1 / dotter["speed"])
    kill_time = kill(spreader["life"])
    clear = mix_clear(cfg["pack"], lambda mult: kill(spreader["life"] * mult), cfg, spreader["life"])
    score = (clear * min(spreader["attr_factor"], dotter["attr_factor"]) * dotter.get("weapon_factor", 1.0)
             * spreader.get("weapon_factor", 1.0) * dotter.get("setup_factor", 1.0))
    return {"skill": f"{spreader['skill']} + {dotter['skill']}", "members": [spreader["skill"], dotter["skill"]],
            "off_weapon": bool(spreader.get("off_weapon") or dotter.get("off_weapon")),
            "st": dotter["st"], "clear": clear, "score": score, "targets": cfg["pack"], "kill_time": kill_time,
            "attr_points": max(spreader["attr_points"], dotter["attr_points"]), "weapon": None, "types": set(),
            "asc_nodes": dotter.get("asc_nodes")}


def rank(stage: str, cls: str, cfg: dict | None = None, data: dict | None = None) -> list[dict]:
    """Score every skill for a class. `stage` may list collections joined by ','; each skill keeps its best
    solo score across them (supports chosen for damage or for clear), and pairs use the first collection
    (damage supports: in a pair the partner covers the pack)."""
    cfg = {**DEFAULT, **(cfg or {})}
    stages = stage.split(",")
    datas = [data] if data is not None else [load(st, cls) for st in stages]
    if cfg.get("loadout") and data is None and len(cfg["mix"]) > 1:
        # tough monsters can be left to the class's best boss skill (raw DPS of the top boss pick)
        top = rank_boss(stage, cls, {**cfg, "loadout": False})
        cfg = {**cfg, "boss_dps": top[0]["st"] if top else 0}
    per = [{m["skill"]: m for m in (metrics(r, cfg, cls) for r in d.values()) if m} for d in datas]
    solo = {}
    for p in per:
        for k, m in p.items():
            if k not in solo or m["score"] > solo[k]["score"]:
                solo[k] = m
    rows = list(solo.values())
    if cfg["pairs"]:
        by = per[0]
        for sp in SPREAD:
            for m in list(by.values()):
                if m["skill"] != sp:
                    p = pair_metrics(by.get(sp), m, cfg)
                    if p:
                        rows.append(p)
    rows.sort(key=lambda m: -m["score"])
    return rows


def rank_boss(stage: str, cls: str, cfg: dict | None = None) -> list[dict]:
    """Boss skill: single-target DPS with the same family, attribute and setup factors (no clear term)."""
    cfg = {**DEFAULT, **(cfg or {})}
    best = {}
    for st in stage.split(","):
        for r in load(st, cls).values():
            m = metrics(r, cfg, cls)
            if m:
                m["boss"] = m["st"] * m["attr_factor"] * m["weapon_factor"] * m["setup_factor"]
                if m["skill"] not in best or m["boss"] > best[m["skill"]]["boss"]:
                    best[m["skill"]] = m
    return sorted(best.values(), key=lambda m: -m["boss"])


def backtest_boss(stage: str, cfg: dict | None = None) -> dict:
    out = {}
    for cls, exp in BACKTEST.items():
        if not exp["boss"]:
            continue
        names = [m["skill"] for m in rank_boss(stage, cls, cfg)]
        ranks = {s: names.index(s) + 1 for s in exp["boss"] if s in names}
        out[cls] = {"ranks": ranks, "top": names[:5]}
    return out


def _random_best(n: int, k: int) -> dict:
    """Best rank of k accepted items among n under a uniformly random order: P(top1), P(top3), E[1/rank]."""
    if n <= 0 or k <= 0:
        return {"top1": 0.0, "top3": 0.0, "rr": 0.0, "dist": []}
    # P(best > r) = C(n-k, r) / C(n, r)
    surv = [math.comb(n - k, r) / math.comb(n, r) for r in range(n + 1)]
    dist = [surv[r - 1] - surv[r] for r in range(1, n + 1)]
    return {"top1": dist[0], "top3": sum(dist[:3]), "rr": sum(p / r for r, p in enumerate(dist, 1)), "dist": dist}


def backtest(stage: str, cfg: dict | None = None, top: int = 3, classes=None, perms: int = 20000) -> dict:
    """Per class: best rank of a community clear pick; pass if within `top`; negatives must not be #1.

    Also scores the rank within the class family (off-family rows dropped) against a uniformly random
    within-family order: expected top-1 / top-3 / MRR, and a permutation p-value for the observed family MRR."""
    import random
    out = {"classes": {}, "passed": 0, "total": 0, "mrr": 0.0, "top1": 0,
           "fam": {"top1": 0, "top3": 0, "mrr": 0.0, "rand_top1": 0.0, "rand_top3": 0.0, "rand_mrr": 0.0}}
    dists = []
    for cls, exp in BACKTEST.items():
        if classes and cls not in classes:
            continue
        if not all(load(st, cls) for st in stage.split(",")):
            continue
        rows = rank(stage, cls, cfg)
        names = [m["skill"] for m in rows]

        def hit(m):
            return any(s in exp["clear"] for s in (m.get("members") or [m["skill"]]))
        ranks = {}
        for i, m in enumerate(rows, 1):
            for s in m.get("members") or [m["skill"]]:
                if s in exp["clear"] and s not in ranks:
                    ranks[s] = i
        best = min(ranks.values()) if ranks else None
        fam = [m for m in rows if not m.get("off_weapon")]
        fam_best = next((i for i, m in enumerate(fam, 1) if hit(m)), None)
        rnd = _random_best(len(fam), sum(1 for m in fam if hit(m)))
        dists.append(rnd["dist"])
        neg = [s for s in NEGATIVE.get(cls, []) if names and names[0] == s]
        ok = best is not None and best <= top and not neg
        out["classes"][cls] = {"best_rank": best, "ranks": ranks, "top": names[:5], "negative_top": neg, "pass": ok,
                               "fam_rank": fam_best, "fam_size": len(fam), "fam_hits": sum(1 for m in fam if hit(m)),
                               "rand_top3": rnd["top3"]}
        out["total"] += 1
        out["passed"] += ok
        out["top1"] += best == 1
        out["mrr"] += (1 / best) if best else 0
        f = out["fam"]
        f["top1"] += fam_best == 1
        f["top3"] += bool(fam_best and fam_best <= 3)
        f["mrr"] += (1 / fam_best) if fam_best else 0
        f["rand_top1"] += rnd["top1"]
        f["rand_top3"] += rnd["top3"]
        f["rand_mrr"] += rnd["rr"]
    if out["total"]:
        n = out["total"]
        out["mrr"] /= n
        out["fam"]["mrr"] /= n
        out["fam"]["rand_mrr"] /= n
        # permutation test: how often a random within-family order reaches the observed family MRR
        rng = random.Random(0)
        obs = out["fam"]["mrr"] - 1e-12
        cum = []
        for d in dists:
            c, acc = [], 0.0
            for p_ in d:
                acc += p_
                c.append(acc)
            cum.append(c)
        hits = 0
        for _ in range(perms):
            tot = 0.0
            for c in cum:
                if not c:
                    continue
                u = rng.random()
                r = next((i for i, v in enumerate(c, 1) if u <= v), None)
                tot += 1 / r if r else 0
            hits += tot / n >= obs
        out["fam"]["p_value"] = hits / perms
    return out
