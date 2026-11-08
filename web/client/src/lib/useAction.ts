// A button's call to the server: busy while it runs, its error in words, and nothing to do for a lost session
// (api.ts sends the page to sign-in itself).
import { useCallback, useRef, useState } from "react";
import { ApiError, NotSignedIn, plainError } from "./api";

/** Thrown by an action's work to end it without an error: the caller already said what happened. */
export class Quiet extends Error {}

/** `run` calls `work`, resolving true when it went through. `hold` keeps the button busy after success, for an
 * action whose screen goes away on its own (a recording starting). `field` is the form box a refusal is about,
 * when the server named one: the form says the error under that box instead of above the button. */
export function useAction<A extends unknown[]>(work: (...a: A) => Promise<unknown>,
  { fallback = "Couldn't reach the server.", hold = false }: { fallback?: string; hold?: boolean } = {}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [field, setField] = useState<string | null>(null);
  const latest = useRef(work);
  latest.current = work;
  const run = useCallback(async (...a: A): Promise<boolean> => {
    setBusy(true);
    setError(null);
    setField(null);
    try {
      await latest.current(...a);
      if (!hold) setBusy(false);
      return true;
    } catch (e) {
      setBusy(false);
      if (!(e instanceof NotSignedIn) && !(e instanceof Quiet)) {
        setError(plainError(e, fallback));
        setField(e instanceof ApiError ? e.field ?? null : null);
      }
      return false;
    }
  }, [fallback, hold]);
  const clear = useCallback(() => { setError(null); setField(null); }, []);
  /** The error for one box (`name`), or, with no name, the error no box claims. */
  const errorFor = (name?: string) => (name ? (field === name ? error : null) : field ? null : error);
  return { run, busy, error, field, errorFor, clear };
}

/** Change a value at once, save it, and put it back if the server refuses: the error, or null once saved. */
export async function optimistic<T>(before: T, next: T, show: (v: T) => void, save: () => Promise<unknown>,
  failed = "That didn't save. Try again."): Promise<string | null> {
  show(next);
  try {
    await save();
    return null;
  } catch (e) {
    show(before);
    return e instanceof NotSignedIn ? null : plainError(e, failed);
  }
}

/** A setting that switches at once and saves behind: its value, the setter, and why the last change didn't hold. */
export function useSaved<T>(initial: T, save: (v: T) => Promise<unknown>, failed?: string) {
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const now = useRef(value);
  now.current = value;
  const set = useCallback(async (next: T) => {
    setError(null);
    setError(await optimistic(now.current, next, setValue, () => save(next), failed));
  }, [save, failed]);
  return [value, set, error] as const;
}
