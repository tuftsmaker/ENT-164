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


def rgb(c) -> tuple[int, int, int]:
    if isinstance(c, tuple):
        return c
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

# ---------------------------------------------------------------- timing

FIRST, HOP, PAUSE = 0.70, 1.05, 0.95   # one hop, then a beat to read its card

HOP_TIMES = []
_t = FIRST
for _ in range(4):
    HOP_TIMES.append((round(_t, 3), round(_t + HOP, 3)))
    _t += HOP + PAUSE

LAST = HOP_TIMES[-1][1]
RESET = (LAST + 1.55, LAST + 2.65)       # everything dims back to the base state
DURATION = LAST + 3.5                    # and a beat on the base state before looping

# ---------------------------------------------------------------- pieces

_HOP_SPEC = [
    ("req", 470, 770, 440),
    ("query", 1150, 1450, 440),
    ("rows", 1450, 1150, 660),
    ("resp", 770, 470, 660),
]
HOPS = [dict(key=key, x0=x0, x1=x1, y=y, t0=HOP_TIMES[i][0], t1=HOP_TIMES[i][1])
        for i, (key, x0, x1, y) in enumerate(_HOP_SPEC)]

# The message itself, sitting in the gap beside its hop: HTTP on the left,
# SQL on the right, the row coming back, the JSON reply.
_CARD_SPEC = [
    (620, 352, "HTTP · REQUEST",
     ["GET /readings/current", "Host: weather.example.com"]),
    (1300, 287, "SQL · QUERY",
     ["SELECT temp_c", "FROM readings", "WHERE station = 'Medford'",
      "ORDER BY taken_at DESC", "LIMIT 1;"]),
    (1300, 700, "SQL · ONE ROW", ["temp_c = 8.4"]),
    (620, 700, "HTTP · RESPONSE",
     ["HTTP/1.1 200 OK", '{"station": "Medford",', ' "temp_c": 8.4}']),
]
CARDS = [dict(cx=cx, top=top, caption=caption, lines=lines, t0=HOP_TIMES[i][0])
         for i, (cx, top, caption, lines) in enumerate(_CARD_SPEC)]

STEPS = [
    ("The browser asks", HOP_TIMES[0][0] - 0.15),
    ("The server decides", HOP_TIMES[1][0] - 0.15),
    ("The database answers", HOP_TIMES[2][0] - 0.15),
    ("The response returns", HOP_TIMES[3][0] - 0.15),
]

PULSES = [(HOP_TIMES[0][1], "server"), (HOP_TIMES[1][1], "data"),
          (HOP_TIMES[2][1], "server"), (HOP_TIMES[3][1], "browser")]


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


def code_card(d, cx, top, caption, lines, a):
    """A message card: caption, then the line itself in mono on a dark panel."""
    if a <= 0.01:
        return
    f = mono(15)
    widest = max(d.textlength(line, font=f) for line in lines) / SCALE
    w = widest + 36
    line_h = 21
    h = len(lines) * line_h + 22
    body = mix("#ffffff", "#0f1b2d", min(1.0, a * 1.7))
    fg = mix(body, "#dbe7f7", a)

    d.text((px(cx), px(top - 17)), caption, font=font(12, "Semibold"),
           fill=mix("#ffffff", DEEP, min(1.0, a * 1.4)), anchor="mm")
    d.rounded_rectangle([px(cx - w / 2), px(top), px(cx + w / 2), px(top + h)],
                        radius=px(12), fill=body)
    y = top + 12
    for line in lines:
        d.text((px(cx - w / 2 + 18), px(y)), line, font=f, fill=fg)
        y += line_h


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

    for card in CARDS:
        code_card(d, card["cx"], card["top"], card["caption"], card["lines"],
                  seg(t, card["t0"] + 0.10, card["t0"] + 0.40) * lit(t))

    return img


# ---------------------------------------------------------------- encode

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="MP4 to write")
    ap.add_argument("--poster", help="JPEG still to write (a lit frame)")
    ap.add_argument("--poster-time", type=float, default=round(LAST + 0.9, 2),
                    help="seconds into the clip for the poster still")
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
