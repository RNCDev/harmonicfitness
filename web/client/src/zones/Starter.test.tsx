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
    expect(slot(/^Length: 30-minute$/)).toBeInTheDocument();
    expect(slot(/^Where: at home$/)).toBeInTheDocument();
    expect(slot(/^Workout: leg workout$/)).toBeInTheDocument();
    expect(slot(/^Go easy on: left knee$/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /How you feel/ })).toBeNull();
    expect(screen.getByText("Suggested because of your log: legs: last trained 6 days ago.")).toBeInTheDocument();
  });

  it("offers only the coaches that can speak", () => {
    render(<Starter info={info} onStart={vi.fn()} onFill={vi.fn()} />);
    fireEvent.click(slot(/^Coach:/));
    const opts = within(screen.getByRole("listbox", { name: "Coach" })).getAllByRole("option").map((o) => o.textContent);
    expect(opts).toEqual(["Reed", "Nolan"]);
  });

  it("sends the request as it reads", () => {
    const onStart = vi.fn();
    render(<Starter info={info} onStart={onStart} onFill={vi.fn()} />);
    fireEvent.click(slot(/^Where:/));
    fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", { name: "in a hotel room" }));
    fireEvent.click(screen.getByRole("button", { name: "Plan my workout" }));
    expect(onStart).toHaveBeenCalledWith(
      "Hey, coach Reed, I'd like a 30-minute leg workout in a hotel room. Go easy on my left knee today.");
  });

  it("picks what's sore from the body chart: each side toggles OK, go easy, keep off", () => {
    render(<Starter info={{ ...info, limits: [] }} onStart={vi.fn()} onFill={vi.fn()} />);
    fireEvent.click(slot(/^Anything bothering you:/));
    const chart = screen.getByRole("group", { name: "Body, head to feet" });
    fireEvent.click(within(chart).getByRole("button", { name: "right shoulder: ok" }));
    fireEvent.click(within(chart).getByRole("button", { name: "neck: ok" }));
    fireEvent.click(within(chart).getByRole("button", { name: "neck: go easy" }));
    fireEvent.click(within(chart).getByRole("button", { name: "left knee: ok" }));
    fireEvent.click(within(chart).getByRole("button", { name: "left knee: go easy" }));
    fireEvent.click(within(chart).getByRole("button", { name: "left knee: keep off" }));
    expect(within(chart).getByRole("button", { name: "left knee: ok" })).toBeInTheDocument();   // round again
    expect(screen.getByText("right shoulder", { selector: "dd" })).toBeInTheDocument();   // the summary, under Go easy
    expect(screen.getByText("neck", { selector: "dd" })).toBeInTheDocument();   // and under Keep off
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(slot(/^Go easy on: right shoulder$/)).toBeInTheDocument();
    expect(slot(/^Keep off: neck$/)).toBeInTheDocument();
  });

  it("can tighten a limit from health notes, never loosen it", () => {
    render(<Starter info={{ ...info, limits: [{ area: "knee", side: "left", level: "delicate" },
      { area: "wrist", side: null, level: "off-limits" }] }} onStart={vi.fn()} onFill={vi.fn()} />);
    fireEvent.click(slot(/^Go easy on:/));
    const chart = screen.getByRole("group", { name: "Body, head to feet" });
    fireEvent.click(within(chart).getByRole("button", { name: "left knee: go easy" }));
    fireEvent.click(within(chart).getByRole("button", { name: "left knee: keep off" }));
    expect(within(chart).getByRole("button", { name: "left knee: go easy" })).toBeInTheDocument();   // never OK
    expect(within(chart).getByRole("button", { name: "left wrist: keep off" })).toBeDisabled();   // a sideless limit holds both sides
    expect(within(chart).getByRole("button", { name: "right wrist: keep off" })).toBeDisabled();
    fireEvent.click(within(chart).getByRole("button", { name: "left knee: go easy" }));
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(slot(/^Keep off: left knee and wrist$/)).toBeInTheDocument();
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
    fireEvent.click(screen.getByRole("button", { name: /^Update an injury or pain/ }));
    expect(onStart).toHaveBeenCalledWith("I'd like to update an injury.");
    fireEvent.click(screen.getByRole("button", { name: /^Give feedback on my last workout/ }));
    expect(onFill).toHaveBeenCalledWith("Feedback on my last workout: ");
    expect(screen.queryByRole("button", { name: /^Finish setting me up/ })).toBeNull();
  });

  it("with no voice key, it waits and says why", () => {
    render(<Starter info={{ ...info, coaches: info.coaches.map((c) => ({ ...c, ready: false })) }} onStart={vi.fn()} onFill={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Plan my workout" })).toBeDisabled();
    expect(screen.getByText("Add a voice key in Settings first.")).toBeInTheDocument();
  });

  it("words for kits and the request with nothing sore", () => {
    expect(kitWords({ id: "bodyweight", label: "the park", preset: true })).toBe("with no equipment");
    expect(kitWords({ id: "travel", label: "travel", preset: false })).toBe("with my travel kit");
    expect(sentence({ coach: "Nolan", minutes: 20, place: "at home", type: "cardio workout", body: {} }))
      .toBe("Hey, coach Nolan, I'd like a 20-minute cardio workout at home. Nothing's bothering me today.");
    expect(sentence({ coach: "Nolan", minutes: 18, place: "at home", type: "core workout", body: { "left knee": "easy", "right knee": "easy", neck: "off" } }))
      .toBe("Hey, coach Nolan, I'd like an 18-minute core workout at home. Go easy on my left knee and right knee, and keep off my neck today.");
  });
});
