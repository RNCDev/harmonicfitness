import { describe, expect, it } from "vitest";
import { markIn, tap } from "./bodyMarks";
import type { Level } from "./request";

describe("the body chart's marks", () => {
  it("move one along with each tap: OK, go easy, keep off, and round again", () => {
    let marks: Record<string, Level> = {};
    marks = tap(marks, {}, "left knee");
    expect(marks).toEqual({ "left knee": "easy" });
    marks = tap(marks, {}, "left knee");
    expect(marks).toEqual({ "left knee": "off" });
    marks = tap(marks, {}, "left knee");
    expect(marks).toEqual({});
  });

  it("never go below the health notes' floor", () => {
    const floor = { "left knee": "easy" as const };
    let marks: Record<string, Level> = { ...floor };
    marks = tap(marks, floor, "left knee");
    expect(marks).toEqual({ "left knee": "off" });
    marks = tap(marks, floor, "left knee");
    expect(marks).toEqual({ "left knee": "easy" });   // back to the floor, never to OK
    const kept = { "neck": "off" as const };
    expect(tap(kept, kept, "neck")).toEqual({ neck: "off" });   // a side kept off stays off
  });

  it("split a sideless limit into its two sides once one side changes", () => {
    const floor = { hip: "easy" as const };
    expect(markIn(floor, "right hip")).toBe("easy");
    expect(tap({ ...floor }, floor, "left hip")).toEqual({ "left hip": "off", "right hip": "easy" });
  });
});
