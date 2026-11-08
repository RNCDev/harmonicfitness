import { describe, expect, it } from "vitest";
import type { StartInfo } from "./api";
import { areaName, kitWords, lineText, requestParts, sentence, suggested, type RequestValues } from "./request";

const V: RequestValues = { coach: "Nolan", minutes: 25, place: "at home", type: "leg workout", body: {} };
/** A start screen's answer that suggests `suggest`, the rest empty. */
const info = (suggest: StartInfo["suggest"]): StartInfo =>
  ({ coaches: [], kits: [], minutes: 25, limits: [], suggest, setup_quick: false });
const blanks = (v: RequestValues) => requestParts(v).flat().filter((p) => p.blank);

describe("the request's parts", () => {
  it("name each blank for a screen reader and the list it opens", () => {
    expect(blanks(V).map((p) => [p.key, p.label, p.blank])).toEqual([
      ["coach", "Coach", "Nolan"], ["minutes", "Length", "25-minute"], ["type", "Workout", "leg workout"],
      ["place", "Where", "at home"], ["when", "When", "right now"], ["body", "Anything bothering you", "Nothing's bothering me"],
    ]);
  });

  it("mark nothing sore as calm, keep off as off, and go easy as neither", () => {
    expect(blanks(V).find((p) => p.key === "body")?.tone).toBe("calm");
    const body = blanks({ ...V, body: { "left knee": "easy", neck: "off" } }).filter((p) => p.key === "body");
    expect(body.map((p) => [p.label, p.blank, p.tone])).toEqual([["Go easy on", "left knee", undefined], ["Keep off", "neck", "off"]]);
    expect(lineText(requestParts({ ...V, body: { neck: "off" } })[1])).toBe("Keep off my neck today.");
  });
});

describe("the request's words", () => {
  it("for kits, and the request with nothing sore", () => {
    expect(kitWords({ id: "bodyweight", label: "the park", preset: true })).toBe("with no equipment");
    expect(kitWords({ id: "travel", label: "travel", preset: false })).toBe("with my travel kit");
    expect(kitWords({ id: "Home", label: "home", preset: false })).toBe("at home");
    expect(sentence({ coach: "Nolan", minutes: 20, place: "at home", type: "cardio workout", body: {} }))
      .toBe("Hey, coach Nolan, I'd like a 20-minute cardio workout at home, right now. Nothing's bothering me today.");
    expect(sentence({ coach: "Nolan", minutes: 18, place: "at home", type: "core workout", body: { "left knee": "easy", "right knee": "easy", neck: "off" } }))
      .toBe("Hey, coach Nolan, I'd like an 18-minute core workout at home, right now. Go easy on my left knee and right knee, and keep off my neck today.");
  });

  it("for a limit's area and a suggestion", () => {
    expect(areaName("low-back", null)).toBe("low back");
    expect(areaName("knee", "left")).toBe("left knee");
    expect(suggested(info({ goal: "targeted", target: "legs", reason: "" }))).toBe("leg workout");
    expect(suggested(info({ goal: "mobility", reason: "" }))).toBe("mobility session");
    expect(suggested(info({ goal: "targeted", target: "balance", reason: "" }))).toBeNull();   // not one we offer
    expect(suggested(info(null))).toBeNull();
    expect(suggested(null)).toBeNull();
  });
});
