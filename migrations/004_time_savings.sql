-- migrations/004_time_savings.sql

-- Track hours saved per client per system delivered
CREATE TABLE IF NOT EXISTS time_savings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_name     TEXT NOT NULL,
    system_name     TEXT NOT NULL,
    hours_per_week  NUMERIC NOT NULL CHECK (hours_per_week >= 0),
    weeks_active    NUMERIC NOT NULL DEFAULT 0 CHECK (weeks_active >= 0),
    total_hours_saved NUMERIC GENERATED ALWAYS AS (hours_per_week * weeks_active) STORED,
    delivered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_time_savings_client ON time_savings(client_name);
CREATE INDEX IF NOT EXISTS idx_time_savings_delivered ON time_savings(delivered_at DESC);

-- Row Level Security — anon can read, only service role can write
ALTER TABLE time_savings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_select" ON time_savings
    FOR SELECT TO anon USING (true);

-- Aggregate view for website API and morning ping
CREATE OR REPLACE VIEW time_savings_summary AS
SELECT
    COALESCE(SUM(total_hours_saved), 0)  AS total_hours_saved,
    COUNT(DISTINCT client_name)           AS total_clients,
    COUNT(*)                              AS total_systems
FROM time_savings;

-- Grant anon read access to the view
GRANT SELECT ON time_savings_summary TO anon;
