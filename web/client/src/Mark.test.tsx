import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MARK, UNLIT, WORDMARK_H } from "./brand";
import { Mark, Meter } from "./Mark";

afterEach(() => vi.useRealTimers());

const lit = (svg: Element | null) =>
  [...(svg?.querySelectorAll("rect") ?? [])].map((r) => r.getAttribute("opacity") !== String(UNLIT));

describe("the logo", () => {
  it("draws the wordmark's H as the meter's segments, some unlit, and names the app", () => {
    const { container } = render(<Mark version="0.46.1 (abc1234)" />);
    expect(screen.getByRole("img", { name: "HarmonicFitness" })).toBeInTheDocument();
    const meter = container.querySelector(".mark-name .meter");
    expect(meter?.querySelectorAll("rect")).toHaveLength(WORDMARK_H.letter.segments.length);
    const reading = lit(meter);
    expect(reading).toEqual(WORDMARK_H.letter.segments.map((s) => s.lit));
    expect(reading).toContain(false);
    expect(screen.getByText("0.46.1 (abc1234)")).toBeInTheDocument();
  });

  it("moves the H only while live", () => {
    vi.useFakeTimers();
    const { container, rerender } = render(<Mark live />);
    act(() => { vi.advanceTimersByTime(110); });
    expect(container.querySelector(".meter")?.getAttribute("data-live")).toBe("true");
    rerender(<Mark />);
    expect(container.querySelector(".meter")?.getAttribute("data-live")).toBeNull();
  });

  it("draws the wordmark in the text colour, FITNESS lighter", () => {
    const { container } = render(<Mark />);
    const paths = container.querySelectorAll(".mark-name path");
    expect(paths).toHaveLength(2);
    expect(paths[0].getAttribute("fill")).toBe("currentColor");
    expect(paths[1].getAttribute("fill")).toBe("currentColor");
    expect(Number(paths[1].getAttribute("opacity"))).toBeLessThan(1);
    expect(container.querySelector(".ver")).toBeNull();
  });

  it("keeps the middle bar lit and colours the meter by height", () => {
    for (const form of Object.values(MARK)) {
      const middle = form.segments.filter((s) => s.ch === "M");
      expect(middle.length).toBeGreaterThan(0);
      expect(middle.every((s) => s.lit)).toBe(true);
      const left = form.segments.filter((s) => s.ch === "L").sort((a, b) => a.fb - b.fb);
      expect(new Set(left.map((s) => s.fill)).size).toBe(left.length);
    }
  });
});

describe("the meter in motion", () => {
  it("moves while live and settles back to the still mark", () => {
    vi.useFakeTimers();
    const { container, rerender } = render(<Meter form="full" height={40} live />);
    const svg = () => container.querySelector("svg");
    const still = MARK.full.segments.map((s) => s.lit);
    const seen = new Set<string>();
    for (let i = 0; i < 30; i++) {
      act(() => { vi.advanceTimersByTime(110); });
      seen.add(lit(svg()).join());
    }
    expect(seen.size).toBeGreaterThan(3);
    expect(svg()?.querySelector(".meter")?.getAttribute("data-live")).toBe("true");
    rerender(<Meter form="full" height={40} live={false} />);
    expect(lit(svg())).toEqual(still);
    expect(svg()?.querySelector(".meter")?.getAttribute("data-live")).toBeNull();
  });

  it("stays still when the system asks for reduced motion", () => {
    vi.useFakeTimers();
    const mm = vi.spyOn(window, "matchMedia").mockImplementation((q: string) =>
      ({ matches: q.includes("reduce"), media: q, addEventListener() {}, removeEventListener() {} }) as unknown as MediaQueryList);
    const { container } = render(<Meter form="full" height={40} live />);
    act(() => { vi.advanceTimersByTime(1000); });
    expect(lit(container.querySelector("svg"))).toEqual(MARK.full.segments.map((s) => s.lit));
    mm.mockRestore();
  });
});
