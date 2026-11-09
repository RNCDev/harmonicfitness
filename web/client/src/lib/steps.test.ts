import { describe, expect, it } from "vitest";
import { planOf, stepsOf } from "./steps";

const PLAN = { rows: [{ what: "Air squat", kind: "movement" as const, segments: 2, seconds: 100 }], seconds: 100 };

describe("the plan while the words are written", () => {
  it("is the newest plan event's, and never a step", () => {
    const events = [{ stage: "step", text: "Planning the script's timing", id: 1, state: "done" },
      { stage: "plan", plan: { ...PLAN, seconds: 90 } }, { stage: "plan", plan: PLAN },
      { stage: "step", text: "Writing your script", id: 2, state: "running" }];
    expect(planOf(events)).toEqual(PLAN);
    expect(stepsOf(events).map((s) => s.text)).toEqual(["Planning the script's timing", "Writing your script"]);
  });

  it("is none until one comes, or when it's empty or malformed", () => {
    expect(planOf([])).toBeNull();
    expect(planOf([{ stage: "plan", plan: { rows: [], seconds: 0 } }])).toBeNull();
    expect(planOf([{ stage: "plan", plan: "nope" }])).toBeNull();
  });
});
