// One look for what the page says back: an error (announced at once), a note (announced politely) or something
// still on its way. Renders nothing without words.
import type { ReactNode } from "react";

export function Notice({ tone = "status", className, children }: {
  tone?: "error" | "status" | "busy"; className?: string; children: ReactNode;
}) {
  if (children === null || children === undefined || children === false || children === "") return null;
  const cls = `notice${tone === "error" ? " err" : tone === "busy" ? " busy" : ""}${className ? " " + className : ""}`;
  if (tone === "error") return <p className={cls} role="alert">{children}</p>;
  if (tone === "busy") return <p className={cls} role="status" aria-busy="true">{children}</p>;
  return <p className={cls} role="status">{children}</p>;
}

/** A section's content once it's in: until then a line saying what's loading, in the room the content will take,
 * so nothing below it jumps; on failure, the error. */
export function Loadable<T>({ value, error, what, room = 0, children }: {
  value: T | null | undefined; error?: string | null; what: string; room?: number; children: (v: T) => ReactNode;
}) {
  if (value !== null && value !== undefined) return <>{children(value)}</>;   // an empty answer is not an answer
  if (error) return <Notice tone="error">{error}</Notice>;
  return (
    <span className="hold" style={{ ["--hold" as string]: `${room}px` }}>
      <Notice tone="busy">{`Loading ${what}…`}</Notice>
    </span>
  );
}
