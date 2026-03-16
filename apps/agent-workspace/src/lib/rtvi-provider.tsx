/* eslint-disable react-hooks/set-state-in-effect */
"use client";

import { useState, useEffect, type ReactNode } from "react";
import { PipecatClient } from "@pipecat-ai/client-js";
import { DailyTransport } from "@pipecat-ai/daily-transport";
import { PipecatClientProvider } from "@pipecat-ai/client-react";

/**
 * Provides a singleton PipecatClient (with DailyTransport) to the component tree.
 *
 * Client creation is deferred to a useEffect because DailyTransport requires
 * browser WebRTC APIs that are unavailable during Next.js SSR.
 * Child hooks (usePipecatClient, useRTVIClientEvent, etc.) gracefully handle
 * the undefined client during the initial server render.
 */
export function PipecatRTVIProvider({ children }: { children: ReactNode }) {
  const [client, setClient] = useState<PipecatClient | null>(null);

  useEffect(() => {
    setClient(
      new PipecatClient({
        transport: new DailyTransport(),
        enableMic: false,
        enableCam: false,
      })
    );
  }, []);

  if (!client) return <>{children}</>;

  return (
    <PipecatClientProvider client={client}>{children}</PipecatClientProvider>
  );
}
