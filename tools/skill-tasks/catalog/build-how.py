#!/usr/bin/env python3
"""Build `tasks/how-tasks-work.html` — the detail behind the short block on the
task catalog.

The catalog page explains tracks and lists tasks; the mechanics of a single task
(who signs it, what the checker can and cannot see, what a signoff means) are
long enough that they were crowding it. They live here instead.

    python3 tools/skill-tasks/catalog/build-how.py
    python3 tools/skill-tasks/catalog/build-how.py --check
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
OUT = REPO / "tasks" / "how-tasks-work.html"

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "site-nav"))

import nav as site_nav  # noqa: E402


def esc(text) -> str:
    return html.escape(str(text), quote=True)


HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>How tasks work &mdash; ENT-164</title>
<meta name="description" content="How a maker skills task works: the video, the file you make, the checker that runs on your own machine, and the signoff that completes it.">
<link rel="stylesheet" href="../assets/site.css">
<style>
  .steprow { display: grid; grid-template-columns: 46px minmax(0,1fr); gap: 18px; align-items: start;
             border: 1px solid var(--line); border-radius: 14px; background: var(--paper); padding: 18px 20px; }
  .steprow + .steprow { margin-top: 12px; }
  .steprow .n { font-size: 22px; font-weight: 800; color: var(--blue-deep); text-align: center; }
  .steprow h3 { margin: 0 0 6px; font-size: 1.02rem; }
  .steprow p { margin: 0; color: var(--muted); font-size: 14.5px; }
  .steprow code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
                  font-size: 13px; background: var(--paper-2); border: 1px solid var(--line);
                  border-radius: 6px; padding: 1px 6px; }
  .mean-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%,280px),1fr)); gap: 16px; }
  .mean-grid .card h3 { margin-top: 0; }
</style>
</head>
<body class="page-class">
"""


def page() -> str:
    return HEAD + site_nav.main_nav(1, "./", "Back to the tasks &rarr;", "tasks") + """
<header class="hero">
  <div class="wrap">
    <p class="kicker reveal">Maker skills tasks</p>
    <h1 class="reveal">How a task <span class="accent">works</span></h1>
    <p class="lead reveal">Every task is the same four steps, whether it is a laser file, a
    3D print, a circuit or a connected device. The shape does not change; only the thing you
    make does.</p>
  </div>
</header>

<main>
  <section id="steps">
    <div class="wrap">
      <div class="section-head left"><h2>The four steps</h2></div>

      <div class="steprow">
        <div class="n">1</div>
        <div>
          <h3>Watch the task video</h3>
          <p>Each task opens with a short video recorded in the tool the class uses — Onshape
          at millimetres and the Top plane, the breadboard on its extension board, the class's
          slicer settings. It is the same demonstration you get in class, short enough to
          rewatch while you work.</p>
        </div>
      </div>

      <div class="steprow">
        <div class="n">2</div>
        <div>
          <h3>Make it yourself</h3>
          <p>Do it in your own document, on your own bench. Nothing is timed and you can redo
          it as often as you need — the task is signed when the work meets the criteria, not
          when you first attempt it.</p>
        </div>
      </div>

      <div class="steprow">
        <div class="n">3</div>
        <div>
          <h3>Check it before you hand it in</h3>
          <p>Ask opencode to check your file. It runs the same checks a TA will, on your
          machine, and tells you what to fix in the tool you are working in. A task's page
          lists every criterion, so there is nothing hidden.</p>
        </div>
      </div>

      <div class="steprow">
        <div class="n">4</div>
        <div>
          <h3>Hand it in, and a person signs it off</h3>
          <p>Upload the zip in Canvas. A TA reviews the report, checks anything that needs
          eyes — your link, a photo, the part in your hand — and signs the task. Then it counts
          toward the track.</p>
        </div>
      </div>
    </div>
  </section>

  <section id="signoff" style="padding-top:0;">
    <div class="wrap">
      <div class="section-head left"><h2>What a signoff means — and does not</h2></div>
      <div class="mean-grid">
        <div class="card accent">
          <h3>It does mean</h3>
          <ul>
            <li>Your work meets every written criterion for the task.</li>
            <li>A person looked at it, not only a program.</li>
            <li>It counts toward that track.</li>
          </ul>
        </div>
        <div class="card">
          <h3>It does not mean</h3>
          <ul>
            <li>That you may run the machine. The laser, the printers and the soldering iron
                each need Nolop's own in-person training and checkout.</li>
            <li>That the file is perfect — it means it is right for this task.</li>
            <li>That you cannot resubmit. Fix it and hand it in again.</li>
          </ul>
        </div>
      </div>

      <div class="callout warm" style="margin-top:24px;">
        <b>Why the machine is separate.</b> A file can be checked by software; whether you can
        safely operate a laser is a judgement about you, made in person. Keeping the two apart
        is deliberate, and it is the same split an emergency-services task book uses.
      </div>
    </div>
  </section>

  <section id="checker" style="padding-top:0;">
    <div class="wrap">
      <div class="section-head left"><h2>What the checker can see</h2></div>
      <p class="lede">Worth knowing, so a green report means what you think it does.</p>
      <div class="cards">
        <div class="card">
          <h3>It reads the file</h3>
          <p>Geometry, units, sizes, thicknesses, closure, watertightness, pin choices,
          whether code compiles. Anything a program can decide, it decides.</p>
        </div>
        <div class="card">
          <h3>It cannot see you</h3>
          <p>It cannot prove the work is yours, or that a physical part exists. That is what
          your Onshape link, a photo, and the supervised step are for.</p>
        </div>
        <div class="card">
          <h3>It never signs off</h3>
          <p>A pass means the file meets the criteria. The signoff is always a person's
          decision — there is no automatic grading in this system.</p>
        </div>
      </div>
    </div>
  </section>

  <section id="tracks" style="padding-top:0;">
    <div class="wrap">
      <div class="section-head left"><h2>Tracks</h2></div>
      <p class="lede">Tasks belong to a track, one per skill the course teaches. Finish every
      task in a track and the track is yours. <b>Laser-Ready File</b> is open now; Print-Ready
      Model, Working Circuit and Connected Device are written down and in development.</p>
      <div class="cta-row">
        <a class="btn btn-primary" href="index.html#tracks">See the tracks &rarr;</a>
        <a class="btn btn-ghost" href="index.html#tasks">The task list</a>
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
      <a href="index.html">Maker skills tasks</a>
    </div>
  </div>
</footer>

</body>
</html>
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="build-how")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    content = page()
    if OUT.exists() and OUT.read_text(encoding="utf-8") == content:
        print("how-tasks-work page is up to date")
        return 0
    if args.check:
        print("stale: run tools/skill-tasks/catalog/build-how.py")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
