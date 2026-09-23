#!/usr/bin/env python3
"""The AI review tier — advisory only, and only where a person was going to look.

Two jobs, both of which a person currently does by hand:

  1. An Onshape share link: open it, screenshot the sketch, and compare what is
     on screen with the submitted DXF. This catches the one thing the DXF
     cannot prove — that the file came from this document.
  2. A photo of a cut part: check it shows the profile and the holes the file
     describes.

Both write a *note* onto the report. Neither posts to Canvas, and neither can
turn a `review` into a pass: a human still signs. The output is a suggestion
with its evidence, so the reviewer can overrule it in one glance.

    python3 canvas/ai_review.py --task cad-03-cut-a-hole --student "Jane Doe"
    python3 canvas/ai_review.py --task cad-03-cut-a-hole --all --dry-run

Needs the opencode CLI (`opencode run`) for the vision step and browser-control
for the screenshot. Without either, it says so and does nothing — it must never
be the reason a report cannot be produced.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent.parent / "skills" / "maker-tasks" / "check"))

import runner  # noqa: E402

DEFAULT_WORKDIR = Path.home() / "ent164" / "grading"

PROMPT_COMPARE = """\
You are checking a student's CAD submission. Two images are attached:
  (1) a screenshot of the Onshape document they linked,
  (2) a rendering of the DXF file they handed in.

Answer only from what is visible. If you cannot tell, say so.

Reply with JSON only:
{"same_shape": true|false, "notes": "<one sentence>", "confidence": 0.0-1.0}
"same_shape" is true only if the outline and the holes match in shape and rough
proportion. Ignore colour, line width, zoom and background.
"""

PROMPT_PHOTO = """\
You are checking a photo of a laser-cut part a student made. The student's DXF
describes this part: {spec}

Look at the photo. Answer only from what is visible.

Reply with JSON only:
{"shows_part": true|false, "visible_features": "<short list>", "confidence": 0.0-1.0}
"""


def have(cmd) -> bool:
    return shutil.which(cmd) is not None


def opencode_json(prompt: str, images: list, model: str | None = None) -> dict | None:
    """Ask opencode for a JSON verdict over the images."""
    if not have("opencode"):
        return None
    cmd = ["opencode", "run", "--format", "json"]
    if model:
        cmd += ["--model", model]
    args = list(cmd)
    for image in images:
        args.append(f"@{image}")
    args.append(prompt)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=180)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.strip()
    # opencode --format json emits events; take the last JSON object with our keys.
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("text", "content", "result"):
            if isinstance(data.get(key), str) and "confidence" in data[key]:
                data = _extract(data[key])
                break
        if isinstance(data, dict) and "confidence" in data:
            return data
    return _extract(text)


def _extract(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def screenshot_onshape(url: str, target: Path, session: str = "onshape-review") -> bool:
    """Screenshot an Onshape share link through browser-control."""
    if not have("browser-control"):
        return False
    script = f"""
    const {{ chromium }} = require('playwright');
    (async () => {{
      const browser = await chromium.connectOverCDP(process.env.CDP_URL);
      const ctx = browser.contexts()[0] || await browser.newContext();
      const page = await ctx.newPage();
      await page.setViewportSize({{ width: 1600, height: 1000 }});
      await page.goto({json.dumps(url)}, {{ waitUntil: 'domcontentloaded', timeout: 60000 }});
      await page.waitForTimeout(9000);
      await page.screenshot({{ path: {json.dumps(str(target))} }});
      await page.close();
      process.exit(0);
    }})().catch(() => process.exit(1));
    """
    try:
        proc = subprocess.run(
            ["browser-control", "run", "--session", session, "node", "-e", script],
            capture_output=True,
            text=True,
            timeout=150,
        )
        return proc.returncode == 0 and target.exists()
    except (subprocess.TimeoutExpired, OSError):
        return False


def load_report(folder: Path) -> dict | None:
    path = folder / "check-report.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_note(folder: Path, note: dict) -> None:
    path = folder / "ai-review.json"
    existing = json.loads(path.read_text()) if path.exists() else []
    existing.append(note)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

    text_path = folder / "ai-review.txt"
    with open(text_path, "a", encoding="utf-8") as fh:
        fh.write(f"[{note['kind']}] {note['verdict']} (confidence {note.get('confidence','?')})\n")
        if note.get("notes"):
            fh.write(f"    {note['notes']}\n")
        fh.write("    This is a suggestion with its evidence. A person decides.\n\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ai_review")
    parser.add_argument("--task", "-t", required=True)
    parser.add_argument("--workdir", default=str(DEFAULT_WORKDIR))
    parser.add_argument("--student")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", help="model id for the vision step")
    args = parser.parse_args(argv)

    try:
        task = runner.load_task(args.task)
    except runner.TaskError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    workdir = Path(args.workdir).expanduser() / task["id"]
    if not workdir.exists():
        print(f"error: no reports in {workdir}", file=sys.stderr)
        return 2

    folders = [p for p in sorted(workdir.iterdir()) if p.is_dir() and load_report(p)]
    if args.student:
        folders = [p for p in folders if args.student.lower() in p.name.lower()]

    if not have("opencode"):
        print("opencode is not on PATH — skipping the AI tier. Reports stand as they are.")
    if not have("browser-control"):
        print("browser-control is not on PATH — cannot screenshot Onshape links.")

    count = 0
    for folder in folders:
        report = load_report(folder)
        manifest = report.get("manifest") or {}
        sub = runner.load_submission(folder) if (folder / "part.dxf").exists() else None
        files = list(folder.iterdir())

        # 1. the Onshape link
        url = manifest.get("onshape_url") or _manifest_value(folder, "onshape_url")
        if url and have("opencode") and have("browser-control"):
            shot = folder / "onshape-screenshot.png"
            if args.dry_run:
                print(f"  would screenshot {url[:60]}… for {folder.name}")
            elif not shot.exists() and screenshot_onshape(url, shot):
                render = folder / "dxf-render.png"
                if not render.exists():
                    _render_dxf(folder / "part.dxf", render)
                verdict = opencode_json(PROMPT_COMPARE, [shot, render], args.model)
                if verdict:
                    save_note(
                        folder,
                        {
                            "kind": "onshape_link",
                            "verdict": "matches" if verdict.get("same_shape") else "does not match",
                            "confidence": verdict.get("confidence"),
                            "notes": verdict.get("notes", ""),
                            "evidence": [shot.name, render.name],
                        },
                    )
                    print(f"  link check {folder.name}: {verdict.get('notes','')[:70]}")
                    count += 1
            elif shot.exists():
                print(f"  {folder.name}: screenshot already there")

        # 2. a photo of the part
        photos = [f for f in files if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        photos = [f for f in photos if "screenshot" not in f.name and "render" not in f.name]
        if photos and have("opencode"):
            if args.dry_run:
                print(f"  would review {photos[0].name} for {folder.name}")
                continue
            prompt = PROMPT_PHOTO.replace("{spec}", task.get("spec", "").strip())
            verdict = opencode_json(prompt, [photos[0]], args.model)
            if verdict:
                save_note(
                    folder,
                    {
                        "kind": "cut_photo",
                        "verdict": "shows the part" if verdict.get("shows_part") else "unclear or does not show the part",
                        "confidence": verdict.get("confidence"),
                        "notes": verdict.get("visible_features", ""),
                        "evidence": [photos[0].name],
                    },
                )
                print(f"  photo check {folder.name}: {verdict.get('visible_features','')[:70]}")
                count += 1
        elif not photos:
            print(f"  {folder.name}: no photo to review (expected for CAD-only tasks)")

    print()
    print(f"{count} advisory note(s) written. They suggest; a person signs.")
    if count:
        print("Read them with: cat <student>/ai-review.txt")
    return 0


def _manifest_value(folder: Path, key: str):
    for name in ("manifest.md", "manifest.txt"):
        path = folder / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().lower().startswith(key):
                return line.split(":", 1)[1].strip()
    return None


def _render_dxf(dxf: Path, target: Path) -> bool:
    """Render a DXF to PNG for the comparison. Uses the checker's own geometry
    so the picture is of what the laser would receive."""
    if not dxf.exists():
        return False
    try:
        script = f"""
import sys
sys.path.insert(0, {json.dumps(str(HERE.parent.parent.parent / "skills" / "maker-tasks" / "check"))})
import dxf_reader
from PIL import Image, ImageDraw
d = dxf_reader.read({json.dumps(str(dxf))})
b = d.bounds(); w, h = b[2]-b[0], b[3]-b[1]
scale = min(900.0/max(w,1), 700.0/max(h,1))
img = Image.new("RGB", (int(w*scale)+40, int(h*scale)+40), "white")
dr = ImageDraw.Draw(img)
for e in d.entities:
    pts = [(20+(x-b[0])*scale, img.height-20-(y-b[1])*scale) for x, y in e.points]
    if len(pts) > 1:
        dr.line(pts, fill="black", width=3)
    if e.is_circle:
        dr.line(pts+[pts[0]], fill="black", width=3)
img.save({json.dumps(str(target))})
print("ok")
"""
        proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
        return proc.returncode == 0 and target.exists()
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
