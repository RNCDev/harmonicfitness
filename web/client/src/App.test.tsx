import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { App } from "./App";

afterEach(() => vi.unstubAllGlobals());

const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status }));

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
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
    expect(fetched.filter((u) => u.startsWith("/api/start") || u.startsWith("/api/conversations"))).toEqual([]);
  });

  it("shows the starter before the start screen's answer, asks for it once, and fills it in when it comes", async () => {
    const starts: ((r: Response) => void)[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url === "/api/me") return json({ app_name: "HarmonicFitness", username: "ana", has_password: true, version: "", minutes: 20 });
      if (url === "/api/start") return new Promise<Response>((r) => { starts.push(r); });
      if (url === "/api/conversations/latest") return Promise.resolve(new Response(null, { status: 204 }));
      return Promise.resolve(new Response(null, { status: 404 }));
    }));
    render(<App />);
    // the first render in a cold CI runner took 1.3 s, past findBy's 1 s default
    const plan = await screen.findByRole("region", { name: "Plan a workout" }, { timeout: 5000 });
    expect(plan).toHaveAttribute("aria-busy", "true");   // the sentence is up while the answer is on its way
    expect(screen.getByRole("button", { name: "Plan my workout" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "New workout" })).toBeNull();   // nothing to clear yet
    expect(screen.getByRole("button", { name: "20 minutes left" })).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    expect(starts).toHaveLength(1);
    starts[0](new Response(JSON.stringify({ coaches: [{ slug: "coach-wade-openrouter", name: "Coach Wade", first: "Wade",
      service: "openrouter", service_name: "OpenRouter", ready: true, own: false, current: true }], kits: [], minutes: 30,
      limits: [], suggest: null, setup_quick: false })));
    await waitFor(() => expect(screen.getByRole("button", { name: "Plan my workout" })).toBeEnabled());
    expect(screen.getByRole("region", { name: "Plan a workout" })).toHaveAttribute("aria-busy", "false");
    expect(screen.getByRole("button", { name: "Coach: Wade" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeEnabled();
    expect(starts).toHaveLength(1);
  });
});
