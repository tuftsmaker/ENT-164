#!/usr/bin/env python3
"""(Re)publish a series of locally rendered videos to the TuftsMaker channel.

Written for the Onshape tips, but not specific to them: it reads a directory of
`tools/video-build` projects, publishes whichever are not already on the channel,
and records the result in a manifest so a run can be resumed.

Why it exists: the channel has a per-account daily upload cap (see AGENTS.md)
that is far tighter than the API quota, so a batch republish cannot be done in
one sitting. Re-run this until it stops saying "capped" - it uploads what it can
and leaves the rest alone.

    scripts/sync-youtube-series.py --dry-run          # say what it would do
    scripts/sync-youtube-series.py                    # upload what the cap allows
    scripts/sync-youtube-series.py --prune            # + delete superseded uploads
    scripts/sync-youtube-series.py --rebuild-playlist # + rebuild the playlist in order

Each project contributes its `heading` as the title, its `subtitle` plus a series
blurb as the description, and `build/title.png` as the thumbnail. The manifest
(default `onshape-tips/youtube.json`) maps slug -> video id, so "already
published" survives across runs and across machines.

Credentials live OUTSIDE this repo; see scripts/_youtube_auth.py.
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _youtube_auth as auth  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TAGS = ("onshape,laser cutting,cad tutorial,ent-164,intro to making,tufts,"
        "nolop makerspace,2d drawing,dxf")
BLURB = ('Part of the ENT-164 "Onshape Tips" series — short lessons on drawing a '
         'part in Onshape, exporting the DXF and cutting it on the laser cutter.')
SITE = "Course site: https://tuftsmaker.github.io/ENT-164/"


def channel_videos(yt, limit=50):
    """Every upload on the channel: {id: title}."""
    ch = yt.channels().list(part='contentDetails', mine=True).execute()['items'][0]
    uploads = ch['contentDetails']['relatedPlaylists']['uploads']
    out, token = {}, None
    while True:
        r = yt.playlistItems().list(part='snippet', playlistId=uploads,
                                    maxResults=limit, pageToken=token).execute()
        for it in r.get('items', []):
            s = it['snippet']
            out[s['resourceId']['videoId']] = s['title']
        token = r.get('nextPageToken')
        if not token:
            return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--projects', default=os.path.join(ROOT, 'tools/video-build/projects/onshape-tips'))
    ap.add_argument('--manifest', default=os.path.join(ROOT, 'onshape-tips/youtube.json'))
    ap.add_argument('--order', default='workspace-overview,basic-rectangle,updating-dimensions,'
                                      'circle-to-cut-a-hole,circle-in-the-center,circle-on-a-corner,'
                                      'mirroring-entities,trim-tool,laser-cut-joints')
    ap.add_argument('--playlist', default='Onshape Tips')
    ap.add_argument('--prune', action='store_true',
                    help='delete channel uploads whose title matches a slug but that are not current')
    ap.add_argument('--rebuild-playlist', action='store_true',
                    help='recreate the playlist so the order is right')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    order = [s.strip() for s in args.order.split(',') if s.strip()]
    manifest = {}
    if os.path.exists(args.manifest):
        manifest = json.load(open(args.manifest))

    yt = auth.service('manage')
    existing = channel_videos(yt)
    by_title = {}
    for vid, title in existing.items():
        by_title.setdefault(title.strip().lower(), []).append(vid)

    def slug_of(path):
        return os.path.basename(path.rstrip('/'))

    uploaded, capped, missing = 0, False, []
    for slug in order:
        proj = os.path.join(args.projects, slug)
        cfg_path = os.path.join(proj, 'video.json')
        if not os.path.exists(cfg_path):
            missing.append(slug)
            continue
        cfg = json.load(open(cfg_path))
        title = cfg['heading']
        video = os.path.expanduser(cfg['output'])
        poster = os.path.join(os.path.expanduser(cfg['workDir']), 'build', 'title.png')

        current = manifest.get(slug, {}).get('id')
        if current and current in existing and existing[current].strip() == title:
            print(f"  {slug:22s} up to date  {current}")
            continue
        if capped:
            continue
        if not os.path.exists(video):
            print(f"  {slug:22s} MISSING {video}")
            continue

        print(f"  {slug:22s} uploading {title!r}")
        if args.dry_run:
            continue
        desc = f"{cfg.get('subtitle', '')}\n\n{BLURB}\n\n{SITE}\nNolop Makerspace · Tufts University"
        p = subprocess.run([sys.executable, os.path.join(HERE, 'upload-youtube.py'), video,
                            '--title', title, '--description', desc, '--tags', TAGS],
                           capture_output=True, text=True)
        out = (p.stdout or '') + (p.stderr or '')
        if 'upload cap' in out.lower() or 'quota' in out.lower():
            print('    capped for today - stopping here; re-run tomorrow')
            capped = True
            continue
        vid = None
        for line in out.splitlines():
            if 'youtu.be/' in line:
                vid = line.strip().split('youtu.be/')[1].split()[0]
        if not vid:
            print('    upload failed:', out.strip().splitlines()[-1][:160] if out.strip() else '(no output)')
            continue
        subprocess.run([sys.executable, os.path.join(HERE, 'update-youtube.py'), vid,
                        '--privacy', 'public'], capture_output=True, text=True)
        if os.path.exists(poster):
            subprocess.run([sys.executable, os.path.join(HERE, 'update-youtube.py'), vid,
                            '--thumbnail', poster], capture_output=True, text=True)
        manifest[slug] = {'id': vid, 'title': title}
        json.dump(manifest, open(args.manifest, 'w'), indent=2, ensure_ascii=True)
        open(args.manifest, 'a').write('\n')
        uploaded += 1
        print(f"    -> {vid}  public")

    if missing:
        print('  not found:', ', '.join(missing))

    if args.prune:
        mine = {m['id'] for m in manifest.values() if m.get('id')}
        drop = []
        for slug in order:
            proj = os.path.join(args.projects, slug)
            if not os.path.exists(os.path.join(proj, 'video.json')):
                continue
            # Only ever remove the superseded upload of a slug whose *replacement*
            # is published. Pruning a slug that is still pending would take the
            # video off the channel with nothing to put in its place.
            if not manifest.get(slug, {}).get('id'):
                continue
            title = json.load(open(os.path.join(proj, 'video.json')))['heading']
            for vid in by_title.get(title.strip().lower(), []):
                if vid not in mine:
                    drop.append((vid, title))
        for vid, title in drop:
            if args.dry_run:
                print(f'  would delete superseded {vid}  {title}')
                continue
            yt.videos().delete(id=vid).execute()
            print(f'  deleted superseded {vid}  {title}')

    if args.rebuild_playlist:
        ids = [manifest[s]['id'] for s in order if manifest.get(s, {}).get('id')]
        if args.dry_run:
            print(f'  would rebuild "{args.playlist}" with {len(ids)} videos')
        else:
            r = yt.playlists().list(part='snippet', mine=True, maxResults=50).execute()
            old = next((p for p in r.get('items', [])
                        if p['snippet']['title'].strip().lower() == args.playlist.lower()), None)
            if old:
                yt.playlists().delete(id=old['id']).execute()
                print(f'  removed the old playlist {old["id"]}')
            pl = yt.playlists().insert(part='snippet,status', body={
                'snippet': {'title': args.playlist,
                            'description': 'Short Onshape lessons for ENT-164 Intro to Making '
                                           '— draw a part, export the DXF, cut it on the laser cutter.'},
                'status': {'privacyStatus': 'public'}}).execute()
            for vid in ids:
                yt.playlistItems().insert(part='snippet', body={
                    'snippet': {'playlistId': pl['id'],
                                'resourceId': {'kind': 'youtube#video', 'videoId': vid}}}).execute()
            print(f'  playlist rebuilt with {len(ids)}: '
                  f'https://www.youtube.com/playlist?list={pl["id"]}')

    published = sum(1 for s in order if manifest.get(s, {}).get('id'))
    print(f'\n  {published}/{len(order)} published'
          + (f'  ({uploaded} this run)' if uploaded else '')
          + ('  - re-run after the cap resets' if capped else ''))


if __name__ == '__main__':
    main()
