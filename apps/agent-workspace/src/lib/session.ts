"use client";

import { useState, useCallback, useEffect } from "react";

import { supabase } from "./supabase";

const SESSION_STORAGE_KEY = "voicebridge_session_id";

export interface SessionState {
  sessionId: string | null;
  roomUrl: string | null;
  roomToken: string | null;
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
}

/**
 * Hook for managing voice session state.
 *
 * Reads session data (room_url, agent_token) directly from Supabase
 * instead of calling the orchestrator. The PCC bot is already running
 * when the agent accepts — no need to start anything server-side.
 */
export function useSession() {
  const [state, setState] = useState<SessionState>({
    sessionId: null,
    roomUrl: null,
    roomToken: null,
    isConnected: false,
    isLoading: false,
    error: null,
  });

  // Restore session from localStorage on mount
  useEffect(() => {
    const storedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (storedSessionId) {
      checkSession(storedSessionId);
    }
  }, []);

  const checkSession = async (sessionId: string) => {
    try {
      const { data, error } = await supabase
        .from("sessions")
        .select("id, status, room_url, agent_token, created_at")
        .eq("id", sessionId)
        .single();

      if (error || !data) {
        localStorage.removeItem(SESSION_STORAGE_KEY);
        return;
      }

      // Clear terminal states (completed, abandoned, escalated, error)
      const terminalStatuses = ["completed", "abandoned", "escalated", "error"];
      if (terminalStatuses.includes(data.status)) {
        localStorage.removeItem(SESSION_STORAGE_KEY);
        return;
      }

      // Clear stale sessions (>1 hour old)
      const createdAt = new Date(data.created_at);
      const ageMs = Date.now() - createdAt.getTime();
      const ONE_HOUR_MS = 60 * 60 * 1000;
      if (ageMs > ONE_HOUR_MS) {
        localStorage.removeItem(SESSION_STORAGE_KEY);
        return;
      }

      // Only restore truly active sessions with complete data
      if (data.status === "active" && data.room_url && data.agent_token) {
        setState((prev) => ({
          ...prev,
          sessionId: data.id,
          roomUrl: data.room_url,
          roomToken: data.agent_token,
          isConnected: true,
        }));
        return;
      }

      // All other cases: clear localStorage
      localStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
  };

  const acceptSession = useCallback(async (sessionId: string) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // Read session from Supabase to get room_url and agent_token
      const { data: session, error: fetchError } = await supabase
        .from("sessions")
        .select("id, room_url, agent_token, status")
        .eq("id", sessionId)
        .single();

      if (fetchError || !session) {
        throw new Error(fetchError?.message || "Session not found");
      }

      if (session.status !== "pending") {
        throw new Error(`Session is not pending (status: ${session.status})`);
      }

      if (!session.agent_token || !session.room_url) {
        throw new Error("Session missing agent_token or room_url");
      }

      // Update session status to active
      const { error: updateError } = await supabase
        .from("sessions")
        .update({
          status: "active",
          agent_joined_at: new Date().toISOString(),
        })
        .eq("id", sessionId)
        .eq("status", "pending");

      if (updateError) {
        throw new Error(`Failed to accept session: ${updateError.message}`);
      }

      localStorage.setItem(SESSION_STORAGE_KEY, session.id);

      setState({
        sessionId: session.id,
        roomUrl: session.room_url,
        roomToken: session.agent_token,
        isConnected: true,
        isLoading: false,
        error: null,
      });

      return {
        session_id: session.id,
        room_url: session.room_url,
        agent_token: session.agent_token,
      };
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

  const stopSession = useCallback(async () => {
    if (!state.sessionId) return;

    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      // Update session status to completed in Supabase
      const { error: updateError } = await supabase
        .from("sessions")
        .update({ status: "completed" })
        .eq("id", state.sessionId);

      if (updateError) {
        throw new Error(`Failed to stop session: ${updateError.message}`);
      }

      // Keep sessionId so postcall_summary phase can activate.
      // Disconnect from room but preserve session reference.
      localStorage.removeItem(SESSION_STORAGE_KEY);

      setState((prev) => ({
        ...prev,
        roomUrl: null,
        roomToken: null,
        isConnected: false,
        isLoading: false,
        error: null,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: message,
      }));
      throw error;
    }
  }, [state.sessionId]);

  /** Fully clear session state — call when leaving postcall to return to idle. */
  const clearSession = useCallback(() => {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    setState({
      sessionId: null,
      roomUrl: null,
      roomToken: null,
      isConnected: false,
      isLoading: false,
      error: null,
    });
  }, []);

  return {
    ...state,
    acceptSession,
    stopSession,
    clearSession,
  };
}

/**
 * Generate a new session ID (client-side)
 */
export function generateSessionId(): string {
  return crypto.randomUUID();
}
