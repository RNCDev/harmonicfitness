// The chat: the lines so far (the coach's as Markdown), what the coach is doing while a turn runs,
// and the box to write in.
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Audio, ChatLine, Offer, StartInfo } from "../api";
import { Starter } from "./Starter";

/** A step of the coach's turn: running while its tool works, then done (or failed). A thinking step (the model
 * working between tools) shows only while it runs. `key` tells one step from another across updates. */
export type Step = { text: string; failed?: boolean; running?: boolean; think?: boolean; key?: string };

/** A turn's job events as its steps, oldest first: an event with an id updates that step (it's said as it
 * starts, then as it ends); one without, from a server before 0.25.2, is a step already done. */
export function stepsOf(events: { stage: string; [field: string]: unknown }[]): Step[] {
  const out: Step[] = [];
  const at = new Map<number, number>();
  for (const e of events) {
    if (e.stage !== "step" || typeof e.text !== "string") continue;
    const step: Step = { text: e.text, failed: e.failed === true || e.state === "failed", running: e.state === "running",
      think: e.think === true, key: typeof e.id === "number" ? `s${e.id}` : `i${out.length}` };
    if (typeof e.id === "number" && at.has(e.id)) {
      out[at.get(e.id)!] = step;
      continue;
    }
    if (typeof e.id === "number") at.set(e.id, out.length);
    out.push(step);
  }
  return out;
}

type Props = {
  lines: ChatLine[];
  working: boolean;
  /** What the coach has done so far this turn, oldest first. */
  steps?: Step[];
  error: string | null;
  noKey: boolean;
  /** Resolves false when the line was refused, so the box gets its text back. */
  onSend: (line: string) => Promise<boolean> | void;
  onOpenKeys: () => void;
  /** A priced recording waiting for approval, and the button that approves it. */
  offer?: Offer | null;
  onRecord?: () => Promise<boolean> | void;
  /** Stops the running turn. */
  onStop?: () => void;
  /** No language-model key yet: the key to ask for, in place of the greeting, and the button that opens it. */
  needsKey?: KeyNeeded | null;
  /** Chooses a service to write the workouts, and opens its key. */
  onAddKey?: (service: string) => void;
  /** What the first screen's sentence is filled in with (null until it arrives). */
  start?: StartInfo | null;
  /** The coach picked in the sentence. */
  onCoach?: (slug: string) => void;
  /** The coach shown above the conversation, with their lane number. */
  coachBar?: { n: number; name: string; service: string } | null;
};

/** The language-model key a new listener adds first. */
export type KeyNeeded = { name: string; service: string; voice: boolean }[];

const FREE_FROM: Record<string, string> = { gemini: "Google AI Studio" };

function Welcome({ need, onAddKey }: { need: KeyNeeded; onAddKey?: (service: string) => void }) {
  return (
    <div className="m a welcome">
      <h2>Welcome to HarmonicFitness</h2>
      <p>Tell your coach what workout you want, and you get it as audio for your earbuds. The coach tells you
        what to do, keeps time and keeps you company, so there's no screen to watch.</p>
      <p>To start, pick the AI that writes your workouts, and add a key for it. Keys are stored encrypted,
        and anything they're used for is billed to your own account.</p>
      <div className="welcome-picks">
        {need.map((o) => (
          <button key={o.service} type="button" className="welcome-pick" onClick={() => onAddKey?.(o.service)}>
            <span className="welcome-pick-name">{o.name}</span>
            <span className="welcome-pick-note">{FREE_FROM[o.service] ? `Free key from ${FREE_FROM[o.service]}` : "Paid key"}
              {o.voice ? ". Also voices a coach" : ""}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

const SERVICES: Record<string, string> = { fish: "Fish Audio", elevenlabs: "ElevenLabs", gemini: "Gemini", inworld: "Inworld" };

function RecordOffer({ offer, onRecord }: { offer: Offer; onRecord?: () => Promise<boolean> | void }) {
  const [busy, setBusy] = useState(false);
  const price = offer.usd < 0.01 ? "under 1¢" : `about $${(Math.ceil(offer.usd * 100 - 1e-9) / 100).toFixed(2)}`;   // rounded up
  return (
    <div className="m a offer">
      <p><strong>{offer.name}</strong> is ready to record with {offer.coach}.</p>
      <p className="cx-s">{offer.chars.toLocaleString()} characters on {SERVICES[offer.service] ?? offer.service}, {price}
        {offer.design ? ", including designing the coach's voice" : ""}. It's charged to your own key.</p>
      <button type="button" className="go" disabled={busy}
        onClick={async () => { setBusy(true); if ((await onRecord?.()) === false) setBusy(false); }}>
        {busy ? "Starting…" : `Record it (${price})`}
      </button>
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

function until(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" });
}

/** A workout's MP3: play it here, or download it, until it expires. */
function AudioLine({ audio }: { audio: Audio }) {
  const expired = new Date(audio.expires_at).getTime() <= Date.now();
  const src = `/api/media/${encodeURIComponent(audio.id)}`;
  return (
    <div className="m a audio">
      <p className="audio-name">{audio.name}</p>
      {expired ? <p className="cx-s">This recording has expired. Ask for the workout again to record a new one.</p> : (
        <>
          <audio controls preload="metadata" src={src} />
          <p className="cx-s">
            <a href={`${src}?download=1`} download={`${audio.name}.mp3`}>Download the MP3</a>
            {until(audio.expires_at) && ` · kept until ${until(audio.expires_at)}`}
          </p>
        </>
      )}
    </div>
  );
}

function seconds(since: number): string {
  const s = Math.max(0, Math.round((Date.now() - since) / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
}

/** "Your coach is working…" with a running clock, the coach's latest steps, and what it's thinking about now. */
function Working({ steps, onStop }: { steps: Step[]; onStop?: () => void }) {
  const [stopping, setStopping] = useState(false);
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
  if (thinking) steps = [...steps, thinking];
  const now = Date.now();
  for (const s of steps) if (s.running && !began.current.has(s.key!)) began.current.set(s.key!, now);
  const age = (s: Step) => (now - (began.current.get(s.key!) ?? now)) / 1000;
  const current = steps.find((s) => s.running && age(s) >= LONG);
  const shown = steps.slice(-SHOWN_STEPS);
  return (
    <div className="m a thinking" aria-live="polite">
      <p className="think-head">{stopping ? "Stopping…" : "Your coach is working…"} <span className="clock">{seconds(since)}</span>
        {onStop && !stopping && (
          <button type="button" className="quiet stop" onClick={() => { setStopping(true); onStop(); }}>Stop</button>
        )}
      </p>
      {shown.length > 0 && (
        <ul className="steps">
          {steps.length > shown.length && <li className="more">{steps.length - shown.length} earlier steps</li>}
          {shown.map((s) => (
            <li key={s.key} className={`${s.running ? "now" : s.failed ? "bad" : ""}${s.think ? " think" : ""}`}
              aria-current={s.running ? "step" : undefined}>
              {s.text}{s.think && s.running ? "…" : ""}
              {s.running && age(s) >= TIMED && <span className="step-t">{seconds(began.current.get(s.key!)!)}</span>}
            </li>
          ))}
        </ul>
      )}
      {current && <p className="think-hint">{longWait(current)}</p>}
    </div>
  );
}

export function Chat({ lines, working, steps = [], error, noKey, onSend, onOpenKeys, offer, onRecord, onStop,
  needsKey = null, onAddKey, start = null, onCoach, coachBar = null }: Props) {
  const [text, setText] = useState(readDraft);
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

  return (
    <main className="chat" aria-label="Chat">
      {coachBar && lines.length > 0 && (
        <div className="coachbar"><span className="lane-badge" aria-hidden="true">{coachBar.n}</span>
          <b>{coachBar.name}</b><small>{coachBar.service}</small></div>
      )}
      <div className="chat-log" ref={log} role="log" aria-live="polite">
        {lines.length === 0 && !working && needsKey && <Welcome need={needsKey} onAddKey={onAddKey ?? (() => onOpenKeys())} />}
        {lines.length === 0 && !working && !needsKey && start && (
          <Starter info={start} onStart={onSend} onCoach={onCoach}
            onFill={(line) => { setText(line); requestAnimationFrame(() => { box.current?.focus(); box.current?.setSelectionRange(line.length, line.length); }); }} />
        )}
        {lines.map((l, i) => l.audio ? <AudioLine key={i} audio={l.audio} /> : l.role === "user" ? (
          <p key={i} className="m u">{l.text}</p>
        ) : (
          <div key={i} className="m a md">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{l.text}</ReactMarkdown>
          </div>
        ))}
        {offer && !working && <RecordOffer offer={offer} onRecord={onRecord} />}
        {working && <Working steps={steps} onStop={onStop} />}
      </div>
      {error && (
        <div className="chat-error" role="alert">
          <p>{error}</p>
          {noKey && <button type="button" className="go alt" onClick={onOpenKeys}>Open Settings</button>}
        </div>
      )}
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <label className="sr" htmlFor="chat-box">Message</label>
        <textarea id="chat-box" ref={box} rows={1} value={text}
          placeholder={needsKey ? "Add a key in Settings first" : lines.length === 0 ? "Or describe the workout you want in your own words" : "Reply to your coach"} disabled={working || !!needsKey}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send();
            }
          }} />
        <button type="submit" className="go" disabled={working || !!needsKey || !text.trim()}>Send</button>
      </form>
    </main>
  );
}
