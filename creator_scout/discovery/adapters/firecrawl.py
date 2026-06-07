from __future__ import annotations

from creator_scout.discovery.adapters.base import AdapterError, AdapterResult
from creator_scout.discovery.compliance import assert_public_fetch_allowed
from creator_scout.discovery.http import HttpClient
from creator_scout.discovery.normalize import extract_public_emails, infer_platform_from_url, normalize_handle


class FirecrawlAdapter:
    provider = "firecrawl"

    def __init__(self, api_key: str, http: HttpClient | None = None) -> None:
        if not api_key:
            raise AdapterError("FIRECRAWL_API_KEY is required")
        self.api_key = api_key
        self.http = http or HttpClient()

    def discover(self, query: str, limit: int = 10) -> AdapterResult:
        raise AdapterError("FirecrawlAdapter requires explicit creator-owned URLs")

    def fetch_profile(self, profile_url: str) -> AdapterResult:
        assert_public_fetch_allowed(profile_url)
        response = self.http.post_json(
            "https://api.firecrawl.dev/v2/scrape",
            {
                "url": profile_url,
                "formats": ["markdown", "links", "metadata"],
                "onlyMainContent": True,
            },
            {"authorization": f"Bearer {self.api_key}"},
        )
        if response.status >= 400:
            raise AdapterError(f"Firecrawl error {response.status}: {response.text()[:300]}")
        body = response.json()
        data = body.get("data", body)
        markdown = data.get("markdown", "")
        metadata = data.get("metadata", {}) or {}
        links = data.get("links", []) or []
        emails = extract_public_emails(markdown)
        social_links = [link for link in links if infer_platform_from_url(str(link)) != infer_platform_from_url(profile_url)]
        accounts = [
            {
                "platform": infer_platform_from_url(str(link)).value,
                "handle": normalize_handle(str(link).rstrip("/").split("/")[-1]),
                "profile_url": str(link).split("?")[0].rstrip("/"),
                "bio": metadata.get("description", ""),
            }
            for link in social_links
            if infer_platform_from_url(str(link)).value
            in {"instagram", "tiktok", "youtube", "twitch", "x", "pinterest", "snapchat"}
        ]
        if not accounts:
            accounts = [
                {
                    "platform": "website",
                    "handle": profile_url,
                    "profile_url": profile_url,
                    "bio": metadata.get("description", ""),
                }
            ]
        record = {
            "display_name": metadata.get("title") or profile_url,
            "primary_niche": "creator",
            "summary": metadata.get("description") or markdown[:500],
            "topics": [],
            "accounts": accounts,
            "contacts": [
                {
                    "contact_type": "email",
                    "value": email,
                    "source_url": profile_url,
                    "permission_basis": "public_business_contact",
                    "confidence": 0.72,
                }
                for email in emails
            ],
            "sources": [
                {
                    "source_url": profile_url,
                    "source_type": "firecrawl_scrape",
                    "confidence": 0.78,
                    "fields_found": {
                        "title": metadata.get("title"),
                        "description": metadata.get("description"),
                        "emails": emails,
                        "links": links[:50],
                    },
                }
            ],
        }
        return AdapterResult(records=[record], provider=self.provider, source_url=profile_url, raw=body)

