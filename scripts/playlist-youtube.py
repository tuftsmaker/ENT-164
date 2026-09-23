#!/usr/bin/env python3
"""Create a playlist on the TuftsMaker channel and fill it, in order.

The series videos live in one playlist so a class page can link a single URL.
Credentials live OUTSIDE this repo; see scripts/_youtube_auth.py. Uses the
`manage` token, which carries youtube.force-ssl (playlist edits are not covered
by youtube.upload).

    scripts/playlist-youtube.py --list
    scripts/playlist-youtube.py --playlist "Onshape Tips" \\
        --video wLzJH4YIjOA --video O6mvUl5oa34

Re-running with the same playlist name adds only the videos that are not in it
already, so it is safe to re-run after a new video is published.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _youtube_auth as auth  # noqa: E402


def find(yt, title):
    r = yt.playlists().list(part='snippet,status', mine=True, maxResults=50).execute()
    for p in r.get('items', []):
        if p['snippet']['title'].strip().lower() == title.strip().lower():
            return p
    return None


def existing_ids(yt, playlist_id):
    ids, token = set(), None
    while True:
        r = yt.playlistItems().list(part='contentDetails', playlistId=playlist_id,
                                    maxResults=50, pageToken=token).execute()
        for it in r.get('items', []):
            ids.add(it['contentDetails']['videoId'])
        token = r.get('nextPageToken')
        if not token:
            return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true', help='list this channel\'s playlists')
    ap.add_argument('--playlist', help='playlist title (created if it does not exist)')
    ap.add_argument('--video', action='append', default=[],
                    help='video id to append, in order (repeatable)')
    ap.add_argument('--privacy', choices=('private', 'unlisted', 'public'), default='public')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    yt = auth.service('manage') if not (args.dry_run and not args.list) else auth.service('manage')

    if args.list:
        r = yt.playlists().list(part='snippet,status', mine=True, maxResults=50).execute()
        for p in r.get('items', []):
            print(f"  {p['id']}  {p['snippet']['title']}  ({p['status']['privacyStatus']})")
        if not r.get('items'):
            print('  (no playlists)')
        return

    if not args.playlist:
        sys.exit('--playlist is required (or --list)')

    p = find(yt, args.playlist)
    if p:
        pid = p['id']
        print(f'playlist exists: {args.playlist}  ({pid})')
        if p['snippet'].get('title') and p['status']['privacyStatus'] != args.privacy and not args.dry_run:
            yt.playlists().update(part='status', body={
                'id': pid, 'status': {'privacyStatus': args.privacy}}).execute()
            print(f'  privacy -> {args.privacy}')
    elif args.dry_run:
        print(f'DRY RUN: would create the playlist "{args.playlist}" ({args.privacy})')
        pid = None
    else:
        p = yt.playlists().insert(part='snippet,status', body={
            'snippet': {'title': args.playlist,
                        'description': 'Short Onshape lessons for ENT-164 Intro to Making '
                                       '— draw a part, export the DXF, cut it on the laser cutter.'},
            'status': {'privacyStatus': args.privacy}}).execute()
        pid = p['id']
        print(f'created playlist: {args.playlist}  ({pid})')

    have = existing_ids(yt, pid) if pid else set()
    added = 0
    for vid in args.video:
        if vid in have:
            print(f'  {vid}  already in the playlist')
            continue
        if args.dry_run:
            print(f'  {vid}  would be added')
            continue
        yt.playlistItems().insert(part='snippet', body={
            'snippet': {'playlistId': pid, 'resourceId': {'kind': 'youtube#video', 'videoId': vid}}}).execute()
        added += 1
        print(f'  {vid}  added')
    if not args.dry_run:
        print(f'{added} added, playlist now {len(have) + added} videos')
        print(f'  https://www.youtube.com/playlist?list={pid}')


if __name__ == '__main__':
    main()
