# ENT-164 site and class decks — working agreement

Static course site for ENT-164 Intro to Making (Tufts), published from this repo
via GitHub Pages: https://tuftsmaker.github.io/ENT-164/

## Deck sync: one source, generated PDFs

- `classes/class-NN/slides.html` (+ its `shots/`, plus shared `assets/`) is the
  single source of truth for a class deck. The PDF is a generated artifact and
  must never be edited by hand.
- After any slide or image edit, rebuild before committing:
  `scripts/build-class.sh class-01` (or `--all`). This regenerates the PDF next
  to `slides.html` and records a source hash in `classes/class-NN/slides.buildinfo`.
- Commit `slides.html`, `shots/`, the PDF and `slides.buildinfo` together.
- `scripts/build-class.sh --check --all` verifies every committed PDF matches
  its sources (also the CI check, see below). Chrome is autodetected; override
  with `CHROME_BIN`. Print flags: `--headless=new --no-pdf-header-footer
  --print-to-pdf=... --virtual-time-budget=12000`.

## Canvas: links only, never copies (course 76330, Fa26-ENT-0164-01)

- Canvas never stores a deck copy. Each class module has an **ExternalUrl** item
  at the slides position pointing at the Pages PDF, e.g. Class 1 →
  `https://tuftsmaker.github.io/ENT-164/classes/class-01/ENT-164-Class-1-Introductions.pdf`.
  Pushing to `main` is the only sync step. Do not upload replacement PDFs.
- Canvas API token and base URL live in `~/esp32/canvas_config.py` (outside the
  repo). Never print, copy, commit, or echo the token.
- Module map (course 76330). Converted classes point at their Pages PDF; the
  rest still point at Google Slides. After converting a class, verify the Pages
  URL returns 200 with the expected byte size, then create an ExternalUrl item
  at the slides position and delete the old item (module item type cannot be
  changed in place):

  | Class | module id | slides item |
  |-------|-----------|-------------|
  | 1     | 314490    | 2151234 (ExternalUrl → Pages PDF) |
  | 2     | 314491    | 2151268 (ExternalUrl → Pages PDF) |
  | 3     | 314492    | 2140693 (Google Slides — no source pptx yet) |
  | 4     | 314493    | 2151269 (ExternalUrl → Pages PDF) |
  | 5     | 314494    | 2151270 (ExternalUrl → Pages PDF) |
  | 6     | 314495    | 2151271 (ExternalUrl → Pages PDF) |
  | 8     | 314496    | 2140716 (Google Slides — no source pptx yet) |
  | 9     | 314497    | 2151272 (ExternalUrl → Pages PDF) |
  | 10    | 314498    | 2140726 (Google Slides — Smart Devices; no source pptx yet) |
  | 11    | 314499    | 2151273 (ExternalUrl → Pages PDF) |
  | 12    | 314500    | 2140733 (Google Slides — no source pptx yet) |
  | 13    | 314501    | 2140736 (Google Slides — no source pptx yet) |

  Note: the source file `ENT-164 Class 10 - Intelligent Devices with AI.pptx`
  is the deck for **Class 11** (syllabus Week 11, Thu Nov 19) — module 314499.
  Class 10 "Smart Devices" still has no source deck.

## Converting another class deck

1. `python3 scripts/extract-pptx.py "slides/ENT-164 Class N - ....pptx" /tmp/class-N`
   — writes per-slide text (charts included), notes, media, and a contact sheet.
2. Author `classes/class-NN/slides.html` + `index.html` + `shots/`, using
   `classes/class-01` as the design reference (same `<style>`, same patterns).
3. Build: `PDF_NAME=ENT-164-Class-N-<Slug>.pdf scripts/build-class.sh class-NN`.
4. Add the class to the hub "In-class decks" cards and the syllabus week chip;
   run `scripts/build-class.sh --check --all`; commit and push.
5. Once Pages serves the PDF (curl 200 + byte size), repoint the Canvas module
   item per the table above and update this file.

- After any Canvas change, re-read the module items and confirm type, URL and
  position.

## Publishing

- Push to `main` publishes the site. After pushing, curl the live URL and check
  status/byte size before pointing Canvas at it.
- Intentionally unpublished: `slides/*.pptx` (source decks) and stray files
  (`TVdV.png`, `Profile (10).pdf`) stay untracked; do not include them.
- `.github/workflows/slides-sync.yml` runs `scripts/build-class.sh --check --all`
  on pushes and PRs touching `classes/`, `assets/` or `scripts/`, and fails when
  a committed PDF drifts from its sources. It does not block Pages deploys, so a
  red run means: rebuild the PDF, commit, push again.

## Class skills for opencode (`skills/`)

- `skills/` is served by Pages at `https://tuftsmaker.github.io/ENT-164/skills/`
  and consumed by opencode via `skills.urls`. `skills/` is the **source of
  truth** — there is no separate source tree; edit in place.
- opencode re-downloads a skill only when its `version` changes, and the version
  is a hash of the skill's contents. So after editing anything under `skills/`:
  run `tools/skill-publish/rebuild.sh`, then commit and push. Editing without
  rebuilding means students silently keep the old copy.
- Never hand-edit `skills/index.json`. `rebuild.sh` derives the file list and
  version from the directory; a hand-edited index will not match what is served.
- **`.nojekyll` at the repo root is load-bearing.** Without it Pages runs Jekyll
  over `skills/`, which converts `maker/SKILL.md` to HTML (so the `.md` 404s) and
  skips `bbd/__init__.py` because it starts with an underscore. Do not delete it.
- Failures are silent — a 404ing file just means the skill never appears, with
  only a log line on the student's machine. After pushing, curl `index.json` and
  confirm every listed file returns 200 (see `tools/skill-publish/README.md`).
- `handouts/add-class-tools.html` is the student-facing one-pager; rebuild its
  PDF with headless Chrome after editing. It is US Letter and must stay on one
  page — check with `pdftotext -f 2 -l 2 ...` (anything printed = it spilled).

## Class web pages

- `classes/class-NN/index.html` is the hand-authored dark landing page, separate
  from the deck (it is not generated). Keep its links to `slides.html` and the
  PDF working, and update it when shared facts change (title, dates, TA info).
- Hub `index.html` and `syllabus/index.html` link to each class page; keep the
  "In-class decks" card counts (e.g. slide counts) accurate.
