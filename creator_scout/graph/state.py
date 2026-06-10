"""GraphState — the single TypedDict that flows through every LangGraph node.

All fields are optional at construction; nodes populate them progressively.
"""
from __future__ import annotations

from typing import Annotated, Any
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):
    # ── Inputs ───────────────────────────────────────────────────────────────
    campaign_id: str
    brand_url: str
    org_id: str | None
    goal: str           # "ugc" | "affiliate" | "ambassador" | "collab"
    geo: str            # e.g. "India", "US"

    # ── Brand scan outputs ────────────────────────────────────────────────────
    brand_brief: dict | None        # BrandBrief as dict
    search_queries: list[str]       # e.g. ["fitness creator India", ...]

    # ── Discovery outputs ─────────────────────────────────────────────────────
    raw_records: list[dict]         # raw creator records from adapters
    creator_ids: list[str]          # after ingest_records()

    # ── Scoring outputs ───────────────────────────────────────────────────────
    scored_creators: list[dict]     # [{creator_id, score, reasons, risks, confidence}]
    shortlist: list[dict]           # top candidates after threshold filter

    # ── Outreach ──────────────────────────────────────────────────────────────
    outreach_drafts: list[dict]     # [{creator_id, subject, body}]

    # ── SSE streaming tokens (brand-brief node) ───────────────────────────────
    stream_tokens: Annotated[list[str], add_messages]

    # ── Control ───────────────────────────────────────────────────────────────
    error: str | None
    human_feedback: str | None      # populated when resuming after HIL gate
    current_node: str               # tracks last completed node
