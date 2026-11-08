// What the first screen's request is filled in with (GET /api/start), and choosing the coach in it.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, NotSignedIn, type KeyState, type StartInfo } from "./api";
import { localDate } from "./when";
import { optimistic } from "./useAction";

/** The request's defaults when the server can't say more. */
const NO_START: StartInfo = { coaches: [], kits: [], minutes: 25, limits: [], suggest: null, setup_quick: false };

/** Asked at once, beside the keys, and again whenever which keys are set changes. The keys list arriving isn't a
 * change: the server read the same keys for the first answer. Only the latest ask is used. If it can't be had, the
 * request still comes, with plain defaults. */
export function useStartInfo(keys: KeyState[] | null) {
  const [start, setStart] = useState<StartInfo | null>(null);
  const [coachError, setCoachError] = useState<string | null>(null);
  const keySig = keys === null ? null : keys.map((k) => `${k.service}:${k.kind}:${k.set}`).join(",");
  const asked = useRef<{ sig: string | null; n: number } | null>(null);
  useEffect(() => {
    const was = asked.current;
    if (was && was.sig === null && keySig !== null) {
      asked.current = { ...was, sig: keySig };
      return;
    }
    const n = (was?.n ?? 0) + 1;
    asked.current = { sig: keySig, n };
    api.start().then((s) => { if (asked.current?.n === n) setStart(s); }, (e) => {
      if (!(e instanceof NotSignedIn) && asked.current?.n === n) setStart((s) => s ?? NO_START);
    });
  }, [keySig]);

  // The coach, chosen on the Coaches page or in the request: switched at once in both, then saved (the server keeps
  // it as the first screen's coach, and tells the chat); put back, with the reason, if the server refuses it.
  const chooseCoach = useCallback(async (slug: string) => {
    const before = start?.coaches.find((c) => c.current)?.slug;
    if (slug === before || !start?.coaches.some((c) => c.slug === slug && c.ready)) return;
    const mark = (current: string | undefined) => setStart((s) => s && {
      ...s, coaches: s.coaches.map((c) => ({ ...c, current: c.slug === current })) });
    setCoachError(await optimistic(before, slug, mark, () => api.setCoach(slug, localDate(new Date())),
      "That coach couldn't be chosen just now. Try again."));
  }, [start]);

  const coaches = start?.coaches ?? [];
  const shown = coaches.find((c) => c.current) ?? null;
  const coachBar = shown ? { n: coaches.indexOf(shown) + 1, name: shown.name, service: shown.service_name } : null;
  return { start, coaches, coachBar, chooseCoach, coachError };
}
