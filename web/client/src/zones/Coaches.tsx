// The Coaches page (beside Logs): an audition. A player bar holds the top of the page and never changes size: the
// coach you're hearing, their sample (a ready-made coach's, or the one kept when a coach was made, one sample at a
// time, ui/Player.tsx), what a workout costs, and the button that makes them your coach. Below it every coach that
// can speak on the web is a tile: their name and how they talk. A tap puts that coach in the bar and plays them;
// nothing else moves. On the hosted site the tiles are one grid and who makes the voices is a line at the foot;
// elsewhere they're grouped by service, the listener's own first in their service's group, and a coach whose service
// has no key says which key it needs. The page's one colour, a soft blue, marks what plays and who is coaching you.
import { useEffect, useRef, useState, type ReactNode, type Ref } from "react";
import type { StartCoach } from "../lib/api";
import { an, dollars } from "../lib/format";
import { useSite } from "../lib/site";
import { Button } from "../ui/Button";
import { Empty, Loadable, Notice } from "../ui/Notice";
import { PageHeader } from "../ui/PageHeader";
import { AudioPlayer, type AudioHandle } from "../ui/Player";

/** "about $1.60 a workout", or nothing when the cost isn't known. */
export function cost(c: StartCoach): string | null {
  return typeof c.usd_per_workout === "number" ? `about ${dollars(c.usd_per_workout)} a workout` : null;
}

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
function Stage({ c, current, player, onCoach, addKey }: { c: StartCoach; current?: StartCoach;
  player: Ref<AudioHandle>; onCoach?: (slug: string) => void; addKey: (service: string, label: string) => ReactNode }) {
  const { hosted } = useSite();
  const active = c.current && c.ready;
  const price = cost(c);
  const svc = `${c.service_name}${c.powered_by ? `, powered by ${c.powered_by}` : ""}`;
  const about = [!hosted && svc, price].filter(Boolean).join(" · ");
  return (
    <section className="cg-stage" aria-label={`Coach ${c.first}, on stage`}>
      <div className="cg-who">
        <h2 className="head cg-name">Coach {c.first}</h2>
        <p className="cg-about">{about || "\u00a0"}</p>
      </div>
      <div className="cg-play">
        {c.sample
          ? <AudioPlayer ref={player} large src={`/api/coaches/${encodeURIComponent(c.slug)}/sample.mp3`}
              label={`Coach ${c.first}'s sample`} />
          : <p className="cg-note">{c.pending ? "Voice made on first use (about 1\u00a2)" : "No sample yet"}</p>}
      </div>
      <div className="cg-act">
        <div className="cg-act-main">{active ? <p className="cg-now">Coaching you now</p>
          : c.ready && onCoach ? <Button variant="primary" onClick={() => onCoach(c.slug)}>{`Make ${c.first} my coach`}</Button>
          : addKey(c.service, `Add ${an(c.service_name)} ${c.service_name} key to choose ${c.first}`)}</div>
        <p className="cg-yours">{!active && current ? `Your coach: ${current.first}` : "\u00a0"}</p>
      </div>
    </section>
  );
}

/** Services in the order a new listener should meet them: the two whose one key also writes, then the rest. */
const SERVICE_ORDER = ["openrouter", "gemini", "fish", "elevenlabs", "inworld"];
const serviceRank = (s: string) => { const i = SERVICE_ORDER.indexOf(s); return i < 0 ? SERVICE_ORDER.length : i; };

/** A service group's heading: "OpenRouter, powered by ElevenLabs · 6 coaches". */
function heading(group: StartCoach[]): string {
  const c = group[0], by = c.powered_by ? `, powered by ${c.powered_by}` : "";
  return `${c.service_name}${by} · ${group.length === 1 ? "1 coach" : `${group.length} coaches`}`;
}

/** A group of tiles under its heading: a service's; on the hosted site, one group with no heading. */
type Group = { key: string; title?: string; label: string; coaches: StartCoach[]; service?: string };


/** Who makes the voices, for the hosted page's foot: "Voices by Google Gemini, through OpenRouter". */
function credit(list: StartCoach[]): string | null {
  const c = list[0];
  if (!c || list.some((x) => x.service !== c.service || x.powered_by !== c.powered_by)) return null;
  return c.powered_by ? `Voices by ${c.powered_by}, through ${c.service_name}` : `Voices by ${c.service_name}`;
}

function CoachGallery({ coaches, onCoach, onAddKey, onOpenSettings }: { coaches: StartCoach[];
  onCoach?: (slug: string) => void; onAddKey?: (service: string) => void; onOpenSettings?: () => void }) {
  const { hosted } = useSite();
  // yours first, then alphabetical, so a tile never moves: choosing one only marks it
  const byName = (a: StartCoach, b: StartCoach) => Number(b.own) - Number(a.own) || a.first.localeCompare(b.first);
  const ready = coaches.filter((c) => c.ready).sort(byName);
  // coaches by service, each group A to Z: the ones that can speak, and the ones waiting for a key
  const bySvc = (list: StartCoach[]) => {
    const m = new Map<string, StartCoach[]>();
    for (const c of list) m.set(c.service, [...(m.get(c.service) ?? []), c]);
    return m;
  };
  const order = (m: Map<string, StartCoach[]>) => [...m.keys()].sort((a, b) => serviceRank(a) - serviceRank(b));
  const voiced = bySvc(ready);
  const waiting = bySvc(coaches.filter((c) => !c.ready).sort(byName));
  const services = order(waiting);
  // with a voice key, only the coaches it can voice; with none, every coach, to hear first
  const bySvcGroups = ready.length > 0 ? order(voiced).map((s) => voiced.get(s)!) : services.map((s) => waiting.get(s)!);
  const listed = bySvcGroups.flat();
  const groups: Group[] = hosted ? [{ key: "all", label: "Coaches", coaches: [...listed].sort(byName) }] : bySvcGroups.map((g) => ({
    key: g[0].service, title: heading(g), label: `${g[0].service_name} coaches`, coaches: g, service: g[0].service }));

  const [picked, setPicked] = useState<string | null>(null);
  const current = listed.find((c) => c.current && c.ready);
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

  if (coaches.length === 0 && hosted) return <Empty>No coach can speak here just now. Try again in a little while.</Empty>;
  if (coaches.length === 0) {
    return <Empty action={onOpenSettings && <Button onClick={onOpenSettings}>Open Settings</Button>}>
      Coaches show here once a key is added.</Empty>;
  }
  const addKey = (service: string, label: string) => onAddKey
    ? <Button variant="text" onClick={() => onAddKey(service)}>{label}</Button>
    : <span className="cg-need">{label}</span>;

  const foot = hosted ? credit(listed) : null;
  return (
    <div className="cg">
      <Stage c={onStage} current={current} player={player} onCoach={onCoach} addKey={addKey} />
      <div className="cg-roster">
        {groups.map((g) => {
          const name = g.coaches[0].service_name;
          return (
            <section key={g.key} className="cg-group" aria-label={g.label}>
              {g.title && <div className="cg-group-h">
                <p className="label cg-h">{g.title}</p>
                {ready.length === 0 && g.service && addKey(g.service, `Add ${an(name)} ${name} key`)}
              </div>}
              <ul className="cg-grid">
                {g.coaches.map((c) => <Tile key={c.slug} c={c} picked={c.slug === onStage.slug} onPick={() => pick(c.slug)} />)}
              </ul>
            </section>
          );
        })}
        {ready.length > 0 && services.length > 0 && (
          <p className="cg-more">
            <span>More coaches with another voice key:</span>
            {services.map((s) => {
              const name = waiting.get(s)![0].service_name, n = waiting.get(s)!.length;
              return <span key={s}>{addKey(s, `${name}${n > 1 ? ` (${n})` : ""}`)}</span>;
            })}
          </p>
        )}
        {foot && <p className="cg-foot">{foot}</p>}
      </div>
    </div>
  );
}

/** The page itself: a heading, a line on what to do, and the audition. */
export function CoachesPage({ coaches, onCoach, onAddKey, onOpenSettings, onClose, error = null, loadError = null,
  onRetry }: {
  coaches: StartCoach[] | null; onCoach: (slug: string) => void; onAddKey: (service: string) => void;
  onOpenSettings?: () => void; onClose: () => void;
  /** Why the coaches couldn't be loaded, and asking again: shown in place of the gallery, never as "no coaches". */
  loadError?: string | null; onRetry?: () => void;
  /** Why the last coach chosen didn't hold. */
  error?: string | null }) {
  const { hosted } = useSite();
  const any = hosted || coaches?.some((c) => c.ready);
  return (
    <section className="page wide" aria-labelledby="coaches-title">
      <PageHeader id="coaches-title" title="Coaches" onClose={onClose}>
        <p className="page-note">{any
          ? "Tap a name to hear that coach, then make the one you like your coach."
          : "Tap a coach to hear them, then add the key for the coaches you like."}</p>
      </PageHeader>
      <Notice tone="error">{error}</Notice>
      <Loadable value={coaches} error={loadError} onRetry={onRetry} what="the coaches">
        {(list) => <CoachGallery coaches={list} onCoach={onCoach} onAddKey={onAddKey} onOpenSettings={onOpenSettings} />}
      </Loadable>
    </section>
  );
}
