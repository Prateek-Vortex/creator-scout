from __future__ import annotations

from urllib.parse import urlencode

from creator_scout.discovery.adapters.base import AdapterError, AdapterResult
from creator_scout.discovery.http import HttpClient


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeAdapter:
    provider = "youtube"

    def __init__(self, api_key: str, http: HttpClient | None = None) -> None:
        if not api_key:
            raise AdapterError("YOUTUBE_API_KEY is required")
        self.api_key = api_key
        self.http = http or HttpClient()

    def discover(self, query: str, limit: int = 10) -> AdapterResult:
        params = {
            "part": "snippet",
            "type": "channel",
            "q": query,
            "maxResults": min(limit, 50),
            "key": self.api_key,
        }
        search = self._get("/search", params)
        channel_ids = [
            item.get("snippet", {}).get("channelId")
            for item in search.get("items", [])
            if item.get("snippet", {}).get("channelId")
        ]
        records = self._records_from_channels(channel_ids)
        return AdapterResult(records=records, provider=self.provider, raw={"search": search})

    def fetch_profile(self, profile_url: str) -> AdapterResult:
        # YouTube Data API does not resolve every handle by URL directly in a cheap way.
        # For P0, treat the last path segment as a query and hydrate the best channel.
        handle = profile_url.rstrip("/").split("/")[-1].removeprefix("@")
        result = self.discover(handle, limit=1)
        result.source_url = profile_url
        return result

    def _records_from_channels(self, channel_ids: list[str]) -> list[dict]:
        if not channel_ids:
            return []
        channels = self._get(
            "/channels",
            {
                "part": "snippet,statistics",
                "id": ",".join(channel_ids),
                "key": self.api_key,
            },
        )
        records = []
        for item in channels.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            custom_url = snippet.get("customUrl", "").removeprefix("@")
            handle = custom_url or item["id"]
            profile_url = f"https://youtube.com/@{handle}" if custom_url else f"https://youtube.com/channel/{item['id']}"
            topics = [
                topic.lower()
                for topic in [snippet.get("title", ""), snippet.get("description", "")]
                if topic
            ]
            records.append(
                {
                    "display_name": snippet.get("title") or handle,
                    "primary_niche": "youtube creator",
                    "summary": snippet.get("description", "")[:1000],
                    "topics": topics,
                    "accounts": [
                        {
                            "platform": "youtube",
                            "handle": handle,
                            "profile_url": profile_url,
                            "subscriber_count": _int_or_none(stats.get("subscriberCount")),
                            "avg_views": _int_or_none(stats.get("viewCount")),
                            "bio": snippet.get("description", ""),
                            "provider_user_id": item["id"],
                        }
                    ],
                    "sources": [
                        {
                            "source_url": profile_url,
                            "source_type": "youtube_data_api",
                            "confidence": 0.9,
                            "fields_found": {
                                "channel_id": item["id"],
                                "title": snippet.get("title"),
                                "description": snippet.get("description"),
                                "subscriber_count": stats.get("subscriberCount"),
                            },
                        }
                    ],
                }
            )
        return records

    def _get(self, path: str, params: dict) -> dict:
        url = f"{YOUTUBE_API_BASE}{path}?{urlencode(params)}"
        response = self.http.get(url)
        if response.status >= 400:
            raise AdapterError(f"YouTube API error {response.status}: {response.text()[:300]}")
        return response.json()


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

