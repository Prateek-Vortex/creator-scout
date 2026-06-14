from __future__ import annotations

import re
from urllib.parse import urlencode, urlparse

from creator_scout.discovery.adapters.base import AdapterError, AdapterResult
from creator_scout.discovery.http import HttpClient


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# Canonical channel IDs look like "UC..." (24 chars total). Path components that
# match this are channels.list-able directly without spending search.list quota.
_YT_CHANNEL_ID_RE = re.compile(r"^UC[0-9A-Za-z_-]{22}$")


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
        # Three cheap paths before falling back to expensive search.list:
        #   1. URL contains /channel/UCxxx  -> channels.list?id=UCxxx (1 unit)
        #   2. URL contains /@handle        -> channels.list?forHandle=@handle (1 unit)
        #   3. fallback                     -> discover(handle) (~101 units)
        parsed = urlparse(profile_url if "://" in profile_url else f"https://{profile_url}")
        segments = [seg for seg in parsed.path.split("/") if seg]

        # /channel/UCxxx
        for i, seg in enumerate(segments):
            if seg == "channel" and i + 1 < len(segments):
                channel_id = segments[i + 1]
                if _YT_CHANNEL_ID_RE.match(channel_id):
                    records = self._records_from_channels([channel_id])
                    if records:
                        return AdapterResult(
                            records=records,
                            provider=self.provider,
                            source_url=profile_url,
                            raw={"resolved_via": "channels_list_by_id"},
                        )

        # /@handle (or a plain handle as last segment)
        handle = ""
        for seg in segments:
            if seg.startswith("@"):
                handle = seg
                break
        if not handle and segments:
            last = segments[-1]
            if not last.startswith("watch") and "=" not in last:
                handle = "@" + last.removeprefix("@")
        if handle:
            channel_id = self._channel_id_for_handle(handle)
            if channel_id:
                records = self._records_from_channels([channel_id])
                if records:
                    return AdapterResult(
                        records=records,
                        provider=self.provider,
                        source_url=profile_url,
                        raw={"resolved_via": "channels_list_by_handle"},
                    )

        # Last resort: spend the 100-unit search.list budget.
        result = self.discover(handle.removeprefix("@") or segments[-1] if segments else "", limit=1)
        result.source_url = profile_url
        return result

    def _channel_id_for_handle(self, handle: str) -> str | None:
        """Resolve a @handle to its canonical UCxxx channel_id using the cheap
        channels.list?forHandle endpoint (1 unit). Returns None on failure.
        """
        try:
            body = self._get(
                "/channels",
                {
                    "part": "id",
                    "forHandle": handle,
                    "key": self.api_key,
                },
            )
        except AdapterError:
            return None
        items = body.get("items") or []
        if not items:
            return None
        return items[0].get("id")

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

