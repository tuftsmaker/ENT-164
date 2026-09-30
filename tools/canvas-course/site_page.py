#!/usr/bin/env python3
"""Convert a class-site page into the HTML Canvas stores.

Shared by `syllabus.py` and `pages.py`. Canvas strips `<style>` blocks and keeps
a fixed set of inline properties, so the output is inline styles and basic tags;
images stay hotlinked to the class site (Canvas keeps external `<img>`), and the
caller supplies `map_href`, which rewrites every link — Canvas pages, the
syllabus tab, or the absolute site.

The site's components are known, so they are mapped rather than flattened, and
they keep the site's light-theme look: a hero card, chips for pills, buttons
for `.btn`s, bordered cards and callouts, ruled section headings, striped
tables. Anything unmapped degrades to its text. Canvas's sanitizer keeps
display, margin, border, colour and size but drops `letter-spacing` and
`text-transform`, so the caps the site gets from CSS are baked into the text.
"""
from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser

SITE = "https://tuftsmaker.github.io/ENT-164/"

DROP = {"svg", "script", "style", "nav", "aside", "footer", "input", "label", "button"}
VOID = {"img", "br", "hr", "input", "meta", "link"}
SKIP = {"grade-bar", "step-num"}

# ---------------------------------------------------------------- the look

WRAP = ("max-width: 980px; color: #17203a; font-size: 16px; line-height: 1.62; "
        "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;")
HERO = ("background: #ffffff; border: 1px solid #e6eaf1; border-radius: 18px; "
        "padding: 26px 28px; margin: 0 0 26px;")
KICKER = "margin: 0 0 12px; color: #1F6FD0; font-size: 12px;"
LEAD = "margin: 0 0 14px; color: #3f4a5a; font-size: 17.5px; max-width: 72ch;"
NOTE = "margin: 0; color: #5f6b7a; font-size: 13.5px;"
H1 = "margin: 0 0 12px; color: #0d1526; font-size: 33px; line-height: 1.12;"
H2 = "margin: 30px 0 8px; color: #0d1526; font-size: 27px; line-height: 1.2;"
RULE = ("width: 48px; height: 4px; border-radius: 2px; margin: 0 0 14px; "
        "background-image: linear-gradient(90deg, #2f7cc9, #7fb6ea);")
SEC_NUM = "display: block; margin: 0 0 3px; color: #1F6FD0; font-size: 12px;"
H3 = "margin: 24px 0 6px; color: #0d1526; font-size: 19px; line-height: 1.3;"
H4 = "margin: 18px 0 4px; color: #0d1526; font-size: 16.5px; line-height: 1.35;"
P = "margin: 0 0 12px;"
UL = "margin: 10px 0; padding-left: 22px;"
HR = "border: 0; border-top: 1px solid #e6eaf1; margin: 26px 0;"
PILL = ("display: inline-block; background: #f2f7fd; border: 1px solid #d5dce7; "
        "border-radius: 999px; padding: 3px 12px; margin: 0 6px 6px 0; font-size: 13.5px; color: #3f4a5a;")
CHIP = ("display: inline-block; background: #f7f9fc; border: 1px solid #e6eaf1; "
        "border-radius: 999px; padding: 4px 12px; margin: 0 8px 8px 0; font-size: 13.5px; color: #3f4a5a;")
BTN = ("display: inline-block; background-color: #2f7cc9; background-image: linear-gradient(145deg, #4c9ae6, #2f7cc9); "
       "color: #ffffff; border-radius: 999px; padding: 11px 22px; font-size: 15px; text-decoration: none; "
       "margin: 0 10px 10px 0;")
BTN_GHOST = ("display: inline-block; background: #ffffff; border: 1px solid #d5dce7; color: #1F6FD0; "
             "border-radius: 999px; padding: 10px 20px; font-size: 15px; text-decoration: none; margin: 0 10px 10px 0;")
CARD = ("flex: 1 1 300px; background: #ffffff; border: 1px solid #e6eaf1; border-radius: 14px; "
        "padding: 18px 20px; margin: 0;")
PHASE = ("flex: 1 1 240px; background: #f7f9fc; border: 1px solid #e6eaf1; "
         "border-radius: 12px; padding: 14px 16px; margin: 0;")
CALLOUT = ("background: #f7f9fc; border-left: 4px solid #2f7cc9; border-radius: 0 10px 10px 0; "
           "padding: 14px 18px; margin: 16px 0;")
TABLE = "border-collapse: collapse; width: 100%; margin: 14px 0;"
TD = "padding: 8px 12px; border-bottom: 1px solid #e6eaf1; vertical-align: top;"
TH = ("text-align: left; padding: 8px 12px; border-bottom: 2px solid #d5dce7; "
      "color: #0d1526; background: #f7f9fc;")
FIGURE = "margin: 18px 0;"
CAPTION = "margin: 6px 0 0; color: #5f6b7a; font-size: 13.5px;"
COURSE_LINE = "margin: 0 0 6px; color: #5f6b7a; font-size: 12.5px;"
WEEK_LINE = "margin: 20px 0 4px; color: #1F6FD0; font-size: 13px;"
STEP_CARD = ("background: #ffffff; border: 1px solid #e6eaf1; border-radius: 14px; "
             "padding: 20px 22px; margin: 18px 0;")
STEP_NUM = "margin: 0 0 4px; color: #2f7cc9; font-size: 12px;"
STEP_TITLE = "margin: 0 0 10px; color: #0d1526; font-size: 21px; line-height: 1.25;"
STEP_CHIP = ("flex: 0 1 auto; background: #f7f9fc; border: 1px solid #e6eaf1; "
             "border-radius: 10px; padding: 8px 12px; margin: 0;")
STEP_CHIP_ACCENT = ("flex: 0 1 auto; background: #f2f7fd; border: 1px solid #d5dce7; "
                    "border-radius: 10px; padding: 8px 12px; margin: 0;")
KEYCAP = ("display: inline-block; border: 1px solid #d5dce7; border-radius: 6px; "
          "padding: 0 6px; background: #f7f9fc; font-size: 13px;")
UI = ("display: inline-block; border: 1px solid #d5dce7; border-radius: 6px; "
      "padding: 1px 7px; background: #ffffff; font-size: 13.5px;")
ACCENT = "color: #2f7cc9;"
PASTE = ("background: #f2f7fd; border: 2px solid #3E8EDE; border-radius: 10px; "
         "padding: 14px 16px; margin: 12px 0;")
PASTE_LABEL = "margin: 0 0 6px; color: #1F6FD0; font-size: 12px;"
PASTE_SAY = ("margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; "
             "font-size: 16.5px; line-height: 1.5; color: #0d1526;")
URL_MARK = "background: #fff3cd; border-bottom: 2px solid #e0a800;"

# image caps — full-width images dwarf a Canvas page
IMG_MAX = 620      # a screenshot or hero image
SHOT_MAX = 340     # a gallery shot, tiled on the site
PHOTO_MAX = 220    # one photo in a strip of four
AVATAR_MAX = 160   # a portrait
AVATAR_SMALL_MAX = 96


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": None, "attrs": {}, "kids": []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "kids": []}
        self.stack[-1]["kids"].append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1]["kids"].append({"tag": tag, "attrs": dict(attrs), "kids": []})

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        text = re.sub(r"\s+", " ", data)
        if text.strip():
            self.stack[-1]["kids"].append({"tag": None, "text": text})


def parse(fragment: str) -> dict:
    tree = Tree()
    tree.feed(fragment)
    return tree.root


def text_of(node: dict) -> str:
    if node.get("tag") is None:
        return node.get("text", "")
    return "".join(text_of(kid) for kid in node["kids"])


def class_of(node: dict) -> str:
    return node.get("attrs", {}).get("class", "")


def find_tag(node: dict, name: str):
    if node.get("tag") == name:
        return node
    for kid in node.get("kids", []):
        found = find_tag(kid, name)
        if found is not None:
            return found
    return None


def find_class(node: dict, name: str):
    if name in class_of(node).split():
        return node
    for kid in node.get("kids", []):
        found = find_class(kid, name)
        if found is not None:
            return found
    return None


def normalized(html: str) -> str:
    """The body's text: tags stripped, entities unescaped — Canvas stores `&`
    as `&amp;`, so comparisons have to read through that."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def annotate_internal_links(html: str) -> str:
    """Mark course-internal links the way Canvas's rich-content editor does.

    A link to Canvas's own content carries `data-api-endpoint` and
    `data-api-returntype`, and the editor treats it as an internal link. Canvas
    absolutizes root-relative hrefs on save, so `href` is written absolute;
    the attributes are what mark it as internal. Links with no origin (site
    links) are left alone.
    """
    def replace(match):
        if match.string[match.end():match.end() + 13].startswith(" data-api-"):
            return match.group(0)  # already annotated
        href = match.group(1)
        for pattern, rettype, folder in ((CANVAS_PAGE, "Page", "pages"),
                                         (CANVAS_ASSIGNMENT_LINK, "Assignment", "assignments")):
            found = pattern.match(href)
            if found and found.group("origin"):
                return (f'<a href="{href}" data-api-endpoint="{found.group("origin")}/api/v1/courses/'
                        f'{found.group("course")}/{folder}/{found.group("rest")}" '
                        f'data-api-returntype="{rettype}"')
        return match.group(0)

    return ANCHOR_HREF.sub(replace, html)


def img_html(node: dict, map_href, cap: int | None = None, bare: bool = False) -> str:
    """An `<img>` with a sane width cap — the site tiles gallery shots and
    crops portraits, so the cap follows the component. `bare` drops the frame
    for marks and logos that carry no photographic content."""
    src = node.get("attrs", {}).get("src", "")
    alt = node.get("attrs", {}).get("alt", "")
    if not src:
        return ""
    cls = class_of(node).split()
    width = node.get("attrs", {}).get("width", "")
    if cap is None:
        if "avatar-sm" in cls:
            cap = AVATAR_SMALL_MAX
        elif "avatar" in cls:
            cap = AVATAR_MAX
        elif width.isdigit() and int(width) <= 2 * AVATAR_MAX:
            cap = int(width)
        else:
            cap = IMG_MAX
    frame = "" if bare else "border-radius:10px;border:1px solid #e6eaf1;"
    return (f'<img src="{map_href(src)}" alt="{alt}" style="display:block;height:auto;'
            f'max-width:{cap}px;{frame}">')


def _join(node: dict, map_href, sep=" ") -> str:
    parts = []
    for kid in node["kids"]:
        piece = render(kid, map_href).strip()
        if piece:
            parts.append(piece)
    return sep.join(parts)


def _anchor(node: dict, map_href, inner: str) -> str:
    cls = class_of(node).split()
    href = node.get("attrs", {}).get("href", "")
    mapped = map_href(href) if href else ""
    if "btn-ghost" in cls:
        style = BTN_GHOST
    elif "btn" in cls:
        style = BTN
    elif "chip" in cls:
        style = CHIP
    else:
        style = None
    text = inner if style is None else f"<b>{inner}</b>"
    if not mapped:
        # A jump link to a section on the site has no target in Canvas; keep
        # its look, drop the link.
        return f'<span style="{style}">{text}</span>' if style else text
    attribute = f' style="{style}"' if style else ""
    return f'<a href="{mapped}"{attribute}>{text}</a>'


def render(node: dict, map_href) -> str:
    tag = node.get("tag")
    if tag is None:
        if "text" in node:
            return node["text"]
        return "".join(render(kid, map_href) for kid in node["kids"])
    if tag in DROP or any(skip in class_of(node).split() for skip in SKIP):
        return ""
    cls = class_of(node).split()
    inner = "".join(render(kid, map_href) for kid in node["kids"])

    if tag == "a":
        return _anchor(node, map_href, inner)

    if tag == "img":
        return img_html(node, map_href)

    if tag == "figure":
        cap = SHOT_MAX if "shot" in cls else None
        kids = []
        for kid in node["kids"]:
            if kid.get("tag") == "img":
                kids.append(img_html(kid, map_href, cap))
            else:
                kids.append(render(kid, map_href))
        return f'<div style="{FIGURE}">' + "".join(kids) + "</div>\n"
    if tag == "figcaption":
        inner = re.sub(r"</b>(?=\S)", "</b> — ", inner)  # "Lead-in" + "text" glue
        return f'<p style="{CAPTION}"><i>{inner}</i></p>'

    if tag == "header" and "hero" in cls:
        return hero_block(node, map_href)

    if tag == "span" and "pill" in cls:
        return f'<span style="{PILL}">{inner}</span>'
    if tag == "span" and "chip" in cls:
        return f'<span style="{CHIP}">{inner}</span>'

    if tag == "div" and "pills" in cls:
        return f'<p style="margin:0 0 16px;">{_join(node, map_href)}</p>\n'
    if tag == "div" and "chips" in cls:
        return f'<p style="margin:0 0 10px;">{_join(node, map_href)}</p>\n'
    if tag == "div" and "pill" in cls:
        return f'<span style="{PILL}">{inner}</span>'
    if tag == "div" and "mark" in cls:
        kids = [img_html(kid, map_href, cap=96, bare=True) if kid.get("tag") == "img"
                else render(kid, map_href) for kid in node["kids"]]
        return "".join(kids) + "\n"
    if tag == "div" and "week-side" in cls:
        num = find_class(node, "week-num")
        date = find_class(node, "week-date")
        n = re.sub(r"\s+", " ", text_of(num)).strip() if num is not None else ""
        d = re.sub(r"\s+", " ", text_of(date)).strip() if date is not None else ""
        line = f"<b>{n}</b>" + (f" &middot; {d}" if d else "")
        return f'<p style="{WEEK_LINE}">{line}</p>\n'
    if tag == "div" and "course" in cls:
        return f'<p style="{COURSE_LINE}"><b>{inner}</b></p>\n'
    if tag == "div" and "kicker" in cls:
        return f'<p style="{KICKER}"><b>{text_of(node).strip().upper()}</b></p>\n'
    if tag == "div" and "subtitle" in cls:
        return f'<p style="{LEAD}">{inner}</p>\n'
    if tag == "div" and "steps" in cls:
        return f'<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:14px 0;">{inner}</div>\n'
    if tag == "div" and "arrow" in cls:
        return '<span style="color:#9aa7b8;font-size:18px;">&rarr;</span>\n'
    if tag == "div" and "cards" in cls:
        return f'<div style="display:flex;flex-wrap:wrap;gap:14px;margin:16px 0;align-items:stretch;">{inner}</div>\n'
    if tag == "div" and "phases" in cls:
        return f'<div style="display:flex;flex-wrap:wrap;gap:14px;margin:16px 0;align-items:stretch;">{inner}</div>\n'
    if tag == "div" and "phase" in cls:
        return f'<div style="{PHASE}">{inner}</div>\n'
    if tag == "div" and "gallery" in cls:
        return f'<div style="display:flex;flex-wrap:wrap;gap:18px;margin:16px 0;align-items:flex-start;">{inner}</div>\n'
    if tag == "div" and "photo-strip" in cls:
        # Tiled photos: a row of equal-width figures, not one giant image each.
        kids = []
        for kid in node["kids"]:
            if kid.get("tag") == "figure":
                parts = [img_html(k, map_href, cap=PHOTO_MAX) if k.get("tag") == "img"
                         else render(k, map_href) for k in kid["kids"]]
                kids.append('<div style="flex:1 1 200px;margin:0;">' + "".join(parts) + "</div>")
            else:
                kids.append(render(kid, map_href))
        return ('<div style="display:flex;flex-wrap:wrap;gap:16px;margin:22px 0 0;'
                'align-items:flex-start;">' + "".join(kids) + "</div>\n")
    if tag == "div" and "cta-row" in cls:
        return f'<p style="margin:0 0 6px;">{_join(node, map_href)}</p>\n'
    if tag == "div" and "step" in cls:
        header = find_class(node, "step-header")
        if header is not None:
            # A guide step: a card with the number badge and heading.
            num = find_class(header, "step-num")
            digits = re.sub(r"\D", "", text_of(num)) if num is not None else ""
            head = next((k for k in header["kids"] if k.get("tag") in ("h2", "h3", "h4")), None)
            title = re.sub(r"\s+", " ", text_of(head)).strip() if head is not None else ""
            rest = "".join(render(kid, map_href) for kid in node["kids"] if kid is not header)
            badge = f'<p style="{STEP_NUM}"><b>STEP {digits}</b></p>' if digits else ""
            return (f'<div style="{STEP_CARD}">{badge}<h3 style="{STEP_TITLE}">{title}</h3>\n'
                    f"{rest}</div>\n")
        # A class page's process step: a title and its when, as a chip.
        bold = next((k for k in node["kids"] if k.get("tag") in ("b", "strong")), None)
        when = next((k for k in node["kids"] if k.get("tag") == "span"), None)
        title = re.sub(r"\s+", " ", text_of(bold)).strip() if bold is not None else ""
        meta = re.sub(r"\s+", " ", text_of(when)).strip() if when is not None else ""
        style = STEP_CHIP_ACCENT if "accent" in cls else STEP_CHIP
        if not title and not meta:
            return f'<div style="{style}">{inner}</div>\n'
        return (f'<div style="{style}"><b>{title}</b>'
                + (f'<br><span style="color:#5f6b7a;font-size:13.5px;">{meta}</span>' if meta else "")
                + "</div>\n")
    if tag == "div" and "cyc" in cls:
        head = next((k for k in node["kids"] if k.get("tag") == "h3"), None)
        body = next((k for k in node["kids"] if k.get("tag") == "p"), None)
        return (f"<p style=\"{P}\"><b>{text_of(head).strip()}</b>"
                f"{' — ' + text_of(body).strip() if body is not None else ''}</p>\n")
    if tag == "div" and "divider" in cls:
        return f'<hr style="{HR}">\n'
    if tag == "div" and "paste" in cls:
        return f'<div style="{PASTE}">{inner}</div>\n'
    if tag == "div" and "label" in cls:
        return f'<p style="{PASTE_LABEL}"><b>{text_of(node).strip().upper()}</b></p>\n'
    if tag == "div" and "say" in cls:
        return f'<p style="{PASTE_SAY}">{inner}</p>\n'
    if tag == "div" and "footer" in cls:
        return f'<p style="{NOTE}"><i>{_join(node, map_href)}</i></p>\n'

    if tag in ("h1",):
        return f'<h1 style="{H1}">{inner}</h1>\n'
    if tag == "h2":
        return f'<h2 style="{H2}">{inner}</h2>\n<div style="{RULE}"></div>\n'
    if tag == "h3":
        return f'<h3 style="{H3}">{inner}</h3>\n'
    if tag == "h4" or tag == "h5":
        return f'<h4 style="{H4}">{inner}</h4>\n'
    if tag == "p" and "kicker" in cls:
        return f'<p style="{KICKER}"><b>{text_of(node).strip().upper()}</b></p>\n'
    if tag == "p" and "lede" in cls:
        return f'<p style="{LEAD}">{inner}</p>\n'
    if tag == "p":
        return f'<p style="{P}">{inner}</p>\n'
    if tag in ("ul", "ol"):
        if "grade-list" in cls:
            return grade_table(node) + "\n"
        return f'<{tag} style="{UL}">{inner}</{tag}>\n'
    if tag == "li":
        return f"<li>{inner}</li>\n"
    if tag == "hr":
        return f'<hr style="{HR}">\n'
    if tag == "br":
        return "<br>\n"
    if tag in ("b", "strong"):
        return f"<b>{inner}</b>"
    if tag in ("i", "em"):
        return f"<i>{inner}</i>"
    if tag == "code":
        return f"<code>{inner}</code>"
    if tag == "table":
        return f'<table style="{TABLE}">{inner}</table>\n'
    if tag == "td":
        return f'<td style="{TD}">{inner}</td>'
    if tag == "th":
        return f'<th style="{TH}">{inner}</th>'
    if tag in ("tr", "tbody"):
        return f"<{tag}>{inner}</{tag}>"
    if tag == "blockquote":
        return f'<div style="{CALLOUT}">{inner}</div>\n'
    if tag == "cite":
        return f'<span style="display:block;margin-top:6px;color:#5f6b7a;">{inner}</span>'
    if tag == "div":
        if "callout" in cls:
            inner = re.sub(r"</b>(?=\S)", "</b> ", inner)
            return f'<div style="{CALLOUT}">{inner}</div>\n'
        if "card" in cls:
            return f'<div style="{CARD}">{inner}</div>\n'
        if "hero" in cls:
            return f'<div style="{HERO}">{inner}</div>\n'
        return inner + "\n"  # a wrapper: keep its children's text runs apart
    if tag == "span" and any(c in cls for c in ("num", "qn", "cn", "step-num")):
        if text_of(node).strip().isdigit():
            return ""  # decorative numbering, not content
    if tag == "span" and "sec-num" in cls:
        return f'<span style="{SEC_NUM}">{inner}</span>'
    if tag == "span" and "url" in cls:
        return f'<span style="{URL_MARK}"><b>{inner}</b></span>'
    if tag == "span" and "accent" in cls:
        return f'<span style="{ACCENT}">{inner}</span>'
    if tag == "span" and "keycap" in cls:
        return f'<span style="{KEYCAP}">{inner}</span>'
    if tag == "span" and "ui" in cls:
        return f'<span style="{UI}">{inner}</span>'
    if tag in ("span", "small"):
        return inner
    return inner


def grade_table(node: dict) -> str:
    """`ul.grade-list` → a two-column table of label and weight."""
    rows = []
    for kid in node["kids"]:
        if kid.get("tag") != "li":
            continue
        label = next((k for k in kid["kids"] if "grade-label" in class_of(k).split()), None)
        weight = next((k for k in kid["kids"] if "grade-weight" in class_of(k).split()), None)
        if label is not None and weight is not None:
            rows.append(
                f'<tr><td style="{TD}">' + text_of(label).strip()
                + f'</td><td style="{TD}"><b>' + text_of(weight).strip()
                + "</b></td></tr>"
            )
    return f'<table style="{TABLE}">' + "".join(rows) + "</table>"


def hero_block(hero: dict, map_href) -> str:
    """A class page's `<header class="hero">` as a card: kicker, accent rule,
    lead, chips, buttons and any hero figure. The heading is left out — Canvas
    shows the page title above the body, and a Page module item carries the same
    title, so repeating it here would read twice."""
    kicker = find_class(hero, "kicker")
    lead = find_class(hero, "lead")
    pills = find_class(hero, "pills")
    note = find_class(hero, "note")
    cta = find_class(hero, "cta-row")
    lines = []
    portrait = next((k for k in _walk(hero)
                     if k.get("tag") == "img" and "portrait" in class_of(k).split()), None)
    if portrait is not None:
        src = map_href(portrait.get("attrs", {}).get("src", ""))
        alt = portrait.get("attrs", {}).get("alt", "")
        lines.append(f'<p style="margin:0 0 16px;"><img src="{src}" alt="{alt}" '
                     'style="display:block;height:auto;max-width:180px;'
                     'border-radius:50%;border:1px solid #e6eaf1;"></p>')
    if kicker is not None:
        lines.append(f'<p style="{KICKER}"><b>{text_of(kicker).strip().upper()}</b></p>')
        lines.append(f'<div style="{RULE}"></div>')
    if lead is not None:
        lines.append(f'<p style="{LEAD}">{text_of(lead).strip()}</p>')
    if pills is not None:
        lines.append(f'<p style="margin:0 0 18px;">{_join(pills, map_href)}</p>')
    if cta is not None:
        # A jump link has no target on a Canvas page; drop it, keep the rest.
        buttons = {"tag": "div", "attrs": {}, "kids": [
            kid for kid in cta["kids"]
            if not (kid.get("tag") == "a" and kid.get("attrs", {}).get("href", "").startswith("#"))]}
        lines.append(f'<p style="margin:0 0 6px;">{_join(buttons, map_href)}</p>')
    if note is not None:
        lines.append(f'<p style="{NOTE}"><i>{text_of(note).strip()}</i></p>')
    for figure in [k for k in _walk(hero) if k.get("tag") == "figure"]:
        lines.append(render(figure, map_href).strip())
    return f'<div style="{HERO}">\n' + "\n".join(lines) + "\n</div>\n"


def _walk(node: dict):
    yield node
    for kid in node.get("kids", []):
        yield from _walk(kid)

CANVAS_PAGE = re.compile(r'^(?P<origin>https?://[^/]+)?/courses/(?P<course>\d+)/pages/(?P<rest>[^"#?]+)$')
CANVAS_ASSIGNMENT_LINK = re.compile(
    r'^(?P<origin>https?://[^/]+)?/courses/(?P<course>\d+)/assignments/(?P<rest>\d+)$')
ANCHOR_HREF = re.compile(r'<a href="([^"]*)"')
