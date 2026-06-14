from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]


class GmailOAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class GmailOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str

    @classmethod
    def from_env(cls) -> "GmailOAuthConfig":
        client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
        redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
        if not (client_id and client_secret and redirect_uri):
            raise GmailOAuthError(
                "Google OAuth is not configured. Set GOOGLE_OAUTH_CLIENT_ID, "
                "GOOGLE_OAUTH_CLIENT_SECRET, and GOOGLE_OAUTH_REDIRECT_URI."
            )
        return cls(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)


# OAuth state tokens — short-lived, in-process. The state encodes the user_id we
# expect the callback to belong to, plus a random nonce we must match on return.
_STATE_TTL_SECONDS = 600
_state_store: dict[str, tuple[float, str]] = {}


def issue_state(user_id: str) -> str:
    nonce = secrets.token_urlsafe(24)
    _state_store[nonce] = (time.monotonic() + _STATE_TTL_SECONDS, user_id)
    _gc_states()
    return nonce


def consume_state(state: str) -> str | None:
    entry = _state_store.pop(state, None)
    if not entry:
        return None
    expires_at, user_id = entry
    if time.monotonic() > expires_at:
        return None
    return user_id


def _gc_states() -> None:
    now = time.monotonic()
    for k in list(_state_store.keys()):
        if _state_store[k][0] < now:
            _state_store.pop(k, None)


def build_consent_url(config: GmailOAuthConfig, state: str) -> str:
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code(config: GmailOAuthConfig, code: str) -> dict:
    resp = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uri": config.redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if resp.status_code >= 400:
        raise GmailOAuthError(f"Token exchange failed: {resp.status_code} {resp.text}")
    return resp.json()


def refresh_access_token(config: GmailOAuthConfig, refresh_token: str) -> dict:
    resp = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "refresh_token": refresh_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    if resp.status_code >= 400:
        raise GmailOAuthError(f"Token refresh failed: {resp.status_code} {resp.text}")
    return resp.json()


def fetch_userinfo(access_token: str) -> dict:
    resp = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if resp.status_code >= 400:
        raise GmailOAuthError(f"userinfo failed: {resp.status_code} {resp.text}")
    return resp.json()


def expires_at_iso(expires_in_seconds: int | None) -> str | None:
    if not expires_in_seconds:
        return None
    dt = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in_seconds))
    return dt.isoformat()


def is_token_expired(expires_at: str | None, *, leeway_seconds: int = 60) -> bool:
    if not expires_at:
        return True
    try:
        dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) + timedelta(seconds=leeway_seconds) >= dt
