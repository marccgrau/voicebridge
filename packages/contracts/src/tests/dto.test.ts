import { describe, it, expect } from "vitest";
import {
  ProcessLookupInputSchema,
  ProcessLookupOutputSchema,
  SessionConfigSchema,
  SessionStartResponseSchema,
  UIPreferencesSchema,
} from "../dto.js";

describe("DTO Schemas", () => {
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
});
