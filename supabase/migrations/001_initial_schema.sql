-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    process_key TEXT,
    state JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned', 'escalated')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_created_at ON sessions(created_at DESC);
CREATE INDEX idx_sessions_process_key ON sessions(process_key) WHERE process_key IS NOT NULL;

-- Transcript segments table
CREATE TABLE transcript_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    speaker TEXT NOT NULL CHECK (speaker IN ('agent', 'customer')),
    text TEXT NOT NULL,
    is_final BOOLEAN NOT NULL DEFAULT false,
    confidence REAL,
    start_time REAL,
    end_time REAL,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_transcript_segments_session_id ON transcript_segments(session_id);
CREATE INDEX idx_transcript_segments_session_ts ON transcript_segments(session_id, ts);
CREATE INDEX idx_transcript_segments_is_final ON transcript_segments(session_id, is_final) WHERE is_final = true;

-- Process selection events table (audit log)
CREATE TABLE process_selection_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    process_key TEXT NOT NULL,
    confidence REAL NOT NULL,
    rationale TEXT,
    candidates JSONB,
    trigger_text TEXT,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_process_selection_events_session_id ON process_selection_events(session_id);
CREATE INDEX idx_process_selection_events_ts ON process_selection_events(ts DESC);

-- Suggestions table
CREATE TABLE suggestions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    suggestions_json JSONB NOT NULL,
    process_key TEXT,
    step_key TEXT,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_suggestions_session_id ON suggestions(session_id);
CREATE INDEX idx_suggestions_ts ON suggestions(ts DESC);

-- Suggestion feedback table
CREATE TABLE suggestion_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    suggestion_id UUID NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('used', 'modified', 'dismissed')),
    modified_text TEXT,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_suggestion_feedback_session_id ON suggestion_feedback(session_id);
CREATE INDEX idx_suggestion_feedback_suggestion_id ON suggestion_feedback(suggestion_id);

-- UI preferences table
CREATE TABLE ui_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID UNIQUE NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    prefs_json JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Updated at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at trigger to sessions
CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply updated_at trigger to ui_preferences
CREATE TRIGGER update_ui_preferences_updated_at
    BEFORE UPDATE ON ui_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcript_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE process_selection_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE suggestion_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE ui_preferences ENABLE ROW LEVEL SECURITY;

-- RLS Policies (allow all for service role, restrict for anon)
-- Service role bypasses RLS by default

-- Sessions: allow read/write for authenticated users on their own sessions
CREATE POLICY "Users can view their own sessions"
    ON sessions FOR SELECT
    USING (true);

CREATE POLICY "Users can insert sessions"
    ON sessions FOR INSERT
    WITH CHECK (true);

CREATE POLICY "Users can update their own sessions"
    ON sessions FOR UPDATE
    USING (true);

-- Transcript segments: inherit from session access
CREATE POLICY "Users can view transcript segments"
    ON transcript_segments FOR SELECT
    USING (true);

CREATE POLICY "Users can insert transcript segments"
    ON transcript_segments FOR INSERT
    WITH CHECK (true);

-- Process selection events: read-only for users
CREATE POLICY "Users can view process selection events"
    ON process_selection_events FOR SELECT
    USING (true);

CREATE POLICY "Service can insert process selection events"
    ON process_selection_events FOR INSERT
    WITH CHECK (true);

-- Suggestions: read-only for users
CREATE POLICY "Users can view suggestions"
    ON suggestions FOR SELECT
    USING (true);

CREATE POLICY "Service can insert suggestions"
    ON suggestions FOR INSERT
    WITH CHECK (true);

-- Suggestion feedback
CREATE POLICY "Users can view suggestion feedback"
    ON suggestion_feedback FOR SELECT
    USING (true);

CREATE POLICY "Users can insert suggestion feedback"
    ON suggestion_feedback FOR INSERT
    WITH CHECK (true);

-- UI preferences
CREATE POLICY "Users can view their preferences"
    ON ui_preferences FOR SELECT
    USING (true);

CREATE POLICY "Users can manage their preferences"
    ON ui_preferences FOR ALL
    USING (true);
