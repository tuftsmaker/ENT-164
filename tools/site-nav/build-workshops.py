#!/usr/bin/env python3
"""Build the workshops landing page from the class pages and the syllabus.

`workshops/index.html` is generated, not hand-written, for the same reason the
task catalog is: it is a list of facts that already exist elsewhere (each class
page's title, the syllabus week and date, whether a deck exists yet), and a
hand-maintained copy drifts the moment a class is added or a deck lands.

The class pages remain the source of truth for what a workshop is. This reads
them and presents the whole semester as one page.

    python3 tools/site-nav/build-workshops.py
    python3 tools/site-nav/build-workshops.py --check    # fail if stale
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

import nav as site_nav  # noqa: E402

OUT = REPO / "workshops" / "index.html"


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def clean(text: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", "", text or "").split())


def first(pattern: str, text: str, group: int = 1) -> str:
    m = re.search(pattern, text, re.S)
    return clean(m.group(group)) if m else ""


def read_schedule() -> dict:
    """Week -> (date, syllabus title), from the syllabus page."""
    t = (REPO / "syllabus" / "index.html").read_text()
    m = re.search(r'id="schedule".*?id="grading"', t, re.S)
    seg = m.group(0) if m else ""
    out = {}
    for article in re.findall(r'<article class="week[^"]*".*?</article>', seg, re.S):
        num = first(r'week-num">(.*?)<', article)
        date = first(r'week-date">(.*?)<', article)
        title = first(r'<h3[^>]*>(.*?)</h3>', article)
        out[num] = (date, title)
    return out


def read_workshops() -> list:
    """Every class page, as (number, title, blurb, href, has_deck, date)."""
    schedule = read_schedule()
    rows = []
    for folder in sorted((REPO / "classes").iterdir()):
        m = re.match(r"class-(\d+)$", folder.name)
        if not m or not (folder / "index.html").exists():
            continue
        number = int(m.group(1))
        t = (folder / "index.html").read_text()

        title = first(r'<h1[^>]*>(.*?)</h1>', t)
        lede = first(r'<p class="lede[^"]*"[^>]*>(.*?)</p>', t)
        if not lede:
            lede = first(r'<p class="lead[^"]*"[^>]*>(.*?)</p>', t)
        if len(lede) > 200:
            lede = lede[:197].rsplit(" ", 1)[0] + "…"

        week = schedule.get(f"Week {number}", ("", ""))
        has_deck = (folder / "slides.html").exists() and bool(list(folder.glob("*.pdf")))

        rows.append(
            {
                "number": number,
                "title": title or f"Class {number}",
                "blurb": lede,
                "href": f"../{folder.name}/",
                "deck": has_deck,
                "date": week[0],
                "week_title": week[1],
            }
        )
    return rows


CSS = """
  /* The workshops list: one row per class, deck state visible at a glance. */
  .ws-list { display: grid; gap: 14px; }
  .ws-row { display: grid; grid-template-columns: 54px minmax(0,1fr) auto; gap: 18px;
            align-items: start; border: 1px solid var(--line); border-radius: 14px;
            background: var(--paper); padding: 18px 20px; }
  .ws-row:hover { border-color: #cfe1f7; background: var(--blue-tint); }
  .ws-num { font-size: 24px; font-weight: 800; color: var(--blue-deep); text-align: center; line-height: 1.1; }
  .ws-body h3 { margin: 0 0 5px; font-size: 1.05rem; }
  .ws-body h3 a { color: var(--ink); }
  .ws-body p { margin: 0; color: var(--muted); font-size: 14.5px; }
  .ws-meta { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px;
             color: var(--muted); font-size: 13px; }
  .ws-state { white-space: nowrap; align-self: center; }
  .ws-pill { display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .06em;
             text-transform: uppercase; border-radius: 999px; padding: 3px 10px; }
  .ws-pill.ready { color: var(--blue-deep); background: var(--blue-tint); }
  .ws-pill.soon { color: #8a5a00; background: #fff4e0; }
  @media (max-width: 640px) {
    .ws-row { grid-template-columns: 40px minmax(0,1fr); }
    .ws-state { grid-column: 2; }
  }
"""


def page() -> str:
    rows = read_workshops()
    ready = sum(1 for r in rows if r["deck"])
    items = []
    for r in rows:
        pill = (
            '<span class="ws-pill ready">Deck ready</span>'
            if r["deck"]
            else '<span class="ws-pill soon">Deck coming</span>'
        )
        meta = []
        if r["date"]:
            meta.append(f'<span>{esc(r["date"])}</span>')
        if r["week_title"]:
            meta.append(f'<span>{esc(r["week_title"])}</span>')
        meta.append(f'<span>Week {r["number"]}</span>')
        items.append(
            f"""<article class="ws-row">
          <div class="ws-num">{r["number"]}</div>
          <div class="ws-body">
            <h3><a href="{esc(r['href'])}">{esc(r['title'])}</a></h3>
            <p>{esc(r['blurb'])}</p>
            <p class="ws-meta">{' · '.join(meta)}</p>
          </div>
          <div class="ws-state"><a class="btn btn-ghost btn-sm" href="{esc(r['href'])}">{esc(pill)}</a></div>
        </article>"""
        )

    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Workshops &mdash; ENT-164</title>
<meta name="description" content="Every workshop in ENT-164 Intro to Making: the semester's classes in order, each with its own page and, where it is ready, the deck as a PDF.">
<link rel="stylesheet" href="../assets/site.css">
<style>{CSS}</style>
</head>
<body class="page-class">
"""
    return head + site_nav.main_nav(1, "../syllabus/", "Course syllabus &rarr;") + f"""
<header class="hero">
  <div class="wrap">
    <p class="kicker reveal">Workshops</p>
    <h1 class="reveal">Thirteen weeks,<br><span class="accent">one workshop at a time</span></h1>
    <p class="lead reveal">Each workshop has its own page: what we cover, what you make,
    and what is due. Where the deck is ready you can read it on the web or take the PDF
    to class.</p>
    <div class="pills reveal">
      <span class="pill">{len(rows)} workshops</span>
      <span class="pill">{ready} decks ready</span>
      <span class="pill">Thursdays 1:20&ndash;4:20pm</span>
      <span class="pill">JCC 301 / Nolop</span>
    </div>
    <div class="cta-row reveal">
      <a class="btn btn-primary" href="#list">See the workshops &rarr;</a>
      <a class="btn btn-ghost" href="../syllabus/#schedule">The full schedule</a>
    </div>
  </div>
</header>

<main>
  <section id="list">
    <div class="wrap">
      <div class="section-head">
        <h2>The semester</h2>
        <p>In teaching order. A workshop with its deck ready works straight from the page;
        one marked coming is a page with the plan while the deck is converted.</p>
      </div>
      <div class="ws-list">
        {chr(10).join(items)}
      </div>
    </div>
  </section>

  <section style="padding-top:0;">
    <div class="wrap">
      <div class="callout warm">
        <b>How a workshop runs.</b> We meet in the classroom for the first half to introduce
        the skill, then move to Nolop to use it. The <a href="../syllabus/">syllabus</a> has
        the learning outcomes, grading and policies; the
        <a href="../tasks/">maker skills tasks</a> are where you get each skill signed off.
      </div>
    </div>
  </section>
</main>

<footer>
  <div class="wrap foot-inner">
    <div class="foot-brand">
      <span>ENT-164 &middot; Intro to Making &mdash; class materials</span>
    </div>
    <div class="foot-links">
      <a href="../">All materials</a>
      <a href="../syllabus/">Course syllabus</a>
      <a href="../tasks/">Maker skills tasks</a>
    </div>
  </div>
</footer>

</body>
</html>
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="build-workshops")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    content = page()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == content:
        print("workshops page is up to date")
        return 0
    if args.check:
        print("stale: run tools/site-nav/build-workshops.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    rows = read_workshops()
    print(f"wrote {OUT.relative_to(REPO)} — {len(rows)} workshops, "
          f"{sum(1 for r in rows if r['deck'])} with a deck")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
