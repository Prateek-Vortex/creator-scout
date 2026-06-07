from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from creator_scout.config import load_env
from creator_scout.discovery.auth import provision_api_key, hash_api_key
from creator_scout.discovery.ingest import ingest_records
from creator_scout.discovery.store import DiscoveryStore


def seed_database(seed_path: str) -> tuple[list[str], str]:
    store = DiscoveryStore()
    
    # 1. Resolve org_id
    project_json_path = Path(__file__).resolve().parents[2] / ".insforge" / "project.json"
    org_id = "e1e3e5a6-6d57-4600-9eb0-928e00f3bbf7" # default fallback
    if project_json_path.exists():
        try:
            project_data = json.loads(project_json_path.read_text(encoding="utf-8"))
            if project_data.get("org_id"):
                org_id = project_data["org_id"]
        except Exception:
            pass

    # 2. Ingest seed creators
    records = json.loads(Path(seed_path).read_text(encoding="utf-8"))
    creator_ids = ingest_records(store, records)

    # 3. Provision the exact demo developer key expected by frontend
    demo_key = "cs_demo__Oa10-u56rUsfIdxMRj7rqrcyldsU096b1KUxzxltic"
    store.create_api_key(
        org_id=org_id,
        name="Demo developer key",
        key_hash=hash_api_key(demo_key),
        scopes=["discovery:read", "discovery:write"],
        monthly_credit_limit=1000.0,
    )
    
    store.close()
    return creator_ids, demo_key


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Seed InsForge Creator Scout discovery data")
    parser.add_argument("--seed", default="data/seed_creators.json")
    args = parser.parse_args()
    
    # Ensure database credentials exist in environment
    if not os.environ.get("NEXT_PUBLIC_INSFORGE_URL") or not os.environ.get("NEXT_PUBLIC_INSFORGE_ANON_KEY"):
        # Try loading from apps/web/.env.local as a fallback
        local_env = Path(__file__).resolve().parents[2] / "apps" / "web" / ".env.local"
        if local_env.exists():
            for line in local_env.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")

    creator_ids, api_key = seed_database(args.seed)
    print(f"Seeded {len(creator_ids)} creators into InsForge Postgres")
    print(f"Demo API key: {api_key}")


if __name__ == "__main__":
    main()
