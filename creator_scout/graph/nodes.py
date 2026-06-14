"""LangGraph node functions.

Each node receives the full GraphState and returns a *partial* state dict
(only the keys it mutates). LangGraph merges this into the running state.

Nodes wrap existing Creator Scout services — no new AI/business logic lives
here; this is pure orchestration.
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import asdict
from typing import Any

from creator_scout.brand.brief import build_brand_brief
from creator_scout.brand.crawler import BrandCrawler
from creator_scout.discovery.adapters.factory import (
    adapter_for_provider,
    choose_provider_for_query,
)
from creator_scout.discovery.ingest import ingest_records
from creator_scout.discovery.models import DiscoveryQuery, Platform
from creator_scout.discovery.scoring import score_creator
from creator_scout.discovery.store import DiscoveryStore
from creator_scout.graph.state import GraphState

logger = logging.getLogger(__name__)

# Score threshold — creators below this are dropped from the shortlist
SHORTLIST_SCORE_THRESHOLD = int(os.environ.get("SHORTLIST_SCORE_THRESHOLD", "50"))
SHORTLIST_MAX = int(os.environ.get("SHORTLIST_MAX", "20"))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _store_from_config(state: GraphState) -> DiscoveryStore:
    """Return a fresh DiscoveryStore per node (thread-safe)."""
    return DiscoveryStore()


# ─── Node 1: Brand Scan ───────────────────────────────────────────────────────

def brand_scan_node(state: GraphState) -> dict:
    """Crawl the brand URL and extract brand brief + search queries.

    Emits SSE stream_tokens during the AI completion so the frontend can
    show a live typing effect.
    """
    brand_url = state.get("brand_url", "")
    goal = state.get("goal", "ugc")
    geo = state.get("geo", "India")

    logger.info("[graph:brand_scan] Scanning %s (goal=%s, geo=%s)", brand_url, goal, geo)

    store = _store_from_config(state)
    try:
        crawler = BrandCrawler()
        pages = crawler.crawl(brand_url)
        brief = build_brand_brief(brand_url, pages, store, geo=geo, goal=goal)
        brief_dict = asdict(brief)
        queries = brief.search_queries or []

        logger.info("[graph:brand_scan] Got %d search queries", len(queries))
        return {
            "brand_brief": brief_dict,
            "search_queries": queries,
            "current_node": "brand_scan",
            "error": None,
            # Emit a summary token for SSE streaming
            "stream_tokens": [
                f"Brand: {brief.brand_name}\n"
                f"Category: {brief.category}\n"
                f"Queries: {', '.join(queries[:3])}{'...' if len(queries) > 3 else ''}"
            ],
        }
    except Exception as exc:
        logger.error("[graph:brand_scan] Error: %s", exc)
        return {"error": str(exc), "current_node": "brand_scan"}
    finally:
        store.close()


# ─── Node 2: Query Planner ────────────────────────────────────────────────────

def query_planner_node(state: GraphState) -> dict:
    """Re-rank queries and assign a provider to each.

    Returns search_queries with provider annotations.
    Runs AFTER the brand-brief HIL gate.
    """
    queries = state.get("search_queries") or []
    human_feedback = state.get("human_feedback")

    # If the human edited the brief / queries during HIL approval, use theirs
    if human_feedback and human_feedback.strip():
        try:
            import json
            feedback_data = json.loads(human_feedback)
            if "search_queries" in feedback_data:
                queries = feedback_data["search_queries"]
                logger.info("[graph:query_planner] Using %d human-edited queries", len(queries))
        except Exception:
            pass  # plain text feedback — keep original queries

    # De-dupe and limit to sensible number
    seen: set[str] = set()
    deduped: list[str] = []
    for q in queries:
        if q and q.lower() not in seen:
            seen.add(q.lower())
            deduped.append(q)
    queries = deduped[:10]  # max 10 parallel discovery jobs

    logger.info("[graph:query_planner] Planning %d queries", len(queries))
    return {
        "search_queries": queries,
        "human_feedback": None,  # consumed
        "current_node": "query_planner",
    }


# ─── Node 3: Discovery ────────────────────────────────────────────────────────

def discovery_node(state: GraphState) -> dict:
    """Run one discovery query and ingest the results.

    This node is called in PARALLEL via LangGraph Send() — one instance
    per search query. Results are accumulated into raw_records / creator_ids
    via the Annotated list reducer in GraphState.
    """
    # When called via Send(), the per-query payload is merged into state
    query = state.get("_query") or (state.get("search_queries") or [""])[0]
    provider = state.get("_provider") or choose_provider_for_query()
    campaign_id = state.get("campaign_id")
    org_id = state.get("org_id")

    logger.info("[graph:discovery] query=%r provider=%s", query, provider)

    store = _store_from_config(state)
    try:
        adapter = adapter_for_provider(provider)
        result = adapter.discover(query, limit=15)
        creator_ids = ingest_records(store, result.records)
        logger.info("[graph:discovery] Ingested %d creators for %r", len(creator_ids), query)
        return {
            "raw_records": result.records,
            "creator_ids": creator_ids,
            "current_node": "discovery",
        }
    except Exception as exc:
        logger.warning("[graph:discovery] query=%r error: %s", query, exc)
        return {"raw_records": [], "creator_ids": [], "current_node": "discovery"}
    finally:
        store.close()


# ─── Node 4: Scoring ──────────────────────────────────────────────────────────

def scoring_node(state: GraphState) -> dict:
    """Score every ingested creator against the brand brief."""
    creator_ids = state.get("creator_ids") or []
    brand_brief = state.get("brand_brief") or {}
    goal = state.get("goal", "ugc")

    logger.info("[graph:scoring] Scoring %d creators", len(creator_ids))

    store = _store_from_config(state)
    scored: list[dict] = []
    try:
        dq = DiscoveryQuery(
            text=brand_brief.get("category", ""),
            platforms=[Platform.YOUTUBE],
            topics=[str(t).lower() for t in (brand_brief.get("best_creator_niches") or [])],
            locations=[brand_brief.get("geo", "")],
            languages=[],
        )
        for creator_id in creator_ids:
            creator = store.get_creator(creator_id)
            if not creator:
                continue
            try:
                score, reasons, risks, missing, confidence = score_creator(
                    creator, dq, store=store, run_ai=True
                )
                scored.append({
                    "creator_id": creator_id,
                    "score": score,
                    "reasons": reasons,
                    "risks": risks,
                    "missing_fields": missing,
                    "confidence": confidence,
                })
            except Exception as exc:
                logger.warning("[graph:scoring] creator %s error: %s", creator_id, exc)
    finally:
        store.close()

    scored.sort(key=lambda x: (x["score"], x["confidence"]), reverse=True)
    logger.info("[graph:scoring] Scored %d creators", len(scored))
    return {"scored_creators": scored, "current_node": "scoring"}


# ─── Node 5: Shortlist ────────────────────────────────────────────────────────

def shortlist_node(state: GraphState) -> dict:
    """Filter and rank scored creators into a presentable shortlist.

    Runs BEFORE the shortlist-review HIL gate so the human sees the curated list.
    """
    scored = state.get("scored_creators") or []
    threshold = SHORTLIST_SCORE_THRESHOLD

    candidates = [c for c in scored if c.get("score", 0) >= threshold]
    candidates = candidates[:SHORTLIST_MAX]

    logger.info(
        "[graph:shortlist] %d/%d creators passed threshold %d",
        len(candidates), len(scored), threshold,
    )
    return {"shortlist": candidates, "current_node": "shortlist"}


# ─── Node 6: Outreach Draft ───────────────────────────────────────────────────

def outreach_draft_node(state: GraphState) -> dict:
    """Generate AI-powered outreach pitches for each shortlisted creator."""
    shortlist = state.get("shortlist") or []
    brand_brief = state.get("brand_brief") or {}
    campaign_id = state.get("campaign_id", "")
    org_id = state.get("org_id")

    logger.info("[graph:outreach_draft] Drafting for %d creators", len(shortlist))

    store = _store_from_config(state)
    drafts: list[dict] = []
    try:
        from creator_scout.campaign.service import CampaignService
        from creator_scout.outreach.service import OutreachService

        campaign_service = CampaignService(store)
        outreach_service = OutreachService(store, campaign_service=campaign_service)

        for item in shortlist:
            creator_id = item.get("creator_id", "")
            try:
                draft = outreach_service.draft_outreach(
                    campaign_id=campaign_id,
                    creator_id=creator_id,
                    org_id=org_id,
                )
                if draft:
                    drafts.append(draft)
            except Exception as exc:
                logger.warning("[graph:outreach_draft] creator %s error: %s", creator_id, exc)
    except Exception as exc:
        logger.error("[graph:outreach_draft] Outreach service error: %s", exc)
    finally:
        store.close()

    logger.info("[graph:outreach_draft] Generated %d drafts", len(drafts))
    return {"outreach_drafts": drafts, "current_node": "outreach_draft"}


# ─── Node 7: Send Outreach ────────────────────────────────────────────────────

def send_outreach_node(state: GraphState) -> dict:
    """Dispatch approved outreach emails via AutoSend.

    Only runs after the send-approval HIL gate is approved.
    """
    drafts = state.get("outreach_drafts") or []
    campaign_id = state.get("campaign_id", "")
    org_id = state.get("org_id")

    human_feedback = state.get("human_feedback", "")
    if human_feedback and "reject" in str(human_feedback).lower():
        logger.info("[graph:send_outreach] Send rejected by human — skipping")
        return {"current_node": "send_outreach", "human_feedback": None}

    logger.info("[graph:send_outreach] Sending %d outreach emails", len(drafts))

    store = _store_from_config(state)
    sent_count = 0
    try:
        from creator_scout.campaign.service import CampaignService
        from creator_scout.outreach.service import OutreachService

        campaign_service = CampaignService(store)
        outreach_service = OutreachService(store, campaign_service=campaign_service)

        for draft in drafts:
            creator_id = draft.get("creator_id", "")
            try:
                result = outreach_service.send_campaign_creator_outreach(
                    campaign_id=campaign_id,
                    creator_id=creator_id,
                    org_id=org_id,
                    subject=draft.get("subject"),
                    body=draft.get("body"),
                )
                if result:
                    sent_count += 1
            except Exception as exc:
                logger.warning("[graph:send_outreach] creator %s error: %s", creator_id, exc)
    finally:
        store.close()

    logger.info("[graph:send_outreach] Sent %d emails", sent_count)
    return {"current_node": "send_outreach", "human_feedback": None}
