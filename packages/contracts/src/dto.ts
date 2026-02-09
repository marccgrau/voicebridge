import { z } from "zod";
import { ProcessStepSchema } from "./events.js";

/**
 * Process candidate returned from lookup
 */
export const ProcessCandidateSchema = z.object({
  processKey: z.string(),
  name: z.string(),
  domain: z.string(),
  score: z.number(),
  snippet: z.string().optional(),
});

export type ProcessCandidate = z.infer<typeof ProcessCandidateSchema>;

/**
 * Process lookup input for the skill
 */
export const ProcessLookupInputSchema = z.object({
  query: z.string().min(1),
  locale: z.string().default("en"),
  domain: z.string().optional(),
  queueTag: z.string().optional(),
  limit: z.number().int().min(1).max(10).default(5),
});

export type ProcessLookupInput = z.infer<typeof ProcessLookupInputSchema>;

/**
 * Process lookup output from the skill
 */
export const ProcessLookupOutputSchema = z.object({
  results: z.array(
    z.object({
      processKey: z.string(),
      name: z.string(),
      domain: z.string(),
      version: z.string(),
      score: z.number(),
      processText: z.string(),
      stepsJson: z.unknown().optional(),
    })
  ),
  queryTime: z.number(),
});

export type ProcessLookupOutput = z.infer<typeof ProcessLookupOutputSchema>;

/**
 * Process selection result from LLM
 */
export const ProcessSelectionResultSchema = z.object({
  processKey: z.string(),
  processName: z.string(),
  confidence: z.number().min(0).max(1),
  rationale: z.string(),
  candidates: z.array(ProcessCandidateSchema),
});

export type ProcessSelectionResult = z.infer<
  typeof ProcessSelectionResultSchema
>;

/**
 * Session configuration for starting a new session
 */
export const SessionConfigSchema = z.object({
  sessionId: z.string().uuid().optional(),
  locale: z.string().default("en"),
  domain: z.string().optional(),
  queueTag: z.string().optional(),
  agentId: z.string().optional(),
  customerId: z.string().optional(),
  metadata: z.record(z.unknown()).optional(),
  // NEW: Service selection
  suggestionService: z
    .enum(["simple_turn", "tool_agent", "split_flows"])
    .default("split_flows"),
  processIllustrationEnabled: z.boolean().default(true),
  processContentPath: z.string().optional(),
});

export type SessionConfig = z.infer<typeof SessionConfigSchema>;

/**
 * Session start response
 */
export const SessionStartResponseSchema = z.object({
  sessionId: z.string().uuid(),
  roomUrl: z.string().url(),
  roomToken: z.string(),
  createdAt: z.string().datetime(),
  // NEW: RTVI connection info
  rtviUrl: z.string().url(),
  services: z.object({
    suggestionService: z.enum(["simple_turn", "tool_agent"]),
    processIllustrationEnabled: z.boolean(),
  }),
});

export type SessionStartResponse = z.infer<typeof SessionStartResponseSchema>;

/**
 * Session stop response
 */
export const SessionStopResponseSchema = z.object({
  sessionId: z.string().uuid(),
  stoppedAt: z.string().datetime(),
  duration: z.number(),
  status: z.enum(["completed", "abandoned", "escalated", "pending", "error"]),
});

export type SessionStopResponse = z.infer<typeof SessionStopResponseSchema>;

/**
 * Full session state for UI
 */
export const SessionStateSchema = z.object({
  sessionId: z.string().uuid(),
  processKey: z.string().nullable(),
  processName: z.string().nullable(),
  currentStep: z.string().nullable(),
  steps: z.array(ProcessStepSchema),
  slots: z.record(z.string()),
  status: z.enum([
    "pending",
    "active",
    "completed",
    "abandoned",
    "escalated",
    "error",
  ]),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

export type SessionState = z.infer<typeof SessionStateSchema>;

/**
 * Transcript entry for history
 */
export const TranscriptEntrySchema = z.object({
  id: z.string().uuid(),
  speaker: z.enum(["agent", "customer"]),
  text: z.string(),
  timestamp: z.string().datetime(),
  isFinal: z.boolean(),
});

export type TranscriptEntry = z.infer<typeof TranscriptEntrySchema>;

/**
 * Suggestion feedback from agent
 */
export const SuggestionFeedbackSchema = z.object({
  sessionId: z.string().uuid(),
  suggestionId: z.string().uuid(),
  action: z.enum(["used", "modified", "dismissed"]),
  modifiedText: z.string().optional(),
  timestamp: z.string().datetime(),
});

export type SuggestionFeedback = z.infer<typeof SuggestionFeedbackSchema>;

/**
 * UI preferences
 */
export const UIPreferencesSchema = z.object({
  panelLayout: z.enum(["default", "compact", "expanded"]).default("default"),
  showConfidence: z.boolean().default(true),
  autoScroll: z.boolean().default(true),
  suggestionCount: z.number().int().min(1).max(6).default(3),
  theme: z.enum(["light", "dark", "system"]).default("system"),
});

export type UIPreferences = z.infer<typeof UIPreferencesSchema>;

/**
 * Health check response
 */
export const HealthCheckResponseSchema = z.object({
  status: z.enum(["healthy", "degraded", "unhealthy"]),
  version: z.string(),
  uptime: z.number(),
  services: z.object({
    database: z.enum(["up", "down"]),
    stt: z.enum(["up", "down"]),
    llm: z.enum(["up", "down"]),
    daily: z.enum(["up", "down"]),
  }),
});

export type HealthCheckResponse = z.infer<typeof HealthCheckResponseSchema>;

/**
 * KB snippet for suggestions
 */
export const KBSnippetSchema = z.object({
  id: z.string().uuid(),
  processKey: z.string(),
  stepKey: z.string().optional(),
  intentKey: z.string().optional(),
  template: z.string(),
  constraints: z.record(z.unknown()).optional(),
});

export type KBSnippet = z.infer<typeof KBSnippetSchema>;

/**
 * Process definition from catalog
 */
export const ProcessDefinitionSchema = z.object({
  processKey: z.string(),
  name: z.string(),
  domain: z.string(),
  queueTag: z.string().optional(),
  locale: z.string(),
  version: z.string(),
  status: z.enum(["active", "inactive"]),
  processText: z.string(),
  stepsJson: z
    .array(
      z.object({
        key: z.string(),
        label: z.string(),
        description: z.string().optional(),
        requiredSlots: z.array(z.string()).optional(),
      })
    )
    .optional(),
  updatedAt: z.string().datetime(),
});

export type ProcessDefinition = z.infer<typeof ProcessDefinitionSchema>;

/**
 * Customer classification levels
 */
export const CustomerClassificationSchema = z.enum([
  "basis",
  "affluent",
  "HNWI",
  "UHNWI",
]);

export type CustomerClassification = z.infer<
  typeof CustomerClassificationSchema
>;

/**
 * Customer profile
 */
export const CustomerSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  gender: z.enum(["male", "female", "other"]),
  email: z.string().email().nullable(),
  phone: z.string().nullable(),
  customerSince: z.string(), // Date string
  classification: CustomerClassificationSchema,
  products: z.array(z.string()),
  preferredLanguage: z.string(),
  notes: z.string().nullable(),
});

export type Customer = z.infer<typeof CustomerSchema>;

/**
 * Customer interaction types
 */
export const CustomerInteractionTypeSchema = z.enum([
  "phone",
  "chat",
  "branch_visit",
  "email",
]);

export type CustomerInteractionType = z.infer<
  typeof CustomerInteractionTypeSchema
>;

/**
 * Customer interaction record
 */
export const CustomerInteractionSchema = z.object({
  id: z.string().uuid(),
  customerId: z.string().uuid(),
  type: CustomerInteractionTypeSchema,
  date: z.string().datetime(),
  summary: z.string(),
  outcome: z.string().nullable(),
  agentName: z.string().nullable(),
  channelDetail: z.string().nullable(),
});

export type CustomerInteraction = z.infer<typeof CustomerInteractionSchema>;

/**
 * Customer-initiated session creation request
 */
export const SessionCreateRequestSchema = z.object({
  locale: z.string().default("en"),
  domain: z.string().optional(),
  metadata: z.record(z.unknown()).optional(),
  customerId: z.string().uuid().optional(),
});

export type SessionCreateRequest = z.infer<typeof SessionCreateRequestSchema>;

/**
 * Customer-initiated session creation response
 */
export const SessionCreateResponseSchema = z.object({
  sessionId: z.string().uuid(),
  roomUrl: z.string().url(),
  customerToken: z.string(),
});

export type SessionCreateResponse = z.infer<typeof SessionCreateResponseSchema>;

/**
 * Agent accepts a pending session
 */
export const SessionAcceptRequestSchema = z.object({
  sessionId: z.string().uuid(),
  enableProcessFlow: z.boolean().default(true),
  enableSuggestionFlow: z.boolean().default(true),
  processFlowModel: z.string().default("claude-3-5-haiku-20241022"),
  suggestionFlowModel: z.string().default("claude-sonnet-4-20250514"),
  processContentPath: z.string().optional(),
});

export type SessionAcceptRequest = z.infer<typeof SessionAcceptRequestSchema>;

/**
 * Agent accept session response
 */
export const SessionAcceptResponseSchema = z.object({
  sessionId: z.string().uuid(),
  roomUrl: z.string().url(),
  agentToken: z.string(),
  rtviUrl: z.string().url(),
  services: z.object({
    processFlowEnabled: z.boolean(),
    suggestionFlowEnabled: z.boolean(),
  }),
});

export type SessionAcceptResponse = z.infer<typeof SessionAcceptResponseSchema>;
