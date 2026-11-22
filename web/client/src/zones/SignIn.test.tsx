import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { leave, leaving } from "../lib/visits";
import { SignIn } from "./SignIn";

// Clerk, as this page meets it: who it says is signed in on this browser, and a form in its place
const clerk = vi.hoisted(() => ({
  auth: { isLoaded: true, isSignedIn: false, sessionId: null as string | null,
    getToken: async (): Promise<string | null> => "clerk-token", signOut: vi.fn(async () => {}) },
}));
vi.mock("@clerk/clerk-react", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => children,
  ClerkLoading: () => null, ClerkFailed: () => null, SignIn: () => "Clerk's form",
  useAuth: () => clerk.auth,
}));

function serve(registration: boolean, signIn: { status: number; body?: unknown }, clerkKey: string | null = null) {
  const calls: { url: string; body: unknown }[] = [];
  const kept = new Map<string, string>();   // this browser's storage, fresh for each test
  vi.stubGlobal("localStorage", { getItem: (k: string) => kept.get(k) ?? null, setItem: (k: string, v: string) => kept.set(k, v),
    removeItem: (k: string) => kept.delete(k) });
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (url === "/api/auth") {
      return new Response(JSON.stringify({ app_name: "HarmonicFitness", registration, version: "0.20.0 (75da105)", clerk: clerkKey }), { status: 200 });
    }
    return new Response(signIn.body ? JSON.stringify(signIn.body) : null, { status: signIn.status });
  }));
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe("the sign-in page", () => {
  it("signs in, and shows the server's refusal", async () => {
    const calls = serve(false, { status: 400, body: { detail: "Wrong username or password." } });
    const done = vi.fn();
    render(<SignIn onSignedIn={done} />);
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    fireEvent.change(await screen.findByLabelText("Username"), { target: { value: "ana" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "not right" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong username or password.");
    expect(calls[calls.length - 1]).toEqual({ url: "/api/sign-in", body: { username: "ana", password: "not right" } });
    expect(done).not.toHaveBeenCalled();
  });

  it("checks a new password and username before sending, and says the server's refusal under the username", async () => {
    const calls = serve(true, { status: 409, body: { detail: "That username is taken.", field: "username" } });
    render(<SignIn onSignedIn={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: "Make an account" }));
    const name = screen.getByLabelText("Username");
    fireEvent.change(name, { target: { value: "ana" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "Make my account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("at least 8 characters");
    expect(calls.map((c) => c.url)).toEqual(["/api/auth"]);

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

describe("the sign-in page, where sign-in goes through Clerk", () => {
  const signedIn = () => {
    clerk.auth.signOut.mockClear();
    Object.assign(clerk.auth, { isLoaded: true, isSignedIn: true, sessionId: "sess_1" });
  };
  afterEach(() => Object.assign(clerk.auth, { isSignedIn: false, sessionId: null }));

  it("shows Clerk's form to someone signed out, and asks the server for no session", async () => {
    const calls = serve(true, { status: 204 }, "pk_test_x");
    render(<SignIn onSignedIn={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Clerk's form")).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).toBeNull();
    expect(calls.map((c) => c.url)).toEqual(["/api/auth"]);
  });

  it("trades whoever Clerk signed in for a session here, once", async () => {
    signedIn();
    const calls = serve(true, { status: 204 }, "pk_test_x");
    const done = vi.fn();
    const { rerender } = render(<SignIn onSignedIn={done} />);
    await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
    rerender(<SignIn onSignedIn={done} />);
    expect(calls.filter((c) => c.url === "/api/session")).toEqual([{ url: "/api/session", body: { token: "clerk-token" } }]);
    expect(clerk.auth.signOut).not.toHaveBeenCalled();
  });

  it("says the server's refusal, and offers another account, which signs out of Clerk", async () => {
    signedIn();
    serve(false, { status: 403, body: { detail: "This site isn't taking new accounts." } }, "pk_test_x");
    const done = vi.fn();
    render(<SignIn onSignedIn={done} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("This site isn't taking new accounts.");
    expect(done).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Use another account" }));
    expect(clerk.auth.signOut).toHaveBeenCalledTimes(1);
  });

  it("signs someone who just signed out here out of Clerk too, never back in", async () => {
    signedIn();
    const calls = serve(true, { status: 204 }, "pk_test_x");
    const done = vi.fn();
    leave();
    render(<SignIn onSignedIn={done} />);
    await waitFor(() => expect(clerk.auth.signOut).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(leaving()).toBe(false));
    expect(calls.some((c) => c.url === "/api/session")).toBe(false);
    expect(done).not.toHaveBeenCalled();
  });
});
