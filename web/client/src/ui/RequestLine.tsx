// The request's two lines (lib/request.ts's parts), as the first screen and the sign-in page's demos both show it:
// the fixed words in coral, each blank in cream with its underline. The first screen's blanks are buttons; the
// demos' are words. `at` counts the words before each piece, for a turn that flips them in one after another.
import type { ReactNode } from "react";
import type { Part } from "../lib/request";

const words = (s: string) => s.split(/\s+/).filter(Boolean).length;

export function RequestLine({ parts, className, blank, fixed = (text) => text }: {
  parts: Part[][];
  /** Each line's class; the second line also takes `<className>-2`. */
  className: string;
  blank: (part: Part, at: number) => ReactNode;
  fixed?: (text: string, at: number) => ReactNode;
}) {
  let n = 0;
  const count = (s: string) => { const at = n; n += words(s); return at; };
  return (
    <>
      {parts.map((line, l) => (
        <p key={l} className={`${className}${l ? ` ${className}-2` : ""}`}>
          {line.map((p, i) => {
            const before = count(p.fixed);
            const at = p.blank ? count(p.blank) : n;
            return (
              <span key={i}>
                {p.fixed && fixed(p.fixed, before)}
                {p.blank && blank(p, at)}
              </span>
            );
          })}
        </p>
      ))}
    </>
  );
}
