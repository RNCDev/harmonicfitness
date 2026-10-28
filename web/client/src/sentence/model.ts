// The editable sentence: plain words and tokens, each token a setting with its choices.

export type Option = { value: string | number; label: string };
export type Token = { key: string; value: string | number; options: Option[]; why: string };
export type SentenceModel = { parts: (string | Token)[] };

export type Options = { minutes: number[]; goals: string[]; presets: string[] };
export type Chosen = { minutes?: number; goal?: string; preset?: string };
export type JobArgs = { kind: "brief"; goal: string; minutes: number; preset: string; today: string };

const DEFAULTS = { minutes: 20, goal: "strength", preset: "bodyweight" };

const GOAL_WORDS: Record<string, string> = { general: "general fitness" };
const PRESET_WORDS: Record<string, string> = {
  "full-gym": "a full gym",
  "hotel-gym": "a hotel gym",
  "hotel-room": "hotel-room kit",
};

/** What a setting is called, for an accessible name ("Length: 20 minutes"). */
export const TOKEN_NAMES: Record<string, string> = { minutes: "Length", goal: "Goal", preset: "Kit" };

function pick<T>(wanted: T | undefined, fallback: T, have: T[]): T {
  if (wanted !== undefined && have.includes(wanted)) return wanted;
  if (have.includes(fallback)) return fallback;
  return have[0] ?? fallback;
}

export function buildWorkoutSentence(opts: Options, chosen: Chosen): SentenceModel {
  const minutes: Token = {
    key: "minutes",
    value: pick(chosen.minutes, DEFAULTS.minutes, opts.minutes),
    options: opts.minutes.map((m) => ({ value: m, label: `${m} minutes` })),
    why: "How long you have",
  };
  const goal: Token = {
    key: "goal",
    value: pick(chosen.goal, DEFAULTS.goal, opts.goals),
    options: opts.goals.map((g) => ({ value: g, label: GOAL_WORDS[g] ?? g.replace(/-/g, " ") })),
    why: "What today is for",
  };
  const preset: Token = {
    key: "preset",
    value: pick(chosen.preset, DEFAULTS.preset, opts.presets),
    options: opts.presets.map((p) => ({ value: p, label: PRESET_WORDS[p] ?? p.replace(/-/g, " ") })),
    why: "What you have to train with",
  };
  return { parts: ["A ", minutes, "-minute ", goal, " workout with ", preset, "."] };
}

/** A new model with one token's value changed; the rest are the same objects. */
export function setToken(m: SentenceModel, key: string, value: string | number): SentenceModel {
  return {
    parts: m.parts.map((p) => (typeof p !== "string" && p.key === key ? { ...p, value } : p)),
  };
}

export function tokens(m: SentenceModel): Token[] {
  return m.parts.filter((p): p is Token => typeof p !== "string");
}

function valueOf(m: SentenceModel, key: string): string | number {
  const t = tokens(m).find((p) => p.key === key);
  if (!t) throw new Error(`the sentence has no ${key}`);
  return t.value;
}

/** The words a token shows in the sentence: the bare number for minutes, else its label. */
export function shown(t: Token): string {
  if (t.key === "minutes") return String(t.value);
  return t.options.find((o) => o.value === t.value)?.label ?? String(t.value);
}

export function toJobArgs(m: SentenceModel, today: string): JobArgs {
  return {
    kind: "brief",
    goal: String(valueOf(m, "goal")),
    minutes: Number(valueOf(m, "minutes")),
    preset: String(valueOf(m, "preset")),
    today,
  };
}

/** The browser's local date as YYYY-MM-DD (never UTC's). */
export function localDate(d: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

/** The browser's local time as "YYYY-MM-DD Weekday HH:MM" (English weekday, ASCII). */
export function localNow(d: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${localDate(d)} ${DAYS[d.getDay()]} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** The sentence as one plain line, such as "A 20-minute strength workout with bodyweight". */
export function sentenceText(m: SentenceModel): string {
  return m.parts.map((p) => (typeof p === "string" ? p : shown(p))).join("").replace(/\.$/, "");
}
