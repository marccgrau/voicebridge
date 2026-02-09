/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import type { PendingSession } from "./pending-sessions";

export type UIPhase =
  | "idle"
  | "incoming"
  | "active_preprocess"
  | "active_inprocess"
  | "postcall_summary";

export type PanelVariant = "expanded" | "compact";

export interface PanelDensity {
  customer: PanelVariant;
  transcript: PanelVariant;
  suggestions: PanelVariant;
}

const PHASE_DEFAULTS: Record<UIPhase, PanelDensity> = {
  idle: {
    customer: "expanded",
    transcript: "expanded",
    suggestions: "expanded",
  },
  incoming: {
    customer: "expanded",
    transcript: "expanded",
    suggestions: "expanded",
  },
  active_preprocess: {
    customer: "compact",
    transcript: "expanded",
    suggestions: "expanded",
  },
  active_inprocess: {
    customer: "compact",
    transcript: "expanded",
    suggestions: "expanded",
  },
  postcall_summary: {
    customer: "compact",
    transcript: "compact",
    suggestions: "compact",
  },
};

const TERMINAL_STATUSES = new Set(["completed", "abandoned", "escalated"]);
const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8000";
const DISCONNECT_DEBOUNCE_MS = 3000;

interface UsePhaseParams {
  sessionId: string | null;
  isConnected: boolean;
  processKey: string | null;
  pendingSessions: PendingSession[];
  sessionStatus?: string | null;
}

export function usePhase({
  sessionId,
  isConnected,
  processKey,
  pendingSessions,
  sessionStatus,
}: UsePhaseParams) {
  const [phase, setPhase] = useState<UIPhase>("idle");
  const [densityOverrides, setDensityOverrides] = useState<
    Partial<PanelDensity>
  >({});
  const previousPhaseRef = useRef<UIPhase>("idle");
  const disconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevSessionIdRef = useRef<string | null>(null);

  // Derive phase from signals
  useEffect(() => {
    // Terminal session status → postcall
    if (sessionStatus && TERMINAL_STATUSES.has(sessionStatus)) {
      if (disconnectTimerRef.current) {
        clearTimeout(disconnectTimerRef.current);
        disconnectTimerRef.current = null;
      }
      setPhase("postcall_summary");
      return;
    }

    // Connected with active session
    if (isConnected && sessionId) {
      if (disconnectTimerRef.current) {
        clearTimeout(disconnectTimerRef.current);
        disconnectTimerRef.current = null;
      }
      setPhase(processKey ? "active_inprocess" : "active_preprocess");
      return;
    }

    // Disconnected but sessionId still set — session was stopped or transient disconnect.
    // Use debounced fetch to determine if terminal.
    if (!isConnected && sessionId) {
      if (!disconnectTimerRef.current) {
        disconnectTimerRef.current = setTimeout(async () => {
          disconnectTimerRef.current = null;
          try {
            const res = await fetch(
              `${ORCHESTRATOR_URL}/sessions/${sessionId}/status`
            );
            if (res.ok) {
              const data = await res.json();
              if (TERMINAL_STATUSES.has(data.status)) {
                setPhase("postcall_summary");
                return;
              }
            }
          } catch {
            // On fetch failure, assume postcall if we were previously active
          }
          // If we were active before, go to postcall. Otherwise stay put.
          if (previousPhaseRef.current.startsWith("active_")) {
            setPhase("postcall_summary");
          }
        }, DISCONNECT_DEBOUNCE_MS);
      }
      return; // Hold current phase while debouncing
    }

    // No session at all
    if (!sessionId && pendingSessions.length > 0) {
      setPhase("incoming");
      return;
    }

    setPhase("idle");
  }, [
    sessionId,
    isConnected,
    processKey,
    pendingSessions.length,
    sessionStatus,
  ]);

  // Track previous phase
  useEffect(() => {
    previousPhaseRef.current = phase;
  }, [phase]);

  // Reset density overrides on phase change
  useEffect(() => {
    setDensityOverrides({});
  }, [phase]);

  // Reset state when sessionId changes (new session)
  useEffect(() => {
    if (sessionId !== prevSessionIdRef.current) {
      prevSessionIdRef.current = sessionId;
      setDensityOverrides({});
    }
  }, [sessionId]);

  // Cleanup disconnect timer on unmount
  useEffect(() => {
    return () => {
      if (disconnectTimerRef.current) {
        clearTimeout(disconnectTimerRef.current);
      }
    };
  }, []);

  const phaseDefaults = PHASE_DEFAULTS[phase];

  const density: PanelDensity = useMemo(
    () => ({ ...phaseDefaults, ...densityOverrides }),
    [phaseDefaults, densityOverrides]
  );

  const toggleDensity = (panel: keyof PanelDensity) => {
    setDensityOverrides((prev) => {
      const current = prev[panel] ?? phaseDefaults[panel];
      return {
        ...prev,
        [panel]: current === "expanded" ? "compact" : "expanded",
      };
    });
  };

  return {
    phase,
    density,
    toggleDensity,
    phaseDefaults,
  };
}
