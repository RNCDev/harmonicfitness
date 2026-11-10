// The app's one audio player, for a workout's MP3 (the chat and Logs), a coach's sample (Coaches) and a demo's clip
// (the sign-in page): a round button, a line to seek along (a real slider, so it works from the keyboard), and the
// time. One clip plays at a time across the page: starting one pauses any other.
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { mss } from "../lib/format";
import { Icon } from "./icons";
import { Notice } from "./Notice";

export function PlayButton({ playing, onClick, label, large = false }: {
  playing: boolean; onClick: () => void; label: string; large?: boolean;
}) {
  return (
    <button type="button" className={`play${large ? " lg" : ""}`} onClick={onClick} aria-label={`${playing ? "Pause" : "Play"} ${label}`}>
      <Icon name={playing ? "pause" : "play"} size={large ? 20 : 14} />
    </button>
  );
}

/** The line to seek along, with `ticks` (seconds) marked on it. Disabled until the clip's length is known. */
export function Seek({ at, length, onSeek, label, ticks = [] }: {
  at: number; length: number; onSeek: (t: number) => void; label: string; ticks?: number[];
}) {
  return (
    <span className="seek">
      <input type="range" min={0} max={length || 1} step={0.1} value={length ? at : 0} disabled={!length}
        aria-label={label} aria-valuetext={length ? `${mss(at)} of ${mss(length)}` : undefined}
        style={{ ["--done" as string]: `${length ? (at / length) * 100 : 0}%` }}
        onChange={(e) => onSeek(Number(e.target.value))} />
      {length > 0 && ticks.filter((t) => t > 0 && t < length).map((t) =>
        <span key={t} className="seek-tick" style={{ left: `${(t / length) * 100}%` }} />)}
    </span>
  );
}

/** "0:12 / 0:45" while it plays or has played, else its length; `idle` before the length is known. */
export function PlayTime({ at, length, playing, idle = "" }: { at: number; length: number; playing: boolean; idle?: string }) {
  return <span className="p-time">{length ? (playing || at > 0 ? `${mss(at)} / ${mss(length)}` : mss(length)) : idle}</span>;
}

/** The clip playing now, anywhere on the page. */
let now: HTMLAudioElement | null = null;

/** Play from `at` seconds (from where it is, without one). */
export type AudioHandle = { play: (at?: number) => void };

type Props = {
  src: string;
  /** What's playing, as a screen reader hears it: "Play <label>", "<label>, position". */
  label: string;
  preload?: "none" | "metadata";
  /** Fetch nothing until the first play (the demos' clips, from the media bucket). */
  lazy?: boolean;
  large?: boolean;
  /** Seconds to mark on the line (a demo's moments). */
  ticks?: number[];
  /** Said where the time goes before the length is known. */
  idle?: string;
  className?: string;
  onPlaying?: (on: boolean) => void;
  /** Any touch of the player: the demos stop turning. */
  onTouch?: () => void;
};

export const AudioPlayer = forwardRef<AudioHandle, Props>(function AudioPlayer({ src, label, preload = "metadata",
  lazy = false, large = false, ticks, idle, className, onPlaying, onTouch }, ref) {
  const audio = useRef<HTMLAudioElement>(null);
  const [on, setOn] = useState(false);
  const [at, setAt] = useState(0);
  const [length, setLength] = useState(0);
  /** The browser refused to play (a file it can't open, or no sound allowed yet): said under the player. */
  const [refused, setRefused] = useState(false);
  const said = useRef({ onPlaying, onTouch });
  said.current = { onPlaying, onTouch };

  useEffect(() => { said.current.onPlaying?.(on); }, [on]);
  // a new clip: the last one stops and is let go
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    const a = audio.current;
    if (!a) return;
    if (!a.paused) a.pause();
    if (lazy) a.removeAttribute("src");
    setOn(false); setAt(0); setLength(0); setRefused(false);
  }, [src, lazy]);
  useEffect(() => {
    const mine = audio.current;   // the ref is cleared before the cleanup runs
    return () => { if (now === mine) now = null; };
  }, []);

  const load = () => {
    const a = audio.current!;
    if (lazy && a.getAttribute("src") !== src) a.src = src;
    return a;
  };
  const start = (a: HTMLAudioElement) => {
    if (now && now !== a && !now.paused) now.pause();
    now = a;
    setRefused(false);
    void a.play()?.catch((e: unknown) => {
      setOn(false);
      // a pause before the play began isn't a refusal
      if (!(e instanceof DOMException && e.name === "AbortError")) setRefused(true);
    });
  };
  const toggle = () => {
    said.current.onTouch?.();
    const a = load();
    if (!a.paused) { a.pause(); return; }
    start(a);
  };
  useImperativeHandle(ref, () => ({
    play: (t?: number) => {
      said.current.onTouch?.();
      const a = load();
      const go = () => { if (t !== undefined) a.currentTime = t; start(a); };
      if (t === undefined || a.readyState >= 1) go(); else a.addEventListener("loadedmetadata", go, { once: true });
    },
  }));
  const sync = (a: HTMLAudioElement) => { setAt(a.currentTime); setLength(Number.isFinite(a.duration) ? a.duration : 0); };

  return (
    <div className={`player${on ? " on" : ""}${className ? " " + className : ""}`}>
      <audio ref={audio} preload={lazy ? "none" : preload} src={lazy ? undefined : src} aria-label={label}
        onPlay={() => setOn(true)} onPause={() => setOn(false)} onEnded={() => { setOn(false); setAt(0); }}
        onTimeUpdate={(e) => sync(e.currentTarget)} onLoadedMetadata={(e) => sync(e.currentTarget)} />
      <PlayButton playing={on} onClick={toggle} label={label} large={large} />
      <Seek at={at} length={length} label={`${label}, position`} ticks={ticks}
        onSeek={(t) => { said.current.onTouch?.(); const a = audio.current; if (a && length) { a.currentTime = t; setAt(t); } }} />
      <PlayTime at={at} length={length} playing={on} idle={idle} />
      <Notice tone="error" className="player-refused">{refused ? "This didn't play. Try again in a moment." : null}</Notice>
    </div>
  );
});
