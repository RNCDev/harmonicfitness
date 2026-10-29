import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { StartInfo } from "../api";
import { kitWords, sentence, Starter } from "./Starter";

const info: StartInfo = {
  coaches: [
    { slug: "coach-reed-fish", name: "Coach Reed", first: "Reed", service: "fish", service_name: "Fish Audio", ready: true, own: false, current: true },
    { slug: "coach-nolan-gemini", name: "Coach Nolan", first: "Nolan", service: "gemini", service_name: "Gemini", ready: true, own: false, current: false },
    { slug: "coach-owen-inworld", name: "Coach Owen", first: "Owen", service: "inworld", service_name: "Inworld", ready: false, own: false, current: false },
  ],
  kits: [{ id: "home", label: "home", preset: false }, { id: "hotel-room", label: "a hotel room", preset: true }],
  minutes: 30,
  limits: [{ area: "knee", side: "left", level: "delicate" }],
  suggest: { goal: "targeted", target: "legs", reason: "legs: last trained 6 days ago" },
  setup_quick: false,
};

const slot = (name: RegExp) => screen.getByRole("button", { name });

describe("the starter", () => {
  it("fills the blanks from what the app knows", () => {
    render(<Starter info={info} onStart={vi.fn()} onFill={vi.fn()} />);
    expect(slot(/^Coach: Reed$/)).toBeInTheDocument();
    expect(slot(/^Length: 30 minutes$/)).toBeInTheDocument();
    expect(slot(/^Where: at home$/)).toBeInTheDocument();
    expect(slot(/^Workout: a leg day$/)).toBeInTheDocument();
    expect(slot(/^Go easy on: left knee$/)).toBeInTheDocument();
    expect(slot(/^How you feel: pick one$/)).toBeInTheDocument();
    expect(screen.getByText("legs: last trained 6 days ago")).toBeInTheDocument();
  });

  it("offers only the coaches that can speak", () => {
    render(<Starter info={info} onStart={vi.fn()} onFill={vi.fn()} />);
    fireEvent.click(slot(/^Coach:/));
    const opts = within(screen.getByRole("listbox", { name: "Coach" })).getAllByRole("option").map((o) => o.textContent);
    expect(opts).toEqual(["Reed", "Nolan"]);
  });

  it("asks how they feel before it starts, then sends the sentence", () => {
    const onStart = vi.fn();
    render(<Starter info={info} onStart={onStart} onFill={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(onStart).not.toHaveBeenCalled();
    fireEvent.click(within(screen.getByRole("listbox", { name: "How you feel" })).getByRole("option", { name: "a bit tired" }));
    fireEvent.click(slot(/^Where:/));
    fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", { name: "in a hotel room" }));
    fireEvent.click(screen.getByRole("button", { name: "Start" }));
    expect(onStart).toHaveBeenCalledWith(
      "Hey Reed, I've got 30 minutes in a hotel room for a leg day. Easy on my left knee today, and I'm feeling a bit tired.");
  });

  it("can tighten a limit from health notes, never loosen it", () => {
    render(<Starter info={info} onStart={vi.fn()} onFill={vi.fn()} />);
    fireEvent.click(slot(/^Go easy on:/));
    const knee = screen.getByRole("radiogroup", { name: "left knee" });
    expect(within(knee).getByRole("radio", { name: "Fine" })).toBeDisabled();
    fireEvent.click(within(knee).getByRole("radio", { name: "Avoid" }));
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "right shoulder" })).getByRole("radio", { name: "Go easy" }));
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(slot(/^Go easy on: right shoulder$/)).toBeInTheDocument();
    expect(slot(/^Keep off: left knee$/)).toBeInTheDocument();
  });

  it("Escape closes a list and gives focus back to its blank", () => {
    render(<Starter info={info} onStart={vi.fn()} onFill={vi.fn()} />);
    const b = slot(/^Length:/);
    fireEvent.click(b);
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(b).toHaveFocus();
  });

  it("something else: most send at once, feedback goes to the box", () => {
    const onStart = vi.fn(), onFill = vi.fn();
    render(<Starter info={info} onStart={onStart} onFill={onFill} />);
    fireEvent.click(screen.getByRole("button", { name: "Update an injury" }));
    expect(onStart).toHaveBeenCalledWith("I'd like to update an injury.");
    fireEvent.click(screen.getByRole("button", { name: "Feedback on my last workout" }));
    expect(onFill).toHaveBeenCalledWith("Feedback on my last workout: ");
    expect(screen.queryByRole("button", { name: "Finish setting me up" })).toBeNull();
  });

  it("with no voice key, Start waits and says why", () => {
    render(<Starter info={{ ...info, coaches: info.coaches.map((c) => ({ ...c, ready: false })) }} onStart={vi.fn()} onFill={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Start" })).toBeDisabled();
    expect(screen.getByText("Add a voice key in Settings first.")).toBeInTheDocument();
  });

  it("words for kits and the sentence with nothing sore", () => {
    expect(kitWords({ id: "bodyweight", label: "the park", preset: true })).toBe("with no gear");
    expect(kitWords({ id: "travel", label: "travel", preset: false })).toBe("with my travel kit");
    expect(sentence({ coach: "Nolan", minutes: 20, place: "at home", type: "cardio", feel: "fresh", body: {} }))
      .toBe("Hey Nolan, I've got 20 minutes at home for cardio. Nothing's bothering me today, and I'm feeling fresh.");
  });
});
