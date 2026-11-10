// One workout in the Logs page, with its own errors: a refused rating or delete says so on its line, not at the top
// of the page. The line opens in place to its MP3, movements, feedback, script and delete.
import { useEffect, useState } from "react";
import { api, workoutRef, type Rating, type Workout } from "../../lib/api";
import { longDate, rowDate } from "../../lib/format";
import { SAID } from "../../lib/messages";
import { optimistic, useAction } from "../../lib/useAction";
import { useFeedbackNote } from "../../lib/useFeedbackNote";
import { useResource } from "../../lib/useResource";
import { AudioFile } from "../../ui/AudioFile";
import { Button } from "../../ui/Button";
import { ConfirmInline } from "../../ui/ConfirmInline";
import { Icon } from "../../ui/icons";
import { Loadable, Notice } from "../../ui/Notice";
import { FeedbackForm } from "./FeedbackForm";

/** A face for each rating: the mouth is what changes. */
const RATINGS: { value: Rating; label: string }[] = [
  { value: "positive", label: "Positive" },
  { value: "neutral", label: "Neutral" },
  { value: "negative", label: "Negative" },
];

/** The words of a workout's script, read when it's first shown. */
function Script({ workout }: { workout: string }) {
  const res = useResource(() => api.workoutScript(workout), SAID.script, [workout]);
  return (
    <div className="logs-script" tabIndex={0} aria-label="Script">
      <Loadable value={res.data} error={res.error} onRetry={res.reload} what="the script">{(s) => s}</Loadable>
    </div>
  );
}

export function WorkoutRow({ w, onChanged }: { w: Workout; onChanged: () => Promise<void> }) {
  const ref = workoutRef(w);
  const [scriptShown, setScriptShown] = useState(false);
  const [writing, setWriting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  /** The line opened to the workout's details. */
  const [shown, setShown] = useState(false);
  const [rated, setRated] = useState<Rating | null>(w.rating);
  const [rateError, setRateError] = useState<string | null>(null);
  useEffect(() => setRated(w.rating), [w.rating]);
  const feedback = useFeedbackNote();
  const remove = useAction(async () => { await api.deleteWorkout(ref); await onChanged(); });

  // at once; put back, with the reason, if the server refuses
  const rate = async (r: Rating) => {
    const next = rated === r ? null : r;
    setRateError(await optimistic(rated, next, setRated, () => api.rateWorkout(ref, next ?? "none")));
  };

  const title = longDate(w.date);
  const meta = [`${w.minutes} min`, w.format, w.kit, w.coach].filter(Boolean).join(" · ");
  const panel = `logs-more-${ref}`;
  return (
    <li className={`logs-card${shown ? " open" : ""}`}>
      <div className="logs-line">
        <Button variant="bare" className="logs-toggle" aria-expanded={shown} aria-controls={panel}
          aria-label={`${title}, ${meta}`} onClick={() => setShown(!shown)}>
          <Icon name="chevron-right" size={14} className="logs-chev" />
          <span className="head logs-date">{rowDate(w.date)}</span>
          <span className="logs-meta">{meta}</span>
          <span className="logs-topics">{w.topics}</span>
          {w.feedback.length > 0 && <span className="logs-has-note" title="Has feedback" />}
        </Button>
        <div className="logs-rate" role="group" aria-label={`Rate the ${title} workout`}>
          {RATINGS.map((r) => (
            <Button key={r.value} variant="bare" className={`rate-btn ${r.value}`} pressed={rated === r.value}
              title={r.label} disabled={remove.busy} onClick={() => void rate(r.value)}>
              <Icon name={`face-${r.value}`} size={20} weight={1.7} /><span className="sr">{r.label}</span>
            </Button>
          ))}
        </div>
      </div>
      <Notice tone="error">{rateError ?? remove.error}</Notice>
      {feedback.noted && <p className="logs-noted" role="status">{feedback.noted}</p>}
      {shown && <div className="logs-more" id={panel}>
        {w.audio && <AudioFile audio={w.audio} preload="none" />}
        <ul className="logs-moves" aria-label="Movements">{w.movements.map((m, i) => <li key={i}>{m}</li>)}</ul>
        {w.topics && <p className="logs-topics-all"><span className="logs-topics-h">Topics</span> {w.topics}</p>}
        {w.feedback.length > 0 && (
          <ul className="logs-feedback" aria-label="Feedback">
            {w.feedback.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        )}
        <div className="logs-actions">
          {w.has_script && <Button variant="text" aria-expanded={scriptShown} onClick={() => setScriptShown(!scriptShown)}>
            {scriptShown ? "Hide the script" : "Show the script"}
          </Button>}
          {!writing && <Button variant="text" onClick={() => setWriting(true)}>Add feedback</Button>}
          {!deleting
            ? <Button variant="text" danger className="logs-delete" disabled={remove.busy} onClick={() => setDeleting(true)}>Delete</Button>
            : <ConfirmInline question="Delete this workout, its feedback and its files?" confirm="Delete it"
                busy={remove.busy} onConfirm={() => void remove.run()} onKeep={() => setDeleting(false)} />}
        </div>
        {scriptShown && <Script workout={ref} />}
        {writing && <FeedbackForm workout={ref} onCancel={() => setWriting(false)}
          onSaved={async (job) => { setWriting(false); void feedback.saved(job); await onChanged(); }} />}
      </div>}
    </li>
  );
}
