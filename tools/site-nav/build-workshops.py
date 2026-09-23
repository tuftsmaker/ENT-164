#!/usr/bin/env python3
"""Build the workshops landing page from the class pages and the syllabus.

`workshops/index.html` is generated, not hand-written, for the same reason the
task catalog is: it is a list of facts that already exist elsewhere (each class
page's title and blurb, the syllabus week and date, whether a deck exists yet),
and a hand-maintained copy drifts the moment a class is added or a deck lands.

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
    """Page text as plain text: tags stripped, entities resolved.

    Without the unescape, a title written `Hand Making &amp; ...` keeps its
    entity and gets escaped a second time on the way out, which is how the page
    first shipped with `&amp;amp;` in the headings.
    """
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", text or "")).split())


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


def card_image(folder: Path, number: int) -> str:
    """The photo a workshop's card uses.

    Chosen by looking at the library rather than by filename. A card should show
    the week's *activity* — a person doing the thing — rather than a product shot
    or a diagram, because twelve cards are read as a set and the sterile ones
    stand out against the rest.

    `PICKS` names the choice per week where the class page's own leading image is
    not the best of what exists. The rest fall back to the class page's first
    content image, which is right by construction.
    """
    PACK = "../assets/photos/class/"
    PICKS = {
        # A robot on the track beats a single motor on a white sweep: it shows
        # the challenge the week is about.
        2: PACK + "class-02-robot-run.jpg",
        # Laser-cut objects in use, not a toy robot standing in for them.
        3: PACK + "laser-cut-projects.jpg",
        # A printed object on the bed, not a cart photographed in a supermarket.
        4: PACK + "printed-medallion.jpg",
        # The class page leads with a bare board shot; this shows the device
        # doing its job.
        6: PACK + "device-list-ui.jpg",
        8: PACK + "band-robot-challenge.jpg",
        # The scoreboard is a whiteboard of arithmetic; the demo is the moment.
        9: PACK + "class-09-demo-1.jpg",
        10: PACK + "device-list-ui.jpg",
        # The poetic typewriter is the week's case study, and the best image here.
        11: "../classes/class-11/shots/poetic-typewriter.jpg",
        12: PACK + "makerspace.jpg",
        13: PACK + "student-builds.jpg",
    }
    if number in PICKS:
        return PICKS[number]

    for src in re.findall(r'<img[^>]*src="([^"]+)"', (folder / "index.html").read_text()):
        if any(x in src for x in ("icon", "logo", ".svg")):
            continue
        rel = (folder / src).resolve()
        if rel.is_file() and ("assets/photos" in str(rel) or "shots" in str(rel)):
            return "../" + str(rel.relative_to(REPO))
    return PACK + "makerspace.jpg"


def deck_slide_count(folder: Path):
    """How many slides a deck has, from slides.html. None when there is no deck."""
    slides = folder / "slides.html"
    if not slides.exists():
        return None
    n = len(re.findall(r'<section class="slide', slides.read_text(errors="replace")))
    return n or None


def read_workshops() -> list:
    """Every class page, as one row of card data."""
    schedule = read_schedule()
    rows = []
    for folder in sorted((REPO / "classes").iterdir()):
        m = re.match(r"class-(\d+)$", folder.name)
        if not m or not (folder / "index.html").exists():
            continue
        number = int(m.group(1))
        t = (folder / "index.html").read_text()

        # The title comes from the syllabus, which owns the week's name; the
        # class page's own <h1> is its own headline and has drifted from it.
        # Falling back to the h1 keeps a page useful before its week is listed.
        week = schedule.get(f"Week {number}", ("", ""))
        title = week[1] or first(r'<h1[^>]*>(.*?)</h1>', t)
        lede = first(r'<p class="lede[^"]*"[^>]*>(.*?)</p>', t)
        if not lede:
            lede = first(r'<p class="lead[^"]*"[^>]*>(.*?)</p>', t)
        if len(lede) > 200:
            lede = lede[:197].rsplit(" ", 1)[0] + "…"

        rows.append(
            {
                "number": number,
                "title": title or f"Class {number}",
                "blurb": lede,
                "href": f"../classes/{folder.name}/",
                "deck": (folder / "slides.html").exists() and bool(list(folder.glob("*.pdf"))),
                "date": week[0],
                "week_title": week[1],
                "image": card_image(folder, number),
                "slides": deck_slide_count(folder),
            }
        )
    return rows


CSS = """
  /* The hub's deck cards, reused: a workshop card shows a photo, the week, what
     the week is about, and one link. That link goes to the workshop's *page*,
     not to the PDF — the deck, the plan, the assignment and the reflection all
     live on the page, and the PDF is one of its links. */
  .deck-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; align-items: stretch; }
  .deck-card { display: grid; grid-template-columns: 40% minmax(0, 1fr);
               border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden;
               background: var(--paper); box-shadow: var(--shadow-sm);
               transition: border-color .2s ease, box-shadow .2s ease; }
  .deck-card:hover { border-color: #cfe1f7; box-shadow: var(--shadow-md); }
  .deck-card img { display: block; width: 100%; height: 100%; min-height: 230px; object-fit: cover; }
  .deck-body { display: flex; flex-direction: column; padding: 22px 24px; }
  .deck-week { font-size: 12px; letter-spacing: 2px; text-transform: uppercase; color: var(--blue-deep);
               font-weight: 700; margin: 0 0 8px; }
  .deck-body h3 { margin: 0 0 8px; font-size: 1.1rem; letter-spacing: -.2px; }
  .deck-body h3 a { color: var(--ink); }
  .deck-body > p { margin: 0 0 14px; color: var(--muted); font-size: 14px; }
  .deck-body .tags { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; list-style: none;
                     padding: 0; margin: 0 0 16px; }
  .deck-body .tags li { font-size: 12.5px; color: var(--muted-2); border: 1px solid var(--line-strong);
                        border-radius: 999px; padding: 4px 11px; background: var(--paper); }
  .deck-body .tags li.pill-cell { border: 0; background: none; padding: 0; }
  .deck-pill { display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .06em;
               text-transform: uppercase; border-radius: 999px; padding: 4px 11px; }
  .deck-pill.ready { color: var(--blue-deep); background: var(--blue-tint); }
  .deck-pill.soon { color: #8a5a00; background: #fff4e0; }
  .deck-body .guide-actions { margin-top: auto; }
  @media (max-width: 900px) {
    .deck-grid { grid-template-columns: 1fr; }
    .deck-card { grid-template-columns: 1fr; }
    .deck-card img { min-height: 210px; aspect-ratio: 16 / 9; }
  }
"""


def page() -> str:
    rows = read_workshops()
    ready = sum(1 for r in rows if r["deck"])
    items = []
    for r in rows:
        label = "Deck ready" if r["deck"] else "Deck coming"
        pill_class = "ready" if r["deck"] else "soon"
        # The kicker already gives the week and its date, so the tags carry
        # only what the kicker does not: the deck's size and its state.
        tags = []
        if r["slides"]:
            tags.append(f'<li>{r["slides"]} slides</li>')
        if not r["deck"]:
            tags.append("<li>Plan only</li>")
        tags.append(f'<li class="pill-cell"><span class="deck-pill {pill_class}">{label}</span></li>')
        items.append(
            f"""<article class="deck-card">
          <img src="{esc(r['image'])}" alt="">
          <div class="deck-body">
            <p class="deck-week">Week {r["number"]}{f" &middot; {esc(r['date'])}" if r["date"] else ""}</p>
            <h3><a href="{esc(r['href'])}">{esc(r["title"])}</a></h3>
            <p>{esc(r["blurb"])}</p>
            <ul class="tags">{''.join(tags)}</ul>
            <div class="guide-actions">
              <a class="btn btn-primary btn-sm" href="{esc(r['href'])}">Open the workshop &rarr;</a>
            </div>
          </div>
        </article>"""
        )

    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Workshops &mdash; ENT-164</title>
<meta name="description" content="Every workshop in ENT-164 Intro to Making: the semester's classes in order, each with its own page, its deck and its assignment.">
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
        <p>In teaching order. Every card opens the workshop's page — the deck, the plan and
        what is due are all there.</p>
      </div>
      <div class="deck-grid">
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
