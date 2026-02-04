"use client";

import { useState } from "react";
import { InteractionPanel } from "@/components/workspace/InteractionPanel";
import { SuggestionsPanel } from "@/components/workspace/SuggestionsPanel";
import { ProcessStatusPanel } from "@/components/workspace/ProcessStatusPanel";
import { HistoryPanel } from "@/components/workspace/HistoryPanel";
import { useSession } from "@/lib/session";
import { useSupabaseSubscription } from "@/lib/supabase";
import type {
  TranscriptSegmentEvent,
  ProcessSelectionEvent,
  SuggestionEvent,
  SessionStateEvent,
  TranscriptEntry,
  Suggestion,
  ProcessStep,
} from "@voicebridge/contracts";

export default function WorkspacePage() {
  const { sessionId, isConnected, startSession, stopSession } = useSession();

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex h-14 items-center justify-between border-b border-border px-6">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">VoiceBridge</h1>
          {sessionId && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              Session: {sessionId.slice(0, 8)}...
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {isConnected ? (
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
          ) : (
            <button
              onClick={startSession}
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Start Session
            </button>
          )}
        </div>
      </header>

      <WorkspacePanels key={sessionId ?? "no-session"} sessionId={sessionId} isConnected={isConnected} />
    </div>
  );
}

function WorkspacePanels({
  sessionId,
  isConnected,
}: {
  sessionId: string | null;
  isConnected: boolean;
}) {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [processKey, setProcessKey] = useState<string | null>(null);
  const [processName, setProcessName] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [steps, setSteps] = useState<ProcessStep[]>([]);
  const [slots, setSlots] = useState<Record<string, string>>({});

  useSupabaseSubscription(sessionId, {
    onTranscriptSegment: (event: TranscriptSegmentEvent) => {
      if (event.isFinal) {
        setTranscript((prev) => [
          ...prev,
          {
            id: event.eventId,
            speaker: event.speaker,
            text: event.text,
            timestamp: event.timestamp,
            isFinal: event.isFinal,
          },
        ]);
      }
    },
    onProcessSelection: (event: ProcessSelectionEvent) => {
      setProcessKey(event.processKey);
      setProcessName(event.processName);
    },
    onSuggestion: (event: SuggestionEvent) => {
      setSuggestions(event.suggestions);
    },
    onSessionState: (event: SessionStateEvent) => {
      setProcessKey(event.processKey);
      setProcessName(event.processName);
      setCurrentStep(event.currentStep);
      setSteps(event.steps);
      setSlots(event.slots);
    },
  });

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
          slots={slots}
        />
      </div>

      {/* Bottom Right - History Panel */}
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <HistoryPanel sessionId={sessionId} />
      </div>
    </main>
  );
}
