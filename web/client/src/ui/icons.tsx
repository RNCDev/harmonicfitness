// Every icon the app draws: one 24-unit grid, one default line weight (a small icon thickens it so it still
// reads), never announced: the control around it is named.
import type { ReactNode } from "react";

const LINE = {
  gear: <>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </>,
  coaches: <path d="M12 3v18M8 8v8M4 11v2M16 6v12M20 10v4" />,
  logs: <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />,
  plus: <path d="M12 3v18M3 12h18" />,
  billing: <path d="M13.5 3.75h6.75v6.75M20.25 3.75 10.5 13.5M17.25 14.25v4.5a1.5 1.5 0 0 1-1.5 1.5H5.25a1.5 1.5 0 0 1-1.5-1.5V8.25a1.5 1.5 0 0 1 1.5-1.5h4.5" />,
  "chevron-left": <path d="M15 4.5 7.5 12l7.5 7.5" />,
  "chevron-right": <path d="m9 4.5 7.5 7.5L9 19.5" />,
  "chevron-down": <path d="M5 9l7 7 7-7" />,
  "face-positive": <><circle cx="12" cy="12" r="9.5" /><path d="M9 9.5h.01M15 9.5h.01" strokeWidth="2.4" /><path d="M8 14a4.5 4.5 0 0 0 8 0" /></>,
  "face-neutral": <><circle cx="12" cy="12" r="9.5" /><path d="M9 9.5h.01M15 9.5h.01" strokeWidth="2.4" /><path d="M8.5 15h7" /></>,
  "face-negative": <><circle cx="12" cy="12" r="9.5" /><path d="M9 9.5h.01M15 9.5h.01" strokeWidth="2.4" /><path d="M8 16.5a4.5 4.5 0 0 1 8 0" /></>,
} satisfies Record<string, ReactNode>;

const FILLED = {
  play: <path d="M7.5 4.8v14.4L19.5 12z" />,
  pause: <path d="M6.75 4.5h3.9v15h-3.9zM13.35 4.5h3.9v15h-3.9z" />,
} satisfies Record<string, ReactNode>;

type IconName = keyof typeof LINE | keyof typeof FILLED;

/** An icon `size` pixels square. Line icons share one weight; `weight` thickens a small one so it still reads. */
export function Icon({ name, size = 16, weight = 1.75, className }: { name: IconName; size?: number; weight?: number;
  className?: string }) {
  const filled = name in FILLED;
  const shape = filled ? FILLED[name as keyof typeof FILLED] : LINE[name as keyof typeof LINE];
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true"
      fill={filled ? "currentColor" : "none"} stroke={filled ? undefined : "currentColor"}
      strokeWidth={filled ? undefined : weight} strokeLinecap="round" strokeLinejoin="round">
      {shape}
    </svg>
  );
}
