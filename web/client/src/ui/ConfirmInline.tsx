// Asking before something is deleted, in place: the question, the brick button that does it, and the way back
// (which takes focus, so Enter never deletes by accident).
import { useEffect, useRef } from "react";
import { Button } from "./Button";

export function ConfirmInline({ question, confirm, keep = "Keep it", busy = false, onConfirm, onKeep, className }: {
  question: string; confirm: string; keep?: string; busy?: boolean; onConfirm: () => void; onKeep: () => void;
  className?: string;
}) {
  const back = useRef<HTMLButtonElement>(null);
  useEffect(() => { back.current?.focus(); }, []);
  return (
    <span className={`confirm${className ? " " + className : ""}`} role="group" aria-label={question}>
      <span className="confirm-q">{question}</span>
      <Button danger busy={busy} onClick={onConfirm}>{confirm}</Button>
      <Button ref={back} disabled={busy} onClick={onKeep}>{keep}</Button>
    </span>
  );
}
