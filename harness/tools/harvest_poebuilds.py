"""Collect a sample of public PoE2 build pastes for research.

Reads poebuilds.cc listing pages (public HTML), extracts build cards that link
to a shareable PoB paste (poe.ninja/poe2/pob/<id> or pobb.in/<id>), and
downloads each paste the same way Path of Building's own importer does
(BuildSiteTools.lua downloadURL). Low-frequency, honest User-Agent.

Usage: python harvest_poebuilds.py OUT_DIR [--pages slug ...] [--version 0.55]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

UA = "pob-agent-research/0.1 (personal PoE2 build research)"
BASE = "https://www.poebuilds.cc/poe2"
DEFAULT_PAGES = ["", "mercenary", "monk", "ranger", "sorceress", "witch", "warrior", "druid", "huntress"]

CARD_RE = re.compile(r'<div class="build-card"(.*?)</div></div></div>', re.S)
TITLE_RE = re.compile(r'class="build-card-title"[^>]*title="([^"]*)"')
VERSION_RE = re.compile(r'build-card-tag--version[^"]*">([^<]*)<')
CLASS_RE = re.compile(r'build-card-tag--class"[^>]*>([^<]*)<')
METRIC_RE = re.compile(r'build-card-tag--metric[^"]*">([^<]*)<')
TAG_RE = re.compile(r'<span class="build-card-tag">([^<]*)<')
AUTHOR_RE = re.compile(r'build-card-tag--author">([^<]*)<')
NINJA_RE = re.compile(r'https://poe\.ninja/poe2/pob/([A-Za-z0-9_-]+)')
POBBIN_RE = re.compile(r'https://pobb\.in/([A-Za-z0-9_-]+)')


def fetch(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def parse_cards(page_html: str) -> list[dict]:
    cards = []
    for m in CARD_RE.finditer(page_html):
        body = m.group(1)
        title = TITLE_RE.search(body)
        ninja = NINJA_RE.search(body)
        pobbin = POBBIN_RE.search(body)
        if not title or not (ninja or pobbin):
            continue
        version = VERSION_RE.search(body)
        cls = CLASS_RE.search(body)
        metric = METRIC_RE.search(body)
        author = AUTHOR_RE.search(body)
        cards.append({
            "title": html.unescape(title.group(1)),
            "version": version.group(1).strip() if version else None,
            "class": cls.group(1).strip() if cls else None,
            "metric": metric.group(1).strip() if metric else None,
            "tags": [t.strip() for t in TAG_RE.findall(body)],
            "author": author.group(1).strip() if author else None,
            "source": "poe.ninja" if ninja else "pobb.in",
            "paste_id": (ninja or pobbin).group(1),
        })
    return cards


def paste_url(card: dict) -> str:
    if card["source"] == "poe.ninja":
        return f"https://poe.ninja/poe2/pob/raw/{card['paste_id']}"
    return f"https://pobb.in/pob/{card['paste_id']}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--pages", nargs="*", default=DEFAULT_PAGES)
    ap.add_argument("--version", default="0.55", help="keep cards whose version tag starts with this")
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    for slug in args.pages:
        url = f"{BASE}/{slug}" if slug else BASE
        status, body = fetch(url)
        print(f"page {url} -> {status}", file=sys.stderr)
        if status == 200:
            for card in parse_cards(body.decode("utf-8", "replace")):
                if args.version and not (card["version"] or "").startswith(args.version):
                    continue
                seen.setdefault(card["source"] + ":" + card["paste_id"], card)
        time.sleep(args.delay)

    manifest = []
    for key, card in list(seen.items())[: args.limit]:
        dest = out / f"{card['source'].replace('.', '_')}_{card['paste_id']}.code"
        if not dest.exists():
            status, body = fetch(paste_url(card))
            if status != 200 or not body.strip():
                print(f"skip {key}: {status}", file=sys.stderr)
                time.sleep(args.delay)
                continue
            dest.write_bytes(body.strip())
            time.sleep(args.delay)
        card["file"] = dest.name
        manifest.append(card)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"{len(manifest)} builds saved to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
