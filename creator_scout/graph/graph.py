"""Assembles and compiles the Creator Scout LangGraph StateGraph.

Checkpointing: Uses PostgresSaver (production) backed by the InsForge
Postgres URL.  Falls back to MemorySaver when INSFORGE_DB_URL is unset
(unit tests, local dev without a DB).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from creator_scout.graph.edges import (
    fan_out_discovery,
    route_after_brand_scan,
    route_after_outreach_draft,
    route_after_shortlist,
)
from creator_scout.graph.nodes import (
    brand_scan_node,
    discovery_node,
    outreach_draft_node,
    query_planner_node,
    scoring_node,
    send_outreach_node,
    shortlist_node,
)
from creator_scout.graph.state import GraphState

logger = logging.getLogger(__name__)

# ─── Checkpointer factory ─────────────────────────────────────────────────────


def _make_postgres_checkpointer():
    """Return a langgraph-checkpoint-postgres PostgresSaver if DB URL is set."""
    db_url = (
        os.environ.get("INSFORGE_DB_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or ""
    ).strip()

    if not db_url:
        logger.info("[graph] No DB URL found — using MemorySaver (dev mode)")
        return MemorySaver()

    try:
        from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore[import]

        # Convert postgres:// → postgresql:// for psycopg3
        if db_url.startswith("postgres://"):
            db_url = "postgresql" + db_url[8:]

        saver = PostgresSaver.from_conn_string(db_url)
        saver.setup()
        logger.info("[graph] PostgresSaver checkpointer initialised")
        return saver
    except Exception as exc:
        logger.warning("[graph] PostgresSaver unavailable (%s) — using MemorySaver", exc)
        return MemorySaver()


# ─── Graph builder ────────────────────────────────────────────────────────────

def build_graph(checkpointer: Any | None = None):
    """Construct and compile the Creator Scout campaign graph.

    HIL gates (interrupt_before) pause the graph BEFORE these nodes:
      1. query_planner  — human approves the extracted brand brief
      2. outreach_draft — human approves the final shortlist
      3. send_outreach  — human approves the outreach email drafts

    Args:
        checkpointer: Optional pre-built checkpointer (for testing with MemorySaver).
    """
    g = StateGraph(GraphState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    g.add_node("brand_scan_node",     brand_scan_node)
    g.add_node("query_planner_node",  query_planner_node)
    g.add_node("discovery_node",      discovery_node)
    g.add_node("scoring_node",        scoring_node)
    g.add_node("shortlist_node",      shortlist_node)
    g.add_node("outreach_draft_node", outreach_draft_node)
    g.add_node("send_outreach_node",  send_outreach_node)

    # ── Edges ─────────────────────────────────────────────────────────────────
    g.add_edge(START, "brand_scan_node")

    # After brand_scan: conditional → query_planner (HIL Gate 1) or __end__
    g.add_conditional_edges("brand_scan_node", route_after_brand_scan, {
        "query_planner_node": "query_planner_node",
        "__end__": END,
    })

    # After query_planner: parallel Send() fan-out to discovery_node
    g.add_conditional_edges("query_planner_node", fan_out_discovery)

    # Discovery results merge → scoring
    g.add_edge("discovery_node", "scoring_node")
    g.add_edge("scoring_node",   "shortlist_node")

    # After shortlist: conditional → outreach_draft (HIL Gate 2) or __end__
    g.add_conditional_edges("shortlist_node", route_after_shortlist, {
        "outreach_draft_node": "outreach_draft_node",
        "__end__": END,
    })

    # After outreach_draft: conditional → send_outreach (HIL Gate 3) or __end__
    g.add_conditional_edges("outreach_draft_node", route_after_outreach_draft, {
        "send_outreach_node": "send_outreach_node",
        "__end__": END,
    })

    g.add_edge("send_outreach_node", END)

    # ── Compile with HIL gates ─────────────────────────────────────────────────
    cp = checkpointer if checkpointer is not None else _make_postgres_checkpointer()
    compiled = g.compile(
        checkpointer=cp,
        interrupt_before=[
            "query_planner_node",   # Gate 1: approve brand brief
            "outreach_draft_node",  # Gate 2: approve shortlist
            "send_outreach_node",   # Gate 3: approve email sends
        ],
    )
    return compiled


# ─── Singleton for API server ─────────────────────────────────────────────────

_graph_instance = None


def get_graph():
    """Return a singleton compiled graph (created once per process)."""
    global _graph_instance  # noqa: PLW0603
    if _graph_instance is None:
        _graph_instance = build_graph()
    return _graph_instance
