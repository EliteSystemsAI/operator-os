-- migrations/002_work_queue.sql
-- Elite Systems AI — Work Queue Table

CREATE TABLE IF NOT EXISTS work_queue (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  title           text        NOT NULL,
  description     text,
  status          text        NOT NULL DEFAULT 'backlog'
                              CHECK (status IN ('backlog','ready','in_progress','done','failed')),
  priority        int         NOT NULL DEFAULT 3
                              CHECK (priority BETWEEN 1 AND 4),
  source          text        NOT NULL DEFAULT 'manual'
                              CHECK (source IN ('telegram','dashboard','analyst','manual')),
  analyst_area    text,
  result_summary  text,
  result_full     text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  started_at      timestamptz,
  completed_at    timestamptz
);

-- Index for worker polling: status=ready ordered by priority, created_at
CREATE INDEX IF NOT EXISTS idx_work_queue_ready
  ON work_queue (priority ASC, created_at ASC)
  WHERE status = 'ready';

-- Index for dashboard queries
CREATE INDEX IF NOT EXISTS idx_work_queue_status
  ON work_queue (status, created_at DESC);

-- Seed one test task so we can verify the worker works
INSERT INTO work_queue (title, description, status, priority, source)
VALUES (
  'Test: Verify worker is running',
  'Reply with: "Worker is online. Mac Mini Claude Code engine is active."',
  'ready',
  3,
  'manual'
);
