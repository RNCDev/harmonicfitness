// The app: the sign-in page, or once signed in the sky, the chat, and the Settings drawer. The server says whether
// sign-in goes through Clerk (GET /api/me); the pages read that from lib/site.ts.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, APP_NAME, NotSignedIn, setAuthLost, type Me } from "./lib/api";
import { ChoosePassword, SignIn } from "./zones/SignIn";
import { Mark } from "./ui/Mark";
import { Sky, type SkyKind } from "./ui/Sky";
import { useConversation } from "./lib/conversation";
import { SiteContext } from "./lib/site";
import { planOf, stepsOf } from "./lib/steps";
import { useSaved } from "./lib/useAction";
import { checkoutReturn, useMinutes } from "./lib/useMinutes";
import { usePage } from "./lib/usePage";
import { useStartInfo } from "./lib/useStartInfo";
import { SAID } from "./lib/messages";
import { leave } from "./lib/visits";
import { Boundary } from "./ui/Boundary";
import { Button } from "./ui/Button";
import { Icon } from "./ui/icons";
import { Notice } from "./ui/Notice";
import { Solo } from "./ui/Solo";
import { Chat } from "./zones/chat/Chat";
import { Settings } from "./zones/settings/Settings";
import { Logs } from "./zones/logs/Logs";
import { AdminPage } from "./zones/Admin";
import { CoachesPage } from "./zones/Coaches";

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
  // an account with no password chooses one, except where Clerk signs people in: there is none to choose
  if (!me.has_password && !me.clerk) {
    return <ChoosePassword username={me.username} onDone={() => setMe({ ...me, has_password: true })} />;
  }
  return <Site me={me}><SignedIn me={me} onSignedOut={signedOut} /></Site>;
}

function Site({ me, children }: { me: Me; children: ReactNode }) {
  const site = useMemo(() => ({ clerk: !!me.clerk }), [me.clerk]);
  return <SiteContext.Provider value={site}>{children}</SiteContext.Provider>;
}

/** The signed-in page. Mounted only once the server says who is signed in; unmounting it closes the job's stream. */
function SignedIn({ me, onSignedOut }: { me: Me; onSignedOut: () => void }) {
  const [drawer, setDrawer] = useState(false);
  const gear = useRef<HTMLButtonElement>(null);
  const [page, go] = usePage();
  const toggle = (p: "logs" | "coaches" | "admin") => go(page === p ? "chat" : p);
  // a page that closes gives focus back to the header button that opened it
  const pageButtons = { logs: useRef<HTMLButtonElement>(null), coaches: useRef<HTMLButtonElement>(null),
    admin: useRef<HTMLButtonElement>(null) };
  const lastPage = useRef(page);
  useEffect(() => {
    const was = lastPage.current;
    lastPage.current = page;
    if (page === "chat" && was !== "chat") pageButtons[was].current?.focus();
  }, [page]); // eslint-disable-line react-hooks/exhaustive-deps
  const { conv, working, error, noMinutes, send, record, schedule, cancel, halt, reset, job, waiting, resume } = useConversation();
  const steps = stepsOf(job?.stages ?? []);
  const plan = planOf(job?.stages ?? []);
  const { start, error: startError, reload: reloadStart, coaches, coachBar, chooseCoach, coachError } = useStartInfo();

  // the settings that switch at once and save behind, put back with the reason if the server refuses
  const [sky, chooseSky, skyError] = useSaved<SkyKind>(me.sky ?? "flow", api.setSky,
    SAID.sky);
  const [autoRecord, chooseAutoRecord, autoRecordError] = useSaved(me.auto_record ?? false, api.setAutoRecord,
    SAID.notSaved);

  // the minutes: what's left sits in the header and opens their section of Settings, as
  // "Get minutes" does, and as coming back from the checkout page does (with how it went, said once)
  const minutes = useMinutes(working);
  const left = minutes.state?.minutes ?? me.minutes ?? null;
  const [goTo, setGoTo] = useState<{ section: string; n: number } | null>(null);
  const openMinutes = useCallback(() => {
    setGoTo((g) => ({ section: "cx-minutes", n: (g?.n ?? 0) + 1 }));
    setDrawer(true);
  }, []);
  const [back, setBack] = useState(checkoutReturn);
  const { settle } = minutes;
  useEffect(() => {
    if (!back) return;
    openMinutes();
    if (back === "bought") settle();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const closeDrawer = useCallback(() => { setDrawer(false); setBack(null); }, []);

  // where Clerk signs people in, the sign-in page ends Clerk's session too (lib/visits.ts): signed out is signed out
  const clerk = !!me.clerk;
  const gone = useCallback(() => {
    if (clerk) leave();
    onSignedOut();
  }, [clerk, onSignedOut]);
  const signOut = useCallback(async () => {
    if (clerk) leave();
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
          {me.admin && (
            <Button ref={pageButtons.admin} variant="header" className="new page-toggle" pressed={page === "admin"}
              title="Usage and profit" aria-label="Admin" onClick={() => toggle("admin")}>
              <Icon name="chart" size={16} />
              <span className="top-label">Admin</span>
            </Button>
          )}
          {left !== null && (
            <Button variant="header" className="minutes-chip" title="Your minutes: add more, and see what was used"
              aria-label={`${left} ${left === 1 ? "minute" : "minutes"} left`} onClick={openMinutes}>
              {left} min
            </Button>
          )}
          <Button ref={gear} variant="header" className="icon" aria-label="Settings" title="Settings"
            aria-expanded={drawer} aria-controls="ctx" onClick={() => setDrawer((d) => !d)}>
            <Icon name="gear" size={18} weight={1.7} />
          </Button>
        </header>
        {page === "logs" && <Boundary key="logs" what="The Logs page"><Logs onClose={() => go("chat")} /></Boundary>}
        {page === "admin" && me.admin && <Boundary key="admin" what="The Admin page">
          <AdminPage onClose={() => go("chat")} /></Boundary>}
        {page === "coaches" && <Boundary key="coaches" what="The Coaches page">
          <CoachesPage coaches={start && !startError ? coaches : null} loadError={startError}
            onRetry={reloadStart} onCoach={(slug) => void chooseCoach(slug)}
            onClose={() => go("chat")} error={coachError} />
        </Boundary>}
        {/* an earlier day's conversation shows as history; the next message starts a new one */}
        <Boundary what="The chat"><Chat lines={conv?.lines ?? []} working={working} steps={steps} plan={plan} error={error}
          noMinutes={noMinutes} onGetMinutes={openMinutes}
          onSend={send} onStop={halt} coachBar={coachBar}
          first={{
            start, starting: start === null,
            onCoach: (slug) => void chooseCoach(slug), coachError,
            startError, onRetryStart: reloadStart,
            waiting: waiting && !conv ? { offer: !!waiting.offer, at: waiting.updated_at } : null, onResume: resume,
          }}
          offers={{
            offer: !working ? conv?.offer ?? null : null, onRecord: record,
            later: conv && conv.state !== "failed" ? conv.later ?? null : null, scheduled: conv?.state === "scheduled",
            onSchedule: schedule, onCancel: cancel,
          }} /></Boundary>
      </div>
      <Settings username={me.username} version={me.version} open={drawer} onClose={closeDrawer}
        onSignOut={signOut} onDeleted={gone} returnFocus={gear}
        minutes={minutes} back={back} goTo={goTo} clerkLinked={!!me.clerk_linked}
        sky={sky} onSky={(s) => void chooseSky(s)} skyError={skyError}
        autoRecord={autoRecord} onAutoRecord={(on) => void chooseAutoRecord(on)} autoRecordError={autoRecordError} />
    </div>
  );
}
