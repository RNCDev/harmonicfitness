import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { api, ApiError, type LevelState, type MinutesState } from "../../lib/api";
import { SiteContext } from "../../lib/site";
import { Settings } from "./Settings";

describe("Settings", () => {
  it("credits the backgrounds to Book of Shapes", () => {
    render(<Settings username="sam" open onClose={vi.fn()} onSignOut={vi.fn()} onSky={vi.fn()} />);
    const link = screen.getByRole("link", { name: "Book of Shapes" });
    expect(link).toHaveAttribute("href", "https://bookofshapes.com");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link.closest("p")).toHaveTextContent("Nikolaj Sokolowski");
    expect(screen.queryByRole("button", { name: /Arcs/ })).toBeNull();   // retired: its licence asks it not be published
  });
});

describe("Settings, with minutes", () => {
  afterEach(() => vi.restoreAllMocks());

  it("opens on the minutes left and the packs, sends a pack to the checkout, and says nothing of a password where Clerk signs in", async () => {
    const state: MinutesState = {
      minutes: 20, can_buy: true, packs: [{ id: "hf_minutes_60", minutes: 60, cents: 500 }],
      history: [{ at: "2026-11-20T10:00:00Z", kind: "grant", minutes: 20, what: "A welcome" }],
    };
    // the checkout page is another site's: the answer never comes here, so the page never leaves
    const checkout = vi.spyOn(api, "checkout").mockReturnValue(new Promise(() => {}));
    render(
      <SiteContext.Provider value={{ clerk: true }}>
        <Settings username="sam" open onClose={vi.fn()} onSignOut={vi.fn()}
          minutes={{ state, error: null, reload: vi.fn(), settle: vi.fn() }} />
      </SiteContext.Provider>,
    );
    expect(screen.getByText("20").closest("p")).toHaveTextContent("20 minutes left");
    expect(screen.getByText("+20")).toBeInTheDocument();
    expect(screen.queryByLabelText(/password/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Buy for $5" }));
    expect(checkout).toHaveBeenCalledWith("hf_minutes_60");
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
  const open = () => render(<Settings username="sam" open onClose={vi.fn()} onSignOut={vi.fn()} />);

  it("offers the three sentences, novice until one is chosen, saves the one picked, and puts it back if refused", async () => {
    vi.spyOn(api, "level").mockResolvedValue(LEVELS);
    open();
    const novice = await screen.findByRole("radio", { name: /I'm new to this/ });
    expect(novice).toHaveAttribute("aria-checked", "true");
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByText(/Not chosen yet/)).toBeInTheDocument();
    cleanup();

    vi.spyOn(api, "level").mockResolvedValue({ ...LEVELS, level: "experienced", set: true });
    const save = vi.spyOn(api, "setLevel").mockResolvedValue(undefined);
    open();
    fireEvent.click(await screen.findByRole("radio", { name: /I know my way around/ }));
    expect(save).toHaveBeenCalledWith("advanced");
    expect(screen.getByRole("radio", { name: /I know my way around/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.queryByText(/Not chosen yet/)).toBeNull();
    cleanup();

    vi.spyOn(api, "level").mockResolvedValue({ ...LEVELS, level: "experienced", set: true });
    vi.spyOn(api, "setLevel").mockRejectedValue(new ApiError(409, "Your files changed at the same moment. Try again."));
    open();
    fireEvent.click(await screen.findByRole("radio", { name: /I know my way around/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Try again"));
    expect(screen.getByRole("radio", { name: /I've trained before/ })).toHaveAttribute("aria-checked", "true");
  });
});

describe("deleting the account", () => {
  afterEach(() => vi.restoreAllMocks());

  it("asks for the password in place, deletes only once it's typed, and Keep my account sends nothing", async () => {
    const del = vi.spyOn(api, "deleteAccount").mockResolvedValue(undefined);
    const onDeleted = vi.fn();
    render(<Settings username="sam" open onClose={vi.fn()} onSignOut={vi.fn()} onDeleted={onDeleted} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete my account" }));
    const box = screen.getByLabelText("Your password");
    expect(box).toHaveFocus();
    expect(screen.getByRole("button", { name: "Delete everything" })).toBeDisabled();
    fireEvent.change(box, { target: { value: "hunter22" } });
    fireEvent.submit(box.closest("form")!);
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
    expect(del).toHaveBeenCalledWith("hunter22");
    cleanup();

    del.mockClear();
    render(<Settings username="sam" open onClose={vi.fn()} onSignOut={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete my account" }));
    fireEvent.click(screen.getByRole("button", { name: "Keep my account" }));
    expect(screen.getByRole("button", { name: "Delete my account" })).toBeInTheDocument();
    expect(del).not.toHaveBeenCalled();
  });
});

describe("the podcast feed", () => {
  afterEach(() => vi.restoreAllMocks());
  const URL = "https://app.test/feed/abc.xml";
  const last = (name: string) => { const all = screen.getAllByRole("button", { name }); return all[all.length - 1]; };
  const openOn = () => {
    render(<Settings username="sam" open onClose={vi.fn()} onSignOut={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Podcast" }));
  };

  it("is off until the listener makes a link, then shows it, and asks before a new link stops the old one", async () => {
    vi.spyOn(api, "feed").mockResolvedValue({ url: null });
    const make = vi.spyOn(api, "makeFeed").mockResolvedValue({ url: URL });
    openOn();
    fireEvent.click(await screen.findByRole("button", { name: "Make my podcast link" }));
    expect(await screen.findByText(URL)).toBeInTheDocument();
    expect(make).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/anyone with the link can hear your workouts/)).toBeInTheDocument();

    make.mockClear();
    make.mockResolvedValue({ url: "https://app.test/feed/new.xml" });
    fireEvent.click(await screen.findByRole("button", { name: "Make a new link" }));
    expect(make).not.toHaveBeenCalled();
    expect(screen.getByText(/stops working, in every app/)).toBeInTheDocument();
    fireEvent.click(last("Make a new link"));
    expect(await screen.findByText("https://app.test/feed/new.xml")).toBeInTheDocument();
  });

  it("turns off, after asking", async () => {
    vi.spyOn(api, "feed").mockResolvedValue({ url: URL });
    const stop = vi.spyOn(api, "stopFeed").mockResolvedValue(undefined);
    openOn();
    fireEvent.click(await screen.findByRole("button", { name: "Turn it off" }));
    fireEvent.click(last("Turn it off"));
    expect(await screen.findByRole("button", { name: "Make my podcast link" })).toBeInTheDocument();
    expect(stop).toHaveBeenCalledTimes(1);
  });
});
