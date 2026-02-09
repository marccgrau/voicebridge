"use client";

import type { PendingSession } from "@/lib/pending-sessions";

interface IncomingCallNotificationProps {
  sessions: PendingSession[];
  onAccept: (sessionId: string) => void;
  isLoading: boolean;
}

export function IncomingCallNotification({
  sessions,
  onAccept,
  isLoading,
}: IncomingCallNotificationProps) {
  if (sessions.length === 0) return null;

  return (
    <div className="mx-6 mt-4 space-y-3">
      {sessions.map((session) => {
        const domain = (session.state?.domain as string) ?? "General";
        const locale = (session.state?.locale as string) ?? "en";
        const waitingSince = session.customer_joined_at
          ? new Date(session.customer_joined_at)
          : new Date(session.created_at);

        return (
          <div
            key={session.id}
            className="flex items-center justify-between rounded-2xl border-2 border-accent/30 bg-accent/5 px-5 py-4 shadow-accent"
          >
            <div className="flex items-center gap-3">
              <span className="h-3 w-3 animate-pulse-dot rounded-full gradient-accent" />
              <div>
                <p className="text-sm font-medium">
                  Incoming call
                  {domain !== "General" && (
                    <span className="font-mono-ui ml-2 rounded-lg bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {domain}
                    </span>
                  )}
                </p>
                <p className="font-mono-ui text-xs text-muted-foreground">
                  Locale: {locale} &middot; Waiting since{" "}
                  {waitingSince.toLocaleTimeString()}
                </p>
              </div>
            </div>
            <button
              onClick={() => onAccept(session.id)}
              disabled={isLoading}
              className="gradient-accent rounded-xl px-5 py-2 text-sm font-medium text-white hover:-translate-y-0.5 hover:shadow-accent-lg disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-none transition-all"
            >
              {isLoading ? "Accepting..." : "Accept"}
            </button>
          </div>
        );
      })}
    </div>
  );
}
