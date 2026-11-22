import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { StartCoach } from "../lib/api";
import { CoachesPage } from "./Coaches";

const coaches: StartCoach[] = [
  { slug: "coach-reed-fish", name: "Coach Reed", first: "Reed", service: "fish", service_name: "Fish Audio", ready: true, own: false, current: false },
  { slug: "coach-nolan-gemini", name: "Coach Nolan", first: "Nolan", service: "gemini", service_name: "Gemini", ready: true, own: false, current: true },
  { slug: "coach-owen-inworld", name: "Coach Owen", first: "Owen", service: "inworld", service_name: "Inworld", ready: false, own: false, current: false },
  { slug: "coach-nora-openrouter", name: "Coach Nora", first: "Nora", service: "openrouter", service_name: "OpenRouter", ready: false, own: false,
    current: false, tone: "Direct and precise.", sample: true, powered_by: "ElevenLabs" },
];

const page = (over: Partial<Parameters<typeof CoachesPage>[0]> = {}) => {
  const props = { coaches, onCoach: vi.fn(), onClose: vi.fn(), ...over };
  render(<CoachesPage {...props} />);
  return props;
};

const tiles = () => screen.getAllByRole("listitem").map((li) => li.querySelector(".cg-tile-name")?.textContent);
const stage = () => screen.getByRole("region", { name: /, on stage$/ });

// jsdom's media elements don't play: a tap on a tile plays its sample, so this stands in
let play: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  play?.mockRestore();
  play = vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(() => Promise.resolve());
});

describe("the Coaches page", () => {
  it("a failed load says so with Try again", () => {
    const onRetry = vi.fn();
    page({ coaches: null, loadError: "Couldn't load your coaches.", onRetry });
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load your coaches.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
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

  it("one grid A to Z of the coaches that can speak, no service in the bar, and who makes the voices at the foot", () => {
    const gem = (first: string, gender: "f" | "m", current = false): StartCoach => ({
      slug: `coach-${first.toLowerCase()}-openrouter`, name: `Coach ${first}`, first, service: "openrouter",
      service_name: "OpenRouter", ready: true, own: false, current, sample: true, powered_by: "Google Gemini", gender,
      tone: `${first} talks like this.` });
    const p = page({ coaches: [gem("Cole", "m"), gem("Ana", "f", true), gem("Ruth", "f"), gem("Ben", "m"),
      { ...gem("Dora", "f"), ready: false }] });
    expect(tiles()).toEqual(["Ana", "Ben", "Cole", "Ruth"]);   // one that can't speak isn't listed
    expect(screen.getByTitle("Your coach")).toBeInTheDocument();   // the mark on the tile of the coach coaching you
    expect(screen.getByText("Ruth talks like this.")).toBeInTheDocument();   // each tile says how the coach talks
    expect(stage()).toHaveAccessibleName("Coach Ana, on stage");
    expect(within(stage()).getByText("Coaching you now")).toBeInTheDocument();
    expect(within(stage()).queryByText(/OpenRouter/)).toBeNull();
    expect(screen.getByText("Voices by Google Gemini, through OpenRouter")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hear Coach Ruth" }));
    expect(play).toHaveBeenCalled();
    expect(tiles()).toEqual(["Ana", "Ben", "Cole", "Ruth"]);   // hearing a coach moves no tile
    expect(within(stage()).getByText("Your coach: Ana")).toBeInTheDocument();
    fireEvent.click(within(stage()).getByRole("button", { name: "Make Ruth my coach" }));
    expect(p.onCoach).toHaveBeenCalledWith("coach-ruth-openrouter");
    fireEvent.click(screen.getByRole("button", { name: "Close, back to the chat" }));
    expect(p.onClose).toHaveBeenCalled();
  });
});
