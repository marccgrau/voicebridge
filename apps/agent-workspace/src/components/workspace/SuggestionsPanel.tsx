"use client";

import type { AdviceItem } from "@voicebridge/contracts";
import type { PanelVariant } from "@/lib/use-phase";

interface SuggestionsPanelProps {
  advice: AdviceItem[];
  isConnected: boolean;
  sessionId: string | null;
  variant?: PanelVariant;
  onToggle?: () => void;
}

export function SuggestionsPanel({
  advice,
  isConnected,
  variant = "expanded",
  onToggle,
}: SuggestionsPanelProps) {
  if (variant === "compact") {
    return (
      <button
        onClick={onToggle}
        className="panel-morph flex w-full items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3 text-left shadow-card hover:shadow-card-hover transition-shadow"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        <span className="text-sm font-medium text-muted-foreground">
          Process-Pilot
        </span>
        {advice.length > 0 && (
          <span className="rounded-lg bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
            {advice.length}
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
        className="flex items-center justify-between border-b border-border px-5 py-4 text-left disabled:cursor-default"
      >
        <span className="font-mono-ui flex items-center gap-2 text-sm uppercase tracking-wide text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Process-Pilot
        </span>
      </button>

      {/* Advice content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {advice.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">
              {isConnected
                ? "Hinweise erscheinen basierend auf dem Gespräch"
                : "Sitzung starten, um Hinweise zu erhalten"}
            </p>
          </div>
        ) : (
          <div className="rounded-xl border border-border/60 bg-accent/5 border-l-4 border-l-accent p-4 shadow-card">
            <ul className="space-y-2">
              {advice.map((item) => (
                <li
                  key={item.id}
                  className="text-sm leading-relaxed text-foreground flex items-start gap-2"
                >
                  <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-accent" />
                  {item.text}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
