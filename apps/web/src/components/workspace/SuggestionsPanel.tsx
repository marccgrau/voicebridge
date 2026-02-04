"use client";

import { useState } from "react";
import type { Suggestion } from "@voicebridge/contracts";
import { submitSuggestionFeedback } from "@/lib/supabase";

interface SuggestionsPanelProps {
  suggestions: Suggestion[];
  isConnected: boolean;
  sessionId: string | null;
}

export function SuggestionsPanel({
  suggestions,
  isConnected,
  sessionId,
}: SuggestionsPanelProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = async (suggestion: Suggestion) => {
    await navigator.clipboard.writeText(suggestion.text);
    setCopiedId(suggestion.id);
    setTimeout(() => setCopiedId(null), 2000);

    // Submit feedback
    if (sessionId) {
      try {
        await submitSuggestionFeedback(sessionId, suggestion.id, "used");
      } catch (error) {
        console.error("Failed to submit feedback:", error);
      }
    }
  };

  const handleDismiss = async (suggestion: Suggestion) => {
    if (sessionId) {
      try {
        await submitSuggestionFeedback(sessionId, suggestion.id, "dismissed");
      } catch (error) {
        console.error("Failed to submit feedback:", error);
      }
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="font-semibold">Suggested Responses</h2>
        {suggestions.length > 0 && (
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            {suggestions.length} suggestions
          </span>
        )}
      </div>

      {/* Suggestions content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {suggestions.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">
              {isConnected
                ? "Suggestions will appear based on the conversation"
                : "Start a session to receive suggestions"}
            </p>
          </div>
        ) : (
          suggestions.map((suggestion) => (
            <SuggestionCard
              key={suggestion.id}
              suggestion={suggestion}
              isCopied={copiedId === suggestion.id}
              onCopy={() => handleCopy(suggestion)}
              onDismiss={() => handleDismiss(suggestion)}
            />
          ))
        )}
      </div>
    </div>
  );
}

interface SuggestionCardProps {
  suggestion: Suggestion;
  isCopied: boolean;
  onCopy: () => void;
  onDismiss: () => void;
}

function SuggestionCard({
  suggestion,
  isCopied,
  onCopy,
  onDismiss,
}: SuggestionCardProps) {
  const typeStyles: Record<Suggestion["type"], string> = {
    response: "border-l-info",
    question: "border-l-warning",
    action: "border-l-success",
    escalation: "border-l-destructive",
  };

  const typeLabels: Record<Suggestion["type"], string> = {
    response: "Response",
    question: "Question",
    action: "Action",
    escalation: "Escalate",
  };

  return (
    <div
      className={`rounded-lg border border-border bg-card p-3 border-l-4 ${
        typeStyles[suggestion.type]
      }`}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">
          {typeLabels[suggestion.type]}
        </span>
        {suggestion.confidence && (
          <span className="text-xs text-muted-foreground">
            {Math.round(suggestion.confidence * 100)}% confidence
          </span>
        )}
      </div>

      <p className="mb-3 text-sm">{suggestion.text}</p>

      <div className="flex items-center gap-2">
        <button
          onClick={onCopy}
          className="rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90"
        >
          {isCopied ? "Copied!" : "Copy"}
        </button>
        <button
          onClick={onDismiss}
          className="rounded-md bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground hover:bg-muted/80"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
