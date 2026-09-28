#!/usr/bin/env python3
"""Render the assignment data into the site, and keep it rendered.

One source of truth: `classes/class-NN/assignments.yml` (Canvas content plus the
entries the repo authors). This writes two surfaces, both between
`<!-- assignments:begin -->` and `<!-- assignments:end -->` markers — the same
pattern `tools/site-nav/apply.py` uses for the navs:

* the **syllabus week chips**, one chip per assignment in the week it is due;
* each class page's **"What's due" block**, the assignments homed in that class
  (name, meta, the description's first paragraph, and a Canvas link when the
  assignment exists in Canvas).

The hand-written teaching sections on class pages stay as they are; this adds
the block before the page's closing section.

    python3 tools/canvas-course/render-assignments.py           # rewrite
    python3 tools/canvas-course/render-assignments.py --check   # verify only

An entry lands in the syllabus week whose class day is the last on or before
its due date (read in Eastern time), unless it carries a `week:` override. The
chip shows "<b>Team|Individual</b> · <summary>"; an entry without a summary
falls back to its Canvas name.
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SYLLABUS = ROOT / "syllabus" / "index.html"
CLASSES = ROOT / "classes"
COURSE_YML = HERE / "course.yml"
IDS_YML = HERE / "canvas-ids.yml"
ET = ZoneInfo("America/New_York")

import sys  # noqa: E402
sys.path.insert(0, str(HERE))
import yaml  # noqa: E402

ARTICLE = re.compile(r'<article class="week[^"]*">.*?</article>', re.S)
WEEK_NUM = re.compile(r'<span class="week-num">Week (\d+)</span>')
WEEK_DATE = re.compile(r'<span class="week-date">([^<]+)</span>')
CHIPS_DIV = re.compile(r'<div class="chips">(.*?)</div>', re.S)
WORKSHOP_CHIP = re.compile(r'<a class="chip"[^>]*>.*?</a>', re.S)
MARKERS = re.compile(r'[ \t]*<!-- assignments:begin -->.*?<!-- assignments:end -->', re.S)
CLOSE = re.compile(r'([ \t]*)(</div>\s*</article>\s*)$', re.S)
CLASS_SECTION = re.compile(r'[ \t]*<section class="section-block"')
PARAGRAPH = re.compile(r"<p[^>]*>(.*?)</p>", re.S)

INDENT = " " * 14
DIV_INDENT = " " * 12
PAGE_INDENT = " " * 4


def week_dates(html):
    year_match = re.search(r"\b(?:Fall|Spring|Summer|Winter)\s+(\d{4})\b", html)
    if not year_match:
        raise SystemExit(f"{SYLLABUS}: no term year to read the week dates against")
    year = int(year_match.group(1))
    weeks = []
    for article in ARTICLE.finditer(html):
        number, text = WEEK_NUM.search(article.group(0)), WEEK_DATE.search(article.group(0))
        if not number or not text:
            continue
        day = text.group(1).split(", ")[-1]  # "Thu, Oct 1" -> "Oct 1"
        weeks.append((int(number.group(1)), datetime.strptime(f"{day} {year}", "%b %d %Y").date()))
    return sorted(weeks)


def audience(entry):
    if entry.get("audience"):
        return entry["audience"]
    group = entry.get("group") or ""
    if group.startswith("Team"):
        return "Team"
    for prefix in ("Individual", "Peer", "Reflections"):
        if group.startswith(prefix):
            return "Individual"
    raise SystemExit(f"{entry['slug']}: no audience and no group to read one from")


def chip(entry):
    text = entry.get("summary") or re.sub(r"^Individual Assignment:\s*", "", entry["name"])
    return f'<b>{audience(entry)}</b> · {text}'


def entry_week(entry, weeks):
    if entry.get("week"):
        return int(entry["week"])
    if not entry.get("due"):
        raise SystemExit(f"{entry['slug']}: no due date and no week override")
    due = datetime.fromisoformat(entry["due"].replace("Z", "+00:00")).astimezone(ET).date()
    hit = [number for number, day in weeks if day <= due]
    if not hit:
        raise SystemExit(f"{entry['slug']}: due {due} is before the first class")
    return hit[-1]


def entries_by_class():
    out = {}
    for path in sorted(CLASSES.glob("class-*/assignments.yml")):
        out[path.parent.name] = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return out


def plain(html):
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def first_paragraph(html):
    found = PARAGRAPH.search(html)
    text = plain(found.group(1)) if found else plain(html)
    return text or plain(html)


def card(entry, live_ids, web, live_id):
    points = entry.get("points")
    parts = [audience(entry)]
    if points is not None:
        parts.append(f"{float(points):g} pt" if float(points) > 0 else "check-in")
    if entry.get("due"):
        due = datetime.fromisoformat(entry["due"].replace("Z", "+00:00")).astimezone(ET)
        parts.append("due " + due.strftime("%a, %b %-d"))
    else:
        parts.append("in class")
    when = " · ".join(parts)
    summary = entry.get("summary") or entry["name"]
    title = summary.split(" — ")[0].strip()
    body = first_paragraph(entry.get("_html") or _description(entry))
    if not body:
        body = summary.split(" — ", 1)[1] if " — " in summary else entry["name"]
    lines = [
        '<div class="card">',
        f'  <span class="num">{when}</span>',
        f"  <h3>{title}</h3>",
        f"  <p>{body}</p>",
    ]
    aid = live_ids.get(entry["slug"])
    if aid and web and live_id:
        lines.append(
            f'  <p class="note"><a href="{web}/courses/{live_id}/assignments/{aid}">'
            f"Hand in on Canvas &rarr;</a></p>"
        )
    lines.append("</div>")
    return lines


def _description(entry):
    relative = entry.get("description")
    if not relative:
        return ""
    path = entry["_class"] / relative
    return path.read_text(encoding="utf-8") if path.exists() else ""


def section(entries, live_ids, web, live_id):
    entries = sorted(entries, key=lambda e: (e.get("due") or "", e["name"]))
    lines = [
        "<!-- assignments:begin -->",
        '<section class="section-block" id="assignments">',
        "  <h2>What's due</h2>",
        '  <div class="cards">',
    ]
    for entry in entries:
        for line in card(entry, live_ids, web, live_id):
            lines.append("    " + line)
    lines += ["  </div>", "</section>", "<!-- assignments:end -->"]
    return "\n".join(PAGE_INDENT + line for line in lines)


def rewrite_class_page(html, entries, live_ids, web, live_id):
    block = section(entries, live_ids, web, live_id)
    if MARKERS.search(html):
        return MARKERS.sub(block, html)
    sections = list(CLASS_SECTION.finditer(html))
    if not sections:
        raise SystemExit("class page has no section to insert before")
    at = sections[-1].start()
    return html[:at] + block + "\n\n" + html[at:]


def rewrite_syllabus(html, weeks, entries):
    by_week = {}
    for entry in entries:
        by_week.setdefault(entry_week(entry, weeks), []).append(entry)
    for week in by_week:
        by_week[week].sort(key=lambda e: (e.get("due") or "", e["name"]))
    parts = []
    for article in ARTICLE.finditer(html):
        text = article.group(0)
        number = WEEK_NUM.search(text)
        week = int(number.group(1)) if number else None
        chips = [chip(e) for e in by_week.get(week, [])] if week else []
        parts.append((article.start(), article.end(), rewrite_article(text, chips)))
    result = html
    for start, end, new in reversed(parts):
        result = result[:start] + new + result[end:]
    return result


def rewrite_article(article, chips):
    tidy = block(chips)
    if MARKERS.search(article):
        return MARKERS.sub(tidy, article)
    if not chips:
        return article
    found = CHIPS_DIV.search(article)
    if found:
        workshop = WORKSHOP_CHIP.search(found.group(1))
        head = workshop.group(0) if workshop else ""
        new = f'<div class="chips">{head}\n{tidy}\n{DIV_INDENT}</div>'
        return article[: found.start()] + new + article[found.end():]
    # No chips list yet: add one at the end of the week's content.
    close = CLOSE.search(article)
    body = article[: close.start()].rstrip()
    return (f"{body}\n{DIV_INDENT}<div class=\"chips\">\n{tidy}\n"
            f"{DIV_INDENT}</div>\n{close.group(1)}{close.group(2)}")


def block(chips):
    lines = ["<!-- assignments:begin -->"]
    lines += [f'<span class="chip">{c}</span>' for c in chips]
    lines.append("<!-- assignments:end -->")
    return "\n".join(INDENT + line for line in lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify the pages match the data")
    args = ap.parse_args()

    spec = yaml.safe_load(COURSE_YML.read_text(encoding="utf-8"))
    live_id = str(spec["courses"]["live"])
    web = spec.get("canvas_web")
    ids = yaml.safe_load(IDS_YML.read_text(encoding="utf-8")) if IDS_YML.exists() else {}
    live_ids = (ids.get(live_id) or {}).get("assignments") or {}

    per_class = entries_by_class()
    for cls, entries in per_class.items():
        for entry in entries:
            entry["_class"] = CLASSES / cls

    syllabus = SYLLABUS.read_text(encoding="utf-8")
    updated = rewrite_syllabus(syllabus, week_dates(syllabus), [e for es in per_class.values() for e in es])

    pages = {}
    for cls, entries in per_class.items():
        if not entries:
            continue
        page = CLASSES / cls / "index.html"
        pages[page] = rewrite_class_page(page.read_text(encoding="utf-8"), entries,
                                         live_ids, web, live_id)

    if args.check:
        stale = []
        if updated != syllabus:
            stale.append(SYLLABUS)
        stale += [p for p, text in pages.items() if p.read_text(encoding="utf-8") != text]
        for path in stale:
            print(f"  stale: {path.relative_to(ROOT)}")
        total = sum(len(v) for v in per_class.values())
        print(f"\n{'stale pages found' if stale else 'pages match the assignment data'}"
              f" — {total} entry(ies), {len(pages)} class page(s)")
        return 1 if stale else 0

    written = 0
    if updated != syllabus:
        SYLLABUS.write_text(updated, encoding="utf-8")
        written += 1
    for path, text in pages.items():
        if path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            written += 1
    print(f"updated {written} page(s) — {sum(len(v) for v in per_class.values())} entry(ies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
