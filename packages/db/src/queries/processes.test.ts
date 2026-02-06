/**
 * Tests for process queries
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { SupabaseClient } from "@supabase/supabase-js";
import {
  searchProcesses,
  getProcess,
  listProcessesByDomain,
  rowToProcessDefinition,
} from "./processes.js";
import { createProcessRow } from "../test/factories.js";

describe("searchProcesses", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    mockClient = {
      rpc: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("calls search_processes RPC with query", async () => {
    const mockResults = [
      { ...createProcessRow(), rank: 0.9 },
      { ...createProcessRow({ process_key: "process-2" }), rank: 0.7 },
    ];

    const mockRpc = vi.fn().mockResolvedValue({
      data: mockResults,
      error: null,
    });

    mockClient.rpc = mockRpc;

    const result = await searchProcesses(mockClient, "billing dispute");

    expect(mockRpc).toHaveBeenCalledWith("search_processes", {
      search_query: "billing dispute",
      search_locale: "en",
      search_domain: undefined,
      search_queue_tag: undefined,
      result_limit: 5,
    });
    expect(result.results).toHaveLength(2);
    expect(result.queryTime).toBeGreaterThanOrEqual(0);
  });

  it("includes locale in search options", async () => {
    const mockRpc = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });

    mockClient.rpc = mockRpc;

    await searchProcesses(mockClient, "test query", {
      locale: "es",
    });

    expect(mockRpc).toHaveBeenCalledWith(
      "search_processes",
      expect.objectContaining({
        search_locale: "es",
      })
    );
  });

  it("includes domain filter when provided", async () => {
    const mockRpc = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });

    mockClient.rpc = mockRpc;

    await searchProcesses(mockClient, "test query", {
      domain: "billing",
    });

    expect(mockRpc).toHaveBeenCalledWith(
      "search_processes",
      expect.objectContaining({
        search_domain: "billing",
      })
    );
  });

  it("includes queueTag filter when provided", async () => {
    const mockRpc = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });

    mockClient.rpc = mockRpc;

    await searchProcesses(mockClient, "test query", {
      queueTag: "priority",
    });

    expect(mockRpc).toHaveBeenCalledWith(
      "search_processes",
      expect.objectContaining({
        search_queue_tag: "priority",
      })
    );
  });

  it("respects custom limit", async () => {
    const mockRpc = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });

    mockClient.rpc = mockRpc;

    await searchProcesses(mockClient, "test query", {
      limit: 10,
    });

    expect(mockRpc).toHaveBeenCalledWith(
      "search_processes",
      expect.objectContaining({
        result_limit: 10,
      })
    );
  });

  it("maps results to ProcessLookupOutput format", async () => {
    const mockResults = [
      {
        ...createProcessRow({
          process_key: "billing-dispute",
          name: "Billing Dispute",
          domain: "billing",
          version: "1.0.0",
          process_text: "Process for billing disputes",
        }),
        rank: 0.95,
      },
    ];

    const mockRpc = vi.fn().mockResolvedValue({
      data: mockResults,
      error: null,
    });

    mockClient.rpc = mockRpc;

    const result = await searchProcesses(mockClient, "billing");

    expect(result.results[0]).toEqual({
      processKey: "billing-dispute",
      name: "Billing Dispute",
      domain: "billing",
      version: "1.0.0",
      score: 0.95,
      processText: "Process for billing disputes",
      stepsJson: expect.any(Array),
    });
  });

  it("throws on database error", async () => {
    const mockRpc = vi.fn().mockResolvedValue({
      data: null,
      error: { message: "RPC failed" },
    });

    mockClient.rpc = mockRpc;

    await expect(searchProcesses(mockClient, "test")).rejects.toThrow(
      "Process search failed: RPC failed"
    );
  });

  it("returns empty results when no matches", async () => {
    const mockRpc = vi.fn().mockResolvedValue({
      data: null,
      error: null,
    });

    mockClient.rpc = mockRpc;

    const result = await searchProcesses(mockClient, "nonexistent");

    expect(result.results).toEqual([]);
  });
});

describe("getProcess", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    mockClient = {
      from: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("returns process by key", async () => {
    const processKey = "billing-dispute";
    const mockRow = createProcessRow({ process_key: processKey });

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

    const result = await getProcess(mockClient, processKey);

    expect(mockFrom).toHaveBeenCalledWith("process_catalog");
    expect(mockSelect).toHaveBeenCalledWith("*");
    expect(mockEq).toHaveBeenCalledWith("process_key", processKey);
    expect(result).toEqual(mockRow);
  });

  it("returns null for non-existent process (PGRST116 error)", async () => {
    const mockSingle = vi.fn().mockResolvedValue({
      data: null,
      error: { code: "PGRST116", message: "No rows found" },
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

    const result = await getProcess(mockClient, "nonexistent");

    expect(result).toBeNull();
  });

  it("throws on other database errors", async () => {
    const mockSingle = vi.fn().mockResolvedValue({
      data: null,
      error: { code: "OTHER_ERROR", message: "Database failure" },
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

    await expect(getProcess(mockClient, "test")).rejects.toThrow(
      "Failed to get process: Database failure"
    );
  });
});

describe("listProcessesByDomain", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    mockClient = {
      from: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("queries processes by domain", async () => {
    const domain = "billing";
    const mockRows = [
      createProcessRow({ process_key: "billing-1", domain }),
      createProcessRow({ process_key: "billing-2", domain }),
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

    const result = await listProcessesByDomain(mockClient, domain);

    expect(mockFrom).toHaveBeenCalledWith("process_catalog");
    expect(mockSelect).toHaveBeenCalledWith("*");
    expect(mockEq).toHaveBeenCalledWith("domain", domain);
    expect(mockOrder).toHaveBeenCalledWith("name");
    expect(result).toEqual(mockRows);
  });

  it("filters by status when provided", async () => {
    const domain = "billing";
    const mockRows = [createProcessRow({ status: "active" })];

    const mockOrder = vi.fn().mockResolvedValue({
      data: mockRows,
      error: null,
    });

    const mockEq = vi.fn((_field: string) => {
      return {
        eq: mockEq,
        order: mockOrder,
      };
    });

    const mockSelect = vi.fn().mockReturnValue({
      eq: mockEq,
    });

    const mockFrom = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    mockClient.from = mockFrom;

    await listProcessesByDomain(mockClient, domain, { status: "active" });

    expect(mockEq).toHaveBeenCalledWith("domain", domain);
    expect(mockEq).toHaveBeenCalledWith("status", "active");
  });

  it("filters by locale when provided", async () => {
    const domain = "billing";
    const mockRows = [createProcessRow({ locale: "es" })];

    const mockOrder = vi.fn().mockResolvedValue({
      data: mockRows,
      error: null,
    });

    const mockEq = vi.fn((_field: string) => {
      return {
        eq: mockEq,
        order: mockOrder,
      };
    });

    const mockSelect = vi.fn().mockReturnValue({
      eq: mockEq,
    });

    const mockFrom = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    mockClient.from = mockFrom;

    await listProcessesByDomain(mockClient, domain, { locale: "es" });

    expect(mockEq).toHaveBeenCalledWith("domain", domain);
    expect(mockEq).toHaveBeenCalledWith("locale", "es");
  });

  it("orders results by name", async () => {
    const domain = "billing";

    const mockOrder = vi.fn().mockResolvedValue({
      data: [],
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

    await listProcessesByDomain(mockClient, domain);

    expect(mockOrder).toHaveBeenCalledWith("name");
  });

  it("returns empty array when no processes found", async () => {
    const mockOrder = vi.fn().mockResolvedValue({
      data: null,
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

    const result = await listProcessesByDomain(mockClient, "nonexistent");

    expect(result).toEqual([]);
  });

  it("throws on database error", async () => {
    const mockOrder = vi.fn().mockResolvedValue({
      data: null,
      error: { message: "Query failed" },
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

    await expect(listProcessesByDomain(mockClient, "billing")).rejects.toThrow(
      "Failed to list processes: Query failed"
    );
  });
});

describe("rowToProcessDefinition", () => {
  it("transforms database row to ProcessDefinition", () => {
    const row = createProcessRow({
      process_key: "billing-dispute",
      name: "Billing Dispute",
      domain: "billing",
      queue_tag: "priority",
      locale: "en",
      version: "1.0.0",
      status: "active",
      process_text: "Process description",
      steps_json: [
        { key: "verify", label: "Verify Account", requiredSlots: ["order_id"] },
      ],
      updated_at: "2024-01-01T00:00:00Z",
    });

    const result = rowToProcessDefinition(row);

    expect(result).toEqual({
      processKey: "billing-dispute",
      name: "Billing Dispute",
      domain: "billing",
      queueTag: "priority",
      locale: "en",
      version: "1.0.0",
      status: "active",
      processText: "Process description",
      stepsJson: [
        { key: "verify", label: "Verify Account", requiredSlots: ["order_id"] },
      ],
      updatedAt: "2024-01-01T00:00:00Z",
    });
  });

  it("converts null queue_tag to undefined", () => {
    const row = createProcessRow({
      queue_tag: null,
    });

    const result = rowToProcessDefinition(row);

    expect(result.queueTag).toBeUndefined();
  });

  it("handles active and inactive status", () => {
    const activeRow = createProcessRow({ status: "active" });
    const inactiveRow = createProcessRow({ status: "inactive" });

    expect(rowToProcessDefinition(activeRow).status).toBe("active");
    expect(rowToProcessDefinition(inactiveRow).status).toBe("inactive");
  });
});
