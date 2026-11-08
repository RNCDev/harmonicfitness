// The conversation with the agent: load the latest, start a new one or continue it, follow each turn's job.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, NotSignedIn, plainError, useJob, type Conversation, type ErrorCode } from "./api";
import { localDate, localNow } from "./when";

/** Waits before each new try at reading the conversation after a turn (about ten seconds in all). */
const RELOAD_DELAYS = [1000, 3000, 6000];
/** How often a scheduled conversation is read again, to see its writing begin. */
const SCHEDULED_EVERY = 30000;

const when = () => {
  const d = new Date();
  return { today: localDate(d), now: localNow(d) };
};

/** True when a conversation last changed on an earlier local day than today: a new message starts a new
 * conversation. A working one is always current. */
export function isHistory(c: Conversation | null, today: Date = new Date()): boolean {
  if (!c || c.state === "working" || c.state === "scheduled" || !c.updated_at) return false;
  const at = new Date(c.updated_at);
  return !Number.isNaN(at.getTime()) && localDate(at) < localDate(today);
}

/** True when a conversation is worth picking up again: it's still working, or it's from today, hasn't failed, has
 * no workout recorded yet, and waits on the listener (a Record offer, or the coach spoke last). Only a working one
 * reopens on its own; the rest are offered on the first screen. */
export function resumable(c: Conversation, today: Date = new Date()): boolean {
  if (c.state === "working" || c.state === "scheduled") return true;
  if (c.state === "failed" || isHistory(c, today) || c.lines.some((l) => l.audio)) return false;
  return !!c.offer || c.lines[c.lines.length - 1]?.role === "agent";
}

/** A refusal Settings answers: no language-model key, or one its service refused. */
const needsKeys = (code: ErrorCode | null | undefined) => code === "no_model_key" || code === "key_refused";

export function useConversation() {
  const [conv, setConv] = useState<Conversation | null>(null);
  /** Today's conversation waiting on the listener, offered on the first screen rather than reopened. */
  const [waiting, setWaiting] = useState<Conversation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [noKey, setNoKey] = useState(false);
  const [posting, setPosting] = useState(false);
  const { job, watch, stop } = useJob();
  const watched = useRef(0);

  const follow = useCallback((jobId: number) => {
    watched.current = jobId;
    watch(jobId);
  }, [watch]);

  const fail = useCallback((e: unknown) => {
    if (e instanceof NotSignedIn) return;   // api.ts has sent the page to sign-in
    setNoKey(e instanceof ApiError && needsKeys(e.code));
    setError(plainError(e));
  }, []);

  const adopt = useCallback((c: Conversation | undefined) => {
    setConv(c ?? null);
    if (c?.state === "working" && c.job_id && c.job_id !== watched.current) follow(c.job_id);
  }, [follow]);

  // The page opens on the first screen, except while a conversation is still working (a reload keeps its steps
  // and Stop). One from today waiting on the listener (the coach's questions, or a Record offer) is offered there.
  useEffect(() => {
    api.latestConversation().then((c) => {
      // a scheduled workout opens on its own, waiting, written, or failed: the listener came back for it
      if (c?.state === "working" || c?.state === "scheduled" || (c?.later?.due && !isHistory(c))) adopt(c);
      else setWaiting(c && resumable(c) ? c : null);
    }, fail);
  }, [adopt, fail]);

  /** "Pick up where you left off": open the conversation that was waiting. */
  const resume = useCallback(() => {
    if (!waiting) return;
    adopt(waiting);
    setWaiting(null);
  }, [waiting, adopt]);

  // A turn's job ended: read the conversation again, a few times if it won't load. If it never
  // does, stop showing "working" so the person can write again.
  const id = conv?.id;
  useEffect(() => {
    if (!job || id === undefined) return;
    if (job.state === "failed" && job.error) {
      setError(plainError(new ApiError(0, job.error)));
      setNoKey(needsKeys(job.code));
    }
    if (job.state !== "done" && job.state !== "failed") return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const attempt = (n: number) => {
      api.conversation(id).then((c) => { if (live) setConv(c); }, (e) => {
        if (!live) return;
        if (e instanceof NotSignedIn) return;
        if (n < RELOAD_DELAYS.length) {
          timer = setTimeout(() => attempt(n + 1), RELOAD_DELAYS[n]);
          return;
        }
        setConv((c) => (c && c.state === "working" ? { ...c, state: "idle", job_id: null } : c));
        setError(plainError(e));
      });
    };
    attempt(0);
    return () => { live = false; clearTimeout(timer); };
  }, [job?.id, job?.state]); // eslint-disable-line react-hooks/exhaustive-deps

  // A scheduled conversation is read again now and then: once its writing begins, it's working, and followed.
  const scheduled = conv?.state === "scheduled";
  useEffect(() => {
    if (!scheduled || id === undefined) return;
    const t = setInterval(() => {
      api.conversation(id).then((c) => { if (c.state !== "scheduled") adopt(c); }, () => {
        /* read again at the next tick; a lost session has gone to sign-in */
      });
    }, SCHEDULED_EVERY);
    return () => clearInterval(t);
  }, [scheduled, id, adopt]);

  const turn = useCallback(async (run: () => Promise<{ job_id: number }>, show: (c: Conversation) => Conversation) => {
    setError(null);
    setNoKey(false);
    setPosting(true);
    try {
      const { job_id } = await run();
      setConv((c) => (c ? show(c) : c));
      follow(job_id);
      return true;
    } catch (e) {
      fail(e);
      return false;
    } finally {
      setPosting(false);
    }
  }, [fail, follow]);

  // a job counts only while its chat is open: Stop closes the chat before the job's last word arrives
  const working = posting || conv?.state === "working" || (!!conv && (job?.state === "queued" || job?.state === "running"));

  /** A new conversation, whatever is open; `startAt`, for a workout at a time the listener picked. */
  const start = useCallback(async (line: string, startAt?: string) => {
    setError(null);
    setNoKey(false);
    setPosting(true);
    try {
      const { id: cid, job_id } = await api.startConversation(line, when(), startAt);
      setWaiting(null);
      setConv({ id: cid, state: "working", job_id, lines: [{ role: "user", text: line }],
        updated_at: new Date().toISOString() });
      follow(job_id);
      return true;
    } catch (e) {
      fail(e);
      return false;
    } finally {
      setPosting(false);
    }
  }, [fail, follow]);

  const history = isHistory(conv);

  /** The chat's text box: the open conversation goes on; with none, or one from an earlier day, a new one. */
  const send = useCallback(async (line: string, startAt?: string) => {
    if (!conv || history) return start(line, startAt);
    return turn(() => api.sendMessage(conv.id, line, when()), (c) => ({
      ...c, state: "working", lines: [...c.lines, { role: "user", text: line }],
      updated_at: new Date().toISOString(),
    }));
  }, [conv, history, start, turn]);

  /** The Record button: approve the priced recording. */
  const record = useCallback(async () => {
    if (!conv) return false;
    return turn(() => api.record(conv.id, when()), (c) => ({
      ...c, state: "working", offer: null, lines: [...c.lines, { role: "user", text: "Yes, record it." }],
      updated_at: new Date().toISOString(),
    }));
  }, [conv, turn]);

  /** Schedule it: the writing is queued for fifteen minutes before the workout's time. */
  const schedule = useCallback(async () => {
    if (!conv) return false;
    setError(null);
    setPosting(true);
    try {
      await api.schedule(conv.id, when());
      setConv(await api.conversation(conv.id));
      return true;
    } catch (e) {
      fail(e);
      return false;
    } finally {
      setPosting(false);
    }
  }, [conv, fail]);

  /** Cancel a scheduled workout before its writing begins. */
  const cancel = useCallback(async () => {
    if (!conv) return false;
    setError(null);
    try {
      setConv(await api.cancel(conv.id));
      return true;
    } catch (e) {
      fail(e);
      return false;
    }
  }, [conv, fail]);

  /** The Stop button: the running turn's work ends within a few seconds, and the chat with it (the server
   * keeps it as stopped, so it isn't offered again); the page goes back to the first screen. If the stop
   * can't be sent, the chat stays open with the error. */
  const halt = useCallback(async () => {
    if (!conv) return;
    try {
      await api.stop(conv.id);
    } catch (e) {
      fail(e);
      return;
    }
    stop();
    setConv(null);
    setWaiting(null);
    setPosting(false);
    setError(null);
    setNoKey(false);
  }, [conv, fail, stop]);

  /** "New chat": clear the page; the next message starts a new conversation. */
  const reset = useCallback(() => {
    if (working) return;
    stop();
    setConv(null);
    setError(null);
    setNoKey(false);
  }, [working, stop]);

  return { conv, history, working, error, noKey, send, record, schedule, cancel, halt, reset, job, stop, waiting, resume };
}
