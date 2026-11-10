// The Logs page's order and filters: which workouts the controls leave, and in what order. Pure, so the page draws
// and this decides.
import type { Rating, Workout } from "./api";

export type Sort = "newest" | "oldest" | "longest" | "shortest" | "best" | "worst";
export type RatingFilter = "all" | Rating | "unrated";

const SCORE: Record<string, number> = { positive: 2, neutral: 1, negative: 0 };

/** The workouts the controls leave, in their order. */
export function arrange(list: Workout[], q: string, rating: RatingFilter, format: string, kit: string,
                        sort: Sort): Workout[] {
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  const kept = list.filter((w) => {
    if (rating === "unrated" ? w.rating !== null : rating !== "all" && w.rating !== rating) return false;
    if (format !== "all" && (w.format ?? "") !== format) return false;
    if (kit !== "all" && w.kit !== kit) return false;
    const hay = [w.date, w.kit, w.coach, w.format ?? "", w.topics, ...w.movements, ...w.feedback].join(" ").toLowerCase();
    return words.every((word) => hay.includes(word));
  });
  const score = (w: Workout) => (w.rating === null ? -1 : SCORE[w.rating]);
  // newest by the date, then by the log's order (n: 1 is the last one logged)
  const newer = (a: Workout, b: Workout) => b.date.localeCompare(a.date) || a.n - b.n;
  const by: Record<Sort, (a: Workout, b: Workout) => number> = {
    newest: newer,
    oldest: (a, b) => newer(b, a),
    longest: (a, b) => b.minutes - a.minutes || newer(a, b),
    shortest: (a, b) => a.minutes - b.minutes || newer(a, b),
    best: (a, b) => score(b) - score(a) || newer(a, b),
    worst: (a, b) => (score(a) === -1 ? 9 : score(a)) - (score(b) === -1 ? 9 : score(b)) || newer(a, b),
  };
  return [...kept].sort(by[sort]);
}
