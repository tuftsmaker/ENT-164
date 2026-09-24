#!/usr/bin/env python3
"""Generate the fixture DXFs and their manifests.

Fixtures are tiny hand-written DXF files (ASCII, R12 style — the same shape
Onshape writes) plus a manifest each. Every fixture directory declares in
`fixture.json` which task it belongs to and what the report should say, so
`selftest.py` can check the checker rather than trusting it.

    python3 check/make_fixtures.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tools/skill-tasks
REPO = HERE.parent.parent
CHECK = REPO / "skills" / "maker-tasks" / "check"
sys.path.insert(0, str(CHECK))
FIXTURES = HERE / "fixtures"

import laser_svg  # noqa: E402  (needs the check dir on sys.path)

# ---------------------------------------------------------------- DXF writer


def pairs(*items):
    return "".join(f"{code}\r\n{value}\r\n" for code, value in items)


def header():
    # Deliberately mimics an Onshape export: AC1014, no $INSUNITS, mm implied.
    return pairs(
        (0, "SECTION"), (2, "HEADER"),
        (9, "$ACADVER"), (1, "AC1014"),
        (9, "$DWGCODEPAGE"), (3, "ANSI_1252"),
        (9, "$INSBASE"), (10, "0.0"), (20, "0.0"), (30, "0.0"),
        (9, "$EXTMIN"), (10, "0.0"), (20, "0.0"), (30, "0.0"),
        (9, "$EXTMAX"), (10, "300.0"), (20, "600.0"), (30, "0.0"),
        (9, "$LUNITS"), (70, "2"),
        (9, "$MEASUREMENT"), (70, "1"),
        (0, "ENDSEC"),
    )


def entities(each):
    out = [pairs((0, "SECTION"), (2, "ENTITIES"))]
    out.extend(each)
    out.append(pairs((0, "ENDSEC"), (0, "EOF")))
    return "".join(out)


def line(layer, x1, y1, x2, y2, closed=None):
    return pairs(
        (0, "LINE"), (8, layer), (100, "AcDbEntity"), (100, "AcDbLine"),
        (10, f"{x1}"), (20, f"{y1}"), (30, "0.0"),
        (11, f"{x2}"), (21, f"{y2}"), (31, "0.0"),
    )


def circle(layer, cx, cy, r):
    return pairs(
        (0, "CIRCLE"), (8, layer), (100, "AcDbEntity"), (100, "AcDbCircle"),
        (10, f"{cx}"), (20, f"{cy}"), (30, "0.0"),
        (40, f"{r}"),
    )


def arc(layer, cx, cy, r, start_deg, end_deg):
    """An ARC entity, the way Onshape exports a sketch arc."""
    return pairs(
        (0, "ARC"), (8, layer), (100, "AcDbEntity"), (100, "AcDbCircle"),
        (10, f"{cx}"), (20, f"{cy}"), (30, "0.0"),
        (40, f"{r}"),
        (100, "AcDbArc"),
        (50, f"{start_deg}"), (51, f"{end_deg}"),
    )


def polyline(layer, points, closed=True):
    """A closed LWPOLYLINE — what Inkscape/Illustrator write, and what a
    student gets after 'join' operations."""
    body = [(0, "LWPOLYLINE"), (8, layer), (100, "AcDbEntity"), (100, "AcDbPolyline"),
            (90, str(len(points))), (70, "1" if closed else "0")]
    for x, y in points:
        body += [(10, f"{x}"), (20, f"{y}")]
    return pairs(*body)


ONSHAPE_LAYER = "MODELSKETCH_VISIBLE"


def rectangle(x0, y0, x1, y1, layer=ONSHAPE_LAYER, open_corner=None):
    """Four sides as separate LINEs, the way Onshape exports a sketch."""
    sides = [
        ((x0, y0), (x1, y0)),
        ((x1, y0), (x1, y1)),
        ((x1, y1), (x0, y1)),
        ((x0, y1), (x0, y0)),
    ]
    out = []
    for i, (a, b) in enumerate(sides):
        if open_corner is not None and i == open_corner:
            # stop short of where it should land: a real unclosed sketch
            b = (b[0] - 0.0 if i % 2 == 0 else b[0], b[1] - 0.0 if i % 2 else b[1])
            if i == 0:
                b = (b[0] - 6.0, b[1])
            elif i == 1:
                b = (b[0], b[1] - 6.0)
            elif i == 2:
                b = (b[0] + 6.0, b[1])
            else:
                b = (b[0], b[1] + 6.0)
        out.append(line(layer, a[0], a[1], b[0], b[1]))
    return out


def write(name, body, **meta):
    folder = FIXTURES / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "part.dxf").write_text(header() + body, encoding="utf-8", newline="")
    manifest = meta.pop("manifest", {})
    lines = [f"{k}: {v}" for k, v in manifest.items()]
    (folder / "manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "fixture.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


MANIFEST = {
    "onshape_url": "https://cad.onshape.com/documents/aaaaaaaaaaaaaaaaaaaaaaaa/w/bbbbbbbbbbbbbbbbbbbbbbbb/e/cccccccccccccccccccccccc",
}
# cad-08 also reads the thickness the student measured.
JOINTS_MANIFEST = {**MANIFEST, "material_thickness": "3.0"}


def main():
    FIXTURES.mkdir(parents=True, exist_ok=True)

    # -- cad-01: the rectangle ------------------------------------------
    write(
        "cad-01-good",
        entities(rectangle(0, 0, 100, 60)),
        task="cad-01-first-sketch",
        expect={"verdict": "ready", "fails": [], "reviews": ["link"]},
        note="100x60 rectangle, four sides, closed",
        manifest=MANIFEST,
    )
    write(
        "cad-01-wrong-size",
        entities(rectangle(0, 0, 80, 60)),
        task="cad-01-first-sketch",
        expect={"verdict": "fix", "fails": ["dims", "shape"]},
        note="the classic: drew 80 mm wide instead of 100",
        manifest=MANIFEST,
    )
    write(
        "cad-01-inches",
        entities(rectangle(0, 0, 3.937, 2.362)),
        task="cad-01-first-sketch",
        expect={"verdict": "fix", "fails": ["dims"]},
        note="exported in inches: 100x60 mm reads as 3.94x2.36",
        manifest=MANIFEST,
    )
    write(
        "cad-01-open",
        entities(rectangle(0, 0, 100, 60, open_corner=0)),
        task="cad-01-first-sketch",
        expect={"verdict": "fix", "fails": ["closed"], "not_fails": ["shape"]},
        note="one side stops 6 mm short of the corner",
        manifest=MANIFEST,
    )

    # -- cad-02: the dimension change ------------------------------------
    write(
        "cad-02-good",
        entities(rectangle(0, 0, 80, 60)),
        task="cad-02-update-dimension",
        expect={"verdict": "ready", "fails": []},
        note="80x60 after the edit",
        manifest=MANIFEST,
    )
    write(
        "cad-02-not-changed",
        entities(rectangle(0, 0, 100, 60)),
        task="cad-02-update-dimension",
        expect={"verdict": "fix", "fails": ["dims"]},
        note="still 100 wide: the dimension was never changed",
        manifest=MANIFEST,
    )

    # -- cad-03: the hole ------------------------------------------------
    body = entities(rectangle(0, 0, 100, 60) + [circle(ONSHAPE_LAYER, 20, 20, 5)])
    write(
        "cad-03-good",
        body,
        task="cad-03-cut-a-hole",
        expect={"verdict": "ready", "fails": []},
        note="10 mm hole at 20,20 from the bottom-left edges",
        manifest=MANIFEST,
    )
    write(
        "cad-03-hole-too-small",
        entities(rectangle(0, 0, 100, 60) + [circle(ONSHAPE_LAYER, 20, 20, 2.5)]),
        task="cad-03-cut-a-hole",
        expect={"verdict": "fix", "fails": ["hole-size"]},
        note="5 mm hole instead of 10",
        manifest=MANIFEST,
    )
    write(
        "cad-03-hole-misplaced",
        entities(rectangle(0, 0, 100, 60) + [circle(ONSHAPE_LAYER, 50, 30, 5)]),
        task="cad-03-cut-a-hole",
        expect={"verdict": "fix", "fails": ["hole-place"]},
        note="hole dropped in the middle instead of 20,20 from the edges",
        manifest=MANIFEST,
    )
    write(
        "cad-03-hole-stray",
        entities(rectangle(0, 0, 100, 60) + [circle(ONSHAPE_LAYER, 20, 20, 5), circle(ONSHAPE_LAYER, 70, 40, 5)]),
        task="cad-03-cut-a-hole",
        expect={"verdict": "fix", "fails": ["hole-count", "profiles"]},
        note="two holes: one is a leftover from practising",
        manifest=MANIFEST,
    )
    write(
        "cad-03-hole-outside",
        entities(rectangle(0, 0, 100, 60) + [circle(ONSHAPE_LAYER, 99, 21, 5)]),
        task="cad-03-cut-a-hole",
        expect={"verdict": "fix", "fails": ["hole-place", "hole-inside"],
                "not_fails": ["closed"]},
        note="hole crosses the right edge: a notch, and nothing left of the wall",
        manifest=MANIFEST,
    )

    # -- cad-04: centred -------------------------------------------------
    write(
        "cad-04-good",
        entities(rectangle(0, 0, 100, 60) + [circle(ONSHAPE_LAYER, 50, 30, 5)]),
        task="cad-04-center-a-hole",
        expect={"verdict": "ready", "fails": []},
        note="hole exactly at the centre",
        manifest=MANIFEST,
    )
    write(
        "cad-04-off-centre",
        entities(rectangle(0, 0, 100, 60) + [circle(ONSHAPE_LAYER, 50.9, 30, 5)]),
        task="cad-04-center-a-hole",
        expect={"verdict": "fix", "fails": ["hole-centred"]},
        note="0.9 mm off centre: eyeballed rather than dimensioned",
        manifest=MANIFEST,
    )
    write(
        "cad-04-guides-left-in",
        entities([
            polyline(ONSHAPE_LAYER, [(0, 0), (100, 0), (100, 60), (0, 60)]),
            circle(ONSHAPE_LAYER, 50, 30, 5),
            line(ONSHAPE_LAYER, 0, 30, 100, 30),
            line(ONSHAPE_LAYER, 50, 0, 50, 60),
        ]),
        task="cad-04-center-a-hole",
        expect={"verdict": "fix", "fails": ["closed"], "reviews": ["no-guides"]},
        note="guide lines left in the file: flagged for a person, and the dangling ends fail",
        manifest=MANIFEST,
    )

    # -- cad-05: corner --------------------------------------------------
    write(
        "cad-05-good",
        entities(rectangle(0, 0, 100, 60) + [circle(ONSHAPE_LAYER, 80, 40, 5)]),
        task="cad-05-corner-hole",
        expect={"verdict": "ready", "fails": []},
        note="hole 20 mm from the right and top edges",
        manifest=MANIFEST,
    )
    write(
        "cad-05-too-close",
        entities(rectangle(0, 0, 100, 60) + [circle(ONSHAPE_LAYER, 96, 56, 5)]),
        task="cad-05-corner-hole",
        expect={"verdict": "fix", "fails": ["hole-corner", "hole-inside"]},
        note="hole 4 mm from the corner: too thin a wall",
        manifest=MANIFEST,
    )

    # -- cad-06: mirror --------------------------------------------------
    write(
        "cad-06-good",
        entities(rectangle(0, 0, 70, 60)),
        task="cad-06-mirror",
        expect={"verdict": "ready", "fails": []},
        note="70x60, symmetric about the vertical centre line",
        manifest=MANIFEST,
    )
    write(
        "cad-06-asymmetric",
        entities([
            # 70 mm wide, but with a 12 mm notch missing on the right and
            # present on the left — mirroring was abandoned half way.
            polyline(ONSHAPE_LAYER, [(0, 0), (70, 0), (70, 24), (58, 24), (58, 36), (70, 36), (70, 60), (0, 60), (0, 54), (12, 54), (12, 48), (0, 48)]),
        ]),
        task="cad-06-mirror",
        expect={"verdict": "fix", "fails": ["symmetric"], "not_fails": ["dims", "closed"]},
        note="notches on one side only: the halves are not mirror images",
        manifest=MANIFEST,
    )
    write(
        "cad-06-wrong-width",
        entities(rectangle(0, 0, 100, 60)),
        task="cad-06-mirror",
        expect={"verdict": "fix", "fails": ["dims"]},
        note="still the 100 mm rectangle",
        manifest=MANIFEST,
    )

    # -- cad-07: the trim tool -------------------------------------------
    # Rectangle 100x60 whose right edge is replaced by an arc bulging to x=112.
    # The arc's circle has centre (68.5, 30) and radius 43.5, so it meets both
    # right corners exactly.
    TRIMMED = [
        line(ONSHAPE_LAYER, 0, 0, 100, 0),
        arc(ONSHAPE_LAYER, 68.5, 30, 43.5, -43.6028, 43.6028),
        line(ONSHAPE_LAYER, 100, 60, 0, 60),
        line(ONSHAPE_LAYER, 0, 60, 0, 0),
    ]
    write(
        "cad-07-good",
        entities(TRIMMED),
        task="cad-07-trim-tool",
        expect={"verdict": "ready", "fails": []},
        note="arc worked into the outline, straight edge trimmed away",
        manifest=MANIFEST,
    )
    # Untrimmed: the straight right edge is still there AND the arc is present,
    # so there are two closed regions — the rectangle, and the lens the arc makes
    # against that edge. That is the drawing the video warns about.
    write(
        "cad-07-untrimmed",
        entities([
            line(ONSHAPE_LAYER, 0, 0, 100, 0),
            line(ONSHAPE_LAYER, 100, 0, 100, 60),
            arc(ONSHAPE_LAYER, 68.5, 30, 43.5, -43.6028, 43.6028),
            line(ONSHAPE_LAYER, 100, 60, 0, 60),
            line(ONSHAPE_LAYER, 0, 60, 0, 0),
        ]),
        task="cad-07-trim-tool",
        expect={"verdict": "fix", "fails": ["single"]},
        note="straight edge and arc both present: leftover geometry the laser would cut",
        manifest=MANIFEST,
    )
    write(
        "cad-07-no-curve",
        entities(rectangle(0, 0, 100, 60)),
        task="cad-07-trim-tool",
        expect={"verdict": "fix", "fails": ["curved"]},
        note="no arc at all — the plain rectangle",
        manifest=MANIFEST,
    )

    # -- cad-08: laser cut joints ----------------------------------------
    # An outline with fingers on the left and right, each 3 mm wide.
    def finger_outline(t):
        """100x60 with 3 fingers of width `t` on the left and right edges."""
        pts = []
        # bottom edge, left to right
        pts += [(0, 0), (100, 0)]
        # right edge: three tabs sticking out by 6 mm, `t` wide, spaced `t` apart
        y = 0.0
        for i in range(3):
            y0, y1 = y + t, y + 2 * t
            pts += [(100, y0), (106, y0), (106, y1), (100, y1)]
            y = y1
        pts += [(100, 60)]
        # top edge back to the left
        pts += [(0, 60)]
        # left edge: matching slots cut in by 6 mm
        y = 0.0
        for i in range(3):
            y0, y1 = y + t, y + 2 * t
            pts += [(0, y1), (-6, y1), (-6, y0), (0, y0)]
            y = y1
        pts += [(0, 0)]
        return pts

    write(
        "cad-08-good",
        entities([polyline(ONSHAPE_LAYER, finger_outline(3.0))]),
        task="cad-08-laser-joints",
        expect={"verdict": "ready", "fails": []},
        note="3 mm fingers matching the 3 mm measured material",
        manifest=JOINTS_MANIFEST,
    )
    write(
        "cad-08-wrong-joint",
        entities([polyline(ONSHAPE_LAYER, finger_outline(2.0))]),
        task="cad-08-laser-joints",
        expect={"verdict": "fix", "fails": ["joints"]},
        note="2 mm joints against 3 mm material — too small by 1 mm",
        manifest=JOINTS_MANIFEST,
    )
    write(
        "cad-08-no-joints",
        entities(rectangle(0, 0, 100, 60)),
        task="cad-08-laser-joints",
        expect={"verdict": "fix", "fails": ["joints"]},
        note="a plain rectangle: no slots or fingers at all",
        manifest=JOINTS_MANIFEST,
    )

    # -- cad-09: the laser-ready SVG ------------------------------------
    # The good one is what the converter really writes, plus the etch text a
    # student would add in Inkscape. The bad ones break one thing each, the two
    # the video warns about: lines left black, and a non-hairline width.
    svg_manifest = {
        "source_dxf": "part.dxf — cad-08-laser-joints",
    }

    def write_svg(name, body, transform=None, expect=None, note="", manifest=None):
        folder = FIXTURES / name
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "part.dxf"
            src.write_text(header() + body, encoding="utf-8", newline="")
            laser_svg.convert(src, folder / "part-laser-ready.svg")
        svg_path = folder / "part-laser-ready.svg"
        if transform:
            svg_path.write_text(transform(svg_path.read_text(encoding="utf-8")),
                                encoding="utf-8")
        lines = [f"{k}: {v}" for k, v in (manifest or {}).items()]
        (folder / "manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (folder / "fixture.json").write_text(
            json.dumps({"task": "cad-09-laser-ready", "expect": expect, "note": note},
                       indent=2) + "\n",
            encoding="utf-8")

    def add_etch(svg):
        return svg.replace(
            "</svg>",
            '  <text id="etch" x="10" y="30" style="fill:#000000;stroke:none;'
            'font-size:6px">ENT-164</text>\n</svg>')

    ready = entities(rectangle(0, 0, 100, 60))
    write_svg(
        "cad-09-good", ready, transform=add_etch,
        manifest=svg_manifest,
        expect={"verdict": "ready", "fails": [], "reviews": ["look"]},
        note="red hairlines to cut, black text to etch",
    )
    write_svg(
        "cad-09-black-lines", ready,
        transform=lambda s: s.replace("stroke:#ff0000", "stroke:#000000"),
        manifest=svg_manifest,
        expect={"verdict": "fix", "fails": ["colours"]},
        note="the DXF's default black lines: nothing will cut",
    )
    write_svg(
        "cad-09-not-hairline", ready,
        transform=lambda s: s.replace("-inkscape-stroke:hairline", ""),
        manifest=svg_manifest,
        expect={"verdict": "fix", "fails": ["colours"]},
        note="red, but a wide line: the laser follows the centre of a hairline",
    )

    # -- broken files ----------------------------------------------------
    folder = FIXTURES / "not-a-dxf"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "part.dxf").write_text("this is not a DXF at all\njust some text\n", encoding="utf-8")
    (folder / "manifest.md").write_text("\n".join(f"{k}: {v}" for k, v in MANIFEST.items()) + "\n", encoding="utf-8")
    (folder / "fixture.json").write_text(
        json.dumps(
            {
                "task": "cad-01-first-sketch",
                "expect": {"verdict": "fix", "fails": ["parses"]},
                "note": "a text file renamed to .dxf",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    folder = FIXTURES / "empty-entities"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "part.dxf").write_text(header() + entities([]), encoding="utf-8", newline="")
    (folder / "manifest.md").write_text("\n".join(f"{k}: {v}" for k, v in MANIFEST.items()) + "\n", encoding="utf-8")
    (folder / "fixture.json").write_text(
        json.dumps(
            {
                "task": "cad-01-first-sketch",
                "expect": {"verdict": "fix", "fails": ["parses"]},
                "note": "valid DXF structure, no geometry",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    count = len([p for p in FIXTURES.iterdir() if p.is_dir()])
    print(f"wrote {count} fixtures to {FIXTURES}")


if __name__ == "__main__":
    main()
