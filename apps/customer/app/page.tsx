"use client";

import { useMemo, useState } from "react";
import type { ScenarioConversationStep } from "@voicebridge/contracts";

import { useCustomerSession } from "@/lib/customer-session";
import { useDailyAudio } from "@/lib/daily-audio";
import {
  renderActorGuidanceTexts,
  renderScenarioConversation,
  renderScenarioText,
} from "@/lib/scenario-render";
import { useCustomers } from "@/lib/use-customers";
import { useScenarios } from "@/lib/use-scenarios";
import { supabase } from "@/lib/supabase";

type PrepStage = "selection" | "briefing";

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
  const {
    scenarios,
    isLoading: isLoadingScenarios,
    error: scenarioError,
  } = useScenarios();

  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("");
  const [prepStage, setPrepStage] = useState<PrepStage>("selection");
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set());
  const [completedCheckpoints, setCompletedCheckpoints] = useState<Set<string>>(
    new Set()
  );
  const [showActorReference, setShowActorReference] = useState(true);

  const selectedCustomer = useMemo(
    () =>
      customers.find((customer) => customer.id === selectedCustomerId) ?? null,
    [customers, selectedCustomerId]
  );

  const selectedScenario = useMemo(
    () =>
      scenarios.find(
        (scenario) => scenario.scenarioId === selectedScenarioId
      ) ?? null,
    [scenarios, selectedScenarioId]
  );

  // Domain filtering: filter scenarios by selected customer's domain and vice versa
  const filteredScenarios = useMemo(() => {
    if (!selectedCustomer?.domain) {
      return scenarios;
    }
    return scenarios.filter(
      (scenario) => scenario.domain === selectedCustomer.domain
    );
  }, [scenarios, selectedCustomer]);

  const filteredCustomers = useMemo(() => {
    if (!selectedScenario) {
      return customers;
    }
    return customers.filter(
      (customer) =>
        !customer.domain || customer.domain === selectedScenario.domain
    );
  }, [customers, selectedScenario]);

  const renderedConversation = useMemo(() => {
    if (!selectedCustomer || !selectedScenario) {
      return [];
    }

    return renderScenarioConversation(selectedScenario, selectedCustomer);
  }, [selectedCustomer, selectedScenario]);

  const renderedActorGuidance = useMemo(() => {
    if (!selectedCustomer || !selectedScenario?.actorGuidance) {
      return null;
    }

    return {
      revealWhenAsked: renderActorGuidanceTexts(
        selectedScenario.actorGuidance.revealWhenAsked,
        selectedCustomer
      ),
      mustAskCheckpoints: selectedScenario.actorGuidance.mustAskCheckpoints,
    };
  }, [selectedCustomer, selectedScenario]);

  const canContinue = Boolean(selectedCustomer && selectedScenario);

  // Clear scenario selection when customer changes and scenario is no longer valid
  const handleCustomerChange = (customerId: string) => {
    setSelectedCustomerId(customerId);
    const customer = customers.find((c) => c.id === customerId);
    if (
      customer?.domain &&
      selectedScenario &&
      selectedScenario.domain !== customer.domain
    ) {
      setSelectedScenarioId("");
    }
  };

  // Clear customer selection when scenario changes and customer is no longer valid
  const handleScenarioChange = (scenarioId: string) => {
    setSelectedScenarioId(scenarioId);
    const scenario = scenarios.find((s) => s.scenarioId === scenarioId);
    if (
      scenario &&
      selectedCustomer?.domain &&
      selectedCustomer.domain !== scenario.domain
    ) {
      setSelectedCustomerId("");
    }
  };

  const handleStartCall = async () => {
    if (!selectedCustomer || !selectedScenario) {
      return;
    }

    setCompletedSteps(new Set());
    setCompletedCheckpoints(new Set());
    try {
      await startCall({
        customerId: selectedCustomer.id,
        scenarioId: selectedScenario.scenarioId,
      });
    } catch {
      // Error state is already set inside useCustomerSession.
    }
  };

  const toggleStepCompleted = async (step: ScenarioConversationStep) => {
    setCompletedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(step.id)) {
        next.delete(step.id);
      } else {
        next.add(step.id);
      }
      return next;
    });

    if (!sessionId || !selectedScenario) {
      return;
    }

    const { error } = await supabase.from("session_events").insert({
      session_id: sessionId,
      event_type: "actor_step_toggled",
      source: "customer_app",
      payload: {
        step_id: step.id,
        scenario_id: selectedScenario.scenarioId,
      },
    });

    if (error) {
      console.error("Failed to log actor step event:", error);
    }
  };

  const toggleCheckpoint = (checkpoint: string) => {
    setCompletedCheckpoints((prev) => {
      const next = new Set(prev);
      if (next.has(checkpoint)) {
        next.delete(checkpoint);
      } else {
        next.add(checkpoint);
      }
      return next;
    });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <div className="w-full max-w-5xl rounded-xl border border-border bg-card p-6 md:p-8">
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

        {scenarioError && (
          <div className="mb-4 rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
            Szenarien konnten nicht geladen werden: {scenarioError}
          </div>
        )}

        {callState === "idle" && prepStage === "selection" && (
          <section className="grid gap-6 md:grid-cols-2">
            <div className="space-y-4">
              <h2 className="text-lg font-medium">1. Persona auswählen</h2>
              <select
                value={selectedCustomerId}
                onChange={(event) => handleCustomerChange(event.target.value)}
                disabled={isLoadingCustomers}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">Persona wählen...</option>
                {filteredCustomers.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name} ({customer.classification})
                  </option>
                ))}
              </select>
              {selectedCustomer && (
                <p className="text-sm text-muted-foreground">
                  {selectedCustomer.domain && (
                    <span className="mr-2 inline-block rounded bg-muted px-1.5 py-0.5 text-xs font-medium uppercase">
                      {selectedCustomer.domain}
                    </span>
                  )}
                  {selectedCustomer.quickInternalNote ?? selectedCustomer.notes}
                </p>
              )}
            </div>

            <div className="space-y-4">
              <h2 className="text-lg font-medium">2. Szenario auswählen</h2>
              <select
                value={selectedScenarioId}
                onChange={(event) => handleScenarioChange(event.target.value)}
                disabled={isLoadingScenarios}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">Szenario wählen...</option>
                {filteredScenarios.map((scenario) => (
                  <option key={scenario.scenarioId} value={scenario.scenarioId}>
                    {scenario.title}
                  </option>
                ))}
              </select>
              {selectedScenario && (
                <p className="text-sm text-muted-foreground">
                  {selectedScenario.behavioralCondition.civilityCondition.toUpperCase()}{" "}
                  Bedingung
                </p>
              )}
            </div>

            <div className="md:col-span-2">
              <button
                onClick={() => setPrepStage("briefing")}
                disabled={!canContinue || isLoading}
                className="w-full rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                Weiter zum Briefing
              </button>
            </div>
          </section>
        )}

        {callState === "idle" &&
          prepStage === "briefing" &&
          selectedCustomer &&
          selectedScenario && (
            <section className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <article className="rounded-lg border border-border bg-muted/20 p-4">
                  <h2 className="text-base font-medium">Persona-Briefing</h2>
                  <p className="mt-2 text-sm">{selectedCustomer.name}</p>
                  <p className="text-sm text-muted-foreground">
                    Kundennummer: {selectedCustomer.customerCode ?? "N/A"}
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {selectedCustomer.quickInternalNote ??
                      selectedCustomer.notes}
                  </p>
                </article>

                <article className="rounded-lg border border-border bg-muted/20 p-4">
                  <h2 className="text-base font-medium">Szenario-Briefing</h2>
                  <p className="mt-2 text-sm">{selectedScenario.background}</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Ziel: {selectedScenario.customerGoal}
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Tonanweisung:{" "}
                    {selectedScenario.behavioralCondition.instruction}
                  </p>
                </article>
              </div>

              {selectedScenario.behavioralCondition.escalationCues && (
                <div className="grid gap-4 md:grid-cols-2">
                  <article className="rounded-lg border border-border bg-muted/10 p-4">
                    <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
                      Eskalationshinweise
                    </h3>
                    <ul className="mt-2 space-y-1">
                      {selectedScenario.behavioralCondition.escalationCues.map(
                        (cue, i) => (
                          <li key={i} className="text-sm text-muted-foreground">
                            &bull; {cue}
                          </li>
                        )
                      )}
                    </ul>
                  </article>

                  {selectedScenario.behavioralCondition.deescalationCues && (
                    <article className="rounded-lg border border-border bg-muted/10 p-4">
                      <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
                        Deeskalationshinweise
                      </h3>
                      <ul className="mt-2 space-y-1">
                        {selectedScenario.behavioralCondition.deescalationCues.map(
                          (cue, i) => (
                            <li
                              key={i}
                              className="text-sm text-muted-foreground"
                            >
                              &bull; {cue}
                            </li>
                          )
                        )}
                      </ul>
                    </article>
                  )}
                </div>
              )}

              {renderedActorGuidance && (
                <div className="grid gap-4 md:grid-cols-2">
                  {renderedActorGuidance.mustAskCheckpoints.length > 0 && (
                    <article className="rounded-lg border border-border bg-muted/10 p-4">
                      <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
                        Pflicht-Checkpoints
                      </h3>
                      <ul className="mt-2 space-y-1">
                        {renderedActorGuidance.mustAskCheckpoints.map(
                          (cp, i) => (
                            <li
                              key={i}
                              className="text-sm text-muted-foreground"
                            >
                              &bull; {cp}
                            </li>
                          )
                        )}
                      </ul>
                    </article>
                  )}

                  {renderedActorGuidance.revealWhenAsked.length > 0 && (
                    <article className="rounded-lg border border-border bg-muted/10 p-4">
                      <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
                        Nur auf Nachfrage preisgeben
                      </h3>
                      <ul className="mt-2 space-y-1">
                        {renderedActorGuidance.revealWhenAsked.map(
                          (item, i) => (
                            <li
                              key={i}
                              className="text-sm text-muted-foreground"
                            >
                              &bull; {item}
                            </li>
                          )
                        )}
                      </ul>
                    </article>
                  )}
                </div>
              )}

              <article className="rounded-lg border border-border bg-muted/10 p-4">
                <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  Erste Dialogschritte
                </h3>
                <div className="mt-3 space-y-2">
                  {renderedConversation.slice(0, 3).map((step) => (
                    <p key={step.id} className="text-sm">
                      {renderScenarioText(step.customerMsg, selectedCustomer)}
                    </p>
                  ))}
                </div>
              </article>

              <div className="grid gap-3 md:grid-cols-2">
                <button
                  onClick={() => setPrepStage("selection")}
                  className="rounded-md border border-border px-4 py-3 text-sm font-medium hover:bg-muted/30"
                >
                  Zurück zur Auswahl
                </button>
                <button
                  onClick={handleStartCall}
                  disabled={isLoading}
                  className="rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {isLoading ? "Anruf wird gestartet..." : "Anruf starten"}
                </button>
              </div>
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
          <section className="space-y-6">
            <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
              Agent hat den Anruf angenommen. Folgen Sie dem Skript unten.
            </div>

            {sessionId && (
              <p className="text-xs text-muted-foreground">
                Sitzung: {sessionId.slice(0, 8)}...
              </p>
            )}

            {renderedActorGuidance && (
              <div className="rounded-lg border border-border bg-muted/10 p-4">
                <button
                  onClick={() => setShowActorReference((v) => !v)}
                  className="flex w-full items-center justify-between text-left"
                >
                  <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
                    Schauspieler-Referenz
                  </h3>
                  <span className="text-xs text-muted-foreground">
                    {showActorReference ? "Ausblenden" : "Anzeigen"}
                  </span>
                </button>

                {showActorReference && (
                  <div className="mt-3 grid gap-4 md:grid-cols-2">
                    {renderedActorGuidance.mustAskCheckpoints.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium uppercase text-muted-foreground">
                          Pflicht-Checkpoints
                        </h4>
                        <ul className="mt-1 space-y-1">
                          {renderedActorGuidance.mustAskCheckpoints.map(
                            (cp, i) => (
                              <li key={i} className="flex items-start gap-2">
                                <button
                                  onClick={() => toggleCheckpoint(cp)}
                                  className={`mt-0.5 h-4 w-4 shrink-0 rounded border ${
                                    completedCheckpoints.has(cp)
                                      ? "border-success bg-success/20"
                                      : "border-border"
                                  }`}
                                />
                                <span
                                  className={`text-sm ${
                                    completedCheckpoints.has(cp)
                                      ? "text-muted-foreground line-through"
                                      : ""
                                  }`}
                                >
                                  {cp}
                                </span>
                              </li>
                            )
                          )}
                        </ul>
                      </div>
                    )}

                    {renderedActorGuidance.revealWhenAsked.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium uppercase text-muted-foreground">
                          Nur auf Nachfrage preisgeben
                        </h4>
                        <ul className="mt-1 space-y-1">
                          {renderedActorGuidance.revealWhenAsked.map(
                            (item, i) => (
                              <li
                                key={i}
                                className="text-sm text-muted-foreground"
                              >
                                &bull; {item}
                              </li>
                            )
                          )}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            <div className="space-y-3">
              {renderedConversation.map((step) => {
                const done = completedSteps.has(step.id);
                return (
                  <article
                    key={step.id}
                    className={`rounded-lg border px-4 py-3 ${
                      done
                        ? "border-success/40 bg-success/5"
                        : "border-border bg-muted/10"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <p className="text-sm font-medium">
                          {step.customerMsg}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Absicht: {step.actorIntent}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Ton: {step.tone}
                        </p>
                      </div>
                      <button
                        onClick={() => toggleStepCompleted(step)}
                        className="rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted/30"
                      >
                        {done ? "Rückgängig" : "Erledigt"}
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>

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
