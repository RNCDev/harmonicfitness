// The sky: a quiet, moving pattern behind every page, after Book of Shapes. Two to choose from in Settings:
// Flow (fine lines drifting sideways) and Field (a grid of dots that a ripple crosses every few seconds, spreading
// from the top right like sound from a speaker). Both hold still when the system asks for reduced motion, and
// brighten a little while the coach works.
import { memo, useEffect, useRef, type ReactNode } from "react";
import { Mark } from "./Mark";

export type SkyKind = "flow" | "field";
export const SKIES: { kind: SkyKind; name: string; about: string }[] = [
  { kind: "flow", name: "Flow", about: "Lines drift slowly across." },
  { kind: "field", name: "Field", about: "A ripple crosses it every few seconds." },
];

const still = () => typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---- Flow: two layers of lines, each repeating every 1440 units, so their drift loops without a seam ----
const W = 1440;
let flowCache: { front: { d: string; o: number }[]; back: { d: string; o: number }[] } | null = null;

function flowLines() {
  if (flowCache) return flowCache;
  const T = (Math.PI * 2) / W;
  const layer = (n: number, top: number, gap: number, amp: number, k1: number, k2: number, op: number) =>
    Array.from({ length: n }, (_, i) => {
      const y0 = top + i * gap;
      let d = "";
      for (let x = 0; x <= W * 2; x += 12) {
        const y = y0 + amp * Math.sin(x * T * k1 + i * 0.22) * Math.sin(i * 0.07 + 0.6) + amp * 0.45 * Math.sin(x * T * k2 + i * 0.5);
        d += `${x ? " L" : "M"}${x},${y.toFixed(1)}`;
      }
      return { d, o: op * Math.sin((Math.PI * (i + 0.5)) / n) };
    });
  flowCache = { front: layer(66, 20, 14, 28, 2, 5, 0.16), back: layer(36, 40, 26, 44, 1, 3, 0.07) };
  return flowCache;
}

function Flow() {
  const { front, back } = flowLines();
  return (
    <svg className="flow" viewBox="0 0 1440 960" preserveAspectRatio="xMidYMid slice">
      <g className="flow-b">{back.map((l, i) => <path key={i} d={l.d} opacity={l.o.toFixed(3)} />)}</g>
      <g className="flow-a">{front.map((l, i) => <path key={i} d={l.d} opacity={l.o.toFixed(3)} />)}</g>
    </svg>
  );
}

// ---- Field: dots on a canvas, so a few thousand of them cost one draw per frame ----
const GAP = 28;          // px between dots
const PERIOD = 7;        // seconds between ripples
const SPEED = 240;       // px a ripple travels per second

/** How lit a dot is at this moment: 0 at rest, 1 at a ripple's crest. */
function crest(t: number, dist: number): number {
  const p = ((((t - dist / SPEED) % PERIOD) + PERIOD) % PERIOD) / PERIOD;
  if (p < 0.05) return p / 0.05;
  if (p < 0.24) return 1 - (p - 0.05) / 0.19;
  return 0;
}

/** Where the ripples start, as a share of the width and height: the top right. */
const ORIGIN = { x: 0.8, y: 0.2 };

function Field() {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvas.current;
    const ctx = c?.getContext?.("2d");
    if (!c || !ctx) return;
    let dots: { x: number; y: number; dist: number; base: number }[] = [];
    let mx = 0, my = 0;
    function layout() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = c!.clientWidth, h = c!.clientHeight;
      c!.width = Math.round(w * dpr);
      c!.height = Math.round(h * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      mx = w * ORIGIN.x;
      my = h * ORIGIN.y;
      const reach = Math.hypot(Math.max(mx, w - mx), Math.max(my, h - my));
      dots = [];
      for (let y = GAP / 2; y < h; y += GAP) {
        for (let x = GAP / 2; x < w; x += GAP) {
          const dist = Math.hypot(x - mx, y - my);
          dots.push({ x, y, dist, base: 0.42 * Math.max(0.25, 1 - dist / (reach * 1.1)) });
        }
      }
    }
    function draw(t: number) {
      ctx!.clearRect(0, 0, c!.clientWidth, c!.clientHeight);
      ctx!.fillStyle = "#EDEAE0";
      for (const d of dots) {
        const a = t < 0 ? 0 : crest(t, d.dist);
        ctx!.globalAlpha = d.base * (0.3 + 0.7 * a);
        ctx!.beginPath();
        ctx!.arc(d.x, d.y, 1.3 * (1 + 1.3 * a), 0, Math.PI * 2);
        ctx!.fill();
      }
      ctx!.globalAlpha = 1;
    }
    layout();
    let frame = 0, last = 0;
    const calm = still();
    const tick = (now: number) => {
      frame = requestAnimationFrame(tick);
      if (now - last < 33) return;   // about 30 frames a second is plenty for this
      last = now;
      draw(now / 1000);
    };
    if (calm) draw(-1);
    else frame = requestAnimationFrame(tick);
    const onResize = () => { layout(); if (calm) draw(-1); };
    window.addEventListener("resize", onResize);
    return () => { cancelAnimationFrame(frame); window.removeEventListener("resize", onResize); };
  }, []);
  return <canvas ref={canvas} className="field" />;
}

/** The background of every page. Fixed behind the content; never takes a click or a screen reader's attention. */
export const Sky = memo(function Sky({ kind = "flow", busy = false }: { kind?: SkyKind; busy?: boolean }) {
  return (
    <div className={`sky sky-${kind}${busy ? " busy" : ""}`} data-sky={kind} aria-hidden="true">
      {kind === "field" ? <Field /> : <Flow />}
    </div>
  );
});

/** A small picture of a sky, for choosing one in Settings. */
export function SkyPreview({ kind }: { kind: SkyKind }) {
  if (kind === "flow") {
    return (
      <svg className="sky-mini" viewBox="0 0 160 90" aria-hidden="true">
        {Array.from({ length: 12 }, (_, i) => {
          let d = "";
          for (let x = 0; x <= 160; x += 4) d += `${x ? " L" : "M"}${x},${(8 + i * 7 + 4 * Math.sin(x * 0.06 + i * 0.4)).toFixed(1)}`;
          return <path key={i} d={d} fill="none" stroke="currentColor" strokeWidth={0.8} opacity={0.45} />;
        })}
      </svg>
    );
  }
  const dots = [];
  for (let y = 5; y < 90; y += 10) {
    for (let x = 5; x < 160; x += 10) {
      const ring = Math.abs(Math.hypot(x - 128, y - 22) - 52) < 6;
      dots.push(<circle key={`${x}-${y}`} cx={x} cy={y} r={ring ? 1.6 : 0.9} fill="currentColor" opacity={ring ? 0.8 : 0.3} />);
    }
  }
  return (
    <svg className="sky-mini" viewBox="0 0 160 90" aria-hidden="true">
      {dots}
    </svg>
  );
}

/** A page with the sky behind one short task: signing in, choosing a password, a server that can't be reached. */
export function Solo({ version, children }: { version?: string; children: ReactNode }) {
  return (
    <div className="app solo-app">
      <Sky />
      <SoloFrame version={version}>{children}</SoloFrame>
    </div>
  );
}

function SoloFrame({ version, children }: { version?: string; children: ReactNode }) {
  return (
    <div className="work">
      <header className="work-top"><Mark version={version} /></header>
      <main className="solo">
        <p className="eyebrow">Audio workouts for your earbuds, written and voiced fresh each time you ask.</p>
        {children}
      </main>
    </div>
  );
}
