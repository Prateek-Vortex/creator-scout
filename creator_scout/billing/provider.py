"""Dodo Payments billing provider.

Handles:
  - Hosted checkout session creation (POST /checkouts)
  - Webhook signature verification (Standard Webhooks / Svix format)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field


class BillingError(RuntimeError):
    pass


class BillingConfigError(BillingError):
    pass


class WebhookSignatureError(BillingError):
    pass


# Maps plan slugs to their environment-variable product IDs.
_PLAN_ENV_VARS: dict[str, str] = {
    "starter": "DODO_PRODUCT_STARTER",
    "growth": "DODO_PRODUCT_GROWTH",
    "agency": "DODO_PRODUCT_AGENCY",
}

# Dodo subscription lifecycle events
ACTIVATING_EVENTS = {
    "subscription.active",
    "subscription.renewed",
    "subscription.updated",
}
DEACTIVATING_EVENTS = {
    "subscription.cancelled",
    "subscription.expired",
    "subscription.failed",
}


@dataclass
class CheckoutSession:
    session_id: str
    checkout_url: str
    raw: dict = field(default_factory=dict)


def _resolve_product_id(plan: str) -> str:
    """Look up the Dodo product ID for a given plan slug."""
    env_var = _PLAN_ENV_VARS.get(plan.lower())
    if not env_var:
        raise BillingConfigError(
            f"Unknown plan '{plan}'. Supported plans: {', '.join(_PLAN_ENV_VARS)}"
        )
    product_id = os.environ.get(env_var, "").strip()
    if not product_id:
        raise BillingConfigError(
            f"Missing environment variable {env_var} for plan '{plan}'. "
            "Add the Dodo product ID to your .env file."
        )
    return product_id


def _http_post_json(url: str, payload: dict, headers: dict) -> dict:
    """Minimal stdlib HTTP POST helper — no external dependencies."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")[:300]
        raise BillingError(
            f"Dodo Payments API error {exc.code}: {body_text}"
        ) from exc


class DodoBillingProvider:
    """First-party Dodo Payments integration for Creator Scout subscriptions."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("DODO_PAYMENTS_API_KEY", "").strip()
        self.api_base = (
            api_base
            or os.environ.get("DODO_PAYMENTS_API_BASE", "https://test.dodopayments.com").rstrip("/")
        )

    def _auth_headers(self) -> dict:
        if not self.api_key:
            raise BillingConfigError(
                "Missing DODO_PAYMENTS_API_KEY. Add it to your .env file."
            )
        return {"Authorization": f"Bearer {self.api_key}"}

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    def create_checkout(
        self,
        *,
        org_id: str,
        plan: str,
        name: str,
        email: str,
        return_url: str,
    ) -> CheckoutSession:
        """Create a hosted Dodo Payments checkout session.

        Returns a ``CheckoutSession`` with ``session_id`` and ``checkout_url``.
        Redirect the user to ``checkout_url`` to complete payment.
        """
        product_id = _resolve_product_id(plan)
        payload = {
            "product_cart": [{"product_id": product_id, "quantity": 1}],
            "customer": {"email": email, "name": name},
            "return_url": return_url,
            "metadata": {
                "org_id": org_id,
                "plan": plan,
                "provider": "dodo",
            },
        }
        url = f"{self.api_base}/checkouts"
        body = _http_post_json(url, payload, self._auth_headers())
        session_id = body.get("session_id") or body.get("id") or ""
        checkout_url = body.get("checkout_url") or body.get("url") or ""
        if not checkout_url:
            raise BillingError(
                f"Dodo Payments response missing checkout_url. Raw: {body}"
            )
        return CheckoutSession(session_id=session_id, checkout_url=checkout_url, raw=body)

    # ------------------------------------------------------------------
    # Webhook Signature Verification (Standard Webhooks / Svix)
    # ------------------------------------------------------------------

    @staticmethod
    def verify_webhook_signature(
        payload_bytes: bytes,
        headers: dict[str, str],
        secret: str,
    ) -> bool:
        """Verify a Dodo Payments webhook using the Standard Webhooks (Svix) format.

        Headers required (case-insensitive):
          webhook-id        — unique message ID
          webhook-timestamp — Unix seconds timestamp
          webhook-signature — space-separated list of "v1,<base64sig>" entries

        The secret is a base64-encoded string, optionally prefixed with "whsec_".
        """
        # Normalise header lookup to lowercase
        hdrs = {k.lower(): v for k, v in headers.items()}
        msg_id = hdrs.get("webhook-id", "").strip()
        msg_timestamp = hdrs.get("webhook-timestamp", "").strip()
        msg_signature = hdrs.get("webhook-signature", "").strip()

        if not msg_id or not msg_timestamp or not msg_signature:
            return False

        # Decode secret
        raw_secret = secret.strip()
        if raw_secret.startswith("whsec_"):
            raw_secret = raw_secret[6:]
        try:
            secret_bytes = base64.b64decode(raw_secret)
        except Exception:
            return False

        # Build the signed content: "{msg_id}.{msg_timestamp}.{body}"
        to_sign = f"{msg_id}.{msg_timestamp}.".encode("utf-8") + payload_bytes

        # Compute expected HMAC-SHA256
        mac = hmac.new(secret_bytes, to_sign, hashlib.sha256).digest()
        expected = base64.b64encode(mac).decode("utf-8")

        # Check any signature in the (possibly space-separated) header value
        for sig in msg_signature.split(" "):
            sig = sig.strip()
            if sig.startswith("v1,"):
                sig_val = sig[3:]
                try:
                    if hmac.compare_digest(sig_val, expected):
                        return True
                except Exception:
                    continue
        return False
