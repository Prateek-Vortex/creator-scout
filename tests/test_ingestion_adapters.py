from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creator_scout.discovery.adapters.base import ComplianceBlocked
from creator_scout.discovery.adapters.public_web import PublicWebAdapter
from creator_scout.discovery.adapters.youtube import YouTubeAdapter
from creator_scout.discovery.compliance import assert_public_fetch_allowed
from creator_scout.discovery.http import HttpResponse
from creator_scout.discovery.ingest import ingest_records
from creator_scout.discovery.jobs import enqueue_discovery_query_job, enqueue_refresh_job, run_job
from creator_scout.discovery.store import DiscoveryStore


class FakeHttp:
    user_agent = "CreatorScoutTest/0.1"

    def __init__(self, responses: dict[str, HttpResponse]) -> None:
        self.responses = responses
        self.requests: list[str] = []

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        self.requests.append(url)
        for key, response in self.responses.items():
            if key in url:
                return response
        return HttpResponse(status=404, body=b"{}", headers={}, url=url)


class IngestionAdapterTestCase(unittest.TestCase):
    def test_blocks_restricted_social_fetch(self) -> None:
        with self.assertRaises(ComplianceBlocked):
            assert_public_fetch_allowed("https://instagram.com/somecreator")
        with self.assertRaises(ComplianceBlocked):
            assert_public_fetch_allowed("https://www.tiktok.com/@somecreator")
        with self.assertRaises(ComplianceBlocked):
            assert_public_fetch_allowed("https://linkedin.com/in/somecreator")

    def test_public_web_adapter_extracts_creator_record(self) -> None:
        html = b"""
        <html>
          <head>
            <title>Priya Wellness Media Kit</title>
            <meta name="description" content="Yoga, fitness, wellness and UGC creator in India">
          </head>
          <body>
            <h1>Priya Wellness</h1>
            <p>Fitness and wellness creator. Business email priya@wellness.example</p>
            <a href="https://youtube.com/@priyawellness">YouTube</a>
            <a href="https://instagram.com/priyawellness">Instagram</a>
          </body>
        </html>
        """
        http = FakeHttp(
            {
                "robots.txt": HttpResponse(status=404, body=b"", headers={}, url="https://priya.example/robots.txt"),
                "media-kit": HttpResponse(status=200, body=html, headers={}, url="https://priya.example/media-kit"),
            }
        )
        result = PublicWebAdapter(http=http).fetch_profile("https://priya.example/media-kit")
        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(record["display_name"], "Priya Wellness Media Kit")
        self.assertEqual(record["contacts"][0]["value"], "priya@wellness.example")
        self.assertEqual({account["platform"] for account in record["accounts"]}, {"youtube", "instagram"})

    def test_youtube_adapter_maps_search_and_channel_response(self) -> None:
        search_body = {
            "items": [
                {
                    "snippet": {
                        "channelId": "UC123",
                        "title": "Test Creator",
                    }
                }
            ]
        }
        channels_body = {
            "items": [
                {
                    "id": "UC123",
                    "snippet": {
                        "title": "Test Creator",
                        "description": "Skincare reviews and acne routines",
                        "customUrl": "@testcreator",
                    },
                    "statistics": {
                        "subscriberCount": "12000",
                        "viewCount": "987654",
                    },
                }
            ]
        }
        http = FakeHttp(
            {
                "/search?": HttpResponse(status=200, body=json.dumps(search_body).encode(), headers={}, url=""),
                "/channels?": HttpResponse(status=200, body=json.dumps(channels_body).encode(), headers={}, url=""),
            }
        )
        result = YouTubeAdapter("fake", http=http).discover("skincare", limit=1)
        self.assertEqual(result.records[0]["display_name"], "Test Creator")
        self.assertEqual(result.records[0]["accounts"][0]["subscriber_count"], 12000)

    def test_refresh_job_can_ingest_public_web_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiscoveryStore(Path(tmp) / "jobs.sqlite3")
            try:
                job_id = enqueue_refresh_job(
                    store,
                    profile_url="https://creator.example/media-kit",
                    provider="public_web",
                    org_id="org_test",
                    api_key_id="key_test",
                )
                job = store.get_discovery_job(job_id)
                self.assertEqual(job["status"], "queued")
                self.assertEqual(job["input"]["profile_url"], "https://creator.example/media-kit")
            finally:
                store.close()

    def test_discovery_query_job_records_provider_usage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = DiscoveryStore(Path(tmp) / "query.sqlite3")
            try:
                job_id = enqueue_discovery_query_job(
                    store,
                    query="skincare India",
                    provider="fake_youtube",
                    limit=1,
                    org_id="org_test",
                    campaign_id="camp_test",
                )

                from creator_scout.discovery import jobs

                original = jobs.adapter_for_provider

                class FakeAdapter:
                    provider = "youtube"

                    def discover(self, query: str, limit: int = 10):
                        return type(
                            "Result",
                            (),
                            {
                                "provider": "youtube",
                                "records": [
                                    {
                                        "display_name": "Query Creator",
                                        "primary_niche": "skincare",
                                        "topics": ["skincare"],
                                        "accounts": [
                                            {
                                                "platform": "youtube",
                                                "handle": "querycreator",
                                                "profile_url": "https://youtube.com/@querycreator",
                                                "subscriber_count": 10000,
                                            }
                                        ],
                                        "sources": [
                                            {
                                                "source_url": "https://youtube.com/@querycreator",
                                                "source_type": "youtube_data_api",
                                                "confidence": 0.9,
                                                "fields_found": {"query": query},
                                            }
                                        ],
                                    }
                                ],
                                "source_url": None,
                            },
                        )()

                jobs.adapter_for_provider = lambda provider: FakeAdapter()
                try:
                    output = run_job(store, job_id)
                finally:
                    jobs.adapter_for_provider = original

                self.assertEqual(output["record_count"], 1)
                self.assertEqual(store.get_discovery_job(job_id)["status"], "passed")
                creator = store.find_by_profile_url("https://youtube.com/@querycreator")
                self.assertIsNotNone(creator)
                request = store.conn.execute("select * from provider_requests").fetchone()
                self.assertEqual(request["provider"], "youtube")
                self.assertEqual(request["cost_units"], 101)
                self.assertEqual(request["campaign_id"], "camp_test")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
