-- migrations/003_memory_and_workflows.sql

-- Session summaries (mid-term memory)
CREATE TABLE IF NOT EXISTS bot_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    summary TEXT NOT NULL,
    workflow TEXT NOT NULL DEFAULT 'chat'  -- 'ads', 'content', 'chat'
);

-- Per-turn conversation messages (short-term memory)
CREATE TABLE IF NOT EXISTS bot_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES bot_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bot_messages_session_created ON bot_messages(session_id, created_at);

-- Workflow run log (ads, content) + approval state
CREATE TABLE IF NOT EXISTS workflow_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow TEXT NOT NULL,         -- 'ads' | 'content'
    ran_at TIMESTAMPTZ DEFAULT NOW(),
    input_data JSONB,               -- raw data fed to Claude
    claude_analysis TEXT,           -- Claude's full analysis text
    action_taken TEXT,              -- description of what was/will be done
    pending_approval BOOLEAN DEFAULT TRUE,
    approved BOOLEAN DEFAULT NULL,  -- NULL = pending, TRUE = approved, FALSE = rejected
    approved_at TIMESTAMPTZ,
    telegram_message_id INTEGER     -- so we can edit the approval message after decision
);
CREATE INDEX IF NOT EXISTS idx_workflow_logs_pending ON workflow_logs(pending_approval, approved);

-- Long-term business context key/value store
CREATE TABLE IF NOT EXISTS business_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
