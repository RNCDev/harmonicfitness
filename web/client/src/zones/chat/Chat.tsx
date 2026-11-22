// The chat: the lines so far (the coach's as Markdown), what the coach is doing while a turn runs,
// and the box to write in.
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatLine, Later, Offer, Plan, StartInfo } from "../../lib/api";
import { clockAt } from "../../lib/format";
import { MOST_PHOTOS, shrink } from "../../lib/photos";
import { readDraft, keepDraft } from "../../lib/draft";
import { keepLineBreaks } from "../../lib/lines";
import type { Step } from "../../lib/steps";
import { AudioFile } from "../../ui/AudioFile";
import { Button } from "../../ui/Button";
import { ConfirmInline } from "../../ui/ConfirmInline";
import { Icon } from "../../ui/icons";
import { Notice } from "../../ui/Notice";
import { Starter } from "../Starter";
import { LaterOffer, RecordOffer, Scheduled } from "./Offers";
import { Working } from "./Working";

/** What the first screen shows before any line: the conversation waiting from earlier today, and the request. */
type FirstScreen = {
  /** Today's conversation waiting on the listener, and opening it. */
  waiting?: { offer: boolean; at: string | null } | null;
  onResume?: () => void;
  /** What the request is filled in with (null until it arrives); `starting`: show it anyway, blanks rolling in. */
  start?: StartInfo | null;
  starting?: boolean;
  onCoach?: (slug: string) => void;
  coachError?: string | null;
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
  /** The last refusal was for want of minutes, and where to get more. */
  noMinutes?: boolean;
  onGetMinutes?: () => void;
  /** Resolves false when the line was refused, so the box gets its text back. `startAt`: the starter's picked time;
   * `photos`: the kit photos the line carries, each a shrunk JPEG in base64. */
  onSend: (line: string, startAt?: string, photos?: string[]) => Promise<boolean> | void;
  /** Stops the running turn. */
  onStop?: () => void;
  /** The coach shown above the conversation. */
  coachBar?: { name: string; service: string } | null;
  first?: FirstScreen;
  offers?: Offers;
};

export function Chat({ lines, working, steps = [], plan = null, error, noMinutes = false, onGetMinutes, onSend,
  onStop, coachBar = null, first = {}, offers = {} }: Props) {
  const { waiting = null, onResume, start = null, starting = false, onCoach, coachError,
    startError = null, onRetryStart } = first;
  const { offer = null, onRecord, later = null, scheduled = false, onSchedule, onCancel } = offers;
  const [text, setText] = useState(readDraft);
  /** Kit photos waiting to go with the next line: each one's preview (this tab only) and what's sent. */
  const [photos, setPhotos] = useState<{ preview: string; data: string }[]>([]);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null);
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

  async function addPhotos(files: FileList | null) {
    setPhotoError(null);
    const room = MOST_PHOTOS - photos.length;
    const picked = Array.from(files ?? []).filter((f) => f.type.startsWith("image/"));
    if (picked.length > room) setPhotoError(`Up to ${MOST_PHOTOS} photos in one message.`);
    const added: { preview: string; data: string }[] = [];
    for (const file of picked.slice(0, Math.max(room, 0))) {
      try {
        added.push({ preview: URL.createObjectURL(file), data: await shrink(file) });
      } catch {
        setPhotoError("That photo couldn't be read. Try another.");
      }
    }
    setPhotos((p) => [...p, ...added].slice(0, MOST_PHOTOS));
  }

  function dropPhoto(i: number) {
    setPhotos((p) => {
      URL.revokeObjectURL(p[i].preview);
      return p.filter((_, j) => j !== i);
    });
  }

  async function send() {
    const sent = photos;
    const line = text.trim() || (sent.length ? "Here are photos of my kit." : "");
    if (!line || working) return;
    setText("");
    setPhotos([]);
    setPhotoError(null);
    const ok = sent.length ? await onSend(line, undefined, sent.map((p) => p.data)) : await onSend(line);
    if (ok === false) {
      setText((t) => t || text.trim());
      setPhotos(sent);
    } else {
      sent.forEach((p) => URL.revokeObjectURL(p.preview));
    }
  }

  const at = clockAt(waiting?.at);
  return (
    <main className={lines.length > 0 || working ? "chat talk" : "chat"} aria-label="Chat">
      {coachBar && lines.length > 0 && (
        <div className="coachbar"><b>{coachBar.name}</b><small>{coachBar.service}</small></div>
      )}
      <div className="chat-log" ref={log} role="log" aria-live="polite">
        {lines.length === 0 && !working && waiting && onResume && (
          <Button variant="bare" className="resume" onClick={onResume}>
            <span className="resume-h">Pick up where you left off</span>
            <span className="resume-s">{waiting.offer ? "Your workout is ready to record" : "Your coach asked you something"}{at && ` at ${at}`}.</span>
            <span className="resume-go" aria-hidden="true">→</span>
          </Button>
        )}
        {lines.length === 0 && !working && (start || starting) && (
          <Starter info={start} onStart={onSend} onCoach={onCoach} coachError={coachError}
            loadError={startError} onRetry={onRetryStart} />
        )}
        {lines.map((l, i) => l.audio ? <div key={i} className="m a audio"><AudioFile audio={l.audio} titled /></div>
          : l.role === "user" ? (
            <p key={i} className="m u">
              {l.photos ? <span className="m-photos"><Icon name="camera" size={14} />
                {l.photos === 1 ? "1 photo" : `${l.photos} photos`}</span> : null}
              {l.text}
            </p>
          ) : (
            <div key={i} className="m a md">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{keepLineBreaks(l.text)}</ReactMarkdown>
            </div>
          ))}
        {offer && !working && <RecordOffer offer={offer} onRecord={onRecord} />}
        {later && !later.done && !later.due && new Date(later.at).getTime() > Date.now() && !offer
          && !working && !scheduled && <LaterOffer later={later} onSchedule={onSchedule} />}
        {later && scheduled && <Scheduled later={later} onCancel={onCancel} />}
        {working && <Working steps={steps} plan={plan} stopping={stopping} />}
      </div>
      {error && (
        <div className="chat-error">
          <Notice tone="error">{error}</Notice>
          {noMinutes && onGetMinutes && <Button variant="outline" onClick={onGetMinutes}>Get minutes</Button>}
        </div>
      )}
      {(photos.length > 0 || photoError) && (
        <div className="chat-photos">
          {photos.length > 0 && (
            <ul aria-label="Photos to send">
              {photos.map((p, i) => (
                <li key={p.preview}>
                  <img src={p.preview} alt={`Photo ${i + 1}`} />
                  <Button variant="bare" className="photo-drop" aria-label={`Remove photo ${i + 1}`} onClick={() => dropPhoto(i)}>
                    <Icon name="close" size={12} weight={2.25} />
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {photoError ? <Notice tone="error">{photoError}</Notice>
            : <small>Photos go to the AI that writes your workouts to be read, and aren't kept here.</small>}
        </div>
      )}
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input ref={picker} type="file" accept="image/*" multiple hidden aria-hidden="true" tabIndex={-1}
          onChange={(e) => { addPhotos(e.target.files); e.target.value = ""; }} />
        <Button variant="bare" className="photo-add" aria-label="Add photos of your kit"
          disabled={working || scheduled || photos.length >= MOST_PHOTOS}
          onClick={() => picker.current?.click()}>
          <Icon name="camera" size={20} />
        </Button>
        <label className="sr" htmlFor="chat-box">Message</label>
        <textarea id="chat-box" ref={box} rows={1} value={text}
          placeholder={scheduled ? "Scheduled: cancel it to change anything"
            : lines.length === 0 ? "Or describe the workout you want in your own words" : "Reply to your coach"}
          disabled={working || scheduled}
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
        <Button type="submit" variant="primary"
          disabled={working || scheduled || (!text.trim() && photos.length === 0)}>Send</Button>
      </form>
    </main>
  );
}
