"use client";

import type { ProcessStep } from "@voicebridge/contracts";

interface ProcessStatusPanelProps {
  processKey: string | null;
  processName: string | null;
  currentStep: string | null;
  steps: ProcessStep[];
  slots: Record<string, string>;
}

export function ProcessStatusPanel({
  processKey,
  processName,
  currentStep,
  steps,
  slots,
}: ProcessStatusPanelProps) {
  const hasProcess = processKey !== null;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/60 px-5 py-4">
        <span className="font-mono-ui flex items-center gap-2 text-sm uppercase tracking-wide text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Process Status
        </span>
        {hasProcess && (
          <span className="rounded-lg bg-success/10 px-2.5 py-1 text-sm font-medium text-success">
            Active
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {!hasProcess ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">
              Process will be detected from the conversation
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Process Info */}
            <div>
              <div className="rounded-xl border border-accent/20 bg-accent/5 p-5">
                <p className="text-lg font-semibold text-foreground">
                  {processName}
                </p>
              </div>
            </div>

            {/* Steps Checklist */}
            {steps.length > 0 && (
              <div>
                <h3 className="mb-3 text-sm font-medium text-muted-foreground">
                  Steps
                </h3>
                <div className="relative space-y-2 pl-6">
                  {/* Vertical timeline line */}
                  <div className="absolute left-2.5 top-2 bottom-2 w-0.5 bg-border" />
                  {steps.map((step) => (
                    <StepItem
                      key={step.key}
                      step={step}
                      isCurrent={step.key === currentStep}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Extracted Slots */}
            {Object.keys(slots).length > 0 && (
              <div>
                <h3 className="mb-3 text-sm font-medium text-muted-foreground">
                  Extracted Information
                </h3>
                <div className="space-y-1.5">
                  {Object.entries(slots).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex items-center justify-between rounded-lg bg-muted px-3 py-2 text-sm"
                    >
                      <span className="text-muted-foreground">
                        {formatSlotKey(key)}
                      </span>
                      <span className="font-medium">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface StepItemProps {
  step: ProcessStep;
  isCurrent: boolean;
}

function StepItem({ step, isCurrent }: StepItemProps) {
  const statusStyles: Record<ProcessStep["status"], string> = {
    pending: "bg-muted text-muted-foreground",
    in_progress: "bg-accent text-white ring-2 ring-accent/20",
    completed: "bg-success text-white",
    skipped: "bg-muted text-muted-foreground",
  };

  return (
    <div
      className={`relative flex items-center gap-3 rounded-lg p-2.5 transition-all ${
        isCurrent ? "bg-accent/5" : ""
      }`}
    >
      <div
        className={`z-10 flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
          statusStyles[step.status]
        } ${step.status === "in_progress" ? "animate-pulse-dot" : ""}`}
      >
        {step.status === "completed" ? (
          <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
        ) : step.status === "in_progress" ? (
          <span className="h-2 w-2 rounded-full bg-white" />
        ) : (
          <span className="h-2 w-2 rounded-full bg-current opacity-50" />
        )}
      </div>
      <span
        className={`text-sm ${step.status === "skipped" ? "line-through opacity-50" : ""}`}
      >
        {step.label}
      </span>
    </div>
  );
}

function formatSlotKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
