"use client";

import { useEffect, useRef, useState } from "react";
import { PipecatClient, RTVIEvent } from "@pipecat-ai/client-js";
import { DailyTransport } from "@pipecat-ai/daily-transport";
import type { RTVIMessage } from "@voicebridge/contracts";

export interface RTVIHandlers {
  onSuggestion?: (
    message: Extract<RTVIMessage, { action: "agent_guidance" }>
  ) => void;
  onProcessIllustration?: (
    message: Extract<RTVIMessage, { action: "process_illustration" }>
  ) => void;
  onTranscript?: (
    message: Extract<RTVIMessage, { action: "transcript_segment" }>
  ) => void;
}

export interface RTVIOptions {
  /** When true, join with microphone enabled (for agent audio). Default false. */
  audioEnabled?: boolean;
}

/**
 * Hook to connect to a Daily.co room via PipecatClient and listen for
 * RTVI server messages. Uses @pipecat-ai/daily-transport under the hood.
 */
export function useRTVI(
  roomUrl: string | null,
  roomToken: string | null,
  handlers: RTVIHandlers,
  options?: RTVIOptions
) {
  const clientRef = useRef<PipecatClient | null>(null);
  const handlersRef = useRef(handlers);
  const [isConnected, setIsConnected] = useState(false);

  // Keep handlers ref updated
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    if (!roomUrl || !roomToken) {
      // Cleanup existing connection
      if (clientRef.current) {
        clientRef.current.disconnect();
        clientRef.current = null;
      }
      return;
    }

    const client = new PipecatClient({
      transport: new DailyTransport(),
      enableMic: options?.audioEnabled ?? false,
      enableCam: false,
    });

    client.on(RTVIEvent.Connected, () => {
      console.log("Connected to Daily.co room for RTVI messages");
      setIsConnected(true);
    });

    client.on(RTVIEvent.Disconnected, () => {
      setIsConnected(false);
    });

    client.on(RTVIEvent.Error, (error) => {
      console.error("PipecatClient error:", error);
      setIsConnected(false);
    });

    // Server messages are auto-unwrapped from the RTVI envelope
    client.on(RTVIEvent.ServerMessage, (message: RTVIMessage) => {
      try {
        const h = handlersRef.current;

        if (message.action === "agent_guidance") {
          h.onSuggestion?.(message);
        } else if (message.action === "process_illustration") {
          h.onProcessIllustration?.(message);
        } else if (message.action === "transcript_segment") {
          h.onTranscript?.(message);
        }
      } catch (error) {
        console.error("Failed to handle RTVI message:", error);
      }
    });

    client.connect({ url: roomUrl, token: roomToken }).catch((error) => {
      console.error("Failed to connect to Daily.co room:", error);
    });

    clientRef.current = client;

    // Cleanup on unmount or room change
    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect();
        clientRef.current = null;
      }
    };
  }, [roomUrl, roomToken, options?.audioEnabled]);

  return {
    isConnected,
  };
}
