"""checkup --guide (item S): five sections, bases from data.itemBases, zh-TW names, jewel bases, the plain report unchanged.

Builds: the sunder example and synthetic in-engine builds only."""
import contextlib
import io
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pob_agent import sources  # noqa: E402
from pob_agent.engine import Engine, POB_SRC  # noqa: E402
from test_smoke import BUILD, _WITCH, _checkup_dict  # noqa: E402

HEADINGS = ["### 1. Skills and supports", "### 2. Passives", "### 3. Gear", "### 4. Jewels", "### 5. Summary"]
CJK = re.compile(r"[　-鿿豈-﫿＀-￯]")
SLOT_TYPE = {"Helmet": "Helmet", "Body Armour": "Body Armour", "Gloves": "Gloves", "Boots": "Boots", "Amulet": "Amulet",
             "Ring 1": "Ring", "Ring 2": "Ring", "Belt": "Belt"}
ARMOUR = {"Helmet", "Body Armour", "Gloves", "Boots", "Shield", "Focus", "Buckler"}
JEWELRY = {"Amulet", "Ring", "Belt"}


def _cli(*argv):
    from pob_agent import cli
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.main(list(argv))
    return buf.getvalue()


def _render(fn, r):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(r)
    return buf.getvalue()


def _sections(text):
    """Section number -> its text (the heading line excluded)."""
    out = {}
    for i, h in enumerate(HEADINGS, 1):
        out[i] = text.split(h, 1)[1].split("\n### ", 1)[0]
    return out


# --- synthetic builds --------------------------------------------------------------------------------------------

WITCH_ITEMS = ["Rarity: RARE\nT\nTwig Circlet", "Rarity: RARE\nT\nTattered Robe", "Rarity: RARE\nT\nGauze Wraps",
               "Rarity: RARE\nT\nStraw Sandals", "Rarity: RARE\nT\nCrimson Amulet", "Rarity: RARE\nT\nIron Ring",
               "Rarity: UNIQUE\nTest Unique\nLazuli Ring"]
ALLOC_SOCKET = ("build.spec:BuildAllDependsAndPaths() local best for id, n in pairs(build.spec.nodes) do "
                "if n.type == 'Socket' and n.path and #n.path > 0 and not n.ascendancyName then "
                "if not best or #n.path < #best.path or (#n.path == #best.path and id < best.id) then best = n end end end "
                "build.spec:AllocNode(best) build.buildFlag = true recalc() return best.id")


def _synth_witch(path):
    """Level-20 Witch with Essence Drain: rare armour in every armour slot, rare amulet and ring, a unique ring, an
    empty belt and empty weapon slots, and one allocated jewel socket with no jewel."""
    with Engine() as eng:
        eng.call("new", level=20)
        eng.call("eval", code=_WITCH)
        eng.call("paste_skill", text="Essence Drain 6/0  1\n", main=True)
        for raw in WITCH_ITEMS:
            eng.call("add_item", raw=raw)
        eng.call("eval", code=ALLOC_SOCKET)
        path.write_text(eng.call("save", xml=True)["xml"])
    return str(path)


def _two_hander(path):
    """Level-30 build holding a rare two-handed mace (an empty, blocked off-hand)."""
    with Engine() as eng:
        eng.call("new", level=30)
        eng.call("paste_skill", text="Boneshatter 6/0  1\n", main=True)
        mace = eng.call("eval", code="local t = {} for n, b in pairs(data.itemBases) do if b.type == 'Two Hand Mace' "
                                     "and not b.hidden and (b.req.level or 1) <= 5 then t[#t + 1] = n end end "
                                     "table.sort(t) return t[1]")
        eng.call("add_item", raw=f"Rarity: RARE\nTest\n{mace}")
        path.write_text(eng.call("save", xml=True)["xml"])
    return str(path)


@pytest.fixture(scope="module")
def witch(tmp_path_factory):
    from pob_agent import checkup
    b = _synth_witch(tmp_path_factory.mktemp("guide") / "witch.xml")
    r = checkup.run(b, spirit=False)
    r["guide"] = checkup.guide(b, r)
    return b, r


@pytest.fixture(scope="module")
def sunder():
    """The sunder example through the CLI: plain JSON, --guide JSON and --guide text."""
    plain = json.loads(_cli("--json", "checkup", str(BUILD), "--no-spirit"))
    guided = json.loads(_cli("--json", "checkup", str(BUILD), "--no-spirit", "--guide"))
    text = _cli("checkup", str(BUILD), "--no-spirit", "--guide")
    return plain, guided, text


# --- independent scan of the vendor base data (GS2) ---------------------------------------------------------------

def _scan_bases():
    """Data/Bases/*.lua parsed as text: type, subType, req level, defences, implicit lines, hidden. A name assigned
    twice keeps its last assignment (as PoB's loader does)."""
    out = {}
    for f in sorted((POB_SRC / "Data" / "Bases").glob("*.lua")):
        for name, body in re.findall(r'itemBases\["(.+?)"\] = \{\n(.*?)\n\}', f.read_text(encoding="utf-8"), re.S):
            sub = re.search(r'\n\tsubType = "(.*?)"', "\n" + body)
            lvl = re.search(r'\treq = \{[^}]*\blevel = (\d+)', body)
            imp = re.search(r'\timplicit = "(.*?)",\n', body + "\n")
            arm = re.search(r'\tarmour = \{(.*?)\}', body)
            defs = {k: float(v) for k, v in re.findall(r"(\w+) = ([\d.]+)", arm.group(1))} if arm else {}
            out[name] = {"type": re.search(r'\ttype = "(.*?)"', body).group(1), "subType": sub.group(1) if sub else None,
                         "req": int(lvl.group(1)) if lvl else 1, "hidden": "\thidden = true" in body,
                         "implicits": imp.group(1).split("\\n") if imp else [],
                         "def": {k: v for k, v in defs.items() if k in ("Armour", "Evasion", "EnergyShield", "Ward") and v > 0}}
    return out


def _trade_text(line):
    line = re.sub(r"\{[^}]*\}", "", line).replace("(Local)", "")
    line = re.sub(r"\([\d.-]+-[\d.-]+\)|\d+(\.\d+)?", "#", line)
    return " ".join(line.split()).lstrip("+")


def _expected_picks(slot, row, eq, scan, level):
    """Rule 3 + S-4/S-5/S-6 applied to the scan: [(name, implicits)]."""
    if row.get("blocked") or row.get("unique"):
        return []
    ty = scan[eq]["type"] if eq else SLOT_TYPE.get(slot)
    if not ty:
        return []
    cands = {n: b for n, b in scan.items() if b["type"] == ty and not b["hidden"] and b["req"] <= level + 3}
    total = lambda b: sum(b["def"].values())
    if ty in ARMOUR:
        if eq:
            e = scan[eq]
            pool = [n for n, b in cands.items() if (not e["subType"] or b["subType"] == e["subType"])
                    and set(b["def"]) == set(e["def"]) and total(b) > total(e)]
            pool = sorted(pool, key=lambda n: (-total(cands[n]), cands[n]["req"], n))[:2]
        else:   # empty: the top base of each subType, in subType order
            top = {}
            for n, b in cands.items():
                if total(b) > 0 and "Ward" not in b["def"]:
                    k = b["subType"] or ""
                    if k not in top or (-total(b), b["req"], n) < (-total(cands[top[k]]), cands[top[k]]["req"], top[k]):
                        top[k] = n
            pool = [top[k] for k in sorted(top)]
    elif ty in JEWELRY:
        ranked = [_trade_text(m["text"]) for m in row["mods"]]
        hits = []
        for n, b in cands.items():
            ranks = [ranked.index(_trade_text(x)) for x in b["implicits"] if _trade_text(x) in ranked]
            if ranks:
                hits.append((min(ranks), b["req"], n))
        pool = [n for _, _, n in sorted(hits)[:3]]
    elif eq:
        e = scan[eq]
        skill = any(x.startswith("Grants Skill:") for x in e["implicits"])
        pool = [n for n, b in cands.items() if b["req"] > e["req"] and (not e["subType"] or b["subType"] == e["subType"])
                and (not skill or b["implicits"] == e["implicits"])]
        pool = sorted(pool, key=lambda n: (-cands[n]["req"], n))[:2]
    else:
        pool = []
    return [(n, tuple(scan[n]["implicits"])) for n in pool]


def _check_bases(build, r):
    scan = _scan_bases()
    with Engine() as eng:
        eng.call("load", **sources.resolve(build))
        items = {i["slot"]: i for i in eng.call("items")["items"]}
    rows = {g["slot"]: g for g in r["gear"]}
    checked = 0
    for g in r["guide"]["gear"]:
        it = items.get(g["slot"])
        eq = it["base"] if it else None
        if g.get("equipped"):
            assert g["equipped"]["base"] == eq and g["equipped"]["reqLevel"] == scan[eq]["req"], g["slot"]
        else:
            assert eq is None or rows[g["slot"]].get("blocked"), g["slot"]
        want = _expected_picks(g["slot"], rows[g["slot"]], eq, scan, r["level"])
        assert [(p["base"], tuple(p["implicits"])) for p in g["picks"]] == want, g["slot"]
        checked += 1
    return checked


# --- GS1 ----------------------------------------------------------------------------------------------------------

def test_guide_cli_prints_five_sections_and_json_adds_one_key(sunder):
    plain, guided, text = sunder
    pos = [text.index(h) for h in HEADINGS]
    assert text.startswith("## Play guide — level 95") and pos == sorted(pos)
    assert "guide" in guided and "guide" not in plain
    assert {k: v for k, v in guided.items() if k != "guide"} == plain
    assert "### Do now" not in text and "### Notes" not in text   # the guide replaces the report


# --- GS2 / S-4 / S-5 / S-6 / S-7 ----------------------------------------------------------------------------------

def test_guide_bases_match_an_independent_scan_sunder(sunder):
    _, guided, _ = sunder
    assert _check_bases(str(BUILD), guided) == len(guided["gear"]) == 10
    rings = [g for g in guided["guide"]["gear"] if g["slot"].startswith("Ring")]
    assert any(g["picks"] for g in rings)   # S-6: at least one real implicit match on the rings


def test_guide_bases_match_an_independent_scan_witch(witch):
    b, r = witch
    gear = {g["slot"]: g for g in r["guide"]["gear"]}
    assert _check_bases(b, r) == 10
    assert gear["Ring 2"]["unique"].startswith("Test Unique") and gear["Ring 2"]["picks"] == []
    assert gear["Belt"].get("empty") and gear["Belt"]["rule"] == "jewelry"
    assert all(gear[s]["rule"] == "armour" and gear[s]["equipped"] for s in ("Helmet", "Body Armour", "Gloves", "Boots"))
    assert any(gear[s]["picks"] for s in ("Helmet", "Body Armour", "Gloves", "Boots"))
    assert gear["Weapon 1"].get("empty") and gear["Weapon 1"]["picks"] == [] and "rule" not in gear["Weapon 1"]


def test_guide_two_hander_has_no_pick_up_and_a_blocked_offhand(tmp_path):
    from pob_agent import checkup, cli
    b = _two_hander(tmp_path / "mace.xml")
    r = checkup.run(b, spirit=False, nxt=False)
    r["guide"] = checkup.guide(b, r)
    gear = {g["slot"]: g for g in r["guide"]["gear"]}
    assert gear["Weapon 1"]["rule"] == "weapon" and gear["Weapon 1"]["grantsSkill"] is False
    assert gear["Weapon 2"]["blocked"] and gear["Weapon 2"]["picks"] == []
    assert _check_bases(b, r) == 10
    text = _render(cli.render_guide, r)
    gear_txt, summary = _sections(text)[3], _sections(text)[5]
    assert "- Weapon 2: blocked by the two-handed main hand" in gear_txt
    w1 = gear_txt.split("- Weapon 1:", 1)[1].split("\n- ", 1)[0]
    assert "pick up" not in w1 and ("other bases of this type" in w1 or not gear["Weapon 1"]["picks"])
    assert "Weapon" not in summary
    # empty armour slots: one base per defence type, never ranked against each other, no Summary line
    helm = gear["Helmet"]
    assert helm.get("empty") and len(helm["picks"]) >= 2
    assert len({p["subType"] for p in helm["picks"]}) == len(helm["picks"])
    assert "Helmet" not in summary and "Boots" not in summary


def test_guide_jewelry_normaliser():
    from pob_agent import checkup
    assert checkup.norm_mod("+(20-30)% to Fire Resistance") == "#% to Fire Resistance"            # Ruby Ring
    plate = [checkup.norm_mod(x) for x in "+(140-180) to Armour\nHas (1-3) Charm Slot".split("\n")]  # Plate Belt
    assert plate == ["# to Armour", "Has # Charm Slot"]
    assert checkup.norm_mod("Adds 1 to (20-30) Lightning damage to Attacks") == "Adds # to # Lightning damage to Attacks"
    assert checkup.norm_mod("{variant:2}+12% to Cold Resistance") == "#% to Cold Resistance"
    assert checkup.norm_mod("# to maximum Energy Shield (Local)") == "# to maximum Energy Shield"
    row = {"slot": "Belt", "mods": [{"text": "# to maximum Life"}, {"text": "# to Armour"}]}
    info = {"candidates": [
        {"base": "Plate Belt", "reqLevel": 24, "type": "Belt", "implicits": ["+(140-180) to Armour", "Has (1-3) Charm Slot"]},
        {"base": "Forking Belt", "reqLevel": 32, "type": "Belt",
         "implicits": ["Adds 1 to (20-30) Lightning damage to Attacks", "Has 1 Charm Slot"]}]}
    g = checkup.guide_bases(row, info, 40)
    assert [(p["base"], p["affix"]) for p in g["picks"]] == [("Plate Belt", "# to Armour")]


def test_guide_armour_rule_ties_and_hybrids():
    # S-5: hybrids sum their defences, the defence key set must match (no Ward runeforged), ties -> lower req, name
    from pob_agent import checkup
    eq = {"base": "E", "reqLevel": 5, "type": "Helmet", "subType": "Armour/Energy Shield",
          "defences": {"armour": 20, "energyShield": 10}, "rarity": "RARE"}
    c = lambda n, lvl, d, sub="Armour/Energy Shield": {"base": n, "reqLevel": lvl, "type": "Helmet", "subType": sub,
                                                        "defences": d, "implicits": []}
    info = {"equipped": eq, "candidates": [c("A", 9, {"armour": 30, "energyShield": 10}),
                                           c("B", 8, {"armour": 35, "energyShield": 5}),
                                           c("W", 8, {"armour": 60, "energyShield": 10, "ward": 9}),
                                           c("X", 30, {"armour": 90, "energyShield": 10}),
                                           c("Z", 8, {"armour": 25, "energyShield": 5})]}
    g = checkup.guide_bases({"slot": "Helmet", "mods": []}, info, 10)
    assert [p["base"] for p in g["picks"]] == ["B", "A"]


# --- GS3 / S-3 / S-10 ---------------------------------------------------------------------------------------------

def test_guide_zh_table_keys_coverage_and_licence():
    from pob_agent import checkup
    raw = json.loads(checkup.ZH_FILE.read_text(encoding="utf-8"))
    assert set(raw) == {"_source", "_licence", "names"} and raw["_licence"].startswith("CC BY-NC-SA 3.0")
    assert not re.search(r"20\d\d|@|/Users|/home", raw["_source"])
    notice = (checkup.ZH_FILE.parent / "NOTICE").read_text(encoding="utf-8")
    assert all(s in notice for s in ("https://poe2db.tw/tw/", "2026-11-28", "CC BY-NC-SA 3.0", "Grinding Gear Games"))
    names = checkup.load_zh()
    with Engine() as eng:
        eng.call("new", level=1)
        bases = eng.call("eval", code="local t = {} for n, b in pairs(data.itemBases) do t[n] = { type = b.type, "
                                      "hidden = b.hidden or false } end return t")
    assert len(names) >= 1700 and set(names) <= set(bases)
    # every covered type resolves for at least 85% of its bases (the stripped name counts); every other type PoB has is
    # either listed as uncovered or not equippable; the table holds no base of a type outside the covered list
    types = {b["type"] for b in bases.values()}
    for ty in checkup.ZH_TYPES:
        of = [n for n, b in bases.items() if b["type"] == ty]
        assert of and sum(bool(checkup.zh_name(n, names)) for n in of) >= 0.85 * len(of), ty
    assert types - set(checkup.ZH_TYPES) <= set(checkup.ZH_UNCOVERED) | {"Flask", "Fishing Rod", "Transcendent Limb"}
    assert {bases[n]["type"] for n in names} <= set(checkup.ZH_TYPES)
    assert checkup.zh_name("Keyblade", names) is None   # missing names stay English
    want = names.get("Shrine Sceptre")
    assert checkup.zh_name("Shrine Sceptre (Purity of Fire)", names) == want
    assert checkup.zh_name("Shrine Sceptre (Purity of Fire)", {}) is None


def _base_lines_ok(r, text):
    """Every base in sections 3-4 shows the table's zh name, or English alone when missing."""
    secs = _sections(text)
    n = 0
    for g in r["guide"]["gear"]:
        for b in ([g["equipped"]] if g.get("equipped") else []) + g["picks"]:
            shown = f"{b['base']} ({b['zh']})" if b.get("zh") else b["base"]
            assert shown in secs[3], b
            if not b.get("zh"):
                assert not re.search(re.escape(b["base"]) + r" \([\u3000-\u9fff]", secs[3]), b
            n += 1
    for j in r["guide"]["jewels"]:
        if j.get("base"):
            assert (f"{j['base']} ({j['zh']})" if j.get("zh") else j["base"]) in secs[4]
            n += 1
    return n


def test_guide_base_lines_show_the_zh_name(sunder, witch):
    from pob_agent import checkup, cli
    names = checkup.load_zh()
    for r, text in ((sunder[1], sunder[2]), (witch[1], _render(cli.render_guide, witch[1]))):
        for g in r["guide"]["gear"]:
            for b in ([g["equipped"]] if g.get("equipped") else []) + g["picks"]:
                assert b["zh"] == checkup.zh_name(b["base"], names)
        assert _base_lines_ok(r, text) > 5
    assert ("Chinese base names cover every equippable item type except TrapTool (not covered); a base missing from "
            "the table prints in English.") in sunder[2]


def test_guide_falls_back_to_english_without_the_table(tmp_path, monkeypatch):
    from pob_agent import checkup, cli
    monkeypatch.setattr(checkup, "ZH_FILE", tmp_path / "missing.json")
    assert checkup.load_zh() == {}
    r = _guide_fixture()
    for g in r["guide"]["gear"]:
        for b in ([g["equipped"]] if g.get("equipped") else []) + g["picks"]:
            b["zh"] = checkup.zh_name(b["base"], checkup.load_zh())
    r["guide"]["jewels"][0]["zh"] = None
    text = _render(cli.render_guide, r)
    assert not CJK.search(text) and "- Helmet: Iron Hat\n" in text


# --- GS4 / S-1 / S-2 ----------------------------------------------------------------------------------------------

def test_trade_query_returns_jewel_affixes_on_an_empty_socket(witch):
    # S-1: the socket's Base query used to return no mods (only data.itemMods.Item was read, no base matched)
    from pob_agent import trade
    b, r = witch
    sock = r["next"]["jewels"][0]["id"]
    with Engine() as eng:
        eng.call("load", **sources.resolve(b))
        eng.call("checkup_prepare")
        q = eng.call("trade_query", slot=f"Jewel {sock}", statWeights=trade.DEFAULT_WEIGHTS, includeRunes=False,
                     includeCorrupted=False, topMods=5, jewelType="Base", group=1)
        ids = sorted({i for m in q["mods"] for i in m["jewel"]["modIds"]})
        known = eng.call("eval", code="local t = {} for _, id in ipairs(req.ids) do t[#t + 1] = data.itemMods.Jewel[id] "
                                      "and true or false end return t", ids=ids)
    assert q["mods"] and ids and all(known)


SOCKET = ("local s = build.itemsTab.slots[req.slot] build.itemsTab:CreateDisplayItemFromRaw(req.raw) "
          "local it = build.itemsTab.displayItem build.itemsTab:AddItem(it, true) s:SetSelItemId(it.id) "
          "build.itemsTab:PopulateSlots() build.buildFlag = true recalc() return it.id")
UNSOCKET = ("local s = build.itemsTab.slots[req.slot] s:SetSelItemId(0) build.itemsTab:PopulateSlots() "
            "build.buildFlag = true recalc() return true")


def _mean_text(line):
    """A mod line at the mean of its ranges, written in the test (not by the engine)."""
    return re.sub(r"\((-?[\d.]+)-(-?[\d.]+)\)", lambda m: "%g" % ((float(m.group(1)) + float(m.group(2))) / 2), line)


def test_guide_jewel_base_is_the_best_measured_jewel(witch):
    # GS4 / must-fix: each base's set is socketed for real in a separate engine as a jewel written from raw mod text;
    # the chosen base's jewel has a check-up value >= every other base's set, each of its mods alone raises the value,
    # and each can roll on that base (spawn weight read in that engine; no weight-0 mod)
    b, r = witch
    (j,) = r["guide"]["jewels"]
    assert j["base"] and j["affixes"] and len(j["sets"]) >= 2
    slot = f"Jewel {j['id']}"
    ids = sorted({i for x in j["sets"] for i in x["modIds"]})
    with Engine() as eng:
        eng.call("load", **sources.resolve(b))
        eng.call("checkup_prepare")
        mods = eng.call("eval", code="local t = {} for _, id in ipairs(req.ids) do local m = data.itemMods.Jewel[id] "
                                     "local l = {} for k = 1, #m do l[k] = m[k] end "
                                     "t[id] = { type = m.type, keys = m.weightKey, vals = m.weightVal, lines = l } end "
                                     "return t", ids=ids)
        tags = eng.call("eval", code="local t = {} for _, n in ipairs({'Ruby', 'Emerald', 'Sapphire'}) do "
                                     "t[n] = data.itemBases[n].tags end return t")
        base = eng.call("checkup_value", group=1)["value"]

        def value(jbase, mod_ids):
            lines = [_mean_text(x) for i in mod_ids for x in mods[i]["lines"]]
            eng.call("eval", code=SOCKET, slot=slot, raw="\n".join(["Rarity: RARE", "Test", jbase] + lines))
            v = eng.call("checkup_value", group=1)["value"]
            eng.call("eval", code=UNSOCKET, slot=slot)
            return v

        got = {x["base"]: value(x["base"], x["modIds"]) for x in j["sets"]}
        alone = [value(j["base"], [i]) for i in j["modIds"]]

    def weight(mod, jbase):
        for k, v in zip(mod["keys"], mod["vals"]):
            if tags[jbase].get(k):
                return v
        return 0

    assert all(got[j["base"]] >= v * (1 - 1e-9) for v in got.values()), got
    assert all(v > base for v in alone)
    assert all(weight(mods[i], j["base"]) > 0 for i in j["modIds"])
    assert abs(got[j["base"]] / base - j["mult"]) < 1e-6   # the printed number is that jewel's measured value
    kinds = [mods[i]["type"] for i in j["modIds"]]
    assert kinds.count("Prefix") <= 2 and kinds.count("Suffix") <= 2


def test_guide_jewel_set_rules():
    from pob_agent import checkup
    m = lambda i, t, k, g, *bases: {"modId": i, "lines": [f"(1-3)% {t}"], "type": k, "group": g, "bases": list(bases)}
    mods = [m("a", "A", "Prefix", "ga", "Ruby"), m("b", "B", "Prefix", "gb", "Ruby", "Sapphire"),
            m("c", "C", "Prefix", "gc", "Ruby"), m("d", "D", "Suffix", "gd", "Sapphire"),
            m("e", "E", "Prefix", "ga", "Sapphire"), m("z", "Z", "Suffix", "gz", "Ruby")]
    singles = checkup.jewel_singles(mods, 100.0, [110, 109, 108, 107, 106, 100])
    assert [x["modId"] for x in singles] == ["a", "b", "c", "d", "e"]   # Z adds nothing: not listed
    assert singles[0]["text"] == "#% A" and abs(singles[0]["mult"] - 1.1) < 1e-12
    sets = {x["base"]: x["modIds"] for x in checkup.jewel_sets(singles)}
    assert sets == {"Ruby": ["a", "b"], "Sapphire": ["b", "d", "e"]}   # 2 prefixes max; one mod per group
    pick = checkup.jewel_pick([{"base": "Ruby", "modIds": ["a", "b"], "value": 5.0},
                               {"base": "Sapphire", "modIds": ["b", "d", "e"], "value": 5.0}])
    assert pick["base"] == "Sapphire"
    assert checkup.jewel_sets(checkup.jewel_singles(mods, 100.0, [100] * 6)) == [] and checkup.jewel_pick([]) is None


# --- GS5 / S-8 ----------------------------------------------------------------------------------------------------

def _guide_fixture():
    r = _checkup_dict()
    r["config_flags"] = []
    r["tree"] = {"allocated": 40, "nodes": [{"name": "Heavy Buffer", "share": 0.12, "type": "Notable"},
                                            {"name": "Small", "share": 0.2, "type": "Normal"},
                                            {"name": "Idle Notable", "share": 0.0, "type": "Notable"}]}
    r["next"]["jewels"] = [{"name": "Jewel Socket", "id": 7}]
    r["gear"] = [{"slot": "Helmet", "mods": [{"text": "# to maximum Life"}]}]
    r["guide"] = {"zh_uncovered": ["TrapTool"], "spirit_in_use": ["Herald of Ash"], "value": 120.0, "mainDps": 80.0,
                  "gear": [
        {"slot": "Helmet", "rule": "armour", "affixes": ["# to maximum Life"],
         "equipped": {"base": "Iron Hat", "zh": "鐵盔", "reqLevel": 1, "defences": {"armour": 29}},
         "picks": [{"base": "Rusted Greathelm", "zh": "生鏽巨盔", "reqLevel": 12, "value": 80, "defences": {"armour": 80},
                    "implicits": []}]},
        {"slot": "Weapon 1", "rule": "weapon", "grantsSkill": True, "affixes": [],
         "equipped": {"base": "Withered Wand", "zh": "枯萎法杖", "reqLevel": 1},
         "picks": [{"base": "Other Wand", "zh": None, "reqLevel": 9, "implicits": ["Grants Skill: Level (1-20) Chaos Bolt"]}]},
        {"slot": "Ring 1", "rule": "jewelry", "affixes": ["#% to Fire Resistance"],
         "equipped": {"base": "Iron Ring", "zh": "鍛鐵戒指", "reqLevel": 1},
         "picks": [{"base": "Ruby Ring", "zh": "紅玉戒指", "reqLevel": 8, "affix": "#% to Fire Resistance", "implicits": []}]},
        {"slot": "Ring 2", "rule": "jewelry", "affixes": ["#% to Cold Resistance"],
         "equipped": {"base": "Sapphire Ring", "zh": "藍玉戒指", "reqLevel": 12},
         "picks": [{"base": "Sapphire Ring", "zh": "藍玉戒指", "reqLevel": 12, "affix": "#% to Cold Resistance",
                    "implicits": [], "equipped": True}]},
        {"slot": "Gloves", "rule": "armour", "affixes": [], "empty": True,
         "picks": [{"base": "Rusted Gauntlets", "zh": None, "reqLevel": 1, "value": 40, "defences": {"armour": 40},
                    "subType": "Armour", "implicits": []},
                   {"base": "Gauze Wraps", "zh": None, "reqLevel": 1, "value": 30, "defences": {"energyShield": 30},
                    "subType": "Energy Shield", "implicits": []}]}],
        "jewels": [{"name": "Jewel Socket", "id": 7, "base": "Ruby", "zh": "紅玉", "affixes": ["#% increased Damage"],
                    "mult": 1.042, "sets": []}]}
    return r


def test_guide_render_cjk_only_on_base_lines_and_summary_rows():
    from pob_agent import cli
    r = _guide_fixture()
    text = _render(cli.render_guide, r)
    secs = _sections(text)
    base_line = re.compile(r"^(- [\w ]+: |  - (pick up|keep|other bases of this type|same granted skill): )")
    for line in text.splitlines():
        if CJK.search(line):
            assert (line in secs[3].splitlines() or line in secs[4].splitlines()) and base_line.match(line), line
            assert "affixes" not in line
    assert "- Helmet: Iron Hat (鐵盔)" in secs[3] and "pick up: Rusted Greathelm (生鏽巨盔) — req 12, 80 armour" in secs[3]
    assert "same granted skill: Other Wand — req 9" in secs[3] and "- Jewel Socket: Ruby (紅玉)" in secs[4]
    report = _render(cli.render_checkup, r)
    do_now = [x for x in report.split("### Do now", 1)[1].split("\n\n", 1)[0].splitlines() if x.startswith("|")]
    assert len(do_now) > 3 and all(x in secs[5] for x in do_now)
    flags = [x for x in report.split("Flags:", 1)[1].split("\n### ", 1)[0].splitlines() if x.startswith("- ")]
    assert flags and all(x in secs[5] for x in flags)
    assert "- Helmet: Rusted Greathelm (req 12) has more base defence than the equipped Iron Hat: 80 vs 29." in secs[5]
    assert "- Ring 1: Ruby Ring's implicit matches a ranked affix (#% to Fire Resistance)." in secs[5]
    assert "above" not in secs[5] and "Weapon 1" not in secs[5] and "Ring 2" not in secs[5] and "Gloves" not in secs[5]
    assert "  - keep: Sapphire Ring (藍玉戒指) — req 12, implicit matches a ranked affix: #% to Cold Resistance (equipped)" \
        in secs[3]
    assert "Core notables: Heavy Buffer 12.0%." in secs[2] and "Spirit: in use Herald of Ash" in secs[1]
    assert "measured with that jewel (mean rolls) in the socket: main skill x1.04" in secs[4]
    assert "may be under-rated" in secs[3]   # value 120 vs main-output DPS 80: the trade ranking caveat
    r["guide"]["mainDps"] = 120.0
    assert "under-rated" not in _render(cli.render_guide, r)


# --- GS6 / S-9 ----------------------------------------------------------------------------------------------------

def test_guide_is_deterministic(sunder, witch):
    from pob_agent import checkup
    for b, r in ((str(BUILD), sunder[1]), witch):
        again = checkup.guide(b, r)
        assert json.dumps(again, sort_keys=False, ensure_ascii=False) == json.dumps(r["guide"], ensure_ascii=False)


def test_plain_checkup_json_has_no_guide_key(sunder):
    assert "guide" not in sunder[0]
