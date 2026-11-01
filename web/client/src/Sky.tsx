// The sky: a quiet, moving pattern behind every page, after Book of Shapes (bookofshapes.com, by Nikolaj
// Sokolowski). Five to choose from under Background in Settings: Flow (fine lines drifting sideways), Field (a grid
// of dots that a ripple crosses every few seconds, spreading from the top right like sound from a speaker), Waves
// (its Interference Mesh: level lines bent by two sources of ripples), Bloom (its Phyllotaxis Bloom: strokes set out like a
// sunflower's seeds, turning slowly, a pulse passing outward) and Lissajous (its Lissajous Field: a 2:3 Lissajous figure drawn as short
// horizontal dashes, turning slowly like a trace on an oscilloscope). All hold still when the system asks for
// reduced motion, and brighten a little while the coach works. The code says "sky"; the page says Background.
// (Arcs, after its Brockmann Beethoven Arcs, went in 0.46.2: Book of Shapes' licence asks that one not be published.)
import { memo, useEffect, useRef, type ReactNode } from "react";
import { Mark } from "./Mark";

export type SkyKind = "flow" | "field" | "waves" | "bloom" | "lissajous";
export const SKIES: { kind: SkyKind; name: string; about: string }[] = [
  { kind: "flow", name: "Flow", about: "Lines drift slowly across." },
  { kind: "field", name: "Field", about: "A ripple crosses it every few seconds." },
  { kind: "waves", name: "Waves", about: "Two ripples bend the lines as they meet." },
  { kind: "bloom", name: "Bloom", about: "A spiral of strokes turns slowly." },
  { kind: "lissajous", name: "Lissajous", about: "A looping trace turns slowly." },
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

// ---- Bloom: after Book of Shapes' Phyllotaxis Bloom ----
// Short strokes set out as a sunflower's seeds: each one a golden angle round from the last and a little further out
// (radius by the square root of its number, so they fill the disc evenly), each pointing out from the centre and
// longer toward the edge. The whole turns slowly, and a soft pulse travels outward through it every few seconds.
const GOLDEN = Math.PI * (3 - Math.sqrt(5));
const SEEDS = 1100;   // more seeds as it grew, so they keep their spacing
const BLOOM_SPIN = 0.012;    // radians a second
const BLOOM_PERIOD = 6;      // seconds between pulses

/** The seeds: each one's angle and its distance out, as a share (0..1) of the bloom's radius. */
function seeds(n: number): { a: number; r: number }[] {
  return Array.from({ length: n }, (_, i) => ({ a: i * GOLDEN, r: Math.sqrt((i + 0.5) / n) }));
}

const paintBloom: Painter = (ctx, w, h) => {
  const cx = w * 0.72, cy = h * 0.5, R = Math.min(h * 0.69, w * 0.6);   // large: its edge runs off the page
  const all = seeds(SEEDS);
  return (t) => {
    const tt = t < 0 ? 0 : t;
    const spin = tt * BLOOM_SPIN;
    const wave = t < 0 ? -1 : (tt % BLOOM_PERIOD) / BLOOM_PERIOD * 1.4 - 0.2;   // the pulse's place, centre to edge
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 1.2;
    ctx.lineCap = "round";
    for (const s of all) {
      const lift = Math.max(0, 1 - Math.abs(s.r - wave) / 0.12);              // 1 where the pulse is passing
      const len = (4 + 18 * s.r) * (1 + 0.5 * lift);
      const a = s.a + spin, d = s.r * R;
      const x = cx + Math.cos(a) * d, y = cy + Math.sin(a) * d;
      ctx.globalAlpha = (0.08 + 0.16 * s.r) * (1 + 0.8 * lift);
      ctx.beginPath();
      ctx.moveTo(x - Math.cos(a) * len / 2, y - Math.sin(a) * len / 2);
      ctx.lineTo(x + Math.cos(a) * len / 2, y + Math.sin(a) * len / 2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  };
};

function Bloom() {
  return <canvas ref={useCanvas(paintBloom)} className="bloom" />;
}

// ---- Lissajous: after Book of Shapes' Lissajous Field ----
// The figure x = sin(2s + phase), y = sin(3s), drawn not as a line but as short horizontal dashes on rows a few
// pixels apart: at every row, a dash wherever the curve crosses it, longer where the curve runs flatter. The phase
// turns slowly, so the figure seems to rotate, as on an oscilloscope.
const DASH_GAP = 7;       // px between rows of dashes
const TURN = 0.05;        // radians of phase a second

/** Where the curve crosses height v (-1..1): the x of each crossing (-1..1) and how flat it runs there. */
function crossings(v: number, phase: number): { x: number; flat: number }[] {
  const a = Math.asin(Math.max(-1, Math.min(1, v)));
  const out: { x: number; flat: number }[] = [];
  for (let n = 0; n < 3; n++) {                       // sin(3s) = v: 3s is a or pi - a, each turn round
    for (const three of [a + n * Math.PI * 2, Math.PI - a + n * Math.PI * 2]) {
      const s = three / 3;
      const dx = 2 * Math.cos(2 * s + phase), dy = 3 * Math.cos(3 * s);
      out.push({ x: Math.sin(2 * s + phase), flat: Math.min(4, Math.abs(dx) / Math.max(0.35, Math.abs(dy))) });
    }
  }
  return out;
}

const paintLissajous: Painter = (ctx, w, h) => {
  // large, running off the page's edges: only part of the figure shows at once
  const cx = w * 0.72, cy = h * 0.5, ry = h * 0.68, rx = Math.min(w * 0.5, ry * 1.1);
  const rows: number[] = [];
  for (let y = -ry; y <= ry; y += DASH_GAP) rows.push(y);
  return (t) => {
    const phase = Math.PI / 4 + (t < 0 ? 0 : t) * TURN;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 1.2;
    ctx.globalAlpha = 0.24;
    ctx.beginPath();
    for (const y of rows) {
      for (const c of crossings(y / ry, phase)) {
        const len = 14 + 14 * c.flat;
        ctx.moveTo(cx + c.x * rx - len / 2, cy + y);
        ctx.lineTo(cx + c.x * rx + len / 2, cy + y);
      }
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
  };
};

function Lissajous() {
  return <canvas ref={useCanvas(paintLissajous)} className="lissajous" />;
}

/** The background of every page. Fixed behind the content; never takes a click or a screen reader's attention. */
export const Sky = memo(function Sky({ kind = "flow", busy = false }: { kind?: SkyKind; busy?: boolean }) {
  return (
    <div className={`sky sky-${kind}${busy ? " busy" : ""}`} data-sky={kind} aria-hidden="true">
      {kind === "field" ? <Field /> : kind === "waves" ? <Waves /> : kind === "bloom" ? <Bloom />
        : kind === "lissajous" ? <Lissajous /> : <Flow />}
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
  if (kind === "bloom") {
    return (
      <svg className="sky-mini" viewBox="0 0 160 90" aria-hidden="true">
        {seeds(260).map((p, i) => {
          const d = p.r * 40, len = 1 + 3.5 * p.r;
          const x = 108 + Math.cos(p.a) * d, y = 45 + Math.sin(p.a) * d, ux = Math.cos(p.a) * len / 2, uy = Math.sin(p.a) * len / 2;
          return <line key={i} x1={(x - ux).toFixed(1)} y1={(y - uy).toFixed(1)} x2={(x + ux).toFixed(1)} y2={(y + uy).toFixed(1)}
            stroke="currentColor" strokeWidth={0.7} opacity={0.6} />;
        })}
      </svg>
    );
  }
  if (kind === "lissajous") {
    const dashes = [];
    for (let y = -76; y <= 76; y += 3) {
      for (const [n, c] of crossings(y / 76, Math.PI / 4).entries()) {
        const len = 4 + 4 * c.flat;
        dashes.push(<line key={`${y}-${n}`} x1={110 + c.x * 80 - len / 2} x2={110 + c.x * 80 + len / 2} y1={45 + y} y2={45 + y}
          stroke="currentColor" strokeWidth={0.8} opacity={0.55} />);
      }
    }
    return <svg className="sky-mini" viewBox="0 0 160 90" aria-hidden="true">{dashes}</svg>;
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
