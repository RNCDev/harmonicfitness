import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CORAL } from "./brand";
import { Mark } from "./Mark";

describe("the logo", () => {
  it("draws the mark as one coral line and names the app on the wordmark", () => {
    const { container } = render(<Mark version="0.43.0 (abc1234)" />);
    expect(screen.getByRole("img", { name: "HarmonicFitness" })).toBeInTheDocument();
    const line = container.querySelector(".mark-icon path");
    expect(line).not.toBeNull();
    expect(line?.getAttribute("stroke")).toBe(CORAL);
    expect(line?.getAttribute("fill")).toBe("none");
    expect(container.querySelector(".mark-icon rect")).toBeNull();
    expect(screen.getByText("0.43.0 (abc1234)")).toBeInTheDocument();
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
});
