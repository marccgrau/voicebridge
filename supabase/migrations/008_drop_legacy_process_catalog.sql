-- 008_drop_legacy_process_catalog.sql
-- Remove legacy DB-backed process catalog. PCC now loads process definitions
-- from markdown files in services/pcc/process_content/.

DROP FUNCTION IF EXISTS search_processes(TEXT, TEXT, TEXT, TEXT, INTEGER);
DROP TRIGGER IF EXISTS update_process_catalog_updated_at ON process_catalog;
DROP TABLE IF EXISTS process_catalog CASCADE;
