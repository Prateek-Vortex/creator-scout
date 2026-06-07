from __future__ import annotations

from creator_scout.discovery.adapters.base import AdapterError, ComplianceBlocked
from creator_scout.discovery.adapters.factory import adapter_for_provider, choose_provider_for_url
from creator_scout.discovery.ingest import ingest_records
from creator_scout.discovery.normalize import stable_id
from creator_scout.discovery.store import DiscoveryStore


def enqueue_refresh_job(
    store: DiscoveryStore,
    *,
    profile_url: str | None = None,
    creator_id: str | None = None,
    provider: str | None = None,
    org_id: str | None = None,
    api_key_id: str | None = None,
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
    raise AdapterError(f"Unsupported job type: {job['job_type']}")


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
    return 0
