"use client";

import { useState } from "react";
import { InteractionPanel } from "@/components/workspace/InteractionPanel";
import { SuggestionsPanel } from "@/components/workspace/SuggestionsPanel";
import { ProcessStatusPanel } from "@/components/workspace/ProcessStatusPanel";
import { HistoryPanel } from "@/components/workspace/HistoryPanel";
import { useSession } from "@/lib/session";
import { useSupabaseSubscription, type TranscriptSegment } from "@/lib/supabase";
import { useRTVI } from "@/lib/rtvi";
import type {
  TranscriptEntry,
  Suggestion,
  ProcessStep,
} from "@voicebridge/contracts";

export default function WorkspacePage() {
  const { sessionId, isConnected, roomUrl, roomToken, startSession, stopSession } = useSession();

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

      <WorkspacePanels
        key={sessionId ?? "no-session"}
        sessionId={sessionId}
        isConnected={isConnected}
        roomUrl={roomUrl}
        roomToken={roomToken}
      />
    </div>
  );
}

function WorkspacePanels({
  sessionId,
  isConnected,
  roomUrl,
  roomToken,
}: {
  sessionId: string | null;
  isConnected: boolean;
  roomUrl: string | null;
  roomToken: string | null;
}) {
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [processKey, setProcessKey] = useState<string | null>(null);
  const [processName, setProcessName] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [steps, setSteps] = useState<ProcessStep[]>([]);

  // Subscribe to transcript updates via Supabase
  useSupabaseSubscription(sessionId, {
    onTranscriptSegment: (segment: TranscriptSegment) => {
      setTranscript((prev) => [
        ...prev,
        {
          id: segment.id,
          speaker: segment.speaker,
          text: segment.text,
          timestamp: segment.ts,
          isFinal: segment.is_final,
        },
      ]);
    },
  });

  // Subscribe to RTVI messages via WebRTC data channel
  useRTVI(roomUrl, roomToken, {
    onSuggestion: (message) => {
      setSuggestions(message.data.suggestions);
    },
    onProcessIllustration: (message) => {
      const processSteps = message.data.steps.map((step) => ({
        key: step.key,
        label: step.label,
        status: step.status,
      }));

      setProcessKey(message.data.processKey);
      setProcessName(message.data.processName);
      setSteps(processSteps);
      // Convert step index to step key
      setCurrentStep(
        message.data.currentStep >= 0 && message.data.currentStep < processSteps.length
          ? processSteps[message.data.currentStep]?.key ?? null
          : null
      );
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
          slots={{}}
        />
      </div>

      {/* Bottom Right - History Panel */}
      <div className="overflow-hidden rounded-lg border border-border bg-card">
        <HistoryPanel sessionId={sessionId} />
      </div>
    </main>
  );
}
