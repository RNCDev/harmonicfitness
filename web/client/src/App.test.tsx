import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

  it("welcomes a listener with no key, and offers the starter once the key is saved", async () => {
    const gemini = { service: "gemini", name: "Gemini", key_page: "https://g.example", set: false, updated_at: null };
    const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status }));
    const put = vi.fn(), chose = vi.fn();
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/me") return json({ app_name: "HarmonicFitness", username: "ana", has_password: true, version: "" });
      if (url === "/api/keys") return json([{ ...gemini, kind: "model" }, { ...gemini, kind: "voice" }]);
      if (url === "/api/keys/gemini" && init?.method === "PUT") { put(); return Promise.resolve(new Response(null, { status: 204 })); }
      if (url === "/api/writer" && init?.method === "PUT") { chose(init.body); return Promise.resolve(new Response(null, { status: 204 })); }
      if (url === "/api/conversations/latest") return Promise.resolve(new Response(null, { status: 204 }));
      return Promise.resolve(new Response(null, { status: 404 }));
    }));
    render(<App />);
    // the first render in a cold CI runner took 1.3 s, past findBy's 1 s default
    fireEvent.click(await screen.findByRole("button", { name: /^Gemini/ }, { timeout: 5000 }));
    const box = await screen.findByLabelText("Gemini key");
    await waitFor(() => expect(box).toHaveFocus());
    expect(screen.getByRole("textbox", { name: "Message" })).toBeDisabled();
    fireEvent.change(box, { target: { value: "AIza-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("region", { name: "Plan a workout" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New workout" })).toBeNull();   // nothing to clear yet
    expect(put).toHaveBeenCalledTimes(1);
    expect(chose).toHaveBeenCalledWith(JSON.stringify({ service: "gemini" }));
    expect(screen.queryByText("Welcome to HarmonicFitness")).toBeNull();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeEnabled();
  });

  it("shows the sentence before the start screen's answer, and asks for it once as the keys arrive", async () => {
    const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status }));
    const gemini = { service: "gemini", name: "Gemini", key_page: "https://g.example", updated_at: null };
    const starts: ((r: Response) => void)[] = [];
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url === "/api/me") return json({ app_name: "HarmonicFitness", username: "ana", has_password: true, version: "" });
      if (url === "/api/keys") return json([{ ...gemini, kind: "model", set: true }, { ...gemini, kind: "voice", set: true }]);
      if (url === "/api/start") return new Promise<Response>((r) => { starts.push(r); });
      if (url === "/api/conversations/latest") return Promise.resolve(new Response(null, { status: 204 }));
      return Promise.resolve(new Response(null, { status: 404 }));
    }));
    render(<App />);
    const plan = await screen.findByRole("region", { name: "Plan a workout" }, { timeout: 5000 });
    expect(plan).toHaveAttribute("aria-busy", "true");   // the sentence is up while the answer is on its way
    expect(screen.getByRole("button", { name: "Plan my workout" })).toBeDisabled();
    await new Promise((r) => setTimeout(r, 50));
    expect(starts).toHaveLength(1);   // the keys arriving is not a change
    starts[0](new Response(JSON.stringify({ coaches: [{ slug: "coach-wade-gemini", name: "Coach Wade", first: "Wade",
      service: "gemini", service_name: "Gemini", ready: true, own: false, current: true }], kits: [], minutes: 30,
      limits: [], suggest: null, setup_quick: false })));
    await waitFor(() => expect(screen.getByRole("button", { name: "Plan my workout" })).toBeEnabled());
    expect(screen.getByRole("region", { name: "Plan a workout" })).toHaveAttribute("aria-busy", "false");
    expect(screen.getByRole("button", { name: "Coach: Wade" })).toBeInTheDocument();
    expect(starts).toHaveLength(1);
  });

  it("shows the saved sky, and switches it from Settings, putting it back if the save is refused", async () => {
    const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status }));
    const saved: string[] = [];
    let refuse = false;
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/me") return json({ app_name: "HarmonicFitness", username: "ana", has_password: true, version: "", sky: "field" });
      if (url === "/api/keys") return json([]);
      if (url === "/api/sky" && init?.method === "PUT") {
        saved.push(String(init.body));
        return Promise.resolve(new Response(null, { status: refuse ? 500 : 204 }));
      }
      if (url === "/api/conversations/latest") return Promise.resolve(new Response(null, { status: 204 }));
      return Promise.resolve(new Response(null, { status: 404 }));
    }));
    const { container } = render(<App />);
    const sky = () => container.querySelector(".sky")?.getAttribute("data-sky");
    await waitFor(() => expect(sky()).toBe("field"));
    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    const flow = await screen.findByRole("button", { name: /^Flow/ });
    expect(screen.getByRole("button", { name: /^Field/ })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(flow);
    expect(sky()).toBe("flow");
    await waitFor(() => expect(saved).toEqual([JSON.stringify({ sky: "flow" })]));
    expect(flow).toHaveAttribute("aria-pressed", "true");
    refuse = true;
    fireEvent.click(screen.getByRole("button", { name: /^Field/ }));
    await waitFor(() => expect(saved).toHaveLength(2));
    await waitFor(() => expect(sky()).toBe("flow"));   // refused: back as it was
  });

  it("gives Logs an address, and holds the keyboard inside Settings while it's open", async () => {
    const json = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status }));
    const claude = { service: "anthropic", name: "Claude", key_page: "https://a.example", set: true, updated_at: null,
      kind: "model", writer: true };
    vi.stubGlobal("fetch", vi.fn((url: string) => {
      if (url === "/api/me") return json({ app_name: "HarmonicFitness", username: "ana", has_password: true, version: "" });
      if (url === "/api/keys") return json([claude]);
      if (url === "/api/workouts") return json({ workouts: [] });
      if (url === "/api/level") return json({ level: "novice", set: false, choices: [] });
      if (url === "/api/start") return json({ coaches: [], kits: [], minutes: 25, limits: [], suggest: null, setup_quick: false });
      return Promise.resolve(new Response(null, { status: 204 }));
    }));
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Logs" }, { timeout: 5000 }));
    expect(window.location.hash).toBe("#logs");
    // an empty list says what will show here, and offers the way there
    expect(await screen.findByText("Your workouts show here once you've recorded one.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Plan a workout" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back to the chat" }));
    expect(window.location.hash).toBe("");
    expect(screen.queryByRole("heading", { name: "Logs" })).toBeNull();

    const gear = screen.getByRole("button", { name: "Settings" });
    gear.focus();
    fireEvent.click(gear);
    const drawer = screen.getByRole("dialog", { name: "Settings" });
    await waitFor(() => expect(drawer).toContainElement(document.activeElement as HTMLElement));
    expect(document.querySelector(".work")).toHaveAttribute("inert");   // the page behind can't be reached
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(gear).toHaveFocus());
    expect(document.querySelector(".work")).not.toHaveAttribute("inert");
  });
});
