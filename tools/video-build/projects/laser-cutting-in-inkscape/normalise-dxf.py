#!/usr/bin/env python3
"""Normalise an Onshape DXF export so Inkscape's stock importer places it correctly.

Why this is needed
------------------
Onshape's DXF export has two properties that together break Inkscape's importer:

  1. **No units.** There is no $INSUNITS, so Inkscape cannot know the drawing is
     in millimetres.
  2. **Sentinel extents.** $EXTMIN/$EXTMAX are set to +/-1e20 — AutoCAD's "empty
     extents" value, not a real bounding box.

Inkscape's bundled importer (dxf_input.py) then flips Y with

    y_svg = height - scale * (y - ymin)

using its own hardcoded A4 page height (297mm) and `ymin` taken as 0. A sketch
drawn in the usual CAD orientation — origin at the bottom-left, Y pointing up —
lands at y = 297..357mm, i.e. entirely *above* the page. The document opens
looking empty, and "zoom to drawing" lands at about 2%.

What this does
--------------
Centres every entity on the importer's A4 page, which needs both shifts: X
because the exporter puts the origin at the part's left edge, and Y so the stock
flip lands it on the page rather than above it. It also writes real $INSUNITS,
$MEASUREMENT and $EXTMIN/$EXTMAX values. It does not change the geometry: the
part keeps its size and shape.

Centring matters for the video, not just for looks: the class deck's take03
centres the added engraving text with Align and Distribute set to "Relative to:
Page" — that dropdown will not open for a synthetic click, so the take relies on
the part being at the page centre for a page-centre alignment to also be a
part-centre alignment. An off-centre part would make the alignment move the part
itself across the page on camera.

Usage
-----
    normalise-dxf.py INPUT.dxf [-o OUTPUT.dxf] [--in-place]

Keep the original alongside the result — the project's `video.json` points
`sourceFile` at the normalised copy, and the untouched original stays as
`*.orig` so the difference is inspectable.
"""
import argparse
import os
import re
import shutil
import sys

# Entity codes that carry X / Y coordinates. 23-24 are the 3D variants some
# exporters emit for the same geometry.
X_CODES = ("10", "11", "13", "14")
Y_CODES = ("20", "21", "23", "24")

# The importer's hardcoded page (it assumes A4 for every DXF).
PAGE_W, PAGE_H = 210.0, 297.0


def read_pairs(path):
    lines = open(path, errors="replace").read().splitlines()
    return [l.rstrip() for l in lines]


def entities_extent(lines):
    """Real bounding box of the ENTITIES section, ignoring header sentinels."""
    xs, ys, in_ent, i = [], [], False, 0
    while i < len(lines) - 1:
        code, val = lines[i].strip(), lines[i+1].strip()
        if code == "0" and val == "SECTION":
            in_ent = (i + 3 < len(lines) and lines[i+2].strip() == "2"
                      and lines[i+3].strip() == "ENTITIES")
        elif code == "0" and val == "ENDSEC":
            in_ent = False
        elif in_ent:
            try:
                if code in X_CODES:
                    xs.append(float(val))
                elif code in Y_CODES:
                    ys.append(float(val))
            except ValueError:
                pass
        i += 2
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def upsert_header(lines, var, values):
    """Replace a header variable's value list, or insert it before ENDSEC.

    A header variable is a `9,<name>` pair followed by one or more `code,value`
    pairs — $EXTMIN and $EXTMAX carry three (X, Y, Z). Replacing only the first
    pair leaves the others at their old value, which is exactly how the +/-1e20
    sentinels survived a first attempt and kept the importer's page wrong.
    """
    start = None
    for k in range(len(lines) - 1):
        if lines[k].strip() == "9" and lines[k+1].strip() == var:
            start = k
            break

    if start is None:
        for k in range(len(lines) - 1):
            if lines[k].strip() == "0" and lines[k+1].strip() == "ENDSEC":
                block = ["9", var]
                for code, value in values:
                    block += [code, value]
                lines[k:k] = block
                return lines
        return lines

    # Find the end of this variable: the next `9` (new variable) or ENDSEC.
    end = start + 2
    while end < len(lines) - 1:
        if lines[end].strip() == "9":
            break
        if lines[end].strip() == "0" and lines[end+1].strip() == "ENDSEC":
            break
        end += 2

    block = ["9", var]
    for code, value in values:
        block += [code, value]
    lines[start:end] = block
    return lines


def normalise(src, dst):
    lines = read_pairs(src)
    ext = entities_extent(lines)
    if ext is None:
        sys.exit(f"{src}: no geometry found in the ENTITIES section")
    xmin, ymin, xmax, ymax = ext
    # Centre on the importer's page. In importer terms the page is y_svg =
    # PAGE_H - (y + dy), so centring Y means dy = PAGE_H/2 - (ymin+ymax)/2.
    dx = PAGE_W / 2 - (xmin + xmax) / 2
    dy = PAGE_H / 2 - (ymin + ymax) / 2

    out, in_ent, i = [], False, 0
    while i < len(lines) - 1:
        code, val = lines[i].strip(), lines[i+1].strip()
        if code == "0" and val == "SECTION":
            in_ent = (i + 3 < len(lines) and lines[i+2].strip() == "2"
                      and lines[i+3].strip() == "ENTITIES")
        elif code == "0" and val == "ENDSEC":
            in_ent = False
        if in_ent and code in X_CODES + Y_CODES:
            try:
                shift = dx if code in X_CODES else dy
                out += [lines[i], f"{float(val) + shift:.6f}"]
                i += 2
                continue
            except ValueError:
                pass
        out.append(lines[i])
        i += 1
    out.append(lines[-1])

    for var, values in (
        ("$INSUNITS", [("70", "4")]),                   # 4 = millimetres
        ("$MEASUREMENT", [("70", "1")]),                # 1 = metric
        ("$EXTMIN", [("10", f"{xmin + dx:.6f}"), ("20", f"{ymin + dy:.6f}"), ("30", "0.000000")]),
        ("$EXTMAX", [("10", f"{xmax + dx:.6f}"), ("20", f"{ymax + dy:.6f}"), ("30", "0.000000")]),
        # Paper-space extents. Onshape leaves these at the +/-1e20 sentinel too,
        # and Inkscape still takes the document's overall bounds from them, so
        # the drawing sits inside a 1e20-unit box and "zoom to drawing" lands at
        # about 2% on a page that looks empty. They must be fixed as well.
        ("$PEXTMIN", [("10", f"{xmin + dx:.6f}"), ("20", f"{ymin + dy:.6f}"), ("30", "0.000000")]),
        ("$PEXTMAX", [("10", f"{xmax + dx:.6f}"), ("20", f"{ymax + dy:.6f}"), ("30", "0.000000")]),
    ):
        out = upsert_header(out, var, values)

    open(dst, "w").write("\n".join(out) + "\n")

    # Report what the stock importer will now do, so a wrong-looking result is
    # obvious at conversion time rather than at recording time.
    width, height = xmax - xmin, ymax - ymin
    top = PAGE_H - (ymax + dy)              # y_svg of the part's top edge
    bottom = PAGE_H - (ymin + dy)           # y_svg of the part's bottom edge
    print(f"  {os.path.basename(src)}: {width:.1f} x {height:.1f} mm")
    print(f"  centred: x = {xmin + dx:.0f}..{xmax + dx:.0f}mm, "
          f"y = {top:.0f}..{bottom:.0f}mm from the page top "
          f"on the importer's {PAGE_W:.0f}x{PAGE_H:.0f}mm page")
    if width > PAGE_W or height > PAGE_H:
        print("  WARNING: larger than the page — the sketch may not fit A4",
              file=sys.stderr)
    print(f"  wrote {dst}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--in-place", action="store_true",
                    help="overwrite the input, keeping a .orig backup")
    args = ap.parse_args()

    if args.in_place:
        shutil.copy(args.input, args.input + ".orig")
        normalise(args.input, args.input)
    else:
        normalise(args.input, args.output or
                  os.path.splitext(args.input)[0] + "-normalised.dxf")


if __name__ == "__main__":
    main()
