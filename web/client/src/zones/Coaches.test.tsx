import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { StartCoach } from "../lib/api";
import { CoachesPage } from "./Coaches";

const coaches: StartCoach[] = [
  { slug: "coach-reed-fish", name: "Coach Reed", first: "Reed", service: "fish", service_name: "Fish Audio", ready: true, own: false, current: false },
  { slug: "coach-nolan-gemini", name: "Coach Nolan", first: "Nolan", service: "gemini", service_name: "Gemini", ready: true, own: false, current: true },
  { slug: "coach-owen-inworld", name: "Coach Owen", first: "Owen", service: "inworld", service_name: "Inworld", ready: false, own: false, current: false },
  { slug: "coach-nora-openrouter", name: "Coach Nora", first: "Nora", service: "openrouter", service_name: "OpenRouter", ready: false, own: false,
    current: false, tone: "Direct and precise.", sample: true, usd_per_workout: 0.8, powered_by: "ElevenLabs" },
];

const page = (over: Partial<Parameters<typeof CoachesPage>[0]> = {}) => {
  const props = { coaches, onCoach: vi.fn(), onAddKey: vi.fn(), onClose: vi.fn(), ...over };
  render(<CoachesPage {...props} />);
  return props;
};

describe("the Coaches page", () => {
  it("a failed load says so with Try again, never that a key is missing", () => {
    const onRetry = vi.fn();
    page({ coaches: null, loadError: "Couldn't load your coaches.", onRetry });
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load your coaches.");
    expect(screen.queryByText(/once a key is added/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("with a voice key, shows only the coaches that can speak, by name, and what another key would add", () => {
    const p = page();
    const names = screen.getAllByRole("listitem").map((li) => li.querySelector("b")?.textContent);
    expect(names).toEqual(["Coach Nolan", "Coach Reed"]);   // Owen and Nora wait for a key
    expect(screen.getAllByRole("region").map((r) => r.getAttribute("aria-label")).filter(Boolean))
      .toEqual(["Gemini coaches", "Fish Audio coaches"]);   // grouped by service, OpenRouter and Gemini first
    expect(screen.getByText("Active")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Choose Reed" }));
    expect(p.onCoach).toHaveBeenCalledWith("coach-reed-fish");
    expect(screen.getByText("More coaches with another voice key:")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "OpenRouter" }));   // OpenRouter before Inworld
    expect(p.onAddKey).toHaveBeenCalledWith("openrouter");
    expect(screen.getAllByRole("button", { name: /^(OpenRouter|Inworld)$/ }).map((b) => b.textContent)).toEqual(["OpenRouter", "Inworld"]);
    fireEvent.click(screen.getByRole("button", { name: "Back to the chat" }));
    expect(p.onClose).toHaveBeenCalled();
  });

  it("with no voice key, shows every coach by service to hear first, one Add key a service", () => {
    const six = ["Tess", "Leah"].map((n) => ({ ...coaches[3], slug: `coach-${n.toLowerCase()}-openrouter`, first: n, name: `Coach ${n}` }));
    const p = page({ coaches: [...coaches, ...six].map((c) => ({ ...c, ready: false, current: c.slug === "coach-reed-fish" })) });
    expect(screen.queryByText("Active")).toBeNull();   // never on a coach that can't speak
    expect(screen.getAllByRole("listitem").filter((li) => li.className.includes("cur"))).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /^Choose/ })).toBeNull();
    expect(screen.getByText(/add the key for the coaches you like/)).toBeInTheDocument();
    const groups = screen.getAllByRole("region").map((r) => r.getAttribute("aria-label")).filter(Boolean);
    expect(groups).toEqual(["OpenRouter coaches", "Gemini coaches", "Fish Audio coaches", "Inworld coaches"]);
    expect(screen.getByText("OpenRouter, powered by ElevenLabs · 3 coaches")).toBeInTheDocument();
    expect(screen.getByText("Gemini · 1 coach")).toBeInTheDocument();
    expect(screen.getAllByText("Direct and precise.")).toHaveLength(3);
    expect(screen.getAllByText("about $0.80 a workout")).toHaveLength(3);
    expect(screen.getByLabelText("Coach Nora's sample")).toHaveAttribute("src", "/api/coaches/coach-nora-openrouter/sample.mp3");
    expect(screen.getByRole("button", { name: "Play Coach Nora's sample" })).toBeInTheDocument();   // heard before any key
    expect(screen.getAllByRole("button", { name: /^Add an? / })).toHaveLength(4);   // one a service
    fireEvent.click(screen.getByRole("button", { name: "Add an OpenRouter key" }));
    expect(p.onAddKey).toHaveBeenCalledWith("openrouter");
  });

  it("the whole card chooses, and the current one is pressed", () => {
    const p = page({ coaches: [...coaches, { ...coaches[3], slug: "coach-tess-openrouter", first: "Tess", name: "Coach Tess", ready: true }] });
    const now = screen.getByRole("button", { name: "Choose Nolan" });
    expect(now).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(now);
    expect(p.onCoach).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Choose Tess" }));
    expect(p.onCoach).toHaveBeenCalledWith("coach-tess-openrouter");
  });

  it("puts the listener's own coaches first in their group, then A to Z, with no tooltip over the card", () => {
    const gemini = (first: string, own: boolean) => ({ ...coaches[1], slug: `coach-${first.toLowerCase()}-gemini`, first,
      name: `Coach ${first}`, own, current: false, tone: `${first}'s line.` });
    page({ coaches: [gemini("June", false), gemini("Dana", true), gemini("Fraser", false), { ...coaches[1] }] });
    const names = screen.getAllByRole("listitem").map((li) => li.querySelector("b")?.textContent);
    expect(names).toEqual(["Coach Dana", "Coach Fraser", "Coach June", "Coach Nolan"]);
    expect(screen.getByText("Yours")).toBeInTheDocument();
    for (const b of screen.getAllByRole("button", { name: /^Choose/ })) expect(b).not.toHaveAttribute("title");
    // the card's own class: never the menu's .pick, whose overflow clipped the Active label
    for (const li of screen.getAllByRole("listitem")) expect(li).not.toHaveClass("pick");
  });

  it("keeps every card in place when another is chosen", () => {
    const props = { onCoach: vi.fn(), onAddKey: vi.fn(), onClose: vi.fn() };
    const { rerender } = render(<CoachesPage coaches={coaches} {...props} />);
    const order = () => screen.getAllByRole("listitem").map((li) => li.querySelector("b")?.textContent);
    const before = order();
    rerender(<CoachesPage coaches={coaches.map((c) => ({ ...c, current: c.first === "Reed" }))} {...props} />);
    expect(order()).toEqual(before);
  });
});
