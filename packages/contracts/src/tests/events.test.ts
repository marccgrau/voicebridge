import { describe, it, expect } from "vitest";
import {
  TranscriptSegmentEventSchema,
  SuggestionSchema,
  ProcessStepSchema,
  RTVISuggestionMessageSchema,
  RTVIProcessIllustrationMessageSchema,
  RTVIMessageSchema,
} from "../events.js";

describe("Event Schemas", () => {
  const baseEvent = {
    eventId: "123e4567-e89b-12d3-a456-426614174000",
    sessionId: "123e4567-e89b-12d3-a456-426614174001",
    timestamp: "2024-01-15T10:30:00.000Z",
  };

  describe("TranscriptSegmentEventSchema", () => {
    it("validates a valid transcript segment event", () => {
      const event = {
        ...baseEvent,
        type: "transcript_segment" as const,
        speaker: "customer" as const,
        text: "I need help with my order",
        isFinal: true,
        confidence: 0.95,
      };

      const result = TranscriptSegmentEventSchema.safeParse(event);
      expect(result.success).toBe(true);
    });

    it("rejects invalid speaker", () => {
      const event = {
        ...baseEvent,
        type: "transcript_segment" as const,
        speaker: "unknown",
        text: "Test",
        isFinal: true,
      };

      const result = TranscriptSegmentEventSchema.safeParse(event);
      expect(result.success).toBe(false);
    });
  });

  describe("SuggestionSchema", () => {
    it("validates a valid suggestion", () => {
      const suggestion = {
        id: "123e4567-e89b-12d3-a456-426614174002",
        text: "I can help you with that billing issue.",
        type: "response" as const,
        confidence: 0.8,
        source: "template" as const,
      };

      const result = SuggestionSchema.safeParse(suggestion);
      expect(result.success).toBe(true);
    });

    it("rejects invalid type", () => {
      const suggestion = {
        id: "123e4567-e89b-12d3-a456-426614174002",
        text: "Test",
        type: "invalid",
      };

      const result = SuggestionSchema.safeParse(suggestion);
      expect(result.success).toBe(false);
    });
  });

  describe("ProcessStepSchema", () => {
    it("validates a valid process step", () => {
      const step = {
        key: "verify-identity",
        label: "Verify Identity",
        status: "in_progress" as const,
      };

      const result = ProcessStepSchema.safeParse(step);
      expect(result.success).toBe(true);
    });
  });

  describe("RTVISuggestionMessageSchema", () => {
    it("validates a valid RTVI suggestion message", () => {
      const message = {
        type: "bot-action" as const,
        action: "agent_guidance" as const,
        data: {
          suggestions: [
            {
              id: "123e4567-e89b-12d3-a456-426614174002",
              text: "I can help you with that.",
              type: "response" as const,
            },
          ],
          serviceType: "simple_turn" as const,
          latencyMs: 150,
        },
      };

      const result = RTVISuggestionMessageSchema.safeParse(message);
      expect(result.success).toBe(true);
    });
  });

  describe("RTVIProcessIllustrationMessageSchema", () => {
    it("validates a valid RTVI process illustration message", () => {
      const message = {
        type: "bot-action" as const,
        action: "process_illustration" as const,
        data: {
          processKey: "billing-dispute",
          processName: "Billing Dispute Resolution",
          steps: [
            {
              key: "step_1",
              label: "Verify Identity",
              status: "completed" as const,
            },
            {
              key: "step_2",
              label: "Identify Issue",
              status: "in_progress" as const,
            },
          ],
          currentStep: 1,
          content: "Process step content",
        },
      };

      const result = RTVIProcessIllustrationMessageSchema.safeParse(message);
      expect(result.success).toBe(true);
    });
  });

  describe("RTVIMessageSchema (discriminated union)", () => {
    it("correctly identifies RTVI message types", () => {
      const suggestionMessage = {
        type: "bot-action" as const,
        action: "agent_guidance" as const,
        data: {
          suggestions: [
            {
              id: "123e4567-e89b-12d3-a456-426614174002",
              text: "Test",
              type: "response" as const,
            },
          ],
          serviceType: "tool_agent" as const,
        },
      };

      const result = RTVIMessageSchema.safeParse(suggestionMessage);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.action).toBe("agent_guidance");
      }
    });
  });
});
