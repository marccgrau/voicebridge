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
 * Individual suggestion (used in RTVI messages)
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
 * Process step status (used in RTVI messages)
 */
export const ProcessStepSchema = z.object({
  key: z.string(),
  label: z.string(),
  status: z.enum(["pending", "in_progress", "completed", "skipped"]),
  completedAt: z.string().datetime().optional(),
});

export type ProcessStep = z.infer<typeof ProcessStepSchema>;

/**
 * RTVI message schemas for low-latency delivery via WebRTC data channel
 */

/**
 * RTVI suggestion message
 */
export const RTVISuggestionMessageSchema = z.object({
  type: z.literal("bot-action"),
  action: z.literal("agent_guidance"),
  data: z.object({
    suggestions: z.array(SuggestionSchema),
    serviceType: z.enum(["simple_turn", "tool_agent"]),
    triggerTurn: z.string().optional(),
    latencyMs: z.number().optional(),
    processKey: z.string().optional(),
    toolsUsed: z.array(z.string()).optional(),
  }),
});

export type RTVISuggestionMessage = z.infer<typeof RTVISuggestionMessageSchema>;

/**
 * RTVI process illustration message
 */
export const RTVIProcessIllustrationMessageSchema = z.object({
  type: z.literal("bot-action"),
  action: z.literal("process_illustration"),
  data: z.object({
    processKey: z.string(),
    processName: z.string(),
    steps: z.array(
      z.object({
        key: z.string(),
        label: z.string(),
        status: z.enum(["pending", "in_progress", "completed", "skipped"]),
      })
    ),
    currentStep: z.number(),
    content: z.string(),
  }),
});

export type RTVIProcessIllustrationMessage = z.infer<typeof RTVIProcessIllustrationMessageSchema>;

/**
 * Union of all RTVI message types
 */
export const RTVIMessageSchema = z.discriminatedUnion("action", [
  RTVISuggestionMessageSchema,
  RTVIProcessIllustrationMessageSchema,
]);

export type RTVIMessage = z.infer<typeof RTVIMessageSchema>;
