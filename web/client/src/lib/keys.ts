// The keys, as the pages use them: a service's rows merged into one, whether a writer is set, and the order
// a new listener meets them in.
import type { KeyState } from "./api";

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
