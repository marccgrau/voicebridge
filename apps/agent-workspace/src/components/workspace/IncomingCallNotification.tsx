"use client";

import type { PendingSession } from "@/lib/pending-sessions";

interface IncomingCallNotificationProps {
  sessions: PendingSession[];
  selectedSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onAccept: (sessionId: string) => void;
  isLoading: boolean;
}

export function IncomingCallNotification({
  sessions,
  selectedSessionId,
  onSelectSession,
  onAccept,
  isLoading,
}: IncomingCallNotificationProps) {
  if (sessions.length === 0) return null;

  return (
    <div className="mx-6 mt-4 space-y-3">
      {sessions.map((session) => {
        const domain = (session.state?.domain as string) ?? "General";
        const locale = (session.state?.locale as string) ?? "de";
        const waitingSince = session.customer_joined_at
          ? new Date(session.customer_joined_at)
          : new Date(session.created_at);
        const isSelected = selectedSessionId === session.id;

        return (
          <div
            key={session.id}
            role="button"
            tabIndex={0}
            aria-pressed={isSelected}
            onClick={() => onSelectSession(session.id)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectSession(session.id);
              }
            }}
            className={`flex cursor-pointer items-center justify-between rounded-2xl border-2 px-5 py-4 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/35 ${
              isSelected
                ? "border-accent/45 bg-accent/10 shadow-accent"
                : "border-border/70 bg-card hover:border-accent/30 hover:bg-accent/5"
            }`}
          >
            <div className="flex items-center gap-3">
              <span
                className={`h-3 w-3 rounded-full ${
                  isSelected
                    ? "animate-pulse-dot gradient-accent"
                    : "bg-accent/40"
                }`}
              />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Eingehender Anruf
                  {domain !== "General" && (
                    <span className="font-mono-ui ml-2 rounded-lg bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {domain}
                    </span>
                  )}
                  {isSelected && (
                    <span className="ml-2 rounded-lg bg-accent/15 px-2 py-0.5 text-xs text-accent">
                      Kundenvorschau
                    </span>
                  )}
                </p>
                <p className="font-mono-ui text-xs text-muted-foreground">
                  Sprache: {locale} &middot; Wartet seit{" "}
                  {waitingSince.toLocaleTimeString()}
                </p>
              </div>
            </div>
            <button
              onClick={(event) => {
                event.stopPropagation();
                onAccept(session.id);
              }}
              disabled={isLoading}
              className="gradient-accent rounded-xl px-5 py-2 text-sm font-medium text-white hover:-translate-y-0.5 hover:shadow-accent-lg disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-none transition-all"
            >
              {isLoading ? "Wird angenommen..." : "Annehmen"}
            </button>
          </div>
        );
      })}
    </div>
  );
}
