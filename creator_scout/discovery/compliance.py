from __future__ import annotations

from urllib.parse import urlparse

from creator_scout.discovery.adapters.base import ComplianceBlocked


BLOCKED_FETCH_DOMAINS = {
    "instagram.com",
    "www.instagram.com",
    "tiktok.com",
    "www.tiktok.com",
    "linkedin.com",
    "www.linkedin.com",
    "facebook.com",
    "www.facebook.com",
}


LOGIN_OR_GATED_PATH_HINTS = (
    "/login",
    "/signin",
    "/sign-in",
    "/account",
    "/admin",
    "/checkout",
    "/cart",
)


def assert_public_fetch_allowed(url: str) -> None:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower()
    if host in BLOCKED_FETCH_DOMAINS or any(host.endswith(f".{domain}") for domain in BLOCKED_FETCH_DOMAINS):
        raise ComplianceBlocked(f"Blocked restricted platform fetch: {host}")
    path = parsed.path.lower()
    if any(hint in path for hint in LOGIN_OR_GATED_PATH_HINTS):
        raise ComplianceBlocked(f"Blocked gated/login-like path: {path}")

