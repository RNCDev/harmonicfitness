// A note on one workout, in its Logs row: typed, saved, and sent to the coach to learn from. A refusal is said
// under the box it's about.
import { useState } from "react";
import { api } from "../../lib/api";
import { useAction } from "../../lib/useAction";
import { Button } from "../../ui/Button";
import { Field } from "../../ui/Field";

export function FeedbackForm({ workout, onSaved, onCancel }: {
  /** The workout's reference (lib/api.ts's workoutRef). */
  workout: string;
  /** Saved: the job that reads it, if one was started. */
  onSaved: (jobId: number | null) => void | Promise<void>;
  onCancel: () => void;
}) {
  const [note, setNote] = useState("");
  const save = useAction(async (text: string) => {
    const r = await api.workoutFeedback(workout, text);
    setNote("");
    await onSaved(r?.job_id ?? null);
  });
  return (
    <form className="logs-note-form" onSubmit={(e) => {
      e.preventDefault();
      const text = note.trim();
      if (text) void save.run(text);
    }}>
      <Field id={`feedback-${workout}`} label="Feedback on this workout" hideLabel error={save.error}>
        <input className="input" type="text" maxLength={1000} placeholder="Too long, loved the quiz…" value={note}
          autoFocus onChange={(e) => setNote(e.target.value)} disabled={save.busy} />
      </Field>
      <Button type="submit" busy={save.busy} busyLabel="Saving…" disabled={!note.trim()}>Save</Button>
      <Button variant="text" disabled={save.busy} onClick={onCancel}>Cancel</Button>
    </form>
  );
}
