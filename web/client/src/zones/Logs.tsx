// The Logs page: every logged workout, newest first, with its script, feedback, a rating and delete.
// Sorted and filtered here, in the page; each change goes to the server and the list is read again.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, NotSignedIn, plainError, workoutRef, type Rating, type Workout } from "../api";
import { optimistic, useAction } from "../lib/useAction";
import { AudioFile } from "../ui/AudioFile";
import { Button } from "../ui/Button";
import { ConfirmInline } from "../ui/ConfirmInline";
import { Field } from "../ui/Field";
import { Icon } from "../ui/icons";
import { Notice } from "../ui/Notice";

type Sort = "newest" | "oldest" | "longest" | "shortest" | "best" | "worst";
type RatingFilter = "all" | Rating | "unrated";

/** A face for each rating: the mouth is what changes. */
const RATINGS: { value: Rating; label: string }[] = [
  { value: "positive", label: "Positive" },
  { value: "neutral", label: "Neutral" },
  { value: "negative", label: "Negative" },
];
const SCORE: Record<string, number> = { positive: 2, neutral: 1, negative: 0 };

/** "Fri 30 Oct 2026" from "2026-10-30", read as the listener's own date. */
export function longDate(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  if (!y || !m || !d) return day;
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short",
    year: "numeric" });
}

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
  const [list, setList] = useState<Workout[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [rating, setRating] = useState<RatingFilter>("all");
  const [format, setFormat] = useState("all");
  const [kit, setKit] = useState("all");
  const [sort, setSort] = useState<Sort>("newest");

  const load = useCallback(async () => {
    try {
      setList(await api.workouts());
      setError(null);
    } catch (e) {
      if (!(e instanceof NotSignedIn)) setError(plainError(e, "Couldn't load your workouts. Try again in a moment."));
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const formats = useMemo(() => [...new Set((list ?? []).map((w) => w.format ?? "").filter(Boolean))].sort(), [list]);
  const kits = useMemo(() => [...new Set((list ?? []).map((w) => w.kit))].sort(), [list]);
  const shown = useMemo(() => arrange(list ?? [], q, rating, format, kit, sort), [list, q, rating, format, kit, sort]);

  return (
    <section className="page" aria-labelledby="logs-title">
      <div className="page-top">
        <h1 id="logs-title">Logs</h1>
        <button type="button" className="quiet" onClick={onClose}>Back to the chat</button>
      </div>
      <div className="logs-controls">
        <label className="logs-search">
          <span className="sr">Search</span>
          <input className="input" type="search" placeholder="Search movements, topics, feedback" value={q}
            onChange={(e) => setQ(e.target.value)} />
        </label>
        <label>
          <span>Rating</span>
          <select className="input" value={rating} onChange={(e) => setRating(e.target.value as RatingFilter)}>
            <option value="all">All</option>
            {RATINGS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            <option value="unrated">Not rated</option>
          </select>
        </label>
        <label>
          <span>Format</span>
          <select className="input" value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="all">All</option>
            {formats.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </label>
        <label>
          <span>Kit</span>
          <select className="input" value={kit} onChange={(e) => setKit(e.target.value)}>
            <option value="all">All</option>
            {kits.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </label>
        <label>
          <span>Sort</span>
          <select className="input" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="longest">Longest first</option>
            <option value="shortest">Shortest first</option>
            <option value="best">Best rated first</option>
            <option value="worst">Worst rated first</option>
          </select>
        </label>
      </div>
      <Notice tone="error">{error}</Notice>
      {list === null && !error && <Notice tone="busy" className="page-note">Loading your workouts…</Notice>}
      {list !== null && list.length === 0 && <p className="page-note">No workouts logged yet.</p>}
      {list !== null && list.length > 0 && shown.length === 0 &&
        <p className="page-note">No workouts match. <button type="button" className="quiet" onClick={() => {
          setQ(""); setRating("all"); setFormat("all"); setKit("all");
        }}>Clear the filters</button></p>}
      {list !== null && list.length > 0 && <p className="page-count">{shown.length} of {list.length} workouts</p>}
      <ol className="logs-list">
        {shown.map((w) => <WorkoutCard key={workoutRef(w) + w.date} w={w} onChanged={load} />)}
      </ol>
    </section>
  );
}

/** One workout, with its own errors: a refused rating or note says so on its card, not at the top of the page. */
function WorkoutCard({ w, onChanged }: { w: Workout; onChanged: () => Promise<void> }) {
  const ref = workoutRef(w);
  const [script, setScript] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [rated, setRated] = useState<Rating | null>(w.rating);
  /** What the coach noted from the last feedback (worked out in the background): null until it says. */
  const [noted, setNoted] = useState<string | null>(null);
  const live = useRef(true);
  useEffect(() => () => { live.current = false; }, []);
  useEffect(() => setRated(w.rating), [w.rating]);

  /** Follow the enrichment job until it ends (two minutes at most), then show its summary, if any. */
  const follow = async (id: number) => {
    setNoted("Noting what that tells me…");
    for (let i = 0; i < 60 && live.current; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const j = await api.jobResult(id);
        if (j.state === "done") {
          const summary = (j.result as { summary?: unknown } | null)?.summary;
          return setNoted(typeof summary === "string" && summary.trim() ? summary : null);
        }
        if (j.state === "failed") return setNoted(null);
      } catch {
        return setNoted(null);
      }
    }
    if (live.current) setNoted(null);
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

  const title = `${longDate(w.date)}, ${w.minutes} minutes`;
  return (
    <li className="logs-card">
      <div className="logs-head">
        <div>
          <h2>{title}</h2>
          <p className="logs-meta">{[w.format, w.kit, w.coach].filter(Boolean).join(" · ")}</p>
        </div>
        <div className="logs-rate" role="group" aria-label={`Rate the ${title} workout`}>
          {RATINGS.map((r) => (
            <button key={r.value} type="button" className={`rate-btn ${r.value}`} aria-pressed={rated === r.value}
              title={r.label} disabled={busy} onClick={() => void rate(r.value)}>
              <Icon name={`face-${r.value}`} size={20} weight={1.8} /><span className="sr">{r.label}</span>
            </button>
          ))}
        </div>
      </div>
      {w.audio && <AudioFile audio={w.audio} preload="none" />}
      <p className="logs-moves">{w.movements.join(", ")}</p>
      {w.topics && <p className="logs-topics">Topics: {w.topics}</p>}
      {w.feedback.length > 0 && (
        <ul className="logs-feedback" aria-label="Feedback">
          {w.feedback.map((f, i) => <li key={i}>{f}</li>)}
        </ul>
      )}
      {noted && <p className="logs-noted" role="status">{noted}</p>}
      <div className="logs-actions">
        <Button aria-expanded={open} disabled={!w.has_script} aria-describedby={w.has_script ? undefined : `noscript-${ref}`}
          onClick={() => void toggleScript()}>
          {open ? "Hide the script" : "Show the script"}
        </Button>
        {!w.has_script && <span className="notice" id={`noscript-${ref}`}>No script was kept for this workout.</span>}
        {!deleting
          ? <Button danger disabled={busy} onClick={() => setDeleting(true)}>Delete</Button>
          : <ConfirmInline question="Delete this workout, its feedback and its files?" confirm="Delete it"
              busy={busy} onConfirm={() => void change.run(() => api.deleteWorkout(ref))} onKeep={() => setDeleting(false)} />}
      </div>
      <Notice tone="error">{shownError}</Notice>
      {open && (
        <div className="logs-script" tabIndex={0} aria-label="Script">
          {script === null ? <p aria-busy="true">Loading the script…</p> : script}
        </div>
      )}
      <form className="logs-note-form" onSubmit={(e) => {
        e.preventDefault();
        const text = note.trim();
        if (!text) return;
        void change.run(async () => {
          const r = await api.workoutFeedback(ref, text);
          setNote("");
          if (r?.job_id) void follow(r.job_id);
        });
      }}>
        <Field id={`feedback-${ref}`} label="Feedback on this workout" hideLabel>
          <input className="input" type="text" maxLength={1000} placeholder="Add feedback: too long, loved the quiz…" value={note}
            onChange={(e) => setNote(e.target.value)} disabled={busy} />
        </Field>
        <Button type="submit" busy={busy} disabled={!note.trim()}>Save</Button>
      </form>
    </li>
  );
}
