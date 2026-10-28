// The check-in: the agent's open question as one form. One Send for every question.
import { useState } from "react";
import type { AnswerValues, AskedQuestion, OpenQuestion } from "../api";

function initial(q: AskedQuestion): string[] {
  const rec = q.options.filter((o) => o.recommended).map((o) => o.label);
  return q.multi ? rec : rec.slice(0, 1);
}

export function Question({ ask, onSend, disabled = false }: {
  ask: OpenQuestion; onSend: (toolCallId: string, values: AnswerValues) => void; disabled?: boolean;
}) {
  const [picked, setPicked] = useState<Record<string, string[]>>(
    () => Object.fromEntries(ask.questions.map((q) => [q.id, initial(q)])));
  const [other, setOther] = useState<Record<string, string>>({});
  const [sent, setSent] = useState(false);

  const typed = (q: AskedQuestion) => (q.other ? (other[q.id] ?? "").trim() : "");
  const answered = ask.questions.every((q) => typed(q) || (picked[q.id] ?? []).length > 0);

  function choose(q: AskedQuestion, label: string, on: boolean) {
    setPicked((p) => ({
      ...p,
      [q.id]: q.multi ? (on ? [...(p[q.id] ?? []), label] : (p[q.id] ?? []).filter((l) => l !== label)) : [label],
    }));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (sent || disabled || !answered) return;
    setSent(true);
    const values: AnswerValues = {};
    for (const q of ask.questions) {
      const t = typed(q);
      values[q.id] = t ? `other: ${t}` : q.options.map((o) => o.label).filter((l) => (picked[q.id] ?? []).includes(l));
    }
    onSend(ask.tool_call_id, values);
  }

  return (
    <form className="question" onSubmit={submit}>
      {ask.questions.map((q) => (
        <fieldset key={q.id} disabled={sent || disabled}>
          <legend>{q.prompt}</legend>
          {q.options.map((o) => {
            const id = `q-${q.id}-${o.label}`;
            return (
              <div className="opt" key={o.label}>
                <input id={id} type={q.multi ? "checkbox" : "radio"} name={q.id}
                  checked={(picked[q.id] ?? []).includes(o.label)}
                  onChange={(e) => choose(q, o.label, e.target.checked)} />
                <label htmlFor={id}>
                  {o.label}
                  {o.recommended && <span className="rec">Recommended</span>}
                  {o.description && <span className="desc">{o.description}</span>}
                </label>
              </div>
            );
          })}
          {q.other && (
            <div className="other">
              <label htmlFor={`o-${q.id}`}>Other</label>
              <input id={`o-${q.id}`} type="text" value={other[q.id] ?? ""}
                onChange={(e) => setOther((o) => ({ ...o, [q.id]: e.target.value }))} />
            </div>
          )}
        </fieldset>
      ))}
      <button type="submit" className="go" disabled={sent || disabled || !answered}>Send</button>
    </form>
  );
}
