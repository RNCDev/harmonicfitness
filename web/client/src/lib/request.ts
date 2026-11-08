// The first screen's request as words: the blanks' choices, how each reads in the sentence, and the sentence as
// it's sent. Pure: Starter.tsx shows it, BodyChart.tsx fills its second line, Demos.tsx reads the demos with it.
import type { StartInfo, StartKit } from "./api";
import { ahead } from "./when";
import { article, listAnd as list } from "./format";

/** The areas a listener can name, head to feet: the body chart's rows. */
export const ROWS = ["neck", "shoulder", "elbow", "wrist", "rib", "low back", "hip", "groin", "hamstring", "knee", "calf",
  "ankle", "foot"];
/** Where a new group starts: the trunk, then the legs. */
export const GROUP_START = new Set(["rib", "hamstring"]);
/** The areas with a left and a right. */
export const SIDED = new Set(["foot", "ankle", "calf", "knee", "hamstring", "hip", "groin", "rib", "shoulder", "elbow", "wrist"]);
export const MINUTES = [10, 15, 20, 25, 30, 40, 45, 60];
/** What to do, as it reads after "a 25-minute": the session goals in plain words, and the usual targets. */
export const TYPES = ["full-body workout", "strength workout", "cardio workout", "mobility session", "leg workout",
  "upper-body workout", "core workout"];
const GOAL_WORDS: Record<string, string> = { strength: "strength workout", general: "full-body workout",
  conditioning: "cardio workout", mobility: "mobility session" };
const TARGET_WORDS: Record<string, string> = { legs: "leg workout", "upper body": "upper-body workout", core: "core workout" };
const PRESET_WORDS: Record<string, string> = { "hotel-room": "in a hotel room", "hotel-gym": "in a hotel gym",
  "full-gym": "at the gym", bodyweight: "with no equipment" };

/** How much care a body part takes today: go easy, or keep off. */
export type Level = "easy" | "off";

/** The words for a kit after "a 25-minute workout": "at home", "in a hotel room", "with my travel kit". */
export function kitWords(k: StartKit): string {
  if (k.preset) return PRESET_WORDS[k.id] ?? `with ${k.label}`;
  return k.id.toLowerCase() === "home" ? "at home" : `with my ${k.label} kit`;
}

/** "left knee", "low back": a limit's area as the request says it. */
export const areaName = (area: string, side: string | null) => `${side ? side + " " : ""}${area.replace(/-/g, " ")}`;

/** The workout type a suggestion picks, when it names one we offer. */
export function suggested(info: StartInfo | null): string | null {
  const s = info?.suggest;
  if (!s) return null;
  return (s.target && TARGET_WORDS[s.target]) || GOAL_WORDS[s.goal] || null;
}

/** What the body line says, as shown and as sent. */
export function bodyWords(body: Record<string, Level>): { easy: string[]; off: string[] } {
  return { easy: Object.keys(body).filter((a) => body[a] === "easy"), off: Object.keys(body).filter((a) => body[a] === "off") };
}

/** When, as it reads after the place: ", right now" or ", at 7:00 AM", ", tomorrow at 6:30 AM". */
export function whenWords(at: Date | null, now: Date = new Date()): string {
  if (!at) return "right now";
  const said = ahead(at, now);
  return said.startsWith("tomorrow") || /^[A-Z][a-z]+day /.test(said) ? said : `at ${said}`;
}

/** The request as it's sent. */
export function sentence(v: { coach: string; minutes: number; place: string; type: string; body: Record<string, Level>;
  when?: string }): string {
  const { easy, off } = bodyWords(v.body);
  let care = "Nothing's bothering me today.";
  if (easy.length && off.length) care = `Go easy on my ${list(easy)}, and keep off my ${list(off)} today.`;
  else if (easy.length) care = `Go easy on my ${list(easy)} today.`;
  else if (off.length) care = `Keep off my ${list(off)} today.`;
  return `Hey, coach ${v.coach}, I'd like ${article(v.minutes)} ${v.minutes}-minute ${v.type} ${v.place}, ${v.when ?? "right now"}. ${care}`;
}
