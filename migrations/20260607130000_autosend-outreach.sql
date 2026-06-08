-- AutoSend-backed explicit outreach sending and suppression tracking.

ALTER TABLE creator_contacts
  ADD COLUMN IF NOT EXISTS suppressed_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS suppression_reason text;

ALTER TABLE outreach_messages
  ADD COLUMN IF NOT EXISTS recipient_contact_id uuid REFERENCES creator_contacts(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS recipient_email text,
  ADD COLUMN IF NOT EXISTS provider text,
  ADD COLUMN IF NOT EXISTS provider_message_id text,
  ADD COLUMN IF NOT EXISTS provider_response jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS error text,
  ADD COLUMN IF NOT EXISTS unsubscribe_group_id text,
  ADD COLUMN IF NOT EXISTS delivered_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS bounced_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS spam_reported_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS unsubscribed_at timestamp with time zone,
  ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS outreach_messages_provider_message_idx
  ON outreach_messages (provider, provider_message_id)
  WHERE provider_message_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS outreach_messages_campaign_creator_created_idx
  ON outreach_messages (campaign_creator_id, created_at DESC);

CREATE INDEX IF NOT EXISTS creator_contacts_suppressed_idx
  ON creator_contacts (do_not_contact, suppressed_at)
  WHERE do_not_contact = true OR suppressed_at IS NOT NULL;

DROP POLICY IF EXISTS project_admin_all_creator_contacts ON creator_contacts;
CREATE POLICY project_admin_all_creator_contacts ON creator_contacts FOR ALL TO project_admin USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS project_admin_all_outreach_messages ON outreach_messages;
CREATE POLICY project_admin_all_outreach_messages ON outreach_messages FOR ALL TO project_admin USING (true) WITH CHECK (true);
