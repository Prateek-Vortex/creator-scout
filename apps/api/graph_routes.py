"""LangGraph campaign graph API routes.

Endpoints:
  POST /v1/graph/run              — Start a new campaign graph run (returns thread_id)
  POST /v1/graph/run/{id}/resume  — Resume after a HIL gate
  GET  /v1/graph/run/{id}/status  — Poll current run status
  GET  /v1/graph/run/{id}/stream  — SSE stream brand-scan tokens (EventSource)

InsForge Realtime notification:
  When the graph pauses at a HIL gate, this module publishes a realtime
  broadcast so the frontend can update without polling.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/graph", tags=["graph"])

# ─── Shared GraphRunner singleton ─────────────────────────────────────────────

_runner = None


def _get_runner():
    global _runner  # noqa: PLW0603
    if _runner is None:
        from creator_scout.graph.runner import GraphRunner
        _runner = GraphRunner()
    return _runner


# ─── Auth helper (mirrors main.py) ────────────────────────────────────────────

def _get_api_key(
    authorization: Annotated[str | None, Header(alias="authorization")] = None,
    x_api_key: Annotated[str | None, Header(alias="x-api-key")] = None,
) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return x_api_key


def _require_api_key(api_key: str | None = Depends(_get_api_key)) -> str:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    return api_key


# ─── InsForge Realtime helper ─────────────────────────────────────────────────

async def _notify_realtime(thread_id: str, event: str, payload: dict) -> None:
    """Publish a broadcast to the InsForge Realtime channel for this run.

    Channel: ``graph_runs:{thread_id}``
    The frontend subscribes via the @insforge/sdk realtime client.
    """
    insforge_url = os.environ.get("INSFORGE_API_BASE_URL", "").rstrip("/")
    insforge_key = os.environ.get("INSFORGE_API_KEY", "")
    if not insforge_url or not insforge_key:
        return  # Realtime not configured — silently skip

    import httpx
    channel = f"graph_runs:{thread_id}"
    body = {"channel": channel, "event": event, "payload": payload}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{insforge_url}/api/realtime/broadcast",
                json=body,
                headers={"Authorization": f"Bearer {insforge_key}"},
            )
    except Exception as exc:
        logger.warning("[graph_routes] Realtime notify failed: %s", exc)


# ─── Request / Response models ────────────────────────────────────────────────

class StartRunRequest(BaseModel):
    campaign_id: str
    brand_url: str
    goal: str = "ugc"
    geo: str = "India"
    org_id: str | None = None


class ResumeRunRequest(BaseModel):
    approved: bool = True
    feedback: str = ""


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/run", status_code=202)
async def start_graph_run(
    body: StartRunRequest,
    api_key: str = Depends(_require_api_key),
):
    """Start a new campaign graph run.

    The graph runs brand_scan_node then PAUSES at query_planner_node
    (HIL Gate 1) waiting for human approval of the extracted brand brief.

    Returns ``{ "thread_id": "..." }`` immediately (non-blocking via thread pool).
    """
    runner = _get_runner()

    def _start():
        return runner.start_campaign_run(
            campaign_id=body.campaign_id,
            brand_url=body.brand_url,
            goal=body.goal,
            geo=body.geo,
            org_id=body.org_id,
        )

    try:
        thread_id = await asyncio.get_event_loop().run_in_executor(None, _start)
    except Exception as exc:
        logger.error("[graph_routes] start error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # Notify frontend via Realtime that graph is paused at Gate 1
    status = runner.get_run_status(thread_id)
    asyncio.create_task(
        _notify_realtime(
            thread_id,
            "graph.paused",
            {
                "thread_id": thread_id,
                "next_node": status.get("next_node"),
                "brand_brief": status.get("brand_brief"),
                "search_queries": status.get("state", {}).get("search_queries", []),
            },
        )
    )

    return {"thread_id": thread_id, "status": "paused", "next_node": status.get("next_node")}


@router.post("/run/{thread_id}/resume")
async def resume_graph_run(
    thread_id: str,
    body: ResumeRunRequest,
    api_key: str = Depends(_require_api_key),
):
    """Resume a graph run after a HIL gate.

    Pass ``approved: true`` to continue to the next stage,
    or ``approved: false`` to reject and terminate the run.

    Optional ``feedback`` (plain text or JSON) is available to nodes.
    """
    runner = _get_runner()

    def _resume():
        return runner.resume_run(
            thread_id,
            approved=body.approved,
            feedback=body.feedback,
        )

    try:
        result = await asyncio.get_event_loop().run_in_executor(None, _resume)
    except Exception as exc:
        logger.error("[graph_routes] resume error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # Notify frontend of new paused state (or completion)
    status = runner.get_run_status(thread_id)
    event = "graph.paused" if status.get("paused") else "graph.completed"
    asyncio.create_task(
        _notify_realtime(
            thread_id,
            event,
            {
                "thread_id": thread_id,
                "next_node": status.get("next_node"),
                "shortlist": status.get("shortlist", []),
                "outreach_drafts": status.get("outreach_drafts", []),
                "error": status.get("error"),
            },
        )
    )

    return {**result, "run_status": status}


@router.get("/run/{thread_id}/status")
async def get_graph_status(
    thread_id: str,
    api_key: str = Depends(_require_api_key),
):
    """Poll the current status of a graph run.

    Response:
    ```json
    {
      "thread_id": "...",
      "paused": true,
      "current_node": "shortlist_node",
      "next_node": "outreach_draft_node",
      "brand_brief": {...},
      "shortlist": [...],
      "outreach_drafts": [...],
      "error": null
    }
    ```
    """
    runner = _get_runner()
    try:
        return runner.get_run_status(thread_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/run/{thread_id}/stream")
async def stream_graph_run(
    thread_id: str | None = None,
    campaign_id: str | None = None,
    brand_url: str | None = None,
    goal: str = "ugc",
    geo: str = "India",
    org_id: str | None = None,
    api_key: str = Depends(_require_api_key),
):
    """Server-Sent Events endpoint for streaming brand-scan tokens.

    Usage (EventSource):
    ```js
    const es = new EventSource(
      `/v1/graph/run/stream?brand_url=...&campaign_id=...&api_key=...`
    );
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.event === "token") console.log(data.text);
      if (data.event === "paused") { /* show HIL gate UI */ }
    };
    ```

    Events emitted:
    - ``{"event": "start", "thread_id": "..."}``
    - ``{"event": "token", "text": "..."}``   (one or more)
    - ``{"event": "paused", "thread_id": "...", "next_node": "...", "brand_brief": {...}}``
    - ``{"event": "error", "message": "..."}``
    """
    if not brand_url or not campaign_id:
        raise HTTPException(status_code=422, detail="brand_url and campaign_id are required")

    runner = _get_runner()

    async def generate():
        async for chunk in runner.stream_brand_scan(
            campaign_id=campaign_id,
            brand_url=brand_url,
            goal=goal,
            geo=geo,
            org_id=org_id,
        ):
            yield chunk
            await asyncio.sleep(0)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
