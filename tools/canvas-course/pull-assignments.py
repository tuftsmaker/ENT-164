#!/usr/bin/env python3
"""Import the class assignments from Canvas into the repo.

The repo is the master copy of the course *content*; Canvas is where it meets
people. This reads what Canvas has — names, descriptions, points, dates,
assignment groups, and where each assignment sits inside its module — and
writes:

    classes/class-NN/assignments.yml           one entry per assignment
    classes/class-NN/assignments/<slug>.html   the scrubbed description
    tools/canvas-course/canvas-ids.yml         Canvas ids, per course

Content only: canvas_client's guard allows content routes, so no roster,
submission, grade or discussion is ever read.

    python3 tools/canvas-course/pull-assignments.py             # import from live
    python3 tools/canvas-course/pull-assignments.py --report    # the link table
    python3 tools/canvas-course/pull-assignments.py --check     # drift, no writes
    python3 tools/canvas-course/pull-assignments.py --ids 81044 # record ids

A pull overwrites the files it owns with Canvas's version: edits made in Canvas
are pulled in, edits made in the repo are pushed out (a later phase). Do not do
both between syncs.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import yaml  # noqa: E402
from canvas_client import Client, load_config  # noqa: E402

# render-assignments owns the assignment data — `plain_name` is the key names
# match on. Loaded by path because the file name carries a dash.
_RA_SPEC = importlib.util.spec_from_file_location("render_assignments", HERE / "render-assignments.py")
render_assignments = importlib.util.module_from_spec(_RA_SPEC)
_RA_SPEC.loader.exec_module(render_assignments)
plain_name = render_assignments.plain_name

COURSE_YML = HERE / "course.yml"
IDS_YML = HERE / "canvas-ids.yml"
CLASSES = ROOT / "classes"

_URL_ATTR = re.compile(r'(href|src)="([^"]*)"', re.I)
_DP_APP = re.compile(r"<link[^>]*dp_app\.css[^>]*>\s*", re.I)
_DP_SCRIPT = re.compile(r"<script[^>]*dp_app\.js[^>]*>\s*</script>\s*", re.I)
_DATA_API = re.compile(r'\s+data-api-[a-z-]+="[^"]*"', re.I)
_CANVAS_FILE = re.compile(r"/courses/\d+/files/\d+")

# Key-shaped strings do not belong in a public repo, and GitHub's push
# protection blocks them anyway. Canvas descriptions are imported verbatim, so
# redact them here and say so: the key stays in Canvas, where students read it.
_SECRETS = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{20,}"              # Anthropic
    r"|sk-[A-Za-z0-9]{20,}"                   # OpenAI-style
    r"|AKIA[0-9A-Z]{16}"                      # AWS access key id
    r"|ghp_[A-Za-z0-9]{36}"                   # GitHub personal access token
    r"|github_pat_[A-Za-z0-9_]{20,}"          # GitHub fine-grained token
    r"|xox[bpsa]-[A-Za-z0-9-]{10,}"           # Slack
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"    # PEM
)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _clean_url(match: re.Match) -> str:
    attr, url = match.group(1), match.group(2)
    if "verifier=" not in url:
        return match.group(0)
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k != "verifier"]
    return f'{attr}="{urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))}"'


def scrub(html: str, where: str = "") -> str:
    """Canvas's injections out; the authored HTML stays, minus secrets."""
    html = _DP_APP.sub("", html)
    html = _DP_SCRIPT.sub("", html)
    html = _DATA_API.sub("", html)
    html = _URL_ATTR.sub(_clean_url, html)
    html, redacted = _SECRETS.subn("[redacted secret]", html)
    if redacted:
        print(f"warning: redacted {redacted} secret-shaped string(s) from "
              f"{where or 'a description'} — keep secrets in Canvas, never in "
              f"the repo", file=sys.stderr)
    return html


def client_for(course_id: str) -> Client:
    cfg = load_config()
    cfg["course_id"] = str(course_id)
    return Client(**cfg)


def read_course(client: Client, module_pattern: str) -> dict:
    """A course's assignments, groups, and where each assignment sits."""
    pattern = re.compile(module_pattern)
    cid = client.course_id
    groups = {g["id"]: g["name"] for g in client.get(f"/courses/{cid}/assignment_groups")}
    modules, non_class, places = {}, [], {}
    for module in client.modules():
        hit = pattern.match(module["name"])
        cls = f"class-{int(hit.group(1)):02d}" if hit else None
        if cls:
            modules[cls] = {"id": module["id"], "name": module["name"]}
        else:
            non_class.append(module["name"])
        section = None
        for item in client.module_items(module["id"]):
            if item["type"] == "SubHeader":
                section = item["title"]
            elif item["type"] == "Assignment" and cls:
                places.setdefault(item.get("content_id"), []).append(
                    {"class": cls, "position": item.get("position"), "section": section})
    return {
        "assignments": client.get(f"/courses/{cid}/assignments"),
        "groups": groups,
        "modules": modules,
        "non_class": non_class,
        "places": places,
    }


def build_entries(course: dict, overrides: dict) -> list:
    """Repo entries for a course's assignments, in the repo's shape."""
    entries = []
    for assignment in course["assignments"]:
        name = plain_name(assignment["name"])
        group = course["groups"].get(assignment["assignment_group_id"]) or ""
        icon = render_assignments.ICONS[
            render_assignments.audience({"slug": slugify(name), "name": name, "group": group})]
        spots = course["places"].get(assignment["id"], [])
        home = overrides.get(name)
        if home is None and len(spots) == 1:
            home = spots[0]["class"]
        if home is None:
            where = ", ".join(sorted({s["class"] for s in spots})) or "no module"
            raise SystemExit(
                f"cannot place {name!r} ({where}): add a home_class_overrides "
                f"entry in {COURSE_YML.name}."
            )
        spot = next((s for s in spots if s["class"] == home), None)
        html = scrub(assignment.get("description") or "", where=name)
        entry = {
            "slug": slugify(name),
            "name": f"{icon} {name}",
            "group": course["groups"].get(assignment["assignment_group_id"]),
            "points": assignment.get("points_possible"),
            "due": assignment.get("due_at"),
            "submission_types": assignment.get("submission_types") or [],
        }
        if assignment.get("unlock_at") or assignment.get("lock_at"):
            entry["unlock"] = assignment.get("unlock_at")
            entry["lock"] = assignment.get("lock_at")
        entry["module_item"] = {
            "position": spot["position"] if spot else None,
            "section": spot["section"] if spot else None,
        }
        entry["description"] = f"assignments/{entry['slug']}.html"
        to_fix = []
        if not spots:
            to_fix.append(f"no module item in Canvas — add one in {home}")
        extra = sorted({s["class"] for s in spots} - {home})
        if extra:
            to_fix.append("module item also in " + ", ".join(extra) + " — remove the extra")
        if _CANVAS_FILE.search(html):
            to_fix.append("description links a Canvas file copy — move it into the repo (media pass)")
        if to_fix:
            entry["to_fix"] = to_fix
        entry["_home"] = home
        entry["_html"] = html
        entry["_cid"] = assignment["id"]
        entries.append(entry)
    entries.sort(key=lambda e: (e["module_item"]["position"] or 999, e["name"]))
    return entries


def repo_entries() -> dict:
    """Every assignment the repo already holds, keyed by slug."""
    out = {}
    for path in sorted(CLASSES.glob("class-*/assignments.yml")):
        for entry in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            entry["_class"] = path.parent.name
            out[entry["slug"]] = entry
    return out


AUTHORED_KEYS = ("summary", "week", "audience", "in_class")


def with_authored(entry: dict, before: dict) -> dict:
    """Merge the repo's display fields into a Canvas-derived entry."""
    if not before:
        return entry
    out = {}
    for key, value in entry.items():
        out[key] = value
        if key == "name":
            for authored in AUTHORED_KEYS:
                if authored in before:
                    out[authored] = before[authored]
    return out


def write_entries(entries: list, live_ids: dict) -> int:
    """Write the Canvas-derived entries, keeping repo-authored ones.

    Canvas owns the fields it exports; the repo owns the display fields
    (`AUTHORED_KEYS`) and any entry Canvas does not have (a reflection, say).
    A pull must not drop either.
    """
    existing = repo_entries()
    by_class = {}
    for entry in entries:
        entry = with_authored(entry, existing.get(entry["slug"]))
        by_class.setdefault(entry["_home"], []).append(entry)
    for slug, entry in existing.items():
        if slug not in live_ids:
            by_class.setdefault(entry.pop("_class"), []).append(entry)
    for group in by_class.values():
        group.sort(key=lambda e: ((e.get("module_item") or {}).get("position") or 999, e["name"]))
    written = 0
    for cls, group in sorted(by_class.items()):
        cls_dir = CLASSES / cls
        (cls_dir / "assignments").mkdir(exist_ok=True)
        for entry in group:
            if "_html" not in entry:
                continue  # repo-authored: its description is the repo's, not Canvas's
            (cls_dir / "assignments" / f"{entry['slug']}.html").write_text(
                entry["_html"], encoding="utf-8")
            written += 1
        payload = [{k: v for k, v in e.items() if not k.startswith("_")} for e in group]
        header = (
            f"# {cls} assignments — imported from Canvas by "
            f"tools/canvas-course/pull-assignments.py.\n"
            f"# The repo is the master copy of the content; edit here and push.\n"
        )
        (cls_dir / "assignments.yml").write_text(
            header + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100),
            encoding="utf-8",
        )
        written += 1
    return written


def read_ids() -> dict:
    if not IDS_YML.exists():
        return {}
    return yaml.safe_load(IDS_YML.read_text(encoding="utf-8")) or {}


def write_ids(course_id: str, modules: dict, assignments: dict) -> None:
    ids = read_ids()
    ids[str(course_id)] = {"modules": modules, "assignments": assignments}
    header = (
        "# Generated by pull-assignments.py — Canvas ids per course, by slug.\n"
        "# Ids change when a course is copied or rebuilt; the repo's identity is\n"
        "# the slug, and nothing else keys off these.\n"
    )
    IDS_YML.write_text(header + yaml.safe_dump(ids, sort_keys=False), encoding="utf-8")


def short_group(name: str | None) -> str:
    if not name:
        return "?"
    return {"Team": "Team", "Individual": "Ind", "Peer-": "Peer", "Reflections": "Refl"}.get(
        name.split()[0], name[:4])


def report(course_id: str, course: dict, entries: list) -> None:
    extra = ""
    if course["non_class"]:
        extra = f", {len(course['non_class'])} non-class module(s): " + ", ".join(course["non_class"])
    print(f"course {course_id}: {len(course['assignments'])} assignments, "
          f"{len(course['groups'])} groups, {len(course['modules'])} workshop modules{extra}")
    print()
    print(f"{'class':<9} {'place':<12} {'group':<5} {'pts':>4}  {'due':<10} name")
    for e in entries:
        place = f"pos {e['module_item']['position']}" if e["module_item"]["position"] else "—"
        print(f"{e['_home']:<9} {place:<12} {short_group(e['group']):<5} "
              f"{str(e['points']):>4}  {(e['due'] or '—')[:10]:<10} {e['name']}")
        for fix in e.get("to_fix", []):
            print(f"{'':<9} {'':<12} {'':<5} {'':>4}  {'':<10}   to fix: {fix}")


def check(course_id: str, course: dict, entries: list, repo: dict) -> tuple:
    drift, to_create, site_only = [], [], []
    live_slugs = {e["slug"] for e in entries}
    live_ids = {e["slug"]: e["_cid"] for e in entries}
    for slug in sorted(live_slugs - set(repo)):
        drift.append(f"in Canvas, not in repo: {slug}")
    for slug in sorted(set(repo) - live_slugs):
        if slug in live_ids:
            drift.append(f"in repo with a live id, not in Canvas: {slug}")
        elif repo[slug].get("source") == "schedule":
            site_only.append(slug)
        else:
            to_create.append(slug)
    for e in entries:
        r = repo.get(e["slug"])
        if not r:
            continue
        for field in ("name", "group", "points", "due", "unlock", "lock", "submission_types"):
            if e.get(field) != r.get(field):
                drift.append(f"{e['slug']}: {field} canvas={e.get(field)!r} repo={r.get(field)!r}")
        if e["_home"] != r["_class"]:
            drift.append(f"{e['slug']}: home class canvas={e['_home']} repo={r['_class']}")
        if e["module_item"] != r.get("module_item"):
            drift.append(f"{e['slug']}: module_item canvas={e['module_item']} repo={r.get('module_item')}")
        path = CLASSES / r["_class"] / (r.get("description") or "")
        if not path.exists():
            drift.append(f"{e['slug']}: description file missing ({path.relative_to(ROOT)})")
        elif path.read_text(encoding="utf-8") != e["_html"]:
            drift.append(f"{e['slug']}: description differs")
    live_ids = (read_ids().get(str(course_id)) or {}).get("assignments") or {}
    for e in entries:
        if live_ids.get(e["slug"]) != e["_cid"]:
            drift.append(f"{e['slug']}: canvas-ids has {live_ids.get(e['slug'])!r}, Canvas has {e['_cid']}")
    return drift, to_create, site_only


def record_ids(course_id: str, course: dict, repo: dict) -> int:
    by_name = {plain_name(e["name"]): e for e in repo.values()}
    assignments, unmatched = {}, []
    for a in course["assignments"]:
        entry = by_name.get(plain_name(a["name"]))
        if entry:
            assignments[entry["slug"]] = a["id"]
        else:
            unmatched.append(a["name"])
    modules = {cls: m["id"] for cls, m in course["modules"].items()}
    write_ids(course_id, modules, assignments)
    print(f"recorded {len(assignments)} assignment id(s) and {len(modules)} module id(s) "
          f"for course {course_id}")
    if unmatched:
        print("not in the repo (left out): " + "; ".join(unmatched))
    missing = sorted(set(repo) - set(assignments))
    if missing:
        print("in the repo but not in this course: " + ", ".join(missing))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="print the link table; change nothing")
    ap.add_argument("--check", action="store_true", help="compare the repo against Canvas; change nothing")
    ap.add_argument("--ids", metavar="COURSE_ID", help="record the ids of another course (e.g. the prototype)")
    args = ap.parse_args()

    spec = yaml.safe_load(COURSE_YML.read_text(encoding="utf-8"))
    live_id = str(spec["courses"]["live"])

    if args.ids:
        course = read_course(client_for(args.ids), spec["module_pattern"])
        return record_ids(str(args.ids), course, repo_entries())

    course = read_course(client_for(live_id), spec["module_pattern"])
    entries = build_entries(course, spec.get("home_class_overrides") or {})

    if args.report:
        report(live_id, course, entries)
        return 0

    if args.check:
        drift, to_create, site_only = check(live_id, course, entries, repo_entries())
        for line in drift:
            print(f"  drift: {line}")
        for slug in to_create:
            print(f"  to create in Canvas: {slug}")
        for slug in site_only:
            print(f"  not for Canvas (site-only): {slug}")
        print(f"\n{'drift found' if drift else 'repo matches Canvas'}"
              f" — {len(entries)} assignment(s) in course {live_id}"
              + (f", {len(to_create)} authored in the repo" if to_create else "")
              + (f", {len(site_only)} site-only" if site_only else ""))
        return 1 if drift else 0

    written = write_entries(entries, {e["slug"]: e["_cid"] for e in entries})
    write_ids(live_id, {cls: m["id"] for cls, m in course["modules"].items()},
              {e["slug"]: e["_cid"] for e in entries})
    print(f"imported {len(entries)} assignment(s) from course {live_id}: "
          f"{written} file(s) written, ids recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
