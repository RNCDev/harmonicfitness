// The app: the sign-in page, or once signed in the sky, the chat, and the Settings drawer.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, APP_NAME, NotSignedIn, setAuthLost, type KeyState, type Me } from "./lib/api";
import { ChoosePassword, SignIn } from "./zones/SignIn";
import { Mark } from "./ui/Mark";
import { Sky, type SkyKind } from "./ui/Sky";
import { useConversation } from "./lib/conversation";
import { KeyAskContext, type KeyAsk } from "./lib/keyAsk";
import { hasModelKey, keyRows } from "./lib/keys";
import { planOf, stepsOf } from "./lib/steps";
import { useSaved } from "./lib/useAction";
import { usePage } from "./lib/usePage";
import { useStartInfo } from "./lib/useStartInfo";
import { SAID } from "./lib/messages";
import { Boundary } from "./ui/Boundary";
import { Button } from "./ui/Button";
import { Icon } from "./ui/icons";
import { Notice } from "./ui/Notice";
import { Solo } from "./ui/Solo";
import { Chat, type KeyNeeded } from "./zones/chat/Chat";
import { Settings } from "./zones/settings/Settings";
import { Logs } from "./zones/logs/Logs";
import { CoachesPage } from "./zones/Coaches";

/** With no language-model key yet: the ones to choose from, to write the workouts. */
function keyNeeded(keys: KeyState[] | null): KeyNeeded | null {
  if (hasModelKey(keys) !== false) return null;
  const options = keyRows(keys ?? []).filter((r) => r.kind === "model")
    .map((r) => ({ name: r.name, service: r.service, voice: r.voice }));
  return options.length ? options : null;
}

type Auth = "loading" | "in" | "out" | "error";

function Unreachable({ onRetry }: { onRetry: () => void }) {
  return (
    <Solo>
      <h1>Can't reach HarmonicFitness</h1>
      <p>Check your connection, then try again.</p>
      <Button variant="primary" onClick={onRetry}>Try again</Button>
    </Solo>
  );
}

/** How long the first screen is the sky alone, so a quick answer doesn't flash words. */
const LOADING_SHOWN_AFTER = 600;

/** While the page asks who is signed in: nothing else asks the server until it knows. The sky at first; past a
 * moment, the mark and the words, so a slow connection never shows a page with nothing on it. */
function Loading() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), LOADING_SHOWN_AFTER);
    return () => clearTimeout(t);
  }, []);
  if (slow) return <Solo><Notice tone="busy">Loading HarmonicFitness…</Notice></Solo>;
  return (
    <div className="app" aria-busy="true">
      <Sky />
      <div className="work"><p className="sr" role="status">Loading HarmonicFitness…</p></div>
    </div>
  );
}

export function App() {
  const [auth, setAuth] = useState<Auth>("loading");
  const [me, setMe] = useState<Me | null>(null);

  const signedOut = useCallback(() => setAuth("out"), []);
  // a call anywhere that finds no one signed in brings the page back here
  useEffect(() => setAuthLost(signedOut), [signedOut]);

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
    return <ChoosePassword username={me.username} onDone={() => setMe({ ...me, has_password: true })} />;
  }
  return <SignedIn me={me} onSignedOut={signedOut} />;
}

/** The signed-in page. Mounted only once the server says who is signed in; unmounting it closes the job's stream. */
function SignedIn({ me, onSignedOut }: { me: Me; onSignedOut: () => void }) {
  const [drawer, setDrawer] = useState(false);
  const gear = useRef<HTMLButtonElement>(null);
  const [page, go] = usePage();
  const toggle = (p: "logs" | "coaches") => go(page === p ? "chat" : p);
  // a page that closes gives focus back to the header button that opened it
  const pageButtons = { logs: useRef<HTMLButtonElement>(null), coaches: useRef<HTMLButtonElement>(null) };
  const lastPage = useRef(page);
  useEffect(() => {
    const was = lastPage.current;
    lastPage.current = page;
    if (page === "chat" && was !== "chat") pageButtons[was].current?.focus();
  }, [page]); // eslint-disable-line react-hooks/exhaustive-deps
  const [keys, setKeys] = useState<KeyState[] | null>(null);
  const [openRow, setOpenRow] = useState<KeyAsk | null>(null);
  const needsKey = keyNeeded(keys);
  const { conv, working, error, noKey, send, record, schedule, cancel, halt, reset, job, waiting, resume } = useConversation();
  const steps = stepsOf(job?.stages ?? []);
  const plan = planOf(job?.stages ?? []);
  const { start, error: startError, reload: reloadStart, coaches, coachBar, chooseCoach, coachError } = useStartInfo(keys);

  // the settings that switch at once and save behind, put back with the reason if the server refuses
  const [sky, chooseSky, skyError] = useSaved<SkyKind>(me.sky ?? "flow", api.setSky,
    SAID.sky);
  const [autoRecord, chooseAutoRecord, autoRecordError] = useSaved(me.auto_record ?? false, api.setAutoRecord,
    SAID.notSaved);

  const closeDrawer = useCallback(() => setDrawer(false), []);

  // A key's row in Settings. From the welcome card the key is also chosen to write; from a coach that needs it,
  // the row only opens, so a voice key never changes who writes (OpenRouter's and Gemini's can do both).
  const openKey = useCallback((service: string, choose: boolean) => {
    setOpenRow((r) => ({ service, n: (r?.n ?? 0) + 1, choose }));
    setDrawer(true);
  }, []);
  const addKey = useCallback((service: string) => openKey(service, true), [openKey]);
  const addVoiceKey = useCallback((service: string) => openKey(service, false), [openKey]);

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
      <Sky kind={sky} busy={working} />
      <div className="work" data-page={page}>
        <header className="work-top">
          <Mark />
          <span className="top-gap" />
          {conv && page === "chat" && <Button variant="header" className="new" onClick={reset} disabled={working}>
            <Icon name="plus" size={14} weight={3.4} />
            New workout
          </Button>}
          <Button ref={pageButtons.coaches} variant="header" className="new page-toggle" pressed={page === "coaches"}
            title="Hear and choose your coach"
            aria-label="Coaches" onClick={() => toggle("coaches")}>
            <Icon name="coaches" size={16} />
            <span className="top-label">Coaches</span>
          </Button>
          <Button ref={pageButtons.logs} variant="header" className="new page-toggle" pressed={page === "logs"}
            title="Your past workouts"
            aria-label="Logs" onClick={() => toggle("logs")}>
            <Icon name="logs" size={16} />
            <span className="top-label">Logs</span>
          </Button>
          <Button ref={gear} variant="header" className="icon" aria-label="Settings" title="Settings"
            aria-expanded={drawer} aria-controls="ctx" onClick={() => setDrawer((d) => !d)}>
            <Icon name="gear" size={18} weight={1.7} />
          </Button>
        </header>
        {page === "logs" && <Boundary key="logs" what="The Logs page"><Logs onClose={() => go("chat")} /></Boundary>}
        {page === "coaches" && <Boundary key="coaches" what="The Coaches page">
          <CoachesPage coaches={start && !startError ? coaches : null} loadError={startError}
            onRetry={reloadStart} onCoach={(slug) => void chooseCoach(slug)}
            onAddKey={addVoiceKey} onOpenSettings={() => setDrawer(true)} onClose={() => go("chat")} error={coachError} />
        </Boundary>}
        {/* an earlier day's conversation shows as history; the next message starts a new one */}
        <Boundary what="The chat"><Chat lines={conv?.lines ?? []} working={working} steps={steps} plan={plan} error={error} noKey={noKey}
          onSend={send} onStop={halt} onOpenKeys={() => setDrawer(true)} coachBar={coachBar}
          first={{
            needsKey, onAddKey: addKey, start, starting: start === null && keys !== null,
            onCoach: (slug) => void chooseCoach(slug), coachError, onOpenCoaches: () => go("coaches"),
            startError, onRetryStart: reloadStart,
            waiting: waiting && !conv ? { offer: !!waiting.offer, at: waiting.updated_at } : null, onResume: resume,
          }}
          offers={{
            offer: !working ? conv?.offer ?? null : null, onRecord: record,
            later: conv && conv.state !== "failed" ? conv.later ?? null : null, scheduled: conv?.state === "scheduled",
            onSchedule: schedule, onCancel: cancel,
          }} /></Boundary>
      </div>
      <KeyAskContext.Provider value={openRow}>
        <Settings username={me.username} version={me.version} open={drawer} onClose={closeDrawer}
          onSignOut={signOut} onDeleted={onSignedOut} onKeys={setKeys} returnFocus={gear}
          sky={sky} onSky={(s) => void chooseSky(s)} skyError={skyError}
          autoRecord={autoRecord} onAutoRecord={(on) => void chooseAutoRecord(on)} autoRecordError={autoRecordError} />
      </KeyAskContext.Provider>
    </div>
  );
}
