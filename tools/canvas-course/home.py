#!/usr/bin/env python3
"""Put the class home page into Canvas, from the site's theme and content.

The page body lives in `home-page.html` next to this script: the same hero,
sections and links as the class site (https://tuftsmaker.github.io/ENT-164/),
styled with the site's light palette. This script pushes it as the course's
front page and points the Home tab at it.

Canvas sanitizes page bodies on save — no `<style>` blocks, and only the CSS
properties it keeps — so the page is written in inline styles, and this script
reports what Canvas actually stored.

    python3 tools/canvas-course/home.py --dry-run     # show what it would do
    python3 tools/canvas-course/home.py               # the prototype course

Writes only ever go to the prototype. Reaching the live course needs
CANVAS_ALLOW_LIVE=1 in the environment *and* --course.

Idempotent: the page is found by its url (`home`), updated in place, and set as
the front page; the course's default view is pointed at it.

`{{syllabus_url}}` in the page is replaced with *this course's* syllabus tab
URL before it is pushed, so the prototype links at the prototype and live at
live.
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools" / "canvas-course"))
from canvas_client import DEV_COURSE, CanvasError, Client, load_config  # noqa: E402
from site_page import annotate_internal_links  # noqa: E402

SOURCE = Path(__file__).resolve().parent / "home-page.html"
PAGE_TITLE = "Home"
PAGE_URL = "home"

# Canvas's sanitizer keeps these; if they stop appearing in what it stored, the
# page will look wrong in ways worth knowing about.
SENTINELS = [
    "linear-gradient(145deg, #4c9ae6, #2f7cc9)",
    "grid-template-columns",
    "border-radius: 999px",
]


def get_or_none(client, path):
    try:
        return client._request("GET", path)
    except CanvasError as exc:
        if "HTTP 404" in str(exc):
            return None
        raise


def main() -> int:
    ap = argparse.ArgumentParser(prog="home")
    ap.add_argument("--course", default=DEV_COURSE,
                    help=f"Canvas course id (default {DEV_COURSE}, the prototype)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        config = load_config()
        config["course_id"] = str(args.course)
        client = Client(**config)
    except CanvasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        page = get_or_none(client, f"/courses/{client.course_id}/pages/{PAGE_URL}")
        front = get_or_none(client, f"/courses/{client.course_id}/front_page")
        course = client._request("GET", f"/courses/{client.course_id}")
        tabs = client.get(f"/courses/{client.course_id}/tabs")
    except CanvasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # The syllabus links point at *this course's* syllabus tab — the generated
    # syllabus lives in Canvas now (tools/canvas-course/syllabus.py).
    syllabus_url = next((t.get("full_url") for t in tabs if t.get("id") == "syllabus"), None) \
        or f"{client.base}/courses/{client.course_id}/assignments/syllabus"
    body = SOURCE.read_text(encoding="utf-8").replace("{{syllabus_url}}", syllabus_url)

    # Class-page links point at this course's generated Canvas pages when they
    # exist (recorded by pages.py), and at the class site until then.
    ids_path = SOURCE.parent / "canvas-ids.yml"
    ids = yaml.safe_load(ids_path.read_text(encoding="utf-8")) if ids_path.exists() else {}
    page_urls = ((ids.get(str(client.course_id)) or {}).get("pages")) or {}
    unknown = []

    def page_link(match):
        slug = match.group(1)
        url = page_urls.get(slug)
        if url:
            return f"{client.base}/courses/{client.course_id}/pages/{url}"
        unknown.append(slug)
        return f"https://tuftsmaker.github.io/ENT-164/classes/{slug}/"

    body = re.sub(r"\{\{page:([a-z0-9-]+)\}\}", page_link, body)
    body = annotate_internal_links(body)

    print(f"course {args.course}: {SOURCE.relative_to(ROOT)} ({len(body):,} bytes)")
    print(f"  {'update' if page else 'create'} page '{PAGE_TITLE}' (/{PAGE_URL})")
    print(f"  syllabus links: {syllabus_url}")
    if unknown:
        print(f"  class links still on the site: {len(unknown)} ({', '.join(sorted(set(unknown)))})")
    print(f"  front page: {front.get('url') if front else '(none)'} -> {PAGE_URL}")
    print(f"  default view: {course.get('default_view')} -> wiki")

    if args.dry_run:
        print("\nnothing written (--dry-run)")
        return 0

    try:
        if page:
            client.put(f"/courses/{client.course_id}/pages/{PAGE_URL}",
                       wiki_page={"title": PAGE_TITLE, "body": body, "published": True})
            print(f"  updated page '{PAGE_TITLE}'")
        else:
            client.post(f"/courses/{client.course_id}/pages",
                        wiki_page={"title": PAGE_TITLE, "body": body, "published": True})
            print(f"  created page '{PAGE_TITLE}'")

        if not front or front.get("url") != PAGE_URL:
            client.put(f"/courses/{client.course_id}/pages/{PAGE_URL}",
                       wiki_page={"front_page": True})
            print("  set as the front page")

        if course.get("default_view") != "wiki":
            client.put(f"/courses/{client.course_id}", course={"default_view": "wiki"})
            print("  Home tab now shows the page (default_view=wiki)")

        saved = get_or_none(client, f"/courses/{client.course_id}/pages/{PAGE_URL}") or {}
        stored = saved.get("body") or ""
        missing = [s for s in SENTINELS if s not in stored]
        print(f"  Canvas stored {len(stored):,} bytes")
        for s in missing:
            print(f"  warning: Canvas dropped this from the page: {s}")
    except CanvasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"\n  {client.base}/courses/{client.course_id}/pages/{PAGE_URL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
