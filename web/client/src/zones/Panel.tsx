// The working panel: the job's stages as they stream in, then the brief (or what went wrong).
import Markdown from "react-markdown";
import type { JobView, Stage } from "../api";

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

export function Panel({ job, onRetry }: { job: JobView | null; onRetry: () => void }) {
  if (!job) {
    return (
      <section className="panel-empty" aria-label="Today's brief">
        <p>Change any underlined word, then get the brief.</p>
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
