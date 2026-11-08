// The demos on the sign-in page: what seven invented listeners asked for, one at a time, each as the app's own
// request (Starter.tsx's two lines, the blanks in cream), with two minutes of the workout it made to play. Who
// asked, their kit, what changed for them and the moments to jump to wait behind one more tap. It turns every ten
// seconds until someone plays, taps or tabs into it, and not at all for anyone who asks for less motion.
// demos.json is written by `./harmonicfitness demos web` from docs/demos/demos.toml; the clips are on the media bucket.
import { useEffect, useRef, useState } from "react";
import data from "../demos.json";
import { listAnd as list, seconds as secs } from "../lib/format";
import { requestParts, type RequestValues } from "../lib/request";
import { prefersReducedMotion as still } from "../lib/motion";
import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";
import { AudioPlayer, type AudioHandle } from "../ui/Player";
import { RequestLine } from "../ui/RequestLine";

type Demo = {
  slug: string; name: string; coach: string; minutes: number; ask: string; audio: string;
  moments: { at: string; label: string }[];
  request: { type: string; place: string; when: string; care: string; area?: string };
  card: { tag?: string; who?: string; kit?: string; limit?: string; topics?: string[]; changed?: string };
};

export const DEMOS = data.demos as Demo[];
export const TURN_MS = 10000;


/** A run of words, each its own span so a turn flips them in one after another; `from` counts on across a slide. */
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

function Request({ d }: { d: Demo }) {
  return <RequestLine parts={requestParts(values(d))} className="demo-req" fixed={(t, at) => <Words text={t} from={at} />}
    blank={(p, at) => <span className={`blank${p.tone === "off" ? " off" : ""}`}><Words text={p.blank!} from={at} /></span>} />;
}


export function Demos() {
  const [at, setAt] = useState(0);
  const [turned, setTurned] = useState(false);
  const [held, setHeld] = useState(false);        // someone played, tapped or tabbed in: it stops turning for good
  const [pointing, setPointing] = useState(false);
  const [open, setOpen] = useState(false);
  const player = useRef<AudioHandle>(null);
  const d = DEMOS[at];

  useEffect(() => {
    if (held || pointing || still() || DEMOS.length < 2) return;
    const t = setInterval(() => { setAt((a) => (a + 1) % DEMOS.length); setTurned(true); }, TURN_MS);
    return () => clearInterval(t);
  }, [held, pointing]);

  const go = (i: number) => { setHeld(true); setTurned(true); setAt((i + DEMOS.length) % DEMOS.length); };

  return (
    <section className="demos" aria-roledescription="carousel" aria-label="Workouts other people asked for"
      onMouseEnter={() => setPointing(true)} onMouseLeave={() => setPointing(false)} onFocus={() => setHeld(true)}>
      <p className="label demo-eyebrow">Workouts for your earbuds, written and voiced fresh each time you ask</p>
      <p className="demo-lede">Ask in one sentence. Your coach builds the workout around your body, your kit and your
        time, and fills the rests with stories about what you're into. Here's what seven people asked for.</p>

      <div className="demo-slides" aria-live={held ? "polite" : "off"}>
        {DEMOS.map((x, i) => (
          <div key={x.slug} className={`demo-slide${i === at ? " on" : ""}${i === at && turned ? " turn" : ""}`}
            role="group" aria-roledescription="slide" aria-label={`${i + 1} of ${DEMOS.length}: ${x.name}`} aria-hidden={i !== at}>
            <p className="label demo-who"><b>{x.name}</b>{x.card.tag && <> · <span>{x.card.tag}</span></>}
              {x.card.topics?.length ? <> · into {list(x.card.topics)}</> : null}</p>
            <Request d={x} />
          </div>
        ))}
      </div>

      <div className="demo-controls">
        <AudioPlayer ref={player} src={d.audio} lazy large label={`${d.name}'s workout`} idle="2 min"
          ticks={d.moments.map((m) => secs(m.at))} onTouch={() => setHeld(true)} />
        <div className="demo-nav">
          <Button variant="icon" onClick={() => go(at - 1)} aria-label="Previous ask"><Icon name="chevron-left" weight={2.4} /></Button>
          <div className="demo-dots">
            {DEMOS.map((x, i) => <button key={x.slug} type="button" className="demo-dot" aria-label={`${x.name}'s ask`}
              aria-current={i === at} onClick={() => go(i)} />)}
          </div>
          <Button variant="icon" onClick={() => go(at + 1)} aria-label="Next ask"><Icon name="chevron-right" weight={2.4} /></Button>
        </div>
      </div>

      <div className="demo-more">
        <Button variant="bare" aria-expanded={open} aria-controls="demo-detail" onClick={() => { setHeld(true); setOpen(!open); }}>
          <Icon name="chevron-right" weight={2.4} />About {d.name}, and what you'll hear
        </Button>
        {open && (
          <div className="demo-detail" id="demo-detail">
            <dl>
              <dt className="label">In words</dt><dd>&ldquo;{d.ask}&rdquo;</dd>
              {d.card.who && <><dt className="label">Who</dt><dd>{d.card.who.replace(/^[^,]*,\s*/, "")}</dd></>}
              {d.card.kit && <><dt className="label">Kit</dt><dd>{d.card.kit}</dd></>}
              {d.card.limit && <><dt className="label">Injury</dt><dd>{d.card.limit}</dd></>}
            </dl>
            {d.card.changed && <p className="demo-changed"><b>What changed for {d.name}.</b> {d.card.changed}</p>}
            <ul className="demo-moments">
              {d.moments.map((m) => (
                <li key={m.at}><Button variant="bare" onClick={() => player.current?.play(secs(m.at))}>
                  <span className="demo-at">{m.at}</span><span>{m.label}</span></Button></li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
