-- JSON-lines RPC daemon around headless PoB-PoE2.
-- One request per stdin line: {"id":1,"cmd":"stats",...}
-- One response per stdout line: {"id":1,"ok":true,"result":...}
-- Run with cwd = PoB src/.

local HARNESS_DIR = (debug.getinfo(1, "S").source:sub(2):match("(.*/)")) or "./"
local pob = dofile(HARNESS_DIR .. "pob_headless.lua")
local json = require("dkjson")
local out = pob.stdout

local STAT_FIELDS = {
	-- offence
	"CombinedDPS", "TotalDPS", "FullDPS", "TotalDot", "WithBleedDPS", "WithIgniteDPS", "WithPoisonDPS",
	"AverageHit", "AverageDamage", "Speed", "HitChance", "CritChance", "CritMultiplier",
	"ManaCost", "ManaPerSecondCost", "Cooldown",
	-- defence
	"Life", "LifeUnreserved", "EnergyShield", "Mana", "ManaUnreserved", "Spirit", "SpiritUnreserved",
	"Armour", "Evasion", "EvadeChance", "Ward",
	"TotalEHP", "PhysicalMaximumHitTaken", "FireMaximumHitTaken", "ColdMaximumHitTaken",
	"LightningMaximumHitTaken", "ChaosMaximumHitTaken",
	"FireResist", "ColdResist", "LightningResist", "ChaosResist",
	"FireResistOverCap", "ColdResistOverCap", "LightningResistOverCap",
	"BlockChance", "SpellBlockChance", "LifeRegenRecovery", "LifeLeechGainRate",
	"EffectiveMovementSpeedMod",
	-- attributes
	"Str", "Dex", "Int", "ReqStr", "ReqDex", "ReqInt",
}

local function recalc()
	build.configTab:BuildModList()
	build.buildFlag = true
	runCallback("OnFrame")
end

local function num(v)
	if type(v) ~= "number" then return nil end
	if v ~= v then return "NaN" end
	if v == math.huge then return "inf" end
	if v == -math.huge then return "-inf" end
	return v
end

local function collectStats(fields)
	local o = build.calcsTab.mainOutput or {}
	local res = {}
	for _, k in ipairs(fields or STAT_FIELDS) do
		local v = num(o[k])
		if v ~= nil then res[k] = v end
	end
	return res
end

local function gemList(group)
	local gems = {}
	for _, g in ipairs(group.gemList or {}) do
		local ge = g.gemData and g.gemData.grantedEffect
		gems[#gems + 1] = {
			name = g.nameSpec or (ge and ge.name),
			level = g.level, quality = g.quality, enabled = g.enabled ~= false,
			support = ge and ge.support or false,
		}
	end
	return gems
end

local function mainSkillInfo()
	local env = build.calcsTab.mainEnv
	local ms = env and env.player and env.player.mainSkill
	if not ms then return nil end
	local supports = {}
	for _, eff in ipairs(ms.effectList or {}) do
		if eff.grantedEffect and eff.grantedEffect.support then
			supports[#supports + 1] = eff.grantedEffect.name
		end
	end
	local tags = {}
	for t, v in pairs(ms.skillTypes or {}) do
		if v then tags[#tags + 1] = tostring(t) end
	end
	return {
		name = ms.activeEffect and ms.activeEffect.grantedEffect and ms.activeEffect.grantedEffect.name,
		supports = supports,
		skillFlags = ms.skillFlags,
	}
end

---------------------------------------------------------------------------
-- Config helpers
---------------------------------------------------------------------------
local configOptions = LoadModule("Modules/ConfigOptions")
local optionByVar = {}
for _, opt in ipairs(configOptions) do
	if opt.var then optionByVar[opt.var] = opt end
end

local function activeConfigSet()
	return build.configTab.configSets[build.configTab.activeConfigSetId]
end

local function snapshotConfig()
	local snap = {}
	for k, v in pairs(build.configTab.input) do snap[k] = v end
	local cs = activeConfigSet()
	-- PoB-PoE2 keeps custom mods in configSets[].customModsList (input.customMods is only a fallback)
	snap.__customModsList = cs and cs.customModsList and copyTable(cs.customModsList) or nil
	return snap
end

local function restoreConfig(snap)
	local input = build.configTab.input
	for k in pairs(input) do input[k] = nil end
	for k, v in pairs(snap) do if k ~= "__customModsList" then input[k] = v end end
	local cs = activeConfigSet()
	if cs then cs.customModsList = snap.__customModsList and copyTable(snap.__customModsList) or nil end
end

local function applyConfig(values, customMods, appendMods)
	local input = build.configTab.input
	for k, v in pairs(values or {}) do
		if v == json.null then input[k] = nil else input[k] = v end
	end
	local cs = activeConfigSet()
	if customMods then
		input.customMods = customMods
		if cs then cs.customModsList = { { title = "Default", enabled = true, text = customMods } } end
	end
	if appendMods and appendMods ~= "" then
		if cs then
			cs.customModsList = cs.customModsList or {}
			table.insert(cs.customModsList, { title = "pob-agent", enabled = true, text = appendMods })
		else
			local cur = input.customMods or ""
			input.customMods = (cur ~= "" and (cur .. "\n") or "") .. appendMods
		end
	end
end

local function configState()
	local res = {}
	for var, val in pairs(build.configTab.input) do
		local opt = optionByVar[var]
		local default = build.configTab:GetDefaultState(var, type(val))
		if val ~= default then
			res[#res + 1] = {
				var = var, value = val, default = default,
				type = opt and opt.type, label = opt and opt.label and opt.label:gsub("%^x%x%x%x%x%x%x", ""):gsub("%^%d", ""),
				ifOption = opt and opt.ifOption,
			}
		end
	end
	table.sort(res, function(a, b) return a.var < b.var end)
	return res
end

local function optionCatalog()
	local res, section = {}, nil
	for _, opt in ipairs(configOptions) do
		if opt.section then
			section = opt.section
		elseif opt.var then
			res[#res + 1] = {
				var = opt.var, type = opt.type, section = section,
				label = opt.label and opt.label:gsub("%^x%x%x%x%x%x%x", ""):gsub("%^%d", ""),
				ifOption = opt.ifOption, ifSkill = opt.ifSkill, ifCond = opt.ifCond, ifMult = opt.ifMult,
				ifFlag = opt.ifFlag, ifSkillData = opt.ifSkillData,
				defaultState = opt.defaultState,
			}
		end
	end
	return res
end

---------------------------------------------------------------------------
-- Commands
---------------------------------------------------------------------------
local commands = {}

local function decodeShareCode(code)
	code = code:gsub("%s", ""):gsub("-", "+"):gsub("_", "/")
	local raw = common.base64.decode(code)
	return raw and Inflate(raw)
end

-- Some exports (poe.ninja) store an item-granted skill twice: as the item's own group and as a
-- plain gem group carrying the supports. The plain copy is then charged Spirit even when the item
-- grants it without reservation (e.g. Absent Amulet). Move its supports onto the item group and
-- disable the copy. Returns a list of what was changed.
function normalizeGrantedDuplicates()
	local changes = {}
	local groups = build.skillsTab.socketGroupList
	local function actives(g)
		local t = {}
		for _, gem in ipairs(g.gemList) do
			local ge = gem.gemData and gem.gemData.grantedEffect or gem.grantedEffect
			if ge and not ge.support then t[#t + 1] = gem.nameSpec or ge.name end
		end
		return t
	end
	local handled = {}
	for _, ig in ipairs(groups) do
		local src = ig.source and tostring(ig.source)
		if src and src:match("^Item:") and not handled[src] then
			handled[src] = true
			local ia = actives(ig)
			local nm = #ia == 1 and ia[1] or nil
			local dups, mixed = {}, 0
			for gi, g in ipairs(groups) do
				if g ~= ig and not g.source and g.enabled ~= false and nm then
					local ga = actives(g)
					local has = false
					for _, a in ipairs(ga) do if a == nm then has = true end end
					if has and #ga == 1 then dups[#dups + 1] = gi
					elseif has then mixed = mixed + 1 end
				end
			end
			if #dups == 1 and mixed == 0 then
				-- one plain copy of the item's skill: it is the item skill, exported twice
				local gi = dups[1]
				local g = groups[gi]
				local moved = {}
				for _, gem in ipairs(g.gemList) do
					local ge = gem.gemData and gem.gemData.grantedEffect
					if ge and ge.support then
						ig.gemList[#ig.gemList + 1] = copyTable(gem, true)
						moved[#moved + 1] = gem.nameSpec
					end
				end
				g.enabled = false
				ig.enabled = true
				if build.mainSocketGroup == gi then
					for k, x in ipairs(groups) do if x == ig then build.mainSocketGroup = k end end
				end
				build.skillsTab:ProcessSocketGroup(ig)
				build.skillsTab:ProcessSocketGroup(g)
				changes[#changes + 1] = { skill = nm, itemSource = src, supportsMoved = moved }
			elseif #dups + mixed > 0 then
				local copiesIdx = {}
				for gi, g in ipairs(groups) do
					if g ~= ig and not g.source and g.enabled ~= false then
						for _, a in ipairs(actives(g)) do if a == nm then copiesIdx[#copiesIdx + 1] = gi end end
					end
				end
				-- ambiguous (several copies, or the copy also holds other skills, e.g. a meta gem
				-- with socketed spells): leave as is, but report it - Spirit may be double-counted
				changes[#changes + 1] = { skill = nm, itemSource = src, skipped = true, copies = #dups + mixed,
					groups = copiesIdx }
			end
		end
	end
	return changes
end

function commands.load(req)
	local xml = req.xml
	if not xml and req.code then
		xml = decodeShareCode(req.code)
		if not xml or xml == "" then error("could not decode share code") end
	end
	if not xml and req.path then
		local f = assert(io.open(req.path, "rb"))
		xml = f:read("*a")
		f:close()
	end
	if not xml then error("load needs xml, code or path") end
	loadBuildFromXML(xml, req.name or "build")
	local normalized = req.normalize ~= false and normalizeGrantedDuplicates() or {}
	recalc()
	return { stats = collectStats(), mainSkill = mainSkillInfo(), className = build.spec.curClassName,
		ascendancy = build.spec.curAscendClassName, level = build.characterLevel, normalized = normalized }
end

function commands.new(req)
	newBuild()
	if req.level then build.characterLevel = req.level end
	recalc()
	return { ok = true }
end

function commands.stats(req)
	return { stats = collectStats(req.fields), mainSkill = mainSkillInfo(),
		className = build.spec.curClassName, ascendancy = build.spec.curAscendClassName,
		level = build.characterLevel, mainSocketGroup = build.mainSocketGroup }
end

function commands.skills()
	local groups = {}
	for i, g in ipairs(build.skillsTab.socketGroupList) do
		groups[#groups + 1] = { index = i, label = g.label, slot = g.slot, enabled = g.enabled ~= false,
			includeInFullDPS = g.includeInFullDPS, gems = gemList(g), main = (i == build.mainSocketGroup) }
	end
	return { groups = groups }
end

function commands.items()
	local res = {}
	for slotName, slot in pairs(build.itemsTab.slots) do
		local item = slot.selItemId and build.itemsTab.items[slot.selItemId]
		if item then
			res[#res + 1] = { slot = slotName, name = item.name, rarity = item.rarity, base = item.baseName,
				raw = item:BuildRaw() }
		end
	end
	table.sort(res, function(a, b) return a.slot < b.slot end)
	local set = build.itemsTab.activeItemSet
	return { items = res, weaponSet = (set and set.useSecondWeaponSet) and 2 or 1 }
end

function commands.config(req)
	if req.catalog then return { options = optionCatalog() } end
	local txt = {}
	local cs = activeConfigSet()
	for _, b in ipairs(cs and cs.customModsList or {}) do
		if b.enabled ~= false and b.text and b.text ~= "" then txt[#txt + 1] = b.text end
	end
	local cm = #txt > 0 and table.concat(txt, "\n") or build.configTab.input.customMods
	return { values = configState(), customMods = cm }
end

function commands.set_config(req)
	applyConfig(req.values, req.customMods, req.appendMods)
	recalc()
	return { stats = collectStats(req.fields) }
end

-- Evaluate several config/customMod variants against the current build without
-- keeping any of them. Each variant: {name, values?, customMods?, appendMods?}
function commands.variants(req)
	local snap = snapshotConfig()
	local results = {}
	for _, v in ipairs(req.variants or {}) do
		restoreConfig(snap)
		applyConfig(v.values, v.customMods, v.appendMods)
		local ok, err = pcall(recalc)
		results[#results + 1] = { name = v.name, ok = ok, error = (not ok) and tostring(err) or nil,
			stats = ok and collectStats(req.fields) or nil }
	end
	restoreConfig(snap)
	recalc()
	return { base = collectStats(req.fields), variants = results }
end

-- Replace the item in a slot with raw item text, using PoB's fast calculator.
function commands.try_items(req)
	local calcFunc, baseOut = build.calcsTab:GetMiscCalculator()
	local res = {}
	for _, cand in ipairs(req.candidates or {}) do
		local item = new("Item"):Item(cand.raw)
		local ok, o = pcall(calcFunc, { repSlotName = cand.slot or req.slot, repItem = item })
		local entry = { name = cand.name or item.name, ok = ok }
		if ok then
			entry.stats = {}
			for _, k in ipairs(req.fields or STAT_FIELDS) do entry.stats[k] = num(o[k]) end
		else
			entry.error = tostring(o)
		end
		res[#res + 1] = entry
	end
	local base = {}
	for _, k in ipairs(req.fields or STAT_FIELDS) do base[k] = num(baseOut[k]) end
	return { base = base, candidates = res }
end

function commands.paste_skill(req)
	build.skillsTab:PasteSocketGroup(req.text)
	if req.main then build.mainSocketGroup = #build.skillsTab.socketGroupList end
	recalc()
	return { stats = collectStats(req.fields), mainSkill = mainSkillInfo() }
end

function commands.add_item(req)
	build.itemsTab:CreateDisplayItemFromRaw(req.raw)
	build.itemsTab:AddDisplayItem()
	recalc()
	return { stats = collectStats(req.fields) }
end

function commands.set_main(req)
	if req.group then build.mainSocketGroup = req.group end
	recalc()
	return { stats = collectStats(req.fields), mainSkill = mainSkillInfo() }
end

function commands.save(req)
	local xml = build:SaveDB("code")
	local code = common.base64.encode(Deflate(xml)):gsub("+", "-"):gsub("/", "_")
	return { xml = req.xml and xml or nil, code = code }
end

-- Weighted trade2 query for one slot, generated by PoB's own TradeQueryGenerator
-- (each candidate mod is tested on a blank item in that slot and weighted by
-- its effect on the chosen output stats).
local tradeGen
local function nn(v) if v == json.null then return nil end return v end
function commands.trade_query(req)
	req.maxPrice, req.maxPriceType, req.maxLevel = nn(req.maxPrice), nn(req.maxPriceType), nn(req.maxLevel)
	req.league, req.status, req.jewelType = nn(req.league), nn(req.status), nn(req.jewelType)
	local tradeHelpers = LoadModule("Classes/TradeHelpers")
	if not tradeGen then
		tradeGen = new("TradeQueryGenerator"):TradeQueryGenerator({ itemsTab = build.itemsTab })
	end
	tradeGen.itemsTab = build.itemsTab
	tradeGen.tradeTypeIndex = ({ securable = 1, available = 2, onlineleague = 3, online = 4, any = 5 })[req.status or "available"] or 2
	tradeGen.lastMaxPrice, tradeGen.lastMaxPriceTypeIndex, tradeGen.lastMaxLevel = nil, nil, nil
	local slot = build.itemsTab.slots[req.slot]
	if not slot then error("unknown slot " .. tostring(req.slot)) end

	local captured
	tradeGen.requesterCallback = function(_, query, err) captured = { query = query, err = err } end
	tradeGen.requesterContext = {}
	local statWeights = {}
	for _, w in ipairs(req.statWeights or { { stat = "FullDPS", weightMult = 1 }, { stat = "TotalEHP", weightMult = 0.5 } }) do
		for _, ps in ipairs(data.powerStatList) do
			if ps.stat == w.stat then
				statWeights[#statWeights + 1] = { stat = w.stat, weightMult = w.weightMult, transform = ps.transform }
			end
		end
	end
	tradeGen:StartQuery(slot, {
		statWeights = statWeights,
		includeCorrupted = req.includeCorrupted ~= false,
		includeRunes = req.includeRunes ~= false,
		includeMirrored = false,
		maxPrice = req.maxPrice, maxPriceType = req.maxPriceType,
		maxLevel = req.maxLevel, jewelType = req.jewelType or "Base",
	})
	local guard = 0
	while tradeGen.calcContext.co and guard < 100000 do
		tradeGen:OnFrame()
		guard = guard + 1
	end
	if not captured then error("trade query generation did not finish") end

	-- id -> human text for explanation
	local textById = {}
	for _, group in pairs(tradeGen.modData or {}) do
		for _, entry in pairs(group) do
			if type(entry) == "table" and entry.tradeMod then textById[entry.tradeMod.id] = entry.tradeMod.text end
		end
	end
	local weights = {}
	for i, w in ipairs(tradeGen.modWeights or {}) do
		if i > (req.topWeights or 25) then break end
		weights[#weights + 1] = { id = w.tradeModId, text = textById[w.tradeModId], weight = w.weight, meanStatDiff = w.meanStatDiff }
	end
	local url
	if captured.query and req.league then
		-- Same URL shape as PoB's CompareBuySimilar: trade2/search/<league>/<b64gzip(query)>
		local q = json.encode(captured.query)
		local league = req.league:gsub("[^%w%-%.%_%~ ]", function(c) return string.format("%%%02X", string.byte(c)) end):gsub(" ", "+")
		url = "https://www.pathofexile.com/trade2/search/" .. league .. "/" .. tradeHelpers.B64GzipEncode(q)
	end
	return { query = captured.query, error = captured.err, weights = weights, url = url }
end

---------------------------------------------------------------------------
-- Skill scan: PoB-data-only strength estimate for active skills on a
-- standardised character (no ladder data involved).
---------------------------------------------------------------------------
local templateWeaponCache = {}
local function templateWeapon(weaponType, maxLevel)
	local key = weaponType .. ":" .. maxLevel
	if templateWeaponCache[key] ~= nil then return templateWeaponCache[key] end
	local best, bestLevel
	local wantType, wantSub = weaponType, nil
	if weaponType == "Quarterstaff" then wantType, wantSub = "Staff", "Warstaff" end
	for name, base in pairs(data.itemBases) do
		if base.type == wantType and (not wantSub or base.subType == wantSub)
			and not (wantType == "Staff" and not wantSub and base.subType == "Warstaff")
			and not base.hidden and base.weapon then
			local lvl = base.req and base.req.level or 1
			if lvl <= maxLevel and (not bestLevel or lvl > bestLevel) then
				best, bestLevel = name, lvl
			end
		end
	end
	templateWeaponCache[key] = best or false
	return best
end

local function findGemByName(name)
	for id, g in pairs(data.gems) do
		if g.name == name then return id, g end
	end
end

local function skillDps()
	local o = build.calcsTab.mainOutput or {}
	local v = o.CombinedDPS
	if not v or v == 0 then v = o.FullDPS or o.TotalDPS or 0 end
	if v ~= v or v == math.huge then v = 0 end
	return v
end

-- DPS through the misc calculator. Baselines for fast-calc comparisons must come from here too:
-- the fast path may return CombinedDPS where the full recalc returns FullDPS.
local function fastDps(calcFunc, override, opts)
	local ok, o = pcall(calcFunc, override or {}, false, opts)
	if not ok or not o then return nil end
	local v = o.CombinedDPS
	if not v or v == 0 then v = o.FullDPS or o.TotalDPS or 0 end
	if v ~= v or v == math.huge then return nil end
	return v
end

-- Which Multiplier:/Condition: names each config option produces. Found by
-- running the option's apply() against a recording mod list.
local optionEffects
local function getOptionEffects()
	if optionEffects then return optionEffects end
	optionEffects = {}
	local function recorder(sink)
		local r = {}
		function r:NewMod(name, ...) sink[name] = true end
		function r:AddMod(mod) if mod and mod.name then sink[mod.name] = true end end
		function r:ReplaceMod(name, ...) sink[name] = true end
		return r
	end
	for _, opt in ipairs(configOptions) do
		if opt.var and opt.apply and (opt.type == "count" or opt.type == "check" or opt.type == "countAllowZero") then
			local sink = {}
			pcall(opt.apply, opt.type == "check" and true or 1, recorder(sink), recorder(sink))
			optionEffects[opt.var] = sink
		end
	end
	return optionEffects
end

-- Multiplier/Condition variables referenced by the current main skill's mods.
local function mainSkillVars()
	local vars = {}
	local env = build.calcsTab.mainEnv
	local ms = env and env.player and env.player.mainSkill
	if not ms or not ms.skillModList then return vars end
	local function scan(list)
		for _, mod in ipairs(list) do
			for _, tag in ipairs(mod) do
				if type(tag) == "table" and tag.var then
					if tag.type == "Multiplier" or tag.type == "MultiplierThreshold" then
						vars["Multiplier:" .. tag.var] = true
					elseif tag.type == "Condition" or tag.type == "ActorCondition" then
						vars["Condition:" .. tag.var] = true
					end
				end
			end
		end
	end
	scan(ms.skillModList)
	if ms.skillModList.parent then scan(ms.skillModList.parent) end
	return vars
end

local function rampOptionsFor(skillName)
	local res, seen = {}, {}
	local vars = mainSkillVars()
	local effects = getOptionEffects()
	for _, opt in ipairs(configOptions) do
		if opt.var and (opt.type == "count" or opt.type == "check") and not seen[opt.var] then
			local match = false
			local s = opt.ifSkill
			if type(s) == "string" then
				match = (s == skillName)
			elseif type(s) == "table" then
				for _, n in ipairs(s) do if n == skillName then match = true end end
			end
			-- options scoped to another skill still count when they feed a variable
			-- this skill reads (e.g. Whirling Slash stages consumed by Twister)
			for name in pairs(effects[opt.var] or {}) do
				if vars[name] then match = true end
			end
			-- charge counts are PowerCharges OVERRIDE mods, not Multipliers; match them when the
			-- skill reads any variable about that charge type (e.g. RemovablePowerCharge)
			local ct = opt.var:match("^override(%a+)Charges$")
			if ct then
				for name in pairs(vars) do if name:find(ct .. "Charge", 1, true) then match = true end end
			end
			-- stacks the build itself has configured (e.g. Rage) are ramp too
			if opt.type == "count" and build.configTab.input[opt.var] ~= nil
				and build.configTab.input[opt.var] ~= 0 then
				match = true
			end
			if match then
				seen[opt.var] = true
				res[#res + 1] = opt
			end
		end
	end
	return res
end

local function computeRamp(skillName, req)
	local ramp = {}
	for _, opt in ipairs(rampOptionsFor(skillName)) do
		local snap = snapshotConfig()
		local current = snap[opt.var]
		local curve = {}
		local values = opt.type == "check" and { false, true } or (req.rampValues or { 0, 1, 2, 3, 5, 10, 20 })
		-- include the build's own configured value (e.g. Rage 30/100) so the curve reaches it
		if opt.type == "count" and type(current) == "number" and current > 0 and not req.rampValues then
			local have = false
			for _, v in ipairs(values) do if v == current then have = true end end
			if not have then
				local t = {}
				for _, v in ipairs(values) do t[#t + 1] = v end
				t[#t + 1] = current
				table.sort(t)
				values = t
			end
		end
		-- charges: sweep 0..max of this build, never past it
		local ct = opt.var:match("^override(%a+)Charges$")
		if ct and opt.type ~= "check" then
			local mx = num((build.calcsTab.mainOutput or {})[ct .. "ChargesMax"]) or 0
			if mx > 0 then
				values = {}
				for v = 0, math.min(mx, 20) do values[#values + 1] = v end
			end
		end
		for _, v in ipairs(values) do
			restoreConfig(snap)
			build.configTab.input[opt.var] = v
			-- count options often sit behind a "do you use X?" checkbox
			if opt.ifOption and v ~= false then build.configTab.input[opt.ifOption] = true end
			-- PoB ignores a "count" value of 0 (falls back to max/default), so 0 must switch the
			-- gating checkbox off instead
			if v == 0 and opt.type == "count" and opt.ifOption then
				build.configTab.input[opt.ifOption] = false
			end
			recalc()
			local o = build.calcsTab.mainOutput or {}
			curve[#curve + 1] = { value = v, dps = skillDps(), ehp = num(o.TotalEHP) }
		end
		restoreConfig(snap)
		local feeds = {}
		for name in pairs(getOptionEffects()[opt.var] or {}) do feeds[#feeds + 1] = name end
		table.sort(feeds)
		ramp[#ramp + 1] = { var = opt.var, type = opt.type, ifSkill = opt.ifSkill, feeds = feeds, current = current,
			label = opt.label and opt.label:gsub("%^x%x%x%x%x%x%x", ""):gsub("%^%d", ""),
			curve = curve, low = curve[1].dps, high = curve[#curve].dps }
	end
	recalc()
	return ramp
end

local function scanOne(gemId, gemData, req)
	newBuild()
	build.characterLevel = req.level or 90
	applyConfig(nil, req.templateMods or "")
	-- weapon for attacks
	local weaponType
	if gemData.weaponRequirements then
		weaponType = gemData.weaponRequirements:match("^([^,]+)")
		local baseName = weaponType and templateWeapon(weaponType, req.weaponLevel or 65)
		if baseName then
			build.itemsTab:CreateDisplayItemFromRaw("Rarity: RARE\nTemplate Weapon\n" .. baseName .. "\n" .. (req.weaponMods or ""))
			build.itemsTab:AddDisplayItem()
		end
	end
	build.skillsTab:PasteSocketGroup(gemData.name .. " " .. (req.gemLevel or 20) .. "/" .. (req.gemQuality or 20) .. "  1")
	build.mainSocketGroup = 1
	recalc()
	recalc() -- first calc after newBuild can be stale
	local group = build.skillsTab.socketGroupList[1]
	local active = group and group.displaySkillList and group.displaySkillList[1]
	local baseDps = skillDps()
	local result = { gem = gemData.name, gemType = gemData.gemType, tags = gemData.tagString, weaponType = weaponType,
		description = gemData.grantedEffect and gemData.grantedEffect.description,
		baseDPS = baseDps, supports = {} }
	if not active or baseDps <= 0 then
		result.note = "no damage output on template"
		return result
	end

	-- greedy supports using PoB's fast misc calculator
	local candidates = {}
	for id, g in pairs(data.gems) do
		if g.grantedEffect and g.grantedEffect.support and not g.grantedEffect.hidden
			and (req.allowLineage or not (g.tags and g.tags.lineage))
			and calcLib.canGrantedEffectSupportActiveSkill(g.grantedEffect, active) then
			candidates[#candidates + 1] = { id = id, g = g }
		end
	end
	local fastOpts = { nodeAlloc = true, requirementsItems = true, requirementsGems = true, skipEHP = true }
	local chosen = {}
	for _ = 1, (req.supports or 5) do
		local calcFunc = build.calcsTab:GetMiscCalculator()
		local bestDps, best = fastDps(calcFunc, nil, fastOpts) or skillDps(), nil
		local idx = #group.gemList + 1
		for _, c in ipairs(candidates) do
			if not chosen[c.id] then
				group.gemList[idx] = { level = c.g.naturalMaxLevel, quality = 0, count = 1, enabled = true,
					enableGlobal1 = true, enableGlobal2 = true, gemId = c.id, nameSpec = c.g.name,
					skillId = c.g.grantedEffectId, gemData = c.g }
				local ok, o = pcall(calcFunc, nil, false, fastOpts)
				if ok and o then
					local v = o.CombinedDPS
					if not v or v == 0 then v = o.FullDPS or o.TotalDPS or 0 end
					if v == v and v ~= math.huge and v > bestDps * 1.001 then bestDps, best = v, c end
				end
			end
		end
		group.gemList[idx] = nil
		if not best then break end
		chosen[best.id] = true
		group.gemList[idx] = { level = best.g.naturalMaxLevel, quality = 0, count = 1, enabled = true,
			enableGlobal1 = true, enableGlobal2 = true, gemId = best.id, nameSpec = best.g.name,
			skillId = best.g.grantedEffectId }
		build.skillsTab:ProcessSocketGroup(group)
		recalc()
		result.supports[#result.supports + 1] = { name = best.g.name, dps = skillDps() }
	end
	result.supportedDPS = skillDps()
	result.supportMult = result.supportedDPS / baseDps

	-- ramp: skill-specific stack/stage options PoB exposes for this skill
	result.ramp = computeRamp(gemData.name, req)

	-- elasticity: DPS gain from one standard unit of each probe stat
	if req.probes then
		local base = skillDps()
		local snap = snapshotConfig()
		result.elasticity = {}
		for _, p in ipairs(req.probes) do
			restoreConfig(snap)
			applyConfig(nil, nil, p.mod)
			recalc()
			result.elasticity[p.name] = base > 0 and (skillDps() / base - 1) or 0
		end
		restoreConfig(snap)
		recalc()
	end
	return result
end

function commands.skill_scan(req)
	local res = {}
	local names = req.skills
	if not names then
		names = {}
		for _, g in pairs(data.gems) do
			if g.grantedEffect and not g.grantedEffect.support and not g.grantedEffect.hidden
				and (g.gemType == "Attack" or g.gemType == "Spell" or g.gemType == "Minion")
				and g.tags and g.tags.grants_active_skill then
				names[#names + 1] = g.name
			end
		end
		table.sort(names)
	end
	for _, name in ipairs(names) do
		local id, g = findGemByName(name)
		if id then
			local ok, r = pcall(scanOne, id, g, req)
			if ok then res[#res + 1] = r else res[#res + 1] = { gem = name, error = tostring(r) } end
		else
			res[#res + 1] = { gem = name, error = "gem not found" }
		end
		if req.progress then io.stderr:write("scanned ", name, "\n") end
	end
	return { results = res }
end

---------------------------------------------------------------------------
-- Ascendancy lift: same skill + supports, each ascendancy's points spent
-- greedily by PoB's calculator. Measures how much an ascendancy multiplies a skill.
---------------------------------------------------------------------------
local function setupSkill(gemData, supportIds, req, classId, ascendId)
	newBuild()
	if classId then
		build.spec:SelectClass(classId)
		build.spec:SelectAscendClass(ascendId or 0)
	end
	build.characterLevel = req.level or 90
	applyConfig(nil, req.templateMods or "")
	if gemData.weaponRequirements then
		local weaponType = gemData.weaponRequirements:match("^([^,]+)")
		local baseName = weaponType and templateWeapon(weaponType, req.weaponLevel or 65)
		if baseName then
			build.itemsTab:CreateDisplayItemFromRaw("Rarity: RARE\nTemplate Weapon\n" .. baseName .. "\n" .. (req.weaponMods or ""))
			build.itemsTab:AddDisplayItem()
		end
	end
	build.skillsTab:PasteSocketGroup(gemData.name .. " " .. (req.gemLevel or 20) .. "/" .. (req.gemQuality or 20) .. "  1")
	build.mainSocketGroup = 1
	local group = build.skillsTab.socketGroupList[1]
	for _, id in ipairs(supportIds or {}) do
		local g = data.gems[id]
		if g then
			group.gemList[#group.gemList + 1] = { level = g.naturalMaxLevel, quality = 0, count = 1, enabled = true,
				enableGlobal1 = true, enableGlobal2 = true, gemId = id, nameSpec = g.name, skillId = g.grantedEffectId }
		end
	end
	build.skillsTab:ProcessSocketGroup(group)
	build.spec:BuildAllDependsAndPaths()
	recalc()
	recalc()
	return group
end

local function greedyAscendancy(points)
	local chosen, spent = {}, 0
	local fastOpts = { requirementsItems = true, requirementsGems = true, skipEHP = true }
	while spent < points do
		local calcFunc = build.calcsTab:GetMiscCalculator()
		local base = fastDps(calcFunc, {}, fastOpts) or skillDps()
		local best, bestGain, bestCost
		for _, node in pairs(build.spec.nodes) do
			if node.ascendancyName == build.spec.curAscendClassName and not node.alloc and node.path
				and not node.isAscendancyStart then
				local cost = #node.path
				if cost > 0 and spent + cost <= points then
					local add = {}
					for _, pn in ipairs(node.path) do add[pn] = true end
					local ok, o = pcall(calcFunc, { addNodes = add }, false, fastOpts)
					if ok and o then
						local v = o.CombinedDPS
						if not v or v == 0 then v = o.FullDPS or o.TotalDPS or 0 end
						if v == v and v ~= math.huge then
							local gain = (v - base) / cost
							if not bestGain or gain > bestGain then best, bestGain, bestCost = node, gain, cost end
						end
					end
				end
			end
		end
		if not best or bestGain <= 0 then break end
		for _, pn in ipairs(best.path) do
			if pn.isNotable or pn == best then chosen[#chosen + 1] = pn.dn end
		end
		build.spec:AllocNode(best)
		build.spec:BuildAllDependsAndPaths()
		recalc()
		spent = spent + bestCost
	end
	return chosen, spent
end

function commands.ascendancy_lift(req)
	local results = {}
	for _, name in ipairs(req.skills or {}) do
		local gemId, gemData = findGemByName(name)
		if not gemId then
			results[#results + 1] = { skill = name, error = "gem not found" }
		else
			-- supports chosen once on the class-less template, then held fixed
			local scan = scanOne(gemId, gemData, req)
			local supportIds = {}
			for _, s in ipairs(scan.supports or {}) do
				local sid = findGemByName(s.name)
				if sid then supportIds[#supportIds + 1] = sid end
			end
			local rows = {}
			for classId, class in pairs(build.spec.tree.classes) do
				for ascendId, asc in pairs(class.classes) do
					if ascendId ~= 0 and (not req.ascendancies or req.ascendancies[asc.name]) then
						local ok, err = pcall(function()
							setupSkill(gemData, supportIds, req, classId, ascendId)
							local before = skillDps()
							local picks, spent = greedyAscendancy(req.points or 8)
							local after = skillDps()
							rows[#rows + 1] = { ascendancy = asc.name, class = class.name, before = before, after = after,
								lift = before > 0 and after / before or nil, nodes = picks, spent = spent }
						end)
						if not ok then rows[#rows + 1] = { ascendancy = asc.name, error = tostring(err) } end
					end
				end
			end
			table.sort(rows, function(a, b) return (a.lift or 0) > (b.lift or 0) end)
			results[#results + 1] = { skill = name, supports = scan.supports, baseDPS = scan.supportedDPS, ascendancies = rows }
		end
		if req.progress then io.stderr:write("lift ", name, "\n") end
	end
	return { results = results }
end

-- Ramp curves for the loaded build's main skill.
---------------------------------------------------------------------------
-- Build-up: construct one skill greedily, layer by layer, and record the
-- multiplier each layer and each pick adds.
--   bare gem -> supports -> ascendancy (8 pts) -> passive tree (N pts)
---------------------------------------------------------------------------
local uniqueSweep -- defined below (unique_sweep)
local function greedyTree(points, maxPath)
	local picks, spent = {}, 0
	local fastOpts = { requirementsItems = true, requirementsGems = true, skipEHP = true }
	while spent < points do
		local calcFunc = build.calcsTab:GetMiscCalculator()
		local base = fastDps(calcFunc, {}, fastOpts) or skillDps()
		local best, bestGain, bestCost, bestV
		for _, node in pairs(build.spec.nodes) do
			if not node.ascendancyName and not node.alloc and node.path
				and (node.type == "Notable" or node.type == "Keystone") then
				local cost = #node.path
				if cost > 0 and cost <= (maxPath or 7) and spent + cost <= points then
					local add = {}
					for _, pn in ipairs(node.path) do add[pn] = true end
					local ok, o = pcall(calcFunc, { addNodes = add }, false, fastOpts)
					if ok and o then
						local v = o.CombinedDPS
						if not v or v == 0 then v = o.FullDPS or o.TotalDPS or 0 end
						if v == v and v ~= math.huge and base > 0 then
							local gain = math.log(v / base) / cost
							if not bestGain or gain > bestGain then best, bestGain, bestCost, bestV = node, gain, cost, v end
						end
					end
				end
			end
		end
		if not best or bestGain <= 0 then break end
		build.spec:AllocNode(best)
		build.spec:BuildAllDependsAndPaths()
		recalc()
		spent = spent + bestCost
		picks[#picks + 1] = { name = best.dn, type = best.type, cost = bestCost, mult = bestV / base }
	end
	return picks, spent
end

function commands.build_up(req)
	local gemId, gemData = findGemByName(req.skill)
	if not gemId then error("gem not found: " .. tostring(req.skill)) end
	-- ascendancy lookup
	local classId, ascendId, className
	for cid, class in pairs(build.spec.tree.classes) do
		for aid, asc in pairs(class.classes) do
			if aid ~= 0 and asc.name == req.ascendancy then classId, ascendId, className = cid, aid, class.name end
		end
	end
	if req.ascendancy and not classId then error("ascendancy not found: " .. req.ascendancy) end

	local res = { skill = req.skill, ascendancy = req.ascendancy, class = className, steps = {} }
	-- 1. bare gem + greedy supports on the class-less template
	local scan = scanOne(gemId, gemData, req)
	res.bareDPS = scan.baseDPS
	local supportIds, prev = {}, scan.baseDPS
	for _, sp in ipairs(scan.supports or {}) do
		local sid = findGemByName(sp.name)
		if sid then supportIds[#supportIds + 1] = sid end
		res.steps[#res.steps + 1] = { layer = "support", name = sp.name, mult = prev > 0 and sp.dps / prev or nil }
		prev = sp.dps
	end
	res.supportedDPS = scan.supportedDPS
	res.ramp = scan.ramp
	-- 2. class + ascendancy
	setupSkill(gemData, supportIds, req, classId, ascendId)
	local beforeAsc = skillDps()
	if classId then
		local before = beforeAsc
		local chosen = {}
		local fastPicks = greedyAscendancy(req.ascPoints or 8)
		res.ascNodes = fastPicks
		res.afterAscDPS = skillDps()
		res.steps[#res.steps + 1] = { layer = "ascendancy", name = table.concat(fastPicks, ", "),
			mult = before > 0 and res.afterAscDPS / before or nil }
	end
	-- 3. passive tree
	local beforeTree = skillDps()
	local picks, spent = greedyTree(req.treePoints or 40, req.maxPath or 7)
	for _, pk in ipairs(picks) do
		res.steps[#res.steps + 1] = { layer = pk.type == "Keystone" and "keystone" or "notable", name = pk.name,
			mult = pk.mult, cost = pk.cost }
	end
	res.treeSpent = spent
	res.finalDPS = skillDps()
	if req.uniques ~= false then res.uniques = uniqueSweep(nil, req.uniqueTop or 3, req.level or 90) end
	res.layers = {
		supports = scan.baseDPS > 0 and scan.supportedDPS / scan.baseDPS or nil,
		classBase = scan.supportedDPS > 0 and beforeAsc / scan.supportedDPS or nil,
		ascendancy = beforeAsc > 0 and (res.afterAscDPS or beforeAsc) / beforeAsc or nil,
		tree = beforeTree > 0 and res.finalDPS / beforeTree or nil,
	}
	return res
end

function commands.ramp(req)
	local info = mainSkillInfo()
	if not info or not info.name then error("no main skill") end
	return { skill = info.name, base = skillDps(), ramp = computeRamp(info.name, req) }
end

function commands.list_skills()
	local res = {}
	for _, g in pairs(data.gems) do
		if g.grantedEffect and not g.grantedEffect.support and not g.grantedEffect.hidden and g.tags and g.tags.grants_active_skill then
			res[#res + 1] = { name = g.name, gemType = g.gemType, tags = g.tagString, weapon = g.weaponRequirements,
				description = g.grantedEffect.description }
		end
	end
	table.sort(res, function(a, b) return a.name < b.name end)
	return { skills = res }
end

-- In-game Build Planner file (.build, GGG's documented JSON format) via PoB's exporter.
function commands.export_build(req)
	local exporter = LoadModule("Modules/BuildExportPoE2")
	local selection = { specIndex = build.treeTab.activeSpec, skillSetId = build.skillsTab.activeSkillSetId,
		itemSetId = build.itemsTab.activeItemSetId }
	local jsonText, err = exporter.Export(build, { name = nn(req.name), author = nn(req.author),
		description = nn(req.description) }, selection)
	if not jsonText then error(err) end
	return { build = jsonText }
end

-- Multiplier decomposition of the loaded build's main skill: how much DPS each
-- support gem, ascendancy node, keystone/notable and jewel socket is worth.
-- Each entry = DPS with everything / DPS with that one thing removed ("leave-one-out").
function commands.decompose(req)
	recalc()
	local base = skillDps()
	local res = { base = base, supports = {}, ascendancy = {}, tree = {}, layers = {} }
	if base <= 0 then return res end
	local function ratio(v) if not v or v <= 0 then return "inf" end return base / v end

	-- supports in the main socket group (toggle enabled, full recalc)
	local group = build.skillsTab.socketGroupList[build.mainSocketGroup]
	if group then
		local supIdx = {}
		for i, g in ipairs(group.gemList) do
			local ge = g.gemData and g.gemData.grantedEffect
			if ge and ge.support and g.enabled ~= false then supIdx[#supIdx + 1] = i end
		end
		for _, i in ipairs(supIdx) do
			local g = group.gemList[i]
			g.enabled = false
			build.skillsTab:ProcessSocketGroup(group); recalc()
			res.supports[#res.supports + 1] = { name = g.nameSpec or g.gemData.name, level = g.level, quality = g.quality,
				mult = ratio(skillDps()) }
			g.enabled = true
		end
		for _, i in ipairs(supIdx) do group.gemList[i].enabled = false end
		build.skillsTab:ProcessSocketGroup(group); recalc()
		res.layers.supports = ratio(skillDps())
		for _, i in ipairs(supIdx) do group.gemList[i].enabled = true end
		build.skillsTab:ProcessSocketGroup(group); recalc()
		base = skillDps()
		res.base = base
	end

	-- passive nodes via the misc calculator's removeNodes override
	local calcFunc = build.calcsTab:GetMiscCalculator()
	-- no requirementsItems: with it the item state is reused and removing a jewel socket keeps the jewel
	local fastOpts = { requirementsGems = true, skipEHP = true }
	local function without(nodes)
		local ok, o = pcall(calcFunc, { removeNodes = nodes }, false, fastOpts)
		if not ok or not o then return nil end
		local v = o.CombinedDPS
		if not v or v == 0 then v = o.FullDPS or o.TotalDPS or 0 end
		return v
	end
	-- The fast calc does not produce FullDPS for every build, so node ratios must use a baseline
	-- computed through the same path (otherwise FullDPS/CombinedDPS mismatch inflates every node).
	local nodeBase = without({}) or 0
	local function ratio(v) if not v or v <= 0 then return "inf" end return nodeBase / v end
	local asc, tree, small, jewels = {}, {}, {}, {}
	for id, node in pairs(build.spec.allocNodes) do
		if node.type ~= "ClassStart" and node.type ~= "AscendClassStart" then
			if node.ascendancyName then
				asc[node] = true
				local m = ratio(without({ [node] = true }))
				if node.type ~= "Normal" or m == "inf" or math.abs(m - 1) > 0.001 then
					res.ascendancy[#res.ascendancy + 1] = { name = node.dn, type = node.type, mult = m }
				end
			else
				tree[node] = true
				if node.type == "Notable" or node.type == "Keystone" or node.type == "Socket" then
					local m = ratio(without({ [node] = true }))
					local entry = { name = node.dn, type = node.type, mult = m }
					if node.type == "Socket" then
						local slot = build.itemsTab.sockets and build.itemsTab.sockets[node.id]
						local item = slot and build.itemsTab.items[slot.selItemId]
						entry.name = item and item.name or node.dn
					end
					if m == "inf" or math.abs(m - 1) > 0.001 then res.tree[#res.tree + 1] = entry end
				else
					small[node] = true
				end
				if node.type == "Socket" then jewels[node] = true end
			end
		end
	end
	res.layers.ascendancy = ratio(without(asc))
	res.layers.tree = ratio(without(tree))
	res.layers.tree_small = ratio(without(small))
	if next(jewels) then res.layers.jewels = ratio(without(jewels)) end
	local key = function(a, b)
		local x = a.mult == "inf" and 1e9 or a.mult
		local y = b.mult == "inf" and 1e9 or b.mult
		return x > y
	end
	table.sort(res.supports, key); table.sort(res.ascendancy, key); table.sort(res.tree, key)
	return res
end

-- Pairwise synergy between load-bearing sources of the loaded build.
-- sources: [{kind="node"|"slot"|"support", name=..., slot=...}]
-- For each pair: synergy = mult(i and j removed together) / (mult_i * mult_j); > 1 = they feed each other.
function commands.synergy(req)
	recalc()
	local base = skillDps()
	if base <= 0 then return { base = 0, pairs = {} } end
	local group = build.skillsTab.socketGroupList[build.mainSocketGroup]
	local nodeByName = {}
	for _, node in pairs(build.spec.allocNodes) do nodeByName[node.dn] = node end
	local supByName = {}
	for _, g in ipairs(group and group.gemList or {}) do
		local nm = g.nameSpec or (g.gemData and g.gemData.name)
		if nm then supByName[nm] = g end
	end
	-- No requirementsItems here: it reuses the previous call's item state and ignores repItem.
	local fastOpts = { requirementsGems = true, skipEHP = true }
	local function dps(o)
		local v = o.CombinedDPS
		if not v or v == 0 then v = o.FullDPS or o.TotalDPS or 0 end
		return v
	end
	-- evaluate DPS with a set of removals
	local function eval(list)
		local override, sups = { removeNodes = {} }, {}
		for _, s in ipairs(list) do
			if s.kind == "node" then
				local n = nodeByName[s.name]; if n then override.removeNodes[n] = true end
			elseif s.kind == "slot" then
				if override.repSlotName then return nil end
				override.repSlotName = s.slot
				override.repItem = s.raw and new("Item"):Item(s.raw) or nil
			elseif s.kind == "support" then
				local g = supByName[s.name]; if g then sups[#sups + 1] = g end
			end
		end
		for _, g in ipairs(sups) do g.enabled = false end
		if #sups > 0 then build.skillsTab:ProcessSocketGroup(group); recalc() end
		local calcFunc = build.calcsTab:GetMiscCalculator()
		local ok, o = pcall(calcFunc, override, false, fastOpts)
		for _, g in ipairs(sups) do g.enabled = true end
		if #sups > 0 then build.skillsTab:ProcessSocketGroup(group); recalc() end
		if not ok or not o then return nil end
		return dps(o)
	end
	local src = req.sources or {}
	base = eval({}) or 0
	if base <= 0 then return { base = 0, pairs = {} } end
	local single = {}
	for i, s in ipairs(src) do
		local v = eval({ s })
		single[i] = (v and v > 0) and base / v or nil
	end
	local pairsOut = {}
	for i = 1, #src do
		for j = i + 1, #src do
			if single[i] and single[j] then
				local v = eval({ src[i], src[j] })
				if v ~= nil then
					local joint = v > 0 and base / v or math.huge
					pairsOut[#pairsOut + 1] = { a = src[i].name, b = src[j].name, ka = src[i].kind, kb = src[j].kind,
						ma = single[i], mb = single[j], joint = joint ~= math.huge and joint or "inf",
						synergy = joint ~= math.huge and joint / (single[i] * single[j]) or "inf" }
				end
			end
		end
	end
	return { base = base, pairs = pairsOut }
end

-- Enablers: pieces whose value is that they make a config condition permanent (Eternal Life keeps
-- you on Low Life, The Taming gives Twister all three elements). Leave-one-out reads them ~x1.0
-- because the config box stays ticked. For each entry measure: removing the piece alone, turning
-- off only the conditions it guarantees, and both together.
-- entries: [{id, sources=[{kind="node",name}|{kind="slot",slot,raw}], off={var=value|null},
--            extra=[sources removed only in the "with" measurement]}]
-- detect=true also lists pieces whose parsed mods set a Condition flag that a config box also sets.
local function activeEquipSlots()
	local set = build.itemsTab.activeItemSet
	local swap = set and set.useSecondWeaponSet
	local res = {}
	for slotName, slot in pairs(build.itemsTab.slots) do
		if not slot.nodeId and not slotName:match("Flask") and not slotName:match("Charm") then
			local isSwap = slotName:match("Swap") ~= nil
			local isWeapon = slotName:match("^Weapon") ~= nil
			if not isWeapon or (isSwap == (swap and true or false)) then
				local item = slot.selItemId and build.itemsTab.items[slot.selItemId]
				if item then res[slotName] = item end
			end
		end
	end
	return res
end

local function detectEnablers()
	-- player-side effects only (getOptionEffects mixes in the enemy mod list: "enemy is Blinded"
	-- would otherwise match a player Condition:Blinded flag)
	local function recorder(sink)
		local r = {}
		function r:NewMod(name, ...) sink[name] = true end
		function r:AddMod(mod) if mod and mod.name then sink[mod.name] = true end end
		function r:ReplaceMod(name, ...) sink[name] = true end
		return r
	end
	local byCond = {}
	for _, opt in ipairs(configOptions) do
		local sink = {}
		if opt.var and opt.type == "check" and opt.apply then
			pcall(opt.apply, true, recorder(sink), recorder({}))
			for name in pairs(sink) do
				if name:match("^Condition:") then
					byCond[name] = byCond[name] or {}
					table.insert(byCond[name], opt.var)
				end
			end
		end
	end
	local found = {}
	local function scan(list, kind, name, slot)
		if not list then return end
		for _, mod in ipairs(list) do
			if mod.type == "FLAG" and type(mod.name) == "string" and mod.name:match("^Condition:") and byCond[mod.name] then
				local tagged = false
				for _, tag in ipairs(mod) do if type(tag) == "table" then tagged = true end end
				found[#found + 1] = { kind = kind, name = name, slot = slot, condition = mod.name,
					vars = byCond[mod.name], conditional = tagged }
			end
		end
	end
	for _, node in pairs(build.spec.allocNodes) do scan(node.modList, "node", node.dn) end
	for slotName, item in pairs(activeEquipSlots()) do
		scan(item.modList or (item.slotModList and item.slotModList[1]), "slot", item.name, slotName)
	end
	return found
end

function commands.enablers(req)
	recalc()
	local nodeByName = {}
	for _, node in pairs(build.spec.allocNodes) do nodeByName[node.dn] = node end
	local fastOpts = { requirementsGems = true, skipEHP = true }
	local snap = snapshotConfig()
	local function eval(sources, off)
		if off and next(off) then
			restoreConfig(snap); applyConfig(off); recalc()
		end
		local override = { removeNodes = {} }
		for _, s in ipairs(sources or {}) do
			if s.kind == "node" then
				override.removeNodes[nodeByName[s.name]] = true
			elseif s.kind == "slot" then
				override.repSlotName = s.slot
				override.repItem = s.raw and new("Item"):Item(s.raw) or nil
			end
		end
		local v = fastDps(build.calcsTab:GetMiscCalculator(), override, fastOpts)
		if off and next(off) then restoreConfig(snap); recalc() end
		return v
	end
	local input = build.configTab.input
	local base = eval({}) or 0
	local rows = {}
	for _, e in ipairs(req.entries or {}) do
		local present, missing = true, nil
		for _, s in ipairs(e.sources or {}) do
			if s.kind == "node" and not nodeByName[s.name] then present = false; missing = s.name end
		end
		local row = { id = e.id, present = present, missing = missing, active = {} }
		if present then
			for var, offv in pairs(e.off or {}) do
				local cur = input[var]
				local offval = offv ~= json.null and offv or nil
				if cur ~= nil and cur ~= offval and cur ~= false then row.active[#row.active + 1] = var end
			end
			table.sort(row.active)
			local function m(v) if not v or v <= 0 then return "inf" end return base / v end
			row.alone = m(eval(e.sources))
			row.cond = m(eval(nil, e.off))
			local all = {}
			for _, s in ipairs(e.sources or {}) do all[#all + 1] = s end
			for _, s in ipairs(e.extra or {}) do all[#all + 1] = s end
			row.with = m(eval(all, e.off))
		end
		rows[#rows + 1] = row
	end
	return { base = base, rows = rows, detected = req.detect and detectEnablers() or nil }
end

-- Try every unique from PoB's database in each equipment slot of the current build.
-- Returns the top uniques per slot by main-skill DPS multiplier (vs the item currently there).
local SWEEP_SLOTS = { "Weapon 1", "Weapon 2", "Helmet", "Body Armour", "Gloves", "Boots", "Amulet", "Ring 1", "Belt" }
local uniqueCache
local function uniqueItems()
	-- PoB's DB items are parsed lazily (mod lists not built); rebuild each from its raw text once.
	if uniqueCache then return uniqueCache end
	uniqueCache = {}
	for name, item in pairs(main.uniqueDB and main.uniqueDB.list or {}) do
		local ok, it = pcall(function() return new("Item"):Item(item:BuildRaw()) end)
		if ok and it and it.base then uniqueCache[name] = it end
	end
	return uniqueCache
end
uniqueSweep = function(slots, top, maxLevel)
	local db = uniqueItems()
	local calcFunc = build.calcsTab:GetMiscCalculator()
	local fastOpts = { requirementsGems = true, skipEHP = true } -- items must be rebuilt per candidate
	local base = skillDps()
	local out = {}
	for _, slotName in ipairs(slots or SWEEP_SLOTS) do
		local rows = {}
		for name, item in pairs(db) do
			local lvl = item.requirements and item.requirements.level or 0
			if lvl <= (maxLevel or 100) and build.itemsTab:IsItemValidForSlot(item, slotName) then
				local ok, o = pcall(calcFunc, { repSlotName = slotName, repItem = item }, false, fastOpts)
				if ok and o then
					local v = o.CombinedDPS
					if not v or v == 0 then v = o.FullDPS or o.TotalDPS or 0 end
					if v == v and v ~= math.huge and base > 0 and v > base * 1.01 then
						rows[#rows + 1] = { name = name, mult = v / base }
					end
				end
			end
		end
		table.sort(rows, function(a, b) return a.mult > b.mult end)
		local cut = {}
		for i = 1, math.min(top or 5, #rows) do cut[i] = rows[i] end
		out[#out + 1] = { slot = slotName, uniques = cut }
	end
	return out
end

function commands.unique_sweep(req)
	recalc()
	return { base = skillDps(), slots = uniqueSweep(req.slots, req.top, req.maxLevel) }
end

-- Debug/eval hook: run a Lua snippet inside the daemon (local use only).
-- What the build's FullDPS is made of (PoB sums every group the author ticked "include in Full DPS").
function commands.full_dps()
	recalc()
	local o = build.calcsTab.mainOutput or {}
	local rows = {}
	for _, r in ipairs(o.SkillDPS or {}) do
		rows[#rows + 1] = { name = r.name, dps = num(r.dps), count = r.count, trigger = r.trigger, skillPart = r.skillPart }
	end
	return { full = num(o.FullDPS), combined = num(o.CombinedDPS), skills = rows,
		extras = { culling = num(o.CullingDPS), ignite = num(o.IgniteDPS), bleed = num(o.BleedDPS), poison = num(o.PoisonDPS) } }
end

function commands.eval(req)
	local f = assert(loadstring(req.code))
	setfenv(f, setmetatable({ recalc = recalc, skillDps = skillDps, req = req }, { __index = _G }))
	return f()
end

function commands.ping()
	return { pong = true, version = launch.versionNumber }
end

---------------------------------------------------------------------------
-- Main loop
---------------------------------------------------------------------------
local function respond(tbl)
	out:write(json.encode(tbl, { exception = function() return "null" end }), "\n")
	out:flush()
end

respond({ id = 0, ok = true, result = { ready = true, version = launch.versionNumber } })

for line in io.lines() do
	if line:match("%S") then
		local req, _, err = json.decode(line, 1, json.null)
		if not req then
			respond({ id = json.null, ok = false, error = "bad json: " .. tostring(err) })
		else
			local fn = commands[req.cmd]
			if not fn then
				respond({ id = req.id, ok = false, error = "unknown cmd " .. tostring(req.cmd) })
			else
				local t0 = os.clock()
				local ok, res = xpcall(function() return fn(req) end, debug.traceback)
				respond({ id = req.id, ok = ok, result = ok and res or nil, error = (not ok) and res or nil,
					ms = math.floor((os.clock() - t0) * 1000) })
			end
		end
	end
end
