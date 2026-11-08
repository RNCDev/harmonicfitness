// A labelled input with its hint and its error beside it, tied to it for a screen reader.
import { cloneElement, type ReactElement } from "react";

export function Field({ id, label, hint, error, hideLabel = false, className, children }: {
  id: string; label: string; hint?: string | null; error?: string | null; hideLabel?: boolean; className?: string;
  children: ReactElement;
}) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errId = error ? `${id}-err` : undefined;
  const described = [hintId, errId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={`field${className ? " " + className : ""}`}>
      <label htmlFor={id} className={hideLabel ? "sr" : "label"}>{label}</label>
      {cloneElement(children, { id, "aria-invalid": error ? true : undefined, "aria-describedby": described })}
      {hint && <p id={hintId} className="hint">{hint}</p>}
      {error && <p id={errId} className="notice err" role="alert">{error}</p>}
    </div>
  );
}
