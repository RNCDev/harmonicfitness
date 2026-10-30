// The first screen: a request with blanks, filled in from what the app knows about the listener. Tap a blank
// for its choices; the new words roll in like a scoreboard. The second line says what to go easy on, picked
// from a body chart, head to feet: each side a three-way toggle, tapped from OK to go easy to keep off and back. "Plan my workout" sends the request as the first message; its answers stand
// in for the check-in.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { StartInfo, StartKit } from "../api";

/** The areas a listener can name, head to feet: the body chart's rows. */
const ROWS = ["neck", "shoulder", "elbow", "wrist", "rib", "low back", "hip", "groin", "hamstring", "knee", "calf", "ankle", "foot"];
/** Where a new group starts: the trunk, then the legs. */
const GROUP_START = new Set(["rib", "hamstring"]);
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
/** A chip's state: fine, go easy, keep off. Each tap moves it one along. */
type Mark = "clear" | Level;
const MARKS: Mark[] = ["clear", "easy", "off"];
const MARK_WORDS: Record<Mark, string> = { clear: "ok", easy: "go easy", off: "keep off" };

/** "Thursday night": the day and its part, for the line above the request. */
export function partOfDay(d: Date): string {
  const h = d.getHours();
  const part = h < 5 ? "night" : h < 12 ? "morning" : h < 17 ? "afternoon" : h < 21 ? "evening" : "night";
  return `${d.toLocaleDateString("en-US", { weekday: "long" })} ${part}`;
}
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

/** Where each word of a text starts and ends, so a long blank wraps between words, never inside one. */
function words(text: string): [number, number][] {
  const out: [number, number][] = [];
  const re = /\S+/g;
  for (let m = re.exec(text); m; m = re.exec(text)) out.push([m.index, m.index + m[0].length]);
  return out;
}

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
      {words(text).map(([from, to], w) => (
        <span key={`${roll}-w${w}`}>
          {w > 0 && " "}
          <span className="flw">
            {shown.slice(from, to).map((c, j) => (
              <span key={`${roll}-${from + j}`} className="fl" style={{ animationDelay: `${(from + j) * 22}ms` }}>{c}</span>
            ))}
          </span>
        </span>
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
  { label: "Update my interests.", about: "Pick the news, topics, and media your coach talks about between sets.",
    line: "I'd like to change what fills out my workout audio." },
  { label: "Pick a different coach", about: "Hear the other coaches, or make a coach of your own.", line: "I want a new coach." },
  { label: "Give feedback on my last workout", about: "Too long, too easy, loved a story: say so and the next one changes.",
    line: "Feedback on my last workout: ", fill: true },
  { label: "Finish setting me up", about: "Answer the rest of the setup questions, for workouts that fit you better.",
    line: "Finish setting me up.", quick: true },
];

type Props = {
  info: StartInfo | null;
  /** Sends a line as the first message; false when it was refused. */
  onStart: (line: string) => Promise<boolean> | void;
  /** Puts a line in the text box to finish by hand. */
  onFill: (line: string) => void;
  /** The coach the listener picked, for the coach's name in the header. */
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
    if (open.k === "body") { p.querySelector<HTMLElement>("button")?.focus(); return; }   // centred, not anchored
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

  // ---- the body chart: a chip per side (one for the neck and low back), from fine to go easy to keep off ----
  const rank = (m: Mark) => MARKS.indexOf(m);
  /** A chip's limit from the health notes; a limit with no side holds both sides. */
  const floorAt = (key: string): Mark => floor[key] ?? (key !== baseArea(key) ? floor[baseArea(key)] : undefined) ?? "clear";
  const markAt = (key: string): Mark => v.body[key] ?? (key !== baseArea(key) ? v.body[baseArea(key)] : undefined) ?? "clear";

  /** A tap moves a side one along, OK to go easy to keep off and round again; never below its limit. */
  function tap(key: string) {
    const can = MARKS.filter((m) => rank(m) >= rank(floorAt(key)));
    const mark = can[(can.indexOf(markAt(key)) + 1) % can.length];
    const area = baseArea(key);
    const next = { ...v.body };
    if (key !== area && area in next) {   // a sideless limit splits into its two sides once one side changes
      const lv = next[area];
      delete next[area];
      next[`left ${area}`] ??= lv;
      next[`right ${area}`] ??= lv;
    }
    if (mark === "clear") delete next[key];
    else next[key] = mark;
    setBody(next);
  }

  const dot = (k: string, where: "l" | "r" | "both") => {
    const mark = markAt(k);
    const fixed = floorAt(k) === "off";
    return (
      <button type="button" className={`bdot ${where} ${mark}`} data-mark={mark} disabled={fixed}
        aria-label={`${k}: ${MARK_WORDS[mark]}`} title={fixed ? "Set in your health notes; change it in the chat" : undefined}
        onClick={() => tap(k)}>{where === "l" ? "L" : where === "r" ? "R" : ""}</button>
    );
  };

  const { easy, off } = bodyWords(v.body);
  const slot = (k: SlotKey, label: string, text: string, tone?: "off" | "calm") =>
    <Slot k={k} label={label} text={text} open={open?.k === k} onOpen={openSlot} tone={tone} />;

  async function start() {
    setBusy(true);
    if ((await onStart(sentence(v))) === false) setBusy(false);
  }

  const hint = !type && info?.suggest?.reason;
  const shownCoach = ready.find((c) => c.first === v.coach);

  return (
    <section className="starter" ref={wrap} aria-label="Plan a workout" onKeyDown={keys}>
      <p className="eyebrow">{partOfDay(new Date())}{shownCoach ? ` · Coach ${shownCoach.first}, voiced by ${shownCoach.service_name}` : ""}</p>
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
                <span className="else-go" aria-hidden="true">→</span>
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
        <div className="pick pick-body" ref={pick} role="dialog" aria-label={LIST_NAMES.body}>
          <div className="bleft">
            <p className="pick-h">Anything bothering you today?</p>
            <p className="pick-s">Tap a side to change it: once to go easy, twice to keep off, again for OK.</p>
            <ul className="bkey" aria-label="Key">
              <li><i className="bdot easy" aria-hidden="true" />Go easy</li>
              <li><i className="bdot off" aria-hidden="true" />Keep off</li>
            </ul>
            <div className="bsum" aria-live="polite">
              {easy.length === 0 && off.length === 0 ? <p className="bsum-none">Nothing marked: a full workout.</p> : (
                <dl>
                  {easy.length > 0 && <><dt>Go easy</dt><dd>{list(easy)}</dd></>}
                  {off.length > 0 && <><dt>Keep off</dt><dd>{list(off)}</dd></>}
                </dl>
              )}
            </div>
            <div className="bfoot">
              <button type="button" className="quiet" onClick={() => setBody({ ...floor })}>Clear all</button>
              <button type="button" className="go done" onClick={() => close()}>Done</button>
            </div>
          </div>
          <div className="bchart" role="group" aria-label="Body, head to feet">
            {ROWS.map((a) => (
              <div key={a} className="brow2">
                {GROUP_START.has(a) && <hr className="bsep" />}
                <span className="barea">{a}</span>
                {SIDED.has(a) ? <>{dot(`left ${a}`, "l")}{dot(`right ${a}`, "r")}</> : dot(a, "both")}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
