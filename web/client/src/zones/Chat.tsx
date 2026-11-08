// The chat: the lines so far (the coach's as Markdown), what the coach is doing while a turn runs,
// and the box to write in.
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatLine, Later, Offer, StartInfo } from "../api";
import { clockAt, dollars } from "../lib/format";
import { serviceName, writerRank } from "../lib/keys";
import type { Step } from "../lib/steps";
import { Quiet, useAction } from "../lib/useAction";
import { AudioFile } from "../ui/AudioFile";
import { Button } from "../ui/Button";
import { Notice } from "../ui/Notice";
import { ahead, timeOfDay } from "../when";
import { Starter } from "./Starter";

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
  error: string | null;
  noKey: boolean;
  /** Resolves false when the line was refused, so the box gets its text back. `startAt`: the starter's picked time. */
  onSend: (line: string, startAt?: string) => Promise<boolean> | void;
  /** Stops the running turn. */
  onStop?: () => void;
  onOpenKeys: () => void;
  /** The coach shown above the conversation, with their lane number. */
  coachBar?: { n: number; name: string; service: string } | null;
  first?: FirstScreen;
  offers?: Offers;
};

/** What each first key gives, in a line. */
const PICK_NOTES: Record<string, string> = {
  gemini: "Writes your workouts and voices your coach, with six coaches to choose from. Free key; the cheapest",
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
          <button key={o.service} type="button" className="welcome-pick" onClick={() => onAddKey?.(o.service)}>
            <span className="welcome-pick-name">{o.name}</span>
            <span className="welcome-pick-note">{PICK_NOTES[o.service]
              ?? (o.voice ? "Writes your workouts and voices your coach" : "Writes your workouts; then choose a coach")}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** An approval button: busy from the tap until its screen goes; a refusal (false) gives it back. */
function useApproval(act?: () => Promise<boolean> | void) {
  return useAction(async () => { if ((await act?.()) === false) throw new Quiet(); }, { hold: true });
}

function RecordOffer({ offer, onRecord }: { offer: Offer; onRecord?: () => Promise<boolean> | void }) {
  const rec = useApproval(onRecord);
  const price = offer.usd < 0.01 ? dollars(offer.usd) : `about ${dollars(offer.usd)}`;
  return (
    <div className="m a offer">
      <p><strong>{offer.name}</strong> is ready to record with {offer.coach}.</p>
      <p className="cx-s">{offer.chars.toLocaleString()} characters on {serviceName(offer.service)}, {price}
        {offer.design ? ", including designing the coach's voice" : ""}. It's charged to your own key.</p>
      <Button variant="primary" busy={rec.busy} busyLabel="Starting…" onClick={() => void rec.run()}>
        {`Record it (${price})`}
      </Button>
    </div>
  );
}

/** The check-in is done for a workout at a later time: what it costs, the most it may, and Schedule it. */
function LaterOffer({ later, onSchedule }: { later: Later; onSchedule?: () => Promise<boolean> | void }) {
  const go = useApproval(onSchedule);
  const at = new Date(later.at);
  const cap = dollars(later.ceiling_usd ?? 0);
  return (
    <div className="m a offer">
      <p>Your {later.minutes}-minute workout with {later.coach} is planned for <strong>{ahead(at)}</strong>.</p>
      <p className="cx-s">About {dollars(later.usd ?? 0)}, and never more than {cap}, charged to your own key.
        {" "}{later.coach ?? "Your coach"} writes and records it fifteen minutes before, with that hour's news and weather, so it's ready when you are.</p>
      <Button variant="primary" busy={go.busy} busyLabel="Scheduling…" onClick={() => void go.run()}>
        {`Schedule it (up to ${cap})`}
      </Button>
    </div>
  );
}

/** A scheduled workout, waiting for its time; Cancel takes it back before the writing begins. */
function Scheduled({ later, onCancel }: { later: Later; onCancel?: () => Promise<boolean> | void }) {
  const stop = useApproval(onCancel);
  const at = new Date(later.at);
  const due = later.due ? new Date(later.due) : null;
  return (
    <div className="m a offer">
      <p>Scheduled for <strong>{ahead(at)}</strong>{later.coach ? ` with ${later.coach}` : ""}.</p>
      <p className="cx-s">{due ? `Writing starts at ${timeOfDay(due)}` : "Writing starts fifteen minutes before"}; the
        workout appears here, ready to play, by {timeOfDay(at)}. Come back then, or leave this page open.</p>
      <Button variant="outline" busy={stop.busy} busyLabel="Cancelling…" onClick={() => void stop.run()}>Cancel</Button>
    </div>
  );
}

const SHOWN_STEPS = 6;

/** The box's unsent text, kept for this tab across a reload. Storage may be missing or refuse: then it isn't kept. */
const DRAFT = "hf-chat-draft";
function readDraft(): string {
  try {
    return sessionStorage.getItem(DRAFT) ?? "";
  } catch {
    return "";
  }
}
function keepDraft(text: string): void {
  try {
    if (text) sessionStorage.setItem(DRAFT, text);
    else sessionStorage.removeItem(DRAFT);
  } catch {
    /* not kept */
  }
}

/** Steps in a row that say the same thing are one step, as the later one stands. */
function collapsed(steps: Step[]): Step[] {
  return steps.filter((s, i) => i === steps.length - 1 || s.text !== steps[i + 1].text);
}

/** A note for a wait that has run long, by what it's waiting on. */
function longWait(s: Step): string {
  if (/^Recording/.test(s.text)) return "Recording a full workout takes a few minutes.";
  if (/^Designing|voices/.test(s.text)) return "Making a voice takes a minute or two.";
  if (s.think) return "Planning carefully takes a minute when there's a lot to fit in.";
  return "Still on it.";
}
const LONG = 25;   // seconds before a running step says it's a long one
const TIMED = 8;   // seconds before a running step shows its own clock

function elapsed(since: number): string {
  const s = Math.max(0, Math.round((Date.now() - since) / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
}

/** "Your coach is working…" with a running clock, the coach's latest steps, and what it's thinking about now.
 * The chat's log already announces what's added to it, so this says nothing more on its own. */
function Working({ steps, stopping }: { steps: Step[]; stopping: boolean }) {
  const [since] = useState(() => Date.now());
  const [, tick] = useState(0);
  const began = useRef(new Map<string, number>());   // when each running step was first seen
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  steps = steps.map((s, i) => (s.key ? s : { ...s, key: `n${i}` }));
  const last = steps[steps.length - 1];
  const thinking = last?.think && last.running ? last : null;
  steps = collapsed(steps.filter((s) => !s.think));
  if (thinking) {
    // "Wrapping up" read as a step and then thought about is one line, not two
    if (steps.length && !steps[steps.length - 1].running && steps[steps.length - 1].text === thinking.text) steps = steps.slice(0, -1);
    steps = [...steps, thinking];
  }
  const now = Date.now();
  for (const s of steps) if (s.running && !began.current.has(s.key!)) began.current.set(s.key!, now);
  const age = (s: Step) => (now - (began.current.get(s.key!) ?? now)) / 1000;
  const current = steps.find((s) => s.running && age(s) >= LONG);
  const shown = steps.slice(-SHOWN_STEPS);
  return (
    <div className="m a thinking">
      <p className="think-head">{stopping ? "Stopping…" : "Your coach is working…"} <span className="clock">{elapsed(since)}</span></p>
      {shown.length > 0 && (
        <ul className="steps">
          {steps.length > shown.length && <li className="more">{steps.length - shown.length} earlier steps</li>}
          {shown.map((s) => (
            <li key={s.key} className={`${s.running ? "now" : s.failed ? "bad" : ""}${s.think ? " think" : ""}`}
              aria-current={s.running ? "step" : undefined}>
              {s.text}{s.think && s.running ? "…" : ""}
              {s.running && age(s) >= TIMED && <span className="step-t">{elapsed(began.current.get(s.key!)!)}</span>}
            </li>
          ))}
        </ul>
      )}
      {current && <p className="think-hint">{longWait(current)}</p>}
    </div>
  );
}

export function Chat({ lines, working, steps = [], error, noKey, onSend, onStop, onOpenKeys, coachBar = null,
  first = {}, offers = {} }: Props) {
  const { needsKey = null, onAddKey, waiting = null, onResume, start = null, starting = false, onCoach, coachError,
    onOpenCoaches } = first;
  const { offer = null, onRecord, later = null, scheduled = false, onSchedule, onCancel } = offers;
  const [text, setText] = useState(readDraft);
  const [stopping, setStopping] = useState(false);
  useEffect(() => { if (!working) setStopping(false); }, [working]);
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
    <main className="chat" aria-label="Chat">
      {coachBar && lines.length > 0 && (
        <div className="coachbar"><span className="lane-badge" aria-hidden="true">{coachBar.n}</span>
          <b>{coachBar.name}</b><small>{coachBar.service}</small></div>
      )}
      <div className="chat-log" ref={log} role="log" aria-live="polite">
        {lines.length === 0 && !working && needsKey && <Welcome need={needsKey} onAddKey={onAddKey ?? (() => onOpenKeys())} />}
        {lines.length === 0 && !working && !needsKey && waiting && onResume && (
          <button type="button" className="resume" onClick={onResume}>
            <span className="resume-h">Pick up where you left off</span>
            <span className="resume-s">{waiting.offer ? "Your workout is ready to record" : "Your coach asked you something"}{at && ` at ${at}`}.</span>
            <span className="resume-go" aria-hidden="true">→</span>
          </button>
        )}
        {lines.length === 0 && !working && !needsKey && (start || starting) && (
          <Starter info={start} onStart={onSend} onCoach={onCoach} onOpenCoaches={onOpenCoaches} coachError={coachError}
            onFill={(line) => { setText(line); requestAnimationFrame(() => { box.current?.focus(); box.current?.setSelectionRange(line.length, line.length); }); }} />
        )}
        {lines.map((l, i) => l.audio ? <div key={i} className="m a audio"><AudioFile audio={l.audio} titled /></div>
          : l.role === "user" ? (
            <p key={i} className="m u">{l.text}</p>
          ) : (
            <div key={i} className="m a md">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{l.text}</ReactMarkdown>
            </div>
          ))}
        {offer && !working && <RecordOffer offer={offer} onRecord={onRecord} />}
        {later && later.usd != null && !later.done && !later.due && new Date(later.at).getTime() > Date.now() && !offer
          && !working && !scheduled && <LaterOffer later={later} onSchedule={onSchedule} />}
        {later && scheduled && <Scheduled later={later} onCancel={onCancel} />}
        {working && <Working steps={steps} stopping={stopping} />}
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
        {working && onStop && !stopping && (
          <button type="button" className="go stop" onClick={() => { setStopping(true); onStop(); }}>Stop</button>
        )}
        <button type="submit" className="go" disabled={working || scheduled || !!needsKey || !text.trim()}>Send</button>
      </form>
    </main>
  );
}
