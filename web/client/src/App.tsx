// The signed-in app: the band, chat, the working panel and the context column.
import { useCallback, useEffect, useState } from "react";
import { api, APP_NAME, NotSignedIn, useJob, type ContextFile } from "./api";
import { buildWorkoutSentence, localDate, setToken, toJobArgs, type SentenceModel } from "./sentence/model";
import { Band } from "./zones/Band";
import { Chat } from "./zones/Chat";
import { ContextColumn } from "./zones/ContextColumn";
import { Panel } from "./zones/Panel";

type Auth = "loading" | "in" | "out" | "error";

function SignedOut() {
  return (
    <main className="solo">
      <div className="mark">{APP_NAME}</div>
      <h1>Open your invite link to sign in</h1>
      <p>Lost it? Ask for a new one, or sign in from a device you already use.</p>
    </main>
  );
}

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
  const [drawer, setDrawer] = useState(false);

  const signedOut = useCallback(() => setAuth("out"), []);
  const { job, start } = useJob(signedOut);

  const load = useCallback(async () => {
    setAuth("loading");
    try {
      const [, options, context] = await Promise.all([api.me(), api.options(), api.context()]);
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

  const go = useCallback(() => {
    if (model) void start(toJobArgs(model, localDate()));
  }, [model, start]);

  const signOut = useCallback(async () => {
    try {
      await api.signOut();
    } catch {
      /* signed out either way, as far as this page goes */
    }
    setAuth("out");
  }, []);

  if (auth === "out") return <SignedOut />;
  if (auth === "error") return <Unreachable onRetry={load} />;

  const busy = job?.state === "queued" || job?.state === "running";
  return (
    <div className="app">
      <Band model={model} busy={busy}
        onChange={(k, v) => setModel((m) => (m ? setToken(m, k, v) : m))}
        onGo={go} filesOpen={drawer}
        onFiles={() => setDrawer((d) => !d)} />
      <Chat />
      <main className="panel">
        <Panel job={job} onRetry={go} />
      </main>
      <ContextColumn files={files} open={drawer} onClose={closeDrawer}
        onSignedOut={signedOut} onSignOut={signOut} />
    </div>
  );
}
