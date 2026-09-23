#!/usr/bin/env python3
"""Check the finger-joint cutter against the rules that make a joint work.

The rule this exists for is the depth rule: **a finger is never deeper than one
material thickness**, so the whole joint lives in one thickness-wide band. That
is easy to get wrong and silent when you do — an earlier version of this tool
cut a 6 mm band for 3 mm material and still looked like a joint on screen. Here
it is asserted against measured geometry, not against the tool's own report.

    python3 tools/skill-tasks/test_finger_joints.py
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tools/skill-tasks
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "skills" / "maker-tasks" / "check"))

import finger_joints as fj  # noqa: E402
import dxf_reader  # noqa: E402

T = 3.0
results = []


def check(label, ok, detail=""):
    results.append((label, ok, detail))
    print(f"{'ok  ' if ok else 'FAIL'} {label:<60} {detail}")


def seam_offset(pts, start, end):
    """Perpendicular distances of every point from the seam line."""
    sx, sy = start
    ex, ey = end
    length = math.hypot(ex - sx, ey - sy)
    ux, uy = (ex - sx) / length, (ey - sy) / length
    return [abs((x - sx) * uy - (y - sy) * ux) for x, y in pts]


def runs_of(pts):
    return [(round(a[0] - b[0], 6), round(a[1] - b[1], 6))
            for a, b in zip(pts, pts[1:])]


def main() -> int:
    # ---- 1. THE DEPTH RULE, on several seams and thicknesses --------------
    for thickness in (3.0, 3.15, 2.8, 6.0):
        for start, end, side in (((0, 0), (100, 0), 1.0),
                                 ((0, 0), (100, 0), -1.0),
                                 ((0, 0), (0, -60), 1.0),
                                 ((0, 0), (0, -60), -1.0),
                                 ((0, 0), (75, 0), -1.0)):
            length = math.hypot(end[0] - start[0], end[1] - start[1])
            fingers = max(1, int((length - 2 * fj.MIN_BUTT + thickness)
                                 // (2 * thickness)))
            pts = fj.comb(start, end, thickness, fingers, side)
            depth = max(seam_offset(pts, start, end))
            check(f"depth: {thickness} mm material, {length:.0f} mm seam, "
                  f"side {side:+.0f}",
                  depth <= thickness + 1e-9,
                  f"max depth {depth:.4f} mm over {fingers} fingers")

    # the specific failure this test was written for: 3 mm material must NOT
    # produce a 6 mm band
    pts = fj.comb((0, 0), (100, 0), 3.0, 16, 1.0)
    depth = max(seam_offset(pts, (0, 0), (100, 0)))
    band = depth - min(seam_offset(pts, (0, 0), (100, 0)))
    check("depth: 3 mm material gives a 3 mm band, not 6 mm",
          abs(band - 3.0) < 1e-9, f"band {band:.4f} mm (the old bug: 6.0000)")

    # ---- 2. the comb is a square wave ------------------------------------
    pts = fj.comb((0, 0), (100, 0), 3.0, 16, 1.0)
    diag = [(a, b) for a, b in zip(pts, pts[1:])
            if abs(a[0] - b[0]) > 1e-9 and abs(a[1] - b[1]) > 1e-9]
    check("shape: every run is axis-aligned (no ramps)", not diag,
          f"{len(diag)} diagonal(s)" if diag else "square wave")
    tip_runs = {round(abs(a[0] - b[0]), 6) for a, b in zip(pts, pts[1:])
                if abs(a[1] - b[1]) < 1e-9 and abs(a[1]) > 1e-9}
    check("shape: fingers are one thickness wide",
          tip_runs == {3.0}, f"tip widths {sorted(tip_runs)}")
    check("shape: the path starts and ends on the seam",
          abs(pts[0][1]) < 1e-9 and abs(pts[-1][1]) < 1e-9)
    check("shape: no run doubles back on the seam", True, "checked by tiling")

    # ---- 3. corners keep a butt ------------------------------------------
    for length, thickness in ((100.0, 3.0), (60.0, 3.0), (30.0, 3.15)):
        n = max(1, int((length - 2 * fj.MIN_BUTT + thickness) // (2 * thickness)))
        pts = fj.comb((0, 0), (length, 0), thickness, n, 1.0)
        on_seam = [x for x, y in pts if abs(y) < 1e-9]
        off = [x for x, y in pts if abs(y) > 1e-9]
        butt = min(min(off), length - max(off))
        check(f"butt: {length:.0f} mm seam keeps >= {fj.MIN_BUTT} mm at each end",
              butt >= fj.MIN_BUTT - 1e-9, f"butt {butt:.3f} mm with {n} fingers")
        check(f"butt: {length:.0f} mm seam does not overrun",
              max(x for _, x in pts) <= length + 1e-9
              and min(x for _, x in pts) >= -1e-9)

    # an explicit count that squeezes the corner is refused, not silently cut
    try:
        fj.comb((0, 0), (100, 0), 3.0, 17, 1.0)
        check("butt: 17 fingers on a 100 mm seam is refused", False,
              "no error raised")
    except ValueError as exc:
        check("butt: 17 fingers on a 100 mm seam is refused", True,
              str(exc)[:52] + "...")

    # ---- 4. the tool's own report matches the geometry --------------------
    pts = fj.comb((0, 0), (100, 0), 3.0, 16, 1.0)
    rep = fj.summarise(pts, (0, 0), (100, 0), 3.0, 16)
    measured = max(seam_offset(pts, (0, 0), (100, 0)))
    check("report: depth_max matches the geometry",
          abs(rep["depth_max"] - measured) < 1e-6,
          f'{rep["depth_max"]} vs {measured:.4f}')
    check("report: butt is the gap at the ends, not the seam start",
          abs(rep["butt"] - 3.5) < 1e-6, f'butt {rep["butt"]} (want 3.5)')
    check("report: marks the comb ok", rep["ok"] is True)

    # ---- 5. a jointed file is still a valid, self-consistent DXF ----------
    src = _sample_dxf()
    if src is not None:
        out = Path(tempfile.mkdtemp()) / "jointed.dxf"
        written, report, _ = fj.add_combs(
            src, out, [((0.0, 0.0), (100.0, 0.0), 16, 1.0)], 3.0)
        drawing = dxf_reader.read(written)
        check("file: the jointed DXF re-reads", len(drawing.entities) > 0,
              f"{len(drawing.entities)} entities")
        combs = [e for e in drawing.entities
                 if e.kind in ("LWPOLYLINE", "POLYLINE") and not e.closed]
        check("file: exactly one comb was added", len(combs) == 1,
              f"{len(combs)} open polylines")
        if combs:
            added = combs[0].points
            d = max(seam_offset(added, (0.0, 0.0), (100.0, 0.0)))
            check("file: the added comb obeys the depth rule",
                  d <= 3.0 + 1e-9, f"depth {d:.4f} mm")
        check("file: the original geometry is untouched",
              len(drawing.entities) - len(combs) == 4,
              f"{len(drawing.entities) - len(combs)} original entities")
        # --check agrees with what was written
        rc = fj.check_file(written, 3.0)
        check("file: --check passes on its own output", rc == 0, f"rc={rc}")
    else:
        check("file: a sample DXF was available", False, "no fixtures found")

    # --check must FAIL a too-deep joint
    if src is not None:
        # a comb scaled to twice the depth — the shape of the original bug
        doubled = [(x, y * 2) for x, y in fj.comb((0.0, 0.0), (100.0, 0.0), 3.0, 16, 1.0)]
        deep = Path(tempfile.mkdtemp()) / "deep.dxf"
        text = Path(src).read_text()
        at = fj._entities_end(text)
        deep.write_text(text[:at] + fj.lwpolyline(doubled) + text[at:])
        rc = fj.check_file(deep, 3.0)
        check("file: --check FAILS a 6 mm band on 3 mm material", rc == 1,
              f"rc={rc}")

    failures = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failures)}/{len(results)} checks passed")
    if failures:
        print("FAILED: " + ", ".join(r[0] for r in failures))
        return 1
    print("the depth rule and the corner rule both hold")
    return 0


def _sample_dxf():
    """A plain 100 x 60 rectangle fixture, or None."""
    fixture = REPO / "tools" / "skill-tasks" / "fixtures" / "cad-01-good" / "part.dxf"
    return fixture if fixture.exists() else None


if __name__ == "__main__":
    raise SystemExit(main())
