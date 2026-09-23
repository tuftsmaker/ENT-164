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

## Syllabus: one source, generated PDF

- **`syllabus/index.html` is the single source of truth for the syllabus, and the
  PDF is generated from it.** There is no separate hand-authored syllabus
  document any more; the old one drifted from the page (it still described
  weekly reflections and "Spring 2026" long after both had changed) and was
  removed. Never edit the PDF.
- After any syllabus edit: `scripts/build-syllabus.sh` regenerates
  `syllabus/ENT-164-Syllabus-Fall-2026.pdf` and records
  `syllabus/syllabus.buildinfo`. Commit page, PDF and buildinfo together.
  `scripts/build-syllabus.sh --check` is the CI check.
- Both scripts print with the same headless-Chrome flags and share the
  bookkeeping in `scripts/pdf_buildinfo.py`. `--all` for build-class.sh means
  every deck and only decks; the syllabus is a separate `--check` so a failure
  names the one stale document.
- **The print layout is CSS, in `assets/site.css` under `@media print`, scoped to
  `.page-syllabus`.** Because the PDF is printed straight from the web page,
  that block is what makes it a document: US Letter, sidebar/hero-CTA/footer
  hidden, cards and weeks kept whole across breaks. The `.reveal` fade-in must
  stay disabled there — those elements start at `opacity: 0` and a print render
  can catch them invisible.
- The syllabus page loads `assets/site.css`, so **any change to that shared
  stylesheet invalidates the syllabus PDF** (and every deck whose PDF references
  an asset that changed). Rebuild both after touching the theme.
- **A pre-commit hook does the rebuilding, so it cannot be forgotten.** Run
  `scripts/install-git-hooks.sh` once per clone (it sets `core.hooksPath` to the
  tracked `scripts/git-hooks/`). The hook calls
  `scripts/rebuild-staged-pdfs.py`, which finds the documents the staged changes
  invalidate, rebuilds each, and stages the PDF and buildinfo. `--dry-run` on
  that script reports without changing anything. Bypass a commit with
  `git commit --no-verify`; the failure mode it prevents is a commit whose PDF
  disagrees with its page, which CI catches but Pages still deploys.
  - It uses the same dependency rule as the source hash (page + image tree +
    referenced `assets/` files), so a `site.css` change rebuilds the syllabus and
    not the decks, and a logo change rebuilds every deck that embeds it.
  - Git does not version `.git/hooks`, which is why the hook lives in
    `scripts/git-hooks/` and is wired up by the installer.

## Canvas: links only, never copies (course 76330, Fa26-ENT-0164-01)

- Canvas never stores a deck copy. Each class module has an **ExternalUrl** item
  at the slides position pointing at the Pages PDF, e.g. Class 1 →
  `https://tuftsmaker.github.io/ENT-164/classes/class-01/ENT-164-Class-1-Introductions.pdf`.
  Pushing to `main` is the only sync step. Do not upload replacement PDFs.
- Canvas credentials live in `~/.config/tuftsmaker/canvas_config.py` (outside the
  repo, mode 0600, dir 0700 — the same directory as the YouTube credentials).
  Never print, copy, commit, or echo the token. `COURSE_ID` in that file is
  accepted but ignored: development targets the prototype (see the skill-tasks
  section below).
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

- **Media never enters the repo — except the finished tips.** Recordings,
  narration audio and intermediates go to the project's `workDir` (from
  `video.json`, default `~/Movies/ent164-onshape-tutorial/<slug>-build/`). Only
  scripts and config are committed. The one exception is the *rendered* Onshape
  tips: the class hosts them itself, so each finished MP4 is copied to
  `onshape-tips/videos/<slug>.mp4` with its title card as
  `onshape-tips/posters/<slug>.png`, and committed. They are small — the set is
  ~19MB, because 1080p captures of a mostly static application window compress
  well — and self-hosting avoids both the platform upload cap and any
  dependency on it. When a tip is re-rendered, copy the new file over the old
  one; git keeps the history, so the repo grows by the size of a rebuild each
  time.
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
  right-*click* opens a context menu. The **Construction toggle resets when the
  tool is escaped**, so a second construction line needs it set again or it is
  drawn as real geometry — and the laser cuts it.
- **Exporting the DXF** (take02 of `basic-rectangle`): right-click the
  *committed* sketch in the feature list — an open sketch has no context menu —
  and choose `Export as DXF/DWG…`. The dialog defaults to DXF, millimetre units
  and Download; press **Export**. It saves to the browser's download folder, so
  the recording shows the dialog rather than a file picker.
- Setups resolve their project through `/tmp/vid/vb-paths.json`, which **only
  `record.sh` writes**. Running a setup by hand without refreshing that pointer
  silently runs it against whichever project ran last — worth remembering when
  probing.
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
- **The legacy tip re-shoots are nearly done.** Under
  `tools/video-build/projects/onshape-tips/`, these have a `documentUrl`, a
  setup, a take and a finished MP4: `updating-dimensions`, `circle-to-cut-a-hole`,
  `trim-tool`, `mirroring-entities`, `circle-on-a-corner`, `basic-rectangle` and
  `circle-in-the-center`. Still to do (narration, cards and captions are ready,
  no document/setup/take yet): `workspace-overview`, whose narration still
  describes the Create-a-document flow — a take cannot show that, because
  Onshape opens the new document in a new tab — so it needs a re-tightened
  script; and `laser-cut-joints`, whose recovered narration is 68 words for a
  5:17 original, so it needs writing rather than tightening.

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
- **`~/.config/tuftsmaker/` is the one place class secrets live** — outside any
  project directory, mode 0600 for files and 0700 for the directory. It holds the
  YouTube credentials (`youtube_config.py` + `client_secret.json` + the two token
  files) and the Canvas one (`canvas_config.py`). Never print, copy, commit or
  echo any of them; add new secrets here rather than inventing another folder.
  Delete `__pycache__` if it appears: the directory is 0700 but the cache it
  creates is not, and byte-compiled secrets are pure liability. The scripts load
  their configs by absolute path, so no `PYTHONPATH` is needed.
- Dependencies are NOT installed in the system Python (mixing them there breaks
  the anaconda `streamlit`, which needs `protobuf<6`). Use the dedicated venv:
  `~/.venvs/ent164-youtube/bin/python scripts/upload-youtube.py ...`
  Run `--dry-run` to validate without uploading; it works without the venv.
- **The audit gate:** Google locks every upload from an API project that has not
  passed a compliance audit to *private* viewing mode — the upload succeeds and
  then cannot be made public. Until the project passes an audit
  (https://support.google.com/youtube/contact/yt_api_form), publish via YouTube
  Studio in the browser instead, or expect private-only. The script detects and
  warns about this after each upload. **As of Sept 2026 this project is not
  gated:** `update-youtube.py <id> --privacy public` took effect immediately and
  the oEmbed endpoint confirmed it, so try the API first and only fall back to
  Studio. `--thumbnail` also works (phone verification is done).
- `scripts/playlist-youtube.py` creates or fills a playlist (the `manage`
  token — playlist edits are not covered by `youtube.upload`). Re-running with
  the same `--playlist` adds only what is missing, so it is safe after a new
  video lands.
- The seven finished Onshape tips are published on the TuftsMaker channel
  (@TuftsMaker) and collected in the public "Onshape Tips" playlist:
  https://www.youtube.com/playlist?list=PLQNuQi1_2lXk — basic-rectangle,
  updating-dimensions, circle-to-cut-a-hole, circle-in-the-center,
  circle-on-a-corner, mirroring-entities, trim-tool, in that order.
- Quota: `videos.insert` has its own bucket of **100 calls/day at 1 unit each**
  (the old "1,600 units, ~6/day" figure is obsolete). Separately, a channel has
  a per-account daily upload cap (`uploadLimitExceeded`) that is lower for new
  or unverified channels. **It is the binding limit, not the API quota:** nine
  uploads in a morning was enough to hit it, and the next attempt fails with
  "this channel has hit YouTube's per-channel daily upload cap". Spread uploads
  over days, or verify the channel. Thumbnails have their own limiter too —
  setting several in a row returns `429 uploadRateLimitExceeded`; wait and
  retry rather than assuming the thumbnail is broken.
- `scripts/delete-youtube.py <id>` removes a video (`--yes` to confirm; it prints
  title, views and privacy first). Deleting is permanent and also drops the
  video from any playlist.
- **`scripts/sync-youtube-series.py` is how the tips get (re)published.** It
  reads the video-build projects, uploads whatever is not on the channel yet,
  publishes it, sets its title card as the thumbnail, and records the id in
  `onshape-tips/youtube.json`. Because the upload cap interrupts a batch, it is
  built to be re-run: it skips what is already up and stops at the cap.
  `--prune` deletes superseded uploads (only for slugs whose replacement is
  published, so it can never empty the channel), and `--rebuild-playlist`
  recreates the playlist in teaching order.
  ```bash
  scripts/sync-youtube-series.py --dry-run
  scripts/sync-youtube-series.py                     # repeat until it stops saying "capped"
  scripts/sync-youtube-series.py --prune --rebuild-playlist
  ```
- The title and end cards use the **class website's light theme**, not the dark
  deck palette, and the heading auto-fits to one line: six of the nine tips had
  headings too long for a fixed size and ran off the sides of the card, in the
  title slide *and* in the thumbnail. If you add a tip, just check the card.
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
  with figures and its own US Letter `add-class-tools-to-opencode.pdf`. Edit both
  together when the instructions change, and rebuild the guide PDF with
  headless Chrome (`--headless=new --no-pdf-header-footer
  --print-to-pdf=add-class-tools/add-class-tools-to-opencode.pdf`).
- **Guide pages are US Letter, not A4.** The class is at a US university and
  students print these. `assets/guide.css` sets `@page { size: Letter }` and
  sizes the on-screen page column to 215.9mm; the `.cover` height is 279.4mm
  and must stay equal to the Letter content height, or the cover spills onto a
  blank second page. If you change the page size, change all three together and
  rebuild **every** guide PDF — `add-class-tools`, both `opencode-deepseek-guide-*`
  and `laser-cutting` are all built from that one stylesheet. Verify with
  `pdfinfo <pdf> | grep 'Page size'` (expect `612 x 792 pts (letter)`).
- `laser-cutting/guide.html` is the Nolop laser-cutting walkthrough (Inkscape →
  UCP → cut), built on the official Nolop Makerspace guide. Its `shots/`
  contains screenshots reused from that guide under CC BY-SA, with credit kept
  in the page footer — retain the attribution if you move or reuse them.
  Class 3's deck and page draw their Inkscape/UCP screenshots from here, so
  editing a shot means copying it into `classes/class-03/shots/` too.

## Onshape tips (the video series)

- The series lives at `onshape-tips/index.html`, served from this repo like any
  other page, with the videos in `onshape-tips/videos/` and their title cards as
  posters. It is linked from the hub's walkthroughs section and from class 3.
- Rebuild the page if the set changes: it is generated from each project's
  `video.json` (heading + subtitle) plus the file's duration, in the teaching
  order workspace-overview, basic-rectangle, updating-dimensions,
  circle-to-cut-a-hole, circle-in-the-center, circle-on-a-corner,
  mirroring-entities, trim-tool, laser-cut-joints.
- Publishing here is just a push — no upload cap, and a re-render is one commit.
  The same videos are also on the TuftsMaker channel; the site does not depend
  on that.

## Maker skill tasks (`tools/skill-tasks/`, `skills/maker-tasks/`, `tasks/`)

A CAP-style task system for maker skills: a task is a short video, a file the
student makes, written criteria checked on that file, and a signoff by a person.
The **Laser-Ready File** track is open (9 tasks; the first eight reuse the
Onshape tips as task videos, and the ninth — preparing the DXF for the laser —
uses the class's Inkscape tutorial). Four further tracks — Print-Ready
Model, Working Circuit, Connected Device, Intelligent Device — exist as
`status: planned` units: documentation of what they will contain, shown dimmed on
the site and refused by the runner. A planned unit uses `planned_tasks` (no real
tasks) plus `why` and `needs`, and `lint_tasks.py` enforces that split.

- **One source of truth: `skills/maker-tasks/tasks/*.yml`.** The public page, the
  checker, the Canvas rubric and the TA report all come from it. Change a task
  there, then rebuild all three:
  ```bash
  python3 tools/skill-tasks/lint_tasks.py        # criteria name real checks
  python3 tools/skill-tasks/selftest.py          # fixtures still agree
  python3 tools/skill-tasks/catalog/build.py     # tasks/*.html
  ./tools/skill-publish/rebuild.sh               # students' copy of the skill
  ```
  `selftest.py` is the load-bearing one: each fixture in
  `tools/skill-tasks/fixtures/` declares in its own `fixture.json` what the
  report should say. Change a tolerance and a fixture disagrees, on purpose.
- **The task map is generated, not drawn** (`catalog/map.py`): a dependency graph
  laid out in columns by each task's depth, plus a band for the supervised cut
  and the qualification. Add a task, or point a `prereqs` at a different task,
  and the map redraws on the next `catalog/build.py` — there is nothing to keep
  in step by hand. It appears on `tasks/index.html` and on the qualification
  page, and each node links to its task.
- **Quote a `time` in YAML.** `time: 1:48` is a sexagesimal integer to YAML and
  arrives as `108`. `lint_tasks.py` fails on an unquoted one; keep them quoted.
- **The checker ships inside the skill** (`skills/maker-tasks/check/`), because a
  student's opencode has no checkout of this repo. Keep the two halves in step:
  the skill runs the checks, `tools/skill-tasks/` drives Canvas and builds pages.
  Never let a repo-only import creep into `skills/maker-tasks/check/`.
- **Signoff is human, and the code enforces it.** A report's verdict is `ready`
  or `fix`, never `qualified`; `review` is a third state for criteria a person
  must judge; `canvas/apply.py` posts nothing without `--reviewed`; the AI tier
  (`canvas/ai_review.py`) writes advisory notes with evidence and cannot change
  a verdict. The qualification means *the file is ready* — running the laser
  stays with Nolop's own checkout, and that separation is deliberate.
- **What the checks can see.** Onshape's DXF export has **no unit header and no
  colours** — it is geometry on one layer, and construction lines are not
  exported at all. So sizes are checked by measurement against the task's stated
  dimensions (an inch export reads ~25× too small), and centring is checked by
  outcome rather than by looking for construction geometry. The *checks* stay
  colour-blind; the one thing that writes colour is the converter below.
- **`check/laser_svg.py` writes the laser-ready SVG, and hairline is a trap.**
  `cli.py --svg` (or the module alone) turns any checked DXF into pure-red
  (`#ff0000`), unfilled, hairline cut paths — the colours UCP reads (see the
  laser-cutting guide). It is stdlib-only, like the rest of the checker, so it
  needs no Inkscape installed.
  - The obvious `stroke-width="hairline"` is **wrong**: Inkscape does not read
    it as the UI's Hairline and falls back to **1 mm**, exactly the thick line
    the guide warns makes the laser fire twice (measured: 1.016 mm vs 0.042 mm).
    Inkscape's own serialisation is three declarations together —
    `stroke-width:1px;vector-effect:non-scaling-stroke;-inkscape-stroke:hairline`
    — and that string is what the converter writes. Keep all three.
  - An **arc's page box** must come from its endpoints plus only the axis
    crossings the sweep passes through. Using the whole circle's box pads the
    page around geometry that is not there (112×60 became 112×87 and shifted the
    part down). Verified by rasterising the converted SVG and comparing inked
    pixels against the DXF's own tessellation, arc sweep direction included.
  - DXF is Y-up and SVG is Y-down, so the Y-flip mirrors the drawing: a CCW CAD
    arc stays CCW on screen, which is SVG `sweep-flag 0`.
  - It reports rather than hides: spline/ellipse approximations, polyline bulge
    vertices, and geometry on unexpected layers are all printed.
- **Canvas writes stop at the prototype. This is enforced in code, not by habit.**
  `canvas_client._guard` refuses any POST/PUT/DELETE that is not aimed at course
  **71548, "Intro to Making Prototype"** — including the case where a client was
  *constructed* for the live course, which is precisely the mistake it exists to
  catch. Reads pass through, so comparing against the live course still works.
  - `load_config()` returns the prototype regardless of the config's `COURSE_ID`,
    because a stale or copied config must not decide which course tools touch.
  - The single escape hatch is `CANVAS_ALLOW_LIVE=1` in the environment. It is
    deliberately not a bare CLI flag, so reaching the live course is a decision
    rather than a typo. `populate.py --i-know` is the same gate.
  - `python3 tools/skill-tasks/canvas/test_guard.py` proves it offline: 12 cases,
    no network, covering writes, deletes, rubrics, grades, account-level routes
    and the override. **Run it after touching the client.**
  - Why it is our job: Canvas token scopes cannot do this. Scopes restrict which
    *endpoints* a token may call, and `:course_id` in a scope is a path
    placeholder, not a filter — there is no syntax for pinning a course. Personal
    access tokens (what we have) are unscoped and inherit the user's full
    permissions across all their courses.
- **Canvas** (course 76330, the live course): a 0-weight group "Skill tasks (not
  graded)", one assignment per task with a rubric whose rows are the criteria.
  All of it is **feedback-only** — 0 points, by decision, this semester. The
  task tools create and leave assignments **unpublished** unless given
  `--publish`. Everything is developed against the prototype first.
- **Modules are classes, and only classes. Tasks are assignments.** The tasks are
  grouped by *assignment category* — the "Skill tasks (not graded)" group — and
  deliberately not by a module, which is the class structure. `sync.py` no longer
  creates one.
- **All the Canvas tools take `--course`**, defaulting to the prototype:
  `sync.py`, `apply.py`, `pull.py` (the skill-task loop) and `populate.py`.
  `apply.py` is the one that writes student records, so being able to rehearse it
  on the prototype matters most.
- `tools/canvas-course/populate.py` builds the course structure from the site:
  one module per class, with the deck PDF, the class page, and the site content
  that belongs to that class (the setup guides with Class 1, the tips and the
  cutting guide with Class 3). Links only, never copies. `--prune` clears modules
  outside the plan and assignments the task sync does not own, and refuses to run
  against the live course without `--i-know` (the same gate as
  `CANVAS_ALLOW_LIVE=1`). Canvas creates modules and items
  unpublished; publishing a module publishes its items with it.
- `sync.py --dry-run` used to call `ensure_group()`/`ensure_module()`, which
  create on the way, so a dry run wrote to Canvas. Both dry runs now only look.
- Student submissions live in Canvas and in the TA's `~/ent164/grading/`. They
  never enter this repo, same rule as every other student artifact.

## Class web pages

- **Navigation is generated, not hand-written.** `tools/site-nav/nav.py` defines
  the one main nav (`MAIN_LINKS`) and the per-page spec (CTA + which site
  section a page belongs to). `tools/site-nav/apply.py` rewrites the
  hand-authored pages from it; `tools/skill-tasks/catalog/build.py` imports the
  same module for the generated `tasks/` pages, so the two can never disagree.
  After editing a nav, a page's links, or adding a page:
  ```bash
  python3 tools/site-nav/apply.py            # rewrite the navs
  python3 tools/site-nav/apply.py --check    # CI: every nav matches the spec
  python3 tools/site-nav/verify-links.py     # every link on the site resolves
  ```
- **`verify-links.py` checks the whole document, not just the nav.** It reported
  "every nav link resolves" while all twelve workshop cards pointed at
  `../class-01/` — no `classes/` segment — because it only read `<nav>` blocks.
  It now walks every `href` and `src` on every page, and distinguishes nav links
  from body links in its output. That distinction matters: a nav mistake is
  generated and appears on every page at once, while a body mistake hides on
  one page, and the second kind is the one that shipped. It has since found and
  fixed three links in class 3 that had been broken since the page was written.
  When you add a builder, run it after: a relative path one level short is the
  failure this catches, and it is easy to write.
- **Main nav vs sub-nav.** The main nav holds *site* links only (Tasks, Class
  slides, Syllabus, About) plus one contextual CTA that is allowed to differ per
  page (a class page's "Download slides"). A page's own sections go in a
  `.subnav` bar, or in the sidebar `On this page` block on class/syllabus pages —
  never both, because the same links twice is noise.
- **The main links are a checkbox-driven menu below 881px.** A hidden
  `.nav-toggle` checkbox plus the `~` combinator shows/hides `.nav-links`; no
  JavaScript. On wider screens the links are a plain flex row. Two hard-won
  rules here: (1) do **not** put the links inside a `<details>` — a closed
  `<details>` hides its children whatever CSS says about its `display`, so
  `display: contents` on the desktop nav silently rendered it *empty*;
  (2) the mobile menu exists because the old CSS `display: none`d every main
  link, leaving a phone with nothing but the CTA. `verify-render.py` is the
  only check that can see either failure, because it looks at painted pixels
  rather than CSS properties — keep it in CI.
- **Guide pages use a different component** (`site-nav`, from the same
  `MAIN_LINKS`) because those pages are printed: `guide.css` hides it in print.
  The class pages' `.pdf` CTAs are relative to the page, not the root.
- `assets/site.css` is the shared light theme for the hub, syllabus, about and
  class pages; `assets/guide.css` is the same theme for the guide pages (US Letter
  print). Both follow the slide decks' palette. Style pages through these
  files — do not reintroduce per-page `<style>` blocks.
- Photography on the site comes from the instructor's own class photos
  (`assets/photos/class/`, EXIF stripped before committing). Prefer these, and
  the deck photos in `classes/*/shots/`, over stock imagery.
- `classes/class-NN/index.html` is the hand-authored class landing page, separate
  from the deck (it is not generated). Keep its links to `slides.html` and the
  PDF working, and update it when shared facts change (title, dates, TA info).
- **Every class in the course has a page; not every class has a deck yet.**
  Classes 8, 10, 12 and 13 are placeholders: a real page with the syllabus week
  title, what the class covers, and the milestone reflection where one is due
  (weeks 8 and 13), plus the note that the deck is being converted. No class
  page links Google Slides or Figma — those are retired, and students reach the
  old material through Canvas.
  - `populate.py` derives a class's title from `<title>` and its week from the
    hero kicker, so a placeholder's Canvas module name changes with its page.
    A placeholder has no `ENT-164-Class-N-*.pdf`, so the plan gives it no
    "Slides (PDF)" item — just the class page.
  - Canvas module names and the syllabus week titles disagree for weeks 10, 12
    and 13 (Canvas: "Smart Devices", "Connectivity (Part 2)", "Final Demos and
    Class Retro"). The class pages follow the **syllabus** titles by decision;
    the Canvas modules still carry the deck names.
  - Placeholders are in `PAGES` in `nav.py` with a syllabus CTA rather than
    "Download slides". When a real deck is converted, add the PDF name and
    switch the CTA and footer link like the other classes.
- Hub `index.html` and `syllabus/index.html` link to each class page; keep the
  "In-class decks" card counts (e.g. slide counts) accurate.
