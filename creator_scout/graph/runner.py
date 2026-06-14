"""GraphRunner — the public API for starting, resuming, and polling graph runs.

All long-running execution happens via LangGraph's compiled graph with
PostgresSaver checkpointing.  The runner is designed to be instantiated
once and shared across FastAPI request handlers.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncIterator

from creator_scout.graph.graph import get_graph
from creator_scout.graph.state import GraphState

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Convert LangGraph/LangChain objects into JSON-safe primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    content = getattr(value, "content", None)
    if content is not None:
        return _json_safe(content)
    return str(value)


def _sse_event(payload: dict[str, Any]) -> str:
    import json

    return f"data: {json.dumps(_json_safe(payload))}\n\n"


class GraphRunner:
    """High-level wrapper around the compiled LangGraph application."""

    def __init__(self, graph=None) -> None:
        # Allow injection for testing (pass a MemorySaver-backed graph)
        self._graph = graph

    @property
    def graph(self):
        if self._graph is None:
            self._graph = get_graph()
        return self._graph

    # ─── Start ────────────────────────────────────────────────────────────────

    def start_campaign_run(
        self,
        *,
        campaign_id: str,
        brand_url: str,
        goal: str = "ugc",
        geo: str = "India",
        org_id: str | None = None,
    ) -> str:
        """Kick off a new campaign graph run.

        Returns the thread_id (checkpoint key).  The graph will execute
        brand_scan_node and then PAUSE before query_planner_node (HIL Gate 1).
        """
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state: GraphState = {
            "campaign_id": campaign_id,
            "brand_url": brand_url,
            "goal": goal,
            "geo": geo,
            "org_id": org_id,
            "brand_brief": None,
            "search_queries": [],
            "raw_records": [],
            "creator_ids": [],
            "scored_creators": [],
            "shortlist": [],
            "outreach_drafts": [],
            "stream_tokens": [],
            "error": None,
            "human_feedback": None,
            "current_node": "",
        }
        # graph.invoke() runs until an interrupt_before gate
        try:
            self.graph.invoke(initial_state, config)
        except Exception as exc:
            logger.error("[runner] start_campaign_run error: %s", exc)
            raise

        logger.info("[runner] Started thread_id=%s", thread_id)
        return thread_id

    # ─── Resume ───────────────────────────────────────────────────────────────

    def resume_run(
        self,
        thread_id: str,
        *,
        approved: bool,
        feedback: str = "",
    ) -> dict:
        """Resume a paused graph run after a HIL gate.

        Pass ``approved=True`` to continue; ``approved=False`` to abort.
        Optional ``feedback`` (JSON string or plain text) is written into
        state.human_feedback so nodes can read it.
        """
        config = {"configurable": {"thread_id": thread_id}}

        if not approved:
            logger.info("[runner] Run %s rejected by human", thread_id)
            # Update state with rejection signal and let graph proceed to __end__
            self.graph.update_state(
                config,
                {"human_feedback": "rejected", "error": "Rejected by user"},
            )
            # Invoke once more to let it resolve to __end__
            try:
                self.graph.invoke(None, config)
            except Exception:
                pass
            return {"thread_id": thread_id, "status": "rejected"}

        # Inject human feedback into state before resuming
        self.graph.update_state(config, {"human_feedback": feedback or "approved"})
        try:
            self.graph.invoke(None, config)
        except Exception as exc:
            logger.error("[runner] resume error: %s", exc)
            raise

        return {"thread_id": thread_id, "status": "running", "resumed": True}

    # ─── Status ───────────────────────────────────────────────────────────────

    def get_run_status(self, thread_id: str) -> dict:
        """Return the current graph run status.

        Returns a dict with:
          - thread_id
          - paused: bool (True when stopped at a HIL gate)
          - current_node: str
          - next_node: str | None
          - state: partial GraphState (sans raw_records to keep response small)
          - error: str | None
        """
        config = {"configurable": {"thread_id": thread_id}}
        try:
            snapshot = self.graph.get_state(config)
        except Exception as exc:
            return {
                "thread_id": thread_id,
                "error": f"Could not load state: {exc}",
                "paused": False,
            }

        state = dict(snapshot.values) if snapshot.values else {}
        next_nodes = list(snapshot.next) if snapshot.next else []
        paused = bool(next_nodes)  # has pending next node = paused at HIL gate

        # Strip heavy fields from status response
        safe_state = {k: v for k, v in state.items() if k not in ("raw_records", "stream_tokens")}

        return {
            "thread_id": thread_id,
            "paused": paused,
            "current_node": state.get("current_node", ""),
            "next_node": next_nodes[0] if next_nodes else None,
            "shortlist": _json_safe(state.get("shortlist", [])),
            "brand_brief": _json_safe(state.get("brand_brief")),
            "outreach_drafts": _json_safe(state.get("outreach_drafts", [])),
            "error": _json_safe(state.get("error")),
            "state": _json_safe(safe_state),
        }

    # ─── SSE streaming ────────────────────────────────────────────────────────

    async def stream_brand_scan(
        self,
        *,
        campaign_id: str,
        brand_url: str,
        goal: str = "ugc",
        geo: str = "India",
        org_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Start a run and yield SSE data events from brand_scan_node.

        Yields Server-Sent Events formatted strings.  The caller wraps this
        in a ``StreamingResponse``.
        """
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state: GraphState = {
            "campaign_id": campaign_id,
            "brand_url": brand_url,
            "goal": goal,
            "geo": geo,
            "org_id": org_id,
            "brand_brief": None,
            "search_queries": [],
            "raw_records": [],
            "creator_ids": [],
            "scored_creators": [],
            "shortlist": [],
            "outreach_drafts": [],
            "stream_tokens": [],
            "error": None,
            "human_feedback": None,
            "current_node": "",
        }

        import asyncio

        yield _sse_event({"event": "start", "thread_id": thread_id})

        # Run graph in thread pool so we don't block the event loop
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self.graph.invoke(initial_state, config),
            )
        except Exception as exc:
            yield _sse_event({"event": "error", "message": str(exc)})
            return

        # After invoke pauses, fetch the state and emit the brand brief
        snapshot = self.graph.get_state(config)
        state = dict(snapshot.values) if snapshot.values else {}
        brief = state.get("brand_brief") or {}
        tokens = state.get("stream_tokens") or []

        for token in tokens:
            yield _sse_event({"event": "token", "text": token})
            await asyncio.sleep(0.01)

        yield _sse_event({
            "event": "paused",
            "thread_id": thread_id,
            "next_node": list(snapshot.next)[0] if snapshot.next else None,
            "brand_brief": brief,
            "search_queries": state.get("search_queries", []),
        })
