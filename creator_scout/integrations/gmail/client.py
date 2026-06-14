from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Any

import requests

from creator_scout.discovery.store import DiscoveryStore
from creator_scout.integrations.gmail.oauth import (
    GmailOAuthConfig,
    GmailOAuthError,
    expires_at_iso,
    is_token_expired,
    refresh_access_token,
)
from creator_scout.integrations.gmail.store import GmailConnectionStore


GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class GmailNotConnected(PermissionError):
    """Raised when the acting user has no Gmail connection."""


class GmailSendError(RuntimeError):
    pass


class GmailClient:
    provider = "gmail"

    def __init__(self, store: DiscoveryStore) -> None:
        self.connections = GmailConnectionStore(store)

    def get_connection_status(self, user_id: str) -> dict:
        row = self.connections.get(user_id)
        if not row:
            return {
                "connected": False,
                "email": None,
                "from_email": None,
                "from_name": None,
            }
        email = row.get("email")
        return {
            "connected": True,
            "email": email,
            "from_email": email,
            "from_name": email,
        }

    def disconnect(self, user_id: str) -> None:
        self.connections.delete(user_id)

    def send_email(
        self,
        *,
        user_id: str,
        to_email: str,
        to_name: str | None,
        subject: str,
        body: str,
        headers: dict[str, str] | None = None,
    ) -> dict:
        row = self.connections.get(user_id)
        if not row:
            raise GmailNotConnected(
                "Gmail is not connected for this user. Connect your Gmail account in Settings to send outreach."
            )

        access_token = self._ensure_fresh_token(row)
        from_email = row.get("email") or ""
        raw = _build_raw_message(
            from_email=from_email,
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            body=body,
            headers=headers,
        )

        resp = requests.post(
            GMAIL_SEND_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"raw": raw},
            timeout=20,
        )
        if resp.status_code >= 400:
            raise GmailSendError(f"Gmail send failed: {resp.status_code} {resp.text}")
        return resp.json()

    def _ensure_fresh_token(self, row: dict) -> str:
        if row.get("access_token") and not is_token_expired(row.get("expires_at")):
            return row["access_token"]

        refresh_token = row.get("refresh_token")
        if not refresh_token:
            raise GmailOAuthError("Stored Gmail connection has no refresh token; reconnect required.")

        config = GmailOAuthConfig.from_env()
        token_data = refresh_access_token(config, refresh_token)
        new_access = token_data.get("access_token")
        if not new_access:
            raise GmailOAuthError("Token refresh response did not include an access_token.")
        new_expires = expires_at_iso(token_data.get("expires_in"))
        self.connections.update_access_token(
            connection_id=row["id"],
            access_token=new_access,
            expires_at=new_expires,
        )
        return new_access


def _build_raw_message(
    *,
    from_email: str,
    to_email: str,
    to_name: str | None,
    subject: str,
    body: str,
    headers: dict[str, str] | None = None,
) -> str:
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
    msg["Subject"] = subject
    if from_email:
        msg["Reply-To"] = from_email
    for k, v in (headers or {}).items():
        msg[k] = v
    msg.set_content(body)
    raw_bytes = msg.as_bytes()
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")


def extract_message_id(response: dict[str, Any]) -> str | None:
    if not isinstance(response, dict):
        return None
    msg_id = response.get("id")
    return str(msg_id) if msg_id else None
