import type { SupabaseClient } from "@supabase/supabase-js";
import type { TranscriptEntry } from "@voicebridge/contracts";

export interface TranscriptSegmentRow {
  id: string;
  session_id: string;
  speaker: string;
  text: string;
  is_final: boolean;
  confidence: number | null;
  ts: string;
}

/**
 * Insert a transcript segment
 */
export async function insertTranscriptSegment(
  client: SupabaseClient,
  segment: {
    sessionId: string;
    speaker: "agent" | "customer";
    text: string;
    isFinal: boolean;
    confidence?: number;
  }
): Promise<TranscriptSegmentRow> {
  const { data, error } = await client
    .from("transcript_segments")
    .insert({
      session_id: segment.sessionId,
      speaker: segment.speaker,
      text: segment.text,
      is_final: segment.isFinal,
      confidence: segment.confidence,
    })
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to insert transcript segment: ${error.message}`);
  }

  return data;
}

/**
 * Get transcript segments for a session
 */
export async function getTranscriptSegments(
  client: SupabaseClient,
  sessionId: string,
  options?: {
    limit?: number;
    finalOnly?: boolean;
  }
): Promise<TranscriptSegmentRow[]> {
  let query = client
    .from("transcript_segments")
    .select("*")
    .eq("session_id", sessionId)
    .order("ts", { ascending: true });

  if (options?.finalOnly) {
    query = query.eq("is_final", true);
  }

  if (options?.limit) {
    query = query.limit(options.limit);
  }

  const { data, error } = await query;

  if (error) {
    throw new Error(`Failed to get transcript segments: ${error.message}`);
  }

  return data ?? [];
}

/**
 * Convert database row to TranscriptEntry
 */
export function rowToTranscriptEntry(row: TranscriptSegmentRow): TranscriptEntry {
  return {
    id: row.id,
    speaker: row.speaker as "agent" | "customer",
    text: row.text,
    timestamp: row.ts,
    isFinal: row.is_final,
  };
}

/**
 * Get recent conversation context as text
 */
export async function getConversationContext(
  client: SupabaseClient,
  sessionId: string,
  maxTurns: number = 10
): Promise<string> {
  const segments = await getTranscriptSegments(client, sessionId, {
    limit: maxTurns,
    finalOnly: true,
  });

  return segments
    .map((s) => `${s.speaker.toUpperCase()}: ${s.text}`)
    .join("\n");
}
