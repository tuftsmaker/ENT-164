#!/usr/bin/env python3
"""Change an existing YouTube video: thumbnail, privacy, title, description, tags.

Complements scripts/upload-youtube.py, which only creates new videos. Use this
to set a custom thumbnail, publish an upload, fix a typo in a title, or adjust
tags afterwards.

This cannot use the upload token: videos.update is not covered by
youtube.upload (the API accepts only youtube, youtube.force-ssl or
youtubepartner). So it consents separately, with its own token file — which
also means adding this capability never invalidates the working upload token.
Thumbnails, by contrast, accept youtube.upload, but go through this same
manage token for consistency.

Credentials live outside this repo; see scripts/_youtube_auth.py.

Usage:
    scripts/update-youtube.py VIDEO_ID --thumbnail cover.png
    scripts/update-youtube.py VIDEO_ID --privacy public
    scripts/update-youtube.py VIDEO_ID --title "New title"
    scripts/update-youtube.py VIDEO_ID --dry-run
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _youtube_auth as auth  # noqa: E402

# videos.update replaces the parts named in `part`, so every writable property
# that is not being changed must be sent back verbatim or it is erased
# (tags are the classic casualty).
WRITABLE_STATUS = ("privacyStatus", "selfDeclaredMadeForKids", "embeddable", "license",
                   "publicStatsViewable")

# thumbnails.set accepts these; 2 MB is the practical limit YouTube enforces
# for custom thumbnails (the API documents 50 MB, YouTube Studio says 2 MB).
THUMB_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
THUMB_MAX_BYTES = 2 * 1024 * 1024
# YouTube displays thumbnails at 16:9 and rejects nothing, but a wrong aspect
# ratio gets letterboxed or centre-cropped, so warn rather than surprise.
THUMB_ASPECT = 16 / 9


def check_thumbnail(path):
    """Validate a thumbnail file before sending it."""
    if not os.path.isfile(path):
        sys.exit(f"No such thumbnail: {path}")
    size = os.path.getsize(path)
    if size == 0:
        sys.exit(f"Thumbnail is empty: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in THUMB_EXTS:
        sys.exit(f"Thumbnail must be one of {', '.join(sorted(THUMB_EXTS))} (got {ext or 'no extension'})")
    if size > THUMB_MAX_BYTES:
        sys.exit(f"Thumbnail is {size/1024/1024:.1f} MB, over the 2 MB limit YouTube enforces.")

    try:
        from PIL import Image
    except ImportError:
        return size  # Pillow not installed: size/type checks are enough

    with Image.open(path) as im:
        w, h = im.size
    ar = w / h
    if abs(ar - THUMB_ASPECT) > 0.01:
        print(f"WARNING: thumbnail is {w}x{h} ({ar:.2f}:1); YouTube uses 16:9 "
              f"({THUMB_ASPECT:.2f}:1) and will letterbox or crop it.", file=sys.stderr)
    if w < 1280:
        print(f"WARNING: thumbnail is only {w}px wide; YouTube recommends "
              f"1280x720 or larger.", file=sys.stderr)
    return size


def set_thumbnail(yt, video_id, path):
    """Upload and assign a custom thumbnail."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    print(f"Setting thumbnail: {os.path.basename(path)}")
    try:
        yt.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(path, mimetype=None, resumable=False),
        ).execute()
    except HttpError as e:
        # The API's wording blames permissions, which sends people chasing
        # OAuth scopes. In practice this is a channel-eligibility gate.
        if e.resp.status == 403 and "thumbnail" in str(e):
            sys.exit(
                "YouTube refused the thumbnail.\n\n"
                "This is NOT a scope problem — the token has youtube.force-ssl,\n"
                "which thumbnails.set accepts. Custom thumbnails are one of\n"
                "YouTube's 'intermediate features', unlocked by verifying the\n"
                "channel with a phone number:\n\n"
                "  https://www.youtube.com/verify\n\n"
                "After verifying, re-run this command. Until then, the video\n"
                "keeps YouTube's auto-generated thumbnail."
            )
        raise


def fetch(yt, video_id):
    resp = yt.videos().list(part="snippet,status", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        sys.exit(f"No video found with id {video_id} on this channel.")
    return items[0]


def build(it, args):
    """Merge the requested changes onto the video's current metadata."""
    snippet = {
        "title": args.title or it["snippet"]["title"],
        "description": (args.description if args.description is not None
                        else it["snippet"].get("description", "")),
        "categoryId": it["snippet"].get("categoryId", "28"),
    }
    if args.tags is not None:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        if tags:
            snippet["tags"] = tags
    elif it["snippet"].get("tags"):
        snippet["tags"] = it["snippet"]["tags"]

    status = {k: it["status"][k] for k in WRITABLE_STATUS if k in it["status"]}
    if args.privacy:
        status["privacyStatus"] = args.privacy
    return snippet, status


def show(snippet, status, current_privacy, tags_label):
    print("After this change:")
    print(f"  Title:   {snippet['title']}")
    print(f"  Privacy: {current_privacy} -> {status.get('privacyStatus')}")
    print(f"  Tags:    {', '.join(snippet.get('tags', [])) or '(none)'}  {tags_label}")
    print(f"  Desc:    {len(snippet['description'])} chars")


def main():
    ap = argparse.ArgumentParser(
        description="Update an existing YouTube video",
        epilog="Config lives in ~/.config/tuftsmaker/ (never in this repo).",
    )
    ap.add_argument("video_id", help="the video id (the part after youtu.be/)")
    ap.add_argument("--privacy", choices=("private", "unlisted", "public"))
    ap.add_argument("--title")
    ap.add_argument("--description")
    ap.add_argument("--tags", help="comma-separated; replaces the existing set")
    ap.add_argument("--thumbnail", help="path to an image to use as the custom thumbnail")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reauth", action="store_true", help="ignore the cached token and consent again")
    args = ap.parse_args()

    if not any((args.privacy, args.title, args.description, args.tags is not None, args.thumbnail)):
        ap.error("nothing to change; pass at least one of "
                 "--privacy/--title/--description/--tags/--thumbnail")

    cfg = auth.load_config()

    thumb_size = check_thumbnail(args.thumbnail) if args.thumbnail else None

    # A dry run still needs a token to read the current values, but should not
    # trigger a browser consent as a side effect.
    if args.dry_run and not os.path.exists(auth.token_path("manage")):
        sys.exit(
            "No manage token yet, so a dry run cannot read the video.\n"
            "Run once without --dry-run to consent (a browser will open)."
        )

    yt = auth.service("manage", force_reauth=args.reauth)
    auth.check_channel(yt, cfg)

    it = fetch(yt, args.video_id)
    current = it["status"].get("privacyStatus")
    snippet, status = build(it, args)

    print(f"Video:   {it['snippet']['title']}")
    print(f"Current: {current}")
    tags_label = "(replaced)" if args.tags is not None else "(unchanged)"
    if args.tags is None and not it["snippet"].get("tags"):
        tags_label = "(none set)"
    show(snippet, status, current, tags_label)
    if args.thumbnail:
        print(f"  Thumb:   {args.thumbnail} ({thumb_size/1024:.0f} KB)")

    if args.dry_run:
        print()
        print("DRY RUN — nothing sent.")
        return

    # Thumbnails are a separate endpoint from videos.update, so do it first:
    # if the metadata update fails, the thumbnail is still applied.
    if args.thumbnail:
        set_thumbnail(yt, args.video_id, args.thumbnail)
        print()

    resp = yt.videos().update(
        part="snippet,status",
        body={"id": args.video_id, "snippet": snippet, "status": status},
    ).execute()

    print("Updated.")
    now = resp["status"]["privacyStatus"]
    print(f"  Privacy: {now}")
    if args.thumbnail:
        print(f"  Thumb:   {os.path.basename(args.thumbnail)}")
    if args.privacy and now != args.privacy:
        print("WARNING: YouTube did not apply the requested privacy.")
        print("         If it stays private, that is the unaudited-project lock:")
        print("         https://support.google.com/youtube/contact/yt_api_form")
    print(f"  https://youtu.be/{args.video_id}")


if __name__ == "__main__":
    main()
