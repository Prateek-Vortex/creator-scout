from __future__ import annotations

import os
from urllib.parse import urlparse

from creator_scout.discovery.adapters.base import AdapterError, CreatorIngestionAdapter
from creator_scout.discovery.adapters.firecrawl import FirecrawlAdapter
from creator_scout.discovery.adapters.public_web import PublicWebAdapter
from creator_scout.discovery.adapters.tinyfish import TinyFishAdapter
from creator_scout.discovery.adapters.youtube import YouTubeAdapter
from creator_scout.discovery.normalize import infer_platform_from_url


def adapter_for_provider(provider: str) -> CreatorIngestionAdapter:
    provider = provider.lower()
    if provider == "youtube":
        return YouTubeAdapter(os.environ.get("YOUTUBE_API_KEY", ""))
    if provider == "tinyfish":
        return TinyFishAdapter(os.environ.get("TINYFISH_API_KEY", ""))
    if provider == "firecrawl":
        return FirecrawlAdapter(os.environ.get("FIRECRAWL_API_KEY", ""))
    if provider in {"public_web", "web"}:
        return PublicWebAdapter()
    raise AdapterError(f"Unsupported provider: {provider}")


def choose_provider_for_url(url: str) -> str:
    platform = infer_platform_from_url(url)
    if platform.value == "youtube":
        return "youtube" if os.environ.get("YOUTUBE_API_KEY") else "public_web"
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower()
    if host and not any(platform_host in host for platform_host in ("instagram.com", "tiktok.com", "linkedin.com")):
        if os.environ.get("TINYFISH_API_KEY"):
            return "tinyfish"
        if os.environ.get("FIRECRAWL_API_KEY"):
            return "firecrawl"
        return "public_web"
    return "public_web"

