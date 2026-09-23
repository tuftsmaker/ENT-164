#!/usr/bin/env python3
"""Rewrite the site's navs from tools/site-nav/nav.py.

Idempotent and checkable: running it twice changes nothing, and `--check` fails
if a page's nav does not match what the spec says — which is what CI runs.

    python3 tools/site-nav/apply.py            # bring every page up to date
    python3 tools/site-nav/apply.py --check     # verify, change nothing
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import nav as spec  # noqa: E402

ROOT = HERE.parent.parent

NAV_RE = re.compile(r'<nav class="nav">.*?</nav>', re.S)
SITE_NAV_RE = re.compile(r'<nav class="site-nav">.*?</nav>', re.S)


def depth_of(path: Path) -> int:
    rel = path.parent.relative_to(ROOT)
    return 0 if str(rel) == "." else len(rel.parts)


def replace_nav(html: str, new: str) -> tuple[str, str]:
    """Swap the first nav block. Returns (text, action)."""
    for name, pattern in (("nav", NAV_RE), ("site-nav", SITE_NAV_RE)):
        m = pattern.search(html)
        if m:
            if m.group(0) == new:
                return html, "same"
            return html[: m.start()] + new + html[m.end():], f"rewrote {name}"
    return html, "no nav found"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="site-nav")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    drift = []
    updated = 0

    for rel, (cta_href, cta_label, active) in spec.PAGES.items():
        page = ROOT / rel
        if not page.exists():
            drift.append(f"{rel}: file is missing")
            continue
        text = page.read_text()
        new = spec.main_nav(depth_of(page), cta_href, cta_label, active)
        # A page's sections, if it has any.
        sections = spec.SUBNav_PAGES.get(rel)
        patched, action = replace_nav(text, new)
        if sections is not None:
            patched, sub_action = replace_sub_nav(patched, spec.sub_nav(sections))
            if sub_action == "inserted":
                action = f"{action}, inserted subnav"
            elif sub_action.startswith("rewrote"):
                action = f"{action}, {sub_action}"
        if action != "same":
            updated += 1
            if action == "no nav found":
                drift.append(f"{rel}: no nav block to replace")
            elif args.check:
                drift.append(f"{rel}: {action} (would change)")
            else:
                page.write_text(patched)
                print(f"  {rel}: {action}")

    for rel, (cta_href, cta_label) in spec.GUIDE_PAGES.items():
        page = ROOT / rel
        if not page.exists():
            drift.append(f"{rel}: file is missing")
            continue
        text = page.read_text()
        new = spec.site_nav(depth_of(page), cta_href, cta_label)
        patched, action = replace_nav(text, new)
        if action != "same":
            updated += 1
            if action == "no nav found":
                drift.append(f"{rel}: no nav block to replace")
            elif args.check:
                drift.append(f"{rel}: {action} (would change)")
            else:
                page.write_text(patched)
                print(f"  {rel}: {action}")

    print()
    if drift:
        print("drift:" if args.check else "problems:")
        for d in drift:
            print(f"  {d}")
        return 1
    print("every nav matches the spec." if args.check else f"{updated} page(s) updated.")
    return 0


SUB_RE = re.compile(r'<nav class="subnav".*?</nav>', re.S)
MARKER = '<header class="hero"'


def replace_sub_nav(html: str, new: str) -> tuple[str, str]:
    """Insert (or refresh) the sub-nav, directly after the hero."""
    existing = SUB_RE.search(html)
    if existing:
        if existing.group(0) == new:
            return html, "same"
        return html[: existing.start()] + new + html[existing.end():], "rewrote subnav"

    # Insert after the closing </header> of the hero.
    hero = re.search(r'<header class="hero".*?</header>', html, re.S)
    if not hero:
        return html, "no hero to attach the subnav to"
    at = hero.end()
    return html[:at] + "\n\n" + new + html[at:], "inserted"


if __name__ == "__main__":
    raise SystemExit(main())
