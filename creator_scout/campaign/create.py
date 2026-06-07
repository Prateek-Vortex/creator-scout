from __future__ import annotations

import argparse
import json
import os

from creator_scout.campaign.service import CampaignService
from creator_scout.config import load_env
from creator_scout.discovery.store import DiscoveryStore


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Create a brand-led Creator Scout campaign.")
    parser.add_argument("brand_url")
    parser.add_argument("--db", default=os.environ.get("CREATOR_SCOUT_DB", "data/creator_scout.sqlite3"))
    parser.add_argument("--org-id", default="system")
    parser.add_argument("--geo", default="India")
    parser.add_argument("--goal", default="ugc")
    parser.add_argument("--provider", default="youtube")
    parser.add_argument("--platform", action="append", dest="platforms")
    parser.add_argument("--query-limit", type=int, default=5)
    parser.add_argument("--per-query-limit", type=int, default=10)
    parser.add_argument("--shortlist", action="store_true")
    parser.add_argument("--shortlist-limit", type=int, default=25)
    args = parser.parse_args()

    store = DiscoveryStore(args.db)
    try:
        service = CampaignService(store)
        result = service.create_campaign(
            args.brand_url,
            org_id=args.org_id,
            geo=args.geo,
            goal=args.goal,
            provider=args.provider,
            platforms=args.platforms,
            query_limit=args.query_limit,
            per_query_limit=args.per_query_limit,
        )
        if args.shortlist:
            campaign_id = result["campaign"]["id"]
            result["shortlist"] = service.build_shortlist(
                campaign_id,
                org_id=args.org_id,
                limit=args.shortlist_limit,
            )
        print(json.dumps(result, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
