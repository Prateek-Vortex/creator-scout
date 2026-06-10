"""Unit tests for TavilyAdapter and ExaAdapter."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from creator_scout.discovery.adapters.base import AdapterError, ComplianceBlocked
from creator_scout.discovery.adapters.exa import ExaAdapter
from creator_scout.discovery.adapters.factory import adapter_for_provider, choose_provider_for_query
from creator_scout.discovery.adapters.tavily import TavilyAdapter
from creator_scout.discovery.http import HttpResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeHttp:
    """Minimal HTTP stub that returns pre-configured responses by keyword."""

    def __init__(self, responses: dict[str, HttpResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def post_json(self, url: str, payload: dict, headers: dict) -> HttpResponse:
        self.calls.append((url, payload))
        for key, response in self.responses.items():
            if key in url:
                return response
        return HttpResponse(status=404, body=b"{}", headers={}, url=url)

    def get(self, url: str, headers: dict | None = None) -> HttpResponse:
        self.calls.append((url, {}))
        for key, response in self.responses.items():
            if key in url:
                return response
        return HttpResponse(status=404, body=b"{}", headers={}, url=url)


def _resp(body: dict, status: int = 200) -> HttpResponse:
    raw = json.dumps(body).encode()
    return HttpResponse(status=status, body=raw, headers={}, url="")


# ---------------------------------------------------------------------------
# TavilyAdapter tests
# ---------------------------------------------------------------------------

TAVILY_SEARCH_RESPONSE = {
    "results": [
        {
            "url": "https://myfitnessblog.example/about",
            "title": "FitLife Creator Hub",
            "content": "Hi, I'm a fitness content creator. Reach me at hello@fitlife.example for collabs.",
            "score": 0.91,
        },
        {
            # Compliance-blocked URL – should be silently skipped
            "url": "https://instagram.com/somefitnessguy",
            "title": "Instagram - somefitnessguy",
            "content": "Fitness account",
            "score": 0.80,
        },
        {
            # No URL – should be skipped
            "url": "",
            "title": "Empty",
            "content": "nothing",
        },
    ]
}

TAVILY_EXTRACT_RESPONSE = {
    "results": [
        {
            "url": "https://myfitnessblog.example/about",
            "raw_content": "Jane Doe | Fitness Coach. Contact: jane@fitlife.example",
        }
    ]
}


class TavilyAdapterDiscoverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.http = FakeHttp({"api.tavily.com/search": _resp(TAVILY_SEARCH_RESPONSE)})
        self.adapter = TavilyAdapter(api_key="test-key", http=self.http)

    def test_discover_returns_allowed_records_only(self) -> None:
        result = self.adapter.discover("fitness creator", limit=5)
        self.assertEqual(result.provider, "tavily")
        # Only 1 record passes compliance (instagram blocked, empty skipped)
        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        self.assertEqual(record["display_name"], "FitLife Creator Hub")
        self.assertEqual(record["accounts"][0]["platform"], "website")

    def test_discover_extracts_email_from_snippet(self) -> None:
        result = self.adapter.discover("fitness creator", limit=5)
        contacts = result.records[0].get("contacts", [])
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["value"], "hello@fitlife.example")

    def test_discover_sends_correct_payload(self) -> None:
        self.adapter.discover("yoga creator", limit=7)
        _url, payload = self.http.calls[0]
        self.assertEqual(payload["query"], "yoga creator")
        self.assertEqual(payload["max_results"], 7)

    def test_discover_raises_on_api_error(self) -> None:
        http = FakeHttp({"api.tavily.com/search": _resp({"error": "bad key"}, status=401)})
        adapter = TavilyAdapter(api_key="bad-key", http=http)
        with self.assertRaises(AdapterError):
            adapter.discover("fitness")

    def test_requires_api_key(self) -> None:
        with self.assertRaises(AdapterError):
            TavilyAdapter(api_key="")


class TavilyAdapterFetchProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.http = FakeHttp({"api.tavily.com/extract": _resp(TAVILY_EXTRACT_RESPONSE)})
        self.adapter = TavilyAdapter(api_key="test-key", http=self.http)

    def test_fetch_profile_extracts_email(self) -> None:
        result = self.adapter.fetch_profile("https://myfitnessblog.example/about")
        self.assertEqual(len(result.records), 1)
        record = result.records[0]
        contacts = record.get("contacts", [])
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["value"], "jane@fitlife.example")

    def test_fetch_profile_compliance_blocks_instagram(self) -> None:
        with self.assertRaises(Exception):
            self.adapter.fetch_profile("https://instagram.com/someone")

    def test_fetch_profile_source_type(self) -> None:
        result = self.adapter.fetch_profile("https://myfitnessblog.example/about")
        self.assertEqual(result.records[0]["sources"][0]["source_type"], "tavily_extract")


# ---------------------------------------------------------------------------
# ExaAdapter tests
# ---------------------------------------------------------------------------

EXA_SEARCH_RESPONSE = {
    "results": [
        {
            "url": "https://techblog.example/creator-hub",
            "title": "Tech Creator Hub",
            "text": "We build tech content. Reach us at team@techblog.example for partnerships.",
            "score": 0.88,
            "author": "Alex Tech",
            "publishedDate": "2024-01-15",
        },
        {
            # Compliance-blocked
            "url": "https://tiktok.com/@techguru",
            "title": "TikTok – techguru",
            "text": "tech content",
            "score": 0.77,
        },
    ]
}

EXA_CONTENTS_RESPONSE = {
    "results": [
        {
            "url": "https://techblog.example/creator-hub",
            "title": "Tech Creator Hub",
            "text": "Alex Tech | YouTube + Blog creator. Contact: alex@techblog.example",
            "author": "Alex Tech",
        }
    ]
}


class ExaAdapterDiscoverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.http = FakeHttp({"api.exa.ai/search": _resp(EXA_SEARCH_RESPONSE)})
        self.adapter = ExaAdapter(api_key="test-key", http=self.http)

    def test_discover_skips_compliance_blocked(self) -> None:
        result = self.adapter.discover("tech creator", limit=5)
        self.assertEqual(result.provider, "exa")
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["display_name"], "Tech Creator Hub")

    def test_discover_extracts_email_from_text(self) -> None:
        result = self.adapter.discover("tech creator", limit=5)
        contacts = result.records[0].get("contacts", [])
        self.assertEqual(contacts[0]["value"], "team@techblog.example")

    def test_discover_sends_correct_payload(self) -> None:
        self.adapter.discover("beauty vlogger", limit=12)
        _url, payload = self.http.calls[0]
        self.assertEqual(payload["query"], "beauty vlogger")
        self.assertEqual(payload["numResults"], 12)
        self.assertTrue(payload.get("useAutoprompt"))

    def test_discover_raises_on_api_error(self) -> None:
        http = FakeHttp({"api.exa.ai/search": _resp({"error": "unauthorized"}, status=401)})
        adapter = ExaAdapter(api_key="bad-key", http=http)
        with self.assertRaises(AdapterError):
            adapter.discover("creator")

    def test_requires_api_key(self) -> None:
        with self.assertRaises(AdapterError):
            ExaAdapter(api_key="")


class ExaAdapterFetchProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.http = FakeHttp({"api.exa.ai/contents": _resp(EXA_CONTENTS_RESPONSE)})
        self.adapter = ExaAdapter(api_key="test-key", http=self.http)

    def test_fetch_profile_extracts_email(self) -> None:
        result = self.adapter.fetch_profile("https://techblog.example/creator-hub")
        contacts = result.records[0].get("contacts", [])
        self.assertEqual(contacts[0]["value"], "alex@techblog.example")

    def test_fetch_profile_source_type(self) -> None:
        result = self.adapter.fetch_profile("https://techblog.example/creator-hub")
        self.assertEqual(result.records[0]["sources"][0]["source_type"], "exa_contents")

    def test_fetch_profile_compliance_blocks_tiktok(self) -> None:
        with self.assertRaises(Exception):
            self.adapter.fetch_profile("https://tiktok.com/@alextech")


# ---------------------------------------------------------------------------
# Factory registration tests
# ---------------------------------------------------------------------------

class FactoryRegistrationTest(unittest.TestCase):
    def test_adapter_for_provider_tavily(self) -> None:
        with patch.dict(os.environ, {"TAVILY_API_KEY": "some-key"}):
            adapter = adapter_for_provider("tavily")
            self.assertIsInstance(adapter, TavilyAdapter)

    def test_adapter_for_provider_exa(self) -> None:
        with patch.dict(os.environ, {"EXA_API_KEY": "some-key"}):
            adapter = adapter_for_provider("exa")
            self.assertIsInstance(adapter, ExaAdapter)

    def test_adapter_for_provider_tavily_missing_key_raises(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            # Remove key if present
            os.environ.pop("TAVILY_API_KEY", None)
            with self.assertRaises(AdapterError):
                adapter_for_provider("tavily")

    def test_adapter_for_provider_exa_missing_key_raises(self) -> None:
        os.environ.pop("EXA_API_KEY", None)
        with self.assertRaises(AdapterError):
            adapter_for_provider("exa")

    def test_choose_provider_for_query_explicit(self) -> None:
        self.assertEqual(choose_provider_for_query("tavily"), "tavily")
        self.assertEqual(choose_provider_for_query("exa"), "exa")

    def test_choose_provider_for_query_prefers_youtube(self) -> None:
        with patch.dict(os.environ, {"YOUTUBE_API_KEY": "yt", "TAVILY_API_KEY": "tv"}):
            self.assertEqual(choose_provider_for_query(), "youtube")

    def test_choose_provider_for_query_falls_back_to_tavily(self) -> None:
        env = {"TAVILY_API_KEY": "tv"}
        env_no_yt = {k: v for k, v in os.environ.items() if k != "YOUTUBE_API_KEY"}
        env_no_yt.update(env)
        with patch.dict(os.environ, env_no_yt, clear=True):
            self.assertEqual(choose_provider_for_query(), "tavily")

    def test_choose_provider_for_query_falls_back_to_exa(self) -> None:
        with patch.dict(os.environ, {"EXA_API_KEY": "ex"}, clear=True):
            self.assertEqual(choose_provider_for_query(), "exa")

    def test_choose_provider_for_query_ultimate_fallback(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(choose_provider_for_query(), "public_web")


if __name__ == "__main__":
    unittest.main()
