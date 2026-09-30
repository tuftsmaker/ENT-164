# ENT-164 site and class decks — working agreement

Static course site for ENT-164 Intro to Making (Tufts), published from this repo
via GitHub Pages: https://tuftsmaker.github.io/ENT-164/

Load the student-writing-style skill before writing or editing any student-facing page.

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

## Canvas: generated pages, linked artifacts (course 76330, Fa26-ENT-0164-01)

- **Pages are generated from the site masters; artifacts stay links.** The home
  page (`home.py`), the syllabus (`syllabus.py`) and the class pages + the
  workshops index (`pages.py`) are pushed as Canvas content — one source,
  regenerated on demand. Deck PDFs, the handout and the tip videos are never
  copied into Canvas. A class page links its own deck — the "Download the
  slides (PDF)" button, a Pages URL such as
  `https://tuftsmaker.github.io/ENT-164/classes/class-01/ENT-164-Class-1-Introductions.pdf`
  — plus its due assignments, so the class module carries no slides item at all
  (Class page → readings → assignments). The handout and the tip videos stay
  **ExternalUrl** links where they are filed. Pushing to `main` is the only site
  sync step. Do not upload replacement PDFs.
- `pages.py` converts the class pages with `site_page.py` (inline styles,
  hotlinked images, links rewritten to Canvas pages or the site) and gives each
  class module a "Class page" **Page** item at position 2. **Canvas builds a
  page's URL from its title and ignores a requested URL**, so the title is the
  page's identity: pages are found/created by title, and the URL Canvas returns
  is recorded in `canvas-ids.yml` under `pages` — the module items and
  `home-page.html`'s `{{page:…}}` tokens use that, never a guessed slug.
  Internal links are written the way the rich-content editor writes them — an
  absolute URL plus `data-api-endpoint` and `data-api-returntype`
  (`site_page.annotate_internal_links`). Canvas **absolutizes** root-relative
  hrefs on save, so those attributes are what mark a link as course content;
  artifacts (deck PDFs, tip videos) stay ordinary site links. `--check`
  compares link targets too — a text-only comparison cannot see a link change.
- **A class page is a summary, not a copy of the deck.** It carries a hero
  card (title, dates, the deck button), one hero image and the "What we'll
  cover" cards — from the class's `coverage.yml` (`hero:`/`hero_alt:`,
  `topics:`, `links:`) — a due-today / due-next-week reminder read from the
  assignment data, and the class's own "What's due" and notes. A resource that
  used to be a bare module item (a signup, a tutorial series) belongs in
  `links:` and shows as a "Class resources" card instead. Module items link
  the page and the assignments; the deck lives on the page and in the PDF.
- Canvas credentials live in `~/.config/tuftsmaker/canvas_config.py` (outside the
  repo, mode 0600, dir 0700 — the same directory as the YouTube credentials).
  Never print, copy, commit, or echo the token. `COURSE_ID` in that file is
  accepted but ignored: development targets the prototype (see the Canvas
  section below).
- **The Canvas tools run wherever the credentials are.** They live in
  `~/.config/tuftsmaker/canvas_config.py`; a checkout without them cannot run a
  Canvas tool at all — the token is loaded before `--dry-run` does anything. The
  push commands are `pages.py`, `syllabus.py`, `home.py` and
  `push-assignments.py`; each defaults to the prototype, and reaching the live
  course takes `--course 76330` plus `CANVAS_ALLOW_LIVE=1` (and `--i-know` on
  `syllabus.py` / `push-assignments.py`).
- Module map (course 76330). Converted classes point at their Pages pages; the
  rest still point at Google Slides. After converting a class, verify the Pages
  URL returns 200 with the expected byte size, then **delete** the module's
  slides item — the class page links the deck now, so nothing replaces it.
  On 2026-09-30 the live course was synced: classes 1, 2, 3, 4, 5, 6, 9 and 11
  carry their converted Pages pages, with the old slides item removed from each
  module. The classes still being converted (8, 10, 12, 13 — modules 314496,
  314498, 314500, 314501) keep their Google Slides items until their decks land.

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
- Intentionally unpublished: `slides/*.pptx` (source decks) stay untracked; do
  not include them.
- `.github/workflows/slides-sync.yml` runs `scripts/build-class.sh --check --all`
  on pushes and PRs touching `classes/`, `assets/` or `scripts/`, and fails when
  a committed PDF drifts from its sources. It also runs
  `render-assignments.py --check`, which fails when a class name drifts across
  the syllabus week headings, the hub and workshop cards, the Canvas home page
  and the class pages. It does not block Pages deploys, so a red run means:
  rebuild or re-render, commit, push again.
- **One name per class, rendered from the class page.** The class page's own
  name (`classes/class-NN/index.html`'s `<title>`) is the source; the syllabus
  week heading, the hub and workshops deck cards, the Canvas home page's week
  list, the Canvas page title (`Class N: <name>`) and the Canvas module name
  are all generated from it (`render-assignments.py`, `pages.py`,
  `populate.py`). Renaming a class means editing its `<title>` and re-running
  those tools — `pages.py` renames the Canvas page in place (Canvas re-slugs
  it) rather than creating a twin, and `--check` on both tools reports any
  surface still carrying the old name.

## Class skills for opencode (now in the `tuftsmaker/skills` repo)

- The three skills — `breadboard-wiring` (diagrams), `laser-ready` (DXF to
  laser SVG, finger joints) and `box-maker` (finger-jointed boxes; the birdhouse
  is its worked example) — live in their own repo, served at
  `https://tuftsmaker.github.io/skills` and consumed by opencode via
  `skills.urls`. That repo is the **source of truth**, including the pinned
  Python sandbox each skill carries, the publisher and the CI; its `README.md`
  and `AGENTS.md` hold the conventions. `skills/` and `tools/skill-publish/`
  moved out of this repo in September 2026.
- This repo references that URL in two student-facing documents:
  `opencode-deepseek-guide/guide.html` (Step 7 and the "where everything
  lives" table) and `handouts/add-class-tools.html`. When a skills change
  alters what those pages say, update them here and rebuild their PDFs (below).
- Make a change to the skills in the skills repo, never by copying files back
  into this one.
- **`.nojekyll` at the repo root stays.** It was load-bearing while the skills
  were here (Jekyll converts `SKILL.md` and skips underscore files); it is
  harmless now and keeps a future underscore path from being silently dropped.
- `handouts/add-class-tools.html` is the student-facing one-pager; rebuild its
  PDF with headless Chrome after editing. It is US Letter and must stay on one
  page — check with `pdftotext -f 2 -l 2 ...` (anything printed = it spilled).
- The fuller web version of that one-pager, `add-class-tools/guide.html` (with
  its own `add-class-tools-to-opencode.pdf`), was **retired** when its steps
  moved into `opencode-deepseek-guide/` as Step 7. `handouts/add-class-tools.*`
  is now the only class-tools handout; edit it when that sentence changes.
- **Guide pages are US Letter, not A4.** The class is at a US university and
  students print these. `assets/guide.css` sets `@page { size: Letter }` and
  sizes the on-screen page column to 215.9mm; the `.cover` height is 279.4mm
  and must stay equal to the Letter content height, or the cover spills onto a
  blank second page. **Print margins live on the page box** (`@page { margin:
  15mm 18mm 12mm }`), not as padding on `.page`: a padded `.page` div only pads
  the first and last page of the run, so continuation pages print to the sheet
  edge. The cover opts out as a named page (`page: cover` + `@page cover {
  margin: 0 }`) so it stays full-bleed. If you change the page size, change all
  three together and rebuild **every** guide PDF — `opencode-deepseek-guide`
  and `laser-cutting` are both built from that one stylesheet. Verify with
  `pdfinfo <pdf> | grep 'Page size'` (expect
  `612 x 792 pts (letter)`) and spot-check that content pages share the same
  top and bottom margins.
- `laser-cutting/guide.html` is the Nolop laser-cutting walkthrough (Inkscape →
  UCP → cut), built on the official Nolop Makerspace guide. Its `shots/`
  contains screenshots reused from that guide under CC BY-SA, with credit kept
  in the page footer — retain the attribution if you move or reuse them.
  Class 3's deck and page draw their Inkscape/UCP screenshots from here, so
  editing a shot means copying it into `classes/class-03/shots/` too.
- **`opencode-deepseek-guide/` is one guide for both operating systems**, with
  `shots/` and `ai-coding-agent-setup-guide.pdf`. It replaced the former
  `opencode-deepseek-guide-mac/` and `-win/` pair: the only real differences
  were the download link and the install steps, so those are the only places
  the page branches (it names both OSes, macOS first). Its provider is
  **OpenCode Console** (called OpenCode Zen in older materials), not OpenRouter.
  Students do **not** create or paste an API key: they accept the instructor's
  invitation, then connect the in-app provider labelled **OpenCode Console**.
  The guide teaches the **`/connect` slash command** (type it in the message
  box → pick OpenCode Console from the Connect provider list) as the primary
  path; Settings → Providers reaches the same list and is kept as a fallback
  note. Connecting opens a **device-code browser sign-in** ("Continue in your
  browser. Confirm the code..."). The API-key option in that dialog is
  explicitly the service-account path — do not point students at it. During
  authorization the student must **switch the workspace to ENT-164 Intro to
  Making** (the class workspace's exact name — an account can also belong to
  "ENT-164 FA26 Intro to Making", so the dropdown lists both; do not confuse
  them), or the app connects to the wrong workspace with no class
  models/budget. **Step 7 absorbed the retired `add-class-tools/guide.html`:**
  paste "Add my class skills to opencode:
  https://tuftsmaker.github.io/skills", allow the settings change,
  restart, and test with **"I am a maker. How can you help me?"**. Note the
  app's settings sidebar changes shape when **more than one server** is
  configured: Projects/Providers/Models/Extensions then live inside each
  server entry under a **Servers** group instead of at the top level; the
  guide carries a callout for that, and the same menu is reproduced by seeding
  an `ssh.servers` entry. Screenshots come from the desktop app (V2, 2.0.16)
  driven over CDP in an isolated profile; the invitation and browser
  authorization figures come from a real class account, and the download and
  provider figures carry red outlines.

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

## Laser-ready SVG (`skills/maker-tasks/`)

The `maker-tasks` skill prepares a DXF for the laser. It does **not** grade or
check: a student exports a sketch from Onshape, and the skill turns it into the
SVG the cutter at Nolop reads — pure-red, unfilled, hairline cut paths on a
millimetre page. The former task/qualification system (task YAML, criteria,
fixtures, the public `tasks/` catalog and the Canvas signoff loop) was removed;
only this converter remains.

- **One converter: `skills/maker-tasks/laser/laser_svg.py`.** Its own CLI is the
  entry point — `python3 laser/laser_svg.py part.dxf` writes
  `part-laser-ready.svg` beside the DXF (`-o` and `--margin` to change that).
  It imports `dxf_reader.py` and `geom.py` from the same folder, all stdlib-only,
  so a student's opencode needs no checkout and nothing is installed. `SKILL.md`
  is the student-facing instruction.
- **Finger joints live beside it: `skills/maker-tasks/laser/finger_joints.py`.**
  Given a seam (`--seam x0,y0,x1,y1`), the measured `--thickness`, a `--side` and
  an optional `--fingers` count, it appends one zigzag cut path per seam so two
  pieces meet with matching fingers and slots (and no doubled path, which would
  make the laser fire twice). A finger is one thickness wide and **never deeper
  than one thickness** — asserted on write and re-measured by `--check`. It
  shares `dxf_reader.py`, so it is stdlib-only too. For a drawing a student
  attached, `--list` enumerates the straight seams (collinear pieces merged) and
  `--preview PATH` writes them numbered and coloured for the student to pick;
  `--pick N` then joints that one. By default a straight LINE already drawn along
  the seam is **removed** so the comb is cut once (`--keep-seam` to append
  instead), and only geometry it cannot remove — a seam inside a polyline — is
  reported as still doubled. Both tools know the Nolop machine: stock up to
  **3 mm** (the store sells 3 mm plywood/acrylic), bed **300 × 600 mm**, and each
  prints a `CHECK` line when its output page is larger than the bed. Both take
  `--open`, which shows the written SVG in the student's browser (on the joint
  tool, after converting the jointed DXF); the agent can also preview the `.svg`
  in opencode itself.
- **Hairline is a trap.** The obvious `stroke-width="hairline"` is **wrong**:
  Inkscape does not read it as the UI's Hairline and falls back to **1 mm**,
  exactly the thick line that makes the laser fire twice (measured: 1.016 mm vs
  0.042 mm). Inkscape's own serialisation is three declarations together —
  `stroke-width:1px;vector-effect:non-scaling-stroke;-inkscape-stroke:hairline`
  — and that string is what the converter writes. Keep all three.
- **An arc's page box** must come from its endpoints plus only the axis
  crossings the sweep passes through. Using the whole circle's box pads the page
  around geometry that is not there (112×60 became 112×87 and shifted the part
  down). Verified by rasterising the converted SVG and comparing inked pixels
  against the DXF's own tessellation, arc sweep direction included.
- **DXF is Y-up and SVG is Y-down**, so the Y-flip mirrors the drawing: a CCW CAD
  arc stays CCW on screen, which is SVG `sweep-flag 0`.
- **It reports rather than hides:** spline/ellipse approximations, polyline
  bulge vertices, geometry on unexpected layers, and lines drawn twice on the
  same line are all printed.

## Canvas (`tools/canvas-course/`)

Links only, never copies. `canvas_client.py` is the shared API client;
`populate.py` builds the course modules from the site, and `home.py` pushes the
home page from `home-page.html`.

Course IDs are constants in the client (`PROTOTYPE_COURSE`, `LIVE_COURSE`);
`python3 tools/canvas-course/canvas_client.py courses` lists what the token can
see, which is how the live ID is refreshed when a semester rolls over — and how
the prototype ID was found when the course was recreated (`71548` → `81044`).
The ID is never resolved at run time.

- **Canvas access is content-only, and writes stop at the prototype. Both are
  enforced in code, not by habit.** `canvas_client._guard` runs every request:
  reads must be one of `READ_FAMILIES` (course metadata, modules, items,
  assignments, groups, pages, single files) and may not ask for people through
  `include[]=`, and any POST/PUT/DELETE not aimed at course **81044, "Intro to
  Making Prototype"** is refused — including the case where a client was
  *constructed* for the live course, which is precisely the mistake it exists to
  catch. Rosters, enrollments, submissions, grades and discussion posts cannot
  be fetched even by a script that asks; comparing against the live course still
  works.
  - `load_config()` returns the prototype regardless of the config's `COURSE_ID`,
    because a stale or copied config must not decide which course tools touch.
  - The single escape hatch is `CANVAS_ALLOW_LIVE=1` in the environment. It is
    deliberately not a bare CLI flag, so reaching the live course is a decision
    rather than a typo. `populate.py --i-know` is the same gate.
  - `python3 tools/canvas-course/test_guard.py` proves both offline, no network:
    content reads allowed, rosters/enrollments/submissions/gradebook/
    discussions refused, writes/deletes/account-level routes stopped at the
    prototype, and the override still works. **Run it after touching the
    client.**
  - Why it is our job: Canvas token scopes cannot do this. Scopes restrict which
    *endpoints* a token may call, and `:course_id` in a scope is a path
    placeholder, not a filter — there is no syntax for pinning a course. Personal
    access tokens (what we have) are unscoped and inherit the user's full
    permissions across all their courses.
- **Canvas** (course 76330, the live course): modules and items only, and the
  home page. All of it is developed against the prototype first.
- `tools/canvas-course/populate.py` builds the course structure from the site:
  one module per class, with the deck PDF, the class page, and the site content
  that belongs to that class (the setup guides with Class 1, the tips and the
  cutting guide with Class 3). Links only, never copies. `--prune` clears modules
  and items outside the plan; more than half the modules, or a module that still
  holds items, needs `--force-prune` — a name-drift mismatch would otherwise
  look like a full cleanup. It refuses to run
  against the live course without `--i-know` (the same gate as
  `CANVAS_ALLOW_LIVE=1`). Canvas creates modules and items
  unpublished; publishing a module publishes its items with it.
- `tools/canvas-course/home.py` pushes the course **home page** from
  `home-page.html` beside it — the hub's theme and content, links only. Canvas
  strips `<style>` blocks and keeps a fixed property set, so the page is all
  inline styles (no `box-shadow`, bold via `<b>`) and the script reports what
  Canvas actually stored. It sets the page as the front page and points the
  Home tab at it (`default_view=wiki`). `{{syllabus_url}}` and
  `{{page:class-NN}}` in the page are resolved per course: the course's syllabus
  tab, and the Canvas page URLs recorded by `pages.py`.
- **Assignments live in the repo.** `classes/class-NN/assignments.yml` plus its
  `assignments/<slug>.html` descriptions are the master copy of every
  assignment. `tools/canvas-course/course.yml` names the courses, groups and
  the module→class pattern; `canvas-ids.yml` records Canvas ids per course,
  generated (`pull-assignments.py`), because ids change when a course is copied
  and the repo's identity is the slug. `pull-assignments.py` imports from live
  (`--report`, `--check`, `--ids COURSE`); it preserves the display fields the
  repo authors (`summary`, `week`, `audience`) and entries Canvas does not have
  (`source: repo` — create on push; `source: schedule` — site-only).
  Descriptions are scrubbed of Canvas injections (dp_app, `data-api-*`,
  verifier tokens) and of secret-shaped strings — a shared key stays in Canvas,
  where students read it, never in this public repo; their Canvas file links
  are noted, not chased.
- `render-assignments.py` writes the syllabus week chips from that data between
  the `<!-- assignments:begin -->` / `end` markers; `--check` proves the page
  matches the files. Run it after editing assignments or the syllabus.
- `syllabus.py` generates the Canvas **syllabus** from `syllabus/index.html`
  (the master) — inline-styled, links rewritten to the site — and pushes it as
  `course[syllabus_body]`, replacing the Google Doc link it used to hold.
  `--check` compares what Canvas stores (tags stripped, entities unescaped);
  `--dry-run` and `--out` preview. Canvas re-adds its dp_app injections on
  save, which the comparison reads through.
- `push-assignments.py` is the other direction, rehearsed on the prototype: it
  creates missing groups, assignments and module items, and updates the fields
  the repo owns (name, points, due/unlock/lock, submission types, group,
  placement) — never descriptions, `published`, or anything about people.
  Matching is by slug through `canvas-ids.yml`, then by exact name (adopted and
  recorded), else created; created assignments are **unpublished** on purpose.
  `--dry-run` first; re-running is a no-op when Canvas matches.
- `test_client.py` pins the form encoding (hashes bracketed, arrays repeated
  `[]` — a dict silently dropped all but the last array element) and
  `test_guard.py` pins the read/write boundary. Run both after touching
  `canvas_client.py`.
- Student work never enters this repo, same rule as every other student
  artifact.

## Class web pages

- **Navigation is generated, not hand-written.** `tools/site-nav/nav.py` defines
  the one main nav (`MAIN_LINKS`) and the per-page spec (CTA + which site
  section a page belongs to). `tools/site-nav/apply.py` rewrites the
  hand-authored pages from it, so the pages can never drift.
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
- **Main nav vs sub-nav.** The main nav holds *site* links only (Workshops,
  Syllabus, About) plus one contextual CTA that is allowed to differ per
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
  (weeks 8 and 13), plus the note that the deck is being converted. Class 7
  (Final Robot Assembly and Testing) is a full working session: a page with the
  build checklist and the assembly checkpoint, no deck, and no Canvas module of
  its own — its page is reached from the home page's week list and the syllabus
  chip. No class page links Google Slides or Figma — those are retired, and
  students reach the old material through Canvas.
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
