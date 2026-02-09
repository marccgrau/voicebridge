"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { InteractionPanel } from "@/components/workspace/InteractionPanel";
import { SuggestionsPanel } from "@/components/workspace/SuggestionsPanel";
import { ProcessStatusPanel } from "@/components/workspace/ProcessStatusPanel";
import { CustomerInfoPanel } from "@/components/workspace/CustomerInfoPanel";
import { IncomingCallNotification } from "@/components/workspace/IncomingCallNotification";
import { useSession } from "@/lib/session";
import { usePendingSessions } from "@/lib/pending-sessions";
import { useRTVI } from "@/lib/rtvi";
import { supabase } from "@/lib/supabase";
import type {
  TranscriptEntry,
  Suggestion,
  ProcessStep,
} from "@voicebridge/contracts";

export default function WorkspacePage() {
  const {
    sessionId,
    isConnected,
    isLoading,
    roomUrl,
    roomToken,
    acceptSession,
    stopSession,
  } = useSession();
  const { pendingSessions } = usePendingSessions();

  // Whether the current session was accepted (customer-initiated) — enable agent audio
  const [audioEnabled, setAudioEnabled] = useState(false);

  const handleAccept = async (pendingSessionId: string) => {
    setAudioEnabled(true);
    await acceptSession(pendingSessionId);
  };

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex h-14 items-center justify-between border-b border-border px-6">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">VoiceBridge</h1>
          <Link
            href={{ pathname: "/admin" }}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Admin
          </Link>
          {sessionId && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              Session: {sessionId.slice(0, 8)}...
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {isConnected && (
            <>
              <span className="flex items-center gap-1.5 text-sm text-success">
                <span className="h-2 w-2 rounded-full bg-success" />
                Connected
              </span>
              <button
                onClick={stopSession}
                className="rounded-md bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
              >
                End Session
              </button>
            </>
          )}
        </div>
      </header>

      {/* Incoming call notifications (only when not connected) */}
      {!isConnected && (
        <IncomingCallNotification
          sessions={pendingSessions}
          onAccept={handleAccept}
          isLoading={isLoading}
        />
      )}

      <WorkspacePanels
        key={sessionId ?? "no-session"}
        sessionId={sessionId}
        isConnected={isConnected}
        roomUrl={roomUrl}
        roomToken={roomToken}
        audioEnabled={audioEnabled}
      />
    </div>
  );
}

function WorkspacePanels({
  sessionId,
  isConnected,
  roomUrl,
  roomToken,
  audioEnabled,
}: {
  sessionId: string | null;
  isConnected: boolean;
  roomUrl: string | null;
  roomToken: string | null;
  audioEnabled: boolean;
}) {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [processKey, setProcessKey] = useState<string | null>(null);
  const [processName, setProcessName] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [steps, setSteps] = useState<ProcessStep[]>([]);
  const [customerId, setCustomerId] = useState<string | null>(null);

  // Fetch customer_id from session
  useEffect(() => {
    let isMounted = true;

    async function fetchCustomerId() {
      if (!sessionId) {
        if (isMounted) {
          setCustomerId(null);
        }
        return;
      }

      try {
        const { data, error } = await supabase
          .from("sessions")
          .select("customer_id")
          .eq("id", sessionId)
          .single();

        if (error) {
          console.error("Failed to fetch customer_id:", error);
          return;
        }

        if (isMounted && data) {
          setCustomerId(data.customer_id ?? null);
        }
      } catch (error) {
        console.error("Error fetching customer_id:", error);
      }
    }

    fetchCustomerId();

    return () => {
      isMounted = false;
    };
  }, [sessionId]);

  // Subscribe to RTVI messages via WebRTC data channel (transcripts, suggestions, process)
  useRTVI(
    roomUrl,
    roomToken,
    {
      onTranscript: (message) => {
        setTranscript((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(), // Generate client-side ID for RTVI messages
            speaker: message.data.speaker,
            text: message.data.text,
            timestamp: message.data.timestamp,
            isFinal: message.data.isFinal,
          },
        ]);
      },
      onSuggestion: (message) => {
        setSuggestions(
          message.data.suggestions.map((s: Suggestion, _i: number) => ({
            ...s,
            id: s.id ?? crypto.randomUUID(),
          }))
        );
      },
      onProcessIllustration: (message) => {
        const processSteps = message.data.steps.map((step: ProcessStep) => ({
          key: step.key,
          label: step.label,
          status: step.status,
        }));

        setProcessKey(message.data.processKey);
        setProcessName(message.data.processName);
        setSteps(processSteps);
        // Convert step index to step key
        setCurrentStep(
          message.data.currentStep >= 0 &&
            message.data.currentStep < processSteps.length
            ? (processSteps[message.data.currentStep]?.key ?? null)
            : null
        );
      },
    },
    { audioEnabled }
  );

  return (
    <main className="grid flex-1 grid-cols-2 grid-rows-2 gap-4 p-4">
      {/* Top Left - Interaction Panel */}
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <InteractionPanel transcript={transcript} isConnected={isConnected} />
      </div>

      {/* Top Right - Suggestions Panel */}
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <SuggestionsPanel
          suggestions={suggestions}
          isConnected={isConnected}
          sessionId={sessionId}
        />
      </div>

      {/* Bottom Left - Process Status Panel */}
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <ProcessStatusPanel
          processKey={processKey}
          processName={processName}
          currentStep={currentStep}
          steps={steps}
          slots={{}}
        />
      </div>

      {/* Bottom Right - Customer Info Panel */}
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <CustomerInfoPanel customerId={customerId} isConnected={isConnected} />
      </div>
    </main>
  );
}
