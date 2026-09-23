# Skill tasks — the maker qualification system

A CAP-style task system for maker skills: each **task** is a short video plus a
submission, checked against written criteria, and signed off by a person. A set
of signed tasks is a **qualification** (e.g. *Laser-Ready File*).

The pilot covers the six CAD/laser tasks behind the Onshape tips, using the
videos that already exist. Nothing new had to be filmed.

## Where everything lives

```
skills/maker-tasks/            ← SHIPPED TO STUDENTS (served by Pages, run locally)
  SKILL.md                       the instructions opencode loads
  check/                         the checker: DXF reader, checks, report, CLI
  tasks/*.yml                    the task definitions — the source of truth

tools/skill-tasks/             ← THE TA'S AND THE REPO'S TOOLS (not shipped)
  catalog/build.py               tasks/*.yml  ->  tasks/*.html
  catalog/map.py                 the task map: a generated SVG dependency graph
  canvas/sync.py                 create/update the Canvas assignments + rubric + module
  canvas/pull.py                 download submissions, run the checks, write reports
  canvas/ai_review.py            advisory notes (link + photo); never signs off
  canvas/apply.py                post the signoff, only after --reviewed
  lint_tasks.py                  every criterion names a check that exists
  selftest.py                    the fixture suite — checks the checker
  make_fixtures.py               regenerates fixtures/ from known answers
  fixtures/                      known-good and known-bad files, one per criterion

tasks/                         ← THE PUBLIC CATALOG (generated; served by Pages)
  index.html                     the task map, then the task list
  cad-NN-*.html                  one page per task
  unit-laser-ready.html          the qualification, with the same map
```

The YAML is the single source of truth: the public page a student reads, the
checker that runs on their file, the Canvas rubric, the TA's report and the
**task map** all come from it. Editing a task means editing one YAML file and
rebuilding.

## The task map

`tasks/index.html` opens with a picture of the whole qualification: the six
tasks laid out by dependency, then a band for the supervised cut and the
qualification itself. It is **generated** from `prereqs` in the task files
(`catalog/map.py`), so it cannot drift — add a task or change a prerequisite and
the next `catalog/build.py` redraws it. Each node links to its task page.

The bottom band is deliberately drawn differently from the tasks: the tasks are
files a checker can read, and the supervised cut is a person watching you cut at
Nolop. The map shows that boundary because it is the point of the whole design.

## The one rule

**Signoff is a human decision.** The checks say whether the *file* meets the
written criteria. They never assign a grade, and they never authorize using a
machine: "Laser-Ready File" means the file is ready, not that you may run the
laser — that stays with Nolop's own training and checkout.

This is enforced in the code, not just the prose:

- the report's verdict is `ready` or `fix`, never `qualified`;
- `review` is a first-class third state, so a task can declare that a person
  must look, and the checker cannot silently pass those criteria;
- `apply.py` refuses to post anything without `--reviewed`;
- `ai_review.py` writes suggestions with evidence and cannot change a verdict.

## Running it

### A student, in opencode

Nothing to install: the skill ships the checker. See `skills/maker-tasks/SKILL.md`.

```bash
python3 <skill>/check/check_submission.py --task cad-03-cut-a-hole ~/ent164/cad-03 --zip
```

### The TA

```bash
# 1. once per task: create the Canvas assignment, rubric and module entry
python3 tools/skill-tasks/canvas/sync.py --dry-run
python3 tools/skill-tasks/canvas/sync.py              # left UNPUBLISHED
python3 tools/skill-tasks/canvas/sync.py --publish    # when you are ready

# 2. per round: pull submissions and check them
python3 tools/skill-tasks/canvas/pull.py --task cad-03-cut-a-hole
python3 tools/skill-tasks/canvas/ai_review.py --task cad-03-cut-a-hole --all

# 3. read the reports, then post the signoffs
python3 tools/skill-tasks/canvas/apply.py --task cad-03-cut-a-hole --summary
python3 tools/skill-tasks/canvas/apply.py --task cad-03-cut-a-hole --reviewed --ready-only \
    --note "checked the link and the photo against the DXF"

# 4. after the class: rebuild the catalog after any task edit
python3 tools/skill-tasks/catalog/build.py
./tools/skill-publish/rebuild.sh
```

### Keeping it honest

```bash
python3 tools/skill-tasks/lint_tasks.py     # every criterion names a real check
python3 tools/skill-tasks/selftest.py       # every fixture gives the expected verdict
python3 tools/skill-tasks/catalog/build.py --check   # catalog matches the YAML
```

`selftest.py` is the important one. Each fixture folder carries a `fixture.json`
declaring what the report should say, so a change to a tolerance that silently
changes a verdict fails the suite instead of confusing a student. When a check
changes on purpose, the fixture's expectation changes in the same commit.

## How a task is defined

`skills/maker-tasks/tasks/cad-01-first-sketch.yml` is the reference. A task
declares the video, the goal, the exact files expected, and a list of criteria:

```yaml
  - id: dims
    title: It measures 100 × 60 mm
    check: checks.dxf_outer_dims
    args: { width: 100, height: 60, tol: 0.25 }
```

A criterion is one of three kinds:

- a **check** — `check: checks.<function>`, run on the file;
- a **human judgement** — `human: true`, always reported as `review`;
- a check that **reports but leaves the decision to a person** — e.g.
  `manifest_source_link`, which confirms a link is present but cannot know the
  document is the student's.

`fail:` on a criterion is the text a student sees when it fails; the check
usually supplies a better one of its own, with the numbers it measured.

## What the checks can and cannot see

Worth knowing before trusting a green report:

- **Onshape's DXF export has no unit header and no colours.** It is geometry on
  one layer. So `dxf_units_detect` reports what it found, and sizes are checked
  by measurement against the task's stated dimensions — which is what actually
  catches an export in inches (it reads ~25× too small).
- **Construction lines are not exported.** The centre-a-hole task is therefore
  checked by outcome (`dxf_circle_centred`), not by looking for construction
  geometry. `dxf_no_construction_lines` flags stray lines, which is a real
  problem (they get cut) but is reported for a person, not failed outright.
- **The file cannot prove authorship.** That is what the Onshape link and the
  supervised cut are for.
- **Colour and line width are an Inkscape step, not a DXF one.** Those belong to
  the laser-cutting guide; nothing here tries to check them.

## Adding a task

1. Add the video (reuse an Onshape tip, or build one with `tools/video-build/`).
2. Write `skills/maker-tasks/tasks/<id>.yml`, copying a neighbour.
3. Add fixtures: a good one and one per way it can go wrong.
4. `python3 tools/skill-tasks/lint_tasks.py`
5. `python3 tools/skill-tasks/selftest.py`
6. `python3 tools/skill-tasks/catalog/build.py`
7. `./tools/skill-publish/rebuild.sh` — otherwise students keep the old skill.
8. `python3 tools/skill-tasks/canvas/sync.py`, then publish when ready.

## Canvas notes

- The tasks sit in a **0-weight assignment group** and carry **0 points**: they
  record completion, not a grade. Feedback-only, by decision.
- Each task is one assignment with an **online-file-upload** submission type and
  a rubric whose rows are the criteria — the rubric assessment is the signoff
  record, in SpeedGrader, where a TA already works.
- The **module** "Skill tasks · Laser-ready file" is the qualification view: all
  six assignments complete means the six tasks are signed.
- The Canvas client is read-mostly by design. `sync.py` creates and updates;
  `pull.py` only reads; `apply.py` is the only writer of grades, and only with
  `--reviewed`.
- Credentials come from `~/.config/tuftsmaker/canvas_config.py` (outside the
  repo, mode 0600, dir 0700 — the same directory as the YouTube credentials).
  The token is never printed, copied or committed. `COURSE_ID` is accepted but
  ignored: the prototype is always the development target.

## Status

- Checker: 6 tasks, 21 fixtures, all agreeing.
- Catalog: 8 pages generated.
- Canvas: the group and module exist; assignments are created by `sync.py` and
  deliberately left unpublished until the pilot starts.
- AI tier: wired, guarded, and off unless `opencode` and `browser-control` are
  both present.
