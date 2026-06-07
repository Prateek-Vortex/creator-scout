from __future__ import annotations

from creator_scout.discovery.models import DiscoveryQuery, Freshness, Platform, SearchResult
from creator_scout.discovery.normalize import build_profile_url, infer_platform_from_url, normalize_handle
from creator_scout.discovery.scoring import freshness_for, passes_filters, score_creator
from creator_scout.discovery.store import DiscoveryStore


def parse_query(payload: dict) -> DiscoveryQuery:
    platforms = [
        Platform(item.lower())
        for item in payload.get("platforms", [])
        if item and item.lower() in {platform.value for platform in Platform}
    ]
    return DiscoveryQuery(
        text=payload.get("text", "") or payload.get("query", ""),
        platforms=platforms,
        locations=[str(item) for item in payload.get("locations", [])],
        languages=[str(item).lower() for item in payload.get("languages", [])],
        topics=[str(item).lower() for item in payload.get("topics", [])],
        follower_min=payload.get("follower_min"),
        follower_max=payload.get("follower_max"),
        limit=min(int(payload.get("limit", 20)), 100),
        offset=max(int(payload.get("offset", 0)), 0),
    )


class DiscoverySearch:
    def __init__(self, store: DiscoveryStore) -> None:
        self.store = store

    def exact_lookup(self, value: str) -> SearchResult | None:
        value = value.strip()
        if not value:
            return None
        if "://" in value or "." in value:
            platform = infer_platform_from_url(value)
            handle = normalize_handle(value.rstrip("/").split("/")[-1])
            profile_url = build_profile_url(platform, handle, value)
            creator = self.store.find_by_profile_url(profile_url)
            if creator:
                return SearchResult(
                    creator=creator,
                    fit_score=100,
                    match_reasons=["Exact profile URL match"],
                    risk_flags=[],
                    missing_fields=[],
                    freshness=freshness_for(creator),
                    confidence=0.98,
                )
        return None

    def search(self, query: DiscoveryQuery, run_ai: bool = True) -> tuple[list[SearchResult], Freshness, float]:
        exact = self.exact_lookup(query.text)
        if exact:
            return [exact], exact.freshness, exact.confidence

        matched_creators = []
        matches = []
        if query.text:
            embedding = self.store.generate_embedding(query.text)
            if embedding:
                matches = self.store.semantic_search(embedding, limit=100)
                for m in matches:
                    creator = self.store.get_creator(m["id"])
                    if creator:
                        matched_creators.append(creator)
            
        if not matched_creators:
            matched_creators = self.store.all_creators()

        candidates = []
        for creator in matched_creators:
            if not passes_filters(creator, query):
                continue
            
            score, reasons, risks, missing, confidence = score_creator(
                creator, query, store=self.store, run_ai=False
            )
            
            # If we did not use semantic search but have query text, check lexical relevance
            if query.text and not matches:
                has_relevance_evidence = any(
                    reason.startswith("Matches query terms") or reason.startswith("Topic overlap")
                    for reason in reasons
                )
                if not has_relevance_evidence:
                    continue
                if score < 25:
                    continue

            candidates.append({
                "creator": creator,
                "score": score,
                "reasons": reasons,
                "risks": risks,
                "missing": missing,
                "confidence": confidence
            })

        # Sort candidates deterministically first
        candidates.sort(key=lambda item: (item["score"], item["confidence"]), reverse=True)

        # Apply AI scoring to top 10 candidates if there is query text and run_ai is True
        if query.text and self.store and run_ai:
            for item in candidates[:10]:
                ai_score, ai_reasons, ai_risks, _, ai_conf = score_creator(
                    item["creator"], query, store=self.store, run_ai=True
                )
                item["score"] = ai_score
                # Keep original non-lexical reasons and append AI reasons
                filtered_reasons = [
                    r for r in item["reasons"]
                    if not r.startswith("Matches query terms") and not r.startswith("Topic overlap")
                ]
                item["reasons"] = ai_reasons + filtered_reasons
                item["risks"] = sorted(list(set(item["risks"] + ai_risks)))
                item["confidence"] = ai_conf

        # Re-sort candidates after optional AI scoring
        candidates.sort(key=lambda item: (item["score"], item["confidence"]), reverse=True)

        results = [
            SearchResult(
                creator=c["creator"],
                fit_score=c["score"],
                match_reasons=c["reasons"],
                risk_flags=c["risks"],
                missing_fields=c["missing"],
                freshness=freshness_for(c["creator"]),
                confidence=c["confidence"],
            )
            for c in candidates
        ]

        paginated = results[query.offset : query.offset + query.limit]
        if not paginated:
            return [], Freshness.UNKNOWN, 0.0
        freshness = Freshness.FRESH if any(item.freshness == Freshness.FRESH for item in paginated) else paginated[0].freshness
        confidence = round(sum(item.confidence for item in paginated) / len(paginated), 3)
        return paginated, freshness, confidence


def credit_cost_for_search(result_count: int, semantic: bool = False) -> float:
    unit = 0.02 if semantic else 0.01
    return round(max(0.01, result_count * unit), 4)
