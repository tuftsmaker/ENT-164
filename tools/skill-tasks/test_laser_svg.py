#!/usr/bin/env python3
"""Prove the DXF -> laser-ready SVG converter is correct, offline.

`laser_svg.py` is shipped to students, and three of its properties are the kind
that fail silently: the hairline encoding (the obvious spelling renders at 1 mm),
the arc page box (a whole-circle box pads the page around nothing), and the arc
sweep direction (a Y-flip can mirror it). Each is checked here against a known
answer rather than against the converter's own output.

Nothing is rasterised and nothing is imported from outside the skill, so this
runs anywhere Python does, including CI and a student's laptop.

    python3 tools/skill-tasks/test_laser_svg.py
"""

from __future__ import annotations

import math
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tools/skill-tasks
REPO = HERE.parent.parent
CHECK = REPO / "skills" / "maker-tasks" / "check"
sys.path.insert(0, str(CHECK))

import laser_svg  # noqa: E402

FIXTURES = HERE / "fixtures"
SVG_NS = "{http://www.w3.org/2000/svg}"

HAIRLINE_PARTS = ("stroke-width:1px", "vector-effect:non-scaling-stroke",
                  "-inkscape-stroke:hairline")

results: list = []


def check(label, ok, detail=""):
    results.append((label, ok, detail))
    print(f"{'ok  ' if ok else 'FAIL'} {label:<52} {detail}")


def path_d(el):
    return el.get("d") or ""


def numbers(text):
    return [float(v) for v in re.findall(r"-?[0-9.]+", text)]


def convert(path, margin=0.0):
    out = Path(tempfile.mkdtemp()) / "out.svg"
    written, report, notes = laser_svg.convert(path, out, margin)
    root = ET.parse(written).getroot()
    return root, report, notes, written


def main() -> int:
    # ---- 1. the file the checker's own fixtures call a good rectangle -------
    good = FIXTURES / "cad-01-good" / "part.dxf"
    if not good.exists():
        print(f"no fixtures at {FIXTURES} — run make_fixtures.py first", file=sys.stderr)
        return 2

    root, report, notes, written = convert(good)
    els = root.findall(f"{SVG_NS}path") + root.findall(f"{SVG_NS}circle")
    check("rectangle: four cut elements written", len(els) == 4, f"{len(els)}")

    # page is the part, in millimetres, at 1 unit = 1 mm
    check("rectangle: page is 100 x 60 mm",
          root.get("width") == "100mm" and root.get("height") == "60mm",
          f'{root.get("width")} x {root.get("height")}')
    check("rectangle: viewBox matches the page",
          root.get("viewBox") == "0 0 100 60", root.get("viewBox") or "")
    check("rectangle: reported size is 100 x 60",
          abs(report["part_w"] - 100) < 1e-6 and abs(report["part_h"] - 60) < 1e-6,
          f'{report["part_w"]:.3f} x {report["part_h"]:.3f}')

    # every path pure red, unfilled, opaque, hairline
    styles = [el.get("style") or "" for el in els]
    check("rectangle: every path is pure red, unfilled, opaque",
          all("stroke:#ff0000" in s and "fill:none" in s and "stroke-opacity:1" in s
              for s in styles))
    check("rectangle: hairline written as Inkscape's three declarations",
          all(all(p in s for p in HAIRLINE_PARTS) for s in styles))
    # the trap: the naive attribute renders at 1 mm in Inkscape, so it must not
    # be the only thing we rely on
    check("rectangle: no bare stroke-width=\"hairline\" in the output",
          "stroke-width=\"hairline\"" not in written.read_text())

    # corners exactly on the rectangle, all four sides present
    coords = set()
    for el in els:
        for mx, my in re.findall(r"(-?[0-9.]+),(-?[0-9.]+)", path_d(el)):
            coords.add((float(mx), float(my)))
    want = {(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)}
    check("rectangle: all four corners exactly on the rectangle",
          coords == want, f"{len(coords)} distinct corners")

    # ---- 2. a margin widens the page and centres the part -------------------
    root2, rep2, _, _ = convert(good, margin=5.0)
    check("margin 5: page grows to 110 x 70 mm",
          root2.get("width") == "110mm" and root2.get("height") == "70mm",
          f'{root2.get("width")} x {root2.get("height")}')
    d2 = " ".join(path_d(el) for el in root2.findall(f"{SVG_NS}path"))
    c2 = [(float(a), float(b)) for a, b in re.findall(r"(-?[0-9.]+),(-?[0-9.]+)", d2)]
    xs = [p[0] for p in c2]
    ys = [p[1] for p in c2]
    check("margin 5: part is inset 5 mm on every side",
          min(xs) == 5.0 and max(xs) == 105.0 and min(ys) == 5.0 and max(ys) == 65.0,
          f"x {min(xs)}..{max(xs)}, y {min(ys)}..{max(ys)}")

    # ---- 3. an arc: page box, and the sweep direction ----------------------
    arc_fixture = FIXTURES / "cad-07-good" / "part.dxf"
    if arc_fixture.exists():
        root3, rep3, _, written3 = convert(arc_fixture)
        # The DXF is 112 x 60 with the arc on the right edge. A whole-circle
        # page box would report 112 x 87 and shift the part down by 13.5.
        check("arc: page box is 112 x 60, not the whole circle",
              abs(rep3["part_h"] - 60) < 1e-6, f'h={rep3["part_h"]:.3f}')
        check("arc: the page is exactly the part's bounding box",
              abs(rep3["page_h"] - 60) < 1e-6 and abs(rep3["page_w"] - 112) < 1e-6,
              f'{rep3["page_w"]:.3f} x {rep3["page_h"]:.3f}')

        arcs = [el for el in root3.findall(f"{SVG_NS}path") if " A " in path_d(el)]
        check("arc: one real arc written, not a polyline", len(arcs) == 1, f"{len(arcs)}")
        if arcs:
            d = path_d(arcs[0])
            # "M sx,sy A rx,ry rotation large-arc sweep ex,ey"
            nums = numbers(d)
            sx, sy, rx, ry, rotation, large, sweep, ex, ey = nums[:9]
            # The CAD arc sweeps 87.2 degrees, so it is the minor arc.
            check("arc: large-arc-flag is 0 (87 deg sweep)", large == 0, f"large={large}")
            # Y is flipped into SVG space, so the CCW CAD arc is still CCW
            # on screen, which is SVG sweep-flag 0.
            check("arc: sweep-flag is 0 after the Y-flip", sweep == 0, f"sweep={sweep}")
            check("arc: no rotation on the ellipse (a circular arc)", rotation == 0)
            check("arc: radius is the DXF radius (43.5 mm)",
                  abs(rx - 43.5) < 1e-3 and abs(ry - 43.5) < 1e-3, f"r={rx}")
            # The arc joins the rectangle's right edge at both corners: the
            # endpoints sit at x=100, one at the bottom of the page (y=60) and
            # one at the top (y=0). It is the bulge (out to x=112) that makes
            # the page 112 wide, so the endpoints are NOT at x=112.
            check("arc: endpoints are the right edge's two corners",
                  abs(sx - 100) < 0.01 and abs(ex - 100) < 0.01
                  and sorted([round(sy), round(ey)]) == [0, 60],
                  f"({sx},{sy}) -> ({ex},{ey})")

    # ---- 4. a circle keeps its own element and its size --------------------
    circ_fixture = FIXTURES / "cad-03-good" / "part.dxf"
    if circ_fixture.exists():
        root4, rep4, _, _ = convert(circ_fixture)
        circles = root4.findall(f"{SVG_NS}circle")
        check("circle: written as <circle>, not a 600-point path",
              len(circles) == 1, f"{len(circles)}")
        if circles:
            r = float(circles[0].get("r"))
            check("circle: radius is 5 mm (a 10 mm hole)",
                  abs(r - 5.0) < 1e-6, f"r={r}")
            check("circle: carries the same red hairline style",
                  all(p in (circles[0].get("style") or "") for p in HAIRLINE_PARTS))

    # ---- 5. duplicate paths are reported, not removed ----------------------
    simple = FIXTURES / "cad-01-good" / "part.dxf"
    _, rep_simple, _, _ = convert(simple)
    check("duplicates: a clean rectangle reports none",
          rep_simple.get("coincident") == [], f"{rep_simple.get('coincident')}")

    # Every entity kind must survive signature-building: a NameError or a
    # missing branch here only shows up on the kind that hits it, so sweep all
    # of them rather than trusting the fixtures that happen to exist.
    kinds_seen = set()
    for fixture in sorted(FIXTURES.iterdir()):
        dxf = fixture / "part.dxf"
        if not dxf.exists():
            continue
        try:
            drawing = laser_svg.dxf_reader.read(dxf)
        except Exception:  # noqa: BLE001 - a deliberately bad fixture
            continue
        for ent in laser_svg.drawable(drawing)[0]:
            kinds_seen.add(ent.kind)
            try:
                laser_svg._geom_signature(ent)
            except Exception as exc:  # noqa: BLE001 - that is the point
                check(f"signature: {ent.kind} does not raise", False, repr(exc)[:60])
                break
        try:
            laser_svg.coincident_paths(laser_svg.drawable(drawing)[0])
        except Exception as exc:  # noqa: BLE001
            check(f"coincident_paths: {fixture.name} does not raise", False,
                  repr(exc)[:60])
    check("signature: every entity kind exercised without raising",
          True, ", ".join(sorted(kinds_seen)))

    # Build a rectangle with one side drawn twice, using the same DXF writer the
    # fixtures come from (string surgery on CRLF files is easy to get wrong).
    sys.path.insert(0, str(HERE))
    try:
        import make_fixtures as mf  # noqa: E402

        # Build the entity list first: entities() wraps it with SECTION/ENDSEC
        # and EOF, so anything appended after that call is outside the section
        # and (correctly) ignored — a mistake this test made once already.
        parts = list(mf.rectangle(0, 0, 100, 60))
        parts.append(mf.line(mf.ONSHAPE_LAYER, 0, 0, 100, 0))  # bottom edge again
        twice = Path(tempfile.mkdtemp()) / "twice.dxf"
        twice.write_bytes(mf.entities(parts).encode("utf-8"))
        _, rep_dup, _, _ = convert(twice)
        reported = rep_dup.get("coincident", [])
        check("duplicates: a repeated side is reported",
              len(reported) == 1 and reported[0]["count"] == 2,
              f"{reported}")
    except Exception as exc:  # noqa: BLE001 - a broken fixture writer is a failure
        check("duplicates: could build the repeated-side case", False, str(exc)[:60])

    # ---- 6. errors are the checker's own wording ---------------------------
    bad = FIXTURES / "not-a-dxf" / "part.dxf"
    if bad.exists():
        try:
            convert(bad)
            check("a non-DXF raises DxfError", False, "no error raised")
        except laser_svg.dxf_reader.DxfError as exc:
            check("a non-DXF raises DxfError", True, str(exc)[:40])

    # ---- 6. the converter's output passes the cad-09 checker ---------------
    # These two halves are written by different hands and must agree: the
    # converter writes `fill:none` for cuts, and the svg_laser_ready check must
    # accept that. It did not once, and nothing caught it because no test ran
    # one against the other.
    #
    # Skipped when the cad-09 task is not present, so this file can be committed
    # independently of that task landing.
    cad09 = CHECK.parent / "tasks" / "cad-09-laser-ready.yml"
    if not cad09.exists():
        print(f"skip cad-09: {cad09.name} is not in this tree yet")
    for fixture in ("cad-01-good", "cad-07-good") if cad09.exists() else ():
        dxf = FIXTURES / fixture / "part.dxf"
        if not dxf.exists():
            continue
        out = Path(tempfile.mkdtemp()) / "part-laser-ready.svg"
        laser_svg.convert(dxf, out)
        try:
            import runner  # noqa: E402

            sub = runner.Submission(source=out.parent)
            sub.files["part-laser-ready.svg"] = out
            sub.manifest = {"material_thickness": "3.0", "source_dxf": dxf.name,
                            "self_check": "ready"}
            task_def = runner.load_task("cad-09-laser-ready")
            report = runner.run(task_def, sub)
            bad = [c.id for c in report.failures]
            # Assert the colour criterion PASSES, not merely that nothing failed.
            # A criterion whose check function is missing becomes `review`, not
            # `fail` (runner._run_criterion), so "no failures" is also true when
            # the check does not exist at all — which is not what this test is
            # for. The pass must be a real pass.
            status = {c.id: c.status for c in report.criterion_results}
            colours_ok = status.get("colours") == "pass"
            check(f"cad-09: the converter's output passes ({fixture})",
                  not bad and colours_ok,
                  f"failures {bad}, colours {status.get('colours')!r}"
                  if (bad or not colours_ok) else "no failures")
        except Exception as exc:  # noqa: BLE001 - report, do not mask
            check(f"cad-09: the converter's output passes ({fixture})", False,
                  repr(exc)[:60])

    failures = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failures)}/{len(results)} checks passed")
    if failures:
        print("FAILED:", ", ".join(r[0] for r in failures))
        return 1
    print("the converter's known answers all hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
