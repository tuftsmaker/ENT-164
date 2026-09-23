#!/usr/bin/env python3
"""Check every nav on the site: links resolve, anchors exist, pages have one.

`apply.py --check` proves a page's nav matches the spec. This proves the spec's
links actually go somewhere — a nav can be consistently wrong. It also checks
that each `#anchor` in a sub-nav or a generated section list has a target on
that page, which is the failure mode a link checker normally misses.

    python3 tools/site-nav/verify-links.py
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

NAV_BLOCK = re.compile(r'<nav class="(?:nav|site-nav|subnav)".*?</nav>', re.S)
SKIP_PARTS = {".git", "out", "brand", "node_modules"}


def pages():
    for path in sorted(ROOT.rglob("*.html")):
        if SKIP_PARTS & set(path.parts):
            continue
        if NAV_BLOCK.search(path.read_text(errors="replace")):
            yield path


def main() -> int:
    broken_links = []
    broken_anchors = []
    no_nav = []
    link_count = 0
    anchor_count = 0

    all_pages = [p for p in ROOT.rglob("*.html") if not (SKIP_PARTS & set(p.parts))]
    for path in sorted(all_pages):
        text = path.read_text(errors="replace")
        rel = path.relative_to(ROOT)
        navs = NAV_BLOCK.findall(text)

        # A published page should have a nav. Slide decks and print handouts are
        # deliberately out, as are the in-browser render outputs under out/.
        is_print_only = "slides.html" in path.name or path.parent.name == "handouts"
        if not navs and not is_print_only:
            no_nav.append(str(rel))
            continue
        if not navs:
            continue

        for block in navs:
            for raw in re.findall(r'href="([^"]+)"', block):
                if raw.startswith(("http://", "https://", "mailto:")):
                    continue
                if raw.startswith("#"):
                    anchor = raw[1:]
                    anchor_count += 1
                    if anchor and f'id="{anchor}"' not in text:
                        broken_anchors.append(f"{rel}: {raw} has no target")
                    continue
                target_href, _, anchor = raw.partition("#")
                decoded = urllib.parse.unquote(target_href)
                target = (path.parent / decoded).resolve()
                if decoded.endswith("/"):
                    target = target / "index.html"
                if not target.exists():
                    broken_links.append(f"{rel}: {raw}")
                elif anchor:
                    anchor_count += 1
                    if f'id="{anchor}"' not in target.read_text(errors="replace"):
                        broken_anchors.append(f"{rel}: {raw} -> no #{anchor} in {decoded}")
                link_count += 1

    print(f"{len(all_pages)} html files scanned")
    print(f"{link_count} nav links, {anchor_count} anchors checked")
    problems = broken_links + broken_anchors + [f"{p}: no nav" for p in no_nav]
    if problems:
        print()
        for p in problems:
            print(f"  {p}")
        print(f"\n{len(problems)} problem(s).")
        return 1
    print("every nav link resolves and every anchor has a target.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
