// The top of a page over the chat (Logs, Coaches): its title, a line under it, and Close back to the chat. Focus
// moves to the title as the page opens, so a keyboard or a screen reader starts on the page it asked for; the
// app puts focus back on the button that opened it once the page closes (App.tsx).
import { useEffect, useRef, type ReactNode } from "react";
import { Button } from "./Button";

export function PageHeader({ id, title, children, onClose }: {
  /** The heading's id: the page's section is labelled by it. */
  id: string;
  title: string;
  /** Under the title: a count, or what to do here. */
  children?: ReactNode;
  onClose: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, []);
  return (
    <div className="page-top">
      <div>
        <h1 className="head" id={id} ref={heading} tabIndex={-1}>{title}</h1>
        {children}
      </div>
      {/* the name starts with the word on it, so "click Close" by voice finds it */}
      <Button variant="bare" className="page-close" aria-label="Close, back to the chat" onClick={onClose}>Close</Button>
    </div>
  );
}
