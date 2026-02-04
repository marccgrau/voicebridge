import type { SupabaseClient } from "@supabase/supabase-js";
import type { SessionState, SessionConfig } from "@voicebridge/contracts";

export interface SessionRow {
  id: string;
  process_key: string | null;
  state: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
}

/**
 * Create a new session
 */
export async function createSession(
  client: SupabaseClient,
  config: SessionConfig
): Promise<SessionRow> {
  const { data, error } = await client
    .from("sessions")
    .insert({
      id: config.sessionId,
      process_key: null,
      state: {
        locale: config.locale,
        domain: config.domain,
        queueTag: config.queueTag,
        agentId: config.agentId,
        customerId: config.customerId,
        metadata: config.metadata,
        slots: {},
        steps: [],
        currentStep: null,
      },
      status: "active",
    })
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to create session: ${error.message}`);
  }

  return data;
}

/**
 * Get session by ID
 */
export async function getSession(
  client: SupabaseClient,
  sessionId: string
): Promise<SessionRow | null> {
  const { data, error } = await client
    .from("sessions")
    .select("*")
    .eq("id", sessionId)
    .single();

  if (error) {
    if (error.code === "PGRST116") {
      return null;
    }
    throw new Error(`Failed to get session: ${error.message}`);
  }

  return data;
}

/**
 * Update session state
 */
export async function updateSessionState(
  client: SupabaseClient,
  sessionId: string,
  updates: Partial<{
    process_key: string | null;
    state: Record<string, unknown>;
    status: string;
  }>
): Promise<SessionRow> {
  const { data, error } = await client
    .from("sessions")
    .update({
      ...updates,
      updated_at: new Date().toISOString(),
    })
    .eq("id", sessionId)
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to update session: ${error.message}`);
  }

  return data;
}

/**
 * Convert database row to SessionState
 */
export function rowToSessionState(row: SessionRow): SessionState {
  const state = row.state as Record<string, unknown>;
  return {
    sessionId: row.id,
    processKey: row.process_key,
    processName: (state.processName as string) ?? null,
    currentStep: (state.currentStep as string) ?? null,
    steps: (state.steps as SessionState["steps"]) ?? [],
    slots: (state.slots as Record<string, string>) ?? {},
    status: row.status as SessionState["status"],
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}
