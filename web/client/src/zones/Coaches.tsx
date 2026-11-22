// The Coaches page (beside Logs): an audition. A player bar holds the top of the page and never changes size: the
// coach you're hearing, their sample (a ready-made coach's, or the one kept when a coach was made, one sample at a
// time, ui/Player.tsx), and the button that makes them your coach. Below it every coach that can speak is a tile in
// one grid, A to Z (the listener's own first): their name and how they talk; who makes the voices is a line at the
// foot. A tap puts that coach in the bar and plays them; nothing else moves. The page's one colour, a soft blue,
// marks what plays and who is coaching you.
import { useEffect, useRef, useState, type Ref } from "react";
import type { StartCoach } from "../lib/api";
import { Button } from "../ui/Button";
import { Empty, Loadable, Notice } from "../ui/Notice";
import { PageHeader } from "../ui/PageHeader";
import { AudioPlayer, type AudioHandle } from "../ui/Player";

/** One coach's tile: their first name, how they talk, and a mark on the one coaching you (or one of your own).
 * A tap puts them in the bar and plays their sample. */
function Tile({ c, picked, onPick }: { c: StartCoach; picked: boolean; onPick: () => void }) {
  const active = c.current && c.ready;
  return (
    <li className={`cg-tile${active ? " cur" : ""}`}>
      <Button variant="bare" pressed={picked} aria-label={`Hear Coach ${c.first}`} onClick={onPick}>
        <span className="cg-tile-top">
          <b className="head cg-tile-name">{c.first}</b>
          {active ? <span className="cg-mark" title="Your coach">{"\u2713"} Your coach</span>
            : c.own && <span className="cg-mark">Yours</span>}
        </span>
        {(c.tone || c.description) && <span className="cg-tile-tone">{c.tone || c.description}</span>}
      </Button>
    </li>
  );
}

/** The bar: the coach you're hearing, their sample, and the one thing to do next. Every slot is always there, so
 * the bar keeps its height whoever is in it. */
function Stage({ c, current, player, onCoach }: { c: StartCoach; current?: StartCoach;
  player: Ref<AudioHandle>; onCoach?: (slug: string) => void }) {
  const active = c.current && c.ready;
  return (
    <section className="cg-stage" aria-label={`Coach ${c.first}, on stage`}>
      <div className="cg-who">
        <h2 className="head cg-name">Coach {c.first}</h2>
        <p className="cg-about">{"\u00a0"}</p>
      </div>
      <div className="cg-play">
        {c.sample
          ? <AudioPlayer ref={player} large src={`/api/coaches/${encodeURIComponent(c.slug)}/sample.mp3`}
              label={`Coach ${c.first}'s sample`} />
          : <p className="cg-note">No sample yet</p>}
      </div>
      <div className="cg-act">
        <div className="cg-act-main">{active ? <p className="cg-now">Coaching you now</p>
          : c.ready && onCoach && <Button variant="primary" onClick={() => onCoach(c.slug)}>{`Make ${c.first} my coach`}</Button>}</div>
        <p className="cg-yours">{!active && current ? `Your coach: ${current.first}` : "\u00a0"}</p>
      </div>
    </section>
  );
}

/** Who makes the voices, for the page's foot: "Voices by Google Gemini, through OpenRouter". */
function credit(list: StartCoach[]): string | null {
  const c = list[0];
  if (!c || list.some((x) => x.service !== c.service || x.powered_by !== c.powered_by)) return null;
  return c.powered_by ? `Voices by ${c.powered_by}, through ${c.service_name}` : `Voices by ${c.service_name}`;
}

function CoachGallery({ coaches, onCoach }: { coaches: StartCoach[]; onCoach?: (slug: string) => void }) {
  // yours first, then alphabetical, so a tile never moves: choosing one only marks it
  const byName = (a: StartCoach, b: StartCoach) => Number(b.own) - Number(a.own) || a.first.localeCompare(b.first);
  const listed = coaches.filter((c) => c.ready).sort(byName);

  const [picked, setPicked] = useState<string | null>(null);
  const current = listed.find((c) => c.current);
  const onStage = listed.find((c) => c.slug === picked) ?? current ?? listed[0];
  const player = useRef<AudioHandle>(null);
  const playNext = useRef(false);
  // a tap plays the coach it put on the stage, once the stage's player holds their sample
  useEffect(() => {
    if (!playNext.current) return;
    playNext.current = false;
    player.current?.play();
  }, [picked]);
  const pick = (slug: string) => {
    playNext.current = true;
    setPicked(slug);   // the bar stays at the top of the page, so nothing scrolls
  };

  if (!onStage) return <Empty>No coach can speak here just now. Try again in a little while.</Empty>;
  const foot = credit(listed);
  return (
    <div className="cg">
      <Stage c={onStage} current={current} player={player} onCoach={onCoach} />
      <div className="cg-roster">
        <section className="cg-group" aria-label="Coaches">
          <ul className="cg-grid">
            {listed.map((c) => <Tile key={c.slug} c={c} picked={c.slug === onStage.slug} onPick={() => pick(c.slug)} />)}
          </ul>
        </section>
        {foot && <p className="cg-foot">{foot}</p>}
      </div>
    </div>
  );
}

/** The page itself: a heading, a line on what to do, and the audition. */
export function CoachesPage({ coaches, onCoach, onClose, error = null, loadError = null, onRetry }: {
  coaches: StartCoach[] | null; onCoach: (slug: string) => void; onClose: () => void;
  /** Why the coaches couldn't be loaded, and asking again: shown in place of the gallery, never as "no coaches". */
  loadError?: string | null; onRetry?: () => void;
  /** Why the last coach chosen didn't hold. */
  error?: string | null }) {
  return (
    <section className="page wide" aria-labelledby="coaches-title">
      <PageHeader id="coaches-title" title="Coaches" onClose={onClose}>
        <p className="page-note">Tap a name to hear that coach, then make the one you like your coach.</p>
      </PageHeader>
      <Notice tone="error">{error}</Notice>
      <Loadable value={coaches} error={loadError} onRetry={onRetry} what="the coaches">
        {(list) => <CoachGallery coaches={list} onCoach={onCoach} />}
      </Loadable>
    </section>
  );
}
