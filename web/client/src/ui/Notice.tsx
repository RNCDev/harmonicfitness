// One look for what the page says back: an error (announced at once), a note (announced politely), something done
// ("Password changed.", one sentence, past tense) or something still on its way. Renders nothing without words. Loadable and Empty are the three states every list shares:
// loading, failed (with Try again), and empty (with the one thing to do next).
import type { ReactNode } from "react";
import { Button } from "./Button";

export function Notice({ tone = "status", className, children }: {
  tone?: "error" | "status" | "done" | "busy"; className?: string; children: ReactNode;
}) {
  if (children === null || children === undefined || children === false || children === "") return null;
  const cls = `notice${tone === "error" ? " err" : tone === "busy" ? " busy" : tone === "done" ? " done" : ""}${className ? " " + className : ""}`;
  if (tone === "error") return <p className={cls} role="alert">{children}</p>;
  if (tone === "busy") return <p className={cls} role="status" aria-busy="true">{children}</p>;
  return <p className={cls} role="status">{children}</p>;
}

/** An empty list: a sentence on what will appear here, and the one action that gets there. */
export function Empty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <p className="page-note">{children}</p>
      {action}
    </div>
  );
}

/** A section's content once it's in: until then a line saying what's loading, in the room the content will take,
 * so nothing below it jumps; on failure, the error and Try again (with `onRetry`). `isEmpty` and `empty` show the
 * empty state in place of the content. */
export function Loadable<T>({ value, error, what, room = 0, onRetry, isEmpty, empty, children }: {
  value: T | null | undefined; error?: string | null; what: string; room?: number; onRetry?: () => void;
  isEmpty?: (v: T) => boolean; empty?: ReactNode; children: (v: T) => ReactNode;
}) {
  if (value !== null && value !== undefined) {   // an empty answer is not an answer
    return <>{isEmpty?.(value) && empty !== undefined ? empty : children(value)}</>;
  }
  if (error) {
    return (
      <div className="failed">
        <Notice tone="error">{error}</Notice>
        {onRetry && <Button onClick={onRetry}>Try again</Button>}
      </div>
    );
  }
  return (
    <span className="hold" style={{ ["--hold" as string]: `${room}px` }}>
      <Notice tone="busy">{`Loading ${what}…`}</Notice>
    </span>
  );
}
