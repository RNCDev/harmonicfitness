// The first screen: a request with blanks, filled in from what the app knows about the listener. Tap a blank
// for its choices; the new words roll in like a scoreboard. The second line says what to go easy on, picked
// from a body map of plain areas. "Plan my workout" sends the request as the first message; its answers stand
// in for the check-in.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { StartInfo, StartKit } from "../api";

/** The areas a listener can name, in three groups, top of the body last. */
const GROUPS: { name: string; areas: string[] }[] = [
  { name: "Legs and feet", areas: ["foot", "ankle", "calf", "knee", "hamstring", "hip", "groin"] },
  { name: "Back and middle", areas: ["low back", "rib"] },
  { name: "Arms and neck", areas: ["shoulder", "elbow", "wrist", "neck"] },
];
const SIDED = new Set(["foot", "ankle", "calf", "knee", "hamstring", "hip", "groin", "rib", "shoulder", "elbow", "wrist"]);
const MINUTES = [10, 15, 20, 25, 30, 40, 45, 60];
/** What to do, as it reads after "a 25-minute": the session goals in plain words, and the usual targets. */
const TYPES = ["full-body workout", "strength workout", "cardio workout", "mobility session", "leg workout",
  "upper-body workout", "core workout"];
const GOAL_WORDS: Record<string, string> = { strength: "strength workout", general: "full-body workout",
  conditioning: "cardio workout", mobility: "mobility session" };
const TARGET_WORDS: Record<string, string> = { legs: "leg workout", "upper body": "upper-body workout", core: "core workout" };
const PRESET_WORDS: Record<string, string> = { "hotel-room": "in a hotel room", "hotel-gym": "in a hotel gym",
  "full-gym": "at the gym", bodyweight: "with no equipment" };

/** The words for a kit after "a 25-minute workout": "at home", "in a hotel room", "with my travel kit". */
export function kitWords(k: StartKit): string {
  if (k.preset) return PRESET_WORDS[k.id] ?? `with ${k.label}`;
  return k.id.toLowerCase() === "home" ? "at home" : `with my ${k.label} kit`;
}

type Level = "easy" | "off";
type Side = "left" | "right" | "both" | null;
const areaName = (area: string, side: string | null) => `${side ? side + " " : ""}${area.replace(/-/g, " ")}`;
const baseArea = (key: string) => key.replace(/^(left|right) /, "");

/** The workout type a suggestion picks, when it names one we offer. */
function suggested(info: StartInfo | null): string | null {
  const s = info?.suggest;
  if (!s) return null;
  return (s.target && TARGET_WORDS[s.target]) || GOAL_WORDS[s.goal] || null;
}

function list(xs: string[]): string {
  return xs.length < 3 ? xs.join(" and ") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;
}

/** "a" or "an" before a number of minutes: an 8-minute, an 11-minute, an 18-minute. */
function article(minutes: number): string {
  const s = String(minutes);
  return s.startsWith("8") || s === "11" || s === "18" ? "an" : "a";
}

/** What the body line says, as shown and as sent. */
function bodyWords(body: Record<string, Level>): { easy: string[]; off: string[] } {
  return { easy: Object.keys(body).filter((a) => body[a] === "easy"), off: Object.keys(body).filter((a) => body[a] === "off") };
}

/** The request as it's sent. */
export function sentence(v: { coach: string; minutes: number; place: string; type: string; body: Record<string, Level> }): string {
  const { easy, off } = bodyWords(v.body);
  let care = "Nothing's bothering me today.";
  if (easy.length && off.length) care = `Go easy on my ${list(easy)}, and keep off my ${list(off)} today.`;
  else if (easy.length) care = `Go easy on my ${list(easy)} today.`;
  else if (off.length) care = `Keep off my ${list(off)} today.`;
  return `Hey, coach ${v.coach}, I'd like ${article(v.minutes)} ${v.minutes}-minute ${v.type} ${v.place}. ${care}`;
}

const still = () => typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const GLYPHS = "abcdefghijklmnopqrstuvwxyz0123456789";

/** Words that roll in letter by letter when they change, like a split-flap board. */
function Flap({ text }: { text: string }) {
  const [shown, setShown] = useState<string[]>(() => [...text]);
  const [roll, setRoll] = useState(0);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; setShown([...text]); return; }
    if (still()) { setShown([...text]); return; }
    const chars = [...text];
    const left = chars.map((c, i) => (c === " " ? 0 : 3 + (i % 3)));
    const rand = () => GLYPHS[(Math.random() * GLYPHS.length) | 0];
    setShown(chars.map((c) => (c === " " ? " " : rand())));
    setRoll((r) => r + 1);
    const t = setInterval(() => {
      const next = chars.map((c, i) => {
        if (left[i] <= 0) return c;
        left[i]--;
        return left[i] === 0 ? c : rand();
      });
      setShown(next);
      if (left.every((n) => n <= 0)) clearInterval(t);
    }, 50);
    return () => clearInterval(t);
  }, [text]);
  return (
    <span className="flap" aria-hidden="true">
      {shown.map((c, i) => (
        <span key={`${roll}-${i}`} className="fl" style={{ animationDelay: `${i * 22}ms` }}>{c === " " ? "\u00a0" : c}</span>
      ))}
    </span>
  );
}

type SlotKey = "coach" | "minutes" | "place" | "type" | "body";

/** Each blank's list, as a screen reader names it. */
const LIST_NAMES: Record<SlotKey, string> = { coach: "Coach", minutes: "Length", place: "Where", type: "Workout",
  body: "Anything bothering you today?" };

function Slot({ k, label, text, open, onOpen, tone }: { k: SlotKey; label: string; text: string; open: boolean;
  onOpen: (k: SlotKey, el: HTMLButtonElement) => void; tone?: "off" | "calm" }) {
  return (
    <button type="button" className={`slot${tone ? " " + tone : ""}`} data-k={k} aria-haspopup={k === "body" ? "dialog" : "listbox"}
      aria-expanded={open} aria-label={`${label}: ${text}`} onClick={(e) => onOpen(k, e.currentTarget)}>
      <Flap text={text} />
      <svg className="car" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
        <path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    </button>
  );
}

const OTHER: { label: string; about: string; line: string; fill?: boolean; quick?: boolean }[] = [
  { label: "Update an injury or pain", about: "Add, change or clear something that hurts, so every workout works around it.",
    line: "I'd like to update an injury." },
  { label: "Change my equipment", about: "Tell your coach what you have at home, at the gym or when you travel.",
    line: "I'd like to change my equipment." },
  { label: "Choose what I hear in the rests", about: "Pick the news, topics, puzzles and videos your coach talks about between sets.",
    line: "I'd like to change what fills the rests: my interests, news, puzzles and videos." },
  { label: "Pick a different coach", about: "Hear the other coaches, or make a coach of your own.", line: "I want a new coach." },
  { label: "Give feedback on my last workout", about: "Too long, too easy, loved a story: say so and the next one changes.",
    line: "Feedback on my last workout: ", fill: true },
  { label: "See how my week is going", about: "What you've trained this week, and what's due next.", line: "How's my week going?" },
  { label: "Finish setting me up", about: "Answer the rest of the setup questions, for workouts that fit you better.",
    line: "Finish setting me up.", quick: true },
];

type Props = {
  info: StartInfo | null;
  /** Sends a line as the first message; false when it was refused. */
  onStart: (line: string) => Promise<boolean> | void;
  /** Puts a line in the text box to finish by hand. */
  onFill: (line: string) => void;
  /** The coach the listener picked, for the poster. */
  onCoach?: (slug: string) => void;
};

export function Starter({ info, onStart, onFill, onCoach }: Props) {
  const ready = (info?.coaches ?? []).filter((c) => c.ready);
  const kits = info?.kits ?? [];
  const floor: Record<string, Level> = {};
  for (const l of info?.limits ?? []) floor[areaName(l.area, l.side)] = l.level === "off-limits" ? "off" : "easy";

  const [coach, setCoach] = useState<string | null>(null);
  const [minutes, setMinutes] = useState<number | null>(null);
  const [place, setPlace] = useState<string | null>(null);
  const [type, setType] = useState<string | null>(null);
  const [body, setBody] = useState<Record<string, Level> | null>(null);
  const [open, setOpen] = useState<{ k: SlotKey; left: number; top: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const wrap = useRef<HTMLElement>(null);
  const pick = useRef<HTMLDivElement>(null);
  const anchor = useRef<HTMLButtonElement | null>(null);

  // What the app knows, until the listener changes it.
  const cur = info?.coaches.find((c) => c.current && c.ready) ?? ready[0];
  const v = {
    coach: coach ?? cur?.first ?? "Coach",
    minutes: minutes ?? info?.minutes ?? 25,
    place: place ?? (kits[0] ? kitWords(kits[0]) : "at home"),
    type: type ?? suggested(info) ?? "full-body workout",
    body: body ?? floor,
  };

  const close = (refocus = true) => {
    setOpen(null);
    if (refocus) anchor.current?.focus();
  };

  function openSlot(k: SlotKey, el: HTMLButtonElement) {
    if (open?.k === k) return close();
    anchor.current = el;
    const host = wrap.current!.getBoundingClientRect(), r = el.getBoundingClientRect();
    setOpen({ k, left: Math.max(0, r.left - host.left), top: r.bottom - host.top + 8 });
  }

  // keep the list inside the column, and move focus into it
  useLayoutEffect(() => {
    const p = pick.current, host = wrap.current;
    if (!open || !p || !host) return;
    const over = open.left + p.offsetWidth - host.clientWidth;
    if (over > 0) p.style.left = `${Math.max(0, open.left - over)}px`;
    p.querySelector<HTMLElement>("[aria-selected='true'], [role='option'], button")?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!pick.current?.contains(t) && !anchor.current?.contains(t)) close(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  function keys(e: React.KeyboardEvent) {
    if (!open) return;
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const opts = [...(pick.current?.querySelectorAll<HTMLElement>("[role='option']") ?? [])];
    if (!opts.length) return;
    e.preventDefault();
    const i = opts.indexOf(document.activeElement as HTMLElement);
    opts[(i + (e.key === "ArrowDown" ? 1 : -1) + opts.length) % opts.length].focus();
  }

  const choose = (set: (x: never) => void, value: unknown) => { set(value as never); close(); };

  let options: { label: string; value: unknown; set: (x: never) => void; on: boolean }[] = [];
  if (open?.k === "coach") options = ready.map((c) => ({ label: c.first, value: c, on: c.first === v.coach,
    set: ((c: typeof ready[number]) => { setCoach(c.first); onCoach?.(c.slug); }) as (x: never) => void }));
  if (open?.k === "minutes") options = [...new Set([...MINUTES, v.minutes])].sort((a, b) => a - b)
    .map((m) => ({ label: `${m} minutes`, value: m, on: m === v.minutes, set: setMinutes as (x: never) => void }));
  if (open?.k === "place") options = kits.map((k) => kitWords(k))
    .map((w) => ({ label: w, value: w, on: w === v.place, set: setPlace as (x: never) => void }));
  if (open?.k === "type") options = [...new Set([...TYPES, v.type])]
    .map((t) => ({ label: t, value: t, on: t === v.type, set: setType as (x: never) => void }));

  // ---- the body map: one row per area picked, each with its side and how careful to be ----
  const rowsOf = (b: Record<string, Level>) => [...new Set(Object.keys(b).map(baseArea))];
  const keysOf = (b: Record<string, Level>, area: string) => Object.keys(b).filter((k) => baseArea(k) === area);
  const sideOf = (b: Record<string, Level>, area: string): Side => {
    const ks = keysOf(b, area);
    if (ks.includes(`left ${area}`) && ks.includes(`right ${area}`)) return "both";
    if (ks.includes(`left ${area}`)) return "left";
    if (ks.includes(`right ${area}`)) return "right";
    return null;
  };
  const levelOf = (b: Record<string, Level>, area: string): Level =>
    keysOf(b, area).some((k) => b[k] === "off") ? "off" : "easy";
  const floorKeys = (area: string) => Object.keys(floor).filter((k) => baseArea(k) === area);
  const sideKeys = (area: string, side: Side) =>
    side === "both" ? [`left ${area}`, `right ${area}`] : side ? [`${side} ${area}`] : [area];

  function setRow(area: string, side: Side, level: Level) {
    const next = { ...v.body };
    for (const k of keysOf(next, area)) delete next[k];
    for (const k of sideKeys(area, side)) next[k] = floor[k] === "off" ? "off" : level;
    for (const k of floorKeys(area)) if (!(k in next)) next[k] = floor[k];
    setBody(next);
  }
  function toggleArea(area: string) {
    if (rowsOf(v.body).includes(area)) {
      if (floorKeys(area).length) return;
      const next = { ...v.body };
      for (const k of keysOf(next, area)) delete next[k];
      setBody(next);
    } else setRow(area, null, "easy");
  }
  /** A side that would drop a limit from the health notes can't be picked. */
  const sideLocked = (area: string, side: Side) => floorKeys(area).some((k) => !sideKeys(area, side).includes(k));
  const levelLocked = (area: string, level: Level) => level === "easy" && floorKeys(area).some((k) => floor[k] === "off");

  const { easy, off } = bodyWords(v.body);
  const slot = (k: SlotKey, label: string, text: string, tone?: "off" | "calm") =>
    <Slot k={k} label={label} text={text} open={open?.k === k} onOpen={openSlot} tone={tone} />;

  async function start() {
    setBusy(true);
    if ((await onStart(sentence(v))) === false) setBusy(false);
  }

  const hint = !type && info?.suggest?.reason;
  const picked = rowsOf(v.body);

  return (
    <section className="starter" ref={wrap} aria-label="Plan a workout" onKeyDown={keys}>
      <p className="mad">
        Hey, coach {slot("coach", "Coach", v.coach)}, I'd like {article(v.minutes)}{" "}
        {slot("minutes", "Length", `${v.minutes}-minute`)} {slot("type", "Workout", v.type)}{" "}
        {slot("place", "Where", v.place)}.
      </p>
      <p className="mad mad-2">
        {easy.length === 0 && off.length === 0 ? (<>{slot("body", "Anything bothering you", "Nothing's bothering me", "calm")} today.</>) : (<>
          {easy.length > 0 && <>Go easy on my {slot("body", "Go easy on", list(easy))}</>}
          {off.length > 0 && <>{easy.length ? ", and keep off my " : "Keep off my "}{slot("body", "Keep off", list(off), "off")}</>} today.
        </>)}
      </p>
      {hint && <p className="hint">Suggested because of your log: {hint}.</p>}
      <div className="start-row">
        <button type="button" className="go start" onClick={start} disabled={busy || ready.length === 0}>Plan my workout</button>
        <span className="start-note">{ready.length === 0 && info
          ? "Add a voice key in Settings first."
          : "Your coach plans it with you, then records it once you say go."}</span>
      </div>
      <nav className="else" aria-label="Other things you can do">
        <p className="else-h">Or ask for something else</p>
        <ul className="else-list">
          {OTHER.filter((o) => !o.quick || info?.setup_quick).map((o) => (
            <li key={o.label}>
              <button type="button" className="else-a" onClick={() => (o.fill ? onFill(o.line) : void onStart(o.line))}>
                <span className="else-t">{o.label}</span>
                <span className="else-d">{o.about}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>
      {open && open.k !== "body" && (
        <div className="pick" ref={pick} role="listbox" aria-label={LIST_NAMES[open.k]} style={{ left: open.left, top: open.top }}>
          {options.map((o) => (
            <button key={o.label} type="button" role="option" aria-selected={o.on} className={`opt${o.on ? " on" : ""}`}
              onClick={() => choose(o.set, o.value)}>{o.label}</button>
          ))}
        </div>
      )}
      {open?.k === "body" && (
        <div className="pick pick-body" ref={pick} role="dialog" aria-label={LIST_NAMES.body}
          style={{ left: open.left, top: open.top }}>
          <p className="pick-h">Anything bothering you today?</p>
          <p className="pick-s">Tap where it is. Your coach works around it, today only.</p>
          {GROUPS.map((g) => (
            <div key={g.name} className="bgroup" role="group" aria-label={g.name}>
              <span className="bgroup-h">{g.name}</span>
              <span className="chips">
                {g.areas.map((a) => (
                  <button key={a} type="button" className={`chip${picked.includes(a) ? " on" : ""}`} aria-pressed={picked.includes(a)}
                    disabled={picked.includes(a) && floorKeys(a).length > 0} onClick={() => toggleArea(a)}>{a}</button>
                ))}
              </span>
            </div>
          ))}
          {picked.length > 0 && (
            <ul className="brows">
              {picked.map((a) => {
                const side = sideOf(v.body, a), level = levelOf(v.body, a);
                return (
                  <li key={a} className="brow">
                    <span className="brow-name">{a}{floorKeys(a).length > 0 && <small> from your health notes</small>}</span>
                    {SIDED.has(a) && (
                      <span className="segs" role="radiogroup" aria-label={`Which ${a}`}>
                        {(["left", "right", "both"] as const).map((s) => (
                          <button key={s} type="button" role="radio" aria-checked={side === s} className={`seg${side === s ? " on" : ""}`}
                            disabled={sideLocked(a, s)} onClick={() => setRow(a, side === s && !sideLocked(a, null) ? null : s, level)}>
                            {s === "both" ? "Both" : s === "left" ? "Left" : "Right"}
                          </button>
                        ))}
                      </span>
                    )}
                    <span className="segs" role="radiogroup" aria-label={`How careful with your ${a}`}>
                      {(["easy", "off"] as const).map((lv) => (
                        <button key={lv} type="button" role="radio" aria-checked={level === lv}
                          className={`seg${level === lv ? " on" : ""}`} data-v={lv} disabled={levelLocked(a, lv)}
                          title={levelLocked(a, lv) ? "Set in your health notes; change it in the chat" : undefined}
                          onClick={() => setRow(a, side, lv)}>
                          {lv === "easy" ? "Go easy" : "Keep off"}
                        </button>
                      ))}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
          <button type="button" className="go done" onClick={() => close()}>Done</button>
        </div>
      )}
    </section>
  );
}
