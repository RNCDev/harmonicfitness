import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useCallback, useState } from "react";
import { ApiError, type Conversation } from "./api";

const stop = () => {};

const m = vi.hoisted(() => ({
  latest: vi.fn(), conversation: vi.fn(), start: vi.fn(), send: vi.fn(), watch: vi.fn(), halt: vi.fn(),
  endJob: null as null | ((state: "done" | "failed", error?: string, code?: "no_model_key" | "key_refused") => void),
}));

vi.mock("./api", async (orig) => {
  const real = await orig<typeof import("./api")>();
  return {
    ...real,
    api: { ...real.api, latestConversation: m.latest, conversation: m.conversation, startConversation: m.start,
      sendMessage: m.send, stop: m.halt },
    useJob: () => {
      const [job, setJob] = useState<{ id: number; state: string; error: string | null; stages: [] } | null>(null);
      m.endJob = (state, error, code) => setJob((j) => (j ? { ...j, state, error: error ?? null, code: code ?? null } : j));
      const watch = useCallback((id: number) => {
        m.watch(id);
        setJob({ id, state: "running", error: null, stages: [] });
      }, []);
      return { job, stop, watch };
    },
  };
});

import { isHistory, LOST_TOUCH, resumable, useConversation } from "./conversation";


const conv = (over: Partial<Conversation>): Conversation => ({
  id: 7, state: "idle", job_id: null, lines: [{ role: "user", text: "hi" }],
  updated_at: new Date().toISOString(), ...over,
});

/** Every stand-in call forgotten, as between tests. */
const fresh = () => {
  m.halt.mockReset(); m.latest.mockReset(); m.conversation.mockReset(); m.start.mockReset(); m.send.mockReset(); m.watch.mockReset();
};
beforeEach(fresh);

const yesterday = () => new Date(Date.now() - 36 * 3600 * 1000).toISOString();
afterEach(() => { vi.useRealTimers(); });

describe("useConversation", () => {
  it("resumes a working conversation by following its job", async () => {
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    const { result } = renderHook(() => useConversation());
    await waitFor(() => expect(m.watch).toHaveBeenCalledWith(42));
    expect(result.current.working).toBe(true);
  });

  it("a scheduled conversation opens on its own, is followed once written, says when it can't be read, and opens once done", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    m.latest.mockResolvedValue(conv({ state: "scheduled", later: { at: new Date().toISOString(), local: "x" } }));
    m.conversation.mockResolvedValue(conv({ state: "working", job_id: 51 }));
    const first = renderHook(() => useConversation());
    await waitFor(() => expect(first.result.current.conv?.state).toBe("scheduled"));
    expect(first.result.current.working).toBe(false);
    expect(isHistory(conv({ state: "scheduled", updated_at: yesterday() }))).toBe(false);
    await act(async () => { vi.advanceTimersByTime(31000); });
    await waitFor(() => expect(m.watch).toHaveBeenCalledWith(51));
    first.unmount();

    // can't be read three times running: says so, and takes it back once one is
    fresh();
    m.latest.mockResolvedValue(conv({ state: "scheduled", later: { at: new Date().toISOString(), local: "x" } }));
    m.conversation.mockRejectedValue(new TypeError("Failed to fetch"));
    const lost = renderHook(() => useConversation());
    await waitFor(() => expect(lost.result.current.conv?.state).toBe("scheduled"));
    await act(async () => { vi.advanceTimersByTime(61000); });
    expect(lost.result.current.error).toBeNull();   // two misses: quiet
    await act(async () => { vi.advanceTimersByTime(30000); });
    await waitFor(() => expect(lost.result.current.error).toBe(LOST_TOUCH));
    m.conversation.mockResolvedValue(conv({ state: "scheduled", later: { at: new Date().toISOString(), local: "x" } }));
    await act(async () => { vi.advanceTimersByTime(30000); });
    await waitFor(() => expect(lost.result.current.error).toBeNull());
    lost.unmount();

    // written while the page was closed: opened
    fresh();
    m.latest.mockResolvedValue(conv({ state: "idle", lines: [{ role: "agent", text: "", audio: { id: "a", name: "W", expires_at: "x" } }],
      later: { at: new Date().toISOString(), local: "x", due: new Date().toISOString(), done: true } }));
    const { result } = renderHook(() => useConversation());
    await waitFor(() => expect(result.current.conv?.id).toBe(7));
    expect(result.current.waiting).toBeNull();
  });

  it("stops working after the reload fails every time, and recovers when a retry works", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    m.conversation.mockRejectedValue(new ApiError(500, "Server is down."));
    const failing = renderHook(() => useConversation());
    await waitFor(() => expect(m.watch).toHaveBeenCalled());
    act(() => m.endJob!("done"));
    await act(async () => { await vi.advanceTimersByTimeAsync(11000); });
    expect(m.conversation).toHaveBeenCalledTimes(4);
    expect(failing.result.current.working).toBe(false);
    expect(failing.result.current.error).toBe("Server is down.");
    failing.unmount();

    fresh();
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    m.conversation.mockRejectedValueOnce(new ApiError(500, "x"))
      .mockResolvedValue(conv({ lines: [{ role: "user", text: "hi" }, { role: "agent", text: "Done" }] }));
    const { result } = renderHook(() => useConversation());
    await waitFor(() => expect(m.watch).toHaveBeenCalled());
    act(() => m.endJob!("done"));
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(result.current.conv?.lines[1]?.text).toBe("Done");
    expect(result.current.working).toBe(false);
  });

  it("opens fresh: only a working turn, or today's waiting on the listener, is picked up again", async () => {
    for (const c of [conv({}), conv({ state: "failed", lines: [{ role: "agent", text: "That didn't work." }] }),
      conv({ updated_at: yesterday(), lines: [{ role: "agent", text: "Which kit?" }] })]) {
      m.latest.mockResolvedValue(c);
      const { result, unmount } = renderHook(() => useConversation());
      await waitFor(() => expect(m.latest).toHaveBeenCalled());
      await act(async () => { await Promise.resolve(); });
      expect(result.current.conv).toBeNull();
      expect(result.current.working).toBe(false);
      expect(m.watch).not.toHaveBeenCalled();
      unmount();
      m.latest.mockReset();
    }

    // resumable: working, or today's and waiting on the listener; never failed, recorded or yesterday's
    const asked = [{ role: "user" as const, text: "hi" }, { role: "agent" as const, text: "Which kit?" }];
    expect(resumable(conv({ state: "working", job_id: 1 }))).toBe(true);
    expect(resumable(conv({ lines: asked }))).toBe(true);
    expect(resumable(conv({ offer: { name: "Legs", coach: "Coach Reed", chars: 100, usd: 0.1, service: "fish" } }))).toBe(true);
    expect(resumable(conv({}))).toBe(false);   // the listener spoke last, nothing pending
    expect(resumable(conv({ state: "failed", lines: asked }))).toBe(false);
    expect(resumable(conv({ lines: asked, updated_at: yesterday() }))).toBe(false);
    expect(resumable(conv({ lines: [...asked, { role: "agent", text: "", audio: { id: "a", name: "Legs", expires_at: "2099-01-01T00:00:00Z" } },
      { role: "agent", text: "Earbuds in." }] }))).toBe(false);

    // history: an earlier local day only, never a working turn
    expect(isHistory(conv({ updated_at: yesterday() }))).toBe(true);
    expect(isHistory(conv({}))).toBe(false);
    expect(isHistory(conv({ state: "working", updated_at: yesterday() }))).toBe(false);
    expect(isHistory(conv({ updated_at: null }))).toBe(false);
    expect(isHistory(null)).toBe(false);
  });

  it("the first message starts a conversation, the next continues it, and New chat starts over", async () => {
    m.latest.mockResolvedValue(conv({ id: 7 }));
    m.start.mockResolvedValueOnce({ id: 8, job_id: 50 }).mockResolvedValueOnce({ id: 9, job_id: 52 });
    m.send.mockResolvedValue({ job_id: 51 });
    const { result } = renderHook(() => useConversation());
    await waitFor(() => expect(m.latest).toHaveBeenCalled());
    await act(async () => { expect(await result.current.send("A 20-minute workout")).toBe(true); });
    expect(m.start).toHaveBeenCalledWith("A 20-minute workout", expect.anything(), undefined, undefined);
    expect(result.current.conv?.id).toBe(8);
    m.conversation.mockResolvedValue(conv({ id: 8 }));
    act(() => m.endJob!("done"));
    await waitFor(() => expect(result.current.working).toBe(false));
    await act(async () => { expect(await result.current.send("and shorter")).toBe(true); });
    expect(m.send).toHaveBeenCalledWith(8, "and shorter", expect.anything(), undefined);
    m.conversation.mockResolvedValue(conv({ id: 8 }));
    act(() => m.endJob!("done"));
    await waitFor(() => expect(result.current.working).toBe(false));
    act(() => result.current.reset());
    expect(result.current.conv).toBeNull();
    await act(async () => { await result.current.send("another"); });
    expect(m.start).toHaveBeenCalledTimes(2);
    expect(result.current.conv?.id).toBe(9);
  });

  it("the first screen offers today's waiting conversation, and a new message there drops it", async () => {
    m.latest.mockResolvedValue(conv({ lines: [{ role: "user", text: "hi" }, { role: "agent", text: "1. How's the knee?" }] }));
    const resumed = renderHook(() => useConversation());
    await waitFor(() => expect(resumed.result.current.waiting?.id).toBe(7));
    expect(resumed.result.current.conv).toBeNull();
    expect(resumed.result.current.working).toBe(false);
    act(() => resumed.result.current.resume());
    expect(resumed.result.current.conv?.id).toBe(7);
    expect(resumed.result.current.waiting).toBeNull();
    resumed.unmount();

    fresh();
    m.latest.mockResolvedValue(conv({ lines: [{ role: "agent", text: "Which kit?" }] }));
    m.start.mockResolvedValue({ id: 8, job_id: 50 });
    const { result } = renderHook(() => useConversation());
    await waitFor(() => expect(result.current.waiting?.id).toBe(7));
    await act(async () => { await result.current.send("A 20-minute workout"); });
    expect(m.start).toHaveBeenCalled();
    expect(result.current.waiting).toBeNull();
    expect(result.current.conv?.id).toBe(8);
  });

  it("Stop ends the chat: the turn is stopped and the page goes back to the first screen", async () => {
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    m.halt.mockResolvedValue({ stopping: true });
    const { result } = renderHook(() => useConversation());
    await waitFor(() => expect(result.current.conv?.id).toBe(7));
    await act(async () => { await result.current.halt(); });
    expect(m.halt).toHaveBeenCalledWith(7);
    expect(result.current.conv).toBeNull();
    expect(result.current.working).toBe(false);
  });

  it("a Stop that can't be sent keeps the chat open, with the error", async () => {
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    m.halt.mockRejectedValue(new Error("offline"));
    const { result } = renderHook(() => useConversation());
    await waitFor(() => expect(result.current.conv?.id).toBe(7));
    await act(async () => { await result.current.halt(); });
    expect(result.current.conv?.id).toBe(7);
    expect(result.current.error).toBeTruthy();
  });

  it("sets noKey, offering Settings, when a key is missing or refused, and only then", async () => {
    m.latest.mockResolvedValue(undefined);
    m.start.mockRejectedValue(new ApiError(409, "Add a key for Claude in Settings first.", undefined, "no_model_key"));
    const missing = renderHook(() => useConversation());
    await act(async () => { expect(await missing.result.current.send("a workout")).toBe(false); });
    expect(missing.result.current.noKey).toBe(true);
    expect(missing.result.current.error).toBe("Add a key for Claude in Settings first.");
    expect(missing.result.current.working).toBe(false);
    missing.unmount();

    fresh();
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    m.conversation.mockResolvedValue(conv({ state: "failed" }));
    const refused = renderHook(() => useConversation());
    await waitFor(() => expect(m.watch).toHaveBeenCalledWith(42));
    act(() => m.endJob!("failed", "Claude refused the key. Replace it in Settings.", "key_refused"));
    await waitFor(() => expect(refused.result.current.error).toBe("Claude refused the key. Replace it in Settings."));
    expect(refused.result.current.noKey).toBe(true);
    refused.unmount();

    fresh();
    m.latest.mockResolvedValue(conv({ state: "working", job_id: 42 }));
    m.conversation.mockResolvedValue(conv({ state: "failed" }));
    const { result } = renderHook(() => useConversation());
    await waitFor(() => expect(m.watch).toHaveBeenCalledWith(42));
    // the wording mentions Settings, but without a code nothing is offered: the page reads codes, not words
    act(() => m.endJob!("failed", "Something in Settings went wrong; try again"));
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.noKey).toBe(false);
  });
});
