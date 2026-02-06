/**
 * Tests for transcript queries
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { SupabaseClient } from "@supabase/supabase-js";
import {
  insertTranscriptSegment,
  getTranscriptSegments,
  rowToTranscriptEntry,
  getConversationContext,
  type TranscriptSegmentRow,
} from "./transcripts.js";
import { createTranscriptRow } from "../test/factories.js";

function getFirstCallArg<T>(mockFn: ReturnType<typeof vi.fn>): T {
  const arg = mockFn.mock.calls[0]?.[0];
  if (arg === undefined) {
    throw new Error(
      "Expected mock function to be called with at least one argument"
    );
  }
  return arg as T;
}

describe("insertTranscriptSegment", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    mockClient = {
      from: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("inserts transcript segment with correct fields", async () => {
    const segment = {
      sessionId: "session-123",
      speaker: "customer" as const,
      text: "I need help with my order",
      isFinal: true,
      confidence: 0.95,
    };

    const mockRow = createTranscriptRow({
      session_id: segment.sessionId,
      speaker: segment.speaker,
      text: segment.text,
      is_final: segment.isFinal,
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

    const result = await insertTranscriptSegment(mockClient, segment);

    expect(mockFrom).toHaveBeenCalledWith("transcript_segments");
    expect(mockInsert).toHaveBeenCalledWith({
      session_id: "session-123",
      speaker: "customer",
      text: "I need help with my order",
      is_final: true,
      confidence: 0.95,
    });
    expect(result).toEqual(mockRow);
  });

  it("inserts segment without confidence", async () => {
    const segment = {
      sessionId: "session-123",
      speaker: "agent" as const,
      text: "How can I help?",
      isFinal: true,
    };

    const mockRow = createTranscriptRow({
      session_id: segment.sessionId,
      speaker: segment.speaker,
      text: segment.text,
      is_final: segment.isFinal,
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

    await insertTranscriptSegment(mockClient, segment);

    const insertCall = getFirstCallArg<{ confidence?: number }>(mockInsert);
    expect(insertCall.confidence).toBeUndefined();
  });

  it("handles interim transcripts (isFinal: false)", async () => {
    const segment = {
      sessionId: "session-123",
      speaker: "customer" as const,
      text: "I need...",
      isFinal: false,
    };

    const mockRow = createTranscriptRow({
      is_final: false,
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

    await insertTranscriptSegment(mockClient, segment);

    const insertCall = getFirstCallArg<{ is_final: boolean }>(mockInsert);
    expect(insertCall.is_final).toBe(false);
  });

  it("throws on database error", async () => {
    const segment = {
      sessionId: "session-123",
      speaker: "customer" as const,
      text: "Test",
      isFinal: true,
    };

    const mockSingle = vi.fn().mockResolvedValue({
      data: null,
      error: { message: "Insert failed" },
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

    await expect(insertTranscriptSegment(mockClient, segment)).rejects.toThrow(
      "Failed to insert transcript segment: Insert failed"
    );
  });
});

describe("getTranscriptSegments", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    mockClient = {
      from: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("queries transcripts by session ID", async () => {
    const sessionId = "session-123";
    const mockRows = [
      createTranscriptRow({ session_id: sessionId, text: "First message" }),
      createTranscriptRow({ session_id: sessionId, text: "Second message" }),
    ];

    const mockChain = {
      data: mockRows,
      error: null,
    };

    const mockOrder = vi.fn().mockResolvedValue(mockChain);

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

    const result = await getTranscriptSegments(mockClient, sessionId);

    expect(mockFrom).toHaveBeenCalledWith("transcript_segments");
    expect(mockSelect).toHaveBeenCalledWith("*");
    expect(mockEq).toHaveBeenCalledWith("session_id", sessionId);
    expect(mockOrder).toHaveBeenCalledWith("ts", { ascending: true });
    expect(result).toEqual(mockRows);
  });

  it("orders by timestamp ascending", async () => {
    const sessionId = "session-123";

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

    await getTranscriptSegments(mockClient, sessionId);

    expect(mockOrder).toHaveBeenCalledWith("ts", { ascending: true });
  });

  it("filters by is_final when finalOnly option is true", async () => {
    const sessionId = "session-123";
    const mockRows = [createTranscriptRow({ is_final: true })];

    // Create a chainable query object with all needed methods
    const mockQuery: {
      eq: ReturnType<typeof vi.fn>;
      limit: ReturnType<typeof vi.fn>;
    } = {
      eq: vi.fn(),
      limit: vi.fn(),
    };

    // Make eq and limit return themselves for chaining
    mockQuery.eq.mockReturnValue(mockQuery);
    mockQuery.limit.mockResolvedValue({ data: mockRows, error: null });

    const mockOrder = vi.fn().mockReturnValue(mockQuery);
    const mockEq = vi.fn().mockReturnValue({ order: mockOrder });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
    const mockFrom = vi.fn().mockReturnValue({ select: mockSelect });

    mockClient.from = mockFrom;

    await getTranscriptSegments(mockClient, sessionId, { finalOnly: true });

    expect(mockEq).toHaveBeenCalledWith("session_id", sessionId);
    expect(mockQuery.eq).toHaveBeenCalledWith("is_final", true);
  });

  it("limits results when limit option is provided", async () => {
    const sessionId = "session-123";

    const mockLimit = vi.fn().mockResolvedValue({
      data: [],
      error: null,
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

    await getTranscriptSegments(mockClient, sessionId, { limit: 10 });

    expect(mockLimit).toHaveBeenCalledWith(10);
  });

  it("returns empty array when no segments found", async () => {
    const sessionId = "session-123";

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

    const result = await getTranscriptSegments(mockClient, sessionId);

    expect(result).toEqual([]);
  });

  it("throws on database error", async () => {
    const sessionId = "session-123";

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

    await expect(getTranscriptSegments(mockClient, sessionId)).rejects.toThrow(
      "Failed to get transcript segments: Query failed"
    );
  });
});

describe("rowToTranscriptEntry", () => {
  it("transforms database row to TranscriptEntry", () => {
    const row: TranscriptSegmentRow = {
      id: "transcript-123",
      session_id: "session-123",
      speaker: "customer",
      text: "I need help",
      is_final: true,
      confidence: null,
      ts: "2024-01-01T00:00:00Z",
    };

    const result = rowToTranscriptEntry(row);

    expect(result).toEqual({
      id: "transcript-123",
      speaker: "customer",
      text: "I need help",
      timestamp: "2024-01-01T00:00:00Z",
      isFinal: true,
    });
  });

  it("handles agent speaker", () => {
    const row: TranscriptSegmentRow = {
      id: "transcript-456",
      session_id: "session-123",
      speaker: "agent",
      text: "How can I assist you?",
      is_final: true,
      confidence: null,
      ts: "2024-01-01T00:00:00Z",
    };

    const result = rowToTranscriptEntry(row);

    expect(result.speaker).toBe("agent");
  });

  it("handles interim transcripts", () => {
    const row: TranscriptSegmentRow = {
      id: "transcript-789",
      session_id: "session-123",
      speaker: "customer",
      text: "I need...",
      is_final: false,
      confidence: null,
      ts: "2024-01-01T00:00:00Z",
    };

    const result = rowToTranscriptEntry(row);

    expect(result.isFinal).toBe(false);
  });
});

describe("getConversationContext", () => {
  let mockClient: SupabaseClient;

  beforeEach(() => {
    mockClient = {
      from: vi.fn(),
    } as unknown as SupabaseClient;
  });

  it("returns formatted conversation text", async () => {
    const sessionId = "session-123";
    const mockRows: TranscriptSegmentRow[] = [
      {
        id: "1",
        session_id: sessionId,
        speaker: "customer",
        text: "I have a question",
        is_final: true,
        confidence: null,
        ts: "2024-01-01T00:00:00Z",
      },
      {
        id: "2",
        session_id: sessionId,
        speaker: "agent",
        text: "How can I help?",
        is_final: true,
        confidence: null,
        ts: "2024-01-01T00:01:00Z",
      },
    ];

    // Create a chainable query object
    const mockQuery: {
      eq: ReturnType<typeof vi.fn>;
      limit: ReturnType<typeof vi.fn>;
    } = {
      eq: vi.fn(),
      limit: vi.fn(),
    };

    mockQuery.eq.mockReturnValue(mockQuery);
    mockQuery.limit.mockResolvedValue({ data: mockRows, error: null });

    const mockOrder = vi.fn().mockReturnValue(mockQuery);
    const mockEq = vi.fn().mockReturnValue({ order: mockOrder });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
    const mockFrom = vi.fn().mockReturnValue({ select: mockSelect });

    mockClient.from = mockFrom;

    const result = await getConversationContext(mockClient, sessionId);

    expect(result).toBe("CUSTOMER: I have a question\nAGENT: How can I help?");
  });

  it("uses default maxTurns of 10", async () => {
    const sessionId = "session-123";

    // Create a chainable query object
    const mockQuery: {
      eq: ReturnType<typeof vi.fn>;
      limit: ReturnType<typeof vi.fn>;
    } = {
      eq: vi.fn(),
      limit: vi.fn(),
    };

    mockQuery.eq.mockReturnValue(mockQuery);
    mockQuery.limit.mockResolvedValue({ data: [], error: null });

    const mockOrder = vi.fn().mockReturnValue(mockQuery);
    const mockEq = vi.fn().mockReturnValue({ order: mockOrder });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
    const mockFrom = vi.fn().mockReturnValue({ select: mockSelect });

    mockClient.from = mockFrom;

    await getConversationContext(mockClient, sessionId);

    expect(mockQuery.limit).toHaveBeenCalledWith(10);
  });

  it("uses custom maxTurns when provided", async () => {
    const sessionId = "session-123";

    // Create a chainable query object
    const mockQuery: {
      eq: ReturnType<typeof vi.fn>;
      limit: ReturnType<typeof vi.fn>;
    } = {
      eq: vi.fn(),
      limit: vi.fn(),
    };

    mockQuery.eq.mockReturnValue(mockQuery);
    mockQuery.limit.mockResolvedValue({ data: [], error: null });

    const mockOrder = vi.fn().mockReturnValue(mockQuery);
    const mockEq = vi.fn().mockReturnValue({ order: mockOrder });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
    const mockFrom = vi.fn().mockReturnValue({ select: mockSelect });

    mockClient.from = mockFrom;

    await getConversationContext(mockClient, sessionId, 5);

    expect(mockQuery.limit).toHaveBeenCalledWith(5);
  });

  it("only includes final transcripts", async () => {
    const sessionId = "session-123";

    // Create a chainable query object
    const mockQuery: {
      eq: ReturnType<typeof vi.fn>;
      limit: ReturnType<typeof vi.fn>;
    } = {
      eq: vi.fn(),
      limit: vi.fn(),
    };

    mockQuery.eq.mockReturnValue(mockQuery);
    mockQuery.limit.mockResolvedValue({ data: [], error: null });

    const mockOrder = vi.fn().mockReturnValue(mockQuery);
    const mockEq = vi.fn().mockReturnValue({ order: mockOrder });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
    const mockFrom = vi.fn().mockReturnValue({ select: mockSelect });

    mockClient.from = mockFrom;

    await getConversationContext(mockClient, sessionId);

    expect(mockQuery.eq).toHaveBeenCalledWith("is_final", true);
  });

  it("returns empty string when no transcripts", async () => {
    const sessionId = "session-123";

    // Create a chainable query object
    const mockQuery: {
      eq: ReturnType<typeof vi.fn>;
      limit: ReturnType<typeof vi.fn>;
    } = {
      eq: vi.fn(),
      limit: vi.fn(),
    };

    mockQuery.eq.mockReturnValue(mockQuery);
    mockQuery.limit.mockResolvedValue({ data: [], error: null });

    const mockOrder = vi.fn().mockReturnValue(mockQuery);
    const mockEq = vi.fn().mockReturnValue({ order: mockOrder });
    const mockSelect = vi.fn().mockReturnValue({ eq: mockEq });
    const mockFrom = vi.fn().mockReturnValue({ select: mockSelect });

    mockClient.from = mockFrom;

    const result = await getConversationContext(mockClient, sessionId);

    expect(result).toBe("");
  });
});
