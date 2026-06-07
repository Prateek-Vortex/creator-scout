from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse, urlunparse

from creator_scout.discovery.models import Platform


TOKEN_RE = re.compile(r"[a-z0-9]+")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
STOPWORDS = {
    "a",
    "an",
    "and",
    "brand",
    "creator",
    "creators",
    "find",
    "for",
    "influencer",
    "influencers",
    "of",
    "the",
    "to",
    "with",
}


PLATFORM_DOMAINS: dict[str, Platform] = {
    "youtube.com": Platform.YOUTUBE,
    "youtu.be": Platform.YOUTUBE,
    "instagram.com": Platform.INSTAGRAM,
    "tiktok.com": Platform.TIKTOK,
    "twitch.tv": Platform.TWITCH,
    "x.com": Platform.X,
    "twitter.com": Platform.X,
    "pinterest.com": Platform.PINTEREST,
    "snapchat.com": Platform.SNAPCHAT,
    "reddit.com": Platform.REDDIT,
}


import uuid


def stable_id(prefix: str, *parts: object) -> str:
    cleaned = "|".join(str(part or "").strip().lower() for part in parts)
    name = f"{prefix}:{cleaned}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS]


def token_set(text: str) -> set[str]:
    return set(tokenize(text))


def normalize_handle(handle: str) -> str:
    handle = handle.strip()
    handle = handle.removeprefix("@")
    handle = handle.split("?")[0].split("#")[0]
    return handle.strip("/").lower()


def canonical_url(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    scheme = "https"
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    return urlunparse((scheme, host, path, "", "", ""))


def infer_platform_from_url(url: str) -> Platform:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for domain, platform in PLATFORM_DOMAINS.items():
        if host == domain or host.endswith(f".{domain}"):
            return platform
    return Platform.WEBSITE


def build_profile_url(platform: Platform, handle: str, fallback_url: str = "") -> str:
    handle = normalize_handle(handle)
    if fallback_url:
        return canonical_url(fallback_url)
    if platform == Platform.YOUTUBE:
        return f"https://youtube.com/@{handle}"
    if platform == Platform.INSTAGRAM:
        return f"https://instagram.com/{handle}"
    if platform == Platform.TIKTOK:
        return f"https://tiktok.com/@{handle}"
    if platform == Platform.TWITCH:
        return f"https://twitch.tv/{handle}"
    if platform == Platform.X:
        return f"https://x.com/{handle}"
    if platform == Platform.PINTEREST:
        return f"https://pinterest.com/{handle}"
    if platform == Platform.SNAPCHAT:
        return f"https://snapchat.com/add/{handle}"
    if platform == Platform.REDDIT:
        return f"https://reddit.com/user/{handle}"
    return canonical_url(handle)


def creator_identity_key(display_name: str, profile_urls: list[str]) -> str:
    if profile_urls:
        return stable_id("cr", *sorted(canonical_url(url) for url in profile_urls))
    return stable_id("cr", display_name)


def extract_public_emails(text: str) -> list[str]:
    # Extraction only finds visible emails in already allowed public text.
    return sorted({match.group(0).lower() for match in EMAIL_RE.finditer(text)})
