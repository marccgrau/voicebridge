-- Add summary fields to sessions table for postcall notes
ALTER TABLE sessions ADD COLUMN summary_text TEXT;
ALTER TABLE sessions ADD COLUMN summary_updated_at TIMESTAMPTZ;
ALTER TABLE sessions ADD COLUMN summary_updated_by TEXT;
