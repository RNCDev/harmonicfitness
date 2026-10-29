import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { KeysBox } from "./KeysBox";
import { api, ApiError, NotSignedIn, type KeyState } from "../api";

vi.mock("../api", async (orig) => {
  const real = await orig<typeof import("../api")>();
  return { ...real, api: { keys: vi.fn(), setKey: vi.fn(), deleteKey: vi.fn() } };
});

const FISH: KeyState = { service: "fish", name: "Fish Audio", key_page: "https://fish.example/keys",
  set: true, updated_at: "2026-10-20T12:00:00Z", kind: "voice" };
const ELEVEN: KeyState = { service: "elevenlabs", name: "ElevenLabs", key_page: "https://el.example/keys",
  set: false, updated_at: null, kind: "voice" };
const CLAUDE: KeyState = { service: "anthropic", name: "Claude", key_page: "https://c.example/keys",
  set: false, updated_at: null, kind: "model" };
const m = api as unknown as { keys: ReturnType<typeof vi.fn>; setKey: ReturnType<typeof vi.fn>;
  deleteKey: ReturnType<typeof vi.fn> };

beforeEach(() => {
  vi.clearAllMocks();
  m.keys.mockResolvedValue([FISH, ELEVEN]);
  m.setKey.mockResolvedValue(undefined);
  m.deleteKey.mockResolvedValue(undefined);
});

describe("the Keys box", () => {
  it("groups the keys as required and optional", async () => {
    m.keys.mockResolvedValue([CLAUDE, FISH, ELEVEN]);
    render(<KeysBox onSignedOut={() => {}} />);
    expect(await screen.findByRole("heading", { name: "Keys" })).toBeInTheDocument();
    const required = screen.getByRole("region", { name: "Required" });
    const optional = screen.getByRole("region", { name: "Optional: more voices" });
    expect(required).toHaveTextContent("Claude");
    expect(required).toHaveTextContent("Writes your workouts.");
    expect(required).not.toHaveTextContent("Fish Audio");
    expect(optional).toHaveTextContent("Fish Audio");
    expect(optional).toHaveTextContent("ElevenLabs");
    expect(screen.getByText("Stored encrypted, never shown again. Each key goes only to its own service, when you use it.")).toBeInTheDocument();
  });

  it("shows Gemini, listed as model and voice, as one row, set once", async () => {
    const model: KeyState = { service: "gemini", name: "Gemini", key_page: "https://g.example/keys",
      set: false, updated_at: null, kind: "model" };
    const voice: KeyState = { ...model, kind: "voice" };
    const seen = vi.fn();
    m.keys.mockResolvedValue([model, voice, FISH]);
    render(<KeysBox onSignedOut={() => {}} onKeys={seen} />);
    expect(await screen.findAllByRole("button", { name: "Add Gemini key" })).toHaveLength(1);
    const required = screen.getByRole("region", { name: "Required" });
    expect(required).toHaveTextContent("Writes your workouts, and can voice your coach.");
    expect(screen.getByRole("region", { name: "Optional: more voices" })).not.toHaveTextContent("Gemini");
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
