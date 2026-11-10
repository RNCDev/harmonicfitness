import { beforeEach, describe, expect, it, vi } from "vitest";
import { KeyAskContext } from "../../lib/keyAsk";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { KeysBox } from "./KeysBox";
import { balanceText } from "../../lib/keys";
import { api, ApiError, checkBalances, NotSignedIn, type KeyState } from "../../lib/api";

vi.mock("../../lib/api", async (orig) => {
  const real = await orig<typeof import("../../lib/api")>();
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
    render(<KeysBox />);
    expect(await screen.findByRole("heading", { name: "Keys" })).toBeInTheDocument();
    const required = screen.getByRole("region", { name: "Who writes your workouts" });
    const optional = screen.getByRole("region", { name: "More voices (optional)" });
    expect(required).toHaveTextContent("Claude");
    expect(required).toHaveTextContent("This key writes every workout.");
    expect(required).not.toHaveTextContent("Fish Audio");
    expect(optional).toHaveTextContent("Fish Audio");
    expect(optional).toHaveTextContent("ElevenLabs");
    expect(screen.getByText("Keys are encrypted, never shown again, and sent only to their own service.")).toBeInTheDocument();
  });

  it("hides the voice keys behind a link when the writer's key voices too", async () => {
    const model: KeyState = { service: "openrouter", name: "OpenRouter", key_page: "https://or.example/keys",
      set: true, updated_at: "2026-10-31T12:00:00Z", kind: "model", writer: true };
    m.keys.mockResolvedValue([model, { ...model, kind: "voice" }, { ...FISH, set: false }, ELEVEN]);
    render(<KeysBox />);
    expect(await screen.findByText(/Your OpenRouter key voices your coaches too/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add Fish Audio key" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Add another voice (optional)" }));
    expect(screen.getByRole("button", { name: "Add Fish Audio key" })).toBeInTheDocument();
  });

  it("keeps the voice keys showing once one is set", async () => {
    const model: KeyState = { service: "openrouter", name: "OpenRouter", key_page: "https://or.example/keys",
      set: true, updated_at: null, kind: "model", writer: true };
    m.keys.mockResolvedValue([model, { ...model, kind: "voice" }, FISH, ELEVEN]);
    render(<KeysBox />);
    expect(await screen.findByRole("region", { name: "More voices (optional)" })).toHaveTextContent("ElevenLabs");
    expect(screen.queryByRole("button", { name: "Add another voice (optional)" })).toBeNull();
  });

  it("shows Gemini, listed as model and voice, as one row, set once", async () => {
    const model: KeyState = { service: "gemini", name: "Gemini", key_page: "https://g.example/keys",
      set: false, updated_at: null, kind: "model" };
    const voice: KeyState = { ...model, kind: "voice" };
    const seen = vi.fn();
    m.keys.mockResolvedValue([model, voice, FISH]);
    render(<KeysBox onKeys={seen} />);
    expect(await screen.findAllByRole("button", { name: "Add Gemini key" })).toHaveLength(1);
    const required = screen.getByRole("region", { name: "Who writes your workouts" });
    expect(required).toHaveTextContent("+ voices");
    expect(screen.getByRole("region", { name: "More voices (optional)" })).not.toHaveTextContent("Gemini");
    fireEvent.click(screen.getByRole("button", { name: "Add Gemini key" }));
    fireEvent.change(screen.getByLabelText("Gemini key"), { target: { value: "AIza-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Replace Gemini key" })).toBeInTheDocument());
    expect(m.setKey).toHaveBeenCalledTimes(1);
    expect(m.setKey).toHaveBeenCalledWith("gemini", "AIza-secret");
    expect(screen.getAllByTitle(/^Key added/)).toHaveLength(2);   // Gemini once, Fish Audio
    const last = seen.mock.calls[seen.mock.calls.length - 1][0] as KeyState[];
    expect(last.filter((k) => k.service === "gemini").every((k) => k.set)).toBe(true);
  });

  it("lists OpenRouter and Gemini first, as they also voice coaches", async () => {
    const or: KeyState = { service: "openrouter", name: "OpenRouter", key_page: "https://or.example", set: false, updated_at: null, kind: "model" };
    const gem: KeyState = { service: "gemini", name: "Gemini", key_page: "https://g.example", set: false, updated_at: null, kind: "model" };
    const gpt: KeyState = { service: "openai", name: "ChatGPT", key_page: "https://o.example", set: false, updated_at: null, kind: "model" };
    m.keys.mockResolvedValue([CLAUDE, gpt, gem, { ...gem, kind: "voice" }, or, { ...or, kind: "voice" }, FISH]);
    render(<KeysBox />);
    await screen.findByRole("region", { name: "Who writes your workouts" });
    expect(screen.getAllByRole("button", { name: /^Use .* to write your workouts$/ }).map((b) => b.getAttribute("aria-label")))
      .toEqual(["OpenRouter", "Gemini", "Claude", "ChatGPT"].map((n) => `Use ${n} to write your workouts`));
    expect(screen.getAllByText("+ voices")).toHaveLength(2);
  });

  it("the listener picks who writes, and a pick with no key opens its key", async () => {
    const claude = { ...CLAUDE, set: true, writer: true };
    const gpt: KeyState = { service: "openai", name: "ChatGPT", key_page: "https://o.example", set: false, updated_at: null, kind: "model", writer: false };
    m.keys.mockResolvedValue([claude, gpt, FISH]);
    render(<KeysBox />);
    const group = await screen.findByRole("region", { name: "Who writes your workouts" });
    expect(screen.getByText("In use").closest(".keys-row")).toHaveTextContent("Claude");
    expect(screen.queryByRole("button", { name: "Use Claude to write your workouts" })).toBeNull();
    expect(group).toHaveTextContent("Pick one");
    fireEvent.click(screen.getByRole("button", { name: "Use ChatGPT to write your workouts" }));
    await waitFor(() => expect(screen.getByText("In use").closest(".keys-row")).toHaveTextContent("ChatGPT"));
    expect(m.setWriter).toHaveBeenCalledWith("openai");
    expect(await screen.findByLabelText("ChatGPT key")).toHaveFocus();
  });

  it("the welcome's pick chooses the writer and opens its key", async () => {
    const gpt: KeyState = { service: "openai", name: "ChatGPT", key_page: "https://o.example", set: false, updated_at: null, kind: "model" };
    m.keys.mockResolvedValue([CLAUDE, gpt, FISH]);
    render(<KeyAskContext.Provider value={{ service: "openai", n: 1, choose: true }}><KeysBox /></KeyAskContext.Provider>);
    expect(await screen.findByLabelText("ChatGPT key")).toBeInTheDocument();
    expect(m.setWriter).toHaveBeenCalledWith("openai");
    expect(screen.getByText("In use").closest(".keys-row")).toHaveTextContent("ChatGPT");
  });

  it("closes an open key box on a click outside its row, but not inside it", async () => {
    m.keys.mockResolvedValue([CLAUDE, ELEVEN]);
    render(<KeysBox />);
    fireEvent.click(await screen.findByRole("button", { name: "Add ElevenLabs key" }));
    const box = await screen.findByLabelText("ElevenLabs key");
    fireEvent.pointerDown(box);
    expect(screen.getByLabelText("ElevenLabs key")).toBeInTheDocument();
    fireEvent.pointerDown(document.body);
    await waitFor(() => expect(screen.queryByLabelText("ElevenLabs key")).toBeNull());
  });

  it("opens a row for its key when asked, and again when asked again", async () => {
    const ask = (n: number) => <KeyAskContext.Provider value={{ service: "elevenlabs", n }}><KeysBox /></KeyAskContext.Provider>;
    const { rerender } = render(<KeyAskContext.Provider value={null}><KeysBox /></KeyAskContext.Provider>);
    await screen.findByRole("button", { name: "Add ElevenLabs key" });
    rerender(ask(1));
    expect(await screen.findByLabelText("ElevenLabs key")).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByLabelText("ElevenLabs key")).toBeNull();
    rerender(ask(1));   // the same ask, drawn again: the row stays closed
    expect(screen.queryByLabelText("ElevenLabs key")).toBeNull();
    rerender(ask(2));   // the same row, asked for again
    expect(await screen.findByLabelText("ElevenLabs key")).toHaveFocus();
  });

  it("shows every service, set or not", async () => {
    render(<KeysBox />);
    expect(await screen.findByTitle(/^Key added/)).toBeInTheDocument();
    expect(screen.getAllByTitle(/^Key added/)).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: /^Add / })).toHaveLength(1);   // an unset key just offers Add
    expect(screen.getByRole("button", { name: "Replace Fish Audio key" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add ElevenLabs key" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Remove/ })).toHaveLength(1);
  });

  it("saves a key and never shows it", async () => {
    const { container } = render(<KeysBox />);
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
    expect(screen.getAllByTitle(/^Key added/)).toHaveLength(2);
  });

  it("shows the server's refusal", async () => {
    m.setKey.mockRejectedValue(new ApiError(400, "That doesn't look like a Fish Audio key: bad."));
    render(<KeysBox />);
    fireEvent.click(await screen.findByRole("button", { name: "Replace Fish Audio key" }));
    fireEvent.change(screen.getByLabelText("Fish Audio key"), { target: { value: "a b" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That doesn't look like a Fish Audio key: bad.");
    expect(screen.getByLabelText("Fish Audio key")).toBeInTheDocument();
  });

  it("removes after asking", async () => {
    render(<KeysBox />);
    fireEvent.click(await screen.findByRole("button", { name: "Remove Fish Audio key" }));
    expect(screen.getByText("Remove your Fish Audio key?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep" }));
    expect(m.deleteKey).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Remove Fish Audio key" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(m.deleteKey).toHaveBeenCalledWith("fish");
    await waitFor(() => expect(screen.getByRole("button", { name: "Add Fish Audio key" })).toBeInTheDocument());
    expect(screen.queryByText(/^Set\b/)).toBeNull();
  });

  it("says nothing of a lost session (the app goes to sign-in), and links to the key page safely", async () => {
    m.setKey.mockRejectedValue(new NotSignedIn("x"));
    render(<KeysBox />);
    fireEvent.click(await screen.findByRole("button", { name: "Add ElevenLabs key" }));
    const link = screen.getByRole("link", { name: "Get a key" });
    expect(link).toHaveAttribute("href", "https://el.example/keys");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("target", "_blank");
    fireEvent.change(screen.getByLabelText("ElevenLabs key"), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(m.setKey).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByLabelText("ElevenLabs key")).toBeInTheDocument();   // the box stays as it was
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
    render(<KeysBox />);
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
    render(<KeysBox />);
    expect(await screen.findAllByText("Checking balance…")).toHaveLength(2);
    done({ fish: { ok: false, kind: "auth" } });
    expect(await screen.findByRole("link", { name: "Fish Audio billing" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ElevenLabs billing" })).toBeInTheDocument();
  });

  it("never asks when no key that can say is set", async () => {
    m.keys.mockResolvedValue([inworld, { ...fish, set: false, updated_at: null }]);
    render(<KeysBox />);
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
