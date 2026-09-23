#!/usr/bin/env python3
"""Create an Onshape document for a video project, once, and adopt its tab.

Onshape's Create flow opens the new document in a **new tab**, and a recording
session stays pinned to the tab it started on. A take's setup therefore cannot
create its own document: it clicks Create, the document appears in another tab,
and the setup carries on against the /documents page - reporting success while
it works on the wrong page.

So each video's document is created here, out of band, and its Part Studio URL
is recorded in the project's video.json as "documentUrl". Setups then only have
to call openDocument(cfg.documentUrl), which navigates the current tab.

    python3 tools/video-build/new-document.py <project> [--session NAME] [--name NAME]

Re-running against a project that already has a documentUrl is a no-op unless
--force is given. Pass --name to override the document name (default: the
project's "documentName", else its "heading").
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PATHS = '/tmp/vid/vb-paths.json'


def run(*args):
    p = subprocess.run(args, capture_output=True, text=True)
    return p.stdout.strip()


def status():
    try:
        return json.loads(run('browser-control', 'status', '--json'))
    except Exception:
        return {}


def targets():
    return (status().get('targets') or [])


def bundle(script):
    """lib.js + lib2.js + beat.js + script, as one execute() body."""
    parts = []
    for name in ('scenes/lib.js', 'scenes/lib2.js'):
        with open(os.path.join(HERE, name)) as fh:
            parts.append('\n'.join(l for l in fh.read().splitlines()
                                   if not l.startswith('module.exports')))
    with open(os.path.join(HERE, 'scenes/beat.js')) as fh:
        parts.append(fh.read())
    parts.append('return await (async () => {')
    parts.append(script)
    parts.append('})();')
    return '\n'.join(parts)


def execute(session, path):
    p = subprocess.run(['browser-control', 'execute', '--session', session,
                        '--file', path, '--json'], capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {'ok': False, 'text': (p.stdout or p.stderr)[:300]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('project')
    ap.add_argument('--session', default=os.environ.get('SESSION', 'onshape-video'))
    ap.add_argument('--name')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    proj = os.path.abspath(args.project if os.path.isdir(args.project)
                            else os.path.join(HERE, 'projects', args.project))
    cfg_path = os.path.join(proj, 'video.json')
    if not os.path.exists(cfg_path):
        sys.exit(f'no video.json in {proj}')
    cfg = json.load(open(cfg_path))

    if cfg.get('documentUrl') and not args.force:
        print(f'already has documentUrl: {cfg["documentUrl"]}')
        print('pass --force to make another document')
        return

    name = args.name or cfg.get('documentName') or cfg.get('heading') or cfg['slug']

    work = os.path.expanduser(cfg['workDir'])
    os.makedirs('/tmp/vid', exist_ok=True)
    with open(PATHS, 'w') as fh:      # beat.js reads the timings on load
        json.dump({'timings': os.path.join(work, 'sentence-timings.json'),
                   'project': proj, 'work': work}, fh)

    before = {t.get('url') for t in targets()}
    os.makedirs('/tmp/vid', exist_ok=True)
    path = '/tmp/vid/.newdoc.js'
    with open(path, 'w') as fh:
        fh.write(bundle(f'return await createDocument({json.dumps(name)});'))

    print(f'creating "{name}" ...')
    res = execute(args.session, path)
    # The helper reports ok:false here by design - it loses sight of the new tab.
    print(f'  create step: ok={res.get("ok")}')
    if not res.get('ok'):
        print(f'  note: {(res.get("text") or "")[:200]}')

    # The new document is the tab that was not there before. Depending on the
    # state of the /documents page the Create flow either navigates in-tab or
    # opens a new one, so check both.
    fresh = None
    url = None
    for _ in range(24):
        time.sleep(2.5)
        here = run('browser-control', 'execute', '--session', args.session, 'return page.url()')
        if '/e/' in here and here not in before:
            url = here
            break
        for t in targets():
            u = t.get('url') or ''
            if u not in before and '/e/' in u and 'Part Studio' in (t.get('title') or ''):
                fresh = t
                break
        if fresh:
            break

    if url:
        print('  created in the session tab (no adopt needed)')
    elif fresh:
        print(f'  new tab: {fresh["title"][:50]}')
        run('browser-control', 'session', 'adopt', '--session', args.session,
            '--target-url', fresh['url'])
    else:
        print('could not find the new Part Studio; open tabs:')
        for t in targets():
            print(f'  {(t.get("title") or "")[:40]:42s} {(t.get("url") or "")[:100]}')
        sys.exit(1)

    # Confirm the session is actually on it before recording the URL.
    for _ in range(10):
        url = run('browser-control', 'execute', '--session', args.session, 'return page.url()')
        if '/e/' in url:
            break
        time.sleep(2)

    if not url or '/e/' not in url:
        sys.exit(f'session did not land on the Part Studio (got {url!r})')

    cfg['documentUrl'] = url
    with open(cfg_path, 'w') as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=True)
        fh.write('\n')
    print(f'  documentUrl -> {url}')
    print(f'  written to {os.path.relpath(cfg_path, os.path.dirname(HERE))}')


if __name__ == '__main__':
    main()
