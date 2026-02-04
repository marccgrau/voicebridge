"use client";

import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";

interface HistoryPanelProps {
  sessionId: string | null;
}

interface SessionSummary {
  id: string;
  process_key: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export function HistoryPanel({ sessionId }: HistoryPanelProps) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch recent sessions
  useEffect(() => {
    const fetchSessions = async () => {
      setIsLoading(true);
      try {
        const { data, error } = await supabase
          .from("sessions")
          .select("id, process_key, status, created_at, updated_at")
          .order("created_at", { ascending: false })
          .limit(10);

        if (error) throw error;
        setSessions(data ?? []);
      } catch (error) {
        console.error("Failed to fetch sessions:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchSessions();
  }, [sessionId]); // Refetch when session changes

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="font-semibold">Recent Sessions</h2>
        <span className="text-xs text-muted-foreground">
          {sessions.length} sessions
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">Loading...</p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">
              No previous sessions
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {sessions.map((session) => (
              <SessionCard
                key={session.id}
                session={session}
                isActive={session.id === sessionId}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface SessionCardProps {
  session: SessionSummary;
  isActive: boolean;
}

function SessionCard({ session, isActive }: SessionCardProps) {
  const statusStyles = {
    active: "bg-success/10 text-success",
    completed: "bg-muted text-muted-foreground",
    abandoned: "bg-warning/10 text-warning",
    escalated: "bg-destructive/10 text-destructive",
  };

  return (
    <div
      className={`rounded-lg border p-3 ${
        isActive ? "border-primary bg-primary/5" : "border-border"
      }`}
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-xs text-muted-foreground">
          {session.id.slice(0, 8)}...
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            statusStyles[session.status as keyof typeof statusStyles] ??
            statusStyles.completed
          }`}
        >
          {session.status}
        </span>
      </div>

      {session.process_key && (
        <p className="mb-1 text-sm font-medium">{formatProcessKey(session.process_key)}</p>
      )}

      <p className="text-xs text-muted-foreground">
        {formatDateTime(session.created_at)}
      </p>
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
