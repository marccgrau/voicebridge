/**
 * Tests for session queries
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { SupabaseClient } from "@supabase/supabase-js";
import {
  createSession,
  getSession,
  updateSessionState,
  rowToSessionState,
} from "./sessions.js";
import { createSessionRow, createSessionConfig } from "../test/factories.js";

function getFirstCallArg<T>(mockFn: ReturnType<typeof vi.fn>): T {
  const arg = mockFn.mock.calls[0]?.[0];
  if (arg === undefined) {
    throw new Error("Expected mock function to be called with at least one argument");
  }
  return arg as T;
}

describe("createSession", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    // Create a fresh mock client for each test
    mockClient = {
      from: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("creates session with correct schema", async () => {
    const config = createSessionConfig({
      sessionId: "test-session-id",
      locale: "en",
      domain: "test-domain",
    });

    const mockRow = createSessionRow({
      id: config.sessionId!,
      process_key: null,
      status: "active",
    });

    const mockSingle = vi.fn().mockResolvedValue({
      data: mockRow,
      error: null,
    });

    const mockSelect = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockInsert = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    const mockFrom = vi.fn().mockReturnValue({
      insert: mockInsert,
    });

    mockClient.from = mockFrom;

    const result = await createSession(mockClient, config);

    expect(mockFrom).toHaveBeenCalledWith("sessions");
    expect(mockInsert).toHaveBeenCalledWith(
      expect.objectContaining({
        id: config.sessionId,
        process_key: null,
        status: "active",
        state: expect.objectContaining({
          locale: "en",
          domain: "test-domain",
          slots: {},
          steps: [],
          currentStep: null,
        }),
      })
    );
    expect(result).toEqual(mockRow);
  });

  it("initializes empty slots and steps", async () => {
    const config = createSessionConfig();
    const mockRow = createSessionRow();

    const mockSingle = vi.fn().mockResolvedValue({
      data: mockRow,
      error: null,
    });

    const mockSelect = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockInsert = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    const mockFrom = vi.fn().mockReturnValue({
      insert: mockInsert,
    });

    mockClient.from = mockFrom;

    await createSession(mockClient, config);

    const insertCall = getFirstCallArg<{ state: { slots: unknown; steps: unknown; currentStep: unknown } }>(mockInsert);
    expect(insertCall.state.slots).toEqual({});
    expect(insertCall.state.steps).toEqual([]);
    expect(insertCall.state.currentStep).toBeNull();
  });

  it("sets status to active", async () => {
    const config = createSessionConfig();
    const mockRow = createSessionRow({ status: "active" });

    const mockSingle = vi.fn().mockResolvedValue({
      data: mockRow,
      error: null,
    });

    const mockSelect = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockInsert = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    const mockFrom = vi.fn().mockReturnValue({
      insert: mockInsert,
    });

    mockClient.from = mockFrom;

    await createSession(mockClient, config);

    const insertCall = getFirstCallArg<{ status: string }>(mockInsert);
    expect(insertCall.status).toBe("active");
  });

  it("throws on database error", async () => {
    const config = createSessionConfig();

    const mockSingle = vi.fn().mockResolvedValue({
      data: null,
      error: { message: "Database error" },
    });

    const mockSelect = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockInsert = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    const mockFrom = vi.fn().mockReturnValue({
      insert: mockInsert,
    });

    mockClient.from = mockFrom;

    await expect(createSession(mockClient, config)).rejects.toThrow(
      "Failed to create session: Database error"
    );
  });

  it("includes optional fields in state", async () => {
    const config = createSessionConfig({
      agentId: "agent-123",
      customerId: "customer-456",
      metadata: { foo: "bar" },
    });

    const mockRow = createSessionRow();

    const mockSingle = vi.fn().mockResolvedValue({
      data: mockRow,
      error: null,
    });

    const mockSelect = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockInsert = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    const mockFrom = vi.fn().mockReturnValue({
      insert: mockInsert,
    });

    mockClient.from = mockFrom;

    await createSession(mockClient, config);

    const insertCall = getFirstCallArg<{
      state: {
        agentId: string;
        customerId: string;
        metadata: Record<string, string>;
      };
    }>(mockInsert);
    expect(insertCall.state.agentId).toBe("agent-123");
    expect(insertCall.state.customerId).toBe("customer-456");
    expect(insertCall.state.metadata).toEqual({ foo: "bar" });
  });
});

describe("getSession", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    mockClient = {
      from: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("returns session by ID", async () => {
    const sessionId = "test-session-id";
    const mockRow = createSessionRow({ id: sessionId });

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

    const result = await getSession(mockClient, sessionId);

    expect(mockFrom).toHaveBeenCalledWith("sessions");
    expect(mockSelect).toHaveBeenCalledWith("*");
    expect(mockEq).toHaveBeenCalledWith("id", sessionId);
    expect(result).toEqual(mockRow);
  });

  it("returns null for non-existent session (PGRST116 error)", async () => {
    const sessionId = "non-existent";

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

    const result = await getSession(mockClient, sessionId);

    expect(result).toBeNull();
  });

  it("throws on other database errors", async () => {
    const sessionId = "test-session-id";

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

    await expect(getSession(mockClient, sessionId)).rejects.toThrow(
      "Failed to get session: Database failure"
    );
  });
});

describe("updateSessionState", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    mockClient = {
      from: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("updates process_key", async () => {
    const sessionId = "test-session-id";
    const updates = { process_key: "billing-dispute" };
    const mockRow = createSessionRow({
      id: sessionId,
      process_key: "billing-dispute",
    });

    const mockSingle = vi.fn().mockResolvedValue({
      data: mockRow,
      error: null,
    });

    const mockSelect = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockEq = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    const mockUpdate = vi.fn().mockReturnValue({
      eq: mockEq,
    });

    const mockFrom = vi.fn().mockReturnValue({
      update: mockUpdate,
    });

    mockClient.from = mockFrom;

    const result = await updateSessionState(mockClient, sessionId, updates);

    expect(mockFrom).toHaveBeenCalledWith("sessions");
    expect(mockUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        process_key: "billing-dispute",
        updated_at: expect.any(String),
      })
    );
    expect(mockEq).toHaveBeenCalledWith("id", sessionId);
    expect(result).toEqual(mockRow);
  });

  it("updates state JSONB", async () => {
    const sessionId = "test-session-id";
    const updates = {
      state: {
        slots: { order_number: "12345" },
        steps: [],
        currentStep: null,
      },
    };
    const mockRow = createSessionRow({ id: sessionId });

    const mockSingle = vi.fn().mockResolvedValue({
      data: mockRow,
      error: null,
    });

    const mockSelect = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockEq = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    const mockUpdate = vi.fn().mockReturnValue({
      eq: mockEq,
    });

    const mockFrom = vi.fn().mockReturnValue({
      update: mockUpdate,
    });

    mockClient.from = mockFrom;

    await updateSessionState(mockClient, sessionId, updates);

    const updateCall = getFirstCallArg<{ state: Record<string, unknown> }>(mockUpdate);
    expect(updateCall.state).toEqual(updates.state);
  });

  it("updates status", async () => {
    const sessionId = "test-session-id";
    const updates = { status: "completed" };
    const mockRow = createSessionRow({ id: sessionId, status: "completed" });

    const mockSingle = vi.fn().mockResolvedValue({
      data: mockRow,
      error: null,
    });

    const mockSelect = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockEq = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    const mockUpdate = vi.fn().mockReturnValue({
      eq: mockEq,
    });

    const mockFrom = vi.fn().mockReturnValue({
      update: mockUpdate,
    });

    mockClient.from = mockFrom;

    await updateSessionState(mockClient, sessionId, updates);

    const updateCall = getFirstCallArg<{ status: string }>(mockUpdate);
    expect(updateCall.status).toBe("completed");
  });

  it("sets updated_at timestamp", async () => {
    const sessionId = "test-session-id";
    const updates = { process_key: "test-process" };
    const mockRow = createSessionRow({ id: sessionId });

    const mockSingle = vi.fn().mockResolvedValue({
      data: mockRow,
      error: null,
    });

    const mockSelect = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockEq = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    const mockUpdate = vi.fn().mockReturnValue({
      eq: mockEq,
    });

    const mockFrom = vi.fn().mockReturnValue({
      update: mockUpdate,
    });

    mockClient.from = mockFrom;

    await updateSessionState(mockClient, sessionId, updates);

    const updateCall = getFirstCallArg<{ updated_at: string }>(mockUpdate);
    expect(updateCall.updated_at).toBeDefined();
    expect(typeof updateCall.updated_at).toBe("string");
  });

  it("throws on database error", async () => {
    const sessionId = "test-session-id";
    const updates = { process_key: "test-process" };

    const mockSingle = vi.fn().mockResolvedValue({
      data: null,
      error: { message: "Update failed" },
    });

    const mockSelect = vi.fn().mockReturnValue({
      single: mockSingle,
    });

    const mockEq = vi.fn().mockReturnValue({
      select: mockSelect,
    });

    const mockUpdate = vi.fn().mockReturnValue({
      eq: mockEq,
    });

    const mockFrom = vi.fn().mockReturnValue({
      update: mockUpdate,
    });

    mockClient.from = mockFrom;

    await expect(
      updateSessionState(mockClient, sessionId, updates)
    ).rejects.toThrow("Failed to update session: Update failed");
  });
});

describe("rowToSessionState", () => {
  it("transforms database row to SessionState", () => {
    const row = createSessionRow({
      id: "session-123",
      process_key: "billing-dispute",
      state: {
        processName: "Billing Dispute",
        currentStep: "verify",
        steps: [{ key: "verify", label: "Verify Account", status: "completed" }],
        slots: { order_number: "12345" },
      },
      status: "active",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T01:00:00Z",
    });

    const result = rowToSessionState(row);

    expect(result).toEqual({
      sessionId: "session-123",
      processKey: "billing-dispute",
      processName: "Billing Dispute",
      currentStep: "verify",
      steps: [{ key: "verify", label: "Verify Account", status: "completed" }],
      slots: { order_number: "12345" },
      status: "active",
      createdAt: "2024-01-01T00:00:00Z",
      updatedAt: "2024-01-01T01:00:00Z",
    });
  });

  it("handles null process_key", () => {
    const row = createSessionRow({
      process_key: null,
      state: {},
    });

    const result = rowToSessionState(row);

    expect(result.processKey).toBeNull();
    expect(result.processName).toBeNull();
  });

  it("handles missing state fields", () => {
    const row = createSessionRow({
      state: {},
    });

    const result = rowToSessionState(row);

    expect(result.currentStep).toBeNull();
    expect(result.steps).toEqual([]);
    expect(result.slots).toEqual({});
  });

  it("extracts nested state properties correctly", () => {
    const row = createSessionRow({
      state: {
        processName: "Test Process",
        currentStep: "step-1",
        steps: [{ key: "step-1", label: "Step 1", status: "active" }],
        slots: { foo: "bar", baz: "qux" },
        // Extra fields that should be ignored
        extraField: "ignored",
      },
    });

    const result = rowToSessionState(row);

    expect(result.processName).toBe("Test Process");
    expect(result.currentStep).toBe("step-1");
    expect(result.steps).toEqual([
      { key: "step-1", label: "Step 1", status: "active" },
    ]);
    expect(result.slots).toEqual({ foo: "bar", baz: "qux" });
  });
});
