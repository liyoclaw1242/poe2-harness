-- pob-agent headless runner for Path of Building PoE2 under stock LuaJIT.
--
-- PoB ships a patched LuaJIT that accepts compound assignment (`x += 1`) and a
-- leading `#@` line. Stock LuaJIT accepts neither, so every file PoB loads goes
-- through `preprocess` first. Deflate/Inflate are bound to the system zlib via
-- FFI so build share codes work.
--
-- Usage (cwd must be PoB's src/ directory):
--   luajit pob_headless.lua            -> JSON-lines RPC on stdin/stdout

local HARNESS_DIR = (debug.getinfo(1, "S").source:sub(2):match("(.*/)")) or "./"

---------------------------------------------------------------------------
-- Source preprocessing
---------------------------------------------------------------------------
-- The right-hand side of `x += rhs` runs to the end of the line, or to the
-- first block keyword when the statement sits inside a one-line block
-- (`if a then n += 1 elseif b then n -= 1 end`).
local function splitRhs(rest)
	local cut
	for _, kw in ipairs({ "elseif", "else", "end" }) do
		local s = rest:find("%s" .. kw .. "%f[^%w_]")
		if s and (not cut or s < cut) then
			cut = s
		end
	end
	if cut then
		return rest:sub(1, cut - 1), rest:sub(cut)
	end
	return rest, ""
end

local function rewriteCompound(line)
	local pre, lhs, op, rest = line:match("^(.-)([%w_%.%[%]]+)%s+(%.%.)=%s+(.*)$")
	if not pre then
		pre, lhs, op, rest = line:match("^(.-)([%w_%.%[%]]+)%s+([%+%-%*/%%%^])=%s+(.*)$")
	end
	if not pre or pre:find("--", 1, true) then
		return line
	end
	local _, quotes = pre:gsub('"', "")
	if quotes % 2 == 1 then
		return line
	end
	-- `pre` may itself hold another compound assignment (one-line blocks).
	pre = rewriteCompound(pre)
	local rhs, tail = splitRhs(rest)
	tail = tail ~= "" and rewriteCompound(tail) or tail
	return pre .. lhs .. " = " .. lhs .. " " .. op .. " (" .. rhs .. ")" .. tail
end

local function preprocess(src)
	if src:sub(1, 1) == "#" then
		src = "--" .. src
	end
	if not src:find("[%+%-%*/%%%^%.]=%s") then
		return src
	end
	local out = {}
	for line in (src .. "\n"):gmatch("(.-)\r?\n") do
		out[#out + 1] = rewriteCompound(line)
	end
	return table.concat(out, "\n")
end

local rawLoadfile = loadfile
function loadfile(path, ...)
	local f = io.open(path, "rb")
	if not f then
		return rawLoadfile(path, ...)
	end
	local src = f:read("*a")
	f:close()
	return loadstring(preprocess(src), "@" .. path)
end

function dofile(path)
	local fn, err = loadfile(path)
	if not fn then
		error(err, 2)
	end
	return fn()
end

-- Lua-file searcher that also preprocesses.
table.insert(package.loaders, 2, function(name)
	local path = package.searchpath(name, package.path)
	if not path then
		return nil
	end
	local fn, err = loadfile(path)
	if not fn then
		error(err)
	end
	return fn
end)

---------------------------------------------------------------------------
-- zlib via FFI
---------------------------------------------------------------------------
local ffi = require("ffi")
ffi.cdef([[
typedef struct z_stream_s {
  const unsigned char *next_in; unsigned int avail_in; unsigned long total_in;
  unsigned char *next_out; unsigned int avail_out; unsigned long total_out;
  const char *msg; void *state; void *zalloc; void *zfree; void *opaque;
  int data_type; unsigned long adler; unsigned long reserved;
} z_stream;
const char *zlibVersion(void);
int inflateInit2_(z_stream *strm, int windowBits, const char *version, int stream_size);
int inflate(z_stream *strm, int flush);
int inflateEnd(z_stream *strm);
int deflateInit2_(z_stream *strm, int level, int method, int windowBits, int memLevel, int strategy, const char *version, int stream_size);
int deflate(z_stream *strm, int flush);
int deflateEnd(z_stream *strm);
]])
local zlib = ffi.load("z")
local CHUNK = 65536

local function zstream(data)
	local strm = ffi.new("z_stream")
	strm.next_in = data
	strm.avail_in = #data
	return strm
end

local function pump(strm, step)
	local buf = ffi.new("unsigned char[?]", CHUNK)
	local parts = {}
	while true do
		strm.next_out = buf
		strm.avail_out = CHUNK
		local rc = step(strm)
		parts[#parts + 1] = ffi.string(buf, CHUNK - strm.avail_out)
		if rc == 1 then -- Z_STREAM_END
			return table.concat(parts)
		elseif rc ~= 0 then
			return nil
		end
	end
end

local function inflateData(data)
	local strm = zstream(data)
	-- 15 + 32: auto-detect zlib or gzip header
	if zlib.inflateInit2_(strm, 47, zlib.zlibVersion(), ffi.sizeof(strm)) ~= 0 then
		return nil
	end
	local out = pump(strm, function(s) return zlib.inflate(s, 0) end)
	zlib.inflateEnd(strm)
	return out
end

local function deflateData(data, isGzip)
	local strm = zstream(data)
	local bits = isGzip and 31 or 15
	if zlib.deflateInit2_(strm, 9, 8, bits, 8, 0, zlib.zlibVersion(), ffi.sizeof(strm)) ~= 0 then
		return nil
	end
	local out = pump(strm, function(s) return zlib.deflate(s, 4) end) -- Z_FINISH
	zlib.deflateEnd(strm)
	return out
end

---------------------------------------------------------------------------
-- Boot PoB
---------------------------------------------------------------------------
package.path = "../runtime/lua/?.lua;../runtime/lua/?/init.lua;./?.lua;" .. package.path
package.cpath = HARNESS_DIR .. "../../vendor/native/?.so;" .. package.cpath

local realStdout = io.stdout
local function log(...)
	io.stderr:write(table.concat({ ... }, " "), "\n")
end
-- PoB prints chatter during init; keep stdout clean for the RPC channel.
print = log

-- HeadlessWrapper waits on io.read() if startup fails; make that non-blocking.
local realRead = io.read
io.read = function() return nil end

dofile("HeadlessWrapper.lua")
io.read = realRead

Deflate = deflateData
Inflate = inflateData

if not build then
	log("PoB failed to initialise")
	os.exit(2)
end

return {
	preprocess = preprocess,
	inflate = inflateData,
	deflate = deflateData,
	stdout = realStdout,
	log = log,
}
