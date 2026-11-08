// The Logs page: every logged workout, newest first, with its script, feedback, a rating and delete.
// Sorted and filtered here, in the page; each change goes to the server and the list is read again.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, NotSignedIn, plainError, waitForJob, workoutRef, type Rating, type Workout } from "../lib/api";
import { longDate } from "../lib/format";
import { optimistic, useAction } from "../lib/useAction";
import { useResource } from "../lib/useResource";
import { AudioFile } from "../ui/AudioFile";
import { Button } from "../ui/Button";
import { ConfirmInline } from "../ui/ConfirmInline";
import { Field } from "../ui/Field";
import { Icon } from "../ui/icons";
import { Empty, Loadable, Notice } from "../ui/Notice";

type Sort = "newest" | "oldest" | "longest" | "shortest" | "best" | "worst";
type RatingFilter = "all" | Rating | "unrated";

/** A face for each rating: the mouth is what changes. */
const RATINGS: { value: Rating; label: string }[] = [
  { value: "positive", label: "Positive" },
  { value: "neutral", label: "Neutral" },
  { value: "negative", label: "Negative" },
];
const SCORE: Record<string, number> = { positive: 2, neutral: 1, negative: 0 };

/** The workouts the controls leave, in their order. */
export function arrange(list: Workout[], q: string, rating: RatingFilter, format: string, kit: string,
                        sort: Sort): Workout[] {
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  const kept = list.filter((w) => {
    if (rating === "unrated" ? w.rating !== null : rating !== "all" && w.rating !== rating) return false;
    if (format !== "all" && (w.format ?? "") !== format) return false;
    if (kit !== "all" && w.kit !== kit) return false;
    const hay = [w.date, w.kit, w.coach, w.format ?? "", w.topics, ...w.movements, ...w.feedback].join(" ").toLowerCase();
    return words.every((word) => hay.includes(word));
  });
  const score = (w: Workout) => (w.rating === null ? -1 : SCORE[w.rating]);
  // newest by the date, then by the log's order (n: 1 is the last one logged)
  const newer = (a: Workout, b: Workout) => b.date.localeCompare(a.date) || a.n - b.n;
  const by: Record<Sort, (a: Workout, b: Workout) => number> = {
    newest: newer,
    oldest: (a, b) => newer(b, a),
    longest: (a, b) => b.minutes - a.minutes || newer(a, b),
    shortest: (a, b) => a.minutes - b.minutes || newer(a, b),
    best: (a, b) => score(b) - score(a) || newer(a, b),
    worst: (a, b) => (score(a) === -1 ? 9 : score(a)) - (score(b) === -1 ? 9 : score(b)) || newer(a, b),
  };
  return [...kept].sort(by[sort]);
}

export function Logs({ onClose }: { onClose: () => void }) {
  const res = useResource(api.workouts, "Couldn't load your workouts.");
  const list = res.data;
  const [q, setQ] = useState("");
  const [rating, setRating] = useState<RatingFilter>("all");
  const [format, setFormat] = useState("all");
  const [kit, setKit] = useState("all");
  const [sort, setSort] = useState<Sort>("newest");

  // after a change, the list is read again; a failed read leaves the list as it was and asks again
  const { set, reload } = res;
  const load = useCallback(async () => {
    try {
      const fresh = await api.workouts();
      set(() => fresh);
    } catch {
      reload();
    }
  }, [set, reload]);

  const formats = useMemo(() => [...new Set((list ?? []).map((w) => w.format ?? "").filter(Boolean))].sort(), [list]);
  const kits = useMemo(() => [...new Set((list ?? []).map((w) => w.kit))].sort(), [list]);
  const shown = useMemo(() => arrange(list ?? [], q, rating, format, kit, sort), [list, q, rating, format, kit, sort]);

  return (
    <section className="page" aria-labelledby="logs-title">
      <div className="page-top">
        <div>
          <h1 className="head" id="logs-title">Logs</h1>
          {list && list.length > 0 && <p className="page-count">
            {shown.length === list.length ? `${list.length} ${list.length === 1 ? "workout" : "workouts"}`
              : `${shown.length} of ${list.length} workouts`}</p>}
        </div>
        <Button variant="bare" className="page-close" aria-label="Back to the chat" onClick={onClose}>Close</Button>
      </div>
      <div className="logs-controls">
        <Field id="logs-search" label="Search" hideLabel className="logs-search">
          <input className="input" type="search" placeholder="Search movements, topics, feedback" value={q}
            onChange={(e) => setQ(e.target.value)} />
        </Field>
        <Field id="logs-rating" label="Rating" hideLabel>
          <select className="input" value={rating} onChange={(e) => setRating(e.target.value as RatingFilter)}>
            <option value="all">Any rating</option>
            {RATINGS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            <option value="unrated">Not rated</option>
          </select>
        </Field>
        <Field id="logs-format" label="Format" hideLabel>
          <select className="input" value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="all">Any format</option>
            {formats.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </Field>
        <Field id="logs-kit" label="Kit" hideLabel>
          <select className="input" value={kit} onChange={(e) => setKit(e.target.value)}>
            <option value="all">Any kit</option>
            {kits.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </Field>
        <Field id="logs-sort" label="Sort" hideLabel>
          <select className="input" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="longest">Longest first</option>
            <option value="shortest">Shortest first</option>
            <option value="best">Best rated first</option>
            <option value="worst">Worst rated first</option>
          </select>
        </Field>
      </div>
      <Loadable value={list} error={res.error} onRetry={res.reload} what="your workouts" isEmpty={(l) => l.length === 0}
        empty={<Empty action={<Button onClick={onClose}>Plan a workout</Button>}>
          Your workouts show here once you've recorded one.</Empty>}>
        {() => (
          <>
            {shown.length === 0 &&
              <p className="page-note">No workouts match. <Button variant="text" onClick={() => {
                setQ(""); setRating("all"); setFormat("all"); setKit("all");
              }}>Clear the filters</Button></p>}
            <ol className="logs-list">
              {shown.map((w) => <WorkoutCard key={workoutRef(w) + w.date} w={w} onChanged={load} />)}
            </ol>
          </>
        )}
      </Loadable>
    </section>
  );
}

/** One workout, with its own errors: a refused rating or note says so on its card, not at the top of the page. */
function WorkoutCard({ w, onChanged }: { w: Workout; onChanged: () => Promise<void> }) {
  const ref = workoutRef(w);
  const [script, setScript] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [writing, setWriting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rated, setRated] = useState<Rating | null>(w.rating);
  /** What the coach noted from the last feedback (worked out in the background): null until it says. Until then,
   * and if it never says, "Feedback saved." stays, so the listener knows the note went in. */
  const [noted, setNoted] = useState<string | null>(null);
  const live = useRef(true);
  useEffect(() => () => { live.current = false; }, []);
  useEffect(() => setRated(w.rating), [w.rating]);

  /** Follow the enrichment job until it ends (two minutes at most), then show its summary, if any. */
  const follow = async (id: number) => {
    setNoted("Feedback saved. Noting what that tells me…");
    let end;
    try {
      end = await waitForJob(id, { every: 2000, within: 120_000, live: () => live.current });
    } catch {
      end = { state: "failed" as const };
    }
    if (!live.current) return;
    const summary = end.state === "done" ? (end.result as { summary?: unknown } | null)?.summary : null;
    setNoted(typeof summary === "string" && summary.trim() ? summary : "Feedback saved.");
  };

  /** A change to this workout, then the list read again. */
  const change = useAction(async (work: () => Promise<void>) => { setError(null); await work(); await onChanged(); });
  const busy = change.busy;
  const [deleting, setDeleting] = useState(false);
  const shownError = error ?? change.error;

  const toggleScript = async () => {
    if (open) return setOpen(false);
    setOpen(true);
    setError(null);
    if (script === null) {
      try {
        setScript(await api.workoutScript(ref));
      } catch (e) {
        setOpen(false);
        if (!(e instanceof NotSignedIn)) setError(plainError(e, "Couldn't load the script. Try again."));
      }
    }
  };

  // at once; put back, with the reason, if the server refuses
  const rate = async (r: Rating) => {
    const next = rated === r ? null : r;
    setError(await optimistic(rated, next, setRated, () => api.rateWorkout(ref, next ?? "none")));
  };

  const title = longDate(w.date);
  return (
    <li className="logs-card">
      <div className="logs-head">
        <div>
          <h2 className="head">{title}</h2>
          <p className="logs-meta">{[`${w.minutes} min`, w.format, w.kit, w.coach].filter(Boolean).join(" · ")}</p>
        </div>
        <div className="logs-rate" role="group" aria-label={`Rate the ${title} workout`}>
          {RATINGS.map((r) => (
            <Button key={r.value} variant="bare" className={`rate-btn ${r.value}`} pressed={rated === r.value}
              title={r.label} disabled={busy} onClick={() => void rate(r.value)}>
              <Icon name={`face-${r.value}`} size={22} weight={1.7} /><span className="sr">{r.label}</span>
            </Button>
          ))}
        </div>
      </div>
      {w.audio && <AudioFile audio={w.audio} preload="none" />}
      <p className="logs-moves">{w.movements.join(", ")}</p>
      {w.topics && <p className="logs-topics"><span className="logs-topics-h">Topics</span> {w.topics}</p>}
      {w.feedback.length > 0 && (
        <ul className="logs-feedback" aria-label="Feedback">
          {w.feedback.map((f, i) => <li key={i}>{f}</li>)}
        </ul>
      )}
      {noted && <p className="logs-noted" role="status">{noted}</p>}
      <div className="logs-actions">
        {w.has_script && <Button variant="text" aria-expanded={open} onClick={() => void toggleScript()}>
          {open ? "Hide the script" : "Show the script"}
        </Button>}
        {!writing && <Button variant="text" onClick={() => setWriting(true)}>Add feedback</Button>}
        {!deleting
          ? <Button variant="text" danger className="logs-delete" disabled={busy} onClick={() => setDeleting(true)}>Delete</Button>
          : <ConfirmInline question="Delete this workout, its feedback and its files?" confirm="Delete it"
              busy={busy} onConfirm={() => void change.run(() => api.deleteWorkout(ref))} onKeep={() => setDeleting(false)} />}
      </div>
      <Notice tone="error">{shownError}</Notice>
      {open && (
        <div className="logs-script" tabIndex={0} aria-label="Script">
          {script === null ? <p aria-busy="true">Loading the script…</p> : script}
        </div>
      )}
      {writing && <form className="logs-note-form" onSubmit={(e) => {
        e.preventDefault();
        const text = note.trim();
        if (!text) return;
        void change.run(async () => {
          const r = await api.workoutFeedback(ref, text);
          setNote("");
          setWriting(false);
          if (r?.job_id) void follow(r.job_id);
          else setNoted("Feedback saved.");
        });
      }}>
        <Field id={`feedback-${ref}`} label="Feedback on this workout" hideLabel>
          <input className="input" type="text" maxLength={1000} placeholder="Too long, loved the quiz…" value={note}
            autoFocus onChange={(e) => setNote(e.target.value)} disabled={busy} />
        </Field>
        <Button type="submit" busy={busy} disabled={!note.trim()}>Save</Button>
        <Button variant="text" disabled={busy} onClick={() => { setWriting(false); setNote(""); }}>Cancel</Button>
      </form>}
    </li>
  );
}
