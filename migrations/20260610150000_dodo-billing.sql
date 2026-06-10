-- Phase 4: Dodo Payments subscription billing columns.
-- Adds subscription tracking fields to the organizations table.

ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS dodo_subscription_id text,
  ADD COLUMN IF NOT EXISTS dodo_checkout_session_id text;

-- Ensure project_admin policy covers the new columns (re-apply to be safe).
DROP POLICY IF EXISTS project_admin_all_organizations ON organizations;
CREATE POLICY project_admin_all_organizations ON organizations FOR ALL TO project_admin USING (true) WITH CHECK (true);
