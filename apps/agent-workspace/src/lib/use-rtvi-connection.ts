"use client";

import { useEffect, useRef } from "react";
import {
  usePipecatClient,
  usePipecatClientTransportState,
} from "@pipecat-ai/client-react";
import type { TransportState } from "@pipecat-ai/client-js";

/**
 * Manages the PipecatClient connection lifecycle.
 *
 * Connects to a Daily room when roomUrl and roomToken are provided,
 * and disconnects when they become null or the component unmounts.
 */
export function useRTVIConnection(
  roomUrl: string | null,
  roomToken: string | null,
  options?: { enableMic?: boolean }
): { transportState: TransportState } {
  const client = usePipecatClient();
  const transportState = usePipecatClientTransportState();
  const enableMicRef = useRef(options?.enableMic ?? false);

  // Keep ref in sync (declared before connect effect so it runs first on mount)
  useEffect(() => {
    enableMicRef.current = options?.enableMic ?? false;
  }, [options?.enableMic]);

  // Manage connection lifecycle
  useEffect(() => {
    if (!client || !roomUrl || !roomToken) return;

    // Set mic state before connect() so DailyTransport joins with the
    // correct audio config (startAudioOff derived from enableMic).
    client.enableMic(enableMicRef.current);

    client.connect({ url: roomUrl, token: roomToken }).catch((error) => {
      console.error("Failed to connect to Daily.co room:", error);
    });

    return () => {
      client.disconnect().catch((error) => {
        console.error("Failed to disconnect from Daily.co room:", error);
      });
    };
  }, [client, roomUrl, roomToken]);

  // Manage mic state independently so toggling mic doesn't cause reconnect
  useEffect(() => {
    if (!client) return;
    client.enableMic(options?.enableMic ?? false);
  }, [client, options?.enableMic]);

  return { transportState };
}
