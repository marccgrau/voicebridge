import { describe, it, expect } from "vitest";
import {
  TranscriptSegmentEventSchema,
  AdviceItemSchema,
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

  describe("AdviceItemSchema", () => {
    it("validates a valid advice item", () => {
      const item = {
        id: "123e4567-e89b-12d3-a456-426614174002",
        text: "Bestätigen Sie das Anliegen des Kunden.",
      };

      const result = AdviceItemSchema.safeParse(item);
      expect(result.success).toBe(true);
    });

    it("rejects missing text", () => {
      const item = {
        id: "123e4567-e89b-12d3-a456-426614174002",
      };

      const result = AdviceItemSchema.safeParse(item);
      expect(result.success).toBe(false);
    });

    it("rejects invalid id", () => {
      const item = {
        id: "not-a-uuid",
        text: "Some advice",
      };

      const result = AdviceItemSchema.safeParse(item);
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
    it("validates a valid RTVI suggestion message with advice", () => {
      const message = {
        action: "agent_guidance" as const,
        data: {
          advice: [
            {
              id: "123e4567-e89b-12d3-a456-426614174002",
              text: "Bestätigen Sie das Anliegen des Kunden.",
            },
          ],
          serviceType: "suggestion_agent" as const,
          latencyMs: 150,
        },
      };

      const result = RTVISuggestionMessageSchema.safeParse(message);
      expect(result.success).toBe(true);
    });

    it("rejects invalid serviceType", () => {
      const message = {
        action: "agent_guidance" as const,
        data: {
          advice: [],
          serviceType: "simple_turn",
        },
      };

      const result = RTVISuggestionMessageSchema.safeParse(message);
      expect(result.success).toBe(false);
    });
  });

  describe("RTVIProcessIllustrationMessageSchema", () => {
    it("validates a valid RTVI process illustration message", () => {
      const message = {
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
        action: "agent_guidance" as const,
        data: {
          advice: [
            {
              id: "123e4567-e89b-12d3-a456-426614174002",
              text: "Fragen Sie nach der Transaktionsnummer.",
            },
          ],
          serviceType: "suggestion_agent" as const,
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
