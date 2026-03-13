"use client";

import { useEffect, useRef } from "react";
import type { TranscriptEntry } from "@voicebridge/contracts";
import type { PanelVariant } from "@/lib/use-phase";

interface InteractionPanelProps {
  transcript: TranscriptEntry[];
  isConnected: boolean;
  variant?: PanelVariant;
  onToggle?: () => void;
}

export function InteractionPanel({
  transcript,
  isConnected,
  variant = "expanded",
  onToggle,
}: InteractionPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript]);

  if (variant === "compact") {
    const lastMessage = transcript[transcript.length - 1];
    const preview = lastMessage
      ? lastMessage.text.length > 60
        ? lastMessage.text.slice(0, 60) + "..."
        : lastMessage.text
      : "Keine Nachrichten";

    return (
      <button
        onClick={onToggle}
        className="panel-morph flex w-full items-center gap-3 rounded-2xl border border-border/60 bg-card px-4 py-3 text-left shadow-sm hover:shadow-md transition-shadow"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        <span className="text-sm font-medium text-muted-foreground">
          Transkript
        </span>
        {transcript.length > 0 && (
          <span className="rounded-lg bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
            {transcript.length}
          </span>
        )}
        <span className="ml-auto truncate text-xs text-muted-foreground max-w-[200px]">
          {preview}
        </span>
      </button>
    );
  }

  return (
    <div className="panel-morph flex h-full flex-col">
      {/* Header */}
      <button
        onClick={onToggle}
        disabled={!onToggle}
        className="flex items-center justify-between border-b border-border/60 px-5 py-4 text-left disabled:cursor-default"
      >
        <span className="font-mono-ui flex items-center gap-2 text-sm uppercase tracking-wide text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Live-Transkript
        </span>
        {isConnected && (
          <span className="flex items-center gap-2 text-sm text-success">
            <span className="h-2 w-2 animate-pulse-dot rounded-full bg-success" />
            Zuhören
          </span>
        )}
      </button>

      {/* Transcript content */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {transcript.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">
              {isConnected
                ? "Warten auf Gespräch..."
                : "Sitzung starten, um das Transkript zu sehen"}
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
    <div className={`flex ${isCustomer ? "justify-start" : "justify-end"}`}>
      <div
        className={`max-w-[80%] rounded-xl px-3 py-2 ${
          isCustomer
            ? "bg-muted text-foreground border-l-2 border-accent/40"
            : "gradient-accent text-white"
        }`}
      >
        <div className="mb-1 flex items-center gap-2 justify-between">
          <span className="font-mono-ui text-xs uppercase opacity-80">
            {isCustomer ? "Kunde" : "Agent"}
          </span>
          <span className="text-xs opacity-60">
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
