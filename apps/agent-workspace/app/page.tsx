"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { InteractionPanel } from "@/components/workspace/InteractionPanel";
import { SuggestionsPanel } from "@/components/workspace/SuggestionsPanel";
import { ProcessLayer } from "@/components/workspace/ProcessLayer";
import { CustomerInfoPanel } from "@/components/workspace/CustomerInfoPanel";
import { IncomingCallNotification } from "@/components/workspace/IncomingCallNotification";
import { SummaryEditor } from "@/components/workspace/SummaryEditor";
import { useSession } from "@/lib/session";
import { usePendingSessions } from "@/lib/pending-sessions";
import { useRTVI } from "@/lib/rtvi";
import { usePhase } from "@/lib/use-phase";
import { useSummary } from "@/lib/use-summary";
import { supabase } from "@/lib/supabase";
import type {
  TranscriptEntry,
  Suggestion,
  ProcessStep,
} from "@voicebridge/contracts";

export default function WorkspacePage() {
  const isAgentMicEnabledByEnv =
    (process.env.NEXT_PUBLIC_AGENT_MIC_ENABLED ?? "true").toLowerCase() !==
    "false";

  const {
    sessionId,
    isConnected,
    isLoading,
    roomUrl,
    roomToken,
    acceptSession,
    stopSession,
    clearSession,
  } = useSession();
  const { pendingSessions } = usePendingSessions();

  // Whether the current session was accepted (customer-initiated) — enable agent audio
  const [audioEnabled, setAudioEnabled] = useState(false);

  const handleAccept = async (pendingSessionId: string) => {
    setAudioEnabled(isAgentMicEnabledByEnv);
    try {
      await acceptSession(pendingSessionId);
    } catch (err) {
      // 409 conflict = already accepted by another agent, handled by pending-sessions realtime
      if (err instanceof Error && err.message.includes("not pending")) {
        // Session was already accepted — pending list auto-updates via Realtime
        return;
      }
      throw err;
    }
  };

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex h-16 items-center justify-between bg-card px-6 shadow-sm">
        <div className="flex items-center gap-4">
          <h1 className="font-display text-xl gradient-text">VoiceBridge</h1>
          <Link
            href={{ pathname: "/admin" }}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Admin
          </Link>
          {sessionId && (
            <span className="font-mono-ui flex items-center gap-1.5 rounded-xl bg-accent/10 px-3 py-1 text-xs text-accent">
              <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse-dot" />
              {sessionId.slice(0, 8)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {isConnected && (
            <>
              <span className="flex items-center gap-2 text-sm text-success">
                <span className="h-2 w-2 rounded-full gradient-accent" />
                Connected
              </span>
              <button
                onClick={stopSession}
                className="rounded-xl border border-destructive px-4 py-1.5 text-sm font-medium text-destructive hover:bg-destructive hover:text-destructive-foreground transition-all hover:-translate-y-0.5"
              >
                End Session
              </button>
            </>
          )}
        </div>
      </header>

      <WorkspacePanels
        key={sessionId ?? "no-session"}
        sessionId={sessionId}
        isConnected={isConnected}
        isLoading={isLoading}
        roomUrl={roomUrl}
        roomToken={roomToken}
        audioEnabled={audioEnabled}
        pendingSessions={pendingSessions}
        onAccept={handleAccept}
        onClearSession={clearSession}
      />
    </div>
  );
}

function WorkspacePanels({
  sessionId,
  isConnected,
  isLoading,
  roomUrl,
  roomToken,
  audioEnabled,
  pendingSessions,
  onAccept,
  onClearSession,
}: {
  sessionId: string | null;
  isConnected: boolean;
  isLoading: boolean;
  roomUrl: string | null;
  roomToken: string | null;
  audioEnabled: boolean;
  pendingSessions: {
    id: string;
    status: string;
    room_url: string;
    room_name: string;
    created_at: string;
    customer_joined_at: string | null;
    customer_id: string | null;
    state: Record<string, unknown>;
  }[];
  onAccept: (sessionId: string) => void;
  onClearSession: () => void;
}) {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [processKey, setProcessKey] = useState<string | null>(null);
  const [processName, setProcessName] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [steps, setSteps] = useState<ProcessStep[]>([]);
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<string | null>(null);

  const { phase, density, toggleDensity } = usePhase({
    sessionId,
    isConnected,
    processKey,
    pendingSessions,
    sessionStatus,
  });

  const {
    summaryText,
    setSummaryText,
    isGenerating,
    isSaving,
    isSaved,
    error: summaryError,
    saveSummary,
  } = useSummary(sessionId, {
    autoGenerate: phase === "postcall_summary",
    onSaveComplete: onClearSession, // Automatically return to idle after saving
  });

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

  // Subscribe to session status changes via Supabase Realtime
  useEffect(() => {
    if (!sessionId) return;

    const channel = supabase
      .channel(`session-status-${sessionId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "sessions",
          filter: `id=eq.${sessionId}`,
        },
        (payload) => {
          const updated = payload.new as { status: string };
          setSessionStatus(updated.status);
        }
      )
      .subscribe();

    return () => {
      channel.unsubscribe();
    };
  }, [sessionId]);

  // Subscribe to RTVI messages via WebRTC data channel
  useRTVI(
    roomUrl,
    roomToken,
    {
      onTranscript: (message) => {
        setTranscript((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
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

  // Select oldest pending session for incoming phase
  const selectedPendingSession = pendingSessions[pendingSessions.length - 1]; // oldest (sorted desc by created_at)

  // --- Phase-based layouts ---

  if (phase === "idle") {
    return (
      <main className="flex flex-1 items-center justify-center bg-background p-5">
        <div className="text-center">
          <p className="text-lg text-muted-foreground">
            Waiting for incoming calls...
          </p>
          <p className="mt-2 text-sm text-muted-foreground/60">
            Calls will appear here when customers connect
          </p>
        </div>
      </main>
    );
  }

  if (phase === "incoming") {
    return (
      <main className="flex flex-1 flex-col bg-background">
        {/* Incoming call notification for selected session */}
        <IncomingCallNotification
          sessions={pendingSessions}
          onAccept={onAccept}
          isLoading={isLoading}
        />

        {/* Process layer - waiting state */}
        <ProcessLayer
          processKey={processKey}
          processName={processName}
          currentStep={currentStep}
          steps={steps}
          phase={phase}
        />

        {/* Customer info - full width expanded */}
        <div className="flex-1 overflow-hidden p-5">
          <div className="h-full overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm">
            <CustomerInfoPanel
              customerId={selectedPendingSession?.customer_id ?? null}
              isConnected={false}
            />
          </div>
        </div>
      </main>
    );
  }

  if (phase === "postcall_summary") {
    return (
      <main className="flex flex-1 flex-col bg-background">
        {/* Process layer - final state */}
        <ProcessLayer
          processKey={processKey}
          processName={processName}
          currentStep={currentStep}
          steps={steps}
          phase={phase}
        />

        {/* Two-column: transcript left, summary editor right */}
        <div className="flex-1 grid grid-cols-[1fr_1fr] gap-5 p-5 overflow-hidden">
          {/* Left column: Customer info (compact) + Transcript (expanded) */}
          <div className="flex flex-col gap-3 overflow-hidden min-h-0">
            <CustomerInfoPanel
              customerId={customerId}
              isConnected={false}
              variant="compact"
              onToggle={() => toggleDensity("customer")}
            />
            <div className="flex-1 overflow-hidden rounded-2xl border border-border/60 bg-card flex flex-col shadow-sm">
              <InteractionPanel
                transcript={transcript}
                isConnected={false}
                variant="expanded"
                onToggle={() => toggleDensity("transcript")}
              />
            </div>
          </div>

          {/* Right column: Summary editor + Back to queue */}
          <div className="flex flex-col gap-3 overflow-hidden min-h-0">
            <SummaryEditor
              summaryText={summaryText}
              onSummaryChange={setSummaryText}
              onSave={() => sessionId && saveSummary(sessionId)}
              isGenerating={isGenerating}
              isSaving={isSaving}
              isSaved={isSaved}
              error={summaryError}
            />
            <button
              onClick={onClearSession}
              className="rounded-xl border border-border/60 bg-card px-4 py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground hover:border-accent/30 transition-all"
            >
              Back to Queue
            </button>
          </div>
        </div>
      </main>
    );
  }

  // active_preprocess / active_inprocess
  return (
    <main className="flex flex-1 flex-col bg-background overflow-hidden">
      {/* Process layer */}
      <ProcessLayer
        processKey={processKey}
        processName={processName}
        currentStep={currentStep}
        steps={steps}
        phase={phase}
      />

      {/* Two-column grid */}
      <div className="flex-1 grid grid-cols-[1.1fr_0.9fr] gap-5 p-5 overflow-hidden">
        {/* Left column */}
        <div className="flex flex-col gap-3 overflow-hidden min-h-0">
          <CustomerInfoPanel
            customerId={customerId}
            isConnected={isConnected}
            variant={density.customer}
            onToggle={() => toggleDensity("customer")}
          />
          <div className="flex-1 overflow-hidden rounded-2xl border border-border/60 bg-card flex flex-col shadow-sm hover:shadow-md transition-shadow min-h-0">
            <InteractionPanel
              transcript={transcript}
              isConnected={isConnected}
              variant={density.transcript}
              onToggle={() => toggleDensity("transcript")}
            />
          </div>
        </div>

        {/* Right column */}
        <div className="overflow-hidden rounded-2xl border border-border/60 bg-card flex flex-col shadow-sm hover:shadow-md transition-shadow min-h-0">
          <SuggestionsPanel
            suggestions={suggestions}
            isConnected={isConnected}
            sessionId={sessionId}
            variant={density.suggestions}
            onToggle={() => toggleDensity("suggestions")}
          />
        </div>
      </div>
    </main>
  );
}
