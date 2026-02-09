"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";
import type { Customer, TranscriptEntry } from "@voicebridge/contracts";

interface SessionDetailProps {
  sessionId: string | null;
}

interface SessionWithCustomer {
  id: string;
  status: string;
  process_key: string | null;
  state: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  room_url: string | null;
  customer?: Customer | null;
}

export function SessionDetail({ sessionId }: SessionDetailProps) {
  const [session, setSession] = useState<SessionWithCustomer | null>(null);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setSession(null);
      setTranscript([]);
      return;
    }

    let isMounted = true;

    async function fetchSessionDetails() {
      setIsLoading(true);
      try {
        // Fetch session with customer info
        const { data: sessionData, error: sessionError } = await supabase
          .from("sessions")
          .select("*, customers (*)")
          .eq("id", sessionId)
          .single();

        if (sessionError) {
          console.error("Failed to fetch session:", sessionError);
          return;
        }

        if (!isMounted) return;

        if (sessionData) {
          const sessionWithCustomer: SessionWithCustomer = {
            id: sessionData.id,
            status: sessionData.status,
            process_key: sessionData.process_key,
            state: sessionData.state,
            created_at: sessionData.created_at,
            updated_at: sessionData.updated_at,
            room_url: sessionData.room_url,
            customer: sessionData.customers
              ? {
                  id: sessionData.customers.id,
                  name: sessionData.customers.name,
                  gender: sessionData.customers.gender,
                  email: sessionData.customers.email,
                  phone: sessionData.customers.phone,
                  customerSince: sessionData.customers.customer_since,
                  classification: sessionData.customers.classification,
                  products: sessionData.customers.products,
                  preferredLanguage: sessionData.customers.preferred_language,
                  notes: sessionData.customers.notes,
                }
              : null,
          };
          setSession(sessionWithCustomer);
        }

        // Fetch transcript
        const { data: transcriptData, error: transcriptError } = await supabase
          .from("transcript_segments")
          .select("*")
          .eq("session_id", sessionId)
          .order("ts", { ascending: true });

        if (transcriptError) {
          console.error("Failed to fetch transcript:", transcriptError);
          // Don't return here - still show session details even if transcript fails
          setTranscript([]);
        } else if (transcriptData && isMounted) {
          setTranscript(
            transcriptData.map((row) => ({
              id: row.id,
              speaker: row.speaker as "agent" | "customer",
              text: row.text,
              timestamp: row.ts,
              isFinal: row.is_final,
            }))
          );
        }
      } catch (error) {
        console.error("Error fetching session details:", error);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    fetchSessionDetails();

    return () => {
      isMounted = false;
    };
  }, [sessionId]);

  if (!sessionId) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">
          Select a session to view details
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Session not found</p>
      </div>
    );
  }

  const statusStyles = {
    pending: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    active: "bg-success/10 text-success",
    completed: "bg-muted text-muted-foreground",
    abandoned: "bg-warning/10 text-warning",
    escalated: "bg-destructive/10 text-destructive",
    error: "bg-destructive/10 text-destructive",
  };

  const state = session.state as Record<string, unknown>;
  const steps =
    (state?.steps as { key: string; label: string; status: string }[]) ?? [];

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border px-6 py-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Session Details</h2>
          <span
            className={`rounded-full px-3 py-1 text-sm font-medium ${
              statusStyles[session.status as keyof typeof statusStyles] ??
              statusStyles.completed
            }`}
          >
            {session.status}
          </span>
        </div>
        <p className="font-mono text-sm text-muted-foreground">{session.id}</p>
      </div>

      {/* Content */}
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {/* Session Info */}
        <div className="space-y-3">
          <h3 className="font-semibold">Session Information</h3>
          <div className="space-y-2 text-sm">
            <InfoRow
              label="Created"
              value={formatDateTime(session.created_at)}
            />
            <InfoRow
              label="Updated"
              value={formatDateTime(session.updated_at)}
            />
            <InfoRow
              label="Duration"
              value={calculateDuration(session.created_at, session.updated_at)}
            />
            {session.process_key && (
              <InfoRow
                label="Process"
                value={formatProcessKey(session.process_key)}
              />
            )}
            {session.room_url && (
              <InfoRow label="Room URL" value={session.room_url} mono />
            )}
          </div>
        </div>

        {/* Customer Info */}
        {session.customer && (
          <div className="space-y-3">
            <h3 className="font-semibold">Customer</h3>
            <div className="space-y-2 text-sm">
              <InfoRow label="Name" value={session.customer.name} />
              <InfoRow
                label="Classification"
                value={session.customer.classification.toUpperCase()}
              />
              {session.customer.email && (
                <InfoRow label="Email" value={session.customer.email} />
              )}
              {session.customer.phone && (
                <InfoRow label="Phone" value={session.customer.phone} />
              )}
            </div>
          </div>
        )}

        {/* Process Steps */}
        {steps.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-semibold">Process Steps</h3>
            <div className="space-y-2">
              {steps.map((step, idx) => (
                <div key={step.key} className="flex items-center gap-3 text-sm">
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
                      step.status === "completed"
                        ? "bg-success/10 text-success"
                        : step.status === "active"
                          ? "bg-primary/10 text-primary"
                          : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {idx + 1}
                  </span>
                  <span className="flex-1">{step.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {step.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Transcript */}
        {transcript.length > 0 && (
          <div className="space-y-3">
            <h3 className="font-semibold">Transcript</h3>
            <div className="space-y-3">
              {transcript.map((entry) => (
                <div
                  key={entry.id}
                  className={`rounded-lg border p-3 ${
                    entry.speaker === "agent"
                      ? "border-primary/20 bg-primary/5"
                      : "border-border"
                  }`}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-xs font-medium capitalize text-foreground">
                      {entry.speaker}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatTime(entry.timestamp)}
                    </span>
                  </div>
                  <p className="text-sm text-foreground">{entry.text}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}:</span>
      <span className={`font-medium ${mono ? "font-mono" : ""}`}>{value}</span>
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
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function calculateDuration(start: string, end: string): string {
  const startDate = new Date(start);
  const endDate = new Date(end);
  const durationMs = endDate.getTime() - startDate.getTime();
  const durationMin = Math.floor(durationMs / 1000 / 60);

  if (durationMin < 1) return "< 1 minute";
  if (durationMin < 60) return `${durationMin} minutes`;

  const hours = Math.floor(durationMin / 60);
  const minutes = durationMin % 60;
  return `${hours} hours ${minutes} minutes`;
}
