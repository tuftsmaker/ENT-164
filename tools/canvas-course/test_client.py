#!/usr/bin/env python3
"""The client's form encoding — offline, no network.

Canvas wants `a[k]=v` for hashes and repeated `a[]=v` for lists. A dict of
pairs kept only the last element of an array, so `submission_types` silently
lost every value but one; this pins the encoding down.

    python3 tools/canvas-course/test_client.py
"""
from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from canvas_client import _flatten  # noqa: E402

CASES = [
    ("a scalar", {"name": "X"}, "name=X"),
    ("a hash", {"assignment": {"name": "X", "points_possible": 5}},
     "assignment%5Bname%5D=X&assignment%5Bpoints_possible%5D=5"),
    ("an array", {"assignment": {"submission_types": ["one", "two", "three"]}},
     "assignment%5Bsubmission_types%5D%5B%5D=one"
     "&assignment%5Bsubmission_types%5D%5B%5D=two"
     "&assignment%5Bsubmission_types%5D%5B%5D=three"),
    ("a flat array", {"ids": [1, 2]}, "ids%5B%5D=1&ids%5B%5D=2"),
]


def main() -> int:
    problems = 0
    for label, body, want in CASES:
        got = urllib.parse.urlencode(_flatten(body))
        ok = got == want
        problems += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {label:<12} {got}")
        if not ok:
            print(f"     want {want}")
    print()
    if problems:
        print(f"{problems} problem(s).")
        return 1
    print(f"all {len(CASES)} cases behave: hashes are bracketed, arrays repeat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
