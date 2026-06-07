from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from creator_scout.brand.crawler import BrandCrawler
from creator_scout.brand.service import BrandScanService
from creator_scout.discovery.auth import authenticate_api_key, provision_api_key
from creator_scout.discovery.http import HttpResponse
from creator_scout.discovery.service import DiscoveryService
from creator_scout.discovery.store import DiscoveryStore


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


class BrandScanTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DiscoveryStore(Path(self.tmp.name) / "brand-store-arg-ignored")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_brand_scan_extracts_brief_and_queries(self) -> None:
        service = BrandScanService(self.store, crawler=TestCrawler(http=FakeHttp(), max_pages=4))
        result = service.scan("https://glow.example", org_id="org_brand", geo="India", goal="ugc")

        brief = result["brief"]
        self.assertEqual(brief["brand_name"], "Glow Lab")
        self.assertEqual(brief["category"], "skincare")
        self.assertIn("clinical", brief["tone"])
        self.assertGreaterEqual(result["pages_crawled"], 3)
        self.assertTrue(any("skincare" in query for query in brief["search_queries"]))

        saved = self.store.get_brand(result["brand_id"])
        self.assertEqual(saved["brief"]["category"], "skincare")
        self.assertGreaterEqual(len(saved["pages"]), 3)

    def test_brand_scan_api_can_enqueue_discovery_jobs(self) -> None:
        _, api_key = provision_api_key(
            self.store,
            org_id="org_brand_api",
            name="brand api key",
            monthly_credit_limit=20,
        )
        principal = authenticate_api_key(self.store, api_key)
        service = DiscoveryService(self.store)

        # Swap in the fake crawler for deterministic testing.
        from creator_scout.discovery import service as service_module

        original = service_module.BrandScanService

        class FakeBrandScanService(BrandScanService):
            def __init__(self, store):
                super().__init__(store, crawler=TestCrawler(http=FakeHttp(), max_pages=4))

        service_module.BrandScanService = FakeBrandScanService
        try:
            response = service.scan_brand(
                {
                    "brand_url": "https://glow.example",
                    "geo": "India",
                    "goal": "ugc",
                    "enqueue_discovery": True,
                    "provider": "youtube",
                    "query_limit": 2,
                },
                principal,
            )
        finally:
            service_module.BrandScanService = original

        self.assertEqual(response["data"]["brief"]["category"], "skincare")
        self.assertEqual(len(response["data"]["discovery_job_ids"]), 2)
        self.assertEqual(self.store.current_credit_usage("org_brand_api"), 2.0)


if __name__ == "__main__":
    unittest.main()
