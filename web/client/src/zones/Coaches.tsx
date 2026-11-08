// The Coaches page (beside Logs): every coach that can speak on the web, as compact cards across the whole width.
// Each says how the coach talks and what a workout costs, and plays its sample (a ready-made coach's, or the
// one kept when a coach was made) from a small player of its own, one sample at a time. The listener's own
// coaches come first in their service's group. A coach whose service has a key is
// chosen with a tap; one that needs a key says which, and can open that key's row in Settings. The page's one
// colour, a soft blue, marks what plays and who is coaching you.
import { createContext, useContext, useEffect, useRef, useState, type MutableRefObject } from "react";
import type { StartCoach } from "../lib/api";
import { an, dollars } from "../lib/format";
import { Button } from "../ui/Button";
import { Empty, Loadable, Notice } from "../ui/Notice";
import { PlayButton, PlayTime, Seek } from "../ui/Player";

/** "about $1.60 a workout", or nothing when the cost isn't known. */
export function cost(c: StartCoach): string | null {
  return typeof c.usd_per_workout === "number" ? `about ${dollars(c.usd_per_workout)} a workout` : null;
}

/** The sample playing now in this gallery, so starting another pauses it. */
const NowPlaying = createContext<MutableRefObject<HTMLAudioElement | null>>({ current: null });

/** A coach's sample: a play button, the time, and a line to seek along. */
function Sample({ c }: { c: StartCoach }) {
  const playing = useContext(NowPlaying);
  const audio = useRef<HTMLAudioElement>(null);
  const [on, setOn] = useState(false);
  const [at, setAt] = useState(0);
  const [length, setLength] = useState(0);
  useEffect(() => () => { if (playing.current === audio.current) playing.current = null; }, [playing]);

  function toggle() {
    const a = audio.current;
    if (!a) return;
    if (!a.paused) { a.pause(); return; }
    if (playing.current && playing.current !== a) playing.current.pause();
    playing.current = a;
    void a.play()?.catch(() => setOn(false));
  }

  const label = `Coach ${c.first}'s sample`;
  return (
    <div className={`player${on ? " on" : ""}`}>
      <audio ref={audio} preload="metadata" src={`/api/coaches/${encodeURIComponent(c.slug)}/sample.mp3`}
        aria-label={label}
        onPlay={() => setOn(true)} onPause={() => setOn(false)} onEnded={() => { setOn(false); setAt(0); }}
        onTimeUpdate={(e) => setAt(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setLength(e.currentTarget.duration)} />
      <PlayButton playing={on} onClick={toggle} label={label} />
      <Seek at={at} length={length} label={`${label}, position`}
        onSeek={(t) => { const a = audio.current; if (a) { a.currentTime = t; setAt(a.currentTime); } }} />
      <PlayTime at={at} length={length} playing={on} />
    </div>
  );
}

function Card({ c, onCoach }: { c: StartCoach; onCoach?: (slug: string) => void }) {
  const price = cost(c);
  const active = c.current && c.ready;
  const choosable = c.ready && !!onCoach;
  return (
    <li className={`cg-card${active ? " cur" : ""}${c.ready ? "" : " off"}${choosable ? " can" : ""}`}>
      {/* the whole card chooses the coach: a button laid over it, beneath the player and any link */}
      {choosable && (
        <button type="button" className="cg-choose" aria-label={`Choose ${c.first}`} aria-pressed={active}
          onClick={() => { if (!active) onCoach!(c.slug); }} />
      )}
      {active && <span className="cg-on">Active</span>}
      <div className="cg-head">
        <b>Coach {c.first}</b>
        <small>{c.own ? "Yours · " : ""}{c.service_name}{price ? ` · ${price}` : ""}</small>
      </div>
      {(c.tone || c.description) && <p className="cg-tone">{c.tone || c.description}</p>}
      {(c.sample || c.pending) && (
        <div className="cg-foot">
          {c.sample ? <Sample c={c} /> : <p className="cg-note">Voice made on first use (about 1¢)</p>}
        </div>
      )}
    </li>
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

export function CoachGallery(props: { coaches: StartCoach[]; onCoach?: (slug: string) => void;
  onAddKey?: (service: string) => void; onOpenSettings?: () => void }) {
  const playing = useRef<HTMLAudioElement | null>(null);
  return <NowPlaying.Provider value={playing}><Gallery {...props} /></NowPlaying.Provider>;
}

function Gallery({ coaches, onCoach, onAddKey, onOpenSettings }: { coaches: StartCoach[];
  onCoach?: (slug: string) => void; onAddKey?: (service: string) => void; onOpenSettings?: () => void }) {
  // yours first, then alphabetical, so a card never moves: choosing one only rings it
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
  if (coaches.length === 0) {
    return <Empty action={onOpenSettings && <Button onClick={onOpenSettings}>Open Settings</Button>}>
      Coaches show here once a key is added.</Empty>;
  }
  const addKey = (service: string, label: string) => onAddKey
    ? <Button variant="text" onClick={() => onAddKey(service)}>{label}</Button>
    : <span className="cg-need">{label}</span>;

  if (ready.length > 0) {   // only the coaches your keys can voice, and a line on what another key would add
    return (
      <div className="cg">
        {order(voiced).map((s) => {
          const group = voiced.get(s)!, name = group[0].service_name;
          return (
            <section key={s} className="cg-group" aria-label={`${name} coaches`}>
              <p className="label cg-h">{heading(group)}</p>
              <ul className="cg-list">{group.map((c) => <Card key={c.slug} c={c} onCoach={onCoach} />)}</ul>
            </section>
          );
        })}
        {services.length > 0 && (
          <p className="cg-more">
            <span>More coaches with another voice key:</span>
            {services.map((s) => {
              const name = waiting.get(s)![0].service_name, n = waiting.get(s)!.length;
              return <span key={s}>{addKey(s, `${name}${n > 1 ? ` (${n})` : ""}`)}</span>;
            })}
          </p>
        )}
      </div>
    );
  }
  // no voice key yet: every coach, by service, to hear first; one key opens a whole group
  return (
    <div className="cg">
      {services.map((s) => {
        const group = waiting.get(s)!, name = group[0].service_name;
        return (
          <section key={s} className="cg-group" aria-label={`${name} coaches`}>
            <div className="cg-group-h">
              <p className="label cg-h">{heading(group)}</p>
              {addKey(s, `Add ${an(name)} ${name} key`)}
            </div>
            <ul className="cg-list">{group.map((c) => <Card key={c.slug} c={c} />)}</ul>
          </section>
        );
      })}
    </div>
  );
}

/** The page itself: a heading, a line on what to do, and the gallery. */
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
      <div className="page-top">
        <h1 className="head" id="coaches-title">Coaches</h1>
        <Button variant="text" onClick={onClose}>Back to the chat</Button>
      </div>
      <p className="page-note">{any
        ? "Listen to a sample, then tap a coach to choose them."
        : "Listen to a sample, then add the key for the coaches you like. Keys stay in Settings."}</p>
      <Notice tone="error">{error}</Notice>
      <Loadable value={coaches} error={loadError} onRetry={onRetry} what="the coaches">
        {(list) => <CoachGallery coaches={list} onCoach={onCoach} onAddKey={onAddKey} onOpenSettings={onOpenSettings} />}
      </Loadable>
    </section>
  );
}
