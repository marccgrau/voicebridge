-- Migration: 003_service_modularization
-- Description: Add service configuration and suggestion metrics for modular suggestion services
-- Created: 2026-02-05

-- Add service config columns to sessions table
ALTER TABLE sessions
  ADD COLUMN IF NOT EXISTS suggestion_service TEXT NOT NULL DEFAULT 'simple_turn',
  ADD COLUMN IF NOT EXISTS process_illustration_enabled BOOLEAN NOT NULL DEFAULT true;

-- Add check constraint for suggestion_service
ALTER TABLE sessions
  ADD CONSTRAINT sessions_suggestion_service_check
  CHECK (suggestion_service IN ('simple_turn', 'tool_agent'));

-- Create suggestion_metrics table for analytics
CREATE TABLE IF NOT EXISTS suggestion_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    service_type TEXT NOT NULL,
    trigger_turn TEXT,
    latency_ms REAL,
    suggestion_count INTEGER,
    tools_used JSONB,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_suggestion_metrics_session
  ON suggestion_metrics(session_id);

CREATE INDEX IF NOT EXISTS idx_suggestion_metrics_service
  ON suggestion_metrics(service_type);

CREATE INDEX IF NOT EXISTS idx_suggestion_metrics_ts
  ON suggestion_metrics(ts DESC);

-- Add RLS policies for suggestion_metrics
ALTER TABLE suggestion_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow authenticated users to read suggestion metrics"
  ON suggestion_metrics
  FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Allow authenticated users to insert suggestion metrics"
  ON suggestion_metrics
  FOR INSERT
  TO authenticated
  WITH CHECK (true);

-- Add comment
COMMENT ON TABLE suggestion_metrics IS 'Analytics metrics for suggestion generation across different services';
COMMENT ON COLUMN sessions.suggestion_service IS 'Suggestion service type: simple_turn (fast) or tool_agent (with function calling)';
COMMENT ON COLUMN sessions.process_illustration_enabled IS 'Whether process illustration flow is enabled for this session';
