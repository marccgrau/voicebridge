"use client";

import { useState, useCallback, useEffect } from "react";

const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8000";
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
 * Hook for managing voice session state
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
      // Check if session is still active
      checkSession(storedSessionId);
    }
  }, []);

  const checkSession = async (sessionId: string) => {
    try {
      const response = await fetch(
        `${ORCHESTRATOR_URL}/sessions/${sessionId}/status`
      );
      if (response.ok) {
        const data = await response.json();
        if (data.is_active) {
          setState((prev) => ({
            ...prev,
            sessionId,
            isConnected: true,
          }));
          return;
        }
      }
      // Session not active, clear storage
      localStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
  };

  const acceptSession = useCallback(async (sessionId: string) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await fetch(`${ORCHESTRATOR_URL}/sessions/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to accept session");
      }

      const data = await response.json();

      localStorage.setItem(SESSION_STORAGE_KEY, data.session_id);

      setState({
        sessionId: data.session_id,
        roomUrl: data.room_url,
        roomToken: data.agent_token,
        isConnected: true,
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

  const stopSession = useCallback(async () => {
    if (!state.sessionId) return;

    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await fetch(`${ORCHESTRATOR_URL}/sessions/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: state.sessionId }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to stop session");
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
