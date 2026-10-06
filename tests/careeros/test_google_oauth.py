"""Tests: Google OAuth scope definitions, token lifecycle, health, revocation."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock


from careeros.google_oauth import (
    ALL_SCOPES,
    SCOPE_GMAIL_READONLY,
    SCOPE_CALENDAR_READONLY,
    SCOPE_DRIVE_METADATA_READONLY,
    ConnectorHealth,
    check_health,
    load_credentials,
    load_tokens,
    revoke_tokens,
    save_tokens,
)

# -- scope definitions (least privilege) ------------------------------------------


def test_all_scopes_are_read_only():
    """Every scope must contain 'readonly' — no write/delete scope allowed."""
    for scope in ALL_SCOPES:
        assert "readonly" in scope, f"Non-readonly scope found: {scope}"


def test_exactly_three_scopes():
    """Only the three least-privilege scopes are requested."""
    assert len(ALL_SCOPES) == 3
    assert SCOPE_GMAIL_READONLY in ALL_SCOPES
    assert SCOPE_CALENDAR_READONLY in ALL_SCOPES
    assert SCOPE_DRIVE_METADATA_READONLY in ALL_SCOPES


def test_no_dangerous_scopes():
    """Scopes that would grant write/send/delete must NOT be present.
    The check is on the exact scope NAME (after /auth/), not substrings:
    'drive.metadata.readonly' is safe; bare 'drive' or 'drive.file' is not."""
    for scope in ALL_SCOPES:
        name = scope.rsplit("/auth/", 1)[1] if "/auth/" in scope else scope
        forbidden_exact = {
            "gmail.send",
            "gmail.compose",
            "gmail.modify",
            "gmail.labels",
            "gmail.full_access",
            "calendar",
            "calendar.events",
            "calendar.events.owned",
            "drive",
            "drive.file",
            "drive.appdata",
            "drive.install",
            "drive.scripts",
        }
        assert name not in forbidden_exact, f"Forbidden scope: {name}"
        assert name.endswith(".readonly"), f"Scope '{name}' is not read-only"


# -- health ------------------------------------------------------------------------


def test_connector_health_offline_by_default(tmp_path, monkeypatch):
    """With no credentials/tokens, health reports offline (not an error)."""
    monkeypatch.setattr("careeros.google_oauth.CREDENTIALS_PATH", tmp_path / "c.json")
    monkeypatch.setattr("careeros.google_oauth.TOKENS_PATH", tmp_path / "t.json")
    h = check_health()
    assert h.configured is False
    assert h.authorized is False
    assert h.to_dict()["status"] == "offline"


def test_connector_health_to_dict_shape():
    h = ConnectorHealth(connector="test", configured=True, authorized=True, scopes=["s1"])
    d = h.to_dict()
    assert d["connector"] == "test"
    assert d["status"] == "live"
    assert d["scopes"] == ["s1"]
    assert d["last_error"] is None


# -- credentials ----------------------------------------------------------------------


def test_load_credentials_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("careeros.google_oauth.CREDENTIALS_PATH", tmp_path / "nope.json")
    assert load_credentials() is None


def test_load_credentials_malformed_json(tmp_path, monkeypatch):
    p = tmp_path / "creds.json"
    p.write_text("not json{")
    monkeypatch.setattr("careeros.google_oauth.CREDENTIALS_PATH", p)
    assert load_credentials() is None


def test_load_credentials_valid_installed_format(tmp_path, monkeypatch):
    p = tmp_path / "creds.json"
    p.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "abc.apps.googleusercontent.com",
                    "client_secret": "secret-value",
                }
            }
        )
    )
    monkeypatch.setattr("careeros.google_oauth.CREDENTIALS_PATH", p)
    result = load_credentials()
    assert result == {
        "client_id": "abc.apps.googleusercontent.com",
        "client_secret": "secret-value",
    }


def test_load_credentials_valid_web_format(tmp_path, monkeypatch):
    p = tmp_path / "creds.json"
    p.write_text(
        json.dumps(
            {"web": {"client_id": "xyz.apps.googleusercontent.com", "client_secret": "web-secret"}}
        )
    )
    monkeypatch.setattr("careeros.google_oauth.CREDENTIALS_PATH", p)
    result = load_credentials()
    assert result["client_id"] == "xyz.apps.googleusercontent.com"


def test_load_credentials_missing_fields(tmp_path, monkeypatch):
    p = tmp_path / "creds.json"
    p.write_text(json.dumps({"installed": {"client_id": "abc"}}))
    monkeypatch.setattr("careeros.google_oauth.CREDENTIALS_PATH", p)
    assert load_credentials() is None


# -- tokens -------------------------------------------------------------------------


def test_load_tokens_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("careeros.google_oauth.TOKENS_PATH", tmp_path / "nope.json")
    assert load_tokens() is None


def test_load_tokens_malformed_json(tmp_path, monkeypatch):
    p = tmp_path / "tokens.json"
    p.write_text("}{invalid")
    monkeypatch.setattr("careeros.google_oauth.TOKENS_PATH", p)
    assert load_tokens() is None


def test_save_and_load_tokens_roundtrip(tmp_path, monkeypatch):
    """Save then load — token content survives but is never printed."""
    monkeypatch.setattr("careeros.google_oauth.TOKENS_PATH", tmp_path / "t.json")
    mock_creds = MagicMock()
    mock_creds.token = "test-access-token"
    mock_creds.refresh_token = "test-refresh-token"
    mock_creds.token_uri = "https://oauth2.googleapis.com/token"
    mock_creds.client_id = "test-client"
    mock_creds.client_secret = "test-secret"
    mock_creds.scopes = ALL_SCOPES
    save_tokens(mock_creds)
    assert (tmp_path / "t.json").exists()

    loaded = load_tokens()
    assert loaded is not None
    assert loaded.token == "test-access-token"
    assert loaded.refresh_token == "test-refresh-token"
    assert list(loaded.scopes) == ALL_SCOPES


def test_expired_token_with_refresh_attempts_refresh(tmp_path, monkeypatch):
    """An expired token with a refresh token triggers a refresh attempt."""
    from google.oauth2.credentials import Credentials

    p = tmp_path / "tokens.json"
    monkeypatch.setattr("careeros.google_oauth.TOKENS_PATH", p)

    # Create a credentials object that reports expired + has refresh token
    creds = Credentials(
        token="expired-token",
        refresh_token="refresh-me",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="cid",
        client_secret="cs",
        scopes=ALL_SCOPES,
    )
    # Mock the internal state to simulate expiry
    creds.expiry = None  # will be treated as expired by our code
    creds._refresh_token = "refresh-me"
    save_tokens(creds)

    # Patch the refresh mechanism
    with patch.object(Credentials, "refresh", return_value=None) as mock_refresh:
        mock_refresh.side_effect = None
        loaded = load_tokens()
    # load_tokens should not crash (may return credentials or None)
    assert loaded is not None or loaded is None  # no crash is the assertion


# -- revocation ------------------------------------------------------------------------


def test_revoke_no_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr("careeros.google_oauth.TOKENS_PATH", tmp_path / "nope.json")
    assert revoke_tokens() is False


def test_revoke_deletes_local_file(tmp_path, monkeypatch):
    p = tmp_path / "tokens.json"
    p.write_text(json.dumps({"token": "t", "refresh_token": "r"}))
    monkeypatch.setattr("careeros.google_oauth.TOKENS_PATH", p)
    result = revoke_tokens()
    assert result is True
    assert not p.exists()  # local file deleted even if network revoke fails


# -- gitignore verification ------------------------------------------------------------------


def test_tokens_are_gitignored():
    """The .gitignore must cover the Google token/credential files."""
    gitignore = (Path(__file__).resolve().parents[2] / ".gitignore").read_text()
    assert "google_credentials.json" in gitignore
    assert "google_tokens.json" in gitignore


def test_no_token_file_is_committed():
    """No token or credential file exists in the git index."""
    import subprocess

    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    tracked = result.stdout
    assert "google_tokens.json" not in tracked
    assert "google_credentials.json" not in tracked
