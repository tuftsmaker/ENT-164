# ENT-164 site and class decks — working agreement

Static course site for ENT-164 Intro to Making (Tufts), published from this repo
via GitHub Pages: https://tvande08.github.io/ENT-164/

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
  `https://tvande08.github.io/ENT-164/classes/class-01/ENT-164-Class-1-Introductions.pdf`.
  Pushing to `main` is the only sync step. Do not upload replacement PDFs.
- Canvas API token and base URL live in `~/esp32/canvas_config.py` (outside the
  repo). Never print, copy, commit, or echo the token.
- Module map (course 76330). Slides item ids below are Google Slides links until
  a class is converted; after converting, verify the Pages URL returns 200 with
  the expected byte size, then create an ExternalUrl item at the slides position
  and delete the old item (module item type cannot be changed in place):

  | Class | module id | slides item |
  |-------|-----------|-------------|
  | 1     | 314490    | 2151234 (ExternalUrl → Pages PDF, pos 2) |
  | 2     | 314491    | 2140686 |
  | 3     | 314492    | 2140693 |
  | 4     | 314493    | 2140699 |
  | 5     | 314494    | 2140704 |
  | 6     | 314495    | 2140711 |
  | 8     | 314496    | 2140716 |
  | 9     | 314497    | 2140722 |
  | 10    | 314498    | 2140726 |
  | 11    | 314499    | 2140731 |
  | 12    | 314500    | 2140733 |
  | 13    | 314501    | 2140736 |

- After any Canvas change, re-read the module items and confirm type, URL and
  position.

## Publishing

- Push to `main` publishes the site. After pushing, curl the live URL and check
  status/byte size before pointing Canvas at it.
- Intentionally unpublished: `slides/*.pptx` (source decks) and stray files
  (`TVdV.png`, `Profile (10).pdf`) stay untracked; do not include them.
- `.github/workflows/slides-sync.yml` exists locally but is not pushed yet: the
  `tvande08` GitHub token lacks the `workflow` scope (classic) / Workflows write
  permission (fine-grained). Once granted, commit and push it — it runs
  `scripts/build-class.sh --check --all` and fails on drift.

## Class web pages

- `classes/class-NN/index.html` is the hand-authored dark landing page, separate
  from the deck (it is not generated). Keep its links to `slides.html` and the
  PDF working, and update it when shared facts change (title, dates, TA info).
- Hub `index.html` and `syllabus/index.html` link to each class page; keep the
  "In-class decks" card counts (e.g. slide counts) accurate.
