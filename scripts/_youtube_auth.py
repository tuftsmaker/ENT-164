#!/usr/bin/env python3
"""Shared YouTube OAuth plumbing for upload-youtube.py and update-youtube.py.

Not a command-line tool; import it. Credentials live OUTSIDE this repo, in
~/.config/tuftsmaker/ (never committed, mode 0600):

    youtube_config.py     points at the client secret
    client_secret.json    OAuth desktop-app client (Google Cloud Console)
    token-upload.json     refresh token for creating videos
    token-manage.json     refresh token for editing existing videos

Each purpose gets its OWN token file. Two reasons:

  1. Least privilege — a token only carries the scopes its job needs. Uploading
     does not need the ability to rewrite or delete existing videos.
  2. Adding a capability never breaks an existing token. Editing needed a
     broader scope than uploading; with one shared token that would have
     invalidated the working upload token and forced a re-consent for both.

When a cached token lacks a scope the caller needs, we detect that here and
re-consent, instead of letting the API fail later with a bare 403
"Insufficient Permission".
"""

import importlib.util
import os
import sys

# videos.insert accepts this and nothing broader is needed to publish.
UPLOAD = "https://www.googleapis.com/auth/youtube.upload"
# Reads: channels.list, videos.list (used for verification and read-back).
READONLY = "https://www.googleapis.com/auth/youtube.readonly"
# videos.update (privacy/title/tags/description) is NOT covered by
# youtube.upload. The API accepts only youtube, youtube.force-ssl or
# youtubepartner for it. force-ssl also happens to cover videos.insert.
FORCE_SSL = "https://www.googleapis.com/auth/youtube.force-ssl"

PURPOSES = {
    "upload": {"scopes": (UPLOAD, READONLY), "token": "token-upload.json"},
    "manage": {"scopes": (FORCE_SSL, READONLY), "token": "token-manage.json"},
}

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "tuftsmaker")
CONFIG_PATH = os.path.join(CONFIG_DIR, "youtube_config.py")

CONFIG_HINT = f"""
    Expected config file: {CONFIG_PATH}

        # OAuth client secret downloaded from Google Cloud Console
        # (Credentials -> Create credentials -> OAuth client ID ->
        #  Desktop app -> Download JSON).
        CLIENT_SECRET_FILE = "{CONFIG_DIR}/client_secret.json"

        # Optional: pin the channel, so consenting with the wrong Google
        # account fails loudly instead of acting on the wrong channel.
        # EXPECTED_CHANNEL_ID = "UC..."
""".strip()


def load_config():
    """Load youtube_config.py by absolute path from outside the repo.

    Absolute path so callers need no PYTHONPATH, and so nothing
    credential-related can drift into the repository.
    """
    if not os.path.exists(CONFIG_PATH):
        sys.exit(f"Config not found: {CONFIG_PATH}\n\n" + CONFIG_HINT)

    spec = importlib.util.spec_from_file_location("youtube_config", CONFIG_PATH)
    cfg = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(cfg)
    except Exception as e:
        sys.exit(f"Could not read {CONFIG_PATH}: {e}")

    if not getattr(cfg, "CLIENT_SECRET_FILE", None):
        sys.exit("youtube_config.py is missing CLIENT_SECRET_FILE\n\n" + CONFIG_HINT)
    return cfg


def token_path(purpose):
    if purpose not in PURPOSES:
        raise ValueError(f"unknown purpose {purpose!r}; expected one of {sorted(PURPOSES)}")
    return os.path.join(CONFIG_DIR, PURPOSES[purpose]["token"])


def _granted_scopes(token_file):
    """Scopes recorded in a cached token file, or None if unreadable."""
    import json

    try:
        with open(token_file) as f:
            return set(json.load(f).get("scopes") or [])
    except Exception:
        return None


def credentials(purpose, force_reauth=False, interactive=True):
    """Return OAuth credentials for a purpose, consenting if necessary.

    Re-consents automatically when no token exists, when the caller asked for
    it, or when the cached token is missing a scope this purpose needs.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    needed = set(PURPOSES[purpose]["scopes"])
    token_file = token_path(purpose)
    cfg = load_config()
    creds = None
    reason = None

    if not force_reauth and os.path.exists(token_file):
        granted = _granted_scopes(token_file)
        if granted is None:
            reason = "the cached token could not be read"
        elif not needed.issubset(granted):
            missing = ", ".join(sorted(needed - granted))
            reason = f"the cached token is missing required scope(s): {missing}"
        else:
            try:
                creds = Credentials.from_authorized_user_file(token_file, list(needed))
            except ValueError:
                reason = "the cached token is not usable"

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if creds and creds.valid:
        return creds

    if not interactive:
        sys.exit(
            f"Cannot {purpose} non-interactively: {reason or 'no valid token'}.\n"
            "Run this once from a terminal so a browser can open for consent."
        )

    if reason:
        print(f"Re-authorizing: {reason}.")
    secret = os.path.expanduser(cfg.CLIENT_SECRET_FILE)
    if not os.path.exists(secret):
        sys.exit(
            f"OAuth client secret not found: {secret}\n\n"
            "Create one in Google Cloud Console:\n"
            "  APIs & Services -> Credentials -> Create credentials\n"
            "  -> OAuth client ID -> Desktop app -> Download JSON\n\n" + CONFIG_HINT
        )

    flow = InstalledAppFlow.from_client_secrets_file(secret, list(needed))
    # Local loopback flow; opens the browser once.
    creds = flow.run_local_server(port=0)
    with open(token_file, "w") as f:
        f.write(creds.to_json())
    os.chmod(token_file, 0o600)
    print(f"Saved {purpose} token to {token_file} (do not commit this)")
    return creds


def service(purpose, force_reauth=False):
    """Build an authorized YouTube Data API client for a purpose."""
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=credentials(purpose, force_reauth=force_reauth),
                 cache_discovery=False)


def check_channel(yt, cfg):
    """Verify the consented account is the channel we expect, if pinned.

    A read call, so it needs the readonly scope. Non-fatal on failure: the
    upload/manage scope alone is still enough to do the work.
    """
    from googleapiclient.errors import HttpError

    try:
        resp = yt.channels().list(part="snippet", mine=True).execute()
    except HttpError as e:
        print(f"Could not read the channel ({e.resp.status}); continuing without verification.")
        return None

    items = resp.get("items", [])
    if not items:
        sys.exit("This Google account has no YouTube channel.")
    ch = items[0]
    cid, name = ch["id"], ch["snippet"]["title"]
    print(f"Channel: {name}  ({cid})")
    expected = getattr(cfg, "EXPECTED_CHANNEL_ID", None)
    if expected and expected != cid:
        sys.exit(
            f"Channel mismatch: expected {expected}, got {cid}.\n"
            "Re-authenticate with the right Google account, or update "
            "EXPECTED_CHANNEL_ID in youtube_config.py."
        )
    return cid
