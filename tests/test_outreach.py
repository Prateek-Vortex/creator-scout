from __future__ import annotations

from types import SimpleNamespace
import unittest

import requests

from creator_scout.outreach.autosend import AutoSendClient, AutoSendConfig, AutoSendError
from creator_scout.outreach.service import OutreachService


class FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._body = body or {}
        self.text = text

    def json(self) -> dict:
        return self._body


class FakeSession:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response or FakeResponse(200, {"success": True, "data": {"emailId": "email_123"}})
        self.error = error
        self.calls: list[dict] = []

    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if self.error:
            raise self.error
        return self.response


class FakeCampaignService:
    def __init__(self) -> None:
        self.updated: dict | None = None

    def get_campaign(self, campaign_id: str, org_id: str | None = None) -> dict:
        return {
            "id": campaign_id,
            "org_id": org_id,
            "brand_url": "https://brand.example",
            "brief": {"brand_name": "Glow Lab"},
        }

    def update_campaign_creator(
        self,
        campaign_id: str,
        creator_id: str,
        *,
        org_id: str | None = None,
        status: str | None = None,
        recommended_pitch: str | None = None,
        notes: str | None = None,
    ) -> dict:
        self.updated = {"campaign_id": campaign_id, "creator_id": creator_id, "status": status}
        return {
            "id": "cc_1",
            "campaign_id": campaign_id,
            "creator_id": creator_id,
            "status": status,
            "creator": None,
        }


class FakeStore:
    def __init__(self, contacts: list[dict] | None = None) -> None:
        self.contacts = contacts if contacts is not None else [valid_contact()]
        self.messages: list[dict] = []
        self.suppressed: list[dict] = []

    def get_campaign_creator(self, campaign_id: str, creator_id: str) -> dict:
        return {
            "id": "cc_1",
            "campaign_id": campaign_id,
            "creator_id": creator_id,
            "outreach_draft": {"subject": "Hello", "body": "Body"},
            "recommended_pitch": "Pitch",
        }

    def get_creator(self, creator_id: str):
        return SimpleNamespace(creator_id=creator_id, display_name="Aditi Skin Notes")

    def list_creator_contact_rows(self, creator_id: str) -> list[dict]:
        return self.contacts

    def create_outreach_message(self, **kwargs) -> dict:
        message = {"id": f"om_{len(self.messages) + 1}", **kwargs}
        self.messages.append(message)
        return message

    def get_outreach_message_by_provider_id(self, provider: str, provider_message_id: str) -> dict | None:
        for message in self.messages:
            if message.get("provider") == provider and message.get("provider_message_id") == provider_message_id:
                return message
        return None

    def update_outreach_message(self, message_id: str, fields: dict) -> dict | None:
        for message in self.messages:
            if message["id"] == message_id:
                message.update(fields)
                return message
        return None

    def suppress_creator_contact(self, **kwargs) -> int:
        self.suppressed.append(kwargs)
        return 1


class FakeAutoSendClient:
    provider = "autosend"

    def __init__(self, response: dict | None = None) -> None:
        self.config = AutoSendConfig(
            api_key="key",
            from_email="campaigns@example.com",
            from_name="Creator Scout",
            reply_to_email=None,
            unsubscribe_group_id="unsub_123",
        )
        self.response = response or {"success": True, "data": {"emailId": "email_123"}}
        self.sent: list[dict] = []

    def send_email(self, **kwargs) -> dict:
        self.sent.append(kwargs)
        return self.response


def valid_contact(**overrides) -> dict:
    contact = {
        "id": "ct_1",
        "creator_id": "creator_1",
        "contact_type": "email",
        "value": "aditi@example.com",
        "source_url": "https://creator.example/contact",
        "permission_basis": "public_business_contact",
        "do_not_contact": False,
        "suppressed_at": None,
    }
    contact.update(overrides)
    return contact


class AutoSendClientTestCase(unittest.TestCase):
    def test_sends_expected_payload(self) -> None:
        session = FakeSession()
        config = AutoSendConfig(
            api_key="secret-key",
            from_email="campaigns@example.com",
            from_name="Creator Scout",
            reply_to_email="reply@example.com",
            unsubscribe_group_id="unsub_123",
        )
        client = AutoSendClient(config=config, session=session)

        response = client.send_email(
            to_email="creator@example.com",
            to_name="Creator",
            subject="Subject",
            body="Hello\n\nBody",
        )

        self.assertEqual(response["data"]["emailId"], "email_123")
        call = session.calls[0]
        self.assertEqual(call["url"], "https://api.autosend.com/v1/mails/send")
        self.assertEqual(call["headers"]["Authorization"], "Bearer secret-key")
        self.assertEqual(call["json"]["to"]["email"], "creator@example.com")
        self.assertEqual(call["json"]["from"]["email"], "campaigns@example.com")
        self.assertEqual(call["json"]["unsubscribeGroupId"], "unsub_123")
        self.assertEqual(call["json"]["replyTo"]["email"], "reply@example.com")

    def test_redacts_secret_from_errors(self) -> None:
        session = FakeSession(error=requests.RequestException("Bearer secret-key leaked secret-key"))
        config = AutoSendConfig(
            api_key="secret-key",
            from_email="campaigns@example.com",
            from_name="Creator Scout",
            reply_to_email=None,
            unsubscribe_group_id="unsub_123",
        )
        client = AutoSendClient(config=config, session=session)

        with self.assertRaises(AutoSendError) as ctx:
            client.send_email(to_email="creator@example.com", to_name=None, subject="Subject", body="Body")

        self.assertNotIn("secret-key", str(ctx.exception))
        self.assertIn("[REDACTED]", str(ctx.exception))


class OutreachServiceTestCase(unittest.TestCase):
    def make_service(self, store: FakeStore, client: FakeAutoSendClient | AutoSendClient | None = None):
        campaign_service = FakeCampaignService()
        return OutreachService(store, campaign_service=campaign_service, autosend_client=client or FakeAutoSendClient()), campaign_service

    def test_blocks_missing_email_before_provider_send(self) -> None:
        store = FakeStore(contacts=[])
        client = FakeAutoSendClient()
        service, _ = self.make_service(store, client)

        with self.assertRaises(ValueError):
            service.send_campaign_creator_outreach("camp_1", "creator_1", org_id="org_1")

        self.assertEqual(client.sent, [])
        self.assertEqual(store.messages, [])

    def test_blocks_do_not_contact_and_suppressed_contacts(self) -> None:
        for contact in [valid_contact(do_not_contact=True), valid_contact(suppressed_at="2026-06-07T00:00:00Z")]:
            with self.subTest(contact=contact):
                store = FakeStore(contacts=[contact])
                client = FakeAutoSendClient()
                service, _ = self.make_service(store, client)

                with self.assertRaises(ValueError):
                    service.send_campaign_creator_outreach("camp_1", "creator_1", org_id="org_1")

                self.assertEqual(client.sent, [])
                self.assertEqual(store.messages, [])

    def test_missing_autosend_config_persists_failed_attempt(self) -> None:
        store = FakeStore()
        disabled_client = AutoSendClient(
            config=AutoSendConfig(
                api_key="",
                from_email="",
                from_name="Creator Scout",
                reply_to_email=None,
                unsubscribe_group_id="",
            ),
            session=FakeSession(),
        )
        service, _ = self.make_service(store, disabled_client)

        with self.assertRaises(ValueError):
            service.send_campaign_creator_outreach("camp_1", "creator_1", org_id="org_1")

        self.assertEqual(store.messages[0]["status"], "failed")
        self.assertIn("AutoSend is not configured", store.messages[0]["error"])

    def test_success_persists_message_and_marks_campaign_creator_contacted(self) -> None:
        store = FakeStore()
        client = FakeAutoSendClient()
        service, campaign_service = self.make_service(store, client)

        result = service.send_campaign_creator_outreach(
            "camp_1",
            "creator_1",
            org_id="org_1",
            subject="Custom subject",
            body="Custom body",
        )

        self.assertEqual(client.sent[0]["to_email"], "aditi@example.com")
        self.assertEqual(result["outreach_message"]["provider_message_id"], "email_123")
        self.assertEqual(result["outreach_message"]["status"], "sent")
        self.assertEqual(campaign_service.updated["status"], "contacted")

    def test_webhook_updates_statuses_and_suppression_state(self) -> None:
        event_expectations = {
            "email.sent": ("sent", False),
            "email.delivered": ("delivered", False),
            "email.bounced": ("bounced", True),
            "email.spam_reported": ("spam_reported", True),
            "email.group_unsubscribed": ("unsubscribed", True),
        }
        for event_type, (expected_status, suppresses) in event_expectations.items():
            with self.subTest(event_type=event_type):
                store = FakeStore()
                store.messages.append(
                    {
                        "id": "om_1",
                        "provider": "autosend",
                        "provider_message_id": "email_123",
                        "recipient_contact_id": "ct_1",
                        "recipient_email": "aditi@example.com",
                    }
                )
                service, _ = self.make_service(store)

                result = service.handle_autosend_webhook(
                    {
                        "type": event_type,
                        "createdAt": "2026-06-07T10:00:00.000Z",
                        "data": {"emailId": "email_123"},
                    }
                )

                self.assertTrue(result["handled"])
                self.assertEqual(store.messages[0]["status"], expected_status)
                self.assertEqual(bool(store.suppressed), suppresses)


if __name__ == "__main__":
    unittest.main()
