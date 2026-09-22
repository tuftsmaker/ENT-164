#!/usr/bin/env python3
"""Upload a video to the ENT-164 / TuftsMaker YouTube channel.

Uses the YouTube Data API v3 `videos.insert` method with a resumable upload.
Credentials live OUTSIDE this repo (see below) and are never printed.

    ~/.config/tuftsmaker/youtube_config.py    client secret + token paths

First run opens a browser for a one-time Google consent; the refresh token is
cached next to the client secret so later runs are unattended.

The config module is loaded from that directory by absolute path, so no
PYTHONPATH juggling is needed.

Requirements (install into a venv, not the system Python):
    python3 -m venv ~/.venvs/ent164-youtube
    ~/.venvs/ent164-youtube/bin/pip install \\
        google-api-python-client google-auth-oauthlib google-auth-httplib2
    ~/.venvs/ent164-youtube/bin/python scripts/upload-youtube.py video.mp4 --title "..."

IMPORTANT — unaudited projects are locked to private:
    Google restricts every upload made through an API project that has not
    passed a compliance audit to *private* viewing mode. The upload succeeds,
    but YouTube then silently refuses to publish it publicly. Run with
    --check-audit to see whether the API will report this for your project,
    and see AGENTS.md for the audit form link.

Usage:
    scripts/upload-youtube.py VIDEO [options]
    scripts/upload-youtube.py VIDEO --title "Class 5 · Electronics" --privacy unlisted
    scripts/upload-youtube.py VIDEO --dry-run
"""
import argparse
import os
import sys

# youtube.upload is the least-privilege scope for publishing. youtube.readonly
# is needed as well because the script verifies the target channel and reads the
# video back afterwards (to detect the unaudited-project private lock), and
# those are read operations that youtube.upload alone does not permit.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

# "Science & Technology" — the closest fit for a making/engineering channel.
# Full list: https://developers.google.com/youtube/v3/docs/videoCategories/list
DEFAULT_CATEGORY = "28"

# Containers YouTube commonly accepts (it re-encodes everything anyway).
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi", ".wmv", ".flv", ".webm", ".mkv", ".mpg", ".mpeg", ".3gp"}

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "tuftsmaker")
CONFIG_PATH = os.path.join(CONFIG_DIR, "youtube_config.py")

CONFIG_HINT = f"""
    Expected config file: {CONFIG_PATH}

        # Path to the OAuth client secret downloaded from Google Cloud Console
        # (Credentials -> OAuth client ID -> Desktop app -> Download JSON).
        CLIENT_SECRET_FILE = "{CONFIG_DIR}/client_secret.json"

        # Where the refresh token is cached after the first consent. Keep this
        # outside the repo as well.
        TOKEN_FILE = "{CONFIG_DIR}/token.json"

        # Optional: pin the channel to protect against consenting with the
        # wrong Google account (recommended).
        EXPECTED_CHANNEL_ID = "UC..."
""".strip()


def load_config():
    """Load youtube_config.py from outside the repo.

    Loaded by absolute path from ~/.config/tuftsmaker/ so the caller does not
    have to set PYTHONPATH, and so nothing credential-related can drift into
    the repository. Values are read but never printed.
    """
    if not os.path.exists(CONFIG_PATH):
        sys.exit(f"Config not found: {CONFIG_PATH}\n\n" + CONFIG_HINT)

    import importlib.util

    spec = importlib.util.spec_from_file_location("youtube_config", CONFIG_PATH)
    cfg = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(cfg)
    except Exception as e:
        sys.exit(f"Could not read {CONFIG_PATH}: {e}")

    missing = [n for n in ("CLIENT_SECRET_FILE", "TOKEN_FILE") if not getattr(cfg, n, None)]
    if missing:
        sys.exit("youtube_config.py is missing: " + ", ".join(missing) + "\n\n" + CONFIG_HINT)
    return cfg


def get_credentials(cfg, force_reauth=False):
    """Return OAuth credentials, running the browser consent flow if needed.

    The refresh token is cached in TOKEN_FILE so this is a one-time step.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_file = os.path.expanduser(cfg.TOKEN_FILE)
    creds = None

    if not force_reauth and os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        except ValueError:
            creds = None  # corrupt/stale token file -> re-consent below

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        secret = os.path.expanduser(cfg.CLIENT_SECRET_FILE)
        if not os.path.exists(secret):
            sys.exit(
                f"OAuth client secret not found: {secret}\n\n"
                "Create one in Google Cloud Console:\n"
                "  APIs & Services -> Credentials -> Create credentials\n"
                "  -> OAuth client ID -> Desktop app -> Download JSON\n\n" + CONFIG_HINT
            )
        flow = InstalledAppFlow.from_client_secrets_file(secret, SCOPES)
        # Local loopback flow; opens the browser once.
        creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())
        os.chmod(token_file, 0o600)
        print(f"Saved refresh token to {token_file} (do not commit this)")

    return creds


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def check_channel(youtube, cfg):
    """Verify the consented account is the channel we expect.

    Guards against silently uploading to whichever Google account happened to
    be signed in during consent. This is a read call, so it needs the
    youtube.readonly scope; failure here is non-fatal because the upload
    scope alone is still enough to publish.
    """
    from googleapiclient.errors import HttpError

    try:
        resp = youtube.channels().list(part="snippet", mine=True).execute()
    except HttpError as e:
        print(f"Could not read the channel ({e.resp.status}); continuing without verification.")
        return None

    items = resp.get("items", [])
    if not items:
        sys.exit("This Google account has no YouTube channel.")
    ch = items[0]
    name = ch["snippet"]["title"]
    cid = ch["id"]
    print(f"Channel: {name}  ({cid})")
    expected = getattr(cfg, "EXPECTED_CHANNEL_ID", None)
    if expected and expected != cid:
        sys.exit(
            f"Channel mismatch: expected {expected}, got {cid}.\n"
            "Re-authenticate with the right Google account, or update "
            "EXPECTED_CHANNEL_ID in youtube_config.py."
        )
    return cid


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


def build_body(args, size):
    """Assemble the video resource.

    Only the properties videos.insert actually accepts are set here; an
    unknown or malformed value makes the whole call fail with a 400.
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


def upload(youtube, args, path, size):
    """Resumable upload with progress, retrying transient failures."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    body = build_body(args, size)
    media = MediaFileUpload(path, chunksize=8 * 1024 * 1024, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
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


def report(youtube, video_id, privacy):
    """Read the video back and warn if YouTube overrode the privacy.

    Read-back is best-effort: the upload has already succeeded by this point,
    so a failure here must not look like an upload failure.
    """
    from googleapiclient.errors import HttpError

    try:
        resp = youtube.videos().list(
            part="status,snippet,processingDetails", id=video_id
        ).execute()
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
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    ap.add_argument("--check-audit", action="store_true",
                    help="upload a tiny throwaway video to learn whether the project is audited")
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
        cfg = load_config()
        secret = os.path.expanduser(cfg.CLIENT_SECRET_FILE)
        token = os.path.expanduser(cfg.TOKEN_FILE)
        print(f"  Secret:   {secret} {'(found)' if os.path.exists(secret) else '(MISSING)'}")
        print(f"  Token:    {token} {'(cached)' if os.path.exists(token) else '(not yet — first run will open a browser)'}")
        return

    cfg = load_config()

    # Imported here so --dry-run works without the libraries installed.
    from googleapiclient.discovery import build

    creds = get_credentials(cfg, force_reauth=args.reauth)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    check_channel(youtube, cfg)

    if args.check_audit:
        print()
        print("--check-audit given: uploading a short test video to see whether")
        print("this project can publish publicly. Delete it afterwards.")
        args.title = args.title or "ENT-164 API audit check (safe to delete)"
        args.privacy = "unlisted"

    try:
        result = upload(youtube, args, args.video, size)
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
    report(youtube, result["id"], args.privacy)


if __name__ == "__main__":
    main()
