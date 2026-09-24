#!/usr/bin/env python3
"""The Canvas comment link reader, proven offline.

Canvas allows one submission type per submission, so a student handing in a zip
cannot also submit a Website URL. The comment box is where a pasted Onshape
link rides along, and `pull.py` reads it. This test stubs the API shapes, so it
runs with no network and no Canvas account.

    python3 tools/skill-tasks/canvas/test_pull.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pull  # noqa: E402

LINK = ("https://cad.onshape.com/documents/aaaaaaaaaaaaaaaaaaaaaaaa/"
        "w/bbbbbbbbbbbbbbbbbbbbbbbb/e/cccccccccccccccccccccccc")
OLD = ("https://cad.onshape.com/documents/111111111111111111111111/"
       "w/222222222222222222222222/e/333333333333333333333333")


def comment(text, author_id=7, created="2026-09-24T10:00:00Z"):
    return {"comment": text, "author_id": author_id, "created_at": created}


def submission(*comments):
    return {"submission_comments": list(comments)}


CASES = [
    ("a student's comment carries the link",
     submission(comment(f"here it is — {LINK}, thanks")), 7, LINK),
    ("trailing punctuation is trimmed",
     submission(comment(f"link: {LINK};")), 7, LINK),
    ("a link split across lines is not invented",
     submission(comment("https://cad.onshape.com/documents/\nnot-a-real-link")), 7, None),
    ("a TA's comment is ignored",
     submission(comment(f"check {LINK}", author_id=99)), 7, None),
    ("the newest student comment wins",
     submission(comment(f"old {OLD}", created="2026-09-23T09:00:00Z"),
                comment(f"new {LINK}", created="2026-09-24T09:00:00Z")), 7, LINK),
    ("no comments", submission(), 7, None),
    ("a non-Onshape URL is not the link",
     submission(comment("https://example.com/documents/x")), 7, None),
    ("no user id: any comment counts",
     submission(comment(LINK)), None, LINK),
]


def main() -> int:
    problems = []
    for label, sub, user_id, want in CASES:
        got = pull.link_from_comments(sub, user_id)
        ok = got == want
        if not ok:
            problems.append(f"{label}: got {got!r}, expected {want!r}")
        print(f"{'ok  ' if ok else 'FAIL'} {label:<44} {got}")
    print()
    if problems:
        for p in problems:
            print(f"  {p}")
        print(f"{len(problems)} problem(s).")
        return 1
    print(f"all {len(CASES)} cases behave.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
