// A form's rules, checked once the listener has tried to send it: nothing is said while they first type, then each
// rule's message sits under its box and updates as they type. Sending stops at a broken rule, so the server never
// hears a form the page already knows is wrong.
import { useCallback, useState, type FormEvent } from "react";

export function useChecked() {
  const [tried, setTried] = useState(false);
  /** The rule's message for `value`, once they've tried; null before, and while it holds. */
  const check = useCallback(<V,>(rule: (v: V) => string | null, value: V) => (tried ? rule(value) : null), [tried]);
  /** The form's submit: marks it tried, then runs `send` (which re-checks the rules itself and stops quietly). */
  const submit = useCallback((e: FormEvent, send: () => void) => {
    e.preventDefault();
    setTried(true);
    send();
  }, []);
  /** Back to untried: a form that went through, or switched what it's for. */
  const reset = useCallback(() => setTried(false), []);
  return { tried, check, submit, reset };
}
