// The coach's replies are Markdown, where a single line break joins two lines into one paragraph. The coach
// writes a line break to mean one ("a) Novice" on one line, "b) Experienced" on the next), so each single
// break between two lines of text becomes a hard break. Tables, lists, quotes, headings and code fences keep
// Markdown's own rules.

const BLOCK = /^\s*(\||[-*+] |\d+[.)] |>|#|```|~~~)/;

/** `text` with each single line break between two plain lines of text kept as a line break. */
export function keepLineBreaks(text: string): string {
  const lines = text.split("\n");
  let fenced = false;
  return lines
    .map((line, i) => {
      if (/^\s*(```|~~~)/.test(line)) fenced = !fenced;
      const next = lines[i + 1];
      if (fenced || next === undefined || !line.trim() || !next.trim()) return line;
      if (BLOCK.test(line) || BLOCK.test(next) || / {2}$/.test(line)) return line;
      return line + "  ";
    })
    .join("\n");
}
