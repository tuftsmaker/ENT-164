#!/usr/bin/env python3
"""Post signoffs back to Canvas — only after a person has reviewed the report.

This is the deliberate gate: nothing signs off automatically. `--reviewed`
means a human read the report and is taking the decision, and the student gets
a comment that says who decided and on what evidence.

    # list what the reports say, without changing anything
    python3 canvas/apply.py --task cad-01-first-sketch --summary

    # post the signoff for students whose reports are ready
    python3 canvas/apply.py --task cad-01-first-sketch --reviewed --ready-only

    # post one student, with a note (e.g. after checking a photo)
    python3 canvas/apply.py --task cad-01-first-sketch --reviewed \
        --student "Jane Doe" --note "photo shows the cut part"
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
from canvas_client import CanvasError, Client, load_config  # noqa: E402

DEFAULT_WORKDIR = Path.home() / "ent164" / "grading"

SIGNOFF_TEXT = """\
{name} — task {task}: {verdict_phrase}

{summary}

The file checks and the notes above are recorded on this submission. Signed by a
{role} on {date} after reviewing the report.

{note}""".strip()

NEEDS_FIX_TEXT = """\
{name} — task {task}: not yet.

{summary}

{fixes}

Fix these in Onshape, re-export, run the checker again, and re-upload. There is no
penalty for resubmitting — the task is signed when the file meets the criteria."""


def load_reports(workdir: Path) -> dict:
    out = {}
    for folder in sorted(p for p in workdir.iterdir() if p.is_dir()):
        report_path = folder / "check-report.json"
        if not report_path.exists():
            continue
        data = json.loads(report_path.read_text())
        data["_folder"] = folder
        out[data.get("student") or folder.name] = data
    return out


def main(argv=None) -> int:
    import datetime

    parser = argparse.ArgumentParser(prog="apply")
    parser.add_argument("--task", "-t", required=True)
    parser.add_argument("--workdir", default=str(DEFAULT_WORKDIR))
    parser.add_argument("--student", help="only this student (a name substring)")
    parser.add_argument("--reviewed", action="store_true", help="a person has read the report")
    parser.add_argument("--ready-only", action="store_true", help="only post where no check failed")
    parser.add_argument("--note", default="", help="a line to add to the comment (what you looked at)")
    parser.add_argument("--role", default="TA")
    parser.add_argument("--summary", action="store_true", help="print the reports and stop")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        task = runner.load_task(args.task)
    except runner.TaskError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    workdir = Path(args.workdir).expanduser() / task["id"]
    if not workdir.exists():
        print(f"error: no reports in {workdir}. Run pull.py first.", file=sys.stderr)
        return 2
    reports = load_reports(workdir)
    if not reports:
        print(f"error: no check-report.json files in {workdir}", file=sys.stderr)
        return 2

    selected = {}
    for name, data in reports.items():
        if args.student and args.student.lower() not in name.lower():
            continue
        if args.ready_only and data.get("verdict") != "ready":
            continue
        selected[name] = data

    if args.summary or not args.reviewed or args.dry_run:
        print(f"{len(selected)} of {len(reports)} report(s) selected:")
        for name, data in selected.items():
            canvas = data.get("canvas") or {}
            grade = "signed already" if canvas.get("graded") else "ungraded"
            print(f"  {name:<28} {data.get('verdict'):<6} {data.get('summary','')}  [{grade}]")
        if not args.reviewed and not args.summary:
            print()
            print("Nothing was posted. Re-run with --reviewed once a person has read these.")
        if args.dry_run and args.reviewed:
            print()
            print("Dry run: nothing was posted.")
        return 0

    try:
        client = Client(**load_config())
    except CanvasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    assignment_name = f"{task['id']} · {task['title']}"
    assignment = client.find_assignment(assignment_name)
    if not assignment:
        print(f"error: no Canvas assignment named '{assignment_name}'", file=sys.stderr)
        return 2

    today = datetime.date.today().isoformat()
    posted = 0
    for name, data in selected.items():
        canvas = data.get("canvas") or {}
        user_id = canvas.get("user_id")
        if not user_id:
            print(f"  ! {name}: report has no Canvas user id; re-run pull.py")
            continue

        verdict = data.get("verdict")
        if verdict == "ready":
            fixes = ""
            summary = data.get("summary", "")
            body = SIGNOFF_TEXT.format(
                name=name.split()[0] if name else "there",
                task=task["id"],
                verdict_phrase="signed off. Your file meets every written criterion, and this task is complete.",
                summary=f"What was checked: {summary}.",
                role=args.role,
                date=today,
                note=args.note or "The parts marked for review were checked before posting.",
            )
            grade = "complete"
        else:
            fixes = "\n".join(
                f"- {c['title']}: {c['detail']}" + (f"\n  → {c['fix']}" if c.get("fix") else "")
                for c in data.get("criteria", [])
                if c["status"] == "fail"
            )
            body = NEEDS_FIX_TEXT.format(
                name=name.split()[0] if name else "there",
                task=task["id"],
                summary=data.get("summary", ""),
                fixes=fixes or "See the report.",
            )
            grade = "incomplete"

        try:
            client.post_grade(assignment["id"], user_id, grade, comment_text=body)
            print(f"  posted {grade:<11} {name}")
            posted += 1
        except CanvasError as exc:
            print(f"  ! {name}: {exc}")

    print()
    print(f"posted {posted} signoff(s) on assignment {assignment['id']}.")
    print("Students see the comment and the rubric; the record stays in Canvas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
