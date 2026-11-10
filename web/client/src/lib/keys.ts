// The keys, as the pages use them: a service's rows merged into one, whether a writer is set, and the order
// a new listener meets them in.
import type { Balance, KeyState } from "./api";
import { balance, count, shortDay } from "./format";

/** One row: a service's key, and whether it writes the workouts (model), voices a coach (voice), or both. */
export type KeyRowState = KeyState & { voice: boolean };

/** The listing as rows: one per service, a model row first; a service listed as both is one row. */
export function keyRows(keys: KeyState[]): KeyRowState[] {
  const rows: KeyRowState[] = [];
  for (const k of keys) {
    const same = rows.find((r) => r.service === k.service);
    if (!same) {
      rows.push({ ...k, voice: k.kind === "voice" });
      continue;
    }
    if (k.kind === "model") { same.kind = "model"; same.writer = k.writer; }
    if (k.kind === "voice") same.voice = true;
    same.set = same.set || k.set;
    same.reports = same.reports || k.reports;
    same.billing_page = same.billing_page ?? k.billing_page;
    same.updated_at = same.updated_at ?? k.updated_at;
  }
  return rows;
}

/** Whether a language-model key is set; null until the listing is in. */
export function hasModelKey(keys: KeyState[] | null): boolean | null {
  return keys === null ? null : keys.some((k) => k.kind === "model" && k.set);
}

/** The writers that also voice coaches, in the order they're offered: first, ahead of the rest. */
export const FIRST = ["openrouter", "gemini"];

/** Where a service sorts: the writers that voice first, then any other voice, then writers alone. */
export function writerRank(service: string, voice: boolean): number {
  const i = FIRST.indexOf(service);
  return i >= 0 ? i : voice ? FIRST.length : FIRST.length + 1;
}

/** The services' names as people say them, for a reply that names only the id (a Record offer). */
const SERVICE_NAMES: Record<string, string> = {
  fish: "Fish Audio", elevenlabs: "ElevenLabs", gemini: "Gemini", inworld: "Inworld", openrouter: "OpenRouter",
};
export const serviceName = (service: string) => SERVICE_NAMES[service] ?? service;

/** Said once, before the first recording (on its Record card, or on the first screen's form for a new listener): where the script goes, and what that means. */
export function privacyNote(service: string): string {
  const name = serviceName(service);
  return `Recording sends the script to ${name}, and it can mention your injuries ("easy on that left knee").`
    + (service === "gemini"
      ? " On Gemini's free tier, Google may use what it's sent to improve its models, with human review; a paid key doesn't."
      : "")
    + " Your key is stored encrypted on this site, never shown again, and removed in Settings.";
}

/** What's left on a key's account, in a few words: dollars of credit, or this period's credits. Null when there's
 * nothing to show. */
export function balanceText(b: Balance): { text: string; title: string } | null {
  if (!b.ok) return null;
  if (typeof b.usd === "number") {
    return { text: `${balance(b.usd)} left`,
      title: "API credit left" };
  }
  if (typeof b.used === "number" && typeof b.limit === "number") {
    const left = Math.max(0, b.limit - b.used);
    const resets = typeof b.resets === "number"
      ? `, resets ${shortDay(new Date(b.resets * 1000))}` : "";
    return { text: `${count(left)} credits left`,
      title: `${count(b.used)} of ${count(b.limit)} credits used this period${resets}` };
  }
  return null;
}
