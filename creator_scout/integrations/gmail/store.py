from __future__ import annotations

from typing import Any

from creator_scout.discovery.models import utc_now
from creator_scout.discovery.store import DiscoveryStore
from creator_scout.integrations.crypto import decrypt, encrypt


TABLE_PATH = "/api/database/records/user_oauth_connections"
PROVIDER_GMAIL = "gmail"


class GmailConnectionStore:
    def __init__(self, store: DiscoveryStore) -> None:
        self.store = store

    def get(self, user_id: str) -> dict | None:
        rows = self.store._request(
            "GET",
            f"{TABLE_PATH}?user_id=eq.{user_id}&provider=eq.{PROVIDER_GMAIL}",
        )
        if not rows:
            return None
        row = rows[0] if isinstance(rows, list) else rows
        return _decrypt_row(row)

    def upsert(
        self,
        *,
        user_id: str,
        email: str,
        access_token: str,
        refresh_token: str,
        expires_at: str | None,
        scopes: list[str],
    ) -> dict:
        existing = self.store._request(
            "GET",
            f"{TABLE_PATH}?user_id=eq.{user_id}&provider=eq.{PROVIDER_GMAIL}",
        ) or []
        payload: dict[str, Any] = {
            "user_id": user_id,
            "provider": PROVIDER_GMAIL,
            "email": email,
            "access_token": encrypt(access_token),
            "refresh_token": encrypt(refresh_token),
            "expires_at": expires_at,
            "scopes": scopes,
            "updated_at": utc_now(),
        }
        if existing:
            row_id = existing[0]["id"]
            self.store._request(
                "PATCH",
                f"{TABLE_PATH}?id=eq.{row_id}",
                json_data=payload,
            )
            row = {**existing[0], **payload}
        else:
            inserted = self.store._request(
                "POST",
                TABLE_PATH,
                json_data=[payload],
                headers={"Prefer": "return=representation"},
            )
            row = inserted[0] if isinstance(inserted, list) and inserted else payload
        return _decrypt_row(row)

    def update_access_token(
        self,
        *,
        connection_id: str,
        access_token: str,
        expires_at: str | None,
    ) -> None:
        self.store._request(
            "PATCH",
            f"{TABLE_PATH}?id=eq.{connection_id}",
            json_data={
                "access_token": encrypt(access_token),
                "expires_at": expires_at,
                "updated_at": utc_now(),
            },
        )

    def delete(self, user_id: str) -> None:
        self.store._request(
            "DELETE",
            f"{TABLE_PATH}?user_id=eq.{user_id}&provider=eq.{PROVIDER_GMAIL}",
        )


def _decrypt_row(row: dict) -> dict:
    out = dict(row)
    if out.get("access_token"):
        try:
            out["access_token"] = decrypt(out["access_token"])
        except Exception:
            out["access_token"] = None
    if out.get("refresh_token"):
        out["refresh_token"] = decrypt(out["refresh_token"])
    return out
