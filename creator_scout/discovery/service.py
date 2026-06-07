from __future__ import annotations

import time
from uuid import uuid4

from creator_scout.campaign.service import CampaignService
from creator_scout.discovery.auth import ApiKeyPrincipal, assert_credit_available
from creator_scout.discovery.jobs import enqueue_discovery_query_job, enqueue_refresh_job
from creator_scout.discovery.models import ApiMeta, ApiResponse, Freshness, to_jsonable
from creator_scout.discovery.search import DiscoverySearch, credit_cost_for_search, parse_query
from creator_scout.discovery.store import DiscoveryStore, to_uuid
from creator_scout.brand.service import BrandScanService


class DiscoveryService:
    def __init__(self, store: DiscoveryStore) -> None:
        self.store = store
        self.search_engine = DiscoverySearch(store)
        self.campaign_service = CampaignService(store)

    def search(self, payload: dict, principal: ApiKeyPrincipal | None = None) -> dict:
        started = time.perf_counter()
        request_id = f"req_{uuid4().hex}"
        query = parse_query(payload)
        provisional_cost = credit_cost_for_search(query.limit, semantic=bool(query.text))
        if principal:
            assert_credit_available(self.store, principal, provisional_cost)

        results, freshness, confidence = self.search_engine.search(query)
        credits = credit_cost_for_search(len(results), semantic=bool(query.text))
        latency_ms = int((time.perf_counter() - started) * 1000)
        if principal:
            self.store.record_api_usage(
                org_id=principal.org_id,
                api_key_id=principal.api_key_id,
                endpoint="/v1/discovery/search",
                request_id=request_id,
                credits=credits,
                status_code=200,
                latency_ms=latency_ms,
                result_count=len(results),
                cache_status=freshness,
            )

        sources = []
        missing_fields = set()
        for result in results:
            missing_fields.update(result.missing_fields)
            sources.extend(
                {
                    "creator_id": result.creator.creator_id,
                    "source_url": source.source_url,
                    "source_type": source.source_type,
                    "fetched_at": source.fetched_at,
                    "confidence": source.confidence,
                }
                for source in result.creator.sources[:3]
            )

        response = ApiResponse(
            data=[
                {
                    "creator": result.creator,
                    "fit_score": result.fit_score,
                    "match_reasons": result.match_reasons,
                    "risk_flags": result.risk_flags,
                    "missing_fields": result.missing_fields,
                    "freshness": result.freshness,
                    "confidence": result.confidence,
                }
                for result in results
            ],
            meta=ApiMeta(
                request_id=request_id,
                credits_used=credits,
                freshness=freshness,
                confidence=confidence,
                sources=sources[:25],
                missing_fields=sorted(missing_fields),
                next_page=None,
            ),
        )
        return to_jsonable(response)

    def get_creator(self, creator_id: str, principal: ApiKeyPrincipal | None = None) -> dict | None:
        started = time.perf_counter()
        request_id = f"req_{uuid4().hex}"
        creator = self.store.get_creator(creator_id)
        if not creator:
            return None
        credits = 0.25
        freshness = Freshness.CACHED
        if principal:
            assert_credit_available(self.store, principal, credits)
            self.store.record_api_usage(
                org_id=principal.org_id,
                api_key_id=principal.api_key_id,
                endpoint="/v1/creators/{creator_id}",
                request_id=request_id,
                credits=credits,
                status_code=200,
                latency_ms=int((time.perf_counter() - started) * 1000),
                result_count=1,
                cache_status=freshness,
            )
        response = ApiResponse(
            data=creator,
            meta=ApiMeta(
                request_id=request_id,
                credits_used=credits,
                freshness=freshness,
                confidence=0.9 if creator.sources else 0.75,
                sources=[
                    {
                        "source_url": source.source_url,
                        "source_type": source.source_type,
                        "fetched_at": source.fetched_at,
                        "confidence": source.confidence,
                    }
                    for source in creator.sources
                ],
                missing_fields=[],
            ),
        )
        return to_jsonable(response)

    def usage(self, principal: ApiKeyPrincipal) -> dict:
        used = self.store.current_credit_usage(principal.org_id)
        return {
            "data": {
                "org_id": principal.org_id,
                "api_key_id": principal.api_key_id,
                "credits_used": used,
                "monthly_credit_limit": principal.monthly_credit_limit,
                "credits_remaining": max(0.0, principal.monthly_credit_limit - used),
            },
            "meta": {
                "request_id": f"req_{uuid4().hex}",
                "credits_used": 0.0,
                "freshness": "fresh",
                "confidence": 1.0,
                "sources": [],
                "missing_fields": [],
                "next_page": None,
            },
        }

    def refresh(self, payload: dict, principal: ApiKeyPrincipal | None = None) -> dict:
        request_id = f"req_{uuid4().hex}"
        credits = 1.0
        if principal:
            assert_credit_available(self.store, principal, credits)
        job_id = enqueue_refresh_job(
            self.store,
            profile_url=payload.get("profile_url"),
            creator_id=payload.get("creator_id"),
            provider=payload.get("provider"),
            org_id=principal.org_id if principal else None,
            api_key_id=principal.api_key_id if principal else None,
        )
        if principal:
            self.store.record_api_usage(
                org_id=principal.org_id,
                api_key_id=principal.api_key_id,
                endpoint="/v1/discovery/refresh",
                request_id=request_id,
                credits=credits,
                status_code=202,
                latency_ms=0,
                result_count=1,
                cache_status=Freshness.UNKNOWN,
            )
        return {
            "data": {
                "job_id": job_id,
                "status": "queued",
                "creator_id": payload.get("creator_id"),
                "profile_url": payload.get("profile_url"),
                "provider": payload.get("provider"),
            },
            "meta": {
                "request_id": request_id,
                "credits_used": credits,
                "freshness": "unknown",
                "confidence": 1.0,
                "sources": [],
                "missing_fields": [],
                "next_page": None,
            },
        }

    def ingest_query(self, payload: dict, principal: ApiKeyPrincipal | None = None) -> dict:
        request_id = f"req_{uuid4().hex}"
        query = str(payload.get("query") or payload.get("text") or "").strip()
        if not query:
            raise ValueError("query is required")
        provider = str(payload.get("provider") or "youtube")
        limit = min(max(int(payload.get("limit", 10)), 1), 50)
        credits = 1.0
        if principal:
            assert_credit_available(self.store, principal, credits)
        job_id = enqueue_discovery_query_job(
            self.store,
            query=query,
            provider=provider,
            limit=limit,
            org_id=principal.org_id if principal else None,
            api_key_id=principal.api_key_id if principal else None,
        )
        if principal:
            self.store.record_api_usage(
                org_id=principal.org_id,
                api_key_id=principal.api_key_id,
                endpoint="/v1/discovery/ingest-query",
                request_id=request_id,
                credits=credits,
                status_code=202,
                latency_ms=0,
                result_count=1,
                cache_status=Freshness.UNKNOWN,
            )
        return {
            "data": {
                "job_id": job_id,
                "status": "queued",
                "job_type": "creator_discovery_query",
                "provider": provider,
                "query": query,
                "limit": limit,
            },
            "meta": {
                "request_id": request_id,
                "credits_used": credits,
                "freshness": "unknown",
                "confidence": 1.0,
                "sources": [],
                "missing_fields": [],
                "next_page": None,
            },
        }

    def job_status(self, job_id: str, principal: ApiKeyPrincipal | None = None) -> dict | None:
        job = self.store.get_discovery_job(job_id)
        if not job:
            return None
        job_org = to_uuid(job.get("org_id"))
        caller_org = to_uuid(principal.org_id) if principal else None
        if caller_org and job_org not in {caller_org, None, to_uuid("system")}:
            raise PermissionError("Job does not belong to this organization")
        return {
            "data": job,
            "meta": {
                "request_id": f"req_{uuid4().hex}",
                "credits_used": 0.0,
                "freshness": "fresh",
                "confidence": 1.0,
                "sources": [],
                "missing_fields": [],
                "next_page": None,
            },
        }

    def retry_job(self, job_id: str, principal: ApiKeyPrincipal | None = None) -> dict | None:
        request_id = f"req_{uuid4().hex}"
        job = self.store.get_discovery_job(job_id)
        if not job:
            return None
        job_org = to_uuid(job.get("org_id"))
        caller_org = to_uuid(principal.org_id) if principal else None
        if caller_org and job_org not in {caller_org, None, to_uuid("system")}:
            raise PermissionError("Job does not belong to this organization")
        credits = 0.1
        if principal:
            assert_credit_available(self.store, principal, credits)
        retried = self.store.retry_discovery_job(job_id)
        if principal:
            self.store.record_api_usage(
                org_id=principal.org_id,
                api_key_id=principal.api_key_id,
                endpoint="/v1/jobs/{job_id}/retry",
                request_id=request_id,
                credits=credits,
                status_code=202,
                latency_ms=0,
                result_count=1,
                cache_status=Freshness.UNKNOWN,
            )
        return {
            "data": retried,
            "meta": {
                "request_id": request_id,
                "credits_used": credits,
                "freshness": "unknown",
                "confidence": 1.0,
                "sources": [],
                "missing_fields": [],
                "next_page": None,
            },
        }

    def scan_brand(self, payload: dict, principal: ApiKeyPrincipal | None = None) -> dict:
        request_id = f"req_{uuid4().hex}"
        brand_url = str(payload.get("brand_url") or payload.get("url") or "").strip()
        if not brand_url:
            raise ValueError("brand_url is required")
        credits = 2.0
        if principal:
            assert_credit_available(self.store, principal, credits)
        result = BrandScanService(self.store).scan(
            brand_url,
            org_id=principal.org_id if principal else None,
            geo=str(payload.get("geo") or "India"),
            goal=str(payload.get("goal") or "ugc"),
            enqueue_discovery=bool(payload.get("enqueue_discovery", False)),
            provider=str(payload.get("provider") or "youtube"),
            query_limit=int(payload.get("query_limit", 5)),
        )
        if principal:
            self.store.record_api_usage(
                org_id=principal.org_id,
                api_key_id=principal.api_key_id,
                endpoint="/v1/brand-scans",
                request_id=request_id,
                credits=credits,
                status_code=202 if result["discovery_job_ids"] else 200,
                latency_ms=0,
                result_count=result["pages_crawled"],
                cache_status=Freshness.FRESH,
            )
        return {
            "data": result,
            "meta": {
                "request_id": request_id,
                "credits_used": credits,
                "freshness": "fresh",
                "confidence": result["brief"]["confidence"],
                "sources": result["brief"]["evidence"],
                "missing_fields": [],
                "next_page": None,
            },
        }

    def get_brand(self, brand_id: str, principal: ApiKeyPrincipal | None = None) -> dict | None:
        brand = self.store.get_brand(brand_id)
        if not brand:
            return None
        if principal and brand.get("org_id") not in {principal.org_id, None, "system"}:
            raise PermissionError("Brand does not belong to this organization")
        brand.pop("brief_json", None)
        return {
            "data": brand,
            "meta": {
                "request_id": f"req_{uuid4().hex}",
                "credits_used": 0.0,
                "freshness": "cached",
                "confidence": brand.get("confidence") or 0.0,
                "sources": [],
                "missing_fields": [],
                "next_page": None,
            },
        }

    def create_campaign(self, payload: dict, principal: ApiKeyPrincipal | None = None) -> dict:
        started = time.perf_counter()
        request_id = f"req_{uuid4().hex}"
        brand_url = str(payload.get("brand_url") or payload.get("url") or "").strip()
        if not brand_url:
            raise ValueError("brand_url is required")
        credits = 3.0
        if principal:
            assert_credit_available(self.store, principal, credits)
        result = self.campaign_service.create_campaign(
            brand_url,
            org_id=principal.org_id if principal else None,
            api_key_id=principal.api_key_id if principal else None,
            geo=str(payload.get("geo") or "India"),
            goal=str(payload.get("goal") or "ugc"),
            platforms=payload.get("platforms"),
            provider=str(payload.get("provider") or "youtube"),
            query_limit=int(payload.get("query_limit", 5)),
            per_query_limit=int(payload.get("per_query_limit", 10)),
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if principal:
            self.store.record_api_usage(
                org_id=principal.org_id,
                api_key_id=principal.api_key_id,
                endpoint="/v1/campaigns",
                request_id=request_id,
                credits=credits,
                status_code=202,
                latency_ms=latency_ms,
                result_count=len(result["discovery_job_ids"]),
                cache_status=Freshness.FRESH,
            )
        return {
            "data": result,
            "meta": {
                "request_id": request_id,
                "credits_used": credits,
                "freshness": "fresh",
                "confidence": result["brand"]["brief"]["confidence"],
                "sources": result["brand"]["brief"]["evidence"],
                "missing_fields": [],
                "next_page": None,
            },
        }

    def get_campaign(self, campaign_id: str, principal: ApiKeyPrincipal | None = None) -> dict | None:
        campaign = self.campaign_service.get_campaign(
            campaign_id,
            org_id=principal.org_id if principal else None,
        )
        if not campaign:
            return None
        return {
            "data": campaign,
            "meta": {
                "request_id": f"req_{uuid4().hex}",
                "credits_used": 0.0,
                "freshness": "cached",
                "confidence": campaign.get("brief", {}).get("confidence") or 0.0,
                "sources": [],
                "missing_fields": [],
                "next_page": None,
            },
        }

    def build_campaign_shortlist(
        self,
        campaign_id: str,
        payload: dict,
        principal: ApiKeyPrincipal | None = None,
    ) -> dict | None:
        started = time.perf_counter()
        request_id = f"req_{uuid4().hex}"
        credits = 1.0
        if principal:
            assert_credit_available(self.store, principal, credits)
        result = self.campaign_service.build_shortlist(
            campaign_id,
            org_id=principal.org_id if principal else None,
            limit=int(payload.get("limit", 50)),
            query_limit=payload.get("query_limit"),
        )
        if result is None:
            return None
        latency_ms = int((time.perf_counter() - started) * 1000)
        if principal:
            self.store.record_api_usage(
                org_id=principal.org_id,
                api_key_id=principal.api_key_id,
                endpoint="/v1/campaigns/{campaign_id}/shortlist",
                request_id=request_id,
                credits=credits,
                status_code=200,
                latency_ms=latency_ms,
                result_count=len(result["shortlist"]),
                cache_status=Freshness.CACHED,
            )
        return {
            "data": result,
            "meta": {
                "request_id": request_id,
                "credits_used": credits,
                "freshness": "cached",
                "confidence": _average_shortlist_confidence(result["shortlist"]),
                "sources": _shortlist_sources(result["shortlist"]),
                "missing_fields": sorted(
                    {missing for item in result["shortlist"] for missing in item.get("unknowns", [])}
                ),
                "next_page": None,
            },
        }

    def list_campaign_creators(
        self,
        campaign_id: str,
        principal: ApiKeyPrincipal | None = None,
        *,
        limit: int = 50,
    ) -> dict | None:
        campaign = self.campaign_service.get_campaign(
            campaign_id,
            org_id=principal.org_id if principal else None,
        )
        if not campaign:
            return None
        shortlist = self.campaign_service.list_shortlist(
            campaign_id,
            org_id=principal.org_id if principal else None,
            limit=limit,
        )
        return {
            "data": shortlist,
            "meta": {
                "request_id": f"req_{uuid4().hex}",
                "credits_used": 0.0,
                "freshness": "cached",
                "confidence": _average_shortlist_confidence(shortlist),
                "sources": _shortlist_sources(shortlist),
                "missing_fields": sorted({missing for item in shortlist for missing in item.get("unknowns", [])}),
                "next_page": None,
            },
        }


def _average_shortlist_confidence(shortlist: list[dict]) -> float:
    confidences = [
        item.get("score_breakdown", {}).get("confidence")
        for item in shortlist
        if item.get("score_breakdown", {}).get("confidence") is not None
    ]
    if not confidences:
        return 0.0
    return round(sum(float(value) for value in confidences) / len(confidences), 3)


def _shortlist_sources(shortlist: list[dict]) -> list[dict]:
    sources = []
    for item in shortlist:
        for evidence in item.get("evidence", []):
            if evidence.get("source_url"):
                sources.append(
                    {
                        "creator_id": item.get("creator_id"),
                        "source_url": evidence.get("source_url"),
                        "source_type": evidence.get("source_type"),
                        "confidence": evidence.get("confidence"),
                    }
                )
    return sources[:25]
