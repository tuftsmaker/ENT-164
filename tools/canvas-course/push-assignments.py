#!/usr/bin/env python3
"""Push the repo's assignments to Canvas — the prototype first.

The repo is the master copy of the assignment content; this makes Canvas match
it: missing groups, missing assignments, changed fields, and module placement.
Canvas keeps what it owns — students, submissions, grades, `published`, and its
own description styling: descriptions are created, never overwritten.

Matching is by slug. `canvas-ids.yml` wins, an exact name match is adopted, and
anything else is created; the ids of whatever it creates are written back into
the map.

    python3 tools/canvas-course/push-assignments.py --dry-run     # show the plan
    python3 tools/canvas-course/push-assignments.py               # the prototype

Writes only ever go to the prototype; live needs CANVAS_ALLOW_LIVE=1 in the
environment *and* --i-know, and is refused otherwise.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import yaml  # noqa: E402
from canvas_client import (  # noqa: E402
    OVERRIDE_ENV,
    PROTOTYPE_COURSE,
    Client,
    load_config,
)

COURSE_YML = HERE / "course.yml"
IDS_YML = HERE / "canvas-ids.yml"
CLASSES = ROOT / "classes"


def entries_by_class():
    out = {}
    for path in sorted(CLASSES.glob("class-*/assignments.yml")):
        out[path.parent.name] = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return out


def description_of(cls, entry):
    relative = entry.get("description")
    if not relative:
        return ""
    path = CLASSES / cls / relative
    return path.read_text(encoding="utf-8") if path.exists() else ""


def field_diffs(canvas, entry, groups_by_name):
    """The fields the repo owns that differ from Canvas's copy."""
    out = {}
    if canvas["name"] != entry["name"]:
        out["name"] = (canvas["name"], entry["name"])
    group = groups_by_name.get(entry.get("group"))
    if entry.get("group") and group and canvas.get("assignment_group_id") != group["id"]:
        out["assignment_group_id"] = (canvas.get("assignment_group_id"), group["id"])
    if float(canvas.get("points_possible") or 0) != float(entry.get("points") or 0):
        out["points_possible"] = (canvas.get("points_possible"), entry.get("points"))
    for field, key in (("due_at", "due"), ("unlock_at", "unlock"), ("lock_at", "lock")):
        if canvas.get(field) != entry.get(key):
            out[field] = (canvas.get(field), entry.get(key))
    if sorted(canvas.get("submission_types") or []) != sorted(entry.get("submission_types") or []):
        out["submission_types"] = (canvas.get("submission_types"), entry.get("submission_types"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--course", default=PROTOTYPE_COURSE,
                    help=f"Canvas course id (default {PROTOTYPE_COURSE}, the prototype)")
    ap.add_argument("--i-know", action="store_true",
                    help=f"allow a push to the live course (same gate as {OVERRIDE_ENV}=1)")
    args = ap.parse_args()

    spec = yaml.safe_load(COURSE_YML.read_text(encoding="utf-8"))
    target = str(args.course)
    live = str(spec["courses"]["live"])
    if target == live and not (args.i_know or os.environ.get(OVERRIDE_ENV) == "1"):
        sys.exit(f"refusing to push to the live course {live}: "
                 f"pass --i-know or set {OVERRIDE_ENV}=1")

    cfg = load_config()
    cfg["course_id"] = target
    client = Client(**cfg)
    print(f"course {target}: acting as {client.whoami().get('name', '?')}")

    per_class = entries_by_class()
    entries = [(cls, e) for cls, group in per_class.items() for e in group
               if e.get("source") != "schedule"]

    ids = yaml.safe_load(IDS_YML.read_text(encoding="utf-8")) if IDS_YML.exists() else {}
    course_ids = ids.setdefault(target, {})
    id_by_slug = course_ids.setdefault("assignments", {})
    module_ids = course_ids.setdefault("modules", {})

    groups = {g["name"]: g for g in client.get(f"/courses/{target}/assignment_groups")}
    assignments = {a["id"]: a for a in client.get(f"/courses/{target}/assignments")}
    by_name = {a["name"]: a for a in assignments.values()}

    plan = {"groups": [], "create": [], "update": [], "add_items": [], "drop_items": []}

    for name in spec["groups"]:
        if name not in groups:
            plan["groups"].append(name)

    resolved = []
    for cls, entry in entries:
        aid = id_by_slug.get(entry["slug"])
        found = assignments.get(aid) if aid else by_name.get(entry["name"])
        if found and id_by_slug.get(entry["slug"]) != found["id"]:
            id_by_slug[entry["slug"]] = found["id"]  # adopted by name; record it
        resolved.append((cls, entry, found))
        if found:
            diffs = field_diffs(found, entry, groups)
            if diffs:
                plan["update"].append((cls, entry, found, diffs))
        else:
            plan["create"].append((cls, entry))

    placed = {}
    for module_id in module_ids.values():
        for item in client.module_items(module_id):
            if item["type"] == "Assignment":
                placed.setdefault(item.get("content_id"), []).append((module_id, item))
    for cls, entry, found in resolved:
        module_id = module_ids.get(cls)
        if not module_id:
            continue
        here = [] if not found else [i for i in placed.get(found["id"], []) if i[0] == module_id]
        elsewhere = [] if not found else [i for i in placed.get(found["id"], []) if i[0] != module_id]
        if not here:
            plan["add_items"].append((cls, entry))
        plan["drop_items"] += elsewhere

    print(f"\nplan:")
    for name in plan["groups"]:
        print(f"  + group {name}")
    for cls, entry in sorted(plan["create"], key=lambda x: x[1]["name"]):
        print(f"  + assignment {entry['slug']} ({cls}, {entry.get('group')})")
    for cls, entry, found, diffs in sorted(plan["update"], key=lambda x: x[1]["name"]):
        changes = ", ".join(f"{k}: {v[0]!r} -> {v[1]!r}" for k, v in sorted(diffs.items()))
        print(f"  ~ assignment {entry['slug']}: {changes}")
    for cls, entry in sorted(plan["add_items"], key=lambda x: x[1]["name"]):
        print(f"  + {cls} module item: {entry['name']}")
    for module_id, item in plan["drop_items"]:
        print(f"  - module {module_id} item: {item['title']}")
    total = sum(len(v) for v in plan.values())
    if not total:
        print("  nothing to do — Canvas matches the repo")
        return 0

    if args.dry_run:
        print("\nnothing written (--dry-run)")
        return 0

    for index, name in enumerate(spec["groups"], start=1):
        if name in groups:
            continue
        # Canvas's assignment-group create takes flat params, not a hash.
        groups[name] = client.post(f"/courses/{target}/assignment_groups",
                                   name=name, position=index)
    created = {}
    for cls, entry in plan["create"]:
        body = {
            "name": entry["name"],
            "description": description_of(cls, entry),
            "points_possible": entry.get("points"),
            "due_at": entry.get("due"),
            "submission_types": entry.get("submission_types") or [],
            "published": False,
        }
        group = groups.get(entry.get("group"))
        if group:
            body["assignment_group_id"] = group["id"]
        if entry.get("unlock"):
            body["unlock_at"] = entry["unlock"]
        if entry.get("lock"):
            body["lock_at"] = entry["lock"]
        assignment = client.post(f"/courses/{target}/assignments", assignment=body)
        created[entry["slug"]] = assignment["id"]
        id_by_slug[entry["slug"]] = assignment["id"]
        print(f"  + created {entry['slug']} ({assignment['id']})")
    for cls, entry, found, diffs in plan["update"]:
        body = {key: value[1] for key, value in diffs.items()}
        client.put(f"/courses/{target}/assignments/{found['id']}", assignment=body)
        print(f"  ~ updated {entry['slug']} ({', '.join(sorted(diffs))})")
    for cls, entry in plan["add_items"]:
        aid = id_by_slug.get(entry["slug"]) or created.get(entry["slug"])
        if not aid:
            found = by_name.get(entry["name"])
            aid = found["id"] if found else None
        if not aid:
            print(f"  ? {entry['slug']}: no assignment id, item not added")
            continue
        client.add_module_item(module_ids[cls], type="Assignment", content_id=aid,
                               title=entry["name"])
        print(f"  + {cls} module item: {entry['name']}")
    for module_id, item in plan["drop_items"]:
        client._request("DELETE", f"/courses/{target}/modules/{module_id}/items/{item['id']}")
        print(f"  - module {module_id} item: {item['title']}")

    IDS_YML.write_text(
        "# Generated by pull-assignments.py — Canvas ids per course, by slug.\n"
        "# Ids change when a course is copied or rebuilt; the repo's identity is\n"
        "# the slug, and nothing else keys off these.\n"
        + yaml.safe_dump(ids, sort_keys=False),
        encoding="utf-8",
    )
    print(f"\npushed to course {target}; ids recorded in {IDS_YML.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
