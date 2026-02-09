/**
 * Tests for customer queries
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { SupabaseClient } from "@supabase/supabase-js";
import {
  getCustomer,
  getAllCustomers,
  getCustomerInteractions,
  rowToCustomer,
  rowToCustomerInteraction,
} from "./customers.js";
import {
  createCustomerRow,
  createCustomerInteractionRow,
} from "../test/factories.js";

describe("getCustomer", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    mockClient = {
      from: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("fetches customer by ID", async () => {
    const customerId = "c1a1a1a1-1111-1111-1111-111111111111";
    const mockRow = createCustomerRow({ id: customerId });

    const mockSingle = vi.fn().mockResolvedValue({
      data: mockRow,
      error: null,
    });

    const mockEq = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockSelect = vi.fn().mockReturnValue({
      eq: mockEq,
    });

    const mockFrom = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    mockClient.from = mockFrom;

    const result = await getCustomer(mockClient, customerId);

    expect(mockFrom).toHaveBeenCalledWith("customers");
    expect(mockSelect).toHaveBeenCalledWith("*");
    expect(mockEq).toHaveBeenCalledWith("id", customerId);
    expect(result).toEqual(mockRow);
  });

  it("returns null when customer not found", async () => {
    const customerId = "non-existent-id";

    const mockSingle = vi.fn().mockResolvedValue({
      data: null,
      error: { code: "PGRST116", message: "Not found" },
    });

    const mockEq = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockSelect = vi.fn().mockReturnValue({
      eq: mockEq,
    });

    const mockFrom = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    mockClient.from = mockFrom;

    const result = await getCustomer(mockClient, customerId);

    expect(result).toBeNull();
  });
});

describe("getAllCustomers", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    mockClient = {
      from: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("fetches all customers ordered by name", async () => {
    const mockRows = [
      createCustomerRow({ name: "Anna Müller" }),
      createCustomerRow({ name: "Thomas Weber" }),
    ];

    const mockOrder = vi.fn().mockResolvedValue({
      data: mockRows,
      error: null,
    });

    const mockSelect = vi.fn().mockReturnValue({
      order: mockOrder,
    });

    const mockFrom = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    mockClient.from = mockFrom;

    const result = await getAllCustomers(mockClient);

    expect(mockFrom).toHaveBeenCalledWith("customers");
    expect(mockSelect).toHaveBeenCalledWith("*");
    expect(mockOrder).toHaveBeenCalledWith("name", { ascending: true });
    expect(result).toEqual(mockRows);
  });

  it("returns empty array when no customers", async () => {
    const mockOrder = vi.fn().mockResolvedValue({
      data: null,
      error: null,
    });

    const mockSelect = vi.fn().mockReturnValue({
      order: mockOrder,
    });

    const mockFrom = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    mockClient.from = mockFrom;

    const result = await getAllCustomers(mockClient);

    expect(result).toEqual([]);
  });
});

describe("getCustomerInteractions", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    mockClient = {
      from: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("fetches customer interactions ordered by date descending", async () => {
    const customerId = "c1a1a1a1-1111-1111-1111-111111111111";
    const mockRows = [
      createCustomerInteractionRow({ customer_id: customerId }),
      createCustomerInteractionRow({ customer_id: customerId }),
    ];

    const mockOrder = vi.fn().mockResolvedValue({
      data: mockRows,
      error: null,
    });

    const mockEq = vi.fn().mockReturnValue({
      order: mockOrder,
    });

    const mockSelect = vi.fn().mockReturnValue({
      eq: mockEq,
    });

    const mockFrom = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    mockClient.from = mockFrom;

    const result = await getCustomerInteractions(mockClient, customerId);

    expect(mockFrom).toHaveBeenCalledWith("customer_interactions");
    expect(mockSelect).toHaveBeenCalledWith("*");
    expect(mockEq).toHaveBeenCalledWith("customer_id", customerId);
    expect(mockOrder).toHaveBeenCalledWith("date", { ascending: false });
    expect(result).toEqual(mockRows);
  });

  it("applies limit and offset when provided", async () => {
    const customerId = "c1a1a1a1-1111-1111-1111-111111111111";
    const mockRows = [
      createCustomerInteractionRow({ customer_id: customerId }),
    ];

    const mockRange = vi.fn().mockResolvedValue({
      data: mockRows,
      error: null,
    });

    const mockLimit = vi.fn().mockReturnValue({
      range: mockRange,
    });

    const mockOrder = vi.fn().mockReturnValue({
      limit: mockLimit,
    });

    const mockEq = vi.fn().mockReturnValue({
      order: mockOrder,
    });

    const mockSelect = vi.fn().mockReturnValue({
      eq: mockEq,
    });

    const mockFrom = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    mockClient.from = mockFrom;

    const result = await getCustomerInteractions(mockClient, customerId, {
      limit: 5,
      offset: 10,
    });

    expect(mockLimit).toHaveBeenCalledWith(5);
    expect(mockRange).toHaveBeenCalledWith(10, 14); // offset 10, limit 5 → 10..14
    expect(result).toEqual(mockRows);
  });
});

describe("rowToCustomer", () => {
  it("converts database row to Customer type", () => {
    const row = createCustomerRow({
      id: "c1a1a1a1-1111-1111-1111-111111111111",
      name: "Anna Müller",
      gender: "female",
      email: "anna@example.com",
      phone: "+41 79 123 4567",
      customer_since: "2023-06-15",
      classification: "basis",
      products: ["Savings Account", "Debit Card"],
      preferred_language: "de",
      notes: "Test notes",
    });

    const result = rowToCustomer(row);

    expect(result).toEqual({
      id: row.id,
      name: row.name,
      gender: row.gender,
      email: row.email,
      phone: row.phone,
      customerSince: row.customer_since,
      classification: row.classification,
      products: row.products,
      preferredLanguage: row.preferred_language,
      notes: row.notes,
    });
  });
});

describe("rowToCustomerInteraction", () => {
  it("converts database row to CustomerInteraction type", () => {
    const row = createCustomerInteractionRow({
      id: "i1a1a1a1-1111-1111-1111-111111111111",
      customer_id: "c1a1a1a1-1111-1111-1111-111111111111",
      type: "phone",
      date: "2025-12-05T09:15:00+00:00",
      summary: "Inquiry about debit card fees",
      outcome: "Explained fee structure",
      agent_name: "Maria Schmidt",
      channel_detail: null,
    });

    const result = rowToCustomerInteraction(row);

    expect(result).toEqual({
      id: row.id,
      customerId: row.customer_id,
      type: row.type,
      date: row.date,
      summary: row.summary,
      outcome: row.outcome,
      agentName: row.agent_name,
      channelDetail: row.channel_detail,
    });
  });
});
