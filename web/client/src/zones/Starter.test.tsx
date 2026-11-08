import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { StartInfo } from "../lib/api";
import { kitWords, sentence, whenWords } from "../lib/request";
import { Starter } from "./Starter";
import { slots, withOffset } from "../lib/when";

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
  it("a failed load keeps the request, says why and offers Try again, not \"Choose your coach\"", () => {
    const onRetry = vi.fn();
    const none: StartInfo = { coaches: [], kits: [], minutes: 25, limits: [], suggest: null, setup_quick: false };
    render(<Starter info={none} onStart={vi.fn()} onOpenCoaches={vi.fn()} loadError="Couldn't load your coaches." onRetry={onRetry} />);
    expect(screen.queryByText("Choose your coach.")).toBeNull();
    expect(screen.queryByText("Add a voice key in Settings first.")).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load your coaches.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("fills the blanks from what the app knows", () => {
    render(<Starter info={info} onStart={vi.fn()} />);
    expect(slot(/^Coach: Reed$/)).toBeInTheDocument();
    expect(slot(/^Length: 30-minute$/)).toBeInTheDocument();
    expect(slot(/^Where: at home$/)).toBeInTheDocument();
    expect(slot(/^Workout: leg workout$/)).toBeInTheDocument();
    expect(slot(/^Go easy on: left knee$/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /How you feel/ })).toBeNull();
    expect(screen.getByText("Suggested because of your log: legs: last trained 6 days ago.")).toBeInTheDocument();
  });

  it("moves through a list from the keyboard, and closes it when focus leaves", () => {
    render(<Starter info={info} onStart={vi.fn()} />);
    fireEvent.click(slot(/^Length:/));
    const list = screen.getByRole("listbox", { name: "Length" });
    const opts = within(list).getAllByRole("option");
    expect(opts.find((o) => o.getAttribute("aria-selected") === "true")).toHaveFocus();   // the chosen one first
    fireEvent.keyDown(list, { key: "End" });
    expect(opts[opts.length - 1]).toHaveFocus();
    fireEvent.keyDown(list, { key: "Home" });
    expect(opts[0]).toHaveFocus();
    fireEvent.keyDown(list, { key: "4" });
    expect(opts.find((o) => o.textContent === "40 minutes")).toHaveFocus();
    // Tab onward: focus lands on the next control, and the list closes behind it
    fireEvent.blur(opts[0], { relatedTarget: slot(/^Workout:/) });
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("opens the body chart as a modal dialog over a scrim", () => {
    render(<Starter info={info} onStart={vi.fn()} />);
    fireEvent.click(slot(/^Go easy on:/));
    const chart = screen.getByRole("dialog", { name: "Anything bothering you today?" });
    expect(chart).toHaveAttribute("aria-modal", "true");
    expect(document.querySelector(".pick-scrim")).not.toBeNull();
    // drawn on the body, beside the page, which sleeps while it's open
    expect(chart.parentElement).toBe(document.body);
    const page = chart.ownerDocument.querySelector(".starter")!.closest("body > *")!;
    expect(page).toHaveAttribute("inert");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(page).not.toHaveAttribute("inert");
    expect(slot(/^Go easy on:/)).toHaveFocus();
  });

  it("offers only the coaches that can speak", () => {
    render(<Starter info={info} onStart={vi.fn()} />);
    fireEvent.click(slot(/^Coach:/));
    const opts = within(screen.getByRole("listbox", { name: "Coach" })).getAllByRole("option").map((o) => o.textContent);
    expect(opts).toEqual(["Reed", "Nolan"]);
  });

  it("hands a picked coach to the page, and follows the page's current coach", () => {
    const onCoach = vi.fn();
    const { rerender } = render(<Starter info={info} onStart={vi.fn()} onCoach={onCoach} />);
    fireEvent.click(slot(/^Coach:/));
    fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", { name: "Nolan" }));
    expect(onCoach).toHaveBeenCalledWith("coach-nolan-gemini");
    const now = { ...info, coaches: info.coaches.map((c) => ({ ...c, current: c.first === "Nolan" })) };
    rerender(<Starter info={now} onStart={vi.fn()} onCoach={onCoach} />);
    expect(slot(/^Coach: Nolan$/)).toBeInTheDocument();
  });

  it("plans a workout for a time picked in the sentence: the check-in now, the time sent with it", () => {
    const onStart = vi.fn();
    render(<Starter info={info} onStart={onStart} />);
    expect(slot(/^When: right now$/)).toBeInTheDocument();
    fireEvent.click(slot(/^When:/));
    const opts = within(screen.getByRole("listbox", { name: "When" })).getAllByRole("option");
    expect(opts[0].textContent).toBe("right now");
    fireEvent.click(opts[3]);
    fireEvent.click(screen.getByRole("button", { name: "Plan it for later" }));
    const [line, startAt] = onStart.mock.calls[0];
    expect(line).toMatch(/^Hey, coach Reed, I'd like a 30-minute leg workout at home, (at|tomorrow at) .+\. Go easy/);
    expect(startAt).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00[+-]\d{2}:\d{2}$/);
    expect(new Date(startAt).getTime()).toBe(slots()[2].getTime());
  });

  it("offers every half hour from half an hour ahead, for a day", () => {
    const now = new Date(2026, 10, 3, 9, 10);
    const got = slots(now);
    expect([got[0].getHours(), got[0].getMinutes()]).toEqual([10, 0]);
    expect(got.length).toBe(47);
    expect(got.every((d, i) => i === 0 || d.getTime() - got[i - 1].getTime() === 30 * 60000)).toBe(true);
    expect(whenWords(null)).toBe("right now");
    expect(whenWords(new Date(2026, 10, 3, 19, 30), now)).toMatch(/^at 7:30/);
    expect(whenWords(new Date(2026, 10, 4, 6, 30), now)).toMatch(/^tomorrow at 6:30/);
    expect(withOffset(new Date(2026, 10, 4, 6, 30))).toMatch(/^2026-11-04T06:30:00[+-]\d{2}:\d{2}$/);
  });

  it("sends the request as it reads", () => {
    const onStart = vi.fn();
    render(<Starter info={info} onStart={onStart} />);
    fireEvent.click(slot(/^Where:/));
    fireEvent.click(within(screen.getByRole("listbox")).getByRole("option", { name: "in a hotel room" }));
    fireEvent.click(screen.getByRole("button", { name: "Plan my workout" }));
    expect(onStart).toHaveBeenCalledWith(
      "Hey, coach Reed, I'd like a 30-minute leg workout in a hotel room, right now. Go easy on my left knee today.",
      undefined);
  });

  it("picks what's sore from the body chart: each side toggles OK, go easy, keep off", () => {
    render(<Starter info={{ ...info, limits: [] }} onStart={vi.fn()} />);
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
      { area: "wrist", side: null, level: "off-limits" }] }} onStart={vi.fn()} />);
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
    render(<Starter info={info} onStart={vi.fn()} />);
    const b = slot(/^Length:/);
    fireEvent.click(b);
    fireEvent.keyDown(screen.getByRole("listbox"), { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(b).toHaveFocus();
  });

  it("something else: each sends at once; coaches and feedback have their own pages", async () => {
    const onStart = vi.fn().mockResolvedValue(false);   // refused, so the asks come back
    render(<Starter info={info} onStart={onStart} onOpenCoaches={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /^Update an injury or pain/ }));
    expect(onStart).toHaveBeenCalledWith("I'd like to update an injury.");
    await waitFor(() => expect(screen.getByRole("button", { name: /^Update my interests/ })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: /^Update my interests/ }));   // also what they've enjoyed
    expect(onStart).toHaveBeenCalledWith("I'd like to update my interests.");
    expect(screen.queryByRole("button", { name: /^Tell me what you enjoyed/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Give feedback on my last workout/ })).toBeNull();   // on Logs
    expect(screen.queryByRole("button", { name: /^Pick a different coach/ })).toBeNull();   // the Coaches page
    expect(screen.queryByRole("button", { name: /^Finish setting me up/ })).toBeNull();
  });

  it("an ask on its way keeps the others from sending a second", () => {
    const onStart = vi.fn(() => new Promise<boolean>(() => {}));
    render(<Starter info={info} onStart={onStart} onOpenCoaches={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /^Update an injury or pain/ }));
    expect(screen.getByRole("button", { name: /^Update my interests/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^Update an injury or pain/ })).toHaveAttribute("aria-busy", "true");
  });

  it("setup not finished: Finish setting me up comes first, marked as the one to do", () => {
    render(<Starter info={{ ...info, setup_quick: true }} onStart={vi.fn()} />);
    const items = within(screen.getByRole("navigation", { name: "Other things you can do" })).getAllByRole("button");
    expect(items[0]).toHaveAccessibleName(/^Finish setting me up/);
    expect(items[0]).toHaveClass("lead");
    expect(items.slice(1).some((b) => b.classList.contains("lead"))).toBe(false);
  });

  it("with no voice key, it waits and says why", () => {
    render(<Starter info={{ ...info, coaches: info.coaches.map((c) => ({ ...c, ready: false })) }} onStart={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Plan my workout" })).toBeDisabled();   // no Coaches page to send to
    expect(screen.getByText("Add a voice key in Settings first.")).toBeInTheDocument();
  });

  it("words for kits and the request with nothing sore", () => {
    expect(kitWords({ id: "bodyweight", label: "the park", preset: true })).toBe("with no equipment");
    expect(kitWords({ id: "travel", label: "travel", preset: false })).toBe("with my travel kit");
    expect(sentence({ coach: "Nolan", minutes: 20, place: "at home", type: "cardio workout", body: {} }))
      .toBe("Hey, coach Nolan, I'd like a 20-minute cardio workout at home, right now. Nothing's bothering me today.");
    expect(sentence({ coach: "Nolan", minutes: 18, place: "at home", type: "core workout", body: { "left knee": "easy", "right knee": "easy", neck: "off" } }))
      .toBe("Hey, coach Nolan, I'd like an 18-minute core workout at home, right now. Go easy on my left knee and right knee, and keep off my neck today.");
  });
});

describe("choosing a coach", () => {
  it("with a key that only writes, asks for a coach first", () => {
    const onOpenCoaches = vi.fn();
    render(<Starter info={{ ...info, coaches: info.coaches.map((c) => ({ ...c, ready: false })) }} onStart={vi.fn()}
      onOpenCoaches={onOpenCoaches} />);
    expect(screen.queryByRole("button", { name: "Plan my workout" })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Coach:/ })).toBeNull();   // no sentence to a coach with no voice
    expect(screen.getByText("One more step")).toBeInTheDocument();
    expect(screen.getByText("Choose your coach.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Choose a coach" }));
    expect(onOpenCoaches).toHaveBeenCalled();
  });
});
