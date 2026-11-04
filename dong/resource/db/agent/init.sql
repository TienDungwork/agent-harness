-- Agent Postgres (sessions + LangGraph checkpoints). Long-term facts → Qdrant.
-- Checkpoint tables: PostgresSaver.setup() lúc backend start.

DROP TABLE IF EXISTS user_memories;

CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT 'Phiên chat mới',
    preview TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_session_messages (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_session_messages(session_id, id);

CREATE TABLE IF NOT EXISTS human_feedback (
    id TEXT PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    rating TEXT NOT NULL CHECK (rating IN ('positive', 'negative')),
    feedback_reason TEXT,
    attachment_path TEXT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    agent_trace JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_human_feedback_ts ON human_feedback (ts DESC);
CREATE INDEX IF NOT EXISTS idx_human_feedback_rating ON human_feedback (rating);
CREATE INDEX IF NOT EXISTS idx_human_feedback_user ON human_feedback (user_id, ts DESC);
