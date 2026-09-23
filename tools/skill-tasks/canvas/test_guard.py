#!/usr/bin/env python3
"""Prove the Canvas tools cannot write to the live course.

Canvas tokens cannot be scoped to a course — scopes restrict *endpoints*, and
`:course_id` in a scope is a path placeholder, not a filter — so the boundary
has to live in our code. It does: `Client._guard` refuses any write that is not
aimed at the development course.

This test is the proof. Every case stubs the transport, so nothing reaches the
network, and asserts whether the guard let the call through. It runs offline.

    python3 tools/skill-tasks/canvas/test_guard.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import canvas_client  # noqa: E402
from canvas_client import (  # noqa: E402
    DEV_COURSE,
    LIVE_COURSE,
    OVERRIDE_ENV,
    Client,
    LiveCourseRefused,
)

calls: list = []


class RecordingTransport:
    """Stands in for urlopen; records that a call got through the guard."""

    def __init__(self, req, timeout=None):
        calls.append((req.method, req.full_url))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b"[]"


def client_for(course_id: str) -> Client:
    return Client(base="https://canvas.invalid", token="not-a-real-token", course_id=course_id)


def attempt(fn) -> bool:
    """True if the call reached the transport, False if the guard refused it."""
    before = len(calls)
    try:
        fn()
    except LiveCourseRefused:
        return False
    except Exception:
        # Anything else (a bad URL, a decode error) still means it got past the
        # guard, which is what this test measures.
        pass
    return len(calls) > before


# (label, call, should_reach_the_network)
CASES = [
    ("write to the dev course", lambda: client_for(DEV_COURSE)._request(
        "POST", f"/courses/{DEV_COURSE}/assignments", body={"a": 1}), True),

    ("write to the live course", lambda: client_for(DEV_COURSE)._request(
        "POST", f"/courses/{LIVE_COURSE}/assignments", body={"a": 1}), False),

    ("a client built for the live course", lambda: client_for(LIVE_COURSE)._request(
        "PUT", f"/courses/{LIVE_COURSE}/assignments/1"), False),

    ("deleting a module on the live course", lambda: client_for(LIVE_COURSE)._request(
        "DELETE", f"/courses/{LIVE_COURSE}/modules/1"), False),

    ("attaching a rubric on the live course", lambda: client_for(LIVE_COURSE)._request(
        "POST", f"/courses/{LIVE_COURSE}/rubric_associations", body={}), False),

    ("posting a grade on the live course", lambda: client_for(LIVE_COURSE).post_grade(
        1, 2, "complete", "text"), False),

    ("a write to an unrelated course", lambda: client_for(LIVE_COURSE)._request(
        "POST", "/courses/99999/assignments", body={}), False),

    ("an account-level write", lambda: client_for(DEV_COURSE)._request(
        "POST", "/accounts/1/developer_keys", body={}), False),

    ("a user-level write", lambda: client_for(DEV_COURSE)._request(
        "PUT", "/users/1", body={}), False),

    ("reading the live course (allowed)", lambda: client_for(DEV_COURSE)._request(
        "GET", f"/courses/{LIVE_COURSE}/assignments"), True),

    ("reading the dev course (allowed)", lambda: client_for(DEV_COURSE)._request(
        "GET", f"/courses/{DEV_COURSE}/assignments"), True),
]


def main() -> int:
    real_transport = canvas_client.urllib.request.urlopen
    canvas_client.urllib.request.urlopen = RecordingTransport
    problems = []
    try:
        os.environ.pop(OVERRIDE_ENV, None)
        for label, call, should_pass in CASES:
            got = attempt(call)
            ok = got == should_pass
            if not ok:
                problems.append(
                    f"{label}: {'reached Canvas' if got else 'was refused'}, "
                    f"expected {'allowed' if should_pass else 'refused'}"
                )
            print(f"{'ok  ' if ok else 'FAIL'} {label:<44} "
                  f"{'allowed' if got else 'refused'}")

        # The escape hatch must still work, or the guard is unshippable.
        os.environ[OVERRIDE_ENV] = "1"
        got = attempt(lambda: client_for(LIVE_COURSE)._request(
            "PUT", f"/courses/{LIVE_COURSE}/assignments/1", body={}))
        if not got:
            problems.append(f"{OVERRIDE_ENV}=1 did not allow the write")
        print(f"{'ok  ' if got else 'FAIL'} {OVERRIDE_ENV}=1 allows the live course")
    finally:
        os.environ.pop(OVERRIDE_ENV, None)
        canvas_client.urllib.request.urlopen = real_transport

    print()
    if problems:
        for p in problems:
            print(f"  {p}")
        print(f"{len(problems)} problem(s).")
        return 1
    print(f"all {len(CASES) + 1} cases behave: writes stop at {DEV_COURSE}, reads pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
