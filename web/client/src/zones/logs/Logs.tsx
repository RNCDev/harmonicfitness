// The Logs page: every logged workout, newest first, one line each (when, what, the topics, a rating); a line opens
// in place to its MP3, movements, feedback, script and delete (WorkoutRow.tsx).
// Sorted and filtered here, in the page (lib/arrange.ts); each change goes to the server and the list is read again.
import { useMemo, useState } from "react";
import { api, workoutRef } from "../../lib/api";
import { arrange, type RatingFilter, type Sort } from "../../lib/arrange";
import { SAID } from "../../lib/messages";
import { useResource } from "../../lib/useResource";
import { Button } from "../../ui/Button";
import { Field } from "../../ui/Field";
import { Empty, Loadable } from "../../ui/Notice";
import { PageHeader } from "../../ui/PageHeader";
import { WorkoutRow } from "./WorkoutRow";

const RATING_OPTIONS: { value: RatingFilter; label: string }[] = [
  { value: "all", label: "Any rating" },
  { value: "positive", label: "Positive" },
  { value: "neutral", label: "Neutral" },
  { value: "negative", label: "Negative" },
  { value: "unrated", label: "Not rated" },
];

const SORTS: { value: Sort; label: string }[] = [
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "longest", label: "Longest first" },
  { value: "shortest", label: "Shortest first" },
  { value: "best", label: "Best rated first" },
  { value: "worst", label: "Worst rated first" },
];

export function Logs({ onClose }: { onClose: () => void }) {
  const res = useResource(api.workouts, SAID.workouts);
  const list = res.data;
  const [q, setQ] = useState("");
  const [rating, setRating] = useState<RatingFilter>("all");
  const [format, setFormat] = useState("all");
  const [kit, setKit] = useState("all");
  const [sort, setSort] = useState<Sort>("newest");

  const formats = useMemo(() => [...new Set((list ?? []).map((w) => w.format ?? "").filter(Boolean))].sort(), [list]);
  const kits = useMemo(() => [...new Set((list ?? []).map((w) => w.kit))].sort(), [list]);
  const shown = useMemo(() => arrange(list ?? [], q, rating, format, kit, sort), [list, q, rating, format, kit, sort]);

  return (
    <section className="page" aria-labelledby="logs-title">
      <PageHeader id="logs-title" title="Logs" onClose={onClose}>
        {list && list.length > 0 && <p className="page-count">
          {shown.length === list.length ? `${list.length} ${list.length === 1 ? "workout" : "workouts"}`
            : `${shown.length} of ${list.length} workouts`}</p>}
      </PageHeader>
      <div className="logs-controls">
        <Field id="logs-search" label="Search" hideLabel className="logs-search">
          <input className="input" type="search" placeholder="Search movements, topics, feedback" value={q}
            onChange={(e) => setQ(e.target.value)} />
        </Field>
        <Field id="logs-rating" label="Rating" hideLabel>
          <select className="input" value={rating} onChange={(e) => setRating(e.target.value as RatingFilter)}>
            {RATING_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
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
            {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Field>
      </div>
      <Loadable value={list} error={res.error} onRetry={res.reload} what="your workouts" isEmpty={(l) => l.length === 0}
        empty={<Empty action={<Button onClick={onClose}>Plan a workout</Button>}>
          Your workouts show here once you've recorded one.</Empty>}>
        {() => (
          <>
            {shown.length === 0 && (
              <Empty action={<Button variant="text" onClick={() => {
                setQ(""); setRating("all"); setFormat("all"); setKit("all");
              }}>Clear the filters</Button>}>No workouts match.</Empty>
            )}
            <ol className="logs-list">
              {shown.map((w) => <WorkoutRow key={workoutRef(w) + w.date} w={w} onChanged={res.refresh} />)}
            </ol>
          </>
        )}
      </Loadable>
    </section>
  );
}
