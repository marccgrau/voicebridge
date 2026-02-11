-- 005_update_suggestion_service_modes.sql
-- Keep historical split_flows values and allow direct_call for active guidance.

ALTER TABLE sessions
    DROP CONSTRAINT IF EXISTS sessions_suggestion_service_check;

ALTER TABLE sessions
    ADD CONSTRAINT sessions_suggestion_service_check
    CHECK (suggestion_service IN ('split_flows', 'direct_call'));

COMMENT ON COLUMN sessions.suggestion_service IS
    'Suggestion service type: split_flows (legacy historical), direct_call (active)';
