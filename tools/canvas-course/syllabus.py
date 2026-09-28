#!/usr/bin/env python3
"""Push the course syllabus into Canvas — generated from the master copy.

`syllabus/index.html` is the source of truth (see AGENTS.md). This converts its
content into the Canvas syllabus body — inline styles and basic tags, links
rewritten to the site — and pushes it with `PUT /courses/:id`
(`course[syllabus_body]`). The Google Doc link it used to hold is replaced.

    python3 tools/canvas-course/syllabus.py --dry-run          # generate and preview
    python3 tools/canvas-course/syllabus.py --out /tmp/s.html  # save the generated HTML
    python3 tools/canvas-course/syllabus.py                    # push to the prototype
    python3 tools/canvas-course/syllabus.py --check            # compare what Canvas holds

Writes only ever go to the prototype; live needs CANVAS_ALLOW_LIVE=1 in the
environment *and* --i-know, and is refused otherwise.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import yaml  # noqa: E402
from canvas_client import (  # noqa: E402
    OVERRIDE_ENV,
    PROTOTYPE_COURSE,
    Client,
    load_config,
)
from site_page import WRAP, SITE as SITE_BASE, find_class, normalized, parse, render, text_of  # noqa: E402

MASTER = ROOT / "syllabus" / "index.html"
PAGE = SITE_BASE + "syllabus/"
PDF = PAGE + "ENT-164-Syllabus-Fall-2026.pdf"
SECTION = re.compile(r'<section class="section-block" id="[^"]+">(.*?)</section>', re.S)


def absolutize(href: str) -> str:
    if href.startswith(("http://", "https://", "mailto:", "tel:")):
        return href
    if href.startswith("#"):
        return PAGE + href
    return SITE_BASE + href.lstrip("./")


def build() -> str:
    html = MASTER.read_text(encoding="utf-8")
    hero = parse(re.search(r'<header class="hero">(.*?)</header>', html, re.S).group(1))
    main = re.search(r'<main class="content">(.*?)</main>', html, re.S).group(1)

    lead = find_class(hero, "lead")
    pills = find_class(hero, "pills")
    note = find_class(hero, "note")

    lines = [
        "<h2>ENT-164 · Intro to Making — Course Syllabus</h2>",
        "<p><b>" + " · ".join(re.sub(r"\s+", " ", text_of(p)).strip() for p in pills["kids"])
        + "</b></p>" if pills is not None else "",
        "<p>" + re.sub(r"\s+", " ", text_of(lead)).strip() + "</p>" if lead is not None else "",
        f'<p><b>Canonical version:</b> the class site — <a href="{PAGE}">{PAGE}</a>'
        f' · <a href="{PDF}">download the PDF</a></p>',
        "<p><i>" + re.sub(r"\s+", " ", text_of(note)).strip() + "</i></p>" if note is not None else "",
    ]

    body = ""
    for match in SECTION.finditer(main):
        body += "<hr>\n" + render(parse(match.group(1)), absolutize).strip() + "\n"

    out = "\n".join(line for line in lines if line) + "\n" + body
    out = re.sub(r"\n{3,}", "\n\n", out)
    return f'<div style="{WRAP}">\n' + out.strip() + "\n</div>\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", metavar="PATH", help="write the generated body here for review")
    ap.add_argument("--check", action="store_true", help="compare Canvas's stored body to the master")
    ap.add_argument("--course", default=PROTOTYPE_COURSE,
                    help=f"Canvas course id (default {PROTOTYPE_COURSE}, the prototype)")
    ap.add_argument("--i-know", action="store_true",
                    help=f"allow a push to the live course (same gate as {OVERRIDE_ENV}=1)")
    args = ap.parse_args()

    body = build()
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"wrote {args.out} ({len(body):,} bytes)")

    target = str(args.course)
    cfg = load_config()
    cfg["course_id"] = target
    client = Client(**cfg)

    stored = client.get(f"/courses/{target}", include=["syllabus_body"]).get("syllabus_body") or ""
    if args.check:
        same = normalized(body) == normalized(stored)
        print(f"canvas holds {len(stored):,} chars, the master generates {len(body):,}")
        print("the stored syllabus matches the master" if same else "the stored syllabus differs — run without --check")
        return 0 if same else 1

    if args.dry_run:
        print(f"would push {len(body):,} chars to course {target}; first lines:\n")
        print("\n".join(body.splitlines()[:12]))
        print("\nnothing written (--dry-run)")
        return 0

    live = str(yaml.safe_load((HERE / "course.yml").read_text())["courses"]["live"])
    if target == live and not (args.i_know or os.environ.get(OVERRIDE_ENV) == "1"):
        sys.exit(f"refusing to push to the live course {live}: "
                 f"pass --i-know or set {OVERRIDE_ENV}=1")

    client.put(f"/courses/{target}", course={"syllabus_body": body})
    after = client.get(f"/courses/{target}", include=["syllabus_body"]).get("syllabus_body") or ""
    print(f"pushed to course {target}: wrote {len(body):,} chars, Canvas stored {len(after):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
