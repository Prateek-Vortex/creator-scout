from __future__ import annotations

import unittest

from creator_scout.discovery.ingest import creator_from_record
from creator_scout.discovery.verifier import (
    clear_stubs,
    stub_domain_resolution,
    verify_email_format_and_domain,
)


class EmailVerifierTestCase(unittest.TestCase):
    def setUp(self) -> None:
        clear_stubs()

    def tearDown(self) -> None:
        clear_stubs()

    def test_verify_email_format_validation(self) -> None:
        self.assertTrue(verify_email_format_and_domain("hello@gmail.com"))
        self.assertFalse(verify_email_format_and_domain("hello_at_gmail.com"))
        self.assertFalse(verify_email_format_and_domain("hello@"))
        self.assertFalse(verify_email_format_and_domain("@gmail.com"))
        self.assertFalse(verify_email_format_and_domain(""))

    def test_verify_email_mx_stubbing(self) -> None:
        stub_domain_resolution("invalid-domain.xyz", False)
        stub_domain_resolution("valid-domain.xyz", True)

        self.assertFalse(verify_email_format_and_domain("test@invalid-domain.xyz"))
        self.assertTrue(verify_email_format_and_domain("test@valid-domain.xyz"))

    def test_ingest_marks_invalid_emails_do_not_contact(self) -> None:
        # Stub the domain as invalid
        stub_domain_resolution("bad-domain.xyz", False)
        stub_domain_resolution("good-domain.xyz", True)

        record = {
            "display_name": "Test Creator",
            "contacts": [
                {
                    "contact_type": "email",
                    "value": "collab@bad-domain.xyz",
                    "source_url": "https://example.com",
                    "confidence": 0.9,
                },
                {
                    "contact_type": "email",
                    "value": "collab@good-domain.xyz",
                    "source_url": "https://example.com",
                    "confidence": 0.9,
                }
            ],
            "summary": "This is a summary with email check@bad-domain.xyz inside it.",
        }

        creator = creator_from_record(record)

        bad_contact = next(c for c in creator.contacts if c.value == "collab@bad-domain.xyz")
        good_contact = next(c for c in creator.contacts if c.value == "collab@good-domain.xyz")
        extracted_bad_contact = next(c for c in creator.contacts if c.value == "check@bad-domain.xyz")

        self.assertTrue(bad_contact.do_not_contact)
        self.assertEqual(bad_contact.confidence, 0.1)
        self.assertEqual(bad_contact.suppression_reason, "failed_verification")
        self.assertIsNotNone(bad_contact.suppressed_at)

        self.assertFalse(good_contact.do_not_contact)
        self.assertEqual(good_contact.confidence, 0.9)
        self.assertIsNone(good_contact.suppressed_at)

        self.assertTrue(extracted_bad_contact.do_not_contact)
        self.assertEqual(extracted_bad_contact.confidence, 0.1)
        self.assertEqual(extracted_bad_contact.suppression_reason, "failed_verification")


if __name__ == "__main__":
    unittest.main()
