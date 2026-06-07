from __future__ import annotations

import argparse

from creator_scout.config import load_env
from creator_scout.discovery.jobs import enqueue_discovery_query_job, run_job
from creator_scout.discovery.store import DiscoveryStore


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Ingest creators from a provider query")
    parser.add_argument("query", help="Search query, e.g. 'skincare India acne routine'")
    parser.add_argument("--provider", default="youtube", choices=["youtube", "tinyfish"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--db", default="data/creator_scout.sqlite3")
    parser.add_argument("--org-id", default="system")
    parser.add_argument("--enqueue-only", action="store_true")
    args = parser.parse_args()

    store = DiscoveryStore(args.db)
    try:
        job_id = enqueue_discovery_query_job(
            store,
            query=args.query,
            provider=args.provider,
            limit=args.limit,
            org_id=args.org_id,
        )
        if args.enqueue_only:
            print({"job_id": job_id, "status": "queued"})
            return
        output = run_job(store, job_id)
        print(output)
    finally:
        store.close()


if __name__ == "__main__":
    main()
