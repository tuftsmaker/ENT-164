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
    _cliclick("-e", str(int(dur * 1000)), f"m:{x},{y}")


def click(x, y, dur=0.35):
    move(x, y, dur)
    _cliclick(f"c:{x},{y}")


def right_click(x, y, dur=0.35):
    move(x, y, dur)
    _cliclick(f"rc:{x},{y}")


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
    osa(
        f'tell application "System Events" to tell process "{APP}"\n'
        f'  set position of window 1 to {{{x}, {y}}}\n'
        f'  set size of window 1 to {{{w}, {h}}}\n'
        f'end tell'
    )


def launch(path, timeout=60):
    """Open Inkscape on a file, and wait until its window is actually usable.

    "A window exists" is not enough: the menu bar is unavailable until the app
    has finished starting, and clicking it too early throws "Can't get menu bar
    item". So wait for the menu bar itself, not just a window count.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    subprocess.run(["open", "-a", "Inkscape", abs_path], check=True)
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
    raise RuntimeError(f"Inkscape not ready on {abs_path} within {timeout}s (last: {last})")


def to_screen(x, y):
    """Canvas coords are given relative to the window; convert for input."""
    w = win_xywh()
    return w["x"] + x, w["y"] + y


def shot(out_png):
    w = win_xywh()
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
    return _TIMINGS[scene]["sentences"][sent]["start"] + off


def _apply(op, marks, started):
    kind = next(iter(op))
    v = op[kind]
    if kind == "mark":
        marks.append({"n": v, "rel": int((time.time() - started) * 1000),
                      "wall": int(time.time() * 1000)})
    elif kind == "click":
        x, y = to_screen(*v)
        click(x, y)
    elif kind == "rclick":
        x, y = to_screen(*v)
        right_click(x, y)
    elif kind == "drag":
        x1, y1 = to_screen(v[0], v[1])
        x2, y2 = to_screen(v[2], v[3])
        drag(x1, y1, x2, y2)
    elif kind == "move":
        x, y = to_screen(*v)
        move(x, y)
    elif kind == "type":
        type_text(v)
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
    type_text(abs_path)
    time.sleep(0.8)
    press("enter")
    time.sleep(3.0)


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


def prepare_dxf(cfg, work):
    """Land Inkscape on the project's DXF, framed, with the recorder stopped.

    This is the native-driver equivalent of a browser project's setup script.
    The fragile parts — waiting for windows, sizing them, and dismissing the
    importer's notices — live here rather than in a take.

    Window handling matters: a GTK modal cannot be resized to a target, and
    clicking by fraction of *that* window is the only way to hit its unnamed
    controls. So we size the main window, then treat the dialog as its own
    coordinate space.
    """
    src = os.path.expanduser(cfg.get("sourceFile") or
                             os.path.join(work, "ENT-164-bracket.dxf"))

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

    dismiss_dialog()                        # "$PDMODE is ignored" note, if shown
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
    menu("View", "Zoom", "Zoom Drawing")
    time.sleep(1.5)


def dismiss_dialog():
    """Click whatever modal Inkscape is showing, if any.

    The DXF importer and several other steps end with a one-button notice whose
    button has no accessible name (GTK), so click it by position within the
    window instead.
    """
    w = win_xywh()
    click(w["x"] + w["w"] // 2, w["y"] + w["h"] - 23)


def _set_field(x, y, text):
    """Click a text field and replace its contents.

    GTK fields in these dialogs expose no accessible name, so select-all is
    done with the keyboard rather than by locating the widget.
    """
    click(x, y)
    time.sleep(0.3)
    raise_app()
    keystroke("a", "cmd")                  # select the existing value
    time.sleep(0.2)
    type_text(text)
    time.sleep(0.2)


def record(project, take, fps=30):
    """Record one take: ffmpeg screen capture around a paced action list."""
    cfg = json.load(open(os.path.join(project, "video.json")))
    work = os.path.expanduser(cfg["workDir"])
    takes = os.path.join(work, "takes")

    take_cfg = next(t for t in cfg["takes"] if t["name"] == take)
    spec = json.load(open(os.path.join(project, "takes", take + ".json")))
    load_timings(work)

    prepare_dxf(cfg, work)

    # Each scene's narration length, summed for this take.
    total = sum(_TIMINGS[s]["duration"] for s in take_cfg["scenes"])
    tail = float(cfg.get("tail", 0.5))
    budget = total + tail + 2.0          # a little slack so nothing is clipped

    out_mp4 = os.path.join(takes, take + ".mp4")
    os.makedirs(takes, exist_ok=True)

    # ffmpeg captures the window region and scales to the pipeline's 1920x1080.
    w = win_xywh()
    vf = (f"crop={w['w']}:{w['h']}:{w['x']}:{w['y']},"
          f"scale=1920:1080:force_original_aspect_ratio=decrease,"
          f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "avfoundation", "-capture_cursor", "1", "-framerate", str(fps),
           "-i", "2:none", "-t", str(budget), "-vf", vf,
           "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", out_mp4]
    print(f"  recording {budget:.1f}s -> {out_mp4}")
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
    return out_mp4


# ------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
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
