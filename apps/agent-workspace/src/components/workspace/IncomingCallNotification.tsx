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
            className="flex items-center justify-between rounded-lg border border-primary/30 bg-primary/5 px-4 py-3"
          >
            <div className="flex items-center gap-3">
              <span className="h-3 w-3 animate-pulse rounded-full bg-primary" />
              <div>
                <p className="text-sm font-medium">
                  Incoming call
                  {domain !== "General" && (
                    <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                      {domain}
                    </span>
                  )}
                </p>
                <p className="text-xs text-muted-foreground">
                  Locale: {locale} &middot; Waiting since{" "}
                  {waitingSince.toLocaleTimeString()}
                </p>
              </div>
            </div>
            <button
              onClick={() => onAccept(session.id)}
              disabled={isLoading}
              className="rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {isLoading ? "Accepting..." : "Accept"}
            </button>
          </div>
        );
      })}
    </div>
  );
}
