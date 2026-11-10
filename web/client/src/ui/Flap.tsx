// Words that roll in letter by letter when they change, like a split-flap board (the request's blanks). Still for
// anyone who asks for less motion. A screen reader hears the words once, from the control around them.
import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion as still } from "../lib/motion";

const GLYPHS = "abcdefghijklmnopqrstuvwxyz0123456789";

/** Where each word of a text starts and ends, so a long blank wraps between words, never inside one. */
function words(text: string): [number, number][] {
  const out: [number, number][] = [];
  const re = /\S+/g;
  for (let m = re.exec(text); m; m = re.exec(text)) out.push([m.index, m.index + m[0].length]);
  return out;
}

/** A run of words that flip in one after another when they change (the sign-in page's demos): each its own span,
 * `from` words after the first of the line, so a line's words follow the line before. */
export function FlipWords({ text, from, stagger = 22 }: { text: string; from: number; stagger?: number }) {
  return <>{text.split(/(\s+)/).map((w, i) => /^\s+$/.test(w) ? w :
    <span key={i} className="fl" style={{ animationDelay: `${(from + i / 2) * stagger}ms` }}>{w}</span>)}</>;
}

export function Flap({ text, stagger = 22 }: { text: string; stagger?: number }) {
  const [shown, setShown] = useState<string[]>(() => [...text]);
  const [roll, setRoll] = useState(0);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; setShown([...text]); return; }
    if (still()) { setShown([...text]); return; }
    const chars = [...text];
    const left = chars.map((c, i) => (c === " " ? 0 : 3 + (i % 3)));
    const rand = () => GLYPHS[(Math.random() * GLYPHS.length) | 0];
    setShown(chars.map((c) => (c === " " ? " " : rand())));
    setRoll((r) => r + 1);
    const t = setInterval(() => {
      const next = chars.map((c, i) => {
        if (left[i] <= 0) return c;
        left[i]--;
        return left[i] === 0 ? c : rand();
      });
      setShown(next);
      if (left.every((n) => n <= 0)) clearInterval(t);
    }, 50);
    return () => clearInterval(t);
  }, [text]);
  return (
    <span className="flap" aria-hidden="true">
      {words(text).map(([from, to], w) => (
        <span key={`${roll}-w${w}`}>
          {w > 0 && " "}
          <span className="flw">
            {shown.slice(from, to).map((c, j) => (
              <span key={`${roll}-${from + j}`} className="fl" style={{ animationDelay: `${(from + j) * stagger}ms` }}>{c}</span>
            ))}
          </span>
        </span>
      ))}
    </span>
  );
}
