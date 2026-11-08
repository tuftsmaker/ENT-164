#!/usr/bin/env python3
"""Render the browser -> server -> database round trip as a looping video.

The class-10 deck draws this as a still diagram. This animates it for the class
page: one request leaves the browser, becomes a query, comes back as rows, and
returns as a response.

Frames are drawn with PIL at 2x and encoded with ffmpeg, so the render is
deterministic and needs no browser. The type is the deck's own stack (SF Pro
from the system, Menlo for the request), so the video sits beside the slides.

    python3 scripts/render-web-loop.py \
        --out classes/class-10/shots/web-round-trip.mp4 \
        --poster classes/class-10/shots/web-round-trip-poster.jpg
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- canvas

SCALE = 2                      # render at 2x, downscale in ffmpeg
W, H = 1920 * SCALE, 1080 * SCALE
FPS = 30
DURATION = 10.4
RESET = (8.6, 9.8)             # everything dims back to the base state

INK, MUTED, MUTED2 = "#0d1526", "#5f6b7a", "#3f4a5a"
LINE, STRONG, BLUE, DEEP = "#e6eaf1", "#d5dce7", "#3E8EDE", "#1F6FD0"
TINT, TINT_BORDER, PAPER2 = "#f2f7fd", "#bcd8f7", "#f7f9fc"

FONT_PATH = "/System/Library/Fonts/SFNS.ttf"
MONO_PATH = "/System/Library/Fonts/Menlo.ttc"

_fonts: dict[tuple[int, str], ImageFont.FreeTypeFont] = {}


def px(v: float) -> int:
    return int(round(v * SCALE))


def font(size: float, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    key = (int(size * SCALE), weight)
    if key not in _fonts:
        f = ImageFont.truetype(FONT_PATH, key[0])
        f.set_variation_by_name(weight)
        _fonts[key] = f
    return _fonts[key]


def mono(size: float) -> ImageFont.FreeTypeFont:
    key = (int(size * SCALE), "mono")
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(MONO_PATH, key[0])
    return _fonts[key]


def text(d, xy, s, size, color, weight="Regular", anchor="la", tracking=0.0):
    f = font(size, weight)
    x, y = xy
    if tracking:
        for ch in s:
            d.text((px(x), px(y)), ch, font=f, fill=color, anchor=anchor)
            x += d.textlength(ch, font=f) / SCALE + tracking
        return
    d.text((px(x), px(y)), s, font=f, fill=color, anchor=anchor)


def rgb(c: str) -> tuple[int, int, int]:
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def mix(a: str, b: str, t: float):
    t = max(0.0, min(1.0, t))
    ca, cb = rgb(a), rgb(b)
    return tuple(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))


def fade(color: str, alpha: float, base: str = "#ffffff"):
    return mix(base, color, alpha)


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def seg(t: float, a: float, b: float) -> float:
    if b <= a:
        return 1.0 if t >= b else 0.0
    return ease((t - a) / (b - a))


def lerp(a: float, b: float, p: float) -> float:
    return a + (b - a) * p


def lit(t: float) -> float:
    """1 while the story is on screen, 0 once it has reset for the loop."""
    return 1.0 - seg(t, *RESET)


# ---------------------------------------------------------------- pieces

PANEL_Y, PANEL_H, PANEL_W = 300, 490, 380

PANELS = [
    dict(key="browser", x=90, fill="#ffffff", stroke=LINE,
         title="Browser", sub="the client", icon="browser",
         lines=("It asks for a page", "and draws the answer")),
    dict(key="server", x=770, fill=TINT, stroke=TINT_BORDER,
         title="Server", sub="the answerer", icon="server",
         lines=("Sends files, runs code", "and asks the database")),
    dict(key="data", x=1450, fill="#ffffff", stroke=LINE,
         title="Database", sub="the memory", icon="db",
         lines=("Keeps data after the", "server is switched off")),
]

HOPS = [
    dict(key="req", x0=470, x1=770, y=440, label="request", side="up",
         t0=1.00, t1=2.05),
    dict(key="query", x0=1150, x1=1450, y=440, label="query", side="up",
         t0=2.45, t1=3.45),
    dict(key="rows", x0=1450, x1=1150, y=660, label="rows", side="down",
         t0=3.85, t1=4.85),
    dict(key="resp", x0=770, x1=470, y=660, label="response", side="down",
         t0=5.20, t1=6.25),
]

STEPS = [
    ("The browser asks", 0.95),
    ("The server decides", 2.10),
    ("The database answers", 3.50),
    ("The response returns", 5.15),
]

PULSES = [(2.05, "server"), (3.45, "data"), (4.85, "server"), (6.25, "browser")]


def background() -> Image.Image:
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=mix("#ffffff", "#eef3fa", y / (H - 1)))
    return img


BG = background()


def panel_box(key: str):
    p = next(p for p in PANELS if p["key"] == key)
    return p, p["x"], PANEL_Y, p["x"] + PANEL_W, PANEL_Y + PANEL_H


def draw_shadow(img, box, radius):
    x0, y0, x1, y1 = box
    layer = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([px(x0), px(y0 + 6), px(x1), px(y1 + 6)],
                        radius=px(radius), fill=26)
    layer = layer.filter(ImageFilter.GaussianBlur(px(9)))
    img.paste(Image.new("RGB", img.size, INK), (0, 0), layer)


def draw_icon(d, cx, cy, kind):
    """A 46px line icon centred on (cx, cy)."""
    col = DEEP
    w = px(2.6)
    half = 23

    def box():
        return [px(cx - half), px(cy - half), px(cx + half), px(cy + half)]

    if kind == "browser":
        x0, y0, x1, y1 = box()
        d.rounded_rectangle([x0, y0 + px(4), x1, y1 - px(4)], radius=px(4),
                            outline=col, width=w)
        d.line([x0, y0 + px(15), x1, y0 + px(15)], fill=col, width=w)
        for dx in (10, 17):
            r = px(1.6)
            d.ellipse([x0 + px(dx) - r, y0 + px(9) - r, x0 + px(dx) + r, y0 + px(9) + r], fill=col)
    elif kind == "server":
        x0, y0, x1, y1 = box()
        for top in (y0 + px(3), y1 - px(21)):
            d.rounded_rectangle([x0, top, x1, top + px(18)], radius=px(4),
                                outline=col, width=w)
            r = px(2)
            d.ellipse([x0 + px(7) - r, top + px(9) - r, x0 + px(7) + r, top + px(9) + r], fill=col)
    else:  # database
        x0, y0, x1, y1 = box()
        ry = px(6)
        d.ellipse([x0, y0 + px(3), x1, y0 + px(3) + 2 * ry], outline=col, width=w)
        d.line([x0, y0 + px(3) + ry, x0, y1 - px(3) - ry], fill=col, width=w)
        d.line([x1, y0 + px(3) + ry, x1, y1 - px(3) - ry], fill=col, width=w)
        d.arc([x0, y1 - px(3) - 2 * ry, x1, y1 - px(3)], 0, 180, fill=col, width=w)
        d.arc([x0, y0 + px(3) + 2 * ry + px(12), x1, y0 + px(3) + 2 * ry + px(12) + 2 * ry],
              0, 180, fill=col, width=w)


def draw_panel(img, d, p):
    x0, y0, x1, y1 = panel_box(p["key"])[1:]
    if p["fill"] == "#ffffff":
        draw_shadow(img, (x0, y0, x1, y1), 26)
    d.rounded_rectangle([px(x0), px(y0), px(x1), px(y1)], radius=px(26),
                        fill=p["fill"], outline=p["stroke"], width=px(2))

    # icon chip
    cw = 76
    cx, cy = x0 + 40, y0 + 40
    d.rounded_rectangle([px(cx), px(cy), px(cx + cw), px(cy + cw)], radius=px(22),
                        fill="#eaf3fd", outline="#cfe1f7", width=px(1.5))
    draw_icon(d, cx + cw / 2, cy + cw / 2, p["icon"])

    text(d, (x0 + 40, y0 + 152), p["title"], 40, INK, "Semibold")
    text(d, (x0 + 40, y0 + 206), p["sub"], 24, MUTED)
    text(d, (x0 + 40, y0 + 288), p["lines"][0], 22, MUTED2)
    text(d, (x0 + 40, y0 + 320), p["lines"][1], 22, MUTED2)


def arrow_head(d, x, y, direction, color):
    s = 13
    if direction > 0:
        pts = [(x, y), (x - s, y - 7), (x - s, y + 7)]
    else:
        pts = [(x, y), (x + s, y - 7), (x + s, y + 7)]
    d.polygon([(px(a), px(b)) for a, b in pts], fill=color)


def pill(d, cx, cy, label, alpha):
    f = font(22, "Semibold")
    tw = d.textlength(label, font=f) / SCALE
    w, h = tw + 44, 44
    d.rounded_rectangle([px(cx - w / 2), px(cy - h / 2), px(cx + w / 2), px(cy + h / 2)],
                        radius=px(22), fill=mix("#ffffff", "#ffffff", 0),
                        outline=fade("#cfe1f7", alpha), width=px(1.5))
    d.text((px(cx), px(cy + 1)), label, font=f, fill=fade(DEEP, alpha), anchor="mm")


def draw_chip(d, x, y, s, alpha):
    f = mono(20)
    w = d.textlength(s, font=f) / SCALE + 34
    d.rounded_rectangle([px(x - w), px(y - 19), px(x), px(y + 19)], radius=px(19),
                        fill=fade("#eaf3fd", alpha), outline=fade("#cfe1f7", alpha),
                        width=px(1.2))
    d.text((px(x - w / 2), px(y + 1)), s, font=f, fill=fade(DEEP, alpha), anchor="mm")


def draw_rail(d, t):
    y = 872
    xs = [110, 560, 1010, 1460]
    active = 0
    for i, (_, start) in enumerate(STEPS):
        if t >= start:
            active = i

    lit_a = lit(t)
    progress = 1.0 if t >= STEPS[0][1] else 0.0
    end_x = xs[active] if progress else xs[0]

    d.line([px(xs[0]), px(y), px(xs[-1]), px(y)], fill=STRONG, width=px(3))
    if active > 0 or progress:
        d.line([px(xs[0]), px(y), px(end_x), px(y)], fill=fade(BLUE, lit_a), width=px(3))

    for i, (label, start) in enumerate(STEPS):
        on = (t >= start) * lit_a
        x = xs[i]
        r = 9
        if on > 0.01:
            d.ellipse([px(x - r), px(y - r), px(x + r), px(y + r)], fill=fade(DEEP, on))
        else:
            d.ellipse([px(x - r), px(y - r), px(x + r), px(y + r)], fill="#ffffff",
                      outline=STRONG, width=px(2))
        col = mix(MUTED, INK, on)
        text(d, (x, y + 26), label, 21, col,
             "Semibold" if on > 0.5 else "Medium")


def draw_pulses(d, t):
    for at, key in PULSES:
        p = seg(t, at, at + 0.55)
        if not 0 < p < 1:
            continue
        a = (1 - p) * lit(t)
        x0, y0, x1, y1 = panel_box(key)[1:]
        grow = 6 + 26 * p
        d.rounded_rectangle([px(x0 - grow), px(y0 - grow), px(x1 + grow), px(y1 + grow)],
                            radius=px(26 + grow), outline=fade(BLUE, a * 0.8), width=px(3))


def render(t: float) -> Image.Image:
    img = BG.copy()
    d = ImageDraw.Draw(img)

    # heading
    text(d, (90, 92), "WEB ARCHITECTURE", 20, DEEP, "Semibold", tracking=3.2)
    f = font(58, "Semibold")
    head_x = 90
    d.text((px(head_x), px(126)), "One ", font=f, fill=INK)
    head_x += d.textlength("One ", font=f) / SCALE
    d.text((px(head_x), px(126)), "round trip", font=f, fill=DEEP)
    text(d, (90, 208), "The browser asks, the server answers, the database remembers.",
         27, MUTED)

    for p in PANELS:
        draw_panel(img, d, p)

    # connections and moving dots
    for hop in HOPS:
        x0, x1, y = hop["x0"], hop["x1"], hop["y"]
        direction = 1 if x1 > x0 else -1
        p = seg(t, hop["t0"], hop["t1"])
        on = lit(t)

        d.line([px(x0), px(y), px(x1), px(y)], fill=STRONG, width=px(3))
        arrow_head(d, x1, y, direction, mix("#c3cbd7", BLUE, 0.0))

        head = lerp(x0, x1, p)
        if p > 0:
            col = fade(BLUE, on)
            d.line([px(x0), px(y), px(head), px(y)], fill=col, width=px(4))
            if p > 0.93:
                arrow_head(d, x1, y, direction, col)

        # label
        la = seg(t, hop["t0"] + 0.15, hop["t0"] + 0.45) * on
        if la > 0.01:
            cy = y - 44 if hop["side"] == "up" else y + 44
            pill(d, (x0 + x1) / 2, cy, hop["label"], la)

        # travelling dot, with a short trail
        dot_a = (1 - seg(t, hop["t1"] - 0.18, hop["t1"])) * (1 if p > 0 else 0) * on
        if dot_a > 0.01:
            for k in range(4, 0, -1):
                tx = head - direction * k * 20
                if min(x0, x1) <= tx <= max(x0, x1):
                    r = 4 + (4 - k) * 1.2
                    d.ellipse([px(tx - r), px(y - r), px(tx + r), px(y + r)],
                              fill=fade(BLUE, dot_a * (0.10 + 0.05 * (4 - k))))
            d.ellipse([px(head - 15), px(y - 15), px(head + 15), px(y + 15)],
                      fill=fade("#d7e9fb", dot_a))
            r = 8.5
            d.ellipse([px(head - r), px(y - r), px(head + r), px(y + r)],
                      fill=fade(DEEP, dot_a))

    draw_pulses(d, t)
    draw_rail(d, t)

    # the request itself, once the first hop is under way
    chip_a = seg(t, 1.15, 1.5) * lit(t)
    if chip_a > 0.01:
        draw_chip(d, 430, 352, "GET /forecast", chip_a)

    return img


# ---------------------------------------------------------------- encode

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="MP4 to write")
    ap.add_argument("--poster", help="JPEG still to write (a lit frame)")
    ap.add_argument("--poster-time", type=float, default=7.4)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = Path(tempfile.mkdtemp(prefix="web-loop-"))
    total = int(round(DURATION * FPS))

    for i in range(total):
        render(i / FPS).save(frames / f"{i:04d}.png")
        if i % 30 == 0:
            print(f"  frame {i}/{total}", flush=True)

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
         "-i", str(frames / "%04d.png"),
         "-vf", f"scale={W // SCALE}:{H // SCALE}:flags=lanczos",
         "-c:v", "libx264", "-profile:v", "high", "-crf", str(args.crf),
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(out)],
        check=True,
    )
    print(f"{out}: {total} frames, {out.stat().st_size} bytes")

    if args.poster:
        still = render(args.poster_time)
        still.resize((W // SCALE, H // SCALE), Image.LANCZOS).save(
            args.poster, quality=90, optimize=True)
        print(f"{args.poster}: still at {args.poster_time}s")

    if not args.keep_frames:
        shutil.rmtree(frames, ignore_errors=True)
    else:
        print(f"frames kept in {frames}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
