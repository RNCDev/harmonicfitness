import { describe, expect, it } from "vitest";
import { flowLines, gardenAt, gardenNodes, paintBloom, paintField, paintGarden, paintWaves, paintWoven, seeds, SvgPen,
  W, weave, type Painter } from "./skyPaint";

/** A path's points, from an SvgPen's or flowLines' "M0,1 L12,3 ..." */
const points = (d: string) => [...d.matchAll(/(-?[\d.]+),(-?[\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])]);

describe("Flow", () => {
  it("draws each line the same at both ends of its 1440 units, so the drift loops without a seam", () => {
    const { front, back } = flowLines();
    expect(flowLines().front).toBe(front);   // worked out once
    expect([front.length, back.length]).toEqual([66, 36]);
    for (const { d, o } of [...front, ...back]) {
      const p = points(d);
      const at = (x: number) => p.find(([px]) => px === x)![1];
      expect(at(W)).toBeCloseTo(at(0), 1);
      expect(at(W * 2)).toBeCloseTo(at(0), 1);
      expect(o).toBeGreaterThan(0);
    }
  });
});

describe("Bloom's seeds", () => {
  it("each a golden angle round from the last, a little further out, filling the disc evenly", () => {
    const s = seeds(1000);
    expect(s).toHaveLength(1000);
    const golden = Math.PI * (3 - Math.sqrt(5));
    s.slice(1).forEach((p, i) => {
      expect(p.a - s[i].a).toBeCloseTo(golden, 10);
      expect(p.r).toBeGreaterThan(s[i].r);
    });
    expect(s[0].r).toBeGreaterThan(0);
    expect(s[999].r).toBeLessThan(1);
    // even by area: a quarter of the seeds inside half the radius
    expect(s.filter((p) => p.r < 0.5).length).toBe(250);
  });
});

describe("Woven", () => {
  const cells = (w: number, h: number, size: number) => (Math.ceil(w / size) + 2) * (Math.ceil(h / size) + 2);

  it("covers the page with a cell to spare past each edge, its threads both ways, over and under in a checkerboard", () => {
    const runs: { across: boolean; over: boolean; threads: number }[] = [];
    weave(400, 240, 80, 6, 0, (across, over, _, run) => {
      const pen = new SvgPen();
      run(pen);
      runs.push({ across, over, threads: pen.d.split("M").length - 1 });
    });
    expect(runs).toHaveLength(cells(400, 240, 80) * 2);
    expect(runs.every((r) => r.threads === 6)).toBe(true);
    // in each cell one way is over and the other under
    for (let i = 0; i < runs.length; i += 2) expect(runs[i].over).not.toBe(runs[i + 1].over);
    expect(runs.filter((r) => r.over)).toHaveLength(runs.length / 2);
  });

  it("never folds a cell over, however the field has drifted", () => {
    for (const t of [0, 3.7, 40, 600]) {
      weave(400, 240, 80, 4, t, (across, _, __, run) => {
        const pen = new SvgPen();
        run(pen);
        const p = points(pen.d);
        for (let k = 0; k < p.length; k += 2) {
          // a thread across runs left to right, one down runs top to bottom
          if (across) expect(p[k + 1][0]).toBeGreaterThan(p[k][0]);
          else expect(p[k + 1][1]).toBeGreaterThan(p[k][1]);
        }
      });
    }
  });
});

describe("Garden", () => {
  it("scatters the same nodes every time, about one to a gap squared, a little past the edges", () => {
    const a = gardenNodes(660, 330, 66);
    expect(a).toEqual(gardenNodes(660, 330, 66));
    expect(a).toHaveLength(50);
    expect(a.every((n) => n.x >= -33 && n.x <= 693 && n.y >= -16.5 && n.y <= 346.5)).toBe(true);
  });

  it("carries each node smoothly, never far from home", () => {
    const nodes = gardenNodes(660, 330, 66);
    expect(gardenAt(nodes, 66, 0)).toEqual(gardenAt(nodes, 66, 0));
    let last = gardenAt(nodes, 66, 0);
    for (let t = 0.5; t < 120; t += 0.5) {
      const now = gardenAt(nodes, 66, t);
      now.forEach(([x, y], i) => {
        expect(Math.hypot(x - nodes[i].x, y - nodes[i].y)).toBeLessThan(2.2 * 66);
        expect(Math.hypot(x - last[i][0], y - last[i][1])).toBeLessThan(66);   // half a second moves it under a gap
      });
      last = now;
    }
  });
});

/** A canvas that keeps what was asked of it: each ink set, each alpha, and the calls. */
function fakeCanvas() {
  const seen = { styles: new Set<string>(), alphas: [] as number[], calls: 0 };
  const ctx = new Proxy({} as Record<string | symbol, unknown>, {
    get: (o, k) => (k in o ? o[k] : () => { seen.calls++; }),
    set: (o, k, v) => {
      if (k === "fillStyle" || k === "strokeStyle") seen.styles.add(v);
      if (k === "globalAlpha") seen.alphas.push(v);
      o[k] = v;
      return true;
    },
  });
  return { ctx: ctx as unknown as CanvasRenderingContext2D, seen };
}

describe("the painters", () => {
  const painters: [string, Painter][] = [["Field", paintField], ["Waves", paintWaves], ["Bloom", paintBloom],
    ["Woven", paintWoven], ["Garden", paintGarden]];

  it.each(painters)("%s draws in the ink it's given, still or moving, and leaves the alpha as it found it", (_, paint) => {
    const { ctx, seen } = fakeCanvas();
    const draw = paint(ctx, 320, 200, "rgb(1, 2, 3)");
    for (const t of [-1, 0, 2.5]) {
      seen.calls = 0;
      draw(t);
      expect(seen.calls).toBeGreaterThan(0);
      expect((ctx as unknown as { globalAlpha: number }).globalAlpha).toBe(1);
    }
    expect([...seen.styles]).toEqual(["rgb(1, 2, 3)"]);
    expect(seen.alphas.every((a) => a >= 0 && a <= 1)).toBe(true);
  });
});
