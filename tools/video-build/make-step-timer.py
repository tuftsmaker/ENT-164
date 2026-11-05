#!/usr/bin/env python3
"""Render the 90-minute step timer for Class 9's brainstorm sprint.

The deck (classes/class-09/slides.html, slide 10) sets four steps for the
sprint: 15 / 15 / 15 / 45 minutes. This turns that agenda into a full-screen
video to run on the projector while teams work.

ffmpeg here has no drawtext (no freetype), so every frame is drawn with PIL and
the video is encoded from those frames.

    python3 tools/video-build/make-step-timer.py --preview DIR   # four stills
    python3 tools/video-build/make-step-timer.py                 # full render

Output: classes/class-09/brainstorm-steps-timer.mp4
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "classes" / "class-09" / "brainstorm-steps-timer.mp4"

W, H = 1920, 1080
FPS = 5                     # output frame rate; frames are drawn once per second
TRANSITION = 5              # seconds of "time's up" between steps
END_CARD = 10               # seconds of closing card

INK = (13, 21, 38)
TEXT = (23, 32, 58)
MUTED = (95, 107, 122)
MUTED_2 = (63, 74, 90)
BLUE = (31, 111, 208)
BLUE_LIGHT = (62, 142, 222)
TINT = (242, 247, 253)
TINT_2 = (234, 243, 253)
LINE = (230, 234, 241)
LINE_STRONG = (213, 220, 231)
PAPER = (255, 255, 255)
AMBER = (180, 83, 9)
RED = (185, 28, 28)
GREEN = (22, 128, 84)

FONTS = "/System/Library/Fonts/Supplemental/"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "Arial Bold.ttf" if bold else "Arial.ttf"
    return ImageFont.truetype(FONTS + name, size)


def mono(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", size)


STEPS = [
    dict(
        label="Step 1",
        who="Individually",
        minutes=15,
        title="Write ideas",
        bullets=[
            "Write 3 to 5 unique ideas",
            "One idea per sticky note",
            "Each idea must meet the criteria",
        ],
    ),
    dict(
        label="Step 2",
        who="As a team",
        minutes=15,
        title="Post & vote",
        bullets=[
            "Post every idea on the team wall",
            "Briefly present your ideas to the team",
            "Vote for your top 3 with round stickers.",
            "You can vote for your own",
        ],
    ),
    dict(
        label="Step 3",
        who="As a team",
        minutes=15,
        title="Discuss & decide",
        bullets=[
            "Count the votes",
            "Discuss the top 3 ideas",
            "Combine ideas (optional)",
            "Decide what you'll pursue",
        ],
    ),
    dict(
        label="Step 4",
        who="As a team",
        minutes=45,
        title="Present",
        bullets=[
            "Present your top 1 or 2 ideas to the entire class",
            "Get feedback from the instructors",
        ],
    ),
]


def tracked(draw: ImageDraw.ImageDraw, xy, text: str, fnt, fill, tracking: float):
    """Draw letter-spaced text; PIL has no tracking option."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return x


def background() -> Image.Image:
    top, bottom = (255, 255, 255), (247, 249, 252)
    strip = Image.new("RGB", (1, H))
    px = strip.load()
    for y in range(H):
        t = y / (H - 1)
        px[0, y] = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
    return strip.resize((W, H))


def mmss(seconds: int) -> str:
    m, s = divmod(max(0, seconds), 60)
    return f"{m:02d}:{s:02d}"


def draw_header(d: ImageDraw.ImageDraw):
    tracked(d, (110, 74), "CLASS 9 · WEEK 9 · FALL 2026", font(24, True), BLUE, 3.2)
    d.text((110, 112), "From sticky notes to a team concept", font=font(56, True), fill=INK)
    label = "ENT-164 · Intro to Making"
    f = font(26)
    d.text((W - 110 - d.textlength(label, font=f), 84), label, font=f, fill=MUTED)


def draw_strip(d: ImageDraw.ImageDraw, x0, y0, active: int | None, done_count: int):
    """The four step cards, the current one lit and the finished ones ticked."""
    total_w = W - 2 * 110
    gap = 22
    bw = (total_w - 3 * gap) / 4
    bh = 132
    for i, step in enumerate(STEPS):
        x = x0 + i * (bw + gap)
        is_active = i == active
        done = i < done_count
        if is_active:
            d.rounded_rectangle([x, y0, x + bw, y0 + bh], 16, fill=TINT, outline=(198, 220, 246), width=3)
        elif done:
            d.rounded_rectangle([x, y0, x + bw, y0 + bh], 16, fill=PAPER, outline=LINE, width=2)
        else:
            d.rounded_rectangle([x, y0, x + bw, y0 + bh], 16, fill=PAPER, outline=LINE, width=2)

        pad = 22
        if done:
            tx, ty = x + bw - pad - 26, y0 + 22
            d.line([(tx, ty + 9), (tx + 9, ty + 18), (tx + 24, ty)], fill=GREEN, width=4, joint="curve")
        lab = step["label"].upper()
        tracked(d, (x + pad, y0 + 18), lab, font(19, True), BLUE if is_active else MUTED, 1.8)
        name_fill = INK if is_active else (MUTED_2 if done else MUTED)
        d.text((x + pad, y0 + 50), step["title"], font=font(34, True), fill=name_fill)
        d.text((x + pad, y0 + 92), f"{step['minutes']} min", font=font(23), fill=MUTED)


def draw_step(d: ImageDraw.ImageDraw, step_index: int, remaining: int, elapsed_step: int, elapsed_total: int):
    step = STEPS[step_index]
    total = step["minutes"] * 60

    d.text((112, 424), f"{step['label'].upper()} · {step['who'].upper()} · {step['minutes']} MIN",
           font=font(26, True), fill=BLUE)
    d.text((110, 466), step["title"], font=font(104, True), fill=INK)

    y = 614
    for bullet in step["bullets"]:
        d.text((124, y), "→", font=font(34, True), fill=BLUE_LIGHT)
        d.text((188, y), bullet, font=font(39), fill=MUTED_2)
        y += 66

    # timer
    if remaining <= 10:
        colour = RED
    elif remaining <= 60:
        colour = AMBER
    else:
        colour = INK
    col_x, col_right = 1180, W - 110
    label = "TIME LEFT"
    tracked(d, (col_x, 430), label, font(24, True), MUTED, 2.6)
    f = mono(190)
    txt = mmss(remaining)
    d.text((col_right - d.textlength(txt, font=f), 462), txt, font=f, fill=colour)

    # step progress
    bar_x, bar_y, bar_h = col_x, 748, 14
    bar_w = col_right - col_x
    d.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], 7, fill=(234, 238, 245))
    frac = 0 if total == 0 else min(1.0, elapsed_step / total)
    if frac > 0:
        d.rounded_rectangle([bar_x, bar_y, bar_x + max(bar_h, int(bar_w * frac)), bar_y + bar_h], 7, fill=BLUE_LIGHT)
    d.text((bar_x, bar_y + 30), f"{max(0, remaining // 60)}:{remaining % 60:02d} of {step['minutes']}:00",
           font=font(24), fill=MUTED)

    draw_total(d, elapsed_total)


def draw_total(d: ImageDraw.ImageDraw, elapsed_total: int):
    total = sum(s["minutes"] for s in STEPS) * 60
    d.text((110, 1000), f"Sprint timer · {elapsed_total // 60} min of {total // 60} min",
           font=font(24), fill=MUTED)
    x0, x1, y = 110, W - 110, 1034
    d.rounded_rectangle([x0, y, x1, y + 8], 4, fill=(234, 238, 245))
    frac = min(1.0, elapsed_total / total)
    if frac > 0:
        d.rounded_rectangle([x0, y, x0 + max(8, int((x1 - x0) * frac)), y + 8], 4, fill=BLUE_LIGHT)


def draw_transition(d: ImageDraw.ImageDraw, done_index: int, elapsed_total: int):
    step = STEPS[done_index]
    nxt = STEPS[done_index + 1] if done_index + 1 < len(STEPS) else None
    d.text((112, 452), "TIME", font=font(26, True), fill=AMBER)
    d.text((110, 494), f"{step['title']} is up.", font=font(96, True), fill=INK)
    if nxt:
        d.text((110, 626), f"Next: {nxt['label']} · {nxt['title']} · {nxt['minutes']} min",
               font=font(46), fill=MUTED_2)
    d.text((110, 706), "Move your team to the next step.", font=font(40), fill=MUTED)
    draw_total(d, elapsed_total)


def draw_end(d: ImageDraw.ImageDraw):
    d.text((110, 420), "SPRINT COMPLETE", font=font(26, True), fill=GREEN)
    d.text((110, 462), "All four steps are done.", font=font(96, True), fill=INK)
    d.text((110, 596), "Sketch, mockup, and slides for the concept presentation.", font=font(46), fill=MUTED_2)
    draw_total(d, sum(s["minutes"] for s in STEPS) * 60)


def frame(kind: str, step_index: int = 0, remaining: int = 0, elapsed_step: int = 0,
          elapsed_total: int = 0) -> Image.Image:
    img = background()
    d = ImageDraw.Draw(img)
    draw_header(d)
    if kind == "step":
        draw_strip(d, 110, 246, active=step_index, done_count=step_index)
        draw_step(d, step_index, remaining, elapsed_step, elapsed_total)
    elif kind == "transition":
        draw_strip(d, 110, 246, active=None, done_count=step_index + 1)
        draw_transition(d, step_index, elapsed_total)
    else:
        draw_strip(d, 110, 246, active=None, done_count=len(STEPS))
        draw_end(d)
    return img


def plan():
    """(kind, kwargs) per second, in order."""
    out = []
    elapsed = 0
    for i, step in enumerate(STEPS):
        total = step["minutes"] * 60
        for e in range(total):
            out.append(("step", dict(step_index=i, remaining=total - e, elapsed_step=e, elapsed_total=elapsed + e)))
        elapsed += total
        if i + 1 < len(STEPS):
            for s in range(TRANSITION):
                out.append(("transition", dict(step_index=i, elapsed_total=elapsed)))
            elapsed += TRANSITION
    for _ in range(END_CARD):
        out.append(("end", dict()))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", metavar="DIR", help="write one still per step and exit")
    ap.add_argument("--only", type=int, help="render only the first N seconds (smoke test)")
    args = ap.parse_args(argv)

    if args.preview:
        out = Path(args.preview)
        out.mkdir(parents=True, exist_ok=True)
        for i, step in enumerate(STEPS):
            frame("step", step_index=i, remaining=step["minutes"] * 60 // 3,
                  elapsed_step=step["minutes"] * 20, elapsed_total=sum(s["minutes"] * 60 for s in STEPS[:i]) + step["minutes"] * 20
                  ).save(out / f"step{i + 1}.png")
        frame("transition", step_index=1, elapsed_total=1800).save(out / "transition.png")
        frame("end").save(out / "end.png")
        print(f"preview written to {out}")
        return 0

    frames = plan()
    if args.only:
        frames = frames[: args.only]
    work = Path(tempfile.mkdtemp(prefix="step-timer-"))
    try:
        for n, (kind, kw) in enumerate(frames):
            frame(kind, **kw).save(work / f"{n:05d}.png")
            if n % 300 == 0:
                print(f"  {n}/{len(frames)} frames", flush=True)
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", "1", "-i", str(work / "%05d.png"),
            "-vf", f"fps={FPS},format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-movflags", "+faststart",
            str(OUT),
        ]
        subprocess.run(cmd, check=True)
        size = OUT.stat().st_size / 1e6
        print(f"wrote {OUT.relative_to(ROOT)} · {len(frames) / 60:.1f} min · {size:.1f} MB")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
