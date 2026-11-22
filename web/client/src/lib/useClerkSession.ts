// Where sign-in goes through Clerk: once Clerk says someone is signed in on this browser, trade its session token
// for this site's session (POST /api/session), once per Clerk session. A refusal is said in the server's words,
// with a way to try again or to use another account. Someone who just signed out here is signed out of Clerk
// instead (lib/visits.ts). Used inside ui/ClerkGate.tsx's provider.
import { useEffect, useReducer, useRef, useState } from "react";
import { useAuth } from "@clerk/react";
import { api, ApiError, NotSignedIn } from "./api";
import { leaving, left, remember } from "./visits";
import { SAID } from "./messages";

const REFUSED = "That sign-in didn't work. Try again.";

/** `loading`: Clerk hasn't said yet; `out`: no one is signed in to Clerk (its form shows); `trading`: the session
 * is being made here; `refused`: it couldn't be, and `error` says why. */
type State = "loading" | "out" | "trading" | "refused";

export function useClerkSession(onSignedIn: () => void): {
  state: State; error: string | null; retry: () => void; other: () => void;
} {
  const { isLoaded, isSignedIn, sessionId, getToken, signOut } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [ending, setEnding] = useState(false);
  const [n, retry] = useReducer((x: number) => x + 1, 0);
  const tried = useRef("");
  const done = useRef(onSignedIn);
  done.current = onSignedIn;

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      if (leaving()) left();   // nothing of Clerk's to end
      return;
    }
    const attempt = `${sessionId}:${n}`;
    if (tried.current === attempt) return;   // one trade per session and per "Try again"
    tried.current = attempt;
    if (leaving()) {
      const over = () => { left(); setEnding(false); };
      setEnding(true);
      void signOut().then(over, over);
      return;
    }
    setError(null);
    void (async () => {
      try {
        const token = await getToken({ skipCache: true });
        if (!token) throw new ApiError(401, REFUSED);
        await api.session(token);
        remember();
        done.current();
      } catch (e) {
        setError(e instanceof NotSignedIn ? REFUSED : e instanceof ApiError ? e.message || REFUSED : SAID.unreachable);
      }
    })();
  }, [isLoaded, isSignedIn, sessionId, n]); // eslint-disable-line react-hooks/exhaustive-deps

  const state: State = !isLoaded || ending ? "loading" : !isSignedIn ? "out" : error ? "refused" : "trading";
  return { state, error, retry, other: () => { setError(null); void signOut(); } };
}

/** A fresh Clerk session token, to prove who is asking before something that can't be undone (deleting the
 * account); null when Clerk has no session on this browser. */
export function useFreshToken(): { ready: boolean; get: () => Promise<string | null> } {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  return { ready: isLoaded, get: async () => (isSignedIn ? getToken({ skipCache: true }) : null) };
}
