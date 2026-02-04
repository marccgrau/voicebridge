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
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="font-semibold">Process Status</h2>
        {hasProcess && (
          <span className="rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
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
              <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                Current Process
              </h3>
              <div className="rounded-lg bg-muted p-3">
                <p className="font-medium">{processName}</p>
                <p className="text-xs text-muted-foreground">{processKey}</p>
              </div>
            </div>

            {/* Steps Checklist */}
            {steps.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                  Steps
                </h3>
                <div className="space-y-2">
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
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                  Extracted Information
                </h3>
                <div className="space-y-1">
                  {Object.entries(slots).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex items-center justify-between rounded-md bg-muted px-3 py-2 text-sm"
                    >
                      <span className="text-muted-foreground">{formatSlotKey(key)}</span>
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
    in_progress: "bg-warning/20 text-warning border border-warning",
    completed: "bg-success/20 text-success",
    skipped: "bg-muted text-muted-foreground line-through",
  };

  const statusIcons: Record<ProcessStep["status"], string> = {
    pending: "○",
    in_progress: "◐",
    completed: "●",
    skipped: "○",
  };

  return (
    <div
      className={`flex items-center gap-3 rounded-md p-2 ${
        isCurrent ? "bg-primary/10 ring-1 ring-primary/20" : ""
      }`}
    >
      <span
        className={`flex h-5 w-5 items-center justify-center rounded-full text-xs ${
          statusStyles[step.status]
        }`}
      >
        {statusIcons[step.status]}
      </span>
      <span className={`text-sm ${step.status === "skipped" ? "line-through opacity-50" : ""}`}>
        {step.label}
      </span>
    </div>
  );
}

function formatSlotKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
