-- 010_customer_scenario_mapping.sql
-- Add fixed scenario_id to customers for 1:1 persona-scenario mapping.

ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS scenario_id TEXT
        REFERENCES scenarios(scenario_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_customers_scenario_id
    ON customers(scenario_id)
    WHERE scenario_id IS NOT NULL;

-- Scenario mappings are set by the seed script and migration 011.
