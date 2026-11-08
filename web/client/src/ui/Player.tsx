// The small player the Coaches page and the sign-in demos share: a round button, a line to seek along (a real
// slider, so it works from the keyboard), and the time. The <audio> itself is the caller's, so each can load its
// clip when it likes.
import { mss } from "../lib/format";
import { Icon } from "./icons";

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
