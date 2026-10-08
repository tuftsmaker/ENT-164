#!/usr/bin/env python3
"""Push the class pages into Canvas — generated from the site masters.

Every class page and the workshops index becomes a Canvas page, converted with
`site_page` (inline styles, hotlinked images). Canvas builds a page's URL from
its title, so the title is the page's identity here: a page is found by title,
created if missing, and the URL Canvas gives back is what the module items and
the pages' own links use (recorded in `canvas-ids.yml` as `pages`). Because the
links need those URLs, each page is built twice — a provisional body first, then
the final body once every URL is known.

Module wiring: each class module gains a page **Page** item near the top,
pointing at the generated page. Canvas ties a Page item's title to the page's
own title, so the two always read the same. The slides item stays an
ExternalUrl to the site PDF (artifacts are links).

    python3 tools/canvas-course/pages.py --list         # what would be pushed
    python3 tools/canvas-course/pages.py --out DIR      # write the generated bodies
    python3 tools/canvas-course/pages.py --dry-run      # show the plan
    python3 tools/canvas-course/pages.py                # the prototype
    python3 tools/canvas-course/pages.py --check        # compare Canvas to the masters

Writes only ever go to the prototype; live needs CANVAS_ALLOW_LIVE=1 in the
environment *and* --i-know, and is refused otherwise.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import posixpath
import re
import sys
from datetime import datetime
from html import escape, unescape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import yaml  # noqa: E402
from canvas_client import (  # noqa: E402
    OVERRIDE_ENV,
    PROTOTYPE_COURSE,
    CanvasError,
    Client,
    load_config,
)
from site_page import H2, RULE, WRAP, SITE, annotate_internal_links, normalized, parse, render, unpublished_class_from  # noqa: E402

# render-assignments.py owns the assignment data — the syllabus week dates, the
# per-class files, the Eastern-time due dates. Loaded by path because the file
# name carries a dash; its main() is guarded, so importing runs nothing.
_RA_SPEC = importlib.util.spec_from_file_location("render_assignments", HERE / "render-assignments.py")
render_assignments = importlib.util.module_from_spec(_RA_SPEC)
_RA_SPEC.loader.exec_module(render_assignments)

HERO = re.compile(r'<header class="hero">.*?</header>', re.S)
MAIN = re.compile(r"<main[^>]*>(.*?)</main>", re.S)
SECTION = re.compile(r"<section[^>]*>(.*?)</section>", re.S)
TITLE = re.compile(r"<title>(.*?)</title>", re.S)
EXTERNAL = ("http://", "https://", "mailto:", "tel:")
# An absolute Canvas link to an assignment, e.g. from the generated "What's
# due" cards; rewritten per course from the id map, in internal-link form.
CANVAS_ASSIGNMENT = re.compile(r"^https?://[^/]+/courses/(\d+)/assignments/(\d+)$")
H2_TEXT = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
# The practical blocks: the generated "What's due" cards and the authored
# assignment and reflection sections. They belong on the page whole.
KEEP_HEADING = re.compile(r"(due|assignment|reflection|deliverable|checkpoint)", re.I)


def _plain(fragment: str) -> str:
    """A fragment's text: tags dropped, entities read through, space collapsed.

    Plain — callers escape on output, and matches (e.g. a heading test) read
    the real characters, apostrophes included.
    """
    text = re.sub(r"<[^>]+>", " ", fragment or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


COVERAGE_GRID = "display:flex;flex-wrap:wrap;gap:14px;margin:16px 0;align-items:stretch;"
COVERAGE_CARD = ("flex: 1 1 360px; background: #f7f9fc; border: 1px solid #e6eaf1; "
                 "border-radius: 14px; padding: 15px 17px; margin: 0;")
COVERAGE_NUM = ("display: inline-block; background: #e3eefb; color: #1F6FD0; "
                "border-radius: 999px; padding: 2px 9px; font-size: 12px;")
COVERAGE_TEXT = "margin: 8px 0 0; color: #0d1526; font-size: 16px; line-height: 1.45;"
COVERAGE_DESC = "margin: 6px 0 0; color: #3f4a5a; font-size: 14.5px; line-height: 1.5;"




HERO_IMAGE = "display:block;width:100%;height:auto;border-radius:14px;border:1px solid #e6eaf1;"


LINK_GRID = "display:flex;flex-wrap:wrap;gap:14px;margin:16px 0;align-items:stretch;"
LINK_CARD = ("flex: 1 1 320px; background: #ffffff; border: 1px solid #e6eaf1; "
             "border-radius: 14px; padding: 14px 16px; margin: 0;")
LINK_TITLE = "margin: 0 0 4px; color: #0d1526; font-size: 16px;"
LINK_NOTE = "margin: 0; color: #3f4a5a; font-size: 14.5px; line-height: 1.5;"


def links_of(page_path: Path) -> list:
    """A class's resource links from `coverage.yml`, as (title, url, note).

    These are the things a student should open to follow the class — a signup,
    a tutorial series — that used to sit as bare module items. The url may be
    relative (resolved against the page) or absolute.
    """
    config = page_path.parent / "coverage.yml"
    if not config.exists():
        return []
    data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    out = []
    for entry in data.get("links") or []:
        if isinstance(entry, dict):
            title = str(entry.get("title") or "").strip()
            url = str(entry.get("url") or "").strip()
            note = str(entry.get("note") or "").strip()
        else:
            title, url, note = str(entry).strip(), "", ""
        if title and url:
            out.append((title, url, note))
    return out


def hero_of(page_path: Path):
    """A class's overview image from `coverage.yml`, as (site url, alt, cap).

    The image is hotlinked from the class site like every other page image;
    `hero_alt` is required with it, so a slow or blocked load still reads.
    `hero_max` caps the width in pixels for a photo that would otherwise run
    the full column — a portrait shot renders very tall at 980px wide.
    """
    config = page_path.parent / "coverage.yml"
    if not config.exists():
        return None
    data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    src = str(data.get("hero") or "").strip()
    if not src:
        return None
    where = posixpath.normpath(posixpath.join(page_path.parent.relative_to(ROOT).as_posix(), src))
    cap = str(data.get("hero_max") or "").strip()
    return SITE + where, str(data.get("hero_alt") or "").strip(), (int(cap) if cap.isdigit() else None)


def coverage_of(page_path: Path) -> list:
    """A class's "What we'll cover" topics from `coverage.yml` beside the page.

    The file is the master: it holds a reading of the deck — the main topics
    and what each one teaches, not its slide titles — and the Canvas page is
    generated from it. Each entry is `{title, learn}`, or a bare title string.
    """
    config = page_path.parent / "coverage.yml"
    if not config.exists():
        return []
    data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    topics = []
    for entry in data.get("topics") or []:
        if isinstance(entry, dict):
            title = str(entry.get("title") or "").strip()
            learn = str(entry.get("learn") or "").strip()
        else:
            title, learn = str(entry).strip(), ""
        if title:
            topics.append((title, learn))
    return topics


def summary_sections(main_html: str):
    """A class page's sections as (headings, kept).

    Kept sections are rendered whole: the "What's due" blocks and the
    unlabelled notes and callouts. The rest of the body — the deck's material
    retold — is left where it belongs, in the slides; the headings are only a
    fallback outline for a class that has no `coverage.yml` yet.
    """
    headings, kept = [], []
    for section in SECTION.finditer(main_html):
        chunk = section.group(1)
        heading = H2_TEXT.search(chunk)
        title = _plain(heading.group(1)) if heading else ""
        if not title or KEEP_HEADING.search(title):
            kept.append(chunk)
        else:
            headings.append(title)
    return headings, kept


def pages() -> dict:
    """site-relative path -> (slug, title).

    The title is the Canvas identity — Canvas builds a page's URL from it, and
    a Page module item shows the page's own title, so it has to read well in
    both places ("Class 2: Hand Making and Robot Challenge Kickoff").
    """
    out = {}
    paths = sorted((ROOT / "classes").glob("class-*/index.html"))
    paths += [ROOT / "workshops" / "index.html",
              ROOT / "opencode-setup" / "guide.html",
              ROOT / "laser-cutting" / "index.html",
              ROOT / "laser-cutting" / "guide.html",
              ROOT / "onshape-tips" / "index.html",
              ROOT / "about" / "index.html"]
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        slug = path.parent.name
        if path.name != "index.html" and path.stem not in slug:
            slug = f"{slug}-{path.stem}"
        title = unescape(re.sub(r"\s+", " ", TITLE.search(path.read_text(encoding="utf-8")).group(1))).strip()
        title = re.sub(r"^ENT-164\s*[·—–-]\s*", "", title)
        title = re.sub(r"\s*[·—–-]\s*ENT-164.*$", "", title)
        if slug.startswith("class-") and slug[6:].isdigit():
            # One page title serves both the page and its module item; the
            # module names use this form ("Class 2: …"), so match it.
            title = re.sub(r"^Class\s+(\d+)\s*[—–-]\s*", r"Class \1: ", title)
        out[rel] = (slug, title)
    return out


def make_map(page_dir: str, ctx: dict):
    """Rewrite a link from `page_dir` to whichever link it means.

    Canvas links are emitted in Canvas's **internal**, root-relative form
    (`/courses/:id/…`), the form the rich-content editor writes and that a
    course copy keeps resolving; a page that is not converted yet stays an
    absolute site link. `ctx` carries the course path, the recorded page URLs,
    and the assignment-id maps used to re-point live links at this course.
    """
    def map_href(href: str) -> str:
        href = (href or "").strip()
        if not href:
            return href
        if href.startswith(EXTERNAL):
            found = CANVAS_ASSIGNMENT.match(href)
            if found:
                course, aid = found.group(1), found.group(2)
                slug = ctx["live_id_by_assignment"].get(aid) if course == ctx["live_course"] else None
                target = ctx["assignment_by_slug"].get(slug) if slug else None
                if target:
                    return f"{ctx['course_path']}/assignments/{target}"
            return href
        if href.startswith("#"):
            return ""  # no anchors on a Canvas page; the link text stays
        raw = href.split("#")[0].split("?")[0]
        target = posixpath.normpath(posixpath.join(page_dir, raw))
        if raw.endswith("/") or (ROOT / target).is_dir():
            target = posixpath.join(target, "index.html")
        if target in SLUG_BY_PATH:
            page_url = ctx["slug_to_url"].get(SLUG_BY_PATH[target])
            return f"{ctx['course_path']}/pages/{page_url}" if page_url else SITE + target
        if target == "syllabus/index.html":
            return ctx["syllabus_path"]
        return SITE + target.lstrip("./")

    return map_href


def build(path: Path, page_dir: str, map_href, summary: bool = False,
          ctx: dict | None = None) -> str:
    html = path.read_text(encoding="utf-8")
    parts = []
    hero = HERO.search(html)
    if hero:
        parts.append(render(parse(hero.group(0)), map_href).strip())
    main = MAIN.search(html)
    if main and summary:
        image = hero_of(path)
        if image:
            src, alt, cap = image
            style = HERO_IMAGE if not cap else (
                f"display:block;width:100%;max-width:{cap}px;height:auto;"
                "border-radius:14px;border:1px solid #e6eaf1;")
            parts.append(f'<div style="margin: 0 0 4px;">'
                         f'<img src="{src}" alt="{escape(alt)}" style="{style}"></div>')
        headings, kept = summary_sections(main.group(1))
        topics = coverage_of(path) or [(heading, "") for heading in headings]
        if topics:
            cards = "".join(
                f'<div style="{COVERAGE_CARD}">'
                f'<span style="{COVERAGE_NUM}"><b>{index:02d}</b></span>'
                f'<p style="{COVERAGE_TEXT}"><b>{escape(title)}</b></p>'
                + (f'<p style="{COVERAGE_DESC}">{escape(learn)}</p>' if learn else "")
                + "</div>"
                for index, (title, learn) in enumerate(topics, 1)
            )
            parts.append(f'<hr>\n<h2 style="{H2}">What we\'ll cover</h2>\n'
                         f'<div style="{RULE}"></div>\n'
                         f'<div style="{COVERAGE_GRID}">{cards}</div>')
        resources = links_of(path)
        if resources:
            cards = "".join(
                f'<div style="{LINK_CARD}">'
                f'<p style="{LINK_TITLE}"><b><a href="{map_href(url)}">{escape(title)}</a></b></p>'
                + (f'<p style="{LINK_NOTE}">{escape(note)}</p>' if note else "")
                + "</div>"
                for title, url, note in resources
            )
            parts.append(f'<hr>\n<h2 style="{H2}">Class resources</h2>\n'
                         f'<div style="{RULE}"></div>\n'
                         f'<div style="{LINK_GRID}">{cards}</div>')
        for chunk in kept:
            parts.append("<hr>\n" + render(parse(chunk), map_href).strip())
    elif main:
        for index, section in enumerate(SECTION.finditer(main.group(1)), start=1):
            # A section number over the heading, the way a printed programme
            # numbers its parts.
            chunk = re.sub(r"(<h2[^>]*>)",
                           lambda m: f'{m.group(1)}<span class="sec-num">{index:02d}</span>',
                           section.group(1), count=1)
            parts.append("<hr>\n" + render(parse(chunk), map_href).strip())
    if not parts:
        # Guide pages: no hero, no main — a cover and a page div. Render the
        # whole body; the converter drops nav and footer and keeps the rest.
        body = re.search(r"<body[^>]*>(.*?)</body>", html, re.S)
        if body:
            parts.append(render(parse(body.group(1)), map_href).strip())
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(p for p in parts if p)).strip() + "\n"
    body = f'<div style="{WRAP}">\n{body}</div>\n'
    return annotate_internal_links(body)


def bodies(ctx: dict) -> dict:
    out = {}
    for rel, slug in SLUG_BY_PATH.items():
        page_dir = posixpath.dirname(rel)
        out[slug] = {"rel": rel, "title": TITLES[slug],
                     "body": build(ROOT / rel, page_dir, make_map(page_dir, ctx),
                                   summary=slug.startswith("class-"), ctx=ctx)}
    return out


PAGES = pages()
TITLES = {slug: title for _, (slug, title) in PAGES.items()}
PATH_BY_SLUG = {slug: rel for rel, (slug, _) in PAGES.items()}
SLUG_BY_PATH = {rel: slug for rel, (slug, _) in PAGES.items()}


def forced_unpublished(slug: str) -> bool:
    """Class pages from `class_pages_unpublished_from` on stay unpublished, so
    students cannot open future weeks. Lower weeks are not managed here: a page
    the instructor published or unpublished by hand keeps that state, and a
    body push must not change it."""
    if not (slug.startswith("class-") and slug[6:].isdigit()):
        return False
    return int(slug[6:]) >= unpublished_class_from()


def record_pages(course_id: str, urls: dict) -> None:
    ids = yaml.safe_load((HERE / "canvas-ids.yml").read_text(encoding="utf-8")) \
        if (HERE / "canvas-ids.yml").exists() else {}
    ids.setdefault(str(course_id), {})["pages"] = dict(sorted(urls.items()))
    (HERE / "canvas-ids.yml").write_text(
        "# Generated by pull-assignments.py — Canvas ids per course, by slug.\n"
        "# Ids change when a course is copied or rebuilt; the repo's identity is\n"
        "# the slug, and nothing else keys off these.\n"
        + yaml.safe_dump(ids, sort_keys=False),
        encoding="utf-8",
    )


def hrefs(html: str) -> list:
    """Every link target, for the check — text comparison cannot see them.

    Canvas re-adds its own dp_app stylesheet on save; ignore that href.
    """
    return sorted(unescape(href) for href in re.findall(r'href="([^"]*)"', html or "")
                  if "dp_app" not in href)


def link_context(course_id: str, canvas_base: str, slug_to_url: dict, syllabus_path: str) -> dict:
    """The link-rewriting context for one course."""
    spec = yaml.safe_load((HERE / "course.yml").read_text(encoding="utf-8"))
    ids = yaml.safe_load((HERE / "canvas-ids.yml").read_text(encoding="utf-8")) \
        if (HERE / "canvas-ids.yml").exists() else {}
    live = str(spec["courses"]["live"])
    live_assignments = (ids.get(live) or {}).get("assignments") or {}
    target_assignments = (ids.get(str(course_id)) or {}).get("assignments") or {}
    return {
        "course_path": f"{canvas_base}/courses/{course_id}",
        "syllabus_path": syllabus_path,
        "slug_to_url": slug_to_url,
        "live_course": live,
        "live_id_by_assignment": {str(v): k for k, v in live_assignments.items()},
        "assignment_by_slug": {k: str(v) for k, v in target_assignments.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--out", metavar="DIR", help="write the generated bodies here for review")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--course", default=PROTOTYPE_COURSE,
                    help=f"Canvas course id (default {PROTOTYPE_COURSE}, the prototype)")
    ap.add_argument("--i-know", action="store_true",
                    help=f"allow a push to the live course (same gate as {OVERRIDE_ENV}=1)")
    args = ap.parse_args()

    titles = TITLES

    if args.list or args.out:
        spec = yaml.safe_load((HERE / "course.yml").read_text(encoding="utf-8"))
        prototype = str(spec["courses"]["prototype"])
        recorded = yaml.safe_load((HERE / "canvas-ids.yml").read_text(encoding="utf-8")) \
            if (HERE / "canvas-ids.yml").exists() else {}
        urls = (recorded.get(prototype) or {}).get("pages") or {}
        base = f"{spec['canvas_web']}/courses/{prototype}"
        ctx = link_context(prototype, spec["canvas_web"], urls, f"{base}/assignments/syllabus")
        final = bodies(ctx)
        if args.list:
            for slug, title in sorted(titles.items()):
                source = (ROOT / PATH_BY_SLUG[slug]).stat().st_size
                print(f"  {slug:<24} {title[:42]:<44} {source:>6} -> {len(final[slug]['body']):>6} bytes")
            return 0
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for slug, t in final.items():
            (out / f"{slug}.html").write_text(t["body"], encoding="utf-8")
        print(f"wrote {len(final)} page(s) to {args.out}")
        return 0

    cfg = load_config()
    cfg["course_id"] = str(args.course)
    client = Client(**cfg)
    course_path = f"{client.base}/courses/{client.course_id}"
    tabs = client.get(f"/courses/{client.course_id}/tabs")
    syllabus_path = next((t.get("full_url") for t in tabs if t.get("id") == "syllabus"), None) \
        or f"{course_path}/assignments/syllabus"

    ids = yaml.safe_load((HERE / "canvas-ids.yml").read_text(encoding="utf-8")) \
        if (HERE / "canvas-ids.yml").exists() else {}
    recorded = (ids.get(str(client.course_id)) or {}).get("pages") or {}
    existing = {p["title"]: p for p in client.get(f"/courses/{client.course_id}/pages")}
    urls = {}
    renamed = []
    for slug, title in sorted(titles.items()):
        page = existing.get(title)
        if not page and recorded.get(slug) and not args.dry_run:
            # The recorded URL still answers, so the master renamed the page:
            # rename it in place. Canvas re-slugs a page when its title changes,
            # and creating a twin would orphan the old one.
            try:
                page = client._request("GET", f"/courses/{client.course_id}/pages/{recorded[slug]}")
            except CanvasError:
                page = None
            if page:
                before = page["url"]
                page = client.put(f"/courses/{client.course_id}/pages/{before}",
                                  wiki_page={"title": title, "body": page.get("body") or ""}) or page
                renamed.append((slug, before, page.get("url") or before))
        if not page:
            if args.check:
                urls[slug] = None
                continue
            page = client.post(f"/courses/{client.course_id}/pages",
                               wiki_page={"title": title, "body": "",
                                          "published": not forced_unpublished(slug)}) \
                if not args.dry_run else {"url": f"(new) {slug}"}
            if not args.dry_run:
                existing[title] = page
        urls[slug] = page["url"]

    for slug, before, after in renamed:
        print(f"  {slug}: renamed the page — /{before} -> /{after}")

    available = {slug: url for slug, url in urls.items() if url}
    ctx = link_context(client.course_id, client.base, available, syllabus_path)

    if args.check:
        stale = []
        for slug, url in urls.items():
            if url:
                continue
            if recorded.get(slug):
                try:
                    page = client._request("GET", f"/courses/{client.course_id}/pages/{recorded[slug]}")
                except CanvasError:
                    page = None
                if page:
                    stale.append(f"  stale title: {slug} — Canvas has {page.get('title')!r}, "
                                 f"the master is {titles[slug]!r}")
                    continue
            stale.append(f"  missing: {slug}")
        final = bodies(ctx)
        for slug, url in available.items():
            # The pages index omits bodies; read the page itself.
            page = client._request("GET", f"/courses/{client.course_id}/pages/{url}") or {}
            stored = page.get("body") or ""
            if normalized(stored) != normalized(final[slug]["body"]) or hrefs(stored) != hrefs(final[slug]["body"]):
                stale.append(f"  stale: {slug}")
            if forced_unpublished(slug) and page.get("published"):
                stale.append(f"  stale publish state: {slug} — Canvas has it published, "
                             f"class_pages_unpublished_from says keep it hidden")
        # Canvas ties a Page module item to its page, so the module's name is
        # the page's title — and it has to carry the same one.
        module_ids = (ids.get(str(client.course_id)) or {}).get("modules") or {}
        module_names = {module["id"]: module["name"] for module in client.modules()}
        for slug in sorted(slug for slug in titles if slug.startswith("class-")):
            current = module_names.get(module_ids.get(slug))
            if current and current != titles[slug]:
                stale.append(f"  stale module name: {slug} — Canvas has {current!r}, "
                             f"the master is {titles[slug]!r}")
        for line in stale:
            print(line)
        print(f"\n{'pages differ from the masters' if stale else 'Canvas pages match the masters'}")
        return 1 if stale else 0

    if args.dry_run:
        for slug in sorted(titles):
            print(f"  {'create' if str(urls.get(slug, '')).startswith('(new)') else 'update'} {slug}")
        print("\nnothing written (--dry-run)")
        return 0

    final = bodies(ctx)
    for slug in sorted(final):
        wiki_page = {"title": final[slug]["title"], "body": final[slug]["body"]}
        if forced_unpublished(slug):
            wiki_page["published"] = False
        client.put(f"/courses/{client.course_id}/pages/{urls[slug]}", wiki_page=wiki_page)
    print(f"  pushed {len(final)} page(s)")
    record_pages(client.course_id, urls)

    # A Page item near the top of each class module, carrying the page's own
    # title (Canvas ties the two together) — so the module's name must match it.
    modules = (ids.get(str(client.course_id)) or {}).get("modules") or {}
    class_slugs = {slug for slug in final if slug.startswith("class-")}
    by_id = {module["id"]: module for module in client.modules()}
    for slug in sorted(class_slugs):
        module_id = modules.get(slug)
        if not module_id:
            continue
        wanted = TITLES[slug]
        module = by_id.get(module_id)
        if module and module["name"] != wanted:
            client.update_module(module_id, name=wanted)
            print(f"  {slug}: renamed the module to {wanted!r}")
        items = client.module_items(module_id)
        if any(item.get("page_url") == urls[slug] for item in items):
            print(f"  {slug}: module already carries the page")
            continue
        # A renamed page leaves its old item behind; replace it rather than
        # stacking a second one on top. (Renaming the item instead would
        # rename the page — Canvas ties a Page item's title to the page.)
        for item in items:
            title = str(item.get("title", ""))
            if item.get("page_url") and (title.startswith("Class page")
                                         or re.match(r"^Class \d+\b", title)):
                client._request("DELETE",
                                f"/courses/{client.course_id}/modules/{module_id}/items/{item['id']}")
                print(f"  {slug}: removed the item for the old page")
        client.add_module_item(module_id, type="Page", page_url=urls[slug],
                               title=wanted, position=2)
        print(f"  {slug}: added the page item to its module")

    # Other module items that point at a converted page (the laser guide, the
    # tips page) become Page items too; artifacts (PDFs, videos) stay links.
    by_site_url = {}
    for rel, slug in SLUG_BY_PATH.items():
        by_site_url[(SITE + rel).removesuffix("index.html").rstrip("/")] = slug
    for module in client.modules():
        items = client.module_items(module["id"])
        linked = {item.get("page_url") for item in items if item.get("page_url")}
        for item in items:
            url = (item.get("external_url") or "").rstrip("/")
            slug = by_site_url.get(url)
            if not slug or item.get("page_url") or slug in linked:
                continue
            client._request("DELETE", f"/courses/{client.course_id}/modules/{module['id']}/items/{item['id']}")
            client.add_module_item(module["id"], type="Page", page_url=urls[slug],
                                   title=item.get("title") or TITLES[slug],
                                   position=item.get("position"))
            print(f"  {module['name'][:28]}: '{item['title'][:40]}' is now the Canvas page")
    print(f"\n  {course_path}/pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
