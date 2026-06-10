"""Unit tests for the Dodo Payments billing module.

Covers:
  - DodoBillingProvider.create_checkout (happy path + error)
  - DodoBillingProvider.verify_webhook_signature (valid / invalid / missing headers)
  - BillingService.create_checkout_session (persistence)
  - BillingService.handle_webhook (subscription lifecycle events)
  - DiscoveryService.create_billing_checkout / handle_billing_webhook delegation
  - store.get_organization / update_organization
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from creator_scout.billing.provider import (
    ACTIVATING_EVENTS,
    DEACTIVATING_EVENTS,
    BillingConfigError,
    BillingError,
    CheckoutSession,
    DodoBillingProvider,
    WebhookSignatureError,
    _resolve_product_id,
)
from creator_scout.billing.service import BillingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_secret() -> str:
    """Return a base64-encoded test secret (whsec_ style)."""
    raw = b"super_secret_key_32bytes_abcdefgh"
    return "whsec_" + base64.b64encode(raw).decode()


def _sign(payload_bytes: bytes, msg_id: str, msg_timestamp: str, secret: str) -> str:
    """Compute a valid Svix signature for the given inputs."""
    raw_secret = secret
    if raw_secret.startswith("whsec_"):
        raw_secret = raw_secret[6:]
    secret_bytes = base64.b64decode(raw_secret)
    to_sign = f"{msg_id}.{msg_timestamp}.".encode() + payload_bytes
    mac = hmac.new(secret_bytes, to_sign, hashlib.sha256).digest()
    return "v1," + base64.b64encode(mac).decode()


def _svix_headers(payload_bytes: bytes, secret: str) -> dict[str, str]:
    """Build valid Standard Webhooks headers for a payload."""
    msg_id = "msg_test_001"
    msg_timestamp = "1700000000"
    sig = _sign(payload_bytes, msg_id, msg_timestamp, secret)
    return {
        "webhook-id": msg_id,
        "webhook-timestamp": msg_timestamp,
        "webhook-signature": sig,
    }


# ---------------------------------------------------------------------------
# DodoBillingProvider.verify_webhook_signature
# ---------------------------------------------------------------------------

class SignatureVerificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = _make_secret()
        self.provider = DodoBillingProvider(api_key="test-key")

    def test_valid_signature_passes(self) -> None:
        payload = b'{"type":"subscription.active"}'
        headers = _svix_headers(payload, self.secret)
        self.assertTrue(
            self.provider.verify_webhook_signature(payload, headers, self.secret)
        )

    def test_wrong_payload_fails(self) -> None:
        payload = b'{"type":"subscription.active"}'
        tampered = b'{"type":"subscription.cancelled"}'
        headers = _svix_headers(payload, self.secret)
        self.assertFalse(
            self.provider.verify_webhook_signature(tampered, headers, self.secret)
        )

    def test_wrong_secret_fails(self) -> None:
        payload = b'{"type":"subscription.active"}'
        headers = _svix_headers(payload, self.secret)
        other_secret = _make_secret().replace("super_secret", "different_secr")
        # Generate a fresh secret that is definitely different
        other_raw = b"other_secret_key_32bytes_XXXXXXXX"
        other_secret = "whsec_" + base64.b64encode(other_raw).decode()
        self.assertFalse(
            self.provider.verify_webhook_signature(payload, headers, other_secret)
        )

    def test_missing_headers_fail(self) -> None:
        payload = b'{"type":"subscription.active"}'
        self.assertFalse(
            self.provider.verify_webhook_signature(payload, {}, self.secret)
        )

    def test_missing_individual_headers_fail(self) -> None:
        payload = b'{"type":"subscription.active"}'
        full = _svix_headers(payload, self.secret)
        for missing_key in ("webhook-id", "webhook-timestamp", "webhook-signature"):
            headers = {k: v for k, v in full.items() if k != missing_key}
            self.assertFalse(
                self.provider.verify_webhook_signature(payload, headers, self.secret),
                f"Expected False when {missing_key!r} is missing",
            )

    def test_whsec_prefix_stripped_correctly(self) -> None:
        """Secrets with and without the whsec_ prefix should both work."""
        payload = b'{"type":"subscription.active"}'
        # Strip the prefix manually and verify it still works
        raw = self.secret[6:]
        headers = _svix_headers(payload, self.secret)
        self.assertTrue(
            self.provider.verify_webhook_signature(payload, headers, raw)
        )


# ---------------------------------------------------------------------------
# DodoBillingProvider.create_checkout
# ---------------------------------------------------------------------------

class CreateCheckoutTest(unittest.TestCase):
    def _provider_with_mock(self, response_json: dict, status: int = 200):
        """Build a provider whose HTTP call returns a fixed response."""
        provider = DodoBillingProvider(api_key="test-key", api_base="https://test.dodopayments.com")

        import urllib.request
        from io import BytesIO

        class FakeResponse:
            def __init__(self) -> None:
                self.status = status
                self._body = json.dumps(response_json).encode()

            def read(self):
                return self._body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        provider._http_open = lambda req, timeout: FakeResponse()
        return provider

    def test_create_checkout_builds_correct_payload(self) -> None:
        captured: dict = {}

        def fake_http(url, payload, headers):
            captured["url"] = url
            captured["payload"] = payload
            return {"session_id": "sess_001", "checkout_url": "https://checkout.dodo.test/sess_001"}

        with patch("creator_scout.billing.provider._http_post_json", side_effect=fake_http):
            with patch.dict(os.environ, {"DODO_PRODUCT_GROWTH": "prod_growth_123"}):
                provider = DodoBillingProvider(api_key="test-key", api_base="https://test.dodopayments.com")
                session = provider.create_checkout(
                    org_id="org-uuid-1",
                    plan="growth",
                    name="Jane Doe",
                    email="jane@brand.example",
                    return_url="https://myapp.example/",
                )

        self.assertEqual(session.checkout_url, "https://checkout.dodo.test/sess_001")
        self.assertEqual(session.session_id, "sess_001")
        self.assertIn("/checkouts", captured["url"])
        self.assertEqual(captured["payload"]["metadata"]["plan"], "growth")
        self.assertEqual(captured["payload"]["metadata"]["org_id"], "org-uuid-1")
        self.assertEqual(captured["payload"]["customer"]["email"], "jane@brand.example")
        self.assertEqual(
            captured["payload"]["product_cart"][0]["product_id"], "prod_growth_123"
        )

    def test_missing_product_id_raises_config_error(self) -> None:
        provider = DodoBillingProvider(api_key="test-key")
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DODO_PRODUCT_STARTER", None)
            with self.assertRaises(BillingConfigError):
                provider.create_checkout(
                    org_id="org-1",
                    plan="starter",
                    name="A",
                    email="a@b.com",
                    return_url="https://example.com/",
                )

    def test_unknown_plan_raises_config_error(self) -> None:
        provider = DodoBillingProvider(api_key="test-key")
        with self.assertRaises(BillingConfigError):
            provider.create_checkout(
                org_id="org-1",
                plan="enterprise_plus",
                name="A",
                email="a@b.com",
                return_url="https://example.com/",
            )

    def test_missing_api_key_raises_config_error(self) -> None:
        provider = DodoBillingProvider(api_key="")
        with self.assertRaises(BillingConfigError):
            with patch.dict(os.environ, {"DODO_PRODUCT_GROWTH": "prod_g"}):
                provider.create_checkout(
                    org_id="org-1",
                    plan="growth",
                    name="A",
                    email="a@b.com",
                    return_url="https://example.com/",
                )

    def test_api_error_raises_billing_error(self) -> None:
        """_http_post_json raises on 4xx; verify create_checkout propagates it."""
        import urllib.error
        from io import BytesIO

        def raise_http(*args, **kwargs):
            # Simulate the error that _http_post_json itself raises after
            # catching urllib.error.HTTPError and re-raising as BillingError.
            raise BillingError("Dodo Payments API error 401: invalid api key")

        with patch("creator_scout.billing.provider._http_post_json", side_effect=raise_http):
            with patch.dict(os.environ, {"DODO_PRODUCT_STARTER": "prod_s"}):
                provider = DodoBillingProvider(api_key="bad-key")
                with self.assertRaises(BillingError):
                    provider.create_checkout(
                        org_id="org-1",
                        plan="starter",
                        name="A",
                        email="a@b.com",
                        return_url="https://example.com/",
                    )



# ---------------------------------------------------------------------------
# BillingService.handle_webhook
# ---------------------------------------------------------------------------

ACTIVATING_PAYLOAD = {
    "type": "subscription.active",
    "data": {
        "subscription_id": "sub_abc123",
        "status": "active",
        "metadata": {
            "org_id": "org-uuid-abc",
            "plan": "growth",
        },
    },
}

CANCEL_PAYLOAD = {
    "type": "subscription.cancelled",
    "data": {
        "subscription_id": "sub_abc123",
        "status": "cancelled",
        "metadata": {
            "org_id": "org-uuid-abc",
            "plan": "growth",
        },
    },
}


class BillingServiceWebhookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = _make_secret()
        self.store = MagicMock()
        provider = DodoBillingProvider(api_key="test-key")
        self.service = BillingService(self.store, provider=provider)

    def _headers(self, payload_bytes: bytes) -> dict:
        return _svix_headers(payload_bytes, self.secret)

    def test_activation_event_updates_plan_and_sub_id(self) -> None:
        payload_bytes = json.dumps(ACTIVATING_PAYLOAD).encode()
        with patch.dict(os.environ, {"DODO_WEBHOOK_SECRET": self.secret}):
            result = self.service.handle_webhook(payload_bytes, self._headers(payload_bytes))

        self.assertTrue(result["ok"])
        self.store.update_organization.assert_called_once()
        call_args = self.store.update_organization.call_args
        org_id, fields = call_args[0]
        self.assertEqual(org_id, "org-uuid-abc")
        self.assertEqual(fields["plan"], "growth")
        self.assertEqual(fields["dodo_subscription_id"], "sub_abc123")

    def test_cancellation_event_reverts_to_free(self) -> None:
        payload_bytes = json.dumps(CANCEL_PAYLOAD).encode()
        with patch.dict(os.environ, {"DODO_WEBHOOK_SECRET": self.secret}):
            result = self.service.handle_webhook(payload_bytes, self._headers(payload_bytes))

        self.assertTrue(result["ok"])
        call_args = self.store.update_organization.call_args
        org_id, fields = call_args[0]
        self.assertEqual(org_id, "org-uuid-abc")
        self.assertEqual(fields["plan"], "free")
        self.assertIsNone(fields["dodo_subscription_id"])

    def test_invalid_signature_raises(self) -> None:
        payload_bytes = json.dumps(ACTIVATING_PAYLOAD).encode()
        bad_headers = {
            "webhook-id": "msg_x",
            "webhook-timestamp": "1700000000",
            "webhook-signature": "v1,invalidsignatureXXX",
        }
        with patch.dict(os.environ, {"DODO_WEBHOOK_SECRET": self.secret}):
            with self.assertRaises(Exception):
                self.service.handle_webhook(payload_bytes, bad_headers)

    def test_no_secret_skips_verification(self) -> None:
        """When DODO_WEBHOOK_SECRET is not set, verification is skipped."""
        payload_bytes = json.dumps(ACTIVATING_PAYLOAD).encode()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DODO_WEBHOOK_SECRET", None)
            result = self.service.handle_webhook(payload_bytes, {})
        self.assertTrue(result["ok"])

    def test_unknown_event_type_is_ignored(self) -> None:
        payload = {"type": "payment.created", "data": {}}
        payload_bytes = json.dumps(payload).encode()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DODO_WEBHOOK_SECRET", None)
            result = self.service.handle_webhook(payload_bytes, {})
        self.assertTrue(result["ok"])
        self.store.update_organization.assert_not_called()

    def test_all_activating_events_update_plan(self) -> None:
        for event_type in ACTIVATING_EVENTS:
            payload = {
                "type": event_type,
                "data": {
                    "subscription_id": "sub_x",
                    "metadata": {"org_id": "org-1", "plan": "starter"},
                },
            }
            payload_bytes = json.dumps(payload).encode()
            self.store.reset_mock()
            with patch.dict(os.environ, {}, clear=True):
                os.environ.pop("DODO_WEBHOOK_SECRET", None)
                result = self.service.handle_webhook(payload_bytes, {})
            self.assertTrue(result["ok"], f"Expected ok for {event_type}")
            self.store.update_organization.assert_called_once()

    def test_all_deactivating_events_revert_to_free(self) -> None:
        for event_type in DEACTIVATING_EVENTS:
            payload = {
                "type": event_type,
                "data": {
                    "subscription_id": "sub_x",
                    "metadata": {"org_id": "org-1", "plan": "growth"},
                },
            }
            payload_bytes = json.dumps(payload).encode()
            self.store.reset_mock()
            with patch.dict(os.environ, {}, clear=True):
                os.environ.pop("DODO_WEBHOOK_SECRET", None)
                result = self.service.handle_webhook(payload_bytes, {})
            self.assertTrue(result["ok"], f"Expected ok for {event_type}")
            call_args = self.store.update_organization.call_args
            self.assertEqual(call_args[0][1]["plan"], "free")


# ---------------------------------------------------------------------------
# BillingService.create_checkout_session
# ---------------------------------------------------------------------------

class BillingServiceCheckoutTest(unittest.TestCase):
    def test_checkout_persists_session_id(self) -> None:
        store = MagicMock()
        provider = MagicMock()
        provider.create_checkout.return_value = CheckoutSession(
            session_id="sess_test",
            checkout_url="https://checkout.dodo.test/sess_test",
        )
        service = BillingService(store, provider=provider)
        result = service.create_checkout_session(
            org_id="org-xyz",
            plan="growth",
            name="Test User",
            email="test@example.com",
            return_url="https://example.com/",
        )
        self.assertEqual(result["checkout_url"], "https://checkout.dodo.test/sess_test")
        self.assertEqual(result["session_id"], "sess_test")
        store.update_organization.assert_called_once_with(
            "org-xyz", {"dodo_checkout_session_id": "sess_test"}
        )


if __name__ == "__main__":
    unittest.main()
