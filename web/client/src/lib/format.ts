// How the app writes numbers, lists, prices and times: one copy of each, shared by every page.

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

/** A price as the Record and Schedule buttons show one: rounded up to the cent, or "under 1¢". */
export function dollars(usd: number): string {
  return usd < 0.01 ? "under 1¢" : `$${(Math.ceil(usd * 100 - 1e-9) / 100).toFixed(2)}`;
}

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

/** "7:00 PM" from a time the server sent. Empty when it can't be read. */
export function clockAt(iso: string | null | undefined): string {
  const d = valid(iso);
  return d ? d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "";
}

/** "Nov 7": the day a thing happened. Empty when it can't be read. */
export function shortDay(iso: string | null | undefined): string {
  const d = valid(iso);
  return d ? d.toLocaleDateString([], { month: "short", day: "numeric" }) : "";
}
