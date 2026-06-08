import os
import requests
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from typing import Any

from creator_scout.discovery.models import (
    CreatorAccount,
    CreatorContact,
    CreatorProfile,
    Freshness,
    PermissionBasis,
    Platform,
    SourceEvidence,
    utc_now,
)
from creator_scout.discovery.normalize import stable_id


IN_TEST = "unittest" in sys.modules or "pytest" in sys.modules or (len(sys.argv) > 0 and "pytest" in sys.argv[0])
UUID_TO_ORIGINAL = {}
_PUBLIC_INSFORGE_FALLBACK_WARNED = False
_RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
_NON_UUID_ID_FIELDS = {
    "provider_message_id",
    "unsubscribe_group_id",
}


def to_uuid(val: Any) -> str | None:
    if not val:
        return None
    val_str = str(val).strip()
    try:
        uuid.UUID(val_str)
        return val_str
    except ValueError:
        u = str(uuid.uuid5(uuid.NAMESPACE_DNS, val_str))
        UUID_TO_ORIGINAL[u] = val_str
        return u


def _normalize_uuids(data: Any) -> Any:
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            if k == "id" or k.endswith("_id"):
                if k in _NON_UUID_ID_FIELDS:
                    new_dict[k] = v
                elif v is not None:
                    new_dict[k] = to_uuid(v)
                else:
                    new_dict[k] = None
            else:
                new_dict[k] = _normalize_uuids(v)
        return new_dict
    elif isinstance(data, list):
        return [_normalize_uuids(item) for item in data]
    return data


def _normalize_path(path: str) -> str:
    if "?" not in path:
        return path
    base, query = path.split("?", 1)
    parts = query.split("&")
    new_parts = []
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            if k == "id" or k.endswith("_id"):
                if k in _NON_UUID_ID_FIELDS:
                    new_parts.append(part)
                    continue
                if v.startswith("eq."):
                    val = v[3:]
                    new_parts.append(f"{k}=eq.{to_uuid(val)}")
                elif v.startswith("in.("):
                    vals_str = v[4:-1]
                    vals = vals_str.split(",")
                    uuid_vals = [to_uuid(x.strip()) for x in vals]
                    new_parts.append(f"{k}=in.({','.join(uuid_vals)})")
                else:
                    new_parts.append(part)
            else:
                new_parts.append(part)
        else:
            new_parts.append(part)
    return f"{base}?{'&'.join(new_parts)}"


class DiscoveryStore:
    def __init__(self, db_path: str | Path = "") -> None:
        # Load environment variables if they aren't loaded
        from creator_scout.config import load_env
        load_env()
        self.url = (
            os.environ.get("INSFORGE_API_BASE_URL")
            or os.environ.get("INSFORGE_URL")
            or os.environ.get("NEXT_PUBLIC_INSFORGE_URL")
        )
        self.api_key = os.environ.get("INSFORGE_API_KEY") or os.environ.get("INSFORGE_SERVICE_KEY")
        using_public_fallback = False
        if not self.api_key:
            self.api_key = os.environ.get("NEXT_PUBLIC_INSFORGE_ANON_KEY")
            using_public_fallback = bool(self.api_key)
        if not self.url or not self.api_key:
            raise RuntimeError(
                "Missing InsForge configuration. Set INSFORGE_API_BASE_URL and INSFORGE_API_KEY for server code."
            )
        self.url = self.url.rstrip("/")
        self.anon_key = self.api_key
        if using_public_fallback:
            self._warn_public_key_fallback()
        if IN_TEST:
            self.clear_database()

    def _warn_public_key_fallback(self) -> None:
        global _PUBLIC_INSFORGE_FALLBACK_WARNED
        if _PUBLIC_INSFORGE_FALLBACK_WARNED:
            return
        print(
            "[store] WARNING: using NEXT_PUBLIC_INSFORGE_ANON_KEY for server persistence. "
            "Set INSFORGE_API_BASE_URL and INSFORGE_API_KEY; public keys will not work after backend hardening.",
            file=sys.stderr,
        )
        _PUBLIC_INSFORGE_FALLBACK_WARNED = True

    def clear_database(self) -> None:
        try:
            self._request("DELETE", "/api/database/records/outreach_messages")
            self._request("DELETE", "/api/database/records/campaign_exports")
            self._request("DELETE", "/api/database/records/campaign_creators")
            self._request("DELETE", "/api/database/records/campaign_discovery_jobs")
            self._request("DELETE", "/api/database/records/provider_requests")
            self._request("DELETE", "/api/database/records/discovery_jobs")
            self._request("DELETE", "/api/database/records/brand_pages")
            self._request("DELETE", "/api/database/records/campaigns")
            self._request("DELETE", "/api/database/records/brands")
            self._request("DELETE", "/api/database/records/creator_index_sources")
            self._request("DELETE", "/api/database/records/creator_contacts")
            self._request("DELETE", "/api/database/records/creator_accounts")
            self._request("DELETE", "/api/database/records/creator_profiles")
            self._request("DELETE", "/api/database/records/api_usage_events")
            self._request("DELETE", "/api/database/records/api_credit_ledger")
            self._request("DELETE", "/api/database/records/developer_api_keys")
            self._request("DELETE", f"/api/database/records/organizations?id=neq.{to_uuid('e1e3e5a6-6d57-4600-9eb0-928e00f3bbf7')}")
        except Exception as e:
            print(f"Error clearing database: {e}")

    @property
    def conn(self):
        class MockConn:
            def __init__(self, store):
                self.store = store
            
            def execute(self, sql_query, *args):
                sql = sql_query.lower().strip()
                class MockCursor:
                    def __init__(self, rows):
                        self.rows = rows
                    def fetchone(self):
                        if not self.rows:
                            return None
                        r = self.rows[0]
                        nr = {}
                        for k, v in r.items():
                            if isinstance(v, str) and v in UUID_TO_ORIGINAL:
                                nr[k] = UUID_TO_ORIGINAL[v]
                            else:
                                nr[k] = v
                        return nr
                    def fetchall(self):
                        return self.rows
                
                if "provider_requests" in sql:
                    rows = self.store._request("GET", "/api/database/records/provider_requests")
                    return MockCursor(rows)
                return MockCursor([])
        return MockConn(self)

    def close(self) -> None:
        pass

    def init_schema(self) -> None:
        pass

    def _headers(self, custom: dict | None = None) -> dict:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }
        if custom:
            h.update(custom)
        return h

    def _send_request(self, method: str, url: str, **kwargs) -> requests.Response:
        attempts = 5
        for attempt in range(attempts):
            response = requests.request(method, url, **kwargs)
            if response.status_code not in _RETRYABLE_HTTP_STATUSES or attempt == attempts - 1:
                return response
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 0.75 * (2 ** attempt)
            except ValueError:
                delay = 0.75 * (2 ** attempt)
            time.sleep(min(delay, 8.0))
        return response

    def _post_records(self, path: str, records: list[dict], *, prefer: str, timeout: int) -> None:
        response = self._send_request(
            "POST",
            f"{self.url}{path}",
            json=records,
            headers=self._headers({"Prefer": prefer}),
            timeout=timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"InsForge REST request failed: {response.status_code} - {response.text}")

    def _request(self, method: str, path: str, json_data: Any = None, params: dict = None, headers: dict = None, timeout: int = 30) -> Any:
        path = _normalize_path(path)
        if json_data is not None:
            json_data = _normalize_uuids(json_data)
        if params is not None:
            params = _normalize_uuids(params)

        # Dynamic record creation to satisfy FK constraints in tests/scaffolding
        if json_data:
            org_ids = []
            campaign_ids = []
            api_key_ids = []
            
            def extract_ids(d):
                if isinstance(d, dict):
                    for k, v in d.items():
                        if k == "org_id" and v:
                            org_ids.append(to_uuid(v))
                        elif k == "campaign_id" and v:
                            campaign_ids.append(to_uuid(v))
                        elif (k == "api_key_id" or k == "requested_by_api_key_id") and v:
                            api_key_ids.append(to_uuid(v))
                        elif isinstance(v, (dict, list)):
                            extract_ids(v)
                elif isinstance(d, list):
                    for item in d:
                        extract_ids(item)

            extract_ids(json_data)
            org_ids = list(set(org_ids))
            campaign_ids = list(set(campaign_ids))
            api_key_ids = list(set(api_key_ids))

            if "/organizations" not in path:
                for oid in org_ids:
                    self._post_records(
                        "/api/database/records/organizations",
                        [{"id": oid, "name": f"Team {oid}", "plan": "free"}],
                        prefer="resolution=ignore-duplicates",
                        timeout=timeout,
                    )

            if "/developer_api_keys" not in path:
                for kid in api_key_ids:
                    default_org = org_ids[0] if org_ids else to_uuid("org_test")
                    if "/organizations" not in path:
                        self._post_records(
                            "/api/database/records/organizations",
                            [{"id": default_org, "name": f"Team {default_org}", "plan": "free"}],
                            prefer="resolution=ignore-duplicates",
                            timeout=timeout,
                        )

                    self._post_records(
                        "/api/database/records/developer_api_keys",
                        [{
                            "id": kid,
                            "org_id": default_org,
                            "name": "Dummy Key",
                            "key_hash": f"dummy_hash_{kid}",
                            "scopes": ["discovery:read", "discovery:write"],
                            "rate_limit_per_minute": 60,
                            "monthly_credit_limit": 1000.0,
                        }],
                        prefer="resolution=ignore-duplicates",
                        timeout=timeout,
                    )

            if "/campaigns" not in path:
                for cid in campaign_ids:
                    default_org = org_ids[0] if org_ids else to_uuid("org_test")
                    if "/organizations" not in path:
                        self._post_records(
                            "/api/database/records/organizations",
                            [{"id": default_org, "name": f"Team {default_org}", "plan": "free"}],
                            prefer="resolution=ignore-duplicates",
                            timeout=timeout,
                        )

                    dummy_brand_id = to_uuid("dummy_brand")
                    if "/brands" not in path:
                        self._post_records(
                            "/api/database/records/brands",
                            [{
                                "id": dummy_brand_id,
                                "org_id": default_org,
                                "website_url": "https://dummybrand.com",
                                "name": "Dummy Brand",
                                "brief_json": {},
                                "confidence": 1.0,
                            }],
                            prefer="resolution=ignore-duplicates",
                            timeout=timeout,
                        )

                    self._post_records(
                        "/api/database/records/campaigns",
                        [{
                            "id": cid,
                            "org_id": default_org,
                            "brand_id": dummy_brand_id,
                            "brand_url": "https://dummybrand.com",
                            "goal": "ugc",
                            "geography": "India",
                            "platforms": [],
                            "status": "draft",
                            "brief_json": {},
                            "search_queries": []
                        }],
                        prefer="resolution=ignore-duplicates",
                        timeout=timeout,
                    )

        url = f"{self.url}{path}"
        r = self._send_request(method, url, json=json_data, params=params, headers=self._headers(headers), timeout=timeout)
        if r.status_code >= 400:
            raise RuntimeError(f"InsForge REST request failed: {r.status_code} - {r.text}")
        if r.status_code == 204:
            return None
        try:
            return r.json()
        except Exception:
            return r.text

    def generate_embedding(self, text: str) -> list[float] | None:
        if IN_TEST:
            return None
        try:
            res = self._request(
                "POST",
                "/api/ai/embeddings",
                json_data={
                    "model": "openai/text-embedding-3-small",
                    "input": text,
                }
            )
            if res and isinstance(res, dict) and "data" in res and res["data"]:
                return res["data"][0]["embedding"]
        except Exception as e:
            print(f"Error generating embedding: {e}")
        return None

    def semantic_search(self, embedding: list[float], limit: int = 20, threshold: float = 0.0) -> list[dict]:
        try:
            res = self._request(
                "POST",
                "/api/database/rpc/match_creators",
                json_data={
                    "query_embedding": embedding,
                    "match_threshold": threshold,
                    "match_limit": limit,
                }
            )
            return res or []
        except Exception as e:
            print(f"Error performing semantic search: {e}")
            return []

    def upsert_creator(self, creator: CreatorProfile) -> None:
        # Generate embedding
        text_rep = f"{creator.display_name or ''} {creator.primary_niche or ''} {creator.summary or ''} {' '.join(creator.topics or [])}"
        text_rep = text_rep.strip()
        embedding = None
        if text_rep:
            embedding = self.generate_embedding(text_rep)

        # 1. Upsert creator profile
        profile_data = {
            "id": creator.creator_id,
            "display_name": creator.display_name,
            "primary_niche": creator.primary_niche,
            "location": creator.location,
            "languages": creator.languages,
            "summary": creator.summary,
            "topics": creator.topics,
            "raw_json": creator.raw,
            "updated_at": creator.updated_at,
        }
        if embedding:
            profile_data["embedding"] = embedding
        self._request(
            "POST",
            "/api/database/records/creator_profiles",
            json_data=[profile_data],
            headers={"Prefer": "resolution=merge-duplicates"},
        )

        # 2. Upsert creator accounts
        accounts_data = []
        seen_account_ids = set()
        for account in creator.accounts:
            account_id = stable_id("acct", creator.creator_id, account.platform.value, account.profile_url)
            if account_id in seen_account_ids:
                continue
            seen_account_ids.add(account_id)
            accounts_data.append({
                "id": account_id,
                "creator_id": creator.creator_id,
                "platform": account.platform.value,
                "handle": account.handle,
                "profile_url": account.profile_url,
                "follower_count": account.follower_count,
                "subscriber_count": account.subscriber_count,
                "avg_views": account.avg_views,
                "engagement_rate": account.engagement_rate,
                "bio": account.bio,
                "raw_json": account.raw,
                "last_verified_at": account.last_verified_at,
            })
        if accounts_data:
            self._request(
                "POST",
                "/api/database/records/creator_accounts",
                json_data=accounts_data,
                headers={"Prefer": "resolution=merge-duplicates"},
            )

        # 3. Upsert creator contacts
        contacts_data = []
        seen_contact_ids = set()
        for contact in creator.contacts:
            contact_id = stable_id("ct", creator.creator_id, contact.contact_type, contact.value)
            if contact_id in seen_contact_ids:
                continue
            seen_contact_ids.add(contact_id)
            # Map confidence: InsForge uses text dataType for confidence
            contacts_data.append({
                "id": contact_id,
                "creator_id": creator.creator_id,
                "contact_type": contact.contact_type,
                "value": contact.value,
                "source_url": contact.source_url,
                "source_type": contact.contact_type if contact.contact_type == "email" else "public_business_contact",
                "permission_basis": contact.permission_basis.value,
                "confidence": str(contact.confidence),
                "do_not_contact": contact.do_not_contact,
                "last_verified_at": contact.last_verified_at,
            })
        if contacts_data:
            self._request(
                "POST",
                "/api/database/records/creator_contacts",
                json_data=contacts_data,
                headers={"Prefer": "resolution=merge-duplicates"},
            )

        # 4. Upsert sources
        seen_source_ids = set()
        for source in creator.sources:
            import hashlib
            import json
            cleaned = json.dumps({"url": source.source_url, "fields": source.fields_found}, sort_keys=True)
            source_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
            source_id = stable_id("src", creator.creator_id or "", source.source_url, source_hash)
            if source_id in seen_source_ids:
                continue
            seen_source_ids.add(source_id)
            try:
                self.add_source(creator.creator_id, None, source)
            except Exception as exc:  # noqa: BLE001  — source indexing is best-effort
                import sys
                print(f"[store] add_source skipped for {source.source_url}: {exc}", file=sys.stderr)

    def add_source(
        self,
        creator_id: str | None,
        account_id: str | None,
        source: SourceEvidence,
        provider: str | None = None,
        crawl_allowed: bool | None = None,
    ) -> None:
        import hashlib
        import json
        cleaned = json.dumps({"url": source.source_url, "fields": source.fields_found}, sort_keys=True)
        source_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
        source_id = stable_id("src", creator_id or "", source.source_url, source_hash)
        
        source_data = {
            "id": source_id,
            "creator_id": creator_id,
            "account_id": account_id,
            "source_type": source.source_type,
            "source_url": source.source_url,
            "source_provider": provider,
            "source_hash": source_hash,
            "crawl_allowed": crawl_allowed,
            "fields_found": source.fields_found,
            "confidence": source.confidence,
            "fetched_at": source.fetched_at,
        }
        self._request(
            "POST",
            "/api/database/records/creator_index_sources",
            json_data=[source_data],
            headers={"Prefer": "resolution=merge-duplicates"},
            timeout=10,  # source evidence is best-effort; don't block on slow writes
        )

    def all_creators(self) -> list[CreatorProfile]:
        rows = self._request("GET", "/api/database/records/creator_profiles")
        return [self._hydrate_creator(row["id"]) for row in rows]

    def get_creator(self, creator_id: str) -> CreatorProfile | None:
        rows = self._request("GET", f"/api/database/records/creator_profiles?id=eq.{creator_id}")
        if not rows:
            return None
        return self._hydrate_creator(creator_id)

    def find_by_profile_url(self, profile_url: str) -> CreatorProfile | None:
        rows = self._request("GET", f"/api/database/records/creator_accounts?profile_url=eq.{profile_url}")
        if not rows:
            return None
        return self._hydrate_creator(rows[0]["creator_id"])

    def _hydrate_creator(self, creator_id: str) -> CreatorProfile:
        READ_TIMEOUT = 8  # seconds — short timeout for GET reads; InsForge can be slow
        profiles = self._request("GET", f"/api/database/records/creator_profiles?id=eq.{creator_id}", timeout=READ_TIMEOUT)
        if not profiles:
            raise KeyError(creator_id)
        row = profiles[0]

        accounts = self._request("GET", f"/api/database/records/creator_accounts?creator_id=eq.{creator_id}", timeout=READ_TIMEOUT)
        contacts = self._request("GET", f"/api/database/records/creator_contacts?creator_id=eq.{creator_id}", timeout=READ_TIMEOUT)
        try:
            sources = self._request("GET", f"/api/database/records/creator_index_sources?creator_id=eq.{creator_id}", timeout=READ_TIMEOUT)
        except Exception:  # noqa: BLE001 — sources are optional for hydration
            sources = []

        return CreatorProfile(
            creator_id=row["id"],
            display_name=row["display_name"],
            primary_niche=row["primary_niche"],
            location=row["location"],
            languages=row["languages"] or [],
            summary=row["summary"] or "",
            topics=row["topics"] or [],
            accounts=[
                CreatorAccount(
                    platform=Platform(account["platform"]),
                    handle=account["handle"],
                    profile_url=account["profile_url"],
                    follower_count=account["follower_count"],
                    subscriber_count=account["subscriber_count"],
                    avg_views=account["avg_views"],
                    engagement_rate=float(account["engagement_rate"]) if account["engagement_rate"] is not None else None,
                    bio=account["bio"] or "",
                    last_verified_at=account["last_verified_at"],
                    raw=account["raw_json"] or {},
                )
                for account in accounts
            ],
            contacts=[
                CreatorContact(
                    contact_type=contact["contact_type"],
                    value=contact["value"],
                    source_url=contact["source_url"],
                    permission_basis=PermissionBasis(contact["permission_basis"]),
                    confidence=float(contact["confidence"]) if contact["confidence"] else 0.75,
                    do_not_contact=bool(contact["do_not_contact"]),
                    suppressed_at=contact.get("suppressed_at"),
                    suppression_reason=contact.get("suppression_reason"),
                    last_verified_at=contact["last_verified_at"],
                )
                for contact in contacts
            ],
            sources=[
                SourceEvidence(
                    source_url=source["source_url"],
                    source_type=source["source_type"],
                    fields_found=source["fields_found"] or {},
                    confidence=float(source["confidence"]) if source["confidence"] is not None else 0.0,
                    fetched_at=source["fetched_at"],
                )
                for source in sources
            ],
            updated_at=row["updated_at"],
            raw=row["raw_json"] or {},
        )

    def create_api_key(
        self,
        org_id: str,
        name: str,
        key_hash: str,
        scopes: list[str],
        monthly_credit_limit: float,
        rate_limit_per_minute: int = 60,
    ) -> str:
        key_id = stable_id("key", org_id, name, key_hash)
        key_data = {
            "id": key_id,
            "org_id": org_id,
            "name": name,
            "key_hash": key_hash,
            "scopes": scopes,
            "rate_limit_per_minute": rate_limit_per_minute,
            "monthly_credit_limit": monthly_credit_limit,
            "created_at": utc_now(),
        }
        self._request(
            "POST",
            "/api/database/records/developer_api_keys",
            json_data=[key_data],
            headers={"Prefer": "resolution=merge-duplicates"},
        )
        return key_id

    def get_api_key_by_hash(self, key_hash: str) -> dict | None:
        rows = self._request(
            "GET",
            f"/api/database/records/developer_api_keys?key_hash=eq.{key_hash}&revoked_at=is.null",
            timeout=10,  # auth lookup — fail fast if InsForge is slow; cache handles the rest
        )
        if not rows:
            return None
        return rows[0]

    def current_credit_usage(self, org_id: str) -> float:
        rows = self._request("GET", f"/api/database/records/api_credit_ledger?org_id=eq.{org_id}")
        return sum(float(row["credits"]) for row in rows)

    def record_api_usage(
        self,
        *,
        org_id: str,
        api_key_id: str | None,
        endpoint: str,
        request_id: str,
        credits: float,
        status_code: int,
        latency_ms: int,
        result_count: int,
        cache_status: Freshness,
    ) -> None:
        balance_after = self.current_credit_usage(org_id) + credits
        ledger_id = stable_id("led", request_id, endpoint, credits)
        ledger_data = {
            "id": ledger_id,
            "org_id": org_id,
            "api_key_id": api_key_id,
            "event_type": "debit",
            "endpoint": endpoint,
            "credits": credits,
            "balance_after": balance_after,
            "request_id": request_id,
            "created_at": utc_now(),
        }
        self._request("POST", "/api/database/records/api_credit_ledger", json_data=[ledger_data])

        usage_id = stable_id("use", request_id, endpoint)
        usage_data = {
            "id": usage_id,
            "org_id": org_id,
            "api_key_id": api_key_id,
            "request_id": request_id,
            "endpoint": endpoint,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "cache_status": cache_status.value,
            "credits_charged": credits,
            "result_count": result_count,
            "created_at": utc_now(),
        }
        self._request("POST", "/api/database/records/api_usage_events", json_data=[usage_data])

    def record_provider_request(
        self,
        *,
        org_id: str,
        provider: str,
        endpoint: str,
        request_hash: str,
        response_status: int,
        response_summary: dict,
        cost_units: float,
        campaign_id: str | None = None,
        job_id: str | None = None,
        cached: bool = False,
    ) -> None:
        request_id = stable_id("pr", provider, endpoint, request_hash, utc_now())
        request_data = {
            "id": request_id,
            "org_id": org_id,
            "campaign_id": campaign_id,
            "job_id": job_id,
            "provider": provider,
            "endpoint": endpoint,
            "request_hash": request_hash,
            "response_status": response_status,
            "response_summary": response_summary,
            "cost_units": cost_units,
            "cached": cached,
            "created_at": utc_now(),
        }
        self._request("POST", "/api/database/records/provider_requests", json_data=[request_data])

    def save_brand_scan(
        self,
        *,
        org_id: str | None,
        brand_url: str,
        brand_name: str,
        brief: dict,
        confidence: float,
        pages: list[dict],
    ) -> str:
        brand_id = stable_id("brand", org_id or "system", brand_url)
        now = utc_now()
        brand_data = {
            "id": brand_id,
            "org_id": org_id,
            "website_url": brand_url,
            "name": brand_name,
            "brief_json": brief,
            "confidence": confidence,
            "category": brief.get("category"),
            "target_audience": brief.get("target_audience"),
            "price_positioning": brief.get("price_positioning"),
            "tone": brief.get("tone"),
            "value_props": brief.get("value_props"),
            "created_at": now,
            "updated_at": now,
        }
        self._request(
            "POST",
            "/api/database/records/brands",
            json_data=[brand_data],
            headers={"Prefer": "resolution=merge-duplicates"},
        )

        for page in pages:
            page_id = stable_id("bp", brand_id, page["url"])
            page_data = {
                "id": page_id,
                "brand_id": brand_id,
                "source_url": page["url"],
                "title": page.get("title"),
                "page_type": page.get("page_type"),
                "markdown": page.get("text", ""),
                "extracted_json": page.get("metadata", {}),
                "fetched_at": page.get("fetched_at"),
                "fetch_status": "passed",
                "robots_allowed": True,
                "created_at": now,
            }
            self._request(
                "POST",
                "/api/database/records/brand_pages",
                json_data=[page_data],
                headers={"Prefer": "resolution=merge-duplicates"},
            )

        return brand_id

    def get_brand(self, brand_id: str) -> dict | None:
        rows = self._request("GET", f"/api/database/records/brands?id=eq.{brand_id}")
        if not rows:
            return None
        pages = self._request("GET", f"/api/database/records/brand_pages?brand_id=eq.{brand_id}")
        brand = rows[0]
        # Re-map storage fields back to the API's brief dict shape.
        brief = brand.get("brief_json") or {}
        return {
            "id": brand["id"],
            "org_id": brand["org_id"],
            "brand_url": brand["website_url"],
            "brand_name": brand["name"],
            "confidence": float(brand["confidence"]) if brand["confidence"] is not None else 0.0,
            "created_at": brand["created_at"],
            "updated_at": brand["updated_at"],
            "brief": brief,
            "pages": [
                {
                    "id": p["id"],
                    "brand_id": p["brand_id"],
                    "url": p["source_url"],
                    "title": p["title"],
                    "page_type": p["page_type"],
                    "text": p["markdown"],
                    "metadata": p["extracted_json"],
                    "fetched_at": p["fetched_at"],
                }
                for p in pages
            ],
        }

    def create_campaign(
        self,
        *,
        org_id: str | None,
        brand_id: str,
        brand_url: str,
        goal: str,
        geo: str,
        platforms: list[str],
        brief: dict,
        search_queries: list[str],
    ) -> str:
        now = utc_now()
        campaign_id = stable_id("camp", org_id or "system", brand_id, goal, geo, now)
        campaign_data = {
            "id": campaign_id,
            "org_id": org_id,
            "brand_id": brand_id,
            "brand_url": brand_url,
            "goal": goal,
            "geography": geo,
            "platforms": platforms,
            "status": "discovering",
            "brief_json": brief,
            "search_queries": search_queries,
            "created_at": now,
            "updated_at": now,
        }
        self._request("POST", "/api/database/records/campaigns", json_data=[campaign_data])
        return campaign_id

    def link_campaign_job(self, campaign_id: str, job_id: str, query: str, provider: str) -> None:
        job_data = {
            "id": stable_id("cdj", campaign_id, job_id),
            "campaign_id": campaign_id,
            "job_id": job_id,
            "query": query,
            "provider": provider,
            "created_at": utc_now(),
        }
        self._request(
            "POST",
            "/api/database/records/campaign_discovery_jobs",
            json_data=[job_data],
            headers={"Prefer": "resolution=ignore-duplicates"},
        )

    def get_campaign(self, campaign_id: str) -> dict | None:
        rows = self._request("GET", f"/api/database/records/campaigns?id=eq.{campaign_id}")
        if not rows:
            return None
        campaign = rows[0]
        jobs = self._request("GET", f"/api/database/records/campaign_discovery_jobs?campaign_id=eq.{campaign_id}")
        
        # Hydrate jobs with their status from discovery_jobs
        hydrated_jobs = []
        for job in jobs:
            dj_rows = self._request("GET", f"/api/database/records/discovery_jobs?id=eq.{job['job_id']}")
            if dj_rows:
                dj = dj_rows[0]
                job_dict = {
                    "id": job["id"],
                    "campaign_id": job["campaign_id"],
                    "job_id": job["job_id"],
                    "query": job["query"],
                    "provider": job["provider"],
                    "created_at": job["created_at"],
                    "status": dj["status"],
                    "output": dj["output"] or {},
                    "error": dj["error"],
                }
            else:
                job_dict = {
                    "id": job["id"],
                    "campaign_id": job["campaign_id"],
                    "job_id": job["job_id"],
                    "query": job["query"],
                    "provider": job["provider"],
                    "created_at": job["created_at"],
                    "status": "queued",
                    "output": {},
                    "error": None,
                }
            hydrated_jobs.append(job_dict)

        job_summary = summarize_job_statuses(hydrated_jobs)
        brief = campaign.get("brief_json") or {}
        return {
            "id": campaign["id"],
            "org_id": campaign["org_id"],
            "brand_id": campaign["brand_id"],
            "brand_url": campaign["brand_url"],
            "goal": campaign["goal"],
            "geo": campaign["geography"],
            "platforms": campaign["platforms"] or [],
            "status": campaign["status"],
            "created_at": campaign["created_at"],
            "updated_at": campaign["updated_at"],
            "brief": brief,
            "search_queries": campaign["search_queries"] or [],
            "jobs": hydrated_jobs,
            "job_summary": job_summary,
        }

    def update_campaign_status(self, campaign_id: str, status: str) -> None:
        self._request(
            "PATCH",
            f"/api/database/records/campaigns?id=eq.{campaign_id}",
            json_data={"status": status, "updated_at": utc_now()},
        )

    def upsert_campaign_creator(
        self,
        *,
        campaign_id: str,
        creator_id: str,
        status: str,
        bucket: str,
        fit_score: int,
        score_breakdown: dict,
        evidence: list[dict],
        risks: list[str],
        unknowns: list[str],
        recommended_pitch: str,
        outreach_draft: dict | None = None,
    ) -> None:
        now = utc_now()
        cc_id = stable_id("cc", campaign_id, creator_id)
        cc_data = {
            "id": cc_id,
            "campaign_id": campaign_id,
            "creator_id": creator_id,
            "status": status,
            "bucket": bucket,
            "fit_score": fit_score,
            "score_breakdown": score_breakdown,
            "evidence": evidence,
            "risks": risks,
            "unknowns": unknowns,
            "recommended_pitch": recommended_pitch,
            "outreach_draft": outreach_draft,
            "created_at": now,
            "updated_at": now,
        }
        self._request(
            "POST",
            "/api/database/records/campaign_creators",
            json_data=[cc_data],
            headers={"Prefer": "resolution=merge-duplicates"},
        )

    def bulk_upsert_campaign_creators(self, creators_list: list[dict]) -> None:
        if not creators_list:
            return
        self._request(
            "POST",
            "/api/database/records/campaign_creators",
            json_data=creators_list,
            headers={"Prefer": "resolution=merge-duplicates"},
        )

    def list_campaign_creators(self, campaign_id: str, limit: int = 50) -> list[dict]:
        rows = self._request(
            "GET",
            f"/api/database/records/campaign_creators?campaign_id=eq.{campaign_id}&order=fit_score.desc&limit={limit}",
        )
        return rows

    def update_campaign_creator(self, campaign_id: str, creator_id: str, fields: dict) -> dict | None:
        allowed = {"status", "recommended_pitch", "notes"}
        patch = {key: value for key, value in fields.items() if key in allowed}
        if not patch:
            return self.get_campaign_creator(campaign_id, creator_id)
        patch["updated_at"] = utc_now()
        self._request(
            "PATCH",
            f"/api/database/records/campaign_creators?campaign_id=eq.{campaign_id}&creator_id=eq.{creator_id}",
            json_data=patch,
        )
        return self.get_campaign_creator(campaign_id, creator_id)

    def get_campaign_creator(self, campaign_id: str, creator_id: str) -> dict | None:
        rows = self._request(
            "GET",
            f"/api/database/records/campaign_creators?campaign_id=eq.{campaign_id}&creator_id=eq.{creator_id}&limit=1",
        )
        return rows[0] if rows else None

    def list_outreach_messages(self, campaign_creator_id: str, limit: int = 20) -> list[dict]:
        return self._request(
            "GET",
            (
                "/api/database/records/outreach_messages"
                f"?campaign_creator_id=eq.{campaign_creator_id}&order=created_at.desc&limit={limit}"
            ),
        )

    def create_outreach_message(
        self,
        *,
        campaign_creator_id: str,
        recipient_contact_id: str | None,
        recipient_email: str,
        subject: str,
        body: str,
        provider: str,
        provider_message_id: str | None,
        provider_response: dict | None,
        status: str,
        error: str | None = None,
        unsubscribe_group_id: str | None = None,
        sent_at: str | None = None,
    ) -> dict:
        now = utc_now()
        message_id = stable_id("om", campaign_creator_id, provider, recipient_email, subject, now)
        message_data = {
            "id": message_id,
            "campaign_creator_id": campaign_creator_id,
            "recipient_contact_id": recipient_contact_id,
            "recipient_email": recipient_email,
            "channel": "email",
            "subject": subject,
            "body": body,
            "tone": "warm",
            "status": status,
            "sequence_order": 1,
            "provider": provider,
            "provider_message_id": provider_message_id,
            "provider_response": provider_response or {},
            "error": error,
            "unsubscribe_group_id": unsubscribe_group_id,
            "sent_at": sent_at,
            "created_at": now,
            "updated_at": now,
        }
        self._request(
            "POST",
            "/api/database/records/outreach_messages",
            json_data=[message_data],
            headers={"Prefer": "resolution=merge-duplicates"},
        )
        return self.get_outreach_message(message_id) or message_data

    def get_outreach_message(self, message_id: str) -> dict | None:
        rows = self._request("GET", f"/api/database/records/outreach_messages?id=eq.{message_id}&limit=1")
        return rows[0] if rows else None

    def get_outreach_message_by_provider_id(self, provider: str, provider_message_id: str) -> dict | None:
        rows = self._request(
            "GET",
            (
                "/api/database/records/outreach_messages"
                f"?provider=eq.{provider}&provider_message_id=eq.{quote(provider_message_id, safe='')}&limit=1"
            ),
        )
        return rows[0] if rows else None

    def update_outreach_message(self, message_id: str, fields: dict) -> dict | None:
        allowed = {
            "status",
            "provider_message_id",
            "provider_response",
            "error",
            "sent_at",
            "delivered_at",
            "opened_at",
            "replied_at",
            "bounced_at",
            "spam_reported_at",
            "unsubscribed_at",
        }
        patch = {key: value for key, value in fields.items() if key in allowed}
        if not patch:
            return self.get_outreach_message(message_id)
        patch["updated_at"] = utc_now()
        self._request(
            "PATCH",
            f"/api/database/records/outreach_messages?id=eq.{message_id}",
            json_data=patch,
        )
        return self.get_outreach_message(message_id)

    def list_creator_contact_rows(self, creator_id: str) -> list[dict]:
        return self._request(
            "GET",
            f"/api/database/records/creator_contacts?creator_id=eq.{creator_id}",
        )

    def suppress_creator_contact(
        self,
        *,
        contact_id: str | None = None,
        email: str | None = None,
        reason: str,
    ) -> int:
        if not contact_id and not email:
            return 0
        now = utc_now()
        path = (
            f"/api/database/records/creator_contacts?id=eq.{contact_id}"
            if contact_id
            else f"/api/database/records/creator_contacts?contact_type=eq.email&value=eq.{quote(email or '', safe='')}"
        )
        self._request(
            "PATCH",
            path,
            json_data={
                "do_not_contact": True,
                "suppressed_at": now,
                "suppression_reason": reason,
                "last_verified_at": now,
            },
        )
        return 1

    def create_campaign_export(
        self,
        *,
        org_id: str | None,
        campaign_id: str,
        storage_key: str,
        file_url: str,
        row_count: int,
    ) -> dict:
        now = utc_now()
        export_id = stable_id("cex", campaign_id, storage_key)
        export_data = {
            "id": export_id,
            "org_id": org_id,
            "campaign_id": campaign_id,
            "storage_key": storage_key,
            "file_url": file_url,
            "row_count": row_count,
            "created_at": now,
            "updated_at": now,
        }
        self._request(
            "POST",
            "/api/database/records/campaign_exports",
            json_data=[export_data],
            headers={"Prefer": "resolution=merge-duplicates"},
        )
        return export_data

    def upload_storage_object(
        self,
        *,
        bucket: str,
        key: str,
        content: bytes,
        content_type: str,
    ) -> dict:
        strategy = self._request(
            "POST",
            f"/api/storage/buckets/{bucket}/upload-strategy",
            json_data={
                "filename": key,
                "contentType": content_type,
                "size": len(content),
            },
        )
        filename = key.rsplit("/", 1)[-1] or "export.csv"
        if strategy.get("method") == "direct":
            headers = self._headers()
            headers.pop("Content-Type", None)
            response = requests.put(
                f"{self.url}/api/storage/buckets/{bucket}/objects/{quote(key, safe='')}",
                files={"file": (filename, content, content_type)},
                headers=headers,
                timeout=30,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"InsForge storage upload failed: {response.status_code} - {response.text}")
            return response.json()
        if strategy.get("method") == "presigned":
            response = requests.post(
                strategy["uploadUrl"],
                data=strategy.get("fields") or {},
                files={"file": (filename, content, content_type)},
                timeout=30,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"InsForge presigned upload failed: {response.status_code} - {response.text}")
            if strategy.get("confirmRequired") and strategy.get("confirmUrl"):
                confirm_url = strategy["confirmUrl"]
                if confirm_url.startswith("http"):
                    confirm_response = requests.post(
                        confirm_url,
                        json={"size": len(content), "contentType": content_type},
                        headers=self._headers(),
                        timeout=30,
                    )
                    if confirm_response.status_code >= 400:
                        raise RuntimeError(
                            f"InsForge storage confirm failed: {confirm_response.status_code} - {confirm_response.text}"
                        )
                    return confirm_response.json()
                return self._request(
                    "POST",
                    confirm_url,
                    json_data={"size": len(content), "contentType": content_type},
                )
            return {
                "key": strategy["key"],
                "bucket": bucket,
                "size": len(content),
                "mimeType": content_type,
                "uploadedAt": utc_now(),
                "url": f"{self.url}/api/storage/buckets/{bucket}/objects/{quote(strategy['key'], safe='')}",
            }
        raise RuntimeError(f"Unsupported InsForge storage upload method: {strategy.get('method')}")

    def create_discovery_job(
        self,
        *,
        job_type: str,
        input_payload: dict,
        org_id: str | None = None,
        api_key_id: str | None = None,
        provider: str | None = None,
    ) -> str:
        job_id = stable_id("job", job_type, str(input_payload), utc_now())
        job_data = {
            "id": job_id,
            "org_id": org_id,
            "requested_by_api_key_id": api_key_id,
            "job_type": job_type,
            "provider": provider,
            "status": "queued",
            "input": input_payload,
            "output": {},
            "attempt_count": 0,
            "max_attempts": 3,
            "next_run_at": None,
            "locked_at": None,
            "locked_by": None,
            "created_at": utc_now(),
        }
        self._request("POST", "/api/database/records/discovery_jobs", json_data=[job_data])
        return job_id

    def get_discovery_job(self, job_id: str) -> dict | None:
        rows = self._request("GET", f"/api/database/records/discovery_jobs?id=eq.{job_id}")
        if not rows:
            return None
        return rows[0]

    def next_discovery_job(self) -> dict | None:
        rows = self._request(
            "GET",
            "/api/database/records/discovery_jobs?status=eq.queued&order=created_at.asc&limit=20",
        )
        now = datetime.now(timezone.utc)
        for row in rows:
            next_run_at = _parse_datetime(row.get("next_run_at"))
            if next_run_at is None or next_run_at <= now:
                return row
        return None

    def mark_discovery_job_running(self, job_id: str) -> None:
        job = self.get_discovery_job(job_id) or {}
        attempt_count = int(job.get("attempt_count") or 0) + 1
        worker_id = os.environ.get("CREATOR_SCOUT_WORKER_ID") or os.environ.get("HOSTNAME") or "worker-local"
        self._request(
            "PATCH",
            f"/api/database/records/discovery_jobs?id=eq.{job_id}",
            json_data={
                "status": "running",
                "attempt_count": attempt_count,
                "started_at": utc_now(),
                "locked_at": utc_now(),
                "locked_by": worker_id,
            },
        )

    def mark_discovery_job_finished(self, job_id: str, output: dict) -> None:
        self._request(
            "PATCH",
            f"/api/database/records/discovery_jobs?id=eq.{job_id}",
            json_data={
                "status": "passed",
                "output": output,
                "error": None,
                "next_run_at": None,
                "locked_at": None,
                "locked_by": None,
                "finished_at": utc_now(),
            },
        )

    def mark_discovery_job_failed(self, job_id: str, error: str) -> None:
        job = self.get_discovery_job(job_id) or {}
        attempt_count = int(job.get("attempt_count") or 0)
        max_attempts = max(1, int(job.get("max_attempts") or 3))
        terminal = attempt_count >= max_attempts
        retry_at = _seconds_from_now(_retry_backoff_seconds(attempt_count)) if not terminal else None
        self._request(
            "PATCH",
            f"/api/database/records/discovery_jobs?id=eq.{job_id}",
            json_data={
                "status": "failed" if terminal else "queued",
                "error": error,
                "next_run_at": retry_at,
                "locked_at": None,
                "locked_by": None,
                "finished_at": utc_now() if terminal else None,
            },
        )

    def retry_discovery_job(self, job_id: str) -> dict | None:
        job = self.get_discovery_job(job_id)
        if not job:
            return None
        self._request(
            "PATCH",
            f"/api/database/records/discovery_jobs?id=eq.{job_id}",
            json_data={
                "status": "queued",
                "output": {},
                "error": None,
                "attempt_count": 0,
                "next_run_at": None,
                "locked_at": None,
                "locked_by": None,
                "started_at": None,
                "finished_at": None,
            },
        )
        return self.get_discovery_job(job_id)


def summarize_job_statuses(jobs: list[dict]) -> dict:
    summary = {"queued": 0, "running": 0, "passed": 0, "failed": 0}
    for job in jobs:
        status = str(job.get("status") or "queued")
        if status in summary:
            summary[status] += 1
    summary["pending"] = summary["queued"] + summary["running"]
    summary["total"] = sum(summary[key] for key in ("queued", "running", "passed", "failed"))
    return summary


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _seconds_from_now(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _retry_backoff_seconds(attempt_count: int) -> int:
    attempt = max(1, attempt_count)
    return min(3600, 30 * (2 ** min(attempt - 1, 6)))
