// Signed out: the front page (a demo to hear and the free workouts, with Sign in and Make an account in the header),
// then the form to sign in, or make an account when registration is open. Where sign-in goes through Clerk
// (GET /api/auth says so) the form is Clerk's, and whoever it signs in gets this site's session in trade
// (lib/useClerkSession.ts); elsewhere it's the site's own username and password. Someone who has signed in on
// this browser before starts at the form. Also the screen that asks for a password when an account has none (one
// from before passwords, or after a reset link).
import { useState } from "react";
import { ClerkFailed, ClerkLoading, SignIn as ClerkSignIn } from "@clerk/clerk-react";
import { Demos } from "./Demos";
import { ReadyWorkouts } from "./Ready";
import { api } from "../lib/api";
import { Quiet, useAction } from "../lib/useAction";
import { useChecked } from "../lib/useChecked";
import { useClerkSession } from "../lib/useClerkSession";
import { useResource } from "../lib/useResource";
import { remember, returning } from "../lib/visits";
import { Button } from "../ui/Button";
import { ClerkGate } from "../ui/ClerkGate";
import { Field } from "../ui/Field";
import { Notice } from "../ui/Notice";
import { MIN_PASSWORD, PasswordForm, tooShort } from "../ui/PasswordForm";
import { Solo } from "../ui/Solo";

/** The server's rule for a new username (web/webapp/auth.py USERNAME), checked here too, as you type once you've
 * tried, so it's said under the box before anything is sent. */
const USERNAME = /^[a-z0-9][a-z0-9_.-]{2,31}$/;
const badName = (name: string) => (USERNAME.test(name.trim().toLowerCase()) ? null
  : "Use 3 to 32 letters, numbers, dots, dashes or underscores, starting with a letter or number.");

/** Clerk's form keeps its place in the address ("#/factor-one", "#/sso-callback" on the way back from Google): a
 * page that opens on one of those is in the middle of signing in, so it opens on the form. */
const midway = () => window.location.hash.startsWith("#/");

type Mode = "in" | "new";

/** The front page: the demos and the free workouts, with the ways in at the header's right. */
function Front({ version, open, onForm }: { version: string; open: boolean; onForm: (m: Mode) => void }) {
  return (
    <Solo version={version} actions={<>
      <Button variant="header" onClick={() => onForm("in")}>Sign in</Button>
      {open && <Button variant="primary" className="solo-join" onClick={() => onForm("new")}>Make an account</Button>}
    </>} landing={<><Demos /><ReadyWorkouts panel /></>} />
  );
}

export function SignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const [front, setFront] = useState(() => !returning() && !midway());
  const [mode, setMode] = useState<Mode>("in");
  // whether accounts can be made here, how to sign in, and the version: until the server says, or if it can't,
  // the site's own sign-in only
  const info = useResource(api.authInfo, "");
  const open = info.data?.registration ?? false;
  const version = info.data?.version ?? "";
  const clerk = info.data?.clerk ?? null;
  const toForm = (m: Mode) => { setMode(m); setFront(false); };

  if (clerk) {
    return (
      <ClerkGate publishableKey={clerk}>
        <ViaClerk version={version} open={open} front={front} onFront={() => setFront(true)} onForm={toForm}
          onSignedIn={onSignedIn} />
      </ClerkGate>
    );
  }
  if (front) return <Front version={version} open={open} onForm={toForm} />;
  // which form it is isn't known until the server answers: a moment's wait, never one form and then the other
  if (!info.data && !info.error) return <Solo><Notice tone="busy">Loading…</Notice></Solo>;
  return <ViaPassword version={version} open={open} mode={mode} onMode={toForm} onFront={() => setFront(true)}
    onSignedIn={onSignedIn} />;
}

/** Sign-in through Clerk: its form, and the trade of whoever it signs in for a session here. Signing in and making
 * an account are one form (Clerk asks an address it doesn't know whether to make one), unless new accounts are
 * closed. */
function ViaClerk({ version, open, front, onFront, onForm, onSignedIn }: {
  version: string; open: boolean; front: boolean; onFront: () => void; onForm: (m: Mode) => void;
  onSignedIn: () => void;
}) {
  const session = useClerkSession(onSignedIn);
  if (session.state === "trading") return <Solo version={version}><Notice tone="busy">Signing you in…</Notice></Solo>;
  if (session.state === "refused") {
    return (
      <Solo version={version}>
        <h1>Sign in</h1>
        <Notice tone="error">{session.error}</Notice>
        <div className="act-row auth-again">
          <Button variant="primary" onClick={session.retry}>Try again</Button>
          <Button variant="outline" onClick={session.other}>Use another account</Button>
        </div>
      </Solo>
    );
  }
  if (front) return <Front version={version} open={open} onForm={onForm} />;
  return (
    <Solo version={version}>
      <div className="auth-clerk">
        <ClerkLoading><Notice tone="busy">Loading sign-in…</Notice></ClerkLoading>
        <ClerkFailed>
          <Notice tone="error">Sign-in didn't load. Check your connection, then reload the page.</Notice>
        </ClerkFailed>
        <ClerkSignIn routing="hash" withSignUp={open}
          appearance={open ? undefined : { elements: { footerAction: { display: "none" } } }} />
      </div>
      <p><Button variant="text" onClick={onFront}>Hear a demo, or play a free workout</Button></p>
    </Solo>
  );
}

/** The site's own sign-in: a username and a password. */
function ViaPassword({ version, open, mode, onMode, onFront, onSignedIn }: {
  version: string; open: boolean; mode: Mode; onMode: (m: Mode) => void; onFront: () => void;
  onSignedIn: () => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const form = useChecked();

  const fresh = mode === "new";
  const short = fresh ? form.check(tooShort, password) : null;
  const nameWrong = fresh ? form.check(badName, username) : null;
  const go = useAction(async () => {
    if (fresh && (tooShort(password) || badName(username))) throw new Quiet();
    await (fresh ? api.register : api.signIn)(username, password);
    remember();
    onSignedIn();
  });

  const switchTo = (m: Mode) => {
    onMode(m);
    form.reset();
    go.clear();
  };

  return (
    <Solo version={version}>
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
      <p><Button variant="text" onClick={onFront}>Hear a demo, or play a free workout</Button></p>
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
