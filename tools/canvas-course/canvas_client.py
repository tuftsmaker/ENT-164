#!/usr/bin/env python3
"""Canvas: the API calls behind the course tools (modules and the home page).

Keeps the course structure in Canvas as links to the class site, never copies.
Nothing here runs in a student's browser or in the skill; this is the
instructor's machine only.

Credentials live OUTSIDE this repo, with the rest of the class secrets, in
`~/.config/tuftsmaker/canvas_config.py` (mode 0600, dir 0700):

    CANVAS_URL   = "https://<institution>.instructure.com"
    CANVAS_TOKEN = "<personal access token>"

`COURSE_ID` is accepted but ignored: development targets the prototype course
below, so a stale or copied config cannot decide which course these tools touch.

The repo keeps course **content** only, and reads are an allow-list that fails
closed (`READ_FAMILIES`): rosters, submissions, grades and discussion posts
cannot be fetched, even by a script that asks for them.

    python3 tools/canvas-course/canvas_client.py whoami
    python3 tools/canvas-course/canvas_client.py modules
    python3 tools/canvas-course/canvas_client.py courses
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
PROTOTYPE_COURSE = "81044"  # "Intro to Making Prototype" — disposable
LIVE_COURSE = "76330"       # Fa26-ENT-0164-01 — real students, real grades
DEV_COURSE = PROTOTYPE_COURSE

# Set this to allow a write against a course other than DEV_COURSE. Deliberately
# awkward to type and deliberately not a CLI flag on the ordinary paths: the
# point is that reaching the live course must be a decision, not a typo.
OVERRIDE_ENV = "CANVAS_ALLOW_LIVE"


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

    def _guard(self, method: str, path: str, params: dict | None = None):
        """Every request funnels through here, and the two rules are:

        * **Reads are content-only, and fail closed.** The path must be one of
          `READ_FAMILIES` and `include[]` may not ask for people, so rosters,
          submissions, grades and discussion posts stay out of the repo even
          when a script asks for them.
        * **Writes go to the prototype only.** Canvas tokens cannot be scoped
          to a course, so the boundary lives here: a write aimed at any other
          course stops before it leaves the machine. The comparison is against
          `DEV_COURSE`, never against `self.course_id` — constructing a client
          *for* the live course is precisely the mistake this must catch, so a
          client's own target cannot be its permission.

        Escape hatch, for the deliberate case: set CANVAS_ALLOW_LIVE=1.
        """
        if _read_family(path) is None:
            raise CanvasError(
                f"refusing {method} {path}: not a content route "
                f"({', '.join(sorted(READ_FAMILIES))}). The repo keeps course "
                f"content only — never rosters, submissions, grades or discussions."
            )
        denied = _denied_includes(params)
        if denied:
            raise CanvasError(
                f"refusing {method} {path}: include[]={','.join(sorted(denied))} "
                f"is people data and stays out of this repo."
            )
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
        self._guard(method, path, params)
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

    def add_module_item(self, module_id, **fields):
        return self.post(
            f"/courses/{self.course_id}/modules/{module_id}/items",
            module_item=fields,
        )

    def update_module_item(self, module_id, item_id, **fields):
        """Careful: for a Page item Canvas treats `title` as the page's title,
        renaming and re-slugging the page — which renames its URL with it."""
        return self.put(
            f"/courses/{self.course_id}/modules/{module_id}/items/{item_id}",
            module_item=fields,
        )


# What the tools may read: course content, and only course content. The repo
# holds no people, so the read side is an allow-list and it fails closed — a
# future script cannot widen it by asking; the families change here, reviewed.
READ_FAMILIES = {
    "whoami": re.compile(r"^/users/self$"),
    "courses": re.compile(r"^/courses$"),
    "course": re.compile(r"^/courses/\d+$"),
    "tabs": re.compile(r"^/courses/\d+/tabs$"),
    "modules": re.compile(r"^/courses/\d+/modules$"),
    "module": re.compile(r"^/courses/\d+/modules/\d+$"),
    "module items": re.compile(r"^/courses/\d+/modules/\d+/items$"),
    "module item": re.compile(r"^/courses/\d+/modules/\d+/items/\d+$"),
    "assignments": re.compile(r"^/courses/\d+/assignments$"),
    "assignment": re.compile(r"^/courses/\d+/assignments/\d+$"),
    "assignment groups": re.compile(r"^/courses/\d+/assignment_groups$"),
    "assignment group": re.compile(r"^/courses/\d+/assignment_groups/\d+$"),
    "pages": re.compile(r"^/courses/\d+/pages$"),
    "page": re.compile(r"^/courses/\d+/pages/[^/]+$"),
    "front page": re.compile(r"^/courses/\d+/front_page$"),
    "file": re.compile(r"^/courses/\d+/files/\d+$"),
}

# include[]= values that carry people; refused wherever they appear.
INCLUDE_DENY = {
    "enrollments", "teachers", "students", "users", "observed_users",
    "submission", "submissions", "grades",
}


def _read_family(path: str) -> str | None:
    """The content family a path belongs to, or None (refused)."""
    for name, pattern in READ_FAMILIES.items():
        if pattern.match(path):
            return name
    return None


def _denied_includes(params: dict | None) -> set:
    """The people-carrying include[] values a request's params ask for."""
    if not params:
        return set()
    include = params.get("include") or []
    if isinstance(include, str):
        include = [include]
    return {str(value) for value in include} & INCLUDE_DENY


def _course_in(path: str) -> str | None:
    """The course a Canvas path targets, if it is scoped to one.

    Canvas paths look like /courses/76330/modules or
    /courses/81044/modules/1/items. Anything else (an account or user route)
    returns None.
    """
    m = re.match(r"^/courses/(\d+)(?:/|$)", path)
    return m.group(1) if m else None


def _flatten(body: dict) -> list:
    """Canvas's form encoding: `a[k]=v` for hashes, repeated `a[]=v` for lists.

    A list of pairs, not a dict: a dict keeps one value per key, so an array
    silently lost every element but the last — which is how `submission_types`
    came back as a single entry.
    """
    out = []

    def walk(prefix, value):
        if isinstance(value, dict):
            for key, item in value.items():
                walk(f"{prefix}[{key}]" if prefix else str(key), item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(f"{prefix}[]", item)
        else:
            out.append((prefix, value))

    for key, value in body.items():
        walk(key, value)
    return out


# ---------------------------------------------------------------- CLI


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="canvas_client")
    parser.add_argument("command", choices=["whoami", "modules", "courses"])
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
        elif args.command == "modules":
            for m in client.modules():
                print(f"{m['id']:>10}  {m['name']}  ({len(client.module_items(m['id']))} items)")
        elif args.command == "courses":
            # Read-only: every course this token can see, with its term. This is
            # how the live ID is found when a semester rolls over; the ID itself
            # is updated by hand below, never resolved at run time.
            rows = []
            for course in client.get("/courses", include=["term"]):
                term = (course.get("term") or {}).get("name") or "-"
                rows.append((term, course.get("name") or "", int(course["id"])))
            rows.sort(key=lambda row: (row[0].lower(), row[1].lower()))
            print(f"{'id':>8}  {'term':<14}  name")
            for term, name, cid in rows:
                mark = ""
                if str(cid) == PROTOTYPE_COURSE:
                    mark = "  (prototype)"
                elif str(cid) == LIVE_COURSE:
                    mark = "  (live)"
                print(f"{cid:>8}  {term:<14}  {name}{mark}")
    except CanvasError as exc:
        print(f"error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
