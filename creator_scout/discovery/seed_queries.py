from __future__ import annotations

import argparse
import json
from pathlib import Path

from creator_scout.config import load_env
from creator_scout.discovery.jobs import enqueue_discovery_query_job, run_job
from creator_scout.discovery.store import DiscoveryStore


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Queue a batch of discovery query jobs")
    parser.add_argument("--db", default="data/creator_scout.sqlite3")
    parser.add_argument("--queries", default="data/seed_queries.json")
    parser.add_argument("--org-id", default="system")
    parser.add_argument("--provider", help="Only queue specs for this provider")
    parser.add_argument("--run", action="store_true", help="Run each job immediately after enqueueing")
    args = parser.parse_args()

    query_specs = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    store = DiscoveryStore(args.db)
    queued = []
    try:
        for spec in query_specs:
            if args.provider and spec.get("provider", "youtube") != args.provider:
                continue
            job_id = enqueue_discovery_query_job(
                store,
                query=spec["query"],
                provider=spec.get("provider", "youtube"),
                limit=int(spec.get("limit", 10)),
                org_id=args.org_id,
            )
            item = {
                "job_id": job_id,
                "provider": spec.get("provider", "youtube"),
                "query": spec["query"],
                "status": "queued",
            }
            if args.run:
                item["output"] = run_job(store, job_id)
                item["status"] = "processed"
            queued.append(item)
    finally:
        store.close()
    print(json.dumps({"queued": queued}, indent=2))


if __name__ == "__main__":
    main()
