import { describe, expect, it } from "vitest";
import { keepLineBreaks } from "./lines";

describe("keepLineBreaks", () => {
  it("keeps a single break between two lines of text", () => {
    expect(keepLineBreaks("a) Novice\nb) Experienced")).toBe("a) Novice  \nb) Experienced");
  });
  it("leaves paragraphs, tables, lists and code alone", () => {
    expect(keepLineBreaks("One.\n\nTwo.")).toBe("One.\n\nTwo.");
    expect(keepLineBreaks("| a | b |\n|---|---|\n| 1 | 2 |")).toBe("| a | b |\n|---|---|\n| 1 | 2 |");
    expect(keepLineBreaks("- one\n- two")).toBe("- one\n- two");
    expect(keepLineBreaks("```\nx\ny\n```")).toBe("```\nx\ny\n```");
  });
});
