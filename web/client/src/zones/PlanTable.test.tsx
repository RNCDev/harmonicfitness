import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { PlanTable } from "./PlanTable";

describe("the plan table", () => {
  it("shows rows and total", () => {
    render(<PlanTable plan={{
      format: "Straight sets", equipment: "Bodyweight", total_seconds: 1200,
      left_out: "No pulling: nothing to hang from.",
      rows: [
        { block: "Warm-up", movements: ["Arm circles", "Cat-cow"], dose: "1 round", seconds: 300 },
        { block: "Work", movements: ["Push-up"], dose: "3 x 10", seconds: 905 },
      ],
    }} />);
    const table = screen.getByRole("table");
    expect(within(table).getByText("Warm-up")).toBeInTheDocument();
    expect(within(table).getByText("Arm circles, Cat-cow")).toBeInTheDocument();
    expect(within(table).getByText("5:00")).toBeInTheDocument();
    expect(within(table).getByText("15:05")).toBeInTheDocument();
    expect(screen.getByText(/Straight sets/)).toBeInTheDocument();
    expect(screen.getByText(/Bodyweight/)).toBeInTheDocument();
    expect(screen.getByText(/Total 20:00/)).toBeInTheDocument();
    expect(screen.getByText(/No pulling/)).toBeInTheDocument();
  });
});
