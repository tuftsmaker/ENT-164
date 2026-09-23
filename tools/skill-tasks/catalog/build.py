#!/usr/bin/env python3
"""Build the public task catalog: tasks/index.html and one page per task.

Generated from the same YAML the checker uses, so the page a student reads and
the check that runs on their file can never drift apart.

    python3 catalog/build.py
    python3 catalog/build.py --check      # fail if the pages are stale (CI)
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "skills" / "maker-tasks" / "check"))

import runner  # noqa: E402
from map import render_svg as task_map_svg  # noqa: E402

sys.path.insert(0, str(REPO / "tools" / "site-nav"))
import nav as site_nav  # noqa: E402

TASKS_DIR = REPO / "tasks"
SITE = "https://tuftsmaker.github.io/ENT-164"

def nav(cta_href="./", cta_label="Start with task 1 &rarr;"):
    """The task pages share the site nav, but each carries its own call to
    action: an open track goes to its first task, a planned one back to the
    tracks, and the catalog to task 1."""
    return site_nav.main_nav(1, cta_href, cta_label, "tasks")

FOOTER = """\
<footer>
  <div class="wrap foot-inner">
    <div class="foot-brand">
      <span>ENT-164 &middot; Intro to Making &mdash; class materials</span>
    </div>
    <div class="foot-links">
      <a href="../">All materials</a>
      <a href="../onshape-tips/">Onshape tips</a>
      <a href="../laser-cutting/">Laser cutting guide</a>
    </div>
  </div>
</footer>
"""

HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} &mdash; ENT-164</title>
<meta name="description" content="{description}">
<link rel="stylesheet" href="../assets/site.css">
<style>
  .criterion {{ border: 1px solid var(--line); border-radius: 12px; background: var(--paper); padding: 14px 16px; }}
  .criterion h4 {{ margin: 0 0 6px; font-size: 14.5px; color: var(--ink); }}
  .criterion p {{ margin: 0; color: var(--muted); font-size: 13.5px; }}
  .criterion .auto {{ display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--blue-deep); background: var(--blue-tint); border-radius: 999px; padding: 2px 9px; margin-bottom: 8px; }}
  .criterion .human {{ color: #8a5a00; background: #fff4e0; }}
  .task-list {{ display: grid; gap: 14px; }}
  .task-row {{ display: grid; grid-template-columns: 46px minmax(0,1fr) auto; gap: 16px; align-items: center; border: 1px solid var(--line); border-radius: 14px; background: var(--paper); padding: 16px 18px; }}
  .task-row:hover {{ border-color: #cfe1f7; background: var(--blue-tint); }}
  .task-row .n {{ font-size: 22px; font-weight: 800; color: var(--blue-deep); text-align: center; }}
  .task-row h3 {{ margin: 0 0 4px; font-size: 1.02rem; }}
  .task-row p {{ margin: 0; color: var(--muted); font-size: 14px; }}
  .task-row .go {{ white-space: nowrap; }}
  .submit-table {{ width: 100%; border-collapse: collapse; font-size: 14.5px; }}
  .submit-table th, .submit-table td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }}
  .submit-table th {{ font-size: 12px; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }}
  .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  .criteria {{ display: grid; gap: 10px; }}
  /* The task map: a generated SVG of the whole qualification. */
  .tm-wrap {{ background: var(--paper-2); border: 1px solid var(--line); border-radius: 18px; padding: 18px 14px; overflow-x: auto; }}
  .tm-svg {{ display: block; width: 100%; height: auto; min-width: 760px; }}
  .tm-svg .tm-node {{ text-decoration: none; }}
  .tm-svg .tm-node rect {{ transition: stroke 0.15s ease, filter 0.15s ease; }}
  .tm-svg .tm-node:hover rect {{ stroke: var(--blue-deep); filter: drop-shadow(0 4px 10px rgba(31,111,208,0.16)); }}
  .tm-svg .tm-node:hover text {{ fill: var(--blue-deep); }}
  .tm-caption {{ max-width: 680px; margin: 16px auto 0; text-align: center; color: var(--muted); font-size: 14.5px; }}
  .tm-empty {{ color: var(--muted); text-align: center; padding: 30px; }}
  /* Tracks: one card per skill. A planned track is dimmed and says so, so the
     page can document what is coming without implying it is available. */
  .track-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr)); gap: 16px; }}
  .track-card {{ position: relative; border: 1px solid var(--line); border-radius: 16px; background: var(--paper); padding: 20px 22px; }}
  .track-card h3 {{ margin: 10px 0 8px; font-size: 1.05rem; }}
  .track-card p {{ margin: 0 0 12px; color: var(--muted); font-size: 14.5px; }}
  .track-card .track-meta {{ font-size: 13px; color: var(--muted); margin-bottom: 14px; }}
  .track-card .track-badge {{ display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; border-radius: 999px; padding: 3px 10px; }}
  .track-card.active .track-badge {{ color: var(--blue-deep); background: var(--blue-tint); }}
  .track-card.active {{ border-color: #cfe1f7; }}
  .track-card.planned {{ background: var(--paper-2); border-style: dashed; }}
  .track-card.planned .track-badge {{ color: #8a5a00; background: #fff4e0; }}
  .track-card.planned h3 {{ color: var(--muted-2); }}
</style>
</head>
<body class="page-class">
"""


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def para(text: str) -> str:
    """A YAML block scalar into paragraphs."""
    blocks = [b.strip() for b in text.strip().split("\n\n")]
    return "\n".join(f"<p>{esc(b)}</p>" for b in blocks if b)


def video_line(task: dict) -> str:
    if not task.get("video"):
        return ""
    poster = task.get("poster")
    poster_attr = f' poster="../{esc(poster)}"' if poster else ""
    length = f" <span class=\"video-len\">({esc(task['time'])})</span>" if task.get("time") else ""
    return f"""\
      <div class="callout video-embed">
        <b>Watch first.</b> {esc(task['title'])}{length}
        <video controls preload="metadata" playsinline{poster_attr}>
          <source src="../{esc(task['video'])}" type="video/mp4">
          Your browser cannot play this video.
          <a href="../{esc(task['video'])}">Download it</a> instead.
        </video>
      </div>"""


def criterion_detail(crit: dict) -> str:
    """A plain-English line for each criterion, so the page explains the check
    rather than naming it."""
    if crit.get("human") or not crit.get("check"):
        return crit.get("review", "A TA looks at this.")
    check = crit.get("check", "")
    if "." in check:
        check = check.split(".", 1)[1]
    args = crit.get("args") or {}
    # A check can be programmatic and still hand the decision to a person —
    # the Onshape link and the self-check both do.
    if check in HUMAN_CHECKS:
        return crit.get("review", "") or MANUAL_TEXT.get(check, "")
    return table_lookup(check, args)


MANUAL_TEXT = {
    "manifest_source_link": "A TA opens your Onshape link to confirm the sketch is yours and committed.",
}

# Checks that report, but leave the decision to a person.
HUMAN_CHECKS = {"manifest_source_link", "human_photo", "human_only", "dxf_text_or_annotations"}


def table_lookup(check: str, args: dict) -> str:
    table = {
        "file_present": "The file is in the submission.",
        "dxf_parses": "The file is readable as a DXF and is not something renamed.",
        "dxf_units_detect": "The size is measured, so a unit mistake cannot hide.",
        "dxf_all_paths_closed": "Every line end meets another line end. A corner that only looks joined would cut open.",
        "dxf_outer_dims": f'Measured overall size: {args.get("width","?")} × {args.get("height","?")} mm.',
        "dxf_bounds_mm": "The part fits inside the laser bed (300 × 600 mm).",
        "dxf_profiles": "The number of closed shapes is what the task asks for.",
        "dxf_circle_count": f'Exactly {args.get("count","?")} hole(s).',
        "dxf_circle_diameter": f'The hole measures {args.get("diameter","?")} mm across.',
        "dxf_circle_position": "The hole sits where the task says, measured from the edges.",
        "dxf_circle_centred": "The hole is at the centre of the outline, not near it.",
        "dxf_min_web": "There is more material around the hole than the laser burns away.",
        "dxf_symmetry": "The two halves are mirror images, measured point by point.",
        "dxf_no_construction_lines": "No stray lines: guides are not exported, so a line in the file gets cut.",
        "dxf_aspect": f'Four straight sides at right angles, in the {args.get("width","?")}:{args.get("height","?")} proportion.',
        "manifest_source_link": "A TA opens your Onshape link to confirm the sketch is yours.",
        "manifest_selfcheck": "You ran the checker on this same file before submitting it.",
        "manifest_field": f'Your manifest records "{args.get("field","")}".',
    }
    return table.get(check, "Checked on your file.")


SUBNav = {
    "catalog": [("map", "The map"), ("tasks", "The tasks"), ("how", "How it works")],
    "unit": [("what", "What it takes"), ("tasks", "The tasks"), ("then", "Supervised cut")],
    "task": [("do", "What to do"), ("hand", "What to hand in"), ("checked", "How it is checked")],
}


def subnav(kind: str) -> str:
    """A page's own sections, under the main nav."""
    links = "\n      ".join(f'<a href="#{sid}">{label}</a>' for sid, label in SUBNav[kind])
    return f"""<nav class="subnav" aria-label="On this page">
  <div class="wrap subnav-inner">
      {links}
  </div>
</nav>"""


def task_page(task: dict, all_tasks: dict) -> str:
    rows = []
    for crit in task["criteria"]:
        check = (crit.get("check") or "").split(".")[-1]
        # A criterion is human if it says so, or if the check itself hands the
        # decision to a person.
        human = bool(crit.get("human")) or not crit.get("check") or check in HUMAN_CHECKS
        badge = "A person checks this" if human else "Checked automatically"
        cls = "human" if human else ""
        detail = criterion_detail(crit) or crit.get("detail") or ""
        rows.append(
            f'<div class="criterion"><span class="auto {cls}">{badge}</span>'
            f'<h4>{esc(crit["title"])}</h4>{f"<p>{esc(detail)}</p>" if detail else ""}</div>'
        )

    submits = "\n".join(
        f'<tr><td class="mono">{esc(item["name"])}</td>'
        f'<td>{"required" if item.get("required") else "optional"}</td>'
        f'<td>{esc(item.get("note",""))}</td></tr>'
        for item in task.get("submit", [])
    )

    prereqs = task.get("prereqs") or []
    prereq_line = ""
    if prereqs:
        links = ", ".join(
            f'<a href="{esc(p)}.html">{esc(all_tasks[p]["title"])}</a>' for p in prereqs if p in all_tasks
        )
        prereq_line = f'<p><b>Do first:</b> {links}.</p>'

    siblings = sorted(
        (t for t in all_tasks.values() if t.get("kind") != "unit"),
        key=lambda t: t.get("order", 99),
    )
    index = [t for t in siblings if t["id"] == task["id"]]
    prev_link = next_link = ""
    if index:
        i = siblings.index(index[0])
        if i > 0:
            prev_link = f'<a class="btn btn-ghost btn-sm" href="{esc(siblings[i-1]["id"])}.html">&larr; {esc(siblings[i-1]["title"])}</a>'
        if i < len(siblings) - 1:
            next_link = f'<a class="btn btn-primary btn-sm" href="{esc(siblings[i+1]["id"])}.html">{esc(siblings[i+1]["title"])} &rarr;</a>'

    return HEAD.format(title=esc(task["title"]), description=esc(task["spec"])) + nav() + f"""
<header class="hero">
  <div class="wrap">
    <p class="kicker reveal">Task {task.get('order','')} &middot; Laser-Ready File</p>
    <h1 class="reveal">{esc(task["title"])}</h1>
    <p class="lead reveal">{esc(task["spec"].strip())}</p>
    <div class="pills reveal">
      <span class="pill">{esc(task.get('time',''))} video</span>
      <span class="pill">One Onshape sketch</span>
      <span class="pill">Signed off by a TA</span>
    </div>
  </div>
</header>

<main>
  {subnav("task")}
  <section id="do">
    <div class="wrap">
{video_line(task)}

      <div class="section-head left"><h2>What to do</h2></div>
      {para(task["goal"])}
      {prereq_line}

      <div class="section-head left" id="hand"><h2>What to hand in</h2></div>
      <table class="submit-table">
        <tr><th>File</th><th></th><th>What it is</th></tr>
        {submits}
      </table>
      <p style="color:var(--muted);font-size:14px;margin-top:12px;">
        Put both files in one folder, run the checker, and upload the zip in Canvas.
        Ask opencode: <span class="mono">check my cad-01 submission</span>.
      </p>

      <div class="section-head left" id="checked"><h2>How it is checked</h2></div>
      <p class="lede">Every criterion below is checked on your file. The ones marked for a person
      are judged by a TA — they are never passed or failed by the checker.</p>
      <div class="criteria">
        {chr(10).join(rows)}
      </div>

      <div class="callout warm" style="margin-top:24px;">
        <b>Passing the checker is not the signoff.</b> It means your file meets the written
        criteria. A TA reads it, checks anything marked for a person, and signs the task — then
        it counts toward the <a href="unit-laser-ready.html">Laser-Ready File</a> qualification.
      </div>

      <div class="cta-row" style="margin-top:24px;">
        {prev_link}
        {next_link}
      </div>
    </div>
  </section>
</main>
{FOOTER}
</body>
</html>
"""


def unit_page(unit: dict, all_tasks: dict) -> str:
    rows = []
    for i, tid in enumerate(unit["tasks"], 1):
        t = all_tasks[tid]
        rows.append(
            f'<div class="task-row"><div class="n">{i}</div>'
            f'<div><h3><a href="{esc(tid)}.html">{esc(t["title"])}</a></h3>'
            f'<p>{esc(t["spec"].strip().replace(chr(10), " "))}</p></div>'
            f'<div class="go"><a class="btn btn-ghost btn-sm" href="{esc(tid)}.html">Open &rarr;</a></div></div>'
        )
    supervised = unit.get("supervised") or {}
    sibling_tasks = sorted(
        (t for t in all_tasks.values() if t.get("kind") != "unit"),
        key=lambda t: t.get("order", 99),
    )
    return HEAD.format(title=esc(unit["title"]), description=esc(unit.get("summary", ""))) + nav() + f"""
<header class="hero">
  <div class="wrap">
    <p class="kicker reveal">Qualification</p>
    <h1 class="reveal">{esc(unit["title"])}</h1>
    <p class="lead reveal">{esc(unit.get("summary","").strip())}</p>
    <div class="pills reveal">
      <span class="pill">{len(unit["tasks"])} tasks</span>
      <span class="pill">{len(unit["tasks"])} DXFs</span>
      <span class="pill">One supervised cut</span>
    </div>
  </div>
</header>

<main>
  {subnav("unit")}
  <section id="what">
    <div class="wrap">
      <div class="section-head">
        <h2>What it takes</h2>
        <p>Every task signed, then one cut with a TA watching. Anything still open shows as
        unfinished on the map below.</p>
      </div>
      <div class="tm-wrap">
        {task_map_svg(sibling_tasks, unit)}
      </div>
      <p class="tm-caption">{esc(unit.get("requirement","").strip().replace(chr(10), " "))}</p>
    </div>
  </section>

  <section id="tasks" style="padding-top:0;">
    <div class="wrap">
      <div class="section-head left"><h2>The tasks</h2></div>
      <div class="task-list">
        {chr(10).join(rows)}
      </div>

      <div class="section-head left" id="then" style="margin-top:40px;"><h2>Then: {esc(supervised.get('title','Supervised cut'))}</h2></div>
      {para(supervised.get("detail",""))}

      <div class="callout warn" style="margin-top:24px;">
        {esc(unit.get("safety","").strip())}
      </div>

      <div class="cta-row" style="margin-top:24px;">
        <a class="btn btn-primary" href="cad-01-first-sketch.html">Start with task 1 &rarr;</a>
        <a class="btn btn-ghost" href="../onshape-tips/">Watch the Onshape tips</a>
      </div>
    </div>
  </section>
</main>
{FOOTER}
</body>
</html>
"""


def catalog_page(tasks: list, unit: dict | None, units: list | None = None) -> str:
    n = len(tasks)
    rows = []
    for t in tasks:
        rows.append(
            f'<div class="task-row"><div class="n">{t.get("order","")}</div>'
            f'<div><h3><a href="{esc(t["id"])}.html">{esc(t["title"])}</a></h3>'
            f'<p>{esc(t["spec"].strip().replace(chr(10), " "))}</p></div>'
            f'<div class="go"><a class="btn btn-ghost btn-sm" href="{esc(t["id"])}.html">Open &rarr;</a></div></div>'
        )
    unit_line = ""
    if unit:
        unit_line = f"""\
      <div class="callout" style="margin-top:26px;">
        <h3 style="margin-top:0;">These {n} tasks are one qualification</h3>
        <p>{esc(unit.get("summary","").strip().replace(chr(10), " "))}</p>
        <div class="cta-row" style="margin-top:14px;">
          <a class="btn btn-primary" href="unit-laser-ready.html">See the qualification &rarr;</a>
        </div>
      </div>"""
    return HEAD.format(
        title="Maker skills tasks",
        description=f"{n} short tasks that take you from a blank Onshape document to a laser-ready DXF, each signed off against written criteria.",
    ) + nav() + f"""
<header class="hero">
  <div class="wrap">
    <p class="kicker reveal">Maker skills tasks</p>
    <h1 class="reveal">Watch it, make it,<br><span class="accent">get it signed off</span></h1>
    <p class="lead reveal">Each task is a short video, one file you make yourself, and written
    criteria your file is checked against. Pass the checks, hand it in, and a TA signs the task
    off. {n} tasks make the Laser-Ready File qualification.</p>
    <div class="pills reveal">
      <span class="pill">{n} tasks</span>
      <span class="pill">Onshape &rarr; DXF</span>
      <span class="pill">Checked on your own machine</span>
      <span class="pill">Signed by a person</span>
    </div>
    <div class="cta-row reveal">
      <a class="btn btn-primary" href="#map">See the map &rarr;</a>
      <a class="btn btn-ghost" href="#tasks">Jump to the task list</a>
    </div>
  </div>
</header>

<main>
  {subnav("catalog")}
  <section id="map">
    <div class="wrap">
      <div class="section-head">
        <h2>The whole thing on one page</h2>
        <p>{n} tasks, each building on the last. Follow the arrows — a task unlocks once the
        ones pointing at it are signed off.</p>
      </div>
      <div class="tm-wrap">
        {task_map_svg(tasks, unit)}
      </div>
      <p class="tm-caption">Every task is one video and one file. The last step is not a file at
      all: you cut one of your own parts at Nolop, with a TA watching. That is what turns {n}
      signed tasks into the qualification.</p>
    </div>
  </section>

  <section id="tasks" style="padding-top:0;">
    <div class="wrap">
      <div class="section-head">
        <h2>The tasks, one by one</h2>
        <p>Same order as the map above, with the full criteria on each task's page.</p>
      </div>
      <div class="task-list">
        {chr(10).join(rows)}
      </div>
{unit_line}
    </div>
  </section>

  <section id="tracks" style="padding-top:0;">
    <div class="wrap">
      <div class="section-head left"><h2>The tracks</h2></div>
      <p class="lede">One track per skill the course teaches. A track is a set of
      tasks; sign each one and the track is yours. You are working on the first
      one now — the others are written down so you can see where the course is
      going.</p>
      <div class="track-grid">
        {chr(10).join(track_card(u, tasks) for u in (units or []))}
      </div>
    </div>
  </section>

  <section id="how" style="padding-top:0;">
    <div class="wrap">
      <div class="section-head left"><h2>How it works</h2></div>
      <div class="cards">
        <div class="card"><span class="num">01</span><h3>Watch</h3>
          <p>Each task has a short video made in Onshape at the class's settings: millimetres, Top plane.</p></div>
        <div class="card"><span class="num">02</span><h3>Make</h3>
          <p>Do it yourself in your own document. Nothing is timed and you can redo it as often as you need.</p></div>
        <div class="card"><span class="num">03</span><h3>Check</h3>
          <p>Ask opencode to check your file before you hand it in — the same criteria the TA uses, run on your laptop.</p></div>
        <div class="card"><span class="num">04</span><h3>Signoff</h3>
          <p>Upload the zip in Canvas. A TA confirms it, signs the task, and it counts toward the qualification.</p></div>
      </div>

      <div class="callout warm" style="margin-top:24px;">
        <b>What a signoff does and does not mean.</b> A signed task means your <i>file</i> is
        right. Using the laser itself needs Nolop's own in-person training and checkout — that
        is separate on purpose, and it stays that way.
      </div>
    </div>
  </section>
</main>
{FOOTER}
</body>
</html>
"""


def planned_unit_page(unit: dict) -> str:
    """A track that is documented but not built. Shown dimmed, with no tasks to
    click: the point is that students and the instructor can see what is coming
    and why, not that they can start it."""
    planned = unit.get("planned_tasks") or []
    rows = []
    for item in planned:
        rows.append(
            f'<div class="criterion"><span class="auto human">Planned</span>'
            f'<h4>{esc(item.get("title",""))}</h4>'
            f'<p>{esc(item.get("video",""))}</p>'
            f'<p><b>Evidence:</b> {esc(item.get("evidence",""))}</p>'
            f'<p><b>Would check:</b> {esc(item.get("checks",""))}</p></div>'
        )
    needs = unit.get("needs", "").strip()
    supervised = unit.get("supervised") or {}
    return HEAD.format(
        title=esc(unit["title"]),
        description=esc(unit.get("summary", "").strip().replace("\n", " ")),
    ) + nav("./", "All tracks &rarr;") + f"""
<header class="hero">
  <div class="wrap">
    <p class="kicker reveal">Track &middot; planned</p>
    <h1 class="reveal">{esc(unit["title"])}</h1>
    <p class="lead reveal">{esc(unit.get("summary","").strip())}</p>
    <div class="pills reveal">
      <span class="pill">Not available yet</span>
      <span class="pill">{len(planned)} tasks planned</span>
      <span class="pill">Signed off by a TA</span>
    </div>
  </div>
</header>

<main>
  <section>
    <div class="wrap">
      <div class="callout warn">
        <b>This track is not open yet.</b> The tasks below are what it will
        contain, written down so the shape of it is clear. The videos have not
        been recorded and the checks have not been built, so nothing here can be
        submitted or signed off.
      </div>

      <div class="section-head left"><h2>Why this track</h2></div>
      {para(unit.get("why",""))}

      <div class="section-head left"><h2>What it will contain</h2></div>
      <div class="criteria">
        {chr(10).join(rows)}
      </div>

      <div class="section-head left" style="margin-top:40px;"><h2>Then: {esc(supervised.get('title','Supervised step'))}</h2></div>
      {para(supervised.get("detail",""))}

      <div class="section-head left" style="margin-top:40px;"><h2>What it needs first</h2></div>
      {para(needs)}

      <div class="cta-row" style="margin-top:24px;">
        <a class="btn btn-ghost" href="index.html">&larr; All tracks</a>
      </div>
    </div>
  </section>
</main>
{FOOTER}
</body>
</html>
"""


def track_card(unit: dict, tasks: list) -> str:
    """One track on the catalog page. Active tracks link through; planned ones
    are dimmed and say so."""
    planned = unit.get("status") == "planned"
    n = len(unit.get("planned_tasks") or []) if planned else len(
        [t for t in tasks if t.get("unit") == unit["id"]]
    )
    label = "In development" if planned else "Open"
    badge = "planned" if planned else "active"
    body = esc(unit.get("summary", "").strip().replace("\n", " "))
    if planned:
        return f"""<article class="track-card {badge}">
          <span class="track-badge">{label}</span>
          <h3>{esc(unit["title"])}</h3>
          <p>{body}</p>
          <p class="track-meta">{n} tasks planned &middot; not yet available</p>
          <a class="btn btn-ghost btn-sm" href="{esc(unit['id'])}.html">See the plan &rarr;</a>
        </article>"""
    return f"""<article class="track-card {badge}">
          <span class="track-badge">{label}</span>
          <h3>{esc(unit["title"])}</h3>
          <p>{body}</p>
          <p class="track-meta">{n} tasks &middot; signed off one at a time</p>
          <a class="btn btn-primary btn-sm" href="{esc(unit['id'])}.html">Open the track &rarr;</a>
        </article>"""


def build(check_only=False) -> int:
    tasks = {}
    units = []
    for t in runner.list_tasks():
        if t.get("kind") == "unit":
            units.append(t)
        else:
            tasks[t["id"]] = t

    units.sort(key=lambda u: u.get("order", 99))
    active = next((u for u in units if u.get("status") != "planned"), None)

    ordered = sorted(tasks.values(), key=lambda t: t.get("order", 99))
    pages = {"index.html": catalog_page(ordered, active, units)}
    for t in ordered:
        pages[f"{t['id']}.html"] = task_page(t, tasks)
    for unit in units:
        if unit.get("status") == "planned":
            pages[f"{unit['id']}.html"] = planned_unit_page(unit)
        else:
            pages[f"{unit['id']}.html"] = unit_page(unit, tasks)

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    stale = []
    for name, content in pages.items():
        path = TASKS_DIR / name
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        if check_only:
            stale.append(name)
            continue
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(REPO)}")

    if check_only:
        if stale:
            print("stale pages (run catalog/build.py):")
            for name in stale:
                print(f"  tasks/{name}")
            return 1
        print(f"catalog is up to date ({len(pages)} pages)")
        return 0

    print(f"\n{len(pages)} pages in {TASKS_DIR.relative_to(REPO)}/")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="build")
    parser.add_argument("--check", action="store_true", help="fail if the pages are stale")
    args = parser.parse_args()
    try:
        rc = build(check_only=args.check)
    except runner.MissingDependency as exc:
        # Never report "up to date" over a catalog that could not be read.
        print(f"error: {exc}", file=sys.stderr)
        rc = 2
    raise SystemExit(rc)
