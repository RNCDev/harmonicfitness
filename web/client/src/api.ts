// The server's JSON API and a job's event stream.
import { useCallback, useEffect, useRef, useState } from "react";
import type { JobArgs, Options } from "./sentence/model";

/** The product's name, in one place on this side. */
export const APP_NAME = "Working Title";

export class NotSignedIn extends Error {}
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export type Me = { app_name: string; email: string };
export type ContextFile = { path: string; version: number; updated_at: string };
export type DeviceLink = { url: string; expires_at: string };
export type Stage = { stage: string; [field: string]: unknown };
export type BriefResult = { brief_md: string; stem: string };
export type JobState = "queued" | "running" | "done" | "failed";
export type JobView = {
  id: number;
  state: JobState;
  error: string | null;
  stages: Stage[];
  result: BriefResult | null;
};

async function call<T>(method: "GET" | "POST", url: string, body?: unknown): Promise<T> {
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
  options: () => call<Options>("GET", "/api/options"),
  context: () => call<ContextFile[]>("GET", "/api/context"),
  deviceLink: () => call<DeviceLink>("POST", "/api/device-link"),
  signOut: () => call<void>("POST", "/api/sign-out"),
  startJob: (args: JobArgs) => call<{ id: number }>("POST", "/api/jobs", args),
  job: (id: number) =>
    call<{ id: number; state: JobState; error: string | null; result: BriefResult | null }>(
      "GET", `/api/jobs/${id}`),
};

function plainError(e: unknown): string {
  if (e instanceof ApiError && e.status === 429) return "You already have jobs waiting. Give them a minute.";
  if (e instanceof ApiError) return e.message;
  return "Couldn't reach the server.";
}

/** One job at a time: start it, follow its events, then read its result. */
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
      setJob((v) => (v && v.id === id ? { ...v, state: j.state, error: j.error,
        result: j.state === "done" ? j.result : null } : v));
    } catch (e) {
      if (e instanceof NotSignedIn) return onSignedOut();
      setJob((v) => (v && v.id === id ? { ...v, state: "failed", error: plainError(e) } : v));
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

  const start = useCallback(async (args: JobArgs) => {
    stop();
    setJob({ id: 0, state: "queued", error: null, stages: [], result: null });
    try {
      const { id } = await api.startJob(args);
      setJob({ id, state: "queued", error: null, stages: [], result: null });
      follow(id);
    } catch (e) {
      if (e instanceof NotSignedIn) return onSignedOut();
      setJob({ id: 0, state: "failed", error: plainError(e), stages: [], result: null });
    }
  }, [follow, onSignedOut, stop]);

  return { job, start, stop };
}
