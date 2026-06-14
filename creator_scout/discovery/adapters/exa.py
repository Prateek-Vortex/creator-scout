from __future__ import annotations

from creator_scout.discovery.adapters.base import AdapterError, AdapterResult
from creator_scout.discovery.compliance import assert_public_fetch_allowed
from creator_scout.discovery.http import HttpClient
from creator_scout.discovery.normalize import (
    extract_public_emails,
    infer_platform_from_url,
    normalize_handle,
)


class ExaAdapter:
    """Query-based discovery via the Exa neural search API."""

    provider = "exa"

    def __init__(self, api_key: str, http: HttpClient | None = None) -> None:
        if not api_key:
            raise AdapterError("EXA_API_KEY is required")
        self.api_key = api_key
        self.http = http or HttpClient()

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "content-type": "application/json",
        }

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self, query: str, limit: int = 10) -> AdapterResult:
        """Search Exa and map results to creator profile records.

        Uses `type: "auto"` (balanced relevance/speed) and `highlights` content
        mode per the project's Exa configuration. See
        https://docs.exa.ai/reference/search-api-guide-for-coding-agents
        """
        payload: dict = {
            "query": query,
            "numResults": min(limit, 25),
            "type": "auto",
            "contents": {
                "highlights": True,
            },
        }
        response = self.http.post_json(
            "https://api.exa.ai/search",
            payload,
            self._auth_headers,
        )
        if response.status >= 400:
            raise AdapterError(f"Exa Search error {response.status}: {response.text()[:300]}")

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
            highlights = item.get("highlights") or []
            snippet = " ".join(h for h in highlights if h)[:500] if highlights else (item.get("text") or "")[:500]
            emails = extract_public_emails(snippet)

            record: dict = {
                "display_name": item.get("title") or url,
                "primary_niche": "creator",
                "summary": snippet,
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
                        "source_type": "exa_search",
                        "confidence": 0.62,
                        "fields_found": {
                            "title": item.get("title"),
                            "author": item.get("author"),
                            "published_date": item.get("publishedDate"),
                            "score": item.get("score"),
                            "highlights": highlights,
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
    # Profile fetch (via Exa contents endpoint)
    # ------------------------------------------------------------------

    def fetch_profile(self, profile_url: str) -> AdapterResult:
        """Fetch a creator profile page using Exa's contents endpoint."""
        assert_public_fetch_allowed(profile_url)
        payload = {
            "urls": [profile_url],
            "text": {"maxCharacters": 2000},
        }
        response = self.http.post_json(
            "https://api.exa.ai/contents",
            payload,
            self._auth_headers,
        )
        if response.status >= 400:
            raise AdapterError(f"Exa Contents error {response.status}: {response.text()[:300]}")

        body = response.json()
        results = body.get("results", [])
        item = results[0] if results else {}
        text = item.get("text", "")
        emails = extract_public_emails(text)
        platform = infer_platform_from_url(profile_url)
        record = {
            "display_name": item.get("title") or profile_url,
            "primary_niche": "creator",
            "summary": text[:500],
            "topics": [],
            "accounts": [
                {
                    "platform": platform.value,
                    "handle": normalize_handle(profile_url.rstrip("/").split("/")[-1]),
                    "profile_url": profile_url,
                    "bio": text[:300],
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
                    "source_type": "exa_contents",
                    "confidence": 0.74,
                    "fields_found": {
                        "title": item.get("title"),
                        "author": item.get("author"),
                        "emails": emails,
                        "content_length": len(text),
                    },
                }
            ],
        }
        return AdapterResult(records=[record], provider=self.provider, source_url=profile_url, raw=body)
