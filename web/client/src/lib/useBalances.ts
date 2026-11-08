// What's left on each keyed account that can say: asked again whenever `asking` (which keys can report, and when
// each was set) changes. "checking" while the worker asks; null when nothing can be said, and the rows fall back to
// their billing links.
import { useEffect, useState } from "react";
import { checkBalances, type Balance } from "./api";

export type Balances = Record<string, Balance> | "checking" | null;

export function useBalances(asking: string): Balances {
  const [balances, setBalances] = useState<Balances>(null);
  useEffect(() => {
    if (!asking) { setBalances(null); return; }
    let live = true;
    setBalances("checking");
    checkBalances({ live: () => live }).then((b) => { if (live) setBalances(b); }, () => {
      if (live) setBalances(null);
    });
    return () => { live = false; };
  }, [asking]);
  return balances;
}
