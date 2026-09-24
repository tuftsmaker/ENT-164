#!/usr/bin/env python3
"""Create or update the Canvas assignments and their rubrics for the tasks.

Idempotent: run it as often as you like. It finds assignments by name, creates
what is missing, and updates descriptions to match the task files. The
assignment category is the open track's: it is named after the unit's title in
the task files, and existing assignments are moved into it. Nothing is
published unless you pass --publish, and no student ever sees an assignment
that is unpublished.

    python3 canvas/sync.py --dry-run         # show what it would do
    python3 canvas/sync.py                   # create, leave unpublished
    python3 canvas/sync.py --publish         # make them visible to students
    python3 canvas/sync.py --publish --write-map   # live only: task -> URL map
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent.parent / "skills" / "maker-tasks" / "check"))

import runner  # noqa: E402
from canvas_client import (  # noqa: E402
    CanvasError,
    Client,
    GROUP_WEIGHT,
    LIVE_COURSE,
    load_config,
)

SITE = "https://tuftsmaker.github.io/ENT-164"
# The task -> assignment URLs the public pages link to. Written only for the
# live course, so the committed map can never point at the prototype.
MAP_PATH = HERE / "assignments.json"


def assignment_name(task: dict) -> str:
    return f"{task['id']} · {task['title']}"


def description(task: dict, order: int) -> str:
    video = f"{SITE}/{task['video']}"
    lines = [
        f"<p><b>Task {order}</b> of the <b>Laser-Ready File</b> qualification.</p>",
        f"<p><b>Do this:</b> {task['goal'].strip()}</p>",
        f"<p><b>The spec:</b> {task['spec'].strip()}</p>",
        f'<p>Watch the video first: <a href="{video}">{task["title"]}</a> '
        f'(<a href="{SITE}/tasks/{task["id"]}.html">full task page</a>).</p>',
        "<p><b>Hand in:</b></p><ul>",
    ]
    for item in task.get("submit", []):
        required = " (required)" if item.get("required") else ""
        lines.append(f"<li><code>{item['name']}</code>{required} — {item.get('note','')}</li>")
    lines.append("</ul>")
    if any("manifest_source_link" in (crit.get("check") or "")
           for crit in task.get("criteria", [])):
        lines.append(
            "<p><b>Your Onshape link.</b> Paste it in the comment box when you upload — "
            "the checker reads it even if it is not in <code>manifest.md</code>.</p>"
        )
    lines += [
        "<p><b>Check it before you upload.</b> In opencode, ask the "
        "<code>maker-tasks</code> skill to check your file. Fix anything it marks "
        "<code>[FIX]</code>, then upload the zip it builds.</p>",
        "<p>Criteria and the checker: "
        f'<a href="{SITE}/tasks/{task["id"]}.html">the task page</a>.</p>',
        "<p><i>This task is signed off by a person. Passing the file checks means the "
        "file is ready; a TA confirms and signs the task.</i></p>",
    ]
    if task["id"] == "cad-01-first-sketch":
        lines.append(
            "<p><b>New here?</b> Start with the "
            f'<a href="{SITE}/onshape-tips/">Onshape tips</a> — nine short videos.</p>'
        )
    return "\n".join(lines)


def rubric_rows(task: dict) -> list:
    """One rubric row per program-checkable criterion, plus one for the human
    judgement. The rubric is the record of what was checked."""
    rows = []
    for crit in task.get("criteria", []):
        human = crit.get("human") or not crit.get("check")
        rows.append(
            {
                "description": crit["title"],
                "points": 0,
                "long_description": (
                    "A person confirms this." if human else f"Checked automatically: {crit.get('check')}"
                ),
            }
        )
    rows.append(
        {
            "description": "TA signoff",
            "points": 0,
            "long_description": "Signed by a TA or instructor. This is the signoff that completes the task.",
        }
    )
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sync")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--publish", action="store_true", help="make assignments visible to students")
    parser.add_argument("--write-map", action="store_true",
                        help="record task -> assignment URLs for the site (live course only)")
    parser.add_argument("--task", help="only this task id")
    parser.add_argument("--course",
                        help="Canvas course id; defaults to the prototype. "
                             "The live course needs CANVAS_ALLOW_LIVE=1 as well.")
    args = parser.parse_args(argv)

    try:
        config = load_config()
        if args.course:
            config["course_id"] = str(args.course)
        client = Client(**config)
    except CanvasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.write_map:
        if args.dry_run:
            print("error: --write-map needs a real run — assignment ids only exist in Canvas",
                  file=sys.stderr)
            return 2
        if str(client.course_id) != LIVE_COURSE:
            print(f"error: the pages link to the live course; run --course {LIVE_COURSE} "
                  f"with CANVAS_ALLOW_LIVE=1 to write the map", file=sys.stderr)
            return 2
        if not args.publish:
            print("error: --write-map without --publish would link students to hidden "
                  "assignments", file=sys.stderr)
            return 2
        if args.task:
            print("error: --write-map rewrites the whole map; run it without --task",
                  file=sys.stderr)
            return 2

    items = runner.list_tasks()
    open_tracks = [t for t in items
                   if t.get("kind") == "unit" and t.get("status", "active") != "planned"]
    if len(open_tracks) != 1:
        found = ", ".join(t["id"] for t in open_tracks) or "none"
        print(f"error: the Canvas category is named after the open track, so exactly "
              f"one track must be open; found {len(open_tracks)}: {found}",
              file=sys.stderr)
        return 2
    group_name = open_tracks[0]["title"]

    tasks = [t for t in items if t.get("kind") != "unit"]
    if args.task:
        tasks = [t for t in tasks if t["id"] == args.task]
    tasks.sort(key=lambda t: t.get("order", 99))

    entries = {}
    try:
        if args.dry_run:
            # Look, do not touch: ensure_group creates on the way, so
            # calling them here made --dry-run write to Canvas.
            group = next((g for g in client.assignment_groups()
                          if g["name"] == group_name), None)
            print(f"category  {group['id'] if group else '(would create)'}  {group_name} "
                  f"(weight {GROUP_WEIGHT})")
        else:
            group = client.ensure_group(name=group_name)
            print(f"category  {group['id']}  {group['name']} (weight {group.get('group_weight')})")
        for task in tasks:
            name = assignment_name(task)
            existing = client.find_assignment(name)
            action = "update" if existing else "create"
            print(f"\n{action}: {name}")
            print(f"   video: {task['video']}")
            if args.dry_run:
                print(f"   would set {len(rubric_rows(task))} rubric rows")
                continue

            if existing:
                # The category is the track's: an assignment that predates the
                # current name is moved into the right group.
                client.update_assignment(
                    existing["id"],
                    description=description(task, task["order"]),
                    points_possible=0.0,
                    assignment_group_id=group["id"],
                    published="true" if args.publish else "false",
                )
                assignment = existing
            else:
                assignment = client.create_assignment(
                    name,
                    description(task, task["order"]),
                    points=0.0,
                    group_id=group["id"],
                    published=args.publish,
                )
            print(f"   assignment {assignment['id']}")

            rows = rubric_rows(task)
            client.create_rubric(assignment["id"], rows)
            print(f"   rubric: {len(rows)} rows")
            entries[task["id"]] = {"id": assignment["id"], "name": name}
    except CanvasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.write_map:
        base = f"{client.base}/courses/{client.course_id}"
        data = {
            "course_id": str(client.course_id),
            "course_url": f"{base}/assignments",
            "assignments": {
                tid: {**entry, "url": f"{base}/assignments/{entry['id']}"}
                for tid, entry in entries.items()
            },
        }
        MAP_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {MAP_PATH}")
        print("Next: rebuild the catalog — python3 tools/skill-tasks/catalog/build.py")

    print()
    print("published" if args.publish else "assignments are UNPUBLISHED (students cannot see them yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
