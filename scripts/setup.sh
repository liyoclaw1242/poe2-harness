#!/usr/bin/env bash
# One-time setup for the pob-agent harness on macOS/Linux.
#  - LuaJIT (stock; harness/lua/pob_headless.lua bridges PoB's dialect)
#  - lua-utf8 native module built against LuaJIT
#  - shallow checkout of PathOfBuilding-PoE2 (dev branch)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v luajit >/dev/null 2>&1 && [ ! -x /opt/homebrew/opt/luajit/bin/luajit ]; then
  if command -v brew >/dev/null 2>&1; then brew install luajit; else
    echo "install LuaJIT 2.1 (e.g. apt install luajit libluajit-5.1-dev)"; exit 1; fi
fi
LUAJIT_INC="$(brew --prefix luajit 2>/dev/null)/include/luajit-2.1"
[ -d "$LUAJIT_INC" ] || LUAJIT_INC=/usr/include/luajit-2.1

mkdir -p vendor/native
if [ ! -d vendor/PathOfBuilding-PoE2 ]; then
  git clone --depth 1 https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2.git vendor/PathOfBuilding-PoE2
else
  git -C vendor/PathOfBuilding-PoE2 pull --ff-only
fi

if [ ! -f vendor/native/lua-utf8.so ]; then
  [ -d vendor/native/luautf8 ] || git clone --depth 1 https://github.com/starwing/luautf8.git vendor/native/luautf8
  if [ "$(uname)" = "Darwin" ]; then
    cc -O2 -fPIC -bundle -undefined dynamic_lookup -I"$LUAJIT_INC" vendor/native/luautf8/lutf8lib.c -o vendor/native/lua-utf8.so
  else
    cc -O2 -fPIC -shared -I"$LUAJIT_INC" vendor/native/luautf8/lutf8lib.c -o vendor/native/lua-utf8.so
  fi
fi

PYTHONPATH=harness python3 -c "from pob_agent.engine import Engine
with Engine() as e: print('PoB-PoE2 engine OK, version', e.version)"
