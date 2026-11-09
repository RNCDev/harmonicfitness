import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { SignIn } from "./SignIn";

function serve(registration: boolean, signIn: { status: number; body?: unknown }) {
  const calls: { url: string; body: unknown }[] = [];
  const kept = new Map<string, string>();   // this browser's storage, fresh for each test
  vi.stubGlobal("localStorage", { getItem: (k: string) => kept.get(k) ?? null, setItem: (k: string, v: string) => kept.set(k, v) });
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth") {
      return new Response(JSON.stringify({ app_name: "HarmonicFitness", registration, version: "0.20.0 (75da105)" }), { status: 200 });
    }
    return new Response(signIn.body ? JSON.stringify(signIn.body) : null, { status: signIn.status });
  }));
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe("the sign-in page", () => {
  it("shows the deployed version", async () => {
    serve(false, { status: 204 });
    render(<SignIn onSignedIn={() => {}} />);
    expect(await screen.findByText("0.20.0 (75da105)")).toBeInTheDocument();
    expect(screen.getByText("Workouts for your earbuds, written and voiced fresh each time you ask")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Workouts other people asked for" })).toBeInTheDocument();   // the demos
    expect(screen.getByRole("heading", { name: "Full workouts, free" })).toBeInTheDocument();   // the free workouts
    expect(screen.queryByLabelText("Username")).toBeNull();   // the form waits behind Sign in
  });

  it("opens on the form for someone who has signed in here before, and goes back to the front", async () => {
    serve(false, { status: 204 });
    const done = vi.fn();
    const { unmount } = render(<SignIn onSignedIn={done} />);
    fireEvent.click(await screen.findByRole("button", { name: "Sign in" }));
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "ana" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "long enough" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(done).toHaveBeenCalled());
    unmount();
    render(<SignIn onSignedIn={() => {}} />);
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hear a demo, or play a free workout" }));
    expect(screen.getByRole("region", { name: "Workouts other people asked for" })).toBeInTheDocument();
  });

  it("offers an account only when registration is open", async () => {
    serve(false, { status: 204 });
    const { unmount } = render(<SignIn onSignedIn={() => {}} />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "Make an account" })).toBeNull();
    unmount();
    serve(true, { status: 204 });
    render(<SignIn onSignedIn={() => {}} />);
    expect(await screen.findByRole("button", { name: "Make an account" })).toBeInTheDocument();
  });

  it("signs in, and shows the server's refusal", async () => {
    const calls = serve(false, { status: 400, body: { detail: "Wrong username or password." } });
    const done = vi.fn();
    render(<SignIn onSignedIn={done} />);
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "ana" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "not right" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong username or password.");
    expect(calls[calls.length - 1]).toEqual({ url: "/api/sign-in", body: { username: "ana", password: "not right" } });
    expect(done).not.toHaveBeenCalled();
  });

  it("checks a new password's length before sending", async () => {
    const calls = serve(true, { status: 201 });
    render(<SignIn onSignedIn={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: "Make an account" }));
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "ana" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "Make my account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("at least 8 characters");
    expect(calls.map((c) => c.url)).toEqual(["/api/auth"]);
  });

  it("says a username's problem under the username box: its rule before sending, the server's refusal after", async () => {
    const calls = serve(true, { status: 409, body: { detail: "That username is taken.", field: "username" } });
    render(<SignIn onSignedIn={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: "Make an account" }));
    const name = screen.getByLabelText("Username");
    fireEvent.change(name, { target: { value: "a!" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "long enough" } });
    fireEvent.click(screen.getByRole("button", { name: "Make my account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("3 to 32 letters");
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(calls.map((c) => c.url)).toEqual(["/api/auth"]);   // nothing sent

    fireEvent.change(name, { target: { value: "ana" } });
    fireEvent.click(screen.getByRole("button", { name: "Make my account" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("That username is taken."));
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(name.getAttribute("aria-describedby")).toContain("signin-username-err");
  });

  it("takes register's empty 201 as signed in", async () => {
    const calls = serve(true, { status: 201 });
    const done = vi.fn();
    render(<SignIn onSignedIn={done} />);
    fireEvent.click(await screen.findByRole("button", { name: "Make an account" }));
    fireEvent.change(screen.getByLabelText("Username"), { target: { value: "ana" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "long enough" } });
    fireEvent.click(screen.getByRole("button", { name: "Make my account" }));
    await waitFor(() => expect(done).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).toBeNull();
    expect(calls[calls.length - 1].url).toBe("/api/register");
  });
});
