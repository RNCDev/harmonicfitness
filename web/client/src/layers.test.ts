// How the client's folders may lean on each other: lib/ (logic) and ui/ (shared pieces) never reach into a page;
// a page (zones/) may show another page's component, but takes no helper from it; and the few things every page
// needs (reduced motion, sign-out) live in one place each.
import { describe, expect, it } from "vitest";

const SOURCES = import.meta.glob(["./**/*.{ts,tsx}", "!./**/*.test.{ts,tsx}"], { query: "?raw", import: "default", eager: true }) as Record<string, string>;

/** Each import's source path and the names it takes (types included, flagged). */
function imports(src: string): { from: string; names: { name: string; type: boolean }[] }[] {
  const out: { from: string; names: { name: string; type: boolean }[] }[] = [];
  for (const m of src.matchAll(/import\s+(type\s+)?\{([^}]*)\}\s+from\s+"([^"]+)"/g)) {
    const all = !!m[1];
    const names = m[2].split(",").map((n) => n.trim()).filter(Boolean).map((n) => {
      const type = all || n.startsWith("type ");
      return { name: n.replace(/^type\s+/, "").split(/\s+as\s+/)[0], type };
    });
    out.push({ from: m[3], names });
  }
  return out;
}

const isZone = (path: string) => path.startsWith("./zones/");
/** An import of a page: from a page, any sibling ("./Starter"); from anywhere else, a path through zones/. */
const takesFromAPage = (path: string, from: string) => (isZone(path) ? from.startsWith("./") : /(^|\/)zones\//.test(from));

describe("the client's layers", () => {
  it("lib/ and ui/ never import a page", () => {
    const bad = Object.entries(SOURCES).filter(([p]) => p.startsWith("./lib/") || p.startsWith("./ui/"))
      .flatMap(([p, src]) => imports(src).filter((i) => /zones\//.test(i.from)).map((i) => `${p} ← ${i.from}`));
    expect(bad).toEqual([]);
  });

  it("a page takes only components and types from another page", () => {
    const bad: string[] = [];
    for (const [p, src] of Object.entries(SOURCES)) {
      for (const i of imports(src).filter((i) => takesFromAPage(p, i.from))) {
        for (const n of i.names) if (!n.type && !/^[A-Z]/.test(n.name)) bad.push(`${p} ← ${n.name} from ${i.from}`);
      }
    }
    expect(bad).toEqual([]);
  });

  it("asks about reduced motion in one place", () => {
    const where = Object.entries(SOURCES).filter(([, src]) => src.includes("prefers-reduced-motion")).map(([p]) => p);
    expect(where).toEqual(["./lib/motion.ts"]);
  });

  it("leaves a lost session to api.ts: no page calls back to sign out on NotSignedIn", () => {
    const bad = Object.entries(SOURCES).filter(([, src]) => /instanceof NotSignedIn\)\s*(return\s+)?on\w+\(/.test(src))
      .map(([p]) => p);
    expect(bad).toEqual([]);
  });
});
