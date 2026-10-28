// The signed-in app: the band, chat, the working panel and the context column.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, APP_NAME, NotSignedIn, type ContextFile, type Me } from "./api";
import { ChoosePassword, SignIn } from "./SignIn";
import { useConversation } from "./conversation";
import { buildWorkoutSentence, sentenceText, setToken, type SentenceModel } from "./sentence/model";
import { Band } from "./zones/Band";
import { Chat } from "./zones/Chat";
import { ContextColumn } from "./zones/ContextColumn";
import { Panel } from "./zones/Panel";

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
  const [model, setModel] = useState<SentenceModel | null>(null);
  const [files, setFiles] = useState<ContextFile[] | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [drawer, setDrawer] = useState(false);

  // useJob reports a 401 through a ref, so its stream can be closed by the same callback.
  const stopRef = useRef<() => void>(() => {});
  const signedOut = useCallback(() => {
    stopRef.current();
    setAuth("out");
  }, []);
  const { conv, history, working, error, noKey, start, send, answer, job, stop } = useConversation(signedOut);
  stopRef.current = stop;

  const load = useCallback(async () => {
    setAuth("loading");
    try {
      const [who, options, context] = await Promise.all([api.me(), api.options(), api.context()]);
      setMe(who);
      setModel((m) => m ?? buildWorkoutSentence(options, {}));
      setFiles(context);
      setAuth("in");
    } catch (e) {
      setAuth(e instanceof NotSignedIn ? "out" : "error");
    }
  }, []);

  useEffect(() => {
    document.title = APP_NAME;
    void load();
  }, [load]);

  // A finished job may have written files back: list them again.
  useEffect(() => {
    if (job?.state === "done") api.context().then(setFiles, () => {});
  }, [job?.state]);

  // The drawer: Escape closes it and focus goes back to its button.
  const closeDrawer = useCallback(() => {
    setDrawer(false);
    document.querySelector<HTMLElement>(".ctx-toggle")?.focus();
  }, []);
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !document.querySelector(".pop")) closeDrawer();
    };
    document.addEventListener("keydown", onKey);
    document.querySelector<HTMLElement>("#ctx button")?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [drawer, closeDrawer]);

  // Start always begins a new conversation; the chat's text box goes on with the open one.
  const go = useCallback(() => {
    if (model) void start(sentenceText(model));
  }, [model, start]);

  const openKeys = useCallback(() => {
    setDrawer(true);
    setTimeout(() => document.querySelector<HTMLElement>("#ctx .cx-s")?.scrollIntoView?.(), 0);
  }, []);

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

  const busy = working;
  return (
    <div className="app">
      <Band model={model} busy={busy}
        onChange={(k, v) => setModel((m) => (m ? setToken(m, k, v) : m))}
        onGo={go} filesOpen={drawer}
        onFiles={() => setDrawer((d) => !d)} />
      <Chat lines={conv?.lines ?? []} working={working} error={error} noKey={noKey}
        onSend={send} onOpenKeys={openKeys} />
      <main className="panel">
        {/* an earlier day's conversation is history: its lines stay in the chat, its plan and question go */}
        <Panel question={conv?.state === "waiting" && !history ? conv.question : null}
          plan={history ? null : conv?.plan ?? null}
          working={working} onAnswer={answer} />
      </main>
      <ContextColumn files={files} username={me?.username ?? ""} open={drawer} onClose={closeDrawer}
        onSignedOut={signedOut} onSignOut={signOut} />
    </div>
  );
}
