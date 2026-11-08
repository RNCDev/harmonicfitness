// The stylesheet keeps to its tokens. theme.css is the list of parts (styles/*.css); every rule here holds for each
// part: no colour typed in by hand and no tint mixed in a rule, colours only by their role, no token used that
// tokens.css doesn't define, no type size, spacing or control size typed in pixels, line heights, opacities, durations
// and focus rings only from their tokens, corners only from the corner tokens, the four breakpoints, and no hover look
// on a disabled control.
import { describe, expect, it } from "vitest";
import theme from "./theme.css?raw";
import tokens from "./tokens.css?raw";

const PARTS = import.meta.glob("./styles/*.css", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
const strip = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, "");
const each = Object.entries(PARTS).map(([path, css]) => [path, strip(css)] as const);
/** What each part breaks of one rule: "part: what", so a failure says where. */
const broken = (find: (css: string) => string[]) => each.flatMap(([p, css]) => find(css).map((x) => `${p}: ${x}`));
const all = (re: RegExp) => (css: string) => css.match(re) ?? [];

describe("theme.css", () => {
  it("imports the tokens first, then every part in styles/, and holds no rules of its own", () => {
    const css = strip(theme).trim();
    expect(css.startsWith('@import "./tokens.css";')).toBe(true);
    const imported = [...css.matchAll(/@import "\.\/(styles\/[\w-]+\.css)";/g)].map((m) => `./${m[1]}`);
    expect(imported.sort()).toEqual(Object.keys(PARTS).sort());
    expect(css.replace(/@import "[^"]+";/g, "").trim()).toBe("");
  });

  it("types in no colour, and mixes no tint: every one comes from tokens.css", () => {
    expect(broken(all(/#[0-9a-fA-F]{3,8}\b/g))).toEqual([]);
    expect(broken(all(/\brgba?\(|\bhsla?\(/g))).toEqual([]);
    expect(broken(all(/color-mix\(/g))).toEqual([]);
  });

  it("uses only tokens that tokens.css defines", () => {
    const defined = new Set([...strip(tokens).matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
    const inline = new Set(["--done", "--hold"]);   // set on the element by its component (a seek's fill, a section's room)
    expect(broken((css) => {
      const local = new Set([...css.matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]));
      return [...new Set([...css.matchAll(/var\((--[\w-]+)/g)].map((m) => m[1]))]
        .filter((t) => !defined.has(t) && !local.has(t) && !inline.has(t));
    })).toEqual([]);
  });

  it("types no font size: the type scale's tokens, or a size relative to the text around it", () => {
    expect(broken(all(/font(?:-size)?:[^;}]*?(?:\b\d+(?:\.\d+)?px|clamp\()/g))).toEqual([]);
  });

  it("types no spacing in pixels: the space scale's tokens (a hairline, or a negative nudge, may be typed)", () => {
    const SPACING = /(?:^|[;{\s])(?:padding|margin|gap|row-gap|column-gap|inset|top|left|right|bottom)[\w-]*\s*:([^;}]*)/g;
    expect(broken((css) => [...css.matchAll(SPACING)].flatMap((m) =>
      (m[1].match(/(?<![\w.-])\d+px/g) ?? []).filter((v) => parseInt(v, 10) > 2)))).toEqual([]);
  });

  it("names each colour by its role: the palette is tokens.css's own, never a rule's", () => {
    const PALETTE = /var\(--(ink|ink-2|ink-3|ink-hi|ink-slot|rule|line|paper|sheet|sheet-2|drawer|stop|stop-tint|blue|blue-hi|blue-tint|coral)\)/g;
    expect(broken(all(PALETTE))).toEqual([]);
  });

  it("sizes a control only by the size tokens (a hairline, a small mark under 16px, or a layout width may be typed)", () => {
    const SIZE = /(?:^|[;{\s])(?:width|height|min-width|min-height)\s*:([^;}]*)/g;
    expect(broken((css) => [...css.matchAll(SIZE)].flatMap((m) =>
      (m[1].match(/(?<![\w.-])\d+px/g) ?? []).filter((v) => parseInt(v, 10) >= 16 && parseInt(v, 10) <= 64)))).toEqual([]);
  });

  it("sets line height, opacity, motion and focus only from their tokens", () => {
    // a line's height may also match a control's, so a label sits level with the dot beside it
    expect(broken(all(/line-height:(?!\s*(?:var\(--(?:lh-[\w-]+|chip|control)\)|inherit|normal))[^;}]+/g))).toEqual([]);
    expect(broken(all(/font:[^;}]*\/\s*[\d.]+/g))).toEqual([]);
    expect(broken(all(/opacity:(?!\s*(?:0|1|var\(--(?:o-[\w-]+|disabled)\))\s*(?:[;}!]|$))[^;}]+/g))).toEqual([]);
    expect(broken((css) => (css.match(/(?:transition|animation)[\w-]*:[^;}]+/g) ?? [])
      .flatMap((d) => (d.match(/(?<![\w.-])\d*\.?\d+m?s\b/g) ?? []).filter((t) => t !== ".01ms")))).toEqual([]);
    expect(broken(all(/outline-offset:(?!\s*var\(--focus-(?:offset|inset)\))[^;}]+/g))).toEqual([]);
    expect(broken(all(/outline:\s*\d+px solid[^;}]*/g))).toEqual([]);
  });

  it("rounds corners only by the corner tokens (or a circle)", () => {
    expect(broken((css) => (css.match(/border-radius:\s*[^;}]+/g) ?? []).map((d) => d.trim())
      .filter((d) => !/^border-radius:\s*(var\(--radius-(control|sheet|pill)\)|50%|inherit)$/.test(d)))).toEqual([]);
  });

  it("changes layout only at the four breakpoints tokens.css names", () => {
    expect(broken((css) => [...css.matchAll(/@media[^{]*?\((?:max|min)-width:\s*(\d+)px\)/g)].map((m) => m[1])
      .filter((w) => !["480", "640", "760", "1000"].includes(w)))).toEqual([]);
  });

  it("never gives a disabled control a hover look, and lifts on hover only where a pointer hovers", () => {
    const LINKS = /^(a|a\.[\w-]+|\.keys-bill)$/;   // links can't be disabled
    expect(broken((css) => {
      const outside = css.replace(/@media \(hover: hover\)\s*\{(?:[^{}]*\{[^{}]*\})*\s*\}/g, "");
      return (outside.match(/[^{},]*:hover[^{,]*/g) ?? []).map((s) => s.trim())
        .filter((s) => !/:hover:not\(:disabled\)/.test(s) && !LINKS.test(s.split(":hover")[0].trim()));
    })).toEqual([]);
  });
});
