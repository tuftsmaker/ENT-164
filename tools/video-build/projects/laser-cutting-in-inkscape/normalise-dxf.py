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
Shifts every entity into positive Y (so the stock flip lands it on the page) and
writes real $INSUNITS, $MEASUREMENT and $EXTMIN/$EXTMAX values. It does not
change the geometry: the part keeps its size and shape.

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
    dy = -ymin if ymin < 0 else 0.0     # lift into positive Y

    out, in_ent, i = [], False, 0
    while i < len(lines) - 1:
        code, val = lines[i].strip(), lines[i+1].strip()
        if code == "0" and val == "SECTION":
            in_ent = (i + 3 < len(lines) and lines[i+2].strip() == "2"
                      and lines[i+3].strip() == "ENTITIES")
        elif code == "0" and val == "ENDSEC":
            in_ent = False
        if in_ent and dy and code in Y_CODES:
            try:
                out += [lines[i], f"{float(val) + dy:.6f}"]
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
        ("$EXTMIN", [("10", f"{xmin:.6f}"), ("20", f"{ymin + dy:.6f}"), ("30", "0.000000")]),
        ("$EXTMAX", [("10", f"{xmax:.6f}"), ("20", f"{ymax + dy:.6f}"), ("30", "0.000000")]),
        # Paper-space extents. Onshape leaves these at the +/-1e20 sentinel too,
        # and Inkscape still takes the document's overall bounds from them, so
        # the drawing sits inside a 1e20-unit box and "zoom to drawing" lands at
        # about 2% on a page that looks empty. They must be fixed as well.
        ("$PEXTMIN", [("10", f"{xmin:.6f}"), ("20", f"{ymin + dy:.6f}"), ("30", "0.000000")]),
        ("$PEXTMAX", [("10", f"{xmax:.6f}"), ("20", f"{ymax + dy:.6f}"), ("30", "0.000000")]),
    ):
        out = upsert_header(out, var, values)

    open(dst, "w").write("\n".join(out) + "\n")

    # Report what the stock importer will now do, so a wrong-looking result is
    # obvious at conversion time rather than at recording time.
    page_h = 297.0                                      # importer's A4 default
    top = page_h - (ymax + dy - (ymin + dy))            # height - (y - ymin) at ymax
    bottom = page_h                                     # at ymin
    print(f"  {os.path.basename(src)}: {xmax-xmin:.1f} x {ymax-ymin:.1f} mm")
    print(f"  shifted Y by {dy:+.1f}mm; lands at y = {top:.0f}..{bottom:.0f}mm "
          f"on the importer's {page_h:.0f}mm page")
    if top < 0:
        print("  WARNING: still above the page — the sketch may be taller than A4",
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
