#!/usr/bin/env python3
"""Pull ungraded submissions for one task and check them.

Downloads each student's upload into a working directory (outside the repo),
runs the checks, and writes one report per student. Nothing is posted back to
Canvas — that is `apply.py`, and only after a person has read the reports.

    python3 canvas/pull.py --task cad-01-first-sketch
    python3 canvas/pull.py --task cad-03-cut-a-hole --workdir ~/ent164/grading
    python3 canvas/pull.py --task cad-01-first-sketch --student "Jane Doe"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent.parent / "skills" / "maker-tasks" / "check"))

import runner  # noqa: E402
from canvas_client import CanvasError, Client, load_config  # noqa: E402

DEFAULT_WORKDIR = Path.home() / "ent164" / "grading"


def safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-").lower() or "unknown"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="pull")
    parser.add_argument("--task", "-t", required=True)
    parser.add_argument("--workdir", default=str(DEFAULT_WORKDIR))
    parser.add_argument("--student", help="only this student's submission")
    parser.add_argument("--all", action="store_true", help="include already-graded submissions")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        task = runner.load_task(args.task)
    except runner.TaskError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if task.get("kind") == "unit":
        print("error: units are signed off from the task reports, not pulled", file=sys.stderr)
        return 2

    try:
        client = Client(**load_config())
    except CanvasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    assignment_name = f"{task['id']} · {task['title']}"
    assignment = client.find_assignment(assignment_name)
    if not assignment:
        print(f"error: no Canvas assignment named '{assignment_name}'. Run sync.py first.", file=sys.stderr)
        return 2

    workdir = Path(args.workdir).expanduser() / task["id"]
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        submissions = client.submissions(assignment["id"])
    except CanvasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    todo = []
    for sub in submissions:
        user = sub.get("user") or {}
        name = user.get("name") or f"user {sub.get('user_id')}"
        if sub.get("workflow_state") in ("unsubmitted", None):
            continue
        if not sub.get("attachments") and not sub.get("submitted_at"):
            continue
        if args.student and safe(args.student) not in safe(name):
            continue
        if not args.all and sub.get("grade") is not None and sub.get("grade") != "":
            continue
        todo.append((sub, name))

    print(f"{len(todo)} submission(s) to check in {workdir}")
    if args.dry_run:
        for _sub, name in todo:
            print(f"  {name}")
        return 0

    summary = []
    for sub, name in todo:
        folder = workdir / safe(name)
        folder.mkdir(parents=True, exist_ok=True)

        files = []
        for att in sub.get("attachments") or []:
            url = att.get("url") or att.get("proxy_url")
            filename = att.get("filename") or "submission.zip"
            target = folder / safe(filename)
            try:
                client.download(url, target)
                files.append(target)
            except Exception as exc:  # a failed download must not stop the run
                print(f"  ! {name}: could not download {filename} ({exc})")

        if not files:
            print(f"  - {name}: nothing downloadable")
            continue

        source = files[0] if len(files) == 1 else folder
        try:
            report = runner.run(task, source)
        except runner.TaskError as exc:
            print(f"  ! {name}: {exc}")
            continue

        report.student = name
        (folder / "check-report.txt").write_text(report.to_text() + "\n", encoding="utf-8")
        (folder / "check-report.json").write_text(
            json.dumps({**report.to_dict(), "canvas": {"user_id": sub["user_id"], "assignment_id": assignment["id"]}}, indent=2) + "\n",
            encoding="utf-8",
        )

        verdict = report.verdict
        summary.append((name, verdict, len(report.failures), len(report.reviews)))
        mark = "ready" if verdict == "ready" else "fix  "
        print(f"  {mark} {name:<28} {report.summary()}")

    ready = sum(1 for _n, v, _f, _r in summary if v == "ready")
    print()
    print(f"{ready} of {len(summary)} ready for signoff. Reports in {workdir}")
    print("Read a report, then post the signoff with apply.py --reviewed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
