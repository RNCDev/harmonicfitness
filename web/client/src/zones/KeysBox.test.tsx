import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { balanceText, KeysBox } from "./KeysBox";
import { api, ApiError, checkBalances, NotSignedIn, type KeyState } from "../api";

vi.mock("../api", async (orig) => {
  const real = await orig<typeof import("../api")>();
  return { ...real, checkBalances: vi.fn(),
    api: { keys: vi.fn(), setKey: vi.fn(), deleteKey: vi.fn(), setWriter: vi.fn() } };
});

const FISH: KeyState = { service: "fish", name: "Fish Audio", key_page: "https://fish.example/keys",
  set: true, updated_at: "2026-10-20T12:00:00Z", kind: "voice" };
const ELEVEN: KeyState = { service: "elevenlabs", name: "ElevenLabs", key_page: "https://el.example/keys",
  set: false, updated_at: null, kind: "voice" };
const CLAUDE: KeyState = { service: "anthropic", name: "Claude", key_page: "https://c.example/keys",
  set: false, updated_at: null, kind: "model" };
const m = api as unknown as { keys: ReturnType<typeof vi.fn>; setKey: ReturnType<typeof vi.fn>;
  deleteKey: ReturnType<typeof vi.fn>; setWriter: ReturnType<typeof vi.fn> };

beforeEach(() => {
  vi.clearAllMocks();
  m.keys.mockResolvedValue([FISH, ELEVEN]);
  m.setKey.mockResolvedValue(undefined);
  m.deleteKey.mockResolvedValue(undefined);
  m.setWriter.mockResolvedValue(undefined);
  check.mockResolvedValue(null);
});
const check = checkBalances as unknown as ReturnType<typeof vi.fn>;

describe("the Keys box", () => {
  it("groups the keys as required and optional", async () => {
    m.keys.mockResolvedValue([CLAUDE, FISH, ELEVEN]);
    render(<KeysBox onSignedOut={() => {}} />);
    expect(await screen.findByRole("heading", { name: "Keys" })).toBeInTheDocument();
    const required = screen.getByRole("region", { name: "Who writes your workouts" });
    const optional = screen.getByRole("region", { name: "More voices (optional)" });
    expect(required).toHaveTextContent("Claude");
    expect(required).toHaveTextContent("This key writes every workout.");
    expect(required).not.toHaveTextContent("Fish Audio");
    expect(optional).toHaveTextContent("Fish Audio");
    expect(optional).toHaveTextContent("ElevenLabs");
    expect(screen.getByText("Keys are stored encrypted and never shown again. Each one goes only to its own service, and only when it's used.")).toBeInTheDocument();
  });

  it("shows Gemini, listed as model and voice, as one row, set once", async () => {
    const model: KeyState = { service: "gemini", name: "Gemini", key_page: "https://g.example/keys",
      set: false, updated_at: null, kind: "model" };
    const voice: KeyState = { ...model, kind: "voice" };
    const seen = vi.fn();
    m.keys.mockResolvedValue([model, voice, FISH]);
    render(<KeysBox onSignedOut={() => {}} onKeys={seen} />);
    expect(await screen.findAllByRole("button", { name: "Add Gemini key" })).toHaveLength(1);
    const required = screen.getByRole("region", { name: "Who writes your workouts" });
    expect(required).toHaveTextContent("The same key also voices a coach.");
    expect(screen.getByRole("region", { name: "More voices (optional)" })).not.toHaveTextContent("Gemini");
    fireEvent.click(screen.getByRole("button", { name: "Add Gemini key" }));
    fireEvent.change(screen.getByLabelText("Gemini key"), { target: { value: "AIza-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Replace Gemini key" })).toBeInTheDocument());
    expect(m.setKey).toHaveBeenCalledTimes(1);
    expect(m.setKey).toHaveBeenCalledWith("gemini", "AIza-secret");
    expect(screen.getAllByText(/^Set\b/)).toHaveLength(2);   // Gemini once, Fish Audio
    const last = seen.mock.calls[seen.mock.calls.length - 1][0] as KeyState[];
    expect(last.filter((k) => k.service === "gemini").every((k) => k.set)).toBe(true);
  });

  it("the listener picks who writes, and a pick with no key opens its key", async () => {
    const claude = { ...CLAUDE, set: true, writer: true };
    const gpt: KeyState = { service: "openai", name: "ChatGPT", key_page: "https://o.example", set: false, updated_at: null, kind: "model", writer: false };
    m.keys.mockResolvedValue([claude, gpt, FISH]);
    render(<KeysBox onSignedOut={() => {}} />);
    const group = await screen.findByRole("radiogroup", { name: "Who writes your workouts" });
    expect(screen.getByRole("radio", { name: "Claude" })).toBeChecked();
    expect(group.closest("section")).toHaveTextContent("Pick one, and add its key.");
    fireEvent.click(screen.getByRole("radio", { name: "ChatGPT" }));
    await waitFor(() => expect(screen.getByRole("radio", { name: "ChatGPT" })).toBeChecked());
    expect(m.setWriter).toHaveBeenCalledWith("openai");
    expect(await screen.findByLabelText("ChatGPT key")).toHaveFocus();
  });

  it("the welcome's pick chooses the writer and opens its key", async () => {
    const gpt: KeyState = { service: "openai", name: "ChatGPT", key_page: "https://o.example", set: false, updated_at: null, kind: "model" };
    m.keys.mockResolvedValue([CLAUDE, gpt, FISH]);
    render(<KeysBox onSignedOut={() => {}} openRow={{ service: "openai", n: 1, choose: true }} />);
    expect(await screen.findByLabelText("ChatGPT key")).toBeInTheDocument();
    expect(m.setWriter).toHaveBeenCalledWith("openai");
    expect(screen.getByRole("radio", { name: "ChatGPT" })).toBeChecked();
  });

  it("opens a row for its key when asked", async () => {
    const { rerender } = render(<KeysBox onSignedOut={() => {}} openRow={null} />);
    await screen.findByRole("button", { name: "Add ElevenLabs key" });
    rerender(<KeysBox onSignedOut={() => {}} openRow={{ service: "elevenlabs", n: 1 }} />);
    expect(await screen.findByLabelText("ElevenLabs key")).toHaveFocus();
  });

  it("shows every service, set or not", async () => {
    render(<KeysBox onSignedOut={() => {}} />);
    expect(await screen.findByText(/^Set\b/)).toBeInTheDocument();
    expect(screen.getAllByText(/^Set\b/)).toHaveLength(1);
    expect(screen.getAllByText("Not set")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Replace Fish Audio key" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add ElevenLabs key" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Remove/ })).toHaveLength(1);
  });

  it("saves a key and never shows it", async () => {
    const { container } = render(<KeysBox onSignedOut={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: "Add ElevenLabs key" }));
    const input = screen.getByLabelText("ElevenLabs key");
    expect(input).toHaveFocus();
    expect(input).toHaveValue("");
    expect(input).toHaveAttribute("data-1p-ignore");
    fireEvent.change(input, { target: { value: "secret-value-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(m.setKey).toHaveBeenCalledWith("elevenlabs", "secret-value-1");
    await waitFor(() => expect(screen.queryByLabelText("ElevenLabs key")).not.toBeInTheDocument());
    expect(container.textContent).not.toContain("secret-value-1");
    for (const el of container.querySelectorAll("input")) expect((el as HTMLInputElement).value).not.toContain("secret-value-1");
    expect(screen.getAllByText(/^Set\b/)).toHaveLength(2);
  });

  it("shows the server's refusal", async () => {
    m.setKey.mockRejectedValue(new ApiError(400, "That doesn't look like a Fish Audio key: bad."));
    render(<KeysBox onSignedOut={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: "Replace Fish Audio key" }));
    fireEvent.change(screen.getByLabelText("Fish Audio key"), { target: { value: "a b" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That doesn't look like a Fish Audio key: bad.");
    expect(screen.getByLabelText("Fish Audio key")).toBeInTheDocument();
  });

  it("removes after asking", async () => {
    render(<KeysBox onSignedOut={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: "Remove Fish Audio key" }));
    expect(screen.getByText("Remove your Fish Audio key?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep" }));
    expect(m.deleteKey).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Remove Fish Audio key" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(m.deleteKey).toHaveBeenCalledWith("fish");
    await waitFor(() => expect(screen.getAllByText("Not set")).toHaveLength(2));
  });

  it("signs out on NotSignedIn and links to the key page safely", async () => {
    const out = vi.fn();
    m.setKey.mockRejectedValue(new NotSignedIn("x"));
    render(<KeysBox onSignedOut={out} />);
    fireEvent.click(await screen.findByRole("button", { name: "Add ElevenLabs key" }));
    const link = screen.getByRole("link", { name: "Get a key" });
    expect(link).toHaveAttribute("href", "https://el.example/keys");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("target", "_blank");
    fireEvent.change(screen.getByLabelText("ElevenLabs key"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(out).toHaveBeenCalled());
  });
});

describe("balances", () => {
  const fish: KeyState = { ...FISH, billing_page: "https://fish.example/billing", reports: true };
  const eleven: KeyState = { ...ELEVEN, set: true, updated_at: "2026-10-20T12:00:00Z",
    billing_page: "https://el.example/billing", reports: true };
  const inworld: KeyState = { service: "inworld", name: "Inworld", key_page: "https://i.example/keys", set: true,
    updated_at: "2026-10-20T12:00:00Z", kind: "voice", billing_page: "https://i.example/billing", reports: false };
  const unset: KeyState = { ...inworld, service: "gemini", name: "Gemini", set: false, updated_at: null };

  it("shows what's left where the service says, and a billing link where it can't", async () => {
    m.keys.mockResolvedValue([fish, eleven, inworld, unset]);
    check.mockResolvedValue({ fish: { ok: true, usd: 12.50 }, elevenlabs: { ok: true, used: 2120, limit: 30000 } });
    render(<KeysBox onSignedOut={() => {}} />);
    const left = await screen.findByRole("link", { name: "$12.50 left" });
    expect(left).toHaveAttribute("href", "https://fish.example/billing");
    expect(left).toHaveAttribute("target", "_blank");
    expect(screen.getByRole("link", { name: "27,880 credits left" })).toHaveAttribute("href", "https://el.example/billing");
    expect(screen.getByRole("link", { name: "Inworld billing" })).toHaveAttribute("href", "https://i.example/billing");
    expect(screen.queryByRole("link", { name: "Gemini billing" })).toBeNull();   // no key, nothing to see
    expect(check).toHaveBeenCalledTimes(1);
  });

  it("says it's checking, then falls back to the link when a service refused or the check failed", async () => {
    m.keys.mockResolvedValue([fish, eleven]);
    let done: (v: unknown) => void = () => {};
    check.mockReturnValue(new Promise((r) => { done = r; }));
    render(<KeysBox onSignedOut={() => {}} />);
    expect(await screen.findAllByText("Checking balance…")).toHaveLength(2);
    done({ fish: { ok: false, kind: "auth" } });
    expect(await screen.findByRole("link", { name: "Fish Audio billing" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ElevenLabs billing" })).toBeInTheDocument();
  });

  it("never asks when no key that can say is set", async () => {
    m.keys.mockResolvedValue([inworld, { ...fish, set: false, updated_at: null }]);
    render(<KeysBox onSignedOut={() => {}} />);
    expect(await screen.findByRole("link", { name: "Inworld billing" })).toBeInTheDocument();
    expect(check).not.toHaveBeenCalled();
  });

  it("words a balance", () => {
    expect(balanceText({ ok: true, usd: 1234.5 })?.text).toBe("$1,234.50 left");
    expect(balanceText({ ok: true, used: 40, limit: 10 })?.text).toBe("0 credits left");
    expect(balanceText({ ok: true, used: 1, limit: 10, resets: 1793000000 })?.title).toMatch(/1 of 10 credits used this period, resets /);
    expect(balanceText({ ok: false })).toBeNull();
    expect(balanceText({ ok: true })).toBeNull();
  });
});
