"""Google OAuth 2.0 flow, token lifecycle, and scope definitions (M2.1).

Design rules:
- Least privilege: only the scopes needed for read-only career operations.
- Tokens are NEVER committed to git; they live in a gitignored local file.
- Refresh is handled transparently; expiry and revocation degrade to the
  null adapter (offline mode), never a crash.
- The authorization flow is founder-local (desktop app): the founder runs
  ``scripts/google_authorize.py``, a browser opens, they authorize, tokens
  are saved to ``data/processed/google_tokens.json``.
- No token is ever logged, printed, or exposed in an error message.

Google Cloud configuration required (see the M2.1 report for step-by-step):
1. Create a project at https://console.cloud.google.com
2. Enable Gmail API, Calendar API, Drive API
3. Create OAuth 2.0 credentials (Application type: Desktop app)
4. Download credentials.json to ``data/processed/google_credentials.json``
5. Add yourself as a test user (or publish the app for production)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Scopes (least privilege — read-only, career-relevant only)
# ---------------------------------------------------------------------------

#: Gmail: read messages/threads. Does NOT grant compose, send, modify, or label.
SCOPE_GMAIL_READONLY = "https://www.googleapis.com/auth/gmail.readonly"

#: Calendar: read events. Does NOT grant create, modify, or delete.
SCOPE_CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.readonly"

#: Drive: read file metadata (names, types, folders). Does NOT grant content
#: read or any mutation. Sufficient for discovering career artifacts.
SCOPE_DRIVE_METADATA_READONLY = "https://www.googleapis.com/auth/drive.metadata.readonly"

#: All scopes requested during the OAuth flow (least-privilege set).
ALL_SCOPES = [
    SCOPE_GMAIL_READONLY,
    SCOPE_CALENDAR_READONLY,
    SCOPE_DRIVE_METADATA_READONLY,
]

# ---------------------------------------------------------------------------
# Paths (all gitignored)
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parents[2]
CREDENTIALS_PATH = _ROOT / "data" / "processed" / "google_credentials.json"
TOKENS_PATH = _ROOT / "data" / "processed" / "google_tokens.json"


# ---------------------------------------------------------------------------
# Health/status
# ---------------------------------------------------------------------------


@dataclass
class ConnectorHealth:
    """Deterministic health report for one Google connector (or the whole set)."""

    connector: str  # "oauth" | "gmail" | "calendar" | "drive"
    configured: bool = False  # credentials file exists
    authorized: bool = False  # tokens exist and are not expired
    last_error: Optional[str] = None  # most recent error, never a token
    scopes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "connector": self.connector,
            "configured": self.configured,
            "authorized": self.authorized,
            "status": "live" if (self.configured and self.authorized) else "offline",
            "last_error": self.last_error,
            "scopes": self.scopes,
        }


# ---------------------------------------------------------------------------
# Token lifecycle
# ---------------------------------------------------------------------------


def credentials_exist() -> bool:
    """True if the OAuth client credentials file is present."""
    return CREDENTIALS_PATH.exists()


def tokens_exist() -> bool:
    """True if the saved user tokens file is present."""
    return TOKENS_PATH.exists()


def load_credentials():
    """Load OAuth client credentials (the developer app's ID/secret).

    Returns google.oauth2.credentials.Credentials or None if unconfigured.
    Never prints or logs the credential content.
    """
    if not credentials_exist():
        return None
    try:

        with open(CREDENTIALS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        # credentials.json from Google may have {"web": {...}} or {"installed": {...}}
        if "installed" in data:
            client_id = data["installed"].get("client_id")
            client_secret = data["installed"].get("client_secret")
        elif "web" in data:
            client_id = data["web"].get("client_id")
            client_secret = data["web"].get("client_secret")
        else:
            client_id = data.get("client_id")
            client_secret = data.get("client_secret")
        if not client_id or not client_secret:
            return None
        return {"client_id": client_id, "client_secret": client_secret}
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def load_tokens():
    """Load saved user tokens (access + refresh).

    Returns google.oauth2.credentials.Credentials or None if not authorized.
    Refreshes automatically if the access token is expired and a refresh
    token exists. Never logs token content.
    """
    if not tokens_exist():
        return None
    try:
        from google.oauth2.credentials import Credentials

        with open(TOKENS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes", []),
        )
        if creds.expired and creds.refresh_token:
            import google.auth.transport.requests

            request = google.auth.transport.requests.Request()
            creds.refresh(request)
            save_tokens(creds)  # persist the refreshed access token
        return creds
    except Exception:  # noqa: BLE001 - any credential problem = offline
        return None


def save_tokens(creds) -> None:
    """Persist user tokens to the gitignored local file. Never logs content."""
    TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or []),
    }
    with open(TOKENS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def revoke_tokens() -> bool:
    """Revoke the saved tokens at Google and delete the local file.

    The founder should also visit
    https://myaccount.google.com/permissions to confirm revocation.
    Returns True if a revocation was attempted (tokens existed).
    """
    if not tokens_exist():
        return False
    try:
        creds = load_tokens()
        if creds and creds.token:
            import google.auth.transport.requests

            request = google.auth.transport.requests.Request()
            google.oauth2.credentials.Credentials.revoke(creds, request)
    except Exception:  # noqa: BLE001 - network errors don't block local cleanup
        pass
    finally:
        TOKENS_PATH.unlink(missing_ok=True)
    return True


def check_health() -> ConnectorHealth:
    """Deterministic health check for the OAuth layer."""
    creds = load_credentials()
    tokens = load_tokens()
    return ConnectorHealth(
        connector="oauth",
        configured=creds is not None,
        authorized=tokens is not None and tokens.valid,
        scopes=ALL_SCOPES,
    )


# ---------------------------------------------------------------------------
# Authorization flow (founder-local, browser-based)
# ---------------------------------------------------------------------------


def run_authorization_flow(redirect_port: int = 8080) -> bool:
    """Run the founder-local OAuth consent flow. Opens a browser.

    Returns True if tokens were saved. The founder must have already:
    1. Downloaded credentials.json to data/processed/
    2. Added their Google account as a test user in the Cloud Console.

    Redirect URI: http://localhost:<port> (Desktop app default).
    """
    client = load_credentials()
    if not client:
        print("ERROR: No Google OAuth credentials found.")
        print(f"Expected: {CREDENTIALS_PATH}")
        print("Download credentials.json from Google Cloud Console")
        print("(OAuth 2.0 Client ID, Application type: Desktop app).")
        return False

    from google_auth_oauthlib.flow import Flow

    # Force consent to guarantee we get a refresh token
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    flow = Flow.from_client_secrets_file(
        str(CREDENTIALS_PATH),
        scopes=ALL_SCOPES,
        redirect_uri=f"http://localhost:{redirect_port}",
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline",  # request a refresh token
        prompt="consent",  # force consent (refresh token on first auth)
        include_granted_scopes="false",
    )

    print()
    print("=" * 60)
    print("GOOGLE AUTHORIZATION")
    print("=" * 60)
    print()
    print("1. Open this URL in your browser:")
    print()
    print(f"   {auth_url}")
    print()
    print("2. Authorize the requested read-only scopes:")
    for s in ALL_SCOPES:
        print(f"     - {s}")
    print()
    print(f"3. Google will redirect to http://localhost:{redirect_port}")
    print("   Copy the authorization code from the redirect URL.")
    print()

    code = input("Paste the authorization code here: ").strip()
    if not code:
        print("No code provided. Authorization cancelled.")
        return False

    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        if not creds.refresh_token:
            print("WARNING: No refresh token received. The authorization may")
            print("not survive token expiry. Re-run with prompt='consent'.")
        save_tokens(creds)
        print()
        print("Authorization successful. Tokens saved to:")
        print(f"  {TOKENS_PATH}")
        print("(This file is gitignored and will never be committed.)")
        return True
    except Exception as e:
        # Never print the token or credential content
        print(f"Authorization failed: {type(e).__name__}")
        return False
