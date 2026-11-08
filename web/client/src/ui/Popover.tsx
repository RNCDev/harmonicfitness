// A panel opened from a control: a list to pick from, under the control that opened it, or a modal dialog in the
// middle of the screen over a scrim. It closes on Escape and on a press outside; a list also closes when focus
// leaves it (Tab), and moves with the arrow keys, Home, End and the first letter of an option. A dialog is drawn on
// the body, holds the keyboard while it's open and puts the page behind it to sleep (useFocusTrap with inert), as
// the Settings drawer does. Focus goes back to the control that opened it, unless the listener
// moved it on themselves.
import { useEffect, useLayoutEffect, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { useFocusTrap } from "../lib/useFocusTrap";

type Props = {
  /** The control that opened it: a list sits under it, and focus returns to it. */
  anchor: HTMLElement | null;
  /** The column a list must stay inside, and is placed in. */
  host: RefObject<HTMLElement>;
  /** Close it; `refocus` is false when the listener already moved focus elsewhere. */
  onClose: (refocus: boolean) => void;
  label: string;
  kind: "listbox" | "dialog";
  className?: string;
  children: ReactNode;
};

const options = (root: HTMLElement | null) => [...(root?.querySelectorAll<HTMLElement>("[role='option']") ?? [])];

export function Popover({ anchor, host, onClose, label, kind, className, children }: Props) {
  const panel = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;

  // a list: under its control, kept inside the column; focus on the chosen option, else the first
  useLayoutEffect(() => {
    const p = panel.current, h = host.current;
    if (kind !== "listbox" || !p || !h || !anchor) return;
    const hr = h.getBoundingClientRect(), ar = anchor.getBoundingClientRect();
    const left = Math.max(0, ar.left - hr.left), over = left + p.offsetWidth - h.clientWidth;
    p.style.left = `${over > 0 ? Math.max(0, left - over) : left}px`;   // placed before it's painted
    p.style.top = `${ar.bottom - hr.top + 8}px`;
    (p.querySelector<HTMLElement>("[aria-selected='true']") ?? options(p)[0])?.focus();
  }, [kind, anchor, host]);

  // a press outside closes it (not on the control that opened it: that one toggles it itself)
  useEffect(() => {
    const away = (e: PointerEvent | MouseEvent) => {
      const t = e.target as Node;
      if (!panel.current?.contains(t) && !anchor?.contains(t)) close.current(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [anchor]);

  // a dialog holds the keyboard, and the page behind it sleeps (it's drawn on the body, beside the page); its Escape
  // closes it
  useFocusTrap(panel, kind === "dialog", { onEscape: () => close.current(true), inert: true });

  function keys(e: React.KeyboardEvent) {
    if (kind !== "listbox") return;
    if (e.key === "Escape") { e.preventDefault(); close.current(true); return; }
    const all = options(panel.current);
    if (!all.length) return;
    const i = all.indexOf(document.activeElement as HTMLElement);
    let to = -1;
    if (e.key === "ArrowDown") to = (i + 1) % all.length;
    else if (e.key === "ArrowUp") to = (i - 1 + all.length) % all.length;
    else if (e.key === "Home") to = 0;
    else if (e.key === "End") to = all.length - 1;
    else if (/^\w$/.test(e.key)) {
      const k = e.key.toLowerCase();
      const order = [...all.slice(i + 1), ...all.slice(0, i + 1)];
      const hit = order.find((o) => o.textContent?.trim().toLowerCase().startsWith(k));
      to = hit ? all.indexOf(hit) : -1;
    }
    if (to < 0) return;
    e.preventDefault();
    all[to].focus();
  }

  // a list closes once focus has left it and its control (Tab, or a click on something that takes focus)
  function left(e: React.FocusEvent) {
    const to = e.relatedTarget as Node | null;
    if (kind === "listbox" && to && !panel.current?.contains(to) && !anchor?.contains(to)) close.current(false);
  }

  if (kind === "dialog") {
    return createPortal(
      <>
        <div className="pick-scrim" aria-hidden="true" data-scrim="" />
        <div className={`pick pick-body${className ? " " + className : ""}`} ref={panel} role="dialog" aria-modal="true"
          aria-label={label}>
          {children}
        </div>
      </>,
      document.body,
    );
  }
  return (
    <div className={`pick${className ? " " + className : ""}`} ref={panel} role="listbox" aria-label={label}
      onKeyDown={keys} onBlur={left}>
      {children}
    </div>
  );
}
