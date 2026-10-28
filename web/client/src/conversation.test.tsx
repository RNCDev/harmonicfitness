import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useCallback, useState } from "react";
import { ApiError, type Conversation } from "./api";

const stop = () => {};

const m = vi.hoisted(() => ({
  latest: vi.fn(), conversation: vi.fn(), start: vi.fn(), watch: vi.fn(),
  endJob: null as null | ((state: "done" | "failed") => void),
}));

vi.mock("./api", async (orig) => {
  const real = await orig<typeof import("./api")>();
  return {
    ...real,
    api: { ...real.api, latestConversation: m.latest, conversation: m.conversation, startConversation: m.start },
    useJob: () => {
      const [job, setJob] = useState<{ id: number; state: string; error: null; stages: [] } | null>(null);
      m.endJob = (state) => setJob((j) => (j ? { ...j, state } : j));
      const watch = useCallback((id: number) => {
        m.watch(id);
        setJob({ id, state: "running", error: null, stages: [] });
      }, []);
      return { job, stop, watch };
    },
  };
});

import { useConversation } from "./conversation";

const out = () => {};

const conv = (over: Partial<Conversation>): Conversation => ({
  id: 7, state: "idle", job_id: null, lines: [{ role: "user", text: "hi" }], question: null, plan: null, ...over,
});

beforeEach(() => { m.latest.mockReset(); m.conversation.mockReset(); m.start.mockReset(); m.watch.mockReset(); });
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
});
