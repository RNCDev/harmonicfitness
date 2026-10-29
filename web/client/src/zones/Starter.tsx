// The first screen: a sentence with blanks, filled in from what the app knows about the listener. Tap a blank
// for its choices; the new word rolls in like a scoreboard. Start sends the sentence as the first message,
// and its answers stand in for the check-in.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { StartInfo, StartKit } from "../api";

const AREAS = ["foot", "ankle", "calf", "knee", "hamstring", "hip", "groin", "low back", "rib", "shoulder",
  "elbow", "wrist", "neck"];
const SIDED = new Set(["foot", "ankle", "calf", "knee", "hamstring", "hip", "groin", "rib", "shoulder", "elbow", "wrist"]);
const MINUTES = [10, 15, 20, 25, 30, 40, 45, 60];
/** What to do, as it reads after "for": the session goals in plain words, and the usual targets. */
const TYPES = ["strength work", "a full-body session", "cardio", "mobility", "a leg day", "upper body", "core work"];
const FEELINGS = ["fresh", "fine", "a bit tired", "sore", "short on sleep"];
const GOAL_WORDS: Record<string, string> = { strength: "strength work", general: "a full-body session",
  conditioning: "cardio", mobility: "mobility" };
const TARGET_WORDS: Record<string, string> = { legs: "a leg day", "upper body": "upper body", core: "core work" };
const PRESET_WORDS: Record<string, string> = { "hotel-room": "in a hotel room", "hotel-gym": "in a hotel gym",
  "full-gym": "at the gym", bodyweight: "with no gear" };

/** The words for a kit after "I've got 25 minutes": "at home", "in a hotel room", "with my travel kit". */
export function kitWords(k: StartKit): string {
  if (k.preset) return PRESET_WORDS[k.id] ?? `with ${k.label}`;
  return k.id.toLowerCase() === "home" ? "at home" : `with my ${k.label} kit`;
}

type Level = "easy" | "off";
const areaName = (area: string, side: string | null) => `${side ? side + " " : ""}${area.replace(/-/g, " ")}`;

/** The workout type a suggestion picks, when it names one we offer. */
function suggested(info: StartInfo | null): string | null {
  const s = info?.suggest;
  if (!s) return null;
  return (s.target && TARGET_WORDS[s.target]) || GOAL_WORDS[s.goal] || null;
}

function list(xs: string[]): string {
  return xs.length < 3 ? xs.join(" and ") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;
}

/** The sentence as it's sent. */
export function sentence(v: { coach: string; minutes: number; place: string; type: string; feel: string;
  body: Record<string, Level> }): string {
  const easy = Object.keys(v.body).filter((a) => v.body[a] === "easy");
  const off = Object.keys(v.body).filter((a) => v.body[a] === "off");
  let care = "Nothing's bothering me today";
  if (easy.length) care = `Easy on my ${list(easy)} today`;
  if (off.length) care = easy.length ? `${care}, keep off my ${list(off)}` : `Keep off my ${list(off)} today`;
  return `Hey ${v.coach}, I've got ${v.minutes} minutes ${v.place} for ${v.type}. ${care}, and I'm feeling ${v.feel}.`;
}

const still = () => typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const GLYPHS = "abcdefghijklmnopqrstuvwxyz0123456789";

/** A word that rolls in letter by letter when it changes, like a split-flap board. */
function Flap({ text }: { text: string }) {
  const [shown, setShown] = useState<string[]>(() => [...text]);
  const [roll, setRoll] = useState(0);
  const first = useRef(true);
  useEffect(() => {
    if (first.current && !text) return;
    first.current = false;
    if (still()) { setShown([...text]); return; }
    const chars = [...text];
    const left = chars.map((c, i) => (c === " " ? 0 : 3 + (i % 3)));
    setShown(chars.map((c) => (c === " " ? " " : GLYPHS[(Math.random() * GLYPHS.length) | 0])));
    setRoll((r) => r + 1);
    const rand = () => GLYPHS[(Math.random() * GLYPHS.length) | 0];
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
        <span key={`${roll}-${i}`} className="fl" style={{ animationDelay: `${i * 26}ms` }}>{c === " " ? " " : c}</span>
      ))}
    </span>
  );
}

type SlotKey = "coach" | "minutes" | "place" | "type" | "body" | "feel";

/** Each blank's list, as a screen reader names it. */
const LIST_NAMES: Record<SlotKey, string> = { coach: "Coach", minutes: "Length", place: "Where", type: "Workout",
  body: "Anything to look after today", feel: "How you feel" };

function Slot({ k, label, text, open, onOpen, tone }: { k: SlotKey; label: string; text: string; open: boolean;
  onOpen: (k: SlotKey, el: HTMLButtonElement) => void; tone?: "ask" | "off" }) {
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

const OTHER: { label: string; line: string; fill?: boolean; quick?: boolean }[] = [
  { label: "Change my gear", line: "I'd like to change my equipment." },
  { label: "Update an injury", line: "I'd like to update an injury." },
  { label: "What fills the rests", line: "I'd like to change what fills the rests: my interests, news, puzzles and videos." },
  { label: "Switch or make a coach", line: "I want a new coach." },
  { label: "Feedback on my last workout", line: "Feedback on my last workout: ", fill: true },
  { label: "How's my week going", line: "How's my week going?" },
  { label: "Finish setting me up", line: "Finish setting me up.", quick: true },
];

type Props = {
  info: StartInfo | null;
  /** Sends a line as the first message; false when it was refused. */
  onStart: (line: string) => Promise<boolean> | void;
  /** Puts a line in the text box to finish by hand. */
  onFill: (line: string) => void;
  /** The coach the listener picked, for the page's coach bar. */
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
  const [feel, setFeel] = useState<string | null>(null);
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
    type: type ?? suggested(info) ?? "a full-body session",
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
    setOpen({ k, left: Math.max(0, r.left - host.left), top: r.bottom - host.top + 6 });
  }

  // keep the list inside the sheet, and move focus into it
  useLayoutEffect(() => {
    const p = pick.current, host = wrap.current;
    if (!open || !p || !host) return;
    const over = open.left + p.offsetWidth - host.clientWidth;
    if (over > 0) p.style.left = `${Math.max(0, open.left - over)}px`;
    p.querySelector<HTMLElement>("[aria-selected='true'], .seg.on:not(:disabled), [role='option'], button")?.focus();
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
  if (open?.k === "feel") options = FEELINGS
    .map((f) => ({ label: f, value: f, on: f === feel, set: setFeel as (x: never) => void }));

  const rows = [...new Set([...Object.keys(v.body), ...Object.keys(floor),
    ...AREAS.flatMap((a) => (SIDED.has(a) ? [`left ${a}`, `right ${a}`] : [a]))])];
  const setArea = (a: string, level: Level | "fine") => {
    const next = { ...v.body };
    if (level === "fine") delete next[a]; else next[a] = level;
    setBody(next);
  };
  const locked = (a: string, level: Level | "fine") =>
    (floor[a] === "easy" && level === "fine") || (floor[a] === "off" && level !== "off");

  const easy = Object.keys(v.body).filter((a) => v.body[a] === "easy");
  const off = Object.keys(v.body).filter((a) => v.body[a] === "off");
  const slot = (k: SlotKey, label: string, text: string, tone?: "ask" | "off") =>
    <Slot k={k} label={label} text={text} open={open?.k === k} onOpen={openSlot} tone={tone} />;

  async function start() {
    if (!feel) {
      const el = wrap.current?.querySelector<HTMLButtonElement>(".slot[data-k='feel']");
      if (el) { el.classList.remove("nudge"); void el.offsetWidth; el.classList.add("nudge"); openSlot("feel", el); }
      return;
    }
    setBusy(true);
    if ((await onStart(sentence({ ...v, feel }))) === false) setBusy(false);
  }

  const hint = !type && info?.suggest?.reason;

  return (
    <section className="starter" ref={wrap} aria-label="Start a workout" onKeyDown={keys}>
      <p className="mad">
        Hey {slot("coach", "Coach", v.coach)}, I've got {slot("minutes", "Length", `${v.minutes} minutes`)}{" "}
        {slot("place", "Where", v.place)} for {slot("type", "Workout", v.type)}.
      </p>
      <p className="mad mad-2">
        {easy.length === 0 && off.length === 0 ? (<>{slot("body", "Anything sore", "Nothing's bothering me")} today</>) : (<>
          {easy.length > 0 && <>Easy on my {slot("body", "Go easy on", list(easy))} today</>}
          {off.length > 0 && <>{easy.length ? ", keep off my " : "Keep off my "}{slot("body", "Keep off", list(off), "off")}{easy.length ? "" : " today"}</>}
        </>)}, and I'm feeling {slot("feel", "How you feel", feel ?? "pick one", feel ? undefined : "ask")}.
      </p>
      {hint && <p className="hint">{hint}</p>}
      <div className="start-row">
        <button type="button" className="go start" onClick={start} disabled={busy || ready.length === 0}>Start</button>
        <span className="cx-s">{ready.length === 0 && info ? "Add a voice key in Settings first." : "or write your own below"}</span>
      </div>
      <div className="else">
        <p className="else-h">Something else</p>
        <div className="else-list">
          {OTHER.filter((o) => !o.quick || info?.setup_quick).map((o) => (
            <button key={o.label} type="button" className="else-a"
              onClick={() => (o.fill ? onFill(o.line) : void onStart(o.line))}>{o.label}</button>
          ))}
        </div>
      </div>
      {open && open.k !== "body" && (
        <div className="pick" ref={pick} role="listbox" aria-label={LIST_NAMES[open.k]} style={{ left: open.left, top: open.top }}>
          {options.map((o) => (
            <button key={o.label} type="button" role="option" aria-selected={o.on} className={`opt${o.on ? " on" : ""}`}
              onClick={() => choose(o.set, o.value)}>{o.label}</button>
          ))}
        </div>
      )}
      {open?.k === "body" && (
        <div className="pick pick-body" ref={pick} role="dialog" aria-label="Anything to look after today"
          style={{ left: open.left, top: open.top }}>
          <p className="pick-h">Anything to look after today?</p>
          <div className="pick-scroll">
            {rows.map((a) => (
              <div key={a} className="brow">
                <span>{a}{floor[a] && <span className="cx-s"> (in your health notes)</span>}</span>
                <span className="segs" role="radiogroup" aria-label={a}>
                  {(["fine", "easy", "off"] as const).map((lv) => (
                    <button key={lv} type="button" role="radio" aria-checked={(v.body[a] ?? "fine") === lv}
                      className={`seg${(v.body[a] ?? "fine") === lv ? " on" : ""}`} data-v={lv} disabled={locked(a, lv)}
                      title={locked(a, lv) ? "Set in your health notes; change it in the chat" : undefined}
                      onClick={() => setArea(a, lv)}>
                      {lv === "fine" ? "Fine" : lv === "easy" ? "Go easy" : "Avoid"}
                    </button>
                  ))}
                </span>
              </div>
            ))}
          </div>
          <button type="button" className="go done" onClick={() => close()}>Done</button>
        </div>
      )}
    </section>
  );
}
