#!/usr/bin/env python3
"""Upload a video to the ENT-164 / TuftsMaker YouTube channel.

Uses the YouTube Data API v3 `videos.insert` method with a resumable upload.
Credentials live OUTSIDE this repo; see scripts/_youtube_auth.py.

First run opens a browser for a one-time Google consent; the refresh token is
cached so later runs are unattended.

Requirements (install into a venv, not the system Python — mixing these into
the anaconda base env breaks streamlit, which needs protobuf<6):
    python3 -m venv ~/.venvs/ent164-youtube
    ~/.venvs/ent164-youtube/bin/pip install \\
        google-api-python-client google-auth-oauthlib google-auth-httplib2
    ~/.venvs/ent164-youtube/bin/python scripts/upload-youtube.py video.mp4 --title "..."

IMPORTANT — unaudited projects are locked to private:
    Google restricts every upload made through an API project that has not
    passed a compliance audit to *private* viewing mode. The upload succeeds,
    but YouTube then silently refuses to publish it publicly. The script warns
    when it detects this. See AGENTS.md for the audit form link.

Usage:
    scripts/upload-youtube.py VIDEO [options]
    scripts/upload-youtube.py VIDEO --title "Class 5 · Electronics" --privacy unlisted
    scripts/upload-youtube.py VIDEO --dry-run
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _youtube_auth as auth  # noqa: E402

# "Science & Technology" — the closest fit for a making/engineering channel.
# Full list: https://developers.google.com/youtube/v3/docs/videoCategories/list
DEFAULT_CATEGORY = "28"

# Containers YouTube commonly accepts (it re-encodes everything anyway).
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".wmv", ".flv", ".webm", ".mkv", ".mpg", ".mpeg", ".3gp"}


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def validate_video(path):
    if not os.path.isfile(path):
        sys.exit(f"No such file: {path}")
    size = os.path.getsize(path)
    if size == 0:
        sys.exit(f"File is empty: {path}")
    # 256 GB is the documented maximum for videos.insert.
    if size > 256 * 1024**3:
        sys.exit(f"File is {human(size)}, over the 256 GB API limit.")
    ext = os.path.splitext(path)[1].lower()
    if ext and ext not in VIDEO_EXTS:
        print(
            f"WARNING: {ext or '(no extension)'} is not a common video container "
            f"({', '.join(sorted(VIDEO_EXTS))}).\n"
            "         YouTube accepts video/* and re-encodes anything it can read,\n"
            "         but a non-video file will fail after the upload starts.",
            file=sys.stderr,
        )
    return size


def build_body(args):
    """Assemble the video resource.

    Only the properties videos.insert actually accepts are set; an unknown or
    malformed value makes the whole call fail with a 400.
    """
    body = {
        "snippet": {
            "title": args.title,
            "description": args.description or "",
            "categoryId": args.category,
        },
        "status": {
            "privacyStatus": args.privacy,
            # Explicit declaration is required by YouTube policy.
            "selfDeclaredMadeForKids": False,
        },
    }
    if args.tags:
        body["snippet"]["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]
    if args.publish_at:
        # Scheduled publishing only works when the video starts private.
        if args.privacy != "private":
            sys.exit("--publish-at requires --privacy private (YouTube rule).")
        body["status"]["publishAt"] = args.publish_at
    return body


def upload(yt, args, path, size):
    """Resumable upload with progress, retrying transient failures."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(path, chunksize=8 * 1024 * 1024, resumable=True)
    request = yt.videos().insert(
        part="snippet,status",
        body=build_body(args),
        media_body=media,
        notifySubscribers=args.notify_subscribers,
    )

    print(f"Uploading {os.path.basename(path)} ({human(size)}) as {args.privacy}...")
    response = None
    retries = 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"  {pct:3d}%  ({human(status.resumable_progress)} of {human(size)})",
                      flush=True)
            retries = 0
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504):
                retries += 1
                if retries > 5:
                    raise
                print(f"  transient {e.resp.status}, retrying ({retries}/5)...")
                continue
            raise
    return response


def report(yt, video_id, privacy):
    """Read the video back and warn if YouTube overrode the privacy.

    Best-effort: the upload already succeeded, so a read failure here must not
    look like an upload failure.
    """
    from googleapiclient.errors import HttpError

    try:
        resp = yt.videos().list(part="status,snippet,processingDetails", id=video_id).execute()
    except HttpError as e:
        print(f"\n  https://youtu.be/{video_id}")
        print(f"  Uploaded, but could not read it back ({e.resp.status}).")
        return

    if not resp.get("items"):
        print(f"Uploaded, but could not read back video {video_id}.")
        return

    item = resp["items"][0]
    snippet = item.get("snippet", {})
    actual = item.get("status", {}).get("privacyStatus")
    print()
    print(f"  https://youtu.be/{video_id}")
    print(f"  Title:   {snippet.get('title')}")
    print(f"  Privacy: {actual}")

    if actual == "private" and privacy != "private":
        print()
        print("  WARNING: YouTube forced this video to private.")
        print("  That is the unaudited-project restriction: videos uploaded via")
        print("  an API project that has not passed a compliance audit are")
        print("  locked to private viewing mode and cannot be made public.")
        print("  Fix: https://support.google.com/youtube/contact/yt_api_form")
        print("  Until then, upload in the YouTube Studio web UI instead.")

    processing = item.get("processingDetails", {}).get("processingStatus")
    if processing and processing != "succeeded":
        print(f"  Processing: {processing} (YouTube is still working on it)")


def main():
    ap = argparse.ArgumentParser(
        description="Upload a video to the TuftsMaker YouTube channel",
        epilog="Config lives in ~/.config/tuftsmaker/ (never in this repo).",
    )
    ap.add_argument("video", help="path to the video file (mp4/mov/mkv/...)")
    ap.add_argument("--title", help="video title (required unless --dry-run)")
    ap.add_argument("--description", help="video description")
    ap.add_argument("--tags", help="comma-separated tags")
    ap.add_argument("--category", default=DEFAULT_CATEGORY,
                    help=f"YouTube category id (default {DEFAULT_CATEGORY} = Science & Technology)")
    ap.add_argument("--privacy", choices=("private", "unlisted", "public"), default="private",
                    help="privacy status (default private — safest given the audit lock)")
    ap.add_argument("--publish-at", help="RFC 3339 time to publish (requires --privacy private)")
    ap.add_argument("--notify-subscribers", action="store_true",
                    help="notify subscribers (default off, to avoid spamming them on bulk uploads)")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate file + config and show what would be sent, without uploading")
    ap.add_argument("--reauth", action="store_true", help="ignore the cached token and consent again")
    args = ap.parse_args()

    if not args.dry_run and not args.title:
        ap.error("--title is required (or use --dry-run)")

    size = validate_video(args.video)

    if args.dry_run:
        print("DRY RUN — nothing will be uploaded.")
        print(f"  File:     {args.video} ({human(size)})")
        print(f"  Title:    {args.title or '(not set)'}")
        print(f"  Privacy:  {args.privacy}")
        print(f"  Category: {args.category}")
        print(f"  Tags:     {args.tags or '(none)'}")
        print(f"  Notify:   {'yes' if args.notify_subscribers else 'no'}")
        cfg = auth.load_config()
        secret = os.path.expanduser(cfg.CLIENT_SECRET_FILE)
        token = auth.token_path("upload")
        print(f"  Secret:   {secret} {'(found)' if os.path.exists(secret) else '(MISSING)'}")
        print(f"  Token:    {token} {'(cached)' if os.path.exists(token) else '(not yet — first run will open a browser)'}")
        return

    cfg = auth.load_config()
    yt = auth.service("upload", force_reauth=args.reauth)
    auth.check_channel(yt, cfg)

    try:
        result = upload(yt, args, args.video, size)
    except Exception as e:
        msg = str(e)
        if "uploadLimitExceeded" in msg:
            sys.exit(
                "Upload limit exceeded: this channel has hit YouTube's per-channel\n"
                "daily upload cap (separate from the API quota, and lower for new\n"
                "or unverified channels). Try again in 24 hours, or verify the\n"
                "channel to raise the limit."
            )
        if "quotaExceeded" in msg:
            sys.exit(
                "API quota exhausted. videos.insert has its own bucket of 100\n"
                "calls/day (1 unit each), resetting at midnight Pacific."
            )
        if "youtubeSignupRequired" in msg or "NoLinkedYouTubeAccount" in msg:
            sys.exit(
                "This Google account has no YouTube channel — service accounts\n"
                "cannot upload, a real user account with a channel is required."
            )
        raise

    print("Upload complete.")
    report(yt, result["id"], args.privacy)


if __name__ == "__main__":
    main()
