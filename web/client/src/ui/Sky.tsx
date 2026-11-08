// The sky: a quiet, moving pattern behind every page, after Book of Shapes (bookofshapes.com, by Nikolaj
// Sokolowski). Six to choose from under Background in Settings: Flow (fine lines drifting sideways), Field (a grid
// of dots that a ripple crosses every few seconds, spreading from the top right like sound from a speaker), Waves
// (its Interference Mesh: level lines bent by two sources of ripples), Bloom (its Phyllotaxis Bloom: strokes set out like a
// sunflower's seeds, turning slowly, a pulse passing outward), Woven (its Woven Grid: a warped grid of fine threads
// going over and under, like stretched cloth) and Garden (its Node Garden: drifting points linked to their near
// neighbours). All hold still when the system asks for reduced motion, and brighten a little while the coach works.
// The code says "sky"; the page says Background. (Arcs, after its Brockmann Beethoven Arcs, went in 0.46.2: Book of
// Shapes' licence asks that one not be published. Lissajous went in 0.50.3, and Hex Strands, its
// short-lived successor, in 0.50.4.)
import { memo, useEffect, useRef } from "react";
import { prefersReducedMotion, token } from "../lib/motion";
import { flowLines, gardenAt, gardenNodes, paintBloom, paintField, paintGarden, paintWaves, paintWoven, seeds, SvgPen,
  weave, type Painter } from "../lib/skyPaint";

export type SkyKind = "flow" | "field" | "waves" | "bloom" | "woven" | "garden";
export const SKIES: { kind: SkyKind; name: string; about: string }[] = [
  { kind: "flow", name: "Flow", about: "Lines drift slowly across." },
  { kind: "field", name: "Field", about: "A ripple crosses it every few seconds." },
  { kind: "waves", name: "Waves", about: "Two ripples bend the lines as they meet." },
  { kind: "bloom", name: "Bloom", about: "A spiral of strokes turns slowly." },
  { kind: "woven", name: "Woven Grid", about: "Threads stretch like cloth as it shifts." },
  { kind: "garden", name: "Node Garden", about: "Drifting points link and let go." },
];

const still = prefersReducedMotion;

// ---- Flow: SVG lines drifting in two layers (lib/skyPaint.ts's flowLines) ----
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
      draw = paint(ctx!, w, h, token("--text", getComputedStyle(c!).color || FALLBACK_INK));
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

/** The canvases draw in the page's text colour (the --text role, tokens.css), read as each one lays out; where
 * styles aren't loaded, in this. */
const FALLBACK_INK = "white";

function Field() {
  return <canvas ref={useCanvas(paintField)} className="field" />;
}

function Waves() {
  return <canvas ref={useCanvas(paintWaves)} className="waves" />;
}

function Bloom() {
  return <canvas ref={useCanvas(paintBloom)} className="bloom" />;
}

function Woven() {
  return <canvas ref={useCanvas(paintWoven)} className="woven" />;
}

function Garden() {
  return <canvas ref={useCanvas(paintGarden)} className="garden" />;
}

/** The background of every page. Fixed behind the content; never takes a click or a screen reader's attention. */
export const Sky = memo(function Sky({ kind = "flow", busy = false }: { kind?: SkyKind; busy?: boolean }) {
  return (
    <div className={`sky sky-${kind}${busy ? " busy" : ""}`} data-sky={kind} aria-hidden="true">
      {kind === "field" ? <Field /> : kind === "waves" ? <Waves /> : kind === "bloom" ? <Bloom />
        : kind === "woven" ? <Woven /> : kind === "garden" ? <Garden /> : <Flow />}
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
        {seeds(900).map((p, i) => {
          const d = p.r * 75, len = 1 + 3.5 * p.r;
          const x = 108 + Math.cos(p.a) * d, y = 45 + Math.sin(p.a) * d, ux = Math.cos(p.a) * len / 2, uy = Math.sin(p.a) * len / 2;
          return <line key={i} x1={(x - ux).toFixed(1)} y1={(y - uy).toFixed(1)} x2={(x + ux).toFixed(1)} y2={(y + uy).toFixed(1)}
            stroke="currentColor" strokeWidth={0.7} opacity={0.6} />;
        })}
      </svg>
    );
  }
  if (kind === "woven") {
    const over = new SvgPen(), under = new SvgPen();
    weave(160, 90, 24, 5, 0, (_, up, __, run) => run(up ? over : under));
    return (
      <svg className="sky-mini" viewBox="0 0 160 90" aria-hidden="true">
        <path d={under.d} fill="none" stroke="currentColor" strokeWidth={0.5} opacity={0.25} />
        <path d={over.d} fill="none" stroke="currentColor" strokeWidth={0.6} opacity={0.65} />
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
