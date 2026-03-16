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
  AdviceItem,
  ProcessStep,
} from "@voicebridge/contracts";

type RoutingSource = "direct" | "voice_ai";

type SessionRoutingContext = {
  source: RoutingSource;
  handoffSummary: string | null;
  transferReason: string | null;
};

const DEFAULT_ROUTING_CONTEXT: SessionRoutingContext = {
  source: "direct",
  handoffSummary: null,
  transferReason: null,
};

function normalizeText(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function readCustomerIdFromState(state: unknown): string | null {
  if (!state || typeof state !== "object") {
    return null;
  }

  const record = state as Record<string, unknown>;
  const customerIdFromState = record.customer_id ?? record.customerId;

  if (
    typeof customerIdFromState === "string" &&
    customerIdFromState.trim().length > 0
  ) {
    return customerIdFromState;
  }

  return null;
}

function readRoutingContextFromState(state: unknown): SessionRoutingContext {
  if (!state || typeof state !== "object") {
    return DEFAULT_ROUTING_CONTEXT;
  }

  const record = state as Record<string, unknown>;
  const routingRecord =
    record.routing && typeof record.routing === "object"
      ? (record.routing as Record<string, unknown>)
      : null;

  const sourceValue =
    routingRecord?.source ??
    record.routing_source ??
    record.routingSource ??
    record.source;

  const handoffSummary =
    normalizeText(routingRecord?.handoff_summary) ??
    normalizeText(routingRecord?.handoffSummary) ??
    normalizeText(record.handoff_summary) ??
    normalizeText(record.handoffSummary);

  const transferReason =
    normalizeText(routingRecord?.transfer_reason) ??
    normalizeText(routingRecord?.transferReason) ??
    normalizeText(record.transfer_reason) ??
    normalizeText(record.transferReason);

  let source: RoutingSource;
  if (sourceValue === "voice_ai") {
    source = "voice_ai";
  } else if (sourceValue === "direct") {
    source = "direct";
  } else {
    source = handoffSummary || transferReason ? "voice_ai" : "direct";
  }

  return {
    source,
    handoffSummary,
    transferReason,
  };
}

function getSessionCustomerId(session: {
  customer_id: string | null;
  state: Record<string, unknown>;
}): string | null {
  if (session.customer_id) {
    return session.customer_id;
  }

  return readCustomerIdFromState(session.state);
}

export default function WorkspacePageClient() {
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
    disconnectRoom,
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
      // Network errors and other failures are already surfaced via useSession().error
      console.error("Failed to accept session:", err);
    }
  };

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex h-16 items-center justify-between border-b border-border bg-white px-6">
        <div className="flex items-center gap-4">
          <h1 className="font-display text-xl font-semibold gradient-text">
            VoiceBridge
          </h1>
          <Link
            href={{ pathname: "/admin" }}
            className="text-sm text-muted-foreground/70 hover:text-foreground transition-colors"
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
              <span className="flex items-center gap-2 text-sm text-accent font-medium">
                <span className="h-2 w-2 rounded-full gradient-accent animate-pulse-dot" />
                Verbunden
              </span>
              <button
                onClick={stopSession}
                className="rounded-xl border border-destructive/60 px-4 py-1.5 text-sm font-medium text-destructive hover:bg-destructive hover:text-destructive-foreground hover:border-destructive transition-all hover:-translate-y-0.5"
              >
                Sitzung beenden
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
        onDisconnectRoom={disconnectRoom}
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
  onDisconnectRoom,
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
  onDisconnectRoom: () => void;
}) {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [advice, setAdvice] = useState<AdviceItem[]>([]);
  const [processKey, setProcessKey] = useState<string | null>(null);
  const [processName, setProcessName] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [steps, setSteps] = useState<ProcessStep[]>([]);
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [sessionRoutingContext, setSessionRoutingContext] =
    useState<SessionRoutingContext>(DEFAULT_ROUTING_CONTEXT);
  const [sessionStatus, setSessionStatus] = useState<string | null>(null);
  const [incomingSelectionId, setIncomingSelectionId] = useState<string | null>(
    null
  );

  const persistSessionEvent = (
    eventType: string,
    payload: Record<string, unknown>
  ) => {
    if (!sessionId) {
      return;
    }

    void supabase
      .from("session_events")
      .insert({
        session_id: sessionId,
        event_type: eventType,
        source: "agent_workspace",
        payload,
      })
      .then(({ error }) => {
        if (error) {
          console.error("Failed to persist session event:", error);
        }
      });
  };

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
          setSessionRoutingContext(DEFAULT_ROUTING_CONTEXT);
        }
        return;
      }

      try {
        const { data, error } = await supabase
          .from("sessions")
          .select("customer_id, state")
          .eq("id", sessionId)
          .single();

        if (error) {
          console.error("Failed to fetch customer_id:", error);
          return;
        }

        if (isMounted && data) {
          const resolvedCustomerId =
            (typeof data.customer_id === "string" &&
            data.customer_id.trim().length > 0
              ? data.customer_id
              : null) ?? readCustomerIdFromState(data.state);
          const resolvedRoutingContext = readRoutingContextFromState(
            data.state
          );

          setCustomerId(resolvedCustomerId);
          setSessionRoutingContext(resolvedRoutingContext);
        }
      } catch (error) {
        console.error("Error fetching customer_id:", error);
        if (isMounted) {
          setSessionRoutingContext(DEFAULT_ROUTING_CONTEXT);
        }
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

  // Disconnect room when session reaches a terminal status (e.g. customer ended call)
  useEffect(() => {
    const terminalStatuses = ["completed", "abandoned", "escalated", "error"];
    if (sessionStatus && terminalStatuses.includes(sessionStatus)) {
      onDisconnectRoom();
    }
  }, [sessionStatus, onDisconnectRoom]);

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

        if (sessionId && message.data.isFinal) {
          void supabase
            .from("transcript_segments")
            .insert({
              session_id: sessionId,
              speaker: message.data.speaker,
              text: message.data.text,
              is_final: message.data.isFinal,
              ts: message.data.timestamp,
            })
            .then(({ error }) => {
              if (error) {
                console.error("Failed to persist transcript segment:", error);
              }
            });
        }
      },
      onSuggestion: (message) => {
        setAdvice(
          message.data.advice.map((a) => ({
            ...a,
            id: a.id ?? crypto.randomUUID(),
          }))
        );

        persistSessionEvent("agent_guidance_received", {
          advice: message.data.advice,
          serviceType: message.data.serviceType,
        });
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

        persistSessionEvent("process_illustration_received", {
          processKey: message.data.processKey,
          processName: message.data.processName,
          currentStep: message.data.currentStep,
          steps: message.data.steps,
        });
      },
    },
    { audioEnabled }
  );

  const selectedPendingSession =
    (incomingSelectionId
      ? pendingSessions.find((session) => session.id === incomingSelectionId)
      : undefined) ?? pendingSessions[pendingSessions.length - 1];
  const selectedIncomingRoutingContext = selectedPendingSession
    ? readRoutingContextFromState(selectedPendingSession.state)
    : DEFAULT_ROUTING_CONTEXT;

  // --- Phase-based layouts ---

  if (phase === "idle") {
    return (
      <main className="flex flex-1 items-center justify-center bg-background p-5">
        <div className="text-center">
          <p className="font-display text-xl font-semibold text-muted-foreground">
            Warten auf eingehende Anrufe...
          </p>
          <p className="mt-3 text-sm text-muted-foreground/50">
            Anrufe erscheinen hier, wenn Kunden sich verbinden
          </p>
          <div className="mx-auto mt-6 h-px w-16 bg-accent/20" />
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
          selectedSessionId={selectedPendingSession?.id ?? null}
          onSelectSession={setIncomingSelectionId}
          onAccept={onAccept}
          isLoading={isLoading}
        />

        {/* Customer info - full width expanded */}
        <div className="flex-1 overflow-hidden p-5">
          <div className="h-full overflow-hidden rounded-2xl border border-border bg-card shadow-card">
            <CustomerInfoPanel
              customerId={
                selectedPendingSession
                  ? getSessionCustomerId(selectedPendingSession)
                  : null
              }
              routingContext={selectedIncomingRoutingContext}
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
              routingContext={sessionRoutingContext}
              isConnected={false}
              variant="compact"
              onToggle={() => toggleDensity("customer")}
            />
            <div className="flex-1 overflow-hidden rounded-2xl border border-border bg-card flex flex-col shadow-card">
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
              className="rounded-xl border border-border bg-white px-4 py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground hover:border-accent/30 hover:bg-accent/5 transition-all"
            >
              Zurück zur Warteschlange
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
          <div
            className={`overflow-hidden flex flex-col min-h-0 ${
              density.customer === "expanded"
                ? "flex-1 rounded-2xl border border-border bg-card shadow-card hover:shadow-card-hover transition-shadow"
                : ""
            }`}
          >
            <CustomerInfoPanel
              customerId={customerId}
              routingContext={sessionRoutingContext}
              isConnected={isConnected}
              variant={density.customer}
              onToggle={() => toggleDensity("customer")}
            />
          </div>
          <div
            className={`overflow-hidden flex flex-col min-h-0 ${
              density.transcript === "expanded"
                ? "flex-1 rounded-2xl border border-border bg-card shadow-card hover:shadow-card-hover transition-shadow"
                : ""
            }`}
          >
            <InteractionPanel
              transcript={transcript}
              isConnected={isConnected}
              variant={density.transcript}
              onToggle={() => toggleDensity("transcript")}
            />
          </div>
        </div>

        {/* Right column */}
        <div className="overflow-hidden rounded-2xl border border-border bg-card flex flex-col shadow-card hover:shadow-card-hover transition-shadow min-h-0">
          <SuggestionsPanel
            advice={advice}
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
