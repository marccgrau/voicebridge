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
      <div className="w-full max-w-md rounded-2xl border border-border bg-white p-6 shadow-card md:p-8">
        <header className="mb-6 pb-4 text-center">
          <h1 className="font-display text-2xl font-semibold gradient-text">
            VoiceBridge Experiment
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Kundenrollen-Schnittstelle
          </p>
          <div className="mx-auto mt-4 h-px w-12 bg-gradient-to-r from-transparent via-accent/30 to-transparent" />
        </header>

        {error && (
          <div className="mb-4 rounded-xl border-l-4 border-l-destructive bg-destructive/5 px-4 py-2.5 text-sm text-destructive">
            {error}
          </div>
        )}

        {callState === "idle" && (
          <section className="space-y-4">
            <div className="space-y-2">
              <h2 className="text-lg font-medium text-foreground">
                Persona auswählen
              </h2>
              <select
                value={selectedCustomerId}
                onChange={(event) => setSelectedCustomerId(event.target.value)}
                disabled={isLoadingCustomers}
                className="w-full rounded-xl border border-border bg-white px-3 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent/25 focus:border-accent/50 transition-colors"
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
              className="w-full rounded-xl gradient-accent px-4 py-3 text-sm font-medium text-white shadow-card hover:-translate-y-0.5 hover:shadow-accent transition-all disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-card"
            >
              {isLoading ? "Anruf wird gestartet..." : "Anruf starten"}
            </button>
          </section>
        )}

        {callState === "calling" && (
          <section className="space-y-5 text-center">
            <div className="relative mx-auto flex h-16 w-16 items-center justify-center">
              <span className="absolute inset-0 rounded-full border-2 border-accent/30 animate-ring-1" />
              <span className="absolute inset-0 rounded-full border-2 border-accent/20 animate-ring-2" />
              <span className="absolute inset-0 rounded-full border-2 border-accent/10 animate-ring-3" />
              <span className="h-4 w-4 rounded-full gradient-accent" />
            </div>
            <p className="text-sm text-muted-foreground">
              {isAudioConnected
                ? "Verbunden. Warten auf Agent-Annahme..."
                : "Verbindung wird hergestellt..."}
            </p>
            {sessionId && (
              <p className="font-mono-ui text-xs text-muted-foreground/60">
                Sitzung: {sessionId.slice(0, 8)}...
              </p>
            )}
            <button
              onClick={endCall}
              disabled={isLoading}
              className="w-full rounded-xl border border-destructive/60 px-4 py-3 text-sm font-medium text-destructive hover:bg-destructive hover:text-white hover:border-destructive transition-all disabled:opacity-50"
            >
              Abbrechen
            </button>
          </section>
        )}

        {callState === "connected" && (
          <section className="space-y-4 text-center">
            <div className="rounded-xl border-2 border-accent/40 bg-accent/5 px-4 py-3.5 text-sm font-semibold text-accent">
              Anruf aktiv
            </div>

            {sessionId && (
              <p className="font-mono-ui text-xs text-muted-foreground/60">
                Sitzung: {sessionId.slice(0, 8)}...
              </p>
            )}

            <button
              onClick={endCall}
              disabled={isLoading}
              className="w-full rounded-xl bg-destructive px-4 py-3 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50"
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
              className="w-full rounded-xl gradient-accent px-4 py-3 text-sm font-medium text-white shadow-card hover:-translate-y-0.5 hover:shadow-accent transition-all"
            >
              Neuen Anruf starten
            </button>
          </section>
        )}
      </div>
    </div>
  );
}
