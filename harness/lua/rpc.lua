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

local function statsOf(o, fields)
	local res = {}
	local wantMinion = fields == nil
	for _, k in ipairs(fields or STAT_FIELDS) do
		if k == "MinionDPS" then wantMinion = true end
		local v = num(o[k])
		if v ~= nil then res[k] = v end
	end
	-- a minion main skill's damage is the minion's (PoB keeps CombinedDPS 0 unless the author ticks "include in
	-- Full DPS"); per minion, as outDps reads it for the leveling probes
	if wantMinion and o.Minion then
		local m = num(o.Minion.CombinedDPS) or num(o.Minion.TotalDPS)
		if type(m) == "number" and m > 0 then res.MinionDPS = m end   -- num() passes NaN/inf on as strings
	end
	return res
end

local function collectStats(fields)
	return statsOf(build.calcsTab.mainOutput or {}, fields)
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
			entry.stats = statsOf(o, req.fields)
		else
			entry.error = tostring(o)
		end
		res[#res + 1] = entry
	end
	return { base = statsOf(baseOut, req.fields), candidates = res }
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

-- Prefix/Suffix item mods by trade hash (data.itemMods.Item), for "can this affix drop on this base".
local affixesByHash
local function dropAffixes(hash)
	if not affixesByHash then
		affixesByHash = {}
		for _, mod in pairsSortByKey(data.itemMods.Item) do
			if mod.type == "Prefix" or mod.type == "Suffix" then
				for h in pairs(mod.tradeHashes or {}) do
					local k = tostring(h)
					affixesByHash[k] = affixesByHash[k] or {}
					table.insert(affixesByHash[k], mod)
				end
			end
		end
	end
	return affixesByHash[hash] or {}
end

-- Item:GetModSpawnWeight on a bare tag set: the first weight key the base has decides.
local function spawnWeight(mod, tags)
	local weight = 0
	for i, key in ipairs(mod.weightKey or {}) do
		if tags[key] then weight = mod.weightVal[i] break end
	end
	for i, key in ipairs(mod.weightMultiplierKey or {}) do
		if tags[key] then weight = weight * mod.weightMultiplierVal[i] / 100 break end
	end
	return weight
end

-- Bases an affix is checked against: the equipped item's base, or for an empty slot every base of the trade
-- category PoB searches that slot with (an empty weapon slot: PoB's one-hand weapon list).
local ONE_HAND = { ["One Hand Mace"] = true, Wand = true, Sceptre = true, Flail = true, Spear = true }
local function slotBaseTags(slot, item, category)
	if item and item.base then return { item.base.tags } end
	local tradeHelpers = LoadModule("Classes/TradeHelpers")
	local list = {}
	for _, base in pairsSortByKey(data.itemBases) do
		if not base.hidden and base.tags then
			local _, cat = tradeHelpers.getTradeCategory(slot.slotName, { type = base.type, base = base })
			if cat == category or (category == "1HWeapon" and ONE_HAND[base.type]) then list[#list + 1] = base.tags end
		end
	end
	return list
end

-- The affixes the generator measured, as a player would look for them: explicit affixes only (implicit, enchant
-- and rune ids dropped), only those a Prefix/Suffix with non-zero spawn weight on the slot's base carries (no
-- Desecrated, Genesis or crafted-only lines), merged by trade text, ordered by meanStatDiff then text.
local function topAffixes(slot, n)
	local textById = {}
	for _, group in pairs(tradeGen.modData or {}) do
		for _, entry in pairs(group) do
			if type(entry) == "table" and entry.tradeMod then textById[entry.tradeMod.id] = entry.tradeMod.text end
		end
	end
	local item = slot.selItemId and build.itemsTab.items[slot.selItemId]
	local tagSets = slotBaseTags(slot, item, tradeGen.calcContext.itemCategory)
	local function drops(id)
		for h in id:gsub("^.-stat_", ""):gmatch("%d+") do
			for _, mod in ipairs(dropAffixes(h)) do
				for _, tags in ipairs(tagSets) do
					if spawnWeight(mod, tags) > 0 then return true end
				end
			end
		end
		return false
	end
	local rows = {}
	for _, w in ipairs(tradeGen.modWeights or {}) do
		local id = w.tradeModId
		if id:match("^explicit%.") and textById[id] and drops(id) then
			rows[#rows + 1] = { id = id, text = textById[id], meanStatDiff = w.meanStatDiff }
		end
	end
	table.sort(rows, function(a, b)
		if a.meanStatDiff ~= b.meanStatDiff then return a.meanStatDiff > b.meanStatDiff end
		if a.text ~= b.text then return a.text < b.text end
		return a.id < b.id
	end)
	local out, seen = {}, {}
	for _, r in ipairs(rows) do
		if not seen[r.text] and #out < n then
			seen[r.text] = true
			out[#out + 1] = r
		end
	end
	return out
end

local tradeQueryInner
function commands.trade_query(req)
	-- the check-up pins its main skill for the call (PoB falls back to the main skill when no skill is in Full DPS)
	local savedMain = build.mainSocketGroup
	if req.group then
		build.mainSocketGroup = req.group
		recalc()
	end
	local ok, res = pcall(tradeQueryInner, req)
	if req.group then
		build.mainSocketGroup = savedMain
		recalc()
	end
	if not ok then error(res, 0) end
	return res
end

tradeQueryInner = function(req)
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
	-- what the link actually searches: the weighted stat filters of the generated query, heaviest first (PoB orders
	-- modWeights by mean stat change, and the query keeps a subset under its complexity budget, some remapped to
	-- pseudo mods)
	local byId = {}
	for _, w in ipairs(tradeGen.modWeights or {}) do byId[w.tradeModId] = byId[w.tradeModId] or w end
	local weights = {}
	local cq = captured.query and (captured.query.query or captured.query)   -- the query body comes wrapped or bare
	for _, group in ipairs((cq and cq.stats) or {}) do
		for _, f in ipairs(group.filters or {}) do
			local wv = f.value and f.value.weight
			if f.id and wv then
				local w = byId[f.id]
				weights[#weights + 1] = { id = f.id, text = textById[f.id] or f.id, weight = wv, meanStatDiff = w and w.meanStatDiff }
			end
		end
	end
	table.sort(weights, function(x, y) if x.weight ~= y.weight then return x.weight > y.weight end return x.id < y.id end)
	for i = #weights, (req.topWeights or 25) + 1, -1 do weights[i] = nil end
	local url
	if captured.query and req.league then
		-- Same URL shape as PoB's CompareBuySimilar: trade2/search/<league>/<b64gzip(query)>
		local q = json.encode(captured.query)
		local league = req.league:gsub("[^%w%-%.%_%~ ]", function(c) return string.format("%%%02X", string.byte(c)) end):gsub(" ", "+")
		url = "https://www.pathofexile.com/trade2/search/" .. league .. "/" .. tradeHelpers.B64GzipEncode(q)
	end
	local res = { query = captured.query, error = captured.err, weights = weights, url = url }
	if req.topMods then
		res.mods = topAffixes(slot, req.topMods)
		local bo = tradeGen.calcContext.baseOutput or {}
		-- the DPS terms PoB's generator weighs: FullDPS when the calculator has it, else the main skill's
		res.fullDPS = num(bo.FullDPS)
		res.mainDPS = (num(bo.TotalDPS) or 0) + (num(bo.TotalDotDPS) or 0) + (num(bo.CombinedDPS) or 0)
	end
	return res
end

---------------------------------------------------------------------------
-- Skill scan: PoB-data-only strength estimate for active skills on a
-- standardised character (no ladder data involved).
---------------------------------------------------------------------------
local templateWeaponCache = {}
local function templateWeapon(weaponType, maxLevel)
	local key = weaponType .. ":" .. maxLevel
	if templateWeaponCache[key] ~= nil then return templateWeaponCache[key] end
	local best, bestLevel, bestAvg
	local wantType, wantSub = weaponType, nil
	if weaponType == "Quarterstaff" then wantType, wantSub = "Staff", "Warstaff" end
	-- shield skills (Shield Wall, Shield Charge) need an armour shield, which is not a weapon base
	local shield = weaponType == "Armoured Shield"
	if shield then wantType = "Shield" end
	for name, base in pairs(data.itemBases) do
		if base.type == wantType and (not wantSub or base.subType == wantSub)
			and not (wantType == "Staff" and not wantSub and base.subType == "Warstaff")
			and not (shield and not (base.subType or ""):find("Armour"))
			and not base.hidden and (base.weapon or shield) then
			local lvl = base.req and base.req.level or 1
			-- ties on level (Wrapped vs Long Quarterstaff, both level 1) were broken by `pairs` order, which
			-- changed between runs and moved attack DPS by up to x0.7: take the higher average physical damage,
			-- then the name, so the template is the same every run
			local w = base.weapon or {}
			local avg = ((w.PhysicalMin or 0) + (w.PhysicalMax or 0)) / 2
			if lvl <= maxLevel and (not bestLevel or lvl > bestLevel
					or (lvl == bestLevel and (avg > bestAvg or (avg == bestAvg and name < best)))) then
				best, bestLevel, bestAvg = name, lvl, avg
			end
		end
	end
	templateWeaponCache[key] = best or false
	return best
end

-- Weapon type a skill is probed with: the first type it accepts. "Any Martial Weapon" has no item base of
-- its own; the caller names the martial weapon the class would hold (req.martialWeapon).
local function requiredWeapon(gemData, req)
	local w = gemData.weaponRequirements:match("^([^,]+)")
	if w == "Any Martial Weapon" then w = req.martialWeapon or "One Hand Mace" end
	return w
end

-- Four names are shared (Unleash is both a spell and a support; Lightning Bolt, Mace Strike, Spear Stab have
-- variants). `pairs` order varies per process, so the lookup used to return either; a support named in a probe
-- result sometimes resolved to the Unleash spell and did nothing. Prefer the requested kind, then the lowest id.
local function findGemByName(name, support)
	local best, bestG
	for id, g in pairs(data.gems) do
		if g.name == name then
			local isSup = g.grantedEffect and g.grantedEffect.support and true or false
			local rank = (isSup == (support and true or false)) and 0 or 1
			if not best or rank < best[1] or (rank == best[1] and id < best[2]) then best, bestG = { rank, id }, g end
		end
	end
	if best then return best[2], bestG end
end

-- Highest gem level a character of `charLevel` can use (PoB's per-level requirement), capped at maxLevel.
local function gemLevelFor(g, charLevel, maxLevel)
	local levels = g.grantedEffect and g.grantedEffect.levels
	local best = 1
	for l = 1, math.min(maxLevel or 20, g.naturalMaxLevel or 20) do
		local lv = levels and levels[l]
		if lv and (lv.levelRequirement or 0) <= charLevel then best = l end
	end
	return best
end

-- Campaign stages limit which gems exist yet: skill gem Tier (uncut skill gem level needed) and
-- support Tier (uncut support gem level). Tier 0 gems are item/ascendancy-granted or untiered.
local function skillAllowed(g, req)
	if req.extraSkills and req.extraSkills[g.name] then return true end
	if not req.maxSkillTier then return true end
	return g.Tier and g.Tier >= 1 and g.Tier <= req.maxSkillTier
end
-- Supports that give the skill a cooldown (Hourglass 10 s, Expanse 8 s, Excise, Execrate, Nova Projectiles II...)
-- trade use rate for damage or area. Nothing here checks how much of that cooldown the skill's effect covers
-- (Contagion is cast once per pack in the leveling model; Profane Ritual lasts 1.3 s), so the pickers never offer them.
-- Read from gem data: a cooldown on any level, or the Cooldown skill type added. Supports a player already has socketed
-- are still scored as they are.
local function grantsCooldown(g)
	local ge = g.grantedEffect
	if not ge then return false end
	for _, lv in pairs(ge.levels or {}) do
		if lv.cooldown then return true end
	end
	for _, t in ipairs(ge.addSkillTypes or {}) do
		if t == SkillType.Cooldown then return true end
	end
	return false
end

local function supportAllowed(g, req)
	if grantsCooldown(g) then return false end
	if not req.maxSupportTier then return true end
	return g.Tier and g.Tier >= 1 and g.Tier <= req.maxSupportTier
end

-- Support gems with levels (a few untiered ones such as Unleash) are capped like skill gems in campaign stages.
local function supportLevel(g, req)
	if req.capGemByLevel then return gemLevelFor(g, req.level or 90, req.gemLevel or 20) end
	return g.naturalMaxLevel
end

local function gemLevelForReq(g, req)
	if req.capGemByLevel then return gemLevelFor(g, req.level or 90, req.gemLevel or 20) end
	return req.gemLevel or 20
end

-- Main skill DPS from a calc output; minion skills fall back to the minion's own DPS.
function outDps(o)
	local v = o.CombinedDPS
	if not v or v == 0 then v = o.FullDPS or o.TotalDPS or 0 end
	if v == 0 and o.Minion then v = o.Minion.CombinedDPS or o.Minion.TotalDPS or 0 end
	return v
end

-- Value a support choice is judged by. "clear" weighs DPS by the monsters a use reaches in a pack
-- (area radius, projectiles, pierce, chain), so supports that trade area for damage lose credit.
function supportValue(o, req, v)
	v = v or outDps(o)
	if req.supportObjective ~= "clear" then return v end
	local pack, density = req.pack or 6, req.density or 0.3
	local r = o.AreaOfEffectRadiusMetres or 0
	local tArea = r > 0 and math.min(pack, math.max(1, density * math.pi * r * r)) or 1
	local proj = o.ProjectileCount or 0
	local tProj = proj > 0 and math.min(pack, proj * (1 + math.min(o.PierceCount or 0, 5)) + (o.ChainMax or 0)) or 1
	return v * math.max(tArea, tProj, 1)
end

-- Value of the main skill for support, passive and ascendancy choices: the first stat set, plus the best
-- DoT-only set when the skill has one (its DPS capped at the DoT, since a DoT part's combined DPS can repeat
-- the hit). Judging the first set alone picked hit supports for Essence Drain, whose clear comes from its DoT
-- set. Skills without a DoT-only set: identical to supportValue on one calc.
-- Labels of stat sets the ranking treats as alternatives, not the normal use (leveling.CONDITIONAL).
local CONDITIONAL_SETS = { "Charged", "Infused", "Enraged", "Empowered", "Frenzy", "Primed", "Fully", "Ground" }

-- life one DoT cast should cover: a magic monster at the probe's level (leveling.RARITY_LIFE magic = 2.48)
DOT_KILL_LIFE = nil
local MAGIC_LIFE = 2.48

-- setsValue's settings come from the request of the skill being set up, never from whichever command ran last:
-- scanOne and setupSkill call this, so every command that picks supports or passives (skill_scan, build_up,
-- campaign, ascendancy_lift, ascendancy_checkpoints, leveling_probe) values a DoT set the same way.
local function setsContext(req)
	SETS_FIRST_ONLY = req.firstSetOnly and true or nil
	DOT_KILL_LIFE = (data.monsterLifeTable[req.level or 90] or 0) * MAGIC_LIFE
end

-- Sort helper for value-ranked lists built from `pairs` (string-keyed, so per-process order under LuaJIT's
-- seeded hash): ties fall back to a name, then an id, so equal values come out in the same order every run.
local function tieBreak(a, b)
	local na, nb = tostring(a.name or a.ascendancy or a.gem or ""), tostring(b.name or b.ascendancy or b.gem or "")
	if na ~= nb then return na < nb end
	return (a.id or 0) < (b.id or 0)
end

local function finite(v)
	return v and v == v and v ~= math.huge and v ~= -math.huge
end

function setsValue(calcFunc, req, override, opts)
	local group = build.skillsTab.socketGroupList[build.mainSocketGroup or 1]
	local gi = group and group.gemList[1]
	local ge = gi and gi.gemData and gi.gemData.grantedEffect
	local n = ge and ge.statSets and #ge.statSets or 0
	local ok, o1 = pcall(calcFunc, override, false, opts)
	if not ok or not o1 then return nil end
	local first = supportValue(o1, req)
	if not finite(first) then first = nil end
	if n <= 1 or req.firstSetOnly or SETS_FIRST_ONLY then return first end
	-- DoT-only exactly as the ranking classifies it: TotalDot (not TotalDotDPS, which counts ailments) and no hit
	local function dotOnly(o) return (o.TotalDot or 0) > 0 and not ((o.AverageHit or 0) > 0) end
	-- same pool as leveling._main_variants: conditional sets dropped
	local saved = gi.statSet
	local bestDot
	-- when the first set's hit is counted, its ailments (poison, bleed) are already in its combined DPS; a DoT-only
	-- set's TotalDotDPS repeats them (Vine Arrow's Vines), so it adds only its own DoT (TotalDot)
	local hitCounted = not dotOnly(o1)
	for i = 1, n do
		local label = ge.statSets[i].label or ""
		local cond = false
		for _, k in ipairs(CONDITIONAL_SETS) do
			if label:find(k, 1, true) then cond = true break end
		end
		if not cond then
			gi.statSet = { [ge.id] = i }
			local okI, o = pcall(calcFunc, override, false, opts)
			if okI and o and dotOnly(o) then
				-- capped at TotalDotDPS or TotalDot, as _dot_dps does (TotalDot alone next to a counted hit)
				local d = (not hitCounted and (o.TotalDotDPS or 0) > 0) and o.TotalDotDPS or o.TotalDot or 0
				d = d > 0 and math.min(outDps(o), d) or outDps(o)
				-- clear counts a DoT whose one cast kills (leveling.metrics, fire and forget): DoT DPS gets full
				-- credit only if DPS x duration covers a magic monster's life, so a support that buys DPS with
				-- duration (Swift Affliction) does not win when it stops one cast from killing
				local hp = not req.boss and DOT_KILL_LIFE
				if hp and hp > 0 and (o.Duration or 0) > 0 then d = d * math.min(1, d * o.Duration / hp) end
				local v = supportValue(o, req, d)
				if finite(v) and (not bestDot or v > bestDot) then bestDot = v end
			end
		end
	end
	gi.statSet = saved
	-- no DoT-only set: the first set alone, as before. Judging every hit set too was tried (round 4) and let
	-- supports switch on enemy-state-gated sets (Siphoning Strike's Shockwave) and pick sets the ranking does
	-- not use (Ember Fusillade's chaining Beam); hit sets stay on the first set.
	if not bestDot then return first end
	return (dotOnly(o1) and 0 or (first or 0)) + bestDot
end

local function skillDps()
	local o = build.calcsTab.mainOutput or {}
	local v = outDps(o)
	if v ~= v or v == math.huge then v = 0 end
	return v
end

-- DPS through the misc calculator. Baselines for fast-calc comparisons must come from here too:
-- the fast path may return CombinedDPS where the full recalc returns FullDPS.
local function fastDps(calcFunc, override, opts)
	local ok, o = pcall(calcFunc, override or {}, false, opts)
	if not ok or not o then return nil end
	local v = outDps(o)
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
	setsContext(req)
	build.characterLevel = req.level or 90
	applyConfig(req.enemyIsBoss and { enemyIsBoss = req.enemyIsBoss } or nil, req.templateMods or "")
	-- a shapeshift skill is only used in its form: the form's own condition is always true
	if req.impliedConditions and gemData.tags and gemData.tags.shapeshift then
		build.configTab.input.conditionShapeshifted = true
	end
	-- weapon for attacks
	local weaponType
	if gemData.weaponRequirements then
		weaponType = requiredWeapon(gemData, req)
		local baseName = weaponType and templateWeapon(weaponType, req.weaponLevel or 65)
		if baseName then
			build.itemsTab:CreateDisplayItemFromRaw("Rarity: RARE\nTemplate Weapon\n" .. baseName .. "\n" .. (req.weaponMods or ""))
			build.itemsTab:AddDisplayItem()
		end
	end
	build.skillsTab:PasteSocketGroup(gemData.name .. " " .. gemLevelForReq(gemData, req) .. "/" .. (req.gemQuality or 20) .. "  1")
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
			and (req.allowLineage or not (g.tags and g.tags.lineage)) and supportAllowed(g, req)
			and calcLib.canGrantedEffectSupportActiveSkill(g.grantedEffect, active) then
			candidates[#candidates + 1] = { id = id, g = g }
		end
	end
	-- fixed order: ties (Cold vs Fire Attunement on a physical attack) otherwise go to whichever `pairs` over
	-- string keys yields first, which varies per process
	table.sort(candidates, function(a, b) return a.id < b.id end)
	local fastOpts = { nodeAlloc = true, requirementsItems = true, requirementsGems = true, skipEHP = true }
	local chosen = {}
	for _ = 1, (req.supports or 5) do
		local calcFunc = build.calcsTab:GetMiscCalculator()
		local bestDps, best = 0, nil
		bestDps = setsValue(calcFunc, req, nil, fastOpts) or skillDps()
		local idx = #group.gemList + 1
		for _, c in ipairs(candidates) do
			if not chosen[c.id] then
				group.gemList[idx] = { level = supportLevel(c.g, req), quality = 0, count = 1, enabled = true,
					enableGlobal1 = true, enableGlobal2 = true, gemId = c.id, nameSpec = c.g.name,
					skillId = c.g.grantedEffectId, gemData = c.g }
				local v = setsValue(calcFunc, req, nil, fastOpts)
				if v and v == v and v ~= math.huge and v > bestDps * 1.001 then bestDps, best = v, c end
			end
		end
		group.gemList[idx] = nil
		if not best then break end
		chosen[best.id] = true
		group.gemList[idx] = { level = supportLevel(best.g, req), quality = 0, count = 1, enabled = true,
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
				and g.tags and g.tags.grants_active_skill and skillAllowed(g, req) then
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
	setsContext(req)
	if classId then
		build.spec:SelectClass(classId)
		build.spec:SelectAscendClass(ascendId or 0)
	end
	build.characterLevel = req.level or 90
	applyConfig(req.enemyIsBoss and { enemyIsBoss = req.enemyIsBoss } or nil, req.templateMods or "")
	-- a shapeshift skill is only used in its form: the form's own condition is always true
	if req.impliedConditions and gemData.tags and gemData.tags.shapeshift then
		build.configTab.input.conditionShapeshifted = true
	end
	if gemData.weaponRequirements then
		local weaponType = requiredWeapon(gemData, req)
		local baseName = weaponType and templateWeapon(weaponType, req.weaponLevel or 65)
		if baseName then
			build.itemsTab:CreateDisplayItemFromRaw("Rarity: RARE\nTemplate Weapon\n" .. baseName .. "\n" .. (req.weaponMods or ""))
			build.itemsTab:AddDisplayItem()
		end
	end
	build.skillsTab:PasteSocketGroup(gemData.name .. " " .. gemLevelForReq(gemData, req) .. "/" .. (req.gemQuality or 20) .. "  1")
	build.mainSocketGroup = 1
	local group = build.skillsTab.socketGroupList[1]
	for _, id in ipairs(supportIds or {}) do
		local g = data.gems[id]
		if g then
			group.gemList[#group.gemList + 1] = { level = supportLevel(g, req), quality = 0, count = 1, enabled = true,
				enableGlobal1 = true, enableGlobal2 = true, gemId = id, nameSpec = g.name, skillId = g.grantedEffectId }
		end
	end
	build.skillsTab:ProcessSocketGroup(group)
	build.spec:BuildAllDependsAndPaths()
	recalc()
	recalc()
	return group
end

-- fill: spend every point the way a player does (a notable with the small node in front of it, never two
-- small nodes when a notable fits), taking the notable that helps this skill most even when none does.
local function greedyAscendancy(points, fill)
	local chosen, spent, firstCandidates = {}, 0, nil
	local fastOpts = { requirementsItems = true, requirementsGems = true, skipEHP = true }
	while spent < points do
		local calcFunc = build.calcsTab:GetMiscCalculator()
		local base = setsValue(calcFunc, {}, {}, fastOpts) or skillDps()
		local best, bestGain, bestCost
		local candidates = 0
		local notableFits = false
		if fill then
			for _, node in pairs(build.spec.nodes) do
				if node.ascendancyName == build.spec.curAscendClassName and not node.alloc and node.path
					and node.isNotable and #node.path > 0 and spent + #node.path <= points then notableFits = true end
			end
		end
		local ids = {}
		for id in pairs(build.spec.nodes) do ids[#ids + 1] = id end
		table.sort(ids)
		for _, id in ipairs(ids) do
			local node = build.spec.nodes[id]
			if node.ascendancyName == build.spec.curAscendClassName and not node.alloc and node.path
				and not node.isAscendancyStart and (not notableFits or node.isNotable) then
				local cost = #node.path
				if cost > 0 and spent + cost <= points then
					candidates = candidates + 1
					local add = {}
					for _, pn in ipairs(node.path) do add[pn] = true end
					local v = setsValue(calcFunc, {}, { addNodes = add }, fastOpts)
					if v then
						if v == v and v ~= math.huge then
							local gain = (v - base) / cost
							if not bestGain or gain > bestGain then best, bestGain, bestCost = node, gain, cost end
						end
					end
				end
			end
		end
		firstCandidates = firstCandidates or candidates
		if not best or (bestGain <= 0 and not fill) then break end
		for _, pn in ipairs(best.path) do
			if pn.isNotable then chosen[#chosen + 1] = pn.dn
			elseif pn == best then chosen[#chosen + 1] = (fill and "small: " or "") .. pn.dn end
		end
		build.spec:AllocNode(best)
		build.spec:BuildAllDependsAndPaths()
		recalc()
		spent = spent + bestCost
	end
	return chosen, spent, firstCandidates
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
				local sid = findGemByName(s.name, true)
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
			table.sort(rows, function(a, b)
				if (a.lift or 0) ~= (b.lift or 0) then return (a.lift or 0) > (b.lift or 0) end
				return tieBreak(a, b)
			end)
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
local function greedyTree(points, maxPath, allowed)
	local picks, spent = {}, 0
	local fastOpts = { requirementsItems = true, requirementsGems = true, skipEHP = true }
	while spent < points do
		local calcFunc = build.calcsTab:GetMiscCalculator()
		local base = setsValue(calcFunc, {}, {}, fastOpts) or skillDps()
		local best, bestGain, bestCost, bestV
		local ids = {}
		for id in pairs(build.spec.nodes) do ids[#ids + 1] = id end
		table.sort(ids)
		for _, id in ipairs(ids) do
			local node = build.spec.nodes[id]
			if not node.ascendancyName and not node.alloc and node.path
				and (node.type == "Notable" or node.type == "Keystone")
				and (not allowed or allowed[node.dn]) then
				local cost = #node.path
				if cost > 0 and cost <= (maxPath or 7) and spent + cost <= points then
					local add = {}
					for _, pn in ipairs(node.path) do add[pn] = true end
					local v = setsValue(calcFunc, {}, { addNodes = add }, fastOpts)
					if v then
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
		local sid = findGemByName(sp.name, true)
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

-- Campaign (pre-ascendancy) scan: which skill is strongest at a campaign stage, per class start.
-- Phase 1 ranks every gem the stage allows on a class-less character (level-capped gem, tiered
-- supports, a plain weapon base of the stage's level). Phase 2 takes the top skills and, for each
-- class, spends the stage's passive points greedily from that class's start (no ascendancy).
-- Classes do not restrict weapons or skills; only the tree start differs.
function commands.campaign(req)
	local scanRes = commands.skill_scan(req).results
	local ranked = {}
	for _, r in ipairs(scanRes) do
		if r.supportedDPS and r.supportedDPS > 0 then ranked[#ranked + 1] = r end
	end
	table.sort(ranked, function(a, b)
		if a.supportedDPS ~= b.supportedDPS then return a.supportedDPS > b.supportedDPS end
		return tieBreak(a, b)
	end)
	local top = {}
	for i = 1, math.min(req.top or 20, #ranked) do top[i] = ranked[i] end
	local classes = {}
	for cid, class in pairs(build.spec.tree.classes) do
		if not req.classes or req.classes[class.name] then classes[#classes + 1] = { id = cid, name = class.name } end
	end
	table.sort(classes, function(a, b) return a.name < b.name end)
	local rows = {}
	for _, r in ipairs(top) do
		local gemId, gemData = findGemByName(r.gem)
		local supportIds = {}
		for _, sp in ipairs(r.supports or {}) do
			local sid = findGemByName(sp.name, true)
			if sid then supportIds[#supportIds + 1] = sid end
		end
		local perClass = {}
		for _, c in ipairs(classes) do
			local ok, err = pcall(function()
				setupSkill(gemData, supportIds, req, c.id, 0)
				local before = skillDps()
				local picks, spent = greedyTree(req.treePoints or 10, req.maxPath or 7)
				perClass[#perClass + 1] = { class = c.name, before = before, dps = skillDps(), spent = spent,
					picks = picks }
			end)
			if not ok then perClass[#perClass + 1] = { class = c.name, error = tostring(err) } end
			collectgarbage("collect")
		end
		rows[#rows + 1] = { skill = r.gem, gemLevel = gemLevelForReq(gemData, req), weaponType = r.weaponType,
			tags = r.tags, supports = r.supports, supportedDPS = r.supportedDPS, classes = perClass }
		if req.progress then io.stderr:write("campaign ", r.gem, "\n") end
	end
	return { scanned = #scanRes, withDamage = #ranked, results = rows }
end

---------------------------------------------------------------------------
-- Leveling probe: raw facts about one skill at a campaign stage, for scoring outside PoB.
-- Every stat set of the main skill is measured (Essence Drain's DoT is its second stat set),
-- minion output is included, and clear-related outputs (area, projectiles, pierce, chain,
-- duration), mana sustain and attribute requirements are returned with the white monster life
-- for the stage level.
---------------------------------------------------------------------------
local PROBE_FIELDS = { "CombinedDPS", "TotalDPS", "TotalDot", "TotalDotDPS", "WithDotDPS", "FullDPS", "AverageHit",
	"AverageDamage", "Speed", "HitChance", "AreaOfEffectRadiusMetres", "ProjectileCount", "PierceCount", "ChainMax",
	"Duration", "ManaCost", "ManaPerSecondCost", "ManaRegenRecovery", "Mana", "ManaUnreserved", "Str", "Dex", "Int",
	"ReqStr", "ReqDex", "ReqInt", "Life", "TotalEHP", "ActiveMinionLimit", "Cooldown", "StoredUses" }
local MINION_FIELDS = { "CombinedDPS", "TotalDPS", "TotalDot", "AverageHit", "Speed", "AreaOfEffectRadiusMetres",
	"ProjectileCount", "Life" }

local function probeOutputs()
	local o = build.calcsTab.mainOutput or {}
	local r = {}
	for _, k in ipairs(PROBE_FIELDS) do
		local v = num(o[k])
		if v ~= nil then r[k] = v end
	end
	if o.Minion then
		r.minion = {}
		for _, k in ipairs(MINION_FIELDS) do
			local v = num(o.Minion[k])
			if v ~= nil then r.minion[k] = v end
		end
	end
	r.dps = outDps(o)
	return r
end

local skillTypeName
local function mainSkillTypes()
	if not skillTypeName then
		skillTypeName = {}
		for k, v in pairs(SkillType) do skillTypeName[v] = k end
	end
	local ms = build.calcsTab.mainEnv and build.calcsTab.mainEnv.player.mainSkill
	local t = {}
	for k, on in pairs(ms and ms.skillTypes or {}) do
		if on and skillTypeName[k] then t[#t + 1] = skillTypeName[k] end
	end
	table.sort(t)
	return t, ms and ms.activeEffect.grantedEffect.name
end

local function probeVariants(group, gi)
	gi = gi or group.gemList[1]
	local ge = gi and gi.gemData and gi.gemData.grantedEffect
	local out = {}
	local sets = ge and ge.statSets or {}
	for i = 1, math.max(#sets, 1) do
		if ge and #sets > 0 then gi.statSet = { [ge.id] = i } end
		recalc()
		local row = probeOutputs()
		row.set = i
		row.label = sets[i] and sets[i].label
		out[#out + 1] = row
	end
	if ge and ge.parts and #ge.parts > 1 then
		gi.statSet = nil
		for k = 2, #ge.parts do
			gi.skillPart = k
			recalc()
			local row = probeOutputs()
			row.part = k
			row.label = ge.parts[k].name
			out[#out + 1] = row
		end
		gi.skillPart = nil
	end
	gi.statSet = nil
	recalc()
	return out
end

-- Names of active skills a campaign stage allows (same filter as skill_scan).
function commands.stage_skills(req)
	local names = {}
	for _, g in pairs(data.gems) do
		if g.grantedEffect and not g.grantedEffect.support and not g.grantedEffect.hidden
			and (g.gemType == "Attack" or g.gemType == "Spell" or g.gemType == "Minion")
			and g.tags and g.tags.grants_active_skill and skillAllowed(g, req) then
			names[g.name] = true
		end
	end
	local out = {}
	for n in pairs(names) do out[#out + 1] = n end
	table.sort(out)
	local classes = {}
	for _, c in pairs(build.spec.tree.classes) do
		classes[#classes + 1] = { name = c.name, str = c.base_str, dex = c.base_dex, int = c.base_int }
	end
	table.sort(classes, function(a, b) return a.name < b.name end)
	return { skills = out, classes = classes }
end

-- Config checks gated on a flag an ascendancy node grants (Eldritch Empowerment: "Are you Sacrificing?")
-- describe what the node does every use; turn them on so the greedy pick sees it.
local function applyAscendancyFlags()
	local flags = {}
	for _, node in pairs(build.spec.nodes) do
		if node.ascendancyName == build.spec.curAscendClassName then
			for _, mod in ipairs(node.modList or {}) do
				if mod.type == "FLAG" then flags[mod.name] = true end
			end
		end
	end
	for _, opt in ipairs(configOptions) do
		local f = opt.ifFlag
		if opt.type == "check" and opt.var and type(f) == "string" and flags[f] then
			build.configTab.input[opt.var] = true
		end
	end
	recalc()
end

-- Ascendancy checkpoints: one skill on a class template, ascendancy points spent the way a player does
-- (notable-first, all points), recording DPS, EHP and the nodes taken at each trial (2/4/6/8 points).
-- DPS a checkpoint reports: the first stat set plus the best DoT-only set (as picks are judged), without the
-- one-cast-kill factor (boss) or clear weighting, so a DoT skill's lift counts its DoT (Essence Drain) in plain DPS.
-- Equal to skillDps() for skills without a DoT-only set.
local function reportDps()
	local opts = { requirementsItems = true, requirementsGems = true, skipEHP = true }
	return setsValue(build.calcsTab:GetMiscCalculator(), { boss = true }, {}, opts) or skillDps()
end

function commands.ascendancy_checkpoints(req)
	local gemId, gemData = findGemByName(req.skill or "")
	if not gemId then error("gem not found: " .. tostring(req.skill)) end
	local scan = scanOne(gemId, gemData, req)
	local supportIds = {}
	for _, sp in ipairs(scan.supports or {}) do
		local sid = findGemByName(sp.name, true)
		if sid then supportIds[#supportIds + 1] = sid end
	end
	local rows = {}
	for classId, class in pairs(build.spec.tree.classes) do
		for ascendId, asc in pairs(class.classes) do
			if ascendId ~= 0 and (not req.ascendancies or req.ascendancies[asc.name])
				and (not req.class or req.class == class.name) then
				local ok, err = pcall(function()
					setupSkill(gemData, supportIds, req, classId, ascendId)
					if req.impliedConditions then applyAscendancyFlags() end
					local before = reportDps()
					local ehp0 = num((build.calcsTab.mainOutput or {}).TotalEHP)
					local steps, spent = {}, 0
					for _, target in ipairs(req.steps or { 2, 4, 6, 8 }) do
						local picks, used, cand = greedyAscendancy(target - spent, true)
						spent = spent + used
						recalc()
						steps[#steps + 1] = { points = target, spent = spent, nodes = picks, candidates = cand, dps = reportDps(),
							ehp = num((build.calcsTab.mainOutput or {}).TotalEHP) }
					end
					rows[#rows + 1] = { ascendancy = asc.name, class = class.name, before = before, ehpBefore = ehp0,
						steps = steps }
				end)
				if not ok then rows[#rows + 1] = { ascendancy = asc.name, class = class.name, error = tostring(err) } end
				collectgarbage("collect")
			end
		end
	end
	table.sort(rows, function(a, b)
		local la = a.steps and a.steps[#a.steps] and a.before and a.before > 0 and a.steps[#a.steps].dps / a.before or 0
		local lb = b.steps and b.steps[#b.steps] and b.before and b.before > 0 and b.steps[#b.steps].dps / b.before or 0
		if la ~= lb then return la > lb end
		return tieBreak(a, b)
	end)
	return { skill = req.skill, supports = scan.supports, weaponType = scan.weaponType, ascendancies = rows }
end

-- Names of the supports grantsCooldown rejects (tests and gates pin this set).
function commands.cooldown_supports()
	local t = {}
	for _, g in pairs(data.gems) do
		local ge = g.grantedEffect
		if ge and ge.support and not ge.hidden and grantsCooldown(g) then t[#t + 1] = g.name end
	end
	table.sort(t)
	return { names = t }
end

function commands.leveling_probe(req)
	-- firstSetOnly: judge supports/passives on the first stat set, as before setsValue (a same-template baseline);
	-- read per skill by setsContext in scanOne/setupSkill
	local classId, ascendId
	if req.class then
		for cid, c in pairs(build.spec.tree.classes) do
			if c.name == req.class then
				classId = cid
				for aid, a in pairs(c.classes) do
					if aid ~= 0 and a.name == req.ascendancy then ascendId = aid end
				end
			end
		end
		if not classId then error("class not found: " .. req.class) end
		if req.ascendancy and not ascendId then error("ascendancy not found: " .. req.ascendancy) end
	end
	local res = {}
	for _, name in ipairs(req.skills or {}) do
		local ok, r = pcall(function()
			local gemId, gemData = findGemByName(name)
			if not gemId then error("gem not found") end
			local scan = scanOne(gemId, gemData, req)
			local supportIds = {}
			for _, sp in ipairs(scan.supports or {}) do
				local sid = findGemByName(sp.name, true)
				if sid then supportIds[#supportIds + 1] = sid end
			end
			local group = setupSkill(gemData, supportIds, req, classId, classId and (ascendId or 0) or nil)
			group.includeInFullDPS = true
			if req.impliedConditions and ascendId then applyAscendancyFlags() end
			local ascNodes
			if ascendId and (req.ascPoints or 0) > 0 then
				ascNodes = greedyAscendancy(req.ascPoints, req.ascFill)
			end
			local picks, spent
			if classId and (req.treePoints or 0) > 0 then
				local allowed
				if req.targetNodes then
					allowed = {}
					for _, n in ipairs(req.targetNodes) do allowed[n] = true end
				end
				picks, spent = greedyTree(req.treePoints, req.maxPath or req.treePoints, allowed)
			end
			recalc()
			local types, effectName = mainSkillTypes()
			return { skill = name, effect = effectName, ascNodes = ascNodes, gemLevel = gemLevelForReq(gemData, req), tier = gemData.Tier,
				weaponType = scan.weaponType, supports = scan.supports, picks = picks, spent = spent, types = types,
				reqStr = gemData.reqStr, reqDex = gemData.reqDex, reqInt = gemData.reqInt,
				variants = probeVariants(group), monsterLife = data.monsterLifeTable[req.level or 1] }
		end)
		res[#res + 1] = ok and r or { skill = name, error = tostring(r) }
		collectgarbage("collect")
	end
	return { results = res }
end

-- Facts that gate when a skill becomes usable in the campaign, read from the gem data: skill tier (the uncut
-- gem level needed), character level per gem level, attribute requirement per gem level, weapon types, spirit
-- reservation. Duplicate gem names (an item- or ascendancy-granted copy) prefer the tiered gem.
function commands.skill_gates(req)
	local out = {}
	for _, name in ipairs(req.skills or {}) do
		local best
		for id, g in pairs(data.gems) do
			if g.name == name and g.grantedEffect and not g.grantedEffect.support then
				if not best or ((g.Tier or 0) >= 1 and (best.Tier or 0) < 1) then best = g end
			end
		end
		if not best then
			out[#out + 1] = { skill = name, error = "gem not found" }
		else
			local levels = {}
			for l = 1, best.naturalMaxLevel or 20 do
				local lv = best.grantedEffect.levels and best.grantedEffect.levels[l]
				if lv then
					local lr = lv.levelRequirement or 0
					levels[#levels + 1] = { level = l, charLevel = lr,
						str = calcLib.getGemStatRequirement(lr, best.reqStr, false),
						dex = calcLib.getGemStatRequirement(lr, best.reqDex, false),
						int = calcLib.getGemStatRequirement(lr, best.reqInt, false),
						spirit = lv.spiritReservationFlat }
				end
			end
			-- lowest item level a base of each accepted weapon type needs
			local weapons = {}
			for w in (best.weaponRequirements or ""):gmatch("[^,]+") do
				w = w:gsub("^%s+", ""):gsub("%s+$", "")
				local lowest
				for _, base in pairs(data.itemBases) do
					local t = base.type
					if (base.weapon or w == "Armoured Shield") and not base.hidden and (t == w or (w == "Quarterstaff" and base.subType == "Warstaff")
						or (w == "Armoured Shield" and t == "Shield")) then
						local lvl = base.req and base.req.level or 1
						if not lowest or lvl < lowest then lowest = lvl end
					end
				end
				weapons[#weapons + 1] = { type = w, minLevel = lowest }
			end
			-- tier 0 skills come from an item or a node: name the ascendancy notables whose text grants it
			local grantedBy = {}
			if (best.Tier or 0) < 1 then
				for _, node in pairs(build.spec.tree.nodes) do
					if node.ascendancyName and node.sd then
						for _, line in ipairs(node.sd) do
							if line:find(name, 1, true) and line:lower():find("grant") then
								grantedBy[#grantedBy + 1] = { ascendancy = node.ascendancyName, node = node.dn }
							end
						end
					end
				end
			end
			out[#out + 1] = { skill = name, tier = best.Tier, gemType = best.gemType, tags = best.tagString,
				weapon = best.weaponRequirements, weapons = weapons, grantedBy = grantedBy, levels = levels }
		end
	end
	return { results = out }
end

-- The loaded build's passive tree: allocated notables/keystones (tree and ascendancy) and point counts.
function commands.tree_nodes()
	local tree, asc, points = {}, {}, 0
	for _, node in pairs(build.spec.allocNodes) do
		if node.type ~= "ClassStart" and node.type ~= "AscendClassStart" then
			if node.ascendancyName then
				if node.type == "Notable" then asc[#asc + 1] = node.dn end
			else
				points = points + 1
				if node.type == "Notable" or node.type == "Keystone" then tree[#tree + 1] = node.dn end
			end
		end
	end
	table.sort(tree); table.sort(asc)
	return { className = build.spec.curClassName, ascendancy = build.spec.curAscendClassName,
		level = build.characterLevel, mainSkill = mainSkillInfo(), notables = tree, ascNotables = asc, points = points }
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
		local v = outDps(o)
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
		if x ~= y then return x > y end
		return tieBreak(a, b)
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
		local v = outDps(o)
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

-- Margins on the thresholds where one item can flip a stat from "fine" to "broken":
-- Mind over Matter at 100% (uncapped sum vs cap), resist caps (over-cap / missing),
-- Spirit (unreserved), attribute requirements (value - requirement).
function commands.thresholds()
	recalc()
	local env = build.calcsTab.mainEnv
	local o = build.calcsTab.mainOutput or {}
	local db = env and env.player and env.player.modDB
	local res = {
		mom = db and num(db:Sum("BASE", nil, "DamageTakenFromManaBeforeLife")) or 0,
		momCapped = num(o.sharedMindOverMatter) or 0,
		lifeUnreserved = num(o.LifeUnreserved), manaUnreserved = num(o.ManaUnreserved),
		spiritUnreserved = num(o.SpiritUnreserved), spirit = num(o.Spirit),
		resists = {}, attributes = {},
	}
	for _, elem in ipairs({ "Fire", "Cold", "Lightning", "Chaos" }) do
		res.resists[elem] = { value = num(o[elem .. "Resist"]), overCap = num(o[elem .. "ResistOverCap"]),
			missing = num(o["Missing" .. elem .. "Resist"]) }
	end
	for _, a in ipairs({ "Str", "Dex", "Int" }) do
		res.attributes[a] = { value = num(o[a]), req = num(o["Req" .. a]) }
	end
	return res
end

-- Scenarios: the same build against PoB's four enemy tiers, with the enemy each tier assumes.
-- Author overrides in the Enemy Stats section (e.g. a hand-set enemy resist) are cleared per tier
-- unless req.keepOverrides, and reported separately. req.sources (synergy format) are measured
-- leave-one-out in every tier, to find pieces whose value depends on the enemy.
local SCENARIOS = {
	{ name = "map", val = "None", label = "normal/magic/rare monsters" },
	{ name = "boss", val = "Boss", label = "standard (map) boss" },
	{ name = "pinnacle", val = "Pinnacle", label = "Guardian/Pinnacle boss (PoB default)" },
	{ name = "uber", val = "Uber", label = "Uber pinnacle boss" },
}

local function enemySnapshot()
	local env = build.calcsTab.mainEnv
	local db = env and env.enemyDB
	if not db then return nil end
	local function s(name) return num(db:Sum("BASE", nil, name)) end
	return {
		level = env.enemyLevel,
		fireResist = s("FireResist"), coldResist = s("ColdResist"),
		lightningResist = s("LightningResist"), chaosResist = s("ChaosResist"),
		armour = s("Armour"), evasion = s("Evasion"),
		damageTakenMore = num(db:More(nil, "DamageTaken")),
	}
end

function commands.scenarios(req)
	recalc()
	local snap = snapshotConfig()
	local input = build.configTab.input
	local overrides, section = {}, nil
	for _, opt in ipairs(configOptions) do
		if opt.section then
			section = opt.section
		elseif opt.var and section == "Enemy Stats" and opt.var ~= "enemyIsBoss" and input[opt.var] ~= nil
				and input[opt.var] ~= build.configTab:GetDefaultState(opt.var, type(input[opt.var]))
				and not (opt.type == "list" and input[opt.var] == "None") then
			overrides[#overrides + 1] = { var = opt.var, value = input[opt.var],
				label = opt.label and opt.label:gsub("%^x%x%x%x%x%x%x", ""):gsub("%^%d", "") }
		end
	end
	local configured = input.enemyIsBoss or "Pinnacle"

	local group = build.skillsTab.socketGroupList[build.mainSocketGroup]
	local nodeByName, supByName = {}, {}
	for _, node in pairs(build.spec.allocNodes) do nodeByName[node.dn] = node end
	for _, g in ipairs(group and group.gemList or {}) do
		local nm = g.nameSpec or (g.gemData and g.gemData.name)
		if nm then supByName[nm] = g end
	end
	local fastOpts = { requirementsGems = true, skipEHP = true }
	local function eval(s)
		local override, sup = { removeNodes = {} }, nil
		if s then
			if s.kind == "node" then
				local n = nodeByName[s.name]; if not n then return nil end
				override.removeNodes[n] = true
			elseif s.kind == "slot" then
				override.repSlotName = s.slot
				override.repItem = s.raw and new("Item"):Item(s.raw) or nil
			elseif s.kind == "support" then
				sup = supByName[s.name]; if not sup then return nil end
				sup.enabled = false; build.skillsTab:ProcessSocketGroup(group); recalc()
			end
		end
		local v = fastDps(build.calcsTab:GetMiscCalculator(), override, fastOpts)
		if sup then sup.enabled = true; build.skillsTab:ProcessSocketGroup(group); recalc() end
		return v
	end

	local out = { configured = configured, overrides = overrides, scenarios = {} }
	for _, sc in ipairs(SCENARIOS) do
		restoreConfig(snap)
		if not req.keepOverrides then for _, o in ipairs(overrides) do input[o.var] = nil end end
		input.enemyIsBoss = sc.val
		recalc()
		local row = { name = sc.name, val = sc.val, label = sc.label, dps = skillDps(),
			ehp = num((build.calcsTab.mainOutput or {}).TotalEHP), enemy = enemySnapshot(), sources = {} }
		if req.sources and #req.sources > 0 then
			local base = eval(nil)
			for i, s in ipairs(req.sources) do
				local v = eval(s)
				row.sources[i] = (base and v and v > 0) and base / v or "inf"
			end
		end
		out.scenarios[#out.scenarios + 1] = row
	end
	restoreConfig(snap)
	recalc()
	out.asConfigured = { dps = skillDps(), ehp = num((build.calcsTab.mainOutput or {}).TotalEHP), enemy = enemySnapshot() }
	return out
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
					local v = outDps(o)
					if v == v and v ~= math.huge and base > 0 and v > base * 1.01 then
						rows[#rows + 1] = { name = name, mult = v / base }
					end
				end
			end
		end
		table.sort(rows, function(a, b)
			if a.mult ~= b.mult then return a.mult > b.mult end
			return tieBreak(a, b)
		end)
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

-- ---------------------------------------------------------------------------
-- Leveling check-up: what to change on a campaign character, measured on its own build.
-- Value of a skill = best hit stat set + best DoT-only stat set (setsValue, as the leveling ranking scores it).
-- ---------------------------------------------------------------------------
local function groupValue(i, vreq)
	build.mainSocketGroup = i
	build.configTab:BuildModList()
	local calcFunc = build.calcsTab:GetMiscCalculator()
	return setsValue(calcFunc, vreq or {}, {}, { requirementsItems = true, requirementsGems = true, skipEHP = true }) or 0
end

-- What a support set is judged by in the check-up. clear: DPS weighted by the monsters a use reaches in a pack,
-- with a DoT set fully credited only if one cast kills a magic monster (the leveling ranking's value). boss: plain
-- single-target DPS; a DoT is not expected to kill a boss in one cast, so duration counts only through DPS.
local function objectiveReq(objective)
	if objective == "boss" then return { boss = true } end
	if objective == "clear" then return { supportObjective = "clear" } end
	return {}
end

-- The skill a group is used for: the one PoB has selected (mainActiveSkill indexes displaySkillList, not gemList), so
-- a triggered or totem skill behind a meta gem is the group's skill; otherwise the first enabled active gem.
local function activeGem(g)
	local ds = g.displaySkillList and g.mainActiveSkill and g.displaySkillList[g.mainActiveSkill]
	local src = ds and ds.activeEffect and ds.activeEffect.srcInstance
	local sge = src and src.gemData and src.gemData.grantedEffect
	if sge and not sge.support and src.enabled ~= false then return src end
	for _, gi in ipairs(g.gemList or {}) do
		local ge = gi.gemData and gi.gemData.grantedEffect
		if ge and not ge.support and gi.enabled ~= false then return gi end
	end
end

-- Gems a what-if must keep so the group's selected skill keeps its place: the sources of every skill PoB lists up to
-- and including the selected one. A support can grant a skill of its own (Impending Doom grants Doom Blast), and
-- dropping it would shift the selection onto another skill.
local function pinnedGems(g)
	local keep = {}
	for k = 1, (g.mainActiveSkill or 1) do
		local ds = g.displaySkillList and g.displaySkillList[k]
		local src = ds and ds.activeEffect and ds.activeEffect.srcInstance
		if src then keep[src] = true end
	end
	return keep
end

-- A group's gem list with its supports replaced: every enabled non-support gem (the skill, and a meta or totem gem
-- it sits behind) and every pinned gem stays, in order, so a what-if measures the same skill the group is used for.
local function withSupports(gems, supports, keep)
	local list = {}
	for _, s in ipairs(gems or {}) do
		local ge = s.gemData and s.gemData.grantedEffect
		if ge and s.enabled ~= false and (not ge.support or (keep and keep[s])) then list[#list + 1] = s end
	end
	for _, s in ipairs(supports or {}) do list[#list + 1] = s end
	return list
end

-- Reprocess a group after a gem-list swap and restore PoB's selected skill: a MAIN calc clamps mainActiveSkill to
-- the list it sees, which a what-if with fewer skills shortens.
local function reprocess(g, mas, masc)
	build.skillsTab:ProcessSocketGroup(g)
	g.mainActiveSkill, g.mainActiveSkillCalcs = mas, masc
end

-- PoB counts minions in presence only for minion skills with a minion-limit stat, so a sceptre's granted
-- Skeletal Warrior counts as none and Minion Pact reads x1.00. When the build has a minion skill but PoB counts
-- none, assume one (PoB's own "# of Minions in your Presence" setting) for the whole check-up and say so.
function commands.checkup_prepare()
	recalc()
	SETS_FIRST_ONLY = nil
	DOT_KILL_LIFE = (data.monsterLifeTable[build.characterLevel or 1] or 0) * MAGIC_LIFE
	local hasMinion = {}
	for _, g in ipairs(build.skillsTab.socketGroupList) do
		local s = g.displaySkillList and g.displaySkillList[1]
		if g.enabled ~= false and s and s.minion then hasMinion[#hasMinion + 1] = s.activeEffect.grantedEffect.name end
	end
	local env = build.calcsTab.mainEnv
	local counted = env and env.player and env.player.modDB:Sum("BASE", nil, "Multiplier:MinionPresenceCount") or 0
	local assumed = false
	if #hasMinion > 0 and counted == 0 and not build.configTab.input.multiplierMinionsInPresence then
		build.configTab.input.multiplierMinionsInPresence = 1
		recalc()
		assumed = true
	end
	return { minionSkills = hasMinion, counted = counted, assumedOne = assumed }
end

-- Damaging socket groups with their value, supports, and what each support adds.
function commands.checkup_groups()
	local saved = build.mainSocketGroup
	local out = {}
	for i, g in ipairs(build.skillsTab.socketGroupList) do
		local gi = activeGem(g)
		if gi and g.enabled ~= false then
			local v = groupValue(i)
			if v > 0 then
				local row = { index = i, skill = gi.gemData.name, level = gi.level, value = v, slot = g.slot,
					source = g.source, supports = {} }
				for _, s in ipairs(g.gemList) do
					local sge = s.gemData and s.gemData.grantedEffect
					if sge and sge.support and s.enabled ~= false then
						s.enabled = false
						local without = groupValue(i)
						s.enabled = true
						local entry = { name = s.gemData.name, level = s.level, mult = without > 0 and v / without or nil }
						row.supports[#row.supports + 1] = entry
					end
				end
				out[#out + 1] = row
			end
		end
	end
	build.mainSocketGroup = saved
	recalc()
	return { groups = out }
end

-- Value of the group's skill at higher gem levels.
function commands.checkup_gem_levels(req)
	local g = build.skillsTab.socketGroupList[req.group]
	local gi = activeGem(g)
	local base, lvl0, rows = groupValue(req.group), gi.level, {}
	for l = lvl0 + 1, math.min(req.maxLevel or lvl0, lvl0 + 4) do
		gi.level = l
		build.skillsTab:ProcessSocketGroup(g)
		rows[#rows + 1] = { level = l, value = groupValue(req.group), mult = nil }
		rows[#rows].mult = base > 0 and rows[#rows].value / base or nil
	end
	gi.level = lvl0
	build.skillsTab:ProcessSocketGroup(g)
	recalc()
	return { base = base, level = lvl0, rows = rows }
end

-- Best support set of the current size (at least `slots`) for one group, greedy over tier-capped supports,
-- with each single swap measured as well. Supports socketed in other groups are flagged, not excluded:
-- whether PoE2 lets one support sit in two skills is not modelled.
function commands.checkup_supports(req)
	local i = req.group
	local g = build.skillsTab.socketGroupList[i]
	local gi = activeGem(g)
	local vreq = objectiveReq(req.objective)
	build.mainSocketGroup = i
	recalc()
	local active = g.displaySkillList and g.displaySkillList[g.mainActiveSkill or 1]
	local mas, masc = g.mainActiveSkill, g.mainActiveSkillCalcs
	local keep = pinnedGems(g)
	local current = {}
	for _, s in ipairs(g.gemList) do
		local sge = s.gemData and s.gemData.grantedEffect
		if sge and sge.support and s.enabled ~= false and not keep[s] then current[#current + 1] = s.gemData.name end
	end
	local elsewhere = {}
	for j, og in ipairs(build.skillsTab.socketGroupList) do
		if j ~= i then
			for _, s in ipairs(og.gemList or {}) do
				if s.gemData and s.gemData.grantedEffect and s.gemData.grantedEffect.support then elsewhere[s.gemData.name] = true end
			end
		end
	end
	local base = groupValue(i, vreq)
	local baseDps = groupValue(i)
	local saved = g.gemList
	local candidates = {}
	for id, cg in pairs(data.gems) do
		local ge = cg.grantedEffect
		if ge and ge.support and not ge.hidden and not (cg.tags and cg.tags.lineage) and not grantsCooldown(cg)
			and cg.Tier and cg.Tier >= 1 and cg.Tier <= (req.maxSupportTier or 1)
			and active and calcLib.canGrantedEffectSupportActiveSkill(ge, active) then
			candidates[#candidates + 1] = { id = id, g = cg }
		end
	end
	table.sort(candidates, function(a, b) return a.id < b.id end)
	local function gemEntry(c)
		return { level = math.min(c.g.naturalMaxLevel or 1, req.supportLevel or 1), quality = 0, count = 1, enabled = true,
			enableGlobal1 = true, enableGlobal2 = true, gemId = c.id, nameSpec = c.g.name, skillId = c.g.grantedEffectId,
			gemData = c.g }
	end
	-- greedy from the bare skill
	g.gemList = withSupports(saved, nil, keep)
	reprocess(g, mas, masc)
	local chosen, picks = {}, {}
	local slots = math.max(req.slots or 2, #current)
	local opts = { requirementsItems = true, requirementsGems = true, skipEHP = true }
	local bare = groupValue(i, vreq)
	for _ = 1, slots do
		local calcFunc = build.calcsTab:GetMiscCalculator()
		local bestV, best = setsValue(calcFunc, vreq, {}, opts) or 0, nil
		local idx = #g.gemList + 1
		for _, c in ipairs(candidates) do
			if not chosen[c.id] and not (req.excludeElsewhere and elsewhere[c.g.name]) then
				g.gemList[idx] = gemEntry(c)
				local v = setsValue(calcFunc, vreq, {}, opts)
				if v and v == v and v ~= math.huge and v > bestV * 1.001 then bestV, best = v, c end
			end
		end
		g.gemList[idx] = nil
		if not best then break end
		chosen[best.id] = true
		g.gemList[idx] = gemEntry(best)
		reprocess(g, mas, masc)
		recalc()
		picks[#picks + 1] = { name = best.g.name, tier = best.g.Tier, value = groupValue(i, vreq), elsewhere = elsewhere[best.g.name] or nil }
	end
	local bestSet = groupValue(i, vreq)
	local bestDps = groupValue(i)
	g.gemList = saved
	reprocess(g, mas, masc)
	recalc()
	-- mult: on the objective's own measure; dpsMult: on the check-up's value column, for comparison
	return { group = i, skill = gi.gemData.name, objective = req.objective, current = current, value = base, bare = bare,
		best = picks, bestValue = bestSet, mult = base > 0 and bestSet / base or nil,
		dpsMult = baseDps > 0 and bestDps / baseDps or nil }
end

-- Probe rows (as leveling_probe returns them) for the group's skill with each listed support set, so the
-- check-up scores pack clear with the leveling ranking's own model. A set is a list of support names; nil
-- (json null / missing) keeps the supports socketed now.
function commands.checkup_probe_sets(req)
	local i = req.group
	local g = build.skillsTab.socketGroupList[i]
	local gi = activeGem(g)
	build.mainSocketGroup = i
	local saved = g.gemList
	local mas, masc = g.mainActiveSkill, g.mainActiveSkillCalcs
	local keep = pinnedGems(g)
	-- probeVariants clears the gem's stat set / part selection; an export can carry a chosen one, so keep it
	local savedSet, savedPart = gi.statSet, gi.skillPart
	local out = {}
	for k = 1, #(req.sets or {}) do
		local names = req.sets[k]
		if type(names) == "table" and names ~= json.null then
			local sups, kept = {}, {}
			for s in pairs(keep) do if s.gemData then kept[s.gemData.name] = true end end
			for _, n in ipairs(names) do if kept[n] then goto continue end
				local id = findGemByName(n, true)
				local cg = id and data.gems[id]
				if cg then
					sups[#sups + 1] = { level = math.min(cg.naturalMaxLevel or 1, req.supportLevel or 1), quality = 0, count = 1,
						enabled = true, enableGlobal1 = true, enableGlobal2 = true, gemId = id, nameSpec = cg.name,
						skillId = cg.grantedEffectId, gemData = cg }
				end
				::continue::
			end
			g.gemList = withSupports(saved, sups, keep)
		else
			g.gemList = saved
		end
		reprocess(g, mas, masc)
		recalc()
		local types = mainSkillTypes()
		out[k] = { skill = gi.gemData.name, types = types, variants = probeVariants(g, gi),
			monsterLife = data.monsterLifeTable[build.characterLevel or 1] }
	end
	g.gemList = saved
	gi.statSet, gi.skillPart = savedSet, savedPart
	reprocess(g, mas, masc)
	recalc()
	return { rows = out }
end

-- Passive points: allocated count and each allocated node's share of the main group's value.
function commands.checkup_tree(req)
	build.mainSocketGroup = req.group
	recalc()
	local calcFunc = build.calcsTab:GetMiscCalculator()
	local opts = { requirementsItems = true, requirementsGems = true, skipEHP = true }
	local base = setsValue(calcFunc, {}, {}, opts) or 0
	local rows, n = {}, 0
	for _, node in pairs(build.spec.allocNodes) do
		if not node.ascendancyName and node.type ~= "ClassStart" and node.type ~= "AscendClassStart" then
			n = n + 1
			local v = setsValue(calcFunc, {}, { removeNodes = { [node] = true } }, opts) or 0
			rows[#rows + 1] = { name = node.dn, id = node.id, type = node.type, share = base > 0 and (1 - v / base) or 0,
				stats = node.sd }
		end
	end
	table.sort(rows, function(a, b)
		if a.share ~= b.share then return a.share > b.share end
		return tieBreak(a, b)
	end)
	return { allocated = n, level = build.characterLevel, base = base, nodes = rows }
end

-- Check-up "next steps": what the next passive points and the next ascendancy trial would add, whether the main
-- skill's mana is sustained, and allocated jewel sockets left empty. Every row is one calcFunc output with the
-- node's shortest path added (node.path includes the node, so #path is its point cost), measured alone.
local NEXT_NOISE = 0.001 -- same value as the check-up's NOISE: below this a node adds nothing to the main skill
local ASC_MAX = 8        -- ascendancy points a character can spend
local function manaSustain(o)
	local mana, unres = o.Mana or 0, o.ManaUnreserved or o.Mana or 0
	local cost, net = o.ManaPerSecondCost or 0, o.NetManaRegen or o.ManaRegenRecovery or 0
	local low = data.misc.LowPoolThreshold
	local r = { mana = mana, unreserved = unres, cost_ps = cost, net = net, low = low, life_cost_ps = o.LifePerSecondCost }
	if not o.ManaPerSecondHasCost or mana <= 0 or cost <= 0 then
		r.state = "no_cost"
	elseif cost <= net then
		r.state = "sustained"
	elseif unres <= low * mana then
		r.state = "already_low"
	else
		r.state = "drains"
		r.secs_to_low = (unres - low * mana) / (cost - net)
	end
	return r
end

function commands.checkup_next(req)
	build.mainSocketGroup = req.group
	recalc()
	local maxPath, ascPoints = req.maxPath or 7, req.ascPoints or 2
	local calcFunc = build.calcsTab:GetMiscCalculator()
	local opts = { requirementsItems = true, requirementsGems = true, skipEHP = true }
	local base = setsValue(calcFunc, {}, {}, opts) or 0
	local o0 = calcFunc({}, false, opts)
	local function res(o)
		return (o.FireResist or 0) + (o.ColdResist or 0) + (o.LightningResist or 0)
	end
	local function row(node)
		local add = {}
		for _, p in ipairs(node.path) do add[p] = true end
		local v = setsValue(calcFunc, {}, { addNodes = add }, opts) or 0
		local o = calcFunc({ addNodes = add }, false, opts)
		return { name = node.dn, id = node.id, cost = #node.path, keystone = node.isKeystone or nil,
			multipleChoice = node.isMultipleChoice or nil, mult = base > 0 and v / base or nil,
			life = (o.Life or 0) - (o0.Life or 0), es = (o.EnergyShield or 0) - (o0.EnergyShield or 0),
			res = res(o) - res(o0), regen = (o.NetManaRegen or o.ManaRegenRecovery or 0) - (o0.NetManaRegen or o0.ManaRegenRecovery or 0),
			sustain = manaSustain(o) }
	end
	local passives = {}
	for _, node in pairs(build.spec.nodes) do
		if not node.alloc and not node.ascendancyName and (node.isNotable or node.isKeystone) and node.path
			and #node.path > 0 and #node.path <= maxPath then
			local r = row(node)
			r.sustain = nil
			if (r.mult and r.mult > 1 + NEXT_NOISE) or r.life > 0 or r.es > 0 or r.res > 0 then
				passives[#passives + 1] = r
			end
		end
	end
	local _, ascUsed = build.spec:CountAllocNodes()
	local ascName = build.spec.curAscendClassName
	local asc, ascLeft = {}, ASC_MAX - (ascUsed or 0)
	if ascName and ascName ~= "None" and ascLeft > 0 then
		local cap = math.min(ascPoints, ascLeft)
		for _, node in pairs(build.spec.nodes) do
			if node.ascendancyName == ascName and not node.alloc and node.isNotable and node.path
				and #node.path > 0 and #node.path <= cap then
				asc[#asc + 1] = row(node)
			end
		end
	end
	local jewels = {}
	for id, node in pairs(build.spec.allocNodes) do
		if node.type == "Socket" then
			local slot = build.itemsTab.sockets and build.itemsTab.sockets[id]
			if not slot or not slot.selItemId or slot.selItemId == 0 then
				jewels[#jewels + 1] = { name = node.dn, id = id }
			end
		end
	end
	table.sort(jewels, tieBreak)
	table.sort(passives, tieBreak)
	table.sort(asc, tieBreak)
	recalc() -- node overrides leave later fast calcs with stale Spirit until the next full calculation
	return { base = base, noise = NEXT_NOISE, passives = passives, ascendancy = asc, ascendancyName = ascName,
		ascUsed = ascUsed, ascMax = ASC_MAX, sustain = manaSustain(o0), jewels = jewels }
end

-- Main group value with the build as is (used around Spirit probes that paste a group in).
function commands.checkup_value(req)
	local o = build.calcsTab.mainOutput or {}
	local v = groupValue(req.group)
	recalc()
	o = build.calcsTab.mainOutput or {}
	return { value = v, spirit = o.Spirit, spiritUnreserved = o.SpiritUnreserved }
end

-- Configuration options as the check-up's Spirit sweep reads them. A Spirit skill (or the build itself) can make PoB
-- show an option whose value it leaves empty (Withering Presence -> "# of Withered Stacks", a banner -> "Is Banner
-- Planted?"); the plain value then misses the effect. Visibility is PoB's own test (ConfigTab varControls[var].shown).
local configMeta
local function configOptions()
	if not configMeta then
		configMeta = {}
		for _, o in ipairs(LoadModule("Modules/ConfigOptions")) do
			if o.var then
				local gates = {}
				for k, v in pairs(o) do
					if type(k) == "string" and k:match("^if") then gates[#gates + 1] = k end
				end
				table.sort(gates)
				local list
				if o.list then
					list = {}
					for _, e in ipairs(o.list) do list[#list + 1] = e.val end
				end
				configMeta[o.var] = { var = o.var, type = o.type, gates = gates, list = list, ifFlag = o.ifFlag, ifSkill = o.ifSkill,
					label = o.label and o.label:gsub("%^x%x%x%x%x%x%x", ""):gsub("%^%d", ""):gsub(":$", "") }
			end
		end
	end
	return configMeta
end

-- What sets a flag, by name: the skill (a wand's Chaos Bolt for CanWither), the passive node or the item behind the
-- mod; the configuration's own mods are left out.
local function flagSources(flag)
	local env, names, seen = build.calcsTab.mainEnv, {}, {}
	local skills = env and env.player and env.player.activeSkillList or {}
	local function describe(src)
		local kind, rest = src:match("^(%a+):(.*)$")
		if kind == "Skill" then
			for _, sk in ipairs(skills) do
				local ge = sk.activeEffect and sk.activeEffect.grantedEffect
				if ge and ge.id == rest then return ge.name end
			end
		elseif kind == "Tree" then
			local node = build.spec.nodes[tonumber(rest)]
			return node and node.dn
		end
		return rest and rest:match("([^:]+)$") or src
	end
	for _, sk in ipairs(skills) do
		for _, m in ipairs(sk.skillModList:Tabulate("FLAG", nil, flag)) do
			local src = tostring(m.mod.source)
			local name = not src:match("^Config") and describe(src)
			if name and not seen[name] then
				seen[name] = true
				names[#names + 1] = name
			end
		end
	end
	table.sort(names)
	return names
end

-- Flags granted by the character's allocated ascendancy nodes, by flag name -> node name (the rule
-- applyAscendancyFlags uses for templates: a check option gated on such a flag is something the node does every use).
local function ascendancyFlags()
	local flags = {}
	for _, node in pairs(build.spec.allocNodes) do
		if node.ascendancyName and node.ascendancyName == build.spec.curAscendClassName then
			for _, mod in ipairs(node.modList or {}) do
				if mod.type == "FLAG" then flags[mod.name] = node.dn end
			end
		end
	end
	return flags
end

-- Options PoB shows now, with what the sweep needs to set them. Take it after checkup_value (a full recalc).
-- sources: what makes PoB show it (the skills, nodes or items setting an ifFlag; the used skills an ifSkill names).
function commands.checkup_config_shown()
	local out, meta, ascFlags = {}, configOptions(), ascendancyFlags()
	local used = build.calcsTab.mainEnv and build.calcsTab.mainEnv.skillsUsed or {}
	for var, c in pairs(build.configTab.varControls) do
		local m = meta[var]
		if m then
			local ok, shown = pcall(function()
				if type(c.shown) == "function" then return c.shown() end
				return c.shown ~= false
			end)
			if ok and shown then
				local v = build.configTab.input[var]
				local row = { var = var, type = m.type, label = m.label, gates = m.gates, list = m.list,
					value = (type(v) == "number" or type(v) == "boolean" or type(v) == "string") and v or nil }
				if m.ifFlag and type(m.ifFlag) == "string" then
					row.sources = flagSources(m.ifFlag)
					if m.type == "check" and ascFlags[m.ifFlag] then row.ascendancyNode = ascFlags[m.ifFlag] end
				elseif m.ifSkill then
					local names = {}
					for _, n in ipairs(type(m.ifSkill) == "table" and m.ifSkill or { m.ifSkill }) do
						if used[n] then names[#names + 1] = n end
					end
					table.sort(names)
					row.sources = names
				end
				out[#out + 1] = row
			end
		end
	end
	table.sort(out, function(a, b) return a.var < b.var end)
	return { options = out }
end

-- The group's value with some configuration options set, then the options restored. recalc after every write.
function commands.checkup_config_value(req)
	local input, saved = build.configTab.input, {}
	for var, v in pairs(req.values or {}) do
		saved[var] = { input[var] }
		input[var] = v
	end
	recalc()
	local ok, v = pcall(groupValue, req.group)
	for var, old in pairs(saved) do input[var] = old[1] end
	recalc()
	if not ok then error(v, 0) end
	return { value = v }
end

-- What the check-up's gear section says about a slot: the equipped base's PoB type and subtype, or for an empty
-- off-hand whether any off-hand can go there at all (PoB's own IsItemValidForSlot over a representative rare of each
-- off-hand-capable type: a two-handed main hand blocks them all unless Bow/Quiver, Staff + Instruments of Power,
-- Talisman + Lord of the Wilds or Giant's Blood opens one).
local OFFHAND_TYPES = { "Shield", "Focus", "Sceptre", "Quiver", "Buckler", "One Hand Mace", "One Hand Sword", "One Hand Axe",
	"Wand", "Dagger", "Claw", "Spear", "Flail" }
function commands.checkup_gear_slot(req)
	local slot = build.itemsTab.slots[req.slot]
	if not slot then error("unknown slot " .. tostring(req.slot)) end
	local item = slot.selItemId and build.itemsTab.items[slot.selItemId]
	if item then
		return { type = item.type or (item.base and item.base.type), subType = item.base and item.base.subType }
	end
	local out = { empty = true }
	if req.slot:match("^Weapon 2") then
		local open = false
		for _, ty in ipairs(OFFHAND_TYPES) do
			for name, base in pairsSortByKey(data.itemBases) do
				if base.type == ty and not base.hidden then
					local probe = new("Item"):Item("Rarity: RARE\nProbe\n" .. name)
					if probe.base and build.itemsTab:IsItemValidForSlot(probe, req.slot) then open = true end
					break
				end
			end
			if open then break end
		end
		out.blocked = not open
	end
	return out
end

-- Persistent / Spirit skills a campaign character could add with its free Spirit.
function commands.checkup_spirit_gems(req)
	local l, seen = {}, {}
	for _, gd in pairs(data.gems) do
		local ge = gd.grantedEffect
		if ge and not ge.support and gd.Tier and gd.Tier >= 1 and gd.Tier <= (req.maxTier or 1) and not seen[gd.name] then
			local lv = ge.levels and ge.levels[1]
			local res = lv and lv.spiritReservationFlat
			if res and res > 0 and res <= (req.spirit or math.huge) then
				seen[gd.name] = true
				l[#l + 1] = { name = gd.name, tier = gd.Tier, spirit = res }
			end
		end
	end
	-- Blasphemy reserves Spirit per curse socketed in it (no flat reservation of its own), so it is listed apart:
	-- its tier, and the curse gems it could carry at this level.
	local blas, curses = nil, {}
	for _, gd in pairs(data.gems) do
		local ge = gd.grantedEffect
		if ge and not ge.support and gd.Tier and gd.Tier >= 1 and gd.Tier <= (req.maxTier or 1) then
			if ge.skillTypes and ge.skillTypes[SkillType.IsBlasphemy] then
				blas = math.min(blas or gd.Tier, gd.Tier)
			elseif ge.skillTypes and ge.skillTypes[SkillType.AppliesCurse] and not seen[gd.name] then
				seen[gd.name] = true
				curses[#curses + 1] = { name = gd.name, tier = gd.Tier }
			end
		end
	end
	table.sort(curses, function(a, b) return a.name < b.name end)
	return { gems = l, blasphemy = blas, curses = blas and curses or {} }
end

-- Curse names PoB applies to the enemy now (after a recalc of the main group).
local function curseNames()
	local env, l = build.calcsTab.mainEnv, {}
	for _, c in ipairs(env and env.curseSlots or {}) do
		if c and c.name and not c.isMark then l[#l + 1] = c.name end
	end
	table.sort(l)
	return l
end

local function usesBlasphemy()
	for _, g in ipairs(build.skillsTab.socketGroupList) do
		if g.enabled ~= false then
			for _, s in ipairs(g.gemList or {}) do
				local ge = s.gemData and s.gemData.grantedEffect
				if s.enabled ~= false and ge and ge.skillTypes and ge.skillTypes[SkillType.IsBlasphemy] then return true end
			end
		end
	end
	return false
end

-- Blasphemy + one curse pasted as a new group, then supports picked greedily on the curse within the free Spirit.
-- Spirit costs are PoB's own (SpiritUnreserved before minus after). The group is left as the plain pair, so the caller
-- can measure configuration options on it. aura=false: PoB did not make the curse an aura (no Blasphemy support on it).
function commands.checkup_blasphemy(req)
	local i = req.group
	if usesBlasphemy() then return { skipped = "the build already uses Blasphemy" } end
	local v0 = groupValue(i); recalc()
	local free = (build.calcsTab.mainOutput or {}).SpiritUnreserved or 0
	local before = curseNames()
	build.skillsTab:PasteSocketGroup(string.format("Blasphemy %d/0  1\n%s %d/0  1\n", req.level, req.curse, req.level))
	local n = #build.skillsTab.socketGroupList
	local g = build.skillsTab.socketGroupList[n]
	local function measure()
		local v = groupValue(i)
		recalc()
		return v, (build.calcsTab.mainOutput or {}).SpiritUnreserved or 0
	end
	local value, left = measure()
	local after = curseNames()
	local active
	for _, a in ipairs(build.calcsTab.mainEnv.player.activeSkillList) do
		if a.socketGroup == g and a.activeEffect.grantedEffect.name == req.curse then active = a end
	end
	local aura = false
	for _, e in ipairs(active and active.effectList or {}) do
		if e.grantedEffect.id == "SupportBlasphemyPlayer" then aura = true end
	end
	local replaced, kept = {}, {}
	for _, c in ipairs(after) do kept[c] = true end
	for _, c in ipairs(before) do if not kept[c] then replaced[#replaced + 1] = c end end
	local out = { value = value, base = v0, free = free, spiritUnreserved = left, spirit = free - left, aura = aura,
		replaced = replaced, picks = {}, candidates = {} }
	if not aura or not active then return out end
	local elsewhere = {}
	for j, og in ipairs(build.skillsTab.socketGroupList) do
		if j ~= n then
			for _, s in ipairs(og.gemList or {}) do
				if s.gemData and s.gemData.grantedEffect and s.gemData.grantedEffect.support then elsewhere[s.gemData.name] = true end
			end
		end
	end
	local cands = {}
	for id, cg in pairs(data.gems) do
		local ge = cg.grantedEffect
		if ge and ge.support and not ge.hidden and not (cg.tags and cg.tags.lineage) and not grantsCooldown(cg)
			and cg.Tier and cg.Tier >= 1 and cg.Tier <= (req.maxSupportTier or 1)
			and calcLib.canGrantedEffectSupportActiveSkill(ge, active) then
			cands[#cands + 1] = { id = id, g = cg }
		end
	end
	table.sort(cands, function(a, b) return a.id < b.id end)
	for _, c in ipairs(cands) do out.candidates[#out.candidates + 1] = c.g.name end
	local plain = g.gemList
	local list = {}
	for _, s in ipairs(plain) do list[#list + 1] = s end
	local chosen, prev = {}, value
	for _ = 1, (req.slots or 2) do
		local best, bv, bl
		for _, c in ipairs(cands) do
			if not chosen[c.id] then
				local trial = {}
				for _, s in ipairs(list) do trial[#trial + 1] = s end
				trial[#trial + 1] = { level = math.min(c.g.naturalMaxLevel or 1, 1), quality = 0, count = 1, enabled = true,
					enableGlobal1 = true, enableGlobal2 = true, gemId = c.id, nameSpec = c.g.name, skillId = c.g.grantedEffectId,
					gemData = c.g }
				g.gemList = trial
				build.skillsTab:ProcessSocketGroup(g)
				local v, l = measure()
				if l >= 0 and v == v and v ~= math.huge and v > prev * 1.001 and (not bv or v > bv) then
					best, bv, bl = { c = c, entry = trial[#trial] }, v, l
				end
			end
		end
		if not best then break end
		chosen[best.c.id] = true
		list[#list + 1] = best.entry
		prev = bv
		out.picks[#out.picks + 1] = { name = best.c.g.name, tier = best.c.g.Tier, value = bv, spiritUnreserved = bl,
			spirit = free - bl, elsewhere = elsewhere[best.c.g.name] or nil }
	end
	g.gemList = plain
	build.skillsTab:ProcessSocketGroup(g)
	measure()
	return out
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

-- A stat set can map two of its stats to the same skill data key, e.g. Earthquake's Aftershock: the generic
-- active_skill_base_area_of_effect_radius -> radius and its own override tertiary radius -> radius. PoB merges
-- stats in `pairs` order, which LuaJIT's seeded string hash varies per process, so the Aftershock radius came out
-- 2.1 m or 3.0 m from run to run. Where a set deliberately remaps a stat (its key differs from the generic map),
-- that mapping wins: generic stats in the set that write the same key are dropped.
local function skillDataKeys(map)
	local keys = {}
	for _, m in ipairs(map or {}) do
		for _, mod in ipairs(m.name and { m } or m) do
			if mod.name == "SkillData" and type(mod.value) == "table" and mod.value.key then keys[mod.value.key] = true end
		end
	end
	return keys
end
local function pinSkillDataOverrides()
	local n = 0
	for _, ge in pairs(data.skills) do
		for _, set in ipairs(ge.statSets or {}) do
			local present = {}
			for _, s in ipairs(set.stats or {}) do present[s] = true end
			for _, c in ipairs(set.constantStats or {}) do present[c[1]] = true end
			local override = {}
			for s in pairs(present) do
				local own = rawget(set.statMap, s)
				if own then
					local generic = skillDataKeys(data.skillStatMap[s])
					for k in pairs(skillDataKeys(own)) do
						if not generic[k] then override[k] = s end
					end
				end
			end
			if next(override) then
				for s in pairs(present) do
					local generic = data.skillStatMap[s]
					if generic and override[next(skillDataKeys(generic)) or ""] and override[next(skillDataKeys(generic))] ~= s then
						rawset(set.statMap, s, {})
						n = n + 1
					end
				end
			end
		end
	end
	return n
end
-- the count goes out with the ready message: a test pins it (1, Earthquake Aftershock) so a data update that
-- pins more stat sets is noticed
local pinnedStats = pinSkillDataOverrides()

respond({ id = 0, ok = true, result = { ready = true, version = launch.versionNumber, pinnedStats = pinnedStats } })

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
