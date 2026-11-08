// A button that may wait on the server: while `busy` it's switched off, says so to a screen reader, and shows
// `busyLabel` in place of its words. The look is the variant's (theme.css): cream for the one action on a screen,
// an outline for the rest, underlined words for a quiet one, brick for anything that deletes.
import { forwardRef, type ButtonHTMLAttributes } from "react";

const LOOK = {
  primary: "go",          // the screen's one action
  secondary: "act",       // an outlined action
  outline: "go alt",      // an outlined action at the cream button's size
  text: "quiet",          // underlined words
} as const;

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof LOOK; danger?: boolean; busy?: boolean; busyLabel?: string;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({ variant = "secondary", danger = false,
  busy = false, busyLabel, className, disabled, children, type = "button", ...rest }, ref) {
  const cls = [LOOK[variant], danger ? "danger" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <button ref={ref} type={type} className={cls} disabled={disabled || busy} aria-busy={busy || undefined} {...rest}>
      {busy && busyLabel ? busyLabel : children}
    </button>
  );
});
