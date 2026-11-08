// A turn's progress, as the chat shows it.

/** A step of the coach's turn: running while its tool works, then done (or failed). A thinking step (the model
 * working between tools) shows only while it runs. `key` tells one step from another across updates. */
export type Step = { text: string; failed?: boolean; running?: boolean; think?: boolean; key?: string;
  /** What a running step waits on, for the note on a long wait (the server's codes.step_kind). */
  kind?: StepKind };
export type StepKind = "think" | "recording" | "voice";
const KINDS: StepKind[] = ["think", "recording", "voice"];

/** A turn's job events as its steps, oldest first: an event with an id updates that step (it's said as it
 * starts, then as it ends); one without, from a server before 0.25.2, is a step already done. */
export function stepsOf(events: { stage: string; [field: string]: unknown }[]): Step[] {
  const out: Step[] = [];
  const at = new Map<number, number>();
  for (const e of events) {
    if (e.stage !== "step" || typeof e.text !== "string") continue;
    const step: Step = { text: e.text, failed: e.failed === true || e.state === "failed", running: e.state === "running",
      think: e.think === true, key: typeof e.id === "number" ? `s${e.id}` : `i${out.length}`,
      kind: KINDS.includes(e.kind as StepKind) ? (e.kind as StepKind) : e.think === true ? "think" : undefined };
    if (typeof e.id === "number" && at.has(e.id)) {
      out[at.get(e.id)!] = step;
      continue;
    }
    if (typeof e.id === "number") at.set(e.id, out.length);
    out.push(step);
  }
  return out;
}
