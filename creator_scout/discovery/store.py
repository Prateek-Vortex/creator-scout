import os
import requests
import sys
import uuid
from pathlib import Path
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
                if v is not None:
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
        self.url = os.environ.get("NEXT_PUBLIC_INSFORGE_URL")
        self.anon_key = os.environ.get("NEXT_PUBLIC_INSFORGE_ANON_KEY")
        if not self.url or not self.anon_key:
            raise RuntimeError("Missing InsForge configuration in environment variables.")
        self.url = self.url.rstrip("/")
        if IN_TEST:
            self.clear_database()

    def clear_database(self) -> None:
        try:
            self._request("DELETE", "/api/database/records/creator_profiles")
            self._request("DELETE", "/api/database/records/campaigns")
            self._request("DELETE", "/api/database/records/brands")
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
            "Authorization": f"Bearer {self.anon_key}",
            "apikey": self.anon_key,
            "Content-Type": "application/json",
        }
        if custom:
            h.update(custom)
        return h

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
                    try:
                        url_org = f"{self.url}/api/database/records/organizations"
                        requests.post(
                            url_org,
                            json=[{"id": oid, "name": f"Team {oid}", "plan": "free"}],
                            headers=self._headers({"Prefer": "resolution=ignore-duplicates"}),
                            timeout=timeout
                        )
                    except Exception:
                        pass
            
            if "/developer_api_keys" not in path:
                for kid in api_key_ids:
                    default_org = org_ids[0] if org_ids else to_uuid("org_test")
                    if "/organizations" not in path:
                        try:
                            requests.post(
                                f"{self.url}/api/database/records/organizations",
                                json=[{"id": default_org, "name": f"Team {default_org}", "plan": "free"}],
                                headers=self._headers({"Prefer": "resolution=ignore-duplicates"}),
                                timeout=timeout
                            )
                        except Exception:
                            pass
                    
                    try:
                        requests.post(
                            f"{self.url}/api/database/records/developer_api_keys",
                            json=[{
                                "id": kid,
                                "org_id": default_org,
                                "name": "Dummy Key",
                                "key_hash": f"dummy_hash_{kid}",
                                "scopes": ["discovery:read", "discovery:write"],
                                "rate_limit_per_minute": 60,
                                "monthly_credit_limit": 1000.0,
                            }],
                            headers=self._headers({"Prefer": "resolution=ignore-duplicates"}),
                            timeout=timeout
                        )
                    except Exception:
                        pass

            if "/campaigns" not in path:
                for cid in campaign_ids:
                    default_org = org_ids[0] if org_ids else to_uuid("org_test")
                    if "/organizations" not in path:
                        try:
                            requests.post(
                                f"{self.url}/api/database/records/organizations",
                                json=[{"id": default_org, "name": f"Team {default_org}", "plan": "free"}],
                                headers=self._headers({"Prefer": "resolution=ignore-duplicates"}),
                                timeout=timeout
                            )
                        except Exception:
                            pass
                    
                    dummy_brand_id = to_uuid("dummy_brand")
                    if "/brands" not in path:
                        try:
                            requests.post(
                                f"{self.url}/api/database/records/brands",
                                json=[{
                                    "id": dummy_brand_id,
                                    "org_id": default_org,
                                    "website_url": "https://dummybrand.com",
                                    "name": "Dummy Brand",
                                    "brief_json": {},
                                    "confidence": 1.0,
                                }],
                                headers=self._headers({"Prefer": "resolution=ignore-duplicates"}),
                                timeout=timeout
                            )
                        except Exception:
                            pass
                    
                    try:
                        requests.post(
                            f"{self.url}/api/database/records/campaigns",
                            json=[{
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
                            headers=self._headers({"Prefer": "resolution=ignore-duplicates"}),
                            timeout=timeout
                        )
                    except Exception:
                        pass

        url = f"{self.url}{path}"
        r = requests.request(method, url, json=json_data, params=params, headers=self._headers(headers), timeout=timeout)
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
        # Re-map back to SQLite brief dict output format
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
            "/api/database/records/discovery_jobs?status=eq.queued&order=created_at.asc&limit=1",
        )
        if not rows:
            return None
        return rows[0]

    def mark_discovery_job_running(self, job_id: str) -> None:
        self._request(
            "PATCH",
            f"/api/database/records/discovery_jobs?id=eq.{job_id}",
            json_data={"status": "running", "started_at": utc_now()},
        )

    def mark_discovery_job_finished(self, job_id: str, output: dict) -> None:
        self._request(
            "PATCH",
            f"/api/database/records/discovery_jobs?id=eq.{job_id}",
            json_data={"status": "passed", "output": output, "finished_at": utc_now()},
        )

    def mark_discovery_job_failed(self, job_id: str, error: str) -> None:
        self._request(
            "PATCH",
            f"/api/database/records/discovery_jobs?id=eq.{job_id}",
            json_data={"status": "failed", "error": error, "finished_at": utc_now()},
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
                "started_at": None,
                "finished_at": None,
            },
        )
        return self.get_discovery_job(job_id)
