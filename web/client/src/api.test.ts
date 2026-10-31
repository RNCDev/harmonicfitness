import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, call, checkBalances } from "./api";

function answer(status: number, body: string | null) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { status })));
}

afterEach(() => vi.unstubAllGlobals());

describe("call", () => {
  it.each([200, 201, 204])("reads an empty %i as no body", async (status) => {
    answer(status, status === 204 ? null : "");
    await expect(call("POST", "/api/x")).resolves.toBeUndefined();
  });

  it("reads a JSON body", async () => {
    answer(201, JSON.stringify({ id: 3 }));
    await expect(call("POST", "/api/x")).resolves.toEqual({ id: 3 });
  });

  it("gives the server's detail on a refusal", async () => {
    answer(409, JSON.stringify({ detail: "That username is taken." }));
    await expect(call("POST", "/api/x")).rejects.toEqual(new ApiError(409, "That username is taken."));
  });
});

describe("checkBalances", () => {
  function answers(...bodies: unknown[]) {
    const f = vi.fn(async () => new Response(JSON.stringify(bodies.shift()), { status: 200 }));
    vi.stubGlobal("fetch", f);
    return f;
  }

  it("starts a check and reads its result once the job is done", async () => {
    const f = answers({ id: 7 }, { id: 7, state: "queued", error: null, result: null },
      { id: 7, state: "done", error: null, result: { balances: { fish: { ok: true, usd: 3 } } } });
    await expect(checkBalances({ every: 1 })).resolves.toEqual({ fish: { ok: true, usd: 3 } });
    expect(f.mock.calls.map((c) => (c as unknown[])[0])).toEqual(["/api/balances", "/api/jobs/7", "/api/jobs/7"]);
  });

  it("gives up on a failed job, or one that takes too long", async () => {
    answers({ id: 1 }, { id: 1, state: "failed", error: "x", result: null });
    await expect(checkBalances({ every: 1 })).resolves.toBeNull();
    answers({ id: 2 }, { id: 2, state: "queued", error: null, result: null });
    await expect(checkBalances({ every: 1, within: 0 })).resolves.toBeNull();
  });
});
