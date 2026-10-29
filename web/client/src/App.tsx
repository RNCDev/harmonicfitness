// The app: the sign-in page, or once signed in a top bar, the chat, and a drawer for keys and settings.
import { useCallback, useEffect, useState } from "react";
import { api, APP_NAME, NotSignedIn, type KeyState, type Me } from "./api";
import { ChoosePassword, SignIn } from "./SignIn";
import { useConversation } from "./conversation";
import { Chat, type KeyNeeded } from "./zones/Chat";
import { ContextColumn } from "./zones/ContextColumn";
import { hasModelKey, keyRows } from "./zones/KeysBox";

/** The key a listener with no language-model key adds first: the first one offered. */
function keyNeeded(keys: KeyState[] | null): KeyNeeded | null {
  if (hasModelKey(keys) !== false) return null;
  const first = keyRows(keys ?? []).find((r) => r.kind === "model");
  return first ? { name: first.name, service: first.service, voice: first.voice } : null;
}

type Auth = "loading" | "in" | "out" | "error";

function Unreachable({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="solo">
      <div className="mark">{APP_NAME}</div>
      <h1>Couldn't reach the server</h1>
      <button type="button" className="go" onClick={onRetry}>Try again</button>
    </main>
  );
}

/** While the page asks who is signed in: nothing else asks the server until it knows. */
function Loading() {
  return (
    <div className="app" aria-busy="true">
      <header className="top"><div className="mark">{APP_NAME}</div></header>
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
  const steps = (job?.stages ?? []).filter((s) => s.stage === "step" && typeof s.text === "string")
    .map((s) => ({ text: s.text as string, failed: s.failed === true }));

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
        <div className="mark">{APP_NAME}{me.version && <span className="ver">{me.version}</span>}</div>
        <button type="button" className="top-btn" onClick={reset} disabled={working || !conv}>New chat</button>
        <button type="button" className="top-btn ctx-toggle" aria-expanded={drawer} aria-controls="ctx"
          onClick={() => setDrawer((d) => !d)}>
          Keys
        </button>
      </header>
      {/* an earlier day's conversation shows as history; the next message starts a new one */}
      <Chat lines={conv?.lines ?? []} working={working} steps={steps} error={error} noKey={noKey}
        offer={!working ? conv?.offer ?? null : null} onRecord={record} onStop={halt}
        onSend={send} onOpenKeys={() => setDrawer(true)} needsKey={needsKey}
        onAddKey={() => {
          if (needsKey) setOpenRow((r) => ({ service: needsKey.service, n: (r?.n ?? 0) + 1 }));
          setDrawer(true);
        }} />
      <ContextColumn username={me.username} open={drawer} onClose={closeDrawer}
        onSignedOut={onSignedOut} onSignOut={signOut} onKeys={setKeys} openRow={openRow} />
    </div>
  );
}
