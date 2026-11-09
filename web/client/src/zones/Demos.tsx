// The demos on the sign-in page: what seven invented listeners asked for, one at a time, each as the app's own
// request (Starter.tsx's two lines, the fixed words in coral, the blanks in cream), with who asked, what changed for
// an injury, and two minutes of the workout it made to play. Their names, under the player, pick another.
// demos.json is written by `./harmonicfitness demos web` from docs/demos/demos.toml; the clips are on the media bucket.
import { useState } from "react";
import data from "../demos.json";
import { listAnd as list, seconds as secs } from "../lib/format";
import { requestParts, type Part, type RequestValues } from "../lib/request";
import { Button } from "../ui/Button";
import { AudioPlayer } from "../ui/Player";
import { RequestLine } from "../ui/RequestLine";

type Demo = {
  slug: string; name: string; coach: string; minutes: number; ask: string; audio: string;
  moments: { at: string; label: string }[];
  request: { type: string; place: string; when: string; care: string; area?: string };
  card: { tag?: string; who?: string; kit?: string; limit?: string; topics?: string[]; changed?: string };
};

export const DEMOS = data.demos as Demo[];

/** A run of words, each its own span so a change flips them in one after another. */
function Words({ text, from }: { text: string; from: number }) {
  return <>{text.split(/(\s+)/).map((w, i) => /^\s+$/.test(w) ? w :
    <span key={i} className="fl" style={{ animationDelay: `${(from + i / 2) * 22}ms` }}>{w}</span>)}</>;
}

/** A demo's request as the app's own (lib/request.ts), so the two never read differently. */
function values(d: Demo): RequestValues {
  const r = d.request;
  return { coach: d.coach.replace(/^Coach /, ""), minutes: d.minutes, type: r.type, place: r.place, when: r.when,
    body: r.care === "easy" || r.care === "off" ? { [r.area ?? ""]: r.care } : {} };
}

/** The request's lines with the comma or full stop after a blank moved onto it, so the two never part at a line's end. */
function glued(lines: Part[][]): { lines: Part[][]; tails: Map<Part, string> } {
  const tails = new Map<Part, string>();
  const out = lines.map((line) => line.map((p) => ({ ...p })));
  for (const line of out) {
    line.forEach((p, i) => {
      const next = line[i + 1];
      const m = p.blank && next?.fixed.match(/^[,.]/);
      if (m) { tails.set(p, m[0]); next.fixed = next.fixed.slice(1); }
    });
  }
  return { lines: out, tails };
}

function Request({ d }: { d: Demo }) {
  const { lines, tails } = glued(requestParts(values(d)));
  return <RequestLine parts={lines} className="demo-req" fixed={(t, at) => <Words text={t} from={at} />}
    blank={(p, at) => <span className="demo-glue"><span className={`blank${p.tone === "off" ? " off" : ""}`}>
      <Words text={p.blank!} from={at} /></span>{tails.get(p)}</span>} />;
}

export function Demos() {
  const [at, setAt] = useState(0);
  const [turned, setTurned] = useState(false);
  const d = DEMOS[at];
  const pick = (i: number) => { setTurned(true); setAt(i); };

  return (
    <section className="demos" aria-label="Workouts other people asked for">
      <p className="label demo-eyebrow">Workouts for your earbuds, written and voiced fresh each time you ask</p>

      <div className="demo-slides" aria-live="polite">
        {DEMOS.map((x, i) => (
          <div key={x.slug} className={`demo-slide${i === at ? " on" : ""}${i === at && turned ? " turn" : ""}`}
            aria-hidden={i !== at}>
            <p className="label demo-who"><b>{x.name}</b>{x.card.tag && <> · <span>{x.card.tag}</span></>}
              {x.card.topics?.length ? <> · into {list(x.card.topics)}</> : null}</p>
            <Request d={x} />
            <p className="demo-note">
              {x.card.changed ? <><b>What changed for {x.name}.</b> {x.card.changed}</>
                : <>Hear two minutes of the {x.minutes}-minute workout {x.coach} made.</>}
            </p>
          </div>
        ))}
      </div>

      <AudioPlayer key={d.slug} src={d.audio} lazy large className="demo-player" label={`${d.name}'s workout`}
        idle={`2 min of ${d.minutes}`} ticks={d.moments.map((m) => secs(m.at))} />

      <div className="demo-people" role="group" aria-labelledby="demo-people-h">
        <span className="label" id="demo-people-h">Hear another</span>
        {DEMOS.map((x, i) => (
          <Button key={x.slug} variant="bare" className="demo-chip" pressed={i === at} onClick={() => pick(i)}>
            {x.name}</Button>
        ))}
      </div>
      <a className="demo-free" href="#ready-h">Or play a free thirty-minute workout now</a>
    </section>
  );
}
