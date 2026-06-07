-- Keep hydrated provider counts from overflowing Postgres integer columns.

ALTER TABLE creator_accounts
  ALTER COLUMN follower_count TYPE bigint,
  ALTER COLUMN subscriber_count TYPE bigint,
  ALTER COLUMN avg_views TYPE bigint;
