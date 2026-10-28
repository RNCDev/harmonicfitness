import { describe, expect, it } from "vitest";
import { buildWorkoutSentence, setToken, type Token } from "./model";

const OPTIONS = {
  minutes: [10, 15, 20, 25, 30, 45],
  goals: ["conditioning", "general", "mobility", "strength"],
  presets: ["bodyweight", "hotel-gym", "hotel-room"],
};

function token(parts: (string | Token)[], key: string): Token {
  const t = parts.find((p): p is Token => typeof p !== "string" && p.key === key);
  if (!t) throw new Error(`no token ${key}`);
  return t;
}

describe("the workout sentence", () => {
  it("setToken replaces only that token and is pure", () => {
    const m = buildWorkoutSentence(OPTIONS, {});
    const before = JSON.stringify(m);
    const n = setToken(m, "minutes", 30);
    expect(JSON.stringify(m)).toBe(before);              // the original is untouched
    expect(n).not.toBe(m);
    expect(token(n.parts, "minutes").value).toBe(30);
    expect(token(n.parts, "goal")).toBe(token(m.parts, "goal"));      // the others are the same objects
    expect(token(n.parts, "preset")).toBe(token(m.parts, "preset"));
    expect(n.parts.filter((p) => typeof p === "string")).toEqual(
      m.parts.filter((p) => typeof p === "string"));
  });


  it("keeps minutes a number and labels presets in words", () => {
    const m = setToken(buildWorkoutSentence(OPTIONS, {}), "preset", "hotel-gym");
    expect(token(m.parts, "preset").options.find((o) => o.value === "hotel-gym")?.label).toBe("a hotel gym");
    expect(typeof token(m.parts, "minutes").value).toBe("number");
    expect(token(m.parts, "preset").value).toBe("hotel-gym");
  });

  it("takes a chosen value and falls back when the options lack the default", () => {
    const m = buildWorkoutSentence({ minutes: [10, 15], goals: ["mobility"], presets: ["hotel-room"] },
      { goal: "mobility" });
    expect([token(m.parts, "minutes").value, token(m.parts, "goal").value, token(m.parts, "preset").value])
      .toEqual([10, "mobility", "hotel-room"]);
  });
});
