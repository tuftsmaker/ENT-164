#!/usr/bin/env python3
"""Populate a Canvas course from the class website.

The site is the source of truth and Canvas gets **links, never copies** (the
rule in AGENTS.md): every module item is an ExternalUrl pointing at the Pages
URL, so pushing to `main` is still the only sync step and no deck or video is
duplicated into Canvas.

Writes the structure only - modules and their items. It does not touch grading,
rubrics or enrolments, and it never deletes anything.

    python3 tools/canvas-course/populate.py --dry-run     # show the plan
    python3 tools/canvas-course/populate.py               # the prototype course
    python3 tools/canvas-course/populate.py --course 76330

Idempotent: modules are found by name and items by title, so re-running after a
class is added only creates what is missing.
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'skill-tasks', 'canvas'))
from canvas_client import Client, load_config  # noqa: E402

SITE = 'https://tuftsmaker.github.io/ENT-164'
PROTOTYPE_COURSE = '71548'          # "Intro to Making Prototype"

TIP_ORDER = ['workspace-overview', 'basic-rectangle', 'updating-dimensions',
             'circle-to-cut-a-hole', 'circle-in-the-center', 'circle-on-a-corner',
             'mirroring-entities', 'trim-tool', 'laser-cut-joints']


def classes():
    """Every class page, in week order, with its deck PDF."""
    out = []
    base = os.path.join(ROOT, 'classes')
    for name in sorted(os.listdir(base)):
        page = os.path.join(base, name, 'index.html')
        if not os.path.exists(page):
            continue
        h = open(page).read()
        kicker = re.search(r'kicker[^>]*>(.*?)<', h, re.S)
        title = re.search(r'<title>ENT-164 · Class \d+ — ([^<]+)</title>', h)
        deck = [p for p in re.findall(r'href="([^"]+\.pdf)"', h)
                if re.search(r'ENT-164-Class-\d', p)]
        week = re.search(r'Week\s+(\d+)', kicker.group(1) if kicker else '')
        out.append({
            'slug': name,
            'week': int(week.group(1)) if week else 99,
            'title': (title.group(1).strip() if title else name),
            'deck': deck[0] if deck else None,
        })
    return sorted(out, key=lambda c: c['week'])


def guides():
    """The walkthrough cards on the hub, in the order they appear."""
    h = open(os.path.join(ROOT, 'index.html')).read()
    out = []
    for card in re.findall(r'<article class="guide-card[^"]*".*?</article>', h, re.S):
        title = re.search(r'<h3>(.*?)</h3>', card, re.S)
        sub = re.search(r'<p class="sub">(.*?)</p>', card, re.S)
        hrefs = re.findall(r'href="(?!https?:|mailto:|#)([^"]+)"', card)
        if not title or not hrefs:
            continue
        clean = lambda s: re.sub(r'<[^>]+>', '', s).replace('&amp;', '&').strip()
        out.append({'title': clean(title.group(1)),
                    'sub': clean(sub.group(1)) if sub else '',
                    'hrefs': hrefs})
    return out


def tips():
    out = []
    for slug in TIP_ORDER:
        cfg = os.path.join(ROOT, 'tools', 'video-build', 'projects', 'onshape-tips', slug, 'video.json')
        if os.path.exists(cfg):
            import json
            out.append((json.load(open(cfg))['heading'], slug))
    return out


def tasks():
    import yaml
    base = os.path.join(ROOT, 'skills', 'maker-tasks', 'tasks')
    out = []
    for name in sorted(os.listdir(base)):
        if not name.endswith('.yml'):
            continue
        t = yaml.safe_load(open(os.path.join(base, name)))
        out.append((t.get('title', name), name[:-4]))
    return out


def plan():
    """The whole course structure, as (module name, [(title, url), ...])."""
    mods = []
    mods.append(('Start here', [
        ('Course site', f'{SITE}/'),
        ('Syllabus', f'{SITE}/syllabus/'),
    ]))

    tip_items = [(title, f'{SITE}/onshape-tips/videos/{slug}.mp4') for title, slug in tips()]
    tip_items.append(('All nine, on the course site', f'{SITE}/onshape-tips/'))
    mods.append(('Onshape tips', tip_items))

    for c in classes():
        items = []
        if c['deck']:
            items.append(('Slides (PDF)', f'{SITE}/classes/{c["slug"]}/{c["deck"]}'))
        items.append(('Class page', f'{SITE}/classes/{c["slug"]}/'))
        mods.append((f'Class {c["week"]} · {c["title"]}', items))

    guide_items = [(g['title'], f'{SITE}/{g["hrefs"][0]}') for g in guides()
                   if not g['hrefs'][0].startswith('syllabus')]
    guide_items.append(('OpenCode + DeepSeek — Windows',
                        f'{SITE}/opencode-deepseek-guide-win/guide.html'))
    mods.append(('Guides', guide_items))

    task_items = [(title, f'{SITE}/tasks/{slug}.html') for title, slug in tasks()]
    task_items.sort(key=lambda kv: ('/unit-' not in kv[1], kv[0]))
    mods.append(('Skill tasks · Laser-ready file', task_items))
    return mods


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--course', default=PROTOTYPE_COURSE,
                    help=f'Canvas course id (default {PROTOTYPE_COURSE}, the prototype)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--publish', action='store_true',
                    help='publish the modules and items (Canvas creates them unpublished)')
    args = ap.parse_args()

    mods = plan()
    total = sum(len(items) for _, items in mods)
    print(f'course {args.course}: {len(mods)} modules, {total} items\n')
    if args.dry_run:
        for name, items in mods:
            print(f'  {name}')
            for title, url in items:
                print(f'      {title:46s} {url}')
        print('\nnothing written (--dry-run)')
        return

    cfg = load_config()
    cfg['course_id'] = str(args.course)
    client = Client(**cfg)
    print(f'  acting as {client.whoami().get("name", "?")}')

    created_mod, created_item, skipped, published = 0, 0, 0, 0
    for position, (name, items) in enumerate(mods, start=1):
        existing = next((m for m in client.modules() if m['name'] == name), None)
        if existing:
            mod = existing
        else:
            mod = client.ensure_module(name=name, position=position)
            created_mod += 1
            print(f'  + module {name}')
        if args.publish and not mod.get('published'):
            client.put(f'/courses/{client.course_id}/modules/{mod["id"]}',
                       module={'published': True})
            published += 1
        have = {i['title']: i for i in client.module_items(mod['id'])}
        for pos, (title, url) in enumerate(items, start=1):
            if title in have:
                skipped += 1
                if args.publish and not have[title].get('published'):
                    client.put(f'/courses/{client.course_id}/modules/{mod["id"]}'
                               f'/items/{have[title]["id"]}', module_item={'published': True})
                    published += 1
                continue
            item = client.add_module_item(mod['id'], type='ExternalUrl', title=title,
                                          external_url=url, position=pos, new_tab=True)
            created_item += 1
            if args.publish:
                client.put(f'/courses/{client.course_id}/modules/{mod["id"]}'
                           f'/items/{item["id"]}', module_item={'published': True})
                published += 1
            print(f'  + {"":26s} {title}')

    print(f'\n  {created_mod} module(s) and {created_item} item(s) created, '
          f'{skipped} already there'
          + (f', {published} published' if args.publish else ' (unpublished - pass --publish)'))
    print(f'  https://canvas.tufts.edu/courses/{args.course}/modules')


if __name__ == '__main__':
    main()
