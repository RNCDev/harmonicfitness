// A page with the sky behind one short task: signing in, choosing a password, a server that can't be reached.
// `landing` (the sign-in page's front: the demos and the free workouts) takes the whole width instead, with
// `actions` (Sign in, Make an account) at the header's right.
import type { ReactNode } from "react";
import { Mark } from "./Mark";
import { Sky } from "./Sky";

export function Solo({ version, children, landing, actions }: {
  version?: string; children?: ReactNode; landing?: ReactNode; actions?: ReactNode;
}) {
  return (
    <div className="app solo-app">
      <Sky />
      <div className="work">
        <header className="work-top"><Mark version={version} />{actions && <div className="solo-actions">{actions}</div>}</header>
        {landing ? (
          <main className="solo-landing">{landing}</main>
        ) : (
          <main className="solo">
            <p className="label eyebrow">Workouts for your earbuds, written and voiced fresh each time you ask</p>
            {children}
          </main>
        )}
      </div>
    </div>
  );
}
