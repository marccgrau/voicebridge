import { describe, it, expect } from "vitest";
import {
  LLMProviderSchema,
  ProcessLookupInputSchema,
  ProcessLookupOutputSchema,
  SessionConfigSchema,
  SessionStartResponseSchema,
  SessionStopResponseSchema,
  SessionStateSchema,
  SessionCreateRequestSchema,
  SessionCreateResponseSchema,
  SessionAcceptRequestSchema,
  SessionAcceptResponseSchema,
  SessionSummaryUpdateRequestSchema,
  SessionSummaryUpdateResponseSchema,
  UIPreferencesSchema,
} from "../dto.js";

describe("DTO Schemas", () => {
  describe("LLMProviderSchema", () => {
    it("accepts valid providers", () => {
      expect(LLMProviderSchema.safeParse("gemini").success).toBe(true);
      expect(LLMProviderSchema.safeParse("anthropic").success).toBe(true);
      expect(LLMProviderSchema.safeParse("openai").success).toBe(true);
    });

    it("rejects invalid provider", () => {
      expect(LLMProviderSchema.safeParse("invalid").success).toBe(false);
    });
  });

  describe("ProcessLookupInputSchema", () => {
    it("validates with required fields only", () => {
      const input = { query: "billing dispute" };
      const result = ProcessLookupInputSchema.safeParse(input);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.locale).toBe("en");
        expect(result.data.limit).toBe(5);
      }
    });

    it("validates with all fields", () => {
      const input = {
        query: "password reset",
        locale: "es",
        domain: "account",
        queueTag: "account-support",
        limit: 3,
      };
      const result = ProcessLookupInputSchema.safeParse(input);
      expect(result.success).toBe(true);
    });

    it("rejects empty query", () => {
      const input = { query: "" };
      const result = ProcessLookupInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });

    it("rejects limit above 10", () => {
      const input = { query: "test", limit: 15 };
      const result = ProcessLookupInputSchema.safeParse(input);
      expect(result.success).toBe(false);
    });
  });

  describe("ProcessLookupOutputSchema", () => {
    it("validates valid output", () => {
      const output = {
        results: [
          {
            processKey: "billing-dispute",
            name: "Billing Dispute",
            domain: "billing",
            version: "1.0.0",
            score: 0.85,
            processText: "Handle billing disputes...",
          },
        ],
        queryTime: 15.5,
      };
      const result = ProcessLookupOutputSchema.safeParse(output);
      expect(result.success).toBe(true);
    });
  });

  describe("SessionConfigSchema", () => {
    it("validates with defaults", () => {
      const config = {};
      const result = SessionConfigSchema.safeParse(config);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.locale).toBe("en");
      }
    });

    it("validates with custom session ID", () => {
      const config = {
        sessionId: "123e4567-e89b-12d3-a456-426614174000",
        locale: "fr",
        domain: "billing",
      };
      const result = SessionConfigSchema.safeParse(config);
      expect(result.success).toBe(true);
    });
  });

  describe("SessionStartResponseSchema", () => {
    it("validates valid response", () => {
      const response = {
        sessionId: "123e4567-e89b-12d3-a456-426614174000",
        roomUrl: "https://daily.co/room123",
        roomToken: "token123",
        createdAt: "2024-01-15T10:30:00.000Z",
        rtviUrl: "https://daily.co/room123",
        services: {
          suggestionService: "simple_turn" as const,
          processIllustrationEnabled: true,
        },
      };
      const result = SessionStartResponseSchema.safeParse(response);
      expect(result.success).toBe(true);
    });
  });

  describe("UIPreferencesSchema", () => {
    it("provides sensible defaults", () => {
      const prefs = {};
      const result = UIPreferencesSchema.safeParse(prefs);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.panelLayout).toBe("default");
        expect(result.data.showConfidence).toBe(true);
        expect(result.data.autoScroll).toBe(true);
        expect(result.data.suggestionCount).toBe(3);
        expect(result.data.theme).toBe("system");
      }
    });

    it("validates custom preferences", () => {
      const prefs = {
        panelLayout: "compact",
        showConfidence: false,
        suggestionCount: 6,
        theme: "dark",
      };
      const result = UIPreferencesSchema.safeParse(prefs);
      expect(result.success).toBe(true);
    });
  });

  describe("SessionStateSchema", () => {
    it("accepts pending status", () => {
      const state = {
        sessionId: "123e4567-e89b-12d3-a456-426614174000",
        processKey: null,
        processName: null,
        currentStep: null,
        steps: [],
        slots: {},
        status: "pending",
        createdAt: "2024-01-15T10:30:00.000Z",
        updatedAt: "2024-01-15T10:30:00.000Z",
      };
      const result = SessionStateSchema.safeParse(state);
      expect(result.success).toBe(true);
    });
  });

  describe("SessionStopResponseSchema", () => {
    it("accepts pending status", () => {
      const response = {
        sessionId: "123e4567-e89b-12d3-a456-426614174000",
        stoppedAt: "2024-01-15T10:30:00.000Z",
        duration: 120,
        status: "pending",
      };
      const result = SessionStopResponseSchema.safeParse(response);
      expect(result.success).toBe(true);
    });
  });

  describe("SessionCreateRequestSchema", () => {
    it("validates with defaults", () => {
      const result = SessionCreateRequestSchema.safeParse({});
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.locale).toBe("en");
      }
    });

    it("validates with all fields", () => {
      const request = {
        locale: "es",
        domain: "billing",
        metadata: { source: "web" },
      };
      const result = SessionCreateRequestSchema.safeParse(request);
      expect(result.success).toBe(true);
    });
  });

  describe("SessionCreateResponseSchema", () => {
    it("validates valid response", () => {
      const response = {
        sessionId: "123e4567-e89b-12d3-a456-426614174000",
        roomUrl: "https://test.daily.co/room123",
        customerToken: "token-abc",
      };
      const result = SessionCreateResponseSchema.safeParse(response);
      expect(result.success).toBe(true);
    });

    it("rejects missing fields", () => {
      const result = SessionCreateResponseSchema.safeParse({
        sessionId: "123e4567-e89b-12d3-a456-426614174000",
      });
      expect(result.success).toBe(false);
    });
  });

  describe("SessionAcceptRequestSchema", () => {
    it("validates with required fields and defaults", () => {
      const request = {
        sessionId: "123e4567-e89b-12d3-a456-426614174000",
      };
      const result = SessionAcceptRequestSchema.safeParse(request);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.enableProcessFlow).toBe(true);
        expect(result.data.enableSuggestionFlow).toBe(true);
        expect(result.data.processFlowProvider).toBe("openai");
        expect(result.data.processFlowModel).toBe("gpt-5-nano");
        expect(result.data.suggestionFlowProvider).toBe("openai");
        expect(result.data.suggestionFlowModel).toBe("gpt-5-nano");
      }
    });

    it("validates with custom providers", () => {
      const request = {
        sessionId: "123e4567-e89b-12d3-a456-426614174000",
        processFlowProvider: "anthropic" as const,
        processFlowModel: "claude-haiku-4-5-20251001",
        suggestionFlowProvider: "openai" as const,
        suggestionFlowModel: "gpt-4",
      };
      const result = SessionAcceptRequestSchema.safeParse(request);
      expect(result.success).toBe(true);
    });

    it("rejects invalid session ID", () => {
      const result = SessionAcceptRequestSchema.safeParse({
        sessionId: "not-a-uuid",
      });
      expect(result.success).toBe(false);
    });

    it("rejects invalid provider", () => {
      const result = SessionAcceptRequestSchema.safeParse({
        sessionId: "123e4567-e89b-12d3-a456-426614174000",
        processFlowProvider: "invalid",
      });
      expect(result.success).toBe(false);
    });
  });

  describe("SessionAcceptResponseSchema", () => {
    it("validates valid response", () => {
      const response = {
        sessionId: "123e4567-e89b-12d3-a456-426614174000",
        roomUrl: "https://test.daily.co/room123",
        agentToken: "agent-token-abc",
        rtviUrl: "https://test.daily.co/room123/rtvi",
        services: {
          processFlowEnabled: true,
          suggestionFlowEnabled: true,
        },
      };
      const result = SessionAcceptResponseSchema.safeParse(response);
      expect(result.success).toBe(true);
    });
  });

  describe("SessionSummaryUpdateRequestSchema", () => {
    it("validates with required fields", () => {
      const request = {
        sessionId: "test-session-123",
        summaryText: "Customer needed help with billing.",
      };
      const result = SessionSummaryUpdateRequestSchema.safeParse(request);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.updatedBy).toBe("agent");
      }
    });

    it("validates with custom updatedBy", () => {
      const request = {
        sessionId: "test-session-123",
        summaryText: "Summary text",
        updatedBy: "supervisor",
      };
      const result = SessionSummaryUpdateRequestSchema.safeParse(request);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.updatedBy).toBe("supervisor");
      }
    });

    it("rejects empty summary text", () => {
      const request = {
        sessionId: "test-session-123",
        summaryText: "",
      };
      const result = SessionSummaryUpdateRequestSchema.safeParse(request);
      expect(result.success).toBe(false);
    });

    it("rejects missing summaryText", () => {
      const result = SessionSummaryUpdateRequestSchema.safeParse({
        sessionId: "test-session-123",
      });
      expect(result.success).toBe(false);
    });
  });

  describe("SessionSummaryUpdateResponseSchema", () => {
    it("validates valid response", () => {
      const response = {
        sessionId: "test-session-123",
        summaryText: "Customer needed help with billing.",
        updatedAt: "2024-01-15T10:30:00Z",
        updatedBy: "agent",
      };
      const result = SessionSummaryUpdateResponseSchema.safeParse(response);
      expect(result.success).toBe(true);
    });

    it("rejects missing fields", () => {
      const result = SessionSummaryUpdateResponseSchema.safeParse({
        sessionId: "test-session-123",
      });
      expect(result.success).toBe(false);
    });
  });
});
