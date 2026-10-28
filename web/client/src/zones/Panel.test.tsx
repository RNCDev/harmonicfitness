import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Panel } from "./Panel";
import type { JobView } from "../api";

const BRIEF = "# Today's brief\n\nSome notes.\n\n## The menu\n\n- squat";

describe("the working panel", () => {
  it("renders stages, then the brief", () => {
    const job: JobView = {
      id: 1, state: "done", error: null,
      stages: [{ stage: "folder" }, { stage: "brief" }, { stage: "saved", conflicts: [] }],
      result: { brief_md: BRIEF, stem: "2026-10-27-strength-20" },
    };
    render(<Panel job={job} onRetry={() => {}} />);
    expect(screen.getByText("Getting your notes ready")).toBeInTheDocument();
    expect(screen.getByText("Reading your limits and kit")).toBeInTheDocument();
    expect(screen.getByText("Saved")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Today's brief" })).toBeInTheDocument();
  });

  it("shows the stages as they stream, before the brief", () => {
    const job: JobView = { id: 1, state: "running", error: null, stages: [{ stage: "folder" }], result: null };
    render(<Panel job={job} onRetry={() => {}} />);
    expect(screen.getByText("Getting your notes ready")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });

  it("on failure shows the error and no brief", () => {
    const job: JobView = {
      id: 1, state: "failed", error: "the engine stopped (exit 1)",
      stages: [{ stage: "folder" }, { stage: "brief" }],
      result: { brief_md: BRIEF, stem: "x" },
    };
    render(<Panel job={job} onRetry={() => {}} />);
    expect(screen.getByText(/engine stopped \(exit 1\)/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.queryByText("Today's brief")).not.toBeInTheDocument();
  });

  it("renders no raw HTML from the brief", () => {
    const job: JobView = {
      id: 1, state: "done", error: null, stages: [],
      result: { brief_md: "# Brief\n\n<b id=\"raw\">bold</b>", stem: "x" },
    };
    const { container } = render(<Panel job={job} onRetry={() => {}} />);
    expect(container.querySelector("#raw")).toBeNull();
  });
});
