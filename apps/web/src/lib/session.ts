"use client";

import { useState, useCallback, useEffect } from "react";

const ORCHESTRATOR_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8000";
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
      const response = await fetch(`${ORCHESTRATOR_URL}/sessions/${sessionId}/status`);
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

  const startSession = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const response = await fetch(`${ORCHESTRATOR_URL}/sessions/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to start session");
      }

      const data = await response.json();

      // Store session ID
      localStorage.setItem(SESSION_STORAGE_KEY, data.session_id);

      setState({
        sessionId: data.session_id,
        roomUrl: data.room_url,
        roomToken: data.room_token,
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

      // Clear storage
      localStorage.removeItem(SESSION_STORAGE_KEY);

      setState({
        sessionId: null,
        roomUrl: null,
        roomToken: null,
        isConnected: false,
        isLoading: false,
        error: null,
      });
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

  return {
    ...state,
    startSession,
    stopSession,
  };
}

/**
 * Generate a new session ID (client-side)
 */
export function generateSessionId(): string {
  return crypto.randomUUID();
}
