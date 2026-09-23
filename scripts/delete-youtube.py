#!/usr/bin/env python3
"""Delete a video from the TuftsMaker channel.

Deleting is permanent: the video, its comments and its place in any playlist all
go. So this prints what it is about to remove and does nothing without --yes.

    scripts/delete-youtube.py 63xGrpgIy8I            # shows what would go
    scripts/delete-youtube.py 63xGrpgIy8I --yes

Credentials live OUTSIDE this repo; see scripts/_youtube_auth.py. Uses the
`manage` token, which carries youtube.force-ssl.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _youtube_auth as auth  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video_id', help='the part after youtu.be/')
    ap.add_argument('--yes', action='store_true', help='actually delete')
    args = ap.parse_args()

    yt = auth.service('manage')
    r = yt.videos().list(part='snippet,statistics,status', id=args.video_id).execute()
    if not r.get('items'):
        sys.exit(f'no such video on this channel: {args.video_id}')
    v = r['items'][0]
    s, st = v['snippet'], v['statistics']
    print(f"  {v['id']}")
    print(f"  Title:   {s['title']}")
    print(f"  Channel: {s['channelTitle']}")
    print(f"  Privacy: {v['status']['privacyStatus']}")
    print(f"  Views:   {st.get('viewCount', '0')}   Comments: {st.get('commentCount', '0')}")

    if not args.yes:
        print('\nnothing deleted - re-run with --yes')
        return
    yt.videos().delete(id=args.video_id).execute()
    print(f"\ndeleted {args.video_id}")


if __name__ == '__main__':
    main()
