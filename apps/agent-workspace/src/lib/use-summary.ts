"use client";

import { useState, useCallback, useEffect, useRef } from "react";

const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:8000";

interface UseSummaryReturn {
  summaryText: string;
  setSummaryText: (text: string) => void;
  isGenerating: boolean;
  isSaving: boolean;
  isSaved: boolean;
  error: string | null;
  saveSummary: (sessionId: string) => Promise<void>;
  generateSummary: (sessionId: string) => Promise<void>;
}

interface UseSummaryOptions {
  autoGenerate: boolean;
  onSaveComplete?: () => void;
}

/**
 * Hook for managing session summary state.
 * When a sessionId is provided and autoGenerate is true, automatically
 * calls the backend to generate a summary from the transcript.
 */
export function useSummary(
  sessionId: string | null,
  options: boolean | UseSummaryOptions
): UseSummaryReturn {
  // Support both old boolean API and new options API
  const { autoGenerate, onSaveComplete } =
    typeof options === "boolean"
      ? { autoGenerate: options, onSaveComplete: undefined }
      : options;
  const [summaryText, setSummaryText] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generatedForRef = useRef<string | null>(null);

  const generateSummary = useCallback(async (sid: string) => {
    setIsGenerating(true);
    setError(null);
    setIsSaved(false);

    try {
      const response = await fetch(
        `${ORCHESTRATOR_URL}/sessions/${sid}/generate-summary`,
        { method: "POST" }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Failed to generate summary");
      }

      const data = await response.json();
      setSummaryText(data.summary_text);
      generatedForRef.current = sid;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
    } finally {
      setIsGenerating(false);
    }
  }, []);

  // Auto-generate when entering postcall for a session
  useEffect(() => {
    if (autoGenerate && sessionId && generatedForRef.current !== sessionId) {
      generatedForRef.current = sessionId; // Mark immediately to prevent double-trigger
      generateSummary(sessionId);
    }
  }, [autoGenerate, sessionId, generateSummary]);

  // Reset when session changes
  useEffect(() => {
    if (!sessionId) {
      setSummaryText("");
      setIsGenerating(false);
      setIsSaving(false);
      setIsSaved(false);
      setError(null);
      generatedForRef.current = null;
    }
  }, [sessionId]);

  const saveSummary = useCallback(
    async (sid: string) => {
      if (!summaryText.trim()) {
        setError("Summary cannot be empty");
        return;
      }

      setIsSaving(true);
      setError(null);
      setIsSaved(false);

      try {
        const response = await fetch(`${ORCHESTRATOR_URL}/sessions/summary`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sid,
            summary_text: summaryText.trim(),
          }),
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || "Failed to save summary");
        }

        setIsSaved(true);

        // Call completion callback after successful save
        if (onSaveComplete) {
          // Small delay to let user see the "Saved" indicator
          setTimeout(() => {
            onSaveComplete();
          }, 1000);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
      } finally {
        setIsSaving(false);
      }
    },
    [summaryText, onSaveComplete]
  );

  return {
    summaryText,
    setSummaryText,
    isGenerating,
    isSaving,
    isSaved,
    error,
    saveSummary,
    generateSummary,
  };
}
