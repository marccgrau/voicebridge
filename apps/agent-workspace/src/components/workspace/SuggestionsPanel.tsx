"use client";

import type { Suggestion } from "@voicebridge/contracts";
import type { PanelVariant } from "@/lib/use-phase";

interface SuggestionsPanelProps {
  suggestions: Suggestion[];
  isConnected: boolean;
  sessionId: string | null;
  variant?: PanelVariant;
  onToggle?: () => void;
}

export function SuggestionsPanel({
  suggestions,
  isConnected,
  variant = "expanded",
  onToggle,
}: SuggestionsPanelProps) {
  if (variant === "compact") {
    const topSuggestion = suggestions[0];

    return (
      <button
        onClick={onToggle}
        className="panel-morph flex w-full items-center gap-3 rounded-2xl border border-border/60 bg-card px-4 py-3 text-left shadow-sm hover:shadow-md transition-shadow"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        <span className="text-sm font-medium text-muted-foreground">
          Suggestions
        </span>
        {suggestions.length > 0 && (
          <span className="rounded-lg bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
            {suggestions.length}
          </span>
        )}
        {topSuggestion && (
          <span className="ml-auto rounded-lg bg-muted px-2 py-0.5 text-xs text-muted-foreground capitalize">
            {topSuggestion.type}
          </span>
        )}
      </button>
    );
  }

  return (
    <div className="panel-morph flex h-full flex-col">
      {/* Header */}
      <button
        onClick={onToggle}
        disabled={!onToggle}
        className="flex items-center justify-between border-b border-border/60 px-5 py-4 text-left disabled:cursor-default"
      >
        <span className="font-mono-ui flex items-center gap-2 text-sm uppercase tracking-wide text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Suggested Responses
        </span>
        {suggestions.length > 0 && (
          <span className="rounded-lg bg-accent/10 px-2.5 py-1 text-sm font-medium text-accent">
            {suggestions.length}
          </span>
        )}
      </button>

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
            <SuggestionCard key={suggestion.id} suggestion={suggestion} />
          ))
        )}
      </div>
    </div>
  );
}

interface SuggestionCardProps {
  suggestion: Suggestion;
}

function SuggestionCard({ suggestion }: SuggestionCardProps) {
  const typeConfig: Record<
    Suggestion["type"],
    { color: string; bgColor: string; label: string }
  > = {
    response: {
      color: "text-info",
      bgColor: "bg-info/5 border-l-info",
      label: "Response",
    },
    question: {
      color: "text-warning",
      bgColor: "bg-warning/5 border-l-warning",
      label: "Question",
    },
    action: {
      color: "text-success",
      bgColor: "bg-success/5 border-l-success",
      label: "Action",
    },
    escalation: {
      color: "text-destructive",
      bgColor: "bg-destructive/5 border-l-destructive",
      label: "Escalate",
    },
  };

  const config = typeConfig[suggestion.type];

  return (
    <div
      className={`rounded-xl border border-border ${config.bgColor} p-4 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all border-l-4`}
    >
      <div className="mb-2.5 flex items-center justify-between">
        <span
          className={`font-mono-ui flex items-center gap-1.5 text-xs uppercase tracking-wide ${config.color} font-medium`}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          {config.label}
        </span>
        {suggestion.confidence && (
          <span className="font-mono-ui text-xs text-muted-foreground">
            {Math.round(suggestion.confidence * 100)}%
          </span>
        )}
      </div>

      <p className="text-sm leading-relaxed text-foreground">
        {suggestion.text}
      </p>
    </div>
  );
}
