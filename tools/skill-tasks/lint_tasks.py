#!/usr/bin/env python3
"""Lint the task definitions.

A task file names check functions by string, so a renamed or mistyped check would
otherwise show up as `review` and quietly hand the work to a person. This makes
that a build failure instead.

    python3 check/lint_tasks.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tools/skill-tasks
REPO = HERE.parent.parent
CHECK = REPO / "skills" / "maker-tasks" / "check"
sys.path.insert(0, str(CHECK))

import checks  # noqa: E402
import runner  # noqa: E402

KNOWN_HUMAN_CHECKS = {"human_photo", "human_only"}

UNIT_KEYS = {
    "kind", "id", "title", "order", "summary", "requirement", "tasks",
    "supervised", "safety",
    # planned (not yet buildable) units declare what they will contain
    "status", "planned_tasks", "why", "needs",
}
TASK_REQUIRED = {"id", "title", "unit", "order", "video", "goal", "spec", "submit", "prereqs", "signoff", "criteria"}
CRITERION_KEYS = {"id", "title", "check", "args", "fail", "detail", "human", "review"}


def main() -> int:
    problems = []
    tasks = {}
    for path in sorted(runner.TASKS_DIR.glob("*.yml")):
        try:
            task = runner.load_task(path.stem)
        except runner.MissingDependency as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except runner.TaskError as exc:
            problems.append(f"{path.name}: cannot load ({exc})")
            continue
        tasks[task["id"]] = task
        if task.get("kind") == "unit":
            problems += _lint_unit(path.name, task, tasks)
        else:
            problems += _lint_task(path.name, task)

    # unit references resolve, and no cycles in prereqs
    for tid, task in tasks.items():
        for prereq in task.get("prereqs", []) or []:
            if prereq not in tasks:
                problems.append(f"{tid}: prereq '{prereq}' is not a task")
        for child in task.get("tasks", []) or []:
            if child not in tasks:
                problems.append(f"{tid}: lists '{child}', which is not a task")

    print(f"checked {sum(1 for t in tasks.values() if t.get('kind') != 'unit')} tasks "
          f"and {sum(1 for t in tasks.values() if t.get('kind') == 'unit')} unit(s)")
    if problems:
        print()
        for p in problems:
            print(f"  {p}")
        print(f"\n{len(problems)} problem(s).")
        return 1
    print("no problems.")
    return 0


def _lint_task(name, task) -> list:
    problems = []
    missing = TASK_REQUIRED - set(task)
    if missing:
        problems.append(f"{name}: missing {sorted(missing)}")
    if not isinstance(task.get("time"), str):
        problems.append(f"{name}: `time` must be quoted in YAML (\"1:48\" not 1:48, which YAML reads as 108)")
    seen = set()
    for crit in task.get("criteria", []):
        unknown = set(crit) - CRITERION_KEYS
        if unknown:
            problems.append(f"{name}: criterion '{crit.get('id')}' has unknown keys {sorted(unknown)}")
        cid = crit.get("id")
        if cid in seen:
            problems.append(f"{name}: duplicate criterion id '{cid}'")
        seen.add(cid)
        check = crit.get("check")
        if not check:
            if not crit.get("human"):
                problems.append(f"{name}: criterion '{cid}' has no check and is not marked human")
            continue
        module_name, _, func_name = check.partition(".")
        fn = getattr(checks, func_name, None) if module_name == "checks" else None
        if fn is None or not callable(fn):
            problems.append(f"{name}: criterion '{cid}' names a check that does not exist: {check}")
        elif func_name in KNOWN_HUMAN_CHECKS and not crit.get("human"):
            problems.append(f"{name}: criterion '{cid}' uses {func_name} without `human: true`")
    return problems


def _lint_unit(name, task, tasks) -> list:
    problems = []
    unknown = set(task) - UNIT_KEYS
    if unknown:
        problems.append(f"{name}: unknown keys {sorted(unknown)}")

    status = task.get("status", "active")
    if status not in ("active", "planned"):
        problems.append(f"{name}: status must be 'active' or 'planned', not {status!r}")

    if status == "planned":
        # A planned track is documentation: it names the tasks it will contain
        # but none of them exist yet, so it needs `planned_tasks` + `why`.
        if task.get("tasks"):
            problems.append(
                f"{name}: a planned unit must not list real `tasks` — those would "
                f"have to exist. Use `planned_tasks`."
            )
        if not task.get("planned_tasks"):
            problems.append(f"{name}: a planned unit must say what it will contain (`planned_tasks`)")
        if not task.get("why"):
            problems.append(f"{name}: a planned unit must say `why` it is planned")
    else:
        if not task.get("tasks"):
            problems.append(f"{name}: lists no tasks")

    return problems


if __name__ == "__main__":
    raise SystemExit(main())
