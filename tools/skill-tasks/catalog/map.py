"""The task map: the whole qualification as one picture.

A dependency graph built from each task's `prereqs`, so it cannot drift from
the task files: change a prerequisite and the map redraws. Tasks sit in columns
by how deep they are in the chain, and every node links to its task page.

The bottom band is the part that is not a file: every task signed, then one
supervised cut, then the qualification. It is drawn differently on purpose —
that step happens at Nolop, with a person watching.
"""

from __future__ import annotations

import html

# Geometry, in SVG user units. Everything below is derived from these, so the
# layout stays consistent if a number changes.
NODE_W = 180
NODE_H = 68
COL_GAP = 44
ROW_GAP = 16
MARGIN = 8

BADGE_R = 11
TEXT_PAD = 14
TITLE_SIZE = 12.0
TITLE_LINE = 15.0
META_SIZE = 10.5

GATE_GAP_BEFORE = 38  # space between the graph and the "all tasks" rule
GATE_GAP_AFTER = 30
GATE_H = 58
SUPERVISED_W = 210
QUALIFICATION_W = 240
GATE_ARROW = 50

INK = "#0d1526"
MUTED = "#5f6b7a"
LINE = "#e6eaf1"
LINE_STRONG = "#d5dce7"
BLUE = "#1F6FD0"
PAPER = "#ffffff"


# ---------------------------------------------------------------- text


def wrap_title(text, max_chars=24):
    text = str(text)
    """One or two *balanced* lines. SVG will not wrap text for us, so the
    split happens here — and balanced, because a greedy split turns
    "Adding a Circle to Cut a Hole" into a long line and the word "Hole"."""
    if len(text) <= max_chars:
        return [str(text)]
    words = text.split()
    best = None
    for i in range(1, len(words)):
        left = " ".join(words[:i])
        right = " ".join(words[i:])
        longest = max(len(left), len(right))
        if longest <= max_chars and (best is None or longest < best[0]):
            best = (longest, [left, right])
    if best:
        return best[1]
    # Nothing fits in two lines: fall back to the midpoint, closest to balanced.
    mid = len(words) // 2
    return [" ".join(words[:mid]), " ".join(words[mid:])]


# ---------------------------------------------------------------- layout


def depths(tasks):
    """How far each task is down the chain. Longest path from a root, so a task
    with two prerequisites sits after both of them."""
    memo = {}

    def depth(task_id):
        if task_id in memo:
            return memo[task_id]
        parents = [p for p in tasks[task_id].get("prereqs") or [] if p in tasks]
        memo[task_id] = 0 if not parents else 1 + max(depth(p) for p in parents)
        return memo[task_id]

    for task_id in tasks:
        depth(task_id)
    return memo


def render_svg(tasks, unit=None) -> str:
    """`tasks` is a list of task dicts; `unit` the qualification (optional)."""
    by_id = {t["id"]: t for t in tasks}
    if not by_id:
        return '<p class="tm-empty">No tasks yet.</p>'

    depth_of = depths(by_id)
    columns = {}
    for task in tasks:
        columns.setdefault(depth_of[task["id"]], []).append(task)
    for group in columns.values():
        group.sort(key=lambda t: t.get("order", 99))

    max_depth = max(columns)
    max_rows = max(len(g) for g in columns.values())

    graph_h = max_rows * NODE_H + max(0, max_rows - 1) * ROW_GAP
    width = MARGIN * 2 + (max_depth + 1) * NODE_W + max_depth * COL_GAP
    center_x = width / 2

    # -- positions, with each column centred vertically -------------------
    positions = {}
    for d, group in columns.items():
        col_h = len(group) * NODE_H + max(0, len(group) - 1) * ROW_GAP
        offset = (graph_h - col_h) / 2
        for i, task in enumerate(group):
            positions[task["id"]] = (
                MARGIN + d * (NODE_W + COL_GAP),
                MARGIN + offset + i * (NODE_H + ROW_GAP),
            )

    graph_bottom = MARGIN + graph_h
    rule_y = graph_bottom + GATE_GAP_BEFORE
    gate_y = rule_y + GATE_GAP_AFTER
    height = gate_y + GATE_H + 12

    # -- the gate band: every task -> supervised cut -> qualification -----
    gate_total = SUPERVISED_W + GATE_ARROW + QUALIFICATION_W
    gate_x = center_x - gate_total / 2
    supervised_x = gate_x
    qualification_x = gate_x + SUPERVISED_W + GATE_ARROW

    parts = [
        f'<svg class="tm-svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'role="img" aria-labelledby="tm-title tm-desc" '
        f'xmlns="http://www.w3.org/2000/svg">',
        "<title id=\"tm-title\">Maker skills task map</title>",
        f'<desc id="tm-desc">{len(tasks)} tasks in their dependency order, then a '
        f'supervised cut, then the {html.escape(str((unit or {}).get("title", "qualification")))} '
        f"qualification.</desc>",
        _defs(),
    ]

    # edges first, so nodes sit on top of them
    for task in tasks:
        for parent in task.get("prereqs") or []:
            if parent not in positions:
                continue
            px, py = positions[parent]
            cx_, cy_ = positions[task["id"]]
            x1, y1 = px + NODE_W, py + NODE_H / 2
            x2, y2 = cx_, cy_ + NODE_H / 2
            bow = (x2 - x1) * 0.45
            parts.append(
                f'<path class="tm-edge" d="M {x1:.1f} {y1:.1f} C {x1+bow:.1f} {y1:.1f}, '
                f'{x2-bow:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}" '
                f'fill="none" stroke="{LINE_STRONG}" stroke-width="1.6" '
                f'marker-end="url(#tm-arrow)"/>'
            )

    for task in tasks:
        x, y = positions[task["id"]]
        parts.append(_task_node(task, x, y))

    # -- the rule that collects every task --------------------------------
    label = "all {n} tasks signed off".format(n=len(tasks))
    label_w = len(label) * 5.6 + 26
    parts.append(
        f'<line x1="{MARGIN}" y1="{rule_y:.0f}" x2="{center_x - label_w/2:.0f}" '
        f'y2="{rule_y:.0f}" stroke="{LINE}" stroke-width="1.4"/>'
    )
    parts.append(
        f'<line x1="{center_x + label_w/2:.0f}" y1="{rule_y:.0f}" x2="{width - MARGIN:.0f}" '
        f'y2="{rule_y:.0f}" stroke="{LINE}" stroke-width="1.4"/>'
    )
    parts.append(
        f'<text class="tm-rule-label" x="{center_x:.0f}" y="{rule_y + 4:.0f}" '
        f'text-anchor="middle" font-size="11.5" fill="{MUTED}">{html.escape(label)}</text>'
    )

    # -- the gate ---------------------------------------------------------
    parts.append(
        _gate_node(
            supervised_x,
            gate_y,
            SUPERVISED_W,
            "Supervised cut",
            "at Nolop, with a TA",
            href="unit-laser-ready.html",
            accent=True,
        )
    )
    parts.append(
        f'<path d="M {supervised_x + SUPERVISED_W + 6:.0f} {gate_y + GATE_H/2:.0f} '
        f'L {qualification_x - 6:.0f} {gate_y + GATE_H/2:.0f}" fill="none" '
        f'stroke="{BLUE}" stroke-width="1.6" marker-end="url(#tm-arrow-blue)"/>'
    )
    parts.append(
        _gate_node(
            qualification_x,
            gate_y,
            QUALIFICATION_W,
            str((unit or {}).get("title", "The qualification")),
            "the qualification",
            href="unit-laser-ready.html" if unit else None,
            solid=True,
        )
    )

    parts.append("</svg>")
    return "\n".join(parts)


def _defs() -> str:
    return f"""\
  <defs>
    <marker id="tm-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"
            markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="{LINE_STRONG}"/>
    </marker>
    <marker id="tm-arrow-blue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"
            markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 9 5 L 0 9 z" fill="{BLUE}"/>
    </marker>
  </defs>"""


def _task_node(task, x, y) -> str:
    """One task: number badge, wrapped title, and its video length."""
    title_lines = wrap_title(task.get("title", task["id"]))
    inner = [
        f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="12" '
        f'fill="{PAPER}" stroke="{LINE}" stroke-width="1.2"/>',
        f'<circle cx="{x + 21}" cy="{y + 21}" r="{BADGE_R}" fill="{BLUE}"/>',
        f'<text x="{x + 21}" y="{y + 25}" text-anchor="middle" font-size="12" '
        f'font-weight="700" fill="{PAPER}">{html.escape(str(task.get("order", "")))}</text>',
    ]
    text_x = x + 40
    for i, line in enumerate(title_lines[:2]):
        inner.append(
            f'<text x="{text_x}" y="{y + 26 + i * TITLE_LINE:.0f}" font-size="{TITLE_SIZE}" '
            f'fill="{INK}">{html.escape(str(line))}</text>'
        )
    if task.get("time"):
        inner.append(
            f'<text x="{x + NODE_W - TEXT_PAD}" y="{y + NODE_H - 11}" text-anchor="end" '
            f'font-size="{META_SIZE}" fill="{MUTED}">{html.escape(str(task["time"]))} video</text>'
        )
    href = f'{task["id"]}.html'
    return (
        f'<a class="tm-node" href="{href}" aria-label="{html.escape(str(task.get("title","")))}">'
        + "".join(inner)
        + "</a>"
    )


def _gate_node(x, y, w, title, sub, href=None, accent=False, solid=False) -> str:
    if solid:
        body = (
            f'<rect x="{x}" y="{y}" width="{w}" height="{GATE_H}" rx="14" fill="{BLUE}"/>'
            f'<text x="{x + w/2:.0f}" y="{y + 25}" text-anchor="middle" font-size="14" '
            f'font-weight="700" fill="{PAPER}">{html.escape(str(title))}</text>'
            f'<text x="{x + w/2:.0f}" y="{y + 43}" text-anchor="middle" font-size="10.5" '
            f'fill="#dceafa">{html.escape(str(sub))}</text>'
        )
    else:
        dash = ' stroke-dasharray="5 4"' if accent else ""
        stroke = BLUE if accent else LINE
        body = (
            f'<rect x="{x}" y="{y}" width="{w}" height="{GATE_H}" rx="14" fill="{PAPER}" '
            f'stroke="{stroke}" stroke-width="1.4"{dash}/>'
            f'<text x="{x + w/2:.0f}" y="{y + 25}" text-anchor="middle" font-size="13.5" '
            f'font-weight="600" fill="{INK}">{html.escape(str(title))}</text>'
            f'<text x="{x + w/2:.0f}" y="{y + 43}" text-anchor="middle" font-size="10.5" '
            f'fill="{MUTED}">{html.escape(str(sub))}</text>'
        )
    if href:
        return f'<a class="tm-node" href="{href}">{body}</a>'
    return body
