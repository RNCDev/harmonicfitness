import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { App } from "./App";

afterEach(() => vi.unstubAllGlobals());

describe("the app", () => {
  it("asks nothing else of the server until it knows who is signed in", async () => {
    let answer: (r: Response) => void = () => {};
    const fetched: string[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      fetched.push(url);
      if (url === "/api/me") return new Promise<Response>((r) => { answer = r; });
      if (url === "/api/auth") {
        return Promise.resolve(new Response(JSON.stringify({ app_name: "HarmonicFitness", registration: true, version: "" })));
      }
      return Promise.resolve(new Response(null, { status: 401 }));
    }));
    render(<App />);
    await new Promise((r) => setTimeout(r, 20));
    expect(fetched).toEqual(["/api/me"]);
    answer(new Response(null, { status: 401 }));
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(fetched.filter((u) => u.startsWith("/api/keys") || u.startsWith("/api/conversations"))).toEqual([]);
  });
});
