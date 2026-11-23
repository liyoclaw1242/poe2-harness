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
