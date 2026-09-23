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
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tools/skill-tasks
REPO = HERE.parent.parent
CHECK = REPO / "skills" / "maker-tasks" / "check"
sys.path.insert(0, str(CHECK))
FIXTURES = HERE / "fixtures"

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
    "student": "Test Student",
    "onshape_url": "https://cad.onshape.com/documents/aaaaaaaaaaaaaaaaaaaaaaaa/w/bbbbbbbbbbbbbbbbbbbbbbbb/e/cccccccccccccccccccccccc",
    "material_thickness": "3.0",
    "self_check": "ready to submit",
}


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
        manifest={**MANIFEST, "width_before": "100"},
    )
    write(
        "cad-02-not-changed",
        entities(rectangle(0, 0, 100, 60)),
        task="cad-02-update-dimension",
        expect={"verdict": "fix", "fails": ["dims"]},
        note="still 100 wide: the dimension was never changed",
        manifest={**MANIFEST, "width_before": "100"},
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
