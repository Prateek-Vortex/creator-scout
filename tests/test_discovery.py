from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creator_scout.discovery.auth import authenticate_api_key, provision_api_key
from creator_scout.discovery.ingest import ingest_records
from creator_scout.discovery.models import Platform
from creator_scout.discovery.search import DiscoverySearch, parse_query
from creator_scout.discovery.service import DiscoveryService
from creator_scout.discovery.store import DiscoveryStore


SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed_creators.json"


class DiscoveryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DiscoveryStore(Path(self.tmp.name) / "test.sqlite3")
        records = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        self.creator_ids = ingest_records(self.store, records)

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_ingests_seed_creators(self) -> None:
        self.assertEqual(len(self.creator_ids), 5)
        creators = self.store.all_creators()
        self.assertEqual(len(creators), 5)
        self.assertTrue(any(creator.display_name == "Aditi Skin Notes" for creator in creators))

    def test_search_ranks_relevant_skincare_creator(self) -> None:
        query = parse_query(
            {
                "text": "Indian acne safe moisturizer skincare creator",
                "platforms": ["instagram", "youtube"],
                "locations": ["India"],
                "languages": ["hi", "en"],
                "topics": ["skincare", "acne", "moisturizer"],
                "follower_min": 5000,
                "follower_max": 100000,
                "limit": 5,
            }
        )
        results, freshness, confidence = DiscoverySearch(self.store).search(query)
        self.assertGreaterEqual(confidence, 0.5)
        self.assertIn(freshness.value, {"fresh", "cached", "stale"})
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].creator.display_name, "Aditi Skin Notes")
        self.assertGreaterEqual(results[0].fit_score, 70)
        self.assertIn(Platform.INSTAGRAM, {account.platform for account in results[0].creator.accounts})

    def test_exact_profile_lookup_is_deterministic(self) -> None:
        query = parse_query({"text": "https://instagram.com/aditiskinnotes"})
        results, _, _ = DiscoverySearch(self.store).search(query)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].fit_score, 100)
        self.assertEqual(results[0].creator.display_name, "Aditi Skin Notes")

    def test_public_api_records_credit_usage(self) -> None:
        _, api_key = provision_api_key(
            self.store,
            org_id="org_test",
            name="test key",
            monthly_credit_limit=10,
        )
        principal = authenticate_api_key(self.store, api_key)
        self.assertIsNotNone(principal)

        response = DiscoveryService(self.store).search(
            {
                "text": "creator hardware gaming twitch",
                "platforms": ["twitch", "youtube"],
                "limit": 3,
            },
            principal,
        )

        self.assertEqual(response["data"][0]["creator"]["display_name"], "Mira Live Builds")
        self.assertGreater(response["meta"]["credits_used"], 0)
        usage = self.store.current_credit_usage("org_test")
        self.assertEqual(usage, response["meta"]["credits_used"])

    def test_credit_limit_blocks_expensive_request(self) -> None:
        _, api_key = provision_api_key(
            self.store,
            org_id="org_limit",
            name="limit key",
            monthly_credit_limit=0.01,
        )
        principal = authenticate_api_key(self.store, api_key)
        with self.assertRaises(PermissionError):
            DiscoveryService(self.store).search({"text": "skincare", "limit": 50}, principal)

    def test_ingest_query_endpoint_queues_job_and_charges_credit(self) -> None:
        _, api_key = provision_api_key(
            self.store,
            org_id="org_query",
            name="query key",
            monthly_credit_limit=10,
        )
        principal = authenticate_api_key(self.store, api_key)
        response = DiscoveryService(self.store).ingest_query(
            {"query": "skincare India acne routine", "provider": "youtube", "limit": 3},
            principal,
        )

        job_id = response["data"]["job_id"]
        job = self.store.get_discovery_job(job_id)
        self.assertEqual(job["job_type"], "creator_discovery_query")
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["input"]["provider"], "youtube")
        self.assertEqual(self.store.current_credit_usage("org_query"), 1.0)

    def test_job_status_and_retry_are_org_scoped(self) -> None:
        _, api_key = provision_api_key(
            self.store,
            org_id="org_jobs",
            name="jobs key",
            monthly_credit_limit=10,
        )
        principal = authenticate_api_key(self.store, api_key)
        service = DiscoveryService(self.store)
        created = service.ingest_query(
            {"query": "fitness creator", "provider": "youtube", "limit": 1},
            principal,
        )
        job_id = created["data"]["job_id"]
        self.store.mark_discovery_job_failed(job_id, "temporary failure")

        status = service.job_status(job_id, principal)
        self.assertEqual(status["data"]["status"], "failed")
        retried = service.retry_job(job_id, principal)
        self.assertEqual(retried["data"]["status"], "queued")
        self.assertIsNone(retried["data"]["error"])


if __name__ == "__main__":
    unittest.main()
