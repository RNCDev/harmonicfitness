// Set or change the password: on the page that asks for one, and in Settings. The rule (at least eight
// characters) is checked as you type once you've tried, and said under the box it's about.
import { useState } from "react";
import { api } from "../lib/api";
import { Quiet, useAction } from "../lib/useAction";
import { useChecked } from "../lib/useChecked";
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
  const form = useChecked();
  const short = form.check(tooShort, next);
  const save = useAction(async () => {
    if (tooShort(next)) throw new Quiet();
    await api.setPassword(needsCurrent ? current : null, next);
    setCurrent("");
    setNext("");
    form.reset();
    onDone();
  });


  return (
    <form className="auth" onSubmit={(e) => form.submit(e, () => void save.run())} noValidate>
      {/* lets a password manager save the pair */}
      <input type="text" name="username" autoComplete="username" hidden readOnly value={username} />
      {needsCurrent && (
        <Field id="pw-current" label="Current password" error={save.errorFor("current")}>
          <input className="input" type="password" autoComplete="current-password" required value={current}
            onChange={(e) => setCurrent(e.target.value)} />
        </Field>
      )}
      <Field id="pw-new" label="New password" hint={`At least ${MIN_PASSWORD} characters. Other devices are signed out.`}
        error={short ?? save.errorFor("new")}>
        <input className="input" type="password" autoComplete="new-password" required value={next}
          onChange={(e) => setNext(e.target.value)} />
      </Field>
      <Notice tone="error">{save.errorFor()}</Notice>
      <Button type="submit" variant="outline" busy={save.busy} busyLabel="Saving…">
        {needsCurrent ? "Change password" : "Save password"}
      </Button>
    </form>
  );
}
