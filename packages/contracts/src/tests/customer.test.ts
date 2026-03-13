import { describe, it, expect } from "vitest";
import {
  CustomerClassificationSchema,
  CustomerSchema,
  CustomerInteractionTypeSchema,
  CustomerInteractionSchema,
} from "../dto.js";

describe("Customer Schemas", () => {
  describe("CustomerClassificationSchema", () => {
    it("validates non-empty classifications", () => {
      expect(CustomerClassificationSchema.safeParse("basis").success).toBe(
        true
      );
      expect(CustomerClassificationSchema.safeParse("affluent").success).toBe(
        true
      );
      expect(
        CustomerClassificationSchema.safeParse("Standard Plus").success
      ).toBe(true);
      expect(CustomerClassificationSchema.safeParse("UHNWI").success).toBe(
        true
      );
    });

    it("rejects empty classifications", () => {
      expect(CustomerClassificationSchema.safeParse("").success).toBe(false);
      expect(CustomerClassificationSchema.safeParse("   ").success).toBe(false);
    });
  });

  describe("CustomerSchema", () => {
    it("validates complete customer profile", () => {
      const customer = {
        id: "0c4bffe9-0730-4ac0-a533-610bf1f054f4",
        name: "Laura Baumann",
        gender: "female",
        email: "laura.baumann@examplemail.ch",
        phone: "+41 79 331 74 25",
        customerSince: "2019-04-01",
        classification: "Standard",
        products: [
          "Grundversicherung (KVG)",
          "Zusatzversicherung Ambulant",
          "Unfallzusatz",
          "Rechtsschutz Gesundheit",
        ],
        preferredLanguage: "de",
        notes:
          "Strukturierte Kommunikation; benötigt verständliche Erklärungen und explizite Checklisten.",
      };
      const result = CustomerSchema.safeParse(customer);
      expect(result.success).toBe(true);
    });

    it("validates customer with nullable fields", () => {
      const customer = {
        id: "572fb421-2f53-4b54-a356-52dd5e3a4f38",
        name: "Alex Meyer",
        gender: "male",
        email: null,
        phone: null,
        customerSince: "2018-09-01",
        classification: "Affluent",
        products: ["Privatkonto Plus"],
        preferredLanguage: "de",
        notes: null,
      };
      const result = CustomerSchema.safeParse(customer);
      expect(result.success).toBe(true);
    });

    it("rejects invalid UUID", () => {
      const customer = {
        id: "invalid-uuid",
        name: "Test User",
        gender: "male",
        email: "test@example.com",
        phone: "+41 79 123 4567",
        customerSince: "2023-01-01",
        classification: "basis",
        products: [],
        preferredLanguage: "en",
        notes: null,
      };
      const result = CustomerSchema.safeParse(customer);
      expect(result.success).toBe(false);
    });

    it("rejects invalid email", () => {
      const customer = {
        id: "c1a1a1a1-1111-1111-1111-111111111111",
        name: "Test User",
        gender: "female",
        email: "not-an-email",
        phone: "+41 79 123 4567",
        customerSince: "2023-01-01",
        classification: "affluent",
        products: [],
        preferredLanguage: "en",
        notes: null,
      };
      const result = CustomerSchema.safeParse(customer);
      expect(result.success).toBe(false);
    });

    it("rejects invalid gender", () => {
      const customer = {
        id: "c1a1a1a1-1111-1111-1111-111111111111",
        name: "Test User",
        gender: "unknown",
        email: "test@example.com",
        phone: "+41 79 123 4567",
        customerSince: "2023-01-01",
        classification: "basis",
        products: [],
        preferredLanguage: "en",
        notes: null,
      };
      const result = CustomerSchema.safeParse(customer);
      expect(result.success).toBe(false);
    });
  });

  describe("CustomerInteractionTypeSchema", () => {
    it("validates valid interaction types", () => {
      expect(CustomerInteractionTypeSchema.safeParse("phone").success).toBe(
        true
      );
      expect(CustomerInteractionTypeSchema.safeParse("chat").success).toBe(
        true
      );
      expect(
        CustomerInteractionTypeSchema.safeParse("branch_visit").success
      ).toBe(true);
      expect(CustomerInteractionTypeSchema.safeParse("email").success).toBe(
        true
      );
      expect(
        CustomerInteractionTypeSchema.safeParse("mobile_app_chat").success
      ).toBe(true);
      expect(
        CustomerInteractionTypeSchema.safeParse("portal_message").success
      ).toBe(true);
      expect(
        CustomerInteractionTypeSchema.safeParse("secure_message").success
      ).toBe(true);
    });

    it("rejects invalid interaction types", () => {
      expect(CustomerInteractionTypeSchema.safeParse("sms").success).toBe(
        false
      );
      expect(CustomerInteractionTypeSchema.safeParse("").success).toBe(false);
    });
  });

  describe("CustomerInteractionSchema", () => {
    it("validates complete interaction", () => {
      const interaction = {
        id: "11111111-1111-1111-1111-111111111111",
        customerId: "c1a1a1a1-1111-1111-1111-111111111111",
        type: "phone",
        date: "2025-12-05T09:15:00Z",
        summary: "Inquiry about debit card fees",
        outcome: "Explained fee structure",
        agentName: "Maria Schmidt",
        channelDetail: null,
      };
      const result = CustomerInteractionSchema.safeParse(interaction);
      expect(result.success).toBe(true);
    });

    it("validates interaction with channel detail", () => {
      const interaction = {
        id: "22222222-2222-2222-2222-222222222222",
        customerId: "c1a1a1a1-1111-1111-1111-111111111111",
        type: "branch_visit",
        date: "2025-10-12T10:30:00Z",
        summary: "Consultation about mortgage refinancing",
        outcome: "Scheduled follow-up with advisor",
        agentName: "Lisa Keller",
        channelDetail: "Zurich Main Branch",
      };
      const result = CustomerInteractionSchema.safeParse(interaction);
      expect(result.success).toBe(true);
    });

    it("rejects invalid UUIDs", () => {
      const interaction = {
        id: "invalid",
        customerId: "also-invalid",
        type: "phone",
        date: "2025-12-05T09:15:00+00:00",
        summary: "Test summary",
        outcome: null,
        agentName: null,
        channelDetail: null,
      };
      const result = CustomerInteractionSchema.safeParse(interaction);
      expect(result.success).toBe(false);
    });

    it("rejects invalid datetime", () => {
      const interaction = {
        id: "33333333-3333-3333-3333-333333333333",
        customerId: "c1a1a1a1-1111-1111-1111-111111111111",
        type: "email",
        date: "not-a-datetime",
        summary: "Request for account statement",
        outcome: "Statement sent",
        agentName: "Paul Meyer",
        channelDetail: null,
      };
      const result = CustomerInteractionSchema.safeParse(interaction);
      expect(result.success).toBe(false);
    });
  });
});
