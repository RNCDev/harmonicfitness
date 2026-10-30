// The server's JSON API and a job's event stream.
import { useCallback, useEffect, useRef, useState } from "react";

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
export type DeviceLink = { url: string; expires_at: string };
export type KeyState = {
  service: string; name: string; key_page: string; set: boolean; updated_at: string | null;
  kind: "voice" | "model";
  /** On a model row: whether it's the one the listener chose to write their workouts. */
  writer?: boolean;
};
export type Stage = { stage: string; [field: string]: unknown };
export type JobState = "queued" | "running" | "done" | "failed";
export type JobView = {
  id: number;
  state: JobState;
  error: string | null;
  stages: Stage[];
};

export type Audio = { id: string; name: string; expires_at: string };
export type ChatLine = { role: "user" | "agent"; text: string; audio?: Audio };
export type Offer = { name: string; coach: string; chars: number; usd: number; service: string; design?: boolean };
export type Conversation = {
  id: number; state: "working" | "waiting" | "idle" | "failed"; job_id: number | null;
  lines: ChatLine[];
  /** A priced recording waiting for the Record button. */
  offer?: Offer | null;
  /** When it last changed (ISO); null only on a server from before it was sent. */
  updated_at: string | null;
};
export type When = { today: string; now: string };
/** What the first screen's sentence is filled in with (GET /api/start). */
export type StartCoach = { slug: string; name: string; first: string; service: string; service_name: string;
  ready: boolean; own: boolean; current: boolean };
export type StartKit = { id: string; label: string; preset: boolean };
export type StartLimit = { area: string; side: string | null; level: "delicate" | "off-limits" };
export type StartInfo = { coaches: StartCoach[]; kits: StartKit[]; minutes: number; limits: StartLimit[];
  suggest: { goal: string; target?: string | null; reason: string } | null; setup_quick: boolean };

/** A call to the server. An empty answer (a 201 from register, a 204) is no body, whatever its status. */
export async function call<T>(method: "GET" | "POST" | "PUT" | "DELETE", url: string, body?: unknown): Promise<T> {
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
  const text = await r.text();
  return (text.trim() === "" ? undefined : JSON.parse(text)) as T;
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
  deviceLink: () => call<DeviceLink>("POST", "/api/device-link"),
  keys: () => call<KeyState[]>("GET", "/api/keys"),
  setKey: (service: string, key: string) =>
    call<void>("PUT", `/api/keys/${encodeURIComponent(service)}`, { key }),
  setWriter: (service: string) => call<void>("PUT", "/api/writer", { service }),
  deleteKey: (service: string) =>
    call<void>("DELETE", `/api/keys/${encodeURIComponent(service)}`),
  startConversation: (line: string, w: When) =>
    call<{ id: number; job_id: number }>("POST", "/api/conversations", { line, ...w }),
  latestConversation: () => call<Conversation | undefined>("GET", "/api/conversations/latest"),
  conversation: (id: number) => call<Conversation>("GET", `/api/conversations/${id}`),
  sendMessage: (id: number, line: string, w: When) =>
    call<{ job_id: number }>("POST", `/api/conversations/${id}/messages`, { line, ...w }),
  record: (id: number, w: When) => call<{ job_id: number }>("POST", `/api/conversations/${id}/record`, w),
  stop: (id: number) => call<{ stopping: boolean }>("POST", `/api/conversations/${id}/stop`),
  start: () => call<StartInfo>("GET", "/api/start"),
  signOut: () => call<void>("POST", "/api/sign-out"),
  deleteAccount: (password: string) => call<void>("POST", "/api/account/delete", { password }),
  importFolder: async (zip: Blob): Promise<{ imported: number; left_out: number }> => {
    const r = await fetch("/api/import", {
      method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/zip" }, body: zip,
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
    return r.json();
  },
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

/** One job at a time: follow its events, then read how it ended. */
export function useJob(onSignedOut: () => void) {
  const [job, setJob] = useState<JobView | null>(null);
  const source = useRef<EventSource | null>(null);

  const stop = useCallback(() => {
    source.current?.close();
    source.current = null;
  }, []);
  useEffect(() => stop, [stop]);

  const finish = useCallback(async (id: number) => {
    try {
      const j = await api.job(id);
      setJob((v) => (v && v.id === id ? { ...v, state: j.state, error: j.error } : v));
    } catch (e) {
      if (e instanceof NotSignedIn) return onSignedOut();
      setJob((v) => (v && v.id === id ? { ...v, state: "failed", error: jobError(e) } : v));
    }
  }, [onSignedOut]);

  const follow = useCallback((id: number) => {
    stop();
    const es = new EventSource(`/api/jobs/${id}/events`);
    source.current = es;
    const seen = new Set<string>();
    es.onmessage = (e) => {
      if (e.lastEventId && seen.has(e.lastEventId)) return;
      seen.add(e.lastEventId);
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
      // The browser reconnects on its own; a refused stream (signed out, gone) is closed: read the job.
      if (es.readyState === EventSource.CLOSED) {
        if (source.current === es) source.current = null;
        void finish(id);
      }
    };
  }, [finish, stop]);

  /** Follow a job another call started (a conversation's turn). */
  const watch = useCallback((id: number) => {
    setJob({ id, state: "queued", error: null, stages: [] });
    follow(id);
  }, [follow]);

  return { job, watch, stop };
}
