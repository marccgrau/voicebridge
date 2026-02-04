import { describe, it, expect } from "vitest";
import {
  TranscriptSegmentEventSchema,
  ProcessSelectionEventSchema,
  SlotExtractionEventSchema,
  SuggestionEventSchema,
  SessionStateEventSchema,
  VoiceBridgeEventSchema,
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

  describe("ProcessSelectionEventSchema", () => {
    it("validates a valid process selection event", () => {
      const event = {
        ...baseEvent,
        type: "process_selection" as const,
        processKey: "billing-dispute",
        processName: "Billing Dispute Resolution",
        confidence: 0.85,
        rationale: "Customer mentioned billing issue",
        candidates: [
          {
            processKey: "billing-dispute",
            name: "Billing Dispute",
            domain: "billing",
            score: 0.9,
          },
        ],
      };

      const result = ProcessSelectionEventSchema.safeParse(event);
      expect(result.success).toBe(true);
    });
  });

  describe("SlotExtractionEventSchema", () => {
    it("validates a valid slot extraction event", () => {
      const event = {
        ...baseEvent,
        type: "slot_extraction" as const,
        intent: "dispute_charge",
        slots: [
          {
            key: "amount",
            value: "$50.00",
            confidence: 0.9,
            source: "customer" as const,
          },
        ],
        processKey: "billing-dispute",
      };

      const result = SlotExtractionEventSchema.safeParse(event);
      expect(result.success).toBe(true);
    });
  });

  describe("SuggestionEventSchema", () => {
    it("validates a valid suggestion event", () => {
      const event = {
        ...baseEvent,
        type: "suggestion" as const,
        suggestions: [
          {
            id: "123e4567-e89b-12d3-a456-426614174002",
            text: "I can help you with that billing issue.",
            type: "response" as const,
            confidence: 0.8,
            source: "template" as const,
          },
        ],
        processKey: "billing-dispute",
      };

      const result = SuggestionEventSchema.safeParse(event);
      expect(result.success).toBe(true);
    });

    it("requires at least one suggestion", () => {
      const event = {
        ...baseEvent,
        type: "suggestion" as const,
        suggestions: [],
      };

      const result = SuggestionEventSchema.safeParse(event);
      expect(result.success).toBe(false);
    });
  });

  describe("SessionStateEventSchema", () => {
    it("validates a valid session state event", () => {
      const event = {
        ...baseEvent,
        type: "session_state" as const,
        processKey: "billing-dispute",
        processName: "Billing Dispute Resolution",
        currentStep: "verify-identity",
        steps: [
          {
            key: "verify-identity",
            label: "Verify Identity",
            status: "in_progress" as const,
          },
        ],
        slots: { amount: "$50.00" },
        status: "active" as const,
      };

      const result = SessionStateEventSchema.safeParse(event);
      expect(result.success).toBe(true);
    });
  });

  describe("VoiceBridgeEventSchema (discriminated union)", () => {
    it("correctly identifies event types", () => {
      const transcriptEvent = {
        ...baseEvent,
        type: "transcript_segment" as const,
        speaker: "customer" as const,
        text: "Hello",
        isFinal: true,
      };

      const result = VoiceBridgeEventSchema.safeParse(transcriptEvent);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.type).toBe("transcript_segment");
      }
    });
  });
});
