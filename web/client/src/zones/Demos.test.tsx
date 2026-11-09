import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DEMOS, Demos } from "./Demos";
import { sentence } from "../lib/request";

const slides = (c: HTMLElement) => [...c.querySelectorAll<HTMLElement>(".demo-slide")];
const shown = (c: HTMLElement) => slides(c).findIndex((s) => s.classList.contains("on"));
/** A slide's request as one line, its two paragraphs joined as the app sends them. */
const said = (s: HTMLElement) => [...s.querySelectorAll("p.demo-req")].map((p) => p.textContent).join(" ");

afterEach(() => { vi.restoreAllMocks(); });

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

  it("keeps a blank's comma or full stop with it, so neither starts a line", () => {
    const { container } = render(<Demos />);
    const glues = [...slides(container)[0].querySelectorAll(".demo-glue")].map((g) => g.textContent);
    expect(glues).toContain("Priya,");
    expect(glues).toContain("in a hotel room,");
    expect(glues).toContain("right now.");
  });

  it("says who asked above the request, and what changed for an injury under it", () => {
    const { container } = render(<Demos />);
    expect(slides(container)[0].querySelector(".demo-who")).toHaveTextContent("Jo · travels for work · into Space history and Jazz");
    expect(slides(container)[0].querySelector(".demo-note")).toHaveTextContent(/^What changed for Jo\./);
    const ben = slides(container)[DEMOS.findIndex((d) => d.slug === "ben")];
    expect(ben.querySelector(".demo-note")).toHaveTextContent("Hear two minutes of the 25-minute workout Coach Bea made.");
  });

  it("picks another ask by name, and plays the shown ask's clip from the bucket", () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function (this: HTMLMediaElement) {
      this.dispatchEvent(new Event("play"));
      return Promise.resolve();
    });
    const { container } = render(<Demos />);
    expect(screen.getByRole("button", { name: "Jo" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Lena" }));
    expect(shown(container)).toBe(DEMOS.findIndex((d) => d.slug === "lena"));
    expect(screen.getByRole("button", { name: "Lena" })).toHaveAttribute("aria-pressed", "true");
    expect(slides(container)[shown(container)]).toHaveClass("turn");   // the words flip in
    fireEvent.click(screen.getByRole("button", { name: "Play Lena's workout" }));
    expect(play).toHaveBeenCalledTimes(1);
    expect(container.querySelector("audio")!.getAttribute("src")).toBe(
      "https://harmonicfitness-media.fly.storage.tigris.dev/demos/v1/lena.mp3");
    expect(screen.getByRole("button", { name: "Pause Lena's workout" })).toBeInTheDocument();
  });

  it("seeks with a slider, so the keyboard can skip through a clip", () => {
    render(<Demos />);
    const seek = screen.getByRole("slider", { name: "Jo's workout, position" });
    expect(seek).toBeDisabled();   // until the clip's length is known
    expect(screen.getByText("2 min of 30")).toBeInTheDocument();
  });
});
