// The logo: the mark (one coral line, a burst of sound) and the wordmark, drawn in the surrounding
// text colour with FITNESS lighter, so it reads on the sky and on a sheet alike.
// Their shapes come from brand.ts, which assets/brand/make.py writes.
import { APP_NAME } from "./api";
import { CORAL, FITNESS_OPACITY, MARK, WORDMARK } from "./brand";

const WORD_H = 19; // the caps' height
const MARK_H = 25; // 1.3 cap heights, as in the brand's lockup

export function Mark({ version }: { version?: string }) {
  return (
    <div className="mark">
      <svg className="mark-icon" width={(MARK.width * MARK_H) / MARK.height} height={MARK_H}
        viewBox={`0 0 ${MARK.width} ${MARK.height}`} aria-hidden="true">
        <path d={MARK.d} fill="none" stroke={CORAL} strokeWidth={MARK.stroke}
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <svg className="mark-name" width={(WORDMARK.width * WORD_H) / WORDMARK.height} height={WORD_H}
        viewBox={`0 0 ${WORDMARK.width} ${WORDMARK.height}`} role="img" aria-label={APP_NAME}>
        <path d={WORDMARK.harmonic} fill="currentColor" />
        <path d={WORDMARK.fitness} fill="currentColor" opacity={FITNESS_OPACITY} />
      </svg>
      {version && <span className="ver">{version}</span>}
    </div>
  );
}
