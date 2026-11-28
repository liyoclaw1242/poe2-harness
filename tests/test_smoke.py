"""Smoke tests against the real headless engine (needs scripts/setup.sh)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))

from pob_agent import analysis, sources  # noqa: E402
from pob_agent.engine import Engine  # noqa: E402

BUILD = ROOT / "examples" / "builds" / "sunder_gemling_pobbin_cbIdNpC1nKDX.code"


def test_preprocess_compound_assignment():
    import subprocess
    from pob_agent.engine import find_luajit, LUA_DIR
    lua = (
        'local src = io.open("%s"):read("*a")\n'
        'local pp = assert(loadstring(src:match("(local function splitRhs.-)\\nlocal function preprocess") '
        '.. "\\nreturn rewriteCompound"))()\n'
        'print(pp("if c == \\"{\\" then depth += 1 elseif c == \\"}\\" then depth -= 1 end"))\n'
        'print(pp("\\turl ..= \\"/\\" .. x"))\n'
    ) % (LUA_DIR / "pob_headless.lua")
    out = subprocess.run([find_luajit(), "-e", lua], capture_output=True, text=True, check=True).stdout
    assert "depth = depth + (1) elseif" in out and "depth = depth - (1) end" in out
    assert 'url = url .. ("/" .. x)' in out


def test_load_and_known_numbers():
    with Engine() as eng:
        info = eng.call("load", **sources.resolve(str(BUILD)))
        assert info["ascendancy"] == "Gemling Legionnaire"
        assert info["mainSkill"]["name"] == "Sunder"
        # pobarchives lists 344K DPS / 10.98K EHP for this paste
        assert abs(info["stats"]["TotalDPS"] - 344_000) / 344_000 < 0.02
        assert abs(info["stats"]["TotalEHP"] - 10_980) / 10_980 < 0.02


def test_audit_finds_rage_and_armour_break():
    with Engine() as eng:
        eng.call("load", **sources.resolve(str(BUILD)))
        a = analysis.audit(eng)
        kinds = {i.var: i.kind for i in a["items"]}
        assert kinds["multiplierRage"] == "ramp"
        assert kinds["conditionEnemyArmourBroken"] == "enemy_state"
        assert analysis.dps_of(a["dewatered"]) < analysis.dps_of(a["base"])


def test_twister_hidden_multiplier_detected():
    from pob_agent import scan
    with Engine() as eng:
        res = scan.run_scan(eng, tier="mid", skills=["Twister"])
    factor, notes = scan.ramp_factor(res[0])
    assert factor > 3, notes  # 80% more per Whirlwind stage, capped


def test_custom_mods_reach_the_calc():
    """PoB-PoE2 reads configSets[].customModsList; probes and template mods must change the numbers."""
    with Engine() as eng:
        eng.call("load", **sources.resolve(str(BUILD)))
        r = eng.call("variants", variants=[{"name": "dmg", "values": {}, "appendMods": "100% increased Damage"}],
                     fields=list(analysis.DPS_KEYS))
        base, probe = analysis.dps_of(r["base"]), analysis.dps_of(r["variants"][0]["stats"])
        assert probe > base * 1.05
        # and the snapshot/restore leaves the build unchanged
        again = eng.call("variants", variants=[], fields=list(analysis.DPS_KEYS))
        assert abs(analysis.dps_of(again["base"]) - base) < 1e-6 * base


def test_decompose_node_baseline_consistent():
    """Removing nothing must give x1.00 for every layer path (fast-calc baseline matches)."""
    with Engine() as eng:
        eng.call("load", **sources.resolve(str(BUILD)))
        d = eng.call("decompose")
        for s in d["tree"] + d["ascendancy"]:
            assert s["mult"] == "inf" or s["mult"] > 0.5


def test_enabler_measures_piece_and_its_condition():
    """A table entry tying a node to a ticked config box reports alone / cond / with consistently,
    and the box it keeps true survives dewatering."""
    from pob_agent import enablers
    fake = enablers.Enabler(id="t", kind="node", name="Mystical Rage", off={"multiplierRage": None},
                            text="test", confidence="high")
    with Engine() as eng:
        eng.call("load", **sources.resolve(str(BUILD)))
        dec = {t["name"]: t["mult"] for t in eng.call("decompose")["tree"]}
        en = enablers.measure(eng, table=[fake], detect=True)
        assert isinstance(en["detected"], list)
        (row,) = en["rows"]
        assert row["active"] == ["multiplierRage"] and row["relies"]
        assert abs(row["alone"] - dec["Mystical Rage"]) < 0.01      # same path as decompose
        assert row["cond"] > 1.05 and row["with"] >= row["cond"] - 1e-6
        backed = enablers.backed_vars(en)
        assert backed == {"multiplierRage": "Mystical Rage"}
        a = analysis.audit(eng, backed=backed)
        plain = analysis.audit(eng)
        assert analysis.dps_of(a["dewatered"]) > analysis.dps_of(plain["dewatered"]) * 1.05
        assert next(i for i in a["items"] if i.var == "multiplierRage").backed_by == "Mystical Rage"


def test_enabler_absent_piece_is_skipped():
    from pob_agent import enablers
    with Engine() as eng:
        eng.call("load", **sources.resolve(str(BUILD)))
        en = enablers.measure(eng, detect=False)   # no table piece in this Sunder build
        assert en["rows"] == []


def test_scenarios_tiers_and_sources():
    """Four enemy tiers with PoB's default resistances, and per-tier leave-one-out for sources."""
    from pob_agent import scenario
    with Engine() as eng:
        eng.call("load", **sources.resolve(str(BUILD)))
        src = [{"kind": "node", "name": "Mystical Rage", "layer": "notable"}]
        sc = scenario.scenarios(eng, src)
        tiers = {t["name"]: t for t in sc["tiers"]}
        assert list(tiers) == ["map", "boss", "pinnacle", "uber"]
        assert tiers["map"]["enemy"]["fireResist"] <= tiers["pinnacle"]["enemy"]["fireResist"]
        assert abs(tiers["uber"]["enemy"]["damageTakenMore"] - 0.3) < 1e-6
        assert tiers["uber"]["dps"] < tiers["pinnacle"]["dps"]
        # configured enemy is the PoB default (pinnacle) and no author overrides
        assert sc["configured"] == "Pinnacle" and sc["overrides"] == []
        assert abs(sc["as_configured"]["dps"] - tiers["pinnacle"]["dps"]) / tiers["pinnacle"]["dps"] < 1e-6
        (row,) = sc["sources"]
        assert set(row["mult"]) == set(scenario.TIERS) and all(v > 1 for v in row["mult"].values())
        # the build is unchanged afterwards
        cfg = {v["var"]: v["value"] for v in eng.call("config")["values"]}
        assert "enemyIsBoss" not in cfg


def test_scenario_dependent_picks_spread():
    from pob_agent import scenario
    rows = [{"name": "inv", "layer": "support", "mult": {"map": 1.0, "boss": 1.6, "pinnacle": 2.2, "uber": 2.2}},
            {"name": "flat", "layer": "gear", "mult": {"map": 1.3, "boss": 1.3, "pinnacle": 1.31, "uber": 1.31}}]
    dep = scenario.dependent(rows)
    assert [r["name"] for r in dep] == ["inv"] and dep[0]["favours"] == "pinnacle"


def test_threshold_breaks_classifies_cliffs():
    from pob_agent import thresholds
    base = {"sharedMindOverMatter": 100, "LifeUnreserved": 91, "MissingFireResist": 0, "FireResist": 75,
            "SpiritUnreserved": 10, "Str": 100, "ReqStr": 90}
    new = {"sharedMindOverMatter": 70, "LifeUnreserved": 91, "MissingFireResist": 20, "FireResist": 55,
           "SpiritUnreserved": -5, "Str": 80, "ReqStr": 90}
    br = {b["kind"]: b for b in thresholds.breaks(base, new)}
    assert set(br) == {"mom", "resist", "spirit", "attribute"}
    assert br["mom"]["cliff"] and br["spirit"]["cliff"] and br["attribute"]["cliff"] and not br["resist"]["cliff"]
    assert thresholds.breaks(base, base) == []


def test_threshold_margins_and_headroom():
    from pob_agent import thresholds, trade
    with Engine() as eng:
        eng.call("load", **sources.resolve(str(BUILD)))
        m = thresholds.margins(eng)
        assert set(m["raw"]["resists"]) == {"Fire", "Cold", "Lightning", "Chaos"}
        assert all("text" in e for e in m["edges"])
        rows = trade.slot_headroom(eng)
        assert rows and all(isinstance(r["breaks"], list) for r in rows)


def _probe(skill, sets, types, **v0):
    variants = [{"label": lab, "dps": d, "TotalDot": dot, "AverageHit": hit, "Speed": 1.25, **v0}
                for lab, d, dot, hit in sets]
    return {"skill": skill, "types": types, "variants": variants, "monsterLife": 366, "weaponType": None,
            "reqInt": 100}


def test_leveling_scores_dot_sets_pairs_and_family():
    from pob_agent import leveling as L
    L.CLASS_BASE.update({"Witch": {"str": 7, "dex": 7, "int": 15}, "Warrior": {"str": 15, "dex": 7, "int": 7}})
    cfg = dict(L.DEFAULT)
    ed = _probe("Essence Drain", [("Projectile", 160, 0, 100), ("Damage over Time", 150, 150, 0)],
                ["Spell", "Chaos", "DamageOverTime", "Projectile"], ProjectileCount=1)
    ed["variants"][1]["Duration"] = 4.8
    cont = _probe("Contagion", [("Contagion", 55, 55, 0)], ["Spell", "Chaos", "DamageOverTime", "Cooldown"],
                  AreaOfEffectRadiusMetres=1.7)
    m = L.metrics(ed, cfg, "Witch")
    assert m["st"] == 310  # hit and DoT sets are both counted
    c = L.metrics(cont, cfg, "Witch")
    pair = L.pair_metrics(c, m, cfg)
    assert pair and pair["targets"] == cfg["pack"] and pair["clear"] > m["clear"] / 6
    # a charged variant is not the normal use
    sp = _probe("Spear", [("Explosion", 100, 0, 100), ("Frenzy-Charged", 400, 0, 400)], ["Attack", "Area"],
                AreaOfEffectRadiusMetres=2.0)
    assert L.metrics(sp, cfg, "Witch")["st"] == 100
    # spells are off-family for a martial class
    assert L.metrics(ed, cfg, "Warrior")["weapon_factor"] < 1 and L.metrics(ed, cfg, "Witch")["weapon_factor"] == 1


def test_leveling_probe_reads_dot_set_and_minions():
    from pob_agent import leveling as L
    with Engine() as eng:
        res = eng.call("leveling_probe", skills=["Essence Drain", "Raise Zombie"], **L.stage_params("pre_asc1"))
    ed, rz = res["results"]
    labels = [v.get("label") for v in ed["variants"]]
    assert "Damage over Time" in labels and any((v.get("TotalDot") or 0) > 0 for v in ed["variants"])
    assert rz["variants"][0]["dps"] > 0 and rz["variants"][0].get("minion")
    # support gems with levels are capped at the stage level (Unleash at 20 needed 157 Int)
    assert all((v.get("ReqInt") or 0) < 100 for v in ed["variants"])


def test_dot_set_value_same_in_every_command():
    # setsValue's DoT duration factor is read per skill (setsContext), so the checkpoints command picks the same
    # supports as leveling_probe, in a fresh engine and after a probe at another stage. Before, a fresh engine had no
    # factor (Swift Affliction won) and a shared one used whatever the last probe left.
    from pob_agent import leveling as L
    p1, p2 = L.stage_params("act1", "Witch"), L.stage_params("pre_asc1", "Witch")
    names = lambda r: [s["name"] if isinstance(s, dict) else s for s in r.get("supports") or []]
    with Engine() as eng:
        fresh = names(eng.call("ascendancy_checkpoints", skill="Essence Drain", **{**p1, "class": "Witch", "steps": [2]}))
        eng.call("leveling_probe", skills=["Essence Drain"], **p2)
        probe = names(eng.call("leveling_probe", skills=["Essence Drain"], **p1)["results"][0])
        after = names(eng.call("ascendancy_checkpoints", skill="Essence Drain", **{**p1, "class": "Witch", "steps": [2]}))
    assert fresh == probe == after
    assert "Swift Affliction I" not in probe


def test_only_earthquake_aftershock_radius_is_pinned():
    # pinSkillDataOverrides: a stat set's own remapping of skill radius wins over the generic one (PoB merged both in
    # hash order, radius 2.1 or 3.0 per run). One stat in today's data; a data update that adds more shows up here.
    with Engine() as eng:
        assert eng.pinned_stats == 1


def test_checkup_clear_and_boss_supports():
    # check-up support advice, once for bosses (PoB greedy on single-target DPS) and once for packs (the leveling
    # ranking's clear model over current / DPS-best / area-best sets). The current set is probed as socketed: a JSON
    # null once decoded to an empty set and scored the bare skill.
    from pob_agent import checkup
    sel = ("for cid, c in pairs(build.spec.tree.classes) do if c.name == 'Witch' then build.spec:SelectClass(cid) end end "
           "recalc() return true")
    with Engine() as eng:
        eng.call("new", level=14)
        eng.call("eval", code=sel)
        eng.call("paste_skill", text="Essence Drain 5/0  1\nSwift Affliction I 1/0  1\nControlled Destruction 1/0  1\n",
                 main=True)
        eng.call("checkup_prepare")
        g = eng.call("checkup_groups")["groups"][0]
        sc = checkup.support_checks(eng, g["index"], 1)
    cur = next(c for c in sc["clear"]["candidates"] if c["label"] == "current")
    assert abs(cur["st"] - g["value"]) <= 0.02 * g["value"]
    assert sc["boss"]["mult"] >= 1 and sc["clear"]["mult"] >= 1
    assert all(p["tier"] <= 1 for p in sc["boss"]["best"])


def test_checkup_clear_with_contagion_scores_the_pair():
    # with Contagion in the build, Essence Drain's clear is the pair's (Contagion covers the pack), so reach supports
    # that cost DPS (Pierce, Multishot, Chain) must not win; solo they looked like x3-5
    from pob_agent import checkup
    sel = ("for cid, c in pairs(build.spec.tree.classes) do if c.name == 'Witch' then build.spec:SelectClass(cid) end end "
           "recalc() return true")
    with Engine() as eng:
        eng.call("new", level=14)
        eng.call("eval", code=sel)
        eng.call("paste_skill", text="Essence Drain 5/0  1\nSwift Affliction I 1/0  1\n", main=True)
        eng.call("paste_skill", text="Contagion 5/0  1\n", main=False)
        eng.call("checkup_prepare")
        groups = eng.call("checkup_groups")["groups"]
        ed = next(g for g in groups if g["skill"] == "Essence Drain")
        sp = next(g for g in groups if g["skill"] == "Contagion")
        sc = checkup.support_checks(eng, ed["index"], 1, sp["index"])
    assert sc["clear"]["pair"] == "Contagion + Essence Drain"
    assert not {"Pierce I", "Multishot I", "Chain I"} & {p["name"] for p in sc["clear"]["best"]}


def test_leveling_probe_never_picks_hourglass():
    # Hourglass trades cast rate for a cooldown and nothing checks the skill's uptime against it; Contagion act1
    # used to pick it first (10 s cooldown, cast once per pack in the ranking)
    from pob_agent import leveling as L
    with Engine() as eng:
        res = eng.call("leveling_probe", skills=["Contagion"], **L.stage_params("act1", "Witch"))["results"][0]
    assert res["supports"] and "Hourglass" not in {s["name"] for s in res["supports"]}


def test_checkup_never_recommends_hourglass():
    # same exclusion in the check-up; a socketed Hourglass stays in the current set and is scored as it is
    from pob_agent import checkup
    sel = ("for cid, c in pairs(build.spec.tree.classes) do if c.name == 'Witch' then build.spec:SelectClass(cid) end end "
           "recalc() return true")
    with Engine() as eng:
        eng.call("new", level=30)
        eng.call("eval", code=sel)
        eng.call("paste_skill", text="Essence Drain 8/0  1\n", main=True)
        eng.call("paste_skill", text="Contagion 8/0  1\nHourglass 1/0  1\n", main=False)
        eng.call("checkup_prepare")
        sp = next(g for g in eng.call("checkup_groups")["groups"] if g["skill"] == "Contagion")
        sc = checkup.support_checks(eng, sp["index"], 3)
    assert "Hourglass" in sc["boss"]["current"]
    for mode in ("boss", "clear"):
        assert "Hourglass" not in {p["name"] for p in sc[mode]["best"]}


COOLDOWN_SUPPORTS = ["Breachlord's Amalgam", "Excise", "Execrate", "Expanse", "Hayoxi's Fulmination", "Hourglass",
                     "Nova Projectiles II", "Zarokh's Refrain", "Zarokh's Revolt"]


def test_supports_that_grant_a_cooldown_are_never_picked():
    # every support giving the skill a cooldown (read from gem data, not a name list) is left out of the pickers:
    # Contagion with clear supports used to take Expanse (8 s cooldown), with or without a tier cap
    from pob_agent import leveling as L
    with Engine() as eng:
        assert eng.call("cooldown_supports")["names"] == COOLDOWN_SUPPORTS
        res = eng.call("leveling_probe", skills=["Contagion"], **L.stage_params("act1+clearsup", "Witch"))["results"][0]
        untiered = {k: v for k, v in L.stage_params("act1+clearsup", "Witch").items() if k != "maxSupportTier"}
        res2 = eng.call("leveling_probe", skills=["Contagion"], **untiered)["results"][0]
    for r in (res, res2):
        assert r["supports"] and not {s["name"] for s in r["supports"]} & set(COOLDOWN_SUPPORTS)


def test_checkup_never_recommends_a_cooldown_support():
    # Profane Ritual (1.3 s duration) at level 14 used to be advised Expanse for clearing packs
    from pob_agent import checkup
    sel = ("for cid, c in pairs(build.spec.tree.classes) do if c.name == 'Witch' then build.spec:SelectClass(cid) end end "
           "recalc() return true")
    with Engine() as eng:
        eng.call("new", level=14)
        eng.call("eval", code=sel)
        eng.call("paste_skill", text="Essence Drain 5/0  1\n", main=True)
        eng.call("paste_skill", text="Profane Ritual 5/0  1\n", main=False)
        eng.call("checkup_prepare")
        g = next(x for x in eng.call("checkup_groups")["groups"] if x["skill"] == "Profane Ritual")
        sc = checkup.support_checks(eng, g["index"], 1)
    for mode in ("boss", "clear"):
        assert not {p["name"] for p in sc[mode]["best"]} & set(COOLDOWN_SUPPORTS)


def test_vine_arrow_counts_hit_ailment_once():
    # Vine Arrow act1 (Ranger, Poison I + Bleed I): Impact's combined DPS 20.64 already holds the hit's poison/bleed
    # (5.52); the Vines set's TotalDotDPS 21.50 repeats it on top of its own DoT 15.98. Total = PoB's Vines combined.
    from pob_agent import leveling as L
    r = {"skill": "Vine Arrow", "types": ["Attack", "Projectile", "DamageOverTime"], "monsterLife": 60,
         "variants": [{"label": "Impact", "dps": 20.6397, "CombinedDPS": 20.6397, "TotalDPS": 15.1199, "TotalDot": 0,
                       "TotalDotDPS": 5.5199, "Speed": 1.35},
                      {"label": "Vines", "dps": 36.6231, "CombinedDPS": 36.6231, "TotalDPS": 15.1199,
                       "TotalDot": 15.9833, "TotalDotDPS": 21.5032, "Duration": 8.019, "Speed": 1.35}]}
    m = L.metrics(r, {**L.DEFAULT, "loadout": False})
    assert abs(m["st"] - 36.6231) < 0.01
    assert abs(m["dot"] - 21.5032) < 0.01   # the dot field (pairs, G8) is unchanged


def test_vine_arrow_hit_and_vines_reach_their_own_targets():
    # Ranger act1 Vine Arrow: Impact's 0.8 m hit reaches ~1 monster, the Vines' 2.4 m area ~5.4. Clear is the better
    # of both sets on the narrow reach (A') and the Vines alone on their own reach with their own DoT (B); the old
    # model credited the hit with the Vines' 5.4 targets. Single-target DPS does not change.
    from pob_agent import leveling as L
    imp = {"label": "Impact", "dps": 19.4075, "CombinedDPS": 19.4075, "TotalDot": 0, "TotalDotDPS": 0.0351,
           "AverageDamage": 14.3499, "Duration": 10.428, "Speed": 1.35, "AreaOfEffectRadiusMetres": 0.8,
           "ProjectileCount": 1, "PierceCount": 0.15, "ChainMax": 0}
    vin = {**imp, "label": "Vines", "dps": 35.3908, "CombinedDPS": 35.3908, "TotalDot": 15.9833, "TotalDotDPS": 16.0185,
           "AreaOfEffectRadiusMetres": 2.4}
    r = {"skill": "Vine Arrow", "types": ["Area", "Attack", "Chaos", "DamageOverTime", "Duration", "Projectile"],
         "monsterLife": 89, "variants": [imp, vin]}
    cfg = {**L.DEFAULT, "loadout": False}
    off = {**cfg, "split_targets": False}
    new, old = L.metrics(r, cfg), L.metrics(r, off)
    a = L.metrics({**r, "variants": [imp, {**vin, "AreaOfEffectRadiusMetres": 0.8}]}, off)   # both sets, narrow reach
    b = L.metrics({**r, "variants": [{**vin, "TotalDotDPS": vin["TotalDot"]}]}, off)         # Vines alone
    assert abs(b["st"] - 15.9833) < 1e-9
    assert abs(new["clear"] - max(a["clear"], b["clear"])) < 1e-12
    assert abs(new["clear"] - 0.4436) < 1e-3 and abs(old["clear"] - 0.7344) < 1e-3
    assert new["st"] == old["st"] and new["dot"] == old["dot"]
    assert new["targets"] == b["targets"] and a["targets"] < b["targets"]   # B wins: the Vines' own reach


def test_leveling_rows_show_their_supports(capsys):
    # a ranked row says which supports its numbers assume (solo: the scored collection's set; pair: each member's)
    from pob_agent import leveling as L, cli
    rows = L.rank("act1,act1+clearsup", "Witch")
    solo = next(m for m in rows if not m.get("members"))
    pair = next(m for m in rows if m.get("members"))
    assert isinstance(solo["supports"], list) and set(pair["supports"]) == set(pair["members"])
    # a row won by the clear-support collection shows that collection's set
    plain, clear = L.load("act1", "Witch"), L.load("act1+clearsup", "Witch")
    names = lambda r: [x["name"] for x in r.get("supports") or []]
    won = [m for m in rows if not m.get("members") and m["skill"] in plain and m["skill"] in clear
           and names(plain[m["skill"]]) != names(clear[m["skill"]]) and m["supports"] == names(clear[m["skill"]])]
    assert won
    cli.render_leveling(rows, "Witch", "act1,act1+clearsup", 5)
    assert "supports: " in capsys.readouterr().out


def test_leveling_ascendancy_sees_node_implied_config():
    # Eldritch Empowerment's 30% more needs PoB's "Are you Sacrificing?" box; the node implies it
    from pob_agent import leveling as L
    with Engine() as eng:
        res = eng.call("leveling_probe", skills=["Essence Drain"], **L.stage_params("asc1+asc-Lich", "Witch"))
    assert res["results"][0]["ascNodes"] == ["Eldritch Empowerment"]


def test_leveling_mix_lets_boss_skill_finish_rares():
    from pob_agent import leveling as L
    cfg = {**L.DEFAULT, "mix": {"white": (1.0, 0.5), "rare": (8.0, 0.5, "leader")}, "travel": 0.0}
    # clear skill alone: rare pack takes 8x as long as a white pack
    assert abs(L.mix_clear(6, lambda m: m * 1.0, cfg, life=100) - 6 / 4.5) < 1e-9
    # with a 400 DPS boss skill: clear the whites (1s), then 800 life / 400 DPS on the rare
    assert abs(L.mix_clear(6, lambda m: m * 1.0, {**cfg, "boss_dps": 400}, life=100) - 3.0) < 1e-9


def test_leveling_boss_skill_takes_at_least_one_use():
    # a tough monster finished with the boss skill costs at least one use of it, in leader and plain packs
    from pob_agent import leveling as L
    cfg = {**L.DEFAULT, "mix": {"magic": (2.0, 0.5), "rare": (8.0, 0.5, "leader")}, "travel": 0.0, "boss_dps": 1000}
    slow = lambda m: m * 10.0
    free = L.mix_clear(6, slow, cfg, life=100)
    floored = L.mix_clear(6, slow, {**cfg, "boss_speed": 0.5}, life=100)   # one use = 2 s > 0.2 s / 0.8 s of DPS
    assert abs(free - 12 / (6 * 0.2 + 10 + 0.8)) < 1e-9
    assert abs(floored - 12 / (6 * 2.0 + 10 + 2.0)) < 1e-9
    assert L.mix_clear(6, slow, {**cfg, "boss_speed": 0}, life=100) == free


def test_leveling_boss_skill_is_in_family():
    # the loadout's boss skill is the best one the class is scored as using: off-family rows (x0.25 in the ranking)
    # do not finish rares at full DPS; with the off-family penalty switched off the top row is used as before
    from pob_agent import leveling as L
    top = L.rank_boss("asc1,asc1+clearsup", "Huntress", {**L.DEFAULT, "loadout": False})
    assert top[0].get("off_weapon")
    b = L.boss_row(top, L.DEFAULT)
    assert not b["off_weapon"] and b is next(m for m in top if not m.get("off_weapon"))
    assert L.boss_row(top, {**L.DEFAULT, "off_weapon_factor": 1.0}) is top[0]
    # rank() hands that row's DPS and raw use rate to the clear model
    seen = []
    orig = L.mix_clear
    L.mix_clear = lambda t, p, cfg, life=0.0: (seen.append((cfg.get("boss_dps"), cfg.get("boss_speed"))), orig(t, p, cfg, life))[1]
    try:
        L.rank("asc1,asc1+clearsup", "Huntress")
    finally:
        L.mix_clear = orig
    used = {x for x in seen if x[0]}   # rank_boss's own scoring runs without a boss skill
    assert used == {(b["st"], b["speed0"])}


def test_blank_item_uses_the_base_pob_reports():
    # a Magic item's raw text has no base line (the old third-line read took "Crafted: true" and PoB errored); the
    # blank is built from PoB's base, and an item with no known base cannot be blanked
    from pob_agent import trade
    raw = "Rarity: MAGIC\nProfessor's Pearlescent Amulet of the Mage\nCrafted: true\nItem Level: 80\n"
    assert trade.blank_item(raw, "Pearlescent Amulet") == "Rarity: RARE\nBlank\nPearlescent Amulet"
    assert trade.blank_item(raw, None) is None


def test_dps_falls_back_to_the_minion_only_without_player_dps():
    # a minion main skill keeps CombinedDPS/FullDPS/TotalDPS at 0 in PoB; its DPS is the minion's (per minion)
    from pob_agent.analysis import dps_of
    assert dps_of({"CombinedDPS": 0, "FullDPS": 0, "TotalDPS": 0, "MinionDPS": 29190.4}) == 29190.4
    assert dps_of({"CombinedDPS": 120.0, "MinionDPS": 29190.4}) == 120.0


def test_summary_label_tolerates_non_numeric_stats(capsys):
    # PoB can report NaN/inf, which the engine passes on as strings; the summary still prints and labels the source
    from pob_agent import cli
    for stats, label in (({"CombinedDPS": "inf", "TotalDPS": 0}, "main skill"),
                         ({"CombinedDPS": 0, "FullDPS": 0, "TotalDPS": 0, "MinionDPS": 500.0}, "minion DPS, per minion")):
        cli.render_summary({"stats": stats, "mainSkill": {"name": "X", "supports": []}, "level": 1}, "test")
        assert label in capsys.readouterr().out


def test_trade_query_lists_the_heaviest_weights_in_the_link():
    # the printed weights are the link's own filters, heaviest first (PoB orders its list by mean stat change)
    from pob_agent import trade
    with Engine() as eng:
        eng.call("load", **sources.resolve(str(BUILD)))
        q = eng.call("trade_query", slot="Ring 1", league="Standard", statWeights=trade.DEFAULT_WEIGHTS, topWeights=12)
    w = [x["weight"] for x in q["weights"]]
    body = q["query"].get("query", q["query"])
    filt = sorted((f["value"]["weight"] for g in body["stats"] for f in g["filters"]
                   if (f.get("value") or {}).get("weight") is not None), reverse=True)
    assert w and w == sorted(w, reverse=True) and w == filt[:len(w)]


def test_checkup_text_agrees_with_its_numbers(capsys):
    # the support verdict follows the measured multiplier, a support the section recommends gets no swap advice,
    # a boss gain stays visible when the two sets merge, a gem above the stage cap is not "the highest", and the
    # support tier header stops at the last tier there is
    from pob_agent import cli, checkup, switch
    assert checkup.max_level_for(97, switch.SUPPORT_DROP) == switch.SUPPORT_DROP[-1][0]
    g = {"skill": "Spark", "level": 20, "value": 100.0, "source": None, "levels": {"rows": []},
         "supports": [{"name": "Multishot I", "mult": 0.6}, {"name": "Chain I", "mult": 1.0}, {"name": "Pierce I", "mult": 0.9}],
         "support_checks": {"boss": {"best": [{"name": "Pierce I"}, {"name": "Fire Attunement"}], "current": ["Multishot I"],
                                     "mult": 1.66},
                            "clear": {"best": [{"name": "Pierce I"}, {"name": "Fire Attunement"}], "current": ["Multishot I"],
                                      "mult": 1.30, "dpsMult": 1.1}}}
    r = {"level": 13, "gem_max": 4, "support_tier": 1, "groups": [g], "main": [g], "minions": {}}
    cli.render_checkup(r)
    out = capsys.readouterr().out
    assert "| Spark | Multishot I | x0.60 | costs single-target DPS" in out
    assert "| Spark | Chain I | x1.00 | no effect on this skill in PoB" in out
    assert "| Spark | Pierce I |" not in out                # recommended in this section: no dead-support row
    assert "x1.66" in out                                 # boss gain printed on the merged line
    assert "at cap" not in out and "above cap 4" in out
    # one objective already best, the other recommending a change: no "no better support found"
    g2 = {**g, "support_checks": {"boss": {**g["support_checks"]["boss"]},
                                  "clear": {"best": [], "current": ["Multishot I"], "unscored": True}}}
    cli.render_checkup({**r, "groups": [g2], "main": [g2]})
    out = capsys.readouterr().out
    assert "no better support found" not in out and "| Spark | Multishot I | x0.60 | costs single-target DPS; swap it" in out


def _checkup_dict(level=41, chaos_missing=75):
    """A synthetic check-up result: one main skill with a x1.20 boss set and a x4.00 clear set, seven passives above
    the report band, an ascendancy notable, resistances below cap."""
    sc_boss = {"best": [{"name": "Pierce I"}, {"name": "Minion Pact I", "elsewhere": True}], "current": ["Chain I", "Pierce I"],
               "mult": 1.2, "own": {"best": [{"name": "Pierce I"}, {"name": "Unleash"}], "mult": 1.05}}
    sc_clear = {"best": [{"name": "Pierce I"}, {"name": "Multishot II"}], "current": ["Chain I", "Pierce I"],
                "mult": 4.0, "dpsMult": 0.6}
    g = {"index": 1, "skill": "Spark", "level": 8, "value": 1436326.0, "source": None,
         "levels": {"rows": [{"level": 9, "value": 1500000.0, "mult": 1.0443}]},
         "supports": [{"name": "Chain I", "mult": 1.0}, {"name": "Pierce I", "mult": 1.3}],
         "support_checks": {"boss": sc_boss, "clear": sc_clear}}
    passives = [{"name": f"Node {c}", "id": i, "cost": 2, "mult": 1.0 + 0.1 * (7 - i), "life": 0, "es": 0, "res": 0,
                 "regen": 0} for i, c in enumerate("ABCDEFG")]
    sustain = {"cost_ps": 40.0, "net": 60.0, "low": 0.35, "state": "sustained", "life_cost_ps": 0}
    nx = {"noise": 0.001, "passives": passives, "jewels": [], "ascendancyName": "Lich", "ascUsed": 2, "ascMax": 8,
          "sustain": sustain, "ascendancy": [{"name": "Conduit", "cost": 2, "mult": 1.15, "life": 0, "es": 0,
                                               "res": 0, "regen": -2.0, "sustain": dict(sustain)}]}
    th = {"resists": {"Fire": {"value": -29, "missing": 104}, "Cold": {"value": 75, "missing": 0},
                      "Lightning": {"value": 75, "missing": 0},
                      "Chaos": {"value": 75 - chaos_missing, "missing": chaos_missing}}}
    return {"level": level, "gem_max": 10, "support_tier": 3, "groups": [g], "main": [g], "minions": {},
            "next": nx, "thresholds": th, "tree": {"allocated": level - 1, "nodes": []}}


def _section(out, head):
    return out.split(head, 1)[1].split("\n### ", 1)[0]


def test_checkup_do_now_groups_by_measure(capsys):
    # value rows (supports, gem level, up to 5 passives, ascendancy) are ranked by gain inside their own measure; the
    # clear-speed row comes after them with its single-target cost, never ranked with them
    from pob_agent import cli
    cli.render_checkup(_checkup_dict())
    out = capsys.readouterr().out
    rows = [ln for ln in _section(out, "### Do now").splitlines() if ln.startswith("| ") and "measure" not in ln]
    measures = [ln.split(" | ")[0][2:] for ln in rows]
    assert measures == ["Spark value"] * 8 + ["Spark clear speed (estimate)"], measures
    gains = [float(ln.split(" | ")[3][1:]) for ln in rows[:8]]
    assert gains == sorted(gains, reverse=True)
    assert sum("passive: " in ln for ln in rows) == 5 and "passive: Node F" not in out.split("### Skills")[0]
    assert "| Spark value | supports: Chain I -> Minion Pact I* | gem swap | x1.20 | x1.05 without the borrowed support |" in rows
    assert rows[-1].endswith("| gem swap | x4.00 | single-target x0.60 |")
    assert "| Spark value | ascendancy: Conduit | next trial, 2 pts | x1.15 | — |" in rows
    assert "| Spark value | gem level 9 | uncut gem level 9 | x1.04 | — |" in rows


def test_checkup_one_multiplier_format_and_notes_once(capsys):
    import re
    from pob_agent import cli
    assert (cli.fx(1.003), cli.fx(0.997), cli.fx(1.0004), cli.fx(None), cli.fx(1.25)) == ("<x1.01", ">x0.99", "x1.00", "—", "x1.25")
    cli.render_checkup(_checkup_dict())
    out = capsys.readouterr().out
    assert all(len(m.split(".")[1]) == 2 for m in re.findall(r"x\d+\.\d+", out))
    assert "1.44M" in out and "1436326" not in out             # values through fmt()
    body, notes = out.split("### Notes")
    keys = re.findall(r"^- \[(\w+)\]", notes, re.M)
    assert len(keys) == len(set(keys)) and set(re.findall(r"\[(\w+)\]", body)) <= set(keys)
    width = None
    for line in body.splitlines():
        if not line.startswith("|"):
            width = None
        elif not line.startswith("|---"):
            cells = line.strip("|").split(" | ")
            width = width or len(cells)
            assert len(cells) == width and all(c.strip() for c in cells), line


def test_checkup_next_passives_table_has_five_damage_rows(capsys):
    from pob_agent import cli
    cli.render_checkup(_checkup_dict())
    out = capsys.readouterr().out
    rows = [ln for ln in _section(out, "### Next passives").splitlines() if ln.startswith("| main skill |")]
    assert len(rows) == 5 and rows[0] == "| main skill | Node A | 2 | x1.70 | +35.0%/pt | — | — | — | — |"


def test_checkup_chaos_resistance_flag_starts_at_65(capsys):
    # campaign characters (below level 65) are not flagged for chaos resistance; the Sustain row still shows it
    from pob_agent import cli
    cli.render_checkup(_checkup_dict(level=64))
    out = capsys.readouterr().out
    assert "- Resistances below cap: Fire -29%." in out and "Chaos 0%" in _section(out, "### Sustain and defences")
    cli.render_checkup(_checkup_dict(level=65))
    out = capsys.readouterr().out
    assert "- Resistances below cap: Fire -29%, Chaos 0%." in out


def test_trade_query_top_mods_are_droppable_affixes_in_order():
    # topMods: distinct trade texts, ordered by meanStatDiff then text, explicit affixes only; without topMods the
    # result has no mods key
    from pob_agent import trade
    main = "return build.mainSocketGroup"
    with Engine() as eng:
        eng.call("load", **sources.resolve(str(BUILD)))
        eng.call("checkup_prepare")
        before = (eng.call("eval", code=main), eng.call("stats"), eng.call("checkup_groups"))
        plain = eng.call("trade_query", slot="Gloves", statWeights=trade.DEFAULT_WEIGHTS)
        groups = before[2]["groups"]
        for g in (groups[-1]["index"], groups[0]["index"]):   # pinned to another group, then to the first: restored
            q = eng.call("trade_query", slot="Gloves", statWeights=trade.DEFAULT_WEIGHTS, includeRunes=False,
                         includeCorrupted=False, topMods=8, group=g)
        after = (eng.call("eval", code=main), eng.call("stats"), eng.call("checkup_groups"))
    assert before == after
    assert "mods" not in plain
    mods = q["mods"]
    assert len(mods) >= 5 and len({m["text"] for m in mods}) == len(mods)
    for a, b in zip(mods, mods[1:]):
        assert a["meanStatDiff"] > b["meanStatDiff"] or (a["meanStatDiff"] == b["meanStatDiff"] and a["text"] <= b["text"])
    assert all(m["id"].startswith("explicit.") for m in mods)
    assert not any(m["id"].startswith(("implicit.", "rune.", "enchant.")) for m in mods)


def test_checkup_keeps_the_skill_behind_a_meta_gem():
    # a group whose skill sits behind a totem or meta gem is checked as that skill, and the check-up's what-ifs
    # leave the group's selected skill in place (it used to fall back to the totem and measure 0 from then on)
    sel = ("for cid, c in pairs(build.spec.tree.classes) do if c.name == 'Sorceress' then build.spec:SelectClass(cid) end end "
           "recalc() return true")
    fp = ("recalc() local g = build.skillsTab.socketGroupList[build.mainSocketGroup] "
          "local ms = build.calcsTab.mainEnv.player.mainSkill return {g.mainActiveSkill, ms.activeEffect.grantedEffect.name}")
    with Engine() as eng:
        eng.call("new", level=40)
        eng.call("eval", code=sel)
        eng.call("paste_skill", text="Spell Totem 5/0  1\nArc 10/0  1\n", main=True)
        eng.call("eval", code="build.skillsTab.socketGroupList[1].mainActiveSkill = 2 recalc() return true")
        before = eng.call("eval", code=fp)
        eng.call("checkup_prepare")
        g = eng.call("checkup_groups")["groups"][0]
        rows = eng.call("checkup_probe_sets", group=g["index"], sets=[None, []])["rows"]
        sc = eng.call("checkup_supports", group=g["index"], objective="boss", maxSupportTier=2)
        after = eng.call("eval", code=fp)
    assert before == after == [2, "Arc"] and g["skill"] == "Arc" and sc["bare"] > 0
    assert all(r["skill"] == "Arc" for r in rows)


def test_checkup_keeps_a_support_that_grants_the_selected_skill():
    # Impending Doom grants Doom Blast; with Doom Blast selected, a what-if that dropped the support used to move the
    # selection onto Despair and measure 0
    sel = ("for cid, c in pairs(build.spec.tree.classes) do if c.name == 'Witch' then build.spec:SelectClass(cid) end end "
           "recalc() return true")
    fp = ("recalc() local g = build.skillsTab.socketGroupList[build.mainSocketGroup] "
          "return {g.mainActiveSkill, g.displaySkillList[g.mainActiveSkill].activeEffect.grantedEffect.name}")
    with Engine() as eng:
        eng.call("new", level=60)
        eng.call("eval", code=sel)
        eng.call("paste_skill", text="Despair 15/0  1\nImpending Doom 1/0  1\nSpell Cascade 1/0  1\n", main=True)
        eng.call("eval", code="build.skillsTab.socketGroupList[1].mainActiveSkill = 2 recalc() return true")
        eng.call("checkup_prepare")
        g = eng.call("checkup_groups")["groups"][0]
        sc = eng.call("checkup_supports", group=g["index"], objective="boss", maxSupportTier=3)
        after = eng.call("eval", code=fp)
    assert after == [2, "Doom Blast"] and sc["bare"] > 0 and "Impending Doom" not in sc["current"]


def test_headroom_reports_a_slot_it_cannot_blank():
    # a slot with no base PoB knows is listed with a note, not dropped
    from pob_agent import trade

    class NoBase:
        def __init__(self, eng):
            self.eng = eng

        def call(self, cmd, **kw):
            r = self.eng.call(cmd, **kw)
            if cmd == "items":
                for it in r["items"]:
                    if it["slot"] == "Helmet":
                        it["base"] = None
            return r
    with Engine() as eng:
        eng.call("load", **sources.resolve(str(BUILD)))
        rows = trade.slot_headroom(NoBase(eng))
    helm = next(r for r in rows if r["slot"] == "Helmet")
    assert helm.get("note") and helm["breaks"] == []


def test_leveling_answer_key_is_frozen():
    # the backtest answer key was frozen on 2026-11-24 (research note §6); changing it invalidates every
    # number logged against it. Add new labels as a separate held-out set instead.
    import hashlib
    import json
    from pob_agent import leveling as L
    key = json.dumps([L.BACKTEST, L.NEGATIVE], sort_keys=True).encode()
    assert hashlib.sha256(key).hexdigest()[:16] == "d84c824a64111d4b"


def test_leveling_heldout_keys_are_frozen():
    # held-out keys frozen 2026-11-24 before any run against them; scored once, never tuned on
    import hashlib
    import json
    from pob_agent import leveling as L
    key = json.dumps([L.HELDOUT_SOURCE2, L.HELDOUT_ASC1], sort_keys=True).encode()
    assert hashlib.sha256(key).hexdigest()[:16] == "e5d178a626d061a2"
    # asc2 key frozen 2026-11-24 before its collection run
    assert hashlib.sha256(json.dumps(L.HELDOUT_ASC2, sort_keys=True).encode()).hexdigest()[:16] == "f9f8b4ba4863bac1"


def test_checkpoints_spend_every_point_notable_first():
    from pob_agent import checkpoints
    r = checkpoints.run("Essence Drain", "Witch", ascendancy="Lich")
    a = r["ascendancies"][0]
    assert a["ascendancy"] == "Lich"
    assert [s["spent"] for s in a["steps"]] == [2, 4, 6, 8]
    # the sacrifice notable is the first pick for a chaos DoT spell (it matched the guides' order)
    assert a["steps"][0]["nodes"] == ["Eldritch Empowerment"]
    assert a["lift"] > 1.2


def test_checkpoint_dps_counts_the_dot_set():
    # checkpoint DPS is the first stat set plus the DoT-only set (plain DPS, no kill factor); for Essence Drain the
    # first set alone is only the projectile hit
    from pob_agent import leveling as L
    p = L.stage_params("asc2", "Witch")
    with Engine() as eng:
        a = eng.call("ascendancy_checkpoints", skill="Essence Drain", **{**p, "class": "Witch",
                     "ascendancies": {"Lich": True}, "steps": [2]})["ascendancies"][0]
        first = eng.call("eval", code="return skillDps()")
    assert a["steps"][0]["dps"] > first * 1.2


def test_checkpoint_key_is_frozen():
    # frozen 2026-11-25 before any run against it; scored once, never tuned on
    import hashlib
    import json
    from pob_agent.checkpoint_key import CHECKPOINT_KEY
    assert hashlib.sha256(json.dumps(CHECKPOINT_KEY, sort_keys=True).encode()).hexdigest()[:16] == "2d9c440b795f9b00"


def test_switch_gates_from_game_data():
    from pob_agent import switch
    assert switch.level_for_tier(5) == 15 and switch.level_for_tier(10) == 37
    r = switch.gates("Shield Wall", "Warrior")
    assert r["act"] == "Act 2"
    w = next(g for g in r["gates"] if g["gate"] == "weapon")
    assert w["off_class"] and "Armoured Shield" in w["detail"]
    t = switch.gates("Supporting Fire", "Mercenary")
    assert t["gates"][0]["node"] == "Unleash Hell!"


def test_gate_diff_same_checkout_is_empty_and_respec_gold():
    from pob_agent import bridge, patchdiff
    from pob_agent.engine import POB_SRC
    r = patchdiff.gate_diff(POB_SRC, POB_SRC, ["Essence Drain", "Shield Wall"])
    assert r["changes"] == []
    assert bridge.respec_gold(1) == 15 and bridge.respec_gold(24) == 344


# --- check-up "next steps": next passives, next ascendancy trial, mana sustain, empty jewel sockets ---

LICH_SYNTH = '''
for cid, c in pairs(build.spec.tree.classes) do if c.name == 'Witch' then build.spec:SelectClass(cid)
  for aid, a in pairs(c.classes) do if a.name == 'Lich' then build.spec:SelectAscendClass(aid) end end end end
local ee for _, n in pairs(build.spec.nodes) do if n.dn == 'Eldritch Empowerment' then ee = n end end
build.spec:AllocNode(ee) build.spec:BuildAllDependsAndPaths()
recalc()
return true
'''


def _lich_synth(eng):
    """Level-30 Lich with only Eldritch Empowerment (2 points) and a gearless Essence Drain: a mana deficit."""
    eng.call("new", level=30)
    eng.call("eval", code=LICH_SYNTH)
    eng.call("paste_skill", text="Essence Drain 8/0  1\nSwift Affliction I 1/0  1\nMinion Pact I 1/0  1\n", main=True)
    groups = eng.call("checkup_groups")["groups"]
    return sorted(groups, key=lambda g: -g["value"])[0]["index"]


def test_checkup_next_passive_row_matches_real_allocation():
    with Engine() as eng:
        gi = _lich_synth(eng)
        before = eng.call("checkup_next", group=gi)
        row = next(p for p in before["passives"] if p["name"] == "Raw Destruction")
        es0 = eng.call("eval", code="return build.calcsTab.mainOutput.EnergyShield or 0")
        eng.call("eval", code="local n for _, x in pairs(build.spec.nodes) do if x.dn == 'Raw Destruction' then n = x end end "
                              "build.spec:AllocNode(n) build.spec:BuildAllDependsAndPaths() recalc() return true")
        after = eng.call("checkup_next", group=gi)
        es1 = eng.call("eval", code="return build.calcsTab.mainOutput.EnergyShield or 0")
        assert abs(after["base"] - before["base"] * row["mult"]) <= 1e-6 * after["base"]
        assert abs((es1 - es0) - row["es"]) < 0.5
        assert row["cost"] == 5 and row["mult"] > 1.2


def test_checkup_next_ascendancy_rows_for_the_next_trial():
    with Engine() as eng:
        gi = _lich_synth(eng)
        n = eng.call("checkup_next", group=gi)
        assert n["ascUsed"] == 2
        assert sorted(a["name"] for a in n["ascendancy"]) == [
            "Crystalline Phylactery", "Necromantic Conduit", "Price of Power", "Rupture the Soul", "Soulless Form"]
        conduit = next(a for a in n["ascendancy"] if a["name"] == "Necromantic Conduit")
        assert conduit["mult"] > 1.05
    with Engine() as eng:  # the example build has all 8 points spent: nothing is listed for a next trial
        eng.call("load", **sources.resolve(str(BUILD)))
        groups = eng.call("checkup_groups")["groups"]
        n = eng.call("checkup_next", group=sorted(groups, key=lambda g: -g["value"])[0]["index"])
        assert n["ascUsed"] == 8 and n["ascendancy"] == []


def test_checkup_next_mana_sustain():
    with Engine() as eng:
        gi = _lich_synth(eng)
        n = eng.call("checkup_next", group=gi)
        m = n["sustain"]
        assert m["state"] == "drains" and m["low"] == 0.35
        assert abs(m["secs_to_low"] - (m["unreserved"] - 0.35 * m["mana"]) / (m["cost_ps"] - m["net"])) < 1e-9
        out = eng.call("eval", code="local o = build.calcsTab.mainOutput return {o.ManaPerSecondCost, o.ManaRegenRecovery}")
        assert abs(m["cost_ps"] - out[0]) < 1e-9 and abs(m["net"] - out[1]) < 1e-9
        rows = {a["name"]: a["sustain"] for a in n["ascendancy"]}
        assert rows["Necromantic Conduit"]["secs_to_low"] < m["secs_to_low"]  # loses 5% of maximum mana per second
        assert rows["Soulless Form"]["secs_to_low"] > m["secs_to_low"]        # regenerates mana from life
    with Engine() as eng:  # a summon has no mana cost per second
        eng.call("new", level=30)
        eng.call("paste_skill", text="Skeletal Warrior 8/0  1\n", main=True)
        n = eng.call("checkup_next", group=eng.call("checkup_groups")["groups"][0]["index"])
        assert n["sustain"]["state"] == "no_cost" and "secs_to_low" not in n["sustain"]


def test_checkup_next_lists_empty_jewel_sockets():
    with Engine() as eng:
        eng.call("load", **sources.resolve(str(BUILD)))
        groups = eng.call("checkup_groups")["groups"]
        gi = sorted(groups, key=lambda g: -g["value"])[0]["index"]
        filled = eng.call("eval", code="local t = {} for id, n in pairs(build.spec.allocNodes) do if n.type == 'Socket' "
                                        "and build.itemsTab.sockets[id].selItemId ~= 0 then t[#t + 1] = id end end "
                                        "table.sort(t) return t")
        assert filled and eng.call("checkup_next", group=gi)["jewels"] == []
        eng.call("eval", code="build.itemsTab.sockets[req.sock].selItemId = 0 build.buildFlag = true recalc() return true",
                 sock=filled[0])
        assert [j["id"] for j in eng.call("checkup_next", group=gi)["jewels"]] == [filled[0]]


def test_checkup_gear_blocks_the_offhand_behind_a_two_hander():
    # an empty off-hand behind a two-handed mace takes no item by PoB's own slot rule: reported blocked, not measured
    # with one-hand affixes; the equipped slot is labelled with its base type
    from pob_agent import checkup
    with Engine() as eng:
        eng.call("new", level=30)
        mace = eng.call("eval", code="local t = {} for n, b in pairs(data.itemBases) do if b.type == 'Two Hand Mace' "
                                     "and not b.hidden then t[#t + 1] = n end end table.sort(t) return t[1]")
        eng.call("add_item", raw=f"Rarity: RARE\nTest\n{mace}")
        rows = {r["slot"]: r for r in checkup.gear(eng, None)}
    assert rows["Weapon 2"]["blocked"] and rows["Weapon 2"]["mods"] == []
    assert rows["Weapon 1"]["type"] == "Two Hand Mace" and rows["Weapon 1"]["mods"]


def test_checkup_gear_basis_and_errors():
    # PoB's generator weighs FullDPS whenever the calculator reports it (0 included: then no DPS term), else the main
    # skill; engine errors lose their Lua source position, so no local path reaches the report
    from pob_agent import checkup, cli
    assert checkup.dps_basis(None, 120.0) == ("main", 120.0)
    assert checkup.dps_basis(0, 120.0) == ("main", 0.0)
    assert checkup.dps_basis(5000.0, 120.0) == ("full", 5000.0)
    assert checkup.clean_error("trade_query failed: /home/u/pob/harness/lua/rpc.lua:415: unknown slot X") == "unknown slot X"
    r = _checkup_dict()
    r["minions"] = {"assumedOne": True, "minionSkills": ["Skeletal Warrior Minion"]}
    r["gear"] = [{"slot": "Weapon 1", "type": "Wand", "mods": [{"text": "# to Strength", "meanStatDiff": 3.0}]},
                 {"slot": "Weapon 2", "empty": True, "blocked": True, "mods": []}]
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.render_checkup(r)
    out = buf.getvalue()
    assert "| Weapon 1 (Wand) | # to Strength (few affixes on this base move Spark DPS or EHP;" in out
    assert "| Weapon 2 (empty) | blocked by the two-handed main hand |" in out
    assert "One minion assumed [minion]." in out
