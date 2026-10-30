// The sky: a quiet, moving pattern behind every page, after Book of Shapes (bookofshapes.com). Four to choose from
// under Background in Settings: Flow (fine lines drifting sideways), Field (a grid of dots that a ripple crosses
// every few seconds, spreading from the top right like sound from a speaker), Arcs (its Brockmann Beethoven Arcs:
// concentric arcs, thicker outward, their turns stepped to a grid of angles, a few stepping round at a time) and
// Waves (its Interference Mesh: level lines bent by two sources of ripples). All hold still when the system asks
// for reduced motion, and brighten a little while the coach works. The code says "sky"; the page says Background.
import { memo, useEffect, useRef, type ReactNode } from "react";
import { Mark } from "./Mark";

export type SkyKind = "flow" | "field" | "arcs" | "waves";
export const SKIES: { kind: SkyKind; name: string; about: string }[] = [
  { kind: "flow", name: "Flow", about: "Lines drift slowly across." },
  { kind: "field", name: "Field", about: "A ripple crosses it every few seconds." },
  { kind: "arcs", name: "Arcs", about: "Rings of arcs turn, a few at a time." },
  { kind: "waves", name: "Waves", about: "Two ripples bend the lines as they meet." },
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

// ---- the canvas backgrounds share one loop: about 30 frames a second, one still frame for reduced motion ----
type Painter = (ctx: CanvasRenderingContext2D, w: number, h: number) => (t: number) => void;

function useCanvas(paint: Painter) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvas.current;
    const ctx = c?.getContext?.("2d");
    if (!c || !ctx) return;
    let draw: (t: number) => void = () => {};
    function layout() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = c!.clientWidth, h = c!.clientHeight;
      c!.width = Math.round(w * dpr);
      c!.height = Math.round(h * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw = paint(ctx!, w, h);
    }
    layout();
    let frame = 0, last = 0;
    const calm = still();
    const tick = (now: number) => {
      frame = requestAnimationFrame(tick);
      if (now - last < 33) return;
      last = now;
      draw(now / 1000);
    };
    if (calm) draw(-1);
    else frame = requestAnimationFrame(tick);
    const onResize = () => { layout(); if (calm) draw(-1); };
    window.addEventListener("resize", onResize);
    return () => { cancelAnimationFrame(frame); window.removeEventListener("resize", onResize); };
  }, [paint]);
  return canvas;
}

const INK = "#EDEAE0";

/** A small seeded random, so a pattern comes out the same on every visit. */
function seeded(seed: number) {
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
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

const paintField: Painter = (ctx, w, h) => {
  const mx = w * ORIGIN.x, my = h * ORIGIN.y;
  const reach = Math.hypot(Math.max(mx, w - mx), Math.max(my, h - my));
  const dots: { x: number; y: number; dist: number; base: number }[] = [];
  for (let y = GAP / 2; y < h; y += GAP) {
    for (let x = GAP / 2; x < w; x += GAP) {
      const dist = Math.hypot(x - mx, y - my);
      dots.push({ x, y, dist, base: 0.42 * Math.max(0.25, 1 - dist / (reach * 1.1)) });
    }
  }
  return (t) => {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = INK;
    for (const d of dots) {
      const a = t < 0 ? 0 : crest(t, d.dist);
      ctx.globalAlpha = d.base * (0.3 + 0.7 * a);
      ctx.beginPath();
      ctx.arc(d.x, d.y, 1.3 * (1 + 1.3 * a), 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  };
};

function Field() {
  return <canvas ref={useCanvas(paintField)} className="field" />;
}

// ---- Arcs: after Book of Shapes' Brockmann Beethoven Arcs (Josef Müller-Brockmann's 1955 Beethoven poster) ----
// Concentric arcs about one centre, thicker toward the outside on an ease curve. Each arc's sweep and turn are
// whole steps of a base angle; each turn is pulled toward one direction, then snapped back to the steps, which
// gathers the arcs into C shapes. Every couple of seconds a few arcs step to a new turn, easing there.
const STEP = Math.PI / 12;              // the base angle: 15 degrees
const snap = (a: number) => Math.round(a / STEP) * STEP;
const lerp = (a: number, b: number, k: number) => a + (b - a) * k;
const ease = (k: number) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);

type Arc = { r: number; width: number; sweep: number; from: number; to: number; at: number };

/** The arcs: radii, widths and sweeps fixed by a seed; the turn toward `toward` (radians) with this much pull. */
function arcSet(n: number, inner: number, outer: number, thin: number, thick: number, toward: number, pull: number, seed = 7) {
  const rnd = seeded(seed);
  const turn = () => snap(lerp(rnd() * Math.PI * 2, toward, pull));
  const arcs: Arc[] = [];
  let r = inner;
  for (let i = 0; i < n; i++) {
    const k = i / (n - 1);
    const width = lerp(thin, thick, k * k);
    const a = turn();
    arcs.push({ r: r + width / 2, width, sweep: snap(lerp(Math.PI * 0.45, Math.PI * 1.6, rnd())), from: a, to: a, at: -99 });
    r += width + lerp(thin * 3, thick * 0.6, k);
    if (r > outer) break;
  }
  return { arcs, turn, rnd };
}

const MOVE = 1.8;     // seconds an arc takes to step round
const EVERY = 2.4;    // seconds between steps

const paintArcs: Painter = (ctx, w, h) => {
  const cx = w * 0.72, cy = h * 0.46;
  const outer = Math.hypot(Math.max(cx, w - cx), Math.max(cy, h - cy));
  const toward = Math.PI;   // the openings face right, so the arcs curl round the words on the left
  const { arcs, turn, rnd } = arcSet(16, Math.min(w, h) * 0.06, outer, 4, 72, toward, 0.55);
  let next = 0;
  return (t) => {
    if (t >= 0 && t >= next) {
      next = t + EVERY;
      for (let j = 0; j < 3; j++) {
        const a = arcs[Math.floor(rnd() * arcs.length)];
        a.from = a.to;
        a.to = turn();
        if (Math.abs(a.to - a.from) < STEP / 2) a.to = a.from + (rnd() < 0.5 ? -2 : 2) * STEP;
        a.at = t;
      }
    }
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = INK;
    ctx.lineCap = "butt";
    arcs.forEach((a, i) => {
      const k = t < 0 ? 1 : Math.min(1, (t - a.at) / MOVE);
      const rot = lerp(a.from, a.to, ease(k));
      ctx.globalAlpha = 0.05 + 0.04 * (i / arcs.length);
      ctx.lineWidth = a.width;
      ctx.beginPath();
      ctx.arc(cx, cy, a.r, rot - a.sweep / 2, rot + a.sweep / 2);
      ctx.stroke();
    });
    ctx.globalAlpha = 1;
  };
};

function Arcs() {
  return <canvas ref={useCanvas(paintArcs)} className="arcs" />;
}

// ---- Waves: after Book of Shapes' Interference Mesh ----
// Two sources send out circular waves; at each point the two waves add, and that sum lifts the level line there,
// so the lines bunch where the waves cancel and spread where they meet in step: the double-slit fringes, as
// contours. The waves travel outward slowly.
const LINE = 12;        // px between level lines
const WAVE = 110;       // px from one crest to the next
const LIFT = 9;         // px a line moves at the full sum of both waves
const RATE = 0.25;      // crests per second

const paintWaves: Painter = (ctx, w, h) => {
  const a = { x: w * 0.62, y: h * 0.5 }, b = { x: w * 0.84, y: h * 0.5 };
  const k = (Math.PI * 2) / WAVE;
  const xs: number[] = [];
  for (let x = -8; x <= w + 8; x += 8) xs.push(x);
  const rows: { y: number; da: number[]; db: number[]; o: number }[] = [];
  for (let y = LINE / 2; y < h + LINE; y += LINE) {
    rows.push({
      y,
      da: xs.map((x) => Math.hypot(x - a.x, y - a.y) * k),
      db: xs.map((x) => Math.hypot(x - b.x, y - b.y) * k),
      o: 0.06 + 0.12 * Math.sin((Math.PI * y) / (h + LINE)),
    });
  }
  return (t) => {
    const ph = (t < 0 ? 0 : t) * RATE * Math.PI * 2;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 1;
    for (const r of rows) {
      ctx.globalAlpha = r.o;
      ctx.beginPath();
      for (let i = 0; i < xs.length; i++) {
        const y = r.y + LIFT * (Math.sin(r.da[i] - ph) + Math.sin(r.db[i] - ph));
        if (i) ctx.lineTo(xs[i], y); else ctx.moveTo(xs[i], y);
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  };
};

function Waves() {
  return <canvas ref={useCanvas(paintWaves)} className="waves" />;
}

/** The background of every page. Fixed behind the content; never takes a click or a screen reader's attention. */
export const Sky = memo(function Sky({ kind = "flow", busy = false }: { kind?: SkyKind; busy?: boolean }) {
  return (
    <div className={`sky sky-${kind}${busy ? " busy" : ""}`} data-sky={kind} aria-hidden="true">
      {kind === "field" ? <Field /> : kind === "arcs" ? <Arcs /> : kind === "waves" ? <Waves /> : <Flow />}
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
  if (kind === "arcs") {
    const { arcs } = arcSet(10, 4, 130, 1.2, 14, Math.PI, 0.55);
    return (
      <svg className="sky-mini" viewBox="0 0 160 90" aria-hidden="true">
        {arcs.map((a, i) => {
          const s0 = a.to - a.sweep / 2, s1 = a.to + a.sweep / 2;
          const [x0, y0, x1, y1] = [112 + a.r * Math.cos(s0), 45 + a.r * Math.sin(s0), 112 + a.r * Math.cos(s1), 45 + a.r * Math.sin(s1)];
          return <path key={i} d={`M${x0.toFixed(1)},${y0.toFixed(1)} A${a.r.toFixed(1)},${a.r.toFixed(1)} 0 ${a.sweep > Math.PI ? 1 : 0} 1 ${x1.toFixed(1)},${y1.toFixed(1)}`}
            fill="none" stroke="currentColor" strokeWidth={a.width.toFixed(1)} opacity={0.3} />;
        })}
      </svg>
    );
  }
  if (kind === "waves") {
    const k = (Math.PI * 2) / 26;
    return (
      <svg className="sky-mini" viewBox="0 0 160 90" aria-hidden="true">
        {Array.from({ length: 14 }, (_, i) => {
          const y0 = 4 + i * 6.5;
          let d = "";
          for (let x = 0; x <= 160; x += 3) {
            const y = y0 + 2.4 * (Math.sin(Math.hypot(x - 92, y0 - 28) * k) + Math.sin(Math.hypot(x - 138, y0 - 58) * k));
            d += `${x ? " L" : "M"}${x},${y.toFixed(1)}`;
          }
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
