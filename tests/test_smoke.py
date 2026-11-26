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
