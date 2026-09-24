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
             "esc": 53, "escape": 53, "left": 123, "right": 124, "down": 125, "up": 126,
             "home": 115, "end": 119, "pageup": 116, "pagedown": 121}


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


def _menu_element_pos(expr):
    """Position and size (screen coords) of an AppleScript menu element."""
    out = osa(
        f'tell application "System Events" to tell process "{APP}"\n'
        f'  set p to position of {expr}\n'
        f'  set s to size of {expr}\n'
        f'  return (item 1 of p) & "," & (item 2 of p) & "," & '
        f'(item 1 of s) & "," & (item 2 of s)\n'
        f'end tell')
    nums = [int(v) for v in re.findall(r"-?\d+", out)]
    if len(nums) < 4 or nums[2] <= 0 or nums[3] <= 0:
        return None
    return nums[0], nums[1], nums[2], nums[3]


def _menu_centre(pos):
    return pos[0] + pos[2] // 2, pos[1] + pos[3] // 2


_MENUBAR_ORDER = ("Apple", "Inkscape", "File", "Edit", "View", "Layer",
                  "Object", "Path", "Text", "Filters", "Extensions", "Help")


def _menu_enabled_names(owner_expr):
    """Names of the enabled items of a menu, in display order.

    Separators and disabled items are left out because the arrow keys skip
    them, so this list's order *is* the order Down walks through.
    """
    out = osa(
        'tell application "System Events"\n'
        f'  tell process "{APP}"\n'
        '    set out to ""\n'
        f'    repeat with mi in (every menu item of {owner_expr})\n'
        '      try\n'
        '        if (enabled of mi) is true then set out to out & (name of mi) & linefeed\n'
        '      end try\n'
        '    end repeat\n'
        '  end tell\n'
        '  return out\n'
        'end tell')
    return [line.strip() for line in out.splitlines() if line.strip()]


def _key_codes(codes, gap=0.1):
    """Send virtual key codes in one osascript call (a process per key is slow)."""
    lines = []
    for code in codes:
        lines.append(f'  key code {code}')
        if gap:
            lines.append(f'  delay {gap}')
    osa(
        'tell application "System Events"\n'
        f'  set frontmost of process "{APP}" to true\n'
        f'  delay 0.15\n'
        + "\n".join(lines) + "\nend tell"
    )


def _menu_atomic(*items):
    """Select a menu path in a single event — fast, and invisible on screen."""
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


def menu(*items, key_gap=0.12):
    """Walk the menu bar with the keyboard, so the dropdowns show on camera.

    menu("File", "Open...")                    -> File > Open...
    menu("View", "Zoom", "Zoom Drawing")       -> View > Zoom > Zoom Drawing

    AppleScript's `click menu item … of menu 1 of …` selects the whole path in
    one event: the dropdown is on screen for a single frame at most, so a
    recording looks like nothing happened. Menu *bar* item positions cannot be
    clicked reliably either — System Events reports them in a space that does
    not match where clicks land — so this drives the menus the way a person
    does: Control+F2 arms the menu bar (its Apple menu highlights, no list
    opens), Right walks the titles, Down opens the requested one, and Down/Up
    counts come from the item names System Events reports for the open menu.
    Each step leaves the menu on screen, so the recording shows it.
    """
    if len(items) < 2:
        raise ValueError("menu() needs at least a menu bar item and a menu item")

    def normalized(name):
        return name.replace("\u2026", "...").strip().lower()

    wanted = [normalized(i) for i in items]
    if items[0] not in _MENUBAR_ORDER:
        _menu_atomic(*items)
        return
    raise_app()
    time.sleep(0.35)
    # Arm the menu bar by clicking the Apple menu — a real click at the far left
    # always lands, and it puts the bar under the keyboard. (Control+F2 works
    # when sent by hand but was dropped mid-take, and the Right keys then nudged
    # the selection instead of walking the titles.) The Apple list flashes for a
    # moment; the first Right closes it and moves along the bar.
    for attempt in range(2):
        _cliclick("m:20,16", "c:20,16")     # arm: one process
        time.sleep(0.25)
        if _MENUBAR_ORDER.index(items[0]):
            _key_codes([124] * _MENUBAR_ORDER.index(items[0]), gap=0.08)
        time.sleep(0.2)
        _key_codes([125], gap=0)             # opens the title's menu
        time.sleep(0.25)
        owner = f'menu 1 of menu bar item "{items[0]}" of menu bar 1'
        try:
            for depth, target in enumerate(wanted[1:], start=1):
                # The first query can land before the menu has rendered; poll.
                names = []
                for _ in range(6):
                    names = [normalized(n) for n in _menu_enabled_names(owner)]
                    if names:
                        break
                    time.sleep(0.15)
                if target not in names:
                    raise RuntimeError(f"{target!r} is not in {' > '.join(items[:depth])}")
                steps = names.index(target)
                if depth == len(items) - 1:
                    _key_codes([125] * steps + [36], gap=key_gap)
                else:
                    _key_codes([125] * steps + [124], gap=key_gap)
                    time.sleep(0.25)
                    owner = f'menu 1 of menu item "{items[depth]}" of {owner}'
            return
        except Exception as e:
            print(f"  menu {items[0]!r}: retrying ({e})")
            press("esc")
            time.sleep(0.3)
    _menu_atomic(*items)


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


# The dock's left edge that every panel offset in this file was measured
# against. The recordings normalise the dock to it at setup time.
DOCK_LEFT = 988


def set_dock_width(target=DOCK_LEFT, tries=4):
    """Make sure the right dock is no wider than TARGET.

    Inkscape does not restore the dock's width reliably between launches: a new
    window comes up with the default, ~708 px dock, and the whole point of the
    narrower panel is a video where it does not dominate the screen. Dragging
    the divider with synthetic events is hit-and-miss (the grab area is a few
    px, and some sessions refuse it entirely), but shrinking the window forces
    the paned widget to squeeze the dock, and restoring the window keeps the
    narrower width. That is the normalisation: no saved state, no divider drag.

    A dock that is already narrower than the target is left alone — every panel
    point is an offset from the dock's left edge, so it tracks whatever width
    the dock happens to have.

    Fill and Stroke is raised first: the pane cannot squeeze below the widest
    dialog's minimum, and a restored Align and Distribute is the widest, so
    without this the squeeze stalls at the wide width.
    """
    if dock_left() >= target - 8:
        return
    menu("Object", "Fill and Stroke...")
    time.sleep(0.8)
    for _ in range(tries):
        left = dock_left()
        if left >= target - 8:
            break
        narrow = max(900, int(WIN["w"] - (target - left)))
        set_window(WIN["x"], WIN["y"], narrow, WIN["h"])
        time.sleep(1.0)
        set_window(WIN["x"], WIN["y"], WIN["w"], WIN["h"])
        time.sleep(1.0)
    print(f"  dock left at {dock_left():.0f} (target {target})")


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

    Takes the start of the longest run of dark columns, not the leftmost dark
    column: the page's drop shadow is a dark sliver sitting left of the dock in
    the same rows, and a leftmost test reports the shadow (~x 648) instead of
    the dock (~x 819), which moves every panel click ~170 px off.
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
    dark = (band.sum(2) < 330).mean(0) > 0.5
    runs, start = [], None
    for i, v in enumerate(dark):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(dark) - 1))
    runs = [(r0, r1) for r0, r1 in runs if (r1 - r0 + 1) / s >= 100]
    if not runs:
        raise RuntimeError("dock_left: no dock found")
    left = max(runs, key=lambda r: r[1] - r[0])[0] / s
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
    "panel:fill": (71, 172),
    "panel:strokepaint": (145, 172),
    "panel:strokestyle": (243, 172),
    "panel:x": (55, 206),           # the ✕ (no paint) button, on both tabs
    "panel:flat": (81, 206),        # flat colour, second button of the row
    "panel:unit": (243, 208),
    "panel:hairline": (243, 401),
    "panel:docktab": (293, 145),
    "panel:mode": ("right", 242),
    "panel:mode-rgb": ("right", 297),
    # panel:rgb-r/g/b are not here: the colour section scrolls under the
    # take's own steps, so those rows are located per use by rgb_field_y().
    "panel:opacity": ("right", 771),
    # Align and Distribute's two centring buttons. Six ~26 px icons per row put
    # them at +109; the row order is Inkscape's — "Centre on vertical axis"
    # (moves the selection left/right) is the upper row, "Centre on horizontal
    # axis" (moves it up/down) below it. Verified on 1.4.4 by clicking and
    # reading the objects' x/y back, at two dock widths — which is why these
    # are offsets and not absolutes: the dock's width is not reliably restored
    # across launches (988 in one session, 804 in the next), while the panel's
    # content is anchored a fixed distance from its left edge.
    "align:centre-v": (109, 329),
    "align:centre-h": (109, 363),
}


def _slider_rows(a):
    """y of each channel's slider row in a screenshot, from its gradient.

    Inkscape draws a channel slider as a gradient of that channel, so between
    its left and right ends that channel rises from its current value to its
    maximum: the red row is the one whose red rises most, and so on. Returns
    {channel: y or None} for the R, G and B rows of the Stroke paint tab.
    """
    s = a.shape[0] / WIN["h"]
    x0, x1 = int(950 * s), int(1400 * s)
    out = {}
    for idx, name in ((0, "r"), (1, "g"), (2, "b")):
        best, run = None, []
        for y in range(int(240 * s), int(470 * s)):
            d = [a[y, x1][i] - a[y, x0][i] for i in range(3)]
            ok = (d[idx] >= 80
                  and d[idx] - max(d[i] for i in range(3) if i != idx) >= 30)
            if ok:
                run.append(y)
            elif run:
                if best is None or len(run) > len(best):
                    best = run
                run = []
        if run and (best is None or len(run) > len(best)):
            best = run
        out[name] = (None if not best or len(best) < 10
                     else (best[0] + best[-1]) / 2 / s)
    return out


def _grab():
    """Screenshot the document window into an RGB array."""
    import tempfile
    from PIL import Image
    import numpy as np

    fd, path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    try:
        shot(path)
        return np.asarray(Image.open(path).convert('RGB')).astype(int)
    finally:
        os.unlink(path)


def _mode_is_rgb():
    """True when all three R/G/B channel sliders are showing.

    That is uniquely RGB mode among the modes Inkscape offers (HSLuv shows
    H/S/L/A, CMYK shows its own four channels).
    """
    rows = _slider_rows(_grab())
    return all(rows[c] is not None for c in ("r", "g", "b"))


def select_rgb_mode(tries=3):
    """Switch the Stroke paint colour mode to RGB, verifying it.

    A click opens the mode list, but the synthetic Home/Down/Return keys do not
    always reach the popup (an override-redirect window whose grab is not always
    in place when the keys arrive), so whether the selection took is checked by
    looking for the three channel sliders, and the whole sequence is retried.
    Each attempt starts with a click on Flat colour: it is where the take was
    anyway, and it dismisses a list left open by a failed attempt.
    """
    for _ in range(tries):
        click(*to_screen(*panel_point("panel:flat")))
        time.sleep(0.4)
        click(*to_screen(*panel_point("panel:mode")))
        time.sleep(0.6)
        for key in ("home", "down", "down", "return"):
            press(key)
            time.sleep(0.2)
        time.sleep(0.5)
        if _mode_is_rgb():
            return
    raise RuntimeError(f"select_rgb_mode: RGB not showing after {tries} tries")


def rgb_field_y(channel):
    """y of the R, G or B numeric field on the Stroke paint tab.

    The colour section scrolls — switching the colour mode can leave it
    scrolled — so the fixed y in _PANEL_OFFSETS is only right part of the time.
    The rows come from _slider_rows(), i.e. from the sliders themselves. The
    flow sets R, then G, then B starting from black, so the channel being set
    is never already flat when it is looked up.
    """
    y = _slider_rows(_grab()).get(channel)
    if y is None:
        raise RuntimeError(f"rgb_field_y({channel!r}): no {channel} slider found")
    print(f"  {channel} field row at {y:.0f}")
    return y


def dxf_dialog_point(name):
    """A point inside the DXF Input dialog, as a fraction of that window.

    The dialog is ~526x490 at the window's top-left, not a full-window sheet, so
    document-window coordinates cannot address it; it can also end up behind the
    document window, so it is raised before the point is returned. Returns
    screen coordinates: the caller must not add the window origin again.
    """
    fracs = {
        "dxf:read-from-file": (0.624, 0.280),   # the radio, already default
        "dxf:ok": (0.912, 0.959),
    }
    if name not in fracs:
        raise ValueError(f"unknown DXF dialog point {name!r}")
    # It appears a moment after File > Open accepts the path.
    w = None
    for _ in range(20):
        w = named_window_xywh("DXF Input")
        if w:
            break
        time.sleep(0.5)
    if not w:
        raise RuntimeError("DXF Input dialog did not appear")
    try:
        osa(f'tell application "System Events" to tell process "{APP}" to '
            f'perform action "AXRaise" of window "DXF Input"')
    except RuntimeError:
        pass
    time.sleep(0.3)
    w = named_window_xywh("DXF Input") or w
    fx, fy = fracs[name]
    return w["x"] + int(w["w"] * fx), w["y"] + int(w["h"] * fy)


def palette_point(name):
    """A colour on the window's palette strip, found by its colour.

    The palette sits at a fixed place at the bottom of the window, but the x of
    a colour is not stable across palette changes (the strip reorders and
    scrolls), so it is located from its colour on each use. Shift-clicking a
    swatch sets the *stroke*; a plain click sets the fill.

    This is the stroke-colour route the take uses: typing into the Fill and
    Stroke RGB fields needs those fields' positions, and the dialog's colour
    section scrolls between the mode switch and the fields, so the fields move
    under the take's own steps. The palette does not move with the panel.
    """
    import tempfile
    from PIL import Image
    import numpy as np

    targets = {"palette:red": (255, 0, 0), "palette:black": (0, 0, 0)}
    if name not in targets:
        raise ValueError(f"unknown palette colour {name!r}")
    fd, path = tempfile.mkstemp(suffix='.png')
    os.close(fd)
    try:
        shot(path)
        a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    finally:
        os.unlink(path)
    s = a.shape[0] / WIN["h"]
    strip = a[int(755 * s):int(840 * s), :]
    tr, tg, tb = targets[name]
    d = (strip[:, :, 0] - tr) ** 2 + (strip[:, :, 1] - tg) ** 2 + (strip[:, :, 2] - tb) ** 2
    iy, ix = np.unravel_index(np.argmin(d), d.shape)
    x, y = ix / s, (int(755 * s) + iy) / s
    print(f"  {name} at {x:.0f},{y:.0f} ({tuple(strip[iy, ix])})")
    return x, y


def panel_point(name):
    """A named Fill and Stroke / Align widget position, in window coordinates."""

    if name in ("panel:rgb-r", "panel:rgb-g", "panel:rgb-b"):
        # These rows move with the panel's scroll; find them before each use.
        return 1456, rgb_field_y(name[-1])
    off = _PANEL_OFFSETS.get(name)
    if off is None:
        raise ValueError(f"unknown panel point {name!r}")
    dx, y = off
    if dx == "right":
        return 1456, y
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
    # does not depend on the zoom or on which dock dialogs are open. DXF dialog
    # points come back in screen space already, because that dialog is not the
    # document window.
    screen_coords = False
    if kind in ("click", "sclick", "rclick", "dd", "move"):
        if isinstance(v[0], str):
            if v[0].startswith("dxf:"):
                v = list(dxf_dialog_point(v[0]))
                screen_coords = True
            else:
                v = list(palette_point(v[0]) if v[0].startswith("palette:")
                         else panel_point(v[0]) if v[0].startswith(("panel:", "align:"))
                         else plate_point(v[0]))
    elif kind == "drag":
        if isinstance(v[0], str):
            a, b = plate_point(v[0]), plate_point(v[1])
            v = [a[0], a[1], b[0], b[1]]

    if kind == "mark":
        marks.append({"n": v, "rel": int((time.time() - started) * 1000),
                      "wall": int(time.time() * 1000)})
    elif kind == "click":
        x, y = v if screen_coords else to_screen(*v)
        click(x, y)
    elif kind == "rclick":
        x, y = v if screen_coords else to_screen(*v)
        right_click(x, y)
    elif kind == "sclick":
        x, y = v if screen_coords else to_screen(*v)
        shift_click(x, y)
    elif kind == "dd":
        # double-click: the only way Inkscape's spin/combo widgets take focus
        x, y = v if screen_coords else to_screen(*v)
        _cliclick(f"dd:{int(round(x))},{int(round(y))}")
    elif kind == "drag":
        x1, y1 = to_screen(v[0], v[1])
        x2, y2 = to_screen(v[2], v[3])
        drag(x1, y1, x2, y2)
    elif kind == "move":
        x, y = v if screen_coords else to_screen(*v)
        move(x, y)
    elif kind == "type":
        type_text(v)
    elif kind == "typecodes":
        _type_codes(v)
    elif kind == "dismiss":
        dismiss_notices()
    elif kind == "rgbmode":
        select_rgb_mode()
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
        dismiss_startup()                   # the startup dialog covers the menu bar
        time.sleep(1.0)
        set_window(WIN["x"], WIN["y"], WIN["w"], WIN["h"])
        time.sleep(1.5)
        set_dock_width()
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
        dismiss_startup()
        time.sleep(2.0)
        dismiss_notices()
        set_window(WIN["x"], WIN["y"], WIN["w"], WIN["h"])
        time.sleep(1.5)
        set_dock_width()
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
    set_dock_width()
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


def dismiss_startup():
    """Close Inkscape's startup dialog, which is modal and covers the menu bar.

    It reappears on every launch unless its "Show this every time" box is
    unticked, so that is done first; then New Document opens the blank window
    the setups expect. Both are clicked by fraction of the dialog window, which
    is ~752x675 — any window that large is the document instead, and then there
    is nothing to do.
    """
    if menu_available():
        return
    w = window_xywh(1)
    if not w or w["w"] > 900 or w["h"] > 800:
        return
    # Untick "Show this every time", then press New Document.
    for fx, fy, note in ((0.082, 0.926, "show-every-time"), (0.842, 0.926, "new-document")):
        click(w["x"] + int(w["w"] * fx), w["y"] + int(w["h"] * fy))
        time.sleep(1.2)
        print(f"  startup dialog: {note}")
    for _ in range(10):
        if menu_available():
            time.sleep(1.0)
            return
        time.sleep(0.5)


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


def _notice_window():
    """Geometry of the importer's notice window, if one is up.

    It is a small **untitled** window of its own — the document window is
    "<file> - Inkscape", the DXF Input dialog is named "DXF Input", and tooltips
    are under 300 px. `menu_available()` is not a test for it: a notice that
    does not fill the document window leaves the menu bar reachable, so the
    menu bar shows View even while the notice is up.
    """
    for i in range(1, window_count() + 1):
        g = window_xywh(i)
        if not g or g["w"] < 300 or g["h"] < 300:
            continue
        if g["w"] > 900 or g["h"] > 800:
            continue                       # the document window
        try:
            name = osa(f'tell application "System Events" to tell process "{APP}" '
                       f'to get name of window {i}')
        except RuntimeError:
            name = ""
        if not name.strip():
            return g
    return None


def dismiss_notices(limit=6):
    """Click OK on the importer's notice window, if one is up.

    The notice comes in two shapes: when Inkscape is launched onto a file it
    fills the document window and blocks the menu bar (tested with
    `menu_available()`), while a File > Open import gets a small untitled dialog
    of its own that leaves the menu bar reachable (found by `_notice_window()`).
    In both, the OK button is at the bottom centre, but how far above the bottom
    varies with the window (h-23 for the full-window form, h-63 for the small
    one), so try a ladder of offsets; a click into the dialog's empty area does
    nothing.
    """
    for _ in range(limit):
        if not menu_available():
            w = window_xywh(1)
            if w:
                click(w["x"] + w["w"] // 2, w["y"] + w["h"] - 23)
                time.sleep(1.0)
                continue
        w = _notice_window()
        if not w:
            return
        for dy in (23, 45, 63):
            click(w["x"] + w["w"] // 2, w["y"] + w["h"] - dy)
            time.sleep(0.8)
            if not _notice_window():
                time.sleep(0.5)
                return


def _set_field(x, y, text):
    """Click a text field and replace its contents.

    GTK fields in these dialogs expose no accessible name, so select-all is
    done with the keyboard rather than by locating the widget. Three hard-won
    details: a single click does not put these fields into edit mode — only a
    double click does; the unicode typing cliclick/osascript offer
    (`CGEventKeyboardSetUnicodeString`) is ignored by Inkscape's GTK entries, so
    type with virtual key codes; and select-all there is **Control**+A, not
    Command+A — Cmd+A is the canvas's Select All, so with Cmd+A the digits are
    *inserted* into the old value and Enter reverts it (a "0" field typed as
    "255" became "2550" → rejected), which looks like the click missed.
    """
    _cliclick(f"dd:{x},{y}")
    time.sleep(0.5)
    keystroke("a", "ctrl")                 # select the existing value
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
    "~": 50, " ": 49,
}


def _type_codes(s, delay=0.02):
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
        shift = " using shift down" if (ch.isupper() or ch in "_~:") else ""
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
    # Slack for the menus, which are driven visibly (open, arrow, Enter) and so
    # take seconds rather than a fraction of one. The film is cut to the
    # narration, so the extra recording is discarded, not shown.
    budget = total + tail + 8.0

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
