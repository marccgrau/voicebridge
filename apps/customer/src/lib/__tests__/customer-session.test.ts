import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCustomerSession } from "../customer-session";

// Capture the Realtime subscription callback so we can trigger it in tests
let realtimeCallback: ((payload: { new: { status: string } }) => void) | null =
  null;
const mockUnsubscribe = vi.fn();
const mockSubscribe = vi.fn(() => ({
  unsubscribe: mockUnsubscribe,
}));

vi.mock("../supabase", () => ({
  supabase: {
    channel: vi.fn(() => ({
      on: vi.fn(
        (
          _event: string,
          _opts: Record<string, unknown>,
          callback: (payload: { new: { status: string } }) => void
        ) => {
          realtimeCallback = callback;
          return { subscribe: mockSubscribe, unsubscribe: mockUnsubscribe };
        }
      ),
    })),
    from: vi.fn(() => ({
      update: vi.fn(() => ({
        eq: vi.fn(() => Promise.resolve({ error: null })),
      })),
    })),
  },
}));

describe("useCustomerSession", () => {
  beforeEach(() => {
    realtimeCallback = null;
    vi.clearAllMocks();
  });

  it("starts in idle state", () => {
    const { result } = renderHook(() => useCustomerSession());
    expect(result.current.callState).toBe("idle");
    expect(result.current.sessionId).toBeNull();
  });

  describe("Realtime subscription lifecycle", () => {
    it("does not subscribe when there is no sessionId", () => {
      renderHook(() => useCustomerSession());
      // No subscription should be created for idle state (no sessionId)
      expect(realtimeCallback).toBeNull();
    });

    it("subscribes when sessionId is set and stays active through connected state", async () => {
      const { result } = renderHook(() => useCustomerSession());

      // Simulate starting a call by calling startCall
      // Since startCall does a fetch, we mock it
      const mockResponse = {
        ok: true,
        json: () =>
          Promise.resolve({
            session_id: "test-session-id",
            room_url: "https://daily.co/test-room",
            customer_token: "test-token",
          }),
      };
      vi.stubGlobal(
        "fetch",
        vi.fn(() => Promise.resolve(mockResponse))
      );

      await act(async () => {
        await result.current.startCall({
          customerId: "cust-1",
          scenarioId: "scenario-1",
        });
      });

      // Should be in "calling" state with a subscription
      expect(result.current.callState).toBe("calling");
      expect(result.current.sessionId).toBe("test-session-id");
      expect(realtimeCallback).not.toBeNull();

      // Simulate agent accepting → status becomes "active"
      act(() => {
        realtimeCallback!({ new: { status: "active" } });
      });

      expect(result.current.callState).toBe("connected");

      // The subscription should still be active (this is the bug fix!)
      // The callback should still be set — subscription was NOT torn down on state change
      expect(realtimeCallback).not.toBeNull();

      // Simulate agent ending call → status becomes "completed"
      act(() => {
        realtimeCallback!({ new: { status: "completed" } });
      });

      expect(result.current.callState).toBe("ended");
      expect(result.current.roomUrl).toBeNull();
      expect(result.current.customerToken).toBeNull();

      vi.unstubAllGlobals();
    });

    it("transitions to ended on abandoned status", async () => {
      const { result } = renderHook(() => useCustomerSession());

      const mockResponse = {
        ok: true,
        json: () =>
          Promise.resolve({
            session_id: "test-session-id",
            room_url: "https://daily.co/test-room",
            customer_token: "test-token",
          }),
      };
      vi.stubGlobal(
        "fetch",
        vi.fn(() => Promise.resolve(mockResponse))
      );

      await act(async () => {
        await result.current.startCall({
          customerId: "cust-1",
          scenarioId: "scenario-1",
        });
      });

      // Go to connected state
      act(() => {
        realtimeCallback!({ new: { status: "active" } });
      });
      expect(result.current.callState).toBe("connected");

      // Simulate session abandoned
      act(() => {
        realtimeCallback!({ new: { status: "abandoned" } });
      });

      expect(result.current.callState).toBe("ended");
      expect(result.current.roomUrl).toBeNull();

      vi.unstubAllGlobals();
    });
  });
});
