#!/usr/bin/env python3
"""Drive Inkscape's real GUI on macOS, to record native-app tutorial takes.

The browser pipeline records a tab over CDP (`record.sh`). Inkscape is a native
app, so it needs a different driver: this controls the GUI through macOS
Accessibility (`osascript`) and synthetic input (`cliclick`), and captures the
screen with `ffmpeg`.

Output matches what `pipeline.py plan/assemble` expect, so post-production is
unchanged:

    <workDir>/takes/takeNN.mp4          the recording
    <workDir>/takes/takeNN.start.json   {"startedAt": <wall ms>}
    <workDir>/takes/takeNN.exec.json    {"value": {"t0": <wall ms>, "marks": [...]}}

One-time setup:
  - Grant Accessibility to the terminal that runs this (System Settings >
    Privacy & Security > Accessibility). Without it `osascript` cannot send UI
    events and nothing here works.
  - `brew install cliclick`

Why this shape: Inkscape's own `--shell` refuses any action needing a desktop
("Only actions that don't require a desktop may be used"), and it has no D-Bus
or pacing support on macOS, so a scripted *visible* walkthrough has to go
through the real window.

Usage:
  ink-drive.py launch FILE            open Inkscape on FILE (no recording)
  ink-drive.py window x y w h         move/resize the Inkscape window
  ink-drive.py shot OUT.png           screenshot the window region
  ink-drive.py act 'json-actions'     run actions without recording
  ink-drive.py record --project P --take takeNN
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

APP = "Inkscape"
CLICLICK = "/opt/homebrew/bin/cliclick"

# The window geometry we standardise on. The screen is 1512x982 logical, and a
# 1512x868 window at y=33 leaves the menu bar clear. Recording crops to this,
# then scales to 1920x1080 so it matches the other tutorials.
WIN = {"x": 0, "y": 33, "w": 1512, "h": 868}


# ------------------------------------------------------------------ primitives

def osa(script):
    """Run an AppleScript snippet, raising on failure."""
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"osascript failed: {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def raise_app():
    """Bring Inkscape to the front.

    Must happen in the SAME osascript process as any keystroke: each
    `osascript -e` is its own process, and the terminal reclaims focus between
    them, so a keystroke sent in a later call lands in the terminal instead of
    Inkscape.
    """
    osa(f'tell application "System Events" to set frontmost of process "{APP}" to true')


def keystroke(key, *mods):
    """Send a keystroke to Inkscape. Raise first, in one osascript process."""
    mod_clause = ""
    if mods:
        mods = [{"cmd": "command down", "shift": "shift down", "alt": "option down",
                 "ctrl": "control down"}.get(m, m) for m in mods]
        mod_clause = " using {" + ", ".join(mods) + "}"
    osa(
        f'tell application "System Events"\n'
        f'  set frontmost of process "{APP}" to true\n'
        f'  delay 0.25\n'
        f'  keystroke "{key}"{mod_clause}\n'
        f'end tell'
    )


def press(key):
    """Press a named key (esc, enter, delete, tab) or a single character."""
    osa(
        f'tell application "System Events"\n'
        f'  set frontmost of process "{APP}" to true\n'
        f'  delay 0.2\n'
        f'  key code {_KEYCODES[key]}\n'
        f'end tell' if key in _KEYCODES else
        f'tell application "System Events"\n'
        f'  set frontmost of process "{APP}" to true\n'
        f'  delay 0.2\n'
        f'  keystroke "{key}"\n'
        f'end tell'
    )


_KEYCODES = {"enter": 36, "return": 36, "tab": 48, "space": 49, "delete": 51,
             "esc": 53, "escape": 53, "left": 123, "right": 124, "down": 125, "up": 126}


def _cliclick(*cmds):
    r = subprocess.run([CLICLICK, *cmds], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cliclick failed: {r.stderr.strip()[:200]}")


def move(x, y, dur=0.35):
    """Move the pointer smoothly, so the recording reads as real mouse motion."""
    _cliclick("-e", str(int(dur * 1000)), f"m:{int(round(x))},{int(round(y))}")


def click(x, y, dur=0.35):
    move(x, y, dur)
    _cliclick(f"c:{int(round(x))},{int(round(y))}")


def right_click(x, y, dur=0.35):
    move(x, y, dur)
    _cliclick(f"rc:{int(round(x))},{int(round(y))}")


def shift_click(x, y, dur=0.35):
    """Click with Shift held, for adding to a selection."""
    move(x, y, dur)
    _cliclick("kd:shift")
    _cliclick(f"c:{int(round(x))},{int(round(y))}")
    _cliclick("ku:shift")


def drag(x1, y1, x2, y2, dur=0.6):
    move(x1, y1)
    _cliclick("-e", str(int(dur * 1000 / 10)), "kd:alt")
    _cliclick(f"dd:{x1},{y1}")
    time.sleep(0.15)
    _cliclick(f"dm:{x2},{y2}")
    time.sleep(0.15)
    _cliclick(f"du:{x2},{y2}")
    _cliclick("ku:alt")


def type_text(s, per_char=0.03):
    raise_app()
    _cliclick("kd:cmd", "ku:cmd")          # settle focus
    subprocess.run([CLICLICK, "-w", str(int(per_char * 1000)), f"t:{s}"], check=True)


def menu(*items):
    """Click through the menu bar, including submenus.

    menu("File", "Open...")                    -> File > Open...
    menu("View", "Zoom", "Zoom Drawing")       -> View > Zoom > Zoom Drawing

    Each leading item is a menu bar item, and each subsequent one is nested
    inside the previous item's `menu 1`. Building the path by hand for the
    multi-level case is fiddly — AppleScript needs the whole chain spelled out —
    so walk it from the inside out.
    """
    if len(items) < 2:
        raise ValueError("menu() needs at least a menu bar item and a menu item")
    # Build from the inside out: the deepest item, then each enclosing submenu.
    expr = f'menu item "{items[-1]}"'
    for item in reversed(items[1:-1]):
        expr = f'{expr} of menu 1 of menu item "{item}"'
    expr = f'{expr} of menu 1 of menu bar item "{items[0]}" of menu bar 1'
    osa(
        f'tell application "System Events" to tell process "{APP}"\n'
        f'  set frontmost to true\n'
        f'  delay 0.2\n'
        f'  click {expr}\n'
        f'end tell'
    )


def win_xywh():
    return window_xywh(1)


def set_window(x, y, w, h):
    """Move/resize the document window (not window 1: a tooltip may be in front)."""
    idx = document_window_index()
    osa(
        f'tell application "System Events" to tell process "{APP}"\n'
        f'  set position of window {idx} to {{{x}, {y}}}\n'
        f'  set size of window {idx} to {{{w}, {h}}}\n'
        f'end tell'
    )


def document_window_index():
    """Index of the largest Inkscape window big enough to be the document window.

    Hover tooltips and transient popups are windows too, and can be 332x51, so
    "the largest" alone is not enough — a small window is never the document.
    """
    best, best_area = 1, 0
    for i in range(1, window_count() + 1):
        try:
            g = window_xywh(i)
        except Exception:
            continue
        if not g or g["w"] < 300 or g["h"] < 300:
            continue
        if g["w"] * g["h"] > best_area:
            best, best_area = i, g["w"] * g["h"]
    return best


def launch(path=None, timeout=60):
    """Open Inkscape (optionally on a file), and wait until it is usable.

    "A window exists" is not enough: the menu bar is unavailable until the app
    has finished starting, and clicking it too early throws "Can't get menu bar
    item". So wait for the menu bar itself, not just a window count.
    """
    args = ["open", "-a", "Inkscape"]
    if path:
        args.append(os.path.abspath(os.path.expanduser(path)))
    subprocess.run(args, check=True)
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            ok = osa(
                f'tell application "System Events" to tell process "{APP}"\n'
                f'  if (count of windows) is 0 then return "no-window"\n'
                f'  if (count of menu bars) is 0 then return "no-menubar"\n'
                f'  return "ready"\n'
                f'end tell')
            last = ok
            if ok == "ready":
                time.sleep(1.5)             # let it finish laying out
                return
        except RuntimeError as e:
            last = str(e)[:80]
        time.sleep(0.6)
    raise RuntimeError(f"Inkscape not ready within {timeout}s (last: {last})")


def to_screen(x, y):
    """Canvas coords are given relative to the document window; convert for input.

    Uses document_window(), not window 1: a stray tooltip would otherwise shift
    every click by its own origin.
    """
    w = document_window()
    return w["x"] + x, w["y"] + y


_PLATE = None
_PANEL = {}


def dock_left():
    """x of the right dock's left edge, found from the canvas/dock boundary.

    The dock grows to fit its widest dialog (Align and Distribute is wider than
    Fill and Stroke), so every panel coordinate has to be an offset from this.
    """
    import tempfile
    from PIL import Image
    import numpy as np

    fd, path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    try:
        shot(path)
        a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    finally:
        os.unlink(path)
    s = a.shape[0] / WIN["h"]
    # A column is "dock" when it is dark for most of a tall band: the dock is a
    # uniform dark slab, while the drawing's ink crosses only a few rows of it.
    band = a[int(380 * s):int(520 * s), :]
    dark_cols = (band.sum(2) < 330).mean(0) > 0.9
    xs = np.where(dark_cols[int(300 * s):int(1500 * s)])[0]
    if len(xs) == 0:
        raise RuntimeError("dock_left: no dock found")
    left = (int(300 * s) + xs.min()) / s
    print(f"  dock left at {left:.0f}")
    return left


def measure_plate():
    """Bounding box of the drawing on the page, in window coordinates.

    Taken from a screenshot rather than assumed: the page is white and the
    canvas grey, so the drawing's strokes are the only ink in that region, and
    measuring them means a canvas click does not depend on the zoom, the dock
    width, or which dialogs happen to be open.
    """
    global _PLATE
    import tempfile
    from PIL import Image
    import numpy as np

    fd, path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    try:
        shot(path)
        a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    finally:
        os.unlink(path)
    s = a.shape[0] / WIN["h"]              # screenshot pixels per logical point
    x0r, x1r = int(60 * s), int(836 * s)
    y0r, y1r = int(150 * s), int(836 * s)
    white = (a[:, :, 0] > 240) & (a[:, :, 1] > 240) & (a[:, :, 2] > 240)
    seen = np.zeros_like(white)
    seen[y0r:y1r, x0r:x1r] = white[y0r:y1r, x0r:x1r]
    # The page is white and large: rows and columns that are mostly white are
    # the page's, never a UI element's, so the profiles find it without any
    # connected-component work.
    rows = np.where(seen.sum(1) > 0.25 * (x1r - x0r))[0]
    cols = np.where(seen.sum(0) > 0.25 * (y1r - y0r))[0]
    if len(rows) < 10 or len(cols) < 10:
        raise RuntimeError("measure_plate: no page found")
    y0, y1, x0, x1 = rows.min() + 4, rows.max() - 4, cols.min() + 4, cols.max() - 4
    sub = a[y0:y1, x0:x1]
    ink = sub.sum(2) < 600                 # strokes: neither page nor canvas
    ys, xs = np.where(ink)
    if len(xs) < 50:
        raise RuntimeError("measure_plate: no drawing found on the page")
    _PLATE = {"left": (x0 + xs.min()) / s, "right": (x0 + xs.max()) / s,
              "top": (y0 + ys.min()) / s, "bottom": (y0 + ys.max()) / s}
    return _PLATE


def plate_point(name):
    """A named point on the drawing, measured now (see measure_plate)."""
    global _PLATE
    p = _PLATE or measure_plate()
    cx = (p["left"] + p["right"]) / 2
    cy = (p["top"] + p["bottom"]) / 2
    points = {
        "plate-centre": (cx, cy),
        "plate-top": (cx, p["top"]),
        "plate-left": (p["left"] + 1, cy),
        "page-below": (cx, min(p["bottom"] + 60, 820)),
    }
    if name not in points:
        raise ValueError(f"unknown plate point {name!r}")
    return points[name]


# Fill and Stroke widgets, as offsets from the dock's left edge. The x positions
# were measured with the panel at two different widths; the y positions do not
# move. Right-aligned widgets (the colour mode menu and the RGBA fields) are
# measured from the window's right edge instead, so they need no offset at all.
_PANEL_OFFSETS = {
    "panel:fill": (71, 168),
    "panel:strokepaint": (145, 168),
    "panel:strokestyle": (243, 168),
    "panel:x": (39, 201),
    "panel:flat": (69, 201),
    "panel:unit": (243, 208),
    "panel:hairline": (243, 401),
    "panel:docktab": (293, 145),
    "panel:mode": ("right", 242),
    "panel:mode-rgb": ("right", 297),
    "panel:rgb-r": ("right", 303),
    "panel:rgb-g": ("right", 341),
    "panel:rgb-b": ("right", 379),
    "panel:opacity": ("right", 416),
    "align:centre-v": (147, 330),
    "align:centre-h": (147, 364),
}


def panel_point(name):
    """A named Fill and Stroke / Align widget position, in window coordinates."""
    off = _PANEL_OFFSETS.get(name)
    if off is None:
        raise ValueError(f"unknown panel point {name!r}")
    dx, y = off
    if dx == "right":
        return 1456, y
    if name.startswith("align:"):
        # Opening Align and Distribute widens the dock, so its own coordinates
        # need a fresh edge measurement rather than the cached one.
        left = _PANEL["left"] = dock_left()
    else:
        left = _PANEL.get("left") or dock_left()
        _PANEL["left"] = left
    return left + dx, y


def shot(out_png):
    w = document_window()
    subprocess.run(["screencapture", "-x", "-R",
                    f"{w['x']},{w['y']},{w['w']},{w['h']}", out_png], check=True)
    return out_png


# ---------------------------------------------------------------- action runner

def run_actions(actions, marks=None, t0=None, verbose=True):
    """Execute a take's action list, paced against the narration.

    Each action is {at: {scene, sent, off}, do: [...]} or {wait: n, do:[...]}.
    Times resolve against sentence-timings.json: `scene` picks the narration
    scene, `sent` its sentence index, `off` extra seconds.
    """
    marks = marks if marks is not None else []
    started = time.time()

    for a in actions:
        if "at" in a:
            target = _resolve_at(a["at"])
        else:
            target = time.time() - started
        delay = target - (time.time() - started)
        if delay > 0:
            time.sleep(delay)

        for op in a.get("do", []):
            if verbose:
                print(f"    [{time.time() - started:6.2f}s] {op}")
            _apply(op, marks, started)

    return {"marks": marks, "elapsed": time.time() - started}


_TIMINGS = None


def load_timings(work):
    global _TIMINGS
    _TIMINGS = json.load(open(os.path.join(work, "sentence-timings.json")))
    return _TIMINGS


_TAKE_OFFSETS = {}


def _set_take(scenes):
    """Record where each scene of the current take starts, take-relative.

    Sentence times in sentence-timings.json are relative to their own scene, so
    a multi-scene take has to add the durations of the scenes before it — the
    same thing `offs()` does in the browser takes.
    """
    global _TAKE_OFFSETS
    _TAKE_OFFSETS, acc = {}, 0.0
    for sid in scenes:
        _TAKE_OFFSETS[sid] = acc
        acc += _TIMINGS[sid]["duration"]


def take_length(scenes, tail=0.0):
    return sum(_TIMINGS[s]["duration"] for s in scenes) + tail


def _resolve_at(spec):
    """Seconds from take start for {scene, sent, off}."""
    if spec is None:
        return 0.0
    if isinstance(spec, (int, float)):
        return float(spec)
    scene, sent, off = spec.get("scene"), spec.get("sent", 0), spec.get("off", 0.0)
    if scene is None:
        return float(off)
    if _TIMINGS is None:
        raise RuntimeError("load_timings() must run before resolving actions")
    base = _TAKE_OFFSETS.get(scene, 0.0)
    return base + _TIMINGS[scene]["sentences"][sent]["start"] + off


def _apply(op, marks, started):
    kind = next(iter(op))
    v = op[kind]

    # Canvas coordinates may be named points on the measured drawing, so a click
    # does not depend on the zoom or on which dock dialogs are open.
    if kind in ("click", "sclick", "rclick", "dd", "move"):
        if isinstance(v[0], str):
            v = list(plate_point(v[0]) if not v[0].startswith(("panel:", "align:"))
                     else panel_point(v[0]))
    elif kind == "drag":
        if isinstance(v[0], str):
            a, b = plate_point(v[0]), plate_point(v[1])
            v = [a[0], a[1], b[0], b[1]]

    if kind == "mark":
        marks.append({"n": v, "rel": int((time.time() - started) * 1000),
                      "wall": int(time.time() * 1000)})
    elif kind == "click":
        x, y = to_screen(*v)
        click(x, y)
    elif kind == "rclick":
        x, y = to_screen(*v)
        right_click(x, y)
    elif kind == "sclick":
        x, y = to_screen(*v)
        shift_click(x, y)
    elif kind == "dd":
        # double-click: the only way Inkscape's spin/combo widgets take focus
        x, y = to_screen(*v)
        _cliclick(f"dd:{int(round(x))},{int(round(y))}")
    elif kind == "drag":
        x1, y1 = to_screen(v[0], v[1])
        x2, y2 = to_screen(v[2], v[3])
        drag(x1, y1, x2, y2)
    elif kind == "move":
        x, y = to_screen(*v)
        move(x, y)
    elif kind == "type":
        type_text(v)
    elif kind == "typecodes":
        _type_codes(v)
    elif kind == "dismiss":
        dismiss_notices()
    elif kind == "saveas":
        save_as(v)
    elif kind == "setfield":
        # setfield: [x, y, text] — double-click, select all, type, Enter. The
        # point may be a named panel widget: [name, text].
        if isinstance(v[0], str):
            px, py, text = *panel_point(v[0]), v[1]
        else:
            px, py, text = v[0], v[1], v[2]
        _set_field(*to_screen(px, py), text)
    elif kind == "press":
        press(v)
    elif kind == "key":
        keystroke(v[0], *v[1:]) if isinstance(v, list) else keystroke(v)
    elif kind == "menu":
        menu(*v)
    elif kind == "zoom":
        # zoom: drawing | page | selection | 1:1
        label = {"drawing": "Zoom Drawing", "page": "Zoom Page",
                 "selection": "Zoom Selection", "1:1": "Zoom to 1:1"}.get(v, v)
        menu("View", "Zoom", label)
    elif kind == "osascript":
        osa(v)
    elif kind == "shell":
        subprocess.run(v, shell=True, check=True)
    elif kind == "wait":
        time.sleep(v)
    elif kind == "window":
        set_window(*v)
    elif kind == "shot":
        shot(v)
    else:
        raise SystemExit(f"unknown action: {kind}")


# ------------------------------------------------------------------- recording

def _osa_ints(script):
    """Run AppleScript returning a comma-separated list; return the integers."""
    out = osa(script)
    return [int(float(v)) for v in re.findall(r"-?\d+", out)]


def window_xywh(index=1):
    """Geometry of an Inkscape window by index (1 = frontmost)."""
    # Query position and size in ONE call but as a delimited string: AppleScript
    # concatenates records without a separator, which is ambiguous for
    # single-digit coordinates ("033 1512868" cannot be split back correctly).
    nums = _osa_ints(
        f'tell application "System Events" to tell process "{APP}"\n'
        f'  set p to position of window {index}\n'
        f'  set s to size of window {index}\n'
        f'  return (item 1 of p) & "," & (item 2 of p) & "," & '
        f'(item 1 of s) & "," & (item 2 of s)\n'
        f'end tell')
    if len(nums) < 4:
        return None
    return {"x": nums[0], "y": nums[1], "w": nums[2], "h": nums[3]}


def document_window():
    """Geometry of the Inkscape document window, ignoring popups and tooltips.

    `window 1` is not reliable: hover tooltips and transient popups appear as
    windows of their own, which silently invalidates every coordinate derived
    from them. The document window is always the big one.
    """
    return window_xywh(document_window_index()) or win_xywh()


def named_window_xywh(title):
    """Geometry of a specific Inkscape window by exact title.

    Needed because a modal dialog may not be window 1, and its size bears no
    relation to the main window's, so clicking it by a fraction of the main
    window misses entirely.
    """
    nums = _osa_ints(
        f'tell application "System Events" to tell process "{APP}"\n'
        f'  repeat with w in windows\n'
        f'    if (name of w) is "{title}" then\n'
        f'      set p to position of w\n'
        f'      set s to size of w\n'
        f'      return (item 1 of p) & "," & (item 2 of p) & "," & '
        f'(item 1 of s) & "," & (item 2 of s)\n'
        f'    end if\n'
        f'  end repeat\n'
        f'  return ""\n'
        f'end tell')
    if len(nums) < 4:
        return None
    return {"x": nums[0], "y": nums[1], "w": nums[2], "h": nums[3]}


def window_count():
    try:
        return int(osa(f'tell application "System Events" to return '
                       f'(count of windows of process "{APP}")'))
    except RuntimeError:
        return 0


def desktop_size():
    """Logical size of the desktop, to turn window geometry into a fraction of
    the captured screen."""
    try:
        out = osa('tell application "Finder" to get bounds of window of desktop')
    except RuntimeError:
        out = ""
    nums = [int(float(v)) for v in re.findall(r"-?\d+", out)]
    if len(nums) < 4 or nums[2] <= 0 or nums[3] <= 0:
        raise RuntimeError(f"cannot read desktop bounds (got {out!r})")
    return nums[2], nums[3]


def screen_device():
    """avfoundation index of the "Capture screen" input.

    The index is not stable: it counts cameras first, so plugging in a display
    with a built-in camera renumbers the screen. It was 2 on the laptop display
    alone and 4 with a Studio Display attached. Discover it, never hardcode.
    """
    r = subprocess.run(["ffmpeg", "-hide_banner", "-f", "avfoundation",
                        "-list_devices", "true", "-i", ""],
                       capture_output=True, text=True)
    for line in r.stderr.splitlines():
        m = re.search(r"\[(\d+)\]\s+(.+?)\s*$", line)
        if m and "capture screen" in m.group(2).lower():
            return int(m.group(1))
    raise RuntimeError("no avfoundation 'Capture screen' device found")


def open_file_via_menu(path):
    """Open a file through File > Open, driving the GTK file chooser.

    Inkscape's chooser is a GTK dialog whose widgets have no accessible names,
    so the path is typed into the location bar (Ctrl+L) rather than navigated
    by clicking through folders.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    menu("File", "Open...")
    time.sleep(2.0)
    keystroke("l", "ctrl")                  # GTK "type a file name" location bar
    time.sleep(0.8)
    _type_codes(abs_path)
    time.sleep(0.8)
    press("enter")
    time.sleep(3.0)


def save_as(target):
    """Save the document as TARGET through File > Save As.

    TARGET may be a bare file name — saved into whatever folder the dialog is
    showing, which is the folder of the document that was opened — or a full
    path, typed into the location bar the leading "/" opens. Key codes again;
    the trailing Return accepts the Replace? prompt when the file exists.
    """
    target = os.path.expanduser(target)
    menu("File", "Save As...")
    time.sleep(1.5)
    keystroke("a", "cmd")
    time.sleep(0.3)
    _type_codes(target)
    time.sleep(0.5)
    press("enter")
    time.sleep(2.5)
    press("enter")                          # Replace? confirmation, if any
    time.sleep(1.5)


def quit_app():
    """Quit Inkscape and make sure it is gone.

    `osascript` asking the app to quit is the polite path, but Inkscape's
    process name is lowercase (`inkscape`) while the bundle is `Inkscape`, so
    `pkill -x Inkscape` silently matches nothing — which leaves stale windows
    and makes the next take's window queries wrong. Match case-insensitively.
    """
    subprocess.run(["osascript", "-e", 'tell application "Inkscape" to quit'],
                   capture_output=True)
    for _ in range(12):
        time.sleep(0.4)
        r = subprocess.run(["pgrep", "-fi", "Inkscape.app/Contents/MacOS/inkscape"],
                           capture_output=True, text=True)
        if not r.stdout.strip():
            return
    for pid in subprocess.run(["pgrep", "-fi", "Inkscape.app/Contents/MacOS/inkscape"],
                              capture_output=True, text=True).stdout.split():
        subprocess.run(["kill", "-9", pid], capture_output=True)
    time.sleep(1.5)


def prepare_dxf(cfg, work, setup="setup-open-dxf"):
    """Land Inkscape in the state a take expects, with the recorder stopped.

    Three setups exist:
      setup-open-dxf     import the project's DXF and frame it (the default —
                         the state s02 leaves the video in)
      setup-empty        a bare Inkscape window, so the take can show the import
      setup-file:<path>  open a hand-off file (the SVG a previous take ended on)

    This is the native-driver equivalent of a browser project's setup script.
    The fragile parts — normalising the file, waiting for windows, sizing them,
    and dismissing the importer's notices — live here rather than in a take.
    """
    src = os.path.expanduser(cfg.get("sourceFile") or
                             os.path.join(work, "ENT-164-bracket.dxf"))

    if setup == "setup-empty":
        quit_app()
        launch()
        time.sleep(1.0)
        set_window(WIN["x"], WIN["y"], WIN["w"], WIN["h"])
        time.sleep(1.5)
        press("s")
        time.sleep(0.5)
        return

    if setup.startswith("setup-file:"):
        p = setup.split(":", 1)[1]
        path = (os.path.expanduser(p) if p.startswith(("~", "/"))
                else os.path.join(work, p))
        if not os.path.exists(path):
            raise SystemExit(f"{setup}: {path} does not exist "
                             f"(record the earlier take first)")
        quit_app()
        launch(path)
        time.sleep(2.0)
        dismiss_notices()
        set_window(WIN["x"], WIN["y"], WIN["w"], WIN["h"])
        time.sleep(1.5)
        press("s")
        time.sleep(0.5)
        zoom_drawing()
        return

    if cfg.get("normaliseDxf"):
        norm = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "projects", cfg["slug"], "normalise-dxf.py")
        if not os.path.exists(norm):
            raise SystemExit(f"normaliseDxf is set but {norm} is missing")
        # Idempotent: always re-derive from the pristine .orig, so re-running
        # after a fresh Onshape export never shifts the geometry twice.
        orig = src + ".orig"
        if os.path.exists(orig):
            shutil.copy(orig, src)
        r = subprocess.run([sys.executable, norm, src, "--in-place"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"normalise-dxf failed: {r.stderr.strip()[:300]}")
        for line in r.stdout.strip().splitlines():
            print(f"  {line.strip()}")

    quit_app()
    # `launch` opens the file directly, which is what raises the DXF Input
    # dialog. Do NOT also drive File > Open: that opens a second document and
    # the dialog then belongs to the wrong window.
    launch(src)
    time.sleep(2.0)

    # The DXF Input dialog, over whatever window Inkscape chose. It fills the
    # window it is given, so click OK by fraction of *that* window.
    for _ in range(20):
        d = named_window_xywh("DXF Input")
        if d:
            click(d["x"] + int(d["w"] * 0.978), d["y"] + int(d["h"] * 0.973))
            break
        time.sleep(0.5)
    time.sleep(3.5)

    dismiss_notices()                       # "$PDMODE is ignored" note, if shown
    time.sleep(1.5)

    # Size the document window, then frame the part. Look it up by title because
    # after the dialogs close the window index can no longer be trusted.
    set_window(WIN["x"], WIN["y"], WIN["w"], WIN["h"])
    time.sleep(1.5)
    press("s")                              # select tool
    time.sleep(0.5)
    # Zoom via the menu, never a bare keystroke: the terminal reclaims focus
    # between osascript calls, so a plain key can land outside Inkscape. (Plain
    # "4" is Center Page and "5" is Grey Scale — sending those is what left the
    # view at 2% on a grey canvas.)
    zoom_drawing()
    try:
        print('  plate:', measure_plate())
    except Exception as e:
        print('  plate: not measured:', e)


def zoom_drawing(attempts=5):
    """View > Zoom > Zoom Drawing, surviving a modal that is still in the way."""
    for i in range(attempts):
        try:
            menu("View", "Zoom", "Zoom Drawing")
            time.sleep(1.5)
            return
        except RuntimeError:
            dismiss_notices(limit=3)
            time.sleep(0.8)
    menu("View", "Zoom", "Zoom Drawing")    # last attempt, let it raise
    time.sleep(1.5)


def menu_available():
    """True when the frontmost window has a document menu bar.

    Not "a menu bar exists": the importer's notice windows have a menu bar too
    (with just Inkscape/Help in it), so checking for the *View* item is what
    distinguishes a usable document window from a modal dialog.
    """
    try:
        n = osa(f'tell application "System Events" to tell process "{APP}" to tell '
                f'menu bar 1 to return (count of (menu bar items whose name is "View"))')
        return int(n) > 0
    except RuntimeError:
        return False


def dialog_windows():
    """Inkscape windows that are not the largest one (notices, dialogs)."""
    doc = document_window()
    out = []
    for i in range(1, window_count() + 1):
        try:
            g = window_xywh(i)
        except Exception:
            continue
        if not g or g["w"] < 150 or g["h"] < 80:
            continue
        if (g["x"], g["y"], g["w"], g["h"]) == (doc["x"], doc["y"], doc["w"], doc["h"]):
            continue
        out.append(g)
    return out


def dismiss_notices(limit=6):
    """Click OK on whatever modal is blocking the document's menus.

    A GTK notice fills the window it is given, and its single unnamed OK button
    sits at the bottom centre. The modal is always the frontmost window — the
    document window cannot be in front of it — and while it is frontmost the
    menu bar has no View item, which is the test for "still modal".
    """
    for _ in range(limit):
        if menu_available():
            return
        w = window_xywh(1) or document_window()
        click(w["x"] + w["w"] // 2, w["y"] + w["h"] - 23)
        time.sleep(1.0)


def _set_field(x, y, text):
    """Click a text field and replace its contents.

    GTK fields in these dialogs expose no accessible name, so select-all is
    done with the keyboard rather than by locating the widget. Two hard-won
    details: a single click does not put these fields into edit mode — only a
    double click does — and the unicode typing cliclick/osascript offer
    (`CGEventKeyboardSetUnicodeString`) is ignored by Inkscape's GTK entries.
    Virtual key codes are accepted, so type with those.
    """
    _cliclick(f"dd:{x},{y}")
    time.sleep(0.5)
    keystroke("a", "cmd")                  # select the existing value
    time.sleep(0.3)
    _type_codes(text)
    time.sleep(0.3)
    press("enter")
    time.sleep(0.5)


_KEYCODES_TEXT = {
    "a": 0, "b": 11, "c": 8, "d": 2, "e": 14, "f": 3, "g": 5, "h": 4, "i": 34,
    "j": 38, "k": 40, "l": 37, "m": 46, "n": 45, "o": 31, "p": 35, "q": 12,
    "r": 15, "s": 1, "t": 17, "u": 32, "v": 9, "w": 13, "x": 7, "y": 16, "z": 6,
    "0": 29, "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22, "7": 26,
    "8": 28, "9": 25, ".": 47, "-": 27, ",": 43, "_": 27, "/": 44, ":": 41,
    " ": 49,
}


def _type_codes(s, delay=0.05):
    """Type a string with virtual key codes (unicode injection is ignored).

    All the keystrokes go in *one* osascript call: one process per character is
    far too slow for a 100-character file path (~15s). Uppercase letters and the
    two shifted punctuation marks are sent with shift held.
    """
    lines = []
    for ch in s:
        code = _KEYCODES_TEXT.get(ch.lower())
        if code is None:
            raise ValueError(f"no key code for {ch!r}")
        shift = " using shift down" if (ch.isupper() or ch in "_:") else ""
        lines.append(f'  key code {code}{shift}')
        if delay:
            lines.append(f'  delay {delay}')
    osa('tell application "System Events"\n'
        f'  set frontmost of process "{APP}" to true\n'
        f'  delay 0.2\n'
        + "\n".join(lines) + "\nend tell")


def record(project, take, fps=30):
    """Record one take: ffmpeg screen capture around a paced action list."""
    cfg = json.load(open(os.path.join(project, "video.json")))
    work = os.path.expanduser(cfg["workDir"])
    takes = os.path.join(work, "takes")

    take_cfg = next(t for t in cfg["takes"] if t["name"] == take)
    spec = json.load(open(os.path.join(project, "takes", take + ".json")))
    load_timings(work)
    _set_take(take_cfg["scenes"])

    prepare_dxf(cfg, work, take_cfg.get("setup", "setup-open-dxf"))

    # Each scene's narration length, summed for this take.
    total = take_length(take_cfg["scenes"])
    tail = float(cfg.get("tail", 0.5))
    budget = total + tail + 2.0          # a little slack so nothing is clipped

    out_mp4 = os.path.join(takes, take + ".mp4")
    os.makedirs(takes, exist_ok=True)

    # ffmpeg captures the whole screen at the display's native pixel size —
    # 3024x1964 on this Retina panel, not the 1512x982 logical points AppleScript
    # reports — so the crop is expressed as a fraction of the captured frame
    # rather than in points. `-capture_cursor 1` keeps the pointer visible.
    w = document_window()
    sw, sh = desktop_size()
    d = {"x": w["x"] / sw, "y": w["y"] / sh, "w": w["w"] / sw, "h": w["h"] / sh}
    vf = (f"crop='trunc(iw*{d['w']:.6f})':'trunc(ih*{d['h']:.6f})':"
          f"'trunc(iw*{d['x']:.6f})':'trunc(ih*{d['y']:.6f})',"
          f"scale=1920:1080:force_original_aspect_ratio=decrease,"
          f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "avfoundation", "-capture_cursor", "1", "-framerate", str(fps),
           "-i", f"{screen_device()}:none", "-t", str(budget), "-vf", vf,
           "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", out_mp4]
    print(f"  recording {budget:.1f}s from {w['x']},{w['y']} {w['w']}x{w['h']} -> {out_mp4}")
    proc = subprocess.Popen(cmd)

    started_at = None
    while started_at is None:
        time.sleep(0.4)
        started_at = int(time.time() * 1000)
        break
    time.sleep(1.0)                     # let ffmpeg settle before the first click

    result = run_actions(spec.get("actions", []), t0=started_at)

    proc.wait(timeout=budget + 30)

    json.dump({"startedAt": started_at},
              open(os.path.join(takes, take + ".start.json"), "w"))
    json.dump({"ok": True, "value": {"t0": started_at, "marks": result["marks"]}},
              open(os.path.join(takes, take + ".exec.json"), "w"), indent=1)
    print(f"  {take}: {result['elapsed']:.1f}s, {len(result['marks'])} marks")

    # Save the state this take ended on, so the *next* take's setup can open it
    # instead of replaying every earlier step. Happens after the recorder stops,
    # so the save dialog is never in the video.
    end_save = take_cfg.get("endSave")
    if end_save:
        save_as(os.path.join(work, end_save))
        print(f"  hand-off: {end_save}")
    return out_mp4


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__,                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("launch"); p.add_argument("file")
    p = sub.add_parser("window"); p.add_argument("x", type=int); p.add_argument("y", type=int)
    p.add_argument("w", type=int); p.add_argument("h", type=int)
    p = sub.add_parser("shot"); p.add_argument("out")
    p = sub.add_parser("act"); p.add_argument("actions")
    p = sub.add_parser("record")
    p.add_argument("--project", required=True); p.add_argument("--take", required=True)

    args = ap.parse_args()

    if args.cmd == "launch":
        launch(args.file)
        print("window:", win_xywh())
    elif args.cmd == "window":
        set_window(args.x, args.y, args.w, args.h)
        print("window:", win_xywh())
    elif args.cmd == "shot":
        print(shot(args.out))
    elif args.cmd == "act":
        run_actions(json.loads(args.actions))
    elif args.cmd == "record":
        record(args.project, args.take)


if __name__ == "__main__":
    main()
