// The poster: the left panel of every page. Seven concentric arcs after Müller-Brockmann, the logo's seven
// bars bent into a sound's ripples: each arc's sweep is its bar's height, the fifth in coral. They draw in
// once as the page loads, and sway while the coach works. Below them, today's coach.
import type { ReactNode } from "react";
import { Mark } from "./Mark";

const CX = 70, CY = 680;
/** Each arc: where it starts (degrees, clockwise from three o'clock) and its colour. Sweeps are 18° per bar unit. */
const ARCS: { start: number; color: string }[] = [
  { start: -112, color: "var(--mist)" },
  { start: 6, color: "var(--sun)" },
  { start: -150, color: "var(--mist)" },
  { start: 24, color: "var(--ink)" },
  { start: -90, color: "var(--coral)" },
  { start: -62, color: "var(--mist)" },
  { start: 64, color: "var(--sun)" },
];
const HEIGHTS = [3, 5, 8, 6, 10, 5, 3];

function arc(r: number, from: number, sweep: number): string {
  const rad = (d: number) => (d * Math.PI) / 180;
  const x0 = CX + r * Math.cos(rad(from)), y0 = CY + r * Math.sin(rad(from));
  const x1 = CX + r * Math.cos(rad(from + sweep)), y1 = CY + r * Math.sin(rad(from + sweep));
  return `M${x0.toFixed(1)} ${y0.toFixed(1)}A${r} ${r} 0 ${sweep > 180 ? 1 : 0} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
}

export function Arcs({ busy = false }: { busy?: boolean }) {
  return (
    <svg className={`arcs${busy ? " busy" : ""}`} viewBox="0 0 440 900" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
      {ARCS.map((a, i) => (
        <path key={i} className="arc" d={arc(58 + i * 42, a.start, HEIGHTS[i] * 18)} pathLength={1}
          stroke={a.color} style={{ animationDelay: `${120 + i * 90}ms, ${i * -0.7}s` }} />
      ))}
      <circle className="arc-dot" cx={CX} cy={CY} r={22} />
    </svg>
  );
}

export function Poster({ version, busy, children }: { version?: string; busy?: boolean; children?: ReactNode }) {
  return (
    <aside className="poster">
      <Arcs busy={busy} />
      <Mark version={version} />
      <div className="poster-foot">{children}</div>
    </aside>
  );
}

/** A page with the poster beside one short task: signing in, choosing a password, a server that can't be reached. */
export function Solo({ version, children }: { version?: string; children: ReactNode }) {
  return (
    <div className="app solo-app">
      <Poster version={version}><p className="poster-tag">Audio workouts for your earbuds, written and voiced fresh each time you ask.</p></Poster>
      <main className="solo">{children}</main>
    </div>
  );
}
