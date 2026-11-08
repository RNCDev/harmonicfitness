// What a screen loads from the server: asked once on mounting (and again when `deps` change or `reload` is
// called), the answer or the reason it failed, and nothing set once the screen has gone. A lost session says
// nothing here: api.ts has already sent the page to sign-in. Every screen that loads data uses this, with
// ui/Notice.tsx's Loadable to show it (layers.test.ts keeps the "still mounted?" flag in lib/).
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { NotSignedIn, plainError } from "./api";

export type Resource<T> = {
  /** The answer, null until it's in. */
  data: T | null;
  /** Why the last ask failed, in words for a person; null while it's fine. */
  error: string | null;
  /** Ask again (a Try again button). */
  reload: () => void;
  /** Change the answer here, as a save changes it on the server. */
  set: (update: (data: T | null) => T | null) => void;
};

export function useResource<T>(load: () => Promise<T>, fallback: string, deps: unknown[] = []): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [n, reload] = useReducer((x: number) => x + 1, 0);
  const latest = useRef(load);
  latest.current = load;

  useEffect(() => {
    let live = true;
    setError(null);
    latest.current().then((d) => { if (live) setData(d); }, (e) => {
      if (live && !(e instanceof NotSignedIn)) setError(plainError(e, fallback));
    });
    return () => { live = false; };
  }, [n, fallback, ...deps]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = useCallback((update: (data: T | null) => T | null) => setData(update), []);
  return { data, error, reload, set };
}
