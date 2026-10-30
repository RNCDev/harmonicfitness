// The logo: the sound-bar mark (its tallest bar coral) and the wordmark, both drawn in the
// surrounding text colour, so it reads on the blue field and on the sheet alike.
// Their shapes come from brand.ts, which assets/brand/make.py writes.
import { APP_NAME } from "./api";
import { CORAL, FITNESS_OPACITY, MARK, WORDMARK } from "./brand";

const MARK_H = 22;
const WORD_H = 17;

export function Mark({ version }: { version?: string }) {
  return (
    <div className="mark">
      <svg className="mark-icon" width={(MARK.width * MARK_H) / MARK.height} height={MARK_H}
        viewBox={`0 0 ${MARK.width} ${MARK.height}`} aria-hidden="true">
        {MARK.bars.map((b) => (
          <rect key={b.x} x={b.x} y={b.y} width={b.w} height={b.h} rx={b.w / 2}
            fill={b.accent ? CORAL : "currentColor"} />
        ))}
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
