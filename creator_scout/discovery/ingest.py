from __future__ import annotations

import sys
from typing import Any

from creator_scout.discovery.models import (
    CreatorAccount,
    CreatorContact,
    CreatorProfile,
    PermissionBasis,
    Platform,
    SourceEvidence,
    utc_now,
)
from creator_scout.discovery.normalize import (
    build_profile_url,
    creator_identity_key,
    extract_public_emails,
    infer_platform_from_url,
    normalize_handle,
)
from creator_scout.discovery.store import DiscoveryStore


def _platform(value: str | None, profile_url: str = "") -> Platform:
    if value:
        normalized = value.lower().strip()
        for platform in Platform:
            if platform.value == normalized:
                return platform
    if profile_url:
        return infer_platform_from_url(profile_url)
    return Platform.UNKNOWN


_BIGINT_MAX = 9_223_372_036_854_775_807  # max int8 / bigint
# PostgREST's schema cache may still report bigint columns as int4 after an
# ALTER TABLE until it is explicitly reloaded.  Cap at int4 max to be safe.
_INT4_MAX = 2_147_483_647  # max PostgreSQL integer (int4)


def _safe_count(value: Any) -> int | None:
    """Clamp a potentially-huge count to a safe integer range.

    PostgREST may still advertise columns as `integer` (int4) even after an
    ALTER TABLE … TYPE bigint until its schema cache is reloaded.  We clamp
    defensively to int4 max (2.1B) to avoid 22003 errors on AI-generated or
    scraped data until the schema cache refreshes.
    """
    if value is None:
        return None
    try:
        v = int(value)
        # Cap at int4 max so PostgREST never sees an out-of-range value even
        # when its cached schema still shows the column as integer rather than bigint.
        return min(v, _INT4_MAX) if v >= 0 else max(v, -_INT4_MAX - 1)
    except (TypeError, ValueError):
        return None


def creator_from_record(record: dict[str, Any]) -> CreatorProfile:
    accounts: list[CreatorAccount] = []
    for item in record.get("accounts", []):
        platform = _platform(item.get("platform"), item.get("profile_url", ""))
        handle = normalize_handle(item.get("handle") or item.get("username") or "")
        profile_url = build_profile_url(platform, handle, item.get("profile_url", ""))
        accounts.append(
            CreatorAccount(
                platform=platform,
                handle=handle,
                profile_url=profile_url,
                follower_count=_safe_count(item.get("follower_count")),
                subscriber_count=_safe_count(item.get("subscriber_count")),
                avg_views=_safe_count(item.get("avg_views")),
                engagement_rate=item.get("engagement_rate"),
                bio=item.get("bio", ""),
                last_verified_at=item.get("last_verified_at") or utc_now(),
                raw=item,
            )
        )

    sources = [
        SourceEvidence(
            source_url=source["source_url"],
            source_type=source.get("source_type", "public_web"),
            fields_found=source.get("fields_found", {}),
            confidence=float(source.get("confidence", 0.75)),
            fetched_at=source.get("fetched_at") or utc_now(),
        )
        for source in record.get("sources", [])
        if source.get("source_url")
    ]

    contacts: list[CreatorContact] = []
    for item in record.get("contacts", []):
        contact_type = item.get("contact_type", "email")
        value = item["value"].lower().strip()
        do_not_contact = bool(item.get("do_not_contact", False))
        suppressed_at = item.get("suppressed_at")
        suppression_reason = item.get("suppression_reason")
        confidence = float(item.get("confidence", 0.75))

        if contact_type == "email":
            from creator_scout.discovery.verifier import verify_email_format_and_domain
            if not verify_email_format_and_domain(value):
                do_not_contact = True
                confidence = 0.1
                suppressed_at = utc_now()
                suppression_reason = "failed_verification"

        contacts.append(
            CreatorContact(
                contact_type=contact_type,
                value=value,
                source_url=item["source_url"],
                permission_basis=PermissionBasis(item.get("permission_basis", "public_business_contact")),
                confidence=confidence,
                do_not_contact=do_not_contact,
                suppressed_at=suppressed_at,
                suppression_reason=suppression_reason,
                last_verified_at=item.get("last_verified_at") or utc_now(),
            )
        )

    public_text = "\n".join(
        [
            record.get("summary", ""),
            " ".join(record.get("topics", [])),
            *[account.bio for account in accounts],
            *[" ".join(map(str, source.fields_found.values())) for source in sources],
        ]
    )
    for email in extract_public_emails(public_text):
        email_val = email.lower().strip()
        from creator_scout.discovery.verifier import verify_email_format_and_domain
        is_valid = verify_email_format_and_domain(email_val)
        
        do_not_contact = not is_valid
        confidence = 0.6 if is_valid else 0.1
        suppressed_at = utc_now() if not is_valid else None
        suppression_reason = "failed_verification" if not is_valid else None

        source_url = sources[0].source_url if sources else (accounts[0].profile_url if accounts else "")
        contacts.append(
            CreatorContact(
                contact_type="email",
                value=email_val,
                source_url=source_url,
                permission_basis=PermissionBasis.PUBLIC_BUSINESS_CONTACT,
                confidence=confidence,
                do_not_contact=do_not_contact,
                suppressed_at=suppressed_at,
                suppression_reason=suppression_reason,
            )
        )

    profile_urls = [account.profile_url for account in accounts]
    creator_id = record.get("creator_id") or creator_identity_key(record["display_name"], profile_urls)
    return CreatorProfile(
        creator_id=creator_id,
        display_name=record["display_name"],
        primary_niche=record.get("primary_niche", "unknown"),
        location=record.get("location"),
        languages=[str(language).lower() for language in record.get("languages", [])],
        summary=record.get("summary", ""),
        topics=[str(topic).lower() for topic in record.get("topics", [])],
        accounts=accounts,
        contacts=contacts,
        sources=sources,
        updated_at=record.get("updated_at") or utc_now(),
        raw=record,
    )


def ingest_records(store: DiscoveryStore, records: list[dict[str, Any]]) -> list[str]:
    """Ingest a list of raw creator records into the store.

    Per-record errors (DB timeouts, type mismatches, FK violations) are
    logged to stderr but do NOT abort the entire batch so the worker can
    continue processing the rest of the job.
    """
    creator_ids: list[str] = []
    for record in records:
        try:
            creator = creator_from_record(record)
            store.upsert_creator(creator)
            creator_ids.append(creator.creator_id)
        except Exception as exc:  # noqa: BLE001
            name = record.get("display_name", "<unknown>")
            print(f"[ingest] WARNING: skipped creator {name!r}: {exc}", file=sys.stderr)
    return creator_ids

