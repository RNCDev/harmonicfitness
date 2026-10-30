import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { StartCoach } from "../api";
import { ContextColumn } from "./ContextColumn";

vi.mock("./KeysBox", () => ({ KeysBox: () => null }));

const coaches: StartCoach[] = [
  { slug: "coach-reed-fish", name: "Coach Reed", first: "Reed", service: "fish", service_name: "Fish Audio", ready: true, own: false, current: true },
  { slug: "coach-nolan-gemini", name: "Coach Nolan", first: "Nolan", service: "gemini", service_name: "Gemini", ready: true, own: false, current: false },
  { slug: "coach-owen-inworld", name: "Coach Owen", first: "Owen", service: "inworld", service_name: "Inworld", ready: false, own: false, current: false },
];

const drawer = (onCoach?: (slug: string) => void) => render(<ContextColumn username="sam" open onClose={vi.fn()}
  onSignedOut={vi.fn()} onSignOut={vi.fn()} coaches={coaches} onCoach={onCoach} />);

describe("the coaches in Settings", () => {
  it("switches to a coach that can speak, and marks the current one", () => {
    const onCoach = vi.fn();
    drawer(onCoach);
    expect(screen.getByRole("button", { name: /^Coach Reed/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Coaching you · Fish Audio")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^Coach Nolan/ }));
    expect(onCoach).toHaveBeenCalledWith("coach-nolan-gemini");
  });

  it("leaves a coach without a key as a plain row", () => {
    drawer(vi.fn());
    expect(screen.queryByRole("button", { name: /^Coach Owen/ })).toBeNull();
    expect(screen.getByText("Needs an Inworld key")).toBeInTheDocument();
  });
});
