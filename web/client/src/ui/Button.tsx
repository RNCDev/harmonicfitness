// A button that may wait on the server: while `busy` it's switched off, says so to a screen reader, and shows
// `busyLabel` in place of its words (without one, the button keeps its words and shows it's working). `pressed`
// marks a toggle that's on (aria-pressed), which every look shows the same way. The look is the variant's
// (styles/primitives.css): cream for the one action on a screen, an outline for the rest, underlined words for a quiet
// one, a brick outline to stop what's running, a square outlined icon, the header's buttons, a picture or card to
// pick (a tile), and brick for anything that deletes; `bare` leaves the look to the className. Every button outside
// ui/ is this component, but for the few custom widgets layers.test.ts names.
import { forwardRef, type ButtonHTMLAttributes } from "react";

const LOOK = {
  primary: "go",          // the screen's one action
  secondary: "act outlined", // an outlined action
  outline: "go alt outlined", // an outlined action at the cream button's size
  text: "quiet",          // underlined words
  stop: "go stop",        // stops what's running
  icon: "icon-btn outlined", // a square outlined icon (its name is the aria-label)
  header: "top-btn outlined", // the header's buttons, over the sky
  tile: "tile outlined",  // a picture or card to pick: ringed when pressed
  bare: "",               // the className says how it looks
} as const;

/** The cream button's sizes: `lg` for the first screen's one action, `sm` to close a panel. */
const SIZE = { md: "", lg: "start", sm: "done" } as const;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof LOOK; size?: keyof typeof SIZE; danger?: boolean; busy?: boolean; busyLabel?: string;
  /** A toggle: on or off (aria-pressed). Leave it out for a plain button. */
  pressed?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({ variant = "secondary", size = "md",
  danger = false, busy = false, busyLabel, pressed, className, disabled, children, type = "button", ...rest }, ref) {
  const cls = [LOOK[variant], SIZE[size], danger ? "danger" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <button ref={ref} type={type} className={cls} disabled={disabled || busy} aria-busy={busy || undefined}
      aria-pressed={pressed} {...rest}>
      {busy && busyLabel ? busyLabel : children}
      {busy && !busyLabel && <span className="busy-dots" aria-hidden="true">…</span>}
    </button>
  );
});
