#!/usr/bin/env python3
"""Render the assignment data into the site, and keep it rendered.

One source of truth: `classes/class-NN/assignments.yml` (Canvas content plus the
entries the repo authors). This writes two surfaces, both between
`<!-- assignments:begin -->` and `<!-- assignments:end -->` markers — the same
pattern `tools/site-nav/apply.py` uses for the navs:

* the **syllabus week chips**, one chip per assignment in the week it is due;
* the **class names** everywhere they are repeated — the syllabus week
  headings and the deck cards on the hub and the workshops page all take the
  class page's own name, so the schedule, the site and the Canvas modules
  cannot drift apart;
* each class page's **"What's due" block**, the assignments homed in that class
  (name, meta, the description's first paragraph, and a Canvas link when the
  assignment exists in Canvas).

The hand-written teaching sections on class pages stay as they are; this adds
the block before the page's closing section.

    python3 tools/canvas-course/render-assignments.py           # rewrite
    python3 tools/canvas-course/render-assignments.py --check   # verify only

An entry lands in the syllabus week whose class day is the last on or before
its due date (read in Eastern time), unless it carries a `week:` override. The
chip shows "👤|👥 · <summary>" — the audience as an icon, with the word in the
`title` — and an entry without a summary
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
HOME = ROOT / "index.html"
WORKSHOPS = ROOT / "workshops" / "index.html"
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
CLASS_TITLE = re.compile(r"<title>ENT-164 · Class \d+ — ([^<]+)</title>")
HEADING = re.compile(r"(<h3[^>]*>).*?(</h3>)", re.S)
DECK_CARD = re.compile(r'(<h3><a href="(?:\.\./)*classes/class-(\d+)/"[^>]*>)(.*?)(</a></h3>)', re.S)
WEEK_LINE = re.compile(r'(<a href="\{\{(?:page:class-(\d+)|syllabus_url)\}\}"><b>)([^<]*)(</b></a>)([^<]*)')
WORKSHOP_CHIP = re.compile(r'(<a class="chip"[^>]*>)(.*?)(</a>)', re.S)
CHIPS_DIV = re.compile(r'<div class="chips">(.*?)</div>', re.S)
OG_TITLE = re.compile(r'(<meta property="og:title" content="ENT-164 · Class \d+ — )(.*?)(">)')
DECK_TITLE = re.compile(r'(<title>ENT-164 Class \d+ · )(.*?)( — Slides</title>)')
DECK_FOOTER = re.compile(r'(<span>Class \d+ · )(.*?)(</span>)')
WEEK_LABEL = re.compile(r'(<b>Week \d+ · )(.*?)(</b>)')
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


def week_headings(html):
    """Week number -> the syllabus week's own heading, for weeks with no class
    page (week 7 is a working session, so it has no class page to name it)."""
    out = {}
    for article in ARTICLE.finditer(html):
        text = article.group(0)
        number = WEEK_NUM.search(text)
        heading = HEADING.search(text)
        if number and heading:
            out[int(number.group(1))] = re.sub(
                r"\s+", " ", re.sub(r"<[^>]+>", "", heading.group(0))).strip()
    return out


def plain_name(name: str) -> str:
    """A name without its leading audience icon.

    The repo's assignment names carry 👤/👥 (they are pushed to Canvas, so the
    module list and gradebook show them); this reads the name back for display
    under one icon, and is the key the tools match a live assignment on.
    """
    return re.sub(r"^[^\w]+ ?", "", name or "")


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


ICONS = {"Individual": "👤", "Team": "👥"}


def audience_icon(entry):
    """The audience as an icon; the word stays in `title` for hover and readers."""
    label = audience(entry)
    icon = ICONS.get(label, "")
    return f'<span title="{label}">{icon}</span>' if icon else label


def chip(entry):
    text = entry.get("summary") or re.sub(r"^Individual Assignment:\s*", "", plain_name(entry["name"]))
    return f'{audience_icon(entry)} · {text}'


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
    parts = []
    if points is not None:
        parts.append(f"{float(points):g} pt" if float(points) > 0 else "check-in")
    if entry.get("due"):
        due = datetime.fromisoformat(entry["due"].replace("Z", "+00:00")).astimezone(ET)
        parts.append("due " + due.strftime("%a, %b %-d"))
    else:
        parts.append("in class")
    when = " · ".join(parts)
    summary = entry.get("summary") or plain_name(entry["name"])
    title = re.split(r" — |\. ", summary)[0].strip()
    body = first_paragraph(entry.get("_html") or _description(entry))
    if not body:
        parts = re.split(r" — |\. ", summary, maxsplit=1)
        body = parts[1] if len(parts) > 1 else plain_name(entry["name"])
    lines = [
        '<div class="card">',
        f'  <span class="num">{when}</span>',
        f"  <h3>{audience_icon(entry)} {title}</h3>",
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


def due_sections(week, entries, live_ids, web, live_id, weeks):
    """The class page's due blocks: what is due on this class's day, and what
    falls due by the next one. An in-class item is only ever "due today" — it
    is done during its own class, not prepared for in advance."""
    today, later = weeks.get(week), weeks.get(week + 1)
    if today is None:
        return ""

    def due_date(entry):
        if not entry.get("due"):
            return None
        return datetime.fromisoformat(str(entry["due"]).replace("Z", "+00:00")) \
            .astimezone(ET).date()

    groups = [
        ("What's due today",
         sorted((e for e in entries if due_date(e) == today),
                key=lambda e: (due_date(e), plain_name(e["name"])))),
        ("What's due next week",
         sorted((e for e in entries
                 if later and not e.get("in_class")
                 and due_date(e) is not None and today < due_date(e) <= later),
                key=lambda e: (due_date(e), plain_name(e["name"])))),
    ]
    blocks = []
    for heading, hits in groups:
        if not hits:
            continue
        # the first block carries the page's "What's due" anchor, so a sidebar
        # link lands on whichever list the week actually has
        anchor = "due" if not blocks else "due-next"
        lines = [f'<section class="section-block" id="{anchor}">',
                 f"  <h2>{heading}</h2>",
                 '  <div class="cards">']
        for entry in hits:
            for line in card(entry, live_ids, web, live_id):
                lines.append("    " + line)
        lines += ["  </div>", "</section>"]
        blocks.append("\n".join(lines))
    if not blocks:
        return ""
    return ("<!-- assignments:begin -->\n" + "\n\n".join(blocks)
            + "\n<!-- assignments:end -->")


def rewrite_class_page(html, week, entries, live_ids, web, live_id, weeks):
    block = due_sections(week, entries, live_ids, web, live_id, weeks)
    if MARKERS.search(html):
        return MARKERS.sub(block, html)
    if not block:
        return html
    sections = list(CLASS_SECTION.finditer(html))
    if not sections:
        raise SystemExit("class page has no section to insert before")
    at = sections[-1].start()
    return html[:at] + block + "\n\n" + html[at:]


def class_names():
    """Week number -> the class page's name — the one source for the week's
    heading, the Canvas page title and the module name."""
    names = {}
    for path in sorted(CLASSES.glob("class-*/index.html")):
        week = int(path.parent.name.split("-")[1])
        found = CLASS_TITLE.search(path.read_text(encoding="utf-8"))
        if found:
            names[week] = found.group(1).strip()
    return names


def sync_heading(article: str, week, names: dict) -> str:
    """Give the week the class page's name, so the two cannot drift."""
    name = names.get(week) if week else None
    if not name:
        return article
    return HEADING.sub(lambda m: m.group(1) + name + m.group(2), article, count=1)


def sync_og_title(html: str, name: str) -> str:
    """The page's social title carries the class name too."""
    return OG_TITLE.sub(lambda m: m.group(1) + name + m.group(3), html, count=1)


def sync_deck(html: str, names: dict) -> str:
    """A deck's title and footers name its own class; its roadmap labels name
    the other weeks — all from the class pages, so a rename reaches them."""
    html = DECK_TITLE.sub(
        lambda m: m.group(1) + names.get(int(m.group(1).split()[2]), m.group(2)) + m.group(3), html)
    html = DECK_FOOTER.sub(
        lambda m: m.group(1) + names.get(int(m.group(1).split()[1]), m.group(2)) + m.group(3), html)
    return WEEK_LABEL.sub(
        lambda m: m.group(1) + names.get(int(m.group(1).split()[1]), m.group(2)) + m.group(3), html)


def sync_workshop(article: str, week, names: dict) -> str:
    """The workshop chip ("Workshop 5 · Electronics — slides & notes") too."""
    name = names.get(week) if week else None
    if not name:
        return article

    def fix(match):
        rest = re.search(r"—\s*(.*)$", match.group(2), re.S)
        suffix = f". {rest.group(1).strip()}" if rest else ""
        return f"{match.group(1)}<b>Workshop {week}</b> · {name}{suffix}{match.group(3)}"

    return WORKSHOP_CHIP.sub(fix, article, count=1)


def sync_cards(html: str, names: dict) -> str:
    """The deck cards on the hub and the workshops page carry the class name."""
    return DECK_CARD.sub(
        lambda m: m.group(1) + names.get(int(m.group(2)), m.group(3)) + m.group(4), html)


def sync_home_weeks(html: str, names: dict, dates: dict, headings: dict) -> str:
    """The Canvas home page's week list is generated from the syllabus: the week
    number and date, and the week's name. The link itself stays as it is (week 7
    points at the syllabus, because it has no class page)."""
    def fix(match):
        prefix, number, label, close, tail = match.groups()
        week = int(number) if number else int(re.search(r"Week (\d+)", label).group(1))
        date = dates.get(week)
        name = names.get(week) or headings.get(week)
        if not date or not name:
            return match.group(0)
        return f"{prefix}Week {week} · {date.strftime('%b %-d')}{close}: {name}"

    return WEEK_LINE.sub(fix, html)


def rewrite_syllabus(html, weeks, entries):
    names = class_names()
    by_week = {}
    for entry in entries:
        by_week.setdefault(entry_week(entry, weeks), []).append(entry)
    for week in by_week:
        by_week[week].sort(key=lambda e: (e.get("due") or "", plain_name(e["name"])))
    parts = []
    for article in ARTICLE.finditer(html):
        text = article.group(0)
        number = WEEK_NUM.search(text)
        week = int(number.group(1)) if number else None
        chips = [chip(e) for e in by_week.get(week, [])] if week else []
        text = sync_heading(text, week, names)
        text = sync_workshop(text, week, names)
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
    week_list = week_dates(syllabus)          # (week, date) pairs for the chips
    weeks = dict(week_list)                   # the same, for the due sections
    all_entries = [e for es in per_class.values() for e in es]
    updated = rewrite_syllabus(syllabus, week_list, all_entries)

    pages = {}
    for cls in sorted(per_class):
        page = CLASSES / cls / "index.html"
        if not page.exists():
            continue
        week = int(cls.split("-")[1])
        pages[page] = rewrite_class_page(page.read_text(encoding="utf-8"), week,
                                         all_entries, live_ids, web, live_id, weeks)

    names = class_names()
    for path in (HOME, WORKSHOPS):
        pages[path] = sync_cards(path.read_text(encoding="utf-8"), names)
    pages[HERE / "home-page.html"] = sync_home_weeks(
        (HERE / "home-page.html").read_text(encoding="utf-8"), names,
        dict(week_dates(syllabus)), week_headings(syllabus))
    for path in sorted(CLASSES.glob("class-*/index.html")):
        week = int(path.parent.name.split("-")[1])
        name = names.get(week)
        if name:
            pages[path] = sync_og_title(pages.get(path) or path.read_text(encoding="utf-8"), name)
    for path in sorted(CLASSES.glob("class-*/slides.html")):
        pages[path] = sync_deck(path.read_text(encoding="utf-8"), names)

    if args.check:
        stale = []
        if updated != syllabus:
            stale.append(SYLLABUS)
        stale += [p for p, text in pages.items() if p.read_text(encoding="utf-8") != text]
        for path in stale:
            print(f"  stale: {path.relative_to(ROOT)}")
        total = sum(len(v) for v in per_class.values())
        print(f"\n{'stale pages found' if stale else 'pages match the assignment data'}"
              f" — {total} entry(ies), {len(pages)} page(s)")
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
