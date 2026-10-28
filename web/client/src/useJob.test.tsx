import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { useJob } from "./api";

type Reply = { id: number; state: string; error: string | null } | 401;
// the job read goes through fetch; mockResolvedValue / mockRejectedValue set what it answers
const m = { job: vi.fn<() => Promise<Reply>>() };
const fakeFetch = async () => {
  const r = await m.job();
  return r === 401
    ? new Response("", { status: 401 })
    : new Response(JSON.stringify(r), { status: 200, headers: { "Content-Type": "application/json" } });
};

class FakeSource {
  static all: FakeSource[] = [];
  static CLOSED = 2;
  readyState = 1;
  onmessage: ((e: { data: string; lastEventId: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  listeners: Record<string, (e: { data: string }) => void> = {};
  constructor(public url: string) {
    FakeSource.all.push(this);
  }
  addEventListener(name: string, fn: (e: { data: string }) => void) {
    this.listeners[name] = fn;
  }
  close() {
    this.readyState = 2;
  }
  drop() {
    this.readyState = 2;
    this.onerror?.();
  }
}

beforeEach(() => {
  FakeSource.all = [];
  m.job.mockReset();
  vi.useFakeTimers();
  vi.stubGlobal("EventSource", FakeSource);
  vi.stubGlobal("fetch", fakeFetch);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
const after = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

describe("useJob", () => {
  it("follows again after a dropped stream while running", async () => {
    m.job.mockResolvedValue({ id: 5, state: "running", error: null });
    const { result } = renderHook(() => useJob(() => {}));
    act(() => result.current.watch(5));
    expect(FakeSource.all).toHaveLength(1);
    act(() => FakeSource.all[0].onmessage?.({ data: '{"stage":"folder"}', lastEventId: "1" }));

    FakeSource.all[0].drop();
    await flush();
    await after(1999);
    expect(FakeSource.all).toHaveLength(1);
    await after(1);
    expect(FakeSource.all).toHaveLength(2);
    // the replayed event is not shown twice
    act(() => FakeSource.all[1].onmessage?.({ data: '{"stage":"folder"}', lastEventId: "1" }));
    expect(result.current.job?.stages).toHaveLength(1);

    // a stream that brought an event starts the waits over; one that brought none waits longer
    FakeSource.all[1].drop();
    await flush();
    await after(2000);
    expect(FakeSource.all).toHaveLength(3);
    FakeSource.all[2].drop();
    await flush();
    await after(4999);
    expect(FakeSource.all).toHaveLength(3);
    await after(1);
    expect(FakeSource.all).toHaveLength(4);
    FakeSource.all[3].drop();
    await flush();
    await after(9999);
    expect(FakeSource.all).toHaveLength(4);
    await after(1);
    expect(FakeSource.all).toHaveLength(5);
    FakeSource.all[4].drop();
    await flush();
    await after(10000);
    expect(FakeSource.all).toHaveLength(6);
  });

  it("stops after the state event", async () => {
    m.job.mockResolvedValue({ id: 5, state: "done", error: null });
    const { result } = renderHook(() => useJob(() => {}));
    act(() => result.current.watch(5));
    act(() => FakeSource.all[0].listeners.state({ data: '{"state":"done","error":null}' }));
    await flush();
    await after(60000);
    expect(FakeSource.all).toHaveLength(1);
    expect(result.current.job?.state).toBe("done");
  });

  it("stops once a dropped stream finds the job ended", async () => {
    m.job.mockResolvedValue({ id: 5, state: "failed", error: "interrupted" });
    const { result } = renderHook(() => useJob(() => {}));
    act(() => result.current.watch(5));
    FakeSource.all[0].drop();
    await flush();
    await after(60000);
    expect(FakeSource.all).toHaveLength(1);
    expect(result.current.job?.state).toBe("failed");
  });

  it("stops on sign-out", async () => {
    const out = vi.fn();
    m.job.mockResolvedValue({ id: 5, state: "running", error: null });
    const { result } = renderHook(() => useJob(out));
    act(() => result.current.watch(5));
    FakeSource.all[0].drop();
    await flush();
    // signed out while waiting: the next read is a 401
    m.job.mockResolvedValue(401);
    act(() => result.current.stop());
    await after(60000);
    expect(FakeSource.all).toHaveLength(1);

    // and a 401 on the read itself ends it too
    const { result: r2 } = renderHook(() => useJob(out));
    act(() => r2.current.watch(6));
    FakeSource.all[FakeSource.all.length - 1].drop();
    await flush();
    await after(60000);
    expect(out).toHaveBeenCalledTimes(1);
    expect(FakeSource.all).toHaveLength(2);
  });
});
