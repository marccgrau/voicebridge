"use client";

import { useEffect, useRef, useState } from "react";
import { supabase } from "./supabase";
import type { RealtimeChannel } from "@supabase/supabase-js";

export interface PendingSession {
  id: string;
  status: string;
  room_url: string;
  room_name: string;
  created_at: string;
  customer_joined_at: string | null;
  state: Record<string, unknown>;
}

/**
 * Hook to track pending (customer-initiated) sessions via Supabase Realtime.
 * Fetches existing pending sessions on mount and subscribes to changes.
 */
export function usePendingSessions() {
  const [sessions, setSessions] = useState<PendingSession[]>([]);
  const channelRef = useRef<RealtimeChannel | null>(null);

  useEffect(() => {
    // Fetch existing pending sessions
    supabase
      .from("sessions")
      .select(
        "id, status, room_url, room_name, created_at, customer_joined_at, state"
      )
      .eq("status", "pending")
      .order("created_at", { ascending: false })
      .then(({ data }) => {
        if (data) {
          setSessions(data as PendingSession[]);
        }
      });

    // Subscribe to realtime changes on sessions table
    const channel = supabase
      .channel("pending-sessions")
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "sessions",
          filter: "status=eq.pending",
        },
        (payload) => {
          const newSession = payload.new as PendingSession;
          setSessions((prev) => [newSession, ...prev]);
        }
      )
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "sessions",
        },
        (payload) => {
          const updated = payload.new as PendingSession;
          // Remove session from pending list if it's no longer pending
          if (updated.status !== "pending") {
            setSessions((prev) => prev.filter((s) => s.id !== updated.id));
          }
        }
      )
      .subscribe();

    channelRef.current = channel;

    return () => {
      channel.unsubscribe();
      channelRef.current = null;
    };
  }, []);

  return { pendingSessions: sessions };
}
