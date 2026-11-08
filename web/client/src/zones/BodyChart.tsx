// The body chart: what to go easy on or keep off today, head to feet. Each side is a three-way toggle, tapped from
// OK to go easy to keep off and back (lib/bodyMarks.ts); a side the health notes keep off can't be tapped, and says
// how to change it. The summary under the key says what will be sent. A modal dialog (ui/Popover.tsx) over the request.
import { listAnd as list } from "../lib/format";
import { MARK_WORDS, markIn, tap } from "../lib/bodyMarks";
import { bodyWords, GROUP_START, ROWS, SIDED, type Level } from "../lib/request";
import { Button } from "../ui/Button";

type Props = {
  /** Today's marks, and the health notes' floor under them. */
  marks: Record<string, Level>;
  floor: Record<string, Level>;
  onChange: (marks: Record<string, Level>) => void;
  onDone: () => void;
};

export function BodyChart({ marks, floor, onChange, onDone }: Props) {
  const fixedAny = ROWS.some((a) => (SIDED.has(a) ? [`left ${a}`, `right ${a}`] : [a]).some((k) => markIn(floor, k) === "off"));
  const { easy, off } = bodyWords(marks);

  const dot = (k: string, where: "l" | "r" | "both") => {
    const mark = markIn(marks, k);
    const fixed = markIn(floor, k) === "off";
    return (
      <button type="button" className={`bdot outlined ${where} ${mark}`} data-mark={mark} disabled={fixed}
        aria-label={`${k}: ${MARK_WORDS[mark]}`} aria-describedby={fixed ? "body-fixed" : undefined}
        onClick={() => onChange(tap(marks, floor, k))}>{where === "l" ? "L" : where === "r" ? "R" : ""}</button>
    );
  };

  return (
    <>
      <div className="bleft">
        <p className="head pick-h">Anything bothering you today?</p>
        <p className="pick-s">Tap a side to change it: once to go easy, twice to keep off, again for OK.</p>
        {fixedAny && <p className="hint" id="body-fixed">A side in a dashed ring is kept off by your health notes. To change
          it, tell your coach in the chat.</p>}
        <ul className="bkey" aria-label="Key">
          <li><i className="bdot easy" aria-hidden="true" />Go easy</li>
          <li><i className="bdot off" aria-hidden="true" />Keep off</li>
        </ul>
        <div className="bsum" aria-live="polite">
          {easy.length === 0 && off.length === 0 ? <p className="bsum-none">Nothing marked: a full workout.</p> : (
            <dl>
              {easy.length > 0 && <><dt className="label">Go easy</dt><dd>{list(easy)}</dd></>}
              {off.length > 0 && <><dt className="label">Keep off</dt><dd>{list(off)}</dd></>}
            </dl>
          )}
        </div>
        <div className="bfoot">
          <Button variant="text" onClick={() => onChange({ ...floor })}>Clear all</Button>
          <Button variant="primary" size="sm" onClick={onDone}>Done</Button>
        </div>
      </div>
      <div className="bchart" role="group" aria-label="Body, head to feet">
        {ROWS.map((a) => (
          <div key={a} className="brow2">
            {GROUP_START.has(a) && <hr className="bsep" />}
            <span className="barea">{a}</span>
            {SIDED.has(a) ? <>{dot(`left ${a}`, "l")}{dot(`right ${a}`, "r")}</> : dot(a, "both")}
          </div>
        ))}
      </div>
    </>
  );
}
