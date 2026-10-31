// The Logs page: every logged workout, newest first, with its script, feedback, a rating and delete.
// Sorted and filtered here, in the page; each change goes to the server and the list is read again.
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, NotSignedIn, plainError, workoutRef, type Rating, type Workout } from "../api";

type Sort = "newest" | "oldest" | "longest" | "shortest" | "best" | "worst";
type RatingFilter = "all" | Rating | "unrated";

/** A face for each rating: the mouth is what changes. */
const Face = ({ mouth }: { mouth: string }) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="9.5" />
    <path d="M9 9.5h.01M15 9.5h.01" strokeWidth="2.4" />
    <path d={mouth} />
  </svg>
);
const RATINGS: { value: Rating; label: string; mouth: string }[] = [
  { value: "positive", label: "Positive", mouth: "M8 14a4.5 4.5 0 0 0 8 0" },
  { value: "neutral", label: "Neutral", mouth: "M8.5 15h7" },
  { value: "negative", label: "Negative", mouth: "M8 16.5a4.5 4.5 0 0 1 8 0" },
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

export function Logs({ onClose, onSignedOut }: { onClose: () => void; onSignedOut: () => void }) {
  const [list, setList] = useState<Workout[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [rating, setRating] = useState<RatingFilter>("all");
  const [format, setFormat] = useState("all");
  const [kit, setKit] = useState("all");
  const [sort, setSort] = useState<Sort>("newest");

  const failed = useCallback((e: unknown) => {
    if (e instanceof NotSignedIn) onSignedOut();
    else setError(plainError(e));
  }, [onSignedOut]);

  const load = useCallback(async () => {
    try {
      setList(await api.workouts());
      setError(null);
    } catch (e) {
      failed(e);
    }
  }, [failed]);
  useEffect(() => { void load(); }, [load]);

  const formats = useMemo(() => [...new Set((list ?? []).map((w) => w.format ?? "").filter(Boolean))].sort(), [list]);
  const kits = useMemo(() => [...new Set((list ?? []).map((w) => w.kit))].sort(), [list]);
  const shown = useMemo(() => arrange(list ?? [], q, rating, format, kit, sort), [list, q, rating, format, kit, sort]);

  return (
    <section className="logs" aria-labelledby="logs-title">
      <div className="logs-top">
        <h1 id="logs-title">Logs</h1>
        <button type="button" className="quiet" onClick={onClose}>Back to the chat</button>
      </div>
      <div className="logs-controls">
        <label className="logs-search">
          <span className="sr">Search</span>
          <input type="search" placeholder="Search movements, topics, feedback" value={q}
            onChange={(e) => setQ(e.target.value)} />
        </label>
        <label>
          <span>Rating</span>
          <select value={rating} onChange={(e) => setRating(e.target.value as RatingFilter)}>
            <option value="all">All</option>
            {RATINGS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            <option value="unrated">Not rated</option>
          </select>
        </label>
        <label>
          <span>Format</span>
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            <option value="all">All</option>
            {formats.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </label>
        <label>
          <span>Kit</span>
          <select value={kit} onChange={(e) => setKit(e.target.value)}>
            <option value="all">All</option>
            {kits.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </label>
        <label>
          <span>Sort</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="longest">Longest first</option>
            <option value="shortest">Shortest first</option>
            <option value="best">Best rated first</option>
            <option value="worst">Worst rated first</option>
          </select>
        </label>
      </div>
      {error && <p className="logs-error" role="alert">{error}</p>}
      {list === null && !error && <p className="logs-note" aria-busy="true">Loading your workouts…</p>}
      {list !== null && list.length === 0 && <p className="logs-note">No workouts logged yet.</p>}
      {list !== null && list.length > 0 && shown.length === 0 &&
        <p className="logs-note">No workouts match. <button type="button" className="quiet" onClick={() => {
          setQ(""); setRating("all"); setFormat("all"); setKit("all");
        }}>Clear the filters</button></p>}
      {list !== null && list.length > 0 && <p className="logs-count">{shown.length} of {list.length} workouts</p>}
      <ol className="logs-list">
        {shown.map((w) => <WorkoutCard key={workoutRef(w) + w.date} w={w} onChanged={load} onFailed={failed} />)}
      </ol>
    </section>
  );
}

function WorkoutCard({ w, onChanged, onFailed }: { w: Workout; onChanged: () => Promise<void>;
  onFailed: (e: unknown) => void }) {
  const ref = workoutRef(w);
  const [script, setScript] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [rated, setRated] = useState<Rating | null>(w.rating);
  const [confirm, setConfirm] = useState(false);
  useEffect(() => setRated(w.rating), [w.rating]);

  /** Run a change, then read the list again; false when it was refused. */
  const act = async (work: () => Promise<void>): Promise<boolean> => {
    setBusy(true);
    try {
      await work();
      await onChanged();
      return true;
    } catch (e) {
      onFailed(e);
      return false;
    } finally {
      setBusy(false);
    }
  };

  const toggleScript = async () => {
    if (open) return setOpen(false);
    setOpen(true);
    if (script === null) {
      try {
        setScript(await api.workoutScript(ref));
      } catch (e) {
        setOpen(false);
        onFailed(e);
      }
    }
  };

  const rate = (r: Rating) => {
    const next = rated === r ? null : r;
    const before = rated;
    setRated(next);   // at once; put back if the server refuses
    void act(() => api.rateWorkout(ref, next ?? "none")).then((ok) => { if (!ok) setRated(before); });
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
            <button key={r.value} type="button" className={`logs-rate-btn ${r.value}`} aria-pressed={rated === r.value}
              title={r.label} disabled={busy} onClick={() => rate(r.value)}>
              <Face mouth={r.mouth} /><span className="sr">{r.label}</span>
            </button>
          ))}
        </div>
      </div>
      <p className="logs-moves">{w.movements.join(", ")}</p>
      {w.topics && <p className="logs-topics">Topics: {w.topics}</p>}
      {w.feedback.length > 0 && (
        <ul className="logs-feedback" aria-label="Feedback">
          {w.feedback.map((f, i) => <li key={i}>{f}</li>)}
        </ul>
      )}
      <div className="logs-actions">
        <button type="button" className="act" aria-expanded={open} disabled={!w.has_script}
          title={w.has_script ? undefined : "No script was kept for this workout"} onClick={() => void toggleScript()}>
          {open ? "Hide the script" : "Show the script"}
        </button>
        {!confirm
          ? <button type="button" className="act danger" disabled={busy} onClick={() => setConfirm(true)}>Delete</button>
          : <span className="logs-confirm" role="alert">
              Delete this workout, its feedback and its files?
              <button type="button" className="act danger" disabled={busy}
                onClick={() => void act(() => api.deleteWorkout(ref))}>Delete it</button>
              <button type="button" className="act" onClick={() => setConfirm(false)}>Keep it</button>
            </span>}
      </div>
      {open && (
        <div className="logs-script" tabIndex={0} aria-label="Script">
          {script === null ? <p aria-busy="true">Loading the script…</p> : script}
        </div>
      )}
      <form className="logs-note-form" onSubmit={(e) => {
        e.preventDefault();
        const text = note.trim();
        if (!text) return;
        void act(async () => { await api.workoutFeedback(ref, text); setNote(""); });
      }}>
        <label>
          <span className="sr">Feedback on this workout</span>
          <input type="text" maxLength={1000} placeholder="Add feedback: too long, loved the quiz…" value={note}
            onChange={(e) => setNote(e.target.value)} disabled={busy} />
        </label>
        <button type="submit" className="act" disabled={busy || !note.trim()}>Save</button>
      </form>
    </li>
  );
}
