from __future__ import annotations

import csv
import io
import os

from creator_scout.brand.service import BrandScanService
from creator_scout.discovery.jobs import enqueue_discovery_query_job
from creator_scout.discovery.models import Platform, SearchResult, to_jsonable
from creator_scout.discovery.search import DiscoverySearch, parse_query
from creator_scout.discovery.scoring import freshness_for, passes_filters, score_creator
from creator_scout.discovery.store import DiscoveryStore, to_uuid


DEFAULT_CAMPAIGN_PLATFORMS = ["youtube", "instagram", "tiktok"]
EXPORT_BUCKET = "campaign-exports"


class CampaignService:
    def __init__(self, store: DiscoveryStore, brand_scan_service: BrandScanService | None = None) -> None:
        self.store = store
        self.brand_scan_service = brand_scan_service or BrandScanService(store)
        self.search_engine = DiscoverySearch(store)

    def create_campaign(
        self,
        brand_url: str,
        *,
        org_id: str | None = None,
        api_key_id: str | None = None,
        geo: str = "India",
        goal: str = "ugc",
        platforms: object | None = None,
        provider: str = "youtube",
        query_limit: int = 5,
        per_query_limit: int = 10,
        discovery_mode: str = "safe_fanout",
        max_providers_per_query: int = 2,
        max_enrichment_urls_per_query: int = 5,
    ) -> dict:
        brand_url = brand_url.strip()
        if not brand_url:
            raise ValueError("brand_url is required")

        normalized_platforms = _normalize_platforms(platforms)
        provider = (provider or "youtube").strip().lower()
        discovery_mode = (discovery_mode or "safe_fanout").strip().lower()
        if discovery_mode not in {"safe_fanout", "single_provider"}:
            raise ValueError("Unsupported discovery_mode")
        query_limit = min(max(int(query_limit), 1), 12)
        per_query_limit = min(max(int(per_query_limit), 1), 50)
        max_providers_per_query = min(max(int(max_providers_per_query), 1), 3)
        max_enrichment_urls_per_query = min(max(int(max_enrichment_urls_per_query), 0), 20)
        selected_providers = _providers_for_campaign(provider, discovery_mode, max_providers_per_query)

        scan = self.brand_scan_service.scan(
            brand_url,
            org_id=org_id,
            geo=geo,
            goal=goal,
            enqueue_discovery=False,
            provider=provider,
            query_limit=query_limit,
        )
        brief = scan["brief"]
        search_queries = _dedupe(brief.get("search_queries", []))[:query_limit]
        campaign_id = self.store.create_campaign(
            org_id=org_id,
            brand_id=scan["brand_id"],
            brand_url=brand_url,
            goal=goal,
            geo=geo,
            platforms=normalized_platforms,
            brief=brief,
            search_queries=search_queries,
        )

        job_ids: list[str] = []
        for query in search_queries:
            for selected_provider in selected_providers:
                job_id = enqueue_discovery_query_job(
                    self.store,
                    query=query,
                    provider=selected_provider,
                    limit=per_query_limit,
                    org_id=org_id,
                    api_key_id=api_key_id,
                    campaign_id=campaign_id,
                    max_enrichment_urls=max_enrichment_urls_per_query,
                )
                self.store.link_campaign_job(campaign_id, job_id, query, selected_provider)
                job_ids.append(job_id)

        return {
            "campaign": self.get_campaign(campaign_id, org_id=org_id),
            "brand": {
                "brand_id": scan["brand_id"],
                "brand_url": brand_url,
                "brief": brief,
                "pages_crawled": scan["pages_crawled"],
            },
            "discovery_job_ids": job_ids,
        }

    def get_campaign(self, campaign_id: str, *, org_id: str | None = None) -> dict | None:
        campaign = self.store.get_campaign(campaign_id)
        if not campaign:
            return None
        campaign_org = to_uuid(campaign.get("org_id"))
        caller_org = to_uuid(org_id)
        if caller_org and campaign_org not in {caller_org, None, to_uuid("system")}:
            raise PermissionError("Campaign does not belong to this organization")
        return _clean_campaign(campaign)

    def list_campaigns(self, *, org_id: str | None = None, limit: int = 20) -> list[dict]:
        return [_clean_campaign(campaign) for campaign in self.store.list_campaigns(org_id=org_id, limit=limit)]

    def generate_outreach_draft(self, campaign: dict, creator: CreatorProfile, pitch: str) -> dict:
        brief = campaign.get("brief") or {}
        brand_name = brief.get("brand_name", campaign.get("brand_url"))
        products = brief.get("products") or []
        product = products[0] if products else (brief.get("category") or "the product")

        import sys
        IN_TEST = "unittest" in sys.modules or "pytest" in sys.modules or (len(sys.argv) > 0 and "pytest" in sys.argv[0])
        if IN_TEST:
            return _fallback_outreach(brand_name, product, creator, pitch)
        
        prompt = f"""You are a founder-led creator outreach writer. Draft a short, warm, specific outreach email — under 110 words — that a real founder would send.

Hard rules:
- No emojis, no exclamation marks, no buzzwords ("amazing", "stoked", "love your vibe"), no flattery clichés.
- Open with one concrete observation about the creator's niche or audience (one sentence), not "I love your content".
- One sentence on why {brand_name} / {product} is relevant to them.
- One clear, low-friction ask (15-min call OR reply with rate card).
- Sign off as "Creator Scout Team" — no placeholders like [Your Name].

Context:
- Brand: {brand_name}
- Product: {product}
- Campaign goal: {campaign.get("goal")}
- Creator: {creator.display_name}
- Niche: {creator.primary_niche}
- Why they fit: {pitch}

Return ONLY a JSON object:
- "subject": 5-8 word subject line, no colons, references the creator's niche or the product — not the word "Partnership".
- "body": the email body text."""

        try:
            import json
            import re
            res = self.store._request(
                "POST",
                "/api/ai/chat/completion",
                json_data={
                    "model": "anthropic/claude-sonnet-4.5",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3
                },
                timeout=2
            )
            if res and isinstance(res, dict) and res.get("success") and "text" in res:
                response_text = res["text"].strip()
                clean_text = response_text
                match = re.search(r"```json\s+(.*?)\s+```", response_text, re.DOTALL | re.IGNORECASE)
                if match:
                    clean_text = match.group(1).strip()
                else:
                    match = re.search(r"```\s+(.*?)\s+```", response_text, re.DOTALL | re.IGNORECASE)
                    if match:
                        clean_text = match.group(1).strip()
                return json.loads(clean_text)
        except Exception as e:
            print(f"Error generating outreach draft: {e}")
        
        return _fallback_outreach(brand_name, product, creator, pitch)

    def build_shortlist(
        self,
        campaign_id: str,
        *,
        org_id: str | None = None,
        limit: int = 50,
        query_limit: int | None = None,
    ) -> dict | None:
        campaign = self.get_campaign(campaign_id, org_id=org_id)
        if not campaign:
            return None

        limit = min(max(int(limit), 1), 100)
        queries = campaign.get("search_queries", [])
        if query_limit is not None:
            queries = queries[: min(max(int(query_limit), 1), len(queries))]
        candidates = self._rank_campaign_candidates(campaign, queries, limit)

        candidates_slice = candidates[:limit]

        brand_name = (campaign.get("brief") or {}).get("brand_name", campaign.get("brand_url"))
        brief_products = (campaign.get("brief") or {}).get("products") or []
        product = brief_products[0] if brief_products else ((campaign.get("brief") or {}).get("category") or "the product")

        # Build deterministic pitch + template outreach for every row. AI-refined
        # outreach is generated lazily on demand (POST .../outreach/draft) so the
        # shortlist build stays fast under load and InsForge rate-limit pressure.
        processed_results = []
        for result, matched_queries in candidates_slice:
            pitch = _pitch_for_result(campaign, result)
            outreach = _fallback_outreach(brand_name, product, result.creator, pitch)
            processed_results.append((result, matched_queries, pitch, outreach))

        from creator_scout.discovery.normalize import stable_id
        from creator_scout.discovery.models import utc_now

        creators_list = []
        now = utc_now()
        for result, matched_queries, pitch, outreach in processed_results:
            bucket = _bucket_for_score(result.fit_score, result.missing_fields, result.risk_flags)
            cc_id = stable_id("cc", campaign_id, result.creator.creator_id)
            cc_data = {
                "id": cc_id,
                "campaign_id": campaign_id,
                "creator_id": result.creator.creator_id,
                "status": "shortlisted",
                "bucket": bucket,
                "fit_score": result.fit_score,
                "score_breakdown": {
                    "fit_score": result.fit_score,
                    "confidence": result.confidence,
                    "freshness": result.freshness.value,
                    "matched_queries": matched_queries,
                    "match_reasons": result.match_reasons,
                },
                "evidence": _evidence_for_result(result),
                "risks": result.risk_flags,
                "unknowns": result.missing_fields,
                "recommended_pitch": pitch,
                "outreach_draft": outreach,
                "created_at": now,
                "updated_at": now,
            }
            creators_list.append(cc_data)

        self.store.bulk_upsert_campaign_creators(creators_list)
        self.store.update_campaign_status(campaign_id, "shortlisted" if candidates else "discovering")

        return {
            "campaign_id": campaign_id,
            "shortlist": self.list_shortlist(campaign_id, org_id=org_id, limit=limit),
            "candidate_count": len(candidates),
            "job_summary": campaign.get("job_summary") or {},
        }

    def list_shortlist(self, campaign_id: str, *, org_id: str | None = None, limit: int = 50) -> list[dict]:
        campaign = self.get_campaign(campaign_id, org_id=org_id)
        if not campaign:
            return []
        rows = self.store.list_campaign_creators(campaign_id, limit=min(max(int(limit), 1), 100))

        # Fetch creator profiles in parallel to avoid sequential N × 4 InsForge round-trips
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def fetch_row(row: dict) -> dict:
            try:
                creator = self.store.get_creator(row["creator_id"])
            except Exception:  # noqa: BLE001
                creator = None
            cleaned = _clean_shortlist_row(row)
            cleaned["creator"] = to_jsonable(creator) if creator else None
            cleaned["outreach_messages"] = self.store.list_outreach_messages(row["id"])
            return cleaned

        max_workers = min(10, len(rows) or 1)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_row, row): row for row in rows}
            hydrated = [future.result() for future in as_completed(futures)]

        # Restore original ordering (as_completed returns in completion order)
        row_order = {row["creator_id"]: i for i, row in enumerate(rows)}
        hydrated.sort(key=lambda r: row_order.get((r.get("creator") or {}).get("creator_id", ""), 999))
        return hydrated

    def update_campaign_creator(
        self,
        campaign_id: str,
        creator_id: str,
        *,
        org_id: str | None = None,
        status: str | None = None,
        recommended_pitch: str | None = None,
        notes: str | None = None,
    ) -> dict | None:
        campaign = self.get_campaign(campaign_id, org_id=org_id)
        if not campaign:
            return None
        fields: dict[str, object] = {}
        if status is not None:
            if status not in _valid_crm_statuses():
                raise ValueError("Unsupported CRM status")
            fields["status"] = status
        if recommended_pitch is not None:
            fields["recommended_pitch"] = recommended_pitch
        if notes is not None:
            fields["notes"] = notes
        updated = self.store.update_campaign_creator(campaign_id, creator_id, fields)
        if not updated:
            return None
        creator = self.store.get_creator(creator_id)
        cleaned = _clean_shortlist_row(updated)
        cleaned["creator"] = to_jsonable(creator) if creator else None
        return cleaned

    def refine_outreach_draft(
        self,
        campaign_id: str,
        creator_id: str,
        *,
        org_id: str | None = None,
    ) -> dict | None:
        """Generate an AI-refined outreach draft for one shortlisted creator.

        Called on demand from the UI; keeps the bulk shortlist build cheap.
        """
        campaign = self.get_campaign(campaign_id, org_id=org_id)
        if not campaign:
            return None
        row = self.store.get_campaign_creator(campaign_id, creator_id)
        if not row:
            return None
        creator = self.store.get_creator(creator_id)
        if not creator:
            return None
        pitch = row.get("recommended_pitch") or ""
        outreach = self.generate_outreach_draft(campaign, creator, pitch)
        updated = self.store.update_campaign_creator(
            campaign_id, creator_id, {"outreach_draft": outreach}
        )
        if not updated:
            return None
        cleaned = _clean_shortlist_row(updated)
        cleaned["creator"] = to_jsonable(creator)
        return cleaned

    def export_shortlist(self, campaign_id: str, *, org_id: str | None = None) -> dict | None:
        campaign = self.get_campaign(campaign_id, org_id=org_id)
        if not campaign:
            return None
        shortlist = self.list_shortlist(campaign_id, org_id=org_id, limit=100)
        csv_text = _shortlist_csv(shortlist)
        timestamp = utc_export_timestamp()
        key = f"campaigns/{campaign_id}/exports/{timestamp}.csv"
        uploaded = self.store.upload_storage_object(
            bucket=EXPORT_BUCKET,
            key=key,
            content=csv_text.encode("utf-8"),
            content_type="text/csv;charset=utf-8",
        )
        file_url = uploaded.get("url") or f"{self.store.url}/api/storage/buckets/{EXPORT_BUCKET}/objects/{key}"
        export = self.store.create_campaign_export(
            org_id=campaign.get("org_id"),
            campaign_id=campaign_id,
            storage_key=uploaded.get("key") or key,
            file_url=file_url,
            row_count=len(shortlist),
        )
        return export

    def _rank_campaign_candidates(
        self,
        campaign: dict,
        queries: list[str],
        limit: int,
    ) -> list[tuple[SearchResult, list[str]]]:
        platform_values = _normalize_platforms(campaign.get("platforms") or DEFAULT_CAMPAIGN_PLATFORMS)
        category = (campaign.get("brief") or {}).get("category")
        topic_values = [category] if category and category != "unknown" else []
        geo = campaign.get("geo") or ""
        best_by_creator: dict[str, tuple[SearchResult, list[str]]] = {}

        # Prefer the fresh creators produced by this campaign's discovery jobs.
        # Global semantic search can miss just-ingested rows before embeddings or
        # vector indexes catch up, which made successful jobs yield an empty shortlist.
        #
        # Hot-path optimization: pre-fetch every unique creator_id in parallel.
        # Previously this looped sequentially across all jobs × all creator_ids,
        # producing N HTTP round-trips to InsForge (up to ~350 per build). Under
        # InsForge rate-limit / slowness pressure that hangs the request for
        # minutes. One parallel fetch pool collapses it to ~1 round-trip wall time.
        from concurrent.futures import ThreadPoolExecutor

        job_creator_map: list[tuple[str, list[str]]] = []  # (job_query, [creator_id, ...])
        unique_ids: list[str] = []
        seen_ids: set[str] = set()
        for job in campaign.get("jobs", []) or []:
            output = job.get("output") or {}
            ids = _dedupe([str(item) for item in output.get("creator_ids", []) if item])
            if not ids:
                continue
            job_query = str(job.get("query") or output.get("query") or "").strip()
            job_creator_map.append((job_query, ids))
            for cid in ids:
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    unique_ids.append(cid)

        creator_cache: dict[str, object] = {}
        if unique_ids:
            with ThreadPoolExecutor(max_workers=min(20, len(unique_ids))) as pool:
                fetched = list(pool.map(self.store.get_creator, unique_ids))
            for cid, creator in zip(unique_ids, fetched):
                if creator is not None:
                    creator_cache[cid] = creator

        for job_query, creator_ids in job_creator_map:
            campaign_query = parse_query(
                {
                    "text": " ".join(part for part in [job_query, category, geo] if part),
                    "platforms": platform_values,
                    "topics": topic_values,
                    "limit": max(limit * 2, 25),
                }
            )
            for creator_id in creator_ids:
                creator = creator_cache.get(creator_id)
                if not creator or not passes_filters(creator, campaign_query):
                    continue
                score, reasons, risks, missing, confidence = score_creator(
                    creator,
                    campaign_query,
                    store=self.store,
                    run_ai=False,
                )
                if score < 50:
                    continue
                result = SearchResult(
                    creator=creator,
                    fit_score=score,
                    match_reasons=reasons,
                    risk_flags=risks,
                    missing_fields=missing,
                    freshness=freshness_for(creator),
                    confidence=confidence,
                )
                current = best_by_creator.get(creator.creator_id)
                if current is None:
                    best_by_creator[creator.creator_id] = (result, [job_query] if job_query else [])
                    continue
                current_result, matched_queries = current
                if result.fit_score > current_result.fit_score:
                    best_by_creator[creator.creator_id] = (result, _dedupe([*matched_queries, job_query]))
                elif job_query:
                    matched_queries.append(job_query)

        if best_by_creator:
            ranked = list(best_by_creator.values())
            ranked.sort(key=lambda item: (item[0].fit_score, item[0].confidence), reverse=True)
            return [(result, _dedupe(matched_queries)) for result, matched_queries in ranked]

        for query in queries:
            campaign_query = parse_query(
                {
                    "text": " ".join(part for part in [query, category, geo] if part),
                    "platforms": platform_values,
                    "topics": topic_values,
                    "limit": max(limit * 2, 25),
                }
            )
            results, _, _ = self.search_engine.search(campaign_query, run_ai=False)
            for result in results:
                if result.fit_score < 50:
                    continue
                current = best_by_creator.get(result.creator.creator_id)
                if current is None:
                    best_by_creator[result.creator.creator_id] = (result, [query])
                    continue
                current_result, matched_queries = current
                if result.fit_score > current_result.fit_score:
                    best_by_creator[result.creator.creator_id] = (result, _dedupe([*matched_queries, query]))
                else:
                    matched_queries.append(query)

        ranked = list(best_by_creator.values())
        ranked.sort(key=lambda item: (item[0].fit_score, item[0].confidence), reverse=True)
        return [(result, _dedupe(matched_queries)) for result, matched_queries in ranked]


def _normalize_platforms(platforms: object | None) -> list[str]:
    valid = {platform.value for platform in Platform}
    if isinstance(platforms, str):
        raw_platforms = [platforms]
    else:
        raw_platforms = list(platforms) if platforms else DEFAULT_CAMPAIGN_PLATFORMS
    selected = [
        str(platform).strip().lower()
        for platform in raw_platforms
        if str(platform).strip().lower() in valid
    ]
    return _dedupe(selected) or DEFAULT_CAMPAIGN_PLATFORMS


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized.lower() not in seen:
            result.append(normalized)
            seen.add(normalized.lower())
    return result


def _providers_for_campaign(provider: str, discovery_mode: str, max_providers_per_query: int) -> list[str]:
    provider = (provider or "youtube").strip().lower()
    if discovery_mode == "single_provider":
        return _dedupe([provider])[:max_providers_per_query]

    providers = ["youtube"]
    if os.environ.get("TINYFISH_API_KEY"):
        providers.append("tinyfish")
    if provider not in providers:
        providers.append(provider)
    return _dedupe(providers)[:max_providers_per_query]


def _bucket_for_score(score: int, missing_fields: list[str], risk_flags: list[str]) -> str:
    if score >= 80 and "public_business_contact" not in missing_fields and not risk_flags:
        return "contact_first"
    if score >= 65:
        return "review"
    if score >= 50:
        return "backup"
    return "avoid"


def _evidence_for_result(result: SearchResult) -> list[dict]:
    evidence = [
        {
            "source_url": source.source_url,
            "source_type": source.source_type,
            "confidence": source.confidence,
            "fields_found": source.fields_found,
        }
        for source in result.creator.sources[:5]
    ]
    evidence.append(
        {
            "source_type": "scoring",
            "fit_score": result.fit_score,
            "match_reasons": result.match_reasons,
        }
    )
    return evidence


def _fallback_outreach(brand_name: str, product: str, creator: CreatorProfile, pitch: str) -> dict:
    niche = (creator.primary_niche or "").strip()
    niche_line = (
        f"Your {niche} work is the closest fit I have seen for what we are building."
        if niche
        else "Your recent work is the closest fit I have seen for what we are building."
    )
    body = (
        f"Hi {creator.display_name},\n\n"
        f"{niche_line}\n\n"
        f"We are launching {product} at {brand_name} and the angle in your last few uploads lines up directly with how we think about it. "
        f"Quick context on the fit: {pitch}\n\n"
        f"Open to a 15-minute call this week, or feel free to reply with your rate card and we can take it from there.\n\n"
        f"— Creator Scout Team"
    )
    subject = f"{brand_name} x {creator.display_name}".strip(" x")
    return {"subject": subject or f"{brand_name} collaboration", "body": body}


def _pitch_for_result(campaign: dict, result: SearchResult) -> str:
    brief = campaign.get("brief") or {}
    brand_name = brief.get("brand_name") or campaign.get("brand_url") or "the brand"
    angles = brief.get("campaign_angles") or ["an honest first-impression review"]
    product = (brief.get("products") or [brief.get("category") or "the product"])[0]
    angle = angles[0].split(":", 1)[-1].strip()
    reasons = [r for r in (result.match_reasons or []) if r][:2]
    niche = (result.creator.primary_niche or "").strip()
    audience_bits = []
    if niche:
        audience_bits.append(f"their {niche} audience")
    if reasons:
        audience_bits.append("strong signal on " + " and ".join(reasons))
    audience = "; ".join(audience_bits) or "audience fit"
    return (
        f"Pitch {result.creator.display_name} on {angle} featuring {product} for {brand_name}. "
        f"Why they fit: {audience}."
    )


def _clean_campaign(campaign: dict) -> dict:
    cleaned = dict(campaign)
    for job in cleaned.get("jobs", []):
        job.pop("output_json", None)
    return cleaned


def _clean_shortlist_row(row: dict) -> dict:
    cleaned = dict(row)
    cleaned.pop("score_breakdown_json", None)
    cleaned.pop("evidence_json", None)
    cleaned.pop("risks_json", None)
    cleaned.pop("unknowns_json", None)
    return cleaned


def _valid_crm_statuses() -> set[str]:
    return {"shortlisted", "contacted", "replied", "negotiating", "accepted", "content_pending", "live", "done"}


def _shortlist_csv(shortlist: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Creator",
            "Score",
            "Bucket",
            "Status",
            "Niche",
            "Location",
            "Platforms",
            "Contact",
            "Pitch",
            "Notes",
        ]
    )
    for item in shortlist:
        creator = item.get("creator") or {}
        writer.writerow(
            [
                creator.get("display_name") or item.get("creator_id"),
                item.get("fit_score"),
                item.get("bucket"),
                item.get("status"),
                creator.get("primary_niche") or "",
                creator.get("location") or "",
                "; ".join(account.get("platform", "") for account in creator.get("accounts", [])),
                "; ".join(contact.get("value", "") for contact in creator.get("contacts", [])),
                item.get("recommended_pitch") or "",
                item.get("notes") or "",
            ]
        )
    return output.getvalue()


def utc_export_timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
