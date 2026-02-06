"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { supabase } from "./supabase";
import type { RealtimeChannel } from "@supabase/supabase-js";

import { env } from "./env";

const ORCHESTRATOR_URL = env.NEXT_PUBLIC_ORCHESTRATOR_URL;

export type CustomerCallState = "idle" | "calling" | "connected" | "ended";

export interface CustomerSessionState {
  callState: CustomerCallState;
  sessionId: string | null;
  roomUrl: string | null;
  customerToken: string | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * Hook for customer-initiated call sessions.
 */
export function useCustomerSession() {
  const [state, setState] = useState<CustomerSessionState>({
    callState: "idle",
    sessionId: null,
    roomUrl: null,
    customerToken: null,
    isLoading: false,
    error: null,
  });

  const channelRef = useRef<RealtimeChannel | null>(null);

  // Subscribe to session updates to detect when agent joins
  useEffect(() => {
    const sessionId = state.sessionId;
    if (!sessionId || state.callState !== "calling") {
      if (channelRef.current) {
        channelRef.current.unsubscribe();
        channelRef.current = null;
      }
      return;
    }

    const channel = supabase
      .channel(`customer-session:${sessionId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "sessions",
          filter: `id=eq.${sessionId}`,
        },
        (payload) => {
          const updated = payload.new as { status: string };
          if (updated.status === "active") {
            setState((prev) => ({ ...prev, callState: "connected" }));
          } else if (
            updated.status === "completed" ||
            updated.status === "abandoned"
          ) {
            setState((prev) => ({
              ...prev,
              callState: "ended",
              roomUrl: null,
              customerToken: null,
            }));
          }
        }
      )
      .subscribe();

    channelRef.current = channel;

    return () => {
      channel.unsubscribe();
      channelRef.current = null;
    };
  }, [state.sessionId, state.callState]);

  const startCall = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await fetch(`${ORCHESTRATOR_URL}/sessions/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to create session");
      }

      const data = await response.json();

      setState({
        callState: "calling",
        sessionId: data.session_id,
        roomUrl: data.room_url,
        customerToken: data.customer_token,
        isLoading: false,
        error: null,
      });

      return data;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: message,
      }));
      throw error;
    }
  }, []);

  const endCall = useCallback(async () => {
    if (!state.sessionId) return;

    setState((prev) => ({ ...prev, isLoading: true }));

    try {
      await fetch(`${ORCHESTRATOR_URL}/sessions/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: state.sessionId }),
      });
    } catch {
      // Best-effort stop
    }

    setState({
      callState: "ended",
      sessionId: null,
      roomUrl: null,
      customerToken: null,
      isLoading: false,
      error: null,
    });
  }, [state.sessionId]);

  return {
    ...state,
    startCall,
    endCall,
  };
}
