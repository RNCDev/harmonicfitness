import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { requestParts, sentence, type RequestValues } from "../lib/request";
import { RequestLine } from "./RequestLine";

const V: RequestValues = { coach: "Nolan", minutes: 18, place: "at home", type: "core workout", when: "at 7:00 AM",
  body: { "left knee": "easy", neck: "off" } };

describe("the request's two lines", () => {
  it("read as the sentence that's sent, whatever the blanks show", () => {
    for (const body of [{}, V.body, { neck: "off" as const }]) {
      const v = { ...V, body };
      const { container, unmount } = render(<RequestLine parts={requestParts(v)} className="req"
        blank={(p) => <button type="button" className={`blank${p.tone ? " " + p.tone : ""}`}>{p.blank}</button>} />);
      const lines = [...container.querySelectorAll("p")];
      expect(lines.map((p) => p.className)).toEqual(["req", "req req-2"]);
      expect(lines.map((p) => p.textContent).join(" ")).toBe(sentence(v));
      unmount();
    }
  });

  it("counts the words before each piece, so a turn can flip them in one after another", () => {
    const at: [string, number][] = [];
    render(<RequestLine parts={requestParts(V)} className="req"
      blank={(p, n) => { at.push([p.blank!, n]); return p.blank; }}
      fixed={(text, n) => { at.push([text.trim(), n]); return text; }} />);
    // "Hey, coach" is two words, so the coach's name is the third (a lone comma counts as one); the second line goes on counting
    expect(at.slice(0, 4)).toEqual([["Hey, coach", 0], ["Nolan", 2], [", I'd like an", 3], ["18-minute", 7]]);
    expect(at.find(([t]) => t === "Go easy on my")).toEqual(["Go easy on my", 17]);
    expect(at.find(([t]) => t === "neck")).toEqual(["neck", 28]);
  });
});
