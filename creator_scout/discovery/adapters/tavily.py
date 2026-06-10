from __future__ import annotations

from creator_scout.discovery.adapters.base import AdapterError, AdapterResult
from creator_scout.discovery.compliance import assert_public_fetch_allowed
from creator_scout.discovery.http import HttpClient
from creator_scout.discovery.normalize import (
    extract_public_emails,
    infer_platform_from_url,
    normalize_handle,
)


class TavilyAdapter:
    """Query-based discovery via the Tavily Search API."""

    provider = "tavily"

    def __init__(self, api_key: str, http: HttpClient | None = None) -> None:
        if not api_key:
            raise AdapterError("TAVILY_API_KEY is required")
        self.api_key = api_key
        self.http = http or HttpClient()

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self, query: str, limit: int = 10) -> AdapterResult:
        """Search Tavily and map results to creator profile records."""
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": min(limit, 20),
            "search_depth": "basic",
            "include_answer": False,
        }
        response = self.http.post_json(
            "https://api.tavily.com/search",
            payload,
            {},
        )
        if response.status >= 400:
            raise AdapterError(f"Tavily Search error {response.status}: {response.text()[:300]}")

        body = response.json()
        records = []
        for item in body.get("results", []):
            url = item.get("url")
            if not url:
                continue
            try:
                assert_public_fetch_allowed(url)
            except Exception:
                continue

            platform = infer_platform_from_url(url)
            snippet = item.get("content") or item.get("snippet") or ""
            emails = extract_public_emails(snippet)

            record: dict = {
                "display_name": item.get("title") or url,
                "primary_niche": "creator",
                "summary": snippet[:500],
                "topics": [t.strip().lower() for t in query.split() if len(t) > 3],
                "accounts": [
                    {
                        "platform": platform.value,
                        "handle": normalize_handle(url.rstrip("/").split("/")[-1]),
                        "profile_url": url,
                        "bio": snippet[:300],
                    }
                ],
                "sources": [
                    {
                        "source_url": url,
                        "source_type": "tavily_search",
                        "confidence": 0.60,
                        "fields_found": {
                            "title": item.get("title"),
                            "snippet": snippet[:200],
                            "score": item.get("score"),
                        },
                    }
                ],
            }
            if emails:
                record["contacts"] = [
                    {
                        "contact_type": "email",
                        "value": email,
                        "source_url": url,
                        "permission_basis": "public_business_contact",
                        "confidence": 0.65,
                    }
                    for email in emails
                ]
            records.append(record)

        return AdapterResult(records=records, provider=self.provider, raw=body)

    # ------------------------------------------------------------------
    # Profile fetch (via Tavily Extract)
    # ------------------------------------------------------------------

    def fetch_profile(self, profile_url: str) -> AdapterResult:
        """Fetch and extract a creator profile page using Tavily's extract endpoint."""
        assert_public_fetch_allowed(profile_url)
        payload = {
            "api_key": self.api_key,
            "urls": [profile_url],
        }
        response = self.http.post_json(
            "https://api.tavily.com/extract",
            payload,
            {},
        )
        if response.status >= 400:
            raise AdapterError(f"Tavily Extract error {response.status}: {response.text()[:300]}")

        body = response.json()
        # Tavily extract returns {"results": [{"url": ..., "raw_content": ...}]}
        results = body.get("results", [])
        raw_content = results[0].get("raw_content", "") if results else ""
        emails = extract_public_emails(raw_content)
        platform = infer_platform_from_url(profile_url)
        record = {
            "display_name": profile_url,
            "primary_niche": "creator",
            "summary": raw_content[:500],
            "topics": [],
            "accounts": [
                {
                    "platform": platform.value,
                    "handle": normalize_handle(profile_url.rstrip("/").split("/")[-1]),
                    "profile_url": profile_url,
                    "bio": raw_content[:300],
                }
            ],
            "contacts": [
                {
                    "contact_type": "email",
                    "value": email,
                    "source_url": profile_url,
                    "permission_basis": "public_business_contact",
                    "confidence": 0.70,
                }
                for email in emails
            ],
            "sources": [
                {
                    "source_url": profile_url,
                    "source_type": "tavily_extract",
                    "confidence": 0.72,
                    "fields_found": {"emails": emails, "content_length": len(raw_content)},
                }
            ],
        }
        return AdapterResult(records=[record], provider=self.provider, source_url=profile_url, raw=body)
