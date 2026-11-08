// The logo: the wordmark, HARMONICFITNESS set in the display face, in the surrounding text colour with FITNESS
// lighter, so it reads on the sky and on a sheet alike. Its shapes come from brand.ts, which assets/brand/make.py
// writes.
//
// The meter (the mark alone) moves only where there's sound: while a workout plays. At rest, or when the system
// asks for reduced motion, it shows the still mark.
import { useEffect, useState } from "react";
import { APP_NAME } from "../lib/api";
import { FITNESS_OPACITY, MARK, UNLIT, WORDMARK, type Form } from "./brand";
import { prefersReducedMotion } from "../lib/motion";

const WORD_H = 19; // the wordmark's height at the header's size

type Levels = { L: number; R: number; peakL: number; peakR: number };

/** A made-up but lively pair of levels, two slow waves and a quicker one per channel, with peaks that fall back
 * slowly. Not the audio's real level: reading it would mean routing the player through Web Audio. */
function useLevels(live: boolean, n: number): Levels | null {
  const [levels, setLevels] = useState<Levels | null>(null);
  useEffect(() => {
    if (!live || prefersReducedMotion()) {
      setLevels(null);
      return;
    }
    let t = 0;
    let peak = { L: 0, R: 0 };
    const id = setInterval(() => {
      const wave = (a: number, b: number, phase: number) =>
        Math.abs(Math.sin(t * a + phase) * 0.7 + Math.sin(t * b) * 0.3);
      const L = Math.round(n * 0.3 + n * 0.7 * wave(1.3, 3.1, 0));
      const R = Math.round(n * 0.3 + n * 0.7 * wave(1.1, 2.7, 1));
      peak = { L: Math.max(L, peak.L - 0.08), R: Math.max(R, peak.R - 0.08) };
      setLevels({ L, R, peakL: Math.round(peak.L), peakR: Math.round(peak.R) });
      t += 0.12;
    }, 110);
    return () => clearInterval(id);
  }, [live, n]);
  return levels;
}

/** The meter's segments as an SVG group, reading the still mark or, while `live`, the moving levels. */
function Segments({ form, live = false }: { form: Form; live?: boolean }) {
  const n = Math.max(...form.segments.map((s) => s.fb));
  const levels = useLevels(live, n);
  const lit = (ch: string, fb: number, still: boolean) => {
    if (!levels || ch === "M") return still;
    const [level, peak] = ch === "L" ? [levels.L, levels.peakL] : [levels.R, levels.peakR];
    return fb <= level || (fb === peak && fb > level);
  };
  return (
    <g className="meter" data-live={levels ? "true" : undefined}>
      {form.segments.map((s, i) => (
        <rect key={i} x={s.x} y={s.y} width={s.w} height={s.h} rx={s.rx || undefined} fill={s.fill}
          opacity={lit(s.ch, s.fb, s.lit) ? undefined : UNLIT} />
      ))}
    </g>
  );
}

/** The meter alone, `height` pixels tall; it moves while `live`. */
export function Meter({ form = "mid", height, live = false, className }: {
  form?: keyof typeof MARK; height: number; live?: boolean; className?: string;
}) {
  const f = MARK[form];
  return (
    <svg className={className} width={(f.width * height) / f.height} height={height}
      viewBox={`0 0 ${f.width} ${f.height}`} aria-hidden="true">
      <Segments form={f} live={live} />
    </svg>
  );
}

/** The wordmark, with the version beside it when given. */
export function Mark({ version }: { version?: string }) {
  return (
    <div className="mark">
      <svg className="mark-name" width={(WORDMARK.width * WORD_H) / WORDMARK.height} height={WORD_H}
        viewBox={`0 0 ${WORDMARK.width} ${WORDMARK.height}`} role="img" aria-label={APP_NAME}>
        <path d={WORDMARK.harmonic} fill="currentColor" />
        <path d={WORDMARK.fitness} fill="currentColor" opacity={FITNESS_OPACITY} />
      </svg>
      {version && <span className="ver">{version}</span>}
    </div>
  );
}
