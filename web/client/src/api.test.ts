import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, call } from "./api";

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
