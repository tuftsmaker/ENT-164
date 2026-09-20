#!/usr/bin/env python3
"""Extract a .pptx into a working directory for deck conversion.

Produces:
  slides.txt      per-slide text (=== Slide N ===)
  notes.txt       per-slide speaker notes
  manifest.json   per slide: media and chart references, plus media dimensions
  media/          referenced media files (originals)
  contact.png     labelled contact sheet of the media (if Pillow is available)

Usage: scripts/extract-pptx.py "slides/ENT-164 Class N - Title.pptx" /tmp/class-N
"""
import argparse
import json
import os
import re
import struct
import zipfile
from xml.etree import ElementTree as ET

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".emf", ".wmf")


def slide_number(name):
    m = re.search(r"slide(\d+)\.xml$", name)
    return int(m.group(1)) if m else -1


def text_lines(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for para in root.iter(A + "p"):
        run_text = "".join(t.text or "" for t in para.iter(A + "t"))
        line = " ".join(run_text.split())
        if line:
            out.append(line)
    return out


def image_size(path):
    try:
        from PIL import Image

        with Image.open(path) as im:
            return list(im.size)
    except Exception:
        pass
    try:
        with open(path, "rb") as f:
            head = f.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", head[16:24])
            return [w, h]
        if head[:2] == b"\xff\xd8":
            with open(path, "rb") as f:
                data = f.read()
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                    h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                    return [w, h]
                if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                seg = struct.unpack(">H", data[i + 2 : i + 4])[0]
                i += 2 + seg
    except Exception:
        pass
    return None


def chart_text(z, chart_path):
    try:
        root = ET.fromstring(z.read(chart_path))
    except KeyError:
        return None
    lines = []
    title = "".join(t.text or "" for t in root.iter(A + "t"))
    if title.strip():
        lines.append(f"title: {' '.join(title.split())}")
    for ser in root.iter(C + "ser"):
        name = "".join(t.text or "" for t in ser.iter(A + "t"))
        vals = []
        for pt in ser.iter(C + "pt"):
            v = pt.find(C + "v")
            if v is not None and v.text:
                vals.append(v.text)
        cats = []
        for cat in ser.iter(C + "cat"):
            for pt in cat.iter(C + "pt"):
                v = pt.find(C + "v")
                if v is not None and v.text:
                    cats.append(v.text)
        if name or vals:
            lines.append(f"series {name.strip()!r}: {', '.join(vals)}")
        if cats:
            lines.append(f"categories: {', '.join(cats)}")
    return "\n".join(lines) if lines else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx")
    ap.add_argument("outdir")
    args = ap.parse_args()

    os.makedirs(os.path.join(args.outdir, "media"), exist_ok=True)

    with zipfile.ZipFile(args.pptx) as z:
        names = set(z.namelist())
        slides = sorted(
            (n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)),
            key=slide_number,
        )
        slide_text, notes_text, manifest = [], [], {}

        for name in slides:
            num = slide_number(name)
            base = name.rsplit("/", 1)[0]
            rels = f"{base}/_rels/{os.path.basename(name)}.rels"
            rel_map = {}
            if rels in names:
                rel_root = ET.fromstring(z.read(rels))
                for rel in rel_root:
                    rel_map[rel.get("Id")] = rel.get("Target")

            text = text_lines(z.read(name))
            slide_text.append(f"=== Slide {num} ===")
            slide_text.extend(text)
            slide_text.append("")

            media, charts = [], []
            root = ET.fromstring(z.read(name))
            for blip in root.iter(A + "blip"):
                rid = blip.get(R + "embed") or blip.get(R + "link")
                target = rel_map.get(rid)
                if not target:
                    continue
                if "media/" in target:
                    media.append(os.path.basename(target))
                elif "charts/" in target:
                    charts.append(os.path.basename(target))
            if rels in names:
                for rel in ET.fromstring(z.read(rels)):
                    t = rel.get("Target") or ""
                    if "charts/" in t:
                        charts.append(os.path.basename(t))
            for m in media:
                src = f"ppt/media/{m}"
                if m.lower().endswith(IMAGE_EXT) and src in names:
                    with open(os.path.join(args.outdir, "media", m), "wb") as f:
                        f.write(z.read(src))

            chart_dump = []
            for ch in dict.fromkeys(charts):
                rel_root = ET.fromstring(z.read(rels)) if rels in names else []
                for rel in rel_root:
                    if (rel.get("Target") or "").endswith(ch):
                        dump = chart_text(z, rel.get("Target").lstrip("/"))
                        if dump:
                            chart_dump.append(dump)
            if chart_dump:
                slide_text.append("[chart]")
                for dump in chart_dump:
                    for line in dump.splitlines():
                        slide_text.append(f"  {line}")
                slide_text.append("")

            notes_name = f"ppt/notesSlides/notesSlide{num}.xml"
            notes = text_lines(z.read(notes_name)) if notes_name in names else []
            if notes:
                notes_text.append(f"=== Slide {num} notes ===")
                notes_text.extend(notes)
                notes_text.append("")

            manifest[str(num)] = {
                "text": text,
                "notes": notes,
                "media": list(dict.fromkeys(media)),
                "charts": list(dict.fromkeys(charts)),
            }

    with open(os.path.join(args.outdir, "slides.txt"), "w") as f:
        f.write("\n".join(slide_text))
    with open(os.path.join(args.outdir, "notes.txt"), "w") as f:
        f.write("\n".join(notes_text))

    dims = {}
    media_dir = os.path.join(args.outdir, "media")
    for m in sorted(os.listdir(media_dir)):
        dims[m] = image_size(os.path.join(media_dir, m))
    with open(os.path.join(args.outdir, "manifest.json"), "w") as f:
        json.dump({"slides": manifest, "media_dimensions": dims}, f, indent=2)

    # contact sheet: numbered tiles, numbered same as the manifest listing
    files = sorted(dims)
    try:
        from PIL import Image, ImageDraw

        cols = 6
        tile = 220
        rows = (len(files) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tile, rows * (tile + 18)), "white")
        draw = ImageDraw.Draw(sheet)
        for i, name in enumerate(files):
            path = os.path.join(media_dir, name)
            try:
                with Image.open(path) as im:
                    im = im.convert("RGB")
                    im.thumbnail((tile - 8, tile - 8))
                    x = (i % cols) * tile + (tile - im.width) // 2
                    y = (i // cols) * (tile + 18) + (tile - im.height) // 2
                    sheet.paste(im, (x, y))
            except Exception:
                pass
            draw.text(((i % cols) * tile + 4, (i // cols) * (tile + 18) + tile), f"{i + 1}. {name}", fill="black")
        sheet.save(os.path.join(args.outdir, "contact.png"))
    except ImportError:
        pass

    print(f"{args.pptx} -> {args.outdir}")
    print(f"  slides: {len(slides)}")
    print(f"  media: {len(files)} (contact.png: {'yes' if os.path.exists(os.path.join(args.outdir, 'contact.png')) else 'no'})")
    print("  media index:")
    for i, name in enumerate(files):
        print(f"    {i + 1}. {name} {dims[name]}")


if __name__ == "__main__":
    main()
