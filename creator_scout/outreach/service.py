from __future__ import annotations

from typing import Any

from creator_scout.discovery.models import utc_now
from creator_scout.discovery.store import DiscoveryStore
from creator_scout.integrations.gmail.client import (
    GmailClient,
    GmailNotConnected,
    GmailSendError,
    extract_message_id,
)
from creator_scout.integrations.gmail.oauth import GmailOAuthError


SENDABLE_PERMISSION_BASES = {"public_business_contact"}


class OutreachService:
    def __init__(
        self,
        store: DiscoveryStore,
        *,
        campaign_service: Any,
        gmail_client: GmailClient | None = None,
    ) -> None:
        self.store = store
        self.campaign_service = campaign_service
        self.gmail_client = gmail_client or GmailClient(store)

    def config_status(self, *, user_id: str | None) -> dict:
        if not user_id:
            return {
                "enabled": False,
                "connected": False,
                "from_email": None,
                "from_name": None,
                "provider": "gmail",
            }
        status = self.gmail_client.get_connection_status(user_id)
        return {
            "enabled": bool(status["connected"]),
            "connected": bool(status["connected"]),
            "from_email": status["from_email"],
            "from_name": status["from_name"],
            "provider": "gmail",
        }

    def send_campaign_creator_outreach(
        self,
        campaign_id: str,
        creator_id: str,
        *,
        org_id: str | None,
        subject: str | None = None,
        body: str | None = None,
    ) -> dict | None:
        campaign = self.campaign_service.get_campaign(campaign_id, org_id=org_id)
        if not campaign:
            return None
        campaign_creator = self.store.get_campaign_creator(campaign_id, creator_id)
        if not campaign_creator:
            return None
        creator = self.store.get_creator(creator_id)
        if not creator:
            raise ValueError("Creator profile is missing")

        if not org_id:
            raise PermissionError("Authentication required to send outreach")

        contact = self._sendable_email_contact(creator_id)
        draft = campaign_creator.get("outreach_draft") or {}
        resolved_subject = _clean_subject(
            subject
            or draft.get("subject")
            or f"Creator collaboration with {campaign.get('brief', {}).get('brand_name') or campaign.get('brand_url')}"
        )
        resolved_body = _clean_body(
            body or draft.get("body") or campaign_creator.get("recommended_pitch") or ""
        )

        provider_response: dict | None = None
        provider_message_id: str | None = None
        status = "failed"
        error: str | None = None
        sent_at: str | None = None
        try:
            provider_response = self.gmail_client.send_email(
                user_id=org_id,
                to_email=contact["value"],
                to_name=creator.display_name,
                subject=resolved_subject,
                body=resolved_body,
                headers={
                    "X-Creator-Scout-Campaign-Creator-Id": campaign_creator["id"],
                    "X-Creator-Scout-Campaign-Id": campaign_id,
                    "X-Creator-Scout-Creator-Id": creator_id,
                },
            )
            provider_message_id = extract_message_id(provider_response)
            status = "sent"
            sent_at = utc_now()
        except GmailNotConnected:
            raise
        except (GmailSendError, GmailOAuthError) as exc:
            error = str(exc)

        message = self.store.create_outreach_message(
            campaign_creator_id=campaign_creator["id"],
            recipient_contact_id=contact.get("id"),
            recipient_email=contact["value"],
            subject=resolved_subject,
            body=resolved_body,
            provider=self.gmail_client.provider,
            provider_message_id=provider_message_id,
            provider_response=provider_response,
            status=status,
            error=error,
            unsubscribe_group_id=None,
            sent_at=sent_at,
        )
        if error:
            raise ValueError(error)

        updated = self.campaign_service.update_campaign_creator(
            campaign_id,
            creator_id,
            org_id=org_id,
            status="contacted",
        )
        return {
            "outreach_message": message,
            "campaign_creator": updated,
        }

    def _sendable_email_contact(self, creator_id: str) -> dict:
        rows = self.store.list_creator_contact_rows(creator_id)
        for row in rows:
            if str(row.get("contact_type") or "").lower() != "email":
                continue
            if not _looks_like_email(str(row.get("value") or "")):
                continue
            permission_basis = str(row.get("permission_basis") or "").lower()
            if permission_basis not in SENDABLE_PERMISSION_BASES:
                continue
            if bool(row.get("do_not_contact")) or row.get("suppressed_at"):
                continue
            if not row.get("source_url"):
                continue
            return row
        raise ValueError("No sendable public business email is available for this creator")


def _clean_subject(value: str) -> str:
    subject = " ".join(str(value or "").split())
    if not subject:
        raise ValueError("subject is required")
    if len(subject) > 998:
        raise ValueError("subject is too long")
    return subject


def _clean_body(value: str) -> str:
    body = str(value or "").strip()
    if not body:
        raise ValueError("body is required")
    return body


def _looks_like_email(value: str) -> bool:
    return "@" in value and "." in value.rsplit("@", 1)[-1]
