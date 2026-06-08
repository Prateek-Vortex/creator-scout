from __future__ import annotations

from dataclasses import dataclass
import html
import os
from typing import Any

import requests


AUTOSEND_SEND_URL = "https://api.autosend.com/v1/mails/send"


class AutoSendError(RuntimeError):
    pass


@dataclass(frozen=True)
class AutoSendConfig:
    api_key: str
    from_email: str
    from_name: str
    reply_to_email: str | None
    unsubscribe_group_id: str

    @classmethod
    def from_env(cls) -> "AutoSendConfig":
        api_key = os.environ.get("AUTOSEND_API_KEY", "").strip()
        from_email = os.environ.get("AUTOSEND_FROM_EMAIL", "").strip()
        from_name = os.environ.get("AUTOSEND_FROM_NAME", "Creator Scout").strip() or "Creator Scout"
        reply_to_email = os.environ.get("AUTOSEND_REPLY_TO_EMAIL", "").strip() or None
        unsubscribe_group_id = os.environ.get("AUTOSEND_UNSUBSCRIBE_GROUP_ID", "").strip()
        return cls(
            api_key=api_key,
            from_email=from_email,
            from_name=from_name,
            reply_to_email=reply_to_email,
            unsubscribe_group_id=unsubscribe_group_id,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.from_email and self.unsubscribe_group_id)

    def public_status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "has_api_key": bool(self.api_key),
            "has_from_email": bool(self.from_email),
            "has_unsubscribe_group": bool(self.unsubscribe_group_id),
            "from_email": self.from_email or None,
            "from_name": self.from_name,
        }


class AutoSendClient:
    provider = "autosend"

    def __init__(self, config: AutoSendConfig | None = None, session: requests.Session | None = None) -> None:
        self.config = config or AutoSendConfig.from_env()
        self.session = session or requests.Session()

    def send_email(
        self,
        *,
        to_email: str,
        to_name: str | None,
        subject: str,
        body: str,
        metadata: dict[str, str] | None = None,
    ) -> dict:
        if not self.config.enabled:
            raise AutoSendError("AutoSend is not configured. Set AUTOSEND_API_KEY, AUTOSEND_FROM_EMAIL, and AUTOSEND_UNSUBSCRIBE_GROUP_ID.")
        payload: dict[str, Any] = {
            "to": {"email": to_email, "name": to_name or ""},
            "from": {"email": self.config.from_email, "name": self.config.from_name},
            "subject": subject,
            "text": body,
            "html": _plain_text_to_html(body),
            "unsubscribeGroupId": self.config.unsubscribe_group_id,
            "headers": {
                "X-Creator-Scout-Source": "creator-scout",
                **(metadata or {}),
            },
        }
        if self.config.reply_to_email:
            payload["replyTo"] = {"email": self.config.reply_to_email, "name": self.config.from_name}

        try:
            response = self.session.post(
                AUTOSEND_SEND_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
        except requests.RequestException as error:
            raise AutoSendError(_redact(str(error), self.config.api_key)) from error

        try:
            body_json = response.json()
        except ValueError:
            body_json = {"raw": response.text}

        if response.status_code >= 400:
            message = body_json.get("message") or body_json.get("error") or response.text
            raise AutoSendError(
                _redact(f"AutoSend request failed: {response.status_code} - {message}", self.config.api_key)
            )
        if not isinstance(body_json, dict):
            raise AutoSendError("AutoSend returned a non-object response")
        return body_json


def extract_email_id(response: dict) -> str | None:
    data = response.get("data") if isinstance(response, dict) else None
    if isinstance(data, dict):
        email_id = data.get("emailId") or data.get("email_id") or data.get("id")
        return str(email_id) if email_id else None
    email_id = response.get("emailId") or response.get("email_id") or response.get("id")
    return str(email_id) if email_id else None


def _plain_text_to_html(text: str) -> str:
    paragraphs = [html.escape(part).replace("\n", "<br>") for part in text.split("\n\n")]
    return "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs if paragraph)


def _redact(message: str, api_key: str) -> str:
    redacted = message
    if api_key:
        redacted = redacted.replace(api_key, "[REDACTED]")
    redacted = redacted.replace("Bearer ", "Bearer [REDACTED] ")
    return redacted
