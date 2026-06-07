from __future__ import annotations

import argparse
import sys
import time

from creator_scout.config import load_env
from creator_scout.discovery.jobs import run_job, run_next_job
from creator_scout.discovery.store import DiscoveryStore


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Run Creator Scout discovery refresh jobs")
    parser.add_argument("--db", default="data/creator_scout.sqlite3")
    parser.add_argument("--job-id")
    parser.add_argument("--loop", action="store_true", help="Keep polling for jobs")
    parser.add_argument("--interval", type=float, default=10.0, help="Seconds between polls when --loop is set")
    parser.add_argument("--max-jobs", type=int, default=0, help="Stop after N jobs; 0 means unlimited in loop mode")
    args = parser.parse_args()

    store = DiscoveryStore(args.db)
    try:
        if args.job_id:
            output = run_job(store, args.job_id)
            print(output)
            return
        if args.loop:
            processed = 0
            consecutive_failures = 0
            while True:
                try:
                    output = run_next_job(store)
                    if output:
                        processed += 1
                        consecutive_failures = 0
                        print(output)
                    elif args.max_jobs and processed >= args.max_jobs:
                        return
                    else:
                        time.sleep(args.interval)
                    if args.max_jobs and processed >= args.max_jobs:
                        return
                except Exception as exc:
                    consecutive_failures += 1
                    print(f"[worker] Job failed ({consecutive_failures} consecutive): {exc}", file=sys.stderr)
                    # Back off exponentially, max 5 minutes
                    backoff = min(300, 5 * (2 ** min(consecutive_failures - 1, 6)))
                    time.sleep(backoff)
        else:
            output = run_next_job(store)
            print(output or {"status": "no_jobs"})
    finally:
        store.close()


if __name__ == "__main__":
    main()
