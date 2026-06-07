from __future__ import annotations

import argparse
import json

from creator_scout.brand.service import BrandScanService
from creator_scout.config import load_env
from creator_scout.discovery.store import DiscoveryStore


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Scan a brand URL and generate creator discovery queries")
    parser.add_argument("brand_url")
    parser.add_argument("--db", default="data/creator_scout.sqlite3")
    parser.add_argument("--org-id", default="system")
    parser.add_argument("--geo", default="India")
    parser.add_argument("--goal", default="ugc")
    parser.add_argument("--enqueue-discovery", action="store_true")
    parser.add_argument("--provider", default="youtube")
    parser.add_argument("--query-limit", type=int, default=5)
    args = parser.parse_args()

    store = DiscoveryStore(args.db)
    try:
        result = BrandScanService(store).scan(
            args.brand_url,
            org_id=args.org_id,
            geo=args.geo,
            goal=args.goal,
            enqueue_discovery=args.enqueue_discovery,
            provider=args.provider,
            query_limit=args.query_limit,
        )
        print(json.dumps(result, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()

