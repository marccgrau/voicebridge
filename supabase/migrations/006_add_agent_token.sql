-- Add agent_token column to sessions table
-- The customer route creates this token when starting a session,
-- and the agent workspace reads it when accepting a call.
ALTER TABLE sessions ADD COLUMN agent_token TEXT;
