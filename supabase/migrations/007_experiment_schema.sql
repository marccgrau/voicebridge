-- 007_experiment_schema.sql
-- Add experiment-ready schema for cross-combinable persona/scenario runs.

-- ============================================================================
-- Scenario catalog
-- ============================================================================

CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id TEXT PRIMARY KEY,
    scenario_family TEXT NOT NULL,
    title TEXT NOT NULL,
    domain TEXT NOT NULL,
    civility_condition TEXT NOT NULL
        CHECK (civility_condition IN ('civil', 'uncivil')),
    behavior_instruction TEXT NOT NULL DEFAULT '',
    background TEXT NOT NULL,
    customer_goal TEXT NOT NULL,
    guidelines JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(guidelines) = 'object'),
    conversation JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(conversation) = 'array'),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scenarios_status_domain
    ON scenarios(status, domain);

CREATE INDEX IF NOT EXISTS idx_scenarios_family
    ON scenarios(scenario_family);

CREATE INDEX IF NOT EXISTS idx_scenarios_civility
    ON scenarios(civility_condition);

DROP TRIGGER IF EXISTS update_scenarios_updated_at ON scenarios;

CREATE TRIGGER update_scenarios_updated_at
    BEFORE UPDATE ON scenarios
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Session events for experiment telemetry
-- ============================================================================

CREATE TABLE IF NOT EXISTS session_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL
        CHECK (source IN ('customer_app', 'agent_workspace', 'pcc', 'system')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_session_events_session_ts
    ON session_events(session_id, ts DESC);

CREATE INDEX IF NOT EXISTS idx_session_events_type
    ON session_events(event_type, ts DESC);

-- ============================================================================
-- Sessions: attach selected scenario metadata per run
-- ============================================================================

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS scenario_id TEXT,
    ADD COLUMN IF NOT EXISTS scenario_family TEXT,
    ADD COLUMN IF NOT EXISTS civility_condition TEXT
        CHECK (civility_condition IN ('civil', 'uncivil'));

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'sessions_scenario_id_fkey'
    ) THEN
        ALTER TABLE sessions
            ADD CONSTRAINT sessions_scenario_id_fkey
            FOREIGN KEY (scenario_id)
            REFERENCES scenarios(scenario_id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_sessions_scenario_id
    ON sessions(scenario_id)
    WHERE scenario_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sessions_scenario_family_civility_created
    ON sessions(scenario_family, civility_condition, created_at DESC)
    WHERE scenario_family IS NOT NULL;

-- ============================================================================
-- Customers: persona data required for experiment context
-- ============================================================================

ALTER TABLE customers
    DROP CONSTRAINT IF EXISTS customers_classification_check;

ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS customer_code TEXT,
    ADD COLUMN IF NOT EXISTS date_of_birth DATE,
    ADD COLUMN IF NOT EXISTS address_street TEXT,
    ADD COLUMN IF NOT EXISTS address_postal_code TEXT,
    ADD COLUMN IF NOT EXISTS address_city TEXT,
    ADD COLUMN IF NOT EXISTS address_country TEXT,
    ADD COLUMN IF NOT EXISTS preferred_contact_channel TEXT,
    ADD COLUMN IF NOT EXISTS quick_internal_note TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_customer_code_unique
    ON customers(customer_code)
    WHERE customer_code IS NOT NULL;

-- ============================================================================
-- Customer interactions: richer channel and experiment metadata
-- ============================================================================

ALTER TABLE customer_interactions
    DROP CONSTRAINT IF EXISTS customer_interactions_type_check;

ALTER TABLE customer_interactions
    ADD CONSTRAINT customer_interactions_type_check
    CHECK (
        type IN (
            'phone',
            'chat',
            'email',
            'mobile_app_chat',
            'portal_message',
            'secure_message',
            'branch_visit',
            'service_desk',
            'video_call'
        )
    );

ALTER TABLE customer_interactions
    ADD COLUMN IF NOT EXISTS direction TEXT
        CHECK (direction IN ('inbound', 'outbound')),
    ADD COLUMN IF NOT EXISTS topic TEXT,
    ADD COLUMN IF NOT EXISTS subtopic TEXT,
    ADD COLUMN IF NOT EXISTS sentiment TEXT,
    ADD COLUMN IF NOT EXISTS priority TEXT,
    ADD COLUMN IF NOT EXISTS owner_team TEXT,
    ADD COLUMN IF NOT EXISTS status TEXT,
    ADD COLUMN IF NOT EXISTS resolution_time_hours INTEGER,
    ADD COLUMN IF NOT EXISTS sla_breached BOOLEAN,
    ADD COLUMN IF NOT EXISTS follow_up_required BOOLEAN,
    ADD COLUMN IF NOT EXISTS related_case_id TEXT,
    ADD COLUMN IF NOT EXISTS csat INTEGER;

-- ============================================================================
-- RLS: scenarios + session_events
-- ============================================================================

ALTER TABLE scenarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anyone can view active scenarios" ON scenarios;
DROP POLICY IF EXISTS "Service can manage scenarios" ON scenarios;

CREATE POLICY "Anyone can view active scenarios"
    ON scenarios FOR SELECT
    USING (status = 'active');

CREATE POLICY "Service can manage scenarios"
    ON scenarios FOR ALL
    USING (auth.role() = 'service_role');

DROP POLICY IF EXISTS "Users can view session events" ON session_events;
DROP POLICY IF EXISTS "Users can insert session events" ON session_events;
DROP POLICY IF EXISTS "Service can manage session events" ON session_events;

CREATE POLICY "Users can view session events"
    ON session_events FOR SELECT
    USING (true);

CREATE POLICY "Users can insert session events"
    ON session_events FOR INSERT
    WITH CHECK (true);

CREATE POLICY "Service can manage session events"
    ON session_events FOR ALL
    USING (auth.role() = 'service_role');
