// The body chart's marks: each side of each area is OK, go easy or keep off, and a tap moves it one along. The
// health notes set a floor no tap goes below (a side kept off by them stays off). Pure, so the rule that keeps a
// listener's limits is tested on its own (bodyMarks.test.ts).
import type { Level } from "./request";

/** A side's state: fine, go easy, keep off. */
export type Mark = "clear" | Level;
export const MARKS: Mark[] = ["clear", "easy", "off"];
export const MARK_WORDS: Record<Mark, string> = { clear: "ok", easy: "go easy", off: "keep off" };

const rank = (m: Mark) => MARKS.indexOf(m);
/** "knee" from "left knee". */
export const baseArea = (key: string) => key.replace(/^(left|right) /, "");

/** A side's mark in `marks`; a mark with no side holds both sides. */
export function markIn(marks: Record<string, Level>, key: string): Mark {
  return marks[key] ?? (key !== baseArea(key) ? marks[baseArea(key)] : undefined) ?? "clear";
}

/** The marks after a tap on `key`: one along (OK, go easy, keep off, and round again), never below its floor. A
 * sideless mark splits into its two sides once one side changes. */
export function tap(marks: Record<string, Level>, floor: Record<string, Level>, key: string): Record<string, Level> {
  const can = MARKS.filter((m) => rank(m) >= rank(markIn(floor, key)));
  const mark = can[(can.indexOf(markIn(marks, key)) + 1) % can.length];
  const area = baseArea(key);
  const next = { ...marks };
  if (key !== area && area in next) {
    const lv = next[area];
    delete next[area];
    next[`left ${area}`] ??= lv;
    next[`right ${area}`] ??= lv;
  }
  if (mark === "clear") delete next[key];
  else next[key] = mark;
  return next;
}
