#!/usr/bin/env python3
"""Canvas: task <-> assignment mapping, and the API calls behind sync/pull/apply.

Signoffs live in Canvas — it is the system of record, it already holds the
submissions, and it keeps student work out of this repo. Nothing here runs in a
student's browser or in the skill; this is the TA's machine only.

Credentials live OUTSIDE this repo, with the rest of the class secrets, in
`~/.config/tuftsmaker/canvas_config.py` (mode 0600, dir 0700):

    CANVAS_URL   = "https://<institution>.instructure.com"
    CANVAS_TOKEN = "<personal access token>"

`COURSE_ID` is accepted but ignored: development targets the prototype course
below, so a stale or copied config cannot decide which course these tools touch.

    python3 canvas/canvas_client.py whoami
    python3 canvas/canvas_client.py assignments
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "tuftsmaker"
CONFIG_PATH = CONFIG_DIR / "canvas_config.py"

CONFIG_HINT = f"""\
    Expected config file: {CONFIG_PATH}

        CANVAS_URL   = "https://canvas.example.edu"
        CANVAS_TOKEN = "<personal access token from User Settings>"

    Create it with:
        mkdir -p {CONFIG_DIR} && chmod 700 {CONFIG_DIR}
        $EDITOR {CONFIG_PATH} && chmod 600 {CONFIG_PATH}

    Same directory as the YouTube credentials — the class keeps its secrets in
    one place, outside the repo, never committed.""".rstrip()

# Which course these tools may touch. Everything in tools/ is in development
# against the prototype; the live course is only ever reached deliberately.
PROTOTYPE_COURSE = "71548"  # "Intro to Making Prototype" — disposable
LIVE_COURSE = "76330"       # Fa26-ENT-0164-01 — real students, real grades
DEV_COURSE = PROTOTYPE_COURSE

# Set this to allow a write against a course other than DEV_COURSE. Deliberately
# awkward to type and deliberately not a CLI flag on the ordinary paths: the
# point is that reaching the live course must be a decision, not a typo.
OVERRIDE_ENV = "CANVAS_ALLOW_LIVE"

# The weight of the tasks' assignment category: 0.0 keeps them off the grade
# while still recording completion. Feedback-only this semester, by design. The
# category is named after the open track — sync.py reads the unit's title in
# `skills/maker-tasks/tasks/`.
GROUP_WEIGHT = 0.0


class CanvasError(Exception):
    pass


class LiveCourseRefused(CanvasError):
    """Raised when a write is aimed at a course other than the prototype."""


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        raise CanvasError(f"no Canvas config at {path}.\n\n{CONFIG_HINT}")
    namespace = {}
    try:
        exec(compile(path.read_text(), str(path), "exec"), namespace)  # noqa: S102
    except SyntaxError as exc:
        raise CanvasError(f"{path} is not valid Python: {exc}") from None
    missing = [k for k in ("CANVAS_URL", "CANVAS_TOKEN") if not namespace.get(k)]
    if missing:
        raise CanvasError(
            f"{path} is missing {', '.join(missing)}.\n\n{CONFIG_HINT}"
        )
    _warn_if_readable_by_others(path)
    # Development points at the prototype, whatever the config's COURSE_ID says:
    # a stale or copied config must not decide which course tools touch.
    return {
        "base": str(namespace["CANVAS_URL"]).rstrip("/"),
        "token": str(namespace["CANVAS_TOKEN"]),
        "course_id": DEV_COURSE,
    }


def _warn_if_readable_by_others(path: Path) -> None:
    """A token file the whole machine can read is worth saying out loud once.
    A warning, not an error: Windows and unusual umasks would otherwise make
    the tools unusable over a permission bit that Canvas does not care about."""
    import stat

    try:
        mode = path.stat().st_mode
    except OSError:
        return
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        import sys

        print(
            f"warning: {path} is readable by other users "
            f"(mode {stat.filemode(mode)}). Run: chmod 600 {path}",
            file=sys.stderr,
        )


@dataclass
class Client:
    base: str
    token: str
    course_id: str
    _cache: dict = None

    def __post_init__(self):
        self._cache = {}

    # -- plumbing ---------------------------------------------------------

    def _guard(self, method: str, path: str):
        """Refuse to write outside the development course.

        Canvas tokens cannot be scoped to a course, so the boundary lives here:
        every request funnels through `_request`, and a write aimed at another
        course stops before it leaves the machine. Reads are allowed — reading
        the live course is how you compare against it — but nothing changes
        there.

        The comparison is against DEV_COURSE, never against `self.course_id`:
        constructing a client *for* the live course is precisely the mistake
        this must catch, so a client's own target cannot be its permission.

        Escape hatch, for the deliberate case: set CANVAS_ALLOW_LIVE=1.
        """
        if method in ("GET", "HEAD"):
            return
        if os.environ.get(OVERRIDE_ENV) == "1":
            return

        target = _course_in(path)
        if target is None:
            # An account- or user-level write, e.g. creating a course.
            raise LiveCourseRefused(
                f"refusing {method} {path}: it is not scoped to a course, and these "
                f"tools only write inside course {DEV_COURSE}. "
                f"Set {OVERRIDE_ENV}=1 if you really mean it."
            )
        if target != DEV_COURSE:
            hint = (
                f" (that is the live course — real students, real grades)"
                if target == LIVE_COURSE else ""
            )
            raise LiveCourseRefused(
                f"refusing {method} {path}: it targets course {target}{hint}. "
                f"These tools only write inside course {DEV_COURSE}. "
                f"Set {OVERRIDE_ENV}=1 if you really mean it."
            )

    def _request(self, method: str, path: str, body: dict | None = None, params: dict | None = None):
        self._guard(method, path)
        url = f"{self.base}/api/v1{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        data = None
        if body is not None:
            if isinstance(body, bytes):
                data = body
            else:
                data = urllib.parse.urlencode(_flatten(body)).encode()
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        if data and not req.get_header("Content-type"):
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise CanvasError(f"{method} {path} -> HTTP {exc.code}: {detail}") from None
        if not raw:
            return None
        return json.loads(raw)

    def get(self, path, **params):
        return self._paginate("GET", path, params=params)

    def _paginate(self, method, path, params=None, body=None, per_page=100):
        """Canvas pages at 10 by default and we never read the Link header, so
        ask explicitly for a page size and keep going while pages come back
        full."""
        params = dict(params or {})
        params.setdefault("per_page", per_page)
        out = []
        page_number = 1
        while True:
            params["page"] = page_number
            page = self._request(method, path, body=body, params=params)
            if not isinstance(page, list):
                return page
            out.extend(page)
            if len(page) < per_page:
                return out
            page_number += 1

    def post(self, path, **body):
        return self._request("POST", path, body=body)

    def put(self, path, **body):
        return self._request("PUT", path, body=body)

    # -- course -----------------------------------------------------------

    def whoami(self):
        return self._request("GET", "/users/self")

    def assignment_groups(self):
        return self.get(f"/courses/{self.course_id}/assignment_groups")

    def ensure_group(self, name, weight=GROUP_WEIGHT):
        for group in self.assignment_groups():
            if group["name"] == name:
                return group
        return self.post(
            f"/courses/{self.course_id}/assignment_groups",
            name=name,
            group_weight=weight,
        )

    def modules(self):
        return self.get(f"/courses/{self.course_id}/modules")

    def ensure_module(self, name, position=None):
        for mod in self.modules():
            if mod["name"] == name:
                return mod
        body = {"module": {"name": name}}
        if position:
            body["module"]["position"] = position
        return self.post(f"/courses/{self.course_id}/modules", **body)

    def module_items(self, module_id):
        return self.get(f"/courses/{self.course_id}/modules/{module_id}/items")

    def assignments(self):
        return self.get(f"/courses/{self.course_id}/assignments")

    def find_assignment(self, name):
        for a in self.assignments():
            if a["name"] == name:
                return a
        return None

    def create_assignment(self, name, description, points=0.0, group_id=None, published=False):
        body = {
            "assignment": {
                "name": name,
                "description": description,
                "points_possible": points,
                "submission_types": ["online_upload"],
                "allowed_extensions": ["zip", "dxf", "md", "pdf", "png", "jpg"],
                "published": bool(published),
            }
        }
        if group_id:
            body["assignment"]["assignment_group_id"] = group_id
        return self.post(f"/courses/{self.course_id}/assignments", **body)

    def update_assignment(self, assignment_id, **fields):
        published = fields.pop("published", None)
        if published is not None:
            fields["published"] = published in (True, "true", "True")
        return self.put(
            f"/courses/{self.course_id}/assignments/{assignment_id}",
            assignment=fields,
        )

    def add_module_item(self, module_id, **fields):
        return self.post(
            f"/courses/{self.course_id}/modules/{module_id}/items",
            module_item=fields,
        )

    def submissions(self, assignment_id, include_user=True):
        params = {}
        if include_user:
            params["include[]"] = ["user", "submission_comments"]
        return self.get(f"/courses/{self.course_id}/assignments/{assignment_id}/submissions", **params)

    def download(self, url, target: Path):
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {self.token}")
        with urllib.request.urlopen(req, timeout=120) as resp, open(target, "wb") as fh:
            shutil_copy(resp, fh)
        return target

    def comment(self, assignment_id, user_id, text):
        return self.put(
            f"/courses/{self.course_id}/assignments/{assignment_id}/submissions/{user_id}",
            comment={"text": text},
        )

    def post_grade(self, assignment_id, user_id, grade, comment_text=None):
        body = {"submission": {"posted_grade": grade}}
        if comment_text:
            body["comment"] = {"text": comment_text}
        return self.put(
            f"/courses/{self.course_id}/assignments/{assignment_id}/submissions/{user_id}",
            **body,
        )

    def rubric(self, assignment_id):
        data = self._request("GET", f"/courses/{self.course_id}/assignments/{assignment_id}", params={"include[]": ["rubric"]})
        return (data or {}).get("rubric")

    def create_rubric(self, assignment_id, criteria, use_for_grading=False):
        """Create a course rubric from `criteria` and attach it to the
        assignment. Each row gets a Met/Not-yet pair of ratings so a TA can
        click through in SpeedGrader — the record of the signoff.

        Re-running replaces the rubric: Canvas has no in-place criteria edit.
        """
        title = f"task-{assignment_id}"
        rows = [
            {
                "description": c["description"],
                "long_description": c.get("long_description", ""),
                "points": 0,
                "ratings": [
                    {"description": "Met", "points": 0},
                    {"description": "Not yet", "points": 0},
                ],
            }
            for c in criteria
        ]
        body = {"rubric[title]": title, "rubric[free_form_criterion_comments]": "true"}
        for i, row in enumerate(rows):
            body[f"rubric[criteria][{i}][description]"] = row["description"]
            body[f"rubric[criteria][{i}][long_description]"] = row["long_description"]
            body[f"rubric[criteria][{i}][points]"] = row["points"]
            for j, rating in enumerate(row["ratings"]):
                body[f"rubric[criteria][{i}][ratings][{j}][description]"] = rating["description"]
                body[f"rubric[criteria][{i}][ratings][{j}][points]"] = rating["points"]

        created = self._request("POST", f"/courses/{self.course_id}/rubrics", body=body)
        rubric = (created or {}).get("rubric") or {}
        rubric_id = rubric.get("id")
        if not rubric_id:
            raise CanvasError("Canvas did not return a rubric id")

        # Attach the rubric to the assignment (course-level association
        # endpoint; rubric_settings[rubric_id] alone does not link it).
        self._request(
            "POST",
            f"/courses/{self.course_id}/rubric_associations",
            body={
                "rubric_association[rubric_id]": rubric_id,
                "rubric_association[association_id]": assignment_id,
                "rubric_association[association_type]": "Assignment",
                "rubric_association[purpose]": "grading",
                "rubric_association[use_for_grading]": "false",
            },
        )
        return {"id": rubric_id, "rows": len(rows), "title": rubric.get("title")}


def _course_in(path: str) -> str | None:
    """The course a Canvas path targets, if it is scoped to one.

    Canvas paths look like /courses/76330/assignments or
    /courses/71548/rubrics/29917/rubric_associations. Anything else (an account
    or user route) returns None.
    """
    m = re.match(r"^/courses/(\d+)(?:/|$)", path)
    return m.group(1) if m else None


def _flatten(body: dict) -> dict:
    """Canvas wants `a[]` for lists and nested k:v for hashes as urlencoded
    brackets."""
    out = {}

    def walk(prefix, value):
        if isinstance(value, dict):
            for k, v in value.items():
                walk(f"{prefix}[{k}]" if prefix else str(k), v)
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                walk(f"{prefix}[]", v)
        else:
            out[prefix] = value

    for key, value in body.items():
        walk(key, value)
    return out


def shutil_copy(src, dst):
    while True:
        chunk = src.read(65536)
        if not chunk:
            break
        dst.write(chunk)


# ---------------------------------------------------------------- CLI


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="canvas_client")
    parser.add_argument("command", choices=["whoami", "assignments", "modules", "groups"])
    args = parser.parse_args(argv)

    try:
        cfg = load_config()
    except CanvasError as exc:
        print(f"error: {exc}")
        return 2

    client = Client(**cfg)
    try:
        if args.command == "whoami":
            me = client.whoami()
            print(f"{me.get('name')} ({me.get('login_id')})")
        elif args.command == "assignments":
            for a in client.assignments():
                print(f"{a['id']:>10}  pub={str(a.get('published')):<5} {a['name']}")
        elif args.command == "modules":
            for m in client.modules():
                print(f"{m['id']:>10}  {m['name']}  ({len(client.module_items(m['id']))} items)")
        elif args.command == "groups":
            for g in client.assignment_groups():
                print(f"{g['id']:>10}  weight={g.get('group_weight')}  {g['name']}")
    except CanvasError as exc:
        print(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
