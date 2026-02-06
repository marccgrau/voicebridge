-- 001_initial_schema.sql
-- Consolidated migration: sessions, transcript_segments, process_catalog
-- Created: 2026-02-06

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- Functions
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ============================================================================
-- Sessions table
-- ============================================================================

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_key TEXT,
    state JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('pending', 'active', 'completed', 'abandoned', 'escalated', 'error')),
    suggestion_service TEXT NOT NULL DEFAULT 'split_flows'
        CHECK (suggestion_service IN ('split_flows')),
    process_illustration_enabled BOOLEAN NOT NULL DEFAULT true,
    room_url TEXT,
    room_name TEXT,
    customer_joined_at TIMESTAMPTZ,
    agent_joined_at TIMESTAMPTZ,
    error_message TEXT,
    error_occurred_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_created_at ON sessions(created_at DESC);
CREATE INDEX idx_sessions_process_key ON sessions(process_key) WHERE process_key IS NOT NULL;
CREATE INDEX idx_sessions_pending ON sessions(status, created_at DESC) WHERE status = 'pending';
CREATE INDEX idx_sessions_error_occurred_at ON sessions(error_occurred_at) WHERE error_occurred_at IS NOT NULL;

CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON COLUMN sessions.suggestion_service IS 'Suggestion service type: split_flows (modular process and suggestion flows)';
COMMENT ON COLUMN sessions.process_illustration_enabled IS 'Whether process illustration flow is enabled for this session';
COMMENT ON COLUMN sessions.error_message IS 'Error message if session failed';
COMMENT ON COLUMN sessions.error_occurred_at IS 'Timestamp when error occurred';

-- ============================================================================
-- Transcript segments table
-- ============================================================================

CREATE TABLE transcript_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- ============================================================================
-- Process catalog table
-- ============================================================================

CREATE TABLE process_catalog (
    process_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    queue_tag TEXT,
    locale TEXT NOT NULL DEFAULT 'en',
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    process_text TEXT NOT NULL,
    steps_json JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_process_catalog_status_locale ON process_catalog(status, locale);
CREATE INDEX idx_process_catalog_domain_queue ON process_catalog(domain, queue_tag);
CREATE INDEX idx_process_catalog_name_trgm ON process_catalog USING GIN (name gin_trgm_ops);
CREATE INDEX idx_process_catalog_fts ON process_catalog
    USING GIN (to_tsvector('simple', process_text));

CREATE TRIGGER update_process_catalog_updated_at
    BEFORE UPDATE ON process_catalog
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Full-text search RPC function
-- ============================================================================

CREATE OR REPLACE FUNCTION search_processes(
    search_query TEXT,
    search_locale TEXT DEFAULT 'en',
    search_domain TEXT DEFAULT NULL,
    search_queue_tag TEXT DEFAULT NULL,
    result_limit INTEGER DEFAULT 5
)
RETURNS TABLE (
    process_key TEXT,
    name TEXT,
    domain TEXT,
    queue_tag TEXT,
    locale TEXT,
    version TEXT,
    status TEXT,
    process_text TEXT,
    steps_json JSONB,
    updated_at TIMESTAMPTZ,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pc.process_key,
        pc.name,
        pc.domain,
        pc.queue_tag,
        pc.locale,
        pc.version,
        pc.status,
        pc.process_text,
        pc.steps_json,
        pc.updated_at,
        ts_rank(
            to_tsvector('simple', pc.process_text),
            plainto_tsquery('simple', search_query)
        ) +
        CASE WHEN pc.name ILIKE '%' || search_query || '%' THEN 0.5 ELSE 0 END +
        similarity(pc.name, search_query) * 0.3 AS rank
    FROM process_catalog pc
    WHERE
        pc.status = 'active'
        AND pc.locale = search_locale
        AND (search_domain IS NULL OR pc.domain = search_domain)
        AND (search_queue_tag IS NULL OR pc.queue_tag = search_queue_tag)
        AND (
            to_tsvector('simple', pc.process_text) @@ plainto_tsquery('simple', search_query)
            OR pc.name ILIKE '%' || search_query || '%'
            OR similarity(pc.name, search_query) > 0.3
        )
    ORDER BY rank DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- Row Level Security
-- ============================================================================

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcript_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE process_catalog ENABLE ROW LEVEL SECURITY;

-- Sessions
CREATE POLICY "Users can view their own sessions"
    ON sessions FOR SELECT
    USING (true);

CREATE POLICY "Users can insert sessions"
    ON sessions FOR INSERT
    WITH CHECK (true);

CREATE POLICY "Users can update their own sessions"
    ON sessions FOR UPDATE
    USING (true);

-- Transcript segments
CREATE POLICY "Users can view transcript segments"
    ON transcript_segments FOR SELECT
    USING (true);

CREATE POLICY "Users can insert transcript segments"
    ON transcript_segments FOR INSERT
    WITH CHECK (true);

-- Process catalog
CREATE POLICY "Anyone can view active processes"
    ON process_catalog FOR SELECT
    USING (status = 'active');

CREATE POLICY "Service can manage processes"
    ON process_catalog FOR ALL
    USING (true);

-- ============================================================================
-- Enable Realtime
-- ============================================================================

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'sessions'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE sessions;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'transcript_segments'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE transcript_segments;
  END IF;
END $$;

-- ============================================================================
-- Seed data: process catalog
-- ============================================================================

INSERT INTO process_catalog (process_key, name, domain, queue_tag, locale, version, status, process_text, steps_json) VALUES
(
    'billing-dispute',
    'Billing Dispute Resolution',
    'billing',
    'billing-support',
    'en',
    '1.0.0',
    'active',
    'Handle customer billing disputes and charge corrections. This process covers unauthorized charges, duplicate billing, incorrect amounts, and refund requests. Agent should verify account ownership, review transaction history, identify the disputed charges, and process appropriate adjustments or escalate to billing specialists.',
    '[
        {"key": "verify-identity", "label": "Verify Customer Identity", "description": "Confirm account ownership with security questions"},
        {"key": "identify-charge", "label": "Identify Disputed Charge", "description": "Locate the specific transaction in question"},
        {"key": "review-history", "label": "Review Transaction History", "description": "Check for patterns or related transactions"},
        {"key": "determine-resolution", "label": "Determine Resolution", "description": "Decide on refund, credit, or escalation"},
        {"key": "process-adjustment", "label": "Process Adjustment", "description": "Apply the approved resolution"},
        {"key": "confirm-resolution", "label": "Confirm with Customer", "description": "Verify customer satisfaction with outcome"}
    ]'::jsonb
),
(
    'account-password-reset',
    'Account Password Reset',
    'account',
    'account-support',
    'en',
    '1.0.0',
    'active',
    'Assist customers with password reset and account recovery. Process includes identity verification, security question validation, email/SMS verification, and password reset link generation. Handle locked accounts and suspicious activity flags.',
    '[
        {"key": "verify-identity", "label": "Verify Identity", "description": "Confirm customer identity through security questions"},
        {"key": "check-account-status", "label": "Check Account Status", "description": "Review any locks or security flags"},
        {"key": "send-reset-link", "label": "Send Reset Link", "description": "Generate and send password reset email/SMS"},
        {"key": "confirm-reset", "label": "Confirm Reset Complete", "description": "Verify customer can access account"}
    ]'::jsonb
),
(
    'order-status-inquiry',
    'Order Status Inquiry',
    'orders',
    'order-support',
    'en',
    '1.0.0',
    'active',
    'Provide customers with order status updates and shipping information. Look up orders by order number, email, or phone. Provide tracking numbers, estimated delivery dates, and handle delivery issues like delays or missing packages.',
    '[
        {"key": "locate-order", "label": "Locate Order", "description": "Find order in system by order number or customer info"},
        {"key": "provide-status", "label": "Provide Current Status", "description": "Share order status and tracking information"},
        {"key": "address-concerns", "label": "Address Concerns", "description": "Handle any issues with the order"},
        {"key": "set-expectations", "label": "Set Expectations", "description": "Confirm delivery timeline and next steps"}
    ]'::jsonb
),
(
    'product-return',
    'Product Return Request',
    'orders',
    'returns-support',
    'en',
    '1.0.0',
    'active',
    'Process product return requests and exchanges. Verify return eligibility based on return policy, generate return labels, process refunds or exchanges, and handle exceptions for damaged or defective items.',
    '[
        {"key": "verify-purchase", "label": "Verify Purchase", "description": "Confirm original order and purchase date"},
        {"key": "check-eligibility", "label": "Check Return Eligibility", "description": "Verify item is within return window and policy"},
        {"key": "determine-type", "label": "Determine Return Type", "description": "Refund, exchange, or store credit"},
        {"key": "generate-label", "label": "Generate Return Label", "description": "Create prepaid shipping label if applicable"},
        {"key": "process-return", "label": "Process Return", "description": "Complete return in system"},
        {"key": "confirm-next-steps", "label": "Confirm Next Steps", "description": "Explain refund timeline and process"}
    ]'::jsonb
),
(
    'technical-troubleshooting',
    'Technical Troubleshooting',
    'technical',
    'tech-support',
    'en',
    '1.0.0',
    'active',
    'Diagnose and resolve technical issues with products or services. Guide customers through troubleshooting steps, check system status, identify known issues, and escalate to tier 2 support when needed. Cover connectivity issues, software problems, and hardware diagnostics.',
    '[
        {"key": "gather-info", "label": "Gather Issue Details", "description": "Understand the technical problem and symptoms"},
        {"key": "check-status", "label": "Check System Status", "description": "Verify no known outages or issues"},
        {"key": "basic-troubleshoot", "label": "Basic Troubleshooting", "description": "Guide through standard resolution steps"},
        {"key": "advanced-diagnosis", "label": "Advanced Diagnosis", "description": "Deeper technical investigation if needed"},
        {"key": "resolve-or-escalate", "label": "Resolve or Escalate", "description": "Fix issue or escalate to specialists"},
        {"key": "confirm-resolution", "label": "Confirm Resolution", "description": "Verify issue is resolved"}
    ]'::jsonb
);
