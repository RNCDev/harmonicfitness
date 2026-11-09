// The ready-made workouts: five thirty-minute sessions recorded once (full body, strength, cardio, mobility, core),
// to play before the listener's own coach is ready: on the sign-in page with no account, on the welcome card before
// any key, and on a new listener's first screen. Each is made for no one, so the list says plainly that it isn't adapted to any injury.
// ready.json is written by `./harmonicfitness ready upload` from docs/demos/ready.toml; the MP3s are on the media
// bucket. Until the set is published it's empty, and this shows nothing.
import data from "../ready.json";
import { AudioPlayer } from "../ui/Player";

type ReadyWorkout = { slug: string; order: number; title: string; kind: string; coach: string; minutes: number;
  about: string; audio: string };

export const READY = (data.workouts as ReadyWorkout[]).slice().sort((a, b) => a.order - b.order);

export function ReadyWorkouts({ intro = "Or start now with a ready-made workout" }: { intro?: string }) {
  if (READY.length === 0) return null;
  return (
    <section className="ready" aria-labelledby="ready-h">
      <h3 className="label ready-h" id="ready-h">{intro}</h3>
      <p className="cx-s ready-note">Thirty minutes each, with a chair, a towel and a little floor space, and no
        jumping. {data.warning}</p>
      <ul className="ready-list">
        {READY.map((w) => (
          <li key={w.slug} className="ready-row">
            <p className="ready-t"><span className="head">{w.title}</span>
              <span className="ready-by"> · {w.minutes} min with {w.coach}</span></p>
            <p className="cx-s ready-about">{w.about}</p>
            <AudioPlayer src={w.audio} label={`${w.title} with ${w.coach}`} preload="none" />
            <p className="cx-s"><a href={w.audio} download target="_blank" rel="noopener noreferrer">Download the MP3</a></p>
          </li>
        ))}
      </ul>
    </section>
  );
}
