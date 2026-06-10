"""Creator Scout API — FastAPI application.

Replaces the stdlib http.server implementation with full async support
required for LangGraph (PostgresSaver, astream) and SSE streaming.

All existing /v1/ routes are preserved 1-to-1.
New /v1/graph/* routes are in graph_routes.py.
"""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from creator_scout.config import load_env
from creator_scout.discovery.auth import authenticate_api_key
from creator_scout.discovery.service import DiscoveryService
from creator_scout.discovery.store import DiscoveryStore
from creator_scout.outreach.service import verify_webhook_signature

load_env()

# ─── App lifecycle ────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise shared resources on startup; clean up on shutdown."""
    store = DiscoveryStore()
    service = DiscoveryService(store)
    app.state.store = store
    app.state.service = service
    yield
    store.close()


app = FastAPI(
    title="Creator Scout API",
    version="0.2.0",
    description="AI-powered creator discovery, matching, and outreach API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Import and mount graph routes ────────────────────────────────────────────

from apps.api.graph_routes import router as graph_router  # noqa: E402
app.include_router(graph_router)


# ─── Auth dependency ──────────────────────────────────────────────────────────

def _get_api_key(
    authorization: Annotated[str | None, Header(alias="authorization")] = None,
    x_api_key: Annotated[str | None, Header(alias="x-api-key")] = None,
) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return x_api_key


def _get_store(request: Request) -> DiscoveryStore:
    return request.app.state.store


def _get_service(request: Request) -> DiscoveryService:
    return request.app.state.service


def _require_principal(
    request: Request,
    api_key: str | None = Depends(_get_api_key),
):
    store = _get_store(request)
    principal = authenticate_api_key(store, api_key)
    if principal is None:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return principal


# ─── Error handlers ───────────────────────────────────────────────────────────

@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    return JSONResponse(status_code=402, content={"error": {"message": str(exc), "status": 402}})


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"ok": True}


# ─── GET routes ───────────────────────────────────────────────────────────────

@app.get("/v1/usage")
async def get_usage(
    request: Request,
    principal=Depends(_require_principal),
):
    return _get_service(request).usage(principal)


@app.get("/v1/outreach/config")
async def get_outreach_config(
    request: Request,
    principal=Depends(_require_principal),
):
    return _get_service(request).outreach_config(principal)


@app.get("/v1/campaigns/{campaign_id}/creators")
async def list_campaign_creators(
    campaign_id: str,
    request: Request,
    principal=Depends(_require_principal),
    limit: int = 50,
):
    payload = _get_service(request).list_campaign_creators(campaign_id, principal, limit=limit)
    if payload is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return payload


@app.get("/v1/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    request: Request,
    principal=Depends(_require_principal),
):
    payload = _get_service(request).get_campaign(campaign_id, principal)
    if payload is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return payload


@app.get("/v1/jobs/{job_id}")
async def get_job(
    job_id: str,
    request: Request,
    principal=Depends(_require_principal),
):
    payload = _get_service(request).job_status(job_id, principal)
    if payload is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return payload


@app.get("/v1/brands/{brand_id}")
async def get_brand(
    brand_id: str,
    request: Request,
    principal=Depends(_require_principal),
):
    payload = _get_service(request).get_brand(brand_id, principal)
    if payload is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return payload


@app.get("/v1/creators/{creator_id}")
async def get_creator(
    creator_id: str,
    request: Request,
    principal=Depends(_require_principal),
):
    payload = _get_service(request).get_creator(creator_id, principal)
    if payload is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    return payload


# ─── POST routes ──────────────────────────────────────────────────────────────

@app.post("/v1/webhooks/autosend")
async def autosend_webhook(request: Request):
    body_bytes = await request.body()
    payload = {}
    try:
        import json
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    secret = os.environ.get("AUTOSEND_WEBHOOK_SECRET", "").strip()
    if secret:
        signature = (
            request.headers.get("x-autosend-signature")
            or request.headers.get("X-AutoSend-Signature")
            or ""
        )
        if not signature or not verify_webhook_signature(body_bytes, signature, secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return _get_service(request).handle_autosend_webhook(payload)


@app.post("/v1/billing/webhook")
async def billing_webhook(request: Request):
    body_bytes = await request.body()
    try:
        return _get_service(request).handle_billing_webhook(body_bytes, dict(request.headers))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/v1/discovery/search")
async def discovery_search(
    request: Request,
    principal=Depends(_require_principal),
):
    payload = await request.json()
    return _get_service(request).search(payload, principal)


@app.post("/v1/brand-scans")
async def brand_scan(
    request: Request,
    principal=Depends(_require_principal),
):
    payload = await request.json()
    result = _get_service(request).scan_brand(payload, principal)
    return JSONResponse(
        status_code=202 if payload.get("enqueue_discovery") else 200,
        content=result,
    )


@app.post("/v1/campaigns")
async def create_campaign(
    request: Request,
    principal=Depends(_require_principal),
):
    payload = await request.json()
    return JSONResponse(
        status_code=202,
        content=_get_service(request).create_campaign(payload, principal),
    )


@app.post("/v1/campaigns/{campaign_id}/creators/{creator_id}/outreach/send")
async def send_outreach(
    campaign_id: str,
    creator_id: str,
    request: Request,
    principal=Depends(_require_principal),
):
    payload = await request.json()
    response = _get_service(request).send_campaign_creator_outreach(
        campaign_id, creator_id, payload, principal
    )
    if response is None:
        raise HTTPException(status_code=404, detail="Campaign creator not found")
    return response


@app.post("/v1/campaigns/{campaign_id}/shortlist")
async def build_shortlist(
    campaign_id: str,
    request: Request,
    principal=Depends(_require_principal),
):
    payload = await request.json()
    response = _get_service(request).build_campaign_shortlist(campaign_id, payload, principal)
    if response is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return response


@app.post("/v1/campaigns/{campaign_id}/export")
async def export_campaign(
    campaign_id: str,
    request: Request,
    principal=Depends(_require_principal),
):
    response = _get_service(request).export_campaign_shortlist(campaign_id, principal)
    if response is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return response


@app.post("/v1/discovery/refresh")
async def discovery_refresh(
    request: Request,
    principal=Depends(_require_principal),
):
    payload = await request.json()
    return JSONResponse(
        status_code=202,
        content=_get_service(request).refresh(payload, principal),
    )


@app.post("/v1/discovery/ingest-query")
async def ingest_query(
    request: Request,
    principal=Depends(_require_principal),
):
    payload = await request.json()
    return JSONResponse(
        status_code=202,
        content=_get_service(request).ingest_query(payload, principal),
    )


@app.post("/v1/billing/checkout")
async def billing_checkout(
    request: Request,
    principal=Depends(_require_principal),
):
    payload = await request.json()
    return _get_service(request).create_billing_checkout(payload, principal)


@app.post("/v1/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    request: Request,
    principal=Depends(_require_principal),
):
    response = _get_service(request).retry_job(job_id, principal)
    if response is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(status_code=202, content=response)


# ─── Settings & Developer Keys routes ─────────────────────────────────────────

def _execute_db_update(query: str, params: tuple) -> None:
    import subprocess
    import psycopg

    db_url = (
        os.environ.get("INSFORGE_DB_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or ""
    ).strip()

    if db_url:
        if db_url.startswith("postgres://"):
            db_url = "postgresql" + db_url[8:]
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
    else:
        # Fallback to CLI database query execution
        formatted_query = query
        for param in params:
            escaped = str(param).replace("'", "''")
            formatted_query = formatted_query.replace("%s", f"'{escaped}'", 1)

        cmd = ["npx", "-y", "@insforge/cli", "db", "query", formatted_query]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"CLI query failed: {res.stderr or res.stdout}")


@app.get("/v1/settings/developer-keys")
async def get_settings_developer_keys(
    user_id: str,
    request: Request,
    principal=Depends(_require_principal),
):
    store = _get_store(request)
    keys = store._request(
        "GET",
        f"/api/database/records/developer_api_keys?org_id=eq.{user_id}&revoked_at=is.null",
    )
    used = store.current_credit_usage(user_id)
    limit = 1000.0
    if keys:
        limit = float(keys[0].get("monthly_credit_limit", 1000.0))
    return {
        "data": {
            "keys": [
                {
                    "id": k["id"],
                    "name": k["name"],
                    "scopes": k.get("scopes", ["discovery:read"]),
                    "rate_limit_per_minute": k.get("rate_limit_per_minute", 60),
                    "monthly_credit_limit": float(k["monthly_credit_limit"]),
                    "created_at": k["created_at"],
                }
                for k in keys
            ],
            "credits": {
                "used": used,
                "limit": limit,
                "remaining": max(0.0, limit - used),
            }
        }
    }


@app.post("/v1/settings/developer-keys")
async def create_settings_developer_key(
    request: Request,
    principal=Depends(_require_principal),
):
    payload = await request.json()
    user_id = payload.get("user_id")
    name = payload.get("name")
    if not user_id or not name:
        raise HTTPException(status_code=400, detail="Missing user_id or name")

    store = _get_store(request)
    from creator_scout.discovery.auth import provision_api_key

    key_id, plain_key = provision_api_key(
        store,
        org_id=user_id,
        name=name,
        scopes=["discovery:read", "discovery:write"],
        monthly_credit_limit=1000.0,
    )
    return {
        "data": {
            "id": key_id,
            "plain_key": plain_key,
        }
    }


@app.delete("/v1/settings/developer-keys/{key_id}")
async def revoke_settings_developer_key(
    key_id: str,
    user_id: str,
    request: Request,
    principal=Depends(_require_principal),
):
    store = _get_store(request)
    from creator_scout.discovery.models import utc_now
    now_str = utc_now()

    store._request(
        "PATCH",
        f"/api/database/records/developer_api_keys?id=eq.{key_id}&org_id=eq.{user_id}",
        json_data={"revoked_at": now_str},
    )
    return {"success": True}


@app.post("/v1/settings/profile")
async def update_settings_profile(
    request: Request,
    principal=Depends(_require_principal),
):
    payload = await request.json()
    user_id = payload.get("user_id")
    name = payload.get("name")
    email = payload.get("email")
    if not user_id or not name or not email:
        raise HTTPException(status_code=400, detail="Missing user_id, name, or email")

    import json
    profile_name_json = json.dumps(name)
    query = """
    UPDATE auth.users 
    SET email = %s, profile = jsonb_set(COALESCE(profile, '{}'::jsonb), '{name}', %s::jsonb) 
    WHERE id = %s
    """
    params = (email, profile_name_json, user_id)

    try:
        _execute_db_update(query, params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database update failed: {exc}")

    return {"success": True}


# ─── PATCH routes ─────────────────────────────────────────────────────────────

@app.patch("/v1/campaigns/{campaign_id}/creators/{creator_id}")
async def update_campaign_creator(
    campaign_id: str,
    creator_id: str,
    request: Request,
    principal=Depends(_require_principal),
):
    payload = await request.json()
    response = _get_service(request).update_campaign_creator(
        campaign_id, creator_id, payload, principal
    )
    if response is None:
        raise HTTPException(status_code=404, detail="Campaign creator not found")
    return response


# ─── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    reload = os.environ.get("RELOAD", "0") == "1"
    print(f"Creator Scout API running at http://{host}:{port}")
    uvicorn.run(
        "apps.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
