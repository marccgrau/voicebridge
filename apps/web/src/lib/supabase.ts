"use client";

import { createClient, RealtimeChannel } from "@supabase/supabase-js";
import { useEffect, useRef } from "react";
import type {
  TranscriptSegmentEvent,
  ProcessSelectionEvent,
  SlotExtractionEvent,
  SuggestionEvent,
  SessionStateEvent,
  VoiceBridgeEvent,
} from "@voicebridge/contracts";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export interface SubscriptionHandlers {
  onTranscriptSegment?: (event: TranscriptSegmentEvent) => void;
  onProcessSelection?: (event: ProcessSelectionEvent) => void;
  onSlotExtraction?: (event: SlotExtractionEvent) => void;
  onSuggestion?: (event: SuggestionEvent) => void;
  onSessionState?: (event: SessionStateEvent) => void;
  onAnyEvent?: (event: VoiceBridgeEvent) => void;
}

/**
 * Hook to subscribe to real-time events for a session
 */
export function useSupabaseSubscription(
  sessionId: string | null,
  handlers: SubscriptionHandlers
) {
  const channelRef = useRef<RealtimeChannel | null>(null);
  const handlersRef = useRef(handlers);

  // Keep handlers ref updated
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    if (!sessionId) {
      // Cleanup existing subscription
      if (channelRef.current) {
        channelRef.current.unsubscribe();
        channelRef.current = null;
      }
      return;
    }

    const channelName = `session:${sessionId}:events`;

    // Create channel and subscribe
    const channel = supabase.channel(channelName);

    channel.on("broadcast", { event: "event" }, ({ payload }) => {
      const event = payload as VoiceBridgeEvent;
      const h = handlersRef.current;

      // Call type-specific handler
      switch (event.type) {
        case "transcript_segment":
          h.onTranscriptSegment?.(event);
          break;
        case "process_selection":
          h.onProcessSelection?.(event);
          break;
        case "slot_extraction":
          h.onSlotExtraction?.(event);
          break;
        case "suggestion":
          h.onSuggestion?.(event);
          break;
        case "session_state":
          h.onSessionState?.(event);
          break;
      }

      // Call generic handler
      h.onAnyEvent?.(event);
    });

    channel.subscribe();
    channelRef.current = channel;

    // Cleanup on unmount or session change
    return () => {
      channel.unsubscribe();
      channelRef.current = null;
    };
  }, [sessionId]);
}

/**
 * Fetch session data from Supabase
 */
export async function fetchSession(sessionId: string) {
  const { data, error } = await supabase
    .from("sessions")
    .select("*")
    .eq("id", sessionId)
    .single();

  if (error) throw error;
  return data;
}

/**
 * Fetch transcript for a session
 */
export async function fetchTranscript(sessionId: string) {
  const { data, error } = await supabase
    .from("transcript_segments")
    .select("*")
    .eq("session_id", sessionId)
    .eq("is_final", true)
    .order("ts", { ascending: true });

  if (error) throw error;
  return data ?? [];
}

/**
 * Submit suggestion feedback
 */
export async function submitSuggestionFeedback(
  sessionId: string,
  suggestionId: string,
  action: "used" | "modified" | "dismissed",
  modifiedText?: string
) {
  const { error } = await supabase.from("suggestion_feedback").insert({
    session_id: sessionId,
    suggestion_id: suggestionId,
    action,
    modified_text: modifiedText,
  });

  if (error) throw error;
}
