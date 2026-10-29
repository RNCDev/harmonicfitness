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
    const put = vi.fn();
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (url === "/api/me") return json({ app_name: "HarmonicFitness", username: "ana", has_password: true, version: "" });
      if (url === "/api/keys") return json([{ ...gemini, kind: "model" }, { ...gemini, kind: "voice" }]);
      if (url === "/api/keys/gemini" && init?.method === "PUT") { put(); return Promise.resolve(new Response(null, { status: 204 })); }
      if (url === "/api/conversations/latest") return Promise.resolve(new Response(null, { status: 204 }));
      return Promise.resolve(new Response(null, { status: 404 }));
    }));
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Add your key" }));
    const box = await screen.findByLabelText("Gemini key");
    await waitFor(() => expect(box).toHaveFocus());
    expect(screen.getByRole("textbox", { name: "Message" })).toBeDisabled();
    fireEvent.change(box, { target: { value: "AIza-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("region", { name: "Start a workout" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New chat" })).toBeNull();   // nothing to clear yet
    expect(put).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Welcome to HarmonicFitness")).toBeNull();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeEnabled();
  });
});
