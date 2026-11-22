// The listener's minutes (GET /api/minutes): what's left, the packs and the history.
// Read once the page opens, again whenever a turn starts or ends (a recording holds minutes, then keeps or gives
// them back), and a few times after coming back from the checkout page, since the payment's word can arrive a
// moment after the listener does.
import { useCallback, useEffect, useRef } from "react";
import { api, type MinutesState } from "./api";
import { SAID } from "./messages";
import { useResource } from "./useResource";

/** How long after the checkout page the balance is read again, for a payment still on its way. */
const SETTLE_AFTER = [3000, 9000];

export type Minutes = {
  /** Null until it's in. */
  state: MinutesState | null;
  error: string | null;
  reload: () => void;
  /** Back from the checkout page: read again now, and twice more. */
  settle: () => void;
};

export function useMinutes(working: boolean): Minutes {
  const res = useResource<MinutesState>(() => api.minutes(), SAID.minutes, []);
  const { refresh } = res;
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }   // the first read is useResource's own
    void refresh();
  }, [working, refresh]);

  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => () => timers.current.forEach(clearTimeout), []);
  const settle = useCallback(() => {
    void refresh();
    timers.current.forEach(clearTimeout);
    timers.current = SETTLE_AFTER.map((ms) => setTimeout(() => void refresh(), ms));
  }, [refresh]);

  return { state: res.data, error: res.error, reload: res.reload, settle };
}

/** How the listener came back from the checkout page, said in the address ("?minutes=bought"); null any other
 * time. Reading it takes it out of the address, so a reload doesn't say it twice. */
export function checkoutReturn(): "bought" | "cancelled" | null {
  let said: string | null = null;
  try {
    const q = new URLSearchParams(window.location.search);
    said = q.get("minutes");
    if (said === null) return null;
    q.delete("minutes");
    const rest = q.toString();
    window.history.replaceState(null, "", window.location.pathname + (rest ? `?${rest}` : "") + window.location.hash);
  } catch {
    /* an address that can't be rewritten still says how it went */
  }
  return said === "bought" || said === "cancelled" ? said : null;
}
