// What the first screen's request is filled in with (GET /api/start), and choosing the coach in it.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, NotSignedIn, plainError, type StartInfo } from "./api";
import { SAID } from "./messages";
import { localDate } from "./when";
import { optimistic } from "./useAction";

/** The request's defaults when the server can't say more. */
const NO_START: StartInfo = { coaches: [], kits: [], minutes: 25, limits: [], suggest: null, setup_quick: false };

/** Asked at once, and again whenever `reload` is called; only the latest ask is used. If it can't be had, the
 * request still comes, with plain defaults, and `error` says why: a screen that lists coaches shows it with Try
 * again. */
export function useStartInfo() {
  const [start, setStart] = useState<StartInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [coachError, setCoachError] = useState<string | null>(null);
  const [again, setAgain] = useState(0);
  const asked = useRef(0);
  useEffect(() => {
    const n = ++asked.current;
    api.start().then((s) => { if (asked.current === n) { setStart(s); setError(null); } }, (e) => {
      if (e instanceof NotSignedIn || asked.current !== n) return;
      setStart((s) => s ?? NO_START);
      setError(plainError(e, SAID.coaches));
    });
  }, [again]);
  const reload = useCallback(() => setAgain((n) => n + 1), []);

  // The coach, chosen on the Coaches page or in the request: switched at once in both, then saved (the server keeps
  // it as the first screen's coach, and tells the chat); put back, with the reason, if the server refuses it.
  const chooseCoach = useCallback(async (slug: string) => {
    const before = start?.coaches.find((c) => c.current)?.slug;
    if (slug === before || !start?.coaches.some((c) => c.slug === slug && c.ready)) return;
    const mark = (current: string | undefined) => setStart((s) => s && {
      ...s, coaches: s.coaches.map((c) => ({ ...c, current: c.slug === current })) });
    setCoachError(await optimistic(before, slug, mark, () => api.setCoach(slug, localDate(new Date())),
      SAID.coach));
  }, [start]);

  const coaches = start?.coaches ?? [];
  const shown = coaches.find((c) => c.current) ?? null;
  const coachBar = shown ? { name: shown.name, service: shown.service_name } : null;
  return { start, error, reload, coaches, coachBar, chooseCoach, coachError };
}
