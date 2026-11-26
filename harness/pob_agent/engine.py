"""Client for the LuaJIT JSON-lines RPC daemon (harness/lua/rpc.lua)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LUA_DIR = ROOT / "harness" / "lua"
POB_SRC = Path(os.environ.get("POB_SRC", ROOT / "vendor" / "PathOfBuilding-PoE2" / "src"))


class EngineError(RuntimeError):
    pass


def find_luajit() -> str:
    env = os.environ.get("POB_LUAJIT")
    if env:
        return env
    found = shutil.which("luajit")
    if found:
        return found
    for cand in ("/opt/homebrew/opt/luajit/bin/luajit", "/usr/local/opt/luajit/bin/luajit"):
        if Path(cand).exists():
            return cand
    raise EngineError("luajit not found; install it (brew install luajit) or set POB_LUAJIT")


class Engine:
    """One headless PoB process. Use as a context manager."""

    def __init__(self, verbose: bool = False, pob_src: Path | str | None = None):
        self.verbose = verbose
        # another PoB-PoE2 checkout's src/ (e.g. the previous patch) for patch diffs
        self.pob_src = Path(pob_src) if pob_src else POB_SRC
        self.proc: subprocess.Popen | None = None
        self._next_id = 1
        self.version: str | None = None

    def __enter__(self) -> "Engine":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def start(self) -> None:
        if not (self.pob_src / "HeadlessWrapper.lua").exists():
            raise EngineError(f"PoB-PoE2 source not found at {self.pob_src}; run scripts/setup.sh")
        self.proc = subprocess.Popen(
            [find_luajit(), str(LUA_DIR / "rpc.lua")],
            cwd=self.pob_src,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None if self.verbose else subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        ready = self._read()
        if not ready.get("ok"):
            raise EngineError(f"engine failed to start: {ready}")
        self.version = ready["result"].get("version")
        self.pinned_stats = ready["result"].get("pinnedStats")

    def close(self) -> None:
        if self.proc:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()
            self.proc = None

    def _read(self) -> dict:
        assert self.proc and self.proc.stdout
        line = self.proc.stdout.readline()
        if not line:
            raise EngineError("engine exited unexpectedly (run with --verbose for PoB output)")
        return json.loads(line)

    def call(self, cmd: str, **params: Any) -> Any:
        assert self.proc and self.proc.stdin
        req_id = self._next_id
        self._next_id += 1
        self.proc.stdin.write(json.dumps({"id": req_id, "cmd": cmd, **params}) + "\n")
        self.proc.stdin.flush()
        resp = self._read()
        if resp.get("id") != req_id:
            raise EngineError(f"out-of-order response: {resp}")
        if not resp.get("ok"):
            raise EngineError(f"{cmd} failed: {resp.get('error')}")
        return resp["result"]
