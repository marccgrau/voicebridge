import { z } from "zod";

/**
 * Base event schema with common fields
 */
export const BaseEventSchema = z.object({
  eventId: z.string().uuid(),
  sessionId: z.string().uuid(),
  timestamp: z.string().datetime(),
});

export type BaseEvent = z.infer<typeof BaseEventSchema>;

/**
 * Transcript segment from STT
 */
export const TranscriptSegmentEventSchema = BaseEventSchema.extend({
  type: z.literal("transcript_segment"),
  speaker: z.enum(["agent", "customer"]),
  text: z.string(),
  isFinal: z.boolean(),
  confidence: z.number().min(0).max(1).optional(),
  startTime: z.number().optional(),
  endTime: z.number().optional(),
});

export type TranscriptSegmentEvent = z.infer<typeof TranscriptSegmentEventSchema>;

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
 * Process selection event from LLM
 */
export const ProcessSelectionEventSchema = BaseEventSchema.extend({
  type: z.literal("process_selection"),
  processKey: z.string(),
  processName: z.string(),
  confidence: z.number().min(0).max(1),
  rationale: z.string(),
  candidates: z.array(ProcessCandidateSchema),
  triggerText: z.string().optional(),
});

export type ProcessSelectionEvent = z.infer<typeof ProcessSelectionEventSchema>;

/**
 * Extracted slot from conversation
 */
export const ExtractedSlotSchema = z.object({
  key: z.string(),
  value: z.string(),
  confidence: z.number().min(0).max(1).optional(),
  source: z.enum(["customer", "agent", "inferred"]).optional(),
});

export type ExtractedSlot = z.infer<typeof ExtractedSlotSchema>;

/**
 * Slot extraction event
 */
export const SlotExtractionEventSchema = BaseEventSchema.extend({
  type: z.literal("slot_extraction"),
  intent: z.string().optional(),
  slots: z.array(ExtractedSlotSchema),
  processKey: z.string().optional(),
});

export type SlotExtractionEvent = z.infer<typeof SlotExtractionEventSchema>;

/**
 * Individual suggestion
 */
export const SuggestionSchema = z.object({
  id: z.string().uuid(),
  text: z.string(),
  type: z.enum(["response", "question", "action", "escalation"]),
  confidence: z.number().min(0).max(1).optional(),
  source: z.enum(["template", "llm", "hybrid"]).optional(),
  metadata: z.record(z.unknown()).optional(),
});

export type Suggestion = z.infer<typeof SuggestionSchema>;

/**
 * Suggestion event with multiple candidates
 */
export const SuggestionEventSchema = BaseEventSchema.extend({
  type: z.literal("suggestion"),
  suggestions: z.array(SuggestionSchema).min(1).max(6),
  processKey: z.string().optional(),
  stepKey: z.string().optional(),
});

export type SuggestionEvent = z.infer<typeof SuggestionEventSchema>;

/**
 * Process step status
 */
export const ProcessStepSchema = z.object({
  key: z.string(),
  label: z.string(),
  status: z.enum(["pending", "in_progress", "completed", "skipped"]),
  completedAt: z.string().datetime().optional(),
});

export type ProcessStep = z.infer<typeof ProcessStepSchema>;

/**
 * Session state event
 */
export const SessionStateEventSchema = BaseEventSchema.extend({
  type: z.literal("session_state"),
  processKey: z.string().nullable(),
  processName: z.string().nullable(),
  currentStep: z.string().nullable(),
  steps: z.array(ProcessStepSchema),
  slots: z.record(z.string()),
  status: z.enum(["active", "completed", "abandoned", "escalated"]),
});

export type SessionStateEvent = z.infer<typeof SessionStateEventSchema>;

/**
 * Union of all event types
 */
export const VoiceBridgeEventSchema = z.discriminatedUnion("type", [
  TranscriptSegmentEventSchema,
  ProcessSelectionEventSchema,
  SlotExtractionEventSchema,
  SuggestionEventSchema,
  SessionStateEventSchema,
]);

export type VoiceBridgeEvent = z.infer<typeof VoiceBridgeEventSchema>;

/**
 * Event type constants
 */
export const EVENT_TYPES = {
  TRANSCRIPT_SEGMENT: "transcript_segment",
  PROCESS_SELECTION: "process_selection",
  SLOT_EXTRACTION: "slot_extraction",
  SUGGESTION: "suggestion",
  SESSION_STATE: "session_state",
} as const;
