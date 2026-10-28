import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useCallback, useState } from "react";
import { ApiError, type Conversation } from "./api";

const stop = () => {};

const m = vi.hoisted(() => ({
  latest: vi.fn(), conversation: vi.fn(), start: vi.fn(), send: vi.fn(), watch: vi.fn(),
  endJob: null as null | ((state: "done" | "failed", error?: string) => void),
}));

vi.mock("./api", async (orig) => {
  const real = await orig<typeof import("./api")>();
  return {
    ...real,
    api: { ...real.api, latestConversation: m.latest, conversation: m.conversation, startConversation: m.start,
      sendMessage: m.send },
    useJob: () => {
      const [job, setJob] = useState<{ id: number; state: string; error: string | null; stages: [] } | null>(null);
      m.endJob = (state, error) => setJob((j) => (j ? { ...j, state, error: error ?? null } : j));
      const watch = useCallback((id: number) => {
        m.watch(id);
        setJob({ id, state: "running", error: null, stages: [] });
      }, []);
      return { job, stop, watch };
    },
  };
});

import { isHistory, useConversation } from "./conversation";

const out = () => {};

const conv = (over: Partial<Conversation>): Conversation => ({
  id: 7, state: "idle", job_id: null, lines: [{ role: "user", text: "hi" }], question: null, plan: null,
  updated_at: new Date().toISOString(), ...over,
});

beforeEach(() => {
  m.latest.mockReset(); m.conversation.mockReset(); m.start.mockReset(); m.send.mockReset(); m.watch.mockReset();
});

const yesterday = () => new Date(Date.now() - 36 * 3600 * 1000).toISOString();
const PLAN = { format: "Sets", equipment: "none", rows: [], left_out: "", total_seconds: 1200 };
const ASKED = { questions: [], tool_call_id: "a1" };
afterEach(() => { vi.useRealTimers(); });

describe("useConversation", () => {
  it("resumes a working conversation by following its job", async () => {
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    const { result } = renderHook(() => useConversation(out));
    await waitFor(() => expect(m.watch).toHaveBeenCalledWith(42));
    expect(result.current.working).toBe(true);
  });

  it("sets noKey when there is no model key", async () => {
    m.latest.mockResolvedValue(undefined);
    m.start.mockRejectedValue(new ApiError(409, "Add a key for Claude in Keys first."));
    const { result } = renderHook(() => useConversation(out));
    await act(async () => { expect(await result.current.send("a workout")).toBe(false); });
    expect(result.current.noKey).toBe(true);
    expect(result.current.error).toBe("Add a key for Claude in Keys first.");
    expect(result.current.working).toBe(false);
  });

  it("stops working after the reload fails every time, and shows the error", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    m.conversation.mockRejectedValue(new ApiError(500, "Server is down."));
    const { result } = renderHook(() => useConversation(out));
    await waitFor(() => expect(m.watch).toHaveBeenCalled());
    act(() => m.endJob!("done"));
    await act(async () => { await vi.advanceTimersByTimeAsync(11000); });
    expect(m.conversation).toHaveBeenCalledTimes(4);
    expect(result.current.working).toBe(false);
    expect(result.current.error).toBe("Server is down.");
  });

  it("recovers when a retry of the reload works", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    m.conversation.mockRejectedValueOnce(new ApiError(500, "x"))
      .mockResolvedValue(conv({ lines: [{ role: "user", text: "hi" }, { role: "agent", text: "Done" }] }));
    const { result } = renderHook(() => useConversation(out));
    await waitFor(() => expect(m.watch).toHaveBeenCalled());
    act(() => m.endJob!("done"));
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(result.current.conv?.lines[1]?.text).toBe("Done");
    expect(result.current.working).toBe(false);
  });

  it("lets a failed conversation be written to again", async () => {
    m.latest.mockResolvedValue(conv({ state: "failed",
      lines: [{ role: "agent", text: "That didn't work: it stopped." }] }));
    const { result } = renderHook(() => useConversation(out));
    await waitFor(() => expect(result.current.conv?.state).toBe("failed"));
    expect(result.current.working).toBe(false);
    expect(result.current.conv?.lines[0].text).toMatch(/didn't work/);
  });

  it("Start always begins a new conversation; the text box goes on with the open one", async () => {
    m.latest.mockResolvedValue(conv({ id: 7 }));
    m.start.mockResolvedValue({ id: 8, job_id: 50 });
    m.send.mockResolvedValue({ job_id: 51 });
    const { result } = renderHook(() => useConversation(out));
    await waitFor(() => expect(result.current.conv?.id).toBe(7));
    await act(async () => { expect(await result.current.start("A 20-minute workout")).toBe(true); });
    expect(m.start).toHaveBeenCalledWith("A 20-minute workout", expect.anything());
    expect(m.send).not.toHaveBeenCalled();
    expect(result.current.conv?.id).toBe(8);
    expect(result.current.conv?.lines).toEqual([{ role: "user", text: "A 20-minute workout" }]);
    m.conversation.mockResolvedValue(conv({ id: 8 }));
    act(() => m.endJob!("done"));
    await waitFor(() => expect(result.current.working).toBe(false));
    await act(async () => { expect(await result.current.send("and shorter")).toBe(true); });
    expect(m.send).toHaveBeenCalledWith(8, "and shorter", expect.anything());
    expect(m.start).toHaveBeenCalledTimes(1);
  });

  it("shows an earlier day's conversation as history", async () => {
    m.latest.mockResolvedValue(conv({ state: "waiting", plan: PLAN, question: ASKED, updated_at: yesterday() }));
    const { result } = renderHook(() => useConversation(out));
    await waitFor(() => expect(result.current.conv?.state).toBe("waiting"));
    expect(result.current.history).toBe(true);
    expect(result.current.conv?.lines[0].text).toBe("hi");   // its lines stay
  });

  it("history: an earlier local day only, never a working turn", () => {
    expect(isHistory(conv({ updated_at: yesterday() }))).toBe(true);
    expect(isHistory(conv({}))).toBe(false);
    expect(isHistory(conv({ state: "working", updated_at: yesterday() }))).toBe(false);
    expect(isHistory(conv({ updated_at: null }))).toBe(false);
    expect(isHistory(null)).toBe(false);
  });

  it("offers Keys when a turn fails for want of a key", async () => {
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    m.conversation.mockResolvedValue(conv({ state: "failed" }));
    const { result } = renderHook(() => useConversation(out));
    await waitFor(() => expect(m.watch).toHaveBeenCalledWith(42));
    act(() => m.endJob!("failed", "Claude refused the key. Replace it in Keys."));
    await waitFor(() => expect(result.current.error).toBe("Claude refused the key. Replace it in Keys."));
    expect(result.current.noKey).toBe(true);
  });

  it("no Keys button for a failure that isn't about keys", async () => {
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    m.conversation.mockResolvedValue(conv({ state: "failed" }));
    const { result } = renderHook(() => useConversation(out));
    await waitFor(() => expect(m.watch).toHaveBeenCalledWith(42));
    act(() => m.endJob!("failed", "this turn ran too long; try again with less to do"));
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.noKey).toBe(false);
  });
});
