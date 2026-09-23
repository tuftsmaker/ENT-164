# Building the tutorial videos

This builds a narrated tutorial video with **burned-in captions** from two
things: a narration script, and a set of **real browser recordings** driven
through `browser-control`.

The output is a 1920×1080 H.264 MP4 with a title card, burned-in captions, and a
closing card. The recordings are genuine screen captures of Onshape — nothing is
mocked up or drawn as a diagram.

```
script.json ──► Deepgram TTS ──► whisper alignment ──► sentence timings
                                                              │
scene scripts ──► browser-control recording ──► takes ──► plan/cut ──► final MP4
                                                              │
                              title card + caption PNGs ──────┘
```

## Layout

```
tools/video-build/
  pipeline.py            post-production: tts, align, cards, captions, plan, assemble
  record.sh              drives browser-control to record the takes
  scenes/
    lib.js               Playwright helpers (mouse, click, text lookup)
    lib2.js              visible DOM cursor, smooth motion, badge hiding
    beat.js              the Beat scheduler + shared scene helpers
    preflight.js         forces a true 1920x1080 capture surface
  projects/<slug>/
    video.json           title text, voice, take list, document name
    script.json          narration text, one entry per scene
    takes/takeNN.js      one script per take (timed actions)
    setup/setup-*.js     lands the app in the right state before each take
```

Media never lives in the repo. Recordings and intermediates go to the
project's `workDir` (see `video.json`), by default
`~/Movies/ent164-onshape-tutorial/<slug>-build/`.

## One-time setup

```bash
brew install whisper-cpp ffmpeg
# a ggml model for the forced alignment (tiny.en is plenty for timing)
mkdir -p ~/.cache/whisper.cpp
curl -L -o ~/.cache/whisper.cpp/ggml-tiny.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin
# Deepgram key for the narration voice
mkdir -p ~/.config/deepgram && printf '%s' 'YOUR_KEY' > ~/.config/deepgram/api_key
chmod 600 ~/.config/deepgram/api_key
```

`ffmpeg` here has **no `drawtext`, `subtitles` or `ass` filter** (no
libfreetype/libass). That is why captions and cards are rendered as images with
PIL and composited with `overlay` — don't try to use text filters.

## Building a video

```bash
cd tools/video-build
P=projects/laser-cutting-in-onshape

# 1. narration  (needs network + the Deepgram key)
python3 pipeline.py tts     --project $P
python3 pipeline.py align   --project $P

# 2. record the Onshape takes  (needs the browser attached, see below)
./record.sh $P

# 3. post-production
python3 pipeline.py all     --project $P
```

`pipeline.py all` runs cards → captions → plan → assemble, which is
deterministic given the recordings. Re-run it freely; `assemble` is the only
slow step (~30 s).

To re-render only part way:

```bash
python3 pipeline.py tts       --project $P    # cached clips are skipped
python3 pipeline.py align     --project $P
python3 pipeline.py cards     --project $P
python3 pipeline.py captions  --project $P
python3 pipeline.py plan      --project $P
python3 pipeline.py assemble  --project $P
```

## Recording takes

The recorder needs a Chromium tab it can drive, attached through
`browser-control`:

```bash
browser-control status                    # which session owns the Onshape tab?
SESSION=onshape-video ./record.sh $P       # adopts that session name
```

`record.sh` runs, per take: **setup** (recorder stopped, lands the app in the
right state) → **pre-flight** (forces a true 1920×1080 surface, hides the
Browser Control badge) → **recording start** → **take** → **stop** → report.

Re-record a single take with `./record.sh $P take04`.

### How a take is timed

Each take script is paced against the narration with the `Beat` scheduler:

```js
const SIDS = ['s06_rectangle', 's07_dimensions'];
const O = offs(SIDS);                    // scene offset within the take
const TOTAL = takeDur(SIDS);
const B = Beat(TOTAL, 'take06');
await scenePrep();

await B.at(at(O, 's06_rectangle', 1) + 0.5);   // sentence 1, half a second in
await clickAt(1090, 780, 650, 600);
B.mark('corner1');
```

`sent(sid, i)` gives sentence *i*'s `[start, end]` from the alignment, so beats
are expressed relative to what is being said, not to absolute seconds. Re-run
`tts`/`align` after any script edit and the take scripts follow automatically —
but you must re-record, because the recorded pacing is baked into the video.

**Every take's setup must land the app in the starting state itself**, so a take
can be re-recorded on its own. Do not rely on the previous take having run.

### The document is created once, not by the setup

Onshape's Create flow opens the new document in a **new tab**, and a recording
session stays pinned to the tab it started on. A setup that creates its own
document therefore keeps working on the wrong page — and reports success while
it does it.

So create the document once, up front (by hand, or with `createDocument()`), and
record its Part Studio URL as `"documentUrl"` in `video.json`. The setup then
calls:

```js
const made = await openDocument(cfg.documentUrl);
```

which navigates the *current* tab. It also repairs a dropped connection: a tab
left idle long enough shows Onshape's "is not connected" banner, and from then
on no command opens a feature dialog — every later step fails quietly, with the
screenshot looking almost normal. `openDocument` detects the banner, reloads,
and waits for it to clear.

## Gotchas worth knowing

These all cost real time to discover. They are handled in the helpers — keep
them that way.

- **The capture surface silently letterboxes.** Recordings sometimes come back
  with the page in a 1512×724 corner of a 1920×1080 frame. `Emulation.setDeviceMetricsOverride`
  must be applied *before* the recorder starts, and re-applied after any
  navigation. `assemble` also detects and crops out letterboxing as a fallback.
- **The OS cursor is not captured over CDP.** `lib2.js` injects a DOM cursor
  and animates it with `requestAnimationFrame`; that also forces the compositor
  to emit frames, which a static page otherwise does not.
- **The Browser Control badge can't be hidden with CSS.** It lives in a shadow
  root declaring `:host { all: initial !important }`. `lib2.js` moves it into a
  `display:none` wrapper instead.
- **A right-click in the canvas opens a context menu; a right-*drag* orbits.**
  Keep the button down and move.
- **Orbiting can flip the camera** so the sketch view ends up upside down.
  Reload the document (`reloadDocument()` in `beat.js`) to restore the default
  camera, and don't orbit more than the scene needs.
- **`Meta+A` does not select-all in Onshape's document-name field.** Clear it
  through the native value setter, then type, or the typed text appends to the
  default "Untitled document".
- **The green check commits and closes a sketch.** Never tell viewers to click
  it until they are done drawing.
- **Verify the plane before recording.** Selecting a datum row in the feature
  tree only *highlights* it; the sketch plane is only set if the datum is
  selected *before* the Sketch tool is clicked. Check the dialog reads
  `Sketch plane: <plane>`.

## Adding another video

1. `cp -R projects/laser-cutting-in-onshape projects/<slug>` and edit
   `video.json` (slug, titles, voice, `documentName`) and `script.json`.
2. Rewrite `takes/` and `setup/` for the new flow. `scenes/beat.js` has the
   shared helpers: `offs`, `sent`, `at`, `Beat`, `scenePrep`, `cleanStudio`,
   `reloadDocument`, `newTopSketchFramed`, `drawRect100x60`, `drawHoleDimmed`,
   `orbit`, `isFullyDefined`.
3. `pipeline.py tts && align`, then `./record.sh <slug>`, then `pipeline.py all`.

Keep `documentName` in `video.json` matching the on-screen title, and have the
take that creates the document type that name.

## Publishing

`scripts/upload-youtube.py` uploads the finished MP4 (`videos.insert`,
resumable, defaults to private) and `scripts/update-youtube.py` publishes it
later. Both live in the repo's `scripts/` and share `scripts/_youtube_auth.py`;
see AGENTS.md for the two tokens, the venv, and the API-audit caveat that forces
private-only uploads until the project passes a compliance audit.

## Recording a native app (Inkscape)

The browser pipeline records a tab over CDP. Inkscape is a **native** app, so it
has its own driver: `ink-drive.py`, which controls the GUI through macOS
Accessibility (`osascript`) and synthetic input (`cliclick`), and captures the
screen with `ffmpeg`. Its output matches what `pipeline.py plan/assemble`
expect, so post-production is unchanged.

```bash
python3 ink-drive.py record --project projects/laser-cutting-in-inkscape --take take01
```

### One-time setup

1. Grant **Accessibility** to the terminal that runs opencode (System Settings >
   Privacy & Security > Accessibility), then restart the terminal. Grant it to
   the *sender* — the terminal — not to Inkscape; the permission is needed to
   send UI events, not to receive them.
2. `brew install cliclick`

### What costs time if you don't know it

- **Zoom is a menu action, not a bare key.** `Cmd+4` is Zoom Drawing and `Cmd+5`
  is Zoom Page, but plain `4` is *Center Page* and plain `5` is *Grey Scale* —
  so a bare keypress leaves the view at about 2% on a grey canvas and it looks
  as though the import failed. `ink-drive.py` uses `menu("View","Zoom",...)`.
  It also uses the menu rather than a keystroke because the terminal reclaims
  focus between `osascript` calls, so a keystroke can land outside Inkscape.
- **Window geometry comes back ambiguously.** AppleScript's
  `(position of w) & (size of w)` concatenates two records with no separator, so
  `{0,33}` + `{1512,868}` arrives as `033 1512868` and cannot be split reliably.
  Query each item and join with commas yourself.
- **A modal dialog is not always window 1**, and its size is unrelated to the
  main window's, so clicking it by a fraction of the main window misses. Look it
  up by title (`named_window_xywh`). GTK widgets in these dialogs have no
  accessible names, so clicking by measured fraction is the only handle.
- **The process is `inkscape`, lowercase.** `pkill -x Inkscape` matches nothing,
  so a "clean restart" silently reuses the old process and every window query
  afterwards is wrong. `quit_app()` matches case-insensitively.
- **"A window exists" is not "the app is ready."** The menu bar is unavailable
  until startup finishes; clicking it too early throws *Can't get menu bar item*.

### Onshape DXFs need normalising before Inkscape will place them

`projects/laser-cutting-in-inkscape/normalise-dxf.py` fixes a real trap: the
Onshape export carries **no units** and sets `$EXTMIN`/`$EXTMAX`/`$PEXTMIN`/
`$PEXTMAX` to AutoCAD's `+/-1e20` "empty extents" sentinel. Inkscape's importer
then flips Y with `height - scale*(y - ymin)` using its own hardcoded A4 height
and `ymin = 0`, which puts a sketch drawn at `y = -60..0` at 297..357mm —
entirely above the page. The document opens looking empty.

The script shifts the geometry into positive Y and writes real units and extents
for all four variables. A header variable like `$EXTMIN` carries **three**
values (X, Y, Z), so replacing only the first leaves the sentinels on the other
axes — which is enough to keep the page wrong.
