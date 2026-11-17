import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, call, checkBalances, NotSignedIn, setAuthLost } from "./api";

function answer(status: number, body: string | null) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(body, { status })));
}

afterEach(() => vi.unstubAllGlobals());

describe("call", () => {
  it("reads an empty answer as no body, a JSON one as its body, and a refusal as the server's detail", async () => {
    for (const status of [200, 201, 204]) {
      answer(status, status === 204 ? null : "");
      await expect(call("POST", "/api/x")).resolves.toBeUndefined();
    }
    answer(201, JSON.stringify({ id: 3 }));
    await expect(call("POST", "/api/x")).resolves.toEqual({ id: 3 });
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

  it("starts a check and reads its result once the job is done, else gives up", async () => {
    const f = answers({ id: 7 }, { id: 7, state: "queued", error: null, result: null },
      { id: 7, state: "done", error: null, result: { balances: { fish: { ok: true, usd: 3 } } } });
    await expect(checkBalances({ every: 1 })).resolves.toEqual({ fish: { ok: true, usd: 3 } });
    expect(f.mock.calls.map((c) => (c as unknown[])[0])).toEqual(["/api/balances", "/api/jobs/7", "/api/jobs/7"]);
    // and gives up on a failed job, or one that takes too long
    answers({ id: 1 }, { id: 1, state: "failed", error: "x", result: null });
    await expect(checkBalances({ every: 1 })).resolves.toBeNull();
    answers({ id: 2 }, { id: 2, state: "queued", error: null, result: null });
    await expect(checkBalances({ every: 1, within: 0 })).resolves.toBeNull();
  });
});

describe("a lost session", () => {
  it("tells the app once, from any call, and still throws NotSignedIn", async () => {
    const lost = vi.fn();
    const off = setAuthLost(lost);
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 401 })));
    await expect(call("GET", "/api/me")).rejects.toBeInstanceOf(NotSignedIn);
    await expect(api.importFolder(new Blob(["x"]))).rejects.toBeInstanceOf(NotSignedIn);
    expect(lost).toHaveBeenCalledTimes(2);
    off();
    await expect(call("GET", "/api/me")).rejects.toBeInstanceOf(NotSignedIn);
    expect(lost).toHaveBeenCalledTimes(2);   // let go
  });
});
