#!/usr/bin/env python3
"""Cut finger joints along the straight seams where two shapes touch.

A finger joint needs one number: the material thickness. Everything else
follows from it, and the rule that makes a joint work or fail is that a finger
is **never deeper than one thickness**:

    finger depth   <=  material thickness      (hard rule)
    finger width    =  material thickness      (the class's convention)

so the whole joint lives in ONE thickness-wide band. Getting that wrong is easy
and silent — an earlier version of this tool cut a 6 mm band for 3 mm material,
i.e. fingers twice as deep as the sheet, and it still looked like a joint. The
depth is therefore asserted here, and `test_finger_joints.py` asserts it again.

What this tool is given, and what it is not
-------------------------------------------
Seams are **supplied**, not discovered. Finding them automatically would mean
deciding which closed region is which piece, and that fails on real exports: an
Onshape sketch that draws one edge twice, or shares an edge between two loops,
does not chain into the regions a person sees in it (the checker's own
`profiles()` reports the lower piece of `Cut Complex` as *open* for exactly that
reason). Rather than guess, this takes each seam as a line segment plus which
side carries the fingers, and verifies the result.

The output is one path per seam — a single zigzag the laser cuts once. Two
pieces that meet along it come apart with matching fingers and slots, so no two
cut paths ever lie on the same line (a doubled path would make the laser fire
twice and scorch the edge).

Usage
-----
    # a seam from (0,0) to (100,0), 3 mm material, fingers cut upward
    finger_joints.py part.dxf -o jointed.dxf \
        --seam 0,0,100,0 --thickness 3 --side up --fingers 16

    # report what the joints on a file already measure
    finger_joints.py jointed.dxf --check --thickness 3

The `--check` mode re-derives each comb's depth and width from the geometry, so
a joint that violates the depth rule is reported rather than assumed.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
CHECK = HERE.parent.parent / "skills" / "maker-tasks" / "check"
sys.path.insert(0, str(CHECK))

import dxf_reader  # noqa: E402

LAYER = "MODELSKETCH_VISIBLE"

# A plain butt is left at each end of a seam, so the piece's corners stay
# intact. It must not be squeezed to nothing: a finger starting a fraction of a
# millimetre from a corner leaves a sliver that snaps off, and the fit near the
# corner is on the sliver rather than on the joint. Half a thickness is the
# floor — an earlier auto count left 0.5 mm for 3 mm material, which is why it
# exists.
MIN_BUTT = 1.5


# ------------------------------------------------------------------ maths

def dedupe(pts, tol=1e-9):
    out = []
    for p in pts:
        if not out or abs(out[-1][0] - p[0]) > tol or abs(out[-1][1] - p[1]) > tol:
            out.append(p)
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) <= tol \
            and abs(out[0][1] - out[-1][1]) <= tol:
        out.pop()
    return out


def comb(start, end, thickness, fingers, side, butt=None):
    """A finger comb along the seam `start` -> `end`.

    `side` is +1 for the fingers to cut to the left of the direction of travel
    (in the direction of the seam's normal) and -1 for the other way; with a
    seam along +X that is up (+Y) and down (-Y) respectively.

    Returns the polyline points. The depth never exceeds `thickness`: every
    finger is one thickness deep, and the material between fingers returns to
    the seam line. The path runs along the seam, so it starts and ends on it.

    `fingers` is the number of fingers. The comb occupies 2*n-1 thicknesses
    (n fingers and n-1 slots), and whatever is left over is split as a plain
    butt at each end, keeping the piece's corners intact.
    """
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    if length <= 0:
        raise ValueError("a seam needs two distinct endpoints")

    span = (2 * fingers - 1) * thickness
    auto_butt = (length - span) / 2
    if butt is None:
        butt = auto_butt
    if butt < 0 or span + 2 * butt > length + 1e-9:
        raise ValueError(
            f"{fingers} fingers of {thickness} mm need "
            f"{span + 2 * butt:.1f} mm of a {length:.1f} mm seam")
    if butt < MIN_BUTT - 1e-9:
        raise ValueError(
            f"{fingers} fingers of {thickness} mm leave only {butt:.2f} mm at "
            f"each end of a {length:.1f} mm seam — too little for the corner "
            f"to hold (minimum {MIN_BUTT} mm). Use fewer fingers.")

    # unit vectors: along the seam, and normal to it
    ux, uy = dx / length, dy / length
    nx, ny = -uy * side, ux * side      # normal, pointing to the fingers' side

    def at(along, deep):
        return (sx + ux * along + nx * deep, sy + uy * along + ny * deep)

    pts = [at(0.0, 0.0), at(butt, 0.0)]
    along = butt
    for i in range(fingers):
        pts += [at(along, thickness), at(along + thickness, thickness),
                at(along + thickness, 0.0)]      # out, across the tip, back
        along += thickness
        if i < fingers - 1:
            pts.append(at(along + thickness, 0.0))   # along the seam to the next
            along += thickness
    pts.append(at(length, 0.0))
    return dedupe(pts)


# ------------------------------------------------------------------ DXF io

def pairs(*items):
    return "".join(f"{c}\r\n{v}\r\n" for c, v in items)


def lwpolyline(pts, layer=LAYER, closed=False):
    body = [(0, "LWPOLYLINE"), (8, layer), (100, "AcDbEntity"),
            (100, "AcDbPolyline"), (90, str(len(pts))),
            (70, "1" if closed else "0")]
    for x, y in pts:
        body += [(10, f"{x:.6f}"), (20, f"{y:.6f}")]
    return pairs(*body)


def add_combs(src, out, seams, thickness, layer=LAYER):
    """Append combs to a copy of `src` and write `out`.

    `seams` is a list of (start, end, fingers, side). Returns the written path
    and a report per seam.

    The combs go at the end of the ENTITIES section. That section is located by
    parsing group codes rather than by matching text: DXF group-code lines may
    be padded (`  0`) or bare (`0`), and the OBJECTS section also has an ENDSEC,
    so `rpartition("ENDSEC")` finds the wrong one and a padded `pairs()` marker
    matches nothing at all.
    """
    drawing = dxf_reader.read(src)
    parts = []
    report = []
    for start, end, fingers, side in seams:
        pts = comb(start, end, thickness, fingers, side)
        parts.append(lwpolyline(pts, layer=layer))
        report.append(summarise(pts, start, end, thickness, fingers))

    text = Path(src).read_text(errors="replace")
    at = _entities_end(text)
    if at is None:
        raise dxf_reader.DxfError("no ENTITIES section found")
    text = text[:at] + "".join(parts) + text[at:]
    Path(out).write_text(text)
    return Path(out), report, drawing


def _entities_end(text):
    """Character offset just before the ENTITIES section's closing ENDSEC."""
    lines = text.splitlines(keepends=True)
    in_entities = False
    i = 0
    while i + 1 < len(lines):
        code = lines[i].strip()
        value = lines[i + 1].strip()
        if code == "0" and value == "SECTION":
            in_entities = (i + 2 < len(lines) and lines[i + 2].strip() == "2"
                           and lines[i + 3].strip() == "ENTITIES")
        elif code == "0" and value == "ENDSEC" and in_entities:
            return sum(len(x) for x in lines[:i])
        i += 1
    return None


def summarise(pts, start, end, thickness, fingers):
    """Measured properties of a comb, for the report and for --check."""
    sx, sy = start
    ex, ey = end
    length = math.hypot(ex - sx, ey - sy)
    ux, uy = (ex - sx) / length, (ey - sy) / length
    # signed distance from the seam line, and distance along it
    deep, along = [], []
    for x, y in pts:
        t = (x - sx) * ux + (y - sy) * uy
        along.append(t)
        deep.append(abs((x - sx) * uy - (y - sy) * ux))

    # the butt is the gap between the seam's end and the nearest point that is
    # off the seam line — NOT min(along), which is where the seam starts.
    off_seam = [t for t, d in zip(along, deep) if d > 1e-9]
    butt = min(min(off_seam), length - max(off_seam)) if off_seam else \
        min(along) if along else 0.0

    runs = {round(max(abs(b[0] - a[0]), abs(b[1] - a[1])), 4)
            for a, b in zip(pts, pts[1:])}
    diagonals = [(a, b) for a, b in zip(pts, pts[1:])
                 if abs(a[0] - b[0]) > 1e-9 and abs(a[1] - b[1]) > 1e-9]
    return {
        "fingers": fingers,
        "thickness": thickness,
        "seam_length": round(length, 4),
        "depth_max": round(max(deep), 6),
        "band": round(max(deep) - min(deep), 6),
        "used": round(max(along) - min(along), 4),
        "butt": round(butt, 4),
        "runs": sorted(runs),
        "diagonals": len(diagonals),
        "ok": max(deep) <= thickness + 1e-9 and not diagonals
              and butt >= MIN_BUTT - 1e-9,
    }


# ------------------------------------------------------------------ check

def read_combs(path):
    """Every open polyline in the file, as point lists — the combs."""
    drawing = dxf_reader.read(path)
    return [e.points for e in drawing.entities
            if e.kind in ("LWPOLYLINE", "POLYLINE") and not e.closed]


def check_file(path, thickness, tol=1e-6):
    """Measure every comb in a file against the depth rule."""
    combs = read_combs(path)
    if not combs:
        print(f"{Path(path).name}: no open polylines — no combs to check")
        return 1
    bad = 0
    for i, pts in enumerate(combs, 1):
        # the seam is the line the comb's butts sit on: use the extremes of the
        # path's own bounding box along its longer axis
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        horizontal = (max(xs) - min(xs)) >= (max(ys) - min(ys))
        if horizontal:
            seam = min(ys) if ys.count(min(ys)) > ys.count(max(ys)) else max(ys)
            deep = [abs(y - seam) for y in ys]
            length = max(xs) - min(xs)
        else:
            seam = min(xs) if xs.count(min(xs)) > xs.count(max(xs)) else max(xs)
            deep = [abs(x - seam) for x in xs]
            length = max(ys) - min(ys)
        runs = {round(max(abs(b[0] - a[0]), abs(b[1] - a[1])), 4)
                for a, b in zip(pts, pts[1:])}
        diagonals = sum(1 for a, b in zip(pts, pts[1:])
                        if abs(a[0] - b[0]) > tol and abs(a[1] - b[1]) > tol)
        depth = max(deep)
        ok = depth <= thickness + tol and diagonals == 0
        bad += 0 if ok else 1
        print(f"  comb {i}: spans {length:.2f} mm, runs {sorted(runs)} mm, "
              f"depth {depth:.4f} mm"
              + (f", {diagonals} diagonal(s)" if diagonals else ""))
        print(f"          {ok and 'ok' or 'FAIL'}"
              + ("" if ok else f" — a finger deeper than {thickness} mm, or a "
                               f"diagonal (a ramp, not a mating face)"))
    print(f"\n{'all combs within one thickness' if not bad else str(bad) + ' BAD'}")
    return 1 if bad else 0


# ------------------------------------------------------------------ CLI

def parse_seam(text):
    parts = [p for p in text.replace(" ", "").split(",") if p]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "a seam is x0,y0,x1,y1 — for example 0,0,100,0")
    try:
        x0, y0, x1, y1 = (float(p) for p in parts)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' has a non-number in it")
    return (x0, y0), (x1, y1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="finger-joints",
        description="Cut finger joints along the straight seams where two "
                    "shapes touch.",
    )
    ap.add_argument("dxf", help="the DXF to add joints to (or --check)")
    ap.add_argument("-o", "--output", help="where to write the jointed DXF")
    ap.add_argument("--seam", action="append", type=parse_seam, default=[],
                    metavar="x0,y0,x1,y1",
                    help="a seam to joint; repeat for more than one")
    ap.add_argument("--thickness", type=float, required=True,
                    help="the material thickness you measured, in mm — this is "
                         "the finger depth AND width")
    ap.add_argument("--fingers", type=int, default=0,
                    help="fingers per seam (default: as many as fit)")
    ap.add_argument("--side", choices=("up", "down"), default="up",
                    help="which side of the seam the fingers cut to (default up)")
    ap.add_argument("--check", action="store_true",
                    help="measure the combs already in the file instead")
    args = ap.parse_args(argv)

    if args.check:
        return check_file(args.dxf, args.thickness)

    if not args.seam:
        ap.error("give at least one --seam (or use --check)")
    if not args.output:
        ap.error("give -o/--output to write the jointed file")

    seams = []
    for start, end in args.seam:
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        if (2 - 1) * args.thickness > length:
            print(f"error: a {args.thickness} mm finger does not fit a "
                  f"{length:.1f} mm seam", file=sys.stderr)
            return 2
        if args.fingers:
            # An explicit count is honoured or refused, never silently reduced:
            # quietly changing it would hide that the request does not fit.
            n = args.fingers
            if (2 * n - 1) * args.thickness + 2 * MIN_BUTT > length + 1e-9:
                most = max(1, int((length - 2 * MIN_BUTT + args.thickness)
                                  // (2 * args.thickness)))
                print(f"error: {n} fingers of {args.thickness} mm leave less "
                      f"than {MIN_BUTT} mm at each end of a {length:.1f} mm "
                      f"seam. At most {most} fit — use --fingers {most}.",
                      file=sys.stderr)
                return 2
        else:
            # as many as fit while leaving a real butt at each end
            n = max(1, int((length - 2 * MIN_BUTT + args.thickness)
                           // (2 * args.thickness)))
        side = 1.0 if args.side == "up" else -1.0
        seams.append((start, end, n, side))

    try:
        out, report, _ = add_combs(args.dxf, args.output, seams,
                                   args.thickness)
    except (dxf_reader.DxfError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"material thickness : {args.thickness} mm")
    for i, r in enumerate(report, 1):
        print(f"seam {i}: {r['seam_length']:.1f} mm, {r['fingers']} fingers of "
              f"{r['thickness']} mm, butt {r['butt']:.2f} mm each end")
        print(f"        depth max {r['depth_max']:.4f} mm, band {r['band']:.4f} mm"
              + ("  (one thickness, ok)" if r["ok"] else "  <-- VIOLATES THE DEPTH RULE"))
    print(f"wrote              : {out}")
    return 0 if all(r["ok"] for r in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
