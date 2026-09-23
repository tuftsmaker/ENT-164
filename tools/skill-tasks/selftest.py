#!/usr/bin/env python3
"""Check the checker.

Every fixture declares, in its own `fixture.json`, what the report should say.
This runs each one and compares. A change to a check that changes a verdict has
to be reflected here deliberately — that is the point.

    python3 check/selftest.py            # all fixtures
    python3 check/selftest.py -v         # show each report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tools/skill-tasks
REPO = HERE.parent.parent
CHECK = REPO / "skills" / "maker-tasks" / "check"
sys.path.insert(0, str(CHECK))

import runner  # noqa: E402

FIXTURES = HERE / "fixtures"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="selftest")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--filter", help="only fixtures whose name contains this")
    parser.add_argument("--show", action="store_true", help="print the full report for failures")
    args = parser.parse_args(argv)

    if not FIXTURES.exists():
        print(f"no fixtures at {FIXTURES} — run check/make_fixtures.py first", file=sys.stderr)
        return 2

    failures = []
    total = 0
    for folder in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        meta_path = folder / "fixture.json"
        if not meta_path.exists():
            continue
        if args.filter and args.filter not in folder.name:
            continue
        total += 1
        meta = json.loads(meta_path.read_text())
        task = runner.load_task(meta["task"])
        report = runner.run(task, folder)
        expect = meta.get("expect", {})

        problems = []
        if report.verdict != expect.get("verdict"):
            problems.append(f"verdict {report.verdict!r}, expected {expect.get('verdict')!r}")
        for cid in expect.get("fails", []):
            if cid not in [c.id for c in report.failures]:
                problems.append(f"expected {cid} to fail")
        for cid in expect.get("reviews", []):
            if cid not in [c.id for c in report.reviews]:
                problems.append(f"expected {cid} to need review")
        for cid in expect.get("not_fails", []):
            if cid in [c.id for c in report.failures]:
                problems.append(f"did not expect {cid} to fail")

        status = "ok  " if not problems else "FAIL"
        print(f"{status} {folder.name:<26} {meta.get('note','')}")
        if args.verbose or problems:
            for line in report.to_text().splitlines():
                print(f"        {line}")
        if problems:
            failures.append((folder.name, problems))

    print()
    if failures:
        print(f"{len(failures)} of {total} fixtures disagree with the checker:")
        for name, problems in failures:
            for p in problems:
                print(f"  {name}: {p}")
        return 1
    print(f"all {total} fixtures agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
