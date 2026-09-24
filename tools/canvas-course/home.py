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
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools" / "skill-tasks" / "canvas"))
from canvas_client import DEV_COURSE, CanvasError, Client, load_config  # noqa: E402

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

    body = SOURCE.read_text(encoding="utf-8")

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
    except CanvasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"course {args.course}: {SOURCE.relative_to(ROOT)} ({len(body):,} bytes)")
    print(f"  {'update' if page else 'create'} page '{PAGE_TITLE}' (/{PAGE_URL})")
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
