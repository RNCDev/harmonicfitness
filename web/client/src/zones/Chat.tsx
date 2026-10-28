// The chat: the lines so far (the coach's as Markdown), what the coach is doing while a turn runs,
// and the box to write in.
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Audio, ChatLine } from "../api";

export type Step = { text: string; failed?: boolean };

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
};

const SHOWN_STEPS = 6;

/** Steps in a row that say the same thing are one step. */
function collapsed(steps: Step[]): Step[] {
  return steps.filter((s, i) => i === 0 || s.text !== steps[i - 1].text);
}

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
      {expired ? <p className="cx-s">This audio has expired. Ask for the workout again to record it again.</p> : (
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

/** "Thinking…" with a running clock and the coach's latest steps. */
function Working({ steps }: { steps: Step[] }) {
  const [since] = useState(() => Date.now());
  const [, tick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  steps = collapsed(steps);
  const shown = steps.slice(-SHOWN_STEPS);
  return (
    <div className="m a thinking" aria-live="polite">
      <p className="think-head">Working… <span className="clock">{seconds(since)}</span></p>
      {shown.length > 0 && (
        <ul className="steps">
          {steps.length > shown.length && <li className="more">{steps.length - shown.length} earlier steps</li>}
          {shown.map((s, i) => (
            <li key={steps.length - shown.length + i} className={i === shown.length - 1 ? "now" : s.failed ? "bad" : ""}>
              {s.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Chat({ lines, working, steps = [], error, noKey, onSend, onOpenKeys }: Props) {
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [lines.length, working, steps.length]);

  async function send() {
    const line = text.trim();
    if (!line || working) return;
    setText("");
    if ((await onSend(line)) === false) setText((t) => t || line);
  }

  return (
    <main className="chat" aria-label="Chat">
      <div className="chat-log" role="log" aria-live="polite">
        {lines.length === 0 && !working && (
          <p className="m a">Hi. Tell me what workout you'd like: how long, what for, what you have with you. I'll check in, then write it.</p>
        )}
        {lines.map((l, i) => l.audio ? <AudioLine key={i} audio={l.audio} /> : l.role === "user" ? (
          <p key={i} className="m u">{l.text}</p>
        ) : (
          <div key={i} className="m a md">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{l.text}</ReactMarkdown>
          </div>
        ))}
        {working && <Working steps={steps} />}
        <div ref={end} />
      </div>
      {error && (
        <div className="chat-error" role="alert">
          <p>{error}</p>
          {noKey && <button type="button" className="go alt" onClick={onOpenKeys}>Open Keys</button>}
        </div>
      )}
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <label className="sr" htmlFor="chat-box">Message</label>
        <textarea id="chat-box" rows={2} value={text} disabled={working}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send();
            }
          }} />
        <button type="submit" className="go alt" disabled={working || !text.trim()}>Send</button>
      </form>
    </main>
  );
}
