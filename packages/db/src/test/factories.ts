/**
 * Test data factories for database package tests
 */

import type { SessionConfig } from "@voicebridge/contracts";
import type { SessionRow } from "../queries/sessions.js";
import type {
  CustomerRow,
  CustomerInteractionRow,
} from "../queries/customers.js";

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

/**
 * Create a customer row for testing
 */
export function createCustomerRow(
  overrides?: Partial<CustomerRow>
): CustomerRow {
  const now = new Date().toISOString();
  return {
    id: overrides?.id ?? crypto.randomUUID(),
    customer_code: overrides?.customer_code ?? null,
    name: overrides?.name ?? "Test Customer",
    gender: overrides?.gender ?? "male",
    date_of_birth: overrides?.date_of_birth ?? null,
    email: overrides?.email ?? "test@example.com",
    phone: overrides?.phone ?? "+41 79 123 4567",
    address_street: overrides?.address_street ?? null,
    address_postal_code: overrides?.address_postal_code ?? null,
    address_city: overrides?.address_city ?? null,
    address_country: overrides?.address_country ?? null,
    customer_since: overrides?.customer_since ?? "2023-01-01",
    classification: overrides?.classification ?? "basis",
    products: overrides?.products ?? ["Savings Account"],
    preferred_language: overrides?.preferred_language ?? "en",
    preferred_contact_channel: overrides?.preferred_contact_channel ?? null,
    notes: overrides?.notes ?? null,
    quick_internal_note: overrides?.quick_internal_note ?? null,
    created_at: overrides?.created_at ?? now,
    updated_at: overrides?.updated_at ?? now,
  };
}

/**
 * Create a customer interaction row for testing
 */
export function createCustomerInteractionRow(
  overrides?: Partial<CustomerInteractionRow>
): CustomerInteractionRow {
  return {
    id: overrides?.id ?? crypto.randomUUID(),
    customer_id: overrides?.customer_id ?? crypto.randomUUID(),
    type: overrides?.type ?? "phone",
    date: overrides?.date ?? new Date().toISOString(),
    summary: overrides?.summary ?? "Test interaction summary",
    outcome: overrides?.outcome ?? "Resolved",
    agent_name: overrides?.agent_name ?? "Test Agent",
    channel_detail: overrides?.channel_detail ?? null,
    direction: overrides?.direction ?? null,
    topic: overrides?.topic ?? null,
    subtopic: overrides?.subtopic ?? null,
    sentiment: overrides?.sentiment ?? null,
    priority: overrides?.priority ?? null,
    owner_team: overrides?.owner_team ?? null,
    status: overrides?.status ?? null,
    resolution_time_hours: overrides?.resolution_time_hours ?? null,
    sla_breached: overrides?.sla_breached ?? null,
    follow_up_required: overrides?.follow_up_required ?? null,
    related_case_id: overrides?.related_case_id ?? null,
    csat: overrides?.csat ?? null,
    created_at: overrides?.created_at ?? new Date().toISOString(),
  };
}
