import { describe, it, expect } from "vitest";

import {
  ScenarioCivilitySchema,
  ScenarioConversationStepSchema,
  ScenarioSchema,
} from "../dto.js";

describe("Scenario Schemas", () => {
  describe("ScenarioCivilitySchema", () => {
    it("accepts civil and uncivil", () => {
      expect(ScenarioCivilitySchema.safeParse("civil").success).toBe(true);
      expect(ScenarioCivilitySchema.safeParse("uncivil").success).toBe(true);
    });

    it("rejects unknown conditions", () => {
      expect(ScenarioCivilitySchema.safeParse("neutral").success).toBe(false);
    });
  });

  describe("ScenarioConversationStepSchema", () => {
    it("validates a step with terminal nextId", () => {
      const result = ScenarioConversationStepSchema.safeParse({
        id: "closing",
        customerMsg: "Please summarize what happens next.",
        actorIntent: "Enforce recap",
        tone: "respectful",
        adviceInstructional: "Provide recap",
        nextId: null,
      });

      expect(result.success).toBe(true);
    });
  });

  describe("ScenarioSchema", () => {
    it("validates a full scenario payload", () => {
      const result = ScenarioSchema.safeParse({
        scenarioId: "bank_unauthorized_transaction_high_urgency_civil",
        scenarioFamily: "bank_unauthorized_transaction_high_urgency",
        title: "Unauthorized Card Transaction - Civil",
        domain: "banking",
        background: "A suspicious charge appeared.",
        customerGoal: "Block card and open dispute.",
        guidelines: {
          security_first: true,
        },
        conversation: [
          {
            id: "opening_alert",
            customerMsg: "I see a suspicious payment.",
            actorIntent: "Create urgency",
            tone: "concerned",
            adviceInstructional: "Verify identity and secure account",
            nextId: "identity_provision",
          },
        ],
        behavioralCondition: {
          civilityCondition: "civil",
          instruction: "Stay cooperative.",
        },
        status: "active",
      });

      expect(result.success).toBe(true);
    });
  });
});
