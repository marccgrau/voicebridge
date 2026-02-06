"use client";

import { createClient, RealtimeChannel } from "@supabase/supabase-js";
import { useEffect, useRef } from "react";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export interface TranscriptSegment {
  id: string;
  session_id: string;
  speaker: "agent" | "customer";
  text: string;
  is_final: boolean;
  ts: string;
  confidence?: number;
}

export interface SubscriptionHandlers {
  onTranscriptSegment?: (segment: TranscriptSegment) => void;
}

/**
 * Hook to subscribe to real-time transcript updates for a session
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

    const channelName = `session:${sessionId}:transcript`;

    // Create channel and subscribe to transcript_segments table
    const channel = supabase
      .channel(channelName)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "transcript_segments",
          filter: `session_id=eq.${sessionId}`,
        },
        (payload) => {
          const segment = payload.new as TranscriptSegment;
          const h = handlersRef.current;

          // Only notify on final transcripts
          if (segment.is_final) {
            h.onTranscriptSegment?.(segment);
          }
        }
      )
      .subscribe();

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
