// The browser's own date and time, as the server's turn expects them, and the arithmetic on them. How a time is
// written for a person is lib/format.ts's.
import { timeOfDay } from "./format";

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

/** A time with the browser's offset from UTC, as the server reads a workout for later: "2026-11-04T07:00:00-05:00". */
export function withOffset(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  return `${localDate(d)}T${p(d.getHours())}:${p(d.getMinutes())}:00${sign}${p(Math.floor(Math.abs(off) / 60))}:${p(Math.abs(off) % 60)}`;
}

/** "7:00 AM", "tomorrow at 6:30 AM", "Friday at 6:30 AM": a time ahead, from where `now` is. */
export function ahead(d: Date, now: Date = new Date()): string {
  const days = Math.round((new Date(localDate(d)).getTime() - new Date(localDate(now)).getTime()) / 86400000);
  return days <= 0 ? timeOfDay(d) : days === 1 ? `tomorrow at ${timeOfDay(d)}` : `${DAYS[d.getDay()]} at ${timeOfDay(d)}`;
}

/** The times a workout can be planned for: every half hour from at least half an hour ahead, for a day. */
export function slots(now: Date = new Date()): Date[] {
  const first = new Date(now.getTime() + 30 * 60000);
  first.setSeconds(0, 0);
  first.setMinutes(first.getMinutes() <= 30 ? (first.getMinutes() === 0 ? 0 : 30) : 60);
  const out: Date[] = [];
  for (let t = first.getTime(); t <= now.getTime() + 24 * 3600000; t += 30 * 60000) out.push(new Date(t));
  return out;
}
