// The signed-in app: a top bar, the chat, and a drawer for keys and settings.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, APP_NAME, NotSignedIn, type Me } from "./api";
import { ChoosePassword, SignIn } from "./SignIn";
import { useConversation } from "./conversation";
import { Chat } from "./zones/Chat";
import { ContextColumn } from "./zones/ContextColumn";

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

export function App() {
  const [auth, setAuth] = useState<Auth>("loading");
  const [me, setMe] = useState<Me | null>(null);
  const [drawer, setDrawer] = useState(false);

  // useJob reports a 401 through a ref, so its stream can be closed by the same callback.
  const stopRef = useRef<() => void>(() => {});
  const signedOut = useCallback(() => {
    stopRef.current();
    setAuth("out");
  }, []);
  const { conv, working, error, noKey, send, reset, job, stop } = useConversation(signedOut);
  const steps = (job?.stages ?? []).filter((s) => s.stage === "step" && typeof s.text === "string")
    .map((s) => ({ text: s.text as string, failed: s.failed === true }));
  stopRef.current = stop;

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
    document.querySelector<HTMLElement>("#ctx button")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [drawer, closeDrawer]);

  const signOut = useCallback(async () => {
    try {
      await api.signOut();
    } catch {
      /* signed out either way, as far as this page goes */
    }
    signedOut();
  }, [signedOut]);

  if (auth === "out") return <SignIn onSignedIn={load} />;
  if (auth === "error") return <Unreachable onRetry={load} />;
  if (me && !me.has_password) {
    return <ChoosePassword username={me.username} onSignedOut={signedOut}
      onDone={() => setMe({ ...me, has_password: true })} />;
  }

  return (
    <div className="app">
      <header className="top">
        <div className="mark">{APP_NAME}{me?.version && <span className="ver">{me.version}</span>}</div>
        <button type="button" className="top-btn" onClick={reset} disabled={working || !conv}>New chat</button>
        <button type="button" className="top-btn ctx-toggle" aria-expanded={drawer} aria-controls="ctx"
          onClick={() => setDrawer((d) => !d)}>
          Keys
        </button>
      </header>
      {/* an earlier day's conversation shows as history; the next message starts a new one */}
      <Chat lines={conv?.lines ?? []} working={working} steps={steps} error={error} noKey={noKey}
        onSend={send} onOpenKeys={() => setDrawer(true)} />
      <ContextColumn username={me?.username ?? ""} open={drawer} onClose={closeDrawer}
        onSignedOut={signedOut} onSignOut={signOut} />
    </div>
  );
}
