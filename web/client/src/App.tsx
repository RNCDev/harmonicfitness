// The app: the sign-in page, or once signed in a top bar, the chat, and the Settings drawer.
import { useCallback, useEffect, useState } from "react";
import { api, APP_NAME, NotSignedIn, type KeyState, type Me, type StartInfo } from "./api";
import { ChoosePassword, SignIn } from "./SignIn";
import { Mark } from "./Mark";
import { useConversation } from "./conversation";
import { Chat, stepsOf, type KeyNeeded } from "./zones/Chat";
import { ContextColumn } from "./zones/ContextColumn";
import { hasModelKey, keyRows } from "./zones/KeysBox";

/** The key a listener with no language-model key adds first: the first one offered. */
function keyNeeded(keys: KeyState[] | null): KeyNeeded | null {
  if (hasModelKey(keys) !== false) return null;
  const first = keyRows(keys ?? []).find((r) => r.kind === "model");
  return first ? { name: first.name, service: first.service, voice: first.voice } : null;
}

type Auth = "loading" | "in" | "out" | "error";

/** The sentence's defaults when the server can't say more. */
const NO_START: StartInfo = { coaches: [], kits: [], minutes: 25, limits: [], suggest: null, setup_quick: false };

const Gear = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
);

function Unreachable({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="solo">
      <Mark />
      <h1>Couldn't reach the server</h1>
      <button type="button" className="go" onClick={onRetry}>Try again</button>
    </main>
  );
}

/** While the page asks who is signed in: nothing else asks the server until it knows. */
function Loading() {
  return (
    <div className="app" aria-busy="true">
      <header className="top"><Mark /></header>
    </div>
  );
}

export function App() {
  const [auth, setAuth] = useState<Auth>("loading");
  const [me, setMe] = useState<Me | null>(null);

  const signedOut = useCallback(() => setAuth("out"), []);

  const load = useCallback(async () => {
    setAuth("loading");
    try {
      setMe(await api.me());
      setAuth("in");
    } catch (e) {
      setAuth(e instanceof NotSignedIn ? "out" : "error");
    }
  }, []);

  useEffect(() => {
    document.title = APP_NAME;
    void load();
  }, [load]);

  if (auth === "loading") return <Loading />;
  if (auth === "out") return <SignIn onSignedIn={load} />;
  if (auth === "error" || !me) return <Unreachable onRetry={load} />;
  if (!me.has_password) {
    return <ChoosePassword username={me.username} onSignedOut={signedOut}
      onDone={() => setMe({ ...me, has_password: true })} />;
  }
  return <SignedIn me={me} onSignedOut={signedOut} />;
}

/** The signed-in page. Mounted only once the server says who is signed in; unmounting it closes the job's stream. */
function SignedIn({ me, onSignedOut }: { me: Me; onSignedOut: () => void }) {
  const [drawer, setDrawer] = useState(false);
  const [keys, setKeys] = useState<KeyState[] | null>(null);
  const [openRow, setOpenRow] = useState<{ service: string; n: number } | null>(null);
  const needsKey = keyNeeded(keys);
  const { conv, working, error, noKey, send, record, halt, reset, job } = useConversation(onSignedOut);
  const steps = stepsOf(job?.stages ?? []);

  // What the first screen's sentence is filled in with: asked at once, beside the keys, and again whenever
  // which keys are set changes. If it can't be had, the sentence still comes, with plain defaults.
  const [start, setStart] = useState<StartInfo | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const keySig = (keys ?? []).map((k) => `${k.service}:${k.kind}:${k.set}`).join(",");
  useEffect(() => {
    let live = true;
    api.start().then((s) => { if (live) setStart(s); }, (e) => {
      if (e instanceof NotSignedIn) return onSignedOut();
      if (live) setStart((s) => s ?? NO_START);
    });
    return () => { live = false; };
  }, [keySig, onSignedOut]);
  const coaches = start?.coaches ?? [];
  const shown = coaches.find((c) => c.slug === picked) ?? coaches.find((c) => c.current) ?? null;
  const coachBar = shown ? { n: coaches.indexOf(shown) + 1, name: shown.name, service: shown.service_name } : null;

  // The drawer: Escape closes it and focus goes back to its button.
  const closeDrawer = useCallback(() => {
    setDrawer(false);
    document.querySelector<HTMLElement>(".ctx-toggle")?.focus();
  }, []);
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeDrawer();
    };
    document.addEventListener("keydown", onKey);
    // focus moves into the drawer, unless a key's box there already has it ("Add your key")
    const ctx = document.getElementById("ctx");
    if (!ctx?.contains(document.activeElement)) ctx?.querySelector<HTMLElement>("button")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [drawer, closeDrawer]);

  const signOut = useCallback(async () => {
    try {
      await api.signOut();
    } catch {
      /* signed out either way, as far as this page goes */
    }
    onSignedOut();
  }, [onSignedOut]);

  return (
    <div className="app">
      <header className="top">
        <Mark version={me.version} />
        {conv && <button type="button" className="top-btn new" onClick={() => { reset(); setPicked(null); }} disabled={working}>
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
            <path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          New chat
        </button>}
        <button type="button" className="top-btn icon ctx-toggle" aria-label="Settings" title="Settings"
          aria-expanded={drawer} aria-controls="ctx" onClick={() => setDrawer((d) => !d)}>
          <Gear />
        </button>
      </header>
      {/* an earlier day's conversation shows as history; the next message starts a new one */}
      <Chat lines={conv?.lines ?? []} working={working} steps={steps} error={error} noKey={noKey}
        offer={!working ? conv?.offer ?? null : null} onRecord={record} onStop={halt}
        onSend={send} onOpenKeys={() => setDrawer(true)} needsKey={needsKey}
        start={start} onCoach={setPicked} coachBar={coachBar}
        onAddKey={() => {
          if (needsKey) setOpenRow((r) => ({ service: needsKey.service, n: (r?.n ?? 0) + 1 }));
          setDrawer(true);
        }} />
      <ContextColumn username={me.username} open={drawer} onClose={closeDrawer}
        onSignedOut={onSignedOut} onSignOut={signOut} onKeys={setKeys} openRow={openRow}
        coaches={coaches} />
    </div>
  );
}
