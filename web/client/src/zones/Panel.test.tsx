import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Panel } from "./Panel";

const ASK = {
  tool_call_id: "t1",
  questions: [{ id: "a", prompt: "How are you?", multi: false, other: false, options: [{ label: "Fine", recommended: true }] }],
};
const PLAN = {
  format: "Straight sets", equipment: "Bodyweight", total_seconds: 600, left_out: "",
  rows: [{ block: "Work", movements: ["Push-up"], dose: "3 x 10", seconds: 600 }],
};

describe("the working panel", () => {
  it("shows the empty state with nothing open", () => {
    render(<Panel />);
    expect(screen.getByText(/then start/)).toBeInTheDocument();
  });

  it("shows the open question before the plan", () => {
    render(<Panel question={ASK} plan={PLAN} />);
    expect(screen.getByRole("group", { name: "How are you?" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows the plan when there is no question", () => {
    render(<Panel plan={PLAN} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
});
