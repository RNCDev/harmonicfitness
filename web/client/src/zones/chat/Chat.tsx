// The chat: the lines so far (the coach's as Markdown), what the coach is doing while a turn runs,
// and the box to write in.
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatLine, Later, Offer, Plan, StartInfo } from "../../lib/api";
import { clockAt } from "../../lib/format";
import { writerRank } from "../../lib/keys";
import { readDraft, keepDraft } from "../../lib/draft";
import { keepLineBreaks } from "../../lib/lines";
import type { Step } from "../../lib/steps";
import { AudioFile } from "../../ui/AudioFile";
import { Button } from "../../ui/Button";
import { ConfirmInline } from "../../ui/ConfirmInline";
import { Notice } from "../../ui/Notice";
import { Starter } from "../Starter";
import { LaterOffer, RecordOffer, Scheduled } from "./Offers";
import { Working } from "./Working";
import { ReadyWorkouts } from "../Ready";

/** The language-model key a new listener adds first. */
export type KeyNeeded = { name: string; service: string; voice: boolean }[];

/** What the first screen shows before any line: the welcome (no key yet), the conversation waiting from earlier
 * today, or the request. */
export type FirstScreen = {
  /** No language-model key yet: the keys to choose from, in place of the request, and the choosing. */
  needsKey?: KeyNeeded | null;
  onAddKey?: (service: string) => void;
  /** Today's conversation waiting on the listener, and opening it. */
  waiting?: { offer: boolean; at: string | null } | null;
  onResume?: () => void;
  /** What the request is filled in with (null until it arrives); `starting`: show it anyway, blanks rolling in. */
  start?: StartInfo | null;
  starting?: boolean;
  onCoach?: (slug: string) => void;
  coachError?: string | null;
  onOpenCoaches?: () => void;
  /** Why the request's coaches and defaults couldn't be loaded, and asking again. */
  startError?: string | null;
  onRetryStart?: () => void;
};

/** What waits on the listener's approval: a priced recording, or a workout for later and its schedule. */
export type Offers = {
  offer?: Offer | null;
  onRecord?: () => Promise<boolean> | void;
  later?: Later | null;
  scheduled?: boolean;
  onSchedule?: () => Promise<boolean> | void;
  onCancel?: () => Promise<boolean> | void;
};

type Props = {
  lines: ChatLine[];
  working: boolean;
  /** What the coach has done so far this turn, oldest first. */
  steps?: Step[];
  /** The workout's plan, once its timing is settled: shown while its words are written. */
  plan?: Plan | null;
  error: string | null;
  noKey: boolean;
  /** Resolves false when the line was refused, so the box gets its text back. `startAt`: the starter's picked time. */
  onSend: (line: string, startAt?: string) => Promise<boolean> | void;
  /** Stops the running turn. */
  onStop?: () => void;
  onOpenKeys: () => void;
  /** The coach shown above the conversation. */
  coachBar?: { name: string; service: string } | null;
  first?: FirstScreen;
  offers?: Offers;
};

/** What each first key gives, in a line. */
const PICK_NOTES: Record<string, string> = {
  gemini: "Writes your workouts and voices your coach, with six coaches to choose from. The cheapest; Google asks for 5 USD of prepaid credit to start",
  openrouter: "Writes your workouts and voices your coach: six coaches with ElevenLabs voices. One bill",
  anthropic: "Writes your workouts; then choose a coach, who needs a voice key",
  openai: "Writes your workouts; then choose a coach, who needs a voice key",
};

function Welcome({ need, onAddKey }: { need: KeyNeeded; onAddKey?: (service: string) => void }) {
  return (
    <div className="m a welcome">
      <h2>Welcome to HarmonicFitness</h2>
      <p>Tell your coach what workout you want, and you get it as audio for your earbuds. The coach tells you
        what to do, keeps time and keeps you company, so there's no screen to watch.</p>
      <p>To start, add one key. Keys are stored encrypted, and anything they're used for is billed to your own
        account.</p>
      <div className="welcome-picks">
        {[...need].sort((a, b) => writerRank(a.service, a.voice) - writerRank(b.service, b.voice)).map((o) => (
          <Button key={o.service} variant="tile" className="welcome-pick" onClick={() => onAddKey?.(o.service)}>
            <span className="head welcome-pick-name">{o.name}</span>
            <span className="welcome-pick-note">{PICK_NOTES[o.service]
              ?? (o.voice ? "Writes your workouts and voices your coach" : "Writes your workouts; then choose a coach")}</span>
          </Button>
        ))}
      </div>
      <ReadyWorkouts intro="Try one now, before any key: a ready-made workout" />
    </div>
  );
}

export function Chat({ lines, working, steps = [], plan = null, error, noKey, onSend, onStop, onOpenKeys, coachBar = null,
  first = {}, offers = {} }: Props) {
  const { needsKey = null, onAddKey, waiting = null, onResume, start = null, starting = false, onCoach, coachError,
    onOpenCoaches, startError = null, onRetryStart } = first;
  const { offer = null, onRecord, later = null, scheduled = false, onSchedule, onCancel } = offers;
  const [text, setText] = useState(readDraft);
  const [stopping, setStopping] = useState(false);
  /** Stop was pressed once: it asks before the plan so far is thrown away. */
  const [askStop, setAskStop] = useState(false);
  useEffect(() => { if (!working) { setStopping(false); setAskStop(false); } }, [working]);
  const log = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => keepDraft(text), [text]);

  useEffect(() => {
    // scroll the list only: scrollIntoView would also scroll the sheet around it, hiding the coach bar
    // the first screen starts at its top; a conversation follows its newest line
    const el = log.current;
    if (el && (lines.length > 0 || working)) el.scrollTop = el.scrollHeight;
  }, [lines.length, working, steps.length, !!coachBar]);

  async function send() {
    const line = text.trim();
    if (!line || working || needsKey) return;
    setText("");
    if ((await onSend(line)) === false) setText((t) => t || line);
  }

  const at = clockAt(waiting?.at);
  return (
    <main className={lines.length > 0 || working ? "chat talk" : "chat"} aria-label="Chat">
      {coachBar && lines.length > 0 && (
        <div className="coachbar"><b>{coachBar.name}</b><small>{coachBar.service}</small></div>
      )}
      <div className="chat-log" ref={log} role="log" aria-live="polite">
        {lines.length === 0 && !working && needsKey && <Welcome need={needsKey} onAddKey={onAddKey ?? (() => onOpenKeys())} />}
        {lines.length === 0 && !working && !needsKey && waiting && onResume && (
          <Button variant="bare" className="resume" onClick={onResume}>
            <span className="resume-h">Pick up where you left off</span>
            <span className="resume-s">{waiting.offer ? "Your workout is ready to record" : "Your coach asked you something"}{at && ` at ${at}`}.</span>
            <span className="resume-go" aria-hidden="true">→</span>
          </Button>
        )}
        {lines.length === 0 && !working && !needsKey && (start || starting) && (
          <Starter info={start} onStart={onSend} onCoach={onCoach} onOpenCoaches={onOpenCoaches} coachError={coachError}
            loadError={startError} onRetry={onRetryStart} />
        )}
        {lines.map((l, i) => l.audio ? <div key={i} className="m a audio"><AudioFile audio={l.audio} titled /></div>
          : l.role === "user" ? (
            <p key={i} className="m u">{l.text}</p>
          ) : (
            <div key={i} className="m a md">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{keepLineBreaks(l.text)}</ReactMarkdown>
            </div>
          ))}
        {offer && !working && <RecordOffer offer={offer} onRecord={onRecord} />}
        {later && later.usd != null && !later.done && !later.due && new Date(later.at).getTime() > Date.now() && !offer
          && !working && !scheduled && <LaterOffer later={later} onSchedule={onSchedule} />}
        {later && scheduled && <Scheduled later={later} onCancel={onCancel} />}
        {working && <Working steps={steps} plan={plan} stopping={stopping} />}
      </div>
      {error && (
        <div className="chat-error">
          <Notice tone="error">{error}</Notice>
          {noKey && <Button variant="outline" onClick={onOpenKeys}>Open Settings</Button>}
        </div>
      )}
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <label className="sr" htmlFor="chat-box">Message</label>
        <textarea id="chat-box" ref={box} rows={1} value={text}
          placeholder={needsKey ? "Add a key in Settings first" : scheduled ? "Scheduled: cancel it to change anything"
            : lines.length === 0 ? "Or describe the workout you want in your own words" : "Reply to your coach"}
          disabled={working || scheduled || !!needsKey}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send();
            }
          }} />
        {working && onStop && !stopping && !askStop && (
          <Button variant="stop" onClick={() => setAskStop(true)}>Stop</Button>
        )}
        {working && onStop && !stopping && askStop && (
          <ConfirmInline className="chat-stop" question="Stop, and lose this workout's plan?" confirm="Stop it"
            keep="Keep going" onConfirm={() => { setAskStop(false); setStopping(true); onStop(); }}
            onKeep={() => { setAskStop(false); box.current?.focus(); }} />
        )}
        <Button type="submit" variant="primary" disabled={working || scheduled || !!needsKey || !text.trim()}>Send</Button>
      </form>
    </main>
  );
}
