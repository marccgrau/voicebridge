"use client";

import { useCustomerSession } from "@/lib/customer-session";
import { useDailyAudio } from "@/lib/daily-audio";

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
              Click below to start a call with a support agent.
            </p>
            <button
              onClick={startCall}
              disabled={isLoading}
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
