// A button that may wait on the server: while `busy` it's switched off, says so to a screen reader, and shows
// `busyLabel` in place of its words (without one, the button keeps its words and shows it's working). The look is
// the variant's (styles/primitives.css): cream for the one action on a screen, an outline for the rest, underlined words
// for a quiet one, a brick outline to stop what's running, a square outlined icon, and brick for anything that
// deletes. Every button in the app that has one of these looks is this component (layers.test.ts).
import { forwardRef, type ButtonHTMLAttributes } from "react";

const LOOK = {
  primary: "go",          // the screen's one action
  secondary: "act outlined", // an outlined action
  outline: "go alt outlined", // an outlined action at the cream button's size
  text: "quiet",          // underlined words
  stop: "go stop",        // stops what's running
  icon: "icon-btn outlined", // a square outlined icon (its name is the aria-label)
} as const;

/** The cream button's sizes: `lg` for the first screen's one action, `sm` to close a panel. */
const SIZE = { md: "", lg: "start", sm: "done" } as const;

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof LOOK; size?: keyof typeof SIZE; danger?: boolean; busy?: boolean; busyLabel?: string;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({ variant = "secondary", size = "md",
  danger = false, busy = false, busyLabel, className, disabled, children, type = "button", ...rest }, ref) {
  const cls = [LOOK[variant], SIZE[size], danger ? "danger" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <button ref={ref} type={type} className={cls} disabled={disabled || busy} aria-busy={busy || undefined} {...rest}>
      {busy && busyLabel ? busyLabel : children}
      {busy && !busyLabel && <span className="busy-dots" aria-hidden="true">…</span>}
    </button>
  );
});
