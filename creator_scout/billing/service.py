"""BillingService — orchestrates Dodo checkout sessions and webhook events.

Bridges the database store with the DodoBillingProvider.
"""
from __future__ import annotations

import json
import logging
import os

from creator_scout.billing.provider import (
    ACTIVATING_EVENTS,
    DEACTIVATING_EVENTS,
    BillingError,
    DodoBillingProvider,
    WebhookSignatureError,
)

logger = logging.getLogger(__name__)


class BillingService:
    def __init__(
        self,
        store,  # DiscoveryStore — avoid circular import with a duck-typed reference
        *,
        provider: DodoBillingProvider | None = None,
    ) -> None:
        self.store = store
        self.provider = provider or DodoBillingProvider()

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    def create_checkout_session(
        self,
        *,
        org_id: str,
        plan: str,
        name: str,
        email: str,
        return_url: str,
    ) -> dict:
        """Create a Dodo hosted checkout and persist the session ID.

        Returns ``{"checkout_url": "...", "session_id": "..."}``.
        """
        session = self.provider.create_checkout(
            org_id=org_id,
            plan=plan,
            name=name,
            email=email,
            return_url=return_url,
        )
        # Persist session ID on the organisation record for audit trail
        try:
            self.store.update_organization(
                org_id,
                {"dodo_checkout_session_id": session.session_id},
            )
        except Exception as exc:
            logger.warning("Could not persist checkout session ID: %s", exc)

        return {"checkout_url": session.checkout_url, "session_id": session.session_id}

    # ------------------------------------------------------------------
    # Webhook handling
    # ------------------------------------------------------------------

    def handle_webhook(
        self,
        payload_bytes: bytes,
        headers: dict[str, str],
    ) -> dict:
        """Verify a Dodo webhook and apply subscription lifecycle changes.

        Raises ``WebhookSignatureError`` when signature is invalid.
        Returns ``{"ok": True, "event_type": "<type>"}`` on success.
        """
        secret = os.environ.get("DODO_WEBHOOK_SECRET", "").strip()
        if secret:
            valid = self.provider.verify_webhook_signature(payload_bytes, headers, secret)
            if not valid:
                raise WebhookSignatureError("Invalid Dodo webhook signature")

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BillingError(f"Malformed webhook payload: {exc}") from exc

        event_type = payload.get("type", "")
        data = payload.get("data") or {}
        metadata = data.get("metadata") or {}

        org_id: str | None = metadata.get("org_id")
        subscription_id: str | None = (
            data.get("subscription_id") or data.get("id")
        )

        # Fall back to looking up the org by subscription_id when metadata is absent.
        if not org_id and subscription_id:
            org_row = self.store.get_organization_by_subscription_id(subscription_id)
            if org_row:
                org_id = org_row["id"]

        if not org_id:
            logger.warning(
                "Dodo webhook %s received but org_id could not be resolved. "
                "Payload data keys: %s",
                event_type,
                list(data.keys()),
            )
            return {"ok": True, "event_type": event_type, "org_resolved": False}

        if event_type in ACTIVATING_EVENTS:
            plan = metadata.get("plan", "starter")
            fields: dict = {"plan": plan}
            if subscription_id:
                fields["dodo_subscription_id"] = subscription_id
            self.store.update_organization(org_id, fields)
            logger.info(
                "Org %s upgraded to plan '%s' via %s (sub=%s)",
                org_id, plan, event_type, subscription_id,
            )

        elif event_type in DEACTIVATING_EVENTS:
            self.store.update_organization(
                org_id,
                {"plan": "free", "dodo_subscription_id": None},
            )
            logger.info(
                "Org %s reverted to free plan via %s (sub=%s)",
                org_id, event_type, subscription_id,
            )

        else:
            logger.debug("Dodo webhook event '%s' — no action taken.", event_type)

        return {"ok": True, "event_type": event_type, "org_id": org_id}
