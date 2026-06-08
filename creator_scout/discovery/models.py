from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Platform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    BLOG = "blog"
    NEWSLETTER = "newsletter"
    PODCAST = "podcast"
    TWITCH = "twitch"
    X = "x"
    PINTEREST = "pinterest"
    SNAPCHAT = "snapchat"
    REDDIT = "reddit"
    WEBSITE = "website"
    UNKNOWN = "unknown"


class Freshness(str, Enum):
    FRESH = "fresh"
    CACHED = "cached"
    STALE = "stale"
    UNKNOWN = "unknown"


class PermissionBasis(str, Enum):
    PUBLIC_BUSINESS_CONTACT = "public_business_contact"
    CREATOR_CLAIMED = "creator_claimed"
    USER_IMPORTED_WITH_ATTESTATION = "user_imported_with_attestation"
    EXISTING_RELATIONSHIP = "existing_relationship"


@dataclass(slots=True)
class SourceEvidence:
    source_url: str
    source_type: str
    fields_found: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    fetched_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class CreatorContact:
    contact_type: str
    value: str
    source_url: str
    permission_basis: PermissionBasis
    confidence: float
    do_not_contact: bool = False
    suppressed_at: str | None = None
    suppression_reason: str | None = None
    last_verified_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class CreatorAccount:
    platform: Platform
    handle: str
    profile_url: str
    follower_count: int | None = None
    subscriber_count: int | None = None
    avg_views: int | None = None
    engagement_rate: float | None = None
    bio: str = ""
    last_verified_at: str = field(default_factory=utc_now)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CreatorProfile:
    creator_id: str
    display_name: str
    primary_niche: str
    location: str | None = None
    languages: list[str] = field(default_factory=list)
    summary: str = ""
    topics: list[str] = field(default_factory=list)
    accounts: list[CreatorAccount] = field(default_factory=list)
    contacts: list[CreatorContact] = field(default_factory=list)
    sources: list[SourceEvidence] = field(default_factory=list)
    updated_at: str = field(default_factory=utc_now)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiscoveryQuery:
    text: str = ""
    platforms: list[Platform] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    follower_min: int | None = None
    follower_max: int | None = None
    limit: int = 20
    offset: int = 0


@dataclass(slots=True)
class SearchResult:
    creator: CreatorProfile
    fit_score: int
    match_reasons: list[str]
    risk_flags: list[str]
    missing_fields: list[str]
    freshness: Freshness
    confidence: float


@dataclass(slots=True)
class ApiMeta:
    request_id: str
    credits_used: float
    freshness: Freshness
    confidence: float
    sources: list[dict[str, Any]] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    next_page: str | None = None


@dataclass(slots=True)
class ApiResponse:
    data: Any
    meta: ApiMeta


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value
