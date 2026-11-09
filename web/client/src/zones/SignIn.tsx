// Signed out: sign in, or make an account when registration is open. Also the screen that asks
// for a password when an account has none (one from before passwords, or after a reset link).
import { useEffect, useState } from "react";
import { Demos } from "./Demos";
import { ReadyWorkouts } from "./Ready";
import { api } from "../lib/api";
import { Quiet, useAction } from "../lib/useAction";
import { useChecked } from "../lib/useChecked";
import { Button } from "../ui/Button";
import { Field } from "../ui/Field";
import { Notice } from "../ui/Notice";
import { MIN_PASSWORD, PasswordForm, tooShort } from "../ui/PasswordForm";
import { Solo } from "../ui/Solo";

/** The server's rule for a new username (web/webapp/auth.py USERNAME), checked here too, as you type once you've
 * tried, so it's said under the box before anything is sent. */
const USERNAME = /^[a-z0-9][a-z0-9_.-]{2,31}$/;
export const badName = (name: string) => (USERNAME.test(name.trim().toLowerCase()) ? null
  : "Use 3 to 32 letters, numbers, dots, dashes or underscores, starting with a letter or number.");

export function SignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const [mode, setMode] = useState<"in" | "new">("in");
  const [open, setOpen] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const form = useChecked();
  const [version, setVersion] = useState("");

  useEffect(() => {
    api.authInfo().then((a) => {
      setOpen(a.registration);
      setVersion(a.version ?? "");
    }, () => setOpen(false));
  }, []);

  const fresh = mode === "new";
  const short = fresh ? form.check(tooShort, password) : null;
  const nameWrong = fresh ? form.check(badName, username) : null;
  const go = useAction(async () => {
    if (fresh && (tooShort(password) || badName(username))) throw new Quiet();
    await (fresh ? api.register : api.signIn)(username, password);
    onSignedIn();
  });

  const switchTo = (m: "in" | "new") => {
    setMode(m);
    form.reset();
    go.clear();
  };

  return (
    <Solo version={version} beside={<div className="solo-beside"><Demos />
      <ReadyWorkouts intro="Or press play on a full workout: no account needed" /></div>}>
      <h1>{fresh ? "Make an account" : "Sign in"}</h1>
      <form className="auth" onSubmit={(e) => form.submit(e, () => void go.run())} noValidate>
        <Field id="signin-username" label="Username" error={nameWrong ?? go.errorFor("username")}
          hint={fresh ? "3 to 32 characters: letters, numbers, dots, dashes or underscores." : null}>
          <input className="input" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false}
            required value={username} onChange={(e) => setUsername(e.target.value)} />
        </Field>
        <Field id="signin-password" label="Password" hint={fresh ? `At least ${MIN_PASSWORD} characters.` : null}
          error={short ?? go.errorFor("password")}>
          <input className="input" name="password" type="password" required
            autoComplete={fresh ? "new-password" : "current-password"}
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <Notice tone="error">{go.errorFor()}</Notice>
        <Button type="submit" variant="primary" busy={go.busy} busyLabel={fresh ? "Making it…" : "Signing in…"}>
          {fresh ? "Make my account" : "Sign in"}
        </Button>
      </form>
      {fresh ? (
        <p>Have an account? <Button variant="text" onClick={() => switchTo("in")}>
          Sign in</Button></p>
      ) : (
        <>
          {open && (
            <p>New here? <Button variant="text" onClick={() => switchTo("new")}>
              Make an account</Button></p>
          )}
          <p className="hint">Forgot your password? Ask the person who runs this site to send you a reset link.</p>
        </>
      )}
    </Solo>
  );
}

export function ChoosePassword({ username, onDone }: { username: string; onDone: () => void }) {
  return (
    <Solo>
      <h1>Choose a password</h1>
      <p>Your username is <strong>{username}</strong>. You'll sign in with it and this password.</p>
      <PasswordForm username={username} needsCurrent={false} onDone={onDone} />
    </Solo>
  );
}
