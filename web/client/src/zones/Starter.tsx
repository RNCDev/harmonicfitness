// The first screen: a request with blanks, filled in from what the app knows about the listener. Tap a blank for
// its choices (a list under it, ui/Popover.tsx); the new words roll in like a scoreboard (ui/Flap.tsx). The second
// line says what to go easy on, picked from the body chart (BodyChart.tsx). "Plan my workout" sends the request
// (lib/request.ts) as the first message; its answers stand in for the check-in. A new listener (no level yet) also
// answers the setup's first questions here, in one go (AboutYou), so the chat asks none of them, and their first
// workout records as soon as it's written: the form says where the script goes and that it's charged to their key.
import { useRef, useState } from "react";
import type { Level as Experience, StartInfo } from "../lib/api";
import { dayPart } from "../lib/format";
import { privacyNote } from "../lib/keys";
import { LEVEL_SAID, LEVELS } from "../lib/levels";
import { aboutMe, areaName, kitWords, MINUTES, requestParts, sentence, suggested, TYPES, whenWords, type About,
  type Level, type SlotKey } from "../lib/request";
import { Quiet, useAction } from "../lib/useAction";
import { ahead, slots, withOffset } from "../lib/when";
import { Button } from "../ui/Button";
import { Field } from "../ui/Field";
import { Flap } from "../ui/Flap";
import { Icon } from "../ui/icons";
import { LevelCards } from "../ui/LevelCards";
import { Failed, Notice } from "../ui/Notice";
import { Popover } from "../ui/Popover";
import { RequestLine } from "../ui/RequestLine";
import { BodyChart } from "./BodyChart";
import { ReadyWorkouts } from "./Ready";

/** Each blank's list, as a screen reader names it. */
const LIST_NAMES: Record<SlotKey, string> = { coach: "Coach", minutes: "Length", place: "Where", type: "Workout", when: "When",
  body: "Anything bothering you today?" };

function Slot({ k, label, text, open, onOpen, tone }: { k: SlotKey; label: string; text: string; open: boolean;
  onOpen: (k: SlotKey, el: HTMLButtonElement) => void; tone?: "off" | "calm" }) {
  return (
    <button type="button" className={`slot${tone ? " " + tone : ""}`} data-k={k} aria-haspopup={k === "body" ? "dialog" : "listbox"}
      aria-expanded={open} aria-label={`${label}: ${text}`} onClick={(e) => onOpen(k, e.currentTarget)}>
      <Flap text={text} />
      <Icon name="chevron-down" size={10} weight={3.6} className="car" />
    </button>
  );
}

const OTHER: { label: string; about: string; line: string; quick?: boolean }[] = [
  { label: "Update an injury or pain", about: "Add, change or clear something that hurts, so every workout works around it.",
    line: "I'd like to update an injury." },
  { label: "Change my equipment", about: "Tell your coach what you have at home, at the gym or when you travel.",
    line: "I'd like to change my equipment." },
  { label: "Update my interests", about: "Tell your coach what you're into and what you've been up to, for things to talk about between sets.",
    line: "I'd like to update my interests." },
  { label: "Finish setting me up", about: "Answer the rest of the setup questions, for workouts that fit you better.",
    line: "Finish setting me up.", quick: true },
];

/** A new listener's answers to the setup's first questions: what to call them, their level, what's at home. */
function AboutYou({ name, level, home, service, onName, onLevel, onHome }: {
  name: string; level: Experience; home: string; service?: string;
  onName: (v: string) => void; onLevel: (v: Experience) => void; onHome: (v: string) => void;
}) {
  return (
    <fieldset className="about">
      <legend className="label">First, about you</legend>
      <Field id="about-name" label="What should your coach call you?" hint="Leave it empty for no name.">
        <input className="input" type="text" autoComplete="given-name" maxLength={40} value={name}
          onChange={(e) => onName(e.target.value)} />
      </Field>
      <p className="label" id="about-level">Which sounds like you?</p>
      <LevelCards choices={LEVELS.map((l) => ({ level: l, said: LEVEL_SAID[l] }))} value={level} onChoose={onLevel}
        labelledBy="about-level" />
      <Field id="about-home" label="What do you have at home to train with?"
        hint="Dumbbells, bands, a bench… Leave it empty for none: your workouts use bodyweight until you say.">
        <input className="input" type="text" maxLength={200} value={home} onChange={(e) => onHome(e.target.value)} />
      </Field>
      <p className="start-note about-note">Your first workout records as soon as it's written, charged to your own key
        (usually less than 1 USD).{service ? " " + privacyNote(service) : ""}</p>
    </fieldset>
  );
}

type Props = {
  info: StartInfo | null;
  /** Sends a line as the first message; false when it was refused. */
  onStart: (line: string, startAt?: string) => Promise<boolean> | void;
  /** The coach the listener picked: made the current coach (and saved) by the page, which updates `info`.
   * Without it, the pick stays in the sentence alone. */
  onCoach?: (slug: string) => void;
  /** Opens the Coaches page: to switch coach, or, with no coach that can speak yet, to choose one. */
  onOpenCoaches?: () => void;
  /** Why the last coach picked didn't hold (the server refused it). */
  coachError?: string | null;
  /** Why the coaches couldn't be loaded (`info` then holds plain defaults), and asking again. */
  loadError?: string | null;
  onRetry?: () => void;
};

export function Starter({ info, onStart, onCoach, onOpenCoaches, coachError = null, loadError = null, onRetry }: Props) {
  const ready = (info?.coaches ?? []).filter((c) => c.ready);
  const kits = info?.kits ?? [];
  const floor: Record<string, Level> = {};
  for (const l of info?.limits ?? []) floor[areaName(l.area, l.side)] = l.level === "off-limits" ? "off" : "easy";

  const [coach, setCoach] = useState<string | null>(null);
  const [minutes, setMinutes] = useState<number | null>(null);
  const [place, setPlace] = useState<string | null>(null);
  const [type, setType] = useState<string | null>(null);
  const [body, setBody] = useState<Record<string, Level> | null>(null);
  /** A time picked for the workout (null: right now). */
  const [at, setAt] = useState<Date | null>(null);
  // a new listener's answers to the setup's first questions (AboutYou)
  const [aboutName, setAboutName] = useState("");
  const [aboutLevel, setAboutLevel] = useState<Experience>("novice");
  const [aboutHome, setAboutHome] = useState("");
  const isNew = info?.new === true;
  const [open, setOpen] = useState<SlotKey | null>(null);
  const wrap = useRef<HTMLElement>(null);
  const anchor = useRef<HTMLButtonElement | null>(null);

  // What the app knows, until the listener changes it.
  const cur = info?.coaches.find((c) => c.current && c.ready) ?? ready[0];
  const v = {
    coach: coach ?? cur?.first ?? (info ? "Coach" : "…"),
    minutes: minutes ?? info?.minutes ?? 25,
    place: place ?? (kits[0] ? kitWords(kits[0]) : "at home"),
    type: type ?? suggested(info) ?? "full-body workout",
    body: body ?? floor,
    when: whenWords(at),
  };

  const close = (refocus = true) => {
    setOpen(null);
    if (refocus) anchor.current?.focus();
  };

  function openSlot(k: SlotKey, el: HTMLButtonElement) {
    if (open === k) return close();
    anchor.current = el;
    setOpen(k);
  }

  const choose = (set: (x: never) => void, value: unknown) => { set(value as never); close(); };

  let options: { label: string; value: unknown; set: (x: never) => void; on: boolean }[] = [];
  if (open === "coach") options = ready.map((c) => ({ label: c.first, value: c, on: c.first === v.coach,
    set: ((c: typeof ready[number]) => { if (onCoach) onCoach(c.slug); else setCoach(c.first); }) as (x: never) => void }));
  if (open === "minutes") options = [...new Set([...MINUTES, v.minutes])].sort((a, b) => a - b)
    .map((m) => ({ label: `${m} minutes`, value: m, on: m === v.minutes, set: setMinutes as (x: never) => void }));
  if (open === "place") options = kits.map((k) => kitWords(k))
    .map((w) => ({ label: w, value: w, on: w === v.place, set: setPlace as (x: never) => void }));
  if (open === "type") options = [...new Set([...TYPES, v.type])]
    .map((t) => ({ label: t, value: t, on: t === v.type, set: setType as (x: never) => void }));
  if (open === "when") options = [{ label: "right now", value: null, on: !at, set: setAt as (x: never) => void },
    ...slots().map((d) => ({ label: ahead(d), value: d, on: !!at && at.getTime() === d.getTime(),
      set: setAt as (x: never) => void }))];


  // busy until the chat takes over; a refused start gives the button back
  const begin = useAction(async () => {
    // a time already passed while the page sat open is a workout now
    const later = at && at.getTime() > Date.now() + 20 * 60000 ? at : null;
    const about: About = { name: aboutName, said: LEVEL_SAID[aboutLevel], home: aboutHome };
    const line = sentence({ ...v, when: whenWords(later) }) + (isNew ? " " + aboutMe(about) : "");
    if ((await onStart(line, later ? withOffset(later) : undefined)) === false) throw new Quiet();
  }, { hold: true });

  // the other asks: busy from the tap until the chat takes over; a refusal gives them back
  const [asked, setAsked] = useState<string | null>(null);
  const ask = useAction(async (line: string) => {
    if ((await onStart(line)) === false) throw new Quiet();
  }, { hold: true });

  const hint = !type && info?.suggest?.reason;
  const shownCoach = ready.find((c) => c.first === v.coach);

  // no coach can speak: choose one, unless the answer never came, which says so with Try again instead
  if (ready.length === 0 && info && !loadError && onOpenCoaches) {
    return (
      <section className="starter" aria-label="Plan a workout">
        <p className="label eyebrow">One more step</p>
        <p className="mad">Choose your coach.</p>
        <p className="start-note step-note">Your key writes the workouts; a coach needs a voice. Hear the coaches, then
          add the key the one you like needs.</p>
        <div className="start-row">
          <Button variant="primary" size="lg" onClick={onOpenCoaches}>Choose a coach</Button>
        </div>
      </section>
    );
  }

  return (
    <section className="starter" ref={wrap} aria-label="Plan a workout" aria-busy={!info}>
      {isNew && <AboutYou name={aboutName} level={aboutLevel} home={aboutHome} service={shownCoach?.service}
        onName={setAboutName} onLevel={setAboutLevel} onHome={setAboutHome} />}
      <p className="label eyebrow">{dayPart(new Date())}{shownCoach ? ` · Coach ${shownCoach.first}, voiced by ${shownCoach.service_name}` : ""}</p>
      <RequestLine parts={requestParts(v)} className="mad" blank={(p) => (
        <Slot k={p.key!} label={p.label!} text={p.blank!} open={open === p.key} onOpen={openSlot} tone={p.tone} />
      )} />
      {hint && <p className="hint">Suggested because of your log: {hint}.</p>}
      <div className="start-row">
        <Button variant="primary" size="lg" onClick={() => void begin.run()} busy={begin.busy} busyLabel="Planning…"
          disabled={ready.length === 0}>{at ? "Plan it for later" : "Plan my workout"}</Button>
        {ready.length === 0 && info && !loadError && <span className="start-note">Add a voice key in Settings first.</span>}
      </div>
      {loadError && <Failed error={loadError} onRetry={onRetry} />}
      <Notice tone="error">{coachError}</Notice>
      <nav className="else" aria-label="Other things you can do">
        <p className="label else-h">Or ask for something else</p>
        <ul className="else-list">
          {/* setup not finished: "Finish setting me up" leads, a little brighter than the rest */}
          {OTHER.filter((o) => !o.quick || info?.setup_quick)
            .sort((a, b) => Number(!!b.quick) - Number(!!a.quick)).map((o) => (
            <li key={o.label}>
              <Button variant="bare" className={`else-a${o.quick ? " lead" : ""}`} busy={ask.busy && asked === o.line}
                disabled={ask.busy} onClick={() => { setAsked(o.line); void ask.run(o.line); }}>
                <span className="else-t">{o.label}</span>
                <span className="else-d">{o.about}</span>
                <span className="else-go" aria-hidden="true">→</span>
              </Button>
            </li>
          ))}
        </ul>
      </nav>
      {isNew && <ReadyWorkouts />}
      {open && open !== "body" && (
        <Popover kind="listbox" anchor={anchor.current} host={wrap} onClose={close} label={LIST_NAMES[open]}>
          {options.map((o) => (
            <button key={o.label} type="button" role="option" aria-selected={o.on} className={`opt${o.on ? " on" : ""}`}
              onClick={() => choose(o.set, o.value)}>{o.label}</button>
          ))}
        </Popover>
      )}
      {open === "body" && (
        <Popover kind="dialog" anchor={anchor.current} host={wrap} onClose={close} label={LIST_NAMES.body}>
          <BodyChart marks={v.body} floor={floor} onChange={setBody} onDone={() => close()} />
        </Popover>
      )}
    </section>
  );
}
