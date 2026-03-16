"use client";

import { useEffect, useRef } from "react";
import { usePipecatClient } from "@pipecat-ai/client-react";

/**
 * Plays audio from all remote participants in the Daily room.
 *
 * The Pipecat RTVI client only exposes "bot" tracks, but our room has 3
 * participants (customer, agent, bot). This component bypasses the Pipecat
 * tracks() API and listens directly on the Daily call object for audio
 * tracks from any non-local participant.
 *
 * Renders nothing visible — just manages hidden <audio> elements.
 */
export function DailyRoomAudio() {
  const client = usePipecatClient();
  const audioElementsRef = useRef<Map<string, HTMLAudioElement>>(new Map());

  useEffect(() => {
    if (!client) return;

    // Access the underlying Daily call object from the transport
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const daily = (client.transport as any)?.dailyCallClient;
    if (!daily) return;

    const handleTrackStarted = (ev: {
      participant?: { local?: boolean; session_id: string };
      track?: MediaStreamTrack;
    }) => {
      if (ev.participant?.local) return;
      if (ev.track?.kind !== "audio") return;

      const id = ev.participant!.session_id;

      // Clean up any existing element for this participant
      const existing = audioElementsRef.current.get(id);
      if (existing) {
        existing.srcObject = null;
      }

      const audio = document.createElement("audio");
      audio.autoplay = true;
      audio.srcObject = new MediaStream([ev.track!]);
      audioElementsRef.current.set(id, audio);
    };

    const handleTrackStopped = (ev: {
      participant?: { local?: boolean; session_id: string };
      track?: MediaStreamTrack;
    }) => {
      if (ev.participant?.local) return;
      if (ev.track?.kind !== "audio") return;

      const id = ev.participant!.session_id;
      const audio = audioElementsRef.current.get(id);
      if (audio) {
        audio.srcObject = null;
        audioElementsRef.current.delete(id);
      }
    };

    daily.on("track-started", handleTrackStarted);
    daily.on("track-stopped", handleTrackStopped);

    // Handle participants already in the room
    const participants = daily.participants?.();
    if (participants) {
      for (const [, p] of Object.entries(participants)) {
        const participant = p as {
          local?: boolean;
          session_id: string;
          tracks?: { audio?: { persistentTrack?: MediaStreamTrack } };
        };
        if (participant.local) continue;
        const audioTrack = participant.tracks?.audio?.persistentTrack;
        if (audioTrack) {
          handleTrackStarted({
            participant,
            track: audioTrack,
          });
        }
      }
    }

    return () => {
      daily.off("track-started", handleTrackStarted);
      daily.off("track-stopped", handleTrackStopped);
      audioElementsRef.current.forEach((audio) => {
        audio.srcObject = null;
      });
      audioElementsRef.current.clear();
    };
  }, [client]);

  return null;
}
