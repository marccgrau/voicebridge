"use client";

import { useCallback, useRef, useEffect } from "react";
import { RTVIEvent } from "@pipecat-ai/client-js";
import { useRTVIClientEvent } from "@pipecat-ai/client-react";
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

/**
 * Subscribes to RTVI server messages via the PipecatClient context
 * and dispatches them to typed handlers.
 */
export function useRTVIMessages(handlers: RTVIHandlers) {
  const handlersRef = useRef(handlers);

  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    useCallback((data: any) => {
      try {
        const message = data as RTVIMessage;
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
    }, [])
  );
}
