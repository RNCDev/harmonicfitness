// The Coaches page (beside Logs): an audition. Every coach that can speak on the web is a small tile, by service; a
// tap puts that coach on the stage beside them and plays their sample (a ready-made coach's, or the one kept when a
// coach was made), one sample at a time (ui/Player.tsx). The stage says how the coach talks and what a workout costs,
// and chooses them. The listener's own coaches come first in their service's group. A coach whose service has no key
// says which key it needs, and can open that key's row in Settings. The page's one colour, a soft blue, marks what
// plays and who is coaching you.
import { useEffect, useRef, useState, type ReactNode, type Ref } from "react";
import type { StartCoach } from "../lib/api";
import { isNarrow } from "../lib/breakpoints";
import { an, dollars } from "../lib/format";
import { Button } from "../ui/Button";
import { Empty, Loadable, Notice } from "../ui/Notice";
import { PageHeader } from "../ui/PageHeader";
import { AudioPlayer, type AudioHandle } from "../ui/Player";

/** "about $1.60 a workout", or nothing when the cost isn't known. */
export function cost(c: StartCoach): string | null {
  return typeof c.usd_per_workout === "number" ? `about ${dollars(c.usd_per_workout)} a workout` : null;
}

/** How the coach talks, in a few words for a tile: the line up to its first comma ("Warm and steady"). */
const gist = (c: StartCoach) => (c.tone || c.description || "").split(/[,;.]/)[0].trim();

/** One coach's tile: their name and a few words. A tap puts them on the stage. */
function Tile({ c, picked, onPick }: { c: StartCoach; picked: boolean; onPick: () => void }) {
  const active = c.current && c.ready;
  return (
    <li className={`cg-tile${active ? " cur" : ""}${picked ? " on" : ""}`}>
      <Button variant="bare" pressed={picked} aria-label={`Hear Coach ${c.first}`} onClick={onPick}>
        <b>Coach {c.first}</b>
        {gist(c) && <span className="cg-gist">{gist(c)}</span>}
        {(active || c.own) && <span className="cg-mark">{active ? "Active" : "Yours"}</span>}
      </Button>
    </li>
  );
}

/** The coach on the stage: who they are, their sample, and the one thing to do next. */
function Stage({ c, player, onCoach, addKey }: { c: StartCoach; player: Ref<AudioHandle>;
  onCoach?: (slug: string) => void; addKey: (service: string, label: string) => ReactNode }) {
  const active = c.current && c.ready;
  const price = cost(c);
  const svc = `${c.service_name}${c.powered_by ? `, powered by ${c.powered_by}` : ""}`;
  return (
    <section className="cg-stage" aria-label={`Coach ${c.first}, on stage`}>
      <p className="label cg-svc">{svc}</p>
      <h2 className="head cg-name">Coach {c.first}</h2>
      {(c.tone || c.description) && <p className="cg-tone">{c.tone || c.description}</p>}
      {c.sample
        ? <AudioPlayer ref={player} large src={`/api/coaches/${encodeURIComponent(c.slug)}/sample.mp3`}
            label={`Coach ${c.first}'s sample`} />
        : c.pending && <p className="cg-note">Voice made on first use (about 1¢)</p>}
      {price && <p className="cg-price">{price}</p>}
      <div className="cg-act">
        {active ? <p className="cg-now">Coaching you now</p>
          : c.ready && onCoach ? <Button variant="primary" onClick={() => onCoach(c.slug)}>Choose {c.first}</Button>
          : addKey(c.service, `Add ${an(c.service_name)} ${c.service_name} key to choose ${c.first}`)}
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

function CoachGallery({ coaches, onCoach, onAddKey, onOpenSettings }: { coaches: StartCoach[];
  onCoach?: (slug: string) => void; onAddKey?: (service: string) => void; onOpenSettings?: () => void }) {
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
  const groups = ready.length > 0 ? order(voiced).map((s) => voiced.get(s)!) : services.map((s) => waiting.get(s)!);
  const listed = groups.flat();

  const [picked, setPicked] = useState<string | null>(null);
  const onStage = listed.find((c) => c.slug === picked) ?? listed.find((c) => c.current && c.ready) ?? listed[0];
  const player = useRef<AudioHandle>(null);
  const side = useRef<HTMLDivElement>(null);
  const playNext = useRef(false);
  // a tap plays the coach it put on the stage, once the stage's player holds their sample
  useEffect(() => {
    if (!playNext.current) return;
    playNext.current = false;
    player.current?.play();
  }, [picked]);
  const pick = (slug: string) => {
    playNext.current = true;
    setPicked(slug);
    // on a narrow screen the stage sits above the tiles: bring it into view
    if (isNarrow()) side.current?.scrollIntoView?.({ block: "nearest" });
  };

  if (coaches.length === 0) {
    return <Empty action={onOpenSettings && <Button onClick={onOpenSettings}>Open Settings</Button>}>
      Coaches show here once a key is added.</Empty>;
  }
  const addKey = (service: string, label: string) => onAddKey
    ? <Button variant="text" onClick={() => onAddKey(service)}>{label}</Button>
    : <span className="cg-need">{label}</span>;

  return (
    <div className="cg">
      <div className="cg-roster">
        {groups.map((group) => {
          const s = group[0].service, name = group[0].service_name;
          return (
            <section key={s} className="cg-group" aria-label={`${name} coaches`}>
              <div className="cg-group-h">
                <p className="label cg-h">{heading(group)}</p>
                {ready.length === 0 && addKey(s, `Add ${an(name)} ${name} key`)}
              </div>
              <ul className="cg-list">
                {group.map((c) => <Tile key={c.slug} c={c} picked={c.slug === onStage.slug} onPick={() => pick(c.slug)} />)}
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
      </div>
      <div className="cg-side" ref={side}>
        <Stage c={onStage} player={player} onCoach={onCoach} addKey={addKey} />
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
  const any = coaches?.some((c) => c.ready);
  return (
    <section className="page wide" aria-labelledby="coaches-title">
      <PageHeader id="coaches-title" title="Coaches" onClose={onClose}>
        <p className="page-note">{any
          ? "Tap a coach to hear them, then choose the one you like."
          : "Tap a coach to hear them, then add the key for the coaches you like."}</p>
      </PageHeader>
      <Notice tone="error">{error}</Notice>
      <Loadable value={coaches} error={loadError} onRetry={onRetry} what="the coaches">
        {(list) => <CoachGallery coaches={list} onCoach={onCoach} onAddKey={onAddKey} onOpenSettings={onOpenSettings} />}
      </Loadable>
    </section>
  );
}
