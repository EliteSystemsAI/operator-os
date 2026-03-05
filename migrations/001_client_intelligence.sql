-- Elite Systems AI — Client Intelligence Schema
-- Run this in Supabase Dashboard → SQL Editor
-- Project: bsjuquawicyqvivevnrt

-- ── client_profiles ──────────────────────────────────────────────────────────
-- One row per client. Stores metadata + links to Google Drive, GHL, Slack.

CREATE TABLE IF NOT EXISTS client_profiles (
  id              uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  client_name     text    UNIQUE NOT NULL,
  business_type   text,
  monthly_revenue text,
  pain_points     text[],
  gdrive_doc_id   text,           -- Google Doc ID for their Working Doc
  ghl_location_id text,           -- Their GHL sub-account ID
  slack_channel   text,           -- e.g. "acme-fitness" (from channel name)
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);

-- Auto-update updated_at on any change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS client_profiles_updated_at ON client_profiles;
CREATE TRIGGER client_profiles_updated_at
  BEFORE UPDATE ON client_profiles
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── client_systems ────────────────────────────────────────────────────────────
-- One row per system delivered. Grows over time as Zac ships work.

CREATE TABLE IF NOT EXISTS client_systems (
  id               uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  client_name      text    NOT NULL,
  system_name      text    NOT NULL,
  description      text,
  platform         text,           -- "GHL", "n8n", "Railway", etc.
  delivered_date   date    DEFAULT CURRENT_DATE,
  source           text,           -- "fathom", "slack", "manual"
  call_summary     text,           -- relevant transcript excerpt
  next_suggestion  text,           -- Claude-generated next system suggestion
  created_at       timestamptz DEFAULT now()
);

-- Index for fast client lookups
CREATE INDEX IF NOT EXISTS idx_client_systems_client_name
  ON client_systems (client_name, delivered_date DESC);
