"use client";

import { useState, useEffect, useCallback } from "react";
import { supabase } from "@/lib/supabase";

interface SessionListProps {
  onSelectSession: (sessionId: string) => void;
  selectedSessionId: string | null;
}

interface SessionWithCustomer {
  id: string;
  status: string;
  process_key: string | null;
  created_at: string;
  updated_at: string;
  customer_name?: string | null;
}

export function SessionList({
  onSelectSession,
  selectedSessionId,
}: SessionListProps) {
  const [sessions, setSessions] = useState<SessionWithCustomer[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [hasLoadedInitial, setHasLoadedInitial] = useState(false);

  const LIMIT = 20;

  const loadSessions = useCallback(async () => {
    setIsLoading(true);
    try {
      // Fetch sessions with customer name via join
      const { data, error } = await supabase
        .from("sessions")
        .select(
          `
          *,
          customers (
            name
          )
        `
        )
        .order("created_at", { ascending: false })
        .range(offset, offset + LIMIT - 1);

      if (error) {
        console.error("Failed to fetch sessions:", error);
        return;
      }

      if (data) {
        // Map the joined data
        const sessionsWithCustomer = data.map((row) => ({
          ...row,
          customer_name:
            (row.customers as { name?: string } | null)?.name ?? null,
        }));

        // Filter out any duplicates based on session ID
        setSessions((prev) => {
          const existingIds = new Set(prev.map((s) => s.id));
          const newSessions = sessionsWithCustomer.filter(
            (s) => !existingIds.has(s.id)
          );
          return [...prev, ...newSessions];
        });
        setHasMore(data.length === LIMIT);
        setOffset((prev) => prev + LIMIT);
      }
    } catch (error) {
      console.error("Error loading sessions:", error);
    } finally {
      setIsLoading(false);
    }
  }, [offset, LIMIT]);

  useEffect(() => {
    if (!hasLoadedInitial) {
      setHasLoadedInitial(true);
      loadSessions();
    }
  }, [hasLoadedInitial, loadSessions]);

  const statusStyles = {
    pending: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    active: "bg-success/10 text-success",
    completed: "bg-muted text-muted-foreground",
    abandoned: "bg-warning/10 text-warning",
    escalated: "bg-destructive/10 text-destructive",
    error: "bg-destructive/10 text-destructive",
  };

  return (
    <div className="flex h-full flex-col border-r border-border">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="font-semibold">Sessions</h2>
        <span className="text-xs text-muted-foreground">
          {sessions.length} loaded
        </span>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && sessions.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">Loading...</p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">No sessions found</p>
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={`w-full rounded-lg border p-3 text-left transition-colors hover:bg-muted/50 ${
                  selectedSessionId === session.id
                    ? "border-primary bg-primary/5"
                    : "border-border"
                }`}
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-mono text-xs text-muted-foreground">
                    {session.id.slice(0, 8)}...
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      statusStyles[
                        session.status as keyof typeof statusStyles
                      ] ?? statusStyles.completed
                    }`}
                  >
                    {session.status}
                  </span>
                </div>

                {session.customer_name && (
                  <p className="mb-1 text-sm font-medium">
                    {session.customer_name}
                  </p>
                )}

                {session.process_key && (
                  <p className="mb-1 text-sm text-foreground">
                    {formatProcessKey(session.process_key)}
                  </p>
                )}

                <p className="text-xs text-muted-foreground">
                  {formatDateTime(session.created_at)}
                  {session.updated_at !== session.created_at && (
                    <span className="ml-2">
                      •{" "}
                      {calculateDuration(
                        session.created_at,
                        session.updated_at
                      )}
                    </span>
                  )}
                </p>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Load More */}
      {hasMore && !isLoading && (
        <div className="border-t border-border p-3">
          <button
            onClick={loadSessions}
            className="w-full rounded-md bg-muted px-3 py-2 text-sm font-medium hover:bg-muted/80"
          >
            Load More
          </button>
        </div>
      )}

      {isLoading && sessions.length > 0 && (
        <div className="border-t border-border p-3 text-center">
          <p className="text-xs text-muted-foreground">Loading...</p>
        </div>
      )}
    </div>
  );
}

function formatProcessKey(key: string): string {
  return key
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatDateTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function calculateDuration(start: string, end: string): string {
  const startDate = new Date(start);
  const endDate = new Date(end);
  const durationMs = endDate.getTime() - startDate.getTime();
  const durationMin = Math.floor(durationMs / 1000 / 60);

  if (durationMin < 1) return "<1m";
  if (durationMin < 60) return `${durationMin}m`;

  const hours = Math.floor(durationMin / 60);
  const minutes = durationMin % 60;
  return `${hours}h ${minutes}m`;
}
