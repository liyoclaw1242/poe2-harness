"""Resolve a build reference (file, share code, pobb.in / poe.ninja paste URL)."""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

UA = "pob-agent/0.1"

# Same download endpoints Path of Building's importer uses (Modules/BuildSiteTools.lua).
PASTE_SITES = [
    (re.compile(r"pobb\.in/([A-Za-z0-9_-]+)"), "https://pobb.in/pob/{}"),
    (re.compile(r"poe2?\.ninja/(?:poe2/)?pob/([A-Za-z0-9_-]+)"), "https://poe.ninja/poe2/pob/raw/{}"),
]


def _download(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8").strip()


def resolve(ref: str) -> dict:
    """Return kwargs for the engine's `load` command."""
    path = Path(ref).expanduser()
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        return {"xml": text} if text.lstrip().startswith("<") else {"code": text}
    for pattern, template in PASTE_SITES:
        m = pattern.search(ref)
        if m:
            return {"code": _download(template.format(m.group(1)))}
    if ref.lstrip().startswith("<"):
        return {"xml": ref}
    return {"code": ref.strip()}
