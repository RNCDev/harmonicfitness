// The stylesheet keeps to its tokens: no colour typed in by hand, and no token used that tokens.css doesn't define.
import { describe, expect, it } from "vitest";
import theme from "./theme.css?raw";
import tokens from "./tokens.css?raw";

const strip = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, "");

describe("theme.css", () => {
  it("types in no colour: every one comes from tokens.css", () => {
    const css = strip(theme);
    expect(css.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([]);
    expect(css.match(/\brgba?\(|\bhsla?\(/g) ?? []).toEqual([]);
  });

  it("uses only tokens that tokens.css defines", () => {
    const defined = new Set([...strip(tokens).matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
    const local = new Set([...strip(theme).matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
    const inline = new Set(["--done", "--hold"]);   // set on the element by its component (a seek's fill, a section's room)
    const used = [...new Set([...strip(theme).matchAll(/var\((--[\w-]+)/g)].map((m) => m[1]))];
    expect(used.filter((t) => !defined.has(t) && !local.has(t) && !inline.has(t))).toEqual([]);
  });

  it("imports the tokens first", () => {
    expect(strip(theme).trimStart().startsWith('@import "./tokens.css";')).toBe(true);
  });
});
