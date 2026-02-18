-- 009_cross_combinable_experiments.sql
-- Add domain to customers and actor_guidance to scenarios for cross-combinable experiments.

-- ============================================================================
-- Customers: domain field for persona/scenario domain filtering
-- ============================================================================

ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS domain TEXT;

-- ============================================================================
-- Scenarios: actor guidance for structured actor briefings
-- ============================================================================

ALTER TABLE scenarios
    ADD COLUMN IF NOT EXISTS actor_guidance JSONB;
