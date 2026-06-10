"""LangGraph conditional edge functions and parallel Send() fan-out.

These are pure routing functions — they inspect the current state and
decide which node to run next. No side effects.
"""
from __future__ import annotations

import logging

from langgraph.types import Send

from creator_scout.discovery.adapters.factory import choose_provider_for_query
from creator_scout.graph.state import GraphState

logger = logging.getLogger(__name__)


# ─── After brand_scan ─────────────────────────────────────────────────────────

def route_after_brand_scan(state: GraphState) -> str:
    """Route to query_planner (HIL gate) or end on error."""
    if state.get("error"):
        logger.warning("[graph:route] brand_scan errored — terminating")
        return "__end__"
    if not state.get("search_queries"):
        logger.warning("[graph:route] No search queries extracted — terminating")
        return "__end__"
    # Graph is compiled with interrupt_before=["query_planner_node"],
    # so this edge causes a pause for human approval of the brand brief.
    return "query_planner_node"


# ─── After query_planner: parallel Send() fan-out ─────────────────────────────

def fan_out_discovery(state: GraphState) -> list[Send]:
    """Create one parallel discovery task per search query.

    LangGraph executes all Send() tasks concurrently; their outputs are
    merged back into state via the list-reducer on raw_records / creator_ids.
    """
    queries = state.get("search_queries") or []
    if not queries:
        # No queries → skip to scoring with whatever we already have
        return [Send("scoring_node", state)]

    sends: list[Send] = []
    for query in queries:
        provider = choose_provider_for_query()
        sends.append(
            Send(
                "discovery_node",
                {
                    **state,
                    "_query": query,
                    "_provider": provider,
                },
            )
        )
    logger.info("[graph:route] Fanning out %d discovery tasks", len(sends))
    return sends


# ─── After shortlist ──────────────────────────────────────────────────────────

def route_after_shortlist(state: GraphState) -> str:
    """Route to outreach_draft (HIL gate) or end if shortlist is empty."""
    shortlist = state.get("shortlist") or []
    if not shortlist:
        logger.info("[graph:route] Empty shortlist — terminating")
        return "__end__"
    # Compiled with interrupt_before=["outreach_draft_node"]
    return "outreach_draft_node"


# ─── After outreach_draft ─────────────────────────────────────────────────────

def route_after_outreach_draft(state: GraphState) -> str:
    """Route to send_outreach (HIL gate) or end if no drafts."""
    drafts = state.get("outreach_drafts") or []
    if not drafts:
        logger.info("[graph:route] No outreach drafts — terminating")
        return "__end__"
    # Compiled with interrupt_before=["send_outreach_node"]
    return "send_outreach_node"
