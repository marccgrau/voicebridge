"use client";

import type { ProcessStep } from "@voicebridge/contracts";
import type { UIPhase } from "@/lib/use-phase";

interface ProcessLayerProps {
  processKey: string | null;
  processName: string | null;
  currentStep: string | null;
  steps: ProcessStep[];
  phase: UIPhase;
}

export function ProcessLayer({
  processKey,
  processName,
  currentStep,
  steps,
  phase,
}: ProcessLayerProps) {
  if (phase === "idle") return null;

  const hasProcess = processKey !== null;

  return (
    <div className="panel-morph mx-5 mt-3 rounded-2xl border border-border bg-white px-5 py-3 shadow-card">
      {!hasProcess ? (
        <div className="flex items-center gap-3">
          <span className="h-2 w-2 animate-pulse-dot rounded-full bg-accent" />
          <span className="text-sm text-muted-foreground">
            Prozesserkennung läuft...
          </span>
        </div>
      ) : (
        <div className="flex items-center gap-4">
          <span className="font-display text-sm font-semibold text-foreground">
            {processName}
          </span>
          {/* Step track with connecting line */}
          <div className="relative flex items-center gap-1.5">
            {/* Connecting track line */}
            <div className="absolute top-1/2 left-0 right-0 h-px -translate-y-1/2 bg-border" />
            {steps.map((step) => (
              <StepPill
                key={step.key}
                step={step}
                isCurrent={step.key === currentStep}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StepPill({
  step,
  isCurrent,
}: {
  step: ProcessStep;
  isCurrent: boolean;
}) {
  const statusStyles: Record<ProcessStep["status"], string> = {
    pending: "bg-muted text-muted-foreground border border-border",
    in_progress:
      "gradient-accent text-white ring-2 ring-accent/25 shadow-accent",
    completed: "bg-accent text-white",
    skipped: "bg-muted text-muted-foreground/50 line-through opacity-60",
  };

  return (
    <span
      className={`relative z-10 inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
        statusStyles[step.status]
      } ${isCurrent ? "scale-105" : ""}`}
      title={step.label}
    >
      {step.status === "completed" && (
        <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
            clipRule="evenodd"
          />
        </svg>
      )}
      {step.status === "in_progress" && (
        <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-white" />
      )}
      {step.label}
    </span>
  );
}
