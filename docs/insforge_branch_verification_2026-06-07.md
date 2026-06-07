# InsForge Branch Verification - 2026-06-07

Project branch: `mvp-hardening` (`schema-only`)

## Applied Migrations

- `20260607120000_backend-hardening`
- `20260607121000_creator-account-count-bigints`

## Verified On Branch

- `campaign_exports` exists with export metadata columns.
- `discovery_jobs` has `attempt_count`, `max_attempts`, `next_run_at`, `locked_at`, and `locked_by`.
- `creator_accounts.follower_count`, `subscriber_count`, and `avg_views` are `bigint`.
- RLS is enabled on checked app tables including `campaigns`, `campaign_creators`, `campaign_exports`, `creator_profiles`, and `discovery_jobs`.
- `anon` and `authenticated` have no broad app-table grants in `public`.
- Storage bucket `campaign-exports` exists and is private.

## Test Notes

- `python3 -m py_compile ...` passed for the touched Python API, services, worker, and tests.
- `npm run lint` passed in `apps/web`.
- `npm run build` passed in `apps/web`.
- Branch-backed `pytest -q` reached `17 passed / 1 failed` before the first cleanup fix; the failure exposed stale `discovery_jobs` test data leaking across tests.
- After fixing cleanup and adding REST retry/backoff, a rerun hit InsForge `429 Too many requests from this IP`. The stalled retrying subset was stopped to avoid adding more load.

Do not merge this branch to the parent project until branch-backed smoke tests complete after the rate limit clears.
