from __future__ import annotations

from typing import Any

from creator_scout.discovery.models import utc_now
from creator_scout.discovery.store import DiscoveryStore
from creator_scout.outreach.autosend import AutoSendClient, AutoSendConfig, AutoSendError, extract_email_id


SENDABLE_PERMISSION_BASES = {"public_business_contact"}
SEND_STATUSES = {
    "email.sent": ("sent", "sent_at"),
    "email.delivered": ("delivered", "delivered_at"),
    "email.deferred": ("deferred", None),
    "email.bounced": ("bounced", "bounced_at"),
    "email.opened": ("opened", "opened_at"),
    "email.spam_reported": ("spam_reported", "spam_reported_at"),
    "email.unsubscribed": ("unsubscribed", "unsubscribed_at"),
    "email.group_unsubscribed": ("unsubscribed", "unsubscribed_at"),
}
SUPPRESSING_EVENTS = {
    "email.bounced": "autosend_bounced",
    "email.spam_reported": "autosend_spam_reported",
    "email.unsubscribed": "autosend_unsubscribed",
    "email.group_unsubscribed": "autosend_group_unsubscribed",
}


class OutreachService:
    def __init__(
        self,
        store: DiscoveryStore,
        *,
        campaign_service: Any,
        autosend_client: AutoSendClient | None = None,
    ) -> None:
        self.store = store
        self.campaign_service = campaign_service
        self.autosend_client = autosend_client or AutoSendClient()

    def config_status(self) -> dict:
        return AutoSendConfig.from_env().public_status()

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

        contact = self._sendable_email_contact(creator_id)
        draft = campaign_creator.get("outreach_draft") or {}
        resolved_subject = _clean_subject(subject or draft.get("subject") or f"Creator collaboration with {campaign.get('brief', {}).get('brand_name') or campaign.get('brand_url')}")
        resolved_body = _clean_body(body or draft.get("body") or campaign_creator.get("recommended_pitch") or "")

        provider_response: dict | None = None
        provider_message_id: str | None = None
        status = "failed"
        error: str | None = None
        sent_at: str | None = None
        try:
            provider_response = self.autosend_client.send_email(
                to_email=contact["value"],
                to_name=creator.display_name,
                subject=resolved_subject,
                body=resolved_body,
                metadata={
                    "X-Creator-Scout-Campaign-Creator-Id": campaign_creator["id"],
                    "X-Creator-Scout-Campaign-Id": campaign_id,
                    "X-Creator-Scout-Creator-Id": creator_id,
                },
            )
            provider_message_id = extract_email_id(provider_response)
            status = "sent"
            sent_at = utc_now()
        except AutoSendError as exc:
            error = str(exc)

        message = self.store.create_outreach_message(
            campaign_creator_id=campaign_creator["id"],
            recipient_contact_id=contact.get("id"),
            recipient_email=contact["value"],
            subject=resolved_subject,
            body=resolved_body,
            provider=self.autosend_client.provider,
            provider_message_id=provider_message_id,
            provider_response=provider_response,
            status=status,
            error=error,
            unsubscribe_group_id=self.autosend_client.config.unsubscribe_group_id,
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

    def handle_autosend_webhook(self, payload: dict) -> dict:
        event_type = str(payload.get("type") or payload.get("event") or "").strip()
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        provider_message_id = (
            data.get("emailId")
            or data.get("email_id")
            or data.get("messageId")
            or data.get("message_id")
            or payload.get("emailId")
        )
        if not event_type:
            raise ValueError("webhook type is required")
        if not provider_message_id:
            return {"handled": False, "reason": "missing_email_id", "event_type": event_type}

        message = self.store.get_outreach_message_by_provider_id("autosend", str(provider_message_id))
        if not message:
            return {"handled": False, "reason": "message_not_found", "event_type": event_type}

        status, timestamp_field = SEND_STATUSES.get(event_type, (None, None))
        if not status:
            return {"handled": False, "reason": "ignored_event", "event_type": event_type}

        event_time = str(payload.get("createdAt") or payload.get("created_at") or utc_now())
        patch: dict[str, object] = {
            "status": status,
            "provider_response": payload,
        }
        if timestamp_field:
            patch[timestamp_field] = event_time
        updated = self.store.update_outreach_message(message["id"], patch)

        reason = SUPPRESSING_EVENTS.get(event_type)
        if reason:
            self.store.suppress_creator_contact(
                contact_id=message.get("recipient_contact_id"),
                email=message.get("recipient_email"),
                reason=reason,
            )

        return {
            "handled": True,
            "event_type": event_type,
            "outreach_message": updated,
            "suppressed": bool(reason),
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


def verify_webhook_signature(body_bytes: bytes, signature: str, secret: str) -> bool:
    import hashlib
    import hmac

    if not secret:
        return False
    sig = signature.strip()
    if sig.startswith("sha256="):
        sig = sig[7:]
    try:
        computed = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed.lower(), sig.lower())
    except Exception:
        return False

