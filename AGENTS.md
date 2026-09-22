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

## Tutorial videos (`tools/video-build/`)

Tutorial videos are built from a narration script plus **real browser
recordings** driven through `browser-control`. `tools/video-build/README.md` is
the manual; this is the contract.

- **Media never enters the repo.** Recordings, narration audio and intermediates
  go to the project's `workDir` (from `video.json`, default
  `~/Movies/ent164-onshape-tutorial/<slug>-build/`). Only scripts and config are
  committed.
- Pipeline: `tts -> align -> cards -> captions -> plan -> assemble`, with
  `./tools/video-build/record.sh <project>` driving the takes. Everything after
  `align` is deterministic given the recordings, so re-running is safe.
- **Scene timing is derived from the narration.** Take scripts pace themselves
  with `Beat` / `at(O, scene, sentence)` against the aligned sentence timings, so
  editing `script.json` and re-running `tts`+`align` retimes the scenes on its
  own — but the pacing is baked into the footage, so **re-record the affected
  takes**; do not just rebuild.
- Each take's setup must land its own starting state, so any take can be
  re-recorded alone: `./tools/video-build/record.sh <project> take04`.
- ffmpeg here has **no `drawtext`, `subtitles` or `ass`** (no freetype/libass).
  Captions and the title/end cards are rendered with PIL and composited with
  `overlay`. Do not reach for text filters.
- After `record.sh`, read the reported capture surface and content rectangle.
  Letterboxed captures are recovered automatically by `assemble`; a wrong *state*
  is not.
- Onshape specifics that are easy to get wrong: selecting a datum row only
  *highlights* it — the sketch plane is set only if the datum is selected
  **before** the Sketch tool; the green check **commits and closes** the sketch,
  so it must not be clicked until drawing is done; a right-*drag* orbits while a
  right-*click* opens a context menu.
- **If browser-control keeps dropping mid-record**, check in this order:
  `browser-control status` (extension connected? relay reachable?),
  then reload the extension via chrome://extensions, then recycle a wedged
  relay with `kill -9 <pid of cli.js serve>` — the next CLI call auto-starts a
  fresh one. A long-lived relay (many hours) tends to start rejecting executes
  while still answering `status`, and a session whose page was replaced will try
  to create a new target, which fails if the extension is mid-reconnect. Starting
  a fresh `session new` is cheaper than reusing a broken one. Recording needs
  five consecutive operations (setup, preflight, start, take, stop), so the
  connection has to hold for the whole take, not just one command.

## YouTube: uploads via API, credentials outside the repo (TuftsMaker)

- `scripts/upload-youtube.py` uploads a video to the channel with the YouTube
  Data API v3 (`videos.insert`, resumable). It defaults to `--privacy private`,
  does not notify subscribers, and reads the video back afterwards to report
  what YouTube actually did.
- `scripts/update-youtube.py` changes an existing video (`videos.update`):
  privacy (i.e. publishing a private upload), title, description, tags,
  thumbnail (`thumbnails.set`).
- `scripts/channel-youtube.py` reads or changes channel-level settings, currently
  the **made-for-kids** declaration (`--show`, `--made-for-kids`,
  `--not-made-for-kids`, `--sync-videos`). This channel must be **NOT made for
  kids**: the declaration is for content whose primary audience is *children*,
  and when set, YouTube disables comments, end screens, cards, notifications and
  personalised ads on every video. It was set by accident once and silently
  broke those features; keep it `False`. `--sync-videos` realigns videos whose
  stored declaration drifts from the channel's.
- **Custom thumbnails additionally require phone verification** of the channel
  (they are one of YouTube's "intermediate features"). Until that is done,
  `thumbnails.set` fails with a 403 whose message wrongly blames permissions —
  verify at https://www.youtube.com/verify, then re-run. This is unrelated to
  the made-for-kids setting and to OAuth scopes.
- Both share `scripts/_youtube_auth.py`. **Two tokens, one per purpose**, in
  `~/.config/tuftsmaker/`: `token-upload.json` (`youtube.upload` +
  `youtube.readonly`) and `token-manage.json` (`youtube.force-ssl` +
  `youtube.readonly`). They are separate because `videos.update` is *not*
  covered by `youtube.upload` — the API accepts only `youtube`,
  `youtube.force-ssl` or `youtubepartner` — and because one shared token would
  mean widening it breaks the other capability. The auth module checks a cached
  token's scopes and re-consents when one is missing, instead of failing later
  with a bare 403 "Insufficient Permission".
- OAuth client secret and tokens live in `~/.config/tuftsmaker/`
  (`youtube_config.py` + `client_secret.json` + the two token files, mode 0600,
  dir 0700). Outside the repo, same rule as the Canvas token: never print, copy,
  commit or echo them. The scripts load the config by absolute path, so no
  `PYTHONPATH` is needed.
- Dependencies are NOT installed in the system Python (mixing them there breaks
  the anaconda `streamlit`, which needs `protobuf<6`). Use the dedicated venv:
  `~/.venvs/ent164-youtube/bin/python scripts/upload-youtube.py ...`
  Run `--dry-run` to validate without uploading; it works without the venv.
- **The audit gate:** Google locks every upload from an API project that has not
  passed a compliance audit to *private* viewing mode — the upload succeeds and
  then cannot be made public. Until the project passes an audit
  (https://support.google.com/youtube/contact/yt_api_form), publish via YouTube
  Studio in the browser instead, or expect private-only. The script detects and
  warns about this after each upload.
- Quota: `videos.insert` has its own bucket of **100 calls/day at 1 unit each**
  (the old "1,600 units, ~6/day" figure is obsolete). Separately, a channel has
  a per-account daily upload cap (`uploadLimitExceeded`) that is lower for new
  or unverified channels.
- Source footage lives in `Photos/*.mp4` (untracked, unpublished). Do not commit
  video files to this repo.

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
- Skills are **student-facing**. Repo-internal build processes (the deck
  pipeline, `tools/video-build/`, the Canvas and YouTube scripts) do not belong
  here — they go in AGENTS.md and the tool's own README. A skill is distributed
  to student machines and publicly served, so publishing build tooling there
  only pushes irrelevant files at students.
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
- `add-class-tools/guide.html` is the fuller web version of that one-pager,
  with figures and its own A4 `add-class-tools-to-opencode.pdf`. Edit both
  together when the instructions change, and rebuild the guide PDF with
  headless Chrome (`--headless=new --no-pdf-header-footer
  --print-to-pdf=add-class-tools/add-class-tools-to-opencode.pdf`).

## Class web pages

- `assets/site.css` is the shared light theme for the hub, syllabus, about and
  class pages; `assets/guide.css` is the same theme for the guide pages (A4
  print). Both follow the slide decks' palette. Style pages through these
  files — do not reintroduce per-page `<style>` blocks.
- Photography on the site comes from the instructor's own class photos
  (`assets/photos/class/`, EXIF stripped before committing). Prefer these, and
  the deck photos in `classes/*/shots/`, over stock imagery.
- `classes/class-NN/index.html` is the hand-authored class landing page, separate
  from the deck (it is not generated). Keep its links to `slides.html` and the
  PDF working, and update it when shared facts change (title, dates, TA info).
- Hub `index.html` and `syllabus/index.html` link to each class page; keep the
  "In-class decks" card counts (e.g. slide counts) accurate.
