from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from creator_scout.brand.crawler import BrandCrawler
from creator_scout.brand.service import BrandScanService
from creator_scout.campaign.service import CampaignService
from creator_scout.discovery.auth import authenticate_api_key, provision_api_key
from creator_scout.discovery.http import HttpResponse
from creator_scout.discovery.ingest import ingest_records
from creator_scout.discovery.service import DiscoveryService
from creator_scout.discovery.store import DiscoveryStore


SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed_creators.json"


class FakeHttp:
    user_agent = "CreatorScoutTest/0.1"

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        if url == "https://glow.example":
            return HttpResponse(
                status=200,
                body=b"""
                <html>
                  <head>
                    <title>Glow Lab</title>
                    <meta name="description" content="Clinical skincare for acne-prone sensitive skin">
                  </head>
                  <body>
                    <h1>Acne-safe moisturizer and barrier repair serum</h1>
                    <p>Clean, dermatologist tested skincare for Indian routines.</p>
                    <a href="/products/acne-safe-moisturizer">Moisturizer</a>
                    <a href="/about">About</a>
                    <a href="/reviews">Reviews</a>
                  </body>
                </html>
                """,
                headers={},
                url=url,
            )
        if "products" in url:
            return HttpResponse(
                status=200,
                body=b"<title>Acne Safe Moisturizer</title><p>Affordable acne-safe moisturizer for sensitive skin.</p>",
                headers={},
                url=url,
            )
        if "about" in url:
            return HttpResponse(
                status=200,
                body=b"<title>About Glow Lab</title><p>Science-backed, clean, trustworthy skincare.</p>",
                headers={},
                url=url,
            )
        if "reviews" in url:
            return HttpResponse(
                status=200,
                body=b"<title>Reviews</title><p>Customers love the safe routine and honest results.</p>",
                headers={},
                url=url,
            )
        return HttpResponse(status=404, body=b"", headers={}, url=url)


class TestCrawler(BrandCrawler):
    def _robots_allowed(self, url: str) -> bool:
        return True


def fake_brand_scan_service(store: DiscoveryStore) -> BrandScanService:
    return BrandScanService(store, crawler=TestCrawler(http=FakeHttp(), max_pages=4))


class CampaignOrchestratorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.original_tinyfish_key = os.environ.pop("TINYFISH_API_KEY", None)
        self.store = DiscoveryStore(Path(self.tmp.name) / "campaign-store-arg-ignored")
        ingest_records(self.store, json.loads(SEED_PATH.read_text(encoding="utf-8")))

    def tearDown(self) -> None:
        if self.original_tinyfish_key is not None:
            os.environ["TINYFISH_API_KEY"] = self.original_tinyfish_key
        else:
            os.environ.pop("TINYFISH_API_KEY", None)
        self.store.close()
        self.tmp.cleanup()

    def test_campaign_creation_links_brand_queries_and_discovery_jobs(self) -> None:
        service = CampaignService(self.store, brand_scan_service=fake_brand_scan_service(self.store))
        result = service.create_campaign(
            "https://glow.example",
            org_id="org_campaign",
            geo="India",
            goal="ugc",
            provider="youtube",
            query_limit=2,
            per_query_limit=3,
        )

        campaign = result["campaign"]
        self.assertEqual(campaign["brief"]["category"], "skincare")
        self.assertEqual(len(result["discovery_job_ids"]), 2)
        self.assertEqual(len(campaign["jobs"]), 2)
        self.assertEqual(campaign["job_summary"]["queued"], 2)
        self.assertEqual(campaign["job_summary"]["pending"], 2)
        for job_id in result["discovery_job_ids"]:
            job = self.store.get_discovery_job(job_id)
            self.assertEqual(job["input"]["campaign_id"], campaign["id"])
            self.assertEqual(job["input"]["limit"], 3)

    def test_campaign_creation_safe_fanout_queues_youtube_and_tinyfish_when_configured(self) -> None:
        os.environ["TINYFISH_API_KEY"] = "fake-tinyfish"
        service = CampaignService(self.store, brand_scan_service=fake_brand_scan_service(self.store))
        result = service.create_campaign(
            "https://glow.example",
            org_id="org_campaign",
            geo="India",
            goal="ugc",
            provider="youtube",
            query_limit=2,
            per_query_limit=3,
            discovery_mode="safe_fanout",
            max_enrichment_urls_per_query=4,
        )

        campaign = result["campaign"]
        providers = [job["provider"] for job in campaign["jobs"]]
        self.assertEqual(len(result["discovery_job_ids"]), 4)
        self.assertEqual(providers.count("youtube"), 2)
        self.assertEqual(providers.count("tinyfish"), 2)
        tinyfish_job_id = next(job["job_id"] for job in campaign["jobs"] if job["provider"] == "tinyfish")
        tinyfish_job = self.store.get_discovery_job(tinyfish_job_id)
        self.assertEqual(tinyfish_job["input"]["max_enrichment_urls"], 4)

    def test_campaign_shortlist_ranks_existing_index_matches(self) -> None:
        service = CampaignService(self.store, brand_scan_service=fake_brand_scan_service(self.store))
        created = service.create_campaign(
            "https://glow.example",
            org_id="org_campaign",
            geo="India",
            goal="ugc",
            provider="youtube",
            query_limit=4,
        )
        campaign_id = created["campaign"]["id"]

        shortlist = service.build_shortlist(campaign_id, org_id="org_campaign", limit=5)

        self.assertIsNotNone(shortlist)
        self.assertGreaterEqual(shortlist["candidate_count"], 1)
        top = shortlist["shortlist"][0]
        self.assertEqual(top["creator"]["display_name"], "Aditi Skin Notes")
        self.assertIn(top["bucket"], {"contact_first", "review"})
        self.assertTrue(top["recommended_pitch"])
        saved_rows = self.store.list_campaign_creators(campaign_id)
        self.assertEqual(saved_rows[0]["creator_id"], top["creator_id"])
        self.assertEqual(self.store.get_campaign(campaign_id)["status"], "shortlisted")
        self.assertEqual(shortlist["job_summary"]["queued"], len(created["discovery_job_ids"]))

    def test_campaign_creator_update_and_export_persist(self) -> None:
        service = CampaignService(self.store, brand_scan_service=fake_brand_scan_service(self.store))
        created = service.create_campaign(
            "https://glow.example",
            org_id="org_campaign",
            geo="India",
            goal="ugc",
            provider="youtube",
            query_limit=2,
        )
        campaign_id = created["campaign"]["id"]
        shortlist = service.build_shortlist(campaign_id, org_id="org_campaign", limit=5)
        creator_id = shortlist["shortlist"][0]["creator_id"]

        updated = service.update_campaign_creator(
            campaign_id,
            creator_id,
            org_id="org_campaign",
            status="contacted",
            recommended_pitch="Updated pitch",
            notes="Private note",
        )

        self.assertEqual(updated["status"], "contacted")
        self.assertEqual(updated["recommended_pitch"], "Updated pitch")
        self.assertEqual(updated["notes"], "Private note")
        persisted = self.store.get_campaign_creator(campaign_id, creator_id)
        self.assertEqual(persisted["status"], "contacted")
        self.assertEqual(persisted["notes"], "Private note")

        original_upload = self.store.upload_storage_object
        self.store.upload_storage_object = lambda **kwargs: {
            "key": kwargs["key"],
            "url": f"https://exports.example/{kwargs['key']}",
        }
        try:
            export = service.export_shortlist(campaign_id, org_id="org_campaign")
        finally:
            self.store.upload_storage_object = original_upload

        self.assertEqual(export["campaign_id"], campaign_id)
        self.assertEqual(export["row_count"], len(shortlist["shortlist"]))
        self.assertTrue(export["storage_key"].endswith(".csv"))
        rows = self.store._request(
            "GET",
            f"/api/database/records/campaign_exports?campaign_id=eq.{campaign_id}",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["storage_key"], export["storage_key"])

    def test_campaign_api_charges_and_returns_shortlist(self) -> None:
        _, api_key = provision_api_key(
            self.store,
            org_id="org_campaign_api",
            name="campaign api key",
            monthly_credit_limit=20,
        )
        principal = authenticate_api_key(self.store, api_key)

        from creator_scout.discovery import service as service_module

        original = service_module.CampaignService

        class FakeCampaignService(CampaignService):
            def __init__(self, store: DiscoveryStore) -> None:
                super().__init__(store, brand_scan_service=fake_brand_scan_service(store))

        service_module.CampaignService = FakeCampaignService
        try:
            api = DiscoveryService(self.store)
            created = api.create_campaign(
                {
                    "brand_url": "https://glow.example",
                    "geo": "India",
                    "goal": "ugc",
                    "provider": "youtube",
                    "query_limit": 2,
                },
                principal,
            )
            campaign_id = created["data"]["campaign"]["id"]
            shortlist = api.build_campaign_shortlist(campaign_id, {"limit": 5}, principal)
        finally:
            service_module.CampaignService = original

        self.assertEqual(len(created["data"]["discovery_job_ids"]), 2)
        self.assertEqual(created["data"]["campaign"]["job_summary"]["queued"], 2)
        self.assertEqual(shortlist["data"]["shortlist"][0]["creator"]["display_name"], "Aditi Skin Notes")
        self.assertEqual(self.store.current_credit_usage("org_campaign_api"), 4.0)


if __name__ == "__main__":
    unittest.main()
