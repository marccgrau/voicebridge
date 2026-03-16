"use client";

import { useEffect, useRef, useState } from "react";
import DailyIframe from "@daily-co/daily-js";
import type { DailyCall } from "@daily-co/daily-js";

/**
 * Hook for joining a Daily.co room with audio (no video).
 * Used by the customer call UI.
 *
 * Creates hidden <audio> elements for each remote participant's audio track
 * so that the customer can hear the agent (and any other remote participants).
 */
export function useDailyAudio(roomUrl: string | null, token: string | null) {
  const callRef = useRef<DailyCall | null>(null);
  const audioElementsRef = useRef<Map<string, HTMLAudioElement>>(new Map());
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!roomUrl || !token) {
      if (callRef.current) {
        callRef.current.leave();
        callRef.current.destroy();
        callRef.current = null;
      }
      audioElementsRef.current.forEach((audio) => {
        audio.srcObject = null;
      });
      audioElementsRef.current.clear();
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

    // Play audio from remote participants
    call.on("track-started", (ev) => {
      if (!ev?.participant || ev.participant.local) return;
      if (ev?.track?.kind !== "audio") return;

      const id = ev.participant.session_id;

      // Clean up any existing element for this participant
      const existing = audioElementsRef.current.get(id);
      if (existing) {
        existing.srcObject = null;
      }

      const audio = document.createElement("audio");
      audio.autoplay = true;
      audio.srcObject = new MediaStream([ev.track]);
      audioElementsRef.current.set(id, audio);
    });

    call.on("track-stopped", (ev) => {
      if (!ev?.participant || ev.participant.local) return;
      if (ev?.track?.kind !== "audio") return;

      const id = ev.participant.session_id;
      const audio = audioElementsRef.current.get(id);
      if (audio) {
        audio.srcObject = null;
        audioElementsRef.current.delete(id);
      }
    });

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
      audioElementsRef.current.forEach((audio) => {
        audio.srcObject = null;
      });
      audioElementsRef.current.clear();
      if (callRef.current) {
        callRef.current.leave();
        callRef.current.destroy();
        callRef.current = null;
      }
    };
  }, [roomUrl, token]);

  const leave = () => {
    audioElementsRef.current.forEach((audio) => {
      audio.srcObject = null;
    });
    audioElementsRef.current.clear();
    if (callRef.current) {
      callRef.current.leave();
      callRef.current.destroy();
      callRef.current = null;
      setIsConnected(false);
    }
  };

  return { isConnected, leave };
}
