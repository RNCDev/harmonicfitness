// What the coach is doing while a turn runs: a running clock, the latest steps, what it's thinking about now, and a
// note when a step runs long.
import { useEffect, useRef, useState } from "react";
import type { Step } from "../../lib/steps";

const SHOWN_STEPS = 6;

/** Steps in a row that say the same thing are one step, as the later one stands. */
function collapsed(steps: Step[]): Step[] {
  return steps.filter((s, i) => i === steps.length - 1 || s.text !== steps[i + 1].text);
}

/** A note for a wait that has run long, by what it's waiting on. */
function longWait(s: Step): string {
  if (s.kind === "recording") return "Recording a full workout takes a few minutes.";
  if (s.kind === "voice") return "Making a voice takes a minute or two.";
  if (s.kind === "think") return "Planning carefully takes a minute when there's a lot to fit in.";
  return "Still on it.";
}
const LONG = 25;   // seconds before a running step says it's a long one
const TIMED = 8;   // seconds before a running step shows its own clock

function elapsed(since: number): string {
  const s = Math.max(0, Math.round((Date.now() - since) / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
}

/** "Your coach is working…" with a running clock, the coach's latest steps, and what it's thinking about now.
 * The chat's log already announces what's added to it, so this says nothing more on its own. */
export function Working({ steps, stopping }: { steps: Step[]; stopping: boolean }) {
  const [since] = useState(() => Date.now());
  const [, tick] = useState(0);
  const began = useRef(new Map<string, number>());   // when each running step was first seen
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  steps = steps.map((s, i) => (s.key ? s : { ...s, key: `n${i}` }));
  const last = steps[steps.length - 1];
  const thinking = last?.think && last.running ? last : null;
  steps = collapsed(steps.filter((s) => !s.think));
  if (thinking) {
    // "Wrapping up" read as a step and then thought about is one line, not two
    if (steps.length && !steps[steps.length - 1].running && steps[steps.length - 1].text === thinking.text) steps = steps.slice(0, -1);
    steps = [...steps, thinking];
  }
  const now = Date.now();
  for (const s of steps) if (s.running && !began.current.has(s.key!)) began.current.set(s.key!, now);
  const age = (s: Step) => (now - (began.current.get(s.key!) ?? now)) / 1000;
  const current = steps.find((s) => s.running && age(s) >= LONG);
  const shown = steps.slice(-SHOWN_STEPS);
  return (
    <div className="m a thinking">
      <p className="think-head">{stopping ? "Stopping…" : "Your coach is working…"} <span className="clock">{elapsed(since)}</span></p>
      {shown.length > 0 && (
        <ul className="steps">
          {steps.length > shown.length && <li className="more">{steps.length - shown.length} earlier steps</li>}
          {shown.map((s) => (
            <li key={s.key} className={`${s.running ? "now" : s.failed ? "bad" : ""}${s.think ? " think" : ""}`}
              aria-current={s.running ? "step" : undefined}>
              {s.text}{s.think && s.running ? "…" : ""}
              {s.running && age(s) >= TIMED && <>{" "}<span className="step-t">{elapsed(began.current.get(s.key!)!)}</span></>}
            </li>
          ))}
        </ul>
      )}
      {current && <p className="think-hint">{longWait(current)}</p>}
    </div>
  );
}
