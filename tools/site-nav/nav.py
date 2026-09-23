"""The site's navigation, defined once.

Two components, used by every published page:

* `main_nav()`  — the sticky bar. The same site links everywhere, plus the one
  call to action that is allowed to differ per page.
* `sub_nav()`   — a page's own sections, shown as a bar under the main nav on
  pages that have no sidebar. Class and syllabus pages already carry a sidebar
  "On this page" block, so they do not get a second copy.

`tools/site-nav/apply.py` rewrites the hand-authored pages from this;
`tools/skill-tasks/catalog/build.py` imports it for the generated `tasks/`
pages. One definition, so the two can never drift apart.
"""

from __future__ import annotations

# ---------------------------------------------------------------- main nav

# The site links. Order matters: it is the reading order of the site, not the
# order the pages were built in.
MAIN_LINKS = [
    ("Tasks", "tasks/"),
    ("Workshops", "syllabus/#schedule"),
    ("Syllabus", "syllabus/"),
    ("About", "about/"),
]

MARK_SVG = """\
<span class="mark-sm" aria-hidden="true">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 12-9.373 9.373a1 1 0 0 1-3.001-3L12 9" />
          <path d="m18 15 4-4" />
          <path d="m21.5 11.5-1.914-1.914A2 2 0 0 1 19 8.172v-.344a2 2 0 0 0-.586-1.414l-1.657-1.657A6 6 0 0 0 12.516 3H9l1.243 1.243A6 6 0 0 1 12 8.485V10l2 2h1.172a2 2 0 0 1 1.414.586L18.5 14.5" />
        </svg>
      </span>"""


def root_prefix(depth: int) -> str:
    """How a page `depth` folders down reaches the site root."""
    return "../" * depth if depth else "./"


def main_nav(depth: int, cta_href: str, cta_label: str, active: str | None = None) -> str:
    """The main nav.

    `cta_href` is relative to the page (not to the root) — it is the page's own
    action, e.g. a class page's "Download slides". `active` names the site
    section the page belongs to, so the current one can be marked.

    On a wide screen the links are a plain flex row. On a narrow one they
    collapse behind a "Menu" button, driven by a checkbox and the `~`
    combinator — no JavaScript, and critically, no element whose *state* can
    hide the links on a wide screen. (A previous attempt used `<details>`;
    a closed `<details>` hides its children whatever CSS says about its
    `display`, which rendered the desktop nav empty.)
    """
    root = root_prefix(depth)
    items = []
    for label, href in MAIN_LINKS:
        if active and label.lower().replace(" ", "-") == active:
            items.append(f'<a href="{root}{href}" aria-current="page">{label}</a>')
        else:
            items.append(f'<a href="{root}{href}">{label}</a>')
    items.append(f'<a class="nav-cta" href="{cta_href}">{cta_label}</a>')
    body = "\n        ".join(items)
    return f"""<nav class="nav">
  <div class="wrap nav-inner">
    <a class="brand" href="{root}">
      {MARK_SVG}
      <span>ENT-164 <small>&middot; Intro to Making</small></span>
    </a>
    <input type="checkbox" id="nav-toggle" class="nav-toggle">
    <label for="nav-toggle" class="nav-toggle-label">
      <span class="nav-toggle-text">Menu</span>
      <span class="nav-toggle-bars" aria-hidden="true"></span>
    </label>
    <div class="nav-links">
        {body}
    </div>
  </div>
</nav>"""


def site_nav(depth: int, cta_href: str, cta_label: str) -> str:
    """The nav used on guide pages, which get printed onto paper: same links,
    different component, hidden by `@media print` in guide.css.

    The hammer mark is drawn from the laser-cutting shots, which every guide
    page can reach, so the path is absolute from the root.
    """
    root = root_prefix(depth)
    items = "\n    ".join(f'<a href="{root}{href}">{label}</a>' for label, href in MAIN_LINKS)
    return f"""<nav class="site-nav">
  <a class="brand" href="{root}">
    <span class="mark"><img src="{root}laser-cutting/shots/class-hammer.svg" alt=""></span>
    <span>ENT-164 <small>&middot; Intro to Making</small></span>
  </a>
  <div class="links">
    {items}
    <a class="pill-link" href="{cta_href}">{cta_label}</a>
  </div>
</nav>"""


# ---------------------------------------------------------------- sub nav


def sub_nav(sections: list, current: str | None = None) -> str:
    """A page's sections as a bar. `sections` is [(id, label), ...]."""
    if not sections:
        return ""
    links = "\n      ".join(
        f'<a href="#{sid}">{label}</a>' for sid, label in sections
    )
    return f"""<nav class="subnav" aria-label="On this page">
  <div class="wrap subnav-inner">
      {links}
  </div>
</nav>"""


# ---------------------------------------------------------------- page specs

# hand-authored page -> (cta href, cta label, site section)
PAGES = {
    "index.html": ("syllabus/", "Start here &rarr;", None),
    "syllabus/index.html": (
        "ENT164%20FA26%20Introduction%20to%20Making%20Syllabus.pdf", "Download PDF", "syllabus",
    ),
    "about/index.html": ("../opencode-deepseek-guide-mac/guide.html", "Start with opencode &rarr;", "about"),
    "onshape-tips/index.html": ("../laser-cutting/", "Laser cutting guide &rarr;", None),
    "laser-cutting/index.html": ("guide.html", "Read the guide &rarr;", None),
    "classes/class-01/index.html": ("ENT-164-Class-1-Introductions.pdf", "Download slides", None),
    "classes/class-02/index.html": ("ENT-164-Class-2-Hand-Making-and-Robot-Challenge.pdf", "Download slides", None),
    "classes/class-03/index.html": ("ENT-164-Class-3-Laser-Cutting.pdf", "Download slides", None),
    "classes/class-04/index.html": ("ENT-164-Class-4-3D-Printing.pdf", "Download slides", None),
    "classes/class-05/index.html": ("ENT-164-Class-5-Electronics.pdf", "Download slides", None),
    "classes/class-06/index.html": ("ENT-164-Class-6-Connectivity-with-AI.pdf", "Download slides", None),
    "classes/class-09/index.html": ("ENT-164-Class-9-Final-Project-Kickoff.pdf", "Download slides", None),
    "classes/class-11/index.html": ("ENT-164-Class-11-Intelligent-Devices-with-AI.pdf", "Download slides", None),
}

# guide page -> (cta href, cta label)
GUIDE_PAGES = {
    "laser-cutting/guide.html": ("../classes/class-03/", "Class 3"),
    "add-class-tools/guide.html": ("../syllabus/", "Syllabus"),
    "opencode-deepseek-guide-mac/guide.html": ("../syllabus/", "Syllabus"),
    "opencode-deepseek-guide-win/guide.html": ("../syllabus/", "Syllabus"),
}

# Pages that need a section bar because they have no sidebar. Pages with a
# sidebar (class-*, syllabus) are deliberately absent — a second copy of the
# same links is noise. The generated tasks pages are handled by their builder.
SUBNav_PAGES = {
    "index.html": [
        ("making", "Hands-on"),
        ("syllabus", "The semester"),
        ("guides", "Walkthroughs"),
        ("classes", "Workshops"),
        ("before", "What you'll need"),
        ("instructor", "Instructor"),
    ],
    "about/index.html": [
        ("story", "About"),
        ("highlights", "Highlights"),
        ("timeline", "The path here"),
        ("background", "Background"),
    ],
    "onshape-tips/index.html": [
        ("videos", "The tips"),
        ("where", "Where these fit"),
    ],
}
