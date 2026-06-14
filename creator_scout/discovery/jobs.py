from __future__ import annotations

import logging
import os
import re

from creator_scout.discovery.adapters.agent_extract import (
    AgentParseError,
    TinyFishAgentAdapter,
)
from creator_scout.discovery.adapters.base import AdapterError, ComplianceBlocked
from creator_scout.discovery.adapters.factory import adapter_for_provider, choose_provider_for_url
from creator_scout.discovery.compliance import assert_public_fetch_allowed
from creator_scout.discovery.ingest import ingest_records
from creator_scout.discovery.models import Platform
from creator_scout.discovery.normalize import infer_platform_from_url, stable_id
from creator_scout.discovery.store import DiscoveryStore

logger = logging.getLogger(__name__)

JOB_LISTICLE_EXTRACT = "listicle_extract"

_LISTICLE_TITLE_HINTS = (
    "best ",
    "top ",
    "creators",
    "influencers",
    "list of",
    "accounts to follow",
    "round-up",
    "roundup",
)
_LISTICLE_URL_NUMBER_RE = re.compile(r"/\d{1,3}-")


def enqueue_refresh_job(
    store: DiscoveryStore,
    *,
    profile_url: str | None = None,
    creator_id: str | None = None,
    provider: str | None = None,
    org_id: str | None = None,
    api_key_id: str | None = None,
    campaign_id: str | None = None,
    source_query: str | None = None,
) -> str:
    selected_provider = provider
    if not selected_provider and profile_url:
        selected_provider = choose_provider_for_url(profile_url)
    if not selected_provider:
        selected_provider = "public_web"
    return store.create_discovery_job(
        job_type="creator_refresh",
        provider=selected_provider,
        org_id=org_id,
        api_key_id=api_key_id,
        input_payload={
            "profile_url": profile_url,
            "creator_id": creator_id,
            "provider": selected_provider,
            "campaign_id": campaign_id,
            "source_query": source_query,
        },
    )


def enqueue_discovery_query_job(
    store: DiscoveryStore,
    *,
    query: str,
    provider: str = "youtube",
    limit: int = 10,
    org_id: str | None = None,
    api_key_id: str | None = None,
    campaign_id: str | None = None,
    max_enrichment_urls: int = 5,
) -> str:
    return store.create_discovery_job(
        job_type="creator_discovery_query",
        provider=provider,
        org_id=org_id,
        api_key_id=api_key_id,
        input_payload={
            "query": query,
            "provider": provider,
            "limit": limit,
            "campaign_id": campaign_id,
            "max_enrichment_urls": max_enrichment_urls,
        },
    )


def run_next_job(store: DiscoveryStore) -> dict | None:
    job = store.next_discovery_job()
    if not job:
        return None
    return run_job(store, job["id"])


def run_next_refresh_job(store: DiscoveryStore) -> dict | None:
    return run_next_job(store)


def run_job(store: DiscoveryStore, job_id: str) -> dict:
    job = store.get_discovery_job(job_id)
    if not job:
        raise KeyError(job_id)
    if job["job_type"] == "creator_refresh":
        return run_refresh_job(store, job_id)
    if job["job_type"] == "creator_discovery_query":
        return run_discovery_query_job(store, job_id)
    if job["job_type"] == JOB_LISTICLE_EXTRACT:
        return run_listicle_extract_job(store, job_id)
    raise AdapterError(f"Unsupported job type: {job['job_type']}")


def enqueue_listicle_extract_job(
    store: DiscoveryStore,
    *,
    source_url: str,
    source_title: str | None = None,
    campaign_id: str | None = None,
    org_id: str | None = None,
    api_key_id: str | None = None,
    source_query: str | None = None,
) -> str:
    return store.create_discovery_job(
        job_type=JOB_LISTICLE_EXTRACT,
        provider="tinyfish_agent",
        org_id=org_id,
        api_key_id=api_key_id,
        input_payload={
            "source_url": source_url,
            "source_title": source_title,
            "campaign_id": campaign_id,
            "source_query": source_query,
        },
    )


def run_listicle_extract_job(store: DiscoveryStore, job_id: str) -> dict:
    job = store.get_discovery_job(job_id)
    if not job:
        raise KeyError(job_id)
    store.mark_discovery_job_running(job_id)
    payload = job["input"]
    source_url = payload.get("source_url")
    source_title = payload.get("source_title")
    if not source_url:
        store.mark_discovery_job_failed(job_id, "source_url is required for listicle_extract jobs")
        raise AdapterError("source_url is required for listicle_extract jobs")
    campaign_id = payload.get("campaign_id")
    api_key = os.environ.get("TINYFISH_API_KEY", "")
    try:
        adapter = TinyFishAgentAdapter(api_key)
        result = adapter.extract_creators(source_url, source_title=source_title)
    except AgentParseError as exc:
        # Agent gave us junk — fall back to the legacy behaviour of ingesting
        # the listicle URL itself as a creator_refresh job so we don't lose the
        # signal entirely.
        logger.warning(
            "[jobs] listicle_extract %s: parse failed (%s); falling back to creator_refresh",
            source_url,
            exc,
        )
        fallback_job_id = enqueue_refresh_job(
            store,
            profile_url=source_url,
            provider=_enrichment_provider_for_url(source_url),
            org_id=job.get("org_id"),
            api_key_id=job.get("requested_by_api_key_id"),
            campaign_id=campaign_id,
            source_query=payload.get("source_query"),
        )
        output = {
            "provider": "tinyfish_agent",
            "source_url": source_url,
            "fell_back": True,
            "reason": str(exc),
            "fallback_job_id": fallback_job_id,
            "record_count": 0,
            "num_of_steps": 0,
        }
        store.mark_discovery_job_finished(job_id, output)
        return output
    except (AdapterError, ComplianceBlocked, Exception) as error:
        store.mark_discovery_job_failed(job_id, str(error))
        raise

    if not result.records:
        # Empty extraction — fall back too, but log at info level.
        logger.info(
            "[jobs] listicle_extract %s: agent returned 0 creators; falling back",
            source_url,
        )
        fallback_job_id = enqueue_refresh_job(
            store,
            profile_url=source_url,
            provider=_enrichment_provider_for_url(source_url),
            org_id=job.get("org_id"),
            api_key_id=job.get("requested_by_api_key_id"),
            campaign_id=campaign_id,
            source_query=payload.get("source_query"),
        )
        output = {
            "provider": "tinyfish_agent",
            "source_url": source_url,
            "fell_back": True,
            "reason": "empty_extraction",
            "fallback_job_id": fallback_job_id,
            "record_count": 0,
            "num_of_steps": int(result.raw.get("num_of_steps") or 0),
        }
        store.mark_discovery_job_finished(job_id, output)
        return output

    try:
        creator_ids = ingest_records(store, result.records)
    except Exception as error:  # noqa: BLE001
        store.mark_discovery_job_failed(job_id, str(error))
        raise

    _record_provider_usage(
        store,
        job=job,
        provider=result.provider,
        endpoint="extract_creators",
        request_key=source_url,
        record_count=len(result.records),
    )

    output = {
        "provider": result.provider,
        "source_url": source_url,
        "creator_ids": creator_ids,
        "record_count": len(result.records),
        "num_of_steps": int(result.raw.get("num_of_steps") or 0),
        "agent_run_id": result.raw.get("run_id"),
    }
    # NOTE: intentionally do NOT call _enqueue_search_result_enrichment_jobs
    # on the extracted records. We index handles; we do not fetch profiles
    # (which would route Instagram / TikTok URLs into compliance.py block).
    store.mark_discovery_job_finished(job_id, output)
    return output


def run_refresh_job(store: DiscoveryStore, job_id: str) -> dict:
    job = store.get_discovery_job(job_id)
    if not job:
        raise KeyError(job_id)
    store.mark_discovery_job_running(job_id)
    payload = job["input"]
    provider = payload.get("provider") or job.get("provider") or "public_web"
    try:
        adapter = adapter_for_provider(provider)
        profile_url = payload.get("profile_url")
        if not profile_url:
            raise AdapterError("profile_url is required for refresh jobs")
        result = adapter.fetch_profile(profile_url)
        creator_ids = ingest_records(store, result.records)
        _record_provider_usage(
            store,
            job=job,
            provider=result.provider,
            endpoint="fetch_profile",
            request_key=profile_url,
            record_count=len(result.records),
        )
        output = {
            "provider": result.provider,
            "source_url": result.source_url,
            "creator_ids": creator_ids,
            "record_count": len(result.records),
        }
        store.mark_discovery_job_finished(job_id, output)
        return output
    except (AdapterError, ComplianceBlocked, Exception) as error:
        store.mark_discovery_job_failed(job_id, str(error))
        raise


def run_discovery_query_job(store: DiscoveryStore, job_id: str) -> dict:
    job = store.get_discovery_job(job_id)
    if not job:
        raise KeyError(job_id)
    store.mark_discovery_job_running(job_id)
    payload = job["input"]
    provider = payload.get("provider") or job.get("provider") or "youtube"
    try:
        adapter = adapter_for_provider(provider)
        query = payload.get("query")
        if not query:
            raise AdapterError("query is required for discovery query jobs")
        limit = int(payload.get("limit", 10))
        result = adapter.discover(query, limit=limit)
        creator_ids = ingest_records(store, result.records)
        enrichment_job_ids = _enqueue_search_result_enrichment_jobs(
            store,
            records=result.records,
            job=job,
            query=query,
            provider=provider,
            max_urls=int(payload.get("max_enrichment_urls", 5)),
        )
        _record_provider_usage(
            store,
            job=job,
            provider=result.provider,
            endpoint="discover",
            request_key=f"{query}:{limit}",
            record_count=len(result.records),
        )
        output = {
            "provider": result.provider,
            "query": query,
            "creator_ids": creator_ids,
            "record_count": len(result.records),
            "enrichment_job_ids": enrichment_job_ids,
        }
        store.mark_discovery_job_finished(job_id, output)
        return output
    except (AdapterError, ComplianceBlocked, Exception) as error:
        store.mark_discovery_job_failed(job_id, str(error))
        raise


def _record_provider_usage(
    store: DiscoveryStore,
    *,
    job: dict,
    provider: str,
    endpoint: str,
    request_key: str,
    record_count: int,
) -> None:
    store.record_provider_request(
        org_id=job.get("org_id") or "system",
        provider=provider,
        endpoint=endpoint,
        request_hash=stable_id("req", provider, endpoint, request_key),
        response_status=200,
        response_summary={"record_count": record_count},
        cost_units=_provider_cost_units(provider, endpoint, record_count),
        job_id=job["id"],
        campaign_id=(job.get("input") or {}).get("campaign_id"),
    )


def _provider_cost_units(provider: str, endpoint: str, record_count: int) -> float:
    if provider == "youtube" and endpoint == "discover":
        # YouTube search.list costs 100 units; channels.list costs 1 unit.
        return 100 + max(1, record_count)
    if provider in {"tinyfish", "firecrawl"}:
        return max(1, record_count)
    if provider == "tinyfish_agent":
        # Real credit cost lives in job.output.num_of_steps; this is just a
        # coarse units count so the provider_requests log isn't zero.
        return max(1, record_count)
    return 0


def _enqueue_search_result_enrichment_jobs(
    store: DiscoveryStore,
    *,
    records: list[dict],
    job: dict,
    query: str,
    provider: str,
    max_urls: int,
) -> list[str]:
    if provider != "tinyfish" or max_urls <= 0:
        return []
    campaign_id = (job.get("input") or {}).get("campaign_id")

    agent_enabled = os.getenv("TINYFISH_AGENT_ENABLED", "true").lower() in {"1", "true", "yes"}
    max_listicles = int(os.getenv("TINYFISH_AGENT_MAX_LISTICLES_PER_QUERY", "3"))
    listicle_count = 0

    # Build (url, title) pairs so the listicle heuristic can use the source
    # title from the search-result record. Accounts entries don't carry a
    # title; only sources do.
    pairs: list[tuple[str, str | None]] = []
    for record in records:
        record_title = str(record.get("display_name") or "").strip() or None
        for account in record.get("accounts", []) or []:
            url = account.get("profile_url")
            if url:
                pairs.append((str(url), record_title))
        for source in record.get("sources", []) or []:
            url = source.get("source_url")
            if url:
                fields = source.get("fields_found") or {}
                title = (
                    str(fields.get("title"))
                    if isinstance(fields, dict) and fields.get("title")
                    else record_title
                )
                pairs.append((str(url), title))

    job_ids: list[str] = []
    seen_urls: set[str] = set()
    for url, title in pairs:
        if len(job_ids) >= max_urls:
            break
        normalized = url.split("#", 1)[0].strip().rstrip("/")
        if not normalized or normalized.lower() in seen_urls:
            continue
        seen_urls.add(normalized.lower())
        try:
            assert_public_fetch_allowed(normalized)
        except ComplianceBlocked:
            continue

        platform = infer_platform_from_url(normalized)
        if (
            agent_enabled
            and platform is Platform.WEBSITE
            and listicle_count < max_listicles
            and _looks_like_listicle(normalized, title)
        ):
            listicle_job_id = enqueue_listicle_extract_job(
                store,
                source_url=normalized,
                source_title=title,
                campaign_id=campaign_id,
                org_id=job.get("org_id"),
                api_key_id=job.get("requested_by_api_key_id"),
                source_query=query,
            )
            if campaign_id:
                store.link_campaign_job(
                    campaign_id, listicle_job_id, f"listicle:{normalized}", "tinyfish_agent"
                )
            job_ids.append(listicle_job_id)
            listicle_count += 1
            continue

        enrichment_provider = _enrichment_provider_for_url(normalized)
        refresh_job_id = enqueue_refresh_job(
            store,
            profile_url=normalized,
            provider=enrichment_provider,
            org_id=job.get("org_id"),
            api_key_id=job.get("requested_by_api_key_id"),
            campaign_id=campaign_id,
            source_query=query,
        )
        if campaign_id:
            store.link_campaign_job(campaign_id, refresh_job_id, f"enrich:{normalized}", enrichment_provider)
        job_ids.append(refresh_job_id)
    return job_ids


def _looks_like_listicle(url: str, title: str | None) -> bool:
    if title:
        lowered = title.lower()
        if any(hint in lowered for hint in _LISTICLE_TITLE_HINTS):
            return True
    if _LISTICLE_URL_NUMBER_RE.search(url):
        return True
    return False


def _enrichment_provider_for_url(url: str) -> str:
    # Route platform-specific URLs to their native API first — TinyFish Fetch
    # on a YouTube channel URL would scrape the HTML and miss subscriber_count
    # / avg_views. choose_provider_for_url already does YouTube + key check.
    platform = infer_platform_from_url(url)
    if platform is Platform.YOUTUBE and os.environ.get("YOUTUBE_API_KEY"):
        return "youtube"
    if os.environ.get("TINYFISH_API_KEY"):
        return "tinyfish"
    if os.environ.get("FIRECRAWL_API_KEY"):
        return "firecrawl"
    return choose_provider_for_url(url)


