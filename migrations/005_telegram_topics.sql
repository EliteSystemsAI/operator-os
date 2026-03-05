-- Auto-discovered Telegram forum topics
CREATE TABLE IF NOT EXISTS telegram_topics (
    thread_id     BIGINT PRIMARY KEY,
    name          TEXT NOT NULL,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Allow bot to upsert and read
ALTER TABLE telegram_topics ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_all" ON telegram_topics USING (true) WITH CHECK (true);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

CREATE OR REPLACE TRIGGER telegram_topics_updated_at
    BEFORE UPDATE ON telegram_topics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
