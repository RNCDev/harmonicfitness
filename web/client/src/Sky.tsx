// The sky: a quiet, moving pattern behind every page, after Book of Shapes (bookofshapes.com, by Nikolaj
// Sokolowski). Six to choose from under Background in Settings: Flow (fine lines drifting sideways), Field (a grid
// of dots that a ripple crosses every few seconds, spreading from the top right like sound from a speaker), Waves
// (its Interference Mesh: level lines bent by two sources of ripples), Bloom (its Phyllotaxis Bloom: strokes set out like a
// sunflower's seeds, turning slowly, a pulse passing outward), Strands (its Hex Strands: a breathing hexagon grid
// with bundles of lines wandering through it) and Garden (its Node Garden: drifting points linked to their near
// neighbours). All hold still when the system asks for reduced motion, and brighten a little while the coach works.
// The code says "sky"; the page says Background. (Arcs, after its Brockmann Beethoven Arcs, went in 0.46.2: Book of
// Shapes' licence asks that one not be published. Lissajous went in 0.50.3, for Strands and Garden.)
import { memo, useEffect, useRef, type ReactNode } from "react";
import { Mark } from "./Mark";

export type SkyKind = "flow" | "field" | "waves" | "bloom" | "strands" | "garden";
export const SKIES: { kind: SkyKind; name: string; about: string }[] = [
  { kind: "flow", name: "Flow", about: "Lines drift slowly across." },
  { kind: "field", name: "Field", about: "A ripple crosses it every few seconds." },
  { kind: "waves", name: "Waves", about: "Two ripples bend the lines as they meet." },
  { kind: "bloom", name: "Bloom", about: "A spiral of strokes turns slowly." },
  { kind: "strands", name: "Hex Strands", about: "Lines wander through a breathing grid." },
  { kind: "garden", name: "Node Garden", about: "Drifting points link and let go." },
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
const SEEDS = 1720;   // more seeds as it grew, so they keep their spacing
const BLOOM_SPIN = 0.012;    // radians a second
const BLOOM_PERIOD = 6;      // seconds between pulses

/** The seeds: each one's angle and its distance out, as a share (0..1) of the bloom's radius. */
function seeds(n: number): { a: number; r: number }[] {
  return Array.from({ length: n }, (_, i) => ({ a: i * GOLDEN, r: Math.sqrt((i + 0.5) / n) }));
}

const paintBloom: Painter = (ctx, w, h) => {
  const cx = w * 0.72, cy = h * 0.5, R = Math.min(h * 0.86, w * 0.75);   // large: its edge runs off the page
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

// ---- shared by Strands and Garden: a fixed random sequence, and a slow field that carries points about ----

/** The same "random" numbers every time for one seed (mulberry32), so a page draws the same strands or nodes. */
function rng(seed: number): () => number {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** One swell of the field at (u, v): the slope of sin·sin, turned by `turn`. How sharply it stretches or squeezes
 *  the plane is at most k × amp, so two swells whose k × amp add to under 1 never fold it over. */
function swell(u: number, v: number, k: number, amp: number, a: number, b: number, turn: number): [number, number] {
  const c = Math.cos(turn), s = Math.sin(turn);
  const p = c * u + s * v, q = -s * u + c * v;
  const gp = amp * Math.cos(k * p + a) * Math.sin(k * q + b);
  const gq = amp * Math.sin(k * p + a) * Math.cos(k * q + b);
  return [c * gp - s * gq, s * gp + c * gq];
}

/** Anything that draws lines: a canvas, or the SvgPen below for a preview. */
type Pen = Pick<CanvasRenderingContext2D, "moveTo" | "lineTo" | "bezierCurveTo">;

class SvgPen implements Pen {
  d = "";
  moveTo(x: number, y: number) { this.d += `M${x.toFixed(1)},${y.toFixed(1)}`; }
  lineTo(x: number, y: number) { this.d += `L${x.toFixed(1)},${y.toFixed(1)}`; }
  bezierCurveTo(a: number, b: number, c: number, d: number, e: number, f: number) {
    this.d += `C${a.toFixed(1)},${b.toFixed(1)} ${c.toFixed(1)},${d.toFixed(1)} ${e.toFixed(1)},${f.toFixed(1)}`;
  }
}

/** How much a line at this x shows: faint on the left, where the page's words sit, full on the right. */
const fade = (x: number, w: number) => 0.35 + 0.65 * Math.max(0, Math.min(1, x / w));

// ---- Strands: after Book of Shapes' Hex Strands (itself after markknol's Waved Grid on Turtletoy) ----
// A grid of hexagons warped by a slow field, so cells balloon in places and crowd in others but never overlap: every
// corner moves with the field, and a corner three cells share moves once. Some cells hold a bundle of parallel lines
// from one wall to another, straight across or bending; the next cell carries the bundle on through the wall it came
// in by, so each strand wanders across the grid until a wall stops it. The field drifts, and the cells breathe.
const HEX = 44;              // px from a cell's centre to a corner
const ROOT3 = Math.sqrt(3);
const HEX_STEP = [[1, 0], [0, 1], [-1, 1], [-1, 0], [0, -1], [1, -1]];   // the cell through wall k, in (q, r)

type Bundle = { e: number; x: number; n: number };   // in through wall e, out through wall x, n lines
type Cell = { cx: number; cy: number; bundle?: Bundle };

/** The cells covering w × h with a cell to spare past every edge, and the strands through them. */
function hexCells(w: number, h: number, size: number): Cell[] {
  const cells = new Map<string, Cell>();
  for (let q = -1; q <= Math.ceil(w / (1.5 * size)) + 1; q++) {
    for (let r = Math.floor(-q / 2) - 1; r <= Math.ceil(h / (ROOT3 * size) - q / 2) + 1; r++) {
      cells.set(`${q},${r}`, { cx: 1.5 * size * q, cy: ROOT3 * size * (r + q / 2) });
    }
  }
  const rand = rng(7);
  const keys = [...cells.keys()];
  for (let i = keys.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [keys[i], keys[j]] = [keys[j], keys[i]];
  }
  for (const key of keys) {
    if (cells.get(key)!.bundle || rand() < 0.75) continue;
    let [q, r] = key.split(",").map(Number);
    let e = Math.floor(rand() * 6);
    const n = 3 + Math.floor(rand() * 4);
    for (let step = 0; step < 10; step++) {
      const cell = cells.get(`${q},${r}`);
      if (!cell || cell.bundle) break;                  // off the grid, or another strand's wall
      const turn = rand();
      const x = (e + (turn < 0.4 ? 3 : turn < 0.7 ? 2 : 4)) % 6;   // straight on, or bending either way
      cell.bundle = { e, x, n };
      if (rand() < 0.2) break;
      q += HEX_STEP[x][0];
      r += HEX_STEP[x][1];
      e = (x + 3) % 6;
    }
  }
  return [...cells.values()];
}

/** A cell's six corners as the field has moved them at time t (in seconds; 0 when still). */
function hexCorners(cell: Cell, size: number, t: number): [number, number][] {
  return Array.from({ length: 6 }, (_, k) => {
    const x = cell.cx + size * Math.cos((k * Math.PI) / 3), y = cell.cy + size * Math.sin((k * Math.PI) / 3);
    const u = x / size, v = y / size;
    const [ax, ay] = swell(u, v, 0.42, 0.71, 0.08 * t, 0.055 * t, 0);
    const [bx, by] = swell(u, v, 0.71, 0.21, 1 - 0.06 * t, 2 + 0.07 * t, 0.9);
    return [x + (ax + bx) * size, y + (ay + by) * size];
  });
}

/** Walls 0 to 2 of a cell: the other three are its neighbours', so each wall is drawn once. */
function hexWalls(pen: Pen, v: [number, number][]) {
  pen.moveTo(v[0][0], v[0][1]);
  for (let k = 1; k <= 3; k++) pen.lineTo(v[k][0], v[k][1]);
}

/** A bundle's lines: in through wall e and out through wall x, leaving and meeting each wall square on, so a
 *  strand runs smoothly into the next cell. */
function hexBundle(pen: Pen, v: [number, number][], { e, x, n }: Bundle) {
  const at = (a: [number, number], b: [number, number], f: number) => [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
  const cx = v.reduce((s, p) => s + p[0], 0) / 6, cy = v.reduce((s, p) => s + p[1], 0) / 6;
  const mid = (k: number) => at(v[k], v[(k + 1) % 6], 0.5);
  const [me, mx] = [mid(e), mid(x)];
  for (let i = 0; i < n; i++) {
    const f = 0.2 + (0.6 * i) / (n - 1);
    const [px, py] = at(v[e], v[(e + 1) % 6], f);
    const [qx, qy] = at(v[(x + 1) % 6], v[x], f);   // the far wall walked the other way, so the lines never cross
    pen.moveTo(px, py);
    pen.bezierCurveTo(px + (cx - me[0]) * 0.55, py + (cy - me[1]) * 0.55, qx + (cx - mx[0]) * 0.55, qy + (cy - mx[1]) * 0.55, qx, qy);
  }
}

const paintStrands: Painter = (ctx, w, h) => {
  const cells = hexCells(w, h, HEX);
  return (t) => {
    const tt = t < 0 ? 0 : t;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = INK;
    ctx.lineWidth = 1;
    for (const cell of cells) {
      const v = hexCorners(cell, HEX, tt), o = fade(cell.cx, w);
      ctx.globalAlpha = 0.09 * o;
      ctx.beginPath();
      hexWalls(ctx, v);
      ctx.stroke();
      if (cell.bundle) {
        ctx.globalAlpha = 0.3 * o;
        ctx.beginPath();
        hexBundle(ctx, v, cell.bundle);
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  };
};

function Strands() {
  return <canvas ref={useCanvas(paintStrands)} className="strands" />;
}

// ---- Garden: after Book of Shapes' Node Garden ----
// Points scattered over the page, each joined to those within reach by a line that fades as they part. A slow field
// carries them, so neighbours move together and clusters gather and break up, and each wanders a little on its own,
// so the links keep forming and letting go.
const NODE_GAP = 66;      // px: about one node to every 66 × 66
const REACH = 130;        // px within which two nodes are linked

type Node = { x: number; y: number; p: number; q: number; f: number; g: number };

function gardenNodes(w: number, h: number, gap: number): Node[] {
  const rand = rng(11);
  return Array.from({ length: Math.round((w * h) / (gap * gap)) }, () => ({
    x: (rand() * 1.1 - 0.05) * w, y: (rand() * 1.1 - 0.05) * h,
    p: rand() * Math.PI * 2, q: rand() * Math.PI * 2, f: 0.06 + rand() * 0.08, g: 0.06 + rand() * 0.08,
  }));
}

/** Where every node is at time t (in seconds; 0 when still), the field and its own wander measured in gaps. */
function gardenAt(nodes: Node[], gap: number, t: number): [number, number][] {
  return nodes.map((n) => {
    const [fx, fy] = swell(n.x / gap, n.y / gap, 0.4, 1.2, 0.1 * t, -0.07 * t, 0.4);
    return [n.x + (fx + 0.35 * Math.sin(n.f * t + n.p)) * gap, n.y + (fy + 0.35 * Math.sin(n.g * t + n.q)) * gap];
  });
}

const paintGarden: Painter = (ctx, w, h) => {
  const nodes = gardenNodes(w, h, NODE_GAP);
  return (t) => {
    const at = gardenAt(nodes, NODE_GAP, t < 0 ? 0 : t);
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = INK;
    ctx.fillStyle = INK;
    ctx.lineWidth = 1;
    for (let i = 0; i < at.length; i++) {
      const [x, y] = at[i];
      for (let j = i + 1; j < at.length; j++) {
        const d = Math.hypot(at[j][0] - x, at[j][1] - y);
        if (d >= REACH) continue;
        const near = 1 - d / REACH;
        ctx.globalAlpha = 0.34 * near * near * fade((x + at[j][0]) / 2, w);
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(at[j][0], at[j][1]);
        ctx.stroke();
      }
      ctx.globalAlpha = 0.6 * fade(x, w);
      ctx.beginPath();
      ctx.arc(x, y, 1.6, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  };
};

function Garden() {
  return <canvas ref={useCanvas(paintGarden)} className="garden" />;
}

/** The background of every page. Fixed behind the content; never takes a click or a screen reader's attention. */
export const Sky = memo(function Sky({ kind = "flow", busy = false }: { kind?: SkyKind; busy?: boolean }) {
  return (
    <div className={`sky sky-${kind}${busy ? " busy" : ""}`} data-sky={kind} aria-hidden="true">
      {kind === "field" ? <Field /> : kind === "waves" ? <Waves /> : kind === "bloom" ? <Bloom />
        : kind === "strands" ? <Strands /> : kind === "garden" ? <Garden /> : <Flow />}
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
        {seeds(400).map((p, i) => {
          const d = p.r * 50, len = 1 + 3.5 * p.r;
          const x = 108 + Math.cos(p.a) * d, y = 45 + Math.sin(p.a) * d, ux = Math.cos(p.a) * len / 2, uy = Math.sin(p.a) * len / 2;
          return <line key={i} x1={(x - ux).toFixed(1)} y1={(y - uy).toFixed(1)} x2={(x + ux).toFixed(1)} y2={(y + uy).toFixed(1)}
            stroke="currentColor" strokeWidth={0.7} opacity={0.6} />;
        })}
      </svg>
    );
  }
  if (kind === "strands") {
    const walls = new SvgPen(), lines = new SvgPen();
    for (const cell of hexCells(160, 90, 10)) {
      const v = hexCorners(cell, 10, 0);
      hexWalls(walls, v);
      if (cell.bundle) hexBundle(lines, v, cell.bundle);
    }
    return (
      <svg className="sky-mini" viewBox="0 0 160 90" aria-hidden="true">
        <path d={walls.d} fill="none" stroke="currentColor" strokeWidth={0.5} opacity={0.25} />
        <path d={lines.d} fill="none" stroke="currentColor" strokeWidth={0.6} opacity={0.6} />
      </svg>
    );
  }
  if (kind === "garden") {
    const at = gardenAt(gardenNodes(160, 90, 13), 13, 0), links = [];
    for (let i = 0; i < at.length; i++) {
      for (let j = i + 1; j < at.length; j++) {
        const near = 1 - Math.hypot(at[j][0] - at[i][0], at[j][1] - at[i][1]) / 19;
        if (near > 0) links.push(<line key={`${i}-${j}`} x1={at[i][0].toFixed(1)} y1={at[i][1].toFixed(1)} x2={at[j][0].toFixed(1)}
          y2={at[j][1].toFixed(1)} stroke="currentColor" strokeWidth={0.6} opacity={(0.2 + 0.5 * near).toFixed(2)} />);
      }
    }
    return (
      <svg className="sky-mini" viewBox="0 0 160 90" aria-hidden="true">
        {links}
        {at.map(([x, y], i) => <circle key={i} cx={x.toFixed(1)} cy={y.toFixed(1)} r={0.9} fill="currentColor" opacity={0.7} />)}
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
