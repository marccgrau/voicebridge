/**
 * Test data factories for database package tests
 */

import type { SessionConfig } from "@voicebridge/contracts";
import type { SessionRow } from "../queries/sessions.js";

/**
 * Create a SessionRow for testing
 */
export function createSessionRow(overrides?: Partial<SessionRow>): SessionRow {
  const now = new Date().toISOString();
  return {
    id: overrides?.id ?? crypto.randomUUID(),
    process_key: overrides?.process_key ?? null,
    state: overrides?.state ?? {
      locale: "en",
      domain: undefined,
      queueTag: undefined,
      agentId: undefined,
      customerId: undefined,
      metadata: undefined,
      slots: {},
      steps: [],
      currentStep: null,
    },
    status: overrides?.status ?? "active",
    created_at: overrides?.created_at ?? now,
    updated_at: overrides?.updated_at ?? now,
  };
}

/**
 * Create a SessionConfig for testing
 */
export function createSessionConfig(
  overrides?: Partial<SessionConfig>
): SessionConfig {
  return {
    sessionId: overrides?.sessionId ?? crypto.randomUUID(),
    locale: overrides?.locale ?? "en",
    domain: overrides?.domain,
    queueTag: overrides?.queueTag,
    agentId: overrides?.agentId,
    customerId: overrides?.customerId,
    metadata: overrides?.metadata,
    suggestionService: overrides?.suggestionService ?? "simple_turn",
    processIllustrationEnabled: overrides?.processIllustrationEnabled ?? true,
    processContentPath: overrides?.processContentPath,
  };
}

/**
 * Create a process row for testing
 */
export interface ProcessRow {
  process_key: string;
  name: string;
  domain: string;
  queue_tag: string | null;
  locale: string;
  version: string;
  status: string;
  process_text: string;
  steps_json: unknown;
  updated_at: string;
}

export function createProcessRow(overrides?: Partial<ProcessRow>): ProcessRow {
  return {
    process_key: overrides?.process_key ?? "test-process",
    name: overrides?.name ?? "Test Process",
    domain: overrides?.domain ?? "test-domain",
    queue_tag: overrides?.queue_tag ?? null,
    locale: overrides?.locale ?? "en",
    version: overrides?.version ?? "1.0.0",
    status: overrides?.status ?? "active",
    process_text: overrides?.process_text ?? "Test process description",
    steps_json: overrides?.steps_json ?? [],
    updated_at: overrides?.updated_at ?? new Date().toISOString(),
  };
}

/**
 * Create a transcript row for testing
 */
export interface TranscriptRow {
  id: string;
  session_id: string;
  speaker: string;
  text: string;
  timestamp: string;
  is_final: boolean;
}

export function createTranscriptRow(
  overrides?: Partial<TranscriptRow>
): TranscriptRow {
  return {
    id: overrides?.id ?? crypto.randomUUID(),
    session_id: overrides?.session_id ?? crypto.randomUUID(),
    speaker: overrides?.speaker ?? "customer",
    text: overrides?.text ?? "Sample transcript text",
    timestamp: overrides?.timestamp ?? new Date().toISOString(),
    is_final: overrides?.is_final ?? true,
  };
}
