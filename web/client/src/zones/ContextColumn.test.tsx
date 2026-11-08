import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { api, ApiError, type LevelState } from "../lib/api";
import { ContextColumn } from "./ContextColumn";

vi.mock("./KeysBox", () => ({ KeysBox: () => null }));

describe("Settings", () => {
  it("holds keys, not coaches (they have their own page)", () => {
    render(<ContextColumn username="sam" open onClose={vi.fn()} onSignOut={vi.fn()} />);
    expect(screen.queryByRole("heading", { name: "Coaches" })).toBeNull();
  });

  it("credits the backgrounds to Book of Shapes", () => {
    render(<ContextColumn username="sam" open onClose={vi.fn()} onSignOut={vi.fn()} onSky={vi.fn()} />);
    const link = screen.getByRole("link", { name: "Book of Shapes" });
    expect(link).toHaveAttribute("href", "https://bookofshapes.com");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link.closest("p")).toHaveTextContent("Nikolaj Sokolowski");
    expect(screen.queryByRole("button", { name: /Arcs/ })).toBeNull();   // retired: its licence asks it not be published
    expect(screen.getByRole("button", { name: /Bloom/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Lissajous/ })).toBeNull();   // replaced in 0.50.3
    expect(screen.queryByRole("button", { name: /Hex Strands/ })).toBeNull();   // replaced by Woven Grid in 0.50.4
    expect(screen.getByRole("button", { name: /Woven Grid/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Node Garden/ })).toBeInTheDocument();
  });
});

describe("the version", () => {
  it("shows at the foot of Settings", () => {
    render(<ContextColumn username="sam" version="0.42.3 (abc1234)" open onClose={vi.fn()}
      onSignOut={vi.fn()} />);
    expect(screen.getByText("Version 0.42.3 (abc1234)")).toBeInTheDocument();
  });
});

const LEVELS: LevelState = {
  level: "novice", set: false, choices: [
    { level: "novice", said: "I'm new to this, or it's been a long while." },
    { level: "experienced", said: "I've trained before and know the basic moves, but I'm no expert." },
    { level: "advanced", said: "I know my way around and want to be pushed." },
  ],
};

describe("your level", () => {
  afterEach(() => vi.restoreAllMocks());
  const open = () => render(<ContextColumn username="sam" open onClose={vi.fn()} onSignOut={vi.fn()} />);

  it("offers the three sentences, novice until one is chosen", async () => {
    vi.spyOn(api, "level").mockResolvedValue(LEVELS);
    open();
    const novice = await screen.findByRole("radio", { name: /I'm new to this/ });
    expect(novice).toHaveAttribute("aria-checked", "true");
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByText(/Not chosen yet/)).toBeInTheDocument();
  });

  it("saves the one picked", async () => {
    vi.spyOn(api, "level").mockResolvedValue({ ...LEVELS, level: "experienced", set: true });
    const save = vi.spyOn(api, "setLevel").mockResolvedValue(undefined);
    open();
    fireEvent.click(await screen.findByRole("radio", { name: /I know my way around/ }));
    expect(save).toHaveBeenCalledWith("advanced");
    expect(screen.getByRole("radio", { name: /I know my way around/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.queryByText(/Not chosen yet/)).toBeNull();
  });

  it("puts the old one back when the save is refused", async () => {
    vi.spyOn(api, "level").mockResolvedValue({ ...LEVELS, level: "experienced", set: true });
    vi.spyOn(api, "setLevel").mockRejectedValue(new ApiError(409, "Your files changed at the same moment. Try again."));
    open();
    fireEvent.click(await screen.findByRole("radio", { name: /I know my way around/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Try again"));
    expect(screen.getByRole("radio", { name: /I've trained before/ })).toHaveAttribute("aria-checked", "true");
  });
});

describe("an empty answer", () => {
  afterEach(() => vi.restoreAllMocks());
  it("leaves the level loading, never breaks the drawer", async () => {
    vi.spyOn(api, "level").mockResolvedValue(undefined as unknown as LevelState);
    render(<ContextColumn username="sam" open onClose={vi.fn()} onSignOut={vi.fn()} />);
    expect(await screen.findByText("Loading your level…")).toBeInTheDocument();
    expect(screen.getByText("Signed in as")).toBeInTheDocument();
  });
});
