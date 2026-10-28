// The working panel: the job's stages as they stream in, then the brief (or what went wrong).
import Markdown from "react-markdown";
import type { AnswerValues, JobView, OpenQuestion, Plan, Stage } from "../api";
import { PlanTable } from "./PlanTable";
import { Question } from "./Question";

const STAGE_WORDS: Record<string, string> = {
  queued: "Waiting for a turn",
  folder: "Getting your notes ready",
  brief: "Reading your limits and kit",
  saved: "Saved",
};

function said(error: string | null): string {
  if (!error) return "Something went wrong.";
  if (error === "interrupted") return "It was interrupted before it finished.";
  const s = error.charAt(0).toUpperCase() + error.slice(1);
  return /[.!?]$/.test(s) ? s : `${s}.`;
}

type Row = { key: string; words: string; status: "done" | "now" | "failed" };

function rows(job: JobView): Row[] {
  const streamed: Stage[] = job.stages;
  const all = [{ stage: "queued" }, ...streamed];
  const finished = job.state === "done";
  return all.map((s, i) => {
    const last = i === all.length - 1;
    let status: Row["status"] = "done";
    if (last && !finished) status = job.state === "failed" ? "failed" : "now";
    return { key: `${i}-${s.stage}`, words: STAGE_WORDS[s.stage] ?? s.stage, status };
  });
}

type Props = {
  job?: JobView | null;
  onRetry?: () => void;
  question?: OpenQuestion | null;
  plan?: Plan | null;
  working?: boolean;
  onAnswer?: (toolCallId: string, values: AnswerValues) => void;
};

export function Panel({ job = null, onRetry = () => {}, question = null, plan = null, working = false,
  onAnswer = () => {} }: Props) {
  if (question) {
    return (
      <section aria-label="Check-in">
        <Question key={question.tool_call_id} ask={question} onSend={onAnswer} disabled={working} />
      </section>
    );
  }
  if (plan) return <PlanTable plan={plan} />;
  if (!job) {
    return (
      <section className="panel-empty" aria-label="Today's plan">
        <p>Change any underlined word, then start.</p>
      </section>
    );
  }
  const showBrief = job.state === "done" && job.result;
  return (
    <section aria-label="Today's brief" aria-busy={job.state === "queued" || job.state === "running"}>
      <ol className="stages" aria-live="polite">
        {rows(job).map((r) => (
          <li key={r.key} className={`stage ${r.status}`}>
            <span className="dot" aria-hidden="true" />
            <span>{r.words}</span>
            {r.status === "now" && <span className="sr"> (working)</span>}
          </li>
        ))}
      </ol>
      {job.state === "failed" && (
        <div className="failed" role="alert">
          <h2>That didn't work</h2>
          <p>{said(job.error)}</p>
          <button type="button" className="go alt" onClick={onRetry}>Try again</button>
        </div>
      )}
      {job.state === "done" && !job.result && (
        <p className="meta">Done, but there's no brief to show.</p>
      )}
      {showBrief && (
        <article className="brief">
          <Markdown skipHtml>{job.result!.brief_md}</Markdown>
        </article>
      )}
    </section>
  );
}
