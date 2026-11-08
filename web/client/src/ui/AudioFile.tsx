// A workout's MP3, in the chat and on the Logs page: play it here, or download it, while the site keeps it (the
// three newest workouts'; any other MP3 a day).
// The meter moves while it plays.
import { useState } from "react";
import type { Audio } from "../lib/api";
import { keptUntil } from "../lib/format";
import { Meter } from "./Mark";
import { AudioPlayer } from "./Player";

export function AudioFile({ audio, titled = false, preload = "metadata" }: {
  audio: Audio;
  /** With its name above it, as the chat shows a new recording; without, beside a card that names it (Logs). */
  titled?: boolean;
  preload?: "metadata" | "none";
}) {
  const [playing, setPlaying] = useState(false);
  const src = `/api/media/${encodeURIComponent(audio.id)}`;
  const expired = !!audio.gone || (audio.expires_at !== null && new Date(audio.expires_at).getTime() <= Date.now());
  const until = audio.expires_at ? keptUntil(audio.expires_at) : "";
  const player = <AudioPlayer src={src} label={audio.name} preload={preload} large={titled} onPlaying={setPlaying} />;
  return (
    <div className={`audio-file${titled ? "" : " compact"}`}>
      {titled && (
        <p className="head audio-name">{!expired && <Meter className="audio-meter" height={22} live={playing} />}{audio.name}</p>
      )}
      {expired ? (
        <p className="cx-s">This recording is no longer kept: the site keeps your three newest workouts. Ask for the
          workout again to record a new one.</p>
      ) : (
        <>
          {titled ? player : <div className="audio-row"><Meter className="audio-meter" height={22} live={playing} />{player}</div>}
          <p className="cx-s">
            <a href={`${src}?download=1`} download={`${audio.name}.mp3`}>Download the MP3</a>
            {until && ` · kept until ${until}`}
          </p>
        </>
      )}
    </div>
  );
}
