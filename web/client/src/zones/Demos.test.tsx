import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { DEMOS, Demos, TURN_MS } from "./Demos";
import { sentence } from "../lib/request";

const slides = (c: HTMLElement) => [...c.querySelectorAll<HTMLElement>(".demo-slide")];
const shown = (c: HTMLElement) => slides(c).findIndex((s) => s.classList.contains("on"));
/** A slide's request as one line, its two paragraphs joined as the app sends them. */
const said = (s: HTMLElement) => [...s.querySelectorAll("p.demo-req")].map((p) => p.textContent).join(" ");

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe("the demos on the sign-in page", () => {
  it("shows each ask as the app's own request would read", () => {
    const { container } = render(<Demos />);
    expect(slides(container)).toHaveLength(DEMOS.length);
    slides(container).forEach((s, i) => {
      const d = DEMOS[i], r = d.request;
      const body: Record<string, "easy" | "off"> = r.care === "none" ? {} : { [r.area!]: r.care as "easy" | "off" };
      expect(said(s)).toBe(sentence({ coach: d.coach.replace(/^Coach /, ""), minutes: d.minutes, type: r.type,
        place: r.place, when: r.when, body }));
    });
    expect(said(slides(container)[0])).toBe(
      "Hey, coach Priya, I'd like a 30-minute full-body workout in a hotel room, right now. Go easy on my left knee today.");
    const frank = slides(container)[DEMOS.findIndex((d) => d.slug === "frank")];
    expect(frank.querySelector(".blank.off")).toHaveTextContent("right shoulder");   // keep off: the brick underline
  });

  it("says who asked and what they're into, above the request", () => {
    const { container } = render(<Demos />);
    expect(slides(container)[0].querySelector(".demo-who")).toHaveTextContent("Jo · travels for work · into Space history and Jazz");
  });

  it("moves by the arrows and the dots, and plays the shown ask's clip from the bucket", () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function (this: HTMLMediaElement) {
      this.dispatchEvent(new Event("play"));
      return Promise.resolve();
    });
    const { container } = render(<Demos />);
    fireEvent.click(screen.getByRole("button", { name: "Next ask" }));
    expect(shown(container)).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Previous ask" }));
    fireEvent.click(screen.getByRole("button", { name: "Previous ask" }));
    expect(shown(container)).toBe(DEMOS.length - 1);   // round from the first to the last
    fireEvent.click(screen.getByRole("button", { name: "Lena's ask" }));
    expect(shown(container)).toBe(DEMOS.findIndex((d) => d.slug === "lena"));
    fireEvent.click(screen.getByRole("button", { name: "Play Lena's workout" }));
    expect(play).toHaveBeenCalledTimes(1);
    expect(container.querySelector("audio")!.getAttribute("src")).toBe(
      "https://harmonicfitness-media.fly.storage.tigris.dev/demos/v1/lena.mp3");
    expect(screen.getByRole("button", { name: "Pause Lena's workout" })).toBeInTheDocument();
  });

  it("turns on its own until someone taps it, then stays", () => {
    vi.useFakeTimers();
    const { container } = render(<Demos />);
    expect(shown(container)).toBe(0);
    act(() => { vi.advanceTimersByTime(TURN_MS); });
    expect(shown(container)).toBe(1);
    expect(slides(container)[1]).toHaveClass("turn");   // the words flip in
    fireEvent.click(screen.getByRole("button", { name: "Next ask" }));
    act(() => { vi.advanceTimersByTime(TURN_MS * 3); });
    expect(shown(container)).toBe(2);
  });

  it("keeps who asked and the moments behind one tap", () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    render(<Demos />);
    expect(screen.queryByText(/In words/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "About Jo, and what you'll hear" }));
    expect(screen.getByText(`“${DEMOS[0].ask}”`)).toBeInTheDocument();
    expect(screen.getByText(/What changed for Jo\./)).toBeInTheDocument();
    Object.defineProperty(HTMLMediaElement.prototype, "readyState", { configurable: true, get: () => 4 });
    fireEvent.click(screen.getByRole("button", { name: /0:56/ }));
    expect(play).toHaveBeenCalled();
    delete (HTMLMediaElement.prototype as unknown as Record<string, unknown>).readyState;
  });

  it("seeks with a slider, so the keyboard can skip through a clip", () => {
    render(<Demos />);
    const seek = screen.getByRole("slider", { name: "Jo's workout, position" });
    expect(seek).toBeDisabled();   // until the clip's length is known
    expect(screen.getByText("2 min")).toBeInTheDocument();
  });
});
