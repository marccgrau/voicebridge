"use client";

import { useMemo, useState } from "react";
import type { ScenarioConversationStep } from "@voicebridge/contracts";

import { useCustomerSession } from "@/lib/customer-session";
import { useDailyAudio } from "@/lib/daily-audio";
import {
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

  const renderedConversation = useMemo(() => {
    if (!selectedCustomer || !selectedScenario) {
      return [];
    }

    return renderScenarioConversation(selectedScenario, selectedCustomer);
  }, [selectedCustomer, selectedScenario]);

  const canContinue = Boolean(selectedCustomer && selectedScenario);

  const handleStartCall = async () => {
    if (!selectedCustomer || !selectedScenario) {
      return;
    }

    setCompletedSteps(new Set());
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

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-8">
      <div className="w-full max-w-5xl rounded-xl border border-border bg-card p-6 md:p-8">
        <header className="mb-6 border-b border-border pb-4 text-center">
          <h1 className="text-2xl font-semibold">VoiceBridge Experiment</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Customer role interface
          </p>
        </header>

        {error && (
          <div className="mb-4 rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {scenarioError && (
          <div className="mb-4 rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive">
            Failed to load scenarios: {scenarioError}
          </div>
        )}

        {callState === "idle" && prepStage === "selection" && (
          <section className="grid gap-6 md:grid-cols-2">
            <div className="space-y-4">
              <h2 className="text-lg font-medium">1. Select persona</h2>
              <select
                value={selectedCustomerId}
                onChange={(event) => setSelectedCustomerId(event.target.value)}
                disabled={isLoadingCustomers}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">Choose persona...</option>
                {customers.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name} ({customer.classification})
                  </option>
                ))}
              </select>
              {selectedCustomer && (
                <p className="text-sm text-muted-foreground">
                  {selectedCustomer.quickInternalNote ?? selectedCustomer.notes}
                </p>
              )}
            </div>

            <div className="space-y-4">
              <h2 className="text-lg font-medium">2. Select scenario</h2>
              <select
                value={selectedScenarioId}
                onChange={(event) => setSelectedScenarioId(event.target.value)}
                disabled={isLoadingScenarios}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">Choose scenario...</option>
                {scenarios.map((scenario) => (
                  <option key={scenario.scenarioId} value={scenario.scenarioId}>
                    {scenario.title}
                  </option>
                ))}
              </select>
              {selectedScenario && (
                <p className="text-sm text-muted-foreground">
                  {selectedScenario.behavioralCondition.civilityCondition.toUpperCase()}{" "}
                  condition
                </p>
              )}
            </div>

            <div className="md:col-span-2">
              <button
                onClick={() => setPrepStage("briefing")}
                disabled={!canContinue || isLoading}
                className="w-full rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                Continue to briefing
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
                  <h2 className="text-base font-medium">Persona briefing</h2>
                  <p className="mt-2 text-sm">{selectedCustomer.name}</p>
                  <p className="text-sm text-muted-foreground">
                    Customer code: {selectedCustomer.customerCode ?? "N/A"}
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {selectedCustomer.quickInternalNote ??
                      selectedCustomer.notes}
                  </p>
                </article>

                <article className="rounded-lg border border-border bg-muted/20 p-4">
                  <h2 className="text-base font-medium">Scenario briefing</h2>
                  <p className="mt-2 text-sm">{selectedScenario.background}</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Goal: {selectedScenario.customerGoal}
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Tone instruction:{" "}
                    {selectedScenario.behavioralCondition.instruction}
                  </p>
                </article>
              </div>

              <article className="rounded-lg border border-border bg-muted/10 p-4">
                <h3 className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  First scripted turns
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
                  Back to selection
                </button>
                <button
                  onClick={handleStartCall}
                  disabled={isLoading}
                  className="rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {isLoading ? "Starting call..." : "Start Call"}
                </button>
              </div>
            </section>
          )}

        {callState === "calling" && (
          <section className="space-y-4 text-center">
            <span className="mx-auto block h-4 w-4 animate-pulse rounded-full bg-primary" />
            <p className="text-muted-foreground">
              {isAudioConnected
                ? "Connected. Waiting for an agent to accept..."
                : "Connecting to room..."}
            </p>
            {sessionId && (
              <p className="text-xs text-muted-foreground">
                Session: {sessionId.slice(0, 8)}...
              </p>
            )}
            <button
              onClick={endCall}
              disabled={isLoading}
              className="w-full rounded-md bg-destructive px-4 py-3 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
            >
              Cancel
            </button>
          </section>
        )}

        {callState === "connected" && (
          <section className="space-y-6">
            <div className="rounded-lg border border-success/40 bg-success/10 px-4 py-3 text-sm text-success">
              Agent accepted the call. Follow your script below.
            </div>

            {sessionId && (
              <p className="text-xs text-muted-foreground">
                Session: {sessionId.slice(0, 8)}...
              </p>
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
                          Intent: {step.actorIntent}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Tone: {step.tone}
                        </p>
                      </div>
                      <button
                        onClick={() => toggleStepCompleted(step)}
                        className="rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted/30"
                      >
                        {done ? "Undo" : "Mark done"}
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
              End Call
            </button>
          </section>
        )}

        {callState === "ended" && (
          <section className="space-y-4 text-center">
            <p className="text-muted-foreground">Call ended. Thank you!</p>
            <button
              onClick={() => window.location.reload()}
              className="w-full rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Start New Call
            </button>
          </section>
        )}
      </div>
    </div>
  );
}
