"use client";

import { useState } from "react";
import {
  useCustomerSession,
  type SessionRoutingOptions,
} from "@/lib/customer-session";
import { useDailyAudio } from "@/lib/daily-audio";
import { useCustomers } from "@/lib/use-customers";

export default function CustomerCallPage() {
  const {
    callState,
    sessionId,
    roomUrl,
    customerToken,
    isLoading,
    error,
    startCall,
    endCall,
  } = useCustomerSession();

  const { isConnected: isAudioConnected } = useDailyAudio(
    roomUrl,
    customerToken
  );

  const { customers, isLoading: isLoadingCustomers } = useCustomers();
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");
  const [callEntrySource, setCallEntrySource] = useState<"direct" | "voice_ai">(
    "direct"
  );
  const [voiceAiSummary, setVoiceAiSummary] = useState<string>(
    "Customer explained their issue to the Voice AI assistant and requested a specialist review."
  );
  const [voiceAiTransferReason, setVoiceAiTransferReason] = useState<string>(
    "Needs a human agent for account-specific decision and final confirmation."
  );

  const handleStartCall = () => {
    const routing: SessionRoutingOptions =
      callEntrySource === "voice_ai"
        ? {
            source: "voice_ai",
            handoffSummary: voiceAiSummary,
            transferReason: voiceAiTransferReason,
          }
        : { source: "direct" };

    startCall(selectedCustomerId || undefined, routing);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-md space-y-6 rounded-xl border border-border bg-card p-8 text-center">
        <h1 className="text-2xl font-semibold">VoiceBridge</h1>
        <p className="text-sm text-muted-foreground">Customer Support Call</p>

        {error && (
          <div className="rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Idle state */}
        {callState === "idle" && (
          <div className="space-y-4">
            <p className="text-muted-foreground">
              Select a customer profile and start a call with a support agent.
            </p>

            {/* Customer selector */}
            <div className="space-y-2 text-left">
              <label
                htmlFor="customer-select"
                className="text-sm font-medium text-foreground"
              >
                Customer
              </label>
              <select
                id="customer-select"
                value={selectedCustomerId}
                onChange={(e) => setSelectedCustomerId(e.target.value)}
                disabled={isLoadingCustomers}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
              >
                <option value="">Select a customer...</option>
                {customers.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name} ({customer.classification})
                  </option>
                ))}
              </select>
            </div>

            {/* Call routing simulation */}
            <div className="space-y-2 text-left">
              <label
                htmlFor="call-entry-source"
                className="text-sm font-medium text-foreground"
              >
                Entry Route
              </label>
              <select
                id="call-entry-source"
                value={callEntrySource}
                onChange={(e) =>
                  setCallEntrySource(e.target.value as "direct" | "voice_ai")
                }
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="direct">Direct to agent queue</option>
                <option value="voice_ai">Transferred from Voice AI</option>
              </select>
              <p className="text-xs text-muted-foreground">
                This controls routing context shown to the agent before accept.
              </p>
            </div>

            {callEntrySource === "voice_ai" && (
              <div className="space-y-3 rounded-md border border-accent/30 bg-accent/5 p-3 text-left">
                <div className="space-y-1.5">
                  <label
                    htmlFor="voice-ai-summary"
                    className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    Voice AI handoff summary
                  </label>
                  <textarea
                    id="voice-ai-summary"
                    value={voiceAiSummary}
                    onChange={(e) => setVoiceAiSummary(e.target.value)}
                    rows={3}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div className="space-y-1.5">
                  <label
                    htmlFor="voice-ai-transfer-reason"
                    className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
                  >
                    Transfer reason
                  </label>
                  <textarea
                    id="voice-ai-transfer-reason"
                    value={voiceAiTransferReason}
                    onChange={(e) => setVoiceAiTransferReason(e.target.value)}
                    rows={2}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>
            )}

            <button
              onClick={handleStartCall}
              disabled={isLoading || isLoadingCustomers}
              className="w-full rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {isLoading ? "Connecting..." : "Start Call"}
            </button>
          </div>
        )}

        {/* Calling state — waiting for agent */}
        {callState === "calling" && (
          <div className="space-y-4">
            <div className="flex flex-col items-center gap-3">
              <span className="h-4 w-4 animate-pulse rounded-full bg-primary" />
              <p className="text-muted-foreground">
                {isAudioConnected
                  ? "Connected. Waiting for an agent to accept..."
                  : "Connecting to room..."}
              </p>
            </div>
            {sessionId && (
              <p className="text-xs text-muted-foreground">
                Session: {sessionId.slice(0, 8)}...
              </p>
            )}
            <button
              onClick={endCall}
              disabled={isLoading}
              className="w-full rounded-md bg-destructive px-4 py-3 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        )}

        {/* Connected state — agent joined */}
        {callState === "connected" && (
          <div className="space-y-4">
            <div className="flex flex-col items-center gap-3">
              <span className="flex items-center gap-2 text-sm text-success">
                <span className="h-2 w-2 rounded-full bg-success" />
                Connected with agent
              </span>
            </div>
            {sessionId && (
              <p className="text-xs text-muted-foreground">
                Session: {sessionId.slice(0, 8)}...
              </p>
            )}
            <button
              onClick={endCall}
              disabled={isLoading}
              className="w-full rounded-md bg-destructive px-4 py-3 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
            >
              End Call
            </button>
          </div>
        )}

        {/* Ended state */}
        {callState === "ended" && (
          <div className="space-y-4">
            <p className="text-muted-foreground">Call ended. Thank you!</p>
            <button
              onClick={() => window.location.reload()}
              className="w-full rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Start New Call
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
