"use client";

import { useEffect, useRef, useState } from "react";
import DailyIframe from "@daily-co/daily-js";
import type { DailyCall, DailyEventObjectAppMessage } from "@daily-co/daily-js";
import type { RTVIMessage } from "@voicebridge/contracts";

export interface RTVIHandlers {
  onSuggestion?: (message: Extract<RTVIMessage, { action: "agent_guidance" }>) => void;
  onProcessIllustration?: (message: Extract<RTVIMessage, { action: "process_illustration" }>) => void;
}

/**
 * Hook to connect to Daily.co room and listen for RTVI messages
 */
export function useRTVI(
  roomUrl: string | null,
  roomToken: string | null,
  handlers: RTVIHandlers
) {
  const callRef = useRef<DailyCall | null>(null);
  const handlersRef = useRef(handlers);
  const [isConnected, setIsConnected] = useState(false);

  // Keep handlers ref updated
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  useEffect(() => {
    if (!roomUrl || !roomToken) {
      // Cleanup existing connection
      if (callRef.current) {
        callRef.current.leave();
        callRef.current.destroy();
        callRef.current = null;
      }
      return;
    }

    // Create Daily call object
    const call = DailyIframe.createCallObject();

    // Track connection state with Daily events
    call.on("joined-meeting", () => {
      console.log("Connected to Daily.co room for RTVI messages");
      setIsConnected(true);
    });

    call.on("left-meeting", () => {
      setIsConnected(false);
    });

    call.on("error", (error) => {
      console.error("Daily.co error:", error);
      setIsConnected(false);
    });

    // Listen for app messages (RTVI messages)
    call.on("app-message", (event: DailyEventObjectAppMessage) => {
      try {
        const message = event.data as RTVIMessage;
        const h = handlersRef.current;

        // Route message to appropriate handler
        if (message.action === "agent_guidance") {
          h.onSuggestion?.(message);
        } else if (message.action === "process_illustration") {
          h.onProcessIllustration?.(message);
        }
      } catch (error) {
        console.error("Failed to handle RTVI message:", error);
      }
    });

    // Join the room
    call
      .join({
        url: roomUrl,
        token: roomToken,
        // Listen-only: no audio/video from frontend
        startAudioOff: true,
        startVideoOff: true,
      })
      .catch((error) => {
        console.error("Failed to join Daily.co room:", error);
      });

    callRef.current = call;

    // Cleanup on unmount or room change
    return () => {
      if (callRef.current) {
        callRef.current.leave();
        callRef.current.destroy();
        callRef.current = null;
      }
    };
  }, [roomUrl, roomToken]);

  return {
    isConnected,
  };
}
