import { beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { StartCoach } from "../lib/api";
import { SiteContext } from "../lib/site";
import { CoachesPage } from "./Coaches";

const coaches: StartCoach[] = [
  { slug: "coach-reed-fish", name: "Coach Reed", first: "Reed", service: "fish", service_name: "Fish Audio", ready: true, own: false, current: false },
  { slug: "coach-nolan-gemini", name: "Coach Nolan", first: "Nolan", service: "gemini", service_name: "Gemini", ready: true, own: false, current: true },
  { slug: "coach-owen-inworld", name: "Coach Owen", first: "Owen", service: "inworld", service_name: "Inworld", ready: false, own: false, current: false },
  { slug: "coach-nora-openrouter", name: "Coach Nora", first: "Nora", service: "openrouter", service_name: "OpenRouter", ready: false, own: false,
    current: false, tone: "Direct and precise.", sample: true, usd_per_workout: 0.8, powered_by: "ElevenLabs" },
];

const page = (over: Partial<Parameters<typeof CoachesPage>[0]> = {}, hosted = false) => {
  const props = { coaches, onCoach: vi.fn(), onAddKey: vi.fn(), onClose: vi.fn(), ...over };
  render(<SiteContext.Provider value={{ hosted, clerk: hosted }}><CoachesPage {...props} /></SiteContext.Provider>);
  return props;
};

const tiles = () => screen.getAllByRole("listitem").map((li) => li.querySelector(".cg-tile-name")?.textContent);
const groups = () => screen.getAllByRole("region").map((r) => r.getAttribute("aria-label")).filter((l) => l?.endsWith("coaches"));
const stage = () => screen.getByRole("region", { name: /, on stage$/ });

// jsdom's media elements don't play: a tap on a tile plays its sample, so this stands in
let play: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  play?.mockRestore();
  play = vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(() => Promise.resolve());
});

describe("the Coaches page", () => {
  it("a failed load says so with Try again, never that a key is missing", () => {
    const onRetry = vi.fn();
    page({ coaches: null, loadError: "Couldn't load your coaches.", onRetry });
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load your coaches.");
    expect(screen.queryByText(/once a key is added/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("with a voice key, shows only the coaches that can speak and what another key would add; with none, every coach to hear first", () => {
    const p = page();
    expect(tiles()).toEqual(["Nolan", "Reed"]);   // Owen and Nora wait for a key
    expect(groups()).toEqual(["Gemini coaches", "Fish Audio coaches"]);   // grouped by service, OpenRouter and Gemini first
    expect(screen.getByTitle("Your coach")).toBeInTheDocument();   // the mark on the tile of the coach coaching you
    // the coach coaching you starts on the stage
    expect(stage()).toHaveAccessibleName("Coach Nolan, on stage");
    expect(within(stage()).getByText("Coaching you now")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hear Coach Reed" }));
    expect(stage()).toHaveAccessibleName("Coach Reed, on stage");
    expect(within(stage()).getByText("Your coach: Nolan")).toBeInTheDocument();
    fireEvent.click(within(stage()).getByRole("button", { name: "Make Reed my coach" }));
    expect(p.onCoach).toHaveBeenCalledWith("coach-reed-fish");
    expect(screen.getByText("More coaches with another voice key:")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "OpenRouter" }));   // OpenRouter before Inworld
    expect(p.onAddKey).toHaveBeenCalledWith("openrouter");
    expect(screen.getAllByRole("button", { name: /^(OpenRouter|Inworld)$/ }).map((b) => b.textContent)).toEqual(["OpenRouter", "Inworld"]);
    fireEvent.click(screen.getByRole("button", { name: "Close, back to the chat" }));
    expect(p.onClose).toHaveBeenCalled();
    cleanup();

    // with no voice key: every coach by service to hear first, one Add key a service
    const six = ["Tess", "Leah"].map((n) => ({ ...coaches[3], slug: `coach-${n.toLowerCase()}-openrouter`, first: n, name: `Coach ${n}` }));
    const q = page({ coaches: [...coaches, ...six].map((c) => ({ ...c, ready: false, current: c.slug === "coach-reed-fish" })) });
    expect(screen.queryByTitle("Your coach")).toBeNull();   // never on a coach that can't speak
    expect(screen.getAllByRole("listitem").filter((li) => li.className.includes("cur"))).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /^Make .+ my coach$/ })).toBeNull();
    expect(screen.getByText(/add the key for the coaches you like/)).toBeInTheDocument();
    expect(groups()).toEqual(["OpenRouter coaches", "Gemini coaches", "Fish Audio coaches", "Inworld coaches"]);
    expect(screen.getByText("OpenRouter, powered by ElevenLabs · 3 coaches")).toBeInTheDocument();
    expect(screen.getByText("Gemini · 1 coach")).toBeInTheDocument();
    // the first coach starts on the stage, with their sample, price and the key that would let you choose them
    expect(stage()).toHaveAccessibleName("Coach Leah, on stage");
    expect(screen.getAllByText("Direct and precise.").length).toBeGreaterThan(0);   // how each talks, on their tile
    expect(within(stage()).getByText(/about \$0\.80 a workout/)).toBeInTheDocument();
    expect(screen.getByLabelText("Coach Leah's sample")).toHaveAttribute("src", "/api/coaches/coach-leah-openrouter/sample.mp3");
    expect(screen.getByRole("button", { name: "Play Coach Leah's sample" })).toBeInTheDocument();   // heard before any key
    fireEvent.click(screen.getByRole("button", { name: "Hear Coach Nora" }));
    expect(screen.getByLabelText("Coach Nora's sample")).toHaveAttribute("src", "/api/coaches/coach-nora-openrouter/sample.mp3");
    expect(screen.getAllByRole("button", { name: /^Add an? .+ key$/ })).toHaveLength(4);   // one a service
    fireEvent.click(screen.getByRole("button", { name: "Add an OpenRouter key" }));
    expect(q.onAddKey).toHaveBeenCalledWith("openrouter");
    fireEvent.click(within(stage()).getByRole("button", { name: "Add an OpenRouter key to choose Nora" }));
    expect(q.onAddKey).toHaveBeenCalledTimes(2);
  });

  it("a tap puts a coach on the stage and plays their sample; Choose chooses", () => {
    const p = page({ coaches: [...coaches, { ...coaches[3], slug: "coach-tess-openrouter", first: "Tess", name: "Coach Tess", ready: true }] });
    expect(screen.getByRole("button", { name: "Hear Coach Nolan" })).toHaveAttribute("aria-pressed", "true");
    expect(play).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Hear Coach Tess" }));
    expect(screen.getByRole("button", { name: "Hear Coach Tess" })).toHaveAttribute("aria-pressed", "true");
    expect(play).toHaveBeenCalled();
    expect(p.onCoach).not.toHaveBeenCalled();   // hearing never chooses
    fireEvent.click(within(stage()).getByRole("button", { name: "Make Tess my coach" }));
    expect(p.onCoach).toHaveBeenCalledWith("coach-tess-openrouter");
  });

  it("on the hosted site: one grid A to Z, no service in the bar, and who makes the voices at the foot", () => {
    const gem = (first: string, gender: "f" | "m", current = false): StartCoach => ({
      slug: `coach-${first.toLowerCase()}-openrouter`, name: `Coach ${first}`, first, service: "openrouter",
      service_name: "OpenRouter", ready: true, own: false, current, sample: true, powered_by: "Google Gemini", gender,
      tone: `${first} talks like this.` });
    const p = page({ coaches: [gem("Cole", "m"), gem("Ana", "f", true), gem("Ruth", "f"), gem("Ben", "m")] }, true);
    expect(groups()).toEqual([]);   // one grid, no headings
    expect(tiles()).toEqual(["Ana", "Ben", "Cole", "Ruth"]);
    expect(screen.getByText("Ruth talks like this.")).toBeInTheDocument();   // each tile says how the coach talks
    expect(stage()).toHaveAccessibleName("Coach Ana, on stage");
    expect(within(stage()).queryByText(/OpenRouter/)).toBeNull();
    expect(screen.getByText("Voices by Google Gemini, through OpenRouter")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hear Coach Ruth" }));
    expect(play).toHaveBeenCalled();
    expect(tiles()).toEqual(["Ana", "Ben", "Cole", "Ruth"]);   // hearing a coach moves no tile
    fireEvent.click(within(stage()).getByRole("button", { name: "Make Ruth my coach" }));
    expect(p.onCoach).toHaveBeenCalledWith("coach-ruth-openrouter");
  });
});
