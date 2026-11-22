// A page with the sky behind one short task: signing in, choosing a password, a server that can't be reached.
// `pitch` (the sign-in form's: what this is, and the way to the demos) sits beside the task on a wide screen and
// above it on a narrow one, in place of the tagline over it. `landing` (the sign-in page's front: the demos and the free workouts) takes the whole width instead, with
// `actions` (Sign in, Make an account) at the header's right.
import type { ReactNode } from "react";
import { Mark } from "./Mark";
import { Sky } from "./Sky";

/** What HarmonicFitness is, in one line: over a page with one task, and over the sign-in page's demos. */
export const TAGLINE = "A coach in your ear, and a workout written for today";

export function Solo({ version, children, landing, actions, pitch, after }: {
  version?: string; children?: ReactNode; landing?: ReactNode; actions?: ReactNode;
  /** Beside the task: what this is. `after` goes under the task on a narrow screen, under the pitch on a wide one. */
  pitch?: ReactNode; after?: ReactNode;
}) {
  return (
    <div className="app solo-app">
      <Sky />
      <div className="work">
        <header className="work-top"><Mark version={version} />{actions && <div className="solo-actions">{actions}</div>}</header>
        {landing ? (
          <main className="solo-landing">{landing}</main>
        ) : pitch ? (
          <main className="solo-split">
            <div className="solo-pitch">{pitch}</div>
            <div className="solo-task">{children}</div>
            {after && <div className="solo-after">{after}</div>}
          </main>
        ) : (
          <main className="solo">
            <p className="label eyebrow">{TAGLINE}</p>
            {children}
          </main>
        )}
      </div>
    </div>
  );
}
