// The browser's own date and time, as the server's turn expects them.

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
