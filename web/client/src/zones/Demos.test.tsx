import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DEMOS, Demos } from "./Demos";

const slides = (c: HTMLElement) => [...c.querySelectorAll<HTMLElement>(".demo-slide")];
const shown = (c: HTMLElement) => slides(c).findIndex((s) => s.classList.contains("on"));

afterEach(() => { vi.restoreAllMocks(); });

describe("the demos on the sign-in page", () => {
  it("picks another ask by name, plays the shown ask's clip from the bucket, and seeks with a slider", () => {
    const play = vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function (this: HTMLMediaElement) {
      this.dispatchEvent(new Event("play"));
      return Promise.resolve();
    });
    const { container } = render(<Demos />);
    // the keyboard can skip through a clip, once its length is known
    expect(screen.getByRole("slider", { name: "Jo's workout, position" })).toBeDisabled();
    expect(screen.getByText("2 min of 30")).toBeInTheDocument();

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
});
