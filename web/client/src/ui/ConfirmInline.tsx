// Asking before something is deleted, in place: the question, the brick button that does it, and the way back.
// Focus goes to the way back, so Enter never deletes by accident; when deleting needs something typed first (the
// account's password, `field`), focus goes there, and Enter in it confirms once `canConfirm`.
import { useEffect, useRef, type ReactNode } from "react";
import { Button } from "./Button";

export function ConfirmInline({ question, detail, field, canConfirm = true, confirm, keep = "Keep it", busy = false,
  onConfirm, onKeep, className }: {
  question: string;
  /** What goes, said under the question. */
  detail?: string;
  /** What must be typed first (a Field), inside a form so Enter confirms. */
  field?: ReactNode;
  canConfirm?: boolean;
  confirm: string; keep?: string; busy?: boolean; onConfirm: () => void; onKeep: () => void; className?: string;
}) {
  const root = useRef<HTMLFormElement & HTMLSpanElement>(null);
  const back = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (field) root.current?.querySelector<HTMLElement>("input, textarea, select")?.focus();
    else back.current?.focus();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const buttons = (
    <>
      <Button type={field ? "submit" : "button"} danger busy={busy} disabled={!canConfirm}
        onClick={field ? undefined : onConfirm}>{confirm}</Button>
      <Button ref={back} disabled={busy} onClick={onKeep}>{keep}</Button>
    </>
  );
  if (!field) {
    return (
      <span ref={root} className={`confirm${className ? " " + className : ""}`} role="group" aria-label={question}>
        <span className="confirm-q">{question}</span>
        {buttons}
      </span>
    );
  }
  return (
    <form ref={root} className={`confirm confirm-form${className ? " " + className : ""}`} aria-label={question}
      onSubmit={(e) => { e.preventDefault(); if (canConfirm && !busy) onConfirm(); }}>
      <p className="confirm-q">{question}</p>
      {detail && <p className="notice err">{detail}</p>}
      {field}
      <span className="confirm">{buttons}</span>
    </form>
  );
}
