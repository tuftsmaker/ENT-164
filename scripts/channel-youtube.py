#!/usr/bin/env python3
"""Inspect or change channel-level settings on the TuftsMaker channel.

Currently handles the "made for kids" audience declaration, which YouTube
applies per channel and per video. Use this to read the current state, or to
correct it.

Why this exists: the declaration has heavy consequences and is easy to set by
accident during channel onboarding. Setting it (or having it set) means
YouTube treats the content as child-directed, which disables comments, end
screens, cards, notifications, and personalised ads on every video. For a
university course channel that is almost always the wrong answer; the correct
value is "not made for kids".

Note the API only exposes the channel's *own* declaration through
channels.update (status.selfDeclaredMadeForKids). Audit decisions made by
YouTube itself are not editable this way.

Credentials live outside this repo; see scripts/_youtube_auth.py.

Usage:
    scripts/channel-youtube.py --show
    scripts/channel-youtube.py --not-made-for-kids
    scripts/channel-youtube.py --made-for-kids
    scripts/channel-youtube.py --sync-videos          # align every video to the channel
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _youtube_auth as auth  # noqa: E402

# Features YouTube disables once content is child-directed. Printed as a
# warning, because the setting is silent and its effects are not reversible
# from the API alone.
MADE_FOR_KIDS_LOSSES = (
    "comments",
    "end screens and cards",
    "notifications of new uploads",
    "personalised ads",
    "channel memberships and Super Chat",
)


def channel_status(yt):
    return yt.channels().list(part="snippet,status,brandingSettings", mine=True).execute()["items"][0]


def show(yt, header=False):
    """Print the current declaration.

    header defaults to False because auth.check_channel has already printed the
    channel line by the time this runs.
    """
    ch = channel_status(yt)
    st = ch["status"]
    if header:
        print(f"Channel: {ch['snippet']['title']}  ({ch['id']})")
    print(f"  madeForKids:             {st.get('madeForKids')}")
    print(f"  selfDeclaredMadeForKids: {st.get('selfDeclaredMadeForKids')}")
    if st.get("madeForKids"):
        print()
        print("  This content is treated as child-directed, so YouTube disables:")
        for item in MADE_FOR_KIDS_LOSSES:
            print(f"    - {item}")
    return st


def set_made_for_kids(yt, value):
    """Set the channel's own declaration. Returns the resulting status."""
    cid = channel_status(yt)["id"]
    # part="status" is accepted even though the docs' parameter list only
    # mentions brandingSettings/invideoPromotion/localizations;
    # selfDeclaredMadeForKids is the documented property to set.
    yt.channels().update(
        part="status",
        body={"id": cid, "status": {"selfDeclaredMadeForKids": value}},
    ).execute()
    return channel_status(yt)["status"]


def sync_videos(yt, channel_made_for_kids):
    """Align every video's declaration with the channel's.

    A channel-wide audience setting does not retroactively rewrite each
    video's stored declaration, so a mismatch can linger. This walks the
    uploads playlist and fixes any video that disagrees.
    """
    uploads = yt.channels().list(part="contentDetails", mine=True).execute()[
        "items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    video_ids, token = [], None
    while True:
        page = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                       maxResults=50, pageToken=token).execute()
        video_ids += [i["contentDetails"]["videoId"] for i in page["items"]]
        token = page.get("nextPageToken")
        if not token:
            break

    fixed, ok = [], 0
    for vid in video_ids:
        cur = yt.videos().list(part="status", id=vid).execute()["items"][0]
        declared = cur["status"].get("selfDeclaredMadeForKids")
        if declared == channel_made_for_kids:
            ok += 1
            continue
        yt.videos().update(
            part="status",
            body={"id": vid, "status": {"selfDeclaredMadeForKids": channel_made_for_kids}},
        ).execute()
        fixed.append(vid)

    print(f"Videos checked: {len(video_ids)}  already correct: {ok}  corrected: {len(fixed)}")
    for vid in fixed:
        print(f"  https://youtu.be/{vid}  -> selfDeclaredMadeForKids={channel_made_for_kids}")


def main():
    ap = argparse.ArgumentParser(
        description="Inspect or change channel-level YouTube settings",
        epilog="Config lives in ~/.config/tuftsmaker/ (never in this repo).",
    )
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--show", action="store_true", help="print the current declaration")
    group.add_argument("--made-for-kids", action="store_true",
                       help="declare the channel as child-directed (disables features)")
    group.add_argument("--not-made-for-kids", action="store_true",
                       help="declare the channel as NOT child-directed (correct for a course channel)")
    group.add_argument("--sync-videos", action="store_true",
                       help="align every video's made-for-kids declaration with the channel's")
    args = ap.parse_args()

    cfg = auth.load_config()
    yt = auth.service("manage")
    # Safety: fail loudly if the token belongs to an unexpected channel.
    auth.check_channel(yt, cfg)

    if args.show:
        show(yt)
        return

    if args.sync_videos:
        st = show(yt, header=False)
        target = bool(st.get("madeForKids"))
        print()
        sync_videos(yt, target)
        return

    target = True if args.made_for_kids else False
    before = show(yt, header=False)
    if before.get("madeForKids") == target:
        print()
        print(f"Already set to {target}; nothing to change.")
        return

    print()
    if target:
        print("WARNING: declaring this channel child-directed will disable:")
        for item in MADE_FOR_KIDS_LOSSES:
            print(f"  - {item}")

    after = set_made_for_kids(yt, target)
    print()
    print(f"Updated. madeForKids is now {after.get('madeForKids')} "
          f"(selfDeclaredMadeForKids={after.get('selfDeclaredMadeForKids')})")
    print("Existing videos keep their own declaration; run --sync-videos to align them.")


if __name__ == "__main__":
    main()
