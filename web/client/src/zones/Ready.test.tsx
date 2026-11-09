import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../ready.json", () => ({ default: {
  version: 1, warning: "Made for no one in particular, so not adapted to any injury: skip or ease off anything that hurts.",
  workouts: [
    { slug: "ready-core", order: 5, title: "Core", kind: "core workout", coach: "Coach Priya", minutes: 30,
      about: "A strong middle.", audio: "https://media.test/ready/v1/ready-core.mp3" },
    { slug: "ready-full-body", order: 1, title: "Full body", kind: "full-body workout", coach: "Coach Bea", minutes: 30,
      about: "Every major muscle.", audio: "https://media.test/ready/v1/ready-full-body.mp3" },
  ] } }));

import { ReadyWorkouts } from "./Ready";

describe("the ready-made workouts", () => {
  it("lists each in order, playable, and says they aren't adapted to injuries", () => {
    render(<ReadyWorkouts />);
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Full body · 30 min with Coach Bea");
    expect(rows[1]).toHaveTextContent("Core");
    expect(screen.getByRole("button", { name: "Play Full body with Coach Bea" })).toBeInTheDocument();
    expect(screen.getByText(/not adapted to any injury/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Download the MP3" })[0])
      .toHaveAttribute("href", "https://media.test/ready/v1/ready-full-body.mp3");
  });
});
