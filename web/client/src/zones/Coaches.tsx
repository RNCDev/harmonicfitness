// The Coaches page (beside Logs): an audition. A stage across the top holds one coach: their sample (a ready-made
// coach's, or the one kept when a coach was made, one sample at a time, ui/Player.tsx), how they talk, what a workout
// costs, and the button that makes them your coach. Below it every coach that can speak on the web is a name chip; a
// tap puts that coach on the stage and plays them. On the hosted site the chips are Women and Men, and who makes the
// voices is a line at the foot; elsewhere they're by service, the listener's own first in their service's group, and
// a coach whose service has no key says which key it needs. The page's one colour, a soft blue, marks what plays
// and who is coaching you.
import { useEffect, useRef, useState, type ReactNode, type Ref } from "react";
import type { StartCoach } from "../lib/api";
import { isNarrow } from "../lib/breakpoints";
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

/** One coach's chip: their first name, and a mark on the one coaching you (or one of your own). A tap puts them
 * on the stage and plays their sample. */
function Chip({ c, picked, onPick }: { c: StartCoach; picked: boolean; onPick: () => void }) {
  const active = c.current && c.ready;
  return (
    <li className={`cg-chip${active ? " cur" : ""}${picked ? " on" : ""}`}>
      <Button variant="bare" pressed={picked} aria-label={`Hear Coach ${c.first}`} onClick={onPick}>
        <b>{c.first}</b>
        {active ? <span className="cg-mark" title="Your coach">{"\u2713"}<span className="sr"> your coach</span></span>
          : c.own && <span className="cg-mark">Yours</span>}
      </Button>
    </li>
  );
}

/** The coach on the stage: who they are, their sample, and the one thing to do next. */
function Stage({ c, current, player, onCoach, addKey }: { c: StartCoach; current?: StartCoach;
  player: Ref<AudioHandle>; onCoach?: (slug: string) => void; addKey: (service: string, label: string) => ReactNode }) {
  const { hosted } = useSite();
  const active = c.current && c.ready;
  const price = cost(c);
  const svc = `${c.service_name}${c.powered_by ? `, powered by ${c.powered_by}` : ""}`;
  return (
    <section className="cg-stage" aria-label={`Coach ${c.first}, on stage`}>
      {!hosted && <p className="label cg-svc">{svc}</p>}
      <h2 className="head cg-name">Coach {c.first}</h2>
      {c.sample
        ? <AudioPlayer ref={player} large src={`/api/coaches/${encodeURIComponent(c.slug)}/sample.mp3`}
            label={`Coach ${c.first}'s sample`} />
        : c.pending && <p className="cg-note">Voice made on first use (about 1¢)</p>}
      {(c.tone || c.description) && <p className="cg-tone">{c.tone || c.description}</p>}
      {price && <p className="cg-price">{price}</p>}
      <div className="cg-act">
        {active ? <p className="cg-now">Coaching you now</p>
          : c.ready && onCoach ? <Button variant="primary" onClick={() => onCoach(c.slug)}>{`Make ${c.first} my coach`}</Button>
          : addKey(c.service, `Add ${an(c.service_name)} ${c.service_name} key to choose ${c.first}`)}
        {!active && current && <p className="cg-yours">Your coach: {current.first}</p>}
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

/** A group of chips under its heading: a service's, or on the hosted site Women or Men. */
type Group = { key: string; title: string; label: string; coaches: StartCoach[]; service?: string };

/** The hosted site's groups: Women, then Men, then any voice not known as either. */
function byGender(list: StartCoach[]): Group[] {
  const rows: Group[] = [
    { key: "f", title: "Women", label: "Women coaches", coaches: list.filter((c) => c.gender === "f") },
    { key: "m", title: "Men", label: "Men coaches", coaches: list.filter((c) => c.gender === "m") },
    { key: "x", title: "More coaches", label: "More coaches", coaches: list.filter((c) => c.gender !== "f" && c.gender !== "m") },
  ];
  return rows.filter((g) => g.coaches.length > 0);
}

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
  const groups: Group[] = hosted ? byGender(listed) : bySvcGroups.map((g) => ({
    key: g[0].service, title: heading(g), label: `${g[0].service_name} coaches`, coaches: g, service: g[0].service }));

  const [picked, setPicked] = useState<string | null>(null);
  const current = listed.find((c) => c.current && c.ready);
  const onStage = listed.find((c) => c.slug === picked) ?? current ?? listed[0];
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
    // on a narrow screen the chips can scroll the stage away: bring it back into view
    if (isNarrow()) side.current?.scrollIntoView?.({ block: "nearest" });
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
      <div className="cg-side" ref={side}>
        <Stage c={onStage} current={current} player={player} onCoach={onCoach} addKey={addKey} />
      </div>
      <div className="cg-roster">
        {groups.map((g) => {
          const name = g.coaches[0].service_name;
          return (
            <section key={g.key} className="cg-group" aria-label={g.label}>
              <div className="cg-group-h">
                <p className="label cg-h">{g.title}</p>
                {ready.length === 0 && g.service && addKey(g.service, `Add ${an(name)} ${name} key`)}
              </div>
              <ul className="cg-list">
                {g.coaches.map((c) => <Chip key={c.slug} c={c} picked={c.slug === onStage.slug} onPick={() => pick(c.slug)} />)}
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
