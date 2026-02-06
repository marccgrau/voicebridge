"use client";

import { useEffect, useRef, useState } from "react";
import DailyIframe from "@daily-co/daily-js";
import type { DailyCall } from "@daily-co/daily-js";

/**
 * Hook for joining a Daily.co room with audio (no video).
 * Used by the customer call UI.
 */
export function useDailyAudio(roomUrl: string | null, token: string | null) {
  const callRef = useRef<DailyCall | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!roomUrl || !token) {
      if (callRef.current) {
        callRef.current.leave();
        callRef.current.destroy();
        callRef.current = null;
      }
      return;
    }

    // Prevent duplicate instances (React strict mode double-mount)
    if (callRef.current) {
      return;
    }

    const call = DailyIframe.createCallObject();

    call.on("joined-meeting", () => setIsConnected(true));
    call.on("left-meeting", () => setIsConnected(false));
    call.on("error", () => setIsConnected(false));

    call
      .join({
        url: roomUrl,
        token,
        startAudioOff: false,
        startVideoOff: true,
      })
      .catch((error) => {
        console.error("Failed to join Daily.co room:", error);
      });

    callRef.current = call;

    return () => {
      if (callRef.current) {
        callRef.current.leave();
        callRef.current.destroy();
        callRef.current = null;
      }
    };
  }, [roomUrl, token]);

  const leave = () => {
    if (callRef.current) {
      callRef.current.leave();
      callRef.current.destroy();
      callRef.current = null;
      setIsConnected(false);
    }
  };

  return { isConnected, leave };
}
