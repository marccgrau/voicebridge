"use client";

import { useMemo, useState } from "react";

import { useCustomerSession } from "@/lib/customer-session";
import { useDailyAudio } from "@/lib/daily-audio";
import { useCustomers } from "@/lib/use-customers";

export default function CustomerCallPage() {
  const {
    callState,
    sessionId,
    roomUrl,
    customerToken,
    isLoading,
    error,
    startCall,
    endCall,
  } = useCustomerSession();

  const { isConnected: isAudioConnected } = useDailyAudio(
    roomUrl,
    customerToken
  );
  const { customers, isLoading: isLoadingCustomers } = useCustomers();

  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");

  const selectedCustomer = useMemo(
    () =>
      customers.find((customer) => customer.id === selectedCustomerId) ?? null,
    [customers, selectedCustomerId]
  );

  const canStartCall = Boolean(selectedCustomer?.scenarioId);

  const handleStartCall = async () => {
    if (!selectedCustomer?.scenarioId) {
      return;
    }

    try {
      await startCall({
        customerId: selectedCustomer.id,
        scenarioId: selectedCustomer.scenarioId,
      });
    } catch {
      // Error state is already set inside useCustomerSession.
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 md:p-8">
        <header className="mb-6 border-b border-border pb-4 text-center">
          <h1 className="text-2xl font-semibold">VoiceBridge Experiment</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Kundenrollen-Schnittstelle
          </p>
        </header>

        {error && (
          <div className="mb-4 rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {callState === "idle" && (
          <section className="space-y-4">
            <div className="space-y-2">
              <h2 className="text-lg font-medium">Persona auswählen</h2>
              <select
                value={selectedCustomerId}
                onChange={(event) => setSelectedCustomerId(event.target.value)}
                disabled={isLoadingCustomers}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">Persona wählen...</option>
                {customers.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                  </option>
                ))}
              </select>
              {selectedCustomer && !selectedCustomer.scenarioId && (
                <p className="text-sm text-destructive">
                  Kein Szenario zugeordnet.
                </p>
              )}
            </div>

            <button
              onClick={handleStartCall}
              disabled={!canStartCall || isLoading}
              className="w-full rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {isLoading ? "Anruf wird gestartet..." : "Anruf starten"}
            </button>
          </section>
        )}

        {callState === "calling" && (
          <section className="space-y-4 text-center">
            <span className="mx-auto block h-4 w-4 animate-pulse rounded-full bg-primary" />
            <p className="text-muted-foreground">
              {isAudioConnected
                ? "Verbunden. Warten auf Agent-Annahme..."
                : "Verbindung wird hergestellt..."}
            </p>
            {sessionId && (
              <p className="text-xs text-muted-foreground">
                Sitzung: {sessionId.slice(0, 8)}...
              </p>
            )}
            <button
              onClick={endCall}
              disabled={isLoading}
              className="w-full rounded-md bg-destructive px-4 py-3 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
            >
              Abbrechen
            </button>
          </section>
        )}

        {callState === "connected" && (
          <section className="space-y-4 text-center">
            <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
              Anruf aktiv
            </div>

            {sessionId && (
              <p className="text-xs text-muted-foreground">
                Sitzung: {sessionId.slice(0, 8)}...
              </p>
            )}

            <button
              onClick={endCall}
              disabled={isLoading}
              className="w-full rounded-md bg-destructive px-4 py-3 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
            >
              Anruf beenden
            </button>
          </section>
        )}

        {callState === "ended" && (
          <section className="space-y-4 text-center">
            <p className="text-muted-foreground">Anruf beendet. Vielen Dank!</p>
            <button
              onClick={() => window.location.reload()}
              className="w-full rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Neuen Anruf starten
            </button>
          </section>
        )}
      </div>
    </div>
  );
}
