// The Coaches page (beside Logs): every coach that can speak on the web, as compact cards across the whole width.
// Each says how the coach talks and what a workout costs, and plays its sample (a ready-made coach's, or the
// one kept when a coach was made) from a small player of its own, one sample at a time. The listener's own
// coaches come first in their service's group. A coach whose service has a key is
// chosen with a tap; one that needs a key says which, and can open that key's row in Settings. The page's one
// colour, a soft blue, marks what plays and who is coaching you.
import { useEffect, useRef, useState } from "react";
import type { StartCoach } from "../api";

const an = (word: string) => (/^[aeiou]/i.test(word) ? "an" : "a");

/** "about $1.60 a workout", or nothing when the cost isn't known. */
export function cost(c: StartCoach): string | null {
  return typeof c.usd_per_workout === "number" ? `about $${c.usd_per_workout.toFixed(2)} a workout` : null;
}

const clock = (s: number) => (Number.isFinite(s) ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}` : "0:00");

/** The sample playing now, so starting another pauses it. */
let playing: HTMLAudioElement | null = null;

/** A coach's sample: a play button, the time, and a line to seek along. */
function Sample({ c }: { c: StartCoach }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [on, setOn] = useState(false);
  const [at, setAt] = useState(0);
  const [length, setLength] = useState(0);
  useEffect(() => () => { if (playing === audio.current) playing = null; }, []);

  function toggle() {
    const a = audio.current;
    if (!a) return;
    if (!a.paused) { a.pause(); return; }
    if (playing && playing !== a) playing.pause();
    playing = a;
    void a.play()?.catch(() => setOn(false));
  }

  return (
    <div className={`cg-play${on ? " on" : ""}`}>
      <audio ref={audio} preload="metadata" src={`/api/coaches/${encodeURIComponent(c.slug)}/sample.mp3`}
        aria-label={`Coach ${c.first}'s sample`}
        onPlay={() => setOn(true)} onPause={() => setOn(false)} onEnded={() => { setOn(false); setAt(0); }}
        onTimeUpdate={(e) => setAt(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setLength(e.currentTarget.duration)} />
      <button type="button" className="cg-btn" onClick={toggle}
        aria-label={`${on ? "Pause" : "Play"} Coach ${c.first}'s sample`}>
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
          {on ? <path d="M3 2h3v10H3zM8 2h3v10H8z" fill="currentColor" />
            : <path d="M3.5 1.8v10.4L12 7z" fill="currentColor" />}
        </svg>
      </button>
      <input type="range" className="cg-seek" min={0} max={length || 1} step={0.1} value={at}
        aria-label={`Coach ${c.first}'s sample, position`} disabled={!length}
        style={{ ["--done" as string]: `${length ? (at / length) * 100 : 0}%` }}
        onChange={(e) => { const a = audio.current; if (a) { a.currentTime = Number(e.target.value); setAt(a.currentTime); } }} />
      <span className="cg-time">{length ? (on || at > 0 ? `${clock(at)} / ${clock(length)}` : clock(length)) : ""}</span>
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

export function CoachGallery({ coaches, onCoach, onAddKey }: { coaches: StartCoach[]; onCoach?: (slug: string) => void;
  onAddKey?: (service: string) => void }) {
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
  if (coaches.length === 0) return <p className="cx-s">No coaches yet: add a key to hear them.</p>;
  const addKey = (service: string, label: string) => onAddKey
    ? <button type="button" className="quiet" onClick={() => onAddKey(service)}>{label}</button>
    : <span className="cg-need">{label}</span>;

  if (ready.length > 0) {   // only the coaches your keys can voice, and a line on what another key would add
    return (
      <div className="cg">
        {order(voiced).map((s) => {
          const group = voiced.get(s)!, name = group[0].service_name;
          return (
            <section key={s} className="cg-group" aria-label={`${name} coaches`}>
              <p className="cg-h">{heading(group)}</p>
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
              <p className="cg-h">{heading(group)}</p>
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
export function CoachesPage({ coaches, onCoach, onAddKey, onClose }: { coaches: StartCoach[] | null;
  onCoach: (slug: string) => void; onAddKey: (service: string) => void; onClose: () => void }) {
  const any = coaches?.some((c) => c.ready);
  return (
    <section className="logs coaches wide" aria-labelledby="coaches-title">
      <div className="logs-top">
        <h1 id="coaches-title">Coaches</h1>
        <button type="button" className="quiet" onClick={onClose}>Back to the chat</button>
      </div>
      <p className="logs-note">{any
        ? "Listen to a sample, then tap a coach to choose them."
        : "Listen to a sample, then add the key for the coaches you like. Keys stay in Settings."}</p>
      {coaches === null ? <p className="logs-note">Loading…</p>
        : <CoachGallery coaches={coaches} onCoach={onCoach} onAddKey={onAddKey} />}
    </section>
  );
}
