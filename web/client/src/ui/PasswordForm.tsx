// Set or change the password: on the page that asks for one, and in Settings. The rule (at least eight
// characters) is checked as you type once you've tried, and said under the box it's about.
import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Quiet, useAction } from "../lib/useAction";
import { Button } from "./Button";
import { Field } from "./Field";
import { Notice } from "./Notice";

export const MIN_PASSWORD = 8;
export const tooShort = (p: string) => (p.length < MIN_PASSWORD ? `Use a password of at least ${MIN_PASSWORD} characters.` : null);

/** `needsCurrent` is false for an account that has none. */
export function PasswordForm({ username, needsCurrent, onDone }: {
  username: string; needsCurrent: boolean; onDone: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [tried, setTried] = useState(false);
  const short = tried ? tooShort(next) : null;
  const save = useAction(async () => {
    if (tooShort(next)) throw new Quiet();
    await api.setPassword(needsCurrent ? current : null, next);
    setCurrent("");
    setNext("");
    setTried(false);
    onDone();
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setTried(true);
    void save.run();
  }

  return (
    <form className="auth" onSubmit={submit} noValidate>
      {/* lets a password manager save the pair */}
      <input type="text" name="username" autoComplete="username" hidden readOnly value={username} />
      {needsCurrent && (
        <Field id="pw-current" label="Current password">
          <input className="input" type="password" autoComplete="current-password" required value={current}
            onChange={(e) => setCurrent(e.target.value)} />
        </Field>
      )}
      <Field id="pw-new" label="New password" hint={`At least ${MIN_PASSWORD} characters. Other devices are signed out.`}
        error={short}>
        <input className="input" type="password" autoComplete="new-password" required value={next}
          onChange={(e) => setNext(e.target.value)} />
      </Field>
      <Notice tone="error">{save.error}</Notice>
      <Button type="submit" variant="outline" busy={save.busy} busyLabel="Saving…">
        {needsCurrent ? "Change password" : "Save password"}
      </Button>
    </form>
  );
}
