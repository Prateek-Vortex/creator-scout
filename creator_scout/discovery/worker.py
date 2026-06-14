from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait

from creator_scout.config import load_env
from creator_scout.discovery.jobs import run_job, run_next_job
from creator_scout.discovery.store import DiscoveryStore


def _run_one(job_id: str | None = None) -> dict | None:
    """Process a single job in its own DiscoveryStore.

    Each worker thread instantiates its own store because DiscoveryStore mutates
    instance state during FK-scaffold safe-writes; sharing one across threads
    would race.
    """
    store = DiscoveryStore()
    try:
        if job_id is not None:
            return run_job(store, job_id)
        return run_next_job(store)
    finally:
        store.close()


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Run Creator Scout discovery refresh jobs")
    parser.add_argument("--job-id")
    parser.add_argument("--loop", action="store_true", help="Keep polling for jobs")
    parser.add_argument("--interval", type=float, default=10.0, help="Seconds between polls when --loop is set")
    parser.add_argument("--max-jobs", type=int, default=0, help="Stop after N jobs; 0 means unlimited in loop mode")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.environ.get("CREATOR_SCOUT_WORKER_CONCURRENCY", "3")),
        help="Max concurrent jobs in --loop mode (default 3 or $CREATOR_SCOUT_WORKER_CONCURRENCY)",
    )
    args = parser.parse_args()

    if args.job_id:
        output = _run_one(args.job_id)
        print(output)
        return

    if not args.loop:
        output = _run_one()
        print(output or {"status": "no_jobs"})
        return

    concurrency = max(1, int(args.concurrency))
    processed = 0
    consecutive_failures = 0

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        in_flight: set[Future] = set()
        try:
            while True:
                # Fill the pool up to `concurrency`.
                while len(in_flight) < concurrency:
                    in_flight.add(pool.submit(_run_one))

                # Wait for at least one to finish. Timeout = interval so we
                # don't sit forever if jobs are long-running.
                done, _pending = wait(in_flight, timeout=args.interval, return_when="FIRST_COMPLETED")
                if not done:
                    # All slots are busy with long jobs — keep waiting.
                    continue

                batch_had_work = False
                batch_failed = 0
                for fut in done:
                    in_flight.discard(fut)
                    try:
                        output = fut.result()
                    except Exception as exc:  # noqa: BLE001
                        batch_failed += 1
                        print(f"[worker] Job failed: {exc}", file=sys.stderr)
                        continue
                    if output:
                        processed += 1
                        batch_had_work = True
                        print(output)
                    else:
                        # Queue was empty for this slot.
                        time.sleep(min(args.interval, 1.0))

                if batch_had_work:
                    consecutive_failures = 0
                elif batch_failed:
                    consecutive_failures += batch_failed
                    backoff = min(300, 5 * (2 ** min(consecutive_failures - 1, 6)))
                    print(
                        f"[worker] {consecutive_failures} consecutive failures — sleeping {backoff}s",
                        file=sys.stderr,
                    )
                    time.sleep(backoff)

                if args.max_jobs and processed >= args.max_jobs:
                    return
        finally:
            for fut in in_flight:
                fut.cancel()


if __name__ == "__main__":
    main()
