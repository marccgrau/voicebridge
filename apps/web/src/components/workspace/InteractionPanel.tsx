"use client";

import { useEffect, useRef } from "react";
import type { TranscriptEntry } from "@voicebridge/contracts";

interface InteractionPanelProps {
  transcript: TranscriptEntry[];
  isConnected: boolean;
}

export function InteractionPanel({ transcript, isConnected }: InteractionPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript]);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="font-semibold">Live Transcript</h2>
        {isConnected && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
            Listening
          </span>
        )}
      </div>

      {/* Transcript content */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-3"
      >
        {transcript.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">
              {isConnected
                ? "Waiting for conversation..."
                : "Start a session to see the transcript"}
            </p>
          </div>
        ) : (
          transcript.map((entry) => (
            <TranscriptMessage key={entry.id} entry={entry} />
          ))
        )}
      </div>
    </div>
  );
}

function TranscriptMessage({ entry }: { entry: TranscriptEntry }) {
  const isCustomer = entry.speaker === "customer";

  return (
    <div
      className={`flex ${isCustomer ? "justify-start" : "justify-end"}`}
    >
      <div
        className={`max-w-[80%] rounded-lg px-3 py-2 ${
          isCustomer
            ? "bg-muted text-foreground"
            : "bg-primary text-primary-foreground"
        }`}
      >
        <div className="mb-1 flex items-center gap-2">
          <span className="text-xs font-medium opacity-70">
            {isCustomer ? "Customer" : "Agent"}
          </span>
          <span className="text-xs opacity-50">
            {formatTime(entry.timestamp)}
          </span>
        </div>
        <p className="text-sm">{entry.text}</p>
      </div>
    </div>
  );
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
