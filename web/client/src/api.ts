// The server's JSON API and a job's event stream.
import { useCallback, useEffect, useRef, useState } from "react";
import type { Options } from "./sentence/model";

/** The product's name, in one place on this side. */
export const APP_NAME = "HarmonicFitness";

export class NotSignedIn extends Error {}
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export type Me = { app_name: string; username: string; has_password: boolean; version: string };
export type AuthInfo = { app_name: string; registration: boolean; version: string };
export type ContextFile = { path: string; version: number; updated_at: string };
export type DeviceLink = { url: string; expires_at: string };
export type KeyState = {
  service: string; name: string; key_page: string; set: boolean; updated_at: string | null;
  kind: "voice" | "model";
};
export type Stage = { stage: string; [field: string]: unknown };
export type JobState = "queued" | "running" | "done" | "failed";
export type JobView = {
  id: number;
  state: JobState;
  error: string | null;
  stages: Stage[];
};

export type ChatLine = { role: "user" | "agent"; text: string };
export type QuestionOption = { label: string; description?: string | null; recommended?: boolean };
export type AskedQuestion = {
  id: string; prompt: string; options: QuestionOption[]; multi: boolean; other: boolean;
};
export type OpenQuestion = { questions: AskedQuestion[]; tool_call_id: string };
export type PlanRow = { block: string; movements: string[]; dose: string; seconds: number };
export type Plan = {
  format: string; equipment: string; rows: PlanRow[]; left_out: string; total_seconds: number;
};
export type Conversation = {
  id: number; state: "working" | "waiting" | "idle" | "failed"; job_id: number | null;
  lines: ChatLine[]; question: OpenQuestion | null; plan: Plan | null;
  /** When it last changed (ISO); null only on a server from before it was sent. */
  updated_at: string | null;
};
export type AnswerValues = Record<string, string[] | string>;
export type When = { today: string; now: string };

async function call<T>(method: "GET" | "POST" | "PUT" | "DELETE", url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (r.status === 401) throw new NotSignedIn("not signed in");
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const j = await r.json();
      if (typeof j?.detail === "string") detail = j.detail;
    } catch {
      /* no JSON body */
    }
    throw new ApiError(r.status, detail);
  }
  return r.status === 204 ? (undefined as T) : ((await r.json()) as T);
}

export const api = {
  me: () => call<Me>("GET", "/api/me"),
  authInfo: () => call<AuthInfo>("GET", "/api/auth"),
  signIn: (username: string, password: string) =>
    call<void>("POST", "/api/sign-in", { username, password }),
  register: (username: string, password: string) =>
    call<void>("POST", "/api/register", { username, password }),
  setPassword: (current: string | null, next: string) =>
    call<void>("POST", "/api/password", current === null ? { new: next } : { current, new: next }),
  options: () => call<Options>("GET", "/api/options"),
  context: () => call<ContextFile[]>("GET", "/api/context"),
  deviceLink: () => call<DeviceLink>("POST", "/api/device-link"),
  keys: () => call<KeyState[]>("GET", "/api/keys"),
  setKey: (service: string, key: string) =>
    call<void>("PUT", `/api/keys/${encodeURIComponent(service)}`, { key }),
  deleteKey: (service: string) =>
    call<void>("DELETE", `/api/keys/${encodeURIComponent(service)}`),
  startConversation: (line: string, w: When) =>
    call<{ id: number; job_id: number }>("POST", "/api/conversations", { line, ...w }),
  latestConversation: () => call<Conversation | undefined>("GET", "/api/conversations/latest"),
  conversation: (id: number) => call<Conversation>("GET", `/api/conversations/${id}`),
  sendMessage: (id: number, line: string, w: When) =>
    call<{ job_id: number }>("POST", `/api/conversations/${id}/messages`, { line, ...w }),
  answer: (id: number, tool_call_id: string, values: AnswerValues, w: When) =>
    call<{ job_id: number }>("POST", `/api/conversations/${id}/answer`, { tool_call_id, values, ...w }),
  signOut: () => call<void>("POST", "/api/sign-out"),
  latestJob: () => call<{ id: number; kind: string; state: JobState } | undefined>("GET", "/api/jobs/latest"),
  job: (id: number) =>
    call<{ id: number; state: JobState; error: string | null }>(
      "GET", `/api/jobs/${id}`),
};

/** A message for a person, from a failed call. */
export function plainError(e: unknown): string {
  if (e instanceof ApiError && e.status === 422) return "Check what you typed and try again.";
  if (e instanceof ApiError) return e.message;
  return "Couldn't reach the server.";
}

function jobError(e: unknown): string {
  if (e instanceof ApiError && e.status === 429) return "You already have jobs waiting. Give them a minute.";
  return plainError(e);
}

/** Seconds to wait before following a dropped stream again: 2, then 5, then every 10. */
export const REFOLLOW_MS = [2000, 5000, 10000];

/** One job at a time: follow its events, then read how it ended. A stream that closes while the job
 * still works is followed again (2 s, 5 s, then every 10 s) until the job ends or the user signs out. */
export function useJob(onSignedOut: () => void) {
  const [job, setJob] = useState<JobView | null>(null);
  const source = useRef<EventSource | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tries = useRef(0);
  const seen = useRef<{ id: number; ids: Set<string> }>({ id: 0, ids: new Set() });

  const stop = useCallback(() => {
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
    source.current?.close();
    source.current = null;
  }, []);
  useEffect(() => stop, [stop]);

  const followRef = useRef<(id: number) => void>(() => {});

  /** Read how the job stands; true if it still works. */
  const finish = useCallback(async (id: number): Promise<boolean> => {
    try {
      const j = await api.job(id);
      setJob((v) => (v && v.id === id ? { ...v, state: j.state, error: j.error } : v));
      return j.state === "queued" || j.state === "running";
    } catch (e) {
      if (e instanceof NotSignedIn) {
        stop();
        onSignedOut();
        return false;
      }
      setJob((v) => (v && v.id === id ? { ...v, state: "failed", error: jobError(e) } : v));
      return false;
    }
  }, [onSignedOut, stop]);

  const follow = useCallback((id: number) => {
    stop();
    if (seen.current.id !== id) seen.current = { id, ids: new Set() };
    const ids = seen.current.ids;
    const es = new EventSource(`/api/jobs/${id}/events`);
    source.current = es;
    es.onmessage = (e) => {
      tries.current = 0;
      if (e.lastEventId && ids.has(e.lastEventId)) return;
      ids.add(e.lastEventId);
      let body: Stage;
      try {
        body = JSON.parse(e.data);
      } catch {
        return;
      }
      setJob((v) => (v && v.id === id ? { ...v, state: "running", stages: [...v.stages, body] } : v));
    };
    es.addEventListener("state", (e) => {
      es.close();
      if (source.current === es) source.current = null;
      let end: { state?: JobState; error?: string | null } = {};
      try {
        end = JSON.parse((e as MessageEvent).data);
      } catch {
        /* read it from the job instead */
      }
      if (end.state === "failed") {
        setJob((v) => (v && v.id === id ? { ...v, state: "failed", error: end.error ?? null } : v));
      } else {
        void finish(id);
      }
    });
    es.onerror = () => {
      // The browser reconnects on its own; a refused or dropped stream is closed: read the job and,
      // if it still works, follow it again after a wait.
      if (es.readyState !== EventSource.CLOSED) return;
      if (source.current === es) source.current = null;
      void finish(id).then((working) => {
        if (!working || source.current !== null || timer.current !== null) return;
        const wait = REFOLLOW_MS[Math.min(tries.current, REFOLLOW_MS.length - 1)];
        tries.current += 1;
        timer.current = setTimeout(() => {
          timer.current = null;
          followRef.current(id);
        }, wait);
      });
    };
  }, [finish, stop]);
  followRef.current = follow;

  /** Follow a job another call started (a conversation's turn, or one found on load). */
  const watch = useCallback((id: number) => {
    tries.current = 0;
    setJob({ id, state: "queued", error: null, stages: [] });
    follow(id);
  }, [follow]);

  return { job, watch, stop };
}
