// The server's JSON API and a job's event stream.
import { useCallback, useEffect, useRef, useState } from "react";
import { SAID } from "./messages";

/** The product's name, in one place on this side. */
export const APP_NAME = "HarmonicFitness";

export class NotSignedIn extends Error {}
/** What the page offers for a refusal or a failed job, named by the server beside its words (0.71.0): the page reads
 * the code, never the wording. */
export type ErrorCode = "no_minutes";
/** A refusal, in the server's words; `field` names the form's box it's about, and `code` what the page can offer for
 * it, when the server says. */
export class ApiError extends Error {
  constructor(public status: number, message: string, public field?: string, public code?: ErrorCode) {
    super(message);
  }
}

export type Me = { app_name: string; username: string; has_password: boolean; version: string;
  /** The animated background chosen in Settings; absent from a server older than 0.33.0. */
  sky?: "flow" | "field" | "waves" | "bloom" | "woven" | "garden";
  /** Record without asking (Settings); absent from a server older than 0.48.0. */
  auto_record?: boolean;
  /** Sign-in goes through Clerk here (no password to choose or change), and whether this account is one of
   * Clerk's; absent from a server older than 0.85.0, as the two below are. */
  clerk?: boolean; clerk_linked?: boolean;
  /** The listener's balance of minutes. */
  minutes?: number | null;
  /** One of the accounts HARMONICFITNESS_ADMINS names: the Admin page shows (the server checks again). */
  admin?: boolean };
/** The listener's level (novice when none is set), and the three to choose from as a listener would say each. */
export type LevelState = { level: Level; set: boolean; choices: { level: Level; said: string }[] };
export type Level = "novice" | "experienced" | "advanced";
/** What the sign-in page offers. `clerk`: the Clerk instance's publishable key where sign-in goes through Clerk,
 * else null (or absent) and the page shows its own username and password form. */
type AuthInfo = { app_name: string; registration: boolean; version: string; clerk?: string | null };
/** A pack of minutes for sale, and a line of what happened to the balance (bought, used, given back). */
export type Pack = { id: string; minutes: number; cents: number };
type MinutesLine = { at: string; kind: string; minutes: number; what: string };
/** `can_buy`: whether packs are sold here. */
export type MinutesState = { minutes: number; can_buy: boolean; packs: Pack[]; history: MinutesLine[] };
export type DeviceLink = { url: string; expires_at: string };
export type Stage = { stage: string; [field: string]: unknown };
type JobState = "queued" | "running" | "done" | "failed";
type JobView = {
  id: number;
  state: JobState;
  error: string | null;
  /** What the page can offer for the error (Get minutes), when there is something. */
  code?: ErrorCode | null;
  stages: Stage[];
};

/** An MP3 the site keeps: a workout's has no expiry (`expires_at` null; three newer ones replace it), and `gone`
 *  marks one a conversation still names that's no longer kept. */
export type Audio = { id: string; name: string; expires_at: string | null; gone?: boolean };
/** `photos`: how many kit photos the listener's line carried; the photos themselves are never kept. */
export type ChatLine = { role: "user" | "agent"; text: string; audio?: Audio; photos?: number };
/** The plan the engine worked out from the draft's own segments (`get plan`), so its times add up. */
type PlanRow = { what: string; kind: "movement" | "rest" | "talk"; segments: number; seconds: number };
export type Plan = { rows: PlanRow[]; seconds: number };
/** `first`: no script has gone to a voice service yet, so the card says where it goes. `minutes` is the workout's
 * length and `charge` what recording it takes from the balance (0 for the free second take). */
export type Offer = { name: string; coach: string; service: string; plan?: Plan | null; first?: boolean;
  minutes?: number; charge?: number };
/** A workout for later: its time (UTC and the listener's), and once the check-in is done, its length; `due` once
 * it's scheduled (when the writing starts). */
export type Later = { at: string; local: string; due?: string; done?: boolean; minutes?: number; coach?: string };
export type Conversation = {
  id: number; state: "working" | "waiting" | "idle" | "failed" | "scheduled"; job_id: number | null;
  later?: Later | null;
  lines: ChatLine[];
  /** A priced recording waiting for the Record button. */
  offer?: Offer | null;
  /** When it last changed (ISO); null only on a server from before it was sent. */
  updated_at: string | null;
};
export type When = { today: string; now: string };
/** What the first screen's sentence is filled in with (GET /api/start). */
export type StartCoach = { slug: string; name: string; first: string; service: string; service_name: string;
  ready: boolean; own: boolean; current: boolean;
  /** For the gallery: how the coach sounds and talks, and whether a sample ships. */
  description?: string | null; tone?: string | null; sample?: boolean;
  /** Who makes the voices, where the service is a go-between: OpenRouter's "ElevenLabs". */
  powered_by?: string | null;
  /** A stock voice heard as a woman's ("f") or a man's ("m"), where its service knows it. */
  gender?: "f" | "m" | null };
/** The Admin page's books (GET /api/admin/books): dollars throughout; null where a cost isn't tracked. */
export type BooksDay = { day: string; sales: number; refunds: number; fees: number; write: number | null;
  voice: number | null; unattributed: number | null; fly: number | null };
export type Books = { days: number; from: string; to: string;
  money: { sales: number; refunds: number; net: number; fees: number; write: number | null; voice: number | null;
    voice_estimated: boolean; unattributed: number | null; fly: number | null; profit: number; margin: number | null;
    missing: string[]; costs_since: string | null; checked_since: string | null };
  fly: { monthly: number | null; lines: { what: string; monthly: number }[]; left_out: string[]; why: string | null };
  daily: BooksDay[];
  units: { packs: { id: string; minutes: number; price: number; per_minute: number; after_fee: number }[];
    minutes_sold: number; sales: number; per_minute_sold: number | null; minutes_recorded: number; recordings: number;
    minutes_given: number; cost_per_minute: number | null; write_per_recording: number | null;
    voice_per_minute: number | null };
  usage: { accounts: number; new_accounts: number; active: number; turns: number; talking: number; turn_days: number;
    payers: number; payers_ever: number; repeat_payers: number; recorders_ever: number; paid_share: number | null;
    recorded_share: number | null };
  listeners: { username: string; joined: string; balance: number; paid: number; bought: number; packs: number;
    recorded: number; recordings: number; cost: number | null; profit: number }[] };
export type StartKit = { id: string; label: string; preset: boolean };
type StartLimit = { area: string; side: string | null; level: "delicate" | "off-limits" };
export type StartInfo = { coaches: StartCoach[]; kits: StartKit[]; minutes: number; limits: StartLimit[];
  suggest: { goal: string; target?: string | null; reason: string } | null; setup_quick: boolean;
  /** No level yet: the first screen asks the setup's first questions with the request. */
  new?: boolean };

/** A logged workout (GET /api/workouts), newest first. `ref` it by its build id, else its number. */
export type Rating = "positive" | "neutral" | "negative";
export type Workout = { n: number; date: string; minutes: number; kit: string; coach: string; format: string | null;
  movements: string[]; topics: string; build_id: string | null; feedback: string[]; rating: Rating | null;
  has_script: boolean;
  /** Its MP3, while the site keeps it (24 hours after recording). */
  audio?: Audio };
export const workoutRef = (w: Workout) => w.build_id ?? String(w.n);

/** What the page does when the server says no one is signed in: set once by the app (back to the sign-in page),
 * so no screen has to. Every call still throws NotSignedIn, which screens just let go. */
let authLost: () => void = () => {};
export function setAuthLost(fn: () => void): () => void {
  authLost = fn;
  return () => { if (authLost === fn) authLost = () => {}; };
}

/** A 401 tells the app; any other refusal is an ApiError with the server's own words, where it sent some. */
async function checked(r: Response): Promise<Response> {
  if (r.status === 401) {
    authLost();
    throw new NotSignedIn("not signed in");
  }
  if (!r.ok) {
    let detail = r.statusText;
    let field: string | undefined;
    let code: ErrorCode | undefined;
    try {
      const j = await r.json();
      if (typeof j?.detail === "string") detail = j.detail;
      if (typeof j?.field === "string") field = j.field;
      if (typeof j?.code === "string") code = j.code as ErrorCode;
    } catch {
      /* no JSON body */
    }
    throw new ApiError(r.status, detail, field, code);
  }
  return r;
}

/** A call to the server. An empty answer (a 201 from register, a 204) is no body, whatever its status. */
export async function call<T>(method: "GET" | "POST" | "PUT" | "DELETE", url: string, body?: unknown): Promise<T> {
  const r = await checked(await fetch(url, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }));
  const text = await r.text();
  return (text.trim() === "" ? undefined : JSON.parse(text)) as T;
}

const jobResult = (id: number) =>
  call<{ id: number; state: JobState; error: string | null; code?: ErrorCode | null; result: unknown }>("GET", `/api/jobs/${id}`);

export const api = {
  me: () => call<Me>("GET", "/api/me"),
  authInfo: () => call<AuthInfo>("GET", "/api/auth"),
  signIn: (username: string, password: string) =>
    call<void>("POST", "/api/sign-in", { username, password }),
  register: (username: string, password: string) =>
    call<void>("POST", "/api/register", { username, password }),
  setPassword: (current: string | null, next: string) =>
    call<void>("POST", "/api/password", current === null ? { new: next } : { current, new: next }),
  /** Trade a Clerk session token for this site's session (where sign-in goes through Clerk). */
  session: (token: string) => call<void>("POST", "/api/session", { token }),
  /** The balance of minutes, the packs for sale and what happened lately. */
  minutes: () => call<MinutesState>("GET", "/api/minutes"),
  books: (days: number) => call<Books>("GET", `/api/admin/books?days=${days}`),
  /** Where to pay for a pack: its checkout page's address. Nothing is credited until the payment is. */
  checkout: (pack: string) => call<{ url: string }>("POST", "/api/minutes/checkout", { pack }),
  deviceLink: () => call<DeviceLink>("POST", "/api/device-link"),
  /** The private podcast feed's link (null while it's off); making one replaces the old link. */
  feed: () => call<{ url: string | null }>("GET", "/api/feed"),
  makeFeed: () => call<{ url: string }>("POST", "/api/feed"),
  stopFeed: () => call<void>("DELETE", "/api/feed"),
  setSky: (sky: "flow" | "field" | "waves" | "bloom" | "woven" | "garden") => call<void>("PUT", "/api/sky", { sky }),
  setAutoRecord: (on: boolean) => call<void>("PUT", "/api/auto-record", { on }),
  level: () => call<LevelState>("GET", "/api/level"),
  setLevel: (level: Level) => call<void>("PUT", "/api/level", { level }),
  /** `day` is the listener's own date (YYYY-MM-DD), as the log's are. */
  setCoach: (slug: string, day: string) => call<void>("PUT", "/api/coach", { slug, day }),
  /** `startAt` (from `withOffset`) asks for the workout at that time: the check-in now, the writing before it. */
  startConversation: (line: string, w: When, startAt?: string, photos?: string[]) =>
    call<{ id: number; job_id: number }>("POST", "/api/conversations", { line, ...w, ...(startAt ? { start_at: startAt } : {}),
      ...(photos?.length ? { photos } : {}) }),
  latestConversation: () => call<Conversation | undefined>("GET", "/api/conversations/latest"),
  conversation: (id: number) => call<Conversation>("GET", `/api/conversations/${id}`),
  /** `photos`: the kit photos the line carries, each a shrunk JPEG in base64 (lib/photos.ts). */
  sendMessage: (id: number, line: string, w: When, photos?: string[]) =>
    call<{ job_id: number }>("POST", `/api/conversations/${id}/messages`, { line, ...w, ...(photos?.length ? { photos } : {}) }),
  record: (id: number, w: When) => call<{ job_id: number }>("POST", `/api/conversations/${id}/record`, w),
  stop: (id: number) => call<{ stopping: boolean }>("POST", `/api/conversations/${id}/stop`),
  /** Schedule it: the one approval for a workout for later, up to its ceiling. */
  schedule: (id: number, w: When) => call<{ job_id: number; due: string }>("POST", `/api/conversations/${id}/schedule`, w),
  cancel: (id: number) => call<Conversation>("POST", `/api/conversations/${id}/cancel`),
  start: () => call<StartInfo>("GET", "/api/start"),
  workouts: () => call<{ workouts: Workout[] }>("GET", "/api/workouts").then((r) => r.workouts),
  workoutScript: (ref: string) =>
    call<{ script: string }>("GET", `/api/workouts/${encodeURIComponent(ref)}/script`).then((r) => r.script),
  /** Saves the feedback; the server then works out what it teaches in the background (`job_id`, read with
   * `jobResult`: its result's `summary`). A server older than 0.49.0 answers with nothing. */
  workoutFeedback: (ref: string, text: string) =>
    call<{ job_id?: number } | undefined>("POST", `/api/workouts/${encodeURIComponent(ref)}/feedback`, { text }),
  rateWorkout: (ref: string, rating: Rating | "none") =>
    call<void>("PUT", `/api/workouts/${encodeURIComponent(ref)}/rating`, { rating }),
  deleteWorkout: (ref: string) => call<void>("DELETE", `/api/workouts/${encodeURIComponent(ref)}`),
  signOut: () => call<void>("POST", "/api/sign-out"),
  deleteAccount: (password: string) => call<void>("POST", "/api/account/delete", { password }),
  /** The same for an account that signs in through Clerk: a fresh Clerk session token proves it's them. */
  deleteAccountAs: (token: string) => call<void>("POST", "/api/account/delete", { token }),
  importFolder: async (zip: Blob): Promise<{ imported: number; left_out: number }> => {
    const r = await checked(await fetch("/api/import", {
      method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/zip" }, body: zip,
    }));
    return r.json();
  },
  jobResult,
  /** How a job ended (its result too, unread). */
  job: jobResult,
};

/** A message for a person, from a failed call: the server's words, or `fallback` when it never answered. */
export function plainError(e: unknown, fallback = SAID.unreachable): string {
  if (e instanceof ApiError && e.status === 422) return "Check what you typed and try again.";
  if (e instanceof ApiError) return e.message || fallback;
  return fallback;
}

function jobError(e: unknown): string {
  if (e instanceof ApiError && e.status === 429) return "You already have jobs waiting. Give them a minute.";
  return plainError(e);
}

/** One job at a time: follow its events, then read how it ended. */
export function useJob() {
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
      setJob((v) => (v && v.id === id ? { ...v, state: j.state, error: j.error, code: j.code ?? null } : v));
    } catch (e) {
      if (e instanceof NotSignedIn) return;   // the app is already on its way to the sign-in page
      setJob((v) => (v && v.id === id ? { ...v, state: "failed", error: jobError(e) } : v));
    }
  }, []);

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
      let end: { state?: JobState; error?: string | null; code?: ErrorCode | null } = {};
      try {
        end = JSON.parse((e as MessageEvent).data);
      } catch {
        /* read it from the job instead */
      }
      if (end.state === "failed") {
        setJob((v) => (v && v.id === id ? { ...v, state: "failed", error: end.error ?? null, code: end.code ?? null } : v));
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

/** How waiting on a background job ended: its result once done, else why there is none. "gone": the screen that
 * asked closed first. */
type JobEnd = { state: "done"; result: unknown } | { state: "failed" | "timeout" | "gone" };

/** Wait for a worker job, reading it every `every` ms for at most `within` ms, while `live()` holds. The one
 * polling loop on this side: the feedback's summary uses it. A failed read ends it as
 * failed. */
export async function waitForJob(id: number, opts: { every?: number; within?: number; live?: () => boolean } = {})
  : Promise<JobEnd> {
  const { every = 1500, within = 90_000, live = () => true } = opts;
  const until = Date.now() + within;
  while (live()) {
    const j = await api.jobResult(id);
    if (j.state === "done") return { state: "done", result: j.result };
    if (j.state === "failed") return { state: "failed" };
    if (Date.now() >= until) return { state: "timeout" };
    await new Promise((r) => setTimeout(r, every));
  }
  return { state: "gone" };
}
