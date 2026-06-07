from __future__ import annotations

from urllib.parse import urlencode

from creator_scout.discovery.adapters.base import AdapterError, AdapterResult
from creator_scout.discovery.compliance import assert_public_fetch_allowed
from creator_scout.discovery.http import HttpClient
from creator_scout.discovery.normalize import extract_public_emails, infer_platform_from_url, normalize_handle


class TinyFishAdapter:
    provider = "tinyfish"

    def __init__(self, api_key: str, http: HttpClient | None = None) -> None:
        if not api_key:
            raise AdapterError("TINYFISH_API_KEY is required")
        self.api_key = api_key
        self.http = http or HttpClient()

    def discover(self, query: str, limit: int = 10) -> AdapterResult:
        params = urlencode({"q": query, "limit": min(limit, 20)})
        response = self.http.get(
            f"https://api.search.tinyfish.ai?{params}",
            {"authorization": f"Bearer {self.api_key}"},
        )
        if response.status >= 400:
            raise AdapterError(f"TinyFish Search error {response.status}: {response.text()[:300]}")
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
            records.append(
                {
                    "display_name": item.get("title") or url,
                    "primary_niche": "creator",
                    "summary": item.get("snippet") or item.get("description", ""),
                    "topics": [query.lower()],
                    "accounts": [
                        {
                            "platform": infer_platform_from_url(url).value,
                            "handle": normalize_handle(url.rstrip("/").split("/")[-1]),
                            "profile_url": url,
                            "bio": item.get("snippet") or "",
                        }
                    ],
                    "sources": [
                        {
                            "source_url": url,
                            "source_type": "tinyfish_search",
                            "confidence": 0.65,
                            "fields_found": item,
                        }
                    ],
                }
            )
        return AdapterResult(records=records, provider=self.provider, raw=body)

    def fetch_profile(self, profile_url: str) -> AdapterResult:
        assert_public_fetch_allowed(profile_url)
        response = self.http.post_json(
            "https://api.fetch.tinyfish.ai",
            {"url": profile_url, "formats": ["markdown", "html"]},
            {"authorization": f"Bearer {self.api_key}"},
        )
        if response.status >= 400:
            raise AdapterError(f"TinyFish Fetch error {response.status}: {response.text()[:300]}")
        body = response.json()
        markdown = body.get("markdown") or body.get("data", {}).get("markdown", "")
        emails = extract_public_emails(markdown)
        record = {
            "display_name": body.get("title") or body.get("data", {}).get("title") or profile_url,
            "primary_niche": "creator",
            "summary": (body.get("description") or body.get("data", {}).get("description") or markdown[:500]),
            "topics": [],
            "accounts": [
                {
                    "platform": infer_platform_from_url(profile_url).value,
                    "handle": normalize_handle(profile_url.rstrip("/").split("/")[-1]),
                    "profile_url": profile_url,
                    "bio": markdown[:500],
                }
            ],
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
                    "source_type": "tinyfish_fetch",
                    "confidence": 0.78,
                    "fields_found": {
                        "emails": emails,
                        "title": body.get("title"),
                        "description": body.get("description"),
                    },
                }
            ],
        }
        return AdapterResult(records=[record], provider=self.provider, source_url=profile_url, raw=body)
