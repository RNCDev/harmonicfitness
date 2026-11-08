// How the app writes numbers, lists, prices, dates and times: one copy of each, shared by every page. Nothing
// outside this file calls toLocale…() (layers.test.ts).

/** Seconds as "m:ss" ("0:00" for anything not a finite number). */
export function mss(s: number): string {
  return Number.isFinite(s) ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}` : "0:00";
}

/** "m:ss" as seconds. */
export function seconds(at: string): number {
  const [m, s] = at.split(":").map(Number);
  return m * 60 + s;
}

/** "a", "a and b", "a, b and c". */
export function listAnd(xs: string[]): string {
  return xs.length < 3 ? xs.join(" and ") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;
}

/** "a" or "an" before a number of minutes: an 8-minute, an 11-minute, an 18-minute. */
export function article(minutes: number): string {
  const s = String(minutes);
  return s.startsWith("8") || s === "11" || s === "18" ? "an" : "a";
}

/** "a" or "an" before a word. */
export const an = (word: string) => (/^[aeiou]/i.test(word) ? "an" : "a");

/** A price the listener will pay, as every page shows one: rounded up to the cent, never down, so a quote is
 * never under the charge; or "under 1¢". The Coaches page's estimate and the Record button's quote agree. */
export function dollars(usd: number): string {
  return usd < 0.01 ? "under 1¢" : `$${(Math.ceil(usd * 100 - 1e-9) / 100).toFixed(2)}`;
}

/** Money already on an account (a balance): to the cent, in the browser's way of grouping digits. */
export function balance(usd: number): string {
  return `$${usd.toLocaleString([], { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** A count, in the browser's way of grouping digits: "12,400". */
export const count = (n: number) => n.toLocaleString();

const valid = (iso: string | null | undefined): Date | null => {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
};

/** "Fri 7:00 PM": until when a recording is kept. Empty when the time can't be read. */
export function keptUntil(iso: string): string {
  const d = valid(iso);
  return d ? d.toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" }) : "";
}

/** "7:00 AM" in the browser's own way of writing a time. */
export function timeOfDay(d: Date): string {
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

/** "7:00 PM" from a time the server sent. Empty when it can't be read. */
export function clockAt(iso: string | null | undefined): string {
  const d = valid(iso);
  return d ? timeOfDay(d) : "";
}

/** "Fri 30 Oct 2026" from "2026-10-30", read as the listener's own date. */
export function longDate(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  if (!y || !m || !d) return day;
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short",
    year: "numeric" });
}

/** "Thursday night": the day and its part, for the line above the request. In English on purpose: the words
 * around it ("night", the request itself) are English, so the weekday is too. */
export function dayPart(d: Date): string {
  const h = d.getHours();
  const part = h < 5 ? "night" : h < 12 ? "morning" : h < 17 ? "afternoon" : h < 21 ? "evening" : "night";
  return `${d.toLocaleDateString("en-US", { weekday: "long" })} ${part}`;
}

/** "Nov 7": the day a thing happened (an ISO time, or a Date). Empty when it can't be read. */
export function shortDay(when: string | Date | null | undefined): string {
  const d = when instanceof Date ? (Number.isNaN(when.getTime()) ? null : when) : valid(when);
  return d ? d.toLocaleDateString([], { month: "short", day: "numeric" }) : "";
}
