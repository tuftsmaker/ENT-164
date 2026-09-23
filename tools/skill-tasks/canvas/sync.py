#!/usr/bin/env python3
"""Create or update the Canvas assignments, rubric and module for the tasks.

Idempotent: run it as often as you like. It finds assignments by name, creates
what is missing, and updates descriptions to match the task files. Nothing is
published unless you pass --publish, and no student ever sees an assignment
that is unpublished.

    python3 canvas/sync.py --dry-run         # show what it would do
    python3 canvas/sync.py                   # create, leave unpublished
    python3 canvas/sync.py --publish         # make them visible to students
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent.parent / "skills" / "maker-tasks" / "check"))

import runner  # noqa: E402
from canvas_client import (  # noqa: E402
    CanvasError,
    Client,
    GROUP_NAME,
    GROUP_WEIGHT,
    MODULE_NAME,
    load_config,
)

SITE = "https://tuftsmaker.github.io/ENT-164"


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
    parser.add_argument("--task", help="only this task id")
    args = parser.parse_args(argv)

    try:
        client = Client(**load_config())
    except CanvasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    tasks = [t for t in runner.list_tasks() if t.get("kind") != "unit"]
    if args.task:
        tasks = [t for t in tasks if t["id"] == args.task]
    tasks.sort(key=lambda t: t.get("order", 99))

    try:
        group = client.ensure_group()
        module = client.ensure_module()
        print(f"group  {group['id']}  {group['name']} (weight {group.get('group_weight')})")
        print(f"module {module['id']}  {module['name']}")
        for task in tasks:
            name = assignment_name(task)
            existing = client.find_assignment(name)
            action = "update" if existing else "create"
            print(f"\n{action}: {name}")
            print(f"   video: {task['video']}")
            if args.dry_run:
                print(f"   would set {len(rubric_rows(task))} rubric rows")
                print("   would add to the module" if not existing else "   already in the module, if linked")
                continue

            if existing:
                client.update_assignment(
                    existing["id"],
                    description=description(task, task["order"]),
                    points_possible=0.0,
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

            items = client.module_items(module["id"])
            already = [i for i in items if i.get("title") == name]
            if already:
                print(f"   module item {already[0]['id']} already present")
            else:
                item = client.add_module_item(
                    module["id"],
                    title=name,
                    type="Assignment",
                    content_id=assignment["id"],
                )
                print(f"   module item {item['id']} added")
    except CanvasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print()
    print("published" if args.publish else "assignments are UNPUBLISHED (students cannot see them yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
