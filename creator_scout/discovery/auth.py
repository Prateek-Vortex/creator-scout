from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass

from creator_scout.discovery.store import DiscoveryStore


@dataclass(slots=True)
class ApiKeyPrincipal:
    api_key_id: str
    org_id: str
    scopes: list[str]
    monthly_credit_limit: float


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def create_plain_api_key(prefix: str = "cs_live") -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def provision_api_key(
    store: DiscoveryStore,
    *,
    org_id: str,
    name: str,
    scopes: list[str] | None = None,
    monthly_credit_limit: float = 500.0,
    prefix: str = "cs_dev",
) -> tuple[str, str]:
    plain_key = create_plain_api_key(prefix)
    key_id = store.create_api_key(
        org_id=org_id,
        name=name,
        key_hash=hash_api_key(plain_key),
        scopes=scopes or ["discovery:read"],
        monthly_credit_limit=monthly_credit_limit,
    )
    return key_id, plain_key


# ── Simple in-process TTL cache for API key lookups ──────────────────────────
# Avoids a round-trip to InsForge on every HTTP request.  Cache entries expire
# after _CACHE_TTL_SECONDS so revoked keys are picked up within that window.
_CACHE_TTL_SECONDS = 300  # 5 minutes
_api_key_cache: dict[str, tuple[float, ApiKeyPrincipal | None]] = {}


def _cache_get(key_hash: str) -> tuple[bool, ApiKeyPrincipal | None]:
    """Return (hit, principal).  hit=True means a valid cached entry was found."""
    entry = _api_key_cache.get(key_hash)
    if entry is None:
        return False, None
    expires_at, principal = entry
    if time.monotonic() > expires_at:
        del _api_key_cache[key_hash]
        return False, None
    return True, principal


def _cache_set(key_hash: str, principal: ApiKeyPrincipal | None) -> None:
    _api_key_cache[key_hash] = (time.monotonic() + _CACHE_TTL_SECONDS, principal)


def authenticate_api_key(store: DiscoveryStore, api_key: str | None) -> ApiKeyPrincipal | None:
    if not api_key:
        return None
    key_hash = hash_api_key(api_key)

    hit, cached = _cache_get(key_hash)
    if hit:
        return cached

    row = store.get_api_key_by_hash(key_hash)
    if not row:
        _cache_set(key_hash, None)
        return None

    scopes = row.get("scopes") or row.get("scopes_json") or []
    if isinstance(scopes, str):
        import json
        try:
            scopes = json.loads(scopes)
        except Exception:
            scopes = [scopes]

    principal = ApiKeyPrincipal(
        api_key_id=row["id"],
        org_id=row["org_id"],
        scopes=scopes,
        monthly_credit_limit=float(row["monthly_credit_limit"]),
    )
    _cache_set(key_hash, principal)
    return principal


def assert_credit_available(store: DiscoveryStore, principal: ApiKeyPrincipal, requested: float) -> None:
    used = store.current_credit_usage(principal.org_id)
    if used + requested > principal.monthly_credit_limit:
        raise PermissionError("Monthly API credit limit exceeded")

