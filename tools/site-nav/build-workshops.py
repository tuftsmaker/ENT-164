#!/usr/bin/env python3
"""Build the workshops landing page and the homepage's workshop cards.

`workshops/index.html` is generated, not hand-written, for the same reason the
task catalog is: it is a list of facts that already exist elsewhere (each week's
title and date from the syllabus, whether a deck exists, what the week is
about), and a hand-maintained copy drifts the moment a class is added or a deck
lands.

The homepage's workshop grid is generated from the same list, for the same
reason: the two pages show the same workshops, so they must show the same
titles, blurbs and photos. `index.html` carries a pair of markers around its
grid; this script rewrites everything between them.

The syllabus remains the source of truth for a week's name and date; the class
pages remain the source of truth for what a workshop contains (its deck).

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
HOME = REPO / "index.html"
HOME_START = "<!-- workshops:start -->"
HOME_END = "<!-- workshops:end -->"


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


# What each workshop's card says. One entry per week, so the homepage and the
# workshops page show the same photo, the same sentence and the same alt text.
# The copy is written for the card rather than pulled from the class page,
# because a class page's first lede is often written for the page's own layout
# ("By the end of this course, you will be able to:") and reads as a fragment
# out of context.
CARDS = {
    1: {
        "image": "assets/photos/class/class-01-presenting.jpg",
        "alt": "The instructor introducing the course to students gathered in the Nolop makerspace",
        "blurb": "Welcome to Intro to Making: what you'll learn this semester, how class "
                 "works, the grading rubric, your tools and maker kit, and an introduction "
                 "to the Nolop makerspace.",
    },
    2: {
        "image": "classes/class-02/shots/foam-core-samples.jpg",
        "alt": "Three folded foam-core mockups standing on a cutting mat",
        "blurb": "The robot challenge rules and scoring, your team and kit, foam-core "
                 "mockups, and the clay-to-3D scanning workflow.",
    },
    3: {
        "image": "assets/photos/class/laser-cut-projects.jpg",
        "alt": "A table of student-built laser-cut enclosures and boxes",
        "blurb": "From sketch to cut part: read your drawings, pull numbers from "
                 "datasheets, model in Onshape, and cut at Nolop.",
    },
    4: {
        "image": "assets/photos/class/printed-medallion.jpg",
        "alt": "A 3D-printed blue Tufts medallion",
        "blurb": "From model to machine: how a 3D printer works, filament choices, "
                 "exporting from Onshape, slicing in PrusaSlicer, and printing at Nolop.",
    },
    5: {
        "image": "classes/class-05/shots/lab-test-rig.jpg",
        "alt": "A breadboard wired to motors, a servo, and an ESP32 on the bench",
        "blurb": "Wire motors, servos, and sensors on the breadboard, install MicroPython "
                 "on the ESP32, and write your first AI-assisted code.",
    },
    6: {
        "image": "classes/class-06/shots/phone-rgb-control.jpg",
        "alt": "A phone screen showing an RGB LED control page",
        "blurb": "Direct an AI coding agent: give your ESP32 a web page with Wi-Fi setup, "
                 "the client/server model, a smart RGB light, and Tufts device registration.",
    },
    7: {
        "image": "assets/photos/class/robot-internals.jpg",
        "alt": "The inside of a team robot showing a servo, a battery pack, and wiring",
        "blurb": "A full working session at Nolop: integrate everything into one working "
                 "robot, then debug, test, and iterate with your team.",
    },
    8: {
        "image": "assets/photos/class/band-robot-challenge.jpg",
        "alt": "A student-built robot on the challenge course, with hands adjusting it",
        "blurb": "Put your robot to the test: teams race on the course, scores go on the "
                 "board, and the awards close out the first module.",
    },
    9: {
        "image": "assets/photos/class/class-09-demo-1.jpg",
        "alt": "A team presenting their project to the class",
        "blurb": "Robot Challenge awards, the five-week final project arc, what your build "
                 "must include, and the 5-minute concept pitch.",
    },
    10: {
        "image": "assets/photos/class/device-item-added.jpg",
        "alt": "A tablet showing live sensor readings, including the weather",
        "blurb": "Collect data from the physical world with sensors, then present it in a "
                 "real-time visualization someone can read at a glance.",
    },
    11: {
        "image": "classes/class-11/shots/poetic-typewriter.jpg",
        "alt": "An illustration of the poetic typewriter with glowing butterflies",
        "blurb": "A voice-driven poetic light built with an ESP32, cloud APIs, and Claude "
                 "— plus how humans and AI divide the work.",
    },
    12: {
        "image": "assets/photos/class/makerspace.jpg",
        "alt": "Students working at tables in the Nolop makerspace",
        "blurb": "Dedicated workshop time at Nolop: finish the build, make it reliable, and "
                 "rehearse the demo before the showcase.",
    },
    13: {
        "image": "assets/photos/class/student-builds.jpg",
        "alt": "Three students holding the robots and models they built in class",
        "blurb": "Demo Day: every team presents a finished product to the Tufts community, "
                 "and the course closes with a final reflection.",
    },
}


def card_image(folder: Path) -> str:
    """A fallback photo for a week with no entry in CARDS: the class page's
    first content image. A card should show the week's *activity* — a person
    doing the thing — rather than a product shot or a diagram, because the
    cards are read as a set and the sterile ones stand out against the rest."""
    for src in re.findall(r'<img[^>]*src="([^"]+)"', (folder / "index.html").read_text()):
        if any(x in src for x in ("icon", "logo", ".svg")):
            continue
        rel = (folder / src).resolve()
        if rel.is_file() and ("assets/photos" in str(rel) or "shots" in str(rel)):
            return str(rel.relative_to(REPO))
    return "assets/photos/class/makerspace.jpg"


def deck_slide_count(folder: Path):
    """How many slides a deck has, from slides.html. None when there is no deck."""
    slides = folder / "slides.html"
    if not slides.exists():
        return None
    n = len(re.findall(r'<section class="slide', slides.read_text(errors="replace")))
    return n or None


def read_workshops() -> list:
    """Every teaching week, as one row of card data.

    The weeks come from the syllabus, so a week with no class page yet (Week 7)
    still appears; its card points at the syllabus week instead of a missing
    page.
    """
    schedule = read_schedule()
    rows = []
    for number, (date, title) in sorted(
        (int(k.split()[1]), v) for k, v in schedule.items() if k.startswith("Week ")
    ):
        folder = REPO / "classes" / f"class-{number:02d}"
        has_page = (folder / "index.html").exists()
        page = (folder / "index.html").read_text() if has_page else ""
        deck = has_page and (folder / "slides.html").exists() and bool(list(folder.glob("*.pdf")))

        card = CARDS.get(number, {})
        blurb = card.get("blurb") or first(r'<p class="lede[^"]*"[^>]*>(.*?)</p>', page)
        if not blurb:
            blurb = first(r'<p class="lead[^"]*"[^>]*>(.*?)</p>', page)
        if len(blurb) > 200:
            blurb = blurb[:197].rsplit(" ", 1)[0] + "…"

        rows.append(
            {
                "number": number,
                "title": title or f"Class {number}",
                "blurb": blurb,
                "date": date,
                "page": has_page,
                "path": f"classes/class-{number:02d}/" if has_page else "syllabus/#schedule",
                "cta": "Open the Workshop" if has_page else "See the syllabus week",
                "deck": deck,
                "slides": deck_slide_count(folder) if has_page else None,
                "image": card.get("image") or (card_image(folder) if has_page else ""),
                "alt": card.get("alt", ""),
            }
        )
    return rows


def card(r: dict, depth: int = 0, delay: float | None = None) -> str:
    """One workshop card, as it appears on both pages.

    `depth` is the page's distance from the site root; `delay` is the homepage's
    staggered reveal, which the workshops page does not use.
    """
    root = "../" * depth
    href = root + r["path"]
    classes = "deck-card reveal" if delay is not None else "deck-card"
    style = f' style="--d:{delay:.2f}s"' if delay is not None else ""

    tags = []
    if r["slides"]:
        tags.append(f'<li>{r["slides"]} slides</li>')
    elif not r["page"]:
        tags.append("<li>Working session</li>")
    else:
        tags.append("<li>Plan only</li>")
    if r["deck"]:
        tags.append('<li class="pill-cell"><span class="deck-pill ready">Deck ready</span></li>')
    elif r["page"]:
        tags.append('<li class="pill-cell"><span class="deck-pill soon">Deck coming</span></li>')

    kicker = f"Week {r['number']}" + (f" &middot; {esc(r['date'])}" if r["date"] else "")
    return f"""        <article class="{classes}"{style}>
          <img src="{esc(root + r['image'])}" alt="{esc(r['alt'])}">
          <div class="deck-body">
            <p class="deck-week">{kicker}</p>
            <h3><a href="{esc(href)}">{esc(r['title'])}</a></h3>
            <p>{esc(r['blurb'])}</p>
            <ul class="tags">{''.join(tags)}</ul>
            <div class="guide-actions">
              <a class="btn btn-primary btn-sm" href="{esc(href)}">{esc(r['cta'])} &rarr;</a>
            </div>
          </div>
        </article>"""


def home_grid() -> str:
    """The homepage's workshop grid, between its markers."""
    items = [card(r, 0, delay=0.04 + 0.02 * i) for i, r in enumerate(read_workshops())]
    return (
        HOME_START
        + '\n      <div class="deck-grid">\n'
        + "\n".join(items)
        + "\n      </div>\n      "
        + HOME_END
    )


def page() -> str:
    rows = read_workshops()
    ready = sum(1 for r in rows if r["deck"])
    grid = "\n".join(card(r, 1) for r in rows)

    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Workshops &mdash; ENT-164</title>
<meta name="description" content="Every workshop in ENT-164 Intro to Making: the semester's weeks in order, each with its page, its deck and its assignments.">
<link rel="stylesheet" href="../assets/site.css">
</head>
<body class="page-class">
"""
    return head + site_nav.main_nav(1, "../syllabus/", "Course syllabus &rarr;") + f"""
<header class="hero">
  <div class="wrap">
    <p class="kicker reveal">Workshops</p>
    <h1 class="reveal">Thirteen weeks,<br><span class="accent">one workshop at a time</span></h1>
    <p class="lead reveal">The semester, week by week — what each workshop covers, what you
    make, and what is due. Open a card for the week's page, and take the PDF to class where
    the deck is ready.</p>
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
        <p>In teaching order. Each card opens the workshop's page — the deck, the plan and
        what is due are all there — except Week 7, which is a full build session at Nolop.</p>
      </div>
      <div class="deck-grid">
{grid}
      </div>
    </div>
  </section>

  <section style="padding-top:0;">
    <div class="wrap">
      <div class="callout warm">
        <b>How a workshop runs.</b> We meet in the JCC classroom for a short introduction
        to the skill, then move to Nolop where the work is hands-on. The
        <a href="../syllabus/">syllabus</a> has the learning outcomes, grading and
        policies; the <a href="../tasks/">maker skills tasks</a> are where you get each
        skill signed off.
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


def replace_region(text: str, start: str, end: str, new: str) -> str:
    """Swap everything between two markers, keeping the markers themselves."""
    if start not in text or end not in text:
        raise SystemExit(f"{HOME.name} is missing its {start} / {end} markers")
    pre, rest = text.split(start, 1)
    _, post = rest.split(end, 1)
    return pre + new + post


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="build-workshops")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    content = page()
    home_before = HOME.read_text()
    home_after = replace_region(home_before, HOME_START, HOME_END, home_grid())

    stale = []
    if not OUT.exists() or OUT.read_text(encoding="utf-8") != content:
        stale.append(f"{OUT.relative_to(REPO)}")
    if home_after != home_before:
        stale.append(f"{HOME.relative_to(REPO)} (workshop grid)")

    if not stale:
        print("workshops pages are up to date")
        return 0
    if args.check:
        print("stale: run tools/site-nav/build-workshops.py — " + ", ".join(stale))
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    HOME.write_text(home_after, encoding="utf-8")
    rows = read_workshops()
    print(f"wrote {OUT.relative_to(REPO)} and the homepage grid — {len(rows)} workshops, "
          f"{sum(1 for r in rows if r['deck'])} with a deck")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
