// Signed out: sign in, or make an account when registration is open. Also the screen that asks
// for a password when an account has none (one from before passwords, or after a reset link).
import { useEffect, useState, type FormEvent } from "react";
import { Solo } from "./Sky";
import { api, NotSignedIn, plainError } from "./api";

const MIN = 8;

export function SignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const [mode, setMode] = useState<"in" | "new">("in");
  const [open, setOpen] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState("");

  useEffect(() => {
    api.authInfo().then((a) => {
      setOpen(a.registration);
      setVersion(a.version ?? "");
    }, () => setOpen(false));
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (mode === "new" && password.length < MIN) {
      setError(`Use a password of at least ${MIN} characters.`);
      return;
    }
    setBusy(true);
    try {
      await (mode === "in" ? api.signIn : api.register)(username, password);
      onSignedIn();
    } catch (err) {
      setError(plainError(err));
    } finally {
      setBusy(false);
    }
  }

  const switchTo = (m: "in" | "new") => {
    setMode(m);
    setError(null);
  };

  return (
    <Solo version={version}>
      <h1>{mode === "in" ? "Sign in" : "Make an account"}</h1>
      <form className="auth" onSubmit={submit}>
        <label>
          Username
          <input name="username" autoComplete="username" autoCapitalize="none" spellCheck={false}
            required value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        {mode === "new" && (
          <p className="hint">3 to 32 characters: letters, numbers, dots, dashes or underscores.</p>
        )}
        <label>
          Password
          <input name="password" type="password" required
            autoComplete={mode === "in" ? "current-password" : "new-password"}
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {mode === "new" && <p className="hint">At least {MIN} characters.</p>}
        {error && <p className="err" role="alert">{error}</p>}
        <button type="submit" className="go" disabled={busy}>
          {mode === "in" ? "Sign in" : "Make my account"}
        </button>
      </form>
      {mode === "in" ? (
        <>
          {open && (
            <p>New here? <button type="button" className="quiet" onClick={() => switchTo("new")}>
              Make an account</button></p>
          )}
          <p className="hint">Forgot your password? Ask the person who runs this site to send you a reset link.</p>
        </>
      ) : (
        <p>Have an account? <button type="button" className="quiet" onClick={() => switchTo("in")}>
          Sign in</button></p>
      )}
    </Solo>
  );
}

/** Set or change the password. `needsCurrent` is false for an account that has none. */
export function PasswordForm({ username, needsCurrent, onDone, onSignedOut }: {
  username: string;
  needsCurrent: boolean;
  onDone: () => void;
  onSignedOut: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (next.length < MIN) {
      setError(`Use a password of at least ${MIN} characters.`);
      return;
    }
    setBusy(true);
    try {
      await api.setPassword(needsCurrent ? current : null, next);
      setCurrent("");
      setNext("");
      onDone();
    } catch (err) {
      if (err instanceof NotSignedIn) return onSignedOut();
      setError(plainError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth" onSubmit={submit}>
      {/* lets a password manager save the pair */}
      <input type="text" name="username" autoComplete="username" hidden readOnly value={username} />
      {needsCurrent && (
        <label>
          Current password
          <input type="password" autoComplete="current-password" required value={current}
            onChange={(e) => setCurrent(e.target.value)} />
        </label>
      )}
      <label>
        New password
        <input type="password" autoComplete="new-password" required value={next}
          onChange={(e) => setNext(e.target.value)} />
      </label>
      <p className="hint">At least {MIN} characters. Other devices are signed out.</p>
      {error && <p className="err" role="alert">{error}</p>}
      <button type="submit" className="go alt" disabled={busy}>
        {needsCurrent ? "Change password" : "Save password"}
      </button>
    </form>
  );
}

export function ChoosePassword({ username, onDone, onSignedOut }: {
  username: string;
  onDone: () => void;
  onSignedOut: () => void;
}) {
  return (
    <Solo>
      <h1>Choose a password</h1>
      <p>Your username is <strong>{username}</strong>. You'll sign in with it and this password.</p>
      <PasswordForm username={username} needsCurrent={false} onDone={onDone} onSignedOut={onSignedOut} />
    </Solo>
  );
}
